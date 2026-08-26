"""Deterministic narration, templated from the actual result rows.

The LLM never writes prose about numbers. Every sentence here is assembled from values that
came out of the database, which removes the whole class of "confidently describes a figure
it did not compute" failure — and, as a side effect, closes the prompt-injection vector
that feeding result rows back into a model would open (§7.3).

The narrator also never recommends. "Collections fell 12%" is a fact; "you should tighten
underwriting" is outside the brief.
"""

from __future__ import annotations

from typing import Any

from app.services.nlq.catalog import Catalog, get_catalog
from app.services.nlq.compiler import CompiledQuery
from app.services.nlq.contracts import QuerySpec
from app.services.nlq.executor import QueryResult

CRORE = 10_000_000
LAKH = 100_000


def humanize_label(label: str) -> str:
    """A catalog label, fit to sit mid-sentence.

    `label.lower()` is the obvious move and it mangles every acronym the catalog has: "PAR
    30" becomes "par 30", "NPA ratio" becomes "npa ratio". Only ordinary Titlecase words are
    lowered; anything already carrying capitals — an acronym, a code — is left as written.
    """
    words = []
    for word in label.split():
        if word[:1].isupper() and word[1:].islower():
            words.append(word.lower())
        else:
            words.append(word)
    return " ".join(words)


def format_value(value: Any, unit: str) -> str:
    """Indian money conventions: crore and lakh, not millions."""
    if value is None:
        return "no data"
    if not isinstance(value, (int, float)):
        return str(value)

    if unit == "inr":
        magnitude = abs(value)
        if magnitude >= CRORE:
            return f"₹{value / CRORE:,.2f} Cr"
        if magnitude >= LAKH:
            return f"₹{value / LAKH:,.2f} L"
        return f"₹{value:,.0f}"
    if unit == "percent":
        return f"{value:.2f}%" if abs(value) < 1 else f"{value:.1f}%"
    if unit in ("count", "days"):
        return f"{value:,.0f}"
    return f"{value:,.2f}"


TIME_CHARTS = frozenset({"line", "area", "stacked_area", "small_multiples"})
"""Forms whose x-axis is time, so the summary should describe movement rather than rank."""


def narrate(
    spec: QuerySpec,
    compiled: CompiledQuery,
    result: QueryResult,
    rows: list[dict[str, Any]],
    chart_type: str,
    catalog: Catalog | None = None,
) -> str:
    cat = catalog or get_catalog()

    if result.status == "empty" or not rows:
        return _empty_summary(spec, compiled, cat)

    metric = cat.metrics[spec.metrics[0]]
    parts: list[str] = []

    if chart_type == "kpi":
        parts.append(_kpi_sentence(spec, compiled, rows, cat))
    elif chart_type in ("variance", "dumbbell"):
        parts.append(_variance_sentence(compiled, rows, metric))
    elif chart_type in TIME_CHARTS:
        parts.append(_trend_sentence(spec, compiled, rows, metric, cat))
    else:
        parts.append(_ranking_sentence(spec, compiled, rows, metric, cat))

    parts.append(_definition_sentence(spec, cat))

    # A KPI tile already states the single value; repeating "every value is zero" adds
    # nothing. On a chart with several bars it is the point worth making.
    if chart_type not in ("kpi", "variance", "dumbbell"):
        zero_note = _all_zero_note(rows, metric)
        if zero_note:
            parts.append(zero_note)

    if compiled.signoff_pending:
        labels = ", ".join(cat.metrics[m].label for m in compiled.signoff_pending)
        parts.append(f"Definition of {labels} is pending client sign-off.")

    return " ".join(p for p in parts if p)


def _filter_phrase(spec: QuerySpec, cat: Catalog) -> str:
    """Name the slice the number was measured over.

    A filtered KPI otherwise reads as the whole book: "Loans sanctioned was 76 in all time"
    is the count of *closed* accounts, and the sentence that omits the filter is the one
    people quote.
    """
    parts = []
    for filt in spec.filters:
        dimension = cat.dimensions.get(filt.field)
        if dimension is None or filt.op != "eq" or filt.value is None:
            continue
        enum = cat.enum_for_dimension(dimension.decode) if dimension.decode else None
        label = enum.label_for(str(filt.value)) if enum else str(filt.value)
        parts.append(f"{dimension.label.lower()} {label}")
    return (" for " + " and ".join(parts)) if parts else ""


def _period_phrase(compiled: CompiledQuery) -> str:
    if compiled.as_of:
        return f"as at {compiled.as_of.strftime('%d %b %Y')}"
    return f"in {compiled.period_label}" if compiled.period_label else ""


def _kpi_sentence(
    spec: QuerySpec, compiled: CompiledQuery, rows: list[dict[str, Any]], cat: Catalog
) -> str:
    row = rows[0]
    pieces = []
    for metric_id in spec.metrics:
        metric = cat.metrics[metric_id]
        pieces.append(f"{metric.label} was {format_value(row.get(metric_id), metric.unit)}")
    scope = f"{_filter_phrase(spec, cat)} {_period_phrase(compiled)}".strip()
    return f"{'; '.join(pieces)} {scope}.".replace("  ", " ").strip()


def _ranking_sentence(
    spec: QuerySpec,
    compiled: CompiledQuery,
    rows: list[dict[str, Any]],
    metric,
    cat: Catalog,
) -> str:
    dim_id = next((d for d in spec.dimensions if not cat.dimensions[d].is_time), None)
    if dim_id is None:
        return _kpi_sentence(spec, compiled, rows, cat)

    dim = cat.dimensions[dim_id]
    values = [r for r in rows if isinstance(r.get(metric.id), (int, float))]
    if not values:
        return f"{metric.label} by {dim.label.lower()} {_period_phrase(compiled)}."

    ranked = sorted(values, key=lambda r: r[metric.id], reverse=True)
    top = ranked[0]
    total = sum(r[metric.id] for r in ranked)
    share = (top[metric.id] / total * 100) if total else None

    if len(ranked) == 1:
        value = format_value(top[metric.id], metric.unit)
        measure = (
            f"{value} {metric.label.lower()}"
            if metric.unit == "count"
            else f"{metric.label.lower()} of {value}"
        )
        return (
            f"{top.get(dim_id)} is the only {dim.label.lower()} returned, with {measure} "
            f"{_period_phrase(compiled)}."
        ).replace("  ", " ")

    sentence = (
        f"{top.get(dim_id)} has the highest {metric.label.lower()}, at "
        f"{format_value(top[metric.id], metric.unit)} {_period_phrase(compiled)}"
    )
    # Share of total is meaningless for a percentage metric — PAR values do not sum to
    # anything, so "36% of the total PAR" would be a number with no referent.
    if share is not None and metric.unit != "percent" and len(ranked) > 1:
        sentence += (
            f", {share:.0f}% of the total across {_plural(len(ranked), dim.label.lower())}"
        )
    return sentence + "."


def _definition_sentence(spec: QuerySpec, cat: Catalog) -> str:
    """Explain what the result measures, not just which number is largest."""
    definitions: list[str] = []
    for metric_id in spec.metrics:
        metric = cat.metrics[metric_id]
        formula = " ".join(metric.formula.split()).rstrip(".")
        if formula:
            formula = formula[:1].lower() + formula[1:]
            definitions.append(
                formula if len(spec.metrics) == 1 else f"{metric.label}: {formula}"
            )
    if not definitions:
        return ""

    if len(definitions) == 1:
        sentence = f"This measures {definitions[0]}"
    else:
        sentence = "The figures use these governed definitions: " + "; ".join(definitions)

    grouped = [cat.dimensions[d].label.lower() for d in spec.dimensions]
    if grouped:
        sentence += f", grouped by {' and '.join(grouped)}"
    return sentence.rstrip(".") + "."


def _plural(count: int, noun: str) -> str:
    if count == 1:
        return f"1 {noun}"
    suffix = "es" if noun.endswith(("s", "x", "ch", "sh")) else "s"
    return f"{count} {noun}{suffix}"


def _trend_sentence(
    spec: QuerySpec,
    compiled: CompiledQuery,
    rows: list[dict[str, Any]],
    metric,
    cat: Catalog,
) -> str:
    points = [r for r in rows if isinstance(r.get(metric.id), (int, float))]
    gaps = len(rows) - len(points)

    if len(points) < 2:
        base = f"{metric.label} {_period_phrase(compiled)}."
        if gaps:
            base += f" {gaps} period(s) have no data."
        return base

    first, last = points[0], points[-1]
    change = last[metric.id] - first[metric.id]
    direction = "rose" if change > 0 else "fell" if change < 0 else "was unchanged"
    time_dim = next((d for d in spec.dimensions if cat.dimensions[d].is_time), None)

    sentence = (
        f"{metric.label} {direction} from {format_value(first[metric.id], metric.unit)} "
        f"({first.get(time_dim)}) to {format_value(last[metric.id], metric.unit)} "
        f"({last.get(time_dim)})"
    )
    if change and first[metric.id]:
        sentence += f", a change of {abs(change / first[metric.id] * 100):.1f}%"
    sentence += "."
    if gaps:
        sentence += f" {gaps} period(s) in this range have no underlying data."
    return sentence


def _variance_sentence(compiled: CompiledQuery, rows: list[dict[str, Any]], metric) -> str:
    totals_now = sum(r["current"] for r in rows if isinstance(r.get("current"), (int, float)))
    totals_before = sum(
        r["previous"] for r in rows if isinstance(r.get("previous"), (int, float))
    )
    if not totals_before:
        return (
            f"{metric.label} was {format_value(totals_now, metric.unit)} in "
            f"{compiled.period_label}; there is no comparable figure for "
            f"{compiled.compare_label}."
        )
    delta = totals_now - totals_before
    direction = "up" if delta > 0 else "down" if delta < 0 else "flat"
    delta_text = (
        f"{abs(delta):.1f} percentage points"
        if metric.unit == "percent"
        else format_value(abs(delta), metric.unit)
    )
    return (
        f"{metric.label} is {direction} {delta_text} "
        f"({abs(delta / totals_before * 100):.1f}% relative) in {compiled.period_label} "
        f"versus {compiled.compare_label}."
    )


def _all_zero_note(rows: list[dict[str, Any]], metric) -> str:
    """A real zero is a finding; say so, so nobody reads it as a broken query."""
    values = [r.get(metric.id) for r in rows]
    numeric = [v for v in values if isinstance(v, (int, float))]
    if numeric and all(v == 0 for v in numeric):
        return f"Every value is zero — this is a real result, not a failed query."
    return ""


def _empty_summary(spec: QuerySpec, compiled: CompiledQuery, cat: Catalog) -> str:
    """Name the filters that produced the empty result, so it can be corrected.

    "No results" alone leaves the user unable to tell a wrong filter from a genuine
    absence.
    """
    metric = cat.metrics[spec.metrics[0]]
    clauses = []
    for flt in spec.filters:
        dim = cat.dimensions.get(flt.field)
        label = dim.label if dim else flt.field
        clauses.append(f"{label} {flt.op} {flt.value}")

    sentence = f"No {metric.label.lower()} found {_period_phrase(compiled)}"
    if clauses:
        sentence += f" with {', '.join(clauses)}"
    sentence += "."
    if metric.caveat:
        sentence += " " + " ".join(metric.caveat.split())
    return sentence + " " + _definition_sentence(spec, cat)
