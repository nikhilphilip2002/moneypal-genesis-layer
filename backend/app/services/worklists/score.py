"""The priority order, as arithmetic anyone can check.

Pure: rows in, ranked rows out, no database and no catalog lookups beyond the score model.
That is what makes "why is this account third and not first?" a test rather than an argument.

**Percentile rank, not min-max.** One ₹5 Cr account would otherwise compress every other row
to nearly zero on the exposure term, and the list would sort by exposure alone — which is
emphatically not what a collections day looks like. Ranking within the candidate set keeps
each component contributing the share of the score its weight says it should.

**A missing value is not a zero.** An account with no recorded last payment has an unknown
days-since-payment, not a payment today. It receives the median rank on that component, so
the missing field neither promotes nor demotes it, and the row says so.
"""

from __future__ import annotations

from typing import Any, Sequence

from app.services.nlq.catalog.loader import ScoreModel
from app.services.nlq.contracts import ScoreWeight

NEUTRAL = 0.5
"""The rank given to a row whose component value is missing — the middle of the field."""


def prioritise(
    rows: Sequence[dict[str, Any]], model: ScoreModel
) -> list[tuple[float, list[ScoreWeight]]]:
    """Score every row, returning (score, the terms behind it) in the input order.

    The terms are returned rather than logged because they are shown on the card. A ranking
    whose order cannot be interrogated gets trusted once, tested against an account the
    officer already knows, and then ignored for good.
    """
    if not rows:
        return []

    ranks = {c.id: _percentile_ranks([_number(r.get(c.id)) for r in rows]) for c in model.components}

    out: list[tuple[float, list[ScoreWeight]]] = []
    for index in range(len(rows)):
        weights: list[ScoreWeight] = []
        total = 0.0
        for component in model.components:
            value = ranks[component.id][index]
            contribution = component.weight * value
            total += contribution
            weights.append(
                ScoreWeight(
                    id=component.id,
                    label=component.label,
                    weight=component.weight,
                    value=round(value, 4),
                    contribution=round(contribution, 4),
                )
            )
        out.append((round(total, 4), weights))
    return out


def _percentile_ranks(values: Sequence[float | None]) -> list[float]:
    """Each value's position in the field, 0 (lowest) to 1 (highest).

    Ties share a rank, so two accounts with identical arrears cannot be separated by the
    order they happened to come back from the database.
    """
    present = sorted(v for v in values if v is not None)
    if not present:
        return [NEUTRAL] * len(values)
    if len(present) == 1:
        return [NEUTRAL if v is None else 1.0 for v in values]

    # Rank by how many distinct values sit below this one, so the spread is over the values
    # the list actually contains rather than over its row count.
    distinct = sorted(set(present))
    if len(distinct) == 1:
        return [NEUTRAL if v is None else 1.0 for v in values]
    position = {value: index / (len(distinct) - 1) for index, value in enumerate(distinct)}
    return [NEUTRAL if v is None else position[v] for v in values]


def _number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


__all__ = ["NEUTRAL", "prioritise"]
