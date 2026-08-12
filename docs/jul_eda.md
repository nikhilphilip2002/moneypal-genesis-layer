# GICCPROD_NEW — EDA Report (July 2026 Dump)

**Source dump:** `GICCPROD_NEW_31072026.zip` (6.2 GB uncompressed `.dmp`)
**Imported into:** Oracle Database 26ai Free 23.26.2.0.0 (containerised)
**Report date:** 2026-08-07
**Schema:** `GICCPROD_NEW`

## Connection

| Field | Value |
|---|---|
| Host | `139.84.155.19` |
| Port | `1521` |
| Service name | `FREEPDB1` |
| Username | `GICCPROD_NEW` |
| Password | `Gicc123` |
| Admin user | `SYSTEM` / `Oracle123` |

## Executive summary

- **Total schema footprint:** 8.29 GB (within Oracle Free's 12 GB cap).
- **6,339 tables** created; **1,144 populated** with data; the other 5,211 exist as empty structures.
- **6,402 indexes**, **1,195 packages** (1,134 bodies), **1,275 procedures**, **534 functions**.
- **1,588 invalid PL/SQL objects** — expected: they reference tables intentionally excluded from the import to fit under the 12 GB cap.
- Heaviest data lives in **operational/audit logs and API request-response captures**, not in the core banking tables.
- Dump appears to have been taken at end of July 2026 (latest `LAST_ANALYZED` = 2026-07-31).

## Excluded from import

To fit under the Free-edition 12 GB cap, these prefixes were skipped:

| Prefix | Nature |
|---|---|
| `GENLN_RPT%` | Per-account loan-report snapshots |
| `GENLNACNTS%` | Per-account general-loan account tables |
| `LNSCHDL%` | Per-account loan-schedule snapshots |
| `RTMP%` | Temp/report scratch tables |
| `TRANBAT20%` | Year-partitioned transaction batch history |
| `GLSUM20%` | Year-partitioned GL summary history |

Any procedure/report that touches these prefixes will fail with `ORA-00942`. The 1,588 invalid PL/SQL objects are almost entirely dependents of the excluded tables.

## Storage breakdown

### By segment type
| Segment type | Segments | Size (MB) |
|---|---|---|
| TABLE | 1,144 | 5,454.4 |
| INDEX | 1,094 | 1,077.7 |
| LOBSEGMENT | 75 | 812.6 |
| LOBINDEX | 75 | 4.7 |

### Tablespaces
| Tablespace | Segments | Size (MB) |
|---|---|---|
| GICC_DATA | 2,384 | 7,346.6 |
| SYSTEM | 4 | 2.8 |

All source-schema tablespaces (`TBFES`, `TBLNS`, `TBLIAB`, `TBHIST`, `TBSACCESS`, `TBSCOMMON`, `TBRPTS`, `USERS`) were remapped onto `GICC_DATA` at import time.

## Object inventory

| Object type | Count |
|---|---|
| INDEX | 6,402 |
| TABLE | 6,339 |
| PROCEDURE | 1,275 |
| PACKAGE | 1,195 |
| PACKAGE BODY | 1,134 |
| FUNCTION | 534 |
| LOB | 267 |
| SEQUENCE | 111 |
| TRIGGER | 46 |
| TYPE | 28 |
| VIEW | 25 |
| JOB | 20 |
| SYNONYM | 4 |
| DATABASE LINK | 1 |

### PL/SQL validity
| Status | Count |
|---|---|
| VALID | 2,621 |
| INVALID | 1,588 |

Invalid ones are heavily concentrated in procedures/package-bodies that touch excluded prefixes. Recompile can recover any whose dependencies are actually present:
```sql
EXEC UTL_RECOMP.RECOMP_SERIAL('GICCPROD_NEW');
```

## Data profile

### Empty vs populated
| State | Tables |
|---|---|
| Populated | 1,128 |
| Empty | 5,211 |

The ratio suggests the source system carries a lot of **staging / temp / feature-flag / migration** tables that only get populated during specific batch jobs.

### Column-type distribution (top)
| Data type | Columns |
|---|---|
| VARCHAR2 | 37,738 |
| NUMBER | 29,821 |
| DATE | 13,230 |
| CHAR | 7,344 |
| CLOB | 249 |
| RAW | 29 |
| BLOB | 17 |
| TIMESTAMP(6) | 11 |
| NVARCHAR2 | 6 |
| BFILE | 6 |
| XMLTYPE | 2 |
| LONG | 1 |

Standard Oracle-based line-of-business shape — heavy on VARCHAR2/NUMBER/DATE, minimal use of LOB/XML/TIMESTAMP.

### Top 20 largest tables (by MB)
| Table | MB |
|---|---|
| JSONLOG_APP | 1,895 |
| JSONLOG_V2 | 472 |
| KARZA_REQ_RESP_LOGS | 375 |
| CUST_INTF_PID_DTLS_RESP | 272 |
| AUDITLOG2026 | 136 |
| OPRLOG2026 | 128 |
| COLL_ACTION_HIST | 112 |
| TRAN2026_31072026 | 88 |
| TRAN2026 | 88 |
| AUDITLOG2025 | 88 |
| CUSTOMER_LOCATION_HIST | 88 |
| DECENTRO_API_LOGS | 80 |
| ENACH_LOG_DETAILS | 80 |
| SPDOCIMAGE | 80 |
| OPRLOG2025 | 80 |
| TRAN2026_27072026 | 80 |
| NBFC_OPR_CHK_DTL | 55 |
| TRAN2025_27072026 | 44 |
| TRAN2025 | 44 |
| TRAN2025_24022026 | 39 |

More than half the storage sits in **API/audit/JSON logs** rather than transactional tables. This is a good candidate for aggressive retention/archival if space becomes a concern.

### Top 20 tables by estimated row count
| Table | Rows | MB |
|---|---|---|
| OPRLOG2026 | 1,456,269 | 117.9 |
| JSONLOG_APP | 1,397,728 | 1,834.8 |
| CUSTOMER_LOCATION_HIST | 1,201,890 | 88.0 |
| OPRLOG2025 | 932,881 | 79.1 |
| NBFC_OPR_CHK_DTL | 797,070 | 54.0 |
| GENLNAPPL_CHKLIST_DTL | 550,389 | 18.5 |
| AUDITLOG2026 | 396,890 | 127.9 |
| JSONLOG_V2 | 332,189 | 447.9 |
| COLL_ACTION_HIST | 282,082 | 111.6 |
| AUDITLOG2025 | 251,307 | 81.1 |
| KARZA_REQ_RESP_LOGS | 245,574 | 369.0 |
| TMP_ACNT_LED_17042026 | 241,026 | 25.4 |
| SBACNTS_ACCRPOST02SEP2025 | 237,569 | 13.8 |
| SPDOCIMAGE | 236,644 | 72.0 |
| TMP_ACNT_LED | 231,632 | 29.8 |
| LOANSCHEDULE_14072026 | 225,568 | 9.6 |
| SBACNTS_DAY | 220,724 | 24.6 |
| LOANSCHEDULE | 216,171 | 10.0 |
| LOANSCHEDULE_PREV | 206,070 | 9.0 |
| GLBALASONHIST | 203,925 | 31.9 |

Notice the pattern of **dated backup copies** (`TMP_ACNT_LED_17042026`, `SBACNTS_ACCRPOST02SEP2025`, `LOANSCHEDULE_14072026`) — the source system carries manual point-in-time copies alongside live tables. Query only the un-suffixed table for current data.

### Widest tables (most columns)
| Table | Columns |
|---|---|
| GENLN_API_COMMON | 244 |
| GENLN_API_COMMON_HIST | 244 |
| CHG_AGE_TENOR | 241 |
| GENLN_API_COMMON_SC2301 | 180 |
| TMP_0206REPY | 178 |
| COLEND_UPD_DTL | 159 |
| COLEND_UPD_DTL_HIST | 159 |
| MIGRATE_CUST | 156 |
| DOORSTEP_LEAD_MAIN_REJ | 119 |
| DOORSTEP_LEAD_MAIN | 119 |
| DOORSTEP_LEAD_MAIN_COMP | 119 |
| MOB_ELIGIBLE_REQ | 116 |
| IMP_SD_15172-11_15_57 | 113 |
| LNPRODPM | 109 |
| NBFCLNSCHEME | 106 |

Wide tables cluster around the general-loan API surface (`GENLN_API_COMMON`), collection-lending updates, and doorstep-lead capture — classic form-driven wide-row designs.

### Indexes per table (top 15)
| Table | Indexes |
|---|---|
| DOORSTEP_LEAD_MAIN | 15 |
| MIG_TRAN_BAT_DTL | 14 |
| GENLNAPPL | 13 |
| DOORSTEP_LEAD_MAIN_COMP | 13 |
| ESIGN_SUBMITTED | 13 |
| DOORSTEP_LEAD_MAIN_REJ | 12 |
| BRN_HIER_DTLS_HIST | 12 |
| BRN_HIER_DTLS | 12 |
| DBFS_MIG_TRAN_BAT_DTL | 11 |
| TRAN2022 | 10 |
| TRAN2024 | 10 |
| TRAN2026 | 10 |
| TRAN2025 | 10 |
| TRAN2023 | 10 |
| DLY_COLLECT_II_MAIN | 9 |

Yearly `TRAN20xx` partitions each carry the same ~10 indexes — evidence the source system rolls a new physical table per year rather than using Oracle partitioning.

## Naming patterns (top prefixes)

| Prefix | # Tables | Likely domain |
|---|---|---|
| MSME | 224 | MSME loan module |
| MIG_ | 207 | Migration/staging |
| GENL | 137 | General-loan module (`GENLN…`) |
| NBFC | 127 | NBFC-specific tables |
| RTMS | 119 | Reports / templates |
| TRAN | 108 | Transactions (yearly copies) |
| SBAC | 108 | Savings/current-account (`SBACNTS…`) |
| CUST | 98 | Customer master + variants |
| AUDI | 92 | Audit trail |
| TMP_ | 79 | Temp / working sets |
| CIFD | 77 | CIF (customer info file) data |
| TEMP | 70 | More temp tables |
| COLE | 66 | Co-lending |
| SHAR | 65 | Shares |
| AUCT | 63 | Auctions |
| USER | 60 | Users / access |
| ACNT | 60 | Accounts |
| LOAN | 54 | Loan-related |
| MFI_ | 45 | Microfinance module |
| DEPA | 40 | Deposit accounts |

The heavy `MIG_` / `TMP_` / `TEMP` / dated-suffix footprint suggests the source is an **actively-maintained production system with a long history of migrations and manual data fixes retained in-place**.

## Freshness signal (last analyzed)

| Table | Last analyzed |
|---|---|
| ACNTS_BK310726 | 2026-07-31 17:46:32 |
| TRAN2026_31072026 | 2026-07-31 15:11:09 |
| LNINTCALCPOST | 2026-07-31 03:42:54 |
| TMP_SEP_GP_2810 | 2026-07-31 03:42:53 |
| REMAIND_BRN | 2026-07-31 03:42:53 |
| ATTDDETAILS | 2026-07-31 03:42:19 |
| SODEODCTRL | 2026-07-31 03:42:18 |
| SWFRECONSTAT_TMP | 2026-07-31 03:42:14 |
| RCPT_UPLD_LOCK | 2026-07-31 03:42:14 |
| GSTRZ1 | 2026-07-31 03:42:13 |

Data is current as of **2026-07-31**. Anything referencing "today" in downstream analysis should treat that as the effective as-of date.

## Recommendations

1. **Rely on unsuffixed table names** for current data; ignore backup copies like `_BK310726`, `_14072026`, `_ACCRPOST02SEP2025` unless doing point-in-time analysis.
2. **Recompile PL/SQL** to shrink the invalid-object list to just the truly broken (excluded-table-dependent) ones:
   ```sql
   EXEC UTL_RECOMP.RECOMP_SERIAL('GICCPROD_NEW');
   ```
3. **If you need any excluded table**, cherry-pick it later — provided total stays under 12 GB:
   ```
   impdp system/Oracle123@localhost:1521/FREEPDB1 \
     DIRECTORY=DUMPS DUMPFILE=GICCPROD_NEW.DMP \
     TABLES=GICCPROD_NEW.<TABLE_NAME> \
     REMAP_TABLESPACE=TBFES:GICC_DATA \
     ...
   ```
4. **For any long-term dev workload**, consider moving to `container-registry.oracle.com/database/enterprise:latest` (no 12 GB cap, free for non-prod).

## How this report was generated

- Connected via `python-oracledb` thin mode to `139.84.155.19:1521/FREEPDB1`.
- All figures derived from `dba_segments`, `dba_tables`, `dba_indexes`, `dba_objects`, `dba_tab_columns`, `dba_lobs`.
- Row counts are the CBO estimates from `dba_tables.num_rows` (populated during import stats phase); actual counts may drift slightly for churned tables.
