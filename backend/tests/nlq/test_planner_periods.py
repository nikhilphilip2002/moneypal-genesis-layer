import pytest

from app.services.nlq import cache
from app.services.nlq.contracts import QuerySpecPlan
from app.services.nlq.llm.client import LLMResult
from app.services.nlq.planner import plan


class FixedPlanClient:
    provider = "test"
    model = "test"

    def __init__(self):
        self.calls = []

    async def complete(self, **kwargs):
        self.calls.append(kwargs)
        return LLMResult(
            text=(
                '{"route":"queryspec","confidence":0.95,"reasoning":"composition",'
                '"spec":{"metrics":["principal_outstanding"],'
                '"dimensions":["month","asset_class"],'
                '"period":{"start":"2025-12-01","end":"2026-02-28"},'
                '"as_share":true}}'
            ),
            model=self.model,
            provider=self.provider,
        )


class WrongOverduePlanClient(FixedPlanClient):
    async def complete(self, **kwargs):
        self.calls.append(kwargs)
        return LLMResult(
            text=(
                '{"route":"queryspec","confidence":0.95,"reasoning":"wrong ratio",'
                '"spec":{"metrics":["par_30"],"dimensions":["asset_class"],'
                '"period":{"relative":"today"},"as_share":false}}'
            ),
            model=self.model,
            provider=self.provider,
        )


@pytest.mark.anyio
async def test_last_90_days_cannot_be_replaced_with_model_guessed_dates():
    cache.clear_all()
    outcome = await plan(
        "Show monthly principal-outstanding composition by asset classification over the last 90 days",
        client=FixedPlanClient(),
    )

    assert isinstance(outcome.plan, QuerySpecPlan)
    assert outcome.plan.spec.period.relative == "last_90_days"
    assert outcome.plan.spec.period.start is None
    assert outcome.plan.spec.period.end is None


@pytest.mark.anyio
async def test_session_history_is_sent_before_the_current_planner_question():
    cache.clear_all()
    client = FixedPlanClient()
    history_messages = [
        {"role": "user", "content": "Show principal outstanding"},
        {"role": "assistant", "content": "Principal outstanding was ₹10 Cr."},
    ]

    await plan(
        "now by asset classification",
        client=client,
        history_messages=history_messages,
    )

    sent = client.calls[0]["messages"]
    assert sent[-3:] == [
        *history_messages,
        {"role": "user", "content": "now by asset classification"},
    ]


@pytest.mark.anyio
async def test_explicit_overdue_principal_share_cannot_be_changed_to_par30():
    cache.clear_all()
    outcome = await plan(
        "Show the overdue-principal share by asset classification today.",
        client=WrongOverduePlanClient(),
    )

    assert isinstance(outcome.plan, QuerySpecPlan)
    assert outcome.plan.spec.metrics == ["overdue_principal"]
    assert outcome.plan.spec.dimensions == ["asset_class"]
    assert outcome.plan.spec.as_share is True


@pytest.mark.anyio
async def test_donut_suffix_is_removed_and_converted_to_share_intent():
    cache.clear_all()
    client = WrongOverduePlanClient()
    await plan(
        "Show the overdue-principal share by asset classification today in a donut graph.",
        client=client,
    )

    sent_question = client.calls[0]["messages"][-1]["content"]
    assert "donut" not in sent_question.lower()
    assert "share or composition" in sent_question.lower()


@pytest.mark.anyio
async def test_chart_only_followup_reuses_previous_user_question():
    cache.clear_all()
    client = WrongOverduePlanClient()
    history_messages = [
        {
            "role": "user",
            "content": "Show the overdue-principal share by asset classification today.",
        },
        {"role": "assistant", "content": "Previous chart result."},
    ]
    await plan("in a donut graph", client=client, history_messages=history_messages)

    sent_question = client.calls[0]["messages"][-1]["content"]
    assert sent_question.startswith("Show the overdue-principal share")
    assert "share or composition" in sent_question.lower()


@pytest.mark.anyio
async def test_this_financial_year_cannot_be_replaced_with_a_hard_coded_prior_fy():
    cache.clear_all()

    class PriorFyClient(FixedPlanClient):
        async def complete(self, **kwargs):
            self.calls.append(kwargs)
            return LLMResult(
                text=(
                    '{"route":"queryspec","confidence":0.95,"spec":{'
                    '"metrics":["collection_efficiency"],"dimensions":["product"],'
                    '"period":{"start":"2025-04-01","end":"2026-03-31"}}}'
                ),
                model="test",
                provider="test",
            )

    outcome = await plan(
        "Collection efficiency by product this financial year",
        client=PriorFyClient(),
    )

    assert isinstance(outcome.plan, QuerySpecPlan)
    assert outcome.plan.spec.period.relative == "fy_to_date"
    assert outcome.plan.spec.period.start is None
    assert outcome.plan.spec.period.end is None
