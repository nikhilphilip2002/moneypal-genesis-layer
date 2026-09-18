"""Protocol-level checks for the internal read-only PostgreSQL MCP server."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from types import SimpleNamespace

import pytest

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


def test_query_tool_preserves_statement_timeout_code(monkeypatch):
    class Meta:
        def model_dump(self, **_kwargs):
            return {
                "workbench_role": "admin",
                "workbench_effective_sources": ["db"],
            }

    ctx = SimpleNamespace(request_context=SimpleNamespace(meta=Meta()))
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

    payload = postgres_server.query(checked.sql, ctx)

    assert payload["status"] == "error"
    assert payload["code"] == "QUERY_TIMEOUT"
    assert payload["retryable"] is True


def test_query_tool_classifies_sql_validation_as_compile_rejected(monkeypatch):
    class Meta:
        def model_dump(self, **_kwargs):
            return {
                "workbench_role": "admin",
                "workbench_effective_sources": ["db"],
            }

    ctx = SimpleNamespace(request_context=SimpleNamespace(meta=Meta()))
    catalog = SimpleNamespace(version="test-catalog")
    monkeypatch.setattr(postgres_server, "get_catalog", lambda: catalog)
    monkeypatch.setattr(postgres_server.pii, "may_see_pii", lambda _role: True)

    def rejected(*_args, **_kwargs):
        raise ValidationError("SELECT * is not allowed; name the columns explicitly")

    monkeypatch.setattr(postgres_server, "validate", rejected)

    payload = postgres_server.query("SELECT * FROM gold.agents", ctx)

    assert payload["status"] == "error"
    assert payload["code"] == "COMPILE_REJECTED"
    assert payload["retryable"] is True
    assert "name the columns explicitly" in payload["message"]
