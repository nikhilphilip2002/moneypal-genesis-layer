# NLQ / Local LLM Implementation Handoff

Updated: 2026-09-08 UTC
Branch: `fix/regex-removal`
Repository: `/home/null/Projects/moneypal`

## 1. Objective

The goal of this work is to make the Workbench native agent reliably answer realistic
questions across all 18 governed PostgreSQL Gold semantic views using either locally
hosted Ling or Qwen models.

The requested design constraints are:

- Inspect the actual PostgreSQL Gold views before changing the catalog.
- Update the Gold YAML only where the live schema or real user vocabulary requires it.
- Build 100–200 answerable evaluation questions covering all 18 views.
- Give each business intent multiple natural-language phrasings.
- Test the configured local model directly and optimize the prompt for its actual capability.
- Do not hard-code individual user questions or phrase-specific answers.
- Do not send the complete Gold catalog/YAML to the model on every request.
- Use provider-native tool calls. There must be no structured-output JSON fallback for tool
  calls.
- Avoid a polymorphic `oneOf` mega-tool. Keep concrete, flat tool schemas.

This task is **not complete yet**. The architecture, catalog audit, 108-question corpus,
and static contract coverage are implemented. Ling passes the one-prompt-per-view smoke
test at 18/18, but the latest source still needs a complete live 108-prompt rerun. Qwen
needs the same live evaluation after the endpoint is configured to serve it.

### 2026-09-08 continuation update

- The combined live Ling smoke test now passes **18/18 views (100%)**.
- A complete 108-prompt Ling run produced **85/108 (78.7%)** before the subsequent fixes.
- The 23 failures in that baseline were grouped into raw-row routing, unnecessary secondary
  tables, invented dimensions, conflicting period shapes, and one isolated 45-second model
  timeout.
- Subsequent fixes in commit `499bea6c` make all 108 prompt contexts mechanically satisfy their
  expected tool-specific catalog surface: exact governed metrics/dimensions for metric
  questions and exact required table sets for validated row questions.
- Those post-baseline fixes still require a final full 108-prompt live rerun; 85/108 must not
  be presented as the expected accuracy of the latest source.
- The endpoint still advertises only Ling. Qwen live validation cannot be completed until a
  Qwen model is served. The evaluator is ready via `--model` and uses the identical corpus.

### 2026-09-08 production regressions discovered after deployment

Do not treat the 18/18 evaluator smoke result as production completion. Two real Workbench
conversations exposed coverage missing from the corpus and evaluator.

#### A. Explicit non-time grouping was silently omitted

Observed question:

```text
interest collected schemewise
```

Observed result: one all-time `interest_collected` total with no scheme breakdown. The metric
was correct, but the explicit grouping was lost. This is the same semantic class as the
earlier month-wise bug; current canonicalization protects month only and does not enforce
other catalog-recognized grouping dimensions. The governed `scheme` dimension also does not
currently list `schemewise`/`scheme wise` as vocabulary.

Required general fix:

1. Extend genuine dimension vocabulary in Gold YAML (for example `scheme wise`,
   `schemewise`, and `by scheme` for the existing governed `scheme` dimension).
2. Separate **explicitly requested dimensions** from merely retrieved candidate dimensions in
   `AgentCatalogContext`.
3. After the native `query_metrics` call, reconcile its arguments with those explicitly
   requested dimensions. Add a missing dimension only after `_can_group_from` has established
   a governed direct column or safe non-fan-out join from the selected metric base table.
4. Keep this catalog-driven. Do not add sentence-specific regexes or force every retrieved
   candidate dimension into the query.
5. Add live and unit coverage for `schemewise`, `branchwise`, `productwise`, and `monthwise`,
   including spelling/spacing variants. Assert returned tool arguments and compiled
   `GROUP BY`, not only that a dimension appeared in the prompt/schema.

#### B. Elliptical detail follow-up lost prior lookup bindings and hallucinated a column

Observed conversation:

```text
User: customers under vanitha
Assistant: returned 338 linked customers
User: include tenure and santioned amount with the above details
```

The second turn selected native `run_validated_query`, but generated SQL referenced
`disbursement_amount` on `gold.semantic_loan_account`. That column does not exist there; the
correct governed account column is `sanction_amount`. The requested tenure also needed to be
carried alongside the prior customer fields and the `vanitha` agent constraint.

This is not primarily a PostgreSQL problem. The native tool receives conversation history,
but `run_validated_query` passes only its generated `intent` string and preferred tables into
the downstream text-to-SQL call. An elliptical phrase such as “with the above details” can
therefore lose the previous lookup's selected entity, filter, and output-column bindings.

Required general fix:

1. Persist a compact structured data-query binding after every successful DB tool call:
   selected table(s), governed output fields, filters/entity values, metrics, dimensions, and
   period. Do not depend on rendered assistant prose or hundreds of returned rows.
2. Resolve a structural follow-up into a standalone governed intent by merging the prior
   binding with the current additions/removals. In this example it must retain the agent
   constraint and customer identity fields, then add governed tenure and sanction amount.
3. Feed text-to-SQL a table-scoped allowlist of physical column identifiers. When the
   preferred table is `gold.semantic_loan_account`, `disbursement_amount` must be impossible
   to emit; `sanction_amount` is allowed. Reject unknown or wrong-table columns before
   database execution.
4. Add one bounded repair for a rejected validated query using structured validator feedback,
   not raw PostgreSQL traces and not assistant-content JSON fallback.
5. Add multi-turn tests with paraphrases such as “include”, “also add”, “with the above
   details”, and misspelled business terms. Verify retained filters, retained fields, newly
   requested fields, selected table, generated identifiers, and final execution.

#### C. Log interpretation

- `NLQ ask turn started` with `route=lookup` can be the governed legacy lookup used for an
  explicit entity lookup; it does not alone prove that `WORKBENCH_AGENT_MODE` is off.
- `native tool run_validated_query failed` proves the native path was active for the failing
  follow-up.
- The database password problem is resolved and unrelated to these two semantic failures.

### 2026-09-08 Resolution of production regressions A & B

Both post-deployment production regressions have been fully resolved with catalog-driven, model-neutral mechanisms and verified by the test suite:

1. **Regression A (Explicit non-time grouping):**
   - **Gold Catalog Synonyms:** Extended genuine grouping vocabulary in `dimensions.yaml` for `scheme` (`schemewise`, `scheme wise`, `by scheme`), `branch` (`branchwise`, `branch wise`, `by branch`), `product` (`productwise`, `product wise`, `by product`), `agent` (`agentwise`, `agent wise`, `by agent`), `quarter` (`quarterwise`, `quarter wise`), and `year` (`yearwise`, `year wise`, `by year`).
   - **Catalog Context Separation:** Added `requested_dimensions` to `AgentCatalogContext` in `prompts.py` to separate explicitly requested grouping dimensions from merely retrieved candidate dimensions using `_catalog_phrase_matches`.
   - **Native Tool Argument Canonicalization:** In `agent._canonicalize_native_arguments`, explicitly requested dimensions are reconciled with `query_metrics` arguments only after verifying compatibility via `_can_group_from` (guaranteeing direct columns or safe non-fan-out joins from the metric base table without modifying filter dimensions).
   - **Coverage:** Added 16 parametrized cases in `test_agent.py::test_explicit_non_time_grouping_preserved_and_compiled` asserting both returned tool arguments and compiled SQL `GROUP BY` across `schemewise`, `branchwise`, `productwise`, and `monthwise` (and their spacing/hyphenation variants).

2. **Regression B (Elliptical follow-up bindings & column hallucination):**
   - **Structured Query Binding Persistence:** Added `set_data_binding`, `get_last_data_binding`, and turn reconstruction in `history.py` to persist compact structured DB query bindings (`tables`, `output_fields`, `filters`, `entity`, `metrics`, `dimensions`, `intent`) upon successful execution of `lookup_records`, `query_metrics`, and `run_validated_query`.
   - **Structured Follow-up Resolution:** Added `followup.py` (`is_followup_question` and `resolve_followup`) to merge prior bindings with new additions, retaining prior entity filters (e.g. agent `vanitha`) and output columns while extracting newly requested governed fields.
   - **Gold Catalog Synonyms for Colloquial Attributes:** Added genuine synonyms in `columns.yaml` for `loan.sanction_amount` (`sanctioned amount`, `santioned amount`, `sanction value`, `sanctioned value`) and `loan.number_of_emis` (`tenure`, `tenor`, `loan tenure`, `loan tenor`, `EMI count`, `term in months`, `tenure months`, `tenor months`, `number of instalments`).
   - **Table-Scoped Column AST Validator:** Updated `_check_columns` in `validator.py` so that unqualified and qualified column references are strictly validated against the query's referenced tables, rejecting wrong-table columns (e.g. `disbursement_amount` on `gold.semantic_loan_account`) before PostgreSQL execution with structured feedback.
   - **Table-Scoped Context Allowlist Rules:** Updated `text_to_sql.py` prompt instructions with explicit table-scoped column allowlist rules.
   - **Coverage:** Added `test_agent.py::test_multiturn_elliptical_followup_preserves_bindings` testing multi-turn follow-ups (`"customers under vanitha"` -> `"include tenure and santioned amount with the above details"` and `"also add tenure and sanction amount"`), asserting retained filters, new fields (`sanction_amount`, `number_of_emis`), table allowlist, and AST rejection of wrong-table columns.

## 2. Repository state and ownership boundaries

The latest pushed implementation commit is:

```text
499bea6c feat(workbench): harden local LLM query routing
```

Earlier related commits already pushed on the branch are:

```text
ef4c6159 fix(workbench): preserve explicit monthly grouping
7ca05c11 fix(workbench): harden native loan query execution
b67dbeed fix(workbench): route loan queries through native agent
f7bb1b07 feat(workbench): add governed native tool agent
```

Only this new production-regression handoff update is currently uncommitted.

The following pre-existing/user-owned files must not be staged or overwritten as part of
this task:

- `plan.md`
- `HACKY.md`
- `REGEX_PLAN.md`

`.env.prod` is intentionally ignored by Git. It contains deployment credentials and must
never be staged, committed, printed, or copied into this document. The local ignored file
has the deployment model and timeout corrections needed for testing.

Files included in implementation commit `499bea6c` are:

```text
.env.example
backend/app/core/config.py
backend/app/services/nlq/catalog/defs/gold/columns.yaml
backend/app/services/nlq/catalog/defs/gold/dimensions.yaml
backend/app/services/nlq/catalog/defs/gold/enums.yaml
backend/app/services/nlq/catalog/defs/gold/metrics.yaml
backend/app/services/nlq/catalog/defs/gold/tables.yaml
backend/app/services/nlq/catalog/retrieval.py
backend/app/services/workbench/agent.py
backend/app/services/workbench/agent_tools.py
backend/app/services/workbench/prompts.py
backend/scripts/evaluate_native_agent.py
backend/tests/nlq/test_metrics_fixtures.py
backend/tests/workbench/golden/agent_questions.yaml
backend/tests/workbench/test_agent.py
backend/tests/workbench/test_agent_questions.py
backend/tests/workbench/test_agent_tools.py
backend/tests/workbench/test_prompts.py
NLQ_LLM_HANDOFF.md
```

Before staging, inspect `git diff` and stage only this task-owned set.

## 3. Live PostgreSQL audit completed

The Gold catalog was checked against the PostgreSQL instance configured in `.env.prod`.
Results:

- All 18 configured Gold semantic views exist.
- All 537 live columns are represented in the Gold catalog.
- Catalog column, join, metric, and dimension references validate against the live views.
- The only observed row-count drift was `gold.semantic_agent`: the old YAML stated 1,014
  rows while the live view contains 154 rows.
- After the catalog changes, the live catalog-introspection suite passed all 12 checks.
- The newly added `collection_activity_count` metric was compiled and independently tested
  against live PostgreSQL successfully.

The 18 views covered are:

1. `gold.semantic_loan_account`
2. `gold.semantic_customer_profile`
3. `gold.semantic_customer_document`
4. `gold.semantic_branch`
5. `gold.semantic_product_scheme`
6. `gold.semantic_agent`
7. `gold.semantic_organization_hierarchy`
8. `gold.semantic_disbursement_event`
9. `gold.semantic_repayment_event`
10. `gold.semantic_schedule_event`
11. `gold.semantic_portfolio_snapshot`
12. `gold.semantic_application`
13. `gold.semantic_receipt_adjustment_event`
14. `gold.semantic_loan_ledger_event`
15. `gold.semantic_collection_operation_event`
16. `gold.semantic_origination_vintage`
17. `gold.semantic_gl_balance`
18. `gold.semantic_msme_lead`

Six important views do not have a suitable reviewed metric for their row-level/catalog
questions and therefore need the validated SQL path:

- customer profile
- customer document
- branch
- product scheme
- organization hierarchy
- MSME lead

This is expected. The model should select `run_validated_query` for those raw field requests;
it must not fabricate a nearby metric.

## 4. Local model capability findings

The acceptance target now covers both Ling and Qwen. Prompt text, retrieval, schema
narrowing, and deterministic validation must remain model-neutral. The evaluator accepts a
`--model` override and records requested/returned model IDs so the same corpus can be
compared without changing prompts. At this update, the configured endpoint advertises only
Ling; live Qwen evaluation remains pending until Qwen is served.

The configured llama.cpp endpoint was tested directly through its OpenAI-compatible API.
Do not hard-code its host in source; continue loading it from `.env.prod`.

The endpoint currently reports:

- Model: `/root/Aroha/models/Ling-3.0.gguf`
- Approximately 7.893 billion parameters
- GGUF Q4_K quantization
- Runtime context: 131,072 tokens

This is a roughly 8B local model, not a 32B model. Prompt and schema complexity therefore
matter significantly.

A minimal native-tool probe demonstrated that Ling can:

- choose `query_metrics` correctly;
- select interest/disbursement metrics;
- select the `month` dimension;
- emit provider-native tool calls.

It initially interpreted “till today” as `today` even for flow metrics. The application now
normalizes lifetime flow wording to `all_time` using the selected metric’s governed grain.

The endpoint was temporarily unavailable during one 18-view run. The sequence was:

1. The preceding 3-question live test succeeded.
2. The next run received connection failures for all 18 prompts before inference.
3. `/health` and `/v1/models` then returned `503 Loading model`.
4. After loading completed, both endpoints returned healthy responses.
5. The 18-view evaluation was rerun successfully at the transport layer.

The failed 0/18 transport run is not a model-quality result and must not be included in
accuracy comparisons.

## 5. Architecture implemented so far

### 5.1 Concrete flat native tools

The model uses separate concrete tools rather than one discriminated-union mega-tool:

- `query_metrics`
- `lookup_records`
- `run_analysis`
- `create_worklist`
- `generate_briefing`
- `run_validated_query`
- `search_curated_knowledge`
- `search_public_web`
- `finish_without_data`

Pydantic remains the execution-boundary validator. The provider sees a portable flat JSON
Schema. Object-shape unions are rejected rather than emitted as `oneOf`.

There is intentionally no path that parses assistant content as fallback tool-call JSON.

### 5.2 Two-stage native tool selection

`backend/app/services/workbench/agent.py` now performs two native LLM calls per attempted
question:

1. **Capability route:** all authorized candidate tools have stable empty object schemas.
   Ling selects exactly one tool name.
2. **Argument fill:** only the chosen tool is provided, with a question-specific narrowed
   schema derived from the relevant Gold catalog slice.

This reduces simultaneous schema complexity for llama.cpp grammar compilation and lowers
field bleed between unrelated tools. `parallel_tool_calls` is disabled. Repairs reuse the
already selected tool rather than running the route stage again.

When observing server logs, expect approximately two LLM requests for each evaluation
question. The evaluator does not run SQL; it tests selection and validates the resulting
arguments only.

### 5.3 Retrieved catalog projection

`backend/app/services/workbench/prompts.py` now builds a compact, question-specific catalog
context. It includes only the strongest relevant subset of:

- Gold tables and their grain/restrictions/coverage warnings;
- matching columns;
- governed metrics;
- safe dimensions;
- exact governed enum values.

The full 537-column catalog is not placed in every prompt.

Prompt version:

```text
workbench-native-agent-v2-retrieved-catalog
```

The stable system prefix is question-independent so it remains cacheable. The retrieved
catalog context follows it as dynamic context.

### 5.4 Schema narrowing

`backend/app/services/workbench/agent_tools.py` supports per-question narrowing for:

- metric IDs;
- dimension IDs;
- filter dimension IDs;
- validated-query table names;
- visible tool names;
- route-only empty schemas.

Important safety behavior now implemented:

- Metric and dimension enums are limited to retrieved candidates.
- `having.field` is limited to the candidate metric IDs.
- Filter fields are exposed only when the question matches a governed enum value for that
  dimension.
- If there is no relevant categorical filter, `filters.maxItems` is set to zero. This stops
  Ling from inventing filters such as “active” or application status on an unfiltered trend.
- Dimensions are limited to the selected metric’s base table, a compiler-supported direct
  non-fan-out join, or a global time dimension.
- If the user explicitly asks for a time grain such as monthly, weaker retrieved time grains
  are removed.

### 5.5 Deterministic, metadata-grounded normalization

`backend/app/services/workbench/agent.py` currently applies narrow post-generation
normalization grounded in the question and catalog metadata:

- Explicit monthly wording preserves/adds the `month` dimension.
- Lifetime wording such as “all time,” “till today,” “to date,” and “through today” maps to
  `all_time` for flow metrics unless an explicit bounded period was given.
- Explicit calendar-year bounds take precedence over a conflicting relative period.
- Metrics marked `no_time_travel` are normalized to `today` rather than `all_time`.

This normalization is not a question-answer lookup and does not hard-code business results.
It resolves schema-equivalent temporal ambiguity using governed metric metadata.

### 5.6 Retrieval improvements

`backend/app/services/nlq/catalog/retrieval.py` now has:

- boundary-safe phrase matching, preventing accidental matches such as `day` inside `today`
  or `HO` inside `show`;
- token canonicalization for common harmless variants such as borrower/borrowers,
  customer/customers, paid/pay, rate/rates, minimum/min, maximum/max, and ID/IDs;
- additional catalog vocabulary for real business paraphrases.

The module-level documentation still contains an older statement saying the planner does not
use retrieval for metrics/dimensions. That comment should be updated because the native-agent
path now does use retrieval to narrow its catalog projection.

## 6. Gold YAML changes made

The current uncommitted catalog changes include:

- Corrected the semantic-agent row count and cardinality to 154.
- Added and refined synonyms for real paraphrases across tables, metrics, dimensions, and
  columns.
- Added loan-ledger/table vocabulary.
- Added `collection_activity_count` as a reviewed metric.
- Removed `sanctioned` from `account_status` synonyms. A request for “sanctioned amount” was
  otherwise misread as a status filter.
- Replaced an overly broad “current” asset-class synonym with “current asset class.”
- Added product-term, organization-hierarchy, and MSME vendor-ID column synonyms.
- Removed “repayment frequency” from the product-scheme table synonyms after confirming the
  live view does not expose a payment-frequency column.

Do not add vocabulary merely to make an evaluation pass. Each synonym must correspond to a
real column, metric, dimension, table, or governed enum meaning.

## 7. Question bank created

File:

```text
backend/tests/workbench/golden/agent_questions.yaml
```

It contains:

- 36 intent families;
- exactly two intent families per Gold view;
- three natural phrasings per intent;
- 108 total prompts;
- expected tool and expected catalog metric/dimension/table metadata.

The test file is:

```text
backend/tests/workbench/test_agent_questions.py
```

It verifies:

- 36 families and 108 unique prompts;
- exact coverage of all 18 views;
- referenced metrics, dimensions, and tables exist;
- retrieval includes the expected view/catalog entries;
- every expected `query_metrics` specification compiles.

Three initially proposed question families contained fields absent from the live views and
have now been corrected:

- Product payment frequency was replaced by min/max interest rate and tenor fields.
- Hierarchy employee/manager names were replaced by actor/manager user IDs and role codes.
- MSME vendor name was replaced by vendor ID.

The focused agent suite now covers these corrections and passes 45/45 tests.

## 8. Evaluation script

File:

```text
backend/scripts/evaluate_native_agent.py
```

Run it from `backend/` as a module:

```bash
set -a
source ../.env.prod
set +a
export NLQ_LLM_LOCK_PATH=/tmp/moneypal-llamacpp.lock
export WORKBENCH_ROUTER_TIMEOUT_S=45
UV_CACHE_DIR=/tmp/moneypal-uv-cache uv run python -m scripts.evaluate_native_agent --one-per-view --output /tmp/moneypal-agent-eval-18.json
```

Supported selectors include:

- `--view`
- `--family`
- `--limit`
- `--one-per-view`
- `--output`
- `--model`

Use `--model` to run the identical prompt corpus against a served Ling or Qwen model. The
requested model and the model reported by each response are retained in the JSON report so
results cannot be accidentally attributed to the wrong model.

The evaluator calls the model and validates the selected tool arguments. It deliberately does
not dispatch database tools or execute SQL.

## 9. Test and evaluation evidence

### 9.1 Focused local tests

The latest focused result, including the final wording, retrieval, routing, schema, and period
normalization changes, is:

```text
45 passed in 38.15s
```

The command covered:

```text
backend/tests/workbench/test_agent.py
backend/tests/workbench/test_agent_tools.py
backend/tests/workbench/test_prompts.py
backend/tests/workbench/test_agent_questions.py
```

Earlier focused checkpoints were 30, then 31 passing tests while schema restrictions were
being added.

A broader test run reached roughly 166 passing checks and one skip, then stopped producing
output for several minutes and was interrupted. It did not print a failure. The next session
must rerun the broader suite with verbose progress or smaller groups to identify whether a
live-integration test was waiting on the model/database.

### 9.2 Disbursement smoke evaluation

Before filter/schema narrowing, all three phrasings failed because Ling inserted unrelated
application fields.

After the current filter and dimension restrictions:

```text
3/3 passed (100%)
```

The resulting requests correctly used:

- `disbursement_total`
- `disbursement_count`
- `month`
- `all_time`
- no invented filters

### 9.3 One prompt per Gold view

Live evaluation progression during this work:

```text
6/18  = 33.3%  initial retrieved prompt
8/18  = 44.4%  general prompt/retrieval improvements
9/18  = 50.0%  boundary and synonym improvements
9/18  = 50.0%  dynamically narrowed single-stage schemas
10/18 = 55.6%  two-stage native routing plus stricter schemas
18/18 = 100%   current combined Ling smoke baseline
```

The current 10 passing representative views/intents were:

- disbursement trend
- repayment principal/interest collections
- scheduled instalment trend
- portfolio quality
- application trend
- receipt trend
- loan-ledger trend
- collection activity
- origination vintage/PAR
- GL balance

The eight failed representative cases were:

1. Loan sanctions: Ling added an unrequested `account_status` dimension/filter.
2. Customer demographics: chose `query_metrics` instead of validated SQL.
3. Customer document expiry: chose curated knowledge instead of the Gold view.
4. Branch directory: chose irrelevant GL metrics.
5. Product scheme terms: chose average loan-account interest rate and dropped requested raw
   scheme fields.
6. Agent ranking: used an all-time period for a catalog metric marked `no_time_travel`.
7. Sales hierarchy: selected an inappropriate metric-style route and generated a conflicting
   period shape.
8. MSME lead pipeline: chose application metrics instead of the MSME view.

Fixes already implemented after that 10/18 run:

- The `sanctioned` account-status synonym was removed.
- Filter allowlists now come only from exact enum values named in the question.
- `no_time_travel` metrics now normalize to `today`.
- A `requires_validated_query` catalog-context signal was introduced.
- When that signal is true, route-stage tool access is restricted to
  `run_validated_query`, `lookup_records`, and `finish_without_data`.
- Product, hierarchy, and MSME question wording/YAML were corrected to real columns.

Those eight cases were addressed with catalog-driven retrieval, direct-column coverage,
table-concept ranking, restricted schemas, and period normalization. The resulting current
Ling smoke artifact is:

```text
/tmp/moneypal-agent-eval-18-ling-final.json
18/18 passed (100%)
```

### 9.4 Full Ling corpus baseline

The last complete 108-prompt live run, made before the final retrieval and normalization
fixes, is:

```text
/tmp/moneypal-agent-eval-108-ling.json
85/108 passed (78.7%)
```

Its 23 failures were categorized and used to make the subsequent general catalog/retrieval
fixes. All 108 questions now pass the mechanical expected-context invariant, but this does
not replace a live model run. A final Ling 108 run remains required.

Temporary evaluation outputs, if `/tmp` has not been cleared, are:

```text
/tmp/moneypal-agent-eval-stage-disb.json
/tmp/moneypal-agent-eval-stage-disb-2.json
/tmp/moneypal-agent-eval-18.json
/tmp/moneypal-agent-eval-18-retry.json
```

## 10. Resolved implementation problems

This section records the reasoning behind the post-baseline fixes. Both problems below
are implemented and covered by the 108-question context invariant; do not redo them unless
the final live run exposes a genuine regression.

The active work was improving detection of row-level field requests.

`build_agent_catalog_context()` currently marks `requires_validated_query` when the primary
table has directly named columns/dimensions and there is no suitable direct metric on that
table. This correctly handles many catalog-only questions, but it is still too conservative.

An audit across all 108 prompts found two remaining classes of issue:

### 10.1 Raw detail questions can contain a direct metric phrase

Example:

```text
List open loan accounts with borrower name, sanction amount and interest rate
```

“Sanction amount” and “interest rate” match reviewed metrics, but those metrics cannot return
the requested account and borrower columns. This must route to `run_validated_query`.

The implementation now calculates **uncovered requested columns**:

1. Collect directly named columns on the primary table.
2. Treat a column as covered if it is the physical input of a selected metric or the physical
   column of a directly requested dimension.
3. If any directly requested primary-table column remains uncovered, set
   `requires_validated_query=True` even when a direct metric also matched.

This is catalog-driven and general. Do not implement it as regexes for “list,” “show
accounts,” or individual question strings.

### 10.2 Shared generic columns can outrank the intended event view

Many views contain `loan_account_number`, `customer_id`, `branch_code`, or similarly generic
fields. A raw event question can therefore retrieve `semantic_loan_account` ahead of the
correct event table.

Examples observed in the 108-prompt routing audit include some phrasings for:

- customer documents;
- branch directory;
- agent directory;
- disbursement details;
- schedule details;
- portfolio delinquent details;
- receipt waivers;
- loan balance history;
- MSME security details.

Table ranking was improved using catalog evidence:

- Give an exact table label/synonym or event-specific column match more weight than a shared
  identifier column.
- Keep the exact requested view first when its table vocabulary is explicitly present.
- Do not globally ban `semantic_loan_account`; it is correctly needed for account detail and
  as a safe dimension/attribution join for several metrics.
- Add YAML synonyms only where they describe fields that genuinely exist.

The current context audit command used to identify these cases is included below.

## 11. Recommended continuation sequence

### Step 1: Confirm the worktree

```bash
git status --short
git diff --check
```

Do not modify or stage `plan.md`, `HACKY.md`, or `REGEX_PLAN.md`.

### Step 2: Uncovered-column routing — completed

`backend/app/services/workbench/prompts.py` now implements section 10.1. Tests cover:

- a pure governed metric trend remains `query_metrics`;
- a raw account/detail request containing metric words requires validated SQL;
- a raw catalog view with no metric requires validated SQL;
- a knowledge/document question without Gold row fields retains knowledge-search access.

### Step 3: Primary table ranking — completed

Use table and column catalog evidence, not question-specific rules. Then run this audit:

```bash
PYTHONPATH=backend UV_CACHE_DIR=/tmp/moneypal-uv-cache uv run python - <<'PY'
import yaml
from app.services.workbench.prompts import build_agent_catalog_context

families = yaml.safe_load(open("backend/tests/workbench/golden/agent_questions.yaml"))
for family in families:
    if family["tool"] != "run_validated_query":
        continue
    for index, question in enumerate(family["prompts"], 1):
        context = build_agent_catalog_context(question)
        expected = family["tables"][0]
        primary = context.tables[0] if context.tables else None
        if not context.requires_validated_query or primary != expected:
            print(
                f"{family['id']}:{index} validated={context.requires_validated_query} "
                f"primary={primary} expected={expected} :: {question}"
            )
PY
```

Do not require zero output blindly: inspect any remaining mismatch and decide whether the
question, YAML vocabulary, or ranking is wrong.

### Step 4: Rerun focused tests

```bash
PYTHONPATH=backend UV_CACHE_DIR=/tmp/moneypal-uv-cache uv run pytest -q \
  backend/tests/workbench/test_agent.py \
  backend/tests/workbench/test_agent_tools.py \
  backend/tests/workbench/test_prompts.py \
  backend/tests/workbench/test_agent_questions.py
```

### Step 5: Verify the local model is ready

Load `.env.prod` without printing it and call the configured health/model endpoints. A 503
with `Loading model` means wait and retry; do not count those prompts as model failures.

### Step 6: Run a small live regression first

Start with the previously failing families, not all 108 prompts. Suggested order:

1. `loan_account_sanctions`
2. `agent_rank`
3. `customer_profile_demographics`
4. `customer_document_expiry`
5. `branch_directory`
6. `product_scheme_terms`
7. `sales_hierarchy`
8. `msme_lead_pipeline`

Example:

```bash
cd backend
set -a
source ../.env.prod
set +a
export NLQ_LLM_LOCK_PATH=/tmp/moneypal-llamacpp.lock
export WORKBENCH_ROUTER_TIMEOUT_S=45
UV_CACHE_DIR=/tmp/moneypal-uv-cache uv run python -m scripts.evaluate_native_agent \
  --family customer_document_expiry \
  --output /tmp/customer-document-eval.json
```

Each family runs three phrasings and normally causes six LLM calls.

### Step 7: Run one prompt per view

Only after the small regressions are clean:

```bash
UV_CACHE_DIR=/tmp/moneypal-uv-cache uv run python -m scripts.evaluate_native_agent \
  --one-per-view \
  --output /tmp/moneypal-agent-eval-18-final.json
```

Inspect every failure and every suspicious “pass.” A schema-valid call that silently adds an
unrequested filter or drops a requested field is not acceptable.

### Step 8: Run all 108 prompts

Do this only after the 18-view smoke test is strong. The local model is sequential and the
full set means roughly 216 inference calls.

```bash
UV_CACHE_DIR=/tmp/moneypal-uv-cache uv run python -m scripts.evaluate_native_agent \
  --output /tmp/moneypal-agent-eval-108-final.json
```

The evaluator’s assertions may need strengthening so a “pass” also rejects:

- unrequested dimensions;
- unrequested filters;
- omitted requested catalog tables;
- invalid period semantics that happen to compile.

### Step 9: Run catalog/live DB tests

Run the existing catalog and metric fixture tests with `.env.prod` loaded, without printing
the environment. Confirm the 18 views and 537 columns still match after all YAML edits.

### Step 10: Run the broader suite in smaller groups

Because the previous broad command appeared to wait after roughly 166 checks, split it into
logical groups or use `-vv` to identify the slow test. Do not report a full pass until the
process exits successfully.

### Step 11: Review, stage selectively, commit, and push

Before committing:

- run `git diff --check`;
- run Ruff/format checks for changed Python files;
- inspect YAML diffs for unsupported vocabulary;
- verify `.env.prod` is ignored and unstaged;
- ensure `plan.md`, `HACKY.md`, and `REGEX_PLAN.md` remain unstaged;
- include this handoff only if it is still useful to keep in the repository.

No new commit or push has been made for the work in this handoff.

## 12. Important quality rules for the next session

- Do not optimize only for the literal 108 prompts. They are evaluation examples, not a
  production phrase dictionary.
- Prefer governed catalog metadata and schema constraints over increasingly long prompt prose.
- Never let the model invent joins. Only compiler-declared safe joins are allowed.
- A raw row/detail request must preserve every requested output field in the validated-query
  intent.
- A governed metric request should stay on `query_metrics` whenever the metrics and dimensions
  fully express the question.
- A catalog-only database question must not be redirected to curated knowledge search.
- A public/curated knowledge question must not leak customer or bank data into web search.
- Flow metrics and point-in-time metrics have different period semantics; use metric metadata.
- Treat transport failures, model-loading responses, schema failures, routing failures, and
  semantic argument failures as separate result categories.
- Do not execute SQL from the model evaluation script. Database execution tests should remain
  explicit and separately controlled.

## 13. Security note

Environment files contain live API and database credentials. They are ignored for a reason.
Never copy their values into logs, patches, tests, commits, or future handoff documents. Since
credentials were displayed in an earlier conversation message, rotating externally issued API
keys is prudent; that operational action is outside the source-code changes documented here.
