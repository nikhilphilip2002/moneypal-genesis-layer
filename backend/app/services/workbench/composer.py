"""One bounded, grounded answer composition pass for all retrieved evidence."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Iterable

from app.services.workbench.facts import Fact
from app.services.workbench.results import ToolResult

MAX_TOTAL_EVIDENCE_CHARS = 12_000
MAX_HISTORY_CHARS = 8_000
MAX_FACTS_CHARS = 6_000
_NUMBER = re.compile(r"(?<![\w.])[-+]?(?>\d[\d,]*(?:\.\d+)?)%?(?![%\w])")
# Numbers that are part of a date or a period label are not numeric claims.
_DATE_LIKE = re.compile(
    r"\d{4}-\d{2}-\d{2}|\d{4}-\d{2}\b|\bFY\s?\d{2,4}(?:-\d{2,4})?|"
    r"\b(?:19|20)\d{2}-\d{2}\b|\d{1,2}/\d{1,2}/\d{2,4}|"
    r"\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?\s+(?:19|20)\d{2}\b",
    re.IGNORECASE,
)
_SCALES = {
    "cr": 10_000_000, "crore": 10_000_000, "crores": 10_000_000,
    "l": 100_000, "lakh": 100_000, "lakhs": 100_000, "lac": 100_000, "lacs": 100_000,
    "k": 1_000, "thousand": 1_000,
    "mn": 1_000_000, "million": 1_000_000,
    "bn": 1_000_000_000, "billion": 1_000_000_000,
}
_SCALE_SUFFIX = re.compile(
    r"\s*(cr|crores?|l|lakhs?|lacs?|k|thousand|mn|million|bn|billion)\b", re.IGNORECASE,
)
_INR_SCALES = frozenset({"cr", "crore", "crores", "l", "lakh", "lakhs", "lac", "lacs"})
# Fact units each claim unit may be checked against. ``number`` is the unknown default
# for governed columns without a declared unit, so it never contradicts a claim.
_COMPATIBLE_UNITS = {
    "percent": {"percent", "ratio", "number"},
    "inr": {"inr", "number"},
    "count": {"count", "number"},
    "days": {"days", "number"},
    "months": {"months", "number"},
    "years": {"years", "number"},
}
_SIGNLESS_OPERATIONS = frozenset({"difference", "percent_change"})
_PERIOD = re.compile(
    r"\b(?:FY\s?\d{2,4}|(?:this|last)\s+(?:month|quarter|FY|year)|"
    r"today|yesterday|YTD)\b",
    re.IGNORECASE,
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


@dataclass(frozen=True, slots=True)
class NumericClaim:
    """One numeric statement in an answer, scaled and unit-tagged from its context."""

    text: str
    value: Decimal
    unit: str
    period: str
    start: int
    end: int
    tolerance: Decimal


@dataclass(frozen=True, slots=True)
class ClaimValidation:
    supported: tuple[tuple[NumericClaim, Fact], ...]
    unsupported: tuple[NumericClaim, ...]

    @property
    def ok(self) -> bool:
        return not self.unsupported

    @property
    def unsupported_texts(self) -> list[str]:
        return [claim.text for claim in self.unsupported]

    @property
    def cited_facts(self) -> list[Fact]:
        """Verified facts that support the answer, in order of first citation."""
        seen: set[str] = set()
        cited: list[Fact] = []
        for _claim, fact in self.supported:
            if fact.source != "evidence" and fact.id not in seen:
                seen.add(fact.id)
                cited.append(fact)
        return cited


def numeric_claims(text: str) -> list[NumericClaim]:
    """Extract numeric candidates; matching against facts is the oracle, not this regex."""
    excluded = [(m.start(), m.end()) for m in _DATE_LIKE.finditer(text)]
    claims: list[NumericClaim] = []
    for match in _NUMBER.finditer(text):
        raw = match.group(0).rstrip(",")
        start, end = match.start(), match.start() + len(raw)
        if _ordered_list_marker(text, start, end):
            continue
        if any(lo <= start and end <= hi for lo, hi in excluded):
            continue
        base = _decimal(raw)
        if base is None:
            continue
        unit, scale, end = _claim_unit(text, start, end)
        mantissa = raw.rstrip("%")
        digits = len(mantissa.rsplit(".", 1)[1]) if "." in mantissa else 0
        # Half a unit in the last rendered digit, at the claim's magnitude.
        tolerance = Decimal(5) * (Decimal(10) ** (-digits - 1)) * scale
        claims.append(NumericClaim(
            text=text[start:end], value=base * scale, unit=unit,
            period=_claim_period(text, start), start=start, end=end, tolerance=tolerance,
        ))
    return claims


def validate_claims(
    text: str, evidence: str = "", facts: Iterable[Fact] = (),
) -> ClaimValidation:
    """Map every numeric claim to a verified fact, a derived fact, or quoted evidence."""
    candidates = [fact for fact in facts if fact.verified]
    candidates.extend(_evidence_facts(evidence))
    supported: list[tuple[NumericClaim, Fact]] = []
    unsupported: list[NumericClaim] = []
    for claim in numeric_claims(text):
        match = next((fact for fact in candidates if _supports(claim, fact)), None)
        if match is None:
            unsupported.append(claim)
        else:
            supported.append((claim, match))
    return ClaimValidation(tuple(supported), tuple(unsupported))


def unsupported_numbers(
    text: str, evidence: str, facts: Iterable[Fact] = (),
) -> list[str]:
    """Return numeric claims not present in evidence or the verified fact ledger."""
    return validate_claims(text, evidence, facts).unsupported_texts


def numbers_are_grounded(
    text: str, evidence: str, facts: Iterable[Fact] = (),
) -> bool:
    """Compatibility predicate backed by claim-level validation."""
    return validate_claims(text, evidence, facts).ok


def _supports(claim: NumericClaim, fact: Fact) -> bool:
    allowed = _COMPATIBLE_UNITS.get(claim.unit)
    if allowed is not None and fact.unit not in allowed:
        return False
    if claim.period and fact.period:
        periods = {_normalize_period(part) for part in fact.period.split(" vs ")}
        if claim.period not in periods:
            return False
    values = [fact.value]
    if claim.unit in {"", "percent"} and fact.unit == "ratio":
        values.append(fact.value * 100)
    if claim.unit == "" and fact.unit == "percent":
        values.append(fact.value / 100)
    signless = fact.operation in _SIGNLESS_OPERATIONS
    for value in values:
        if abs(value - claim.value) <= claim.tolerance:
            return True
        if signless and abs(abs(value) - abs(claim.value)) <= claim.tolerance:
            return True
    return False


def _evidence_facts(evidence: str) -> list[Fact]:
    """Numbers quoted in governed evidence excerpts count as support for external sources."""
    facts: list[Fact] = []
    for index, claim in enumerate(numeric_claims(evidence)):
        facts.append(Fact(
            id=f"evidence:{index}", label="evidence", value=claim.value,
            display_value=claim.text, unit=claim.unit or "number", source="evidence",
            card_type="evidence", row=index, field="excerpt", period=claim.period,
        ))
    return facts


def _decimal(value: str) -> Decimal | None:
    try:
        return Decimal(value.replace(",", "").lstrip("+").rstrip("%"))
    except InvalidOperation:
        return None


def _canonical_number(value: str) -> str:
    normalized = value.replace(",", "").lstrip("+").rstrip("%")
    try:
        decimal = Decimal(normalized)
    except InvalidOperation:
        return normalized
    if decimal == 0:
        return "0"
    return format(decimal.normalize(), "f")


def _claim_unit(text: str, start: int, end: int) -> tuple[str, Decimal, int]:
    """Unit, magnitude scale and the extended end of the claim including its suffix."""
    value = text[start:end]
    around_before = text[max(0, start - 5):start].casefold()
    after = text[end:end + 12]
    around_after = after.casefold()
    scale = Decimal(1)
    suffix = _SCALE_SUFFIX.match(after)
    scale_word = suffix.group(1).casefold() if suffix is not None else ""
    if suffix is not None:
        scale = Decimal(_SCALES[scale_word])
        end = end + suffix.end()
    currency = "₹" in around_before or bool(re.search(r"\b(?:rs\.?|inr)\s*$", around_before))
    if value.endswith("%") or re.match(r"\s*per\s*cent\b", around_after):
        return "percent", scale, end
    if currency or scale_word in _INR_SCALES:
        return "inr", scale, end
    for unit in ("days", "months", "years"):
        if re.match(rf"\s*{unit}?\b", around_after):
            return unit, scale, end
    return "", scale, end


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


def remove_unsupported_claims(
    text: str, unsupported: Iterable[NumericClaim | str],
) -> tuple[str, list[str]]:
    """Drop only the sentences carrying unsupported claims; return the text and what went.

    Sentence boundaries are punctuation followed by whitespace, or line breaks, so a
    bullet list loses one bullet rather than the whole list.
    """
    spans: list[tuple[int, int]] = []
    canonical: set[str] = set()
    for item in unsupported:
        if isinstance(item, NumericClaim):
            spans.append((item.start, item.end))
        else:
            canonical.add(_canonical_number(item))
    if not spans and not canonical:
        return text.strip(), []
    boundaries = [0]
    # A line break is its own boundary; the zero-width one fires only before spaces so
    # a removed bullet does not leave an empty piece (and a blank line) behind.
    for match in re.finditer(r"(?<=[.!?])(?=[ \t])|\n+", text):
        boundaries.extend((match.start(), match.end()))
    boundaries.append(len(text))
    kept: list[str] = []
    removed: list[str] = []
    for index in range(0, len(boundaries) - 1, 2):
        piece_start, piece_end = boundaries[index], boundaries[index + 1]
        separator = text[piece_end:boundaries[index + 2]] if index + 2 < len(boundaries) else ""
        piece = text[piece_start:piece_end]
        hit = any(piece_start <= lo and hi <= piece_end for lo, hi in spans) or bool(
            canonical & {
                _canonical_number(m.group(0))
                for m in _NUMBER.finditer(piece)
                if not _ordered_list_marker(piece, m.start(), m.end())
            }
        )
        if hit:
            if piece.strip():
                removed.append(piece.strip())
            continue
        kept.append(piece + ("\n" if "\n" in separator else separator))
    cleaned = "".join(kept)
    cleaned = re.sub(r"[ \t]+\n", "\n", cleaned)
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip(), removed


def remove_unsupported_numeric_sentences(text: str, unsupported: Iterable[str]) -> str:
    """Compatibility wrapper around :func:`remove_unsupported_claims`."""
    return remove_unsupported_claims(text, unsupported)[0]


def fact_dict(fact: Fact) -> dict:
    return {
        "id": fact.id,
        "label": fact.label,
        "value": format(fact.value, "f"),
        "display_value": fact.display_value,
        "unit": fact.unit,
        "period": fact.period,
        "dimensions": dict(fact.dimensions),
        "derived": fact.source == "calculation",
        "operation": fact.operation,
        "operands": list(fact.operands),
        "formula": fact.formula,
    }


def facts_text(facts: Iterable[Fact], limit: int = MAX_FACTS_CHARS) -> str:
    """Machine-readable fact set for the model: one compact JSON object per line."""
    lines: list[str] = []
    remaining = limit
    for fact in facts:
        if not fact.verified:
            continue
        item = fact_dict(fact)
        # Compact: the model needs id, label, value and unit; provenance only for
        # derived facts, and no field that repeats another or is empty.
        if not item["derived"]:
            for key in ("derived", "operation", "operands", "formula"):
                item.pop(key)
        if item["display_value"] == item["value"]:
            item.pop("display_value")
        for key in ("period", "dimensions"):
            if not item[key]:
                item.pop(key)
        rendered = json.dumps(item, ensure_ascii=False, separators=(",", ":"))
        if len(rendered) + 1 > remaining:
            break
        lines.append(rendered)
        remaining -= len(rendered) + 1
    return "\n".join(lines)


def facts_message(facts_block: str) -> str:
    return (
        "VERIFIED FACTS (machine-readable). Every number in the answer must equal one of "
        "these values, rounded, or a number quoted in the retrieved evidence. Derived "
        "facts list their operands and formula; you may state them but must not compute "
        "new ones. Qualitative observations are welcome as long as they add no figure.\n"
        + facts_block
    )


def repair_message(unsupported: Iterable[NumericClaim | str], facts_block: str) -> str:
    """One focused repair request naming the exact unsupported claims."""
    names = [item.text if isinstance(item, NumericClaim) else str(item) for item in unsupported]
    quoted = "; ".join('"' + name + '"' for name in names)
    return (
        "The answer contains numeric claims that the retrieved results do not support: "
        + quoted
        + ". Rewrite the answer once. Keep every supported statement and qualitative "
        "observation. Remove or correct only the unsupported claims, using the verified "
        "facts below or numbers quoted in the retrieved evidence. Do not introduce any "
        "other figure.\n\n"
        + (facts_message(facts_block) if facts_block else "No verified facts are available.")
    )


__all__ = [
    "ClaimValidation",
    "MAX_FACTS_CHARS",
    "MAX_HISTORY_CHARS",
    "MAX_TOTAL_EVIDENCE_CHARS",
    "NumericClaim",
    "evidence_text",
    "extractive_fallback",
    "fact_dict",
    "facts_message",
    "facts_text",
    "numbers_are_grounded",
    "numeric_claims",
    "relevant_history",
    "remove_unsupported_claims",
    "remove_unsupported_numeric_sentences",
    "repair_message",
    "unsupported_numbers",
    "validate_claims",
]
