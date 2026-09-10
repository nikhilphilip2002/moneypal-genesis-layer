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

-- Start closed, then grant only the reviewed friendly views. PostgreSQL treats views as
-- tables for GRANT, so `GRANT ... ON ALL TABLES` would also expose any physical Gold table
-- added later. Keep this allowlist synchronized with catalog/defs/gold/tables.yaml.
REVOKE ALL ON ALL TABLES IN SCHEMA gold FROM nlq_readonly;
GRANT SELECT ON
    gold.agents,
    gold.branches,
    gold.business_loan_leads,
    gold.collection_activities,
    gold.customer_kyc_documents,
    gold.customers,
    gold.daily_loan_status,
    gold.emi_schedule,
    gold.general_ledger_balances,
    gold.loan_account_entries,
    gold.loan_accounts,
    gold.loan_applications,
    gold.loan_disbursements,
    gold.loan_products,
    gold.loan_repayments,
    gold.loan_vintage_performance,
    gold.payment_receipts,
    gold.staff_reporting_structure
TO nlq_readonly;

-- Point-in-time metrics now collapse the friendly daily status view directly, so the
-- technical as-of function is outside the assistant surface too.
REVOKE ALL ON FUNCTION gold.portfolio_snapshot_as_of(date) FROM PUBLIC, nlq_readonly;

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
-- SELECT count(*) FROM gold.loan_accounts;                  -- expect: a number
-- SELECT count(*) FROM gold.loan_repayments;                -- expect: a number
-- SELECT count(*) FROM silver.loan_account_master;         -- expect: permission denied
-- SELECT count(*) FROM bronze.genlnacnts;                  -- expect: permission denied
-- CREATE TABLE gold.x (i int);                             -- expect: permission denied
-- BEGIN READ WRITE; DELETE FROM gold.loan_account_master;  -- expect: permission denied
-- ROLLBACK;
--
-- backend/tests/nlq/test_readonly_role.py asserts all four in CI.
