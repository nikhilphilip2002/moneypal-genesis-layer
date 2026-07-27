import os
import io
import calendar
import datetime
import logging
from typing import Dict, Any, List, Tuple, Optional
import openpyxl

logger = logging.getLogger(__name__)

# Connection handling and section provenance are shared with the curiosity graph so a
# change to either is made once. Aliased to the private names this module already used.
from app.services.db_schema import (
    get_connection,
    db_cursor as _db_cursor,
    run_section as _run_section,
    SectionResult,
)


class PeriodError(ValueError):
    """The requested reporting period is malformed, or has no data behind it."""


def parse_period_range(frequency: str, period: str) -> Tuple[str, str]:
    """Parse a frequency and period code into (start_date, end_date) ISO strings.

    Raises PeriodError on anything malformed. This used to swallow parse failures and
    return hardcoded 2026 dates, so a typo in the period silently produced a May-2026
    report labelled with whatever the caller had asked for.
    """
    freq = (frequency or "").lower().strip()
    p_str = (period or "").strip()
    if not p_str:
        raise PeriodError("A reporting period is required.")

    if freq == "monthly":
        # Expected: YYYY-MM
        try:
            year_s, month_s = p_str.split("-")
            year, month = int(year_s), int(month_s)
            last_day = calendar.monthrange(year, month)[1]
        except Exception as exc:
            raise PeriodError(
                f"Monthly period must look like 'YYYY-MM' (got {period!r})."
            ) from exc
        return f"{year:04d}-{month:02d}-01", f"{year:04d}-{month:02d}-{last_day:02d}"

    if freq == "quarterly":
        # Expected: YYYY-Qn, where the year is the financial year start (Apr-Mar).
        try:
            year_part, q_part = p_str.split("-")
            year = int(year_part.replace("FY", ""))
            q_part = q_part.upper()
        except Exception as exc:
            raise PeriodError(
                f"Quarterly period must look like 'YYYY-Q1'..'YYYY-Q4' (got {period!r})."
            ) from exc
        fiscal_quarters = {
            "Q1": (f"{year:04d}-04-01", f"{year:04d}-06-30"),
            "Q2": (f"{year:04d}-07-01", f"{year:04d}-09-30"),
            "Q3": (f"{year:04d}-10-01", f"{year:04d}-12-31"),
            # Q4 of FY <year> runs Jan-Mar of the following calendar year.
            "Q4": (f"{year + 1:04d}-01-01", f"{year + 1:04d}-03-31"),
        }
        if q_part not in fiscal_quarters:
            raise PeriodError(
                f"Unknown quarter {q_part!r}; expected Q1, Q2, Q3 or Q4."
            )
        return fiscal_quarters[q_part]

    if freq == "yearly":
        # Expected: YYYY-YYYY (financial year) or a single YYYY.
        try:
            if "-" in p_str:
                start_s, end_s = p_str.split("-")
                start_year, end_year = int(start_s.replace("FY", "")), int(end_s)
                if end_year != start_year + 1:
                    raise PeriodError(
                        f"Financial year {period!r} must span consecutive years "
                        f"(e.g. '{start_year}-{start_year + 1}')."
                    )
            else:
                start_year = int(p_str.replace("FY", ""))
                end_year = start_year + 1
        except PeriodError:
            raise
        except Exception as exc:
            raise PeriodError(
                f"Yearly period must look like 'YYYY-YYYY' or 'YYYY' (got {period!r})."
            ) from exc
        return f"{start_year:04d}-04-01", f"{end_year:04d}-03-31"

    raise PeriodError(
        f"Unknown frequency {frequency!r}; expected 'monthly', 'quarterly' or 'yearly'."
    )


def get_available_snapshot_dates(cur: Any) -> List[str]:
    """Month-end dates for which bronze.genln_rpt_day actually holds a portfolio snapshot."""
    cur.execute(
        "SELECT DISTINCT gnlnr_report_date FROM bronze.genln_rpt_day "
        "WHERE gnlnr_report_date IS NOT NULL ORDER BY gnlnr_report_date"
    )
    return [r[0].isoformat() for r in cur.fetchall()]


def get_available_gl_years(cur: Any) -> List[int]:
    """Financial years for which bronze.glbbal holds a trial balance.

    glbbal is keyed by year only, so Parts 1/3/4 cannot be produced at sub-annual
    granularity from this warehouse.
    """
    cur.execute(
        "SELECT DISTINCT glbbal_year FROM bronze.glbbal "
        "WHERE glbbal_year IS NOT NULL ORDER BY glbbal_year"
    )
    return [int(r[0]) for r in cur.fetchall()]


def resolve_snapshot_date(cur: Any, end_date: str) -> str:
    """Return the snapshot date to report on, or explain why the period is unusable.

    DNBS-02 point-in-time fields are measured as at the period end, so the warehouse must
    hold a snapshot on exactly that date. Silently reporting the nearest earlier snapshot
    would mislabel the return.
    """
    available = get_available_snapshot_dates(cur)
    if not available:
        raise PeriodError("bronze.genln_rpt_day holds no portfolio snapshots at all.")
    if end_date in available:
        return end_date
    raise PeriodError(
        f"No portfolio snapshot exists for period end {end_date}. "
        f"bronze.genln_rpt_day holds month-end snapshots for: {', '.join(available)}."
    )

# ---------------------------------------------------------------------------
# GL classification.
#
# bronze.extgl's own classification flags (extgl_int_income, extgl_operational_exps,
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


def _f(value: Any) -> float:
    """Coerce a DB numeric (Decimal, None) to float."""
    return float(value or 0)


def get_reportable_periods() -> Dict[str, Any]:
    """Periods the warehouse can actually back, so the UI cannot offer unbacked ones.

    The period dropdown used to list fixed options regardless of what the database held;
    picking an unbacked one silently produced fabricated figures.
    """
    with _db_cursor() as (_conn, cur):
        snapshots = get_available_snapshot_dates(cur)
        gl_years = get_available_gl_years(cur)
    monthly = [
        {"value": s[:7], "label": datetime.date.fromisoformat(s).strftime("%B %Y"), "end_date": s}
        for s in snapshots
    ]
    return {
        "monthly": list(reversed(monthly)),
        "snapshot_dates": snapshots,
        "gl_years": gl_years,
        # Quarterly and yearly returns need a period-end snapshot on the quarter/year end.
        "note": (
            "Point-in-time sections require a bronze.genln_rpt_day snapshot dated exactly "
            "on the period end. Parts 1, 3 and 4 come from bronze.glbbal, which is keyed "
            "by year only and therefore cannot be produced at sub-annual granularity."
        ),
    }


def _gl_year_for(end_date: str) -> int:
    """Calendar year used to select a trial balance from bronze.glbbal.

    glbbal is keyed by branch and year only - there is no date dimension - so Parts 1,
    3 and 4 cannot be produced at sub-annual granularity from this warehouse.
    """
    return int(end_date[:4])


def get_dnbs02_report_data(
    frequency: str = "monthly",
    period: str = "",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> Dict[str, Any]:
    """Build the RBI DNBS-02 return from PostgreSQL.

    Every figure is either sourced from the warehouse or left empty. There is no
    fallback data: a section with no feed reports status "no_source" and renders blank,
    because a plausible-looking invented number in a regulatory return is worse than a
    gap.
    """
    if not start_date or not end_date:
        calc_start, calc_end = parse_period_range(frequency, period)
        start_date = start_date or calc_start
        end_date = end_date or calc_end

    try:
        d1 = datetime.datetime.strptime(start_date, "%Y-%m-%d")
        d2 = datetime.datetime.strptime(end_date, "%Y-%m-%d")
    except ValueError as exc:
        raise PeriodError(f"Dates must be ISO YYYY-MM-DD (got {start_date!r}..{end_date!r}).") from exc
    if d2 < d1:
        raise PeriodError(f"Period end {end_date} precedes period start {start_date}.")
    num_days = (d2 - d1).days + 1

    provenance: Dict[str, Dict[str, Any]] = {}
    coverage: Dict[str, Any] = {}
    part1_capital: List[Dict[str, Any]] = []
    part2_loans: List[Dict[str, Any]] = []
    part3_income: List[Dict[str, Any]] = []
    part4_nof: List[Dict[str, Any]] = []
    part6_sensitive: List[Dict[str, Any]] = []
    part8_asset_quality: List[Dict[str, Any]] = []
    part8a_msme: List[Dict[str, Any]] = []
    annex2_shareholders: List[Dict[str, Any]] = []
    annex9_top_borrowers: List[Dict[str, Any]] = []
    annex10_top_investments: List[Dict[str, Any]] = []
    annex11_top_npas: List[Dict[str, Any]] = []
    annex13_branches: List[Dict[str, Any]] = []

    total_loan_book = 0.0
    accrued_interest = 0.0
    provision_held = 0.0
    npa_amount = 0.0
    owned_funds = 0.0
    account_count = 0
    borrower_count = 0

    def no_source(name: str, reason: str) -> None:
        provenance[name] = SectionResult(name, "no_source", 0, reason).as_dict()

    with _db_cursor() as (conn, cur):
        snapshot_date = resolve_snapshot_date(cur, end_date)
        gl_year = _gl_year_for(end_date)
        gl_years = get_available_gl_years(cur)
        gl_available = gl_year in gl_years

        # -- Portfolio summary (as at the snapshot date) ----------------------
        def _summary() -> int:
            nonlocal total_loan_book, accrued_interest, provision_held, account_count, borrower_count
            cur.execute(
                """
                SELECT COUNT(*),
                       COUNT(DISTINCT gnlnr_cust_id),
                       COALESCE(SUM(gnlnr_princ_os), 0) / 100000.0,
                       COALESCE(SUM(gnlnr_int_due), 0) / 100000.0,
                       COALESCE(SUM(gnlnr_provision_amt), 0) / 100000.0
                FROM bronze.genln_rpt_day
                WHERE gnlnr_report_date = CAST(%s AS DATE)
                  AND gnlnr_closed_date IS NULL
                """,
                (snapshot_date,),
            )
            row = cur.fetchone()
            if not row or not row[0]:
                return 0
            account_count = int(row[0])
            borrower_count = int(row[1])
            total_loan_book = round(_f(row[2]), 2)
            accrued_interest = round(_f(row[3]), 2)
            provision_held = round(_f(row[4]), 2)
            return account_count

        _run_section(provenance, "summary", _summary, conn)

        # -- Coverage reconciliation ------------------------------------------
        # bronze.genln_rpt_day is the only table with a genuine as-of dimension, but it
        # does not cover the whole book: it holds product 16 only, so products 1 and 13
        # have no dated snapshot. Falling back to bronze.genlnacnts for those would
        # reintroduce undated balances reported as if they were period-end figures, so
        # the uncovered portion is disclosed instead of silently dropped or back-filled.
        def _coverage() -> int:
            cur.execute(
                """
                SELECT COUNT(*) AS uncovered_accounts,
                       COALESCE(SUM(COALESCE(a.gnlnac_lndisb_amt, a.gnlnac_sanc_amt)
                                    - COALESCE(a.gnlnac_pri_repay_amt, 0)), 0) / 100000.0
                           AS uncovered_lakhs
                FROM bronze.genlnacnts a
                WHERE a.gnlnac_closure_date IS NULL
                  AND NOT EXISTS (
                        SELECT 1 FROM bronze.genln_rpt_day r
                        WHERE r.gnlnr_acnt_num = a.gnlnac_acnt_num
                  )
                """
            )
            row = cur.fetchone()
            coverage["uncovered_accounts"] = int(row[0] or 0)
            coverage["uncovered_lakhs"] = round(_f(row[1]), 2)
            coverage["covered_accounts"] = account_count
            coverage["covered_lakhs"] = total_loan_book
            denom = total_loan_book + coverage["uncovered_lakhs"]
            coverage["covered_pct"] = round(total_loan_book / denom * 100, 2) if denom else 0.0
            return 1

        _run_section(provenance, "coverage", _coverage, conn)
        if coverage.get("uncovered_accounts"):
            logger.warning(
                "DNBS-02 %s: %s open accounts (%.2f lakh) have no dated snapshot in "
                "bronze.genln_rpt_day and are excluded from the return.",
                snapshot_date,
                coverage["uncovered_accounts"],
                coverage["uncovered_lakhs"],
            )

        # -- Part 1: sources of funds, from the GL trial balance --------------
        def _part1() -> int:
            nonlocal owned_funds
            cur.execute(
                """
                SELECT LEFT(g.extgl_access_code, 4) AS gl_group,
                       g.extgl_ext_head_descn,
                       COALESCE(SUM(b.glbbal_bc_bal), 0) / 100000.0 AS amount_lakhs
                FROM bronze.glbbal b
                JOIN bronze.extgl g ON b.glbbal_glacc_code = g.extgl_access_code
                WHERE b.glbbal_year = %s
                  AND LEFT(g.extgl_access_code, 4) IN (%s, %s, %s)
                GROUP BY 1, 2
                HAVING COALESCE(SUM(b.glbbal_bc_bal), 0) <> 0
                ORDER BY 1, 3 DESC
                """,
                (gl_year, GL_SHARE_CAPITAL, GL_RESERVES, GL_BORROWINGS),
            )
            share_capital = reserves = borrowings = 0.0
            for gl_group, descn, amount in cur.fetchall():
                amt = round(_f(amount), 2)
                if gl_group == GL_SHARE_CAPITAL:
                    share_capital += amt
                elif gl_group == GL_RESERVES:
                    reserves += amt
                else:
                    borrowings += amt
                part1_capital.append(
                    {
                        "gl_group": gl_group,
                        "particulars": (descn or "").strip(),
                        "amount_lakhs": amt,
                    }
                )
            owned_funds = round(share_capital + reserves, 2)
            if part1_capital:
                part1_capital.append(
                    {"gl_group": "TOTAL", "particulars": "Share Capital", "amount_lakhs": round(share_capital, 2)}
                )
                part1_capital.append(
                    {"gl_group": "TOTAL", "particulars": "Reserves and Surplus", "amount_lakhs": round(reserves, 2)}
                )
                part1_capital.append(
                    {"gl_group": "TOTAL", "particulars": "Borrowings", "amount_lakhs": round(borrowings, 2)}
                )
                part1_capital.append(
                    {"gl_group": "TOTAL", "particulars": "Owned Funds", "amount_lakhs": owned_funds}
                )
            return len(part1_capital)

        if gl_available:
            _run_section(provenance, "part1_capital", _part1, conn)
        else:
            no_source(
                "part1_capital",
                f"bronze.glbbal has no trial balance for year {gl_year} (available: {gl_years}).",
            )

        # -- Part 2: application of funds -------------------------------------
        def _part2() -> int:
            cur.execute(
                """
                SELECT COALESCE(s.lnschm_schm_name, 'Scheme ' || COALESCE(r.gnlnr_schm_code, 'unmapped'))
                           AS category,
                       COUNT(*) AS account_count,
                       COALESCE(SUM(r.gnlnr_princ_os), 0) / 100000.0 AS amount_lakhs
                FROM bronze.genln_rpt_day r
                LEFT JOIN bronze.nbfclnscheme s
                       ON s.lnschm_schm_code = r.gnlnr_schm_code
                      AND s.lnschm_prod_code = r.gnlnr_prod_code
                WHERE r.gnlnr_report_date = CAST(%s AS DATE)
                  AND r.gnlnr_closed_date IS NULL
                GROUP BY 1
                ORDER BY 3 DESC
                """,
                (snapshot_date,),
            )
            rows = cur.fetchall()
            total = sum(_f(r[2]) for r in rows) or 1.0
            for category, cnt, amount in rows:
                part2_loans.append(
                    {
                        "category": category,
                        "account_count": int(cnt),
                        "amount_lakhs": round(_f(amount), 2),
                        "share_pct": round(_f(amount) / total * 100, 2),
                    }
                )
            return len(part2_loans)

        _run_section(provenance, "part2_loans", _part2, conn)

        # -- Part 2 maturity buckets, from the amortisation schedule ----------
        part2_maturity: List[Dict[str, Any]] = []

        def _part2_maturity() -> int:
            cur.execute(
                """
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
                FROM bronze.genln_rpt_day r
                WHERE r.gnlnr_report_date = CAST(%s AS DATE)
                  AND r.gnlnr_closed_date IS NULL
                GROUP BY 1
                ORDER BY 3 DESC
                """,
                (snapshot_date, snapshot_date, snapshot_date),
            )
            for bucket, cnt, amount in cur.fetchall():
                part2_maturity.append(
                    {"bucket": bucket, "account_count": int(cnt), "amount_lakhs": round(_f(amount), 2)}
                )
            return len(part2_maturity)

        _run_section(provenance, "part2_maturity", _part2_maturity, conn)

        # -- Part 3: income, from the GL trial balance ------------------------
        def _part3() -> int:
            cur.execute(
                """
                SELECT g.extgl_ext_head_descn,
                       COALESCE(SUM(b.glbbal_bc_bal), 0) / 100000.0 AS amount_lakhs
                FROM bronze.glbbal b
                JOIN bronze.extgl g ON b.glbbal_glacc_code = g.extgl_access_code
                WHERE b.glbbal_year = %s
                  AND LEFT(g.extgl_access_code, 4) = %s
                GROUP BY 1
                HAVING COALESCE(SUM(b.glbbal_bc_bal), 0) <> 0
                ORDER BY 2 DESC
                """,
                (gl_year, GL_INCOME),
            )
            for descn, amount in cur.fetchall():
                part3_income.append(
                    {"head": (descn or "").strip(), "amount_lakhs": round(_f(amount), 2)}
                )
            return len(part3_income)

        if gl_available:
            _run_section(provenance, "part3_income", _part3, conn)
        else:
            no_source(
                "part3_income",
                f"bronze.glbbal has no trial balance for year {gl_year} (available: {gl_years}).",
            )

        # Expenses and PBT need a GL-head -> RBI-line mapping that this warehouse does
        # not carry; extgl's expense flags are all NULL and the access-code prefixes for
        # expense groups are ambiguous (1008/1013/1014/1021/1025 mix expenses, payables
        # and deposits). Reporting a derived PBT would mean guessing.
        no_source(
            "part3_expenses",
            "No reliable GL-head to RBI-line mapping for expense accounts; "
            "extgl classification flags are NULL on all rows.",
        )

        # -- Part 4: net owned funds ------------------------------------------
        def _part4() -> int:
            part4_nof.append({"particulars": "Owned Fund (from Part 1)", "amount_lakhs": owned_funds})
            return len(part4_nof)

        if gl_available and owned_funds:
            _run_section(provenance, "part4_nof", _part4, conn)
        else:
            no_source("part4_nof", "Depends on Part 1, which has no trial balance for this period.")

        # -- Part 6: exposure to sensitive sectors ----------------------------
        def _part6() -> int:
            cur.execute(
                """
                SELECT g.extgl_ext_head_descn,
                       ABS(COALESCE(SUM(b.glbbal_bc_bal), 0)) / 100000.0 AS amount_lakhs
                FROM bronze.glbbal b
                JOIN bronze.extgl g ON b.glbbal_glacc_code = g.extgl_access_code
                WHERE b.glbbal_year = %s
                  AND LEFT(g.extgl_access_code, 4) = %s
                GROUP BY 1
                HAVING COALESCE(SUM(b.glbbal_bc_bal), 0) <> 0
                ORDER BY 2 DESC
                """,
                (gl_year, GL_INVESTMENTS),
            )
            for descn, amount in cur.fetchall():
                label = (descn or "").strip()
                upper = label.upper()
                if "PROPPERT" in upper or "PROPERT" in upper:
                    sector = "Real Estate"
                elif "SHARE" in upper or "MUTUAL" in upper:
                    sector = "Capital Market"
                else:
                    sector = "Other"
                part6_sensitive.append(
                    {"sector": sector, "particulars": label, "exposure_lakhs": round(_f(amount), 2)}
                )
            return len(part6_sensitive)

        if gl_available:
            _run_section(provenance, "part6_sensitive", _part6, conn)
        else:
            no_source(
                "part6_sensitive",
                f"bronze.glbbal has no trial balance for year {gl_year} (available: {gl_years}).",
            )

        # -- Part 8 / 8C: asset classification --------------------------------
        def _part8() -> int:
            nonlocal npa_amount
            cur.execute(
                """
                SELECT COALESCE(gnlnr_asset_cd, 'UNCLASSIFIED') AS asset_code,
                       COUNT(*),
                       COALESCE(SUM(gnlnr_princ_os), 0) / 100000.0,
                       COALESCE(SUM(gnlnr_provision_amt), 0) / 100000.0
                FROM bronze.genln_rpt_day
                WHERE gnlnr_report_date = CAST(%s AS DATE)
                  AND gnlnr_closed_date IS NULL
                GROUP BY 1
                ORDER BY 3 DESC
                """,
                (snapshot_date,),
            )
            for asset_code, cnt, amount, provision in cur.fetchall():
                code = (asset_code or "").strip().upper()
                is_npa = code in NPA_ASSET_CODES
                if is_npa:
                    npa_amount += _f(amount)
                part8_asset_quality.append(
                    {
                        "asset_code": code,
                        "status": ASSET_CODE_LABELS.get(code, f"Unmapped asset code ({code})"),
                        "is_npa": is_npa,
                        "count": int(cnt),
                        "amount_lakhs": round(_f(amount), 2),
                        # Provision comes from the ledger, not from an assumed rate.
                        "provision_lakhs": round(_f(provision), 2),
                    }
                )
            npa_amount = round(npa_amount, 2)
            return len(part8_asset_quality)

        _run_section(provenance, "part8_asset_quality", _part8, conn)

        # -- Part 8A: MSME exposure -------------------------------------------
        def _part8a() -> int:
            # Sourced from the loan master rather than the snapshot: nsecmsmemap maps
            # product-13 accounts exclusively, and bronze.genln_rpt_day holds product 16
            # only, so the two sets are disjoint and the snapshot yields no MSME rows.
            #
            # The interest rate comes from bronze.genlnacnts.gnlnac_ln_intrate, which is
            # populated on all 13,344 open accounts and is identical to the snapshot's
            # gnlnr_ln_intrate wherever both exist (4,445 of 4,445 rows at 2026-05-31).
            #
            # Caveat recorded in provenance: genlnacnts has no as-of dimension, so the
            # outstanding amount is a current balance, not a period-end one. Rates and
            # account counts are unaffected by that.
            cur.execute(
                """
                WITH msme_loans AS (
                    SELECT a.gnlnac_acnt_num,
                           a.gnlnac_ln_intrate AS interest_rate,
                           COALESCE(a.gnlnac_lndisb_amt, a.gnlnac_sanc_amt, 0)
                               - COALESCE(a.gnlnac_pri_repay_amt, 0) AS outstanding
                    FROM bronze.genlnacnts a
                    WHERE a.gnlnac_closure_date IS NULL
                      AND a.gnlnac_ln_intrate IS NOT NULL
                      AND EXISTS (
                            SELECT 1 FROM bronze.nsecmsmemap m
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
            )
            row = cur.fetchone()
            if not row or not row[0]:
                return 0
            part8a_msme.append(
                {
                    # MSMED Micro/Small/Medium classification needs investment and
                    # turnover, which this warehouse does not hold. Only the aggregate
                    # MSME exposure and its rate spread are derivable.
                    "category": "Micro, Small and Medium Enterprises (aggregate)",
                    "account_count": int(row[0]),
                    "amount_lakhs": round(_f(row[1]), 2),
                    "min_interest_rate": round(_f(row[2]), 2),
                    "max_interest_rate": round(_f(row[3]), 2),
                    "weighted_avg_interest_rate": round(_f(row[4]), 2),
                }
            )
            return len(part8a_msme)

        _run_section(
            provenance,
            "part8a_msme",
            _part8a,
            conn,
            note=(
                "Sourced from bronze.genlnacnts (rate: gnlnac_ln_intrate) because "
                "nsecmsmemap maps product-13 accounts, which have no dated snapshot. "
                "genlnacnts has no as-of dimension, so the outstanding amount is a "
                "current balance rather than a period-end one."
            ),
        )
        no_source(
            "part8a_msme_size_split",
            "MSMED Micro/Small/Medium classification requires investment in plant and "
            "machinery and turnover; bronze.nsecmsmemap carries only collateral value and LTV.",
        )

        # -- Annex 2: shareholding pattern ------------------------------------
        no_source(
            "annex2_shareholders",
            "No share register in the warehouse (bronze.mig_share_details does not exist).",
        )

        # -- Annex 9: top 25 borrowers ----------------------------------------
        def _annex9() -> int:
            # Aggregated by borrower, not by account: RBI asks for the top 25
            # *borrowers*, and a borrower may hold several loans.
            cur.execute(
                """
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
                       MAX(r.gnlnr_asset_cd)                 AS asset_code
                FROM bronze.genln_rpt_day r
                LEFT JOIN bronze.genlnacnts a ON a.gnlnac_acnt_num = r.gnlnr_acnt_num
                WHERE r.gnlnr_report_date = CAST(%s AS DATE)
                  AND r.gnlnr_closed_date IS NULL
                GROUP BY r.gnlnr_cust_id
                ORDER BY total_outstanding DESC
                LIMIT 25
                """,
                (snapshot_date,),
            )
            for row in cur.fetchall():
                sanctioned = round(_f(row[4]), 2)
                disbursed = round(_f(row[5]), 2)
                code = (row[9] or "").strip().upper()
                annex9_top_borrowers.append(
                    {
                        "cust_id": str(row[0]),
                        "borrower_name": (row[1] or "").strip(),
                        # PAN is carried on the snapshot itself; no need to invent "NA".
                        "pan": row[2] or "",
                        # Legal constitution is not derivable: bronze.firmcifdata_dtl is an
                        # associated-firm detail table, not a corporate register (7,294 of
                        # its 7,594 ids are also individuals).
                        "borrower_type": "",
                        "account_count": int(row[3]),
                        "sanctioned_amt": sanctioned,
                        "disbursed_amt": disbursed,
                        "undisbursed_amt": round(max(sanctioned - disbursed, 0.0), 2),
                        "principal_outstanding": round(_f(row[6]), 2),
                        "accrued_interest": round(_f(row[7]), 2),
                        "account_status": ASSET_CODE_LABELS.get(code, code),
                        "total_outstanding": round(_f(row[8]), 2),
                    }
                )
            return len(annex9_top_borrowers)

        _run_section(provenance, "annex9_top_borrowers", _annex9, conn)

        # -- Annex 10: top 25 investments -------------------------------------
        def _annex10() -> int:
            # Only aggregate GL lines exist. The entity-level detail Annex 10 asks for
            # (name, PAN, nature, group-company flag) has no source, so those fields stay
            # blank rather than being filled with plausible names.
            cur.execute(
                """
                SELECT g.extgl_ext_head_descn,
                       ABS(COALESCE(SUM(b.glbbal_bc_bal), 0)) / 100000.0 AS amount_lakhs
                FROM bronze.glbbal b
                JOIN bronze.extgl g ON b.glbbal_glacc_code = g.extgl_access_code
                WHERE b.glbbal_year = %s
                  AND LEFT(g.extgl_access_code, 4) = %s
                GROUP BY 1
                HAVING COALESCE(SUM(b.glbbal_bc_bal), 0) <> 0
                ORDER BY 2 DESC
                LIMIT 25
                """,
                (gl_year, GL_INVESTMENTS),
            )
            for descn, amount in cur.fetchall():
                label = (descn or "").strip()
                upper = label.upper()
                if "MUTUAL" in upper:
                    inv_type = "MUTUAL FUNDS"
                elif "SHARE" in upper:
                    inv_type = "EQUITY SHARES"
                elif "PROPPERT" in upper or "PROPERT" in upper:
                    inv_type = "IMMOVABLE PROPERTY"
                else:
                    inv_type = ""
                annex10_top_investments.append(
                    {
                        "entity_name": "",
                        "gl_head": label,
                        "nature": "",
                        "investment_type": inv_type,
                        "pan": "",
                        "book_value": round(_f(amount), 2),
                        "is_group_company": "",
                        "amt_outstanding": round(_f(amount), 2),
                    }
                )
            return len(annex10_top_investments)

        if gl_available:
            _run_section(provenance, "annex10_investment_totals", _annex10, conn)
        else:
            no_source(
                "annex10_investment_totals",
                f"bronze.glbbal has no trial balance for year {gl_year} (available: {gl_years}).",
            )
        no_source(
            "annex10_investment_entities",
            "No entity-level investment register in the warehouse; bronze.glbbal carries "
            "only aggregate investment GL heads, with no counterparty name or PAN.",
        )

        # -- Annex 11: top 25 NPA accounts ------------------------------------
        def _annex11() -> int:
            cur.execute(
                """
                SELECT TRIM(r.gnlnr_cust_name),
                       NULLIF(TRIM(r.gnlnr_pan_no), ''),
                       COALESCE(r.gnlnr_princ_os, 0) / 100000.0,
                       COALESCE(r.gnlnr_int_due, 0) / 100000.0,
                       r.gnlnr_asset_cd,
                       r.gnlnr_npa_dt,
                       r.gnlnr_pay_date,
                       COALESCE(a.gnlnac_sanc_amt, 0) / 100000.0
                FROM bronze.genln_rpt_day r
                LEFT JOIN bronze.genlnacnts a ON a.gnlnac_acnt_num = r.gnlnr_acnt_num
                WHERE r.gnlnr_report_date = CAST(%s AS DATE)
                  AND r.gnlnr_closed_date IS NULL
                  AND UPPER(TRIM(COALESCE(r.gnlnr_asset_cd, ''))) = ANY(%s)
                ORDER BY r.gnlnr_princ_os DESC
                LIMIT 25
                """,
                (snapshot_date, list(NPA_ASSET_CODES)),
            )
            for row in cur.fetchall():
                annex11_top_npas.append(
                    {
                        "borrower_name": row[0] or "",
                        "pan": row[1] or "",
                        "borrower_type": "",
                        "principal_os": round(_f(row[2]), 2),
                        "int_due": round(_f(row[3]), 2),
                        "asset_code": (row[4] or "").strip(),
                        "npa_date": row[5].isoformat() if row[5] else "",
                        "last_payment_date": row[6].isoformat() if row[6] else "",
                        "sanctioned_amt": round(_f(row[7]), 2),
                    }
                )
            return len(annex11_top_npas)

        _run_section(provenance, "annex11_top_npas", _annex11, conn)

        # -- Annex 13: branch details -----------------------------------------
        def _annex13() -> int:
            cur.execute(
                """
                SELECT r.gnlnr_brn_code,
                       COUNT(DISTINCT r.gnlnr_cust_id),
                       COUNT(*),
                       COALESCE(SUM(r.gnlnr_princ_os), 0) / 100000.0
                FROM bronze.genln_rpt_day r
                WHERE r.gnlnr_report_date = CAST(%s AS DATE)
                  AND r.gnlnr_closed_date IS NULL
                  AND r.gnlnr_brn_code IS NOT NULL
                GROUP BY 1
                ORDER BY 4 DESC
                """,
                (snapshot_date,),
            )
            for brn_code, customers, accounts, amount in cur.fetchall():
                code = str(int(brn_code))
                annex13_branches.append(
                    {
                        "branch_code": code,
                        # No branch master exists. Address, city, state and district have
                        # no source (cust_intf_pid_dtls geography columns are 100% NULL
                        # and gnlnr_adh_district holds unmapped numeric codes), so they
                        # are left blank rather than invented from a district lookup.
                        "branch_name": f"Branch {code}",
                        "address": "",
                        "city": "",
                        "state": "",
                        "district": "",
                        "customer_count": int(customers),
                        "account_count": int(accounts),
                        "total_outstanding": round(_f(amount), 2),
                    }
                )
            return len(annex13_branches)

        _run_section(provenance, "annex13_branches", _annex13, conn)
        no_source(
            "annex13_branch_geography",
            "No branch master; customer_kyc_details district/state columns are 100% NULL "
            "and gnlnr_adh_district holds numeric codes with no reference table.",
        )

    gross_npa_pct = round(npa_amount / total_loan_book * 100, 2) if total_loan_book else 0.0

    # A section is "live" only if its own query actually ran and returned rows - not
    # merely because the connection opened.
    live_sections = sorted(k for k, v in provenance.items() if v["status"] == "ok")
    degraded_sections = sorted(k for k, v in provenance.items() if v["status"] != "ok")

    return {
        "frequency": frequency,
        "period": period,
        "start_date": start_date,
        "end_date": end_date,
        "snapshot_date": snapshot_date,
        "gl_year": gl_year,
        "duration_days": num_days,
        "generated_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "provenance": provenance,
        "coverage": coverage,
        "live_sections": live_sections,
        "degraded_sections": degraded_sections,
        "is_live_pg": bool(live_sections) and not degraded_sections,
        "summary": {
            "total_loan_book": total_loan_book,
            "accrued_interest": accrued_interest,
            "account_count": account_count,
            "borrower_count": borrower_count,
            "owned_funds": owned_funds,
            "provision_held": provision_held,
            "gross_npa_amount": npa_amount,
            "gross_npa_pct": gross_npa_pct,
            # CRAR needs risk-weighted assets (Part 9), which has no source here. It was
            # previously reported as `24.8 + date_scale_factor * 0.1`.
            "crar_pct": None,
        },
        "part1_capital": part1_capital,
        "part2_loans": part2_loans,
        "part2_maturity": part2_maturity,
        "part3_income": part3_income,
        "part4_nof": part4_nof,
        "part6_sensitive": part6_sensitive,
        "part8_asset_quality": part8_asset_quality,
        "part8a_msme": part8a_msme,
        "annex2_shareholders": annex2_shareholders,
        "annex9_top_borrowers": annex9_top_borrowers,
        "annex10_top_investments": annex10_top_investments,
        "annex11_top_npas": annex11_top_npas,
        "annex13_branches": annex13_branches,
    }


TEMPLATE_FILENAME = "DNBS02_Blank_Template.xlsx"


def get_template_path() -> str:
    """Locate the blank DNBS-02 workbook.

    Only the blank is acceptable. The previous implementation fell back to
    DNBS02_Template.xlsx and then to a source document under docs/, both of which are
    completed filings; any sheet the generator did not overwrite was exported carrying
    the prior filer's data. Regenerate the blank with
    backend/scripts/build_dnbs02_blank_template.py.
    """
    candidates = [
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "assets", TEMPLATE_FILENAME)),
        "/srv/backend/app/assets/" + TEMPLATE_FILENAME,
    ]
    for p in candidates:
        if os.path.exists(p):
            return p
    raise FileNotFoundError(
        f"Blank RBI DNBS-02 template {TEMPLATE_FILENAME!r} not found (searched {candidates}). "
        "Generate it with backend/scripts/build_dnbs02_blank_template.py."
    )


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

    __slots__ = ("sheet", "source_key", "header_row", "first_row", "max_rows", "columns", "serial_column")

    def __init__(
        self,
        sheet: str,
        source_key: str,
        columns: List[TableColumn],
        header_row: int = 12,
        first_row: int = 13,
        max_rows: int = 40,
        serial_column: Optional[str] = None,
    ):
        self.sheet = sheet
        self.source_key = source_key
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


def _find_label_row(sheet, label: str, within: Optional[Tuple[int, int]] = None) -> int:
    """Row whose label column starts with `label`. Must match exactly one row."""
    target = _norm(label)
    lo, hi = within if within else (1, sheet.max_row)
    matches = [
        r
        for r in range(lo, min(hi, sheet.max_row) + 1)
        if _norm(sheet.cell(r, LABEL_COLUMN).value).startswith(target)
    ]
    if len(matches) == 1:
        return matches[0]
    if not matches:
        raise CellMapError(f"{sheet.title}: no row whose label starts with {label!r}")
    raise CellMapError(
        f"{sheet.title}: label {label!r} is ambiguous, matches rows {matches}. "
        "Use a longer fragment or scope it with `within`."
    )


def validate_cell_map(wb) -> None:
    """Check every declared table header exists before writing anything.

    A template whose columns have shifted must fail here rather than silently writing
    outstanding balances into a date column, which is what the old positional writer did
    on Annex 11 and Annex 13.
    """
    problems: List[str] = []

    for block in TABLE_BLOCKS:
        if block.sheet not in wb.sheetnames:
            problems.append(f"{block.sheet}: sheet missing from template")
            continue
        sheet = wb[block.sheet]
        for col in block.columns:
            actual = _norm(sheet[f"{col.column}{block.header_row}"].value)
            if not actual.startswith(_norm(col.header)):
                problems.append(
                    f"{block.sheet}!{col.column}{block.header_row}: expected header "
                    f"{col.header!r} for field {col.field!r}, found {actual!r}"
                )

    if problems:
        raise CellMapError(
            "DNBS-02 template does not match the declared cell map:\n  "
            + "\n  ".join(problems)
        )


DEFAULT_COLUMN_WIDTH = 8.43
DEFAULT_ROW_HEIGHT = 15.0
MAX_ROW_HEIGHT = 220.0


def _effective_width(sheet, cell) -> float:
    """Usable width for a cell, summing the columns it spans if it is merged."""
    from openpyxl.utils import get_column_letter

    first_col, last_col = cell.column, cell.column
    for rng in sheet.merged_cells.ranges:
        if rng.min_row <= cell.row <= rng.max_row and rng.min_col <= cell.column <= rng.max_col:
            first_col, last_col = rng.min_col, rng.max_col
            break
    total = 0.0
    for col in range(first_col, last_col + 1):
        dim = sheet.column_dimensions.get(get_column_letter(col))
        total += (dim.width if dim and dim.width else DEFAULT_COLUMN_WIDTH)
    return max(total, 1.0)


def _fit_row_height(sheet, cell, text: str) -> None:
    """Grow the row so wrapped text is fully visible.

    Turning on wrap_text without adjusting the row height is what made long values
    overlap the rows beneath them: the text rewraps onto several lines but the row stays
    one line tall, so it renders clipped and bleeds over the labels below.
    """
    width = _effective_width(sheet, cell)
    lines = 0
    for paragraph in str(text).split("\n"):
        # ~1.1 characters per width unit at the default font.
        chars_per_line = max(int(width * 1.1), 1)
        lines += max(1, -(-len(paragraph) // chars_per_line))
    needed = min(DEFAULT_ROW_HEIGHT * lines, MAX_ROW_HEIGHT)
    current = sheet.row_dimensions[cell.row].height or DEFAULT_ROW_HEIGHT
    if needed > current:
        sheet.row_dimensions[cell.row].height = needed


def _safe_set_cell_value(sheet, coord: str, value: Any, wrap_text: bool = True) -> None:
    """Write a cell, skipping merged anchors. Raises on anything unexpected."""
    cell = sheet[coord]
    if type(cell).__name__ == "MergedCell":
        logger.warning("DNBS-02: skipped merged cell %s!%s", sheet.title, coord)
        return
    cell.value = value
    if not isinstance(value, str):
        return

    # The cell may already wrap because the template styles it that way - short values in
    # narrow columns (e.g. "SMA-0 (1-30 days)" in Annex 9 column K) rewrap onto two lines
    # without this module touching the alignment. Any wrapped cell needs its row sized,
    # whoever turned the wrapping on.
    wrapped = bool(cell.alignment and cell.alignment.wrap_text)
    if wrap_text and not wrapped and len(value) > 25:
        from openpyxl.styles import Alignment

        cell.alignment = Alignment(wrap_text=True, vertical="top")
        wrapped = True
    if wrapped:
        _fit_row_height(sheet, cell, value)


def _write_line(sheet, item: LineItem, value: Any) -> None:
    row = _find_label_row(sheet, item.label, item.within)
    _safe_set_cell_value(sheet, f"{item.column}{row}", value, wrap_text=False)


def _write_table(wb, data: Dict[str, Any], block: TableBlock) -> int:
    """Write one annexure table. Rows beyond the data are left blank."""
    if block.sheet not in wb.sheetnames:
        return 0
    sheet = wb[block.sheet]
    rows = data.get(block.source_key) or []
    for idx, record in enumerate(rows[: block.max_rows]):
        row_num = block.first_row + idx
        if block.serial_column:
            _safe_set_cell_value(sheet, f"{block.serial_column}{row_num}", idx + 1, wrap_text=False)
        for col in block.columns:
            value = record.get(col.field, "")
            _safe_set_cell_value(sheet, f"{col.column}{row_num}", value)
    return len(rows[: block.max_rows])


def generate_dnbs02_excel(
    frequency: str = "monthly",
    period: str = "",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> bytes:
    """Render the RBI DNBS-02 return into the blank template workbook.

    Only values with a source are written. Sections the warehouse cannot back are left
    blank and listed on the FilingInfo sheet, rather than being filled with fabricated
    figures.
    """
    data = get_dnbs02_report_data(
        frequency=frequency, period=period, start_date=start_date, end_date=end_date
    )

    wb = openpyxl.load_workbook(get_template_path())
    validate_cell_map(wb)

    try:
        end_display = datetime.datetime.strptime(data["end_date"], "%Y-%m-%d").strftime("%d/%m/%Y")
        start_display = datetime.datetime.strptime(data["start_date"], "%Y-%m-%d").strftime("%d/%m/%Y")
        end_upper = datetime.datetime.strptime(data["end_date"], "%Y-%m-%d").strftime("%d-%b-%Y").upper()
    except ValueError:
        start_display, end_display, end_upper = data["start_date"], data["end_date"], data["end_date"]

    # Period-end stamp on every reporting sheet.
    for name in wb.sheetnames:
        if name.startswith("DNBS02_"):
            _safe_set_cell_value(wb[name], "B5", f"Reporting Period End Date :{end_upper}", wrap_text=False)

    # -- FilingInfo, including an explicit statement of what has no source ----
    if "FilingInfo" in wb.sheetnames:
        sheet = wb["FilingInfo"]
        _safe_set_cell_value(sheet, "B2", f"Period: {data['start_date']} to {data['end_date']} ({data['frequency']})")
        _safe_set_cell_value(sheet, "B3", f"Generated: {data['generated_at']}")
        _safe_set_cell_value(sheet, "C11", data["frequency"].capitalize())
        _safe_set_cell_value(sheet, "C12", start_display)
        _safe_set_cell_value(sheet, "C13", end_display)
        _safe_set_cell_value(sheet, "C15", "LAKHS")

        # The disclosures go in the value column of the template's own "General remarks"
        # row. They previously went into B18/B19/B20, which are inside the sheet's
        # label column and sit directly above the "General remarks" and "Scoping
        # Question" labels, so the text overlapped them.
        remarks = [
            f"Portfolio snapshot date: {data['snapshot_date']}; "
            f"GL trial balance year: {data['gl_year']}."
        ]
        coverage = data.get("coverage") or {}
        if coverage.get("uncovered_accounts"):
            remarks.append(
                f"Coverage: {coverage['covered_accounts']} accounts "
                f"({coverage['covered_lakhs']} lakh, {coverage['covered_pct']}% of the open "
                f"book). {coverage['uncovered_accounts']} open accounts "
                f"({coverage['uncovered_lakhs']} lakh) have no dated snapshot and are excluded."
            )
        if data.get("degraded_sections"):
            remarks.append(
                "Sections left blank (no source): " + ", ".join(data["degraded_sections"])
            )
        try:
            remarks_row = _find_label_row(sheet, "General remarks")
            _safe_set_cell_value(sheet, f"C{remarks_row}", "\n".join(remarks))
        except CellMapError:
            logger.warning("FilingInfo has no 'General remarks' row; disclosures omitted")

    # -- Part 1: sources of funds -------------------------------------------
    if "DNBS02_PART1" in wb.sheetnames and data.get("part1_capital"):
        sheet = wb["DNBS02_PART1"]
        by_line: Dict[str, float] = {}
        share_capital = reserves = 0.0
        for row in data["part1_capital"]:
            if row["gl_group"] == "TOTAL":
                if row["particulars"] == "Share Capital":
                    share_capital = row["amount_lakhs"]
                elif row["particulars"] == "Reserves and Surplus":
                    reserves = row["amount_lakhs"]
                continue
            target = GL_DESC_TO_PART1_LINE.get(row["particulars"].upper())
            if target:
                by_line[target] = round(by_line.get(target, 0.0) + row["amount_lakhs"], 2)
            else:
                logger.info("DNBS-02 Part 1: GL head %r has no RBI line mapping", row["particulars"])
        for label, amount in by_line.items():
            _write_line(sheet, LineItem("DNBS02_PART1", label, "C"), amount)
        _write_line(sheet, LineItem("DNBS02_PART1", "2 Share Capital", "C"), share_capital)
        _write_line(sheet, LineItem("DNBS02_PART1", "3 Reserves and Surplus", "C"), reserves)

    # -- Part 2: application of funds ---------------------------------------
    if "DNBS02_PART2" in wb.sheetnames:
        sheet = wb["DNBS02_PART2"]
        _write_line(
            sheet, LineItem("DNBS02_PART2", "1 Loans & Advances", "C"), data["summary"]["total_loan_book"]
        )
        # The secured/unsecured split is deliberately not written: the scheme master marks
        # every scheme unsecured but covers product 16 only, so the split has no source.
        maturity_lines = {
            "Receivable within 3 months": "(a) Of Total Loans",
            "Receivable in 3 to 12 months": "(b) Of Total Loans",
            "Receivable after 12 months": "(c ) Of Total Loans",
        }
        for bucket in data.get("part2_maturity", []):
            label = maturity_lines.get(bucket["bucket"])
            if label:
                _write_line(sheet, LineItem("DNBS02_PART2", label, "C"), bucket["amount_lakhs"])

    # -- Part 3: income ------------------------------------------------------
    if "DNBS02_PART3" in wb.sheetnames and data.get("part3_income"):
        sheet = wb["DNBS02_PART3"]
        by_line: Dict[str, float] = {}
        for row in data["part3_income"]:
            target = GL_DESC_TO_PART3_LINE.get(row["head"].upper())
            if target:
                by_line[target] = round(by_line.get(target, 0.0) + row["amount_lakhs"], 2)
            else:
                logger.info("DNBS-02 Part 3: GL head %r has no RBI line mapping", row["head"])
        for label, amount in by_line.items():
            scope = PART3_INVESTMENT_SCOPE if label in ("(a) Interest", "(b) Dividends") else None
            _write_line(sheet, LineItem("DNBS02_PART3", label, "C", scope), amount)

    # -- Part 4: net owned funds --------------------------------------------
    if "DNBS02_PART4" in wb.sheetnames and data.get("part4_nof"):
        sheet = wb["DNBS02_PART4"]
        _write_line(
            sheet,
            LineItem("DNBS02_PART4", "Owned Fund (from Part 1)", "C"),
            data["summary"]["owned_funds"],
        )

    # -- Part 8C: asset classification --------------------------------------
    if "DNBS02_PART8C" in wb.sheetnames and data.get("part8_asset_quality"):
        sheet = wb["DNBS02_PART8C"]
        buckets = {"standard": 0.0, "sub": 0.0, "doubtful": 0.0, "loss": 0.0}
        provisions = dict(buckets)
        for row in data["part8_asset_quality"]:
            code = row["asset_code"]
            if code in ("STD", "SMA0", "SMA1", "SMA2"):
                key = "standard"
            elif code in ("SUB", "NPA"):
                key = "sub"
            elif code in ("DBT", "D1", "D2", "D3"):
                key = "doubtful"
            elif code == "LOSS":
                key = "loss"
            else:
                logger.warning("DNBS-02 Part 8C: unmapped asset code %r", code)
                continue
            buckets[key] += row["amount_lakhs"]
            provisions[key] += row["provision_lakhs"]
        for key, label in ASSET_CLASS_TO_PART8C_LINE.items():
            _write_line(sheet, LineItem("DNBS02_PART8C", label, "C"), round(buckets[key], 2))
            _write_line(sheet, LineItem("DNBS02_PART8C", label, "D"), round(provisions[key], 2))
        gross = round(sum(buckets.values()), 2)
        _write_line(sheet, LineItem("DNBS02_PART8C", "2 Gross Credit Exposure", "C"), gross)
        _write_line(sheet, LineItem("DNBS02_PART8C", "2 Gross Credit Exposure", "D"), round(sum(provisions.values()), 2))
        _write_line(sheet, LineItem("DNBS02_PART8C", "3 Total NPAs", "C"), data["summary"]["gross_npa_amount"])
        _write_line(sheet, LineItem("DNBS02_PART8C", "4 Gr. NPA (%)", "C"), data["summary"]["gross_npa_pct"])

    # -- Part 8A: MSME exposure ---------------------------------------------
    if "DNBS02_PART8A" in wb.sheetnames and data.get("part8a_msme"):
        sheet = wb["DNBS02_PART8A"]
        msme = data["part8a_msme"][0]
        for label in ("A Micro, Small and Medium Enterprises", "A.1 Direct Exposure"):
            _write_line(sheet, LineItem("DNBS02_PART8A", label, "C"), msme["account_count"])
            _write_line(sheet, LineItem("DNBS02_PART8A", label, "D"), msme["amount_lakhs"])
        # Columns G/H/I are Min / Max / Weighted Average - the old writer put a single
        # average into G, the "Min" column.
        _write_line(sheet, LineItem("DNBS02_PART8A", "A.1 Direct Exposure", "G"), msme["min_interest_rate"])
        _write_line(sheet, LineItem("DNBS02_PART8A", "A.1 Direct Exposure", "H"), msme["max_interest_rate"])
        _write_line(
            sheet,
            LineItem("DNBS02_PART8A", "A.1 Direct Exposure", "I"),
            msme["weighted_avg_interest_rate"],
        )

    # -- Annexure tables -----------------------------------------------------
    for block in TABLE_BLOCKS:
        written = _write_table(wb, data, block)
        logger.debug("DNBS-02 %s: wrote %d rows", block.sheet, written)

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf.getvalue()
