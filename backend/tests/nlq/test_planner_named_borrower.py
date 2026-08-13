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


@pytest.mark.anyio
async def test_named_month_disbursement_preserves_branch_breakdown():
    outcome = await plan("Show total disbursement by branch in July 2026")

    assert isinstance(outcome.plan, QuerySpecPlan)
    assert outcome.plan.spec.dimensions == ["branch"]
    compiled = compile_spec(outcome.plan.spec)
    assert "GROUP BY" in compiled.sql
    assert 'lam."branch_code"' in compiled.sql


@pytest.mark.anyio
async def test_disbursement_month_range_preserves_monthly_series():
    outcome = await plan("Show monthly disbursement from January 2026 through July 2026.")

    assert isinstance(outcome.plan, QuerySpecPlan)
    assert outcome.plan.spec.dimensions == ["month"]
    compiled = compile_spec(outcome.plan.spec)
    assert "DATE_TRUNC('month'" in compiled.sql
    assert compiled.params["period_start"].isoformat() == "2026-01-01"
    assert compiled.params["period_end"].isoformat() == "2026-07-31"


@pytest.mark.anyio
async def test_distinct_borrowers_in_named_month_uses_customer_count_without_time_dimension():
    outcome = await plan("How many distinct borrowers received loans in July 2026?")

    assert isinstance(outcome.plan, QuerySpecPlan)
    assert outcome.plan.spec.metrics == ["customer_count"]
    assert outcome.plan.spec.dimensions == []
    compiled = compile_spec(outcome.plan.spec)
    assert "COUNT(DISTINCT lam.customer_id)" in compiled.sql
    assert "DATE_TRUNC" not in compiled.sql


@pytest.mark.anyio
async def test_rank_schemes_over_month_range_keeps_scheme_dimension():
    outcome = await plan(
        "Rank schemes by total disbursement from January 2026 through July 2026."
    )

    assert isinstance(outcome.plan, QuerySpecPlan)
    assert outcome.plan.spec.dimensions == ["scheme"]
    compiled = compile_spec(outcome.plan.spec)
    assert 'lam."scheme_code"' in compiled.sql
    assert "DATE_TRUNC" not in compiled.sql


@pytest.mark.anyio
async def test_compare_two_named_disbursement_months_uses_compare_to():
    outcome = await plan("Compare total disbursement in July 2026 with June 2026.")

    assert isinstance(outcome.plan, QuerySpecPlan)
    assert outcome.plan.spec.dimensions == []
    assert outcome.plan.spec.compare_to is not None
    assert outcome.plan.spec.period.start.isoformat() == "2026-07-01"
    assert outcome.plan.spec.period.end.isoformat() == "2026-07-31"
    assert outcome.plan.spec.compare_to.start.isoformat() == "2026-06-01"
    assert outcome.plan.spec.compare_to.end.isoformat() == "2026-06-30"


@pytest.mark.anyio
async def test_top_borrowers_is_a_governed_current_outstanding_ranking():
    outcome = await plan("top 25 borrowers")

    assert isinstance(outcome.plan, QuerySpecPlan)
    assert outcome.model == "deterministic"
    assert outcome.plan.spec.metrics == ["principal_outstanding"]
    assert outcome.plan.spec.dimensions == ["borrower"]
    assert outcome.plan.spec.limit == 25
    compiled = compile_spec(outcome.plan.spec)
    assert "gold.portfolio_snapshot_as_of(:as_of)" in compiled.sql
    assert 'portfolio."customer_name" AS borrower' in compiled.sql
    assert "ORDER BY SUM(portfolio.principal_outstanding) DESC" in compiled.sql
    assert compiled.params["row_limit"] == 25
