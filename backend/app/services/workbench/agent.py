"""Bounded provider-native agent selection and governed execution loop."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
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
    if call.name == "inspect_loan_catalog":
        return "schema"
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


async def _select(
    state: dict[str, Any], *, repair_messages=None, reroute: bool = False,
):
    rounds = int(state.get("_agent_rounds", 0))
    if rounds >= settings.workbench_agent_max_rounds:
        raise LLMProtocolError("native agent exceeded its model-round limit")
    state["_agent_rounds"] = rounds + 1
    catalog = state.setdefault("_agent_catalog", get_catalog())
    catalog_context = prompts.build_agent_catalog_context(state["question"], catalog)
    client = models.for_step("route", sensitive=True)

    selected_tool = None if reroute else state.get("_agent_selected_tool")
    if not repair_messages or not selected_tool:
        route_tool_names = None
        if catalog_context.requires_validated_query:
            route_tool_names = (
                "run_validated_query", "lookup_records", "finish_without_data",
            )
        route_definitions = native_tool_definitions(
            state["source_policy"], catalog=catalog, tool_names=route_tool_names,
            route_only=True,
        )
        if not route_definitions:
            raise LLMError("no native tools are authorized for this request")
        route_prompt = prompts.build_agent_prompt(
            question=state["question"],
            history_messages=state.get(
                "agent_history_messages", state.get("history_messages", []),
            ),
            tool_names=[definition["function"]["name"] for definition in route_definitions],
            catalog=catalog,
            catalog_context=catalog_context,
        )
        route_messages = list(route_prompt.messages)
        if repair_messages:
            route_messages.extend(repair_messages)
            route_messages.append({
                "role": "user",
                "content": (
                    "Inspect the complete tool results above. Choose the next authorized "
                    "capability needed to answer the original question or recover from the "
                    "reported error. Do not repeat a failed call unchanged."
                ),
            })
        routed = await client.complete(
            messages=route_messages,
            tools=route_definitions,
            tool_choice="required",
            parallel_tool_calls=False,
            timeout_s=_remaining_timeout(state, settings.workbench_router_timeout_s),
            call_purpose="agent_route",
            call_kind="planned",
            prompt_version=route_prompt.version,
            prefix_hash=route_prompt.prefix_hash,
            catalog_version=catalog.version,
        )
        if len(routed.tool_calls) != 1:
            raise LLMProtocolError("native route selection must choose exactly one tool")
        selected_tool = routed.tool_calls[0].name
        state["_agent_selected_tool"] = selected_tool

    definitions = native_tool_definitions(
        state["source_policy"],
        catalog=catalog,
        metric_ids=catalog_context.metrics,
        dimension_ids=catalog_context.dimensions,
        filter_dimension_ids=catalog_context.filter_dimensions,
        table_names=catalog_context.tables,
        tool_names=[selected_tool],
    )
    if not definitions:
        raise LLMError(f"native tool {selected_tool!r} is not authorized for this request")
    prompt = prompts.build_agent_prompt(
        question=state["question"],
        history_messages=state.get("agent_history_messages", state.get("history_messages", [])),
        tool_names=[definition["function"]["name"] for definition in definitions],
        catalog=catalog,
        catalog_context=catalog_context,
    )
    messages = [
        *prompt.messages,
        *(repair_messages or []),
        {
            "role": "user",
            "content": (
                f"The capability-selection stage chose {selected_tool}. Call that function "
                "now with the complete arguments for the original question."
            ),
        },
    ]
    return await client.complete(
        messages=messages,
        tools=definitions,
        tool_choice="required",
        parallel_tool_calls=False,
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
        repair_messages = _repair_messages(result, failures)
        if all(state.get(key) for key in ("conversation_id", "user", "turn_id")):
            history.add_agent_exchange(
                state["conversation_id"], state["user"], state["turn_id"],
                assistant_message=result.assistant_message,
                calls=[{
                    "id": call.id,
                    "name": call.name,
                    "arguments": call.arguments,
                } for call in result.tool_calls],
                tool_messages=repair_messages[1:],
            )
        result = await _select(state, repair_messages=repair_messages)
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
    tool_call_count = len(calls)
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

    failed = [
        item for item in executed
        if item.error is not None and item.error.get("code") != "PII_POLICY_VIOLATION"
    ]
    if (
        failed
        and settings.workbench_agent_argument_repairs
        and int(state.get("_agent_rounds", 0)) < settings.workbench_agent_max_rounds
        and len(calls) < settings.workbench_agent_max_tool_calls
    ):
        repaired_selection = await _select(
            state, repair_messages=exchange_messages, reroute=True,
        )
        failures = _preflight(repaired_selection, state)
        if failures:
            raise AgentToolArgumentsInvalid(failures[0][1])
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
        tool_call_count += len(repaired_selection.tool_calls)
        persist_exchange(repaired_selection, repaired)
        exchange_messages.extend([
            *(
                [repaired_selection.assistant_message]
                if repaired_selection.assistant_message is not None else []
            ),
            *(item.replay_message() for item in repaired),
        ])
        executed = [item for item in executed if item not in failed] + repaired

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
        tool_call_count += len(repaired_selection.tool_calls)
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

    while (
        not any(item.terminal is not None for item in executed)
        and int(state.get("_agent_rounds", 0)) < settings.workbench_agent_max_rounds
        and tool_call_count < settings.workbench_agent_max_tool_calls
    ):
        catalog_context = prompts.build_agent_catalog_context(
            state["question"], state.get("_agent_catalog"),
        )
        definitions = native_tool_definitions(
            state["source_policy"],
            catalog=state.get("_agent_catalog"),
            metric_ids=catalog_context.metrics,
            dimension_ids=catalog_context.dimensions,
            filter_dimension_ids=catalog_context.filter_dimensions,
            table_names=catalog_context.tables,
        )
        continuation_prompt = prompts.build_agent_prompt(
            question=state["question"],
            history_messages=state.get("agent_history_messages", []),
            tool_names=[definition["function"]["name"] for definition in definitions],
            catalog=state.get("_agent_catalog"),
            catalog_context=catalog_context,
        )
        continuation_messages = [
            *continuation_prompt.messages,
            *exchange_messages,
            {
                "role": "user",
                "content": (
                    "Review the original question and every complete tool result above. "
                    "If more evidence or a corrected query is needed, call the appropriate "
                    "authorized function with complete arguments. Otherwise answer the "
                    "original question now using only those tool results."
                ),
            },
        ]
        state["_agent_rounds"] = int(state.get("_agent_rounds", 0)) + 1
        client = models.for_step("synthesize", sensitive=True)
        continuation = await client.complete(
            messages=continuation_messages,
            tools=definitions,
            tool_choice="auto",
            parallel_tool_calls=False,
            timeout_s=_remaining_timeout(state, settings.workbench_composer_timeout_s),
            call_purpose="agent_continue",
            prompt_version=continuation_prompt.version,
            prefix_hash=continuation_prompt.prefix_hash,
            catalog_version=getattr(state.get("_agent_catalog"), "version", ""),
            max_output_tokens=settings.workbench_composer_max_tokens,
        )
        if not continuation.tool_calls:
            if not continuation.text.strip():
                raise LLMProtocolError(
                    "native continuation returned neither tool calls nor an answer"
                )
            state["agent_final_result"] = continuation
            history.set_synthesis(
                state["conversation_id"], state["user"], state["turn_id"],
                continuation.text.strip(),
            )
            break

        continuation_failures = _preflight(continuation, state)
        if continuation_failures:
            invalid_messages = _repair_messages(continuation, continuation_failures)
            history.add_agent_exchange(
                state["conversation_id"], state["user"], state["turn_id"],
                assistant_message=continuation.assistant_message,
                calls=[{
                    "id": call.id,
                    "name": call.name,
                    "arguments": call.arguments,
                } for call in continuation.tool_calls],
                tool_messages=invalid_messages[1:],
            )
            exchange_messages.extend(invalid_messages)
            tool_call_count += len(continuation.tool_calls)
            continue
        if tool_call_count + len(continuation.tool_calls) > settings.workbench_agent_max_tool_calls:
            raise LLMProtocolError("native agent exceeded the per-turn tool-call limit")
        for call in continuation.tool_calls:
            source = _source_for_call(call)
            if source is not None:
                state["timing"]["source_attempts"].append(source)
                await emit.put(sse(
                    "source_start", {"source": source, "tool": call.name},
                ))
        continued = await execute_batch(continuation.tool_calls)
        persist_exchange(continuation, continued)
        exchange_messages.extend([
            *(
                [continuation.assistant_message]
                if continuation.assistant_message is not None else []
            ),
            *(item.replay_message() for item in continued),
        ])
        tool_call_count += len(continuation.tool_calls)
        executed.extend(continued)

    synthesis_prompt = prompts.build_agent_prompt(
        question=state["question"],
        history_messages=state.get("agent_history_messages", []),
        tool_names=[call.name for call in calls],
        catalog=state.get("_agent_catalog"),
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
