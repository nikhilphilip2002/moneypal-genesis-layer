# Moneypal Genesis — 200 Mixed Intelligence Questions Benchmark

**Generated:** 2026-08-26 09:09:47 UTC
**Endpoint:** `http://100.70.118.31:4321`
**Mode:** Execution benchmark
**Selected questions:** 200 / 200
**Completed requests:** 200
**Elapsed:** 4819.58s

## Payload isolation

Every request body contains exactly one key:

```json
{"question": "<plain user question>"}
```

No source pin, expected route, category, evaluation intent, conversation ID, history, answer hint, or expected SQL is sent by this benchmark client.

## Summary

| Metric | Value |
|---|---:|
| Answered | 158 |
| Partial | 31 |
| Clarification | 2 |
| Refused | 7 |
| Errors | 2 |
| Expected route observed | 168 / 200 |
| Average latency | 24.09s |

## Domain coverage

| Domain | Selected | Completed | Answered | Route match |
|---|---:|---:|---:|---:|
| Loan Book | 32 | 32 | 28 | 32 |
| Macro | 32 | 32 | 23 | 31 |
| Competitive | 32 | 32 | 24 | 27 |
| Regulatory | 32 | 32 | 30 | 16 |
| General Banking | 32 | 32 | 31 | 29 |
| Hybrid | 40 | 40 | 22 | 33 |

## Question results

### Q001 — What is the total principal outstanding across our loan book?

- Domain: **Loan Book / Portfolio**
- Expected source: `db`
- Status: **Answered**
- Actual sources: `db`
- Route match: **Yes**
- Latency: `29.64s`
- Cards: `chart`

#### Response

````text
Principal outstanding (whole book) was ₹214.00 Cr in 2026-08-26. This measures cumulative disbursed minus cumulative principal repaid across loan accounts.
````

#### SQL

````sql
SELECT SUM(lam.disbursed_amount - lam.principal_repaid) AS principal_outstanding_book
FROM gold.loan_account_master AS lam
LIMIT 200
````

---

### Q002 — Show our principal outstanding by product.

- Domain: **Loan Book / Portfolio**
- Expected source: `db`
- Status: **Answered**
- Actual sources: `db`
- Route match: **Yes**
- Latency: `26.25s`
- Cards: `chart`

#### Response

````text
Business & MSME Loans is the only product returned, with principal outstanding of ₹204.54 Cr as at 26 Aug 2026. This measures principal outstanding from each classified account at the requested snapshot, grouped by product.
````

#### SQL

````sql
SELECT lam."product_code" AS product,
       SUM(portfolio.principal_outstanding) AS principal_outstanding
FROM gold.portfolio_snapshot_as_of(DATE '2026-08-26') AS portfolio
     JOIN gold.loan_account_master AS lam ON portfolio."entity_num" = lam."entity_num" AND portfolio."loan_account_number" = lam."loan_account_number"
GROUP BY lam."product_code"
ORDER BY SUM(portfolio.principal_outstanding) DESC NULLS LAST
LIMIT 200
````

---

### Q003 — Which branches have the highest principal outstanding?

- Domain: **Loan Book / Portfolio**
- Expected source: `db`
- Status: **Answered**
- Actual sources: `db`
- Route match: **Yes**
- Latency: `18.75s`
- Cards: `chart`

#### Response

````text
Head Office — Credit Division is the only branch returned, with principal outstanding of ₹204.54 Cr as at 26 Aug 2026. This measures principal outstanding from each classified account at the requested snapshot, grouped by branch.
````

#### SQL

````sql
SELECT lam."branch_code" AS branch,
       SUM(portfolio.principal_outstanding) AS principal_outstanding
FROM gold.portfolio_snapshot_as_of(DATE '2026-08-26') AS portfolio
     JOIN gold.loan_account_master AS lam ON portfolio."entity_num" = lam."entity_num" AND portfolio."loan_account_number" = lam."loan_account_number"
GROUP BY lam."branch_code"
ORDER BY SUM(portfolio.principal_outstanding) DESC NULLS LAST
LIMIT 200
````

---

### Q004 — Break down our current outstanding by asset classification.

- Domain: **Loan Book / Portfolio**
- Expected source: `db`
- Status: **Answered**
- Actual sources: `db`
- Route match: **Yes**
- Latency: `40.54s`
- Cards: `chart`

#### Response

````text
Standard has the highest principal outstanding, at ₹194.43 Cr as at 26 Aug 2026, 95% of the total across 5 asset classifications. This measures principal outstanding from each classified account at the requested snapshot, grouped by asset classification.
````

#### SQL

````sql
SELECT portfolio."asset_code" AS asset_class,
       SUM(portfolio.principal_outstanding) AS principal_outstanding
FROM gold.portfolio_snapshot_as_of(DATE '2026-08-26') AS portfolio
GROUP BY portfolio."asset_code"
ORDER BY SUM(portfolio.principal_outstanding) DESC NULLS LAST
LIMIT 200
````

---

### Q005 — How many open loan accounts are in our portfolio?

- Domain: **Loan Book / Portfolio**
- Expected source: `db`
- Status: **Refused**
- Actual sources: `db`
- Route match: **Yes**
- Latency: `85.73s`
- Cards: `refusal`

#### Response

````text
I could not answer that safely from the available data.
````

---

### Q006 — What is our average principal outstanding per active account?

- Domain: **Loan Book / Portfolio**
- Expected source: `db`
- Status: **Answered**
- Actual sources: `db`
- Route match: **Yes**
- Latency: `38.84s`
- Cards: `chart`

#### Response

````text
Avg Principal Outstanding was ₹3.74 L. Average principal outstanding calculated only on active (non-delinquent) accounts with positive balances. This uses a validated read-only generated query rather than a reviewed metric; check Source details before relying on it.
````

#### SQL

````sql
SELECT
  AVG(principal_outstanding) AS avg_principal_outstanding
FROM gold.portfolio_daily_snapshot
WHERE
  is_delinquent = FALSE AND principal_outstanding > 0
LIMIT 5000
````

---

### Q007 — Show open versus closed loan accounts by product.

- Domain: **Loan Book / Portfolio**
- Expected source: `db`
- Status: **Answered**
- Actual sources: `db`
- Route match: **Yes**
- Latency: `2.84s`
- Cards: `chart`

#### Response

````text
Open has the highest loans sanctioned, at 5,677 in all time, 99% of the total across 2 account states. This measures count of loan accounts sanctioned in the period, grouped by account state.
````

#### SQL

````sql
SELECT CASE WHEN UPPER(BTRIM(COALESCE(lam."loan_status", ''))) = 'CLOSED' THEN 'Closed' ELSE 'Open' END AS open_closed_status,
       COUNT(*) AS loan_count
FROM gold.loan_account_master AS lam
WHERE lam."sanction_date" BETWEEN DATE '2000-01-01' AND DATE '2026-08-26'
GROUP BY CASE WHEN UPPER(BTRIM(COALESCE(lam."loan_status", ''))) = 'CLOSED' THEN 'Closed' ELSE 'Open' END, CASE WHEN UPPER(BTRIM(COALESCE(lam."loan_status", ''))) = 'CLOSED' THEN 2 ELSE 1 END
ORDER BY COUNT(*) DESC NULLS LAST
LIMIT 200
````

---

### Q008 — What share of our principal outstanding is in Gold Loans?

- Domain: **Loan Book / Portfolio**
- Expected source: `db`
- Status: **Answered**
- Actual sources: `db`
- Route match: **Yes**
- Latency: `2.96s`
- Cards: `chart`

#### Response

````text
No principal outstanding found as at 26 Aug 2026 with Product eq 1. This measures principal outstanding from each classified account at the requested snapshot.
````

#### SQL

````sql
SELECT SUM(portfolio.principal_outstanding) AS principal_outstanding
FROM gold.portfolio_snapshot_as_of(DATE '2026-08-26') AS portfolio
     JOIN gold.loan_account_master AS lam ON portfolio."entity_num" = lam."entity_num" AND portfolio."loan_account_number" = lam."loan_account_number"
WHERE lam."product_code"::text = '1'
LIMIT 200
````

---

### Q009 — What is our total sanctioned amount this financial year?

- Domain: **Loan Book / Origination**
- Expected source: `db`
- Status: **Answered**
- Actual sources: `db`
- Route match: **Yes**
- Latency: `17.11s`
- Cards: `chart`

#### Response

````text
Sanctioned amount was ₹138.41 Cr in FY27 to date. This measures sum of sanctioned amounts for accounts sanctioned in the period.
````

#### SQL

````sql
SELECT SUM(lam.sanction_amount) AS sanctioned_amount
FROM gold.loan_account_master AS lam
WHERE lam."sanction_date" BETWEEN DATE '2026-04-01' AND DATE '2026-08-26'
LIMIT 200
````

---

### Q010 — How many loans did we sanction in each month of the last year?

- Domain: **Loan Book / Origination**
- Expected source: `db`
- Status: **Clarification**
- Actual sources: `db`
- Route match: **Yes**
- Latency: `10.81s`
- Cards: `clarify`

#### Response

````text
Does "last year" mean the Financial Year ending March 2025 (FY25) or the Calendar Year 2025?
````

---

### Q011 — Show our average sanctioned loan amount by product.

- Domain: **Loan Book / Origination**
- Expected source: `db`
- Status: **Answered**
- Actual sources: `db`
- Route match: **Yes**
- Latency: `5.26s`
- Cards: `chart`

#### Response

````text
Business & MSME Loans is the only product returned, with average ticket size of ₹3.98 L in all time. This measures total sanctioned amount divided by number of loans, grouped by product.
````

#### SQL

````sql
SELECT lam."product_code" AS product,
       (COALESCE(SUM(lam.sanction_amount), 0) / NULLIF(COUNT(*), 0)) AS avg_ticket_size
FROM gold.loan_account_master AS lam
WHERE lam."sanction_date" BETWEEN DATE '2000-01-01' AND DATE '2026-08-26'
GROUP BY lam."product_code"
ORDER BY (COALESCE(SUM(lam.sanction_amount), 0) / NULLIF(COUNT(*), 0)) DESC NULLS LAST
LIMIT 200
````

---

### Q012 — Which schemes have the highest sanctioned amount?

- Domain: **Loan Book / Origination**
- Expected source: `db`
- Status: **Answered**
- Actual sources: `db`
- Route match: **Yes**
- Latency: `6.32s`
- Cards: `chart`

#### Response

````text
MSME Loans has the highest sanctioned amount, at ₹65.47 Cr in all time, 29% of the total across 17 schemes. This measures sum of sanctioned amounts for accounts sanctioned in the period, grouped by scheme.
````

#### SQL

````sql
SELECT lam."scheme_code" AS scheme,
       SUM(lam.sanction_amount) AS sanctioned_amount
FROM gold.loan_account_master AS lam
WHERE lam."sanction_date" BETWEEN DATE '2000-01-01' AND DATE '2026-08-26'
GROUP BY lam."scheme_code"
ORDER BY SUM(lam.sanction_amount) DESC NULLS LAST
LIMIT 200
````

---

### Q013 — Show loans sanctioned by agent for all time.

- Domain: **Loan Book / Origination**
- Expected source: `db`
- Status: **Answered**
- Actual sources: `db`
- Route match: **Yes**
- Latency: `9.46s`
- Cards: `chart`

#### Response

````text
Vanitha has the highest loans sanctioned, at 336 in all time, 6% of the total across 155 agents. This measures count of loan accounts sanctioned in the period, grouped by agent.
````

#### SQL

````sql
SELECT attrs."agent_code" AS agent,
       COUNT(*) AS loan_count
FROM gold.loan_account_master AS lam
     LEFT JOIN gold.loan_reporting_attributes AS attrs ON lam."entity_num" = attrs."entity_num" AND lam."loan_account_number" = attrs."loan_account_number"
WHERE lam."sanction_date" BETWEEN DATE '2000-01-01' AND DATE '2026-08-26'
GROUP BY attrs."agent_code"
ORDER BY COUNT(*) DESC NULLS LAST
LIMIT 200
````

---

### Q014 — Which five branches sanctioned the most loans?

- Domain: **Loan Book / Origination**
- Expected source: `db`
- Status: **Answered**
- Actual sources: `db`
- Route match: **Yes**
- Latency: `9.37s`
- Cards: `chart`

#### Response

````text
Head Office — Credit Division has the highest loans sanctioned, at 5,746 in all time, 100% of the total across 2 branches. This measures count of loan accounts sanctioned in the period, grouped by branch.
````

#### SQL

````sql
SELECT lam."branch_code" AS branch,
       COUNT(*) AS loan_count
FROM gold.loan_account_master AS lam
WHERE lam."sanction_date" BETWEEN DATE '2000-01-01' AND DATE '2026-08-26'
GROUP BY lam."branch_code"
ORDER BY COUNT(*) DESC NULLS LAST
LIMIT 5
````

---

### Q015 — Compare our sanctioned amount with disbursed amount by branch.

- Domain: **Loan Book / Origination**
- Expected source: `db`
- Status: **Answered**
- Actual sources: `db`
- Route match: **Yes**
- Latency: `3.71s`
- Cards: `analysis`

#### Response

````text
Nothing is outside its threshold across 2 indicators.
````

---

### Q016 — Show our monthly sanction amount trend for the last 12 months.

- Domain: **Loan Book / Origination**
- Expected source: `db`
- Status: **Answered**
- Actual sources: `db`
- Route match: **Yes**
- Latency: `8.50s`
- Cards: `chart`

#### Response

````text
Sanctioned amount rose from ₹63.50 L (Oct 2025) to ₹8.36 Cr (Jul 2026), a change of 1215.7%. This measures sum of sanctioned amounts for accounts sanctioned in the period, grouped by month.
````

#### SQL

````sql
SELECT DATE_TRUNC('month', lam."sanction_date")::date AS month,
       SUM(lam.sanction_amount) AS sanctioned_amount
FROM gold.loan_account_master AS lam
WHERE lam."sanction_date" BETWEEN DATE '2025-08-27' AND DATE '2026-08-26'
GROUP BY DATE_TRUNC('month', lam."sanction_date")::date
ORDER BY DATE_TRUNC('month', lam."sanction_date")::date ASC
LIMIT 200
````

---

### Q017 — What is our total disbursed amount this financial year?

- Domain: **Loan Book / Disbursement**
- Expected source: `db`
- Status: **Answered**
- Actual sources: `db`
- Route match: **Yes**
- Latency: `11.79s`
- Cards: `chart`

#### Response

````text
Disbursement was ₹137.16 Cr in FY27 to date. This measures sum of disbursement event amounts in the period.
````

#### SQL

````sql
SELECT SUM(disb.disbursement_amount) AS disbursement_total
FROM gold.loan_disbursement_events AS disb
WHERE disb."disbursement_date" BETWEEN DATE '2026-04-01' AND DATE '2026-08-26'
LIMIT 200
````

---

### Q018 — Show monthly disbursement by product for the last year.

- Domain: **Loan Book / Disbursement**
- Expected source: `db`
- Status: **Answered**
- Actual sources: `db`
- Route match: **Yes**
- Latency: `9.60s`
- Cards: `chart`

#### Response

````text
Disbursement rose from ₹59.50 L (Oct 2025) to ₹9.62 Cr (Jul 2026), a change of 1516.0%. This measures sum of disbursement event amounts in the period, grouped by month and product.
````

#### SQL

````sql
SELECT DATE_TRUNC('month', disb."disbursement_date")::date AS month,
       lam."product_code" AS product,
       SUM(disb.disbursement_amount) AS disbursement_total
FROM gold.loan_disbursement_events AS disb
     JOIN gold.loan_account_master AS lam ON disb."entity_num" = lam."entity_num" AND disb."loan_account_number" = lam."loan_account_number"
WHERE disb."disbursement_date" BETWEEN DATE '2025-08-27' AND DATE '2026-08-26'
GROUP BY DATE_TRUNC('month', disb."disbursement_date")::date, lam."product_code"
ORDER BY DATE_TRUNC('month', disb."disbursement_date")::date ASC
LIMIT 200
````

---

### Q019 — Which branches have the highest disbursement amount?

- Domain: **Loan Book / Disbursement**
- Expected source: `db`
- Status: **Answered**
- Actual sources: `db`
- Route match: **Yes**
- Latency: `9.14s`
- Cards: `chart`

#### Response

````text
Head Office — Credit Division has the highest disbursement, at ₹226.68 Cr in all time, 100% of the total across 2 branches. This measures sum of disbursement event amounts in the period, grouped by branch.
````

#### SQL

````sql
SELECT lam."branch_code" AS branch,
       SUM(disb.disbursement_amount) AS disbursement_total
FROM gold.loan_disbursement_events AS disb
     JOIN gold.loan_account_master AS lam ON disb."entity_num" = lam."entity_num" AND disb."loan_account_number" = lam."loan_account_number"
WHERE disb."disbursement_date" BETWEEN DATE '2000-01-01' AND DATE '2026-08-26'
GROUP BY lam."branch_code"
ORDER BY SUM(disb.disbursement_amount) DESC NULLS LAST
LIMIT 200
````

---

### Q020 — What is our sanction-to-disbursement conversion ratio?

- Domain: **Loan Book / Disbursement**
- Expected source: `db`
- Status: **Clarification**
- Actual sources: `db`
- Route match: **Yes**
- Latency: `16.17s`
- Cards: `clarify`

#### Response

````text
Do you want the sanctioned amount and disbursement amount reported as two separate totals, or a calculated ratio of the two?
````

---

### Q021 — What is our overall collection efficiency?

- Domain: **Loan Book / Collections**
- Expected source: `db`
- Status: **Answered**
- Actual sources: `db`
- Route match: **Yes**
- Latency: `11.55s`
- Cards: `chart`

#### Response

````text
Collection efficiency was 98.8% in all time. This measures total principal and interest paid divided by total principal and interest due.
````

#### SQL

````sql
SELECT (100.0 * COALESCE(SUM(repay.total_paid), 0) / NULLIF(SUM(repay.total_due), 0)) AS collection_efficiency
FROM gold.loan_repayment_events AS repay
WHERE repay."repayment_date" BETWEEN DATE '2000-01-01' AND DATE '2026-08-26'
LIMIT 200
````

---

### Q022 — Show collection efficiency by branch.

- Domain: **Loan Book / Collections**
- Expected source: `db`
- Status: **Answered**
- Actual sources: `db`
- Route match: **Yes**
- Latency: `5.79s`
- Cards: `chart`

#### Response

````text
Head Office — Credit Division has the highest collection efficiency, at 98.8% in all time. This measures total principal and interest paid divided by total principal and interest due, grouped by branch.
````

#### SQL

````sql
SELECT lam."branch_code" AS branch,
       (100.0 * COALESCE(SUM(repay.total_paid), 0) / NULLIF(SUM(repay.total_due), 0)) AS collection_efficiency
FROM gold.loan_repayment_events AS repay
     JOIN gold.loan_account_master AS lam ON repay."entity_num" = lam."entity_num" AND repay."loan_account_number" = lam."loan_account_number"
WHERE repay."repayment_date" BETWEEN DATE '2000-01-01' AND DATE '2026-08-26'
GROUP BY lam."branch_code"
ORDER BY (100.0 * COALESCE(SUM(repay.total_paid), 0) / NULLIF(SUM(repay.total_due), 0)) DESC NULLS LAST
LIMIT 200
````

---

### Q023 — Show total due and total paid by month.

- Domain: **Loan Book / Collections**
- Expected source: `db`
- Status: **Answered**
- Actual sources: `db`
- Route match: **Yes**
- Latency: `13.35s`
- Cards: `chart`

#### Response

````text
Amount due rose from ₹2.14 L (Nov 2025) to ₹6.88 Cr (Jul 2026), a change of 32077.9%. The figures use these governed definitions: Amount due: principal plus interest due in the period; Amount collected: principal plus interest paid in the period, grouped by month.
````

#### SQL

````sql
SELECT DATE_TRUNC('month', repay."repayment_date")::date AS month,
       SUM(repay.total_due) AS amount_due,
       SUM(repay.total_paid) AS amount_collected
FROM gold.loan_repayment_events AS repay
WHERE repay."repayment_date" BETWEEN DATE '2000-01-01' AND DATE '2026-08-26'
GROUP BY DATE_TRUNC('month', repay."repayment_date")::date
ORDER BY DATE_TRUNC('month', repay."repayment_date")::date ASC
LIMIT 200
````

---

### Q024 — Which products have the largest collection shortfall?

- Domain: **Loan Book / Collections**
- Expected source: `db`
- Status: **Answered**
- Actual sources: `db`
- Route match: **Yes**
- Latency: `12.79s`
- Cards: `chart`

#### Response

````text
Business & MSME Loans is the only product returned, with collection shortfall of ₹28.35 L in all time. This measures amount due minus amount paid in the period, grouped by product.
````

#### SQL

````sql
SELECT lam."product_code" AS product,
       SUM(repay.collection_shortfall) AS collection_shortfall
FROM gold.loan_repayment_events AS repay
     JOIN gold.loan_account_master AS lam ON repay."entity_num" = lam."entity_num" AND repay."loan_account_number" = lam."loan_account_number"
WHERE repay."repayment_date" BETWEEN DATE '2000-01-01' AND DATE '2026-08-26'
GROUP BY lam."product_code"
ORDER BY SUM(repay.collection_shortfall) DESC NULLS LAST
LIMIT 200
````

---

### Q025 — What is the total amount collected in the current financial year?

- Domain: **Loan Book / Collections**
- Expected source: `db`
- Status: **Answered**
- Actual sources: `db`
- Route match: **Yes**
- Latency: `12.16s`
- Cards: `chart`

#### Response

````text
Amount collected was ₹19.17 Cr in FY27 to date. This measures principal plus interest paid in the period.
````

#### SQL

````sql
SELECT SUM(repay.total_paid) AS amount_collected
FROM gold.loan_repayment_events AS repay
WHERE repay."repayment_date" BETWEEN DATE '2026-04-01' AND DATE '2026-08-26'
LIMIT 200
````

---

### Q026 — Show our repayment trend for the last 12 months.

- Domain: **Loan Book / Collections**
- Expected source: `db`
- Status: **Answered**
- Actual sources: `db`
- Route match: **Yes**
- Latency: `10.59s`
- Cards: `chart`

#### Response

````text
Amount collected rose from ₹2.14 L (Nov 2025) to ₹6.62 Cr (Jul 2026), a change of 30877.8%. This measures principal plus interest paid in the period, grouped by month.
````

#### SQL

````sql
SELECT DATE_TRUNC('month', repay."repayment_date")::date AS month,
       SUM(repay.total_paid) AS amount_collected
FROM gold.loan_repayment_events AS repay
WHERE repay."repayment_date" BETWEEN DATE '2025-08-27' AND DATE '2026-08-26'
GROUP BY DATE_TRUNC('month', repay."repayment_date")::date
ORDER BY DATE_TRUNC('month', repay."repayment_date")::date ASC
LIMIT 200
````

---

### Q027 — What is our current PAR 30 ratio?

- Domain: **Loan Book / Risk**
- Expected source: `db`
- Status: **Answered**
- Actual sources: `db`
- Route match: **Yes**
- Latency: `5.70s`
- Cards: `chart`

#### Response

````text
PAR 30 was 0.27% as at 26 Aug 2026. This measures principal outstanding over 30 DPD divided by classified principal outstanding. Definition of PAR 30 is pending client sign-off.
````

#### SQL

````sql
SELECT (100.0 * COALESCE(SUM(portfolio.principal_outstanding) FILTER (WHERE portfolio.is_par30), 0) / NULLIF(SUM(portfolio.principal_outstanding), 0)) AS par_30
FROM gold.portfolio_snapshot_as_of(DATE '2026-08-26') AS portfolio
LIMIT 200
````

---

### Q028 — What is our current NPA ratio?

- Domain: **Loan Book / Risk**
- Expected source: `db`
- Status: **Answered**
- Actual sources: `db`
- Route match: **Yes**
- Latency: `8.68s`
- Cards: `chart`

#### Response

````text
NPA ratio was 0.02% as at 26 Aug 2026. This measures nPA-classified principal outstanding divided by classified principal outstanding. Definition of NPA ratio is pending client sign-off.
````

#### SQL

````sql
SELECT (100.0 * COALESCE(SUM(portfolio.principal_outstanding) FILTER (WHERE portfolio.is_npa), 0) / NULLIF(SUM(portfolio.principal_outstanding), 0)) AS npa_ratio
FROM gold.portfolio_snapshot_as_of(DATE '2026-08-26') AS portfolio
LIMIT 200
````

---

### Q029 — Show principal outstanding by DPD bucket.

- Domain: **Loan Book / Risk**
- Expected source: `db`
- Status: **Answered**
- Actual sources: `db`
- Route match: **Yes**
- Latency: `10.27s`
- Cards: `chart`

#### Response

````text
0 (current) has the highest principal outstanding, at ₹194.43 Cr as at 26 Aug 2026, 95% of the total across 5 dpd buckets. This measures principal outstanding from each classified account at the requested snapshot, grouped by dpd bucket.
````

#### SQL

````sql
SELECT CASE WHEN portfolio."dpd_days" = 0 THEN '0 (current)' WHEN portfolio."dpd_days" BETWEEN 1 AND 30 THEN '1-30' WHEN portfolio."dpd_days" BETWEEN 31 AND 60 THEN '31-60' WHEN portfolio."dpd_days" BETWEEN 61 AND 90 THEN '61-90' ELSE '90+' END AS dpd_bucket,
       SUM(portfolio.principal_outstanding) AS principal_outstanding
FROM gold.portfolio_snapshot_as_of(DATE '2026-08-26') AS portfolio
GROUP BY CASE WHEN portfolio."dpd_days" = 0 THEN '0 (current)' WHEN portfolio."dpd_days" BETWEEN 1 AND 30 THEN '1-30' WHEN portfolio."dpd_days" BETWEEN 31 AND 60 THEN '31-60' WHEN portfolio."dpd_days" BETWEEN 61 AND 90 THEN '61-90' ELSE '90+' END, CASE WHEN portfolio."dpd_days" = 0 THEN 0 WHEN portfolio."dpd_days" <= 30 THEN 1 WHEN portfolio."dpd_days" <= 60 THEN 2 WHEN portfolio."dpd_days" <= 90 THEN 3 ELSE 4 END
ORDER BY SUM(portfolio.principal_outstanding) DESC NULLS LAST
LIMIT 200
````

---

### Q030 — How many accounts are classified as SMA-2?

- Domain: **Loan Book / Risk**
- Expected source: `db`
- Status: **Refused**
- Actual sources: `db`
- Route match: **Yes**
- Latency: `34.29s`
- Cards: `refusal`

#### Response

````text
I could not answer that safely from the available data.
````

---

### Q031 — Which branches have the highest overdue amount?

- Domain: **Loan Book / Risk**
- Expected source: `db`
- Status: **Answered**
- Actual sources: `db`
- Route match: **Yes**
- Latency: `12.57s`
- Cards: `chart`

#### Response

````text
Head Office — Credit Division is the only branch returned, with overdue principal of ₹19.57 L as at 26 Aug 2026. This measures principal overdue at the requested portfolio snapshot, grouped by branch.
````

#### SQL

````sql
SELECT lam."branch_code" AS branch,
       SUM(portfolio.principal_overdue) AS overdue_principal
FROM gold.portfolio_snapshot_as_of(DATE '2026-08-26') AS portfolio
     JOIN gold.loan_account_master AS lam ON portfolio."entity_num" = lam."entity_num" AND portfolio."loan_account_number" = lam."loan_account_number"
GROUP BY lam."branch_code"
ORDER BY SUM(portfolio.principal_overdue) DESC NULLS LAST
LIMIT 200
````

---

### Q032 — Show Standard, SMA and NPA account counts by product.

- Domain: **Loan Book / Risk**
- Expected source: `db`
- Status: **Answered**
- Actual sources: `db`
- Route match: **Yes**
- Latency: `10.90s`
- Cards: `chart`

#### Response

````text
Business & MSME Loans has the highest classified loan accounts, at 5,193 as at 26 Aug 2026, 95% of the total across 5 products. This measures count of loan accounts present in the requested classified portfolio snapshot, grouped by product and asset classification.
````

#### SQL

````sql
SELECT lam."product_code" AS product,
       portfolio."asset_code" AS asset_class,
       COUNT(*) AS classified_account_count
FROM gold.portfolio_snapshot_as_of(DATE '2026-08-26') AS portfolio
     JOIN gold.loan_account_master AS lam ON portfolio."entity_num" = lam."entity_num" AND portfolio."loan_account_number" = lam."loan_account_number"
GROUP BY lam."product_code", portfolio."asset_code"
ORDER BY COUNT(*) DESC NULLS LAST
LIMIT 200
````

---

### Q033 — What is the latest supported estimate of India's GDP growth?

- Domain: **Macro / Growth**
- Expected source: `macro`
- Status: **Error**
- Actual sources: `macro`
- Route match: **Yes**
- Latency: `122.12s`
- Cards: `none`

#### Response

````text
Request timed out after 120s
````

---

### Q034 — What does the indexed evidence say about Karnataka's GSDP growth?

- Domain: **Macro / Growth**
- Expected source: `macro`
- Status: **Answered**
- Actual sources: `macro`
- Route match: **Yes**
- Latency: `107.42s`
- Cards: `brief`

#### Response

````text
Based on the Karnataka Economic Survey 2025-26, the Gross State Domestic Product (GSDP) for 2025-26 is projected to grow by 12.9 per cent at current prices, reaching Rs. 32,81,065 crore [karnataka_des, p.43]. At constant (2011-12) prices, the anticipated growth rate is 8.1 per cent, with an estimated value of Rs. 17,23,006 crore [karnataka_des, p.43]. This projected growth significantly exceeds the national GDP growth rate of 8.0 per cent at current prices and 7.4 per cent at constant prices for the same period [karnataka_des, p.43]. Historical data from 2011-12 to 2024-25 shows GSDP growth rates ranging from 1.5 per cent in 2020-21 to 21.4 per cent in 2021-22 at current prices [karnataka_des, p.43].
````

#### Citations

- karnataka_des

---

### Q035 — Which sectors are driving Karnataka's economic growth?

- Domain: **Macro / Growth**
- Expected source: `macro`
- Status: **Answered**
- Actual sources: `macro`
- Route match: **Yes**
- Latency: `18.05s`
- Cards: `brief`

#### Response

````text
Karnataka's economic growth is driven by a diversified mix of high-technology industries, agriculture, and manufacturing. The state's prominence in information technology, biotechnology, and high-technology sectors has positioned it as a premier investment destination, with exports accounting for a substantial share of the Gross State Domestic Product (GSDP) [karnataka_des, p.8]. Agriculture continues to anchor rural livelihoods, projected to grow by 9.1 per cent at constant prices in 2025-26 [karnataka_des, p.8]. The industry sector is also a key driver, projected to grow by 6.7 per cent in 2025-26, with manufacturing specifically contributing 7.2 per cent to industrial expansion [karnataka_des, p.8]. These sectors collectively underpin the state's robust economic trajectory, which outpaced the national growth rate of 7.4 per cent in 2025-26 [karnataka_des, p.8].
````

#### Citations

- karnataka_des

---

### Q036 — How has India's real gross value added changed in the latest supported period?

- Domain: **Macro / Growth**
- Expected source: `macro`
- Status: **Partial**
- Actual sources: `macro`
- Route match: **Yes**
- Latency: `13.96s`
- Cards: `brief`

#### Response

````text
Based on the provided context, India's real Gross Value Added (GVA) at basic prices for the latest supported period, the third quarter of 2025-26, increased by 7.1% [rbi, p.65]. This figure represents the annual growth rate for that specific quarter. The context does not provide a daily measure or a specific "today's" value, as GDP and GSDP are periodic statistics; the latest available data point is from Q3 2025-26.
````

#### Citations

- rbi
- economic_survey

---

### Q037 — What are the main downside risks to India's growth outlook?

- Domain: **Macro / Growth**
- Expected source: `macro`
- Status: **Answered**
- Actual sources: `macro`
- Route match: **Yes**
- Latency: `12.69s`
- Cards: `brief`

#### Response

````text
Downside risks to India's growth outlook stem from powerful global headwinds, including intensified geopolitical competition, complex security environments in Europe, and trade policy driven by security rather than efficiency. These factors create a world that is more risk-averse and exposed to non-linear outcomes with a narrower margin of safety. Financial vulnerabilities associated with leveraged technology investments are looming, and fragility, uncertainty, and episodic shocks are becoming structural features of the global system. Additionally, investor reluctance persists due to the rupee's undervaluation, which, while offsetting some tariff impacts, causes hesitation in committing capital. The balance of risks has shifted perceptibly, with concerns that negative effects of global turmoil may manifest with a lag, potentially escalating minor shocks into larger reverberations.
````

#### Citations

- economic_survey

---

### Q038 — How does Karnataka's economic structure differ from the national economy?

- Domain: **Macro / Growth**
- Expected source: `macro`
- Status: **Answered**
- Actual sources: `macro`
- Route match: **Yes**
- Latency: `15.86s`
- Cards: `brief`

#### Response

````text
Karnataka's economic structure broadly mirrors the national level, characterized by rich diversity and conditions reflecting the country's prevailing trends [karnataka_des, p.42]. While the state ranks ninth in population size at 5.05 per cent of India's total [karnataka_des, p.42], its urbanization share of 38.67 per cent is notably higher than the national average [karnataka_des, p.42]. Economically, the state's progress is driven by Agriculture, Industry, and Services sectors, with the latest 2025-26 Advance Estimates projecting a GSDP of Rs.32,81,065 crore at a growth rate of 12.9 per cent [karnataka_des, p.42]. The state covers 5.83 per cent of the country's total geographical area [karnataka_des, p.42]. Specific comparative data on sectoral contribution ratios between Karnataka and the national economy is not provided in the text.
````

#### Citations

- karnataka_des

---

### Q039 — What does the Economic Survey say about private investment conditions?

- Domain: **Macro / Growth**
- Expected source: `macro`
- Status: **Answered**
- Actual sources: `macro`
- Route match: **Yes**
- Latency: `15.20s`
- Cards: `brief`

#### Response

````text
The Karnataka Economic Survey 2023-24 notes that private investment intentions are improving, providing resilience against external shocks and supporting growth momentum [economic_survey, p.82]. Policy reforms over recent years have lifted India's medium-term growth potential closer to 7 per cent, driven by manufacturing initiatives like PLI schemes, FDI liberalisation, and logistics reforms [economic_survey, p.82]. Sustained public investment in infrastructure reached 4 per cent of GDP, while measures for MSMEs, including expanded credit guarantees and the Unified Lending Interface, have eased credit constraints [economic_survey, p.82]. Additionally, corporate balance sheets have strengthened, with gross non-performing assets declining to 2.2% as of September 2025, and core debt for the private non-financial sector falling to 85.6% of GDP by March 2020 [economic_survey, p.82]. These factors indicate a shift toward greater regulatory clarity and improved investment conditions.
````

#### Citations

- karnataka_des
- economic_survey

---

### Q040 — Summarize the latest supported industrial growth trend in India.

- Domain: **Macro / Growth**
- Expected source: `macro`
- Status: **Answered**
- Actual sources: `macro`
- Route match: **Yes**
- Latency: `14.14s`
- Cards: `brief`

#### Response

````text
India's industrial sector demonstrates sustained momentum with Real Manufacturing GVA growth accelerating to 9.13% in Q2 FY26 [economic_survey, p.25], following a recovery from 7.59% in Q1 FY25. Broader Real Industry GVA growth reached 7.00% in H1 FY26, up from 6.09% in H1 FY25 [economic_survey, p.25]. Structural transformation is evident as medium and high-technology activities now account for 46.3% of total manufacturing value added [economic_survey, p.25]. Business optimism remains high, with the Business Expectations Index indicating positive prospects through mid-2025 [economic_survey, p.25]. Global exports of medium- and high-tech manufactured products show sustained momentum in USD billions [economic_survey, p.25]. These trends reflect resilience and a shift toward advanced manufacturing sectors.
````

#### Citations

- economic_survey

---

### Q041 — What is the latest inflation trend supported by the macro sources?

- Domain: **Macro / Inflation**
- Expected source: `macro`
- Status: **Answered**
- Actual sources: `macro`
- Route match: **Yes**
- Latency: `10.30s`
- Cards: `brief`

#### Response

````text
Based on the Economic Survey 2025-26, headline CPI inflation declined to 1.7 per cent in FY26 (April–December), driven by sharp disinflation in food prices due to favourable farm conditions and supply-side interventions [economic_survey, p.75]. While core inflation has shown persistence, it is largely influenced by price spikes in precious metals; excluding these, underlying inflation pressures appear materially softer [economic_survey, p.75]. The outlook remains benign, supported by supply-side conditions and GST rationalisation, though core inflation requires monitoring against potential global base metal price pressures [economic_survey, p.75].
````

#### Citations

- economic_survey

---

### Q042 — What factors are driving food inflation in India?

- Domain: **Macro / Inflation**
- Expected source: `macro`
- Status: **Answered**
- Actual sources: `macro`
- Route match: **Yes**
- Latency: `8.62s`
- Cards: `brief`

#### Response

````text
Based on the provided context, there are no factors driving food inflation in India identified. The text explicitly states that food inflation was "subdued" and recorded a decline of -2.71% during the April-December 2025 period, contributing to the lowest headline inflation rate of 1.7% since the beginning of the CPI series [economic_survey, p.16]. Consequently, the document does not list any drivers causing food inflation, as the metric was decreasing rather than rising.
````

#### Citations

- economic_survey

---

### Q043 — How could inflation affect household borrowing demand?

- Domain: **Macro / Inflation**
- Expected source: `macro`
- Status: **Partial**
- Actual sources: `macro`
- Route match: **Yes**
- Latency: `6.20s`
- Cards: `brief`

#### Response

````text
The provided context does not contain information explaining the impact of inflation on household borrowing demand. While it notes that easing inflation improved real purchasing power and supported consumption, it does not discuss how these dynamics specifically influence the demand for household loans or credit.
````

#### Citations

- economic_survey

---

### Q044 — What does the evidence say about rural versus urban inflation?

- Domain: **Macro / Inflation**
- Expected source: `macro`
- Status: **Answered**
- Actual sources: `macro`
- Route match: **Yes**
- Latency: `13.65s`
- Cards: `brief`

#### Response

````text
Based on the Karnataka Economic Survey 2023-24 (p.65), rural inflation trends diverged sharply from urban trends in late 2023. While urban prices rose steadily, peaking at a 4.02% increase in October 2023 (p.65), rural inflation spiked dramatically to 11.35% in July 2023 before contracting sharply to -5.07% in September 2023 (p.65). By November 2023, rural inflation recovered to 4.01%, still slightly lower than the urban rate of 3.12% for that month (p.65). Historically, rural indices were generally lower than urban ones until the 2015-16 period, after which rural volatility increased significantly compared to the more stable urban trajectory (p.65).
````

#### Citations

- karnataka_des

---

### Q045 — What policy stance does the latest indexed RBI material describe?

- Domain: **Macro / Monetary Policy**
- Expected source: `macro`
- Status: **Answered**
- Actual sources: `macro`
- Route match: **Yes**
- Latency: `17.82s`
- Cards: `brief`

#### Response

````text
The latest RBI policy stance, as per the June 2026 Monetary Policy Statement, is **neutral**. The Monetary Policy Committee (MPC) voted unanimously to keep the policy repo rate under the Liquidity Adjustment Facility (LAF) unchanged at **5.25 per cent** [rbi, p.9]. Consequently, the Standing Deposit Facility (SDF) rate remains at **5.00 per cent**, while the Marginal Standing Facility (MSF) rate and the Bank Rate are maintained at **5.50 per cent** [rbi, p.9]. This decision was made during the 61st MPC meeting held from June 3 to 5, 2026, amidst global economic turbulence and domestic supply chain disruptions [rbi, p.15]. The Governor emphasized that while the economy is relatively strong, the MPC remains cautious regarding inflation and growth risks, warranting a neutral stance to balance these challenges [rbi, p.9].
````

#### Citations

- rbi

---

### Q046 — How do repo-rate changes transmit to lending rates?

- Domain: **Macro / Monetary Policy**
- Expected source: `macro`
- Status: **Answered**
- Actual sources: `macro`
- Route match: **Yes**
- Latency: `14.80s`
- Cards: `brief`

#### Response

````text
The transmission mechanism from repo rates to lending rates is uneven across sectors and bank types. During the easing cycle (February 2025 to April 2026), the pass-through to lending rates was more pronounced in private sector banks, while public sector banks showed stronger transmission to deposit rates [rbi, p.53]. The overall interest rate effect is calculated based on specific weights, such as those at January 2025 [rbi, p.53]. Additionally, the weighted average call rate, the operating target of monetary policy, remained below the policy repo rate in FY26, averaging 8 basis points lower [economic_survey, p.8]. This indicates that while the repo rate sets the policy direction, the actual transmission to lending rates like WALR (Weighted Average Lending Rate) and MCLR varies by institution and loan type [rbi, p.53].
````

#### Citations

- rbi
- economic_survey

---

### Q047 — What does the RBI evidence say about liquidity conditions?

- Domain: **Macro / Monetary Policy**
- Expected source: `macro`
- Status: **Partial**
- Actual sources: `macro`
- Route match: **Yes**
- Latency: `13.32s`
- Cards: `brief`

#### Response

````text
The provided context does not contain specific evidence on overall liquidity conditions, such as net liquidity levels or trends, for the period ending June 2026. While the RBI Bulletin lists daily liquidity operations (Repo, Reverse Repo, OMO) showing significant net absorption (negative values) in April 2026, and includes a table for Liquidity Aggregates (NM3, L1, L2, L3) without specific numerical values filled in, it does not offer a definitive statement or calculated figure characterizing the current liquidity stance. Therefore, based strictly on the text, no conclusion on liquidity conditions can be drawn.
````

#### Citations

- rbi

---

### Q048 — How could tighter monetary conditions affect MSME credit demand?

- Domain: **Macro / Monetary Policy**
- Expected source: `macro`
- Status: **Partial**
- Actual sources: `macro`
- Route match: **Yes**
- Latency: `9.77s`
- Cards: `brief`

#### Response

````text
The provided context does not contain information regarding the impact of tighter monetary conditions on MSME credit demand. Instead, the text highlights that MSME credit demand has remained robust and robust, with bank credit to the sector increasing by 21.8 per cent in November 2025 compared to the previous year [economic_survey, p.145]. This growth is attributed to regulatory measures like revised collateral guidelines and Union Budget enhancements rather than monetary tightening. Consequently, the document does not support an analysis of how restrictive monetary policy affects this specific demand metric.
````

#### Citations

- economic_survey

---

### Q049 — How is bank credit growth trending in the latest supported period?

- Domain: **Macro / Credit**
- Expected source: `macro`
- Status: **Answered**
- Actual sources: `macro`
- Route match: **Yes**
- Latency: `15.24s`
- Cards: `brief`

#### Response

````text
In the latest supported period (FY26 thus far), bank credit growth shows a moderate overall increase, but momentum remains robust specifically within the MSME sector. As of November 2025, bank credit to MSMEs rose by 21.8% year-on-year, compared to 13% in November 2024 [economic_survey, p.145]. Within this, credit to micro and small enterprises surged by 24.6% in November 2025, up from 10.2% the prior year [economic_survey, p.145]. Broader commercial sector resource flow also accelerated, reaching ₹30.8 lakh crore in April-December 2025, a 44.7% increase over the previous year [economic_survey, p.145]. However, non-food bank credit growth of 58.6% and non-bank source growth of 23.8% as of December 2025 indicate a significant shift toward alternative financing channels [economic_survey, p.145].
````

#### Citations

- economic_survey

---

### Q050 — What macro factors are influencing retail credit growth?

- Domain: **Macro / Credit**
- Expected source: `macro`
- Status: **Answered**
- Actual sources: `macro`
- Route match: **Yes**
- Latency: `14.87s`
- Cards: `brief`

#### Response

````text
Retail credit growth is driven by robust MSME sector momentum, with bank credit rising 21.8% YoY in November 2025 [economic_survey, p.145]. This expansion is supported by regulatory measures, including revised gold pledge guidelines and Union Budget initiatives like enhanced guarantee covers and new credit cards for micro-enterprises [economic_survey, p.145]. Additionally, the revision of MSME classification thresholds, raising investment limits and turnover criteria, has facilitated higher credit uptake [economic_survey, p.145]. Broader commercial sector resource flows also bolster this trend, increasing to ₹30.8 lakh crore in April-December 2025, a 44.7% YoY rise [economic_survey, p.145]. Non-bank financial resources contributed significantly, growing 23.8% YoY by December 2025, while non-food bank credit surged 58.6% YoY [economic_survey, p.145]. These factors collectively indicate a favorable macroeconomic environment for retail lending.
````

#### Citations

- economic_survey

---

### Q051 — What does the indexed evidence say about credit conditions for small firms?

- Domain: **Macro / Credit**
- Expected source: `macro`
- Status: **Partial**
- Actual sources: `macro`
- Route match: **Yes**
- Latency: `7.96s`
- Cards: `brief`

#### Response

````text
The provided context does not contain information regarding credit conditions for small firms. While the text defines MSMEs and lists abbreviations related to funding schemes like ISEC (Interest Subsidy Eligibility Certificate) on page 163, it does not offer specific data or analysis on the actual credit conditions faced by these firms. The available statistics focus on employment distribution, gender-wise ownership, and investment ranges rather than lending terms or availability.
````

#### Citations

- msme

---

### Q052 — Are deposit growth and credit growth moving at similar rates?

- Domain: **Macro / Credit**
- Expected source: `macro`
- Status: **Answered**
- Actual sources: `knowledge`
- Route match: **No**
- Latency: `8.90s`
- Cards: `brief`

#### Response

````text
Deposit growth and credit growth are distinct metrics that measure the expansion of bank liabilities versus assets, respectively, and they do not necessarily move at similar rates. Deposit growth tracks the increase in customer funds held in accounts, while credit growth reflects the rise in sanctioned loan amounts, which is calculated using the "Sanctioned amount" from the provided catalog. Although both indicate bank activity, confusing them is common because one represents money flowing into the bank, whereas the other represents money flowing out to borrowers.
````

---

### Q053 — What is the latest supported outlook for India's MSME sector?

- Domain: **Macro / MSME**
- Expected source: `macro`
- Status: **Partial**
- Actual sources: `macro`
- Route match: **Yes**
- Latency: `8.04s`
- Cards: `brief`

#### Response

````text
The provided context does not contain a specific latest supported outlook or forecast for India's MSME sector. It details the sector's historical contribution (30% of GDP, over 45% of exports) [msme, p.7] and outlines the Ministry's vision for sustainable development and its objectives to address challenges like access to credit and technology. However, no forward-looking projections or specific future outlook data are included in the text.
````

#### Citations

- msme

---

### Q054 — What financing gaps do Indian MSMEs face?

- Domain: **Macro / MSME**
- Expected source: `macro`
- Status: **Answered**
- Actual sources: `macro`
- Route match: **Yes**
- Latency: `15.09s`
- Cards: `brief`

#### Response

````text
Indian MSMEs face a critical financing gap driven by delayed payments, with an estimated ₹8.1 lakh crore locked in arrears, severely impacting working capital and restricting growth [msme, p.34]. This liquidity crunch forces enterprises to avoid legal recourse due to fears of damaging long-term buyer relationships, thereby perpetuating the debt cycle [msme, p.34]. While the MSME Samadhaan Portal has facilitated the resolution of ₹14,638.38 crore through 53,911 disposed cases and ₹3,018.37 crore via mutual settlements as of December 2025, a significant portion of ₹8,397.25 crore remains under review and ₹14,243 crore has been converted into formal cases, indicating unresolved financial distress [msme, p.13]. The persistence of these delays highlights a structural gap in timely credit availability for the sector [msme, p.34].
````

#### Citations

- msme

---

### Q055 — Which MSME segments appear most credit constrained?

- Domain: **Macro / MSME**
- Expected source: `macro`
- Status: **Answered**
- Actual sources: `macro`
- Route match: **Yes**
- Latency: `7.25s`
- Cards: `brief`

#### Response

````text
The provided context does not identify specific credit-constrained MSME segments. It broadly lists "Access to Credit" as a key objective and mentions challenges like "Inadequate Skilling/Reskilling" and "Infrastructural Bottlenecks" (p.7), but it does not specify which segments within the MSME sector face credit constraints.
````

#### Citations

- msme

---

### Q056 — What does the MSME annual report say about enterprise formalization?

- Domain: **Macro / MSME**
- Expected source: `macro`
- Status: **Answered**
- Actual sources: `macro`
- Route match: **Yes**
- Latency: `14.02s`
- Cards: `brief`

#### Response

````text
The MSME Annual Report 2024-25 indicates that nearly 4,000 enterprises obtained a Basic Certificate in FY 2024-25, with 742 expressing willingness to advance to the Intermediate level [msme, p.101]. Formalization efforts include the formation of 202 Groups of Enterprises comprising nearly 1,600 MSMEs, where consultant selection is complete and lean implementation is underway in 129 groups [msme, p.101]. Additionally, 294 awareness and 15 consultant training programs were conducted since April 2024 to support these initiatives [msme, p.101]. The report also highlights MoUs with major OEMs to onboard supplier bases, further integrating MSMEs into formal supply chains [msme, p.101]. These findings reflect a structured approach to enterprise formalization through certification, capacity building, and supply chain integration.
````

#### Citations

- msme

---

### Q057 — How important are micro enterprises within the Indian MSME base?

- Domain: **Macro / MSME**
- Expected source: `macro`
- Status: **Partial**
- Actual sources: `macro`
- Route match: **Yes**
- Latency: `7.54s`
- Cards: `brief`

#### Response

````text
The provided context does not contain specific data or figures detailing the importance of micro enterprises within the Indian MSME base. While it states that MSMEs generally play a pivotal role in driving entrepreneurial growth, fostering innovation, and generating significant employment at lower capital costs, it does not isolate the specific contribution of the micro-enterprise segment to the overall MSME base. Therefore, the exact importance of micro enterprises cannot be determined from the text.
````

#### Citations

- msme

---

### Q058 — What barriers limit MSME access to formal credit?

- Domain: **Macro / MSME**
- Expected source: `macro`
- Status: **Answered**
- Actual sources: `macro`
- Route match: **Yes**
- Latency: `14.52s`
- Cards: `brief`

#### Response

````text
The provided context does not explicitly list barriers limiting MSME access to formal credit. Instead, it details government initiatives designed to overcome such hurdles. Specifically, the Credit Guarantee Fund Trust for Micro and Small Enterprises (CGTMSE) facilitates collateral-free and third-party guarantee-free loans, with a guarantee ceiling of ₹ 10 crore per borrower [msme, p.93]. The scheme offers guarantee coverage ranging from 75% to 90% [msme, p.93] and includes fee concessions for special categories like women-owned or SC/ST-owned enterprises [msme, p.93]. Additionally, the PM Vishwakarma Scheme, launched in September 2023 with an outlay of ₹ 13,000 crore, aims to support artisans by enhancing their product quality and integrating them into value chains [msme, p.86]. While these measures address credit accessibility, the text does not describe the specific obstacles preventing access.
````

#### Citations

- msme

---

### Q059 — How could digital public infrastructure improve MSME lending?

- Domain: **Macro / MSME**
- Expected source: `macro`
- Status: **Partial**
- Actual sources: `macro`
- Route match: **Yes**
- Latency: `7.73s`
- Cards: `brief`

#### Response

````text
The provided context does not contain information regarding how digital public infrastructure impacts MSME lending. While the text details digital platforms like the MSME Sambandh Portal and GeM that facilitate procurement and registration, and mentions financial support mechanisms such as the Self Reliant India Fund, it does not analyze the specific effects of digital infrastructure on lending volumes or credit access for MSMEs.
````

#### Citations

- msme

---

### Q060 — What macro indicators should a Karnataka MSME lender monitor?

- Domain: **Macro / MSME**
- Expected source: `macro`
- Status: **Answered**
- Actual sources: `macro`
- Route match: **Yes**
- Latency: `16.12s`
- Cards: `brief`

#### Response

````text
As of December 2025, Karnataka's MSME sector comprises 24.86 lakh registered entities on the Udyam Portal, employing 235.27 lakh persons [karnataka_des, p.151]. For the 2025-26 fiscal year, Rs.69,211.08 lakh was allocated to the sector, with Rs.28,442.84 lakh utilized by December 2025 [karnataka_des, p.151]. Support mechanisms include capital and interest subsidies, SCSP, TSP schemes, and cluster development programs. While the Large and Medium Industries sector received a budget of Rs.129,433.67 lakh [karnataka_des, p.151], the MSME focus remains on artisan and traditional sector support. Additionally, 350 projects worth Rs.65,979.54 crore were approved under the Single Window system, expected to generate 98,279 jobs [karnataka_des, p.151]. These figures reflect the state's commitment to MSME growth through targeted financial allocation and policy facilitation.
````

#### Citations

- karnataka_des

---

### Q061 — What are the main economic strengths of Karnataka?

- Domain: **Macro / Karnataka**
- Expected source: `macro`
- Status: **Answered**
- Actual sources: `macro`
- Route match: **Yes**
- Latency: `17.29s`
- Cards: `brief`

#### Response

````text
Karnataka's economic strengths include a robust, diversified economy driven by IT, biotechnology, and high-tech industries, which significantly contribute to exports. The state's Gross State Domestic Product (GSDP) grew by 12.9% at current prices in 2025-26, reaching Rs.32.81 lakh crore [karnataka_des, p.8], with a constant price growth of 8.1%, outpacing the national rate of 7.4% [karnataka_des, p.8]. Its share in India's GDP rose to 9.19% in 2025-26 [karnataka_des, p.8]. The per capita income stood at Rs.4,33,326 in 2025-26, approximately 97% higher than the All-India average [karnataka_des, p.8]. Sectoral recovery is evident, with agriculture projected to grow by 9.1% and the industry sector by 6.7% at constant prices in 2025-26 [karnataka_des, p.8]. Additionally, the state maintains strong ecological assets and has transformed infrastructure in renewable energy and urban mobility.
````

#### Citations

- karnataka_des

---

### Q062 — Which Karnataka sectors create opportunities for MSME lending?

- Domain: **Macro / Karnataka**
- Expected source: `macro`
- Status: **Answered**
- Actual sources: `macro`
- Route match: **Yes**
- Latency: `17.21s`
- Cards: `brief`

#### Response

````text
The MSME sector in Karnataka is a vital economic pillar, with 24.86 lakh registered units generating employment for 235.27 lakh persons as of December 2025 [karnataka_des, p.151]. Significant lending opportunities exist within artisan and traditional sectors, supported by Rs.69,211.08 lakh allocated during 2025-26, of which Rs.28,442.84 lakh was utilized by December 2025 [karnataka_des, p.151]. These funds are channeled through capital and interest subsidies, SCSP, TSP schemes, and cluster development programmes [karnataka_des, p.151]. Additionally, the Large and Medium Industries sector offers opportunities via the Clean Mobility Policy 2025-30, which targets Rs.50,000 crore in investment and one lakh jobs [karnataka_des, p.151]. During 2025-26, 350 projects involving Rs.65,979.54 crore were approved, expected to create 98,279 jobs, further expanding the lending landscape [karnataka_des, p.151].
````

#### Citations

- karnataka_des

---

### Q063 — What regional risks could weaken credit demand in Karnataka?

- Domain: **Macro / Karnataka**
- Expected source: `macro`
- Status: **Answered**
- Actual sources: `macro`
- Route match: **Yes**
- Latency: `13.16s`
- Cards: `brief`

#### Response

````text
Regional risks affecting credit demand in Karnataka stem primarily from fiscal pressures that constrain public expenditure quality and efficiency. The state faces a medium-term fiscal risk with outstanding liabilities projected to reach 27 per cent of GSDP by 2025-26, potentially forcing difficult rationalization of revenue expenditures and impacting credit availability. Additionally, the state runs a revenue deficit of about 1 per cent of GSDP, necessitating hard decisions on spending. The sheer volume of 1806 schemes limits administrative efficiency, while high subsidies, particularly non-merit components, divert resources from growth objectives. Declining central devolution and GST-related uncertainties further strain state finances, reducing the capacity to support credit demand through public investment. These fiscal challenges create an environment where prudent management is required to prevent a deterioration in the quality of expenditures that could dampen economic activity and credit uptake.
````

#### Citations

- karnataka_des

---

### Q064 — How does urbanization influence Karnataka's lending opportunity?

- Domain: **Macro / Karnataka**
- Expected source: `macro`
- Status: **Answered**
- Actual sources: `macro`
- Route match: **Yes**
- Latency: `16.71s`
- Cards: `brief`

#### Response

````text
Urbanization in Karnataka, with 39.27% of the population living in urban areas as per the 2011 census [karnataka_des, p.149], drives lending opportunities primarily through housing demand. The state's focus on urban housing schemes, such as PMAY-U and Vajpayee Urban Housing Scheme, which saw 3857 houses constructed under the latter by November 2023 [karnataka_des, p.149], creates significant credit demand for construction and home loans. However, the lopsided nature of this growth, with Bangalore at 90.94% urbanization versus Kodagu at 14.61% [karnataka_des, p.149], concentrates lending risks in specific districts. The state's allocation of Rs.18,127.29 crore for urban development in 2023-24 [karnataka_des, p.149] further signals a robust pipeline for infrastructure and housing finance. Consequently, while urbanization expands the lending base, the high regional variation necessitates differentiated credit strategies to manage concentration risks in primate cities like Bangalore.
````

#### Citations

- karnataka_des

---

### Q065 — Who are the indexed competitors serving Karnataka MSME borrowers?

- Domain: **Competitive / Landscape**
- Expected source: `competitive`
- Status: **Answered**
- Actual sources: `competitive`
- Route match: **Yes**
- Latency: `23.49s`
- Cards: `brief`

#### Response

````text
Indexed competitors serving Karnataka MSME borrowers include Kinara Capital, SIDBI, Karnataka State Co-operative Apex Bank, Karnataka State Financial Corporation, Bellary Urban Co-operative Bank, Bhatkal Urban Co-operative Bank, and Kaujalgi Urban Co-operative Bank.

Kinara Capital explicitly offers collateral-free business loans ranging from Rs. 1 lakh to Rs. 30 lakhs with quicker disburseals and minimum documentation [Kinara Capital]. It also provides HerVikas loans tailored for women-owned businesses [Kinara Capital].

SIDBI lists MSME Loans and schemes like PM Vishwakarma and PM SVANidhi, though specific Karnataka MSME targeting details are absent in the provided text [SIDBI].

Several co-operative banks, including Karnataka State Co-operative Apex Bank, Bellary Urban Co-operative Bank, Bhatkal Urban Co-operative Bank, and Kaujalgi Urban Co-operative Bank, show MSME or small-business relevance in their extracted materials and possess local branch networks supporting relationship-led acquisition [Karnataka State Co-operative Apex Bank][Bellary Urban Co-operative Bank][Bhatkal Urban Co-operative Bank][Kaujalgi Urban Co-operative Bank]. However, explicit MSME product details, rates, or ticket sizes are not provided for these co-operatives in the supplied evidence.
````

#### Citations

- Kinara Capital
- SIDBI
- Karnataka State Co-operative Apex Bank

---

### Q066 — How do co-operative banks and NBFCs differ in their MSME positioning?

- Domain: **Competitive / Landscape**
- Expected source: `competitive`
- Status: **Answered**
- Actual sources: `competitive`
- Route match: **Yes**
- Latency: `18.53s`
- Cards: `brief`

#### Response

````text
Co-operative banks position MSME lending through local branch presence and rural/agriculture differentiation, supporting relationship-led acquisition [Karnataka State Co-operative Apex Bank]. They explicitly benchmark against digital-first lenders to highlight their geographic reach [Kaujalgi Urban Co-operative Bank]. In contrast, NBFCs and fintechs compete on faster approval, clearer pricing, and digital onboarding [Karnataka State Co-operative Apex Bank]. While co-ops offer detailed loan pages for product comparison, NBFCs leverage speed and digital rails [Karnataka State Co-operative Apex Bank]. Specific NBFC examples show explicit MSME products like working capital loans for small business entrepreneurs with defined eligibility, whereas some co-op crawls note MSME positioning is not always explicit in public text [Bellary Urban Co-operative Bank]. Both sectors face credit-quality pressures in local and unsecured segments [Karnataka State Co-operative Apex Bank].

**Gap:** No specific NBFC names or rates are provided in the supplied text for direct rate/ticket comparison.
````

#### Citations

- Karnataka State Co-operative Apex Bank
- Bellary Urban Co-operative Bank
- Bhatkal Urban Co-operative Bank
- Kaujalgi Urban Co-operative Bank
- Belgaum Industrial Co-operative Bank

---

### Q067 — Where does the indexed competitor evidence show white space in MSME lending?

- Domain: **Competitive / Landscape**
- Expected source: `competitive`
- Status: **Answered**
- Actual sources: `competitive`
- Route match: **Yes**
- Latency: `20.50s`
- Cards: `brief`

#### Response

````text
Competitor evidence reveals significant white space in MSME lending for traditional Karnataka co-operative lenders. While institutions like the Karnataka State Co-operative Apex Bank and Kaujalgi Urban Co-operative Bank explicitly reference MSME relevance and digital channels, they lack explicit details on product eligibility, documentation, and application journeys found in fintech profiles like Kinara Capital [Kinara Capital]. Kinara highlights "collateral-free business loans" and "Quick Approval and Disbursal" within 24 hours, contrasting with co-operatives where "Financial figures may require annual reports" and public information is often fragmented [Belagavi District Central Co-operative Bank]. The threat of "digital-first MSME platforms" competing on "faster approval, clearer pricing, and digital onboarding" suggests co-operatives are losing ground on speed and transparency [Karnataka State Co-operative Apex Bank]. The gap lies in the co-operatives' inability to match the unsecured, rapid-turnaround offerings of NBFCs and fintechs, leaving room for product bundling and clearer eligibility communication [Bellary Urban Co-operative Bank].
````

#### Citations

- Karnataka State Co-operative Apex Bank
- Kaujalgi Urban Co-operative Bank
- Bellary Urban Co-operative Bank
- Karnataka State Financial Corporation
- SIDBI
- Belgaum Industrial Co-operative Bank

---

### Q068 — Which indexed lenders emphasize small-business finance?

- Domain: **Competitive / Landscape**
- Expected source: `competitive`
- Status: **Answered**
- Actual sources: `competitive`
- Route match: **Yes**
- Latency: `11.74s`
- Cards: `brief`

#### Response

````text
Based on the indexed evidence, the Small Industries Development Bank of India (SIDBI) is the primary lender emphasizing small-business finance. Its portfolio explicitly includes "Loans For MSMEs," "MSME Loans," and specific schemes like the "India Microfinance Equity Scheme," "PM Vishwakarma Scheme," and "PM SVANidhi Scheme" [SIDBI]. SIDBI also operates the "Udyam Assist Platform" and publishes recurring "Small Business Spotlight" reports to track the sector [SIDBI]. The institution highlights its role in empowering women entrepreneurs and accelerating enterprise growth through loan sanctions [SIDBI]. No other co-operative lenders are mentioned in the provided text for comparison.
````

#### Citations

- SIDBI

---

### Q069 — Compare the geographic positioning of the indexed Karnataka lenders.

- Domain: **Competitive / Landscape**
- Expected source: `competitive`
- Status: **Answered**
- Actual sources: `competitive`
- Route match: **Yes**
- Latency: `25.85s`
- Cards: `brief`

#### Response

````text
Karnataka lenders exhibit distinct geographic positioning strategies. **Karnataka State Financial Corporation (KSFC)** maintains a statewide presence with specific branches listed in Bagalkot, Ballari, Belagavi, Bidar, Chamarajanagara, Chikkamagaluru, Haveri, Madikeri, Mandya, Mangaluru, Mysuru, Tumakuru, and Bengaluru [Karnataka State Financial Corporation]. **Kaujalgi Urban Co-operative Bank** operates exclusively within Belagavi District, emphasizing local community reach [Kaujalgi Urban Co-operative Bank]. **Bhatkal Urban Co-operative Bank** is similarly hyper-localized, with its head office and branches concentrated in Bhatkal, Uttara Kannada District [Bhatkal Urban Co-operative Bank].

In contrast, **Kinara Capital**, while noting its "1st Branch Opens in Karnataka," primarily lists operational details for Andhra Pradesh and Gujarat, indicating a limited or nascent footprint in Karnataka compared to the established state-wide networks of KSFC or the district-specific focus of the co-operative banks [Kinara Capital]. The Apex Bank supports these institutions but does not list specific branch locations in the provided text [Karnataka State Co-operative Apex Bank].
````

#### Citations

- Kinara Capital
- Karnataka State Financial Corporation
- Karnataka State Co-operative Apex Bank
- Bhatkal Urban Co-operative Bank

---

### Q070 — Which competitors appear focused on underserved enterprise segments?

- Domain: **Competitive / Landscape**
- Expected source: `competitive`
- Status: **Answered**
- Actual sources: `competitive`
- Route match: **Yes**
- Latency: `19.85s`
- Cards: `brief`

#### Response

````text
Competitors explicitly focused on underserved enterprise segments include Kinara Capital and SIDBI. Kinara Capital targets MSME women entrepreneurs with collateral-free loans via its "HerVikas Business Loan for Women" and offers specialized products like Green Loans and Machinery Purchase Loans [Kinara Capital]. SIDBI supports the sector through the India Microfinance Equity Scheme and the Udyam Assist Platform, focusing on small business development [SIDBI].

Several Karnataka co-operative banks, such as Kaujalgi Urban Co-operative Bank, Belgaum Industrial Co-operative Bank, and Bhatkal Urban Co-operative Bank, indicate relevance to small-business finance through MSME and working-capital references, though their specific underserved segment strategies are less detailed than Kinara's [Kaujalgi Urban Co-operative Bank]. In contrast, Karnataka State Financial Corporation and Belagavi District Central Co-operative Bank show weaker explicit MSME positioning in available data [Karnataka State Financial Corporation]. No specific rates or ticket sizes are provided for these institutions.
````

#### Citations

- Karnataka State Co-operative Apex Bank
- Kaujalgi Urban Co-operative Bank
- SIDBI
- Karnataka State Financial Corporation
- Bellary Urban Co-operative Bank

---

### Q071 — What loan products does Kinara Capital highlight for MSMEs?

- Domain: **Competitive / Products**
- Expected source: `competitive`
- Status: **Answered**
- Actual sources: `competitive`
- Route match: **Yes**
- Latency: `17.88s`
- Cards: `brief`

#### Response

````text
Kinara Capital offers four primary loan products for MSMEs:

1. **MSME Business Loan**: Collateral-free, ranging from ₹50,000 to ₹30 lakhs with a tenure of 12 to 54 months, suitable for working capital and expansion.
2. **Machinery Purchase Loan**: For buying new or second-hand machinery, ranging from ₹1 lakh to ₹30 lakhs over 12 to 60 months.
3. **Short-Term Working Capital Loan**: For small equipment costs, ranging from ₹50,000 to ₹2 lakhs.
4. **Loan Against Property (LAP)**: For larger financing, allowing pledges of residential or commercial property for amounts between ₹5 lakhs and ₹40 lakhs over 72 to 120 months.

Additionally, Kinara offers a **HerVikas Loan**, though specific terms are not detailed in the provided text. The lender emphasizes collateral-free options, quick disbursals (up to 24 hours), and minimal documentation. Eligibility requires Udyam registration and a minimum business vintage of 12 months for manufacturing units.

[Kinara Capital]
````

#### Citations

- Kinara Capital

---

### Q072 — What lending products are described for SIDBI?

- Domain: **Competitive / Products**
- Expected source: `competitive`
- Status: **Answered**
- Actual sources: `competitive`
- Route match: **Yes**
- Latency: `12.07s`
- Cards: `brief`

#### Response

````text
Based on the provided indexed passages, specific lending product names or detailed terms (such as interest rates or ticket sizes) are not explicitly listed. The documents confirm the existence of specific schemes and platforms, including the **India Microfinance Equity Scheme** and the **Udyam Assist Platform** [SIDBI]. Additionally, a category titled **Other Loan Products** is referenced via a dedicated URL, implying a broader range of offerings exists but is not detailed in the text [SIDBI]. The text also notes the establishment of **SIDBI Venture Capital Limited** and **CGTMSE**, which relate to financing and guarantee mechanisms rather than direct loan products [SIDBI]. No direct comparison with other institutions is possible as no other lender data is supplied.
````

#### Citations

- SIDBI

---

### Q073 — What business-loan products are documented for KSFC?

- Domain: **Competitive / Products**
- Expected source: `competitive`
- Status: **Answered**
- Actual sources: `db`
- Route match: **No**
- Latency: `32.77s`
- Cards: `chart`

#### Response

````text
The query returned 14 row(s) covering product name, scheme name. List of distinct business and MSME product and scheme names from the loan book. This uses a validated read-only generated query rather than a reviewed metric; check Source details before relying on it.
````

#### SQL

````sql
SELECT DISTINCT
  product_name,
  scheme_name
FROM gold.loan_account_master
WHERE
  product_code = 16
LIMIT 5000
````

---

### Q074 — What loan facilities does Belagavi DCCB offer?

- Domain: **Competitive / Products**
- Expected source: `competitive`
- Status: **Answered**
- Actual sources: `competitive`
- Route match: **Yes**
- Latency: `19.67s`
- Cards: `brief`

#### Response

````text
The provided indexed passages do not list specific loan facilities offered by Belagavi District Central Co-operative Bank (BDCC), such as home loans, education loans, or business loans, despite mentioning pages like "Loans Advances" and "Small Business" on its website [Belagavi District Central Co-operative Bank]. The text only quantifies disbursements for Kissan Credit Cards (Rs 1,22,489 Lakh) and sugar factories (Rs 50,224 Lakh) [Belagavi District Central Co-operative Bank].

In contrast, South Canara District Central Co-operative Bank explicitly lists a wide array of facilities including Home Loans, Education Loans, Vehicle Loans, and various business loan types like Cash Credit and Pledge Loans [South Canara District Central Co-operative Bank]. While BDCC mentions specific limits for sugar factory stores and spares (120% of average utilization) [Belagavi District Central Co-operative Bank], it lacks the detailed product menu found in the South Canara evidence. No direct comparison of specific product features or rates is possible due to the absence of BDCC's detailed facility list in the provided text.
````

#### Citations

- Belagavi District Central Co-operative Bank
- South Canara District Central Co-operative Bank

---

### Q075 — What loan products are listed by Belgaum Industrial Co-operative Bank?

- Domain: **Competitive / Products**
- Expected source: `competitive`
- Status: **Answered**
- Actual sources: `competitive`
- Route match: **Yes**
- Latency: `21.48s`
- Cards: `brief`

#### Response

````text
The provided indexed passages do not list specific loan products offered by Belgaum Industrial Co-operative Bank. While the text confirms the bank's establishment in 1948, its conversion to an Urban Co-operative Bank in 1990, and its operational area in Belagavi district, it contains no details on its lending portfolio.

In contrast, other institutions in the region have defined offerings. For instance, Kaujalgi Urban Co-operative Bank offers Crop Loans, Home Loans, Personal Loans, Education Loans, MSME Loans, and Working Capital Loans [Kaujalgi Urban Co-operative Bank]. Similarly, Belagavi District Central Co-operative Bank provides Sugar Factory Loans, Gold Loans, Vehicle Loans, and various Working Capital and Term Loans for small-scale industries [Belagavi District Central Co-operative Bank]. Bhatkal Urban Co-operative Bank lists Boat Loans, Machinery Loans, and Car Loan Schemes [Bhatkal Urban Co-operative Bank].

**Gap:** Specific loan product names and terms for Belgaum Industrial Co-operative Bank are absent from the supplied evidence.
````

#### Citations

- Belgaum Industrial Co-operative Bank
- Kaujalgi Urban Co-operative Bank
- Bhatkal Urban Co-operative Bank

---

### Q076 — What products does Bellary Urban Co-operative Bank promote?

- Domain: **Competitive / Products**
- Expected source: `competitive`
- Status: **Answered**
- Actual sources: `competitive`
- Route match: **Yes**
- Latency: `19.16s`
- Cards: `brief`

#### Response

````text
Bellary Urban Co-operative Bank promotes Savings Accounts, Current Accounts, Deposits, Safe Deposit Lockers, Personal Loans, Home/Car Loans, and Two-wheeler Loans. It also offers net banking and fund transfers. Specific interest rates are partially listed, showing 03.00% on Savings Deposits, with Term Deposit rates absent in the provided text.

Unlike Bellary, other institutions like Kaujalgi Urban Co-operative Bank emphasize digital partnerships (200+ platforms) and mobile banking, while Belgaum Industrial Co-operative Bank highlights specific loan-to-deposit ratios (75% for vehicles, 85% for term deposits) and gold loans up to ₹1 lakh. The Karnataka State Co-operative Apex Bank focuses on agricultural marketing and infrastructure loans rather than retail consumer products.

[Bellary Urban Co-operative Bank]
[Bellary Urban Co-operative Bank]
````

#### Citations

- Bellary Urban Co-operative Bank
- Kaujalgi Urban Co-operative Bank
- National Co-operative Bank

---

### Q077 — What loan facilities are documented for Bhatkal Urban Co-operative Bank?

- Domain: **Competitive / Products**
- Expected source: `competitive`
- Status: **Refused**
- Actual sources: `none`
- Route match: **No**
- Latency: `4.28s`
- Cards: `none`

#### Response

````text
I do not have access to external information about specific third-party banks like Bhatkal Urban Co-operative Bank. My sources cover our own bank's data, general macro trends, competitive landscape, regulations, and educational concepts.
````

---

### Q078 — What lending services are described for Karnataka State Co-operative Apex Bank?

- Domain: **Competitive / Products**
- Expected source: `competitive`
- Status: **Answered**
- Actual sources: `knowledge`
- Route match: **No**
- Latency: `7.68s`
- Cards: `brief`

#### Response

````text
The provided catalog context does not describe any specific lending services offered by the Karnataka State Co-operative Apex Bank. Instead, it defines general banking metrics such as collection efficiency and account states like ACTIVE or NPA. Consequently, no details about the bank's particular loan products or services can be derived from this text.
````

---

### Q079 — What products are documented for Kaujalgi Urban Co-operative Bank?

- Domain: **Competitive / Products**
- Expected source: `competitive`
- Status: **Answered**
- Actual sources: `competitive`
- Route match: **Yes**
- Latency: `19.04s`
- Cards: `brief`

#### Response

````text
The provided indexed passages do not document specific loan products for Kaujalgi Urban Co-operative Bank. While the bank's website lists categories like "Products" and mentions "Quick approval for your immediate financial needs with minimal documentation" [Kaujalgi Urban Co-operative Bank], it does not enumerate specific loan types (e.g., home, business, or personal loans) or provide details on interest rates, ticket sizes, or eligibility criteria. In contrast, other institutions like Bhatkal Urban Co-operative Bank explicitly list products such as Boat Loans, Machinery Loans, and BUCB Car Loan Scheme [Bhatkal Urban Co-operative Bank], and Belagavi District Central Co-operative Bank details Sugar Factory Loans and Term Loans [Belagavi District Central Co-operative Bank]. The gap in specific product documentation for Kaujalgi prevents a direct comparison of their loan portfolios.
````

#### Citations

- Kaujalgi Urban Co-operative Bank
- Belagavi District Central Co-operative Bank
- Karnataka State Co-operative Apex Bank
- South Canara District Central Co-operative Bank

---

### Q080 — What loan offerings are indexed for National Co-operative Bank?

- Domain: **Competitive / Products**
- Expected source: `competitive`
- Status: **Partial**
- Actual sources: `competitive`
- Route match: **Yes**
- Latency: `21.72s`
- Cards: `brief`

#### Response

````text
The indexed evidence does not contain specific loan offerings for the National Co-operative Bank of Property; it only lists the product name under "Loan against Mortgage of Property" without detailing terms or rates. In contrast, the Belgaum Industrial Co-operative Bank offers Pledge Loans against Deposit Receipts up to 85% of the deposit amount, with a mandatory PAN card for deposits of Rs. 50,000 or more. The Belgaum Industrial Co-operative Bank also provides Recurring Deposits with tenures from 12 to 120 months and a minimum core deposit of Rs. 100. The National Co-operative Bank does offer a Shop Keeper's Loan for small business entrepreneurs with at least two years of experience, but specific interest rates or ticket sizes are not provided in the text. The Karnataka State Co-operative Apex Bank focuses on refinance policies for agricultural marketing rather than direct retail loan products. No direct comparison of specific loan terms between the National Co-operative Bank and other institutions is possible due to missing data in the provided passages.
````

#### Citations

- National Co-operative Bank
- South Canara District Central Co-operative Bank
- Karnataka State Co-operative Apex Bank

---

### Q081 — What lending products are described for South Canara DCCB?

- Domain: **Competitive / Products**
- Expected source: `competitive`
- Status: **Partial**
- Actual sources: `competitive`
- Route match: **Yes**
- Latency: `16.68s`
- Cards: `brief`

#### Response

````text
South Canara District Central Co-operative Bank offers business loans for working capital, block capital, and expansion, with funds disbursed directly to suppliers for plant and machinery after margin collection [South Canara District Central Co-operative Bank]. It also provides agricultural land purchase loans and various deposit-linked loans.

Belagavi District Central Co-operative Bank lists similar categories including Crop, SHG, Sugar Factory, and Petty Business loans, with specific interest rates for sectors like Sugar Factories (11.5%) and Consumer Groups (12%) [Belagavi District Central Co-operative Bank]. Belagavi explicitly details policies limiting sugar factory lending to 50% of capital funds and mandates 15% free sale sugar stock for working capital pledges [Belagavi District Central Co-operative Bank].

While both institutions serve small entrepreneurs and agricultural needs, the provided text lacks specific interest rates, ticket sizes, or turnaround times for South Canara's business loans, creating a data gap for direct comparison on those specific terms.
````

#### Citations

- South Canara District Central Co-operative Bank
- Belagavi District Central Co-operative Bank

---

### Q082 — What interest-rate information is available for Belagavi DCCB loans?

- Domain: **Competitive / Pricing**
- Expected source: `competitive`
- Status: **Refused**
- Actual sources: `db`
- Route match: **No**
- Latency: `47.51s`
- Cards: `refusal`

#### Response

````text
I could not answer that safely from the available data.
````

---

### Q083 — What lending-rate evidence is indexed for Bellary Urban Co-operative Bank?

- Domain: **Competitive / Pricing**
- Expected source: `competitive`
- Status: **Answered**
- Actual sources: `competitive`
- Route match: **Yes**
- Latency: `16.38s`
- Cards: `brief`

#### Response

````text
No specific lending rates are indexed for Bellary Urban Co-operative Bank in the provided passages. The text confirms the bank offers Personal, Home, and Car loans but lists no interest rates or loan limits for these products [Bellary Urban Co-operative Bank]. While other institutions like Karnataka State Co-operative Apex Bank and Belgaum Industrial Co-operative Bank have indexed rates (e.g., 11.00% or 14%), these figures cannot be attributed to Bellary Urban Co-operative Bank based on the available evidence. The gap regarding Bellary's specific lending rates remains unsupported.
````

#### Citations

- Bellary Urban Co-operative Bank
- Karnataka State Co-operative Apex Bank
- Kaujalgi Urban Co-operative Bank

---

### Q084 — Compare available loan-pricing evidence across the indexed co-operative banks.

- Domain: **Competitive / Pricing**
- Expected source: `competitive`
- Status: **Partial**
- Actual sources: `db, competitive`
- Route match: **Yes**
- Latency: `47.43s`
- Cards: `brief, refusal`

#### Response

````text
No direct loan-pricing evidence (specific interest rates or fees) is available for Karnataka State Co-operative Apex Bank or Kaujalgi Urban Co-operative Bank in the indexed passages; only product lists and SWOT analyses exist.

In contrast, Belagavi District Central Co-operative Bank provides specific working capital rates: 11.5% for Sugar Factory loans, 12% for TAPCMC/Consumer Groups, 9% for Fertilizer loans, and 12.5% for Employment Co-op Societies [Belagavi District Central Co-operative Bank].

National Co-operative Bank offers a 0.25% p.a. concession on interest for women borrowers across Housing, Education, Gold, and Business loans [National Co-operative Bank].

Bhatkal Urban Co-operative Bank charges a 5% membership fee on unsecured loans up to Rs. 5.00L [Bhatkal Urban Co-operative Bank].

Bellary Urban Co-operative Bank and South Canara District Central Co-operative Bank lack explicit rate data in the provided text.

I could not answer that safely from the available data.
````

#### Citations

- Karnataka State Co-operative Apex Bank
- Kaujalgi Urban Co-operative Bank

---

### Q085 — Does the indexed evidence provide MSME pricing for Kinara Capital?

- Domain: **Competitive / Pricing**
- Expected source: `competitive`
- Status: **Answered**
- Actual sources: `competitive`
- Route match: **Yes**
- Latency: `13.08s`
- Cards: `brief`

#### Response

````text
Kinara Capital offers MSME Short-Term Working Capital loans with interest rates starting at 24% per annum on a reducing balance basis [Kinara Capital]. The institution provides collateral-free loans, including the HerVikas Loan for women entrepreneurs, with minimal documentation and disbursement in as little as 24 hours [Kinara Capital]. Processing fees and additional charges are not explicitly detailed in the provided text; applicants are directed to the "Interest Rate and Charges Policy" page on the website for specifics [Kinara Capital]. Kinara Capital representatives explicitly state they will not ask for any commission or payment to process loan applications [Kinara Capital]. No direct comparison with other institutions is possible as no other lender data was supplied.
````

#### Citations

- Kinara Capital

---

### Q086 — What pricing gaps remain in the competitor evidence?

- Domain: **Competitive / Pricing**
- Expected source: `competitive`
- Status: **Partial**
- Actual sources: `competitive`
- Route match: **Yes**
- Latency: `14.74s`
- Cards: `brief`

#### Response

````text
The provided indexed evidence does not contain specific pricing data, interest rates, or fee structures for any institution, making it impossible to identify quantitative pricing gaps. All passages for Karnataka State Co-operative Apex Bank, Kaujalgi Urban Co-operative Bank, and others only note that "product rates, fees, and eligibility rules can change" and require manual verification [Kaujalgi Urban Co-operative Bank]. While threats mention competitors competing on "clearer pricing," no comparative figures exist [Karnataka State Co-operative Apex Bank]. Consequently, a direct comparison of pricing between institutions is unsupported by the current text. The evidence suggests a gap in the availability of static pricing data within the crawled sources, necessitating a refresh of product pages or annual reports to enable benchmarking [Belagavi District Central Co-operative Bank].
````

#### Citations

- Karnataka State Co-operative Apex Bank
- Kaujalgi Urban Co-operative Bank
- Kinara Capital
- SIDBI

---

### Q087 — What branch information is available for Bhatkal Urban Co-operative Bank?

- Domain: **Competitive / Distribution**
- Expected source: `competitive`
- Status: **Refused**
- Actual sources: `db`
- Route match: **No**
- Latency: `28.87s`
- Cards: `refusal`

#### Response

````text
No records matched that question in the available data.
````

---

### Q088 — What does the evidence say about South Canara DCCB's reach?

- Domain: **Competitive / Distribution**
- Expected source: `competitive`
- Status: **Partial**
- Actual sources: `competitive`
- Route match: **Yes**
- Latency: `15.98s`
- Cards: `brief`

#### Response

````text
The provided indexed passages do not contain specific data on market reach (e.g., total branch count, geographic coverage area) or explicit positioning statements for either the Belagavi District Central Co-operative Bank (BDCC) or the South Canara District Central Co-operative Bank (SCDCB).

While BDCC highlights its historical presence since 1919 and specific disbursement figures for farmers and sugar factories, it lacks a defined market reach metric [Belagavi District Central Co-operative Bank]. Similarly, SCDCB lists extensive product categories like agriculture, solar, and vehicle loans, but does not quantify its market footprint or state its strategic positioning relative to competitors [South Canara District Central Co-operative Bank].

Therefore, a direct comparison of market reach and positioning cannot be made with the supplied evidence. The gap lies in the absence of quantitative reach metrics and qualitative positioning narratives in the text.
````

#### Citations

- Belagavi District Central Co-operative Bank
- South Canara District Central Co-operative Bank

---

### Q089 — Compare the documented distribution presence of the indexed lenders.

- Domain: **Competitive / Distribution**
- Expected source: `competitive`
- Status: **Answered**
- Actual sources: `competitive`
- Route match: **Yes**
- Latency: `22.11s`
- Cards: `brief`

#### Response

````text
Documented distribution presence varies significantly among indexed lenders. Cooperative banks like **Bellary**, **Bhatkal**, **Belgaum**, and **Kaujalgi** explicitly highlight "Local, branch, co-operative, or rural presence" as a strength supporting relationship-led distribution [Bellary Urban Co-operative Bank]. Similarly, **Karnataka State Co-operative Apex Bank** notes its "Local branch or district presence" aids acquisition [Karnataka State Co-operative Apex Bank].

In contrast, **Karnataka State Financial Corporation** mentions contacting "nearest Branch Offices" but lacks specific branch counts or geographic scope details in the provided text [Karnataka State Financial Corporation]. **Kinara Capital** details aggressive expansion, citing growth from "1st Branch" to "133rd Branch" across multiple states, though it is an NBFC, not a cooperative lender [Kinara Capital]. **SIDBI** lists schemes and documents but offers no specific branch network data [SIDBI].

**Gap:** No indexed passage provides specific branch counts, city lists, or exact geographic footprints for the cooperative banks, preventing a quantitative comparison of their physical distribution networks.
````

#### Citations

- Karnataka State Co-operative Apex Bank
- Karnataka State Financial Corporation
- Bellary Urban Co-operative Bank
- Kinara Capital
- Kaujalgi Urban Co-operative Bank

---

### Q090 — Which indexed competitors appear strongest outside Bengaluru?

- Domain: **Competitive / Distribution**
- Expected source: `competitive`
- Status: **Answered**
- Actual sources: `competitive`
- Route match: **Yes**
- Latency: `19.97s`
- Cards: `brief`

#### Response

````text
Competitor strength outside Bengaluru is defined by a mix of localized cooperative networks and expanding NBFCs. Local co-operatives like Bellary Urban, Belgaum Industrial, Bhatkal Urban, Kaujalgi Urban, and Belagavi District Central leverage "Local, branch, co-operative, or rural presence" to support relationship-led distribution [Bellary Urban Co-operative Bank]. Their primary threat is competition from banks, NBFCs, and fintech lenders [Karnataka State Financial Corporation].

Conversely, Kinara Capital demonstrates significant expansion beyond Karnataka, noting a "1st Branch Opens in Tamil Nadu" and "Foray into new states including Maharashtra, Andhra Pradesh, Telangana" [Kinara Capital]. While co-operatives dominate rural and district-level access, NBFCs like Kinara Capital and SIDBI compete on digital rails and faster approval processes [Kaujalgi Urban Co-operative Bank]. No specific market share or financial figures are provided in the evidence to quantify this strength directly.
````

#### Citations

- Bellary Urban Co-operative Bank
- Karnataka State Financial Corporation
- Kaujalgi Urban Co-operative Bank
- Karnataka State Co-operative Apex Bank
- Belgaum Industrial Co-operative Bank

---

### Q091 — Which competitor sources mention digital banking capabilities?

- Domain: **Competitive / Capabilities**
- Expected source: `competitive`
- Status: **Answered**
- Actual sources: `competitive`
- Route match: **Yes**
- Latency: `15.04s`
- Cards: `brief`

#### Response

````text
Multiple competitor sources, including Karnataka State Co-operative Apex Bank, Kaujalgi Urban Co-operative Bank, Belagavi District Central Co-operative Bank, and others, explicitly mention "Digital/payment-channel references" or "Digital/payment channels" as strengths indicating customer-service modernization and improved access [Karnataka State Co-operative Apex Bank]. These institutions highlight digital rails for faster applications and payments. However, none of the provided passages specify exact digital banking capabilities, such as mobile app features, UPI integration, or specific online loan processing workflows. The evidence confirms the *presence* of digital channels as a strategic focus but lacks granular details on their implementation or comparative performance metrics.
````

#### Citations

- Karnataka State Co-operative Apex Bank
- Kaujalgi Urban Co-operative Bank
- Karnataka State Financial Corporation
- Bellary Urban Co-operative Bank
- Belagavi District Central Co-operative Bank

---

### Q092 — What customer-service channels are documented across competitors?

- Domain: **Competitive / Capabilities**
- Expected source: `competitive`
- Status: **Answered**
- Actual sources: `competitive`
- Route match: **Yes**
- Latency: `16.60s`
- Cards: `brief`

#### Response

````text
The provided indexed passages do not list specific customer-service channels (e.g., phone numbers, email addresses, or chatbots) for any rival lender. While the text notes that "Digital/payment-channel references indicate customer-service modernization" for institutions like Kaujalgi Urban Co-operative Bank and Karnataka State Co-operative Apex Bank, it does not detail these channels [Kaujalgi Urban Co-operative Bank]. Similarly, Kinara Capital mentions an email address (help@kinaracapital.com) for concerns but lacks broader channel lists [Kinara Capital]. Other co-operative banks are described as having "Established official web presence" but specific service contact points are absent [Bhatkal Urban Co-operative Bank]. Consequently, a direct comparison of specific channels is not possible from the supplied evidence.
````

#### Citations

- Karnataka State Co-operative Apex Bank
- Kaujalgi Urban Co-operative Bank
- Kinara Capital
- Karnataka State Financial Corporation
- Bellary Urban Co-operative Bank

---

### Q093 — Which indexed banks describe agriculture-linked lending capabilities?

- Domain: **Competitive / Capabilities**
- Expected source: `competitive`
- Status: **Answered**
- Actual sources: `competitive`
- Route match: **Yes**
- Latency: `22.72s`
- Cards: `brief`

#### Response

````text
The **Karnataka State Co-operative Apex Bank** explicitly offers agriculture-linked lending, financing short-term loans for crop production and marketing, as well as medium-term loans for agricultural infrastructure like lift irrigation and dairy [Karnataka State Co-operative Apex Bank] `new_corporate-banking_cma-of-nabard.md`. It also extends cash credit to agro-processing and sugar factories [Karnataka State Co-operative Apex Bank] `new_corporate-banking_cma-of-nabard.md`.

The **South Canara District Central Co-operative Bank** lists specific agriculture products including Crop Loan (S.A.O), Agriculture Loan, and Navodaya SHG Loans in its product suite [South Canara District Central Co-operative Bank] `new_retail-banking_deposit-schemes_current-account.md`.

Other indexed institutions—**Kaujalgi Urban Co-operative Bank**, **Belagavi District Central Co-operative Bank**, **Belgaum Industrial Co-operative Bank**, **Bhatkal Urban Co-operative Bank**, and **Karnataka State Financial Corporation**—are noted to have "Agriculture/rural product signals" that differentiate them from urban lenders, though specific product names or rates are not detailed in the provided text [Kaujalgi Urban Co-operative Bank] `rprises.`. No specific rates or ticket sizes are available for these institutions in the supplied evidence.
````

#### Citations

- Karnataka State Co-operative Apex Bank
- Kaujalgi Urban Co-operative Bank

---

### Q094 — What collateral-backed loan offerings appear across competitors?

- Domain: **Competitive / Capabilities**
- Expected source: `competitive`
- Status: **Answered**
- Actual sources: `competitive`
- Route match: **Yes**
- Latency: `18.73s`
- Cards: `brief`

#### Response

````text
Kinara Capital offers collateral-free business loans for MSMEs, including women entrepreneurs, with quick approvals and flexible repayment structures like EMIs and overdrafts [Kinara Capital]. In contrast, Karnataka State Co-operative Apex Bank requires security for loans above Rs. 10 lakhs, accepting land, gold, or third-party guarantees, and mandates joint liability with parents/guardians for smaller amounts [Karnataka State Co-operative Apex Bank]. While Kinara emphasizes digital onboarding and unsecured options, cooperative banks like Bellary Urban and Kaujalgi Urban Co-operative Bank rely on local branch presence for relationship-led distribution but lack explicit collateral details in public text [Bellary Urban Co-operative Bank], [Kaujalgi Urban Co-operative Bank]. Most cooperatives face threats from fintechs competing on faster approval and clearer pricing [Karnataka State Co-operative Apex Bank]. Specific interest rates and processing times for cooperatives are absent in the provided text.
````

#### Citations

- Kinara Capital
- Karnataka State Co-operative Apex Bank

---

### Q095 — How does SIDBI position itself as an MSME finance benchmark?

- Domain: **Competitive / Benchmark**
- Expected source: `competitive`
- Status: **Answered**
- Actual sources: `competitive`
- Route match: **Yes**
- Latency: `12.90s`
- Cards: `brief`

#### Response

````text
SIDBI positions itself as the definitive benchmark for the MSME ecosystem rather than a direct peer to local co-operative lenders. Its mandate, established by the Government of India, focuses on empowering women entrepreneurs and accelerating enterprise growth through specific schemes like CGTMSE and SMERA (now Acuité) [SIDBI]. The institution leverages platforms such as Udyam Assist and publishes regular insights via the "Small Business Spotlight" series to track sector progress [SIDBI]. Unlike regional banks, SIDBI operates with a defined hierarchy focused on single organizational objectives to ensure effective decision-making [SIDBI]. The provided evidence explicitly advises treating SIDBI as an ecosystem benchmark for product-gap analysis, distinguishing its national strategic role from local lending peers [SIDBI]. No specific interest rates, ticket sizes, or market share figures are available in the supplied text to quantify its competitive standing against other lenders.
````

#### Citations

- SIDBI

---

### Q096 — What differentiates Kinara Capital from co-operative-bank competitors?

- Domain: **Competitive / Benchmark**
- Expected source: `competitive`
- Status: **Answered**
- Actual sources: `competitive`
- Route match: **Yes**
- Latency: `21.50s`
- Cards: `brief`

#### Response

````text
Kinara Capital is a fintech NBFC founded in 2011 by Hardika Shah, focusing on MSME financial inclusion with business loans up to Rs. 30 lakhs [Kinara Capital]. Unlike Karnataka co-operative banks like Kaujalgi Urban Co-operative Bank, which serve specific districts (e.g., Belagavi) and emphasize local community initiatives and partnerships with 1,500+ local businesses [Kaujalgi Urban Co-operative Bank], Kinara operates as a registered brand of Kinara Capital Private Limited with a national mission [Kinara Capital]. While co-operative banks like the Karnataka State Co-operative Apex Bank focus on consortium arrangements for sugar factories and agro-processing [Karnataka State Co-operative Apex Bank], Kinara utilizes a co-lending model with banks and NBFCs to reach underserved sectors [Kinara Capital]. Specific rates, ticket sizes beyond Kinara's Rs. 30 lakh limit, or exact turnaround times for co-operative competitors are not provided in the supplied text.
````

#### Citations

- Kinara Capital
- Karnataka State Co-operative Apex Bank
- Kaujalgi Urban Co-operative Bank

---

### Q097 — What do the indexed RBI digital-lending directions require?

- Domain: **Regulatory / Digital Lending**
- Expected source: `regulatory`
- Status: **Answered**
- Actual sources: `regulatory`
- Route match: **Yes**
- Latency: `28.56s`
- Cards: `brief`

#### Response

````text
Based on the provided evidence, the requirements for **indexed** RBI digital-lending directions are not explicitly detailed in the text. The document outlines general operational mandates for Regulated Entities (REs) and Lending Service Providers (LSPs), such as obtaining explicit consent before sharing personal information, conducting enhanced due diligence before agreements, ensuring unbiased content display on Digital Lending Apps (DLAs), prohibiting automatic credit limit increases without explicit borrower request, providing a penalty-free exit option during a "cooling-off period," and limiting Default Loss Guarantee (DLG) cover to 5% of the total disbursed amount.

However, the specific term "indexed" does not appear in the provided passages, nor are there explicit rules detailing an indexing mechanism for these directions. While the text mentions that the **Effective date** is "As specified in the RBI digital lending directions," the specific date is not provided in the evidence.

Therefore, **entity-specific applicability must be confirmed** to determine if specific entities fall under the scope of any potential "indexed" provisions or to verify the exact effective date, as the provided text only confirms the general applicability to RBI-regulated entities and lending service arrangements without listing specific indexed thresholds or dates.

**Citations:**
*   (Digital Lending.pdf, p.1)
````

#### Citations

- Digital Lending.pdf

---

### Q098 — What obligations apply when a lender uses a lending service provider?

- Domain: **Regulatory / Digital Lending**
- Expected source: `regulatory`
- Status: **Answered**
- Actual sources: `regulatory`
- Route match: **Yes**
- Latency: `34.71s`
- Cards: `brief`

#### Response

````text
Based on the provided RBI Master Direction on Outsourcing of Information Technology Services (2023), the obligations for a lending service provider (acting as a Regulated Entity or RE) and its vendors are structured as follows:

**1. Explicit Rules for Service Providers (Contractual Obligations)**
The regulations explicitly mandate specific contractual clauses that the Regulated Entity (RE) must enforce with the service provider. These are not merely principles but binding requirements:
*   **Liability for Sub-contractors:** The contract must include clauses making the service provider "contractually liable for the performance and risk management practices of its sub-contractors" (outsourcing.pdf, p.17, clause 13p).
*   **Compliance with RBI Directions:** The service provider is obligated to "comply with directions issued by the RBI in relation to the activities outsourced," enforceable through specific contractual terms (outsourcing.pdf, p.17, clause 13q).
*   **Sub-contractor Approval:** Clauses must require "prior approval/ consent of the RE for use of sub-contractors by the service provider for all or part of an outsourced activity" (outsourcing.pdf, p.17, clause 13r).
*   **Inspection and Access:** Contracts must allow the RBI or authorized persons to access the RE's IT infrastructure, data, and documents stored or processed by the service provider or its sub-contractors (outsourcing.pdf, p.17, clause 13o).
*   **Insolvency Cooperation:** The service provider must have an obligation to "co-operate with the relevant authorities in case of insolvency/ resolution of the RE" (outsourcing.pdf, p.17, clause 13t).

**2. Related Principles for the Regulated Entity (RE)**
While the rules above bind the vendor, the underlying principles governing the RE's relationship with the vendor include:
*   **Ultimate Responsibility:** Outsourcing does not diminish the RE's obligations; the Board and Senior Management remain "ultimately responsible for the outsourced activity" (outsourcing.pdf, p.9, clause 4a).
*   **Standard of Care:** The RE must ensure the service provider employs the "same high standard of care" as if the activity were performed internally (outsourcing.pdf, p.9, clause 4a).
*   **Supervisory Non-Interference:** The arrangement must not impede the RBI's ability to carry out supervisory functions (outsourcing.pdf, p.9, clause 4b).

**3. Applicability and Threshold Confirmation**
````

#### Citations

- outsourcing.pdf

---

### Q099 — What does RBI require for digital-loan disclosures to borrowers?

- Domain: **Regulatory / Digital Lending**
- Expected source: `regulatory`
- Status: **Answered**
- Actual sources: `regulatory`
- Route match: **Yes**
- Latency: `31.33s`
- Cards: `brief`

#### Response

````text
Based on the provided regulatory passages, the explicit requirements for digital-loan disclosures and borrower protections are as follows:

**1. Consent and Data Sharing**
*   **Explicit Rule:** Explicit consent of the borrower must be obtained before sharing their personal information with any third party.
*   **Citation:** (Digital Lending.pdf, p.1)

**2. Transparency of Loan Offers**
*   **Explicit Rule:** The Lending Service Provider (LSP) must provide a digital view of all loan offers matching the borrower's request on Digital Lending Apps (DLAs).
*   **Explicit Rule:** The content displayed by the LSP must be unbiased and objective; it shall not directly or indirectly promote or push a product of a particular Regulated Entity (RE).
*   **Citation:** (Digital Lending.pdf, p.1)

**3. Credit Limit Increases**
*   **Explicit Rule:** There must be no automatic increase in the credit limit unless an explicit request is received, evaluated, and kept on record from the borrower.
*   **Citation:** (Digital Lending.pdf, p.1)

**4. Exit Mechanism and Cooling-Off Period**
*   **Explicit Rule:** Borrowers must be given the option to exit a digital loan by paying the principal and the proportionate Annual Percentage Rate (APR) without any penalty during an initial "cooling-off period."
*   **Citation:** (Digital Lending.pdf, p.1)

**5. Privacy and Data Protection**
*   **Explicit Rule:** The RE and LSP must have a comprehensive privacy policy compliant with applicable laws.
*   **Explicit Rule:** Biometric data should not be stored or collected by the RE and LSP.
*   **Citation:** (Digital Lending.pdf, p.1)

**6. Default Loss Guarantee (DLG) Disclosure**
*   **Explicit Rule:** The RE must ensure that the total amount of Default Loss Guarantee (DLG) cover on any outstanding portfolio is specified upfront and shall not exceed 5% of the total amount disbursed out of that loan portfolio at any given time.
*   **Citation:** (Digital Lending.pdf, p.1)

**Applicability Note:**
These rules apply to RBI-regulated entities (REs) and their arrangements with Lending Service Providers (LSPs), including NBFC digital lending operations where applicable. While the text specifies that REs must conduct enhanced due diligence before entering agreements with LSPs, the specific applicability of these directions to a particular entity or lending service arrangement must be confirmed against
````

#### Citations

- Digital Lending.pdf

---

### Q100 — What controls apply to digital collection and use of borrower data?

- Domain: **Regulatory / Digital Lending**
- Expected source: `regulatory`
- Status: **Answered**
- Actual sources: `regulatory`
- Route match: **Yes**
- Latency: `19.15s`
- Cards: `brief`

#### Response

````text
Based on the provided regulatory passages, the following controls apply to the digital collection and use of borrower data:

*   **Explicit Consent for Third-Party Sharing:** Before sharing personal information with any third party, the explicit consent of the borrower must be obtained (Digital Lending.pdf, p.1).
*   **Prohibition on Biometric Data:** Neither the Regulated Entity (RE) nor the Lending Service Provider (LSP) is permitted to store or collect biometric data (Digital Lending.pdf, p.1).
*   **Privacy Policy Requirement:** Both the RE and the LSP engaged by the RE must maintain a comprehensive privacy policy that complies with applicable laws (Digital Lending.pdf, p.1).
*   **Unbiased Data Display:** The content displayed by the LSP regarding loan offers must be unbiased and objective, ensuring it does not directly or indirectly promote a specific product of a particular RE (Digital Lending.pdf, p.1).

**Applicability Note:**
These rules apply to RBI-regulated entities and lending service arrangements, including NBFC digital lending operations where applicable. While the text specifies that Regulated Entities (REs) must conduct enhanced due diligence before entering agreements with Lending Service Providers (LSPs), the specific applicability of these digital lending directions to a particular entity or arrangement must be confirmed against the full RBI Digital Lending Directions, 2025, as the provided excerpt does not list every specific entity type covered.
````

#### Citations

- Digital Lending.pdf

---

### Q101 — What does the Fair Practices Code require in loan communication?

- Domain: **Regulatory / Fair Practices**
- Expected source: `regulatory`
- Status: **Answered**
- Actual sources: `regulatory`
- Route match: **Yes**
- Latency: `33.38s`
- Cards: `brief`

#### Response

````text
Based on the provided Fair Practices Code passages, the requirements for loan communication by NBFCs are as follows:

**1. Language of Communication**
*   **Explicit Rule:** All communications to the borrower must be in the vernacular language or a language as understood by the borrower (p.46). This applies to loan application forms, acknowledgement letters, sanction letters, and the Fair Practices Code itself (p.46, p.52).
*   **Related Principle:** The spirit of the guidelines requires that borrowers are not misled and can make informed decisions; therefore, communication must be clear and understandable to the specific borrower (p.46, p.52).

**2. Content and Clarity of Loan Application and Sanction**
*   **Explicit Rule:** Loan application forms must include necessary information affecting the borrower's interest to enable meaningful comparison with other NBFCs and indicate required documents (p.46).
*   **Explicit Rule:** NBFCs must convey the sanctioned amount, terms, conditions, annualised rate of interest, and the method of application in writing (sanction letter) in the borrower's understood language. Crucially, penalties for late repayment must be mentioned in **bold** in the loan agreement (p.46).
*   **Explicit Rule:** A system of acknowledgement for receipt of all loan applications must be devised, preferably indicating the time frame for disposal (p.46).

**3. Conduct of Agents (DSAs, DMAs, Recovery Agents)**
*   **Explicit Rule:** Agents must be trained to convey correct terms and conditions and adhere to a Board-approved Code of Conduct (p.269).
*   **Explicit Rule:** Agents must refrain from intimidation, harassment, public humiliation, or intruding on privacy. Specifically, they must not call borrowers before **8:00 a.m.** or after **7:00 p.m.** (p.269).
*   **Explicit Rule:** Agents must not make false or misleading representations (p.269).

**4. Digital Lending Platforms and Outsourcing**
*   **Explicit Rule:** If digital lending platforms are used as agents, the NBFC must disclose the platform's name on its website, and the platform must disclose the NBFC's name to the customer upfront (p.60).
*   **Explicit Rule:** The sanction letter must be issued on the NBFC's letterhead immediately after sanction but before execution of the loan agreement (p.60).
*   **Explicit Rule:** The NBFC retains sole responsibility for compliance even when outsourcing activities (p.60).

**5
````

#### Citations

- Fair Practices Code.pdf

---

### Q102 — What fair-practice requirements apply during loan recovery?

- Domain: **Regulatory / Fair Practices**
- Expected source: `regulatory`
- Status: **Answered**
- Actual sources: `regulatory`
- Route match: **Yes**
- Latency: `33.78s`
- Cards: `brief`

#### Response

````text
Based on the provided regulatory passages, here are the fair-practice requirements during loan recovery for NBFCs:

**Explicit Rules on Recovery Conduct**
*   **Prohibition of Harassment:** NBFCs must not resort to undue harassment, which includes persistently bothering borrowers at odd hours, using muscle power, or engaging in rude behavior by staff (Fair Practices Code.pdf, p.51).
*   **Restrictions on Contact Times and Methods:** Recovery agents and staff are prohibited from making calls before 8:00 a.m. or after 7:00 p.m. They must also refrain from intimidation, physical harassment, public humiliation, intruding on the privacy of family members/friends, sending inappropriate messages, or making threatening/anonymous calls (Fair Practices Code.pdf, p.269).
*   **Staff Training:** NBFCs must ensure staff are adequately trained to deal with customers in an appropriate manner to prevent rude behavior (Fair Practices Code.pdf, p.51).
*   **Agent Conduct:** Recovery Agents must adhere to a Board-approved Code of Conduct, maintain strict customer confidentiality, and refrain from actions that damage the NBFC's integrity or reputation (Fair Practices Code.pdf, p.269).
*   **Communication Language:** All communications to the borrower regarding the loan must be in the vernacular language or a language understood by the borrower (Fair Practices Code.pdf, p.46).

**Related Principles and Obligations**
*   **Board Oversight:** The Board of Directors must lay down a grievance redressal mechanism where disputes are heard at the next higher level and conduct periodical reviews of Fair Practices Code compliance (Fair Practices Code.pdf, p.52).
*   **Transparency:** While not a direct "recovery" rule, the requirement to share quarterly statements detailing principal, interest, EMI, and APR ensures borrowers can track their debt status, supporting fair treatment (Fair Practices Code.pdf, p.51).

**Entity-Specific Applicability Confirmation**
*   **Microfinance Exception:** The specific time-restriction rule (no calls before 8:00 a.m. or after 7:00 p.m.) found in paragraph 5.7.3 **does not apply** to microfinance loans. For these loans, NBFCs must follow the Master Direction – Reserve Bank of India (Regulatory Framework for Microfinance Loans) Directions, 2022 (Fair Practices Code.pdf, p.269).
*   **Scope:** These guidelines explicitly apply to NBFCs having a customer interface (Fair Practices Code.pdf, p.46).
````

#### Citations

- Fair Practices Code.pdf

---

### Q103 — What grievance-redressal expectations are stated for lenders?

- Domain: **Regulatory / Fair Practices**
- Expected source: `regulatory`
- Status: **Answered**
- Actual sources: `regulatory`
- Route match: **Yes**
- Latency: `34.72s`
- Cards: `brief`

#### Response

````text
Based on the provided regulatory passages, the expectations for grievance redressal for lenders (specifically NBFCs) are as follows:

**1. Establishment of Machinery and Nodal Officer**
NBFCs must constitute a Grievance Redressal Machinery in accordance with the Reserve Bank's circular dated February 18, 2013, titled 'Guidelines on Fair Practices Code for NBFCs – Grievance Redressal Mechanism-Nodal Officer' (Fair Practices Code.pdf, p.271).

**2. Operational Display and Scope**
At the operational level, the name and contact details (telephone/mobile numbers and email address) of the Grievance Redressal Officer must be displayed prominently at branches or places where business is transacted. The machinery must deal with grievances regarding services provided by outsourced agencies (Fair Practices Code.pdf, p.271).

**3. Board-Level Responsibility and Escalation**
The Board of Directors is responsible for laying down the appropriate grievance redressal mechanism. This mechanism must ensure that all disputes arising from the decisions of the lending institution's functionaries are heard and disposed of at least at the next higher level (Fair Practices Code.pdf, p.52).

**4. Periodic Review and Reporting**
The Board must provide for a periodical review of the compliance of the Fair Practices Code and the functioning of the grievance redressal mechanism at various management levels. A consolidated report of these reviews must be submitted to the Board at regular intervals (Fair Practices Code.pdf, p.52).

**5. Compliance with Integrated Ombudsman Scheme**
NBFCs covered under the Reserve Bank – Integrated Ombudsman Scheme, 2021 (RB-IOS, 2021) must comply with the directions provided under that specific Scheme (Fair Practices Code.pdf, p.52).

**Distinction and Applicability Note:**
*   **Explicit Rule:** The requirement to constitute the machinery, display contact details, and ensure Board-level review is an explicit rule for NBFCs.
*   **Related Principle:** The prompt to "ensure that genuine grievances... are redressed promptly without involving delay" is a principle of conduct that underpins the explicit rule.
*   **Entity-Specific Applicability:** You must confirm whether the specific NBFC in question is covered under the **Reserve Bank – Integrated Ombudsman Scheme, 2021**, as this triggers additional compliance directions under that specific scheme (Fair Practices Code.pdf, p.52). Additionally, applicability depends on whether the entity is an NBFC,
````

#### Citations

- Fair Practices Code.pdf

---

### Q104 — How should changes in loan terms be communicated under the Fair Practices Code?

- Domain: **Regulatory / Fair Practices**
- Expected source: `regulatory`
- Status: **Answered**
- Actual sources: `knowledge`
- Route match: **No**
- Latency: `9.93s`
- Cards: `brief`

#### Response

````text
The provided catalog context contains only internal reporting metrics and does not include information regarding the Fair Practices Code or requirements for communicating loan term changes. Consequently, I cannot explain the communication protocols based on this specific text. For accurate guidance on regulatory communication standards, please consult the official Fair Practices Code documentation or relevant banking laws.
````

---

### Q105 — What customer due-diligence requirements are described in the KYC directions?

- Domain: **Regulatory / KYC AML**
- Expected source: `regulatory`
- Status: **Answered**
- Actual sources: `regulatory`
- Route match: **Yes**
- Latency: `33.79s`
- Cards: `brief`

#### Response

````text
Based on the provided RBI KYC Master Directions (2016), the following explicit rules and principles govern KYC due diligence for the specified NBFC activities:

**1. Explicit Rules for Due Diligence Triggers**
*   **High-Value Walk-in Transactions:** REs must conduct due diligence for non-account-based (walk-in) customers where the transaction amount equals or exceeds **₹50,000**, whether as a single transaction or connected series of transactions (p.14).
*   **Structuring Detection:** Due diligence is required when an RE has reason to believe a customer is intentionally structuring transactions to remain below the ₹50,000 threshold (p.14).
*   **Third-Party Product Sales:** Due diligence applies to agents selling third-party products, credit card dues, or reloading prepaid/travel cards if the value exceeds **₹50,000** (p.14).
*   **New Product/Technology Introduction:** Appropriate KYC procedures must be applied before introducing new products, services, or technologies (p.38).

**2. Explicit Rules for On-going Due Diligence and Monitoring**
*   **Transaction Consistency:** REs must undertake on-going due diligence to ensure transactions are consistent with the customer's known business, risk profile, and source of funds (p.25).
*   **Mandatory Monitoring Triggers:** Specific transactions must be monitored, including:
    *   Large/complex transactions (e.g., RTGS) or those with unusual patterns lacking economic rationale (p.25).
    *   Transactions exceeding prescribed thresholds for specific account categories (p.25).
    *   High account turnover inconsistent with the balance maintained (p.25).
    *   Deposit of third-party cheques followed by large cash withdrawals (p.25).
*   **Risk-Based Monitoring:** The extent of monitoring must align with the customer's risk category. High-risk accounts require intensified monitoring (p.25).
*   **Periodic Review:** A system for periodic review of risk categorization must be in place with a frequency of **at least once every six months** (p.25).
*   **MLM Monitoring:** Accounts of Multi-level Marketing (MLM) companies require close monitoring, with specific reporting obligations to the RBI if certain patterns (e.g., multiple small cash deposits, large cheque books) are observed (p.25).

**3. Principles and Related Obligations**
*   **Third-Party Reliance:** An RE may rely on third-party due diligence only if
````

#### Citations

- KYC AML.pdf

---

### Q106 — What does RBI require for periodic KYC updation?

- Domain: **Regulatory / KYC AML**
- Expected source: `regulatory`
- Status: **Answered**
- Actual sources: `regulatory`
- Route match: **Yes**
- Latency: `34.71s`
- Cards: `brief`

#### Response

````text
Based on the provided RBI Master Direction documents, here are the specific requirements for periodic KYC updation:

**1. Mandatory Frequency by Risk Category**
Periodic updation must be carried out at the following intervals:
*   **High Risk Customers:** At least once every **two years**.
*   **Medium Risk Customers:** At least once every **eight years**.
*   **Low Risk Customers:** At least once every **ten years**.
*(Source: KYC AML.pdf, p.25)*

**2. Procedures During Periodic Updation**
*   **General Requirement:** Regulated Entities (REs) must carry out Customer Due Diligence (CDD) as specified in Section 16 at the time of periodic updation.
*   **Low Risk Exception:** For low-risk customers where there is **no change** in status regarding identity and address, REs may obtain a **self-certification** instead of full CDD.
*   **Legal Entities:** For legal entities, REs must review the documents sought at account opening and obtain **fresh certified copies**.
*   **Migration:** During periodic updation, customers must be migrated to the current CDD standard.
*(Source: KYC AML.pdf, p.26)*

**3. Documentation and Acknowledgment**
*   REs must ensure KYC documents per extant Master Direction requirements are available with them.
*   REs must provide an **acknowledgment with the date** of having performed the KYC updation to the customer.
*(Source: KYC AML.pdf, p.26)*

**4. Validity and Transfer**
*   KYC verification done by one branch is valid for transfer to another branch of the same RE, provided the account is **not due for periodic updation**.
*(Source: KYC AML.pdf, p.21)*

**5. Data Upload to CKYCR**
*   REs must upload/update KYC data for accounts opened prior to the initial mandatory dates **at the time of periodic updation** (as specified in Section 38) or earlier when updated information is received.
*(Source: KYC AML.pdf, p.35)*

**Distinction: Explicit Rule vs. Related Principle**
*   **Explicit Rule:** The specific timelines (2, 8, and 10 years) and the requirement to obtain fresh certified copies for Legal Entities during updation are mandatory operational rules.
*   **Related Principle:** The provision allowing self-certification for low-risk customers with no change in status is a risk
````

#### Citations

- KYC AML.pdf

---

### Q107 — What AML monitoring and suspicious-transaction controls are required?

- Domain: **Regulatory / KYC AML**
- Expected source: `regulatory`
- Status: **Answered**
- Actual sources: `regulatory`
- Route match: **Yes**
- Latency: `33.79s`
- Cards: `brief`

#### Response

````text
Based on the provided RBI KYC Master Directions, the required AML monitoring and suspicious-transaction controls for an NBFC are as follows:

**1. Mandatory AML Software and Alerting**
The NBFC must possess AML software capable of capturing, generating, and analyzing alerts specifically for filing Cash Transaction Reports (CTR) and Suspicious Transaction Reports (STR) regarding third-party product transactions (including walk-in customers) (KYC AML.pdf, p.40). Furthermore, robust software must be deployed that throws alerts when transactions are inconsistent with the customer's risk categorization and updated profile (KYC AML.pdf, p.32).

**2. Scope of Monitoring**
On-going due diligence must ensure transactions are consistent with the customer's known business, risk profile, and source of funds (KYC AML.pdf, p.25). The NBFC must necessarily monitor:
*   Large and complex transactions (including RTGS), those with unusual patterns inconsistent with normal activity, and those lacking an apparent economic rationale or legitimate purpose.
*   Transactions exceeding prescribed thresholds for specific account categories.
*   High account turnover inconsistent with the maintained balance.
*   Deposits of third-party cheques/drafts followed by large cash withdrawals (KYC AML.pdf, p.25).

**3. Risk-Based Intensification**
The extent of monitoring must align with the customer's risk category. High-risk accounts require intensified monitoring (KYC AML.pdf, p.25). Additionally, accounts of marketing firms, particularly Multi-level Marketing (MLM) companies, must be closely monitored for specific red flags such as multiple small cash deposits across the country or large numbers of cheques with similar amounts/dates (KYC AML.pdf, p.25).

**4. Definition and Reporting of Suspicious Transactions**
A "suspicious transaction" includes any attempted or made transaction (cash or otherwise) that gives rise to reasonable suspicion of proceeds of an offence, unusual complexity, lack of economic rationale, or financing of terrorism (KYC AML.pdf, p.7). If a match with designated individuals/entities (e.g., UN sanctions lists) is beyond doubt, the NBFC must prevent transactions, inform authorities, and file an STR with FIU-IND (KYC AML.pdf, p.48).

**5. Confidentiality and Tipping-Off Prohibition**
STRs must be kept strictly confidential, and it is mandatory to ensure no tipping-off occurs to the customer at any level (KYC AML.pdf, p.32).

**Applicability Note:**
While the text explicitly outlines these
````

#### Citations

- KYC AML.pdf

---

### Q108 — What KYC recordkeeping obligations are supported by the indexed directions?

- Domain: **Regulatory / KYC AML**
- Expected source: `regulatory`
- Status: **Answered**
- Actual sources: `regulatory`
- Route match: **Yes**
- Latency: `34.31s`
- Cards: `brief`

#### Response

````text
Based on the provided RBI KYC Master Directions, the recordkeeping obligations under indexed directions are defined by the following explicit rules and principles:

**1. Explicit Rule: Mandatory Upload to CKYCR**
Regulated Entities (REs) are explicitly required to capture customer KYC records and upload them to the Central KYC Records Registry (CKYCR) within **10 days** of the commencement of an account-based relationship. This applies to both individuals and legal entities (LEs), with specific timelines for uploading historical data during periodic updation.
*   **Individuals:** Upload data for accounts opened on or after April 1, 2017 (with a grace period for SCBs until February 1, 2017).
*   **Legal Entities (LEs):** Upload data for accounts opened on or after April 1, 2021.
*   **Historical Data:** REs must upload/update KYC data for accounts opened prior to these dates at the time of periodic updation (as specified in Section 38) or earlier when updated information is received.
*   **Citation:** (KYC AML.pdf, p.34, para 56(b); p.35, paras 35(e)-(h))

**2. Explicit Rule: Confidentiality and Restrictions on Disclosure**
Information collected for account opening must be treated as confidential. It cannot be divulged for cross-selling or other purposes without the customer's express permission. Exceptions to this rule are limited to:
*   Compulsion of law.
*   Duty to the public.
*   Interest of the bank requiring disclosure.
*   Express or implied consent of the customer.
*   **Citation:** (KYC AML.pdf, p.34, para 56(b)-(d))

**3. Related Principle: Digital KYC Standards**
While not a strict "recordkeeping" rule in the archival sense, the directions establish a principle that the KYC process must be undertaken through an authenticated RE application. This application must ensure:
*   Capture of a live photograph (no printed/video images) with specific watermarks (CAF number, GPS, employee code, timestamp).
*   Verification of original OVDs (Original Verifiable Documents).
*   **Citation:** (KYC AML.pdf, p.43, Annex I)

**4. Entity-Specific Applicability Confirmation Required**
The provided text distinguishes between **SCBs** (Scheduled Commercial Banks) and **REs other than SCBs** (which includes NBFCs).
*   **SC
````

#### Citations

- KYC AML.pdf

---

### Q109 — What asset-classification rules are stated in the prudential norms?

- Domain: **Regulatory / Prudential**
- Expected source: `regulatory`
- Status: **Answered**
- Actual sources: `regulatory`
- Route match: **Yes**
- Latency: `34.19s`
- Cards: `brief`

#### Response

````text
Based on the provided regulatory passages, here are the specific rules regarding asset classification for NBFCs:

**1. General Restructuring and Classification Continuity**
*   **Explicit Rule:** While a restructuring proposal is under consideration by the Joint Lending Forum (JLF) or Credit Decision Review (CDR), the **usual asset classification norms must continue to apply**. The process of re-classification cannot stop merely because a restructuring proposal is pending.
*   **Source:** (Prudential Norms.pdf, p.168; p.208)

**2. Classification of Converted Instruments (Principal to Debt/Equity)**
*   **Explicit Rule:** If a part of the outstanding principal is converted into debt or equity instruments during restructuring, these new instruments must be classified in the **same asset classification category** in which the original restructured advance was classified.
*   **Movement Rule:** Any subsequent movement in the asset classification of these new instruments must be determined based on the subsequent classification of the original restructured advance.
*   **Source:** (Prudential Norms.pdf, p.174)

**3. Classification of Converted Unpaid Interest (FITL)**
*   **Explicit Rule:** A 'Funded Interest Term Loan' (FITL), debt, or equity instrument created by the conversion of unpaid interest shall be classified in the **same asset classification category** as the restructured advance from which it was derived.
*   **Source:** (Prudential Norms.pdf, p.174)

**4. Special Asset Classification Benefit (Historical Context)**
*   **Explicit Rule:** Previously, a special asset classification benefit was available for accounts undertaken for restructuring under specific guidelines, where the status as on the date of JLF formation determined the post-implementation status.
*   **Applicability Note:** This specific benefit was **withdrawn for all restructurings with effect from April 1, 2015**, with exceptions only for provisions related to changes in the Date of Commencement of Commercial Operations (DCCO) for infrastructure and non-infrastructure project loans.
*   **Source:** (Prudential Norms.pdf, p.208)

**5. Eligibility for Restructuring**
*   **Explicit Rule:** NBFCs may restructure accounts classified under the **'standard', 'substandard', and 'doubtful'** categories.
*   **Source:** (Prudential Norms.pdf, p.168)

**6. Valuation Norms for Converted Equity**
*   **Explicit Rule:** Equity shares
````

#### Citations

- Prudential Norms.pdf

---

### Q110 — What provisioning principles apply to non-performing assets?

- Domain: **Regulatory / Prudential**
- Expected source: `regulatory`
- Status: **Answered**
- Actual sources: `regulatory, knowledge`
- Route match: **Yes**
- Latency: `50.06s`
- Cards: `brief, brief`

#### Response

````text
Provisioning for Non-Performing Assets (NPAs) is the practice of setting aside funds from a bank's profits to cover potential losses from loans that borrowers are unlikely to repay. While specific calculation methods and reserve ratios vary by jurisdiction and bank policy, the core principle is to ensure the institution remains solvent despite credit defaults. This concept is distinct from capital adequacy, which measures a bank's overall financial strength against risk, whereas provisioning specifically targets expected losses on existing bad debts.

Based on the provided regulatory passages, the current RBI provisioning norms for NPAs for NBFCs are structured by asset category and entity type, with specific rules for standard assets and non-performing assets (NPAs).

**1. Standard Asset Provisioning**
The required provision for standard assets varies by NBFC classification:
*   **NBFC-BL (Non-Banking Financial Company - Non-Deposit Taking):** Must make a provision of **0.25 percent** of the outstanding. This provision is shown separately as 'Contingent Provisions against Standard Assets' and is not netted from gross advances (Prudential Norms.pdf, p.30).
*   **NBFC (General/Other than NBFC-UL):** Must make a provision of **0.40 percent** of the outstanding, also shown separately as 'Contingent Provisions against Standard Assets' (Prudential Norms.pdf, p.88).
*   **NBFC-MFIs (Microfinance Institutions):** Standard asset provisioning follows the instructions in paragraphs 16 and 88 of the Directions (Prudential Norms.pdf, p.119).

**2. NPA Provisioning Norms**
*   **General NPAs:** The text clarifies that income recognition and provisioning are separate aspects; the fact that income on an NPA has not been recognized is not a reason to avoid making provisions. Provisions must be made on the total outstanding balances, including the depreciated book value of leased assets (Prudential Norms.pdf, p.30).
*   **Renegotiated/Rescheduled Assets:** An asset renegotiated or rescheduled must be classified as sub-standard or remain in its prior category (doubtful/loss) and necessary provisions must be made until it is upgraded (Prudential Norms.pdf, p.30).
*   **NBFC-MFIs (Microfinance Loans):** Specific norms apply where the aggregate loan provision must be the higher of:
    *   1% of the outstanding loan portfolio; OR
    *   50% of aggregate loan instalments overdue for more than 90 days but less than 180 days; AND
    *   100% of aggregate loan instalments overdue for 180 days or more (Prudential Norms.pdf, p.119).
*   **Guaranteed Portion:** If an advance covered by the Credit Risk Guarantee Fund Trust for Low Income Housing (CRGFTLIH) becomes non-performing, **no provision** is required for the guaranteed portion. Pro

Provisioning for non-performing assets (NPAs) requires setting aside funds from profits to cover potential losses, ensuring the institution remains solvent despite credit defaults. For general NPAs, provisions must be made on the total outstanding balances, including the depreciated book value of leased assets, and income recognition is a separate aspect from provisioning. Specific rules apply to renegotiated or rescheduled assets, which must be classified as sub-standard, doubtful, or loss with necessary provisions made until upgraded. For NBFC-MFIs, the aggregate loan provision must be the higher of 1% of the outstanding portfolio or specific percentages of overdue instalments (50% for 90–180 days and 100% for 180+ days), while no provision is required for the guaranteed portion of advances covered by the CRGFTLIH. The provided findings do not specify the exact percentage requirements for standard assets within the NPA category, only detailing them separately for standard assets.
````

#### Citations

- Prudential Norms.pdf

---

### Q111 — What capital requirements are described for NBFCs in the indexed material?

- Domain: **Regulatory / Prudential**
- Expected source: `regulatory`
- Status: **Refused**
- Actual sources: `none`
- Route match: **No**
- Latency: `3.69s`
- Cards: `none`

#### Response

````text
The indexed sources cover the bank's own lending warehouse, macroeconomic context, competitive landscape, and regulations applicable to the bank. They do not contain indexed material regarding NBFC capital requirements.
````

---

### Q112 — What exposure and concentration controls are described in the prudential norms?

- Domain: **Regulatory / Prudential**
- Expected source: `regulatory`
- Status: **Answered**
- Actual sources: `regulatory`
- Route match: **Yes**
- Latency: `34.71s`
- Cards: `brief`

#### Response

````text
Based on the provided regulatory passages, here are the specific rules and principles regarding exposure and concentration controls for NBFCs:

### 1. Explicit Regulatory Rules (Hard Limits)
The regulations establish specific quantitative ceilings for exposure to single parties and groups, which vary by NBFC classification:

*   **General NBFCs (excluding NBFC-IFC):**
    *   Exposure to a **single party** shall not exceed **25%** of Tier 1 capital.
    *   Exposure to a **single group of parties** shall not exceed **40%** of Tier 1 capital.
    *   *Exception:* An NBFC may exceed these limits by **5%** (for a single party) and **10%** (for a single group) if the additional exposure is due to infrastructure loans/investments.
    *   *(Source: Prudential Norms.pdf, p.91)*

*   **NBFC-IFC (Infrastructure Finance Companies):**
    *   Exposure to a **single party** shall not exceed **30%** of Tier 1 capital.
    *   Exposure to a **single group of parties** shall not exceed **50%** of Tier 1 capital.
    *   *(Source: Prudential Norms.pdf, p.91)*

*   **NBFCs held by NOFHC (Non-Operating Financial Holding Company):**
    *   Such NBFCs are prohibited from having any exposure to Promoters/Promoter Group entities or individuals associated with the Promoter Group/NOFHC.
    *   They are prohibited from investing in equity/debt capital instruments of financial entities under the NOFHC.
    *   They are prohibited from investing in equity instruments of other NOFHCs.
    *   *(Source: Prudential Norms.pdf, p.38)*

*   **Exemptions from Exposure Norms:**
    *   Norms do not apply to NBFCs not accessing public funds in India (directly/indirectly) and not issuing guarantees.
    *   Norms do not apply to investments in shares of subsidiaries or companies in the same group (to the extent reduced from Owned Funds for NOF calculation).
    *   Norms do not apply to the book value of debentures, bonds, outstanding loans, and deposits made to subsidiaries or companies in the same group (to the extent reduced from Owned Funds for NOF calculation).
    *   *(Source: Prudential Norms.pdf, p.91)*

### 2. Related Principles and Frameworks
*   **Large
````

#### Citations

- Prudential Norms.pdf

---

### Q113 — What board-oversight responsibilities are set out in the governance directions?

- Domain: **Regulatory / Governance**
- Expected source: `regulatory`
- Status: **Answered**
- Actual sources: `knowledge`
- Route match: **No**
- Latency: `7.68s`
- Cards: `brief`

#### Response

````text
The provided catalog context does not contain information regarding board-oversight responsibilities or governance directions. It only defines specific financial metrics: collection efficiency as a percentage of payments received versus due, and disbursement as the total sum of funds released in a period. Consequently, no details on governance duties can be derived from these definitions.
````

---

### Q114 — Which policies require board approval under the indexed governance material?

- Domain: **Regulatory / Governance**
- Expected source: `regulatory`
- Status: **Answered**
- Actual sources: `knowledge`
- Route match: **No**
- Latency: `7.48s`
- Cards: `brief`

#### Response

````text
The provided catalog context defines specific reporting metrics like collection efficiency and agent codes but does not contain any information regarding board approval policies or governance requirements. Consequently, it is impossible to identify which policies require board approval based solely on the text you supplied. You would need to consult the full indexed governance material or a separate policy document for those details.
````

---

### Q115 — What management-accountability expectations are described for NBFCs?

- Domain: **Regulatory / Governance**
- Expected source: `regulatory`
- Status: **Answered**
- Actual sources: `knowledge`
- Route match: **No**
- Latency: `9.20s`
- Cards: `brief`

#### Response

````text
The provided catalog context does not contain information regarding management-accountability expectations for NBFCs; it only defines a "Loan account" as the finest grain data point for tracking individual loans. Consequently, no specific units, calculations, or distinctions for NBFC accountability can be derived from this text. For details on NBFC governance, you would need to consult external regulatory sources or specific banking reports outside this limited scope.
````

---

### Q116 — What control-framework requirements appear in the governance directions?

- Domain: **Regulatory / Governance**
- Expected source: `regulatory`
- Status: **Answered**
- Actual sources: `knowledge`
- Route match: **No**
- Latency: `8.29s`
- Cards: `brief`

#### Response

````text
The provided catalog context does not contain any governance directions or control-framework requirements; it only defines "Collection efficiency" as a metric calculated by dividing total principal and interest paid by the total amount due. This specific term measures performance rather than outlining regulatory controls or governance mandates. Consequently, no control-framework requirements can be identified from the available text.
````

---

### Q117 — What due diligence is required before outsourcing a financial service?

- Domain: **Regulatory / Outsourcing**
- Expected source: `regulatory`
- Status: **Answered**
- Actual sources: `knowledge`
- Route match: **No**
- Latency: `9.21s`
- Cards: `brief`

#### Response

````text
The provided catalog context focuses on loan performance metrics like collection efficiency and days past due, rather than the regulatory due diligence steps for outsourcing financial services. Before outsourcing, institutions must verify the vendor's compliance licenses, security protocols, and data privacy adherence, which are distinct from the internal portfolio health indicators listed in your text. This process ensures the third party can safely handle sensitive financial data without compromising the bank's risk management standards.
````

---

### Q118 — What ongoing vendor-monitoring controls are required for outsourced services?

- Domain: **Regulatory / Outsourcing**
- Expected source: `regulatory`
- Status: **Answered**
- Actual sources: `knowledge`
- Route match: **No**
- Latency: `8.60s`
- Cards: `brief`

#### Response

````text
The provided catalog context defines collection efficiency as a metric for measuring loan repayment performance and does not contain information regarding vendor-monitoring controls for outsourced services. Consequently, I cannot specify the required ongoing controls or their calculation units based on the available text. For details on outsourcing compliance, you should consult relevant banking regulations or internal policy documents outside this context.
````

---

### Q119 — What exit-planning requirements apply to material outsourcing arrangements?

- Domain: **Regulatory / Outsourcing**
- Expected source: `regulatory`
- Status: **Answered**
- Actual sources: `regulatory`
- Route match: **Yes**
- Latency: `34.29s`
- Cards: `brief`

#### Response

````text
Based on the provided RBI outsourcing directions, here are the specific requirements for exit planning in material outsourcing arrangements:

**1. Mandatory Inclusion in Policy**
The RE's IT Outsourcing Policy must contain a clear exit strategy specifically for outsourced IT activities or IT-enabled services. This strategy must ensure business continuity both during and after the exit.
*   **Source:** (outsourcing.pdf p.11, para 9)

**2. Scenario-Based Planning and Timelines**
The exit strategy must address different scenarios of exit or termination. It must stipulate a **minimum period** required to execute such plans, as necessary.
*   **Source:** (outsourcing.pdf p.23, para 22a)

**3. Identification of Alternatives**
When documenting the exit strategy, the RE must identify alternative arrangements. These may include:
*   Performing the activity by a different service provider.
*   Performing the activity by the RE itself.
*   **Source:** (outsourcing.pdf p.23, para 22a)

**4. Data and Asset Security During Transition**
The agreement must include clauses ensuring the safe removal or destruction of data, hardware, and all records (digital and physical). Crucially, the service provider is legally obliged to cooperate fully with the RE and any new service provider(s) to ensure a smooth transition.
*   **Source:** (outsourcing.pdf p.23, para 22b)

**5. Prohibition on Data Alteration**
Unless specifically advised by the regulator or the concerned RE, the service provider is **prohibited** from erasing, purging, revoking, altering, or changing any data during the transition period.
*   **Source:** (outsourcing.pdf p.23, para 22b)

**6. Cross-Border Specifics**
For cross-border outsourcing, the RE must establish sound procedures for mitigating country risk, which explicitly includes having appropriate contingency and exit strategies. Furthermore, arrangements must ensure that the availability of records to the RE and the RBI is not affected even in the event of the service provider's liquidation.
*   **Source:** (outsourcing.pdf p.22, para 21a)

**Distinction: Explicit Rule vs. Related Principle**
*   **Explicit Rule:** The policy *must* contain a clear exit strategy with stipulated minimum execution periods and specific clauses on data preservation during transition (outsourcing.pdf p.23, para 22).
*   **Related Principle:** The overarching governance principle is that the RE must maintain an "arm's length relationship
````

#### Citations

- outsourcing.pdf

---

### Q120 — Which outsourced responsibilities remain with the regulated entity?

- Domain: **Regulatory / Outsourcing**
- Expected source: `regulatory`
- Status: **Answered**
- Actual sources: `knowledge`
- Route match: **No**
- Latency: `9.02s`
- Cards: `brief`

#### Response

````text
The provided catalog context does not contain information regarding outsourced responsibilities or which duties remain with a regulated entity. It only defines specific data metrics like collection efficiency, account states, and borrower gender attributes. Consequently, I cannot identify which responsibilities stay with the bank based on this text alone.
````

---

### Q121 — What information-security governance controls are required for NBFCs?

- Domain: **Regulatory / Information Security**
- Expected source: `regulatory`
- Status: **Answered**
- Actual sources: `knowledge`
- Route match: **No**
- Latency: `7.68s`
- Cards: `brief`

#### Response

````text
The provided catalog context defines "collection efficiency" as a financial performance metric and does not contain information regarding information-security governance controls for NBFCs. Consequently, I cannot define, calculate, or distinguish security requirements based on the available text. For accurate details on security governance, please consult official regulatory guidelines or banking compliance frameworks.
````

---

### Q122 — What cyber-incident handling obligations are described in the indexed directions?

- Domain: **Regulatory / Information Security**
- Expected source: `regulatory`
- Status: **Answered**
- Actual sources: `knowledge`
- Route match: **No**
- Latency: `7.57s`
- Cards: `brief`

#### Response

````text
The provided catalog context does not contain any information regarding cyber-incident handling obligations or banking regulations. Consequently, I cannot define this concept, state its units, or distinguish related terms based on the available stable lending and banking materials. For details on cyber-incident protocols, please consult specific regulatory documents or cybersecurity guidelines outside this scope.
````

---

### Q123 — What controls support digital operational resilience?

- Domain: **Regulatory / Information Security**
- Expected source: `regulatory`
- Status: **Answered**
- Actual sources: `knowledge`
- Route match: **No**
- Latency: `8.70s`
- Cards: `brief`

#### Response

````text
Digital operational resilience is supported by controls that ensure systems remain available and data remains accurate during disruptions, though the provided catalog context does not list specific resilience controls. The only metric defined in your context is collection efficiency, which measures repayment performance as a percentage and is unrelated to operational resilience. Do not confuse collection efficiency with resilience metrics, as one tracks financial recovery while the other tracks system stability.
````

---

### Q124 — What board responsibilities apply to cyber and information-security risk?

- Domain: **Regulatory / Information Security**
- Expected source: `regulatory`
- Status: **Answered**
- Actual sources: `knowledge`
- Route match: **No**
- Latency: `9.52s`
- Cards: `brief`

#### Response

````text
The provided catalog context regarding PAR 30 (Percent of Principal Outstanding over 30 Days Past Due) relates to credit risk metrics and does not contain information on board responsibilities for cyber and information-security risk. Board duties in this area typically involve overseeing the bank's overall risk appetite, approving cybersecurity strategies, and ensuring adequate resources are allocated to protect digital assets. These responsibilities are distinct from operational risk measures like PAR 30, which specifically quantifies the portion of classified loans that are delinquent.
````

---

### Q125 — What areas are covered by the indexed NBFC master directions?

- Domain: **Regulatory / Master Directions**
- Expected source: `regulatory`
- Status: **Answered**
- Actual sources: `competitive`
- Route match: **No**
- Latency: `13.72s`
- Cards: `brief`

#### Response

````text
The provided indexed passages do not list specific areas covered by the "NBFC master directions." While the text mentions regulatory bodies like the ACB (Audit Committee of the Board) and RBI, and references forms like Form A regarding auditor appointments, it does not detail the scope of the master directions themselves. The documents focus instead on Kinara Capital's ESG alignment, branch expansion, and grievance redressal mechanisms. Therefore, the specific areas covered by the indexed NBFC master directions cannot be identified from the supplied evidence.
````

#### Citations

- Kinara Capital

---

### Q126 — How should an institution determine which RBI master direction applies to it?

- Domain: **Regulatory / Master Directions**
- Expected source: `regulatory`
- Status: **Answered**
- Actual sources: `regulatory`
- Route match: **Yes**
- Latency: `35.11s`
- Cards: `brief`

#### Response

````text
Based on the provided **Master Direction – Reserve Bank of India (Non-Banking Financial Company – Scale Based Regulation) Directions, 2023**, the applicable regulatory framework for the institution is determined as follows:

**1. Primary Applicable Master Direction**
The institution must comply with the **Master Direction – Reserve Bank of India (Non-Banking Financial Company – Scale Based Regulation) Directions, 2023**.
*   **Explicit Rule:** This direction superseded the previous 2016 directions (for both Systemically Important and Non-Systemically Important NBFCs) and applies to every NBFC registered with the RBI under the RBI Act, 1934, as well as those registered under the Factoring Regulation Act, 2011 (NBFC-Factor and NBFC-ICC), NBFC-MFI, NBFC-IFC, and IDF-NBFC (Section 3.1; p.1, p.8).
*   **Scope:** It covers registration, scale-based regulation, prudential conduct, governance, and operating requirements (p.1).

**2. Applicability Confirmation Required**
Before applying the full scope of the 2023 Directions, the specific category of the institution must be confirmed to identify any exemptions or specific sub-regulations:
*   **Exemption Check:** If the institution is an **NBFC-BL** (Banking License) having a customer interface but **not availing public funds**, it is explicitly **exempt** from Chapter IV and Chapter V of the Directions (p.9).
*   **Category-Specific Rules:** If the institution falls under specific categories such as **NBFC-P2P**, **NBFC-AA**, **CIC**, or **SPD**, the 2023 Directions state that they are subject to their respective extant Master Directions (e.g., P2P Directions 2017, AA Directions 2016) in addition to the general provisions (p.9).
*   **Microfinance Loans:** If the institution deals with microfinance loans, it must adhere to the **Master Direction – Reserve Bank of India (Regulatory Framework for Microfinance Loans) Directions, 2022** (p.9, p.269).

**3. Consolidated Compliance Obligations**
Regardless of the specific category (unless exempted), the institution must ensure compliance with the following other Master Directions listed in Section 4.1 of the 2023 Directions:
*   Master Direction – Know Your Customer (KYC) Direction, 2016 (p.
````

#### Citations

- sbr_master_direction_2023.pdf

---

### Q127 — What registration requirements are described in the NBFC master directions?

- Domain: **Regulatory / Master Directions**
- Expected source: `regulatory`
- Status: **Answered**
- Actual sources: `competitive`
- Route match: **No**
- Latency: `13.52s`
- Cards: `brief`

#### Response

````text
The provided indexed passages do not describe the specific registration requirements outlined in the NBFC master directions. While the text mentions that an NBFC must be "registered with the Reserve Bank under Section 45-IA of the Reserve Bank of India Act, 1934" [Kinara Capital], it does not detail the procedural registration requirements mandated by the master directions themselves. The documents instead focus on Kinara Capital's internal compliance, such as informing the RBI Regional Office about Statutory Auditors via Form A [Kinara Capital] and obtaining auditor consent [Kinara Capital]. Consequently, the specific regulatory registration criteria from the master directions are absent from the supplied evidence.
````

#### Citations

- Kinara Capital

---

### Q128 — What scale-based regulatory obligations are supported by the indexed material?

- Domain: **Regulatory / Master Directions**
- Expected source: `regulatory`
- Status: **Refused**
- Actual sources: `none`
- Route match: **No**
- Latency: `4.60s`
- Cards: `none`

#### Response

````text
The question asks about 'indexed material' which is not a defined knowledge source in the bank intelligence workbench. The available sources cover the bank's internal data (db), external macro/competitive/regulatory intelligence (macro, competitive, regulatory), and general concepts (knowledge).
````

---

### Q129 — What is principal outstanding?

- Domain: **General Banking / Definitions**
- Expected source: `knowledge`
- Status: **Answered**
- Actual sources: `db`
- Route match: **No**
- Latency: `14.44s`
- Cards: `chart`

#### Response

````text
Principal outstanding was ₹204.54 Cr as at 26 Aug 2026. This measures principal outstanding from each classified account at the requested snapshot.
````

#### SQL

````sql
SELECT SUM(portfolio.principal_outstanding) AS principal_outstanding
FROM gold.portfolio_snapshot_as_of(DATE '2026-08-26') AS portfolio
LIMIT 200
````

---

### Q130 — What is the difference between sanctioned amount and disbursed amount?

- Domain: **General Banking / Definitions**
- Expected source: `knowledge`
- Status: **Error**
- Actual sources: `db`
- Route match: **No**
- Latency: `92.77s`
- Cards: `error`

#### Response

````text
The loan book could not answer that.
````

---

### Q131 — What is a loan account number?

- Domain: **General Banking / Definitions**
- Expected source: `knowledge`
- Status: **Answered**
- Actual sources: `db`
- Route match: **No**
- Latency: `55.91s`
- Cards: `chart`

#### Response

````text
The query returned 5,000 row(s) covering loan account number. List of unique loan account numbers from the governed master view. This uses a validated read-only generated query rather than a reviewed metric; check Source details before relying on it.
````

#### SQL

````sql
SELECT DISTINCT
  loan_account_number
FROM gold.loan_account_master
LIMIT 5000
````

---

### Q132 — What does loan maturity mean?

- Domain: **General Banking / Definitions**
- Expected source: `knowledge`
- Status: **Answered**
- Actual sources: `knowledge`
- Route match: **Yes**
- Latency: `14.43s`
- Cards: `brief`

#### Response

````text
Loan maturity refers to the specific date or duration by which a borrower must fully repay the principal and interest of a loan. It is typically expressed in time units such as months or years, defining the end of the lending agreement rather than the current amount owed. This concept is distinct from "principal outstanding," which measures the remaining balance at any given time, and "average ticket size," which calculates the mean value of individual loans.
````

---

### Q133 — What is an amortizing loan?

- Domain: **General Banking / Definitions**
- Expected source: `knowledge`
- Status: **Answered**
- Actual sources: `knowledge`
- Route match: **Yes**
- Latency: `8.60s`
- Cards: `brief`

#### Response

````text
An amortizing loan is a standard borrowing arrangement where each periodic payment includes both principal repayment and interest, gradually reducing the total debt until it reaches zero. Unlike interest-only loans, the outstanding balance decreases with every payment, making the principal portion of each installment grow over time while the interest portion shrinks. This concept is distinct from non-amortizing loans, which typically require a single lump-sum payment of the full principal at the end of the term.
````

---

### Q134 — What is a bullet-repayment loan?

- Domain: **General Banking / Definitions**
- Expected source: `knowledge`
- Status: **Answered**
- Actual sources: `knowledge`
- Route match: **Yes**
- Latency: `7.68s`
- Cards: `brief`

#### Response

````text
A bullet-repayment loan is a financing structure where the borrower makes regular interest-only payments during the term, with the entire principal amount due as a single lump sum at maturity. Unlike amortizing loans where principal is gradually reduced, this method keeps the outstanding balance constant until the final payment date. While the provided catalog tracks metrics like principal outstanding and average ticket size, it does not contain specific definitions or figures for this particular loan type.
````

---

### Q135 — What is a secured loan?

- Domain: **General Banking / Definitions**
- Expected source: `knowledge`
- Status: **Answered**
- Actual sources: `knowledge`
- Route match: **Yes**
- Latency: `8.29s`
- Cards: `brief`

#### Response

````text
A secured loan is a borrowing arrangement where the borrower pledges specific assets, such as property or vehicles, as collateral to guarantee repayment. Unlike unsecured loans which rely solely on creditworthiness, secured loans typically allow for larger amounts and lower interest rates because the lender has a claim on the collateral if the borrower defaults. While the provided catalog tracks metrics like "Principal outstanding" and "Average ticket size" for various loan products, it does not specify the interest rates or legal terms associated with secured versus unsecured lending.
````

---

### Q136 — What is an unsecured loan?

- Domain: **General Banking / Definitions**
- Expected source: `knowledge`
- Status: **Answered**
- Actual sources: `knowledge`
- Route match: **Yes**
- Latency: `8.91s`
- Cards: `brief`

#### Response

````text
An unsecured loan is a financial product provided without requiring collateral, meaning the lender relies solely on the borrower's creditworthiness rather than assets to secure repayment. Unlike secured loans, there is no specific unit or calculation within the provided catalog context that distinguishes unsecured loans from other types, as the data focuses on aggregate metrics like sanctioned counts and principal outstanding. This concept is often confused with secured loans, which require assets like property or vehicles as a guarantee for the debt.
````

---

### Q137 — What is an EMI and how is it calculated?

- Domain: **General Banking / Repayment**
- Expected source: `knowledge`
- Status: **Answered**
- Actual sources: `knowledge`
- Route match: **Yes**
- Latency: `7.53s`
- Cards: `brief`

#### Response

````text
An EMI (Equated Monthly Installment) is a fixed payment amount made by a borrower to a lender at a specified date each month to pay off a loan with interest. It is calculated based on the principal amount, the interest rate, and the loan tenure, ensuring the debt is fully repaid by the end of the term. This concept is distinct from a simple interest payment, which only covers the cost of borrowing without reducing the principal balance.
````

---

### Q138 — What is the difference between principal due and principal paid?

- Domain: **General Banking / Repayment**
- Expected source: `knowledge`
- Status: **Answered**
- Actual sources: `knowledge`
- Route match: **Yes**
- Latency: `8.13s`
- Cards: `brief`

#### Response

````text
Principal due represents the outstanding loan balance that remains unpaid at a specific snapshot in time, whereas principal paid refers to the actual portion of that balance the borrower has successfully repaid during a period. While "Amount due" includes both principal and interest, "principal due" isolates just the loan balance, and similarly, "Amount collected" covers both components while "principal paid" tracks only the reduction of the debt. These metrics are often confused with overdue principal, which specifically measures the unpaid balance that has missed its payment deadline.
````

---

### Q139 — What does repayment frequency mean?

- Domain: **General Banking / Repayment**
- Expected source: `knowledge`
- Status: **Answered**
- Actual sources: `knowledge`
- Route match: **Yes**
- Latency: `6.15s`
- Cards: `brief`

#### Response

````text
Repayment frequency refers to how often a borrower makes scheduled payments toward a loan, such as monthly, quarterly, or annually. While the provided catalog defines collection efficiency as a percentage measuring total payments made versus total due, repayment frequency is simply the time interval between these payments. It is distinct from collection efficiency, which tracks the success rate of collecting those payments rather than their timing.
````

---

### Q140 — What is a repayment schedule?

- Domain: **General Banking / Repayment**
- Expected source: `knowledge`
- Status: **Answered**
- Actual sources: `knowledge`
- Route match: **Yes**
- Latency: `7.97s`
- Cards: `brief`

#### Response

````text
A repayment schedule is a detailed timeline that lists when and how much money a borrower must pay back to a lender, typically broken down into regular installments. While the provided catalog context defines collection efficiency as a percentage of payments made versus due, a repayment schedule itself is not a calculated unit but rather the plan used to generate those payments. This concept is often confused with the loan term, which is the total duration of the loan, whereas the schedule specifies the exact dates and amounts for each payment within that term.
````

---

### Q141 — What is a collection shortfall?

- Domain: **General Banking / Repayment**
- Expected source: `knowledge`
- Status: **Answered**
- Actual sources: `knowledge`
- Route match: **Yes**
- Latency: `7.06s`
- Cards: `brief`

#### Response

````text
A collection shortfall is the difference between the total amount due (principal plus interest) and the actual amount paid within a specific period, measured in Indian Rupees (INR). It represents the unpaid balance that remains after collection efforts for that timeframe. This metric is distinct from collection efficiency, which is a percentage ratio, and collection activity amount, which tracks the total sum of final collections recorded.
````

---

### Q142 — How is collection efficiency calculated?

- Domain: **General Banking / Repayment**
- Expected source: `knowledge`
- Status: **Answered**
- Actual sources: `knowledge`
- Route match: **Yes**
- Latency: `6.15s`
- Cards: `brief`

#### Response

````text
Collection efficiency is calculated as a percentage by dividing the total principal and interest actually paid by the total principal and interest that was due. This metric measures how effectively a bank collects owed funds within a specific period. It is distinct from related terms like "collection shortfall," which represents the specific monetary gap between what was due and what was paid.
````

---

### Q143 — What is prepayment of a loan?

- Domain: **General Banking / Repayment**
- Expected source: `knowledge`
- Status: **Answered**
- Actual sources: `knowledge`
- Route match: **Yes**
- Latency: `8.28s`
- Cards: `brief`

#### Response

````text
Loan prepayment occurs when a borrower pays back part or all of their loan principal before the scheduled due date, reducing the total outstanding balance. This action directly lowers the "Principal outstanding" figure, which is calculated as the cumulative disbursed amount minus cumulative principal repaid across all loan accounts. It is distinct from regular scheduled repayments because it happens outside the agreed-upon amortization timeline, often affecting the bank's collection efficiency metrics.
````

---

### Q144 — What is loan foreclosure?

- Domain: **General Banking / Repayment**
- Expected source: `knowledge`
- Status: **Answered**
- Actual sources: `knowledge`
- Route match: **Yes**
- Latency: `7.37s`
- Cards: `brief`

#### Response

````text
Loan foreclosure is the process where a borrower pays off their entire loan balance before the scheduled maturity date, stopping all future interest charges. Unlike "collection efficiency," which measures the percentage of total payments received versus those due, foreclosure specifically refers to the early settlement of the principal and accrued interest. This action reduces the "principal outstanding" in a bank's books, distinguishing it from regular monthly repayments that only partially reduce the debt.
````

---

### Q145 — What does days past due mean?

- Domain: **General Banking / Risk**
- Expected source: `knowledge`
- Status: **Answered**
- Actual sources: `knowledge`
- Route match: **Yes**
- Latency: `6.75s`
- Cards: `brief`

#### Response

````text
Days past due (DPD) measures how many days a loan payment has been late, serving as the primary metric for tracking delinquency. This concept is often categorized into specific "DPD buckets" representing standard aging bands to classify account risk. It is distinct from "overdue principal," which refers only to the unpaid amount, whereas DPD specifically tracks the duration of the delay.
````

---

### Q146 — How are DPD buckets used in lending?

- Domain: **General Banking / Risk**
- Expected source: `knowledge`
- Status: **Answered**
- Actual sources: `knowledge`
- Route match: **Yes**
- Latency: `7.98s`
- Cards: `brief`

#### Response

````text
DPD buckets are standard aging bands used to categorize loans based on how many days they are past due, helping lenders track delinquency levels. Metrics like PAR 30 and PAR 60 calculate the percentage of principal outstanding within specific buckets (over 30 or 60 days) relative to the total classified principal. These buckets differ from simple delinquent account counts by providing a weighted view of exposure severity rather than just the number of affected accounts.
````

---

### Q147 — What is PAR 30 and how is it calculated?

- Domain: **General Banking / Risk**
- Expected source: `knowledge`
- Status: **Answered**
- Actual sources: `knowledge`
- Route match: **Yes**
- Latency: `8.29s`
- Cards: `brief`

#### Response

````text
PAR 30 is a banking metric that measures the percentage of classified loan principal outstanding for 30 days past due (DPD) relative to the total classified principal. It is calculated by dividing the principal amount overdue by 30 days by the total classified principal outstanding. This metric differs from PAR 60 or PAR 90, which track delinquency at 60 and 90 days respectively, and from the Vintage PAR 30 rate, which focuses on account counts rather than principal amounts.
````

---

### Q148 — What is the difference between PAR and NPA ratio?

- Domain: **General Banking / Risk**
- Expected source: `knowledge`
- Status: **Answered**
- Actual sources: `knowledge`
- Route match: **Yes**
- Latency: `8.29s`
- Cards: `brief`

#### Response

````text
The NPA ratio measures the total proportion of classified principal outstanding that is non-performing, while the PAR 30 and PAR 60 ratios specifically isolate the portions of that classified principal overdue by 30 or 60 days, respectively. All three metrics are expressed as percentages calculated by dividing specific subsets of overdue principal by the total classified principal outstanding. Although they all relate to loan performance, PAR ratios provide a more granular view of delinquency severity within the broader NPA category.
````

---

### Q149 — What do SMA-0, SMA-1 and SMA-2 mean?

- Domain: **General Banking / Risk**
- Expected source: `knowledge`
- Status: **Answered**
- Actual sources: `knowledge`
- Route match: **Yes**
- Latency: `8.60s`
- Cards: `brief`

#### Response

````text
SMA-0, SMA-1, and SMA-2 are not standard banking terms but appear to be a misinterpretation of RBI's Special Mention Account (SMA) categories used for asset classification. SMA-1 indicates a loan showing early warning signs of stress, while SMA-2 signifies a loan that has deteriorated further and is closer to becoming a non-performing asset. These classifications help banks monitor credit risk before assets are officially reclassified as NPA, distinct from the general asset classification snapshots provided by the RBI.
````

---

### Q150 — What is a non-performing asset?

- Domain: **General Banking / Risk**
- Expected source: `knowledge`
- Status: **Answered**
- Actual sources: `knowledge`
- Route match: **Yes**
- Latency: `8.29s`
- Cards: `brief`

#### Response

````text
A non-performing asset (NPA) is a loan or advance where the borrower has failed to make scheduled interest or principal payments for a specific period, causing the asset to be reclassified as risky. While the provided catalog defines the NPA ratio as the percentage of classified principal outstanding relative to the total classified portfolio, the term itself refers to the individual loan accounts within that classified snapshot. This concept is distinct from performing assets, which are loans being repaid according to schedule, and should not be confused with general asset quality metrics that include performing loans.
````

---

### Q151 — What is credit risk?

- Domain: **General Banking / Risk**
- Expected source: `knowledge`
- Status: **Answered**
- Actual sources: `knowledge`
- Route match: **Yes**
- Latency: `11.06s`
- Cards: `brief`

#### Response

````text
Credit risk is the potential for a borrower to fail to repay a loan as agreed, leading to financial loss for the lender. While the provided catalog defines metrics like PAR 30 (measuring overdue principal) and collection efficiency to assess this risk, the concept itself is distinct from these specific performance indicators. It differs from liquidity risk, which concerns a bank's ability to meet immediate obligations, rather than the probability of default on existing assets.
````

---

### Q152 — What is concentration risk in a loan portfolio?

- Domain: **General Banking / Risk**
- Expected source: `knowledge`
- Status: **Answered**
- Actual sources: `knowledge`
- Route match: **Yes**
- Latency: `7.51s`
- Cards: `brief`

#### Response

````text
Concentration risk is the potential for significant losses because a loan portfolio is overly exposed to a single borrower, industry, or geographic area. While the provided catalog defines metrics like PAR 30 and principal outstanding to measure overall portfolio health, it does not contain specific data or thresholds for calculating concentration limits. This concept is distinct from general credit risk, as it specifically addresses the danger of a localized shock affecting many loans simultaneously rather than isolated defaults.
````

---

### Q153 — What is a loan interest rate?

- Domain: **General Banking / Pricing**
- Expected source: `knowledge`
- Status: **Answered**
- Actual sources: `knowledge`
- Route match: **Yes**
- Latency: `6.40s`
- Cards: `brief`

#### Response

````text
A loan interest rate is the percentage cost charged by a lender for borrowing money, typically expressed as an annual figure. While related metrics like "average interest rate" calculate a weighted mean across all accounts, the specific rate applies to individual loan terms. This concept is distinct from "collection efficiency," which measures repayment performance rather than the cost of credit.
````

---

### Q154 — What is the difference between fixed and floating interest rates?

- Domain: **General Banking / Pricing**
- Expected source: `knowledge`
- Status: **Answered**
- Actual sources: `knowledge`
- Route match: **Yes**
- Latency: `6.65s`
- Cards: `brief`

#### Response

````text
A fixed interest rate remains constant throughout the loan term, while a floating rate changes based on a benchmark index. Neither concept is directly measured by the provided catalog metrics, which instead track outcomes like average interest rates, collection efficiency, and overdue amounts. This distinction helps borrowers predict repayment costs, whereas the catalog data reflects the bank's actual performance in collecting those payments.
````

---

### Q155 — What is reducing-balance interest?

- Domain: **General Banking / Pricing**
- Expected source: `knowledge`
- Status: **Answered**
- Actual sources: `knowledge`
- Route match: **Yes**
- Latency: `6.45s`
- Cards: `brief`

#### Response

````text
Reducing-balance interest is a method where interest is calculated only on the remaining unpaid principal amount of a loan, rather than the original total sum. As you make payments that reduce the principal, the interest charged in subsequent periods decreases accordingly. This differs from flat-rate interest, which calculates charges on the initial loan amount regardless of how much principal has been repaid.
````

---

### Q156 — What is flat-rate interest?

- Domain: **General Banking / Pricing**
- Expected source: `knowledge`
- Status: **Answered**
- Actual sources: `knowledge`
- Route match: **Yes**
- Latency: `7.37s`
- Cards: `brief`

#### Response

````text
Flat-rate interest is a method where interest is calculated as a fixed percentage of the original loan amount for the entire term, rather than on the declining balance. This results in a higher effective cost compared to reducing-balance methods because the borrower pays interest on money they no longer owe. It is distinct from the "Average interest rate" found in your catalog, which is a weighted average of rates across accounts, not a specific loan pricing structure.
````

---

### Q157 — What is average ticket size in lending?

- Domain: **General Banking / Pricing**
- Expected source: `knowledge`
- Status: **Answered**
- Actual sources: `knowledge`
- Route match: **Yes**
- Latency: `7.57s`
- Cards: `brief`

#### Response

````text
Average ticket size in lending is calculated by dividing the total sanctioned loan amount by the number of loans issued, providing a measure of the typical loan value per borrower. This metric helps lenders understand their portfolio composition but should not be confused with collection efficiency, which measures repayment performance, or principal outstanding, which tracks the remaining balance. Unlike average interest rates that are weighted by sanction amounts, average ticket size focuses purely on the volume of funds distributed per transaction.
````

---

### Q158 — What is yield on a loan portfolio?

- Domain: **General Banking / Pricing**
- Expected source: `knowledge`
- Status: **Answered**
- Actual sources: `knowledge`
- Route match: **Yes**
- Latency: `6.54s`
- Cards: `brief`

#### Response

````text
Portfolio yield is the average interest rate earned across a group of loans, calculated by weighting each account's rate by its sanction amount. This metric helps lenders understand overall profitability but is distinct from the principal outstanding, which measures the total remaining loan balance rather than the rate of return. Unlike simple averages, portfolio yield accounts for the size of each loan to provide a more accurate picture of performance.
````

---

### Q159 — What is loan origination?

- Domain: **General Banking / Operations**
- Expected source: `knowledge`
- Status: **Answered**
- Actual sources: `knowledge`
- Route match: **Yes**
- Latency: `7.37s`
- Cards: `brief`

#### Response

````text
Loan origination is the process of creating a new loan account, tracked in banking reports as the "count of loan accounts sanctioned" within a specific period. This stage involves determining the "average ticket size," which is calculated by dividing the total sanctioned amount by the number of loans issued. It is distinct from loan collection, which measures repayment efficiency, and from the "principal outstanding," which represents the remaining balance after disbursement and repayments rather than the initial approval.
````

---

### Q160 — What is loan underwriting?

- Domain: **General Banking / Operations**
- Expected source: `knowledge`
- Status: **Answered**
- Actual sources: `knowledge`
- Route match: **Yes**
- Latency: `7.06s`
- Cards: `brief`

#### Response

````text
Loan underwriting is the process of evaluating a borrower's creditworthiness and risk before approving a loan. It involves analyzing factors like income and repayment history to determine the loan amount and terms, distinct from post-disbursement metrics like collection efficiency which measure actual payments made. While the provided catalog tracks outcomes such as sanctioned loan counts and outstanding principal, underwriting is the pre-approval assessment that decides if a loan enters those records.
````

---

### Q161 — Compare our loan-book growth with the latest supported national credit-growth trend.

- Domain: **Hybrid / Book + Macro**
- Expected source: `db, macro`
- Status: **Answered**
- Actual sources: `db, macro`
- Route match: **Yes**
- Latency: `50.71s`
- Cards: `chart, brief`

#### Response

````text
Principal outstanding was ₹0 in 2025-04-01 to 2026-03-31; there is no comparable figure for 2024-04-01 to 2025-03-31. This measures principal outstanding from each classified account at the requested snapshot, grouped by month.

The latest national credit-growth trend, as of May 31, 2026, shows a widening wedge between credit and deposit growth, with SCB credit growing at 17.7% (y-o-y) versus deposits at 12.2% (rbi, p.51). Total bank credit recorded double-digit growth across major sectors in April 2026, driven by a pickup in non-food bank credit and foreign direct investment (rbi, p.51). Specifically, non-food bank credit growth stood higher than the previous year, leading to higher total outstanding credit (rbi, p.51). Sectoral data for April 2026 indicates robust performance in Computer Software (52.7% growth) and Loan against gold jewellery (121.2% growth), while Wholesale Trade declined by 5.7% (rbi, p.77). Historically, the flow of resources to the commercial sector has demonstrated a CAGR of 20.9% between FY20 and FY25, rising to ₹35.1 lakh crore in FY25 (economic_survey, p.145). This upward trend continued into FY26, with the overall flow reaching ₹30.8 lakh crore in April-December 2025, registering a 44.7% increase (economic_survey, p.145).

Our loan-book growth cannot be compared to the national credit-growth trend because the database contains no principal outstanding figures for the 2024-04-01 to 2025-03-31 period, making a year-over-year calculation impossible. In contrast, the latest national data indicates robust credit expansion, with total bank credit showing double-digit growth driven by a 17.7% year-over-year increase in SCB credit and surging sectoral performance in Computer Software (52.7%) and Loan against gold jewellery (121.2%). While the national flow of resources to the commercial sector rose 44.7% to ₹30.8 lakh crore in April-December 2025, our internal records lack the necessary historical snapshot to determine if we are participating in this upward trajectory.
````

#### SQL

````sql
SELECT buckets.bucket_start AS month,
       SUM(portfolio.principal_outstanding) AS principal_outstanding
FROM (SELECT generate_series(DATE '2025-04-01'::date, DATE '2026-03-31'::date,
                             INTERVAL '1 month')::date AS bucket_start) AS buckets
     LEFT JOIN LATERAL gold.portfolio_snapshot_as_of(
       LEAST((buckets.bucket_start + INTERVAL '1 month' - INTERVAL '1 day')::date, DATE '2026-03-31'::date)
     ) AS portfolio ON TRUE
GROUP BY buckets.bucket_start
ORDER BY buckets.bucket_start ASC
LIMIT 200
````

#### Citations

- rbi
- economic_survey

---

### Q162 — How does our MSME disbursement trend compare with the macro outlook for Indian MSMEs?

- Domain: **Hybrid / Book + Macro**
- Expected source: `db, macro`
- Status: **Answered**
- Actual sources: `db, macro`
- Route match: **Yes**
- Latency: `21.16s`
- Cards: `chart, brief`

#### Response

````text
Disbursement was ₹226.69 Cr in all time. This measures sum of disbursement event amounts in the period.

The Indian MSME sector remains a vibrant engine of the economy, contributing approximately 30% of India's GDP and over 45% of exports [msme, p.7]. It fosters entrepreneurship and employment at lower capital costs, acting as a crucial complement to large industries. The Ministry envisions sustainable, globally competitive MSMEs by addressing challenges such as access to credit, finance, markets, and technology, while promoting digitalization and skill development. The outlook emphasizes inclusive growth through geographic and demographic inclusivity, supporting ancillary units and women entrepreneurship. However, the provided text outlines the sector's structural importance and policy objectives rather than offering a specific forward-looking macroeconomic forecast or current performance metrics for the 2024-25 period.

Our bank's total historical MSME disbursement stands at ₹226.69 Cr, whereas the macro outlook for Indian MSMEs highlights the sector's structural importance as a contributor to approximately 30% of India's GDP and over 45% of exports. While the Ministry envisions sustainable growth through digitalization and inclusive policies, the provided text does not offer specific forward-looking performance metrics or forecasts for the 2024-25 period to allow for a direct quantitative comparison of our disbursement trend against current macroeconomic projections. Consequently, a precise trend comparison cannot be established due to the absence of specific future macroeconomic data in the source material.
````

#### SQL

````sql
SELECT SUM(disb.disbursement_amount) AS disbursement_total
FROM gold.loan_disbursement_events AS disb
     JOIN gold.loan_account_master AS lam ON disb."entity_num" = lam."entity_num" AND disb."loan_account_number" = lam."loan_account_number"
WHERE disb."disbursement_date" BETWEEN DATE '2000-01-01' AND DATE '2026-08-26'
  AND lam."product_code"::text = '16'
LIMIT 200
````

#### Citations

- msme

---

### Q163 — Compare our Gold Loan portfolio trend with the macro factors affecting gold prices.

- Domain: **Hybrid / Book + Macro**
- Expected source: `db, macro`
- Status: **Partial**
- Actual sources: `db, macro`
- Route match: **Yes**
- Latency: `49.77s`
- Cards: `brief, refusal`

#### Response

````text
Based on the provided context, a primary macro factor affecting gold prices is its direct impact on core inflation. The text notes that the steady pace of core inflation has been largely influenced by higher inflation in the prices of precious metals like gold and silver [economic_survey, p.18]. While the document details trends in the Terms of Trade for the manufacturing sector and sectoral shares in Gross Value Added, it does not provide further specific macroeconomic factors driving gold price movements beyond this inflationary link. Consequently, the available information only supports the explanation that rising gold prices contribute to increased core inflation.

I could not answer that safely from the available data.
````

#### Citations

- economic_survey

---

### Q164 — Assess our collection-efficiency trend alongside the latest supported inflation conditions.

- Domain: **Hybrid / Book + Macro**
- Expected source: `db, macro`
- Status: **Answered**
- Actual sources: `db, macro`
- Route match: **Yes**
- Latency: `32.25s`
- Cards: `chart, brief`

#### Response

````text
Collection efficiency fell from 100.0% (Nov 2025) to 96.3% (Jul 2026), a change of 3.7%. This measures total principal and interest paid divided by total principal and interest due, grouped by month.

The latest available inflation data from the provided context covers April 2026, which is marked as provisional [mospi, p.10]. During this period, the All India Combined Consumer Price Index stood at 105.12, reflecting a combined inflation rate of 3.48% [mospi, p.10]. Specifically, rural inflation was recorded at 3.74% while urban inflation was 3.16% for the same month [mospi, p.10]. Prior to April 2026, the combined inflation rate in March 2026 was 3.40% [mospi, p.10]. As these are periodic statistics, no daily or "today's" inflation value is available in the text.

Our collection efficiency has declined by 3.7%, dropping from 100.0% in November 2025 to 96.3% in July 2026. This downward trend coincides with a stable inflationary environment where the All India Combined Consumer Price Index recorded a 3.48% rate in April 2026, following a 3.40% rate in March 2026. While rural inflation (3.74%) was slightly higher than urban inflation (3.16%) during this period, the available data does not extend beyond April 2026 to provide a direct comparison with the July 2026 collection figures.
````

#### SQL

````sql
SELECT DATE_TRUNC('month', repay."repayment_date")::date AS month,
       (100.0 * COALESCE(SUM(repay.total_paid), 0) / NULLIF(SUM(repay.total_due), 0)) AS collection_efficiency
FROM gold.loan_repayment_events AS repay
WHERE repay."repayment_date" BETWEEN DATE '2000-01-01' AND DATE '2026-08-26'
GROUP BY DATE_TRUNC('month', repay."repayment_date")::date
ORDER BY DATE_TRUNC('month', repay."repayment_date")::date ASC
LIMIT 200
````

#### Citations

- mospi

---

### Q165 — Compare our average sanctioned interest rate with the indexed RBI monetary-policy context.

- Domain: **Hybrid / Book + Macro**
- Expected source: `db, macro`
- Status: **Partial**
- Actual sources: `db, macro`
- Route match: **Yes**
- Latency: `27.97s`
- Cards: `chart, brief`

#### Response

````text
Average interest rate was 17.7% in all time. This measures sanction-amount-weighted average account interest rate. Definition of Average interest rate is pending client sign-off.

The provided context does not contain specific indexed monetary policy rates or the current RBI monetary policy stance. It only lists the titles of tables and indicators available in the RBI Bulletin June 2026, such as "Liquidity Operations by RBI" and "RBI's Standing Facilities" [rbi, p.63], but does not display the actual rate values or policy decisions. The document presents provisional balance sheet data for May 2025 and monetary aggregates up to March 31, 2026, without detailing the policy context or specific interest rates [rbi, p.66], [rbi, p.72].

Our average sanctioned interest rate stands at 17.7%, calculated as a sanction-amount-weighted average across all time, though this definition remains pending client sign-off. A direct comparison with the indexed RBI monetary-policy context cannot be completed because the provided source material lists relevant RBI Bulletin titles and data categories but fails to display the actual policy rates or specific monetary stance values required for analysis. Consequently, while our internal rate is quantified, the external benchmark data necessary to contextualize it is absent from the supplied findings.
````

#### SQL

````sql
SELECT (COALESCE(SUM(lam.interest_rate * lam.sanction_amount), 0) / NULLIF(SUM(lam.sanction_amount), 0)) AS avg_interest_rate
FROM gold.loan_account_master AS lam
WHERE lam."sanction_date" BETWEEN DATE '2000-01-01' AND DATE '2026-08-26'
LIMIT 200
````

#### Citations

- rbi

---

### Q166 — How does our branch-level disbursement trend align with Karnataka's economic outlook?

- Domain: **Hybrid / Book + Macro**
- Expected source: `db, macro`
- Status: **Answered**
- Actual sources: `db, macro`
- Route match: **Yes**
- Latency: `36.70s`
- Cards: `chart, brief`

#### Response

````text
Head Office — Credit Division is the only branch returned, with disbursement of ₹137.16 Cr in FY27 to date. This measures sum of disbursement event amounts in the period, grouped by branch.

Karnataka's economic outlook for 2025-26 (Budget Estimate) shows a fiscal deficit of 2.90% of GSDP and a revenue deficit of 0.63% of GSDP [karnataka_des, p.83]. The state leads among southern states in capital outlay (Rs.68,172.20 crore) and maintains the lowest outstanding debt as a percentage of GSDP at 24.91% [karnataka_des, p.83]. Additionally, Karnataka ranks second in the region for revenue deficit (Rs.19,262.00 crore) and interest payments as a percentage of revenue receipts at 15.59% [karnataka_des, p.83]. While the fiscal deficit is projected to rise slightly from 2.55% in 2023-24 to 2.90% in 2024-25 before reaching 2.95% in 2025-26 [karnataka_des, p.83], the state's overall fiscal position remains robust compared to peers like Andhra Pradesh and Kerala.

Our branch-level disbursement trend is currently represented solely by the Head Office Credit Division, which recorded ₹137.16 Cr in disbursements in FY27 to date. This specific branch data cannot be directly compared to Karnataka's broader economic outlook because the findings lack disbursement figures for other branches or a total branch-level aggregate. While the state maintains a robust fiscal position with the lowest outstanding debt as a percentage of GSDP at 24.91% and leads southern states in capital outlay, the available evidence does not provide the necessary branch-wide volume to assess alignment with these macroeconomic indicators. Consequently, a direct comparison between our branch performance and the state's economic trajectory remains unsupported by the current data.
````

#### SQL

````sql
SELECT lam."branch_code" AS branch,
       SUM(disb.disbursement_amount) AS disbursement_total
FROM gold.loan_disbursement_events AS disb
     JOIN gold.loan_account_master AS lam ON disb."entity_num" = lam."entity_num" AND disb."loan_account_number" = lam."loan_account_number"
WHERE disb."disbursement_date" BETWEEN DATE '2026-04-01' AND DATE '2026-08-26'
GROUP BY lam."branch_code"
ORDER BY SUM(disb.disbursement_amount) DESC NULLS LAST
LIMIT 200
````

#### Citations

- karnataka_des

---

### Q167 — Compare our retail-loan growth with the macro evidence on household credit conditions.

- Domain: **Hybrid / Book + Macro**
- Expected source: `db, macro`
- Status: **Partial**
- Actual sources: `db, macro`
- Route match: **Yes**
- Latency: `64.65s`
- Cards: `brief, refusal`

#### Response

````text
The latest data from the RBI Bulletin June 2026 indicates that household credit conditions, specifically Personal Loans, grew by 0.3% year-on-year as of March 31, 2026, reaching ₹16.0 lakh crore [rbi, p.77]. Within this category, Vehicle Loans showed robust growth at 0.6% (₹18.0 lakh crore) [rbi, p.77], while Loan against gold jewellery surged dramatically by 5.9% to ₹121.2 lakh crore [rbi, p.77]. Conversely, Consumer Durables credit contracted by 3.4% [rbi, p.77], and Advances against Fixed Deposits fell by 6.6% [rbi, p.77]. Education loans declined slightly by 0.1% [rbi, p.77]. Overall, the commercial sector's non-food credit contracted by 0.9% year-on-year, with the broader Bank Credit figure showing a marginal decline of 0.7% [rbi, p.77].

I could not answer that safely from the available data.
````

#### Citations

- rbi

---

### Q168 — Assess our current PAR 30 against the macro risks facing MSME borrowers.

- Domain: **Hybrid / Book + Macro**
- Expected source: `db, macro`
- Status: **Answered**
- Actual sources: `db, macro`
- Route match: **Yes**
- Latency: `20.57s`
- Cards: `chart, brief`

#### Response

````text
Dairy Loan has the highest par 30, at 1.2% as at 26 Aug 2026. This measures principal outstanding over 30 DPD divided by classified principal outstanding, grouped by scheme. Definition of PAR 30 is pending client sign-off.

The primary macroeconomic risk affecting MSME borrowers is the persistence of delayed payments, with an estimated ₹8.1 lakh crore locked in arrears [msme, p.34]. This liquidity crunch restricts working capital and growth, while the fear of damaging long-term commercial ties prevents borrowers from pursuing legal recourse against buyers [msme, p.34]. Although initiatives like the ODR Portal aim to facilitate amicable settlements and recover dues without straining relationships, the underlying challenge of non-payment remains a critical barrier to operational sustainability [msme, p.34].

Our current PAR 30 for the Dairy Loan scheme stands at 1.2% as of 26 August 2026, which is the highest among all schemes, though the official definition of this metric is still pending client sign-off. This specific portfolio risk contrasts with the broader macroeconomic environment where ₹8.1 lakh crore remains locked in arrears across MSMEs, creating a liquidity crunch that restricts working capital and growth. While borrowers currently avoid legal recourse to preserve commercial ties, the persistence of non-payment remains a critical barrier to operational sustainability that our current PAR 30 figure does not fully capture given the pending definition.
````

#### SQL

````sql
SELECT lam."scheme_code" AS scheme,
       (100.0 * COALESCE(SUM(portfolio.principal_outstanding) FILTER (WHERE portfolio.is_par30), 0) / NULLIF(SUM(portfolio.principal_outstanding), 0)) AS par_30
FROM gold.portfolio_snapshot_as_of(DATE '2026-08-26') AS portfolio
     JOIN gold.loan_account_master AS lam ON portfolio."entity_num" = lam."entity_num" AND portfolio."loan_account_number" = lam."loan_account_number"
WHERE lam."product_code"::text = '16'
GROUP BY lam."scheme_code"
ORDER BY (100.0 * COALESCE(SUM(portfolio.principal_outstanding) FILTER (WHERE portfolio.is_par30), 0) / NULLIF(SUM(portfolio.principal_outstanding), 0)) DESC NULLS LAST
LIMIT 200
````

#### Citations

- msme

---

### Q169 — Compare our monthly sanctions with the latest supported industrial-growth trend.

- Domain: **Hybrid / Book + Macro**
- Expected source: `db, macro`
- Status: **Answered**
- Actual sources: `db, macro`
- Route match: **Yes**
- Latency: `51.60s`
- Cards: `chart, brief`

#### Response

````text
Loans sanctioned rose from 13 (Oct 2025) to 179 (Jul 2026), a change of 1276.9%. This measures count of loan accounts sanctioned in the period, grouped by month.

The latest industrial growth trend, as of April 2026, shows a headline Index of Industrial Production (IIP) growth of 4.9% year-on-year under the new base year 2022-23 [rbi, p.42]. This follows a strengthening trend in April compared to the previous month, driven by robust manufacturing sector performance [rbi, p.42]. High-frequency indicators suggest continued strengthening, with the IIP headline averaging 3.6% growth in Q3 FY26 [economic_survey, p.68]. While the overall trend remains positive, the Index of Eight Core Industries witnessed moderation in May 2026, primarily due to declines in refinery products and coal [rbi, p.42]. Manufacturing activity faces headwinds from rising input costs and the West Asia conflict, though PMI manufacturing remains in expansion territory at 55.0 [rbi, p.42]. Sectoral variations persist, with capital goods showing strong growth of 16.0% in May, while electricity generation surged due to peak demand [rbi, p.42].

Our monthly loan sanctions surged from 13 in October 2025 to 179 in July 2026, representing a 1276.9% increase in account count, which contrasts sharply with the macroeconomic backdrop where the Index of Industrial Production grew at a steady 4.9% year-on-year as of April 2026. While the overall industrial trend remains positive with an average Q3 FY26 growth of 3.6%, the recent moderation in the Index of Eight Core Industries and headwinds from rising input costs suggest a divergence between our aggressive sanctioning volume and the sector's current cooling momentum. Specifically, although capital goods and electricity generation showed strong performance, the decline in refinery products and coal indicates that our broad sanctioning strategy may not be fully aligned with the specific industrial slowdowns occurring in May 2026.
````

#### SQL

````sql
SELECT DATE_TRUNC('month', lam."sanction_date")::date AS month,
       COUNT(*) AS loan_count
FROM gold.loan_account_master AS lam
WHERE lam."sanction_date" BETWEEN DATE '2000-01-01' AND DATE '2026-08-26'
GROUP BY DATE_TRUNC('month', lam."sanction_date")::date
ORDER BY DATE_TRUNC('month', lam."sanction_date")::date ASC
LIMIT 200
````

#### Citations

- rbi
- economic_survey

---

### Q170 — What do our disbursement figures and the macro credit outlook together imply for near-term lending demand?

- Domain: **Hybrid / Book + Macro**
- Expected source: `db, macro`
- Status: **Answered**
- Actual sources: `db, macro`
- Route match: **Yes**
- Latency: `49.76s`
- Cards: `analysis, brief`

#### Response

````text
Nothing is outside its threshold across 6 indicators.

The latest macro credit data (RBI Bulletin June 2026, p.77) indicates a mixed outlook: total bank credit grew 16.0% Y-o-Y, driven by strong services (18.6%) and personal loans (16.0%), while agriculture (-0.7%) and industry (-1.0%) contracted. Lending conditions show hardening rates during the easing cycle (Feb 2025–Apr 2026), with uneven transmission to sectors (p.53). Non-food bank credit stood at ₹1,83,71,998 crore as of May 31, 2026 (p.81), excluding co-operative banks. Priority sector lending remains robust, with micro & small enterprises up 28.5% (p.77). Overall, credit deployment is sectoral, with services and gold loans (121.2% growth) leading, while trade and wholesale segments face contraction.

Our disbursement figures indicate that nothing is outside its threshold across six indicators, suggesting internal stability, while the macro credit outlook reveals a mixed near-term demand landscape where services and personal loans are growing at 18.6% and 16.0% respectively, contrasting sharply with contractions in agriculture (-0.7%) and industry (-1.0%). This divergence implies that lending demand is becoming increasingly sectoral, heavily driven by gold loans (121.2% growth) and micro & small enterprises (28.5% growth), whereas trade and wholesale segments face headwinds. Although total bank credit expanded by 16.0% year-over-year, the hardening of lending rates during the easing cycle and uneven transmission to specific sectors suggest that future demand will depend on navigating these divergent sectoral trends rather than uniform growth. The provided findings do not explicitly quantify the specific impact of our internal disbursement figures on the broader macro trends, leaving the precise magnitude of our contribution to the overall market shift unmeasured.
````

#### Citations

- rbi

---

### Q171 — Compare our MSME product mix with the products documented for Karnataka competitors.

- Domain: **Hybrid / Book + Competitive**
- Expected source: `db, competitive`
- Status: **Answered**
- Actual sources: `db, competitive`
- Route match: **Yes**
- Latency: `46.38s`
- Cards: `chart, brief`

#### Response

````text
Business & MSME Loans is the only product returned, with principal outstanding of ₹204.54 Cr as at 26 Aug 2026. This measures principal outstanding from each classified account at the requested snapshot, grouped by product.

Rival lenders in Karnataka offer distinct MSME products. Kinara Capital provides working capital, asset purchase, and collateral-free loans (₹1 lakh–₹30 lakhs), plus the women-focused HerVikas loan [Kinara Capital]. It also leverages government schemes like Stand-Up India and MUDRA Yojana [Kinara Capital].

Traditional cooperatives like Karnataka State Co-operative Apex Bank focus on agriculture and rural credit, offering short-term crop loans and medium-term infrastructure financing, though specific MSME product details are less detailed in the provided text [Karnataka State Co-operative Apex Bank]. National Co-operative Bank offers working capital term loans for small business entrepreneurs, with a 0.25% p.a. interest concession for women borrowers [National Co-operative Bank].

SIDBI acts primarily as a facilitator and refinance agency rather than a direct lender, supporting MSMEs through schemes like PM Vishwakarma and Udyam Assist [SIDBI]. Other local co-ops (Bhatkal, Kaujalgi, Belgaum) have local presence but lack specific product details in the evidence [Bhatkal Urban Co-operative Bank] [Kaujalgi Urban Co-operative Bank] [Belgaum Industrial Co-operative Bank].

**Gap:** Specific interest rates, ticket sizes, and turnaround times for most institutions are absent from the provided evidence.

Our MSME portfolio currently consists solely of Business & MSME Loans with a principal outstanding of ₹204.54 Cr, whereas Karnataka competitors offer a distinct mix including Kinara Capital's collateral-free working capital and asset purchase loans, National Co-operative Bank's working capital term loans with interest concessions, and various agricultural and rural credit products from traditional cooperatives. While our data captures only one product category, the competitive landscape reveals a broader range of offerings such as women-focused schemes and government-backed facilitation by SIDBI, though specific details on ticket sizes, interest rates, and turnaround times for most institutions remain absent from the evidence.
````

#### SQL

````sql
SELECT lam."product_code" AS product,
       SUM(portfolio.principal_outstanding) AS principal_outstanding
FROM gold.portfolio_snapshot_as_of(DATE '2026-08-26') AS portfolio
     JOIN gold.loan_account_master AS lam ON portfolio."entity_num" = lam."entity_num" AND portfolio."loan_account_number" = lam."loan_account_number"
GROUP BY lam."product_code"
ORDER BY SUM(portfolio.principal_outstanding) DESC NULLS LAST
LIMIT 200
````

#### Citations

- Kinara Capital
- Karnataka State Co-operative Apex Bank
- SIDBI

---

### Q172 — How does our average MSME ticket size compare with available competitor evidence?

- Domain: **Hybrid / Book + Competitive**
- Expected source: `db, competitive`
- Status: **Partial**
- Actual sources: `db, competitive`
- Route match: **Yes**
- Latency: `62.36s`
- Cards: `brief, chart`

#### Response

````text
The provided indexed passages do not contain specific evidence on competitor MSME ticket sizes (loan amounts) or explicit positioning details for most institutions. While [Kinara Capital] defines MSME categories by annual turnover (Micro: up to INR 5 crores; Small: INR 5–50 crores; Medium: INR 50–250 crores), it does not state specific loan ticket sizes or interest rates.

For other entities like [Bellary Urban Co-operative Bank], [Karnataka State Financial Corporation], and various district co-operative banks, the text explicitly states: "MSME positioning is not explicit in the extracted crawl text." Similarly, financial figures and specific ticket sizes for these lenders are absent, requiring annual reports or statutory documents for validation. Consequently, a direct comparison of ticket sizes and precise positioning is not possible based solely on the supplied evidence.

Avg Msme Ticket Size was ₹3.98 L. Average sanctioned amount for MSME loans (product_code 16). This uses a validated read-only generated query rather than a reviewed metric; check Source details before relying on it.

Our internal average MSME ticket size is ₹3.98 lakhs, derived from a validated read-only query for product code 16, though this metric requires source verification before full reliance. In contrast, direct comparison with competitors is not possible because the available evidence lacks specific loan ticket sizes or explicit positioning details for institutions like Kinara Capital, Bellary Urban Co-operative Bank, and Karnataka State Financial Corporation. While Kinara Capital defines MSME categories by turnover, it does not disclose specific loan amounts, and other entities explicitly lack extracted financial figures for ticket sizes. Consequently, a precise comparative analysis of our ticket size against competitor evidence cannot be completed with the current data.
````

#### SQL

````sql
SELECT
  AVG(sanction_amount) AS avg_msme_ticket_size
FROM gold.loan_account_master
WHERE
  product_code = 16 AND sanction_date >= CAST('2023-01-01' AS DATE)
LIMIT 100
````

#### Citations

- Bellary Urban Co-operative Bank
- Karnataka State Financial Corporation
- SIDBI
- Bhatkal Urban Co-operative Bank
- Kaujalgi Urban Co-operative Bank
- Belgaum Industrial Co-operative Bank

---

### Q173 — Compare our Gold Loan presence with collateral-backed products offered by competitors.

- Domain: **Hybrid / Book + Competitive**
- Expected source: `db, competitive`
- Status: **Answered**
- Actual sources: `db, competitive`
- Route match: **Yes**
- Latency: `47.62s`
- Cards: `analysis, brief`

#### Response

````text
Nothing is outside its threshold across 5 indicators.

Competitor collateral-backed products vary significantly. Karnataka State Co-operative Apex Bank offers loans up to ₹10 lakhs without security (with guarantors) and requires collateral equal to 100% of the loan amount for larger sums, accepting land, gold, or government securities [Karnataka State Co-operative Apex Bank]. In contrast, Kinara Capital primarily markets collateral-free MSME loans, though it acknowledges Loan Against Property (LAP) as a security option [Kinara Capital]. Other institutions like Bellary, Bhatkal, and Belgaum Urban Co-operative Banks lack explicit collateral details in available text [Bellary Urban Co-operative Bank].

Positioning-wise, cooperative banks leverage local branch presence for relationship-led acquisition, differentiating themselves from digital-first NBFCs and fintechs that compete on speed and unsecured offerings [Karnataka State Co-operative Apex Bank]. While cooperatives focus on rural/agriculture segments, competitors like Kinara Capital target urgent working capital needs with 24-hour disbursement and flexible tenures [Kinara Capital]. A gap exists regarding specific interest rates and processing times for the cooperative banks' collateral products, as source pages require periodic refreshing [Karnataka State Co-operative Apex Bank].

Our Gold Loan presence is not explicitly detailed in the provided findings, whereas competitor collateral-backed products vary significantly in structure and target segments. Competitors like Karnataka State Co-operative Apex Bank offer a hybrid model ranging from unsecured loans up to ₹10 lakhs to fully secured loans requiring 100% collateral for larger sums, while Kinara Capital primarily markets collateral-free MSME loans with Loan Against Property as an option. Positioning-wise, cooperative banks leverage local branch presence for relationship-led acquisition in rural and agriculture segments, contrasting with digital-first NBFCs like Kinara Capital that compete on speed and urgent working capital needs. A gap exists regarding specific interest rates and processing times for the cooperative banks' collateral products, as source pages require periodic refreshing.
````

#### Citations

- Karnataka State Co-operative Apex Bank
- Kinara Capital
- Kaujalgi Urban Co-operative Bank

---

### Q174 — Assess our branch concentration against the documented geographic reach of competitors.

- Domain: **Hybrid / Book + Competitive**
- Expected source: `db, competitive`
- Status: **Partial**
- Actual sources: `db, competitive`
- Route match: **Yes**
- Latency: `36.86s`
- Cards: `refusal, brief`

#### Response

````text
I could not answer that safely from the available data.

Rival lenders in Karnataka exhibit a dual geographic strategy: deep local penetration and expanding digital reach. Cooperative institutions like Bellary Urban Co-operative Bank, Kaujalgi Urban Co-operative Bank, Bhatkal Urban Co-operative Bank, Belgaum Industrial Co-operative Bank, and Belagavi District Central Co-operative Bank leverage "local, branch, co-operative, or rural presence" to support relationship-led distribution [Bellary Urban Co-operative Bank]. This network extends to district and office levels, indicating identifiable geographic distribution networks [Karnataka State Co-operative Apex Bank].

Conversely, NBFCs and fintechs like Kinara Capital and SIDBI demonstrate broader, multi-state footprints. Kinara Capital has expanded from its initial Karnataka branch to over 125 branches across 100+ cities in states including Maharashtra, Andhra Pradesh, Telangana, and Gujarat [Kinara Capital]. While cooperative banks focus on rural and local segments, these larger entities compete on faster approval and digital onboarding, often lacking explicit rural product signals found in cooperative profiles [Karnataka State Co-operative Apex Bank]. No specific page numbers are cited as the source documents do not include them.
````

#### Citations

- Karnataka State Co-operative Apex Bank
- Bellary Urban Co-operative Bank
- Karnataka State Financial Corporation
- Kaujalgi Urban Co-operative Bank
- Bhatkal Urban Co-operative Bank

---

### Q175 — Compare our sanctioned interest rates with available competitor loan-pricing evidence.

- Domain: **Hybrid / Book + Competitive**
- Expected source: `db, competitive`
- Status: **Answered**
- Actual sources: `db, competitive`
- Route match: **Yes**
- Latency: `25.49s`
- Cards: `chart, brief`

#### Response

````text
18.0% has the highest loan count at 3,740 across 8 returned interest rate value(s). Distinct contractual account interest rates, with the number of sanctioned loans at each rate, across the full available loan book. This uses a validated read-only generated query rather than a reviewed metric; check Source details before relying on it.

No specific loan interest rates, ticket sizes, or turnaround times are provided in the supplied indexed passages for any institution. While Karnataka State Co-operative Apex Bank and Karnataka State Financial Corporation mention a "4 Percent Interest Rate" for specific schemes, the context implies fixed deposits or subsidies rather than general lending rates [Karnataka State Financial Corporation]. Kinara Capital lists "Business Loan Interest Rate" as a topic but provides no numerical values [Kinara Capital]. National Co-operative Bank notes a "Concession Rate 0.25% p.a." for women borrowers but does not state the base rate [National Co-operative Bank]. Consequently, direct pricing comparison is impossible with the current evidence.

Our internal data indicates that 18.0% is the most prevalent sanctioned interest rate, applied to 3,740 loans across eight distinct rate values. However, a direct comparison with competitor pricing is impossible because the available evidence provides no specific loan interest rates, ticket sizes, or turnaround times for any institution. While some competitors mention specific schemes or concessions, these do not constitute general lending rates required for a valid comparison. Consequently, the current evidence is insufficient to benchmark our rates against the market.
````

#### SQL

````sql
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
````

#### Citations

- Karnataka State Co-operative Apex Bank
- Kinara Capital
- Kaujalgi Urban Co-operative Bank

---

### Q176 — Which gaps between our scheme mix and competitor offerings could represent white space?

- Domain: **Hybrid / Book + Competitive**
- Expected source: `db, competitive`
- Status: **Answered**
- Actual sources: `db, competitive`
- Route match: **Yes**
- Latency: `53.87s`
- Cards: `chart, brief`

#### Response

````text
The query returned 14 row(s) covering scheme code, scheme name. Distinct schemes from the active loan book. This uses a validated read-only generated query rather than a reviewed metric; check Source details before relying on it.

Competitor offerings in the MSME market vary significantly by institution type. Kinara Capital, an NBFC, offers distinct products including Machinery Purchase Loans, Green Loans, Short-Term Working Capital Loans, and Loan Against Property (LAP). Notably, they provide collateral-free business loans ranging from Rs. 1 lakh to Rs. 30 lakhs and feature specialized "HerVikas" loans for women-owned businesses. They also highlight quick disbursals and minimum documentation [Kinara Capital].

In contrast, most listed Karnataka co-operative banks (e.g., Bhatkal, Kaujalgi, Belgaum) and the Karnataka State Co-operative Apex Bank lack explicit product details in the provided text. While they possess local branch networks supporting relationship-led acquisition and servicing, specific loan types, interest rates, or ticket sizes are absent from the indexed evidence [Bhatkal Urban Co-operative Bank]. Similarly, SIDBI and Karnataka State Financial Corporation show MSME relevance but lack explicit product listings in the source material [SIDBI]. The primary competitive gap is the absence of detailed product specifications for co-operatives compared to the granular offerings of NBFCs like Kinara.

The primary white space identified is the absence of detailed product specifications for Karnataka co-operative banks and SIDBI, which contrasts sharply with the granular offerings of NBFCs like Kinara Capital. While Kinara provides distinct products such as collateral-free loans ranging from Rs. 1 lakh to Rs. 30 lakhs and specialized "HerVikas" loans for women-owned businesses, the indexed evidence lacks explicit product details, interest rates, or ticket sizes for the co-operatives. Consequently, the specific gaps between our scheme mix and competitor offerings cannot be quantified because the source data does not list the actual scheme codes or names for the co-operative competitors.
````

#### SQL

````sql
SELECT DISTINCT
  scheme_code,
  scheme_name
FROM gold.loan_account_master
WHERE
  scheme_code IS NOT NULL AND scheme_name IS NOT NULL
ORDER BY
  scheme_code
LIMIT 5000
````

#### Citations

- Karnataka State Co-operative Apex Bank
- Kinara Capital
- Bhatkal Urban Co-operative Bank
- Kaujalgi Urban Co-operative Bank

---

### Q177 — Compare our MSME disbursement trend with Kinara Capital's documented positioning.

- Domain: **Hybrid / Book + Competitive**
- Expected source: `db, competitive`
- Status: **Answered**
- Actual sources: `db, competitive`
- Route match: **Yes**
- Latency: `26.21s`
- Cards: `chart, brief`

#### Response

````text
Disbursement was ₹226.69 Cr in all time. This measures sum of disbursement event amounts in the period.

Kinara Capital positions itself as a mission-driven fintech NBFC founded in 2011 to drive last-mile MSME financial inclusion and fuel small business growth [Kinara Capital]. It targets underserved MSMEs through collateral-free loans disbursed in 24 hours with minimal documentation [Kinara Capital]. The institution emphasizes a balanced business model that achieved profitability for nine consecutive years while scaling operations [Kinara Capital]. Its strategy involves partnering with equity investors who share its long-term view of unlocking the massive opportunity in India's MSME sector [Kinara Capital]. Eligibility typically requires businesses to be operational for 1–2 years, though women-led or registered MSMEs may face relaxed criteria [Kinara Capital]. Loan amounts can reach up to Rs. 30 lakhs, depending on business age, sector, turnover, and loan purpose [Kinara Capital]. Unlike some competitors, Kinara explicitly states it will not ask for commissions or payments for loan processing [Kinara Capital]. No direct comparison with other institutions is provided in the supplied text.

Our total MSME disbursement stands at ₹226.69 Cr, whereas Kinara Capital positions itself as a mission-driven NBFC focused on last-mile inclusion through collateral-free loans disbursed in 24 hours with minimal documentation. While Kinara targets underserved businesses operational for 1–2 years with loan amounts up to Rs. 30 lakhs and explicitly avoids charging commissions, the provided findings do not contain specific disbursement figures or operational metrics for Kinara to allow for a direct quantitative comparison of our trends against theirs. Consequently, we can only contrast our aggregate volume with Kinara's qualitative strategic positioning regarding speed, eligibility, and fee structure.
````

#### SQL

````sql
SELECT SUM(disb.disbursement_amount) AS disbursement_total
FROM gold.loan_disbursement_events AS disb
     JOIN gold.loan_account_master AS lam ON disb."entity_num" = lam."entity_num" AND disb."loan_account_number" = lam."loan_account_number"
WHERE disb."disbursement_date" BETWEEN DATE '2000-01-01' AND DATE '2026-08-26'
  AND lam."product_code"::text = '16'
LIMIT 200
````

#### Citations

- Kinara Capital

---

### Q178 — How does our portfolio focus compare with SIDBI's documented MSME priorities?

- Domain: **Hybrid / Book + Competitive**
- Expected source: `db, competitive`
- Status: **Partial**
- Actual sources: `db, regulatory`
- Route match: **No**
- Latency: `64.52s`
- Cards: `refusal, brief`

#### Response

````text
I could not answer that safely from the available data.

Based on the provided evidence, **there is no information regarding SIDBI's documented MSME lending priorities or focus areas.**

The supplied text exclusively outlines the **RBI Digital Lending Directions (2025)** for Regulated Entities (REs) and Lending Service Providers (LSPs). It details operational requirements such as:
*   Obtaining explicit consent before sharing personal information.
*   Conducting enhanced due diligence before agreements with LSPs.
*   Ensuring unbiased content display on Digital Lending Apps (DLAs).
*   Prohibiting automatic credit limit increases without explicit borrower request.
*   Providing a "cooling-off period" for exiting digital loans.
*   Restrictions on storing biometric data.
*   Limiting Default Loss Guarantee (DLG) cover to 5% of the outstanding portfolio.

The provided documents do not contain specific mandates, priorities, or focus areas for SIDBI (Small Industries Development Bank of India) concerning MSME lending. Therefore, no specific SIDBI priorities can be cited from this evidence.
````

#### Citations

- Digital Lending.pdf

---

### Q179 — Compare our lending footprint with Belagavi DCCB and South Canara DCCB.

- Domain: **Hybrid / Book + Competitive**
- Expected source: `db, competitive`
- Status: **Partial**
- Actual sources: `db, competitive`
- Route match: **Yes**
- Latency: `35.93s`
- Cards: `clarify, brief`

#### Response

````text
The provided indexed passages do not contain specific data regarding the market share or comparative positioning of Belagavi DCCB and South Canara DCCB.

Belagavi DCCB (BDCC) is positioned as a historic institution founded in 1919, with a specific focus on the sugar district economy, having disbursed Rs 50,224 Lakh to sugar factories and Rs 1,22,489 Lakh to farmers via Kissan Credit Card [Belagavi District Central Co-operative Bank].

South Canara DCCB offers a range of loan products including vehicle, solar, and society loans, with a branch network spanning Udupi and Dakshina Kannada districts [South Canara District Central Co-operative Bank]. While South Canara DCCB's balance sheet as of March 2025 shows a capital of Rs 475.99 crore, no corresponding financial figures or market share percentages are available for Belagavi DCCB to allow for a direct comparison [South Canara District Central Co-operative Bank].

**Gap:** No market share percentages or comparative financial metrics exist in the source text to quantify their relative positioning.
````

#### Citations

- Belagavi District Central Co-operative Bank
- South Canara District Central Co-operative Bank

---

### Q180 — Use our product performance and indexed competitor evidence to identify contested borrower segments.

- Domain: **Hybrid / Book + Competitive**
- Expected source: `db, competitive`
- Status: **Partial**
- Actual sources: `db, competitive`
- Route match: **Yes**
- Latency: `45.77s`
- Cards: `brief, refusal`

#### Response

````text
Contested borrower segments include local, agriculture, MSME, and unsecured borrowers, where credit-quality pressure is a shared risk across institutions [Karnataka State Co-operative Apex Bank]. Rival positioning involves comparable banks, NBFCs, and fintech lenders competing on faster approval, clearer pricing, and digital onboarding [Kaujalgi Urban Co-operative Bank].

Cooperative lenders differentiate through local branch presence supporting relationship-led acquisition and agriculture/rural product signals, distinguishing them from purely urban or digital-first lenders [Karnataka State Co-operative Apex Bank]. However, public information for many lenders, including Karnataka State Financial Corporation and Bellary Urban Co-operative Bank, is fragmented, and MSME positioning is often not explicit in extracted text [Karnataka State Financial Corporation]. No specific rates, ticket sizes, or market shares are provided in the evidence. The primary competitive gap lies in the lack of explicit MSME product details and the need to refresh source pages due to changing eligibility rules [Bhatkal Urban Co-operative Bank].

I could not answer that safely from the available data.
````

#### Citations

- Karnataka State Co-operative Apex Bank
- Kaujalgi Urban Co-operative Bank
- Karnataka State Financial Corporation
- Bellary Urban Co-operative Bank
- Bhatkal Urban Co-operative Bank

---

### Q181 — Compare our current asset classifications with the indexed regulatory prudential definitions.

- Domain: **Hybrid / Book + Regulatory**
- Expected source: `db, regulatory`
- Status: **Answered**
- Actual sources: `db, regulatory`
- Route match: **Yes**
- Latency: `61.15s`
- Cards: `chart, brief`

#### Response

````text
Standard has the highest principal outstanding, at ₹194.43 Cr as at 26 Aug 2026, 95% of the total across 5 asset classifications. The figures use these governed definitions: Principal outstanding: principal outstanding from each classified account at the requested snapshot; PAR 30: principal outstanding over 30 DPD divided by classified principal outstanding; PAR 60: principal outstanding over 60 DPD divided by classified principal outstanding; PAR 90: principal outstanding over 90 DPD divided by classified principal outstanding; NPA ratio: nPA-classified principal outstanding divided by classified principal outstanding, grouped by asset classification. Definition of PAR 30, PAR 60, PAR 90, NPA ratio is pending client sign-off.

Based on the provided regulatory passages, the indexed prudential definitions for asset classification for NBFCs are as follows:

**1. Standard Asset**
*   **Definition:** An asset in respect of which no default in repayment of principal or payment of interest is perceived, and which does not disclose any problem or carry more than normal risk attached to the business.
*   **Source:** (Prudential Norms.pdf, p.24)

**2. Sub-standard Asset**
*   **Definition:** An asset which meets either of the following criteria:
    1.  Has been classified as a non-performing asset (NPA) for a period not exceeding 18 months.
    2.  Where the terms of the agreement regarding interest and/or principal have been renegotiated, rescheduled, or restructured after commencement of operations, until the expiry of one year of satisfactory performance under the new terms.
*   **Note:** Infrastructure loans classified as sub-standard must comply with specific provisions in paragraph 17 (not fully detailed in the provided text).
*   **Source:** (Prudential Norms.pdf, p.24)

**3. Doubtful Asset**
*   **Definition:** A term loan, lease asset, hire purchase asset, or any other asset which remains classified as a sub-standard asset for a period exceeding 18 months.
*   **Source:** (Prudential Norms.pdf, p.24)

**4. Loss Asset**
*   **Definition:** An asset which has been identified as a loss asset by the NBFC, its internal or external auditor, or by the Reserve Bank during inspection, to the extent it is not written off by the applicable NBFC.
*   **Source:** (Prudential Norms.pdf, p.24)

**Special Classification Rules:**
*   **Restructured Assets:** If unpaid interest is converted into a Funded Interest Term Loan (FITL), debt, or equity instrument, the new instrument shall be classified in the **same asset classification category** in which the original restructured advance was classified. Any subsequent movement in classification follows the status of the restructured advance. (Prudential Norms.pdf, p.174; p.174)
*   **Commercial Real Estate (CRE):** Loans to builders/developers for commercial real estate (offices, retail, industrial, hotels, etc.) where repayment depends primarily on cash flows from the asset, or loans for the third dwelling unit onwards to an individual, are treated as CRE exposure. CRE-Residential Housing (CRE-RH) is a

Our current asset portfolio is dominated by the Standard classification, which holds the highest principal outstanding at ₹194.43 Cr as of 26 Aug 2026, representing 95% of the total across five asset classifications. This aligns with the indexed regulatory definition of a Standard Asset as one where no default in principal or interest repayment is perceived and which carries no more than normal risk. While the regulatory framework further defines Sub-standard assets as those classified as NPAs for up to 18 months or those with renegotiated terms, our specific metrics for PAR 30, PAR 60, PAR 90, and NPA ratios remain pending client sign-off, preventing a direct quantitative comparison of our performance against these thresholds. Additionally, the regulatory rules for restructured assets and Commercial Real Estate exposures are noted in the findings but lack corresponding data points in our current snapshot to evaluate compliance.
````

#### SQL

````sql
SELECT portfolio."asset_code" AS asset_class,
       SUM(portfolio.principal_outstanding) AS principal_outstanding,
       (100.0 * COALESCE(SUM(portfolio.principal_outstanding) FILTER (WHERE portfolio.is_par30), 0) / NULLIF(SUM(portfolio.principal_outstanding), 0)) AS par_30,
       (100.0 * COALESCE(SUM(portfolio.principal_outstanding) FILTER (WHERE portfolio.is_par60), 0) / NULLIF(SUM(portfolio.principal_outstanding), 0)) AS par_60,
       (100.0 * COALESCE(SUM(portfolio.principal_outstanding) FILTER (WHERE portfolio.is_par90), 0) / NULLIF(SUM(portfolio.principal_outstanding), 0)) AS par_90,
       (100.0 * COALESCE(SUM(portfolio.principal_outstanding) FILTER (WHERE portfolio.is_npa), 0) / NULLIF(SUM(portfolio.principal_outstanding), 0)) AS npa_ratio
FROM gold.portfolio_snapshot_as_of(DATE '2026-08-26') AS portfolio
GROUP BY portfolio."asset_code"
ORDER BY SUM(portfolio.principal_outstanding) DESC NULLS LAST
LIMIT 200
````

#### Citations

- Prudential Norms.pdf

---

### Q182 — Assess our NPA and PAR position in the context of regulatory asset-classification requirements.

- Domain: **Hybrid / Book + Regulatory**
- Expected source: `db, regulatory`
- Status: **Answered**
- Actual sources: `db, regulatory`
- Route match: **Yes**
- Latency: `57.18s`
- Cards: `chart, brief`

#### Response

````text
SMA-2 has the highest par 30, at 100.0% as at 26 Aug 2026. The figures use these governed definitions: PAR 30: principal outstanding over 30 DPD divided by classified principal outstanding; PAR 60: principal outstanding over 60 DPD divided by classified principal outstanding; PAR 90: principal outstanding over 90 DPD divided by classified principal outstanding; NPA ratio: nPA-classified principal outstanding divided by classified principal outstanding, grouped by asset classification. Definition of PAR 30, PAR 60, PAR 90, NPA ratio is pending client sign-off.

Based on the provided regulatory passages, the following norms and thresholds regarding asset classification and related prudential requirements apply to NBFCs:

**1. Asset Classification During Restructuring**
*   **Norm:** While a restructuring proposal is under consideration by the Joint Lenders' Forum (JLF) or Creditors' Debt Restructuring (CDR), the **usual asset classification norms continue to apply**. The re-classification process does not stop merely because a restructuring proposal is under consideration.
*   **Special Benefit (Withdrawn):** Previously, a special asset classification benefit was available for accounts undertaken for restructuring, provided the package was implemented within 90 days of approval. The status as on the date of JLF formation was the relevant date for post-implementation classification.
*   **Threshold/Effective Date:** This special asset classification benefit was **withdrawn for all restructurings with effect from April 1, 2015**, with exceptions for provisions related to changes in Date of Commencement of Commercial Operations (DCCO) for infrastructure and non-infrastructure project loans. (Prudential Norms.pdf, p.208)

**2. Classification of Converted Instruments (Principal to Debt/Equity)**
*   **Norm:** When a part of the outstanding principal is converted into debt or equity instruments as part of restructuring, these new instruments must be classified in the **same asset classification category** in which the restructured advance was originally classified.
*   **Subsequent Movement:** Any future movement in the asset classification of these instruments is determined based on the subsequent asset classification of the restructured advance.
*   **Valuation:**
    *   **Standard Assets:** Valued at market value (if quoted) or break-up value (if not quoted).
    *   **NPA Assets:** Valued at market value (if quoted) or ₹1 (if not quoted).
*   **Provisioning:** Depreciation on these instruments cannot be offset against appreciation in other securities held under 'current investments'. (Prudential Norms.pdf, p.174)

**3. Disclosure and Reporting Norms**
*   **Norm:** NBFCs must disclose asset classification in notes to financial statements distinguishing between:
    *   Performing Assets (Standard Stage 1, Stage 2).
    *   Non-Performing Assets (NPA) categorized as Substandard (Stage 3), Doubtful (Stage 3, split into up to 1 year, 1 to 3 years, and more than 3 years), and Loss (Stage 3).
    *   Other items (

Our SMA-2 portfolio shows a PAR 30 of 100.0% as of 26 Aug 2026, indicating that all classified principal outstanding is overdue by more than 30 days, while regulatory norms require that asset classification continues to apply even while restructuring proposals are under consideration by the Joint Lenders' Forum. Additionally, any principal converted into debt or equity instruments during restructuring must be classified in the same category as the original restructured advance, and NBFCs must disclose Non-Performing Assets as Substandard, Doubtful, or Loss in their financial statements. The provided findings do not include specific figures for PAR 60, PAR 90, or the overall NPA ratio to fully assess the depth of delinquency against these regulatory thresholds.
````

#### SQL

````sql
SELECT portfolio."asset_code" AS asset_class,
       (100.0 * COALESCE(SUM(portfolio.principal_outstanding) FILTER (WHERE portfolio.is_par30), 0) / NULLIF(SUM(portfolio.principal_outstanding), 0)) AS par_30,
       (100.0 * COALESCE(SUM(portfolio.principal_outstanding) FILTER (WHERE portfolio.is_par60), 0) / NULLIF(SUM(portfolio.principal_outstanding), 0)) AS par_60,
       (100.0 * COALESCE(SUM(portfolio.principal_outstanding) FILTER (WHERE portfolio.is_par90), 0) / NULLIF(SUM(portfolio.principal_outstanding), 0)) AS par_90,
       (100.0 * COALESCE(SUM(portfolio.principal_outstanding) FILTER (WHERE portfolio.is_npa), 0) / NULLIF(SUM(portfolio.principal_outstanding), 0)) AS npa_ratio
FROM gold.portfolio_snapshot_as_of(DATE '2026-08-26') AS portfolio
GROUP BY portfolio."asset_code"
ORDER BY (100.0 * COALESCE(SUM(portfolio.principal_outstanding) FILTER (WHERE portfolio.is_par30), 0) / NULLIF(SUM(portfolio.principal_outstanding), 0)) DESC NULLS LAST
LIMIT 200
````

#### Citations

- Prudential Norms.pdf

---

### Q183 — Compare our overdue-account profile with the regulatory fair-practice expectations for recovery.

- Domain: **Hybrid / Book + Regulatory**
- Expected source: `db, regulatory`
- Status: **Answered**
- Actual sources: `db, regulatory`
- Route match: **Yes**
- Latency: `55.24s`
- Cards: `analysis, brief`

#### Response

````text
Nothing is outside its threshold across 6 indicators.

Based on the provided regulatory passages, here is the outline of fair-practice expectations for recovery in overdue accounts, specifically for NBFCs:

**1. Definition and Classification of Overdue Status**
*   **Explicit Rule:** An account is deemed overdue on the day-end process date if full dues are not received by the due date.
    *   *Example:* If the due date is March 31, the account is overdue on March 31. It is tagged as **SMA-1** upon the day-end process on April 30 (30 days continuously overdue). It is tagged as **SMA-2** on May 30, and classified as **NPA** thereafter per extant norms. (Fair Practices Code.pdf, p.130)
*   **Related Principle:** Overdue liabilities must be categorized into specific time buckets (1–7 days and 8–14 days) based on behavioral estimates for reporting purposes. (Fair Practices Code.pdf, p.231)

**2. Governance and Grievance Redressal**
*   **Explicit Rule:** The Board of Directors must establish a grievance redressal mechanism where disputes arising from lending functionaries' decisions are heard and disposed of at the **next higher level**. (Fair Practices Code.pdf, p.52)
*   **Explicit Rule:** The Board must conduct periodic reviews of the Fair Practices Code compliance and the functioning of the grievance mechanism, submitting consolidated reports at regular intervals. (Fair Practices Code.pdf, p.52)
*   **Explicit Rule:** NBFCs covered under the **Reserve Bank – Integrated Ombudsman Scheme, 2021 (RB-IOS)** must comply with its directions. (Fair Practices Code.pdf, p.52)

**3. Communication and Disclosure**
*   **Explicit Rule:** The Fair Practices Code must be communicated to borrowers in their **vernacular language** or a language they understand. (Fair Practices Code.pdf, p.52)
*   **Explicit Rule:** The Code must be published on the NBFC's website for stakeholder information. (Fair Practices Code.pdf, p.52)
*   **Explicit Rule:** Annual Balance Sheets must disclose the number and amount of restructured advances, diminution in fair value, and details of movement of restructured accounts (separately for CDR, SME, and other categories). (Fair Practices Code.pdf, p.177)

**4. Restructuring and Asset Classification**
*   **Explicit Rule:** Once higher provisions on restructured advances revert to normal levels due

Our overdue-account profile currently meets regulatory fair-practice expectations, as the database indicates that nothing is outside its threshold across all six indicators. This aligns with regulatory requirements for overdue classification, which mandate tagging accounts as SMA-1 upon 30 days of continuous overdue status and categorizing liabilities into specific time buckets for reporting. Furthermore, our profile adheres to governance standards requiring Board-level grievance redressal at the next higher level and the communication of the Fair Practices Code in borrowers' vernacular languages. However, the provided findings are incomplete regarding the specific rules for restructuring and asset classification, as the text cuts off before detailing the explicit rule for when higher provisions on restructured advances revert to normal levels.
````

#### Citations

- Fair Practices Code.pdf

---

### Q184 — Relate our agent-sourced loan volumes to regulatory outsourcing oversight requirements.

- Domain: **Hybrid / Book + Regulatory**
- Expected source: `db, regulatory`
- Status: **Partial**
- Actual sources: `db, regulatory`
- Route match: **Yes**
- Latency: `86.35s`
- Cards: `refusal, brief`

#### Response

````text
I could not answer that safely from the available data.

Based on the provided RBI Master Direction excerpts, the regulatory oversight requirements for agents (defined here as service providers in the context of outsourcing) are structured around the Regulated Entity's (RE) ultimate responsibility, contractual governance, and active monitoring.

**1. Ultimate Responsibility and Non-Diminution of Obligations**
The core principle is that outsourcing does not diminish the RE's obligations. The RE's Board and Senior Management remain ultimately responsible for the outsourced activity.
*   **Explicit Rule:** The RE must ensure the service provider employs the "same high standard of care" as if the activity were performed internally.
*   **Explicit Rule:** The RE must ensure the arrangement does not compromise the RE's reputation or impede the RBI's supervisory functions.
*   **Principle:** The RE must maintain the ability to effectively oversee and manage activities regardless of whether the service provider is located in India or abroad.

**2. Contractual Governance and Vendor Controls**
The oversight is codified in a legally binding agreement that must define rights, obligations, and the legal relationship between parties.
*   **Explicit Rule:** The agreement must include clauses making the service provider contractually liable for the performance and risk management practices of its **sub-contractors** (agents in the supply chain).
*   **Explicit Rule:** The RE must secure the right to seek information about third parties engaged by the service provider.
*   **Explicit Rule:** The agreement must require **prior approval/consent** from the RE for the use of any sub-contractors.
*   **Explicit Rule:** The service provider must comply with RBI directions issued in relation to the outsourced activities.
*   **Explicit Rule:** The agreement must include termination rights allowing the RE to orderly transfer the arrangement to another provider.

**3. Monitoring, Auditing, and Risk Management**
The RE is required to actively monitor the service provider's performance and compliance.
*   **Explicit Rule:** The RE must conduct audits to assess the service provider's performance, adequacy of risk management practices, and compliance with laws. The frequency must be risk-based.
*   **Explicit Rule:** The RE must periodically review the financial and operational condition of the service provider to assess its ability to continue meeting obligations.
*   **Explicit Rule:** Reports on monitoring and control activities must be reviewed by Senior Management and escalated to the Board if adverse developments occur.
*   **Principle:** While the RE may rely on third-party certifications, this does not absolve the RE of its responsibility to ensure assurance on controls and data security at the provider's end.

**4. Customer Protection and Grievance Redressal
````

#### Citations

- outsourcing.pdf

---

### Q185 — Compare our digital-loan portfolio indicators with regulatory digital-lending obligations.

- Domain: **Hybrid / Book + Regulatory**
- Expected source: `db, regulatory`
- Status: **Partial**
- Actual sources: `db, regulatory`
- Route match: **Yes**
- Latency: `90.29s`
- Cards: `refusal, brief`

#### Response

````text
I could not answer that safely from the available data.

Based on the provided regulatory passages, the following digital lending obligations and reporting requirements apply to RBI-regulated entities (REs) and Lending Service Providers (LSPs):

**1. Consent and Data Privacy Obligations**
*   **Explicit Consent:** REs must obtain explicit consent from borrowers before sharing their personal information with any third party.
*   **Privacy Policy:** Both REs and LSPs must maintain a comprehensive privacy policy compliant with applicable laws.
*   **Biometric Data Restriction:** Neither the RE nor the LSP is permitted to store or collect biometric data.

**2. Operational and Process Obligations**
*   **Enhanced Due Diligence:** REs must conduct enhanced due diligence before entering into an agreement with an LSP for digital lending.
*   **Unbiased Content Display:** The LSP must provide a digital view of loan offers that is unbiased and objective. It shall not directly or indirectly promote or push a product of a particular RE.
*   **Credit Limit Increases:** There must be no automatic increase in credit limits unless an explicit request is received, evaluated, and recorded from the borrower.
*   **Cooling-off Period:** Borrowers must be given the option to exit a digital loan by paying the principal and the proportionate Annual Percentage Rate (APR) without any penalty during an initial "cooling-off period."
*   **Grievance Redressal:** The RE and the LSP (if they have an interface with the borrower) must designate nodal grievance redressal officers to handle complaints related to digital lending.

**3. Financial Guarantee Obligations**
*   **Default Loss Guarantee (DLG) Cap:** REs must ensure that the total amount of DLG cover on any outstanding portfolio specified upfront does not exceed 5% of the total amount disbursed from that loan portfolio at any given time.

**Applicability Note:**
These rules apply to RBI-regulated entities and lending service arrangements, including NBFC digital lending operations where applicable. While the text specifies that REs must conduct enhanced due diligence before agreements with LSPs, the specific applicability of these directions to a particular entity or specific lending arrangement must be confirmed against the full RBI Digital Lending Directions, 2025.

*(Source: Digital Lending.pdf p.1)*
````

#### Citations

- Digital Lending.pdf

---

### Q186 — Assess our concentration by borrower and scheme against regulatory concentration-risk principles.

- Domain: **Hybrid / Book + Regulatory**
- Expected source: `db, regulatory`
- Status: **Answered**
- Actual sources: `db, regulatory`
- Route match: **Yes**
- Latency: `59.59s`
- Cards: `chart, brief`

#### Response

````text
ASHWINI  ASHWINI has the highest principal outstanding, at ₹22.27 L as at 26 Aug 2026, 1% of the total across 200 borrowers. This measures principal outstanding from each classified account at the requested snapshot, grouped by borrower and scheme.

Based on the provided regulatory passages, here are the concentration-risk principles and limits for NBFCs, distinguished by their nature and applicability:

### 1. Explicit Regulatory Limits (Hard Caps)
These are specific numerical thresholds that NBFCs must not exceed.

*   **General NBFCs (excluding NBFC-IFC):**
    *   **Single Party:** Exposure (credit + investment) shall not exceed **25% of Tier 1 capital**.
    *   **Single Group:** Exposure shall not exceed **40% of Tier 1 capital**.
    *   *Principle:* An NBFC may exceed these limits by **5% (single party)** and **10% (single group)** if the additional exposure is specifically for infrastructure loans/investments.
    *   *(Prudential Norms.pdf, p.91)*

*   **NBFC-IFC (Infrastructure Finance Company):**
    *   **Single Party:** Exposure shall not exceed **30% of Tier 1 capital**.
    *   **Single Group:** Exposure shall not exceed **50% of Tier 1 capital**.
    *   *(Prudential Norms.pdf, p.91)*

*   **Large Exposure Framework (LEF):**
    *   **Principle:** NBFCs must identify large exposures, refine criteria for grouping connected counterparties, and adhere to reporting norms to address credit risk concentration.
    *   **Scope:** Applies to both solo and consolidated (group) levels and includes on- and off-balance sheet exposures.
    *   *(Prudential Norms.pdf, p.108)*

### 2. Related Principles and Frameworks
These are structural requirements and policy mandates rather than fixed numerical caps.

*   **Policy Formulation:** Every NBFC must formulate a specific policy regarding exposures to a single party or a single group of parties.
    *   *(Prudential Norms.pdf, p.91)*
*   **Liquidity Risk Management:**
    *   **Principle:** NBFCs with an asset size of ₹100 crore and above (excluding Type I, NOFHCs, and SPDs) must adhere to a Liquidity Risk Management Framework. This includes maintaining sufficient liquidity with a cushion of unencumbered, high-quality liquid assets to withstand stress events.
    *   **Applicability:** Mandatory for non-deposit taking NBFCs with assets ≥ ₹100 crore; encouraged voluntarily for others.
    *   *(Prudential Norms.pdf, p.215; p.

Our concentration assessment reveals that the borrower ASHWINI holds the highest principal outstanding at ₹22.27 L, representing 1% of the total portfolio across 200 borrowers as of 26 Aug 2026. While this specific exposure is well below the explicit regulatory hard caps for single-party exposure (25% of Tier 1 capital for general NBFCs or 30% for NBFC-IFCs), the findings do not disclose the bank's Tier 1 capital figure or the specific regulatory classification of the entity to definitively confirm compliance with the capital-based limits. Additionally, the data provided does not include information on connected groups or off-balance sheet items required for a full Large Exposure Framework analysis.
````

#### SQL

````sql
SELECT lam."customer_name" AS borrower,
       lam."scheme_code" AS scheme,
       SUM(portfolio.principal_outstanding) AS principal_outstanding
FROM gold.portfolio_snapshot_as_of(DATE '2026-08-26') AS portfolio
     JOIN gold.loan_account_master AS lam ON portfolio."entity_num" = lam."entity_num" AND portfolio."loan_account_number" = lam."loan_account_number"
GROUP BY lam."customer_name", lam."scheme_code"
ORDER BY SUM(portfolio.principal_outstanding) DESC NULLS LAST
LIMIT 200
````

#### Citations

- Prudential Norms.pdf

---

### Q187 — Use our repayment performance to explain which regulatory prudential risks deserve attention.

- Domain: **Hybrid / Book + Regulatory**
- Expected source: `db, regulatory`
- Status: **Answered**
- Actual sources: `db, regulatory`
- Route match: **Yes**
- Latency: `54.57s`
- Cards: `analysis, brief`

#### Response

````text
Nothing is outside its threshold across 6 indicators.

Based on the provided regulatory passages, the relevant prudential norms and risk requirements for NBFCs are categorized below. Please note that specific applicability (e.g., whether an entity is a deposit-taking NBFC, Core Investment Company, or NOFHC) must be confirmed against the entity's specific classification, as exemptions and thresholds vary by category.

### 1. Capital Adequacy and Risk-Weighted Assets
*   **Minimum Capital Ratio:** NBFCs must maintain a minimum capital ratio consisting of Tier I and Tier II capital of not less than **15%** of aggregate risk-weighted assets (on-balance sheet) and risk-adjusted value of off-balance sheet items. (Prudential Norms.pdf, p.72)
*   **Tier I Capital Requirement:** For most NBFCs (excluding NBFC-MFI and those primarily engaged in lending against gold jewellery), Tier I capital must be a minimum of **10%** at any point in time. (Prudential Norms.pdf, p.72)
*   **Perpetual Debt Instruments (PDI):** NBFCs (except NBFCs-D) may augment capital via PDI, eligible for inclusion as Tier I capital up to **15%** of total Tier I capital as of March 31 of the previous accounting year. (Prudential Norms.pdf, p.72)
*   **ICAAP (Internal Capital Adequacy Assessment Process):** NBFCs must conduct a thorough internal assessment of capital needs commensurate with business risks (credit, market, operational, and residual risks). The methodology must be proportionate to the scale and complexity of operations and approved by the Board. (Prudential Norms.pdf, p.72)
*   **Specific Threshold for High-Loan Concentration:** For NBFCs where loans comprising **50% or more** of financial assets are of a specific type, Tier I capital must be a minimum of **12%** (as per paragraph 9.2 of the Directions). (Prudential Norms.pdf, p.72)

### 2. Liquidity Risk Management
*   **Applicability:** Mandatory for Non-deposit taking NBFCs with asset size of **₹100 crore and above**, Core Investment Companies (CICs), and all deposit-taking NBFCs. Other NBFCs are encouraged to adopt these guidelines voluntarily. (Prudential Norms.pdf, p.215)
*   **Framework Requirements:** The Board must frame a framework ensuring sufficient liquidity, including a cushion of unencumbered, high-quality liquid assets

Our repayment performance indicates that nothing is currently outside its threshold across six indicators, suggesting immediate compliance with baseline metrics; however, the provided findings do not specify the exact nature of these six indicators or their current values relative to the regulatory norms. Consequently, while we can confirm general adherence, we cannot yet pinpoint which specific prudential risks—such as the 15% minimum capital ratio or the 10% Tier I capital requirement for most NBFCs—deserve heightened attention based on our actual performance data. To fully explain which risks require focus, we need the specific breakdown of the six indicators to compare them directly against the capital adequacy and liquidity thresholds outlined in the regulatory passages. Without this granular data, we must assume current stability while preparing for potential stress in areas like high-loan concentration where Tier I capital must rise to 12%.
````

#### Citations

- Prudential Norms.pdf

---

### Q188 — Compare our branch and agent structure with regulatory governance and control expectations.

- Domain: **Hybrid / Book + Regulatory**
- Expected source: `db, regulatory`
- Status: **Partial**
- Actual sources: `db, regulatory`
- Route match: **Yes**
- Latency: `92.67s`
- Cards: `chart, brief`

#### Response

````text
The query returned 5,000 row(s) covering branch code, branch name, branch status, agent code, agent name. Current active branches with their assigned agent details. This uses a validated read-only generated query rather than a reviewed metric; check Source details before relying on it.

Based on the provided regulatory passages, the following outlines the governance and control expectations for branches and agents within the NBFC framework:

**1. Explicit Rules on Branch and Agent Governance**
The provided documents **do not contain explicit rules** detailing specific governance or control expectations exclusively for "branches" or "agents" (e.g., specific reporting lines, local compliance mandates, or agent-specific conduct codes).

**2. Related Principles and Board Oversight**
While specific branch/agent rules are absent, the documents establish a related principle of **Board-level accountability** that implicitly governs all operational units, including branches and agents. The Board is expected to oversee:
*   **Constitution and Delegation:** The constitution, delegation of authority, and terms of reference of various committees constituted by the Board (Governance.pdf, p.319).
*   **Senior Executive Authority:** The appointments of Senior Executives and their authority (Governance.pdf, p.319).
*   **Policy Frameworks:** The formulation of rate policies and procedures (Governance.pdf, p.319).
*   **Risk and Conduct:** Insider dealing restrictions and overall risk management systems (Governance.pdf, p.319; Governance.pdf, p.133).

**3. Applicability Confirmation Required**
Because the text does not explicitly define branch or agent-specific controls, **entity-specific applicability must be confirmed** against the following criteria found in the documents:
*   **Regulatory Layer:** The specific layer (Base, Middle, Upper, or Top) the NBFC occupies determines the intensity of governance requirements (Governance.pdf, p.5; p.6). For instance, NBFCs in the Upper Layer face enhanced regulatory requirements, while Base Layer entities have different scopes (Governance.pdf, p.5).
*   **Activity Type:** Specific activities (e.g., NBFC-P2P, NBFC-AA, Deposit Taking) dictate whether an entity falls into the Base or Middle/Upper layer, which influences the governance framework applied (Governance.pdf, p.6).
*   **Scale Based Regulation:** The entity's asset size and perceived riskiness determine its layer placement, which in turn dictates the capital and governance norms applicable to its operations (Governance.pdf, p.5).

**Conclusion**
The provided evidence mandates that the Board holds ultimate accountability for policies, delegations, and senior executive authority that cover the entire organization. However, it does not explicitly list distinct "branch and agent" governance rules; therefore, the specific controls applicable to these units must be derived from the entity's assigned regulatory layer and activity category as defined in

Our current data reflects 5,000 active branches and their assigned agents, though this figure relies on a validated read-only query rather than a reviewed metric. While regulatory documents do not contain explicit rules detailing specific governance or control expectations exclusively for branches or agents, they mandate that the Board holds ultimate accountability for the constitution, delegation of authority, and senior executive authority covering the entire organization. Consequently, the specific controls applicable to these units must be derived from the entity's assigned regulatory layer and activity category, as the intensity of governance requirements varies based on whether the NBFC occupies the Base, Middle, or Upper layer. The evidence is incomplete regarding direct branch-specific mandates, as the provided text requires confirmation of entity-specific applicability against the defined regulatory layers and activity types to fully map the structure to expectations.
````

#### SQL

````sql
SELECT
  bm.branch_code,
  bm.branch_name,
  bm.branch_status,
  lra.agent_code,
  am.agent_name,
  am.designation
FROM gold.branch_master AS bm
LEFT JOIN gold.loan_reporting_attributes AS lra
  ON bm.branch_code = lra.posting_branch_code
LEFT JOIN gold.agent_master AS am
  ON lra.agent_code = am.agent_code
WHERE
  bm.branch_status <> 'CLOSED'
LIMIT 5000
````

#### Citations

- Governance.pdf

---

### Q189 — Relate our customer KYC coverage to the indexed regulatory KYC and AML obligations.

- Domain: **Hybrid / Book + Regulatory**
- Expected source: `db, regulatory`
- Status: **Partial**
- Actual sources: `db, regulatory`
- Route match: **Yes**
- Latency: `82.01s`
- Cards: `error, brief`

#### Response

````text
The loan book could not answer that.

Based on the provided regulatory passages, the indexed KYC and AML obligations for the bank (referred to as REs or Banks) are summarized below. Please note that while the text outlines specific operational mandates, **entity-specific applicability must be confirmed** regarding the exact scope of "NBFC customer due diligence" and "periodic KYC updation" as these terms appear in the applicability metadata but are not explicitly detailed as distinct sections in the provided evidence snippets (which focus on hiring, correspondent banking, and specific transaction thresholds).

### 1. Employee Screening and Training
*   **Explicit Rule:** The bank must implement an adequate screening mechanism as an integral part of the personnel recruitment/hiring process.
*   **Explicit Rule:** An ongoing employee training program must be established, with differentiated focus for front-line staff, compliance staff, and staff dealing with new customers. Front desk staff must be specially trained to handle issues arising from a lack of customer education.
*   **Explicit Rule:** The audit function must be properly staffed with persons adequately trained in AML/CFT policies, regulations, and related issues.
*   *(Source: KYC AML.pdf, p.42)*

### 2. KYC Compliance for Authorized Personnel and Agents
*   **Explicit Rule:** Persons authorized by the bank (including brokers/agents) for collecting deposits must be fully compliant with KYC guidelines applicable to the bank.
*   **Explicit Rule:** All information regarding these authorized persons must be made available to the Reserve Bank of India (RBI) for verification.
*   **Explicit Rule:** Books of accounts relating to brokerage functions of authorized persons must be available for audit and inspection whenever required.
*   *(Source: KYC AML.pdf, p.42)*

### 3. Product and Technology Due Diligence
*   **Explicit Rule:** Appropriate KYC procedures must be applied before introducing new products, services, or technologies.
*   **Explicit Rule:** Agents used for marketing credit cards must be subjected to due diligence and KYC measures.
*   *(Source: KYC AML.pdf, p.38)*

### 4. Correspondent Banking Relationships
*   **Explicit Rule:** The bank must have a Board-approved policy to lay down parameters for approving correspondent banking relationships.
*   **Explicit Rule:** Sufficient information must be gathered regarding the nature of business, management, AML/CFT compliance, and the regulatory framework of the correspondent bank's home country.
*   **Explicit Rule:** Post-facto Board approval is required for proposals approved by the committee.
*   **Explicit Rule:** Responsibilities must be clearly
````

#### Citations

- KYC AML.pdf

---

### Q190 — Which regulatory themes are most relevant to the current risk profile of our loan book?

- Domain: **Hybrid / Book + Regulatory**
- Expected source: `db, regulatory`
- Status: **Partial**
- Actual sources: `db, regulatory`
- Route match: **Yes**
- Latency: `52.84s`
- Cards: `analysis, brief`

#### Response

````text
Nothing is outside its threshold across 6 indicators.

Based strictly on the provided regulatory passages and metadata, **no explicit regulatory requirements or risk norms applicable to the bank can be outlined.**

The provided evidence consists exclusively of a **registry listing** of Non-Banking Financial Companies (NBFCs) and ARC Registrars (ARCs) registered with the RBI as of March 31, 2026. The documents contain entity-specific data such as names, addresses, CINs, and classification layers (e.g., Base, Middle), but they **do not contain**:
*   Specific regulatory requirements or risk norms.
*   Thresholds for lending, capital adequacy, or asset quality.
*   Operational guidelines for banks or NBFCs.

**Determination of Applicability:**
*   **Explicit Rule:** None found in the text.
*   **Related Principle:** The documents imply that entities listed are registered with the RBI, but the text does not define the obligations attached to this registration.
*   **Entity-Specific Applicability Confirmation:** Required. The provided text lists various NBFCs (e.g., LIC Housing Finance Limited, Light Micro Finance Private Limited) but does not identify the specific "bank" in your question. Furthermore, the text does not link any specific regulatory norm to any listed entity.

**Conclusion:**
It is impossible to answer the question regarding "current regulatory requirements and risk norms" using only the supplied evidence. The evidence serves as a directory of registered entities rather than a source of regulatory rules. To determine the applicable norms, you must consult the specific Master Directions (e.g., Master Direction on Prudential Norms on Income Recognition, Asset Classification and Provisioning pertaining to Advances) or the specific Master Direction applicable to Banks/NBFCs, which are not included in the provided passages.

The provided evidence indicates that nothing is currently outside its threshold across six specific indicators, yet it explicitly fails to outline any explicit regulatory requirements or risk norms applicable to the bank. The available data consists solely of a registry listing of Non-Banking Financial Companies and ARC Registrars, which contains entity details but lacks specific rules regarding lending thresholds, capital adequacy, or asset quality. Consequently, it is impossible to identify the most relevant regulatory themes for the current loan book risk profile because the text does not define the obligations attached to registration or link specific norms to the bank's operations. To determine the applicable norms, you must consult external Master Directions, as the supplied evidence serves only as a directory of registered entities rather than a source of regulatory rules.
````

#### Citations

- List_of_NBFCs_and_ARCs_registered_with_the_RBI.pdf

---

### Q191 — How do current macro credit conditions affect the positioning of Karnataka MSME competitors?

- Domain: **Hybrid / Macro + Competitive**
- Expected source: `macro, competitive`
- Status: **Partial**
- Actual sources: `macro`
- Route match: **No**
- Latency: `12.28s`
- Cards: `brief`

#### Response

````text
The provided context does not contain information regarding current macro credit conditions in India or Karnataka. It exclusively details fiscal parameters such as revenue deficits, fiscal deficits, and state tax revenue ratios for the 2019–2024 period, noting that Karnataka maintained a revenue surplus until the onset of the pandemic and recorded the lowest fiscal deficit (2.50%) among southern states in 2023–24 [karnataka_des, p.68]. No data on credit growth, lending rates, or non-performing assets is available in the text.
````

#### Citations

- karnataka_des

---

### Q192 — Compare the macro outlook for MSMEs with the products emphasized by indexed competitors.

- Domain: **Hybrid / Macro + Competitive**
- Expected source: `macro, competitive`
- Status: **Answered**
- Actual sources: `macro`
- Route match: **No**
- Latency: `14.75s`
- Cards: `brief`

#### Response

````text
As of November 2025, bank credit to the MSME sector increased by 21.8% year-on-year, with micro and small enterprises seeing a 24.6% rise, indicating robust momentum [economic_survey, p.145]. This growth is supported by regulatory measures like revised gold pledge guidelines and Union Budget initiatives enhancing guarantee covers and credit card access [economic_survey, p.145]. The broader commercial sector resource flow reached ₹30.8 lakh crore in April-December 2025, up 44.7% YoY, while non-food bank credit grew 58.6% [economic_survey, p.145]. Although the context highlights strong credit expansion and improved flow from non-bank sources, it does not explicitly detail specific remaining credit gaps or negative trends within the MSME sector, focusing instead on the positive trajectory and policy drivers.
````

#### Citations

- economic_survey

---

### Q193 — Which competitor strategies appear best aligned with Karnataka's economic outlook?

- Domain: **Hybrid / Macro + Competitive**
- Expected source: `macro, competitive`
- Status: **Answered**
- Actual sources: `macro`
- Route match: **No**
- Latency: `19.04s`
- Cards: `brief`

#### Response

````text
Karnataka's economic outlook for 2023-24 shows robust growth, with Gross State Domestic Product (GSDP) estimated at Rs.25,00,733 crore, representing a 10.2% growth at current prices and 6.6% at constant (2011-12) prices [karnataka_des, p.35]. While the state's constant price growth of 6.6% is slightly lower than the national GDP growth of 7.3% for the same period, the current price growth significantly outpaces the national rate of 8.9% [karnataka_des, p.35]. Karnataka's GSDP share in All India GDP is projected at 8.4% for 2023-24 [karnataka_des, p.35]. Historically, the state's current price growth has consistently exceeded the national average, except in 2017-18 and 2022-23, whereas at constant prices, it lagged only in 2014-15, 2018-19, and 2023-24 [karnataka_des, p.35].
````

#### Citations

- karnataka_des

---

### Q194 — How could the monetary-policy outlook interact with regulatory prudential requirements for lenders?

- Domain: **Hybrid / Macro + Regulatory**
- Expected source: `macro, regulatory`
- Status: **Answered**
- Actual sources: `regulatory`
- Route match: **No**
- Latency: `35.73s`
- Cards: `brief`

#### Response

````text
Based on the provided regulatory passages, the relevant prudential requirements for lenders (specifically NBFCs) are as follows:

**1. Capital Adequacy and Composition**
*   **Minimum Capital Ratio:** NBFCs must maintain a minimum capital ratio consisting of Tier 1 and Tier 2 capital of not less than **15%** of aggregate risk-weighted assets (on-balance sheet) and risk-adjusted value of off-balance sheet items (Prudential Norms.pdf, p.72).
*   **Tier 1 Capital Floor:** For most NBFCs, Tier 1 capital must be at least **10%** of risk-weighted assets.
    *   *Exception:* NBFCs primarily engaged in lending against gold jewellery (where such loans comprise >50% of financial assets) must maintain a minimum Tier 1 capital of **12%** (Prudential Norms.pdf, p.72; p.21).
    *   *Exception:* NBFC-MFIs and NBFCs primarily engaged in gold jewellery lending are excluded from the standard 10% Tier 1 rule in the general clause, though the gold jewellery category has its own 12% rule (Prudential Norms.pdf, p.72).
*   **Perpetual Debt Instruments (PDI):** NBFCs (except NBFCs-D) may augment capital via PDIs, eligible for inclusion as Tier 1 capital up to **15%** of total Tier 1 capital as of March 31 of the previous accounting year (Prudential Norms.pdf, p.72).
*   **Leverage Ratio:** The leverage ratio (Total Outside Liabilities / Owned Fund) for NBFCs (excluding NBFC-MFIs, NBFCs-ML, and others) shall not exceed **7** (Prudential Norms.pdf, p.21).

**2. Internal Risk Assessment**
*   **ICAAP:** NBFCs must conduct an Internal Capital Adequacy Assessment Process (ICAAP) to assess capital needs commensurate with business risks (credit, market, operational, and residual risks). The methodology should be proportionate to the scale and complexity of operations and approved by the Board (Prudential Norms.pdf, p.72).

**3. Asset Classification and Provisioning**
*   **General Norms:** Loans must be subject to applicable asset classification, income recognition, and provisioning norms (Prudential Norms.pdf, p.120).
*   **NBFC-MFI Specifics:** NBFC-MFIs
````

#### Citations

- Prudential Norms.pdf

---

### Q195 — Relate the MSME macro outlook to applicable regulatory lending-conduct requirements.

- Domain: **Hybrid / Macro + Regulatory**
- Expected source: `macro, regulatory`
- Status: **Partial**
- Actual sources: `macro`
- Route match: **No**
- Latency: `11.37s`
- Cards: `brief`

#### Response

````text
The provided context does not contain specific data on the current MSME sector outlook or credit conditions for the Karnataka co-operative bank. It only offers general background stating that the MSME sector contributes around 30% of India's GDP and over 45% of exports [msme, p.7], along with the Ministry's vision for sustainable development and objectives to address challenges like access to credit and finance [msme, p.7]. No periodic statistics or daily measures regarding current credit availability or sectoral performance trends are included in the text.
````

#### Citations

- msme

---

### Q196 — Compare indexed digital-lending competitor capabilities with regulatory digital-lending requirements.

- Domain: **Hybrid / Competitive + Regulatory**
- Expected source: `competitive, regulatory`
- Status: **Answered**
- Actual sources: `competitive`
- Route match: **No**
- Latency: `18.42s`
- Cards: `brief`

#### Response

````text
Indexed digital-lending capabilities across Karnataka co-operative lenders and competitors like Kinara Capital, SIDBI, and NBFCs show similar structural strengths: established official web presences with crawlable information, visible product details, and digital/payment channels improving access [Karnataka State Co-operative Apex Bank]. All institutions leverage local branch networks for relationship-led distribution and highlight MSME or small-business relevance [Bhatkal Urban Co-operative Bank]. However, a critical gap exists: public information is often fragmented, requiring manual validation, and specific financial figures, ticket sizes, or exact turnaround times are absent from the extracted text [Bellary Urban Co-operative Bank]. Competitors compete on faster approval and clearer pricing, while co-ops differentiate via agriculture/rural product signals [Karnataka State Co-operative Apex Bank]. No specific rates or market shares are provided in the evidence.
````

#### Citations

- Karnataka State Co-operative Apex Bank
- Bellary Urban Co-operative Bank
- Karnataka State Financial Corporation
- Kaujalgi Urban Co-operative Bank
- Bhatkal Urban Co-operative Bank

---

### Q197 — Compare our MSME growth with macro credit conditions and indexed competitor positioning.

- Domain: **Hybrid / Book + Macro + Competitive**
- Expected source: `db, macro, competitive`
- Status: **Partial**
- Actual sources: `db, macro, competitive`
- Route match: **Yes**
- Latency: `76.18s`
- Cards: `brief, brief, refusal`

#### Response

````text
Current macro credit conditions show robust momentum in the MSME sector, with bank credit rising 21.8% year-on-year in November 2025 compared to 13% in the prior year [economic_survey, p.145]. Specifically, credit to micro and small enterprises surged 24.6% in November 2025, up from 10.2% previously [economic_survey, p.145]. This growth is supported by regulatory measures like revised gold pledge guidelines and Union Budget enhancements for credit availability [economic_survey, p.145]. Broader commercial sector resource flow also strengthened, reaching ₹30.8 lakh crore in April–December 2025, a 44.7% increase over the same period last year [economic_survey, p.145]. Additionally, non-food bank credit grew 58.6% year-on-year as of December 2025 [economic_survey, p.145].

Competitors position in the MSME market through a mix of relationship-led local presence and digital innovation. NBFCs like Kinara Capital lead in product flexibility, offering collateral-free loans and specialized schemes for women-owned businesses, noting they are "more proactive in innovating financial products than banks" [Kinara Capital]. Conversely, Karnataka co-operative lenders (e.g., Bhatkal, Belgaum, Apex Bank) leverage their "Local, branch, co-operative, or rural presence" to support relationship-led acquisition and servicing [Bhatkal Urban Co-operative Bank].

While co-operatives emphasize local distribution and agriculture/rural differentiation, they face threats from "banks, NBFCs, fintech lenders, and digital-first MSME platforms" that compete on "faster approval, clearer pricing, and digital onboarding" [Karnataka State Co-operative Apex Bank]. Most co-operative profiles lack explicit MSME positioning details in public web crawls, creating a data gap regarding their specific product rates and eligibility rules [Karnataka State Financial Corporation]. Opportunities for all lie in packaging products with clearer eligibility and using digital rails to grow working-capital relationships [Belagavi District Central Co-operative Bank].

I could not answer that safely from the available data.

Our MSME sector is experiencing robust momentum, with bank credit rising 21.8% year-on-year in November 2025, significantly outpacing the 13% growth of the prior year and driving a 24.6% surge specifically in micro and small enterprise credit. This expansion is underpinned by broader commercial resource flows that increased 44.7% to ₹30.8 lakh crore and non-food bank credit growth of 58.6% as of December 2025. In contrast to this macro strength, competitor positioning reveals a strategic divergence where NBFCs like Kinara Capital lead in product flexibility and digital innovation, while co-operative lenders rely on local presence but face threats from faster, digital-first platforms. Although opportunities exist for all players to enhance digital onboarding and product clarity, the provided findings lack specific data points regarding our bank's exact indexed competitor positioning metrics to allow for a direct quantitative comparison.
````

#### Citations

- economic_survey
- Karnataka State Co-operative Apex Bank
- Kinara Capital
- Bhatkal Urban Co-operative Bank
- Kaujalgi Urban Co-operative Bank
- Belgaum Industrial Co-operative Bank
- Karnataka State Financial Corporation

---

### Q198 — Assess our portfolio-risk trend using macro conditions and regulatory prudential expectations.

- Domain: **Hybrid / Book + Macro + Regulatory**
- Expected source: `db, macro, regulatory`
- Status: **Answered**
- Actual sources: `db, macro, regulatory`
- Route match: **Yes**
- Latency: `97.08s`
- Cards: `analysis, brief, brief`

#### Response

````text
Nothing is outside its threshold across 6 indicators.

Relevant macroeconomic conditions affecting risk include a globally uncertain environment driven by geopolitical tensions, trade disruptions, and fragmented supply chains, which pose external vulnerabilities despite near-term resilience. Domestically, while India's FY26 real GDP growth is estimated at 7.4% [economic_survey, p.52], supported by strong private consumption and capital formation, risks persist from elevated fiscal pressures and structural constraints in agriculture. Inflation has moderated, and financial sector balance sheets remain healthy, yet the outlook for FY27 depends on sustaining these domestic drivers against evolving external conditions. The medium-term growth potential has strengthened to 7% [economic_survey, p.52], but reliance on economic policy instruments for strategic purposes and the need to balance growth with fiscal consolidation remain critical factors influencing economic stability and risk profiles.

Based on the provided regulatory passages, the applicable prudential norms and expectations for NBFCs regarding restructuring, asset classification, and provisioning are outlined below. Please note that specific thresholds (e.g., exact capital ratios) and effective dates for the broader framework are referenced in the metadata but detailed values are not present in the provided text excerpts.

### 1. Eligibility and Scope of Restructuring
*   **Applicable Categories:** NBFCs may restructure accounts classified under **'Standard', 'Substandard', and 'Doubtful'** categories.
*   **Prohibition on Retrospective Effect:** NBFCs **cannot** reschedule, restructure, or renegotiate borrowal accounts with retrospective effect.
*   **Continuity of Classification:** While a restructuring proposal is under consideration, the **usual asset classification norms must continue to apply**. The process of re-classification cannot stop merely because a proposal is pending.
*   **Scope:** These norms apply to all restructurings, including those under the **CDR (Corporate Debt Restructuring) Mechanism**.

### 2. Asset Classification Norms During and After Restructuring
*   **Status During Consideration:** An asset undergoing restructuring retains its classification status as of the date the restructuring proposal is under consideration.
*   **Post-Restructuring Classification:**
    *   An asset that has been renegotiated or rescheduled shall be classified as **Sub-standard** or shall **continue to remain** in the category it held prior to the action (e.g., if it was Doubtful, it remains Doubtful; if Loss, it remains Loss).
    *   Necessary provisions must be made as applicable to such assets until they are upgraded.
*   **Special Benefit (Historical Context):** Previously, a special asset classification benefit was available for accounts undertaken for restructuring under specific guidelines, provided the package was implemented within **90 days** from the date of approval. The status as on the date of the Joint Lenders' Forum (JLF) formation was the relevant date for this decision.
    *   *Note:* The text indicates this special benefit was withdrawn for most restructurings with effect from **April 1, 2015**, with exceptions for changes in the Date of Commencement of Commercial Operations (DCCO) for infrastructure and non-infrastructure project loans.

### 3. Provisioning Norms
*   **Separation of Income and Provisioning:** Income recognition and provisioning against Non-Performing Assets (NPAs) are distinct aspects. Provisions must be made on the **total outstanding balances** (including the depreciated book value

Our portfolio risk assessment indicates that no indicators currently exceed their thresholds, yet this stability exists against a backdrop of global uncertainty driven by geopolitical tensions and fragmented supply chains. Domestically, while India's FY26 GDP growth is estimated at 7.4% and medium-term potential has strengthened to 7%, risks persist from elevated fiscal pressures and structural constraints in agriculture that could influence future risk profiles. Concurrently, regulatory prudential expectations for NBFCs mandate strict adherence to asset classification norms during restructuring, prohibiting retrospective rescheduling and requiring continued classification under usual norms until re-classification is finalized. Although specific capital ratio thresholds are referenced in metadata, the detailed values required to quantify the exact regulatory buffer are not present in the provided text excerpts.
````

#### Citations

- economic_survey
- Prudential Norms.pdf

---

### Q199 — Compare our digital-lending position with competitor capabilities and regulatory requirements.

- Domain: **Hybrid / Book + Competitive + Regulatory**
- Expected source: `db, competitive, regulatory`
- Status: **Partial**
- Actual sources: `db, competitive, regulatory`
- Route match: **Yes**
- Latency: `97.38s`
- Cards: `brief, refusal, brief`

#### Response

````text
Competitors like banks, NBFCs, and fintechs position themselves on faster approval, clearer pricing, and digital onboarding [Karnataka State Co-operative Apex Bank]. Cooperative lenders counter with local branch presence for relationship-led acquisition and servicing, alongside MSME and agriculture/rural product signals that differentiate them from purely digital-first lenders [Kaujalgi Urban Co-operative Bank].

Most institutions, including Bellary Urban Co-operative Bank and Belagavi District Central Co-operative Bank, maintain established web presences with visible product information and digital payment channels [Bellary Urban Co-operative Bank]. However, public information is often fragmented, requiring manual validation, and MSME positioning is frequently not explicit in extracted text [Bellary Urban Co-operative Bank].

While many cooperatives highlight digital rails for working-capital and enterprise finance, specific digital capabilities like application journey speed or exact turnaround times are absent from the provided evidence. Similarly, precise market shares and financial figures are not available in the indexed passages [Karnataka State Co-operative Apex Bank].

I could not answer that safely from the available data.

Based on the provided regulatory passages, the following requirements apply to digital lending for RBI-regulated entities (REs) and Lending Service Providers (LSPs):

**1. Consent and Data Sharing**
*   **Explicit Consent:** Explicit consent must be obtained from the borrower before sharing their personal information with any third party. (Digital Lending.pdf, p.1)

**2. Operational Process and Technology**
*   **Definition:** Digital lending is defined as a remote and automated lending process utilizing seamless digital technologies for customer acquisition, credit assessment, loan approval, disbursement, recovery, and customer service. (Digital Lending.pdf, p.1)
*   **Enhanced Due Diligence:** REs must conduct enhanced due diligence before entering into an agreement with an LSP for digital lending. (Digital Lending.pdf, p.1)

**3. Lending Service Provider (LSP) Conduct**
*   **Digital View:** The LSP must provide a digital view of all loan offers matching the borrower's request on Digital Lending Apps (DLAs). (Digital Lending.pdf, p.1)
*   **Unbiased Content:** Content displayed by the LSP must be unbiased and objective; it shall not directly or indirectly promote or push a product of a particular RE. (Digital Lending.pdf, p.1)
*   **Credit Limit Increases:** There must be no automatic increase in credit limit unless an explicit request is received, evaluated, and kept on record from the borrower. (Digital Lending.pdf, p.1)

**4. Borrower Protections**
*   **Cooling-off Period:** Borrowers must be given the option to exit a digital loan by paying the principal and the proportionate Annual Percentage Rate (APR) without any penalty during an initial "cooling-off period." (Digital Lending.pdf, p.1)

**5. Grievance Redressal**
*   **Nodal Officers:** Both the RE and the LSP (if they have an interface with the borrower) must designate nodal grievance redressal officers to handle complaints related to digital lending. (Digital Lending.pdf, p.1)

**6. Data Privacy and Biometrics**
*   **Biometric Data:** Biometric data must not be stored or collected by the RE or the LSP. (Digital Lending.pdf, p.1)
*   **Privacy Policy:** REs and LSPs engaged by REs must have a comprehensive privacy policy compliant with applicable laws. (Digital Lending.pdf, p.1)

**7. Default Loss Guarantee (DLG)**

Our digital-lending position is characterized by established web presences and digital payment channels, yet we lack explicit MSME positioning and specific metrics on application journey speed or turnaround times that competitors like fintechs leverage for faster approval and clearer pricing. While cooperative lenders differentiate themselves through local branch presence and rural product signals, our public information remains fragmented, often requiring manual validation unlike the streamlined digital onboarding of pure-play digital lenders. Regarding regulatory compliance, we must ensure explicit borrower consent before third-party data sharing, conduct enhanced due diligence with Lending Service Providers, and provide a digital view of all loan offers without bias. Furthermore, we are required to implement a cooling-off period for exits, designate nodal grievance officers, and strictly avoid collecting or storing biometric data while maintaining comprehensive privacy policies.
````

#### Citations

- Karnataka State Co-operative Apex Bank
- Bellary Urban Co-operative Bank
- Karnataka State Financial Corporation
- Kaujalgi Urban Co-operative Bank
- Belagavi District Central Co-operative Bank
- Digital Lending.pdf

---

### Q200 — Use our product performance, Karnataka's macro outlook, and competitor evidence to identify lending opportunities.

- Domain: **Hybrid / Book + Macro + Competitive**
- Expected source: `db, macro, competitive`
- Status: **Partial**
- Actual sources: `db, macro, competitive`
- Route match: **Yes**
- Latency: `50.68s`
- Cards: `clarify, brief, brief`

#### Response

````text
As of December 2025, Karnataka's MSME sector comprises 24.86 lakh registered entities supporting 235.27 lakh jobs [karnataka_des, p.151]. During 2025-26, Rs.69,211.08 lakh was allocated to the sector, with Rs.28,442.84 lakh utilized by December 2025 [karnataka_des, p.151]. Support mechanisms include capital/interest subsidies, SCSP, TSP schemes, and cluster development programs [karnataka_des, p.151]. While the text details allocation and utilization figures, it does not explicitly quantify current credit gaps or specific sectoral trends beyond these financial allocations and employment metrics. The provided context focuses on budgetary support rather than analyzing the disparity between demand and available credit.

Kinara Capital positions as a digital-first NBFC offering collateral-free loans up to ₹30 lakhs with quicker disbursals and minimum documentation, expanding aggressively across Karnataka and other states [Kinara Capital]. In contrast, Karnataka State Co-operative Apex Bank and urban co-operative banks (e.g., Kaujalgi, Bellary) leverage local branch networks for relationship-led acquisition and differentiate via agriculture/rural products [Karnataka State Co-operative Apex Bank].

The primary white space lies in blending cooperative rural depth with NBFC-style speed and digital onboarding. While co-ops face threats from faster approval and clearer pricing from fintechs and NBFCs, they currently lack explicit MSME product clarity in public data compared to Kinara's detailed calculators and scheme guides [Kinara Capital]. Co-ops should package MSME products with clearer eligibility and digital journeys to compete on speed without losing their rural advantage [Bhatkal Urban Co-operative Bank].

Karnataka's MSME sector presents a significant lending opportunity with 24.86 lakh registered entities supporting 235.27 lakh jobs, yet current data lacks explicit quantification of credit gaps or specific sectoral demand trends. Competitor analysis reveals a clear divergence where Kinara Capital dominates with digital-first, collateral-free loans up to ₹30 lakhs, while cooperative banks like Karnataka State Co-operative Apex Bank rely on local networks for agriculture and rural products. The primary white space lies in blending cooperative rural depth with NBFC-style speed, as co-ops currently lack the explicit MSME product clarity and digital calculators that Kinara offers. To capture this opportunity, banks must package MSME products with clearer eligibility and digital journeys to compete on speed without losing their rural advantage.
````

#### Citations

- karnataka_des
- Kinara Capital
- Karnataka State Co-operative Apex Bank
- Kaujalgi Urban Co-operative Bank

---

## Methodology

- Loan Book coverage is based on the governed Gold semantic YAML and PostgreSQL-backed views.
- Macro coverage reflects the configured macro Qdrant collection and local source inventory.
- Competitive coverage reflects all 11 registered institution Qdrant collections.
- Regulatory coverage reflects all 12 registered regulatory Qdrant collections.
- General Banking questions test natural routing to the catalog-backed concept explainer.
- Hybrid questions test natural multi-source routing without a source pin or routing hint.
- Expected sources are used only to score routing and are never sent to the application.
