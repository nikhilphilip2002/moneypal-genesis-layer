"""Execution-boundary argument contracts for Workbench tools.

FastMCP function signatures own the public schemas. These models provide defense-in-depth
validation and cross-field business rules immediately before execution.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Discriminator,
    Field,
    Tag,
    model_validator,
)


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


class QueryEvidenceReference(AgentArguments):
    query_id: int = Field(
        ge=1,
        description="ID of a successful database query.",
    )


class CardEvidenceReference(AgentArguments):
    card_reference: str = Field(
        min_length=1,
        max_length=500,
        description="ID of a successful knowledge or web search result.",
    )


EvidenceReference = QueryEvidenceReference | CardEvidenceReference


class AnswerVisual(AgentArguments):
    query_id: int = Field(
        ge=1,
        description="ID of the database query result shown in the visual.",
    )
    view: VisualizationChartType = Field(
        description="Visualization Type",
    )


class AnswerEvidence(AgentArguments):
    evidence: list[EvidenceReference] = Field(
        max_length=30,
        description="References to retrieved results.",
    )


class AnswerPresentation(AnswerEvidence):
    visuals: list[AnswerVisual] = Field(
        default_factory=list,
        max_length=10,
        description="Visualization Type",
    )

    @model_validator(mode="after")
    def validate_presentation(self):
        if len({visual.query_id for visual in self.visuals}) != len(
            self.visuals
        ):
            raise ValueError("Provide at most one visual per query")
        evidence_queries = {
            ref.query_id
            for ref in self.evidence
            if isinstance(ref, QueryEvidenceReference)
        }
        if any(
            visual.query_id not in evidence_queries for visual in self.visuals
        ):
            raise ValueError(
                "Each visual query_id must also appear in evidence"
            )
        return self


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


class SubmitAnswerArguments(AnswerEvidence):
    outcome: Literal["answer"] = Field(
        description="Completed answer outcome.",
    )
    message: str = Field(
        min_length=1,
        max_length=20_000,
        description="Final answer.",
    )


class SubmitVisualAnswerArguments(SubmitAnswerArguments, AnswerPresentation):
    message: str = Field(
        min_length=1,
        max_length=1_000,
        description=(
            "Short summary of key findings."
        ),
    )
    visuals: list[AnswerVisual] = Field(
        min_length=1,
        max_length=10,
        description="Visualization type",
    )


class SubmitMarkdownAnswerArguments(SubmitAnswerArguments):
    message: str = Field(
        min_length=1,
        max_length=20_000,
        description="Final answer",
    )


class SubmitClarificationArguments(AgentArguments):
    """Ask for missing or ambiguous information needed to answer the request."""

    outcome: Literal["clarify"] = Field(
        description="Clarification outcome.",
    )
    message: str = Field(
        min_length=1,
        max_length=500,
        description="The clarification question shown to the user.",
    )
    suggestions: list[str] = Field(
        max_length=3,
        description="Suggested responses to the clarification question.",
    )


class SubmitRefusalArguments(AgentArguments):
    """Decline an unsupported or prohibited request with a governed reason."""

    outcome: Literal["refuse"] = Field(description="Refusal outcome.")
    message: str = Field(
        min_length=1,
        max_length=500,
        description="The refusal reason.",
    )
    reason_code: Literal[
        "out_of_scope",
        "not_in_data",
        "predictive",
        "advice",
        "unsafe",
    ] = Field(
        description="The reason category for declining the request.",
    )


def _submission_variant(submission: Any) -> str | None:
    outcome = (
        submission.get("outcome")
        if isinstance(submission, dict)
        else getattr(submission, "outcome", None)
    )
    if outcome == "answer":
        visuals = (
            submission.get("visuals")
            if isinstance(submission, dict)
            else getattr(submission, "visuals", None)
        )
        return "visual_answer" if visuals else "markdown_answer"
    return outcome


def _submission_any_of_schema(schema: dict[str, Any]) -> None:
    schema["anyOf"] = schema.pop("oneOf")


FinalSubmissionArguments = Annotated[
    Annotated[SubmitVisualAnswerArguments, Tag("visual_answer")]
    | Annotated[SubmitMarkdownAnswerArguments, Tag("markdown_answer")]
    | Annotated[SubmitClarificationArguments, Tag("clarify")]
    | Annotated[SubmitRefusalArguments, Tag("refuse")],
    Discriminator(_submission_variant),
    Field(
        json_schema_extra=_submission_any_of_schema,
        description="The final answer, clarification, or refusal shown to the user.",
    ),
]


__all__ = [
    "AgentArguments",
    "QueryEvidenceReference",
    "CardEvidenceReference",
    "EvidenceReference",
    "FinalSubmissionArguments",
    "SubmitAnswerArguments",
    "SubmitVisualAnswerArguments",
    "SubmitMarkdownAnswerArguments",
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
