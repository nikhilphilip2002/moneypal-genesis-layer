"""In-process FastMCP server for governed Workbench tools."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from fastmcp import Context, FastMCP
from fastmcp.tools import ToolResult
from pydantic import Field

from app.mcp.results import success
from app.services.nlq.catalog import get_catalog
from app.services.workbench.access import SourceAccessDenied, build_policy
from app.services.workbench.agent_contracts import (
    FinalSynthesis,
    FinishWithoutDataArguments,
    SearchCuratedKnowledgeArguments,
    SearchPublicWebArguments,
    VisualizationAggregation,
    VisualizationChartType,
    VisualizeQueryResultArguments,
)


mcp = FastMCP(
    "Moneypal Workbench",
    instructions=(
        "Governed in-process tools for curated knowledge, public web evidence, "
        "query-result visualization, and terminal Workbench responses."
    ),
)


def _trusted_meta(ctx: Context) -> dict[str, Any]:
    request_context = ctx.request_context
    meta = request_context.meta if request_context is not None else None
    if meta is None:
        return {}
    if isinstance(meta, dict):
        return dict(meta)
    return meta.model_dump(exclude_none=True)


def _execution_context(ctx: Context):
    """Rebuild and verify the request policy from backend-supplied metadata."""
    from app.services.workbench.agent_executor import AgentExecutionContext

    meta = _trusted_meta(ctx)
    role = str(meta.get("workbench_role") or "")
    external_enabled = bool(meta.get("workbench_external_sources_enabled"))
    pinned_source = meta.get("workbench_pinned_source")
    if pinned_source is not None:
        pinned_source = str(pinned_source)
    policy = build_policy(
        role=role,
        external_sources_enabled=external_enabled,
        pinned_source=pinned_source,
    )
    supplied_sources = tuple(meta.get("workbench_effective_sources") or ())
    if supplied_sources != policy.effective_sources:
        raise SourceAccessDenied("source policy metadata does not match current policy")
    supplied_version = str(meta.get("source_policy_version") or "")
    if supplied_version != policy.version:
        raise SourceAccessDenied("source policy version does not match current policy")
    return AgentExecutionContext(
        user=str(meta.get("workbench_user") or ""),
        role=role,
        conversation_id=str(meta.get("workbench_conversation_id") or ""),
        turn_id=str(meta.get("workbench_turn_id") or ""),
        source_policy=policy,
        deadline_s=float(meta.get("workbench_deadline_s") or 0.001),
        question=str(meta.get("workbench_question") or ""),
        catalog=get_catalog(),
        catalog_version=str(meta.get("workbench_catalog_version") or ""),
        private_entities=tuple(meta.get("workbench_private_entities") or ()),
        query_id=(str(meta["workbench_query_id"]) if meta.get("workbench_query_id") else None),
        attempt_id=(
            str(meta["workbench_attempt_id"])
            if meta.get("workbench_attempt_id") else None
        ),
    )


def _card_data(card: Any) -> dict[str, Any]:
    payload = card.as_dict()
    payload["sources"] = list(card.sources)
    return {"kind": "card", "card": payload}


@mcp.tool(
    description=(
        "Search policy documents, definitions, catalog documentation, macro, competitive, "
        "or regulatory evidence. Never use this to query customer, KYC, loan, agent, or "
        "other database rows named in Gold TABLE hints."
    )
)
async def search_curated_knowledge(
    domain: Literal["concepts", "macro", "competitive", "regulatory"],
    query: Annotated[str, Field(min_length=1, max_length=1000)],
    ctx: Context,
) -> dict[str, Any]:
    from app.services.workbench.agent_executor import _search_curated

    execution_ctx = _execution_context(ctx)
    args = SearchCuratedKnowledgeArguments(domain=domain, query=query)
    execution_ctx.source_policy.require({
        "concepts": "knowledge",
        "macro": "macro",
        "competitive": "competitive",
        "regulatory": "regulatory",
    }[domain])
    return success(_card_data(await _search_curated(args, execution_ctx)))


@mcp.tool(
    description="Search the live public web; never include private bank or customer data."
)
async def search_public_web(
    search_query: Annotated[str, Field(min_length=1, max_length=500)],
    ctx: Context,
) -> dict[str, Any]:
    from app.services.workbench.agent_executor import _search_public_web

    execution_ctx = _execution_context(ctx)
    execution_ctx.source_policy.require("web")
    args = SearchPublicWebArguments(search_query=search_query)
    return success(_card_data(await _search_public_web(args, execution_ctx)))


@mcp.tool(description="Create a visualization from a successful query result.")
async def visualize_query_result(
    query_id: str,
    chart_type: VisualizationChartType,
    x: str | None,
    y: list[str],
    series: str | None,
    aggregation: Annotated[
        VisualizationAggregation,
        Field(
            description=(
                "Use none when each x/series pair is already aggregated; otherwise choose "
                "how to combine multiple y values for the same x/series pair."
            )
        ),
    ],
    ctx: Context,
) -> dict[str, Any]:
    from app.services.workbench.agent_executor import _visualize_query_result

    execution_ctx = _execution_context(ctx)
    execution_ctx.source_policy.require("db")
    args = VisualizeQueryResultArguments(
        query_id=query_id,
        chart_type=chart_type,
        x=x,
        y=y,
        series=series,
        aggregation=aggregation,
    )
    return success(_card_data(await _visualize_query_result(args, execution_ctx)))


@mcp.tool(
    description=(
        "End the turn with a clarifying question or governed refusal when no data tool "
        "should run."
    )
)
async def finish_without_data(
    outcome: Literal["clarify", "refuse"],
    message: Annotated[str, Field(min_length=1, max_length=500)],
    suggestions: Annotated[list[str], Field(max_length=3)],
    reason_code: Literal[
        "out_of_scope", "not_in_data", "predictive", "advice", "unsafe"
    ] | None = None,
) -> dict[str, Any]:
    parsed = FinishWithoutDataArguments(
        outcome=outcome,
        message=message,
        suggestions=suggestions,
        reason_code=reason_code,
    )
    return success({"kind": "terminal", "terminal": parsed.model_dump(mode="json")})


@mcp.tool(
    description=(
        "Select one successful database query from this conversation, choose its view, and optionally "
        "add concise insights. The backend infers the view fields from the query result. "
        "It must be the only call in the response."
    )
)
async def submit_final_answer(
    insights: Annotated[str, Field(max_length=20_000)],
    query_id: Annotated[int, Field(ge=1)],
    view: VisualizationChartType,
) -> ToolResult:
    parsed = FinalSynthesis(
        insights=insights,
        query_id=query_id,
        view=view,
    )
    structured = success({
        "kind": "terminal",
        "terminal": {
            "outcome": "answer",
            "synthesis": parsed.model_dump(mode="json"),
        },
    })
    return ToolResult(
        content={"success": True},
        structured_content=structured,
    )


__all__ = ["mcp"]
