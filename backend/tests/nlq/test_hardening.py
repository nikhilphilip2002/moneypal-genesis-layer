"""PII masking, rate limiting, caching and the fiscal calendar.

No database, no LLM. These are the modules where a subtle bug is invisible in normal use
and expensive exactly once.
"""

from datetime import date

import pytest

from app.services.nlq import cache, pii, ratelimit
from app.services.nlq.catalog import get_catalog
from app.services.nlq.contracts import ColumnSpec
from app.services.nlq.periods import (
    PeriodError,
    fy_bounds,
    fy_of,
    fy_quarter_bounds,
    fy_quarter_of,
    previous_period,
    resolve_relative,
    truncate_sql,
)

TODAY = date(2026, 7, 29)


# --------------------------------------------------------------------------------------
# Fiscal calendar
# --------------------------------------------------------------------------------------


class TestFiscalYear:
    def test_fy_boundary_is_1_april(self):
        assert fy_of(date(2026, 3, 31)) == 2026
        assert fy_of(date(2026, 4, 1)) == 2027

    def test_fy_bounds_span_april_to_march(self):
        bounds = fy_bounds(2026)
        assert (bounds.start, bounds.end) == (date(2025, 4, 1), date(2026, 3, 31))
        assert bounds.label == "FY26"

    def test_q1_is_april_to_june(self):
        q1 = fy_quarter_bounds(2027, 1)
        assert (q1.start, q1.end) == (date(2026, 4, 1), date(2026, 6, 30))

    def test_fy_quarter_of_a_july_date(self):
        assert fy_quarter_of(date(2026, 7, 29)) == (2027, 2)

    @pytest.mark.parametrize(
        "relative,expected",
        [
            ("last_fy", (date(2025, 4, 1), date(2026, 3, 31))),
            ("this_fy", (date(2026, 4, 1), date(2027, 3, 31))),
            ("fy_to_date", (date(2026, 4, 1), date(2026, 7, 29))),
            ("last_quarter", (date(2026, 4, 1), date(2026, 6, 30))),
            ("last_month", (date(2026, 6, 1), date(2026, 6, 30))),
            ("ytd", (date(2026, 1, 1), date(2026, 7, 29))),
        ],
    )
    def test_relative_periods_resolve(self, relative, expected):
        resolved = resolve_relative(relative, TODAY)
        assert (resolved.start, resolved.end) == expected

    def test_unknown_relative_period_is_an_error(self):
        with pytest.raises(PeriodError):
            resolve_relative("last_fortnight", TODAY)

    def test_whole_month_spans_shift_by_months_not_days(self):
        """A quarter must compare to the previous quarter, not to "the 91 days before" it,
        which lands mid-December and makes every QoQ comparison quietly wrong."""
        quarter = resolve_relative("last_quarter", TODAY)
        prior = previous_period(quarter)
        assert (prior.start, prior.end) == (date(2026, 1, 1), date(2026, 3, 31))

    def test_fiscal_year_compares_to_the_prior_fiscal_year(self):
        prior = previous_period(resolve_relative("last_fy", TODAY))
        assert (prior.start, prior.end) == (date(2024, 4, 1), date(2025, 3, 31))

    def test_rolling_window_compares_by_day_count(self):
        prior = previous_period(resolve_relative("last_30_days", TODAY))
        assert (prior.end - prior.start).days == 29

    def test_fiscal_truncation_shifts_by_three_months(self):
        assert "INTERVAL '3 months'" in truncate_sql("fy", "col")


# --------------------------------------------------------------------------------------
# PII
# --------------------------------------------------------------------------------------


class TestPiiMasking:
    def test_only_named_roles_see_unmasked_data(self):
        assert pii.may_see_pii("admin")
        assert pii.may_see_pii("gicc_admin")
        assert pii.may_see_pii("gicc_director")
        assert not pii.may_see_pii("gicc_policy")
        assert not pii.may_see_pii(None)
        assert not pii.may_see_pii("anonymous")

    @pytest.mark.parametrize(
        "value,expected",
        [("Rajesh Kumar", "Rajesh K***"), ("Priya", "Pr***"), ("A", "A")],
    )
    def test_names_keep_enough_to_confirm_not_to_identify(self, value, expected):
        assert pii.mask_name(value) == expected

    def test_identifiers_keep_the_last_four(self):
        assert pii.mask_identifier("123456784821") == "XXXX-XXXX-4821"

    def test_dates_of_birth_reduce_to_a_year(self):
        """Enough for cohort analysis, not enough to identify."""
        assert pii.mask_date("1985-06-12") == "1985"

    def test_rows_are_masked_for_an_unprivileged_role(self):
        catalog = get_catalog()
        columns = [
            ColumnSpec(name="indcif_first_name", label="First name", sensitivity="pii"),
            ColumnSpec(name="loan_count", label="Loans", unit="count"),
        ]
        rows = [{"indcif_first_name": "Rajesh Kumar", "loan_count": 3}]
        masked, fields = pii.mask_rows(rows, columns, role="gicc_policy", catalog=catalog)
        assert masked[0]["indcif_first_name"] == "Rajesh K***"
        assert masked[0]["loan_count"] == 3  # non-PII is untouched
        assert "indcif_first_name" in fields
        assert columns[0].masked is True

    def test_rows_are_untouched_for_a_privileged_role(self):
        columns = [ColumnSpec(name="indcif_first_name", label="First name", sensitivity="pii")]
        rows = [{"indcif_first_name": "Rajesh Kumar"}]
        masked, fields = pii.mask_rows(rows, columns, role="gicc_admin")
        assert masked[0]["indcif_first_name"] == "Rajesh Kumar"
        assert fields == []

    def test_pii_tables_are_detected_for_the_audit_flag(self):
        assert pii.touches_pii(["silver.individual_customer_master"])
        assert not pii.touches_pii(["silver.loan_account_master"])


# --------------------------------------------------------------------------------------
# Rate limiting
# --------------------------------------------------------------------------------------


class TestRateLimit:
    def setup_method(self):
        ratelimit.reset()

    def test_allows_up_to_the_limit(self):
        for _ in range(5):
            ratelimit.check_rate_limit("alice", limit=5)

    def test_rejects_past_the_limit(self):
        for _ in range(5):
            ratelimit.check_rate_limit("bob", limit=5)
        with pytest.raises(ratelimit.RateLimitExceeded) as exc:
            ratelimit.check_rate_limit("bob", limit=5)
        assert exc.value.retry_after > 0

    def test_limits_are_per_user(self):
        for _ in range(5):
            ratelimit.check_rate_limit("carol", limit=5)
        ratelimit.check_rate_limit("dave", limit=5)  # must not raise


# --------------------------------------------------------------------------------------
# Caching
# --------------------------------------------------------------------------------------


class TestCache:
    def setup_method(self):
        cache.clear_all()

    def test_result_round_trips(self):
        key = cache.result_key("SELECT 1", [1])
        assert cache.get_result(key) is None
        cache.put_result(key, "value")
        assert cache.get_result(key) == "value"

    def test_bumping_the_data_version_invalidates_results(self):
        """An ingestion must not leave yesterday's numbers answering today's question."""
        key = cache.result_key("SELECT 1", [])
        cache.put_result(key, "old")
        cache.bump_data_version("v2")
        assert cache.result_key("SELECT 1", []) != key
        assert cache.get_result(cache.result_key("SELECT 1", [])) is None

    def test_different_params_are_different_keys(self):
        assert cache.result_key("SELECT 1", [1]) != cache.result_key("SELECT 1", [2])

    @pytest.mark.parametrize(
        "a,b",
        [
            ("What is our PAR 30?", "what is our par 30"),
            ("  Disbursement by branch  ", "disbursement by branch"),
        ],
    )
    def test_question_normalisation_collapses_noise(self, a, b):
        assert cache.normalise_question(a) == cache.normalise_question(b)

    def test_word_order_is_not_normalised(self):
        """"disbursement by branch" and "branch by disbursement" are different questions;
        collapsing them would serve a wrong plan."""
        assert cache.normalise_question("disbursement by branch") != cache.normalise_question(
            "branch by disbursement"
        )

    def test_plan_cache_is_keyed_by_catalog_version(self):
        cache.put_plan("q", "v1", "plan-a")
        assert cache.get_plan("q", "v1") == "plan-a"
        assert cache.get_plan("q", "v2") is None

    def test_lru_evicts_beyond_capacity(self):
        small = cache.TTLCache(capacity=2, ttl=60)
        small.put("a", 1)
        small.put("b", 2)
        small.put("c", 3)
        assert small.get("a") is None
        assert small.get("c") == 3

    def test_entries_expire(self):
        expiring = cache.TTLCache(capacity=4, ttl=-1)  # already expired
        expiring.put("a", 1)
        assert expiring.get("a") is None
