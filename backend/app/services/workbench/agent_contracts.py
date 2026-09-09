"""Flat argument contracts for provider-native Workbench tools.

Each tool has one ordinary object contract. Provider schemas are a constrained projection of
these models; these Pydantic models remain the execution-boundary authority.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

class AgentArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SearchCuratedKnowledgeArguments(AgentArguments):
    domain: Literal["concepts", "macro", "competitive", "regulatory"]
    query: str = Field(min_length=1, max_length=1000)


class SearchPublicWebArguments(AgentArguments):
    search_query: str = Field(min_length=1, max_length=500)


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
    "SearchCuratedKnowledgeArguments",
    "SearchPublicWebArguments",
]
