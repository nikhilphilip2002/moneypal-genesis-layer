# Moneypal Genesis Intelligence — 200 Loan Book Queries Benchmark & Evaluation Report

**Execution Timestamp:** 2026-08-24 11:03:28 UTC  
**Target Application Endpoint:** `http://100.70.118.31:4321`  
**Domain Focus:** Governed Loan Book (Gold Semantic Layer)  
**Environment Configuration:** Production (`.env.prod` settings applied)  
**Total Run Duration:** 5110.58 seconds (85.2 minutes)  

---

## 1. Executive Summary & KPIs

| Metric | Result | Benchmark Target | Status |
|---|---|---|---|
| **Total Loan Book Queries** | **200** | 200 | ✅ Complete |
| **Complete Answers** | **163 / 200** (81.5%) | **≥ 140 (70%)** | **✅ PASS** |
| **Partial Answers** | **0 / 200** | Reported separately | ℹ️ Handled |
| **Useful Response Rate** | **163 / 200** (81.5%) | Diagnostic only | ℹ️ Response rate |
| **Refused (Governed Safety Policy)** | 3 | < 5% | ℹ️ Handled |
| **Clarifications Triggered** | 2 | < 5% | ℹ️ Handled |
| **Errors / Timeouts** | 32 | < 5% | ⚠️ Review |
| **Average Query Latency** | **25.55s** | < 15.0s | ⚠️ Above target |

### Sub-Domain Breakdown (Loan Book)

| Sub-Domain | Total Queries | Complete | Partial | Complete Rate (%) | Avg Latency (s) |
|---|---|---|---|---|---|
| **Portfolio Outstanding** | 20 | 15 / 20 | 0 | 75.0% | 32.85s |
| **Origination & Sanctions** | 20 | 20 / 20 | 0 | 100.0% | 5.71s |
| **Disbursements** | 20 | 16 / 20 | 0 | 80.0% | 29.31s |
| **Collections & Repayments** | 25 | 23 / 25 | 0 | 92.0% | 15.27s |
| **Delinquency & PAR** | 25 | 22 / 25 | 0 | 88.0% | 18.84s |
| **Asset Quality & NPA** | 20 | 10 / 20 | 0 | 50.0% | 59.94s |
| **Schemes & Products** | 25 | 12 / 25 | 0 | 48.0% | 51.24s |
| **Branch Performance** | 20 | 20 / 20 | 0 | 100.0% | 6.87s |
| **Demographics & Vintages** | 15 | 15 / 15 | 0 | 100.0% | 15.75s |
| **Analyses & Worklists** | 10 | 10 / 10 | 0 | 100.0% | 4.67s |

---

## 2. Detailed Query Execution Log (200 Queries)

### Q001: What is our total principal outstanding across the loan book?

- **Domain:** `Loan Book` — *Portfolio Outstanding*
- **Status:** 🟢 **Answered**
- **Latency:** `0.89s`
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
- **Latency:** `0.87s`
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
- **Latency:** `0.84s`
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

### Q004: Show principal outstanding by scheme.

- **Domain:** `Loan Book` — *Portfolio Outstanding*
- **Status:** 🟢 **Answered**
- **Latency:** `4.03s`
- **Chart Type:** `bar`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `chart`
- **Evaluation Intent:** *Scheme-level distribution of current principal outstanding*

#### Application Response Output:
```text
HEADLINE: Principal outstanding by scheme (As at 24 Aug 2026)
SUMMARY / ANSWER:
MSME Loans has the highest principal outstanding, at ₹59.81 Cr as at 24 Aug 2026, 29% of the total across 8 schemes. This measures principal outstanding from each classified account at the requested snapshot, grouped by scheme.

CHART SPEC: Type=bar, Title=Principal outstanding by scheme (As at 24 Aug 2026)
COLUMNS: Scheme, Principal outstanding
SAMPLE ROWS (8 total): [{"scheme": "MSME Loans", "principal_outstanding": 598093032.27, "scheme__raw": "1616"}, {"scheme": "Site / Housing Construction / House Repair", "principal_outstanding": 417574205.4, "scheme__raw": "1618"}, {"scheme": "Personal Loan", "principal_outstanding": 406744496.01, "scheme__raw": "1617"}]

GOVERNED SQL QUERY:
SELECT lam."scheme_code" AS scheme,
       SUM(portfolio.principal_outstanding) AS principal_outstanding
FROM gold.portfolio_snapshot_as_of(DATE '2026-08-24') AS portfolio
     JOIN gold.loan_account_master AS lam ON portfolio."entity_num" = lam."entity_num" AND portfolio."loan_account_number" = lam."loan_account_number"
GROUP BY lam."scheme_code"
ORDER BY SUM(portfolio.principal_outstanding) DESC NULLS LAST
LIMIT 200
```

---

### Q005: What is the total overdue principal across all active loans?

- **Domain:** `Loan Book` — *Portfolio Outstanding*
- **Status:** 🟢 **Answered**
- **Latency:** `6.20s`
- **Chart Type:** `kpi`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `chart`
- **Evaluation Intent:** *Total delinquent principal overdue at current snapshot*

#### Application Response Output:
```text
HEADLINE: Overdue principal (As at 24 Aug 2026)
SUMMARY / ANSWER:
Overdue principal was ₹19.57 L as at 24 Aug 2026. This measures principal overdue at the requested portfolio snapshot.

CHART SPEC: Type=kpi, Title=Overdue principal (As at 24 Aug 2026)
COLUMNS: Overdue principal
SAMPLE ROWS (1 total): [{"overdue_principal": 1957196.06}]

GOVERNED SQL QUERY:
SELECT SUM(portfolio.principal_overdue) AS overdue_principal
FROM gold.portfolio_snapshot_as_of(DATE '2026-08-24') AS portfolio
LIMIT 200
```

---

### Q006: What is the total overdue amount including interest and penal charges?

- **Domain:** `Loan Book` — *Portfolio Outstanding*
- **Status:** 🟢 **Answered**
- **Latency:** `5.52s`
- **Chart Type:** `kpi`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `chart`
- **Evaluation Intent:** *Total overdue balance (principal, interest, charges, penal) across book*

#### Application Response Output:
```text
HEADLINE: Total overdue (As at 24 Aug 2026)
SUMMARY / ANSWER:
Total overdue was ₹34.83 L as at 24 Aug 2026. This measures principal, interest, charges and penal overdue at the requested snapshot.

CHART SPEC: Type=kpi, Title=Total overdue (As at 24 Aug 2026)
COLUMNS: Total overdue
SAMPLE ROWS (1 total): [{"overdue_total": 3483456.42}]

GOVERNED SQL QUERY:
SELECT SUM(portfolio.total_overdue) AS overdue_total
FROM gold.portfolio_snapshot_as_of(DATE '2026-08-24') AS portfolio
LIMIT 200
```

---

### Q007: How many total active loan accounts do we have?

- **Domain:** `Loan Book` — *Portfolio Outstanding*
- **Status:** 🟡 **Refused**
- **Latency:** `60.83s`
- **Chart Type:** `N/A`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `refusal`
- **Evaluation Intent:** *Count of active loan accounts in loan master*

#### Application Response Output:
```text
SUMMARY / ANSWER:
I could not answer that safely from the available data.
```

---

### Q008: What is the total principal outstanding in Gold Loans?

- **Domain:** `Loan Book` — *Portfolio Outstanding*
- **Status:** 🔴 **Error**
- **Latency:** `90.63s`
- **Chart Type:** `N/A`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `error`
- **Evaluation Intent:** *Principal outstanding filtered for Product Code 1 (Gold Loans)*

#### Application Response Output:
```text
ERROR DETAIL: No intelligence source produced a usable answer.
```

---

### Q009: What is the total principal outstanding in Business and MSME Loans?

- **Domain:** `Loan Book` — *Portfolio Outstanding*
- **Status:** 🔴 **Error**
- **Latency:** `90.62s`
- **Chart Type:** `N/A`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `error`
- **Evaluation Intent:** *Principal outstanding filtered for Product Code 16 (Business & MSME Loans)*

#### Application Response Output:
```text
ERROR DETAIL: No intelligence source produced a usable answer.
```

---

### Q010: What is the total principal outstanding in Microfinance and Retail EMI?

- **Domain:** `Loan Book` — *Portfolio Outstanding*
- **Status:** 🔴 **Error**
- **Latency:** `90.63s`
- **Chart Type:** `N/A`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `error`
- **Evaluation Intent:** *Principal outstanding filtered for Product Code 13 (Microfinance / Retail EMI)*

#### Application Response Output:
```text
ERROR DETAIL: No intelligence source produced a usable answer.
```

---

### Q011: Show principal outstanding by loan type.

- **Domain:** `Loan Book` — *Portfolio Outstanding*
- **Status:** 🟢 **Answered**
- **Latency:** `40.87s`
- **Chart Type:** `bar`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `chart`
- **Evaluation Intent:** *Principal outstanding comparison between EMI term loans and bullet/demand loans*

#### Application Response Output:
```text
HEADLINE: Principal outstanding by loan type (As at 24 Aug 2026)
SUMMARY / ANSWER:
EMI term loan is the only loan type returned, with principal outstanding of ₹204.54 Cr as at 24 Aug 2026. This measures principal outstanding from each classified account at the requested snapshot, grouped by loan type.

CHART SPEC: Type=bar, Title=Principal outstanding by loan type (As at 24 Aug 2026)
COLUMNS: Loan type, Principal outstanding
SAMPLE ROWS (1 total): [{"loan_type": "EMI term loan", "principal_outstanding": 2045394519.25, "loan_type__raw": "E"}]

GOVERNED SQL QUERY:
SELECT lam."loan_type" AS loan_type,
       SUM(portfolio.principal_outstanding) AS principal_outstanding
FROM gold.portfolio_snapshot_as_of(DATE '2026-08-24') AS portfolio
     JOIN gold.loan_account_master AS lam ON portfolio."entity_num" = lam."entity_num" AND portfolio."loan_account_number" = lam."loan_account_number"
GROUP BY lam."loan_type"
ORDER BY SUM(portfolio.principal_outstanding) DESC NULLS LAST
LIMIT 200
```

---

### Q012: What is the distribution of principal outstanding by asset classification?

- **Domain:** `Loan Book` — *Portfolio Outstanding*
- **Status:** 🟢 **Answered**
- **Latency:** `6.71s`
- **Chart Type:** `donut`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `chart`
- **Evaluation Intent:** *Principal outstanding across Standard, SMA-0, SMA-1, SMA-2, and NPA categories*

#### Application Response Output:
```text
HEADLINE: Principal outstanding by asset classification (As at 24 Aug 2026)
SUMMARY / ANSWER:
Standard has the highest principal outstanding, at ₹194.43 Cr as at 24 Aug 2026, 95% of the total across 5 asset classifications. This measures principal outstanding from each classified account at the requested snapshot, grouped by asset classification.

CHART SPEC: Type=donut, Title=Principal outstanding by asset classification (As at 24 Aug 2026)
COLUMNS: Asset classification, Principal outstanding
SAMPLE ROWS (5 total): [{"asset_class": "Standard", "principal_outstanding": 1944297584.74, "asset_class__raw": "STD"}, {"asset_class": "SMA-0", "principal_outstanding": 95603973.38, "asset_class__raw": "SMA0"}, {"asset_class": "SMA-1", "principal_outstanding": 4895028.14, "asset_class__raw": "SMA1"}]

GOVERNED SQL QUERY:
SELECT portfolio."asset_code" AS asset_class,
       SUM(portfolio.principal_outstanding) AS principal_outstanding
FROM gold.portfolio_snapshot_as_of(DATE '2026-08-24') AS portfolio
GROUP BY portfolio."asset_code"
ORDER BY SUM(portfolio.principal_outstanding) DESC NULLS LAST
LIMIT 200
```

---

### Q013: What is the total cumulative principal repaid across all loan accounts?

- **Domain:** `Loan Book` — *Portfolio Outstanding*
- **Status:** 🟢 **Answered**
- **Latency:** `51.95s`
- **Chart Type:** `kpi`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `chart`
- **Evaluation Intent:** *Cumulative principal repaid across loan master accounts*

#### Application Response Output:
```text
HEADLINE: What is the total cumulative principal repaid across all loan accounts (Generated query — not a reviewed metric)
SUMMARY / ANSWER:
Total Principal Repaid was ₹12.69 Cr. Sum of cumulative principal repaid across all loan accounts in the master view. This uses a validated read-only generated query rather than a reviewed metric; check Source details before relying on it.

CHART SPEC: Type=kpi, Title=What is the total cumulative principal repaid across all loan accounts (Generated query — not a reviewed metric)
COLUMNS: Total Principal Repaid
SAMPLE ROWS (1 total): [{"total_principal_repaid": 126927411.06}]

GOVERNED SQL QUERY:
SELECT
  SUM(principal_repaid) AS total_principal_repaid
FROM gold.loan_account_master
LIMIT 5000
```

---

### Q014: What is the total cumulative disbursed amount across all accounts in the loan master?

- **Domain:** `Loan Book` — *Portfolio Outstanding*
- **Status:** 🟢 **Answered**
- **Latency:** `43.36s`
- **Chart Type:** `kpi`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `chart`
- **Evaluation Intent:** *Total cumulative amount disbursed recorded on account master*

#### Application Response Output:
```text
HEADLINE: Disbursement (all time)
SUMMARY / ANSWER:
Disbursement was ₹226.69 Cr in all time. This measures sum of disbursement event amounts in the period.

CHART SPEC: Type=kpi, Title=Disbursement (all time)
COLUMNS: Disbursement
SAMPLE ROWS (1 total): [{"disbursement_total": 2266908902.0}]

GOVERNED SQL QUERY:
SELECT SUM(disb.disbursement_amount) AS disbursement_total
FROM gold.loan_disbursement_events AS disb
WHERE disb."disbursement_date" BETWEEN DATE '2000-01-01' AND DATE '2026-08-24'
LIMIT 200
```

---

### Q015: Show principal outstanding for open versus closed loan accounts.

- **Domain:** `Loan Book` — *Portfolio Outstanding*
- **Status:** 🟢 **Answered**
- **Latency:** `1.02s`
- **Chart Type:** `donut`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `chart`
- **Evaluation Intent:** *Binary lifecycle split of outstanding balances between Open and Closed states*

#### Application Response Output:
```text
HEADLINE: Loans sanctioned by account state (all time)
SUMMARY / ANSWER:
Open has the highest loans sanctioned, at 5,677 in all time, 99% of the total across 2 account states. This measures count of loan accounts sanctioned in the period, grouped by account state.

CHART SPEC: Type=donut, Title=Loans sanctioned by account state (all time)
COLUMNS: Account state, Loans sanctioned
SAMPLE ROWS (2 total): [{"open_closed_status": "Open", "loan_count": 5677, "open_closed_status__raw": "Open"}, {"open_closed_status": "Closed", "loan_count": 76, "open_closed_status__raw": "Closed"}]

GOVERNED SQL QUERY:
SELECT CASE WHEN UPPER(BTRIM(COALESCE(lam."loan_status", ''))) = 'CLOSED' THEN 'Closed' ELSE 'Open' END AS open_closed_status,
       COUNT(*) AS loan_count
FROM gold.loan_account_master AS lam
WHERE lam."sanction_date" BETWEEN DATE '2000-01-01' AND DATE '2026-08-24'
GROUP BY CASE WHEN UPPER(BTRIM(COALESCE(lam."loan_status", ''))) = 'CLOSED' THEN 'Closed' ELSE 'Open' END, CASE WHEN UPPER(BTRIM(COALESCE(lam."loan_status", ''))) = 'CLOSED' THEN 2 ELSE 1 END
ORDER BY COUNT(*) DESC NULLS LAST
LIMIT 200
```

---

### Q016: Top 10 loan accounts by principal outstanding.

- **Domain:** `Loan Book` — *Portfolio Outstanding*
- **Status:** 🟢 **Answered**
- **Latency:** `5.39s`
- **Chart Type:** `bar`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `chart`
- **Evaluation Intent:** *Ranking top 10 individual loan accounts with highest exposure*

#### Application Response Output:
```text
HEADLINE: Principal outstanding by loan account (As at 24 Aug 2026)
SUMMARY / ANSWER:
1000400001588.0 has the highest principal outstanding, at ₹17.53 L as at 24 Aug 2026, 15% of the total across 10 loan accounts. This measures principal outstanding from each classified account at the requested snapshot, grouped by loan account.

CHART SPEC: Type=bar, Title=Principal outstanding by loan account (As at 24 Aug 2026)
COLUMNS: Loan account, Principal outstanding
SAMPLE ROWS (10 total): [{"loan_account": 1000400001588.0, "principal_outstanding": 1752997.84, "loan_account__raw": 1000400001588.0}, {"loan_account": 1000400000222.0, "principal_outstanding": 1302342.59, "loan_account__raw": 1000400000222.0}, {"loan_account": 1000400000319.0, "principal_outstanding": 1223549.2, "loan_account__raw": 1000400000319.0}]

GOVERNED SQL QUERY:
SELECT lam."loan_account_number" AS loan_account,
       SUM(portfolio.principal_outstanding) AS principal_outstanding
FROM gold.portfolio_snapshot_as_of(DATE '2026-08-24') AS portfolio
     JOIN gold.loan_account_master AS lam ON portfolio."entity_num" = lam."entity_num" AND portfolio."loan_account_number" = lam."loan_account_number"
GROUP BY lam."loan_account_number"
ORDER BY SUM(portfolio.principal_outstanding) DESC NULLS LAST
LIMIT 10
```

---

### Q017: List the top 5 branches by total principal outstanding.

- **Domain:** `Loan Book` — *Portfolio Outstanding*
- **Status:** 🟢 **Answered**
- **Latency:** `4.40s`
- **Chart Type:** `bar`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `chart`
- **Evaluation Intent:** *Ranking top 5 branches managing largest portfolio volumes*

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
LIMIT 5
```

---

### Q018: What is the average principal outstanding per loan account?

- **Domain:** `Loan Book` — *Portfolio Outstanding*
- **Status:** 🟢 **Answered**
- **Latency:** `6.96s`
- **Chart Type:** `ranking`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `chart`
- **Evaluation Intent:** *Average exposure per classified loan account*

#### Application Response Output:
```text
HEADLINE: Principal outstanding (whole book) by loan account (2026-08-24)
SUMMARY / ANSWER:
1000400001588.0 has the highest principal outstanding (whole book), at ₹17.53 L in 2026-08-24, 1% of the total across 200 loan accounts. This measures cumulative disbursed minus cumulative principal repaid across loan accounts, grouped by loan account.

CHART SPEC: Type=ranking, Title=Principal outstanding (whole book) by loan account (2026-08-24)
COLUMNS: Loan account, Principal outstanding (whole book)
SAMPLE ROWS (200 total): [{"loan_account": 1000400001588.0, "principal_outstanding_book": 1752997.84, "loan_account__raw": 1000400001588.0}, {"loan_account": 1000400000222.0, "principal_outstanding_book": 1267648.73, "loan_account__raw": 1000400000222.0}, {"loan_account": 1000400000441.0, "principal_outstanding_book": 1215832.55, "loan_account__raw": 1000400000441.0}]

GOVERNED SQL QUERY:
SELECT lam."loan_account_number" AS loan_account,
       SUM(lam.disbursed_amount - lam.principal_repaid) AS principal_outstanding_book
FROM gold.loan_account_master AS lam
GROUP BY lam."loan_account_number"
ORDER BY SUM(lam.disbursed_amount - lam.principal_repaid) DESC NULLS LAST
LIMIT 200
```

---

### Q019: Show principal outstanding in Head Office Credit Division.

- **Domain:** `Loan Book` — *Portfolio Outstanding*
- **Status:** 🟢 **Answered**
- **Latency:** `54.68s`
- **Chart Type:** `kpi`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `chart`
- **Evaluation Intent:** *Principal outstanding for branch 4 (Head Office — Credit Division)*

#### Application Response Output:
```text
HEADLINE: Show principal outstanding in Head Office Credit Division (Generated query — not a reviewed metric)
SUMMARY / ANSWER:
Total Principal Outstanding was ₹204.54 Cr. Sum of principal outstanding for branch code 4 (Head Office - Credit Division). This uses a validated read-only generated query rather than a reviewed metric; check Source details before relying on it.

CHART SPEC: Type=kpi, Title=Show principal outstanding in Head Office Credit Division (Generated query — not a reviewed metric)
COLUMNS: Total Principal Outstanding
SAMPLE ROWS (1 total): [{"total_principal_outstanding": 2045394519.25}]

GOVERNED SQL QUERY:
SELECT
  SUM(principal_outstanding) AS total_principal_outstanding
FROM gold.portfolio_daily_snapshot
WHERE
  branch_code = 4
LIMIT 5000
```

---

### Q020: What is the total principal outstanding in Aluva branch?

- **Domain:** `Loan Book` — *Portfolio Outstanding*
- **Status:** 🔴 **Error**
- **Latency:** `90.62s`
- **Chart Type:** `N/A`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `error`
- **Evaluation Intent:** *Principal outstanding for branch 1002 (Aluva)*

#### Application Response Output:
```text
ERROR DETAIL: No intelligence source produced a usable answer.
```

---

### Q021: What is the total sanctioned amount this financial year?

- **Domain:** `Loan Book` — *Origination & Sanctions*
- **Status:** 🟢 **Answered**
- **Latency:** `0.69s`
- **Chart Type:** `kpi`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `chart`
- **Evaluation Intent:** *FYTD sanctioned amount KPI from loan master*

#### Application Response Output:
```text
HEADLINE: Sanctioned amount (FY27 to date)
SUMMARY / ANSWER:
Sanctioned amount was ₹138.41 Cr in FY27 to date. This measures sum of sanctioned amounts for accounts sanctioned in the period.

CHART SPEC: Type=kpi, Title=Sanctioned amount (FY27 to date)
COLUMNS: Sanctioned amount
SAMPLE ROWS (1 total): [{"sanctioned_amount": 1384080902.0}]

GOVERNED SQL QUERY:
SELECT SUM(lam.sanction_amount) AS sanctioned_amount
FROM gold.loan_account_master AS lam
WHERE lam."sanction_date" BETWEEN DATE '2026-04-01' AND DATE '2026-08-24'
LIMIT 200
```

---

### Q022: What was our total sanctioned amount in FY26?

- **Domain:** `Loan Book` — *Origination & Sanctions*
- **Status:** 🟢 **Answered**
- **Latency:** `43.58s`
- **Chart Type:** `kpi`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `chart`
- **Evaluation Intent:** *Total sanctioned volume during fiscal year 2025-26*

#### Application Response Output:
```text
HEADLINE: Sanctioned amount (2025-04-01 to 2026-03-31)
SUMMARY / ANSWER:
Sanctioned amount was ₹90.69 Cr in 2025-04-01 to 2026-03-31. This measures sum of sanctioned amounts for accounts sanctioned in the period.

CHART SPEC: Type=kpi, Title=Sanctioned amount (2025-04-01 to 2026-03-31)
COLUMNS: Sanctioned amount
SAMPLE ROWS (1 total): [{"sanctioned_amount": 906878000.0}]

GOVERNED SQL QUERY:
SELECT SUM(lam.sanction_amount) AS sanctioned_amount
FROM gold.loan_account_master AS lam
WHERE lam."sanction_date" BETWEEN DATE '2025-04-01' AND DATE '2026-03-31'
LIMIT 200
```

---

### Q023: What was the sanctioned amount in the last quarter?

- **Domain:** `Loan Book` — *Origination & Sanctions*
- **Status:** 🟢 **Answered**
- **Latency:** `5.34s`
- **Chart Type:** `bar`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `chart`
- **Evaluation Intent:** *Sanctioned amount in Q2 2026*

#### Application Response Output:
```text
HEADLINE: Sanctioned amount by branch (Q2 2026)
SUMMARY / ANSWER:
Head Office — Credit Division is the only branch returned, with sanctioned amount of ₹130.05 Cr in Q2 2026. This measures sum of sanctioned amounts for accounts sanctioned in the period, grouped by branch.

CHART SPEC: Type=bar, Title=Sanctioned amount by branch (Q2 2026)
COLUMNS: Branch, Sanctioned amount
SAMPLE ROWS (1 total): [{"branch": "Head Office — Credit Division", "sanctioned_amount": 1300530902.0, "branch__raw": 4.0}]

GOVERNED SQL QUERY:
SELECT lam."branch_code" AS branch,
       SUM(lam.sanction_amount) AS sanctioned_amount
FROM gold.loan_account_master AS lam
WHERE lam."sanction_date" BETWEEN DATE '2026-04-01' AND DATE '2026-06-30'
GROUP BY lam."branch_code"
ORDER BY SUM(lam.sanction_amount) DESC NULLS LAST
LIMIT 200
```

---

### Q024: Show me the monthly trend of sanctioned amount over the last 12 months.

- **Domain:** `Loan Book` — *Origination & Sanctions*
- **Status:** 🟢 **Answered**
- **Latency:** `3.55s`
- **Chart Type:** `area`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `chart`
- **Evaluation Intent:** *12-month monthly time-series of total loan sanction amounts*

#### Application Response Output:
```text
HEADLINE: Sanctioned amount by month (last 12 months)
SUMMARY / ANSWER:
Sanctioned amount rose from ₹63.50 L (Oct 2025) to ₹8.36 Cr (Jul 2026), a change of 1215.7%. This measures sum of sanctioned amounts for accounts sanctioned in the period, grouped by month.

CHART SPEC: Type=area, Title=Sanctioned amount by month (last 12 months)
COLUMNS: Month, Sanctioned amount
SAMPLE ROWS (10 total): [{"month": "Oct 2025", "sanctioned_amount": 6350000.0, "month__raw": "2025-10-01"}, {"month": "Nov 2025", "sanctioned_amount": 30500000.0, "month__raw": "2025-11-01"}, {"month": "Dec 2025", "sanctioned_amount": 123910000.0, "month__raw": "2025-12-01"}]

GOVERNED SQL QUERY:
SELECT DATE_TRUNC('month', lam."sanction_date")::date AS month,
       SUM(lam.sanction_amount) AS sanctioned_amount
FROM gold.loan_account_master AS lam
WHERE lam."sanction_date" BETWEEN DATE '2025-08-25' AND DATE '2026-08-24'
GROUP BY DATE_TRUNC('month', lam."sanction_date")::date
ORDER BY DATE_TRUNC('month', lam."sanction_date")::date ASC
LIMIT 200
```

---

### Q025: How many loans did we sanction each month in the last year?

- **Domain:** `Loan Book` — *Origination & Sanctions*
- **Status:** 🟢 **Answered**
- **Latency:** `6.43s`
- **Chart Type:** `area`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `chart`
- **Evaluation Intent:** *12-month monthly time-series of sanctioned loan counts*

#### Application Response Output:
```text
HEADLINE: Loans sanctioned by month (last 12 months)
SUMMARY / ANSWER:
Loans sanctioned rose from 13 (Oct 2025) to 179 (Jul 2026), a change of 1276.9%. This measures count of loan accounts sanctioned in the period, grouped by month.

CHART SPEC: Type=area, Title=Loans sanctioned by month (last 12 months)
COLUMNS: Month, Loans sanctioned
SAMPLE ROWS (10 total): [{"month": "Oct 2025", "loan_count": 13, "month__raw": "2025-10-01"}, {"month": "Nov 2025", "loan_count": 87, "month__raw": "2025-11-01"}, {"month": "Dec 2025", "loan_count": 365, "month__raw": "2025-12-01"}]

GOVERNED SQL QUERY:
SELECT DATE_TRUNC('month', lam."sanction_date")::date AS month,
       COUNT(*) AS loan_count
FROM gold.loan_account_master AS lam
WHERE lam."sanction_date" BETWEEN DATE '2025-08-25' AND DATE '2026-08-24'
GROUP BY DATE_TRUNC('month', lam."sanction_date")::date
ORDER BY DATE_TRUNC('month', lam."sanction_date")::date ASC
LIMIT 200
```

---

### Q026: What is the total count of loans sanctioned in the current financial year?

- **Domain:** `Loan Book` — *Origination & Sanctions*
- **Status:** 🟢 **Answered**
- **Latency:** `4.91s`
- **Chart Type:** `kpi`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `chart`
- **Evaluation Intent:** *FYTD count of sanctioned loan accounts*

#### Application Response Output:
```text
HEADLINE: Loans sanctioned (FY27 to date)
SUMMARY / ANSWER:
Loans sanctioned was 3,270 in FY27 to date. This measures count of loan accounts sanctioned in the period.

CHART SPEC: Type=kpi, Title=Loans sanctioned (FY27 to date)
COLUMNS: Loans sanctioned
SAMPLE ROWS (1 total): [{"loan_count": 3270}]

GOVERNED SQL QUERY:
SELECT COUNT(*) AS loan_count
FROM gold.loan_account_master AS lam
WHERE lam."sanction_date" BETWEEN DATE '2026-04-01' AND DATE '2026-08-24'
LIMIT 200
```

---

### Q027: What is the average ticket size of sanctioned loans across all branches?

- **Domain:** `Loan Book` — *Origination & Sanctions*
- **Status:** 🟢 **Answered**
- **Latency:** `3.28s`
- **Chart Type:** `bar`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `chart`
- **Evaluation Intent:** *Average sanctioned loan amount across all branches*

#### Application Response Output:
```text
HEADLINE: Average ticket size by branch (all time)
SUMMARY / ANSWER:
Head Office — Credit Division has the highest average ticket size, at ₹3.98 L in all time, 54% of the total across 2 branches. This measures total sanctioned amount divided by number of loans, grouped by branch.

CHART SPEC: Type=bar, Title=Average ticket size by branch (all time)
COLUMNS: Branch, Average ticket size
SAMPLE ROWS (2 total): [{"branch": "Head Office — Credit Division", "avg_ticket_size": 398287.3132613992, "branch__raw": 4.0}, {"branch": "Head Office", "avg_ticket_size": 342857.14285714284, "branch__raw": 1.0}]

GOVERNED SQL QUERY:
SELECT lam."branch_code" AS branch,
       (COALESCE(SUM(lam.sanction_amount), 0) / NULLIF(COUNT(*), 0)) AS avg_ticket_size
FROM gold.loan_account_master AS lam
WHERE lam."sanction_date" BETWEEN DATE '2000-01-01' AND DATE '2026-08-24'
GROUP BY lam."branch_code"
ORDER BY (COALESCE(SUM(lam.sanction_amount), 0) / NULLIF(COUNT(*), 0)) DESC NULLS LAST
LIMIT 200
```

---

### Q028: Show average ticket size by product type.

- **Domain:** `Loan Book` — *Origination & Sanctions*
- **Status:** 🟢 **Answered**
- **Latency:** `3.19s`
- **Chart Type:** `bar`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `chart`
- **Evaluation Intent:** *Average ticket size comparison across Gold, Microfinance, and MSME products*

#### Application Response Output:
```text
HEADLINE: Average ticket size by product (all time)
SUMMARY / ANSWER:
Business & MSME Loans is the only product returned, with average ticket size of ₹3.98 L in all time. This measures total sanctioned amount divided by number of loans, grouped by product.

CHART SPEC: Type=bar, Title=Average ticket size by product (all time)
COLUMNS: Product, Average ticket size
SAMPLE ROWS (1 total): [{"product": "Business & MSME Loans", "avg_ticket_size": 398219.868242656, "product__raw": 16.0}]

GOVERNED SQL QUERY:
SELECT lam."product_code" AS product,
       (COALESCE(SUM(lam.sanction_amount), 0) / NULLIF(COUNT(*), 0)) AS avg_ticket_size
FROM gold.loan_account_master AS lam
WHERE lam."sanction_date" BETWEEN DATE '2000-01-01' AND DATE '2026-08-24'
GROUP BY lam."product_code"
ORDER BY (COALESCE(SUM(lam.sanction_amount), 0) / NULLIF(COUNT(*), 0)) DESC NULLS LAST
LIMIT 200
```

---

### Q029: What is the average ticket size by loan scheme?

- **Domain:** `Loan Book` — *Origination & Sanctions*
- **Status:** 🟢 **Answered**
- **Latency:** `3.98s`
- **Chart Type:** `ranking`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `chart`
- **Evaluation Intent:** *Average ticket size breakdown across individual loan schemes*

#### Application Response Output:
```text
HEADLINE: Average ticket size by scheme (all time)
SUMMARY / ANSWER:
Loan Against Property (Scheme #1619) has the highest average ticket size, at ₹8.82 L in all time, 13% of the total across 17 schemes. This measures total sanctioned amount divided by number of loans, grouped by scheme.

CHART SPEC: Type=ranking, Title=Average ticket size by scheme (all time)
COLUMNS: Scheme, Average ticket size
SAMPLE ROWS (17 total): [{"scheme": "Loan Against Property (Scheme #1619)", "avg_ticket_size": 881547.619047619, "scheme__raw": "1619"}, {"scheme": "Loan Against Property (Scheme #1615)", "avg_ticket_size": 660714.2857142857, "scheme__raw": "1615"}, {"scheme": "Farming", "avg_ticket_size": 473684.2105263158, "scheme__raw": "1611"}]

GOVERNED SQL QUERY:
SELECT lam."scheme_code" AS scheme,
       (COALESCE(SUM(lam.sanction_amount), 0) / NULLIF(COUNT(*), 0)) AS avg_ticket_size
FROM gold.loan_account_master AS lam
WHERE lam."sanction_date" BETWEEN DATE '2000-01-01' AND DATE '2026-08-24'
GROUP BY lam."scheme_code"
ORDER BY (COALESCE(SUM(lam.sanction_amount), 0) / NULLIF(COUNT(*), 0)) DESC NULLS LAST
LIMIT 200
```

---

### Q030: What is the average sanctioned interest rate across all accounts?

- **Domain:** `Loan Book` — *Origination & Sanctions*
- **Status:** 🟢 **Answered**
- **Latency:** `1.23s`
- **Chart Type:** `bar`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `chart`
- **Evaluation Intent:** *Sanction-amount weighted average interest rate across portfolio*

#### Application Response Output:
```text
HEADLINE: What is the average sanctioned interest rate across all accounts (Generated query — not a reviewed metric)
SUMMARY / ANSWER:
18.0% has the highest loan count at 3,740 across 8 returned interest rate value(s). Distinct contractual account interest rates, with the number of sanctioned loans at each rate, across the full available loan book. This uses a validated read-only generated query rather than a reviewed metric; check Source details before relying on it.

CHART SPEC: Type=bar, Title=What is the average sanctioned interest rate across all accounts (Generated query — not a reviewed metric)
COLUMNS: Interest Rate, Loan Count
SAMPLE ROWS (8 total): [{"interest_rate": 16.0, "loan_count": 33}, {"interest_rate": 16.5, "loan_count": 145}, {"interest_rate": 17.0, "loan_count": 1060}]

GOVERNED SQL QUERY:
SELECT
  interest_rate AS interest_rate,
  COUNT(interest_rate) AS loan_count
FROM gold.loan_account_master
WHERE
  interest_rate IS NOT NULL AND sanction_date <= CURRENT_DATE
GROUP BY
  interest_rate
ORDER BY
  interest_rate ASC
LIMIT 5000
```

---

### Q031: Show average interest rate by product type.

- **Domain:** `Loan Book` — *Origination & Sanctions*
- **Status:** 🟢 **Answered**
- **Latency:** `4.00s`
- **Chart Type:** `bar`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `chart`
- **Evaluation Intent:** *Weighted average interest rate across product categories*

#### Application Response Output:
```text
HEADLINE: Average interest rate by product (all time)
SUMMARY / ANSWER:
Business & MSME Loans is the only product returned, with average interest rate of 17.7% in all time. This measures sanction-amount-weighted average account interest rate, grouped by product. Definition of Average interest rate is pending client sign-off.

CHART SPEC: Type=bar, Title=Average interest rate by product (all time)
COLUMNS: Product, Average interest rate
SAMPLE ROWS (1 total): [{"product": "Business & MSME Loans", "avg_interest_rate": 17.733762595886148, "product__raw": 16.0}]

GOVERNED SQL QUERY:
SELECT lam."product_code" AS product,
       (COALESCE(SUM(lam.interest_rate * lam.sanction_amount), 0) / NULLIF(SUM(lam.sanction_amount), 0)) AS avg_interest_rate
FROM gold.loan_account_master AS lam
WHERE lam."sanction_date" BETWEEN DATE '2000-01-01' AND DATE '2026-08-24'
GROUP BY lam."product_code"
ORDER BY (COALESCE(SUM(lam.interest_rate * lam.sanction_amount), 0) / NULLIF(SUM(lam.sanction_amount), 0)) DESC NULLS LAST
LIMIT 200
```

---

### Q032: What is the average interest rate by scheme?

- **Domain:** `Loan Book` — *Origination & Sanctions*
- **Status:** 🟢 **Answered**
- **Latency:** `1.23s`
- **Chart Type:** `ranking`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `chart`
- **Evaluation Intent:** *Weighted average interest rate across product schemes*

#### Application Response Output:
```text
HEADLINE: Average interest rate by scheme (all time)
SUMMARY / ANSWER:
Loan Against Property (Scheme #1619) has the highest average interest rate, at 17.8% in all time. This measures sanction-amount-weighted average account interest rate, grouped by scheme. Definition of Average interest rate is pending client sign-off.

CHART SPEC: Type=ranking, Title=Average interest rate by scheme (all time)
COLUMNS: Scheme, Average interest rate
SAMPLE ROWS (17 total): [{"scheme": "Loan Against Property (Scheme #1619)", "avg_interest_rate": 17.78843124015305, "scheme__raw": "1619"}, {"scheme": "Personal Loan", "avg_interest_rate": 17.78182732843472, "scheme__raw": "1617"}, {"scheme": "MSME Loans", "avg_interest_rate": 17.751225733530877, "scheme__raw": "1616"}]

GOVERNED SQL QUERY:
SELECT lam."scheme_code" AS scheme,
       (COALESCE(SUM(lam.interest_rate * lam.sanction_amount), 0) / NULLIF(SUM(lam.sanction_amount), 0)) AS avg_interest_rate
FROM gold.loan_account_master AS lam
WHERE lam."sanction_date" BETWEEN DATE '2000-01-01' AND DATE '2026-08-24'
GROUP BY lam."scheme_code"
ORDER BY (COALESCE(SUM(lam.interest_rate * lam.sanction_amount), 0) / NULLIF(SUM(lam.sanction_amount), 0)) DESC NULLS LAST
LIMIT 200
```

---

### Q033: Show loan sanction count by branch last quarter.

- **Domain:** `Loan Book` — *Origination & Sanctions*
- **Status:** 🟢 **Answered**
- **Latency:** `7.07s`
- **Chart Type:** `bar`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `chart`
- **Evaluation Intent:** *Branch-level sanction volume in the prior quarter*

#### Application Response Output:
```text
HEADLINE: Loans sanctioned by branch (Q2 2026)
SUMMARY / ANSWER:
Head Office — Credit Division is the only branch returned, with 3,091 loans sanctioned in Q2 2026. This measures count of loan accounts sanctioned in the period, grouped by branch.

CHART SPEC: Type=bar, Title=Loans sanctioned by branch (Q2 2026)
COLUMNS: Branch, Loans sanctioned
SAMPLE ROWS (1 total): [{"branch": "Head Office — Credit Division", "loan_count": 3091, "branch__raw": 4.0}]

GOVERNED SQL QUERY:
SELECT lam."branch_code" AS branch,
       COUNT(*) AS loan_count
FROM gold.loan_account_master AS lam
WHERE lam."sanction_date" BETWEEN DATE '2026-04-01' AND DATE '2026-06-30'
GROUP BY lam."branch_code"
ORDER BY COUNT(*) DESC NULLS LAST
LIMIT 200
```

---

### Q034: What was the sanctioned amount by branch in the last financial year?

- **Domain:** `Loan Book` — *Origination & Sanctions*
- **Status:** 🟢 **Answered**
- **Latency:** `6.85s`
- **Chart Type:** `bar`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `chart`
- **Evaluation Intent:** *Branch-level sanctioned amount breakdown in FY26*

#### Application Response Output:
```text
HEADLINE: Sanctioned amount by branch (2025-04-01 to 2026-03-31)
SUMMARY / ANSWER:
Head Office — Credit Division has the highest sanctioned amount, at ₹90.45 Cr in 2025-04-01 to 2026-03-31, 100% of the total across 2 branches. This measures sum of sanctioned amounts for accounts sanctioned in the period, grouped by branch.

CHART SPEC: Type=bar, Title=Sanctioned amount by branch (2025-04-01 to 2026-03-31)
COLUMNS: Branch, Sanctioned amount
SAMPLE ROWS (2 total): [{"branch": "Head Office — Credit Division", "sanctioned_amount": 904478000.0, "branch__raw": 4.0}, {"branch": "Head Office", "sanctioned_amount": 2400000.0, "branch__raw": 1.0}]

GOVERNED SQL QUERY:
SELECT lam."branch_code" AS branch,
       SUM(lam.sanction_amount) AS sanctioned_amount
FROM gold.loan_account_master AS lam
WHERE lam."sanction_date" BETWEEN DATE '2025-04-01' AND DATE '2026-03-31'
GROUP BY lam."branch_code"
ORDER BY SUM(lam.sanction_amount) DESC NULLS LAST
LIMIT 200
```

---

### Q035: Show loan count by product type.

- **Domain:** `Loan Book` — *Origination & Sanctions*
- **Status:** 🟢 **Answered**
- **Latency:** `1.02s`
- **Chart Type:** `bar`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `chart`
- **Evaluation Intent:** *Distribution of loan counts by product code*

#### Application Response Output:
```text
HEADLINE: Loans sanctioned by product (all time)
SUMMARY / ANSWER:
Business & MSME Loans is the only product returned, with 5,753 loans sanctioned in all time. This measures count of loan accounts sanctioned in the period, grouped by product.

CHART SPEC: Type=bar, Title=Loans sanctioned by product (all time)
COLUMNS: Product, Loans sanctioned
SAMPLE ROWS (1 total): [{"product": "Business & MSME Loans", "loan_count": 5753, "product__raw": 16.0}]

GOVERNED SQL QUERY:
SELECT lam."product_code" AS product,
       COUNT(*) AS loan_count
FROM gold.loan_account_master AS lam
WHERE lam."sanction_date" BETWEEN DATE '2000-01-01' AND DATE '2026-08-24'
GROUP BY lam."product_code"
ORDER BY COUNT(*) DESC NULLS LAST
LIMIT 200
```

---

### Q036: How many distinct borrowers do we have in our portfolio?

- **Domain:** `Loan Book` — *Origination & Sanctions*
- **Status:** 🟢 **Answered**
- **Latency:** `4.08s`
- **Chart Type:** `kpi`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `chart`
- **Evaluation Intent:** *Total distinct customer count with sanctioned loans*

#### Application Response Output:
```text
HEADLINE: Borrowers (all time)
SUMMARY / ANSWER:
Borrowers was 5,719 in all time. This measures distinct borrowers with an account sanctioned in the period.

CHART SPEC: Type=kpi, Title=Borrowers (all time)
COLUMNS: Borrowers
SAMPLE ROWS (1 total): [{"customer_count": 5719}]

GOVERNED SQL QUERY:
SELECT COUNT(DISTINCT lam.customer_id) AS customer_count
FROM gold.loan_account_master AS lam
WHERE lam."sanction_date" BETWEEN DATE '2000-01-01' AND DATE '2026-08-24'
LIMIT 200
```

---

### Q037: What is the sanctioned amount for EMI term loans versus bullet loans?

- **Domain:** `Loan Book` — *Origination & Sanctions*
- **Status:** 🟢 **Answered**
- **Latency:** `4.34s`
- **Chart Type:** `bar`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `chart`
- **Evaluation Intent:** *Sanction volume comparison by loan amortization type (E vs C)*

#### Application Response Output:
```text
HEADLINE: Sanctioned amount by loan type (all time)
SUMMARY / ANSWER:
EMI term loan is the only loan type returned, with sanctioned amount of ₹229.10 Cr in all time. This measures sum of sanctioned amounts for accounts sanctioned in the period, grouped by loan type.

CHART SPEC: Type=bar, Title=Sanctioned amount by loan type (all time)
COLUMNS: Loan type, Sanctioned amount
SAMPLE ROWS (1 total): [{"loan_type": "EMI term loan", "sanctioned_amount": 2290958902.0, "loan_type__raw": "E"}]

GOVERNED SQL QUERY:
SELECT lam."loan_type" AS loan_type,
       SUM(lam.sanction_amount) AS sanctioned_amount
FROM gold.loan_account_master AS lam
WHERE lam."sanction_date" BETWEEN DATE '2000-01-01' AND DATE '2026-08-24'
GROUP BY lam."loan_type"
ORDER BY SUM(lam.sanction_amount) DESC NULLS LAST
LIMIT 200
```

---

### Q038: What is the total number of loan applications received?

- **Domain:** `Loan Book` — *Origination & Sanctions*
- **Status:** 🟢 **Answered**
- **Latency:** `3.05s`
- **Chart Type:** `kpi`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `chart`
- **Evaluation Intent:** *Application volume from loan application master*

#### Application Response Output:
```text
HEADLINE: Applications received (all time)
SUMMARY / ANSWER:
Applications received was 9,021 in all time. This measures count of application master records entered in the period.

CHART SPEC: Type=kpi, Title=Applications received (all time)
COLUMNS: Applications received
SAMPLE ROWS (1 total): [{"application_count": 9021}]

GOVERNED SQL QUERY:
SELECT COUNT(*) AS application_count
FROM gold.loan_application_master AS application
WHERE application."application_date" BETWEEN DATE '2000-01-01' AND DATE '2026-08-24'
LIMIT 200
```

---

### Q039: Show application volume by application branch.

- **Domain:** `Loan Book` — *Origination & Sanctions*
- **Status:** 🟢 **Answered**
- **Latency:** `3.07s`
- **Chart Type:** `bar`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `chart`
- **Evaluation Intent:** *Application counts grouped by origination branch*

#### Application Response Output:
```text
HEADLINE: Applications received by application branch (all time)
SUMMARY / ANSWER:
Branch 0 has the highest applications received, at 7,731 in all time, 86% of the total across 5 application branches. This measures count of application master records entered in the period, grouped by application branch.

CHART SPEC: Type=bar, Title=Applications received by application branch (all time)
COLUMNS: Application branch, Applications received
SAMPLE ROWS (5 total): [{"application_branch": "Branch 0", "application_count": 7731, "application_branch__raw": 0.0}, {"application_branch": "Head Office — Credit Division", "application_count": 1270, "application_branch__raw": 4.0}, {"application_branch": "Head Office", "application_count": 18, "application_branch__raw": 1.0}]

GOVERNED SQL QUERY:
SELECT application."branch_code" AS application_branch,
       COUNT(*) AS application_count
FROM gold.loan_application_master AS application
WHERE application."application_date" BETWEEN DATE '2000-01-01' AND DATE '2026-08-24'
GROUP BY application."branch_code"
ORDER BY COUNT(*) DESC NULLS LAST
LIMIT 200
```

---

### Q040: What is the observable application to disbursement conversion rate?

- **Domain:** `Loan Book` — *Origination & Sanctions*
- **Status:** 🟢 **Answered**
- **Latency:** `3.38s`
- **Chart Type:** `kpi`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `chart`
- **Evaluation Intent:** *Observable conversion percentage of applications to disbursed accounts*

#### Application Response Output:
```text
HEADLINE: Observable application-to-disbursement conversion (all time)
SUMMARY / ANSWER:
Observable application-to-disbursement conversion was 83.3% in all time. This measures applications observed as disbursed divided by all application records in the period. Definition of Observable application-to-disbursement conversion is pending client sign-off.

CHART SPEC: Type=kpi, Title=Observable application-to-disbursement conversion (all time)
COLUMNS: Observable application-to-disbursement conversion
SAMPLE ROWS (1 total): [{"observable_application_conversion_rate": 83.30562021948786}]

GOVERNED SQL QUERY:
SELECT (100.0 * COALESCE(COUNT(*) FILTER (WHERE application_outcome.outcome_status = 'disbursed'), 0) / NULLIF(COUNT(*), 0)) AS observable_application_conversion_rate
FROM gold.loan_application_outcomes AS application_outcome
WHERE application_outcome."application_date" BETWEEN DATE '2000-01-01' AND DATE '2026-08-24'
LIMIT 200
```

---

### Q041: What was our total disbursement last quarter?

- **Domain:** `Loan Book` — *Disbursements*
- **Status:** 🟢 **Answered**
- **Latency:** `1.24s`
- **Chart Type:** `kpi`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `chart`
- **Evaluation Intent:** *Disbursement event flow in prior quarter (Q2 2026)*

#### Application Response Output:
```text
HEADLINE: Disbursement (Q2 2026)
SUMMARY / ANSWER:
Disbursement was ₹127.55 Cr in Q2 2026. This measures sum of disbursement event amounts in the period.

CHART SPEC: Type=kpi, Title=Disbursement (Q2 2026)
COLUMNS: Disbursement
SAMPLE ROWS (1 total): [{"disbursement_total": 1275455902.0}]

GOVERNED SQL QUERY:
SELECT SUM(disb.disbursement_amount) AS disbursement_total
FROM gold.loan_disbursement_events AS disb
WHERE disb."disbursement_date" BETWEEN DATE '2026-04-01' AND DATE '2026-06-30'
LIMIT 200
```

---

### Q042: What is the total disbursement amount this financial year?

- **Domain:** `Loan Book` — *Disbursements*
- **Status:** 🟢 **Answered**
- **Latency:** `6.68s`
- **Chart Type:** `kpi`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `chart`
- **Evaluation Intent:** *FYTD total disbursement volume from disbursement events*

#### Application Response Output:
```text
HEADLINE: Disbursement (FY27 to date)
SUMMARY / ANSWER:
Disbursement was ₹137.16 Cr in FY27 to date. This measures sum of disbursement event amounts in the period.

CHART SPEC: Type=kpi, Title=Disbursement (FY27 to date)
COLUMNS: Disbursement
SAMPLE ROWS (1 total): [{"disbursement_total": 1371605902.0}]

GOVERNED SQL QUERY:
SELECT SUM(disb.disbursement_amount) AS disbursement_total
FROM gold.loan_disbursement_events AS disb
WHERE disb."disbursement_date" BETWEEN DATE '2026-04-01' AND DATE '2026-08-24'
LIMIT 200
```

---

### Q043: What was the total disbursement in FY26?

- **Domain:** `Loan Book` — *Disbursements*
- **Status:** 🟢 **Answered**
- **Latency:** `6.82s`
- **Chart Type:** `kpi`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `chart`
- **Evaluation Intent:** *Total disbursement amount in FY2025-26*

#### Application Response Output:
```text
HEADLINE: Disbursement (2025-04-01 to 2026-03-31)
SUMMARY / ANSWER:
Disbursement was ₹89.53 Cr in 2025-04-01 to 2026-03-31. This measures sum of disbursement event amounts in the period.

CHART SPEC: Type=kpi, Title=Disbursement (2025-04-01 to 2026-03-31)
COLUMNS: Disbursement
SAMPLE ROWS (1 total): [{"disbursement_total": 895303000.0}]

GOVERNED SQL QUERY:
SELECT SUM(disb.disbursement_amount) AS disbursement_total
FROM gold.loan_disbursement_events AS disb
WHERE disb."disbursement_date" BETWEEN DATE '2025-04-01' AND DATE '2026-03-31'
LIMIT 200
```

---

### Q044: Show me the disbursement trend over the last 12 months.

- **Domain:** `Loan Book` — *Disbursements*
- **Status:** 🟢 **Answered**
- **Latency:** `1.54s`
- **Chart Type:** `area`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `chart`
- **Evaluation Intent:** *12-month monthly disbursement flow time-series*

#### Application Response Output:
```text
HEADLINE: Disbursement by month (last 12 months)
SUMMARY / ANSWER:
Disbursement rose from ₹59.50 L (Oct 2025) to ₹9.62 Cr (Jul 2026), a change of 1516.0%. This measures sum of disbursement event amounts in the period, grouped by month.

CHART SPEC: Type=area, Title=Disbursement by month (last 12 months)
COLUMNS: Month, Disbursement
SAMPLE ROWS (10 total): [{"month": "Oct 2025", "disbursement_total": 5950000.0, "month__raw": "2025-10-01"}, {"month": "Nov 2025", "disbursement_total": 28000000.0, "month__raw": "2025-11-01"}, {"month": "Dec 2025", "disbursement_total": 88360000.0, "month__raw": "2025-12-01"}]

GOVERNED SQL QUERY:
SELECT DATE_TRUNC('month', disb."disbursement_date")::date AS month,
       SUM(disb.disbursement_amount) AS disbursement_total
FROM gold.loan_disbursement_events AS disb
WHERE disb."disbursement_date" BETWEEN DATE '2025-08-25' AND DATE '2026-08-24'
GROUP BY DATE_TRUNC('month', disb."disbursement_date")::date
ORDER BY DATE_TRUNC('month', disb."disbursement_date")::date ASC
LIMIT 200
```

---

### Q045: Show monthly disbursement count over the last 12 months.

- **Domain:** `Loan Book` — *Disbursements*
- **Status:** 🟢 **Answered**
- **Latency:** `3.69s`
- **Chart Type:** `area`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `chart`
- **Evaluation Intent:** *Monthly count of disbursement events over past year*

#### Application Response Output:
```text
HEADLINE: Number of disbursements by month (last 12 months)
SUMMARY / ANSWER:
Number of disbursements rose from 11 (Oct 2025) to 215 (Jul 2026), a change of 1854.5%. This measures count of disbursement events in the period, grouped by month.

CHART SPEC: Type=area, Title=Number of disbursements by month (last 12 months)
COLUMNS: Month, Number of disbursements
SAMPLE ROWS (10 total): [{"month": "Oct 2025", "disbursement_count": 11, "month__raw": "2025-10-01"}, {"month": "Nov 2025", "disbursement_count": 81, "month__raw": "2025-11-01"}, {"month": "Dec 2025", "disbursement_count": 269, "month__raw": "2025-12-01"}]

GOVERNED SQL QUERY:
SELECT DATE_TRUNC('month', disb."disbursement_date")::date AS month,
       COUNT(*) AS disbursement_count
FROM gold.loan_disbursement_events AS disb
WHERE disb."disbursement_date" BETWEEN DATE '2025-08-25' AND DATE '2026-08-24'
GROUP BY DATE_TRUNC('month', disb."disbursement_date")::date
ORDER BY DATE_TRUNC('month', disb."disbursement_date")::date ASC
LIMIT 200
```

---

### Q046: What was our disbursement by branch last quarter?

- **Domain:** `Loan Book` — *Disbursements*
- **Status:** 🟢 **Answered**
- **Latency:** `3.99s`
- **Chart Type:** `bar`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `chart`
- **Evaluation Intent:** *Branch-level disbursement breakdown in Q2 2026*

#### Application Response Output:
```text
HEADLINE: Disbursement by branch (Q2 2026)
SUMMARY / ANSWER:
Head Office — Credit Division is the only branch returned, with disbursement of ₹127.55 Cr in Q2 2026. This measures sum of disbursement event amounts in the period, grouped by branch.

CHART SPEC: Type=bar, Title=Disbursement by branch (Q2 2026)
COLUMNS: Branch, Disbursement
SAMPLE ROWS (1 total): [{"branch": "Head Office — Credit Division", "disbursement_total": 1275455902.0, "branch__raw": 4.0}]

GOVERNED SQL QUERY:
SELECT lam."branch_code" AS branch,
       SUM(disb.disbursement_amount) AS disbursement_total
FROM gold.loan_disbursement_events AS disb
     JOIN gold.loan_account_master AS lam ON disb."entity_num" = lam."entity_num" AND disb."loan_account_number" = lam."loan_account_number"
WHERE disb."disbursement_date" BETWEEN DATE '2026-04-01' AND DATE '2026-06-30'
GROUP BY lam."branch_code"
ORDER BY SUM(disb.disbursement_amount) DESC NULLS LAST
LIMIT 200
```

---

### Q047: Which branches disbursed the most last quarter?

- **Domain:** `Loan Book` — *Disbursements*
- **Status:** 🟢 **Answered**
- **Latency:** `3.99s`
- **Chart Type:** `bar`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `chart`
- **Evaluation Intent:** *Ranking branches by disbursed amount in prior quarter*

#### Application Response Output:
```text
HEADLINE: Disbursement by branch (Q2 2026)
SUMMARY / ANSWER:
Head Office — Credit Division is the only branch returned, with disbursement of ₹127.55 Cr in Q2 2026. This measures sum of disbursement event amounts in the period, grouped by branch.

CHART SPEC: Type=bar, Title=Disbursement by branch (Q2 2026)
COLUMNS: Branch, Disbursement
SAMPLE ROWS (1 total): [{"branch": "Head Office — Credit Division", "disbursement_total": 1275455902.0, "branch__raw": 4.0}]

GOVERNED SQL QUERY:
SELECT lam."branch_code" AS branch,
       SUM(disb.disbursement_amount) AS disbursement_total
FROM gold.loan_disbursement_events AS disb
     JOIN gold.loan_account_master AS lam ON disb."entity_num" = lam."entity_num" AND disb."loan_account_number" = lam."loan_account_number"
WHERE disb."disbursement_date" BETWEEN DATE '2026-04-01' AND DATE '2026-06-30'
GROUP BY lam."branch_code"
ORDER BY SUM(disb.disbursement_amount) DESC NULLS LAST
LIMIT 200
```

---

### Q048: Show disbursement amount by product type last quarter.

- **Domain:** `Loan Book` — *Disbursements*
- **Status:** 🟢 **Answered**
- **Latency:** `3.99s`
- **Chart Type:** `bar`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `chart`
- **Evaluation Intent:** *Disbursement breakdown by product in Q2 2026*

#### Application Response Output:
```text
HEADLINE: Disbursement by product (Q2 2026)
SUMMARY / ANSWER:
Business & MSME Loans is the only product returned, with disbursement of ₹127.55 Cr in Q2 2026. This measures sum of disbursement event amounts in the period, grouped by product.

CHART SPEC: Type=bar, Title=Disbursement by product (Q2 2026)
COLUMNS: Product, Disbursement
SAMPLE ROWS (1 total): [{"product": "Business & MSME Loans", "disbursement_total": 1275455902.0, "product__raw": 16.0}]

GOVERNED SQL QUERY:
SELECT lam."product_code" AS product,
       SUM(disb.disbursement_amount) AS disbursement_total
FROM gold.loan_disbursement_events AS disb
     JOIN gold.loan_account_master AS lam ON disb."entity_num" = lam."entity_num" AND disb."loan_account_number" = lam."loan_account_number"
WHERE disb."disbursement_date" BETWEEN DATE '2026-04-01' AND DATE '2026-06-30'
GROUP BY lam."product_code"
ORDER BY SUM(disb.disbursement_amount) DESC NULLS LAST
LIMIT 200
```

---

### Q049: How much have we disbursed in gold loans?

- **Domain:** `Loan Book` — *Disbursements*
- **Status:** 🟢 **Answered**
- **Latency:** `0.92s`
- **Chart Type:** `kpi`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `chart`
- **Evaluation Intent:** *Cumulative disbursement amount for Product Code 1 (Gold Loans)*

#### Application Response Output:
```text
HEADLINE: Disbursement (all time)
SUMMARY / ANSWER:
No disbursement found in all time with Product eq Gold Loans. This measures sum of disbursement event amounts in the period.

CHART SPEC: Type=kpi, Title=Disbursement (all time)
COLUMNS: Disbursement
SAMPLE ROWS (1 total): [{"disbursement_total": null}]

GOVERNED SQL QUERY:
SELECT SUM(disb.disbursement_amount) AS disbursement_total
FROM gold.loan_disbursement_events AS disb
     JOIN gold.loan_account_master AS lam ON disb."entity_num" = lam."entity_num" AND disb."loan_account_number" = lam."loan_account_number"
WHERE disb."disbursement_date" BETWEEN DATE '2000-01-01' AND DATE '2026-08-24'
  AND lam."product_code"::text = '1'
LIMIT 200
```

---

### Q050: How much have we disbursed in business and MSME loans?

- **Domain:** `Loan Book` — *Disbursements*
- **Status:** 🟢 **Answered**
- **Latency:** `57.47s`
- **Chart Type:** `kpi`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `chart`
- **Evaluation Intent:** *Cumulative disbursement amount for Product Code 16 (Business & MSME Loans)*

#### Application Response Output:
```text
HEADLINE: How much have we disbursed in business and MSME loans (Generated query — not a reviewed metric)
SUMMARY / ANSWER:
Total Disbursed was ₹226.69 Cr. Sum of disbursement amounts for Business (16), MSME (1616), and Business/Service (1610) schemes. This uses a validated read-only generated query rather than a reviewed metric; check Source details before relying on it.

CHART SPEC: Type=kpi, Title=How much have we disbursed in business and MSME loans (Generated query — not a reviewed metric)
COLUMNS: Total Disbursed
SAMPLE ROWS (1 total): [{"total_disbursed": 2266908902.0}]

GOVERNED SQL QUERY:
SELECT
  SUM(disbursement_amount) AS total_disbursed
FROM gold.loan_disbursement_events
WHERE
  product_code IN (16, 1616, 1610)
  AND disbursement_date >= CAST('2023-01-01' AS DATE)
LIMIT 5000
```

---

### Q051: How much have we disbursed in microfinance loans?

- **Domain:** `Loan Book` — *Disbursements*
- **Status:** 🟢 **Answered**
- **Latency:** `89.90s`
- **Chart Type:** `table`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `chart`
- **Evaluation Intent:** *Cumulative disbursement amount for Product Code 13 (Microfinance / Retail EMI)*

#### Application Response Output:
```text
HEADLINE: How much have we disbursed in microfinance loans (Generated query — not a reviewed metric)
SUMMARY / ANSWER:
The query returned 1 row(s) covering total disbursed. Total disbursed amount for product code 13 (Microfinance / Retail EMI). This uses a validated read-only generated query rather than a reviewed metric; check Source details before relying on it.

CHART SPEC: Type=table, Title=How much have we disbursed in microfinance loans (Generated query — not a reviewed metric)
COLUMNS: Total Disbursed
SAMPLE ROWS (1 total): [{"total_disbursed": null}]

GOVERNED SQL QUERY:
SELECT
  SUM(disbursement_amount) AS total_disbursed
FROM gold.loan_disbursement_events
WHERE
  product_code = 13 AND disbursement_date >= CAST('2023-01-01' AS DATE)
LIMIT 1
```

---

### Q052: Top 10 schemes by disbursement amount.

- **Domain:** `Loan Book` — *Disbursements*
- **Status:** 🟢 **Answered**
- **Latency:** `50.93s`
- **Chart Type:** `bar`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `chart`
- **Evaluation Intent:** *Ranking schemes by total historical disbursement volume*

#### Application Response Output:
```text
HEADLINE: Disbursement by scheme (all time)
SUMMARY / ANSWER:
MSME Loans has the highest disbursement, at ₹65.47 Cr in all time, 29% of the total across 10 schemes. This measures sum of disbursement event amounts in the period, grouped by scheme.

CHART SPEC: Type=bar, Title=Disbursement by scheme (all time)
COLUMNS: Scheme, Disbursement
SAMPLE ROWS (10 total): [{"scheme": "MSME Loans", "disbursement_total": 654710000.0, "scheme__raw": "1616"}, {"scheme": "Site / Housing Construction / House Repair", "disbursement_total": 457645000.0, "scheme__raw": "1618"}, {"scheme": "Personal Loan", "disbursement_total": 439308000.0, "scheme__raw": "1617"}]

GOVERNED SQL QUERY:
SELECT lam."scheme_code" AS scheme,
       SUM(disb.disbursement_amount) AS disbursement_total
FROM gold.loan_disbursement_events AS disb
     JOIN gold.loan_account_master AS lam ON disb."entity_num" = lam."entity_num" AND disb."loan_account_number" = lam."loan_account_number"
WHERE disb."disbursement_date" BETWEEN DATE '2000-01-01' AND DATE '2026-08-24'
GROUP BY lam."scheme_code"
ORDER BY SUM(disb.disbursement_amount) DESC NULLS LAST
LIMIT 10
```

---

### Q053: Show disbursement volume in Kozhikode branch.

- **Domain:** `Loan Book` — *Disbursements*
- **Status:** 🔴 **Error**
- **Latency:** `90.50s`
- **Chart Type:** `N/A`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `error`
- **Evaluation Intent:** *Total disbursement events in branch 1007 (Kozhikode)*

#### Application Response Output:
```text
ERROR DETAIL: No intelligence source produced a usable answer.
```

---

### Q054: Show disbursement volume in Thripunithura branch.

- **Domain:** `Loan Book` — *Disbursements*
- **Status:** 🔴 **Error**
- **Latency:** `90.61s`
- **Chart Type:** `N/A`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `error`
- **Evaluation Intent:** *Total disbursement events in branch 1001 (Thripunithura)*

#### Application Response Output:
```text
ERROR DETAIL: No intelligence source produced a usable answer.
```

---

### Q055: Show disbursement volume in Angamally branch.

- **Domain:** `Loan Book` — *Disbursements*
- **Status:** 🔴 **Error**
- **Latency:** `90.58s`
- **Chart Type:** `N/A`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `error`
- **Evaluation Intent:** *Total disbursement events in branch 1013 (Angamally)*

#### Application Response Output:
```text
ERROR DETAIL: No intelligence source produced a usable answer.
```

---

### Q056: What was the total disbursement in Q1 2026?

- **Domain:** `Loan Book` — *Disbursements*
- **Status:** 🟢 **Answered**
- **Latency:** `60.23s`
- **Chart Type:** `kpi`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `chart`
- **Evaluation Intent:** *Disbursement volume in Q1 2026 (Jan-Mar 2026)*

#### Application Response Output:
```text
HEADLINE: Disbursement (2026-04-01 to 2026-06-30)
SUMMARY / ANSWER:
Disbursement was ₹127.55 Cr in 2026-04-01 to 2026-06-30. This measures sum of disbursement event amounts in the period.

CHART SPEC: Type=kpi, Title=Disbursement (2026-04-01 to 2026-06-30)
COLUMNS: Disbursement
SAMPLE ROWS (1 total): [{"disbursement_total": 1275455902.0}]

GOVERNED SQL QUERY:
SELECT SUM(disb.disbursement_amount) AS disbursement_total
FROM gold.loan_disbursement_events AS disb
WHERE disb."disbursement_date" BETWEEN DATE '2026-04-01' AND DATE '2026-06-30'
LIMIT 200
```

---

### Q057: What was the total disbursement in Q2 2026?

- **Domain:** `Loan Book` — *Disbursements*
- **Status:** 🟢 **Answered**
- **Latency:** `6.63s`
- **Chart Type:** `kpi`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `chart`
- **Evaluation Intent:** *Disbursement volume in Q2 2026 (Apr-Jun 2026)*

#### Application Response Output:
```text
HEADLINE: Disbursement (2026-04-01 to 2026-06-30)
SUMMARY / ANSWER:
Disbursement was ₹127.55 Cr in 2026-04-01 to 2026-06-30. This measures sum of disbursement event amounts in the period.

CHART SPEC: Type=kpi, Title=Disbursement (2026-04-01 to 2026-06-30)
COLUMNS: Disbursement
SAMPLE ROWS (1 total): [{"disbursement_total": 1275455902.0}]

GOVERNED SQL QUERY:
SELECT SUM(disb.disbursement_amount) AS disbursement_total
FROM gold.loan_disbursement_events AS disb
WHERE disb."disbursement_date" BETWEEN DATE '2026-04-01' AND DATE '2026-06-30'
LIMIT 200
```

---

### Q058: What is the total number of disbursement events in the system?

- **Domain:** `Loan Book` — *Disbursements*
- **Status:** 🟢 **Answered**
- **Latency:** `4.69s`
- **Chart Type:** `kpi`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `chart`
- **Evaluation Intent:** *Count of all governed disbursement event rows (5,696 events)*

#### Application Response Output:
```text
HEADLINE: Number of disbursements (all time)
SUMMARY / ANSWER:
Number of disbursements was 5,696 in all time. This measures count of disbursement events in the period.

CHART SPEC: Type=kpi, Title=Number of disbursements (all time)
COLUMNS: Number of disbursements
SAMPLE ROWS (1 total): [{"disbursement_count": 5696}]

GOVERNED SQL QUERY:
SELECT COUNT(*) AS disbursement_count
FROM gold.loan_disbursement_events AS disb
WHERE disb."disbursement_date" BETWEEN DATE '2000-01-01' AND DATE '2026-08-24'
LIMIT 200
```

---

### Q059: Show disbursement amount by scheme for Gold Loan schemes.

- **Domain:** `Loan Book` — *Disbursements*
- **Status:** 🟢 **Answered**
- **Latency:** `0.75s`
- **Chart Type:** `kpi`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `chart`
- **Evaluation Intent:** *Disbursement volume across gold schemes (1001, 1005, 1342)*

#### Application Response Output:
```text
HEADLINE: Disbursement (all time)
SUMMARY / ANSWER:
No disbursement found in all time with Product eq Gold Loans. This measures sum of disbursement event amounts in the period.

CHART SPEC: Type=kpi, Title=Disbursement (all time)
COLUMNS: Disbursement
SAMPLE ROWS (1 total): [{"disbursement_total": null}]

GOVERNED SQL QUERY:
SELECT SUM(disb.disbursement_amount) AS disbursement_total
FROM gold.loan_disbursement_events AS disb
     JOIN gold.loan_account_master AS lam ON disb."entity_num" = lam."entity_num" AND disb."loan_account_number" = lam."loan_account_number"
WHERE disb."disbursement_date" BETWEEN DATE '2000-01-01' AND DATE '2026-08-24'
  AND lam."product_code"::text = '1'
LIMIT 200
```

---

### Q060: Compare sanctioned amount against total disbursed amount by branch.

- **Domain:** `Loan Book` — *Disbursements*
- **Status:** 🟡 **Clarification Needed**
- **Latency:** `11.11s`
- **Chart Type:** `N/A`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `clarify`
- **Evaluation Intent:** *Branch-level comparison of sanctions versus disbursements*

#### Application Response Output:
```text
SUMMARY / ANSWER:
You requested a comparison of sanctioned amount and disbursed amount by branch. Since these metrics come from different source tables (loan_account_master vs loan_disbursement_events) and lack a direct branch-level join in the catalog, I cannot generate a single query for both. Would you like the comparison for a specific branch, or should I provide the metrics separately?
```

---

### Q061: What is our overall collection efficiency this financial year?

- **Domain:** `Loan Book` — *Collections & Repayments*
- **Status:** 🟢 **Answered**
- **Latency:** `7.75s`
- **Chart Type:** `kpi`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `chart`
- **Evaluation Intent:** *FYTD collection efficiency ratio (total paid / total due)*

#### Application Response Output:
```text
HEADLINE: Collection efficiency (FY27 to date)
SUMMARY / ANSWER:
Collection efficiency was 98.5% in FY27 to date. This measures total principal and interest paid divided by total principal and interest due.

CHART SPEC: Type=kpi, Title=Collection efficiency (FY27 to date)
COLUMNS: Collection efficiency
SAMPLE ROWS (1 total): [{"collection_efficiency": 98.54437200622546}]

GOVERNED SQL QUERY:
SELECT (100.0 * COALESCE(SUM(repay.total_paid), 0) / NULLIF(SUM(repay.total_due), 0)) AS collection_efficiency
FROM gold.loan_repayment_events AS repay
WHERE repay."repayment_date" BETWEEN DATE '2026-04-01' AND DATE '2026-08-24'
LIMIT 200
```

---

### Q062: What was our collection efficiency last quarter?

- **Domain:** `Loan Book` — *Collections & Repayments*
- **Status:** 🟢 **Answered**
- **Latency:** `3.63s`
- **Chart Type:** `kpi`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `chart`
- **Evaluation Intent:** *Collection efficiency in prior quarter (Q2 2026)*

#### Application Response Output:
```text
HEADLINE: Collection efficiency (Q2 2026)
SUMMARY / ANSWER:
Collection efficiency was 99.8% in Q2 2026. This measures total principal and interest paid divided by total principal and interest due.

CHART SPEC: Type=kpi, Title=Collection efficiency (Q2 2026)
COLUMNS: Collection efficiency
SAMPLE ROWS (1 total): [{"collection_efficiency": 99.78922330619737}]

GOVERNED SQL QUERY:
SELECT (100.0 * COALESCE(SUM(repay.total_paid), 0) / NULLIF(SUM(repay.total_due), 0)) AS collection_efficiency
FROM gold.loan_repayment_events AS repay
WHERE repay."repayment_date" BETWEEN DATE '2026-04-01' AND DATE '2026-06-30'
LIMIT 200
```

---

### Q063: What is the current monthly collection efficiency?

- **Domain:** `Loan Book` — *Collections & Repayments*
- **Status:** 🟢 **Answered**
- **Latency:** `6.33s`
- **Chart Type:** `table`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `chart`
- **Evaluation Intent:** *Collection efficiency for current month*

#### Application Response Output:
```text
HEADLINE: Collection efficiency by month (2026-08-24)
SUMMARY / ANSWER:
No collection efficiency found in 2026-08-24. This measures total principal and interest paid divided by total principal and interest due, grouped by month.

CHART SPEC: Type=table, Title=Collection efficiency by month (2026-08-24)
COLUMNS: Month, Collection efficiency

GOVERNED SQL QUERY:
SELECT DATE_TRUNC('month', repay."repayment_date")::date AS month,
       (100.0 * COALESCE(SUM(repay.total_paid), 0) / NULLIF(SUM(repay.total_due), 0)) AS collection_efficiency
FROM gold.loan_repayment_events AS repay
WHERE repay."repayment_date" BETWEEN DATE '2026-08-24' AND DATE '2026-08-24'
GROUP BY DATE_TRUNC('month', repay."repayment_date")::date
ORDER BY DATE_TRUNC('month', repay."repayment_date")::date ASC
LIMIT 200
```

---

### Q064: Show collection efficiency by branch this financial year.

- **Domain:** `Loan Book` — *Collections & Repayments*
- **Status:** 🟢 **Answered**
- **Latency:** `3.96s`
- **Chart Type:** `bar`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `chart`
- **Evaluation Intent:** *Branch-level collection efficiency breakdown*

#### Application Response Output:
```text
HEADLINE: Collection efficiency by branch (FY27 to date)
SUMMARY / ANSWER:
Head Office — Credit Division is the only branch returned, with collection efficiency of 98.5% in FY27 to date. This measures total principal and interest paid divided by total principal and interest due, grouped by branch.

CHART SPEC: Type=bar, Title=Collection efficiency by branch (FY27 to date)
COLUMNS: Branch, Collection efficiency
SAMPLE ROWS (1 total): [{"branch": "Head Office — Credit Division", "collection_efficiency": 98.54437200622546, "branch__raw": 4.0}]

GOVERNED SQL QUERY:
SELECT lam."branch_code" AS branch,
       (100.0 * COALESCE(SUM(repay.total_paid), 0) / NULLIF(SUM(repay.total_due), 0)) AS collection_efficiency
FROM gold.loan_repayment_events AS repay
     JOIN gold.loan_account_master AS lam ON repay."entity_num" = lam."entity_num" AND repay."loan_account_number" = lam."loan_account_number"
WHERE repay."repayment_date" BETWEEN DATE '2026-04-01' AND DATE '2026-08-24'
GROUP BY lam."branch_code"
ORDER BY (100.0 * COALESCE(SUM(repay.total_paid), 0) / NULLIF(SUM(repay.total_due), 0)) DESC NULLS LAST
LIMIT 200
```

---

### Q065: Which branches have the lowest collection efficiency?

- **Domain:** `Loan Book` — *Collections & Repayments*
- **Status:** 🟢 **Answered**
- **Latency:** `4.73s`
- **Chart Type:** `bar`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `chart`
- **Evaluation Intent:** *Underperforming branches ranked by lowest recovery rate*

#### Application Response Output:
```text
HEADLINE: Collection efficiency by branch (FY27 to date)
SUMMARY / ANSWER:
Head Office — Credit Division is the only branch returned, with collection efficiency of 98.5% in FY27 to date. This measures total principal and interest paid divided by total principal and interest due, grouped by branch.

CHART SPEC: Type=bar, Title=Collection efficiency by branch (FY27 to date)
COLUMNS: Branch, Collection efficiency
SAMPLE ROWS (1 total): [{"branch": "Head Office — Credit Division", "collection_efficiency": 98.54437200622546, "branch__raw": 4.0}]

GOVERNED SQL QUERY:
SELECT lam."branch_code" AS branch,
       (100.0 * COALESCE(SUM(repay.total_paid), 0) / NULLIF(SUM(repay.total_due), 0)) AS collection_efficiency
FROM gold.loan_repayment_events AS repay
     JOIN gold.loan_account_master AS lam ON repay."entity_num" = lam."entity_num" AND repay."loan_account_number" = lam."loan_account_number"
WHERE repay."repayment_date" BETWEEN DATE '2026-04-01' AND DATE '2026-08-24'
GROUP BY lam."branch_code"
ORDER BY (100.0 * COALESCE(SUM(repay.total_paid), 0) / NULLIF(SUM(repay.total_due), 0)) ASC NULLS LAST
LIMIT 200
```

---

### Q066: Which branches have the highest collection efficiency?

- **Domain:** `Loan Book` — *Collections & Repayments*
- **Status:** 🟢 **Answered**
- **Latency:** `3.79s`
- **Chart Type:** `bar`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `chart`
- **Evaluation Intent:** *Top performing branches ranked by collection recovery percentage*

#### Application Response Output:
```text
HEADLINE: Collection efficiency by branch (FY27 to date)
SUMMARY / ANSWER:
Head Office — Credit Division is the only branch returned, with collection efficiency of 98.5% in FY27 to date. This measures total principal and interest paid divided by total principal and interest due, grouped by branch.

CHART SPEC: Type=bar, Title=Collection efficiency by branch (FY27 to date)
COLUMNS: Branch, Collection efficiency
SAMPLE ROWS (1 total): [{"branch": "Head Office — Credit Division", "collection_efficiency": 98.54437200622546, "branch__raw": 4.0}]

GOVERNED SQL QUERY:
SELECT lam."branch_code" AS branch,
       (100.0 * COALESCE(SUM(repay.total_paid), 0) / NULLIF(SUM(repay.total_due), 0)) AS collection_efficiency
FROM gold.loan_repayment_events AS repay
     JOIN gold.loan_account_master AS lam ON repay."entity_num" = lam."entity_num" AND repay."loan_account_number" = lam."loan_account_number"
WHERE repay."repayment_date" BETWEEN DATE '2026-04-01' AND DATE '2026-08-24'
GROUP BY lam."branch_code"
ORDER BY (100.0 * COALESCE(SUM(repay.total_paid), 0) / NULLIF(SUM(repay.total_due), 0)) DESC NULLS LAST
LIMIT 200
```

---

### Q067: Show collection efficiency by product this financial year.

- **Domain:** `Loan Book` — *Collections & Repayments*
- **Status:** 🟢 **Answered**
- **Latency:** `6.12s`
- **Chart Type:** `bar`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `chart`
- **Evaluation Intent:** *Product-level collection efficiency across Gold, MSME, and Retail*

#### Application Response Output:
```text
HEADLINE: Collection efficiency by product (FY27 to date)
SUMMARY / ANSWER:
Business & MSME Loans is the only product returned, with collection efficiency of 98.5% in FY27 to date. This measures total principal and interest paid divided by total principal and interest due, grouped by product.

CHART SPEC: Type=bar, Title=Collection efficiency by product (FY27 to date)
COLUMNS: Product, Collection efficiency
SAMPLE ROWS (1 total): [{"product": "Business & MSME Loans", "collection_efficiency": 98.54437200622546, "product__raw": 16.0}]

GOVERNED SQL QUERY:
SELECT lam."product_code" AS product,
       (100.0 * COALESCE(SUM(repay.total_paid), 0) / NULLIF(SUM(repay.total_due), 0)) AS collection_efficiency
FROM gold.loan_repayment_events AS repay
     JOIN gold.loan_account_master AS lam ON repay."entity_num" = lam."entity_num" AND repay."loan_account_number" = lam."loan_account_number"
WHERE repay."repayment_date" BETWEEN DATE '2026-04-01' AND DATE '2026-08-24'
GROUP BY lam."product_code"
ORDER BY (100.0 * COALESCE(SUM(repay.total_paid), 0) / NULLIF(SUM(repay.total_due), 0)) DESC NULLS LAST
LIMIT 200
```

---

### Q068: What is the collection efficiency for Gold Loans?

- **Domain:** `Loan Book` — *Collections & Repayments*
- **Status:** 🟢 **Answered**
- **Latency:** `56.24s`
- **Chart Type:** `table`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `chart`
- **Evaluation Intent:** *Collection efficiency for Product Code 1 (Gold Loans)*

#### Application Response Output:
```text
HEADLINE: What is the collection efficiency for Gold Loans (Generated query — not a reviewed metric)
SUMMARY / ANSWER:
The query returned 1 row(s) covering avg collection efficiency. Average collection efficiency for Gold Loans (product_code=1) based on repayment events. This uses a validated read-only generated query rather than a reviewed metric; check Source details before relying on it.

CHART SPEC: Type=table, Title=What is the collection efficiency for Gold Loans (Generated query — not a reviewed metric)
COLUMNS: Avg Collection Efficiency
SAMPLE ROWS (1 total): [{"avg_collection_efficiency": null}]

GOVERNED SQL QUERY:
SELECT
  AVG(collection_efficiency) AS avg_collection_efficiency
FROM gold.loan_repayment_events
WHERE
  product_code = 1 AND repayment_date >= CAST('2023-01-01' AS DATE)
LIMIT 100
```

---

### Q069: What is the collection efficiency for MSME Loans?

- **Domain:** `Loan Book` — *Collections & Repayments*
- **Status:** 🔴 **Error**
- **Latency:** `90.58s`
- **Chart Type:** `N/A`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `error`
- **Evaluation Intent:** *Collection efficiency for Product Code 16 (Business & MSME Loans)*

#### Application Response Output:
```text
ERROR DETAIL: No intelligence source produced a usable answer.
```

---

### Q070: What is the collection efficiency for Microfinance and Retail EMI?

- **Domain:** `Loan Book` — *Collections & Repayments*
- **Status:** 🔴 **Error**
- **Latency:** `90.53s`
- **Chart Type:** `N/A`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `error`
- **Evaluation Intent:** *Collection efficiency for Product Code 13 (Microfinance / Retail EMI)*

#### Application Response Output:
```text
ERROR DETAIL: No intelligence source produced a usable answer.
```

---

### Q071: Show collection efficiency by scheme.

- **Domain:** `Loan Book` — *Collections & Repayments*
- **Status:** 🟢 **Answered**
- **Latency:** `1.52s`
- **Chart Type:** `bar`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `chart`
- **Evaluation Intent:** *Scheme-level collection efficiency breakdown*

#### Application Response Output:
```text
HEADLINE: Amount collected by scheme (all time)
SUMMARY / ANSWER:
MSME Loans has the highest amount collected, at ₹6.96 Cr in all time, 31% of the total across 8 schemes. This measures principal plus interest paid in the period, grouped by scheme.

CHART SPEC: Type=bar, Title=Amount collected by scheme (all time)
COLUMNS: Scheme, Amount collected
SAMPLE ROWS (8 total): [{"scheme": "MSME Loans", "amount_collected": 69580395.04, "scheme__raw": "1616"}, {"scheme": "Site / Housing Construction / House Repair", "amount_collected": 48066140.12, "scheme__raw": "1618"}, {"scheme": "Personal Loan", "amount_collected": 45050601.04, "scheme__raw": "1617"}]

GOVERNED SQL QUERY:
SELECT lam."scheme_code" AS scheme,
       SUM(repay.total_paid) AS amount_collected
FROM gold.loan_repayment_events AS repay
     JOIN gold.loan_account_master AS lam ON repay."entity_num" = lam."entity_num" AND repay."loan_account_number" = lam."loan_account_number"
WHERE repay."repayment_date" BETWEEN DATE '2000-01-01' AND DATE '2026-08-24'
GROUP BY lam."scheme_code"
ORDER BY SUM(repay.total_paid) DESC NULLS LAST
LIMIT 200
```

---

### Q072: What is the total repayment amount collected in the last 30 days?

- **Domain:** `Loan Book` — *Collections & Repayments*
- **Status:** 🟢 **Answered**
- **Latency:** `41.48s`
- **Chart Type:** `kpi`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `chart`
- **Evaluation Intent:** *Repayment cash collections in recent 30-day window*

#### Application Response Output:
```text
HEADLINE: Amount collected (last 30 days)
SUMMARY / ANSWER:
Amount collected was ₹1.01 Cr in last 30 days. This measures principal plus interest paid in the period.

CHART SPEC: Type=kpi, Title=Amount collected (last 30 days)
COLUMNS: Amount collected
SAMPLE ROWS (1 total): [{"amount_collected": 10108570.7}]

GOVERNED SQL QUERY:
SELECT SUM(repay.total_paid) AS amount_collected
FROM gold.loan_repayment_events AS repay
WHERE repay."repayment_date" BETWEEN DATE '2026-07-26' AND DATE '2026-08-24'
LIMIT 200
```

---

### Q073: What was the total amount collected last quarter?

- **Domain:** `Loan Book` — *Collections & Repayments*
- **Status:** 🟢 **Answered**
- **Latency:** `3.73s`
- **Chart Type:** `kpi`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `chart`
- **Evaluation Intent:** *Total collections (principal + interest) in Q2 2026*

#### Application Response Output:
```text
HEADLINE: Amount collected (Q2 2026)
SUMMARY / ANSWER:
Amount collected was ₹12.54 Cr in Q2 2026. This measures principal plus interest paid in the period.

CHART SPEC: Type=kpi, Title=Amount collected (Q2 2026)
COLUMNS: Amount collected
SAMPLE ROWS (1 total): [{"amount_collected": 125434573.58}]

GOVERNED SQL QUERY:
SELECT SUM(repay.total_paid) AS amount_collected
FROM gold.loan_repayment_events AS repay
WHERE repay."repayment_date" BETWEEN DATE '2026-04-01' AND DATE '2026-06-30'
LIMIT 200
```

---

### Q074: What is the total amount collected this financial year?

- **Domain:** `Loan Book` — *Collections & Repayments*
- **Status:** 🟢 **Answered**
- **Latency:** `6.15s`
- **Chart Type:** `kpi`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `chart`
- **Evaluation Intent:** *FYTD total cash collections from repayment events*

#### Application Response Output:
```text
HEADLINE: Amount collected (FY27 to date)
SUMMARY / ANSWER:
Amount collected was ₹19.17 Cr in FY27 to date. This measures principal plus interest paid in the period.

CHART SPEC: Type=kpi, Title=Amount collected (FY27 to date)
COLUMNS: Amount collected
SAMPLE ROWS (1 total): [{"amount_collected": 191682408.46}]

GOVERNED SQL QUERY:
SELECT SUM(repay.total_paid) AS amount_collected
FROM gold.loan_repayment_events AS repay
WHERE repay."repayment_date" BETWEEN DATE '2026-04-01' AND DATE '2026-08-24'
LIMIT 200
```

---

### Q075: What is the total principal collected this financial year?

- **Domain:** `Loan Book` — *Collections & Repayments*
- **Status:** 🟢 **Answered**
- **Latency:** `5.93s`
- **Chart Type:** `kpi`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `chart`
- **Evaluation Intent:** *FYTD principal recovered from repayment events*

#### Application Response Output:
```text
HEADLINE: Principal collected (FY27 to date)
SUMMARY / ANSWER:
Principal collected was ₹10.61 Cr in FY27 to date. This measures principal paid in the period.

CHART SPEC: Type=kpi, Title=Principal collected (FY27 to date)
COLUMNS: Principal collected
SAMPLE ROWS (1 total): [{"principal_collected": 106125149.3}]

GOVERNED SQL QUERY:
SELECT SUM(repay.principal_paid) AS principal_collected
FROM gold.loan_repayment_events AS repay
WHERE repay."repayment_date" BETWEEN DATE '2026-04-01' AND DATE '2026-08-24'
LIMIT 200
```

---

### Q076: What is the total interest amount collected this financial year?

- **Domain:** `Loan Book` — *Collections & Repayments*
- **Status:** 🟢 **Answered**
- **Latency:** `6.01s`
- **Chart Type:** `kpi`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `chart`
- **Evaluation Intent:** *FYTD interest income collected from repayment events*

#### Application Response Output:
```text
HEADLINE: Interest collected (FY27 to date)
SUMMARY / ANSWER:
Interest collected was ₹8.56 Cr in FY27 to date. This measures interest paid in the period.

CHART SPEC: Type=kpi, Title=Interest collected (FY27 to date)
COLUMNS: Interest collected
SAMPLE ROWS (1 total): [{"interest_collected": 85557259.16}]

GOVERNED SQL QUERY:
SELECT SUM(repay.interest_paid) AS interest_collected
FROM gold.loan_repayment_events AS repay
WHERE repay."repayment_date" BETWEEN DATE '2026-04-01' AND DATE '2026-08-24'
LIMIT 200
```

---

### Q077: What was the total amount due in the last quarter?

- **Domain:** `Loan Book` — *Collections & Repayments*
- **Status:** 🟢 **Answered**
- **Latency:** `3.55s`
- **Chart Type:** `kpi`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `chart`
- **Evaluation Intent:** *Billed demand (principal + interest due) in Q2 2026*

#### Application Response Output:
```text
HEADLINE: Amount due (Q2 2026)
SUMMARY / ANSWER:
Amount due was ₹12.57 Cr in Q2 2026. This measures principal plus interest due in the period.

CHART SPEC: Type=kpi, Title=Amount due (Q2 2026)
COLUMNS: Amount due
SAMPLE ROWS (1 total): [{"amount_due": 125699518.87}]

GOVERNED SQL QUERY:
SELECT SUM(repay.total_due) AS amount_due
FROM gold.loan_repayment_events AS repay
WHERE repay."repayment_date" BETWEEN DATE '2026-04-01' AND DATE '2026-06-30'
LIMIT 200
```

---

### Q078: What is the total collection shortfall this financial year?

- **Domain:** `Loan Book` — *Collections & Repayments*
- **Status:** 🟢 **Answered**
- **Latency:** `6.15s`
- **Chart Type:** `kpi`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `chart`
- **Evaluation Intent:** *FYTD unpaid gap (amount due minus amount paid)*

#### Application Response Output:
```text
HEADLINE: Collection shortfall (FY27 to date)
SUMMARY / ANSWER:
Collection shortfall was ₹28.31 L in FY27 to date. This measures amount due minus amount paid in the period.

CHART SPEC: Type=kpi, Title=Collection shortfall (FY27 to date)
COLUMNS: Collection shortfall
SAMPLE ROWS (1 total): [{"collection_shortfall": 2831397.41}]

GOVERNED SQL QUERY:
SELECT SUM(repay.collection_shortfall) AS collection_shortfall
FROM gold.loan_repayment_events AS repay
WHERE repay."repayment_date" BETWEEN DATE '2026-04-01' AND DATE '2026-08-24'
LIMIT 200
```

---

### Q079: Show monthly collection shortfall over the last 12 months.

- **Domain:** `Loan Book` — *Collections & Repayments*
- **Status:** 🟢 **Answered**
- **Latency:** `3.92s`
- **Chart Type:** `area`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `chart`
- **Evaluation Intent:** *12-month time-series of collection shortfall*

#### Application Response Output:
```text
HEADLINE: Collection shortfall by month (last 12 months)
SUMMARY / ANSWER:
Collection shortfall rose from ₹0 (Nov 2025) to ₹25.66 L (Jul 2026). This measures amount due minus amount paid in the period, grouped by month.

CHART SPEC: Type=area, Title=Collection shortfall by month (last 12 months)
COLUMNS: Month, Collection shortfall
SAMPLE ROWS (9 total): [{"month": "Nov 2025", "collection_shortfall": 0.0, "month__raw": "2025-11-01"}, {"month": "Dec 2025", "collection_shortfall": 0.0, "month__raw": "2025-12-01"}, {"month": "Jan 2026", "collection_shortfall": 0.0, "month__raw": "2026-01-01"}]

GOVERNED SQL QUERY:
SELECT DATE_TRUNC('month', repay."repayment_date")::date AS month,
       SUM(repay.collection_shortfall) AS collection_shortfall
FROM gold.loan_repayment_events AS repay
WHERE repay."repayment_date" BETWEEN DATE '2025-08-25' AND DATE '2026-08-24'
GROUP BY DATE_TRUNC('month', repay."repayment_date")::date
ORDER BY DATE_TRUNC('month', repay."repayment_date")::date ASC
LIMIT 200
```

---

### Q080: Show the trend of monthly collections over the last 12 months.

- **Domain:** `Loan Book` — *Collections & Repayments*
- **Status:** 🟢 **Answered**
- **Latency:** `4.81s`
- **Chart Type:** `area`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `chart`
- **Evaluation Intent:** *12-month monthly cash collections time-series*

#### Application Response Output:
```text
HEADLINE: Amount collected by month (last 12 months)
SUMMARY / ANSWER:
Amount collected rose from ₹2.14 L (Nov 2025) to ₹6.62 Cr (Jul 2026), a change of 30877.8%. This measures principal plus interest paid in the period, grouped by month.

CHART SPEC: Type=area, Title=Amount collected by month (last 12 months)
COLUMNS: Month, Amount collected
SAMPLE ROWS (9 total): [{"month": "Nov 2025", "amount_collected": 213856.0, "month__raw": "2025-11-01"}, {"month": "Dec 2025", "amount_collected": 1205153.0, "month__raw": "2025-12-01"}, {"month": "Jan 2026", "amount_collected": 4794129.0, "month__raw": "2026-01-01"}]

GOVERNED SQL QUERY:
SELECT DATE_TRUNC('month', repay."repayment_date")::date AS month,
       SUM(repay.total_paid) AS amount_collected
FROM gold.loan_repayment_events AS repay
WHERE repay."repayment_date" BETWEEN DATE '2025-08-25' AND DATE '2026-08-24'
GROUP BY DATE_TRUNC('month', repay."repayment_date")::date
ORDER BY DATE_TRUNC('month', repay."repayment_date")::date ASC
LIMIT 200
```

---

### Q081: What is the total payment receipt amount across all receipts?

- **Domain:** `Loan Book` — *Collections & Repayments*
- **Status:** 🟢 **Answered**
- **Latency:** `3.85s`
- **Chart Type:** `kpi`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `chart`
- **Evaluation Intent:** *Total cash collected recorded in payment receipt events*

#### Application Response Output:
```text
HEADLINE: Payment receipts (all time)
SUMMARY / ANSWER:
Payment receipts was ₹46.48 Cr in all time. This measures sum of governed loan receipt amounts in the period.

CHART SPEC: Type=kpi, Title=Payment receipts (all time)
COLUMNS: Payment receipts
SAMPLE ROWS (1 total): [{"receipt_total": 464832760.7}]

GOVERNED SQL QUERY:
SELECT SUM(receipt.receipt_amount) AS receipt_total
FROM gold.payment_receipt_events AS receipt
WHERE receipt."receipt_date" BETWEEN DATE '2000-01-01' AND DATE '2026-08-24'
LIMIT 200
```

---

### Q082: Show payment receipts breakdown by receipt mode.

- **Domain:** `Loan Book` — *Collections & Repayments*
- **Status:** 🟢 **Answered**
- **Latency:** `4.31s`
- **Chart Type:** `donut`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `chart`
- **Evaluation Intent:** *Payment receipt distribution by mode (Cash, Transfer, Cheque, Online)*

#### Application Response Output:
```text
HEADLINE: Payment receipts by receipt mode (all time)
SUMMARY / ANSWER:
2 has the highest payment receipts, at ₹30.10 Cr in all time, 65% of the total across 6 receipt modes. This measures sum of governed loan receipt amounts in the period, grouped by receipt mode.

CHART SPEC: Type=donut, Title=Payment receipts by receipt mode (all time)
COLUMNS: Receipt mode, Payment receipts
SAMPLE ROWS (6 total): [{"receipt_mode": "2", "receipt_total": 300977983.9, "receipt_mode__raw": "2"}, {"receipt_mode": "5", "receipt_total": 160061083.92, "receipt_mode__raw": "5"}, {"receipt_mode": "6", "receipt_total": 3488430.88, "receipt_mode__raw": "6"}]

GOVERNED SQL QUERY:
SELECT receipt."receipt_mode" AS receipt_mode,
       SUM(receipt.receipt_amount) AS receipt_total
FROM gold.payment_receipt_events AS receipt
WHERE receipt."receipt_date" BETWEEN DATE '2000-01-01' AND DATE '2026-08-24'
GROUP BY receipt."receipt_mode"
ORDER BY SUM(receipt.receipt_amount) DESC NULLS LAST
LIMIT 200
```

---

### Q083: Show total payment receipts by receipt branch.

- **Domain:** `Loan Book` — *Collections & Repayments*
- **Status:** 🟢 **Answered**
- **Latency:** `4.06s`
- **Chart Type:** `bar`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `chart`
- **Evaluation Intent:** *Branch-level payment receipt totals*

#### Application Response Output:
```text
HEADLINE: Payment receipts by receipt branch (all time)
SUMMARY / ANSWER:
Head Office — Credit Division has the highest payment receipts, at ₹30.85 Cr in all time, 66% of the total across 5 receipt branches. This measures sum of governed loan receipt amounts in the period, grouped by receipt branch.

CHART SPEC: Type=bar, Title=Payment receipts by receipt branch (all time)
COLUMNS: Receipt branch, Payment receipts
SAMPLE ROWS (5 total): [{"receipt_branch": "Head Office — Credit Division", "receipt_total": 308510188.04, "receipt_branch__raw": 4.0}, {"receipt_branch": "Head Office", "receipt_total": 156148001.66, "receipt_branch__raw": 1.0}, {"receipt_branch": "Branch 3", "receipt_total": 77365.0, "receipt_branch__raw": 3.0}]

GOVERNED SQL QUERY:
SELECT receipt."receipt_branch" AS receipt_branch,
       SUM(receipt.receipt_amount) AS receipt_total
FROM gold.payment_receipt_events AS receipt
WHERE receipt."receipt_date" BETWEEN DATE '2000-01-01' AND DATE '2026-08-24'
GROUP BY receipt."receipt_branch"
ORDER BY SUM(receipt.receipt_amount) DESC NULLS LAST
LIMIT 200
```

---

### Q084: What is the total amount recorded in collection activity summaries?

- **Domain:** `Loan Book` — *Collections & Repayments*
- **Status:** 🟢 **Answered**
- **Latency:** `4.40s`
- **Chart Type:** `kpi`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `chart`
- **Evaluation Intent:** *Sum of final collection amounts from recovery activity events*

#### Application Response Output:
```text
HEADLINE: Collection activity amount (all time)
SUMMARY / ANSWER:
Collection activity amount was ₹28.77 L in all time. This measures sum of final collection amounts recorded in collector activity summaries.

CHART SPEC: Type=kpi, Title=Collection activity amount (all time)
COLUMNS: Collection activity amount
SAMPLE ROWS (1 total): [{"collection_activity_total": 2877148.0}]

GOVERNED SQL QUERY:
SELECT SUM(collection_activity.final_collection_amount) AS collection_activity_total
FROM gold.collection_activity_events AS collection_activity
WHERE collection_activity."activity_date" BETWEEN DATE '2000-01-01' AND DATE '2026-08-24'
LIMIT 200
```

---

### Q085: Show contractual scheduled loan instalments falling due in the next quarter.

- **Domain:** `Loan Book` — *Collections & Repayments*
- **Status:** 🟢 **Answered**
- **Latency:** `8.11s`
- **Chart Type:** `bar`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `chart`
- **Evaluation Intent:** *Future contractual scheduled principal and interest dues*

#### Application Response Output:
```text
HEADLINE: Scheduled instalments by branch (2026-07-01 to 2026-09-30)
SUMMARY / ANSWER:
Head Office — Credit Division has the highest scheduled instalments, at ₹14.35 Cr in 2026-07-01 to 2026-09-30, 100% of the total across 2 branches. This measures contractual principal plus interest scheduled in the period, grouped by branch.

CHART SPEC: Type=bar, Title=Scheduled instalments by branch (2026-07-01 to 2026-09-30)
COLUMNS: Branch, Scheduled instalments
SAMPLE ROWS (2 total): [{"branch": "Head Office — Credit Division", "scheduled_amount": 143478212.0, "branch__raw": 4.0}, {"branch": "Head Office", "scheduled_amount": 10845.0, "branch__raw": 1.0}]

GOVERNED SQL QUERY:
SELECT lam."branch_code" AS branch,
       SUM(sched.scheduled_total) AS scheduled_amount
FROM gold.loan_schedule_events AS sched
     JOIN gold.loan_account_master AS lam ON sched."entity_num" = lam."entity_num" AND sched."loan_account_number" = lam."loan_account_number"
WHERE sched."scheduled_date" BETWEEN DATE '2026-07-01' AND DATE '2026-09-30'
GROUP BY lam."branch_code"
ORDER BY SUM(sched.scheduled_total) DESC NULLS LAST
LIMIT 200
```

---

### Q086: What is our current PAR 30?

- **Domain:** `Loan Book` — *Delinquency & PAR*
- **Status:** 🟢 **Answered**
- **Latency:** `3.67s`
- **Chart Type:** `kpi`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `chart`
- **Evaluation Intent:** *Current Portfolio at Risk > 30 days percentage*

#### Application Response Output:
```text
HEADLINE: PAR 30 (As at 24 Aug 2026)
SUMMARY / ANSWER:
PAR 30 was 0.27% as at 24 Aug 2026. This measures principal outstanding over 30 DPD divided by classified principal outstanding. Definition of PAR 30 is pending client sign-off.

CHART SPEC: Type=kpi, Title=PAR 30 (As at 24 Aug 2026)
COLUMNS: PAR 30
SAMPLE ROWS (1 total): [{"par_30": 0.26855264734033535}]

GOVERNED SQL QUERY:
SELECT (100.0 * COALESCE(SUM(portfolio.principal_outstanding) FILTER (WHERE portfolio.is_par30), 0) / NULLIF(SUM(portfolio.principal_outstanding), 0)) AS par_30
FROM gold.portfolio_snapshot_as_of(DATE '2026-08-24') AS portfolio
LIMIT 200
```

---

### Q087: What is our current PAR 60?

- **Domain:** `Loan Book` — *Delinquency & PAR*
- **Status:** 🟢 **Answered**
- **Latency:** `3.71s`
- **Chart Type:** `kpi`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `chart`
- **Evaluation Intent:** *Current Portfolio at Risk > 60 days percentage*

#### Application Response Output:
```text
HEADLINE: PAR 60 (As at 24 Aug 2026)
SUMMARY / ANSWER:
PAR 60 was 0.03% as at 24 Aug 2026. This measures principal outstanding over 60 DPD divided by classified principal outstanding. Definition of PAR 60 is pending client sign-off.

CHART SPEC: Type=kpi, Title=PAR 60 (As at 24 Aug 2026)
COLUMNS: PAR 60
SAMPLE ROWS (1 total): [{"par_60": 0.02923313739098355}]

GOVERNED SQL QUERY:
SELECT (100.0 * COALESCE(SUM(portfolio.principal_outstanding) FILTER (WHERE portfolio.is_par60), 0) / NULLIF(SUM(portfolio.principal_outstanding), 0)) AS par_60
FROM gold.portfolio_snapshot_as_of(DATE '2026-08-24') AS portfolio
LIMIT 200
```

---

### Q088: What is our current PAR 90?

- **Domain:** `Loan Book` — *Delinquency & PAR*
- **Status:** 🟢 **Answered**
- **Latency:** `3.61s`
- **Chart Type:** `kpi`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `chart`
- **Evaluation Intent:** *Current Portfolio at Risk > 90 days percentage*

#### Application Response Output:
```text
HEADLINE: PAR 90 (As at 24 Aug 2026)
SUMMARY / ANSWER:
PAR 90 was 0.02% as at 24 Aug 2026. This measures principal outstanding over 90 DPD divided by classified principal outstanding. Definition of PAR 90 is pending client sign-off.

CHART SPEC: Type=kpi, Title=PAR 90 (As at 24 Aug 2026)
COLUMNS: PAR 90
SAMPLE ROWS (1 total): [{"par_90": 0.02008484359049893}]

GOVERNED SQL QUERY:
SELECT (100.0 * COALESCE(SUM(portfolio.principal_outstanding) FILTER (WHERE portfolio.is_par90), 0) / NULLIF(SUM(portfolio.principal_outstanding), 0)) AS par_90
FROM gold.portfolio_snapshot_as_of(DATE '2026-08-24') AS portfolio
LIMIT 200
```

---

### Q089: How has PAR 30 moved over the last three months?

- **Domain:** `Loan Book` — *Delinquency & PAR*
- **Status:** 🟢 **Answered**
- **Latency:** `7.46s`
- **Chart Type:** `line`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `chart`
- **Evaluation Intent:** *90-day trend of PAR 30 delinquency ratio*

#### Application Response Output:
```text
HEADLINE: PAR 30 by month (As at 31 Jul 2026)
SUMMARY / ANSWER:
PAR 30 fell from 1.2% (May 2026) to 0.27% (Jul 2026), a change of 78.1%. This measures principal outstanding over 30 DPD divided by classified principal outstanding, grouped by month. Definition of PAR 30 is pending client sign-off.

CHART SPEC: Type=line, Title=PAR 30 by month (As at 31 Jul 2026)
COLUMNS: Month, PAR 30
SAMPLE ROWS (3 total): [{"month": "May 2026", "par_30": 1.2236990803010663, "month__raw": "2026-05-01"}, {"month": "Jun 2026", "par_30": 0.08999595283058374, "month__raw": "2026-06-01"}, {"month": "Jul 2026", "par_30": 0.26855264734033535, "month__raw": "2026-07-01"}]

GOVERNED SQL QUERY:
SELECT buckets.bucket_start AS month,
       (100.0 * COALESCE(SUM(portfolio.principal_outstanding) FILTER (WHERE portfolio.is_par30), 0) / NULLIF(SUM(portfolio.principal_outstanding), 0)) AS par_30
FROM (SELECT generate_series(DATE '2026-05-01'::date, DATE '2026-07-31'::date,
                             INTERVAL '1 month')::date AS bucket_start) AS buckets
     LEFT JOIN LATERAL gold.portfolio_snapshot_as_of(
       LEAST((buckets.bucket_start + INTERVAL '1 month' - INTERVAL '1 day')::date, DATE '2026-07-31'::date)
     ) AS portfolio ON TRUE
GROUP BY buckets.bucket_start
ORDER BY buckets.bucket_start ASC
LIMIT 200
```

---

### Q090: Show PAR 30 breakdown by branch.

- **Domain:** `Loan Book` — *Delinquency & PAR*
- **Status:** 🟢 **Answered**
- **Latency:** `5.70s`
- **Chart Type:** `bar`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `chart`
- **Evaluation Intent:** *Branch-level PAR 30 risk comparison*

#### Application Response Output:
```text
HEADLINE: PAR 30 by branch (As at 24 Aug 2026)
SUMMARY / ANSWER:
Head Office — Credit Division is the only branch returned, with par 30 of 0.27% as at 24 Aug 2026. This measures principal outstanding over 30 DPD divided by classified principal outstanding, grouped by branch. Definition of PAR 30 is pending client sign-off.

CHART SPEC: Type=bar, Title=PAR 30 by branch (As at 24 Aug 2026)
COLUMNS: Branch, PAR 30
SAMPLE ROWS (1 total): [{"branch": "Head Office — Credit Division", "par_30": 0.26855264734033535, "branch__raw": 4.0}]

GOVERNED SQL QUERY:
SELECT lam."branch_code" AS branch,
       (100.0 * COALESCE(SUM(portfolio.principal_outstanding) FILTER (WHERE portfolio.is_par30), 0) / NULLIF(SUM(portfolio.principal_outstanding), 0)) AS par_30
FROM gold.portfolio_snapshot_as_of(DATE '2026-08-24') AS portfolio
     JOIN gold.loan_account_master AS lam ON portfolio."entity_num" = lam."entity_num" AND portfolio."loan_account_number" = lam."loan_account_number"
GROUP BY lam."branch_code"
ORDER BY (100.0 * COALESCE(SUM(portfolio.principal_outstanding) FILTER (WHERE portfolio.is_par30), 0) / NULLIF(SUM(portfolio.principal_outstanding), 0)) DESC NULLS LAST
LIMIT 200
```

---

### Q091: Show PAR 30 breakdown by product type.

- **Domain:** `Loan Book` — *Delinquency & PAR*
- **Status:** 🟢 **Answered**
- **Latency:** `7.40s`
- **Chart Type:** `bar`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `chart`
- **Evaluation Intent:** *PAR 30 ratio across Gold, Microfinance, and MSME products*

#### Application Response Output:
```text
HEADLINE: PAR 30 by product (As at 24 Aug 2026)
SUMMARY / ANSWER:
Business & MSME Loans is the only product returned, with par 30 of 0.27% as at 24 Aug 2026. This measures principal outstanding over 30 DPD divided by classified principal outstanding, grouped by product. Definition of PAR 30 is pending client sign-off.

CHART SPEC: Type=bar, Title=PAR 30 by product (As at 24 Aug 2026)
COLUMNS: Product, PAR 30
SAMPLE ROWS (1 total): [{"product": "Business & MSME Loans", "par_30": 0.26855264734033535, "product__raw": 16.0}]

GOVERNED SQL QUERY:
SELECT lam."product_code" AS product,
       (100.0 * COALESCE(SUM(portfolio.principal_outstanding) FILTER (WHERE portfolio.is_par30), 0) / NULLIF(SUM(portfolio.principal_outstanding), 0)) AS par_30
FROM gold.portfolio_snapshot_as_of(DATE '2026-08-24') AS portfolio
     JOIN gold.loan_account_master AS lam ON portfolio."entity_num" = lam."entity_num" AND portfolio."loan_account_number" = lam."loan_account_number"
GROUP BY lam."product_code"
ORDER BY (100.0 * COALESCE(SUM(portfolio.principal_outstanding) FILTER (WHERE portfolio.is_par30), 0) / NULLIF(SUM(portfolio.principal_outstanding), 0)) DESC NULLS LAST
LIMIT 200
```

---

### Q092: Show PAR 30 breakdown by scheme.

- **Domain:** `Loan Book` — *Delinquency & PAR*
- **Status:** 🟢 **Answered**
- **Latency:** `5.74s`
- **Chart Type:** `bar`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `chart`
- **Evaluation Intent:** *Scheme-level PAR 30 delinquency ratio*

#### Application Response Output:
```text
HEADLINE: PAR 30 by scheme (As at 24 Aug 2026)
SUMMARY / ANSWER:
Dairy Loan has the highest par 30, at 1.2% as at 24 Aug 2026. This measures principal outstanding over 30 DPD divided by classified principal outstanding, grouped by scheme. Definition of PAR 30 is pending client sign-off.

CHART SPEC: Type=bar, Title=PAR 30 by scheme (As at 24 Aug 2026)
COLUMNS: Scheme, PAR 30
SAMPLE ROWS (8 total): [{"scheme": "Dairy Loan", "par_30": 1.241914877328521, "scheme__raw": "1622"}, {"scheme": "Loan Against Property (Scheme #1619)", "par_30": 0.9401292302328449, "scheme__raw": "1619"}, {"scheme": "Farming Loan", "par_30": 0.2811763047327321, "scheme__raw": "1621"}]

GOVERNED SQL QUERY:
SELECT lam."scheme_code" AS scheme,
       (100.0 * COALESCE(SUM(portfolio.principal_outstanding) FILTER (WHERE portfolio.is_par30), 0) / NULLIF(SUM(portfolio.principal_outstanding), 0)) AS par_30
FROM gold.portfolio_snapshot_as_of(DATE '2026-08-24') AS portfolio
     JOIN gold.loan_account_master AS lam ON portfolio."entity_num" = lam."entity_num" AND portfolio."loan_account_number" = lam."loan_account_number"
GROUP BY lam."scheme_code"
ORDER BY (100.0 * COALESCE(SUM(portfolio.principal_outstanding) FILTER (WHERE portfolio.is_par30), 0) / NULLIF(SUM(portfolio.principal_outstanding), 0)) DESC NULLS LAST
LIMIT 200
```

---

### Q093: Show PAR 60 breakdown by product.

- **Domain:** `Loan Book` — *Delinquency & PAR*
- **Status:** 🟢 **Answered**
- **Latency:** `5.65s`
- **Chart Type:** `bar`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `chart`
- **Evaluation Intent:** *PAR 60 ratio comparison across product lines*

#### Application Response Output:
```text
HEADLINE: PAR 60 by product (As at 24 Aug 2026)
SUMMARY / ANSWER:
Business & MSME Loans is the only product returned, with par 60 of 0.03% as at 24 Aug 2026. This measures principal outstanding over 60 DPD divided by classified principal outstanding, grouped by product. Definition of PAR 60 is pending client sign-off.

CHART SPEC: Type=bar, Title=PAR 60 by product (As at 24 Aug 2026)
COLUMNS: Product, PAR 60
SAMPLE ROWS (1 total): [{"product": "Business & MSME Loans", "par_60": 0.02923313739098355, "product__raw": 16.0}]

GOVERNED SQL QUERY:
SELECT lam."product_code" AS product,
       (100.0 * COALESCE(SUM(portfolio.principal_outstanding) FILTER (WHERE portfolio.is_par60), 0) / NULLIF(SUM(portfolio.principal_outstanding), 0)) AS par_60
FROM gold.portfolio_snapshot_as_of(DATE '2026-08-24') AS portfolio
     JOIN gold.loan_account_master AS lam ON portfolio."entity_num" = lam."entity_num" AND portfolio."loan_account_number" = lam."loan_account_number"
GROUP BY lam."product_code"
ORDER BY (100.0 * COALESCE(SUM(portfolio.principal_outstanding) FILTER (WHERE portfolio.is_par60), 0) / NULLIF(SUM(portfolio.principal_outstanding), 0)) DESC NULLS LAST
LIMIT 200
```

---

### Q094: Show PAR 90 breakdown by product.

- **Domain:** `Loan Book` — *Delinquency & PAR*
- **Status:** 🟢 **Answered**
- **Latency:** `5.54s`
- **Chart Type:** `bar`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `chart`
- **Evaluation Intent:** *PAR 90 ratio comparison across product lines*

#### Application Response Output:
```text
HEADLINE: PAR 90 by product (As at 24 Aug 2026)
SUMMARY / ANSWER:
Business & MSME Loans is the only product returned, with par 90 of 0.02% as at 24 Aug 2026. This measures principal outstanding over 90 DPD divided by classified principal outstanding, grouped by product. Definition of PAR 90 is pending client sign-off.

CHART SPEC: Type=bar, Title=PAR 90 by product (As at 24 Aug 2026)
COLUMNS: Product, PAR 90
SAMPLE ROWS (1 total): [{"product": "Business & MSME Loans", "par_90": 0.02008484359049893, "product__raw": 16.0}]

GOVERNED SQL QUERY:
SELECT lam."product_code" AS product,
       (100.0 * COALESCE(SUM(portfolio.principal_outstanding) FILTER (WHERE portfolio.is_par90), 0) / NULLIF(SUM(portfolio.principal_outstanding), 0)) AS par_90
FROM gold.portfolio_snapshot_as_of(DATE '2026-08-24') AS portfolio
     JOIN gold.loan_account_master AS lam ON portfolio."entity_num" = lam."entity_num" AND portfolio."loan_account_number" = lam."loan_account_number"
GROUP BY lam."product_code"
ORDER BY (100.0 * COALESCE(SUM(portfolio.principal_outstanding) FILTER (WHERE portfolio.is_par90), 0) / NULLIF(SUM(portfolio.principal_outstanding), 0)) DESC NULLS LAST
LIMIT 200
```

---

### Q095: Which branches have the highest PAR 30 ratio?

- **Domain:** `Loan Book` — *Delinquency & PAR*
- **Status:** 🟢 **Answered**
- **Latency:** `3.89s`
- **Chart Type:** `bar`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `chart`
- **Evaluation Intent:** *Ranking branches with highest delinquency rates*

#### Application Response Output:
```text
HEADLINE: PAR 30 by branch (As at 24 Aug 2026)
SUMMARY / ANSWER:
Head Office — Credit Division is the only branch returned, with par 30 of 0.27% as at 24 Aug 2026. This measures principal outstanding over 30 DPD divided by classified principal outstanding, grouped by branch. Definition of PAR 30 is pending client sign-off.

CHART SPEC: Type=bar, Title=PAR 30 by branch (As at 24 Aug 2026)
COLUMNS: Branch, PAR 30
SAMPLE ROWS (1 total): [{"branch": "Head Office — Credit Division", "par_30": 0.26855264734033535, "branch__raw": 4.0}]

GOVERNED SQL QUERY:
SELECT lam."branch_code" AS branch,
       (100.0 * COALESCE(SUM(portfolio.principal_outstanding) FILTER (WHERE portfolio.is_par30), 0) / NULLIF(SUM(portfolio.principal_outstanding), 0)) AS par_30
FROM gold.portfolio_snapshot_as_of(DATE '2026-08-24') AS portfolio
     JOIN gold.loan_account_master AS lam ON portfolio."entity_num" = lam."entity_num" AND portfolio."loan_account_number" = lam."loan_account_number"
GROUP BY lam."branch_code"
ORDER BY (100.0 * COALESCE(SUM(portfolio.principal_outstanding) FILTER (WHERE portfolio.is_par30), 0) / NULLIF(SUM(portfolio.principal_outstanding), 0)) DESC NULLS LAST
LIMIT 200
```

---

### Q096: Break down the outstanding portfolio by DPD bucket.

- **Domain:** `Loan Book` — *Delinquency & PAR*
- **Status:** 🟢 **Answered**
- **Latency:** `1.38s`
- **Chart Type:** `donut`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `chart`
- **Evaluation Intent:** *Delinquency distribution across Current, 1-30, 31-60, 61-90, and 90+ buckets*

#### Application Response Output:
```text
HEADLINE: Principal outstanding by dpd bucket (As at 24 Aug 2026)
SUMMARY / ANSWER:
0 (current) has the highest principal outstanding, at ₹194.43 Cr as at 24 Aug 2026, 95% of the total across 5 dpd buckets. This measures principal outstanding from each classified account at the requested snapshot, grouped by dpd bucket.

CHART SPEC: Type=donut, Title=Principal outstanding by dpd bucket (As at 24 Aug 2026)
COLUMNS: DPD bucket, Principal outstanding
SAMPLE ROWS (5 total): [{"dpd_bucket": "0 (current)", "principal_outstanding": 1944297584.74, "dpd_bucket__raw": "0 (current)"}, {"dpd_bucket": "1-30", "principal_outstanding": 95603973.38, "dpd_bucket__raw": "1-30"}, {"dpd_bucket": "31-60", "principal_outstanding": 4895028.14, "dpd_bucket__raw": "31-60"}]

GOVERNED SQL QUERY:
SELECT CASE WHEN portfolio."dpd_days" = 0 THEN '0 (current)' WHEN portfolio."dpd_days" BETWEEN 1 AND 30 THEN '1-30' WHEN portfolio."dpd_days" BETWEEN 31 AND 60 THEN '31-60' WHEN portfolio."dpd_days" BETWEEN 61 AND 90 THEN '61-90' ELSE '90+' END AS dpd_bucket,
       SUM(portfolio.principal_outstanding) AS principal_outstanding
FROM gold.portfolio_snapshot_as_of(DATE '2026-08-24') AS portfolio
GROUP BY CASE WHEN portfolio."dpd_days" = 0 THEN '0 (current)' WHEN portfolio."dpd_days" BETWEEN 1 AND 30 THEN '1-30' WHEN portfolio."dpd_days" BETWEEN 31 AND 60 THEN '31-60' WHEN portfolio."dpd_days" BETWEEN 61 AND 90 THEN '61-90' ELSE '90+' END, CASE WHEN portfolio."dpd_days" = 0 THEN 0 WHEN portfolio."dpd_days" <= 30 THEN 1 WHEN portfolio."dpd_days" <= 60 THEN 2 WHEN portfolio."dpd_days" <= 90 THEN 3 ELSE 4 END
ORDER BY SUM(portfolio.principal_outstanding) DESC NULLS LAST
LIMIT 200
```

---

### Q097: Show loan account count by DPD bucket.

- **Domain:** `Loan Book` — *Delinquency & PAR*
- **Status:** 🟢 **Answered**
- **Latency:** `5.04s`
- **Chart Type:** `bar`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `chart`
- **Evaluation Intent:** *Count of accounts in each DPD ageing bucket*

#### Application Response Output:
```text
HEADLINE: Delinquent accounts by dpd bucket (As at 24 Aug 2026)
SUMMARY / ANSWER:
1-30 has the highest delinquent accounts, at 262 as at 24 Aug 2026, 96% of the total across 5 dpd buckets. This measures count of classified accounts with DPD greater than zero, grouped by dpd bucket.

CHART SPEC: Type=bar, Title=Delinquent accounts by dpd bucket (As at 24 Aug 2026)
COLUMNS: DPD bucket, Delinquent accounts
SAMPLE ROWS (5 total): [{"dpd_bucket": "1-30", "delinquent_account_count": 262, "dpd_bucket__raw": "1-30"}, {"dpd_bucket": "31-60", "delinquent_account_count": 9, "dpd_bucket__raw": "31-60"}, {"dpd_bucket": "90+", "delinquent_account_count": 1, "dpd_bucket__raw": "90+"}]

GOVERNED SQL QUERY:
SELECT CASE WHEN portfolio."dpd_days" = 0 THEN '0 (current)' WHEN portfolio."dpd_days" BETWEEN 1 AND 30 THEN '1-30' WHEN portfolio."dpd_days" BETWEEN 31 AND 60 THEN '31-60' WHEN portfolio."dpd_days" BETWEEN 61 AND 90 THEN '61-90' ELSE '90+' END AS dpd_bucket,
       COUNT(*) FILTER (WHERE portfolio.is_delinquent) AS delinquent_account_count
FROM gold.portfolio_snapshot_as_of(DATE '2026-08-24') AS portfolio
GROUP BY CASE WHEN portfolio."dpd_days" = 0 THEN '0 (current)' WHEN portfolio."dpd_days" BETWEEN 1 AND 30 THEN '1-30' WHEN portfolio."dpd_days" BETWEEN 31 AND 60 THEN '31-60' WHEN portfolio."dpd_days" BETWEEN 61 AND 90 THEN '61-90' ELSE '90+' END, CASE WHEN portfolio."dpd_days" = 0 THEN 0 WHEN portfolio."dpd_days" <= 30 THEN 1 WHEN portfolio."dpd_days" <= 60 THEN 2 WHEN portfolio."dpd_days" <= 90 THEN 3 ELSE 4 END
ORDER BY COUNT(*) FILTER (WHERE portfolio.is_delinquent) DESC NULLS LAST
LIMIT 200
```

---

### Q098: What is the total count of delinquent accounts in our portfolio?

- **Domain:** `Loan Book` — *Delinquency & PAR*
- **Status:** 🟢 **Answered**
- **Latency:** `3.65s`
- **Chart Type:** `kpi`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `chart`
- **Evaluation Intent:** *Count of accounts with DPD > 0*

#### Application Response Output:
```text
HEADLINE: Delinquent accounts (As at 24 Aug 2026)
SUMMARY / ANSWER:
Delinquent accounts was 273 as at 24 Aug 2026. This measures count of classified accounts with DPD greater than zero.

CHART SPEC: Type=kpi, Title=Delinquent accounts (As at 24 Aug 2026)
COLUMNS: Delinquent accounts
SAMPLE ROWS (1 total): [{"delinquent_account_count": 273}]

GOVERNED SQL QUERY:
SELECT COUNT(*) FILTER (WHERE portfolio.is_delinquent) AS delinquent_account_count
FROM gold.portfolio_snapshot_as_of(DATE '2026-08-24') AS portfolio
LIMIT 200
```

---

### Q099: What is the average DPD across all classified accounts?

- **Domain:** `Loan Book` — *Delinquency & PAR*
- **Status:** 🟢 **Answered**
- **Latency:** `3.55s`
- **Chart Type:** `kpi`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `chart`
- **Evaluation Intent:** *Mean days past due across portfolio snapshot*

#### Application Response Output:
```text
HEADLINE: Average DPD (As at 24 Aug 2026)
SUMMARY / ANSWER:
Average DPD was 0 as at 24 Aug 2026. This measures mean days past due across classified accounts at the snapshot.

CHART SPEC: Type=kpi, Title=Average DPD (As at 24 Aug 2026)
COLUMNS: Average DPD
SAMPLE ROWS (1 total): [{"avg_dpd": 0.13648005854372486}]

GOVERNED SQL QUERY:
SELECT (COALESCE(SUM(portfolio.dpd_days), 0) / NULLIF(COUNT(*), 0)) AS avg_dpd
FROM gold.portfolio_snapshot_as_of(DATE '2026-08-24') AS portfolio
LIMIT 200
```

---

### Q100: Show average DPD by branch.

- **Domain:** `Loan Book` — *Delinquency & PAR*
- **Status:** 🟢 **Answered**
- **Latency:** `3.74s`
- **Chart Type:** `bar`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `chart`
- **Evaluation Intent:** *Average days past due by branch location*

#### Application Response Output:
```text
HEADLINE: Average DPD by branch (As at 24 Aug 2026)
SUMMARY / ANSWER:
Head Office — Credit Division is the only branch returned, with average dpd of 0 as at 24 Aug 2026. This measures mean days past due across classified accounts at the snapshot, grouped by branch.

CHART SPEC: Type=bar, Title=Average DPD by branch (As at 24 Aug 2026)
COLUMNS: Branch, Average DPD
SAMPLE ROWS (1 total): [{"branch": "Head Office — Credit Division", "avg_dpd": 0.13648005854372486, "branch__raw": 4.0}]

GOVERNED SQL QUERY:
SELECT lam."branch_code" AS branch,
       (COALESCE(SUM(portfolio.dpd_days), 0) / NULLIF(COUNT(*), 0)) AS avg_dpd
FROM gold.portfolio_snapshot_as_of(DATE '2026-08-24') AS portfolio
     JOIN gold.loan_account_master AS lam ON portfolio."entity_num" = lam."entity_num" AND portfolio."loan_account_number" = lam."loan_account_number"
GROUP BY lam."branch_code"
ORDER BY (COALESCE(SUM(portfolio.dpd_days), 0) / NULLIF(COUNT(*), 0)) DESC NULLS LAST
LIMIT 200
```

---

### Q101: Show average DPD by product type.

- **Domain:** `Loan Book` — *Delinquency & PAR*
- **Status:** 🟢 **Answered**
- **Latency:** `5.20s`
- **Chart Type:** `bar`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `chart`
- **Evaluation Intent:** *Average days past due by product line*

#### Application Response Output:
```text
HEADLINE: Average DPD by product (As at 24 Aug 2026)
SUMMARY / ANSWER:
Business & MSME Loans is the only product returned, with average dpd of 0 as at 24 Aug 2026. This measures mean days past due across classified accounts at the snapshot, grouped by product.

CHART SPEC: Type=bar, Title=Average DPD by product (As at 24 Aug 2026)
COLUMNS: Product, Average DPD
SAMPLE ROWS (1 total): [{"product": "Business & MSME Loans", "avg_dpd": 0.13648005854372486, "product__raw": 16.0}]

GOVERNED SQL QUERY:
SELECT lam."product_code" AS product,
       (COALESCE(SUM(portfolio.dpd_days), 0) / NULLIF(COUNT(*), 0)) AS avg_dpd
FROM gold.portfolio_snapshot_as_of(DATE '2026-08-24') AS portfolio
     JOIN gold.loan_account_master AS lam ON portfolio."entity_num" = lam."entity_num" AND portfolio."loan_account_number" = lam."loan_account_number"
GROUP BY lam."product_code"
ORDER BY (COALESCE(SUM(portfolio.dpd_days), 0) / NULLIF(COUNT(*), 0)) DESC NULLS LAST
LIMIT 200
```

---

### Q102: Break down the overdue principal amount by branch.

- **Domain:** `Loan Book` — *Delinquency & PAR*
- **Status:** 🟢 **Answered**
- **Latency:** `3.81s`
- **Chart Type:** `bar`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `chart`
- **Evaluation Intent:** *Branch-level delinquent principal amounts*

#### Application Response Output:
```text
HEADLINE: Overdue principal by branch (As at 24 Aug 2026)
SUMMARY / ANSWER:
Head Office — Credit Division is the only branch returned, with overdue principal of ₹19.57 L as at 24 Aug 2026. This measures principal overdue at the requested portfolio snapshot, grouped by branch.

CHART SPEC: Type=bar, Title=Overdue principal by branch (As at 24 Aug 2026)
COLUMNS: Branch, Overdue principal
SAMPLE ROWS (1 total): [{"branch": "Head Office — Credit Division", "overdue_principal": 1957196.06, "branch__raw": 4.0}]

GOVERNED SQL QUERY:
SELECT lam."branch_code" AS branch,
       SUM(portfolio.principal_overdue) AS overdue_principal
FROM gold.portfolio_snapshot_as_of(DATE '2026-08-24') AS portfolio
     JOIN gold.loan_account_master AS lam ON portfolio."entity_num" = lam."entity_num" AND portfolio."loan_account_number" = lam."loan_account_number"
GROUP BY lam."branch_code"
ORDER BY SUM(portfolio.principal_overdue) DESC NULLS LAST
LIMIT 200
```

---

### Q103: Break down overdue principal amount by product type.

- **Domain:** `Loan Book` — *Delinquency & PAR*
- **Status:** 🟢 **Answered**
- **Latency:** `5.77s`
- **Chart Type:** `bar`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `chart`
- **Evaluation Intent:** *Product-level delinquent principal amounts*

#### Application Response Output:
```text
HEADLINE: Overdue principal by product (As at 24 Aug 2026)
SUMMARY / ANSWER:
Business & MSME Loans is the only product returned, with overdue principal of ₹19.57 L as at 24 Aug 2026. This measures principal overdue at the requested portfolio snapshot, grouped by product.

CHART SPEC: Type=bar, Title=Overdue principal by product (As at 24 Aug 2026)
COLUMNS: Product, Overdue principal
SAMPLE ROWS (1 total): [{"product": "Business & MSME Loans", "overdue_principal": 1957196.06, "product__raw": 16.0}]

GOVERNED SQL QUERY:
SELECT lam."product_code" AS product,
       SUM(portfolio.principal_overdue) AS overdue_principal
FROM gold.portfolio_snapshot_as_of(DATE '2026-08-24') AS portfolio
     JOIN gold.loan_account_master AS lam ON portfolio."entity_num" = lam."entity_num" AND portfolio."loan_account_number" = lam."loan_account_number"
GROUP BY lam."product_code"
ORDER BY SUM(portfolio.principal_overdue) DESC NULLS LAST
LIMIT 200
```

---

### Q104: Show total overdue amount by DPD bucket.

- **Domain:** `Loan Book` — *Delinquency & PAR*
- **Status:** 🟢 **Answered**
- **Latency:** `4.82s`
- **Chart Type:** `bar`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `chart`
- **Evaluation Intent:** *Total arrears (principal + interest) across DPD bands*

#### Application Response Output:
```text
HEADLINE: Total overdue by dpd bucket (As at 24 Aug 2026)
SUMMARY / ANSWER:
1-30 has the highest total overdue, at ₹31.89 L as at 24 Aug 2026, 92% of the total across 5 dpd buckets. This measures principal, interest, charges and penal overdue at the requested snapshot, grouped by dpd bucket.

CHART SPEC: Type=bar, Title=Total overdue by dpd bucket (As at 24 Aug 2026)
COLUMNS: DPD bucket, Total overdue
SAMPLE ROWS (5 total): [{"dpd_bucket": "1-30", "overdue_total": 3188956.32, "dpd_bucket__raw": "1-30"}, {"dpd_bucket": "31-60", "overdue_total": 242760.8, "dpd_bucket__raw": "31-60"}, {"dpd_bucket": "90+", "overdue_total": 37279.3, "dpd_bucket__raw": "90+"}]

GOVERNED SQL QUERY:
SELECT CASE WHEN portfolio."dpd_days" = 0 THEN '0 (current)' WHEN portfolio."dpd_days" BETWEEN 1 AND 30 THEN '1-30' WHEN portfolio."dpd_days" BETWEEN 31 AND 60 THEN '31-60' WHEN portfolio."dpd_days" BETWEEN 61 AND 90 THEN '61-90' ELSE '90+' END AS dpd_bucket,
       SUM(portfolio.total_overdue) AS overdue_total
FROM gold.portfolio_snapshot_as_of(DATE '2026-08-24') AS portfolio
GROUP BY CASE WHEN portfolio."dpd_days" = 0 THEN '0 (current)' WHEN portfolio."dpd_days" BETWEEN 1 AND 30 THEN '1-30' WHEN portfolio."dpd_days" BETWEEN 31 AND 60 THEN '31-60' WHEN portfolio."dpd_days" BETWEEN 61 AND 90 THEN '61-90' ELSE '90+' END, CASE WHEN portfolio."dpd_days" = 0 THEN 0 WHEN portfolio."dpd_days" <= 30 THEN 1 WHEN portfolio."dpd_days" <= 60 THEN 2 WHEN portfolio."dpd_days" <= 90 THEN 3 ELSE 4 END
ORDER BY SUM(portfolio.total_overdue) DESC NULLS LAST
LIMIT 200
```

---

### Q105: What is the total principal outstanding in the 1-30 DPD bucket?

- **Domain:** `Loan Book` — *Delinquency & PAR*
- **Status:** 🟢 **Answered**
- **Latency:** `60.07s`
- **Chart Type:** `kpi`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `chart`
- **Evaluation Intent:** *Principal outstanding in 1-30 DPD early stress bucket*

#### Application Response Output:
```text
HEADLINE: What is the total principal outstanding in the 1-30 DPD bucket (Generated query — not a reviewed metric)
SUMMARY / ANSWER:
Total Principal Outstanding was ₹9.56 Cr. Sum of principal outstanding for accounts with 1 to 30 days past due. This uses a validated read-only generated query rather than a reviewed metric; check Source details before relying on it.

CHART SPEC: Type=kpi, Title=What is the total principal outstanding in the 1-30 DPD bucket (Generated query — not a reviewed metric)
COLUMNS: Total Principal Outstanding
SAMPLE ROWS (1 total): [{"total_principal_outstanding": 95603973.38}]

GOVERNED SQL QUERY:
SELECT
  SUM(principal_outstanding) AS total_principal_outstanding
FROM gold.portfolio_daily_snapshot
WHERE
  dpd_days BETWEEN 1 AND 30
LIMIT 5000
```

---

### Q106: What is the total principal outstanding in the 31-60 DPD bucket?

- **Domain:** `Loan Book` — *Delinquency & PAR*
- **Status:** 🔴 **Error**
- **Latency:** `90.44s`
- **Chart Type:** `N/A`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `error`
- **Evaluation Intent:** *Principal outstanding in 31-60 DPD SMA-1 bucket*

#### Application Response Output:
```text
ERROR DETAIL: No intelligence source produced a usable answer.
```

---

### Q107: What is the total principal outstanding in the 61-90 DPD bucket?

- **Domain:** `Loan Book` — *Delinquency & PAR*
- **Status:** 🔴 **Error**
- **Latency:** `90.56s`
- **Chart Type:** `N/A`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `error`
- **Evaluation Intent:** *Principal outstanding in 61-90 DPD SMA-2 bucket*

#### Application Response Output:
```text
ERROR DETAIL: No intelligence source produced a usable answer.
```

---

### Q108: What is the total principal outstanding in the 90+ DPD bucket?

- **Domain:** `Loan Book` — *Delinquency & PAR*
- **Status:** 🔴 **Error**
- **Latency:** `90.59s`
- **Chart Type:** `N/A`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `error`
- **Evaluation Intent:** *Principal outstanding in 90+ DPD default bucket*

#### Application Response Output:
```text
ERROR DETAIL: No intelligence source produced a usable answer.
```

---

### Q109: Show delinquent account count by branch.

- **Domain:** `Loan Book` — *Delinquency & PAR*
- **Status:** 🟢 **Answered**
- **Latency:** `46.17s`
- **Chart Type:** `bar`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `chart`
- **Evaluation Intent:** *Count of accounts with arrears by branch*

#### Application Response Output:
```text
HEADLINE: Delinquent accounts by branch (As at 24 Aug 2026)
SUMMARY / ANSWER:
Head Office — Credit Division is the only branch returned, with 273 delinquent accounts as at 24 Aug 2026. This measures count of classified accounts with DPD greater than zero, grouped by branch.

CHART SPEC: Type=bar, Title=Delinquent accounts by branch (As at 24 Aug 2026)
COLUMNS: Branch, Delinquent accounts
SAMPLE ROWS (1 total): [{"branch": "Head Office — Credit Division", "delinquent_account_count": 273, "branch__raw": 4.0}]

GOVERNED SQL QUERY:
SELECT lam."branch_code" AS branch,
       COUNT(*) FILTER (WHERE portfolio.is_delinquent) AS delinquent_account_count
FROM gold.portfolio_snapshot_as_of(DATE '2026-08-24') AS portfolio
     JOIN gold.loan_account_master AS lam ON portfolio."entity_num" = lam."entity_num" AND portfolio."loan_account_number" = lam."loan_account_number"
GROUP BY lam."branch_code"
ORDER BY COUNT(*) FILTER (WHERE portfolio.is_delinquent) DESC NULLS LAST
LIMIT 200
```

---

### Q110: Show delinquent account count by scheme.

- **Domain:** `Loan Book` — *Delinquency & PAR*
- **Status:** 🟢 **Answered**
- **Latency:** `3.88s`
- **Chart Type:** `bar`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `chart`
- **Evaluation Intent:** *Count of delinquent accounts by loan scheme*

#### Application Response Output:
```text
HEADLINE: Delinquent accounts by scheme (As at 24 Aug 2026)
SUMMARY / ANSWER:
MSME Loans has the highest delinquent accounts, at 80 as at 24 Aug 2026, 29% of the total across 8 schemes. This measures count of classified accounts with DPD greater than zero, grouped by scheme.

CHART SPEC: Type=bar, Title=Delinquent accounts by scheme (As at 24 Aug 2026)
COLUMNS: Scheme, Delinquent accounts
SAMPLE ROWS (8 total): [{"scheme": "MSME Loans", "delinquent_account_count": 80, "scheme__raw": "1616"}, {"scheme": "Personal Loan", "delinquent_account_count": 69, "scheme__raw": "1617"}, {"scheme": "Site / Housing Construction / House Repair", "delinquent_account_count": 62, "scheme__raw": "1618"}]

GOVERNED SQL QUERY:
SELECT lam."scheme_code" AS scheme,
       COUNT(*) FILTER (WHERE portfolio.is_delinquent) AS delinquent_account_count
FROM gold.portfolio_snapshot_as_of(DATE '2026-08-24') AS portfolio
     JOIN gold.loan_account_master AS lam ON portfolio."entity_num" = lam."entity_num" AND portfolio."loan_account_number" = lam."loan_account_number"
GROUP BY lam."scheme_code"
ORDER BY COUNT(*) FILTER (WHERE portfolio.is_delinquent) DESC NULLS LAST
LIMIT 200
```

---

### Q111: What is the NPA ratio right now?

- **Domain:** `Loan Book` — *Asset Quality & NPA*
- **Status:** 🟢 **Answered**
- **Latency:** `3.52s`
- **Chart Type:** `kpi`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `chart`
- **Evaluation Intent:** *Current Gross NPA percentage across classified accounts*

#### Application Response Output:
```text
HEADLINE: NPA ratio (As at 24 Aug 2026)
SUMMARY / ANSWER:
NPA ratio was 0.02% as at 24 Aug 2026. This measures nPA-classified principal outstanding divided by classified principal outstanding. Definition of NPA ratio is pending client sign-off.

CHART SPEC: Type=kpi, Title=NPA ratio (As at 24 Aug 2026)
COLUMNS: NPA ratio
SAMPLE ROWS (1 total): [{"npa_ratio": 0.02008484359049893}]

GOVERNED SQL QUERY:
SELECT (100.0 * COALESCE(SUM(portfolio.principal_outstanding) FILTER (WHERE portfolio.is_npa), 0) / NULLIF(SUM(portfolio.principal_outstanding), 0)) AS npa_ratio
FROM gold.portfolio_snapshot_as_of(DATE '2026-08-24') AS portfolio
LIMIT 200
```

---

### Q112: What is the total principal outstanding classified as NPA?

- **Domain:** `Loan Book` — *Asset Quality & NPA*
- **Status:** 🟢 **Answered**
- **Latency:** `52.39s`
- **Chart Type:** `kpi`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `chart`
- **Evaluation Intent:** *Total principal balance on NPA classified accounts*

#### Application Response Output:
```text
HEADLINE: What is the total principal outstanding classified as NPA (Generated query — not a reviewed metric)
SUMMARY / ANSWER:
Total Npa Principal was ₹4.11 L. Sum of principal outstanding for accounts classified as NPA. This uses a validated read-only generated query rather than a reviewed metric; check Source details before relying on it.

CHART SPEC: Type=kpi, Title=What is the total principal outstanding classified as NPA (Generated query — not a reviewed metric)
COLUMNS: Total Npa Principal
SAMPLE ROWS (1 total): [{"total_npa_principal": 410814.29}]

GOVERNED SQL QUERY:
SELECT
  SUM(principal_outstanding) AS total_npa_principal
FROM gold.portfolio_daily_snapshot
WHERE
  is_npa = TRUE
LIMIT 5000
```

---

### Q113: Show NPA ratio by branch.

- **Domain:** `Loan Book` — *Asset Quality & NPA*
- **Status:** 🟢 **Answered**
- **Latency:** `40.82s`
- **Chart Type:** `bar`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `chart`
- **Evaluation Intent:** *Branch-level gross NPA percentage comparison*

#### Application Response Output:
```text
HEADLINE: NPA ratio by branch (As at 24 Aug 2026)
SUMMARY / ANSWER:
Head Office — Credit Division is the only branch returned, with npa ratio of 0.02% as at 24 Aug 2026. This measures nPA-classified principal outstanding divided by classified principal outstanding, grouped by branch. Definition of NPA ratio is pending client sign-off.

CHART SPEC: Type=bar, Title=NPA ratio by branch (As at 24 Aug 2026)
COLUMNS: Branch, NPA ratio
SAMPLE ROWS (1 total): [{"branch": "Head Office — Credit Division", "npa_ratio": 0.02008484359049893, "branch__raw": 4.0}]

GOVERNED SQL QUERY:
SELECT lam."branch_code" AS branch,
       (100.0 * COALESCE(SUM(portfolio.principal_outstanding) FILTER (WHERE portfolio.is_npa), 0) / NULLIF(SUM(portfolio.principal_outstanding), 0)) AS npa_ratio
FROM gold.portfolio_snapshot_as_of(DATE '2026-08-24') AS portfolio
     JOIN gold.loan_account_master AS lam ON portfolio."entity_num" = lam."entity_num" AND portfolio."loan_account_number" = lam."loan_account_number"
GROUP BY lam."branch_code"
ORDER BY (100.0 * COALESCE(SUM(portfolio.principal_outstanding) FILTER (WHERE portfolio.is_npa), 0) / NULLIF(SUM(portfolio.principal_outstanding), 0)) DESC NULLS LAST
LIMIT 200
```

---

### Q114: Show NPA ratio by product type.

- **Domain:** `Loan Book` — *Asset Quality & NPA*
- **Status:** 🟢 **Answered**
- **Latency:** `4.53s`
- **Chart Type:** `bar`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `chart`
- **Evaluation Intent:** *Gross NPA ratio across Gold, Microfinance, and MSME products*

#### Application Response Output:
```text
HEADLINE: NPA ratio by product (As at 24 Aug 2026)
SUMMARY / ANSWER:
Business & MSME Loans is the only product returned, with npa ratio of 0.02% as at 24 Aug 2026. This measures nPA-classified principal outstanding divided by classified principal outstanding, grouped by product. Definition of NPA ratio is pending client sign-off.

CHART SPEC: Type=bar, Title=NPA ratio by product (As at 24 Aug 2026)
COLUMNS: Product, NPA ratio
SAMPLE ROWS (1 total): [{"product": "Business & MSME Loans", "npa_ratio": 0.02008484359049893, "product__raw": 16.0}]

GOVERNED SQL QUERY:
SELECT lam."product_code" AS product,
       (100.0 * COALESCE(SUM(portfolio.principal_outstanding) FILTER (WHERE portfolio.is_npa), 0) / NULLIF(SUM(portfolio.principal_outstanding), 0)) AS npa_ratio
FROM gold.portfolio_snapshot_as_of(DATE '2026-08-24') AS portfolio
     JOIN gold.loan_account_master AS lam ON portfolio."entity_num" = lam."entity_num" AND portfolio."loan_account_number" = lam."loan_account_number"
GROUP BY lam."product_code"
ORDER BY (100.0 * COALESCE(SUM(portfolio.principal_outstanding) FILTER (WHERE portfolio.is_npa), 0) / NULLIF(SUM(portfolio.principal_outstanding), 0)) DESC NULLS LAST
LIMIT 200
```

---

### Q115: Show NPA ratio by scheme.

- **Domain:** `Loan Book` — *Asset Quality & NPA*
- **Status:** 🟢 **Answered**
- **Latency:** `3.71s`
- **Chart Type:** `bar`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `chart`
- **Evaluation Intent:** *Gross NPA ratio across individual loan schemes*

#### Application Response Output:
```text
HEADLINE: NPA ratio by scheme (As at 24 Aug 2026)
SUMMARY / ANSWER:
Site / Housing Construction / House Repair has the highest npa ratio, at 0.10% as at 24 Aug 2026. This measures nPA-classified principal outstanding divided by classified principal outstanding, grouped by scheme. Definition of NPA ratio is pending client sign-off.

CHART SPEC: Type=bar, Title=NPA ratio by scheme (As at 24 Aug 2026)
COLUMNS: Scheme, NPA ratio
SAMPLE ROWS (8 total): [{"scheme": "Site / Housing Construction / House Repair", "npa_ratio": 0.09838114631780845, "scheme__raw": "1618"}, {"scheme": "MSME Loans", "npa_ratio": 0.0, "scheme__raw": "1616"}, {"scheme": "Personal Loan", "npa_ratio": 0.0, "scheme__raw": "1617"}]

GOVERNED SQL QUERY:
SELECT lam."scheme_code" AS scheme,
       (100.0 * COALESCE(SUM(portfolio.principal_outstanding) FILTER (WHERE portfolio.is_npa), 0) / NULLIF(SUM(portfolio.principal_outstanding), 0)) AS npa_ratio
FROM gold.portfolio_snapshot_as_of(DATE '2026-08-24') AS portfolio
     JOIN gold.loan_account_master AS lam ON portfolio."entity_num" = lam."entity_num" AND portfolio."loan_account_number" = lam."loan_account_number"
GROUP BY lam."scheme_code"
ORDER BY (100.0 * COALESCE(SUM(portfolio.principal_outstanding) FILTER (WHERE portfolio.is_npa), 0) / NULLIF(SUM(portfolio.principal_outstanding), 0)) DESC NULLS LAST
LIMIT 200
```

---

### Q116: Show the distribution of active loan accounts by asset classification.

- **Domain:** `Loan Book` — *Asset Quality & NPA*
- **Status:** 🟢 **Answered**
- **Latency:** `6.61s`
- **Chart Type:** `donut`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `chart`
- **Evaluation Intent:** *Count of loan accounts in STD, SMA0, SMA1, SMA2, and NPA*

#### Application Response Output:
```text
HEADLINE: Principal outstanding by asset classification (As at 24 Aug 2026)
SUMMARY / ANSWER:
Standard has the highest principal outstanding, at ₹194.43 Cr as at 24 Aug 2026, 95% of the total across 5 asset classifications. This measures principal outstanding from each classified account at the requested snapshot, grouped by asset classification.

CHART SPEC: Type=donut, Title=Principal outstanding by asset classification (As at 24 Aug 2026)
COLUMNS: Asset classification, Principal outstanding
SAMPLE ROWS (5 total): [{"asset_class": "Standard", "principal_outstanding": 1944297584.74, "asset_class__raw": "STD"}, {"asset_class": "SMA-0", "principal_outstanding": 95603973.38, "asset_class__raw": "SMA0"}, {"asset_class": "SMA-1", "principal_outstanding": 4895028.14, "asset_class__raw": "SMA1"}]

GOVERNED SQL QUERY:
SELECT portfolio."asset_code" AS asset_class,
       SUM(portfolio.principal_outstanding) AS principal_outstanding
FROM gold.portfolio_snapshot_as_of(DATE '2026-08-24') AS portfolio
GROUP BY portfolio."asset_code"
ORDER BY SUM(portfolio.principal_outstanding) DESC NULLS LAST
LIMIT 200
```

---

### Q117: Show principal outstanding by RBI asset classification.

- **Domain:** `Loan Book` — *Asset Quality & NPA*
- **Status:** 🟢 **Answered**
- **Latency:** `5.29s`
- **Chart Type:** `bar`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `chart`
- **Evaluation Intent:** *Principal outstanding in Standard vs Special Mention vs NPA categories*

#### Application Response Output:
```text
HEADLINE: Principal outstanding by asset classification (As at 24 Aug 2026)
SUMMARY / ANSWER:
Standard has the highest principal outstanding, at ₹194.43 Cr as at 24 Aug 2026, 95% of the total across 5 asset classifications. This measures principal outstanding from each classified account at the requested snapshot, grouped by asset classification.

CHART SPEC: Type=bar, Title=Principal outstanding by asset classification (As at 24 Aug 2026)
COLUMNS: Asset classification, Principal outstanding
SAMPLE ROWS (5 total): [{"asset_class": "Standard", "principal_outstanding": 1944297584.74, "asset_class__raw": "STD"}, {"asset_class": "SMA-0", "principal_outstanding": 95603973.38, "asset_class__raw": "SMA0"}, {"asset_class": "SMA-1", "principal_outstanding": 4895028.14, "asset_class__raw": "SMA1"}]

GOVERNED SQL QUERY:
SELECT portfolio."asset_code" AS asset_class,
       SUM(portfolio.principal_outstanding) AS principal_outstanding
FROM gold.portfolio_snapshot_as_of(DATE '2026-08-24') AS portfolio
GROUP BY portfolio."asset_code"
ORDER BY SUM(portfolio.principal_outstanding) DESC NULLS LAST
LIMIT 200
```

---

### Q118: What is the total principal outstanding in Standard assets?

- **Domain:** `Loan Book` — *Asset Quality & NPA*
- **Status:** 🟢 **Answered**
- **Latency:** `55.60s`
- **Chart Type:** `kpi`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `chart`
- **Evaluation Intent:** *Principal outstanding in Standard (performing) credit category*

#### Application Response Output:
```text
HEADLINE: What is the total principal outstanding in Standard assets (Generated query — not a reviewed metric)
SUMMARY / ANSWER:
Total Principal Outstanding was ₹194.43 Cr. Sum of principal outstanding for accounts classified as Standard (STD). This uses a validated read-only generated query rather than a reviewed metric; check Source details before relying on it.

CHART SPEC: Type=kpi, Title=What is the total principal outstanding in Standard assets (Generated query — not a reviewed metric)
COLUMNS: Total Principal Outstanding
SAMPLE ROWS (1 total): [{"total_principal_outstanding": 1944297584.74}]

GOVERNED SQL QUERY:
SELECT
  SUM(principal_outstanding) AS total_principal_outstanding
FROM gold.portfolio_daily_snapshot
WHERE
  asset_code = 'STD'
LIMIT 5000
```

---

### Q119: What is the total principal outstanding in SMA-0 assets?

- **Domain:** `Loan Book` — *Asset Quality & NPA*
- **Status:** 🔴 **Error**
- **Latency:** `90.59s`
- **Chart Type:** `N/A`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `error`
- **Evaluation Intent:** *Principal outstanding in SMA-0 early stress category*

#### Application Response Output:
```text
ERROR DETAIL: No intelligence source produced a usable answer.
```

---

### Q120: What is the total principal outstanding in SMA-1 assets?

- **Domain:** `Loan Book` — *Asset Quality & NPA*
- **Status:** 🟢 **Answered**
- **Latency:** `59.26s`
- **Chart Type:** `kpi`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `chart`
- **Evaluation Intent:** *Principal outstanding in SMA-1 (31-60 DPD) category*

#### Application Response Output:
```text
HEADLINE: What is the total principal outstanding in SMA-1 assets (Generated query — not a reviewed metric)
SUMMARY / ANSWER:
Total Sma1 Outstanding was ₹48.95 L. Sum of principal outstanding for accounts classified as SMA-1. This uses a validated read-only generated query rather than a reviewed metric; check Source details before relying on it.

CHART SPEC: Type=kpi, Title=What is the total principal outstanding in SMA-1 assets (Generated query — not a reviewed metric)
COLUMNS: Total Sma1 Outstanding
SAMPLE ROWS (1 total): [{"total_sma1_outstanding": 4895028.14}]

GOVERNED SQL QUERY:
SELECT
  SUM(principal_outstanding) AS total_sma1_outstanding
FROM gold.portfolio_daily_snapshot
WHERE
  asset_code = 'SMA1'
LIMIT 5000
```

---

### Q121: What is the total principal outstanding in SMA-2 assets?

- **Domain:** `Loan Book` — *Asset Quality & NPA*
- **Status:** 🔴 **Error**
- **Latency:** `90.87s`
- **Chart Type:** `N/A`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `error`
- **Evaluation Intent:** *Principal outstanding in SMA-2 (61-90 DPD) category*

#### Application Response Output:
```text
ERROR DETAIL: No intelligence source produced a usable answer.
```

---

### Q122: How many loan accounts are classified as Standard?

- **Domain:** `Loan Book` — *Asset Quality & NPA*
- **Status:** 🔴 **Error**
- **Latency:** `90.93s`
- **Chart Type:** `N/A`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `error`
- **Evaluation Intent:** *Count of accounts in Standard asset class*

#### Application Response Output:
```text
ERROR DETAIL: No intelligence source produced a usable answer.
```

---

### Q123: How many loan accounts are classified as SMA-0?

- **Domain:** `Loan Book` — *Asset Quality & NPA*
- **Status:** 🔴 **Error**
- **Latency:** `90.67s`
- **Chart Type:** `N/A`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `error`
- **Evaluation Intent:** *Count of accounts in SMA-0 asset class*

#### Application Response Output:
```text
ERROR DETAIL: No intelligence source produced a usable answer.
```

---

### Q124: How many loan accounts are classified as SMA-1?

- **Domain:** `Loan Book` — *Asset Quality & NPA*
- **Status:** 🔴 **Error**
- **Latency:** `90.58s`
- **Chart Type:** `N/A`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `error`
- **Evaluation Intent:** *Count of accounts in SMA-1 asset class*

#### Application Response Output:
```text
ERROR DETAIL: No intelligence source produced a usable answer.
```

---

### Q125: How many loan accounts are classified as SMA-2?

- **Domain:** `Loan Book` — *Asset Quality & NPA*
- **Status:** 🟡 **Refused**
- **Latency:** `60.79s`
- **Chart Type:** `N/A`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `refusal`
- **Evaluation Intent:** *Count of accounts in SMA-2 asset class*

#### Application Response Output:
```text
SUMMARY / ANSWER:
I could not answer that safely from the available data.
```

---

### Q126: How many loan accounts are classified as NPA?

- **Domain:** `Loan Book` — *Asset Quality & NPA*
- **Status:** 🔴 **Error**
- **Latency:** `90.62s`
- **Chart Type:** `N/A`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `error`
- **Evaluation Intent:** *Count of accounts in Non-Performing Asset category*

#### Application Response Output:
```text
ERROR DETAIL: No intelligence source produced a usable answer.
```

---

### Q127: What is the total overdue amount on NPA accounts?

- **Domain:** `Loan Book` — *Asset Quality & NPA*
- **Status:** 🟢 **Answered**
- **Latency:** `90.22s`
- **Chart Type:** `kpi`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `chart`
- **Evaluation Intent:** *Arrears and overdue balance sitting on bad loans*

#### Application Response Output:
```text
HEADLINE: What is the total overdue amount on NPA accounts (Generated query — not a reviewed metric)
SUMMARY / ANSWER:
Total Overdue Npa was ₹37,279. Sum of all overdue components (principal, interest, charges, penal) for accounts classified as NPA. This uses a validated read-only generated query rather than a reviewed metric; check Source details before relying on it.

CHART SPEC: Type=kpi, Title=What is the total overdue amount on NPA accounts (Generated query — not a reviewed metric)
COLUMNS: Total Overdue Npa
SAMPLE ROWS (1 total): [{"total_overdue_npa": 37279.3}]

GOVERNED SQL QUERY:
SELECT
  SUM(principal_overdue + interest_overdue + charges_overdue + penal_overdue) AS total_overdue_npa
FROM gold.portfolio_daily_snapshot
WHERE
  is_npa = TRUE
LIMIT 5000
```

---

### Q128: Show asset classification breakdown for Business & MSME loans.

- **Domain:** `Loan Book` — *Asset Quality & NPA*
- **Status:** 🔴 **Error**
- **Latency:** `90.64s`
- **Chart Type:** `N/A`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `error`
- **Evaluation Intent:** *Asset class distribution in Product Code 16*

#### Application Response Output:
```text
ERROR DETAIL: No intelligence source produced a usable answer.
```

---

### Q129: Show asset classification breakdown for Gold Loans.

- **Domain:** `Loan Book` — *Asset Quality & NPA*
- **Status:** 🔴 **Error**
- **Latency:** `90.66s`
- **Chart Type:** `N/A`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `error`
- **Evaluation Intent:** *Asset class distribution in Product Code 1*

#### Application Response Output:
```text
ERROR DETAIL: No intelligence source produced a usable answer.
```

---

### Q130: Show asset classification breakdown in Head Office Credit Division.

- **Domain:** `Loan Book` — *Asset Quality & NPA*
- **Status:** 🔴 **Error**
- **Latency:** `90.57s`
- **Chart Type:** `N/A`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `error`
- **Evaluation Intent:** *Asset class distribution in branch 4*

#### Application Response Output:
```text
ERROR DETAIL: No intelligence source produced a usable answer.
```

---

### Q131: Top 10 schemes by sanctioned amount.

- **Domain:** `Loan Book` — *Schemes & Products*
- **Status:** 🟢 **Answered**
- **Latency:** `42.19s`
- **Chart Type:** `bar`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `chart`
- **Evaluation Intent:** *Ranking top 10 schemes by cumulative sanctioned amount*

#### Application Response Output:
```text
HEADLINE: Sanctioned amount by scheme (all time)
SUMMARY / ANSWER:
MSME Loans has the highest sanctioned amount, at ₹65.47 Cr in all time, 29% of the total across 10 schemes. This measures sum of sanctioned amounts for accounts sanctioned in the period, grouped by scheme.

CHART SPEC: Type=bar, Title=Sanctioned amount by scheme (all time)
COLUMNS: Scheme, Sanctioned amount
SAMPLE ROWS (10 total): [{"scheme": "MSME Loans", "sanctioned_amount": 654710000.0, "scheme__raw": "1616"}, {"scheme": "Site / Housing Construction / House Repair", "sanctioned_amount": 457645000.0, "scheme__raw": "1618"}, {"scheme": "Personal Loan", "sanctioned_amount": 439308000.0, "scheme__raw": "1617"}]

GOVERNED SQL QUERY:
SELECT lam."scheme_code" AS scheme,
       SUM(lam.sanction_amount) AS sanctioned_amount
FROM gold.loan_account_master AS lam
WHERE lam."sanction_date" BETWEEN DATE '2000-01-01' AND DATE '2026-08-24'
GROUP BY lam."scheme_code"
ORDER BY SUM(lam.sanction_amount) DESC NULLS LAST
LIMIT 10
```

---

### Q132: Which schemes have the largest outstanding balance?

- **Domain:** `Loan Book` — *Schemes & Products*
- **Status:** 🟢 **Answered**
- **Latency:** `4.74s`
- **Chart Type:** `bar`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `chart`
- **Evaluation Intent:** *Ranking schemes by current principal outstanding balance*

#### Application Response Output:
```text
HEADLINE: Principal outstanding by scheme (As at 24 Aug 2026)
SUMMARY / ANSWER:
MSME Loans has the highest principal outstanding, at ₹59.81 Cr as at 24 Aug 2026, 29% of the total across 8 schemes. This measures principal outstanding from each classified account at the requested snapshot, grouped by scheme.

CHART SPEC: Type=bar, Title=Principal outstanding by scheme (As at 24 Aug 2026)
COLUMNS: Scheme, Principal outstanding
SAMPLE ROWS (8 total): [{"scheme": "MSME Loans", "principal_outstanding": 598093032.27, "scheme__raw": "1616"}, {"scheme": "Site / Housing Construction / House Repair", "principal_outstanding": 417574205.4, "scheme__raw": "1618"}, {"scheme": "Personal Loan", "principal_outstanding": 406744496.01, "scheme__raw": "1617"}]

GOVERNED SQL QUERY:
SELECT lam."scheme_code" AS scheme,
       SUM(portfolio.principal_outstanding) AS principal_outstanding
FROM gold.portfolio_snapshot_as_of(DATE '2026-08-24') AS portfolio
     JOIN gold.loan_account_master AS lam ON portfolio."entity_num" = lam."entity_num" AND portfolio."loan_account_number" = lam."loan_account_number"
GROUP BY lam."scheme_code"
ORDER BY SUM(portfolio.principal_outstanding) DESC NULLS LAST
LIMIT 200
```

---

### Q133: Top 10 schemes by active loan count.

- **Domain:** `Loan Book` — *Schemes & Products*
- **Status:** 🟢 **Answered**
- **Latency:** `4.39s`
- **Chart Type:** `table`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `chart`
- **Evaluation Intent:** *Ranking schemes by total account volume*

#### Application Response Output:
```text
HEADLINE: Loans sanctioned by scheme (2026-08-24)
SUMMARY / ANSWER:
No loans sanctioned found in 2026-08-24. This measures count of loan accounts sanctioned in the period, grouped by scheme.

CHART SPEC: Type=table, Title=Loans sanctioned by scheme (2026-08-24)
COLUMNS: Scheme, Loans sanctioned

GOVERNED SQL QUERY:
SELECT lam."scheme_code" AS scheme,
       COUNT(*) AS loan_count
FROM gold.loan_account_master AS lam
WHERE lam."sanction_date" BETWEEN DATE '2026-08-24' AND DATE '2026-08-24'
GROUP BY lam."scheme_code"
ORDER BY COUNT(*) DESC NULLS LAST
LIMIT 10
```

---

### Q134: What is the total sanctioned amount in Standard Retail Gold Loan scheme?

- **Domain:** `Loan Book` — *Schemes & Products*
- **Status:** 🟢 **Answered**
- **Latency:** `0.87s`
- **Chart Type:** `kpi`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `chart`
- **Evaluation Intent:** *Sanction volume in Scheme 1001 (Standard Retail Gold Loan)*

#### Application Response Output:
```text
HEADLINE: Sanctioned amount (all time)
SUMMARY / ANSWER:
Sanctioned amount was ₹229.10 Cr in all time. This measures sum of sanctioned amounts for accounts sanctioned in the period.

CHART SPEC: Type=kpi, Title=Sanctioned amount (all time)
COLUMNS: Sanctioned amount
SAMPLE ROWS (1 total): [{"sanctioned_amount": 2290958902.0}]

GOVERNED SQL QUERY:
SELECT SUM(lam.sanction_amount) AS sanctioned_amount
FROM gold.loan_account_master AS lam
WHERE lam."sanction_date" BETWEEN DATE '2000-01-01' AND DATE '2026-08-24'
LIMIT 200
```

---

### Q135: What is the principal outstanding in High-Value Special Gold Loan scheme?

- **Domain:** `Loan Book` — *Schemes & Products*
- **Status:** 🟢 **Answered**
- **Latency:** `58.12s`
- **Chart Type:** `table`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `chart`
- **Evaluation Intent:** *Outstanding balance in Scheme 1005 (High-Value Special Gold Loan)*

#### Application Response Output:
```text
HEADLINE: What is the principal outstanding in High-Value Special Gold Loan scheme (Generated query — not a reviewed metric)
SUMMARY / ANSWER:
The query returned 1 row(s) covering total principal outstanding. Sum of principal outstanding for scheme 1005 as of the latest snapshot. This uses a validated read-only generated query rather than a reviewed metric; check Source details before relying on it.

CHART SPEC: Type=table, Title=What is the principal outstanding in High-Value Special Gold Loan scheme (Generated query — not a reviewed metric)
COLUMNS: Total Principal Outstanding
SAMPLE ROWS (1 total): [{"total_principal_outstanding": null}]

GOVERNED SQL QUERY:
SELECT
  SUM(principal_outstanding) AS total_principal_outstanding
FROM gold.portfolio_daily_snapshot
WHERE
  scheme_code = '1005'
  AND snapshot_date = (
    SELECT
      MAX(snapshot_date)
    FROM gold.portfolio_daily_snapshot
  )
LIMIT 1
```

---

### Q136: What is the performance and volume of FTG Patharamattu Scheme?

- **Domain:** `Loan Book` — *Schemes & Products*
- **Status:** 🔴 **Error**
- **Latency:** `90.60s`
- **Chart Type:** `N/A`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `error`
- **Evaluation Intent:** *Sanctions and outstanding in Scheme 1342 (FTG Patharamattu Scheme)*

#### Application Response Output:
```text
ERROR DETAIL: No intelligence source produced a usable answer.
```

---

### Q137: Show sanctioned amount in CCF Low ROI Scheme.

- **Domain:** `Loan Book` — *Schemes & Products*
- **Status:** 🔴 **Error**
- **Latency:** `90.45s`
- **Chart Type:** `N/A`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `error`
- **Evaluation Intent:** *Sanctions in Scheme 1352 (CCF Low ROI Scheme)*

#### Application Response Output:
```text
ERROR DETAIL: No intelligence source produced a usable answer.
```

---

### Q138: Show loan count in EV Retail Scheme.

- **Domain:** `Loan Book` — *Schemes & Products*
- **Status:** 🟡 **Clarification Needed**
- **Latency:** `46.35s`
- **Chart Type:** `N/A`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `clarify`
- **Evaluation Intent:** *Account volume in Scheme 1354 (EV Retail Scheme)*

#### Application Response Output:
```text
SUMMARY / ANSWER:
Which specific EV Retail Scheme code or name should I filter by?
```

---

### Q139: What is the total sanctioned amount in Purchase of Site scheme?

- **Domain:** `Loan Book` — *Schemes & Products*
- **Status:** 🟢 **Answered**
- **Latency:** `0.74s`
- **Chart Type:** `kpi`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `chart`
- **Evaluation Intent:** *Sanctioned amount in Scheme 1601 (Purchase of Site)*

#### Application Response Output:
```text
HEADLINE: Sanctioned amount (all time)
SUMMARY / ANSWER:
Sanctioned amount was ₹229.10 Cr in all time. This measures sum of sanctioned amounts for accounts sanctioned in the period.

CHART SPEC: Type=kpi, Title=Sanctioned amount (all time)
COLUMNS: Sanctioned amount
SAMPLE ROWS (1 total): [{"sanctioned_amount": 2290958902.0}]

GOVERNED SQL QUERY:
SELECT SUM(lam.sanction_amount) AS sanctioned_amount
FROM gold.loan_account_master AS lam
WHERE lam."sanction_date" BETWEEN DATE '2000-01-01' AND DATE '2026-08-24'
LIMIT 200
```

---

### Q140: What is the principal outstanding in Repair of House scheme?

- **Domain:** `Loan Book` — *Schemes & Products*
- **Status:** 🟢 **Answered**
- **Latency:** `61.07s`
- **Chart Type:** `table`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `chart`
- **Evaluation Intent:** *Outstanding balance in Scheme 1602 (Repair of House)*

#### Application Response Output:
```text
HEADLINE: What is the principal outstanding in Repair of House scheme (Generated query — not a reviewed metric)
SUMMARY / ANSWER:
The query returned 1 row(s) covering total principal outstanding. Sum of principal outstanding for scheme 1602 (Repair of House). This uses a validated read-only generated query rather than a reviewed metric; check Source details before relying on it.

CHART SPEC: Type=table, Title=What is the principal outstanding in Repair of House scheme (Generated query — not a reviewed metric)
COLUMNS: Total Principal Outstanding
SAMPLE ROWS (1 total): [{"total_principal_outstanding": null}]

GOVERNED SQL QUERY:
SELECT
  SUM(principal_outstanding) AS total_principal_outstanding
FROM gold.portfolio_daily_snapshot
WHERE
  scheme_code = '1602'
LIMIT 1
```

---

### Q141: Show sanctioned amount in Purchase of Two Wheelers scheme.

- **Domain:** `Loan Book` — *Schemes & Products*
- **Status:** 🔴 **Error**
- **Latency:** `90.58s`
- **Chart Type:** `N/A`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `error`
- **Evaluation Intent:** *Sanctions in Scheme 1604 (Purchase of Two Wheelers)*

#### Application Response Output:
```text
ERROR DETAIL: No intelligence source produced a usable answer.
```

---

### Q142: What is the loan volume in New Autorickshaw scheme?

- **Domain:** `Loan Book` — *Schemes & Products*
- **Status:** 🔴 **Error**
- **Latency:** `90.54s`
- **Chart Type:** `N/A`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `error`
- **Evaluation Intent:** *Sanctions in Scheme 1605 (New Autorickshaw)*

#### Application Response Output:
```text
ERROR DETAIL: No intelligence source produced a usable answer.
```

---

### Q143: Show principal outstanding in Four Wheeler Taxi / Car scheme.

- **Domain:** `Loan Book` — *Schemes & Products*
- **Status:** 🔴 **Error**
- **Latency:** `90.61s`
- **Chart Type:** `N/A`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `error`
- **Evaluation Intent:** *Outstanding balance in Scheme 1606 (Four Wheeler Taxi / Car)*

#### Application Response Output:
```text
ERROR DETAIL: No intelligence source produced a usable answer.
```

---

### Q144: What is the total sanctioned amount in Tractor loan scheme?

- **Domain:** `Loan Book` — *Schemes & Products*
- **Status:** 🟢 **Answered**
- **Latency:** `0.92s`
- **Chart Type:** `kpi`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `chart`
- **Evaluation Intent:** *Sanctions in Scheme 1607 (Tractor)*

#### Application Response Output:
```text
HEADLINE: Sanctioned amount (all time)
SUMMARY / ANSWER:
Sanctioned amount was ₹229.10 Cr in all time. This measures sum of sanctioned amounts for accounts sanctioned in the period.

CHART SPEC: Type=kpi, Title=Sanctioned amount (all time)
COLUMNS: Sanctioned amount
SAMPLE ROWS (1 total): [{"sanctioned_amount": 2290958902.0}]

GOVERNED SQL QUERY:
SELECT SUM(lam.sanction_amount) AS sanctioned_amount
FROM gold.loan_account_master AS lam
WHERE lam."sanction_date" BETWEEN DATE '2000-01-01' AND DATE '2026-08-24'
LIMIT 200
```

---

### Q145: Show loan count in New Lorry / Bus scheme.

- **Domain:** `Loan Book` — *Schemes & Products*
- **Status:** 🔴 **Error**
- **Latency:** `90.62s`
- **Chart Type:** `N/A`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `error`
- **Evaluation Intent:** *Account volume in Scheme 1608 (New Lorry / Bus)*

#### Application Response Output:
```text
ERROR DETAIL: No intelligence source produced a usable answer.
```

---

### Q146: What is the total outstanding in Used Vehicles Under 7 Years scheme?

- **Domain:** `Loan Book` — *Schemes & Products*
- **Status:** 🔴 **Error**
- **Latency:** `90.64s`
- **Chart Type:** `N/A`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `error`
- **Evaluation Intent:** *Outstanding balance in Scheme 1609 (Used Vehicles Under 7 Years)*

#### Application Response Output:
```text
ERROR DETAIL: No intelligence source produced a usable answer.
```

---

### Q147: What is the sanctioned amount in Business / Service / Industry scheme?

- **Domain:** `Loan Book` — *Schemes & Products*
- **Status:** 🔴 **Error**
- **Latency:** `90.62s`
- **Chart Type:** `N/A`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `error`
- **Evaluation Intent:** *Sanctions in Scheme 1610 (Business / Service / Industry)*

#### Application Response Output:
```text
ERROR DETAIL: No intelligence source produced a usable answer.
```

---

### Q148: What is the total sanctioned amount in Farming loan scheme?

- **Domain:** `Loan Book` — *Schemes & Products*
- **Status:** 🟢 **Answered**
- **Latency:** `0.93s`
- **Chart Type:** `kpi`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `chart`
- **Evaluation Intent:** *Sanctions in Scheme 1611 (Farming)*

#### Application Response Output:
```text
HEADLINE: Sanctioned amount (all time)
SUMMARY / ANSWER:
Sanctioned amount was ₹229.10 Cr in all time. This measures sum of sanctioned amounts for accounts sanctioned in the period.

CHART SPEC: Type=kpi, Title=Sanctioned amount (all time)
COLUMNS: Sanctioned amount
SAMPLE ROWS (1 total): [{"sanctioned_amount": 2290958902.0}]

GOVERNED SQL QUERY:
SELECT SUM(lam.sanction_amount) AS sanctioned_amount
FROM gold.loan_account_master AS lam
WHERE lam."sanction_date" BETWEEN DATE '2000-01-01' AND DATE '2026-08-24'
LIMIT 200
```

---

### Q149: Show principal outstanding in Cattle loan scheme.

- **Domain:** `Loan Book` — *Schemes & Products*
- **Status:** 🔴 **Error**
- **Latency:** `90.52s`
- **Chart Type:** `N/A`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `error`
- **Evaluation Intent:** *Outstanding balance in Scheme 1612 (Cattle)*

#### Application Response Output:
```text
ERROR DETAIL: No intelligence source produced a usable answer.
```

---

### Q150: Show loan count in Poultry / Sheep / Pigs scheme.

- **Domain:** `Loan Book` — *Schemes & Products*
- **Status:** 🟡 **Refused**
- **Latency:** `61.33s`
- **Chart Type:** `N/A`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `refusal`
- **Evaluation Intent:** *Account volume in Scheme 1613 (Poultry / Sheep / Pigs)*

#### Application Response Output:
```text
SUMMARY / ANSWER:
I could not answer that safely from the available data.
```

---

### Q151: What is the total sanctioned amount in Debt Swapping / Consolidation scheme?

- **Domain:** `Loan Book` — *Schemes & Products*
- **Status:** 🟢 **Answered**
- **Latency:** `1.23s`
- **Chart Type:** `kpi`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `chart`
- **Evaluation Intent:** *Sanctions in Scheme 1614 (Debt Swapping / Consolidation)*

#### Application Response Output:
```text
HEADLINE: Sanctioned amount (all time)
SUMMARY / ANSWER:
Sanctioned amount was ₹229.10 Cr in all time. This measures sum of sanctioned amounts for accounts sanctioned in the period.

CHART SPEC: Type=kpi, Title=Sanctioned amount (all time)
COLUMNS: Sanctioned amount
SAMPLE ROWS (1 total): [{"sanctioned_amount": 2290958902.0}]

GOVERNED SQL QUERY:
SELECT SUM(lam.sanction_amount) AS sanctioned_amount
FROM gold.loan_account_master AS lam
WHERE lam."sanction_date" BETWEEN DATE '2000-01-01' AND DATE '2026-08-24'
LIMIT 200
```

---

### Q152: What is the principal outstanding in Loan Against Property schemes?

- **Domain:** `Loan Book` — *Schemes & Products*
- **Status:** 🔴 **Error**
- **Latency:** `90.63s`
- **Chart Type:** `N/A`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `error`
- **Evaluation Intent:** *Outstanding balance in Scheme 1615 and 1619 (Loan Against Property)*

#### Application Response Output:
```text
ERROR DETAIL: No intelligence source produced a usable answer.
```

---

### Q153: What is the total sanctioned amount in MSME Loans scheme?

- **Domain:** `Loan Book` — *Schemes & Products*
- **Status:** 🟢 **Answered**
- **Latency:** `0.78s`
- **Chart Type:** `kpi`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `chart`
- **Evaluation Intent:** *Sanctions in Scheme 1616 (MSME Loans)*

#### Application Response Output:
```text
HEADLINE: Sanctioned amount (all time)
SUMMARY / ANSWER:
Sanctioned amount was ₹229.10 Cr in all time. This measures sum of sanctioned amounts for accounts sanctioned in the period.

CHART SPEC: Type=kpi, Title=Sanctioned amount (all time)
COLUMNS: Sanctioned amount
SAMPLE ROWS (1 total): [{"sanctioned_amount": 2290958902.0}]

GOVERNED SQL QUERY:
SELECT SUM(lam.sanction_amount) AS sanctioned_amount
FROM gold.loan_account_master AS lam
WHERE lam."sanction_date" BETWEEN DATE '2000-01-01' AND DATE '2026-08-24'
LIMIT 200
```

---

### Q154: Show loan count in Personal Loan scheme.

- **Domain:** `Loan Book` — *Schemes & Products*
- **Status:** 🔴 **Error**
- **Latency:** `90.76s`
- **Chart Type:** `N/A`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `error`
- **Evaluation Intent:** *Account volume in Scheme 1617 (Personal Loan)*

#### Application Response Output:
```text
ERROR DETAIL: No intelligence source produced a usable answer.
```

---

### Q155: What is the total sanctioned amount in Dairy Loan scheme?

- **Domain:** `Loan Book` — *Schemes & Products*
- **Status:** 🟢 **Answered**
- **Latency:** `0.83s`
- **Chart Type:** `kpi`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `chart`
- **Evaluation Intent:** *Sanctions in Scheme 1622 (Dairy Loan)*

#### Application Response Output:
```text
HEADLINE: Sanctioned amount (all time)
SUMMARY / ANSWER:
Sanctioned amount was ₹229.10 Cr in all time. This measures sum of sanctioned amounts for accounts sanctioned in the period.

CHART SPEC: Type=kpi, Title=Sanctioned amount (all time)
COLUMNS: Sanctioned amount
SAMPLE ROWS (1 total): [{"sanctioned_amount": 2290958902.0}]

GOVERNED SQL QUERY:
SELECT SUM(lam.sanction_amount) AS sanctioned_amount
FROM gold.loan_account_master AS lam
WHERE lam."sanction_date" BETWEEN DATE '2000-01-01' AND DATE '2026-08-24'
LIMIT 200
```

---

### Q156: List all branches ranked by total sanctioned amount.

- **Domain:** `Loan Book` — *Branch Performance*
- **Status:** 🟢 **Answered**
- **Latency:** `0.72s`
- **Chart Type:** `kpi`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `chart`
- **Evaluation Intent:** *Ranking all 16 branches by total sanctioned credit volume*

#### Application Response Output:
```text
HEADLINE: Sanctioned amount (all time)
SUMMARY / ANSWER:
Sanctioned amount was ₹229.10 Cr in all time. This measures sum of sanctioned amounts for accounts sanctioned in the period.

CHART SPEC: Type=kpi, Title=Sanctioned amount (all time)
COLUMNS: Sanctioned amount
SAMPLE ROWS (1 total): [{"sanctioned_amount": 2290958902.0}]

GOVERNED SQL QUERY:
SELECT SUM(lam.sanction_amount) AS sanctioned_amount
FROM gold.loan_account_master AS lam
WHERE lam."sanction_date" BETWEEN DATE '2000-01-01' AND DATE '2026-08-24'
LIMIT 200
```

---

### Q157: Which branches disbursed the most this financial year?

- **Domain:** `Loan Book` — *Branch Performance*
- **Status:** 🟢 **Answered**
- **Latency:** `42.38s`
- **Chart Type:** `bar`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `chart`
- **Evaluation Intent:** *Ranking branches by FYTD disbursement volume*

#### Application Response Output:
```text
HEADLINE: Disbursement by branch (FY27 to date)
SUMMARY / ANSWER:
Head Office — Credit Division is the only branch returned, with disbursement of ₹137.16 Cr in FY27 to date. This measures sum of disbursement event amounts in the period, grouped by branch.

CHART SPEC: Type=bar, Title=Disbursement by branch (FY27 to date)
COLUMNS: Branch, Disbursement
SAMPLE ROWS (1 total): [{"branch": "Head Office — Credit Division", "disbursement_total": 1371605902.0, "branch__raw": 4.0}]

GOVERNED SQL QUERY:
SELECT lam."branch_code" AS branch,
       SUM(disb.disbursement_amount) AS disbursement_total
FROM gold.loan_disbursement_events AS disb
     JOIN gold.loan_account_master AS lam ON disb."entity_num" = lam."entity_num" AND disb."loan_account_number" = lam."loan_account_number"
WHERE disb."disbursement_date" BETWEEN DATE '2026-04-01' AND DATE '2026-08-24'
GROUP BY lam."branch_code"
ORDER BY SUM(disb.disbursement_amount) DESC NULLS LAST
LIMIT 200
```

---

### Q158: List all branches by active loan account count.

- **Domain:** `Loan Book` — *Branch Performance*
- **Status:** 🟢 **Answered**
- **Latency:** `6.48s`
- **Chart Type:** `bar`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `chart`
- **Evaluation Intent:** *Branch-level distribution of active loan accounts*

#### Application Response Output:
```text
HEADLINE: Loans sanctioned by branch (all time)
SUMMARY / ANSWER:
Head Office — Credit Division has the highest loans sanctioned, at 5,746 in all time, 100% of the total across 2 branches. This measures count of loan accounts sanctioned in the period, grouped by branch.

CHART SPEC: Type=bar, Title=Loans sanctioned by branch (all time)
COLUMNS: Branch, Loans sanctioned
SAMPLE ROWS (2 total): [{"branch": "Head Office — Credit Division", "loan_count": 5746, "branch__raw": 4.0}, {"branch": "Head Office", "loan_count": 7, "branch__raw": 1.0}]

GOVERNED SQL QUERY:
SELECT lam."branch_code" AS branch,
       COUNT(*) AS loan_count
FROM gold.loan_account_master AS lam
WHERE lam."sanction_date" BETWEEN DATE '2000-01-01' AND DATE '2026-08-24'
GROUP BY lam."branch_code"
ORDER BY COUNT(*) DESC NULLS LAST
LIMIT 200
```

---

### Q159: Show average ticket size by branch.

- **Domain:** `Loan Book` — *Branch Performance*
- **Status:** 🟢 **Answered**
- **Latency:** `3.66s`
- **Chart Type:** `bar`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `chart`
- **Evaluation Intent:** *Average loan sanction ticket size by branch*

#### Application Response Output:
```text
HEADLINE: Average ticket size by branch (all time)
SUMMARY / ANSWER:
Head Office — Credit Division has the highest average ticket size, at ₹3.98 L in all time, 54% of the total across 2 branches. This measures total sanctioned amount divided by number of loans, grouped by branch.

CHART SPEC: Type=bar, Title=Average ticket size by branch (all time)
COLUMNS: Branch, Average ticket size
SAMPLE ROWS (2 total): [{"branch": "Head Office — Credit Division", "avg_ticket_size": 398287.3132613992, "branch__raw": 4.0}, {"branch": "Head Office", "avg_ticket_size": 342857.14285714284, "branch__raw": 1.0}]

GOVERNED SQL QUERY:
SELECT lam."branch_code" AS branch,
       (COALESCE(SUM(lam.sanction_amount), 0) / NULLIF(COUNT(*), 0)) AS avg_ticket_size
FROM gold.loan_account_master AS lam
WHERE lam."sanction_date" BETWEEN DATE '2000-01-01' AND DATE '2026-08-24'
GROUP BY lam."branch_code"
ORDER BY (COALESCE(SUM(lam.sanction_amount), 0) / NULLIF(COUNT(*), 0)) DESC NULLS LAST
LIMIT 200
```

---

### Q160: Show average interest rate by branch.

- **Domain:** `Loan Book` — *Branch Performance*
- **Status:** 🟢 **Answered**
- **Latency:** `3.39s`
- **Chart Type:** `bar`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `chart`
- **Evaluation Intent:** *Weighted average interest rate across branches*

#### Application Response Output:
```text
HEADLINE: Average interest rate by branch (all time)
SUMMARY / ANSWER:
Head Office — Credit Division has the highest average interest rate, at 17.7% in all time. This measures sanction-amount-weighted average account interest rate, grouped by branch. Definition of Average interest rate is pending client sign-off.

CHART SPEC: Type=bar, Title=Average interest rate by branch (all time)
COLUMNS: Branch, Average interest rate
SAMPLE ROWS (2 total): [{"branch": "Head Office — Credit Division", "avg_interest_rate": 17.734794262682254, "branch__raw": 4.0}, {"branch": "Head Office", "avg_interest_rate": 16.75, "branch__raw": 1.0}]

GOVERNED SQL QUERY:
SELECT lam."branch_code" AS branch,
       (COALESCE(SUM(lam.interest_rate * lam.sanction_amount), 0) / NULLIF(SUM(lam.sanction_amount), 0)) AS avg_interest_rate
FROM gold.loan_account_master AS lam
WHERE lam."sanction_date" BETWEEN DATE '2000-01-01' AND DATE '2026-08-24'
GROUP BY lam."branch_code"
ORDER BY (COALESCE(SUM(lam.interest_rate * lam.sanction_amount), 0) / NULLIF(SUM(lam.sanction_amount), 0)) DESC NULLS LAST
LIMIT 200
```

---

### Q161: Show total amount collected by branch this financial year.

- **Domain:** `Loan Book` — *Branch Performance*
- **Status:** 🟢 **Answered**
- **Latency:** `4.00s`
- **Chart Type:** `bar`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `chart`
- **Evaluation Intent:** *FYTD total recovery collections by branch*

#### Application Response Output:
```text
HEADLINE: Amount collected by branch (FY27 to date)
SUMMARY / ANSWER:
Head Office — Credit Division is the only branch returned, with amount collected of ₹19.17 Cr in FY27 to date. This measures principal plus interest paid in the period, grouped by branch.

CHART SPEC: Type=bar, Title=Amount collected by branch (FY27 to date)
COLUMNS: Branch, Amount collected
SAMPLE ROWS (1 total): [{"branch": "Head Office — Credit Division", "amount_collected": 191682408.46, "branch__raw": 4.0}]

GOVERNED SQL QUERY:
SELECT lam."branch_code" AS branch,
       SUM(repay.total_paid) AS amount_collected
FROM gold.loan_repayment_events AS repay
     JOIN gold.loan_account_master AS lam ON repay."entity_num" = lam."entity_num" AND repay."loan_account_number" = lam."loan_account_number"
WHERE repay."repayment_date" BETWEEN DATE '2026-04-01' AND DATE '2026-08-24'
GROUP BY lam."branch_code"
ORDER BY SUM(repay.total_paid) DESC NULLS LAST
LIMIT 200
```

---

### Q162: What is the loan portfolio summary for Thripunithura branch?

- **Domain:** `Loan Book` — *Branch Performance*
- **Status:** 🟢 **Answered**
- **Latency:** `7.04s`
- **Chart Type:** `briefing`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `analysis`
- **Evaluation Intent:** *Portfolio volume and risk for branch 1001 (Thripunithura)*

#### Application Response Output:
```text
HEADLINE: Portfolio health
SUMMARY / ANSWER:
Nothing is outside its threshold across 6 indicators.

CHART SPEC: Type=briefing, Title=Portfolio health
```

---

### Q163: What is the loan portfolio summary for Aluva branch?

- **Domain:** `Loan Book` — *Branch Performance*
- **Status:** 🟢 **Answered**
- **Latency:** `3.71s`
- **Chart Type:** `briefing`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `analysis`
- **Evaluation Intent:** *Portfolio volume and risk for branch 1002 (Aluva)*

#### Application Response Output:
```text
HEADLINE: Portfolio health
SUMMARY / ANSWER:
Nothing is outside its threshold across 6 indicators.

CHART SPEC: Type=briefing, Title=Portfolio health
```

---

### Q164: What is the loan portfolio summary for Nilambur branch?

- **Domain:** `Loan Book` — *Branch Performance*
- **Status:** 🟢 **Answered**
- **Latency:** `5.51s`
- **Chart Type:** `briefing`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `analysis`
- **Evaluation Intent:** *Portfolio volume and risk for branch 1006 (Nilambur)*

#### Application Response Output:
```text
HEADLINE: Portfolio health
SUMMARY / ANSWER:
Nothing is outside its threshold across 6 indicators.

CHART SPEC: Type=briefing, Title=Portfolio health
```

---

### Q165: What is the loan portfolio summary for Kozhikode branch?

- **Domain:** `Loan Book` — *Branch Performance*
- **Status:** 🟢 **Answered**
- **Latency:** `5.22s`
- **Chart Type:** `briefing`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `analysis`
- **Evaluation Intent:** *Portfolio volume and risk for branch 1007 (Kozhikode)*

#### Application Response Output:
```text
HEADLINE: Portfolio health
SUMMARY / ANSWER:
Nothing is outside its threshold across 6 indicators.

CHART SPEC: Type=briefing, Title=Portfolio health
```

---

### Q166: What is the loan portfolio summary for Chalakudy branch?

- **Domain:** `Loan Book` — *Branch Performance*
- **Status:** 🟢 **Answered**
- **Latency:** `7.07s`
- **Chart Type:** `briefing`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `briefing`
- **Evaluation Intent:** *Portfolio volume and risk for branch 1008 (Chalakudy)*

#### Application Response Output:
```text
SUMMARY / ANSWER:
3 things need attention: portfolio snapshot freshness, loan disbursement events freshness, loan repayment events freshness.

CHART SPEC: Type=briefing, Title=
```

---

### Q167: What is the loan portfolio summary for Pathanamthitta branch?

- **Domain:** `Loan Book` — *Branch Performance*
- **Status:** 🟢 **Answered**
- **Latency:** `5.43s`
- **Chart Type:** `briefing`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `analysis`
- **Evaluation Intent:** *Portfolio volume and risk for branch 1010 (Pathanamthitta)*

#### Application Response Output:
```text
HEADLINE: Portfolio health
SUMMARY / ANSWER:
Nothing is outside its threshold across 6 indicators.

CHART SPEC: Type=briefing, Title=Portfolio health
```

---

### Q168: What is the loan portfolio summary for Kanhangad branch?

- **Domain:** `Loan Book` — *Branch Performance*
- **Status:** 🟢 **Answered**
- **Latency:** `5.94s`
- **Chart Type:** `briefing`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `briefing`
- **Evaluation Intent:** *Portfolio volume and risk for branch 1012 (Kanhangad)*

#### Application Response Output:
```text
SUMMARY / ANSWER:
3 things need attention: portfolio snapshot freshness, loan disbursement events freshness, loan repayment events freshness.

CHART SPEC: Type=briefing, Title=
```

---

### Q169: What is the loan portfolio summary for Angamally branch?

- **Domain:** `Loan Book` — *Branch Performance*
- **Status:** 🟢 **Answered**
- **Latency:** `5.22s`
- **Chart Type:** `briefing`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `analysis`
- **Evaluation Intent:** *Portfolio volume and risk for branch 1013 (Angamally)*

#### Application Response Output:
```text
HEADLINE: Portfolio health
SUMMARY / ANSWER:
Nothing is outside its threshold across 6 indicators.

CHART SPEC: Type=briefing, Title=Portfolio health
```

---

### Q170: What is the loan portfolio summary for Kanjikuzhy branch?

- **Domain:** `Loan Book` — *Branch Performance*
- **Status:** 🟢 **Answered**
- **Latency:** `4.71s`
- **Chart Type:** `briefing`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `analysis`
- **Evaluation Intent:** *Portfolio volume and risk for branch 1014 (Kanjikuzhy)*

#### Application Response Output:
```text
HEADLINE: Portfolio health
SUMMARY / ANSWER:
Nothing is outside its threshold across 6 indicators.

CHART SPEC: Type=briefing, Title=Portfolio health
```

---

### Q171: What is the loan portfolio summary for Karamana branch?

- **Domain:** `Loan Book` — *Branch Performance*
- **Status:** 🟢 **Answered**
- **Latency:** `5.12s`
- **Chart Type:** `briefing`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `analysis`
- **Evaluation Intent:** *Portfolio volume and risk for branch 1016 (Karamana)*

#### Application Response Output:
```text
HEADLINE: Portfolio health
SUMMARY / ANSWER:
Nothing is outside its threshold across 6 indicators.

CHART SPEC: Type=briefing, Title=Portfolio health
```

---

### Q172: What is the loan portfolio summary for Gudallur branch?

- **Domain:** `Loan Book` — *Branch Performance*
- **Status:** 🟢 **Answered**
- **Latency:** `5.23s`
- **Chart Type:** `briefing`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `analysis`
- **Evaluation Intent:** *Portfolio volume and risk for branch 1017 (Gudallur)*

#### Application Response Output:
```text
HEADLINE: Portfolio health
SUMMARY / ANSWER:
Nothing is outside its threshold across 6 indicators.

CHART SPEC: Type=briefing, Title=Portfolio health
```

---

### Q173: What is the loan portfolio summary for Muvattupuzha branch?

- **Domain:** `Loan Book` — *Branch Performance*
- **Status:** 🟢 **Answered**
- **Latency:** `5.53s`
- **Chart Type:** `briefing`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `analysis`
- **Evaluation Intent:** *Portfolio volume and risk for branch 1018 (Muvattupuzha)*

#### Application Response Output:
```text
HEADLINE: Portfolio health
SUMMARY / ANSWER:
Nothing is outside its threshold across 6 indicators.

CHART SPEC: Type=briefing, Title=Portfolio health
```

---

### Q174: What is the loan portfolio summary for Kattapana branch?

- **Domain:** `Loan Book` — *Branch Performance*
- **Status:** 🟢 **Answered**
- **Latency:** `5.53s`
- **Chart Type:** `briefing`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `analysis`
- **Evaluation Intent:** *Portfolio volume and risk for branch 1020 (Kattapana)*

#### Application Response Output:
```text
HEADLINE: Portfolio health
SUMMARY / ANSWER:
Nothing is outside its threshold across 6 indicators.

CHART SPEC: Type=briefing, Title=Portfolio health
```

---

### Q175: What is the loan portfolio summary for Kanjirapally branch?

- **Domain:** `Loan Book` — *Branch Performance*
- **Status:** 🟢 **Answered**
- **Latency:** `5.52s`
- **Chart Type:** `briefing`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `analysis`
- **Evaluation Intent:** *Portfolio volume and risk for branch 1021 (Kanjirapally)*

#### Application Response Output:
```text
HEADLINE: Portfolio health
SUMMARY / ANSWER:
Nothing is outside its threshold across 6 indicators.

CHART SPEC: Type=briefing, Title=Portfolio health
```

---

### Q176: What is the count of female borrowers versus male borrowers in our portfolio?

- **Domain:** `Loan Book` — *Demographics & Vintages*
- **Status:** 🟢 **Answered**
- **Latency:** `1.53s`
- **Chart Type:** `donut`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `chart`
- **Evaluation Intent:** *Gender distribution of customer borrower base*

#### Application Response Output:
```text
HEADLINE: Borrowers by borrower gender (all time)
SUMMARY / ANSWER:
M has the highest borrowers, at 3,142 in all time, 55% of the total across 3 borrower genders. This measures distinct borrowers with an account sanctioned in the period, grouped by borrower gender.

CHART SPEC: Type=donut, Title=Borrowers by borrower gender (all time)
COLUMNS: Borrower gender, Borrowers
SAMPLE ROWS (3 total): [{"gender": "M", "customer_count": 3142, "gender__raw": "M"}, {"gender": "F", "customer_count": 2553, "gender__raw": "F"}, {"gender": "Not recorded", "customer_count": 46, "gender__raw": null}]

GOVERNED SQL QUERY:
SELECT customer."gender" AS gender,
       COUNT(DISTINCT lam.customer_id) AS customer_count
FROM gold.loan_account_master AS lam
     LEFT JOIN gold.customer_master AS customer ON lam."entity_num" = customer."entity_num" AND lam."customer_id" = customer."customer_id"
WHERE lam."sanction_date" BETWEEN DATE '2000-01-01' AND DATE '2026-08-24'
GROUP BY customer."gender"
ORDER BY COUNT(DISTINCT lam.customer_id) DESC NULLS LAST
LIMIT 200
```

---

### Q177: Show sanctioned amount breakdown by borrower gender.

- **Domain:** `Loan Book` — *Demographics & Vintages*
- **Status:** 🟢 **Answered**
- **Latency:** `6.14s`
- **Chart Type:** `bar`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `chart`
- **Evaluation Intent:** *Sanctioned credit volume across Male, Female, and Transgender borrowers*

#### Application Response Output:
```text
HEADLINE: Sanctioned amount by borrower gender (all time)
SUMMARY / ANSWER:
M has the highest sanctioned amount, at ₹128.19 Cr in all time, 56% of the total across 3 borrower genders. This measures sum of sanctioned amounts for accounts sanctioned in the period, grouped by borrower gender.

CHART SPEC: Type=bar, Title=Sanctioned amount by borrower gender (all time)
COLUMNS: Borrower gender, Sanctioned amount
SAMPLE ROWS (3 total): [{"gender": "M", "sanctioned_amount": 1281915902.0, "gender__raw": "M"}, {"gender": "F", "sanctioned_amount": 988293000.0, "gender__raw": "F"}, {"gender": "Not recorded", "sanctioned_amount": 20750000.0, "gender__raw": null}]

GOVERNED SQL QUERY:
SELECT customer."gender" AS gender,
       SUM(lam.sanction_amount) AS sanctioned_amount
FROM gold.loan_account_master AS lam
     LEFT JOIN gold.customer_master AS customer ON lam."entity_num" = customer."entity_num" AND lam."customer_id" = customer."customer_id"
WHERE lam."sanction_date" BETWEEN DATE '2000-01-01' AND DATE '2026-08-24'
GROUP BY customer."gender"
ORDER BY SUM(lam.sanction_amount) DESC NULLS LAST
LIMIT 200
```

---

### Q178: Show principal outstanding breakdown by borrower gender.

- **Domain:** `Loan Book` — *Demographics & Vintages*
- **Status:** 🟢 **Answered**
- **Latency:** `52.84s`
- **Chart Type:** `bar`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `chart`
- **Evaluation Intent:** *Principal outstanding exposure across borrower genders*

#### Application Response Output:
```text
HEADLINE: Show principal outstanding breakdown by borrower gender (Generated query — not a reviewed metric)
SUMMARY / ANSWER:
Male has the highest total principal outstanding at ₹115.22 Cr across 3 returned gender value(s). Sum of principal outstanding grouped by borrower gender. This uses a validated read-only generated query rather than a reviewed metric; check Source details before relying on it.

CHART SPEC: Type=bar, Title=Show principal outstanding breakdown by borrower gender (Generated query — not a reviewed metric)
COLUMNS: Gender, Total Principal Outstanding
SAMPLE ROWS (3 total): [{"gender": "Male", "total_principal_outstanding": 1152166965.47, "gender__raw": "M"}, {"gender": "Female", "total_principal_outstanding": 891568301.76, "gender__raw": "F"}, {"gender": "Not recorded", "total_principal_outstanding": 1659252.02}]

GOVERNED SQL QUERY:
SELECT
  cm.gender,
  SUM(pds.principal_outstanding) AS total_principal_outstanding
FROM gold.portfolio_daily_snapshot AS pds
JOIN gold.customer_master AS cm
  ON pds.customer_id = cm.customer_id
WHERE
  pds.principal_outstanding > 0
GROUP BY
  cm.gender
ORDER BY
  total_principal_outstanding DESC
LIMIT 100
```

---

### Q179: What is the average ticket size for female borrowers compared to male borrowers?

- **Domain:** `Loan Book` — *Demographics & Vintages*
- **Status:** 🟢 **Answered**
- **Latency:** `0.92s`
- **Chart Type:** `donut`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `chart`
- **Evaluation Intent:** *Ticket size disparity analysis by borrower gender*

#### Application Response Output:
```text
HEADLINE: Borrowers by borrower gender (all time)
SUMMARY / ANSWER:
M has the highest borrowers, at 3,142 in all time, 55% of the total across 3 borrower genders. This measures distinct borrowers with an account sanctioned in the period, grouped by borrower gender.

CHART SPEC: Type=donut, Title=Borrowers by borrower gender (all time)
COLUMNS: Borrower gender, Borrowers
SAMPLE ROWS (3 total): [{"gender": "M", "customer_count": 3142, "gender__raw": "M"}, {"gender": "F", "customer_count": 2553, "gender__raw": "F"}, {"gender": "Not recorded", "customer_count": 46, "gender__raw": null}]

GOVERNED SQL QUERY:
SELECT customer."gender" AS gender,
       COUNT(DISTINCT lam.customer_id) AS customer_count
FROM gold.loan_account_master AS lam
     LEFT JOIN gold.customer_master AS customer ON lam."entity_num" = customer."entity_num" AND lam."customer_id" = customer."customer_id"
WHERE lam."sanction_date" BETWEEN DATE '2000-01-01' AND DATE '2026-08-24'
GROUP BY customer."gender"
ORDER BY COUNT(DISTINCT lam.customer_id) DESC NULLS LAST
LIMIT 200
```

---

### Q180: Show borrower count by gender across branches.

- **Domain:** `Loan Book` — *Demographics & Vintages*
- **Status:** 🟢 **Answered**
- **Latency:** `43.93s`
- **Chart Type:** `heatmap`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `chart`
- **Evaluation Intent:** *Cross-tabulation of borrower gender across branch network*

#### Application Response Output:
```text
HEADLINE: Borrowers by borrower gender and branch (all time)
SUMMARY / ANSWER:
M has the highest borrowers, at 3,140 in all time, 55% of the total across 6 borrower genders. This measures distinct borrowers with an account sanctioned in the period, grouped by borrower gender and branch.

CHART SPEC: Type=heatmap, Title=Borrowers by borrower gender and branch (all time)
COLUMNS: Borrower gender, Branch, Borrowers
SAMPLE ROWS (6 total): [{"gender": "M", "branch": "Head Office — Credit Division", "customer_count": 3140, "gender__raw": "M", "branch__raw": 4.0}, {"gender": "F", "branch": "Head Office — Credit Division", "customer_count": 2552, "gender__raw": "F", "branch__raw": 4.0}, {"gender": "Not recorded", "branch": "Head Office — Credit Division", "customer_count": 42, "gender__raw": null, "branch__raw": 4.0}]

GOVERNED SQL QUERY:
SELECT customer."gender" AS gender,
       lam."branch_code" AS branch,
       COUNT(DISTINCT lam.customer_id) AS customer_count
FROM gold.loan_account_master AS lam
     LEFT JOIN gold.customer_master AS customer ON lam."entity_num" = customer."entity_num" AND lam."customer_id" = customer."customer_id"
WHERE lam."sanction_date" BETWEEN DATE '2000-01-01' AND DATE '2026-08-24'
GROUP BY customer."gender", lam."branch_code"
ORDER BY COUNT(DISTINCT lam.customer_id) DESC NULLS LAST
LIMIT 200
```

---

### Q181: Show top 10 agents by linked loan count.

- **Domain:** `Loan Book` — *Demographics & Vintages*
- **Status:** 🟢 **Answered**
- **Latency:** `1.54s`
- **Chart Type:** `bar`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `chart`
- **Evaluation Intent:** *Ranking sourcing and field agents by total loans linked*

#### Application Response Output:
```text
HEADLINE: Linked loans by agent (2026-08-24)
SUMMARY / ANSWER:
Vanitha has the highest linked loans, at 674 in 2026-08-24, 20% of the total across 10 agents. This measures sum of loan accounts linked to each governed agent, grouped by agent.

CHART SPEC: Type=bar, Title=Linked loans by agent (2026-08-24)
COLUMNS: Agent, Linked loans
SAMPLE ROWS (10 total): [{"agent_profile": "Vanitha", "agent_linked_loans": 674.0, "agent_profile__raw": "AGNT45"}, {"agent_profile": "Manjula", "agent_linked_loans": 384.0, "agent_profile__raw": "AGNT106"}, {"agent_profile": "Harish Gowda", "agent_linked_loans": 374.0, "agent_profile__raw": "AGNT49"}]

GOVERNED SQL QUERY:
SELECT agent."agent_code" AS agent_profile,
       SUM(agent.linked_loan_count) AS agent_linked_loans
FROM gold.agent_master AS agent
GROUP BY agent."agent_code"
ORDER BY SUM(agent.linked_loan_count) DESC NULLS LAST
LIMIT 10
```

---

### Q182: Which agents have the highest number of linked borrowers?

- **Domain:** `Loan Book` — *Demographics & Vintages*
- **Status:** 🟢 **Answered**
- **Latency:** `53.09s`
- **Chart Type:** `table`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `chart`
- **Evaluation Intent:** *Ranking agent directory by distinct linked customer count*

#### Application Response Output:
```text
HEADLINE: Which agents have the highest number of linked borrowers (Generated query — not a reviewed metric)
SUMMARY / ANSWER:
ST234 has the highest linked customer count at 3 across 50 returned agent code value(s). Agents ranked by the number of linked customers. This uses a validated read-only generated query rather than a reviewed metric; check Source details before relying on it.

CHART SPEC: Type=table, Title=Which agents have the highest number of linked borrowers (Generated query — not a reviewed metric)
COLUMNS: Agent Code, Agent Name, Linked Customer Count
SAMPLE ROWS (50 total): [{"agent_code": "ST234", "agent_name": "ABCDE", "linked_customer_count": 3}, {"agent_code": "EM1923", "agent_name": "TEST ABC", "linked_customer_count": 1}, {"agent_code": "ST98", "agent_name": "ABCDE", "linked_customer_count": 1}]

GOVERNED SQL QUERY:
SELECT
  agent_code,
  agent_name,
  linked_customer_count
FROM gold.agent_master
ORDER BY
  linked_customer_count DESC
LIMIT 50
```

---

### Q183: Show agent directory loan count distribution.

- **Domain:** `Loan Book` — *Demographics & Vintages*
- **Status:** 🟢 **Answered**
- **Latency:** `1.29s`
- **Chart Type:** `table`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `chart`
- **Evaluation Intent:** *Summary distribution of loan sourcing across agent network*

#### Application Response Output:
```text
HEADLINE: Show agent directory loan count distribution (Generated query — not a reviewed metric)
SUMMARY / ANSWER:
AGNT45 has the highest linked loan count at 674 across 200 returned agent code value(s). Current governed agent-directory fields requested by the user, ordered by linked customer count. This uses a validated read-only generated query rather than a reviewed metric; check Source details before relying on it.

CHART SPEC: Type=table, Title=Show agent directory loan count distribution (Generated query — not a reviewed metric)
COLUMNS: Agent Code, Agent Name, Designation, Branch Code, Linked Loan Count, Linked Customer Count, Mobile, Email, Agent Type, Role Code, Joined On
SAMPLE ROWS (200 total): [{"agent_code": "ST234", "agent_name": "ABCDE", "designation": "BRAUTH", "branch_code": "Branch 1037", "linked_loan_count": 0, "linked_customer_count": 3, "mobile": "9961176697", "email": null, "agent_type": "STAFF", "role_code": "BRAUTH", "joined_on": null, "branch_code__raw": "1037"}, {"agent_code": "ST98", "agent_name": "ABCDE", "designation": "BRAUTH", "branch_code": "Branch 1037", "linked_loan_count": 0, "linked_customer_count": 1, "mobile": "9497756295", "email": null, "agent_type": "STAFF", "role_code": "BRAUTH", "joined_on": null, "branch_code__raw": "1037"}, {"agent_code": "ST868", "agent_name": "ABCDE", "designation": "BRAUTH", "branch_code": "Branch 1037", "linked_loan_count": 0, "linked_customer_count": 1, "mobile": "9895015678", "email": null, "agent_type": "STAFF", "role_code": "BRAUTH", "joined_on": null, "branch_code__raw": "1037"}]

GOVERNED SQL QUERY:
SELECT
  agent_code,
  agent_name,
  designation,
  branch_code,
  linked_loan_count,
  linked_customer_count,
  mobile,
  email,
  agent_type,
  role_code,
  joined_on
FROM gold.agent_master
ORDER BY
  linked_customer_count DESC NULLS LAST
LIMIT 200
```

---

### Q184: What is the monthly origination vintage matrix distribution?

- **Domain:** `Loan Book` — *Demographics & Vintages*
- **Status:** 🟢 **Answered**
- **Latency:** `44.13s`
- **Chart Type:** `table`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `chart`
- **Evaluation Intent:** *Account counts across monthly origination cohorts (Dec 2025 - Jun 2026)*

#### Application Response Output:
```text
HEADLINE: Vintage PAR 30 account rate and Vintage NPA account rate by vintage origination month and months on book (all time)
SUMMARY / ANSWER:
2025-10-01 has the highest vintage par 30 account rate, at 20.0% in all time. The figures use these governed definitions: Vintage PAR 30 account rate: pAR-30 account count divided by cohort account count at each report month; Vintage NPA account rate: nPA account count divided by cohort account count at each report month, grouped by vintage origination month and months on book. Definition of Vintage PAR 30 account rate, Vintage NPA account rate is pending client sign-off.

CHART SPEC: Type=table, Title=Vintage PAR 30 account rate and Vintage NPA account rate by vintage origination month and months on book (all time)
COLUMNS: Vintage origination month, Months on book, Vintage PAR 30 account rate, Vintage NPA account rate
SAMPLE ROWS (45 total): [{"vintage_origination_month": "2025-10-01", "months_on_book": 8, "vintage_par30_rate": 20.0, "vintage_npa_rate": 0.0, "vintage_origination_month__raw": "2025-10-01", "months_on_book__raw": 8}, {"vintage_origination_month": "2025-10-01", "months_on_book": 4, "vintage_par30_rate": 9.090909090909092, "vintage_npa_rate": 0.0, "vintage_origination_month__raw": "2025-10-01", "months_on_book__raw": 4}, {"vintage_origination_month": "2025-10-01", "months_on_book": 7, "vintage_par30_rate": 9.090909090909092, "vintage_npa_rate": 0.0, "vintage_origination_month__raw": "2025-10-01", "months_on_book__raw": 7}]

GOVERNED SQL QUERY:
SELECT vintage."origination_month" AS vintage_origination_month,
       vintage."months_on_book" AS months_on_book,
       (100.0 * COALESCE(SUM(vintage.accounts_par30), 0) / NULLIF(SUM(vintage.account_count), 0)) AS vintage_par30_rate,
       (100.0 * COALESCE(SUM(vintage.accounts_npa), 0) / NULLIF(SUM(vintage.account_count), 0)) AS vintage_npa_rate
FROM gold.origination_vintage_matrix AS vintage
WHERE vintage."report_month" BETWEEN DATE '2000-01-01' AND DATE '2026-08-24'
GROUP BY vintage."origination_month", vintage."months_on_book"
ORDER BY (100.0 * COALESCE(SUM(vintage.accounts_par30), 0) / NULLIF(SUM(vintage.account_count), 0)) DESC NULLS LAST
LIMIT 200
```

---

### Q185: Show vintage PAR 30 rate across origination cohorts.

- **Domain:** `Loan Book` — *Demographics & Vintages*
- **Status:** 🟢 **Answered**
- **Latency:** `6.24s`
- **Chart Type:** `heatmap`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `chart`
- **Evaluation Intent:** *Cohort-level PAR 30 account delinquency rate by origination month*

#### Application Response Output:
```text
HEADLINE: Vintage PAR 30 account rate by vintage origination month and months on book (all time)
SUMMARY / ANSWER:
2025-10-01 has the highest vintage par 30 account rate, at 20.0% in all time. This measures pAR-30 account count divided by cohort account count at each report month, grouped by vintage origination month and months on book. Definition of Vintage PAR 30 account rate is pending client sign-off.

CHART SPEC: Type=heatmap, Title=Vintage PAR 30 account rate by vintage origination month and months on book (all time)
COLUMNS: Vintage origination month, Months on book, Vintage PAR 30 account rate
SAMPLE ROWS (45 total): [{"vintage_origination_month": "2025-10-01", "months_on_book": 8, "vintage_par30_rate": 20.0, "vintage_origination_month__raw": "2025-10-01", "months_on_book__raw": 8}, {"vintage_origination_month": "2025-10-01", "months_on_book": 4, "vintage_par30_rate": 9.090909090909092, "vintage_origination_month__raw": "2025-10-01", "months_on_book__raw": 4}, {"vintage_origination_month": "2025-10-01", "months_on_book": 7, "vintage_par30_rate": 9.090909090909092, "vintage_origination_month__raw": "2025-10-01", "months_on_book__raw": 7}]

GOVERNED SQL QUERY:
SELECT vintage."origination_month" AS vintage_origination_month,
       vintage."months_on_book" AS months_on_book,
       (100.0 * COALESCE(SUM(vintage.accounts_par30), 0) / NULLIF(SUM(vintage.account_count), 0)) AS vintage_par30_rate
FROM gold.origination_vintage_matrix AS vintage
WHERE vintage."report_month" BETWEEN DATE '2000-01-01' AND DATE '2026-08-24'
GROUP BY vintage."origination_month", vintage."months_on_book"
ORDER BY (100.0 * COALESCE(SUM(vintage.accounts_par30), 0) / NULLIF(SUM(vintage.account_count), 0)) DESC NULLS LAST
LIMIT 200
```

---

### Q186: Show vintage NPA rate across origination months.

- **Domain:** `Loan Book` — *Demographics & Vintages*
- **Status:** 🟢 **Answered**
- **Latency:** `5.74s`
- **Chart Type:** `bar`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `chart`
- **Evaluation Intent:** *Cohort-level NPA account default rate by origination month*

#### Application Response Output:
```text
HEADLINE: Vintage NPA account rate by vintage origination month (all time)
SUMMARY / ANSWER:
2025-10-01 has the highest vintage npa account rate, at 0.00% in all time. This measures nPA account count divided by cohort account count at each report month, grouped by vintage origination month. Every value is zero — this is a real result, not a failed query. Definition of Vintage NPA account rate is pending client sign-off.

CHART SPEC: Type=bar, Title=Vintage NPA account rate by vintage origination month (all time)
COLUMNS: Vintage origination month, Vintage NPA account rate
SAMPLE ROWS (9 total): [{"vintage_origination_month": "2025-10-01", "vintage_npa_rate": 0.0, "vintage_origination_month__raw": "2025-10-01"}, {"vintage_origination_month": "2025-11-01", "vintage_npa_rate": 0.0, "vintage_origination_month__raw": "2025-11-01"}, {"vintage_origination_month": "2025-12-01", "vintage_npa_rate": 0.0, "vintage_origination_month__raw": "2025-12-01"}]

GOVERNED SQL QUERY:
SELECT vintage."origination_month" AS vintage_origination_month,
       (100.0 * COALESCE(SUM(vintage.accounts_npa), 0) / NULLIF(SUM(vintage.account_count), 0)) AS vintage_npa_rate
FROM gold.origination_vintage_matrix AS vintage
WHERE vintage."report_month" BETWEEN DATE '2000-01-01' AND DATE '2026-08-24'
GROUP BY vintage."origination_month"
ORDER BY (100.0 * COALESCE(SUM(vintage.accounts_npa), 0) / NULLIF(SUM(vintage.account_count), 0)) DESC NULLS LAST
LIMIT 200
```

---

### Q187: What is the vintage performance by months on book?

- **Domain:** `Loan Book` — *Demographics & Vintages*
- **Status:** 🟢 **Answered**
- **Latency:** `1.03s`
- **Chart Type:** `line`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `chart`
- **Evaluation Intent:** *Delinquency seasoning curve across Months on Book (MOB 1 to 9)*

#### Application Response Output:
```text
HEADLINE: Vintage PAR 30 account rate and Vintage NPA account rate by vintage origination month and month (all time)
SUMMARY / ANSWER:
Vintage PAR 30 account rate was unchanged from 0.00% (Oct 2025) to 0.00% (Jun 2026). The figures use these governed definitions: Vintage PAR 30 account rate: pAR-30 account count divided by cohort account count at each report month; Vintage NPA account rate: nPA account count divided by cohort account count at each report month, grouped by vintage origination month and month. Definition of Vintage PAR 30 account rate, Vintage NPA account rate is pending client sign-off.

CHART SPEC: Type=line, Title=Vintage PAR 30 account rate and Vintage NPA account rate by vintage origination month and month (all time)
COLUMNS: Vintage origination month, Month, Vintage PAR 30 account rate, Vintage NPA account rate
SAMPLE ROWS (45 total): [{"vintage_origination_month": "2025-10-01", "month": "Oct 2025", "vintage_par30_rate": 0.0, "vintage_npa_rate": 0.0, "vintage_origination_month__raw": "2025-10-01", "month__raw": "2025-10-01"}, {"vintage_origination_month": "2025-10-01", "month": "Nov 2025", "vintage_par30_rate": 0.0, "vintage_npa_rate": 0.0, "vintage_origination_month__raw": "2025-10-01", "month__raw": "2025-11-01"}, {"vintage_origination_month": "2025-11-01", "month": "Nov 2025", "vintage_par30_rate": 0.0, "vintage_npa_rate": 0.0, "vintage_origination_month__raw": "2025-11-01", "month__raw": "2025-11-01"}]

GOVERNED SQL QUERY:
SELECT vintage."origination_month" AS vintage_origination_month,
       DATE_TRUNC('month', vintage."report_month")::date AS month,
       (100.0 * COALESCE(SUM(vintage.accounts_par30), 0) / NULLIF(SUM(vintage.account_count), 0)) AS vintage_par30_rate,
       (100.0 * COALESCE(SUM(vintage.accounts_npa), 0) / NULLIF(SUM(vintage.account_count), 0)) AS vintage_npa_rate
FROM gold.origination_vintage_matrix AS vintage
WHERE vintage."report_month" BETWEEN DATE '2000-01-01' AND DATE '2026-08-24'
GROUP BY vintage."origination_month", DATE_TRUNC('month', vintage."report_month")::date
ORDER BY DATE_TRUNC('month', vintage."report_month")::date ASC
LIMIT 200
```

---

### Q188: Show vintage account count by product code.

- **Domain:** `Loan Book` — *Demographics & Vintages*
- **Status:** 🟢 **Answered**
- **Latency:** `7.66s`
- **Chart Type:** `scatter`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `chart`
- **Evaluation Intent:** *Origination cohort volume across product lines*

#### Application Response Output:
```text
HEADLINE: Vintage NPA account rate and Vintage PAR 30 account rate by vintage product (all time)
SUMMARY / ANSWER:
Business & MSME Loans is the only vintage product returned, with vintage npa account rate of 0.00% in all time. The figures use these governed definitions: Vintage NPA account rate: nPA account count divided by cohort account count at each report month; Vintage PAR 30 account rate: pAR-30 account count divided by cohort account count at each report month, grouped by vintage product. Every value is zero — this is a real result, not a failed query. Definition of Vintage NPA account rate, Vintage PAR 30 account rate is pending client sign-off.

CHART SPEC: Type=scatter, Title=Vintage NPA account rate and Vintage PAR 30 account rate by vintage product (all time)
COLUMNS: Vintage product, Vintage NPA account rate, Vintage PAR 30 account rate
SAMPLE ROWS (1 total): [{"vintage_product": "Business & MSME Loans", "vintage_npa_rate": 0.0, "vintage_par30_rate": 0.10766000968940087, "vintage_product__raw": 16.0}]

GOVERNED SQL QUERY:
SELECT vintage."product_code" AS vintage_product,
       (100.0 * COALESCE(SUM(vintage.accounts_npa), 0) / NULLIF(SUM(vintage.account_count), 0)) AS vintage_npa_rate,
       (100.0 * COALESCE(SUM(vintage.accounts_par30), 0) / NULLIF(SUM(vintage.account_count), 0)) AS vintage_par30_rate
FROM gold.origination_vintage_matrix AS vintage
WHERE vintage."report_month" BETWEEN DATE '2000-01-01' AND DATE '2026-08-24'
GROUP BY vintage."product_code"
ORDER BY (100.0 * COALESCE(SUM(vintage.accounts_npa), 0) / NULLIF(SUM(vintage.account_count), 0)) DESC NULLS LAST
LIMIT 200
```

---

### Q189: Show vintage account count by branch.

- **Domain:** `Loan Book` — *Demographics & Vintages*
- **Status:** 🟢 **Answered**
- **Latency:** `6.77s`
- **Chart Type:** `bar`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `chart`
- **Evaluation Intent:** *Origination cohort volume across branch network*

#### Application Response Output:
```text
HEADLINE: Vintage NPA account rate by vintage branch (all time)
SUMMARY / ANSWER:
Head Office has the highest vintage npa account rate, at 0.00% in all time. This measures nPA account count divided by cohort account count at each report month, grouped by vintage branch. Every value is zero — this is a real result, not a failed query. Definition of Vintage NPA account rate is pending client sign-off.

CHART SPEC: Type=bar, Title=Vintage NPA account rate by vintage branch (all time)
COLUMNS: Vintage branch, Vintage NPA account rate
SAMPLE ROWS (2 total): [{"vintage_branch": "Head Office", "vintage_npa_rate": 0.0, "vintage_branch__raw": 1.0}, {"vintage_branch": "Head Office — Credit Division", "vintage_npa_rate": 0.0, "vintage_branch__raw": 4.0}]

GOVERNED SQL QUERY:
SELECT vintage."branch_code" AS vintage_branch,
       (100.0 * COALESCE(SUM(vintage.accounts_npa), 0) / NULLIF(SUM(vintage.account_count), 0)) AS vintage_npa_rate
FROM gold.origination_vintage_matrix AS vintage
WHERE vintage."report_month" BETWEEN DATE '2000-01-01' AND DATE '2026-08-24'
GROUP BY vintage."branch_code"
ORDER BY (100.0 * COALESCE(SUM(vintage.accounts_npa), 0) / NULLIF(SUM(vintage.account_count), 0)) DESC NULLS LAST
LIMIT 200
```

---

### Q190: What is the total number of collection handover records?

- **Domain:** `Loan Book` — *Demographics & Vintages*
- **Status:** 🟢 **Answered**
- **Latency:** `3.37s`
- **Chart Type:** `kpi`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `chart`
- **Evaluation Intent:** *Count of recovery ownership reassignments in collection handover events*

#### Application Response Output:
```text
HEADLINE: Collection handovers (all time)
SUMMARY / ANSWER:
Collection handovers was 174 in all time. This measures count of collection ownership handover records in the period.

CHART SPEC: Type=kpi, Title=Collection handovers (all time)
COLUMNS: Collection handovers
SAMPLE ROWS (1 total): [{"collection_handover_count": 174}]

GOVERNED SQL QUERY:
SELECT COUNT(*) AS collection_handover_count
FROM gold.collection_handover_events AS handover
WHERE handover."handover_date" BETWEEN DATE '2000-01-01' AND DATE '2026-08-24'
LIMIT 200
```

---

### Q191: How healthy is our portfolio?

- **Domain:** `Loan Book` — *Analyses & Worklists*
- **Status:** 🟢 **Answered**
- **Latency:** `3.08s`
- **Chart Type:** `briefing`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `analysis`
- **Evaluation Intent:** *Composite portfolio health analysis (outstanding, arrears, PAR, NPA, CE)*

#### Application Response Output:
```text
HEADLINE: Portfolio health
SUMMARY / ANSWER:
Nothing is outside its threshold across 6 indicators.

CHART SPEC: Type=briefing, Title=Portfolio health
```

---

### Q192: Where should collections focus?

- **Domain:** `Loan Book` — *Analyses & Worklists*
- **Status:** 🟢 **Answered**
- **Latency:** `5.22s`
- **Chart Type:** `worklist`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `worklist`
- **Evaluation Intent:** *Composite collections focus analysis (shortfall, branch CE, DPD buckets)*

#### Application Response Output:
```text
HEADLINE: Today's collection priority list
SUMMARY / ANSWER:
Today's collection priority list: 50 accounts, 50 needing immediate action.

CHART SPEC: Type=worklist, Title=Today's collection priority list
COLUMNS: Account, Borrower, Branch, Product, Agent, Asset class, Days past due, Overdue, Outstanding, EMI, Last payment, Days since payment, Days since repayment began, Previous asset class, NPA date

GOVERNED SQL QUERY:
SELECT s.loan_account_number AS loan_account_number,
       s.customer_name AS borrower,
       s.branch_code AS branch,
       s.product_code AS product,
       l.agent_name AS agent,
       s.asset_code AS asset_class,
       s.dpd_days AS dpd_days,
       s.total_overdue AS total_overdue,
       s.principal_outstanding AS principal_outstanding,
       l.emi_amount AS emi_amount,
       l.last_payment_date AS last_payment_date,
       CASE WHEN l.last_payment_date IS NULL THEN NULL ELSE (DATE '2026-08-24'::date - l.last_payment_date::date) END AS days_since_last_payment,
       CASE WHEN l.repayment_start_date IS NULL THEN NULL ELSE (DATE '2026-08-24'::date - l.repayment_start_date::date) END AS days_since_repayment_start,
       s.previous_asset_code AS previous_asset_class,
       l.npa_date AS npa_date,
       (COALESCE(l.receipt_count, 0) = 0 AND l.repayment_start_date IS NOT NULL AND l.repayment_start_date < DATE '2026-08-24'::date) AS rule__never_paid,
       (s.previous_asset_code IS NOT NULL AND (CASE s.asset_code WHEN 'STD' THEN 0 WHEN 'SMA0' THEN 1 WHEN 'SMA1' THEN 2 WHEN 'SMA2' THEN 3 WHEN 'NPA' THEN 4 ELSE -1 END) > (CASE s.previous_asset_code WHEN 'STD' THEN 0 WHEN 'SMA0' THEN 1 WHEN 'SMA1' THEN 2 WHEN 'SMA2' THEN 3 WHEN 'NPA' THEN 4 ELSE -1 END) AND (CASE s.previous_asset_code WHEN 'STD' THEN 0 WHEN 'SMA0' THEN 1 WHEN 'SMA1' THEN 2 WHEN 'SMA2' THEN 3 WHEN 'NPA' THEN 4 ELSE -1 END) >= 0) AS rule__classification_worsened,
       (s.total_overdue > 0 AND l.last_payment_date IS NOT NULL AND l.last_payment_date < DATE '2026-08-24'::date - INTERVAL '60 days') AS rule__payments_stalled,
       (l.emi_amount > 0 AND s.total_overdue > l.emi_amount * 3) AS rule__overdue_exceeds_three_emis,
       (s.is_npa AND l.npa_date IS NOT NULL AND l.npa_date >= DATE '2026-08-24'::date - INTERVAL '90 days') AS rule__newly_npa,
       (s.dpd_days BETWEEN 1 AND 30 AND s.total_overdue > 0) AS rule__early_stress
FROM gold.portfolio_daily_snapshot s
LEFT JOIN gold.loan_account_master l ON l.entity_num = s.entity_num AND l.loan_account_number = s.loan_account_number
WHERE ((COALESCE(l.receipt_count, 0) = 0 AND l.repayment_start_date IS NOT NULL AND l.repayment_start_date < DATE '2026-08-24'::date) OR (s.previous_asset_code IS NOT NULL AND (CASE s.asset_code WHEN 'STD' THEN 0 WHEN 'SMA0' THEN 1 WHEN 'SMA1' THEN 2 WHEN 'SMA2' THEN 3 WHEN 'NPA' THEN 4 ELSE -1 END) > (CASE s.previous_asset_code WHEN 'STD' THEN 0 WHEN 'SMA0' THEN 1 WHEN 'SMA1' THEN 2 WHEN 'SMA2' THEN 3 WHEN 'NPA' THEN 4 ELSE -1 END) AND (CASE s.previous_asset_code WHEN 'STD' THEN 0 WHEN 'SMA0' THEN 1 WHEN 'SMA1' THEN 2 WHEN 'SMA2' THEN 3 WHEN 'NPA' THEN 4 ELSE -1 END) >= 0) OR (s.total_overdue > 0 AND l.last_payment_date IS NOT NULL AND l.last_payment_date < DATE '2026-08-24'::date - INTERVAL '60 days') OR (l.emi_amount > 0 AND s.total_overdue > l.emi_amount * 3) OR (s.is_npa AND l.npa_date IS NOT NULL AND l.npa_date >= DATE '2026-08-24'::date - INTERVAL '90 days') OR (s.dpd_days BETWEEN 1 AND 30 AND s.total_overdue > 0))
ORDER BY s.total_overdue DESC NULLS LAST, s.dpd_days DESC NULLS LAST
LIMIT 50
```

---

### Q193: How is origination doing?

- **Domain:** `Loan Book` — *Analyses & Worklists*
- **Status:** 🟢 **Answered**
- **Latency:** `5.23s`
- **Chart Type:** `briefing`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `analysis`
- **Evaluation Intent:** *Composite origination review (disbursements, sanctions, ticket size, yields)*

#### Application Response Output:
```text
HEADLINE: Origination review
SUMMARY / ANSWER:
Nothing is outside its threshold across 6 indicators.

CHART SPEC: Type=briefing, Title=Origination review
```

---

### Q194: What is our single borrower concentration risk?

- **Domain:** `Loan Book` — *Analyses & Worklists*
- **Status:** 🟢 **Answered**
- **Latency:** `5.20s`
- **Chart Type:** `concentration`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `analysis`
- **Evaluation Intent:** *Composite concentration analysis (Herfindahl index, top 10 borrower exposures)*

#### Application Response Output:
```text
HEADLINE: Concentration risk
SUMMARY / ANSWER:
The Herfindahl index across 500 borrowers is 0.003 (not concentrated).

CHART SPEC: Type=concentration, Title=Concentration risk
```

---

### Q195: Which branches have the best growth and credit quality?

- **Domain:** `Loan Book` — *Analyses & Worklists*
- **Status:** 🟢 **Answered**
- **Latency:** `5.85s`
- **Chart Type:** `quadrant`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `analysis`
- **Evaluation Intent:** *Quadrant analysis comparing branch disbursement growth vs PAR 30 credit quality*

#### Application Response Output:
```text
HEADLINE: Growth against credit quality
SUMMARY / ANSWER:
One comparable member is available; a relative ranking is not possible.

CHART SPEC: Type=quadrant, Title=Growth against credit quality
```

---

### Q196: Show today's collection priority list.

- **Domain:** `Loan Book` — *Analyses & Worklists*
- **Status:** 🟢 **Answered**
- **Latency:** `3.39s`
- **Chart Type:** `worklist`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `worklist`
- **Evaluation Intent:** *Governed worklist of delinquent accounts ranked by priority score*

#### Application Response Output:
```text
HEADLINE: Today's collection priority list
SUMMARY / ANSWER:
Today's collection priority list: 50 accounts, 50 needing immediate action.

CHART SPEC: Type=worklist, Title=Today's collection priority list
COLUMNS: Account, Borrower, Branch, Product, Agent, Asset class, Days past due, Overdue, Outstanding, EMI, Last payment, Days since payment, Days since repayment began, Previous asset class, NPA date

GOVERNED SQL QUERY:
SELECT s.loan_account_number AS loan_account_number,
       s.customer_name AS borrower,
       s.branch_code AS branch,
       s.product_code AS product,
       l.agent_name AS agent,
       s.asset_code AS asset_class,
       s.dpd_days AS dpd_days,
       s.total_overdue AS total_overdue,
       s.principal_outstanding AS principal_outstanding,
       l.emi_amount AS emi_amount,
       l.last_payment_date AS last_payment_date,
       CASE WHEN l.last_payment_date IS NULL THEN NULL ELSE (DATE '2026-08-24'::date - l.last_payment_date::date) END AS days_since_last_payment,
       CASE WHEN l.repayment_start_date IS NULL THEN NULL ELSE (DATE '2026-08-24'::date - l.repayment_start_date::date) END AS days_since_repayment_start,
       s.previous_asset_code AS previous_asset_class,
       l.npa_date AS npa_date,
       (COALESCE(l.receipt_count, 0) = 0 AND l.repayment_start_date IS NOT NULL AND l.repayment_start_date < DATE '2026-08-24'::date) AS rule__never_paid,
       (s.previous_asset_code IS NOT NULL AND (CASE s.asset_code WHEN 'STD' THEN 0 WHEN 'SMA0' THEN 1 WHEN 'SMA1' THEN 2 WHEN 'SMA2' THEN 3 WHEN 'NPA' THEN 4 ELSE -1 END) > (CASE s.previous_asset_code WHEN 'STD' THEN 0 WHEN 'SMA0' THEN 1 WHEN 'SMA1' THEN 2 WHEN 'SMA2' THEN 3 WHEN 'NPA' THEN 4 ELSE -1 END) AND (CASE s.previous_asset_code WHEN 'STD' THEN 0 WHEN 'SMA0' THEN 1 WHEN 'SMA1' THEN 2 WHEN 'SMA2' THEN 3 WHEN 'NPA' THEN 4 ELSE -1 END) >= 0) AS rule__classification_worsened,
       (s.total_overdue > 0 AND l.last_payment_date IS NOT NULL AND l.last_payment_date < DATE '2026-08-24'::date - INTERVAL '60 days') AS rule__payments_stalled,
       (l.emi_amount > 0 AND s.total_overdue > l.emi_amount * 3) AS rule__overdue_exceeds_three_emis,
       (s.is_npa AND l.npa_date IS NOT NULL AND l.npa_date >= DATE '2026-08-24'::date - INTERVAL '90 days') AS rule__newly_npa,
       (s.dpd_days BETWEEN 1 AND 30 AND s.total_overdue > 0) AS rule__early_stress
FROM gold.portfolio_daily_snapshot s
LEFT JOIN gold.loan_account_master l ON l.entity_num = s.entity_num AND l.loan_account_number = s.loan_account_number
WHERE ((COALESCE(l.receipt_count, 0) = 0 AND l.repayment_start_date IS NOT NULL AND l.repayment_start_date < DATE '2026-08-24'::date) OR (s.previous_asset_code IS NOT NULL AND (CASE s.asset_code WHEN 'STD' THEN 0 WHEN 'SMA0' THEN 1 WHEN 'SMA1' THEN 2 WHEN 'SMA2' THEN 3 WHEN 'NPA' THEN 4 ELSE -1 END) > (CASE s.previous_asset_code WHEN 'STD' THEN 0 WHEN 'SMA0' THEN 1 WHEN 'SMA1' THEN 2 WHEN 'SMA2' THEN 3 WHEN 'NPA' THEN 4 ELSE -1 END) AND (CASE s.previous_asset_code WHEN 'STD' THEN 0 WHEN 'SMA0' THEN 1 WHEN 'SMA1' THEN 2 WHEN 'SMA2' THEN 3 WHEN 'NPA' THEN 4 ELSE -1 END) >= 0) OR (s.total_overdue > 0 AND l.last_payment_date IS NOT NULL AND l.last_payment_date < DATE '2026-08-24'::date - INTERVAL '60 days') OR (l.emi_amount > 0 AND s.total_overdue > l.emi_amount * 3) OR (s.is_npa AND l.npa_date IS NOT NULL AND l.npa_date >= DATE '2026-08-24'::date - INTERVAL '90 days') OR (s.dpd_days BETWEEN 1 AND 30 AND s.total_overdue > 0))
ORDER BY s.total_overdue DESC NULLS LAST, s.dpd_days DESC NULLS LAST
LIMIT 50
```

---

### Q197: Show early-warning accounts watchlist.

- **Domain:** `Loan Book` — *Analyses & Worklists*
- **Status:** 🟢 **Answered**
- **Latency:** `5.20s`
- **Chart Type:** `worklist`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `worklist`
- **Evaluation Intent:** *Governed worklist of accounts showing early stress before severe arrears*

#### Application Response Output:
```text
HEADLINE: Early-warning accounts
SUMMARY / ANSWER:
Early-warning accounts: 50 accounts, 50 needing immediate action.

CHART SPEC: Type=worklist, Title=Early-warning accounts
COLUMNS: Account, Borrower, Branch, Product, Agent, Asset class, Days past due, Overdue, Outstanding, EMI, Last payment, Days since payment, Days since repayment began, Previous asset class, NPA date

GOVERNED SQL QUERY:
SELECT s.loan_account_number AS loan_account_number,
       s.customer_name AS borrower,
       s.branch_code AS branch,
       s.product_code AS product,
       l.agent_name AS agent,
       s.asset_code AS asset_class,
       s.dpd_days AS dpd_days,
       s.total_overdue AS total_overdue,
       s.principal_outstanding AS principal_outstanding,
       l.emi_amount AS emi_amount,
       l.last_payment_date AS last_payment_date,
       CASE WHEN l.last_payment_date IS NULL THEN NULL ELSE (DATE '2026-08-24'::date - l.last_payment_date::date) END AS days_since_last_payment,
       CASE WHEN l.repayment_start_date IS NULL THEN NULL ELSE (DATE '2026-08-24'::date - l.repayment_start_date::date) END AS days_since_repayment_start,
       s.previous_asset_code AS previous_asset_class,
       l.npa_date AS npa_date,
       (COALESCE(l.receipt_count, 0) = 0 AND l.repayment_start_date IS NOT NULL AND l.repayment_start_date < DATE '2026-08-24'::date) AS rule__never_paid,
       (s.previous_asset_code IS NOT NULL AND (CASE s.asset_code WHEN 'STD' THEN 0 WHEN 'SMA0' THEN 1 WHEN 'SMA1' THEN 2 WHEN 'SMA2' THEN 3 WHEN 'NPA' THEN 4 ELSE -1 END) > (CASE s.previous_asset_code WHEN 'STD' THEN 0 WHEN 'SMA0' THEN 1 WHEN 'SMA1' THEN 2 WHEN 'SMA2' THEN 3 WHEN 'NPA' THEN 4 ELSE -1 END) AND (CASE s.previous_asset_code WHEN 'STD' THEN 0 WHEN 'SMA0' THEN 1 WHEN 'SMA1' THEN 2 WHEN 'SMA2' THEN 3 WHEN 'NPA' THEN 4 ELSE -1 END) >= 0) AS rule__classification_worsened,
       (s.dpd_days BETWEEN 1 AND 30 AND s.total_overdue > 0) AS rule__early_stress,
       (s.total_overdue > 0 AND s.principal_outstanding >= ( SELECT PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY principal_outstanding) FROM gold.portfolio_daily_snapshot )) AS rule__large_exposure_in_arrears
FROM gold.portfolio_daily_snapshot s
LEFT JOIN gold.loan_account_master l ON l.entity_num = s.entity_num AND l.loan_account_number = s.loan_account_number
WHERE ((COALESCE(l.receipt_count, 0) = 0 AND l.repayment_start_date IS NOT NULL AND l.repayment_start_date < DATE '2026-08-24'::date) OR (s.previous_asset_code IS NOT NULL AND (CASE s.asset_code WHEN 'STD' THEN 0 WHEN 'SMA0' THEN 1 WHEN 'SMA1' THEN 2 WHEN 'SMA2' THEN 3 WHEN 'NPA' THEN 4 ELSE -1 END) > (CASE s.previous_asset_code WHEN 'STD' THEN 0 WHEN 'SMA0' THEN 1 WHEN 'SMA1' THEN 2 WHEN 'SMA2' THEN 3 WHEN 'NPA' THEN 4 ELSE -1 END) AND (CASE s.previous_asset_code WHEN 'STD' THEN 0 WHEN 'SMA0' THEN 1 WHEN 'SMA1' THEN 2 WHEN 'SMA2' THEN 3 WHEN 'NPA' THEN 4 ELSE -1 END) >= 0) OR (s.dpd_days BETWEEN 1 AND 30 AND s.total_overdue > 0) OR (s.total_overdue > 0 AND s.principal_outstanding >= ( SELECT PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY principal_outstanding) FROM gold.portfolio_daily_snapshot )))
ORDER BY s.total_overdue DESC NULLS LAST, s.dpd_days DESC NULLS LAST
LIMIT 50
```

---

### Q198: Show large exposures in arrears.

- **Domain:** `Loan Book` — *Analyses & Worklists*
- **Status:** 🟢 **Answered**
- **Latency:** `5.53s`
- **Chart Type:** `worklist`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `worklist`
- **Evaluation Intent:** *Governed worklist of top 1% loan exposures currently in delinquency*

#### Application Response Output:
```text
HEADLINE: Large exposures in arrears
SUMMARY / ANSWER:
Large exposures in arrears: 25 accounts, 25 needing immediate action.

CHART SPEC: Type=worklist, Title=Large exposures in arrears
COLUMNS: Account, Borrower, Branch, Product, Agent, Asset class, Days past due, Overdue, Outstanding, EMI, Last payment, Days since payment, Days since repayment began, Previous asset class, NPA date

GOVERNED SQL QUERY:
SELECT s.loan_account_number AS loan_account_number,
       s.customer_name AS borrower,
       s.branch_code AS branch,
       s.product_code AS product,
       l.agent_name AS agent,
       s.asset_code AS asset_class,
       s.dpd_days AS dpd_days,
       s.total_overdue AS total_overdue,
       s.principal_outstanding AS principal_outstanding,
       l.emi_amount AS emi_amount,
       l.last_payment_date AS last_payment_date,
       CASE WHEN l.last_payment_date IS NULL THEN NULL ELSE (DATE '2026-08-24'::date - l.last_payment_date::date) END AS days_since_last_payment,
       CASE WHEN l.repayment_start_date IS NULL THEN NULL ELSE (DATE '2026-08-24'::date - l.repayment_start_date::date) END AS days_since_repayment_start,
       s.previous_asset_code AS previous_asset_class,
       l.npa_date AS npa_date,
       (s.total_overdue > 0 AND s.principal_outstanding >= ( SELECT PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY principal_outstanding) FROM gold.portfolio_daily_snapshot )) AS rule__large_exposure_in_arrears,
       (s.is_npa AND l.npa_date IS NOT NULL AND l.npa_date >= DATE '2026-08-24'::date - INTERVAL '90 days') AS rule__newly_npa,
       (s.previous_asset_code IS NOT NULL AND (CASE s.asset_code WHEN 'STD' THEN 0 WHEN 'SMA0' THEN 1 WHEN 'SMA1' THEN 2 WHEN 'SMA2' THEN 3 WHEN 'NPA' THEN 4 ELSE -1 END) > (CASE s.previous_asset_code WHEN 'STD' THEN 0 WHEN 'SMA0' THEN 1 WHEN 'SMA1' THEN 2 WHEN 'SMA2' THEN 3 WHEN 'NPA' THEN 4 ELSE -1 END) AND (CASE s.previous_asset_code WHEN 'STD' THEN 0 WHEN 'SMA0' THEN 1 WHEN 'SMA1' THEN 2 WHEN 'SMA2' THEN 3 WHEN 'NPA' THEN 4 ELSE -1 END) >= 0) AS rule__classification_worsened
FROM gold.portfolio_daily_snapshot s
LEFT JOIN gold.loan_account_master l ON l.entity_num = s.entity_num AND l.loan_account_number = s.loan_account_number
WHERE ((s.total_overdue > 0 AND s.principal_outstanding >= ( SELECT PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY principal_outstanding) FROM gold.portfolio_daily_snapshot )) OR (s.is_npa AND l.npa_date IS NOT NULL AND l.npa_date >= DATE '2026-08-24'::date - INTERVAL '90 days') OR (s.previous_asset_code IS NOT NULL AND (CASE s.asset_code WHEN 'STD' THEN 0 WHEN 'SMA0' THEN 1 WHEN 'SMA1' THEN 2 WHEN 'SMA2' THEN 3 WHEN 'NPA' THEN 4 ELSE -1 END) > (CASE s.previous_asset_code WHEN 'STD' THEN 0 WHEN 'SMA0' THEN 1 WHEN 'SMA1' THEN 2 WHEN 'SMA2' THEN 3 WHEN 'NPA' THEN 4 ELSE -1 END) AND (CASE s.previous_asset_code WHEN 'STD' THEN 0 WHEN 'SMA0' THEN 1 WHEN 'SMA1' THEN 2 WHEN 'SMA2' THEN 3 WHEN 'NPA' THEN 4 ELSE -1 END) >= 0))
ORDER BY s.total_overdue DESC NULLS LAST, s.dpd_days DESC NULLS LAST
LIMIT 25
```

---

### Q199: List top 10 largest overdue loan accounts.

- **Domain:** `Loan Book` — *Analyses & Worklists*
- **Status:** 🟢 **Answered**
- **Latency:** `4.08s`
- **Chart Type:** `worklist`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `worklist`
- **Evaluation Intent:** *Governed worklist of individual accounts with largest total overdue balances*

#### Application Response Output:
```text
HEADLINE: Large exposures in arrears
SUMMARY / ANSWER:
Large exposures in arrears: 25 accounts, 25 needing immediate action.

CHART SPEC: Type=worklist, Title=Large exposures in arrears
COLUMNS: Account, Borrower, Branch, Product, Agent, Asset class, Days past due, Overdue, Outstanding, EMI, Last payment, Days since payment, Days since repayment began, Previous asset class, NPA date

GOVERNED SQL QUERY:
SELECT s.loan_account_number AS loan_account_number,
       s.customer_name AS borrower,
       s.branch_code AS branch,
       s.product_code AS product,
       l.agent_name AS agent,
       s.asset_code AS asset_class,
       s.dpd_days AS dpd_days,
       s.total_overdue AS total_overdue,
       s.principal_outstanding AS principal_outstanding,
       l.emi_amount AS emi_amount,
       l.last_payment_date AS last_payment_date,
       CASE WHEN l.last_payment_date IS NULL THEN NULL ELSE (DATE '2026-08-24'::date - l.last_payment_date::date) END AS days_since_last_payment,
       CASE WHEN l.repayment_start_date IS NULL THEN NULL ELSE (DATE '2026-08-24'::date - l.repayment_start_date::date) END AS days_since_repayment_start,
       s.previous_asset_code AS previous_asset_class,
       l.npa_date AS npa_date,
       (s.total_overdue > 0 AND s.principal_outstanding >= ( SELECT PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY principal_outstanding) FROM gold.portfolio_daily_snapshot )) AS rule__large_exposure_in_arrears,
       (s.is_npa AND l.npa_date IS NOT NULL AND l.npa_date >= DATE '2026-08-24'::date - INTERVAL '90 days') AS rule__newly_npa,
       (s.previous_asset_code IS NOT NULL AND (CASE s.asset_code WHEN 'STD' THEN 0 WHEN 'SMA0' THEN 1 WHEN 'SMA1' THEN 2 WHEN 'SMA2' THEN 3 WHEN 'NPA' THEN 4 ELSE -1 END) > (CASE s.previous_asset_code WHEN 'STD' THEN 0 WHEN 'SMA0' THEN 1 WHEN 'SMA1' THEN 2 WHEN 'SMA2' THEN 3 WHEN 'NPA' THEN 4 ELSE -1 END) AND (CASE s.previous_asset_code WHEN 'STD' THEN 0 WHEN 'SMA0' THEN 1 WHEN 'SMA1' THEN 2 WHEN 'SMA2' THEN 3 WHEN 'NPA' THEN 4 ELSE -1 END) >= 0) AS rule__classification_worsened
FROM gold.portfolio_daily_snapshot s
LEFT JOIN gold.loan_account_master l ON l.entity_num = s.entity_num AND l.loan_account_number = s.loan_account_number
WHERE ((s.total_overdue > 0 AND s.principal_outstanding >= ( SELECT PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY principal_outstanding) FROM gold.portfolio_daily_snapshot )) OR (s.is_npa AND l.npa_date IS NOT NULL AND l.npa_date >= DATE '2026-08-24'::date - INTERVAL '90 days') OR (s.previous_asset_code IS NOT NULL AND (CASE s.asset_code WHEN 'STD' THEN 0 WHEN 'SMA0' THEN 1 WHEN 'SMA1' THEN 2 WHEN 'SMA2' THEN 3 WHEN 'NPA' THEN 4 ELSE -1 END) > (CASE s.previous_asset_code WHEN 'STD' THEN 0 WHEN 'SMA0' THEN 1 WHEN 'SMA1' THEN 2 WHEN 'SMA2' THEN 3 WHEN 'NPA' THEN 4 ELSE -1 END) AND (CASE s.previous_asset_code WHEN 'STD' THEN 0 WHEN 'SMA0' THEN 1 WHEN 'SMA1' THEN 2 WHEN 'SMA2' THEN 3 WHEN 'NPA' THEN 4 ELSE -1 END) >= 0))
ORDER BY s.total_overdue DESC NULLS LAST, s.dpd_days DESC NULLS LAST
LIMIT 25
```

---

### Q200: What is the overall summary of our loan book performance?

- **Domain:** `Loan Book` — *Analyses & Worklists*
- **Status:** 🟢 **Answered**
- **Latency:** `3.91s`
- **Chart Type:** `briefing`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `analysis`
- **Evaluation Intent:** *Executive portfolio briefing synthesizing loan book KPIs and operational metrics*

#### Application Response Output:
```text
HEADLINE: Portfolio health
SUMMARY / ANSWER:
Nothing is outside its threshold across 6 indicators.

CHART SPEC: Type=briefing, Title=Portfolio health
```

---

## 3. Architecture & Methodology Notes

1. **Unified Routing (`/api/workbench/ask`):** Every loan book question routes deterministically to the governed `db` source.
2. **Governed SQL Pipeline (`db`):** Queries compile into deterministic `QuerySpec` ASTs and execute against PostgreSQL Gold semantic views without SQL injection risk.
3. **Gold Semantic Alignment:** Covers `gold.loan_account_master`, `gold.loan_disbursement_events`, `gold.loan_repayment_events`, `gold.portfolio_daily_snapshot`, `gold.customer_master`, `gold.product_master`, `gold.branch_master`, `gold.agent_master`, `gold.payment_receipt_events`, `gold.origination_vintage_matrix`, `gold.collection_activity_events`, preset analyses, and worklists.
4. **Zero Cold-Start:** Execution maintains high reliability across 200 consecutive turns.

---
*Report generated by Moneypal Genesis Automated Benchmark Suite (200 Loan Book Queries)*