"""Declarative specification of the RBI DNBS-02 return.

This module is the single source of truth for three questions:

  1. Which query feeds each section of the return  (``SOURCES``)
  2. Which workbook cell each RBI line item lands in  (``FIELD_SPECS``)
  3. Which RBI line items have no source at all, and why  (``FIELD_SPECS``, kind
     ``no_source``)

Two consumers read it. ``dnbs02_service.generate_dnbs02_excel`` uses it to *write* the
return; ``dnbs02_lineage.generate_dnbs02_lineage_excel`` uses it to *document* the
return. Because both read the same registry, the lineage workbook cannot drift from the
filing: a wrong mapping produces a wrong report, not merely a wrong document.

Everything here is pure - no database, no openpyxl. The derivation callables take the
assembled report dict and return a value, so they can be unit-tested without a warehouse.
"""

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# GL classification.
#
# silver.external_gl_master's own classification flags (extgl_int_income, extgl_operational_exps,
# extgl_int_expenses, ...) are NULL on all 723 rows, so they cannot be used. The only
# usable structure is the leading segment of extgl_access_code. See
# docs/DNBS02_EDA_REPORT.md section 5.
# ---------------------------------------------------------------------------
GL_SHARE_CAPITAL = "1001"
GL_BORROWINGS = "1002"
GL_FIXED_ASSETS = "1003"
GL_INCOME = "1007"
GL_INVESTMENTS = "1009"
GL_PROVISIONS = "1022"
GL_RESERVES = "1033"

# Asset codes that represent a non-performing asset under IRACP. SMA-0/1/2 are
# *standard* assets under stress and must never be counted here - the previous
# implementation used an ELSE catch-all that swept SMA-2 into "Doubtful / Loss" and
# provisioned it at 100%.
NPA_ASSET_CODES = ("SUB", "NPA", "DBT", "D1", "D2", "D3", "LOSS")
STANDARD_ASSET_CODES = ("STD", "SMA0", "SMA1", "SMA2")

ASSET_CODE_LABELS = {
    "STD": "Standard Assets",
    "SMA0": "SMA-0 (1-30 days)",
    "SMA1": "SMA-1 (31-60 days)",
    "SMA2": "SMA-2 (61-90 days)",
    "SUB": "Sub-Standard Assets",
    "DBT": "Doubtful Assets",
    "D1": "Doubtful Assets - up to 1 year",
    "D2": "Doubtful Assets - 1 to 3 years",
    "D3": "Doubtful Assets - over 3 years",
    "LOSS": "Loss Assets",
    "NPA": "Non-Performing Assets",
}


# ---------------------------------------------------------------------------
# SQL. Held as named constants rather than inline literals so the lineage writer can
# print the exact text that produced a figure. The %s placeholders are documented by the
# matching Source.binds tuple.
# ---------------------------------------------------------------------------

SNAPSHOT_DATES_SQL = """
SELECT DISTINCT gnlnr_report_date
FROM silver.loan_daily_snapshot_summary
WHERE gnlnr_report_date IS NOT NULL
ORDER BY gnlnr_report_date
"""

GL_YEARS_SQL = """
SELECT DISTINCT EXTRACT(YEAR FROM glbalh_ason_date)::INTEGER
FROM silver.gl_balance_history
WHERE glbalh_ason_date IS NOT NULL
ORDER BY 1
"""

GL_DATES_SQL = """
SELECT DISTINCT glbalh_ason_date::date
FROM silver.gl_balance_history
WHERE glbalh_ason_date IS NOT NULL
ORDER BY 1
"""

SUMMARY_SQL = """
SELECT COUNT(*),
       COUNT(DISTINCT gnlnr_cust_id),
       COALESCE(SUM(gnlnr_princ_os), 0) / 100000.0,
       COALESCE(SUM(gnlnr_int_due), 0) / 100000.0,
       COALESCE(SUM(gnlnr_provision_amt), 0) / 100000.0
FROM silver.loan_daily_snapshot_summary
WHERE gnlnr_report_date = CAST(%s AS DATE)
  AND gnlnr_closed_date IS NULL
"""

COVERAGE_SQL = """
SELECT COUNT(*) AS uncovered_accounts,
       COALESCE(SUM(COALESCE(a.gnlnac_lndisb_amt, a.gnlnac_sanc_amt)
                    - COALESCE(a.gnlnac_pri_repay_amt, 0)), 0) / 100000.0
           AS uncovered_lakhs
FROM silver.loan_account_master a
WHERE a.gnlnac_closure_date IS NULL
  AND NOT EXISTS (
        SELECT 1 FROM silver.loan_daily_snapshot_summary r
        WHERE r.gnlnr_acnt_num = a.gnlnac_acnt_num
  )
"""

PART1_SQL = """
SELECT LEFT(g.extgl_access_code, 4) AS gl_group,
       g.extgl_ext_head_descn,
       COALESCE(SUM(b.glbalh_bc_bal), 0) / 100000.0 AS amount_lakhs
FROM silver.gl_balance_history b
JOIN silver.external_gl_master g ON b.glbalh_glacc_code = g.extgl_access_code
WHERE b.glbalh_ason_date::date = CAST(%s AS DATE)
  AND LEFT(g.extgl_access_code, 4) IN (%s, %s, %s)
GROUP BY 1, 2
HAVING COALESCE(SUM(b.glbalh_bc_bal), 0) <> 0
ORDER BY 1, 3 DESC
"""

PART2_SQL = """
SELECT COALESCE(s.lnschm_schm_name, 'Scheme ' || COALESCE(r.gnlnr_schm_code, 'unmapped'))
           AS category,
       COUNT(*) AS account_count,
       COALESCE(SUM(r.gnlnr_princ_os), 0) / 100000.0 AS amount_lakhs
FROM silver.loan_daily_snapshot_summary r
LEFT JOIN silver.loan_product_scheme_master s
       ON s.lnschm_schm_code = r.gnlnr_schm_code
      AND s.lnschm_prod_code = r.gnlnr_prod_code
WHERE r.gnlnr_report_date = CAST(%s AS DATE)
  AND r.gnlnr_closed_date IS NULL
GROUP BY 1
ORDER BY 3 DESC
"""

PART2_MATURITY_SQL = """
SELECT CASE
           WHEN r.gnlnr_maturity_dt IS NULL THEN 'Unspecified maturity'
           WHEN r.gnlnr_maturity_dt <= CAST(%s AS DATE) + INTERVAL '3 months'
               THEN 'Receivable within 3 months'
           WHEN r.gnlnr_maturity_dt <= CAST(%s AS DATE) + INTERVAL '12 months'
               THEN 'Receivable in 3 to 12 months'
           ELSE 'Receivable after 12 months'
       END AS bucket,
       COUNT(*),
       COALESCE(SUM(r.gnlnr_princ_os), 0) / 100000.0
FROM silver.loan_daily_snapshot_summary r
WHERE r.gnlnr_report_date = CAST(%s AS DATE)
  AND r.gnlnr_closed_date IS NULL
GROUP BY 1
ORDER BY 3 DESC
"""

PART3_SQL = """
SELECT g.extgl_ext_head_descn,
       COALESCE(SUM(b.glbalh_bc_bal), 0) / 100000.0 AS amount_lakhs
FROM silver.gl_balance_history b
JOIN silver.external_gl_master g ON b.glbalh_glacc_code = g.extgl_access_code
WHERE b.glbalh_ason_date::date = CAST(%s AS DATE)
  AND LEFT(g.extgl_access_code, 4) = %s
GROUP BY 1
HAVING COALESCE(SUM(b.glbalh_bc_bal), 0) <> 0
ORDER BY 2 DESC
"""

PART6_SQL = """
SELECT g.extgl_ext_head_descn,
       ABS(COALESCE(SUM(b.glbalh_bc_bal), 0)) / 100000.0 AS amount_lakhs
FROM silver.gl_balance_history b
JOIN silver.external_gl_master g ON b.glbalh_glacc_code = g.extgl_access_code
WHERE b.glbalh_ason_date::date = CAST(%s AS DATE)
  AND LEFT(g.extgl_access_code, 4) = %s
GROUP BY 1
HAVING COALESCE(SUM(b.glbalh_bc_bal), 0) <> 0
ORDER BY 2 DESC
"""

PART8_SQL = """
SELECT COALESCE(gnlnr_asset_cd, 'UNCLASSIFIED') AS asset_code,
       COUNT(*),
       COALESCE(SUM(gnlnr_princ_os), 0) / 100000.0,
       COALESCE(SUM(gnlnr_provision_amt), 0) / 100000.0
FROM silver.loan_daily_snapshot_summary
WHERE gnlnr_report_date = CAST(%s AS DATE)
  AND gnlnr_closed_date IS NULL
GROUP BY 1
ORDER BY 3 DESC
"""

PART8A_SQL = """
WITH msme_loans AS (
    SELECT a.gnlnac_acnt_num,
           a.gnlnac_ln_intrate AS interest_rate,
           COALESCE(a.gnlnac_lndisb_amt, a.gnlnac_sanc_amt, 0)
               - COALESCE(a.gnlnac_pri_repay_amt, 0) AS outstanding
    FROM silver.loan_account_master a
    WHERE a.gnlnac_closure_date IS NULL
      AND a.gnlnac_ln_intrate IS NOT NULL
      AND EXISTS (
            SELECT 1 FROM silver.msme_sector_classification_mapping m
            WHERE m.nsecm_account_no = a.gnlnac_acnt_num
      )
)
SELECT COUNT(*) AS account_count,
       COALESCE(SUM(outstanding), 0) / 100000.0 AS amount_lakhs,
       MIN(interest_rate) AS min_rate,
       MAX(interest_rate) AS max_rate,
       CASE WHEN COALESCE(SUM(outstanding), 0) > 0
            THEN SUM(interest_rate * outstanding) / SUM(outstanding)
            ELSE AVG(interest_rate) END AS weighted_rate
FROM msme_loans
"""

ANNEX2_SQL = """
WITH holders AS (
    SELECT prosper_customer_id,
           MAX(TRIM(prosper_customer_name)) AS holder_name,
           SUM(COALESCE(share_no_of_units, 0)) AS units,
           CASE WHEN SUM(COALESCE(share_no_of_units, 0)) > 0
                THEN SUM(COALESCE(share_amount, 0))
                     / SUM(COALESCE(share_no_of_units, 0))
                ELSE MAX(share_face_value) END AS face_value
    FROM silver.migrated_shareholder_details
    GROUP BY prosper_customer_id
), totals AS (
    SELECT SUM(units) AS total_units FROM holders
)
SELECT holder_name, units, face_value,
       CASE WHEN total_units > 0 THEN units * 100.0 / total_units ELSE 0 END
FROM holders CROSS JOIN totals
WHERE units > 0
ORDER BY units DESC, prosper_customer_id
LIMIT 10
"""

# The three "top 25" queries below (Annex 9, 10, 11) each carry an explicit tiebreaker on
# a unique key. Without one the filed list is not reproducible: at 2026-06-30, 37 borrowers
# tie at exactly 10.00 lakh total outstanding, so ranks 6-25 were 20 arbitrary picks out of
# 37, resolved by whatever physical row order the heap happened to have. Re-running the
# same return after a VACUUM, a re-ingest, or a plan change would file a different set of
# names against identical amounts.
ANNEX9_SQL = """
SELECT r.gnlnr_cust_id,
       MAX(TRIM(r.gnlnr_cust_name))          AS borrower_name,
       MAX(NULLIF(TRIM(r.gnlnr_pan_no), '')) AS pan,
       COUNT(*)                              AS account_count,
       COALESCE(SUM(a.gnlnac_sanc_amt), 0) / 100000.0   AS sanctioned_amt,
       COALESCE(SUM(r.gnlnr_disb_amt), 0) / 100000.0    AS disbursed_amt,
       COALESCE(SUM(r.gnlnr_princ_os), 0) / 100000.0    AS principal_outstanding,
       COALESCE(SUM(r.gnlnr_int_due), 0) / 100000.0     AS accrued_interest,
       COALESCE(SUM(r.gnlnr_princ_os + r.gnlnr_int_due
                    + COALESCE(r.gnlnr_chg_due, 0)), 0) / 100000.0 AS total_outstanding,
       MAX(r.gnlnr_asset_cd)                 AS asset_code,
       MAX(CASE
               WHEN UPPER(TRIM(COALESCE(c.cifdata_type_flg, c.cifdata_cust_type))) = 'I'
                   THEN 'Individual'
               WHEN UPPER(TRIM(COALESCE(c.cifdata_type_flg, c.cifdata_cust_type))) = 'C'
                   THEN 'Corporate'
               ELSE NULL
           END)                              AS borrower_type
FROM silver.loan_daily_snapshot_summary r
LEFT JOIN silver.loan_account_master a ON a.gnlnac_acnt_num = r.gnlnr_acnt_num
LEFT JOIN silver.customer_information_file_master c
       ON c.cifdata_cust_id = r.gnlnr_cust_id
WHERE r.gnlnr_report_date = CAST(%s AS DATE)
  AND r.gnlnr_closed_date IS NULL
GROUP BY r.gnlnr_cust_id
ORDER BY total_outstanding DESC, r.gnlnr_cust_id
LIMIT 25
"""

ANNEX10_SQL = """
SELECT g.extgl_ext_head_descn,
       ABS(COALESCE(SUM(b.glbalh_bc_bal), 0)) / 100000.0 AS amount_lakhs
FROM silver.gl_balance_history b
JOIN silver.external_gl_master g ON b.glbalh_glacc_code = g.extgl_access_code
WHERE b.glbalh_ason_date::date = CAST(%s AS DATE)
  AND LEFT(g.extgl_access_code, 4) = %s
GROUP BY 1
HAVING COALESCE(SUM(b.glbalh_bc_bal), 0) <> 0
ORDER BY 2 DESC, 1
LIMIT 25
"""

ANNEX11_SQL = """
SELECT TRIM(r.gnlnr_cust_name),
       NULLIF(TRIM(r.gnlnr_pan_no), ''),
       COALESCE(r.gnlnr_princ_os, 0) / 100000.0,
       COALESCE(r.gnlnr_int_due, 0) / 100000.0,
       r.gnlnr_asset_cd,
       r.gnlnr_npa_dt,
       r.gnlnr_pay_date,
       COALESCE(a.gnlnac_sanc_amt, 0) / 100000.0
FROM silver.loan_daily_snapshot_summary r
LEFT JOIN silver.loan_account_master a ON a.gnlnac_acnt_num = r.gnlnr_acnt_num
WHERE r.gnlnr_report_date = CAST(%s AS DATE)
  AND r.gnlnr_closed_date IS NULL
  AND UPPER(TRIM(COALESCE(r.gnlnr_asset_cd, ''))) = ANY(%s)
ORDER BY r.gnlnr_princ_os DESC, r.gnlnr_acnt_num
LIMIT 25
"""

ANNEX13_SQL = """
WITH portfolio AS (
    SELECT r.gnlnr_brn_code,
           COUNT(DISTINCT r.gnlnr_cust_id) AS customer_count,
           COUNT(*) AS account_count,
           COALESCE(SUM(r.gnlnr_princ_os), 0) / 100000.0 AS amount_lakhs
    FROM silver.loan_daily_snapshot_summary r
    WHERE r.gnlnr_report_date = CAST(%s AS DATE)
      AND r.gnlnr_closed_date IS NULL
      AND r.gnlnr_brn_code IS NOT NULL
    GROUP BY r.gnlnr_brn_code
), branches AS (
    SELECT DISTINCT ON (mbrn_code)
           mbrn_code,
           NULLIF(BTRIM(mbrn_name), '') AS branch_name,
           NULLIF(CONCAT_WS(', ',
               NULLIF(BTRIM(mbrn_addr1), ''),
               NULLIF(BTRIM(mbrn_addr2), ''),
               NULLIF(BTRIM(mbrn_addr3), ''),
               NULLIF(BTRIM(mbrn_addr4), ''),
               NULLIF(BTRIM(mbrn_addr5), '')
           ), '') AS branch_address,
           mbrn_opened_on_date::date AS opening_date,
           mbrn_closure_date::date AS closing_date,
           NULLIF(BTRIM(mbrn_locn_code), '') AS location_code
    FROM silver.branch_master
    ORDER BY mbrn_code, mbrn_auth_on DESC NULLS LAST, mbrn_last_mod_on DESC NULLS LAST
)
SELECT p.gnlnr_brn_code,
       b.branch_name,
       b.branch_address,
       b.opening_date,
       b.closing_date,
       b.location_code,
       p.customer_count,
       p.account_count,
       p.amount_lakhs
FROM portfolio p
LEFT JOIN branches b ON b.mbrn_code = p.gnlnr_brn_code
ORDER BY p.amount_lakhs DESC, p.gnlnr_brn_code
"""


ACCOUNT_RECONCILIATION_SQL = """
WITH snapshot AS (
    SELECT r.gnlnr_acnt_num,
           MAX(r.gnlnr_cust_id) AS cust_id
    FROM silver.loan_daily_snapshot_summary r
    WHERE r.gnlnr_report_date = CAST(%s AS DATE)
      AND r.gnlnr_closed_date IS NULL
    GROUP BY r.gnlnr_acnt_num
), core_accounts AS (
    SELECT acnts_internal_acnum,
           MAX(acnts_client_num) AS client_num
    FROM silver.customer_accounts_master
    GROUP BY acnts_internal_acnum
), balances AS (
    SELECT DISTINCT acntbal_internal_acnum
    FROM silver.account_balances
), customers AS (
    SELECT DISTINCT cifdata_cust_id
    FROM silver.customer_information_file_master
)
SELECT COUNT(*) AS snapshot_accounts,
       COUNT(a.acnts_internal_acnum) AS core_account_matches,
       COUNT(b.acntbal_internal_acnum) AS balance_matches,
       COUNT(c.cifdata_cust_id) AS customer_matches
FROM snapshot s
LEFT JOIN core_accounts a ON a.acnts_internal_acnum = s.gnlnr_acnt_num
LEFT JOIN balances b ON b.acntbal_internal_acnum = s.gnlnr_acnt_num
LEFT JOIN customers c ON c.cifdata_cust_id = COALESCE(a.client_num, s.cust_id)
"""


# ---------------------------------------------------------------------------
# Source and Section descriptors.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Source:
    """Where one section's data comes from, in enough detail to audit it."""

    tables: Tuple[str, ...]
    columns: Tuple[str, ...]
    sql: str
    binds: Tuple[str, ...] = ()
    filters: str = ""
    grain: str = ""
    caveat: str = ""

    @property
    def table(self) -> str:
        return ", ".join(self.tables)


SOURCES: Dict[str, Source] = {
    "summary": Source(
        tables=("silver.loan_daily_snapshot_summary",),
        columns=(
            "gnlnr_cust_id",
            "gnlnr_princ_os",
            "gnlnr_int_due",
            "gnlnr_provision_amt",
        ),
        sql=SUMMARY_SQL,
        binds=("snapshot_date",),
        filters="gnlnr_report_date = {snapshot_date} AND gnlnr_closed_date IS NULL",
        grain="one row per open account on the snapshot date, aggregated to a single row",
    ),
    "coverage": Source(
        tables=("silver.loan_account_master", "silver.loan_daily_snapshot_summary"),
        columns=("gnlnac_lndisb_amt", "gnlnac_sanc_amt", "gnlnac_pri_repay_amt"),
        sql=COVERAGE_SQL,
        filters="gnlnac_closure_date IS NULL AND NOT EXISTS (matching row in genln_rpt_day)",
        grain="one row: the open accounts that have no dated snapshot at all",
        caveat=(
            "genln_rpt_day holds product 16 only, so products 1 and 13 have no dated "
            "snapshot and are excluded from the return rather than back-filled from "
            "undated balances."
        ),
    ),
    "part1_capital": Source(
        tables=("silver.gl_balance_history", "silver.external_gl_master"),
        columns=("glbalh_bc_bal", "glbalh_glacc_code", "extgl_access_code", "extgl_ext_head_descn"),
        sql=PART1_SQL,
        binds=("end_date", "GL_SHARE_CAPITAL", "GL_RESERVES", "GL_BORROWINGS"),
        filters=(
            "glbalh_ason_date = {end_date} AND LEFT(extgl_access_code,4) IN "
            "('1001' share capital, '1033' reserves, '1002' borrowings)"
        ),
        grain="one row per (GL group, GL head description), non-zero balances only",
        caveat=(
            "Uses the exact period-end GL history date; no nearest-date fallback is allowed."
        ),
    ),
    "part2_loans": Source(
        tables=("silver.loan_daily_snapshot_summary", "silver.loan_product_scheme_master"),
        columns=("gnlnr_princ_os", "gnlnr_schm_code", "gnlnr_prod_code", "lnschm_schm_name"),
        sql=PART2_SQL,
        binds=("snapshot_date",),
        filters="gnlnr_report_date = {snapshot_date} AND gnlnr_closed_date IS NULL",
        grain="one row per loan scheme",
    ),
    "part2_maturity": Source(
        tables=("silver.loan_daily_snapshot_summary",),
        columns=("gnlnr_maturity_dt", "gnlnr_princ_os"),
        sql=PART2_MATURITY_SQL,
        binds=("snapshot_date", "snapshot_date", "snapshot_date"),
        filters="gnlnr_report_date = {snapshot_date} AND gnlnr_closed_date IS NULL",
        grain="one row per residual-maturity bucket, measured from the snapshot date",
    ),
    "part3_income": Source(
        tables=("silver.gl_balance_history", "silver.external_gl_master"),
        columns=("glbalh_bc_bal", "extgl_access_code", "extgl_ext_head_descn"),
        sql=PART3_SQL,
        binds=("end_date", "GL_INCOME"),
        filters="glbalh_ason_date = {end_date} AND LEFT(extgl_access_code,4) = '1007' (income)",
        grain="one row per income GL head, non-zero balances only",
    ),
    "part4_nof": Source(
        tables=("silver.gl_balance_history", "silver.external_gl_master"),
        columns=("glbalh_bc_bal",),
        sql=PART1_SQL,
        binds=("end_date", "GL_SHARE_CAPITAL", "GL_RESERVES", "GL_BORROWINGS"),
        filters="derived from Part 1, not queried separately",
        grain="single figure",
        caveat=(
            "Owned funds only. The statutory NOF deductions (investments in group "
            "companies, intangibles) have no source in this warehouse."
        ),
    ),
    "part6_sensitive": Source(
        tables=("silver.gl_balance_history", "silver.external_gl_master"),
        columns=("glbalh_bc_bal", "extgl_access_code", "extgl_ext_head_descn"),
        sql=PART6_SQL,
        binds=("end_date", "GL_INVESTMENTS"),
        filters="glbalh_ason_date = {end_date} AND LEFT(extgl_access_code,4) = '1009' (investments)",
        grain="one row per investment GL head",
    ),
    "part8_asset_quality": Source(
        tables=("silver.loan_daily_snapshot_summary",),
        columns=("gnlnr_asset_cd", "gnlnr_princ_os", "gnlnr_provision_amt"),
        sql=PART8_SQL,
        binds=("snapshot_date",),
        filters="gnlnr_report_date = {snapshot_date} AND gnlnr_closed_date IS NULL",
        grain="one row per IRACP asset classification code",
        caveat=(
            "Provision is read from the ledger (gnlnr_provision_amt), not assumed from a "
            "regulatory rate."
        ),
    ),
    "part8a_msme": Source(
        tables=("silver.loan_account_master", "silver.msme_sector_classification_mapping"),
        columns=(
            "gnlnac_ln_intrate",
            "gnlnac_lndisb_amt",
            "gnlnac_sanc_amt",
            "gnlnac_pri_repay_amt",
            "nsecm_account_no",
        ),
        sql=PART8A_SQL,
        filters="gnlnac_closure_date IS NULL AND account present in nsecmsmemap",
        grain="single aggregate row over all MSME-mapped open accounts",
        caveat=(
            "Sourced from the loan master, not the snapshot: nsecmsmemap maps product-13 "
            "accounts exclusively and genln_rpt_day holds product 16 only, so the two "
            "sets are disjoint. genlnacnts has no as-of dimension, so the outstanding "
            "amount is a current balance rather than a period-end one."
        ),
    ),
    "annex2_shareholders": Source(
        tables=("silver.migrated_shareholder_details",),
        columns=("prosper_customer_name", "share_no_of_units", "share_face_value", "share_amount"),
        sql=ANNEX2_SQL,
        filters="valid migrated share-register rows aggregated by customer; top 10 by units",
        grain="one row per shareholder",
        caveat="The source has no PAN column; PAN remains blank.",
    ),
    "annex9_top_borrowers": Source(
        tables=(
            "silver.loan_daily_snapshot_summary",
            "silver.loan_account_master",
            "silver.customer_information_file_master",
        ),
        columns=(
            "gnlnr_cust_id",
            "gnlnr_cust_name",
            "gnlnr_pan_no",
            "gnlnr_princ_os",
            "gnlnr_int_due",
            "gnlnr_chg_due",
            "gnlnr_disb_amt",
            "gnlnac_sanc_amt",
            "cifdata_type_flg",
            "cifdata_cust_type",
        ),
        sql=ANNEX9_SQL,
        binds=("snapshot_date",),
        filters="gnlnr_report_date = {snapshot_date} AND gnlnr_closed_date IS NULL",
        grain="top 25 by total outstanding, aggregated per borrower (not per account)",
        caveat="CIF type I/C is mapped to Individual/Corporate; unknown codes remain blank.",
    ),
    "annex10_investment_totals": Source(
        tables=("silver.gl_balance_history", "silver.external_gl_master"),
        columns=("glbalh_bc_bal", "extgl_ext_head_descn"),
        sql=ANNEX10_SQL,
        binds=("end_date", "GL_INVESTMENTS"),
        filters="glbalh_ason_date = {end_date} AND LEFT(extgl_access_code,4) = '1009'",
        grain="top 25 investment GL heads by book value",
    ),
    "annex11_top_npas": Source(
        tables=("silver.loan_daily_snapshot_summary", "silver.loan_account_master"),
        columns=(
            "gnlnr_asset_cd",
            "gnlnr_cust_name",
            "gnlnr_pan_no",
            "gnlnr_princ_os",
            "gnlnr_npa_dt",
            "gnlnr_pay_date",
            "gnlnac_sanc_amt",
        ),
        sql=ANNEX11_SQL,
        binds=("snapshot_date", "NPA_ASSET_CODES"),
        filters=(
            "gnlnr_report_date = {snapshot_date} AND gnlnr_closed_date IS NULL "
            "AND gnlnr_asset_cd IN " + str(NPA_ASSET_CODES)
        ),
        grain="top 25 NPA accounts by principal outstanding",
    ),
    "annex13_branches": Source(
        tables=("silver.loan_daily_snapshot_summary", "silver.branch_master"),
        columns=(
            "gnlnr_brn_code",
            "gnlnr_cust_id",
            "gnlnr_princ_os",
            "mbrn_code",
            "mbrn_name",
            "mbrn_addr1..mbrn_addr5",
            "mbrn_opened_on_date",
            "mbrn_closure_date",
            "mbrn_locn_code",
        ),
        sql=ANNEX13_SQL,
        binds=("snapshot_date",),
        filters="gnlnr_report_date = {snapshot_date} AND gnlnr_closed_date IS NULL",
        grain="one row per branch code",
        caveat=(
            "Branch master supplies name, address and opening/closing dates, but its location "
            "code has no city/state/district reference mapping. Those geography cells stay blank."
        ),
    ),
    "core_account_reconciliation": Source(
        tables=(
            "silver.loan_daily_snapshot_summary",
            "silver.customer_accounts_master",
            "silver.account_balances",
            "silver.customer_information_file_master",
        ),
        columns=(
            "gnlnr_acnt_num",
            "gnlnr_cust_id",
            "acnts_internal_acnum",
            "acnts_client_num",
            "acntbal_internal_acnum",
            "cifdata_cust_id",
        ),
        sql=ACCOUNT_RECONCILIATION_SQL,
        binds=("snapshot_date",),
        filters="snapshot accounts open at gnlnr_report_date = {snapshot_date}",
        grain="one reconciliation result for the requested portfolio snapshot",
        caveat=(
            "Core account and balance tables are current-state controls, not historical "
            "reporting facts; they validate coverage but never replace the dated snapshot."
        ),
    ),
}


@dataclass
class Section:
    """One stage of the report pipeline.

    ``run`` is bound in dnbs02_service (it needs a cursor); everything else is metadata
    the lineage writer reads. A section with ``run=None`` is structurally unsourced and
    only ever records why.
    """

    key: str
    source: Optional[Source] = None
    requires: Tuple[str, ...] = ()
    run: Optional[Callable[[Any], int]] = None
    precondition: Optional[Callable[[Any], bool]] = None
    precondition_reason: Optional[Callable[[Any], str]] = None
    no_source_reason: str = ""
    note: str = ""


# ---------------------------------------------------------------------------
# Workbook cell map.
# ---------------------------------------------------------------------------


class CellMapError(RuntimeError):
    """The workbook does not match the declared cell map."""


def _norm(text: Any) -> str:
    """Normalise a template label for comparison: collapse whitespace, casefold."""
    return " ".join(str(text or "").split()).casefold()


class LineItem:
    """One RBI line item, located by its label text rather than by row number.

    Row positions were previously hardcoded, which put paid-up equity into "Total
    Authorized Capital" and net owned funds into "Compulsory Convertible Preference
    Shares". Resolving by label makes a template change fail loudly instead of silently
    misfiling a figure.
    """

    __slots__ = ("sheet", "label", "column", "within")

    def __init__(self, sheet: str, label: str, column: str, within: Optional[Tuple[int, int]] = None):
        self.sheet = sheet
        self.label = label
        self.column = column
        self.within = within


class TableColumn:
    __slots__ = ("column", "field", "header")

    def __init__(self, column: str, field: str, header: str):
        self.column = column
        self.field = field
        self.header = header


class TableBlock:
    """A repeating annexure table, with each column pinned to its expected header."""

    __slots__ = (
        "sheet", "source_key", "section", "header_row", "first_row", "max_rows",
        "columns", "serial_column",
    )

    def __init__(
        self,
        sheet: str,
        source_key: str,
        columns: List[TableColumn],
        header_row: int = 12,
        first_row: int = 13,
        max_rows: int = 40,
        serial_column: Optional[str] = None,
        section: Optional[str] = None,
    ):
        self.sheet = sheet
        # The key the rows live under in the report dict...
        self.source_key = source_key
        # ...which is not always the key the section is registered under in provenance.
        # Annex 10's rows are `annex10_top_investments` but its section is
        # `annex10_investment_totals`, and conflating the two lost the annexure's source.
        self.section = section or source_key
        self.columns = columns
        self.header_row = header_row
        self.first_row = first_row
        self.max_rows = max_rows
        self.serial_column = serial_column


LABEL_COLUMN = 2  # column B carries the RBI line-item taxonomy on every Part sheet

TABLE_BLOCKS: List[TableBlock] = [
    TableBlock(
        sheet="DNBS02_Annex9",
        source_key="annex9_top_borrowers",
        serial_column="B",
        columns=[
            TableColumn("C", "borrower_name", "Name of the Borrower"),
            TableColumn("D", "pan", "PAN"),
            TableColumn("E", "borrower_type", "Type of Borrower"),
            TableColumn("F", "sanctioned_amt", "Total Sanctioned"),
            TableColumn("G", "disbursed_amt", "Disbursed Loan Amount"),
            TableColumn("H", "undisbursed_amt", "Un-disbursed Loan Amount"),
            TableColumn("I", "principal_outstanding", "Total Principal Outstanding"),
            TableColumn("J", "accrued_interest", "Total Accrued Interest"),
            TableColumn("K", "account_status", "Status of Account"),
            TableColumn("L", "total_outstanding", "Amount Outstanding"),
        ],
    ),
    TableBlock(
        sheet="DNBS02_Annex10",
        source_key="annex10_top_investments",
        section="annex10_investment_totals",
        columns=[
            TableColumn("B", "entity_name", "Name of the Entity"),
            TableColumn("C", "nature", "Nature of investment"),
            TableColumn("D", "investment_type", "Type of Investment"),
            TableColumn("E", "pan", "PAN"),
            TableColumn("F", "book_value", "Book Value"),
            TableColumn("G", "is_group_company", "Whether it is Group Company?"),
            TableColumn("H", "amt_outstanding", "Amount Outstanding"),
        ],
    ),
    TableBlock(
        sheet="DNBS02_Annex11",
        source_key="annex11_top_npas",
        serial_column="B",
        columns=[
            TableColumn("C", "borrower_name", "Name of the Borrower"),
            TableColumn("D", "pan", "PAN"),
            TableColumn("E", "borrower_type", "Type of Borrower"),
            TableColumn("J", "sanctioned_amt", "Total Sanctioned Loan Amount"),
            TableColumn("K", "principal_os", "Total Outstanding Loan Amount"),
            TableColumn("L", "last_payment_date", "Date of Last Payment"),
            TableColumn("M", "npa_date", "Date of First Default"),
        ],
    ),
    TableBlock(
        sheet="DNBS02_Annex13",
        source_key="annex13_branches",
        serial_column="B",
        columns=[
            TableColumn("C", "branch_name", "Branch Name"),
            TableColumn("D", "address", "Branch Address"),
            TableColumn("E", "city", "City"),
            TableColumn("F", "state", "State"),
            TableColumn("G", "district", "District"),
            TableColumn("H", "opening_date", "Opening Date"),
            TableColumn("I", "closing_date", "Closing Date"),
            TableColumn("K", "account_count", "Number of loan accounts"),
            TableColumn("L", "total_outstanding", "Amount of loans & advances outstanding"),
        ],
    ),
    TableBlock(
        sheet="DNBS02_Annex2",
        source_key="annex2_shareholders",
        columns=[
            TableColumn("B", "name", "Name"),
            TableColumn("C", "type_of_capital", "Type of capital"),
            TableColumn("D", "pan", "PAN"),
            TableColumn("E", "num_shares", "Number of shares held"),
            TableColumn("F", "face_value", "Face Value"),
            TableColumn("G", "shareholding_pct", "Percentage shareholding"),
        ],
    ),
]

# GL account description -> RBI Part 1 line. Several GL heads legitimately roll into one
# RBI line, so values are summed per target line.
GL_DESC_TO_PART1_LINE: Dict[str, str] = {
    "EQUITY SHARES": "(i) Ordinary Shares",
    "APPLICATION MONEY ON RIGHTS SHARES RECD": "(viii) Share application money pending allotment",
    "APPLICATION MONEY RIGHTS AND SHARES RECD": "(viii) Share application money pending allotment",
    "CAPITAL RESERVE": "(i) Capital Reserve",
    "SHARES PREMIUM": "(iii) Share Premium",
    "GENERAL RESERVE": "(iv) General Reserves",
    "SPECIAL RESERVE": "(v) Statutory/Special Reserve",
    "PROFIT AND LOSS ACCOUNT": "(x) Balance of profit and loss account",
    "PROFIT & LOSS A/C": "(x) Balance of profit and loss account",
    "PROFIT AND LOSS FOR 25 AND 2026": "(x) Balance of profit and loss account",
}

# GL account description -> RBI Part 3 income line.
GL_DESC_TO_PART3_LINE: Dict[str, str] = {
    "MICRO ENTERPRISES - INTEREST INCOME": "(b) Interest on Other Loans",
    "INTEREST COLLECTED": "(b) Interest on Other Loans",
    "INTEREST RECEIVED - LOANS AND ADVANCES": "(b) Interest on Other Loans",
    "INTEREST OTHERS": "(b) Interest on Other Loans",
    "INTEREST ON FD WITH BANKS": "(a) Interest",
    "DIVIDEND RECEIVED": "(b) Dividends",
    "PROFIT ON SALE OF MUTUAL FUNDS": "(vi) Profit on Sale of Investments",
    "PROFIT ON SALE OF SHARES": "(vi) Profit on Sale of Investments",
}

# Part 3 has two "(a) Interest" style labels; scope the investment-income ones to the
# rows below "(v) Investment Income" so the lookup stays unambiguous.
PART3_INVESTMENT_SCOPE = (23, 26)

PART1_TOTAL_LINES = {
    "2 Share Capital": "share_capital",
    "3 Reserves and Surplus": "reserves",
}

ASSET_CLASS_TO_PART8C_LINE = {
    "standard": "(i) Standard assets",
    "sub": "(ii) Sub-standard assets",
    "doubtful": "(iii) Doubtful assets",
    "loss": "(iv) Loss assets",
}

# Part 2 residual-maturity bucket -> RBI line label.
PART2_MATURITY_LINES = {
    "Receivable within 3 months": "(a) Of Total Loans",
    "Receivable in 3 to 12 months": "(b) Of Total Loans",
    "Receivable after 12 months": "(c ) Of Total Loans",
}


# ---------------------------------------------------------------------------
# Pure derivations. Each takes the assembled report dict and returns the value for one
# cell, or None to leave the cell untouched.
# ---------------------------------------------------------------------------


def _sum_mapped(rows, key: str, mapping: Dict[str, str], target: str):
    """Sum the rows whose description maps to `target`, or None if none do.

    Returning None rather than 0.0 keeps a line the GL never fed blank, which is the
    difference between "we have no data" and "the balance is zero".
    """
    total = None
    for row in rows:
        if row.get("gl_group") == "TOTAL":
            continue
        if mapping.get(str(row.get(key, "")).upper()) == target:
            total = round((total or 0.0) + row["amount_lakhs"], 2)
    return total


def part1_line(target: str) -> Callable[[Dict[str, Any]], Any]:
    def fn(data):
        return _sum_mapped(data.get("part1_capital") or [], "particulars", GL_DESC_TO_PART1_LINE, target)

    return fn


def part3_line(target: str) -> Callable[[Dict[str, Any]], Any]:
    def fn(data):
        return _sum_mapped(data.get("part3_income") or [], "head", GL_DESC_TO_PART3_LINE, target)

    return fn


def part1_total(particulars: str) -> Callable[[Dict[str, Any]], Any]:
    def fn(data):
        for row in data.get("part1_capital") or []:
            if row.get("gl_group") == "TOTAL" and row.get("particulars") == particulars:
                return row["amount_lakhs"]
        return 0.0

    return fn


def part2_maturity_line(bucket: str) -> Callable[[Dict[str, Any]], Any]:
    def fn(data):
        for row in data.get("part2_maturity") or []:
            if row.get("bucket") == bucket:
                return row["amount_lakhs"]
        return None

    return fn


def part8c_buckets(data: Dict[str, Any]) -> Tuple[Dict[str, float], Dict[str, float], List[str]]:
    """Roll IRACP asset codes up into the four RBI Part 8C classes.

    Returns (amounts, provisions, unmapped_codes). SMA-0/1/2 are standard assets; an
    unrecognised code is reported rather than swept into a bucket.
    """
    buckets = {"standard": 0.0, "sub": 0.0, "doubtful": 0.0, "loss": 0.0}
    provisions = dict(buckets)
    unmapped: List[str] = []
    for row in data.get("part8_asset_quality") or []:
        code = row["asset_code"]
        if code in STANDARD_ASSET_CODES:
            key = "standard"
        elif code in ("SUB", "NPA"):
            key = "sub"
        elif code in ("DBT", "D1", "D2", "D3"):
            key = "doubtful"
        elif code == "LOSS":
            key = "loss"
        else:
            unmapped.append(code)
            continue
        buckets[key] += row["amount_lakhs"]
        provisions[key] += row["provision_lakhs"]
    return buckets, provisions, unmapped


def part8c_amount(bucket_key: str) -> Callable[[Dict[str, Any]], Any]:
    def fn(data):
        return round(part8c_buckets(data)[0][bucket_key], 2)

    return fn


def part8c_provision(bucket_key: str) -> Callable[[Dict[str, Any]], Any]:
    def fn(data):
        return round(part8c_buckets(data)[1][bucket_key], 2)

    return fn


def part8c_gross_amount(data: Dict[str, Any]) -> float:
    return round(sum(part8c_buckets(data)[0].values()), 2)


def part8c_gross_provision(data: Dict[str, Any]) -> float:
    return round(sum(part8c_buckets(data)[1].values()), 2)


def summary_field(name: str) -> Callable[[Dict[str, Any]], Any]:
    def fn(data):
        return data["summary"][name]

    return fn


def msme_field(name: str) -> Callable[[Dict[str, Any]], Any]:
    def fn(data):
        rows = data.get("part8a_msme") or []
        return rows[0][name] if rows else None

    return fn


# ---------------------------------------------------------------------------
# FieldSpec: the cell-level registry.
# ---------------------------------------------------------------------------

KIND_LINE = "line"  # a single RBI line item, located by label
KIND_TABLE = "table"  # a column of a repeating annexure table
KIND_META = "meta"  # a fixed coordinate (FilingInfo, period stamps)
KIND_NO_SOURCE = "no_source"  # documented gap: nothing is ever written


@dataclass
class FieldSpec:
    """One documented target in the workbook.

    `value` is None for no_source specs and for table columns (whose values come from
    the section's row list via TableBlock).
    """

    sheet: str
    rbi_line: str
    kind: str = KIND_LINE
    column: str = ""
    within: Optional[Tuple[int, int]] = None
    coord: str = ""  # KIND_META only
    section: str = ""
    derivation: str = ""
    value: Optional[Callable[[Dict[str, Any]], Any]] = None
    gate: str = ""  # report key that must be non-empty before writing
    unit: str = ""
    no_source_reason: str = ""
    table_field: str = ""  # KIND_TABLE only
    data_key: str = ""  # report dict key holding the rows, when it differs from `section`

    @property
    def target(self) -> str:
        if self.kind == KIND_META:
            return f"{self.sheet}!{self.coord}"
        if self.kind == KIND_NO_SOURCE:
            return f"{self.sheet} / {self.rbi_line}"
        return f"{self.sheet}!{self.column}<row of {self.rbi_line!r}>"

    def line_item(self) -> LineItem:
        return LineItem(self.sheet, self.rbi_line, self.column, self.within)


LAKHS = "Rs. lakh"
PCT = "per cent"
COUNT = "count"


def _part1_specs() -> List[FieldSpec]:
    specs: List[FieldSpec] = []
    # One spec per distinct RBI target line, listing the GL heads that feed it.
    seen: List[str] = []
    for target in GL_DESC_TO_PART1_LINE.values():
        if target in seen:
            continue
        seen.append(target)
        heads = [k for k, v in GL_DESC_TO_PART1_LINE.items() if v == target]
        specs.append(
            FieldSpec(
                sheet="DNBS02_PART1",
                rbi_line=target,
                column="C",
                section="part1_capital",
                derivation=(
                    "SUM(glbbal_bc_bal)/100000 for GL head(s) " + ", ".join(repr(h) for h in heads)
                    + "; blank if no such head carries a balance"
                ),
                value=part1_line(target),
                gate="part1_capital",
                unit=LAKHS,
            )
        )
    for label, particulars in (
        ("2 Share Capital", "Share Capital"),
        ("3 Reserves and Surplus", "Reserves and Surplus"),
    ):
        group = GL_SHARE_CAPITAL if particulars == "Share Capital" else GL_RESERVES
        specs.append(
            FieldSpec(
                sheet="DNBS02_PART1",
                rbi_line=label,
                column="C",
                section="part1_capital",
                derivation=(
                    f"SUM(glbbal_bc_bal)/100000 over every GL head in access-code group "
                    f"{group} - the whole group total, not only the mapped heads"
                ),
                value=part1_total(particulars),
                gate="part1_capital",
                unit=LAKHS,
            )
        )
    return specs


def _part3_specs() -> List[FieldSpec]:
    specs: List[FieldSpec] = []
    seen: List[str] = []
    for target in GL_DESC_TO_PART3_LINE.values():
        if target in seen:
            continue
        seen.append(target)
        heads = [k for k, v in GL_DESC_TO_PART3_LINE.items() if v == target]
        scope = PART3_INVESTMENT_SCOPE if target in ("(a) Interest", "(b) Dividends") else None
        specs.append(
            FieldSpec(
                sheet="DNBS02_PART3",
                rbi_line=target,
                column="C",
                within=scope,
                section="part3_income",
                derivation=(
                    "SUM(glbbal_bc_bal)/100000 for GL head(s) " + ", ".join(repr(h) for h in heads)
                    + (
                        f"; label resolved within rows {scope[0]}-{scope[1]} because "
                        "Part 3 repeats this label under Investment Income"
                        if scope
                        else ""
                    )
                ),
                value=part3_line(target),
                gate="part3_income",
                unit=LAKHS,
            )
        )
    return specs


def _table_specs() -> List[FieldSpec]:
    specs: List[FieldSpec] = []
    for block in TABLE_BLOCKS:
        for col in block.columns:
            specs.append(
                FieldSpec(
                    sheet=block.sheet,
                    rbi_line=col.header,
                    kind=KIND_TABLE,
                    column=col.column,
                    section=block.section,
                    data_key=block.source_key,
                    table_field=col.field,
                    derivation=(
                        f"rows {block.first_row}-{block.first_row + block.max_rows - 1}, "
                        f"field {col.field!r} of section {block.section!r}"
                    ),
                )
            )
    return specs


FIELD_SPECS: List[FieldSpec] = (
    [
        # -- FilingInfo and period stamps: purely UI-derived -------------------
        FieldSpec(
            sheet="FilingInfo",
            rbi_line="Reporting frequency",
            kind=KIND_META,
            coord="C11",
            section="_bindings",
            derivation="UI frequency selection, title-cased",
        ),
        FieldSpec(
            sheet="FilingInfo",
            rbi_line="Period start date",
            kind=KIND_META,
            coord="C12",
            section="_bindings",
            derivation="parse_period_range(frequency, period)[0], formatted dd/mm/yyyy",
        ),
        FieldSpec(
            sheet="FilingInfo",
            rbi_line="Period end date",
            kind=KIND_META,
            coord="C13",
            section="_bindings",
            derivation="parse_period_range(frequency, period)[1], formatted dd/mm/yyyy",
        ),
        FieldSpec(
            sheet="FilingInfo",
            rbi_line="Reporting unit",
            kind=KIND_META,
            coord="C15",
            section="_bindings",
            derivation="constant: every amount in this return is divided by 100000",
        ),
        FieldSpec(
            sheet="FilingInfo",
            rbi_line="General remarks",
            kind=KIND_META,
            coord="(General remarks row)",
            section="_bindings",
            derivation=(
                "snapshot date, GL year, coverage reconciliation and the list of "
                "sections left blank for want of a source"
            ),
        ),
        FieldSpec(
            sheet="(every DNBS02_* sheet)",
            rbi_line="Reporting Period End Date",
            kind=KIND_META,
            coord="B5",
            section="_bindings",
            derivation="period end date formatted DD-MON-YYYY",
        ),
        # -- Part 2 ------------------------------------------------------------
        FieldSpec(
            sheet="DNBS02_PART2",
            rbi_line="1 Loans & Advances",
            column="C",
            section="summary",
            derivation="SUM(gnlnr_princ_os)/100000 over open accounts at the snapshot date",
            value=summary_field("total_loan_book"),
            unit=LAKHS,
        ),
    ]
    + [
        FieldSpec(
            sheet="DNBS02_PART2",
            rbi_line=label,
            column="C",
            section="part2_maturity",
            derivation=(
                f"SUM(gnlnr_princ_os)/100000 for accounts in the {bucket!r} residual "
                "maturity bucket, measured from the snapshot date"
            ),
            value=part2_maturity_line(bucket),
            unit=LAKHS,
        )
        for bucket, label in PART2_MATURITY_LINES.items()
    ]
    + _part1_specs()
    + _part3_specs()
    + [
        # -- Part 4 ------------------------------------------------------------
        FieldSpec(
            sheet="DNBS02_PART4",
            rbi_line="Owned Fund (from Part 1)",
            column="C",
            section="part4_nof",
            derivation="Part 1 share capital + reserves (access-code groups 1001 + 1033)",
            value=summary_field("owned_funds"),
            gate="part4_nof",
            unit=LAKHS,
        ),
    ]
    + [
        # -- Part 8C: asset classification -------------------------------------
        FieldSpec(
            sheet="DNBS02_PART8C",
            rbi_line=label,
            column=col,
            section="part8_asset_quality",
            derivation=(
                f"SUM({src})/100000 for asset codes rolling up to {key!r}"
                + (
                    " (STD, SMA0, SMA1, SMA2 - SMA buckets are standard assets under stress)"
                    if key == "standard"
                    else ""
                )
            ),
            value=(part8c_amount(key) if col == "C" else part8c_provision(key)),
            gate="part8_asset_quality",
            unit=LAKHS,
        )
        for key, label in ASSET_CLASS_TO_PART8C_LINE.items()
        for col, src in (("C", "gnlnr_princ_os"), ("D", "gnlnr_provision_amt"))
    ]
    + [
        FieldSpec(
            sheet="DNBS02_PART8C",
            rbi_line="2 Gross Credit Exposure",
            column="C",
            section="part8_asset_quality",
            derivation="sum of the four asset-classification amounts above",
            value=part8c_gross_amount,
            gate="part8_asset_quality",
            unit=LAKHS,
        ),
        FieldSpec(
            sheet="DNBS02_PART8C",
            rbi_line="2 Gross Credit Exposure",
            column="D",
            section="part8_asset_quality",
            derivation="sum of the four provision amounts above",
            value=part8c_gross_provision,
            gate="part8_asset_quality",
            unit=LAKHS,
        ),
        FieldSpec(
            sheet="DNBS02_PART8C",
            rbi_line="3 Total NPAs",
            column="C",
            section="part8_asset_quality",
            derivation=(
                "SUM(gnlnr_princ_os)/100000 for asset codes " + ", ".join(NPA_ASSET_CODES)
                + "; SMA-0/1/2 are excluded, they are standard assets"
            ),
            value=summary_field("gross_npa_amount"),
            gate="part8_asset_quality",
            unit=LAKHS,
        ),
        FieldSpec(
            sheet="DNBS02_PART8C",
            rbi_line="4 Gr. NPA (%)",
            column="C",
            section="part8_asset_quality",
            derivation="gross_npa_amount / total_loan_book * 100, or 0 if the book is empty",
            value=summary_field("gross_npa_pct"),
            gate="part8_asset_quality",
            unit=PCT,
        ),
        # -- Part 8A: MSME -----------------------------------------------------
    ]
    + [
        FieldSpec(
            sheet="DNBS02_PART8A",
            rbi_line=label,
            column=col,
            section="part8a_msme",
            derivation=derivation,
            value=msme_field(fieldname),
            gate="part8a_msme",
            unit=unit,
        )
        for label in ("A Micro, Small and Medium Enterprises", "A.1 Direct Exposure")
        for col, fieldname, unit, derivation in (
            ("C", "account_count", COUNT, "COUNT(*) of open accounts present in nsecmsmemap"),
            (
                "D",
                "amount_lakhs",
                LAKHS,
                "SUM(disbursed or sanctioned - repaid)/100000 over MSME-mapped open accounts",
            ),
        )
    ]
    + [
        FieldSpec(
            sheet="DNBS02_PART8A",
            rbi_line="A.1 Direct Exposure",
            column=col,
            section="part8a_msme",
            derivation=derivation,
            value=msme_field(fieldname),
            gate="part8a_msme",
            unit=PCT,
        )
        for col, fieldname, derivation in (
            ("G", "min_interest_rate", "MIN(gnlnac_ln_intrate) over MSME-mapped open accounts"),
            ("H", "max_interest_rate", "MAX(gnlnac_ln_intrate) over MSME-mapped open accounts"),
            (
                "I",
                "weighted_avg_interest_rate",
                "SUM(rate * outstanding) / SUM(outstanding) over MSME-mapped open accounts",
            ),
        )
    ]
    + _table_specs()
    + [
        # -- Documented gaps ---------------------------------------------------
        # Every one of these is a line RBI asks for that this warehouse cannot back.
        # They are listed so a reader can tell a gap from a genuine zero.
        FieldSpec(
            sheet="DNBS02_PART9",
            rbi_line="Capital Adequacy Ratio (CRAR)",
            kind=KIND_NO_SOURCE,
            section="part9_crar",
            no_source_reason=(
                "Requires risk-weighted assets. No RWA feed exists in the warehouse and "
                "risk weights cannot be derived from the loan snapshot alone. Previously "
                "reported as the fabricated expression 24.8 + date_scale_factor * 0.1."
            ),
        ),
        FieldSpec(
            sheet="DNBS02_PART2",
            rbi_line="1.1 Secured / 1.2 Unsecured split",
            kind=KIND_NO_SOURCE,
            section="part2_security_split",
            no_source_reason=(
                "silver.loan_product_scheme_master marks every scheme unsecured and covers product 16 "
                "only, so the split would be an artefact of missing reference data."
            ),
        ),
        FieldSpec(
            sheet="DNBS02_PART3",
            rbi_line="Expenses and Profit Before Tax",
            kind=KIND_NO_SOURCE,
            section="part3_expenses",
            no_source_reason=(
                "No reliable GL-head to RBI-line mapping for expense accounts; extgl "
                "classification flags are NULL on all 723 rows and the access-code "
                "prefixes for expense groups (1008/1013/1014/1021/1025) mix expenses, "
                "payables and deposits."
            ),
        ),
        FieldSpec(
            sheet="DNBS02_PART8A",
            rbi_line="Micro / Small / Medium size split",
            kind=KIND_NO_SOURCE,
            section="part8a_msme_size_split",
            no_source_reason=(
                "MSMED classification requires investment in plant and machinery and "
                "turnover; silver.msme_sector_classification_mapping carries only collateral value and LTV."
            ),
        ),
        FieldSpec(
            sheet="DNBS02_Annex10",
            rbi_line="Entity name, PAN, nature, group-company flag",
            kind=KIND_NO_SOURCE,
            section="annex10_investment_entities",
            no_source_reason=(
                "No entity-level investment register; silver.gl_daily_balances carries only "
                "aggregate investment GL heads, with no counterparty name or PAN."
            ),
        ),
        FieldSpec(
            sheet="DNBS02_Annex13",
            rbi_line="City, state and district",
            kind=KIND_NO_SOURCE,
            section="annex13_branch_geography",
            no_source_reason=(
                "silver.branch_master now supplies branch name, address and opening/closing dates, "
                "but mbrn_locn_code has no approved city/state/district reference mapping."
            ),
        ),
    ]
)


def specs_for_sheet(sheet: str) -> List[FieldSpec]:
    return [s for s in FIELD_SPECS if s.sheet == sheet]


def written_specs() -> List[FieldSpec]:
    """Specs that actually put a value in the workbook."""
    return [s for s in FIELD_SPECS if s.kind != KIND_NO_SOURCE]
