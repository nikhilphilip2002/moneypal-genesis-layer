# Oracle and Bronze-to-Gold Requirements for the Top 50 Questions

**Assessment date:** 2026-08-20  
**Oracle source:** `139.84.155.19:1521/FREEPDB1`, schema `GICCPROD_NEW`  
**PostgreSQL target:** `moneypaldb`, schemas `bronze`, `silver`, and `gold`  
**Security:** Credentials are intentionally excluded. Oracle inspection was read-only.

## 1. Executive summary

This document identifies:

1. populated Oracle tables that should be ingested or confirmed in PostgreSQL;
2. existing Bronze/Silver data that still needs a governed Gold model;
3. the business purpose and Top-50 questions unlocked by each model; and
4. questions that remain unanswerable because their source data is empty, absent, or requires an approved predictive/decision policy.

The strict data-readiness assessment is:

| Classification | Count | Question numbers |
|---|---:|---|
| Fully answerable from available database data | **19** | 1, 2, 6, 8, 9, 10, 18–21, 23, 24, 27, 29, 31–33, 35, 45 |
| Partially answerable | **7** | 4, 7, 13, 14, 26, 41, 50 |
| Not accurately answerable | **24** | 3, 5, 11, 12, 15–17, 22, 25, 28, 30, 34, 36–40, 42–44, 46–49 |

Therefore, **19/50** questions can be answered exactly with existing data. Another **7/50** can return a useful but explicitly limited answer. The remaining **24/50** need a new feed, populated source table, approved definition, or predictive model.

## 2. Required data flow

```mermaid
flowchart LR
    O[Oracle GICCPROD_NEW] -->|Immutable source copy| B[PostgreSQL Bronze]
    B -->|Typing, deduplication, key reconciliation| S[PostgreSQL Silver]
    S -->|Governed business grain and formulas| G[PostgreSQL Gold]
    G --> C[NLQ catalog, signals, analyses and worklists]
```

- **Bronze** must preserve source columns and source grain without business reinterpretation.
- **Silver** must standardize types, names, keys, deduplication, and current-versus-legacy portfolio rules.
- **Gold** must expose stable business grains, documented metrics, safe joins, coverage warnings, and approved definitions.
- NLQ must query only governed `gold.*` objects, never Oracle, Bronze, or raw Silver directly.

## 3. Live Oracle facts relevant to the Top 50

The following counts were verified against the current Oracle instance:

| Domain | Verified source coverage |
|---|---|
| Branches and geography | `MBRN`: 67 named branches, all with location and parent-administration codes; 63 distinct locations; `DISTRICT`: 828; `STATE`: 36; `DASH_FILTER_REGION`: 28 |
| Sales and collections hierarchy | `COLLSALE_HIER`: 192; `COLLSALE_HIER_HIST`: 6,233; `COLLNB_HIER`: 63; `COLLNB_HIER_HIST`: 1,591 |
| Collection allocation | `COLLNB_CPV_ALLOT`: 14,091 |
| Applications and outcomes | `GENLNAPPL`: 9,021 applications; `GENLNAPPLDISB`: 7,731 disbursement outcomes |
| Application documentation | `GENLNAPPL_CHKLIST`: 21,042; `GENLNAPPL_CHKLIST_DTL`: 550,389 |
| Receipts and waivers | `GENLNRCPT`: 46,144; `GENLNRCPTDTL`: 46,144; `GENLNRCPT_WAIVE`: 40,421 |
| Loan ledger | `LNACLED`: 94,124; `LNACLED_OS`: 102,321; `LNACLEDBRKUP`: 36,878 |
| Collection operations | `DLY_COLLECT_II_MAIN`: 885; history: 144; handover: 174 |

These are live counts, not acceptance constants. Production ingestion must reconcile every run to a consistent Oracle SCN or extraction timestamp.

## 4. Oracle tables to ingest or verify in Bronze/Silver

This table is scoped to the executive Top-50 questions. It does not replace the separate RBI reporting migration inventory.

| Priority | Oracle source | Bronze/Silver action | Gold destination | Purpose / questions improved |
|---|---|---|---|---|
| P0 | `DISTRICT`, `STATE`, `DASH_FILTER_REGION` | Ingest if absent; preserve source codes; validate the location-to-district bridge before publishing | `gold.geography_master`, `gold.branch_geography_bridge` | Region/state/district analysis for Q6, Q18, Q21 and Q27 |
| P0 | `COLLSALE_HIER`, `COLLSALE_HIER_HIST` | Ingest current and effective-dated history | `gold.sales_team_hierarchy` | Sales team ownership and historical team comparisons for Q14 and Q50 |
| P0 | `COLLNB_HIER`, `COLLNB_HIER_HIST` | Ingest current and effective-dated history | `gold.collection_team_hierarchy` | Collection team performance for Q29, Q31 and Q32 |
| P0 | `COLLNB_CPV_ALLOT` | Ingest assignments with their source dates and account/agent keys | `gold.collection_assignment_events` | Account-to-collector/team attribution for Q29 and Q32 |
| P0 | `GENLNAPPLDISB` | Ingest and reconcile to applications and loan accounts | `gold.loan_application_outcomes` | Application-to-disbursement conversion and disbursement-pattern analysis; partially improves Q15, Q16, Q25 and Q26 |
| P1 | `GENLNAPPL_CHKLIST`, `GENLNAPPL_CHKLIST_DTL` | Ingest with application and checklist keys | `gold.application_checklist_events` | Documentation completion and missing-document analysis; partially improves Q15, Q42 and Q43 |
| P1 | `DLY_COLLECT_II_MAIN`, its history and handover tables | Ingest as dated operational events, not a current-state overwrite | `gold.collection_activity_events`, `gold.collection_handover_events` | Collection activity, ownership changes, bottlenecks and team productivity for Q29, Q31, Q32 and Q50 |
| P1 | `GENLNRCPT`, `GENLNRCPTDTL` | Already present in the July PostgreSQL estate; reconcile and retain as event-level Silver sources | `gold.payment_receipt_events` | Actual receipt date, amount, instrument and channel for Q29–Q33 and Q41 |
| P1 | `GENLNRCPT_WAIVE` | Already present; reconcile and model waiver reason/type where populated | `gold.loan_waiver_events` | Waiver monitoring and possible financial anomalies for Q41 |
| P1 | `LNACLED`, `LNACLED_OS`, `LNACLEDBRKUP` | Already present; reconcile transaction keys, signs and breakup rules | `gold.loan_ledger_events`, `gold.loan_balance_events` | Principal/interest/charge movement, collections drivers and anomaly checks for Q20, Q31, Q33 and Q41 |
| P2 | `GENLNAPPL` and populated application child tables | Existing application tables must be reconciled to the current Oracle snapshot and normalized | `gold.loan_application_master` | Application counts, cohorts, branch/product mix and limited acquisition analysis for Q6, Q13 and Q26 |
| P2 | `MBRN` | Already represented as `silver.branch_master` and `gold.branch_master`; verify freshness rather than remigrating blindly | Enrich existing `gold.branch_master` | Branch names, status, IFSC, location code and hierarchy for Q6, Q18, Q21, Q27 and Q32 |

### Important limitation

`GENLNAPPLDISB` proves an application reached disbursement, but it does not provide a complete acquisition funnel. The inspected rejection, pending and lead tables contain zero rows. Application-to-disbursement reporting is possible; stage-by-stage conversion, rejection-rate and rejection-reason reporting is not.

## 5. Existing Bronze/Silver sources that need Gold promotion

The current Gold layer already covers loan accounts, disbursements, repayment schedules, portfolio snapshots, GL balances, customers, agents, branches, products and reporting attributes. The following additional governed objects are needed.

| Proposed Gold object | Required Bronze/Silver inputs | Grain | Required measures/dimensions | Purpose |
|---|---|---|---|---|
| `gold.geography_master` | `district`, `state`, `dash_filter_region` | One row per governed geography code | state, district, region, effective status | Reusable geographic drill path |
| `gold.branch_geography_bridge` | branch master plus validated location/geography mapping | One effective-dated row per branch-to-geography relationship | branch, location, district, state, region | Prevent unsupported joins based only on similar code names |
| `gold.sales_team_hierarchy` | `collsale_hier`, `collsale_hier_hist` | One effective-dated hierarchy relationship | employee/agent, manager, team, branch, effective dates | Historical team attribution |
| `gold.collection_team_hierarchy` | `collnb_hier`, `collnb_hier_hist` | One effective-dated hierarchy relationship | collector, manager, team, branch, effective dates | Fair collections-team comparison |
| `gold.collection_assignment_events` | `collnb_cpv_allot` | One assignment event per account/collector/time | account, collector, team, assigned time, status | Attribute recoveries to the responsible team |
| `gold.loan_application_master` | `genlnappl` and relevant application children | One row per application | application date, branch, product, customer, source, current observable outcome | Application volumes and mix |
| `gold.loan_application_outcomes` | `genlnappldisb`, loan account/disbursement sources | One observable outcome per application/account | application, account, disbursement date/amount | Submitted-to-disbursed conversion only |
| `gold.application_checklist_events` | application checklist header/detail | One checklist item status event | application, requirement, status, event time | Documentation completeness and delays |
| `gold.payment_receipt_events` | `genlnrcpt`, `genlnrcptdtl` | One governed receipt event | amount, receipt date, mode, instrument, branch, account | Cash collection and payment-channel facts |
| `gold.loan_waiver_events` | `genlnrcpt_waive` | One waiver event | waived amount, component, reason, approver, date, account | Waiver governance and anomaly detection |
| `gold.loan_ledger_events` | `lnacled`, `lnacledbrkup` | One account-ledger transaction/component | principal, interest, fee, penalty, transaction type/date | Transaction-level loan movement |
| `gold.loan_balance_events` | `lnacled_os` | One account balance state per transaction/date | principal/interest/charge outstanding | Historical balance reconstruction |
| `gold.collection_activity_events` | daily collection main/history | One collector-account interaction/activity | activity date, outcome, promise, amount, collector/team | Collection driver and productivity analysis |
| `gold.collection_handover_events` | collection handover tables | One ownership handover event | from/to owner, reason, date, account | Identify repeated reassignment and operational friction |
| `gold.origination_vintage_matrix` | application/account/disbursement plus portfolio snapshots | One origination cohort × month-on-book | disbursed amount, account count, PAR30/60/90, NPA | Q24 vintage analysis; this can be derived without a new external feed |

### Gold publication controls

Each new Gold object must have:

- a documented business grain and unique-key test;
- source-to-target row-count reconciliation;
- join-coverage tests against loan, branch, customer, and agent keys;
- effective-date rules for historical hierarchies;
- freshness and maximum-business-date checks;
- null-coverage thresholds for critical dimensions;
- an NLQ catalog entry only after semantic validation; and
- an explicit coverage warning when the source is incomplete.

## 6. Oracle structures that exist but contain no usable data

Creating Gold views over these tables will not unlock the questions because the source row count is zero or the meaningful fields are unpopulated.

| Missing domain | Oracle structures inspected | Finding |
|---|---|---|
| Marketing channels | `MKTCHANNEL` | 0 rows |
| Rejected/pending applications | `ACNTSREJ`, `APREJPEND`, `APREJPENDDTL` and related tables | 0 rows |
| Acquisition leads/workflow | `DOORSTEP_LEAD_MAIN*`, `APPLDOCBRN_VERIFY*` | 0 rows |
| Budgets and targets | `BUDGET*`, `PBBUDGET*`, `ZBBUDGET*`, `FABUDGET*` | Operational budget tables are empty; only isolated performance-budget rows exist and are insufficient |
| Branch expenses | `BRNEXPS`, `BRNBANKEXPS` | 0 rows |
| Legal case register | `CASE_INT`, `CASE_RECORD`, `LN_LEGAL_DETAILS` and report-temporary legal tables | 0 rows; `GENLN_RPT` legal flag is `0` for all 5,696 rows and legal date/current status are unpopulated |
| Audit and compliance exceptions | `AUDIT_BRN*`, `AUDITSCHED*`, `AUDIT_IRREGLAR*`, `AUDIT_RATING*`, `CUSTOMEREXCEPTION`, `CUSTOMERIRREGULARITY` | 0 rows |
| Complaints | `RCOMPL*` and report-temporary complaint tables | 0 rows |
| People, payroll and training | `STAFFREG`, `PAY`, `PAYRECORD`, `RTMPSTAFFPERFORMANCE`, training/configuration tables | 0 rows |

These are **source-data gaps**, not engineering defects. Empty Oracle tables must not be presented as evidence that there were zero complaints, exceptions, legal cases, audit findings, or staff gaps unless the business owner confirms that the tables are the authoritative registers and that zero is a valid declaration.

## 7. Questions that remain unanswerable and why

The table below uses strict semantic equivalence: returning a related metric does not count as answering the question.

| Q | Question | Why it is unanswerable now | Data or governance required |
|---:|---|---|---|
| 3 | Are we on track against our annual business plan? | No approved annual plan or target series is populated | Annual plan by period, KPI, product, branch and owner |
| 5 | What are the biggest risks to achieving this quarter's targets? | Targets are absent, and “biggest risks” requires an approved risk/driver method | Quarterly targets plus governed variance and risk-driver definitions |
| 11 | Why are disbursements above or below target? | Actual disbursement exists; target does not | Monthly disbursement targets and approved variance-driver rules |
| 12 | Which branches are performing above and below expectations? | Branch actuals exist; branch expectations do not | Branch-level KPI targets/benchmarks and effective dates |
| 15 | Where are we losing customers during the acquisition process? | Only applications and disbursement outcomes are populated; intermediate stages and exits are missing | Complete acquisition event log, exit reason and timestamps |
| 16 | What is the conversion rate at each stage of the sales funnel? | Rejected, pending, lead and workflow sources are empty | Defined funnel stages and one timestamped event per stage transition |
| 17 | Which customer segments have the highest potential for growth? | Historical growth can be shown, but “potential” is predictive/recommendatory | Approved opportunity score, forecast horizon and segment policy |
| 22 | Which loans are most likely to become delinquent in the next 30/60/90 days? | Current early-warning facts do not constitute a probability forecast | Validated delinquency model, training labels, calibration and model governance |
| 25 | Where are approval rates changing significantly, and why? | A disbursed outcome is not a complete approval decision; rejection and decision history are absent | Approval/rejection decision events, decision time, reason and policy version |
| 28 | What will happen to portfolio quality if current delinquency trends continue? | This is a forecast/scenario question | Approved forecasting/scenario model with confidence bounds and assumptions |
| 30 | Which overdue customers have the highest probability of payment if contacted now? | A priority ranking is not a calibrated payment probability | Contact attempts/outcomes, promise-to-pay history and approved propensity model |
| 34 | What collection strategy should we use for different customer segments? | Data can rank accounts but cannot invent a business strategy | Ratified strategy/playbook by segment, eligibility and escalation policy |
| 36 | Where are we making and losing money across products, branches, channels and customers? | Loan income proxies exist, but allocated costs and channel attribution do not | Revenue recognition, funding cost, opex and allocation bridge to each dimension |
| 37 | Why is profitability different from budget? | Neither usable budget nor governed profitability allocation is available | Finance actuals, budget, allocation rules and variance-driver hierarchy |
| 38 | What are the biggest cost overruns and what is causing them? | Cost-center actuals and budgets are missing | Expense transactions, cost-center hierarchy, budget and cause classification |
| 39 | Which products or customer segments have the highest contribution margin? | Interest collected is not contribution margin | Product/customer revenue plus direct and variable allocated costs |
| 40 | How is our cost of acquisition changing? | Sourcing/marketing cost and channel attribution are absent | Acquisition spend, application source/channel and an approved CAC denominator |
| 42 | Where are our biggest operational bottlenecks? | Application and operational workflow timestamps are absent | Process instance/stage event log, queue time, owner and completion status |
| 43 | Which processes have the highest rejection, rework, exception or turnaround time? | Rejection/rework/exception sources are empty and stage TAT is unavailable | Workflow transitions, reason codes, exception events and timestamps |
| 44 | What operational issues are currently impacting customer experience or revenue? | Complaint/ticket data and impact attribution are absent | Complaint/incident feed, affected customer/process, severity, downtime and revenue impact |
| 46 | Are there any significant compliance or regulatory exceptions that require attention? | NPA status is credit risk, not a compliance-exception register; inspected exception tables are empty | Authoritative exception register, regulation, severity, owner, due date and remediation status |
| 47 | Which legal matters, contracts or cases require management attention? | Legal case tables are empty and the reporting legal flag contains no active case information | Legal matter/case register, exposure, counterparty, stage, next date and owner |
| 48 | What control failures or recurring audit observations should management be concerned about? | Audit tables are empty | Audit findings, control, severity, recurrence, owner and closure status |
| 49 | Are we achieving our strategic initiatives, and which ones are off-track? | No strategic initiative/OKR tracker exists | Initiative, milestone, target, actual, owner, due date, dependency and status |

## 8. Partially answerable questions and the remaining gap

| Q | What can be answered now | What is still missing |
|---:|---|---|
| 4 | Current loan-book KPIs and threshold alerts | Approved enterprise targets for every business KPI |
| 7 | Underperformance after the user identifies a metric and dimension | A default definition of performance and governed causal drivers |
| 13 | Product growth and, after geography promotion, location growth | `MKTCHANNEL` is empty, so channel growth is unavailable |
| 14 | Actual sales/location ranking and trends | Team quotas, capacity and expected performance |
| 26 | Historical disbursement anomalies and limited application-volume anomalies | Complete approval/rejection outcomes and approved anomaly rules |
| 41 | Waivers, unusual receipts and ledger movements requiring review | Confirmed leakage definitions, costs, expected values and investigation outcomes |
| 50 | Agent-linked loan and collection productivity | Authoritative staff master, headcount, capacity, skills and training |

## 9. New non-Oracle feeds required

| Feed | Minimum fields | Questions unlocked |
|---|---|---|
| Business plan and targets | KPI, target value, period, branch/product/team, version, approver | 3–5, 11, 12, 14, 37 |
| Complete LOS workflow | application, stage, entered/exited time, decision, reason, policy version | 15, 16, 25, 26, 42, 43 |
| Finance/Tally actuals and allocations | GL/cost center, amount, date, expense type, allocation key, branch/product/channel | 36–41 |
| Channel attribution | channel/source, campaign, application/customer, acquisition date | 13, 36, 40 |
| Customer service and incidents | case, type, opened/resolved time, severity, customer/process, impact | 44 |
| Compliance exceptions | regulation/control, exception, severity, owner, due date, status | 46 |
| Legal matters and contracts | case/contract, counterparty, exposure, stage, dates, owner | 47 |
| Internal audit findings | audit, control, observation, severity, recurrence, owner, closure | 48 |
| Strategy/OKR tracker | initiative, milestone, target, actual, owner, due date, status | 49 |
| HR/capability | employee, role, team, branch, availability, capacity, skills, training | 50 |
| Contact outcomes for modeling | account/customer, contact time/channel, outcome, promise/payment result | 30 and collections model validation |

## 10. Recommended delivery order

1. **Reconcile current PostgreSQL sources.** Confirm which P0/P1 Oracle tables already exist in Bronze/Silver and record row counts, source SCN, maximum business date, and schema checksum.
2. **Publish geography and hierarchy Gold models.** These provide immediate value without predictive modeling.
3. **Publish receipt, waiver and loan-ledger Gold events.** Add transaction sign/component validation before exposing financial anomaly metrics.
4. **Publish limited application models.** Label the outcome explicitly as `disbursed` versus `not_observed_as_disbursed`; never infer that the remainder was rejected.
5. **Build vintage and collection analyses.** These are derivable from existing database history.
6. **Obtain business feeds.** Targets, costs, workflow events, complaints, compliance, legal, audit, OKR and HR data cannot be manufactured from the current Oracle schema.
7. **Add predictive questions only after governance.** Q17, Q22, Q28 and Q30 require approved definitions/models, validation evidence, monitoring and an accountable business owner.

## 11. Acceptance criteria

The migration and Gold work is complete only when:

- every migrated table has source/target count and schema reconciliation;
- no Gold join silently drops more rows than its documented threshold;
- each metric has a formula, grain, date semantics, owner and coverage warning;
- all 50 evaluation questions assert the expected route and required Gold objects;
- an unavailable dataset produces a specific `not_in_data` response rather than a proxy answer;
- predictive/advisory wording cannot be answered by relabeling a factual ranking; and
- the resulting counts are re-evaluated against the live API and recorded with the catalog version.

## 12. Corrections to older repository documentation

Older analyses that state Oracle has no branch master are no longer valid for the current July source. The live instance contains 67 populated `MBRN` rows, and the July PostgreSQL estate already exposes branch master data in Silver and Gold. Treat the current Oracle endpoint and the latest reconciliation as authoritative, and do not remigrate `MBRN` solely because an older report lists it as absent.
