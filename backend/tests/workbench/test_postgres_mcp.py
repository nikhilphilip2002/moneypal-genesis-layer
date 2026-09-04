"""Protocol-level checks for the internal read-only PostgreSQL MCP server."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

import pytest

from app.core.config import settings
from app.mcp import postgres_client, postgres_server


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


@pytest.mark.anyio
async def test_client_has_a_whole_operation_timeout(monkeypatch):
    @asynccontextmanager
    async def stalled_transport(*args, **kwargs):
        await asyncio.sleep(1)
        yield "read", "write", lambda: None  # pragma: no cover

    monkeypatch.setattr(postgres_client, "streamablehttp_client", stalled_transport)
    monkeypatch.setattr(settings, "postgres_mcp_timeout_s", 0.001)
    monkeypatch.setattr(postgres_client, "MCP_SHUTDOWN_GRACE_S", 0.0)

    with pytest.raises(postgres_client.PostgresMCPError, match="timed out"):
        await postgres_client.health()
