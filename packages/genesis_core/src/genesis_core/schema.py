"""Shared response contract. Every intelligence endpoint returns IntelligenceResponse."""
from __future__ import annotations

from datetime import date
from typing import Literal, Optional

from pydantic import BaseModel, Field

Confidence = Literal["high", "medium", "low"]


class SourceRef(BaseModel):
    document: str                 # e.g. "RBI NBFC Master Directions 2016"
    url: str                      # link back to the original source
    page: Optional[str] = None    # page/section reference if available


class IntelligenceResponse(BaseModel):
    title: str
    summary: str                                          # AI-generated executive summary
    key_points: list[str] = Field(default_factory=list)   # 3-5 bullets
    source: SourceRef
    ai_note: str                                          # separates fact from AI interpretation
    last_updated: str = Field(default_factory=lambda: date.today().isoformat())
    confidence: Confidence = "medium"


def make_response(
    title: str,
    summary: str,
    key_points: list[str],
    document: str,
    url: str,
    ai_note: str,
    page: Optional[str] = None,
    confidence: Confidence = "medium",
) -> IntelligenceResponse:
    """Convenience builder so service code stays short."""
    return IntelligenceResponse(
        title=title,
        summary=summary,
        key_points=key_points,
        source=SourceRef(document=document, url=url, page=page),
        ai_note=ai_note,
        confidence=confidence,
    )
