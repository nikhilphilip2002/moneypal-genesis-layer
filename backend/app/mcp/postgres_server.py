"""Read-only PostgreSQL MCP server for Moneypal Workbench.

The model calls the server's native ``query`` tool directly. The server validates SQL against
the governed Gold catalog, applies cost, row, and statement limits, and connects as
``nlq_readonly``. MCP changes the integration boundary; it does not weaken the database boundary.
"""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import Context, FastMCP

from app.services.nlq import db as nlq_db, pii
from app.services.nlq.catalog import get_catalog
from app.services.nlq.executor import ExecutionError, execute_raw
from app.services.nlq.text_to_sql import _infer_column_units
from app.services.nlq.validator import ValidationError as SqlValidationError
from app.services.nlq.validator import validate


mcp = FastMCP(
    "Moneypal PostgreSQL",
    instructions=(
        "Read-only PostgreSQL access to the governed Gold loan-book schema. Every statement "
        "is catalog-validated and executed as nlq_readonly."
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


def _trusted_meta(ctx: Context) -> dict[str, Any]:
    """MCP request metadata is attached by the backend and is not a model argument."""
    meta = ctx.request_context.meta
    return meta.model_dump(exclude_none=True) if meta is not None else {}


@mcp.tool()
def query(sql: str, ctx: Context) -> dict[str, Any]:
    """Execute one read-only PostgreSQL SELECT against governed gold.* views.

    Schema-qualify every table, name every selected column, use only columns and joins from
    the supplied Gold schema, include an appropriate date condition when the question names a
    period, and include LIMIT 5000 or less. Validation errors are returned for correction.
    """
    catalog = get_catalog()
    meta = _trusted_meta(ctx)
    role = str(meta.get("workbench_role") or "")
    effective_sources = meta.get("workbench_effective_sources")
    if not isinstance(effective_sources, list) or "db" not in effective_sources:
        return {
            "status": "error",
            "code": "POLICY_DENIED",
            "message": "This request is not authorized to access the loan-book source.",
            "retryable": False,
            "catalog_version": catalog.version,
        }
    try:
        checked = validate(
            sql,
            catalog=catalog,
            allow_pii=pii.may_see_pii(role),
        )
    except SqlValidationError as exc:
        return {
            "status": "error",
            "code": "SQL_VALIDATION_ERROR",
            "message": str(exc)[:1000],
            "retryable": True,
            "catalog_version": catalog.version,
        }

    try:
        result = execute_raw(checked.sql)
    except ExecutionError as exc:
        return {
            "status": "error",
            "code": "SQL_EXECUTION_ERROR",
            "message": str(exc)[:500],
            "detail": exc.detail[:1000],
            "retryable": True,
            "catalog_version": catalog.version,
        }

    return {
        "status": result.status,
        "columns": result.columns,
        "rows": result.rows,
        "row_count": result.row_count,
        "truncated": result.truncated,
        "duration_ms": result.duration_ms,
        "plan_cost": result.plan_cost,
        "validated_sql": result.sql,
        "tables": checked.tables,
        "pii_columns": checked.pii_columns,
        "limit_injected": checked.limit_injected,
        "warnings": [*checked.warnings, *result.warnings],
        "column_units": _infer_column_units(checked.sql, checked.tables, catalog),
        "catalog_version": catalog.version,
    }


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
