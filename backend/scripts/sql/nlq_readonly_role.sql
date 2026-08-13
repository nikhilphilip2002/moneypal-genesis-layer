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

-- Start closed, then enumerate views. PostgreSQL treats views as tables for GRANT, so
-- `GRANT ... ON ALL TABLES` would also expose any physical Gold table added later.
REVOKE ALL ON ALL TABLES IN SCHEMA gold FROM nlq_readonly;
SELECT format('GRANT SELECT ON %I.%I TO nlq_readonly', schemaname, viewname)
FROM pg_views
WHERE schemaname = 'gold'
ORDER BY viewname
\gexec
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
-- SELECT count(*) FROM silver.loan_account_master;         -- expect: permission denied
-- SELECT count(*) FROM bronze.genlnacnts;                  -- expect: permission denied
-- CREATE TABLE gold.x (i int);                             -- expect: permission denied
-- BEGIN READ WRITE; DELETE FROM gold.loan_account_master;  -- expect: permission denied
-- ROLLBACK;
--
-- backend/tests/nlq/test_readonly_role.py asserts all four in CI.
