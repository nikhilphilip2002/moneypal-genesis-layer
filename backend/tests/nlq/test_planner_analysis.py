"""The `analysis` route has to survive the planner, not just the JSON schema.

The schema offered the model an `analysis` branch while `_parse` still whitelisted four
routes, so every analysis plan was rejected as an unknown route and demoted to text-to-SQL —
the whole multi-query feature was unreachable from a question. These tests pin the route open
end to end.
"""

from __future__ import annotations

import pytest

from app.services.nlq import cache
from app.services.nlq.contracts import AnalysisPlan, ClarifyPlan, Period
from app.services.nlq.llm.client import LLMResult
from app.services.nlq.planner import plan


class AnalysisClient:
    provider = "test"
    model = "test"

    def __init__(self, body: str):
        self.body = body

    async def complete(self, **kwargs):
        return LLMResult(text=self.body, model=self.model, provider=self.provider)


@pytest.fixture(autouse=True)
def _clear_plan_cache():
    cache.clear_all()


@pytest.mark.anyio
async def test_an_analysis_plan_survives_parsing():
    client = AnalysisClient(
        '{"route":"analysis","analysis_id":"portfolio_health","confidence":0.9,'
        '"reasoning":"a briefing"}'
    )
    outcome = await plan("How is the business doing?", client=client)

    assert isinstance(outcome.plan, AnalysisPlan)
    assert outcome.plan.analysis_id == "portfolio_health"


@pytest.mark.anyio
async def test_the_period_and_filters_bind_to_the_preset():
    client = AnalysisClient(
        '{"route":"analysis","analysis_id":"portfolio_health",'
        '"period":{"relative":"last_quarter"},'
        '"filters":[{"field":"product","op":"eq","value":"1"}],'
        '"confidence":0.9,"reasoning":""}'
    )
    outcome = await plan("How did gold loans do last quarter?", client=client)

    assert isinstance(outcome.plan, AnalysisPlan)
    assert outcome.plan.period == Period(relative="last_quarter")
    assert outcome.plan.filters[0].field == "product"


@pytest.mark.anyio
async def test_an_unknown_preset_is_not_accepted():
    """A hallucinated preset id must fail validation and be retried, not reach `build` and
    raise there — by then the turn has already been reported as an analysis."""
    client = AnalysisClient(
        '{"route":"analysis","analysis_id":"quarterly_magic","confidence":0.9,"reasoning":""}'
    )
    outcome = await plan("How is the business doing?", client=client)

    assert not isinstance(outcome.plan, AnalysisPlan)


@pytest.mark.anyio
async def test_a_low_confidence_analysis_asks_instead():
    client = AnalysisClient(
        '{"route":"analysis","analysis_id":"portfolio_health","confidence":0.2,"reasoning":""}'
    )
    outcome = await plan("how are things", client=client)

    assert isinstance(outcome.plan, ClarifyPlan)


@pytest.mark.anyio
async def test_the_union_fields_of_other_routes_are_trimmed_away():
    """Models routinely emit the whole union. `extra="forbid"` would reject an otherwise
    correct analysis plan, which is what `_trim_to_route` exists to prevent."""
    client = AnalysisClient(
        '{"route":"analysis","analysis_id":"concentration","confidence":0.9,"reasoning":"",'
        '"spec":null,"intent":"unused","tables":[],"question":"unused"}'
    )
    outcome = await plan("How concentrated is the book?", client=client)

    assert isinstance(outcome.plan, AnalysisPlan)
    assert outcome.plan.analysis_id == "concentration"
