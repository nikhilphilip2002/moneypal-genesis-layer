"""High-frequency lending language should not depend on a model guess."""

from __future__ import annotations

import pytest

from app.services.nlq import cache
from app.services.nlq.catalog import get_catalog
from app.services.nlq.compiler import compile_spec
from app.services.nlq.contracts import (
    BriefingPlan,
    ClarifyPlan,
    QuerySpecPlan,
    RefusalPlan,
    SqlPlan,
)
from app.services.nlq.planner import plan
from app.services.nlq.text_to_sql import generate


class NoModel:
    provider = "unused"
    model = "unused"

    async def complete(self, **kwargs):  # pragma: no cover - a call is the test failure
        raise AssertionError("the reviewed common-intent path must not call the LLM")


@pytest.fixture(autouse=True)
def _clear_plan_cache():
    cache.clear_all()


@pytest.mark.anyio
@pytest.mark.parametrize(
    "question,metric,dimensions",
    [
        ("How many borrowers are there by product?", "customer_count", ["product"]),
        ("Show the loan-count split between open and closed accounts.", "loan_count", ["open_closed_status"]),
        ("intrest rate based on schema name", "avg_interest_rate", ["scheme"]),
        ("schema name and the amount paid", "amount_collected", ["scheme"]),
        ("what is the total loan amount sanctioned?", "sanctioned_amount", []),
    ],
)
async def test_common_question_maps_to_reviewed_queryspec(question, metric, dimensions):
    outcome = await plan(question, client=NoModel())

    assert isinstance(outcome.plan, QuerySpecPlan)
    assert outcome.plan.spec.metrics == [metric]
    assert outcome.plan.spec.dimensions == dimensions
    assert outcome.attempts == 0
    # Prove that each shortcut is accepted by the same compiler as an LLM-produced spec.
    assert compile_spec(outcome.plan.spec, get_catalog()).sql.startswith("SELECT")


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("question", "metric", "filter_field", "filter_value"),
    [
        ("what is the total amount of equity shares", "share_capital", None, None),
        ("what is the capital share", "share_capital", None, None),
        ("what is the total capital reserve sharesz", "capital_reserves", None, None),
        ("show reserves and surplus", "capital_reserves", None, None),
        ("what is the sanction amount of agent 45", "sanctioned_amount", "agent", ["45", "agent45", "agnt45"]),
        ("total approved amount under AGNT45", "sanctioned_amount", "agent", ["45", "agent45", "agnt45"]),
        ("how many agriculturist loan accounts is theer", "loan_count", "occupation", "AGRICULT"),
        ("How many agricultural loan accounts are there?", "loan_count", "scheme", ["1611", "1621"]),
    ],
)
async def test_governed_business_entities_bypass_the_model(
    question, metric, filter_field, filter_value
):
    outcome = await plan(question, client=NoModel())

    assert isinstance(outcome.plan, QuerySpecPlan)
    assert outcome.plan.spec.metrics == [metric]
    assert outcome.attempts == 0
    if filter_field is None:
        assert outcome.plan.spec.filters == []
    else:
        assert outcome.plan.spec.filters[0].field == filter_field
        assert outcome.plan.spec.filters[0].value == filter_value
    assert compile_spec(outcome.plan.spec, get_catalog()).sql.startswith("SELECT")


@pytest.mark.anyio
async def test_natural_top_agent_wording_ranks_by_linked_loan_accounts():
    outcome = await plan("which agent under more loan accounts is ther", client=NoModel())

    assert isinstance(outcome.plan, QuerySpecPlan)
    assert outcome.plan.spec.metrics == ["agent_linked_loans"]
    assert outcome.plan.spec.dimensions == ["agent_profile"]
    assert outcome.plan.spec.order_by.field == "agent_linked_loans"
    assert outcome.plan.spec.order_by.direction == "desc"


@pytest.mark.anyio
@pytest.mark.parametrize("state_word", ["open", "active", "live"])
async def test_single_open_account_count_filters_instead_of_grouping(state_word):
    outcome = await plan(f"How many {state_word} loan accounts are there", client=NoModel())

    assert isinstance(outcome.plan, QuerySpecPlan)
    assert outcome.plan.spec.metrics == ["loan_count"]
    assert outcome.plan.spec.dimensions == []
    assert outcome.plan.spec.filters[0].field == "open_closed_status"
    assert outcome.plan.spec.filters[0].value == "Open"
    assert outcome.attempts == 0
    assert compile_spec(outcome.plan.spec, get_catalog()).sql.startswith("SELECT")


@pytest.mark.anyio
async def test_various_interest_rates_uses_validated_column_query_path():
    outcome = await plan("what are the various intrest rate?", client=NoModel())
    assert isinstance(outcome.plan, SqlPlan)
    assert outcome.plan.tables == ["gold.loan_account_master"]

    attempt = await generate("what are the various intrest rate?", client=NoModel())
    assert attempt.validated is True
    assert "GROUP BY" in attempt.sql and "interest_rate" in attempt.sql
    assert attempt.column_units == {"interest_rate": "percent", "loan_count": "count"}


@pytest.mark.anyio
async def test_interest_rate_amount_explains_the_unit_mismatch_and_offers_real_metrics():
    outcome = await plan("what is the total intrest rate amunt?", client=NoModel())
    assert isinstance(outcome.plan, ClarifyPlan)
    assert "percentage" in outcome.plan.question
    assert outcome.plan.suggestions == [
        "What is the total interest collected?",
        "What is the total interest due?",
        "What is the average interest rate?",
    ]


@pytest.mark.anyio
@pytest.mark.parametrize(
    "question",
    [
        "Why are disbursements above or below target?",
        "Which branches are performing above and below expectations?",
        "What is the conversion rate at each stage of the sales funnel?",
        "Where are approval rates changing significantly?",
        "Which products have the highest contribution margin?",
        "Why is profitability different from budget?",
        "Which legal matters or cases require attention?",
        "What recurring audit observations should management be concerned about?",
    ],
)
async def test_known_enterprise_data_gaps_refuse_without_calling_the_model(question):
    outcome = await plan(question, client=NoModel())
    assert isinstance(outcome.plan, RefusalPlan)
    assert outcome.plan.reason == "not_in_data"
    assert outcome.attempts == 0


@pytest.mark.anyio
async def test_vintage_performance_uses_promoted_gold_matrix():
    outcome = await plan("How is our vintage performance changing?", client=NoModel())
    assert isinstance(outcome.plan, QuerySpecPlan)
    assert outcome.plan.spec.metrics == ["vintage_par30_rate", "vintage_npa_rate"]
    assert outcome.plan.spec.dimensions == ["vintage_origination_month", "month"]
    assert outcome.attempts == 0


@pytest.mark.anyio
async def test_data_pipeline_issues_use_existing_freshness_signals():
    outcome = await plan(
        "Which technology or data issues are impacting business performance?",
        client=NoModel(),
    )
    assert isinstance(outcome.plan, BriefingPlan)
    assert outcome.plan.persona_id == "ceo"
    assert outcome.attempts == 0


@pytest.mark.anyio
@pytest.mark.parametrize(
    "question,metric,dimensions,filter_value,period",
    [
        (
            "Show our gold loan disbursement trend over time",
            "disbursement_total", ["month"], "Gold Loans", "all_time",
        ),
        (
            "How much have we disbursed in gold loans?",
            "disbursement_total", [], "Gold Loans", "all_time",
        ),
        (
            "How do our portfolio delinquency levels in MSME schemes compare with SIDBI?",
            "par_30", ["scheme"], "Business & MSME Loans", "today",
        ),
        (
            "How does our borrower gender diversity compare with microfinance targets?",
            "customer_count", ["gender"], None, "all_time",
        ),
    ],
)
async def test_benchmark_internal_tasks_use_complete_governed_plans(
    question, metric, dimensions, filter_value, period,
):
    outcome = await plan(question, client=NoModel())

    assert isinstance(outcome.plan, QuerySpecPlan)
    assert outcome.plan.spec.metrics == [metric]
    assert outcome.plan.spec.dimensions == dimensions
    assert outcome.plan.spec.period.relative == period
    if filter_value is not None:
        assert outcome.plan.spec.filters[0].value == filter_value
    assert compile_spec(outcome.plan.spec, get_catalog()).sql.startswith("SELECT")
