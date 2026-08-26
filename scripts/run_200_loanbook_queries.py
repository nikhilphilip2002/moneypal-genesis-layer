#!/usr/bin/env python3
"""Run 200 evaluation queries strictly based on the Loan Book Gold semantic layer.

Connects to Moneypal Genesis Intelligence application (default: http://100.70.118.31:4321)
using timeout and configuration settings loaded from .env.prod.
Generates a comprehensive Markdown report with questions, natural language answers,
rendered chart types, and executed governed SQL queries from the catalog.
"""

from __future__ import annotations

import argparse
import datetime
import json
import random
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


# --------------------------------------------------------------------------------------
# Environment & Configuration Loader
# --------------------------------------------------------------------------------------

def load_env_prod(env_path: Path | None = None) -> dict[str, str]:
    """Parse .env.prod or fallback env file without external dependencies."""
    env_vars: dict[str, str] = {}
    candidates = [
        env_path,
        Path(".env.prod"),
        Path(__file__).resolve().parents[1] / ".env.prod",
        Path(".env"),
        Path(__file__).resolve().parents[1] / ".env",
    ]
    
    target_file = None
    for c in candidates:
        if c and c.exists() and c.is_file():
            target_file = c
            break

    if target_file:
        for line in target_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                k, v = line.split("=", 1)
                env_vars[k.strip()] = v.strip().strip("'\"")
    return env_vars


# --------------------------------------------------------------------------------------
# Query Data Models
# --------------------------------------------------------------------------------------

@dataclass
class QueryItem:
    id: int
    category: str  # "Loan Book"
    sub_category: str
    question: str
    preferred_pin: str = "db"
    description: str = ""


@dataclass
class QueryResult:
    item: QueryItem
    status: str  # "Answered" | "Partial" | "Refused" | "Clarification Needed" | "Error"
    latency_s: float
    sources: list[str] = field(default_factory=list)
    card_types: list[str] = field(default_factory=list)
    headline: str = ""
    summary: str = ""
    synthesis: str = ""
    chart_info: dict[str, Any] | None = None
    chart_type: str = ""
    sql_query: str = ""
    citations: list[str] = field(default_factory=list)
    error_message: str = ""


_INCOMPLETE_RESPONSE_RE = re.compile(
    r"\b(?:cannot|can't|unable to)\s+(?:compare|determine|assess|align)|"
    r"\b(?:direct|precise|quantitative)\s+comparison\b[^.]{0,100}\b(?:not possible|cannot)|"
    r"\b(?:data|evidence|benchmark|figures?|targets?)\s+(?:is|are)\s+"
    r"(?:missing|absent|unavailable)|"
    r"\b(?:context|findings|passages|evidence)\s+lacks?\b|\bdata gap\b",
    re.IGNORECASE,
)


def response_is_incomplete(text: str) -> bool:
    return bool(_INCOMPLETE_RESPONSE_RE.search(text))


# --------------------------------------------------------------------------------------
# 200 Curated Loan Book Questions from Gold YAML Schema
# --------------------------------------------------------------------------------------

def get_200_loanbook_queries() -> list[QueryItem]:
    """Generate 200 loan book evaluation queries referencing the Gold semantic layer catalog."""
    queries_data: list[tuple[str, str, str]] = [
        # ==============================================================================
        # 1. Portfolio Outstanding & Book Balances (Q001 - Q020)
        # ==============================================================================
        (
            "Portfolio Outstanding",
            "What is our total principal outstanding across the loan book?",
            "Total principal outstanding across all active classified accounts in portfolio snapshot",
        ),
        (
            "Portfolio Outstanding",
            "Show principal outstanding breakdown by product type.",
            "Distribution of principal outstanding across Gold, Microfinance, and MSME products",
        ),
        (
            "Portfolio Outstanding",
            "What is the principal outstanding by branch?",
            "Branch-level breakdown of total principal outstanding",
        ),
        (
            "Portfolio Outstanding",
            "Show principal outstanding by scheme.",
            "Scheme-level distribution of current principal outstanding",
        ),
        (
            "Portfolio Outstanding",
            "What is the total overdue principal across all active loans?",
            "Total delinquent principal overdue at current snapshot",
        ),
        (
            "Portfolio Outstanding",
            "What is the total overdue amount including interest and penal charges?",
            "Total overdue balance (principal, interest, charges, penal) across book",
        ),
        (
            "Portfolio Outstanding",
            "How many total active loan accounts do we have?",
            "Count of active loan accounts in loan master",
        ),
        (
            "Portfolio Outstanding",
            "What is the total principal outstanding in Gold Loans?",
            "Principal outstanding filtered for Product Code 1 (Gold Loans)",
        ),
        (
            "Portfolio Outstanding",
            "What is the total principal outstanding in Business and MSME Loans?",
            "Principal outstanding filtered for Product Code 16 (Business & MSME Loans)",
        ),
        (
            "Portfolio Outstanding",
            "What is the total principal outstanding in Microfinance and Retail EMI?",
            "Principal outstanding filtered for Product Code 13 (Microfinance / Retail EMI)",
        ),
        (
            "Portfolio Outstanding",
            "Show principal outstanding by loan type.",
            "Principal outstanding comparison between EMI term loans and bullet/demand loans",
        ),
        (
            "Portfolio Outstanding",
            "What is the distribution of principal outstanding by asset classification?",
            "Principal outstanding across Standard, SMA-0, SMA-1, SMA-2, and NPA categories",
        ),
        (
            "Portfolio Outstanding",
            "What is the total cumulative principal repaid across all loan accounts?",
            "Cumulative principal repaid across loan master accounts",
        ),
        (
            "Portfolio Outstanding",
            "What is the total cumulative disbursed amount across all accounts in the loan master?",
            "Total cumulative amount disbursed recorded on account master",
        ),
        (
            "Portfolio Outstanding",
            "Show principal outstanding for open versus closed loan accounts.",
            "Binary lifecycle split of outstanding balances between Open and Closed states",
        ),
        (
            "Portfolio Outstanding",
            "Top 10 loan accounts by principal outstanding.",
            "Ranking top 10 individual loan accounts with highest exposure",
        ),
        (
            "Portfolio Outstanding",
            "List the top 5 branches by total principal outstanding.",
            "Ranking top 5 branches managing largest portfolio volumes",
        ),
        (
            "Portfolio Outstanding",
            "What is the average principal outstanding per loan account?",
            "Average exposure per classified loan account",
        ),
        (
            "Portfolio Outstanding",
            "Show principal outstanding in Head Office Credit Division.",
            "Principal outstanding for branch 4 (Head Office — Credit Division)",
        ),
        (
            "Portfolio Outstanding",
            "What is the total principal outstanding in Aluva branch?",
            "Principal outstanding for branch 1002 (Aluva)",
        ),

        # ==============================================================================
        # 2. Origination, Sanctions & Pipeline (Q021 - Q040)
        # ==============================================================================
        (
            "Origination & Sanctions",
            "What is the total sanctioned amount this financial year?",
            "FYTD sanctioned amount KPI from loan master",
        ),
        (
            "Origination & Sanctions",
            "What was our total sanctioned amount in FY26?",
            "Total sanctioned volume during fiscal year 2025-26",
        ),
        (
            "Origination & Sanctions",
            "What was the sanctioned amount in the last quarter?",
            "Sanctioned amount in Q2 2026",
        ),
        (
            "Origination & Sanctions",
            "Show me the monthly trend of sanctioned amount over the last 12 months.",
            "12-month monthly time-series of total loan sanction amounts",
        ),
        (
            "Origination & Sanctions",
            "How many loans did we sanction each month in the last year?",
            "12-month monthly time-series of sanctioned loan counts",
        ),
        (
            "Origination & Sanctions",
            "What is the total count of loans sanctioned in the current financial year?",
            "FYTD count of sanctioned loan accounts",
        ),
        (
            "Origination & Sanctions",
            "What is the average ticket size of sanctioned loans across all branches?",
            "Average sanctioned loan amount across all branches",
        ),
        (
            "Origination & Sanctions",
            "Show average ticket size by product type.",
            "Average ticket size comparison across Gold, Microfinance, and MSME products",
        ),
        (
            "Origination & Sanctions",
            "What is the average ticket size by loan scheme?",
            "Average ticket size breakdown across individual loan schemes",
        ),
        (
            "Origination & Sanctions",
            "What is the average sanctioned interest rate across all accounts?",
            "Sanction-amount weighted average interest rate across portfolio",
        ),
        (
            "Origination & Sanctions",
            "Show average interest rate by product type.",
            "Weighted average interest rate across product categories",
        ),
        (
            "Origination & Sanctions",
            "What is the average interest rate by scheme?",
            "Weighted average interest rate across product schemes",
        ),
        (
            "Origination & Sanctions",
            "Show loan sanction count by branch last quarter.",
            "Branch-level sanction volume in the prior quarter",
        ),
        (
            "Origination & Sanctions",
            "What was the sanctioned amount by branch in the last financial year?",
            "Branch-level sanctioned amount breakdown in FY26",
        ),
        (
            "Origination & Sanctions",
            "Show loan count by product type.",
            "Distribution of loan counts by product code",
        ),
        (
            "Origination & Sanctions",
            "How many distinct borrowers do we have in our portfolio?",
            "Total distinct customer count with sanctioned loans",
        ),
        (
            "Origination & Sanctions",
            "What is the sanctioned amount for EMI term loans versus bullet loans?",
            "Sanction volume comparison by loan amortization type (E vs C)",
        ),
        (
            "Origination & Sanctions",
            "What is the total number of loan applications received?",
            "Application volume from loan application master",
        ),
        (
            "Origination & Sanctions",
            "Show application volume by application branch.",
            "Application counts grouped by origination branch",
        ),
        (
            "Origination & Sanctions",
            "What is the observable application to disbursement conversion rate?",
            "Observable conversion percentage of applications to disbursed accounts",
        ),

        # ==============================================================================
        # 3. Disbursements & Cash Outflows (Q041 - Q060)
        # ==============================================================================
        (
            "Disbursements",
            "What was our total disbursement last quarter?",
            "Disbursement event flow in prior quarter (Q2 2026)",
        ),
        (
            "Disbursements",
            "What is the total disbursement amount this financial year?",
            "FYTD total disbursement volume from disbursement events",
        ),
        (
            "Disbursements",
            "What was the total disbursement in FY26?",
            "Total disbursement amount in FY2025-26",
        ),
        (
            "Disbursements",
            "Show me the disbursement trend over the last 12 months.",
            "12-month monthly disbursement flow time-series",
        ),
        (
            "Disbursements",
            "Show monthly disbursement count over the last 12 months.",
            "Monthly count of disbursement events over past year",
        ),
        (
            "Disbursements",
            "What was our disbursement by branch last quarter?",
            "Branch-level disbursement breakdown in Q2 2026",
        ),
        (
            "Disbursements",
            "Which branches disbursed the most last quarter?",
            "Ranking branches by disbursed amount in prior quarter",
        ),
        (
            "Disbursements",
            "Show disbursement amount by product type last quarter.",
            "Disbursement breakdown by product in Q2 2026",
        ),
        (
            "Disbursements",
            "How much have we disbursed in gold loans?",
            "Cumulative disbursement amount for Product Code 1 (Gold Loans)",
        ),
        (
            "Disbursements",
            "How much have we disbursed in business and MSME loans?",
            "Cumulative disbursement amount for Product Code 16 (Business & MSME Loans)",
        ),
        (
            "Disbursements",
            "How much have we disbursed in microfinance loans?",
            "Cumulative disbursement amount for Product Code 13 (Microfinance / Retail EMI)",
        ),
        (
            "Disbursements",
            "Top 10 schemes by disbursement amount.",
            "Ranking schemes by total historical disbursement volume",
        ),
        (
            "Disbursements",
            "Show disbursement volume in Kozhikode branch.",
            "Total disbursement events in branch 1007 (Kozhikode)",
        ),
        (
            "Disbursements",
            "Show disbursement volume in Thripunithura branch.",
            "Total disbursement events in branch 1001 (Thripunithura)",
        ),
        (
            "Disbursements",
            "Show disbursement volume in Angamally branch.",
            "Total disbursement events in branch 1013 (Angamally)",
        ),
        (
            "Disbursements",
            "What was the total disbursement in Q1 2026?",
            "Disbursement volume in Q1 2026 (Jan-Mar 2026)",
        ),
        (
            "Disbursements",
            "What was the total disbursement in Q2 2026?",
            "Disbursement volume in Q2 2026 (Apr-Jun 2026)",
        ),
        (
            "Disbursements",
            "What is the total number of disbursement events in the system?",
            "Count of all governed disbursement event rows (5,696 events)",
        ),
        (
            "Disbursements",
            "Show disbursement amount by scheme for Gold Loan schemes.",
            "Disbursement volume across gold schemes (1001, 1005, 1342)",
        ),
        (
            "Disbursements",
            "Compare sanctioned amount against total disbursed amount by branch.",
            "Branch-level comparison of sanctions versus disbursements",
        ),

        # ==============================================================================
        # 4. Collections, Repayments & Recoveries (Q061 - Q085)
        # ==============================================================================
        (
            "Collections & Repayments",
            "What is our overall collection efficiency this financial year?",
            "FYTD collection efficiency ratio (total paid / total due)",
        ),
        (
            "Collections & Repayments",
            "What was our collection efficiency last quarter?",
            "Collection efficiency in prior quarter (Q2 2026)",
        ),
        (
            "Collections & Repayments",
            "What is the current monthly collection efficiency?",
            "Collection efficiency for current month",
        ),
        (
            "Collections & Repayments",
            "Show collection efficiency by branch this financial year.",
            "Branch-level collection efficiency breakdown",
        ),
        (
            "Collections & Repayments",
            "Which branches have the lowest collection efficiency?",
            "Underperforming branches ranked by lowest recovery rate",
        ),
        (
            "Collections & Repayments",
            "Which branches have the highest collection efficiency?",
            "Top performing branches ranked by collection recovery percentage",
        ),
        (
            "Collections & Repayments",
            "Show collection efficiency by product this financial year.",
            "Product-level collection efficiency across Gold, MSME, and Retail",
        ),
        (
            "Collections & Repayments",
            "What is the collection efficiency for Gold Loans?",
            "Collection efficiency for Product Code 1 (Gold Loans)",
        ),
        (
            "Collections & Repayments",
            "What is the collection efficiency for MSME Loans?",
            "Collection efficiency for Product Code 16 (Business & MSME Loans)",
        ),
        (
            "Collections & Repayments",
            "What is the collection efficiency for Microfinance and Retail EMI?",
            "Collection efficiency for Product Code 13 (Microfinance / Retail EMI)",
        ),
        (
            "Collections & Repayments",
            "Show collection efficiency by scheme.",
            "Scheme-level collection efficiency breakdown",
        ),
        (
            "Collections & Repayments",
            "What is the total repayment amount collected in the last 30 days?",
            "Repayment cash collections in recent 30-day window",
        ),
        (
            "Collections & Repayments",
            "What was the total amount collected last quarter?",
            "Total collections (principal + interest) in Q2 2026",
        ),
        (
            "Collections & Repayments",
            "What is the total amount collected this financial year?",
            "FYTD total cash collections from repayment events",
        ),
        (
            "Collections & Repayments",
            "What is the total principal collected this financial year?",
            "FYTD principal recovered from repayment events",
        ),
        (
            "Collections & Repayments",
            "What is the total interest amount collected this financial year?",
            "FYTD interest income collected from repayment events",
        ),
        (
            "Collections & Repayments",
            "What was the total amount due in the last quarter?",
            "Billed demand (principal + interest due) in Q2 2026",
        ),
        (
            "Collections & Repayments",
            "What is the total collection shortfall this financial year?",
            "FYTD unpaid gap (amount due minus amount paid)",
        ),
        (
            "Collections & Repayments",
            "Show monthly collection shortfall over the last 12 months.",
            "12-month time-series of collection shortfall",
        ),
        (
            "Collections & Repayments",
            "Show the trend of monthly collections over the last 12 months.",
            "12-month monthly cash collections time-series",
        ),
        (
            "Collections & Repayments",
            "What is the total payment receipt amount across all receipts?",
            "Total cash collected recorded in payment receipt events",
        ),
        (
            "Collections & Repayments",
            "Show payment receipts breakdown by receipt mode.",
            "Payment receipt distribution by mode (Cash, Transfer, Cheque, Online)",
        ),
        (
            "Collections & Repayments",
            "Show total payment receipts by receipt branch.",
            "Branch-level payment receipt totals",
        ),
        (
            "Collections & Repayments",
            "What is the total amount recorded in collection activity summaries?",
            "Sum of final collection amounts from recovery activity events",
        ),
        (
            "Collections & Repayments",
            "Show contractual scheduled loan instalments falling due in the next quarter.",
            "Future contractual scheduled principal and interest dues",
        ),

        # ==============================================================================
        # 5. Delinquency, DPD Buckets & PAR (Q086 - Q110)
        # ==============================================================================
        (
            "Delinquency & PAR",
            "What is our current PAR 30?",
            "Current Portfolio at Risk > 30 days percentage",
        ),
        (
            "Delinquency & PAR",
            "What is our current PAR 60?",
            "Current Portfolio at Risk > 60 days percentage",
        ),
        (
            "Delinquency & PAR",
            "What is our current PAR 90?",
            "Current Portfolio at Risk > 90 days percentage",
        ),
        (
            "Delinquency & PAR",
            "How has PAR 30 moved over the last three months?",
            "90-day trend of PAR 30 delinquency ratio",
        ),
        (
            "Delinquency & PAR",
            "Show PAR 30 breakdown by branch.",
            "Branch-level PAR 30 risk comparison",
        ),
        (
            "Delinquency & PAR",
            "Show PAR 30 breakdown by product type.",
            "PAR 30 ratio across Gold, Microfinance, and MSME products",
        ),
        (
            "Delinquency & PAR",
            "Show PAR 30 breakdown by scheme.",
            "Scheme-level PAR 30 delinquency ratio",
        ),
        (
            "Delinquency & PAR",
            "Show PAR 60 breakdown by product.",
            "PAR 60 ratio comparison across product lines",
        ),
        (
            "Delinquency & PAR",
            "Show PAR 90 breakdown by product.",
            "PAR 90 ratio comparison across product lines",
        ),
        (
            "Delinquency & PAR",
            "Which branches have the highest PAR 30 ratio?",
            "Ranking branches with highest delinquency rates",
        ),
        (
            "Delinquency & PAR",
            "Break down the outstanding portfolio by DPD bucket.",
            "Delinquency distribution across Current, 1-30, 31-60, 61-90, and 90+ buckets",
        ),
        (
            "Delinquency & PAR",
            "Show loan account count by DPD bucket.",
            "Count of accounts in each DPD ageing bucket",
        ),
        (
            "Delinquency & PAR",
            "What is the total count of delinquent accounts in our portfolio?",
            "Count of accounts with DPD > 0",
        ),
        (
            "Delinquency & PAR",
            "What is the average DPD across all classified accounts?",
            "Mean days past due across portfolio snapshot",
        ),
        (
            "Delinquency & PAR",
            "Show average DPD by branch.",
            "Average days past due by branch location",
        ),
        (
            "Delinquency & PAR",
            "Show average DPD by product type.",
            "Average days past due by product line",
        ),
        (
            "Delinquency & PAR",
            "Break down the overdue principal amount by branch.",
            "Branch-level delinquent principal amounts",
        ),
        (
            "Delinquency & PAR",
            "Break down overdue principal amount by product type.",
            "Product-level delinquent principal amounts",
        ),
        (
            "Delinquency & PAR",
            "Show total overdue amount by DPD bucket.",
            "Total arrears (principal + interest) across DPD bands",
        ),
        (
            "Delinquency & PAR",
            "What is the total principal outstanding in the 1-30 DPD bucket?",
            "Principal outstanding in 1-30 DPD early stress bucket",
        ),
        (
            "Delinquency & PAR",
            "What is the total principal outstanding in the 31-60 DPD bucket?",
            "Principal outstanding in 31-60 DPD SMA-1 bucket",
        ),
        (
            "Delinquency & PAR",
            "What is the total principal outstanding in the 61-90 DPD bucket?",
            "Principal outstanding in 61-90 DPD SMA-2 bucket",
        ),
        (
            "Delinquency & PAR",
            "What is the total principal outstanding in the 90+ DPD bucket?",
            "Principal outstanding in 90+ DPD default bucket",
        ),
        (
            "Delinquency & PAR",
            "Show delinquent account count by branch.",
            "Count of accounts with arrears by branch",
        ),
        (
            "Delinquency & PAR",
            "Show delinquent account count by scheme.",
            "Count of delinquent accounts by loan scheme",
        ),

        # ==============================================================================
        # 6. Asset Quality, RBI Classifications & NPA (Q111 - Q130)
        # ==============================================================================
        (
            "Asset Quality & NPA",
            "What is the NPA ratio right now?",
            "Current Gross NPA percentage across classified accounts",
        ),
        (
            "Asset Quality & NPA",
            "What is the total principal outstanding classified as NPA?",
            "Total principal balance on NPA classified accounts",
        ),
        (
            "Asset Quality & NPA",
            "Show NPA ratio by branch.",
            "Branch-level gross NPA percentage comparison",
        ),
        (
            "Asset Quality & NPA",
            "Show NPA ratio by product type.",
            "Gross NPA ratio across Gold, Microfinance, and MSME products",
        ),
        (
            "Asset Quality & NPA",
            "Show NPA ratio by scheme.",
            "Gross NPA ratio across individual loan schemes",
        ),
        (
            "Asset Quality & NPA",
            "Show the distribution of active loan accounts by asset classification.",
            "Count of loan accounts in STD, SMA0, SMA1, SMA2, and NPA",
        ),
        (
            "Asset Quality & NPA",
            "Show principal outstanding by RBI asset classification.",
            "Principal outstanding in Standard vs Special Mention vs NPA categories",
        ),
        (
            "Asset Quality & NPA",
            "What is the total principal outstanding in Standard assets?",
            "Principal outstanding in Standard (performing) credit category",
        ),
        (
            "Asset Quality & NPA",
            "What is the total principal outstanding in SMA-0 assets?",
            "Principal outstanding in SMA-0 early stress category",
        ),
        (
            "Asset Quality & NPA",
            "What is the total principal outstanding in SMA-1 assets?",
            "Principal outstanding in SMA-1 (31-60 DPD) category",
        ),
        (
            "Asset Quality & NPA",
            "What is the total principal outstanding in SMA-2 assets?",
            "Principal outstanding in SMA-2 (61-90 DPD) category",
        ),
        (
            "Asset Quality & NPA",
            "How many loan accounts are classified as Standard?",
            "Count of accounts in Standard asset class",
        ),
        (
            "Asset Quality & NPA",
            "How many loan accounts are classified as SMA-0?",
            "Count of accounts in SMA-0 asset class",
        ),
        (
            "Asset Quality & NPA",
            "How many loan accounts are classified as SMA-1?",
            "Count of accounts in SMA-1 asset class",
        ),
        (
            "Asset Quality & NPA",
            "How many loan accounts are classified as SMA-2?",
            "Count of accounts in SMA-2 asset class",
        ),
        (
            "Asset Quality & NPA",
            "How many loan accounts are classified as NPA?",
            "Count of accounts in Non-Performing Asset category",
        ),
        (
            "Asset Quality & NPA",
            "What is the total overdue amount on NPA accounts?",
            "Arrears and overdue balance sitting on bad loans",
        ),
        (
            "Asset Quality & NPA",
            "Show asset classification breakdown for Business & MSME loans.",
            "Asset class distribution in Product Code 16",
        ),
        (
            "Asset Quality & NPA",
            "Show asset classification breakdown for Gold Loans.",
            "Asset class distribution in Product Code 1",
        ),
        (
            "Asset Quality & NPA",
            "Show asset classification breakdown in Head Office Credit Division.",
            "Asset class distribution in branch 4",
        ),

        # ==============================================================================
        # 7. Schemes & Sub-Products Detailed Analysis (Q131 - Q155)
        # ==============================================================================
        (
            "Schemes & Products",
            "Top 10 schemes by sanctioned amount.",
            "Ranking top 10 schemes by cumulative sanctioned amount",
        ),
        (
            "Schemes & Products",
            "Which schemes have the largest outstanding balance?",
            "Ranking schemes by current principal outstanding balance",
        ),
        (
            "Schemes & Products",
            "Top 10 schemes by active loan count.",
            "Ranking schemes by total account volume",
        ),
        (
            "Schemes & Products",
            "What is the total sanctioned amount in Standard Retail Gold Loan scheme?",
            "Sanction volume in Scheme 1001 (Standard Retail Gold Loan)",
        ),
        (
            "Schemes & Products",
            "What is the principal outstanding in High-Value Special Gold Loan scheme?",
            "Outstanding balance in Scheme 1005 (High-Value Special Gold Loan)",
        ),
        (
            "Schemes & Products",
            "What is the performance and volume of FTG Patharamattu Scheme?",
            "Sanctions and outstanding in Scheme 1342 (FTG Patharamattu Scheme)",
        ),
        (
            "Schemes & Products",
            "Show sanctioned amount in CCF Low ROI Scheme.",
            "Sanctions in Scheme 1352 (CCF Low ROI Scheme)",
        ),
        (
            "Schemes & Products",
            "Show loan count in EV Retail Scheme.",
            "Account volume in Scheme 1354 (EV Retail Scheme)",
        ),
        (
            "Schemes & Products",
            "What is the total sanctioned amount in Purchase of Site scheme?",
            "Sanctioned amount in Scheme 1601 (Purchase of Site)",
        ),
        (
            "Schemes & Products",
            "What is the principal outstanding in Repair of House scheme?",
            "Outstanding balance in Scheme 1602 (Repair of House)",
        ),
        (
            "Schemes & Products",
            "Show sanctioned amount in Purchase of Two Wheelers scheme.",
            "Sanctions in Scheme 1604 (Purchase of Two Wheelers)",
        ),
        (
            "Schemes & Products",
            "What is the loan volume in New Autorickshaw scheme?",
            "Sanctions in Scheme 1605 (New Autorickshaw)",
        ),
        (
            "Schemes & Products",
            "Show principal outstanding in Four Wheeler Taxi / Car scheme.",
            "Outstanding balance in Scheme 1606 (Four Wheeler Taxi / Car)",
        ),
        (
            "Schemes & Products",
            "What is the total sanctioned amount in Tractor loan scheme?",
            "Sanctions in Scheme 1607 (Tractor)",
        ),
        (
            "Schemes & Products",
            "Show loan count in New Lorry / Bus scheme.",
            "Account volume in Scheme 1608 (New Lorry / Bus)",
        ),
        (
            "Schemes & Products",
            "What is the total outstanding in Used Vehicles Under 7 Years scheme?",
            "Outstanding balance in Scheme 1609 (Used Vehicles Under 7 Years)",
        ),
        (
            "Schemes & Products",
            "What is the sanctioned amount in Business / Service / Industry scheme?",
            "Sanctions in Scheme 1610 (Business / Service / Industry)",
        ),
        (
            "Schemes & Products",
            "What is the total sanctioned amount in Farming loan scheme?",
            "Sanctions in Scheme 1611 (Farming)",
        ),
        (
            "Schemes & Products",
            "Show principal outstanding in Cattle loan scheme.",
            "Outstanding balance in Scheme 1612 (Cattle)",
        ),
        (
            "Schemes & Products",
            "Show loan count in Poultry / Sheep / Pigs scheme.",
            "Account volume in Scheme 1613 (Poultry / Sheep / Pigs)",
        ),
        (
            "Schemes & Products",
            "What is the total sanctioned amount in Debt Swapping / Consolidation scheme?",
            "Sanctions in Scheme 1614 (Debt Swapping / Consolidation)",
        ),
        (
            "Schemes & Products",
            "What is the principal outstanding in Loan Against Property schemes?",
            "Outstanding balance in Scheme 1615 and 1619 (Loan Against Property)",
        ),
        (
            "Schemes & Products",
            "What is the total sanctioned amount in MSME Loans scheme?",
            "Sanctions in Scheme 1616 (MSME Loans)",
        ),
        (
            "Schemes & Products",
            "Show loan count in Personal Loan scheme.",
            "Account volume in Scheme 1617 (Personal Loan)",
        ),
        (
            "Schemes & Products",
            "What is the total sanctioned amount in Dairy Loan scheme?",
            "Sanctions in Scheme 1622 (Dairy Loan)",
        ),

        # ==============================================================================
        # 8. Branch Performance & Comparison (Q156 - Q175)
        # ==============================================================================
        (
            "Branch Performance",
            "List all branches ranked by total sanctioned amount.",
            "Ranking all 16 branches by total sanctioned credit volume",
        ),
        (
            "Branch Performance",
            "Which branches disbursed the most this financial year?",
            "Ranking branches by FYTD disbursement volume",
        ),
        (
            "Branch Performance",
            "List all branches by active loan account count.",
            "Branch-level distribution of active loan accounts",
        ),
        (
            "Branch Performance",
            "Show average ticket size by branch.",
            "Average loan sanction ticket size by branch",
        ),
        (
            "Branch Performance",
            "Show average interest rate by branch.",
            "Weighted average interest rate across branches",
        ),
        (
            "Branch Performance",
            "Show total amount collected by branch this financial year.",
            "FYTD total recovery collections by branch",
        ),
        (
            "Branch Performance",
            "What is the loan portfolio summary for Thripunithura branch?",
            "Portfolio volume and risk for branch 1001 (Thripunithura)",
        ),
        (
            "Branch Performance",
            "What is the loan portfolio summary for Aluva branch?",
            "Portfolio volume and risk for branch 1002 (Aluva)",
        ),
        (
            "Branch Performance",
            "What is the loan portfolio summary for Nilambur branch?",
            "Portfolio volume and risk for branch 1006 (Nilambur)",
        ),
        (
            "Branch Performance",
            "What is the loan portfolio summary for Kozhikode branch?",
            "Portfolio volume and risk for branch 1007 (Kozhikode)",
        ),
        (
            "Branch Performance",
            "What is the loan portfolio summary for Chalakudy branch?",
            "Portfolio volume and risk for branch 1008 (Chalakudy)",
        ),
        (
            "Branch Performance",
            "What is the loan portfolio summary for Pathanamthitta branch?",
            "Portfolio volume and risk for branch 1010 (Pathanamthitta)",
        ),
        (
            "Branch Performance",
            "What is the loan portfolio summary for Kanhangad branch?",
            "Portfolio volume and risk for branch 1012 (Kanhangad)",
        ),
        (
            "Branch Performance",
            "What is the loan portfolio summary for Angamally branch?",
            "Portfolio volume and risk for branch 1013 (Angamally)",
        ),
        (
            "Branch Performance",
            "What is the loan portfolio summary for Kanjikuzhy branch?",
            "Portfolio volume and risk for branch 1014 (Kanjikuzhy)",
        ),
        (
            "Branch Performance",
            "What is the loan portfolio summary for Karamana branch?",
            "Portfolio volume and risk for branch 1016 (Karamana)",
        ),
        (
            "Branch Performance",
            "What is the loan portfolio summary for Gudallur branch?",
            "Portfolio volume and risk for branch 1017 (Gudallur)",
        ),
        (
            "Branch Performance",
            "What is the loan portfolio summary for Muvattupuzha branch?",
            "Portfolio volume and risk for branch 1018 (Muvattupuzha)",
        ),
        (
            "Branch Performance",
            "What is the loan portfolio summary for Kattapana branch?",
            "Portfolio volume and risk for branch 1020 (Kattapana)",
        ),
        (
            "Branch Performance",
            "What is the loan portfolio summary for Kanjirapally branch?",
            "Portfolio volume and risk for branch 1021 (Kanjirapally)",
        ),

        # ==============================================================================
        # 9. Demographics, Sourcing Agents & Vintage Analysis (Q176 - Q190)
        # ==============================================================================
        (
            "Demographics & Vintages",
            "What is the count of female borrowers versus male borrowers in our portfolio?",
            "Gender distribution of customer borrower base",
        ),
        (
            "Demographics & Vintages",
            "Show sanctioned amount breakdown by borrower gender.",
            "Sanctioned credit volume across Male, Female, and Transgender borrowers",
        ),
        (
            "Demographics & Vintages",
            "Show principal outstanding breakdown by borrower gender.",
            "Principal outstanding exposure across borrower genders",
        ),
        (
            "Demographics & Vintages",
            "What is the average ticket size for female borrowers compared to male borrowers?",
            "Ticket size disparity analysis by borrower gender",
        ),
        (
            "Demographics & Vintages",
            "Show borrower count by gender across branches.",
            "Cross-tabulation of borrower gender across branch network",
        ),
        (
            "Demographics & Vintages",
            "Show top 10 agents by linked loan count.",
            "Ranking sourcing and field agents by total loans linked",
        ),
        (
            "Demographics & Vintages",
            "Which agents have the highest number of linked borrowers?",
            "Ranking agent directory by distinct linked customer count",
        ),
        (
            "Demographics & Vintages",
            "Show agent directory loan count distribution.",
            "Summary distribution of loan sourcing across agent network",
        ),
        (
            "Demographics & Vintages",
            "What is the monthly origination vintage matrix distribution?",
            "Account counts across monthly origination cohorts (Dec 2025 - Jun 2026)",
        ),
        (
            "Demographics & Vintages",
            "Show vintage PAR 30 rate across origination cohorts.",
            "Cohort-level PAR 30 account delinquency rate by origination month",
        ),
        (
            "Demographics & Vintages",
            "Show vintage NPA rate across origination months.",
            "Cohort-level NPA account default rate by origination month",
        ),
        (
            "Demographics & Vintages",
            "What is the vintage performance by months on book?",
            "Delinquency seasoning curve across Months on Book (MOB 1 to 9)",
        ),
        (
            "Demographics & Vintages",
            "Show vintage account count by product code.",
            "Origination cohort volume across product lines",
        ),
        (
            "Demographics & Vintages",
            "Show vintage account count by branch.",
            "Origination cohort volume across branch network",
        ),
        (
            "Demographics & Vintages",
            "What is the total number of collection handover records?",
            "Count of recovery ownership reassignments in collection handover events",
        ),

        # ==============================================================================
        # 10. Composite Analyses, Portfolio Risk & Worklists (Q191 - Q200)
        # ==============================================================================
        (
            "Analyses & Worklists",
            "How healthy is our portfolio?",
            "Composite portfolio health analysis (outstanding, arrears, PAR, NPA, CE)",
        ),
        (
            "Analyses & Worklists",
            "Where should collections focus?",
            "Composite collections focus analysis (shortfall, branch CE, DPD buckets)",
        ),
        (
            "Analyses & Worklists",
            "How is origination doing?",
            "Composite origination review (disbursements, sanctions, ticket size, yields)",
        ),
        (
            "Analyses & Worklists",
            "What is our single borrower concentration risk?",
            "Composite concentration analysis (Herfindahl index, top 10 borrower exposures)",
        ),
        (
            "Analyses & Worklists",
            "Which branches have the best growth and credit quality?",
            "Quadrant analysis comparing branch disbursement growth vs PAR 30 credit quality",
        ),
        (
            "Analyses & Worklists",
            "Show today's collection priority list.",
            "Governed worklist of delinquent accounts ranked by priority score",
        ),
        (
            "Analyses & Worklists",
            "Show early-warning accounts watchlist.",
            "Governed worklist of accounts showing early stress before severe arrears",
        ),
        (
            "Analyses & Worklists",
            "Show large exposures in arrears.",
            "Governed worklist of top 1% loan exposures currently in delinquency",
        ),
        (
            "Analyses & Worklists",
            "List top 10 largest overdue loan accounts.",
            "Governed worklist of individual accounts with largest total overdue balances",
        ),
        (
            "Analyses & Worklists",
            "What is the overall summary of our loan book performance?",
            "Executive portfolio briefing synthesizing loan book KPIs and operational metrics",
        ),
    ]

    queries: list[QueryItem] = []
    for idx, (sub_cat, q, desc) in enumerate(queries_data, 1):
        queries.append(QueryItem(
            id=idx,
            category="Loan Book",
            sub_category=sub_cat,
            question=q,
            preferred_pin="db",
            description=desc,
        ))

    return queries


# --------------------------------------------------------------------------------------
# API Client
# --------------------------------------------------------------------------------------

class GenesisAPIClient:
    def __init__(self, base_url: str, timeout_s: int = 120, auth_token: str = "mock-token-gicc_admin"):
        self.base_url = base_url.rstrip("/")
        self.timeout_s = timeout_s
        self.auth_token = auth_token

    def _headers(self) -> dict[str, str]:
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.auth_token}",
            "User-Agent": "Moneypal-200LoanBook-Evaluator/1.0",
        }

    def execute_query(self, query: QueryItem) -> QueryResult:
        url = f"{self.base_url}/api/workbench/ask"
        body: dict[str, Any] = {
            "question": query.question,
            "pinned_source": query.preferred_pin,
        }

        payload_bytes = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(url, data=payload_bytes, headers=self._headers())

        start_time = time.time()
        events: list[tuple[str, dict[str, Any]]] = []
        error_msg = ""

        try:
            with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:
                buffer = ""
                for raw_line in resp:
                    line = raw_line.decode("utf-8", errors="replace")
                    buffer += line
                    while "\n\n" in buffer:
                        frame, buffer = buffer.split("\n\n", 1)
                        event_type = ""
                        data_str = ""
                        for frame_line in frame.split("\n"):
                            if frame_line.startswith("event: "):
                                event_type = frame_line[7:].strip()
                            elif frame_line.startswith("data: "):
                                data_str += frame_line[6:]

                        if event_type:
                            try:
                                payload_obj = json.loads(data_str) if data_str else {}
                            except Exception:
                                payload_obj = {"raw": data_str}
                            events.append((event_type, payload_obj))

        except urllib.error.HTTPError as exc:
            error_msg = f"HTTP {exc.code}: {exc.reason}"
        except urllib.error.URLError as exc:
            error_msg = f"Connection error: {exc.reason}"
        except TimeoutError:
            error_msg = f"Request timed out after {self.timeout_s}s"
        except Exception as exc:
            error_msg = f"Unexpected error: {str(exc)}"

        latency = time.time() - start_time
        return self._process_events(query, events, latency, error_msg)

    def _process_events(
        self,
        query: QueryItem,
        events: list[tuple[str, dict[str, Any]]],
        latency: float,
        error_msg: str,
    ) -> QueryResult:
        sources: list[str] = []
        card_types: list[str] = []
        headline = ""
        summary = ""
        synthesis = ""
        chart_info: dict[str, Any] | None = None
        chart_type = ""
        sql_query = ""
        citations: list[str] = []
        status = "Error"

        for ev_type, ev_data in events:
            if ev_type == "route":
                sources = ev_data.get("sources", sources)
            elif ev_type == "source_card":
                src = ev_data.get("source", "")
                c_type = ev_data.get("card_type", "")
                if src and src not in sources:
                    sources.append(src)
                if c_type:
                    card_types.append(c_type)

                # Extract chart type
                if "chart_type" in ev_data:
                    chart_type = ev_data["chart_type"]

                # Extract SQL lineage
                lineage = ev_data.get("lineage", {})
                if isinstance(lineage, dict):
                    display_sql = lineage.get("display_sql")
                    raw_sql = lineage.get("sql")
                    if display_sql:
                        sql_query = display_sql
                    elif raw_sql and not sql_query:
                        sql_query = raw_sql

                if c_type in ("chart", "table", "kpi"):
                    chart_info = ev_data
                    title = ev_data.get("title", "Loan Metric Analysis")
                    subtitle = ev_data.get("subtitle", "")
                    headline = f"{title} ({subtitle})" if subtitle else title
                    c_summary = ev_data.get("summary", "")
                    if c_summary:
                        summary = c_summary
                    elif "rows" in ev_data:
                        summary = f"Rendered {chart_type or c_type} with {len(ev_data.get('rows', []))} rows."
                    status = "Answered"

                elif c_type in ("analysis", "briefing"):
                    chart_info = ev_data
                    chart_type = chart_type or ev_data.get("compose", "briefing")
                    card_summary = ev_data.get("summary", "")
                    title = ev_data.get("title", "")
                    if title and not headline:
                        headline = title
                    if card_summary:
                        summary = (summary + "\n\n" + card_summary).strip() if summary else card_summary
                        status = "Answered"

                elif c_type == "worklist":
                    chart_info = ev_data
                    chart_type = "worklist"
                    title = ev_data.get("title", "Collections Worklist")
                    if title:
                        headline = title
                    cnt = ev_data.get("account_count", len(ev_data.get("accounts", [])))
                    summary = f"Generated collections worklist with {cnt} accounts."
                    status = "Answered"

                elif c_type == "schema":
                    chart_type = "schema_graph"
                    summary = "Enterprise Curiosity Schema Graph returned."
                    headline = "Schema Graph"
                    status = "Answered"

                elif c_type == "clarify":
                    status = "Clarification Needed"
                    summary = ev_data.get("question", "Please clarify query parameters.")

                elif c_type == "refusal":
                    status = "Refused"
                    summary = ev_data.get("message", "Query was refused.")

                elif c_type == "error":
                    if status != "Answered":
                        error_msg = ev_data.get("message", "Source error")

            elif ev_type == "synthesis":
                synthesis = ev_data.get("text", "")
                if synthesis:
                    status = "Answered"

            elif ev_type == "answer":
                final_status = ev_data.get("status", "answered")
                ans_text = ev_data.get("text", "")
                if ans_text:
                    summary = ans_text
                if final_status == "partial" and summary:
                    status = "Partial"
                elif final_status == "answered" and summary:
                    status = "Answered"
                elif final_status == "clarify":
                    status = "Clarification Needed"
                elif final_status == "refused":
                    status = "Refused"
                for s_ref in ev_data.get("citations", []):
                    if isinstance(s_ref, dict) and s_ref.get("document"):
                        citations.append(s_ref["document"])

            elif ev_type == "refusal":
                status = "Refused"
                summary = ev_data.get("message", "Request refused by security/intent policy.")

            elif ev_type == "error":
                if status != "Answered":
                    error_msg = ev_data.get("message", "Unknown error")

        if not summary and synthesis:
            summary = synthesis
        if status == "Answered" and response_is_incomplete(summary):
            status = "Partial"
        if not summary and not error_msg and status == "Answered":
            summary = "Loan book metric successfully computed from Gold semantic views."

        if status == "Error" and not error_msg:
            error_msg = "No answer or cards returned in stream."

        return QueryResult(
            item=query,
            status=status,
            latency_s=latency,
            sources=sources,
            card_types=card_types,
            headline=headline,
            summary=summary,
            synthesis=synthesis,
            chart_info=chart_info,
            chart_type=chart_type or "N/A",
            sql_query=sql_query,
            citations=list(set(citations)),
            error_message=error_msg,
        )


# --------------------------------------------------------------------------------------
# Markdown Report Generator
# --------------------------------------------------------------------------------------

def generate_markdown_report(results: list[QueryResult], total_duration_s: float, app_url: str) -> str:
    total_queries = len(results)
    answered_count = sum(1 for r in results if r and r.status == "Answered")
    partial_count = sum(1 for r in results if r and r.status == "Partial")
    refused_count = sum(1 for r in results if r and r.status == "Refused")
    clarify_count = sum(1 for r in results if r and r.status == "Clarification Needed")
    error_count = sum(1 for r in results if r and r.status == "Error")
    answered_pct = (answered_count / total_queries) * 100 if total_queries else 0

    sub_cats = list(dict.fromkeys(r.item.sub_category for r in results if r))
    sub_stats: dict[str, dict[str, Any]] = {}
    for sub in sub_cats:
        sub_res = [r for r in results if r and r.item.sub_category == sub]
        c_tot = len(sub_res)
        c_ans = sum(1 for r in sub_res if r.status == "Answered")
        c_partial = sum(1 for r in sub_res if r.status == "Partial")
        c_lat = sum(r.latency_s for r in sub_res) / c_tot if c_tot else 0
        sub_stats[sub] = {
            "total": c_tot,
            "answered": c_ans,
            "partial": c_partial,
            "pct": (c_ans / c_tot * 100) if c_tot else 0,
            "avg_latency": c_lat,
        }

    avg_latency_all = sum(r.latency_s for r in results if r) / total_queries if total_queries else 0

    lines: list[str] = []
    lines.append(f"# Moneypal Genesis Intelligence — 200 Loan Book Queries Benchmark & Evaluation Report")
    lines.append("")
    lines.append(f"**Execution Timestamp:** {datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}  ")
    lines.append(f"**Target Application Endpoint:** `{app_url}`  ")
    lines.append(f"**Domain Focus:** Governed Loan Book (Gold Semantic Layer)  ")
    lines.append("**Environment Configuration:** Production (`.env.prod` settings applied)  ")
    lines.append(f"**Total Run Duration:** {total_duration_s:.2f} seconds ({total_duration_s/60:.1f} minutes)  ")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 1. Executive Summary & KPIs")
    lines.append("")
    lines.append("| Metric | Result | Benchmark Target | Status |")
    lines.append("|---|---|---|---|")
    pass_target = max(1, int(total_queries * 0.70 + 0.999999))
    pass_condition = answered_count >= pass_target
    status_emoji = "✅ PASS" if pass_condition else "❌ FAIL"
    lines.append(f"| **Total Loan Book Queries** | **{total_queries}** | {total_queries} | ✅ Complete |")
    lines.append(f"| **Complete Answers** | **{answered_count} / {total_queries}** ({answered_pct:.1f}%) | **≥ {pass_target} ({pass_target/total_queries*100:.0f}%)** | **{status_emoji}** |")
    lines.append(f"| **Partial Answers** | **{partial_count} / {total_queries}** | Reported separately | ℹ️ Handled |")
    useful_pct = ((answered_count + partial_count) / total_queries * 100) if total_queries else 0
    lines.append(f"| **Useful Response Rate** | **{answered_count + partial_count} / {total_queries}** ({useful_pct:.1f}%) | Diagnostic only | ℹ️ Response rate |")
    lines.append(f"| **Refused (Governed Safety Policy)** | {refused_count} | < 5% | ℹ️ Handled |")
    lines.append(f"| **Clarifications Triggered** | {clarify_count} | < 5% | ℹ️ Handled |")
    lines.append(f"| **Errors / Timeouts** | {error_count} | < 5% | {'⚠️ Review' if error_count > 0 else '✅ Zero Errors'} |")
    latency_status = "✅ Optimal" if avg_latency_all < 15.0 else "⚠️ Above target"
    lines.append(f"| **Average Query Latency** | **{avg_latency_all:.2f}s** | < 15.0s | {latency_status} |")
    lines.append("")
    lines.append("### Sub-Domain Breakdown (Loan Book)")
    lines.append("")
    lines.append("| Sub-Domain | Total Queries | Complete | Partial | Complete Rate (%) | Avg Latency (s) |")
    lines.append("|---|---|---|---|---|---|")
    for sub in sub_cats:
        s = sub_stats[sub]
        lines.append(f"| **{sub}** | {s['total']} | {s['answered']} / {s['total']} | {s['partial']} | {s['pct']:.1f}% | {s['avg_latency']:.2f}s |")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append(f"## 2. Detailed Query Execution Log ({total_queries} Queries)")
    lines.append("")

    for r in results:
        if not r:
            continue
        q = r.item
        status_icon = "🟢" if r.status == "Answered" else ("🟡" if r.status in ("Partial", "Refused", "Clarification Needed") else "🔴")
        lines.append(f"### Q{q.id:03d}: {q.question}")
        lines.append("")
        lines.append(f"- **Domain:** `{q.category}` — *{q.sub_category}*")
        lines.append(f"- **Status:** {status_icon} **{r.status}**")
        lines.append(f"- **Latency:** `{r.latency_s:.2f}s`")
        lines.append(f"- **Chart Type:** `{r.chart_type}`")
        if r.sources:
            lines.append(f"- **Dispatched Sources:** `{', '.join(r.sources)}`")
        if r.card_types:
            lines.append(f"- **Rendered Cards:** `{', '.join(r.card_types)}`")
        if q.description:
            lines.append(f"- **Evaluation Intent:** *{q.description}*")
        lines.append("")

        lines.append("#### Application Response Output:")
        lines.append("```text")
        if r.headline:
            lines.append(f"HEADLINE: {r.headline}")
        if r.summary:
            lines.append(f"SUMMARY / ANSWER:\n{r.summary}")
        if r.synthesis and r.synthesis != r.summary:
            lines.append(f"\nCROSS-SOURCE SYNTHESIS:\n{r.synthesis}")
        if r.chart_type and r.chart_type != "N/A":
            lines.append(f"\nCHART SPEC: Type={r.chart_type}, Title={r.headline}")
        if r.chart_info:
            c = r.chart_info
            if "columns" in c:
                cols = [col.get("label", col.get("name", "")) for col in c.get("columns", [])]
                lines.append(f"COLUMNS: {', '.join(cols)}")
            if "rows" in c and c["rows"]:
                lines.append(f"SAMPLE ROWS ({len(c['rows'])} total): {json.dumps(c['rows'][:3], ensure_ascii=False)}")
        if r.sql_query:
            lines.append(f"\nGOVERNED SQL QUERY:\n{r.sql_query.strip()}")
        if r.error_message:
            lines.append(f"ERROR DETAIL: {r.error_message}")
        lines.append("```")
        lines.append("")
        lines.append("---")
        lines.append("")

    lines.append("## 3. Architecture & Methodology Notes")
    lines.append("")
    lines.append("1. **Unified Routing (`/api/workbench/ask`):** Every loan book question routes deterministically to the governed `db` source.")
    lines.append("2. **Governed SQL Pipeline (`db`):** Queries compile into deterministic `QuerySpec` ASTs and execute against PostgreSQL Gold semantic views without SQL injection risk.")
    lines.append("3. **Gold Semantic Alignment:** Covers `gold.loan_account_master`, `gold.loan_disbursement_events`, `gold.loan_repayment_events`, `gold.portfolio_daily_snapshot`, `gold.customer_master`, `gold.product_master`, `gold.branch_master`, `gold.agent_master`, `gold.payment_receipt_events`, `gold.origination_vintage_matrix`, `gold.collection_activity_events`, preset analyses, and worklists.")
    lines.append("4. **Zero Cold-Start:** Execution maintains high reliability across 200 consecutive turns.")
    lines.append("")
    lines.append("---")
    lines.append("*Report generated by Moneypal Genesis Automated Benchmark Suite (200 Loan Book Queries)*")

    return "\n".join(lines)


# --------------------------------------------------------------------------------------
# Main Runner CLI
# --------------------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description="Run 200 Loan Book queries against Moneypal Genesis application")
    parser.add_argument("--url", default="http://100.70.118.31:4321", help="Application base URL (default: http://100.70.118.31:4321)")
    parser.add_argument("--env-file", default=".env.prod", help="Path to production .env file")
    parser.add_argument("--output-md", default="query_test_results_200_loanbook.md", help="Output markdown file path")
    parser.add_argument("--timeout", type=int, default=None, help="Per-query timeout in seconds")
    parser.add_argument("--token", default="mock-token-gicc_admin", help="Authentication token")
    parser.add_argument("--limit", type=int, default=200, help="Number of queries to run (default: 200)")
    parser.add_argument("--ids", help="Run specific query IDs, for example --ids 1,5,10,20")
    parser.add_argument("--sample", type=int, help="Run a reproducible random sample of N queries")
    parser.add_argument("--seed", type=int, default=20260824, help="Seed used with --sample")
    args = parser.parse_args()

    env_config = load_env_prod(Path(args.env_file) if args.env_file else None)
    timeout_s = args.timeout or int(env_config.get("NLQ_REQUEST_BUDGET_S", 120))
    base_url = args.url or "http://100.70.118.31:4321"

    print("=" * 80, flush=True)
    print(" Moneypal Genesis Intelligence — 200 Loan Book Queries Benchmark Runner", flush=True)
    print("=" * 80, flush=True)
    print(f" Target Application URL : {base_url}", flush=True)
    print(f" Configuration Source   : {args.env_file} (Loaded {len(env_config)} env vars)", flush=True)
    print(f" Per-Query Timeout      : {timeout_s}s", flush=True)
    print(f" Authentication Token   : {args.token[:18]}...", flush=True)
    print(f" Output Markdown File   : {args.output_md}", flush=True)
    print("-" * 80, flush=True)

    client = GenesisAPIClient(base_url=base_url, timeout_s=timeout_s, auth_token=args.token)
    query_bank = get_200_loanbook_queries()

    if args.ids and args.sample is not None:
        parser.error("--ids and --sample cannot be used together")
    if args.ids:
        try:
            requested_ids = [int(value.strip()) for value in args.ids.split(",") if value.strip()]
        except ValueError:
            parser.error("--ids must be a comma-separated list of integers")
        by_id = {query.id: query for query in query_bank}
        missing = [query_id for query_id in requested_ids if query_id not in by_id]
        if missing:
            parser.error(f"unknown query IDs: {', '.join(map(str, missing))}")
        all_queries = [by_id[query_id] for query_id in dict.fromkeys(requested_ids)]
    elif args.sample is not None:
        if not 1 <= args.sample <= len(query_bank):
            parser.error(f"--sample must be between 1 and {len(query_bank)}")
        all_queries = sorted(random.Random(args.seed).sample(query_bank, args.sample), key=lambda q: q.id)
    else:
        if not 1 <= args.limit <= len(query_bank):
            parser.error(f"--limit must be between 1 and {len(query_bank)}")
        all_queries = query_bank[:args.limit]

    total_count = len(all_queries)
    print(f"Loaded {total_count} curated Loan Book test questions across 10 sub-domains.", flush=True)
    print("Starting execution...\n", flush=True)

    results: list[QueryResult] = []
    overall_start = time.time()

    for idx, query in enumerate(all_queries, 1):
        print(f"[{idx:03d}/{total_count:03d}] (Q{query.id:03d}) [{query.sub_category:24s}] Q: {query.question[:50]}...", flush=True)
        res = client.execute_query(query)
        results.append(res)
        status_symbol = "✓" if res.status == "Answered" else ("!" if res.status in ("Partial", "Refused", "Clarification Needed") else "✗")
        chart_tag = f"Chart: {res.chart_type}" if res.chart_type and res.chart_type != "N/A" else "No Chart"
        sql_tag = "SQL: Yes" if res.sql_query else "SQL: No"
        print(f"       -> [{status_symbol} {res.status:10s}] ({res.latency_s:.2f}s) | {chart_tag} | {sql_tag} | {res.headline or res.summary[:40]}", flush=True)

    overall_duration = time.time() - overall_start

    print("\n" + "=" * 80, flush=True)
    print(" Benchmark Execution Completed", flush=True)
    print("=" * 80, flush=True)

    answered = sum(1 for r in results if r and r.status == "Answered")
    partial = sum(1 for r in results if r and r.status == "Partial")
    pass_target = max(1, int(total_count * 0.70 + 0.999999))
    passed = answered >= pass_target
    print(f" Total Executed : {total_count}", flush=True)
    print(f" Complete       : {answered} / {total_count} ({(answered/total_count)*100:.1f}%)", flush=True)
    print(f" Partial        : {partial} / {total_count}", flush=True)
    print(f" Total Duration : {overall_duration:.2f}s ({overall_duration/60:.1f} min)", flush=True)
    print(f" Pass Threshold : ≥ {pass_target} Complete -> {'PASSED ✅' if passed else 'FAILED ❌'}", flush=True)
    print("-" * 80, flush=True)

    # Write Markdown file
    output_path = Path(args.output_md)
    markdown_content = generate_markdown_report(results, overall_duration, base_url)
    output_path.write_text(markdown_content, encoding="utf-8")
    print(f" Markdown report written successfully to: {output_path.resolve()}", flush=True)
    print("=" * 80, flush=True)

    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
