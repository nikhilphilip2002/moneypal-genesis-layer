"""Where an answer can go next.

Every answer carries three or four offered follow-ups, derived from the catalog's drill
graph and the QuerySpec that produced it. Two properties make this worth having as an engine
rather than a prompt:

**No model is involved.** A step is a QuerySpec, built here, executed by `/nlq/execute`.
Tapping a chip is as fast and as reliable as re-running the original question, which is what
lets a director drill six levels in the time it takes to read one chart.

**The ladder is configuration.** This replaces a hardcoded `branch -> product -> scheme`
sequence. Rungs the bank asks for but we cannot source — `region`, `segment` — are declared
`pending` in drill.yaml, so the gap is visible in the catalog rather than invisible in code.
"""

from __future__ import annotations

from datetime import date

from app.services.nlq import periods
from app.services.nlq.catalog import Catalog, get_catalog
from app.services.nlq.contracts import DrillStep, Filter, OrderBy, Period, QuerySpec

DEFAULT_LIMIT = 5
"""More chips than this and nobody reads any of them."""


class DrillError(ValueError):
    """A drill that cannot be built — an unknown dimension, or a member of nothing."""


# --------------------------------------------------------------------------------------
# Offered steps
# --------------------------------------------------------------------------------------


def next_steps(
    spec: QuerySpec,
    catalog: Catalog | None = None,
    *,
    limit: int = DEFAULT_LIMIT,
    today: date | None = None,
) -> list[DrillStep]:
    """The follow-ups this answer offers, best first.

    Order is deliberate, because `limit` cuts from the bottom: down the current path first
    (the question the user is most likely already forming), then "why", then the accounts
    themselves, and only then the alternative axes. Sideways moves are the least urgent and
    the most numerous, so they must never crowd out the step that ends the chain in
    something a team can act on.
    """
    cat = catalog or get_catalog()
    steps: list[DrillStep] = []
    if _is_ambiguous(spec, cat):
        # A two-dimensional grid has no single next level. The accounts behind it are still
        # a coherent question, so that step alone survives.
        act = _act_step(spec, cat) if "act" in cat.drill.offers else None
        return [act] if act else []

    steps.extend(_deeper_steps(spec, cat))
    if "explain" in cat.drill.offers:
        step = _explain_step(spec, cat, today)
        if step is not None:
            steps.append(step)
    if "act" in cat.drill.offers:
        step = _act_step(spec, cat)
        if step is not None:
            steps.append(step)
    steps.extend(_sideways_steps(spec, cat))

    return _dedupe(steps)[:limit]


def _deeper_steps(spec: QuerySpec, cat: Catalog) -> list[DrillStep]:
    current = _current_level(spec, cat)

    if current is None:
        # An undimensioned total. The first split is a choice of axis, not a descent, so
        # offer the heads of the paths that suit any metric.
        return [
            _split_step("deeper", spec, head, cat)
            for head in cat.drill.heads(primary_only=True)
            if head in cat.dimensions
        ]

    path = cat.drill.path_for(current)
    if path is None:
        # A dimension outside every path — the GL, for instance. Inventing a next level here
        # would land the user somewhere arbitrary, which is worse than offering nothing.
        return []
    nxt = path.next_after(current)
    if nxt is None or nxt not in cat.dimensions:
        return []
    return [_split_step("deeper", spec, nxt, cat)]


def _sideways_steps(spec: QuerySpec, cat: Catalog) -> list[DrillStep]:
    current = _current_level(spec, cat)
    if current is None:
        return []
    here = cat.drill.path_for(current)
    steps = []
    for path in cat.drill.paths:
        if path is here or not path.levels:
            continue
        head = path.levels[0]
        if head == cat.drill.entity or head not in cat.dimensions:
            continue  # the entity is the `act` step, not a sideways split
        steps.append(_split_step("sideways", spec, head, cat))
    return steps


def _explain_step(spec: QuerySpec, cat: Catalog, today: date | None) -> DrillStep | None:
    """"Why did that change?" — the same metric, decomposed across its drivers."""
    if spec.explain:
        return None
    metric = cat.metrics.get(spec.metrics[0])
    if metric is None:
        return None

    dimension = _current_level(spec, cat)
    if dimension is None:
        # A change has to be attributed to something. Fall back to the first primary head.
        heads = [h for h in cat.drill.heads(primary_only=True) if h in cat.dimensions]
        if not heads:
            return None
        dimension = heads[0]

    # Never override a comparison the user already chose. On a chart built as "Q3 vs Q1",
    # explaining Q3 vs Q2 answers a question that is not on screen and says nothing about
    # having changed it.
    compare_to = spec.compare_to or _previous_period(spec.period, today)
    if compare_to is None:
        return None

    metrics = [metric.id]
    if metric.weight_metric and metric.weight_metric in cat.metrics:
        # Carry the denominator so the mix/rate split is exact rather than indicative.
        metrics.append(metric.weight_metric)

    drilled = spec.model_copy(
        update={
            "metrics": metrics,
            "dimensions": [dimension],
            "compare_to": compare_to,
            "explain": True,
            "order_by": None,
            "as_share": False,
        }
    )
    label = cat.dimensions[dimension].label.lower()
    return DrillStep(
        kind="explain",
        id=f"explain:{dimension}",
        label="Why did it change?",
        question=f"why {metric.label.lower()} changed, by {label}{_qualifiers(spec, cat)}",
        dimension=dimension,
        spec=drilled,
    )


def _act_step(spec: QuerySpec, cat: Catalog) -> DrillStep | None:
    """The end of every chain: the accounts behind the number."""
    entity = cat.drill.entity
    if entity not in cat.dimensions or entity in spec.dimensions:
        return None
    metric = spec.metrics[0]
    drilled = spec.model_copy(
        update={
            "dimensions": [entity],
            "order_by": OrderBy(field=metric, direction="desc"),
            "limit": min(spec.limit, cat.drill.entity_limit),
            "compare_to": None,
            "explain": False,
            "as_share": False,
        }
    )
    return DrillStep(
        kind="act",
        id=f"act:{entity}",
        label="Show the accounts",
        question=(
            f"{_subject(spec, cat)} by {cat.dimensions[entity].label.lower()}"
            f"{_qualifiers(spec, cat)}"
        ),
        dimension=entity,
        spec=drilled,
    )


def _split_step(kind: str, spec: QuerySpec, dimension: str, cat: Catalog) -> DrillStep:
    drilled = spec.model_copy(
        update={"dimensions": _replace_categorical(spec, dimension, cat), "order_by": None}
    )
    label = cat.dimensions[dimension].label
    return DrillStep(
        kind=kind,  # type: ignore[arg-type]
        id=f"{kind}:{dimension}",
        label=f"By {label.lower()}",
        question=f"{_subject(spec, cat)} by {label.lower()}{_qualifiers(spec, cat)}",
        dimension=dimension,
        spec=drilled,
    )


def _subject(spec: QuerySpec, cat: Catalog) -> str:
    metric = cat.metrics.get(spec.metrics[0])
    return metric.label.lower() if metric else spec.metrics[0]


def _qualifiers(spec: QuerySpec, cat: Catalog) -> str:
    """The period and filters, spelled out in the step's question.

    A step's `spec` is the authoritative version, but the workbench re-asks in words rather
    than executing the spec — its turns have to go through the router to land in history with
    their sources. A bare "disbursement by agent" would then be re-planned with no filter and
    a default period, quietly answering about the whole book when the chart on screen was
    gold loans in Q2.
    """
    parts = []
    for filt in spec.filters:
        dim = cat.dimensions.get(filt.field)
        if dim is None or filt.op != "eq" or filt.value is None:
            continue
        enum = cat.enum_for_dimension(dim.decode) if dim.decode else None
        value = enum.label_for(filt.value) if enum else str(filt.value)
        parts.append(f"for {dim.label.lower()} {value}")

    period = spec.period.relative or (
        f"{spec.period.start} to {spec.period.end}" if spec.period.start else ""
    )
    if period:
        parts.append(f"in {str(period).replace('_', ' ')}")
    return (" " + " ".join(parts)) if parts else ""


# --------------------------------------------------------------------------------------
# Drilling into one member
# --------------------------------------------------------------------------------------


def append_level(spec: QuerySpec, catalog: Catalog | None = None) -> QuerySpec | None:
    """The next level *added* to the current split, rather than swapping it.

    This is what a click on a bar re-runs. It differs from the `deeper` chip on purpose: the
    chip re-splits the same population ("show me agents instead of branches"), while a click
    on a specific bar reads as "go inside this one". Until the click carries its member (see
    `drill_into`), adding the level is the honest approximation — it narrows the view rather
    than widening it, which swapping would.

    Returns None when there is no next level, rather than inventing one.
    """
    cat = catalog or get_catalog()
    if _is_ambiguous(spec, cat):
        return None
    current = _current_level(spec, cat)
    if current is None:
        heads = [h for h in cat.drill.heads(primary_only=True) if h in cat.dimensions]
        nxt = heads[0] if heads else None
    else:
        path = cat.drill.path_for(current)
        nxt = path.next_after(current) if path else None
    if nxt is None or nxt in spec.dimensions or nxt not in cat.dimensions:
        return None
    return spec.model_copy(update={"dimensions": [*spec.dimensions, nxt]})


def drill_into(
    spec: QuerySpec, dimension: str, member: str, catalog: Catalog | None = None
) -> QuerySpec:
    """Clicking a bar: filter to that member, then split by the next level down.

    This is the difference between a chart and a chain. `next_steps` re-splits the whole
    population; this narrows it first, which is what "which branches? … which accounts?"
    actually means.
    """
    cat = catalog or get_catalog()
    if dimension not in cat.dimensions:
        raise DrillError(f"unknown dimension {dimension!r}")

    path = cat.drill.path_for(dimension)
    nxt = path.next_after(dimension) if path else None
    if nxt is None or nxt not in cat.dimensions:
        nxt = cat.drill.entity
    if nxt == dimension or nxt not in cat.dimensions:
        raise DrillError(f"{dimension!r} has no level below it")

    kept = [f for f in spec.filters if f.field != dimension]
    return spec.model_copy(
        update={
            "filters": [*kept, Filter(field=dimension, op="eq", value=member)],
            "dimensions": _replace_categorical(spec, nxt, cat),
            "order_by": None,
        }
    )


# --------------------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------------------


def _categorical_levels(spec: QuerySpec, cat: Catalog) -> list[str]:
    return [d for d in spec.dimensions if (e := cat.dimensions.get(d)) and not e.is_time]


def _is_ambiguous(spec: QuerySpec, cat: Catalog) -> bool:
    """Two categorical splits already — branch x product — so there is no single "current
    level" to descend from, and no honest way to pick one. Offer nothing rather than
    silently drilling one of the two."""
    return len(_categorical_levels(spec, cat)) > 1


def _current_level(spec: QuerySpec, cat: Catalog) -> str | None:
    """The categorical dimension the answer is currently split by, if exactly one."""
    levels = _categorical_levels(spec, cat)
    return levels[0] if len(levels) == 1 else None


def _replace_categorical(spec: QuerySpec, dimension: str, cat: Catalog) -> list[str]:
    """Swap the categorical split, keep the time grain.

    Stacking branch x agent yields a two-dimensional grid nobody asked for; dropping the
    month from a trend loses the shape the question was about. Same rule the conversation
    layer applies to "and by branch?"."""
    time_dims = [d for d in spec.dimensions if (e := cat.dimensions.get(d)) and e.is_time]
    return [*time_dims, dimension]


_RELATIVE_PREDECESSOR = {
    "this_month": "last_month",
    "this_quarter": "last_quarter",
    "this_fy": "last_fy",
    "fy_to_date": "last_fy",
    "ytd": "last_fy",
    "today": "yesterday",
}
"""Where the business already has a word for the previous period, use it: "vs last quarter"
reads better in a subtitle than a pair of dates, and it survives being saved and re-run."""


def _previous_period(period: Period, today: date | None) -> Period | None:
    """The period immediately before this one, for a change to be measured against."""
    named = _RELATIVE_PREDECESSOR.get(period.relative or "")
    if named:
        return Period(grain=period.grain, relative=named)  # type: ignore[arg-type]

    try:
        if period.relative:
            current = periods.resolve_relative(period.relative, today)
        elif period.start and period.end:
            current = periods.DateRange(period.start, period.end, "requested period")
        else:
            return None
        prior = periods.previous_period(current, today)
    except (periods.PeriodError, ValueError):
        return None
    return Period(grain=period.grain, start=prior.start, end=prior.end)


def _dedupe(steps: list[DrillStep]) -> list[DrillStep]:
    seen: set[str] = set()
    out = []
    for step in steps:
        if step.id in seen:
            continue
        seen.add(step.id)
        out.append(step)
    return out


__all__ = ["DrillError", "DrillStep", "append_level", "drill_into", "next_steps"]
