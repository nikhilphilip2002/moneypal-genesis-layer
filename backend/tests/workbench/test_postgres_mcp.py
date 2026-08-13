"""Protocol-level checks for the internal read-only PostgreSQL MCP server."""

from __future__ import annotations

import pytest

from app.mcp import postgres_server


@pytest.mark.anyio
async def test_health_tool_is_discoverable_and_returns_structured_content(monkeypatch):
    monkeypatch.setattr(
        postgres_server.nlq_db,
        "health",
        lambda: {"status": "ok", "role": "nlq_readonly", "gold_views": 15},
    )

    tools = await postgres_server.mcp.list_tools()
    result = await postgres_server.mcp.call_tool("postgres_health", {})

    assert "postgres_health" in {tool.name for tool in tools}
    assert isinstance(result, tuple)
    _content, payload = result
    assert payload["status"] == "ok"
    assert payload["role"] == "nlq_readonly"
