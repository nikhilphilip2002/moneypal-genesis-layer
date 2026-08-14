"""High-frequency lending language should not depend on a model guess."""

from __future__ import annotations

import pytest

from app.services.nlq import cache
from app.services.nlq.catalog import get_catalog
from app.services.nlq.compiler import compile_spec
from app.services.nlq.contracts import ClarifyPlan, QuerySpecPlan, SqlPlan
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
