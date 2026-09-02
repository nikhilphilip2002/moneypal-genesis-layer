"""Tests for the Enterprise Information Graph.

The previous suite only checked that node details contained certain keys and that
efficiency equalled repaid/disbursed - it would have passed unchanged on entirely
fabricated data. These tests check the graph against the database it claims to describe.
"""

import re

import pytest

from app.services import db_schema as svc
from app.services.db_schema import (
    branch_label,
    db_cursor,
    get_db_schema_graph,
    get_mom_loan_start_analysis,
    get_monthly_breakdown,
    scheme_title,
    search_entities,
)

# Real customers that were hardcoded as fallback data, lifted from a filed DNBS-02 return.
HARDCODED_PII = ["SUBRAMANYA", "MEGHARAJ", "DIVYA B C", "PRAKASH H R", "RAMESH KUMAR"]
# Invented geography from the old district map.
INVENTED_GEOGRAPHY = ["Udupi", "Mandya", "Shimoga", "Chikmagalur", "Hassan", "Mysore", "District Lead"]


def _db_available() -> bool:
    try:
        with db_cursor() as (_c, cur):
            cur.execute("SELECT 1")
            return True
    except Exception:
        return False


requires_db = pytest.mark.skipif(not _db_available(), reason="PostgreSQL warehouse not reachable")


def parse_currency(val: str) -> float:
    cleaned = re.sub(r"[^\d.]", "", val or "")
    return float(cleaned) if cleaned else 0.0


class TestLabelling:
    def test_branch_label_has_no_invented_geography(self):
        """Unknown branches fall back to their code without invented geography."""
        for code in ["1", "4", "1002", "9999", "", None]:
            label = branch_label(code)
            for word in INVENTED_GEOGRAPHY:
                assert word.lower() not in label.lower(), f"{label!r} invents geography"

    def test_unknown_scheme_keeps_its_code(self):
        """45 scheme codes have no master row; they must not get an invented category."""
        assert scheme_title("9999", {}) == "Scheme #9999"
        assert scheme_title("1610", {"1610": "BUSINESS/ SERVICE/INDUSTRY"}) == (
            "BUSINESS/ SERVICE/INDUSTRY (Scheme #1610)"
        )

    def test_no_module_level_fallback_data(self):
        """The fabricated product/branch/cohort matrices must be gone."""
        source = open(svc.__file__, encoding="utf-8").read()
        for marker in HARDCODED_PII:
            assert marker not in source, f"hardcoded PII {marker!r} still in db_schema.py"
        assert "Peak All-Time High" not in source
        assert "38.2" not in source


@requires_db
class TestExecutiveView:
    def test_totals_match_the_database(self):
        graph = get_db_schema_graph(view_level="executive")
        with db_cursor() as (_c, cur):
            cur.execute(
                f"""SELECT COUNT(*), COUNT(DISTINCT gnlnac_cust_id),
                          COALESCE(SUM(COALESCE(NULLIF(gnlnac_lndisb_amt,0), gnlnac_sanc_amt)),0)
                   FROM {svc.LOAN_PORTFOLIO_SQL} portfolio"""
            )
            accounts, customers, disbursed = cur.fetchone()
        metrics = graph["total_database_metrics"]
        assert metrics["total_accounts"] == accounts
        assert metrics["total_customers"] == customers
        assert metrics["total_loan_borrowers"] == customers
        with db_cursor() as (_c, cur):
            cur.execute(
                "SELECT COUNT(DISTINCT cifdata_cust_id) "
                "FROM silver.customer_information_file_master"
            )
            assert metrics["total_registered_customers"] == cur.fetchone()[0]
        node = next(n for n in graph["nodes"] if n["type"] == "executive")
        assert parse_currency(node["details"]["Total Disbursed"]) == pytest.approx(
            float(disbursed), rel=1e-6
        )

    def test_describes_itself_as_postgres(self):
        """The module reads PostgreSQL; it used to label every node Oracle."""
        graph = get_db_schema_graph(view_level="executive")
        node = next(n for n in graph["nodes"] if n["type"] == "executive")
        blob = " ".join(str(v) for v in node["details"].values()) + node["subtitle"]
        assert "Oracle" not in blob
        assert "silver" in blob

    def test_product_nodes_match_database(self):
        graph = get_db_schema_graph(view_level="executive")
        with db_cursor() as (_c, cur):
            cur.execute(
                f"SELECT COUNT(DISTINCT gnlnac_prod_code) FROM {svc.LOAN_PORTFOLIO_SQL} portfolio "
                "WHERE gnlnac_prod_code IS NOT NULL"
            )
            expected = cur.fetchone()[0]
        assert len({n["id"] for n in graph["nodes"] if n["type"] == "zonal"}) == expected


@requires_db
class TestBranchProductRelationship:
    def test_links_match_the_database_exactly(self):
        """Branches used to be attached to products by round-robin list index."""
        graph = get_db_schema_graph(view_level="executive")
        actual = {
            (l["branch_code"], l["product_code"], l["acnt_count"])
            for l in graph["branch_product_links"]
        }
        with db_cursor() as (_c, cur):
            cur.execute(
                f"""SELECT gnlnac_appl_brn_code, gnlnac_prod_code, COUNT(*)
                   FROM {svc.LOAN_PORTFOLIO_SQL} portfolio
                   WHERE gnlnac_appl_brn_code IS NOT NULL AND gnlnac_prod_code IS NOT NULL
                   GROUP BY 1,2"""
            )
            expected = {(svc._code(b), svc._code(p), int(n)) for b, p, n in cur.fetchall()}
        assert actual == expected

    def test_branch_product_links_are_not_duplicated(self):
        graph = get_db_schema_graph(view_level="executive")
        pairs = [(l["branch_code"], l["product_code"]) for l in graph["branch_product_links"]]
        assert len(pairs) == len(set(pairs))

    def test_branch_names_come_from_silver_master(self):
        graph = get_db_schema_graph(view_level="executive")
        with db_cursor() as (_c, cur):
            cur.execute(
                "SELECT mbrn_code, BTRIM(mbrn_name) FROM silver.branch_master "
                "WHERE NULLIF(BTRIM(mbrn_name), '') IS NOT NULL LIMIT 1"
            )
            code, name = cur.fetchone()
        branch = next((b for b in graph["branches"] if b["code"] == svc._code(code)), None)
        if branch:
            assert name in branch["display_title"]

    def test_product_drilldown_only_shows_originating_branches(self):
        graph = get_db_schema_graph(view_level="zonal", zonal_id="ZONE-PROD-16")
        shown = {n["id"] for n in graph["nodes"] if n["type"] == "manager"}
        with db_cursor() as (_c, cur):
            cur.execute(
                """SELECT DISTINCT gnlnac_appl_brn_code FROM silver.loan_account_master
                   WHERE gnlnac_prod_code = 16 AND gnlnac_appl_brn_code IS NOT NULL"""
            )
            expected = {f"BRN-{svc._code(r[0])}" for r in cur.fetchall()}
        assert shown == expected


@requires_db
class TestExactMatching:
    def test_branch_search_is_exact(self):
        """Searching branch "1" used to match 15 branches via LIKE '%1%'."""
        results = search_entities("1", entity_type="manager")
        assert [r["id"] for r in results] == ["BRN-1"]

    def test_product_search_is_exact(self):
        with db_cursor() as (_c, cur):
            cur.execute(
                "SELECT gnlnac_prod_code FROM silver.loan_account_master "
                "WHERE gnlnac_prod_code IS NOT NULL ORDER BY 1 LIMIT 1"
            )
            code = svc._code(cur.fetchone()[0])
        results = search_entities(code, entity_type="zonal")
        assert [r["id"] for r in results] == [f"ZONE-PROD-{code}"]

    def test_branch_drilldown_excludes_other_branches(self):
        """Every borrower shown under branch 1 must genuinely hold an account there.

        A borrower may also hold accounts at other branches, so the check is that each
        one has at least one branch-1 account - not that they have none elsewhere. Under
        the old LIKE '%1%' filter, borrowers whose only accounts sat at branches
        1001-1021 appeared here.
        """
        graph = get_db_schema_graph(view_level="agent", agent_id="SCHM-1-")
        cust_ids = [n["customer_id"] for n in graph["nodes"] if n["type"] == "customer"]
        if not cust_ids:
            pytest.skip("no borrowers returned for branch 1")
        with db_cursor() as (_c, cur):
            cur.execute(
                f"""SELECT COUNT(DISTINCT gnlnac_cust_id) FROM {svc.LOAN_PORTFOLIO_SQL} portfolio
                   WHERE CAST(gnlnac_cust_id AS TEXT) = ANY(%s)
                     AND CAST(gnlnac_appl_brn_code AS TEXT) = '1'""",
                (cust_ids,),
            )
            assert cur.fetchone()[0] == len(cust_ids)


@requires_db
class TestSchemeDesk:
    def test_different_schemes_return_different_borrowers(self):
        """The scheme code used to be title-only; every desk showed one borrower list."""
        a = get_db_schema_graph(view_level="agent", agent_id="SCHM-4-1615")
        b = get_db_schema_graph(view_level="agent", agent_id="SCHM-4-1610")
        ids_a = {n["id"] for n in a["nodes"] if n["type"] == "customer"}
        ids_b = {n["id"] for n in b["nodes"] if n["type"] == "customer"}
        assert ids_a and ids_b
        assert not (ids_a & ids_b), "scheme desks must not share borrowers"

    def test_borrowers_actually_hold_that_scheme(self):
        graph = get_db_schema_graph(view_level="agent", agent_id="SCHM-4-1615")
        cust_ids = [n["customer_id"] for n in graph["nodes"] if n["type"] == "customer"]
        with db_cursor() as (_c, cur):
            cur.execute(
                """SELECT COUNT(DISTINCT gnlnac_cust_id) FROM silver.loan_account_master
                   WHERE CAST(gnlnac_cust_id AS TEXT) = ANY(%s)
                     AND CAST(gnlnac_appl_brn_code AS TEXT) = '4'
                     AND CAST(gnlnac_schm_code AS TEXT) = '1615'""",
                (cust_ids,),
            )
            assert cur.fetchone()[0] == len(cust_ids)

    def test_scheme_titles_come_from_the_master(self):
        graph = get_db_schema_graph(view_level="manager", manager_id="BRN-4")
        titles = [n["title"] for n in graph["nodes"] if n["type"] == "agent"]
        assert any("LOAN AGAINST PROPERTY" in t for t in titles)
        # Invented desk names must be gone.
        assert not any("Priority Credit Desk" in t for t in titles)


@requires_db
class TestBorrowerDetail:
    @staticmethod
    def _multi_account_customer():
        with db_cursor() as (_c, cur):
            cur.execute(
                """SELECT g.gnlnac_cust_id FROM silver.loan_account_master g
                   WHERE EXISTS (SELECT 1 FROM bronze.loanrepay r
                                 WHERE r.lnrepay_acnt_no = g.gnlnac_acnt_num
                                   AND r.lnrepay_prin_pdamt > 0)
                   GROUP BY 1 HAVING COUNT(*) > 1 ORDER BY COUNT(*) DESC LIMIT 1"""
            )
            row = cur.fetchone()
        if not row:
            pytest.skip("no multi-account borrower with repayments")
        return svc._code(row[0])

    def test_all_accounts_are_shown(self):
        """The detail view used to LIMIT 1, understating 1,990 multi-account borrowers."""
        cust = self._multi_account_customer()
        graph = get_db_schema_graph(view_level="customer", customer_id=cust)
        shown = {n["id"] for n in graph["nodes"] if n["type"] == "account"}
        with db_cursor() as (_c, cur):
            cur.execute(
                "SELECT gnlnac_acnt_num FROM silver.loan_account_master WHERE CAST(gnlnac_cust_id AS TEXT)=%s",
                (cust,),
            )
            expected = {f"ACNT-{svc._code(r[0])}" for r in cur.fetchall()}
        assert shown == expected
        assert len(shown) > 1

    def test_transaction_nodes_are_real_rows(self):
        """Disbursement and repayment nodes used to be synthesised one-per-account."""
        cust = self._multi_account_customer()
        graph = get_db_schema_graph(view_level="customer", customer_id=cust)
        disb = [n for n in graph["nodes"] if n["type"] == "disbursement"]
        repay = [n for n in graph["nodes"] if n["type"] == "repayment"]
        with db_cursor() as (_c, cur):
            cur.execute(
                """SELECT COUNT(*) FROM bronze.genlndisb
                   WHERE genlndisb_acnt_num IN (
                     SELECT gnlnac_acnt_num FROM silver.loan_account_master
                     WHERE CAST(gnlnac_cust_id AS TEXT)=%s)""",
                (cust,),
            )
            expected_disb = cur.fetchone()[0]
            cur.execute(
                """SELECT COUNT(*) FROM bronze.loanrepay
                   WHERE lnrepay_acnt_no IN (
                     SELECT gnlnac_acnt_num FROM silver.loan_account_master
                     WHERE CAST(gnlnac_cust_id AS TEXT)=%s)
                     AND (lnrepay_prin_pdamt > 0 OR lnrepay_int_pdamt > 0)""",
                (cust,),
            )
            expected_repay = cur.fetchone()[0]
        assert len(disb) == expected_disb
        assert len(repay) == expected_repay
        # More than one repayment means these cannot be the old one-per-account synthetics.
        assert len(repay) > 1
        for node in disb + repay:
            assert node["details"]["Source"].startswith("bronze.")

    def test_transaction_nodes_carry_real_dates(self):
        cust = self._multi_account_customer()
        graph = get_db_schema_graph(view_level="customer", customer_id=cust)
        for node in graph["nodes"]:
            if node["type"] == "repayment":
                assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", node["details"]["Repayment Date"])
            if node["type"] == "disbursement":
                assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", node["details"]["Disbursement Date"])

    def test_unknown_customer_yields_no_invented_borrower(self):
        """This used to fall back to a hardcoded 'S V SUBRAMANYA BHAT' at Rs 15,00,000."""
        graph = get_db_schema_graph(view_level="customer", customer_id="-999")
        assert [n for n in graph["nodes"] if n["type"] == "customer"] == []
        assert graph["selected_customer"] is None


@requires_db
class TestMetrics:
    def test_principal_repaid_is_not_called_collection_efficiency(self):
        """repaid/disbursed is a cumulative ratio, not collection efficiency."""
        graph = get_db_schema_graph(view_level="executive")
        node = next(n for n in graph["nodes"] if n["type"] == "executive")
        assert "Principal Repaid" in node["details"]
        assert "Collection Efficiency" not in node["details"]

    def test_true_collection_efficiency_is_paid_over_due(self):
        with db_cursor() as (_c, cur):
            result = svc.get_collection_efficiency(cur)
            cur.execute(
                """SELECT COALESCE(SUM(lnrepay_prin_amt + lnrepay_int_amt),0),
                          COALESCE(SUM(lnrepay_prin_pdamt + lnrepay_int_pdamt),0)
                   FROM bronze.loanrepay"""
            )
            due, paid = cur.fetchone()
        assert result["amount_due"] == pytest.approx(float(due), rel=1e-6)
        assert result["amount_paid"] == pytest.approx(float(paid), rel=1e-6)
        assert result["efficiency_pct"] == pytest.approx(float(paid) / float(due) * 100, abs=0.1)


@requires_db
class TestMonthlySeries:
    def test_monthly_breakdown_is_live(self):
        data = get_monthly_breakdown()
        assert data["provenance"]["monthly_series"]["status"] == "ok"
        assert data["monthly_series"]

    def test_mom_analysis_runs_against_the_database(self):
        """This always failed on the non-existent gnlnac_int_rate column and returned
        a hardcoded nine-month series."""
        data = get_mom_loan_start_analysis()
        assert data["provenance"]["monthly_cohorts"]["status"] == "ok"
        cohorts = data["monthly_cohorts"]
        assert cohorts
        with db_cursor() as (_c, cur):
            cur.execute(
                f"""SELECT COUNT(DISTINCT TO_CHAR(gnlnac_sanc_date,'YYYY-MM'))
                   FROM {svc.LOAN_PORTFOLIO_SQL} portfolio
                   WHERE gnlnac_sanc_date IS NOT NULL"""
            )
            assert len(cohorts) == cur.fetchone()[0]

    def test_first_cohort_has_no_growth_figure(self):
        """There is no prior month to grow from; it must be null, not 0.0."""
        data = get_mom_loan_start_analysis()
        earliest = data["monthly_cohorts"][-1]
        assert earliest["mom_growth_pct"] is None

    def test_no_editorial_status_labels(self):
        data = get_mom_loan_start_analysis()
        for cohort in data["monthly_cohorts"]:
            assert "institution_status" not in cohort


@requires_db
class TestProvenance:
    def test_is_live_reflects_query_outcomes(self):
        graph = get_db_schema_graph(view_level="executive")
        meta = graph["metadata"]
        assert meta["is_live"] is (bool(meta["live_sections"]) and not meta["degraded_sections"])

    def test_every_section_reports_a_status(self):
        graph = get_db_schema_graph(view_level="executive")
        assert graph["provenance"]
        for name, entry in graph["provenance"].items():
            assert entry["status"] in {"ok", "empty", "error", "no_source"}, name

    def test_graph_is_fully_connected(self):
        graph = get_db_schema_graph(view_level="executive")
        connected = {e["source"] for e in graph["edges"]} | {e["target"] for e in graph["edges"]}
        assert {n["id"] for n in graph["nodes"]} <= connected
