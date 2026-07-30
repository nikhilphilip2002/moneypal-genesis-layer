"""Metric semantics — the rules that stop a structurally valid query being nonsense.

The catalog says what a metric *is*; this module says what may be done with it. It runs
before any SQL is generated, so a rejected query never reaches the database.

The rule that earns its keep is the grain rule. PAR is a point-in-time ratio: summing it
across months is meaningless, and averaging monthly PAR is not annual PAR. Disbursement is
a flow and must be summed. Getting this wrong produces a confident, plausible, wrong
number — the failure mode that ends the project.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.services.nlq.catalog import Catalog, Metric, get_catalog
from app.services.nlq.contracts import QuerySpec


class MetricError(ValueError):
    """A query that the metric registry refuses. The message is shown to the user, so it
    explains what is wrong in business terms rather than naming a column."""


@dataclass(frozen=True, slots=True)
class MetricPlan:
    """What the compiler needs to know about the metrics in one query."""

    metrics: tuple[Metric, ...]
    base_table: str
    needs_as_of: bool
    signoff_pending: tuple[str, ...]
    warnings: tuple[str, ...]


def resolve(spec: QuerySpec, catalog: Catalog | None = None) -> MetricPlan:
    """Validate a spec's metrics and return the plan, or raise MetricError."""
    cat = catalog or get_catalog()

    unknown = [m for m in spec.metrics if m not in cat.metrics]
    if unknown:
        raise MetricError(
            f"unknown metric(s): {', '.join(unknown)}. "
            f"Available: {', '.join(sorted(cat.metrics))}"
        )
    metrics = tuple(cat.metrics[m] for m in spec.metrics)

    # Dimensions are validated first: every later check indexes into cat.dimensions, and an
    # unknown name there would surface as a KeyError traceback instead of a usable message.
    _check_dimensions_exist(spec, cat)
    _check_single_base_table(metrics)
    _check_time_grain(spec, metrics, cat)
    _check_dimension_compatibility(spec, metrics, cat)

    warnings = [m.caveat.strip() for m in metrics if m.caveat.strip()]
    coverage = _coverage_warnings(metrics, cat)

    return MetricPlan(
        metrics=metrics,
        base_table=metrics[0].base_table,
        needs_as_of=any(m.needs_as_of for m in metrics),
        signoff_pending=tuple(m.id for m in metrics if m.requires_signoff),
        warnings=tuple(dict.fromkeys([*warnings, *coverage])),
    )


def _check_single_base_table(metrics: tuple[Metric, ...]) -> None:
    """One query, one fact table.

    Metrics from different fact tables can be combined — but only by aggregating each to
    the requested grain separately and joining the results, never by joining the fact
    tables first (which fans out and multiplies money). That machinery is deliberately not
    built yet: refusing is honest, whereas a silent cross-fact join is not.
    """
    tables = {m.base_table for m in metrics}
    if len(tables) > 1:
        by_table = {t: [m.id for m in metrics if m.base_table == t] for t in sorted(tables)}
        detail = "; ".join(f"{t.split('.')[-1]}: {', '.join(ids)}" for t, ids in by_table.items())
        raise MetricError(
            "these metrics come from different source tables and cannot be combined in one "
            f"query without double-counting ({detail}). Ask for them separately."
        )


def _check_time_grain(spec: QuerySpec, metrics: tuple[Metric, ...], cat: Catalog) -> None:
    """The grain rule (§2.2)."""
    time_dims = [cat.dimensions[d] for d in spec.dimensions if cat.dimensions[d].is_time]

    for metric in metrics:
        if metric.grain == "point_in_time" and time_dims and not metric.needs_as_of:
            raise MetricError(
                f"'{metric.label}' is a point-in-time figure with no history in the data — "
                "it cannot be broken down over time. Ask for it as a single value instead."
            )
        if metric.no_time_travel and (spec.period.start or spec.period.relative not in (None, "today")):
            raise MetricError(
                f"'{metric.label}' is only available as of the latest data load and cannot "
                "be back-dated. For a historical view use a metric based on the "
                "classification history."
            )
        if metric.grain == "point_in_time" and spec.compare_to and not metric.needs_as_of:
            raise MetricError(
                f"'{metric.label}' cannot be compared across periods — it has a single "
                "as-of value."
            )


def _check_dimensions_exist(spec: QuerySpec, cat: Catalog) -> None:
    names = [*spec.dimensions, *(f.field for f in spec.filters)]
    unknown = [d for d in names if d not in cat.dimensions]
    if unknown:
        raise MetricError(
            f"unknown dimension(s): {', '.join(sorted(set(unknown)))}. "
            f"Available: {', '.join(sorted(cat.dimensions))}"
        )


def _check_dimension_compatibility(
    spec: QuerySpec, metrics: tuple[Metric, ...], cat: Catalog
) -> None:
    """A GL metric cannot group by loan scheme (§2.5 rule 2)."""
    base_table = metrics[0].base_table
    base_entry = cat.table_by_name(base_table)
    hub = next(t.table for t in cat.tables.values() if t.is_hub)

    for dim_id in spec.dimensions:
        dim = cat.dimensions[dim_id]
        if dim.is_time or dim.table == base_table:
            continue
        # Reaching a dimension on another table needs a declared route: either the
        # dimension sits on the hub and the base table joins to it, or it sits on a table
        # the base table joins to directly.
        if cat.join_between(base_table, dim.table) is not None:
            continue
        if dim.table == hub or cat.join_between(base_table, hub) is not None:
            if cat.join_between(hub, dim.table) is not None or dim.table == hub:
                continue
        restriction = (base_entry.restrictions if base_entry else "") or (
            "there is no declared join between these tables"
        )
        raise MetricError(
            f"'{metrics[0].label}' cannot be grouped by {dim.label.lower()} — "
            f"{restriction.strip()}"
        )


def _coverage_warnings(metrics: tuple[Metric, ...], cat: Catalog) -> list[str]:
    """Surface a source table's known coverage gaps on every answer that reads it.

    A user comparing a PAR denominator against the board pack should learn about the
    classified-subset gap from the answer, not from the discrepancy.
    """
    out = []
    for table in {m.base_table for m in metrics}:
        entry = cat.table_by_name(table)
        if entry and entry.coverage_warning.strip():
            out.append(" ".join(entry.coverage_warning.split()))
    return out


def formulas_for(metric_ids: list[str], catalog: Catalog | None = None) -> dict[str, str]:
    """Metric id -> human-readable formula, for the lineage panel."""
    cat = catalog or get_catalog()
    return {mid: cat.metrics[mid].formula for mid in metric_ids if mid in cat.metrics}
