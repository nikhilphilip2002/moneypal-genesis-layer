"""Compile -> execute -> chart, in one call.

The deterministic half of the product. `/nlq/execute` is exactly this and nothing else,
which is why saved questions, drill-downs and dashboards keep working when the LLM is
offline.
"""

from __future__ import annotations

import logging
from datetime import date

from app.services.nlq import charts, pii, text_to_sql
from app.services.nlq.catalog import Catalog, get_catalog
from app.services.nlq.compiler import CompileError, compile_comparison, compile_spec
from app.services.nlq.contracts import ChartSpec, QuerySpec
from app.services.nlq.executor import ExecutionError, QueryResult, execute

logger = logging.getLogger(__name__)


def run_spec(
    spec: QuerySpec,
    *,
    catalog: Catalog | None = None,
    today: date | None = None,
    path: str = "queryspec",
    role: str | None = None,
) -> ChartSpec:
    """Execute a QuerySpec and return a rendered ChartSpec.

    Raises CompileError for a question we refuse to answer (the message is for the user)
    and ExecutionError when the database itself failed.
    """
    cat = catalog or get_catalog()

    prior: QueryResult | None = None
    if spec.compare_to is not None:
        compiled, compiled_prior = compile_comparison(spec, cat, today)
        result = execute(compiled)
        prior = execute(compiled_prior)
    else:
        compiled = compile_spec(spec, cat, today)
        result = execute(compiled)

    chart = charts.build(spec, compiled, result, prior=prior, catalog=cat, path=path)
    return _mask(chart, role, cat)


def run_sql(attempt, *, question: str, role: str | None, catalog: Catalog | None = None) -> ChartSpec:
    """Execute an already-validated generated statement.

    `attempt.validated` is asserted rather than checked politely: reaching here with an
    unvalidated statement is a programming error, and failing loudly is the only acceptable
    response to it.
    """
    from app.services.nlq.executor import execute_raw

    cat = catalog or get_catalog()
    if not getattr(attempt, "validated", False):
        raise AssertionError("refusing to execute SQL that did not pass the validator")

    result = execute_raw(attempt.sql)
    chart = charts.build_from_rows(
        question=question,
        result=result,
        lineage=text_to_sql.lineage_for(attempt, result.row_count, result.duration_ms),
        catalog=cat,
        unit_hints=getattr(attempt, "column_units", None),
        description=getattr(attempt, "explanation", ""),
    )
    return _mask(chart, role, cat)


def _mask(chart: ChartSpec, role: str | None, catalog: Catalog) -> ChartSpec:
    """Mask PII unless the caller's role permits it (§7.4)."""
    rows, masked = pii.mask_rows(chart.rows, chart.columns, role=role, catalog=catalog)
    if masked:
        chart.rows = rows
        chart.lineage.warnings.append(
            f"Personal data is masked for your role ({', '.join(masked)})."
        )
    return chart


__all__ = ["run_spec", "run_sql", "CompileError", "ExecutionError"]
