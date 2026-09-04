"""Typed boundary between governed Workbench tools and answer composition.

Renderable payloads stay compatible with the existing SSE cards.  ``evidence`` is the
only model-facing representation: it is compact, bounded, and deliberately excludes raw
rows, SQL, hidden lineage, and tool traces.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

MAX_EVIDENCE_ITEMS = 14
MAX_EXCERPT_CHARS = 1_600


@dataclass(frozen=True, slots=True)
class Evidence:
    excerpt: str
    document: str = ""
    page: str | int | None = None
    url: str = ""
    date: str = ""
    score: float | None = None
    untrusted: bool = True

    def __post_init__(self) -> None:
        compact = " ".join(str(self.excerpt).split())[:MAX_EXCERPT_CHARS]
        object.__setattr__(self, "excerpt", compact)

    def as_dict(self) -> dict[str, Any]:
        return {key: value for key, value in asdict(self).items() if value not in ("", None)}


@dataclass(slots=True)
class ToolResult:
    source: str
    card_type: str
    payload: dict[str, Any]
    summary: str = ""
    sources: list[dict[str, Any]] = field(default_factory=list)
    evidence: list[Evidence] = field(default_factory=list)
    complete: bool = True
    limitation: str = ""
    sensitive: bool = False
    lineage: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        # Import lazily to avoid a source-catalog/result import cycle.
        from app.services.workbench.access import source_group

        if self.card_type != "error":
            source_group(self.source)  # every successful tool result is registered
        self.evidence = list(self.evidence[:MAX_EVIDENCE_ITEMS])

    @property
    def kind(self) -> str:
        """Compatibility name used by audit/tool callers."""
        return self.card_type

    @property
    def source_group(self) -> str:
        from app.services.workbench.access import source_group

        return source_group(self.source).value

    def evidence_dicts(self) -> list[dict[str, Any]]:
        return [item.as_dict() for item in self.evidence]

    def as_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "kind": self.card_type,
            "payload": self.payload,
            "evidence": self.evidence_dicts(),
            "summary": self.summary,
            "complete": self.complete,
            "limitation": self.limitation,
            "sensitive": self.sensitive,
            "lineage": self.lineage,
        }


# Additive compatibility alias. Existing imports and card tests keep working while the
# stronger name documents the contract at new call sites.
SourceResult = ToolResult


__all__ = [
    "Evidence",
    "MAX_EVIDENCE_ITEMS",
    "MAX_EXCERPT_CHARS",
    "SourceResult",
    "ToolResult",
]
