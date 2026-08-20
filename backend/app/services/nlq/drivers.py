"""Why a number moved: contribution decomposition over two result sets.

The system was good at reporting *what* a number is and had nothing to say about *why* it
changed — so "why did collections fall?" degraded into a breakdown, which does not answer
it. This module is that answer, and it is arithmetic rather than an opinion: the model is
never asked to attribute a change, because a model asked to explain a delta will produce a
fluent attribution whether or not one exists in the data.

Two cases, and the difference between them is the whole design.

**Flow and point-in-time metrics add up.** Disbursement fell by 40 lakh; each branch's fall
sums to exactly that. Contribution is a subtraction and share is a division.

**Ratios do not.** A weighted average can fall while every member rises, purely because the
weak members grew. So a ratio's change is split into two exact terms:

    rate_i = w_i0 * (r_i1 - r_i0)          each member's own ratio moved
    mix_i  = (w_i1 - w_i0) * (r_i1 - R0)   the population re-weighted underneath it

which sum, over all members, to exactly R1 - R0. That identity is the reason the weight
(the metric's denominator, named in metrics.yaml as `weight_metric`) has to be carried
through the query rather than approximated here. Without weights the split is impossible,
and this module says so and withholds the shares rather than presenting a plausible number.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Sequence

from app.services.nlq.catalog import Catalog, get_catalog
from app.services.nlq.catalog.loader import canonical_enum_code
from app.services.nlq.narrator import format_value, humanize_label

DEFAULT_TOP_N = 6
"""Past six bars a waterfall stops being readable and starts being a table."""

DEFAULT_COVERAGE = 0.8
"""Stop once the shown movers account for this much of the total absolute movement. The
long tail of 0.3% contributors is noise that makes the real driver harder to see."""

_MISSING = object()

NO_WEIGHT_CAVEAT = (
    "This is a ratio, and ratio changes do not add up across members. Each figure is that "
    "member's own change; they are not shares of the total change."
)


@dataclass(frozen=True, slots=True)
class Contribution:
    """One member's part in the change."""

    member: str
    label: str
    current: float
    prior: float
    delta: float
    """For a ratio with weights this is the member's contribution to the *total's* change
    (rate + mix). For everything else it is simply current - prior."""
    share: float | None = None
    """Fraction of the total change. None when the total change is zero, or when the metric
    is a ratio whose weights were not supplied — in both cases a share would be fiction."""
    mix_effect: float = 0.0
    rate_effect: float = 0.0
    weight_current: float = 0.0
    weight_prior: float = 0.0


@dataclass(frozen=True, slots=True)
class Decomposition:
    metric: str
    label: str
    unit: str
    dimension: str
    dimension_label: str
    current_total: float
    prior_total: float
    delta: float
    contributions: tuple[Contribution, ...]
    """The shown movers, largest absolute contribution first."""
    all_contributions: tuple[Contribution, ...] = ()
    """Every member, before truncation. This is what the sum-to-total invariant is checked
    on, and what an export or a deeper drill reads."""
    other: Contribution | None = None
    """Everything below the cut, rolled up so the parts still sum to the whole."""
    is_ratio: bool = False
    exact: bool = True
    """False when a ratio was decomposed without weights: the per-member changes are real,
    but they do not compose into the total's change."""
    totals_known: bool = True
    """False when the totals could not be computed at all. A ratio's total is a weighted
    average, so without weights there is no honest value to report — and an unweighted mean
    of the members would contradict the figure the compiler produced for the same metric on
    the chart directly above. The narration then names no total rather than a wrong one."""
    caveat: str = ""

    @property
    def direction(self) -> str:
        if self.delta > 0:
            return "rose"
        if self.delta < 0:
            return "fell"
        return "held"


# --------------------------------------------------------------------------------------
# Decomposition
# --------------------------------------------------------------------------------------


def decompose(
    metric_id: str,
    dimension: str,
    current_rows: Sequence[dict[str, Any]],
    prior_rows: Sequence[dict[str, Any]],
    catalog: Catalog | None = None,
    *,
    weight_metric: str | None = None,
    top_n: int = DEFAULT_TOP_N,
    coverage: float = DEFAULT_COVERAGE,
) -> Decomposition:
    """Attribute the change in `metric_id` across the members of `dimension`.

    `weight_metric` is only consulted for ratios. Pass it (normally
    `catalog.metrics[metric_id].weight_metric`) when the rows carry the denominator, and the
    mix/rate split is exact; omit it and the result is honest about being indicative.
    """
    cat = catalog or get_catalog()
    metric = cat.metrics.get(metric_id)
    if metric is None:
        raise KeyError(f"unknown metric {metric_id!r}")

    dim = cat.dimensions.get(dimension)
    dim_label = dim.label if dim else dimension
    enum = cat.enum_for_dimension(dim.decode) if dim and dim.decode else None

    current = _index(current_rows, dimension, metric_id, weight_metric)
    prior = _index(prior_rows, dimension, metric_id, weight_metric)
    members = sorted(set(current) | set(prior))

    is_ratio = metric.is_ratio
    totals_known = True
    has_weights = bool(weight_metric) and any(
        w for _, w in current.values()
    ) or bool(weight_metric) and any(w for _, w in prior.values())

    if is_ratio and has_weights:
        contributions, current_total, prior_total = _ratio_contributions(
            members, current, prior, enum, dim_label
        )
        exact, caveat = True, ""
    elif is_ratio:
        contributions, current_total, prior_total = _unweighted_ratio_contributions(
            members, current, prior, enum, dim_label
        )
        exact, caveat, totals_known = False, NO_WEIGHT_CAVEAT, False
    else:
        contributions, current_total, prior_total = _additive_contributions(
            members, current, prior, enum, dim_label
        )
        exact, caveat = True, ""

    delta = current_total - prior_total
    contributions = _with_shares(contributions, delta, attributable=exact)
    ranked = tuple(sorted(contributions, key=lambda c: abs(c.delta), reverse=True))

    shown, other = _truncate(ranked, top_n=top_n, coverage=coverage)
    if delta == 0 and exact:
        # Nothing moved in aggregate. Members that individually moved are still real and
        # still ranked, but there is no change to attribute them to.
        shown = shown if any(c.delta for c in ranked) else ()

    return Decomposition(
        metric=metric.id,
        label=metric.label,
        unit=metric.unit,
        dimension=dimension,
        dimension_label=dim_label,
        current_total=current_total,
        prior_total=prior_total,
        delta=delta,
        contributions=shown,
        other=other,
        all_contributions=ranked,
        is_ratio=is_ratio,
        exact=exact,
        totals_known=totals_known,
        caveat=caveat,
    )


def _index(
    rows: Sequence[dict[str, Any]], dimension: str, metric_id: str, weight_metric: str | None
) -> dict[str, tuple[float, float]]:
    """member -> (metric value, weight). Rows arrive from the executor, so values may be
    Decimal or None; both are coerced once here rather than at every use."""
    out: dict[str, tuple[float, float]] = {}
    for row in rows:
        # Key on the raw code, never the decoded label. The current period's rows have been
        # through `_decode_rows` (branch 1 -> "Head Office") while the prior period's come
        # straight from the executor, so keying on the display value makes the two member
        # sets disjoint: every member is then counted twice, once as a pure gain and once as
        # a pure loss, and every share is nonsense. `_variance_rows` has always read `__raw`
        # for the same reason.
        raw = row.get(f"{dimension}__raw", row.get(dimension, _MISSING))
        if raw is _MISSING:
            continue
        member = canonical_enum_code(raw)
        value = _number(row.get(metric_id))
        weight = _number(row.get(weight_metric)) if weight_metric else 0.0
        out[member] = (value, weight)
    return out


def _number(value: Any) -> float:
    if value is None:
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _label_for(member: str, enum, dim_label: str) -> str:
    if enum is not None:
        return enum.label_for(member)
    return member if member else f"(no {humanize_label(dim_label)})"


def _additive_contributions(members, current, prior, enum, dim_label):
    contributions = []
    current_total = prior_total = 0.0
    for member in members:
        c = current.get(member, (0.0, 0.0))[0]
        p = prior.get(member, (0.0, 0.0))[0]
        current_total += c
        prior_total += p
        contributions.append(
            Contribution(
                member=member,
                label=_label_for(member, enum, dim_label),
                current=c,
                prior=p,
                delta=c - p,
            )
        )
    return contributions, current_total, prior_total


def _ratio_contributions(members, current, prior, enum, dim_label):
    """The exact two-term split. See the module docstring for the identity."""
    weight_current = sum(current.get(m, (0.0, 0.0))[1] for m in members)
    weight_prior = sum(prior.get(m, (0.0, 0.0))[1] for m in members)

    # Recomputed from numerator and denominator, never averaged from the member ratios —
    # the same invariant the compiler enforces for ratio metrics.
    current_total = (
        sum(current.get(m, (0.0, 0.0))[0] * current.get(m, (0.0, 0.0))[1] for m in members)
        / weight_current
        if weight_current
        else 0.0
    )
    prior_total = (
        sum(prior.get(m, (0.0, 0.0))[0] * prior.get(m, (0.0, 0.0))[1] for m in members)
        / weight_prior
        if weight_prior
        else 0.0
    )

    contributions = []
    for member in members:
        r1, d1 = current.get(member, (0.0, 0.0))
        r0, d0 = prior.get(member, (0.0, 0.0))
        w1 = d1 / weight_current if weight_current else 0.0
        w0 = d0 / weight_prior if weight_prior else 0.0
        # A member absent from the prior period has w0 = 0, so the rate term vanishes
        # regardless of what r0 is taken to be, and its whole effect lands in mix — which
        # is exactly right: it is new business, not a rate move.
        rate = w0 * (r1 - r0)
        mix = (w1 - w0) * (r1 - prior_total)
        contributions.append(
            Contribution(
                member=member,
                label=_label_for(member, enum, dim_label),
                current=r1,
                prior=r0,
                delta=rate + mix,
                mix_effect=mix,
                rate_effect=rate,
                weight_current=d1,
                weight_prior=d0,
            )
        )
    return contributions, current_total, prior_total


def _unweighted_ratio_contributions(members, current, prior, enum, dim_label):
    """No weights: report each member's own move and claim nothing about the total.

    An unweighted mean of the member ratios is *not* the metric — the compiler computes the
    weighted value — so publishing one here would put two different numbers for the same
    metric on two adjacent cards. The totals are reported as unknown instead."""
    contributions = []
    for member in members:
        c = current.get(member, (0.0, 0.0))[0]
        p = prior.get(member, (0.0, 0.0))[0]
        contributions.append(
            Contribution(
                member=member,
                label=_label_for(member, enum, dim_label),
                current=c,
                prior=p,
                delta=c - p,
            )
        )
    return contributions, 0.0, 0.0


def _with_shares(
    contributions: list[Contribution], delta: float, *, attributable: bool
) -> list[Contribution]:
    """A share of a zero change, or of a change the parts do not compose into, is not a
    small number — it is an undefined one. Withhold it rather than round it."""
    if not attributable or delta == 0:
        return contributions


    return [replace(c, share=c.delta / delta) for c in contributions]


def _truncate(
    ranked: tuple[Contribution, ...], *, top_n: int, coverage: float
) -> tuple[tuple[Contribution, ...], Contribution | None]:
    """Keep the movers that matter; roll the rest into one row that preserves the total."""
    if len(ranked) <= top_n:
        return ranked, None

    total_movement = sum(abs(c.delta) for c in ranked)
    shown: list[Contribution] = []
    seen = 0.0
    for contribution in ranked:
        if len(shown) >= top_n:
            break
        shown.append(contribution)
        seen += abs(contribution.delta)
        if total_movement and seen / total_movement >= coverage:
            break

    rest = ranked[len(shown) :]
    if not rest:
        return tuple(shown), None

    # A rolled-up share is known when every part's share is known. `sum(...) or None` would
    # report a bucket whose parts genuinely net to zero as *unknown*, which this module
    # reserves for shares that would be fiction.
    shares = [c.share for c in rest]
    other = Contribution(
        member="__other__",
        label=f"All other {len(rest)}",
        current=sum(c.current for c in rest),
        prior=sum(c.prior for c in rest),
        delta=sum(c.delta for c in rest),
        share=sum(shares) if all(s is not None for s in shares) else None,  # type: ignore[arg-type]
        mix_effect=sum(c.mix_effect for c in rest),
        rate_effect=sum(c.rate_effect for c in rest),
    )
    return tuple(shown), other


# --------------------------------------------------------------------------------------
# Narration
# --------------------------------------------------------------------------------------


def narrate(decomposition: Decomposition, catalog: Catalog | None = None) -> str:
    """The sentence under the waterfall. Templated, so every figure in it came from above.

    Deliberately not a model call: this is the one sentence a director will quote in a
    meeting, and it has to be reproducible."""
    d = decomposition
    unit = d.unit
    if catalog is not None and not d.label:
        d = replace(d, label=catalog.metrics[d.metric].label)

    if not d.totals_known:
        # No weights, so there is no total to move between. Report only what is known: how
        # many members moved, and which moved most.
        movers = [c for c in d.all_contributions if c.delta]
        if not movers:
            return f"{d.label} was unchanged across every {humanize_label(d.dimension_label)}."
        top = movers[0]
        return (
            f"{d.label} moved at {len(movers)} of {len(d.all_contributions)} "
            f"{humanize_label(d.dimension_label)} values. The largest is {top.label} at "
            f"{_signed(top.delta, unit)}. {d.caveat}"
        )

    if d.delta == 0:
        return f"{d.label} was unchanged at {format_value(d.current_total, unit)}."

    head = (
        f"{d.label} {d.direction} from {format_value(d.prior_total, unit)} to "
        f"{format_value(d.current_total, unit)} "
        f"({_signed(d.delta, unit)})."
    )

    if not d.contributions:
        return head

    top = d.contributions[0]
    parts = [head]

    if d.is_ratio and d.exact:
        driver = "rate" if abs(top.rate_effect) >= abs(top.mix_effect) else "mix"
        parts.append(
            f"The largest mover is {top.label} at {_signed(top.delta, unit)}, mostly a "
            f"{driver} effect ({_signed(top.rate_effect, unit)} rate, "
            f"{_signed(top.mix_effect, unit)} mix)."
        )
    elif top.share is not None:
        parts.append(
            f"{top.label} accounts for {abs(top.share) * 100:.0f}% of the change "
            f"({_signed(top.delta, unit)})."
        )
    else:
        parts.append(f"The largest mover is {top.label} at {_signed(top.delta, unit)}.")

    if d.caveat:
        parts.append(d.caveat)
    return " ".join(parts)


def _signed(value: float, unit: str) -> str:
    formatted = format_value(abs(value), unit)
    return f"{'+' if value >= 0 else '-'}{formatted}"


__all__ = ["Contribution", "Decomposition", "decompose", "narrate"]
