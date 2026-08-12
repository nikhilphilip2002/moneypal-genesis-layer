-- Controlled silver inputs for RBI fields that do not exist in the Oracle warehouse.
-- Run with the migration owner, not the application/NLQ read-only role.

BEGIN;

CREATE TABLE IF NOT EXISTS silver.regulatory_report_values (
    regulatory_value_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    report_id text NOT NULL CHECK (
        report_id IN ('dnbs02', 'dnbs13', 'dnbs4a', 'dnbs4b_structural', 'dnbs4b_irs')
    ),
    reporting_date date NOT NULL,
    sheet_name text NOT NULL,
    target_cell varchar(12) NOT NULL CHECK (target_cell ~ '^[A-Z]{1,3}[1-9][0-9]{0,5}$'),
    value_numeric numeric,
    value_text text,
    value_date date,
    value_boolean boolean,
    unit text,
    source_document text NOT NULL,
    maker text NOT NULL,
    checker text NOT NULL CHECK (checker <> maker),
    approved_at timestamp with time zone NOT NULL,
    effective_from date NOT NULL,
    effective_to date,
    created_at timestamp with time zone NOT NULL DEFAULT now(),
    CHECK (effective_to IS NULL OR effective_to >= effective_from),
    CHECK (num_nonnulls(value_numeric, value_text, value_date, value_boolean) = 1),
    UNIQUE (report_id, reporting_date, sheet_name, target_cell, effective_from)
);

CREATE INDEX IF NOT EXISTS regulatory_report_values_lookup_idx
    ON silver.regulatory_report_values (report_id, reporting_date, approved_at)
    WHERE approved_at IS NOT NULL;

CREATE TABLE IF NOT EXISTS silver.regulatory_report_declarations (
    regulatory_declaration_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    report_id text NOT NULL CHECK (
        report_id IN ('dnbs02', 'dnbs13', 'dnbs4a', 'dnbs4b_structural', 'dnbs4b_irs')
    ),
    reporting_date date NOT NULL,
    coverage_status text NOT NULL CHECK (coverage_status IN ('complete', 'not_applicable')),
    declaration_text text NOT NULL,
    source_document text NOT NULL,
    maker text NOT NULL,
    checker text NOT NULL CHECK (checker <> maker),
    approved_at timestamp with time zone NOT NULL,
    effective_from date NOT NULL,
    effective_to date,
    created_at timestamp with time zone NOT NULL DEFAULT now(),
    CHECK (effective_to IS NULL OR effective_to >= effective_from),
    UNIQUE (report_id, reporting_date, effective_from)
);

COMMIT;
