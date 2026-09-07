"""One bounded, grounded answer composition pass for all retrieved evidence."""

from __future__ import annotations

import json
import re
from decimal import Decimal, InvalidOperation
from typing import Iterable

from app.services.workbench.facts import Fact
from app.services.workbench.results import ToolResult

MAX_TOTAL_EVIDENCE_CHARS = 12_000
MAX_HISTORY_CHARS = 8_000
_NUMBER = re.compile(r"(?<![\w.])[-+]?(?>\d[\d,]*(?:\.\d+)?)%?(?![%\w])")
_PERIOD = re.compile(
    r"\b(?:FY\s?\d{2,4}|(?:this|last)\s+(?:month|quarter|FY|year)|"
    r"today|yesterday|YTD)\b",
    re.I,
)


def evidence_text(results: Iterable[ToolResult]) -> str:
    """Serialize only bounded model evidence, never render payloads or lineage."""
    blocks: list[str] = []
    remaining = MAX_TOTAL_EVIDENCE_CHARS
    for result in results:
        if remaining <= 0:
            break
        if result.summary:
            trusted_summary = json.dumps({
                "source": result.source,
                "kind": "governed_summary",
                "text": result.summary,
                "untrusted": False,
            }, ensure_ascii=False, sort_keys=True)
            blocks.append(trusted_summary[:remaining])
            remaining -= len(blocks[-1])
        for item in result.evidence:
            if remaining <= 0:
                break
            rendered = json.dumps(
                {"source": result.source, **item.as_dict()},
                ensure_ascii=False,
                sort_keys=True,
            )
            rendered = rendered[:remaining]
            blocks.append(rendered)
            remaining -= len(rendered)
    return "\n".join(blocks)


def relevant_history(messages: list[dict[str, str]]) -> list[dict[str, str]]:
    """Cap replay independently from evidence and retain newest complete messages."""
    kept: list[dict[str, str]] = []
    remaining = MAX_HISTORY_CHARS
    for message in reversed(messages):
        content = str(message.get("content", ""))
        if not content:
            continue
        clipped = content[-remaining:]
        kept.append({"role": str(message.get("role", "user")), "content": clipped})
        remaining -= len(clipped)
        if remaining <= 0:
            break
    return list(reversed(kept))


def extractive_fallback(results: Iterable[ToolResult]) -> str:
    """Return bounded source excerpts if composition is unavailable or ungrounded."""
    parts: list[str] = []
    for result in results:
        excerpts = [item.excerpt for item in result.evidence[:2] if item.excerpt]
        if excerpts:
            parts.append(f"{result.source.title()}: {' '.join(excerpts)}")
        elif result.summary:
            parts.append(result.summary)
    return "\n\n".join(parts)[:4_000] or "The selected sources returned no usable evidence."


def unsupported_numbers(
    text: str, evidence: str, facts: Iterable[Fact] = (),
) -> list[str]:
    """Return numeric claims not present in evidence or the verified fact ledger."""
    available: dict[str, set[tuple[str, str]]] = {}
    for match in _NUMBER.finditer(evidence):
        available.setdefault(_canonical_number(match.group(0)), set()).add(
            (_claim_unit(evidence, match.start(), match.end()), _claim_period(evidence, match.start()))
        )
    for fact in facts:
        if fact.verified:
            contexts = {(fact.unit, _normalize_period(fact.period))}
            for value in _NUMBER.findall(fact.display_value):
                available.setdefault(_canonical_number(value), set()).update(contexts)
            available.setdefault(_canonical_number(str(fact.value)), set()).update(contexts)
    unsupported: list[str] = []
    for match in _NUMBER.finditer(text):
        value = match.group(0)
        if _ordered_list_marker(text, match.start(), match.end()):
            continue
        contexts = available.get(_canonical_number(value), set())
        unit = _claim_unit(text, match.start(), match.end())
        period = _claim_period(text, match.start())
        if not contexts or not any(
            (not unit or unit == allowed_unit)
            and (not period or not allowed_period or period == allowed_period)
            for allowed_unit, allowed_period in contexts
        ):
            unsupported.append(value)
    return unsupported


def numbers_are_grounded(
    text: str, evidence: str, facts: Iterable[Fact] = (),
) -> bool:
    """Compatibility predicate backed by claim-aware evidence and typed facts."""
    return not unsupported_numbers(text, evidence, facts)


def _canonical_number(value: str) -> str:
    normalized = value.replace(",", "").lstrip("+").rstrip("%")
    try:
        decimal = Decimal(normalized)
    except InvalidOperation:
        return normalized
    if decimal == 0:
        return "0"
    return format(decimal.normalize(), "f")


def _claim_unit(text: str, start: int, end: int) -> str:
    value = text[start:end]
    around_before = text[max(0, start - 5):start].casefold()
    around_after = text[end:end + 12].casefold()
    if value.endswith("%") or re.match(r"\s*per\s+cent\b", around_after):
        return "percent"
    if "₹" in around_before or re.search(r"\brs\.?\s*$", around_before):
        return "inr"
    for unit in ("days", "months", "years"):
        if re.match(rf"\s*{unit}?\b", around_after):
            return unit
    if re.match(r"\s*(?:crore|lakh)\b", around_after):
        return "inr"
    return ""


def _claim_period(text: str, start: int) -> str:
    line_start = text.rfind("\n", 0, start) + 1
    line_end = text.find("\n", start)
    match = _PERIOD.search(text[line_start:line_end if line_end >= 0 else len(text)])
    return _normalize_period(match.group(0) if match else "")


def _normalize_period(value: str) -> str:
    return " ".join(value.replace("_", " ").upper().split())


def _ordered_list_marker(text: str, start: int, end: int) -> bool:
    line_start = text.rfind("\n", 0, start) + 1
    prefix = text[line_start:start]
    suffix = text[end:end + 2]
    return not prefix.strip() and suffix.startswith((". ", ") "))


def remove_unsupported_numeric_sentences(text: str, unsupported: Iterable[str]) -> str:
    """Remove only ungrounded numeric sentences when sentence boundaries are clear."""
    canonical = {_canonical_number(value) for value in unsupported}
    if not canonical:
        return text.strip()
    pieces = re.split(r"(?<=[.!?])(?=\s|$)|\n+", text)
    kept: list[str] = []
    for piece in pieces:
        claims = {
            _canonical_number(match.group(0))
            for match in _NUMBER.finditer(piece)
            if not _ordered_list_marker(piece, match.start(), match.end())
        }
        if claims & canonical:
            continue
        if piece.strip():
            kept.append(piece.strip())
    return " ".join(kept).strip()


__all__ = [
    "MAX_HISTORY_CHARS",
    "MAX_TOTAL_EVIDENCE_CHARS",
    "evidence_text",
    "extractive_fallback",
    "numbers_are_grounded",
    "relevant_history",
    "remove_unsupported_numeric_sentences",
    "unsupported_numbers",
]
