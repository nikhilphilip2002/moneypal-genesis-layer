"""Multi-query analyses: build, compose, and the ranking of what is notable.

`build` and `compose` are both pure — no database, no model — which is the property that
lets "what are the five things I need to know?" be a test rather than a judgement call.
"""

from datetime import date

import pytest

from app.services.nlq import analysis
from app.services.nlq.catalog import get_catalog
from app.services.nlq.compiler import compile_spec
from app.services.nlq.contracts import ChartSpec, Filter, Lineage, Period

TODAY = date(2026, 7, 29)


@pytest.fixture(scope="module")
def catalog():
    return get_catalog()


def _chart(step, rows, chart_type="kpi"):
    """A stand-in for what the pipeline would return for one step."""
    return ChartSpec(
        chart_type=chart_type,
        title=step.label,
        rows=rows,
        lineage=Lineage(path="queryspec", sql="SELECT 1", row_count=len(rows)),
    )


def _results(spec, values: dict[str, list[dict]]):
    """Pair each step with a chart built from `values[step.id]`."""
    return [
        analysis.StepResult(step=step, chart=_chart(step, values.get(step.id, [])))
        for step in spec.steps
    ]


class TestBuild:
    def test_every_preset_builds_and_compiles(self, catalog):
        """A preset that cannot compile is a broken product surface, not a bad question."""
        for preset_id in catalog.analyses:
            spec = analysis.build(preset_id, catalog=catalog)
            for step in spec.steps:
                compile_spec(step.spec, catalog, TODAY)

    def test_it_uses_the_presets_default_period(self, catalog):
        spec = analysis.build("portfolio_health", catalog=catalog)
        assert spec.steps[0].spec.period.relative == "this_month"

    def test_a_named_period_overrides_the_default(self, catalog):
        spec = analysis.build(
            "portfolio_health", catalog=catalog, period=Period(relative="last_quarter")
        )
        assert all(s.spec.period.relative == "last_quarter" for s in spec.steps)

    def test_filters_are_applied_to_every_step(self, catalog):
        gold_loans = [Filter(field="product", op="eq", value="1")]
        spec = analysis.build("portfolio_health", catalog=catalog, filters=gold_loans)
        assert all(s.spec.filters == gold_loans for s in spec.steps)

    def test_thresholds_survive_the_build(self, catalog):
        spec = analysis.build("portfolio_health", catalog=catalog)
        par30 = next(s for s in spec.steps if s.id == "par30")
        assert par30.alert_above == 10.0

    def test_an_unknown_preset_is_refused(self, catalog):
        with pytest.raises(analysis.AnalysisError):
            analysis.build("no_such_analysis", catalog=catalog)


class TestLabelsInProse:
    """Catalog labels sit mid-sentence all over the findings, and `.lower()` mangles every
    acronym the catalog has."""

    @pytest.mark.parametrize(
        "label,expected",
        [
            ("PAR 30", "PAR 30"),
            ("NPA ratio", "NPA ratio"),
            ("DPD bucket", "DPD bucket"),
            ("Collection efficiency", "collection efficiency"),
            ("Branch", "branch"),
        ],
    )
    def test_acronyms_survive(self, label, expected):
        from app.services.nlq.narrator import humanize_label

        assert humanize_label(label) == expected

    def test_a_finding_does_not_lowercase_an_acronym(self, catalog):
        spec = analysis.build("portfolio_health", catalog=catalog)
        results = _results(spec, {"par30": [{"par_30": 14.0}]})
        result = analysis.compose(spec, results, catalog)
        assert "par 30" not in result.headline


class TestBriefing:
    """The composer behind "how is the business doing, and what should I know?"."""

    def _composed(self, catalog, values):
        spec = analysis.build("portfolio_health", catalog=catalog)
        return analysis.compose(spec, _results(spec, values), catalog)

    def test_a_breached_alert_outranks_everything_else(self, catalog):
        result = self._composed(catalog, {
            "book_size": [{"principal_outstanding": 5_00_00_000.0}],
            "par30": [{"par_30": 14.0}],          # alert_above 10
            "npa": [{"npa_ratio": 1.0}],
            "collections": [{"collection_efficiency": 99.0}],
        })
        assert result.findings[0].step_id == "par30"
        assert result.findings[0].severity == "alert"

    def test_watch_outranks_info_but_not_alert(self, catalog):
        result = self._composed(catalog, {
            "par30": [{"par_30": 7.0}],           # watch_above 5
            "npa": [{"npa_ratio": 8.0}],          # alert_above 6
            "book_size": [{"principal_outstanding": 1.0}],
        })
        severities = [f.severity for f in result.findings]
        assert severities == sorted(severities, key=lambda s: {"alert": 0, "watch": 1, "info": 2}[s])

    def test_a_below_threshold_fires_on_falling_below_it(self, catalog):
        result = self._composed(catalog, {"collections": [{"collection_efficiency": 88.0}]})
        collections = next(f for f in result.findings if f.step_id == "collections")
        assert collections.severity == "alert"

    def test_a_healthy_value_is_only_info(self, catalog):
        result = self._composed(catalog, {"collections": [{"collection_efficiency": 99.0}]})
        collections = next(f for f in result.findings if f.step_id == "collections")
        assert collections.severity == "info"

    def test_a_step_that_returned_nothing_produces_no_finding(self, catalog):
        """An empty result is not a zero. Reporting "PAR 30 is 0.0%" for a query that
        matched no rows is the most dangerous number the product could print."""
        result = self._composed(catalog, {"par30": []})
        assert not [f for f in result.findings if f.step_id == "par30"]

    def test_the_headline_counts_what_needs_attention(self, catalog):
        result = self._composed(catalog, {
            "par30": [{"par_30": 14.0}],
            "npa": [{"npa_ratio": 8.0}],
            "collections": [{"collection_efficiency": 99.0}],
        })
        assert "2" in result.headline

    def test_a_clean_briefing_says_so(self, catalog):
        result = self._composed(catalog, {
            "par30": [{"par_30": 1.0}],
            "npa": [{"npa_ratio": 1.0}],
            "collections": [{"collection_efficiency": 99.0}],
        })
        assert "nothing" in result.headline.lower() or "no " in result.headline.lower()

    def test_every_finding_carries_the_spec_that_produced_it(self, catalog):
        result = self._composed(catalog, {"par30": [{"par_30": 14.0}]})
        for finding in result.findings:
            assert finding.spec.metrics

    def test_charts_are_returned_for_every_step_that_answered(self, catalog):
        result = self._composed(catalog, {
            "par30": [{"par_30": 4.0}],
            "npa": [{"npa_ratio": 1.0}],
        })
        assert len(result.charts) == 2

    def test_a_breakdown_step_reports_its_largest_member(self, catalog):
        spec = analysis.build("collections_focus", catalog=catalog)
        results = [
            analysis.StepResult(
                step=step,
                chart=_chart(
                    step,
                    [{"dpd_bucket": "90+", "overdue_total": 900.0},
                     {"dpd_bucket": "30-59", "overdue_total": 100.0}],
                    chart_type="bar",
                ) if step.id == "by_bucket" else _chart(step, []),
            )
            for step in spec.steps
        ]
        result = analysis.compose(spec, results, catalog)
        bucket = next(f for f in result.findings if f.step_id == "by_bucket")
        assert "90+" in bucket.text


class TestConcentration:
    def test_a_single_borrower_book_is_maximally_concentrated(self, catalog):
        spec = analysis.build("concentration", catalog=catalog)
        rows = [{"borrower": "A", "principal_outstanding": 1000.0}]
        result = analysis.compose(spec, _results(spec, {"exposure": rows}), catalog)
        hhi = next(f for f in result.findings if "Herfindahl" in f.label)
        assert hhi.value == pytest.approx(1.0)
        assert hhi.severity == "alert"

    def test_an_evenly_spread_book_is_not(self, catalog):
        spec = analysis.build("concentration", catalog=catalog)
        rows = [{"borrower": str(i), "principal_outstanding": 100.0} for i in range(100)]
        result = analysis.compose(spec, _results(spec, {"exposure": rows}), catalog)
        hhi = next(f for f in result.findings if "Herfindahl" in f.label)
        assert hhi.value == pytest.approx(0.01)
        assert hhi.severity == "info"

    def test_it_reports_the_top_ten_share(self, catalog):
        spec = analysis.build("concentration", catalog=catalog)
        rows = [{"borrower": str(i), "principal_outstanding": 100.0} for i in range(20)]
        result = analysis.compose(spec, _results(spec, {"exposure": rows}), catalog)
        top10 = next(f for f in result.findings if "Top 10" in f.label)
        assert top10.value == pytest.approx(50.0)

    def test_an_empty_book_produces_no_ratio(self, catalog):
        spec = analysis.build("concentration", catalog=catalog)
        result = analysis.compose(spec, _results(spec, {"exposure": []}), catalog)
        assert not result.findings


class TestQuadrant:
    """Two steps merged on their shared dimension — the metrics live on different source
    tables, so the compiler will not (and must not) join them in SQL."""

    GROWTH = [
        {"branch": "1", "disbursement_total": 900.0},
        {"branch": "2", "disbursement_total": 900.0},
        {"branch": "3", "disbursement_total": 100.0},
        {"branch": "4", "disbursement_total": 100.0},
    ]
    QUALITY = [
        {"branch": "1", "par_30": 2.0},    # grow, clean
        {"branch": "2", "par_30": 20.0},   # grow, risky
        {"branch": "3", "par_30": 2.0},    # slow, clean
        {"branch": "4", "par_30": 20.0},   # slow, risky
    ]

    def _composed(self, catalog):
        spec = analysis.build("growth_versus_quality", catalog=catalog)
        results = _results(spec, {"growth": self.GROWTH, "quality": self.QUALITY})
        return analysis.compose(spec, results, catalog), spec

    def test_each_member_lands_in_a_quadrant(self, catalog):
        result, _ = self._composed(catalog)
        quadrants = {r["branch"]: r["quadrant"] for r in result.charts[0].rows}
        assert len(set(quadrants.values())) == 4

    def test_the_two_steps_are_merged_onto_one_chart(self, catalog):
        result, _ = self._composed(catalog)
        assert len(result.charts) == 1
        row = result.charts[0].rows[0]
        assert "disbursement_total" in row and "par_30" in row

    def test_the_merged_chart_keeps_both_queries_in_its_lineage(self, catalog):
        """A merged answer whose lineage named one of its two queries is untraceable
        exactly where tracing matters most."""
        result, _ = self._composed(catalog)
        assert result.charts[0].lineage.sql.count("SELECT") == 2

    def test_growth_is_good_and_arrears_are_bad(self, catalog):
        result, _ = self._composed(catalog)
        by_branch = {r["branch"]: r["quadrant"] for r in result.charts[0].rows}
        assert by_branch["1"] == "Growing, clean"
        assert by_branch["2"] == "Growing, risky"
        assert by_branch["4"] == "Slow, risky"

    def test_it_names_the_best_and_the_worst(self, catalog):
        result, _ = self._composed(catalog)
        assert "1" in result.findings[0].text
        attention = next(f for f in result.findings if f.label == "Needs attention")
        assert "4" in attention.text
        assert attention.severity == "watch"

    def test_it_cuts_at_the_median_not_at_zero(self, catalog):
        result, _ = self._composed(catalog)
        assert any("median" in w.lower() for w in result.warnings)

    def test_a_member_missing_from_one_step_is_dropped(self, catalog):
        """A branch with disbursement but no snapshot row cannot be placed on two axes, and
        plotting it at zero arrears would invent the most flattering possible position."""
        spec = analysis.build("growth_versus_quality", catalog=catalog)
        results = _results(spec, {
            "growth": [*self.GROWTH, {"branch": "9", "disbursement_total": 50.0}],
            "quality": self.QUALITY,
        })
        result = analysis.compose(spec, results, catalog)
        assert "9" not in {r["branch"] for r in result.charts[0].rows}

    def test_too_few_members_to_split_produces_no_quadrants(self, catalog):
        spec = analysis.build("growth_versus_quality", catalog=catalog)
        results = _results(spec, {
            "growth": [{"branch": "1", "disbursement_total": 1.0}],
            "quality": [{"branch": "1", "par_30": 1.0}],
        })
        result = analysis.compose(spec, results, catalog)
        assert not result.findings


class TestFindingsCarryTheirOwnQuestion:
    """The workbench re-asks a chip in words — it routes every turn through the planner so
    the turn lands in history with its sources. A chip carrying only "PAR 30" is re-planned
    with no period and no filters, quietly answering about the whole book."""

    def test_a_finding_names_its_period(self, catalog):
        spec = analysis.build(
            "portfolio_health", catalog=catalog, period=Period(relative="last_quarter")
        )
        result = analysis.compose(spec, _results(spec, {"par30": [{"par_30": 14.0}]}), catalog)
        assert "last quarter" in result.findings[0].question

    def test_a_finding_carries_the_filter_the_card_was_built_with(self, catalog):
        spec = analysis.build(
            "portfolio_health",
            catalog=catalog,
            filters=[Filter(field="product", op="eq", value="1")],
        )
        result = analysis.compose(spec, _results(spec, {"par30": [{"par_30": 14.0}]}), catalog)
        assert "product" in result.findings[0].question

    def test_every_composer_populates_it(self, catalog):
        cases = {
            "concentration": {"exposure": [
                {"borrower": str(i), "principal_outstanding": 100.0} for i in range(20)
            ]},
            "growth_versus_quality": {
                "growth": TestQuadrant.GROWTH, "quality": TestQuadrant.QUALITY
            },
            "portfolio_health": {"par30": [{"par_30": 14.0}]},
        }
        for preset, values in cases.items():
            spec = analysis.build(preset, catalog=catalog)
            result = analysis.compose(spec, _results(spec, values), catalog)
            assert result.findings, preset
            for finding in result.findings:
                assert finding.question.strip(), f"{preset}/{finding.label}"


class TestAFailedStepNeverBecomesAPosition:
    """A quadrant places each member on two axes. One axis missing is not "zero on that
    axis" — and zero arrears is the most flattering position on the grid, so a failed query
    would read back as a spotless book."""

    def _one_step_failed(self, catalog):
        spec = analysis.build("growth_versus_quality", catalog=catalog)
        results = [
            analysis.StepResult(
                step=step,
                chart=_chart(step, TestQuadrant.GROWTH) if step.id == "growth" else None,
                error="" if step.id == "growth" else "connection timed out",
            )
            for step in spec.steps
        ]
        return analysis.compose(spec, results, catalog), spec

    def test_no_quadrants_are_produced(self, catalog):
        result, _ = self._one_step_failed(catalog)
        assert not any(r.get("quadrant") for chart in result.charts for r in chart.rows)

    def test_it_says_which_half_is_missing(self, catalog):
        result, _ = self._one_step_failed(catalog)
        assert result.warnings
        assert "could not" in result.headline.lower() or any(
            "could not" in w.lower() for w in result.warnings
        )

    def test_it_names_no_best_or_worst_branch(self, catalog):
        result, _ = self._one_step_failed(catalog)
        assert not result.findings


class TestStepConcurrencyIsBudgetedProcessWide:
    def test_the_slot_count_leaves_a_connection_for_an_ordinary_question(self):
        """Per-analysis caps only hold while one analysis runs. Two briefings opened together
        asked for eight connections from a pool of five, and the surplus steps failed on the
        acquire timeout — reported to the reader as "could not be answered" rather than load."""
        from app.services.nlq.db import POOL_SIZE

        assert analysis.MAX_WORKERS < POOL_SIZE
        assert analysis._STEP_SLOTS._value == analysis.MAX_WORKERS
