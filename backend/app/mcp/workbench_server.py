"""In-process FastMCP server for governed Workbench tools."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from fastmcp import Context, FastMCP
from fastmcp.tools import ToolResult
from pydantic import Field

from app.core.tool_names import (
    ASK_CLARIFICATION,
    READ_TOOL_OUTPUT,
    REFUSE_REQUEST,
    SEARCH_CURATED_KNOWLEDGE,
    SEARCH_PUBLIC_WEB,
    VISUALIZE_RESULT,
)
from app.mcp.results import success
from app.services.nlq.catalog import get_catalog
from app.services.workbench.access import SourceAccessDenied, build_policy
from app.services.workbench.agent_contracts import (
    RefusalReason,
    SearchCuratedKnowledgeArguments,
    SearchPublicWebArguments,
    VisualizationChartType,
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
        raise SourceAccessDenied(
            "source policy metadata does not match current policy"
        )
    supplied_version = str(meta.get("source_policy_version") or "")
    if supplied_version != policy.version:
        raise SourceAccessDenied(
            "source policy version does not match current policy"
        )
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
        query_id=(
            str(meta["workbench_query_id"])
            if meta.get("workbench_query_id")
            else None
        ),
        attempt_id=(
            str(meta["workbench_attempt_id"])
            if meta.get("workbench_attempt_id")
            else None
        ),
    )


def _card_data(card: Any) -> dict[str, Any]:
    payload = card.as_dict()
    payload["sources"] = list(card.sources)
    return {"kind": "card", "card": payload}


@mcp.tool(
    name=SEARCH_CURATED_KNOWLEDGE,
    description=(
        "Search policy documents, definitions, catalog documentation, macro, competitive, "
        "or regulatory evidence. Never use this to query customer, KYC, loan, agent, or "
        "other database rows named in Gold TABLE hints."
    ),
)
async def search_curated_knowledge(
    domain: Literal["concepts", "macro", "competitive", "regulatory"],
    query: Annotated[str, Field(min_length=1, max_length=1000)],
    ctx: Context,
) -> dict[str, Any]:
    from app.services.workbench.agent_executor import _search_curated

    execution_ctx = _execution_context(ctx)
    args = SearchCuratedKnowledgeArguments(domain=domain, query=query)
    execution_ctx.source_policy.require(
        {
            "concepts": "knowledge",
            "macro": "macro",
            "competitive": "competitive",
            "regulatory": "regulatory",
        }[domain]
    )
    return success(_card_data(await _search_curated(args, execution_ctx)))


@mcp.tool(
    name=SEARCH_PUBLIC_WEB,
    description="Search the live public web; never include private bank or customer data.",
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


@mcp.tool(
    name=READ_TOOL_OUTPUT,
    description=(
        "Continue an oversized tool result by its output ID and character offset. "
        "Page size is controlled by the server."
    ),
)
async def read_tool_output(
    id: Annotated[str, Field(min_length=1)],
    offset: Annotated[int, Field(ge=0, strict=True)],
    ctx: Context,
) -> dict[str, Any]:
    from app.services.workbench import history

    execution_ctx = _execution_context(ctx)
    page = history.read_tool_output(
        execution_ctx.conversation_id,
        execution_ctx.user,
        id,
        offset,
        execution_ctx.source_policy,
    )
    return success({"kind": "tool_output", "page": page})


@mcp.tool(name=VISUALIZE_RESULT)
async def visualize_result(
    query_id: Annotated[
        int,
        Field(ge=1, description="ID of a successful stored database query."),
    ],
    view: Annotated[
        VisualizationChartType,
        Field(
            description="Visualization type; use table when no chart is suitable."
        ),
    ],
    ctx: Context,
) -> ToolResult:
    """Render a query result using all stored rows, including rows omitted from previews.

    Use for query results. Continue explaining in ordinary assistant content afterward.
    """
    _execution_context(ctx).source_policy.require("db")
    return ToolResult(
        content={"success": True},
        structured_content=success(
            {"kind": "visual", "visual": {"query_id": query_id, "view": view}}
        ),
    )


@mcp.tool(name=ASK_CLARIFICATION)
async def ask_clarification(
    question: Annotated[
        str,
        Field(
            min_length=1,
            max_length=500,
            description="Question shown to the user.",
        ),
    ],
    suggestions: Annotated[
        list[str], Field(max_length=3, description="Suggested replies.")
    ],
) -> ToolResult:
    """Ask for missing information, end the turn, and wait for the user's reply."""
    return ToolResult(
        content={"success": True},
        structured_content=success(
            {
                "kind": "terminal",
                "terminal": {
                    "outcome": "clarify",
                    "message": question,
                    "suggestions": suggestions,
                },
            }
        ),
    )


@mcp.tool(name=REFUSE_REQUEST)
async def refuse_request(
    message: Annotated[
        str,
        Field(
            min_length=1,
            max_length=500,
            description="Refusal shown to the user.",
        ),
    ],
    reason_code: Annotated[
        RefusalReason, Field(description="Reason for declining the request.")
    ],
) -> ToolResult:
    """Display a refusal and end the turn without requiring a visualization."""
    return ToolResult(
        content={"success": True},
        structured_content=success(
            {
                "kind": "terminal",
                "terminal": {
                    "outcome": "refuse",
                    "message": message,
                    "reason_code": reason_code,
                },
            }
        ),
    )


__all__ = ["mcp"]
