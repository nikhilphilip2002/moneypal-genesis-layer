"""Protocol-level checks for the internal read-only PostgreSQL MCP server."""

from __future__ import annotations

import asyncio
from contextlib import contextmanager
from types import SimpleNamespace
from typing import Any

import pytest
import sqlglot
from fastmcp import Client

from app.core.config import settings
from app.mcp import postgres_client, postgres_server
from app.services.nlq import executor
from app.services.nlq.executor import QueryTimeoutError
from app.services.nlq.validator import ValidationError


@pytest.mark.parametrize(
    "sql, available_rows, expected_rows, expected_limit, truncated",
    [
        ("SELECT loan_account_number FROM gold.loan_accounts", 0, 0, 5001, False),
        ("SELECT loan_account_number FROM gold.loan_accounts", 4999, 4999, 5001, False),
        ("SELECT loan_account_number FROM gold.loan_accounts", 5000, 5000, 5001, False),
        ("SELECT loan_account_number FROM gold.loan_accounts", 8000, 5000, 5001, True),
        ("SELECT loan_account_number FROM gold.loan_accounts LIMIT 10", 8000, 10, 10, False),
        ("SELECT loan_account_number FROM gold.loan_accounts LIMIT 5000", 8000, 5000, 5000, False),
        ("SELECT COUNT(*) AS total FROM gold.loan_accounts", 8000, 1, 5001, False),
        (
            "WITH loans AS (SELECT loan_account_number FROM gold.loan_accounts) "
            "SELECT loan_account_number FROM loans",
            8000, 5000, 5001, True,
        ),
        (
            "SELECT loan_account_number FROM gold.loan_accounts UNION ALL "
            "SELECT loan_account_number FROM gold.loan_accounts",
            8000, 5000, 5001, True,
        ),
    ],
)
def test_query_detects_incomplete_automatic_limits(
    monkeypatch, sql, available_rows, expected_rows, expected_limit, truncated
):
    executed_sql = []
    explained_sql = []

    class Cursor:
        description = [("total" if "COUNT(*)" in sql else "loan_account_number",)]

        def execute(self, statement):
            executed_sql.append(statement)

        def fetchall(self):
            limit = int(
                sqlglot.parse_one(executed_sql[-1], read="postgres")
                .args["limit"].expression.this
            )
            if "COUNT(*)" in sql:
                return [(available_rows,)]
            return [(index,) for index in range(min(available_rows, limit))]

    class Connection:
        def rollback(self):
            pass

    @contextmanager
    def readonly_cursor():
        yield Connection(), Cursor()

    def explain(_conn, _cur, statement, _params):
        explained_sql.append(statement)
        return 1.0

    monkeypatch.setattr(executor.nlq_db, "readonly_cursor", readonly_cursor)
    monkeypatch.setattr(executor, "_explain", explain)
    payload = postgres_server._query(
        sql,
        {"workbench_role": "admin", "workbench_effective_sources": ["db"]},
    )

    assert payload["success"] is True
    data = payload["data"]
    assert data["row_count"] == expected_rows
    assert len(data["rows"]) == expected_rows
    assert data["truncated"] is truncated
    assert data["limit_injected"] is ("LIMIT" not in sql)
    assert bool(data["warnings"]) is truncated
    if truncated:
        assert "More rows match the query." in data["warnings"][0]
        assert data["rows"][-1] == {"loan_account_number": 4999}
    if "COUNT(*)" in sql:
        assert data["rows"] == [{"total": available_rows}]
    assert explained_sql == executed_sql
    executed_limit = sqlglot.parse_one(executed_sql[0], read="postgres").args["limit"]
    assert int(executed_limit.expression.this) == expected_limit


def test_trusted_metadata_accepts_fastmcp_dictionary_shape():
    meta = {
        "workbench_role": "admin",
        "workbench_effective_sources": ["db"],
    }
    ctx: Any = SimpleNamespace(request_context=SimpleNamespace(meta=meta))

    assert postgres_server._trusted_meta(ctx) == meta
    assert postgres_server._trusted_meta(ctx) is not meta


def test_trusted_metadata_accepts_model_shape_and_missing_context():
    model_meta = SimpleNamespace(
        model_dump=lambda **_kwargs: {"workbench_role": "admin"}
    )
    ctx: Any = SimpleNamespace(request_context=SimpleNamespace(meta=model_meta))

    assert postgres_server._trusted_meta(ctx) == {"workbench_role": "admin"}
    ctx.request_context = None
    assert postgres_server._trusted_meta(ctx) == {}


@pytest.mark.anyio
async def test_health_tool_is_discoverable_and_returns_structured_content(
    monkeypatch,
):
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
            return SimpleNamespace(
                data={"success": True, "data": {"status": "ok"}}
            )

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
    monkeypatch.setattr(
        postgres_server, "validate", lambda *_args, **_kwargs: checked
    )
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
        raise ValidationError(
            "Including all columns using * is prohibited specify the needed colums."
        )

    monkeypatch.setattr(postgres_server, "validate", rejected)

    payload = postgres_server._query("SELECT * FROM gold.agents", meta)

    assert payload["success"] is False
    assert payload["error"]["code"] == "COMPILE_REJECTED"
    assert payload["error"]["retryable"] is True
    assert payload["error"]["message"] == (
        "Including all columns using * is prohibited specify the needed colums."
    )
