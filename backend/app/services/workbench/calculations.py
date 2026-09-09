"""Deterministic calculations over governed facts."""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from app.services.workbench.facts import Fact

MAX_DERIVED_FACTS = 400
"""Upper bound on derived facts per answer so the fact set stays prompt-sized."""

MAX_PAIRWISE_ROWS = 12
"""Groups up to this size get every pair compared; larger groups keep consecutive pairs
and the endpoints, which is what period-over-period prose actually cites."""

MAX_RATE_FIELDS = 4
"""Cross-field rates are computed over at most this many numeric fields of a row."""

_NON_ADDITIVE_UNITS = frozenset({"percent", "ratio", "rank"})


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


def _quantize(value: Decimal) -> Decimal:
    """Six decimal places is beyond any rendered precision and keeps ids stable."""
    return value.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP).normalize()


def _derived(
    *, operation: str, value: Decimal, unit: str, operands: tuple[str, ...],
    label: str, period: str, formula: str, dimensions: tuple[tuple[str, str], ...] = (),
) -> Fact:
    value = _quantize(value)
    return Fact(
        id=f"calc:{operation}:" + "~".join(operands),
        label=label,
        value=value,
        display_value=format(value, "f"),
        unit=unit,
        source="calculation",
        card_type="derived",
        row=0,
        field=operation,
        period=period,
        dimensions=dimensions,
        formula=formula,
        operands=operands,
        operation=operation,
    )


def _card(fact: Fact) -> str:
    parts = fact.id.split(":")
    return parts[1] if len(parts) > 1 else ""


def _describe(fact: Fact) -> str:
    where = ", ".join(f"{name}={value}" for name, value in fact.dimensions)
    return f"{fact.label} [{where}]" if where else fact.label


def _pairs(count: int) -> list[tuple[int, int]]:
    if count <= MAX_PAIRWISE_ROWS:
        return [(i, j) for i in range(count) for j in range(i + 1, count)]
    pairs = [(i, i + 1) for i in range(count - 1)]
    pairs.append((0, count - 1))
    return pairs


def _series_facts(group: list[Fact]) -> list[Fact]:
    """Total, share, rank, delta and percentage change over one measure across rows."""
    out: list[Fact] = []
    period = group[0].period
    unit = group[0].unit
    additive = unit not in _NON_ADDITIVE_UNITS
    ids = tuple(fact.id for fact in group)
    if additive:
        total = sum((fact.value for fact in group), Decimal(0))
        out.append(_derived(
            operation="total", value=total, unit=unit, operands=ids,
            label=f"Total {group[0].label}", period=period, formula="sum(operands)",
        ))
        if total != 0:
            for fact in group:
                out.append(_derived(
                    operation="share", value=fact.value / total * 100, unit="percent",
                    operands=(fact.id, out[0].id), label=f"Share of total: {_describe(fact)}",
                    period=period, formula="operand / total * 100", dimensions=fact.dimensions,
                ))
    ordered = sorted(group, key=lambda fact: fact.value, reverse=True)
    rank = 0
    previous: Decimal | None = None
    for position, fact in enumerate(ordered, start=1):
        if previous is None or fact.value != previous:
            rank = position
            previous = fact.value
        out.append(_derived(
            operation="rank", value=Decimal(rank), unit="rank", operands=(fact.id,),
            label=f"Rank by {fact.label}: {_describe(fact)}", period=period,
            formula="1 = highest value", dimensions=fact.dimensions,
        ))
    for i, j in _pairs(len(group)):
        earlier, later = group[i], group[j]
        out.append(_derived(
            operation="difference", value=later.value - earlier.value, unit=unit,
            operands=(later.id, earlier.id),
            label=f"Change: {_describe(later)} minus {_describe(earlier)}",
            period=period, formula="later - earlier",
        ))
        # Both bases: "up 23% on B" and "19% below A" are the same pair, different base.
        for base, other in ((earlier, later), (later, earlier)):
            if base.value != 0:
                out.append(_derived(
                    operation="percent_change",
                    value=(other.value - base.value) / base.value * 100, unit="percent",
                    operands=(other.id, base.id),
                    label=f"Percent change: {_describe(other)} vs {_describe(base)}",
                    period=period, formula="(other - base) / base * 100",
                ))
    return out


def _rate_facts(row: list[Fact]) -> list[Fact]:
    """Cross-field rates within one row, e.g. collected / demanded."""
    out: list[Fact] = []
    fields = row[:MAX_RATE_FIELDS]
    for numerator in fields:
        for denominator in fields:
            if numerator is denominator or denominator.value == 0:
                continue
            if numerator.unit in _NON_ADDITIVE_UNITS or denominator.unit in _NON_ADDITIVE_UNITS:
                continue
            out.append(_derived(
                operation="rate", value=numerator.value / denominator.value * 100,
                unit="percent", operands=(numerator.id, denominator.id),
                label=f"Rate: {numerator.label} / {denominator.label}"
                + (f" [{', '.join(f'{k}={v}' for k, v in numerator.dimensions)}]"
                   if numerator.dimensions else ""),
                period=numerator.period, formula="numerator / denominator * 100",
                dimensions=numerator.dimensions,
            ))
    return out


def derived_facts(ledger: list[Fact]) -> list[Fact]:
    """Deterministic derived facts over verified source facts.

    Every derived fact carries its operands, operation, unit and formula so a numeric
    claim in the answer can be traced to governed inputs. Nothing here consults the
    model; the set is a function of the ledger alone.
    """
    series: dict[tuple[str, str, str, str], list[Fact]] = {}
    rows: dict[tuple[str, int, str], list[Fact]] = {}
    for fact in ledger:
        if not fact.verified or fact.source == "calculation":
            continue
        card = _card(fact)
        field = fact.field if fact.card_type == "chart" else ""
        series.setdefault((card, field, fact.unit, fact.period), []).append(fact)
        if fact.card_type == "chart":
            rows.setdefault((card, fact.row, fact.period), []).append(fact)
    out: list[Fact] = []
    for group in series.values():
        if len(group) > 1:
            out.extend(_series_facts(group))
    for row in rows.values():
        if len(row) > 1:
            out.extend(_rate_facts(row))
    seen: set[str] = set()
    unique: list[Fact] = []
    for fact in out:
        if fact.id not in seen:
            seen.add(fact.id)
            unique.append(fact)
    return unique[:MAX_DERIVED_FACTS]


def fact_set(ledger: list[Fact]) -> list[Fact]:
    """Source facts followed by their deterministic derivations."""
    return [*ledger, *derived_facts(ledger)]


__all__ = [
    "CalculationError",
    "MAX_DERIVED_FACTS",
    "derive",
    "derived_facts",
    "fact_set",
    "weighted_average",
]
