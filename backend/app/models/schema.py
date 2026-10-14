from pydantic import BaseModel, Field

from genesis_core.schema import IntelligenceResponse, SourceRef

__all__ = ["IntelligenceResponse", "SourceRef"]

Source = SourceRef


class RegulationCategory(BaseModel):
    id: str
    display_name: str
    category: str
    applicability: str
    effective_date: str
    source_docs: list[str]
    rbi_url: str
    qdrant_collection: str
    priority: str = "medium"


class RegulatoryAlert(BaseModel):
    title: str
    category: str
    severity: str = Field(pattern="^(high|medium)$")
    summary: str
    action_required: str
    source_url: str
    ai_note: str
