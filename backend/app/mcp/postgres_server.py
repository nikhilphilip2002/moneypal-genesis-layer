"""Read-only PostgreSQL MCP server for Moneypal Workbench.

The server deliberately exposes domain tools instead of unrestricted SQL. The NLQ tool
still plans against the governed semantic catalog, validates generated SQL, applies row and
statement limits, and connects as `nlq_readonly`. MCP changes the integration boundary; it
does not weaken the database boundary.
"""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from app.services.curiosity_graph import get_curiosity_graph
from app.services.nlq import db as nlq_db
from app.services.nlq.ask import AskContext, ask_once


mcp = FastMCP(
    "Moneypal PostgreSQL",
    instructions=(
        "Read-only tools for governed loan-book analytics and the Enterprise Curiosity "
        "Graph. Never invent SQL or bypass the semantic catalog."
    ),
    host="0.0.0.0",
    port=8001,
    streamable_http_path="/mcp",
    json_response=True,
    stateless_http=True,
)


@mcp.tool()
def postgres_health() -> dict[str, Any]:
    """Check the dedicated read-only PostgreSQL role and governed Gold-view availability."""
    return nlq_db.health()


@mcp.tool()
async def ask_loan_book(
    question: str,
    conversation_id: str,
    user: str = "anonymous",
    role: str = "gicc_policy",
    history_messages: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    """Answer a governed loan-book question and return its chart, lineage, or refusal."""
    response = await ask_once(AskContext(
        question=question,
        conversation_id=conversation_id,
        user=user,
        role=role,
        history_messages=history_messages or [],
    ))
    return response.model_dump(mode="json")


@mcp.tool()
def curiosity_graph(
    search: str = "",
    entity_type: str = "all",
    view_level: str = "executive",
    zonal_id: str = "",
    manager_id: str = "",
    agent_id: str = "",
    customer_id: str = "",
    month: str = "",
    limit: int = 40,
    level: str = "",
    product_code: str = "",
    branch_code: str = "",
    scheme_code: str = "",
    agent_code: str = "",
    weight_by: str = "borrowers",
    offset: int = 0,
) -> dict[str, Any]:
    """Retrieve a read-only slice of the Enterprise Information Graph."""
    effective_level = level or {"executive": "portfolio", "zonal": "product", "manager": "branch"}.get(
        view_level or "executive", view_level or "portfolio"
    )
    return get_curiosity_graph(
        level=effective_level,
        product_code=product_code or (zonal_id or "").removeprefix("product:") or None,
        branch_code=branch_code or (manager_id or "").removeprefix("branch:") or None,
        scheme_code=scheme_code or None,
        agent_code=agent_code or (agent_id or "").removeprefix("agent:") or None,
        customer_id=customer_id or None,
        month=month or None,
        weight_by=weight_by,
        limit=max(1, min(limit, 100)),
        offset=max(0, offset),
    )


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
