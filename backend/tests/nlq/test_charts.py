"""Chart selection and narration. Table-driven, no database.

Chart type is a deterministic function of result shape — the same question must always
render the same way. These tests are what stop that quietly becoming a judgement call.
"""

from datetime import date

import pytest

from app.services.nlq import charts
from app.services.nlq.catalog import get_catalog
from app.services.nlq.compiler import compile_spec
from app.services.nlq.contracts import Period, QuerySpec
from app.services.nlq.executor import QueryResult
from app.services.nlq.narrator import format_value

TODAY = date(2026, 7, 29)


@pytest.fixture(scope="module")
def catalog():
    return get_catalog()


def result_of(rows, columns=None):
    return QueryResult(
        rows=rows,
        columns=columns or (list(rows[0]) if rows else []),
        status="ok" if rows else "empty",
        duration_ms=5,
        sql="SELECT 1",
        row_count=len(rows),
    )


def chart_for(spec: QuerySpec, rows, catalog, prior=None):
    compiled = compile_spec(spec, catalog, TODAY)
    return charts.build(spec, compiled, result_of(rows), prior=prior, catalog=catalog)


class TestChartTypeRules:
    def test_one_metric_no_dimension_is_a_kpi(self, catalog):
        spec = QuerySpec(metrics=["loan_count"], period=Period(relative="all_time"))
        assert chart_for(spec, [{"loan_count": 13510}], catalog).chart_type == "kpi"

    def test_a_flow_over_time_is_an_area(self, catalog):
        """Filling under the curve claims the values accumulate. For a flow they do."""
        spec = QuerySpec(
            metrics=["loan_count"], dimensions=["month"], period=Period(relative="last_fy")
        )
        rows = [{"month": "2026-01-01", "loan_count": 5}, {"month": "2026-02-01", "loan_count": 8}]
        assert chart_for(spec, rows, catalog).chart_type == "area"

    def test_a_stock_over_time_stays_a_line(self, catalog):
        """PAR 30 is a percentage of a book at a moment. Area under it would imply that
        three months of PAR sum to something, and nothing sums there."""
        spec = QuerySpec(
            metrics=["par_30"], dimensions=["month"], period=Period(relative="last_fy")
        )
        rows = [{"month": "2026-01-01", "par_30": 4.1}, {"month": "2026-02-01", "par_30": 4.6}]
        assert chart_for(spec, rows, catalog).chart_type == "line"

    def test_few_categories_is_a_bar(self, catalog):
        spec = QuerySpec(
            metrics=["loan_count"], dimensions=["product"], period=Period(relative="all_time")
        )
        rows = [{"product": c, "loan_count": 1} for c in (1, 13, 16)]
        assert chart_for(spec, rows, catalog).chart_type == "bar"

    def test_many_categories_becomes_a_ranking(self, catalog):
        spec = QuerySpec(
            metrics=["sanctioned_amount"],
            dimensions=["scheme"],
            period=Period(relative="all_time"),
        )
        rows = [{"scheme": str(1300 + i), "sanctioned_amount": i} for i in range(30)]
        assert chart_for(spec, rows, catalog).chart_type == "ranking"

    def test_compare_to_per_item_is_a_dumbbell(self, catalog):
        """Before and after for each product: two dots and the gap between them."""
        spec = QuerySpec(
            metrics=["sanctioned_amount"],
            dimensions=["product"],
            period=Period(relative="last_fy"),
            compare_to=Period(relative="last_quarter"),
        )
        rows = [{"product": 16, "sanctioned_amount": 100.0}]
        prior = result_of([{"product": 16, "sanctioned_amount": 80.0}])
        chart = chart_for(spec, rows, catalog, prior=prior)
        assert chart.chart_type == "dumbbell"
        assert chart.rows[0]["delta"] == 20.0
        assert chart.rows[0]["delta_pct"] == 25.0
        # The series must address the merged columns, not the metric id, or the chart
        # renders empty.
        assert [s.field for s in chart.series] == ["previous", "current"]

    def test_compare_to_over_time_is_a_variance_bar(self, catalog):
        spec = QuerySpec(
            metrics=["sanctioned_amount"],
            dimensions=["month"],
            period=Period(relative="last_fy"),
            compare_to=Period(relative="last_quarter"),
        )
        rows = [{"month": "2026-01-01", "sanctioned_amount": 100.0}]
        prior = result_of([{"month": "2026-01-01", "sanctioned_amount": 120.0}])
        chart = chart_for(spec, rows, catalog, prior=prior)
        assert chart.chart_type == "variance"
        assert [s.field for s in chart.series] == ["delta"]
        assert chart.rows[0]["delta"] == -20.0

    def test_two_categorical_dimensions_is_a_heatmap(self, catalog):
        spec = QuerySpec(
            metrics=["loan_count"],
            dimensions=["branch", "product"],
            period=Period(relative="all_time"),
        )
        rows = [{"branch": 1, "product": 13, "loan_count": 5}]
        assert chart_for(spec, rows, catalog).chart_type == "heatmap"

    def test_share_intent_over_few_categories_is_a_donut(self, catalog):
        spec = QuerySpec(
            metrics=["sanctioned_amount"],
            dimensions=["product"],
            period=Period(relative="all_time"),
            as_share=True,
        )
        rows = [{"product": c, "sanctioned_amount": 10.0} for c in (1, 13, 16)]
        assert chart_for(spec, rows, catalog).chart_type == "donut"

    def test_the_same_rows_without_share_intent_stay_a_bar(self, catalog):
        """Part-to-whole is what the question asked for, not what the rows look like."""
        spec = QuerySpec(
            metrics=["sanctioned_amount"],
            dimensions=["product"],
            period=Period(relative="all_time"),
        )
        rows = [{"product": c, "sanctioned_amount": 10.0} for c in (1, 13, 16)]
        assert chart_for(spec, rows, catalog).chart_type == "bar"

    def test_a_ratio_is_never_a_donut(self, catalog):
        """Three collection-efficiency percentages have no total to be shares of."""
        spec = QuerySpec(
            metrics=["collection_efficiency"],
            dimensions=["product"],
            period=Period(relative="all_time"),
            as_share=True,
        )
        rows = [{"product": c, "collection_efficiency": 90.0} for c in (1, 13, 16)]
        assert chart_for(spec, rows, catalog).chart_type == "bar"

    def test_too_many_slices_is_not_a_donut(self, catalog):
        spec = QuerySpec(
            metrics=["sanctioned_amount"],
            dimensions=["scheme"],
            period=Period(relative="all_time"),
            as_share=True,
        )
        rows = [{"scheme": str(1300 + i), "sanctioned_amount": 1.0} for i in range(9)]
        assert chart_for(spec, rows, catalog).chart_type == "bar"

    def test_share_of_a_flow_over_time_is_a_stacked_area(self, catalog):
        spec = QuerySpec(
            metrics=["disbursement_total"],
            dimensions=["month", "product"],
            period=Period(relative="last_fy"),
            as_share=True,
        )
        rows = [
            {"month": "2026-01-01", "product": p, "disbursement_total": 10.0}
            for p in (1, 13, 16)
        ]
        assert chart_for(spec, rows, catalog).chart_type == "stacked_area"

    def test_share_of_a_stock_over_time_is_a_stacked_bar(self, catalog):
        """Outstanding does not accumulate between two dates, so there is no area to fill —
        but the balances at each date do sum across products."""
        spec = QuerySpec(
            metrics=["principal_outstanding"],
            dimensions=["month", "product"],
            period=Period(relative="last_fy"),
            as_share=True,
        )
        rows = [
            {"month": "2026-01-01", "product": p, "principal_outstanding": 10.0}
            for p in (1, 13, 16)
        ]
        assert chart_for(spec, rows, catalog).chart_type == "stacked_bar"

    def test_every_declared_chart_type_is_reachable(self):
        """A form the backend can never choose is dead code that looks like a feature —
        `heatmap` rendered as a spreadsheet for exactly this reason."""
        import re
        from pathlib import Path

        from app.services.nlq.contracts import ChartType

        source = Path(charts.__file__).read_text()
        # Every literal on a return line, not just the first — several rules choose with a
        # conditional expression (`return "bar" if ... else "ranking"`).
        chosen = {
            literal
            for line in source.splitlines()
            if line.lstrip().startswith("return ")
            for literal in re.findall(r'"(\w+)"', line)
        }
        declared = set(ChartType.__args__)  # type: ignore[attr-defined]
        assert declared - chosen == set(), f"unreachable chart types: {declared - chosen}"

    def test_many_series_over_time_becomes_small_multiples(self, catalog):
        """Sixteen branches on one time axis is a hairball, and stacking them answers a
        question about the total that nobody asked."""
        spec = QuerySpec(
            metrics=["disbursement_total"],
            dimensions=["month", "branch"],
            period=Period(relative="last_fy"),
        )
        rows = [
            {"month": "2026-01-01", "branch": b, "disbursement_total": 1.0} for b in range(1, 17)
        ]
        assert chart_for(spec, rows, catalog).chart_type == "small_multiples"

    def test_two_metrics_across_one_dimension_is_a_scatter(self, catalog):
        """Genuinely independent x and y — not the dual-axis trap, which needs a shared x
        to align a second y-scale against. Mixed units are legitimate here, and only here.

        Both metrics must live on one table: the registry refuses a cross-fact join
        rather than double-count, so a scatter is always within a single fact.
        """
        spec = QuerySpec(
            metrics=["avg_ticket_size", "avg_interest_rate"],
            dimensions=["branch"],
            period=Period(relative="all_time"),
        )
        rows = [
            {"branch": b, "avg_ticket_size": 1.0, "avg_interest_rate": 2.0} for b in (1, 2, 3)
        ]
        assert chart_for(spec, rows, catalog).chart_type == "scatter"

    def test_mixed_units_on_a_shared_axis_is_still_a_table(self, catalog):
        """Three metrics cannot become a scatter, and rupees beside percent cannot share
        a y-axis. A second axis is not the answer."""
        spec = QuerySpec(
            metrics=["sanctioned_amount", "avg_interest_rate", "loan_count"],
            dimensions=["branch"],
            period=Period(relative="all_time"),
        )
        rows = [
            {"branch": 1, "sanctioned_amount": 1.0, "avg_interest_rate": 2.0, "loan_count": 3}
        ]
        assert chart_for(spec, rows, catalog).chart_type == "table"


class TestDecoding:
    def test_codes_become_labels_and_keep_the_raw_value(self, catalog):
        """The label is what a human reads; the raw code is what a drill-down filters on."""
        spec = QuerySpec(
            metrics=["loan_count"], dimensions=["product"], period=Period(relative="all_time")
        )
        chart = chart_for(spec, [{"product": 1, "loan_count": 140}], catalog)
        assert chart.rows[0]["product"] == "Gold Loans"
        assert chart.rows[0]["product__raw"] == 1

    def test_time_buckets_get_fiscal_labels(self, catalog):
        spec = QuerySpec(
            metrics=["loan_count"], dimensions=["fy"], period=Period(relative="last_fy")
        )
        chart = chart_for(spec, [{"fy": "2025-04-01", "loan_count": 10}], catalog)
        assert chart.rows[0]["fy"] == "FY26"

    def test_missing_dimension_values_are_named_not_dropped(self, catalog):
        spec = QuerySpec(
            metrics=["loan_count"], dimensions=["product"], period=Period(relative="all_time")
        )
        chart = chart_for(spec, [{"product": None, "loan_count": 3}], catalog)
        assert chart.rows[0]["product"] == "Not recorded"


class TestFormatting:
    @pytest.mark.parametrize(
        "value,unit,expected",
        [
            (2752249524.087, "inr", "₹275.22 Cr"),
            (1275455.0, "inr", "₹12.75 L"),
            (4500.0, "inr", "₹4,500"),
            (97.93, "percent", "97.9%"),
            (0.0897, "percent", "0.09%"),
            (13510, "count", "13,510"),
            (None, "inr", "no data"),
        ],
    )
    def test_indian_money_conventions(self, value, unit, expected):
        """Crore and lakh, not millions — this is a report for an Indian NBFC board."""
        assert format_value(value, unit) == expected

    def test_units_come_from_the_catalog(self, catalog):
        spec = QuerySpec(metrics=["par_30"], period=Period(relative="today"))
        chart = chart_for(spec, [{"par_30": 0.09}], catalog)
        assert chart.columns[0].unit == "percent"
        assert chart.columns[0].format == "percent_1"


class TestNarration:
    def test_kpi_states_the_value_and_the_date(self, catalog):
        spec = QuerySpec(metrics=["par_30"], period=Period(relative="today"))
        chart = chart_for(spec, [{"par_30": 0.0897}], catalog)
        assert "0.09%" in chart.summary
        assert "as at" in chart.summary.lower()

    def test_unratified_metrics_are_badged_in_the_summary(self, catalog):
        spec = QuerySpec(metrics=["par_30"], period=Period(relative="today"))
        chart = chart_for(spec, [{"par_30": 0.09}], catalog)
        assert "pending client sign-off" in chart.summary
        assert "par_30" in chart.lineage.requires_signoff

    def test_empty_result_names_the_filters_that_produced_it(self, catalog):
        """"No results" alone leaves the user unable to tell a wrong filter from a genuine
        absence."""
        spec = QuerySpec(
            metrics=["disbursement_total"],
            period=Period(start=date(2024, 1, 1), end=date(2024, 6, 30)),
        )
        compiled = compile_spec(spec, catalog, TODAY)
        empty = QueryResult(rows=[], columns=[], status="empty", duration_ms=1, sql="SELECT 1")
        chart = charts.build(spec, compiled, empty, catalog=catalog)
        assert "No disbursement found" in chart.summary
        assert "2024-01-01" in chart.summary

    def test_an_all_zero_chart_says_it_is_a_real_result(self, catalog):
        spec = QuerySpec(
            metrics=["par_30"], dimensions=["branch"], period=Period(relative="today")
        )
        rows = [{"branch": 1, "par_30": 0.0}, {"branch": 4, "par_30": 0.0}]
        assert "not a failed query" in chart_for(spec, rows, catalog).summary

    def test_narrator_never_recommends(self, catalog):
        """The brief excludes AI-generated advice; the narrator states facts only."""
        spec = QuerySpec(
            metrics=["collection_efficiency"],
            dimensions=["month"],
            period=Period(relative="last_fy"),
        )
        rows = [
            {"month": "2025-04-01", "collection_efficiency": 99.0},
            {"month": "2025-05-01", "collection_efficiency": 80.0},
        ]
        summary = chart_for(spec, rows, catalog).summary.lower()
        for word in ("should", "recommend", "suggest", "consider", "advise", "must"):
            assert word not in summary

    def test_trend_reports_gaps_rather_than_hiding_them(self, catalog):
        spec = QuerySpec(
            metrics=["par_30"], dimensions=["month"], period=Period(relative="last_90_days")
        )
        rows = [
            {"month": "2026-05-01", "par_30": None},
            {"month": "2026-06-01", "par_30": 1.2},
            {"month": "2026-07-01", "par_30": 0.09},
        ]
        assert "no underlying data" in chart_for(spec, rows, catalog).summary


class TestLineage:
    def test_every_chart_carries_its_sql_and_formula(self, catalog):
        spec = QuerySpec(metrics=["par_30"], period=Period(relative="today"))
        chart = chart_for(spec, [{"par_30": 0.09}], catalog)
        assert chart.lineage.sql
        assert "par_30" in chart.lineage.formulas
        assert chart.lineage.source_tables == ["silver.asset_classification_details"]

    def test_queryspec_answers_are_not_marked_unverified(self, catalog):
        spec = QuerySpec(metrics=["loan_count"], period=Period(relative="all_time"))
        chart = chart_for(spec, [{"loan_count": 1}], catalog)
        assert chart.lineage.path == "queryspec"
        assert chart.lineage.unverified is False

    def test_coverage_warnings_reach_the_lineage_panel(self, catalog):
        spec = QuerySpec(metrics=["par_30"], period=Period(relative="today"))
        chart = chart_for(spec, [{"par_30": 0.09}], catalog)
        assert any("5,238" in w for w in chart.lineage.warnings)


class TestDrilldown:
    def test_a_time_chart_drills_into_branch(self, catalog):
        spec = QuerySpec(
            metrics=["loan_count"], dimensions=["month"], period=Period(relative="last_fy")
        )
        chart = chart_for(spec, [{"month": "2026-01-01", "loan_count": 1}], catalog)
        assert chart.drilldown is not None
        assert "branch" in chart.drilldown.dimensions

    def test_no_drilldown_is_offered_when_there_is_no_sensible_next_level(self, catalog):
        spec = QuerySpec(
            metrics=["loan_count"],
            dimensions=["branch", "product"],
            period=Period(relative="all_time"),
        )
        assert chart_for(spec, [{"branch": 1, "product": 13, "loan_count": 1}], catalog).drilldown is None
