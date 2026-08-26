"""Regression coverage for generalized customer/account record lookups."""

import pytest

from app.services.nlq.catalog import get_catalog
from app.services.nlq.charts import build_from_rows
from app.services.nlq.contracts import Lineage, LookupPlan
from app.services.nlq.executor import QueryResult
from app.services.nlq.lookup import (
    _gender_sample,
    _loan_details,
    _repayment_history,
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
