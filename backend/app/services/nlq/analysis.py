"""Questions that take more than one query.

`QuerySpec` answers "what is our PAR 30". It cannot answer "how is the business doing, and
what are the five things I need to know?", which is eight queries plus a ranking of what is
notable. This module is that second shape.

Three properties carry the design.

**The steps are ordinary QuerySpecs.** They compile, execute, cache, mask and drill exactly
like a hand-typed question, so an analysis adds no new database surface and no second code
path to keep honest.

**The composition is code, not a prompt.** A model asked to summarise eight result sets will
produce a confident narrative whether or not the numbers support it. Here the findings are
templated from rows and ranked by thresholds the bank ratified in `analyses.yaml`; a
narrative, if one is generated at all, is written *over the findings* and can restate a
number but cannot introduce one.

**"Notable" has a definition.** `watch_*`/`alert_*` in the catalog are what make the ranking
reproducible. Without them, "the five things I need to know" is whatever the model felt
strongly about that run.
"""

from __future__ import annotations

import concurrent.futures
import logging
import threading
from dataclasses import dataclass
from datetime import date
from statistics import median
from typing import Any, Iterable, Sequence

from app.services.nlq import drilldown
from app.services.nlq.catalog import Catalog, get_catalog
from app.services.nlq.catalog.loader import AnalysisDef, AnalysisStepDef, canonical_enum_code
from app.services.nlq.contracts import (
    AnalysisResult,
    AnalysisSpec,
    AnalysisStep,
    AxisSpec,
    ChartSpec,
    ColumnSpec,
    Filter,
    Finding,
    Lineage,
    OrderBy,
    Period,
    QuerySpec,
    SeriesSpec,
)
from app.services.nlq.narrator import format_value, humanize_label

logger = logging.getLogger(__name__)

MAX_WORKERS = 4
"""One less than the read-only pool, so an analysis can never starve a concurrent question."""

_STEP_SLOTS = threading.Semaphore(MAX_WORKERS)
"""Process-wide, not per-analysis. Capping each analysis at four workers only holds while
one analysis runs at a time; two directors opening a briefing together asked for eight
connections from a pool of five, and the surplus steps failed on a ten-second acquire
timeout — reported to the reader as "could not be answered" rather than as load. Holding the
budget here keeps a step queued instead of failed, and always leaves one connection free for
someone asking an ordinary question."""

TOP_FINDINGS = 5
""""The five things I need to know" is the actual ask, and a briefing that lists everything
has ranked nothing."""


class AnalysisError(ValueError):
    """An analysis that cannot be built — an unknown preset, or a preset the catalog lost."""


@dataclass(slots=True)
class StepResult:
    step: AnalysisStep
    chart: ChartSpec | None = None
    error: str = ""


# --------------------------------------------------------------------------------------
# Build
# --------------------------------------------------------------------------------------


def build(
    analysis_id: str,
    *,
    catalog: Catalog | None = None,
    period: Period | None = None,
    filters: Sequence[Filter] = (),
) -> AnalysisSpec:
    """Turn a catalog preset into runnable steps, bound to a period and filters.

    The binding is the planner's whole contribution: it picks the preset and says which
    period and which slice of the book. Everything else was reviewed when the preset was
    written.
    """
    cat = catalog or get_catalog()
    definition = cat.analyses.get(analysis_id)
    if definition is None:
        raise AnalysisError(f"unknown analysis {analysis_id!r}")

    resolved_period = period or _default_period(definition)
    steps = [
        AnalysisStep(
            id=step.id,
            label=step.label,
            spec=_step_spec(step, resolved_period, filters),
            watch_above=step.watch_above,
            watch_below=step.watch_below,
            alert_above=step.alert_above,
            alert_below=step.alert_below,
            note=step.note,
        )
        for step in definition.steps
    ]
    return AnalysisSpec(
        id=definition.id,
        title=definition.title,
        compose=definition.compose,  # type: ignore[arg-type]
        steps=steps,
        subtitle=_subtitle(resolved_period, filters, cat),
    )


def _default_period(definition: AnalysisDef) -> Period:
    raw = dict(definition.default_period or {})
    if not raw:
        return Period(relative="this_month")
    return Period.model_validate(raw)


def _step_spec(step: AnalysisStepDef, period: Period, filters: Sequence[Filter]) -> QuerySpec:
    order_by = None
    if step.order_by:
        order_by = OrderBy(
            field=step.order_by["field"], direction=step.order_by.get("direction", "desc")
        )
    return QuerySpec(
        metrics=list(step.metrics),
        dimensions=list(step.dimensions),
        filters=list(filters),
        period=period,
        order_by=order_by,
        limit=step.limit or 200,
        as_share=step.as_share,
    )


def _subtitle(period: Period, filters: Sequence[Filter], cat: Catalog) -> str:
    parts = []
    if period.relative:
        parts.append(period.relative.replace("_", " "))
    elif period.start and period.end:
        parts.append(f"{period.start} to {period.end}")
    for filt in filters:
        dim = cat.dimensions.get(filt.field)
        if dim is None or filt.op != "eq" or filt.value is None:
            continue
        enum = cat.enum_for_dimension(dim.decode) if dim.decode else None
        value = enum.label_for(filt.value) if enum else str(filt.value)
        parts.append(f"{humanize_label(dim.label)} {value}")
    return " · ".join(parts)


# --------------------------------------------------------------------------------------
# Run
# --------------------------------------------------------------------------------------


def run(
    spec: AnalysisSpec,
    *,
    catalog: Catalog | None = None,
    today: date | None = None,
    role: str | None = None,
) -> AnalysisResult:
    """Execute every step, then compose. Steps run concurrently on the read-only pool.

    A step that fails does not fail the analysis: seven of eight answers with one gap named
    is far more useful to a director than an error page, and the gap is stated rather than
    silently dropped.
    """
    cat = catalog or get_catalog()
    from app.services.nlq.pipeline import run_spec

    def one(step: AnalysisStep) -> StepResult:
        try:
            with _STEP_SLOTS:
                return StepResult(step=step, chart=run_spec(step.spec, catalog=cat, today=today,
                                                            role=role))
        except Exception as exc:  # noqa: BLE001 - one bad step must not lose the other seven
            logger.warning("analysis step %s failed: %s", step.id, exc)
            return StepResult(step=step, error=str(exc))

    workers = min(MAX_WORKERS, len(spec.steps))
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        results = list(pool.map(one, spec.steps))
    return compose(spec, results, cat)


# --------------------------------------------------------------------------------------
# Compose
# --------------------------------------------------------------------------------------


def compose(
    spec: AnalysisSpec, results: Sequence[StepResult], catalog: Catalog | None = None
) -> AnalysisResult:
    """Turn step results into findings, a headline and charts. Pure and deterministic."""
    cat = catalog or get_catalog()
    composer = {
        "briefing": _compose_briefing,
        "concentration": _compose_concentration,
        "quadrant": _compose_quadrant,
    }.get(spec.compose)
    if composer is None:  # pragma: no cover - the catalog validator rejects these
        raise AnalysisError(f"unknown composer {spec.compose!r}")

    result = composer(spec, results, cat)
    for failed in (r for r in results if r.error):
        result.warnings.append(f"{failed.step.label} could not be answered.")
    return result


def _compose_briefing(
    spec: AnalysisSpec, results: Sequence[StepResult], cat: Catalog
) -> AnalysisResult:
    findings: list[Finding] = []
    charts: list[ChartSpec] = []

    for result in results:
        if result.chart is None or not result.chart.rows:
            # An empty result is not a zero. "PAR 30 is 0.0%" for a query that matched
            # nothing is the most dangerous number this product could print.
            continue
        charts.append(result.chart)
        finding = _finding_for(result, cat)
        if finding is not None:
            findings.append(finding)

    findings.sort(key=_notability)
    flagged = [f for f in findings if f.severity != "info"]

    if flagged:
        headline = (
            f"{len(flagged)} of {len(findings)} indicators need attention: "
            + ", ".join(humanize_label(f.label) for f in flagged[:3])
            + "."
        )
    elif findings:
        headline = f"Nothing is outside its threshold across {len(findings)} indicators."
    else:
        headline = "No indicator returned data for this period."

    return AnalysisResult(
        id=spec.id,
        title=spec.title,
        subtitle=spec.subtitle,
        compose=spec.compose,
        headline=headline,
        findings=findings[:TOP_FINDINGS],
        charts=charts,
    )


def _finding_for(result: StepResult, cat: Catalog) -> Finding | None:
    """One line per step: the headline number, or the largest member of a breakdown."""
    step, chart = result.step, result.chart
    assert chart is not None
    metric_id = step.spec.metrics[0]
    metric = cat.metrics.get(metric_id)
    if metric is None:
        return None

    if step.spec.dimensions:
        return _breakdown_finding(step, chart, metric, cat)

    value = _number(chart.rows[0].get(metric_id))
    if value is None:
        return None
    severity = _severity(value, step)
    # A colon rather than "is": step labels are a mix of singular and plural ("PAR 30",
    # "Delinquent accounts"), and no single verb is grammatical for both.
    clause = _threshold_clause(severity, value, step, metric.unit)
    return Finding(
        step_id=step.id,
        label=step.label,
        text=f"{step.label}: {format_value(value, metric.unit)}{clause}.",
        value=value,
        unit=metric.unit,  # type: ignore[arg-type]
        severity=severity,
        spec=step.spec,
        question=drilldown.describe(step.spec, cat),
    )


def _breakdown_finding(step: AnalysisStep, chart: ChartSpec, metric, cat: Catalog) -> Finding | None:
    dimension = next(
        (d for d in step.spec.dimensions if not cat.dimensions[d].is_time), None
    )
    if dimension is None:
        return None

    ranked = [r for r in chart.rows if _number(r.get(metric.id)) is not None]
    if not ranked:
        return None
    # A ratio's "largest member" is only meaningful the way the question asks for it, so
    # respect the step's own ordering when it declared one.
    reverse = not (step.spec.order_by and step.spec.order_by.direction == "asc")
    ranked.sort(key=lambda r: _number(r.get(metric.id)) or 0.0, reverse=reverse)
    top = ranked[0]
    value = _number(top.get(metric.id)) or 0.0
    label = _member_label(top, dimension)
    total = sum(_number(r.get(metric.id)) or 0.0 for r in ranked)
    share = f" — {value / total * 100:.0f}% of the total" if total and metric.grain != "ratio" else ""

    return Finding(
        step_id=step.id,
        label=step.label,
        text=(
            f"{step.label}: {label} leads at {format_value(value, metric.unit)}{share}, "
            f"across {len(ranked)} {humanize_label(cat.dimensions[dimension].label)} values."
        ),
        value=value,
        unit=metric.unit,  # type: ignore[arg-type]
        severity=_severity(value, step),
        spec=step.spec,
        question=drilldown.describe(step.spec, cat),
    )


def _member_label(row: dict[str, Any] | None, dimension: str) -> str:
    """Rows reaching here are decoded, so the display value is already present."""
    if not row:
        return ""
    value = row.get(dimension, row.get(f"{dimension}__raw"))
    return str(value) if value not in (None, "") else f"(no {dimension})"


def _severity(value: float, step: AnalysisStep) -> str:
    """Thresholds are the bank's, from analyses.yaml. Alert is checked before watch."""
    if step.alert_above is not None and value > step.alert_above:
        return "alert"
    if step.alert_below is not None and value < step.alert_below:
        return "alert"
    if step.watch_above is not None and value > step.watch_above:
        return "watch"
    if step.watch_below is not None and value < step.watch_below:
        return "watch"
    return "info"


def _threshold_clause(severity: str, value: float, step: AnalysisStep, unit: str) -> str:
    """Name the bound that actually fired, so the reader can see why it was flagged."""
    if severity == "info":
        return ""
    upper = step.alert_above if severity == "alert" else step.watch_above
    if upper is not None and value > upper:
        return f", above the {severity} threshold of {format_value(upper, unit)}"
    lower = step.alert_below if severity == "alert" else step.watch_below
    if lower is not None and value < lower:
        return f", below the {severity} threshold of {format_value(lower, unit)}"
    return ""


_SEVERITY_RANK = {"alert": 0, "watch": 1, "info": 2}


def _notability(finding: Finding) -> tuple[int, str]:
    return (_SEVERITY_RANK[finding.severity], finding.step_id)


def _compose_concentration(
    spec: AnalysisSpec, results: Sequence[StepResult], cat: Catalog
) -> AnalysisResult:
    """How much of the book sits with how few names: Herfindahl plus the top-10 share."""
    step_result = results[0] if results else None
    step = spec.steps[0]
    metric = cat.metrics[step.spec.metrics[0]]

    rows = step_result.chart.rows if step_result and step_result.chart else []
    values = [v for v in (_number(r.get(metric.id)) for r in rows) if v and v > 0]
    total = sum(values)
    if not values or total <= 0:
        return AnalysisResult(
            id=spec.id, title=spec.title, subtitle=spec.subtitle, compose=spec.compose,
            headline="No exposure was returned for this period.",
            charts=[step_result.chart] if step_result and step_result.chart else [],
        )

    shares = sorted((v / total for v in values), reverse=True)
    hhi = sum(s * s for s in shares)
    top10 = sum(shares[:10]) * 100

    findings = [
        Finding(
            step_id=step.id,
            label="Herfindahl index",
            text=(
                f"The Herfindahl index across {len(values)} borrowers is {hhi:.3f} "
                f"({_hhi_verdict(hhi)})."
            ),
            value=hhi,
            unit="ratio",
            severity=_severity(hhi, step),
            spec=step.spec,
            question=drilldown.describe(step.spec, cat),
        ),
        Finding(
            step_id=step.id,
            label="Top 10 share",
            text=(
                f"The ten largest borrowers hold {top10:.1f}% of "
                f"{format_value(total, metric.unit)} outstanding."
            ),
            value=top10,
            unit="percent",
            severity="info",
            spec=step.spec,
            question=drilldown.describe(step.spec, cat),
        ),
    ]
    return AnalysisResult(
        id=spec.id,
        title=spec.title,
        subtitle=spec.subtitle,
        compose=spec.compose,
        headline=findings[0].text,
        findings=findings,
        charts=[step_result.chart] if step_result and step_result.chart else [],
        warnings=(
            [f"Measured over the largest {len(values)} borrowers returned by the query."]
            if len(values) >= step.spec.limit
            else []
        ),
    )


def _hhi_verdict(hhi: float) -> str:
    if hhi >= 0.25:
        return "highly concentrated"
    if hhi >= 0.15:
        return "moderately concentrated"
    return "not concentrated"


def _compose_quadrant(
    spec: AnalysisSpec, results: Sequence[StepResult], cat: Catalog
) -> AnalysisResult:
    """Two metrics over one dimension, merged here and split at each median.

    The merge is the reason this is an analysis and not a query: the two metrics sit on
    different source tables, and the compiler refuses to join them because doing so would
    double-count. Two correct result sets combined on the dimension is the honest form.

    Cutting at medians rather than absolute thresholds is the other half of the point — the
    question is which branches are better or worse *than the rest of this bank*, which no
    fixed number knows.
    """
    x_step, y_step = spec.steps[0], spec.steps[1]
    x_metric = cat.metrics[x_step.spec.metrics[0]]
    y_metric = cat.metrics[y_step.spec.metrics[0]]
    dimension = x_step.spec.dimensions[0]

    # Both axes or neither. A quadrant built from one surviving step would place every
    # member at zero on the missing axis, and zero arrears is the most flattering position
    # on the grid — a failed query would read as a clean book.
    if any(r.chart is None for r in results[:2]):
        return AnalysisResult(
            id=spec.id, title=spec.title, subtitle=spec.subtitle, compose=spec.compose,
            headline=f"{spec.title} needs both measures, and one of them could not be read.",
            charts=[r.chart for r in results if r.chart],
        )

    rows: list[dict[str, Any]] = []
    for row in _merge_on_dimension(results, dimension).values():
        x, y = _number(row.get(x_metric.id)), _number(row.get(y_metric.id))
        if x is None or y is None:
            continue  # a member on one axis only cannot be placed on a grid
        rows.append({**row, x_metric.id: x, y_metric.id: y})
    if len(rows) < 2:
        return AnalysisResult(
            id=spec.id, title=spec.title, subtitle=spec.subtitle, compose=spec.compose,
            headline="Not enough members to compare.",
            charts=[r.chart for r in results if r.chart],
        )

    x_cut = median(r[x_metric.id] for r in rows)
    y_cut = median(r[y_metric.id] for r in rows)

    # The first step is read as "more is better" and the second as "more is worse", which is
    # what makes "growth against arrears" a quadrant rather than a scatter. A preset pairing
    # two good metrics would need its own composer, not a silent reinterpretation here.
    best = worst = None
    for row in rows:
        high_x = row[x_metric.id] >= x_cut
        high_y = row[y_metric.id] >= y_cut
        row["quadrant"] = _QUADRANTS[(high_x, high_y)]
        if high_x and not high_y and best is None:
            best = row
        if not high_x and high_y and worst is None:
            worst = row

    dim_label = humanize_label(cat.dimensions[dimension].label)
    findings = [
        Finding(
            step_id=x_step.id,
            label="Growing and clean",
            text=(
                f"{_member_label(best, dimension)} is above the median {humanize_label(x_metric.label)} "
                f"and below the median {humanize_label(y_metric.label)}."
                if best
                else f"No {dim_label} is above the median {humanize_label(x_metric.label)} while "
                f"staying below the median {humanize_label(y_metric.label)}."
            ),
            unit="text",
            severity="info",
            spec=x_step.spec,
            question=drilldown.describe(x_step.spec, cat),
        )
    ]
    if worst is not None:
        findings.append(
            Finding(
                step_id=y_step.id,
                label="Needs attention",
                text=(
                    f"{_member_label(worst, dimension)} is below the median "
                    f"{humanize_label(x_metric.label)} and above the median {humanize_label(y_metric.label)}."
                ),
                unit="text",
                severity="watch",
                spec=y_step.spec,
                question=drilldown.describe(y_step.spec, cat),
            )
        )

    chart = _quadrant_chart(spec, results, rows, dimension, x_metric, y_metric, cat)
    return AnalysisResult(
        id=spec.id,
        title=spec.title,
        subtitle=spec.subtitle,
        compose=spec.compose,
        headline=findings[0].text,
        findings=findings,
        charts=[chart],
        warnings=[
            f"Quadrants are cut at the median {humanize_label(x_metric.label)} "
            f"({format_value(x_cut, x_metric.unit)}) and median {humanize_label(y_metric.label)} "
            f"({format_value(y_cut, y_metric.unit)}), not at absolute thresholds."
        ],
    )


def _merge_on_dimension(
    results: Sequence[StepResult], dimension: str
) -> dict[str, dict[str, Any]]:
    """Join step results by dimension member.

    Keyed on the raw code where the rows carry one: the decoded label is a display value and
    two steps that decoded differently would silently produce disjoint member sets — the same
    trap the driver decomposition has to avoid.
    """
    merged: dict[str, dict[str, Any]] = {}
    for result in results:
        if result.chart is None:
            continue
        for row in result.chart.rows:
            raw = row.get(f"{dimension}__raw", row.get(dimension))
            if raw is None:
                continue
            key = canonical_enum_code(raw)
            entry = merged.setdefault(key, {dimension: row.get(dimension, key)})
            for name, value in row.items():
                entry.setdefault(name, value)
    # Only members present in *both* steps can be placed on two axes.
    wanted = [r for r in results if r.chart is not None]
    metrics = {m for r in wanted for m in r.step.spec.metrics}
    return {k: v for k, v in merged.items() if all(m in v for m in metrics)}


def _quadrant_chart(
    spec: AnalysisSpec,
    results: Sequence[StepResult],
    rows: list[dict[str, Any]],
    dimension: str,
    x_metric,
    y_metric,
    cat: Catalog,
) -> ChartSpec:
    """One scatter over the merged rows, with both steps' lineage kept intact.

    A merged answer whose lineage named only one of its two queries would be untraceable
    exactly where tracing matters most.
    """
    lineages = [r.chart.lineage for r in results if r.chart is not None]
    merged_lineage = Lineage(
        path="queryspec",
        sql="\n\n-- and --\n\n".join(lin.sql for lin in lineages),
        display_sql="\n\n-- and --\n\n".join(lin.display_sql for lin in lineages if lin.display_sql),
        source_tables=sorted({t for lin in lineages for t in lin.source_tables}),
        formulas={k: v for lin in lineages for k, v in lin.formulas.items()},
        row_count=len(rows),
        duration_ms=sum(lin.duration_ms for lin in lineages),
        warnings=[w for lin in lineages for w in lin.warnings],
        requires_signoff=sorted({m for lin in lineages for m in lin.requires_signoff}),
    )
    return ChartSpec(
        chart_type="scatter",
        title=spec.title,
        subtitle=spec.subtitle or None,
        x=AxisSpec(field=x_metric.id, label=x_metric.label, unit=x_metric.unit),
        series=[SeriesSpec(field=y_metric.id, label=y_metric.label, unit=y_metric.unit)],
        columns=[
            ColumnSpec(name=dimension, label=cat.dimensions[dimension].label, unit="text"),
            ColumnSpec(name=x_metric.id, label=x_metric.label, unit=x_metric.unit),
            ColumnSpec(name=y_metric.id, label=y_metric.label, unit=y_metric.unit),
            ColumnSpec(name="quadrant", label="Quadrant", unit="text", sensitivity="public"),
        ],
        rows=rows,
        lineage=merged_lineage,
    )


_QUADRANTS = {
    (True, False): "Growing, clean",
    (True, True): "Growing, risky",
    (False, False): "Slow, clean",
    (False, True): "Slow, risky",
}


def _number(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def presets(catalog: Catalog | None = None) -> Iterable[AnalysisDef]:
    return (catalog or get_catalog()).analyses.values()


__all__ = ["AnalysisError", "StepResult", "build", "compose", "presets", "run"]
