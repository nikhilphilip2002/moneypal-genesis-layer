# Regulatory supplemental data

Some RBI disclosures required by DNBS02, DNBS13, DNBS4A, and DNBS4B do not exist in
the Oracle operational schema. The report generator supports those disclosures through
maker/checker-approved PostgreSQL values rather than fabricated defaults.

## Migration

Run [`backend/scripts/sql/regulatory_reference_tables.sql`](../backend/scripts/sql/regulatory_reference_tables.sql)
with the PostgreSQL migration owner. It creates:

- `silver.regulatory_report_values`: approved values for currently blank workbook cells.
- `silver.regulatory_report_declarations`: an approved declaration that a return is
  complete or not applicable for a reporting date.

The complete deployment, loading, cell-mapping, validation, and handoff procedure is in
[`REGULATORY_REFERENCE_MIGRATION.md`](REGULATORY_REFERENCE_MIGRATION.md).

The application reads approved rows only. A value must have a source document, separate
maker and checker, approval timestamp, and effective dates. Exactly one typed value
(numeric, text, date, or boolean) is permitted per row.

## Loading rules

1. Use one of the five application report IDs: `dnbs02`, `dnbs13`, `dnbs4a`,
   `dnbs4b_structural`, or `dnbs4b_irs`.
2. Set `reporting_date` to the exact report period end.
3. Set `sheet_name` and `target_cell` to a blank data cell in the corresponding clean
   workbook template.
4. Load values in the unit printed by the workbook (`LAKHS` or `THOUSANDS`).
5. Do not load totals already calculated by the generator or target a populated cell;
   generation will fail instead of overwriting it.
6. Add a `complete` declaration only after every required cell has been reviewed. For a
   genuinely inapplicable DNBS13 return, use an approved `not_applicable` declaration.

This mechanism covers CRAR/RWA, controlled expense mappings, MSME size classifications,
investment-entity disclosures, branch geography, DNBS13 overseas-investment details,
and DNBS4 liability/investment/OBS or repricing positions once their approved values are
loaded. The existing Oracle-derived calculations remain the primary source and cannot be
overridden.
