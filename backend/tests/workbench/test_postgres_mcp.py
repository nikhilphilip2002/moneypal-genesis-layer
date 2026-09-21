"""Protocol-level checks for the internal read-only PostgreSQL MCP server."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest
from fastmcp import Client

from app.core.config import settings
from app.mcp import postgres_client, postgres_server
from app.services.nlq.executor import QueryTimeoutError
from app.services.nlq.validator import ValidationError


@pytest.mark.anyio
async def test_health_tool_is_discoverable_and_returns_structured_content(monkeypatch):
    monkeypatch.setattr(
        postgres_server.nlq_db,
        "health",
        lambda: {"status": "ok", "role": "nlq_readonly", "gold_views": 15},
    )

    async with Client(postgres_server.mcp, mode="legacy") as client:
        tools = await client.list_tools()
        result = await client.call_tool("postgres_health", {})

    assert "postgres_health" in {tool.name for tool in tools}
    payload = result.data
    assert payload["success"] is True
    payload = payload["data"]
    assert payload["status"] == "ok"
    assert payload["role"] == "nlq_readonly"


@pytest.mark.anyio
async def test_client_has_a_whole_operation_timeout(monkeypatch):
    class StalledClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            await asyncio.sleep(1)
            return self  # pragma: no cover

        async def __aexit__(self, *args):
            return None

    monkeypatch.setattr(postgres_client, "Client", StalledClient)
    monkeypatch.setattr(settings, "postgres_mcp_timeout_s", 0.001)
    monkeypatch.setattr(postgres_client, "MCP_SHUTDOWN_GRACE_S", 0.0)

    with pytest.raises(postgres_client.PostgresMCPError, match="timed out"):
        await postgres_client.health()


@pytest.mark.anyio
async def test_client_timeout_also_bounds_session_shutdown(monkeypatch):
    class SlowShutdownClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def call_tool(self, *_args, **_kwargs):
            return SimpleNamespace(data={"success": True, "data": {"status": "ok"}})

        async def __aexit__(self, *args):
            await asyncio.sleep(1)

    monkeypatch.setattr(postgres_client, "Client", SlowShutdownClient)
    monkeypatch.setattr(settings, "postgres_mcp_timeout_s", 0.001)
    monkeypatch.setattr(postgres_client, "MCP_SHUTDOWN_GRACE_S", 0.0)

    with pytest.raises(postgres_client.PostgresMCPError, match="timed out"):
        await postgres_client.health()


def test_query_tool_preserves_statement_timeout_code(monkeypatch):
    meta = {
        "workbench_role": "admin",
        "workbench_effective_sources": ["db"],
    }
    checked = SimpleNamespace(
        sql="SELECT value FROM gold.slow_view LIMIT 1",
        tables=["gold.slow_view"],
        pii_columns=[],
        limit_injected=False,
        warnings=[],
    )
    catalog = SimpleNamespace(version="test-catalog")
    monkeypatch.setattr(postgres_server, "get_catalog", lambda: catalog)
    monkeypatch.setattr(postgres_server, "validate", lambda *_args, **_kwargs: checked)
    monkeypatch.setattr(postgres_server.pii, "may_see_pii", lambda _role: True)

    def timed_out(_sql):
        raise QueryTimeoutError(
            "Rewrite it and do not repeat the same SQL.",
            detail="QueryCanceled: canceling statement due to statement timeout",
        )

    monkeypatch.setattr(postgres_server, "execute_raw", timed_out)

    payload = postgres_server._query(checked.sql, meta)

    assert payload["success"] is False
    assert payload["error"]["code"] == "QUERY_TIMEOUT"
    assert payload["error"]["retryable"] is True


def test_query_tool_classifies_sql_validation_as_compile_rejected(monkeypatch):
    meta = {
        "workbench_role": "admin",
        "workbench_effective_sources": ["db"],
    }
    catalog = SimpleNamespace(version="test-catalog")
    monkeypatch.setattr(postgres_server, "get_catalog", lambda: catalog)
    monkeypatch.setattr(postgres_server.pii, "may_see_pii", lambda _role: True)

    def rejected(*_args, **_kwargs):
        raise ValidationError("SELECT * is not allowed; name the columns explicitly")

    monkeypatch.setattr(postgres_server, "validate", rejected)

    payload = postgres_server._query("SELECT * FROM gold.agents", meta)

    assert payload["success"] is False
    assert payload["error"]["code"] == "COMPILE_REJECTED"
    assert payload["error"]["retryable"] is True
    assert "name the columns explicitly" in payload["error"]["message"]
