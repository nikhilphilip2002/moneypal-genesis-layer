"""Quantity and period parsing shared by the macro pipeline and workbench compaction.

Both need to pull figures out of Indian financial prose, and both were carrying their own
copy of these patterns. The copies had already diverged — one dropped the magnitude unit
("₹1,200 crore" became a bare 1200), the other missed a word boundary so "yea|rs 2024"
parsed as a rupee amount. One definition, fixed once.

The magnitude word matters enormously here: crore and lakh crore differ by 10,000x, so a
parser that keeps the number and discards the scale produces figures that are not merely
imprecise but wrong by orders of magnitude.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# `\b` before the currency marker is required: without it "yea|rs 2024" and
# "quarte|rs 2025" are read as rupee amounts.
_RUPEE_RE = re.compile(
    r"(?:₹|\brs\.?|\binr)\s?(\d[\d,]*(?:\.\d{1,2})?)"
    r"\s*(lakh\s*crore|thousand\s*crore|crore|lakh|trillion|billion|million)?",
    re.I,
)
_PERCENT_RE = re.compile(r"(-?\d{1,3}(?:\.\d{1,2})?)\s*(?:%|per\s*cent\b|percent\b)", re.I)
_BPS_RE = re.compile(r"(-?\d{1,4})\s*(?:bps\b|basis\s*points?\b)", re.I)
_PP_RE = re.compile(r"(-?\d{1,3}(?:\.\d{1,2})?)\s*(?:percentage\s*points?\b|pp\b)", re.I)

# FY25 / FY2025 / Q1 FY25 / CY2024 / 2026-07 / 2026-07-31
_PERIOD_RE = re.compile(
    r"\b(?:(?:Q[1-4]\s*)?FY\s?\d{2,4}|CY\s?\d{4}|\d{4}-\d{2}(?:-\d{2})?)\b", re.I
)

PERCENT = "percent"
CURRENCY = "currency"
BPS = "bps"
PP = "pp"


@dataclass(frozen=True, slots=True)
class Quantity:
    kind: str      # percent | currency | bps | pp
    value: float   # the number itself
    unit: str      # "%", "crore", "lakh crore", "bps", "pp", or "" when unqualified
    text: str      # normalized for display, e.g. "Rs 1,200 crore"
    start: int     # offset in the source string, for locating the sentence around it


def _to_float(raw: str) -> float:
    try:
        return float(raw.replace(",", ""))
    except ValueError:
        return 0.0


def find_quantities(text: str) -> list[Quantity]:
    """Every percent / rupee / bps / pp quantity in `text`, in order of appearance."""
    found: list[Quantity] = []

    for match in _PERCENT_RE.finditer(text):
        value = _to_float(match.group(1))
        found.append(Quantity(PERCENT, value, "%", f"{match.group(1)}%", match.start()))

    for match in _RUPEE_RE.finditer(text):
        unit = " ".join((match.group(2) or "").split()).lower()
        amount = match.group(1)
        found.append(
            Quantity(
                CURRENCY,
                _to_float(amount),
                unit,
                f"Rs {amount} {unit}".strip(),
                match.start(),
            )
        )

    for match in _BPS_RE.finditer(text):
        value = _to_float(match.group(1))
        found.append(Quantity(BPS, value, "bps", f"{match.group(1)} bps", match.start()))

    for match in _PP_RE.finditer(text):
        value = _to_float(match.group(1))
        found.append(Quantity(PP, value, "pp", f"{match.group(1)} pp", match.start()))

    found.sort(key=lambda quantity: quantity.start)
    return found


def find_period(text: str) -> str:
    """The first period label in `text`, normalized, or "" when there is none."""
    match = _PERIOD_RE.search(text)
    return match.group(0).upper().replace(" ", "") if match else ""
