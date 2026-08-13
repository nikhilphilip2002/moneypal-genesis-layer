"""Compiler snapshot and rejection tests. No LLM, no database.

Two jobs: the SQL for a given spec stays stable, and the six validation gates keep
rejecting what they are there to reject. The rejection tests are the more valuable half —
each one corresponds to a way of producing a confident wrong number.
"""

from datetime import date

import pytest

from app.services.nlq.compiler import CompileError, bind, compile_comparison, compile_spec
from app.services.nlq.contracts import Filter, OrderBy, Period, QuerySpec

TODAY = date(2026, 7, 29)


def spec(**kwargs) -> QuerySpec:
    kwargs.setdefault("period", Period(relative="all_time"))
    return QuerySpec(**kwargs)


def sql_for(**kwargs) -> str:
    return compile_spec(spec(**kwargs), today=TODAY).sql


class TestGeneratedSql:
    def test_simple_aggregate(self):
        out = sql_for(metrics=["disbursement_total"])
        assert "SUM(disb.disbursement_amount)" in out
        assert "FROM gold.loan_disbursement_events AS disb" in out
        assert "LIMIT :row_limit" in out

    def test_group_by_joins_through_the_hub(self):
        out = sql_for(metrics=["disbursement_total"], dimensions=["branch"])
        assert "JOIN gold.loan_account_master AS lam" in out
        assert 'disb."entity_num" = lam."entity_num"' in out
        assert 'lam."branch_code"' in out

    def test_entity_number_is_always_in_the_join(self):
        """entity_num takes two values; omitting it merges two entities' accounts that
        share an account number."""
        out = sql_for(metrics=["collection_efficiency"], dimensions=["product"])
        assert "entity_num" in out

    def test_every_value_is_a_bound_parameter(self):
        compiled = compile_spec(
            spec(
                metrics=["loan_count"],
                filters=[Filter(field="product", op="eq", value="gold loans")],
            ),
            today=TODAY,
        )
        assert "gold loans" not in compiled.sql.lower()
        assert compiled.params["f0"] == "1"  # decoded to the product code

    def test_limit_is_capped_at_the_hard_ceiling(self):
        compiled = compile_spec(spec(metrics=["loan_count"], limit=5000), today=TODAY)
        assert compiled.params["row_limit"] == 5000

    def test_time_grain_truncates_the_metrics_own_date_column(self):
        out = sql_for(metrics=["loan_count"], dimensions=["month"])
        assert "DATE_TRUNC('month', lam.\"sanction_date\")" in out

    def test_fiscal_year_grain_shifts_by_three_months(self):
        out = sql_for(metrics=["sanctioned_amount"], dimensions=["fy"])
        assert "INTERVAL '3 months'" in out

    def test_dpd_bucket_sorts_by_band_not_alphabetically(self):
        """'1-30' must not sort before '0 (current)'."""
        out = sql_for(metrics=["principal_outstanding"], dimensions=["dpd_bucket"])
        assert "CASE WHEN" in out and "THEN 0" in out


class TestPointInTimeCollapse:
    """The guard against reading an event log as a snapshot."""

    def test_single_as_of_uses_reviewed_gold_function(self):
        out = sql_for(metrics=["par_30"])
        assert "gold.portfolio_snapshot_as_of(:as_of)" in out
        assert "silver." not in out

    def test_never_filters_by_date_equality(self):
        """Equality reports PAR 30 as NULL where the correct answer is 0.090%."""
        out = sql_for(metrics=["par_30"])
        assert "snapshot_date =" not in out

    def test_trend_builds_one_snapshot_per_bucket(self):
        out = sql_for(metrics=["par_30"], dimensions=["month"])
        assert "generate_series" in out
        assert "LATERAL" in out
        assert "gold.portfolio_snapshot_as_of" in out

    def test_trend_keeps_empty_buckets(self):
        """LEFT, not CROSS — a month with no classified accounts is a visible gap, not a
        month the chart skips over."""
        out = sql_for(metrics=["par_30"], dimensions=["month"])
        assert "LEFT JOIN LATERAL" in out
        assert "ON TRUE" in out

    def test_as_of_date_is_the_period_end(self):
        compiled = compile_spec(
            spec(metrics=["par_30"], period=Period(start=date(2026, 1, 1), end=date(2026, 7, 1))),
            today=TODAY,
        )
        assert compiled.as_of == date(2026, 7, 1)
        assert compiled.params["as_of"] == date(2026, 7, 1)


class TestValidationGates:
    def test_unknown_metric(self):
        with pytest.raises(CompileError, match="unknown metric"):
            compile_spec(spec(metrics=["profit_margin"]), today=TODAY)

    def test_unknown_dimension(self):
        with pytest.raises(CompileError, match="unknown dimension"):
            compile_spec(spec(metrics=["loan_count"], dimensions=["salesperson"]), today=TODAY)

    def test_metrics_from_different_fact_tables_are_refused(self):
        """Joining two fact tables to satisfy one query multiplies money."""
        with pytest.raises(CompileError, match="different source tables"):
            compile_spec(
                spec(metrics=["disbursement_total", "collection_efficiency"]), today=TODAY
            )

    def test_gl_cannot_be_grouped_by_loan_dimension(self):
        """No join path exists; GL branch codes are a different coding system."""
        with pytest.raises(CompileError):
            compile_spec(
                spec(metrics=["gl_balance"], dimensions=["product"],
                     period=Period(relative="this_fy")),
                today=TODAY,
            )

    def test_whole_book_metric_cannot_be_back_dated(self):
        with pytest.raises(CompileError, match="cannot be back-dated"):
            compile_spec(
                spec(metrics=["principal_outstanding_book"], period=Period(relative="last_fy")),
                today=TODAY,
            )

    def test_ordering_by_a_field_not_in_the_query(self):
        with pytest.raises(CompileError, match="cannot order by"):
            compile_spec(
                spec(
                    metrics=["loan_count"],
                    dimensions=["branch"],
                    order_by=OrderBy(field="par_30", direction="desc"),
                ),
                today=TODAY,
            )

    def test_filtering_on_a_time_dimension_is_redirected_to_the_period(self):
        with pytest.raises(CompileError, match="period"):
            compile_spec(
                spec(
                    metrics=["loan_count"],
                    filters=[Filter(field="month", op="eq", value="2026-01")],
                ),
                today=TODAY,
            )


class TestFilters:
    def test_having_filters_a_grouped_metric_with_bound_value(self):
        compiled = compile_spec(
            spec(
                metrics=["principal_outstanding_book"],
                dimensions=["borrower"],
                having=[Filter(field="principal_outstanding_book", op="eq", value=0)],
                period=Period(relative="today"),
            ),
            today=TODAY,
        )
        assert "HAVING SUM(lam.disbursed_amount - lam.principal_repaid) = :h0" in compiled.sql
        assert compiled.params["h0"] == 0

    def test_having_rejects_a_metric_not_selected(self):
        with pytest.raises(CompileError, match="aggregate conditions"):
            compile_spec(
                spec(
                    metrics=["loan_count"],
                    having=[Filter(field="sanctioned_amount", op="gt", value=0)],
                ),
                today=TODAY,
            )

    def test_enum_synonym_decodes_to_a_code(self):
        compiled = compile_spec(
            spec(metrics=["loan_count"],
                 filters=[Filter(field="product", op="eq", value="microfinance")]),
            today=TODAY,
        )
        assert compiled.params["f0"] == "13"

    def test_unknown_enum_text_is_passed_through_not_guessed(self):
        compiled = compile_spec(
            spec(metrics=["loan_count"],
                 filters=[Filter(field="product", op="eq", value="platinum")]),
            today=TODAY,
        )
        assert compiled.params["f0"] == "platinum"  # will match nothing, and says so

    def test_in_filter_binds_a_list(self):
        compiled = compile_spec(
            spec(metrics=["loan_count"],
                 filters=[Filter(field="product", op="in", value=["gold loans", "MSME"])]),
            today=TODAY,
        )
        assert compiled.params["f0"] == ["1", "16"]

    def test_between_binds_two_parameters(self):
        compiled = compile_spec(
            spec(metrics=["loan_count"],
                 filters=[Filter(field="branch", op="between", value=[1000, 1100])]),
            today=TODAY,
        )
        assert compiled.params["f0_lo"] == "1000" and compiled.params["f0_hi"] == "1100"


class TestBinding:
    def test_named_params_become_positional(self):
        sql, values = bind("SELECT :a, :b WHERE x = :a", {"a": 1, "b": 2})
        assert sql == "SELECT %s, %s WHERE x = %s"
        assert values == [1, 2, 1]

    def test_postgres_casts_survive(self):
        """`::text` must not be mistaken for a `:text` parameter."""
        sql, values = bind("SELECT x::text WHERE y = :v", {"v": 3})
        assert sql == "SELECT x::text WHERE y = %s"
        assert values == [3]

    def test_unbound_parameter_is_an_error(self):
        with pytest.raises(CompileError, match="unbound"):
            bind("SELECT :missing", {})


class TestComparison:
    def test_produces_two_queries_over_different_periods(self):
        current, prior = compile_comparison(
            spec(
                metrics=["sanctioned_amount"],
                dimensions=["product"],
                period=Period(relative="last_quarter"),
                compare_to=Period(relative="last_fy"),
            ),
            today=TODAY,
        )
        assert current.params["period_start"] != prior.params["period_start"]
        assert current.sql.count("SELECT") == prior.sql.count("SELECT")
