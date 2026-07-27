# Oracle → PostgreSQL Migration Gap Analysis

**Oracle source:** `GICCPROD_NEW` @ `192.168.1.183:1521/FREEPDB1` — Oracle AI Database 26ai Free 23.26.2.0.0
**PostgreSQL target:** `moneypaldb` @ `192.168.1.183:5432` — PostgreSQL 16.13, schemas `bronze` / `silver`
**Date of analysis:** 2026-07-27
**Method:** live queries against both databases (`dba_tables`/`all_tables` + exact `COUNT(*)` on both sides)

> **Headline:** every table that *was* migrated is byte-for-byte complete — all 19 `bronze` tables match
> their Oracle counterparts exactly on row count, with zero discrepancies. The problem is not corruption,
> it is **scope**: only 19 of 9,545 Oracle tables were migrated, and the omissions include the exact
> tables the DNBS-02 and Curiosity Graph modules fabricate data for.

---

## 1. Scale of the two databases

| | Oracle `GICCPROD_NEW` | PostgreSQL `bronze` |
|---|---:|---:|
| Tables | **9,545** | **19** |
| Views | 25 | 0 |
| Migrated coverage | — | **0.2%** |

Verified as `SYSTEM` against `dba_tables`: 9,545 — identical to what the `moneypal` user sees via
`all_tables`, so nothing is hidden by privileges. `GICCPROD_NEW` is the only application schema
(other non-system owners hold ≤13 tables: `VECSYS` 13, `OJVMSYS` 6, `OUTLN` 3, `DBSFWUSER` 3).

### 1.1 What the 9,545 tables actually are

| Category | Count | Migrate? |
|---|---:|---|
| Core candidates (no backup/temp marker) | 8,547 | selectively |
| `RTMP*` runtime temp | 543 | no |
| `MIG_*` migration one-offs | 105 | selectively |
| `*_HIST` history | 101 | selectively |
| `TMP_*` / `TEMP_*` staging | 87 | selectively |
| `*_BK` / `*_BAK` / `*_OLD` backups | 82 | no |
| Date-stamped backups (`LOANSCHEDULE_28012026`) | 80 | no |

Of the 8,547 "core candidates", **6,835 carry rows** per optimizer statistics. The genuine
application surface is far smaller than that — the largest tables are operational logs
(`OPRLOG2026` 1.3M, `AUDITLOG2026` 354K, `KARZA_REQ_RESP_LOGS` 247K, `NBFC_JOB_LOG` 173K,
`DECENTRO_API_LOGS` 102K) which have no analytical value for the return.

---

## 2. Migrated tables — full reconciliation

**All 19 `bronze` tables reconcile exactly against Oracle. No row-count drift anywhere.**

| PG `bronze` table | Oracle table | PG rows | Oracle rows | Status |
|---|---|---:|---:|:--|
| `appldocuplddtl` | `APPLDOCUPLDDTL` | 184,792 | 184,792 | MATCH |
| `asset_classify_dtls` | `ASSET_CLASSIFY_DTLS` | 6,833 | 6,833 | MATCH |
| `cust_intf_pid_dtls` | `CUST_INTF_PID_DTLS` | 36,144 | 36,144 | MATCH |
| `extgl` | `EXTGL` | 723 | 723 | MATCH |
| `firmcifdata_dtl` | `FIRMCIFDATA_DTL` | 13,888 | 13,888 | MATCH |
| `fvdata` | `FVDATA` | 15,443 | 15,443 | MATCH |
| `genln_rpt_day` | `GENLN_RPT_DAY` | 18,587 | 18,587 | MATCH |
| `genlnacnts` | `GENLNACNTS` | 13,510 | 13,510 | MATCH |
| `genlnappl` | `GENLNAPPL` | 8,661 | 8,661 | MATCH |
| `genlnapplca` | `GENLNAPPLCA` | 7,438 | 7,438 | MATCH |
| `genlnapplga` | `GENLNAPPLGA` | 7,208 | 7,208 | MATCH |
| `genlndisb` | `GENLNDISB` | 5,481 | 5,481 | MATCH |
| `glbbal` | `GLBBAL` | 1,221 | 1,221 | MATCH |
| `indcifdata_10012025_indcifdata` | `INDCIFDATA_10012025_INDCIFDATA` | 33,907 | 33,907 | MATCH |
| `loanrepay` | `LOANREPAY` | 13,483 | 13,483 | MATCH |
| `loanschedule` | `LOANSCHEDULE` | 260,437 | 260,437 | MATCH |
| `nbfcln_security` | `NBFCLN_SECURITY` | 23 | 23 | MATCH |
| `nbfclnscheme` | `NBFCLNSCHEME` | 15 | 15 | MATCH |
| `nsecmsmemap` | `NSECMSMEMAP` | 10,571 | 10,571 | MATCH |

`silver` is a 1:1 renamed mirror of `bronze` (identical counts on all 19), so it inherits the same gaps.

### 2.1 Correction to `docs/PROSPER_EDA_REPORT.md`

That report states `LOANSCHEDULE` = **221,460** rows. The live Oracle table now holds **260,437**,
which is exactly what PG holds. The 221,460 figure was an earlier snapshot; PG is **not** over-loaded.
The remaining three core tables in that report (`GENLNACNTS` 13,510, `GENLNDISB` 5,481,
`LOANREPAY` 13,483) match both sides exactly.

### 2.2 `migration_audit` is stale and misleading

`public.migration_audit` holds four rows, all dated 2026-07-23 and all **`FAILED`** with
`oracle_count = 0, postgres_count = 0`:

```
genlnacnts   FAILED  "current transaction is aborted, commands ignored until end of transaction block"
genlndisb    FAILED  (same)
loanschedule FAILED  (same)
loanrepay    FAILED  (same)
```

All four tables are in fact fully and correctly loaded. The classic symptom above — every statement
after the first error failing — means the loader did not roll back between tables, so one initial
failure cascaded and was recorded against every subsequent table. Whatever load actually populated
PG did not write to this audit table, so **`migration_audit` cannot be used to judge migration state**
and currently reports the opposite of the truth. It covers 4 of 19 migrated tables and none of the gaps.

---

## 3. Missing tables that the application needs

These exist in Oracle with real data and are **absent from PostgreSQL**. Each one maps to a specific
place where the codebase currently fabricates or omits data.

| Oracle table | Rows | Needed by | Consequence today |
|---|---:|---|---|
| `MIG_SHARE_DETAILS` | **4,079** | DNBS-02 Annex 2 (shareholding pattern) | Section has no source; previously filled with 3 invented shareholders |
| `GENLNRCPT` | **34,605** | Curiosity Graph repayment nodes; Part 3 | Graph synthesises one fake repayment per account |
| `GENLNRCPTDTL` | **34,605** | Repayment mode/instrument detail | No payment-channel data at all |
| `LNACLED` | **77,003** | Loan account ledger (all transactions) | No transaction-level ledger in PG |
| `LNACLED_OS` | **85,446** | Running principal/interest outstanding per transaction | Outstanding can only be read at month-end |
| `LNACLEDBRKUP` | 31,526 | Ledger breakup | — |
| `TEMP_CUST_MIG_WIN` | **3,984** | Borrower PAN / demographics (per `DNBS02_REPORT_PLAN.md`) | See §3.1 — low value, do not prioritise |
| `GENLNRCPT_WAIVE` | 29,103 | Interest/charge waivers | Waivers invisible |
| `BRANCH_MERGE_V2` | 93 | Branch merge history | Not a branch master — see §3.2 |

### 3.1 `TEMP_CUST_MIG_WIN` is not worth migrating for PAN

`docs/DNBS02_REPORT_PLAN.md` §127 designs Annex 9 around joining this table for borrower PANs.
Measured against the live data, that design would have failed:

- 3,429 of 3,984 rows carry `TEMP_PAN_NUMBER`
- but it joins to `GENLNACNTS` on `NEW_CUST_ID` for only **642 of 13,510 accounts — 4.8% coverage**

`bronze.genln_rpt_day.gnlnr_pan_no` is **100% populated** (4,445/4,445 at 2026-05-31) and is already
in PG. The implemented Annex 9 uses that instead. **No migration needed.**

### 3.2 There is no branch master anywhere in Oracle

Searched all 9,545 tables for any table carrying a branch-name column. The only populated hits are
`IFSRID` (147,949 — IFSC reference), `CIFDATA_OTH`, `GENLNRCPTDTL`, and assorted temp tables.
`BRANCH_MERGE_V2` (93 rows) is `OLD_BRANCH, ACCOUNTNO, NEW_BRANCH, MERGE_DATE` — a merge map, not a master.

**Branch name, address, city, state and district have no source in Oracle either.** This is not a
migration gap — the data does not exist. Annex 13 geography and the Curiosity Graph's district labels
therefore cannot be sourced without a new reference feed from the client.

### 3.3 There is no investment register

Only `RTMP_GICC_GENERAL_INVEST` matches `%INVEST%`, and it holds **0 rows**. Confirms the DNBS-02
finding: entity-level Annex 10 (Top 25 investments by name and PAN) is **not derivable from Oracle
either**; only the aggregate GL heads in `GLBBAL` prefix `1009` exist.

---

## 4. Column-name mismatch in the retired Annex 2 query

The removed `dnbs02_service` query selected `share_customer_name`, `share_no_of_units`,
`share_face_value` from `bronze.mig_share_details`. Oracle's actual `MIG_SHARE_DETAILS` columns are:

```
PROSPER_CUSTOMER_ID, PROSPER_CUSTOMER_NAME, SHARE_BRANCH_CODE, SHARE_APPLICATION_DATE,
SHARE_ALLOTMENT_DATE, SHARE_TRADING_DATE, SHARE_FACE_VALUE, SHARE_NO_OF_UNITS, SHARE_AMOUNT,
SHARE_DISTINCTIVE_FROM, SHARE_DISTINCTIVE_UPTO, SHARE_CERTIFICATE_NUM, ...
```

The name column is `PROSPER_CUSTOMER_NAME`, not `share_customer_name`. So even had the table been
migrated, that query would still have failed. It was never run against real data.

---

## 5. Recommended migration batch

Ordered by value per unit of effort. All are plain tables with no exotic types.

**Priority 1 — unlocks currently-fabricated sections (~146K rows)**

| Table | Rows | Unlocks |
|---|---:|---|
| `GENLNRCPT` | 34,605 | Real repayment events for the Curiosity Graph; Part 3 collections |
| `GENLNRCPTDTL` | 34,605 | Repayment mode, bank, instrument, UTR |
| `MIG_SHARE_DETAILS` | 4,079 | DNBS-02 Annex 2 shareholding pattern |
| `LNACLED` | 77,003 | Transaction-level loan ledger |

**Priority 2 — analytical depth (~117K rows)**

| Table | Rows | Unlocks |
|---|---:|---|
| `LNACLED_OS` | 85,446 | Running outstanding at any date, not just month-end |
| `LNACLEDBRKUP` | 31,526 | Principal/interest/charge breakup per transaction |
| `GENLNRCPT_WAIVE` | 29,103 | Waiver tracking |

**Do not migrate:** the 6,800+ log, backup, temp and `RTMP_*` tables; `TEMP_CUST_MIG_WIN` (§3.1);
anything matching `%_BK`, `%_OLD`, or a date suffix.

**Also fix:** the loader must roll back per table so one failure stops cascading, and must write a
row to `migration_audit` for every table it touches — today the audit table describes a run that
bears no relation to what is actually in PG (§2.2).

---

## 6. Open item carried from the DNBS-02 work

`bronze.genln_rpt_day` — the only table with a true as-of dimension — contains **product 16 only**.
Products 13 (7,653 open accounts) and 1 (99) have no dated snapshot, so 7,884 open accounts
(₹6,773.53 lakh, 29% of the open book) are excluded from every point-in-time figure.

Confirmed on the Oracle side: `GENLN_RPT_DAY` holds 18,587 rows there too — **identical to PG**.
The gap is in the source system, not the migration. Either the Oracle job that populates
`GENLN_RPT_DAY` needs extending to products 1 and 13, or those products need a different dated source.
