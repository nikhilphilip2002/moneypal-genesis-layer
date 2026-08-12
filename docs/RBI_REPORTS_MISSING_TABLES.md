# RBI Reports Oracle → PostgreSQL Migration Handoff

**Prepared:** 2026-08-12  
**Oracle source schema:** `GICCPROD_NEW`  
**PostgreSQL target:** `moneypaldb`, schema `bronze`  
**Reports covered:** 5 report outputs packaged in 4 RBI workbooks  
**Purpose:** Supply or define every missing source required by the RBI workbooks in `docs/Fwd_ RBI REPORTS.zip`.

The five application report outputs are:

1. DNBS02 — Important Financial Parameters.
2. DNBS13 — Overseas Investment Details.
3. DNBS4A — Short-Term Dynamic Liquidity (STDL).
4. DNBS4B — Structural Liquidity.
5. DNBS4B — Interest Rate Sensitivity (IRS).

Outputs 4 and 5 are two separate statements inside the same DNBS4B monthly workbook and share RBI return code `R228`.

## Complete scope summary

| Report output | Oracle tables to migrate | Other source work |
|---|---:|---|
| DNBS02 | 7 | Reuse the existing 34-table bronze warehouse; enable the already migrated shareholder table; add non-Oracle reference feeds for governance, branches, ratings, and investment entities |
| DNBS13 | 0 | No qualifying Oracle source exists; create a controlled PostgreSQL reference/declaration feed |
| DNBS4A | 12 shared ALM tables | Shares its migrated table set with DNBS4B |
| DNBS4B Structural Liquidity | 12 shared ALM tables | Shares its migrated table set with DNBS4A and DNBS4B IRS |
| DNBS4B Interest Rate Sensitivity | Same 12 shared ALM tables | Second statement in the DNBS4B workbook; no additional migration batch |

The complete Oracle migration batch remains **19 unique durable tables**: 7 DNBS02 tables plus 12 tables shared by DNBS4A and both DNBS4B statements. DNBS13 is not an Oracle migration problem because its required source dataset does not exist in the Oracle schema.

## DNBS02: missing Oracle tables

Migrate these 7 tables for accurate period-end balances, repayments, outstanding balances, ledger breakup, and waivers.

| Priority | Oracle source table | PostgreSQL target | Estimated rows | Columns | Oracle primary key | Report use |
|---|---|---|---:|---:|---|---|
| P0 | `GLBALASONHIST` | `bronze.glbalasonhist` | 203,925 | 11 | `GLBALH_ENTITY_NUM`, `GLBALH_GLACC_CODE`, `GLBALH_BRN_CODE`, `GLBALH_CURR_CODE`, `GLBALH_ASON_DATE` | True as-of GL balances for Parts 1, 3, 4, 5, 6, 7, and 9; replaces year-only/current `GLBBAL` reporting |
| P0 | `GENLNRCPT` | `bronze.genlnrcpt` | 46,144 | 30 | `GENLNRCPT_ENTITY_NUM`, `GENLNRCPT_ACNT_NUM`, `GENLNRCPT_TRAN_DATE`, `GENLNRCPT_DAY_SL` | Actual loan repayment events and cash collections |
| P0 | `LNACLED` | `bronze.lnacled` | 85,932 | 13 | `LNACLED_ENTITY_NUM`, `LNACLED_ACNT_NO`, `LNACLED_TRAN_DATE`, `LNACLED_TRAN_DAYSL` | Transaction-level loan ledger |
| P0 | `LNACLED_OS` | `bronze.lnacled_os` | 95,263 | 28 | `LNACLEDO_ENTITY_NUM`, `LNACLEDO_ACNT_NO`, `LNACLEDO_TRAN_DATE`, `LNACLEDO_TRAN_DAYSL` | Principal, interest, asset classification, and running outstanding at transaction dates |
| P1 | `GENLNRCPTDTL` | `bronze.genlnrcptdtl` | 44,812 | 15 | `GENLNRCPTD_ENTITY_NUM`, `GENLNRCPTD_ACNT_NUM`, `GENLNRCPTD_TRAN_DATE`, `GENLNRCPTD_DAY_SL`, `GENLNRCPTD_RCPT_SL` | Repayment mode, instrument, and receipt detail |
| P1 | `LNACLEDBRKUP` | `bronze.lnacledbrkup` | 34,676 | 9 | `LNACBK_ENTITY_NUM`, `LNACBK_ACNT_NO`, `LNACBK_TRAN_DATE`, `LNACBK_TRAN_DAYSL` | Principal/interest/charge breakup for ledger movements |
| P1 | `GENLNRCPT_WAIVE` | `bronze.genlnrcpt_waive` | 36,931 | 16 | `GENLNRCPTW_ENTITY_NUM`, `GENLNRCPTW_ACNT_NUM`, `GENLNRCPTW_TRAN_DATE`, `GENLNRCPTW_DAY_SL` | Interest and charge waivers needed for complete income and collection reconciliation |

The following DNBS02 source is **already present** and must not be migrated again:

- Oracle `MIG_SHARE_DETAILS` → PostgreSQL `bronze.mig_share_details` for Annex 2. The application still needs to be updated to use its real Oracle column names.

The following DNBS02 gaps cannot be solved by migrating another Oracle table:

- Annex 3 board/director details: create controlled institutional reference data.
- Annex 10 investment entities and PANs: Oracle has aggregate investment GL balances but no populated entity-level investment register.
- Annex 13 now uses Oracle `MBRN` → PostgreSQL `silver.branch_master` for branch names,
  addresses, and opening/closing dates. `MBRN_LOCN_CODE` still has no approved location
  reference mapping, so city, state, and district require a client-maintained reference feed.
- Ratings, authorised signatory, group companies, overseas entities, and similar institutional disclosures: manage as effective-dated reference data with approval history.
- Do not migrate `TEMP_CUST_MIG_WIN`; borrower PAN coverage is poor and `GENLN_RPT_DAY.GNLNR_PAN_NO` is already available in PostgreSQL.

## DNBS13: no Oracle table to migrate

The Oracle schema was searched by table name, column name, and PL/SQL source for overseas investment, WOS, joint venture, RBI NOC, host-country regulator, and overseas-remittance concepts. No table contains the DNBS13 dataset.

Do not use these false matches:

- `RTMPRJOURVOUCH*`: `JV` means journal voucher, not joint venture.
- `SI_SHARE_INVEST_INFO` and `SI_SHARE_INVEST_SCHM_CONFIG`: insurance/loyalty benefit configuration, not investments.
- `RTMPIRWOS`: interest-warrant report scratch data, not an overseas WOS register.
- Transaction `REMITTANCE_CODE` columns: ordinary transaction metadata without the DNBS13 entity, country, RBI NOC, regulator, or performance fields.

Create an effective-dated, audited PostgreSQL reference table instead. At minimum it must hold:

- Reporting institution and reporting period.
- JV/WOS name and country.
- Incorporation date and RBI NOC date/reference.
- Business undertaken.
- Remittance during the quarter.
- Aggregate overseas investment and NOF percentage.
- Host-country regulation flag and regulator name.
- Whether the entity is operational and its financial-performance fields required by the workbook.
- Maker, checker, approval timestamp, source document, effective-from, and effective-to.

If GICC has no overseas JV/WOS, store an approved effective-dated `not_applicable` declaration. Do not infer non-applicability merely from an empty table and do not manufacture zero-valued entities.

## DNBS4A / DNBS4B: shared migration scope

Migrate all 12 shared tables below. Use lowercase Oracle table names in PostgreSQL and preserve every source column, converting column names to lowercase in the same way as the existing `bronze` tables.

Oracle statistics are included only as sizing guidance. They are not acceptance row counts: the Oracle database is active, and the ALM fact-table counts changed while this analysis was running. Extract all tables from one consistent Oracle SCN or Data Pump snapshot.

| Priority | Oracle source table | PostgreSQL target | Estimated rows | Columns | Oracle primary key | Reason required |
|---|---|---|---:|---:|---|---|
| P0 | `NBFC_ALM_DTL_II` | `bronze.nbfc_alm_dtl_ii` | 633 | 13 | None declared | Saved ALM bucket totals and category descriptions |
| P0 | `NBFC_ALM_DTL_II_CONFIG` | `bronze.nbfc_alm_dtl_ii_config` | 10 | 4 | None declared | Maturity-bucket boundaries and units |
| P0 | `NBFC_ALM_MAIN_DTL_II` | `bronze.nbfc_alm_main_dtl_ii` | 6,154 | 22 | None declared | Detailed ALM facts by date, category, product, scheme, principal/interest, and payable/receivable direction |
| P0 | `DEPOSIT_PROD` | `bronze.deposit_prod` | 8 | 33 | `DP_ENTITY_NUM`, `DP_PROD_CODE` | Deposit product classification |
| P0 | `DEPOSIT_SCHM` | `bronze.deposit_schm` | 83 | 50 | `DS_ENTITY_NUM`, `DS_PROD_CODE`, `DS_SCHM_CODE` | Deposit scheme and maturity classification |
| P0 | `LNINTRTDTL` | `bronze.lnintrtdtl` | 317 | 11 | `LNINTRTD_ENTITY_NUM`, `LNINTRTD_PROD_CODE`, `LNINTRTD_SCHM_CODE`, `LNINTRTD_FROM_AMT`, `LNINTRTD_UPTO_AMT`, `LNINTRTD_UPTO_DAYS` | Loan interest-rate bands needed for interest-rate sensitivity |
| P0 | `INSTALL` | `bronze.install` | 1 | 33 | `INS_ENTITY_NUM` | Institution-level configuration used by the Oracle ALM packages |
| P1 | `DEPACNTS` | `bronze.depacnts` | 0 | 56 | `DEPACNTS_ENTITYNUM`, `DEPACNTS_DEPACNUM` | Deposit-account source; currently empty but required for future-period completeness |
| P1 | `DEPACNTS_DEMAT` | `bronze.depacnts_demat` | 0 | 31 | `DEPACNTS_ENTITYNUM`, `DEPACNTS_ISIN_NUM`, `DEPACNTS_PROD_CODE`, `DEPACNTS_SCHM_CODE` | Dematerialized deposit/instrument details |
| P1 | `PUBLIC_ISSUE_SCHEME` | `bronze.public_issue_scheme` | 0 | 35 | `PIS_ENTITY_NUM`, `PIS_ISSUE_NUM`, `PIS_SCHEME_NUM` | Public issues, bonds, and maturity terms |
| P1 | `SBACNTS` | `bronze.sbacnts` | 0 | 41 | `SB_ENTITY_NUM`, `SB_ACNT_NUM` | Savings/deposit account master used by the full ALM package |
| P1 | `SBACNTSINTADJ_FUT` | `bronze.sbacntsintadj_fut` | 0 | 9 | `SBTAF_ENTITY_NUM`, `SBTAF_CUST_ID`, `SBTAF_ACNTS`, `SBTAF_EFF_DATE` | Future interest adjustments used in contractual cash flows |

P0 tables are required to reproduce the currently populated DNBS4 data. P1 tables are presently empty in Oracle but must still be migrated with their complete structure so a later filing does not silently omit newly introduced deposits or instruments.

## DNBS4 tables already present in PostgreSQL

Do not create duplicate copies of these tables. They already exist in `bronze`, but their Oracle/PostgreSQL row counts and column definitions should be reconciled as part of the same migration run.

| Oracle table | Existing PostgreSQL table | Current PostgreSQL rows |
|---|---|---:|
| `GENLNACNTS` | `bronze.genlnacnts` | Existing |
| `NBFCLNSCHEME` | `bronze.nbfclnscheme` | Existing |
| `DEPOSIT_ADD_DETAILS` | `bronze.deposit_add_details` | 83 |
| `RTMP_ALM_XLS_RPT` | `bronze.rtmp_alm_xls_rpt` | 0 |
| `RTMP_NBFC_ALM_MAIN_II` | `bronze.rtmp_nbfc_alm_main_ii` | 1 |

## DNBS4 transient tables not to use as report sources

The following Oracle tables are package scratch/output tables. Do **not** migrate them as authoritative report data:

- `RTMP_ALM_XLS_RPT`
- `RTMP_NBFC_ALM_DTL_II`
- `RTMP_NBFC_ALM_MAIN_DTL_II`
- `RTMP_NBFC_ALM_MAIN_II`
- `RTMP_USER_NBFC_ALM_II`

`RTMP_ALM_XLS_RPT` is already present in PostgreSQL but empty. Its contents are produced transiently by Oracle packages `PKG_NBFC_ALM_II` and `PKG_NBFC_ALM_II_T234`. The Moneypal report service will calculate deterministic output from the durable tables instead.

## Required extraction rules

1. Extract all 19 tables using one consistent Oracle SCN or a single Data Pump snapshot.
2. Read from `GICCPROD_NEW`; do not copy similarly named dated, backup, or suffixed tables.
3. Preserve every column, including empty and nullable columns.
4. Convert Oracle unquoted identifiers to lowercase PostgreSQL identifiers.
5. Use these type conversions unless the existing ingestion pipeline specifies a stricter mapping:
   - `NUMBER(p,0)` → `numeric(p,0)` or `bigint` only when the range has been proven safe.
   - Other `NUMBER` values → `numeric` without loss of scale.
   - `VARCHAR2` / `CHAR` → `varchar` / `char` while preserving declared length.
   - `DATE` → `timestamp without time zone`, matching the existing bronze convention.
6. Preserve Oracle primary keys shown above. Do not invent primary keys for the three ALM tables that have none declared.
7. Record source SCN, extraction time, source row count, target row count, and a deterministic checksum for each table.
8. Load into staging tables first, validate them, and then promote the complete set together so reports cannot observe a partially migrated ALM snapshot.

## Validation after migration

### 1. Confirm that every required target exists

```sql
WITH required(table_name) AS (
    VALUES
        ('depacnts'),
        ('depacnts_demat'),
        ('deposit_prod'),
        ('deposit_schm'),
        ('genlnrcpt'),
        ('genlnrcpt_waive'),
        ('genlnrcptdtl'),
        ('glbalasonhist'),
        ('install'),
        ('lnintrtdtl'),
        ('lnacled'),
        ('lnacled_os'),
        ('lnacledbrkup'),
        ('nbfc_alm_dtl_ii'),
        ('nbfc_alm_dtl_ii_config'),
        ('nbfc_alm_main_dtl_ii'),
        ('public_issue_scheme'),
        ('sbacnts'),
        ('sbacntsintadj_fut')
)
SELECT r.table_name,
       CASE WHEN t.table_name IS NULL THEN 'MISSING' ELSE 'PRESENT' END AS status
FROM required r
LEFT JOIN information_schema.tables t
  ON t.table_schema = 'bronze'
 AND t.table_name = r.table_name
ORDER BY r.table_name;
```

Acceptance: all 19 rows report `PRESENT`.

### 2. Capture PostgreSQL row counts

```sql
SELECT 'nbfc_alm_dtl_ii' AS table_name, COUNT(*) FROM bronze.nbfc_alm_dtl_ii
UNION ALL
SELECT 'nbfc_alm_dtl_ii_config', COUNT(*) FROM bronze.nbfc_alm_dtl_ii_config
UNION ALL
SELECT 'nbfc_alm_main_dtl_ii', COUNT(*) FROM bronze.nbfc_alm_main_dtl_ii
UNION ALL
SELECT 'deposit_prod', COUNT(*) FROM bronze.deposit_prod
UNION ALL
SELECT 'deposit_schm', COUNT(*) FROM bronze.deposit_schm
UNION ALL
SELECT 'lnintrtdtl', COUNT(*) FROM bronze.lnintrtdtl;
```

Acceptance: each target count must equal the source count captured at the extraction SCN, not the estimates in this document.

### 3. Validate column parity

For each table, compare the ordered Oracle `ALL_TAB_COLUMNS` result with PostgreSQL `information_schema.columns`. Column names, nullability, precision, scale, and declared string lengths must be accounted for.

### 4. Validate the ALM business grain

After migration, provide these control totals from both databases at the same SCN:

- Minimum and maximum `NBFC_ASON_DATE`.
- Distinct `NBFC_ASON_DATE` count.
- Row count by `NBFC_ASON_DATE`.
- Sum of `NBFC_COL1` through `NBFC_COL10` by date for `NBFC_ALM_MAIN_DTL_II`.
- Row count by `NBFC_CATEGORY`, `NBFC_PROD_CD`, `NBFC_SCHM_CD`, `NBFC_PRINC_INT`, and `NBFC_PAY_RECV`.
- Duplicate count across the full logical grain because the ALM tables do not declare primary keys.

## Migration completion evidence

Please provide the following when the migration is finished:

- Oracle source SCN or Data Pump export identifier.
- Extraction and load timestamps.
- Source and target row counts for all 19 Oracle tables.
- Column-parity results.
- Control-total comparison for the three populated ALM tables.
- Any rejected or truncated values.
- Confirmation that the load was promoted atomically.

Once these checks pass, the application can create normalized `silver` models for DNBS02, DNBS4A, and DNBS4B. DNBS13 implementation can proceed after its controlled reference schema and an applicability declaration are approved.
