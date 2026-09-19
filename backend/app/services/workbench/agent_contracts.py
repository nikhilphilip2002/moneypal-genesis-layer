"""Flat argument contracts for provider-native Workbench tools.

Each tool has one ordinary object contract. Provider schemas are a constrained projection of
these models; these Pydantic models remain the execution-boundary authority.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

class AgentArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")


QueryExecutionStatus = Literal[
    "pending", "running", "success", "empty", "error", "timeout", "cancelled",
]
QueryPurpose = Literal["answer", "discovery", "validation", "intermediate"]
QueryExclusionReason = Literal[
    "execution_error", "timeout", "cancelled", "empty_result", "superseded",
    "discovery_only", "validation_only", "unused_by_synthesis", "visual_unavailable",
]
VisualizationChartType = Literal[
    "kpi", "line", "area", "stacked_area", "bar", "grouped_bar", "table",
    "donut", "scatter", "heatmap",
]
VisualizationAggregation = Literal[
    "none", "sum", "avg", "min", "max", "count", "count_distinct",
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
    card: dict[str, Any] | None = None


class ExcludedQueryReference(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query_id: str = Field(min_length=1, max_length=200)
    reason_code: QueryExclusionReason
    reason: str = Field(default="", max_length=500)


class FinalSynthesis(BaseModel):
    """Strict model-authored final response before backend reconciliation."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    narrative_insights: str = Field(min_length=1, max_length=20_000)
    active_query_ids: list[str] = Field(default_factory=list, max_length=100)
    visual_query_ids: list[str] = Field(default_factory=list, max_length=100)
    excluded_queries: list[ExcludedQueryReference] = Field(default_factory=list, max_length=100)


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
    aggregation: VisualizationAggregation = Field(
        description=(
            "Use none when each x/series pair is already aggregated; otherwise choose "
            "how to combine multiple y values for the same x/series pair."
        ),
    )


class FinishWithoutDataArguments(AgentArguments):
    outcome: Literal["clarify", "refuse"]
    message: str = Field(min_length=1, max_length=500)
    suggestions: list[str] = Field(default_factory=list, max_length=3)
    reason_code: Literal[
        "out_of_scope", "not_in_data", "predictive", "advice", "unsafe",
    ] | None = None

    @model_validator(mode="after")
    def _check_outcome_fields(self) -> "FinishWithoutDataArguments":
        if self.outcome == "clarify" and self.reason_code is not None:
            raise ValueError("clarification cannot include a refusal reason_code")
        if self.outcome == "refuse":
            if self.reason_code is None:
                raise ValueError("refusal requires reason_code")
            if self.suggestions:
                raise ValueError("refusal cannot include suggestions")
        return self


__all__ = [
    "AgentArguments",
    "FinishWithoutDataArguments",
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
