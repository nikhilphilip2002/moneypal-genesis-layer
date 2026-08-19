"""The drill graph: what a question offers as its next question.

These run with no database and no model. That is the point — every step here is derived
from the catalog and the current QuerySpec, so drilling is instant and cannot go wrong.
"""

import pytest

from app.services.nlq import drilldown
from app.services.nlq.catalog import get_catalog
from app.services.nlq.contracts import Filter, Period, QuerySpec


@pytest.fixture(scope="module")
def catalog():
    return get_catalog()


def _kinds(steps):
    return [s.kind for s in steps]


def _ids(steps):
    return [s.id for s in steps]


class TestDrillGraph:
    """The graph is configuration, so its integrity is a catalog-validation concern."""

    def test_every_active_level_is_a_known_dimension(self, catalog):
        for path in catalog.drill.paths:
            for level in path.active_levels:
                assert level in catalog.dimensions, f"{path.id} names unknown level {level}"

    def test_pending_levels_are_not_dimensions_yet(self, catalog):
        """A pending level documents a rung we cannot source. If it becomes a real
        dimension, it must be promoted rather than left pending."""
        for path in catalog.drill.paths:
            for level in path.pending:
                assert level not in catalog.dimensions

    def test_region_is_declared_pending(self, catalog):
        """No branch master exists, so geography has no source. The rung is declared so it
        is one YAML edit away the day the client feed lands."""
        pending = {lvl for p in catalog.drill.paths for lvl in p.pending}
        assert "region" in pending

    def test_terminal_entity_is_a_real_dimension(self, catalog):
        assert catalog.drill.entity in catalog.dimensions

    def test_paths_do_not_share_levels(self, catalog):
        """Overlapping paths would make 'deeper' ambiguous."""
        seen: set[str] = set()
        for path in catalog.drill.paths:
            for level in path.levels:
                assert level not in seen, f"{level} appears in more than one drill path"
                seen.add(level)


class TestNextSteps:
    def test_an_undimensioned_total_offers_each_path_head(self, catalog):
        spec = QuerySpec(metrics=["disbursement_total"], period=Period(relative="last_quarter"))
        steps = drilldown.next_steps(spec, catalog)
        deeper = [s for s in steps if s.kind == "deeper"]
        assert [s.dimension for s in deeper] == ["branch", "product"]

    def test_a_branch_split_offers_the_next_level_down(self, catalog):
        spec = QuerySpec(
            metrics=["disbursement_total"],
            dimensions=["branch"],
            period=Period(relative="last_quarter"),
        )
        steps = drilldown.next_steps(spec, catalog)
        deeper = [s for s in steps if s.kind == "deeper"]
        assert [s.dimension for s in deeper] == ["agent"]

    def test_a_branch_split_offers_other_paths_sideways(self, catalog):
        spec = QuerySpec(
            metrics=["disbursement_total"],
            dimensions=["branch"],
            period=Period(relative="last_quarter"),
        )
        sideways = [s for s in drilldown.next_steps(spec, catalog) if s.kind == "sideways"]
        assert "product" in [s.dimension for s in sideways]

    def test_the_last_level_of_a_path_offers_nothing_deeper(self, catalog):
        spec = QuerySpec(
            metrics=["disbursement_total"],
            dimensions=["agent"],
            period=Period(relative="last_quarter"),
        )
        steps = drilldown.next_steps(spec, catalog)
        assert not [s for s in steps if s.kind == "deeper"]

    def test_a_deeper_step_replaces_the_categorical_split(self, catalog):
        """Stacking branch x agent produces a two-dimensional grid nobody asked for."""
        spec = QuerySpec(
            metrics=["disbursement_total"],
            dimensions=["branch"],
            period=Period(relative="last_quarter"),
        )
        step = next(s for s in drilldown.next_steps(spec, catalog) if s.kind == "deeper")
        assert step.spec.dimensions == ["agent"]

    def test_a_deeper_step_keeps_the_time_dimension(self, catalog):
        spec = QuerySpec(
            metrics=["disbursement_total"],
            dimensions=["month", "branch"],
            period=Period(relative="last_12_months"),
        )
        step = next(s for s in drilldown.next_steps(spec, catalog) if s.kind == "deeper")
        assert step.spec.dimensions == ["month", "agent"]

    def test_a_deeper_step_keeps_existing_filters(self, catalog):
        spec = QuerySpec(
            metrics=["disbursement_total"],
            dimensions=["branch"],
            filters=[Filter(field="product", op="eq", value="1")],
            period=Period(relative="last_quarter"),
        )
        step = next(s for s in drilldown.next_steps(spec, catalog) if s.kind == "deeper")
        assert step.spec.filters == spec.filters

    def test_every_answer_offers_the_accounts_behind_it(self, catalog):
        spec = QuerySpec(
            metrics=["overdue_total"],
            dimensions=["branch"],
            period=Period(relative="this_month"),
        )
        act = next(s for s in drilldown.next_steps(spec, catalog) if s.kind == "act")
        assert act.spec.dimensions == [catalog.drill.entity]
        assert act.spec.order_by is not None
        assert act.spec.order_by.field == "overdue_total"

    def test_the_account_list_is_already_at_the_entity_level(self, catalog):
        """Nothing to offer once you are looking at accounts."""
        spec = QuerySpec(
            metrics=["overdue_total"],
            dimensions=[catalog.drill.entity],
            period=Period(relative="this_month"),
        )
        assert "act" not in _kinds(drilldown.next_steps(spec, catalog))

    def test_every_answer_offers_an_explanation(self, catalog):
        spec = QuerySpec(
            metrics=["collection_efficiency"],
            dimensions=["branch"],
            period=Period(relative="this_month"),
        )
        explain = next(s for s in drilldown.next_steps(spec, catalog) if s.kind == "explain")
        assert explain.spec.explain is True
        assert explain.spec.compare_to is not None

    def test_an_explanation_is_not_offered_twice(self, catalog):
        spec = QuerySpec(
            metrics=["collection_efficiency"],
            dimensions=["branch"],
            period=Period(relative="this_month"),
            compare_to=Period(relative="last_month"),
            explain=True,
        )
        assert "explain" not in _kinds(drilldown.next_steps(spec, catalog))

    def test_an_explanation_of_a_total_picks_a_driver_dimension(self, catalog):
        """"Why did collections fall?" over an undimensioned total has to split by
        something to have any drivers at all."""
        spec = QuerySpec(
            metrics=["amount_collected"], period=Period(relative="this_month")
        )
        explain = next(s for s in drilldown.next_steps(spec, catalog) if s.kind == "explain")
        assert explain.spec.dimensions == ["branch"]

    def test_steps_are_capped(self, catalog):
        spec = QuerySpec(
            metrics=["disbursement_total"],
            dimensions=["branch"],
            period=Period(relative="last_quarter"),
        )
        assert len(drilldown.next_steps(spec, catalog, limit=3)) == 3

    def test_step_ids_are_unique(self, catalog):
        spec = QuerySpec(metrics=["disbursement_total"], period=Period(relative="last_quarter"))
        ids = _ids(drilldown.next_steps(spec, catalog))
        assert len(ids) == len(set(ids))

    def test_every_step_carries_a_standalone_question(self, catalog):
        spec = QuerySpec(
            metrics=["disbursement_total"],
            dimensions=["branch"],
            period=Period(relative="last_quarter"),
        )
        for step in drilldown.next_steps(spec, catalog):
            assert step.question.strip()
            assert step.label.strip()

    def test_a_two_dimensional_grid_offers_no_next_level(self, catalog):
        """branch x product has no single "current level", so descending from it would mean
        picking one of the two arbitrarily. Only the accounts step survives."""
        spec = QuerySpec(
            metrics=["loan_count"],
            dimensions=["branch", "product"],
            period=Period(relative="all_time"),
        )
        steps = drilldown.next_steps(spec, catalog)
        assert _kinds(steps) == ["act"]

    def test_a_gl_only_split_has_no_drill_path(self, catalog):
        """A dimension outside every path offers no deeper step rather than an arbitrary one."""
        spec = QuerySpec(
            metrics=["gl_balance"],
            dimensions=["gl_account"],
            period=Period(relative="this_fy"),
        )
        steps = drilldown.next_steps(spec, catalog)
        assert not [s for s in steps if s.kind == "deeper"]


class TestAppendLevel:
    """The bar-click target. It *adds* a level where the chip *swaps* one, because clicking
    one bar reads as "go inside this", and a control that implies narrowing must not widen."""

    def test_it_adds_rather_than_replaces(self, catalog):
        spec = QuerySpec(
            metrics=["disbursement_total"],
            dimensions=["branch"],
            period=Period(relative="last_quarter"),
        )
        assert drilldown.append_level(spec, catalog).dimensions == ["branch", "agent"]

    def test_a_time_chart_gains_the_first_split(self, catalog):
        spec = QuerySpec(
            metrics=["disbursement_total"],
            dimensions=["month"],
            period=Period(relative="last_12_months"),
        )
        assert drilldown.append_level(spec, catalog).dimensions == ["month", "branch"]

    def test_a_two_dimensional_grid_has_nothing_to_add(self, catalog):
        spec = QuerySpec(
            metrics=["loan_count"],
            dimensions=["branch", "product"],
            period=Period(relative="all_time"),
        )
        assert drilldown.append_level(spec, catalog) is None

    def test_the_last_level_of_a_path_has_nothing_to_add(self, catalog):
        spec = QuerySpec(
            metrics=["loan_count"],
            dimensions=["agent"],
            period=Period(relative="all_time"),
        )
        assert drilldown.append_level(spec, catalog) is None


class TestStepQuestions:
    """The workbench re-asks a chip in words, so the words have to carry the whole context."""

    def test_a_question_names_the_filters_and_the_period(self, catalog):
        spec = QuerySpec(
            metrics=["disbursement_total"],
            dimensions=["branch"],
            filters=[Filter(field="product", op="eq", value="1")],
            period=Period(relative="last_quarter"),
        )
        step = next(s for s in drilldown.next_steps(spec, catalog) if s.kind == "deeper")
        assert "product" in step.question
        assert "last quarter" in step.question

    def test_an_explanation_keeps_a_comparison_the_user_chose(self, catalog):
        """On a chart built as "this quarter vs last FY", explaining it against last quarter
        would answer a question that is not on screen."""
        chosen = Period(relative="last_fy")
        spec = QuerySpec(
            metrics=["disbursement_total"],
            dimensions=["branch"],
            period=Period(relative="this_quarter"),
            compare_to=chosen,
        )
        step = next(s for s in drilldown.next_steps(spec, catalog) if s.kind == "explain")
        assert step.spec.compare_to == chosen


class TestDrillIntoMember:
    """Clicking a bar filters to that member and splits by the next level down."""

    def test_it_filters_to_the_clicked_member(self, catalog):
        spec = QuerySpec(
            metrics=["disbursement_total"],
            dimensions=["branch"],
            period=Period(relative="last_quarter"),
        )
        drilled = drilldown.drill_into(spec, "branch", "3", catalog)
        assert Filter(field="branch", op="eq", value="3") in drilled.filters

    def test_it_splits_by_the_next_level_down(self, catalog):
        spec = QuerySpec(
            metrics=["disbursement_total"],
            dimensions=["branch"],
            period=Period(relative="last_quarter"),
        )
        drilled = drilldown.drill_into(spec, "branch", "3", catalog)
        assert drilled.dimensions == ["agent"]

    def test_the_last_level_drills_to_the_entity(self, catalog):
        spec = QuerySpec(
            metrics=["overdue_total"],
            dimensions=["agent"],
            period=Period(relative="this_month"),
        )
        drilled = drilldown.drill_into(spec, "agent", "A12", catalog)
        assert drilled.dimensions == [catalog.drill.entity]

    def test_it_replaces_a_previous_filter_on_the_same_field(self, catalog):
        spec = QuerySpec(
            metrics=["disbursement_total"],
            dimensions=["branch"],
            filters=[Filter(field="branch", op="eq", value="1")],
            period=Period(relative="last_quarter"),
        )
        drilled = drilldown.drill_into(spec, "branch", "3", catalog)
        branch_filters = [f for f in drilled.filters if f.field == "branch"]
        assert len(branch_filters) == 1
        assert branch_filters[0].value == "3"

    def test_an_unknown_dimension_is_refused(self, catalog):
        spec = QuerySpec(metrics=["disbursement_total"], period=Period(relative="last_quarter"))
        with pytest.raises(drilldown.DrillError):
            drilldown.drill_into(spec, "nonexistent", "3", catalog)
