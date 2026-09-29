from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, replace
from functools import lru_cache
from typing import Any, Literal, TypedDict, cast

from langgraph.graph import END, START, StateGraph
from langgraph.runtime import Runtime

from app.core.config import settings
from app.services.nlq.llm import LLMProtocolError, LLMTimeout
from app.services.nlq.llm.client import LLMResult
from app.services.workbench import agent, history
from app.services.workbench.agent_contracts import FinalSynthesis
from app.services.workbench.agent_executor import (
    AgentExecutionContext,
    ExecutedAgentCall,
)


class WorkflowState(TypedDict):
    exchange: list[dict[str, Any]]
    executed: list[ExecutedAgentCall]
    result: LLMResult | None
    final: LLMResult | None
    denial: dict[str, Any] | None
    last_error: str
    finalizing: bool
    final_attempts: int
    stopped: bool


@dataclass
class TurnContext:
    state: dict[str, Any]
    budget: agent.TurnBudget
    execution: AgentExecutionContext


def _has_data(flow: WorkflowState) -> bool:
    return any(
        item.error is None
        and (item.card is not None or item.raw_result is not None)
        for item in flow["executed"]
    )


async def _next_node(
    flow: WorkflowState, runtime: Runtime[TurnContext]
) -> Literal["model", "finalize", "render"]:
    context = runtime.context
    if any(item.terminal is not None for item in flow["executed"]):
        return "render"
    if flow["stopped"] or flow["final"] is not None:
        return "render"
    if context.budget.expired or not context.budget.rounds_remaining:
        return "render"
    if not context.budget.calls_remaining:
        return "render"
    if flow["finalizing"] or (
        context.state.get("query_registry")
        and (
            context.budget.rounds_remaining == 1
            or context.budget.calls_remaining == 1
        )
    ):
        if (
            flow["final_attempts"]
            >= 1 + settings.workbench_agent_synthesis_repairs
        ):
            return "render"
        return "finalize"
    return "model"


async def _request(
    flow: WorkflowState, runtime: Runtime[TurnContext], *, finalizing: bool
) -> dict[str, Any]:
    context = runtime.context
    state, budget = context.state, context.budget
    choice = "final" if finalizing else "auto"
    budget.charge_round(agent._PURPOSES[choice])
    trace_id = f"model-{budget.rounds_used}"
    started = time.perf_counter()
    label = (
        "Model preparing answer"
        if finalizing
        else "Model deciding next action"
    )
    await agent._emit_trace(
        state,
        {
            "id": trace_id,
            "kind": "model",
            "status": "running",
            "label": label,
            **(
                {"prompt_progress_percent": 0}
                if settings.llm_prompt_progress_enabled
                else {}
            ),
        },
    )
    update: dict[str, Any] = {
        "result": None,
        "finalizing": finalizing,
        "final_attempts": flow["final_attempts"] + int(finalizing),
    }
    try:
        result = await agent._select(
            state,
            repair_messages=flow["exchange"] or None,
            tool_choice=choice,
            supplement=flow["last_error"],
            trace_id=trace_id,
        )
    except asyncio.CancelledError:
        await agent.finalize_running_traces(state)
        raise
    except (LLMProtocolError, TimeoutError, LLMTimeout) as exc:
        await agent._emit_trace(
            state,
            {
                "id": trace_id,
                "kind": "model",
                "status": "error",
                "label": label,
                "detail": str(exc)[:500],
                "duration_ms": int((time.perf_counter() - started) * 1000),
            },
        )
        if isinstance(exc, (TimeoutError, LLMTimeout)):
            if not _has_data(flow):
                raise
            return {**update, "stopped": True, "last_error": str(exc)}
        exchange = list(flow["exchange"])
        agent._queue_protocol_repair(state, exchange, exc, choice)
        return {**update, "exchange": exchange, "last_error": str(exc)}
    except Exception as exc:
        await agent._emit_trace(
            state,
            {
                "id": trace_id,
                "kind": "model",
                "status": "error",
                "label": label,
                "detail": str(exc)[:500],
                "duration_ms": int((time.perf_counter() - started) * 1000),
            },
        )
        raise
    trace: dict[str, Any] = {
        "id": trace_id,
        "kind": "model",
        "status": "complete",
        "label": label,
        "detail": f"Selected {len(result.tool_calls)} tool call(s)"
        if result.tool_calls
        else "Prepared the response",
        "duration_ms": int((time.perf_counter() - started) * 1000),
    }
    if result.reasoning:
        trace["reasoning"] = result.reasoning
    if result.tool_calls:
        trace["tool_calls"] = [
            {"index": index, "id": call.id, "name": call.name}
            for index, call in enumerate(result.tool_calls)
        ]
    await agent._emit_trace(state, trace)
    if result.tool_calls:
        return {**update, "result": result}
    if (
        result.text.strip()
        and not state.get("query_registry")
        and not finalizing
    ):
        return {**update, "final": result}
    agent._persist_exchange(state, result, (), (), stage=agent._STAGES[choice])
    exchange = list(flow["exchange"])
    message = result.assistant_message or {
        "role": "assistant",
        "content": result.text,
    }
    exchange.append(message)
    error = (
        "A query-backed turn requires submit_final_answer."
        if state.get("query_registry") or finalizing
        else "Model returned neither an answer nor tool calls."
    )
    return {
        **update,
        "exchange": exchange,
        "last_error": error,
        "finalizing": finalizing or bool(state.get("query_registry")),
    }


async def call_model(
    state: WorkflowState, runtime: Runtime[TurnContext]
) -> dict[str, Any]:
    return await _request(state, runtime, finalizing=False)


async def prepare_final(
    state: WorkflowState, runtime: Runtime[TurnContext]
) -> dict[str, Any]:
    return await _request(state, runtime, finalizing=True)


async def _after_model(flow: WorkflowState) -> Literal["tools", "route"]:
    return "tools" if flow["result"] is not None else "route"


async def execute_tools(
    state: WorkflowState, runtime: Runtime[TurnContext]
) -> dict[str, Any]:
    context = runtime.context
    turn, budget = context.state, context.budget
    result = state["result"]
    assert result is not None
    budget.charge_call(len(result.tool_calls))
    if turn.get("decision") is None:
        await agent._announce_route(turn, result.tool_calls)
    failures = agent._preflight(result, turn)
    if state["finalizing"]:
        failures.extend(
            (
                call.id,
                "Only submit_final_answer is allowed during finalization.",
                "INVALID_TOOL_ARGUMENTS",
            )
            for call in result.tool_calls
            if call.name != "submit_final_answer"
            and not any(item[0] == call.id for item in failures)
        )
    failed_ids = {item[0] for item in failures}
    calls = {call.id: call for call in result.tool_calls}
    for call_id, message, code in failures:
        call = calls[call_id]
        await agent._emit_trace(
            turn,
            {
                "id": f"tool-{call_id}",
                "kind": "tool",
                "status": "error",
                "label": call.name,
                "call_id": call_id,
                "detail": f"{code}: {message}"[:500],
                "arguments": agent._trace_arguments(call),
                "duration_ms": 0,
            },
        )
    items = await agent._execute_batch(
        turn,
        replace(
            context.execution,
            deadline_s=max(
                0.001,
                budget.remaining_s(settings.nlq_request_budget_s)
                * (1.0 if state["finalizing"] else 0.75),
            ),
        ),
        [call for call in result.tool_calls if call.id not in failed_ids],
    )
    if any(item.terminal is not None for item in items):
        _persist_model_context(turn)
    choice = "final" if state["finalizing"] else "auto"
    agent._persist_exchange(
        turn, result, failures, items, stage=agent._STAGES[choice]
    )
    rejected_final = any(
        call.name == "submit_final_answer"
        and (
            call.id in failed_ids
            or any(item.call.id == call.id and item.error for item in items)
        )
        for call in result.tool_calls
    )
    if rejected_final:
        turn["attribution_repairs"] = turn.get("attribution_repairs", 0) + 1
    return {
        "exchange": [
            *state["exchange"],
            *agent._repair_messages(
                result, failures, executed=items, state=turn
            ),
        ],
        "executed": [*state["executed"], *items],
        "denial": agent._denial(failures, items) or state["denial"],
        "last_error": agent._latest_error(failures, items),
        "result": None,
        "finalizing": state["finalizing"] or rejected_final,
        "final_attempts": state["final_attempts"]
        + int(rejected_final and not state["finalizing"]),
    }


async def render_outcome(
    state: WorkflowState, runtime: Runtime[TurnContext]
) -> dict[str, Any]:
    from app.services.workbench.graph import WorkbenchState, answer_results

    context = runtime.context
    turn = context.state
    terminal = next(
        (item for item in state["executed"] if item.terminal is not None), None
    )
    turn["results"] = [
        item.card for item in state["executed"] if item.card is not None
    ]
    if terminal is not None:
        payload = terminal.terminal or {}
        if payload.get("outcome") == "answer":
            turn["agent_final_synthesis"] = FinalSynthesis.model_validate(
                payload.get("synthesis")
            )
            await answer_results(cast(WorkbenchState, turn))
        else:
            await agent._end_without_data(turn, payload, origin="model")
        return {"stopped": True}
    if state["denial"] is not None and not _has_data(state):
        await agent._end_without_data(
            turn,
            {
                "outcome": "refuse",
                "message": agent._PII_REFUSAL_TEXT
                if state["denial"]["policy"] == "outbound_privacy"
                else agent._SOURCE_REFUSAL_TEXT,
                "suggestions": [],
                "reason_code": "POLICY_DENIED",
            },
            origin="application",
        )
        return {"stopped": True}
    if turn.get("query_registry"):
        raise LLMProtocolError(
            "Final submission was not valid before the turn budget ended."
        )
    final = state["final"]
    if final is not None:
        _persist_model_context(turn)
        turn["agent_final_result"] = final
        history.set_synthesis(
            turn["conversation_id"],
            turn["user"],
            turn["turn_id"],
            final.text,
            message=final.assistant_message,
            stage="synthesize",
        )
    elif not turn["results"]:
        if context.budget.expired:
            raise TimeoutError("Workbench request deadline exhausted")
        raise agent.BudgetExhausted(
            "native agent spent its budget without a usable result"
        )
    elif turn.get("decision") is not None:
        turn["decision"].limitations.append(dict(agent._BUDGET_LIMITATION))
    await answer_results(cast(WorkbenchState, turn))
    return {"stopped": True}


async def route(state: WorkflowState) -> dict[str, Any]:
    return {}


def _persist_model_context(state: dict[str, Any]) -> None:
    messages = state.get("_last_model_messages")
    if messages:
        history.set_model_request_context(
            state["conversation_id"],
            state["user"],
            state["turn_id"],
            messages[1:],
        )


@lru_cache(maxsize=1)
def get_workflow():
    builder = StateGraph(cast(Any, WorkflowState), context_schema=TurnContext)
    builder.add_node("route", route)
    builder.add_node("model", call_model)
    builder.add_node("finalize", prepare_final)
    builder.add_node("tools", execute_tools)
    builder.add_node("render", render_outcome)
    builder.add_edge(START, "route")
    builder.add_conditional_edges("route", _next_node)
    builder.add_conditional_edges("model", _after_model)
    builder.add_conditional_edges("finalize", _after_model)
    builder.add_edge("tools", "route")
    builder.add_edge("render", END)
    return builder.compile()


async def run_workflow(state: dict[str, Any]) -> None:
    from app.services.nlq.catalog import get_catalog
    from app.services.workbench.graph import sse

    budget = agent._budget(state)
    catalog = state.setdefault("_agent_catalog", get_catalog())
    execution = AgentExecutionContext(
        user=state["user"],
        role=state["role"],
        conversation_id=state["conversation_id"],
        turn_id=state["turn_id"],
        source_policy=state["source_policy"],
        deadline_s=max(0.001, budget.deadline - time.perf_counter()),
        question=state["question"],
        catalog=catalog,
        catalog_version=catalog.version,
        private_entities=tuple(state.get("agent_private_entities", ())),
    )
    await state["emit"].put(
        sse("stage", {"stage": "routing", "agent": "native"})
    )
    async with asyncio.timeout(
        budget.remaining_s(settings.nlq_request_budget_s)
    ):
        await get_workflow().ainvoke(
            WorkflowState(
                exchange=[],
                executed=[],
                result=None,
                final=None,
                denial=None,
                last_error="",
                finalizing=False,
                final_attempts=0,
                stopped=False,
            ),
            config={"recursion_limit": 4 * budget.max_rounds + 4},
            context=TurnContext(state, budget, execution),
        )
