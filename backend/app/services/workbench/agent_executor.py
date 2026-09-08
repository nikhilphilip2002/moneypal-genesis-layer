"""Governed execution boundary for validated native agent calls."""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Awaitable, Callable

from pydantic import BaseModel

from app.services.nlq import governed_execution, pii, text_to_sql
from app.services.nlq.catalog import Catalog, get_catalog
from app.services.nlq.contracts import LookupPlan
from app.services.nlq.llm import NativeToolCall
from app.services.nlq.pipeline import run_sql
from app.services.workbench import facts
from app.services.workbench.access import SourceAccessPolicy
from app.services.workbench.agent_contracts import (
    CreateWorklistArguments,
    FinishWithoutDataArguments,
    GenerateBriefingArguments,
    InspectLoanCatalogArguments,
    LookupRecordsArguments,
    QueryMetricsArguments,
    RunAnalysisArguments,
    RunValidatedQueryArguments,
    SearchCuratedKnowledgeArguments,
    SearchPublicWebArguments,
)
from app.services.workbench.agent_tools import get_agent_tool, validate_agent_arguments
from app.services.workbench.results import SourceResult


class AgentExecutionError(RuntimeError):
    code = "SOURCE_UNAVAILABLE"


class AgentToolTimeout(AgentExecutionError):
    code = "TOOL_TIMEOUT"


class AgentCompileRejected(AgentExecutionError):
    code = "COMPILE_REJECTED"


@dataclass(frozen=True, slots=True)
class AgentExecutionContext:
    user: str
    role: str
    conversation_id: str
    turn_id: str
    source_policy: SourceAccessPolicy
    deadline_s: float
    catalog: Catalog | None = None
    catalog_version: str = ""
    today: date | None = None
    data_access: str | None = None
    private_entities: tuple[str, ...] = ()
    deadline_started_at: float = field(default_factory=time.monotonic)


@dataclass(slots=True)
class ExecutedAgentCall:
    call: NativeToolCall
    card: SourceResult | None = None
    terminal: dict[str, Any] | None = None
    error: dict[str, Any] | None = None

    def replay_payload(self) -> dict[str, Any]:
        if self.error is not None:
            return {"status": "error", **self.error}
        if self.terminal is not None:
            return {"status": "terminal", **self.terminal}
        assert self.card is not None
        return {
            "status": "ok",
            "source": self.card.source,
            "card_type": self.card.card_type,
            "card_reference": self.call.id,
            "payload": self.card.payload,
            "summary": self.card.summary,
            "complete": self.card.complete,
            "limitation": self.card.limitation,
            "citations": self.card.sources,
            "evidence": self.card.evidence_dicts(),
            "lineage": self.card.lineage,
            "facts": [
                {
                    "id": fact.id,
                    "label": fact.label,
                    "value": str(fact.value),
                    "display_value": fact.display_value,
                    "unit": fact.unit,
                    "period": fact.period,
                    "dimensions": dict(fact.dimensions),
                }
                for fact in facts.from_results([self.card], max_per_result=100)
            ],
        }

    def replay_message(self) -> dict[str, str]:
        return {
            "role": "tool",
            "tool_call_id": self.call.id,
            "content": json.dumps(self.replay_payload(), default=str, separators=(",", ":")),
        }


def _chart_result(chart) -> SourceResult:
    lineage = chart.lineage.model_dump(mode="json")
    return SourceResult(
        source="db",
        card_type="chart",
        payload=chart.model_dump(mode="json"),
        summary=chart.summary,
        sensitive=True,
        lineage=lineage,
    )


async def _query_metrics(args: QueryMetricsArguments, ctx: AgentExecutionContext) -> SourceResult:
    chart = await asyncio.to_thread(
        governed_execution.metrics,
        args,
        catalog=ctx.catalog,
        today=ctx.today,
        role=ctx.role,
    )
    return _chart_result(chart)


async def _lookup_records(args: LookupRecordsArguments, ctx: AgentExecutionContext) -> SourceResult:
    plan = LookupPlan(route="lookup", confidence=1.0, **args.model_dump())
    result = await asyncio.to_thread(
        governed_execution.records, plan, role=ctx.role, catalog=ctx.catalog,
    )
    if result.clarification is not None:
        return SourceResult(
            source="db", card_type="clarify",
            payload=result.clarification.model_dump(mode="json"),
        )
    if result.no_match or result.chart is None:
        return SourceResult(
            source="db", card_type="refusal",
            payload={
                "reason": "not_in_data",
                "message": "No customer or loan records matched that lookup.",
            },
        )
    return _chart_result(result.chart)


async def _run_analysis(args: RunAnalysisArguments, ctx: AgentExecutionContext) -> SourceResult:
    result = await asyncio.to_thread(
        governed_execution.reviewed_analysis,
        args.analysis_id,
        catalog=ctx.catalog,
        period=args.period,
        filters=args.filters,
        today=ctx.today,
        role=ctx.role,
    )
    return SourceResult(
        source="db", card_type="analysis", payload=result.model_dump(mode="json"),
        summary=result.headline, sensitive=True,
    )


async def _create_worklist(args: CreateWorklistArguments, ctx: AgentExecutionContext) -> SourceResult:
    result = await asyncio.to_thread(
        governed_execution.reviewed_worklist,
        args.worklist_id,
        catalog=ctx.catalog,
        as_of=ctx.today,
        filters=args.filters,
        limit=args.limit,
        role=ctx.role,
    )
    alerts = sum(1 for item in result.items if item.severity == "alert")
    return SourceResult(
        source="db", card_type="worklist", payload=result.model_dump(mode="json"),
        summary=f"{result.title}: {len(result.items)} accounts, {alerts} needing immediate action.",
        sensitive=True,
    )


async def _generate_briefing(args: GenerateBriefingArguments, ctx: AgentExecutionContext) -> SourceResult:
    result = await asyncio.to_thread(
        governed_execution.reviewed_briefing,
        args.persona_id,
        catalog=ctx.catalog,
        today=ctx.today,
        role=ctx.role,
    )
    return SourceResult(
        source="db", card_type="briefing", payload=result.model_dump(mode="json"),
        summary=result.headline, sensitive=True,
    )


async def _run_validated_query(
    args: RunValidatedQueryArguments, ctx: AgentExecutionContext,
) -> SourceResult:
    attempt = await text_to_sql.generate(
        args.intent,
        catalog=ctx.catalog,
        allow_pii=pii.may_see_pii(ctx.role),
        preferred_tables=args.tables,
        allow_reviewed_shortcuts=False,
    )
    if not attempt.validated:
        raise AgentCompileRejected("validated query was rejected by the SQL safety gate")
    chart = await asyncio.to_thread(
        run_sql, attempt, question=args.intent, role=ctx.role, catalog=ctx.catalog,
    )
    result = _chart_result(chart)
    result.lineage = {
        **(result.lineage or {}),
        "text_to_sql": {
            "model": attempt.model,
            "provider": attempt.provider,
            "attempts": attempt.attempts,
            "trace": attempt.trace,
        },
    }
    return result


async def _inspect_loan_catalog(
    args: InspectLoanCatalogArguments, ctx: AgentExecutionContext,
) -> SourceResult:
    from app.services.nlq.catalog.retrieval import retrieve

    catalog = ctx.catalog or get_catalog()
    # Lexical catalog inspection is a small in-memory scan. Keeping it local also avoids
    # consuming a worker-thread slot needed by warehouse calls.
    found = retrieve(args.topic, catalog=catalog, use_vectors=False)
    selected_tables = list(dict.fromkeys([*args.tables, *found.tables]))[:8]
    selected_table_set = set(selected_tables)
    metrics = [
        {
            "id": metric.id,
            "label": metric.label,
            "unit": metric.unit,
            "grain": metric.grain,
            "base_table": metric.base_table,
            "synonyms": list(metric.synonyms),
            "description": metric.description,
            "caveat": metric.caveat,
        }
        for metric_id in found.metrics
        if (metric := catalog.metrics.get(metric_id)) is not None
    ]
    dimensions = [
        {
            "id": dimension.id,
            "label": dimension.label,
            "type": dimension.type,
            "table": dimension.table,
            "column": dimension.column,
            "synonyms": list(dimension.synonyms),
            "description": dimension.description,
        }
        for dimension_id in found.dimensions
        if (dimension := catalog.dimensions.get(dimension_id)) is not None
    ]
    tables = [
        {
            "name": table_name,
            "label": table.label,
            "grain": table.grain,
            "description": table.description,
            "coverage_warning": table.coverage_warning,
            "columns": [
                {
                    "id": column.id,
                    "name": column.column,
                    "label": column.label,
                    "unit": column.unit,
                    "synonyms": list(column.synonyms),
                    "sensitivity": column.sensitivity,
                }
                for column in catalog.columns_for(table_name)
            ],
        }
        for table_name in selected_tables
        if (table := catalog.table_by_name(table_name)) is not None
    ]
    joins = [
        {
            "id": join.id,
            "left": join.left,
            "right": join.right,
            "on": [list(pair) for pair in join.on],
            "cardinality": join.cardinality,
            "description": join.description,
        }
        for join in catalog.joins
        if join.left in selected_table_set and join.right in selected_table_set
    ]
    payload = {
        "topic": args.topic,
        "catalog_version": catalog.version,
        "retrieval_mode": found.mode,
        "metrics": metrics,
        "dimensions": dimensions,
        "tables": tables,
        "joins": joins,
        "enum_values": found.enum_values,
    }
    return SourceResult(
        source="schema",
        card_type="catalog",
        payload=payload,
        summary=(
            f"Catalog metadata: {len(metrics)} metrics, {len(dimensions)} dimensions, "
            f"{len(tables)} tables, and {len(joins)} declared joins."
        ),
        lineage={"catalog_version": catalog.version},
    )


async def _search_curated(
    args: SearchCuratedKnowledgeArguments, ctx: AgentExecutionContext,
) -> SourceResult:
    from app.services.workbench import nodes

    handlers: dict[str, Callable[[], Awaitable[SourceResult]]] = {
        "concepts": lambda: nodes.run_knowledge(args.query),
        "schema": lambda: nodes.run_schema(args.query, access_mode=ctx.data_access),
        "macro": lambda: nodes.run_macro(args.query, policy=ctx.source_policy),
        "competitive": lambda: nodes.run_competitive(args.query, policy=ctx.source_policy),
        "regulatory": lambda: nodes.run_regulatory(args.query, policy=ctx.source_policy),
    }
    return await handlers[args.domain]()


async def _search_public_web(
    args: SearchPublicWebArguments, ctx: AgentExecutionContext,
) -> SourceResult:
    from app.services.workbench import nodes

    return await nodes.run_web(
        args.search_query, user=ctx.user, policy=ctx.source_policy,
        raise_policy_denials=True,
        private_entities=ctx.private_entities,
    )


Handler = Callable[[Any, AgentExecutionContext], Awaitable[SourceResult]]
_HANDLERS: dict[str, Handler] = {
    "query_metrics": _query_metrics,
    "lookup_records": _lookup_records,
    "run_analysis": _run_analysis,
    "create_worklist": _create_worklist,
    "generate_briefing": _generate_briefing,
    "run_validated_query": _run_validated_query,
    "inspect_loan_catalog": _inspect_loan_catalog,
    "search_curated_knowledge": _search_curated,
    "search_public_web": _search_public_web,
}


async def execute_agent_call(
    call: NativeToolCall, ctx: AgentExecutionContext,
) -> ExecutedAgentCall:
    """Validate, reauthorize, bound, and execute exactly one native call."""
    catalog = ctx.catalog or get_catalog()
    parsed: BaseModel = validate_agent_arguments(
        call.name, call.arguments, policy=ctx.source_policy, catalog=catalog,
    )
    if isinstance(parsed, FinishWithoutDataArguments):
        return ExecutedAgentCall(
            call=call,
            terminal=parsed.model_dump(mode="json"),
        )

    tool = get_agent_tool(call.name)
    handler = _HANDLERS[tool.handler_key]
    remaining = ctx.deadline_s - (time.monotonic() - ctx.deadline_started_at)
    timeout = min(tool.timeout_s, max(0.001, remaining))
    try:
        async with asyncio.timeout(timeout):
            card = await handler(parsed, ctx)
    except TimeoutError as exc:
        raise AgentToolTimeout(f"{call.name} exceeded its execution deadline") from exc
    if card.card_type == "error":
        return ExecutedAgentCall(
            call=call,
            card=card,
            error={
                "code": str(card.payload.get("code") or "SOURCE_UNAVAILABLE"),
                "message": str(card.payload.get("message") or "Source unavailable.")[:500],
            },
        )
    if card.card_type == "refusal" and card.payload.get("reason") == "not_in_data":
        return ExecutedAgentCall(
            call=call,
            card=card,
            error={
                "code": "NO_MATCHING_ROWS",
                "message": str(card.payload.get("message") or "No matching rows.")[:500],
            },
        )
    return ExecutedAgentCall(call=call, card=card)


__all__ = [
    "AgentExecutionContext",
    "AgentExecutionError",
    "AgentCompileRejected",
    "AgentToolTimeout",
    "ExecutedAgentCall",
    "execute_agent_call",
]
