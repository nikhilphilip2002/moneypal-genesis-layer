"""Typed numeric facts extracted from governed tool results."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Iterable

from app.services.workbench.results import ToolResult


@dataclass(frozen=True, slots=True)
class Fact:
    id: str
    label: str
    value: Decimal
    display_value: str
    unit: str
    source: str
    card_type: str
    row: int
    field: str
    period: str = ""
    dimensions: tuple[tuple[str, str], ...] = ()
    verified: bool = True
    formula: str = ""
    operands: tuple[str, ...] = ()
    operation: str = ""


def _decimal(value: Any) -> Decimal | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return Decimal(str(value).replace(",", ""))
    except (InvalidOperation, ValueError):
        return None


def _period_from_payload(payload: dict[str, Any]) -> str:
    plan = payload.get("drilldown") if isinstance(payload.get("drilldown"), dict) else {}
    period = plan.get("period") if isinstance(plan.get("period"), dict) else {}
    if period.get("relative"):
        return str(period["relative"])
    if period.get("start") or period.get("end"):
        return f"{period.get('start', '')} to {period.get('end', '')}".strip(" to")
    return str(payload.get("subtitle") or "")


def from_results(
    results: Iterable[ToolResult], *, max_per_result: int | None = None,
) -> list[Fact]:
    facts: list[Fact] = []
    for card_index, result in enumerate(results):
        if result.source != "db":
            continue
        if result.card_type == "analysis":
            found = _analysis_facts(result, card_index)
            facts.extend(found[:max_per_result] if max_per_result is not None else found)
            continue
        if result.card_type != "chart":
            continue
        columns = result.payload.get("columns")
        rows = result.payload.get("rows")
        if not isinstance(columns, list) or not isinstance(rows, list):
            continue
        numeric = {
            str(column.get("name")): column
            for column in columns
            if isinstance(column, dict)
            and column.get("name")
            and column.get("unit") not in {"text", "date", "datetime", "boolean"}
        }
        dimension_fields = [
            str(column.get("name"))
            for column in columns
            if isinstance(column, dict)
            and column.get("name")
            and column.get("unit") in {"text", "date", "datetime"}
        ]
        period = _period_from_payload(result.payload)
        result_fact_count = 0
        for row_index, row in enumerate(rows):
            if not isinstance(row, dict):
                continue
            for field, column in numeric.items():
                value = _decimal(row.get(field))
                if value is None:
                    continue
                if max_per_result is not None and result_fact_count >= max_per_result:
                    break
                facts.append(Fact(
                    id=f"{result.source}:{card_index}:{row_index}:{field}",
                    label=str(column.get("label") or field),
                    value=value,
                    display_value=str(row.get(field)),
                    unit=str(column.get("unit") or "number"),
                    source=result.source,
                    card_type=result.card_type,
                    row=row_index,
                    field=field,
                    period=period,
                    dimensions=tuple(
                        (name, str(row[name]))
                        for name in dimension_fields
                        if row.get(name) is not None
                    ),
                ))
                result_fact_count += 1
            if max_per_result is not None and result_fact_count >= max_per_result:
                break
    return facts


def _analysis_facts(result: ToolResult, card_index: int) -> list[Fact]:
    findings = result.payload.get("findings")
    if not isinstance(findings, list):
        return []
    output: list[Fact] = []
    for row_index, finding in enumerate(findings):
        if not isinstance(finding, dict):
            continue
        value = _decimal(finding.get("value"))
        if value is None:
            continue
        spec = finding.get("spec") if isinstance(finding.get("spec"), dict) else {}
        period_value = spec.get("period") if isinstance(spec.get("period"), dict) else {}
        period = str(
            period_value.get("relative")
            or " to ".join(
                str(period_value.get(key, "")) for key in ("start", "end")
            ).strip(" to")
        )
        dimensions = tuple(
            (str(item.get("field")), str(item.get("value")))
            for item in spec.get("filters", [])
            if isinstance(item, dict) and item.get("field") and item.get("value") is not None
        )
        output.append(Fact(
            id=f"{result.source}:{card_index}:finding:{row_index}",
            label=str(finding.get("label") or finding.get("step_id") or "Finding"),
            value=value,
            display_value=str(finding.get("value")),
            unit=str(finding.get("unit") or "number"),
            source=result.source,
            card_type=result.card_type,
            row=row_index,
            field=str(finding.get("step_id") or "value"),
            period=period,
            dimensions=dimensions,
        ))
    return output


__all__ = ["Fact", "from_results"]
