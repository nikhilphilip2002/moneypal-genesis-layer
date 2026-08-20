"""The ask pipeline: question -> plan -> chart, streamed as SSE stages.

Streaming is not decoration. The QuerySpec path takes 1.5-3s and text-to-SQL up to 7s;
showing "Understanding -> Planning -> Querying -> Charting" makes that legible, whereas a
spinner of the same duration reads as a hang.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from dataclasses import dataclass
from datetime import date
from typing import Any, AsyncIterator

from app.core.config import settings
from app.services.nlq import audit, conversation, pii, planner, text_to_sql
from app.services.nlq.catalog import Catalog, get_catalog
from app.services.nlq.compiler import CompileError
from app.services.nlq.contracts import (
    AnalysisPlan,
    AskResponse,
    BriefingPlan,
    ClarifyPlan,
    QuerySpecPlan,
    RefusalPlan,
    SqlPlan,
    WorklistPlan,
)
from app.services.nlq.executor import ExecutionError
from app.services.nlq.llm import LLMError
from app.services.nlq.pipeline import run_spec, run_sql

logger = logging.getLogger(__name__)

# Module-level so the budget test can replace it with a few milliseconds.
HARD_CEILING_S = settings.nlq_request_budget_s

NOT_IN_DATA_MESSAGE = (
    "The loan book does not hold what that question needs. It covers origination, "
    "outstanding balances, delinquency, collections and the general ledger."
)
"""Fixed, because the alternative is the model narrating the shape of a warehouse it has
only seen a catalogue listing of. A wrong explanation of *why* an answer is unavailable is
as damaging as a wrong answer: the user plans around it."""

COVERAGE_REASONS = frozenset({"not_in_data", "out_of_scope"})
"""The refusal reasons that assert something about the data rather than the question."""


@dataclass(slots=True)
class AskContext:
    question: str
    conversation_id: str
    user: str = "anonymous"
    role: str = "gicc_policy"
    today: date | None = None
    history_messages: list[dict[str, str]] | None = None


def _remaining_seconds(started: float) -> float:
    """One budget for the whole turn, rather than a fresh timeout for every phase."""
    return max(0.001, HARD_CEILING_S - (time.perf_counter() - started))


def sse(event: str, data: Any) -> str:
    return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"


def _clarified_last_turn(state) -> bool:
    turns = getattr(state, "turns", None)
    return bool(turns) and turns[-1].route == "clarify"


async def ask_stream(ctx: AskContext, catalog: Catalog | None = None) -> AsyncIterator[str]:
    """Run one question, yielding SSE frames."""
    cat = catalog or get_catalog()
    turn_id = uuid.uuid4().hex[:12]
    started = time.perf_counter()

    state = conversation.load(ctx.conversation_id)
    yield sse("stage", {"stage": "understanding", "turn_id": turn_id})

    # Reference resolution before retrieval, so what gets planned and logged is the
    # complete question rather than "and by branch?".
    resolved, structural = conversation.resolve(ctx.question, state, cat)
    if resolved != ctx.question:
        yield sse("rewrite", {"resolved_question": resolved})

    # A follow-up that only adds a dimension or changes a filter is detected structurally
    # and skips the LLM entirely: instant, free, and always correct.
    if structural is not None:
        yield sse("stage", {"stage": "querying", "shortcut": "structural_followup"})
        async for frame in _execute_and_emit(
            ctx, cat, structural, turn_id, state, resolved, plan_summary="Follow-up applied "
            "to the previous question without re-planning.", started=started
        ):
            yield frame
        return

    yield sse("stage", {"stage": "planning"})
    try:
        outcome = await asyncio.wait_for(
            planner.plan(
                resolved, catalog=cat, history_messages=ctx.history_messages or [],
            ),
            timeout=_remaining_seconds(started),
        )
    except TimeoutError:
        logger.warning("NLQ ask exceeded its request budget during planning")
        audit.record(
            turn_id=turn_id, ctx=ctx, resolved=resolved, route="error",
            outcome="timeout", detail="planning exceeded the request budget",
        )
        yield sse(
            "error",
            {"message": "The question took too long to plan. Please try again.", "retryable": True},
        )
        yield sse("done", {"turn_id": turn_id})
        return
    except LLMError as exc:
        logger.warning("NLQ ask failed at planning: %s", exc)
        audit.record(
            turn_id=turn_id, ctx=ctx, resolved=resolved, route="error",
            outcome="llm_unavailable", detail=str(exc),
        )
        yield sse(
            "error",
            {
                "message": "The assistant is offline. Saved questions and dashboards still "
                "work.",
                "retryable": True,
            },
        )
        yield sse("done", {"turn_id": turn_id})
        return

    plan = outcome.plan
    yield sse(
        "plan",
        {
            "route": plan.route,
            "attempts": outcome.attempts,
            "repaired": outcome.repaired,
            "model": outcome.model,
        },
    )

    if isinstance(plan, ClarifyPlan):
        # Answering a clarification arrives as an ordinary new question, so a planner that
        # clarifies again leaves the user in a loop with no exit — tapping a suggestion
        # produces the next question, forever. Two in a row means the question is not
        # going to resolve, and saying so is the only honest way out.
        if _clarified_last_turn(state):
            audit.record(turn_id=turn_id, ctx=ctx, resolved=resolved, route="clarify",
                         outcome="clarify_loop", plan=outcome)
            conversation.append_turn(state, ctx.question, resolved, "refuse", None, 0)
            conversation.save(state)
            yield sse(
                "refusal",
                {
                    "route": "refuse",
                    "reason": "not_in_data",
                    "message": "I asked for a clarification and still could not pin that "
                               "down. Try one of these, which name a measure and a period "
                               "outright.",
                    "examples": planner.refusal_examples(),
                },
            )
            yield sse("done", {"turn_id": turn_id})
            return
        audit.record(turn_id=turn_id, ctx=ctx, resolved=resolved, route="clarify",
                     outcome="clarify", plan=outcome)
        conversation.append_turn(state, ctx.question, resolved, "clarify", None, 0)
        conversation.save(state)
        yield sse("clarify", plan.model_dump(mode="json"))
        yield sse("done", {"turn_id": turn_id})
        return

    if isinstance(plan, RefusalPlan):
        payload = plan.model_dump(mode="json")
        # The examples are never the model's to write. Asked why it cannot answer, it will
        # invent a neighbouring question that sounds answerable and is not — one refusal
        # here offered "Equity shareholding breakdown by shareholder", a subject the
        # warehouse has no data on at all, immediately after saying so. Every suggestion
        # shown must be one the catalog can actually serve.
        payload["examples"] = planner.refusal_examples(resolved, plan.reason)
        if plan.reason in COVERAGE_REASONS:
            # These two are claims about the warehouse's contents, and the model knows the
            # catalog only as a list. It has asserted things that are plainly false ("no
            # standalone principal outstanding metric" — there is one). The remaining
            # reasons judge the *question* — predictive, advice, unsafe — which the model
            # is entitled to do in its own words.
            payload["message"] = NOT_IN_DATA_MESSAGE
        audit.record(turn_id=turn_id, ctx=ctx, resolved=resolved, route="refuse",
                     outcome=plan.reason, plan=outcome)
        conversation.append_turn(state, ctx.question, resolved, "refuse", None, 0)
        yield sse("refusal", payload)
        yield sse("done", {"turn_id": turn_id})
        return

    if isinstance(plan, AnalysisPlan):
        async for frame in _analysis_path(ctx, cat, plan, turn_id, state, resolved, started):
            yield frame
        return

    if isinstance(plan, WorklistPlan):
        async for frame in _worklist_path(ctx, cat, plan, turn_id, state, resolved, started):
            yield frame
        return

    if isinstance(plan, BriefingPlan):
        async for frame in _briefing_path(ctx, cat, plan, turn_id, state, resolved, started):
            yield frame
        return

    if isinstance(plan, SqlPlan):
        async for frame in _text_to_sql_path(ctx, cat, plan, turn_id, state, resolved, started):
            yield frame
        return

    assert isinstance(plan, QuerySpecPlan)
    yield sse("stage", {"stage": "querying"})
    async for frame in _execute_and_emit(
        ctx, cat, plan.spec, turn_id, state, resolved,
        plan_summary=plan.reasoning or "", started=started,
    ):
        yield frame


async def _analysis_path(
    ctx: AskContext,
    cat: Catalog,
    plan: AnalysisPlan,
    turn_id: str,
    state,
    resolved: str,
    started: float,
) -> AsyncIterator[str]:
    """Run a preset analysis: several governed queries, then a deterministic composition.

    The steps run off the event loop — they are synchronous psycopg2 calls on the read-only
    pool — so a seven-step briefing does not block every other in-flight question.
    """
    import asyncio

    from app.services.nlq import analysis as analysis_service

    yield sse("stage", {"stage": "querying", "analysis": plan.analysis_id})
    try:
        spec = analysis_service.build(
            plan.analysis_id, catalog=cat, period=plan.period, filters=plan.filters
        )
        result = await asyncio.wait_for(
            asyncio.to_thread(
                analysis_service.run, spec, catalog=cat, today=ctx.today, role=ctx.role
            ),
            timeout=_remaining_seconds(started),
        )
    except TimeoutError:
        audit.record(turn_id=turn_id, ctx=ctx, resolved=resolved, route="analysis",
                     outcome="timeout", detail="analysis exceeded the request budget")
        yield sse("error", {"message": "The analysis took too long. Please retry.",
                            "retryable": True})
        yield sse("done", {"turn_id": turn_id})
        return
    except analysis_service.AnalysisError as exc:
        # The preset enum makes this near-impossible from the model, so reaching here means
        # the catalog changed under a cached plan. Fall back rather than error.
        logger.warning("NLQ analysis %s unavailable: %s", plan.analysis_id, exc)
        audit.record(turn_id=turn_id, ctx=ctx, resolved=resolved, route="analysis",
                     outcome="unknown_analysis", detail=str(exc))
        yield sse(
            "refusal",
            {
                "route": "refuse",
                "reason": "not_in_data",
                "message": NOT_IN_DATA_MESSAGE,
                "examples": planner.refusal_examples(),
            },
        )
        yield sse("done", {"turn_id": turn_id})
        return
    except ExecutionError as exc:
        logger.error("NLQ analysis execution failed: %s", exc.detail)
        audit.record(turn_id=turn_id, ctx=ctx, resolved=resolved, route="analysis",
                     outcome="execution_error", detail=exc.detail)
        yield sse("error", {"message": str(exc), "retryable": True})
        yield sse("done", {"turn_id": turn_id})
        return

    yield sse("stage", {"stage": "charting"})

    conversation.append_turn(
        state, ctx.question, resolved, "analysis",
        result.charts[0].chart_type if result.charts else None,
        sum(c.lineage.row_count for c in result.charts),
    )
    # The anchor is the top finding's own spec, so "why?" and "which branches?" continue
    # from the thing the briefing led with rather than from the whole briefing. Findings
    # carry their spec precisely so this needs no matching back to a step — chart titles are
    # generated from the spec and would not match a step label anyway.
    if result.findings:
        conversation.set_anchor(state, result.findings[0].spec)
    conversation.save(state)

    audit.record(
        turn_id=turn_id, ctx=ctx, resolved=resolved, route="analysis", outcome="answered",
        detail=plan.analysis_id,
        row_count=sum(c.lineage.row_count for c in result.charts),
        duration_ms=int((time.perf_counter() - started) * 1000),
    )

    response = AskResponse(
        conversation_id=ctx.conversation_id,
        turn_id=turn_id,
        status="answered",
        analysis=result,
        plan_summary=plan.reasoning or "",
    )
    yield sse("analysis", response.model_dump(mode="json"))
    yield sse("done", {"turn_id": turn_id,
                       "duration_ms": int((time.perf_counter() - started) * 1000)})


async def _worklist_path(
    ctx: AskContext,
    cat: Catalog,
    plan: WorklistPlan,
    turn_id: str,
    state,
    resolved: str,
    started: float,
) -> AsyncIterator[str]:
    """Run a worklist preset: one governed scan, then a transparent ranking.

    The anchor is deliberately left alone. A worklist is the end of a chain, and the useful
    follow-up after it is "why is that branch on here so often?" — which should continue from
    the chart the user was looking at, not from a list of account numbers.
    """
    import asyncio

    from app.services import worklists as worklist_service

    yield sse("stage", {"stage": "querying", "worklist": plan.worklist_id})
    try:
        result = await asyncio.wait_for(
            asyncio.to_thread(
                worklist_service.build,
                plan.worklist_id,
                catalog=cat,
                as_of=ctx.today,
                filters=list(plan.filters),
                limit=plan.limit,
                role=ctx.role,
            ),
            timeout=_remaining_seconds(started),
        )
    except TimeoutError:
        audit.record(turn_id=turn_id, ctx=ctx, resolved=resolved, route="worklist",
                     outcome="timeout", detail="worklist exceeded the request budget")
        yield sse("error", {"message": "The worklist took too long. Please retry.",
                            "retryable": True})
        yield sse("done", {"turn_id": turn_id})
        return
    except worklist_service.WorklistError as exc:
        # A filter the account list cannot honour lands here. Saying so is the whole point:
        # silently dropping it would send one branch's accounts to another branch's team.
        logger.warning("NLQ worklist %s unavailable: %s", plan.worklist_id, exc)
        audit.record(turn_id=turn_id, ctx=ctx, resolved=resolved, route="worklist",
                     outcome="unavailable", detail=str(exc))
        yield sse(
            "refusal",
            {
                "route": "refuse",
                "reason": "not_in_data",
                "message": str(exc),
                "examples": planner.refusal_examples(),
            },
        )
        yield sse("done", {"turn_id": turn_id})
        return
    except ExecutionError as exc:
        logger.error("NLQ worklist execution failed: %s", exc.detail)
        audit.record(turn_id=turn_id, ctx=ctx, resolved=resolved, route="worklist",
                     outcome="execution_error", detail=exc.detail)
        yield sse("error", {"message": str(exc), "retryable": True})
        yield sse("done", {"turn_id": turn_id})
        return

    conversation.append_turn(
        state, ctx.question, resolved, "worklist", None, len(result.items)
    )
    conversation.save(state)

    audit.record(
        turn_id=turn_id, ctx=ctx, resolved=resolved, route="worklist", outcome="answered",
        detail=plan.worklist_id,
        row_count=len(result.items),
        duration_ms=int((time.perf_counter() - started) * 1000),
    )

    response = AskResponse(
        conversation_id=ctx.conversation_id,
        turn_id=turn_id,
        status="answered",
        worklist=result,
        plan_summary=plan.reasoning or "",
    )
    yield sse("worklist", response.model_dump(mode="json"))
    yield sse("done", {"turn_id": turn_id,
                       "duration_ms": int((time.perf_counter() - started) * 1000)})


async def _briefing_path(
    ctx: AskContext,
    cat: Catalog,
    plan: BriefingPlan,
    turn_id: str,
    state,
    resolved: str,
    started: float,
) -> AsyncIterator[str]:
    """"What do I need to know?" — one desk's read, answered in the thread.

    Cheap by construction: the signals were found by the scheduled scan hours ago and are
    read back from an indexed table, so the only work here is the persona's analyses. That
    is the whole reason the scan exists — asked at request time, this question has no
    baseline to compare against and nothing has been ranked.
    """
    import asyncio

    from app.services import signals as signal_service

    yield sse("stage", {"stage": "querying", "briefing": plan.persona_id})
    try:
        result = await asyncio.wait_for(
            asyncio.to_thread(
                signal_service.briefing,
                plan.persona_id,
                catalog=cat,
                today=ctx.today,
                role=ctx.role,
            ),
            timeout=_remaining_seconds(started),
        )
    except TimeoutError:
        audit.record(turn_id=turn_id, ctx=ctx, resolved=resolved, route="briefing",
                     outcome="timeout", detail="briefing exceeded the request budget")
        yield sse("error", {"message": "The briefing took too long. Please retry.",
                            "retryable": True})
        yield sse("done", {"turn_id": turn_id})
        return
    except signal_service.BriefingError as exc:
        logger.warning("NLQ briefing %s unavailable: %s", plan.persona_id, exc)
        audit.record(turn_id=turn_id, ctx=ctx, resolved=resolved, route="briefing",
                     outcome="unknown_persona", detail=str(exc))
        yield sse(
            "refusal",
            {
                "route": "refuse",
                "reason": "not_in_data",
                "message": NOT_IN_DATA_MESSAGE,
                "examples": planner.refusal_examples(),
            },
        )
        yield sse("done", {"turn_id": turn_id})
        return
    except ExecutionError as exc:
        logger.error("NLQ briefing execution failed: %s", exc.detail)
        audit.record(turn_id=turn_id, ctx=ctx, resolved=resolved, route="briefing",
                     outcome="execution_error", detail=exc.detail)
        yield sse("error", {"message": str(exc), "retryable": True})
        yield sse("done", {"turn_id": turn_id})
        return

    conversation.append_turn(
        state, ctx.question, resolved, "briefing", None, len(result.signals)
    )
    # The anchor is the leading signal's own spec, so "why?" and "which branches?" continue
    # from the thing the briefing led with. A briefing whose top finding is a data-health
    # warning carries no spec, and leaving the previous anchor alone is right — there is no
    # chart behind "the snapshot is four days old" to drill into.
    evidence = next((s.spec for s in result.signals if s.spec is not None), None)
    if evidence is not None:
        conversation.set_anchor(state, evidence)
    elif result.analyses and result.analyses[0].findings:
        conversation.set_anchor(state, result.analyses[0].findings[0].spec)
    conversation.save(state)

    audit.record(
        turn_id=turn_id, ctx=ctx, resolved=resolved, route="briefing", outcome="answered",
        detail=plan.persona_id, row_count=len(result.signals),
        duration_ms=int((time.perf_counter() - started) * 1000),
    )

    response = AskResponse(
        conversation_id=ctx.conversation_id,
        turn_id=turn_id,
        status="answered",
        briefing=result,
        plan_summary=plan.reasoning or "",
    )
    yield sse("briefing", response.model_dump(mode="json"))
    yield sse("done", {"turn_id": turn_id,
                       "duration_ms": int((time.perf_counter() - started) * 1000)})


async def _text_to_sql_path(
    ctx: AskContext,
    cat: Catalog,
    plan: SqlPlan,
    turn_id: str,
    state,
    resolved: str,
    started: float,
) -> AsyncIterator[str]:
    """The long tail: generate SQL, validate it, and only then execute.

    An unvalidated generated statement never reaches a cursor. If validation fails twice
    the answer is a refusal — on this path a plausible wrong result is worse than none,
    because the user cannot tell them apart.
    """
    yield sse("stage", {"stage": "writing_sql"})

    try:
        attempt = await asyncio.wait_for(
            text_to_sql.generate(
                resolved,
                catalog=cat,
                allow_pii=pii.may_see_pii(ctx.role),
                preferred_tables=plan.tables,
            ),
            timeout=_remaining_seconds(started),
        )
    except TimeoutError:
        audit.record(turn_id=turn_id, ctx=ctx, resolved=resolved, route="text_to_sql",
                     outcome="timeout", detail="SQL generation exceeded the request budget")
        yield sse("error", {"message": "The question took too long to translate safely. "
                                       "Please try a more specific question.",
                            "retryable": True})
        yield sse("done", {"turn_id": turn_id})
        return

    if not attempt.validated:
        audit.record(
            turn_id=turn_id, ctx=ctx, resolved=resolved, route="text_to_sql",
            outcome="validator_rejected", sql=attempt.sql, detail=attempt.error,
        )
        logger.info("NLQ text-to-SQL refused after %d attempts: %s", attempt.attempts, attempt.error)
        yield sse(
            "refusal",
            {
                "route": "refuse",
                "reason": "not_in_data",
                # The validator's message names tables and would leak schema, so it goes to
                # the audit log and never to the user.
                "message": "I could not answer that safely from the available data.",
                "examples": planner.refusal_examples(),
            },
        )
        yield sse("done", {"turn_id": turn_id})
        return

    yield sse("stage", {"stage": "querying"})
    try:
        chart = await asyncio.wait_for(
            asyncio.to_thread(
                run_sql, attempt, question=resolved, role=ctx.role, catalog=cat
            ),
            timeout=_remaining_seconds(started),
        )
    except TimeoutError:
        audit.record(turn_id=turn_id, ctx=ctx, resolved=resolved, route="text_to_sql",
                     outcome="timeout", sql=attempt.sql,
                     detail="SQL execution exceeded the request budget")
        yield sse("error", {"message": "The warehouse query took too long. Please retry.",
                            "retryable": True})
        yield sse("done", {"turn_id": turn_id})
        return
    except ExecutionError as exc:
        audit.record(
            turn_id=turn_id, ctx=ctx, resolved=resolved, route="text_to_sql",
            outcome="execution_error", sql=attempt.sql, detail=exc.detail,
        )
        yield sse("error", {"message": str(exc), "retryable": False})
        yield sse("done", {"turn_id": turn_id})
        return

    if not chart.rows:
        audit.record(
            turn_id=turn_id, ctx=ctx, resolved=resolved, route="text_to_sql",
            outcome="no_matching_rows", sql=attempt.sql, row_count=0,
            duration_ms=int((time.perf_counter() - started) * 1000),
        )
        conversation.append_turn(state, ctx.question, resolved, "refuse", None, 0)
        conversation.save(state)
        yield sse(
            "refusal",
            {
                "route": "refuse",
                "reason": "not_in_data",
                "message": "No records matched that question in the available data.",
                "examples": planner.refusal_examples(resolved, "not_in_data"),
            },
        )
        yield sse("done", {"turn_id": turn_id})
        return

    conversation.append_turn(
        state, ctx.question, resolved, "sql", chart.chart_type, chart.lineage.row_count
    )
    conversation.save(state)
    audit.record(
        turn_id=turn_id, ctx=ctx, resolved=resolved, route="text_to_sql", outcome="answered",
        sql=attempt.sql, row_count=chart.lineage.row_count,
        duration_ms=int((time.perf_counter() - started) * 1000),
        # A PII column may live on an otherwise mixed/internal table (borrower name is
        # denormalised onto loan_account_master), so table-level metadata alone is not
        # sufficient for the audit flag.
        touches_pii=bool(attempt.pii_columns)
        or pii.touches_pii(chart.lineage.source_tables, cat),
    )

    response = AskResponse(
        conversation_id=ctx.conversation_id,
        turn_id=turn_id,
        status="answered",
        chart=chart,
        plan_summary=attempt.explanation,
    )
    yield sse("chart", response.model_dump(mode="json"))
    yield sse("done", {"turn_id": turn_id})


async def _execute_and_emit(
    ctx: AskContext,
    cat: Catalog,
    spec,
    turn_id: str,
    state,
    resolved: str,
    *,
    plan_summary: str,
    started: float,
) -> AsyncIterator[str]:
    try:
        chart = await asyncio.wait_for(
            asyncio.to_thread(
                run_spec, spec, catalog=cat, today=ctx.today, role=ctx.role
            ),
            timeout=_remaining_seconds(started),
        )
    except TimeoutError:
        audit.record(turn_id=turn_id, ctx=ctx, resolved=resolved, route="queryspec",
                     outcome="timeout", detail="query exceeded the request budget")
        yield sse("error", {"message": "The warehouse query took too long. Please retry.",
                            "retryable": True})
        yield sse("done", {"turn_id": turn_id})
        return
    except CompileError as exc:
        audit.record(turn_id=turn_id, ctx=ctx, resolved=resolved, route="queryspec",
                     outcome="refused_by_compiler", detail=str(exc))
        yield sse(
            "refusal",
            {
                "route": "refuse",
                "reason": "not_in_data",
                "message": str(exc),
                "examples": planner.refusal_examples(),
            },
        )
        yield sse("done", {"turn_id": turn_id})
        return
    except ExecutionError as exc:
        logger.error("NLQ execution failed: %s", exc.detail)
        audit.record(turn_id=turn_id, ctx=ctx, resolved=resolved, route="queryspec",
                     outcome="execution_error", detail=exc.detail)
        yield sse("error", {"message": str(exc), "retryable": True})
        yield sse("done", {"turn_id": turn_id})
        return

    yield sse("stage", {"stage": "charting"})

    conversation.append_turn(
        state, ctx.question, resolved, "queryspec", chart.chart_type, chart.lineage.row_count
    )
    conversation.set_anchor(state, spec)
    conversation.save(state)

    audit.record(
        turn_id=turn_id, ctx=ctx, resolved=resolved, route="queryspec", outcome="answered",
        spec=spec, sql=chart.lineage.sql, row_count=chart.lineage.row_count,
        duration_ms=int((time.perf_counter() - started) * 1000),
        touches_pii=any("customer" in t for t in chart.lineage.source_tables),
    )

    response = AskResponse(
        conversation_id=ctx.conversation_id,
        turn_id=turn_id,
        status="answered",
        chart=chart,
        plan_summary=plan_summary,
    )
    yield sse("chart", response.model_dump(mode="json"))
    yield sse("done", {"turn_id": turn_id, "duration_ms": int((time.perf_counter() - started) * 1000)})


async def ask_once(ctx: AskContext, catalog: Catalog | None = None) -> AskResponse:
    """Non-streaming variant, for tests and for the eval harness."""
    cat = catalog or get_catalog()
    payload: dict[str, Any] = {}
    async for frame in ask_stream(ctx, cat):
        event, _, data = frame.partition("\n")
        name = event.removeprefix("event: ").strip()
        body = data.removeprefix("data: ").strip()
        if name in (
            "chart", "analysis", "worklist", "briefing", "clarify", "refusal", "error",
        ):
            payload[name] = json.loads(body)

    if "chart" in payload:
        return AskResponse.model_validate(payload["chart"])
    if "analysis" in payload:
        return AskResponse.model_validate(payload["analysis"])
    if "worklist" in payload:
        return AskResponse.model_validate(payload["worklist"])
    if "briefing" in payload:
        return AskResponse.model_validate(payload["briefing"])
    if "clarify" in payload:
        return AskResponse(
            conversation_id=ctx.conversation_id,
            turn_id="",
            status="clarify",
            clarification=ClarifyPlan.model_validate(payload["clarify"]),
        )
    if "refusal" in payload:
        return AskResponse(
            conversation_id=ctx.conversation_id,
            turn_id="",
            status="refused",
            refusal=RefusalPlan.model_validate(payload["refusal"]),
        )
    raise ExecutionError(payload.get("error", {}).get("message", "the question could not be answered"))
