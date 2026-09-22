"""Validated visual derivation from a stored, user-owned query result."""

from __future__ import annotations

from collections import OrderedDict
from typing import Any

from app.services.nlq.contracts import AxisSpec, ChartSpec, ColumnSpec, Lineage, SeriesSpec
from app.services.workbench.agent_contracts import (
    VisualizationChartType,
    VisualizeQueryResultArguments,
)
from app.services.workbench.results import SourceResult


class VisualizationError(ValueError):
    code = "INVALID_TOOL_ARGUMENTS"
    retryable = True


def _label(field: str) -> str:
    return field.replace("_", " ").strip().title()


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _result_fields(source_record: dict[str, Any]) -> tuple[list[str], list[str]]:
    payload = source_record.get("result_payload") or {}
    rows = [row for row in payload.get("rows", []) if isinstance(row, dict)]
    declared = [
        str(column.get("name"))
        for column in payload.get("columns", [])
        if isinstance(column, dict) and column.get("name")
    ]
    fields = list(dict.fromkeys([
        *declared,
        *(str(key) for row in rows for key in row),
    ]))
    numeric = [
        field for field in fields
        if any(row.get(field) is not None for row in rows)
        and all(
            row.get(field) is None or _is_number(row.get(field))
            for row in rows
        )
    ]
    return fields, numeric


def infer_visual_arguments(
    source_record: dict[str, Any], *, query_id: str, view: VisualizationChartType,
) -> VisualizeQueryResultArguments:
    """Derive a deterministic chart mapping from a shaped query result."""
    payload = source_record.get("result_payload") or {}
    rows = [row for row in payload.get("rows", []) if isinstance(row, dict)]
    fields, numeric = _result_fields(source_record)

    if view == "table":
        return VisualizeQueryResultArguments(
            query_id=query_id, chart_type=view, x=None, y=[], series=None,
            aggregation="none",
        )
    if view == "kpi":
        if len(rows) != 1 or not numeric:
            raise VisualizationError("kpi requires one result row with a numeric value")
        return VisualizeQueryResultArguments(
            query_id=query_id, chart_type=view, x=None, y=numeric, series=None,
            aggregation="none",
        )
    if view == "scatter":
        if len(numeric) != 2:
            raise VisualizationError("scatter requires exactly two numeric columns")
        return VisualizeQueryResultArguments(
            query_id=query_id, chart_type=view, x=numeric[0], y=[numeric[1]],
            series=None, aggregation="none",
        )
    if view in {"grouped_bar", "stacked_area", "heatmap"}:
        if len(fields) < 3:
            raise VisualizationError(
                f"{view} requires an x column, a series column, and a numeric value"
            )
        x, series = fields[0], fields[1]
        measures = [field for field in numeric if field not in {x, series}]
        if len(measures) != 1:
            raise VisualizationError(f"{view} requires exactly one numeric value column")
        return VisualizeQueryResultArguments(
            query_id=query_id, chart_type=view, x=x, y=measures,
            series=series, aggregation="none",
        )
    if len(fields) < 2:
        raise VisualizationError(f"{view} requires an x column and a numeric value")
    x = fields[0]
    measures = [field for field in numeric if field != x]
    if not measures:
        raise VisualizationError(f"{view} requires a numeric value column after x")
    if view == "donut" and len(measures) != 1:
        raise VisualizationError("donut requires exactly one numeric column")
    return VisualizeQueryResultArguments(
        query_id=query_id, chart_type=view, x=x, y=measures,
        series=None, aggregation="none",
    )


def build_inferred_visual(
    source_record: dict[str, Any], *, query_id: str, view: VisualizationChartType,
) -> SourceResult:
    return build_visual(
        source_record,
        infer_visual_arguments(source_record, query_id=query_id, view=view),
    )


def _column_map(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(column.get("name")): column
        for column in payload.get("columns", [])
        if isinstance(column, dict) and column.get("name")
    }


def _unit(columns: dict[str, dict[str, Any]], field: str, *, counted: bool = False) -> str:
    if counted:
        return "count"
    return str(columns.get(field, {}).get("unit") or "count")


def _require_fields(
    args: VisualizeQueryResultArguments, rows: list[dict[str, Any]],
    columns: dict[str, dict[str, Any]],
) -> None:
    available = set(columns)
    for row in rows:
        available.update(str(key) for key in row)
    requested = [field for field in (args.x, args.series, *args.y) if field]
    missing = list(dict.fromkeys(field for field in requested if field not in available))
    if missing:
        raise VisualizationError(f"unknown result field(s): {', '.join(missing)}")


def _validate_shape(args: VisualizeQueryResultArguments, rows: list[dict[str, Any]]) -> None:
    if args.chart_type == "table":
        return
    if not args.y:
        raise VisualizationError(f"{args.chart_type} requires at least one y field")
    if args.chart_type == "kpi":
        if args.x is not None or args.series is not None:
            raise VisualizationError("kpi requires x and series to be null")
    elif args.chart_type == "scatter":
        if args.x is None or len(args.y) != 1:
            raise VisualizationError("scatter requires one numeric x and one numeric y field")
    else:
        if args.x is None:
            raise VisualizationError(f"{args.chart_type} requires x")
    if args.chart_type in {"stacked_area", "heatmap"}:
        if args.series is None or len(args.y) != 1:
            raise VisualizationError(
                f"{args.chart_type} requires one y field and a series field"
            )
    if args.chart_type == "donut" and (args.series is not None or len(args.y) != 1):
        raise VisualizationError("donut requires one y field and a null series")
    if args.series is not None and len(args.y) != 1:
        raise VisualizationError("a series split supports exactly one y field")
    if args.aggregation == "none" and args.chart_type == "kpi" and len(rows) != 1:
        raise VisualizationError("kpi with aggregation none requires exactly one source row")


def _numeric_fields(args: VisualizeQueryResultArguments) -> list[str]:
    fields = list(args.y)
    if args.chart_type == "scatter" and args.x is not None:
        fields.insert(0, args.x)
    return fields


def _validate_numeric(args: VisualizeQueryResultArguments, rows: list[dict[str, Any]]) -> None:
    if args.aggregation in {"count", "count_distinct"}:
        numeric = [args.x] if args.chart_type == "scatter" and args.x else []
    else:
        numeric = _numeric_fields(args)
    invalid = [
        field for field in numeric
        if field and not any(_is_number(row.get(field)) for row in rows if row.get(field) is not None)
    ]
    if invalid:
        raise VisualizationError(f"numeric field(s) required: {', '.join(invalid)}")


def _aggregate(
    rows: list[dict[str, Any]], args: VisualizeQueryResultArguments,
) -> list[dict[str, Any]]:
    if args.aggregation == "none":
        if args.chart_type not in {"table", "scatter", "kpi"}:
            seen: set[tuple[Any, ...]] = set()
            keys = [field for field in (args.x, args.series) if field]
            for row in rows:
                key = tuple(row.get(field) for field in keys)
                if key in seen:
                    raise VisualizationError(
                        "aggregation none requires one row per x/series pair"
                    )
                seen.add(key)
        return [dict(row) for row in rows]

    group_fields = [field for field in (args.x, args.series) if field]
    grouped: OrderedDict[tuple[Any, ...], list[dict[str, Any]]] = OrderedDict()
    for row in rows:
        grouped.setdefault(tuple(row.get(field) for field in group_fields), []).append(row)

    output: list[dict[str, Any]] = []
    for key, members in grouped.items():
        item = dict(zip(group_fields, key, strict=True))
        for field in args.y:
            values = [row.get(field) for row in members if row.get(field) is not None]
            if args.aggregation == "count":
                item[field] = len(values)
            elif args.aggregation == "count_distinct":
                item[field] = len({str(value) for value in values})
            else:
                numbers = [value for value in values if _is_number(value)]
                if len(numbers) != len(values):
                    raise VisualizationError(f"{args.aggregation} requires numeric y field {field}")
                if not numbers:
                    item[field] = None
                elif args.aggregation == "sum":
                    item[field] = sum(numbers)
                elif args.aggregation == "avg":
                    item[field] = sum(numbers) / len(numbers)
                elif args.aggregation == "min":
                    item[field] = min(numbers)
                else:
                    item[field] = max(numbers)
        output.append(item)
    return output


def build_visual(
    source_record: dict[str, Any], args: VisualizeQueryResultArguments,
) -> SourceResult:
    source_complete = source_record.get("result_complete", True) is True
    if not source_complete and args.aggregation != "none":
        raise VisualizationError("cannot aggregate a truncated query result; run a bounded query")
    payload = source_record.get("result_payload") or {}
    source_rows = payload.get("rows")
    if not isinstance(source_rows, list) or not source_rows:
        raise VisualizationError("the query has no stored rows to visualize")
    rows = [dict(row) for row in source_rows if isinstance(row, dict)]
    columns = _column_map(payload)
    _require_fields(args, rows, columns)
    _validate_shape(args, rows)
    _validate_numeric(args, rows)

    if args.chart_type == "table":
        lineage = Lineage.model_validate(payload.get("lineage") or {})
        lineage.warnings = [
            *lineage.warnings,
            f"Visualization derived from query {args.query_id} using {args.aggregation}.",
        ]
        summary = f"Table derived from query {args.query_id}."
        chart = ChartSpec(
            chart_type="table",
            title=str(payload.get("title") or "Query result"),
            subtitle="Model-selected table",
            columns=[ColumnSpec.model_validate(column) for column in payload.get("columns", [])],
            rows=_aggregate(rows, args),
            summary=summary,
            lineage=lineage,
        )
        return SourceResult(
            source="db", card_type="chart", payload=chart.model_dump(mode="json"),
            summary=summary, lineage=chart.lineage.model_dump(mode="json"),
            complete=source_complete,
        )

    transformed = _aggregate(rows, args)
    counted = args.aggregation in {"count", "count_distinct"}
    lineage = Lineage.model_validate(payload.get("lineage") or {})
    lineage.warnings = [
        *lineage.warnings,
        f"Visualization derived from query {args.query_id} using {args.aggregation}.",
    ]

    if args.chart_type == "scatter":
        assert args.x is not None
        label_field = args.series or "__point"
        if args.series is None:
            for index, row in enumerate(transformed, start=1):
                row[label_field] = str(index)
        x_axis = AxisSpec(field=label_field, label=_label(label_field), unit="text")
        series_by = None
        series_specs = [
            SeriesSpec(field=args.x, label=_label(args.x), unit=_unit(columns, args.x)),
            SeriesSpec(
                field=args.y[0], label=_label(args.y[0]),
                unit=_unit(columns, args.y[0], counted=counted),
            ),
        ]
    else:
        x_axis = (
            AxisSpec(
                field=args.x, label=_label(args.x),
                unit=_unit(columns, args.x) if args.x else "text",
            )
            if args.x else None
        )
        series_by = (
            AxisSpec(
                field=args.series, label=_label(args.series),
                unit=_unit(columns, args.series),
            )
            if args.series else None
        )
        series_specs = [
            SeriesSpec(
                field=field, label=_label(field),
                unit=_unit(columns, field, counted=counted),
            )
            for field in args.y
        ]

    used_fields = list(dict.fromkeys(
        field for field in (args.x, args.series, *args.y) if field
    ))
    if args.chart_type == "scatter" and args.series is None:
        used_fields.insert(0, "__point")
    column_specs = [
        ColumnSpec(
            name=field,
            label=str(columns.get(field, {}).get("label") or _label(field)),
            unit=(
                "text" if field == "__point"
                else _unit(columns, field, counted=counted and field in args.y)
            ),
            sensitivity=str(columns.get(field, {}).get("sensitivity") or "internal"),
        )
        for field in used_fields
    ]
    title = str(payload.get("title") or "Query result")
    summary = f"{args.chart_type.replace('_', ' ').title()} derived from query {args.query_id}."
    chart = ChartSpec(
        chart_type=args.chart_type,
        title=title,
        subtitle="Derived from a previous query result",
        x=x_axis,
        series_by=series_by,
        series=series_specs,
        columns=column_specs,
        rows=transformed,
        summary=summary,
        lineage=lineage,
    )
    return SourceResult(
        source="db", card_type="chart", payload=chart.model_dump(mode="json"),
        summary=summary, lineage=chart.lineage.model_dump(mode="json"),
        complete=source_complete,
    )


__all__ = [
    "VisualizationError", "build_inferred_visual", "build_visual",
    "infer_visual_arguments",
]
