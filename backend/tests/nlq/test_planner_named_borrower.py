import pytest

from app.services.nlq.compiler import compile_spec
from app.services.nlq.contracts import QuerySpecPlan, SqlPlan
from app.services.nlq.planner import plan


@pytest.mark.anyio
async def test_named_borrower_principal_routes_without_calling_an_llm():
    outcome = await plan("principle amount paid by sheelavati")

    assert isinstance(outcome.plan, SqlPlan)
    assert outcome.plan.tables == ["gold.loan_account_master"]
    assert outcome.model == "deterministic"
    assert outcome.attempts == 0


@pytest.mark.anyio
async def test_named_borrower_disbursement_routes_without_calling_an_llm():
    outcome = await plan("loan amount disburdsed to shellavati")

    assert isinstance(outcome.plan, SqlPlan)
    assert outcome.plan.tables == ["gold.loan_account_master"]
    assert outcome.model == "deterministic"
    assert outcome.attempts == 0


@pytest.mark.anyio
async def test_agent_borrower_count_routes_without_calling_an_llm():
    outcome = await plan("under agent45 how many borrowers are there??")

    assert isinstance(outcome.plan, QuerySpecPlan)
    assert outcome.plan.spec.metrics == ["customer_count"]
    assert outcome.plan.spec.filters[0].field == "agent"
    assert outcome.plan.spec.filters[0].value == ["45", "agent45"]
    compiled = compile_spec(outcome.plan.spec)
    assert "gold.loan_account_master" in compiled.sql
    assert 'LOWER(lam."agent_code"::text) = ANY(:f0)' in compiled.sql
    assert compiled.params["f0"] == ["45", "agent45"]


@pytest.mark.anyio
async def test_named_month_disbursement_routes_without_calling_an_llm():
    outcome = await plan("What was our total disbursement in July 2026?")

    assert isinstance(outcome.plan, QuerySpecPlan)
    assert outcome.model == "deterministic"
    assert outcome.attempts == 0
    assert outcome.plan.spec.metrics == ["disbursement_total"]
    compiled = compile_spec(outcome.plan.spec)
    assert "gold.loan_disbursement_events" in compiled.sql
    assert compiled.params["period_start"].isoformat() == "2026-07-01"
    assert compiled.params["period_end"].isoformat() == "2026-07-31"
