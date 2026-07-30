"""Contract tests for the NLQ type layer.

These run with no database and no LLM. They exist because every other module in the
pipeline compiles against these types — a loosened validator here silently widens what the
planner is allowed to emit.
"""

from datetime import date

import pytest
from pydantic import BaseModel, ValidationError

from app.services.nlq.contracts import (
    ChartSpec,
    ClarifyPlan,
    Filter,
    Lineage,
    Period,
    PlanResult,
    QuerySpec,
    QuerySpecPlan,
    RefusalPlan,
    SqlPlan,
)


class _PlanEnvelope(BaseModel):
    plan: PlanResult


def _spec(**overrides) -> QuerySpec:
    base = dict(
        metrics=["disbursement_total"],
        dimensions=["branch"],
        period=Period(grain="month", relative="last_quarter"),
    )
    base.update(overrides)
    return QuerySpec(**base)


class TestFilter:
    @pytest.mark.parametrize(
        "kwargs",
        [
            dict(field="product", op="in", value="16"),          # scalar for a list op
            dict(field="product", op="in", value=[]),            # empty list
            dict(field="amount", op="between", value=[1]),       # wrong arity
            dict(field="amount", op="between", value=[1, 2, 3]),
            dict(field="branch", op="eq", value=None),           # missing value
            dict(field="branch", op="eq", value=["3", "4"]),     # list for a scalar op
        ],
    )
    def test_rejects_malformed_filters(self, kwargs):
        with pytest.raises(ValidationError):
            Filter(**kwargs)

    def test_is_null_needs_no_value(self):
        assert Filter(field="closure_date", op="is_null").value is None

    def test_unknown_operator_is_rejected(self):
        with pytest.raises(ValidationError):
            Filter(field="branch", op="regex", value=".*")


class TestPeriod:
    def test_requires_bounds(self):
        with pytest.raises(ValidationError):
            Period(grain="month")

    def test_rejects_inverted_range(self):
        with pytest.raises(ValidationError):
            Period(grain="day", start=date(2026, 3, 1), end=date(2026, 1, 1))

    def test_is_resolved_only_with_concrete_dates(self):
        assert not Period(relative="last_quarter").is_resolved
        assert Period(start=date(2026, 1, 1), end=date(2026, 3, 31)).is_resolved

    def test_relative_vocabulary_is_closed(self):
        """An open string would let the planner invent periods the compiler cannot honour."""
        with pytest.raises(ValidationError):
            Period(relative="last_fortnight")


class TestQuerySpec:
    def test_requires_at_least_one_metric(self):
        with pytest.raises(ValidationError):
            _spec(metrics=[])

    def test_rejects_duplicate_metrics_and_dimensions(self):
        with pytest.raises(ValidationError):
            _spec(metrics=["disbursement_total", "disbursement_total"])
        with pytest.raises(ValidationError):
            _spec(dimensions=["branch", "branch"])

    def test_limit_is_capped_at_5000(self):
        with pytest.raises(ValidationError):
            _spec(limit=5001)
        with pytest.raises(ValidationError):
            _spec(limit=0)

    def test_unknown_field_is_rejected(self):
        """extra="forbid" — a hallucinated key must fail loudly, not be dropped."""
        with pytest.raises(ValidationError):
            QuerySpec(
                metrics=["par_30"],
                period=Period(relative="ytd"),
                having="sum > 100",
            )

    def test_cache_key_is_stable_and_order_independent(self):
        a = _spec(metrics=["disbursement_total"], dimensions=["branch"])
        b = _spec(metrics=["disbursement_total"], dimensions=["branch"])
        assert a.cache_key() == b.cache_key()

    def test_cache_key_changes_with_meaning(self):
        assert _spec(limit=50).cache_key() != _spec(limit=51).cache_key()
        assert _spec(dimensions=["branch"]).cache_key() != _spec(dimensions=["product"]).cache_key()

    def test_round_trips_through_json(self):
        original = _spec(
            filters=[Filter(field="product", op="in", value=[1, 16])],
            compare_to=Period(grain="month", relative="last_fy"),
        )
        assert QuerySpec.model_validate(original.model_dump(mode="json")) == original


class TestPlanUnion:
    """The planner emits a tagged union under constrained decoding; the tag must route."""

    @pytest.mark.parametrize(
        "payload,expected",
        [
            (
                {"route": "queryspec", "spec": None, "confidence": 0.9},
                QuerySpecPlan,
            ),
            ({"route": "sql", "intent": "gl detail", "confidence": 0.5}, SqlPlan),
            ({"route": "clarify", "question": "FY or calendar year?"}, ClarifyPlan),
            ({"route": "refuse", "reason": "predictive"}, RefusalPlan),
        ],
    )
    def test_discriminates_on_route(self, payload, expected):
        if payload.get("spec", "missing") is None:
            payload["spec"] = _spec().model_dump(mode="json")
        assert isinstance(_PlanEnvelope.model_validate({"plan": payload}).plan, expected)

    def test_unknown_route_is_rejected(self):
        with pytest.raises(ValidationError):
            _PlanEnvelope.model_validate({"plan": {"route": "execute_sql", "sql": "SELECT 1"}})

    def test_refusal_reason_is_a_closed_set(self):
        with pytest.raises(ValidationError):
            RefusalPlan(reason="dont_feel_like_it")

    def test_confidence_is_bounded(self):
        with pytest.raises(ValidationError):
            SqlPlan(intent="x", confidence=1.4)


class TestChartSpec:
    def test_lineage_is_mandatory(self):
        with pytest.raises(ValidationError):
            ChartSpec(chart_type="kpi", title="Disbursement")

    def test_text_to_sql_answers_are_marked_unverified(self):
        chart = ChartSpec(
            chart_type="kpi",
            title="Disbursement",
            lineage=Lineage(path="text_to_sql", sql="SELECT 1", unverified=True),
        )
        assert chart.lineage.unverified is True
        assert chart.rows == []

    def test_unknown_chart_type_is_rejected(self):
        with pytest.raises(ValidationError):
            ChartSpec(
                chart_type="pie",  # deliberately not in the vocabulary
                title="Share",
                lineage=Lineage(path="queryspec", sql="SELECT 1"),
            )
