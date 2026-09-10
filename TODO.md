# Native Tool-Calling Workbench TODO

Updated: 2026-09-09
Branch: `fix/regex-removal`
Authority: `PLAN.md`

The Workbench uses one provider-native agent path. Phases A to H record the completed foundation
and remaining handoff checks. Phase I migrates all Workbench loan-book access to one PostgreSQL
MCP tool and places the complete compact Gold schema in the first model request. Focused static
checks and live smoke validation remain in scope; the regression suite is deferred until the
user re-enables it.

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

### F5. Remove hidden local SQL-generation shortcuts

- [x] Remove the legacy local SQL generator and its callers.
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
- [x] Confirm the previous native-only plan, `TODO.md`, and final `context.md` described the same
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
- [x] Make `agent_customers` honor advertised loan fields, including per-customer sanctioned
      totals and all distinct tenure values, while rejecting unsupported field/detail pairs.
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
- Run focused validation as implementation changes land; keep the regression suite deferred
  until the user re-enables it.

## Phase I — PostgreSQL MCP-native database access

Canonical design: `PLAN.md`

### I0. Analysis and contract decision

- [x] Audit the model-visible tools, executor handlers, PostgreSQL MCP server/client, Gold
      catalog prompt, source policy, API request, and frontend connection selector.
- [x] Confirm the Workbench model does not currently receive PostgreSQL MCP tools directly.
- [x] Confirm native database handlers currently bypass MCP even when `data_access=mcp`.
- [x] Decide that only tools discovered from the configured PostgreSQL MCP server will be exposed
      for loan-book database access; no local database wrapper tool will be introduced.
- [x] Decide that the complete compact Gold schema will be present from the first model request.

### I1. PostgreSQL MCP boundary

- [x] Configure the PostgreSQL MCP implementation with native read-only `query(sql)` capability;
      complete Gold metadata is supplied in the startup-cached model prompt.
- [x] Call MCP `list_tools` and record the actual native tool names, descriptions, and schemas;
      do not invent or rename a `query_gold` wrapper.
- [x] Reuse the existing Gold catalog, SQL AST, function, join, PII, cost, row-limit,
      statement-timeout, and read-only-role enforcement inside the MCP server.
- [x] Derive user, role, and frozen policy from trusted backend context; never accept model-chosen
      authorization attributes.
- [x] Return native structured metadata/query results and safe structured errors from the MCP
      tools.
- [x] Keep `postgres_health` backend-only.
- [x] Remove the nested-planner `ask_loan_book` tool from the PostgreSQL MCP server.
- [x] Remove `curiosity_graph` from PostgreSQL MCP while keeping its standalone API intact.

### I2. Startup initialization and Gold schema prefix

- [x] Build a compact complete schema projection covering all Gold tables, columns, joins,
      metrics, dimensions, enums, restrictions, units, grains, PII classifications, and catalog
      version.
- [ ] Measure the schema prefix with the deployed tokenizer and keep adequate 32K context headroom
      for tools, history, observations, and output.
- [x] Load and validate the catalog during backend application startup.
- [x] Cache the exact schema prefix by catalog version and include it in every agent system prompt.
- [x] Retain question-specific catalog retrieval only as optional ranking guidance, never as an
      allowlist or substitute for complete schema context.
- [x] Initialize PostgreSQL MCP at startup, validate the discovered read-only tool contracts, and
      expose cached readiness plus the Gold schema version in backend `/health` diagnostics.
- [ ] Decide from measured startup/runtime behavior whether a non-authoritative llama.cpp prompt
      warm-up is beneficial.

### I3. MCP client and model tool exposure

- [x] Add generic discovered-tool dispatch and structured MCP error mapping without a semantic
      database wrapper.
- [ ] Reuse a managed MCP session when supported, with bounded reconnect as fallback.
- [x] Discover and validate MCP tool schemas at startup and translate the authorized definitions
      into provider-native function definitions without renaming or semantic rewriting.
- [x] Combine authorized PostgreSQL MCP tools only with authorized non-database tools for each
      request.
- [x] Dispatch every discovered PostgreSQL tool by its original name and arguments exclusively
      through MCP.
- [x] Return all retryable MCP validation, transport, timeout, and execution failures to the same
      model within the existing turn budget.
- [x] Remove the argument-repair kill switch so malformed/denied tool calls always return a typed
      observation to the same model while the hard turn budget remains.

### I4. Remove model-facing database tools

- [x] Remove `query_metrics` from the Workbench model registry and executor.
- [x] Remove `lookup_records` from the Workbench model registry and executor.
- [x] Remove `run_analysis` from the Workbench model registry and executor.
- [x] Remove `create_worklist` from the Workbench model registry and executor.
- [x] Remove `generate_briefing` from the Workbench model registry and executor.
- [x] Remove `run_validated_query` and its nested SQL-generation path from the Workbench agent.
- [x] Remove `inspect_loan_catalog` from the model registry after the complete startup schema is
      available.
- [x] Preserve underlying domain services still used by dedicated APIs or UI features.
- [x] Remove obsolete model-only argument contracts after confirming their remaining references
      were confined to the deferred Workbench regression tests.

### I5. Keep non-database sources separate

- [x] Keep `search_curated_knowledge` for concepts, macro, competitive, and regulatory sources.
- [x] Remove the `schema` domain from `search_curated_knowledge`.
- [x] Keep `search_public_web` subject to deployment availability, explicit consent, and outbound
      private-data protection.
- [x] Keep `finish_without_data` for clarification and governed refusal.
- [x] Remove the obsolete Workbench schema source pin and schema quick action; the complete Gold
      schema is now agent context, while the standalone Curiosity Graph API remains intact.
- [x] Verify structurally that source pins and policy filtering narrow the effective source set;
      MCP definitions are added only when the frozen policy contains `db`.

### I6. Remove selectable direct database access

- [x] Remove `data_access` from the Workbench API request and backend state.
- [x] Remove `data_access` from `AgentExecutionContext` and all active Workbench handlers.
- [x] Remove frontend `dataAccess` state and API serialization.
- [x] Remove the Direct adapter/MCP selector from the Composer.
- [x] Show a non-editable PostgreSQL MCP connection/status label.
- [x] Update environment and Compose comments so PostgreSQL MCP is the sole Workbench database
      boundary and the MCP container executes only through the read-only adapter.

### I7. Cleanup and documentation

- [x] Remove the legacy Workbench `nodes.run_db()` and `nodes.run_schema()` comparison paths after
      confirming they had no active callers.
- [x] Remove obsolete Workbench wrappers, imports, model-only schemas, and direct/MCP selection
      configuration.
- [x] Keep standalone `/nlq`, Curiosity Graph, worklist, analysis, and briefing consumers intact
      until their dependencies are explicitly audited.
- [x] Update `context.md` to describe the resulting MCP-native architecture and distinguish
      local verification from deployment-machine checks.
- [x] Update the rollout runbook for MCP discovery, status-only model health, and deployment-host
      smoke validation.
- [x] Keep `PLAN.md` and this checklist synchronized whenever scope or contracts change.

### I8. Focused verification and exit gate

- [x] Run focused Python compilation, frontend TypeScript, prompt completeness, in-process MCP
      contract, retired-symbol, and `git diff --check` validation; Ruff is unavailable in this
      environment and the deferred regression suite remains intentionally unrun.
- [ ] Smoke-test a simple aggregate, multi-column record list, join, filtered ranking, and
      multi-turn follow-up against the deployed model.
- [ ] Smoke-test unknown column, invalid join, unsafe SQL, timeout, MCP disconnect, authorization
      denial, and result truncation; verify retryable failures return to the model.
- [ ] Verify on the deployment machine that the first recorded model request contains the complete
      catalog-versioned Gold schema; local prompt construction has been statically verified.
- [x] Verify every model-visible loan-book database tool comes from PostgreSQL MCP discovery and no
      locally defined model-facing database tool remains.
- [x] Verify no model-initiated Workbench database execution occurs in the API process or invokes a
      nested planner. Dedicated APIs and composer completion lookup are outside this model-tool
      migration and still use their existing governed services.
- [ ] Record catalog/prompt versions, deployed model, commands, smoke results, latency, and known
      limitations in the final handoff.
