# June dump vs July Oracle cross-analysis

**Analysis date:** 2026-08-12  
**June temporary dump:** `192.168.1.183:1521/FREEPDB1`, schema `GICCPROD_NEW`  
**July Oracle source:** `139.84.155.19:1521/FREEPDB1`, schema `GICCPROD_NEW`  
**PostgreSQL target:** `192.168.1.183:5432/moneypaldb`, schema `silver`

All checks were read-only and used exact `COUNT(*)`, distinct counts, date ranges, and
account-ID set comparisons. Credentials are intentionally not recorded here.

## Executive conclusion

The apparent fall from “13,000-something” to “5,000-something” was caused by comparing
different grains and different July source tables:

- **13,510** was the June number of loan **accounts**, not borrowers.
- The June dump had **11,347 distinct loan borrowers** across products 1, 13 and 16.
- July live `GENLNACNTS` has **5,753 accounts / 5,719 borrowers**, all product 16.
- July `GENLNACNTS_29102024` holds the unchanged legacy products 1 and 13:
  **7,855 accounts / 7,409 borrowers**.
- The correct deduplicated July portfolio is **13,608 accounts / 11,477 loan borrowers**.
- July also has **17,972 registered CIF customers**. CIF customers are not all borrowers.

The legacy archive is safe for portfolio coverage because its 7,855 account IDs match
the June product-1/product-13 population exactly: zero missing and zero extra accounts.
It must still be labelled as a legacy/run-off source rather than current activity.

## Database scope

| Measure | June temporary Oracle | July Oracle |
|---|---:|---:|
| Schema tables | 9,545 | 14,585 |
| Live `GENLNACNTS` accounts | 13,510 | 5,753 |
| Live `GENLNACNTS` borrowers | 11,347 | 5,719 |
| CIF customers | Table absent | 17,972 |
| Branch master | Table absent | 67 rows |

The July instance is a broader import than the earlier July EDA snapshot documented in
`jul_eda.md`; the live schema now contains 14,585 tables and includes tables that were
previously excluded or imported later.

## Loan portfolio comparison

| Product | June accounts | June borrowers | July authoritative source | July accounts | July borrowers |
|---|---:|---:|---|---:|---:|
| 1 — Gold Loans | 140 | 86 | `GENLNACNTS_29102024` | 140 | 86 |
| 13 — Microfinance/Retail | 7,715 | 7,324 | `GENLNACNTS_29102024` | 7,715 | 7,324 |
| 16 — Business/MSME | 5,655 | 5,544 | live `GENLNACNTS` | 5,753 | 5,719 |
| Deduplicated total | 13,510 | 11,347 | live + verified legacy archive | 13,608 | 11,477 |

Borrowers cannot be added across products because 1,651 customer IDs occur in both the
July live and legacy populations. The 11,477 result is a distinct count across both.

### Product-16 account continuity

| Account comparison | Count |
|---|---:|
| Present in both June and July live tables | 5,574 |
| Present in June but absent from July live table | 81 |
| New in July live table | 179 |
| Net account increase | 98 |

July live `GENLNACNTS` is therefore authoritative for product 16; it is not merely the
June table plus new rows.

### Portfolio monetary movement

| Measure | June full portfolio | July full portfolio | Change |
|---|---:|---:|---:|
| Sanctioned/disbursed | ₹3,076,186,367.69 | ₹3,125,636,367.69 | +₹49,450,000.00 |
| Cumulative principal repaid | ₹209,144,116.00 | ₹248,898,502.03 | +₹39,754,386.03 |

The July full value combines current product 16 with the unchanged product-1/product-13
archive. It does not double-count any account ID.

## Core/report table comparison

| Oracle table | June rows | July rows | Difference | PostgreSQL silver rows | PG status |
|---|---:|---:|---:|---:|---|
| `GENLNACNTS` | 13,510 | 5,753 | -7,757 | 5,753 | Exact July match |
| `GENLNACNTS_29102024` | Not used | 7,855 | — | 7,855 | Exact July match |
| `GENLN_RPT_DAY` | 18,587 | 18,587 | 0 | 18,587 | Exact July match |
| `GENLNDISB` | 5,481 | 5,696 | +215 | 5,696 | Exact July match |
| `LOANREPAY` | 13,483 | 18,836 | +5,353 | 18,836 | Exact July match |
| `LOANSCHEDULE` | 260,437 | 225,132 | -35,305 | 225,132 | Exact July match |
| `CIFDATA` | Absent | 17,972 | — | 17,972 | Exact July match |
| `ACNTS` | Absent | 5,846 | — | 5,846 | Exact July match |
| `ACNTBAL` | 5,667 | 5,846 | +179 | 5,846 | Exact July match |
| `ACNTLINK` | Absent | 5,846 | — | 5,846 | Exact July match |
| `MBRN` | Absent | 67 | — | 67 | Exact July match |
| `GLBALASONHIST` | Absent | 203,933 | — | 203,933 | Exact July match |
| `GLBBAL` | 1,221 | 1,302 | +81 | 1,302 | Exact July match |
| `NBFC_ALM_MAIN_DTL_II` | Absent | 6,724 | — | 6,724 | Exact July match |
| `NBFC_ALM_DTL_II` | Absent | 693 | — | 693 | Exact July match |
| `MIG_SHARE_DETAILS` | 4,079 | 4,079 | 0 | 4,079 | Exact July match |
| `GENLNRCPT` | 34,605 | 46,144 | +11,539 | 46,144 | Exact July match |
| `LNACLED` | 77,003 | 94,124 | +17,121 | 94,124 | Exact July match |
| `LNACLED_OS` | 85,446 | 102,321 | +16,875 | 102,321 | Exact July match |
| `LNACLEDBRKUP` | 31,526 | 36,878 | +5,352 | 36,878 | Exact July match |

All listed PostgreSQL silver tables reconcile exactly to the July Oracle source by row
count. This confirms that the current application database represents July, not the
temporary June dump.

`LOANSCHEDULE` falling by 35,305 rows requires business interpretation, but it is not a
migration loss: PostgreSQL exactly matches July Oracle. Likely causes include schedule
regeneration, pruning, or closure processing.

## Reporting-date coverage

| Source | June Oracle maximum | July Oracle maximum | Report impact |
|---|---|---|---|
| `GENLN_RPT_DAY` | 2026-06-30 | 2026-06-30 | DNBS02 remains reportable only through June |
| `GLBALASONHIST` | Table absent | 2026-07-30 | No exact July 31 GL balance |
| `NBFC_ALM_MAIN_DTL_II` | Table absent | 2026-07-31 | DNBS4B July is reportable |

Consequences:

- DNBS02 must not show July until `GENLN_RPT_DAY` contains an exact 2026-07-31 snapshot.
- DNBS4B Structural and IRS can show July because the ALM fact reaches July 31.
- DNBS4A and DNBS13 are quarterly; July is not a completed quarter-end filing date.
- A July date in account/CIF tables does not make every report July-reportable.

## Curiosity graph action

The graph now uses this July-authoritative portfolio definition:

```sql
SELECT * FROM silver.loan_account_master
UNION ALL
SELECT * FROM silver.general_loan_accounts_oct_2024
WHERE gnlnac_prod_code IN (1, 13)
```

Controls implemented:

- The archive is restricted to legacy products 1 and 13.
- Live product 16 always comes from `silver.loan_account_master`.
- Account IDs do not overlap across the two inputs.
- Borrowers are deduplicated by customer ID.
- The UI separately displays 11,477 loan borrowers, 5,719 active borrowers, and 17,972
  registered CIF customers.
- Product, branch, scheme, borrower, search and monthly drill-downs use the same portfolio
  definition.
- Branch labels come from `silver.branch_master`.

## Recommendations

1. Treat `139.84.155.19` and its matching PostgreSQL silver tables as authoritative.
2. Retain the June dump only for reconciliation and audit, not application queries.
3. Preserve `GENLNACNTS_29102024`/`general_loan_accounts_oct_2024` while products 1 and
   13 remain absent from live `GENLNACNTS`.
4. Ask the Oracle owner why the 81 June product-16 accounts are absent in July and retain
   evidence of closure, migration, write-off, or deletion.
5. Ask the Oracle owner whether the 35,305-row schedule reduction was an approved rebuild.
6. Extend the Oracle `GENLN_RPT_DAY` batch through July before enabling July DNBS02.

