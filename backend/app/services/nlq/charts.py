"""Result shape -> ChartSpec. Deterministic, never chosen by the LLM.

The same question always renders the same way. That is what makes the product feel like a
tool rather than a slot machine, and it is why chart choice is a table of rules here rather
than a prompt.

Formatting comes from catalog metadata — `unit: inr` renders in lakh/crore, `unit: percent`
to one decimal — so a number never appears in a unit the catalog did not declare.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from app.services.nlq import drilldown, drivers
from app.services.nlq.catalog import Catalog, get_catalog
from app.services.nlq.catalog import lookups
from app.services.nlq.catalog.loader import canonical_enum_code
from app.services.nlq.compiler import CompiledQuery, describe_parameters, render_sql_for_display
from app.services.nlq.contracts import (
    AxisSpec,
    ChartSpec,
    ColumnSpec,
    Lineage,
    QuerySpec,
    SeriesSpec,
)
from app.services.nlq.executor import QueryResult
from app.services.nlq.narrator import format_value
from app.services.nlq.normalization import normalize_lending_question
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
        display_sql=render_sql_for_display(compiled.sql, compiled.params),
        parameters=describe_parameters(compiled.params),
        source_tables=compiled.source_tables,
        formulas=compiled.formulas,
        row_count=result.row_count,
        duration_ms=result.duration_ms,
        as_of=compiled.as_of,
        warnings=_lineage_warnings(compiled, result),
        unverified=path == "text_to_sql",
        requires_signoff=compiled.signoff_pending,
    )

    decomposition = None
    if chart_type == "waterfall" and prior is not None:
        decomposition = _decompose(spec, rows, prior, cat)
        rows, columns = _waterfall_rows(decomposition, cat)
    elif chart_type in ("variance", "dumbbell") and prior is not None:
        rows, columns = _variance_rows(spec, compiled, rows, prior, cat)

    x_axis, series = _axes(spec, compiled, chart_type, cat)
    series_by = _series_by(spec, chart_type, x_axis, cat)

    from app.services.nlq.narrator import narrate  # local: narrator imports chart vocabulary

    if decomposition is not None:
        summary = drivers.narrate(decomposition, cat)
        if decomposition.caveat:
            lineage.warnings.append(decomposition.caveat)
    else:
        summary = narrate(spec, compiled, result, rows, chart_type, cat)

    steps = drilldown.next_steps(spec, cat)
    return ChartSpec(
        chart_type=chart_type,
        title=_title(spec, compiled, cat),
        subtitle=_subtitle(compiled, result),
        x=x_axis,
        series_by=series_by,
        series=series,
        columns=columns,
        rows=rows,
        summary=summary,
        # `drilldown` is the bar-click target and keeps its original *append* semantics —
        # branch, then branch x agent. The `deeper` chip's spec cannot serve here because it
        # *replaces* the split: clicking one branch would return a by-agent view of the whole
        # book, so a control that implies narrowing would quietly widen. Narrowing to the
        # clicked member is `drilldown.drill_into`, which needs the member the click carries.
        drilldown=drilldown.append_level(spec, cat),
        next_steps=steps,
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

    # "Why did it change?" is a different question from "what were the two values?", and
    # only the spec can say which was asked — the row shapes are identical.
    #
    # A ratio whose denominator was not carried through the query is the one case that must
    # not become a waterfall: without weights there is no exact split and no honest total,
    # so the bridge would have nothing at either end. It falls back to the comparison forms,
    # which claim only what a ratio can support.
    #
    # A time split is the second case. A bridge attributes one change to one set of members;
    # with a month on the axis each member appears once per month, and the decomposition
    # would keep whichever row happened to arrive last — reporting one month's movement as
    # the whole period's. Explaining branch-by-month means explaining the total first.
    if (
        spec.explain
        and spec.compare_to is not None
        and cat_dims
        and not time_dims
        and _is_decomposable(spec, cat)
    ):
        return "waterfall"

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
            if (
                spec.as_share
                and 2 <= n_rows <= MAX_DONUT_SLICES
                and _is_additive(metrics[0], cat)
            ):
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


def _is_decomposable(spec: QuerySpec, cat: Catalog) -> bool:
    """Whether the change in this spec's metric can be split exactly across members."""
    metric = cat.metrics.get(spec.metrics[0])
    if metric is None:
        return False
    if not metric.is_ratio:
        return True  # flows and stocks add up by construction
    return bool(metric.weight_metric) and metric.weight_metric in spec.metrics


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
    _disambiguate_decoded_dimensions(out, spec, cat)
    return out


def _disambiguate_decoded_dimensions(
    rows: list[dict[str, Any]], spec: QuerySpec, catalog: Catalog
) -> None:
    """Keep two codes with one governed label visually distinct.

    The Gold product master legitimately contains scheme 1615 and 1619 under the same
    "Loan Against Property" name. A chart with two identical category labels is ambiguous,
    so only colliding labels receive their code suffix.
    """
    for dimension_id in spec.dimensions:
        dimension = catalog.dimensions.get(dimension_id)
        if dimension is None or not dimension.decode:
            continue
        codes_by_label: dict[str, set[str]] = {}
        for row in rows:
            if f"{dimension_id}__raw" not in row:
                continue
            label = str(row.get(dimension_id, ""))
            code = canonical_enum_code(row[f"{dimension_id}__raw"])
            codes_by_label.setdefault(label, set()).add(code)
        collisions = {label for label, codes in codes_by_label.items() if len(codes) > 1}
        for row in rows:
            label = str(row.get(dimension_id, ""))
            if label not in collisions:
                continue
            code = canonical_enum_code(row[f"{dimension_id}__raw"])
            suffix = f"Scheme #{code}" if dimension_id == "scheme" else code
            row[dimension_id] = f"{label} ({suffix})"


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
        sensitivity = (
            "pii" if (dim.table, dim.column) in cat.pii_columns() else "internal"
        )
        columns.append(
            ColumnSpec(name=dim_id, label=dim.label, unit="text", sensitivity=sensitivity)
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
        "months": "integer",
        "years": "integer",
        "year": "integer",
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

    # A waterfall's rows are the decomposition's, not the query's: `step` and `value`
    # replace the dimension and the metric, so the axes have to name those instead. Without
    # this the export and the representation toggle read keys that are not in the rows.
    if chart_type == "waterfall":
        metric = cat.metrics[spec.metrics[0]]
        return (
            AxisSpec(field="step", label=axis_dim.label if axis_dim else "Driver", unit="text"),
            [SeriesSpec(field="value", label="Contribution", unit=metric.unit)],
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
    if chart_type in ("kpi", "table", "variance", "dumbbell", "waterfall"):
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
    description: str = "",
) -> ChartSpec:
    """ChartSpec for the text-to-SQL path, where there is no QuerySpec to read from.

    Shape is inferred from the returned columns rather than from a catalog entry, so the
    rules are necessarily weaker than on the trusted path — which is one more reason these
    answers are marked unverified.
    """
    cat = catalog or get_catalog()
    unit_hints = unit_hints or {}
    columns = result.columns
    rows = _decode_generated_rows(result.rows, columns, cat)
    numeric = [
        c for c in columns
        if _column_is_numeric(rows, c) and not _generated_dimension_column(c, columns, unit_hints)
    ]
    labels = [c for c in columns if c not in numeric]

    if not result.rows:
        chart_type = "table"
    elif len(rows) == 1 and len(numeric) >= 1 and not labels:
        chart_type = "kpi"
    elif len(labels) == 1 and len(numeric) == 1:
        chart_type = "bar" if len(rows) <= MAX_BAR_CATEGORIES else "ranking"
    else:
        chart_type = "table"

    clean_title = normalize_lending_question(question).strip().rstrip("?.!")
    return ChartSpec(
        chart_type=chart_type,
        title=(clean_title[:1].upper() + clean_title[1:])[:120],
        subtitle="Generated query — not a reviewed metric",
        x=AxisSpec(
            field=labels[0],
            label=labels[0].replace("_", " ").title(),
            unit=unit_hints.get(labels[0], "text"),
        )
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
        rows=rows,
        summary=_generated_summary(
            rows, columns, numeric, labels, unit_hints, description=description
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


_DIMENSION_LIKE_GENERATED_COLUMNS = frozenset({
    "interest_rate", "year", "month", "quarter", "fy", "product_code", "scheme_code",
    "branch_code", "loan_status", "account_status", "asset_code", "dpd_bucket",
})


def _generated_dimension_column(
    column: str, columns: list[str], unit_hints: dict[str, str]
) -> bool:
    """Recognise a numeric grouping key in generated output.

    ``interest_rate`` in a rate distribution is an x value, not a second measure.  Keeping
    it out of ``numeric`` lets the normal one-dimension/one-metric bar rule apply while its
    percent unit still formats both the table and the category labels correctly.
    """
    return (
        len(columns) > 1
        and column == columns[0]
        and column.lower() in _DIMENSION_LIKE_GENERATED_COLUMNS
        and any(other != column and unit_hints.get(other) in {"count", "inr", "percent"}
                for other in columns)
    )


def _decode_generated_rows(
    rows: list[dict[str, Any]], columns: list[str], catalog: Catalog
) -> list[dict[str, Any]]:
    """Apply the same governed labels to generated SQL that QuerySpec charts receive."""
    decoders: dict[str, str] = {}
    for column in columns:
        lowered = column.lower()
        for dimension_id, enum in catalog.enums.items():
            if lowered in {dimension_id.lower(), enum.column.lower(), f"{dimension_id.lower()}_code"}:
                decoders[column] = dimension_id
                break

    decoded_rows: list[dict[str, Any]] = []
    for row in rows:
        decoded = dict(row)
        for column, dimension_id in decoders.items():
            raw = decoded.get(column)
            if raw in (None, ""):
                decoded[column] = "Not recorded"
                continue
            decoded[f"{column}__raw"] = raw
            decoded[column] = lookups.label_for(catalog, dimension_id, raw)
        decoded_rows.append(decoded)
    for column, dimension_id in decoders.items():
        codes_by_label: dict[str, set[str]] = {}
        for row in decoded_rows:
            raw_key = f"{column}__raw"
            if raw_key in row:
                codes_by_label.setdefault(str(row[column]), set()).add(
                    canonical_enum_code(row[raw_key])
                )
        collisions = {label for label, codes in codes_by_label.items() if len(codes) > 1}
        for row in decoded_rows:
            if str(row.get(column)) not in collisions:
                continue
            code = canonical_enum_code(row[f"{column}__raw"])
            suffix = f"Scheme #{code}" if dimension_id == "scheme" else code
            row[column] = f"{row[column]} ({suffix})"
    return decoded_rows


def _generated_summary(
    rows: list[dict[str, Any]],
    columns: list[str],
    numeric: list[str],
    labels: list[str],
    unit_hints: dict[str, str],
    *,
    description: str,
) -> str:
    if not rows:
        base = "The generated query returned no matching rows."
    elif len(rows) == 1 and numeric and not labels:
        values = [
            f"{column.replace('_', ' ').title()} was "
            f"{format_value(rows[0].get(column), unit_hints.get(column, 'count'))}"
            for column in numeric
        ]
        base = "; ".join(values) + "."
    elif labels and numeric:
        label, metric = labels[0], numeric[0]
        ranked = [row for row in rows if isinstance(row.get(metric), (int, float))]
        if ranked:
            top = max(ranked, key=lambda row: row[metric])
            label_value = top.get(label)
            if isinstance(label_value, (int, float)) and unit_hints.get(label, "text") != "text":
                label_value = format_value(label_value, unit_hints[label])
            base = (
                f"{label_value} has the highest {metric.replace('_', ' ')} at "
                f"{format_value(top[metric], unit_hints.get(metric, 'count'))} across "
                f"{len(rows):,} returned {label.replace('_', ' ')} value(s)."
            )
        else:
            base = f"The query returned {len(rows):,} row(s)."
    else:
        readable = ", ".join(column.replace("_", " ") for column in columns[:5])
        base = f"The query returned {len(rows):,} row(s) covering {readable}."

    detail = " ".join(description.split()).strip()
    if detail:
        detail = detail.rstrip(".") + "."
    verification = (
        "This uses a validated read-only generated query rather than a reviewed metric; "
        "check Source details before relying on it."
    )
    return " ".join(part for part in (base, detail, verification) if part)


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


def _decompose(
    spec: QuerySpec, rows: list[dict[str, Any]], prior: QueryResult, cat: Catalog
) -> drivers.Decomposition:
    """Attribute the change to the members of the spec's categorical dimension."""
    dimension = next(d for d in spec.dimensions if not cat.dimensions[d].is_time)
    metric = cat.metrics[spec.metrics[0]]
    # The weight only counts if the query actually carried it — a ratio explained without
    # its denominator is reported as indicative rather than silently treated as exact.
    weight = metric.weight_metric if metric.weight_metric in spec.metrics else None
    return drivers.decompose(
        metric.id, dimension, rows, prior.rows, cat, weight_metric=weight
    )


def _waterfall_rows(
    decomposition: drivers.Decomposition, cat: Catalog
) -> tuple[list[dict[str, Any]], list[ColumnSpec]]:
    """Prior total, each mover, current total — the bridge between two numbers.

    The two totals are marked `total` so the renderer can floor them at zero while the
    contributions float on the running balance."""
    d = decomposition
    unit = d.unit

    rows: list[dict[str, Any]] = [
        {"step": f"{d.label} before", "value": d.prior_total, "kind": "total"}
    ]
    for contribution in (*d.contributions, *( (d.other,) if d.other else () )):
        row = {
            "step": contribution.label,
            "value": contribution.delta,
            "kind": "contribution",
            # Scaled to whole percent here, because `unit: percent` means "already scaled"
            # everywhere else in the product — both `narrator.format_value` and the
            # frontend's. Passing the raw 0.62 fraction rendered a 62% driver as "0.62%" in
            # the table, directly under a summary sentence that said 62%.
            "share": None if contribution.share is None else contribution.share * 100,
        }
        if d.is_ratio and d.exact:
            row["rate_effect"] = contribution.rate_effect
            row["mix_effect"] = contribution.mix_effect
        rows.append(row)
    rows.append({"step": f"{d.label} after", "value": d.current_total, "kind": "total"})

    columns = [
        ColumnSpec(name="step", label=d.dimension_label, unit="text", sensitivity="public"),
        ColumnSpec(name="value", label=f"{d.label} contribution", unit=unit),  # type: ignore[arg-type]
        ColumnSpec(name="kind", label="Kind", unit="text", sensitivity="public"),
        ColumnSpec(name="share", label="Share of change", unit="percent"),
    ]
    if d.is_ratio and d.exact:
        columns += [
            ColumnSpec(name="rate_effect", label="Rate effect", unit=unit),  # type: ignore[arg-type]
            ColumnSpec(name="mix_effect", label="Mix effect", unit=unit),  # type: ignore[arg-type]
        ]
    return rows, columns
