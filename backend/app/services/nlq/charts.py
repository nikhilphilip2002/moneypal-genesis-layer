"""Result shape -> ChartSpec. Deterministic, never chosen by the LLM.

The same question always renders the same way. That is what makes the product feel like a
tool rather than a slot machine, and it is why chart choice is a table of rules here rather
than a prompt.

Formatting comes from catalog metadata — `unit: inr` renders in lakh/crore, `unit: percent`
to one decimal — so a number never appears in a unit the catalog did not declare.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from app.services.nlq.catalog import Catalog, get_catalog
from app.services.nlq.catalog import lookups
from app.services.nlq.compiler import CompiledQuery
from app.services.nlq.contracts import (
    AxisSpec,
    ChartSpec,
    ColumnSpec,
    Lineage,
    QuerySpec,
    SeriesSpec,
)
from app.services.nlq.executor import QueryResult
from app.services.nlq.periods import format_bucket

MAX_BAR_CATEGORIES = 12
MAX_LINE_SERIES = 6
MAX_DONUT_SLICES = 6      # past six, slices are thinner than the eye can compare
MAX_DUMBBELL_ITEMS = 20   # one row per item, so the limit is vertical space


def build(
    spec: QuerySpec,
    compiled: CompiledQuery,
    result: QueryResult,
    *,
    prior: QueryResult | None = None,
    catalog: Catalog | None = None,
    path: str = "queryspec",
) -> ChartSpec:
    """Assemble the single response payload."""
    cat = catalog or get_catalog()

    rows = _decode_rows(spec, compiled, result, cat)
    columns = _columns(spec, compiled, cat)
    chart_type = choose_chart_type(spec, compiled, result, cat)

    lineage = Lineage(
        path="text_to_sql" if path == "text_to_sql" else "queryspec",
        sql=result.sql,
        source_tables=compiled.source_tables,
        formulas=compiled.formulas,
        row_count=result.row_count,
        duration_ms=result.duration_ms,
        as_of=compiled.as_of,
        warnings=_lineage_warnings(compiled, result),
        unverified=path == "text_to_sql",
        requires_signoff=compiled.signoff_pending,
    )

    if chart_type in ("variance", "dumbbell") and prior is not None:
        rows, columns = _variance_rows(spec, compiled, rows, prior, cat)

    x_axis, series = _axes(spec, compiled, chart_type, cat)
    series_by = _series_by(spec, chart_type, x_axis, cat)

    from app.services.nlq.narrator import narrate  # local: narrator imports chart vocabulary

    return ChartSpec(
        chart_type=chart_type,
        title=_title(spec, compiled, cat),
        subtitle=_subtitle(compiled, result),
        x=x_axis,
        series_by=series_by,
        series=series,
        columns=columns,
        rows=rows,
        summary=narrate(spec, compiled, result, rows, chart_type, cat),
        drilldown=_drilldown(spec, cat),
        lineage=lineage,
    )


# --------------------------------------------------------------------------------------
# Chart type selection (§5)
# --------------------------------------------------------------------------------------


def choose_chart_type(
    spec: QuerySpec, compiled: CompiledQuery, result: QueryResult, cat: Catalog
) -> str:
    if result.status == "empty":
        return "kpi" if not spec.dimensions else "table"

    metrics = spec.metrics
    dims = [cat.dimensions[d] for d in spec.dimensions]
    time_dims = [d for d in dims if d.is_time]
    cat_dims = [d for d in dims if not d.is_time]
    n_rows = result.row_count

    # A comparison of two periods. Which form depends on what is being compared across:
    # per-item before/after is a dumbbell (two dots and the gap between them), while a
    # bare delta reads as a diverging bar around zero.
    if spec.compare_to is not None:
        if len(cat_dims) == 1 and not time_dims and n_rows <= MAX_DUMBBELL_ITEMS:
            return "dumbbell"
        return "variance"

    if not dims:
        return "kpi" if len(metrics) == 1 else "table"

    if len(metrics) == 1:
        if time_dims and not cat_dims:
            # A flow accumulates over the period, and area says so. A stock does not —
            # filling the space under PAR 30 would imply summing a percentage.
            return "area" if _is_flow(metrics[0], cat) else "line"
        if time_dims and cat_dims:
            distinct = len({r.get(cat_dims[0].id) for r in result.rows})
            if distinct > MAX_LINE_SERIES:
                # Sixteen branches on one time axis is a hairball, and stacking them
                # answers a question about the total that nobody asked.
                return "small_multiples"
            if spec.as_share and _is_flow(metrics[0], cat):
                return "stacked_area"
            if spec.as_share and _is_additive(metrics[0], cat):
                # A stock has no area to fill — nothing accumulates between two dates — but
                # the balances at each date do sum across categories, so the composition is
                # a stack of bars per period rather than a band.
                return "stacked_bar"
            return "line"
        if len(cat_dims) == 1:
            if spec.as_share and n_rows <= MAX_DONUT_SLICES and _is_additive(metrics[0], cat):
                return "donut"
            return "bar" if n_rows <= MAX_BAR_CATEGORIES else "ranking"
        if len(cat_dims) == 2:
            return "heatmap"
        return "table"

    # Two metrics against each other across one set of items is a scatter — genuinely two
    # independent axes, which is not the dual-axis trap: there is no shared x to align a
    # second y-scale against, so no false correlation is manufactured. Mixed units are
    # therefore fine here, and only here.
    if len(metrics) == 2 and len(cat_dims) == 1 and not time_dims:
        return "scatter"

    # Any other multi-metric shape shares one y-axis, so it has to share one unit. A rupee
    # series and a percentage series cannot, and a second axis is not the answer.
    if len({cat.metrics[m].unit for m in metrics}) > 1:
        return "table"
    if len(cat_dims) == 1 and not time_dims:
        return "grouped_bar"
    if time_dims:
        return "line"
    return "table"


def _is_flow(metric_id: str, cat: Catalog) -> bool:
    metric = cat.metrics.get(metric_id)
    return bool(metric and metric.grain == "flow")


def _is_additive(metric_id: str, cat: Catalog) -> bool:
    """Part-to-whole requires the parts to sum to the whole. A ratio's slices do not:
    three collection-efficiency percentages have no meaningful total to be shares of."""
    metric = cat.metrics.get(metric_id)
    return bool(metric and metric.grain in ("flow", "point_in_time"))


# --------------------------------------------------------------------------------------
# Rows, columns, axes
# --------------------------------------------------------------------------------------


def _decode_rows(
    spec: QuerySpec, compiled: CompiledQuery, result: QueryResult, cat: Catalog
) -> list[dict[str, Any]]:
    """Replace codes with labels and time buckets with fiscal-aware text.

    Both the raw and the labelled value are kept: the label is what a human reads, the raw
    code is what a drill-down filters on.
    """
    out: list[dict[str, Any]] = []
    for row in result.rows:
        decoded = dict(row)
        for dim_id in spec.dimensions:
            dim = cat.dimensions.get(dim_id)
            if dim is None or dim_id not in decoded:
                continue
            raw = decoded[dim_id]
            decoded[f"{dim_id}__raw"] = raw
            if dim.is_time:
                decoded[dim_id] = format_bucket(dim.grain or "month", _as_date(raw))
            elif dim.decode:
                decoded[dim_id] = (
                    "Not recorded" if raw in (None, "") else lookups.label_for(cat, dim.decode, raw)
                )
            elif raw in (None, ""):
                decoded[dim_id] = "Not recorded"
        out.append(decoded)
    return out


def _as_date(value: Any) -> Any:
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value).date()
        except ValueError:
            return value
    if isinstance(value, datetime):
        return value.date()
    return value


def _columns(spec: QuerySpec, compiled: CompiledQuery, cat: Catalog) -> list[ColumnSpec]:
    columns: list[ColumnSpec] = []
    for dim_id in spec.dimensions:
        dim = cat.dimensions[dim_id]
        columns.append(
            ColumnSpec(name=dim_id, label=dim.label, unit="text", sensitivity="internal")
        )
    for metric_id in spec.metrics:
        metric = cat.metrics[metric_id]
        columns.append(
            ColumnSpec(
                name=metric_id,
                label=metric.label,
                unit=metric.unit,
                format=_format_hint(metric.unit),
                sensitivity="internal",
            )
        )
    return columns


def _format_hint(unit: str) -> str | None:
    return {
        "inr": "inr_compact",   # ₹1.23 Cr / ₹4.56 L
        "percent": "percent_1", # 12.3%
        "count": "integer",     # 13,510
        "days": "integer",
    }.get(unit)


def _axes(
    spec: QuerySpec, compiled: CompiledQuery, chart_type: str, cat: Catalog
) -> tuple[AxisSpec | None, list[SeriesSpec]]:
    if chart_type == "kpi":
        return None, [
            SeriesSpec(field=m, label=cat.metrics[m].label, unit=cat.metrics[m].unit)
            for m in spec.metrics
        ]

    dims = [cat.dimensions[d] for d in spec.dimensions]
    axis_dim = next((d for d in dims if d.is_time), dims[0] if dims else None)
    x_axis = (
        AxisSpec(
            field=axis_dim.id,
            label=axis_dim.label,
            grain=axis_dim.grain if axis_dim.is_time else None,
            unit="text",
        )
        if axis_dim
        else None
    )

    # The comparison forms read `_variance_rows` output, whose columns are `previous`,
    # `current` and `delta` — the metric id is not a key in those rows, so pointing the
    # series at it would render an empty chart.
    if chart_type in ("variance", "dumbbell"):
        metric = cat.metrics[spec.metrics[0]]
        if chart_type == "variance":
            return x_axis, [SeriesSpec(field="delta", label="Change", unit=metric.unit)]
        return x_axis, [
            SeriesSpec(field="previous", label=compiled.compare_label or "Before",
                       unit=metric.unit),
            SeriesSpec(field="current", label=compiled.period_label or "After",
                       unit=metric.unit),
        ]

    # Always one axis. A second y-scale lets the reader infer a crossing or a correlation
    # that the numbers do not support — it is the single most misleading thing a chart can
    # do. Where units genuinely differ, `choose_chart_type` falls back to a table instead.
    series = [
        SeriesSpec(
            field=metric_id,
            label=cat.metrics[metric_id].label,
            unit=cat.metrics[metric_id].unit,
        )
        for metric_id in spec.metrics
    ]
    return x_axis, series


def _series_by(
    spec: QuerySpec, chart_type: str, x_axis: AxisSpec | None, cat: Catalog
) -> AxisSpec | None:
    """The dimension that splits the rows into series, when there is a second one.

    Rows come back long-format — one row per (month, branch) pair — so a multi-series time
    chart has to pivot before it can draw. Naming the column here means the renderer never
    infers it from the shape of the data, which is guesswork that fails on the first
    dimension whose values happen to look numeric.
    """
    if chart_type in ("kpi", "table", "variance", "dumbbell"):
        return None
    extra = [cat.dimensions[d] for d in spec.dimensions if not x_axis or d != x_axis.field]
    if not extra:
        return None
    dim = extra[0]
    return AxisSpec(field=dim.id, label=dim.label, grain=dim.grain if dim.is_time else None)


def _variance_rows(
    spec: QuerySpec,
    compiled: CompiledQuery,
    current_rows: list[dict[str, Any]],
    prior: QueryResult,
    cat: Catalog,
) -> tuple[list[dict[str, Any]], list[ColumnSpec]]:
    """A, B, delta, delta% — joined on the dimension values, not on row position."""
    key_fields = [d for d in spec.dimensions]
    metric_id = spec.metrics[0]

    def key_of(row: dict[str, Any]) -> tuple:
        return tuple(row.get(f"{k}__raw", row.get(k)) for k in key_fields)

    prior_by_key = {key_of(r): r for r in prior.rows}
    # A bounded period comparison can still arrive with its period grain as a dimension:
    # "this quarter vs last quarter" then produces one Q3 row and one Q2 row. Those raw
    # time keys are necessarily different, but the singleton rows are the two sides of the
    # comparison. Joining them by the literal quarter used to discard the prior value.
    singleton_time_pair = (
        len(current_rows) == 1
        and len(prior.rows) == 1
        and bool(key_fields)
        and all(cat.dimensions[field].is_time for field in key_fields)
    )

    rows: list[dict[str, Any]] = []
    for row in current_rows:
        prior_row = prior.rows[0] if singleton_time_pair else prior_by_key.get(key_of(row), {})
        before = prior_row.get(metric_id)
        after = row.get(metric_id)
        delta = None
        delta_pct = None
        if isinstance(after, (int, float)) and isinstance(before, (int, float)):
            delta = after - before
            delta_pct = (delta / before * 100) if before else None
        merged = {k: row[k] for k in key_fields if k in row}
        merged.update(
            {
                "current": after,
                "previous": before,
                "delta": delta,
                "delta_pct": round(delta_pct, 1) if delta_pct is not None else None,
            }
        )
        rows.append(merged)

    metric = cat.metrics[metric_id]
    columns = [
        ColumnSpec(name=k, label=cat.dimensions[k].label, unit="text") for k in key_fields
    ] + [
        ColumnSpec(name="current", label=f"{metric.label} ({compiled.period_label})",
                   unit=metric.unit, format=_format_hint(metric.unit)),
        ColumnSpec(name="previous", label=f"{metric.label} ({compiled.compare_label})",
                   unit=metric.unit, format=_format_hint(metric.unit)),
        ColumnSpec(name="delta", label="Change", unit=metric.unit,
                   format=_format_hint(metric.unit)),
        ColumnSpec(name="delta_pct", label="Change %", unit="percent", format="percent_1"),
    ]
    return rows, columns


def build_from_rows(
    *,
    question: str,
    result: QueryResult,
    lineage: Lineage,
    catalog: Catalog | None = None,
    unit_hints: dict[str, str] | None = None,
) -> ChartSpec:
    """ChartSpec for the text-to-SQL path, where there is no QuerySpec to read from.

    Shape is inferred from the returned columns rather than from a catalog entry, so the
    rules are necessarily weaker than on the trusted path — which is one more reason these
    answers are marked unverified.
    """
    cat = catalog or get_catalog()
    unit_hints = unit_hints or {}
    columns = result.columns
    numeric = [c for c in columns if _column_is_numeric(result.rows, c)]
    labels = [c for c in columns if c not in numeric]

    if not result.rows:
        chart_type = "table"
    elif len(result.rows) == 1 and len(numeric) >= 1 and not labels:
        chart_type = "kpi"
    elif len(labels) == 1 and len(numeric) == 1:
        chart_type = "bar" if len(result.rows) <= MAX_BAR_CATEGORIES else "ranking"
    else:
        chart_type = "table"

    return ChartSpec(
        chart_type=chart_type,
        title=question[:120],
        subtitle="Generated query — not a reviewed metric",
        x=AxisSpec(field=labels[0], label=labels[0].replace("_", " ").title(), unit="text")
        if labels
        else None,
        series=[
            SeriesSpec(
                field=c,
                label=c.replace("_", " ").title(),
                unit=unit_hints.get(c, "count"),
            )
            for c in numeric
        ],
        columns=[
            ColumnSpec(
                name=c,
                label=c.replace("_", " ").title(),
                unit=unit_hints.get(c, "count" if c in numeric else "text"),
                format=_format_hint(unit_hints[c]) if c in unit_hints else None,
                sensitivity="internal",
            )
            for c in columns
        ],
        rows=result.rows,
        summary=(
            f"{result.row_count} row(s) returned. This answer came from a generated query "
            "rather than a reviewed metric — check the SQL before relying on it."
            if result.rows
            else "The generated query returned no rows."
        ),
        drilldown=None,
        lineage=lineage,
    )


def _column_is_numeric(rows: list[dict[str, Any]], column: str) -> bool:
    for row in rows:
        value = row.get(column)
        if value is None:
            continue
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    return False


def _title(spec: QuerySpec, compiled: CompiledQuery, cat: Catalog) -> str:
    metric_labels = " and ".join(cat.metrics[m].label for m in spec.metrics)
    dim_labels = [cat.dimensions[d].label.lower() for d in spec.dimensions]
    if dim_labels:
        return f"{metric_labels} by {' and '.join(dim_labels)}"
    return metric_labels


def _subtitle(compiled: CompiledQuery, result: QueryResult) -> str | None:
    if compiled.as_of:
        return f"As at {compiled.as_of.strftime('%d %b %Y')}"
    return compiled.period_label or None


def _lineage_warnings(compiled: CompiledQuery, result: QueryResult) -> list[str]:
    warnings = list(compiled.warnings)
    if result.truncated:
        warnings.append(
            f"Showing the first {result.row_count} rows — the full result was larger."
        )
    return warnings


def _drilldown(spec: QuerySpec, cat: Catalog) -> QuerySpec | None:
    """What a click re-runs: the same question one level deeper.

    Returns None when there is no sensible next level, rather than inventing one — a
    drill-down that lands somewhere arbitrary is worse than none.
    """
    if len(spec.dimensions) >= 2:
        return None
    ladder = ["branch", "product", "scheme"]
    current = spec.dimensions[0] if spec.dimensions else None
    if current in (None, "month", "quarter", "fy", "year", "day", "week", "fy_quarter"):
        nxt = "branch"
    else:
        try:
            nxt = ladder[ladder.index(current) + 1]
        except (ValueError, IndexError):
            return None
    if nxt == current or nxt not in cat.dimensions:
        return None
    return spec.model_copy(update={"dimensions": [*spec.dimensions, nxt]})
