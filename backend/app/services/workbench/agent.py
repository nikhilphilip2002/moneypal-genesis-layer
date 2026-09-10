"""Bounded provider-native agent: one loop, one budget, one repair mechanism.

Every LLM request is one round of the :class:`TurnBudget`, every attempted tool call is one
call of it, and every failure the model can recover from (invalid arguments, an unknown
tool, a policy denial, an execution error) is returned to the model as a typed ``tool``
observation on the next round. Nothing here narrows the tool schema on lexical grounds and
nothing fabricates a tool call the model did not emit.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass
from typing import Any

from app.core.config import settings
from app.services.nlq.catalog import get_catalog
from app.services.nlq.llm import LLMError, LLMProtocolError, LLMTimeout
from app.services.workbench import history, models, prompts
from app.services.workbench.agent_executor import (
    AgentExecutionContext,
    ExecutedAgentCall,
    execute_agent_call,
)
from app.services.workbench.agent_tools import (
    AgentToolAccessDenied,
    AgentToolArgumentsInvalid,
    AgentToolError,
    AgentToolNotFound,
    get_agent_tool,
    native_tool_definitions,
    validate_agent_arguments,
    visible_agent_tools,
)
from app.services.workbench.results import ExecutionDecision, SourceResult

logger = logging.getLogger(__name__)


class BudgetExhausted(LLMProtocolError):
    """The turn spent its rounds or tool calls before the model finished."""


@dataclass
class TurnBudget:
    """The only gate on the agent loop: rounds, calls, and the shared request deadline.

    A round is exactly one LLM request, whichever purpose it serves (selection,
    continuation, final synthesis, synthesis repair). A call is one tool call the model
    attempted, valid or not.
    """

    max_rounds: int
    max_calls: int
    deadline: float
    rounds_used: int = 0
    calls_used: int = 0

    @property
    def rounds_remaining(self) -> int:
        return max(0, self.max_rounds - self.rounds_used)

    @property
    def calls_remaining(self) -> int:
        return max(0, self.max_calls - self.calls_used)

    @property
    def expired(self) -> bool:
        return time.perf_counter() >= self.deadline

    def remaining_s(self, cap: float) -> float:
        remaining = self.deadline - time.perf_counter()
        if remaining <= 0:
            raise TimeoutError("Workbench request deadline exhausted")
        return min(cap, remaining)

    def charge_round(self, purpose: str = "") -> None:
        if self.rounds_used >= self.max_rounds:
            raise BudgetExhausted(
                f"native agent exceeded its model-round limit ({self.max_rounds}) "
                f"before {purpose or 'the next request'}"
            )
        self.rounds_used += 1

    def charge_call(self, count: int = 1) -> None:
        self.calls_used += count
        if self.calls_used > self.max_calls:
            raise BudgetExhausted(
                f"native agent exceeded the per-turn tool-call limit ({self.max_calls})"
            )

    def snapshot(self) -> dict[str, int]:
        return {
            "rounds_used": self.rounds_used, "max_rounds": self.max_rounds,
            "calls_used": self.calls_used, "max_calls": self.max_calls,
        }


def _budget(state: dict[str, Any]) -> TurnBudget:
    started_at = state.get("timing", {}).get("started_at")
    if not isinstance(started_at, (int, float)):
        started_at = time.perf_counter()
    budget = TurnBudget(
        max_rounds=settings.workbench_agent_max_rounds,
        max_calls=settings.workbench_agent_max_tool_calls,
        deadline=started_at + settings.nlq_request_budget_s,
    )
    state["_agent_budget"] = budget
    return budget


_CURATED_SOURCES = {
    "concepts": "knowledge", "macro": "macro",
    "competitive": "competitive", "regulatory": "regulatory",
}


def _source_for_call(call) -> str | None:
    from app.mcp import postgres_client

    if postgres_client.is_model_tool(call.name):
        return "db"
    if call.name == "search_public_web":
        return "web"
    if call.name == "search_curated_knowledge":
        return _CURATED_SOURCES.get(str(call.arguments.get("domain", "")))
    return None


_USER_ERROR_MESSAGES = {
    "TOOL_TIMEOUT": "This source took too long to answer.",
    "COMPILE_REJECTED": "The generated query did not pass the safety checks.",
    "NO_MATCHING_ROWS": "No matching records were found.",
    "SOURCE_UNAVAILABLE": "This source is unavailable right now.",
}


def _user_error_message(code: str, turn_id: str) -> str:
    base = _USER_ERROR_MESSAGES.get(code, _USER_ERROR_MESSAGES["SOURCE_UNAVAILABLE"])
    return f"{base} (reference {turn_id})"


_PII_REFUSAL_TEXT = (
    "I can’t send private customer, account, or repayment details to public web search."
)
_SOURCE_REFUSAL_TEXT = "That source is not enabled for this request."
_BUDGET_LIMITATION = {
    "source": "agent",
    "reason": (
        "The model's turn budget ran out before it could write the answer; the retrieved "
        "result is shown as returned."
    ),
}

# One nudge per request kind, appended only when the transcript already holds this turn's
# tool exchange. ``required`` re-selects after a failure, ``auto`` lets the model choose
# between more evidence and an answer, ``none`` is the reserved final synthesis round.
_NUDGES = {
    "required": (
        "Inspect the complete tool results above. Choose the next authorized capability "
        "needed to answer the original question or recover from the reported error. Do "
        "not repeat a failed call unchanged."
    ),
    "auto": (
        "Review the original question and every complete tool result above. If more "
        "evidence or a corrected query is needed, call the appropriate authorized function "
        "with complete arguments. Otherwise answer the original question now using only "
        "those tool results."
    ),
    "none": (
        "Answer the original question now using only the tool results above. Do not call "
        "another tool. Do not introduce unsupported numbers. For a large result table, "
        "summarize the leading result and tell the user the full rows are in the table; "
        "do not enumerate the table in prose."
    ),
}
_PURPOSES = {"required": "agent_select", "auto": "agent_continue", "none": "agent_synthesize"}
# The stage each request kind is recorded under in the turn's event stream.
_STAGES = {"required": "route", "auto": "continue", "none": "synthesize"}


async def _select(
    state: dict[str, Any], *, repair_messages=None, tool_choice: str = "required",
    supplement: str = "",
):
    """Make exactly one provider request with every authorized tool.

    The catalog context is recomputed from the question plus the latest tool error so a
    dimension or table named in an error can surface as a candidate. Rounds are charged by
    the caller so selection-only callers and the full loop share one accounting.
    """
    budget: TurnBudget = state["_agent_budget"]
    catalog = state.setdefault("_agent_catalog", get_catalog())
    catalog_context = prompts.build_agent_catalog_context(
        state["question"], catalog, supplement=supplement,
    )
    definitions = native_tool_definitions(state["source_policy"], catalog=catalog)
    if state["source_policy"].allows("db"):
        from app.mcp import postgres_client

        if not postgres_client.model_tool_definitions():
            await postgres_client.discover_model_tools()
        definitions = [*postgres_client.model_tool_definitions(), *definitions]
    if not definitions:
        raise LLMError("no native tools are authorized for this request")
    prompt = prompts.build_agent_prompt(
        question=state["question"],
        history_messages=state.get("agent_history_messages", []),
        tool_names=[definition["function"]["name"] for definition in definitions],
        catalog=catalog,
        catalog_context=catalog_context,
    )
    messages = [*prompt.messages, *(repair_messages or [])]
    if repair_messages:
        messages.append({"role": "user", "content": _NUDGES[tool_choice]})
        _persist_nudge(state, tool_choice)
    selecting = tool_choice == "required"
    if not selecting:
        # The exact context of the answering request, so a synthesis repair in
        # graph.answer_results replays what the model actually saw.
        state["agent_synthesis_messages"] = messages
    client = models.client()
    extra: dict[str, Any] = {}
    if not selecting:
        extra["max_output_tokens"] = settings.workbench_agent_synthesis_max_tokens
    return await client.complete(
        messages=messages,
        tools=definitions,
        tool_choice=tool_choice,
        parallel_tool_calls=False,
        timeout_s=budget.remaining_s(settings.llm_timeout_s),
        call_purpose=_PURPOSES[tool_choice],
        call_kind="repair" if repair_messages and selecting else "planned",
        catalog_version=catalog.version,
        **extra,
    )


def _preflight(result, state: dict[str, Any]) -> list[tuple[str, str, str]]:
    """Validate and reauthorize every call; one ``(call_id, message, code)`` per failure."""
    failures: list[tuple[str, str, str]] = []
    terminals = [call for call in result.tool_calls if call.name == "finish_without_data"]
    if terminals and len(result.tool_calls) != 1:
        failures.extend(
            (call.id, "finish_without_data must be the only call", "INVALID_TOOL_ARGUMENTS")
            for call in terminals
        )
    for call in result.tool_calls:
        if terminals and len(result.tool_calls) != 1 and call in terminals:
            continue
        try:
            from app.mcp import postgres_client

            if postgres_client.is_model_tool(call.name):
                state["source_policy"].require("db")
                if not isinstance(call.arguments, dict):
                    raise AgentToolArgumentsInvalid("MCP tool arguments must be a JSON object")
                continue
            parsed = validate_agent_arguments(
                call.name, call.arguments,
                policy=state["source_policy"], catalog=state.get("_agent_catalog"),
            )
            constraints = [
                *getattr(parsed, "filters", ()),
                *getattr(parsed, "having", ()),
            ]
            dimensions = set(getattr(parsed, "dimensions", ()))
            grouped_null_fields = list(dict.fromkeys(
                item.field
                for item in constraints
                if item.op == "is_null" and item.field in dimensions
            ))
            if grouped_null_fields:
                fields = ", ".join(grouped_null_fields)
                raise AgentToolArgumentsInvalid(
                    f"cannot group by {fields} while filtering the same dimension to null; "
                    "remove the grouping or the null constraint based on the user's request"
                )
        except AgentToolAccessDenied as exc:
            failures.append((call.id, str(exc), "POLICY_DENIED"))
        except AgentToolNotFound as exc:
            failures.append((call.id, str(exc), "TOOL_NOT_FOUND"))
        except AgentToolArgumentsInvalid as exc:
            failures.append((call.id, str(exc), "INVALID_TOOL_ARGUMENTS"))
        except Exception as exc:  # noqa: BLE001 - every call failure is model-repairable
            logger.exception("native tool preflight failed for %s", call.name)
            failures.append((call.id, str(exc)[:500], "TOOL_VALIDATION_ERROR"))
    return failures


def _authorized_tool_names(state: dict[str, Any]) -> list[str]:
    from app.mcp import postgres_client

    names = [tool.name for tool in visible_agent_tools(state["source_policy"])]
    if state["source_policy"].allows("db"):
        names = [*postgres_client.readiness()["tools"], *names]
    return names


def _failure_observation(call, message: str, code: str, state: dict[str, Any] | None):
    payload: dict[str, Any] = {"status": "error", "code": code, "message": message[:500]}
    if code == "POLICY_DENIED":
        payload["denied"] = {
            "tool": call.name, "source": _source_for_call(call), "policy": "source_access",
        }
        if state is not None:
            payload["authorized_tools"] = _authorized_tool_names(state)
    return {
        "role": "tool", "tool_call_id": call.id,
        "content": json.dumps(payload, separators=(",", ":")),
    }


def _repair_messages(
    result, failures: list[tuple[str, str, str]], *,
    executed: list[ExecutedAgentCall] | tuple[ExecutedAgentCall, ...] = (),
    state: dict[str, Any] | None = None, durable: bool = False,
):
    """The assistant message plus exactly one tool message per call it contains.

    Failed calls carry their typed error; executed calls carry their real observation
    (bounded for the model, complete when ``durable``), so replay parity always holds.
    """
    if result.assistant_message is None:
        raise LLMProtocolError("native tool response cannot be replayed for repair")
    failed = {call_id: (message, code) for call_id, message, code in failures}
    items = {item.call.id: item for item in executed}
    messages = [result.assistant_message]
    for call in result.tool_calls:
        if call.id in failed:
            message, code = failed[call.id]
            messages.append(_failure_observation(call, message, code, state))
        elif call.id in items:
            item = items[call.id]
            messages.append(item.replay_message() if durable else item.observation_message())
        else:
            messages.append(_failure_observation(
                call, "the call was not executed", "SOURCE_UNAVAILABLE", state,
            ))
    return messages


def _raise_first_failure(failures: list[tuple[str, str, str]]) -> None:
    _call_id, message, code = failures[0]
    if code == "POLICY_DENIED":
        raise AgentToolAccessDenied(message)
    if code == "TOOL_NOT_FOUND":
        raise AgentToolNotFound(message)
    raise AgentToolArgumentsInvalid(message)


def _stored_arguments(state: dict[str, Any], call, failed: bool) -> dict[str, Any]:
    if failed:
        return call.arguments
    from app.mcp import postgres_client

    if postgres_client.is_model_tool(call.name):
        return call.arguments
    try:
        return validate_agent_arguments(
            call.name, call.arguments,
            policy=state["source_policy"], catalog=state.get("_agent_catalog"),
        ).model_dump(mode="json", exclude_none=True)
    except AgentToolError:
        return call.arguments


def _persistable(state) -> bool:
    return all(state.get(key) for key in ("conversation_id", "user", "turn_id"))


def _persist_exchange(state, result, failures, executed, *, stage: str = "route") -> None:
    """One write per round: the assistant message, its calls, their complete results,
    and the rendered cards the client was streamed. The ``tool_result`` events carry
    the cards' content, so the cards get no event of their own."""
    if result.assistant_message is None:
        return
    if not _persistable(state):
        return
    failed_ids = {call_id for call_id, _message, _code in failures}
    history.add_agent_exchange(
        state["conversation_id"], state["user"], state["turn_id"],
        assistant_message=result.assistant_message,
        calls=[
            {
                "id": call.id, "name": call.name,
                "arguments": _stored_arguments(state, call, call.id in failed_ids),
            }
            for call in result.tool_calls
        ],
        tool_messages=_repair_messages(
            result, failures, executed=executed, state=state, durable=True,
        )[1:],
        stage=stage,
        cards=[
            {
                "source": item.card.source, "card_type": item.card.card_type,
                "payload": item.card.payload, "call_id": item.call.id,
            }
            for item in executed if item.card is not None
        ],
    )


def _persist_nudge(state, tool_choice: str) -> None:
    """The nudge is part of the transcript the model saw; the record says so."""
    if not _persistable(state):
        return
    budget = state.get("_agent_budget")
    try:
        history.add_system_message(
            state["conversation_id"], state["user"], state["turn_id"],
            content=_NUDGES[tool_choice], kind="nudge", stage=_STAGES[tool_choice],
            round_number=budget.rounds_used if budget is not None else 0,
        )
    except Exception:  # noqa: BLE001 - persistence is best effort
        logger.warning("native nudge persistence failed", exc_info=True)


def _protocol_repair_message(exc: BaseException, tool_choice: str) -> dict[str, str]:
    instruction = (
        "Return one valid native tool call with a unique call ID, an authorized function "
        "name, and JSON-object arguments."
        if tool_choice == "required"
        else "Return either a valid authorized native tool call or a non-empty final answer."
    )
    if tool_choice == "none":
        instruction = "Return a non-empty final answer and do not call a tool."
    return {
        "role": "user",
        "content": json.dumps({
            "status": "error",
            "code": "MODEL_PROTOCOL_ERROR",
            "message": str(exc)[:500],
            "instruction": instruction,
        }, separators=(",", ":")),
    }


def _persist_protocol_repair(
    state: dict[str, Any], message: dict[str, str], tool_choice: str,
) -> None:
    if not _persistable(state):
        return
    budget = state.get("_agent_budget")
    try:
        history.add_system_message(
            state["conversation_id"], state["user"], state["turn_id"],
            content=message["content"], kind="protocol_repair",
            stage=_STAGES[tool_choice],
            round_number=budget.rounds_used if budget is not None else 0,
        )
    except Exception:  # noqa: BLE001 - persistence is best effort
        logger.warning("native protocol repair persistence failed", exc_info=True)


def _queue_protocol_repair(
    state: dict[str, Any], exchange: list[dict[str, Any]], exc: BaseException,
    tool_choice: str, *, assistant_message: dict[str, Any] | None = None,
) -> None:
    if assistant_message is not None:
        exchange.append(assistant_message)
    feedback = _protocol_repair_message(exc, tool_choice)
    exchange.append(feedback)
    _persist_protocol_repair(state, feedback, tool_choice)


def _denial(failures, executed) -> dict[str, Any] | None:
    """The latest policy denial of a round, or None."""
    latest = None
    for _call_id, message, code in failures:
        if code == "POLICY_DENIED":
            latest = {"policy": "source_access", "message": message}
    for item in executed:
        if item.error is not None and item.error.get("code") == "POLICY_DENIED":
            latest = {
                "policy": item.error.get("denied", {}).get("policy", "source_access"),
                "message": item.error.get("message", ""),
            }
    return latest


def _latest_error(failures, executed) -> str:
    text = ""
    for _call_id, message, _code in failures:
        text = message
    for item in executed:
        if item.error is not None:
            text = str(item.error.get("message", ""))
    return text


async def select_calls(state: dict[str, Any]):
    """Select without executing for the offline native-call evaluator.

    Preflight failures are returned to the model as observations while the budget lasts;
    when it runs out the first failure is raised so the caller can classify it.
    """
    budget = _budget(state)
    exchange: list[dict[str, Any]] = []
    while True:
        budget.charge_round("agent_select")
        try:
            result = await _select(state, repair_messages=exchange or None)
        except LLMProtocolError as exc:
            if not budget.rounds_remaining:
                raise
            _queue_protocol_repair(state, exchange, exc, "required")
            continue
        if not result.tool_calls:
            exc = LLMProtocolError(
                "native selection returned no tool_calls; assistant content is not executable"
            )
            if not budget.rounds_remaining:
                raise exc
            _persist_exchange(state, result, (), ())
            _queue_protocol_repair(
                state, exchange, exc, "required", assistant_message=result.assistant_message,
            )
            continue
        budget.charge_call(len(result.tool_calls))
        failures = _preflight(result, state)
        if not failures:
            return result
        if not budget.rounds_remaining:
            _raise_first_failure(failures)
        _persist_exchange(state, result, failures, ())
        exchange.extend(_repair_messages(result, failures, state=state))


async def _execute_one(state, context: AgentExecutionContext, call) -> ExecutedAgentCall:
    try:
        return await execute_agent_call(call, context)
    except Exception as exc:  # noqa: BLE001 - isolate independent calls
        logger.warning("native tool %s failed: %s", call.name, exc)
        code = getattr(exc, "code", "SOURCE_UNAVAILABLE")
        error: dict[str, Any] = {
            "code": code,
            "message": str(exc)[:500],
            "retryable": bool(getattr(exc, "retryable", True)),
        }
        if code == "PII_POLICY_VIOLATION":
            # The outbound privacy gate is a policy denial like any other: the model is
            # told what was denied and what it may still call, then decides.
            error = {
                "code": "POLICY_DENIED", "message": str(exc)[:500],
                "denied": {
                    "tool": call.name, "source": _source_for_call(call),
                    "policy": "outbound_privacy",
                },
                "authorized_tools": _authorized_tool_names(state),
            }
        return ExecutedAgentCall(call=call, error=error)


async def _stream_item(state: dict[str, Any], item: ExecutedAgentCall) -> None:
    from app.services.workbench.graph import sse

    if item.card is None and item.error is not None and item.error.get("code") != "POLICY_DENIED":
        source = _source_for_call(item.call)
        if source is not None:
            # The exact failure text goes back to the model; the user sees a stable
            # message plus the turn id so the incident can be found in the logs.
            code = item.error.get("code", "SOURCE_UNAVAILABLE")
            item.card = SourceResult(
                source=source, card_type="error",
                payload={
                    "message": _user_error_message(code, state["turn_id"]),
                    "code": code,
                    "retryable": bool(item.error.get("retryable", True)),
                },
            )
    if item.card is None:
        return
    source = item.card.source
    state["timing"]["source_completions"].append(source)
    await state["emit"].put(sse("source_card", {
        "source": source, "card_type": item.card.card_type, **item.card.payload,
    }))
    state["timing"].setdefault(
        "first_card_ms", int((time.perf_counter() - state["timing"]["started_at"]) * 1000),
    )
    # Not persisted here: the round's ``tool_result`` event already carries this card,
    # and `_persist_exchange` records the rendered view in the same write.


async def _execute_batch(state, context: AgentExecutionContext, calls) -> list[ExecutedAgentCall]:
    from app.services.workbench.graph import sse

    for call in calls:
        source = _source_for_call(call)
        if source is not None:
            state["timing"]["source_attempts"].append(source)
            await state["emit"].put(sse("source_start", {"source": source, "tool": call.name}))

    output: list[ExecutedAgentCall | None] = [None] * len(calls)
    from app.mcp import postgres_client

    parallel = [
        (i, call) for i, call in enumerate(calls)
        if not postgres_client.is_model_tool(call.name) and get_agent_tool(call.name).parallel_safe
    ]
    serial = [
        (i, call) for i, call in enumerate(calls)
        if postgres_client.is_model_tool(call.name) or not get_agent_tool(call.name).parallel_safe
    ]
    if parallel:
        async def indexed(index, call):
            return index, await _execute_one(state, context, call)

        tasks = [asyncio.create_task(indexed(index, call)) for index, call in parallel]
        try:
            for task in asyncio.as_completed(tasks):
                index, item = await task
                output[index] = item
                await _stream_item(state, item)
        finally:
            for task in tasks:
                if not task.done():
                    task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
    for index, call in serial:
        output[index] = await _execute_one(state, context, call)
        await _stream_item(state, output[index])
    return [item for item in output if item is not None]


async def _announce_route(state: dict[str, Any], calls) -> None:
    from app.services.workbench.graph import sse

    sources = list(dict.fromkeys(
        source for call in calls if (source := _source_for_call(call))
    ))
    decision = ExecutionDecision(
        sources=sources, intent=state["question"],
        policy_version=state["source_policy"].version,
        effective_sources=state["source_policy"].effective_sources,
    )
    state["decision"] = decision
    await state["emit"].put(sse("route", {
        "sources": sources, "intent": state["question"], "model": "native_agent",
        "reason": "native_tool_selection",
        "policy_version": decision.policy_version, "tools": [call.name for call in calls],
    }))
    history.set_route(
        state["conversation_id"], state["user"], state["turn_id"],
        sources=sources, intent=state["question"], model="native_agent",
        reason="native_tool_selection",
        effective_sources=decision.effective_sources,
        tools=[call.name for call in calls],
    )


async def _end_without_data(state: dict[str, Any], payload: dict[str, Any], *, origin: str) -> None:
    """Emit a clarification or refusal. ``origin`` says who decided: the model's
    ``finish_without_data`` call, or the application after a denial the model never
    resolved within budget."""
    from app.services.workbench.graph import sse

    outcome = payload.get("outcome")
    answer = {
        "status": "clarify" if outcome == "clarify" else "refused",
        "text": payload.get("message", ""),
        "sources": [], "citations": [], "unavailable_sources": [], "limitations": [],
        "suggestions": payload.get("suggestions", []),
        "reason": payload.get("reason_code"),
        "origin": origin,
    }
    await state["emit"].put(sse("refusal" if outcome == "refuse" else "answer", answer))
    history.set_answer(state["conversation_id"], state["user"], state["turn_id"], answer)


async def run(state: dict[str, Any]) -> None:
    """One bounded loop: request, observe, execute, repeat; then answer.

    Each iteration is one LLM request. The first round is ``auto`` so the agent can answer
    schema and conceptual questions from supplied context, while its system contract requires
    PostgreSQL MCP evidence for loan-book figures and records. The last evidence-backed round
    is ``none`` so a result executed on the previous tool round is still synthesized.
    """
    from app.services.workbench.graph import answer_results, sse

    emit = state["emit"]
    budget = _budget(state)
    catalog = state.setdefault("_agent_catalog", get_catalog())
    context = AgentExecutionContext(
        user=state["user"], role=state["role"],
        conversation_id=state["conversation_id"], turn_id=state["turn_id"],
        source_policy=state["source_policy"],
        deadline_s=max(0.001, budget.deadline - time.perf_counter()),
        question=state["question"],
        catalog=catalog, catalog_version=getattr(catalog, "version", ""),
        private_entities=tuple(state.get("agent_private_entities", ())),
    )
    await emit.put(sse("stage", {"stage": "routing", "agent": "native"}))

    exchange: list[dict[str, Any]] = []  # this turn's assistant and tool messages
    executed: list[ExecutedAgentCall] = []
    final = None
    denial: dict[str, Any] | None = None
    last_error = ""
    while budget.rounds_remaining and not budget.expired:
        if any(item.terminal is not None for item in executed):
            break
        has_data = any(item.card is not None and item.error is None for item in executed)
        if not has_data:
            if not budget.calls_remaining:
                break
            tool_choice = "auto"
        elif budget.rounds_remaining == 1 or not budget.calls_remaining:
            tool_choice = "none"
        else:
            tool_choice = "auto"
        budget.charge_round(_PURPOSES[tool_choice])
        try:
            result = await _select(
                state, repair_messages=exchange or None, tool_choice=tool_choice,
                supplement=last_error,
            )
        except (TimeoutError, LLMTimeout):
            if not has_data:
                raise
            break
        except LLMProtocolError as exc:
            if not budget.rounds_remaining:
                if has_data:
                    break
                raise
            last_error = str(exc)
            _queue_protocol_repair(state, exchange, exc, tool_choice)
            continue
        if not result.tool_calls:
            if tool_choice == "required":
                exc = LLMProtocolError(
                    "native selection returned no tool_calls; assistant content is not executable"
                )
                if not budget.rounds_remaining:
                    raise exc
                _persist_exchange(state, result, (), (), stage=_STAGES[tool_choice])
                _queue_protocol_repair(
                    state, exchange, exc, tool_choice,
                    assistant_message=result.assistant_message,
                )
                last_error = str(exc)
                continue
            if not result.text.strip():
                exc = LLMProtocolError(
                    "native continuation returned neither tool calls nor an answer"
                )
                if not budget.rounds_remaining:
                    break
                _persist_exchange(state, result, (), (), stage=_STAGES[tool_choice])
                _queue_protocol_repair(
                    state, exchange, exc, tool_choice,
                    assistant_message=result.assistant_message,
                )
                last_error = str(exc)
                continue
            final = result
            break
        if tool_choice == "none":
            exc = LLMProtocolError("tool call returned during final synthesis phase")
            if not budget.rounds_remaining:
                break
            _persist_exchange(state, result, (), (), stage=_STAGES[tool_choice])
            _queue_protocol_repair(
                state, exchange, exc, tool_choice,
                assistant_message=result.assistant_message,
            )
            last_error = str(exc)
            continue
        try:
            budget.charge_call(len(result.tool_calls))
        except BudgetExhausted:
            if not has_data:
                raise
            break
        if state.get("decision") is None:
            await _announce_route(state, result.tool_calls)
        failures = _preflight(result, state)
        failed_ids = {call_id for call_id, _message, _code in failures}
        items = await _execute_batch(
            state, context, [call for call in result.tool_calls if call.id not in failed_ids],
        )
        _persist_exchange(state, result, failures, items, stage=_STAGES[tool_choice])
        exchange.extend(_repair_messages(result, failures, executed=items, state=state))
        executed.extend(items)
        denial = _denial(failures, items) or denial
        last_error = _latest_error(failures, items)
    logger.info("native agent turn budget %s", budget.snapshot())

    terminal = next((item for item in executed if item.terminal is not None), None)
    if terminal is not None:
        await _end_without_data(state, terminal.terminal or {}, origin="model")
        return
    cards = [item.card for item in executed if item.card is not None]
    if final is not None:
        state["agent_final_result"] = final
        # The candidate as the model wrote it; `answer_results` records the final text.
        history.set_synthesis(
            state["conversation_id"], state["user"], state["turn_id"], final.text.strip(),
            message=final.assistant_message, stage="synthesize",
        )
    elif not cards:
        if budget.expired:
            raise TimeoutError("Workbench request deadline exhausted")
        if denial is not None:
            # The model never resolved the denial with a replacement call or a refusal
            # of its own; the application ends the turn and says so.
            await _end_without_data(state, {
                "outcome": "refuse",
                "message": (
                    _PII_REFUSAL_TEXT if denial["policy"] == "outbound_privacy"
                    else _SOURCE_REFUSAL_TEXT
                ),
                "suggestions": [], "reason_code": "POLICY_DENIED",
            }, origin="application")
            return
        raise BudgetExhausted("native agent spent its budget without a usable result")
    elif any(card.card_type != "error" for card in cards):
        state["decision"].limitations.append(dict(_BUDGET_LIMITATION))
    state["results"] = cards
    await answer_results(state)


__all__ = [
    "BudgetExhausted",
    "TurnBudget",
    "run",
    "select_calls",
]
