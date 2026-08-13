"""Read-only PostgreSQL MCP server for Moneypal Workbench.

The server deliberately exposes domain tools instead of unrestricted SQL. The NLQ tool
still plans against the governed semantic catalog, validates generated SQL, applies row and
statement limits, and connects as `nlq_readonly`. MCP changes the integration boundary; it
does not weaken the database boundary.
"""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from app.services import db_schema
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
    """Check the dedicated read-only PostgreSQL role and silver-schema availability."""
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
) -> dict[str, Any]:
    """Retrieve a read-only slice of the Enterprise Curiosity Graph."""
    return db_schema.get_db_schema_graph(
        search_term=search or None,
        entity_type=entity_type or "all",
        view_level=view_level or "executive",
        zonal_id=zonal_id or None,
        manager_id=manager_id or None,
        agent_id=agent_id or None,
        customer_id=customer_id or None,
        month=month or None,
        limit=max(1, min(limit, 100)),
    )


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
