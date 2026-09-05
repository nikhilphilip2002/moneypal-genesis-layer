# Workbench Source-Access and Simplification TODO

This checklist implements plan.md. Complete phases in order unless a task explicitly says it
can run in parallel. The retired runtime remains recoverable through the prior deployment
image; it is not retained as a second path in the new image.

Status as of 2026-09-04: the required repository implementation is complete. Unchecked Phase
0/6/7 items require the deployed PostgreSQL/Qdrant/model/provider environment, a real canary
observation window, or the metrics-based decision on removing the already-disabled
personalization hook. Phase 8 and conversation-state consolidation are explicitly
optional/deferred and have not been started.

## Phase 0 — Baseline and safeguards

### Telemetry

- [x] Define call purposes: route, db_plan, sql_generate, sql_repair, vector_compose,
  final_compose, suggestions, and compaction.
- [x] Define separate prompt builders for router fallback, DB planner, and composer.
- [x] Assign every instruction to one owner: application policy, tool/compiler, evidence
  envelope, system prompt, or structured-output schema.
- [x] Add a test that rejects duplicated structured-schema prose in model prompts.
- [x] Serialize stable prefixes deterministically.
- [x] Version and hash every stable prefix.
- [x] Add byte-stability tests before changing orchestration.
- [x] Add call purpose to every LLM completion log.
- [x] Record provider, model, prompt/catalog versions, prompt tokens, cached tokens,
  completion tokens, duration, retries, and finish reason.
- [x] Record cache-write tokens and computed uncached tokens where supported.
- [x] Record the prefix version/hash on every model call.
- [x] Aggregate model calls and tokens into each Workbench turn.
- [x] Expose/export turn-level cost and latency data for evaluation.
- [x] Distinguish planned, retry, and repair calls.

### Baseline evaluation

- [x] Build fixtures for DB, macro, competitive, regulatory, knowledge, schema, web, and
  mixed-source requests.
- [x] Run every external and mixed fixture with external sources both disabled and enabled.
- [x] Include pins, structural follow-ups, deterministic lookups, clarifications, refusals,
  partial results, and dependency failures.
- [x] Capture model calls by purpose for every fixture.
- [ ] Capture prompt, cached-prompt, and completion tokens.
- [ ] Capture cache-write and uncached input tokens where available.
- [ ] Capture p50/p95 tokens for router, planner, composer, history, and evidence.
- [x] Capture first-event, first-card, final-answer, and total latency.
- [x] Capture attempted/completed Qdrant and web operations by consent state.
- [x] Save the existing route-golden baseline.
- [x] Save canonical NLQ accuracy/reconciliation results.
- [ ] Document deployed llama.cpp slot/cache configuration.
- [ ] Ratify or revise the provisional Section 10 token budgets from baseline evidence.

### Safety net

- [x] Add WORKBENCH_ORCHESTRATOR_V2; keep legacy default initially.
- [x] Add WORKBENCH_DETERMINISTIC_ROUTING; default false.
- [x] Add WORKBENCH_COMMON_COMPOSER; default false.
- [x] Add WORKBENCH_PERSONALIZE_SUGGESTIONS; default false.
- [x] Add WORKBENCH_EXTERNAL_CONNECTORS_ENABLED as a deployment kill switch; default it
  independently from per-conversation user consent.
- [x] Add model-call-budget test helpers.
- [x] Run and record existing Workbench tests.
- [x] Run and record existing NLQ tests.
- [x] Run and record frontend type-check/build.

### Phase 0 exit gate

- [x] Baseline report is recorded.
- [ ] Every target path has a measured call count.
- [ ] Every purpose has a p50/p95 uncached-token baseline and prefix hash.
- [ ] Supported providers demonstrate reuse for repeated byte-identical prefixes.
- [x] Legacy/new selection is tested.
- [x] Pre-existing failures are documented.

## Phase 1 — Data-source consent and optional critical-path calls

### Source classification and policy

- [x] Add source groups: internal_data, internal_metadata, local_knowledge,
  external_indexed, and live_external.
- [x] Classify db as internal_data.
- [x] Classify schema as authorized internal_metadata.
- [x] Classify knowledge as local_knowledge with no connector access.
- [x] Classify macro, competitive, and regulatory as external_indexed.
- [x] Classify web as live_external.
- [x] Define one immutable SourceAccessPolicy per submitted request.
- [x] Compute effective sources as consent ∩ role ∩ deployment availability.
- [x] Ensure user consent cannot grant a role or deployment capability.
- [x] Ensure locally hosted Qdrant still requires external-source consent.

### API and persistence

- [x] Add optional external_sources_enabled to AskRequest with default false.
- [x] Add source group and availability metadata to GET /workbench/sources.
- [x] Add the submitted consent snapshot and effective sources to each turn.
- [x] Increment the JSON history record version additively.
- [x] Load old history with external_sources_enabled=false.
- [x] Store the latest explicit conversation toggle state.
- [x] Restore that state when reopening a conversation.
- [x] Keep an in-flight request's policy immutable if the UI changes meanwhile.
- [x] Audit denials without copying sensitive question text into general logs.

### Backend enforcement

- [x] Filter source candidates before deterministic or model routing.
- [x] Validate selected sources again before dispatch.
- [x] Reject an external pinned source while consent is disabled.
- [x] Gate POST /workbench/tool/{id} by the same policy.
- [x] Inventory and gate Workbench workspace actions that access Qdrant or web.
- [x] Check consent inside Qdrant handlers as defense in depth.
- [x] Check consent immediately before a web network request.
- [x] Return a deterministic consent-required response for an external-only question.
- [x] Return the DB-supported portion plus a disabled-external limitation for mixed questions.
- [x] Verify disabled external requests make no router-model call when the policy outcome is
  already deterministic.

### Frontend toggle

- [x] Add conversation-scoped externalSourcesEnabled state; initialize false.
- [x] Add one accessible “Use external sources” toggle to the composer.
- [x] Explain that it enables macro, competitive, regulatory, and web together.
- [x] Avoid local/cloud wording because Qdrant may be locally hosted.
- [x] Send the boolean with every chat request.
- [x] Send/resolve it for direct tools and workspace actions.
- [x] Display the active data-source mode beside the composer.
- [x] Restore the saved state when a conversation is opened.
- [x] Reset it to false for a new conversation.
- [x] Disable external source pins while off.
- [x] Clear an active external pin when the toggle turns off.
- [x] Keep Direct/MCP selection independent.
- [x] Keep local/Groq model mode independent.

### Consent tests

- [x] Omitted request field defaults to false.
- [x] False allows DB and authorized explicit schema access.
- [x] False allows only connector-free governed knowledge outside DB.
- [x] False blocks macro Qdrant.
- [x] False blocks competitive Qdrant.
- [x] False blocks regulatory Qdrant.
- [x] False blocks web search.
- [x] True enables only role/deployment-permitted external sources.
- [x] DB remains eligible when external sources are enabled.
- [x] Forged external pins are rejected while off.
- [x] Direct tool calls cannot bypass consent.
- [x] Workspace actions cannot bypass consent.
- [x] Turning off affects subsequent turns immediately.
- [x] Reopened old conversations default off.
- [x] Reopened new conversations visibly restore the saved value.
- [x] Frontend toggle has label, keyboard, and screen-reader coverage.

### Deterministic next steps

- [x] Disable suggestions.personalize by default in the DB chart path.
- [x] Return existing compiler-checked next steps unchanged.
- [x] Retain personalization only behind its feature flag if needed.
- [x] Test that suggestions remain valid without personalization.
- [x] Test that disabled personalization makes no model call.

### Known-source bypasses

- [x] Bypass model routing for an authorized pin.
- [x] Bypass model routing for deterministic record lookup.
- [x] Bypass model routing for structurally resolved DB follow-ups.
- [x] Preserve exact names, account ids, periods, and measures passed to DB.
- [x] Add zero-router-call assertions for these paths.

### Phase 1 exit gate

- [x] DB chart/drill UX remains functional in local contract/unit tests.
- [x] Toggle-off paths cannot reach Qdrant or web through any Workbench entry point.
- [x] Toggle-on paths can select all role-permitted available external sources.
- [x] Old callers and old histories safely default off.
- [x] External consent, Direct/MCP, pins, and local/Groq remain independent.
- [x] Deterministic call budgets pass.
- [x] Security, role, PII, and DB validation tests pass in the local suites.

## Phase 2 — Replace LangGraph with plain async orchestration

### Orchestrator

- [x] Extract ordinary async select, dispatch, and answer functions from graph.py.
- [x] Preserve the run_workbench signature and import path.
- [x] Preserve bounded transcript loading and turn creation.
- [x] Carry the immutable SourceAccessPolicy snapshot through the complete turn.
- [x] Preserve asyncio.gather parallel execution.
- [x] Preserve source_start before each result.
- [x] Preserve per-source exception isolation.
- [x] Preserve partial-answer and limitation aggregation.
- [x] Preserve cancellation behavior.
- [x] Preserve interrupted-turn persistence.
- [x] Preserve post-turn compaction scheduling.
- [x] Emit exactly one queue sentinel.
- [x] Persist exactly one definitive outcome.

### SSE contract

- [x] Preserve conversation.
- [x] Preserve stage.
- [x] Preserve route.
- [x] Preserve source_start.
- [x] Preserve source_card.
- [x] Preserve answer.
- [x] Preserve refusal.
- [x] Preserve error and retryable semantics.
- [x] Preserve final done.
- [x] Add event schema and ordering tests.

### Dependencies

- [x] Remove StateGraph, START, and END imports.
- [x] Confirm no runtime import of langgraph remains.
- [x] Confirm whether langchain-core has another consumer.
- [x] Remove langgraph from pyproject.toml.
- [x] Regenerate uv.lock through the approved package workflow.
- [x] Remove unused graph packages from backend/Dockerfile.
- [ ] Build the backend image.

### Tests

- [x] Convert graph tests into framework-neutral orchestrator tests.
- [x] Test one-source success.
- [x] Test multi-source success.
- [x] Test one source failing while another succeeds.
- [x] Test all sources unavailable.
- [x] Test clarification and refusal.
- [x] Test context overflow.
- [x] Test cancellation before orchestration and during dispatch.
- [x] Test history-write failure degradation.
- [x] Test that orchestration refactoring cannot dispatch outside effective sources.
- [x] Test compaction remains off the response path.

### Phase 2 exit gate

- [x] Workbench backend tests pass (242 passed, 1 live-model test skipped).
- [x] Frontend consumes the unchanged stream.
- [x] Event, route, card, answer, and history compatibility pass.
- [x] No unused graph dependency remains.
- [x] Model-call counts do not increase.

## Phase 3 — Deterministic-first source selection

### Decision contract

- [x] Define sources, focused intents, confidence, reason, fallback-used, and policy-version
  fields.
- [x] Ensure every selected source is role-visible.
- [x] Ensure pins only narrow access.
- [x] Define precedence for overlapping cues.
- [x] Record why every source was selected.
- [x] Include the effective allowed-source set in decision telemetry.

### Deterministic routes

- [x] Short-circuit external-only requests while the toggle is off.
- [x] Do not call the ambiguity router for a deterministic consent-required response.
- [x] Return internal results plus a structured disabled-source limitation for mixed requests.
- [x] Route schema/relationship requests to schema.
- [x] Route governed record lookups to DB.
- [x] Route catalog-matched value questions to DB.
- [x] Route explicit public searches to web after sanitization.
- [x] Route current public-data requests to web when freshness requires it.
- [x] Route macro questions to macro.
- [x] Route peer/competitor questions to competitive.
- [x] Route regulatory-policy questions to regulatory.
- [x] Route stable definitions to knowledge when no bank value is requested.
- [x] Select DB plus an external source for explicit comparisons.
- [x] Produce safe focused subquestions for hybrid requests.
- [x] Clarify rather than force a low-confidence selection.

### Ambiguity fallback

- [x] Use constrained LLM routing only for ambiguous cases.
- [x] Validate fallback output against role and registry policy.
- [x] Constrain fallback schema to the effective allowed-source set.
- [x] Override false DB-coverage refusals with catalog evidence.
- [x] Record fallback frequency and ambiguity class.
- [x] Add failures to evaluation fixtures, not answer lookup rules.

### Tests/evaluation

- [x] Cover typos and paraphrases across governed sources.
- [x] Cover overlapping macro/regulatory/competitive cues.
- [x] Cover destructive and out-of-scope requests.
- [x] Cover role-restricted sources and unavailable web access.
- [x] Cover unknown and unauthorized pins.
- [x] Cover external pins with consent omitted, false, and true.
- [x] Assert the router never sees or returns a disabled external source.
- [x] Reach at least 95% source-set accuracy on the deterministic fixture corpus.
- [x] Demonstrate at least 80% router-model avoidance on the deterministic fixture corpus.

### Phase 3 exit gate

- [x] Route threshold passes on the deterministic fixture corpus.
- [x] Permission/destructive suites pass 100% locally.
- [x] Fallback is safe and observable.
- [x] New selection can be disabled independently.

## Phase 4 — Typed results and retrieval-only vector tools

### Common ToolResult

- [x] Introduce a typed result envelope.
- [x] Separate renderable payload from model evidence.
- [x] Add complete, limitation, sensitive, and lineage fields.
- [x] Define document, page, URL, date, score, and excerpt evidence fields.
- [x] Enforce evidence count and token bounds.
- [x] Add serialization/backward-compatibility tests.
- [x] Require every successful tool result to declare a registered source group.

### Database tool

- [x] Wrap ask_once/direct/MCP behavior behind ToolResult.
- [x] Keep exact-question handling.
- [x] Require role and PII context.
- [x] Keep compiler and validator mandatory.
- [x] Keep read-only transaction, timeout, and row limits.
- [x] Keep audit and lineage.
- [x] Exclude unauthorized/raw rows from composer evidence.
- [x] Test direct and MCP modes with local fakes/contracts.

### Macro

- [x] Require external-source consent before Qdrant access.
- [x] Split Qdrant retrieval from macro prose generation.
- [x] Return passages and source metadata.
- [x] Preserve periodic-statistic date semantics.
- [x] Preserve empty/unavailable-store behavior.

### Competitive

- [x] Require external-source consent before Qdrant access.
- [x] Split institution selection/retrieval from prose generation.
- [x] Preserve per-institution failure isolation.
- [x] Preserve registry-metadata degraded fallback.
- [x] Preserve page-citation protection.

### Regulatory and knowledge

- [x] Require external-source consent for regulatory Qdrant access.
- [x] Keep connector-free catalog knowledge available without broadening data access.
- [x] Inventory deterministic versus document-based regulatory paths.
- [x] Convert document-based output to common evidence.
- [x] Preserve complete registered regulatory cards.
- [x] Return governed catalog definitions as knowledge evidence.

### Web

- [x] Require external-source consent before request sanitization and network access.
- [x] Reject private external queries before network access.
- [x] Return sanitized query and citable evidence without source prose.
- [x] Mark web content as untrusted.
- [x] Preserve rate-limit and dependency-failure behavior.

### Phase 4 exit gate

- [x] All handlers return the typed envelope.
- [x] Vector sources do not pre-synthesize prose.
- [x] Citation, limitation, and degraded-mode tests pass.
- [x] Existing cards render from payload unchanged.
- [x] Direct handler tests prove disabled connectors are never called.

## Phase 5 — Common answer composer

### Prompt/output

- [x] Implement the minimal versioned composer prompt defined in plan Section 11.
- [x] Define status, text, sources, citations, unavailable sources, and limitations.
- [x] Keep fixed security/citation rules in the stable prefix.
- [x] Keep routing and authorization logic out of the composer prompt.
- [x] Keep the complete source registry and tool descriptions out of the composer prompt.
- [x] Keep DB catalog, schema mechanics, and SQL instructions out of the composer prompt.
- [x] Keep output field/type descriptions in structured output rather than duplicate prose.
- [x] Carry source-specific limitations in ToolResult rather than global prompt prose.
- [x] Put transcript and evidence after the prefix.
- [x] Delimit retrieved passages as untrusted evidence.
- [x] Prohibit unsupported inference and numeric alteration.
- [x] Require explicit missing/conflicting evidence.

### Composition policy

- [x] Return a deterministic enable-external-sources message for external-only requests while off.
- [x] Add a disabled-external limitation to supported DB results for mixed requests while off.
- [x] Never invoke the composer only to explain that consent is disabled.
- [x] Return complete DB headlines without composition.
- [x] Return deterministic clarification/refusal without composition.
- [x] Return complete schema cards without composition.
- [x] Compose one vector source with one call.
- [x] Compose multiple vector sources with one call.
- [x] Compose DB plus vector evidence with one call.
- [x] Add an extractive fallback.
- [x] Include every unavailable source and limitation in partial status.
- [x] Deduplicate citations deterministically.
- [x] Emit/persist one final answer envelope.

### Model-call budget tests

- [x] Structural DB follow-up: zero routing/composer calls.
- [x] Deterministic DB lookup: zero routing/composer calls.
- [x] Governed DB planning: one planner call on its planned path.
- [x] Normal text-to-SQL: no more than two calls.
- [x] SQL repair: no more than one additional call.
- [x] Single vector source: one call.
- [x] Multiple vector sources: one call.
- [x] DB plus vector: DB planning if needed plus one composer.
- [x] Schema and permission refusal: zero calls.
- [x] External-only request while off: zero model, Qdrant, and web calls.
- [x] Mixed request while off: DB budget only and zero external calls.
- [x] No per-source plus final double synthesis.

### Grounding

- [x] Every generated figure exists exactly in tool evidence or the response falls back extractively.
- [x] Citations are built from associated evidence metadata.
- [x] Missing evidence produces partial/clarify/refuse appropriately.
- [x] Conflicting evidence is required to be surfaced by the composer contract.
- [x] Sensitive DB facts never enter a public-provider request.

### Phase 5 exit gate

- [x] Call budgets pass in local deterministic and fake-provider tests.
- [x] Composer-context audit proves only grounding, citation, answer semantics, relevant
  history, selected evidence, and current request are present.
- [x] One definitive answer is emitted.
- [x] Numerical grounding/reconciliation tests pass.
- [x] Citation/partial-answer contract tests pass.

## Phase 6 — Cache and history hardening

### Stable prefix

- [x] Revalidate router, DB planner, and composer prefix versions/hashes created in Phase 0.
- [x] Keep router source descriptions compact, stable, and deterministically ordered.
- [x] Keep the DB planner's governed Gold prefix independent from other prompts.
- [x] Keep the composer prefix independent from source/tool catalogs.
- [x] Remove dynamic timestamps and ids from the prefix.
- [x] Put current evidence/question after cacheable content.
- [x] Put dynamic consent/effective-source state after the stable prefix.
- [x] Keep stable router descriptions byte-identical across equivalent allowed-source sets.
- [x] Keep provider/model affinity when policy permits.
- [x] Test identical prefix bytes across consecutive turns.

### Cache telemetry/load

- [x] Record prefix version and cached tokens.
- [x] Record cache-write and uncached tokens where supported.
- [x] Compute sum of uncached input tokens across every call in a turn.
- [x] Compute provider-weighted input cost when read/write cache pricing differs.
- [ ] Compare cached-token ratio to baseline.
- [ ] Test one active conversation.
- [ ] Test interleaved conversations.
- [ ] Test production-like concurrency.
- [ ] Tune llama.cpp cache reuse/slots only from measurements.
- [ ] Confirm Gold planner-prefix warmup still works.
- [ ] For llama.cpp, benchmark cache_prompt and n_cache_reuse without changing other providers.
- [ ] For OpenAI Responses API when used, test a stable prompt_cache_key.
- [ ] For supported OpenAI models when useful, test an explicit breakpoint immediately after
  stable instructions and measure cache writes as well as reads.
- [x] Do not send provider-specific cache fields to unsupported providers.
- [ ] Verify the deployed model's minimum cacheable length rather than padding prompts.

### Per-call token budgets

- [ ] Router fallback meets p50 600 and p95 900 uncached input tokens.
- [ ] DB planner dynamic suffix meets p50 1,200 and p95 2,500.
- [ ] Text-to-SQL schema/evidence pack meets p50 1,800 and p95 3,000.
- [ ] Composer total input meets p50 2,000 and p95 4,000.
- [ ] Replayed history meets p50 1,000 and p95 2,000.
- [ ] Single-source evidence meets p50 600 and p95 1,200.
- [ ] All-source evidence meets p50 1,500 and p95 3,000.
- [ ] Compaction input meets p50 2,000 and p95 4,000.
- [x] Router output is capped at 300 tokens.
- [x] DB planner output is capped at 700 tokens.
- [x] Composer output is capped at 160 tokens, with a 20-second whole-call deadline and
  grounded partial fallback.
- [ ] Document any evidence-based budget revision before changing a CI threshold.

### Post-architecture model tuning

- [x] Wait until routing, retrieval, composition, and prompt shapes are stable.
- [ ] Benchmark lower reasoning effort independently for router fallback.
- [ ] Benchmark lower reasoning effort independently for DB planning.
- [ ] Benchmark lower reasoning effort independently for composition.
- [ ] Benchmark lower output verbosity for user-facing composition.
- [ ] Compare correctness, grounding, latency, output tokens, and total cost.
- [ ] Adopt a lower setting only when its task-specific evaluation passes.

### Canonical history

- [x] Maintain one ordered conversational list of user questions and definitive answers.
- [x] Keep router prompts, planner JSON, tool traces, retrieved documents, and UI cards out
  of that conversational list.
- [x] Keep typed per-turn execution state separately and project only relevant facts.
- [x] Confirm Workbench is the only prose transcript sent to Workbench calls.
- [x] Replay only the definitive assistant answer.
- [x] Keep cards, SQL, lineage, and tool logs out of model history.
- [x] Preserve exact structured session facts through compaction.
- [x] Preserve pins and active bindings.
- [x] Preserve the exact submitted consent value and effective source set per turn.
- [x] Preserve the latest explicit conversation toggle outside lossy summaries.
- [x] Keep nlq_conversations structured-only.
- [x] Document why it is not a second chat transcript.
- [ ] Re-tune transcript budget from measured prompts.

### Compaction

- [x] Trigger by token budget, not turn count alone.
- [x] Keep compaction outside response latency.
- [x] Avoid repeatedly summarizing unchanged turns.
- [x] Test newest-turn overflow and recovery.
- [x] Test summary-failure fallback.
- [x] Test long DB, vector, and mixed conversations.

### Phase 6 exit gate

- [ ] Cached-token ratio improves without correctness loss.
- [x] Prefix hashes prove stable serialization before cache comparisons.
- [ ] Per-call p50/p95 budgets pass or have an approved evidence-based revision.
- [ ] Model-setting decisions have post-refactor benchmark evidence.
- [x] Long-history/compaction tests pass.
- [x] Cross-user isolation passes.
- [x] Prompts contain no unauthorized data in local policy/context audits.

## Phase 7 — Rollout and cleanup

### Verification

- [ ] Run the complete backend suite in the deployment image (local sandbox lacks
  `libstdc++.so.6` for NumPy; Workbench and NLQ scoped suites pass).
- [x] Run canonical NLQ and security scoped suites.
- [x] Run Workbench route and answer evaluation.
- [x] Run frontend type-check and production build.
- [ ] Build/smoke-test backend container.
- [ ] Test direct PostgreSQL.
- [x] Test PostgreSQL MCP with a live deterministic governed lookup (752 ms total;
  90 ms SQL execution).
- [x] Test Qdrant unavailable with dependency fakes.
- [x] Test local LLM unavailable with dependency fakes.
- [x] Test stalled router and composer calls against whole-call deadlines.
- [x] Make the rollout verifier reject an unavailable or mismatched required LLM.
- [x] Route unqualified current whole-book outstanding directly from the governed catalog.
- [x] Keep optional entity completion SQL off the event loop, suppress overlapping probes,
  and apply a database-outage cooldown.
- [x] Apply a database-outage cooldown to Workbench history persistence retries.
- [x] Test optional public-only Groq routing/model isolation with configuration tests.
- [ ] Test all external connectors with consent off and on.
- [x] Test role ∩ deployment ∩ consent intersections locally.
- [x] Test source pin, direct tool, workspace, and web-client bypass attempts locally.

### Rollout

- [ ] Shadow legacy/new paths where feasible.
- [ ] Review route, answer, citation, and numeric differences.
- [ ] Enable internal canary.
- [ ] Monitor calls, tokens, cache, latency, errors, partials, and refusals.
- [ ] Monitor external-consent denials, toggle adoption, connector use, and policy mismatches.
- [ ] Expand by percentage after canary gate.
- [ ] Complete observation window.
- [ ] Exercise rollback before full rollout.

### Cleanup

- [x] Make the new orchestrator default.
- [x] Remove the legacy graph path.
- [x] Remove obsolete LangGraph routing/runtime schemas while retaining the compact ambiguity fallback.
- [x] Remove per-source synthesis prompts.
- [ ] Remove unused personalization if product metrics do not justify it.
- [x] Remove temporary graph adapters.
- [x] Remove graph dependencies and regenerate lockfiles.
- [x] Update backend README and architecture docs.
- [x] Update deployment/rollback runbooks.
- [x] Archive baseline/final comparison reports.

### Final acceptance

- [x] Serialize llama.cpp calls within and across the API/PostgreSQL MCP containers.
- [x] Send explicit prompt-cache and no-thinking controls to llama.cpp.
- [x] Limit prompt-cache warmup generation to one token.
- [x] Replace the planner's complete column YAML with the compact governed semantic surface.
- [x] Use retrieved table detail, rather than every catalog column, for text-to-SQL.
- [x] Document the required single-slot Qwen3.5/3.6 server configuration.

- [x] Safety, PII, role, and read-only scoped tests pass 100% locally.
- [x] Omitted/false consent produces zero Qdrant and web operations in local tests.
- [x] True consent enables only the role/deployment intersection.
- [x] Direct pins, tools, and Workbench workspace actions cannot bypass consent.
- [x] Every new conversation defaults to external sources off.
- [x] Canonical NLQ numeric accuracy does not regress in the scoped NLQ suite.
- [x] Source-set accuracy is at least 95% on the deterministic fixture corpus.
- [ ] Median call count falls at least 50%.
- [ ] Non-cached prompt tokens fall at least 40%.
- [x] Router, DB planner, and composer use distinct minimal prompt builders.
- [x] Composer contains no routing catalog, complete tool descriptions, DB schema, or
  duplicated structured-output specification.
- [ ] Per-call p50/p95 token budgets pass or have approved evidence-based revisions.
- [ ] Prefix version/hash telemetry proves byte-stable reuse.
- [ ] Reasoning and verbosity settings are backed by post-refactor evaluations.
- [x] At least 80% of deterministic evaluation selections avoid the model router.
- [x] No turn uses more than one user-facing composition call.
- [ ] Single-source p95 latency does not regress.
- [ ] First-card regression is no greater than 10%.
- [x] SSE/history compatibility passes.
- [ ] Rollback is verified.
- [x] Legacy orchestration is deleted.

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
- [ ] Keep external-source consent outside model control and validate every tool call against it.

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
