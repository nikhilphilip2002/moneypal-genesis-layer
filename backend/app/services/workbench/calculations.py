"""Deterministic calculations over governed facts."""

from __future__ import annotations

from decimal import Decimal

from app.services.workbench.facts import Fact


class CalculationError(ValueError):
    pass


def _compatible_context(left: Fact, right: Fact, *, same_period: bool) -> None:
    if not left.period or not right.period:
        raise CalculationError("operand periods are incompatible or missing")
    if same_period and left.period != right.period:
        raise CalculationError("operand periods are incompatible or missing")
    if left.dimensions != right.dimensions:
        raise CalculationError("operand grains are incompatible")


def derive(operation: str, left: Fact, right: Fact, *, fact_id: str, label: str) -> Fact:
    if not left.verified or not right.verified:
        raise CalculationError("derived facts require verified operands")
    if operation in {"difference", "sum", "percent_change", "ratio", "share"} and left.unit != right.unit:
        raise CalculationError("operand units are incompatible")
    _compatible_context(
        left,
        right,
        same_period=operation in {"sum", "ratio", "share"},
    )
    if operation == "difference":
        value, unit, formula = left.value - right.value, left.unit, "left - right"
    elif operation == "sum":
        value, unit, formula = left.value + right.value, left.unit, "left + right"
    elif operation in {"ratio", "share"}:
        if right.value == 0:
            raise CalculationError("division by zero")
        value = left.value / right.value
        unit = "percent" if operation == "share" else "ratio"
        if operation == "share":
            value *= Decimal(100)
        formula = "left / right" + (" * 100" if operation == "share" else "")
    elif operation == "percent_change":
        if right.value == 0:
            raise CalculationError("division by zero")
        value, unit, formula = (left.value - right.value) / right.value * 100, "percent", "(left - right) / right * 100"
    else:
        raise CalculationError(f"unsupported operation {operation!r}")
    return Fact(
        id=fact_id, label=label, value=value, display_value=str(value), unit=unit,
        source="calculation", card_type="derived", row=0, field=label,
        period=(
            left.period
            if left.period == right.period
            else f"{left.period} vs {right.period}"
        ),
        formula=formula, operands=(left.id, right.id), operation=operation,
    )


def weighted_average(
    values: list[Fact], weights: list[Fact], *, fact_id: str, label: str,
) -> Fact:
    if not values or len(values) != len(weights):
        raise CalculationError("weighted average needs matching values and weights")
    if any(not fact.verified for fact in [*values, *weights]):
        raise CalculationError("derived facts require verified operands")
    unit = values[0].unit
    if any(value.unit != unit for value in values):
        raise CalculationError("value units are incompatible")
    period = values[0].period
    if not period or any(
        value.period != period
        or weight.period != period
        or value.dimensions != weight.dimensions
        for value, weight in zip(values, weights)
    ):
        raise CalculationError("operand periods are incompatible or missing")
    total_weight = sum((weight.value for weight in weights), Decimal(0))
    if total_weight == 0:
        raise CalculationError("division by zero")
    value = sum(
        (item.value * weight.value for item, weight in zip(values, weights)), Decimal(0)
    ) / total_weight
    operands = tuple(fact.id for pair in zip(values, weights) for fact in pair)
    return Fact(
        id=fact_id,
        label=label,
        value=value,
        display_value=str(value),
        unit=unit,
        source="calculation",
        card_type="derived",
        row=0,
        field=label,
        period=period,
        formula="sum(value * weight) / sum(weight)",
        operands=operands,
        operation="weighted_average",
    )


__all__ = ["CalculationError", "derive", "weighted_average"]
