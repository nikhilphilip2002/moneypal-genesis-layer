"""Bounded provider-native agent selection and governed execution loop."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re
import time
from typing import Any

from app.core.config import settings
from app.services.nlq.catalog import get_catalog
from app.services.nlq.llm import LLMError, LLMProtocolError
from app.services.workbench import history, models, prompts, router
from app.services.workbench.agent_executor import (
    AgentExecutionContext,
    ExecutedAgentCall,
    execute_agent_call,
)
from app.services.workbench.agent_tools import (
    AgentToolAccessDenied,
    AgentToolArgumentsInvalid,
    native_tool_definitions,
    validate_agent_arguments,
)
from app.services.workbench.results import SourceResult

logger = logging.getLogger(__name__)


_MONTH_GRAIN_RE = re.compile(
    r"\b(?:month\s*-?\s*wise|monthly|by\s*-?\s*month|each\s*-?\s*month)\b",
    re.IGNORECASE,
)
_RANKING_RE = re.compile(
    r"\b(?:highest|lowest|top|bottom|most|least|rank(?:ed|ing)?)\b",
    re.IGNORECASE,
)


def _canonicalize_native_arguments(result, state: dict[str, Any]) -> None:
    """Preserve explicit time grain and resolve unambiguous duplicate periods.

    Tool selection is probabilistic even with a strict schema: local models can omit an
    explicitly requested month dimension or populate both nullable period representations.
    These corrections are grounded entirely in the current user text. Ambiguous conflicts
    still use the normal native repair path.
    """
    question = state.get("question", "")
    mentioned_years = {
        int(value) for value in re.findall(r"\b(20\d{2})\b", question)
    }
    month_grain_requested = bool(_MONTH_GRAIN_RE.search(question))
    ranking_requested = bool(_RANKING_RE.search(question))
    changed: dict[str, dict[str, Any]] = {}
    for call in result.tool_calls:
        if call.name != "query_metrics":
            continue

        if month_grain_requested:
            dimensions = call.arguments.get("dimensions")
            if isinstance(dimensions, list) and "month" not in dimensions:
                dimensions.append("month")
                if not ranking_requested and not call.arguments.get("order_by"):
                    call.arguments["order_by"] = {
                        "field": "month", "direction": "asc",
                    }
                changed[call.id] = call.arguments

        period = call.arguments.get("period")
        if not isinstance(period, dict):
            continue
        if month_grain_requested and period.get("grain") != "month":
            period["grain"] = "month"
            changed[call.id] = call.arguments
        start, end, relative = period.get("start"), period.get("end"), period.get("relative")
        if not (start and end and relative):
            continue
        try:
            bound_years = {int(str(start)[:4]), int(str(end)[:4])}
        except (TypeError, ValueError):
            continue
        if not mentioned_years or not bound_years.issubset(mentioned_years):
            continue
        period["relative"] = None
        changed[call.id] = call.arguments

    if not changed or result.assistant_message is None:
        return
    for raw_call in result.assistant_message.get("tool_calls", []) or []:
        if not isinstance(raw_call, dict) or raw_call.get("id") not in changed:
            continue
        function = raw_call.get("function")
        if isinstance(function, dict):
            function["arguments"] = json.dumps(
                changed[str(raw_call["id"])], separators=(",", ":"), default=str,
            )


def _remaining_timeout(state: dict[str, Any], cap: float) -> float:
    started_at = state.get("timing", {}).get("started_at")
    if not isinstance(started_at, (int, float)):
        return cap
    remaining = settings.nlq_request_budget_s - (time.perf_counter() - started_at)
    if remaining <= 0:
        raise TimeoutError("Workbench request deadline exhausted")
    return min(cap, remaining)


def _source_for_call(call) -> str | None:
    if call.name in {
        "query_metrics", "lookup_records", "run_analysis", "create_worklist",
        "generate_briefing", "run_validated_query",
    }:
        return "db"
    if call.name == "search_public_web":
        return "web"
    if call.name == "search_curated_knowledge":
        return {
            "concepts": "knowledge", "schema": "schema", "macro": "macro",
            "competitive": "competitive", "regulatory": "regulatory",
        }.get(str(call.arguments.get("domain", "")))
    return None


def assigned_mode(conversation_id: str, user: str) -> str:
    mode = settings.workbench_agent_mode
    if mode != "canary":
        return mode
    digest = hashlib.sha256(f"{user}\0{conversation_id}".encode()).digest()
    bucket = int.from_bytes(digest[:4], "big") % 100
    return "on" if bucket < settings.workbench_agent_canary_percent else "off"


async def _select(state: dict[str, Any], *, repair_messages=None):
    rounds = int(state.get("_agent_rounds", 0))
    if rounds >= settings.workbench_agent_max_rounds:
        raise LLMProtocolError("native agent exceeded its model-round limit")
    state["_agent_rounds"] = rounds + 1
    catalog = state.setdefault("_agent_catalog", get_catalog())
    definitions = native_tool_definitions(state["source_policy"], catalog=catalog)
    if not definitions:
        raise LLMError("no native tools are authorized for this request")
    prompt = prompts.build_agent_prompt(
        question=state["question"],
        history_messages=state.get("agent_history_messages", state.get("history_messages", [])),
        tool_names=[definition["function"]["name"] for definition in definitions],
    )
    messages = list(prompt.messages)
    if repair_messages:
        messages.extend(repair_messages)
    client = models.for_step("route", sensitive=True)
    return await client.complete(
        messages=messages,
        tools=definitions,
        tool_choice="required",
        parallel_tool_calls=True,
        timeout_s=_remaining_timeout(state, settings.workbench_router_timeout_s),
        call_purpose="agent_select",
        call_kind="repair" if repair_messages else "planned",
        prompt_version=prompt.version,
        prefix_hash=prompt.prefix_hash,
        catalog_version=catalog.version,
    )


def _preflight(result, state: dict[str, Any]) -> list[tuple[str, str]]:
    if not result.tool_calls:
        raise LLMProtocolError(
            "native selection returned no tool_calls; assistant content is not executable"
        )
    _canonicalize_native_arguments(result, state)
    if len(result.tool_calls) > settings.workbench_agent_max_tool_calls:
        raise LLMProtocolError("native selection exceeded the per-turn tool-call limit")
    terminals = [call for call in result.tool_calls if call.name == "finish_without_data"]
    if terminals and len(result.tool_calls) != 1:
        return [(call.id, "finish_without_data must be the only call") for call in terminals]

    failures: list[tuple[str, str]] = []
    for call in result.tool_calls:
        try:
            validate_agent_arguments(
                call.name,
                call.arguments,
                policy=state["source_policy"],
                catalog=state.get("_agent_catalog"),
            )
        except AgentToolAccessDenied:
            raise
        except AgentToolArgumentsInvalid as exc:
            failures.append((call.id, str(exc)))
    return failures


def _repair_messages(result, failures: list[tuple[str, str]]):
    if result.assistant_message is None:
        raise LLMProtocolError("native tool response cannot be replayed for repair")
    messages = [result.assistant_message]
    messages.extend({
        "role": "tool",
        "tool_call_id": call_id,
        "content": json.dumps({
            "status": "error",
            "code": "INVALID_TOOL_ARGUMENTS",
            "message": message[:500],
        }, separators=(",", ":")),
    } for call_id, message in failures)
    return messages


async def select_calls(state: dict[str, Any]):
    result = await _select(state)
    attempted_calls = len(result.tool_calls)
    failures = _preflight(result, state)
    if (
        failures
        and settings.workbench_agent_argument_repairs
        and settings.workbench_agent_max_rounds >= 3
    ):
        result = await _select(state, repair_messages=_repair_messages(result, failures))
        attempted_calls += len(result.tool_calls)
        if attempted_calls > settings.workbench_agent_max_tool_calls:
            raise LLMProtocolError("native repairs exceeded the per-turn tool-call limit")
        failures = _preflight(result, state)
    if failures:
        raise AgentToolArgumentsInvalid(failures[0][1])
    return result


async def shadow(state: dict[str, Any]) -> None:
    """Record protocol/telemetry behavior without execution or visible output changes."""
    try:
        result = await select_calls(state)
        logger.info(
            "native agent shadow selection tools=%s",
            [call.name for call in result.tool_calls],
        )
    except Exception as exc:  # noqa: BLE001 - shadow can never affect the live path
        logger.warning("native agent shadow selection failed: %s", exc)


async def run(state: dict[str, Any]) -> None:
    """Select, execute, stream cards, and reuse the common answer composer."""
    from app.services.workbench.graph import answer_results, sse

    emit = state["emit"]
    state["agent_native"] = True
    await emit.put(sse("stage", {"stage": "routing", "agent": "native"}))
    selected = await select_calls(state)
    calls = selected.tool_calls
    sources = [source for call in calls if (source := _source_for_call(call))]
    sources = list(dict.fromkeys(sources))
    decision = router.RouteDecision(
        route="dispatch",
        sources=sources,
        intent=state["question"],
        model="native_agent",
        reason="native_tool_selection",
        confidence=1.0,
        policy_version=state["source_policy"].version,
        effective_sources=state["source_policy"].effective_sources,
    )
    state["decision"] = decision
    await emit.put(sse("route", {
        "sources": sources,
        "intent": state["question"],
        "model": "native_agent",
        "reason": "native_tool_selection",
        "confidence": 1.0,
        "fallback_used": False,
        "policy_version": decision.policy_version,
        "tools": [call.name for call in calls],
    }))
    history.set_route(
        state["conversation_id"], state["user"], state["turn_id"],
        sources=sources, intent=state["question"], model="native_agent",
        reason="native_tool_selection", confidence=1.0,
        effective_sources=decision.effective_sources,
    )

    deadline = max(
        0.001,
        settings.nlq_request_budget_s
        - (time.perf_counter() - state["timing"]["started_at"]),
    )
    context = AgentExecutionContext(
        user=state["user"], role=state["role"],
        conversation_id=state["conversation_id"], turn_id=state["turn_id"],
        source_policy=state["source_policy"], deadline_s=deadline,
        catalog=state.get("_agent_catalog"),
        catalog_version=getattr(state.get("_agent_catalog"), "version", ""),
        data_access=state.get("data_access"),
        private_entities=tuple(state.get("agent_private_entities", ())),
    )
    for call in calls:
        source = _source_for_call(call)
        if source is not None:
            state["timing"]["source_attempts"].append(source)
            await emit.put(sse("source_start", {"source": source, "tool": call.name}))

    async def execute(call):
        try:
            return await execute_agent_call(call, context)
        except Exception as exc:  # noqa: BLE001 - isolate independent calls
            logger.warning("native tool %s failed: %s", call.name, exc)
            return ExecutedAgentCall(
                call=call,
                error={
                    "code": getattr(exc, "code", "SOURCE_UNAVAILABLE"),
                    "message": str(exc)[:500],
                },
            )

    async def stream_item(item: ExecutedAgentCall) -> None:
        if (
            item.card is None
            and item.error is not None
            and item.error.get("code") != "PII_POLICY_VIOLATION"
        ):
            source = _source_for_call(item.call)
            if source is not None:
                item.card = SourceResult(
                    source=source,
                    card_type="error",
                    payload={
                        "message": item.error.get("message", "Source unavailable."),
                        "code": item.error.get("code", "SOURCE_UNAVAILABLE"),
                        "retryable": item.error.get("code") == "TOOL_TIMEOUT",
                    },
                )
        if item.card is None:
            return
        source = item.card.source
        state["timing"]["source_completions"].append(source)
        await emit.put(sse("source_card", {
            "source": source, "card_type": item.card.card_type, **item.card.payload,
        }))
        state["timing"].setdefault(
            "first_card_ms",
            int((time.perf_counter() - state["timing"]["started_at"]) * 1000),
        )
        try:
            history.add_card(
                state["conversation_id"], state["user"], state["turn_id"],
                {
                    "source": source,
                    "card_type": item.card.card_type,
                    "payload": item.card.payload,
                },
            )
        except Exception:  # noqa: BLE001 - persistence is best effort
            logger.warning("native source card persistence failed", exc_info=True)

    async def execute_batch(batch):
        from app.services.workbench.agent_tools import get_agent_tool

        output: list[ExecutedAgentCall | None] = [None] * len(batch)
        parallel = [
            (index, call) for index, call in enumerate(batch)
            if get_agent_tool(call.name).parallel_safe
        ]
        serial = [
            (index, call) for index, call in enumerate(batch)
            if not get_agent_tool(call.name).parallel_safe
        ]
        if parallel:
            async def indexed(index, call):
                return index, await execute(call)

            tasks = [asyncio.create_task(indexed(index, call)) for index, call in parallel]
            try:
                for task in asyncio.as_completed(tasks):
                    index, item = await task
                    output[index] = item
                    await stream_item(item)
            finally:
                for task in tasks:
                    if not task.done():
                        task.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)
        for index, call in serial:
            output[index] = await execute(call)
            await stream_item(output[index])
        return [item for item in output if item is not None]

    def persist_exchange(selection, items) -> None:
        if selection.assistant_message is None:
            return
        history.add_agent_exchange(
            state["conversation_id"], state["user"], state["turn_id"],
            assistant_message=selection.assistant_message,
            calls=[
                {
                    "id": call.id,
                    "name": call.name,
                    "arguments": validate_agent_arguments(
                        call.name,
                        call.arguments,
                        policy=state["source_policy"],
                        catalog=state.get("_agent_catalog"),
                    ).model_dump(mode="json", exclude_none=True),
                }
                for call in selection.tool_calls
            ],
            tool_messages=[item.replay_message() for item in items],
        )

    executed = await execute_batch(calls)
    persist_exchange(selected, executed)
    exchange_messages = [
        *([selected.assistant_message] if selected.assistant_message is not None else []),
        *(item.replay_message() for item in executed),
    ]

    denied = [
        item for item in executed
        if item.error is not None and item.error.get("code") == "PII_POLICY_VIOLATION"
    ]
    if (
        denied
        and settings.workbench_agent_argument_repairs
        and settings.workbench_agent_max_rounds >= 3
    ):
        repaired_selection = await _select(state, repair_messages=[
            *exchange_messages,
            {
                "role": "user",
                "content": (
                    "The external-search call was denied by outbound privacy policy. "
                    "Make exactly one replacement search_public_web call containing only "
                    "a complete public query, or use finish_without_data to refuse."
                ),
            },
        ])
        failures = _preflight(repaired_selection, state)
        allowed_repair_names = {"search_public_web", "finish_without_data"}
        if failures or any(
            call.name not in allowed_repair_names for call in repaired_selection.tool_calls
        ):
            raise AgentToolArgumentsInvalid(
                failures[0][1] if failures else "outbound repair selected an unrelated tool"
            )
        if len(calls) + len(repaired_selection.tool_calls) > settings.workbench_agent_max_tool_calls:
            raise LLMProtocolError("native repairs exceeded the per-turn tool-call limit")
        for call in repaired_selection.tool_calls:
            source = _source_for_call(call)
            if source is not None:
                state["timing"]["source_attempts"].append(source)
                await emit.put(sse(
                    "source_start",
                    {"source": source, "tool": call.name, "repair": True},
                ))
        repaired = await execute_batch(repaired_selection.tool_calls)
        persist_exchange(repaired_selection, repaired)
        exchange_messages.extend([
            *(
                [repaired_selection.assistant_message]
                if repaired_selection.assistant_message is not None else []
            ),
            *(item.replay_message() for item in repaired),
        ])
        second_denial = next(
            (
                item for item in repaired
                if item.error is not None
                and item.error.get("code") == "PII_POLICY_VIOLATION"
            ),
            None,
        )
        if second_denial is not None:
            second_denial.error = None
            second_denial.terminal = {
                "outcome": "refuse",
                "message": (
                    "I can’t send private customer, account, or repayment details to "
                    "public web search."
                ),
                "suggestions": [],
                "reason_code": "PII_POLICY_VIOLATION",
            }
        executed = [item for item in executed if item not in denied] + repaired

    synthesis_prompt = prompts.build_agent_prompt(
        question=state["question"],
        history_messages=state.get("agent_history_messages", []),
        tool_names=[call.name for call in calls],
    )
    state["agent_synthesis_messages"] = [
        *synthesis_prompt.messages,
        *exchange_messages,
        {
            "role": "user",
            "content": (
                "Answer the original question now using only the tool results above. "
                "Do not call another tool. Do not introduce unsupported numbers. For a "
                "large result table, summarize the leading result and tell the user the "
                "full rows are in the table; do not enumerate the table in prose."
            ),
        },
    ]
    state["agent_prompt_prefix_hash"] = synthesis_prompt.prefix_hash
    terminal = next((item for item in executed if item.terminal is not None), None)
    if terminal is not None:
        payload = terminal.terminal or {}
        outcome = payload.get("outcome")
        answer = {
            "status": "clarify" if outcome == "clarify" else "refused",
            "text": payload.get("message", ""),
            "sources": [], "citations": [], "unavailable_sources": [], "limitations": [],
            "suggestions": payload.get("suggestions", []),
            "reason": payload.get("reason_code"),
        }
        await emit.put(sse("refusal" if outcome == "refuse" else "answer", answer))
        history.set_answer(
            state["conversation_id"], state["user"], state["turn_id"], answer,
        )
        return

    results = []
    for item in executed:
        if item.card is None:
            continue
        results.append(item.card)
    state["results"] = results
    await answer_results(state)


__all__ = ["assigned_mode", "run", "select_calls", "shadow"]
