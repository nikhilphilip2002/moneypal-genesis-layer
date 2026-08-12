# Regulatory reference-data migration handoff

**Prepared:** 2026-08-12  
**PostgreSQL target:** `192.168.1.183:5432/moneypaldb`  
**Target schema:** `silver`  
**Application read role:** `moneypal`  
**Reports:** `dnbs02`, `dnbs13`, `dnbs4a`, `dnbs4b_structural`, `dnbs4b_irs`

## Purpose

Oracle does not contain several disclosures required by the five RBI outputs. This
migration creates controlled PostgreSQL inputs for those values. It does not invent
data and does not replace Oracle-derived calculations. Approved values can populate
only cells that are blank when the report is generated.

The executable migration is:

[`backend/scripts/sql/regulatory_reference_tables.sql`](../backend/scripts/sql/regulatory_reference_tables.sql)

## Objects created

### `silver.regulatory_report_values`

One maker/checker-approved value for one workbook cell and reporting date.

| Column | Type | Required | Meaning |
|---|---|---:|---|
| `regulatory_value_id` | `bigint identity` | Yes | Surrogate primary key |
| `report_id` | `text` | Yes | One of the five application report IDs |
| `reporting_date` | `date` | Yes | Exact period-end date used by the generator |
| `sheet_name` | `text` | Yes | Exact clean-template worksheet name |
| `target_cell` | `varchar(12)` | Yes | Uppercase Excel coordinate such as `C35` |
| `value_numeric` | `numeric` | Conditional | Monetary, percentage or count value |
| `value_text` | `text` | Conditional | Text disclosure |
| `value_date` | `date` | Conditional | Date disclosure; exported as `DD/MM/YYYY` |
| `value_boolean` | `boolean` | Conditional | Boolean disclosure |
| `unit` | `text` | No | Normally `LAKHS`, `THOUSANDS`, `PERCENT`, or `COUNT` |
| `source_document` | `text` | Yes | Board paper, audited schedule, register, or source-file reference |
| `maker` | `text` | Yes | Person preparing the value |
| `checker` | `text` | Yes | Different person approving the value |
| `approved_at` | `timestamptz` | Yes | Approval timestamp |
| `effective_from` | `date` | Yes | First date for which approval applies |
| `effective_to` | `date` | No | Last applicable date; `NULL` means open-ended |
| `created_at` | `timestamptz` | Yes | Database insertion timestamp |

Exactly one of `value_numeric`, `value_text`, `value_date`, or `value_boolean` must be
set. Duplicate values for the same report, date, sheet, cell, and effective start date
are rejected.

### `silver.regulatory_report_declarations`

Period-level approval declaring a report complete or not applicable.

| Column | Type | Required | Meaning |
|---|---|---:|---|
| `report_id` | `text` | Yes | Application report ID |
| `reporting_date` | `date` | Yes | Exact period-end date |
| `coverage_status` | `text` | Yes | `complete` or `not_applicable` |
| `declaration_text` | `text` | Yes | Approved basis for the declaration |
| `source_document` | `text` | Yes | Approval evidence |
| `maker`, `checker` | `text` | Yes | Separate preparer and approver |
| `approved_at` | `timestamptz` | Yes | Approval timestamp |
| `effective_from`, `effective_to` | `date` | Yes/No | Effective-date window |

Do not add a `complete` declaration merely because rows were loaded. It means every
required disclosure for that return and date has been reviewed.

## Deployment procedure

1. Connect using the database migration owner. Do not use the NLQ read-only role.
2. Take a schema-only backup of any existing objects with the same names.
3. Execute the migration as one transaction:

   ```bash
   psql -h 192.168.1.183 -p 5432 -U <migration-owner> -d moneypaldb \
     -v ON_ERROR_STOP=1 \
     -f backend/scripts/sql/regulatory_reference_tables.sql
   ```

4. Give the application read-only access:

   ```sql
   GRANT USAGE ON SCHEMA silver TO moneypal;
   GRANT SELECT ON silver.regulatory_report_values TO moneypal;
   GRANT SELECT ON silver.regulatory_report_declarations TO moneypal;
   ```

5. Give INSERT/UPDATE permission only to the controlled regulatory-data loader role,
   not to `moneypal` and not to the NLQ role.
6. Load and validate approved values for one reporting date before bulk-loading history.

No password is stored in this document or migration file.

## Workbook targeting rules

- Use the sheet name and cell coordinate from the clean templates under
  `backend/app/assets/`.
- The report generator rejects unknown sheets, coordinates outside the template, and
  attempts to overwrite headings, formulas, Oracle-derived figures, or other populated
  cells.
- Use the unit printed in each workbook: DNBS02 and DNBS13 use lakhs; DNBS4A and DNBS4B
  use thousands.
- Store dates in `value_date`, not as text.
- Monetary totals already calculated from silver facts must not be loaded again.

### DNBS02 target areas

| Missing disclosure | Sheet/cells | Notes |
|---|---|---|
| Expense mapping | `DNBS02_PART3!C35:D55` | Column C amount; column D cumulative amount since 1 April |
| MSME size split | `DNBS02_PART8A!C17:I23` | Micro/small/medium counts, exposures and rates |
| Risk-weighted assets | `DNBS02_PART9!D13:F68` | Book value, risk weight and adjusted value |
| Investment entity attributes | `DNBS02_Annex10!B13:H35` | Load only blank cells that reconcile one-to-one with generated investment rows |
| Branch geography | `DNBS02_Annex13!E13:G13` and subsequent generated rows | City, state and district |

Borrower type is no longer supplemental: the application now maps CIF type `I`/`C` to
`Individual`/`Corporate`. Branch name, address and opening/closing dates also come from
`silver.branch_master`.

### DNBS13 target areas

- JV/WOS details: `DNBS13!B13:Q13`.
- Partner details: `DNBS13!B16:F16`.
- If more rows are required, first extend the approved clean template and its tests; do
  not target coordinates outside the current template.
- If the institution has no overseas JV/WOS, load no fabricated zero row. Insert an
  approved `not_applicable` declaration instead.

### DNBS4A target areas

- Main statement: rows 12–87, buckets `C:G`, total `H`.
- OBS outflows/inflows: rows 91–180, buckets `C:G`, total `H`.
- Existing performing-advance interest inflow is generated from the ALM fact and cannot
  be overwritten.

### DNBS4B structural-liquidity target areas

- Rows 13–198.
- Ten maturity buckets: `C:L`.
- Total: `M`; remarks: `N`; actual previous-month flow: `O`.
- Existing performing term-loan cashflows are generated from
  `silver.nbfc_alm_main_detail_ii` and cannot be overwritten.

### DNBS4B interest-rate-sensitivity target areas

- Main IRS table rows 12–192 uses buckets `C`, `D`, `F:N`, non-sensitive `O`, total `P`.
- OBS IRS table rows 198 onward uses buckets `C:L`, non-sensitive `M`, total `N`.
- Existing performing term-loan parent values cannot be overwritten. Approved fixed-rate,
  floating-rate, liability, investment and OBS positions may fill currently blank cells.

## Example loads

Replace all example values and evidence references with approved source data.

### DNBS02 branch geography

```sql
INSERT INTO silver.regulatory_report_values
    (report_id, reporting_date, sheet_name, target_cell, value_text, unit,
     source_document, maker, checker, approved_at, effective_from)
VALUES
    ('dnbs02', DATE '2026-06-30', 'DNBS02_Annex13', 'E13', '<approved-city>', NULL,
     '<branch-register-reference>', '<maker>', '<checker>', now(), DATE '2026-06-30'),
    ('dnbs02', DATE '2026-06-30', 'DNBS02_Annex13', 'F13', '<approved-state>', NULL,
     '<branch-register-reference>', '<maker>', '<checker>', now(), DATE '2026-06-30'),
    ('dnbs02', DATE '2026-06-30', 'DNBS02_Annex13', 'G13', '<approved-district>', NULL,
     '<branch-register-reference>', '<maker>', '<checker>', now(), DATE '2026-06-30');
```

### DNBS02 expense amount

```sql
INSERT INTO silver.regulatory_report_values
    (report_id, reporting_date, sheet_name, target_cell, value_numeric, unit,
     source_document, maker, checker, approved_at, effective_from)
VALUES
    ('dnbs02', DATE '2026-06-30', 'DNBS02_PART3', 'C35', <amount-lakhs>, 'LAKHS',
     '<audited-expense-schedule>', '<maker>', '<checker>', now(), DATE '2026-06-30');
```

### DNBS13 not-applicable declaration

```sql
INSERT INTO silver.regulatory_report_declarations
    (report_id, reporting_date, coverage_status, declaration_text, source_document,
     maker, checker, approved_at, effective_from)
VALUES
    ('dnbs13', DATE '2026-06-30', 'not_applicable',
     '<approved statement that the institution held no overseas JV/WOS>',
     '<board-or-compliance-approval-reference>', '<maker>', '<checker>', now(),
     DATE '2026-06-30');
```

### DNBS4B approved liability bucket

```sql
INSERT INTO silver.regulatory_report_values
    (report_id, reporting_date, sheet_name, target_cell, value_numeric, unit,
     source_document, maker, checker, approved_at, effective_from)
VALUES
    ('dnbs4b_structural', DATE '2026-06-30', 'DNBS4BStructuralLiquidity',
     'C40', <amount-thousands>, 'THOUSANDS', '<deposit-maturity-schedule>',
     '<maker>', '<checker>', now(), DATE '2026-06-30');
```

## Post-migration validation

### Confirm objects and privileges

```sql
SELECT to_regclass('silver.regulatory_report_values') AS values_table,
       to_regclass('silver.regulatory_report_declarations') AS declarations_table;

SELECT grantee, table_name, privilege_type
FROM information_schema.role_table_grants
WHERE table_schema = 'silver'
  AND table_name IN ('regulatory_report_values', 'regulatory_report_declarations')
ORDER BY table_name, grantee, privilege_type;
```

Acceptance: both objects exist; `moneypal` has `SELECT` only.

### Validate a reporting date

```sql
SELECT report_id, reporting_date, COUNT(*) AS approved_cells,
       COUNT(DISTINCT (sheet_name, target_cell)) AS distinct_targets
FROM silver.regulatory_report_values
WHERE reporting_date = DATE '2026-06-30'
GROUP BY report_id, reporting_date
ORDER BY report_id;

SELECT report_id, reporting_date, coverage_status, checker, approved_at,
       source_document
FROM silver.regulatory_report_declarations
WHERE reporting_date = DATE '2026-06-30'
ORDER BY report_id;
```

Acceptance: cell count equals distinct-target count, every row has traceable evidence,
and declarations exist only for genuinely complete or inapplicable returns.

### Application acceptance

1. Generate each applicable report for the exact loaded date.
2. Confirm supplemental values appear only in their approved cells.
3. Confirm Oracle-derived values are unchanged.
4. Confirm workbook sheet names, merged cells, formulas, styles and dimensions match the
   clean reference template.
5. Confirm DNBS13 changes from `blocked` to `not_applicable` or `complete` only when an
   approved declaration exists.
6. Run:

   ```bash
   PYTHONPATH=backend .venv/bin/pytest -q \
     backend/tests/test_approved_report_values.py \
     backend/tests/test_dnbs02_report.py \
     backend/tests/test_regulatory_reports.py
   ```

Current code baseline: **73 targeted tests passing** before the reference tables are
loaded.

## Migration evidence to return

Provide:

- Migration execution timestamp and database owner.
- DDL checksum or commit identifier.
- Grants applied to application and loader roles.
- Row counts by report ID and reporting date.
- Source-document references and maker/checker evidence.
- Generated workbook comparison results for all five outputs.
- Any rejected target cells or attempted overwrites.

