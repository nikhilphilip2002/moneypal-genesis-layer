# GICC Loan Book — 100-Question Executive Chain Benchmark

**Generated:** 2026-09-05 13:08:54 UTC
**Endpoint:** `http://100.70.118.31:4321`
**Questions completed:** 100 / 100
**Wall-clock time:** 1177.57s
**Per-question client SLA:** 15s
**Concurrent chain workers:** 1

## Summary

| Metric | Result |
|---|---:|
| Answered or partial | 24 / 100 (24.0%) |
| Fully answered | 23 |
| Partial | 1 |
| Clarification | 0 |
| Refused | 3 |
| Errors | 73 |
| Complete five-turn chains | 0 / 20 |
| Mean latency | 11.78s |
| Median latency | 15.55s |
| P90 latency | 15.70s |
| P95 latency | 15.77s |
| Maximum latency | 16.25s |

## Results by executive role

| Role | Completed | Answered/partial | Errors | Mean latency |
|---|---:|---:|---:|---:|
| CEO | 35 | 10 | 25 | 11.42s |
| CFO | 35 | 6 | 29 | 13.26s |
| CGO | 30 | 8 | 19 | 10.45s |

## Results by turn depth

| Turn | Completed | Answered/partial | Errors | Mean latency |
|---:|---:|---:|---:|---:|
| 1 | 20 | 10 | 9 | 7.82s |
| 2 | 20 | 3 | 16 | 12.69s |
| 3 | 20 | 3 | 16 | 12.88s |
| 4 | 20 | 3 | 17 | 13.48s |
| 5 | 20 | 5 | 15 | 12.00s |

## Detailed results

### Chain 1: CEO — Scale and account mix

#### Q001 / Turn 1: How many sanctioned loan accounts are in the loan book?

- Status: **Answered**
- Latency: `0.87s`
- Route: `db` via `deterministic`
- Card types: `chart`
- Rows: `4`
- Database duration: `0 ms`

ACTIVE has the highest loans sanctioned, at 5,396 in all time, 94% of the total across 4 account statuses. This measures count of loan accounts sanctioned in the period, grouped by account status.

<details><summary>SQL</summary>

```sql
SELECT lam."loan_status" AS account_status,
       COUNT(*) AS loan_count
FROM gold.semantic_loan_account AS lam
WHERE lam."sanction_date" BETWEEN DATE '2000-01-01' AND DATE '2026-09-05'
GROUP BY lam."loan_status"
ORDER BY COUNT(*) DESC NULLS LAST
LIMIT 200
```

</details>

#### Q002 / Turn 2: Break that down by account status.

- Status: **Error**
- Latency: `15.41s`
- Route: `db` via `deterministic`
- Card types: `none`
- Rows: `n/a`
- Database duration: `n/a ms`

Request timed out after 15s

#### Q003 / Turn 3: Now show it by scheme.

- Status: **Error**
- Latency: `15.59s`
- Route: `db` via `deterministic`
- Card types: `none`
- Rows: `n/a`
- Database duration: `n/a ms`

Request timed out after 15s

#### Q004 / Turn 4: Which application branches have the most accounts?

- Status: **Error**
- Latency: `15.65s`
- Route: `db` via `deterministic`
- Card types: `none`
- Rows: `n/a`
- Database duration: `n/a ms`

Request timed out after 15s

#### Q005 / Turn 5: Show the top 10 borrowers by principal outstanding.

- Status: **Answered**
- Latency: `1.18s`
- Route: `db` via `deterministic`
- Card types: `chart`
- Rows: `10`
- Database duration: `0 ms`

MANJULA has the highest principal outstanding (whole book), at ₹67.37 L in 2026-09-05, 15% of the total across 10 borrowers. This measures cumulative disbursed minus cumulative principal repaid across loan accounts, grouped by borrower.

<details><summary>SQL</summary>

```sql
SELECT lam."customer_name" AS borrower,
       SUM(lam.disbursed_amount - lam.principal_repaid) AS principal_outstanding_book
FROM gold.semantic_loan_account AS lam
GROUP BY lam."customer_name"
ORDER BY SUM(lam.disbursed_amount - lam.principal_repaid) DESC NULLS LAST
LIMIT 10
```

</details>

### Chain 2: CEO — Disbursement trajectory

#### Q006 / Turn 1: What is our total disbursed amount this financial year?

- Status: **Answered**
- Latency: `0.82s`
- Route: `db` via `deterministic`
- Card types: `chart`
- Rows: `1`
- Database duration: `0 ms`

Disbursement was ₹137.16 Cr in FY27 to date. This measures sum of disbursement event amounts in the period.

<details><summary>SQL</summary>

```sql
SELECT SUM(disb.disbursement_amount) AS disbursement_total
FROM gold.semantic_disbursement_event AS disb
WHERE disb."disbursement_date" BETWEEN DATE '2026-04-01' AND DATE '2026-09-05'
LIMIT 200
```

</details>

#### Q007 / Turn 2: Show the monthly trend.

- Status: **Error**
- Latency: `15.41s`
- Route: `db` via `deterministic`
- Card types: `none`
- Rows: `n/a`
- Database duration: `n/a ms`

Request timed out after 15s

#### Q008 / Turn 3: Compare it with the previous financial year.

- Status: **Error**
- Latency: `15.77s`
- Route: `db` via `deterministic`
- Card types: `none`
- Rows: `n/a`
- Database duration: `n/a ms`

Request timed out after 15s

#### Q009 / Turn 4: Break the current financial year down by application branch.

- Status: **Error**
- Latency: `15.58s`
- Route: `db` via `deterministic`
- Card types: `none`
- Rows: `n/a`
- Database duration: `n/a ms`

Request timed out after 15s

#### Q010 / Turn 5: Which five schemes disbursed the most?

- Status: **Error**
- Latency: `15.65s`
- Route: `db` via `deterministic`
- Card types: `none`
- Rows: `n/a`
- Database duration: `n/a ms`

Request timed out after 15s

### Chain 3: CEO — Borrower reach and mix

#### Q011 / Turn 1: How many distinct borrowers have sanctioned loan accounts?

- Status: **Answered**
- Latency: `1.18s`
- Route: `db` via `deterministic`
- Card types: `chart`
- Rows: `1`
- Database duration: `0 ms`

Borrowers was 5,719 in all time. This measures distinct borrowers with an account sanctioned in the period.

<details><summary>SQL</summary>

```sql
SELECT COUNT(DISTINCT lam.customer_id) AS customer_count
FROM gold.semantic_loan_account AS lam
WHERE lam."sanction_date" BETWEEN DATE '2000-01-01' AND DATE '2026-09-05'
LIMIT 200
```

</details>

#### Q012 / Turn 2: Break the borrower count down by scheme.

- Status: **Error**
- Latency: `15.41s`
- Route: `db` via `deterministic`
- Card types: `none`
- Rows: `n/a`
- Database duration: `n/a ms`

Request timed out after 15s

#### Q013 / Turn 3: Now split it by gender.

- Status: **Error**
- Latency: `15.67s`
- Route: `db` via `deterministic`
- Card types: `none`
- Rows: `n/a`
- Database duration: `n/a ms`

Request timed out after 15s

#### Q014 / Turn 4: Show borrower count by application branch.

- Status: **Error**
- Latency: `15.59s`
- Route: `db` via `deterministic`
- Card types: `none`
- Rows: `n/a`
- Database duration: `n/a ms`

Request timed out after 15s

#### Q015 / Turn 5: Which ten agents have the highest customer count?

- Status: **Answered**
- Latency: `1.15s`
- Route: `db` via `deterministic`
- Card types: `chart`
- Rows: `1`
- Database duration: `0 ms`

Borrowers was 0 in all time. This measures distinct borrowers with an account sanctioned in the period.

<details><summary>SQL</summary>

```sql
SELECT COUNT(DISTINCT lam.customer_id) AS customer_count
FROM gold.semantic_loan_account AS lam
WHERE lam."sanction_date" BETWEEN DATE '2000-01-01' AND DATE '2026-09-05'
  AND LOWER(lam."agent_code"::text) = ANY(ARRAY['s'])
LIMIT 200
```

</details>

### Chain 4: CEO — Outstanding portfolio concentration

#### Q016 / Turn 1: What is the current principal outstanding across the loan book?

- Status: **Answered**
- Latency: `0.82s`
- Route: `db` via `deterministic`
- Card types: `chart`
- Rows: `1`
- Database duration: `0 ms`

Principal outstanding was ₹194.43 Cr for asset classification Standard as at 05 Sep 2026. This measures principal outstanding from each classified account at the requested snapshot.

<details><summary>SQL</summary>

```sql
SELECT SUM(portfolio.principal_outstanding) AS principal_outstanding
FROM gold.portfolio_snapshot_as_of(DATE '2026-09-05') AS portfolio
WHERE portfolio."asset_code"::text = 'STD'
LIMIT 200
```

</details>

#### Q017 / Turn 2: Break it down by scheme.

- Status: **Error**
- Latency: `15.41s`
- Route: `db` via `deterministic`
- Card types: `none`
- Rows: `n/a`
- Database duration: `n/a ms`

Request timed out after 15s

#### Q018 / Turn 3: Now show it by application branch.

- Status: **Error**
- Latency: `15.77s`
- Route: `db` via `deterministic`
- Card types: `none`
- Rows: `n/a`
- Database duration: `n/a ms`

Request timed out after 15s

#### Q019 / Turn 4: Split it by account status.

- Status: **Error**
- Latency: `15.67s`
- Route: `db` via `deterministic`
- Card types: `none`
- Rows: `n/a`
- Database duration: `n/a ms`

Request timed out after 15s

#### Q020 / Turn 5: Which ten borrowers have the largest principal outstanding?

- Status: **Error**
- Latency: `15.66s`
- Route: `db` via `deterministic`
- Card types: `none`
- Rows: `n/a`
- Database duration: `n/a ms`

Request timed out after 15s

### Chain 5: CEO — NPA profile

#### Q021 / Turn 1: What is our current NPA ratio?

- Status: **Answered**
- Latency: `1.08s`
- Route: `db` via `deterministic`
- Card types: `chart`
- Rows: `1`
- Database duration: `0 ms`

NPA ratio was 0.02% as at 05 Sep 2026. This measures nPA-classified principal outstanding divided by classified principal outstanding. Definition of NPA ratio is pending client sign-off.

<details><summary>SQL</summary>

```sql
SELECT (100.0 * COALESCE(SUM(portfolio.principal_outstanding) FILTER (WHERE portfolio.is_npa), 0) / NULLIF(SUM(portfolio.principal_outstanding), 0)) AS npa_ratio
FROM gold.portfolio_snapshot_as_of(DATE '2026-09-05') AS portfolio
LIMIT 200
```

</details>

#### Q022 / Turn 2: Break it down by scheme.

- Status: **Error**
- Latency: `15.40s`
- Route: `db` via `deterministic`
- Card types: `none`
- Rows: `n/a`
- Database duration: `n/a ms`

Request timed out after 15s

#### Q023 / Turn 3: Now show it by application branch.

- Status: **Error**
- Latency: `15.58s`
- Route: `db` via `deterministic`
- Card types: `none`
- Rows: `n/a`
- Database duration: `n/a ms`

Request timed out after 15s

#### Q024 / Turn 4: Which borrowers have the highest NPA principal outstanding?

- Status: **Answered**
- Latency: `1.27s`
- Route: `db` via `deterministic`
- Card types: `chart`
- Rows: `1`
- Database duration: `0 ms`

No principal outstanding found as at 05 Sep 2026 with Asset classification eq NPA. This measures principal outstanding from each classified account at the requested snapshot.

<details><summary>SQL</summary>

```sql
SELECT SUM(portfolio.principal_outstanding) AS principal_outstanding
FROM gold.portfolio_snapshot_as_of(DATE '2026-09-05') AS portfolio
WHERE portfolio."asset_code"::text = 'NPA'
LIMIT 200
```

</details>

#### Q025 / Turn 5: How many accounts are currently classified as NPA?

- Status: **Error**
- Latency: `15.41s`
- Route: `db` via `deterministic`
- Card types: `none`
- Rows: `n/a`
- Database duration: `n/a ms`

Request timed out after 15s

### Chain 6: CEO — Portfolio at risk

#### Q026 / Turn 1: What is our current PAR 30 ratio?

- Status: **Error**
- Latency: `15.42s`
- Route: `db` via `deterministic`
- Card types: `none`
- Rows: `n/a`
- Database duration: `n/a ms`

Request timed out after 15s

#### Q027 / Turn 2: Break PAR 30 down by scheme.

- Status: **Error**
- Latency: `15.63s`
- Route: `db` via `deterministic`
- Card types: `none`
- Rows: `n/a`
- Database duration: `n/a ms`

Request timed out after 15s

#### Q028 / Turn 3: Now show PAR 30 by application branch.

- Status: **Error**
- Latency: `15.65s`
- Route: `db` via `deterministic`
- Card types: `none`
- Rows: `n/a`
- Database duration: `n/a ms`

Request timed out after 15s

#### Q029 / Turn 4: What is our current PAR 90 ratio?

- Status: **Error**
- Latency: `15.67s`
- Route: `db` via `deterministic`
- Card types: `none`
- Rows: `n/a`
- Database duration: `n/a ms`

Request timed out after 15s

#### Q030 / Turn 5: Which schemes have the highest overdue principal?

- Status: **Error**
- Latency: `15.67s`
- Route: `db` via `deterministic`
- Card types: `none`
- Rows: `n/a`
- Database duration: `n/a ms`

Request timed out after 15s

### Chain 7: CEO — Product and scheme portfolio

#### Q031 / Turn 1: Which schemes have the largest principal outstanding?

- Status: **Answered**
- Latency: `1.18s`
- Route: `db` via `deterministic`
- Card types: `chart`
- Rows: `8`
- Database duration: `0 ms`

MSME Loans has the highest principal outstanding, at ₹59.81 Cr as at 05 Sep 2026, 29% of the total across 8 schemes. This measures principal outstanding from each classified account at the requested snapshot, grouped by scheme.

<details><summary>SQL</summary>

```sql
SELECT lam."scheme_code" AS scheme,
       SUM(portfolio.principal_outstanding) AS principal_outstanding
FROM gold.portfolio_snapshot_as_of(DATE '2026-09-05') AS portfolio
     JOIN gold.semantic_loan_account AS lam ON portfolio."entity_num"::text = lam."entity_num"::text AND portfolio."loan_account_number"::text = lam."loan_account_number"::text
GROUP BY lam."scheme_code"
ORDER BY SUM(portfolio.principal_outstanding) DESC NULLS LAST
LIMIT 200
```

</details>

#### Q032 / Turn 2: For those schemes, show total disbursed amount.

- Status: **Answered**
- Latency: `0.92s`
- Route: `db` via `catalog`
- Card types: `chart`
- Rows: `1`
- Database duration: `0 ms`

Principal outstanding (whole book) was ₹214.00 Cr in 2026-09-05. This measures cumulative disbursed minus cumulative principal repaid across loan accounts.

<details><summary>SQL</summary>

```sql
SELECT SUM(lam.disbursed_amount - lam.principal_repaid) AS principal_outstanding_book
FROM gold.semantic_loan_account AS lam
LIMIT 200
```

</details>

#### Q033 / Turn 3: Also show their sanctioned loan count.

- Status: **Error**
- Latency: `15.39s`
- Route: `db` via `deterministic`
- Card types: `none`
- Rows: `n/a`
- Database duration: `n/a ms`

Request timed out after 15s

#### Q034 / Turn 4: Which schemes have the highest average ticket size?

- Status: **Error**
- Latency: `15.69s`
- Route: `db` via `deterministic`
- Card types: `none`
- Rows: `n/a`
- Database duration: `n/a ms`

Request timed out after 15s

#### Q035 / Turn 5: Which schemes combine high growth with low PAR 30?

- Status: **Error**
- Latency: `15.56s`
- Route: `db` via `deterministic`
- Card types: `none`
- Rows: `n/a`
- Database duration: `n/a ms`

Request timed out after 15s

### Chain 8: CFO — Sanction-to-disbursement

#### Q036 / Turn 1: Compare total sanctioned amount with total disbursed amount.

- Status: **Answered**
- Latency: `1.08s`
- Route: `db` via `deterministic`
- Card types: `chart`
- Rows: `1`
- Database duration: `0 ms`

Sanctioned amount was ₹229.10 Cr in all time. This measures sum of sanctioned amounts for accounts sanctioned in the period.

<details><summary>SQL</summary>

```sql
SELECT SUM(lam.sanction_amount) AS sanctioned_amount
FROM gold.semantic_loan_account AS lam
WHERE lam."sanction_date" BETWEEN DATE '2000-01-01' AND DATE '2026-09-05'
LIMIT 200
```

</details>

#### Q037 / Turn 2: Show the difference by scheme.

- Status: **Error**
- Latency: `15.31s`
- Route: `db` via `deterministic`
- Card types: `none`
- Rows: `n/a`
- Database duration: `n/a ms`

Request timed out after 15s

#### Q038 / Turn 3: Now show it by application branch.

- Status: **Error**
- Latency: `15.67s`
- Route: `db` via `deterministic`
- Card types: `none`
- Rows: `n/a`
- Database duration: `n/a ms`

Request timed out after 15s

#### Q039 / Turn 4: What is the sanction-to-disbursement conversion rate?

- Status: **Error**
- Latency: `15.66s`
- Route: `db` via `deterministic`
- Card types: `none`
- Rows: `n/a`
- Database duration: `n/a ms`

Request timed out after 15s

#### Q040 / Turn 5: Which schemes have the lowest conversion rate?

- Status: **Error**
- Latency: `15.77s`
- Route: `db` via `deterministic`
- Card types: `none`
- Rows: `n/a`
- Database duration: `n/a ms`

Request timed out after 15s

### Chain 9: CFO — Collection efficiency

#### Q041 / Turn 1: What is our collection efficiency this month?

- Status: **Error**
- Latency: `15.57s`
- Route: `db` via `deterministic`
- Card types: `none`
- Rows: `n/a`
- Database duration: `n/a ms`

Request timed out after 15s

#### Q042 / Turn 2: Show total amount due and total amount collected behind that result.

- Status: **Error**
- Latency: `15.46s`
- Route: `db` via `deterministic`
- Card types: `none`
- Rows: `n/a`
- Database duration: `n/a ms`

Request timed out after 15s

#### Q043 / Turn 3: Break collection efficiency down by scheme.

- Status: **Answered**
- Latency: `1.99s`
- Route: `db` via `deterministic`
- Card types: `chart`
- Rows: `8`
- Database duration: `639 ms`

MSME Loans has the highest amount collected, at ₹6.96 Cr in all time, 31% of the total across 8 schemes. This measures principal plus interest paid in the period, grouped by scheme.

<details><summary>SQL</summary>

```sql
SELECT lam."scheme_code" AS scheme,
       SUM(repay.total_paid) AS amount_collected
FROM gold.semantic_repayment_event AS repay
     JOIN gold.semantic_loan_account AS lam ON repay."entity_num"::text = lam."entity_num"::text AND repay."loan_account_number"::text = lam."loan_account_number"::text
WHERE repay."repayment_date" BETWEEN DATE '2000-01-01' AND DATE '2026-09-05'
GROUP BY lam."scheme_code"
ORDER BY SUM(repay.total_paid) DESC NULLS LAST
LIMIT 200
```

</details>

#### Q044 / Turn 4: Now show it by application branch.

- Status: **Error**
- Latency: `16.25s`
- Route: `db` via `deterministic`
- Card types: `none`
- Rows: `n/a`
- Database duration: `n/a ms`

Request timed out after 15s

#### Q045 / Turn 5: Compare this month with last month.

- Status: **Error**
- Latency: `15.55s`
- Route: `db` via `deterministic`
- Card types: `none`
- Rows: `n/a`
- Database duration: `n/a ms`

Request timed out after 15s

### Chain 10: CFO — Interest performance

#### Q046 / Turn 1: How much interest have we collected this financial year?

- Status: **Error**
- Latency: `15.56s`
- Route: `db` via `deterministic`
- Card types: `none`
- Rows: `n/a`
- Database duration: `n/a ms`

Request timed out after 15s

#### Q047 / Turn 2: Show the monthly trend.

- Status: **Error**
- Latency: `15.67s`
- Route: `db` via `deterministic`
- Card types: `none`
- Rows: `n/a`
- Database duration: `n/a ms`

Request timed out after 15s

#### Q048 / Turn 3: Break it down by scheme.

- Status: **Error**
- Latency: `15.70s`
- Route: `db` via `deterministic`
- Card types: `none`
- Rows: `n/a`
- Database duration: `n/a ms`

Request timed out after 15s

#### Q049 / Turn 4: Now show it by application branch.

- Status: **Error**
- Latency: `15.53s`
- Route: `db` via `deterministic`
- Card types: `none`
- Rows: `n/a`
- Database duration: `n/a ms`

Request timed out after 15s

#### Q050 / Turn 5: What is the weighted average contractual interest rate?

- Status: **Answered**
- Latency: `0.98s`
- Route: `knowledge` via `deterministic`
- Card types: `brief`
- Rows: `n/a`
- Database duration: `n/a ms`

Average interest rate is measured as sanction-amount-weighted average account interest rate.

### Chain 11: CFO — Principal cash flows

#### Q051 / Turn 1: How much principal has been repaid this financial year?

- Status: **Error**
- Latency: `15.31s`
- Route: `db` via `deterministic`
- Card types: `none`
- Rows: `n/a`
- Database duration: `n/a ms`

Request timed out after 15s

#### Q052 / Turn 2: Show the monthly principal repayment trend.

- Status: **Error**
- Latency: `15.67s`
- Route: `db` via `deterministic`
- Card types: `none`
- Rows: `n/a`
- Database duration: `n/a ms`

Request timed out after 15s

#### Q053 / Turn 3: Break principal repaid down by scheme.

- Status: **Error**
- Latency: `15.67s`
- Route: `db` via `deterministic`
- Card types: `none`
- Rows: `n/a`
- Database duration: `n/a ms`

Request timed out after 15s

#### Q054 / Turn 4: Now compare principal repaid with disbursed amount.

- Status: **Error**
- Latency: `15.67s`
- Route: `db` via `deterministic`
- Card types: `none`
- Rows: `n/a`
- Database duration: `n/a ms`

Request timed out after 15s

#### Q055 / Turn 5: Which schemes have the lowest principal repayment percentage?

- Status: **Error**
- Latency: `15.67s`
- Route: `db` via `deterministic`
- Card types: `none`
- Rows: `n/a`
- Database duration: `n/a ms`

Request timed out after 15s

### Chain 12: CFO — Ticket size

#### Q056 / Turn 1: What is the average sanctioned ticket size?

- Status: **Error**
- Latency: `15.36s`
- Route: `db` via `deterministic`
- Card types: `none`
- Rows: `n/a`
- Database duration: `n/a ms`

Request timed out after 15s

#### Q057 / Turn 2: Break average ticket size down by scheme.

- Status: **Error**
- Latency: `15.56s`
- Route: `db` via `deterministic`
- Card types: `none`
- Rows: `n/a`
- Database duration: `n/a ms`

Request timed out after 15s

#### Q058 / Turn 3: Now show it by application branch.

- Status: **Error**
- Latency: `15.67s`
- Route: `db` via `deterministic`
- Card types: `none`
- Rows: `n/a`
- Database duration: `n/a ms`

Request timed out after 15s

#### Q059 / Turn 4: Which ten borrowers received the largest sanctioned amounts?

- Status: **Error**
- Latency: `15.57s`
- Route: `db` via `deterministic`
- Card types: `none`
- Rows: `n/a`
- Database duration: `n/a ms`

Request timed out after 15s

#### Q060 / Turn 5: How has average ticket size changed by month this year?

- Status: **Error**
- Latency: `15.66s`
- Route: `db` via `deterministic`
- Card types: `none`
- Rows: `n/a`
- Database duration: `n/a ms`

Request timed out after 15s

### Chain 13: CFO — Disbursement and collection cash flow

#### Q061 / Turn 1: Show monthly disbursements and total collections for this financial year.

- Status: **Error**
- Latency: `15.57s`
- Route: `db` via `deterministic`
- Card types: `none`
- Rows: `n/a`
- Database duration: `n/a ms`

Request timed out after 15s

#### Q062 / Turn 2: Which months had collections below disbursements?

- Status: **Error**
- Latency: `15.77s`
- Route: `db` via `deterministic`
- Card types: `none`
- Rows: `n/a`
- Database duration: `n/a ms`

Request timed out after 15s

#### Q063 / Turn 3: What was the largest monthly cash-flow gap?

- Status: **Error**
- Latency: `16.08s`
- Route: `db` via `deterministic`
- Card types: `none`
- Rows: `n/a`
- Database duration: `n/a ms`

Request timed out after 15s

#### Q064 / Turn 4: Break the current total collection amount down by scheme.

- Status: **Partial**
- Latency: `1.28s`
- Route: `db` via `policy`
- Card types: `chart`
- Rows: `8`
- Database duration: `0 ms`

MSME Loans has the highest amount collected, at ₹6.96 Cr in all time, 31% of the total across 8 schemes. This measures principal plus interest paid in the period, grouped by scheme.

<details><summary>SQL</summary>

```sql
SELECT lam."scheme_code" AS scheme,
       SUM(repay.total_paid) AS amount_collected
FROM gold.semantic_repayment_event AS repay
     JOIN gold.semantic_loan_account AS lam ON repay."entity_num"::text = lam."entity_num"::text AND repay."loan_account_number"::text = lam."loan_account_number"::text
WHERE repay."repayment_date" BETWEEN DATE '2000-01-01' AND DATE '2026-09-05'
GROUP BY lam."scheme_code"
ORDER BY SUM(repay.total_paid) DESC NULLS LAST
LIMIT 200
```

</details>

#### Q065 / Turn 5: Which branches collected the most this financial year?

- Status: **Error**
- Latency: `15.41s`
- Route: `db` via `deterministic`
- Card types: `none`
- Rows: `n/a`
- Database duration: `n/a ms`

Request timed out after 15s

### Chain 14: CFO — Equity and book leverage

#### Q066 / Turn 1: What is the current share capital balance in the general ledger?

- Status: **Answered**
- Latency: `4.56s`
- Route: `db` via `deterministic`
- Card types: `chart`
- Rows: `1`
- Database duration: `2508 ms`

Share capital was ₹85.50 L as at 05 Sep 2026. This measures current base-currency balance of governed GL accounts in access-code group 1001. Definition of Share capital is pending client sign-off.

<details><summary>SQL</summary>

```sql
SELECT SUM(CASE WHEN LEFT(COALESCE(gl.external_access_code, ''), 4) = '1001' THEN COALESCE(gl.base_currency_balance, 0) ELSE 0 END) AS share_capital
FROM (
       SELECT DISTINCT ON ("entity_num", "branch_code", "gl_number", "currency_code") *
       FROM gold.semantic_gl_balance
       WHERE "balance_date" <= DATE '2026-09-05'
       ORDER BY "entity_num", "branch_code", "gl_number", "currency_code", "balance_date" DESC
     ) AS gl
LIMIT 200
```

</details>

#### Q067 / Turn 2: Show the general-ledger accounts included in that balance.

- Status: **Error**
- Latency: `15.51s`
- Route: `db` via `deterministic`
- Card types: `none`
- Rows: `n/a`
- Database duration: `n/a ms`

Request timed out after 15s

#### Q068 / Turn 3: What is current principal outstanding relative to share capital?

- Status: **Answered**
- Latency: `1.38s`
- Route: `db` via `deterministic`
- Card types: `chart`
- Rows: `1`
- Database duration: `0 ms`

Share capital was ₹85.50 L as at 05 Sep 2026. This measures current base-currency balance of governed GL accounts in access-code group 1001. Definition of Share capital is pending client sign-off.

<details><summary>SQL</summary>

```sql
SELECT SUM(CASE WHEN LEFT(COALESCE(gl.external_access_code, ''), 4) = '1001' THEN COALESCE(gl.base_currency_balance, 0) ELSE 0 END) AS share_capital
FROM (
       SELECT DISTINCT ON ("entity_num", "branch_code", "gl_number", "currency_code") *
       FROM gold.semantic_gl_balance
       WHERE "balance_date" <= DATE '2026-09-05'
       ORDER BY "entity_num", "branch_code", "gl_number", "currency_code", "balance_date" DESC
     ) AS gl
LIMIT 200
```

</details>

#### Q069 / Turn 4: How much total interest is outstanding?

- Status: **Error**
- Latency: `15.42s`
- Route: `db` via `deterministic`
- Card types: `none`
- Rows: `n/a`
- Database duration: `n/a ms`

Request timed out after 15s

#### Q070 / Turn 5: Break interest outstanding down by scheme.

- Status: **Error**
- Latency: `15.75s`
- Route: `db` via `deterministic`
- Card types: `none`
- Rows: `n/a`
- Database duration: `n/a ms`

Request timed out after 15s

### Chain 15: CGO — Agent customer franchise

#### Q071 / Turn 1: Show the top 10 agents with the highest customer count.

- Status: **Answered**
- Latency: `2.40s`
- Route: `db` via `deterministic`
- Card types: `chart`
- Rows: `10`
- Database duration: `434 ms`

Vanitha has the highest borrowers, at 338 in all time, 20% of the total across 10 agents. This measures distinct borrowers with an account sanctioned in the period, grouped by agent.

<details><summary>SQL</summary>

```sql
SELECT lam."agent_code" AS loan_agent,
       COUNT(DISTINCT lam.customer_id) AS customer_count
FROM gold.semantic_loan_account AS lam
WHERE lam."sanction_date" BETWEEN DATE '2000-01-01' AND DATE '2026-09-05'
GROUP BY lam."agent_code"
ORDER BY COUNT(DISTINCT lam.customer_id) DESC NULLS LAST
LIMIT 10
```

</details>

#### Q072 / Turn 2: Show me customers under Vanitha.

- Status: **Answered**
- Latency: `2.16s`
- Route: `db` via `catalog`
- Card types: `chart`
- Rows: `338`
- Database duration: `409 ms`

Showing 338 of 338 linked customer(s).

<details><summary>SQL</summary>

```sql
SELECT
  CAST(reporting.customer_id AS TEXT) AS customer_id,
  MIN(TRIM(REGEXP_REPLACE(reporting.customer_name, '\s+', ' ', 'g'))) AS borrower_name,
  COUNT(DISTINCT reporting.loan_account_number) AS linked_loan_count,
  COUNT(reporting.customer_id) OVER () AS total_linked_customer_count
FROM gold.semantic_loan_account AS reporting
WHERE
  LOWER(reporting.agent_code) = 'agnt45'
  AND reporting.sanction_date <= CURRENT_DATE
GROUP BY
  reporting.customer_id
ORDER BY
  borrower_name,
  customer_id
LIMIT 500
```

</details>

#### Q073 / Turn 3: Add scheme name and tenure.

- Status: **Answered**
- Latency: `2.66s`
- Route: `db` via `catalog`
- Card types: `chart`
- Rows: `338`
- Database duration: `546 ms`

Showing 338 of 338 linked loan account(s) with borrower names, scheme names, tenure (EMIs).

<details><summary>SQL</summary>

```sql
SELECT
  CAST(reporting.loan_account_number AS TEXT) AS loan_account_number,
  reporting.customer_name AS borrower_name,
  reporting.scheme_name,
  reporting.number_of_emis,
  COUNT(reporting.loan_account_number) OVER () AS total_linked_account_count
FROM gold.semantic_loan_account AS reporting
WHERE
  LOWER(reporting.agent_code) = 'agnt45'
ORDER BY
  reporting.loan_account_number
LIMIT 500
```

</details>

#### Q074 / Turn 4: Also include the disbursed loan amount.

- Status: **Error**
- Latency: `15.40s`
- Route: `db` via `deterministic`
- Card types: `none`
- Rows: `n/a`
- Database duration: `n/a ms`

Request timed out after 15s

#### Q075 / Turn 5: Show the linked loan account numbers.

- Status: **Error**
- Latency: `15.77s`
- Route: `db` via `deterministic`
- Card types: `none`
- Rows: `n/a`
- Database duration: `n/a ms`

Request timed out after 15s

### Chain 16: CGO — Branch customer franchise

#### Q076 / Turn 1: List customers in Ujire.

- Status: **Refused**
- Latency: `1.28s`
- Route: `db` via `catalog`
- Card types: `refusal`
- Rows: `n/a`
- Database duration: `n/a ms`

No customer or loan records matched that lookup.

#### Q077 / Turn 2: Add scheme name and tenure.

- Status: **Refused**
- Latency: `1.03s`
- Route: `db` via `catalog`
- Card types: `refusal`
- Rows: `n/a`
- Database duration: `n/a ms`

No customer or loan records matched that lookup.

#### Q078 / Turn 3: Also include disbursed amount.

- Status: **Refused**
- Latency: `1.23s`
- Route: `db` via `catalog`
- Card types: `refusal`
- Rows: `n/a`
- Database duration: `n/a ms`

No customer or loan records matched that lookup.

#### Q079 / Turn 4: How many distinct customers are in that branch?

- Status: **Error**
- Latency: `15.41s`
- Route: `db` via `deterministic`
- Card types: `none`
- Rows: `n/a`
- Database duration: `n/a ms`

Request timed out after 15s

#### Q080 / Turn 5: What is total principal outstanding for that branch?

- Status: **Answered**
- Latency: `1.28s`
- Route: `db` via `deterministic`
- Card types: `chart`
- Rows: `1`
- Database duration: `0 ms`

Principal outstanding (whole book) was ₹214.00 Cr in 2026-09-05. This measures cumulative disbursed minus cumulative principal repaid across loan accounts.

<details><summary>SQL</summary>

```sql
SELECT SUM(lam.disbursed_amount - lam.principal_repaid) AS principal_outstanding_book
FROM gold.semantic_loan_account AS lam
LIMIT 200
```

</details>

### Chain 17: CGO — Scheme origination

#### Q081 / Turn 1: Which ten schemes have the highest sanctioned loan count?

- Status: **Error**
- Latency: `15.41s`
- Route: `db` via `deterministic`
- Card types: `none`
- Rows: `n/a`
- Database duration: `n/a ms`

Request timed out after 15s

#### Q082 / Turn 2: Show their total sanctioned amount.

- Status: **Answered**
- Latency: `1.38s`
- Route: `db` via `deterministic`
- Card types: `chart`
- Rows: `1`
- Database duration: `96 ms`

Sanctioned amount was ₹229.10 Cr in all time. This measures sum of sanctioned amounts for accounts sanctioned in the period.

<details><summary>SQL</summary>

```sql
SELECT SUM(lam.sanction_amount) AS sanctioned_amount
FROM gold.semantic_loan_account AS lam
WHERE lam."sanction_date" BETWEEN DATE '2000-01-01' AND DATE '2026-09-05'
LIMIT 200
```

</details>

#### Q083 / Turn 3: Now add total disbursed amount.

- Status: **Error**
- Latency: `15.41s`
- Route: `db` via `deterministic`
- Card types: `none`
- Rows: `n/a`
- Database duration: `n/a ms`

Request timed out after 15s

#### Q084 / Turn 4: What is their average ticket size?

- Status: **Answered**
- Latency: `0.97s`
- Route: `knowledge` via `deterministic`
- Card types: `brief`
- Rows: `n/a`
- Database duration: `n/a ms`

Average ticket size is measured as total sanctioned amount divided by number of loans.

#### Q085 / Turn 5: Which of those schemes grew fastest this financial year?

- Status: **Error**
- Latency: `15.41s`
- Route: `db` via `deterministic`
- Card types: `none`
- Rows: `n/a`
- Database duration: `n/a ms`

Request timed out after 15s

### Chain 18: CGO — Gender participation

#### Q086 / Turn 1: How many borrowers are female and how many are male?

- Status: **Error**
- Latency: `15.79s`
- Route: `db` via `deterministic`
- Card types: `none`
- Rows: `n/a`
- Database duration: `n/a ms`

Request timed out after 15s

#### Q087 / Turn 2: Show total disbursed amount by gender.

- Status: **Error**
- Latency: `15.65s`
- Route: `db` via `deterministic`
- Card types: `none`
- Rows: `n/a`
- Database duration: `n/a ms`

Request timed out after 15s

#### Q088 / Turn 3: Now show average sanctioned ticket size by gender.

- Status: **Error**
- Latency: `15.67s`
- Route: `db` via `deterministic`
- Card types: `none`
- Rows: `n/a`
- Database duration: `n/a ms`

Request timed out after 15s

#### Q089 / Turn 4: Break female borrower count down by scheme.

- Status: **Error**
- Latency: `16.08s`
- Route: `db` via `deterministic`
- Card types: `none`
- Rows: `n/a`
- Database duration: `n/a ms`

Request timed out after 15s

#### Q090 / Turn 5: Which application branches serve the most female borrowers?

- Status: **Error**
- Latency: `15.66s`
- Route: `db` via `deterministic`
- Card types: `none`
- Rows: `n/a`
- Database duration: `n/a ms`

Request timed out after 15s

### Chain 19: CGO — Origination network

#### Q091 / Turn 1: Rank application branches by total disbursed amount this financial year.

- Status: **Error**
- Latency: `15.56s`
- Route: `db` via `deterministic`
- Card types: `none`
- Rows: `n/a`
- Database duration: `n/a ms`

Request timed out after 15s

#### Q092 / Turn 2: Add sanctioned loan count for each branch.

- Status: **Error**
- Latency: `15.67s`
- Route: `db` via `deterministic`
- Card types: `none`
- Rows: `n/a`
- Database duration: `n/a ms`

Request timed out after 15s

#### Q093 / Turn 3: Now add distinct borrower count.

- Status: **Error**
- Latency: `15.56s`
- Route: `db` via `deterministic`
- Card types: `none`
- Rows: `n/a`
- Database duration: `n/a ms`

Request timed out after 15s

#### Q094 / Turn 4: Which branch has the highest average ticket size?

- Status: **Error**
- Latency: `15.67s`
- Route: `db` via `deterministic`
- Card types: `none`
- Rows: `n/a`
- Database duration: `n/a ms`

Request timed out after 15s

#### Q095 / Turn 5: Which branches have declining monthly disbursements?

- Status: **Error**
- Latency: `15.56s`
- Route: `db` via `deterministic`
- Card types: `none`
- Rows: `n/a`
- Database duration: `n/a ms`

Request timed out after 15s

### Chain 20: CGO — Agent volume and quality

#### Q096 / Turn 1: Rank the top 10 agents by sanctioned loan count.

- Status: **Answered**
- Latency: `1.59s`
- Route: `db` via `deterministic`
- Card types: `chart`
- Rows: `1`
- Database duration: `397 ms`

Loans sanctioned was 0 in all time. This measures count of loan accounts sanctioned in the period.

<details><summary>SQL</summary>

```sql
SELECT COUNT(*) AS loan_count
FROM gold.semantic_loan_account AS lam
WHERE lam."sanction_date" BETWEEN DATE '2000-01-01' AND DATE '2026-09-05'
  AND LOWER(lam."agent_code"::text) = ANY(ARRAY['s'])
LIMIT 200
```

</details>

#### Q097 / Turn 2: Now rank them by total disbursed amount.

- Status: **Error**
- Latency: `15.40s`
- Route: `db` via `deterministic`
- Card types: `none`
- Rows: `n/a`
- Database duration: `n/a ms`

Request timed out after 15s

#### Q098 / Turn 3: Add distinct borrower count.

- Status: **Error**
- Latency: `15.57s`
- Route: `db` via `deterministic`
- Card types: `none`
- Rows: `n/a`
- Database duration: `n/a ms`

Request timed out after 15s

#### Q099 / Turn 4: Which agents have the highest principal outstanding?

- Status: **Error**
- Latency: `15.66s`
- Route: `db` via `deterministic`
- Card types: `none`
- Rows: `n/a`
- Database duration: `n/a ms`

Request timed out after 15s

#### Q100 / Turn 5: For the leading agent, show the linked customers.

- Status: **Answered**
- Latency: `1.18s`
- Route: `db` via `catalog`
- Card types: `chart`
- Rows: `1`
- Database duration: `0 ms`

Principal outstanding (whole book) was ₹214.00 Cr in 2026-09-05. This measures cumulative disbursed minus cumulative principal repaid across loan accounts.

<details><summary>SQL</summary>

```sql
SELECT SUM(lam.disbursed_amount - lam.principal_repaid) AS principal_outstanding_book
FROM gold.semantic_loan_account AS lam
LIMIT 200
```

</details>

## Methodology

- Exactly 100 questions are grouped into 20 five-turn conversations.
- Turns in each chain share the API-issued conversation ID and run sequentially.
- Independent chains may run concurrently; wall-clock time therefore differs from summed latency.
- No source is pinned. External sources are disabled so every question must be handled by the loan book or fail visibly.
- 'Answered' is based on the Workbench SSE answer/card contract, not a separate semantic correctness judge.
- SQL, row counts, route, and database duration are retained for manual correctness review.
