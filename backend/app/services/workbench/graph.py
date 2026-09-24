"""Stable streaming entry point for the native-tool Workbench."""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import time
import uuid
from typing import Any, AsyncIterator, NotRequired, TypedDict

import anyio

from app.core.config import settings
from app.services.nlq.llm.telemetry import collect_calls, summarize_calls
from app.services.workbench import access, compaction, history
from app.services.workbench.results import ExecutionDecision, SourceResult

logger = logging.getLogger(__name__)
_active_turn_tasks: dict[tuple[str, str, str], asyncio.Task[None]] = {}


def cancel_active_turn(conversation_id: str, user: str, turn_id: str) -> bool:
    """Cancel an active turn owned by this user, independently of stream disconnect."""
    task = _active_turn_tasks.get((conversation_id, user, turn_id))
    if task is None or task.done():
        return False
    # Stop and HTTP disconnect can both arrive for the same turn. Cancelling again
    # interrupts the first cancellation's awaited upstream connection cleanup.
    if not task.cancelling():
        task.cancel()
    return True


def _persist(operation, *args, **kwargs) -> None:
    """History is durable best-effort; storage failure must not erase an answer."""
    try:
        operation(*args, **kwargs)
    except Exception:  # noqa: BLE001
        logger.warning("workbench history operation failed", exc_info=True)


def sse(event: str, data: Any) -> str:
    return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"


def _log_query_attribution(
    state: dict[str, Any], *, active: list[str], visual: list[str],
    invalid: list[str], proposed: list[str], fallback_used: bool,
) -> None:
    """Emit counts only; query rows and model prose never enter attribution telemetry."""
    registry = list(state.get("query_registry", []))
    successful = sum(
        1 for record in registry
        if record.get("status") == "success" and record.get("has_data") is True
    )
    by_id = {
        str(record.get("query_id")): record
        for record in registry if record.get("query_id")
    }
    filtered_execution_references = sum(
        1 for query_id in dict.fromkeys(proposed)
        if query_id in by_id and not (
            by_id[query_id].get("status") == "success"
            and by_id[query_id].get("has_data") is True
        )
    )
    active_set = set(active)
    unused_records = [
        record for record in registry
        if record.get("status") == "success" and record.get("has_data") is True
        and record.get("query_id") not in active_set
    ]
    unused_by_purpose: dict[str, int] = {}
    unused_by_tool: dict[str, int] = {}
    for record in unused_records:
        purpose = str(record.get("purpose") or "answer")
        tool = str(record.get("tool_name") or "unknown")
        unused_by_purpose[purpose] = unused_by_purpose.get(purpose, 0) + 1
        unused_by_tool[tool] = unused_by_tool.get(tool, 0) + 1
    from app.core.logging import log_app_event

    log_app_event(
        "Workbench query attribution reconciled",
        event="workbench_query_attribution",
        data={
            "turn_id": state.get("turn_id"),
            "attempted_queries": len(registry),
            "successful_queries": successful,
            "active_queries": len(active),
            "visual_queries": len(visual),
            "unused_successful_queries": max(0, successful - len(active)),
            "unused_by_purpose": unused_by_purpose,
            "unused_by_tool": unused_by_tool,
            "invalid_model_references": len(invalid),
            "filtered_execution_references": filtered_execution_references,
            "structured_output_repairs": int(state.get("attribution_repairs", 0)),
            "fallback_used": fallback_used,
            "data_bearing_answer_empty_attribution": successful > 0 and not active,
            "executed_to_active_ratio": (
                round(len(registry) / len(active), 3) if active else None
            ),
        },
    )


CONTEXT_CAPACITY_CODE = "CONTEXT_CAPACITY"
CONTEXT_FULL_MESSAGE = (
    "This conversation has grown too long for the model's context window, so earlier "
    "detail has been dropped. Please start a new chat session to continue with full "
    "accuracy."
)

# The transcript budget reserves headroom for the system prompt, catalog grammar and the
# question, but that reserve is an estimate — a large grammar can still push a request
# past the window. Providers report it as a 4xx whose body names the context limit, so
# the runtime case is matched here as well as the pre-emptive one.
_CONTEXT_ERROR_MARKERS = (
    "context window", "context length", "context size", "n_ctx",
    "too many tokens", "exceeds the available", "maximum context",
)


def _is_context_overflow(exc: BaseException) -> bool:
    text = str(exc).lower()
    return any(marker in text for marker in _CONTEXT_ERROR_MARKERS)


def _native_error(exc: BaseException) -> tuple[str, str, bool]:
    """Map every native-loop escape to one stable, user-facing error contract."""
    from app.services.nlq.llm import (
        LLMError,
        LLMIncomplete,
        LLMProtocolError,
        LLMResponseBlocked,
        LLMTimeout,
        LLMUnavailable,
    )
    from app.services.workbench.agent import BudgetExhausted
    from app.services.workbench.agent_tools import AgentToolAccessDenied

    if _is_context_overflow(exc):
        return CONTEXT_CAPACITY_CODE, CONTEXT_FULL_MESSAGE, False
    if isinstance(exc, BudgetExhausted):
        return (
            "AGENT_BUDGET_EXHAUSTED",
            "The agent reached its turn limit before it could produce an answer.",
            False,
        )
    if isinstance(exc, (TimeoutError, LLMTimeout)):
        return "AGENT_TIMEOUT", "The agent took too long to answer.", True
    if isinstance(exc, LLMUnavailable):
        return "MODEL_UNAVAILABLE", "The language model is unavailable right now.", True
    if isinstance(exc, LLMIncomplete):
        return "MODEL_INCOMPLETE", "The language model response was cut short.", True
    if isinstance(exc, LLMResponseBlocked):
        return "MODEL_RESPONSE_BLOCKED", "The language model could not provide a response.", False
    if isinstance(exc, AgentToolAccessDenied):
        return "POLICY_DENIED", "That capability is not authorized for this request.", False
    if isinstance(exc, LLMProtocolError):
        return (
            "MODEL_PROTOCOL_ERROR",
            "The language model did not return a valid native tool response.",
            True,
        )
    if isinstance(exc, LLMError):
        return "MODEL_ERROR", "The language model could not complete this request.", True
    return "WORKBENCH_INTERNAL", "The workbench hit an internal error.", True


class WorkbenchState(TypedDict):
    question: str
    conversation_id: str
    user: str
    role: str
    turn_id: str
    agent_history_messages: NotRequired[list[dict[str, Any]]]
    _restore_system_slot: NotRequired[bool]
    agent_private_entities: NotRequired[tuple[str, ...]]
    emit: "asyncio.Queue[str | None]"
    pinned: NotRequired[str | None]
    source_policy: access.SourceAccessPolicy
    decision: NotRequired[ExecutionDecision]
    results: NotRequired[list[SourceResult]]
    timing: dict[str, Any]
    trace: NotRequired[list[dict[str, Any]]]
    agent_synthesis_messages: NotRequired[list[dict[str, Any]]]
    agent_final_synthesis: NotRequired[Any]
    attribution_repairs: NotRequired[int]
    query_registry: NotRequired[list[dict[str, Any]]]


_ANSWERABLE_CARD_TYPES = frozenset(
    {"chart", "analysis", "worklist", "briefing", "brief", "schema"}
)


async def answer_results(state: WorkbenchState) -> dict[str, Any]:
    emit = state["emit"]
    decision = state.get("decision")
    all_results = state.get("results", [])
    results = [
        r for r in all_results
        if r.card_type in _ANSWERABLE_CARD_TYPES and r.summary.strip()
    ]
    unavailable = [
        {
            "source": r.source,
            "type": r.card_type,
            "reason": str(
                r.payload.get("message") or r.payload.get("question") or "No usable result."
            ),
        }
        for r in all_results
        if r not in results
    ]
    limitations = list(decision.limitations if decision is not None else []) + [
        {
            "source": r.source,
            "reason": r.limitation or "The source only supported part of the request.",
        }
        for r in results
        if not r.complete
    ]

    final_result = state.get("agent_final_result")
    if (
        not results
        and final_result is not None
        and final_result.text.strip()
        and not state.get("query_registry")
    ):
        payload = {
            "schema_version": 1,
            "status": "answered",
            "text": final_result.text.strip(),
            "active_query_ids": [], "visual_query_ids": [], "excluded_queries": [],
            "model_active_query_ids": [], "invalid_query_ids": [],
            "attribution_fallback_used": False,
            "sources": [], "citations": [], "unavailable_sources": [],
            "limitations": [], "facts": [],
        }
        await emit.put(sse("answer", payload))
        state["timing"].setdefault(
            "final_answer_ms", int((time.perf_counter() - state["timing"]["started_at"]) * 1000)
        )
        _persist(
            history.set_answer,
            state["conversation_id"], state["user"], state["turn_id"], payload,
        )
        _log_query_attribution(
            state, active=[], visual=[], invalid=[], proposed=[], fallback_used=False,
        )
        return {}

    if not results:
        refusal = next((r for r in all_results if r.card_type == "refusal"), None)
        clarification = next((r for r in all_results if r.card_type == "clarify"), None)
        if clarification is not None:
            payload = {
                "schema_version": 1,
                "status": "clarify",
                "text": str(clarification.payload.get("question") or "Please clarify the request."),
                "sources": [], "citations": [], "unavailable_sources": unavailable,
                "limitations": [],
                "active_query_ids": [], "visual_query_ids": [], "excluded_queries": [],
            }
            await emit.put(sse("answer", payload))
            state["timing"].setdefault(
                "final_answer_ms", int((time.perf_counter() - state["timing"]["started_at"]) * 1000)
            )
            _persist(history.set_answer, state["conversation_id"], state["user"], state["turn_id"], payload)
        elif refusal is not None:
            payload = {
                "schema_version": 1,
                "status": "refused",
                "text": str(refusal.payload.get("message") or "That request cannot be answered safely."),
                "sources": [], "citations": [], "unavailable_sources": unavailable,
                "limitations": [],
                "active_query_ids": [], "visual_query_ids": [], "excluded_queries": [],
            }
            await emit.put(sse("answer", payload))
            state["timing"].setdefault(
                "final_answer_ms", int((time.perf_counter() - state["timing"]["started_at"]) * 1000)
            )
            _persist(history.set_answer, state["conversation_id"], state["user"], state["turn_id"], payload)
        else:
            first_error = next((r for r in all_results if r.card_type == "error"), None)
            if first_error is not None:
                # The source card already streamed the actionable failure. Do not add a
                # second generic Workbench error underneath it.
                message = str(first_error.payload.get("message") or "Source unavailable.")
                _persist(history.set_error,
                    state["conversation_id"], state["user"], state["turn_id"], message,
                    code=str(first_error.payload.get("code") or "SOURCE_UNAVAILABLE"),
                    retryable=bool(first_error.payload.get("retryable")),
                )
                return {}
            message = "No intelligence source produced a usable answer."
            _persist(
                history.set_error,
                state["conversation_id"], state["user"], state["turn_id"], message,
                code="NO_USABLE_RESULT", retryable=True,
            )
            await emit.put(sse("error", {
                "code": "NO_USABLE_RESULT", "message": message, "retryable": True,
            }))
        return {}

    text = results[0].summary.strip()
    result = final_result
    structured_synthesis = state.get("agent_final_synthesis")
    if result is not None and result.text:
        # Preserve the model's content verbatim. Tool calls and tool results remain
        # separate messages, and the agent loop alone decides whether to continue.
        text = result.text
        try:
            from app.services.workbench.agent_contracts import FinalSynthesis

            structured_synthesis = FinalSynthesis.model_validate(result.json())
            text = structured_synthesis.insights or text
        except Exception:  # noqa: BLE001 - invalid output fails closed below
            structured_synthesis = None

    from app.services.workbench.attribution import (
        ReconciledAttribution,
        reconcile_query_attribution,
    )

    registry = list(state.get("query_registry", []))
    attribution = (
        reconcile_query_attribution(registry, structured_synthesis)
        if structured_synthesis is not None else ReconciledAttribution()
    )
    if structured_synthesis is not None:
        text = structured_synthesis.insights.strip()
    proposed = (
        [f"q{structured_synthesis.query_id}"]
        if structured_synthesis is not None else []
    )
    _persist(
        history.set_query_registry,
        state["conversation_id"], state["user"], state["turn_id"], registry,
    )
    _log_query_attribution(
        state,
        active=attribution.active_query_ids,
        visual=attribution.visual_query_ids,
        invalid=attribution.invalid_query_ids,
        proposed=proposed,
        fallback_used=attribution.fallback_used,
    )

    citations: list[dict[str, Any]] = []
    seen_citations: set[tuple[str, str]] = set()
    for item in results:
        for citation in item.sources:
            key = (
                str(citation.get("url") or citation.get("document", "")),
                str(citation.get("page", "")),
            )
            if key not in seen_citations:
                seen_citations.add(key)
                citations.append(citation)
    payload = {
        "schema_version": 1,
        "status": "partial" if unavailable or limitations else "answered",
        "text": text,
        "insights": text,
        "query_id": (
            structured_synthesis.query_id if structured_synthesis is not None else None
        ),
        "view": (
            structured_synthesis.view if structured_synthesis is not None else None
        ),
        "active_query_ids": attribution.active_query_ids,
        "visual_query_ids": attribution.visual_query_ids,
        "excluded_queries": [
            item.model_dump(mode="json") for item in attribution.excluded_queries
        ],
        "model_active_query_ids": proposed,
        "invalid_query_ids": attribution.invalid_query_ids,
        "attribution_fallback_used": attribution.fallback_used,
        "sources": list(dict.fromkeys(r.source for r in results)),
        "citations": citations,
        "unavailable_sources": unavailable,
        "limitations": limitations,
        "facts": [],
    }
    await emit.put(sse("answer", payload))
    state["timing"].setdefault(
        "final_answer_ms", int((time.perf_counter() - state["timing"]["started_at"]) * 1000)
    )
    _persist(history.set_answer, state["conversation_id"], state["user"], state["turn_id"], payload)
    if result is not None:
        # The prompt this call carried is the best available measure of how full the
        # conversation's context has become; the transcript budget is built on it.
        _persist(history.set_usage,
            state["conversation_id"], state["user"], state["turn_id"],
            prompt_tokens=getattr(result, "prompt_tokens", 0),
            completion_tokens=getattr(result, "completion_tokens", 0),
        )
    return {}


# asyncio keeps only a weak reference to a running task, so a fire-and-forget coroutine
# can be garbage collected mid-flight. Holding a strong reference until it finishes is the
# documented way to detach work safely.
_background: set[asyncio.Task] = set()


def _spawn_background(coro) -> None:
    task = asyncio.create_task(coro)
    _background.add(task)
    task.add_done_callback(_background.discard)


async def run_workbench(
    *, question: str, conversation_id: str, user: str, role: str, pinned: str | None = None,
    external_sources_enabled: bool = False,
) -> AsyncIterator[str]:
    """Run one turn, yielding SSE frames as the graph produces them."""
    started_at = time.perf_counter()
    emit: "asyncio.Queue[str | None]" = asyncio.Queue()
    source_policy = access.build_policy(
        role=role, external_sources_enabled=external_sources_enabled,
        pinned_source=pinned,
    )
    is_new_chat = False
    try:
        is_new_chat = history.get(conversation_id, user=user) is None
        turn_id = history.begin_turn(
            conversation_id, user, question, pinned=pinned,
            source_policy=source_policy.snapshot(),
        )
    except Exception:  # noqa: BLE001
        logger.warning("workbench turn persistence unavailable", exc_info=True)
        turn_id = uuid.uuid4().hex[:12]
    from app.core.logging import log_app_event, set_trace_context

    set_trace_context(
        turn_id=turn_id,
        conversation_id=conversation_id,
        username=user,
        role=role,
    )
    log_app_event(
        "Workbench turn started",
        event="workbench_turn_started",
        stage="understanding",
        data={
            "conversation_id": conversation_id,
            "pinned": pinned,
            "source_policy": source_policy.snapshot(),
            "question_chars": len(question),
        },
    )

    # Announce the conversation id first so the client can thread follow-ups and the History
    # rail onto it.
    first_event_ms = int((time.perf_counter() - started_at) * 1000)
    try:
        yield sse("conversation", {
            "conversation_id": conversation_id, "turn_id": turn_id,
        })
        # The native transcript is loaded only after the turn exists and the client has
        # the conversation id, so a transcript that cannot fit becomes a recorded,
        # user-visible error rather than a dropped stream.
        try:
            agent_history_messages = history.build_native_transcript(
                conversation_id, user=user,
            )
            agent_private_entities = history.private_entities(conversation_id, user=user)
        except history.NativeTranscriptOverflow as exc:
            logger.warning(
                "workbench native transcript overflow: conversation=%s turn=%s: %s",
                conversation_id, turn_id, exc,
            )
            log_app_event(
                "Workbench turn refused: native transcript exceeds the context window",
                event="workbench_turn_completed",
                outcome="error",
                error=str(exc),
                data={"code": CONTEXT_CAPACITY_CODE, "reason": exc.reason},
            )
            _persist(
                history.set_error, conversation_id, user, turn_id, CONTEXT_FULL_MESSAGE,
                code=CONTEXT_CAPACITY_CODE, retryable=False, reason=exc.reason,
            )
            _persist(history.complete_turn, conversation_id, user, turn_id, partial=True)
            # `reason` says whether compaction could have helped
            # (conversation_exceeds_budget) or the newest turn alone is too large
            # (single_turn_exceeds_budget); the message to the user is the same.
            yield sse("error", {
                "message": CONTEXT_FULL_MESSAGE, "retryable": False,
                "code": CONTEXT_CAPACITY_CODE, "reason": exc.reason,
            })
            yield sse("done", {})
            return
        except Exception as exc:  # noqa: BLE001
            # Anything but overflow means the durable record could not be read. Handing
            # the agent the 20-row prose transcript instead would answer from a
            # different history than the one the user can see, so the turn fails
            # visibly and retryably.
            logger.exception(
                "workbench native transcript load failed: conversation=%s turn=%s",
                conversation_id, turn_id,
            )
            message = (
                "The conversation history could not be loaded, so this question was "
                "not answered. Please try again; if it keeps failing, start a new chat."
            )
            log_app_event(
                "Workbench turn failed: conversation history could not be loaded",
                event="workbench_turn_completed",
                outcome="error",
                error=str(exc),
                data={"code": "HISTORY_UNAVAILABLE"},
            )
            _persist(
                history.set_error, conversation_id, user, turn_id, message,
                code="HISTORY_UNAVAILABLE", retryable=True,
            )
            _persist(history.complete_turn, conversation_id, user, turn_id, partial=True)
            yield sse("error", {
                "message": message, "retryable": True, "code": "HISTORY_UNAVAILABLE",
            })
            yield sse("done", {})
            return
        yield sse("stage", {"stage": "understanding"})
    except (GeneratorExit, asyncio.CancelledError):
        _persist(history.complete_turn, conversation_id, user, turn_id, partial=True)
        raise

    state: WorkbenchState = {
        "question": question, "conversation_id": conversation_id,
        "user": user, "role": role, "turn_id": turn_id,
        "agent_history_messages": agent_history_messages,
        "_slot_new_chat": is_new_chat,
        "agent_private_entities": agent_private_entities,
        "emit": emit, "pinned": pinned,
        "source_policy": source_policy,
        "timing": {
            "started_at": started_at,
            "first_event_ms": first_event_ms,
            "source_attempts": [],
            "source_completions": [],
        },
        "trace": [],
        "query_registry": [],
    }

    async def drive() -> None:
        partial = False
        call_records = []
        try:
            with collect_calls() as call_records:
                from app.services.workbench import agent

                await agent.run(state)
            log_app_event(
                "Workbench turn completed successfully",
                event="workbench_turn_completed",
                outcome="success",
            )
        except asyncio.CancelledError:
            partial = True
            logger.info(
                "Workbench stream task cancelled: conversation=%s turn=%s",
                conversation_id, turn_id,
            )
            await agent.finalize_running_queries(state)
            await agent.finalize_running_traces(state)
            raise
        except Exception as exc:  # noqa: BLE001 - surface as an error frame, never a 500
            partial = True
            code, message, retryable = _native_error(exc)
            if code == CONTEXT_CAPACITY_CODE:
                logger.warning("workbench context overflow: conversation=%s", conversation_id)
            else:
                logger.exception("workbench graph failed")
            log_app_event(
                f"Workbench turn failed: {message}",
                event="workbench_turn_completed",
                outcome="error",
                error=str(exc), data={"code": code},
            )
            _persist(
                history.set_error, conversation_id, user, turn_id, message,
                code=code, retryable=retryable,
            )
            await emit.put(sse("error", {
                "code": code, "message": message, "retryable": retryable,
            }))
        finally:
            if call_records:
                _persist(history.set_usage,
                    conversation_id, user, turn_id,
                    **summarize_calls(call_records),
                )
            _persist(history.set_timing,
                conversation_id, user, turn_id,
                first_event_ms=state["timing"].get("first_event_ms", 0),
                first_card_ms=state["timing"].get("first_card_ms", 0),
                final_answer_ms=state["timing"].get("final_answer_ms", 0),
                total_ms=int((time.perf_counter() - started_at) * 1000),
                source_attempts=state["timing"].get("source_attempts", []),
                source_completions=state["timing"].get("source_completions", []),
            )
            _persist(
                history.set_execution_trace,
                conversation_id, user, turn_id,
                trace=state.get("trace", []),
            )
            _persist(history.complete_turn, conversation_id, user, turn_id, partial=partial)
            # Checkpoint after the turn, never before it: the summarization call would
            # otherwise sit between the user's question and their first streamed token.
            # Detached and failure-tolerant — the transcript works without it.
            if not partial and settings.workbench_compaction_enabled:
                _spawn_background(compaction.maybe_compact(conversation_id, user))
            await emit.put(None)  # sentinel: the graph is done producing frames

    task = asyncio.create_task(drive())
    active_key = (conversation_id, user, turn_id)
    _active_turn_tasks[active_key] = task
    try:
        while True:
            frame = await emit.get()
            if frame is None:
                break
            yield frame
    finally:
        try:
            # StreamingResponse runs in an AnyIO cancel scope. A disconnect keeps
            # cancelling every await in that scope, which would propagate through
            # `await task` and interrupt the LLM socket close inside drive().
            with anyio.CancelScope(shield=True):
                if not task.done() and not task.cancelling():
                    task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task
        finally:
            if _active_turn_tasks.get(active_key) is task:
                _active_turn_tasks.pop(active_key, None)
    yield sse("done", {"total_ms": int((time.perf_counter() - started_at) * 1000)})
