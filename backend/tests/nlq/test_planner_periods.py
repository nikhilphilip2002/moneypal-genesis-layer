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
