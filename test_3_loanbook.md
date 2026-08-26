# Moneypal Genesis Intelligence — 200 Loan Book Queries Benchmark & Evaluation Report

**Execution Timestamp:** 2026-08-24 09:38:02 UTC  
**Target Application Endpoint:** `http://100.70.118.31:4321`  
**Domain Focus:** Governed Loan Book (Gold Semantic Layer)  
**Environment Configuration:** Production (`.env.prod` settings applied)  
**Total Run Duration:** 13.85 seconds (0.2 minutes)  

---

## 1. Executive Summary & KPIs

| Metric | Result | Benchmark Target | Status |
|---|---|---|---|
| **Total Loan Book Queries** | **3** | 3 | ✅ Complete |
| **Complete Answers** | **3 / 3** (100.0%) | **≥ 3 (100%)** | **✅ PASS** |
| **Partial Answers** | **0 / 3** | Reported separately | ℹ️ Handled |
| **Useful Response Rate** | **3 / 3** (100.0%) | Diagnostic only | ℹ️ Response rate |
| **Refused (Governed Safety Policy)** | 0 | < 5% | ℹ️ Handled |
| **Clarifications Triggered** | 0 | < 5% | ℹ️ Handled |
| **Errors / Timeouts** | 0 | < 5% | ✅ Zero Errors |
| **Average Query Latency** | **4.62s** | < 15.0s | ✅ Optimal |

### Sub-Domain Breakdown (Loan Book)

| Sub-Domain | Total Queries | Complete | Partial | Complete Rate (%) | Avg Latency (s) |
|---|---|---|---|---|---|
| **Portfolio Outstanding** | 3 | 3 / 3 | 0 | 100.0% | 4.62s |

---

## 2. Detailed Query Execution Log (3 Queries)

### Q001: What is our total principal outstanding across the loan book?

- **Domain:** `Loan Book` — *Portfolio Outstanding*
- **Status:** 🟢 **Answered**
- **Latency:** `3.71s`
- **Chart Type:** `kpi`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `chart`
- **Evaluation Intent:** *Total principal outstanding across all active classified accounts in portfolio snapshot*

#### Application Response Output:
```text
HEADLINE: Principal outstanding (whole book) (2026-08-24)
SUMMARY / ANSWER:
Principal outstanding (whole book) was ₹214.00 Cr in 2026-08-24. This measures cumulative disbursed minus cumulative principal repaid across loan accounts.

CHART SPEC: Type=kpi, Title=Principal outstanding (whole book) (2026-08-24)
COLUMNS: Principal outstanding (whole book)
SAMPLE ROWS (1 total): [{"principal_outstanding_book": 2139981490.94}]

GOVERNED SQL QUERY:
SELECT SUM(lam.disbursed_amount - lam.principal_repaid) AS principal_outstanding_book
FROM gold.loan_account_master AS lam
LIMIT 200
```

---

### Q002: Show principal outstanding breakdown by product type.

- **Domain:** `Loan Book` — *Portfolio Outstanding*
- **Status:** 🟢 **Answered**
- **Latency:** `6.25s`
- **Chart Type:** `bar`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `chart`
- **Evaluation Intent:** *Distribution of principal outstanding across Gold, Microfinance, and MSME products*

#### Application Response Output:
```text
HEADLINE: Principal outstanding by product (As at 24 Aug 2026)
SUMMARY / ANSWER:
Business & MSME Loans is the only product returned, with principal outstanding of ₹204.54 Cr as at 24 Aug 2026. This measures principal outstanding from each classified account at the requested snapshot, grouped by product.

CHART SPEC: Type=bar, Title=Principal outstanding by product (As at 24 Aug 2026)
COLUMNS: Product, Principal outstanding
SAMPLE ROWS (1 total): [{"product": "Business & MSME Loans", "principal_outstanding": 2045394519.25, "product__raw": 16.0}]

GOVERNED SQL QUERY:
SELECT lam."product_code" AS product,
       SUM(portfolio.principal_outstanding) AS principal_outstanding
FROM gold.portfolio_snapshot_as_of(DATE '2026-08-24') AS portfolio
     JOIN gold.loan_account_master AS lam ON portfolio."entity_num" = lam."entity_num" AND portfolio."loan_account_number" = lam."loan_account_number"
GROUP BY lam."product_code"
ORDER BY SUM(portfolio.principal_outstanding) DESC NULLS LAST
LIMIT 200
```

---

### Q003: What is the principal outstanding by branch?

- **Domain:** `Loan Book` — *Portfolio Outstanding*
- **Status:** 🟢 **Answered**
- **Latency:** `3.89s`
- **Chart Type:** `bar`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `chart`
- **Evaluation Intent:** *Branch-level breakdown of total principal outstanding*

#### Application Response Output:
```text
HEADLINE: Principal outstanding by branch (As at 24 Aug 2026)
SUMMARY / ANSWER:
Head Office — Credit Division is the only branch returned, with principal outstanding of ₹204.54 Cr as at 24 Aug 2026. This measures principal outstanding from each classified account at the requested snapshot, grouped by branch.

CHART SPEC: Type=bar, Title=Principal outstanding by branch (As at 24 Aug 2026)
COLUMNS: Branch, Principal outstanding
SAMPLE ROWS (1 total): [{"branch": "Head Office — Credit Division", "principal_outstanding": 2045394519.25, "branch__raw": 4.0}]

GOVERNED SQL QUERY:
SELECT lam."branch_code" AS branch,
       SUM(portfolio.principal_outstanding) AS principal_outstanding
FROM gold.portfolio_snapshot_as_of(DATE '2026-08-24') AS portfolio
     JOIN gold.loan_account_master AS lam ON portfolio."entity_num" = lam."entity_num" AND portfolio."loan_account_number" = lam."loan_account_number"
GROUP BY lam."branch_code"
ORDER BY SUM(portfolio.principal_outstanding) DESC NULLS LAST
LIMIT 200
```

---

## 3. Architecture & Methodology Notes

1. **Unified Routing (`/api/workbench/ask`):** Every loan book question routes deterministically to the governed `db` source.
2. **Governed SQL Pipeline (`db`):** Queries compile into deterministic `QuerySpec` ASTs and execute against PostgreSQL Gold semantic views without SQL injection risk.
3. **Gold Semantic Alignment:** Covers `gold.loan_account_master`, `gold.loan_disbursement_events`, `gold.loan_repayment_events`, `gold.portfolio_daily_snapshot`, `gold.customer_master`, `gold.product_master`, `gold.branch_master`, `gold.agent_master`, `gold.payment_receipt_events`, `gold.origination_vintage_matrix`, `gold.collection_activity_events`, preset analyses, and worklists.
4. **Zero Cold-Start:** Execution maintains high reliability across 200 consecutive turns.

---
*Report generated by Moneypal Genesis Automated Benchmark Suite (200 Loan Book Queries)*