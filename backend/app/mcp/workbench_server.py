"""Workbench FastMCP server exposing governed workbench extensions.

Provides dedicated lookup_customer_profile tool classified under RUNTIME_TOOL_POLICIES.
"""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from app.services.workbench.customer import lookup_customer_profile as _lookup_customer

mcp = FastMCP(
    "Moneypal Workbench Tools",
    instructions=(
        "Governed extension tools for Moneypal Workbench, including customer profile lookups."
    ),
    host="0.0.0.0",
    port=8002,
    streamable_http_path="/mcp",
    json_response=True,
    stateless_http=True,
)

RUNTIME_TOOL_POLICIES: dict[str, str] = {
    "lookup_customer_profile": "customer",
}


@mcp.tool()
async def lookup_customer_profile(customer_id: str) -> dict[str, Any]:
    """Look up an external customer profile by exact canonical customer ID.

    Never use this without an explicitly identified customer ID. Returns approved
    records from External_customer_details with full provenance citations.
    """
    card = await _lookup_customer(customer_id)
    return card.as_dict()


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
