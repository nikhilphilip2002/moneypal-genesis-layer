"""Stable streaming entry point for the native-tool Workbench."""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import time
import uuid
from typing import Any, AsyncIterator, NotRequired, TypedDict

from app.core.config import settings
from app.services.nlq.llm.telemetry import collect_calls, summarize_calls
from app.services.workbench import access, compaction, history
from app.services.workbench.results import ExecutionDecision, SourceResult

logger = logging.getLogger(__name__)


def _persist(operation, *args, **kwargs) -> None:
    """History is durable best-effort; storage failure must not erase an answer."""
    try:
        operation(*args, **kwargs)
    except Exception:  # noqa: BLE001
        logger.warning("workbench history operation failed", exc_info=True)


def sse(event: str, data: Any) -> str:
    return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"


CONTEXT_CAPACITY_CODE = "CONTEXT_CAPACITY"
CONTEXT_FULL_MESSAGE = (
    "This conversation has grown too long for the model's context window, so earlier "
    "detail has been dropped. Please start a new chat session to continue with full "
    "accuracy."
)


def _parse_end_call(json_text: str) -> dict[str, Any] | None:
    """Recover a sloppy model's ``finish_without_data`` call written as prose JSON.

    Small models occasionally serialize the tool call instead of emitting it as a
    structured tool use. Accept that shape so a refusal/clarification still lands in
    the right SSE frame rather than being printed verbatim as the answer.
    """
    stripped = json_text.strip()
    if not (stripped.startswith("{") and stripped.endswith("}")):
        return None
    try:
        data = json.loads(stripped)
    except (ValueError, TypeError):
        return None
    if not isinstance(data, dict) or data.get("name") != "finish_without_data":
        return None
    arguments = data.get("arguments")
    return arguments if isinstance(arguments, dict) else None

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

    if not results:
        refusal = next((r for r in all_results if r.card_type == "refusal"), None)
        clarification = next((r for r in all_results if r.card_type == "clarify"), None)
        if clarification is not None:
            payload = {
                "status": "clarify",
                "text": str(clarification.payload.get("question") or "Please clarify the request."),
                "sources": [], "citations": [], "unavailable_sources": unavailable,
                "limitations": [],
            }
            await emit.put(sse("answer", payload))
            state["timing"].setdefault(
                "final_answer_ms", int((time.perf_counter() - state["timing"]["started_at"]) * 1000)
            )
            _persist(history.set_answer, state["conversation_id"], state["user"], state["turn_id"], payload)
        elif refusal is not None:
            payload = {
                "status": "refused",
                "text": str(refusal.payload.get("message") or "That request cannot be answered safely."),
                "sources": [], "citations": [], "unavailable_sources": unavailable,
                "limitations": [],
            }
            await emit.put(sse("answer", payload))
            state["timing"].setdefault(
                "final_answer_ms", int((time.perf_counter() - state["timing"]["started_at"]) * 1000)
            )
            _persist(history.set_answer, state["conversation_id"], state["user"], state["turn_id"], payload)
        else:
            # The agent can answer a bare message (greeting, chit-chat, a question with
            # no tool result) by writing text directly; that is a usable reply even
            # though it produced no intelligence card. Surface it as a normal answer
            # instead of erroring.
            direct = state.get("agent_final_result")
            if direct is not None and (direct.text or "").strip():
                serialized_end = _parse_end_call(direct.text)
                if serialized_end is not None:
                    outcome = serialized_end.get("outcome")
                    payload = {
                        "status": "clarify" if outcome == "clarify" else "refused",
                        "text": serialized_end.get("message", ""),
                        "sources": [],
                        "citations": [],
                        "unavailable_sources": unavailable,
                        "limitations": [],
                        "suggestions": serialized_end.get("suggestions", []),
                        "reason": serialized_end.get("reason_code"),
                        "origin": "model",
                    }
                    await emit.put(
                        sse("refusal" if outcome == "refuse" else "answer", payload)
                    )
                    state["timing"].setdefault(
                        "final_answer_ms",
                        int((time.perf_counter() - state["timing"]["started_at"]) * 1000),
                    )
                    _persist(history.set_answer,
                        state["conversation_id"], state["user"], state["turn_id"], payload)
                    return {}
                payload = {
                    "status": "answered",
                    "text": direct.text,
                    "sources": [],
                    "citations": [],
                    "unavailable_sources": unavailable,
                    "limitations": [],
                    "facts": [],
                }
                await emit.put(sse("answer", payload))
                state["timing"].setdefault(
                    "final_answer_ms", int((time.perf_counter() - state["timing"]["started_at"]) * 1000)
                )
                _persist(history.set_answer, state["conversation_id"], state["user"], state["turn_id"], payload)
                _persist(history.set_usage,
                    state["conversation_id"], state["user"], state["turn_id"],
                    prompt_tokens=getattr(direct, "prompt_tokens", 0),
                    completion_tokens=getattr(direct, "completion_tokens", 0),
                )
                return {}
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
    result = state.get("agent_final_result")
    if result is not None and result.text:
        # Preserve the model's content verbatim. Tool calls and tool results remain
        # separate messages, and the agent loop alone decides whether to continue.
        text = result.text

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
        "status": "partial" if unavailable or limitations else "answered",
        "text": text,
        "sources": [r.source for r in results],
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
        yield sse("conversation", {"conversation_id": conversation_id})
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
        "_restore_system_slot": is_new_chat,
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
            if settings.workbench_compaction_enabled:
                _spawn_background(compaction.maybe_compact(conversation_id, user))
            await emit.put(None)  # sentinel: the graph is done producing frames

    task = asyncio.create_task(drive())
    try:
        while True:
            frame = await emit.get()
            if frame is None:
                break
            yield frame
    finally:
        if not task.done():
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
    yield sse("done", {"total_ms": int((time.perf_counter() - started_at) * 1000)})
