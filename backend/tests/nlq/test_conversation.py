"""Multi-turn context.

The structural follow-up path is the one that matters most: it skips the LLM entirely, so
it must be right by construction. A false positive here silently answers a different
question than the one asked, which is worse than not recognising the follow-up at all.
"""

import pytest

from app.services.nlq import conversation
from app.services.nlq.catalog import get_catalog
from app.services.nlq.contracts import ConversationState, Filter, Period, QuerySpec


@pytest.fixture(scope="module")
def catalog():
    return get_catalog()


@pytest.fixture
def state(catalog):
    anchor = QuerySpec(
        metrics=["disbursement_total"],
        dimensions=["month"],
        period=Period(relative="last_quarter"),
    )
    state = ConversationState(conversation_id="test")
    conversation.set_anchor(state, anchor)
    return state


class TestStructuralFollowUps:
    """These resolve without any model call — instant, free, and always correct."""

    @pytest.mark.parametrize(
        "question",
        ["and by branch?", "by branch", "now show me by branch", "break it down by branch"],
    )
    def test_adding_a_dimension_is_recognised(self, question, state, catalog):
        resolved, spec = conversation.resolve(question, state, catalog)
        assert spec is not None, "should not have needed the LLM"
        assert "branch" in spec.dimensions
        assert "disbursement" in resolved.lower()

    def test_a_new_categorical_replaces_the_previous_one(self, state, catalog):
        """Stacking would produce a two-dimensional heatmap nobody asked for."""
        _resolved, spec = conversation.resolve("and by branch?", state, catalog)
        conversation.set_anchor(state, spec)
        _resolved2, spec2 = conversation.resolve("and by product?", state, catalog)
        assert spec2.dimensions.count("product") == 1
        assert "branch" not in spec2.dimensions
        assert "month" in spec2.dimensions  # the time axis survives

    @pytest.mark.parametrize("question", ["same for gold loans", "what about gold loans?"])
    def test_changing_a_filter_is_recognised(self, question, state, catalog):
        resolved, spec = conversation.resolve(question, state, catalog)
        assert spec is not None
        assert any(f.field == "product" and f.value == "1" for f in spec.filters)
        assert "Gold Loans" in resolved

    def test_a_replaced_filter_does_not_stack(self, state, catalog):
        _r, spec = conversation.resolve("same for gold loans", state, catalog)
        conversation.set_anchor(state, spec)
        _r2, spec2 = conversation.resolve("what about MSME?", state, catalog)
        product_filters = [f for f in spec2.filters if f.field == "product"]
        assert len(product_filters) == 1
        assert product_filters[0].value == "16"

    def test_an_unrecognised_dimension_falls_through_to_the_planner(self, state, catalog):
        _resolved, spec = conversation.resolve("and by salesperson?", state, catalog)
        assert spec is None


class TestAnchorReset:
    def test_a_question_naming_its_own_metric_resets_the_anchor(self, state, catalog):
        """Otherwise a fresh question silently inherits the previous one's filters."""
        question = "What is our collection efficiency by product this year?"
        resolved, spec = conversation.resolve(question, state, catalog)
        assert spec is None
        assert resolved == question

    def test_no_anchor_means_no_rewriting(self, catalog):
        empty = ConversationState(conversation_id="fresh")
        resolved, spec = conversation.resolve("and by branch?", empty, catalog)
        assert spec is None
        assert resolved == "and by branch?"

    def test_elliptical_but_unrecognised_still_gets_context(self, state, catalog):
        """The planner should see a complete question, not a fragment — and the audit log
        should record what was actually meant."""
        resolved, spec = conversation.resolve("how about weekly", state, catalog)
        assert spec is None
        assert "disbursement" in resolved.lower()


class TestStickyFilters:
    def test_equality_filters_become_visible_chips(self, catalog):
        spec = QuerySpec(
            metrics=["loan_count"],
            filters=[Filter(field="product", op="eq", value="1")],
            period=Period(relative="all_time"),
        )
        state = ConversationState(conversation_id="c")
        conversation.set_anchor(state, spec)
        chips = conversation.sticky_filters(state, catalog)
        assert len(chips) == 1
        assert chips[0]["field"] == "product"
        assert chips[0]["display"] == "Gold Loans"  # decoded, not the raw code

    def test_non_equality_filters_do_not_become_chips(self, catalog):
        """A chip implies "click to remove"; a `not_in` filter cannot be expressed that
        way, so showing one would promise an interaction that does not exist."""
        spec = QuerySpec(
            metrics=["loan_count"],
            filters=[Filter(field="branch", op="not_in", value=["1", "4"])],
            period=Period(relative="all_time"),
        )
        state = ConversationState(conversation_id="c")
        conversation.set_anchor(state, spec)
        assert conversation.sticky_filters(state, catalog) == []


class TestTurnHistory:
    def test_only_the_last_five_turns_are_retained(self):
        state = ConversationState(conversation_id="c")
        for index in range(8):
            conversation.append_turn(state, f"q{index}", f"q{index}", "queryspec", "bar", 1)
        assert len(state.turns) == 5
        assert state.turns[0].question == "q3"

    def test_expired_context_is_discarded_not_resumed(self, monkeypatch):
        from datetime import datetime, timedelta, timezone

        stale = ConversationState(
            conversation_id="stale",
            updated_at=datetime.now(timezone.utc) - timedelta(hours=2),
        )
        stale.active_spec = QuerySpec(
            metrics=["loan_count"], period=Period(relative="all_time")
        )
        monkeypatch.setattr(conversation, "_memory", {"stale": stale})
        monkeypatch.setattr(conversation, "_ensure_table", lambda: False)

        loaded = conversation.load("stale")
        assert loaded.active_spec is None
        assert loaded.turns == []
