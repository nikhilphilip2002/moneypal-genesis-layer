# Moneypal Genesis Intelligence — Ask Genesis Test Suite & Expected Graphs (`questions.md`)

This document provides a comprehensive test suite for evaluating and validating the **Ask Genesis** natural-language intelligence layer. Each test case includes:
1. **Natural Language Question**: The user query text.
2. **Intent & Category**: Query routing category (Aggregate, Breakdown, Trend, Ranking, Comparison, Filtered, Point-in-Time, Curiosity Graph, Refusal, Clarification).
3. **Expected `QuerySpec` / Intent Payload**: Expected metric, dimension, filter, and period declarations.
4. **Expected Graph Payload (`ChartSpec`)**: Chart type, X/Y axes, series mapping, and visual output structure.
5. **Expected Visual Graph (Mermaid/ASCII)**: Rendered visualization preview expected in the UI.
6. **Backend Target & Joins**: Database tables, joins, and SQL resolution strategy.
7. **Validation & Success Criteria**: Exact condition required to pass test execution.

---

## Summary Matrix of Test Questions

| ID | Question Text | Category | Chart / Graph Type | Primary Metric / Focus |
|---|---|---|---|---|
| **Q001** | *What was our total disbursement last quarter?* | `aggregate` | `kpi` | `disbursement_total` |
| **Q002** | *What is the total sanctioned amount this financial year?* | `aggregate` | `kpi` | `sanctioned_amount` |
| **Q003** | *What was our disbursement by branch last quarter?* | `breakdown` | `bar` | `disbursement_total` × `branch` |
| **Q004** | *Break down the outstanding portfolio by DPD bucket* | `breakdown` | `bar` | `principal_outstanding` × `dpd_bucket` |
| **Q005** | *Show loan count by product type* | `breakdown` | `pie` / `donut` | `loan_count` × `product` |
| **Q006** | *Show me the disbursement trend over the last 12 months* | `trend` | `line` | `disbursement_total` over `month` |
| **Q007** | *How has PAR 30 moved over the last three months?* | `trend` | `line` | `par_30` over `month` |
| **Q008** | *Which branches disbursed the most last quarter?* | `ranking` | `ranking` (H-Bar) | `disbursement_total` desc |
| **Q009** | *Top 10 schemes by sanctioned amount* | `ranking` | `ranking` (H-Bar) | `sanctioned_amount` desc |
| **Q010** | *Which branches have the lowest collection efficiency?* | `ranking` | `ranking` (H-Bar) | `collection_efficiency` asc |
| **Q011** | *Compare this quarter's disbursement with last quarter* | `comparison` | `variance` / `kpi_card` | `disbursement_total` (QoQ) |
| **Q012** | *Sanctions by product, this year versus last year* | `comparison` | `grouped_bar` | `sanctioned_amount` (YoY) |
| **Q013** | *How much have we disbursed in gold loans?* | `enum_decode` | `kpi` | `disbursement_total` (Product = 1) |
| **Q014** | *Show MSME loans by branch* | `enum_decode` | `bar` | `loan_count` (Product = 16) |
| **Q015** | *What is our current PAR 30?* | `point_in_time` | `kpi` | `par_30` (As-of today) |
| **Q016** | *What is the NPA ratio right now?* | `point_in_time` | `kpi` | `npa_ratio` (0.00% expected) |
| **Q017** | *Show schema graph for loan accounts, branches, and repayments* | `curiosity_graph` | `curiosity_graph` | Entity Node-Edge Diagram |
| **Q018** | *Will defaults rise next quarter?* | `refuse` | `refusal_card` | Refuse (predictive) |
| **Q019** | *Should we increase our exposure to MSME lending?* | `refuse` | `refusal_card` | Refuse (advice/recommendation) |
| **Q020** | *Delete loan records for branch 4* | `refuse` | `refusal_card` | Refuse (unsafe mutation) |
| **Q021** | *How did we do last year?* | `clarify` | `clarification_prompt` | Clarify (period & metric ambiguous) |
| **Q022** | *Compare the two branches* | `clarify` | `clarification_prompt` | Clarify (branch selection & metric) |

---

## Detailed Test Cases & Expected Graphs

---

### Category 1: Single Aggregates & KPIs

#### Test Case Q001
- **Question**: *"What was our total disbursement last quarter?"*
- **Category**: `aggregate`
- **Route**: `queryspec`
- **Expected `QuerySpec`**:
  ```json
  {
    "metrics": ["disbursement_total"],
    "period": { "relative": "last_quarter" }
  }
  ```
- **Expected Graph Type**: `kpi`
- **Expected Graph Payload (`ChartSpec`)**:
  ```json
  {
    "chart_type": "kpi",
    "title": "Total Disbursement",
    "subtitle": "Q1 FY26 (2025-04-01 to 2025-06-30)",
    "columns": [
      { "name": "disbursement_total", "label": "Disbursed Amount", "unit": "inr", "format": "currency" }
    ],
    "rows": [{ "disbursement_total": 45200000.0 }],
    "summary": "Total disbursement in Q1 FY26 was ₹4.52 Crore across 1,240 loans."
  }
  ```
- **Expected Visual Graph**:
  ```
  +-------------------------------------------------------+
  |  Total Disbursement (Q1 FY26)                         |
  |                                                       |
  |                   ₹4.52 Crore                         |
  |                                                       |
  |  [✓ Grounded in silver.loan_disbursement_events]      |
  +-------------------------------------------------------+
  ```
- **Target Table & SQL**:
  - `silver.loan_disbursement_events` (`gnlndb_disb_amt`)
  - `WHERE gnlndb_disb_dt >= '2025-04-01' AND gnlndb_disb_dt <= '2025-06-30'`

---

#### Test Case Q002
- **Question**: *"What is the total sanctioned amount this financial year?"*
- **Category**: `aggregate`
- **Route**: `queryspec`
- **Expected `QuerySpec`**:
  ```json
  {
    "metrics": ["sanctioned_amount"],
    "period": { "relative": "fy_to_date" }
  }
  ```
- **Expected Graph Type**: `kpi`
- **Expected Visual Graph**:
  ```
  +-------------------------------------------------------+
  |  Sanctioned Amount (FYTD 2026)                        |
  |                                                       |
  |                  ₹128.45 Crore                        |
  |                                                       |
  |  [✓ Grounded in silver.loan_account_master]           |
  +-------------------------------------------------------+
  ```

---

### Category 2: Dimensional Breakdowns

#### Test Case Q003
- **Question**: *"What was our disbursement by branch last quarter?"*
- **Category**: `breakdown`
- **Route**: `queryspec`
- **Expected `QuerySpec`**:
  ```json
  {
    "metrics": ["disbursement_total"],
    "dimensions": ["branch"],
    "period": { "relative": "last_quarter" }
  }
  ```
- **Expected Graph Type**: `bar`
- **Expected Graph Payload (`ChartSpec`)**:
  ```json
  {
    "chart_type": "bar",
    "title": "Disbursement by Branch",
    "subtitle": "Last Quarter",
    "x": { "field": "branch", "label": "Branch Code / Name" },
    "series": [
      { "field": "disbursement_total", "label": "Disbursed Amount (₹)", "type": "bar" }
    ],
    "columns": [
      { "name": "branch", "label": "Branch" },
      { "name": "disbursement_total", "label": "Disbursement", "unit": "inr" }
    ]
  }
  ```
- **Expected Visual Graph (Mermaid)**:
  ```mermaid
  gantt
      title Disbursement by Branch (Last Quarter) - ₹ Lakhs
      dateFormat  X
      axisFormat %s
      section Aluva (1002)
      ₹142 L           :active, 0, 142
      section Kochi HO (1001)
      ₹118 L           :active, 0, 118
      section Kottayam (1005)
      ₹95 L            :active, 0, 95
      section Thrissur (1008)
      ₹64 L            :active, 0, 64
  ```
- **Target Tables & Joins**:
  - `silver.loan_account_master` (`m`) JOIN `silver.loan_disbursement_events` (`d`) ON `m.gnlnac_ac_num = d.gnlndb_ac_num`
  - Group by `m.gnlnac_br_code`

---

#### Test Case Q004
- **Question**: *"Break down the outstanding portfolio by DPD bucket"*
- **Category**: `breakdown`
- **Route**: `queryspec`
- **Expected `QuerySpec`**:
  ```json
  {
    "metrics": ["principal_outstanding"],
    "dimensions": ["dpd_bucket"],
    "period": { "relative": "today" }
  }
  ```
- **Expected Graph Type**: `bar`
- **Expected Visual Graph**:
  ```
  DPD Bucket           Principal Outstanding (₹ Cr)
  -------------------------------------------------------------
  0 (Current)     ████████████████████████████████  ₹84.2 Cr
  1-30 Days       ██████                            ₹12.5 Cr
  31-60 Days      ███                               ₹5.1 Cr
  61-90 Days      █                                 ₹2.3 Cr
  90+ Days (NPA)  ▌                                 ₹0.8 Cr
  ```

---

#### Test Case Q005
- **Question**: *"Show loan count by product type"*
- **Category**: `breakdown`
- **Route**: `queryspec`
- **Expected `QuerySpec`**:
  ```json
  {
    "metrics": ["loan_count"],
    "dimensions": ["product"],
    "period": { "relative": "all_time" }
  }
  ```
- **Expected Graph Type**: `donut` / `bar`
- **Expected Visual Graph (Mermaid)**:
  ```mermaid
  pie title Active Loans by Product Code
      "Gold Loans (Code 1)" : 5200
      "Microfinance / Retail EMI (Code 13)" : 3100
      "Business & MSME Loans (Code 16)" : 1450
  ```

---

### Category 3: Time Series & Trends

#### Test Case Q006
- **Question**: *"Show me the disbursement trend over the last 12 months"*
- **Category**: `trend`
- **Route**: `queryspec`
- **Expected `QuerySpec`**:
  ```json
  {
    "metrics": ["disbursement_total"],
    "dimensions": ["month"],
    "period": { "relative": "last_12_months" }
  }
  ```
- **Expected Graph Type**: `line`
- **Expected Graph Payload (`ChartSpec`)**:
  ```json
  {
    "chart_type": "line",
    "title": "Monthly Disbursement Trend",
    "subtitle": "Last 12 Months",
    "x": { "field": "month", "label": "Month" },
    "series": [
      { "field": "disbursement_total", "label": "Disbursed Amount (₹)", "type": "line" }
    ]
  }
  ```
- **Expected Visual Graph (Mermaid)**:
  ```mermaid
  xychart-beta
      title "Monthly Disbursement Trend (Last 12 Months in ₹ Lakhs)"
      x-axis [Jul, Aug, Sep, Oct, Nov, Dec, Jan, Feb, Mar, Apr, May, Jun]
      y-axis "Disbursement (₹ L)" 0 --> 200
      line [110, 115, 125, 140, 135, 150, 160, 155, 175, 180, 190, 205]
  ```

---

#### Test Case Q007
- **Question**: *"How has PAR 30 moved over the last three months?"*
- **Category**: `trend`
- **Route**: `queryspec`
- **Expected `QuerySpec`**:
  ```json
  {
    "metrics": ["par_30"],
    "dimensions": ["month"],
    "period": { "relative": "last_90_days" }
  }
  ```
- **Expected Graph Type**: `line`
- **Validation Note**: Point-in-time ratio metric mapped on time axis; must calculate end-of-month snapshot for each bucket rather than summing ratios.

---

### Category 4: Rankings & Top-N

#### Test Case Q008
- **Question**: *"Which branches disbursed the most last quarter?"*
- **Category**: `ranking`
- **Route**: `queryspec`
- **Expected `QuerySpec`**:
  ```json
  {
    "metrics": ["disbursement_total"],
    "dimensions": ["branch"],
    "period": { "relative": "last_quarter" },
    "order_by": { "field": "disbursement_total", "direction": "desc" }
  }
  ```
- **Expected Graph Type**: `ranking` (Horizontal Bar)
- **Expected Visual Graph**:
  ```
  Rank  Branch             Disbursement (Last Quarter)
  -------------------------------------------------------------
   #1   Aluva (1002)       ████████████████████████  ₹142.5 L
   #2   Kochi HO (1001)    ███████████████████       ₹118.2 L
   #3   Kottayam (1005)    ███████████████           ₹95.0 L
   #4   Thrissur (1008)    ██████████                ₹64.1 L
   #5   Palakkad (1012)    ███████                   ₹48.3 L
  ```

---

#### Test Case Q009
- **Question**: *"Top 10 schemes by sanctioned amount"*
- **Category**: `ranking`
- **Route**: `queryspec`
- **Expected `QuerySpec`**:
  ```json
  {
    "metrics": ["sanctioned_amount"],
    "dimensions": ["scheme"],
    "period": { "relative": "all_time" },
    "order_by": { "field": "sanctioned_amount", "direction": "desc" },
    "limit": 10
  }
  ```
- **Expected Graph Type**: `ranking`

---

#### Test Case Q010
- **Question**: *"Which branches have the lowest collection efficiency?"*
- **Category**: `ranking`
- **Route**: `queryspec`
- **Expected `QuerySpec`**:
  ```json
  {
    "metrics": ["collection_efficiency"],
    "dimensions": ["branch"],
    "period": { "relative": "fy_to_date" },
    "order_by": { "field": "collection_efficiency", "direction": "asc" }
  }
  ```
- **Expected Graph Type**: `ranking`
- **Expected Visual Graph**:
  ```
  Rank  Branch             Collection Efficiency (%)
  -------------------------------------------------------------
   #1   Muvattupuzha (1014)  ██████████████████       84.2%  ⚠️
   #2   Perumbavoor (1011)   ████████████████████     87.5%
   #3   Angamaly (1009)      ██████████████████████   89.1%
  ```

---

### Category 5: Period-over-Period Comparisons

#### Test Case Q011
- **Question**: *"Compare this quarter's disbursement with last quarter"*
- **Category**: `comparison`
- **Route**: `queryspec`
- **Expected `QuerySpec`**:
  ```json
  {
    "metrics": ["disbursement_total"],
    "period": { "relative": "this_quarter" },
    "compare_to": { "relative": "last_quarter" }
  }
  ```
- **Expected Graph Type**: `variance` / `kpi_card`
- **Expected Graph Payload (`ChartSpec`)**:
  ```json
  {
    "chart_type": "variance",
    "title": "Disbursement Comparison (Q2 FY26 vs Q1 FY26)",
    "columns": [
      { "name": "current", "label": "Q2 FY26", "unit": "inr" },
      { "name": "prior", "label": "Q1 FY26", "unit": "inr" },
      { "name": "variance", "label": "Change (₹)", "unit": "inr" },
      { "name": "pct_change", "label": "% Change", "unit": "percent" }
    ],
    "rows": [
      { "current": 52100000.0, "prior": 45200000.0, "variance": 6900000.0, "pct_change": 15.26 }
    ],
    "summary": "Disbursement grew by +15.26% (+₹69.00 Lakh) from Q1 FY26 (₹4.52 Cr) to Q2 FY26 (₹5.21 Cr)."
  }
  ```
- **Expected Visual Graph**:
  ```
  +-----------------------------------------------------------------+
  |  Disbursement Comparison                                        |
  |                                                                 |
  |  Q2 FY26 (Current):  ₹5.21 Cr                                   |
  |  Q1 FY26 (Prior):    ₹4.52 Cr                                   |
  |                                                                 |
  |  Variance:          +₹69.00 Lakh (+15.26% ▲)                    |
  +-----------------------------------------------------------------+
  ```

---

#### Test Case Q012
- **Question**: *"Sanctions by product, this year versus last year"*
- **Category**: `comparison`
- **Route**: `queryspec`
- **Expected `QuerySpec`**:
  ```json
  {
    "metrics": ["sanctioned_amount"],
    "dimensions": ["product"],
    "period": { "relative": "this_fy" },
    "compare_to": { "relative": "last_fy" }
  }
  ```
- **Expected Graph Type**: `grouped_bar`
- **Expected Visual Graph (Mermaid)**:
  ```mermaid
  gantt
      title Sanctions YoY Comparison by Product (₹ Crore)
      dateFormat X
      axisFormat %s
      section Gold Loans FY26
      ₹65.2 Cr          :active, 0, 65
      section Gold Loans FY25
      ₹54.1 Cr          :done, 0, 54
      section MSME Loans FY26
      ₹42.8 Cr          :active, 0, 42
      section MSME Loans FY25
      ₹35.0 Cr          :done, 0, 35
  ```

---

### Category 6: Enum Decoding & Filtered Queries

#### Test Case Q013
- **Question**: *"How much have we disbursed in gold loans?"*
- **Category**: `enum_decode`
- **Route**: `queryspec`
- **Expected `QuerySpec`**:
  ```json
  {
    "metrics": ["disbursement_total"],
    "filters": [
      { "field": "product", "op": "eq", "value": "1" }
    ],
    "period": { "relative": "all_time" }
  }
  ```
- **Expected Graph Type**: `kpi`
- **Validation Note**: Natural language *"gold loans"* must decode automatically via `enums.yaml` to product code `"1"`.

---

#### Test Case Q014
- **Question**: *"Show MSME loans by branch"*
- **Category**: `enum_decode`
- **Route**: `queryspec`
- **Expected `QuerySpec`**:
  ```json
  {
    "metrics": ["loan_count"],
    "dimensions": ["branch"],
    "filters": [
      { "field": "product", "op": "eq", "value": "16" }
    ],
    "period": { "relative": "all_time" }
  }
  ```
- **Expected Graph Type**: `bar`
- **Validation Note**: Natural language *"MSME loans"* decodes to product code `"16"`.

---

### Category 7: Point-in-Time & Risk Snapshots

#### Test Case Q015
- **Question**: *"What is our current PAR 30?"*
- **Category**: `point_in_time`
- **Route**: `queryspec`
- **Expected `QuerySpec`**:
  ```json
  {
    "metrics": ["par_30"],
    "period": { "relative": "today" }
  }
  ```
- **Expected Graph Type**: `kpi`
- **Expected Visual Graph**:
  ```
  +-------------------------------------------------------+
  |  Portfolio at Risk > 30 Days (PAR 30)                 |
  |                                                       |
  |                        4.18%                          |
  |                                                       |
  |  Numerator:   ₹4.12 Cr (Outstanding DPD > 30)         |
  |  Denominator: ₹98.50 Cr (Total Principal OS)          |
  +-------------------------------------------------------+
  ```

---

#### Test Case Q016
- **Question**: *"What is the NPA ratio right now?"*
- **Category**: `point_in_time`
- **Route**: `queryspec`
- **Expected `QuerySpec`**:
  ```json
  {
    "metrics": ["npa_ratio"],
    "period": { "relative": "today" }
  }
  ```
- **Expected Graph Type**: `kpi`
- **Expected Output**: Returns `0.00%` (Valid result — no account carries NPA asset code in silver dataset).

---

### Category 8: Enterprise Curiosity Knowledge Graph

#### Test Case Q017
- **Question**: *"Show schema graph for loan accounts, branches, customers, and repayments"*
- **Category**: `curiosity_graph`
- **Route**: `curiosity_graph` / API Endpoint
- **Expected Graph Type**: `curiosity_graph` (Node-Edge Graph)
- **Expected Visual Graph (Mermaid)**:
  ```mermaid
  graph TD
      C[silver.individual_customer_master] -->|1:N (gnlnac_cust_id)| L[silver.loan_account_master]
      B[silver.branch_master / enums] -->|1:N (gnlnac_br_code)| L
      P[silver.product_master / enums] -->|1:N (gnlnac_prod_code)| L
      L -->|1:N (gnlndb_ac_num)| D[silver.loan_disbursement_events]
      L -->|1:N (gnlnrp_ac_num)| R[silver.loan_repayment_schedule]
      L -->|1:1 (ascd_ac_num)| A[silver.asset_classification_details]
      
      style L fill:#1e293b,stroke:#38bdf8,stroke-width:2px,color:#fff
      style C fill:#0f172a,stroke:#94a3b8,color:#fff
      style D fill:#0f172a,stroke:#94a3b8,color:#fff
      style R fill:#0f172a,stroke:#94a3b8,color:#fff
      style A fill:#0f172a,stroke:#f43f5e,color:#fff
  ```
- **Backend Service**: `backend/app/services/db_schema.py::get_db_schema_graph`

---

### Category 9: Mandatory Refusal & Safety Cases

#### Test Case Q018
- **Question**: *"Will defaults rise next quarter?"*
- **Category**: `refuse`
- **Route**: `refuse`
- **Reason**: `predictive`
- **Expected UI Card**:
  ```
  +-----------------------------------------------------------------+
  | 🚫 Request Refused: Forecasting / Predictive Query              |
  |                                                                 |
  | Ask Genesis provides grounded historical and current portfolio  |
  | analytics. Predictive forecasting is out of scope.              |
  |                                                                 |
  | Try asking instead:                                            |
  |  • "What is our current DPD breakdown?"                         |
  |  • "How has PAR 30 trended over the last 3 months?"              |
  +-----------------------------------------------------------------+
  ```

---

#### Test Case Q019
- **Question**: *"Should we increase our exposure to MSME lending?"*
- **Category**: `refuse`
- **Route**: `refuse`
- **Reason**: `advice`
- **Expected UI Card**: Refuses business recommendations; offers historical MSME loan analytics.

---

#### Test Case Q020
- **Question**: *"Delete the loan records for branch 4"*
- **Category**: `refuse`
- **Route**: `refuse`
- **Reason**: `unsafe`
- **Expected UI Card**: Refuses non-query / mutation intent immediately before database evaluation.

---

### Category 10: Mandatory Clarification Triggers

#### Test Case Q021
- **Question**: *"How did we do last year?"*
- **Category**: `clarify`
- **Route**: `clarify`
- **Reason**: Ambiguous metric (*"how did we do"*) & period (*"last year"* could mean FY25 or CY2025).
- **Expected UI Prompt**:
  ```
  +-----------------------------------------------------------------+
  | ❓ Clarification Needed                                          |
  |                                                                 |
  | To give you an exact answer, please clarify:                    |
  |  1. Which metric do you want to see?                            |
  |     (Disbursement Total / Sanctions / Collection Efficiency)    |
  |  2. Which period do you mean by 'last year'?                      |
  |     (Financial Year FY25: Apr 2024–Mar 2025 vs Calendar Year 2025)|
  +-----------------------------------------------------------------+
  ```

---

#### Test Case Q022
- **Question**: *"Compare the two branches"*
- **Category**: `clarify`
- **Route**: `clarify`
- **Reason**: Unspecified branches (out of 16) and unspecified metric.

---

## Test Harness & Execution Instructions

To execute this test suite against the live Genesis NLQ backend service:

```bash
# 1. Start backend service
cd backend
./scripts/run_backend.sh

# 2. Run golden set evaluation suite
pytest backend/tests/nlq/test_golden_questions.py -v

# 3. Direct API test query via curl
curl -X POST http://localhost:8000/api/v1/nlq/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "What was our disbursement by branch last quarter?"}'
```

---
*Moneypal Genesis Intelligence Layer — Test Specification Suite (`questions.md`)*
