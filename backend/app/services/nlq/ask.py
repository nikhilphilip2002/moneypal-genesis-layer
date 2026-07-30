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


@dataclass(slots=True)
class AskContext:
    question: str
    conversation_id: str
    user: str = "anonymous"
    role: str = "gicc_policy"
    today: date | None = None


def sse(event: str, data: Any) -> str:
    return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"


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
        outcome = await planner.plan(resolved, catalog=cat)
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
        audit.record(turn_id=turn_id, ctx=ctx, resolved=resolved, route="clarify",
                     outcome="clarify", plan=outcome)
        conversation.append_turn(state, ctx.question, resolved, "clarify", None, 0)
        yield sse("clarify", plan.model_dump(mode="json"))
        yield sse("done", {"turn_id": turn_id})
        return

    if isinstance(plan, RefusalPlan):
        payload = plan.model_dump(mode="json")
        if not payload.get("examples"):
            payload["examples"] = planner.refusal_examples()
        audit.record(turn_id=turn_id, ctx=ctx, resolved=resolved, route="refuse",
                     outcome=plan.reason, plan=outcome)
        conversation.append_turn(state, ctx.question, resolved, "refuse", None, 0)
        yield sse("refusal", payload)
        yield sse("done", {"turn_id": turn_id})
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
        resolved, catalog=cat, allow_pii=pii.may_see_pii(ctx.role)
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
        touches_pii=pii.touches_pii(chart.lineage.source_tables, cat),
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
        chart = run_spec(spec, catalog=cat, today=ctx.today)
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
        if name in ("chart", "clarify", "refusal", "error"):
            payload[name] = json.loads(body)

    if "chart" in payload:
        return AskResponse.model_validate(payload["chart"])
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
