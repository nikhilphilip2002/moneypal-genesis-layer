# Moneypal Loan Book Benchmark Analysis

**Generated:** 2026-09-08 08:15:16 UTC  
**Target Application:** `http://100.70.118.31:4321`  
**Benchmark Scope:** 200 Loan Book Questions Across 18 Gold Views  
**Execution Mode:** Concurrent multi-turn chains with sequential conversational turns (Concurrency: 3 workers, Timeout: 120s)  
**Total Run Duration:** 1819.6s (30.3 min)  

---

## 1. Executive Summary

| Metric | Result | Benchmark Target | Status |
|---|---|---|---|
| **Total Evaluated Questions** | **200** | 200 / 500 | ✅ Complete |
| **Answered / Successful** | **106 (53.0%)** | ≥ 95.0% | ⚠️ OBSERVE |
| **Failed / Errors** | **94** | 0 | ⚠️ Needs Review |
| **Visual Graphs / Cards Rendered** | **106 (53.0%)** | ≥ 90.0% | ⚠️ OBSERVE |
| **Compaction Checkpoints** | **0** | > 0 in deep chains | ℹ️ Tested |
| **Latency p50 (Median)** | **27.13s** | ≤ 6.0s | ⚠️ High |
| **Latency p90** | **50.90s** | ≤ 12.0s | ⚠️ High |
| **Latency p95** | **59.40s** | ≤ 18.0s | ⚠️ High |
| **Latency Range** | **1.13s – 84.67s** (Avg: 29.77s) | - | - |

---

## 2. Graph & Visualizations Verification

Every response was inspected for returned source cards, chart configurations, and structural rendering metadata.

### Chart Type Distribution

| Chart / Card Type | Count | Share | Description |
|---|---|---|---|
| `table` | 41 | 20.5% | Governed TABLE visualization |
| `kpi` | 27 | 13.5% | Governed KPI visualization |
| `bar` | 16 | 8.0% | Governed BAR visualization |
| `area` | 12 | 6.0% | Governed AREA visualization |
| `heatmap` | 3 | 1.5% | Governed HEATMAP visualization |
| `small_multiples` | 3 | 1.5% | Governed SMALL_MULTIPLES visualization |
| `ranking` | 2 | 1.0% | Governed RANKING visualization |
| `line` | 2 | 1.0% | Governed LINE visualization |

### Status Distribution

| Status | Count | Share |
|---|---|---|
| **Answered** | 105 | 52.5% |
| **Error** | 84 | 42.0% |
| **Refused** | 8 | 4.0% |
| **Clarification** | 2 | 1.0% |
| **Partial** | 1 | 0.5% |

---

## 3. Coverage by Gold Semantic View (18 Views)

| View Identifier | Questions | Answered | Success Rate | Graphs Rendered | Avg Latency |
|---|---|---|---|---|---|
| `gold.semantic_agent` | 10 | 4 | 40.0% | 4 | 35.34s |
| `gold.semantic_application` | 10 | 6 | 60.0% | 6 | 26.23s |
| `gold.semantic_branch` | 10 | 4 | 40.0% | 4 | 33.74s |
| `gold.semantic_collection_activity` | 20 | 8 | 40.0% | 8 | 24.08s |
| `gold.semantic_customer_document` | 10 | 3 | 30.0% | 3 | 29.68s |
| `gold.semantic_customer_profile` | 10 | 4 | 40.0% | 4 | 33.28s |
| `gold.semantic_disbursement_event` | 10 | 4 | 40.0% | 4 | 22.06s |
| `gold.semantic_gl_balance` | 10 | 7 | 70.0% | 7 | 32.13s |
| `gold.semantic_loan_account` | 20 | 8 | 40.0% | 8 | 38.35s |
| `gold.semantic_loan_ledger_event` | 10 | 3 | 30.0% | 3 | 32.58s |
| `gold.semantic_msme_lead` | 10 | 4 | 40.0% | 4 | 28.55s |
| `gold.semantic_payment_receipt` | 10 | 9 | 90.0% | 9 | 26.05s |
| `gold.semantic_portfolio_snapshot` | 10 | 7 | 70.0% | 7 | 18.52s |
| `gold.semantic_product` | 10 | 7 | 70.0% | 7 | 31.18s |
| `gold.semantic_repayment_event` | 10 | 8 | 80.0% | 8 | 24.99s |
| `gold.semantic_repayment_schedule` | 10 | 9 | 90.0% | 9 | 27.17s |
| `gold.semantic_sales_hierarchy` | 10 | 5 | 50.0% | 5 | 37.94s |
| `gold.semantic_vintage_par` | 10 | 6 | 60.0% | 6 | 31.00s |

---

## 4. Multi-Turn Conversational Chains & Compaction Verification

Chains execute sequentially using the session conversation ID returned by the API. They explicitly exercise context inheritance (retaining filters such as `vanitha` across turns, adding requested fields like `tenure` and `sanction_amount`, and switching dimensions from scheme to branch).

| Chain Title | Semantic View | Turns | Success Rate | Avg Latency |
|---|---|---|---|---|
| Chain 1: Agent Vanitha Sourcing & Follow-up | `gold.semantic_loan_account` | 5 | 2/5 (40%) | 19.71s |
| Chain 2: Disbursement Trajectory & Schemewise Grouping | `gold.semantic_disbursement_event` | 5 | 2/5 (40%) | 10.88s |
| Chain 3: NPA Profile and Large Exposure Arrears | `gold.semantic_portfolio_snapshot` | 5 | 2/5 (40%) | 7.64s |
| Chain 4: Deep Recovery Investigation & Compaction | `gold.semantic_collection_activity` | 10 | 3/10 (30%) | 16.59s |
| Chain 5: Customer Demographics and KYC Verification | `gold.semantic_customer_profile` | 5 | 2/5 (40%) | 16.40s |
| Chain 6: Customer Document Expiry Funnel | `gold.semantic_customer_document` | 5 | 2/5 (40%) | 18.13s |
| Chain 7: Branch Network & Performance Hierarchy | `gold.semantic_branch` | 5 | 2/5 (40%) | 36.14s |
| Chain 8: Product Schemes, ROI & Tenor Matrix | `gold.semantic_product` | 5 | 4/5 (80%) | 36.61s |
| Chain 9: Field Agent Productivity & Portfolio | `gold.semantic_agent` | 5 | 2/5 (40%) | 31.39s |
| Chain 10: Sales Reporting Structure & Managers | `gold.semantic_sales_hierarchy` | 5 | 3/5 (60%) | 46.28s |
| Chain 11: Principal vs Interest Inflow | `gold.semantic_repayment_event` | 5 | 3/5 (60%) | 29.02s |
| Chain 12: Scheduled Cash Inflows & Future EMIs | `gold.semantic_repayment_schedule` | 5 | 5/5 (100%) | 22.58s |
| Chain 13: Origination Vintage PAR & Delinquency Timing | `gold.semantic_vintage_par` | 5 | 3/5 (60%) | 30.70s |
| Chain 14: Loan Application Inflow & Rejection Funnel | `gold.semantic_application` | 5 | 2/5 (40%) | 36.07s |
| Chain 15: Payment Receipts & Payment Modes | `gold.semantic_payment_receipt` | 5 | 4/5 (80%) | 28.39s |
| Chain 16: Loan Ledger Movements & Audit Trail | `gold.semantic_loan_ledger_event` | 5 | 1/5 (20%) | 35.07s |
| Chain 17: Collection Visits & Delinquency Follow-up | `gold.semantic_collection_activity` | 5 | 4/5 (80%) | 26.77s |
| Chain 18: GL Account Balances & Accounting Reconciliation | `gold.semantic_gl_balance` | 5 | 3/5 (60%) | 38.77s |
| Chain 19: MSME Sourcing & Lead Funnel | `gold.semantic_msme_lead` | 5 | 2/5 (40%) | 38.36s |
| Chain 20: Comprehensive Portfolio & Sourcing Audit | `gold.semantic_loan_account` | 10 | 3/10 (30%) | 46.16s |
| Chain 21: Loan Account Details & Terms Workflow 21 | `gold.semantic_loan_account` | 5 | 3/5 (60%) | 41.38s |
| Chain 22: Customer Demographics & Profiles Workflow 22 | `gold.semantic_customer_profile` | 5 | 2/5 (40%) | 50.16s |
| Chain 23: Document Tracking & Verification Workflow 23 | `gold.semantic_customer_document` | 5 | 1/5 (20%) | 41.23s |
| Chain 24: Branch Metrics & Origination Workflow 24 | `gold.semantic_branch` | 5 | 2/5 (40%) | 31.35s |
| Chain 25: Product Performance & Pricing Workflow 25 | `gold.semantic_product` | 5 | 3/5 (60%) | 25.74s |
| Chain 26: Agent Portfolios & Quality Workflow 26 | `gold.semantic_agent` | 5 | 2/5 (40%) | 39.29s |
| Chain 27: Sales Supervision & Coverage Workflow 27 | `gold.semantic_sales_hierarchy` | 5 | 2/5 (40%) | 29.60s |
| Chain 28: Disbursement Trends & Velocities Workflow 28 | `gold.semantic_disbursement_event` | 5 | 2/5 (40%) | 33.25s |
| Chain 29: Collections Inflow & Performance Workflow 29 | `gold.semantic_repayment_event` | 5 | 5/5 (100%) | 20.95s |
| Chain 30: Repayment Due Projections Workflow 30 | `gold.semantic_repayment_schedule` | 5 | 4/5 (80%) | 31.76s |
| Chain 31: Portfolio Risk & Asset Quality Workflow 31 | `gold.semantic_portfolio_snapshot` | 5 | 5/5 (100%) | 29.41s |
| Chain 32: Application Conversion Funnel Workflow 32 | `gold.semantic_application` | 5 | 4/5 (80%) | 16.39s |
| Chain 33: Receipt Reconciliation & Modes Workflow 33 | `gold.semantic_payment_receipt` | 5 | 5/5 (100%) | 23.70s |
| Chain 34: Ledger Accounting & Reconciliation Workflow 34 | `gold.semantic_loan_ledger_event` | 5 | 2/5 (40%) | 30.09s |
| Chain 35: Field Recoveries & Action Log Workflow 35 | `gold.semantic_collection_activity` | 5 | 1/5 (20%) | 36.37s |
| Chain 36: Vintage Risk & MOB Performance Workflow 36 | `gold.semantic_vintage_par` | 5 | 3/5 (60%) | 31.31s |
| Chain 37: General Ledger Accounting Workflow 37 | `gold.semantic_gl_balance` | 5 | 4/5 (80%) | 25.49s |
| Chain 38: MSME Pipeline & Partner Channels Workflow 38 | `gold.semantic_msme_lead` | 5 | 2/5 (40%) | 18.74s |

---

## 5. Per-Question Detail Table

| ID | Chain | Turn | Question | View | Status | Latency | Chart | Rows |
|---|---|---|---|---|---|---|---|---|
| 1 | 1 | 1 | customers under vanitha | `gold.semantic_loan_account` | Answered | 2.01s | `table` | 338 |
| 2 | 1 | 2 | include tenure and santioned amount with the above details | `gold.semantic_loan_account` | Error | 12.56s | `-` | - |
| 3 | 1 | 3 | filter to active loans only | `gold.semantic_loan_account` | Error | 9.49s | `-` | - |
| 4 | 1 | 4 | which branch are they from? | `gold.semantic_loan_account` | Refused | 62.13s | `-` | - |
| 5 | 1 | 5 | show the monthly trend of these sanctions | `gold.semantic_loan_account` | Answered | 12.34s | `table` | 100 |
| 6 | 2 | 1 | total disbursements this financial year | `gold.semantic_disbursement_event` | Answered | 5.56s | `area` | 2 |
| 7 | 2 | 2 | break that down schemewise | `gold.semantic_disbursement_event` | Error | 9.66s | `-` | - |
| 8 | 2 | 3 | now show it monthwise | `gold.semantic_disbursement_event` | Error | 10.89s | `-` | - |
| 9 | 2 | 4 | break it down by application branch | `gold.semantic_disbursement_event` | Answered | 9.72s | `table` | 5 |
| 10 | 2 | 5 | compare with the previous financial year | `gold.semantic_disbursement_event` | Error | 18.54s | `-` | - |
| 11 | 3 | 1 | what is our current NPA ratio? | `gold.semantic_portfolio_snapshot` | Answered | 5.89s | `bar` | 3 |
| 12 | 3 | 2 | break it down by scheme | `gold.semantic_portfolio_snapshot` | Answered | 1.16s | `table` | 0 |
| 13 | 3 | 3 | show overdue principal by branch | `gold.semantic_portfolio_snapshot` | Error | 9.96s | `-` | - |
| 14 | 3 | 4 | list top 10 overdue accounts | `gold.semantic_portfolio_snapshot` | Error | 10.21s | `-` | - |
| 15 | 3 | 5 | include borrower name and days past due with the above details | `gold.semantic_portfolio_snapshot` | Error | 10.98s | `-` | - |
| 16 | 4 | 1 | what is our collection efficiency this month? | `gold.semantic_collection_activity` | Error | 10.56s | `-` | - |
| 17 | 4 | 2 | break it down branchwise | `gold.semantic_collection_activity` | Error | 15.66s | `-` | - |
| 18 | 4 | 3 | how much was collected in Aluva? | `gold.semantic_collection_activity` | Answered | 7.31s | `kpi` | 1 |
| 19 | 4 | 4 | which agent collected the most there? | `gold.semantic_collection_activity` | Answered | 8.58s | `table` | 0 |
| 20 | 4 | 5 | list the accounts handled by that agent | `gold.semantic_collection_activity` | Error | 15.08s | `-` | - |
| 21 | 4 | 6 | include tenure and sanction amount | `gold.semantic_collection_activity` | Error | 10.61s | `-` | - |
| 22 | 4 | 7 | filter to standard accounts only | `gold.semantic_collection_activity` | Clarification | 59.36s | `-` | - |
| 23 | 4 | 8 | what is the total outstanding for these accounts? | `gold.semantic_collection_activity` | Error | 15.26s | `-` | - |
| 24 | 4 | 9 | show the scheduled repayments for next month | `gold.semantic_collection_activity` | Error | 12.44s | `-` | - |
| 25 | 4 | 10 | summarize our total exposure for this group | `gold.semantic_collection_activity` | Answered | 11.05s | `kpi` | 1 |
| 26 | 5 | 1 | how many customer profiles are in our database? | `gold.semantic_customer_profile` | Answered | 12.33s | `table` | 100 |
| 27 | 5 | 2 | break down customer count by gender | `gold.semantic_customer_profile` | Error | 14.56s | `-` | - |
| 28 | 5 | 3 | show the occupation distribution for female borrowers | `gold.semantic_customer_profile` | Error | 18.47s | `-` | - |
| 29 | 5 | 4 | which customers have missing or expired KYC documents? | `gold.semantic_customer_profile` | Answered | 15.26s | `kpi` | 1 |
| 30 | 5 | 5 | list the top 10 oldest customer relationships | `gold.semantic_customer_profile` | Error | 21.40s | `-` | - |
| 31 | 6 | 1 | list customer documents expiring in the next 90 days | `gold.semantic_customer_document` | Answered | 10.45s | `table` | 0 |
| 32 | 6 | 2 | filter to Aadhaar and PAN documents only | `gold.semantic_customer_document` | Answered | 6.43s | `table` | 0 |
| 33 | 6 | 3 | group the expiring count by document type | `gold.semantic_customer_document` | Error | 7.13s | `-` | - |
| 34 | 6 | 4 | break this down by customer branch | `gold.semantic_customer_document` | Clarification | 53.70s | `-` | - |
| 35 | 6 | 5 | show customer name and mobile number for expiring documents | `gold.semantic_customer_document` | Error | 12.94s | `-` | - |
| 36 | 7 | 1 | show all operating branches and their branch codes | `gold.semantic_branch` | Answered | 35.44s | `table` | 67 |
| 37 | 7 | 2 | which branches have the highest active loan count? | `gold.semantic_branch` | Answered | 20.95s | `heatmap` | 6 |
| 38 | 7 | 3 | what is the total sanctioned amount for Aluva branch? | `gold.semantic_branch` | Refused | 1.48s | `-` | - |
| 39 | 7 | 4 | break down Aluva loans by scheme | `gold.semantic_branch` | Error | 58.19s | `-` | - |
| 40 | 7 | 5 | show average ticket size across all branches | `gold.semantic_branch` | Error | 64.60s | `-` | - |
| 41 | 8 | 1 | list all loan product schemes with minimum and maximum interest rates | `gold.semantic_product` | Answered | 26.15s | `table` | 22 |
| 42 | 8 | 2 | which scheme offers the lowest interest rate? | `gold.semantic_product` | Answered | 25.74s | `ranking` | 17 |
| 43 | 8 | 3 | show the maximum loan tenor in months for each scheme | `gold.semantic_product` | Error | 60.07s | `-` | - |
| 44 | 8 | 4 | what is the total disbursed amount productwise? | `gold.semantic_product` | Answered | 36.31s | `bar` | 1 |
| 45 | 8 | 5 | which product scheme has the highest average ticket size? | `gold.semantic_product` | Answered | 34.78s | `ranking` | 17 |
| 46 | 9 | 1 | rank agents by total sanctioned loan volume | `gold.semantic_agent` | Answered | 11.79s | `kpi` | 1 |
| 47 | 9 | 2 | who are the top 5 agents by customer count? | `gold.semantic_agent` | Answered | 31.34s | `table` | 154 |
| 48 | 9 | 3 | show loans sourced by agent 1001 | `gold.semantic_agent` | Refused | 1.44s | `-` | - |
| 49 | 9 | 4 | break down agent 1001 volume by scheme | `gold.semantic_agent` | Error | 60.53s | `-` | - |
| 50 | 9 | 5 | what is the collection efficiency for loans sourced by agent 1001? | `gold.semantic_agent` | Error | 51.87s | `-` | - |
| 51 | 10 | 1 | show current sales reporting lines with actor user ID and manager ID | `gold.semantic_sales_hierarchy` | Answered | 45.10s | `table` | 0 |
| 52 | 10 | 2 | which managers oversee more than 10 agents? | `gold.semantic_sales_hierarchy` | Answered | 35.89s | `table` | 129 |
| 53 | 10 | 3 | list all active sales agents under regional manager R01 | `gold.semantic_sales_hierarchy` | Error | 45.94s | `-` | - |
| 54 | 10 | 4 | show the total portfolio size managed under R01 | `gold.semantic_sales_hierarchy` | Answered | 52.13s | `table` | 0 |
| 55 | 10 | 5 | break down R01 portfolio by branch | `gold.semantic_sales_hierarchy` | Error | 52.35s | `-` | - |
| 56 | 11 | 1 | show total repayments collected this financial year | `gold.semantic_repayment_event` | Answered | 16.16s | `area` | 2 |
| 57 | 11 | 2 | split repayments between principal collected and interest collected | `gold.semantic_repayment_event` | Answered | 15.79s | `table` | 1 |
| 58 | 11 | 3 | show the monthly trend of interest collected | `gold.semantic_repayment_event` | Answered | 19.03s | `area` | 9 |
| 59 | 11 | 4 | break down interest collected schemewise | `gold.semantic_repayment_event` | Error | 44.79s | `-` | - |
| 60 | 11 | 5 | which branch collected the highest interest this month? | `gold.semantic_repayment_event` | Error | 49.34s | `-` | - |
| 61 | 12 | 1 | what is the total scheduled instalment amount for next month? | `gold.semantic_repayment_schedule` | Answered | 17.46s | `area` | 1 |
| 62 | 12 | 2 | show scheduled EMI inflow monthwise for the next 6 months | `gold.semantic_repayment_schedule` | Answered | 15.88s | `area` | 1 |
| 63 | 12 | 3 | break down next month scheduled dues by scheme | `gold.semantic_repayment_schedule` | Answered | 19.95s | `small_multiples` | 13 |
| 64 | 12 | 4 | which branches have the highest scheduled dues next month? | `gold.semantic_repayment_schedule` | Answered | 34.18s | `table` | 0 |
| 65 | 12 | 5 | how many accounts are scheduled to pay an EMI next month? | `gold.semantic_repayment_schedule` | Answered | 25.41s | `area` | 1 |
| 66 | 13 | 1 | show PAR 30 by origination vintage and months on book | `gold.semantic_vintage_par` | Answered | 23.88s | `heatmap` | 45 |
| 67 | 13 | 2 | which vintage year has the highest PAR 30 at month 6? | `gold.semantic_vintage_par` | Refused | 23.70s | `-` | - |
| 68 | 13 | 3 | show the vintage delinquency trend for 2025 originations | `gold.semantic_vintage_par` | Error | 51.59s | `-` | - |
| 69 | 13 | 4 | break down 2025 vintage PAR by scheme | `gold.semantic_vintage_par` | Answered | 26.87s | `kpi` | 1 |
| 70 | 13 | 5 | compare 2024 and 2025 origination performance at month 12 | `gold.semantic_vintage_par` | Answered | 27.45s | `line` | 9 |
| 71 | 14 | 1 | how many loan applications were received this month? | `gold.semantic_application` | Answered | 21.44s | `table` | 0 |
| 72 | 14 | 2 | break down loan applications monthwise for the past 12 months | `gold.semantic_application` | Answered | 28.96s | `area` | 10 |
| 73 | 14 | 3 | show applications by application branch | `gold.semantic_application` | Error | 47.42s | `-` | - |
| 74 | 14 | 4 | what is the application rejection rate by scheme? | `gold.semantic_application` | Error | 45.92s | `-` | - |
| 75 | 14 | 5 | which branch has the highest approval rate? | `gold.semantic_application` | Error | 36.61s | `-` | - |
| 76 | 15 | 1 | show total payment receipts collected this month | `gold.semantic_payment_receipt` | Answered | 24.64s | `table` | 0 |
| 77 | 15 | 2 | break down payment receipts by payment mode | `gold.semantic_payment_receipt` | Answered | 27.23s | `table` | 0 |
| 78 | 15 | 3 | what is the cash payment percentage versus digital modes? | `gold.semantic_payment_receipt` | Answered | 33.75s | `table` | 0 |
| 79 | 15 | 4 | show the daily receipt volume for the past 30 days | `gold.semantic_payment_receipt` | Error | 37.31s | `-` | - |
| 80 | 15 | 5 | which branch processed the most cash receipts? | `gold.semantic_payment_receipt` | Answered | 19.02s | `table` | 0 |
| 81 | 16 | 1 | show the count of loan ledger transactions this month | `gold.semantic_loan_ledger_event` | Answered | 18.01s | `table` | 0 |
| 82 | 16 | 2 | show the monthly trend of loan ledger movements | `gold.semantic_loan_ledger_event` | Error | 34.18s | `-` | - |
| 83 | 16 | 3 | list debit transactions exceeding 10 lakhs in the last 30 days | `gold.semantic_loan_ledger_event` | Error | 35.90s | `-` | - |
| 84 | 16 | 4 | which accounts had the highest number of ledger movements? | `gold.semantic_loan_ledger_event` | Error | 44.84s | `-` | - |
| 85 | 16 | 5 | show ledger movements for account 10001 | `gold.semantic_loan_ledger_event` | Error | 42.42s | `-` | - |
| 86 | 17 | 1 | how many collection activities were logged this month? | `gold.semantic_collection_activity` | Answered | 19.10s | `table` | 0 |
| 87 | 17 | 2 | break down collection actions by activity type | `gold.semantic_collection_activity` | Error | 35.63s | `-` | - |
| 88 | 17 | 3 | rank collection agents by number of borrower visits | `gold.semantic_collection_activity` | Answered | 27.18s | `table` | 0 |
| 89 | 17 | 4 | which branches logged the most collection activities? | `gold.semantic_collection_activity` | Answered | 27.07s | `kpi` | 1 |
| 90 | 17 | 5 | what percentage of visited accounts made a repayment within 7 days? | `gold.semantic_collection_activity` | Answered | 24.88s | `kpi` | 1 |
| 91 | 18 | 1 | show current GL balances by ledger account | `gold.semantic_gl_balance` | Answered | 21.68s | `table` | 5000 |
| 92 | 18 | 2 | what is the total balance on loan asset accounts? | `gold.semantic_gl_balance` | Answered | 30.33s | `kpi` | 1 |
| 93 | 18 | 3 | break down GL balances by branch | `gold.semantic_gl_balance` | Answered | 36.42s | `table` | 100 |
| 94 | 18 | 4 | compare current GL loan assets with the previous quarter | `gold.semantic_gl_balance` | Error | 56.95s | `-` | - |
| 95 | 18 | 5 | show daily GL balance movements for the gold loan asset account | `gold.semantic_gl_balance` | Error | 48.46s | `-` | - |
| 96 | 19 | 1 | how many MSME leads are currently in the pipeline? | `gold.semantic_msme_lead` | Partial | 21.76s | `bar` | 1 |
| 97 | 19 | 2 | break down MSME leads by lead status | `gold.semantic_msme_lead` | Error | 46.33s | `-` | - |
| 98 | 19 | 3 | show MSME leads by vendor ID | `gold.semantic_msme_lead` | Error | 42.28s | `-` | - |
| 99 | 19 | 4 | which vendor has the highest lead conversion rate? | `gold.semantic_msme_lead` | Refused | 60.52s | `-` | - |
| 100 | 19 | 5 | what is the average ticket size of converted MSME loans? | `gold.semantic_msme_lead` | Answered | 20.90s | `kpi` | 1 |
| 101 | 20 | 1 | what is the total principal outstanding across the loan book? | `gold.semantic_loan_account` | Answered | 30.92s | `kpi` | 1 |
| 102 | 20 | 2 | break it down schemewise | `gold.semantic_loan_account` | Error | 43.50s | `-` | - |
| 103 | 20 | 3 | now show it by application branch | `gold.semantic_loan_account` | Answered | 28.07s | `table` | 29 |
| 104 | 20 | 4 | which branch has the largest exposure? | `gold.semantic_loan_account` | Answered | 60.71s | `bar` | 1 |
| 105 | 20 | 5 | list the top 10 largest accounts in that branch | `gold.semantic_loan_account` | Refused | 19.56s | `-` | - |
| 106 | 20 | 6 | include borrower name and interest rate | `gold.semantic_loan_account` | Error | 84.67s | `-` | - |
| 107 | 20 | 7 | also add tenure and sanction amount | `gold.semantic_loan_account` | Error | 44.66s | `-` | - |
| 108 | 20 | 8 | filter to loans sanctioned in the last 12 months | `gold.semantic_loan_account` | Error | 58.36s | `-` | - |
| 109 | 20 | 9 | who are the sourcing agents for these accounts? | `gold.semantic_loan_account` | Error | 50.82s | `-` | - |
| 110 | 20 | 10 | what is the overdue status on these loans? | `gold.semantic_loan_account` | Error | 40.34s | `-` | - |
| 111 | 21 | 1 | show active loan accounts with interest rate above 15% | `gold.semantic_loan_account` | Error | 49.68s | `-` | - |
| 112 | 21 | 2 | include sanction amount and tenure | `gold.semantic_loan_account` | Error | 33.78s | `-` | - |
| 113 | 21 | 3 | filter by gold loan scheme | `gold.semantic_loan_account` | Answered | 77.04s | `bar` | 2 |
| 114 | 21 | 4 | which branch has the most such accounts? | `gold.semantic_loan_account` | Answered | 21.05s | `bar` | 2 |
| 115 | 21 | 5 | what is the total outstanding for these accounts? | `gold.semantic_loan_account` | Answered | 25.37s | `kpi` | 1 |
| 116 | 22 | 1 | how many borrowers are located in district 3? | `gold.semantic_customer_profile` | Answered | 61.23s | `kpi` | 1 |
| 117 | 22 | 2 | break down by occupation | `gold.semantic_customer_profile` | Error | 47.05s | `-` | - |
| 118 | 22 | 3 | show customer count by gender | `gold.semantic_customer_profile` | Error | 46.69s | `-` | - |
| 119 | 22 | 4 | which customers have more than 2 active loans? | `gold.semantic_customer_profile` | Answered | 61.23s | `bar` | 4 |
| 120 | 22 | 5 | include customer name and total sanctioned amount | `gold.semantic_customer_profile` | Error | 34.59s | `-` | - |
| 121 | 23 | 1 | how many customer documents were uploaded in month 12? | `gold.semantic_customer_document` | Error | 43.38s | `-` | - |
| 122 | 23 | 2 | break down by document type | `gold.semantic_customer_document` | Answered | 53.40s | `kpi` | 1 |
| 123 | 23 | 3 | show documents pending verification | `gold.semantic_customer_document` | Error | 36.66s | `-` | - |
| 124 | 23 | 4 | which branch has the highest pending document count? | `gold.semantic_customer_document` | Error | 40.45s | `-` | - |
| 125 | 23 | 5 | list the oldest 5 pending verification documents | `gold.semantic_customer_document` | Error | 32.28s | `-` | - |
| 126 | 24 | 1 | compare loan sanction volume between branch 1001 and branch 1002 | `gold.semantic_branch` | Answered | 30.44s | `kpi` | 1 |
| 127 | 24 | 2 | break down sanctions by scheme for branch 1001 | `gold.semantic_branch` | Error | 31.37s | `-` | - |
| 128 | 24 | 3 | show total disbursed amount for branch 1002 | `gold.semantic_branch` | Error | 32.73s | `-` | - |
| 129 | 24 | 4 | what is the PAR 30 ratio for branch 1001? | `gold.semantic_branch` | Answered | 21.90s | `bar` | 1 |
| 130 | 24 | 5 | rank all branches by collection efficiency | `gold.semantic_branch` | Error | 40.29s | `-` | - |
| 131 | 25 | 1 | show total outstanding productwise | `gold.semantic_product` | Answered | 15.52s | `bar` | 1 |
| 132 | 25 | 2 | break down by scheme | `gold.semantic_product` | Error | 30.23s | `-` | - |
| 133 | 25 | 3 | which scheme has the highest number of active loans? | `gold.semantic_product` | Error | 36.44s | `-` | - |
| 134 | 25 | 4 | what is the average loan size for that scheme? | `gold.semantic_product` | Answered | 24.44s | `table` | 0 |
| 135 | 25 | 5 | show the monthly disbursement trend for that scheme | `gold.semantic_product` | Answered | 22.09s | `small_multiples` | 102 |
| 136 | 26 | 1 | show total loans sourced by agent A07 | `gold.semantic_agent` | Answered | 31.34s | `table` | 155 |
| 137 | 26 | 2 | include customer names and sanction amount | `gold.semantic_agent` | Error | 42.11s | `-` | - |
| 138 | 26 | 3 | also add loan tenure and interest rate | `gold.semantic_agent` | Error | 41.38s | `-` | - |
| 139 | 26 | 4 | what is the total overdue on these loans? | `gold.semantic_agent` | Error | 36.92s | `-` | - |
| 140 | 26 | 5 | show repayment status for these accounts | `gold.semantic_agent` | Answered | 44.68s | `table` | 0 |
| 141 | 27 | 1 | show all reporting lines for sales manager M08 | `gold.semantic_sales_hierarchy` | Error | 30.60s | `-` | - |
| 142 | 27 | 2 | how many field agents report to this manager? | `gold.semantic_sales_hierarchy` | Error | 36.58s | `-` | - |
| 143 | 27 | 3 | what is the total disbursement under this hierarchy this month? | `gold.semantic_sales_hierarchy` | Answered | 25.70s | `table` | 0 |
| 144 | 27 | 4 | break it down schemewise | `gold.semantic_sales_hierarchy` | Error | 34.33s | `-` | - |
| 145 | 27 | 5 | which agent under this manager disbursed the most? | `gold.semantic_sales_hierarchy` | Answered | 20.78s | `table` | 0 |
| 146 | 28 | 1 | what was the disbursement amount in quarter 1? | `gold.semantic_disbursement_event` | Answered | 19.57s | `area` | 2 |
| 147 | 28 | 2 | break that down productwise | `gold.semantic_disbursement_event` | Error | 34.94s | `-` | - |
| 148 | 28 | 3 | now show it schemewise | `gold.semantic_disbursement_event` | Error | 43.78s | `-` | - |
| 149 | 28 | 4 | show monthly trend for that quarter | `gold.semantic_disbursement_event` | Error | 32.94s | `-` | - |
| 150 | 28 | 5 | which branch contributed the highest disbursement? | `gold.semantic_disbursement_event` | Answered | 35.01s | `table` | 0 |
| 151 | 29 | 1 | how much principal was repaid in month 6? | `gold.semantic_repayment_event` | Answered | 15.79s | `area` | 9 |
| 152 | 29 | 2 | how much interest was collected in the same month? | `gold.semantic_repayment_event` | Answered | 18.45s | `area` | 9 |
| 153 | 29 | 3 | break down the interest collected schemewise | `gold.semantic_repayment_event` | Answered | 21.98s | `bar` | 8 |
| 154 | 29 | 4 | show collections by application branch | `gold.semantic_repayment_event` | Answered | 22.16s | `bar` | 8 |
| 155 | 29 | 5 | compare total collections with the prior month | `gold.semantic_repayment_event` | Answered | 26.37s | `area` | 9 |
| 156 | 30 | 1 | show scheduled instalments due in Q3 | `gold.semantic_repayment_schedule` | Answered | 22.21s | `kpi` | 1 |
| 157 | 30 | 2 | break down scheduled amount by branch | `gold.semantic_repayment_schedule` | Error | 45.65s | `-` | - |
| 158 | 30 | 3 | how many accounts have scheduled payments in this period? | `gold.semantic_repayment_schedule` | Answered | 20.25s | `kpi` | 1 |
| 159 | 30 | 4 | what is the total principal scheduled versus interest scheduled? | `gold.semantic_repayment_schedule` | Answered | 25.33s | `table` | 1 |
| 160 | 30 | 5 | which scheme has the largest scheduled dues? | `gold.semantic_repayment_schedule` | Answered | 45.34s | `bar` | 1 |
| 161 | 31 | 1 | show total overdue principal across the loan book | `gold.semantic_portfolio_snapshot` | Answered | 22.69s | `kpi` | 1 |
| 162 | 31 | 2 | break down overdue principal by dpd bucket | `gold.semantic_portfolio_snapshot` | Answered | 26.78s | `bar` | 5 |
| 163 | 31 | 3 | show accounts in SMA1 and SMA2 | `gold.semantic_portfolio_snapshot` | Answered | 37.64s | `table` | 100 |
| 164 | 31 | 4 | which branch has the highest overdue amount? | `gold.semantic_portfolio_snapshot` | Answered | 29.30s | `bar` | 1 |
| 165 | 31 | 5 | list top 10 borrowers in arrears | `gold.semantic_portfolio_snapshot` | Answered | 30.62s | `heatmap` | 4727 |
| 166 | 32 | 1 | how many loan applications were approved in month 9? | `gold.semantic_application` | Answered | 14.41s | `table` | 0 |
| 167 | 32 | 2 | what was the total approved sanction value? | `gold.semantic_application` | Answered | 19.74s | `kpi` | 1 |
| 168 | 32 | 3 | break down approved applications by scheme | `gold.semantic_application` | Answered | 18.34s | `table` | 0 |
| 169 | 32 | 4 | show the average processing turnaround time by branch | `gold.semantic_application` | Refused | 1.13s | `-` | - |
| 170 | 32 | 5 | how many applications were rejected in that month? | `gold.semantic_application` | Answered | 28.33s | `table` | 0 |
| 171 | 33 | 1 | show payment receipts collected on weekend dates | `gold.semantic_payment_receipt` | Answered | 25.59s | `kpi` | 1 |
| 172 | 33 | 2 | break down receipts by payment channel | `gold.semantic_payment_receipt` | Answered | 23.24s | `kpi` | 1 |
| 173 | 33 | 3 | what is the average receipt ticket size? | `gold.semantic_payment_receipt` | Answered | 22.58s | `kpi` | 1 |
| 174 | 33 | 4 | show receipt amount by branch | `gold.semantic_payment_receipt` | Answered | 24.48s | `bar` | 2 |
| 175 | 33 | 5 | list receipts exceeding 5 lakhs | `gold.semantic_payment_receipt` | Answered | 22.61s | `kpi` | 1 |
| 176 | 34 | 1 | show total debit ledger entries in month 11 | `gold.semantic_loan_ledger_event` | Error | 20.71s | `-` | - |
| 177 | 34 | 2 | show total credit ledger entries in the same month | `gold.semantic_loan_ledger_event` | Answered | 22.09s | `area` | 7 |
| 178 | 34 | 3 | what is the net ledger balance change? | `gold.semantic_loan_ledger_event` | Answered | 25.09s | `kpi` | 1 |
| 179 | 34 | 4 | break down ledger volume by branch | `gold.semantic_loan_ledger_event` | Error | 42.04s | `-` | - |
| 180 | 34 | 5 | list high value credit transactions above 10 lakhs | `gold.semantic_loan_ledger_event` | Error | 40.52s | `-` | - |
| 181 | 35 | 1 | how many customer contact attempts were recorded this week? | `gold.semantic_collection_activity` | Answered | 11.91s | `small_multiples` | 177 |
| 182 | 35 | 2 | break down by outcome code | `gold.semantic_collection_activity` | Error | 43.26s | `-` | - |
| 183 | 35 | 3 | which agents conducted more than 50 visits? | `gold.semantic_collection_activity` | Error | 44.41s | `-` | - |
| 184 | 35 | 4 | show promised-to-pay conversion rate | `gold.semantic_collection_activity` | Error | 41.51s | `-` | - |
| 185 | 35 | 5 | break down collection visits by branch | `gold.semantic_collection_activity` | Error | 40.74s | `-` | - |
| 186 | 36 | 1 | show 30+ DPD vintage curve for Q1 disbursements | `gold.semantic_vintage_par` | Answered | 20.03s | `kpi` | 1 |
| 187 | 36 | 2 | compare vintage performance across schemes | `gold.semantic_vintage_par` | Error | 31.43s | `-` | - |
| 188 | 36 | 3 | which vintage cohort shows the steepest delinquency increase? | `gold.semantic_vintage_par` | Error | 41.07s | `-` | - |
| 189 | 36 | 4 | show MOB 12 PAR 90 by branch | `gold.semantic_vintage_par` | Answered | 21.62s | `table` | 0 |
| 190 | 36 | 5 | compare vintage performance against portfolio average | `gold.semantic_vintage_par` | Answered | 42.39s | `table` | 0 |
| 191 | 37 | 1 | show general ledger balances for interest income accounts | `gold.semantic_gl_balance` | Answered | 22.17s | `kpi` | 1 |
| 192 | 37 | 2 | break down interest income by branch | `gold.semantic_gl_balance` | Error | 34.77s | `-` | - |
| 193 | 37 | 3 | compare this financial year interest income with last FY | `gold.semantic_gl_balance` | Answered | 19.29s | `line` | 2 |
| 194 | 37 | 4 | show GL balance for cash in transit accounts | `gold.semantic_gl_balance` | Answered | 20.19s | `kpi` | 1 |
| 195 | 37 | 5 | show daily ledger balance movements for the head office branch | `gold.semantic_gl_balance` | Answered | 31.03s | `table` | 100 |
| 196 | 38 | 1 | how many MSME leads were sourced from digital channels? | `gold.semantic_msme_lead` | Error | 33.97s | `-` | - |
| 197 | 38 | 2 | break down digital leads by status | `gold.semantic_msme_lead` | Answered | 21.69s | `bar` | 5 |
| 198 | 38 | 3 | what is the conversion rate of digital leads? | `gold.semantic_msme_lead` | Answered | 22.97s | `kpi` | 1 |
| 199 | 38 | 4 | show average sanctioned amount for converted digital leads | `gold.semantic_msme_lead` | Refused | 1.65s | `-` | - |
| 200 | 38 | 5 | which branches processed the most digital MSME leads? | `gold.semantic_msme_lead` | Error | 13.42s | `-` | - |