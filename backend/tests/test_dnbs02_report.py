import pytest
import io
import openpyxl
from app.services.dnbs02_service import (
    parse_period_range,
    get_dnbs02_report_data,
    generate_dnbs02_excel,
)


class TestDNBS02Service:
    """TDD Test suite for DNBS-02 Regulatory Report calculation and export logic."""

    def test_parse_period_range_monthly(self):
        start_date, end_date = parse_period_range("monthly", "2026-05")
        assert start_date == "2026-05-01"
        assert end_date == "2026-05-31"

    def test_parse_period_range_quarterly(self):
        # Q1: Apr-Jun, Q2: Jul-Sep, Q3: Oct-Dec, Q4: Jan-Mar
        start_q4, end_q4 = parse_period_range("quarterly", "2025-Q4")
        assert start_q4 == "2026-01-01"
        assert end_q4 == "2026-03-31"

        start_q1, end_q1 = parse_period_range("quarterly", "2026-Q1")
        assert start_q1 == "2026-04-01"
        assert end_q1 == "2026-06-30"

    def test_parse_period_range_yearly(self):
        start_y, end_y = parse_period_range("yearly", "2025-2026")
        assert start_y == "2025-04-01"
        assert end_y == "2026-03-31"

    def test_get_dnbs02_report_data_structure(self):
        data = get_dnbs02_report_data(frequency="monthly", period="2026-05")
        assert isinstance(data, dict)
        assert data["frequency"] == "monthly"
        assert data["period"] == "2026-05"
        
        # Summary metrics
        assert "summary" in data
        summary = data["summary"]
        assert "total_loan_book" in summary
        assert "net_owned_funds" in summary
        assert "crar_pct" in summary
        assert "npa_ratio_pct" in summary
        assert summary["total_loan_book"] >= 0

        # Part 1 Capital
        assert "part1_capital" in data
        assert isinstance(data["part1_capital"], list)
        assert len(data["part1_capital"]) > 0

        # Part 8 Asset Quality
        assert "part8_asset_quality" in data
        assert isinstance(data["part8_asset_quality"], list)

        # Annex 9 Top Borrowers
        assert "annex9_top_borrowers" in data
        assert isinstance(data["annex9_top_borrowers"], list)
        assert len(data["annex9_top_borrowers"]) <= 25

        # Annex 10 Top Investments
        assert "annex10_top_investments" in data
        assert isinstance(data["annex10_top_investments"], list)
        assert len(data["annex10_top_investments"]) > 0


        # Annex 13 Branches
        assert "annex13_branches" in data
        assert isinstance(data["annex13_branches"], list)

    def test_generate_dnbs02_excel(self):
        excel_bytes = generate_dnbs02_excel(frequency="monthly", period="2026-05")
        assert isinstance(excel_bytes, bytes)
        assert len(excel_bytes) > 0
        assert excel_bytes.startswith(b"PK\x03\x04")  # Zip signature for .xlsx

        # Verify openpyxl can load the generated workbook and all 28 template sheets exist
        wb = openpyxl.load_workbook(io.BytesIO(excel_bytes))
        sheet_names = wb.sheetnames
        assert len(sheet_names) == 28, f"Expected 28 sheets from template, got {len(sheet_names)}"
        assert "DNBS02_PART1" in sheet_names
        assert "DNBS02_Annex9" in sheet_names
        assert "DNBS02_Annex13" in sheet_names

        # Verify FilingInfo sheet dates are correctly updated
        filing_sheet = wb["FilingInfo"]
        assert filing_sheet["C12"].value == "01/05/2026"
        assert filing_sheet["C13"].value == "31/05/2026"
        assert filing_sheet["C15"].value == "LAKHS"


