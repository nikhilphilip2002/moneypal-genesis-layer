# Native Tool-Calling Workbench TODO

Updated: 2026-09-09
Branch: `fix/regex-removal`
Authority: `plan.md`

The Workbench will support one execution path: provider-native tool calling. Phases A to E are
complete. Remaining work removes rollout modes, legacy orchestration, behavioral routing, and
hidden text-to-SQL shortcuts. Run the full validation suite after implementation; cross-model
testing is out of scope.

## Completed foundation — Phases A to E

- [x] Bound model observations while retaining complete durable tool results.
- [x] Persist context overflow and return a user-visible SSE error.
- [x] Use one bounded agent loop and one round/tool-call budget.
- [x] Return recoverable failures to the model as typed tool observations.
- [x] Keep full authorized native tool schemas available without lexical narrowing.
- [x] Store ordered version-7 execution events and replay native history from them.
- [x] Measure compaction against native replay without deleting durable events.
- [x] Validate SQL columns per scope, including CTEs, aliases, subqueries, and UNION branches.
- [x] Ground numeric answer claims against source and deterministic derived facts.

## Phase F — Native-only simplification

### F1. Native agent is the only entry point

- [x] Call `agent.run(state)` directly for every Workbench request.
- [x] Remove `assigned_mode`, mode hashing, shadow selection, and canary assignment.
- [x] Remove `WORKBENCH_AGENT_MODE` and `WORKBENCH_AGENT_CANARY_PERCENT` from configuration and
      `.env.example`.
- [x] Log the execution architecture as `native_only` at startup.

### F2. Remove legacy orchestration and fallback

- [x] Delete `_run_legacy` and the legacy branch from `workbench/orchestrator.py`; remove the
      wrapper if it is no longer useful.
- [x] Remove native-to-legacy fallback, counters, route events, and history metadata.
- [x] Remove `select_sources` and `dispatch_sources` after all callers use native tools.
- [x] Remove frontend `legacy_fallback` handling and fallback-only API types.
- [x] Ensure native failures produce exactly one typed observation, refusal, or error outcome.

### F3. Remove behavioral routing

- [x] Delete `workbench/router.py` and its routing prompt/evaluator dependencies.
- [x] Remove database, schema, knowledge, macro, competitive, regulatory, web, freshness,
      descriptive, structural-follow-up, and ambiguity-routing cues.
- [x] Remove `_db_subquestion`, catalog routing overrides, and question rewriting.
- [x] Replace `router.RouteDecision` with a neutral execution-result contract.
- [x] Derive sources, tool names, limitations, and effective sources from validated native calls.
- [x] Keep the `route` SSE event only as a compatibility report of model-selected calls.

### F4. Preserve policy and safety boundaries

- [x] Compute visible tools solely from role, deployment availability, consent, and pins.
- [x] Reauthorize every model-returned tool call immediately before execution.
- [x] Keep PII/outbound checks, strict argument validation, catalog governance, SQL AST
      validation, parameter binding, and read-only execution.
- [x] Keep round, call, row, observation, context, and deadline limits.
- [x] Prevent destructive operations through capability absence and SQL validation, without a
      question-routing regex.
- [x] Verify direct-tool and pinned-source entry points cannot broaden authorization.

### F5. Remove hidden text-to-SQL shortcuts

- [x] Remove `allow_reviewed_shortcuts` from `text_to_sql.generate` and its callers.
- [x] Delete automatic question-pattern selection for interest-rate distributions,
      agent/borrower collections, agent directory queries, named-borrower disbursement, and
      named-borrower principal collection.
- [x] Delete shortcut-only regexes, helper functions, lineage labels, and tests.
- [x] Send every free-form validated-query request through model SQL generation and governed
      validation.
- [x] Retain explicit native preset tools; they execute only when the model selects them.

### F6. Cleanup

- [x] Remove unreachable legacy adapters, router prompts/schemas, evaluation modules,
      configuration, imports, fixtures, and fallback-only history fields.
- [x] Retain source handlers used by native tool executors.
- [x] Do not remove unrelated FastAPI route modules or domain APIs.
- [x] Update architecture and environment comments for the native-only path.
- [x] Confirm `rg` finds no remaining Workbench references to `workbench.router`,
      `select_sources`, `dispatch_sources`, `_run_legacy`, `assigned_mode`, shadow, canary,
      legacy fallback, or `allow_reviewed_shortcuts`.

### F7. Final validation

- [x] Run focused Ruff, Python compilation, retired-symbol scans, and `git diff --check` after
      F1–F6.
- [ ] Run the complete backend suite and frontend type/build checks.
- [ ] Run the single-turn and multi-turn native corpus against the deployed model.
- [x] Run the offline multi-turn corpus (24 passed) and verify the current nudge expectations.
- [x] Assert exact native tool names and structured arguments; do not score behavior with
      question-specific regexes.
- [x] Cover follow-up filter/period changes, aggregate-to-record drills, spelling errors,
      invalid arguments, unknown tools, rejected SQL repair, exhausted budgets, and large
      bounded observations.
- [ ] Verify every Workbench request enters the native agent exactly once and no legacy or
      shortcut path can execute.
- [ ] Record model id, prompt/catalog versions, commit, commands, pass counts, latency, and
      failure categories.

### Phase F exit gate

- [x] Native tool calling is the sole Workbench execution path.
- [x] Sources in SSE/history come only from validated model tool calls.
- [x] No application code rewrites user questions or model semantic arguments.
- [x] No behavioral router, legacy fallback, rollout mode, or hidden SQL shortcut remains.
- [x] Authorization, consent, PII, SQL safety, and bounded execution remain enforced.
- [ ] The final suite and native conversation corpus pass against the deployed model.

## Phase G — Documentation and handoff

- [x] Rewrite `context.md` after Phase F for the resulting native-only code.
- [x] Remove obsolete shadow, canary, legacy fallback, router-retirement, shortcut-retirement,
      and cross-model evaluation claims from active documentation.
- [ ] Record final branch, commit, deployed model id, prompt/catalog versions, commands, pass
      counts, and interrupted commands.
- [ ] Record whether the version-7 production history migration has run.
- [ ] After its rollback window, disable and remove legacy `agent_exchanges` compatibility
      writes.
- [x] Confirm `plan.md`, `TODO.md`, and final `context.md` describe the same architecture and
      completion state.

## Phase H — Workbench contract fidelity

### H1. Stream and history contracts

- [x] Add answer suggestions, refusal metadata, route tools, and structured errors to the
      frontend API/event contracts.
- [x] Parse refusal `text`, route `tools`, and complete structured errors from live SSE.
- [x] Preserve the same route and error metadata in persisted history and reopened turns.

### H2. Rendering

- [x] Render verified facts separately from answer prose.
- [x] Include `catalog` in final-answer supporting cards.
- [x] Render direct-answer suggestions as accessible `onAsk` chips.
- [x] Render error codes/references without obscuring the error message.
- [x] Show model-selected native tools separately from source badges.

### H3. Tests and rollout

- [x] Add live/parser, history-compatibility, and rendering contract regressions for every field.
- [x] Run focused backend tests, Ruff, TypeScript, production frontend build, and `git diff --check`.
- [x] Preserve verified tool results when provider-specific LLM synthesis times out.
- [x] Consolidate generic, selection, and composition LLM deadlines into `LLM_TIMEOUT`.
- [x] Check provider `/health` status—without model-name matching—before the Workbench submits
      its first completion request.
- [x] Return malformed native responses and unexpected tool preflight failures to the model as
      structured repair feedback instead of ending the turn immediately.
- [x] Gate frontend sends on `/nlq/health`, retry three times, and preserve unsent composer text
      when readiness cannot be established.
- [x] Remove the obsolete `reviewed` argument that broke deterministic record lookups and
      completions after the `SqlAttempt` contract changed.
- [ ] Deploy, then verify representative answer, clarification, refusal, error, catalog, and
      history-reload flows against the live Workbench.

## Standing rules

- The LLM selects behavior; application code enforces permissions and safety.
- Never parse assistant prose as an executable tool call.
- Never mutate model-generated semantic arguments.
- Never expose a tool the role, deployment, consent state, or pin does not authorize.
- Never execute generated SQL before catalog and AST validation.
- Never add question-specific behavioral routing or SQL shortcuts to fix an evaluation case.
- Keep complete durable audit events and explicitly bounded model observations.
- Run all final tests after the implementation changes are complete.
