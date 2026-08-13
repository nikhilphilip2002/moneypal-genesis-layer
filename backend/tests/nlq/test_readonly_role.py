"""Proof — not inspection — that the NLQ database path cannot write.

The build plan's definition of done requires this to be demonstrated by test. These skip
until `nlq_readonly` exists and NLQ_DB_PASSWORD is set; that skip is itself the Phase 0
exit gate, so a green run with everything skipped is not a pass.

Run after applying backend/scripts/sql/nlq_readonly_role.sql.
"""

import pytest

from app.core.config import settings
from app.services.nlq import db as nlq_db

pytestmark = pytest.mark.skipif(
    not settings.nlq_db_password,
    reason="nlq_readonly not provisioned — run scripts/sql/nlq_readonly_role.sql and set NLQ_DB_PASSWORD",
)


def _fails(cur, sql: str) -> str:
    """Execute `sql` expecting the server to refuse it; return the error text."""
    try:
        cur.execute(sql)
    except Exception as exc:
        return f"{type(exc).__name__}: {exc}"
    raise AssertionError(f"read-only role was permitted to run: {sql}")


class TestPrivileges:
    def test_connects_as_the_readonly_role(self):
        with nlq_db.readonly_cursor() as (_conn, cur):
            cur.execute("SELECT current_user")
            assert cur.fetchone()[0] == settings.nlq_db_user

    def test_can_read_gold_view(self):
        with nlq_db.readonly_cursor() as (_conn, cur):
            cur.execute("SELECT count(*) FROM gold.loan_account_master")
            assert cur.fetchone()[0] > 0

    def test_sees_every_gold_view(self):
        """Guards the ALTER DEFAULT PRIVILEGES FOR ROLE moneypal clause: without it, tables
        created by the next ingestion would be invisible here."""
        with nlq_db.readonly_cursor() as (_conn, cur):
            cur.execute(
                "SELECT count(*) FROM information_schema.views WHERE table_schema = 'gold'"
            )
            assert cur.fetchone()[0] == 15

    def test_can_execute_reviewed_portfolio_function(self):
        with nlq_db.readonly_cursor() as (_conn, cur):
            cur.execute("SELECT count(*) FROM gold.portfolio_snapshot_as_of(CURRENT_DATE)")
            assert cur.fetchone()[0] >= 0


class TestWritesAreRejected:
    @pytest.mark.parametrize(
        "sql",
        [
            "INSERT INTO gold.loan_account_master (loan_account_number) VALUES ('x')",
            "UPDATE gold.loan_account_master SET sanction_amount = 0",
            "DELETE FROM gold.loan_account_master",
            "CREATE TABLE gold.nlq_should_not_exist (i int)",
        ],
    )
    def test_write_is_denied(self, sql):
        with nlq_db.readonly_cursor() as (conn, cur):
            error = _fails(cur, sql)
            conn.rollback()
        assert "denied" in error.lower() or "read-only" in error.lower()

    def test_write_denied_even_in_an_explicit_read_write_transaction(self):
        """`default_transaction_read_only` is only a default — a session can turn it off.
        What must hold is the privilege set underneath it."""
        with nlq_db.readonly_cursor() as (conn, cur):
            cur.execute("SET default_transaction_read_only = off")
            error = _fails(cur, "DELETE FROM gold.loan_account_master")
            conn.rollback()
        assert "denied" in error.lower()


class TestSchemaIsolation:
    @pytest.mark.parametrize(
        "sql",
        [
            "SELECT count(*) FROM bronze.genlnacnts",
            "SELECT * FROM bronze.genlnacnts LIMIT 1",
        ],
    )
    def test_bronze_is_unreachable(self, sql):
        with nlq_db.readonly_cursor() as (conn, cur):
            error = _fails(cur, sql)
            conn.rollback()
        assert "denied" in error.lower() or "does not exist" in error.lower()

    def test_silver_is_unreachable(self):
        with nlq_db.readonly_cursor() as (conn, cur):
            error = _fails(cur, "SELECT count(*) FROM silver.loan_account_master")
            conn.rollback()
        assert "denied" in error.lower() or "does not exist" in error.lower()

    def test_cannot_read_other_roles_passwords(self):
        with nlq_db.readonly_cursor() as (conn, cur):
            error = _fails(cur, "SELECT rolpassword FROM pg_authid LIMIT 1")
            conn.rollback()
        assert "denied" in error.lower()


class TestSessionGuards:
    def test_statement_timeout_is_applied(self):
        with nlq_db.readonly_cursor() as (_conn, cur):
            cur.execute("SELECT current_setting('statement_timeout')")
            assert cur.fetchone()[0] == "15s"

    def test_search_path_excludes_bronze_and_public(self):
        with nlq_db.readonly_cursor() as (_conn, cur):
            cur.execute("SELECT current_setting('search_path')")
            assert cur.fetchone()[0] == "gold"


def test_refuses_to_fall_back_to_the_app_role(monkeypatch):
    """The dangerous failure mode is running NLQ as `moneypal` because the read-only
    credential was missing. That must raise, never degrade."""
    monkeypatch.setattr(settings, "nlq_db_password", None)
    with pytest.raises(nlq_db.ReadOnlyNotConfigured):
        nlq_db._connect_kwargs()
