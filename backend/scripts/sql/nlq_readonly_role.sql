-- Genesis NLQ — read-only database role (docs/GENESIS_NLQ_BUILD_PLAN.md §7.1).
--
-- RUN MANUALLY, once, as a SUPERUSER:
--
--   psql -h <host> -U postgres -d moneypaldb -v pw=<strong-password> \
--        -f backend/scripts/sql/nlq_readonly_role.sql
--
-- Why not a migration: CREATE ROLE is cluster-level and the application role `moneypal`
-- has neither SUPERUSER nor CREATEROLE (verified 2026-07-29 against PostgreSQL 16.13).
-- `:'pw'` safely adds SQL-literal quoting. Do not put quote characters in the `-v pw=`
-- value itself, or those quotes become part of the role's actual password.
--
-- Afterwards put the same password in .env as NLQ_DB_PASSWORD (never in this file, and
-- never the same credential as POSTGRES_PASSWORD).

\set ON_ERROR_STOP on

SELECT 'CREATE ROLE nlq_readonly LOGIN'
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'nlq_readonly') \gexec
ALTER ROLE nlq_readonly LOGIN PASSWORD :'pw';

REVOKE ALL ON DATABASE moneypaldb FROM nlq_readonly;
GRANT CONNECT ON DATABASE moneypaldb TO nlq_readonly;

GRANT USAGE ON SCHEMA gold TO nlq_readonly;

-- Start closed, then grant only the reviewed semantic views. PostgreSQL treats views as
-- tables for GRANT, so `GRANT ... ON ALL TABLES` would also expose any physical Gold table
-- added later. Keep this allowlist synchronized with catalog/defs/gold/tables.yaml.
REVOKE ALL ON ALL TABLES IN SCHEMA gold FROM nlq_readonly;
GRANT SELECT ON
    gold.agent_master,
    gold.application_checklist_events,
    gold.branch_geography_bridge,
    gold.branch_master,
    gold.collection_activity_events,
    gold.collection_assignment_events,
    gold.collection_handover_events,
    gold.collection_team_hierarchy,
    gold.customer_master,
    gold.geography_master,
    gold.gl_daily_balances,
    gold.gl_ledger_master,
    gold.kyc_document_master,
    gold.loan_account_master,
    gold.loan_application_master,
    gold.loan_application_outcomes,
    gold.loan_balance_events,
    gold.loan_disbursement_events,
    gold.loan_ledger_events,
    gold.loan_repayment_events,
    gold.loan_reporting_attributes,
    gold.loan_schedule_events,
    gold.loan_waiver_events,
    gold.msme_master,
    gold.origination_vintage_matrix,
    gold.payment_receipt_events,
    gold.portfolio_daily_snapshot,
    gold.product_master,
    gold.reporting_product_mapping,
    gold.sales_team_hierarchy
TO nlq_readonly;

-- The reviewed as-of function reads raw Silver tables internally. Keep Silver invisible
-- to the runtime role while allowing this one fixed, non-dynamic function to execute with
-- its owner's privileges. Pinning search_path prevents object-shadowing attacks.
REVOKE ALL ON FUNCTION gold.portfolio_snapshot_as_of(date) FROM PUBLIC;
ALTER FUNCTION gold.portfolio_snapshot_as_of(date) SECURITY DEFINER;
ALTER FUNCTION gold.portfolio_snapshot_as_of(date)
    SET search_path = pg_catalog, gold, silver;
GRANT EXECUTE ON FUNCTION gold.portfolio_snapshot_as_of(date) TO nlq_readonly;

-- Re-run this script after creating a new governed view. New objects are intentionally
-- not auto-granted: adding a source to the LLM surface must be an explicit deployment.

-- Belt and braces. Both schemas already have nspacl = NULL (owner-only, no PUBLIC grant),
-- and PG15+ ships `public` without CREATE for PUBLIC, so these are no-ops today — kept so
-- a future stray GRANT does not silently widen the role.
REVOKE ALL ON SCHEMA bronze FROM nlq_readonly;
REVOKE ALL ON SCHEMA public FROM nlq_readonly;
REVOKE ALL ON SCHEMA silver FROM nlq_readonly;
REVOKE ALL ON ALL TABLES IN SCHEMA bronze FROM nlq_readonly;
REVOKE ALL ON ALL TABLES IN SCHEMA silver FROM nlq_readonly;

-- Session defaults. NOT a security control: a session can override any of these with a
-- plain SET. The boundary is the privilege set above — SELECT on Gold views and nothing
-- else. The SQL validator separately rejects non-Gold schemas.
ALTER ROLE nlq_readonly SET default_transaction_read_only = on;
ALTER ROLE nlq_readonly SET statement_timeout = '15s';
ALTER ROLE nlq_readonly SET idle_in_transaction_session_timeout = '10s';
ALTER ROLE nlq_readonly SET work_mem = '32MB';
ALTER ROLE nlq_readonly SET search_path = 'gold';

-- ---------------------------------------------------------------------------------------
-- Verification. Each of these must behave as annotated; run them after the grants above.
-- (\c reconnects as the new role — psql will prompt for the password.)
-- ---------------------------------------------------------------------------------------
-- \c moneypaldb nlq_readonly
-- SELECT count(*) FROM gold.loan_account_master;           -- expect: a number
-- SELECT count(*) FROM gold.payment_receipt_events;        -- expect: a number
-- SELECT count(*) FROM gold.origination_vintage_matrix;    -- expect: a number
-- SELECT count(*) FROM silver.loan_account_master;         -- expect: permission denied
-- SELECT count(*) FROM bronze.genlnacnts;                  -- expect: permission denied
-- CREATE TABLE gold.x (i int);                             -- expect: permission denied
-- BEGIN READ WRITE; DELETE FROM gold.loan_account_master;  -- expect: permission denied
-- ROLLBACK;
--
-- backend/tests/nlq/test_readonly_role.py asserts all four in CI.
