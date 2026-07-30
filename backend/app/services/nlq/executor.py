"""Run compiled SQL under the read-only role and return typed rows.

Reuses the provenance discipline from db_schema.py: an empty result and a failed query are
never conflated. A wrong-looking zero is the failure mode that destroys trust fastest, so
every outcome carries a status that distinguishes "the query ran and found nothing" from
"the query did not run".
"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field, replace
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from app.core.config import settings
from app.services.nlq import cache
from app.services.nlq import db as nlq_db
from app.services.nlq.compiler import CompiledQuery, bind

logger = logging.getLogger(__name__)

# Rejected before execution: EXPLAIN's estimate is in arbitrary planner units, but on a
# schema whose largest table is 260k rows a plan costing more than this is a fan-out bug,
# not honest work.
MAX_PLAN_COST = 5_000_000.0


class ExecutionError(RuntimeError):
    """A query that failed to run. The message shown to the user is deliberately generic —
    a raw Postgres error leaks schema (§2.6)."""

    def __init__(self, message: str, *, detail: str = "") -> None:
        super().__init__(message)
        self.detail = detail


@dataclass(slots=True)
class QueryResult:
    rows: list[dict[str, Any]]
    columns: list[str]
    status: str  # "ok" | "empty"
    duration_ms: int
    sql: str
    row_count: int = 0
    truncated: bool = False
    plan_cost: float | None = None
    cached: bool = False
    warnings: list[str] = field(default_factory=list)


def execute(
    compiled: CompiledQuery, *, explain_gate: bool = True, use_cache: bool = True
) -> QueryResult:
    """Execute a compiled query on the read-only pool."""
    sql, params = bind(compiled.sql, compiled.params)

    # Keyed on the data version, so an ingestion invalidates every entry rather than
    # serving yesterday's numbers under today's question.
    cache_key = cache.result_key(sql, params) if use_cache else None
    if cache_key is not None:
        hit = cache.get_result(cache_key)
        if hit is not None:
            return replace(hit, duration_ms=0, cached=True)

    started = time.perf_counter()

    try:
        with nlq_db.readonly_cursor() as (conn, cur):
            plan_cost = _explain(cur, sql, params) if explain_gate else None
            if plan_cost is not None and plan_cost > MAX_PLAN_COST:
                raise ExecutionError(
                    "That question is too broad to answer quickly. Try narrowing the "
                    "period or adding a filter.",
                    detail=f"estimated plan cost {plan_cost:,.0f} exceeds {MAX_PLAN_COST:,.0f}",
                )
            cur.execute(sql, params)
            columns = [d[0] for d in cur.description] if cur.description else []
            raw_rows = cur.fetchall()
            conn.rollback()  # read-only: end the transaction without holding locks
    except ExecutionError:
        raise
    except nlq_db.ReadOnlyNotConfigured as exc:
        raise ExecutionError(
            "The query service is not configured yet.", detail=str(exc)
        ) from exc
    except Exception as exc:  # noqa: BLE001 - one generic message, full detail to the log
        logger.exception("NLQ query failed: %s", compiled.sql)
        raise ExecutionError(
            "The query could not be completed against the warehouse.",
            detail=f"{type(exc).__name__}: {exc}",
        ) from exc

    duration_ms = int((time.perf_counter() - started) * 1000)
    rows = [dict(zip(columns, _coerce_row(row))) for row in raw_rows]
    limit = min(compiled.params.get("row_limit", settings.nlq_max_rows), settings.nlq_max_rows)

    # An aggregate over zero rows returns one row of NULLs, not zero rows. Reporting that
    # as a successful result renders "no data" inside a KPI tile as though it were a value;
    # it is an empty result and is labelled as one, with the filters that produced it.
    all_null = len(rows) == 1 and all(v is None for v in rows[0].values())

    result = QueryResult(
        rows=rows,
        columns=columns,
        status="empty" if (not rows or all_null) else "ok",
        duration_ms=duration_ms,
        sql=sql,
        row_count=len(rows),
        truncated=len(rows) >= limit,
        plan_cost=plan_cost,
        warnings=list(compiled.warnings),
    )
    if cache_key is not None:
        cache.put_result(cache_key, result)
    return result


def execute_raw(sql: str, *, explain_gate: bool = True) -> QueryResult:
    """Execute a statement that has already passed `validator.validate`.

    Separate from `execute` so the type system makes the difference visible: this takes a
    bare string and therefore must only ever be called with validator output. It carries no
    parameters, because the text-to-SQL path produces a complete literal statement.
    """
    started = time.perf_counter()
    try:
        with nlq_db.readonly_cursor() as (conn, cur):
            plan_cost = _explain(cur, sql, []) if explain_gate else None
            if plan_cost is not None and plan_cost > MAX_PLAN_COST:
                raise ExecutionError(
                    "That question is too broad to answer quickly. Try narrowing the "
                    "period or adding a filter.",
                    detail=f"estimated plan cost {plan_cost:,.0f}",
                )
            cur.execute(sql)
            columns = [d[0] for d in cur.description] if cur.description else []
            raw_rows = cur.fetchall()
            conn.rollback()
    except ExecutionError:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.exception("NLQ generated SQL failed: %s", sql)
        raise ExecutionError(
            "The generated query could not be completed.",
            detail=f"{type(exc).__name__}: {exc}",
        ) from exc

    rows = [dict(zip(columns, _coerce_row(row))) for row in raw_rows]
    return QueryResult(
        rows=rows,
        columns=columns,
        status="ok" if rows else "empty",
        duration_ms=int((time.perf_counter() - started) * 1000),
        sql=sql,
        row_count=len(rows),
        plan_cost=plan_cost,
    )


def _explain(cur: Any, sql: str, params: list[Any]) -> float | None:
    """Estimated total cost of the plan, or None when EXPLAIN itself fails.

    A failed EXPLAIN is not fatal — the statement_timeout on the role remains the backstop —
    but it is logged, because it usually means the SQL is malformed.
    """
    try:
        cur.execute(f"EXPLAIN {sql}", params)
        text = " ".join(str(r[0]) for r in cur.fetchall())
    except Exception as exc:  # noqa: BLE001
        logger.warning("NLQ EXPLAIN failed, proceeding without the cost gate: %s", exc)
        return None
    match = re.search(r"cost=[\d.]+\.\.([\d.]+)", text)
    return float(match.group(1)) if match else None


def _coerce_row(row: Any) -> list[Any]:
    """JSON-safe values. Decimal -> float and dates -> ISO strings, because a ChartSpec is
    serialised straight to the browser."""
    out = []
    for value in row:
        if isinstance(value, Decimal):
            out.append(float(value))
        elif isinstance(value, datetime):
            out.append(value.date().isoformat())
        elif isinstance(value, date):
            out.append(value.isoformat())
        elif isinstance(value, (bytes, bytearray)):
            out.append(value.decode("utf-8", "replace"))
        elif isinstance(value, str):
            out.append(value.strip())
        else:
            out.append(value)
    return out
