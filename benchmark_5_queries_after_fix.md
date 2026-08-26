# Moneypal Genesis Intelligence — 5-Query Benchmark & Evaluation Report

**Execution Timestamp:** 2026-08-21 08:03:34 UTC  
**Target Application Endpoint:** `http://100.70.118.31:4321`  
**Environment Configuration:** Production (`.env.prod` timeout settings applied)  
**Total Run Duration:** 422.31 seconds (7.0 minutes)  

---

## 1. Executive Summary & KPIs

| Metric | Result | Benchmark Target | Status |
|---|---|---|---|
| **Total Queries Executed** | **5** | 5 | ✅ Complete |
| **Complete Answers** | **1 / 5** (20.0%) | **≥ 4 (80%)** | **❌ FAIL** |
| **Partial Answers** | **3 / 5** | Reported separately; not counted as accurate | ℹ️ Useful but incomplete |
| **Useful Response Rate** | **4 / 5** (80.0%) | Diagnostic only | ℹ️ Not accuracy |
| **Refused (Governed Safety Policy)** | 0 | < 10% | ℹ️ Handled |
| **Clarifications Triggered** | 0 | < 5% | ℹ️ Handled |
| **Errors / Timeouts** | 1 | < 10% | ⚠️ Review |
| **Average Query Latency** | **84.46s** | < 15.0s | ⚠️ Above target |

### Category Breakdown

| Category | Total Queries | Complete | Partial | Complete Rate (%) | Avg Latency (s) |
|---|---|---|---|---|---|
| **Loan Book** | 0 | 0 / 0 | 0 | 0.0% | 0.00s |
| **Macro** | 0 | 0 / 0 | 0 | 0.0% | 0.00s |
| **Competitive** | 1 | 0 / 1 | 0 | 0.0% | 127.18s |
| **Hybrid** | 4 | 1 / 4 | 3 | 25.0% | 73.78s |
| **General** | 0 | 0 / 0 | 0 | 0.0% | 0.00s |

---

## 2. Detailed Query Execution Log (5 Queries)

### Q056: How do NBFC interest rates on MSME loans compare with co-operative bank rates?

- **Category:** `Competitive`
- **Status:** 🔴 **Error**
- **Latency:** `127.18s`
- **Dispatched Sources:** `competitive`
- **Evaluation Intent:** *Interest rate spread between NBFCs and co-operatives*

#### Application Response Output:
```text
ERROR DETAIL: Request timed out after 120s
```

---

### Q070: How does our gold loan disbursement trend align with macro gold price movements and demand?

- **Category:** `Hybrid`
- **Status:** 🟢 **Answered**
- **Latency:** `131.80s`
- **Dispatched Sources:** `db, macro`
- **Rendered Cards:** `chart`
- **Evaluation Intent:** *Gold loan portfolio growth vs commodity macro trends*

#### Application Response Output:
```text
HEADLINE: Disbursement (all time)
SUMMARY / ANSWER:
No disbursement found in all time with Product eq Gold Loans. This measures sum of disbursement event amounts in the period.

CHART SPEC: Type=kpi, Title=Disbursement
COLUMNS: Disbursement
SAMPLE ROWS (1 total): [{"disbursement_total": null}]
ERROR DETAIL: Request timed out after 120s
```

---

### Q074: How do our portfolio delinquency levels in MSME schemes compare with SIDBI industry benchmarks?

- **Category:** `Hybrid`
- **Status:** 🟡 **Partial**
- **Latency:** `78.86s`
- **Dispatched Sources:** `db, macro`
- **Rendered Cards:** `chart, brief`
- **Evaluation Intent:** *Scheme-wise delinquency vs SIDBI Pulse indicators*
- **Grounded Citations:** *ministry_of_finance, mospi, msme*

#### Application Response Output:
```text
HEADLINE: PAR 30 by scheme (As at 21 Aug 2026)
SUMMARY / ANSWER:
Our Dairy Loan scheme currently reports a PAR 30 of 1.2% as of 21 August 2026, representing the highest level among our MSME schemes. However, a direct comparison with SIDBI industry benchmarks cannot be made because the provided findings do not contain any specific delinquency data or benchmark figures from SIDBI. Consequently, while our internal Dairy Loan metric is identified, the external industry context required for a comparative analysis is missing.

CHART SPEC: Type=bar, Title=PAR 30 by scheme
COLUMNS: Scheme, PAR 30
SAMPLE ROWS (8 total): [{"scheme": "Dairy Loan", "par_30": 1.241914877328521, "scheme__raw": "1622"}, {"scheme": "Loan Against Property (Scheme #1619)", "par_30": 0.9401292302328449, "scheme__raw": "1619"}, {"scheme": "Farming Loan", "par_30": 0.2811763047327321, "scheme__raw": "1621"}]
```

---

### Q076: How does our scheme-wise concentration align with priority sector lending (PSL) guidelines?

- **Category:** `Hybrid`
- **Status:** 🟡 **Partial**
- **Latency:** `49.77s`
- **Dispatched Sources:** `db, regulatory`
- **Rendered Cards:** `chart, brief`
- **Evaluation Intent:** *Portfolio composition vs regulatory PSL norms*
- **Grounded Citations:** *sbr_master_direction_2023.pdf*

#### Application Response Output:
```text
HEADLINE: Principal outstanding by scheme (As at 21 Aug 2026)
SUMMARY / ANSWER:
Our MSME Loans scheme holds the highest principal outstanding at ₹59.81 Cr, representing 29% of the total across 8 schemes as of 21 Aug 2026. However, the provided findings do not contain the specific quantitative thresholds, sectoral definitions, or target percentages required to determine if this concentration aligns with Priority Sector Lending (PSL) guidelines. While the documents confirm that current lending must adhere to Master Directions and prudential norms, they explicitly lack the substantive rules defining those targets. Consequently, a direct comparison between our 29% MSME concentration and regulatory requirements cannot be made with the available data.

CHART SPEC: Type=bar, Title=Principal outstanding by scheme
COLUMNS: Scheme, Principal outstanding
SAMPLE ROWS (8 total): [{"scheme": "MSME Loans", "principal_outstanding": 598093032.27, "scheme__raw": "1616"}, {"scheme": "Site / Housing Construction / House Repair", "principal_outstanding": 417574205.4, "scheme__raw": "1618"}, {"scheme": "Personal Loan", "principal_outstanding": 406744496.01, "scheme__raw": "1617"}]
```

---

### Q079: How does our borrower gender diversity compare with microfinance industry inclusion targets?

- **Category:** `Hybrid`
- **Status:** 🟡 **Partial**
- **Latency:** `34.71s`
- **Dispatched Sources:** `db, macro, competitive`
- **Rendered Cards:** `chart, brief, brief`
- **Evaluation Intent:** *Internal gender inclusion vs regional microfinance averages*
- **Grounded Citations:** *SIDBI, economic_survey*

#### Application Response Output:
```text
HEADLINE: Borrowers by borrower gender (all time)
SUMMARY / ANSWER:
Our borrower gender diversity cannot be directly compared to microfinance industry inclusion targets because the provided evidence does not contain specific industry targets or gender breakdowns for the broader sector. While our institution, M, has the highest borrower count at 3,142 distinct borrowers across three genders, representing 55% of the total, the available data only notes that the sector currently comprises 95% women borrowers without outlining future goals. Consequently, a direct comparison between our lender's specific gender diversity metrics and explicit industry inclusion targets cannot be made with the supplied evidence.

CHART SPEC: Type=donut, Title=Borrowers by borrower gender
COLUMNS: Borrower gender, Borrowers
SAMPLE ROWS (3 total): [{"gender": "M", "customer_count": 3142, "gender__raw": "M"}, {"gender": "F", "customer_count": 2553, "gender__raw": "F"}, {"gender": "Not recorded", "customer_count": 46, "gender__raw": null}]
```

---

## 3. Architecture & Methodology Notes

1. **Unified Routing (`/api/workbench/ask`):** The default score measures only the same unified endpoint used by the application. Optional direct fallbacks are diagnostic and must be explicitly enabled.
2. **Governed SQL Pipeline (`db`):** Loan book queries compiled into deterministic `QuerySpec` contracts and executed against PostgreSQL gold views without SQL injection risk.
3. **Vector Semantic Retrieval (`macro` & `competitive`):** Macro and competitive intelligence leveraged Qdrant vector retrieval (`bge-m3` 1024-dim embeddings) and local synthesis.
4. **Zero Cold-Start:** Execution remained responsive throughout all 100 consecutive turns.

---
*Report generated by Moneypal Genesis Automated Benchmark Suite*