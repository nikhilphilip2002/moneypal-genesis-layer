import pytest

from app.services.nlq.contracts import QuerySpecPlan
from app.services.nlq.planner import plan


class PlannerMustNotRun:
    provider = "test"
    model = "test"

    async def complete(self, **_kwargs):
        raise AssertionError("an explicit governed metric question must not call the LLM")


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("question", "metric", "dimensions", "period"),
    [
        ("What is our current PAR 30 ratio?", "par_30", [], "today"),
        (
            "What is our total disbursed amount this financial year?",
            "disbursement_total",
            [],
            "fy_to_date",
        ),
        (
            "Which schemes have the highest overdue principal?",
            "overdue_principal",
            ["scheme"],
            "today",
        ),
        (
            "Rank the top 10 agents by sanctioned loan count.",
            "loan_count",
            ["loan_agent"],
            "all_time",
        ),
        (
            "How much interest have we collected this financial year?",
            "interest_collected",
            [],
            "fy_to_date",
        ),
        (
            "What is the weighted average contractual interest rate?",
            "avg_interest_rate",
            [],
            "all_time",
        ),
        (
            "Show principal-outstanding composition by asset classification over the last 90 days",
            "principal_outstanding",
            ["asset_class"],
            "last_90_days",
        ),
        (
            "Show the monthly principal repayment trend.",
            "principal_collected",
            ["month"],
            "all_time",
        ),
        (
            "Which ten borrowers received the largest sanctioned amounts?",
            "sanctioned_amount",
            ["borrower"],
            "all_time",
        ),
        (
            "Which application branches serve the most female borrowers?",
            "customer_count",
            ["branch"],
            "all_time",
        ),
    ],
)
async def test_explicit_governed_metric_questions_skip_the_llm(
    question, metric, dimensions, period,
):
    outcome = await plan(question, client=PlannerMustNotRun())

    assert isinstance(outcome.plan, QuerySpecPlan)
    assert outcome.model == "deterministic"
    assert outcome.plan.spec.metrics == [metric]
    assert outcome.plan.spec.dimensions == dimensions
    assert outcome.plan.spec.period.relative == period


@pytest.mark.anyio
async def test_npa_account_count_uses_the_classified_snapshot_metric():
    outcome = await plan(
        "How many accounts are currently classified as NPA?",
        client=PlannerMustNotRun(),
    )

    assert isinstance(outcome.plan, QuerySpecPlan)
    assert outcome.plan.spec.metrics == ["classified_account_count"]
    assert any(
        item.field == "asset_class" and item.value == "NPA"
        for item in outcome.plan.spec.filters
    )


@pytest.mark.anyio
async def test_female_borrower_breakdown_keeps_filter_and_scheme_dimension():
    outcome = await plan(
        "Break female borrower count down by scheme.",
        client=PlannerMustNotRun(),
    )

    assert isinstance(outcome.plan, QuerySpecPlan)
    assert outcome.plan.spec.metrics == ["customer_count"]
    assert outcome.plan.spec.dimensions == ["scheme"]
    assert any(item.field == "gender" and item.value == "F" for item in outcome.plan.spec.filters)
