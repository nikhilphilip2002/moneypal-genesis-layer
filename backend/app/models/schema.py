from pydantic import BaseModel, Field


class Source(BaseModel):
    document: str
    url: str


class IntelligenceResponse(BaseModel):
    title: str
    summary: str
    key_points: list[str] = Field(default_factory=list)
    source: Source
    ai_note: str
    last_updated: str
    confidence: str = Field(pattern="^(high|medium|low)$")


class RegulationCategory(BaseModel):
    id: str
    display_name: str
    category: str
    applicability: str
    effective_date: str
    source_docs: list[str]
    rbi_url: str
    qdrant_collection: str


class RegulatoryAlert(BaseModel):
    title: str
    category: str
    severity: str = Field(pattern="^(high|medium)$")
    summary: str
    action_required: str
    source_url: str
    ai_note: str
