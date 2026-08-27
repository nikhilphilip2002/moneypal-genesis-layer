-- Production remediation for the consolidated Gold semantic layer.
--
-- Safe to rerun. CREATE OR REPLACE preserves the view names and schemas; the
-- explicit grant makes all 18 governed semantic views readable by NLQ.
-- Run as the Gold view owner with ON_ERROR_STOP enabled so the transaction is
-- all-or-nothing.

\set ON_ERROR_STOP on

BEGIN;
SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '60s';

-- Source hierarchy tables retain repeated upload snapshots. Keep only the most
-- recently uploaded version of each business relationship while preserving the
-- winning row's version and upload timestamp for lineage.
CREATE OR REPLACE VIEW gold.semantic_organization_hierarchy AS
WITH source_rows AS (
    SELECT
        'sales'::text AS hierarchy_type,
        s.hierarchy_version,
        s.entity_num::text AS entity_num,
        s.user_id::text AS actor_user_id,
        s.role_code::text AS actor_role_code,
        s.manager_user_id::text AS manager_user_id,
        s.effective_from,
        s.effective_to,
        s.manager_effective_from,
        s.remarks::text AS remarks,
        s.uploaded_on::timestamp with time zone AS uploaded_on,
        s.source_systems
    FROM gold.sales_team_hierarchy s

    UNION ALL

    SELECT
        'collections'::text AS hierarchy_type,
        c.hierarchy_version,
        c.entity_num::text AS entity_num,
        c.collector_user_id::text AS actor_user_id,
        c.role_code::text AS actor_role_code,
        c.manager_user_id::text AS manager_user_id,
        c.effective_from,
        c.effective_to,
        c.manager_effective_from,
        c.remarks::text AS remarks,
        c.uploaded_on::timestamp with time zone AS uploaded_on,
        c.source_systems
    FROM gold.collection_team_hierarchy c
),
ranked AS (
    SELECT
        source_rows.*,
        row_number() OVER (
            PARTITION BY
                hierarchy_type,
                entity_num,
                actor_user_id,
                actor_role_code,
                manager_user_id,
                effective_from,
                effective_to,
                manager_effective_from
            ORDER BY
                uploaded_on DESC NULLS LAST,
                hierarchy_version DESC NULLS LAST
        ) AS relationship_rank
    FROM source_rows
)
SELECT
    hierarchy_type,
    hierarchy_version,
    entity_num,
    actor_user_id,
    actor_role_code,
    manager_user_id,
    effective_from,
    effective_to,
    manager_effective_from,
    remarks,
    uploaded_on,
    source_systems,
    CURRENT_DATE AS data_as_of,
    'complete'::text AS coverage_status
FROM ranked
WHERE relationship_rank = 1;

-- The former generated keys omitted fields from the source records' declared
-- keys, causing unrelated operations to collapse to the same semantic key.
CREATE OR REPLACE VIEW gold.semantic_collection_operation_event AS
WITH assignment_ranked AS (
    SELECT
        a.*,
        row_number() OVER (
            PARTITION BY
                a.entity_num,
                a.application_or_ref_num,
                a.customer_id,
                a.cpv_type,
                a.assigned_on
            ORDER BY
                (a.customer_type IS NOT NULL) DESC,
                a.completed_on DESC NULLS LAST,
                a.vendor_type DESC NULLS LAST,
                a.vendor_id DESC NULLS LAST,
                a.collector_user_id DESC NULLS LAST,
                a.source_systems DESC NULLS LAST
        ) AS source_rank
    FROM gold.collection_assignment_events a
),
activity_ranked AS (
    SELECT
        x.*,
        row_number() OVER (
            PARTITION BY
                x.activity_version,
                x.entity_num,
                x.branch_code,
                x.collector_user_id,
                x.activity_date,
                x.run_number
            ORDER BY x.source_systems DESC NULLS LAST
        ) AS source_rank
    FROM gold.collection_activity_events x
)
SELECT
    'assignment'::text AS operation_type,
    a.entity_num::text AS entity_num,
    concat_ws(
        '|'::text,
        a.entity_num,
        a.application_or_ref_num,
        a.customer_id,
        a.cpv_type,
        a.assigned_on
    ) AS source_event_key,
    COALESCE(a.completed_on, a.assigned_on) AS operation_date,
    NULL::timestamp with time zone AS operation_timestamp,
    a.application_or_ref_num::text AS application_or_reference_number,
    a.customer_id::text AS customer_id,
    NULL::text AS loan_account_number,
    NULL::text AS branch_code,
    NULL::text AS from_branch_code,
    NULL::text AS to_branch_code,
    a.collector_user_id::text AS actor_user_id,
    NULL::text AS actor_user_name,
    NULL::text AS manager_user_id,
    NULL::text AS agent_code,
    a.vendor_type::text AS vendor_type,
    a.vendor_id::text AS vendor_id,
    a.cpv_type::text AS cpv_type,
    a.customer_type::text AS customer_type,
    a.assigned_on,
    a.completed_on,
    NULL::text AS handover_status,
    NULL::date AS handover_effective_date,
    NULL::numeric(20, 2) AS total_collection_amount,
    NULL::numeric(20, 2) AS final_collection_amount,
    NULL::text AS posting_branch_code,
    NULL::date AS posting_date,
    NULL::text AS run_number,
    'unmatched'::text AS account_link_status,
    a.source_systems,
    a.assigned_on AS data_as_of,
    'unverified'::text AS coverage_status
FROM assignment_ranked a
WHERE a.source_rank = 1

UNION ALL

SELECT
    'activity'::text AS operation_type,
    x.entity_num::text AS entity_num,
    concat_ws(
        '|'::text,
        x.activity_version,
        x.entity_num,
        x.branch_code,
        x.collector_user_id,
        x.activity_date,
        x.run_number
    ) AS source_event_key,
    x.activity_date AS operation_date,
    NULL::timestamp with time zone AS operation_timestamp,
    NULL::text AS application_or_reference_number,
    NULL::text AS customer_id,
    NULL::text AS loan_account_number,
    x.branch_code::text AS branch_code,
    NULL::text AS from_branch_code,
    NULL::text AS to_branch_code,
    x.collector_user_id::text AS actor_user_id,
    x.collector_user_name::text AS actor_user_name,
    NULL::text AS manager_user_id,
    x.agent_code::text AS agent_code,
    NULL::text AS vendor_type,
    NULL::text AS vendor_id,
    NULL::text AS cpv_type,
    NULL::text AS customer_type,
    NULL::date AS assigned_on,
    NULL::date AS completed_on,
    NULL::text AS handover_status,
    NULL::date AS handover_effective_date,
    x.total_collection_amount::numeric(20, 2) AS total_collection_amount,
    x.final_collection_amount::numeric(20, 2) AS final_collection_amount,
    x.post_branch::text AS posting_branch_code,
    x.post_date AS posting_date,
    x.run_number::text AS run_number,
    'unmatched'::text AS account_link_status,
    x.source_systems,
    x.activity_date AS data_as_of,
    'complete'::text AS coverage_status
FROM activity_ranked x
WHERE x.source_rank = 1

UNION ALL

SELECT
    'handover'::text AS operation_type,
    h.entity_num::text AS entity_num,
    concat_ws(
        '|'::text,
        h.entity_num,
        h.inventory_number,
        h.inventory_sl,
        h.run_number
    ) AS source_event_key,
    COALESCE(h.handover_date, h.effective_date) AS operation_date,
    h.handover_time::timestamp with time zone AS operation_timestamp,
    h.inventory_number::text AS application_or_reference_number,
    NULL::text AS customer_id,
    NULL::text AS loan_account_number,
    h.from_branch_code::text AS branch_code,
    h.from_branch_code::text AS from_branch_code,
    h.handover_to_branch::text AS to_branch_code,
    h.from_user_id::text AS actor_user_id,
    NULL::text AS actor_user_name,
    h.handover_to_user::text AS manager_user_id,
    NULL::text AS agent_code,
    NULL::text AS vendor_type,
    NULL::text AS vendor_id,
    NULL::text AS cpv_type,
    NULL::text AS customer_type,
    NULL::date AS assigned_on,
    NULL::date AS completed_on,
    h.status::text AS handover_status,
    h.effective_date AS handover_effective_date,
    NULL::numeric(20, 2) AS total_collection_amount,
    NULL::numeric(20, 2) AS final_collection_amount,
    NULL::text AS posting_branch_code,
    NULL::date AS posting_date,
    h.run_number::text AS run_number,
    'unmatched'::text AS account_link_status,
    h.source_systems,
    COALESCE(h.handover_date, h.effective_date) AS data_as_of,
    'unverified'::text AS coverage_status
FROM gold.collection_handover_events h;

-- The application catalog has completed its cutover. Compatibility views remain for
-- warehouse consumers but are no longer part of the NLQ security surface.
REVOKE SELECT ON
    gold.agent_master,
    gold.application_checklist_events,
    gold.branch_geography_bridge,
    gold.branch_master,
    gold.collection_activity_events,
    gold.collection_assignment_events,
    gold.collection_handover_events,
    gold.collection_team_hierarchy,
    gold.customer_master,
    gold.geography_master,
    gold.gl_daily_balances,
    gold.gl_ledger_master,
    gold.kyc_document_master,
    gold.loan_account_master,
    gold.loan_application_master,
    gold.loan_application_outcomes,
    gold.loan_balance_events,
    gold.loan_disbursement_events,
    gold.loan_ledger_events,
    gold.loan_repayment_events,
    gold.loan_reporting_attributes,
    gold.loan_schedule_events,
    gold.loan_waiver_events,
    gold.msme_master,
    gold.origination_vintage_matrix,
    gold.payment_receipt_events,
    gold.portfolio_daily_snapshot,
    gold.product_master,
    gold.reporting_product_mapping,
    gold.sales_team_hierarchy
FROM nlq_readonly;

GRANT SELECT ON
    gold.semantic_agent,
    gold.semantic_application,
    gold.semantic_branch,
    gold.semantic_collection_operation_event,
    gold.semantic_customer_document,
    gold.semantic_customer_profile,
    gold.semantic_disbursement_event,
    gold.semantic_gl_balance,
    gold.semantic_loan_account,
    gold.semantic_loan_ledger_event,
    gold.semantic_msme_lead,
    gold.semantic_organization_hierarchy,
    gold.semantic_origination_vintage,
    gold.semantic_portfolio_snapshot,
    gold.semantic_product_scheme,
    gold.semantic_receipt_adjustment_event,
    gold.semantic_repayment_event,
    gold.semantic_schedule_event
TO nlq_readonly;

COMMIT;
