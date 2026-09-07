"""Flat argument contracts for provider-native Workbench tools.

These models intentionally contain no routing discriminator. The native function name is the
route, leaving each tool with one ordinary object contract. Provider schemas are a constrained
projection of these models; these Pydantic models remain the execution-boundary authority.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.services.nlq.contracts import Filter, Period, QuerySpec


class AgentArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")


class QueryMetricsArguments(QuerySpec):
    """The full governed metric contract, without planner wrapper metadata."""


class LookupRecordsArguments(AgentArguments):
    selector: Literal[
        "borrower_name", "customer_id", "loan_account", "agent_code", "agent_name",
        "product_code", "branch", "gender",
    ]
    value: str = Field(min_length=1)
    detail: Literal[
        "customer_summary", "loan_details", "repayment_history", "agent_details",
        "agent_count", "agent_accounts", "agent_customers", "agent_directory",
        "branch_directory", "branch_customers", "product_details", "account_sample",
    ]
    requested_fields: list[Literal[
        "sanction_amount", "sanction_date", "disbursed_amount", "first_disbursement_date",
        "agent_name", "agent_type", "designation", "mobile", "email", "branch_code",
        "role_code", "joined_on", "linked_customer_count", "linked_loan_count",
        "borrower_name", "scheme_name", "number_of_emis",
    ]] = Field(default_factory=list)


class RunAnalysisArguments(AgentArguments):
    analysis_id: str = Field(min_length=1, description="Reviewed analysis id from the catalog.")
    period: Period | None = None
    filters: list[Filter] = Field(default_factory=list, max_length=4)


class CreateWorklistArguments(AgentArguments):
    worklist_id: str = Field(min_length=1, description="Reviewed worklist id from the catalog.")
    filters: list[Filter] = Field(default_factory=list, max_length=4)
    limit: int | None = Field(default=None, ge=1, le=200)


class GenerateBriefingArguments(AgentArguments):
    persona_id: str = Field(min_length=1, description="Persona id from the catalog.")


class RunValidatedQueryArguments(AgentArguments):
    intent: str = Field(min_length=1, max_length=1000)
    tables: list[str] = Field(default_factory=list)


class SearchCuratedKnowledgeArguments(AgentArguments):
    domain: Literal["concepts", "schema", "macro", "competitive", "regulatory"]
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
    "CreateWorklistArguments",
    "FinishWithoutDataArguments",
    "GenerateBriefingArguments",
    "LookupRecordsArguments",
    "QueryMetricsArguments",
    "RunAnalysisArguments",
    "RunValidatedQueryArguments",
    "SearchCuratedKnowledgeArguments",
    "SearchPublicWebArguments",
]
