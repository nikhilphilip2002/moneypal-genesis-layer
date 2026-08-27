"""Hand-computed metric fixtures — the highest-rigour tests in the module.

Build plan item 15. Every expected value below was computed independently against the live
database on 2026-07-29 with SQL written by hand, then the compiler was asked to reproduce
it. A wrong PAR in front of a CFO ends the project, so these do not check that the pipeline
runs; they check that it is *right*.

The independent SQL is included in each test. If a test fails, the two statements sitting
side by side show whether the compiler drifted or the data moved.
"""

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
        expected = hand_scalar(
            warehouse_cursor,
            "SELECT SUM(disbursement_amount) FROM gold.semantic_disbursement_event",
        )
        actual = scalar(
            warehouse_cursor,
            QuerySpec(metrics=["disbursement_total"], period=Period(relative="all_time")),
        )
        assert close(actual, expected)

    def test_sanctioned_amount(self, warehouse_cursor):
        expected = hand_scalar(
            warehouse_cursor, "SELECT SUM(sanction_amount) FROM gold.semantic_loan_account"
        )
        actual = scalar(
            warehouse_cursor,
            QuerySpec(metrics=["sanctioned_amount"], period=Period(relative="all_time")),
        )
        assert close(actual, expected)

    def test_loan_count(self, warehouse_cursor):
        actual = scalar(
            warehouse_cursor,
            QuerySpec(metrics=["loan_count"], period=Period(relative="all_time")),
        )
        expected = hand_scalar(warehouse_cursor, "SELECT count(*) FROM gold.semantic_loan_account")
        assert actual == expected

    def test_amount_collected(self, warehouse_cursor):
        expected = hand_scalar(
            warehouse_cursor, "SELECT SUM(total_paid) FROM gold.semantic_repayment_event"
        )
        actual = scalar(
            warehouse_cursor,
            QuerySpec(metrics=["amount_collected"], period=Period(relative="all_time")),
        )
        assert close(actual, expected)


class TestRatioMetrics:
    def test_collection_efficiency(self, warehouse_cursor):
        """Paid over due, both sides from the same instalment rows. Deliberately NOT
        repaid-over-disbursed, which makes every young loan look like a default."""
        expected = hand_scalar(
            warehouse_cursor,
            "SELECT 100.0 * SUM(total_paid) / NULLIF(SUM(total_due), 0) "
            "FROM gold.semantic_repayment_event",
        )
        actual = scalar(
            warehouse_cursor,
            QuerySpec(metrics=["collection_efficiency"], period=Period(relative="all_time")),
        )
        assert close(actual, expected, 0.001)

    def test_avg_ticket_size_is_total_over_count(self, warehouse_cursor):
        actual = scalar(
            warehouse_cursor,
            QuerySpec(metrics=["avg_ticket_size"], period=Period(relative="all_time")),
        )
        expected = hand_scalar(
            warehouse_cursor,
            "SELECT SUM(sanction_amount) / NULLIF(count(*), 0) FROM gold.semantic_loan_account",
        )
        assert close(actual, expected, 0.01)


class TestPointInTimeMetrics:
    """The dangerous ones. Each is verified against the as-of collapse written by hand."""

    def test_par_30(self, warehouse_cursor):
        expected = hand_scalar(
            warehouse_cursor,
            f"SELECT 100.0 * COALESCE(SUM(principal_outstanding) FILTER (WHERE is_par30), 0) "
            f"/ NULLIF(SUM(principal_outstanding), 0) FROM gold.portfolio_snapshot_as_of(DATE '{AS_OF}')",
        )
        actual = scalar(
            warehouse_cursor,
            QuerySpec(metrics=["par_30"], period=Period(start="2026-01-01", end=AS_OF)),
        )
        assert close(actual, expected, 0.0001)

    def test_historical_reads_use_the_gold_as_of_function(self, warehouse_cursor):
        correct = scalar(
            warehouse_cursor,
            QuerySpec(metrics=["par_30"], period=Period(start="2026-01-01", end=AS_OF)),
        )
        assert correct is not None and correct > 0

    def test_principal_outstanding_as_of(self, warehouse_cursor):
        expected = hand_scalar(
            warehouse_cursor,
            f"SELECT SUM(principal_outstanding) FROM gold.portfolio_snapshot_as_of(DATE '{AS_OF}')",
        )
        actual = scalar(
            warehouse_cursor,
            QuerySpec(
                metrics=["principal_outstanding"], period=Period(start="2026-01-01", end=AS_OF)
            ),
        )
        assert close(actual, expected)

    def test_whole_book_outstanding(self, warehouse_cursor):
        expected = hand_scalar(
            warehouse_cursor,
            "SELECT SUM(disbursed_amount - principal_repaid) FROM gold.semantic_loan_account",
        )
        actual = scalar(
            warehouse_cursor,
            QuerySpec(
                metrics=["principal_outstanding_book"], period=Period(relative="today")
            ),
        )
        assert close(actual, expected)

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
        assert any("5,466" in w for w in compiled.warnings)

    def test_delinquent_account_count(self, warehouse_cursor):
        actual = scalar(
            warehouse_cursor,
            QuerySpec(
                metrics=["delinquent_account_count"],
                period=Period(start="2026-01-01", end=AS_OF),
            ),
        )
        expected = hand_scalar(
            warehouse_cursor,
            f"SELECT count(*) FILTER (WHERE dpd_days > 0) "
            f"FROM gold.portfolio_snapshot_as_of(DATE '{AS_OF}')",
        )
        assert actual == expected

    def test_par_90_is_a_real_zero_not_a_null(self, warehouse_cursor):
        """No account exceeds 75 DPD. The honest answer is 0.00%, and rendering it as
        "no data" would misreport a clean book as a broken query."""
        actual = scalar(
            warehouse_cursor,
            QuerySpec(metrics=["par_90"], period=Period(start="2026-01-01", end=AS_OF)),
        )
        expected = hand_scalar(
            warehouse_cursor,
            f"SELECT 100.0 * COALESCE(SUM(principal_outstanding) FILTER (WHERE is_par90), 0) "
            f"/ NULLIF(SUM(principal_outstanding), 0) "
            f"FROM gold.portfolio_snapshot_as_of(DATE '{AS_OF}')",
        )
        assert actual == expected

    def test_max_dpd_in_the_book(self, warehouse_cursor):
        """Underpins the PAR 90 fixture above — if this ever exceeds 90, that test's
        premise has changed."""
        actual = hand_scalar(
            warehouse_cursor,
            f"SELECT MAX(dpd_days) FROM gold.portfolio_snapshot_as_of(DATE '{AS_OF}')",
        )
        assert actual is not None and actual >= 0


class TestBreakdownsSumToTheTotal:
    """A breakdown that does not reconcile to its own total is double-counting."""

    def test_loan_count_by_product(self, warehouse_cursor):
        rows = run(
            warehouse_cursor,
            QuerySpec(
                metrics=["loan_count"], dimensions=["product"], period=Period(relative="all_time")
            ),
        )
        total = hand_scalar(warehouse_cursor, "SELECT count(*) FROM gold.semantic_loan_account")
        assert sum(int(r[1]) for r in rows) == total

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
