import pytest
import re
from app.services.db_schema import (
    get_db_schema_graph,
    get_monthly_breakdown,
    get_mom_loan_start_analysis,
)


def parse_currency(val_str: str) -> float:
    """Helper to parse currency strings like '₹377,400,000' to float."""
    cleaned = re.sub(r"[^\d.]", "", val_str)
    return float(cleaned) if cleaned else 0.0


def parse_percentage(val_str: str) -> float:
    """Helper to parse percentage strings like '95.3%' to float."""
    cleaned = re.sub(r"[^\d.]", "", val_str)
    return float(cleaned) if cleaned else 0.0


class TestDBSchemaCuriosityGraph:
    """Test suite verifying contract integrity and math consistency for Enterprise Curiosity Graph nodes."""

    def test_executive_node_metrics(self):
        graph = get_db_schema_graph(view_level="executive")
        assert graph["view_level"] == "executive"
        assert len(graph["nodes"]) > 0

        exec_node = next((n for n in graph["nodes"] if n["type"] == "executive"), None)
        assert exec_node is not None, "Executive portfolio node must exist"

        details = exec_node["details"]
        assert "Total Disbursed" in details, "Executive node must contain Total Disbursed"
        assert "Total Repaid" in details, "Executive node must contain Total Repaid"
        assert "Collection Efficiency" in details, "Executive node must contain Collection Efficiency"

        disbursed = parse_currency(details["Total Disbursed"])
        repaid = parse_currency(details["Total Repaid"])
        efficiency = parse_percentage(details["Collection Efficiency"])

        assert disbursed > 0, "Total Disbursed must be greater than zero"
        assert repaid > 0, "Total Repaid must be greater than zero"
        expected_eff = round((repaid / disbursed) * 100, 1)
        assert abs(efficiency - expected_eff) <= 0.1, f"Expected efficiency {expected_eff}%, got {efficiency}%"

    def test_product_division_nodes(self):
        graph = get_db_schema_graph(view_level="executive")
        product_nodes = [n for n in graph["nodes"] if n["type"] == "zonal"]
        assert len(product_nodes) > 0, "Product division nodes must exist"

        for p_node in product_nodes:
            details = p_node["details"]
            assert "Total Disbursed" in details
            assert "Total Repaid" in details
            assert "Collection Efficiency" in details

            disb = parse_currency(details["Total Disbursed"])
            repay = parse_currency(details["Total Repaid"])
            eff = parse_percentage(details["Collection Efficiency"])

            assert disb > 0
            assert repay > 0
            expected_eff = round((repay / disb) * 100, 1)
            assert abs(eff - expected_eff) <= 0.1

    def test_district_virtual_branch_nodes(self):
        graph = get_db_schema_graph(view_level="zonal", zonal_id="ZONE-PROD-16")
        branch_nodes = [n for n in graph["nodes"] if n["type"] == "manager"]
        assert len(branch_nodes) > 0, "District branch nodes must exist when querying zone"

        for b_node in branch_nodes:
            details = b_node["details"]
            assert "Total Disbursed" in details
            assert "Total Repaid" in details
            assert "Collection Efficiency" in details

            disb = parse_currency(details["Total Disbursed"])
            repay = parse_currency(details["Total Repaid"])
            eff = parse_percentage(details["Collection Efficiency"])

            assert details["Total Repaid"] != "N/A", "District branch Total Repaid must not be N/A"
            assert disb > 0
            assert repay > 0
            expected_eff = round((repay / disb) * 100, 1)
            assert abs(eff - expected_eff) <= 0.1

    def test_scheme_desk_nodes(self):
        graph = get_db_schema_graph(view_level="manager", manager_id="BRN-1")
        scheme_nodes = [n for n in graph["nodes"] if n["type"] == "agent"]
        assert len(scheme_nodes) > 0, "Scheme desk nodes must exist"

        for s_node in scheme_nodes:
            details = s_node["details"]
            assert "Total Disbursed" in details
            assert "Total Repaid" in details
            assert "Collection Efficiency" in details

            disb = parse_currency(details["Total Disbursed"])
            repay = parse_currency(details["Total Repaid"])
            eff = parse_percentage(details["Collection Efficiency"])

            assert disb > 0
            assert repay > 0
            expected_eff = round((repay / disb) * 100, 1)
            assert abs(eff - expected_eff) <= 0.1

    def test_borrower_customer_nodes(self):
        graph = get_db_schema_graph(view_level="customer", customer_id="261")
        cust_node = next((n for n in graph["nodes"] if n["type"] == "customer"), None)
        assert cust_node is not None, "Customer node must exist"

        details = cust_node["details"]
        assert "Total Disbursed" in details
        assert "Total Repaid" in details
        assert "Collection Efficiency" in details

        disb = parse_currency(details["Total Disbursed"])
        repay = parse_currency(details["Total Repaid"])
        eff = parse_percentage(details["Collection Efficiency"])

        assert disb > 0
        assert repay > 0
        expected_eff = round((repay / disb) * 100, 1)
        assert abs(eff - expected_eff) <= 0.1

    def test_monthly_breakdown_math(self):
        breakdown = get_monthly_breakdown()
        assert "monthly_series" in breakdown
        for m in breakdown["monthly_series"]:
            disb = m["total_disbursed"]
            repay = m["total_repaid"]
            eff = m["collection_efficiency"]
            if disb > 0:
                expected_eff = round((repay / disb) * 100, 1)
                assert abs(eff - expected_eff) <= 0.1

    def test_mom_loan_analysis_math(self):
        analysis = get_mom_loan_start_analysis()
        assert "monthly_cohorts" in analysis
        for c in analysis["monthly_cohorts"]:
            disb = c["volume_disbursed"]
            repay = c["volume_repaid"]
            rate = c["repayment_rate"]
            if disb > 0:
                expected_rate = round((repay / disb) * 100, 1)
                assert abs(rate - expected_rate) <= 0.1
