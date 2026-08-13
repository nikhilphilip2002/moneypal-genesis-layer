import pytest

from app.services.nlq.contracts import SqlPlan
from app.services.nlq.planner import plan


@pytest.mark.anyio
async def test_named_borrower_principal_routes_without_calling_an_llm():
    outcome = await plan("principle amount paid by sheelavati")

    assert isinstance(outcome.plan, SqlPlan)
    assert outcome.plan.tables == ["silver.loan_account_master"]
    assert outcome.model == "deterministic"
    assert outcome.attempts == 0


@pytest.mark.anyio
async def test_named_borrower_disbursement_routes_without_calling_an_llm():
    outcome = await plan("loan amount disburdsed to shellavati")

    assert isinstance(outcome.plan, SqlPlan)
    assert outcome.plan.tables == ["silver.loan_account_master"]
    assert outcome.model == "deterministic"
    assert outcome.attempts == 0
