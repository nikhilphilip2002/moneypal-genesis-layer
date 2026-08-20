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


class TestWorklistRoute:
    """"Create today's collection priority list" is not a chart question and not advice —
    it is a preset over the account list. The route has to survive the planner the same way
    the analysis route does."""

    @pytest.mark.anyio
    async def test_a_worklist_plan_survives_parsing(self):
        from app.services.nlq.contracts import WorklistPlan

        client = AnalysisClient(
            '{"route":"worklist","worklist_id":"collections_today","confidence":0.9,'
            '"reasoning":"a priority list"}'
        )
        outcome = await plan("Create today's collection priority list", client=client)
        assert isinstance(outcome.plan, WorklistPlan)
        assert outcome.plan.worklist_id == "collections_today"

    @pytest.mark.anyio
    async def test_a_slice_binds_to_the_preset(self):
        from app.services.nlq.contracts import WorklistPlan

        client = AnalysisClient(
            '{"route":"worklist","worklist_id":"collections_today",'
            '"filters":[{"field":"branch","op":"eq","value":"1002"}],"limit":20,'
            '"confidence":0.9,"reasoning":""}'
        )
        outcome = await plan("Collection list for Aluva", client=client)
        assert isinstance(outcome.plan, WorklistPlan)
        assert outcome.plan.filters[0].value == "1002"
        assert outcome.plan.limit == 20

    @pytest.mark.anyio
    async def test_an_unknown_preset_is_not_accepted(self):
        from app.services.nlq.contracts import WorklistPlan

        client = AnalysisClient(
            '{"route":"worklist","worklist_id":"magic_list","confidence":0.9,"reasoning":""}'
        )
        outcome = await plan("Create a list", client=client)
        assert not isinstance(outcome.plan, WorklistPlan)


class TestThePromptNamesThePresets:
    """The route descriptions say "one of the ANALYSES below" and "one of the WORKLISTS
    below". Until both lists were appended there was nothing below: the schema enum stopped
    the model naming a preset that does not exist, but gave it no way to tell two apart."""

    def test_both_listings_reach_the_model(self):
        from app.services.nlq.llm.prompts import build_messages

        system = build_messages("anything")[0]["content"]
        assert "### ANALYSES" in system
        assert "### WORKLISTS" in system

    def test_every_preset_id_is_named(self):
        from app.services.nlq.catalog import get_catalog
        from app.services.nlq.llm.prompts import build_messages

        catalog = get_catalog()
        system = build_messages("anything")[0]["content"]
        for preset_id in (*catalog.analyses, *catalog.worklists.presets):
            assert preset_id in system, preset_id

    def test_the_schema_offers_both_routes(self):
        import json

        from app.services.nlq.llm.schemas import plan_schema

        rendered = json.dumps(plan_schema())
        assert '"const": "analysis"' in rendered
        assert '"const": "worklist"' in rendered


class TestBriefingRoute:
    """"What do I need to know?" is a chat question like any other, and it answers in the
    thread. There is no dashboard, no tab and no panel — the whole product is the
    conversation, so a standing read has to arrive as a turn in it."""

    @pytest.mark.anyio
    async def test_a_briefing_plan_survives_parsing(self):
        from app.services.nlq.contracts import BriefingPlan

        client = AnalysisClient(
            '{"route":"briefing","persona_id":"ceo","confidence":0.9,"reasoning":"open read"}'
        )
        outcome = await plan("What do I need to know this morning?", client=client)
        assert isinstance(outcome.plan, BriefingPlan)
        assert outcome.plan.persona_id == "ceo"

    @pytest.mark.anyio
    async def test_the_desk_in_the_question_binds(self):
        from app.services.nlq.contracts import BriefingPlan

        client = AnalysisClient(
            '{"route":"briefing","persona_id":"collections","confidence":0.9,"reasoning":""}'
        )
        outcome = await plan("Anything collections should worry about?", client=client)
        assert isinstance(outcome.plan, BriefingPlan)
        assert outcome.plan.persona_id == "collections"

    @pytest.mark.anyio
    async def test_an_unknown_desk_is_not_accepted(self):
        from app.services.nlq.contracts import BriefingPlan

        client = AnalysisClient(
            '{"route":"briefing","persona_id":"marketing","confidence":0.9,"reasoning":""}'
        )
        outcome = await plan("What should marketing know?", client=client)
        assert not isinstance(outcome.plan, BriefingPlan)

    def test_the_desks_are_named_in_the_prompt(self):
        """The route description says "DESKS below". Until they were listed there was
        nothing below, and the model had no way to tell `risk` from `collections`."""
        from app.services.nlq.catalog import get_catalog
        from app.services.nlq.llm.prompts import build_messages

        system = build_messages("anything")[0]["content"]
        assert "### DESKS" in system
        for persona_id in get_catalog().personas:
            assert persona_id in system, persona_id

    def test_the_schema_offers_the_route(self):
        import json

        from app.services.nlq.llm.schemas import plan_schema

        assert '"const": "briefing"' in json.dumps(plan_schema())
