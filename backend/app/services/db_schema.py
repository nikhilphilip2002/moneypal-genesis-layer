"""Enterprise Information Graph - a navigable view of the loan book in PostgreSQL.

Portfolio nodes and edges are derived from semantic `silver` tables. Where the warehouse
has no source for something (branch geography, for instance) the field is omitted rather
than filled with a plausible-looking placeholder.
"""

import contextlib
import logging
import os
from typing import Any, Callable, Dict, Generator, List, Optional, Sequence, Tuple

logger = logging.getLogger(__name__)

# psycopg2 is the deployment driver (see backend/Dockerfile). pg8000 is a pure-Python
# fallback for environments where psycopg2's compiled extension cannot load (e.g. NixOS,
# where it fails on libz). Both expose the DB-API "format" paramstyle, so the %s
# placeholders used throughout this package work unchanged on either.
try:
    import psycopg2 as _driver
except ImportError:
    try:
        import pg8000.dbapi as _driver
    except ImportError:
        _driver = None

psycopg2 = _driver

NODE_TYPE_STYLES = {
    "executive": {"color": "#4c1d95", "label": "Portfolio Master", "size": 32},
    "zonal": {"color": "#6d28d9", "label": "Product Division", "size": 28},
    "manager": {"color": "#4338ca", "label": "Branch", "size": 24},
    "agent": {"color": "#0284c7", "label": "Lending Scheme", "size": 20},
    "customer": {"color": "#0f766e", "label": "Borrower", "size": 18},
    "account": {"color": "#075fac", "label": "Loan Account", "size": 18},
    "disbursement": {"color": "#ea580c", "label": "Disbursement", "size": 14},
    "repayment": {"color": "#10b981", "label": "Repayment", "size": 14},
}

# Product codes present in silver.loan_account_master. Names come from the client's product
# taxonomy (see docs/PROSPER_EDA_REPORT.md section 2A); anything else shows its bare code.
PRODUCT_NAMES = {
    "1": "Gold Loans",
    "13": "Microfinance / Retail EMI",
    "16": "Business & MSME Loans",
}

# July Oracle keeps the current product-16 book in GENLNACNTS and the unchanged
# product-1/product-13 run-off book in GENLNACNTS_29102024. Account-level reconciliation
# against the June dump proved all 7,855 legacy accounts match exactly. The graph uses
# both sources without treating the dated archive as current operational activity.
LOAN_PORTFOLIO_SQL = """(
    SELECT live.*
    FROM silver.loan_account_master live
    UNION ALL
    SELECT legacy.*
    FROM silver.general_loan_accounts_oct_2024 legacy
    WHERE legacy.gnlnac_prod_code IN (1, 13)
)"""


def get_connection():
    if _driver is None:
        raise RuntimeError(
            "No PostgreSQL driver available. Install psycopg2-binary (preferred) or pg8000."
        )
    host = os.environ.get("POSTGRES_HOST", "192.168.1.183")

    if host.startswith("http://"):
        host = host[7:]
    if host.endswith("/"):
        host = host[:-1]

    port = int(os.environ.get("POSTGRES_PORT", "5432"))
    dbname = os.environ.get("POSTGRES_DB", "moneypaldb")
    user = os.environ.get("POSTGRES_USER", "moneypal")
    password = os.environ.get("POSTGRES_PASSWORD", "moneypal123")

    kwargs: Dict[str, Any] = {
        "host": host,
        "port": port,
        "database": dbname,
        "user": user,
        "password": password,
    }
    # The two drivers spell the connect timeout differently.
    kwargs["connect_timeout" if _driver.__name__.startswith("psycopg2") else "timeout"] = 3
    return _driver.connect(**kwargs)


@contextlib.contextmanager
def db_cursor() -> Generator[Tuple[Any, Any], None, None]:
    """Yield (connection, cursor), guaranteeing the connection is closed even on error."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        try:
            yield conn, cur
        finally:
            with contextlib.suppress(Exception):
                cur.close()
    finally:
        with contextlib.suppress(Exception):
            conn.close()


class SectionResult:
    """Outcome of one query, so a failure is never mistaken for an empty result.

    `status` is one of "ok", "empty", "error", "no_source".
    """

    __slots__ = ("name", "status", "rows", "error", "note")

    def __init__(self, name: str, status: str, rows: int = 0, error: str = "", note: str = ""):
        self.name = name
        self.status = status
        self.rows = rows
        self.error = error
        self.note = note

    def as_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {"status": self.status, "row_count": self.rows}
        if self.error:
            d["error"] = self.error
        if self.note:
            d["note"] = self.note
        return d


def run_section(
    provenance: Dict[str, Dict[str, Any]],
    name: str,
    fn: Callable[[], int],
    conn: Any = None,
    note: str = "",
) -> None:
    """Run one loader, recording why it produced nothing rather than swallowing it."""
    try:
        count = fn()
        provenance[name] = SectionResult(
            # Preserve caveats for an empty result as well: an auditor still needs to
            # know why a valid query produced a blank regulatory section.
            name, "ok" if count else "empty", count, note=note
        ).as_dict()
    except Exception as exc:  # noqa: BLE001 - one bad section must not kill the graph
        logger.exception("Information graph section %r failed", name)
        if conn is not None:
            with contextlib.suppress(Exception):
                conn.rollback()
        provenance[name] = SectionResult(name, "error", 0, f"{type(exc).__name__}: {exc}").as_dict()


def _f(value: Any) -> float:
    return float(value or 0)


def _code(raw: Any) -> str:
    """Normalise a numeric code that may arrive as 4, '4', 4.0 or Decimal('4')."""
    if raw is None:
        return ""
    s = str(raw).strip()
    if s.endswith(".0"):
        s = s[:-2]
    return s


def branch_label(raw_code: Any, names: Optional[Dict[str, str]] = None) -> str:
    """Identify a branch from the migrated branch master, falling back to its code."""
    code = _code(raw_code)
    if code and names and names.get(code):
        return f"{names[code]} (Branch {code})"
    return f"Branch {code}" if code else "Unassigned Branch"


def get_branch_name_map(cur) -> Dict[str, str]:
    cur.execute(
        "SELECT mbrn_code, mbrn_name FROM silver.branch_master "
        "WHERE mbrn_code IS NOT NULL AND NULLIF(BTRIM(mbrn_name), '') IS NOT NULL"
    )
    return {_code(code): str(name).strip() for code, name in cur.fetchall()}


def get_scheme_name_map(cur) -> Dict[str, str]:
    """Real scheme names from bronze.nbfclnscheme, keyed by scheme code.

    Only 15 schemes (all product 16) have a master row; 45 further codes are in use
    without one. Those keep their bare code rather than being given an invented
    category name.
    """
    cur.execute(
        "SELECT lnschm_schm_code, lnschm_schm_name FROM bronze.nbfclnscheme "
        "WHERE lnschm_schm_code IS NOT NULL"
    )
    return {str(c).strip(): (n or "").strip() for c, n in cur.fetchall() if (n or "").strip()}


def scheme_title(code: Any, name_map: Dict[str, str]) -> str:
    c = _code(code)
    if not c:
        return "Unassigned Scheme"
    name = name_map.get(c)
    return f"{name} (Scheme #{c})" if name else f"Scheme #{c}"


def product_title(code: Any) -> str:
    c = _code(code)
    name = PRODUCT_NAMES.get(c)
    return f"Product {c}: {name}" if name else f"Product {c}"


def _repaid_pct(repaid: float, disbursed: float) -> float:
    """Cumulative principal repaid as a share of principal disbursed.

    Deliberately *not* called collection efficiency: it compares repayments to the whole
    disbursed book rather than to the amount actually due, so a young loan looks like a
    default. True collection efficiency comes from bronze.loanrepay (due vs paid) - see
    get_collection_efficiency.
    """
    return round(repaid / disbursed * 100, 1) if disbursed else 0.0


def get_collection_efficiency(cur, account_nums: Optional[Sequence[Any]] = None) -> Dict[str, Any]:
    """True collection efficiency: instalments paid over instalments due.

    bronze.loanrepay carries both sides - lnrepay_prin_amt / lnrepay_int_amt are amounts
    due, lnrepay_prin_pdamt / lnrepay_int_pdamt are amounts actually received.
    """
    sql = """
        SELECT COALESCE(SUM(lnrepay_prin_amt + lnrepay_int_amt), 0) AS due,
               COALESCE(SUM(lnrepay_prin_pdamt + lnrepay_int_pdamt), 0) AS paid,
               COUNT(*)
        FROM bronze.loanrepay
    """
    params: Tuple[Any, ...] = ()
    if account_nums:
        sql += " WHERE lnrepay_acnt_no = ANY(%s)"
        params = (list(account_nums),)
    cur.execute(sql, params)
    due, paid, n = cur.fetchone()
    due_f, paid_f = _f(due), _f(paid)
    return {
        "instalments": int(n or 0),
        "amount_due": round(due_f, 2),
        "amount_paid": round(paid_f, 2),
        "efficiency_pct": round(paid_f / due_f * 100, 1) if due_f else 0.0,
    }


# --------------------------------------------------------------------------- #
# Search
# --------------------------------------------------------------------------- #

def search_entities(query_str: str, entity_type: str = "all") -> List[Dict[str, Any]]:
    """Find products, branches and borrowers.

    Codes are matched exactly. They used to be matched with LIKE '%term%', so searching
    branch "1" returned 15 branches and 7,943 accounts instead of one branch and 7,803,
    and searching product "1" returned products 1, 13 and 16. Names still match on
    substring, which is what a name search should do.
    """
    results: List[Dict[str, Any]] = []
    term = (query_str or "").strip()
    if not term:
        return results

    like = f"%{term.lower()}%"
    is_numeric = term.isdigit()

    try:
        with db_cursor() as (conn, cur):
            branch_names = get_branch_name_map(cur)
            if is_numeric and entity_type in ("all", "zonal"):
                cur.execute(
                    f"""
                    SELECT gnlnac_prod_code, COUNT(DISTINCT gnlnac_cust_id), COUNT(*)
                    FROM {LOAN_PORTFOLIO_SQL} portfolio
                    WHERE CAST(gnlnac_prod_code AS TEXT) = %s
                    GROUP BY gnlnac_prod_code
                    """,
                    (term,),
                )
                for prod, custs, accts in cur.fetchall():
                    code = _code(prod)
                    results.append(
                        {
                            "id": f"ZONE-PROD-{code}",
                            "title": product_title(code),
                            "subtitle": f"{custs:,} Borrowers • {accts:,} Loans",
                            "type": "zonal",
                            "view_level": "zonal",
                            "zonal_id": f"ZONE-PROD-{code}",
                        }
                    )

            if is_numeric and entity_type in ("all", "manager"):
                cur.execute(
                    f"""
                    SELECT gnlnac_appl_brn_code, COUNT(DISTINCT gnlnac_cust_id), COUNT(*)
                    FROM {LOAN_PORTFOLIO_SQL} portfolio
                    WHERE CAST(gnlnac_appl_brn_code AS TEXT) = %s
                    GROUP BY gnlnac_appl_brn_code
                    """,
                    (term,),
                )
                for brn, custs, accts in cur.fetchall():
                    code = _code(brn)
                    results.append(
                        {
                            "id": f"BRN-{code}",
                            "title": branch_label(code, branch_names),
                            "subtitle": f"{custs:,} Borrowers • {accts:,} Loans",
                            "type": "manager",
                            "view_level": "manager",
                            "manager_id": f"BRN-{code}",
                        }
                    )

            if entity_type in ("all", "customer"):
                # Borrower names come from the loan master directly. The customer master
                # CIF is deliberately not used for the display name: the graph represents
                # loan borrowers and the loan master carries the account's customer name.
                cur.execute(
                    f"""
                    SELECT g.gnlnac_cust_id,
                           MAX(TRIM(g.gnlnac_cust_name)) AS borrower_name,
                           COUNT(*) AS account_count,
                           COALESCE(SUM(COALESCE(NULLIF(g.gnlnac_lndisb_amt, 0),
                                                 g.gnlnac_sanc_amt)), 0) AS disbursed,
                           MAX(g.gnlnac_appl_brn_code) AS brn_code
                    FROM {LOAN_PORTFOLIO_SQL} g
                    WHERE LOWER(TRIM(g.gnlnac_cust_name)) LIKE %s
                       OR CAST(g.gnlnac_cust_id AS TEXT) = %s
                       OR CAST(g.gnlnac_acnt_num AS TEXT) = %s
                    GROUP BY g.gnlnac_cust_id
                    ORDER BY disbursed DESC
                    LIMIT 12
                    """,
                    (like, term, term),
                )
                for cust_id, name, accts, disbursed, brn in cur.fetchall():
                    results.append(
                        {
                            "id": f"CUST-{cust_id}",
                            "title": (name or f"Borrower #{cust_id}").strip(),
                            "subtitle": (
                                f"Customer #{cust_id} • {accts} account(s) • "
                                f"{branch_label(brn, branch_names)}"
                            ),
                            "type": "customer",
                            "view_level": "customer",
                            "customer_id": _code(cust_id),
                        }
                    )
    except Exception:
        logger.exception("Information graph search failed for %r", query_str)
        return []

    return results[:15]


# --------------------------------------------------------------------------- #
# Monthly aggregates
# --------------------------------------------------------------------------- #

def get_monthly_breakdown(selected_month: Optional[str] = None) -> Dict[str, Any]:
    """Monthly sanction / disbursement / repayment aggregates.

    Returns an empty series if the query fails rather than a fabricated one - this used to
    fall back to nine months of invented figures on any error.
    """
    monthly_series: List[Dict[str, Any]] = []
    provenance: Dict[str, Dict[str, Any]] = {}

    def _load() -> int:
        cur.execute(
            f"""
            SELECT TO_CHAR(gnlnac_sanc_date, 'YYYY-MM') AS month_str,
                   COUNT(*),
                   COUNT(DISTINCT gnlnac_cust_id),
                   COALESCE(SUM(gnlnac_sanc_amt), 0),
                   COALESCE(SUM(COALESCE(NULLIF(gnlnac_lndisb_amt, 0), gnlnac_sanc_amt)), 0),
                   COALESCE(SUM(gnlnac_pri_repay_amt), 0),
                   COUNT(*) FILTER (WHERE gnlnac_prod_code = 16),
                   COUNT(*) FILTER (WHERE gnlnac_prod_code = 13),
                   COUNT(*) FILTER (WHERE gnlnac_prod_code = 1)
            FROM {LOAN_PORTFOLIO_SQL} portfolio
            WHERE gnlnac_sanc_date IS NOT NULL
            GROUP BY 1
            ORDER BY 1 DESC
            """
        )
        for row in cur.fetchall():
            disbursed = _f(row[4])
            repaid = _f(row[5])
            monthly_series.append(
                {
                    "month": str(row[0]),
                    "loan_count": int(row[1]),
                    "cust_count": int(row[2]),
                    "total_sanctioned": _f(row[3]),
                    "total_disbursed": disbursed,
                    "total_repaid": repaid,
                    "msme_count": int(row[6]),
                    "mfi_count": int(row[7]),
                    "gold_count": int(row[8]),
                    "principal_repaid_pct": _repaid_pct(repaid, disbursed),
                }
            )
        return len(monthly_series)

    try:
        with db_cursor() as (conn, cur):
            run_section(provenance, "monthly_series", _load, conn)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Monthly breakdown unavailable")
        provenance["monthly_series"] = SectionResult(
            "monthly_series", "error", 0, f"{type(exc).__name__}: {exc}"
        ).as_dict()

    selected_metrics = None
    if monthly_series:
        selected_metrics = next(
            (m for m in monthly_series if m["month"] == selected_month), monthly_series[0]
        )

    return {
        "monthly_series": monthly_series,
        "selected_month": selected_month or (monthly_series[0]["month"] if monthly_series else None),
        "selected_metrics": selected_metrics,
        "total_months": len(monthly_series),
        "provenance": provenance,
    }


def get_mom_loan_start_analysis() -> Dict[str, Any]:
    """Month-on-month origination cohorts by sanction date.

    The rate column is silver.loan_account_master.gnlnac_ln_intrate. This function used to
    reference gnlnac_int_rate, which does not exist, so the query threw on every run and
    the whole result came from a hardcoded nine-month series.
    """
    monthly_cohorts: List[Dict[str, Any]] = []
    provenance: Dict[str, Dict[str, Any]] = {}

    def _load() -> int:
        cur.execute(
            f"""
            SELECT TO_CHAR(gnlnac_sanc_date, 'YYYY-MM') AS start_month,
                   COUNT(*),
                   COUNT(DISTINCT gnlnac_cust_id),
                   COALESCE(SUM(gnlnac_sanc_amt), 0),
                   COALESCE(SUM(COALESCE(NULLIF(gnlnac_lndisb_amt, 0), gnlnac_sanc_amt)), 0),
                   COALESCE(SUM(gnlnac_pri_repay_amt), 0),
                   AVG(gnlnac_ln_intrate),
                   AVG(gnlnac_sanc_amt)
            FROM {LOAN_PORTFOLIO_SQL} portfolio
            WHERE gnlnac_sanc_date IS NOT NULL
            GROUP BY 1
            ORDER BY 1 ASC
            """
        )
        prev_volume: Optional[float] = None
        for row in cur.fetchall():
            sanctioned = _f(row[3])
            disbursed = _f(row[4])
            repaid = _f(row[5])
            growth = (
                round((sanctioned - prev_volume) / prev_volume * 100, 1)
                if prev_volume
                else None
            )
            prev_volume = sanctioned
            monthly_cohorts.append(
                {
                    "start_month": str(row[0]),
                    "loans_started": int(row[1]),
                    "borrowers_onboarded": int(row[2]),
                    "volume_sanctioned": sanctioned,
                    "volume_disbursed": disbursed,
                    "volume_repaid": repaid,
                    # Real average rate, no 17.7 default.
                    "avg_interest_rate": round(_f(row[6]), 2) if row[6] is not None else None,
                    "avg_ticket_size": round(_f(row[7]), 2),
                    # None for the first cohort: there is no prior month to grow from.
                    "mom_growth_pct": growth,
                    "principal_repaid_pct": _repaid_pct(repaid, disbursed),
                }
            )
        return len(monthly_cohorts)

    try:
        with db_cursor() as (conn, cur):
            run_section(provenance, "monthly_cohorts", _load, conn)
    except Exception as exc:  # noqa: BLE001
        logger.exception("MoM loan start analysis unavailable")
        provenance["monthly_cohorts"] = SectionResult(
            "monthly_cohorts", "error", 0, f"{type(exc).__name__}: {exc}"
        ).as_dict()

    first = monthly_cohorts[0] if monthly_cohorts else None
    latest = monthly_cohorts[-1] if monthly_cohorts else None
    growths = [c["mom_growth_pct"] for c in monthly_cohorts if c["mom_growth_pct"] is not None]

    return {
        "monthly_cohorts": list(reversed(monthly_cohorts)),
        "institution_improvement": {
            "start_period": first["start_month"] if first else None,
            "latest_period": latest["start_month"] if latest else None,
            "origination_growth_multiplier": (
                round(latest["volume_sanctioned"] / first["volume_sanctioned"], 1)
                if first and latest and first["volume_sanctioned"]
                else None
            ),
            "average_mom_growth_pct": round(sum(growths) / len(growths), 1) if growths else None,
            "total_new_volume_started": sum(c["volume_sanctioned"] for c in monthly_cohorts),
        },
        "provenance": provenance,
    }


# --------------------------------------------------------------------------- #
# Graph
# --------------------------------------------------------------------------- #

def _money(value: float) -> str:
    return f"₹{value:,.0f}"


def get_db_schema_graph(
    search_term: Optional[str] = None,
    entity_type: Optional[str] = "all",
    view_level: Optional[str] = "executive",
    zonal_id: Optional[str] = None,
    manager_id: Optional[str] = None,
    agent_id: Optional[str] = None,
    customer_id: Optional[str] = None,
    month: Optional[str] = None,
    limit: int = 40,
) -> Dict[str, Any]:
    """Build the information graph for the requested drill-down level."""
    nodes: List[Dict[str, Any]] = []
    edges: List[Dict[str, Any]] = []
    provenance: Dict[str, Dict[str, Any]] = {}

    products: List[Dict[str, Any]] = []
    branches: List[Dict[str, Any]] = []
    branch_product_links: List[Dict[str, Any]] = []
    scheme_names: Dict[str, str] = {}

    totals = {
        "loan_borrowers": 0,
        "active_loan_borrowers": 0,
        "registered_customers": 0,
        "accounts": 0,
        "disbursed": 0.0,
        "repaid": 0.0,
    }

    executive_info = {
        "id": "EXEC-PORTFOLIO",
        "name": "GICC Loanbook",
        # The module reads PostgreSQL; it previously described itself as Oracle.
        "role": "PostgreSQL warehouse (schema: silver)",
        "org": "Moneypal GICC Holdings Ltd",
    }

    month_filter = "WHERE TO_CHAR(gnlnac_sanc_date, 'YYYY-MM') = %s" if month else ""
    month_params: Tuple[Any, ...] = (month,) if month else ()

    with db_cursor() as (conn, cur):

        branch_names = get_branch_name_map(cur)

        def _totals() -> int:
            cur.execute(
                f"""
                SELECT COUNT(*), COUNT(DISTINCT gnlnac_cust_id),
                       COALESCE(SUM(COALESCE(NULLIF(gnlnac_lndisb_amt, 0), gnlnac_sanc_amt)), 0),
                       COALESCE(SUM(gnlnac_pri_repay_amt), 0)
                FROM {LOAN_PORTFOLIO_SQL} portfolio {month_filter}
                """,
                month_params,
            )
            row = cur.fetchone()
            totals["accounts"] = int(row[0] or 0)
            totals["loan_borrowers"] = int(row[1] or 0)
            totals["disbursed"] = _f(row[2])
            totals["repaid"] = _f(row[3])
            cur.execute(
                "SELECT COUNT(DISTINCT gnlnac_cust_id) FROM silver.loan_account_master"
            )
            totals["active_loan_borrowers"] = int(cur.fetchone()[0] or 0)
            cur.execute(
                "SELECT COUNT(DISTINCT cifdata_cust_id) "
                "FROM silver.customer_information_file_master"
            )
            totals["registered_customers"] = int(cur.fetchone()[0] or 0)
            return totals["accounts"]

        run_section(provenance, "portfolio_totals", _totals, conn)

        def _products() -> int:
            cur.execute(
                f"""
                SELECT gnlnac_prod_code, COUNT(DISTINCT gnlnac_cust_id), COUNT(*),
                       COALESCE(SUM(COALESCE(NULLIF(gnlnac_lndisb_amt, 0), gnlnac_sanc_amt)), 0),
                       COALESCE(SUM(gnlnac_pri_repay_amt), 0)
                FROM {LOAN_PORTFOLIO_SQL} portfolio
                {month_filter or 'WHERE TRUE'} AND gnlnac_prod_code IS NOT NULL
                GROUP BY gnlnac_prod_code
                ORDER BY 2 DESC
                """,
                month_params,
            )
            for prod, custs, accts, disbursed, repaid in cur.fetchall():
                code = _code(prod)
                products.append(
                    {
                        "id": f"ZONE-PROD-{code}",
                        "code": code,
                        "name": product_title(code),
                        "cust_count": int(custs or 0),
                        "acnt_count": int(accts or 0),
                        "total_vol": _f(disbursed),
                        "repay_vol": _f(repaid),
                        "repaid_pct": _repaid_pct(_f(repaid), _f(disbursed)),
                    }
                )
            return len(products)

        run_section(provenance, "products", _products, conn)

        def _branches() -> int:
            cur.execute(
                f"""
                SELECT gnlnac_appl_brn_code, COUNT(DISTINCT gnlnac_cust_id), COUNT(*),
                       COALESCE(SUM(COALESCE(NULLIF(gnlnac_lndisb_amt, 0), gnlnac_sanc_amt)), 0),
                       COALESCE(SUM(gnlnac_pri_repay_amt), 0)
                FROM {LOAN_PORTFOLIO_SQL} portfolio
                {month_filter or 'WHERE TRUE'} AND gnlnac_appl_brn_code IS NOT NULL
                GROUP BY gnlnac_appl_brn_code
                ORDER BY 2 DESC
                """,
                month_params,
            )
            for brn, custs, accts, disbursed, repaid in cur.fetchall():
                code = _code(brn)
                branches.append(
                    {
                        "id": f"BRN-{code}",
                        "code": code,
                        "name": branch_label(code, branch_names),
                        "display_title": branch_label(code, branch_names),
                        "cust_count": int(custs or 0),
                        "acnt_count": int(accts or 0),
                        "total_vol": _f(disbursed),
                        "repay_vol": _f(repaid),
                        "repaid_pct": _repaid_pct(_f(repaid), _f(disbursed)),
                        # Filled in by _links below from the real product mix.
                        "zone_id": "",
                        "zone_ids": [],
                        "zone_name": "",
                    }
                )
            return len(branches)

        run_section(provenance, "branches", _branches, conn)

        def _links() -> int:
            """The real branch-to-product relationship.

            Branches used to be attached to products by round-robin list index
            (`real_products[i % len(real_products)]`), so every edge in this tier was
            fabricated. A branch can carry several products, so this is many-to-many.
            """
            cur.execute(
                f"""
                SELECT gnlnac_appl_brn_code, gnlnac_prod_code, COUNT(*),
                       COALESCE(SUM(COALESCE(NULLIF(gnlnac_lndisb_amt, 0), gnlnac_sanc_amt)), 0),
                       COALESCE(SUM(gnlnac_pri_repay_amt), 0)
                FROM {LOAN_PORTFOLIO_SQL} portfolio
                {month_filter or 'WHERE TRUE'}
                  AND gnlnac_appl_brn_code IS NOT NULL AND gnlnac_prod_code IS NOT NULL
                GROUP BY 1, 2
                ORDER BY 3 DESC
                """,
                month_params,
            )
            by_branch: Dict[str, List[Dict[str, Any]]] = {}
            for brn, prod, accts, disbursed, repaid in cur.fetchall():
                b_code, p_code = _code(brn), _code(prod)
                link = {
                    "branch_id": f"BRN-{b_code}",
                    "branch_code": b_code,
                    "zone_id": f"ZONE-PROD-{p_code}",
                    "product_code": p_code,
                    "acnt_count": int(accts or 0),
                    "total_vol": _f(disbursed),
                    "repay_vol": _f(repaid),
                }
                branch_product_links.append(link)
                by_branch.setdefault(b_code, []).append(link)

            for branch in branches:
                links = sorted(
                    by_branch.get(branch["code"], []), key=lambda x: -x["acnt_count"]
                )
                branch["zone_ids"] = [link_["zone_id"] for link_ in links]
                if links:
                    # zone_id keeps the single-value shape the UI expects; it is the
                    # branch's dominant product by account count, and zone_ids carries
                    # the full set.
                    branch["zone_id"] = links[0]["zone_id"]
                    branch["zone_name"] = product_title(links[0]["product_code"])
            return len(branch_product_links)

        run_section(provenance, "branch_product_links", _links, conn)

        def _schemes() -> int:
            nonlocal scheme_names
            scheme_names = get_scheme_name_map(cur)
            return len(scheme_names)

        run_section(provenance, "scheme_names", _schemes, conn)

        # Search may redirect the requested level.
        current_level = view_level or "executive"
        if search_term and search_term.strip():
            matches = search_entities(search_term, entity_type=entity_type or "all")
            if matches:
                top = matches[0]
                current_level = top["view_level"]
                zonal_id = top.get("zonal_id", zonal_id)
                manager_id = top.get("manager_id", manager_id)
                agent_id = top.get("agent_id", agent_id)
                customer_id = top.get("customer_id", customer_id)

        selected_zonal = None
        selected_mgr = None
        selected_agent = None
        selected_customer = None

        def product_by_id(pid: Optional[str]) -> Optional[Dict[str, Any]]:
            return next((p for p in products if p["id"] == pid), None)

        def branch_by_id(bid: Optional[str]) -> Optional[Dict[str, Any]]:
            return next((b for b in branches if b["id"] == bid), None)

        # ---------------- Tier 0: executive ----------------
        if current_level == "executive":
            nodes.append(
                {
                    "id": executive_info["id"],
                    "type": "executive",
                    "title": executive_info["name"],
                    "subtitle": executive_info["role"],
                    "node_label": NODE_TYPE_STYLES["executive"]["label"],
                    "color": NODE_TYPE_STYLES["executive"]["color"],
                    "size": NODE_TYPE_STYLES["executive"]["size"],
                    "details": {
                        "Source": "PostgreSQL silver active + verified legacy loan portfolio",
                        "Holding Entity": executive_info["org"],
                        "Branches": f"{len(branches)}",
                        "Registered CIF Customers": f"{totals['registered_customers']:,}",
                        "Loan Borrowers": f"{totals['loan_borrowers']:,}",
                        "Active Loan Borrowers": f"{totals['active_loan_borrowers']:,}",
                        "Total Borrowers": f"{totals['loan_borrowers']:,}",
                        "Total Loan Accounts": f"{totals['accounts']:,}",
                        "Total Disbursed": _money(totals["disbursed"]),
                        "Total Repaid": _money(totals["repaid"]),
                        "Principal Repaid": f"{_repaid_pct(totals['repaid'], totals['disbursed']):.1f}%",
                    },
                }
            )
            for product in products:
                linked = {l["branch_code"] for l in branch_product_links if l["zone_id"] == product["id"]}
                nodes.append(_product_node(product, len(linked)))
                edges.append(
                    {
                        "source": executive_info["id"],
                        "target": product["id"],
                        "weight": 9,
                        "label": "PRODUCT_DIVISION",
                        "purpose": "Portfolio Division",
                    }
                )

        # ---------------- Tier 1: product division ----------------
        elif current_level == "zonal" or (zonal_id and not manager_id and not agent_id and not customer_id):
            selected_zonal = product_by_id(zonal_id) or (products[0] if products else None)
            if selected_zonal:
                # Only branches that genuinely originate this product.
                linked_codes = [
                    l["branch_code"]
                    for l in branch_product_links
                    if l["zone_id"] == selected_zonal["id"]
                ]
                assigned = [b for b in branches if b["code"] in set(linked_codes)]
                nodes.append(_product_node(selected_zonal, len(assigned)))
                for branch in assigned:
                    link = next(
                        (
                            l
                            for l in branch_product_links
                            if l["branch_code"] == branch["code"]
                            and l["zone_id"] == selected_zonal["id"]
                        ),
                        None,
                    )
                    nodes.append(_branch_node(branch, link))
                    edges.append(
                        {
                            "source": selected_zonal["id"],
                            "target": branch["id"],
                            "weight": 8,
                            "label": "ORIGINATES_AT",
                            "purpose": f"{link['acnt_count']:,} accounts" if link else "Branch",
                        }
                    )

        # ---------------- Tier 2: branch ----------------
        elif current_level == "manager" or (manager_id and not agent_id and not customer_id):
            selected_mgr = branch_by_id(manager_id) or (branches[0] if branches else None)
            if selected_mgr:
                selected_zonal = product_by_id(selected_mgr["zone_id"])
                if selected_zonal:
                    nodes.append(_product_node(selected_zonal, None))
                nodes.append(_branch_node(selected_mgr, None))
                if selected_zonal:
                    edges.append(
                        {
                            "source": selected_zonal["id"],
                            "target": selected_mgr["id"],
                            "weight": 8,
                            "label": "ORIGINATES_AT",
                            "purpose": "Branch Operations",
                        }
                    )

                branch_schemes: List[Dict[str, Any]] = []

                def _branch_schemes() -> int:
                    # Exact branch match; this used to be a LIKE '%code%' substring.
                    cur.execute(
                        f"""
                        SELECT gnlnac_schm_code, COUNT(DISTINCT gnlnac_cust_id), COUNT(*),
                               COALESCE(SUM(COALESCE(NULLIF(gnlnac_lndisb_amt, 0),
                                                     gnlnac_sanc_amt)), 0),
                               COALESCE(SUM(gnlnac_pri_repay_amt), 0)
                        FROM {LOAN_PORTFOLIO_SQL} portfolio
                        WHERE CAST(gnlnac_appl_brn_code AS TEXT) = %s
                          AND gnlnac_schm_code IS NOT NULL
                        GROUP BY gnlnac_schm_code
                        ORDER BY 3 DESC
                        LIMIT 8
                        """,
                        (selected_mgr["code"],),
                    )
                    for schm, custs, accts, disbursed, repaid in cur.fetchall():
                        branch_schemes.append(
                            {
                                "schm_code": _code(schm),
                                "cust_count": int(custs or 0),
                                "acnt_count": int(accts or 0),
                                "total_vol": _f(disbursed),
                                "repay_vol": _f(repaid),
                            }
                        )
                    return len(branch_schemes)

                run_section(provenance, "branch_schemes", _branch_schemes, conn)

                for scheme in branch_schemes:
                    title = scheme_title(scheme["schm_code"], scheme_names)
                    node_id = f"SCHM-{selected_mgr['code']}-{scheme['schm_code']}"
                    nodes.append(
                        {
                            "id": node_id,
                            "type": "agent",
                            "title": title,
                            "subtitle": f"{scheme['cust_count']:,} Borrowers • {scheme['acnt_count']:,} Loans",
                            "node_label": NODE_TYPE_STYLES["agent"]["label"],
                            "color": NODE_TYPE_STYLES["agent"]["color"],
                            "size": NODE_TYPE_STYLES["agent"]["size"],
                            "agent_id": node_id,
                            "manager_id": selected_mgr["id"],
                            "details": {
                                "Scheme Name": title,
                                "Scheme Code": scheme["schm_code"],
                                "Branch": selected_mgr["display_title"],
                                "Total Borrowers": f"{scheme['cust_count']:,}",
                                "Loan Accounts": f"{scheme['acnt_count']:,}",
                                "Total Disbursed": _money(scheme["total_vol"]),
                                "Total Repaid": _money(scheme["repay_vol"]),
                                "Principal Repaid": f"{_repaid_pct(scheme['repay_vol'], scheme['total_vol']):.1f}%",
                            },
                        }
                    )
                    edges.append(
                        {
                            "source": selected_mgr["id"],
                            "target": node_id,
                            "weight": 7,
                            "label": "OFFERS_SCHEME",
                            "purpose": "Credit Facility",
                        }
                    )

        # ---------------- Tier 3: scheme desk ----------------
        elif current_level == "agent" or (agent_id and not customer_id):
            parts = (agent_id or "").split("-")
            brn_code = parts[1] if len(parts) > 1 else (branches[0]["code"] if branches else "")
            schm_code = parts[2] if len(parts) > 2 else ""
            selected_mgr = next((b for b in branches if b["code"] == brn_code), None)

            borrowers: List[Dict[str, Any]] = []

            def _borrowers() -> int:
                # Filters on BOTH branch and scheme. The scheme code used to be parsed
                # from agent_id and then used only in the node title, so every scheme
                # desk under a branch showed an identical borrower list.
                sql = f"""
                    SELECT g.gnlnac_cust_id,
                           MAX(TRIM(g.gnlnac_cust_name)),
                           COUNT(*),
                           COALESCE(SUM(COALESCE(NULLIF(g.gnlnac_lndisb_amt, 0),
                                                 g.gnlnac_sanc_amt)), 0),
                           COALESCE(SUM(g.gnlnac_pri_repay_amt), 0),
                           MAX(g.gnlnac_sanc_date)
                    FROM {LOAN_PORTFOLIO_SQL} g
                    WHERE CAST(g.gnlnac_appl_brn_code AS TEXT) = %s
                """
                params: List[Any] = [brn_code]
                if schm_code:
                    sql += " AND CAST(g.gnlnac_schm_code AS TEXT) = %s"
                    params.append(schm_code)
                sql += " GROUP BY g.gnlnac_cust_id ORDER BY 4 DESC LIMIT %s"
                params.append(limit)
                cur.execute(sql, tuple(params))
                for cust_id, name, accts, disbursed, repaid, last_date in cur.fetchall():
                    borrowers.append(
                        {
                            "cust_id": _code(cust_id),
                            "cust_name": (name or f"Borrower #{_code(cust_id)}").strip(),
                            "account_count": int(accts or 0),
                            "disb_amt": _f(disbursed),
                            "repay_amt": _f(repaid),
                            "sanc_date": last_date.isoformat() if last_date else "",
                        }
                    )
                return len(borrowers)

            run_section(provenance, "scheme_borrowers", _borrowers, conn)

            title = scheme_title(schm_code, scheme_names)
            agent_disb = sum(b["disb_amt"] for b in borrowers)
            agent_repay = sum(b["repay_amt"] for b in borrowers)
            selected_agent = {
                "id": agent_id or f"SCHM-{brn_code}-{schm_code}",
                "name": title,
                "role": "Lending Scheme",
                "manager_id": selected_mgr["id"] if selected_mgr else "",
                "cust_count": len(borrowers),
                "total_disbursed": agent_disb,
                "total_repaid": agent_repay,
            }

            if selected_mgr:
                nodes.append(_branch_node(selected_mgr, None))
            nodes.append(
                {
                    "id": selected_agent["id"],
                    "type": "agent",
                    "title": title,
                    "subtitle": f"{len(borrowers):,} Borrowers",
                    "node_label": NODE_TYPE_STYLES["agent"]["label"],
                    "color": NODE_TYPE_STYLES["agent"]["color"],
                    "size": 24,
                    "agent_id": selected_agent["id"],
                    "details": {
                        "Scheme Name": title,
                        "Scheme Code": schm_code or "—",
                        "Branch": selected_mgr["display_title"] if selected_mgr else "—",
                        "Total Borrowers": f"{len(borrowers):,}",
                        "Total Disbursed": _money(agent_disb),
                        "Total Repaid": _money(agent_repay),
                        "Principal Repaid": f"{_repaid_pct(agent_repay, agent_disb):.1f}%",
                    },
                }
            )
            if selected_mgr:
                edges.append(
                    {
                        "source": selected_mgr["id"],
                        "target": selected_agent["id"],
                        "weight": 7,
                        "label": "OFFERS_SCHEME",
                        "purpose": "Credit Facility",
                    }
                )

            for borrower in borrowers:
                node_id = f"CUST-{borrower['cust_id']}"
                nodes.append(
                    {
                        "id": node_id,
                        "type": "customer",
                        "title": borrower["cust_name"],
                        "subtitle": f"#{borrower['cust_id']} • {_money(borrower['disb_amt'])}",
                        "node_label": NODE_TYPE_STYLES["customer"]["label"],
                        "color": NODE_TYPE_STYLES["customer"]["color"],
                        "size": NODE_TYPE_STYLES["customer"]["size"],
                        "customer_id": borrower["cust_id"],
                        "details": {
                            "Borrower Name": borrower["cust_name"],
                            "Customer ID": borrower["cust_id"],
                            "Branch": selected_mgr["display_title"] if selected_mgr else "—",
                            "Loan Accounts": f"{borrower['account_count']:,}",
                            "Total Disbursed": _money(borrower["disb_amt"]),
                            "Total Repaid": _money(borrower["repay_amt"]),
                            "Principal Repaid": f"{_repaid_pct(borrower['repay_amt'], borrower['disb_amt']):.1f}%",
                        },
                    }
                )
                edges.append(
                    {
                        "source": selected_agent["id"],
                        "target": node_id,
                        "weight": 6,
                        "label": "BORROWER",
                        "purpose": "Loan Portfolio",
                    }
                )

        # ---------------- Tier 4: borrower detail ----------------
        elif current_level == "customer" or customer_id:
            accounts: List[Dict[str, Any]] = []
            borrower: Dict[str, Any] = {}

            def _accounts() -> int:
                # All of the borrower's accounts. This used to be LIMIT 1, understating
                # every one of the 1,990 borrowers who hold more than one loan.
                cur.execute(
                    f"""
                    SELECT g.gnlnac_acnt_num, TRIM(g.gnlnac_cust_name), g.gnlnac_sanc_amt,
                           COALESCE(NULLIF(g.gnlnac_lndisb_amt, 0), g.gnlnac_sanc_amt),
                           g.gnlnac_pri_repay_amt, g.gnlnac_sanc_date, g.gnlnac_appl_brn_code,
                           g.gnlnac_schm_code, g.gnlnac_loan_type, g.gnlnac_closure_date
                    FROM {LOAN_PORTFOLIO_SQL} g
                    WHERE CAST(g.gnlnac_cust_id AS TEXT) = %s
                    ORDER BY g.gnlnac_sanc_date DESC
                    """,
                    (customer_id or "",),
                )
                for row in cur.fetchall():
                    accounts.append(
                        {
                            "acnt_num": _code(row[0]),
                            "name": (row[1] or "").strip(),
                            "sanc_amt": _f(row[2]),
                            "disb_amt": _f(row[3]),
                            "repay_amt": _f(row[4]),
                            "sanc_date": row[5].isoformat() if row[5] else "",
                            "brn_code": _code(row[6]),
                            "schm_code": _code(row[7]),
                            "loan_type": (row[8] or "").strip(),
                            "closed": bool(row[9]),
                        }
                    )
                return len(accounts)

            run_section(provenance, "borrower_accounts", _accounts, conn)

            if accounts:
                account_nums = [int(a["acnt_num"]) for a in accounts if a["acnt_num"].isdigit()]
                borrower = {
                    "cust_id": customer_id,
                    "cust_name": next((a["name"] for a in accounts if a["name"]), f"Borrower #{customer_id}"),
                    "account_count": len(accounts),
                    "disb_amt": sum(a["disb_amt"] for a in accounts),
                    "repay_amt": sum(a["repay_amt"] for a in accounts),
                    "brn_code": accounts[0]["brn_code"],
                }
                selected_customer = borrower
                cust_node_id = f"CUST-{customer_id}"
                nodes.append(
                    {
                        "id": cust_node_id,
                        "type": "customer",
                        "title": borrower["cust_name"],
                        "subtitle": f"Customer #{customer_id} • {borrower['account_count']} account(s)",
                        "node_label": NODE_TYPE_STYLES["customer"]["label"],
                        "color": NODE_TYPE_STYLES["customer"]["color"],
                        "size": 24,
                        "customer_id": str(customer_id),
                        "details": {
                            "Borrower Name": borrower["cust_name"],
                            "Customer ID": str(customer_id),
                            "Branch": branch_label(borrower["brn_code"], branch_names),
                            "Loan Accounts": f"{borrower['account_count']:,}",
                            "Total Disbursed": _money(borrower["disb_amt"]),
                            "Total Repaid": _money(borrower["repay_amt"]),
                            "Principal Repaid": f"{_repaid_pct(borrower['repay_amt'], borrower['disb_amt']):.1f}%",
                        },
                    }
                )

                disbursements: List[Dict[str, Any]] = []
                repayments: List[Dict[str, Any]] = []

                def _disbursements() -> int:
                    # Real disbursement transactions. The graph used to synthesise a
                    # single node per account from aggregate columns, dated at the
                    # sanction date, while bronze.genlndisb went unqueried.
                    if not account_nums:
                        return 0
                    cur.execute(
                        """
                        SELECT genlndisb_acnt_num, genlndisb_disb_sl, genlndisb_disb_date,
                               genlndisb_disb_amt, genlndisb_net_pay_amt, genlndisb_tot_chgs_amt
                        FROM bronze.genlndisb
                        WHERE genlndisb_acnt_num = ANY(%s)
                        ORDER BY genlndisb_disb_date, genlndisb_disb_sl
                        """,
                        (account_nums,),
                    )
                    for row in cur.fetchall():
                        disbursements.append(
                            {
                                "acnt_num": _code(row[0]),
                                "sl": _code(row[1]),
                                "date": (
                                    row[2].date().isoformat()
                                    if row[2] and hasattr(row[2], "date")
                                    else (row[2].isoformat() if row[2] else "")
                                ),
                                "amount": _f(row[3]),
                                "net_paid": _f(row[4]),
                                "charges": _f(row[5]),
                            }
                        )
                    return len(disbursements)

                def _repayments() -> int:
                    # Real repayment instalments from bronze.loanrepay, which carries both
                    # the amount due and the amount actually received.
                    if not account_nums:
                        return 0
                    cur.execute(
                        """
                        SELECT lnrepay_acnt_no, lnrepay_sl_no, lnrepay_repay_date,
                               lnrepay_prin_amt, lnrepay_int_amt,
                               lnrepay_prin_pdamt, lnrepay_int_pdamt
                        FROM bronze.loanrepay
                        WHERE lnrepay_acnt_no = ANY(%s)
                          AND (lnrepay_prin_pdamt > 0 OR lnrepay_int_pdamt > 0)
                        ORDER BY lnrepay_repay_date, lnrepay_sl_no
                        """,
                        (account_nums,),
                    )
                    for row in cur.fetchall():
                        repayments.append(
                            {
                                "acnt_num": _code(row[0]),
                                "sl": _code(row[1]),
                                "date": (
                                    row[2].date().isoformat()
                                    if row[2] and hasattr(row[2], "date")
                                    else (row[2].isoformat() if row[2] else "")
                                ),
                                "principal_due": _f(row[3]),
                                "interest_due": _f(row[4]),
                                "principal_paid": _f(row[5]),
                                "interest_paid": _f(row[6]),
                            }
                        )
                    return len(repayments)

                run_section(provenance, "disbursements", _disbursements, conn)
                run_section(provenance, "repayments", _repayments, conn)

                for account in accounts:
                    acnt_node_id = f"ACNT-{account['acnt_num']}"
                    nodes.append(
                        {
                            "id": acnt_node_id,
                            "type": "account",
                            "title": f"Account #{account['acnt_num']}",
                            "subtitle": f"Sanction: {_money(account['sanc_amt'])}",
                            "node_label": NODE_TYPE_STYLES["account"]["label"],
                            "color": NODE_TYPE_STYLES["account"]["color"],
                            "size": 22,
                            "details": {
                                "Account Number": account["acnt_num"],
                                "Borrower Name": borrower["cust_name"],
                                "Scheme": scheme_title(account["schm_code"], scheme_names),
                                "Sanctioned": _money(account["sanc_amt"]),
                                "Total Disbursed": _money(account["disb_amt"]),
                                "Total Repaid": _money(account["repay_amt"]),
                                "Sanction Date": account["sanc_date"],
                                "Status": "Closed" if account["closed"] else "Open",
                            },
                        }
                    )
                    edges.append(
                        {
                            "source": cust_node_id,
                            "target": acnt_node_id,
                            "weight": 8,
                            "label": "OWNS_ACCOUNT",
                            "purpose": "Loan Ownership",
                        }
                    )

                for idx, disb in enumerate(disbursements):
                    node_id = f"DISB-{disb['acnt_num']}-{disb['sl'] or idx}"
                    nodes.append(
                        {
                            "id": node_id,
                            "type": "disbursement",
                            "title": f"Disbursement {_money(disb['amount'])}",
                            "subtitle": disb["date"],
                            "node_label": NODE_TYPE_STYLES["disbursement"]["label"],
                            "color": NODE_TYPE_STYLES["disbursement"]["color"],
                            "size": 16,
                            "details": {
                                "Account Number": disb["acnt_num"],
                                "Disbursed Amount": _money(disb["amount"]),
                                "Net Paid to Borrower": _money(disb["net_paid"]),
                                "Charges Deducted": _money(disb["charges"]),
                                "Disbursement Date": disb["date"],
                                "Source": "bronze.genlndisb",
                            },
                        }
                    )
                    edges.append(
                        {
                            "source": f"ACNT-{disb['acnt_num']}",
                            "target": node_id,
                            "weight": 6,
                            "label": "DISBURSED",
                            "purpose": "Capital Payout",
                        }
                    )

                for idx, repay in enumerate(repayments):
                    node_id = f"REPAY-{repay['acnt_num']}-{repay['sl'] or idx}"
                    paid = repay["principal_paid"] + repay["interest_paid"]
                    due = repay["principal_due"] + repay["interest_due"]
                    nodes.append(
                        {
                            "id": node_id,
                            "type": "repayment",
                            "title": f"Repayment {_money(paid)}",
                            "subtitle": repay["date"],
                            "node_label": NODE_TYPE_STYLES["repayment"]["label"],
                            "color": NODE_TYPE_STYLES["repayment"]["color"],
                            "size": 16,
                            "details": {
                                "Account Number": repay["acnt_num"],
                                "Instalment Due": _money(due),
                                "Amount Received": _money(paid),
                                "Principal Received": _money(repay["principal_paid"]),
                                "Interest Received": _money(repay["interest_paid"]),
                                "Repayment Date": repay["date"],
                                "Source": "bronze.loanrepay",
                            },
                        }
                    )
                    edges.append(
                        {
                            "source": node_id,
                            "target": f"ACNT-{repay['acnt_num']}",
                            "weight": 6,
                            "label": "REPAID",
                            "purpose": "Credit Receipt",
                        }
                    )

                # A genuine collection efficiency for this borrower: received over due.
                def _efficiency() -> int:
                    borrower["collection_efficiency"] = get_collection_efficiency(cur, account_nums)
                    return 1

                run_section(provenance, "collection_efficiency", _efficiency, conn)
                eff = borrower.get("collection_efficiency") or {}
                if eff.get("instalments"):
                    for node in nodes:
                        if node["id"] == cust_node_id:
                            node["details"]["Collection Efficiency (paid/due)"] = (
                                f"{eff['efficiency_pct']:.1f}%"
                            )

        monthly_summary = get_monthly_breakdown(month)

    # Keep only nodes that participate in an edge, and de-duplicate.
    unique_nodes: List[Dict[str, Any]] = []
    seen: set = set()
    for node in nodes:
        if node["id"] not in seen:
            seen.add(node["id"])
            unique_nodes.append(node)

    connected = {e["source"] for e in edges} | {e["target"] for e in edges}
    if len(unique_nodes) > 1 and connected:
        unique_nodes = [n for n in unique_nodes if n["id"] in connected]

    live = sorted(k for k, v in provenance.items() if v["status"] == "ok")
    degraded = sorted(k for k, v in provenance.items() if v["status"] not in ("ok", "empty"))

    return {
        "nodes": unique_nodes,
        "edges": edges,
        "view_level": current_level,
        "executive_info": executive_info,
        "zonals": products,
        "selected_zonal": selected_zonal,
        "branches": branches,
        "branch_product_links": branch_product_links,
        "selected_manager": selected_mgr,
        "selected_agent": selected_agent,
        "selected_customer": selected_customer,
        "total_database_metrics": {
            # Backwards-compatible field: customers represented by loan nodes.
            "total_customers": totals["loan_borrowers"],
            "total_loan_borrowers": totals["loan_borrowers"],
            "total_active_loan_borrowers": totals["active_loan_borrowers"],
            "total_registered_customers": totals["registered_customers"],
            "total_accounts": totals["accounts"],
            "total_branches": len(branches),
        },
        "monthly_summary": monthly_summary,
        "provenance": provenance,
        "metadata": {
            # True only when every query resolved with rows - not merely because the
            # connection opened, which is what this used to mean.
            "is_live": bool(live) and not degraded,
            "live_sections": live,
            "degraded_sections": degraded,
            "schema": "silver",
            "total_nodes": len(unique_nodes),
            "total_edges": len(edges),
        },
    }


def _product_node(product: Dict[str, Any], branch_count: Optional[int]) -> Dict[str, Any]:
    details = {
        "Product Code": product["code"],
        "Product": product["name"],
        "Total Borrowers": f"{product['cust_count']:,}",
        "Loan Accounts": f"{product['acnt_count']:,}",
        "Total Disbursed": _money(product["total_vol"]),
        "Total Repaid": _money(product["repay_vol"]),
        "Principal Repaid": f"{product['repaid_pct']:.1f}%",
    }
    if branch_count is not None:
        details["Originating Branches"] = f"{branch_count}"
    return {
        "id": product["id"],
        "type": "zonal",
        "title": product["name"],
        "subtitle": f"Code #{product['code']} • {product['cust_count']:,} Borrowers",
        "node_label": NODE_TYPE_STYLES["zonal"]["label"],
        "color": NODE_TYPE_STYLES["zonal"]["color"],
        "size": NODE_TYPE_STYLES["zonal"]["size"],
        "zonal_id": product["id"],
        "details": details,
    }


def _branch_node(branch: Dict[str, Any], link: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    details = {
        "Branch Code": branch["code"],
        "Total Borrowers": f"{branch['cust_count']:,}",
        "Loan Accounts": f"{branch['acnt_count']:,}",
        "Total Disbursed": _money(branch["total_vol"]),
        "Total Repaid": _money(branch["repay_vol"]),
        "Principal Repaid": f"{branch['repaid_pct']:.1f}%",
    }
    if link:
        details["Accounts in this Product"] = f"{link['acnt_count']:,}"
        details["Disbursed in this Product"] = _money(link["total_vol"])
    return {
        "id": branch["id"],
        "type": "manager",
        "title": branch["display_title"],
        "subtitle": f"Branch #{branch['code']} • {branch['cust_count']:,} Borrowers",
        "node_label": NODE_TYPE_STYLES["manager"]["label"],
        "color": NODE_TYPE_STYLES["manager"]["color"],
        "size": NODE_TYPE_STYLES["manager"]["size"],
        "manager_id": branch["id"],
        "details": details,
    }
