# Gold View Consolidation Specification

## Purpose

Reduce the 30 current assistant-facing Gold views to 18 reusable semantic views while
preserving correct grains, totals, lineage, PII controls, and historical analysis.

This is an **assistant-facing consolidation**. Existing Gold objects may remain temporarily as
implementation sources and compatibility views. Remove them from the active NLQ catalog after
the replacement view reconciles and all consumers migrate; do not drop them immediately.

## Why the target is 18, not one or two views

The current objects contain incompatible grains:

- one row per loan;
- one row per disbursement;
- one row per instalment;
- one row per receipt;
- one row per ledger transaction;
- one row per account and snapshot date;
- one row per application;
- one row per hierarchy relationship.

Joining these into a mega-view would multiply rows and overstate money. For example, joining a
loan with three disbursements, twelve repayment events, and ten receipts can create 360 rows for
one account. The consolidation therefore follows two rules:

1. use `JOIN` only for verified many-to-one or one-to-one enrichment;
2. use typed `UNION ALL` for related event families that have different keys or grains.

## Naming standard

- Schema: `gold`
- Assistant-facing prefix: `semantic_`
- Identifiers: `text`
- Monetary fields: `numeric(20,2)` unless source precision requires more
- Rates: `numeric(12,6)`; store percentages consistently as 0–100
- Dates: `date`; timestamps: `timestamp with time zone`
- Every view ends with `source_systems`, `data_as_of`, and `coverage_status`
- Every event view includes `event_type` and `source_event_key`

## Target inventory

| # | Target semantic view | Replaces/absorbs current views |
|---:|---|---|
| 1 | `gold.semantic_loan_account` | `gold.loan_account_master`, `gold.loan_reporting_attributes`, active `gold.reporting_product_mapping` attributes |
| 2 | `gold.semantic_customer_profile` | `gold.customer_master` plus KYC summary |
| 3 | `gold.semantic_customer_document` | `gold.kyc_document_master` |
| 4 | `gold.semantic_branch` | `gold.branch_master`, `gold.branch_geography_bridge`, `gold.geography_master` |
| 5 | `gold.semantic_product_scheme` | `gold.product_master`, `gold.reporting_product_mapping` |
| 6 | `gold.semantic_agent` | `gold.agent_master` |
| 7 | `gold.semantic_organization_hierarchy` | `gold.sales_team_hierarchy`, `gold.collection_team_hierarchy` |
| 8 | `gold.semantic_disbursement_event` | `gold.loan_disbursement_events` |
| 9 | `gold.semantic_repayment_event` | `gold.loan_repayment_events` |
| 10 | `gold.semantic_schedule_event` | `gold.loan_schedule_events` |
| 11 | `gold.semantic_portfolio_snapshot` | `gold.portfolio_daily_snapshot` |
| 12 | `gold.semantic_application` | `gold.loan_application_master`, `gold.loan_application_outcomes`, aggregated `gold.application_checklist_events` headers |
| 13 | `gold.semantic_receipt_adjustment_event` | `gold.payment_receipt_events`, `gold.loan_waiver_events` via `UNION ALL` |
| 14 | `gold.semantic_loan_ledger_event` | `gold.loan_ledger_events`, `gold.loan_balance_events` via `UNION ALL` |
| 15 | `gold.semantic_collection_operation_event` | `gold.collection_assignment_events`, `gold.collection_activity_events`, and `gold.collection_handover_events` via `UNION ALL` |
| 16 | `gold.semantic_origination_vintage` | `gold.origination_vintage_matrix` |
| 17 | `gold.semantic_gl_balance` | `gold.gl_daily_balances`, `gold.gl_ledger_master` |
| 18 | `gold.semantic_msme_lead` | `gold.msme_master` |

## Shared implementation rules

### Shared lineage columns

Every target view must expose:

```text
source_systems
data_as_of
coverage_status
```

`coverage_status` is a controlled value such as `complete`, `partial`, `unmatched`,
`unverified`, or `source_empty`. It is not free-form prose.

### Effective-dated joins

For reporting mappings and hierarchies, match the business date inside the effective interval:

```sql
business_date >= effective_from
AND business_date < COALESCE(effective_to, DATE '9999-12-31')
```

Reject publication if effective intervals overlap for the same business key.

### PII

Views 2 and 3 are protected record-lookup views. Name and contact fields in other views must be
excluded from aggregate planner packs or masked according to the existing role policy.

---

## 1. `gold.semantic_loan_account`

**Grain:** one row per loan account
**Key:** `(entity_num, loan_account_number)`

**Sources and joins**

- Base: `gold.loan_account_master l`
- Left join `gold.loan_reporting_attributes r` on
  `(entity_num, loan_account_number)`; currently declared one-to-one.
- Resolve at most one effective `gold.reporting_product_mapping m` using
  `(entity_num, product_code, scheme_code, sanction_date)`.
- Do not join customer, repayment, receipt, schedule, ledger, or portfolio-event rows here.

**Columns**

```text
entity_num
loan_account_number
application_number
customer_id
customer_name
application_branch_code
posting_branch_code
servicing_branch_code
reporting_branch_code
product_code
product_name
scheme_code
scheme_name
reporting_product_code
reporting_product_name
reporting_product_group
secured_flag
msme_flag
loan_type
loan_purpose_code
loan_purpose_desc
sanction_date
sanction_amount
disbursed_amount
first_disbursement_date
disbursement_count
interest_rate
emi_amount
number_of_emis
application_emi_date
coapplicant_count
repayment_start_date
repayment_end_date
principal_repaid
interest_repaid
receipt_count
total_receipt_amount
last_payment_date
schedule_installments
latest_asset_code
latest_asset_category
asset_classified_on
dpd_days
principal_outstanding_current
npa_type
npa_date
closure_date
loan_status
agent_code
agent_name
sourced_by
direct_selling_agent
reporting_mapping_status
source_systems
data_as_of
coverage_status
```

**Important:** rename existing ambiguous `outstanding_amount` to
`principal_outstanding_current` only after formula reconciliation. Otherwise retain the old
name and mark it provisional.

---

## 2. `gold.semantic_customer_profile`

**Grain:** one row per customer
**Key:** `(entity_num, customer_id)`
**Sensitivity:** PII

**Sources and joins**

- Base: `gold.customer_master c`
- Left join a KYC aggregate grouped by `(entity_num, customer_id)`.
- Never join raw KYC documents directly to customers in this view.

**Columns**

```text
entity_num
customer_id
customer_ucid
customer_type
customer_category_code
customer_category
customer_status
full_name
prefix_code
first_name
middle_name
last_name
father_name
date_of_birth
age
gender
marital_status
resident_status
occupation_type
occupation_name
occupation_nature
yearly_income
monthly_income
risk_rating
mobile_primary
mobile_secondary
email
landline
pan_number
aadhaar_number
kyc_verified_flag
kyc_document_count
kyc_identity_proof_count
kyc_address_proof_count
kyc_expired_document_count
address_line1
address_line2
landmark
city_code
city
district_code
district
state_code
state
pincode
additional_address
home_branch_code
home_branch_name
agency_code
agency_name
staff_emp_num
staff_name
is_corporate
is_director_elsewhere
primary_din
firm_party_count
related_loan_count
source_systems
data_as_of
coverage_status
```

---

## 3. `gold.semantic_customer_document`

**Grain:** one customer document
**Key:** `(inventory_num, document_sl)`
**Sensitivity:** PII; authorized record lookup only

**Columns**

```text
inventory_num
document_sl
entity_num
customer_id
customer_name
pid_type_code
pid_type_desc
document_number
issue_date
expiry_date
issue_place
issue_authority
is_address_proof
is_identity_proof
is_pan_type
is_aadhaar_type
document_status
source_systems
data_as_of
coverage_status
```

`document_status` is derived as `valid`, `expired`, `future_dated`, or `unknown` using the
query/as-of date; do not permanently label a record from load date alone.

---

## 4. `gold.semantic_branch`

**Grain:** one branch
**Key:** `(entity_num, branch_code)`

**Sources and joins**

- Base: `gold.branch_master b`
- Left join `gold.branch_geography_bridge bg` on `(entity_num, branch_code)`.
- Left join `gold.geography_master g` only through the validated geography codes in `bg`.
- Never join branch location code directly to district code without an approved mapping.

**Columns**

```text
entity_num
branch_code
branch_name
branch_address
location_code
branch_category_code
branch_category_name
branch_size
admin_unit_type
parent_admin_code
division_codes
ifsc_code
micr_code
bsr_code
base_currency
phone_primary
email_primary
opened_on
closed_on
branch_status
country_code
district_code
district_name
state_code
state_name
gst_state_code
region_name
geography_match_status
source_systems
data_as_of
coverage_status
```

Publication rule: geography dimensions remain disabled until at least 99% of active loan
exposure maps or the answer displays the unmatched-exposure percentage.

---

## 5. `gold.semantic_product_scheme`

**Grain:** one source product and scheme combination
**Key:** `(entity_num, product_code, scheme_code)`

**Sources and joins**

- Normalize `gold.product_master` to product/scheme grain.
- Left join exactly one effective reporting mapping from
  `gold.reporting_product_mapping`.

**Columns**

```text
entity_num
product_code
product_name
product_domain
product_group
scheme_code
scheme_name
loan_type
security_type_code
security_type_desc
product_family
gl_account_code
min_amount
max_amount
min_tenor_months
max_tenor_months
ltv_rate
min_interest_rate
max_interest_rate
product_status
reporting_product_code
reporting_product_name
reporting_product_group
secured_flag
msme_flag
mapping_effective_from
mapping_effective_to
mapping_status
mapping_approved_by
mapping_approved_at
source_systems
data_as_of
coverage_status
```

---

## 6. `gold.semantic_agent`

**Grain:** one governed agent identity
**Key:** `(agent_code)`
**Sensitivity:** contains contact PII

**Columns**

```text
agent_code
agent_name
agent_type
designation
mobile
email
joined_on
branch_code
role_code
linked_customer_count
linked_loan_count
source_systems
data_as_of
coverage_status
```

Do not join hierarchy rows into this current-state dimension because that would erase or
duplicate historical assignments.

---

## 7. `gold.semantic_organization_hierarchy`

**Grain:** one distinct effective-dated actor-to-manager relationship
**Key:** `(hierarchy_type, entity_num, actor_user_id, actor_role_code, manager_user_id,
effective_from, effective_to, manager_effective_from)`

**Construction:** `UNION ALL` sales and collection hierarchies; do not join them. Source
hierarchy uploads repeat the same business relationship across upload versions. After the
union, apply `ROW_NUMBER()` over the semantic key above, ordered by `uploaded_on DESC`, and
retain row 1. Keep the selected `hierarchy_version` and `uploaded_on` for lineage; neither is
part of the business relationship key.

**Columns**

```text
hierarchy_type
hierarchy_version
entity_num
actor_user_id
actor_role_code
manager_user_id
effective_from
effective_to
manager_effective_from
remarks
uploaded_on
source_systems
data_as_of
coverage_status
```

`hierarchy_type` is `sales` or `collections`.

---

## 8. `gold.semantic_disbursement_event`

**Grain:** one disbursement event
**Key:** `(entity_num, loan_account_number, disbursement_sequence)`

**Columns**

```text
event_type
entity_num
loan_account_number
disbursement_sequence
disbursement_date
disbursement_amount
charges_amount
net_paid_amount
currency_code
posting_branch_code
customer_id
application_branch_code
reporting_branch_code
product_code
scheme_code
agent_code
source_event_key
source_systems
data_as_of
coverage_status
```

Names are decoded through dimensions in the UI/compiler. Do not repeat customer, branch,
product, and scheme names on every event unless required for immutable historical labeling.

---

## 9. `gold.semantic_repayment_event`

**Grain:** one contractual due-versus-paid repayment event
**Key:** `(entity_num, loan_account_number, repayment_sequence)`

**Columns**

```text
event_type
entity_num
loan_account_number
repayment_sequence
repayment_date
principal_due
interest_due
total_due
principal_paid
interest_paid
total_paid
collection_shortfall
collection_efficiency
customer_id
branch_code
product_code
scheme_code
agent_code
source_event_key
source_systems
data_as_of
coverage_status
```

This remains separate from receipts: contractual paid allocation and cash receipts are
different business facts.

---

## 10. `gold.semantic_schedule_event`

**Grain:** one scheduled instalment
**Key:** `(entity_num, loan_account_number, instalment_sequence)`

**Columns**

```text
event_type
entity_num
loan_account_number
instalment_sequence
scheduled_date
scheduled_principal
scheduled_interest
scheduled_total
customer_id
branch_code
product_code
scheme_code
loan_status
source_event_key
source_systems
data_as_of
coverage_status
```

---

## 11. `gold.semantic_portfolio_snapshot`

**Grain:** one loan account per snapshot date
**Key:** `(snapshot_date, entity_num, loan_account_number)`

The current catalog incorrectly describes a current-only key without `snapshot_date`. The
replacement must include it so historical snapshots cannot collide.

**Columns**

```text
snapshot_date
entity_num
loan_account_number
customer_id
branch_code
product_code
scheme_code
asset_code
asset_classification
previous_asset_code
dpd_days
principal_outstanding
principal_overdue
interest_overdue
charges_overdue
penal_overdue
total_overdue
is_delinquent
is_par30
is_par60
is_par90
is_npa
source_systems
data_as_of
coverage_status
```

---

## 12. `gold.semantic_application`

**Grain:** one loan application
**Key:** `(entity_num, application_number)`

**Sources and joins**

- Base: `gold.loan_application_master a`
- Left join `gold.loan_application_outcomes o` on `(entity_num, application_number)`;
  verified one-to-one.
- Left join checklist aggregates grouped by `(entity_num, application_number)`.
- Do not expose invalid checklist-detail columns until their source join is repaired.

**Columns**

```text
entity_num
application_number
application_date
branch_code
customer_id
product_code
scheme_code
loan_type
loan_purpose_code
applied_amount
application_sanction_amount
loan_account_number
coapplicant_count
guarantor_count
sourced_by
dealer_code
direct_selling_agent
canvassed_by
last_completion_stage
authorized_on
account_link_status
observable_outcome_status
application_disbursement_sequence
first_disbursement_date
observable_disbursed_amount
observable_sanction_amount
checklist_header_count
checklist_approved_count
checklist_rejected_count
first_checklist_entered_on
last_checklist_entered_on
checklist_coverage_status
source_systems
data_as_of
coverage_status
```

Forbidden labels: `approved`, `rejected`, `declined`, or stage conversion unless authoritative
decision/stage events are added.

---

## 13. `gold.semantic_receipt_adjustment_event`

**Grain:** one receipt or waiver source event
**Key:** `(event_type, entity_num, loan_account_number, event_date, source_event_key)`

**Construction:** normalized `UNION ALL`; never join receipt and waiver rows.

**Columns**

```text
event_type
entity_num
loan_account_number
event_date
source_event_key
receipt_amount
principal_adjusted
interest_adjusted
charges_adjusted
penal_adjusted
total_due
posting_branch_code
posting_date
receipt_mode
receipt_branch_code
instrument_number
instrument_date
utr_number
detail_receipt_amount
interest_waived
charges_waived
penal_waived
total_waived_amount
installments_due
installments_paid
excess_amount
early_payment_charge
source_systems
data_as_of
coverage_status
```

`event_type` is `receipt` or `waiver`. Receipt metrics filter `event_type='receipt'`; waiver
metrics filter `event_type='waiver'`. Current zero-valued waiver components retain
`coverage_status='source_empty'` or `unverified` as appropriate.

---

## 14. `gold.semantic_loan_ledger_event`

**Grain:** one transaction or balance-state source event
**Key:** `(record_type, entity_num, loan_account_number, event_date, day_serial)`

**Construction:** normalized `UNION ALL` until a tested one-to-one transaction/balance link
exists. If source reconciliation proves identical keys and exactly one balance state per ledger
transaction, the team may replace the union with a one-to-one join.

**Columns**

```text
record_type
entity_num
loan_account_number
event_date
day_serial
source_event_key
debit_credit_flag
currency_code
principal_movement
interest_movement
charges_movement
penal_movement
future_installment_movement
narration
transaction_reference
breakup_from_date
breakup_upto_date
breakup_interest_amount
breakup_interest_rate
principal_outstanding
interest_outstanding
charges_outstanding
penal_outstanding
excess_outstanding
channel_id
recovery_type
asset_code
cash_payment
online_payment
cheque_payment
source_systems
data_as_of
coverage_status
```

`record_type` is `transaction` or `balance_state`. Movement metrics and balance metrics must
filter their respective record type.

---

## 15. `gold.semantic_collection_operation_event`

**Grain:** one collection assignment, activity summary, or handover event
**Key:** `(operation_type, entity_num, source_event_key)`

**Construction:** normalized `UNION ALL`; do not join the three current facts.

**Columns**

```text
operation_type
entity_num
source_event_key
operation_date
operation_timestamp
application_or_reference_number
customer_id
loan_account_number
branch_code
from_branch_code
to_branch_code
actor_user_id
actor_user_name
manager_user_id
agent_code
vendor_type
vendor_id
cpv_type
customer_type
assigned_on
completed_on
handover_status
handover_effective_date
total_collection_amount
final_collection_amount
posting_branch_code
posting_date
run_number
account_link_status
source_systems
data_as_of
coverage_status
```

`operation_type` is `assignment`, `activity`, or `handover`.

Build `source_event_key` from the complete declared source key:

```text
assignment = entity_num | application_or_ref_num | customer_id | cpv_type | assigned_on
activity   = activity_version | entity_num | branch_code | collector_user_id |
             activity_date | run_number
handover   = entity_num | inventory_number | inventory_sl | run_number
```

`loan_account_number` and `account_link_status` must remain null/`unmatched` for assignment or
handover records until their references are proven to be loan-account keys. Never infer this
mapping by equal-looking text.

---

## 16. `gold.semantic_origination_vintage`

**Grain:** origination month × report month × branch × product × scheme
**Key:** `(entity_num, origination_month, report_month, branch_code, product_code, scheme_code)`

**Columns**

```text
entity_num
origination_month
report_month
months_on_book
branch_code
product_code
scheme_code
account_count
disbursed_amount
principal_outstanding
accounts_par30
accounts_par60
accounts_par90
accounts_npa
par30_account_rate
par60_account_rate
par90_account_rate
npa_account_rate
source_systems
data_as_of
coverage_status
```

Rates are derived from account counts. They must not be labeled balance-weighted PAR/NPA.

---

## 17. `gold.semantic_gl_balance`

**Grain:** GL account × branch × currency × balance date
**Key:** `(balance_date, entity_num, branch_code, gl_number, currency_code)`

**Sources and joins**

- Base: `gold.gl_daily_balances b`
- Left join `gold.gl_ledger_master g` on `gl_number` only after verifying `gl_number` is unique.
- Do not join GL branch codes to loan branch/product/customer dimensions without an approved
  reconciliation bridge.

**Columns**

```text
balance_date
entity_num
branch_code
branch_name
gl_number
gl_account_code
gl_name
gl_short_name
gl_type
gl_hierarchy_code
gl_hierarchy_name
gl_hierarchy_parent
gl_category_code
gl_category_name
gl_family
parent_gl_number
parent_gl_name
contra_gl
currency_code
default_currency
allowed_currencies
account_currency_balance
base_currency_balance
account_currency_debits
account_currency_credits
base_currency_debits
base_currency_credits
is_gicc_gl
is_external_gl
external_access_code
external_gl_head
external_gl_usage
gl_status
opened_on
closed_on
source_systems
data_as_of
coverage_status
```

---

## 18. `gold.semantic_msme_lead`

**Grain:** one MSME lead
**Key:** `(entity_num, lead_number)`
**Sensitivity:** contains PII

**Columns**

```text
entity_num
lead_number
entered_on
customer_id
customer_name
firm_name
mobile_number
branch_code
firm_type_code
firm_type_desc
customer_category_code
customer_category_desc
product_code
scheme_code
loan_purpose_code
requested_amount
secured_unsecured
security_type
security_value
lead_source
entered_by_employee
lead_status
reject_reason
loan_application_number
lead_vendor_id
vendor_id
vehicle_make
vehicle_model
vendor_loan_amount
finance_amount
vendor_row_count
cif_shop_name
cif_entered_by_agent
msme_status
source_systems
data_as_of
coverage_status
```

Do not treat `lead_source` as an enterprise distribution channel until the business approves
its taxonomy and coverage.

---

## Views that must not be directly joined

| Left | Right | Reason |
|---|---|---|
| disbursement events | repayment events | many-to-many per loan; monetary fan-out |
| repayment events | receipt events | contractual allocation and cash receipt have different keys |
| schedule events | repayment events | sequence/date matching is not a declared one-to-one relationship |
| portfolio snapshots | event facts | snapshot row repeats for every event unless aggregated first |
| collection assignment | collection activity/handover | account/reference relationship not proven |
| GL balances | loan dimensions | no approved account/product/branch reconciliation bridge |
| application checklist details | application headers | current detail enrichment has zero valid joins |

Cross-fact questions must run one correct aggregate per fact and compose the results on a
shared conformed dimension. They must not generate one multi-fact SQL join.

## Migration sequence

1. Create all 18 views alongside the existing 30.
2. Run key uniqueness, null, row-count, monetary reconciliation, join-coverage, and freshness
   tests.
3. Compare every existing governed metric between old and new views for all-time and monthly
   totals.
4. Update catalog table/column definitions to the semantic names.
5. Update metric base tables, dimensions, joins, worklists, analyses, and lookup SQL.
6. Run the full NLQ, workbench, regulatory, and Top-50 suites.
7. Shadow old and new catalog versions on production-like data.
8. Remove the old views from the assistant catalog after acceptance.
9. Retain compatibility views for other application consumers until their owners migrate.
10. Drop obsolete physical views only through a separate approved database migration.

## Acceptance gates

- Exactly one row per declared key.
- No monetary metric differs from its approved old-view baseline without a signed
  reconciliation explanation.
- Every effective-dated mapping is non-overlapping.
- Every many-to-one join records match rate and unmatched exposure.
- No event family is joined in a way that multiplies another event family.
- Restricted/PII fields remain role-gated.
- Catalog retrieval exposes these 18 views by domain rather than sending all column lists.
- Normal planning still uses compact metric/dimension packs; reducing view count is not a
  substitute for semantic retrieval.

## Production inspection — 2026-08-27

The 18 views were inspected on `moneypaldb` using `.env.prod` credentials in a transaction
forced to read-only mode. Credential values were not logged.

### Pre-remediation summary

- All 18 expected views exist in schema `gold`.
- All 30 original Gold views also remain, giving 49 Gold objects including the helper
  `_semantic_data_as_of`.
- Row counts reconcile to their component sources for the direct and `UNION ALL` views.
- Sixteen column contracts match after accepting the standard event lineage columns already
  present in production.
- `gold.semantic_branch` is missing required column `country_code`.
- `nlq_readonly` has no `SELECT` privilege on any of the 18 views. The old views remain
  selectable, so the assistant cannot yet migrate to the new catalog.
- Two declared target keys are not unique and require view-definition fixes.

### Pre-remediation view results

| View | Rows | Duplicate declared-key groups | Column result |
|---|---:|---:|---|
| `semantic_loan_account` | 5,753 | 0 | match |
| `semantic_customer_profile` | 17,972 | 0 | match |
| `semantic_customer_document` | 72,295 | 0 | match |
| `semantic_branch` | 67 | 0 | missing `country_code` |
| `semantic_product_scheme` | 22 | 0 | match |
| `semantic_agent` | 1,014 | 0 | match |
| `semantic_organization_hierarchy` | 8,079 | 258 | repeated upload snapshots |
| `semantic_disbursement_event` | 5,696 | 0 | match; production also has `event_type` |
| `semantic_repayment_event` | 18,836 | 0 | match; production also has `event_type` |
| `semantic_schedule_event` | 225,132 | 0 | match; production also has `event_type` |
| `semantic_portfolio_snapshot` | 5,466 | 0 | match |
| `semantic_application` | 9,021 | 0 | match |
| `semantic_receipt_adjustment_event` | 86,565 | 0 | match |
| `semantic_loan_ledger_event` | 196,445 | 0 | match; production also has `source_event_key` |
| `semantic_collection_operation_event` | 15,294 | 2,214 | incomplete generated source keys |
| `semantic_origination_vintage` | 286 | 0 | match |
| `semantic_gl_balance` | 203,933 | 0 | match |
| `semantic_msme_lead` | 9,168 | 0 | match |

### Duplicate breakdown

`semantic_organization_hierarchy`:

| Type | Rows | Duplicate groups | Excess rows |
|---|---:|---:|---:|
| sales | 6,425 | 190 | 6,041 |
| collections | 1,654 | 68 | 1,525 |

Adding `uploaded_on` makes the physical rows unique, confirming that repeated uploads are the
cause. The serving view should deduplicate by the semantic relationship and keep the latest
upload, rather than treating uploads as distinct hierarchy relationships.

`semantic_collection_operation_event`:

| Type | Rows | Duplicate groups | Excess rows |
|---|---:|---:|---:|
| assignment | 14,091 | 2,171 | 3,773 |
| activity | 1,029 | 1 | 2 |
| handover | 174 | 42 | 62 |

The current `source_event_key` expressions omit key fields. Rebuild them from the complete
source keys specified under view 15.

### Remediation status — 2026-08-27

Applied transactionally in production and recorded in
`backend/scripts/sql/semantic_view_remediation.sql`:

1. `semantic_organization_hierarchy` now retains the latest uploaded row per semantic
   relationship: 366 serving rows and zero duplicate declared-key groups.
2. `semantic_collection_operation_event` now uses the complete source keys and removes
   repeated upstream source rows deterministically: 13,689 serving rows and zero duplicate
   `(operation_type, entity_num, source_event_key)` groups.
3. `nlq_readonly` now has explicit `SELECT` on all 18 semantic views; the persistent role
   bootstrap allowlist was updated to match.
4. A connection using the production NLQ credentials successfully selected from all 18 views.

Per the product decision, `semantic_branch.country_code` is deferred and is not a blocker for
the current single-country deployment. The active NLQ catalog, deterministic SQL, metrics,
dimensions, joins, analyses, worklists, tests, and production role were migrated together to
the 18 semantic views on 2026-08-27. The 30 compatibility views remain available to warehouse
consumers but are no longer visible to `nlq_readonly`.
