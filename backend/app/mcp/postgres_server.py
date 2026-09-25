"""Read-only PostgreSQL MCP server for Moneypal Workbench.

The model calls the server's native ``query`` tool directly. The server validates SQL against
the governed Gold catalog, applies cost, row, and statement limits, and connects as
``nlq_readonly``. MCP changes the integration boundary; it does not weaken the database boundary.
"""

from __future__ import annotations

from typing import Any

from fastmcp import Context, FastMCP

from app.mcp.results import failure, success
from app.services.nlq import db as nlq_db, pii
from app.services.nlq.catalog import get_catalog
from app.services.nlq.executor import ExecutionError, execute_raw
from app.services.nlq.sql_execution import infer_column_units
from app.services.nlq.validator import ValidationError as SqlValidationError
from app.services.nlq.validator import validate


mcp = FastMCP(
    "Moneypal PostgreSQL",
    instructions=(
        "Read-only PostgreSQL access to the governed Gold loan-book schema. Every statement "
        "is catalog-validated and executed as nlq_readonly."
    ),
)


@mcp.tool
async def postgres_health() -> dict[str, Any]:
    """Check the dedicated read-only PostgreSQL role and governed Gold-view availability."""
    return success(nlq_db.health())


def _trusted_meta(ctx: Context) -> dict[str, Any]:
    """MCP request metadata is attached by the backend and is not a model argument."""
    request_context = ctx.request_context
    meta = request_context.meta if request_context is not None else None
    if meta is None:
        return {}
    if isinstance(meta, dict):
        return dict(meta)
    return meta.model_dump(exclude_none=True)


def _query(sql: str, meta: dict[str, Any]) -> dict[str, Any]:
    """Synchronous query boundary in the dedicated, serialized MCP service."""
    catalog = get_catalog()
    role = str(meta.get("workbench_role") or "")
    effective_sources = meta.get("workbench_effective_sources")
    if (
        not isinstance(effective_sources, list)
        or "db" not in effective_sources
    ):
        return failure(
            "POLICY_DENIED",
            "This request is not authorized to access the loan-book source.",
            retryable=False,
            catalog_version=catalog.version,
        )
    try:
        checked = validate(
            sql,
            catalog=catalog,
            allow_pii=pii.may_see_pii(role),
        )
    except SqlValidationError as exc:
        return failure(
            "COMPILE_REJECTED",
            str(exc)[:1000],
            retryable=True,
            catalog_version=catalog.version,
        )

    try:
        result = execute_raw(checked.sql)
    except ExecutionError as exc:
        return failure(
            exc.code,
            str(exc)[:500],
            retryable=exc.retryable,
            detail=exc.detail[:1000],
            catalog_version=catalog.version,
        )

    return success(
        {
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
            "column_units": infer_column_units(
                checked.sql, checked.tables, catalog
            ),
            "catalog_version": catalog.version,
        }
    )


@mcp.tool
async def query(sql: str, ctx: Context) -> dict[str, Any]:
    """Query results are returned to the assistant and are not rendered to the user.

    Execute one read-only PostgreSQL SELECT against governed gold.* views.
    SELECT * is not allowed; name the columns explicitly.

    Schema-qualify every table, name every selected column, use only columns and joins from
    the supplied Gold schema, include an appropriate date condition when the question names a
    period, and include LIMIT 5000 or less. Filter before joining and aggregate one-to-many
    inputs before joining them. Avoid correlated subqueries. Validation and timeout errors are
    returned for correction; never repeat identical SQL after a timeout.

    Select dimensions before measures. For category/time-series charts, aggregate in SQL
    with GROUP BY as needed to return one row per x/series pair. Final presentation does
    not aggregate duplicates. KPI needs one row; tables and scatter allow repeated x values.
    """
    meta = _trusted_meta(ctx)
    return _query(sql, meta)


if __name__ == "__main__":
    mcp.run(
        transport="http",
        host="0.0.0.0",
        port=8001,
        path="/mcp",
        json_response=True,
        stateless_http=True,
    )
