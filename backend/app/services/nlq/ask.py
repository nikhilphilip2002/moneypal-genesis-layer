"""The ask pipeline: question -> plan -> chart, streamed as SSE stages.

Streaming is not decoration. The QuerySpec path takes 1.5-3s and text-to-SQL up to 7s;
showing "Understanding -> Planning -> Querying -> Charting" makes that legible, whereas a
spinner of the same duration reads as a hang.
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from dataclasses import dataclass
from datetime import date
from typing import Any, AsyncIterator

from app.services.nlq import audit, conversation, pii, planner, text_to_sql
from app.services.nlq.catalog import Catalog, get_catalog
from app.services.nlq.compiler import CompileError
from app.services.nlq.contracts import (
    AnalysisPlan,
    AskResponse,
    ClarifyPlan,
    QuerySpecPlan,
    RefusalPlan,
    SqlPlan,
)
from app.services.nlq.executor import ExecutionError
from app.services.nlq.llm import LLMError
from app.services.nlq.pipeline import run_spec, run_sql

logger = logging.getLogger(__name__)

HARD_CEILING_S = 20.0

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
        outcome = await planner.plan(
            resolved, catalog=cat, history_messages=ctx.history_messages or [],
        )
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
        payload["examples"] = planner.refusal_examples()
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
        result = await asyncio.to_thread(
            analysis_service.run, spec, catalog=cat, today=ctx.today, role=ctx.role
        )
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

    attempt = await text_to_sql.generate(
        resolved,
        catalog=cat,
        allow_pii=pii.may_see_pii(ctx.role),
        preferred_tables=plan.tables,
    )

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
        chart = run_sql(
            attempt, question=resolved, role=ctx.role, catalog=cat
        )
    except ExecutionError as exc:
        audit.record(
            turn_id=turn_id, ctx=ctx, resolved=resolved, route="text_to_sql",
            outcome="execution_error", sql=attempt.sql, detail=exc.detail,
        )
        yield sse("error", {"message": str(exc), "retryable": False})
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
        chart = run_spec(spec, catalog=cat, today=ctx.today, role=ctx.role)
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
        if name in ("chart", "analysis", "clarify", "refusal", "error"):
            payload[name] = json.loads(body)

    if "chart" in payload:
        return AskResponse.model_validate(payload["chart"])
    if "analysis" in payload:
        return AskResponse.model_validate(payload["analysis"])
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
