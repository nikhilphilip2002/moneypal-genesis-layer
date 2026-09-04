"""One bounded, grounded answer composition pass for all retrieved evidence."""

from __future__ import annotations

import json
import re
from typing import Iterable

from app.services.workbench.results import ToolResult

MAX_TOTAL_EVIDENCE_CHARS = 12_000
MAX_HISTORY_CHARS = 8_000
_NUMBER = re.compile(r"(?<![\w.])[-+]?\d[\d,]*(?:\.\d+)?%?(?![\w.])")


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


def numbers_are_grounded(text: str, evidence: str) -> bool:
    """Reject figures absent from evidence; formatting variants remain equivalent."""
    available = {_canonical_number(value) for value in _NUMBER.findall(evidence)}
    return all(_canonical_number(value) in available for value in _NUMBER.findall(text))


def _canonical_number(value: str) -> str:
    return value.replace(",", "").lstrip("+").rstrip("%")


__all__ = [
    "MAX_HISTORY_CHARS",
    "MAX_TOTAL_EVIDENCE_CHARS",
    "evidence_text",
    "extractive_fallback",
    "numbers_are_grounded",
    "relevant_history",
]
