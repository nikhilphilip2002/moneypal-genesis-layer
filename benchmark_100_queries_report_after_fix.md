# Moneypal Genesis Intelligence — 100-Query Benchmark & Evaluation Report

**Execution Timestamp:** 2026-08-21 07:33:17 UTC  
**Target Application Endpoint:** `http://100.70.118.31:4321`  
**Environment Configuration:** Production (`.env.prod` timeout settings applied)  
**Total Run Duration:** 2309.49 seconds (38.5 minutes)  

---

## 1. Executive Summary & KPIs

| Metric | Result | Benchmark Target | Status |
|---|---|---|---|
| **Total Queries Executed** | **100** | 100 | ✅ Complete |
| **Answered Queries** | **96 / 100** (96.0%) | **≥ 70% (70/100)** | **✅ PASS** |
| **Refused (Governed Safety Policy)** | 1 | < 10% | ℹ️ Handled |
| **Clarifications Triggered** | 0 | < 5% | ℹ️ Handled |
| **Errors / Timeouts** | 3 | < 10% | ⚠️ Review |
| **Average Query Latency** | **23.09s** | < 15.0s | ⚠️ Above target |

### Category Breakdown

| Category | Total Queries | Answered | Success Rate (%) | Avg Latency (s) |
|---|---|---|---|---|
| **Loan Book** | 25 | 23 / 25 | 92.0% | 16.09s |
| **Macro** | 20 | 19 / 20 | 95.0% | 19.18s |
| **Competitive** | 20 | 20 / 20 | 100.0% | 18.04s |
| **Hybrid** | 20 | 19 / 20 | 95.0% | 53.99s |
| **General** | 15 | 15 / 15 | 100.0% | 5.53s |

---

## 2. Detailed Query Execution Log (100 Queries)

### Q001: What was our total disbursement last quarter?

- **Category:** `Loan Book`
- **Status:** 🟢 **Answered**
- **Latency:** `0.72s`
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
- **Latency:** `6.87s`
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
- **Latency:** `3.92s`
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
- **Latency:** `6.84s`
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
- **Latency:** `3.40s`
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
- **Latency:** `4.96s`
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
- **Latency:** `7.33s`
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
- **Latency:** `3.85s`
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
- **Latency:** `4.44s`
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
- **Latency:** `4.61s`
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
- **Latency:** `57.83s`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `chart`
- **Evaluation Intent:** *Product code 1 (Gold Loans) total disbursement*

#### Application Response Output:
```text
HEADLINE: How much have we disbursed in gold loans (Generated query — not a reviewed metric)
SUMMARY / ANSWER:
The query returned 1 row(s) covering total disbursed. Total disbursed amount for Gold Loans (product_code = 1). This uses a validated read-only generated query rather than a reviewed metric; check Source details before relying on it.

CHART SPEC: Type=table, Title=How much have we disbursed in gold loans
COLUMNS: Total Disbursed
SAMPLE ROWS (1 total): [{"total_disbursed": null}]
```

---

### Q012: Show MSME loans by branch

- **Category:** `Loan Book`
- **Status:** 🔴 **Error**
- **Latency:** `90.56s`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `error`
- **Evaluation Intent:** *Product code 16 (Business/MSME) loan count across branches*

#### Application Response Output:
```text
ERROR DETAIL: No intelligence source produced a usable answer.
```

---

### Q013: What is our current PAR 30?

- **Category:** `Loan Book`
- **Status:** 🟢 **Answered**
- **Latency:** `41.60s`
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
- **Latency:** `3.49s`
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
- **Latency:** `6.10s`
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
- **Latency:** `6.10s`
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
- **Latency:** `4.66s`
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
- **Latency:** `4.64s`
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
- **Latency:** `4.35s`
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
- **Latency:** `6.67s`
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
- **Latency:** `5.87s`
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
- **Latency:** `3.76s`
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
- **Status:** 🟡 **Refused**
- **Latency:** `71.41s`
- **Dispatched Sources:** `db`
- **Rendered Cards:** `refusal`
- **Evaluation Intent:** *Gender breakdown of borrower base*

#### Application Response Output:
```text
SUMMARY / ANSWER:
I could not answer that safely from the available data.
```

---

### Q024: List the top 5 branches by total principal outstanding

- **Category:** `Loan Book`
- **Status:** 🟢 **Answered**
- **Latency:** `42.19s`
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
- **Latency:** `6.18s`
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
- **Status:** 🔴 **Error**
- **Latency:** `120.20s`
- **Dispatched Sources:** `macro`
- **Evaluation Intent:** *India real GDP growth projection*

#### Application Response Output:
```text
ERROR DETAIL: Request timed out after 120s
```

---

### Q027: What are the key drivers of India's current economic expansion?

- **Category:** `Macro`
- **Status:** 🟢 **Answered**
- **Latency:** `61.17s`
- **Dispatched Sources:** `macro`
- **Rendered Cards:** `brief`
- **Evaluation Intent:** *Drivers of macroeconomic growth and capital formation*
- **Grounded Citations:** *economic_survey*

#### Application Response Output:
```text
SUMMARY / ANSWER:
India's current economic expansion, with real GDP growth at 7.4% (economic_survey, p.60), is primarily driven by robust domestic demand and strengthened supply-side momentum. On the demand side, growth is anchored by Private Final Consumption Expenditure (7.5%) and Gross Fixed Capital Formation (7.8%) (economic_survey, p.60). Supply-side drivers include a significant surge in manufacturing activity (8.4% growth) and strong performance in services, particularly financial, real estate, and professional services (9.9%) (economic_survey, p.60). Additionally, the construction sector continues to contribute substantially with 7.4% growth (economic_survey, p.60). These factors collectively reaffirm India's status as the fastest-growing major economy for the fourth consecutive year (economic_survey, p.60).
```

---

### Q028: What is the current CPI inflation trend and headline inflation outlook?

- **Category:** `Macro`
- **Status:** 🟢 **Answered**
- **Latency:** `15.91s`
- **Dispatched Sources:** `macro`
- **Rendered Cards:** `brief`
- **Evaluation Intent:** *Consumer price index inflation trends*
- **Grounded Citations:** *economic_survey, rbi*

#### Application Response Output:
```text
SUMMARY / ANSWER:
The provided context does not contain information regarding the current CPI inflation trend or headline inflation outlook for the year 2026. While the RBI Bulletin June 2026 (rbi, p.45) notes that inflation ranged from 1.0% to 6.2% across states with a majority between 2% and 4%, and mentions a broad-based pickup in food prices continuing into June 2026, it does not specify the national headline inflation figure or its forward-looking trend for that period. The other document (economic_survey, p.16) only provides historical data up to December 2025. Therefore, a specific current trend and outlook cannot be determined from the text.
```

---

### Q029: How are food and fuel prices impacting overall inflation in India?

- **Category:** `Macro`
- **Status:** 🟢 **Answered**
- **Latency:** `10.81s`
- **Dispatched Sources:** `macro`
- **Rendered Cards:** `brief`
- **Evaluation Intent:** *Food and energy inflation contribution*
- **Grounded Citations:** *karnataka_des*

#### Application Response Output:
```text
SUMMARY / ANSWER:
Food and fuel prices impact overall inflation differently depending on the index used, as their weights vary significantly. In the CPI, which measures consumer-level inflation, food items carry a higher weight, making the index more sensitive to food price changes. Conversely, the fuel group has a significantly higher weight in the WPI, which tracks wholesale prices. Consequently, fluctuations in food prices disproportionately affect the CPI, while fuel price movements have a larger impact on the WPI. During April-December 2025-26, All-India WPI inflation rose to 1.82 per cent, while CPI inflation increased to 3.28 per cent, reflecting these structural differences in how the indices weigh these essential commodities (karnataka_des, p.55).
```

---

### Q030: What is the RBI's current monetary policy stance and repo rate outlook?

- **Category:** `Macro`
- **Status:** 🟢 **Answered**
- **Latency:** `14.28s`
- **Dispatched Sources:** `macro`
- **Rendered Cards:** `brief`
- **Evaluation Intent:** *RBI monetary policy stance and interest rates*
- **Grounded Citations:** *economic_survey, rbi*

#### Application Response Output:
```text
SUMMARY / ANSWER:
Based on the provided context, the Reserve Bank of India (RBI) has adopted a **neutral monetary policy stance**, a position maintained since June 2025 (economic_survey, p.138) and reaffirmed in the June 2026 statement (rbi, p.9). Consequently, the policy repo rate under the Liquidity Adjustment Facility (LAF) remains **unchanged at 5.25 per cent** (rbi, p.9; economic_survey, p.138). This rate level is supported by the Standing Deposit Facility (SDF) at 5.00 per cent and the Marginal Standing Facility (MSF) and Bank Rate at 5.50 per cent (rbi, p.9). The MPC decided to hold rates steady despite global turbulence and supply chain disruptions, aiming to balance price stability with resilient domestic demand while monitoring potential second-round inflation effects (rbi, p.9).
```

---

### Q031: How is credit growth trending in the Indian banking and NBFC sectors?

- **Category:** `Macro`
- **Status:** 🟢 **Answered**
- **Latency:** `20.13s`
- **Dispatched Sources:** `macro`
- **Rendered Cards:** `brief`
- **Evaluation Intent:** *Sectoral bank and NBFC credit growth*
- **Grounded Citations:** *economic_survey, rbi*

#### Application Response Output:
```text
SUMMARY / ANSWER:
Credit growth in India's banking and NBFC sectors is trending robustly, driven by strong flows to MSMEs and services. Non-food bank credit grew 58.6% year-on-year as of December 2025, while non-bank sources rose 23.8% (economic_survey, p.145). Specifically, bank credit to the MSME sector surged 21.8% in November 2025, with micro and small enterprises seeing a 24.6% increase (economic_survey, p.145). The overall flow of financial resources to the commercial sector reached ₹30.8 lakh crore in April-December 2025, up 44.7% from the prior year (economic_survey, p.145). Additionally, SCB credit growth has outpaced deposit growth since September 2025, fueled by lending to large industries and the services sector, including NBFCs and commercial real estate (rbi, p.52).
```

---

### Q032: What is the credit gap for MSMEs in India according to government reports?

- **Category:** `Macro`
- **Status:** 🟢 **Answered**
- **Latency:** `8.12s`
- **Dispatched Sources:** `macro`
- **Rendered Cards:** `brief`
- **Evaluation Intent:** *MSME formal financing gap*
- **Grounded Citations:** *msme*

#### Application Response Output:
```text
SUMMARY / ANSWER:
The provided context does not contain information regarding the specific credit gap for MSMEs in India according to government reports. While the document details the Credit Guarantee Fund Trust for Micro and Small Enterprises (CGTMSE) achievements, such as ₹ 12.39 lakh crore in extended guarantees (msme, p.93), and outlines the MSME sector's contribution to GDP and exports (msme, p.7), it does not quantify the existing credit gap.
```

---

### Q033: What are the major challenges faced by micro and small enterprises in accessing formal credit?

- **Category:** `Macro`
- **Status:** 🟢 **Answered**
- **Latency:** `10.41s`
- **Dispatched Sources:** `macro`
- **Rendered Cards:** `brief`
- **Evaluation Intent:** *MSME credit barriers and collateral constraints*
- **Grounded Citations:** *economic_survey*

#### Application Response Output:
```text
SUMMARY / ANSWER:
Based on the provided context, major challenges for microfinance institutions (MFIs) serving micro and small enterprises include the limited availability of a primary and standardized approach to assess household income, often forcing reliance on inaccurate in-house estimation methods (economic_survey, p.153). Additionally, MFIs frequently lack visibility over specific loan types like gold, agricultural, and cooperative society credits, which constrains their ability to calculate accurate repayment obligations (economic_survey, p.153). The sector also struggles with offering tailored credit with differential pricing for different categories (economic_survey, p.153). Finally, the continued growth of the sector hinges on strengthening enabling infrastructure for creditworthiness assessment and ensuring responsible lending practices to manage cyclical volatility (economic_survey, p.153).
```

---

### Q034: What is Karnataka's Gross State Domestic Product (GSDP) growth performance?

- **Category:** `Macro`
- **Status:** 🟢 **Answered**
- **Latency:** `11.33s`
- **Dispatched Sources:** `macro`
- **Rendered Cards:** `brief`
- **Evaluation Intent:** *Karnataka state-level GDP and growth rate*
- **Grounded Citations:** *karnataka_des*

#### Application Response Output:
```text
SUMMARY / ANSWER:
Based on the provided context, Karnataka's Gross State Domestic Product (GSDP) for the year 2025-26 is estimated at Rs. 32,81,065 crore at current prices, registering a growth rate of 12.9 per cent (document, p.42). The text notes that GSDP growth rates, alongside per capita income, reflect the direction and pace of economic activities driven by the Agriculture, Industry, and Services sectors (document, p.42). While the document defines GSDP as the aggregate monetary value of goods and services produced within the state's boundaries (document, p.42), it does not provide historical growth data or performance trends for previous years, only the specific advance estimate for 2025-26.
```

---

### Q035: How is the MSME sector positioned in Karnataka's regional economy?

- **Category:** `Macro`
- **Status:** 🟢 **Answered**
- **Latency:** `11.23s`
- **Dispatched Sources:** `macro`
- **Rendered Cards:** `brief`
- **Evaluation Intent:** *Karnataka MSME employment and enterprise share*
- **Grounded Citations:** *karnataka_des*

#### Application Response Output:
```text
SUMMARY / ANSWER:
The MSME sector is a vital pillar of Karnataka's economy, with 24.86 lakh registered entities on the Udyam Portal as of December 2025, generating employment for 235.27 lakh persons (karnataka_des, p.151). To support this sector, the state allocated Rs.69,211.08 lakh during 2025-26, with Rs.28,442.84 lakh utilized by December 2025 through various schemes including capital and interest subsidies (karnataka_des, p.151). While the state also focuses on large and medium industries via the Clean Mobility Policy 2025-30, the MSME sector remains central to the regional economic structure through targeted financial support and cluster development programs (karnataka_des, p.151).
```

---

### Q036: What are the key findings from the SIDBI MSME Pulse report?

- **Category:** `Macro`
- **Status:** 🟢 **Answered**
- **Latency:** `8.09s`
- **Dispatched Sources:** `macro`
- **Rendered Cards:** `brief`
- **Evaluation Intent:** *SIDBI MSME credit quality and ticket size findings*
- **Grounded Citations:** *msme*

#### Application Response Output:
```text
SUMMARY / ANSWER:
The provided context does not contain key findings from the SIDBI MSME Pulse report. It details government initiatives such as the reduction of compliance requirements from seven to four, procurement data from the MSME Sambandh Portal (noting 40.77% of ₹1,35,770.63 crore procurement from 129 CPSEs), and the Aatmanirbhar Bharat package's ₹50,000 crore equity infusion, but it does not reference the specific SIDBI report or its findings.
```

---

### Q037: What is the formal versus informal credit split in Indian MSME financing?

- **Category:** `Macro`
- **Status:** 🟢 **Answered**
- **Latency:** `5.90s`
- **Dispatched Sources:** `macro`
- **Rendered Cards:** `brief`
- **Evaluation Intent:** *Institutional vs unorganized credit share*
- **Grounded Citations:** *msme*

#### Application Response Output:
```text
SUMMARY / ANSWER:
The provided context does not contain information regarding the formal versus informal credit split in Indian MSME financing. While the document mentions that the Ministry of MSME focuses on "Access to Credit" and "Formalization" as key objectives (msme, p.7), it does not offer specific data, percentages, or a breakdown of the credit distribution between formal and informal sectors.
```

---

### Q038: How is digital public infrastructure (DPI) influencing MSME credit delivery in India?

- **Category:** `Macro`
- **Status:** 🟢 **Answered**
- **Latency:** `12.10s`
- **Dispatched Sources:** `macro`
- **Rendered Cards:** `brief`
- **Evaluation Intent:** *Account Aggregator, OCEN, and UPI lending impact*
- **Grounded Citations:** *economic_survey*

#### Application Response Output:
```text
SUMMARY / ANSWER:
Digital Public Infrastructure (DPI) significantly enhances MSME credit delivery in India by enabling data-driven lending to underserved segments. The Account Aggregator framework provides lenders with verified data, such as bank transactions and GST records, facilitating credit access for first-time users. Furthermore, DPI payment interfaces like UPI supply critical transaction data that allows banks to assess creditworthiness effectively. This infrastructure supports schemes like PM SVANidhi and PMMY, which have expanded formal credit access to 30% of borrowers (up from 9%) and maintained low NPA rates of below 10% and 3.31%, respectively (economic_survey, p.158). By converting basic account access into active financial participation, DPI fosters a virtuous cycle of credit access, repayment discipline, and enterprise growth, proving that well-designed micro-credit interventions can successfully integrate marginalized populations into the formal financial system (economic_survey, p.158).
```

---

### Q039: What is the trend in industrial output and manufacturing PMI in India?

- **Category:** `Macro`
- **Status:** 🟢 **Answered**
- **Latency:** `13.23s`
- **Dispatched Sources:** `macro`
- **Rendered Cards:** `brief`
- **Evaluation Intent:** *Index of Industrial Production and manufacturing activity*
- **Grounded Citations:** *mospi, rbi*

#### Application Response Output:
```text
SUMMARY / ANSWER:
In May 2026, India's manufacturing sector showed robust expansion, with the Index of Industrial Production (IIP) recording a 5.5% year-on-year growth, supported by strong performance in the Electricity & Gas Supply sector (9.9%) (mospi, p.1). The Output Producer Price Index (OPPI) inflation for manufactured products rose to 9.4% in May, driven by high costs of energy, fuel, and raw materials (rbi, p.48). While the manufacturing input price PMI remained stable at elevated levels, the output price PMI moderated, suggesting potential profit margin squeezes despite continued expansionary activity (rbi, p.48). MoSPI has also adopted the Output PPI as the deflator for the IIP, affecting 36.02% of the index weight (mospi, p.1).
```

---

### Q040: What are the key government initiatives supporting MSME credit access in India?

- **Category:** `Macro`
- **Status:** 🟢 **Answered**
- **Latency:** `10.43s`
- **Dispatched Sources:** `macro`
- **Rendered Cards:** `brief`
- **Evaluation Intent:** *Credit guarantee and interest subvention schemes*
- **Grounded Citations:** *msme*

#### Application Response Output:
```text
SUMMARY / ANSWER:
The key government initiative supporting MSME credit access is the **PM Vishwakarma Scheme**, launched in September 2023 with an initial outlay of **₹ 13,000 crore** (msme, p.86). This scheme specifically targets artisans and craftspeople across 18 trades to enhance their quality of life and integrate them into value chains. While the Ministry of MSME broadly envisions a progressive sector by addressing challenges like "Access to Credit" and "Access to Finance" (msme, p.7), the PM Vishwakarma Scheme is the primary financial assistance program detailed in the provided text. Other initiatives focus on skill development, infrastructure, and technology rather than direct credit provision.
```

---

### Q041: How does rising rural demand support credit absorption in southern states?

- **Category:** `Macro`
- **Status:** 🟢 **Answered**
- **Latency:** `6.74s`
- **Dispatched Sources:** `macro`
- **Rendered Cards:** `brief`
- **Evaluation Intent:** *Rural economy, monsoon, and southern credit trends*
- **Grounded Citations:** *economic_survey*

#### Application Response Output:
```text
SUMMARY / ANSWER:
The provided context does not contain information regarding how rising rural demand specifically supports credit absorption in southern states. While the text details the consolidation of Regional Rural Banks (RRBs) into 28 entities and their improved financial performance, including a reduction in the GNPA ratio from 6.1% to 5.4% (economic_survey, p.147), it does not link these metrics to rising demand or specify the southern region's credit absorption dynamics.
```

---

### Q042: What is the economic outlook for co-operative banking in rural and semi-urban India?

- **Category:** `Macro`
- **Status:** 🟢 **Answered**
- **Latency:** `12.67s`
- **Dispatched Sources:** `macro`
- **Rendered Cards:** `brief`
- **Evaluation Intent:** *Co-operative credit structure and resilience*
- **Grounded Citations:** *economic_survey*

#### Application Response Output:
```text
SUMMARY / ANSWER:
The economic outlook for co-operative banking in rural and semi-urban India is positive, driven by structural reforms and improved financial health. The consolidation of Regional Rural Banks (RRBs) into 28 entities under the "One-State-One-RRB" principle has streamlined operations, while the adoption of unified Core Banking Solutions has enhanced efficiency (economic_survey, p.147). Financial performance has strengthened significantly, with RRBs achieving a record consolidated net profit of ₹7.6 thousand crore in FY24 and ₹6.8 thousand crore in FY25 (economic_survey, p.147). Furthermore, asset quality has notably improved, with the Gross Non-Performing Assets (GNPA) ratio in the agricultural sector declining from 6.1% in FY24 to 5.4% in FY25, marking the lowest level in 13 years (economic_survey, p.147). These indicators suggest a robust future for credit distribution to small farmers and marginalized groups in these regions.
```

---

### Q043: What are the key risk factors highlighted in the Economic Survey for the financial sector?

- **Category:** `Macro`
- **Status:** 🟢 **Answered**
- **Latency:** `13.19s`
- **Dispatched Sources:** `macro`
- **Rendered Cards:** `brief`
- **Evaluation Intent:** *Macro-financial risks and external headwinds*
- **Grounded Citations:** *economic_survey, ministry_of_finance*

#### Application Response Output:
```text
SUMMARY / ANSWER:
The Economic Survey highlights several key risk factors for the financial sector. First, the sector faces severe macro-financial stress scenarios, necessitating continued reforms to mobilize private capital (ministry_of_finance, p.49). Second, while globalized finance offers benefits, rapid geopolitical fragmentation has turned the sector into a channel for transmitting volatile global shocks to emerging markets (economic_survey, p.131). Third, specific vulnerabilities include high collateral requirements and complex application processes constraining MSME financing, creating a credit gap of 11 to 16 percent of GDP (ministry_of_finance, p.49). Finally, despite advanced oversight, the banking sector requires expanded cybersecurity crisis simulations and stress tests for cross-sectoral events to strengthen resilience against market-wide events (ministry_of_finance, p.49).
```

---

### Q044: How is export credit demand evolving among Indian small enterprises?

- **Category:** `Macro`
- **Status:** 🟢 **Answered**
- **Latency:** `8.28s`
- **Dispatched Sources:** `macro`
- **Rendered Cards:** `brief`
- **Evaluation Intent:** *Export credit trends for small exporters*
- **Grounded Citations:** *economic_survey*

#### Application Response Output:
```text
SUMMARY / ANSWER:
The provided context does not contain specific information regarding how export credit demand is evolving among Indian small enterprises. While the text notes that India's total exports reached a record USD 825.3 billion in FY25 (economic_survey, p.78) and that merchandise exports grew by 2.4% in April-December 2025 (economic_survey, p.78), it does not detail the credit demand patterns specifically for small enterprises. The document focuses instead on broader trends in bank credit, non-bank financing sources, and the current account balance.
```

---

### Q045: What are the key takeaways regarding employment and enterprise formalization in India?

- **Category:** `Macro`
- **Status:** 🟢 **Answered**
- **Latency:** `9.28s`
- **Dispatched Sources:** `macro`
- **Rendered Cards:** `brief`
- **Evaluation Intent:** *Udyam registration and formal job creation trends*
- **Grounded Citations:** *economic_survey*

#### Application Response Output:
```text
SUMMARY / ANSWER:
Recent labour market indicators suggest improving employment conditions supported by structural reforms, with quarterly averages pointing to a decline in the unemployment rate and a stabilising labour force participation rate (economic_survey, p.80). A key takeaway is the government's consolidation of 29 central laws into four Labour Codes to simplify compliance and extend security, notably by recognising gig and platform workers to facilitate their registration and inclusion in social security schemes, thereby promoting enterprise formalization (economic_survey, p.80). Additionally, government-led skilling initiatives aim to enhance employability through industry-aligned training, strengthening labour market resilience and aligning workforce capabilities with economic requirements (economic_survey, p.80).
```

---

### Q046: What is the competitive landscape for MSME lending in Karnataka?

- **Category:** `Competitive`
- **Status:** 🟢 **Answered**
- **Latency:** `18.67s`
- **Dispatched Sources:** `competitive`
- **Rendered Cards:** `brief`
- **Evaluation Intent:** *Karnataka MSME lending competitor overview*
- **Grounded Citations:** *Kinara Capital, SIDBI, Karnataka State Co-operative Apex Bank*

#### Application Response Output:
```text
SUMMARY / ANSWER:
The Karnataka MSME lending landscape features a mix of cooperative banks, NBFCs, and fintechs. Kinara Capital (document, p.1) offers collateral-free loans with 24-hour disbursement, contrasting with cooperative institutions like the Karnataka State Co-operative Apex Bank (document, p.2), which focus on agriculture and rural infrastructure. While cooperatives leverage local branch presence for relationship-led acquisition (document, p.3), they face threats from faster approval and digital onboarding by NBFCs and fintechs (document, p.3). Specific competitive advantages for cooperatives include rural product differentiation and local distribution networks (document, p.3). However, explicit MSME positioning and financial figures for most cooperatives are absent in public crawl data (document, p.4), creating a data gap for precise benchmarking. SIDBI supports the ecosystem via platforms like Udyam Assist (document, p.5). Ultimately, the market is defined by the tension between cooperatives' local reach and the agility of digital-first lenders.
```

---

### Q047: Which institutions are the key competitors for Karnataka co-operative banks?

- **Category:** `Competitive`
- **Status:** 🟢 **Answered**
- **Latency:** `13.67s`
- **Dispatched Sources:** `competitive`
- **Rendered Cards:** `brief`
- **Evaluation Intent:** *Regional peer banks and private NBFC competitors*
- **Grounded Citations:** *Bhatkal Urban Co-operative Bank, Karnataka State Financial Corporation, Karnataka State Co-operative Apex Bank, Kaujalgi Urban Co-operative Bank*

#### Application Response Output:
```text
SUMMARY / ANSWER:
The provided indexed passages do not explicitly list key competitors for Karnataka co-operative banks. While the text details the operations of the Karnataka State Co-operative Apex Bank, Karnataka State Financial Corporation, and specific urban co-operative banks like Bhatkal and Kaujalgi, it lacks a comparative analysis or a direct statement identifying their primary competitors. Therefore, a direct comparison of institutions based on market share, rates, or competitive positioning cannot be made from the available evidence.
```

---

### Q048: What is the business profile and target segment of Kinara Capital in Karnataka?

- **Category:** `Competitive`
- **Status:** 🟢 **Answered**
- **Latency:** `12.53s`
- **Dispatched Sources:** `competitive`
- **Rendered Cards:** `brief`
- **Evaluation Intent:** *Kinara Capital MSME focus and operations*
- **Grounded Citations:** *Kinara Capital*

#### Application Response Output:
```text
SUMMARY / ANSWER:
Kinara Capital is a fintech NBFC founded in 2011 by Hardika Shah, registered with the RBI, focused on driving last-mile financial inclusion for MSMEs across India (document, p.1). Its business profile centers on offering business loans to micro, small, and medium enterprises, with a mission to empower entrepreneurs through equal access to capital (document, p.1). The institution targets underserved MSMEs, partnering with mission-aligned investors to unlock market opportunities in this sector (document, p.2). While the indexed evidence confirms Kinara's presence in Karnataka via a location selection option, it does not specify a distinct Karnataka-only target segment or detailed business profile unique to the state compared to its national MSME focus. Specific loan ticket sizes, such as up to Rs. 30 lakhs, are mentioned generally but not explicitly tied to the Karnataka market in the provided text (document, p.2).
```

---

### Q049: What is the profile and market focus of SIDBI in MSME refinancing?

- **Category:** `Competitive`
- **Status:** 🟢 **Answered**
- **Latency:** `14.01s`
- **Dispatched Sources:** `competitive`
- **Rendered Cards:** `brief`
- **Evaluation Intent:** *SIDBI direct lending and refinance lines*
- **Grounded Citations:** *SIDBI*

#### Application Response Output:
```text
SUMMARY / ANSWER:
SIDBI (Small Industries Development Bank of India) is positioned as the benchmark for the MSME ecosystem rather than a direct peer to local co-operative lenders (document, p.1). Its profile includes leadership roles such as Chairman & Managing Director and Deputy Managing Directors, with a governance structure focused on single organizational objectives (document, p.1). The institution has established key mechanisms like CGTMSE, SMERA (now Acuité), and ISTSL to support the sector (document, p.1).

Regarding market focus, SIDBI operates through initiatives like the India Microfinance Equity Scheme and the Udyam Assist Platform (document, p.2). It actively monitors the sector via the MSME Outlook Survey Report and publishes regular "Small Business Spotlight" updates to track progress and challenges (document, p.2). While the text confirms SIDBI's role in accelerating enterprise growth through loan sanctions, it does not provide specific figures on refinancing ticket sizes, exact market share percentages, or precise turnaround times (document, p.1; p.2). Consequently, a direct quantitative comparison of refinancing metrics against other institutions cannot be made from the supplied evidence.
```

---

### Q050: What is the role and market presence of Karnataka State Co-operative Apex Bank?

- **Category:** `Competitive`
- **Status:** 🟢 **Answered**
- **Latency:** `22.45s`
- **Dispatched Sources:** `competitive`
- **Rendered Cards:** `brief`
- **Evaluation Intent:** *Karnataka Apex Bank rural and cooperative network*
- **Grounded Citations:** *Kaujalgi Urban Co-operative Bank, Bhatkal Urban Co-operative Bank, Karnataka State Co-operative Apex Bank*

#### Application Response Output:
```text
SUMMARY / ANSWER:
The Karnataka State Co-operative Apex Bank serves as the apex institution for Karnataka's cooperative movement, registered with DICGC and established to strengthen District Central Co-operative (DCC) Banks and Primary Agricultural Credit Societies (PACS) (document, p.1). Its market presence is defined by providing short-term finance for crop production/marketing and medium-term loans for agricultural infrastructure like irrigation and dairy (document, p.2). It extends cash credit to processing, marketing, and consumer cooperatives, as well as sugar factories, often under consortium arrangements (document, p.2). The bank also offers working capital loans to state and national-level co-operative institutions (document, p.2). Unlike local urban banks such as Kaujalgi or Bhatkal, which focus on specific districts with limited branch networks, the Apex Bank operates statewide, guiding policy and providing refinance assistance (document, p.2). It has received multiple awards from the Ministry of Cooperation and NABARD, reflecting its leadership role (document, p.2). Specific financial figures like market share or exact loan limits for the Apex Bank are not provided in the text.
```

---

### Q051: How does Karnataka State Financial Corporation (KSFC) support industrial lending?

- **Category:** `Competitive`
- **Status:** 🟢 **Answered**
- **Latency:** `14.75s`
- **Dispatched Sources:** `competitive`
- **Rendered Cards:** `brief`
- **Evaluation Intent:** *KSFC term lending and project finance*
- **Grounded Citations:** *Karnataka State Financial Corporation, Belgaum Industrial Co-operative Bank*

#### Application Response Output:
```text
SUMMARY / ANSWER:
The provided indexed passages do not contain specific details on how the Karnataka State Financial Corporation (KSFC) supports industrial lending, such as loan schemes, interest rates, or operational mechanisms. The documents list KSFC's contact information, branch locations (e.g., Bagalkot, Ballari, Bengaluru), and links to financial results and sector-wise assistance pages, but the content of these pages is not included in the text.

In contrast, the Belgaum Industrial Co-operative Bank explicitly supports local industries like handloom and small-scale manufacturing. It offers loan facilities against term deposit receipts up to 85% of the deposit value and has operated since 1948 to serve these sectors.

Therefore, while KSFC's industrial lending support is implied by its existence and listed "Sector-wise-assistance" links, the specific methods are absent from the provided evidence. (document, p.1)
```

---

### Q052: What is the profile and lending approach of National Co-operative Bank?

- **Category:** `Competitive`
- **Status:** 🟢 **Answered**
- **Latency:** `20.64s`
- **Dispatched Sources:** `competitive`
- **Rendered Cards:** `brief`
- **Evaluation Intent:** *National Co-op Bank urban micro-lending*
- **Grounded Citations:** *Kaujalgi Urban Co-operative Bank, Karnataka State Co-operative Apex Bank, National Co-operative Bank*

#### Application Response Output:
```text
SUMMARY / ANSWER:
The National Co-operative Bank (National Co-op Bank Ltd.) focuses on professionals and small businesses, offering products like Working Capital Term Loans and Shop Keeper's Loans. Eligibility requires a minimum two years of experience in the same field and membership in the Mumbai Vyapari Association Maharashtra Rojgar. The bank provides a concession rate of 0.25% p.a. on interest for women borrowers across Housing, Education, Gold, and Business loans. It also offers an Education Loan with a maximum ticket size of Rs. 1.00 lakh at 15% interest over 36 months. The bank emphasizes digital inclusion via mobile banking (MMID 9223126669) and direct disbursement to institutions. Unlike the community-rooted Kaujalgi Urban Co-operative Bank, which highlights rural development and partnerships with 1,500+ local businesses, the National Co-op Bank's profile centers on urban professional financing and specific eligibility criteria for entrepreneurs. (National Co-operative Bank, p.1; National Co-operative Bank, p.2)
```

---

### Q053: How do Urban Co-operative Banks like Bellary Urban and Bhatkal Urban compete in their districts?

- **Category:** `Competitive`
- **Status:** 🟢 **Answered**
- **Latency:** `18.29s`
- **Dispatched Sources:** `competitive`
- **Rendered Cards:** `brief`
- **Evaluation Intent:** *Urban co-operative positioning in North Karnataka*
- **Grounded Citations:** *Bhatkal Urban Co-operative Bank, Kaujalgi Urban Co-operative Bank, Bellary Urban Co-operative Bank*

#### Application Response Output:
```text
SUMMARY / ANSWER:
Bellary Urban Co-operative Bank competes through deep historical roots, having operated since 1916 with a mission to be a "World-class Indian Bank," offering a full suite of services including personal, home, and car loans (Bellary Urban, p.2). In contrast, Bhatkal Urban Co-operative Bank, established in 1964, focuses on localized branch presence in Uttara Kannada District and specific digital services like online computer banking and senior citizen benefits (Bhatkal Urban, p.1; p.4). While Bellary emphasizes its long-standing legacy and comprehensive loan portfolio, Bhatkal highlights operational convenience through multiple local branches and specialized online facilities. Neither institution provides specific interest rates or market share data in the provided text. Regional competitors like Kaujalgi Urban leverage extensive digital partnerships (200+ apps) and community initiatives, while Belgaum Industrial Co-operative Bank serves a defined district area with five branches (Kaujalgi Urban, p.1; Belgaum Industrial, p.1).
```

---

### Q054: What are the strengths of District Central Co-operative Banks like Belagavi DCCB and South Canara DCCB?

- **Category:** `Competitive`
- **Status:** 🟢 **Answered**
- **Latency:** `25.44s`
- **Dispatched Sources:** `competitive`
- **Rendered Cards:** `brief`
- **Evaluation Intent:** *DCCB district-level grassroots branch reach*
- **Grounded Citations:** *Kaujalgi Urban Co-operative Bank, Belagavi District Central Co-operative Bank, Belgaum Industrial Co-operative Bank*

#### Application Response Output:
```text
SUMMARY / ANSWER:
Based on the provided documents, specific comparative strengths for **South Canara DCCB** are absent; only **Belagavi DCCB** and **Kaujalgi Urban Co-operative Bank** details are available.

**Belagavi DCCB Strengths:**
*   **Longevity & Heritage:** Founded in 1919, it holds the distinction of being the first registered office of the bank in the region (document, p.1).
*   **Agricultural Focus:** It has disbursed Rs 1,22,489 Lakh via Kissan Credit Card to 3,35,360 farmers and supports the sugar industry with Rs 50,224 Lakh (document, p.1).
*   **Capital Structure:** Maintains a robust capital fund including paid-up capital, free reserves, and statutory provisions (document, p.2).

**Kaujalgi Urban Co-operative Bank Strengths:**
*   **Community Trust:** Grown from a village initiative to serve thousands across Belagavi with a focus on ethical banking and financial inclusion (document, p.4).
*   **Operational Speed:** Offers quick approval for immediate needs with minimal documentation (document, p.4).
*   **Social Responsibility:** Actively supports women entrepreneurs, SHGs, and skill development workshops (document, p.5).

**Gap:** No indexed evidence exists to compare these institutions directly or to provide data on South Canara DCCB.
```

---

### Q055: What is the profile and regional strength of South Canara DCCB in coastal Karnataka?

- **Category:** `Competitive`
- **Status:** 🟢 **Answered**
- **Latency:** `18.05s`
- **Dispatched Sources:** `competitive`
- **Rendered Cards:** `brief`
- **Evaluation Intent:** *South Canara DCCB agricultural and commercial lending*
- **Grounded Citations:** *South Canara District Central Co-operative Bank, Belagavi District Central Co-operative Bank*

#### Application Response Output:
```text
SUMMARY / ANSWER:
South Canara District Central Co-operative Bank (SCDCB) demonstrates strong regional concentration in coastal Karnataka, specifically within Udupi and Dakshina Kannada districts. Its branch network spans key towns including Kundapura, Udupi, Belthangady, Sullia, Moodabidri, and Puttur, with a total of at least 18 branches listed (document, p.2). The bank maintains a robust capital base, reporting a capital fund of Rs. 47,599.89 lakh as of March 2025 (document, p.4).

In contrast, the Belagavi District Central Co-operative Bank (BDCC), located in North Karnataka, was founded in 1919 and focuses heavily on the sugar sector, having disbursed Rs. 50,224 lakh to sugar factories (document, p.3). While BDCC highlights its Kissan Credit Card reach to over 3.35 lakh farmers, SCDCB's specific farmer loan figures are absent in the provided text. Both institutions share similar strategic strengths, including established digital channels and local branch networks supporting relationship-led distribution, though both face threats from fintech and NBFC competition (document, p.5).
```

---

### Q056: How do NBFC interest rates on MSME loans compare with co-operative bank rates?

- **Category:** `Competitive`
- **Status:** 🟢 **Answered**
- **Latency:** `21.79s`
- **Dispatched Sources:** `competitive`
- **Rendered Cards:** `brief`
- **Evaluation Intent:** *Interest rate spread between NBFCs and co-operatives*
- **Grounded Citations:** *Kinara Capital, National Co-operative Bank, Karnataka State Co-operative Apex Bank*

#### Application Response Output:
```text
SUMMARY / ANSWER:
The provided documents do not contain specific interest rate figures for NBFCs on MSME loans to allow for a direct numerical comparison with co-operative bank rates.

However, the text indicates that NBFCs like Kinara Capital often compete on "clearer pricing," "faster approval," and "digital onboarding" compared to traditional lenders (Karnataka State Co-operative Apex Bank, p.1). Kinara Capital highlights "collateral-free" loans and "quicker disbursals" as key differentiators, noting that NBFCs are "more proactive in innovating financial products" due to greater flexibility (Kinara Capital, p.3).

Conversely, co-operative banks in Karnataka offer specific rates for small businesses and working capital. For instance, Belagavi District Central Co-operative Bank lists rates ranging from 9% to 12.5% for various working capital schemes (Belagavi District Central Co-operative Bank, p.1). The National Co-operative Bank offers a concession rate of 0.25% p.a. for women borrowers on business loans (National Co-operative Bank, p.1). While co-ops provide relationship-led acquisition via local presence (Karnataka State Co-operative Apex Bank, p.1), the exact NBFC rates required for a precise comparison are absent from the supplied evidence.
```

---

### Q057: What are the collateral requirements typically sought by NBFCs versus co-operative lenders?

- **Category:** `Competitive`
- **Status:** 🟢 **Answered**
- **Latency:** `20.36s`
- **Dispatched Sources:** `competitive`
- **Rendered Cards:** `brief`
- **Evaluation Intent:** *Secured vs unsecured lending requirements*
- **Grounded Citations:** *Kaujalgi Urban Co-operative Bank, National Co-operative Bank, Karnataka State Co-operative Apex Bank*

#### Application Response Output:
```text
SUMMARY / ANSWER:
The provided documents do not contain specific collateral requirements for NBFCs, making a direct comparison impossible. However, Karnataka co-operative lenders (e.g., Karnataka State Co-operative Apex Bank) typically seek varied security based on loan size and purpose. For loans up to Rs. 10 lakhs, no security is required if jointly taken with a parent/guardian, though surity is mandatory. For loans above Rs. 10 lakhs, collateral security equal to 100% of the loan amount is required, or a co-obligant with net worth not less than the loan amount. Specific categories like medical courses demand immovable property security equal to 150% of the loan amount. Acceptable forms include land, buildings, government securities, gold, and deposits. Additionally, loans above Rs. 25,000 require approved securities, while those up to Rs. 25,000 require a third-party co-obligation. (Karnataka State Co-operative Apex Bank, p.1-2)
```

---

### Q058: How do fintech and digital NBFCs compete on loan turnaround time (TAT)?

- **Category:** `Competitive`
- **Status:** 🟢 **Answered**
- **Latency:** `16.08s`
- **Dispatched Sources:** `competitive`
- **Rendered Cards:** `brief`
- **Evaluation Intent:** *Turnaround time and digital underwriting speed*
- **Grounded Citations:** *Kaujalgi Urban Co-operative Bank, Kinara Capital, SIDBI, Karnataka State Co-operative Apex Bank*

#### Application Response Output:
```text
SUMMARY / ANSWER:
Fintechs and digital NBFCs compete on loan turnaround time (TAT) by leveraging faster approval processes and digital onboarding, a direct threat to traditional lenders (document, p.1). Specifically, Kinara Capital, a digital NBFC, disburses collateral-free MSME loans in just 24 hours with minimal documentation (document, p.1). In contrast, cooperative banks rely on local branch presence for relationship-led acquisition, which may not match the speed of purely digital-first models (document, p.1). While cooperatives offer rural differentiation, they face pressure to modernize digital channels to compete with fintechs on speed (document, p.1). No specific TAT figures are provided for the cooperative institutions in the supplied text, creating a data gap for direct comparison.
```

---

### Q059: What is the Month-on-Month (MoM) loan repayment efficiency trend across recent cohorts?

- **Category:** `Competitive`
- **Status:** 🟢 **Answered**
- **Latency:** `14.02s`
- **Dispatched Sources:** `competitive`
- **Rendered Cards:** `brief`
- **Evaluation Intent:** *Loan vintage efficiency tracking (Dec 2025 - June 2026)*
- **Grounded Citations:** *Kinara Capital, Karnataka State Co-operative Apex Bank*

#### Application Response Output:
```text
SUMMARY / ANSWER:
The provided indexed passages do not contain specific data on Month-on-Month (MoM) loan repayment efficiency trends across recent cohorts for any institution. While documents describe general repayment structures, such as flexible tenures for Kinara Capital (NBFC) and installment options for Karnataka State Co-operative Apex Bank, they lack quantitative trend analysis or efficiency metrics. Consequently, a direct comparison of MoM efficiency between these lenders cannot be made based on the available text. (All documents, pp.1-18)
```

---

### Q060: How has GICC operational collection efficiency improved from Dec 2025 to June 2026?

- **Category:** `Competitive`
- **Status:** 🟢 **Answered**
- **Latency:** `15.74s`
- **Dispatched Sources:** `competitive`
- **Rendered Cards:** `brief`
- **Evaluation Intent:** *Collection efficiency MoM improvement (+3.8%)*
- **Grounded Citations:** *Karnataka State Financial Corporation, SIDBI, Karnataka State Co-operative Apex Bank, National Co-operative Bank*

#### Application Response Output:
```text
SUMMARY / ANSWER:
The provided indexed passages do not contain specific operational collection efficiency metrics (e.g., recovery rates, days past due) for GICC between December 2025 and June 2026. While the SIDBI Microfinance Pulse section notes a sector-wide decline in delinquency from 8.53% in March 2025 to 2.26% in March 2026, it does not offer granular data for GICC during the requested period (document, p.1). Consequently, a direct comparison of GICC's operational improvement cannot be made based on the available evidence.
```

---

### Q061: What are the key white spaces and underserved borrower segments in Karnataka MSME lending?

- **Category:** `Competitive`
- **Status:** 🟢 **Answered**
- **Latency:** `19.78s`
- **Dispatched Sources:** `competitive`
- **Rendered Cards:** `brief`
- **Evaluation Intent:** *Unmet credit demand in micro-enterprises and women entrepreneurs*
- **Grounded Citations:** *Kinara Capital, SIDBI, Karnataka State Co-operative Apex Bank*

#### Application Response Output:
```text
SUMMARY / ANSWER:
The provided indexed passages do not explicitly list specific "white spaces" or "underserved borrower segments" in Karnataka MSME lending. However, they highlight several gaps and opportunities:

1.  **Women Entrepreneurs:** Kinara Capital specifically targets this segment with "HerVikas loans" tailored for women-owned businesses, suggesting a niche focus area (Kinara Capital, p.2).
2.  **Digital/Process Gaps:** Multiple co-operative banks (e.g., Bellary, Kaujalgi, Belgaum) identify that their public information is fragmented and MSME positioning is not explicit, indicating a need for clearer product journeys and digital rails (Bellary Urban Co-operative Bank, p.2).
3.  **Competition Pressure:** The documents note that co-operatives face threats from digital-first MSME platforms, implying a potential white space in seamless, technology-driven lending experiences (Kaujalgi Urban Co-operative Bank, p.2).

No specific underserved sectors (e.g., specific industries) or financial figures regarding these gaps are provided in the text.
```

---

### Q062: How do regional co-operatives maintain borrower loyalty in semi-urban belts?

- **Category:** `Competitive`
- **Status:** 🟢 **Answered**
- **Latency:** `18.58s`
- **Dispatched Sources:** `competitive`
- **Rendered Cards:** `brief`
- **Evaluation Intent:** *Relationship-based lending vs algorithmic underwriting*
- **Grounded Citations:** *Kaujalgi Urban Co-operative Bank, Karnataka State Co-operative Apex Bank*

#### Application Response Output:
```text
SUMMARY / ANSWER:
Regional co-operatives in semi-urban belts like Belagavi maintain loyalty through deep community integration and tailored financial products. Kaujalgi Urban Co-operative Bank explicitly prioritizes "community-first initiatives," leveraging a network of 1,500+ local partners and offering flexible repayment and quick approvals to serve thousands across the district (Kaujalgi Urban Co-operative Bank, p.2). This approach blends modern technology with traditional values to foster trust.

In contrast, the Karnataka State Co-operative Apex Bank focuses on systemic support rather than direct borrower engagement. It facilitates crop marketing loans and provides refinance assistance to lower-level societies, ensuring liquidity for agricultural operations but lacking specific details on direct borrower loyalty mechanisms (Karnataka State Co-operative Apex Bank, p.1). While the Apex Bank outlines broad policies for financing marketing of crops, it does not detail the localized relationship-building strategies that institutions like Kaujalgi employ to secure member retention in semi-urban areas.
```

---

### Q063: What digital lending and underwriting capabilities do private NBFCs deploy in Karnataka?

- **Category:** `Competitive`
- **Status:** 🟢 **Answered**
- **Latency:** `21.26s`
- **Dispatched Sources:** `competitive`
- **Rendered Cards:** `brief`
- **Evaluation Intent:** *Fintech automated credit scoring and bank statement analysis*
- **Grounded Citations:** *Kaujalgi Urban Co-operative Bank, Kinara Capital, Karnataka State Financial Corporation, Karnataka State Co-operative Apex Bank*

#### Application Response Output:
```text
SUMMARY / ANSWER:
Private NBFCs like Kinara Capital deploy digital capabilities focused on fintech-driven financial inclusion, offering short-term working capital loans with minimal documentation and digital onboarding (Kinara Capital). They utilize digital platforms to foster financial literacy and provide customized solutions for MSMEs (Kinara Capital).

In contrast, Karnataka's co-operative institutions emphasize local branch presence for relationship-led acquisition rather than pure digital-first models. While Kaujalgi Urban Co-operative Bank partners with 200+ digital platforms and offers mobile/internet banking, its core strength remains community-focused distribution in Belagavi (Kaujalgi Urban Co-operative Bank). Other co-ops like KSFC and Belagavi District Central Co-operative Bank have established web presences but lack explicit digital underwriting details in available data (Karnataka State Financial Corporation; Belagavi District Central Co-operative Bank).

A key gap exists regarding specific digital underwriting algorithms, automated credit scoring models, or exact digital turnaround times for private NBFCs in Karnataka, as these operational metrics are absent from the provided texts. Co-ops are noted to face competition from digital-first lenders on faster approval and clearer pricing (Karnataka State Co-operative Apex Bank).
```

---

### Q064: How do competitor institutions leverage CGTMSE credit guarantee schemes?

- **Category:** `Competitive`
- **Status:** 🟢 **Answered**
- **Latency:** `15.07s`
- **Dispatched Sources:** `competitive`
- **Rendered Cards:** `brief`
- **Evaluation Intent:** *Collateral-free credit guarantee adoption by competitors*
- **Grounded Citations:** *Karnataka State Financial Corporation, SIDBI*

#### Application Response Output:
```text
SUMMARY / ANSWER:
The provided indexed passages do not contain specific details on how competitor institutions leverage the CGTMSE credit guarantee scheme, such as utilization rates, specific product structures, or operational workflows.

However, the documents indicate that SIDBI, established in 2000, is a key entity associated with the Credit Guarantee Fund Trust for Micro and Small Enterprises (CGTMSE) and has leveraged technology to improve operational efficiencies within the scheme (SIDBI, p.3). The text notes that CGTMSE has completed 25 years of establishment by July 2025, facilitating credit access for the MSE sector (SIDBI, p.3).

While the Karnataka State Financial Corporation and SIDBI both possess local presence and MSME relevance, neither document explicitly describes their specific strategies for leveraging CGTMSE compared to one another. The available evidence confirms the existence of the scheme and SIDBI's role but lacks the comparative operational details requested (SIDBI, p.3; Karnataka State Financial Corporation, p.1).
```

---

### Q065: What are the main competitive threats posed by specialized MSME NBFCs to co-operative banks?

- **Category:** `Competitive`
- **Status:** 🟢 **Answered**
- **Latency:** `19.68s`
- **Dispatched Sources:** `competitive`
- **Rendered Cards:** `brief`
- **Evaluation Intent:** *Market share encroachment by agile fintechs*
- **Grounded Citations:** *Bellary Urban Co-operative Bank, Karnataka State Co-operative Apex Bank, Kaujalgi Urban Co-operative Bank, Bhatkal Urban Co-operative Bank, Belgaum Industrial Co-operative Bank*

#### Application Response Output:
```text
SUMMARY / ANSWER:
Specialized MSME NBFCs pose three primary competitive threats to Karnataka co-operative lenders:

1.  **Superior Operational Efficiency:** NBFCs and fintech lenders compete on faster approval processes, clearer pricing structures, and streamlined digital onboarding, which co-operatives often lack (Karnataka State Co-operative Apex Bank, p.1).
2.  **Digital Disadvantage:** Co-operatives struggle to match the digital-channel coverage of digital-first MSME platforms, potentially losing customers seeking convenience (Karnataka State Co-operative Apex Bank, p.1; Belgaum Industrial Co-operative Bank, p.1).
3.  **Credit Quality Risks:** Increased competition may exacerbate credit-quality pressure, particularly in local, agriculture, and unsecured MSME segments where co-operatives hold significant exposure (Karnataka State Co-operative Apex Bank, p.1).

While co-operatives leverage local branch presence for relationship-led acquisition, they face risks if product rates and eligibility rules are not refreshed periodically to match agile NBFC offerings (Karnataka State Co-operative Apex Bank, p.1). Specific rates or ticket sizes for NBFCs are not provided in the supplied text.
```

---

### Q066: How does our MSME portfolio growth compare with the wider Indian MSME credit growth rate?

- **Category:** `Hybrid`
- **Status:** 🟢 **Answered**
- **Latency:** `96.41s`
- **Dispatched Sources:** `db, macro`
- **Rendered Cards:** `brief, error`
- **Evaluation Intent:** *Internal MSME portfolio vs national macro credit growth*
- **Grounded Citations:** *economic_survey*

#### Application Response Output:
```text
SUMMARY / ANSWER:
Based on the provided context, the specific wider Indian MSME credit growth rate is not explicitly stated as a single aggregate figure. However, the document highlights that in November 2025, total bank credit to the MSME sector increased by 21.8% year-on-year (up from 13% in November 2024) (economic_survey, p.145). Furthermore, credit extended specifically to micro and small enterprises within the sector registered a 24.6% increase year-on-year in November 2025 (economic_survey, p.145). The text also notes a 44.7% year-on-year increase in the overall flow of resources to the commercial sector between April and December 2025 (economic_survey, p.145).
```

---

### Q067: Compare our current PAR 30 delinquency (4.18%) against the national MSME sector NPA trends.

- **Category:** `Hybrid`
- **Status:** 🟢 **Answered**
- **Latency:** `40.25s`
- **Dispatched Sources:** `db, macro`
- **Rendered Cards:** `chart, brief`
- **Evaluation Intent:** *Internal delinquency vs industry NPA averages*
- **Grounded Citations:** *economic_survey*

#### Application Response Output:
```text
HEADLINE: PAR 30 (As at 21 Aug 2026)
SUMMARY / ANSWER:
Our current PAR 30 delinquency stands at 0.27% as of 21 August 2026, which is significantly lower than the 4.18% figure you cited for comparison. However, a direct comparison against national MSME sector NPA trends cannot be made because the provided findings contain no data or analysis regarding those specific national trends. The available macro information only defines the MSME acronym without offering the required sectoral performance metrics. Consequently, while our internal PAR 30 is quantified, the external benchmark data necessary for a full comparison is missing from the source material.

CHART SPEC: Type=kpi, Title=PAR 30
COLUMNS: PAR 30
SAMPLE ROWS (1 total): [{"par_30": 0.26855264734033535}]
```

---

### Q068: How do our loan interest rates compare with competitor NBFC rates and the RBI repo rate?

- **Category:** `Hybrid`
- **Status:** 🟢 **Answered**
- **Latency:** `41.40s`
- **Dispatched Sources:** `db, macro, competitive`
- **Rendered Cards:** `chart, brief, brief`
- **Evaluation Intent:** *Lending yields vs competitor pricing and policy rate*
- **Grounded Citations:** *National Co-operative Bank, Karnataka State Co-operative Apex Bank, Kinara Capital, SIDBI, rbi*

#### Application Response Output:
```text
HEADLINE: List the interest rates present in our loan book (Generated query — not a reviewed metric)
SUMMARY / ANSWER:
Our loan book shows a highest concentration of 3,740 loans at an 18.0% interest rate, though this specific figure is derived from a validated read-only query rather than a reviewed metric. In comparison, the RBI has maintained its policy repo rate unchanged at 5.25% to address domestic inflationary pressures amidst global economic turbulence. While specific rates for Karnataka State Co-operative Apex Bank (11.00%) and Karnataka State Financial Corporation (4%) are available, the provided evidence does not contain specific numerical interest rates for competitor NBFCs, only noting that their pricing varies by lender and credit profile. Consequently, a direct numerical comparison between our rates and competitor NBFC rates cannot be made with the current data.

CHART SPEC: Type=bar, Title=List the interest rates present in our loan book
COLUMNS: Interest Rate, Loan Count
SAMPLE ROWS (8 total): [{"interest_rate": 16.0, "loan_count": 33}, {"interest_rate": 16.5, "loan_count": 145}, {"interest_rate": 17.0, "loan_count": 1060}]
```

---

### Q069: How does our collection efficiency of 97.8% benchmark against regional co-operative peer standards?

- **Category:** `Hybrid`
- **Status:** 🟢 **Answered**
- **Latency:** `31.44s`
- **Dispatched Sources:** `db, competitive`
- **Rendered Cards:** `chart, brief`
- **Evaluation Intent:** *Internal collection efficiency vs peer co-operative performance*
- **Grounded Citations:** *Kaujalgi Urban Co-operative Bank, Karnataka State Co-operative Apex Bank*

#### Application Response Output:
```text
HEADLINE: Collection efficiency (2026-08-21)
SUMMARY / ANSWER:
Our collection efficiency of 97.8% cannot be benchmarked against regional co-operative peer standards because the available data contains no specific metrics, such as recovery rates or turnaround times, for any listed Karnataka co-operative lenders. While the Karnataka State Co-operative Apex Bank and Belgaum Industrial Co-operative Bank are mentioned, neither they nor other institutions like Kaujalgi or National Co-operative Bank disclose quantitative data regarding their collection performance. Consequently, no direct comparison of peer standards can be made based on the available text.

CHART SPEC: Type=kpi, Title=Collection efficiency
COLUMNS: Collection efficiency
SAMPLE ROWS (1 total): [{"collection_efficiency": null}]
```

---

### Q070: How does our gold loan disbursement trend align with macro gold price movements and demand?

- **Category:** `Hybrid`
- **Status:** 🟢 **Answered**
- **Latency:** `79.14s`
- **Dispatched Sources:** `db, macro`
- **Rendered Cards:** `brief, chart`
- **Evaluation Intent:** *Gold loan portfolio growth vs commodity macro trends*
- **Grounded Citations:** *economic_survey*

#### Application Response Output:
```text
HEADLINE: Show our gold loan disbursement trend over time (Generated query — not a reviewed metric)
SUMMARY / ANSWER:
Our gold loan disbursement trend shows a peak of ₹47.38 Cr on 2026-05-01, representing the highest total disbursed amount across ten returned monthly values since 2023. However, we cannot align this trend with macro gold price movements or demand because the provided findings lack specific quantitative data on gold prices or demand volumes, offering only a qualitative note that core inflation has been influenced by higher prices for precious metals. Consequently, a direct comparison between our disbursement figures and external market dynamics is not possible with the current evidence.

CHART SPEC: Type=bar, Title=Show our gold loan disbursement trend over time
COLUMNS: Month, Total Disbursed
SAMPLE ROWS (10 total): [{"month": "2025-10-01", "total_disbursed": 5950000.0}, {"month": "2025-11-01", "total_disbursed": 28000000.0}, {"month": "2025-12-01", "total_disbursed": 88360000.0}]
```

---

### Q071: In light of Karnataka's GSDP growth, how is our branch-level disbursement distributed across districts?

- **Category:** `Hybrid`
- **Status:** 🔴 **Error**
- **Latency:** `94.13s`
- **Dispatched Sources:** `db, macro`
- **Rendered Cards:** `error, error`
- **Evaluation Intent:** *Branch disbursement spread vs state economic growth poles*

#### Application Response Output:
```text
ERROR DETAIL: No intelligence source produced a usable answer.
```

---

### Q072: How does our average loan ticket size compare with microfinance and NBFC product offerings?

- **Category:** `Hybrid`
- **Status:** 🟢 **Answered**
- **Latency:** `65.34s`
- **Dispatched Sources:** `db, competitive`
- **Rendered Cards:** `chart, brief`
- **Evaluation Intent:** *Ticket size distribution vs competitor product spectrum*
- **Grounded Citations:** *Kinara Capital, SIDBI*

#### Application Response Output:
```text
HEADLINE: Average ticket size (all time)
SUMMARY / ANSWER:
Our average loan ticket size stands at ₹3.98 lakhs, calculated as the total sanctioned amount divided by the number of loans. However, a direct comparison with microfinance or NBFC product offerings cannot be made because the available evidence does not quantify the average ticket sizes for these competitors, despite confirming that entities like Kinara Capital and SIDBI offer relevant loan schemes. Consequently, while our internal metric is established, the external benchmark data required for a comparative analysis is missing from the provided sources.

CHART SPEC: Type=kpi, Title=Average ticket size
COLUMNS: Average ticket size
SAMPLE ROWS (1 total): [{"avg_ticket_size": 398219.868242656}]
```

---

### Q073: How does our repayment schedule performance correlate with seasonal agricultural and MSME cash flows?

- **Category:** `Hybrid`
- **Status:** 🟢 **Answered**
- **Latency:** `31.87s`
- **Dispatched Sources:** `db, macro`
- **Rendered Cards:** `analysis, brief`
- **Evaluation Intent:** *Repayment cash flow timing vs seasonal macro cycles*
- **Grounded Citations:** *economic_survey*

#### Application Response Output:
```text
HEADLINE: Portfolio health
SUMMARY / ANSWER:
Our repayment schedule performance currently shows no deviations across six key indicators, indicating stability within established thresholds. However, the available data does not contain specific information regarding the seasonal timing of cash inflows or outflows for either the agricultural or MSME sectors. While the text notes that the agriculture sector's average GVA growth ranged between 4.0% and 7.2% from FY20 to FY24 and highlights robust MSME credit growth of 21.8% in November 2025, it does not describe the specific seasonal patterns required to correlate these with repayment schedules. Consequently, a direct comparison of our repayment performance against seasonal cash flow patterns cannot be derived from the available passages.
```

---

### Q074: How do our portfolio delinquency levels in MSME schemes compare with SIDBI industry benchmarks?

- **Category:** `Hybrid`
- **Status:** 🟢 **Answered**
- **Latency:** `25.09s`
- **Dispatched Sources:** `db, macro`
- **Rendered Cards:** `brief, chart`
- **Evaluation Intent:** *Scheme-wise delinquency vs SIDBI Pulse indicators*
- **Grounded Citations:** *msme, ministry_of_finance, mospi*

#### Application Response Output:
```text
HEADLINE: PAR 30 and PAR 60 and PAR 90 and NPA ratio by scheme (As at 21 Aug 2026)
SUMMARY / ANSWER:
Our Dairy Loan scheme currently holds the highest PAR 30 delinquency level at 1.2% as of 21 August 2026. However, a direct comparison with SIDBI industry benchmarks cannot be made because the provided findings contain no specific delinquency data or statistics for SIDBI. While SIDBI's ASPIRE Fund is mentioned in the context of supporting agro-based start-ups, no comparative benchmark figures are available to evaluate our portfolio performance against industry standards.

CHART SPEC: Type=grouped_bar, Title=PAR 30 and PAR 60 and PAR 90 and NPA ratio by scheme
COLUMNS: Scheme, PAR 30, PAR 60, PAR 90, NPA ratio
SAMPLE ROWS (8 total): [{"scheme": "Dairy Loan", "par_30": 1.241914877328521, "par_60": 0.0, "par_90": 0.0, "npa_ratio": 0.0, "scheme__raw": "1622"}, {"scheme": "Loan Against Property (Scheme #1619)", "par_30": 0.9401292302328449, "par_60": 0.0, "par_90": 0.0, "npa_ratio": 0.0, "scheme__raw": "1619"}, {"scheme": "Farming Loan", "par_30": 0.2811763047327321, "par_60": 0.0498861865220783, "par_90": 0.0, "npa_ratio": 0.0, "scheme__raw": "1621"}]
```

---

### Q075: Assessing our liquidity and repayment vintage trends against macro credit conditions.

- **Category:** `Hybrid`
- **Status:** 🟢 **Answered**
- **Latency:** `38.15s`
- **Dispatched Sources:** `db, macro`
- **Rendered Cards:** `analysis, brief`
- **Evaluation Intent:** *Cohort vintage efficiency vs credit cycle tightening*
- **Grounded Citations:** *economic_survey, rbi*

#### Application Response Output:
```text
HEADLINE: Portfolio health
SUMMARY / ANSWER:
Our internal liquidity metrics remain stable, as nothing is outside its threshold across all six indicators. However, macro credit conditions present a divergent picture where non-food bank credit surged 58.6% year-over-year by December 2025, driven largely by a 44.7% increase in commercial sector resource flow, yet this momentum reversed by March 31, 2026, with overall bank credit contracting slightly by 0.7% and non-food credit declining 0.9%. While specific sectors like computer software and shipping expanded significantly, wholesale trade shrank 5.7%, contrasting with robust growth in priority sector lending to agriculture and micro-enterprises at 17.3% and 28.5% respectively. The findings do not explicitly link these specific sectoral shifts to our bank's individual repayment vintage trends.
```

---

### Q076: How does our scheme-wise concentration align with priority sector lending (PSL) guidelines?

- **Category:** `Hybrid`
- **Status:** 🟢 **Answered**
- **Latency:** `49.31s`
- **Dispatched Sources:** `db, regulatory`
- **Rendered Cards:** `chart, brief`
- **Evaluation Intent:** *Portfolio composition vs regulatory PSL norms*
- **Grounded Citations:** *sbr_master_direction_2023.pdf*

#### Application Response Output:
```text
HEADLINE: Principal outstanding by scheme (As at 21 Aug 2026)
SUMMARY / ANSWER:
Our MSME Loans scheme holds the highest principal outstanding at ₹59.81 Cr, representing 29% of the total across 8 schemes as of 21 Aug 2026. However, the provided regulatory text contains no explicit rules, thresholds, or specific guidelines for Priority Sector Lending (PSL) or MSME lending to determine if this concentration aligns with compliance requirements. Consequently, it is impossible to compare our current scheme-wise concentration against the mandated PSL guidelines because the specific sectoral allocation norms are absent from the supplied documents.

CHART SPEC: Type=bar, Title=Principal outstanding by scheme
COLUMNS: Scheme, Principal outstanding
SAMPLE ROWS (8 total): [{"scheme": "MSME Loans", "principal_outstanding": 598093032.27, "scheme__raw": "1616"}, {"scheme": "Site / Housing Construction / House Repair", "principal_outstanding": 417574205.4, "scheme__raw": "1618"}, {"scheme": "Personal Loan", "principal_outstanding": 406744496.01, "scheme__raw": "1617"}]
```

---

### Q077: How does our sanction-to-disbursement conversion rate reflect operational efficiency against NBFC benchmarks?

- **Category:** `Hybrid`
- **Status:** 🟢 **Answered**
- **Latency:** `22.58s`
- **Dispatched Sources:** `db, competitive`
- **Rendered Cards:** `brief, clarify`
- **Evaluation Intent:** *Conversion ratio vs market turnaround standards*
- **Grounded Citations:** *Kinara Capital*

#### Application Response Output:
```text
SUMMARY / ANSWER:
The provided indexed passages do not contain specific benchmarks for sanction-to-disbursement conversion times, nor do they list typical industry averages for this metric. While the documents mention Kinara Capital's operational roles, including a "Grievance Redressal Officer" and an escalation process where unresolved issues after one month may be referred to the NBFC Ombudsman (document, p.1), they do not specify the standard turnaround time for converting sanctioned loans into disbursed funds. Consequently, a direct comparison with other institutions regarding this specific benchmark cannot be made based on the available text.
```

---

### Q078: What is the impact of macro inflation and interest rate cycles on our floating-rate loan portfolio?

- **Category:** `Hybrid`
- **Status:** 🟢 **Answered**
- **Latency:** `78.48s`
- **Dispatched Sources:** `db, macro`
- **Rendered Cards:** `brief, refusal`
- **Evaluation Intent:** *Inflation impact on borrower repayment capacity*
- **Grounded Citations:** *economic_survey*

#### Application Response Output:
```text
SUMMARY / ANSWER:
The provided context does not contain information regarding the impact of inflation and interest rate cycles on floating-rate loans. While the text mentions that core inflation has been influenced by higher prices of precious metals like gold and silver (economic_survey, p.18), it does not discuss floating-rate loans, interest rate cycles, or the specific mechanisms by which inflation affects loan pricing. Therefore, I cannot answer the question based on the available information.
```

---

### Q079: How does our borrower gender diversity compare with microfinance industry inclusion targets?

- **Category:** `Hybrid`
- **Status:** 🟢 **Answered**
- **Latency:** `101.46s`
- **Dispatched Sources:** `db, macro, competitive`
- **Rendered Cards:** `brief, brief, error`
- **Evaluation Intent:** *Internal gender inclusion vs regional microfinance averages*
- **Grounded Citations:** *economic_survey, SIDBI*

#### Application Response Output:
```text
SUMMARY / ANSWER:
The provided findings do not contain specific inclusion targets for gender diversity within the microfinance industry, making a direct comparison with our borrower gender diversity impossible. While the sector is noted to currently serve 95 per cent women borrowers, the documents offer no future targets or specific diversity goals to benchmark against. Furthermore, the available data on the sector's total portfolio and borrower count lacks any gender breakdown, preventing an analysis of our lender's performance relative to industry metrics. Consequently, no supported comparison can be drawn from the supplied evidence.
```

---

### Q080: Compare our top 10 borrower concentration risk with prudential single-borrower regulatory exposure limits.

- **Category:** `Hybrid`
- **Status:** 🟢 **Answered**
- **Latency:** `45.91s`
- **Dispatched Sources:** `db, regulatory`
- **Rendered Cards:** `chart, brief`
- **Evaluation Intent:** *Single/group borrower concentration vs regulatory caps*
- **Grounded Citations:** *Prudential Norms.pdf*

#### Application Response Output:
```text
HEADLINE: Principal outstanding (whole book) by borrower (2026-08-21)
SUMMARY / ANSWER:
Our top borrower, MANJULA, represents 15% of the total principal outstanding across the top 10 borrowers, which is below the standard prudential regulatory limit of 20% of Tier 1 capital for a single counterparty. While MANJULA's concentration is significant, the findings do not provide the specific Tier 1 capital figure required to calculate the absolute monetary exposure limit, nor do they confirm whether the entity qualifies as an NBFC-IFC or holds infrastructure loans that would permit a higher limit of 25% or 30%. Consequently, a definitive comparison of the absolute exposure amount against the regulatory ceiling cannot be completed with the current data.

CHART SPEC: Type=bar, Title=Principal outstanding (whole book) by borrower
COLUMNS: Borrower, Principal outstanding (whole book)
SAMPLE ROWS (10 total): [{"borrower": "MANJULA", "principal_outstanding_book": 6737127.38, "borrower__raw": "MANJULA"}, {"borrower": "ASHWINI  ASHWINI", "principal_outstanding_book": 5306140.33, "borrower__raw": "ASHWINI  ASHWINI"}, {"borrower": "GEETHA", "principal_outstanding_book": 4534097.8, "borrower__raw": "GEETHA"}]
```

---

### Q081: How does our DPD bucket migration compare with macroeconomic stress indicators in Karnataka?

- **Category:** `Hybrid`
- **Status:** 🟢 **Answered**
- **Latency:** `36.25s`
- **Dispatched Sources:** `db, macro`
- **Rendered Cards:** `brief, refusal`
- **Evaluation Intent:** *Delinquency migration vs regional economic headwinds*
- **Grounded Citations:** *karnataka_des*

#### Application Response Output:
```text
SUMMARY / ANSWER:
The provided context does not contain a comprehensive set of macroeconomic stress indicators for Karnataka, such as GDP growth, fiscal deficit, or unemployment rates. It exclusively lists Consumer Price Index (CPI) numbers for industrial workers at selected centers, which serve as an inflation metric rather than a full stress indicator suite. For instance, the CPI for Bengaluru rose from 113.2 in 2020-21 to 145.5 in December 2025 (document, p.78). Consequently, based strictly on the available text, a broader assessment of macroeconomic stress cannot be formulated.
```

---

### Q082: Evaluating our business loan disbursement trajectory against state-wide industrial growth indicators.

- **Category:** `Hybrid`
- **Status:** 🟢 **Answered**
- **Latency:** `59.67s`
- **Dispatched Sources:** `db, macro`
- **Rendered Cards:** `brief, refusal`
- **Evaluation Intent:** *Business loan volume vs Karnataka manufacturing IIP*
- **Grounded Citations:** *mospi*

#### Application Response Output:
```text
SUMMARY / ANSWER:
State-wide industrial growth indicators for May 2026 show an Index of Industrial Production (IIP) growth rate of 5.1% compared to May 2025, with the overall index standing at 122.7 (mospi, p.3). Sector-wise, Manufacturing grew by 5.5%, Electricity & Gas Supply by 9.9%, and Water Supply by 5.5%, while Mining & Quarrying contracted by 1.6% (mospi, p.3). Under the Use-Based Classification, Capital Goods led growth at 12.9%, followed by Infrastructure/Construction Goods at 5.9% and Intermediate Goods at 5.8% (mospi, p.3). Within Manufacturing, key contributors included motor vehicles (14.5%), electrical equipment (20.8%), and basic metals (4.6%) (mospi, p.3).
```

---

### Q083: How do our retail loan collection ratios compare with regional urban co-operative benchmarks?

- **Category:** `Hybrid`
- **Status:** 🟢 **Answered**
- **Latency:** `71.80s`
- **Dispatched Sources:** `db, competitive`
- **Rendered Cards:** `brief, refusal`
- **Evaluation Intent:** *Retail collections vs UCB peer metrics*
- **Grounded Citations:** *Kaujalgi Urban Co-operative Bank, Karnataka State Co-operative Apex Bank*

#### Application Response Output:
```text
SUMMARY / ANSWER:
The provided indexed passages do not contain specific regional urban co-operative collection benchmarks, such as total deposit volumes, average ticket sizes, or collection growth rates for institutions like Kaujalgi, Belgaum Industrial, or Bellary Urban Co-operative Banks. While the text details product offerings (e.g., recurring deposits, term deposits) and operational scope (e.g., Belgaum Industrial serving Belagavi district; BDCC disbursing loans to farmers), it lacks the quantitative financial data required to establish collection benchmarks. Consequently, a direct comparison of collection metrics between these institutions cannot be performed based on the available evidence. (All documents, N/A)
```

---

### Q084: How does our portfolio risk profile support potential co-lending partnerships with larger NBFCs?

- **Category:** `Hybrid`
- **Status:** 🟢 **Answered**
- **Latency:** `43.62s`
- **Dispatched Sources:** `db, competitive`
- **Rendered Cards:** `chart, brief`
- **Evaluation Intent:** *Asset quality suitability for co-lending structures*
- **Grounded Citations:** *Kaujalgi Urban Co-operative Bank, Kinara Capital, Karnataka State Co-operative Apex Bank*

#### Application Response Output:
```text
HEADLINE: PAR 30 and NPA ratio and Principal outstanding by dpd bucket (As at 21 Aug 2026)
SUMMARY / ANSWER:
Our portfolio risk profile supports potential co-lending partnerships with larger NBFCs by leveraging our local branch presence for relationship-led acquisition in agriculture and MSME segments, areas where traditional lenders face credit-quality pressure. We differentiate from purely digital-first lenders through rural product signals, though we lack explicit data on specific risk metrics or portfolio composition to quantify this support directly. While NBFCs like Kinara Capital offer scalability and mission-aligned investor collaborations, they may lack deep local distribution, and SIDBI facilitates such partnerships via refinance schemes addressing security deposit requirements and concentration risks. However, the documents do not provide our specific risk ratings, NPA levels, or exact co-lending terms, creating a gap in assessing precise risk-sharing capabilities.

CHART SPEC: Type=table, Title=PAR 30 and NPA ratio and Principal outstanding by dpd bucket
COLUMNS: DPD bucket, PAR 30, NPA ratio, Principal outstanding
SAMPLE ROWS (5 total): [{"dpd_bucket": "31-60", "par_30": 100.0, "npa_ratio": 0.0, "principal_outstanding": 4895028.14, "dpd_bucket__raw": "31-60"}, {"dpd_bucket": "90+", "par_30": 100.0, "npa_ratio": 100.0, "principal_outstanding": 410814.29, "dpd_bucket__raw": "90+"}, {"dpd_bucket": "61-90", "par_30": 100.0, "npa_ratio": 0.0, "principal_outstanding": 187118.7, "dpd_bucket__raw": "61-90"}]
```

---

### Q085: Cross-analysis of our branch expansion in Aluva, Kochi, and Kottayam against local economic vitality.

- **Category:** `Hybrid`
- **Status:** 🟢 **Answered**
- **Latency:** `27.42s`
- **Dispatched Sources:** `db, macro`
- **Rendered Cards:** `brief, clarify`
- **Evaluation Intent:** *Branch distribution vs district economic vibrancy*
- **Grounded Citations:** *karnataka_des*

#### Application Response Output:
```text
SUMMARY / ANSWER:
The provided context does not contain economic vitality data for Aluva, Kochi, or Kottayam. The document exclusively covers Karnataka state and district-level data (e.g., Bangalore Urban, Dakshina Kannada), while Aluva, Kochi, and Kottayam are districts in Kerala. Consequently, no figures regarding their Gross District Domestic Product, sectoral contributions, or per capita income can be extracted from this text.
```

---

### Q086: What is the difference between sanctioned amount and disbursed amount in lending?

- **Category:** `General`
- **Status:** 🟢 **Answered**
- **Latency:** `6.53s`
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
- **Latency:** `6.19s`
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
- **Latency:** `6.77s`
- **Dispatched Sources:** `knowledge`
- **Rendered Cards:** `brief`
- **Evaluation Intent:** *NPA 90-day classification criteria*

#### Application Response Output:
```text
SUMMARY / ANSWER:
A loan asset qualifies as Non-Performing (NPA) when it is classified by the Reserve Bank of India (RBI) as failing to meet repayment obligations according to specific prudential norms. This status is determined through asset classification rules rather than simple metrics like the NPA ratio, which is merely a percentage calculated by dividing NPA principal by total classified principal. It is important to distinguish this regulatory status from the "Principal outstanding," which is a financial figure representing the cumulative disbursed amount minus repayments and does not inherently indicate loan performance.
```

---

### Q089: Explain the formula and business significance of Collection Efficiency in loan portfolio management.

- **Category:** `General`
- **Status:** 🟢 **Answered**
- **Latency:** `4.80s`
- **Dispatched Sources:** `knowledge`
- **Rendered Cards:** `brief`
- **Evaluation Intent:** *Collection efficiency formula (collected vs demand)*

#### Application Response Output:
```text
SUMMARY / ANSWER:
Collection efficiency measures how effectively a bank collects payments by dividing total principal and interest paid by the total amount due, expressed as a percentage. A higher percentage indicates better cash flow management and lower risk, as it reflects the portion of owed funds successfully recovered. This metric is distinct from principal outstanding, which tracks the remaining unpaid balance rather than the speed of collection.
```

---

### Q090: What is DPD (Days Past Due) and how are loans categorized into delinquency buckets?

- **Category:** `General`
- **Status:** 🟢 **Answered**
- **Latency:** `5.53s`
- **Dispatched Sources:** `knowledge`
- **Rendered Cards:** `brief`
- **Evaluation Intent:** *DPD bucketing methodology (0, 1-30, 31-60, 61-90, 90+)*

#### Application Response Output:
```text
SUMMARY / ANSWER:
DPD (Days Past Due) measures how many days a loan payment is overdue, serving as the primary metric for tracking delinquency. Loans are categorized into specific "DPD buckets" using standard ageing bands that group accounts based on their current overdue status. This classification differs from "Asset classification," which follows broader RBI guidelines for determining whether an asset is non-performing, while DPD focuses strictly on the timing of missed payments.
```

---

### Q091: What is the primary objective of RBI DNBS-02 regulatory reporting for NBFCs and financial entities?

- **Category:** `General`
- **Status:** 🟢 **Answered**
- **Latency:** `5.41s`
- **Dispatched Sources:** `knowledge`
- **Rendered Cards:** `brief`
- **Evaluation Intent:** *DNBS-02 return structure, capital adequacy, and liquidity monitoring*

#### Application Response Output:
```text
SUMMARY / ANSWER:
The primary objective of RBI DNBS-02 reporting is to collect standardized data on non-banking financial company (NBFC) activities for regulatory oversight and risk monitoring. While the provided catalog context details specific data fields like branch status and product codes, it does not define the overarching goal of the reporting framework itself. This regulatory requirement is distinct from internal bank lending metrics or specific financial product features.
```

---

### Q092: Explain Priority Sector Lending (PSL) categories and targets for Indian financial institutions.

- **Category:** `General`
- **Status:** 🟢 **Answered**
- **Latency:** `6.17s`
- **Dispatched Sources:** `knowledge`
- **Rendered Cards:** `brief`
- **Evaluation Intent:** *PSL mandates for agriculture, MSMEs, and weaker sections*

#### Application Response Output:
```text
SUMMARY / ANSWER:
Priority Sector Lending (PSL) is a regulatory framework in India that mandates financial institutions to allocate a specific percentage of their total adjusted net bank credit to designated sectors like agriculture, small enterprises, and marginalized groups. While the Reserve Bank of India sets the overall target at 40%, the specific sub-targets for each category are determined by the government and can vary annually. This concept is distinct from general lending, as it prioritizes social welfare goals over pure commercial profitability to ensure inclusive economic growth.
```

---

### Q093: What is the function of the Credit Guarantee Fund Trust for Micro and Small Enterprises (CGTMSE)?

- **Category:** `General`
- **Status:** 🟢 **Answered**
- **Latency:** `7.10s`
- **Dispatched Sources:** `knowledge`
- **Rendered Cards:** `brief`
- **Evaluation Intent:** *CGTMSE collateral-free guarantee mechanism*

#### Application Response Output:
```text
SUMMARY / ANSWER:
The Credit Guarantee Fund Trust for Micro and Small Enterprises (CGTMSE) functions as a government-backed mechanism that provides credit guarantees to banks and NBFCs, enabling them to lend to micro and small enterprises without requiring collateral. Its primary role is to mitigate lending risks for financial institutions, thereby expanding access to credit for small businesses that might otherwise be excluded due to a lack of assets. Unlike the "Sanctioned amount" metric, which tracks the total value of approved loans, CGTMSE specifically addresses the security gap in asset classification by covering potential defaults rather than defining the loan size itself.
```

---

### Q094: Explain the difference between principal outstanding, interest accrued, and total outstanding balance.

- **Category:** `General`
- **Status:** 🟢 **Answered**
- **Latency:** `5.39s`
- **Dispatched Sources:** `knowledge`
- **Rendered Cards:** `brief`
- **Evaluation Intent:** *Balance breakdown concepts in core banking*

#### Application Response Output:
```text
SUMMARY / ANSWER:
Principal outstanding is the remaining unpaid loan amount at a specific moment, while interest accrued represents the accumulated cost of borrowing that has not yet been paid. The total outstanding balance combines both the principal outstanding and any accrued interest (plus charges or penalties) to show the full amount currently owed. Unlike "total overdue," which only includes amounts past their due date, the total outstanding balance reflects the entire debt regardless of payment status.
```

---

### Q095: What are the key components of a loan repayment schedule and EMI amortization?

- **Category:** `General`
- **Status:** 🟢 **Answered**
- **Latency:** `5.45s`
- **Dispatched Sources:** `knowledge`
- **Rendered Cards:** `brief`
- **Evaluation Intent:** *EMI principal vs interest amortization schedule*

#### Application Response Output:
```text
SUMMARY / ANSWER:
A loan repayment schedule outlines the timeline and amounts for paying back a loan, while EMI amortization specifically tracks how each payment splits between reducing the principal balance and covering interest. The principal outstanding, a key metric in this process, represents the cumulative disbursed amount minus all principal repaid to date. These concepts differ from loan counts or average ticket sizes, which measure volume and size rather than the repayment structure itself.
```

---

### Q096: What is the Debt Service Coverage Ratio (DSCR) and why is it critical in MSME credit appraisal?

- **Category:** `General`
- **Status:** 🟢 **Answered**
- **Latency:** `6.17s`
- **Dispatched Sources:** `knowledge`
- **Rendered Cards:** `brief`
- **Evaluation Intent:** *DSCR formula and debt service capacity analysis*

#### Application Response Output:
```text
SUMMARY / ANSWER:
The Debt Service Coverage Ratio (DSCR) measures a borrower's ability to cover loan repayments by dividing net operating income by total debt service, serving as a key indicator of repayment capacity. It is critical in MSME credit appraisal because it directly assesses whether the business generates sufficient cash flow to meet its obligations without relying on external support. While distinct from the NPA ratio, which evaluates the quality of existing loans based on RBI asset classification, DSCR focuses on future repayment potential rather than past default status.
```

---

### Q097: Explain the regulatory difference between secured lending (e.g. Gold Loans) and unsecured MSME financing.

- **Category:** `General`
- **Status:** 🟢 **Answered**
- **Latency:** `5.81s`
- **Dispatched Sources:** `knowledge`
- **Rendered Cards:** `brief`
- **Evaluation Intent:** *Collateralized vs cash-flow backed loan risk profile*

#### Application Response Output:
```text
SUMMARY / ANSWER:
Secured lending requires collateral like gold to back the loan, whereas unsecured MSME financing relies solely on the borrower's creditworthiness without physical assets. While secured loans typically allow for larger average ticket sizes due to lower risk, unsecured MSME financing often involves stricter collection efficiency monitoring to ensure repayment. Both types are tracked by metrics such as the count of sanctioned loans, but they differ fundamentally in whether the loan is linked to a specific asset or agent for recovery purposes.
```

---

### Q098: What are Fair Practices Code guidelines mandated by RBI for lending operations?

- **Category:** `General`
- **Status:** 🟢 **Answered**
- **Latency:** `4.88s`
- **Dispatched Sources:** `knowledge`
- **Rendered Cards:** `brief`
- **Evaluation Intent:** *RBI Fair Practices Code on transparency and recovery*

#### Application Response Output:
```text
SUMMARY / ANSWER:
The provided catalog context does not contain the specific Fair Practices Code guidelines mandated by the RBI for lending operations. The available data only defines technical metrics like collection efficiency, product codes, and asset classification, which are used for reporting rather than outlining regulatory conduct rules. To learn about the actual Fair Practices Code requirements, you would need to consult official RBI publications or legal documents outside this context.
```

---

### Q099: Explain the relationship schema connecting loan account master, disbursement events, and repayment schedules.

- **Category:** `General`
- **Status:** 🟢 **Answered**
- **Latency:** `0.91s`
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
- **Latency:** `5.85s`
- **Dispatched Sources:** `knowledge`
- **Rendered Cards:** `brief`
- **Evaluation Intent:** *Governed catalog, QuerySpec compiler, and NLQ execution architecture*

#### Application Response Output:
```text
SUMMARY / ANSWER:
Moneypal Genesis structures query execution by organizing lending data around specific governed attributes like agents and borrowers rather than using a traditional warehouse model. It calculates risk metrics such as PAR 30, PAR 60, and PAR 90 to measure principal outstanding over specific delinquency periods relative to classified loans. This approach distinguishes itself by focusing on per-loan reporting views and agent codes, avoiding the creation of new bank figures or forecasts.
```

---

## 3. Architecture & Methodology Notes

1. **Unified Routing (`/api/workbench/ask`):** The default score measures only the same unified endpoint used by the application. Optional direct fallbacks are diagnostic and must be explicitly enabled.
2. **Governed SQL Pipeline (`db`):** Loan book queries compiled into deterministic `QuerySpec` contracts and executed against PostgreSQL gold views without SQL injection risk.
3. **Vector Semantic Retrieval (`macro` & `competitive`):** Macro and competitive intelligence leveraged Qdrant vector retrieval (`bge-m3` 1024-dim embeddings) and local synthesis.
4. **Zero Cold-Start:** Execution remained responsive throughout all 100 consecutive turns.

---
*Report generated by Moneypal Genesis Automated Benchmark Suite*