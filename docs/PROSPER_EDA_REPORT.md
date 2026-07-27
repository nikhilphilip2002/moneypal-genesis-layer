# Prosper Data — Exploratory Data Analysis (EDA) Report

**Source:** Oracle dump `GICCPROD_NEW` (schema `GICCPROD_NEW`, PDB `FREEPDB1`), snapshot as on **30-06-2026**, imported into the local Oracle instance (`192.168.1.183:1521`) per [GENESIS_SPRINT1_BUILD_PLAN.md](file:///home/null/Projects/moneypal/docs/GENESIS_SPRINT1_BUILD_PLAN.md).
**Scope:** This is the source data Genesis DE1 (Ingestion) will parse into the `events` table (`LoanDisbursed`, `RepaymentReceived`, `CustomerOnboarded`, …) per the architecture in the build plan. Findings below feed directly into the Day-1 event taxonomy and Day-4 Data-Quality report deliverables.
**Method:** Direct SQL exploration (`all_tables`, `COUNT`, `GROUP BY`, `MIN/MAX/AVG/SUM`) against the live schema — no sampling.

---

## 1. Schema Landscape & Core Tables

- `GICCPROD_NEW` is a full core-lending-system (Prosper/GICC) schema with **9,545 tables** — a legacy NBFC core banking product (gold/general loans, GL, KYC, collections, migration scaffolding, temp/RTMP staging tables, several years of ad-hoc backup tables with date-stamped suffixes).
- The vast majority of tables are **not relevant** to Genesis — they are historic backups (`*_BK`, `*_HIST`, dated suffixes like `LOANSCHEDULE_28012026`), migration one-offs (`MIG_*`, `RTMP_*`), or unrelated modules (share/demat, penny-drop, VKYC, GL config).
- **Core tables actually populated with this snapshot's live loan book:**

| Table | Row count | Purpose |
|---|---|---|
| `GENLNACNTS` | 13,510 | Loan account master (one row per loan, sanction terms, disbursed/outstanding amounts, closure) |
| `GENLNDISB` | 5,481 | Disbursement transactions (primarily active for Product 16) |
| `LOANSCHEDULE` | 221,460 | Amortization schedule (future + past installments, principal/interest split) |
| `LOANREPAY` | 13,483 | Actual repayment transactions received |

- **Data Gap Observations:** Customer master data (name/KYC) is **not** in a separate customer table in this snapshot (`CUSTDTL` is empty) — the customer name is embedded directly on `GENLNACNTS` (`GNLNAC_CUST_ID`, `GNLNAC_CUST_NAME`), and there is no standalone GL/journal data present. GL/ROI data must come from the **Tally export**, not Prosper.

---

## 2. Canonical Code Dictionary & Reference Mapping

To facilitate the translation of core banking codes into descriptive, business-friendly terms for the event ingestion pipeline, use the following schema mappings:

### A. Product Code Translation (`GNLNAC_PROD_CODE`)

| Product Code | Business Name | Product Description & Operational Status |
|---|---|---|
| **1** | **Gold Loans** | Collateral-backed retail gold loans. Originated at local branches; currently in **run-off status** (no new originations since Oct 2024). |
| **13** | **Microfinance / Retail EMI** | Joint Liability Group (JLG), clean consumer credit, and vehicle retail loans. Centralized at HO; currently in **run-off status** (no new originations since Oct 2024). |
| **16** | **Business & MSME Loans** | Commercial asset-backed and unsecured business lending. Fully **active portfolio** (started Oct 2025). |

### B. Scheme Code Sub-Types (`GNLNAC_SCHM_CODE`)

#### Product 16 (Business / MSME) Schemes
* **1601:** `Purchase of Site` (Commercial site acquisition)
* **1602:** `Repair of House` (Housing renovation loans)
* **1603:** `Purchase of Fixtures & Furniture`
* **1604:** `Purchase of Two Wheelers`
* **1605:** `New Autorikshaw` (Commercial three-wheeler retail)
* **1606:** `Four Wheeler Taxi / Car`
* **1607:** `Tractor` (Agricultural machinery purchase)
* **1608:** `Lorry/Bus New` (Commercial heavy vehicle)
* **1609:** `Used Vehicles Less Than 7 Years`
* **1610:** `Business / Service / Industry` (General MSME working capital)
* **1611:** `Farming` (Agricultural cash flow support)
* **1612:** `Cattle` (Dairy farming retail)
* **1613:** `Poultry / Sheep / Pigs`
* **1614:** `Debt Swapping / Consolidation`
* **1615:** `Loan Against Property` (LAP)

#### Product 13 (Microfinance / Retail EMI) Schemes
* **1342:** `FTG (Flexi-Term Gold) Patharamattu Scheme` (Hybrid gold-backed business facility)
* **1352 / 1353:** `CCF (Consumer Credit Facility) Low ROI Schemes`
* **1354 / 1355 / 1356:** `EV (Electric Vehicle) Retail Schemes` (Subsidized electric auto/two-wheeler lending)
* **All other 13xx codes (e.g. 1328, 1329):** Legacy micro-lending / JLG groups.

#### Product 1 (Gold Loans) Schemes
* **1001:** `Standard Retail Gold Loan`
* **1005:** `High-Value Special Gold Loan`

### C. Loan Repayment Type & Amortization Codes

* **GNLNAC_LOAN_TYPE:**
  * `E` -> **EMI (Equated Monthly Installment) Term Loans:** Loans structured with monthly amortization schedules (principal + interest split over a fixed tenor).
  * `C` -> **Non-EMI demand/bullet loans:** Usually Gold Loans where principal + interest are paid as a lump sum at maturity or on-demand.
* **GNLNAC_EPI_FREQ:**
  * `M` -> **Monthly Installments**
* **GNLNAC_ACRUAL_METHOD:**
  * `2` -> **Monthly Interest Accrual** (Interest is calculated and accrued to the ledger at the end of each calendar month).

### D. Ledger & Transaction Entry Codes

* **Disbursement Mode:**
  * `C` -> **Direct Bank Credit / Transfer** (funds credited directly to client bank account).
* **Ledger Transaction Types (`LNACLEDO_RECOVERY_TYPE`):**
  * `TD` -> **Transaction Debit** (represents a loan disbursement event).
  * `TC` -> **Transaction Credit** (represents a client repayment / collection event).
* **Payment Allocation Fields:**
  * `LNREPAY_PRIN_AMT` / `LNACLEDO_PRINC_OS` -> **Principal portion** of the payment.
  * `LNREPAY_INT_AMT` / `LNACLEDO_INT_OS` -> **Interest portion** of the payment.

### E. Asset Classification & Credit Quality Codes (`ASCD_ASSET_CODE`)

| Code | Status | Meaning & Delinquency Range |
|---|---|---|
| **STD** | Standard | Performing asset. 0 Days Past Due (DPD) or under 30 DPD. |
| **SMA0** | Special Mention Account 0 | Early-stage stress. 1 to 30 Days Past Due (DPD). |
| **SMA1** | Special Mention Account 1 | Medium-stage delinquency. 31 to 60 Days Past Due (DPD). |
| **SMA2** | Special Mention Account 2 | High-stage delinquency. 61 to 90 Days Past Due (DPD). |
| **NPA** | Non-Performing Asset | Over 90 Days Past Due (DPD). Triggers provisioning rules. |

---

## 3. Loan Portfolio Overview (`GENLNACNTS`)

The full loan book consists of **13,510 loan accounts** across **3 distinct products** spanning **16 branches**.

### Portfolio Summary by Product

| Product Code & Name | Loan Count | Total Sanctioned (₹) | Total Disbursed (₹) | Cumulative Principal Repaid (₹) | Outstanding Principal (₹) | Avg Interest Rate |
|---|---|---|---|---|---|---|
| **Product 1:** Gold Loans | 140 | 7,273,419.00 | 7,273,419.00 | 1,648,557.00 | 5,624,862.00 | 17.73% |
| **Product 13:** Microfinance / Retail EMI | 7,715 | 827,404,046.69 | 750,411,319.09 | 111,706,663.76 | 638,704,655.33 | 20.06% |
| **Product 16:** Business / MSME Loans | 5,655 | 2,241,508,902.00 | 2,203,708,902.00 | 95,788,895.24 | 2,107,920,006.76 | 17.73% |
| **Total Portfolio** | **13,510** | **3,076,186,367.69** | **2,961,393,640.09** | **209,144,116.00** | **2,752,249,524.09** | **19.03%** |

---

## 4. Organizational Structure & Branch Distribution

The NBFC's loan operations show a highly structured division of labor across **16 branches**:

| Branch Code & Name | Product 1 (Count) | Product 13 (Count) | Product 16 (Count) | Total Count | Outstanding Portfolio (₹) |
|---|---|---|---|---|---|
| **Branch 1:** HEAD OFFICE | 0 | 7,715 | 88 | 7,803 | 671,727,763.71 |
| **Branch 4:** HEAD OFFICE CREDIT DIVISION | 0 | 0 | 5,567 | 5,567 | 2,074,896,898.38 |
| **Branch 1001:** THRIPUNITHURA | 7 | 0 | 0 | 7 | 805,866.00 |
| **Branch 1002:** ALUVA | 31 | 0 | 0 | 31 | 1,482,420.00 |
| **Branch 1006:** NILAMBUR | 5 | 0 | 0 | 5 | 70,310.00 |
| **Branch 1007:** KOZHIKODE | 2 | 0 | 0 | 2 | 191,770.00 |
| **Branch 1008:** CHALAKUDY | 3 | 0 | 0 | 3 | 0.00 |
| **Branch 1010:** PATHANAMTHITTA | 5 | 0 | 0 | 5 | 589,713.00 |
| **Branch 1012:** KANHANGAD | 8 | 0 | 0 | 8 | 209,985.00 |
| **Branch 1013:** ANGAMALLY | 17 | 0 | 0 | 17 | 225,879.00 |
| **Branch 1014:** KANJIKUZHY | 2 | 0 | 0 | 2 | 52,000.00 |
| **Branch 1016:** KARAMANA | 6 | 0 | 0 | 6 | 43,362.00 |
| **Branch 1017:** GUDALLUR | 6 | 0 | 0 | 6 | 329,900.00 |
| **Branch 1018:** MUVATTUPUZHA | 19 | 0 | 0 | 19 | 741,255.00 |
| **Branch 1020:** KATTAPANA | 17 | 0 | 0 | 17 | 561,505.00 |
| **Branch 1021:** KANJIRAPALLY | 12 | 0 | 0 | 12 | 320,897.00 |
| **Total** | **140** | **7,715** | **5,655** | **13,510** | **2,752,249,524.09** |

### Organizational Insights:
- **Branch 4 (Head Office Credit Division):** Handles all centralized, high-value MSME/Business loans (Product 16) — representing **₹207.5 Cr (75.4%)** of the entire NBFC's outstanding book.
- **Branch 1 (Head Office):** Acts as the centralized hub for the JLG/Microfinance portfolio (Product 13) and contains a legacy pocket of 88 Business Loans.
- **Retail Branches (1001 to 1021):** These 14 branches handle local, retail-level Gold Loans (Product 1) exclusively. None of them originate JLG or Business Loans.

---

## 5. Historical Lifecycle & Growth Trends

A historical analysis of sanction dates reveals that the portfolio has transitioned through three distinct phases, with a **one-year operational gap** in between:

```
Legacy Portfolio Phase (Nov 2023 - Oct 2024)   ===>   Operational Gap (Nov 2024 - Sep 2025)   ===>   MSME Expansion Phase (Oct 2025 - Jun 2026)
- Product 13 (Microfinance / JLG)                     - Zero new loan sanctions                     - Product 16 (Business Loans / MSME)
- Product 1 (Retail Gold Loans)                       - System migration / licensing transition     - Main driver of current loan book
```

### Monthly Sanctions by Product

| Year-Month | Product 1 (Gold) | Product 13 (Microfinance) | Product 16 (Business) |
|---|---|---|---|
| **2023-11** | - | 245 loans / ₹2.77 Cr | - |
| **2023-12** | - | 786 loans / ₹8.76 Cr | - |
| **2024-01** | - | 738 loans / ₹7.92 Cr | - |
| **2024-02** | - | 802 loans / ₹8.63 Cr | - |
| **2024-03** | - | 897 loans / ₹9.67 Cr | - |
| **2024-04** | - | 778 loans / ₹8.36 Cr | - |
| **2024-05** | - | 590 loans / ₹6.24 Cr | - |
| **2024-06** | - | 466 loans / ₹4.88 Cr | - |
| **2024-07** | 13 loans / ₹2.94 L | 541 loans / ₹5.67 Cr | - |
| **2024-08** | 40 loans / ₹18.19 L | 714 loans / ₹7.65 Cr | - |
| **2024-09** | 60 loans / ₹28.77 L | 800 loans / ₹8.48 Cr | - |
| **2024-10** | 27 loans / ₹22.83 L | 358 loans / ₹3.72 Cr | - |
| **2024-11 to 2025-09** | **0** | **0** | **0** |
| **2025-10** | - | - | 21 loans / ₹1.13 Cr |
| **2025-11** | - | - | 143 loans / ₹5.20 Cr |
| **2025-12** | - | - | 380 loans / ₹13.08 Cr |
| **2026-01** | - | - | 560 loans / ₹18.82 Cr |
| **2026-02** | - | - | 628 loans / ₹23.37 Cr |
| **2026-03** | - | - | 832 loans / ₹32.50 Cr |
| **2026-04** | - | - | 922 loans / ₹37.74 Cr |
| **2026-05** | - | - | 1,148 loans / ₹49.13 Cr |
| **2026-06** | - | - | 1,021 loans / ₹43.18 Cr |

- **Operational Insights:** 
  1. The legacy Gold Loan and Microfinance books are in **run-off status**. No new originations have occurred since October 2024.
  2. The **one-year gap** likely represents system migration, corporate restructuring, or transition of the core banking setup prior to launching the Business Loan portfolio in October 2025.
  3. The active Business Loan portfolio has shown steep growth, peaking in May 2026 (1,148 loans, ₹49.1 Cr) before a slight dip in June 2026.

---

## 6. Delinquency & Credit Quality

Asset classification and delinquency (DPD) data are captured dynamically inside the `ASSET_CLASSIFY_DTLS` and `TMP_0206REPY` tables:

| Asset Classification | Delinquency (DPD Range) | Account Count (Product 16) | Outstanding Principal (₹) | % of Product 16 Book |
|---|---|---|---|---|
| **Standard (STD)** | 0 DPD | 5,411 | 2,011,277,807.54 | 95.42% |
| **SMA0** | 1 - 30 DPD | 240 | 94,623,771.34 | 4.49% |
| **SMA1** | 31 - 60 DPD | 3 | 1,583,184.31 | 0.08% |
| **SMA2** | 61 - 90 DPD | 1 | 435,243.57 | 0.02% |
| **NPA (Substandard/Loss)** | >90 DPD | 0 | 0.00 | 0.00% |

- **Insights:** The portfolio demonstrates excellent credit quality, with **95.4%** of the active Business Loan book classified as Standard. Delinquency is concentrated in early-stage SMA0 (4.49%), while only 4 accounts are in advanced delinquency (SMA1/SMA2), and there are **0 NPAs** reported in this cut.
- **Historical Portfolios:** Product 1 and 13 do not have delinquency records in the database, representing a standard (100% performing) book under this migration cut.

---

## 7. Ingestion & Data Quality Recommendations (Sprint 1)

1. **Transaction Table Completeness:** The `LOANREPAY` table only contains active detailed records for the active MSME product (Product 16). For legacy products (Product 1 and 13), historical detailed repayment transactions are archived or not loaded. However, cumulative repayment totals (`GNLNAC_PRI_REPAY_AMT`, `GNLNAC_INT_REPAY_AMT`) are fully preserved in the master table `GENLNACNTS`.
2. **Customer Synthesis:** Customer master tables (`CUSTDTL`) are completely empty in the dump. Ingestion must derive `CustomerOnboarded` events directly from the unique customer IDs (`GNLNAC_CUST_ID`) and names (`GNLNAC_CUST_NAME`) inside the `GENLNACNTS` master table.
3. **Reconciling Duplicate Schedule/Repayment Tables:** The database contains numerous dated tables (e.g. `LOANSCHEDULE_10062026`). Ingestion should strictly target the primary tables `LOANSCHEDULE` and `LOANREPAY` as the authoritative current ledger, as confirmed by our database analysis.
