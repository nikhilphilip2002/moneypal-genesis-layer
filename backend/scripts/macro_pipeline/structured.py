"""Structured macro extraction — rule-based topic classification + figure mining.

Every chunk downstream gets two enrichments:

    topics       -> ["gdp_growth", "inflation_cpi", ...]           (classification)
    figures      -> [{"value": 6.5, "unit": "%", "about": "GDP growth",
                      "sentence": "real GDP grew 6.5 per cent in FY25"}, ...]

Figures are mined with regex for per-cent / rupee(xx crore / lakh) / bps / pp
amounts, each tagged with the topic it belongs to based on nearby keywords.
"""
from __future__ import annotations

import re
from typing import Iterable

from app.services import figures as figure_parser

from . import macro_topics


# Sentence boundary = terminal punctuation followed by whitespace and the start of a
# new sentence. Splitting on a bare "." instead would cut every decimal in half —
# "bond yield is 6.7%" becomes the sentence "bond yield is 6." and the figure loses
# the context that makes it classifiable.
_SENTENCE_BREAK_RE = re.compile(r"(?<=[.!?])\s+(?=[\"'(\[]?[A-Z‘“])")

_MAX_FIGURES_PER_CHUNK = 25


def _clean(amount: str) -> float:
    amount = amount.replace(",", "")
    try:
        return float(amount)
    except ValueError:
        return 0.0


def _sentence_spans(text: str) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    start = 0
    for match in _SENTENCE_BREAK_RE.finditer(text):
        spans.append((start, match.start()))
        start = match.end()
    spans.append((start, len(text)))
    return spans


def _sentence_around(text: str, match_start: int) -> str:
    for start, end in _sentence_spans(text):
        if start <= match_start < end:
            sentence = " ".join(text[start:end].split())
            # A "sentence" spanning a whole table row carries no useful context and
            # would bloat the payload; fall back to a tight window around the number.
            if len(sentence) <= 400:
                return sentence
            break
    window = max(0, match_start - 120)
    return " ".join(text[window : match_start + 120].split())


def _figure(kind: str, value: float, unit: str, about: str, sentence: str) -> dict:
    return {
        "kind": kind,
        "value": round(value, 2),
        "unit": unit,
        "about": about,
        "sentence": sentence[:280],
    }


def _topic_for_about(text: str) -> str:
    """Pick the topic that best explains a figure by scanning keywords near the number."""
    topics = macro_topics.classify_topics(text)
    return topics[0] if topics else "macro_general"


def extract_figures(text: str) -> list[dict]:
    """Mine per-cent, rupee, bps and pp figures (deduplicated, capped).

    Parsing comes from `app.services.figures`, shared with workbench compaction. The
    magnitude word is carried through as the unit: a figure recorded as 1200 without
    "crore" is not merely imprecise, it is wrong by four orders of magnitude.
    """
    figures: list[dict] = [
        _figure(
            quantity.kind,
            quantity.value,
            quantity.unit or "amount",
            _topic_for_about(_sentence_around(text, quantity.start)),
            _sentence_around(text, quantity.start),
        )
        for quantity in figure_parser.find_quantities(text)
    ]

    # Dedupe near-identical (value, unit, sentence) rows.
    seen: set[tuple] = set()
    unique: list[dict] = []
    for fig in figures:
        key = (round(fig["value"], 2), fig["unit"], fig["sentence"][:60])
        if key in seen:
            continue
        seen.add(key)
        unique.append(fig)
        if len(unique) >= _MAX_FIGURES_PER_CHUNK:
            break
    return unique


def extract_topics(text: str) -> list[str]:
    """Topic ids, strongest first; empty when the chunk is unclassified."""
    return macro_topics.classify_topics(text)


def extract_snapshot(rows: Iterable[dict]) -> Iterable[dict]:
    """Augment extraction rows with topics + figures before embedding/upsert.

    ``rows`` match the schema produced by extractor.extract_many: every row gets
    ``topics`` (list of ids) and ``figures`` (list of dicts) added in place.
    """
    for row in rows:
        text: str = row.get("text", "")
        row["topics"] = extract_topics(text)
        row["figures"] = extract_figures(text)
        yield row