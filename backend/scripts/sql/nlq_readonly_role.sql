-- Genesis NLQ — read-only database role (docs/GENESIS_NLQ_BUILD_PLAN.md §7.1).
--
-- RUN MANUALLY, once, as a SUPERUSER:
--
--   psql -h <host> -U postgres -d moneypaldb -v pw="'<strong-password>'" \
--        -f backend/scripts/sql/nlq_readonly_role.sql
--
-- Why not a migration: CREATE ROLE is cluster-level and the application role `moneypal`
-- has neither SUPERUSER nor CREATEROLE (verified 2026-07-29 against PostgreSQL 16.13).
-- `:'pw'` is a psql client variable — it only expands under psql, not via a driver.
--
-- Afterwards put the same password in .env as NLQ_DB_PASSWORD (never in this file, and
-- never the same credential as POSTGRES_PASSWORD).

\set ON_ERROR_STOP on

CREATE ROLE nlq_readonly LOGIN PASSWORD :'pw';

REVOKE ALL ON DATABASE moneypaldb FROM nlq_readonly;
GRANT CONNECT ON DATABASE moneypaldb TO nlq_readonly;

GRANT USAGE ON SCHEMA silver TO nlq_readonly;
GRANT SELECT ON ALL TABLES IN SCHEMA silver TO nlq_readonly;

-- FOR ROLE moneypal is load-bearing. ALTER DEFAULT PRIVILEGES only covers objects
-- created by the named role; `silver.*` is owned by `moneypal`, so without this clause
-- every table the next ingestion creates would be invisible to NLQ.
ALTER DEFAULT PRIVILEGES FOR ROLE moneypal IN SCHEMA silver
    GRANT SELECT ON TABLES TO nlq_readonly;

-- Belt and braces. Both schemas already have nspacl = NULL (owner-only, no PUBLIC grant),
-- and PG15+ ships `public` without CREATE for PUBLIC, so these are no-ops today — kept so
-- a future stray GRANT does not silently widen the role.
REVOKE ALL ON SCHEMA bronze FROM nlq_readonly;
REVOKE ALL ON SCHEMA public FROM nlq_readonly;
REVOKE ALL ON ALL TABLES IN SCHEMA bronze FROM nlq_readonly;

-- Session defaults. NOT a security control: a session can override any of these with a
-- plain SET. The boundary is the privilege set above — SELECT on silver and nothing else.
ALTER ROLE nlq_readonly SET default_transaction_read_only = on;
ALTER ROLE nlq_readonly SET statement_timeout = '15s';
ALTER ROLE nlq_readonly SET idle_in_transaction_session_timeout = '10s';
ALTER ROLE nlq_readonly SET work_mem = '32MB';
ALTER ROLE nlq_readonly SET search_path = 'silver';

-- ---------------------------------------------------------------------------------------
-- Verification. Each of these must behave as annotated; run them after the grants above.
-- (\c reconnects as the new role — psql will prompt for the password.)
-- ---------------------------------------------------------------------------------------
-- \c moneypaldb nlq_readonly
-- SELECT count(*) FROM silver.loan_account_master;         -- expect: a number
-- SELECT count(*) FROM bronze.genlnacnts;                  -- expect: permission denied
-- CREATE TABLE silver.x (i int);                           -- expect: permission denied
-- BEGIN READ WRITE; DELETE FROM silver.loan_account_master;-- expect: permission denied
-- ROLLBACK;
--
-- backend/tests/nlq/test_readonly_role.py asserts all four in CI.
