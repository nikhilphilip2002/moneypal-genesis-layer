# Semantic Views and Low-Token Retrieval Plan

## Objective

Build a governed semantic layer that lets the assistant answer broad, previously unseen
enterprise questions accurately while sending substantially less catalog context to the LLM.
The Top-50 questions remain an acceptance suite, but neither views nor routes may be designed
as one-off solutions for those questions.

The intended data flow is:

```text
Oracle / files / operational applications / approved models
                         ↓
               Bronze — immutable source copy
                         ↓
        Silver — typed, deduplicated, conformed records
                         ↓
       Gold atomic facts and conformed dimensions
                         ↓
        Gold aggregate and analysis-ready marts
                         ↓
     capability graph + compact semantic catalog packs
                         ↓
       deterministic compiler / governed analyses
                         ↓
                       answer
```

The LLM never receives raw Bronze/Silver schemas, full database DDL, or customer rows. It
selects compact business identifiers; deterministic code owns formulas, joins, access rules,
and SQL generation.

## Success criteria

### Accuracy

- 100% semantic correctness on the versioned canonical acceptance suites, including the
  enterprise Top 50.
- At least 95% semantic correctness on paraphrases and compositional questions not present in
  the canonical fixtures.
- 100% numerical reconciliation for governed monetary totals, counts, ratios, conversions,
  target variances, and profitability measures.
- Zero invented metrics, unsupported joins, cross-grain fan-out, or nearby-metric
  substitutions.
- Unsupported claims produce explicit coverage gaps, never plausible proxy answers.

### Token and latency targets

- Source router prompt: no more than 700 catalog tokens.
- Normal metric/dimension planner context: p50 below 800 tokens and p95 below 1,200 tokens.
- Text-to-SQL fallback schema pack: p95 below 3,000 tokens.
- No full-catalog prompt on the normal path once the catalog exceeds the compact-pack budget.
- At least 90% of governed questions compile without text-to-SQL.
- Single-source response latency below 10 seconds p95, excluding database/network outages.
- Repeated normalized questions reuse cached routing and plan results.

## Design principles

1. **Business grains, not question-shaped views.** Build reusable facts such as one repayment
   event or one monthly branch/product result; do not create one SQL view per question.
2. **One authoritative definition per measure.** Synonyms resolve to the same metric id.
3. **No universal mega-view.** Combining unrelated facts creates fan-out, ambiguity, slow
   scans, and larger prompts. Use stars and deterministic multi-query analyses.
4. **Gold is the assistant boundary.** Gold is built from Silver; the assistant never queries
   Bronze or raw Silver.
5. **The model chooses intent, not SQL mechanics.** It selects metric, dimensions, period,
   filters, comparison, and analysis type from constrained identifiers.
6. **Retrieval must preserve closure.** Selecting a metric automatically includes its base
   fact, compatible dimensions, necessary join edges, period rules, and caveats.
7. **Exact vocabulary beats embedding similarity.** Acronyms, codes, ids, and curated synonyms
   use lexical matching before vector ranking.
8. **Compound questions become claims.** Each requested metric/dimension/source is planned and
   evaluated separately, then composed.
9. **Coverage is data.** Freshness, null coverage, match rate, history length, restrictions,
   and sign-off status travel with every result.
10. **Prediction and advice are registered capabilities.** They require an approved model or
    policy artifact; an LLM may not create them.

## Layer contracts

### Bronze

- Preserve source grain, source column names, extraction timestamp, source system, batch id,
  and Oracle SCN or equivalent watermark.
- Never overwrite history with current state.
- Land new spreadsheets and external-system feeds here before modeling.
- Reconcile row count and schema checksum to the source on every load.

### Silver

- Standardize identifiers as text and dates/timestamps to one timezone policy.
- Deduplicate using declared business keys and deterministic survivorship rules.
- Conform entity, customer, account, application, branch, product, scheme, agent, collector,
  channel, geography, GL, and cost-center keys.
- Preserve effective dating for organization and ownership hierarchies.
- Record invalid/unmatched keys instead of silently dropping records.
- Split mixed source tables into stable event, snapshot, and master grains where necessary.

### Gold

- Expose a documented grain, key, date semantics, owner, freshness SLA, restrictions, and
  coverage warning for every object.
- Contain only business-readable columns needed by governed metrics or authorized record
  lookup.
- Publish safe join relationships with tested cardinality and maximum tolerated drop rate.
- Separate event facts, point-in-time snapshots, dimensions, and aggregates.
- Materialize expensive reusable transformations rather than repeatedly asking generated SQL
  to reconstruct them.

## Gold view architecture

The concrete migration from the current 30 Gold views to 18 assistant-facing semantic views,
including exact names, grains, keys, source mappings, column names, unsafe joins, and rollout
gates, is specified in `docs/GOLD_VIEW_CONSOLIDATION_SPEC.md`.

### 1. Conformed dimensions

Create or normalize these reusable dimensions:

| Dimension | Grain | Primary source |
|---|---|---|
| `gold.dim_date` | one calendar date | generated and fiscal-calendar policy |
| `gold.dim_branch` | one effective-dated branch | Silver branch master |
| `gold.dim_geography` | one governed geography code | Silver district/state/region sources |
| `gold.bridge_branch_geography` | branch × effective period | validated branch/geography mapping |
| `gold.dim_product_scheme` | product × scheme × effective period | Silver product/scheme sources |
| `gold.dim_customer_segment` | customer × effective segment | Silver customer/MSME attributes |
| `gold.dim_distribution_channel` | one approved channel/sub-channel | new feed where source is absent |
| `gold.dim_organization` | team/user hierarchy × effective period | Silver sales/collection hierarchies |
| `gold.dim_gl_cost_center` | GL/cost center × effective period | Silver finance mappings/new feed |

Do not duplicate labels independently in every fact. Decode from conformed dimensions so a
branch, product, scheme, segment, or channel has one governed meaning.

### 2. Atomic facts

Retain or reshape the existing 30 views into a small set of unambiguous facts:

| Fact | Grain | Current action |
|---|---|---|
| `gold.fact_loan_account` | one loan account | normalize existing loan account master |
| `gold.fact_disbursement_event` | one disbursement event | retain and reconcile event keys |
| `gold.fact_repayment_due_paid` | one contractual repayment event | retain due-versus-paid semantics |
| `gold.fact_schedule_event` | one scheduled instalment | retain |
| `gold.fact_portfolio_snapshot` | account × snapshot date | retain and extend history |
| `gold.fact_payment_receipt` | one receipt | retain; validate receipt detail linkage |
| `gold.fact_loan_ledger` | one account transaction/component | reconcile signs and component breakup |
| `gold.fact_loan_balance` | account × transaction state/date | retain point-in-time rules |
| `gold.fact_application` | one application | retain limited application master |
| `gold.fact_application_stage` | one stage transition | populate from a complete LOS feed |
| `gold.fact_application_decision` | one decision event | populate from authoritative decisions |
| `gold.fact_collection_assignment` | one assignment event | prove application/account reference key |
| `gold.fact_collection_activity` | one dated collector activity | retain standalone restriction until linked |
| `gold.fact_collection_contact` | one contact/treatment event | new operational feed |
| `gold.fact_gl_balance` | GL × branch × as-of date | retain; never join to lending dimensions without a bridge |
| `gold.fact_target` | KPI × org/dimension × period × version | new FP&A feed |
| `gold.fact_cost_allocation` | cost center × period × allocation target | new Finance feed |
| `gold.fact_operational_incident` | one incident/process event | new Operations/Technology feed |
| `gold.fact_management_issue` | one compliance/legal/audit/strategy issue | domain-owned feeds with typed issue class |
| `gold.fact_workforce_capacity` | org/role × period | new HR feed |
| `gold.fact_model_score` | subject × score date × horizon × model version | approved model registry output |

Compatibility views may preserve current names while the catalog moves to the conformed facts.
Do not expose both old and new objects as competing semantic definitions.

### 3. Aggregate marts

Materialize broadly reusable aggregates, not question-specific answers:

| Mart | Grain | Reusable capabilities |
|---|---|---|
| `gold.mart_origination_monthly` | month × branch × product × scheme × channel | volume, growth, mix, ticket size, conversion |
| `gold.mart_portfolio_daily` | date × branch × product × scheme × segment × DPD class | exposure, PAR, NPA, arrears, migration |
| `gold.mart_vintage_monthly` | origination cohort × MOB × approved dimensions | vintage PAR/NPA and cohort comparison |
| `gold.mart_collections_daily` | date × branch × team × collector × DPD bucket | due, paid, efficiency, shortfall, activity |
| `gold.mart_application_funnel_daily` | date × stage × branch × product × channel | stage conversion, exits, rejection, TAT |
| `gold.mart_profitability_monthly` | month × branch × product × channel × segment | revenue, cost, margin, budget variance |
| `gold.mart_target_attainment_monthly` | month × KPI × approved dimensions | actual, target, variance, attainment |
| `gold.mart_operational_health_daily` | date × process/system/issue type | bottleneck, incident, service and data health |
| `gold.mart_management_attention` | as-of date × issue domain × org/severity | cross-domain executive attention queue |
| `gold.mart_workforce_monthly` | month × org × role/skill | capacity, productivity, vacancies, capability gaps |

Aggregate marts must reconcile to atomic facts. The compiler should prefer a mart only when
its grain can answer the request exactly; otherwise it falls back to the atomic fact.

### 4. Serving projections

Create narrow projections for common planner families:

- `portfolio_performance`;
- `origination_performance`;
- `collections_performance`;
- `application_performance`;
- `finance_performance`;
- `operations_performance`;
- `governance_attention`;
- `workforce_performance`.

These are logical capability packs, not denormalized joins. Each projection declares which
metrics, dimensions, periods, comparisons, explanations, and drill paths it supports.

## Semantic catalog redesign

### Domain registry

Add `catalog/defs/gold/domains.yaml`:

```yaml
- id: collections
  label: Collections
  synonyms: [recovery, arrears, repayment performance]
  facts: [gold.fact_repayment_due_paid, gold.fact_collection_activity]
  marts: [gold.mart_collections_daily]
  metric_ids: [collection_efficiency, amount_collected, collection_shortfall]
  dimension_ids: [branch, collection_team, collector, dpd_bucket, product]
  analyses: [collections_focus, collections_deterioration]
```

The first retrieval step selects one to three domains. It does not search hundreds of columns.

### Capability graph

Add `catalog/defs/gold/capabilities.yaml`. For every metric or analysis, declare:

- compatible dimensions;
- supported period grains and minimum history;
- point-in-time versus flow behavior;
- allowed comparisons: previous period, previous year, target, benchmark;
- supported operations: value, rank, trend, share, contribution, driver, anomaly, forecast;
- required facts/marts and safe joins;
- required role and sensitivity;
- coverage requirements and sign-off status;
- forbidden labels and proxy substitutions;
- available drill paths and terminal worklists.

This graph prevents the planner from seeing or selecting invalid combinations.

### Compact semantic packs

Generate a pack after domain retrieval containing only:

1. candidate metric ids with one-line definitions and units;
2. compatible dimensions only;
3. valid period/comparison/operation enums;
4. exact enum matches needed by the question;
5. relevant analysis/worklist ids;
6. short coverage or restriction codes.

Example target pack:

```text
DOMAIN collections
M collection_efficiency|paid/due|percent|flow
M collection_shortfall|due-paid|inr|flow
D branch,product,dpd_bucket,collector
P today,this_month,last_month,fy_to_date,explicit
O value,rank,trend,share,drivers
A collections_focus,collections_deterioration
R history:repayment>=2025-10-15
```

The deterministic compiler resolves ids into full formulas, tables, joins, caveats, and SQL.
Those details do not consume planner tokens.

## Retrieval and planning pipeline

```text
question
  ↓
normalize + deterministic record/id detection
  ↓
claim decomposition
  ↓
source routing
  ↓
domain retrieval (lexical + vector)
  ↓
capability closure and incompatibility filtering
  ↓
compact semantic pack
  ↓
constrained plan: metric/dimension/period/filter/operation ids
  ↓
deterministic compile or registered analysis/worklist/model
  ↓
execute, validate, compose, cite
```

### Retrieval rules

- Use exact phrase, acronym, id, and enum-code matches first.
- Use vector retrieval only for paraphrase recall.
- Retrieve domains before metrics and columns.
- Apply capability closure after ranking; embeddings must never choose join paths.
- If the top candidate margin is low, broaden the pack or clarify rather than guessing.
- Always include exact lexical candidates even when vector rank is low.
- Retrieve enum values separately so high-cardinality member names do not pollute metric
  retrieval.
- Cache normalized-question → domains and normalized-question → plan by catalog version, role,
  and data-coverage version.

### Claim decomposition

Represent compound requests explicitly:

```json
{
  "claims": [
    {"metric": "disbursement_total", "dimension": "product", "operation": "growth"},
    {"metric": "disbursement_total", "dimension": "region", "operation": "growth"},
    {"metric": "disbursement_total", "dimension": "channel", "operation": "growth"}
  ]
}
```

Each claim is independently supported, answered, clarified, or marked unavailable. The final
card cannot imply that one returned dimension satisfies all requested dimensions.

### Deterministic execution priority

1. Record/customer/account grammar.
2. Cached validated plan.
3. Registered briefing, analysis, signal, worklist, or model capability.
4. QuerySpec compiled from governed ids.
5. Retrieved-schema text-to-SQL only for authorized fields not modeled semantically.
6. Explicit coverage response when none is safe.

## Lower-token implementation changes

### Planner prompt

- Stop sending the full metric/dimension catalog on every call as the catalog grows.
- Keep a small fixed instruction prefix eligible for provider prompt caching.
- Insert only the compact semantic pack and the normalized user claim.
- Return ids in constrained JSON; omit explanations from the planning call.
- Generate user-facing prose after execution from structured results, not during planning.

### Text-to-SQL fallback

- Retrieve at most three table bundles initially.
- A table bundle contains table grain, allowed columns, key, date fields, restrictions, and
  only the join edges connecting retrieved tables.
- Expand once when validation proves a required field is absent; never send the whole schema.
- Prefer business aliases over raw Oracle column names in the prompt.
- Reject SQL using a column, table, join, function, or grain absent from the retrieved bundle.

### Result composition

- Compute rankings, contributions, thresholds, anomaly scores, and totals in SQL/Python.
- Send the narrator only headline values and top contributors, not hundreds of rows.
- Use deterministic templates for standard metrics, comparisons, and coverage statements.
- Use an LLM narrator only for multi-finding synthesis, with every permitted claim supplied as
  structured evidence.

### Conversation

- Persist metric/dimension/filter/period ids as the conversation anchor.
- Resolve structural follow-ups such as “which branches?”, “why?”, “last quarter?”, and “show
  the accounts” without another planning call.
- Compact prose history while retaining structured anchors and source lineage.

## View performance optimization

- Partition large event/snapshot facts by business date where PostgreSQL planning benefits.
- Index every declared primary key, date filter, common foreign key, and high-value compound
  filter after checking actual query plans.
- Materialize monthly/daily marts incrementally using source watermarks.
- Store precomputed numerator and denominator components for ratios; never average ratios.
- Maintain HLL or other approximate structures only for exploratory UI counts, never governed
  financial/regulatory answers.
- Run `ANALYZE` after materialized refreshes and monitor maximum plan cost.
- Limit default result rows by answer type: KPI 1, trend 36 periods, ranking 50, worklist 50.
- Preserve full exports through a separate governed export path rather than enlarging LLM/UI
  query limits.

## Data quality and publication gates

Every Gold object must pass:

- unique-key and not-null tests;
- source-to-Silver-to-Gold reconciliation;
- join cardinality and unmatched-key thresholds;
- event-date and as-of-date validity;
- freshness and history-depth checks;
- accepted-value checks for status/code dimensions;
- ratio numerator/denominator reconciliation;
- PII classification and role enforcement;
- owner approval for business formulas;
- query-plan cost and representative latency tests.

Views that fail remain unpublished from the active catalog. Zero rows in a non-authoritative
source must be reported as missing coverage, not “zero exceptions.”

## Generalized evaluation strategy

### Test suites

1. **Canonical business suites:** Top 50 plus approved departmental questions.
2. **Compositional grid:** valid metric × dimension × period × operation combinations generated
   from the capability graph.
3. **Paraphrases:** at least 10 linguistic variants per canonical intent.
4. **Invalid combinations:** target comparisons without targets, GL by loan product, forecasts
   without registered models, and other forbidden substitutions.
5. **Compound questions:** mixtures of supported and unsupported claims.
6. **Conversation chains:** follow-ups, corrections, period changes, drill-down, and pronouns.
7. **Security:** role visibility, PII masking, injection, destructive requests, and audit logs.
8. **Freshness/coverage:** stale, partial, empty, and missing-source cases.

### Metrics

- source-routing precision/recall;
- domain retrieval recall@1 and recall@3;
- required metric/dimension recall in the compact pack;
- plan exact match and executable-plan rate;
- SQL validation and numerical reconciliation;
- claim-level answer precision and completeness;
- unsupported-claim abstention precision;
- prompt input/output tokens by stage;
- latency and cache-hit rate;
- semantic regressions by catalog version.

An “answered” SSE event is not an accuracy metric. Evaluation must inspect the requested claims,
returned measures, dimensions, caveats, and ground truth.

## Implementation phases

### Phase 0 — Measure the current system

- Record prompt tokens, retrieved entries, route, plan, SQL, latency, rows, and outcome for the
  current evaluation corpus.
- Establish current retrieval recall and semantic accuracy baselines.
- Freeze the Top-50 suite as one acceptance set, not a routing lookup table.

**Exit:** reproducible accuracy, token, and latency baseline.

### Phase 1 — Inventory and contracts

- Profile all Bronze, Silver, and Gold objects.
- Reconcile the 30 current Gold views to their Silver sources.
- Assign every object a grain, key, owner, freshness SLA, sensitivity, restriction, and status:
  retain, reshape, merge, compatibility-only, or retire.

**Exit:** no active view has an ambiguous grain or untested join.

### Phase 2 — Conformed dimensions and atomic facts

- Implement the conformed dimensions and fact naming/grain model.
- Repair application, geography, hierarchy, collection attribution, and ledger defects where
  current source data permits.
- Preserve compatibility views until all consumers migrate.

**Exit:** atomic facts reconcile and all dimension joins meet coverage thresholds.

### Phase 3 — Aggregate marts

- Build origination, portfolio, vintage, collections, and existing-data operational marts.
- Add incremental refresh, reconciliation, indexes, and freshness monitoring.
- Add target, profitability, incident, governance, workforce, and score marts only after their
  sources arrive and owners approve definitions.

**Exit:** common analytical questions avoid repeated multi-million-row transformations.

### Phase 4 — Capability graph and compact catalog

- Add domain and capability definitions.
- Generate compact semantic packs and validate closure.
- Add compatibility/exclusion metadata and structured coverage codes.

**Exit:** every governed capability can produce a self-contained planner pack below the token
budget.

### Phase 5 — Retrieval and constrained planner

- Implement domain-first lexical/vector retrieval.
- Replace full-catalog normal-path prompts with compact packs.
- Add confidence margins, clarification, caching, and exact-term preservation.
- Keep lexical-only fallback when embeddings are unavailable.

**Exit:** at least 99% required-entry recall on canonical/paraphrase suites with planner p95 below
1,200 catalog tokens.

### Phase 6 — Deterministic analyses and conversations

- Generalize briefings, drivers, quadrants, concentration, funnel, target variance, vintage,
  anomaly, worklist, and attention-queue composers.
- Resolve structural follow-ups from the saved spec.
- Add claim-level partial answers and factual pivots.

**Exit:** at least 90% of governed questions avoid text-to-SQL and repeated planning calls.

### Phase 7 — Missing enterprise sources

- Land plans/targets, LOS stages/decisions, channels, Finance allocations, contacts, incidents,
  governance registers, strategy, and HR through Bronze → Silver → Gold.
- Register predictive scores only after model-risk approval.

**Exit:** all source-dependent capability packs are active and reconciled.

### Phase 8 — Certification and rollout

- Run canonical, compositional, paraphrase, adversarial, reconciliation, security, freshness,
  token, and load tests.
- Shadow new planning beside the current path and compare claim-level outcomes.
- Roll out by domain with automated rollback on semantic or reconciliation regression.

**Exit:** canonical suites are 100% correct, broader suites meet the 95% target, and token/latency
budgets hold in production-like conditions.

## Required repository changes

- Add `domains.yaml` and `capabilities.yaml` to the Gold catalog.
- Extend catalog types and startup validation for compatibility, operations, comparisons,
  minimum history, roles, and forbidden substitutions.
- Add a compact-pack builder and domain-first retrieval tests.
- Change the planner to accept a retrieved pack rather than the whole catalog on the normal
  path.
- Add claim decomposition and per-claim coverage results to contracts/API/UI.
- Add mart-aware source selection to the compiler without changing metric definitions.
- Replace status-only enterprise evaluation with claim-level ground-truth assertions.
- Add token budgets as testable telemetry and CI regression thresholds.
- Display source, as-of date, coverage, formula/model version, and caveats on every answer.

## Definition of done

This optimization is complete when:

1. views are organized around reusable dimensions, atomic facts, and aggregate marts rather
   than known questions;
2. the assistant retrieves compact domain packs with all and only the capabilities needed for
   the request;
3. formulas and joins remain deterministic and outside the LLM prompt;
4. at least 90% of governed questions compile without text-to-SQL;
5. normal planner catalog context stays below 1,200 tokens at p95;
6. canonical suites, including the enterprise Top 50, are 100% semantically correct;
7. unseen paraphrase/compositional suites maintain at least 95% correctness; and
8. missing facts remain explicit data gaps until authoritative Bronze/Silver sources exist.
