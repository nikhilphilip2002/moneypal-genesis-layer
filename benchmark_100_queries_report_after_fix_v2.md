# Moneypal Genesis Intelligence — 100-Query Benchmark & Evaluation Report

**Execution Timestamp:** 2026-08-21 08:35:06 UTC  
**Target Application Endpoint:** `http://100.70.118.31:4321`  
**Environment Configuration:** Production (`.env.prod` timeout settings applied)  
**Total Run Duration:** 1923.99 seconds (32.1 minutes)  

---

## 1. Executive Summary & KPIs

| Metric | Result | Benchmark Target | Status |
|---|---|---|---|
| **Total Queries Executed** | **100** | 100 | ✅ Complete |
| **Complete Answers** | **65 / 100** (65.0%) | **≥ 70 (70%)** | **❌ FAIL** |
| **Partial Answers** | **34 / 100** | Reported separately; not counted as accurate | ℹ️ Useful but incomplete |
| **Useful Response Rate** | **99 / 100** (99.0%) | Diagnostic only | ℹ️ Not accuracy |
| **Refused (Governed Safety Policy)** | 1 | < 10% | ℹ️ Handled |
| **Clarifications Triggered** | 0 | < 5% | ℹ️ Handled |
| **Errors / Timeouts** | 0 | < 10% | ✅ Zero Errors |
| **Average Query Latency** | **19.24s** | < 15.0s | ⚠️ Above target |

### Category Breakdown

| Category | Total Queries | Complete | Partial | Complete Rate (%) | Avg Latency (s) |
|---|---|---|---|---|---|
| **Loan Book** | 25 | 24 / 25 | 0 | 96.0% | 9.70s |
| **Macro** | 20 | 13 / 20 | 7 | 65.0% | 11.40s |
| **Competitive** | 20 | 10 / 20 | 10 | 50.0% | 17.02s |
| **Hybrid** | 20 | 3 / 20 | 17 | 15.0% | 51.18s |
| **General** | 15 | 15 / 15 | 0 | 100.0% | 5.96s |

---

## 2. Detailed Query Execution Log (100 Queries)

### Q001: What was our total disbursement last quarter?

- **Category:** `Loan Book`
- **Status:** 🟢 **Answered**
- **Latency:** `12.48s`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `chart`
- **Evaluation Intent:** *Single aggregate disbursement KPI for prior quarter*

#### Application Response Output:
```text
HEADLINE: Disbursement (Q2 2026)
SUMMARY / ANSWER:
Disbursement was ₹127.55 Cr in Q2 2026. This measures sum of disbursement event amounts in the period.

CHART SPEC: Type=kpi, Title=Disbursement
COLUMNS: Disbursement
SAMPLE ROWS (1 total): [{"disbursement_total": 1275455902.0}]
```

---

### Q002: What is the total sanctioned amount this financial year?

- **Category:** `Loan Book`
- **Status:** 🟢 **Answered**
- **Latency:** `8.91s`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `chart`
- **Evaluation Intent:** *FYTD sanctioned amount KPI*

#### Application Response Output:
```text
HEADLINE: Sanctioned amount (FY27 to date)
SUMMARY / ANSWER:
Sanctioned amount was ₹138.41 Cr in FY27 to date. This measures sum of sanctioned amounts for accounts sanctioned in the period.

CHART SPEC: Type=kpi, Title=Sanctioned amount
COLUMNS: Sanctioned amount
SAMPLE ROWS (1 total): [{"sanctioned_amount": 1384080902.0}]
```

---

### Q003: What was our disbursement by branch last quarter?

- **Category:** `Loan Book`
- **Status:** 🟢 **Answered**
- **Latency:** `5.70s`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `chart`
- **Evaluation Intent:** *Disbursement breakdown across 16 branches*

#### Application Response Output:
```text
HEADLINE: Disbursement by branch (Q2 2026)
SUMMARY / ANSWER:
Head Office — Credit Division is the only branch returned, with disbursement of ₹127.55 Cr in Q2 2026. This measures sum of disbursement event amounts in the period, grouped by branch.

CHART SPEC: Type=bar, Title=Disbursement by branch
COLUMNS: Branch, Disbursement
SAMPLE ROWS (1 total): [{"branch": "Head Office — Credit Division", "disbursement_total": 1275455902.0, "branch__raw": 4.0}]
```

---

### Q004: Break down the outstanding portfolio by DPD bucket

- **Category:** `Loan Book`
- **Status:** 🟢 **Answered**
- **Latency:** `7.67s`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `chart`
- **Evaluation Intent:** *DPD delinquency distribution (Current, 1-30, 31-60, 61-90, 90+)*

#### Application Response Output:
```text
HEADLINE: Principal outstanding by dpd bucket (As at 21 Aug 2026)
SUMMARY / ANSWER:
0 (current) has the highest principal outstanding, at ₹194.43 Cr as at 21 Aug 2026, 95% of the total across 5 dpd buckets. This measures principal outstanding from each classified account at the requested snapshot, grouped by dpd bucket.

CHART SPEC: Type=donut, Title=Principal outstanding by dpd bucket
COLUMNS: DPD bucket, Principal outstanding
SAMPLE ROWS (5 total): [{"dpd_bucket": "0 (current)", "principal_outstanding": 1944297584.74, "dpd_bucket__raw": "0 (current)"}, {"dpd_bucket": "1-30", "principal_outstanding": 95603973.38, "dpd_bucket__raw": "1-30"}, {"dpd_bucket": "31-60", "principal_outstanding": 4895028.14, "dpd_bucket__raw": "31-60"}]
```

---

### Q005: Show loan count by product type

- **Category:** `Loan Book`
- **Status:** 🟢 **Answered**
- **Latency:** `3.52s`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `chart`
- **Evaluation Intent:** *Distribution of loan counts by product code*

#### Application Response Output:
```text
HEADLINE: Loans sanctioned by product (all time)
SUMMARY / ANSWER:
Business & MSME Loans is the only product returned, with 5,753 loans sanctioned in all time. This measures count of loan accounts sanctioned in the period, grouped by product.

CHART SPEC: Type=bar, Title=Loans sanctioned by product
COLUMNS: Product, Loans sanctioned
SAMPLE ROWS (1 total): [{"product": "Business & MSME Loans", "loan_count": 5753, "product__raw": 16.0}]
```

---

### Q006: Show me the disbursement trend over the last 12 months

- **Category:** `Loan Book`
- **Status:** 🟢 **Answered**
- **Latency:** `4.97s`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `chart`
- **Evaluation Intent:** *12-month monthly disbursement time-series*

#### Application Response Output:
```text
HEADLINE: Disbursement by month (last 12 months)
SUMMARY / ANSWER:
Disbursement rose from ₹59.50 L (Oct 2025) to ₹9.62 Cr (Jul 2026), a change of 1516.0%. This measures sum of disbursement event amounts in the period, grouped by month.

CHART SPEC: Type=area, Title=Disbursement by month
COLUMNS: Month, Disbursement
SAMPLE ROWS (10 total): [{"month": "Oct 2025", "disbursement_total": 5950000.0, "month__raw": "2025-10-01"}, {"month": "Nov 2025", "disbursement_total": 28000000.0, "month__raw": "2025-11-01"}, {"month": "Dec 2025", "disbursement_total": 88360000.0, "month__raw": "2025-12-01"}]
```

---

### Q007: How has PAR 30 moved over the last three months?

- **Category:** `Loan Book`
- **Status:** 🟢 **Answered**
- **Latency:** `7.62s`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `chart`
- **Evaluation Intent:** *Portfolio at Risk > 30 days trend over 90 days*

#### Application Response Output:
```text
HEADLINE: PAR 30 by month (As at 31 Jul 2026)
SUMMARY / ANSWER:
PAR 30 fell from 1.2% (May 2026) to 0.27% (Jul 2026), a change of 78.1%. This measures principal outstanding over 30 DPD divided by classified principal outstanding, grouped by month. Definition of PAR 30 is pending client sign-off.

CHART SPEC: Type=line, Title=PAR 30 by month
COLUMNS: Month, PAR 30
SAMPLE ROWS (3 total): [{"month": "May 2026", "par_30": 1.2236990803010663, "month__raw": "2026-05-01"}, {"month": "Jun 2026", "par_30": 0.08999595283058374, "month__raw": "2026-06-01"}, {"month": "Jul 2026", "par_30": 0.26855264734033535, "month__raw": "2026-07-01"}]
```

---

### Q008: Which branches disbursed the most last quarter?

- **Category:** `Loan Book`
- **Status:** 🟢 **Answered**
- **Latency:** `4.00s`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `chart`
- **Evaluation Intent:** *Branch ranking by total disbursed volume*

#### Application Response Output:
```text
HEADLINE: Disbursement by branch (Q2 2026)
SUMMARY / ANSWER:
Head Office — Credit Division is the only branch returned, with disbursement of ₹127.55 Cr in Q2 2026. This measures sum of disbursement event amounts in the period, grouped by branch.

CHART SPEC: Type=bar, Title=Disbursement by branch
COLUMNS: Branch, Disbursement
SAMPLE ROWS (1 total): [{"branch": "Head Office — Credit Division", "disbursement_total": 1275455902.0, "branch__raw": 4.0}]
```

---

### Q009: Top 10 schemes by sanctioned amount

- **Category:** `Loan Book`
- **Status:** 🟢 **Answered**
- **Latency:** `4.61s`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `chart`
- **Evaluation Intent:** *Scheme-level ranking by total sanctions*

#### Application Response Output:
```text
HEADLINE: Sanctioned amount by scheme (all time)
SUMMARY / ANSWER:
MSME Loans has the highest sanctioned amount, at ₹65.47 Cr in all time, 29% of the total across 10 schemes. This measures sum of sanctioned amounts for accounts sanctioned in the period, grouped by scheme.

CHART SPEC: Type=bar, Title=Sanctioned amount by scheme
COLUMNS: Scheme, Sanctioned amount
SAMPLE ROWS (10 total): [{"scheme": "MSME Loans", "sanctioned_amount": 654710000.0, "scheme__raw": "1616"}, {"scheme": "Site / Housing Construction / House Repair", "sanctioned_amount": 457645000.0, "scheme__raw": "1618"}, {"scheme": "Personal Loan", "sanctioned_amount": 439308000.0, "scheme__raw": "1617"}]
```

---

### Q010: Which branches have the lowest collection efficiency?

- **Category:** `Loan Book`
- **Status:** 🟢 **Answered**
- **Latency:** `4.91s`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `chart`
- **Evaluation Intent:** *Underperforming branch ranking by collection efficiency*

#### Application Response Output:
```text
HEADLINE: Collection efficiency by branch (FY27 to date)
SUMMARY / ANSWER:
Head Office — Credit Division is the only branch returned, with collection efficiency of 98.5% in FY27 to date. This measures total principal and interest paid divided by total principal and interest due, grouped by branch.

CHART SPEC: Type=bar, Title=Collection efficiency by branch
COLUMNS: Branch, Collection efficiency
SAMPLE ROWS (1 total): [{"branch": "Head Office — Credit Division", "collection_efficiency": 98.54437200622546, "branch__raw": 4.0}]
```

---

### Q011: How much have we disbursed in gold loans?

- **Category:** `Loan Book`
- **Status:** 🟢 **Answered**
- **Latency:** `0.78s`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `chart`
- **Evaluation Intent:** *Product code 1 (Gold Loans) total disbursement*

#### Application Response Output:
```text
HEADLINE: Disbursement (all time)
SUMMARY / ANSWER:
No disbursement found in all time with Product eq Gold Loans. This measures sum of disbursement event amounts in the period.

CHART SPEC: Type=kpi, Title=Disbursement
COLUMNS: Disbursement
SAMPLE ROWS (1 total): [{"disbursement_total": null}]
```

---

### Q012: Show MSME loans by branch

- **Category:** `Loan Book`
- **Status:** 🟡 **Refused**
- **Latency:** `75.41s`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `refusal`
- **Evaluation Intent:** *Product code 16 (Business/MSME) loan count across branches*

#### Application Response Output:
```text
SUMMARY / ANSWER:
I could not answer that safely from the available data.
```

---

### Q013: What is our current PAR 30?

- **Category:** `Loan Book`
- **Status:** 🟢 **Answered**
- **Latency:** `41.18s`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `chart`
- **Evaluation Intent:** *Current point-in-time PAR 30 percentage*

#### Application Response Output:
```text
HEADLINE: PAR 30 (As at 21 Aug 2026)
SUMMARY / ANSWER:
PAR 30 was 0.27% as at 21 Aug 2026. This measures principal outstanding over 30 DPD divided by classified principal outstanding. Definition of PAR 30 is pending client sign-off.

CHART SPEC: Type=kpi, Title=PAR 30
COLUMNS: PAR 30
SAMPLE ROWS (1 total): [{"par_30": 0.26855264734033535}]
```

---

### Q014: What is the NPA ratio right now?

- **Category:** `Loan Book`
- **Status:** 🟢 **Answered**
- **Latency:** `3.98s`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `chart`
- **Evaluation Intent:** *Current Non-Performing Asset ratio*

#### Application Response Output:
```text
HEADLINE: NPA ratio (As at 21 Aug 2026)
SUMMARY / ANSWER:
NPA ratio was 0.02% as at 21 Aug 2026. This measures nPA-classified principal outstanding divided by classified principal outstanding. Definition of NPA ratio is pending client sign-off.

CHART SPEC: Type=kpi, Title=NPA ratio
COLUMNS: NPA ratio
SAMPLE ROWS (1 total): [{"npa_ratio": 0.02008484359049893}]
```

---

### Q015: What is the total principal outstanding across all active accounts?

- **Category:** `Loan Book`
- **Status:** 🟢 **Answered**
- **Latency:** `6.15s`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `chart`
- **Evaluation Intent:** *Total active portfolio principal balance*

#### Application Response Output:
```text
HEADLINE: Principal outstanding (whole book) (2026-08-21)
SUMMARY / ANSWER:
Principal outstanding (whole book) was ₹214.00 Cr in 2026-08-21. This measures cumulative disbursed minus cumulative principal repaid across loan accounts.

CHART SPEC: Type=kpi, Title=Principal outstanding (whole book)
COLUMNS: Principal outstanding (whole book)
SAMPLE ROWS (1 total): [{"principal_outstanding_book": 2139981490.94}]
```

---

### Q016: Show collection efficiency by product this financial year

- **Category:** `Loan Book`
- **Status:** 🟢 **Answered**
- **Latency:** `6.44s`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `chart`
- **Evaluation Intent:** *Product-level collection efficiency breakdown*

#### Application Response Output:
```text
HEADLINE: Collection efficiency by product (FY27 to date)
SUMMARY / ANSWER:
Business & MSME Loans is the only product returned, with collection efficiency of 98.5% in FY27 to date. This measures total principal and interest paid divided by total principal and interest due, grouped by product.

CHART SPEC: Type=bar, Title=Collection efficiency by product
COLUMNS: Product, Collection efficiency
SAMPLE ROWS (1 total): [{"product": "Business & MSME Loans", "collection_efficiency": 98.54437200622546, "product__raw": 16.0}]
```

---

### Q017: How many loans did we sanction each month in FY26?

- **Category:** `Loan Book`
- **Status:** 🟢 **Answered**
- **Latency:** `5.84s`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `chart`
- **Evaluation Intent:** *Monthly sanction count time-series*

#### Application Response Output:
```text
HEADLINE: Loans sanctioned by month (2025-04-01 to 2026-03-31)
SUMMARY / ANSWER:
Loans sanctioned rose from 13 (Oct 2025) to 832 (Mar 2026), a change of 6300.0%. This measures count of loan accounts sanctioned in the period, grouped by month.

CHART SPEC: Type=area, Title=Loans sanctioned by month
COLUMNS: Month, Loans sanctioned
SAMPLE ROWS (6 total): [{"month": "Oct 2025", "loan_count": 13, "month__raw": "2025-10-01"}, {"month": "Nov 2025", "loan_count": 87, "month__raw": "2025-11-01"}, {"month": "Dec 2025", "loan_count": 365, "month__raw": "2025-12-01"}]
```

---

### Q018: Which schemes have the largest outstanding balance?

- **Category:** `Loan Book`
- **Status:** 🟢 **Answered**
- **Latency:** `3.99s`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `chart`
- **Evaluation Intent:** *Ranking schemes by current principal outstanding*

#### Application Response Output:
```text
HEADLINE: Principal outstanding by scheme (As at 21 Aug 2026)
SUMMARY / ANSWER:
MSME Loans has the highest principal outstanding, at ₹59.81 Cr as at 21 Aug 2026, 29% of the total across 8 schemes. This measures principal outstanding from each classified account at the requested snapshot, grouped by scheme.

CHART SPEC: Type=bar, Title=Principal outstanding by scheme
COLUMNS: Scheme, Principal outstanding
SAMPLE ROWS (8 total): [{"scheme": "MSME Loans", "principal_outstanding": 598093032.27, "scheme__raw": "1616"}, {"scheme": "Site / Housing Construction / House Repair", "principal_outstanding": 417574205.4, "scheme__raw": "1618"}, {"scheme": "Personal Loan", "principal_outstanding": 406744496.01, "scheme__raw": "1617"}]
```

---

### Q019: What is the total repayment amount collected in the last 30 days?

- **Category:** `Loan Book`
- **Status:** 🟢 **Answered**
- **Latency:** `4.61s`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `chart`
- **Evaluation Intent:** *Recent 30-day repayment collection total*

#### Application Response Output:
```text
HEADLINE: Amount collected (last 30 days)
SUMMARY / ANSWER:
Amount collected was ₹1.73 Cr in last 30 days. This measures principal plus interest paid in the period.

CHART SPEC: Type=kpi, Title=Amount collected
COLUMNS: Amount collected
SAMPLE ROWS (1 total): [{"amount_collected": 17325611.66}]
```

---

### Q020: Show the distribution of active loan accounts by asset classification

- **Category:** `Loan Book`
- **Status:** 🟢 **Answered**
- **Latency:** `7.06s`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `chart`
- **Evaluation Intent:** *Standard vs Sub-standard vs NPA asset code distribution*

#### Application Response Output:
```text
HEADLINE: Principal outstanding by asset classification (As at 21 Aug 2026)
SUMMARY / ANSWER:
Standard has the highest principal outstanding, at ₹194.43 Cr as at 21 Aug 2026, 95% of the total across 5 asset classifications. This measures principal outstanding from each classified account at the requested snapshot, grouped by asset classification.

CHART SPEC: Type=donut, Title=Principal outstanding by asset classification
COLUMNS: Asset classification, Principal outstanding
SAMPLE ROWS (5 total): [{"asset_class": "Standard", "principal_outstanding": 1944297584.74, "asset_class__raw": "STD"}, {"asset_class": "SMA-0", "principal_outstanding": 95603973.38, "asset_class__raw": "SMA0"}, {"asset_class": "SMA-1", "principal_outstanding": 4895028.14, "asset_class__raw": "SMA1"}]
```

---

### Q021: What is the average sanctioned loan amount across all branches?

- **Category:** `Loan Book`
- **Status:** 🟢 **Answered**
- **Latency:** `6.39s`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `chart`
- **Evaluation Intent:** *Average ticket size of sanctioned loans*

#### Application Response Output:
```text
HEADLINE: Average ticket size by branch (all time)
SUMMARY / ANSWER:
Head Office — Credit Division has the highest average ticket size, at ₹3.98 L in all time, 54% of the total across 2 branches. This measures total sanctioned amount divided by number of loans, grouped by branch.

CHART SPEC: Type=bar, Title=Average ticket size by branch
COLUMNS: Branch, Average ticket size
SAMPLE ROWS (2 total): [{"branch": "Head Office — Credit Division", "avg_ticket_size": 398287.3132613992, "branch__raw": 4.0}, {"branch": "Head Office", "avg_ticket_size": 342857.14285714284, "branch__raw": 1.0}]
```

---

### Q022: Break down the overdue principal amount by branch

- **Category:** `Loan Book`
- **Status:** 🟢 **Answered**
- **Latency:** `4.05s`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `chart`
- **Evaluation Intent:** *Delinquent principal amount by branch*

#### Application Response Output:
```text
HEADLINE: Overdue principal by branch (As at 21 Aug 2026)
SUMMARY / ANSWER:
Head Office — Credit Division is the only branch returned, with overdue principal of ₹19.57 L as at 21 Aug 2026. This measures principal overdue at the requested portfolio snapshot, grouped by branch.

CHART SPEC: Type=bar, Title=Overdue principal by branch
COLUMNS: Branch, Overdue principal
SAMPLE ROWS (1 total): [{"branch": "Head Office — Credit Division", "overdue_principal": 1957196.06, "branch__raw": 4.0}]
```

---

### Q023: What is the count of female borrowers versus male borrowers in our portfolio?

- **Category:** `Loan Book`
- **Status:** 🟢 **Answered**
- **Latency:** `0.62s`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `chart`
- **Evaluation Intent:** *Gender breakdown of borrower base*

#### Application Response Output:
```text
HEADLINE: Borrowers by borrower gender (all time)
SUMMARY / ANSWER:
M has the highest borrowers, at 3,142 in all time, 55% of the total across 3 borrower genders. This measures distinct borrowers with an account sanctioned in the period, grouped by borrower gender.

CHART SPEC: Type=donut, Title=Borrowers by borrower gender
COLUMNS: Borrower gender, Borrowers
SAMPLE ROWS (3 total): [{"gender": "M", "customer_count": 3142, "gender__raw": "M"}, {"gender": "F", "customer_count": 2553, "gender__raw": "F"}, {"gender": "Not recorded", "customer_count": 46, "gender__raw": null}]
```

---

### Q024: List the top 5 branches by total principal outstanding

- **Category:** `Loan Book`
- **Status:** 🟢 **Answered**
- **Latency:** `4.60s`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `chart`
- **Evaluation Intent:** *Top 5 branches managing the largest portfolio volume*

#### Application Response Output:
```text
HEADLINE: Principal outstanding by branch (As at 21 Aug 2026)
SUMMARY / ANSWER:
Head Office — Credit Division is the only branch returned, with principal outstanding of ₹204.54 Cr as at 21 Aug 2026. This measures principal outstanding from each classified account at the requested snapshot, grouped by branch.

CHART SPEC: Type=bar, Title=Principal outstanding by branch
COLUMNS: Branch, Principal outstanding
SAMPLE ROWS (1 total): [{"branch": "Head Office — Credit Division", "principal_outstanding": 2045394519.25, "branch__raw": 4.0}]
```

---

### Q025: What is the total interest amount collected this financial year?

- **Category:** `Loan Book`
- **Status:** 🟢 **Answered**
- **Latency:** `7.07s`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `chart`
- **Evaluation Intent:** *FYTD interest income collected*

#### Application Response Output:
```text
HEADLINE: Interest collected (FY27 to date)
SUMMARY / ANSWER:
Interest collected was ₹8.56 Cr in FY27 to date. This measures interest paid in the period.

CHART SPEC: Type=kpi, Title=Interest collected
COLUMNS: Interest collected
SAMPLE ROWS (1 total): [{"interest_collected": 85557259.16}]
```

---

### Q026: What is the projected real GDP growth rate for India according to the Economic Survey?

- **Category:** `Macro`
- **Status:** 🟢 **Answered**
- **Latency:** `9.53s`
- **Dispatched Sources:** `macro`
- **Rendered Cards:** `brief`
- **Evaluation Intent:** *India real GDP growth projection*
- **Grounded Citations:** *mospi*

#### Application Response Output:
```text
SUMMARY / ANSWER:
According to the provided context from the Economic Survey (mospi, p.4), the projected real GDP growth rate for India in the fiscal year 2025-26 is estimated at 7.7%. This represents an increase compared to the 7.1% growth rate recorded in 2024-25. The document further notes that Real GDP is expected to reach ₹323.12 lakh crore in 2025-26, up from ₹299.89 lakh crore in the previous year.
```

---

### Q027: What are the key drivers of India's current economic expansion?

- **Category:** `Macro`
- **Status:** 🟢 **Answered**
- **Latency:** `11.67s`
- **Dispatched Sources:** `macro`
- **Rendered Cards:** `brief`
- **Evaluation Intent:** *Drivers of macroeconomic growth and capital formation*
- **Grounded Citations:** *economic_survey*

#### Application Response Output:
```text
SUMMARY / ANSWER:
India's current economic expansion is driven by robust domestic demand and strengthened supply-side momentum. Domestic demand anchors growth, supported by a surge in Gross Fixed Capital Formation (GFCF) at 7.6% in H1 FY26 [economic_survey, p.60]. On the supply side, manufacturing activity has gained significant traction, with growth accelerating to 8.4% in H1 FY26 compared to 4.8% in the prior year [economic_survey, p.60]. Services continue to lead overall expansion, particularly in trade, transport, and financial and professional services, which recorded 9.9% growth in H1 FY26 [economic_survey, p.60]. These factors collectively propelled real GDP growth to 7.4% in the First Advance Estimates for FY26 [economic_survey, p.60].
```

---

### Q028: What is the current CPI inflation trend and headline inflation outlook?

- **Category:** `Macro`
- **Status:** 🟡 **Partial**
- **Latency:** `13.38s`
- **Dispatched Sources:** `macro`
- **Rendered Cards:** `brief`
- **Evaluation Intent:** *Consumer price index inflation trends*
- **Grounded Citations:** *economic_survey, rbi*

#### Application Response Output:
```text
SUMMARY / ANSWER:
Based on the provided context, headline inflation in India reached 1.7% for the April–December 2025 period, marking the lowest rate since the beginning of the CPI series [economic_survey, p.16]. This decline was driven by subdued food inflation, with India recording the highest reduction (1.8%) in headline inflation among major economies in 2025 [economic_survey, p.16]. While the document notes a broad-based rise in CPI-Food and Beverages during May 2026 attributed to seasonal summer trends [rbi, p.45], it does not provide a specific current headline inflation figure for June 2026 or a forward-looking outlook beyond the stated 2025 reduction. The text indicates that within foodgrains, prices of rice, wheat, and major pulses recorded an uptick as of mid-June 2026 [rbi, p.45].
```

---

### Q029: How are food and fuel prices impacting overall inflation in India?

- **Category:** `Macro`
- **Status:** 🟢 **Answered**
- **Latency:** `11.53s`
- **Dispatched Sources:** `macro`
- **Rendered Cards:** `brief`
- **Evaluation Intent:** *Food and energy inflation contribution*
- **Grounded Citations:** *karnataka_des*

#### Application Response Output:
```text
SUMMARY / ANSWER:
Food and fuel prices impact overall inflation differently depending on the index used, as their weights vary significantly. Food items carry a higher weight in the Consumer Price Index (CPI), making it more sensitive to food price changes, whereas the fuel group has a significantly higher weight in the Wholesale Price Index (WPI) compared to the CPI [karnataka_des, p.55]. Consequently, while All-India WPI inflation rose to 1.82 per cent in April-December 2025-26, driven largely by fuel components, All-India CPI inflation increased to 3.28 per cent during the same period, reflecting the broader impact of food prices on consumer costs [karnataka_des, p.55]. This divergence highlights how shifts in these specific sectors drive inflation differently at wholesale versus retail levels.
```

---

### Q030: What is the RBI's current monetary policy stance and repo rate outlook?

- **Category:** `Macro`
- **Status:** 🟢 **Answered**
- **Latency:** `15.96s`
- **Dispatched Sources:** `macro`
- **Rendered Cards:** `brief`
- **Evaluation Intent:** *RBI monetary policy stance and interest rates*
- **Grounded Citations:** *economic_survey, rbi*

#### Application Response Output:
```text
SUMMARY / ANSWER:
Based on the provided context, the RBI has adopted a **neutral monetary policy stance**, a position maintained since June 2025 [economic_survey, p.138]. The policy repo rate under the Liquidity Adjustment Facility (LAF) is currently **unchanged at 5.25 per cent** [rbi, p.9]. Consequently, the Standing Deposit Facility (SDF) rate remains at 5.00 per cent, while the Marginal Standing Facility (MSF) rate and Bank Rate are set at 5.50 per cent [rbi, p.9]. The Monetary Policy Committee (MPC) reached this decision unanimously during its June 2026 meeting, citing a deteriorating global environment, supply chain disruptions, and elevated energy prices as key factors influencing the outlook [rbi, p.9]. While headline inflation is projected to firm up towards the upper tolerance level in Q3 2026-27, underlying inflation pressures remain benign, though the MPC warns of potential second-round effects on wages and expectations [rbi, p.9].
```

---

### Q031: How is credit growth trending in the Indian banking and NBFC sectors?

- **Category:** `Macro`
- **Status:** 🟢 **Answered**
- **Latency:** `22.12s`
- **Dispatched Sources:** `macro`
- **Rendered Cards:** `brief`
- **Evaluation Intent:** *Sectoral bank and NBFC credit growth*
- **Grounded Citations:** *economic_survey, rbi*

#### Application Response Output:
```text
SUMMARY / ANSWER:
Credit growth in the Indian banking and NBFC sectors is trending robustly, particularly within the MSME segment. Bank credit to micro and small enterprises grew by 30.1% year-on-year as of April 2026 (rbi, p.77), driven by sustained momentum and regulatory measures like revised gold pledge guidelines (economic_survey, p.145). While overall non-food bank credit contracted slightly at -0.9% (rbi, p.77), credit to NBFCs expanded significantly by 27.7% (rbi, p.77), buoyed by lending to trade, commercial real estate, and services (rbi, p.52). Total flow of resources to the commercial sector surged 44.7% year-on-year in FY26, with non-bank sources rising 23.8% (economic_survey, p.145). Personal loans also showed strength, with gold loans surging 121.2% (rbi, p.77). Overall, credit growth is outpacing deposit growth since September 2025, fueled by large industries and the services sector (rbi, p.52).
```

---

### Q032: What is the credit gap for MSMEs in India according to government reports?

- **Category:** `Macro`
- **Status:** 🟡 **Partial**
- **Latency:** `7.99s`
- **Dispatched Sources:** `macro`
- **Rendered Cards:** `brief`
- **Evaluation Intent:** *MSME formal financing gap*
- **Grounded Citations:** *msme*

#### Application Response Output:
```text
SUMMARY / ANSWER:
The provided context does not contain information regarding the specific credit gap for MSMEs in India. While the text details the Credit Guarantee Fund Trust for MSE (CGTMSE) achievements, such as ₹ 12.39 lakh crore in extended guarantees (p.93), and outlines the MSME sector's contribution to GDP and exports (p.7), it does not quantify the outstanding credit gap or funding shortfall faced by these enterprises.
```

---

### Q033: What are the major challenges faced by micro and small enterprises in accessing formal credit?

- **Category:** `Macro`
- **Status:** 🟢 **Answered**
- **Latency:** `8.70s`
- **Dispatched Sources:** `macro`
- **Rendered Cards:** `brief`
- **Evaluation Intent:** *MSME credit barriers and collateral constraints*
- **Grounded Citations:** *economic_survey*

#### Application Response Output:
```text
SUMMARY / ANSWER:
Based on the provided context, major challenges for microfinance institutions (MFIs) serving micro and small enterprises include the limited availability of a primary, standardized approach to assess household income, forcing reliance on in-house estimation methods that may lack accuracy. Additionally, MFIs often lack visibility over specific loan types like gold, agricultural, and cooperative society credit, which constrains their ability to calculate accurate repayment obligations. The sector also struggles with offering tailored credit with differential pricing for different categories. While stress in the sector has tempered due to regulatory action, continued growth hinges on strengthening enabling infrastructure for creditworthiness assessment and ensuring responsible lending practices.
```

---

### Q034: What is Karnataka's Gross State Domestic Product (GSDP) growth performance?

- **Category:** `Macro`
- **Status:** 🟢 **Answered**
- **Latency:** `9.75s`
- **Dispatched Sources:** `macro`
- **Rendered Cards:** `brief`
- **Evaluation Intent:** *Karnataka state-level GDP and growth rate*
- **Grounded Citations:** *karnataka_des*

#### Application Response Output:
```text
SUMMARY / ANSWER:
Based on the provided context, Karnataka's Gross State Domestic Product (GSDP) growth performance for the year 2025-26 is estimated at 12.9 per cent. This figure is derived from Advance Estimates indicating a total GSDP of Rs.32,81,065 crore at current prices [karnataka_des, p.42]. The document notes that overall economic growth is determined by the performance of the Agriculture, Industry, and Services sectors, though specific sectoral growth rates for 2025-26 are not detailed in the text [karnataka_des, p.42].
```

---

### Q035: How is the MSME sector positioned in Karnataka's regional economy?

- **Category:** `Macro`
- **Status:** 🟢 **Answered**
- **Latency:** `13.44s`
- **Dispatched Sources:** `macro`
- **Rendered Cards:** `brief`
- **Evaluation Intent:** *Karnataka MSME employment and enterprise share*
- **Grounded Citations:** *karnataka_des*

#### Application Response Output:
```text
SUMMARY / ANSWER:
The MSME sector serves as a vital pillar of Karnataka's economy, with 24.86 lakh enterprises registered on the Udyam Portal as of December 31, 2025, generating employment for 235.27 lakh persons [karnataka_des, p.151]. Financial support is substantial, with Rs.69,211.08 lakh allocated for the 2025-26 fiscal year, of which Rs.28,442.84 lakh was utilized by December 2025 [karnataka_des, p.151]. This funding targets capital and interest subsidies, SCSP, TSP schemes, and cluster development to aid artisans and traditional sectors [karnataka_des, p.151]. While the state also pursues major investments in large and medium industries under the Clean Mobility Policy 2025-30, the MSME sector remains central to the state's economic structure through its extensive reach and employment generation [karnataka_des, p.151].
```

---

### Q036: What are the key findings from the SIDBI MSME Pulse report?

- **Category:** `Macro`
- **Status:** 🟡 **Partial**
- **Latency:** `10.60s`
- **Dispatched Sources:** `macro`
- **Rendered Cards:** `brief`
- **Evaluation Intent:** *SIDBI MSME credit quality and ticket size findings*
- **Grounded Citations:** *msme*

#### Application Response Output:
```text
SUMMARY / ANSWER:
The provided context does not contain key findings from a "SIDBI MSME Pulse report." Instead, it details government initiatives and portal data: the MSME Sambandh Portal shows 40.77% of ₹1,35,770.63 crore procurement from 129 CPSEs went to 161,950 MSEs (p.15); GeM data indicates 22.5 lakh MSE sellers contributed 38.21% of order value (p.15); and the Aatmanirbhar Bharat package included a ₹50,000 crore equity infusion via the Self Reliant India Fund (p.15). No specific SIDBI Pulse report findings are mentioned in the text.
```

---

### Q037: What is the formal versus informal credit split in Indian MSME financing?

- **Category:** `Macro`
- **Status:** 🟡 **Partial**
- **Latency:** `5.73s`
- **Dispatched Sources:** `macro`
- **Rendered Cards:** `brief`
- **Evaluation Intent:** *Institutional vs unorganized credit share*
- **Grounded Citations:** *msme*

#### Application Response Output:
```text
SUMMARY / ANSWER:
The provided context does not contain information regarding the formal versus informal credit split in Indian MSME financing. While the text mentions that the Ministry of MSME focuses on "Access to Credit" and "Formalization" as key objectives, it does not offer specific data, percentages, or a breakdown of the formal versus informal credit distribution within the sector.
```

---

### Q038: How is digital public infrastructure (DPI) influencing MSME credit delivery in India?

- **Category:** `Macro`
- **Status:** 🟢 **Answered**
- **Latency:** `10.44s`
- **Dispatched Sources:** `macro`
- **Rendered Cards:** `brief`
- **Evaluation Intent:** *Account Aggregator, OCEN, and UPI lending impact*
- **Grounded Citations:** *economic_survey*

#### Application Response Output:
```text
SUMMARY / ANSWER:
Digital Public Infrastructure (DPI) significantly enhances MSME credit delivery by enabling data-driven lending to underserved segments. The account aggregator framework supplies lenders with verified data, such as bank transactions and GST records, facilitating credit access for first-time users. Additionally, DPI payment interfaces like UPI provide transaction data that allows lenders to assess creditworthiness effectively. This infrastructure supports schemes like PM SVANidhi and PMMY, which have expanded formal credit access to 30% of borrowers and maintained low NPA rates of below 10% and 3.31%, respectively. By converting basic account access into active financial participation, DPI fosters a virtuous cycle of credit access, repayment discipline, and enterprise growth, integrating traditionally unbankable populations into the formal financial system.
```

---

### Q039: What is the trend in industrial output and manufacturing PMI in India?

- **Category:** `Macro`
- **Status:** 🟡 **Partial**
- **Latency:** `13.52s`
- **Dispatched Sources:** `macro`
- **Rendered Cards:** `brief`
- **Evaluation Intent:** *Index of Industrial Production and manufacturing activity*
- **Grounded Citations:** *mospi, rbi*

#### Application Response Output:
```text
SUMMARY / ANSWER:
In May 2026, India's industrial output showed robust growth, with the Index of Industrial Production (IIP) rising 5.1% year-on-year, driven by a 5.5% expansion in the manufacturing sector [mospi, p.1]. Concurrently, the manufacturing output price PMI moderated sequentially in May, indicating a potential squeeze on profit margins despite elevated input costs [rbi, p.48]. While the text does not provide a specific numerical value for the manufacturing activity PMI, it notes that input price PMI remained stable at elevated levels, reflecting high costs for energy and raw materials [rbi, p.48]. The services sector PMI for both output and input prices also moderated but remained in the expansionary zone [rbi, p.48]. Overall, industrial output is expanding, though manufacturing firms face margin pressures from rising input prices.
```

---

### Q040: What are the key government initiatives supporting MSME credit access in India?

- **Category:** `Macro`
- **Status:** 🟢 **Answered**
- **Latency:** `9.83s`
- **Dispatched Sources:** `macro`
- **Rendered Cards:** `brief`
- **Evaluation Intent:** *Credit guarantee and interest subvention schemes*
- **Grounded Citations:** *msme*

#### Application Response Output:
```text
SUMMARY / ANSWER:
The government supports MSME credit access primarily through the **PM Vishwakarma Scheme**, launched in September 2023 with an initial outlay of ₹ 13,000 crore to provide holistic financial and skill support to artisans [msme, p.86]. Broader strategic objectives include ensuring "Access to Credit" and "Access to Finance" as core pillars of the Ministry's vision to foster inclusive growth and address challenges like inadequate skilling [msme, p.7]. While the text confirms these initiatives aim to meet operational and expansion needs, it does not list other specific credit schemes beyond the PM Vishwakarma program in the provided excerpts.
```

---

### Q041: How does rising rural demand support credit absorption in southern states?

- **Category:** `Macro`
- **Status:** 🟡 **Partial**
- **Latency:** `9.21s`
- **Dispatched Sources:** `macro`
- **Rendered Cards:** `brief`
- **Evaluation Intent:** *Rural economy, monsoon, and southern credit trends*
- **Grounded Citations:** *economic_survey*

#### Application Response Output:
```text
SUMMARY / ANSWER:
The provided context does not contain information regarding how rising rural demand specifically supports credit absorption in southern states. While the text notes that Regional Rural Banks (RRBs) serve rural and semi-urban areas in southern states like Karnataka by providing credit to farmers and small industries, it attributes their improved credit absorption to structural reforms such as consolidation into 28 banks and IT integration, rather than explicitly linking it to rising demand. The text highlights a record net profit of ₹7.6 thousand crore in FY24 and a decline in the GNPA ratio from 6.1% to 5.4% in FY25, but does not explain the causal mechanism of rising demand driving these outcomes.
```

---

### Q042: What is the economic outlook for co-operative banking in rural and semi-urban India?

- **Category:** `Macro`
- **Status:** 🟢 **Answered**
- **Latency:** `11.67s`
- **Dispatched Sources:** `macro`
- **Rendered Cards:** `brief`
- **Evaluation Intent:** *Co-operative credit structure and resilience*
- **Grounded Citations:** *economic_survey*

#### Application Response Output:
```text
SUMMARY / ANSWER:
The economic outlook for co-operative and regional rural banking in rural and semi-urban India is positive, driven by structural reforms and improved financial health. The consolidation of Regional Rural Banks (RRBs) from 196 to 28 entities under a "One-State-One-RRB" principle has streamlined operations and enhanced performance. Financial results reflect this stability, with RRBs achieving a record consolidated net profit of ₹7.6 thousand crore in FY24 and ₹6.8 thousand crore in FY25. Asset quality has also strengthened significantly, as the Gross Non-Performing Asset (GNPA) ratio in the agricultural sector declined from 6.1 per cent in FY24 to 5.4 per cent in FY25, marking the lowest level in 13 years. These improvements, supported by unified IT platforms and branding, indicate a robust future for credit distribution to small farmers and rural industries.
```

---

### Q043: What are the key risk factors highlighted in the Economic Survey for the financial sector?

- **Category:** `Macro`
- **Status:** 🟢 **Answered**
- **Latency:** `15.35s`
- **Dispatched Sources:** `macro`
- **Rendered Cards:** `brief`
- **Evaluation Intent:** *Macro-financial risks and external headwinds*
- **Grounded Citations:** *ministry_of_finance, economic_survey*

#### Application Response Output:
```text
SUMMARY / ANSWER:
The Economic Survey highlights several key risk factors for the financial sector. **Macro-financial stress** remains a concern, with authorities noting the need for continued reforms to mobilize private capital amidst severe stress scenarios [ministry_of_finance, p.49]. **Global geopolitical fragmentation** has turned the financial sector into a channel for transmitting volatile shocks to emerging markets, necessitating regulatory innovation to minimize costs [economic_survey, p.131]. **Cybersecurity resilience** is identified as a critical area for improvement, with the IMF recommending expanded crisis simulations and stress tests for cross-sectoral events [ministry_of_finance, p.49]. Additionally, **MSME financing** faces constraints due to high collateral requirements and complex processes, creating a credit gap estimated between 11 to 16 percent of GDP [ministry_of_finance, p.49]. Finally, while the insurance sector is sound, the overall financial system must strengthen its structure to ensure stability against global and domestic shocks [economic_survey, p.131].
```

---

### Q044: How is export credit demand evolving among Indian small enterprises?

- **Category:** `Macro`
- **Status:** 🟡 **Partial**
- **Latency:** `8.14s`
- **Dispatched Sources:** `macro`
- **Rendered Cards:** `brief`
- **Evaluation Intent:** *Export credit trends for small exporters*
- **Grounded Citations:** *economic_survey*

#### Application Response Output:
```text
SUMMARY / ANSWER:
The provided context does not contain information regarding how export credit demand is evolving specifically among Indian small enterprises. While the text notes that India's total exports reached a record USD 825.3 billion in FY25 and that merchandise exports grew by 2.4% (April-December 2025) [economic_survey, p.79], it does not detail the credit demand trends for small businesses within this sector. The document focuses instead on the broader commercial sector's shift toward alternative financing sources and the stability of the external sector.
```

---

### Q045: What are the key takeaways regarding employment and enterprise formalization in India?

- **Category:** `Macro`
- **Status:** 🟢 **Answered**
- **Latency:** `9.49s`
- **Dispatched Sources:** `macro`
- **Rendered Cards:** `brief`
- **Evaluation Intent:** *Udyam registration and formal job creation trends*
- **Grounded Citations:** *economic_survey*

#### Application Response Output:
```text
SUMMARY / ANSWER:
Recent labour market indicators suggest improving employment conditions supported by structural reforms, with monthly PLFS data showing a broadly steady labour market and a declining unemployment rate alongside a stabilising labour force participation rate [economic_survey, p.80]. The consolidation of 29 central laws into four Labour Codes aims to simplify compliance and extend security to a broader workforce, while specifically recognising gig and platform workers to facilitate their registration and inclusion in social security schemes, marking a key step towards formalising non-traditional employment [economic_survey, p.80]. Complementing these regulatory changes, government-led skilling initiatives focus on enhancing employability through industry-aligned training to better align workforce capabilities with economic requirements [economic_survey, p.80].
```

---

### Q046: What is the competitive landscape for MSME lending in Karnataka?

- **Category:** `Competitive`
- **Status:** 🟡 **Partial**
- **Latency:** `19.34s`
- **Dispatched Sources:** `competitive`
- **Rendered Cards:** `brief`
- **Evaluation Intent:** *Karnataka MSME lending competitor overview*
- **Grounded Citations:** *Kinara Capital, SIDBI, Karnataka State Co-operative Apex Bank*

#### Application Response Output:
```text
SUMMARY / ANSWER:
The Karnataka MSME lending landscape features a mix of cooperative banks, NBFCs, and fintechs. Kinara Capital, an RBI-registered NBFC, competes with faster approvals (24 hours), collateral-free loans, and flexible products like HerVikas for women entrepreneurs [Kinara Capital]. Conversely, Karnataka State Co-operative Apex Bank focuses on agriculture and rural segments, offering term loans for infrastructure and cash credit to processing units, leveraging local branch presence for relationship-led acquisition [Karnataka State Co-operative Apex Bank].

Cooperative institutions like Kaujalgi and Bellary Urban Co-operative Banks face threats from digital-first lenders competing on speed and pricing [Kaujalgi Urban Co-operative Bank]. While cooperatives benefit from rural product differentiation, they lack explicit MSME positioning in public data compared to NBFCs [Karnataka State Financial Corporation]. SIDBI supports the ecosystem via platforms like Udyam Assist but does not list specific Karnataka lending rates [SIDBI]. A gap exists regarding specific interest rates, ticket sizes, and market shares for all entities, as these figures are absent from the provided text.
```

---

### Q047: Which institutions are the key competitors for Karnataka co-operative banks?

- **Category:** `Competitive`
- **Status:** 🟡 **Partial**
- **Latency:** `17.31s`
- **Dispatched Sources:** `competitive`
- **Rendered Cards:** `brief`
- **Evaluation Intent:** *Regional peer banks and private NBFC competitors*
- **Grounded Citations:** *Karnataka State Financial Corporation, Karnataka State Co-operative Apex Bank, Kaujalgi Urban Co-operative Bank, Bhatkal Urban Co-operative Bank*

#### Application Response Output:
```text
SUMMARY / ANSWER:
The provided indexed passages do not explicitly list key competitors for Karnataka co-operative banks. While the text details the operations of the Karnataka State Co-operative Apex Bank, Karnataka State Financial Corporation, and specific urban co-operative banks like Bhatkal and Kaujalgi, it lacks a direct competitive analysis or a list of rival institutions.

The documents describe the Apex Bank's role in providing refinance assistance to State Co-operative Banks (SCBs) and District Central Co-operative Banks (DCCBs) for agricultural marketing and crop loans [Karnataka State Co-operative Apex Bank]. They also outline the branch networks and product offerings of KSFC and various urban co-operative banks, but no comparative market data or explicit competitor identification is present. Therefore, a direct comparison of institutions as competitors cannot be made based on the supplied evidence.
```

---

### Q048: What is the business profile and target segment of Kinara Capital in Karnataka?

- **Category:** `Competitive`
- **Status:** 🟢 **Answered**
- **Latency:** `9.14s`
- **Dispatched Sources:** `competitive`
- **Rendered Cards:** `brief`
- **Evaluation Intent:** *Kinara Capital MSME focus and operations*
- **Grounded Citations:** *Kinara Capital*

#### Application Response Output:
```text
SUMMARY / ANSWER:
Kinara Capital is a fintech NBFC registered with the RBI, founded in 2011 by Hardika Shah. Its business profile centers on offering business loans to MSMEs to drive financial inclusion and fuel small business growth across India. The institution targets underserved MSMEs, aiming to empower every entrepreneur with equal access to capital. While the provided text lists branch locations in Andhra Pradesh, Telangana, and Puducherry, it does not specify any operational branches or target segments specifically within Karnataka. Consequently, the exact business profile and target segment for Kinara Capital in Karnataka cannot be determined from the supplied evidence.
```

---

### Q049: What is the profile and market focus of SIDBI in MSME refinancing?

- **Category:** `Competitive`
- **Status:** 🟢 **Answered**
- **Latency:** `11.03s`
- **Dispatched Sources:** `competitive`
- **Rendered Cards:** `brief`
- **Evaluation Intent:** *SIDBI direct lending and refinance lines*
- **Grounded Citations:** *SIDBI*

#### Application Response Output:
```text
SUMMARY / ANSWER:
SIDBI is the Small Industries Development Bank of India, positioned as the benchmark for the MSME ecosystem rather than a direct local-bank peer [SIDBI]. Its profile includes leadership roles such as Chairman & Managing Director and Deputy Managing Directors, alongside specialized entities like SIDBI Venture Capital Limited and the CGTMSE scheme [SIDBI]. The institution focuses on empowering women entrepreneurs and accelerating enterprise growth through loan sanctions, as illustrated by the case of Kaka Industries [SIDBI]. Market focus is evident through initiatives like the India Microfinance Equity Scheme, the Udyam Assist Platform, and the publication of the MSME Outlook Survey Report and Small Business Spotlight series [SIDBI]. While specific refinancing rates or ticket sizes are not provided in the indexed evidence, SIDBI's role is defined by its ecosystem-wide support and strategic schemes designed to address sector progress and challenges [SIDBI].
```

---

### Q050: What is the role and market presence of Karnataka State Co-operative Apex Bank?

- **Category:** `Competitive`
- **Status:** 🟢 **Answered**
- **Latency:** `21.50s`
- **Dispatched Sources:** `competitive`
- **Rendered Cards:** `brief`
- **Evaluation Intent:** *Karnataka Apex Bank rural and cooperative network*
- **Grounded Citations:** *Kaujalgi Urban Co-operative Bank, Karnataka State Co-operative Apex Bank, Bhatkal Urban Co-operative Bank*

#### Application Response Output:
```text
SUMMARY / ANSWER:
The Karnataka State Co-operative Apex Bank serves as the apex institution for Karnataka's cooperative sector, registered with DICGC and established through the reorganization of provisional co-operatives. Its primary role involves financing short-term agricultural loans for crop production/marketing and medium-term loans for infrastructure like irrigation and dairy. It extends cash credit to processing, marketing, and consumer co-operatives, as well as sugar factories, and provides term loans to state and national-level institutions [Karnataka State Co-operative Apex Bank]. The bank has a significant market presence, evidenced by its role in awarding other institutions; for instance, the South Canara District Central Co-operative Bank received multiple awards from the Apex Bank between 1997 and 2014 [South Canara District Central Co-operative Bank]. Additionally, the Apex Bank's influence is structural, as the President of the South Canara District Central Co-operative Bank is also a Director of the Apex Bank [South Canara District Central Co-operative Bank]. Specific market share figures or exact loan volumes for the Apex Bank itself are not provided in the supplied text.
```

---

### Q051: How does Karnataka State Financial Corporation (KSFC) support industrial lending?

- **Category:** `Competitive`
- **Status:** 🟡 **Partial**
- **Latency:** `11.67s`
- **Dispatched Sources:** `competitive`
- **Rendered Cards:** `brief`
- **Evaluation Intent:** *KSFC term lending and project finance*
- **Grounded Citations:** *Karnataka State Financial Corporation, Belgaum Industrial Co-operative Bank*

#### Application Response Output:
```text
SUMMARY / ANSWER:
The provided indexed passages do not contain specific details on how the Karnataka State Financial Corporation (KSFC) supports industrial lending, such as loan schemes, interest rates, or operational mechanisms. The documents list KSFC's contact information, branch addresses, and performance reports but omit lending specifics. In contrast, the Belgaum Industrial Co-operative Bank explicitly states its objective was to extend financial facilities to the local handloom industry and small/medium-scale industries, though it notes restrictions on funding societies post-1990 [Belgaum Industrial Co-operative Bank]. Consequently, a direct comparison of their industrial lending support methods cannot be made from the available text.
```

---

### Q052: What is the profile and lending approach of National Co-operative Bank?

- **Category:** `Competitive`
- **Status:** 🟢 **Answered**
- **Latency:** `20.52s`
- **Dispatched Sources:** `competitive`
- **Rendered Cards:** `brief`
- **Evaluation Intent:** *National Co-op Bank urban micro-lending*
- **Grounded Citations:** *Kaujalgi Urban Co-operative Bank, Karnataka State Co-operative Apex Bank, National Co-operative Bank*

#### Application Response Output:
```text
SUMMARY / ANSWER:
The National Co-operative Bank Ltd. offers products for professionals and small businesses, including working capital term loans and loans against mortgage property [National Co-operative Bank]. It provides a concession rate of 0.25% p.a. on interest for women borrowers across Housing, Education, Gold, and Business loans [National Co-operative Bank]. Specific working capital loans for small business entrepreneurs require a minimum two-year experience in the field and membership in the Mumbai Vyapari Association Maharashtra Rojgar [National Co-operative Bank]. The bank also offers education loans with disbursement directly to institutions and gold loans [National Co-operative Bank].

Unlike the Kaujalgi Urban Co-operative Bank, which emphasizes a "member-focused approach" with mobile banking and digital innovation specifically for the Belagavi district [Kaujalgi Urban Co-operative Bank], the National Co-operative Bank's profile highlights a wide range of products for professionals and small businesses without specifying a single district focus in the provided text [National Co-operative Bank]. The National Co-operative Bank is registered with DICGC and permits participation as both Remitter and Beneficiary [National Co-operative Bank].
```

---

### Q053: How do Urban Co-operative Banks like Bellary Urban and Bhatkal Urban compete in their districts?

- **Category:** `Competitive`
- **Status:** 🟢 **Answered**
- **Latency:** `16.96s`
- **Dispatched Sources:** `competitive`
- **Rendered Cards:** `brief`
- **Evaluation Intent:** *Urban co-operative positioning in North Karnataka*
- **Grounded Citations:** *Kaujalgi Urban Co-operative Bank, Bellary Urban Co-operative Bank, Bhatkal Urban Co-operative Bank*

#### Application Response Output:
```text
SUMMARY / ANSWER:
Bellary Urban Co-operative Bank competes through deep historical roots, having operated since 1916 with a mission to be a "World-class Indian Bank," and offers a full suite of services including personal, home, and car loans alongside digital banking access [Bellary Urban Co-operative Bank]. In contrast, Bhatkal Urban Co-operative Bank focuses on localized branch presence in Uttara Kannada District and specific senior citizen and NRE facilities [Bhatkal Urban Co-operative Bank]. While Bellary emphasizes its long-standing legacy, Bhatkal highlights operational services like online computer banking and e-stamping at its branches. Neither institution's specific interest rates or loan limits are provided in the supplied text, creating a gap in direct product comparison. Both leverage local district presence to support relationship-led acquisition, a key competitive advantage for co-operative lenders [Karnataka State Co-operative Apex Bank].
```

---

### Q054: What are the strengths of District Central Co-operative Banks like Belagavi DCCB and South Canara DCCB?

- **Category:** `Competitive`
- **Status:** 🟡 **Partial**
- **Latency:** `18.43s`
- **Dispatched Sources:** `competitive`
- **Rendered Cards:** `brief`
- **Evaluation Intent:** *DCCB district-level grassroots branch reach*
- **Grounded Citations:** *Belgaum Industrial Co-operative Bank, Kaujalgi Urban Co-operative Bank, Belagavi District Central Co-operative Bank*

#### Application Response Output:
```text
SUMMARY / ANSWER:
The provided indexed passages do not contain specific information regarding the strengths of South Canara DCCB. For Belagavi District Central Co-operative Bank (BDCC), the text highlights its long-standing history, founded in 1919, and its significant focus on agricultural and sugar sector financing. Specifically, BDCC has disbursed Rs 1,22,489 Lakh in loans to over 3.35 lakh farmers via the Kissan Credit Card and provided Rs 50,224 Lakh to sugar factories [Belagavi District Central Co-operative Bank]. The bank also emphasizes community commitment and offers diverse financial products including savings, fixed deposits, and working capital loans [Kaujalgi Urban Co-operative Bank]. However, no direct comparative data or specific strengths for South Canara DCCB are available in the supplied evidence.
```

---

### Q055: What is the profile and regional strength of South Canara DCCB in coastal Karnataka?

- **Category:** `Competitive`
- **Status:** 🟢 **Answered**
- **Latency:** `18.44s`
- **Dispatched Sources:** `competitive`
- **Rendered Cards:** `brief`
- **Evaluation Intent:** *South Canara DCCB agricultural and commercial lending*
- **Grounded Citations:** *Belagavi District Central Co-operative Bank, South Canara District Central Co-operative Bank*

#### Application Response Output:
```text
SUMMARY / ANSWER:
South Canara District Central Co-operative Bank (SCDCB) demonstrates strong regional depth in coastal Karnataka, maintaining a dense branch network across Udupi, Kundapura, Belthangady, Sullia, and Moodabidri [South Canara District Central Co-operative Bank]. Its profile includes diverse deposit products like Nithya Dhara and Insurance Linked schemes, alongside a robust capital base of Rs. 47,599.88 lakh as of March 2025 [South Canara District Central Co-operative Bank].

Unlike Belagavi District Central Co-operative Bank (BDCC), which highlights specific agricultural disbursements (e.g., Rs. 1,22,489 lakh via KCC) and a 1919 founding date [Belagavi District Central Co-operative Bank], the provided text for SCDCB lacks explicit founding dates or specific loan disbursement volumes. Both institutions share similar strategic strengths, including established digital channels and local co-operative presence, though both face threats from fintech and NBFC competition [South Canara District Central Co-operative Bank]. A gap exists in the available data regarding SCDCB's historical timeline and specific loan portfolio metrics compared to BDCC's detailed agricultural lending figures.
```

---

### Q056: How do NBFC interest rates on MSME loans compare with co-operative bank rates?

- **Category:** `Competitive`
- **Status:** 🟡 **Partial**
- **Latency:** `19.34s`
- **Dispatched Sources:** `competitive`
- **Rendered Cards:** `brief`
- **Evaluation Intent:** *Interest rate spread between NBFCs and co-operatives*
- **Grounded Citations:** *Karnataka State Co-operative Apex Bank, National Co-operative Bank, Kinara Capital*

#### Application Response Output:
```text
SUMMARY / ANSWER:
The provided indexed passages do not contain specific interest rate figures for NBFCs on MSME loans to allow for a direct numerical comparison with co-operative bank rates. While the text notes that NBFCs like Kinara Capital offer "advantageous" rates and are "more proactive in innovating financial products" than banks, it does not list their exact percentages [Kinara Capital].

Conversely, specific co-operative bank rates are available. For instance, the Karnataka State Co-operative Apex Bank charges 11.00% per annum for certain lease-related loans [Karnataka State Co-operative Apex Bank]. The Belagavi District Central Co-operative Bank lists rates ranging from 9% to 12.5% for various working capital and small-scale business categories [Belagavi District Central Co-operative Bank]. The National Co-operative Bank offers a concession rate of 0.25% p.a. for women borrowers on business loans [National Co-operative Bank].

**Gap:** Specific NBFC MSME interest rates are absent from the evidence, preventing a direct rate comparison.
```

---

### Q057: What are the collateral requirements typically sought by NBFCs versus co-operative lenders?

- **Category:** `Competitive`
- **Status:** 🟡 **Partial**
- **Latency:** `20.83s`
- **Dispatched Sources:** `competitive`
- **Rendered Cards:** `brief`
- **Evaluation Intent:** *Secured vs unsecured lending requirements*
- **Grounded Citations:** *Kaujalgi Urban Co-operative Bank, Karnataka State Co-operative Apex Bank, National Co-operative Bank*

#### Application Response Output:
```text
SUMMARY / ANSWER:
The provided indexed passages detail collateral requirements for Karnataka co-operative lenders but contain no specific data on NBFC collateral requirements. Consequently, a direct comparison cannot be made based on the supplied text.

For co-operative lenders, security varies by loan size and purpose. Loans up to Rs. 10.00 lakhs often require no security but mandate a guarantor [Karnataka State Co-operative Apex Bank]. Loans exceeding Rs. 10.00 lakhs typically require collateral security equal to 100% of the loan amount or a co-obligant with net worth not less than the loan amount [Karnataka State Co-operative Apex Bank]. Specific products like medical course loans demand immovable property security equal to 150% of the loan amount [Karnataka State Co-operative Apex Bank].

While the text notes that NBFCs compete on faster approval and digital onboarding, it does not specify their collateral thresholds [Karnataka State Co-operative Apex Bank]. The gap regarding NBFC-specific collateral rules remains unsupported by the provided evidence.
```

---

### Q058: How do fintech and digital NBFCs compete on loan turnaround time (TAT)?

- **Category:** `Competitive`
- **Status:** 🟢 **Answered**
- **Latency:** `18.80s`
- **Dispatched Sources:** `competitive`
- **Rendered Cards:** `brief`
- **Evaluation Intent:** *Turnaround time and digital underwriting speed*
- **Grounded Citations:** *Kaujalgi Urban Co-operative Bank, Karnataka State Co-operative Apex Bank, SIDBI, Kinara Capital*

#### Application Response Output:
```text
SUMMARY / ANSWER:
Fintechs and digital NBFCs compete on loan turnaround time (TAT) by leveraging speed and minimal documentation, whereas cooperative lenders rely on local presence for relationship-led servicing.

Kinara Capital, a digital NBFC, explicitly states it disburses collateral-free MSME loans in "just 24 hours, with minimal documentation" [Kinara Capital]. This contrasts with the competitive threat faced by cooperatives, where "Comparable banks, NBFCs, and fintech lenders can compete on faster approval... and digital onboarding" [Karnataka State Co-operative Apex Bank].

While cooperatives like Kaujalgi Urban Co-operative Bank highlight "Digital/payment-channel references" as a strength for modernization [Kaujalgi Urban Co-operative Bank], they remain differentiated by "Agriculture/rural product signals" that digital-first lenders lack [Kaujalgi Urban Co-operative Bank]. The provided evidence does not specify exact TAT figures for the cooperative institutions, only noting the competitive pressure to match fintech speeds.
```

---

### Q059: What is the Month-on-Month (MoM) loan repayment efficiency trend across recent cohorts?

- **Category:** `Competitive`
- **Status:** 🟡 **Partial**
- **Latency:** `14.77s`
- **Dispatched Sources:** `competitive`
- **Rendered Cards:** `brief`
- **Evaluation Intent:** *Loan vintage efficiency tracking (Dec 2025 - June 2026)*
- **Grounded Citations:** *Karnataka State Co-operative Apex Bank, Kinara Capital*

#### Application Response Output:
```text
SUMMARY / ANSWER:
The provided indexed passages do not contain specific data on Month-on-Month (MoM) loan repayment efficiency trends across recent cohorts for any institution. While documents for Karnataka State Co-operative Apex Bank, Kinara Capital, and various urban co-operative banks detail interest rates, loan types, and general processing features like "Quick Approval," none offer quantitative trend analysis or repayment efficiency metrics. Consequently, a direct comparison of MoM trends between these institutions cannot be made based on the available evidence. The gap in specific performance trend data prevents answering the core of your question.
```

---

### Q060: How has GICC operational collection efficiency improved from Dec 2025 to June 2026?

- **Category:** `Competitive`
- **Status:** 🟡 **Partial**
- **Latency:** `15.64s`
- **Dispatched Sources:** `competitive`
- **Rendered Cards:** `brief`
- **Evaluation Intent:** *Collection efficiency MoM improvement (+3.8%)*
- **Grounded Citations:** *Karnataka State Financial Corporation, Karnataka State Co-operative Apex Bank, SIDBI, National Co-operative Bank*

#### Application Response Output:
```text
SUMMARY / ANSWER:
The provided indexed passages do not contain specific operational collection efficiency metrics for GICC between December 2025 and June 2026. While the SIDBI Microfinance Pulse section notes a sector-wide decline in delinquency from 8.53% in March 2025 to 2.26% in March 2026 [SIDBI], it does not offer GICC-specific data for the requested period. No other passage details GICC's performance or compares it to other institutions regarding collection efficiency. Therefore, the specific improvement cannot be determined from the available evidence.
```

---

### Q061: What are the key white spaces and underserved borrower segments in Karnataka MSME lending?

- **Category:** `Competitive`
- **Status:** 🟢 **Answered**
- **Latency:** `17.53s`
- **Dispatched Sources:** `competitive`
- **Rendered Cards:** `brief`
- **Evaluation Intent:** *Unmet credit demand in micro-enterprises and women entrepreneurs*
- **Grounded Citations:** *Kinara Capital, SIDBI, Karnataka State Co-operative Apex Bank*

#### Application Response Output:
```text
SUMMARY / ANSWER:
The provided indexed passages do not explicitly identify specific "white spaces" or underserved borrower segments in Karnataka MSME lending. While Kinara Capital targets India's "missing middle" segment and offers collateral-free loans, including a specific product for women-owned businesses (HerVikas), the text does not quantify gaps or list specific underserved groups within Karnataka [Kinara Capital]. Similarly, while Karnataka State Co-operative Apex Bank focuses on agriculture, sugar factories, and weavers, it does not articulate unmet needs or white spaces in its description [Karnataka State Co-operative Apex Bank]. Other co-operative banks listed (e.g., Bellary, Kaujalgi) mention general MSME relevance but lack explicit details on specific underserved segments [Bellary Urban Co-operative Bank]. Therefore, a direct comparison of institutions regarding specific white spaces is not supported by the available evidence.
```

---

### Q062: How do regional co-operatives maintain borrower loyalty in semi-urban belts?

- **Category:** `Competitive`
- **Status:** 🟢 **Answered**
- **Latency:** `20.25s`
- **Dispatched Sources:** `competitive`
- **Rendered Cards:** `brief`
- **Evaluation Intent:** *Relationship-based lending vs algorithmic underwriting*
- **Grounded Citations:** *Kaujalgi Urban Co-operative Bank, Karnataka State Co-operative Apex Bank*

#### Application Response Output:
```text
SUMMARY / ANSWER:
Regional co-operatives maintain borrower loyalty in semi-urban belts through deep community integration and tailored financial products. Kaujalgi Urban Co-operative Bank explicitly roots its strategy in "community-first initiatives," leveraging a "Member-focused approach" with flexible repayment and quick approval to serve Belagavi's local needs [Kaujalgi Urban Co-operative Bank]. They combine "Modern technology meets traditional values" by partnering with 1,500+ local businesses to deliver innovative solutions [Kaujalgi Urban Co-operative Bank].

In contrast, the Karnataka State Co-operative Apex Bank focuses on systemic support rather than direct semi-urban retail loyalty. It facilitates crop marketing and provides refinance assistance to State Co-operative Banks, ensuring loans are sanctioned before marketing seasons to aid cultivators [Karnataka State Co-operative Apex Bank]. While the Apex Bank coordinates the broader credit movement, institutions like Kaujalgi directly engage members through digital inclusion, vocational training, and transparent community development programs to foster retention [Kaujalgi Urban Co-operative Bank]. No specific loyalty metrics or comparative market shares are provided in the evidence.
```

---

### Q063: What digital lending and underwriting capabilities do private NBFCs deploy in Karnataka?

- **Category:** `Competitive`
- **Status:** 🟡 **Partial**
- **Latency:** `17.61s`
- **Dispatched Sources:** `competitive`
- **Rendered Cards:** `brief`
- **Evaluation Intent:** *Fintech automated credit scoring and bank statement analysis*
- **Grounded Citations:** *Karnataka State Financial Corporation, Kinara Capital, Kaujalgi Urban Co-operative Bank, Karnataka State Co-operative Apex Bank*

#### Application Response Output:
```text
SUMMARY / ANSWER:
The provided indexed passages do not contain specific details on the digital lending and underwriting capabilities deployed by private NBFCs in Karnataka. While [Kinara Capital] is identified as a fintech NBFC with a mission to drive MSME financial inclusion, the text does not describe its specific digital underwriting tools or processes.

Conversely, [Kaujalgi Urban Co-operative Bank] explicitly details its digital capabilities, noting it partners with 200+ digital platforms and offers mobile banking, internet banking, and digital literacy initiatives. [Karnataka State Co-operative Apex Bank] mentions that comparable NBFCs compete on "digital onboarding," but offers no specific NBFC examples.

**Gap:** The documents lack direct evidence of private NBFC digital underwriting mechanics in Karnataka, providing only general competitive context and specific details for a cooperative bank.
```

---

### Q064: How do competitor institutions leverage CGTMSE credit guarantee schemes?

- **Category:** `Competitive`
- **Status:** 🟡 **Partial**
- **Latency:** `13.53s`
- **Dispatched Sources:** `competitive`
- **Rendered Cards:** `brief`
- **Evaluation Intent:** *Collateral-free credit guarantee adoption by competitors*
- **Grounded Citations:** *Karnataka State Financial Corporation, SIDBI*

#### Application Response Output:
```text
SUMMARY / ANSWER:
The provided indexed passages do not contain specific details on how competitor institutions leverage the CGTMSE credit guarantee scheme, such as specific operational tactics, leverage ratios, or implementation strategies.

While the text confirms that SIDBI established the Credit Guarantee Fund Trust for MSME (CGTMSE) in 2000 and notes that it "has leveraged technology to improve operational efficiencies" [SIDBI], it does not elaborate on the mechanism of this leverage. Similarly, while Karnataka State Financial Corporation is mentioned as a competitor facing threats from various lenders, no specific information regarding its use of CGTMSE is available in the source material [Karnataka State Financial Corporation].

Therefore, a direct comparison of how these institutions leverage the scheme cannot be made based on the supplied evidence. The supported portion indicates the existence of the scheme and its technological improvements, but the gap regarding specific leverage strategies remains unaddressed.
```

---

### Q065: What are the main competitive threats posed by specialized MSME NBFCs to co-operative banks?

- **Category:** `Competitive`
- **Status:** 🟢 **Answered**
- **Latency:** `17.81s`
- **Dispatched Sources:** `competitive`
- **Rendered Cards:** `brief`
- **Evaluation Intent:** *Market share encroachment by agile fintechs*
- **Grounded Citations:** *Bhatkal Urban Co-operative Bank, Karnataka State Co-operative Apex Bank, Bellary Urban Co-operative Bank, Belgaum Industrial Co-operative Bank, Kaujalgi Urban Co-operative Bank*

#### Application Response Output:
```text
SUMMARY / ANSWER:
Specialized MSME NBFCs pose competitive threats primarily through superior operational efficiency and digital capabilities. According to the [Karnataka State Co-operative Apex Bank] document, these entities compete on "faster approval, clearer pricing, and digital onboarding," which directly challenges co-operative banks' traditional processes. Additionally, the [Karnataka State Co-operative Apex Bank] notes that "Credit-quality pressure may affect lending portfolios," particularly in MSME and unsecured segments, as NBFCs may absorb risk more aggressively.

While co-operative banks leverage local presence for relationship-led acquisition, the [Karnataka State Co-operative Apex Bank] highlights that "Agriculture/rural product signals differentiate the institution from purely urban or digital-first lenders," suggesting a niche advantage. However, the [National Co-operative Bank] document confirms the threat landscape, listing "Competition from banks, NBFCs, fintech lenders, and digital-first MSME platforms" as a primary risk. No specific rates or ticket sizes were provided in the text to quantify this competition further.
```

---

### Q066: How does our MSME portfolio growth compare with the wider Indian MSME credit growth rate?

- **Category:** `Hybrid`
- **Status:** 🟡 **Partial**
- **Latency:** `74.97s`
- **Dispatched Sources:** `db, macro`
- **Rendered Cards:** `brief, chart`
- **Evaluation Intent:** *Internal MSME portfolio vs national macro credit growth*
- **Grounded Citations:** *economic_survey*

#### Application Response Output:
```text
HEADLINE: Principal outstanding by scheme (As at 21 Aug 2026)
SUMMARY / ANSWER:
Our MSME portfolio shows a principal outstanding of ₹204.54 Cr in FY27 to date, whereas no comparable figure is available for FY26 to establish a direct growth trajectory for our specific portfolio. While the wider Indian MSME credit growth rate is not explicitly defined as a single aggregate figure in the provided data, the broader sector saw bank credit increase by 21.8% in November 2025 compared to the prior year, with micro and small enterprises specifically rising by 24.6%. Consequently, a direct comparison between our portfolio's growth rate and the wider Indian rate cannot be calculated due to the absence of a baseline for our FY26 portfolio and a specific aggregate growth rate for the wider sector.

CHART SPEC: Type=dumbbell, Title=Principal outstanding by scheme
COLUMNS: Scheme, Principal outstanding (FY27 to date), Principal outstanding (FY26), Change, Change %
SAMPLE ROWS (8 total): [{"scheme": "MSME Loans", "current": 598093032.27, "previous": null, "delta": null, "delta_pct": null}, {"scheme": "Site / Housing Construction / House Repair", "current": 417574205.4, "previous": null, "delta": null, "delta_pct": null}, {"scheme": "Personal Loan", "current": 406744496.01, "previous": null, "delta": null, "delta_pct": null}]
```

---

### Q067: Compare our current PAR 30 delinquency (4.18%) against the national MSME sector NPA trends.

- **Category:** `Hybrid`
- **Status:** 🟡 **Partial**
- **Latency:** `22.73s`
- **Dispatched Sources:** `db, macro`
- **Rendered Cards:** `chart, brief`
- **Evaluation Intent:** *Internal delinquency vs industry NPA averages*
- **Grounded Citations:** *economic_survey*

#### Application Response Output:
```text
HEADLINE: PAR 30 (As at 21 Aug 2026)
SUMMARY / ANSWER:
Our current PAR 30 delinquency stands at 0.27% as of 21 Aug 2026, which is significantly lower than the 4.18% figure you cited for comparison. However, a direct comparison against national MSME sector NPA trends cannot be made because the provided findings contain no data on those specific national trends. The available macro information only defines acronyms like MSME and NABARD without offering any Non-Performing Asset statistics or sectoral performance data. Consequently, while our internal metric is quantified, the external benchmark required for the comparison is missing from the source material.

CHART SPEC: Type=kpi, Title=PAR 30
COLUMNS: PAR 30
SAMPLE ROWS (1 total): [{"par_30": 0.26855264734033535}]
```

---

### Q068: How do our loan interest rates compare with competitor NBFC rates and the RBI repo rate?

- **Category:** `Hybrid`
- **Status:** 🟡 **Partial**
- **Latency:** `39.32s`
- **Dispatched Sources:** `db, macro, competitive`
- **Rendered Cards:** `chart, brief, brief`
- **Evaluation Intent:** *Lending yields vs competitor pricing and policy rate*
- **Grounded Citations:** *SIDBI, Kinara Capital, National Co-operative Bank, Karnataka State Co-operative Apex Bank, rbi*

#### Application Response Output:
```text
HEADLINE: List the interest rates present in our loan book (Generated query — not a reviewed metric)
SUMMARY / ANSWER:
Our internal data indicates that 18.0% is the most frequent loan interest rate, associated with the highest loan count of 3,740 across the available book. In contrast, the RBI has maintained a neutral monetary policy stance with the repo rate unchanged at 5.25 per cent as of June 2026. A direct comparison with competitor NBFC rates is not possible because the provided evidence does not disclose specific interest rates charged by NBFCs for MSME loans, with the only explicit rate found belonging to a non-NBFC cooperative bank for a specific lease product.

CHART SPEC: Type=bar, Title=List the interest rates present in our loan book
COLUMNS: Interest Rate, Loan Count
SAMPLE ROWS (8 total): [{"interest_rate": 16.0, "loan_count": 33}, {"interest_rate": 16.5, "loan_count": 145}, {"interest_rate": 17.0, "loan_count": 1060}]
```

---

### Q069: How does our collection efficiency of 97.8% benchmark against regional co-operative peer standards?

- **Category:** `Hybrid`
- **Status:** 🟡 **Partial**
- **Latency:** `31.65s`
- **Dispatched Sources:** `db, competitive`
- **Rendered Cards:** `chart, brief`
- **Evaluation Intent:** *Internal collection efficiency vs peer co-operative performance*
- **Grounded Citations:** *Kaujalgi Urban Co-operative Bank, Karnataka State Co-operative Apex Bank*

#### Application Response Output:
```text
HEADLINE: Collection efficiency (2026-08-21)
SUMMARY / ANSWER:
Our collection efficiency of 97.8% cannot be benchmarked against regional co-operative peer standards because the provided findings contain no specific efficiency metrics, recovery percentages, or standardized benchmarks for comparison. While the data confirms our internal efficiency figure, sources such as the Karnataka State Co-operative Apex Bank and Kaujalgi Urban Co-operative Bank only outline general policies or qualitative advantages like quick approval without offering quantitative peer standards. Consequently, a direct comparison of collection efficiency standards cannot be made from the supplied evidence.

CHART SPEC: Type=kpi, Title=Collection efficiency
COLUMNS: Collection efficiency
SAMPLE ROWS (1 total): [{"collection_efficiency": null}]
```

---

### Q070: How does our gold loan disbursement trend align with macro gold price movements and demand?

- **Category:** `Hybrid`
- **Status:** 🟡 **Partial**
- **Latency:** `16.89s`
- **Dispatched Sources:** `db, macro`
- **Rendered Cards:** `chart, brief`
- **Evaluation Intent:** *Gold loan portfolio growth vs commodity macro trends*
- **Grounded Citations:** *economic_survey*

#### Application Response Output:
```text
HEADLINE: Disbursement (all time)
SUMMARY / ANSWER:
Our gold loan disbursement trend shows no recorded disbursements across the entire available period, as the sum of disbursement event amounts for the "Gold Loans" product is zero. While macroeconomic context indicates that core inflation has been largely influenced by higher prices for precious metals like gold, the provided findings lack specific quantitative data on gold price movements or demand volumes to compare against the disbursement figures. Consequently, a direct alignment between disbursement trends and macro gold price movements cannot be established due to the absence of specific price trajectory or demand data in the source text.

CHART SPEC: Type=kpi, Title=Disbursement
COLUMNS: Disbursement
SAMPLE ROWS (1 total): [{"disbursement_total": null}]
```

---

### Q071: In light of Karnataka's GSDP growth, how is our branch-level disbursement distributed across districts?

- **Category:** `Hybrid`
- **Status:** 🟡 **Partial**
- **Latency:** `87.66s`
- **Dispatched Sources:** `db, macro`
- **Rendered Cards:** `brief, refusal`
- **Evaluation Intent:** *Branch disbursement spread vs state economic growth poles*
- **Grounded Citations:** *karnataka_des*

#### Application Response Output:
```text
SUMMARY / ANSWER:
Karnataka's Gross State Domestic Product (GSDP) is projected to grow by 8.1 per cent at constant (2011-12) prices in 2025-26, reaching an estimated Rs.17,23,006 crore [karnataka_des, p.43]. This growth rate exceeds the anticipated national GDP growth of 7.4 per cent. At current prices, the State's GSDP is expected to reach Rs.32,81,065 crore with a growth rate of 12.9 per cent, contributing an estimated 9.2 per cent to the national GDP [karnataka_des, p.43]. Historically, Karnataka's growth rate at current prices has consistently surpassed the national average, except in 2017-18 and 2023-24, while at constant prices, it surpassed the national average in most years, excluding 2014-15, 2018-19, and 2023-24 [karnataka_des, p.43].
```

---

### Q072: How does our average loan ticket size compare with microfinance and NBFC product offerings?

- **Category:** `Hybrid`
- **Status:** 🟡 **Partial**
- **Latency:** `71.27s`
- **Dispatched Sources:** `db, competitive`
- **Rendered Cards:** `chart, brief`
- **Evaluation Intent:** *Ticket size distribution vs competitor product spectrum*
- **Grounded Citations:** *Kinara Capital, SIDBI*

#### Application Response Output:
```text
HEADLINE: Average ticket size (all time)
SUMMARY / ANSWER:
Our average loan ticket size stands at ₹3.98 lakhs across all time, calculated as the total sanctioned amount divided by the number of loans. However, a direct comparison with microfinance or NBFC product offerings cannot be made because the available evidence lacks specific average ticket size data for those sectors, despite mentioning product types like Mudra-Shishu loans and various capital loans. Consequently, while our internal metric is established, the absence of quantified figures for competitors prevents a meaningful benchmarking analysis.

CHART SPEC: Type=kpi, Title=Average ticket size
COLUMNS: Average ticket size
SAMPLE ROWS (1 total): [{"avg_ticket_size": 398219.868242656}]
```

---

### Q073: How does our repayment schedule performance correlate with seasonal agricultural and MSME cash flows?

- **Category:** `Hybrid`
- **Status:** 🟡 **Partial**
- **Latency:** `25.91s`
- **Dispatched Sources:** `db, macro`
- **Rendered Cards:** `analysis, brief`
- **Evaluation Intent:** *Repayment cash flow timing vs seasonal macro cycles*
- **Grounded Citations:** *economic_survey*

#### Application Response Output:
```text
HEADLINE: Portfolio health
SUMMARY / ANSWER:
Our repayment schedule performance currently shows no deviations across six key indicators, as nothing is outside its threshold. However, the available data does not contain information regarding the specific seasonal cash flow patterns for agricultural or MSME sectors, preventing a direct correlation between our repayment metrics and these seasonal cycles. While the document notes robust credit growth in these sectors, it focuses on overall momentum rather than the timing of income and expenditure cycles required to answer your question.
```

---

### Q074: How do our portfolio delinquency levels in MSME schemes compare with SIDBI industry benchmarks?

- **Category:** `Hybrid`
- **Status:** 🟡 **Partial**
- **Latency:** `17.41s`
- **Dispatched Sources:** `db, macro`
- **Rendered Cards:** `chart, brief`
- **Evaluation Intent:** *Scheme-wise delinquency vs SIDBI Pulse indicators*
- **Grounded Citations:** *ministry_of_finance, mospi, msme*

#### Application Response Output:
```text
HEADLINE: PAR 30 by scheme (As at 21 Aug 2026)
SUMMARY / ANSWER:
Our portfolio delinquency levels in MSME schemes cannot be compared to SIDBI industry benchmarks because the provided findings do not contain any specific SIDBI benchmark data. While our Dairy Loan scheme recorded a PAR 30 of 1.2% as of 21 Aug 2026, the necessary industry figures to establish a comparison are missing from the source text. Consequently, no direct comparison can be made based on the available evidence.

CHART SPEC: Type=bar, Title=PAR 30 by scheme
COLUMNS: Scheme, PAR 30
SAMPLE ROWS (8 total): [{"scheme": "Dairy Loan", "par_30": 1.241914877328521, "scheme__raw": "1622"}, {"scheme": "Loan Against Property (Scheme #1619)", "par_30": 0.9401292302328449, "scheme__raw": "1619"}, {"scheme": "Farming Loan", "par_30": 0.2811763047327321, "scheme__raw": "1621"}]
```

---

### Q075: Assessing our liquidity and repayment vintage trends against macro credit conditions.

- **Category:** `Hybrid`
- **Status:** 🟢 **Answered**
- **Latency:** `45.47s`
- **Dispatched Sources:** `db, macro`
- **Rendered Cards:** `analysis, brief`
- **Evaluation Intent:** *Cohort vintage efficiency vs credit cycle tightening*
- **Grounded Citations:** *economic_survey, rbi*

#### Application Response Output:
```text
HEADLINE: Portfolio health
SUMMARY / ANSWER:
Our internal liquidity metrics remain stable as nothing falls outside its threshold across all six indicators. However, macro credit conditions as of March 31, 2026, reveal a mixed landscape where overall Bank Credit contracted by 0.7% year-on-year, primarily driven by a 0.9% decline in Non-food Credit despite a robust 47.9% surge in Food Credit. This contraction contrasts sharply with sectoral winners like Micro and Small enterprises (30.1% growth) and the Services sector (18.6% growth), while Large industry and Trade sectors contracted by 1.1% and 4.3%, respectively. Concurrently, trends indicate a significant shift toward non-bank sources, which rose 23.8% by December 2025, whereas non-food bank credit grew 58.6% in the same period, suggesting a divergence in funding channels. While regulatory measures have bolstered MSME credit flow and commercial resource flows increased 44.7% YoY, the specific impact of these measures on our bank's repayment vintage trends is not detailed in the provided findings.
```

---

### Q076: How does our scheme-wise concentration align with priority sector lending (PSL) guidelines?

- **Category:** `Hybrid`
- **Status:** 🟡 **Partial**
- **Latency:** `37.80s`
- **Dispatched Sources:** `db, regulatory`
- **Rendered Cards:** `chart, brief`
- **Evaluation Intent:** *Portfolio composition vs regulatory PSL norms*
- **Grounded Citations:** *sbr_master_direction_2023.pdf*

#### Application Response Output:
```text
HEADLINE: Principal outstanding by scheme (As at 21 Aug 2026)
SUMMARY / ANSWER:
Our MSME Loans scheme holds the highest principal outstanding at ₹59.81 Cr, representing 29% of the total across 8 schemes as of 21 Aug 2026. However, the provided regulatory text contains no explicit rules, thresholds, or specific guidelines for Priority Sector Lending (PSL) or MSME lending to determine if this concentration aligns with compliance requirements. Consequently, a direct comparison between our scheme-wise concentration and PSL guidelines cannot be made without consulting the separate Master Directions specifically titled *Reserve Bank of India (Priority Sector Lending) Directions* and *Reserve Bank of India (Lending to Micro, Small and Medium Enterprises) Directions*.

CHART SPEC: Type=bar, Title=Principal outstanding by scheme
COLUMNS: Scheme, Principal outstanding
SAMPLE ROWS (8 total): [{"scheme": "MSME Loans", "principal_outstanding": 598093032.27, "scheme__raw": "1616"}, {"scheme": "Site / Housing Construction / House Repair", "principal_outstanding": 417574205.4, "scheme__raw": "1618"}, {"scheme": "Personal Loan", "principal_outstanding": 406744496.01, "scheme__raw": "1617"}]
```

---

### Q077: How does our sanction-to-disbursement conversion rate reflect operational efficiency against NBFC benchmarks?

- **Category:** `Hybrid`
- **Status:** 🟡 **Partial**
- **Latency:** `23.64s`
- **Dispatched Sources:** `db, competitive`
- **Rendered Cards:** `brief, clarify`
- **Evaluation Intent:** *Conversion ratio vs market turnaround standards*
- **Grounded Citations:** *Kinara Capital*

#### Application Response Output:
```text
SUMMARY / ANSWER:
The provided indexed passages do not contain specific benchmarks for sanction-to-disbursement conversion rates for NBFCs. While the documents detail Kinara Capital's ESG alignment, grievance redressal mechanisms, and loan product categories, they omit operational metrics like conversion rates, turnaround times, or comparative industry standards. Consequently, a direct comparison with other institutions or specific rate figures cannot be derived from the supplied text.
```

---

### Q078: What is the impact of macro inflation and interest rate cycles on our floating-rate loan portfolio?

- **Category:** `Hybrid`
- **Status:** 🟡 **Partial**
- **Latency:** `86.64s`
- **Dispatched Sources:** `db, macro`
- **Rendered Cards:** `brief, refusal`
- **Evaluation Intent:** *Inflation impact on borrower repayment capacity*
- **Grounded Citations:** *economic_survey*

#### Application Response Output:
```text
SUMMARY / ANSWER:
The provided context does not contain information regarding the impact of inflation and interest rate cycles on floating-rate loans. While the text mentions that core inflation has been influenced by higher prices for precious metals like gold and silver [economic_survey, p.18], it does not discuss floating-rate loans, interest rate cycles, or the specific mechanisms by which inflation affects them. Therefore, I cannot answer the question based strictly on the provided passages.
```

---

### Q079: How does our borrower gender diversity compare with microfinance industry inclusion targets?

- **Category:** `Hybrid`
- **Status:** 🟡 **Partial**
- **Latency:** `22.53s`
- **Dispatched Sources:** `db, macro, competitive`
- **Rendered Cards:** `chart, brief, brief`
- **Evaluation Intent:** *Internal gender inclusion vs regional microfinance averages*
- **Grounded Citations:** *economic_survey, SIDBI*

#### Application Response Output:
```text
HEADLINE: Borrowers by borrower gender (all time)
SUMMARY / ANSWER:
Our borrower gender diversity cannot be directly compared to microfinance industry inclusion targets because the provided evidence does not contain specific industry targets or gender breakdowns for the broader sector. While our institution, M, has the highest borrower count at 3,142 with 55% across three genders, the available data only notes that the sector currently comprises 95% women borrowers without outlining future goals. Consequently, a direct comparison between our lender's specific gender diversity and industry targets cannot be made with the supplied evidence.

CHART SPEC: Type=donut, Title=Borrowers by borrower gender
COLUMNS: Borrower gender, Borrowers
SAMPLE ROWS (3 total): [{"gender": "M", "customer_count": 3142, "gender__raw": "M"}, {"gender": "F", "customer_count": 2553, "gender__raw": "F"}, {"gender": "Not recorded", "customer_count": 46, "gender__raw": null}]
```

---

### Q080: Compare our top 10 borrower concentration risk with prudential single-borrower regulatory exposure limits.

- **Category:** `Hybrid`
- **Status:** 🟢 **Answered**
- **Latency:** `48.23s`
- **Dispatched Sources:** `db, regulatory`
- **Rendered Cards:** `chart, brief`
- **Evaluation Intent:** *Single/group borrower concentration vs regulatory caps*
- **Grounded Citations:** *Prudential Norms.pdf*

#### Application Response Output:
```text
HEADLINE: Principal outstanding (whole book) by borrower (2026-08-21)
SUMMARY / ANSWER:
Our top borrower, MANJULA, represents 15% of the total principal outstanding across the top 10 borrowers, which is currently within the standard prudential regulatory limit of 20% of Tier 1 capital for a single counterparty. While MANJULA's specific exposure is compliant, the regulatory framework allows for a maximum exposure of 25% for general NBFCs or 30% for NBFC-IFCs if the exposure relates to infrastructure loans with proper Board approval. The findings do not specify our entity type (general NBFC vs. NBFC-IFC) or the nature of MANJULA's loans, so we cannot confirm if the 25% or 30% ceiling applies to our specific situation. Consequently, while the current 15% concentration is safe under standard norms, we must verify our classification to ensure full compliance with the applicable ceiling.

CHART SPEC: Type=bar, Title=Principal outstanding (whole book) by borrower
COLUMNS: Borrower, Principal outstanding (whole book)
SAMPLE ROWS (10 total): [{"borrower": "MANJULA", "principal_outstanding_book": 6737127.38, "borrower__raw": "MANJULA"}, {"borrower": "ASHWINI  ASHWINI", "principal_outstanding_book": 5306140.33, "borrower__raw": "ASHWINI  ASHWINI"}, {"borrower": "GEETHA", "principal_outstanding_book": 4534097.8, "borrower__raw": "GEETHA"}]
```

---

### Q081: How does our DPD bucket migration compare with macroeconomic stress indicators in Karnataka?

- **Category:** `Hybrid`
- **Status:** 🟡 **Partial**
- **Latency:** `75.26s`
- **Dispatched Sources:** `db, macro`
- **Rendered Cards:** `brief, chart`
- **Evaluation Intent:** *Delinquency migration vs regional economic headwinds*
- **Grounded Citations:** *karnataka_des*

#### Application Response Output:
```text
HEADLINE: Average DPD by dpd bucket (As at 21 Aug 2026)
SUMMARY / ANSWER:
Our DPD bucket migration shows that the 90+ days past due category holds the highest average at 91 days as of 21 August 2026, accounting for 49% of the total across five buckets. However, a direct comparison with macroeconomic stress indicators in Karnataka cannot be completed because the provided data only includes Consumer Price Index figures for industrial workers and lacks essential metrics like unemployment rates, fiscal deficit, or industrial output. Consequently, while the internal delinquency concentration is quantified, the external macroeconomic context required for a full comparative analysis is missing from the source text.

CHART SPEC: Type=bar, Title=Average DPD by dpd bucket
COLUMNS: DPD bucket, Average DPD
SAMPLE ROWS (5 total): [{"dpd_bucket": "90+", "avg_dpd": 91.0, "dpd_bucket__raw": "90+"}, {"dpd_bucket": "61-90", "avg_dpd": 61.0, "dpd_bucket__raw": "61-90"}, {"dpd_bucket": "31-60", "avg_dpd": 31.0, "dpd_bucket__raw": "31-60"}]
```

---

### Q082: Evaluating our business loan disbursement trajectory against state-wide industrial growth indicators.

- **Category:** `Hybrid`
- **Status:** 🟡 **Partial**
- **Latency:** `90.63s`
- **Dispatched Sources:** `db, macro`
- **Rendered Cards:** `brief, refusal`
- **Evaluation Intent:** *Business loan volume vs Karnataka manufacturing IIP*
- **Grounded Citations:** *mospi*

#### Application Response Output:
```text
SUMMARY / ANSWER:
The provided context does not contain state-wide industrial growth indicators for Karnataka; it exclusively presents all-India Quick Estimates of the Index of Industrial Production (IIP) for May 2026 from MOSPI [mospi, p.3]. The document reports an all-India IIP growth rate of 5.1 percent, with the Manufacturing sector growing at 5.5 percent [mospi, p.3]. It further details sectoral indices and use-based classifications for the entire nation, such as a 12.9 percent growth in Capital Goods, but offers no specific data for the state of Karnataka. Therefore, I cannot answer the question using the provided text.
```

---

### Q083: How do our retail loan collection ratios compare with regional urban co-operative benchmarks?

- **Category:** `Hybrid`
- **Status:** 🟡 **Partial**
- **Latency:** `94.31s`
- **Dispatched Sources:** `db, competitive`
- **Rendered Cards:** `brief, error`
- **Evaluation Intent:** *Retail collections vs UCB peer metrics*
- **Grounded Citations:** *Kaujalgi Urban Co-operative Bank, Karnataka State Co-operative Apex Bank*

#### Application Response Output:
```text
SUMMARY / ANSWER:
The provided indexed passages do not contain specific regional urban co-operative collection benchmarks, such as total deposit figures, average ticket sizes, or collection growth rates for the listed institutions.

While **Kaujalgi Urban Co-operative Bank** mentions partnering with 1,500+ local businesses and **Belagavi District Central Co-operative Bank** reports disbursing Rs 1,22,489 Lakh in loans to farmers, neither document provides aggregate collection data or comparative benchmarks against other urban co-operatives. Similarly, **Belgaum Industrial Co-operative Bank** details deposit schemes and interest rates but omits total collection volumes.

Therefore, a direct comparison of collection benchmarks cannot be constructed from the available evidence. The gap lies in the absence of quantitative collection metrics across all supplied documents.
```

---

### Q084: How does our portfolio risk profile support potential co-lending partnerships with larger NBFCs?

- **Category:** `Hybrid`
- **Status:** 🟢 **Answered**
- **Latency:** `81.75s`
- **Dispatched Sources:** `db, competitive`
- **Rendered Cards:** `chart, brief`
- **Evaluation Intent:** *Asset quality suitability for co-lending structures*
- **Grounded Citations:** *Kaujalgi Urban Co-operative Bank, Karnataka State Co-operative Apex Bank, Kinara Capital*

#### Application Response Output:
```text
HEADLINE: PAR 30 and NPA ratio and Principal outstanding by dpd bucket (As at 21 Aug 2026)
SUMMARY / ANSWER:
Our portfolio risk profile supports co-lending partnerships by leveraging local branch presence for relationship-led acquisition in agriculture and MSME segments, which differentiates us from purely digital-first lenders. However, credit-quality pressure in unsecured segments poses a threat comparable to that faced by banks and fintechs. While external models like Kinara Capital and SIDBI offer complementary approaches to unlocking MSME opportunities and managing concentration risks, the provided text does not contain specific data on our own PAR 30 or NPA ratios to fully quantify our current risk standing. Consequently, the direct comparison of our specific risk metrics against larger NBFCs is limited by the absence of finalized governed definitions and specific rate details in the source material.

CHART SPEC: Type=table, Title=PAR 30 and NPA ratio and Principal outstanding by dpd bucket
COLUMNS: DPD bucket, PAR 30, NPA ratio, Principal outstanding
SAMPLE ROWS (5 total): [{"dpd_bucket": "31-60", "par_30": 100.0, "npa_ratio": 0.0, "principal_outstanding": 4895028.14, "dpd_bucket__raw": "31-60"}, {"dpd_bucket": "90+", "par_30": 100.0, "npa_ratio": 100.0, "principal_outstanding": 410814.29, "dpd_bucket__raw": "90+"}, {"dpd_bucket": "61-90", "par_30": 100.0, "npa_ratio": 0.0, "principal_outstanding": 187118.7, "dpd_bucket__raw": "61-90"}]
```

---

### Q085: Cross-analysis of our branch expansion in Aluva, Kochi, and Kottayam against local economic vitality.

- **Category:** `Hybrid`
- **Status:** 🟡 **Partial**
- **Latency:** `29.46s`
- **Dispatched Sources:** `db, macro`
- **Rendered Cards:** `brief, clarify`
- **Evaluation Intent:** *Branch distribution vs district economic vibrancy*
- **Grounded Citations:** *karnataka_des*

#### Application Response Output:
```text
SUMMARY / ANSWER:
The provided context does not contain local economic vitality indicators for Aluva, Kochi, or Kottayam. The document exclusively presents Consumer Price Index Numbers for Industrial Workers in Karnataka cities such as Bengaluru, Belagavi, and Mysuru [karnataka_des, p.78]. Consequently, no data regarding the requested Kerala locations is available in this text.
```

---

### Q086: What is the difference between sanctioned amount and disbursed amount in lending?

- **Category:** `General`
- **Status:** 🟢 **Answered**
- **Latency:** `6.87s`
- **Dispatched Sources:** `knowledge`
- **Rendered Cards:** `brief`
- **Evaluation Intent:** *Sanction vs disbursement conceptual definition*

#### Application Response Output:
```text
SUMMARY / ANSWER:
The sanctioned amount is the total sum of loan limits approved for accounts during a specific period, whereas the disbursed amount is the actual sum of funds released to borrowers in that same period. While the sanctioned amount represents the approved credit capacity, the disbursed amount reflects the real money transferred, meaning these figures often differ if borrowers do not withdraw their full approved limits. Unlike a loan rejection, a negative outcome in this context simply indicates that a sanctioned account has not yet resulted in a disbursement event.
```

---

### Q087: How is Portfolio at Risk (PAR 30) defined and calculated?

- **Category:** `General`
- **Status:** 🟢 **Answered**
- **Latency:** `6.34s`
- **Dispatched Sources:** `knowledge`
- **Rendered Cards:** `brief`
- **Evaluation Intent:** *PAR 30 formula, numerator and denominator definition*

#### Application Response Output:
```text
SUMMARY / ANSWER:
Portfolio at Risk (PAR 30) is a metric that measures the percentage of a bank's classified loan portfolio where the principal has been overdue for more than 30 days. It is calculated by dividing the principal outstanding over 30 days past due (DPD) by the total classified principal outstanding. This differs from PAR 60, which uses a 60-day overdue threshold, and from simple overdue principal, which is an absolute monetary value rather than a risk percentage.
```

---

### Q088: What qualifies a loan asset as Non-Performing (NPA) under banking prudential norms?

- **Category:** `General`
- **Status:** 🟢 **Answered**
- **Latency:** `7.98s`
- **Dispatched Sources:** `knowledge`
- **Rendered Cards:** `brief`
- **Evaluation Intent:** *NPA 90-day classification criteria*

#### Application Response Output:
```text
SUMMARY / ANSWER:
A loan asset qualifies as Non-Performing (NPA) when it is classified by the Reserve Bank of India (RBI) as failing to meet repayment obligations according to specific prudential norms. This status is determined by the "Asset classification" metric at a snapshot date, distinguishing it from the broader "Principal outstanding" which simply tracks the remaining loan balance regardless of performance. While NPAs are often aggregated into the "NPA ratio" to measure portfolio health, the individual loan's NPA status relies on its specific delinquency history rather than the total count of sanctioned loans or average ticket size.
```

---

### Q089: Explain the formula and business significance of Collection Efficiency in loan portfolio management.

- **Category:** `General`
- **Status:** 🟢 **Answered**
- **Latency:** `5.84s`
- **Dispatched Sources:** `knowledge`
- **Rendered Cards:** `brief`
- **Evaluation Intent:** *Collection efficiency formula (collected vs demand)*

#### Application Response Output:
```text
SUMMARY / ANSWER:
Collection efficiency measures the percentage of total principal and interest actually paid compared to the total amount due, serving as a key indicator of a loan portfolio's repayment health. A higher percentage indicates better cash flow collection, while a lower figure signals potential delinquency or collection failures within the book. This metric is distinct from "principal outstanding," which represents the remaining unpaid balance rather than the efficiency of payments received.
```

---

### Q090: What is DPD (Days Past Due) and how are loans categorized into delinquency buckets?

- **Category:** `General`
- **Status:** 🟢 **Answered**
- **Latency:** `5.52s`
- **Dispatched Sources:** `knowledge`
- **Rendered Cards:** `brief`
- **Evaluation Intent:** *DPD bucketing methodology (0, 1-30, 31-60, 61-90, 90+)*

#### Application Response Output:
```text
SUMMARY / ANSWER:
DPD (Days Past Due) measures how many days a loan payment is overdue, serving as the primary metric for tracking delinquency. Loans are categorized into specific "DPD buckets" using standard ageing bands that group accounts based on their current overdue status. This classification helps distinguish between current assets and those requiring asset classification under RBI guidelines, separate from the total amount due which includes both principal and interest.
```

---

### Q091: What is the primary objective of RBI DNBS-02 regulatory reporting for NBFCs and financial entities?

- **Category:** `General`
- **Status:** 🟢 **Answered**
- **Latency:** `6.77s`
- **Dispatched Sources:** `knowledge`
- **Rendered Cards:** `brief`
- **Evaluation Intent:** *DNBS-02 return structure, capital adequacy, and liquidity monitoring*

#### Application Response Output:
```text
SUMMARY / ANSWER:
The primary objective of RBI DNBS-02 reporting is to collect standardized data on Non-Banking Financial Companies (NBFCs) and other financial entities to monitor their lending portfolios and ensure regulatory compliance. While the provided catalog context details specific data fields like "Branch," "Product," and "Scheme" used for organizing this information, the overarching goal remains the systematic tracking of credit exposure rather than defining a specific calculation unit. This reporting framework is distinct from operational banking metrics or internal forecasts, focusing strictly on regulatory oversight of existing loan schemes and product mappings.
```

---

### Q092: Explain Priority Sector Lending (PSL) categories and targets for Indian financial institutions.

- **Category:** `General`
- **Status:** 🟢 **Answered**
- **Latency:** `6.14s`
- **Dispatched Sources:** `knowledge`
- **Rendered Cards:** `brief`
- **Evaluation Intent:** *PSL mandates for agriculture, MSMEs, and weaker sections*

#### Application Response Output:
```text
SUMMARY / ANSWER:
Priority Sector Lending (PSL) is a regulatory requirement in India mandating that banks allocate a specific percentage of their total adjusted net bank credit to designated sectors like agriculture, small enterprises, and marginalized groups. While the Reserve Bank of India sets the overall target at 40%, the specific sub-targets for each category are determined by the government and can vary annually. This concept is distinct from general lending targets, as PSL focuses exclusively on inclusive growth and financial inclusion rather than commercial profitability.
```

---

### Q093: What is the function of the Credit Guarantee Fund Trust for Micro and Small Enterprises (CGTMSE)?

- **Category:** `General`
- **Status:** 🟢 **Answered**
- **Latency:** `6.44s`
- **Dispatched Sources:** `knowledge`
- **Rendered Cards:** `brief`
- **Evaluation Intent:** *CGTMSE collateral-free guarantee mechanism*

#### Application Response Output:
```text
SUMMARY / ANSWER:
The Credit Guarantee Fund Trust for Micro and Small Enterprises (CGTMSE) functions as a government-backed mechanism that provides credit guarantees to banks, enabling them to lend to micro and small enterprises without requiring collateral. Its primary role is to mitigate lending risks for financial institutions, thereby facilitating easier access to credit for these businesses. Unlike the "Sanctioned amount" metric, which tracks the total value of approved loans, CGTMSE specifically addresses the security aspect of those loans rather than measuring the loan volume itself.
```

---

### Q094: Explain the difference between principal outstanding, interest accrued, and total outstanding balance.

- **Category:** `General`
- **Status:** 🟢 **Answered**
- **Latency:** `6.14s`
- **Dispatched Sources:** `knowledge`
- **Rendered Cards:** `brief`
- **Evaluation Intent:** *Balance breakdown concepts in core banking*

#### Application Response Output:
```text
SUMMARY / ANSWER:
Principal outstanding represents the remaining unpaid loan amount at a specific snapshot, while interest accrued is the accumulated cost of borrowing that has not yet been paid. The total outstanding balance combines both the principal and any accrued interest (and potentially charges) to show the full amount currently owed. Unlike "total overdue," which specifically includes only unpaid principal, interest, and penalties past their due date, the total outstanding balance reflects the entire debt obligation regardless of payment status.
```

---

### Q095: What are the key components of a loan repayment schedule and EMI amortization?

- **Category:** `General`
- **Status:** 🟢 **Answered**
- **Latency:** `6.45s`
- **Dispatched Sources:** `knowledge`
- **Rendered Cards:** `brief`
- **Evaluation Intent:** *EMI principal vs interest amortization schedule*

#### Application Response Output:
```text
SUMMARY / ANSWER:
A loan repayment schedule outlines the timeline and amounts for paying back a loan, while EMI amortization specifically tracks how each payment splits between reducing the principal balance and covering interest. The principal outstanding, a key metric in this process, represents the cumulative disbursed amount minus all principal repaid to date. These concepts differ from loan counts or ticket sizes, which measure volume and average size rather than the specific cash flow structure of an individual loan.
```

---

### Q096: What is the Debt Service Coverage Ratio (DSCR) and why is it critical in MSME credit appraisal?

- **Category:** `General`
- **Status:** 🟢 **Answered**
- **Latency:** `6.15s`
- **Dispatched Sources:** `knowledge`
- **Rendered Cards:** `brief`
- **Evaluation Intent:** *DSCR formula and debt service capacity analysis*

#### Application Response Output:
```text
SUMMARY / ANSWER:
The Debt Service Coverage Ratio (DSCR) measures a borrower's ability to cover loan repayments by dividing their net operating income by their total debt service obligations. It is critical in MSME credit appraisal because it directly assesses repayment capacity, serving as a primary filter alongside metrics like the NPA ratio and collection efficiency to gauge credit risk. Unlike simple collection efficiency, which tracks actual payments made against dues, DSCR focuses on the underlying cash flow generation relative to the required payment amount.
```

---

### Q097: Explain the regulatory difference between secured lending (e.g. Gold Loans) and unsecured MSME financing.

- **Category:** `General`
- **Status:** 🟢 **Answered**
- **Latency:** `6.14s`
- **Dispatched Sources:** `knowledge`
- **Rendered Cards:** `brief`
- **Evaluation Intent:** *Collateralized vs cash-flow backed loan risk profile*

#### Application Response Output:
```text
SUMMARY / ANSWER:
Secured lending like Gold Loans requires collateral (e.g., gold) to back the debt, whereas unsecured MSME financing provides funds without specific asset guarantees. While metrics like "Average ticket size" measure the loan amount for both types, secured loans typically carry lower risk due to the collateral, unlike unsecured loans which rely solely on the borrower's creditworthiness. The provided catalog context tracks loan performance and volume but does not define the regulatory distinctions between these two financing structures.
```

---

### Q098: What are Fair Practices Code guidelines mandated by RBI for lending operations?

- **Category:** `General`
- **Status:** 🟢 **Answered**
- **Latency:** `4.60s`
- **Dispatched Sources:** `knowledge`
- **Rendered Cards:** `brief`
- **Evaluation Intent:** *RBI Fair Practices Code on transparency and recovery*

#### Application Response Output:
```text
SUMMARY / ANSWER:
The provided catalog context does not contain information regarding the Fair Practices Code guidelines mandated by the RBI for lending operations. The available data only defines technical metrics like collection efficiency, product codes, and asset classification without detailing regulatory conduct rules. Consequently, I cannot explain those specific guidelines or distinguish them from other terms using the given source material.
```

---

### Q099: Explain the relationship schema connecting loan account master, disbursement events, and repayment schedules.

- **Category:** `General`
- **Status:** 🟢 **Answered**
- **Latency:** `1.13s`
- **Dispatched Sources:** `schema`
- **Rendered Cards:** `schema`
- **Evaluation Intent:** *Database ER graph connecting master, disbursements, and repayments*

#### Application Response Output:
```text
HEADLINE: Enterprise Curiosity Schema Graph
SUMMARY / ANSWER:
4 tables, 3 relationships.
```

---

### Q100: How does Moneypal Genesis structure governed natural language query execution over lending warehouses?

- **Category:** `General`
- **Status:** 🟢 **Answered**
- **Latency:** `6.85s`
- **Dispatched Sources:** `knowledge`
- **Rendered Cards:** `brief`
- **Evaluation Intent:** *Governed catalog, QuerySpec compiler, and NLQ execution architecture*

#### Application Response Output:
```text
SUMMARY / ANSWER:
Moneypal Genesis structures query execution by organizing lending data around specific governed attributes like agents, borrowers, and linked loan counts rather than executing raw database commands. It calculates risk metrics such as PAR 30, PAR 60, and PAR 90 to measure principal outstanding over specific delinquency periods relative to classified principal. This approach distinguishes itself from generic reporting by strictly adhering to defined catalog terms like "governed agent" and "per-loan reporting attributes" to ensure data consistency.
```

---

## 3. Architecture & Methodology Notes

1. **Unified Routing (`/api/workbench/ask`):** The default score measures only the same unified endpoint used by the application. Optional direct fallbacks are diagnostic and must be explicitly enabled.
2. **Governed SQL Pipeline (`db`):** Loan book queries compiled into deterministic `QuerySpec` contracts and executed against PostgreSQL gold views without SQL injection risk.
3. **Vector Semantic Retrieval (`macro` & `competitive`):** Macro and competitive intelligence leveraged Qdrant vector retrieval (`bge-m3` 1024-dim embeddings) and local synthesis.
4. **Zero Cold-Start:** Execution remained responsive throughout all 100 consecutive turns.

---
*Report generated by Moneypal Genesis Automated Benchmark Suite*