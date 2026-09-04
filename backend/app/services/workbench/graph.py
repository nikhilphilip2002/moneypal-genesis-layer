"""Stable streaming entry point for the plain-async Workbench orchestrator."""

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
from app.services.workbench import access, compaction, composer, history, models, nodes, prompts, router
from app.services.workbench.results import SourceResult

logger = logging.getLogger(__name__)


def _persist(operation, *args, **kwargs) -> None:
    """History is durable best-effort; storage failure must not erase an answer."""
    try:
        operation(*args, **kwargs)
    except Exception:  # noqa: BLE001
        logger.warning("workbench history operation failed", exc_info=True)


def sse(event: str, data: Any) -> str:
    return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"


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


class WorkbenchState(TypedDict):
    question: str
    conversation_id: str
    user: str
    role: str
    turn_id: str
    history_messages: list[dict[str, str]]
    emit: "asyncio.Queue[str | None]"
    pinned: NotRequired[str | None]
    data_access: NotRequired[str | None]
    source_policy: access.SourceAccessPolicy
    decision: NotRequired[router.RouteDecision]
    results: NotRequired[list[SourceResult]]
    timing: dict[str, Any]


async def select_sources(state: WorkbenchState) -> dict[str, Any]:
    emit = state["emit"]
    await emit.put(sse("stage", {"stage": "routing"}))
    decision = await router.route(
        state["question"], role=state["role"], pinned=state.get("pinned"),
        history_messages=state.get("history_messages", []),
        policy=state["source_policy"],
    )
    if decision.route == "dispatch":
        await emit.put(sse("route", {"sources": decision.sources, "intent": decision.intent,
                                     "model": decision.model, "reason": decision.reason,
                                     "confidence": decision.confidence,
                                     "fallback_used": decision.fallback_used,
                                     "policy_version": decision.policy_version}))
    from app.core.logging import log_app_event

    log_app_event(
        f"Workbench routed to: {decision.sources if decision.route == 'dispatch' else decision.route}",
        event="workbench_routed",
        stage="routing",
        data={
            "sources": decision.sources, "route": decision.route, "model": decision.model,
            "reason": decision.reason, "confidence": decision.confidence,
            "fallback_used": decision.fallback_used,
            "ambiguity_class": decision.ambiguity_class,
            "effective_sources": list(decision.effective_sources),
        },
    )
    try:
        chosen = decision.sources if decision.route == "dispatch" else []
        history.set_route(
            state["conversation_id"], state["user"], state["turn_id"],
            sources=chosen, intent=decision.intent or state["question"], model=decision.model,
            reason=decision.reason, confidence=decision.confidence,
            fallback_used=decision.fallback_used, ambiguity_class=decision.ambiguity_class,
            effective_sources=decision.effective_sources,
        )
        if decision.route == "refuse":
            history.set_refusal(
                state["conversation_id"], state["user"], state["turn_id"],
                {"reason": decision.reason, "message": decision.message},
            )
    except Exception:  # noqa: BLE001
        logger.warning("workbench history record failed", exc_info=True)
    return {"decision": decision}


async def _h_db(intent: str, state: WorkbenchState) -> SourceResult:
    # The router may paraphrase `intent` while selecting sources. Never send that rewrite
    # into governed NLQ: borrower names, account identifiers, periods, and distinctions
    # such as principal vs interest must remain byte-for-byte as the user supplied them.
    return await nodes.run_db(
        intent,
        conversation_id=state["conversation_id"], user=state["user"], role=state["role"],
        access_mode=state.get("data_access"),
        history_messages=state.get("history_messages", []),
    )


async def _h_macro(intent: str, _state: WorkbenchState) -> SourceResult:
    return await nodes.run_macro(
        intent, history_messages=_state.get("history_messages", []),
        policy=_state["source_policy"],
    )


async def _h_competitive(intent: str, _state: WorkbenchState) -> SourceResult:
    return await nodes.run_competitive(intent, policy=_state["source_policy"])


async def _h_regulatory(intent: str, _state: WorkbenchState) -> SourceResult:
    return await nodes.run_regulatory(intent, policy=_state["source_policy"])


async def _h_knowledge(intent: str, _state: WorkbenchState) -> SourceResult:
    return await nodes.run_knowledge(
        intent, history_messages=_state.get("history_messages", []),
    )


async def _h_schema(intent: str, _state: WorkbenchState) -> SourceResult:
    return await nodes.run_schema(intent, access_mode=_state.get("data_access"))


async def _h_web(intent: str, _state: WorkbenchState) -> SourceResult:
    return await nodes.run_web(
        intent, user=_state["user"], policy=_state["source_policy"],
    )


# source id -> handler. Adding a source is a new entry here plus a catalog entry — the
# dispatch node itself never changes.
_HANDLERS = {
    "db": _h_db,
    "macro": _h_macro,
    "competitive": _h_competitive,
    "regulatory": _h_regulatory,
    "knowledge": _h_knowledge,
    "schema": _h_schema,
    "web": _h_web,
}


async def dispatch_sources(state: WorkbenchState) -> dict[str, Any]:
    emit = state["emit"]
    decision = state.get("decision") or router.RouteDecision(route="refuse", reason="out_of_scope")

    if decision.route == "refuse":
        await emit.put(sse("refusal", {"route": "refuse", "reason": decision.reason,
                                       "message": decision.message}))
        return {"results": []}

    async def run_one(source_id: str) -> SourceResult:
        state["timing"]["source_attempts"].append(source_id)
        await emit.put(sse("source_start", {"source": source_id}))
        handler = _HANDLERS.get(source_id)
        if not state["source_policy"].allows(source_id):
            result = SourceResult(
                source=source_id,
                card_type="error",
                payload={"message": "That source is not enabled for this request."},
            )
        elif handler is None:
            result = SourceResult(source=source_id, card_type="error",
                                  payload={"message": f"Unknown source {source_id}."})
        else:
            try:
                source_intent = decision.source_intents.get(source_id)
                if not source_intent:
                    # Preserve the exact user text for a normal DB turn. Other sources may
                    # safely use the router's normalized intent.
                    source_intent = state["question"] if source_id == "db" else decision.intent
                result = await handler(source_intent, state)
            except Exception:  # noqa: BLE001 - isolate unavailable dependencies
                logger.exception("workbench source %s failed", source_id)
                result = SourceResult(
                    source=source_id,
                    card_type="error",
                    payload={
                        "message": f"{source_id.title()} intelligence is temporarily unavailable.",
                        "retryable": True,
                    },
                )
        await emit.put(sse("source_card", {
            "source": result.source, "card_type": result.card_type, **result.payload,
        }))
        state["timing"].setdefault(
            "first_card_ms", int((time.perf_counter() - state["timing"]["started_at"]) * 1000)
        )
        state["timing"]["source_completions"].append(source_id)
        try:
            history.add_card(
                state["conversation_id"], state["user"], state["turn_id"],
                {"source": result.source, "card_type": result.card_type, "payload": result.payload},
            )
        except Exception:  # noqa: BLE001
            logger.warning("workbench card persistence failed", exc_info=True)
        return result

    # Fan out. Results stream as each finishes; the ordered list is kept for synthesis.
    results = await asyncio.gather(*(run_one(s) for s in decision.sources))
    return {"results": list(results)}


_ANSWERABLE_CARD_TYPES = frozenset(
    {"chart", "analysis", "worklist", "briefing", "brief", "schema"}
)

async def answer_results(state: WorkbenchState) -> dict[str, Any]:
    emit = state["emit"]
    decision = state.get("decision")
    if decision is not None and decision.route == "refuse":
        payload = {
            "status": "refused",
            "text": decision.message or "That request cannot be handled by this workbench.",
            "sources": [], "citations": [], "unavailable_sources": [], "limitations": [],
        }
        await emit.put(sse("answer", payload))
        state["timing"].setdefault(
            "final_answer_ms", int((time.perf_counter() - state["timing"]["started_at"]) * 1000)
        )
        _persist(history.set_answer, state["conversation_id"], state["user"], state["turn_id"], payload)
        return {}
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
            first_error = next((r for r in all_results if r.card_type == "error"), None)
            if first_error is not None:
                # The source card already streamed the actionable failure. Do not add a
                # second generic orchestrator error underneath it.
                message = str(first_error.payload.get("message") or "Source unavailable.")
                _persist(history.set_error,
                    state["conversation_id"], state["user"], state["turn_id"], message
                )
                return {}
            message = "No intelligence source produced a usable answer."
            _persist(history.set_error, state["conversation_id"], state["user"], state["turn_id"], message)
            await emit.put(sse("error", {"message": message, "retryable": True}))
        return {}

    findings = composer.evidence_text(results)
    text = results[0].summary.strip()
    result = None
    composition_limitation: dict[str, str] | None = None
    needs_composition = len(results) > 1 or any(
        r.evidence and r.source in {"macro", "competitive", "regulatory", "web"}
        for r in results
    )
    try:
        if needs_composition:
            client = models.for_step(
                "synthesize", sensitive=any(r.sensitive or r.source == "db" for r in results)
            )
            prompt = prompts.build_composer_prompt(
                question=state["question"], findings=findings,
                history_messages=composer.relevant_history(state.get("history_messages", [])),
            )
            async with asyncio.timeout(settings.workbench_composer_timeout_s):
                result = await client.complete(
                    messages=prompt.messages,
                    timeout_s=settings.workbench_composer_timeout_s,
                    call_purpose="final_compose",
                    prompt_version=prompt.version,
                    prefix_hash=prompt.prefix_hash,
                    max_output_tokens=settings.workbench_composer_max_tokens,
                )
            candidate = result.text.strip()
            if candidate and composer.numbers_are_grounded(candidate, findings):
                text = candidate
            else:
                text = composer.extractive_fallback(results)
                composition_limitation = {
                    "source": "composer",
                    "reason": "The generated synthesis was not fully grounded; showing retrieved evidence instead.",
                }
    except Exception as exc:  # noqa: BLE001 - deterministic findings remain usable
        logger.warning("workbench synthesis failed, using grounded findings: %s", exc)
        text = composer.extractive_fallback(results)
        composition_limitation = {
            "source": "composer",
            "reason": "The answer composer was unavailable; showing retrieved evidence instead.",
        }

    if composition_limitation is not None:
        limitations.append(composition_limitation)

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
    data_access: str | None = None, external_sources_enabled: bool = False,
) -> AsyncIterator[str]:
    """Run one turn, yielding SSE frames as the graph produces them."""
    started_at = time.perf_counter()
    emit: "asyncio.Queue[str | None]" = asyncio.Queue()
    try:
        built = history.build_transcript(conversation_id, user=user)
    except Exception:  # noqa: BLE001
        logger.warning("workbench transcript load failed; continuing without history", exc_info=True)
        built = history.Transcript()
    history_messages = built.messages
    source_policy = access.build_policy(
        role=role, external_sources_enabled=external_sources_enabled,
    )
    try:
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
        if built.overflow:
        # The conversation no longer fits its own most recent exchange. The answer below
        # is still produced, but from a clipped view, so say so rather than let quality
        # degrade silently. Not retryable: asking again in this conversation cannot help.
            logger.warning(
                "workbench transcript overflow: conversation=%s tokens=%d budget=%d",
                conversation_id, built.tokens, built.budget,
            )
            yield sse("error", {"message": CONTEXT_FULL_MESSAGE, "retryable": False})
        yield sse("stage", {"stage": "understanding"})
    except (GeneratorExit, asyncio.CancelledError):
        _persist(history.complete_turn, conversation_id, user, turn_id, partial=True)
        raise

    state: WorkbenchState = {
        "question": question, "conversation_id": conversation_id,
        "user": user, "role": role, "turn_id": turn_id,
        "history_messages": history_messages,
        "emit": emit, "pinned": pinned,
        "data_access": data_access,
        "source_policy": source_policy,
        "timing": {
            "started_at": started_at,
            "first_event_ms": first_event_ms,
            "source_attempts": [],
            "source_completions": [],
        },
    }

    async def drive() -> None:
        partial = False
        call_records = []
        try:
            with collect_calls() as call_records:
                from app.services.workbench.orchestrator import run

                await run(state)
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
            # A context-window rejection is not a transient fault: asking again in this
            # conversation sends the same oversized prompt. Say what will actually help.
            if _is_context_overflow(exc):
                logger.warning("workbench context overflow: conversation=%s", conversation_id)
                message, retryable = CONTEXT_FULL_MESSAGE, False
            else:
                logger.exception("workbench graph failed")
                message, retryable = "The workbench hit an error.", True
            log_app_event(
                f"Workbench turn failed: {message}",
                event="workbench_turn_completed",
                outcome="error",
                error=str(exc),
            )
            _persist(history.set_error, conversation_id, user, turn_id, message)
            await emit.put(sse("error", {"message": message, "retryable": retryable}))
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
            _persist(history.complete_turn, conversation_id, user, turn_id, partial=partial)
            # Checkpoint after the turn, never before it: the summarization call would
            # otherwise sit between the user's question and their first streamed token.
            # Detached and failure-tolerant — the transcript works without it.
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
    yield sse("done", {})
