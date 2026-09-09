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
from app.services.workbench import (
    access, calculations, compaction, composer, facts, history, models, prompts,
)
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
    from app.services.nlq.llm import LLMError, LLMProtocolError, LLMTimeout, LLMUnavailable
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
    history_messages: list[dict[str, str]]
    agent_history_messages: NotRequired[list[dict[str, Any]]]
    agent_private_entities: NotRequired[tuple[str, ...]]
    emit: "asyncio.Queue[str | None]"
    pinned: NotRequired[str | None]
    source_policy: access.SourceAccessPolicy
    decision: NotRequired[ExecutionDecision]
    results: NotRequired[list[SourceResult]]
    timing: dict[str, Any]
    agent_native: NotRequired[bool]
    agent_synthesis_messages: NotRequired[list[dict[str, Any]]]
    agent_prompt_prefix_hash: NotRequired[str]


_ANSWERABLE_CARD_TYPES = frozenset(
    {"chart", "analysis", "worklist", "briefing", "brief", "schema"}
)

def _synthesis_timeout(state: WorkbenchState) -> float:
    return max(0.001, min(
        settings.llm_timeout_s,
        settings.nlq_request_budget_s - (time.perf_counter() - state["timing"]["started_at"]),
    ))


async def _repair_synthesis(
    state: WorkbenchState,
    client,
    *,
    base_messages: list[dict[str, Any]],
    candidate: str,
    validation: composer.ClaimValidation,
    facts_block: str,
    prompt_version: str,
    prefix_hash: str,
) -> str | None:
    """One focused repair round naming the exact unsupported claims and the fact set.

    Returns the repaired text, or ``None`` when a repair is disabled, unaffordable under
    the agent's TurnBudget, or the model returned nothing. The caller decides what to do
    with a repair that is still not fully grounded.
    """
    if not settings.workbench_agent_synthesis_repairs or not base_messages:
        return None
    budget = state.get("_agent_budget")
    if budget is not None:
        if budget.rounds_remaining <= 0:
            return None
        budget.charge_round("agent_synthesize_repair")
    messages = [
        *base_messages,
        {"role": "assistant", "content": candidate},
        {"role": "user", "content": composer.repair_message(validation.unsupported, facts_block)},
    ]
    kwargs: dict[str, Any] = {}
    if state.get("agent_native"):
        from app.services.workbench.agent_tools import native_tool_definitions

        kwargs = {
            "tools": native_tool_definitions(
                state["source_policy"], catalog=state.get("_agent_catalog"),
            ),
            "tool_choice": "none",
            "parallel_tool_calls": False,
        }
    repaired = await client.complete(
        messages=messages,
        timeout_s=_synthesis_timeout(state),
        call_purpose="agent_synthesize" if state.get("agent_native") else "final_compose",
        call_kind="repair",
        prompt_version=prompt_version,
        prefix_hash=prefix_hash,
        max_output_tokens=settings.workbench_composer_max_tokens,
        **kwargs,
    )
    if getattr(repaired, "tool_calls", None):
        raise RuntimeError("tool call returned during synthesis repair phase")
    return repaired.text.strip() or None


async def _ground_answer(
    state: WorkbenchState,
    *,
    candidate: str,
    findings: str,
    fact_set: list[facts.Fact],
    facts_block: str,
    results: list[SourceResult],
    repair,
) -> tuple[str, dict[str, str] | None, list[facts.Fact]]:
    """Claim-level grounding: validate, repair once, then omit what is still unsupported.

    The model's text is never replaced wholesale. ``repair`` is an awaitable taking the
    failed validation and returning repaired text or ``None``.
    """
    validation = composer.validate_claims(candidate, findings, fact_set)
    if validation.ok:
        return candidate, None, validation.cited_facts
    try:
        repaired = await repair(validation)
    except Exception as exc:  # noqa: BLE001 - the original text still has a grounded core
        logger.warning("workbench synthesis repair failed; removing unsupported claims: %s", exc)
        repaired = None
    if repaired:
        repaired_validation = composer.validate_claims(repaired, findings, fact_set)
        if repaired_validation.ok:
            return repaired, None, repaired_validation.cited_facts
        candidate, validation = repaired, repaired_validation
    cleaned, removed = composer.remove_unsupported_claims(candidate, validation.unsupported)
    names = validation.unsupported_texts
    shown = ", ".join(names[:8]) + (f" and {len(names) - 8} more" if len(names) > 8 else "")
    if cleaned:
        cited = composer.validate_claims(cleaned, findings, fact_set).cited_facts
        reason = (
            f"Removed {len(removed)} statement(s) whose figures the retrieved results "
            f"could not verify: {shown}."
        )
        return cleaned, {"source": "composer", "reason": reason}, cited
    # Every sentence carried an unverifiable figure, so nothing of the model's text
    # remains to show; the governed evidence is the only text left.
    return composer.extractive_fallback(results), {
        "source": "composer",
        "reason": (
            "Every statement in the generated answer carried a figure the retrieved "
            f"results could not verify ({shown}); showing retrieved evidence instead."
        ),
    }, []


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

    findings = composer.evidence_text(results)
    fact_ledger = facts.from_results(results, max_per_result=100)
    # Source facts plus their deterministic derivations (totals, shares, deltas, rates,
    # rankings). The model may state any of them; the validator accepts nothing else.
    fact_set = calculations.fact_set(fact_ledger)
    facts_block = composer.facts_text(fact_set)
    text = results[0].summary.strip()
    result = state.get("agent_final_result")
    composition_limitation: dict[str, str] | None = None
    verified_facts: list[facts.Fact] = []
    # One governed DB card already has a deterministic, chart-aware summary and complete
    # rows. Re-synthesizing it made the model omit endpoint months, mis-rank values, and
    # waste a second local-model call. Composition remains necessary when evidence must be
    # combined or interpreted across document/external sources.
    needs_composition = result is None and (len(results) > 1 or any(
        r.source in {"knowledge", "schema", "macro", "competitive", "regulatory", "web"}
        for r in results
    ))
    candidate = result.text.strip() if result is not None else ""
    # How a repair replays exactly what the answering model saw, per path.
    repair_client = None
    repair_messages: list[dict[str, Any]] = list(state.get("agent_synthesis_messages", []))
    repair_version = prompts.AGENT_PROMPT_VERSION
    repair_prefix = state.get("agent_prompt_prefix_hash", "")
    try:
        if needs_composition:
            client = models.for_step(
                "synthesize",
                sensitive=bool(state.get("agent_native"))
                or any(r.sensitive or r.source == "db" for r in results),
            )
            repair_client = client
            prompt = prompts.build_composer_prompt(
                question=state["question"], findings=findings,
                history_messages=composer.relevant_history(state.get("history_messages", [])),
                facts=facts_block,
            )
            async with asyncio.timeout(_synthesis_timeout(state)):
                if state.get("agent_native"):
                    from app.services.workbench.agent_tools import native_tool_definitions

                    # The agent's TurnBudget is the only round accounting; synthesis
                    # is a round like any other and BudgetExhausted lands in the
                    # composer-unavailable limitation below.
                    if (budget := state.get("_agent_budget")) is not None:
                        budget.charge_round("agent_synthesize")
                    repair_messages = list(state.get("agent_synthesis_messages", prompt.messages))
                    if facts_block:
                        repair_messages.append(
                            {"role": "user", "content": composer.facts_message(facts_block)}
                        )
                    result = await client.complete(
                        messages=repair_messages,
                        tools=native_tool_definitions(
                            state["source_policy"], catalog=state.get("_agent_catalog"),
                        ),
                        tool_choice="none",
                        parallel_tool_calls=False,
                        timeout_s=_synthesis_timeout(state),
                        call_purpose="agent_synthesize",
                        prompt_version=prompts.AGENT_PROMPT_VERSION,
                        prefix_hash=state.get("agent_prompt_prefix_hash", ""),
                        max_output_tokens=settings.workbench_composer_max_tokens,
                    )
                    if getattr(result, "tool_calls", None):
                        raise RuntimeError("tool call returned during final synthesis phase")
                else:
                    repair_messages = list(prompt.messages)
                    repair_version, repair_prefix = prompt.version, prompt.prefix_hash
                    result = await client.complete(
                        messages=prompt.messages,
                        timeout_s=_synthesis_timeout(state),
                        call_purpose="final_compose",
                        prompt_version=prompt.version,
                        prefix_hash=prompt.prefix_hash,
                        max_output_tokens=settings.workbench_composer_max_tokens,
                    )
            candidate = result.text.strip()
            if not candidate:
                text = composer.extractive_fallback(results)
                composition_limitation = {
                    "source": "composer",
                    "reason": "The answer composer returned no text; showing retrieved evidence instead.",
                }
        if candidate:
            async def repair(validation: composer.ClaimValidation) -> str | None:
                client = repair_client or models.for_step("synthesize", sensitive=True)
                return await _repair_synthesis(
                    state, client, base_messages=repair_messages, candidate=candidate,
                    validation=validation, facts_block=facts_block,
                    prompt_version=repair_version, prefix_hash=repair_prefix,
                )

            text, composition_limitation, verified_facts = await _ground_answer(
                state, candidate=candidate, findings=findings, fact_set=fact_set,
                facts_block=facts_block, results=results, repair=repair,
            )
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
        # Verified facts the prose cites, rendered apart from any qualitative observation.
        "facts": [composer.fact_dict(fact) for fact in verified_facts],
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
    try:
        built = history.build_transcript(conversation_id, user=user)
    except Exception:  # noqa: BLE001
        logger.warning("workbench transcript load failed; continuing without history", exc_info=True)
        built = history.Transcript()
    history_messages = built.messages
    source_policy = access.build_policy(
        role=role, external_sources_enabled=external_sources_enabled,
        pinned_source=pinned,
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
        if built.overflow:
        # The conversation no longer fits its own most recent exchange. The answer below
        # is still produced, but from a clipped view, so say so rather than let quality
        # degrade silently. Not retryable: asking again in this conversation cannot help.
            logger.warning(
                "workbench transcript overflow: conversation=%s tokens=%d budget=%d",
                conversation_id, built.tokens, built.budget,
            )
            _persist(
                history.set_error, conversation_id, user, turn_id, CONTEXT_FULL_MESSAGE,
                code=CONTEXT_CAPACITY_CODE, retryable=False,
            )
            yield sse("error", {
                "code": CONTEXT_CAPACITY_CODE,
                "message": CONTEXT_FULL_MESSAGE,
                "retryable": False,
            })
        yield sse("stage", {"stage": "understanding"})
    except (GeneratorExit, asyncio.CancelledError):
        _persist(history.complete_turn, conversation_id, user, turn_id, partial=True)
        raise

    state: WorkbenchState = {
        "question": question, "conversation_id": conversation_id,
        "user": user, "role": role, "turn_id": turn_id,
        "history_messages": history_messages,
        "agent_history_messages": agent_history_messages,
        "agent_private_entities": agent_private_entities,
        "emit": emit, "pinned": pinned,
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
    yield sse("done", {})
