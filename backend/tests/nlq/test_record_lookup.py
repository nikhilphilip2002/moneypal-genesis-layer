"""Regression coverage for generalized customer/account record lookups."""

import pytest

from app.services.nlq.catalog import get_catalog
from app.services.nlq.charts import build_from_rows
from app.services.nlq.contracts import Lineage, LookupPlan
from app.services.nlq.executor import QueryResult
from app.services.nlq.lookup import (
    _agent_count,
    _agent_details,
    _branch_directory,
    _customer_summary,
    _gender_sample,
    completions,
    _loan_details,
    _repayment_history,
    _shape_loan_details,
    detect,
    run,
)
from app.services.nlq.planner import plan


@pytest.mark.parametrize(
    ("question", "selector", "value", "detail"),
    [
        (
            "what is the loan amount and date of customer id 128",
            "customer_id", "128", "loan_details",
        ),
        (
            "show loan date and amount for borrower number 1,028.00",
            "customer_id", "1028", "loan_details",
        ),
        (
            "what is SHEELAVATHI MK repayment history",
            "borrower_name", "SHEELAVATHI MK", "repayment_history",
        ),
        (
            "repayment history of SHEELAVATHI M K",
            "borrower_name", "SHEELAVATHI M K", "repayment_history",
        ),
        (
            "payment history for loan account number 1000400001520.00",
            "loan_account", "1000400001520", "repayment_history",
        ),
        (
            "show one male and female account number",
            "gender", "male,female", "account_sample",
        ),
        (
            "details of agnt45",
            "agent_code", "AGNT45", "agent_details",
        ),
        (
            "AGENT-106",
            "agent_code", "AGNT106", "agent_details",
        ),
        (
            "how many agents is there",
            "agent_code", "all", "agent_count",
        ),
        (
            "show me the agent 45 inforamtion",
            "agent_code", "AGNT45", "agent_details",
        ),
        (
            "what are the branches is there",
            "branch", "all", "branch_directory",
        ),
        (
            "what is the disbursment date of customer SHEELAVATHI M K",
            "borrower_name", "SHEELAVATHI M K", "loan_details",
        ),
        (
            "show me the customer id 128 detail",
            "customer_id", "128", "customer_summary",
        ),
        (
            "loan details of MAHABALA GOWDA",
            "borrower_name", "MAHABALA GOWDA", "loan_details",
        ),
        (
            "show me Mahabala Gowda's loan account information",
            "borrower_name", "Mahabala Gowda", "loan_details",
        ),
        (
            "SHEELAVATHI M K's details",
            "borrower_name", "SHEELAVATHI M K", "customer_summary",
        ),
        (
            "show customer profile for Sheelavathi M K",
            "borrower_name", "Sheelavathi M K", "customer_summary",
        ),
    ],
)
def test_lookup_intent_is_phrase_independent(question, selector, value, detail):
    result = detect(question)

    assert result is not None
    assert (result.selector, result.value, result.detail) == (selector, value, detail)


@pytest.mark.anyio
async def test_record_lookup_bypasses_the_llm_planner():
    outcome = await plan("what is ARUNA P repayment history")

    assert isinstance(outcome.plan, LookupPlan)
    assert outcome.attempts == 0
    assert outcome.model == "deterministic"


def test_customer_details_query_returns_both_sanction_and_disbursement_fields():
    attempt = _loan_details(
        LookupPlan(
            selector="customer_id", value="128", detail="loan_details",
            reasoning="test",
        ),
        get_catalog(),
    )

    assert attempt.validated and attempt.reviewed
    assert "sanction_amount" in attempt.sql
    assert "sanction_date" in attempt.sql
    assert "disbursed_amount" in attempt.sql
    assert "first_disbursement_date" in attempt.sql
    assert "customer_id AS TEXT" in attempt.sql


def test_loan_amount_question_requests_only_the_sanction_amount():
    plan_result = detect("what is the loan amount of customer id 129")

    assert plan_result is not None
    assert plan_result.requested_fields == ["sanction_amount"]
    attempt = _loan_details(plan_result, get_catalog())
    projection = attempt.sql.split("FROM", 1)[0]
    assert "sanction_amount" in projection
    assert "sanction_date" not in projection
    assert "disbursed_amount" not in projection
    assert "first_disbursement_date" not in projection


def test_single_loan_result_displays_only_the_requested_fact():
    chart = build_from_rows(
        question="loan amount",
        result=QueryResult(
            rows=[{
                "customer_id": "129", "loan_account_number": "1000400000075",
                "sanction_amount": 700000,
            }],
            columns=["customer_id", "loan_account_number", "sanction_amount"],
            status="ok", duration_ms=1, sql="SELECT 1", row_count=1,
        ),
        lineage=Lineage(path="text_to_sql", sql="SELECT 1", unverified=False),
        unit_hints={
            "customer_id": "text", "loan_account_number": "text", "sanction_amount": "inr",
        },
    )
    _shape_loan_details(
        chart,
        LookupPlan(
            selector="customer_id", value="129", detail="loan_details",
            requested_fields=["sanction_amount"], reasoning="test",
        ),
    )

    assert chart.rows == [{"sanction_amount": 700000}]
    assert [column.name for column in chart.columns] == ["sanction_amount"]
    assert chart.summary.startswith("Sanction amount is ")
    assert "highest" not in chart.summary


def test_customer_summary_returns_only_the_requested_profile_fields():
    attempt = _customer_summary(
        LookupPlan(
            selector="customer_id", value="128", detail="customer_summary",
            reasoning="test",
        ),
        get_catalog(),
    )

    assert attempt.validated and attempt.reviewed
    assert "FROM gold.customer_master AS customer" in attempt.sql
    assert "LEFT JOIN gold.loan_account_master AS loan" in attempt.sql
    assert "customer.full_name AS customer_name" in attempt.sql
    assert "CAST(loan.loan_account_number AS TEXT) AS loan_account_number" in attempt.sql
    assert "loan.sanction_amount" in attempt.sql
    assert "loan.sanction_date" in attempt.sql
    assert "AS address" in attempt.sql
    assert "AS occupation" in attempt.sql
    assert "customer.home_branch_code" in attempt.sql
    assert "customer.agency_code" in attempt.sql
    assert "customer.agency_name" in attempt.sql
    for excluded in ("date_of_birth", "yearly_income", "kyc_doc_count", "risk_rating"):
        assert excluded not in attempt.sql


def test_repayment_history_is_newest_first_and_totals_before_limiting():
    attempt = _repayment_history(
        LookupPlan(
            selector="customer_id", value="128", detail="repayment_history",
            reasoning="test",
        ),
        get_catalog(),
    )

    assert attempt.validated and attempt.reviewed
    assert "SUM(total_due) OVER ()" in attempt.sql
    assert "SUM(total_paid) OVER ()" in attempt.sql
    assert "ORDER BY\n  repayment_date DESC" in attempt.sql
    assert attempt.sql.rstrip().endswith("LIMIT 500")


def test_gender_sample_uses_compound_join_and_stable_one_per_gender():
    attempt = _gender_sample(get_catalog())

    assert attempt.validated and attempt.reviewed
    assert "customer.entity_num = loan.entity_num" in attempt.sql
    assert "customer.customer_id = loan.customer_id" in attempt.sql
    assert "ROW_NUMBER() OVER" in attempt.sql
    assert "sample_rank = 1" in attempt.sql


def test_agent_details_use_the_governed_directory_and_exact_code():
    attempt = _agent_details(
        LookupPlan(
            selector="agent_code", value="AGNT45", detail="agent_details",
            reasoning="test",
        ),
        get_catalog(),
    )

    assert attempt.validated and attempt.reviewed
    assert "FROM gold.agent_master" in attempt.sql
    assert "LOWER(agent_code) = 'agnt45'" in attempt.sql
    assert "agent_name" in attempt.sql
    assert "linked_loan_count" in attempt.sql


def test_agent_count_uses_the_governed_agent_directory():
    attempt = _agent_count(get_catalog())

    assert attempt.validated and attempt.reviewed
    assert "COUNT(agent_code) AS agent_count" in attempt.sql
    assert "FROM gold.agent_master" in attempt.sql


def test_branch_directory_uses_the_governed_branch_master():
    attempt = _branch_directory(get_catalog())

    assert attempt.validated and attempt.reviewed
    assert "FROM gold.branch_master" in attempt.sql
    assert "branch_code" in attempt.sql
    assert "branch_name" in attempt.sql
    assert "branch_status" in attempt.sql


def test_sanctioned_loans_by_agent_decode_codes_to_directory_names():
    dimension = get_catalog().dimensions["agent"]

    assert dimension.decode == "agent_identity"


def test_numeric_identifiers_follow_text_units_in_rows_and_summary():
    chart = build_from_rows(
        question="account for customer",
        result=QueryResult(
            rows=[{"customer_id": 128.0, "loan_account_number": 1000400001520.0}],
            columns=["customer_id", "loan_account_number"],
            status="ok", duration_ms=1, sql="SELECT 1", row_count=1,
        ),
        lineage=Lineage(path="text_to_sql", sql="SELECT 1", unverified=False),
        unit_hints={"customer_id": "text", "loan_account_number": "text"},
    )

    assert chart.rows == [{
        "customer_id": "128",
        "loan_account_number": "1000400001520",
    }]
    assert "128.00" not in chart.summary
    assert "1,000,400,001,520.00" not in chart.summary
    assert chart.subtitle == "Governed read-only record lookup"


def test_ambiguous_name_returns_customer_choices_instead_of_guessing(monkeypatch):
    from app.services.nlq import lookup

    monkeypatch.setattr(lookup, "execute_raw", lambda _sql: QueryResult(
        rows=[
            {"borrower_name": "ANITHA K", "customer_id": "41", "account_number": "100001"},
            {"borrower_name": "ANITHA K R", "customer_id": "42", "account_number": "100099"},
        ],
        columns=["borrower_name", "customer_id", "account_number"],
        status="ok", duration_ms=1, sql="SELECT 1", row_count=2,
    ))

    result = run(
        LookupPlan(
            selector="borrower_name", value="Anitha K", detail="repayment_history",
            reasoning="test",
        ),
        role="anonymous", catalog=get_catalog(),
    )

    assert result.chart is None
    assert result.clarification is not None
    assert len(result.clarification.suggestions) == 2
    assert "customer ID 41" in result.clarification.suggestions[0]
    assert "account ending 0001" in result.clarification.suggestions[0]


def test_borrower_chat_completion_returns_insertable_name_and_context(monkeypatch):
    from app.services.nlq import lookup

    monkeypatch.setattr(lookup, "execute_raw", lambda _sql: QueryResult(
        rows=[{
            "borrower_name": "SHEELAVATHI M K",
            "customer_id": "128",
            "account_number": "1000400001520",
        }],
        columns=["borrower_name", "customer_id", "account_number"],
        status="ok", duration_ms=1, sql="SELECT 1", row_count=1,
    ))

    assert completions("sheel", "borrower") == [{
        "kind": "borrower",
        "value": "SHEELAVATHI M K",
        "label": "SHEELAVATHI M K",
        "detail": "Customer 128 · Account ending 1520",
    }]


def test_agent_chat_completion_returns_code_for_safe_insertion(monkeypatch):
    from app.services.nlq import lookup

    monkeypatch.setattr(lookup, "execute_raw", lambda _sql: QueryResult(
        rows=[{"agent_code": "AGNT45", "agent_name": "Agent Name", "designation": "Officer"}],
        columns=["agent_code", "agent_name", "designation"],
        status="ok", duration_ms=1, sql="SELECT 1", row_count=1,
    ))

    assert completions("AGNT4", "agent")[0] == {
        "kind": "agent", "value": "AGNT45", "label": "Agent Name",
        "detail": "AGNT45 · Officer",
    }
