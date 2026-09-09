# Native Tool-Calling Workbench Plan

Updated: 2026-09-09
Branch: `fix/regex-removal`

## 1. Decision

The Workbench has one execution architecture: provider-native tool calling.

The LLM decides which authorized tool to call, supplies its arguments, sees typed tool results
and errors, decides whether another call is needed, and writes the final answer. Application
code enforces permissions and safety but does not infer intent, select sources from question
keywords, rewrite the question, repair semantic arguments, or substitute a legacy planner.

Consequences:

- The native agent is always active. There are no `off`, `shadow`, or `canary` modes.
- There is no legacy Workbench routing or fallback path.
- There are no hidden question-pattern shortcuts before text-to-SQL generation.
- Sources are selected only by validated native tool calls.
- Native failures produce typed observations, explicit refusals, or user-visible errors; they
  never start a second orchestration pipeline.
- Evaluation uses the single model selected for deployment. Cross-model benchmarking is not a
  release requirement.

## 2. Deterministic safety boundaries

LLM control does not mean LLM authorization. These controls remain outside the model:

- role and deployment tool visibility;
- explicit external-source consent and pinned-source narrowing;
- PII and outbound-data screening;
- strict tool argument validation;
- governed catalog table, column, metric, dimension, and join policy;
- SQL AST validation, parameter binding, and read-only transactions;
- row, observation, round, tool-call, context, and deadline limits;
- unknown-tool and unavailable-source rejection.

No write-capable database tool is exposed. Destructive SQL is rejected by the validator rather
than classified from question wording.

## 3. Native tools

The model may choose from the tools authorized for the current request:

- `query_metrics`
- `lookup_records`
- `run_validated_query`
- `inspect_loan_catalog`
- `run_analysis`
- `create_worklist`
- `generate_briefing`
- `search_curated_knowledge`
- `search_public_web`
- `finish_without_data`

Reviewed presets remain explicit tools because the model deliberately selects them. They are
not hidden shortcuts. Their executors remain deterministic and governed.

## 4. Completed foundation — Phases A to E

Phases A to E are complete and are not reopened by this plan.

### Phase A — Safety and bounded replay

- Durable tool results remain complete while model observations are bounded.
- SQL prompts and provider reasoning are excluded from replay by default.
- Context overflow becomes a persisted, user-visible SSE error.
- Provider locking is portable and user-facing tool errors are sanitized.

### Phase B — One agent loop

- One `TurnBudget` accounts for every model request and attempted tool call.
- Recoverable failures return to the model as typed tool observations.
- The final permitted request is reserved for synthesis when evidence exists.
- Native tool schemas are not narrowed from lexical interpretation of the question.

### Phase C — Ordered history

- Version 7 stores ordered execution events and nested text-to-SQL attempts.
- Native replay and session-state extraction read the event stream.
- Compaction measures native replay and does not delete durable events.
- A migration utility exists for older conversation records.

### Phase D — SQL validation

- Column resolution is scope-aware across subqueries, CTEs, aliases, and UNION branches.
- Generated SQL remains governed, read-only, and validated before execution.

### Phase E — Claim grounding

- Source and derived facts form a machine-readable ledger.
- Numeric claims are checked, repaired once, then unsupported statements are removed with a
  visible limitation.
- Verified facts are returned separately from qualitative prose.

## 5. Phase F — Native-only simplification

### F1. Make the agent the only entry point

- Change the Workbench entry point to invoke `agent.run(state)` directly.
- Remove `assigned_mode`, mode hashing, shadow selection, and percentage assignment.
- Remove `WORKBENCH_AGENT_MODE` and `WORKBENCH_AGENT_CANARY_PERCENT` from configuration and
  environment examples.
- Replace rollout-mode startup telemetry with `workbench_execution=native_only`.

### F2. Remove legacy orchestration and fallback

- Delete `_run_legacy` and the legacy branch from `workbench/orchestrator.py`; delete the
  module if it becomes an unnecessary wrapper.
- Remove native-to-legacy exception fallback, counters, route events, and history metadata.
- Remove frontend handling that clears native cards when a legacy fallback begins.
- Make terminal native failures explicit: recoverable failures go back to the model; exhausted
  or unavailable execution emits one typed user-visible outcome.
- Remove legacy `select_sources` and `dispatch_sources` functions after confirming no direct
  Workbench endpoint depends on them.

### F3. Remove the behavioral Workbench router

- Remove `workbench/router.py` and its prompt/evaluator fixtures.
- Remove keyword and regex source selection for database, schema, knowledge, macro,
  competitive, regulatory, and web sources.
- Remove catalog-match routing overrides, ambiguity routing, `_db_subquestion`, and structural
  follow-up rewriting.
- Move the neutral state required by answer composition out of `RouteDecision` into a
  non-routing `ExecutionDecision` contract.
- Build execution metadata from validated tool calls: invoked sources, tool names, effective
  authorized sources, and limitations.
- Preserve the `route` SSE shape only as a compatibility event emitted after model tool
  selection; it reports actual calls and performs no routing.

### F4. Keep policy enforcement without intent routing

- Build visible native tools from role, deployment availability, consent, and pins before
  every model request.
- Revalidate every returned tool call against the same policy immediately before execution.
- Keep outbound PII checks at the tool boundary.
- Let the model clarify or refuse requests it cannot satisfy with visible tools.
- Rely on capability absence and SQL validation—not destructive-word regexes—to prevent writes.
- Verify direct-tool and pinned-source endpoints cannot broaden the effective tool set.

### F5. Remove hidden text-to-SQL shortcuts

- Remove `allow_reviewed_shortcuts` from `text_to_sql.generate` and all callers.
- Delete automatic pre-generation dispatch for interest-rate distributions, agent/borrower
  collections, agent directory queries, named-borrower disbursement, and named-borrower
  principal collection.
- Delete the question-detection regexes and helpers used only by those shortcuts.
- Route every free-form `run_validated_query` request through model SQL generation followed by
  catalog, AST, PII, and read-only validation.
- Keep explicit native preset tools and deterministic metric compilers; they run only when the
  model selects them.
- Remove shortcut-specific lineage labels and tests that assert question-pattern selection.

### F6. Remove obsolete dependencies and compatibility code

- Remove unused router prompts, schemas, evaluation modules, configuration, imports, fixtures,
  and fallback-only history fields.
- Keep source handlers called by native tool executors; delete only unreachable legacy
  orchestration adapters.
- Do not remove unrelated FastAPI `APIRouter` modules or domain APIs.
- Update architecture comments and environment documentation to describe one execution path.

### F7. Final validation after implementation

Testing happens after F1–F6 are complete.

- Run formatting/lint checks and `git diff --check`.
- Run the complete backend suite and frontend type/build checks.
- Run the single-turn and multi-turn native corpus against the one deployed model; correct
  fixtures only where they disagree with the intended native transcript.
- Assert exact native tool names and structured arguments, not regex-scored prose.
- Verify filter changes/removals, period changes, aggregate-to-record drills, spelling errors,
  invalid arguments, unknown tools, rejected SQL repair, budget exhaustion, and large bounded
  observations.
- Verify every Workbench request enters the native agent and no router, shortcut, shadow,
  canary, or legacy fallback path can execute.
- Record model id, prompt/catalog versions, commit, pass counts, latency, and failure categories
  in the final report.

### Phase F exit gate

- Every Workbench request enters the native agent exactly once.
- No imports or calls remain for `workbench.router`, `select_sources`, `dispatch_sources`,
  `_run_legacy`, `assigned_mode`, shadow, canary, or legacy fallback.
- No question-specific shortcut runs before text-to-SQL generation.
- Application code does not rewrite the user question or model-generated semantic arguments.
- Sources shown in history and SSE are derived from validated native tool calls.
- Authorization, consent, PII, SQL safety, and execution limits remain deterministic.
- The full suite and native conversation corpus pass against the deployed model.

## 6. Phase G — Documentation and handoff

- Keep `plan.md` and `TODO.md` aligned with this native-only decision.
- Rewrite `context.md` after Phase F to describe the resulting code, not the superseded
  rollout architecture.
- Remove claims that shadow, canary, fallback, router tuning, shortcut retirement, or
  cross-model comparison remain future work.
- Record the branch, final commit, deployed model id, prompt/catalog versions, commands run,
  pass counts, and interrupted commands.
- Record production migration status for version-7 history and the date legacy
  `agent_exchanges` compatibility writes can be disabled.

## 7. Completion criteria

The work is complete when:

- provider-native tool calling is the sole Workbench execution protocol;
- the LLM controls tool selection, arguments, correction, clarification, refusal, and final
  answer composition;
- no behavioral router, legacy fallback, or hidden question-pattern SQL shortcut remains;
- application code provides authorization and safety boundaries without semantic rewriting;
- observations are bounded, durable events complete, and history replay ordered;
- SQL validation remains scope-aware, alias-aware, governed, and read-only;
- numeric claims remain traceable to verified source or calculated facts;
- the full suite and native corpus pass against the deployed model; and
- the final handoff accurately records the deployed native-only system.

## 8. Non-goals

- Cross-model Ling/Qwen benchmarking.
- Shadow or percentage-canary execution.
- Retaining the legacy Workbench planner as fallback.
- Unrestricted autonomous web browsing.
- Allowing the model to grant itself tools or bypass consent and role policy.
- Replacing the governed catalog with unrestricted SQL generation.
- Removing parsing, normalization, security, or validation regexes that do not select behavior
  from the user's question.
- Consolidating `nlq_conversations` and `workbench_conversations` in this change.
