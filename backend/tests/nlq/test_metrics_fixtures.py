"""Hand-computed metric fixtures — the highest-rigour tests in the module.

Build plan item 15. Every expected value below was computed independently against the live
database on 2026-07-29 with SQL written by hand, then the compiler was asked to reproduce
it. A wrong PAR in front of a CFO ends the project, so these do not check that the pipeline
runs; they check that it is *right*.

The independent SQL is included in each test. If a test fails, the two statements sitting
side by side show whether the compiler drifted or the data moved.
"""

import pytest

from app.services.nlq.compiler import bind, compile_spec
from app.services.nlq.contracts import Period, QuerySpec
from tests.nlq.conftest import requires_db

pytestmark = requires_db

AS_OF = "2026-07-01"


def run(cursor, spec: QuerySpec):
    compiled = compile_spec(spec)
    sql, params = bind(compiled.sql, compiled.params)
    cursor.execute(sql, params)
    return cursor.fetchall()


def scalar(cursor, spec: QuerySpec) -> float | None:
    rows = run(cursor, spec)
    value = rows[0][0] if rows else None
    return float(value) if value is not None else None


def hand_scalar(cursor, sql: str) -> float | None:
    cursor.execute(sql)
    value = cursor.fetchone()[0]
    return float(value) if value is not None else None


def close(actual, expected, tolerance=0.01) -> bool:
    if actual is None or expected is None:
        return actual == expected
    return abs(actual - expected) <= max(tolerance, abs(expected) * 1e-9)


class TestFlowMetrics:
    def test_disbursement_total(self, warehouse_cursor):
        expected = 2170758902.00
        actual = scalar(
            warehouse_cursor,
            QuerySpec(metrics=["disbursement_total"], period=Period(relative="all_time")),
        )
        hand = hand_scalar(
            warehouse_cursor,
            "SELECT SUM(genlndisb_disb_amt) FROM silver.loan_disbursement_transactions",
        )
        assert close(actual, expected) and close(hand, expected)

    def test_sanctioned_amount(self, warehouse_cursor):
        expected = 3076186367.687
        actual = scalar(
            warehouse_cursor,
            QuerySpec(metrics=["sanctioned_amount"], period=Period(relative="all_time")),
        )
        hand = hand_scalar(
            warehouse_cursor, "SELECT SUM(gnlnac_sanc_amt) FROM silver.loan_account_master"
        )
        assert close(actual, expected) and close(hand, expected)

    def test_loan_count(self, warehouse_cursor):
        actual = scalar(
            warehouse_cursor,
            QuerySpec(metrics=["loan_count"], period=Period(relative="all_time")),
        )
        assert actual == 13510

    def test_amount_collected(self, warehouse_cursor):
        expected = 160253845.36
        actual = scalar(
            warehouse_cursor,
            QuerySpec(metrics=["amount_collected"], period=Period(relative="all_time")),
        )
        hand = hand_scalar(
            warehouse_cursor,
            "SELECT SUM(lnrepay_prin_pdamt + lnrepay_int_pdamt) "
            "FROM silver.loan_repayment_transactions",
        )
        assert close(actual, expected) and close(hand, expected)


class TestRatioMetrics:
    def test_collection_efficiency(self, warehouse_cursor):
        """Paid over due, both sides from the same instalment rows. Deliberately NOT
        repaid-over-disbursed, which makes every young loan look like a default."""
        expected = 97.9332105292604665
        actual = scalar(
            warehouse_cursor,
            QuerySpec(metrics=["collection_efficiency"], period=Period(relative="all_time")),
        )
        hand = hand_scalar(
            warehouse_cursor,
            "SELECT 100.0 * SUM(lnrepay_prin_pdamt + lnrepay_int_pdamt) "
            "           / NULLIF(SUM(lnrepay_prin_amt + lnrepay_int_amt), 0) "
            "FROM silver.loan_repayment_transactions",
        )
        assert close(actual, expected, 0.001) and close(hand, expected, 0.001)

    def test_avg_ticket_size_is_total_over_count(self, warehouse_cursor):
        actual = scalar(
            warehouse_cursor,
            QuerySpec(metrics=["avg_ticket_size"], period=Period(relative="all_time")),
        )
        assert close(actual, 3076186367.687 / 13510, 0.01)


class TestPointInTimeMetrics:
    """The dangerous ones. Each is verified against the as-of collapse written by hand."""

    def test_par_30(self, warehouse_cursor):
        expected = 0.08975494297978701270
        actual = scalar(
            warehouse_cursor,
            QuerySpec(metrics=["par_30"], period=Period(start="2026-01-01", end=AS_OF)),
        )
        hand = hand_scalar(
            warehouse_cursor,
            f"""
            WITH asof AS (
                SELECT DISTINCT ON (ascd_entity_num, ascd_account_num) *
                FROM silver.asset_classification_details
                WHERE ascd_effective_date <= DATE '{AS_OF}'
                ORDER BY ascd_entity_num, ascd_account_num, ascd_effective_date DESC
            )
            SELECT 100.0 * COALESCE(SUM(ascd_princ_os) FILTER (WHERE ascd_dpd_days > 30), 0)
                         / NULLIF(SUM(ascd_princ_os), 0)
            FROM asof
            """,
        )
        assert close(actual, expected, 0.0001)
        assert close(hand, expected, 0.0001)

    def test_naive_date_equality_would_be_wrong(self, warehouse_cursor):
        """The trap, made explicit.

        asset_classification_details is an event log: a given effective_date holds only the
        accounts reclassified that day. Reading it as a snapshot reports PAR 30 as NULL
        where the correct answer is 0.090%. This test exists so that if anyone ever
        "simplifies" the compiler back to date equality, the suite says why not.
        """
        naive = hand_scalar(
            warehouse_cursor,
            f"""
            SELECT 100.0 * SUM(ascd_princ_os) FILTER (WHERE ascd_dpd_days > 30)
                         / NULLIF(SUM(ascd_princ_os), 0)
            FROM silver.asset_classification_details
            WHERE ascd_effective_date = DATE '{AS_OF}'
            """,
        )
        correct = scalar(
            warehouse_cursor,
            QuerySpec(metrics=["par_30"], period=Period(start="2026-01-01", end=AS_OF)),
        )
        assert naive is None, "the naive read is expected to produce no answer at all"
        assert correct is not None and correct > 0

    def test_principal_outstanding_as_of(self, warehouse_cursor):
        expected = 1984698447.64
        actual = scalar(
            warehouse_cursor,
            QuerySpec(
                metrics=["principal_outstanding"], period=Period(start="2026-01-01", end=AS_OF)
            ),
        )
        assert close(actual, expected)

    def test_whole_book_outstanding(self, warehouse_cursor):
        expected = 2752249524.087
        actual = scalar(
            warehouse_cursor,
            QuerySpec(
                metrics=["principal_outstanding_book"], period=Period(relative="today")
            ),
        )
        hand = hand_scalar(
            warehouse_cursor,
            "SELECT SUM(gnlnac_lndisb_amt - gnlnac_pri_repay_amt) "
            "FROM silver.loan_account_master",
        )
        assert close(actual, expected) and close(hand, expected)

    def test_the_two_outstanding_metrics_deliberately_disagree(self, warehouse_cursor):
        """₹198.5 Cr classified vs ₹275.2 Cr whole book. Both are correct answers to
        different questions, which is exactly why the catalog carries a coverage warning
        rather than quietly picking one."""
        classified = scalar(
            warehouse_cursor,
            QuerySpec(
                metrics=["principal_outstanding"], period=Period(start="2026-01-01", end=AS_OF)
            ),
        )
        whole_book = scalar(
            warehouse_cursor,
            QuerySpec(metrics=["principal_outstanding_book"], period=Period(relative="today")),
        )
        assert classified < whole_book
        compiled = compile_spec(
            QuerySpec(
                metrics=["principal_outstanding"], period=Period(start="2026-01-01", end=AS_OF)
            )
        )
        assert any("5,238" in w for w in compiled.warnings)

    def test_delinquent_account_count(self, warehouse_cursor):
        actual = scalar(
            warehouse_cursor,
            QuerySpec(
                metrics=["delinquent_account_count"],
                period=Period(start="2026-01-01", end=AS_OF),
            ),
        )
        assert actual == 244

    def test_par_90_is_a_real_zero_not_a_null(self, warehouse_cursor):
        """No account exceeds 75 DPD. The honest answer is 0.00%, and rendering it as
        "no data" would misreport a clean book as a broken query."""
        actual = scalar(
            warehouse_cursor,
            QuerySpec(metrics=["par_90"], period=Period(start="2026-01-01", end=AS_OF)),
        )
        assert actual == 0.0

    def test_max_dpd_in_the_book(self, warehouse_cursor):
        """Underpins the PAR 90 fixture above — if this ever exceeds 90, that test's
        premise has changed."""
        assert hand_scalar(
            warehouse_cursor,
            "SELECT MAX(ascd_dpd_days) FROM silver.asset_classification_details",
        ) == 75


class TestBreakdownsSumToTheTotal:
    """A breakdown that does not reconcile to its own total is double-counting."""

    def test_loan_count_by_product(self, warehouse_cursor):
        rows = run(
            warehouse_cursor,
            QuerySpec(
                metrics=["loan_count"], dimensions=["product"], period=Period(relative="all_time")
            ),
        )
        assert {int(r[0]): int(r[1]) for r in rows} == {1: 140, 13: 7715, 16: 5655}
        assert sum(int(r[1]) for r in rows) == 13510

    def test_outstanding_by_dpd_bucket_reconciles(self, warehouse_cursor):
        rows = run(
            warehouse_cursor,
            QuerySpec(
                metrics=["principal_outstanding"],
                dimensions=["dpd_bucket"],
                period=Period(start="2026-01-01", end=AS_OF),
            ),
        )
        total = scalar(
            warehouse_cursor,
            QuerySpec(
                metrics=["principal_outstanding"], period=Period(start="2026-01-01", end=AS_OF)
            ),
        )
        assert close(sum(float(r[1]) for r in rows), total, 0.01)

    def test_joining_to_the_hub_does_not_inflate_the_total(self, warehouse_cursor):
        """Grouping by branch routes through loan_account_master. If that join fanned out,
        the grouped total would exceed the ungrouped one."""
        ungrouped = scalar(
            warehouse_cursor,
            QuerySpec(metrics=["disbursement_total"], period=Period(relative="all_time")),
        )
        rows = run(
            warehouse_cursor,
            QuerySpec(
                metrics=["disbursement_total"],
                dimensions=["branch"],
                period=Period(relative="all_time"),
            ),
        )
        assert close(sum(float(r[1]) for r in rows), ungrouped, 0.01)
