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


class TestDrillFollowUps:
    """The chain: why -> which branches -> which accounts, none of it touching a model."""

    @pytest.mark.parametrize(
        "question", ["why?", "why", "why is that?", "and why did it change?", "why so"]
    )
    def test_a_bare_why_becomes_a_decomposition(self, question, state, catalog):
        resolved, spec = conversation.resolve(question, state, catalog)
        assert spec is not None
        assert spec.explain is True
        assert spec.compare_to is not None
        assert "why" in resolved.lower()

    def test_why_keeps_the_anchors_metric(self, state, catalog):
        _, spec = conversation.resolve("why?", state, catalog)
        assert spec.metrics[0] == "disbursement_total"

    def test_why_is_not_offered_twice_in_a_row(self, state, catalog):
        _, spec = conversation.resolve("why?", state, catalog)
        conversation.set_anchor(state, spec)
        _, again = conversation.resolve("why?", state, catalog)
        assert again is None

    @pytest.mark.parametrize("question", ["which branches?", "what branches", "which branch"])
    def test_which_dimension_splits_by_that_dimension(self, question, state, catalog):
        resolved, spec = conversation.resolve(question, state, catalog)
        assert spec is not None
        assert "branch" in spec.dimensions

    def test_which_accounts_reaches_the_entity_level(self, state, catalog):
        resolved, spec = conversation.resolve("which accounts?", state, catalog)
        assert spec is not None
        assert spec.dimensions == ["month", catalog.drill.entity]

    def test_a_full_question_naming_a_dimension_is_not_a_follow_up(self, state, catalog):
        """"Which branches have the lowest collection efficiency?" names its own metric and
        must be planned, not folded onto the anchor."""
        _, spec = conversation.resolve(
            "which branches have the lowest collection efficiency?", state, catalog
        )
        assert spec is None

    def test_an_unknown_dimension_falls_through_to_the_planner(self, state, catalog):
        _, spec = conversation.resolve("which cost centres?", state, catalog)
        assert spec is None

    def test_region_still_resolves_to_branch(self, state, catalog):
        """The catalog lists `region` as a synonym of branch, because no branch master and
        therefore no real geography exists. Pinned here so that the day a region feed lands
        and `drill.yaml` promotes the pending rung, this test fails and forces the synonym
        to be reconsidered rather than left aliasing two different things."""
        _, spec = conversation.resolve("which regions?", state, catalog)
        assert spec is not None
        assert "branch" in spec.dimensions

    def test_resplitting_after_why_drops_the_decomposition(self, state, catalog):
        """"why? -> which accounts?" must produce a list of accounts, not a fifty-bar
        waterfall of a change the user has stopped asking about."""
        _, explained = conversation.resolve("why?", state, catalog)
        conversation.set_anchor(state, explained)

        _, spec = conversation.resolve("which accounts?", state, catalog)
        assert spec is not None
        assert spec.explain is False
        assert spec.compare_to is None

    def test_resplitting_after_why_drops_the_carried_weight_metric(self, state, catalog):
        """A ratio's explanation carries its denominator so the split stays exact. That
        companion is an implementation detail of the decomposition, and leaving it behind
        turns a simple breakdown into a two-metric grouped bar."""
        anchor = QuerySpec(
            metrics=["collection_efficiency"],
            dimensions=["branch"],
            period=Period(relative="this_month"),
        )
        conversation.set_anchor(state, anchor)
        _, explained = conversation.resolve("why?", state, catalog)
        assert explained.metrics == ["collection_efficiency", "amount_due"]
        conversation.set_anchor(state, explained)

        _, spec = conversation.resolve("which accounts?", state, catalog)
        assert spec.metrics == ["collection_efficiency"]

    def test_a_deliberate_second_metric_survives_a_resplit(self, state, catalog):
        """Only the auto-added weight is stripped. A two-metric question the user actually
        asked for keeps both."""
        anchor = QuerySpec(
            metrics=["disbursement_total", "loan_count"],
            dimensions=["branch"],
            period=Period(relative="this_month"),
        )
        conversation.set_anchor(state, anchor)
        _, spec = conversation.resolve("which products?", state, catalog)
        assert spec.metrics == ["disbursement_total", "loan_count"]

    def test_why_without_an_anchor_falls_through(self, catalog):
        empty = ConversationState(conversation_id="fresh")
        _, spec = conversation.resolve("why?", empty, catalog)
        assert spec is None


class TestStructuralFollowUps:
    """These resolve without any model call — instant, free, and always correct."""

    @pytest.mark.parametrize(
        "question",
        [
            "and by branch?",
            "by branch",
            "now show me by branch",
            "now show it by branch",
            "break it down by branch",
            "break that down by branch.",
            "split the result by branch",
        ],
    )
    def test_adding_a_dimension_is_recognised(self, question, state, catalog):
        resolved, spec = conversation.resolve(question, state, catalog)
        assert spec is not None, "should not have needed the LLM"
        assert "branch" in spec.dimensions
        assert "disbursement" in resolved.lower()

    def test_monthly_trend_adds_the_time_dimension(self, state, catalog):
        resolved, spec = conversation.resolve("Show the monthly trend.", state, catalog)

        assert spec is not None
        assert "month" in spec.dimensions
        assert "disbursement" in resolved.lower()

    def test_application_branch_wording_uses_a_metric_compatible_dimension(self, catalog):
        state = ConversationState(conversation_id="portfolio")
        conversation.set_anchor(
            state,
            QuerySpec(
                metrics=["principal_outstanding"],
                period=Period(relative="today"),
            ),
        )

        _resolved, spec = conversation.resolve(
            "Now show it by application branch.", state, catalog,
        )

        assert spec is not None
        assert spec.dimensions == ["branch"]

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


class TestTheChainEndsInAction:
    """"What should we do?" is the last rung, and the whole point of the chain. It resolves
    to a worklist rather than another chart."""

    def _anchor(self, **kwargs):
        base = dict(
            metrics=["overdue_total"],
            dimensions=["branch"],
            period=Period(relative="this_month"),
        )
        base.update(kwargs)
        return ConversationState(conversation_id="chain", active_spec=QuerySpec(**base))

    @pytest.mark.parametrize(
        "question",
        [
            "what should we do?",
            "what should we do about that",
            "what should we do about these",
            "who should we call?",
            "create today's collection priority list",
            "collection priority list",
            "give me the call list",
        ],
    )
    def test_it_resolves_to_a_worklist_question(self, question, catalog):
        resolved, structural = conversation.resolve(question, self._anchor(), catalog)
        assert "collection priority list" in resolved
        # A worklist is not a QuerySpec, so the structural shortcut correctly declines it and
        # the planner routes the rewritten words.
        assert structural is None

    def test_it_carries_the_slice_the_card_was_showing(self, catalog):
        """Asked under a chart of Aluva's arrears, it must produce Aluva's list rather than
        the whole bank's."""
        state = self._anchor(filters=[Filter(field="branch", op="eq", value="1002")])
        resolved, _ = conversation.resolve("what should we do?", state, catalog)
        assert "Aluva" in resolved

    def test_it_does_not_inherit_the_period(self, catalog):
        """A collection list is about the book as it stands this morning. Inheriting "last
        quarter" would list accounts whose arrears may have been cleared since."""
        state = self._anchor(period=Period(relative="last_quarter"))
        resolved, _ = conversation.resolve("what should we do?", state, catalog)
        assert "last quarter" not in resolved

    def test_it_drops_a_filter_the_account_list_cannot_honour(self, catalog):
        """Carrying `dpd_bucket` into the words would produce a worklist request the rules
        engine refuses, turning a working follow-up into an error."""
        state = self._anchor(filters=[Filter(field="dpd_bucket", op="eq", value="90+")])
        resolved, _ = conversation.resolve("what should we do?", state, catalog)
        assert "DPD" not in resolved

    @pytest.mark.parametrize(
        "question",
        [
            "what should we do about our pricing strategy?",
            "what should we do next quarter to grow the book?",
        ],
    )
    def test_a_real_strategy_question_is_left_alone(self, question, catalog):
        """Only the bare forms. A question with its own subject must reach the planner, which
        refuses strategy advice — folding it onto a collections list would answer something
        nobody asked."""
        resolved, _ = conversation.resolve(question, self._anchor(), catalog)
        assert resolved == question
