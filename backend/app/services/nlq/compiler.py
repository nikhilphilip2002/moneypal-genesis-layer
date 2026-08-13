"""QuerySpec -> SQL. Deterministic Python, no LLM anywhere in this file.

This is the trusted path. Because a QuerySpec can only name catalog entries, and every
value reaches the database as a bound parameter, the output cannot be made to say anything
the catalog does not already permit — there is no string interpolation of user input.

Validation runs before generation, in the order given in §2.5:
  1. every metric / dimension / filter field exists           -> metrics.resolve + here
  2. metric <-> dimension compatibility                        -> metrics.resolve
  3. join paths are declared and unambiguous                   -> _join_plan
  4. fan-out check                                             -> _join_plan
  5. grain check                                               -> metrics.resolve
  6. period resolution against the Indian fiscal calendar      -> periods.resolve_relative

Point-in-time portfolio metrics are read through the governed
`gold.portfolio_snapshot_as_of(date)` function. That keeps the historical-collapse rule in
the database semantic layer instead of exposing the underlying classification event log.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any

from app.services.nlq import metrics as metric_rules
from app.services.nlq import periods
from app.services.nlq.catalog import Catalog, Dimension, Join, get_catalog
from app.services.nlq.contracts import Filter, Period, QuerySpec

MAX_ROWS = 5000

# Alias per table, so generated SQL is readable in the lineage panel.
_ALIASES = {
    "gold.loan_account_master": "lam",
    "gold.portfolio_daily_snapshot": "portfolio",
    "gold.loan_disbursement_events": "disb",
    "gold.loan_repayment_events": "repay",
    "gold.loan_schedule_events": "sched",
    "gold.gl_daily_balances": "gl",
    "gold.customer_master": "customer",
    "gold.agent_master": "agent",
}


class CompileError(ValueError):
    """A spec that cannot be compiled. The message reaches the user."""


@dataclass(slots=True)
class CompiledQuery:
    sql: str
    params: dict[str, Any]
    source_tables: list[str]
    metric_ids: list[str]
    dimension_ids: list[str]
    column_order: list[str]
    formulas: dict[str, str]
    warnings: list[str] = field(default_factory=list)
    signoff_pending: list[str] = field(default_factory=list)
    as_of: date | None = None
    period_label: str = ""
    compare_label: str = ""
    touches_pii: bool = False


def _alias(table: str) -> str:
    return _ALIASES.get(table, table.split(".")[-1][:4])


def compile_spec(
    spec: QuerySpec, catalog: Catalog | None = None, today: date | None = None
) -> CompiledQuery:
    """Compile a validated QuerySpec into parameterised SQL."""
    cat = catalog or get_catalog()

    try:
        plan = metric_rules.resolve(spec, cat)
    except metric_rules.MetricError as exc:
        raise CompileError(str(exc)) from exc

    base_table = plan.base_table
    base_alias = _alias(base_table)
    params: dict[str, Any] = {}

    period = _resolve_period(spec.period, today)
    compare = _resolve_period(spec.compare_to, today) if spec.compare_to else None

    dims = [cat.dimensions[d] for d in spec.dimensions]
    joins = _join_plan(cat, base_table, dims, spec.filters, plan)

    # ---- FROM / point-in-time collapse -------------------------------------------------
    # Three shapes, and picking the wrong one is how a plausible wrong number happens:
    #   flow metric              -> aggregate the fact table directly
    #   point-in-time, no trend  -> one DISTINCT ON snapshot at the period end
    #   point-in-time + a trend  -> one snapshot per time bucket, via LATERAL
    time_dims = [d for d in dims if d.is_time]
    as_of_date: date | None = None
    bucket_expr: str | None = None

    if plan.needs_as_of and time_dims:
        if len(time_dims) > 1:
            raise CompileError("only one time grain can be charted at a time")
        as_of_date = period.end
        source_sql, bucket_expr = _as_of_series_source(
            plan, base_table, base_alias, params, period, time_dims[0]
        )
    elif plan.needs_as_of:
        as_of_date = period.end
        source_sql = _as_of_source(plan, base_table, base_alias, params, as_of_date)
    else:
        source_sql = f"{base_table} AS {base_alias}"

    from_parts = [source_sql]
    for join, right_table in joins:
        right_alias = _alias(right_table)
        left_alias = base_alias if join.left == base_table else _alias(join.left)
        conditions = []
        for left_col, right_col in join.on:
            # Column order in joins.yaml follows (left table, right table); flip when the
            # edge is declared in the opposite direction to the one we are traversing.
            if join.right == right_table:
                conditions.append(f'{left_alias}."{left_col}" = {right_alias}."{right_col}"')
            else:
                conditions.append(f'{left_alias}."{right_col}" = {right_alias}."{left_col}"')
        keyword = "LEFT JOIN" if join.join_type == "left" else "JOIN"
        from_parts.append(
            f"{keyword} {right_table} AS {right_alias} ON " + " AND ".join(conditions)
        )

    # ---- SELECT ------------------------------------------------------------------------
    select_parts: list[str] = []
    group_parts: list[str] = []
    order_candidates: dict[str, str] = {}
    column_order: list[str] = []

    date_column = _date_column(plan, base_alias)

    for dim in dims:
        if dim.is_time:
            if bucket_expr is not None:
                expr = bucket_expr  # the LATERAL series already emits one row per bucket
            elif date_column is None:
                raise CompileError(
                    f"'{plan.metrics[0].label}' has no date column, so it cannot be shown "
                    f"by {dim.label.lower()}"
                )
            else:
                expr = periods.truncate_sql(dim.grain, date_column)
            sort_expr = None
        else:
            expr, sort_expr = _dimension_sql(cat, dim, base_table, base_alias)
        select_parts.append(f"{expr} AS {dim.id}")
        group_parts.append(expr)
        if sort_expr:
            group_parts.append(sort_expr)
            order_candidates[dim.id] = sort_expr
        else:
            order_candidates[dim.id] = expr
        column_order.append(dim.id)

    for metric in plan.metrics:
        expr = metric.sql(base_alias)
        select_parts.append(f"{expr} AS {metric.id}")
        order_candidates[metric.id] = expr
        column_order.append(metric.id)

    # ---- WHERE -------------------------------------------------------------------------
    where_parts: list[str] = []
    if date_column and not plan.needs_as_of:
        where_parts.append(f"{date_column} BETWEEN :period_start AND :period_end")
        params["period_start"] = period.start
        params["period_end"] = period.end
    elif plan.metrics[0].year_column:
        where_parts.append(
            f'{base_alias}."{plan.metrics[0].year_column}" '
            "BETWEEN :period_start_year AND :period_end_year"
        )
        params["period_start_year"] = period.start.year
        params["period_end_year"] = period.end.year

    for index, flt in enumerate(spec.filters):
        clause = _filter_sql(cat, flt, base_table, base_alias, params, index)
        where_parts.append(clause)

    # ---- assemble ----------------------------------------------------------------------
    sql_lines = ["SELECT " + ",\n       ".join(select_parts), "FROM " + "\n     ".join(from_parts)]
    if where_parts:
        sql_lines.append("WHERE " + "\n  AND ".join(where_parts))
    if group_parts:
        sql_lines.append("GROUP BY " + ", ".join(dict.fromkeys(group_parts)))

    order_sql = _order_by(spec, order_candidates, dims, plan)
    if order_sql:
        sql_lines.append("ORDER BY " + order_sql)

    limit = min(spec.limit, MAX_ROWS)
    sql_lines.append("LIMIT :row_limit")
    params["row_limit"] = limit

    source_tables = [base_table] + [t for _, t in joins]
    touches_pii = any(
        (cat.table_by_name(t).contains_pii if cat.table_by_name(t) else False)
        for t in source_tables
    )

    compiled = CompiledQuery(
        sql="\n".join(sql_lines),
        params=params,
        source_tables=source_tables,
        metric_ids=list(spec.metrics),
        dimension_ids=list(spec.dimensions),
        column_order=column_order,
        formulas=metric_rules.formulas_for(list(spec.metrics), cat),
        warnings=list(plan.warnings),
        signoff_pending=list(plan.signoff_pending),
        as_of=as_of_date,
        period_label=period.label,
        compare_label=compare.label if compare else "",
        touches_pii=touches_pii,
    )
    return compiled


def compile_comparison(
    spec: QuerySpec, catalog: Catalog | None = None, today: date | None = None
) -> tuple[CompiledQuery, CompiledQuery]:
    """Two compiled queries for a `compare_to` spec: current period and prior period.

    Two round trips rather than one clever self-joined query — the variance table needs
    both result sets anyway, and each half stays independently inspectable in the lineage
    panel, which is what makes a disputed delta traceable.
    """
    if spec.compare_to is None:
        raise CompileError("compile_comparison requires compare_to")
    current = compile_spec(spec, catalog, today)
    prior_spec = spec.model_copy(update={"period": spec.compare_to, "compare_to": None})
    prior = compile_spec(prior_spec, catalog, today)
    return current, prior


# --------------------------------------------------------------------------------------
# Pieces
# --------------------------------------------------------------------------------------


def _resolve_period(period: Period | None, today: date | None) -> periods.DateRange:
    if period is None:
        raise CompileError("a period is required")
    if period.relative:
        return periods.resolve_relative(period.relative, today)
    if period.start and period.end:
        return periods.DateRange(period.start, period.end, f"{period.start} to {period.end}")
    raise CompileError("period must carry either a relative token or both start and end")


def _date_column(plan: metric_rules.MetricPlan, alias: str) -> str | None:
    columns = {m.date_column for m in plan.metrics if m.date_column}
    if not columns:
        return None
    if len(columns) > 1:
        raise CompileError(
            "these metrics are dated by different columns and would need different time "
            "axes; ask for them separately"
        )
    return f'{alias}."{columns.pop()}"'


def _as_of_source(
    plan: metric_rules.MetricPlan,
    base_table: str,
    alias: str,
    params: dict[str, Any],
    as_of: date,
) -> str:
    """Use the reviewed Gold as-of function, or a legacy catalog collapse definition."""
    metric = next(m for m in plan.metrics if m.needs_as_of)
    if metric.as_of_function:
        params["as_of"] = as_of
        return f"{metric.as_of_function}(:as_of) AS {alias}"
    keys = ", ".join(f'"{k}"' for k in metric.as_of_key)
    params["as_of"] = as_of
    inner = (
        f"SELECT DISTINCT ON ({keys}) *\n"
        f"       FROM {base_table}\n"
        f'       WHERE "{metric.as_of_column}" <= :as_of\n'
        f'       ORDER BY {keys}, "{metric.as_of_column}" DESC'
    )
    return f"(\n       {inner}\n     ) AS {alias}"


# Bucket width per time grain, for the point-in-time series.
_GRAIN_INTERVAL = {
    "day": "1 day",
    "week": "1 week",
    "month": "1 month",
    "quarter": "3 months",
    "fy_quarter": "3 months",
    "year": "1 year",
    "fy": "1 year",
}


def _as_of_series_source(
    plan: metric_rules.MetricPlan,
    base_table: str,
    alias: str,
    params: dict[str, Any],
    period: periods.DateRange,
    time_dim: Dimension,
) -> tuple[str, str]:
    """One as-of snapshot per time bucket — a genuine PAR trend line.

    Grouping a single snapshot by its classification date would answer a different and
    misleading question: it would show only the accounts that happened to be reclassified
    in each month, not the state of the book at each month end. So the buckets are
    generated first, and each one gets its own DISTINCT ON snapshot through a LATERAL join.
    """
    metric = next(m for m in plan.metrics if m.needs_as_of)
    interval = _GRAIN_INTERVAL.get(time_dim.grain or "")
    if interval is None:
        raise CompileError(f"cannot build a point-in-time series at {time_dim.grain!r} grain")

    # Anchor on the truncated period start so buckets align to real month/quarter/FY edges
    # rather than to whatever day the period happens to begin on.
    anchor = _bucket_anchor(period.start, time_dim.grain or "month")
    params["bucket_anchor"] = anchor
    params["bucket_end"] = period.end

    if metric.as_of_function:
        source = (
            "(SELECT generate_series(:bucket_anchor::date, :bucket_end::date,\n"
            f"                             INTERVAL '{interval}')::date AS bucket_start) AS buckets\n"
            "     LEFT JOIN LATERAL "
            f"{metric.as_of_function}(\n"
            f"       LEAST((buckets.bucket_start + INTERVAL '{interval}' - "
            "INTERVAL '1 day')::date, :bucket_end::date)\n"
            f"     ) AS {alias} ON TRUE"
        )
        return source, "buckets.bucket_start"

    keys = ", ".join(f'"{k}"' for k in metric.as_of_key)
    source = (
        "(SELECT generate_series(:bucket_anchor::date, :bucket_end::date,\n"
        f"                             INTERVAL '{interval}')::date AS bucket_start) AS buckets\n"
        # LEFT, not CROSS: a bucket with no classified accounts must render as an explicit
        # gap in the trend. Dropping the row instead makes the chart skip from March to May
        # as though the months did not exist.
        "     LEFT JOIN LATERAL (\n"
        f"       SELECT DISTINCT ON ({keys}) *\n"
        f"       FROM {base_table}\n"
        f'       WHERE "{metric.as_of_column}" <= '
        f"LEAST((buckets.bucket_start + INTERVAL '{interval}' - INTERVAL '1 day')::date, "
        ":bucket_end::date)\n"
        f'       ORDER BY {keys}, "{metric.as_of_column}" DESC\n'
        f"     ) AS {alias} ON TRUE"
    )
    return source, "buckets.bucket_start"


def _bucket_anchor(start: date, grain: str) -> date:
    if grain == "day":
        return start
    if grain == "week":
        return periods.week_bounds(start).start
    if grain == "month":
        return periods.month_bounds(start).start
    if grain == "quarter":
        return periods.quarter_bounds(start).start
    if grain == "fy_quarter":
        fy, quarter = periods.fy_quarter_of(start)
        return periods.fy_quarter_bounds(fy, quarter).start
    if grain == "fy":
        return periods.fy_bounds(periods.fy_of(start)).start
    if grain == "year":
        return date(start.year, 1, 1)
    raise CompileError(f"no bucket anchor defined for grain {grain!r}")


def _join_plan(
    cat: Catalog,
    base_table: str,
    dims: list[Dimension],
    filters: list[Filter],
    plan: metric_rules.MetricPlan,
) -> list[tuple[Join, str]]:
    """Which tables to join, in order. Rules 3 and 4 of §2.5 live here."""
    needed: list[str] = []
    for dim in dims:
        if not dim.is_time and dim.table != base_table and dim.table not in needed:
            needed.append(dim.table)
    for flt in filters:
        dim = cat.dimensions.get(flt.field)
        if dim and not dim.is_time and dim.table != base_table and dim.table not in needed:
            needed.append(dim.table)

    out: list[tuple[Join, str]] = []
    for table in needed:
        join = cat.join_between(base_table, table)
        if join is None:
            raise CompileError(
                f"no declared join between {base_table.split('.')[-1]} and "
                f"{table.split('.')[-1]}, so this combination cannot be answered"
            )
        if join.fans_out and _has_additive_metric(plan):
            raise CompileError(
                f"joining {table.split('.')[-1]} would produce multiple rows per account "
                f"and multiply the totals. {join.description.strip().splitlines()[0]}"
            )
        out.append((join, table))
    return out


def _has_additive_metric(plan: metric_rules.MetricPlan) -> bool:
    return any(m.expression and "SUM(" in m.expression.upper() for m in plan.metrics)


def _dimension_sql(
    cat: Catalog, dim: Dimension, base_table: str, base_alias: str
) -> tuple[str, str | None]:
    alias = base_alias if dim.table == base_table else _alias(dim.table)
    return dim.sql(alias), dim.sort_sql(alias)


def _filter_sql(
    cat: Catalog,
    flt: Filter,
    base_table: str,
    base_alias: str,
    params: dict[str, Any],
    index: int,
) -> str:
    dim = cat.dimensions.get(flt.field)
    if dim is None:
        raise CompileError(
            f"cannot filter on {flt.field!r} — it is not a known dimension. "
            f"Available: {', '.join(sorted(cat.dimensions))}"
        )
    if dim.is_time:
        raise CompileError(
            "time is expressed through the period, not as a filter — set `period` instead"
        )

    alias = base_alias if dim.table == base_table else _alias(dim.table)
    column = f'{alias}."{dim.column}"'
    value = _decode_filter_value(cat, dim, flt.value)
    key = f"f{index}"

    if flt.op == "is_null":
        return f"{column} IS NULL"
    if flt.op in ("in", "not_in"):
        # `= ANY(:param)`, not `IN :param`: a bound list adapts to an ARRAY constructor,
        # which `IN` will not accept. ANY/ALL take the array directly and keep the value
        # bound rather than expanded into the statement.
        params[key] = [str(v) for v in value]
        operator = "= ANY" if flt.op == "in" else "<> ALL"
        if dim.id == "agent":
            params[key] = [str(v).lower() for v in value]
            return f"LOWER({column}::text) {operator}(:{key})"
        return f"{column}::text {operator}(:{key})"
    if flt.op == "between":
        params[f"{key}_lo"], params[f"{key}_hi"] = value[0], value[1]
        return f"{column} BETWEEN :{key}_lo AND :{key}_hi"
    if flt.op == "contains":
        params[key] = f"%{value}%"
        return f"{column}::text ILIKE :{key}"

    operators = {"eq": "=", "ne": "<>", "gt": ">", "gte": ">=", "lt": "<", "lte": "<="}
    if dim.id == "agent" and flt.op in ("eq", "ne"):
        params[key] = str(value).lower()
        return f"LOWER({column}::text) {operators[flt.op]} :{key}"
    params[key] = value
    cast = "::text" if flt.op in ("eq", "ne") else ""
    return f"{column}{cast} {operators[flt.op]} :{key}"


def _decode_filter_value(cat: Catalog, dim: Dimension, value: Any) -> Any:
    """Turn "gold loans" into the code 1, so a filter written in English still binds.

    Only exact label/synonym matches resolve. A fuzzy match here would silently answer
    about the wrong product, which is worse than saying the value is unknown.
    """
    enum = cat.enum_for_dimension(dim.id) if dim.decode else None
    if enum is None:
        return value
    if isinstance(value, list):
        return [_decode_one(enum, v) for v in value]
    return _decode_one(enum, value)


def _decode_one(enum, value: Any) -> Any:
    if isinstance(value, str):
        code = enum.code_for(value)
        if code is not None:
            return code
    return str(value)


def _order_by(
    spec: QuerySpec,
    candidates: dict[str, str],
    dims: list[Dimension],
    plan: metric_rules.MetricPlan,
) -> str:
    if spec.order_by:
        expr = candidates.get(spec.order_by.field)
        if expr is None:
            raise CompileError(
                f"cannot order by {spec.order_by.field!r} — it is not in this query's "
                "metrics or dimensions"
            )
        return f"{expr} {spec.order_by.direction.upper()} NULLS LAST"

    # Sensible defaults: chronological along a time axis, largest-first for a ranking.
    time_dims = [d for d in dims if d.is_time]
    if time_dims:
        return f"{candidates[time_dims[0].id]} ASC"
    if dims and plan.metrics:
        return f"{candidates[plan.metrics[0].id]} DESC NULLS LAST"
    return ""


def bind(sql: str, params: dict[str, Any]) -> tuple[str, list[Any]]:
    """Convert :named placeholders to the DB-API %s form, preserving order.

    Values never enter the SQL string — this only rewrites the placeholder syntax, so the
    driver still does the binding.
    """
    import re

    ordered: list[Any] = []

    def replace(match: re.Match) -> str:
        name = match.group(1)
        if name not in params:
            raise CompileError(f"unbound parameter :{name}")
        ordered.append(params[name])
        return "%s"

    # Bare `:name` only — `::text` casts must survive untouched.
    rendered = re.sub(r"(?<!:):([a-zA-Z_][a-zA-Z0-9_]*)", replace, sql)
    return rendered, ordered
