# Workbench Simplification TODO

This checklist implements plan.md. Complete phases in order unless a task explicitly says it
can run in parallel. Do not remove the legacy path or dependencies until rollout gates pass.

## Phase 0 — Baseline and safeguards

### Telemetry

- [ ] Define call purposes: route, db_plan, sql_generate, sql_repair, vector_compose,
  final_compose, suggestions, and compaction.
- [ ] Add call purpose to every LLM completion log.
- [ ] Record provider, model, prompt/catalog versions, prompt tokens, cached tokens,
  completion tokens, duration, retries, and finish reason.
- [ ] Aggregate model calls and tokens into each Workbench turn.
- [ ] Expose/export turn-level cost and latency data for evaluation.
- [ ] Distinguish planned, retry, and repair calls.

### Baseline evaluation

- [ ] Build fixtures for DB, macro, competitive, regulatory, knowledge, schema, web, and
  mixed-source requests.
- [ ] Include pins, structural follow-ups, deterministic lookups, clarifications, refusals,
  partial results, and dependency failures.
- [ ] Capture model calls by purpose for every fixture.
- [ ] Capture prompt, cached-prompt, and completion tokens.
- [ ] Capture first-event, first-card, final-answer, and total latency.
- [ ] Save the existing route-golden baseline.
- [ ] Save canonical NLQ accuracy/reconciliation results.
- [ ] Document deployed llama.cpp slot/cache configuration.

### Safety net

- [ ] Add WORKBENCH_ORCHESTRATOR_V2; keep legacy default initially.
- [ ] Add WORKBENCH_DETERMINISTIC_ROUTING; default false.
- [ ] Add WORKBENCH_COMMON_COMPOSER; default false.
- [ ] Add WORKBENCH_PERSONALIZE_SUGGESTIONS; default false.
- [ ] Add model-call-budget test helpers.
- [ ] Run and record existing Workbench tests.
- [ ] Run and record existing NLQ tests.
- [ ] Run and record frontend type-check/build.

### Phase 0 exit gate

- [ ] Baseline report is recorded.
- [ ] Every target path has a measured call count.
- [ ] Legacy/new selection is tested.
- [ ] Pre-existing failures are documented.

## Phase 1 — Remove optional critical-path calls

### Deterministic next steps

- [ ] Disable suggestions.personalize by default in the DB chart path.
- [ ] Return existing compiler-checked next steps unchanged.
- [ ] Retain personalization only behind its feature flag if needed.
- [ ] Test that suggestions remain valid without personalization.
- [ ] Test that disabled personalization makes no model call.

### Known-source bypasses

- [ ] Bypass model routing for an authorized pin.
- [ ] Bypass model routing for deterministic record lookup.
- [ ] Bypass model routing for structurally resolved DB follow-ups.
- [ ] Preserve exact names, account ids, periods, and measures passed to DB.
- [ ] Add zero-router-call assertions for these paths.

### Phase 1 exit gate

- [ ] DB chart/drill UX remains functional.
- [ ] Deterministic call budgets pass.
- [ ] Security, role, PII, and DB validation tests pass.

## Phase 2 — Replace LangGraph with plain async orchestration

### Orchestrator

- [ ] Extract ordinary async select, dispatch, and answer functions from graph.py.
- [ ] Preserve the run_workbench signature and import path.
- [ ] Preserve bounded transcript loading and turn creation.
- [ ] Preserve asyncio.gather parallel execution.
- [ ] Preserve source_start before each result.
- [ ] Preserve per-source exception isolation.
- [ ] Preserve partial-answer and limitation aggregation.
- [ ] Preserve cancellation behavior.
- [ ] Preserve interrupted-turn persistence.
- [ ] Preserve post-turn compaction scheduling.
- [ ] Emit exactly one queue sentinel.
- [ ] Persist exactly one definitive outcome.

### SSE contract

- [ ] Preserve conversation.
- [ ] Preserve stage.
- [ ] Preserve route.
- [ ] Preserve source_start.
- [ ] Preserve source_card.
- [ ] Preserve answer.
- [ ] Preserve refusal.
- [ ] Preserve error and retryable semantics.
- [ ] Preserve final done.
- [ ] Add event schema and ordering tests.

### Dependencies

- [ ] Remove StateGraph, START, and END imports.
- [ ] Confirm no runtime import of langgraph remains.
- [ ] Confirm whether langchain-core has another consumer.
- [ ] Remove langgraph from pyproject.toml.
- [ ] Regenerate uv.lock through the approved package workflow.
- [ ] Remove unused graph packages from backend/Dockerfile.
- [ ] Build the backend image.

### Tests

- [ ] Convert graph tests into framework-neutral orchestrator tests.
- [ ] Test one-source success.
- [ ] Test multi-source success.
- [ ] Test one source failing while another succeeds.
- [ ] Test all sources unavailable.
- [ ] Test clarification and refusal.
- [ ] Test context overflow.
- [ ] Test cancellation at each stage.
- [ ] Test history-write failure degradation.
- [ ] Test compaction remains off the response path.

### Phase 2 exit gate

- [ ] Workbench backend tests pass.
- [ ] Frontend consumes the unchanged stream.
- [ ] Legacy/new route and answer parity pass.
- [ ] No unused graph dependency remains.
- [ ] Model-call counts do not increase.

## Phase 3 — Deterministic-first source selection

### Decision contract

- [ ] Define sources, focused intents, confidence, reason, fallback-used, and policy-version
  fields.
- [ ] Ensure every selected source is role-visible.
- [ ] Ensure pins only narrow access.
- [ ] Define precedence for overlapping cues.
- [ ] Record why every source was selected.

### Deterministic routes

- [ ] Route schema/relationship requests to schema.
- [ ] Route governed record lookups to DB.
- [ ] Route catalog-matched value questions to DB.
- [ ] Route explicit public searches to web after sanitization.
- [ ] Route current public-data requests to web when freshness requires it.
- [ ] Route macro questions to macro.
- [ ] Route peer/competitor questions to competitive.
- [ ] Route regulatory-policy questions to regulatory.
- [ ] Route stable definitions to knowledge when no bank value is requested.
- [ ] Select DB plus an external source for explicit comparisons.
- [ ] Produce safe focused subquestions for hybrid requests.
- [ ] Clarify rather than force a low-confidence selection.

### Ambiguity fallback

- [ ] Use constrained LLM routing only for ambiguous cases.
- [ ] Validate fallback output against role and registry policy.
- [ ] Override false DB-coverage refusals with catalog evidence.
- [ ] Record fallback frequency and ambiguity class.
- [ ] Add failures to evaluation fixtures, not answer lookup rules.

### Tests/evaluation

- [ ] Cover typos and paraphrases for each source.
- [ ] Cover overlapping macro/regulatory/competitive cues.
- [ ] Cover destructive and out-of-scope requests.
- [ ] Cover roles without DB or web access.
- [ ] Cover unknown and unauthorized pins.
- [ ] Reach at least 95% source-set accuracy.
- [ ] Demonstrate at least 80% router-model avoidance.

### Phase 3 exit gate

- [ ] Route threshold passes.
- [ ] Permission/destructive suites pass 100%.
- [ ] Fallback is safe and observable.
- [ ] New selection can be disabled independently.

## Phase 4 — Typed results and retrieval-only vector tools

### Common ToolResult

- [ ] Introduce a typed result envelope.
- [ ] Separate renderable payload from model evidence.
- [ ] Add complete, limitation, sensitive, and lineage fields.
- [ ] Define document, page, URL, date, score, and excerpt evidence fields.
- [ ] Enforce evidence count and token bounds.
- [ ] Add serialization/backward-compatibility tests.

### Database tool

- [ ] Wrap ask_once/direct/MCP behavior behind ToolResult.
- [ ] Keep exact-question handling.
- [ ] Require role and PII context.
- [ ] Keep compiler and validator mandatory.
- [ ] Keep read-only transaction, timeout, and row limits.
- [ ] Keep audit and lineage.
- [ ] Exclude unauthorized/raw rows from composer evidence.
- [ ] Test direct and MCP modes.

### Macro

- [ ] Split Qdrant retrieval from macro prose generation.
- [ ] Return passages and source metadata.
- [ ] Preserve periodic-statistic date semantics.
- [ ] Preserve empty/unavailable-store behavior.

### Competitive

- [ ] Split institution selection/retrieval from prose generation.
- [ ] Preserve per-institution failure isolation.
- [ ] Preserve registry-metadata degraded fallback.
- [ ] Preserve page-citation protection.

### Regulatory and knowledge

- [ ] Inventory deterministic versus document-based regulatory paths.
- [ ] Convert document-based output to common evidence.
- [ ] Preserve complete registered regulatory cards.
- [ ] Return governed catalog definitions as knowledge evidence.

### Web

- [ ] Reject private external queries before network access.
- [ ] Return sanitized query and citable evidence without source prose.
- [ ] Mark web content as untrusted.
- [ ] Preserve rate-limit and dependency-failure behavior.

### Phase 4 exit gate

- [ ] All handlers return the typed envelope.
- [ ] Vector sources do not pre-synthesize prose.
- [ ] Citation, limitation, and degraded-mode tests pass.
- [ ] Existing cards render from payload unchanged.

## Phase 5 — Common answer composer

### Prompt/output

- [ ] Define a versioned stable composer prompt.
- [ ] Define status, text, sources, citations, unavailable sources, and limitations.
- [ ] Keep fixed security/citation rules in the stable prefix.
- [ ] Put transcript and evidence after the prefix.
- [ ] Delimit retrieved passages as untrusted evidence.
- [ ] Prohibit unsupported inference and numeric alteration.
- [ ] Require explicit missing/conflicting evidence.

### Composition policy

- [ ] Return complete DB headlines without composition.
- [ ] Return deterministic clarification/refusal without composition.
- [ ] Return complete schema cards without composition.
- [ ] Compose one vector source with one call.
- [ ] Compose multiple vector sources with one call.
- [ ] Compose DB plus vector evidence with one call.
- [ ] Add an extractive fallback.
- [ ] Include every unavailable source and limitation in partial status.
- [ ] Deduplicate citations deterministically.
- [ ] Emit/persist one final answer envelope.

### Model-call budget tests

- [ ] Structural DB follow-up: zero calls.
- [ ] Deterministic DB lookup: zero calls.
- [ ] Governed DB planning: one call.
- [ ] Normal text-to-SQL: no more than two calls.
- [ ] SQL repair: no more than one additional call.
- [ ] Single vector source: one call.
- [ ] Multiple vector sources: one call.
- [ ] DB plus vector: DB planning if needed plus one composer.
- [ ] Schema and permission refusal: zero calls.
- [ ] No per-source plus final double synthesis.

### Grounding

- [ ] Every generated figure exists exactly in tool evidence.
- [ ] Citations support associated claims.
- [ ] Missing evidence produces partial/clarify/refuse appropriately.
- [ ] Conflicting evidence is surfaced.
- [ ] Sensitive DB facts never enter a public-provider request.

### Phase 5 exit gate

- [ ] Call budgets pass.
- [ ] One definitive answer is emitted.
- [ ] Numerical reconciliation passes.
- [ ] Citation/partial-answer quality meets or exceeds baseline.

## Phase 6 — Cache and history hardening

### Stable prefix

- [ ] Sort/serialize fixed source and tool descriptions deterministically.
- [ ] Version the common prefix.
- [ ] Remove dynamic timestamps and ids from the prefix.
- [ ] Put current evidence/question after cacheable content.
- [ ] Keep provider/model affinity when policy permits.
- [ ] Test identical prefix bytes across consecutive turns.

### Cache telemetry/load

- [ ] Record prefix version and cached tokens.
- [ ] Compare cached-token ratio to baseline.
- [ ] Test one active conversation.
- [ ] Test interleaved conversations.
- [ ] Test production-like concurrency.
- [ ] Tune llama.cpp cache reuse/slots only from measurements.
- [ ] Confirm Gold planner-prefix warmup still works.

### Canonical history

- [ ] Confirm Workbench is the only prose transcript sent to Workbench calls.
- [ ] Replay only the definitive assistant answer.
- [ ] Keep cards, SQL, lineage, and tool logs out of model history.
- [ ] Preserve exact structured session facts through compaction.
- [ ] Preserve pins and active bindings.
- [ ] Keep nlq_conversations structured-only.
- [ ] Document why it is not a second chat transcript.
- [ ] Re-tune transcript budget from measured prompts.

### Compaction

- [ ] Trigger by token budget, not turn count alone.
- [ ] Keep compaction outside response latency.
- [ ] Avoid repeatedly summarizing unchanged turns.
- [ ] Test newest-turn overflow and recovery.
- [ ] Test summary-failure fallback.
- [ ] Test long DB, vector, and mixed conversations.

### Phase 6 exit gate

- [ ] Cached-token ratio improves without correctness loss.
- [ ] Long-history/compaction tests pass.
- [ ] Cross-user isolation passes.
- [ ] Prompts contain no unauthorized data.

## Phase 7 — Rollout and cleanup

### Verification

- [ ] Run backend unit/integration tests.
- [ ] Run canonical NLQ and security suites.
- [ ] Run Workbench route and answer evaluation.
- [ ] Run frontend type-check and production build.
- [ ] Build/smoke-test backend container.
- [ ] Test direct PostgreSQL.
- [ ] Test PostgreSQL MCP.
- [ ] Test Qdrant unavailable.
- [ ] Test local LLM unavailable.
- [ ] Test optional public-only Groq mode.

### Rollout

- [ ] Shadow legacy/new paths where feasible.
- [ ] Review route, answer, citation, and numeric differences.
- [ ] Enable internal canary.
- [ ] Monitor calls, tokens, cache, latency, errors, partials, and refusals.
- [ ] Expand by percentage after canary gate.
- [ ] Complete observation window.
- [ ] Exercise rollback before full rollout.

### Cleanup

- [ ] Make the new orchestrator default.
- [ ] Remove the legacy graph path.
- [ ] Remove obsolete routing prompts/schemas after fallback retirement.
- [ ] Remove per-source synthesis prompts.
- [ ] Remove unused personalization if product metrics do not justify it.
- [ ] Remove temporary adapters.
- [ ] Remove graph dependencies and regenerate lockfiles.
- [ ] Update backend README and architecture docs.
- [ ] Update deployment/rollback runbooks.
- [ ] Archive baseline/final comparison reports.

### Final acceptance

- [ ] Safety, PII, role, and read-only tests pass 100%.
- [ ] Canonical NLQ numeric accuracy does not regress.
- [ ] Source-set accuracy is at least 95%.
- [ ] Median call count falls at least 50%.
- [ ] Non-cached prompt tokens fall at least 40%.
- [ ] At least 80% of selections avoid the model router.
- [ ] No turn uses more than one user-facing composition call.
- [ ] Single-source p95 latency does not regress.
- [ ] First-card regression is no greater than 10%.
- [ ] SSE/history compatibility passes.
- [ ] Rollback is verified.
- [ ] Legacy orchestration is deleted.

## Phase 8 — Optional native tool-calling agent

Do not begin until Phases 0–7 are stable and measured.

### Feasibility

- [ ] Confirm deployed llama.cpp/model tool-call support.
- [ ] Benchmark native tool calls against constrained JSON actions.
- [ ] Measure calls, tokens, cache, latency, and tool accuracy.
- [ ] Decide whether it materially improves the Phase 7 system.

### Client/protocol

- [ ] Support assistant tool calls and tool-result message types.
- [ ] Send stable tool definitions.
- [ ] Parse and validate every tool call.
- [ ] Add tool-choice controls where supported.
- [ ] Enforce maximum steps.
- [ ] Detect duplicate/repeated calls.
- [ ] Handle malformed calls, cancellation, timeout, and partial results.
- [ ] Keep authorization and DB validation outside the model.

### Phase 8 gate

- [ ] Correctness meets or exceeds Phase 7.
- [ ] Median calls/non-cached tokens do not increase.
- [ ] Local-provider concurrency/reliability passes.
- [ ] Security and injection suites pass.
- [ ] Rollback to application-controlled orchestration remains available.

## Deferred conversation-state consolidation

- [ ] Design versioned fields for active QuerySpec, sticky filters, and NLQ entities.
- [ ] Define migration behavior for active nlq_conversations rows.
- [ ] Preserve or explicitly replace 30-minute structured-state expiry.
- [ ] Update or deprecate the legacy /nlq path.
- [ ] Add backward-compatible record loaders.
- [ ] Add migration and rollback scripts.
- [ ] Verify old Workbench history remains readable.
- [ ] Remove public.nlq_conversations only after every reader/writer migrates.
