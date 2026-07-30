-- Genesis NLQ — indexes for the join/filter paths the catalog declares (§8).
-- Run as the schema owner (`moneypal`): psql -d moneypaldb -f this_file.sql
--
-- Column names verified against silver on 2026-07-29 (PostgreSQL 16.13). Only primary-key
-- indexes existed before this; the silver tables were loaded without a query workload in
-- mind. Every index below is named explicitly so it is droppable without guesswork.
--
-- Sizing note: the loan tables are 5k-13k rows and would seq-scan acceptably. The one that
-- genuinely needs help is loan_repayment_schedule at 260k rows, whose PK
-- (entity_num, acnt_no, sl_no) cannot serve a date-range filter.

\set ON_ERROR_STOP on

-- Grouping/filtering by branch and product — the two most common dimensions.
CREATE INDEX IF NOT EXISTS ix_lam_brn_prod
    ON silver.loan_account_master (gnlnac_appl_brn_code, gnlnac_prod_code);
CREATE INDEX IF NOT EXISTS ix_lam_sanc_date
    ON silver.loan_account_master (gnlnac_sanc_date);
CREATE INDEX IF NOT EXISTS ix_lam_cust_id
    ON silver.loan_account_master (gnlnac_cust_id);

-- PAR / DPD: always as-of a date, usually sliced by branch.
CREATE INDEX IF NOT EXISTS ix_acd_effdate_brn
    ON silver.asset_classification_details (ascd_effective_date, ascd_brn_code);
CREATE INDEX IF NOT EXISTS ix_acd_account
    ON silver.asset_classification_details (ascd_account_num);

-- Transaction tables: account join + date range in one index.
CREATE INDEX IF NOT EXISTS ix_lnrepay_acnt_date
    ON silver.loan_repayment_transactions (lnrepay_acnt_no, lnrepay_repay_date);
CREATE INDEX IF NOT EXISTS ix_lndisb_acnt_date
    ON silver.loan_disbursement_transactions (genlndisb_acnt_num, genlndisb_disb_date);

-- Largest table (260k). Both orderings earn their keep: account-scoped schedule lookups,
-- and portfolio-wide "what is due this month".
CREATE INDEX IF NOT EXISTS ix_lnsched_acnt_date
    ON silver.loan_repayment_schedule (lnsched_acnt_no, lnsched_sched_date);
CREATE INDEX IF NOT EXISTS ix_lnsched_date
    ON silver.loan_repayment_schedule (lnsched_sched_date);

-- The planner has no statistics on freshly loaded tables — without this the indexes above
-- may not even be chosen.
ANALYZE silver.loan_account_master;
ANALYZE silver.asset_classification_details;
ANALYZE silver.loan_repayment_transactions;
ANALYZE silver.loan_disbursement_transactions;
ANALYZE silver.loan_repayment_schedule;
