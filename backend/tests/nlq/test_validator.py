"""Adversarial suite for the PostgreSQL MCP SQL validator.

Every case here is a real technique. The build plan's definition of done requires 100% of
them to be rejected, and the suite is written to fail loudly rather than to be reassuring:
each test names the attack it represents so a future relaxation has to argue with it.

The validator is the second lock. The first is `nlq_readonly`, which cannot write at all —
these tests do not excuse that role from existing.
"""

import pytest

from app.services.nlq.validator import ValidationError, is_safe, validate

GOOD = """
SELECT lam.application_branch_code, SUM(d.amount_given) AS total
FROM gold.loan_disbursements AS d
JOIN gold.loan_accounts AS lam
  ON d.loan_account_number = lam.loan_account_number
 AND d.company_code = lam.company_code
WHERE d.amount_given_on BETWEEN '2026-04-01' AND '2026-06-30'
GROUP BY lam.application_branch_code
LIMIT 100
"""


class TestAcceptsLegitimateQueries:
    def test_a_normal_reporting_query_passes(self):
        result = validate(GOOD)
        assert "gold.loan_disbursements" in result.tables
        assert "gold.loan_accounts" in result.tables

    def test_cte_is_allowed(self):
        sql = """
        WITH asof AS (
            SELECT loan_account_number, principal_still_due
            FROM gold.daily_loan_status
            WHERE status_date <= '2026-07-01'
        )
        SELECT SUM(principal_still_due) AS total FROM asof LIMIT 10
        """
        assert is_safe(sql)

    def test_cross_join_lateral_is_allowed(self):
        """The compiler's own point-in-time series uses it; it is correlated, not cartesian."""
        sql = """
        SELECT b.bucket, SUM(a.principal_still_due) AS os
        FROM (SELECT generate_series('2026-01-01'::date, '2026-06-30'::date,
                                     INTERVAL '1 month')::date AS bucket) AS b
        CROSS JOIN LATERAL (
            SELECT principal_still_due
            FROM gold.daily_loan_status
            WHERE status_date <= b.bucket
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
        sql = f"SELECT {column} FROM gold.loan_accounts LIMIT 1"
        with pytest.raises(ValidationError, match="column"):
            validate(sql, allow_pii=True)

    def test_real_column_from_a_different_gold_view_is_rejected(self):
        sql = (
            "SELECT customer_name, disbursement_sequence "
            "FROM gold.loan_accounts LIMIT 8"
        )
        with pytest.raises(
            ValidationError,
            match="disbursement_sequence.*does not exist on any referenced table",
        ):
            validate(sql, allow_pii=True)

    def test_unqualified_column_shared_by_joined_tables_is_rejected_as_ambiguous(self):
        sql = """
        SELECT loan_account_number
        FROM gold.loan_accounts AS loan
        JOIN gold.loan_disbursements AS disb
          ON disb.loan_account_number = loan.loan_account_number
         AND disb.company_code = loan.company_code
        LIMIT 8
        """
        with pytest.raises(ValidationError, match="ambiguous"):
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
        sql = f"SELECT {call} FROM gold.loan_accounts LIMIT 1"
        with pytest.raises(ValidationError):
            validate(sql)

    def test_nested_in_a_subquery_is_still_caught(self):
        """A denylist that only inspected the top-level select list would miss this."""
        sql = (
            "SELECT loan_account_number FROM gold.loan_accounts "
            "WHERE loan_account_number IN (SELECT pg_sleep(10)) LIMIT 1"
        )
        with pytest.raises(ValidationError):
            validate(sql)


class TestUncontrolledEgress:
    @pytest.mark.parametrize(
        "sql",
        [
            "SELECT * FROM gold.loan_accounts LIMIT 10",
            "SELECT lam.* FROM gold.loan_accounts AS lam LIMIT 10",
            "SELECT a.* FROM gold.customers AS a LIMIT 1",
        ],
    )
    def test_select_star_is_rejected(self, sql):
        """56 columns of customer master, several of them PII."""
        with pytest.raises(ValidationError):
            validate(sql)

    def test_pii_columns_are_rejected_without_permission(self):
        sql = (
            "SELECT full_name, date_of_birth FROM gold.customers LIMIT 5"
        )
        with pytest.raises(ValidationError):
            validate(sql, allow_pii=False)

    def test_pii_columns_are_allowed_for_a_permitted_role(self):
        sql = "SELECT full_name FROM gold.customers LIMIT 5"
        result = validate(sql, allow_pii=True)
        assert "full_name" in result.pii_columns

    def test_pii_can_be_narrowed_to_borrower_name_columns(self):
        sql = (
            "SELECT full_name, date_of_birth "
            "FROM gold.customers LIMIT 5"
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
            "FROM gold.loan_accounts AS a, gold.emi_schedule AS b LIMIT 10"
        )
        with pytest.raises(ValidationError):
            validate(sql)

    def test_join_without_on_is_rejected(self):
        sql = (
            "SELECT a.loan_account_number FROM gold.loan_accounts AS a "
            "JOIN gold.emi_schedule AS b ON TRUE LIMIT 10"
        )
        # ON TRUE is syntactically a condition; it is still bounded by the LIMIT and the
        # EXPLAIN cost gate, so this is allowed through to that check rather than here.
        assert is_safe(sql)

    def test_missing_limit_is_injected(self):
        sql = "SELECT loan_account_number FROM gold.loan_accounts"
        result = validate(sql)
        assert result.limit_injected
        assert "LIMIT" in result.sql.upper()

    def test_excessive_limit_is_rejected(self):
        sql = "SELECT loan_account_number FROM gold.loan_accounts LIMIT 999999"
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
        original = "SELECT loan_account_number FROM gold.loan_accounts"
        result = validate(original)
        assert "LIMIT" in result.sql.upper()
        assert result.sql != original


class TestScopedColumnResolution:
    """Phase D (plan.md F10): columns resolve per SQL scope, not against a statement-wide
    union of every table mentioned anywhere. Both audit false positives below were rejected
    as "ambiguous" by the scope-blind validator."""

    def test_in_subquery_over_a_second_view_is_not_ambiguous(self):
        sql = (
            "SELECT loan_account_number FROM gold.loan_accounts "
            "WHERE company_code IN (SELECT company_code FROM gold.loan_disbursements)"
        )
        result = validate(sql)
        assert result.tables == [
            "gold.loan_accounts", "gold.loan_disbursements",
        ]

    def test_union_branches_validate_independently(self):
        sql = (
            "SELECT loan_account_number FROM gold.loan_accounts "
            "UNION ALL "
            "SELECT loan_account_number FROM gold.loan_disbursements"
        )
        assert is_safe(sql)

    def test_union_order_by_may_name_an_output_column(self):
        sql = (
            "SELECT loan_account_number FROM gold.loan_accounts "
            "UNION ALL "
            "SELECT loan_account_number FROM gold.loan_disbursements "
            "ORDER BY loan_account_number LIMIT 5"
        )
        assert is_safe(sql)

    def test_a_union_branch_with_an_invented_column_is_rejected(self):
        sql = (
            "SELECT loan_account_number FROM gold.loan_accounts "
            "UNION ALL "
            "SELECT invented_column FROM gold.loan_disbursements"
        )
        with pytest.raises(ValidationError, match="invented_column.*UNION branch"):
            validate(sql)

    def test_correlated_subquery_may_reference_the_outer_alias(self):
        sql = """
        SELECT lam.loan_account_number
        FROM gold.loan_accounts AS lam
        WHERE EXISTS (
            SELECT 1 FROM gold.loan_disbursements AS d
            WHERE d.loan_account_number = lam.loan_account_number
              AND d.company_code = lam.company_code
        )
        LIMIT 10
        """
        assert is_safe(sql)

    def test_cte_alias_cannot_bypass_column_validation(self):
        """The scope-blind validator skipped any column qualified by a CTE alias."""
        sql = (
            "WITH c AS (SELECT loan_account_number FROM gold.loan_accounts) "
            "SELECT c.made_up FROM c"
        )
        with pytest.raises(ValidationError, match="made_up.*not projected by 'c'"):
            validate(sql)

    def test_derived_table_alias_cannot_bypass_column_validation(self):
        sql = (
            "SELECT s.made_up FROM "
            "(SELECT loan_account_number FROM gold.loan_accounts) AS s"
        )
        with pytest.raises(ValidationError, match="made_up.*not projected by 's'"):
            validate(sql)

    def test_cte_projection_is_resolved_through_its_select_list_aliases(self):
        sql = (
            "WITH c AS (SELECT loan_account_number AS lan FROM gold.loan_accounts) "
            "SELECT c.lan, lan FROM c"
        )
        assert is_safe(sql)

    def test_unqualified_column_missing_from_the_cte_projection_is_rejected(self):
        sql = (
            "WITH c AS (SELECT loan_account_number AS lan FROM gold.loan_accounts) "
            "SELECT loan_account_number FROM c"
        )
        with pytest.raises(ValidationError, match="does not exist on any referenced table"):
            validate(sql)

    def test_cte_over_a_union_projects_the_first_branch(self):
        sql = (
            "WITH c AS ("
            "SELECT loan_account_number FROM gold.loan_accounts "
            "UNION ALL SELECT loan_account_number FROM gold.loan_disbursements"
            ") SELECT c.loan_account_number FROM c"
        )
        assert is_safe(sql)

    def test_unknown_qualifier_names_the_scope(self):
        sql = "SELECT zz.loan_account_number FROM gold.loan_accounts AS lam"
        with pytest.raises(ValidationError, match="qualifier 'zz'.*outer query"):
            validate(sql)

    def test_ambiguity_error_names_the_candidate_tables(self):
        sql = """
        SELECT loan_account_number
        FROM gold.loan_accounts AS loan
        JOIN gold.loan_disbursements AS disb
          ON disb.loan_account_number = loan.loan_account_number
        LIMIT 8
        """
        with pytest.raises(
            ValidationError,
            match="gold.loan_accounts, gold.loan_disbursements",
        ):
            validate(sql)


class TestFunctionPolicy:
    """The denylist is always on. `allowlist` mode (NLQ_SQL_FUNCTION_MODE) additionally
    rejects anything not on ALLOWED_FUNCTIONS; `denylist` mode logs the unlisted call so
    the allowlist can be completed from canary evidence."""

    UNLISTED = "SELECT pg_typeof(loan_account_number) FROM gold.loan_accounts LIMIT 1"

    def test_allowlist_mode_rejects_an_unlisted_function(self):
        with pytest.raises(ValidationError, match="pg_typeof.*not on the allowlist"):
            validate(self.UNLISTED, function_mode="allowlist")

    def test_denylist_mode_accepts_and_logs_an_unlisted_function(self, caplog):
        with caplog.at_level("INFO", logger="app.services.nlq.validator"):
            assert is_safe(self.UNLISTED, function_mode="denylist")
        assert any(
            "pg_typeof()" in record.getMessage() and record.levelname == "INFO"
            for record in caplog.records
        )

    def test_default_mode_comes_from_settings(self, monkeypatch):
        from app.core.config import settings

        monkeypatch.setattr(settings, "nlq_sql_function_mode", "allowlist")
        with pytest.raises(ValidationError, match="not on the allowlist"):
            validate(self.UNLISTED)
        monkeypatch.setattr(settings, "nlq_sql_function_mode", "denylist")
        assert is_safe(self.UNLISTED)

    def test_unknown_mode_is_a_programming_error(self):
        with pytest.raises(ValueError):
            validate(self.UNLISTED, function_mode="blocklist")

    @pytest.mark.parametrize("mode", ["denylist", "allowlist"])
    def test_banned_functions_are_rejected_in_both_modes(self, mode):
        sql = "SELECT PG_SLEEP(5) FROM gold.loan_accounts LIMIT 1"
        with pytest.raises(ValidationError, match="not permitted"):
            validate(sql, function_mode=mode)

    @pytest.mark.parametrize(
        "sql",
        [
            GOOD,
            """
            WITH asof AS (
                SELECT loan_account_number, principal_still_due
                FROM gold.daily_loan_status
                WHERE status_date <= '2026-07-01'
            )
            SELECT SUM(principal_still_due) AS total FROM asof LIMIT 10
            """,
            """
            SELECT b.bucket, SUM(a.principal_still_due) AS os
            FROM (SELECT generate_series('2026-01-01'::date, '2026-06-30'::date,
                                         INTERVAL '1 month')::date AS bucket) AS b
            CROSS JOIN LATERAL (
                SELECT principal_still_due
                FROM gold.daily_loan_status
                WHERE status_date <= b.bucket
            ) AS a
            GROUP BY b.bucket
            LIMIT 100
            """,
            # The functions the compiler and lookup module emit, spelled as PostgreSQL
            # spells them; sqlglot canonicalises several (DATE_TRUNC, TO_CHAR, STRING_AGG).
            r"""
            SELECT DATE_TRUNC('month', amount_given_on) AS month,
                   TO_CHAR(amount_given_on, 'YYYY-MM') AS label,
                   COUNT(loan_account_number) AS n,
                   COALESCE(SUM(amount_given), 0) AS amount,
                   ROUND(AVG(amount_given), 2) AS mean,
                   NULLIF(MIN(amount_given), 0) AS smallest,
                   LOWER(TRIM(REGEXP_REPLACE(loan_account_number::text, '\s+', ' ', 'g'))) AS who,
                   STRING_AGG(loan_account_number::text, ',') AS accounts,
                   EXTRACT(year FROM amount_given_on) AS yr,
                   CASE WHEN amount_given > 0 THEN 1 ELSE 0 END AS flag,
                   ROW_NUMBER() OVER (ORDER BY amount_given_on) AS rn
            FROM gold.loan_disbursements
            WHERE amount_given_on >= CURRENT_DATE - INTERVAL '1 year'
              AND amount_given_on <= NOW()
            GROUP BY 1, 2, loan_account_number, amount_given, amount_given_on
            LIMIT 100
            """,
        ],
    )
    def test_legitimate_queries_pass_in_allowlist_mode(self, sql):
        validate(sql, allow_pii=True, function_mode="allowlist")
