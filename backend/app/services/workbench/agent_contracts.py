"""Execution-boundary argument contracts for Workbench tools.

FastMCP function signatures own the public schemas. These models provide defense-in-depth
validation and cross-field business rules immediately before execution.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class AgentArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")


QueryExecutionStatus = Literal[
    "pending",
    "running",
    "success",
    "empty",
    "error",
    "timeout",
    "cancelled",
]
QueryPurpose = Literal["answer", "discovery", "validation", "intermediate"]
QueryExclusionReason = Literal[
    "execution_error",
    "timeout",
    "cancelled",
    "empty_result",
    "superseded",
    "discovery_only",
    "validation_only",
    "unused_by_synthesis",
    "visual_unavailable",
]
VisualizationChartType = Literal[
    "kpi",
    "line",
    "area",
    "stacked_area",
    "bar",
    "grouped_bar",
    "table",
    "donut",
    "scatter",
    "heatmap",
]
VisualizationAggregation = Literal[
    "none",
    "sum",
    "avg",
    "min",
    "max",
    "count",
    "count_distinct",
]


class QueryReference(BaseModel):
    """Stable application-owned identity for one logical query and its attempt."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    query_id: str = Field(min_length=1, max_length=200)
    attempt_id: str = Field(min_length=1, max_length=240)


class QueryExecutionRecord(BaseModel):
    """The authoritative per-turn record of a database query attempt."""

    model_config = ConfigDict(extra="forbid")

    query_id: str = Field(min_length=1, max_length=200)
    attempt_id: str = Field(min_length=1, max_length=240)
    tool_call_id: str = Field(min_length=1, max_length=500)
    tool_name: str = Field(min_length=1, max_length=200)
    query_fingerprint: str = Field(min_length=64, max_length=64)
    status: QueryExecutionStatus = "pending"
    purpose: QueryPurpose = "answer"
    row_count: int | None = Field(default=None, ge=0)
    has_data: bool = False
    visual_available: bool = False
    duration_ms: int = Field(default=0, ge=0)
    error_code: str | None = Field(default=None, max_length=200)
    supersedes_query_id: str | None = Field(default=None, max_length=200)
    source_query_id: str | None = Field(default=None, max_length=200)
    result_complete: bool = True
    result_payload: dict[str, Any] | None = None
    card: dict[str, Any] | None = None


class ExcludedQueryReference(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query_id: str = Field(min_length=1, max_length=200)
    reason_code: QueryExclusionReason
    reason: str = Field(default="", max_length=500)


class EvidenceReference(AgentArguments):
    query_id: int | None = Field(default=None, ge=1)
    card_reference: str | None = Field(
        default=None, min_length=1, max_length=500
    )

    @model_validator(mode="after")
    def require_one_reference(self):
        if (self.query_id is None) == (self.card_reference is None):
            raise ValueError(
                "Provide exactly one of query_id or card_reference"
            )
        return self


class AnswerVisual(AgentArguments):
    query_id: int = Field(ge=1)
    view: VisualizationChartType


class AnswerPresentation(AgentArguments):
    query_id: int | None = Field(default=None, ge=1)
    view: VisualizationChartType | None = None
    evidence: list[EvidenceReference] = Field(
        default_factory=list, max_length=30
    )
    visuals: list[AnswerVisual] = Field(default_factory=list, max_length=10)

    @model_validator(mode="after")
    def validate_presentation(self):
        if (self.query_id is None) != (self.view is None):
            raise ValueError(
                "Legacy query_id and view must be provided together"
            )
        if self.query_id is not None and (self.evidence or self.visuals):
            raise ValueError(
                "Use evidence and visuals, or legacy query_id and view"
            )
        if len({visual.query_id for visual in self.visuals}) != len(
            self.visuals
        ):
            raise ValueError("Provide at most one visual per query")
        evidence_queries = {ref.query_id for ref in self.evidence}
        if any(
            visual.query_id not in evidence_queries for visual in self.visuals
        ):
            raise ValueError(
                "Each visual query_id must also appear in evidence"
            )
        return self

    def evidence_references(self) -> list[EvidenceReference]:
        if self.query_id is not None:
            return [EvidenceReference(query_id=self.query_id)]
        return self.evidence

    def requested_visuals(self) -> list[AnswerVisual]:
        if self.query_id is not None and self.view is not None:
            return [AnswerVisual(query_id=self.query_id, view=self.view)]
        return self.visuals


class FinalSynthesis(AnswerPresentation):
    insights: str = Field(default="", max_length=20_000)


class SearchCuratedKnowledgeArguments(AgentArguments):
    domain: Literal["concepts", "macro", "competitive", "regulatory"]
    query: str = Field(min_length=1, max_length=1000)


class SearchPublicWebArguments(AgentArguments):
    search_query: str = Field(min_length=1, max_length=500)


class VisualizeQueryResultArguments(AgentArguments):
    query_id: str
    chart_type: VisualizationChartType
    x: str | None
    y: list[str]
    series: str | None
    aggregation: VisualizationAggregation


class SubmitAnswerArguments(AnswerPresentation):
    outcome: Literal["answer"]
    message: str = Field(max_length=20_000)

    @model_validator(mode="after")
    def require_answer_content(self):
        if self.query_id is None and not self.message.strip():
            raise ValueError("A composed answer requires a Markdown message")
        return self


class SubmitClarificationArguments(AgentArguments):
    """Ask for missing or ambiguous information needed to answer the request."""

    outcome: Literal["clarify"]
    message: str = Field(min_length=1, max_length=500)
    suggestions: list[str] = Field(default_factory=list, max_length=3)


class SubmitRefusalArguments(AgentArguments):
    """Decline an unsupported or prohibited request with a governed reason."""

    outcome: Literal["refuse"]
    message: str = Field(min_length=1, max_length=500)
    reason_code: Literal[
        "out_of_scope",
        "not_in_data",
        "predictive",
        "advice",
        "unsafe",
    ]


FinalSubmissionArguments = Annotated[
    SubmitAnswerArguments | SubmitClarificationArguments | SubmitRefusalArguments,
    Field(discriminator="outcome"),
]


__all__ = [
    "AgentArguments",
    "FinalSubmissionArguments",
    "SubmitAnswerArguments",
    "SubmitClarificationArguments",
    "SubmitRefusalArguments",
    "ExcludedQueryReference",
    "FinalSynthesis",
    "QueryExecutionRecord",
    "QueryExclusionReason",
    "QueryExecutionStatus",
    "QueryPurpose",
    "QueryReference",
    "SearchCuratedKnowledgeArguments",
    "SearchPublicWebArguments",
    "VisualizationAggregation",
    "VisualizationChartType",
    "VisualizeQueryResultArguments",
]
