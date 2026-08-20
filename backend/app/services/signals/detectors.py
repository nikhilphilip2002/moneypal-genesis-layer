"""What counts as notable, as arithmetic.

Every detector here is a pure function over a series of numbers. That is the whole design:
"what are the emerging issues?" is the question a director most wants answered and the one an
LLM is worst at, because it has no baseline and will confidently call an ordinary month
unusual. A z-score against eight prior periods either clears the bar or it does not.

**Abstention is a result.** Genesis holds very little history — the portfolio snapshot starts
2026-05-22 and the disbursement event log 2025-10-15 — so most series are short. A detector
with too few prior periods returns nothing rather than a verdict computed from two points. A
signals feed that fires on noise is worse than no feed: it trains the reader to ignore it,
and then the real one arrives and gets ignored too.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence

MIN_BASELINE = 5
"""Prior periods needed before a z-score means anything. Below this the standard deviation is
mostly an artefact of the sample size, and every series looks alarming roughly a third of the
time."""

Z_WATCH = 2.0
Z_ALERT = 3.0
"""Two sigma is unusual; three is unusual enough to interrupt someone's morning."""

RANK_MOVE = 3
"""Places a member must move before it is worth reporting. Branches shuffle by one or two
between months for no reason anybody can act on."""

FLAT_EPSILON = 1e-9

MIN_DISPERSION = 0.005
"""The baseline's standard deviation must be at least this fraction of its own level before
a z-score means anything.

An absolute floor is not enough. Collection efficiency sat within a whisker of itself for
eight months — a real, non-zero standard deviation, but a vanishing one — and the current
month came back as *31 standard deviations* from the average. A 31-sigma reading is never a
finding; it is a degenerate baseline, and printing it beside a genuine two-sigma move
teaches the reader that the number is decorative."""


@dataclass(frozen=True, slots=True)
class Detection:
    """One notable thing, before it is dressed up as a Signal.

    `magnitude` and `baseline` travel with it because a signal that says only "PAR 30 is
    unusual" is a signal the reader has to go and check. "PAR 30 is 8.1% against a
    trailing average of 4.6%" is one they can act on or dismiss without leaving the page.
    """

    kind: str
    severity: str
    direction: str  # "up" | "down" | "flat"
    magnitude: float
    baseline: float | None = None
    detail: str = ""


def level_shift(series: Sequence[float | None]) -> Detection | None:
    """Is the latest value out of line with the ones before it?

    The classic z-score, with two guards that matter more than the statistic:

    * fewer than `MIN_BASELINE` priors and it abstains, because Genesis's history is short;
    * a baseline with no meaningful spread abstains. A perfectly flat one gives a zero
      standard deviation and an infinite z-score, and a nearly flat one is barely better:
      collection efficiency sat within a whisker of itself for eight months and the next
      reading scored 31 sigma. Neither is a finding; both are degenerate baselines, and a
      metric that behaves this way belongs to the threshold detector instead.
    """
    values = [v for v in series if v is not None]
    if len(values) < MIN_BASELINE + 1:
        return None

    current, prior = values[-1], values[:-1]
    mean = sum(prior) / len(prior)
    variance = sum((v - mean) ** 2 for v in prior) / len(prior)
    deviation = math.sqrt(variance)
    if deviation < FLAT_EPSILON:
        return None

    # A baseline with no meaningful spread cannot support a z-score, whatever the absolute
    # arithmetic says. Such a metric is judged against a threshold instead, or not at all.
    if abs(mean) > FLAT_EPSILON and deviation / abs(mean) < MIN_DISPERSION:
        return None

    z = (current - mean) / deviation
    if abs(z) < Z_WATCH:
        return None

    return Detection(
        kind="level_shift",
        severity="alert" if abs(z) >= Z_ALERT else "watch",
        direction="up" if z > 0 else "down",
        magnitude=round(z, 2),
        baseline=round(mean, 4),
        detail=f"{abs(z):.1f} standard deviations from its {len(prior)}-period average",
    )


def trend_break(series: Sequence[float | None]) -> Detection | None:
    """Has a run in one direction reversed?

    Three or more consecutive moves one way, then a move the other way. This is what people
    mean by "it has turned", and it fires on series a z-score never will — a metric that
    drifts steadily has a wide standard deviation and hides its own inflection inside it.
    """
    values = [v for v in series if v is not None]
    if len(values) < 5:
        return None

    deltas = [b - a for a, b in zip(values, values[1:])]
    latest = deltas[-1]
    if abs(latest) < FLAT_EPSILON:
        return None

    run = 0
    for delta in reversed(deltas[:-1]):
        if delta == 0 or (delta > 0) != (latest < 0):
            break
        run += 1
    if run < 3:
        return None

    return Detection(
        kind="trend_break",
        severity="watch",
        direction="up" if latest > 0 else "down",
        magnitude=round(latest, 4),
        baseline=round(values[-2], 4),
        detail=f"reversed after {run} periods moving the other way",
    )


def threshold_breach(
    value: float | None,
    *,
    watch_above: float | None = None,
    alert_above: float | None = None,
    watch_below: float | None = None,
    alert_below: float | None = None,
) -> Detection | None:
    """A policy or prudential limit crossed. No history needed, which is why it is the only
    detector that works on the metrics Genesis has barely any history for."""
    if value is None:
        return None

    for bound, severity in ((alert_above, "alert"), (watch_above, "watch")):
        if bound is not None and value > bound:
            return Detection(
                kind="threshold", severity=severity, direction="up",
                magnitude=round(value - bound, 4), baseline=bound,
                detail=f"above the {severity} threshold of {bound}",
            )
    for bound, severity in ((alert_below, "alert"), (watch_below, "watch")):
        if bound is not None and value < bound:
            return Detection(
                kind="threshold", severity=severity, direction="down",
                magnitude=round(bound - value, 4), baseline=bound,
                detail=f"below the {severity} threshold of {bound}",
            )
    return None


def concentration(
    values: Sequence[float | None], *, watch_hhi: float, alert_hhi: float
) -> Detection | None:
    """Herfindahl index over a set of exposures.

    Structural rather than statistical: this does not ask whether concentration changed, it
    asks whether the book is concentrated, which is the actual prudential question.
    """
    present = [v for v in values if v is not None and v > 0]
    total = sum(present)
    if not present or total <= 0:
        return None

    hhi = sum((v / total) ** 2 for v in present)
    if hhi < watch_hhi:
        return None

    return Detection(
        kind="concentration",
        severity="alert" if hhi >= alert_hhi else "watch",
        direction="up",
        magnitude=round(hhi, 4),
        baseline=watch_hhi,
        detail=f"Herfindahl index {hhi:.3f} across {len(present)} members",
    )


def rank_movement(
    current: dict[str, float | None], prior: dict[str, float | None]
) -> list[tuple[str, Detection]]:
    """Members that moved several places in the ranking.

    Reported per member, because "branch 12 fell from 3rd to 11th" is a question with an
    owner, while "the ranking changed" is not. Members absent from either period are skipped
    rather than treated as last: an account that did not exist has no rank to have moved from.
    """
    shared = [
        m for m in current
        if m in prior and current[m] is not None and prior[m] is not None
    ]
    if len(shared) < RANK_MOVE + 1:
        return []

    def positions(values: dict[str, float | None]) -> dict[str, int]:
        ordered = sorted(shared, key=lambda m: values[m], reverse=True)  # type: ignore[arg-type]
        return {member: index + 1 for index, member in enumerate(ordered)}

    now, before = positions(current), positions(prior)
    out: list[tuple[str, Detection]] = []
    for member in shared:
        move = before[member] - now[member]
        if abs(move) < RANK_MOVE:
            continue
        out.append((
            member,
            Detection(
                kind="rank_movement",
                severity="watch",
                direction="up" if move > 0 else "down",
                magnitude=float(abs(move)),
                baseline=float(before[member]),
                detail=f"moved from #{before[member]} to #{now[member]}",
            ),
        ))
    return out


def staleness(days_since: int | None, *, watch_days: int, alert_days: int) -> Detection | None:
    """How old the freshest row in a table is.

    This is the honest answer to "which data issues are affecting performance": a metric
    computed over a table that stopped loading four days ago is not wrong, it is stale, and
    every number derived from it is quietly about last Tuesday. Worth its own detector
    because nothing else in the product notices.
    """
    if days_since is None:
        return Detection(
            kind="data_health", severity="alert", direction="flat", magnitude=0.0,
            detail="no dated rows at all",
        )
    if days_since < watch_days:
        return None
    return Detection(
        kind="data_health",
        severity="alert" if days_since >= alert_days else "watch",
        direction="flat",
        magnitude=float(days_since),
        baseline=float(watch_days),
        detail=f"newest row is {days_since} days old",
    )


__all__ = [
    "MIN_BASELINE",
    "MIN_DISPERSION",
    "RANK_MOVE",
    "Z_ALERT",
    "Z_WATCH",
    "Detection",
    "concentration",
    "level_shift",
    "rank_movement",
    "staleness",
    "threshold_breach",
    "trend_break",
]
