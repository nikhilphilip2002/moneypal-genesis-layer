# Query Attribution Implementation Todo

This checklist implements [plan.md](./plan.md). Complete tasks in order unless a task is
explicitly marked as parallel-safe.

> Pre-release cutover: section 13 supersedes every earlier checked compatibility, legacy
> rendering, rollout-flag, and automatic-card item. Those paths must be deleted, not retained.

## 0. Baseline and contract lock

- [ ] Capture current SSE fixtures and history payloads for single-query, corrected-query,
  multi-query, and conceptual turns.
- [x] Record current Workbench backend and frontend test results.
- [x] Confirm final names: `query_id`, `attempt_id`, `active_query_ids`,
  `visual_query_ids`, and `excluded_queries`.
- [x] Lock the initial status, purpose, and exclusion reason-code enums.
- [x] Decide the feature-flag names and default them off.

## 1. Backend identity and registry

- [x] Add typed query execution and attempt contracts in
  `backend/app/services/workbench/agent_contracts.py`.
- [x] Add a per-turn query registry to Workbench state.
- [x] Implement deterministic `<turn_id>:qN` allocation before database execution.
- [x] Implement `<query_id>:aN` attempt allocation for unchanged retries after errors/timeouts.
- [x] Keep provider `tool_call_id` as a separate correlation field.
- [x] Define unchanged-query retry versus corrected-query/new-logical-ID behavior.
- [x] Pass IDs through PostgreSQL MCP metadata and validate any returned correlation.
- [x] Attach `query_id` and `attempt_id` to database card metadata.
- [x] Record pending, running, success, empty, error, timeout, and cancelled transitions.
- [x] Classify query purpose as answer, discovery, validation, or intermediate during
  final reconciliation, without allowing semantic labels to override execution status.

## 2. Observation standardization

- [x] Add the query-reference block to every executed database success and failure observation.
- [x] Put status, summary, row count, and bounded data in a stable observation shape.
- [x] Update observation shaping so identifiers and status can never be truncated.
- [x] Preserve full durable tool results independently of model-facing truncation.
- [x] Add tests for large result sets, errors, empty results, and clipped summaries.
- [x] Verify replayed observations retain the original query identifiers.

## 3. Structured synthesis

- [x] Add the versioned final synthesis Pydantic model.
- [x] Extend the Workbench answer contract with active, visual, and excluded references.
- [x] Update prompts with explicit include/exclude attribution rules.
- [x] Add the explicit no-query/empty-list instruction for conceptual requests.
- [x] Enable provider-native structured output through the strict
  `submit_final_answer` native-tool contract.
- [x] Add strict native-schema validation with bounded in-loop repair and a conservative
  plain-text compatibility fallback. Workbench providers are required to support native tools.
- [x] Ensure identifiers are never extracted from narrative prose.
- [x] Preserve existing answer fields, citations, facts, limitations, and refusal behavior.

## 4. Reconciliation and safety

- [x] Implement ordered deduplication of proposed query IDs.
- [x] Remove IDs not present in the current turn registry.
- [x] Filter failed, timed-out, cancelled, empty, and superseded queries.
- [x] Intersect visual IDs with active IDs and valid visual payloads.
- [x] Generate deterministic backend exclusion reasons.
- [x] Sanitize length and content of optional model-provided rationales.
- [x] Store raw model attribution separately from reconciled attribution.
- [x] Implement the conservative one-query compatibility fallback.
- [x] Preserve explicit valid empty lists without applying fallback.
- [x] Implement the zero-query/no-placeholder behavior.
- [x] Add cross-turn/current-registry and duplicate-ID safety tests.

## 5. Streaming

- [x] Add query registered, started, completed, and failed event contracts.
- [x] Include turn, logical-query, and attempt IDs in every lifecycle event.
- [x] Make frontend query lifecycle updates idempotent by `attempt_id`.
- [x] Include reconciled attribution in the authoritative `answer` event.
- [x] Keep `done` last and exactly once on every terminal path.
- [x] Mark narrative deltas and early cards as provisional in the flagged UI.
- [x] Retain `source_card` compatibility while the frontend flag is off.
- [ ] Test out-of-order parallel completion, replay, interruption, and reconnection.

## 6. Persistence and migration

- [x] Increment `history.RECORD_VERSION`.
- [x] Persist the ordered registry and current attempt records on each turn.
- [x] Key new stored database cards by `query_id`.
- [x] Persist raw and reconciled attribution plus the answer schema version.
- [x] Preserve query IDs in exact native transcript replay.
- [x] Add compatibility reads for records without attribution fields.
- [x] Make legacy turns expose all successful cards only when fields are absent.
- [x] Confirm explicit empty arrays survive save and reload unchanged.
- [x] Test unknown future record versions are not overwritten.
- [ ] Add migration fixtures for every currently supported record version.

## 7. Frontend contracts and state

- [x] Extend `WorkbenchAnswer` and history types in `frontend/lib/api.ts`.
- [x] Add typed parsing for query lifecycle fields.
- [x] Store provisional database cards idempotently by `query_id`.
- [x] Reconcile the visible layout when the authoritative answer arrives.
- [x] Preserve ID ordering from `visual_query_ids`.
- [x] Apply legacy display fallback only when attribution fields are absent.
- [ ] Add reducer/parser tests for duplicate, unknown, and missing IDs.

## 8. Frontend presentation

- [x] Keep full charts, KPIs, and tables unmounted while generation is in progress when
  the rollout flag is enabled.
- [x] Show lightweight execution progress in `ExecutionTrace.tsx`.
- [x] Render verified visual cards beside or below the final narrative.
- [x] Add a collapsed “background queries” drawer to `WorkbenchTurn.tsx`.
- [x] Show status, row count, exclusion reason, and query reference in the drawer.
- [x] Reuse authorized card lineage/SQL inspection controls in the drawer.
- [x] Ensure zero visual IDs produce no blank cards or placeholders.
- [x] Ensure non-visualizable payloads fail closed into the audit drawer.
- [x] Use native accessible `details`/`summary` keyboard behavior for the drawer.

## 9. Automated verification

- [x] Happy path: one successful query, one active visual.
- [x] Self-healing: failed Query 1, corrected Query 2, only Query 2 active.
- [x] Multi-query synthesis: supporting results remain in declared order.
- [x] Abandoned result: successful but unused query receives an audit exclusion.
- [x] Pure conversation: empty attribution and zero cards.
- [x] Hallucinated ID: stripped without a broken card.
- [x] Empty result: excluded from primary visuals.
- [x] Timeout then retry: attempts share the intended logical identity.
- [x] Out-of-order registry completion: final order follows synthesis attribution.
- [x] Malformed/plain synthesis compatibility fallback is deterministic.
- [ ] Stream interruption/reconnect: provisional cards are never promoted accidentally.
- [x] History API reload preserves the exact reconciled visual/audit partition.
- [x] Legacy history: successful historic cards remain visible by field-presence fallback.
- [x] Run `uv run pytest backend/tests/workbench` (328 passed).
- [ ] Run `uv run pytest backend/tests/nlq` cleanly. Current result: 1049 passed and 97
  skipped; unrelated golden case `g071` fails because its May history-warning fixture no
  longer matches the catalog's August single-snapshot warning.
- [x] Run available frontend lint and type-check checks. No component-test script exists.

## 10. Observability

- [x] Emit attempted, successful, active, visual, and unused query counts per answered turn.
- [x] Emit invalid-reference counts.
- [x] Emit single-query fallback telemetry.
- [x] Emit structured-output repair and filtered-error-reference counters.
- [x] Emit data-bearing-answer-with-empty-attribution anomalies.
- [x] Segment unused-query metrics by purpose and tool without logging result rows.
- [ ] Add dashboard panels for executed-to-active ratio and attribution failure rate.
- [ ] Add alerts for cross-scope references and primary-card resolution failures.

## 11. Rollout

- [ ] Deploy the raw-result backend and derived-only frontend as one incompatible cutover.
- [ ] Clear the pre-release Workbench conversation table before enabling the new build.
- [ ] Remove the frontend filtering kill switch and make derived-only rendering unconditional.
- [ ] Canary by stable user bucket and verify visualization repair, timeout, and missing-card
  metrics.
- [ ] Roll back the deployment and clear incompatible pre-release history if the canary fails.
- [ ] Update Workbench runbooks and architecture documentation.

## Definition of done

- [ ] All acceptance criteria in `plan.md` are demonstrated by automated tests or a saved
  release verification artifact.
- [ ] No failed, empty, timed-out, superseded, or hallucinated query appears in the primary
  visual zone.
- [ ] Query identity is unchanged across execution, observation, SSE, storage, and reload.
- [ ] A conceptual no-query answer renders no visual placeholder.
- [ ] Rollback has been exercised successfully before general availability.

## 12. Follow-up visualization

- [x] Add the compact strict `visualize_query_result` contract and aggregation guidance.
- [x] Resolve source results only inside the current user's conversation.
- [x] Validate fields, chart compatibility, numeric inputs, and complete-result aggregation.
- [x] Implement `none`, `sum`, `avg`, `min`, `max`, `count`, and `count_distinct` reshaping.
- [x] Register successful derived visuals as current-turn `<turn_id>:vN` records linked to
  their historical `source_query_id`.
- [x] Stream and persist derived cards through the existing attribution path.
- [x] Tell the model to use the tool for "visualize this" follow-ups and cite its returned ID.
- [x] Add focused contract, access-control, transformation, and attribution tests.

## 13. Remove automatic chart inference

- [x] Split raw SQL result storage from renderable `SourceResult` cards.
- [x] Store rows, columns, units, completeness, and lineage on a non-renderable `qN`
  `result_payload` used by observations and `visualize_query_result`.
- [x] Remove `charts.build_from_rows()` from the Workbench PostgreSQL execution path.
- [x] Mark raw `qN` executions `visual_available=false` and stop emitting `source_card` for
  them; continue emitting query lifecycle progress.
- [x] Update `visualize_query_result` to read the raw result payload rather than a generated
  query card.
- [x] Require the model to call `visualize_query_result` for every database result that must
  be presented, using `table` when no graphical form is appropriate.
- [x] Emit and persist only derived `vN` records as database presentation cards.
- [x] Keep raw `qN` entries in the audit drawer as status, row count, SQL, and lineage only.
- [x] Delete legacy automatic-chart rendering branches from history normalization and the
  frontend; do not support old Workbench turns.
- [x] Increment the record version and reject any pre-release record that survives deployment
  cleanup instead of migrating it.
- [x] Add an explicit deployment step to clear pre-release Workbench conversation records.
- [x] Remove automatic-inference fallback paths, including budget/error fallbacks that could
  promote a raw `qN` card.
- [x] Remove the frontend attribution rollout flag and all render-all-cards fallback behavior.
- [x] Delete tests and fixtures whose only purpose is automatic-chart or legacy-card
  compatibility.
- [x] Add focused tests proving query execution emits no card, every supported presentation
  comes from `vN`, invalid visualization requests repair or fail closed, and unsupported old
  record versions are rejected.

## 14. FastMCP 4 and MCP SDK v2 migration

### 14.1 Dependency and protocol baseline

- [x] Replace `mcp==1.29.0` with `fastmcp>=4.0.5,<5` and `mcp>=2.0.0,<3`.
- [x] Regenerate `uv.lock`, sync the environment, and record the resolved FastMCP/MCP versions.
- [x] Replace MCP SDK v1 imports, transports, timeout types, and camel-case field reads.
- [ ] Disable FastMCP's MCP camel-case compatibility bridge in CI and prove there are no
  compatibility warnings or attribute failures.

### 14.2 Shared result and schema boundaries

- [x] Adopt the owned-tool `success/data/error` JSON-compatible result envelope.
- [x] Return dictionaries from handlers and consume FastMCP `result.data`; do not add a custom
  `MCPToolResult` wrapper, nested `text` payload, or double JSON serialization.
- [x] Add a small helper that requires an object result from Moneypal-owned tools.
- [x] Keep third-party text/structured-content fallback isolated in `exa_client.py`.
- [x] Add `backend/app/mcp/provider_schema.py` as the only MCP-to-provider schema adapter.
- [ ] Cover references, nullable values, nested closed objects, enums, bounds, arrays,
  unsupported unions, failure paths, and deterministic output in adapter tests.

### 14.3 FastMCP clients and remote servers

- [x] Replace the PostgreSQL `ClientSession`/raw Streamable HTTP stack with `fastmcp.Client`.
- [x] Migrate `postgres_server.py` to FastMCP 4 without weakening SQL, role, PII, catalog,
  cost, row, timeout, metadata, or backend-only health boundaries.
- [x] Move PostgreSQL transport settings from the server constructor to the FastMCP 4 runner.
- [x] Return PostgreSQL success and expected failure results through the common envelope.
- [x] Replace the Exa raw MCP session with a FastMCP HTTP client and preserve headers, outer
  timeout, quota/rate-limit classification, and third-party response fallback.
- [ ] Verify Docker service startup, `/mcp` routing, health, discovery, and clean shutdown.

### 14.4 In-process Workbench tool server

- [x] Add `backend/app/mcp/workbench_server.py` with one in-process FastMCP server.
- [x] Register the existing `search_curated_knowledge`, `search_public_web`,
  `visualize_query_result`, `finish_without_data`, and `submit_final_answer` tools.
- [ ] Make typed FastMCP functions the only owner of tool names, descriptions, input fields,
  validation, and handler registration.
- [x] Pass trusted execution context outside the model-visible schema and reauthorize every
  source immediately before execution.
- [x] Test every local tool through `Client(workbench_mcp)` for discovery, valid calls,
  invalid/extra arguments, cross-field validation, result envelopes, and policy denial.

### 14.5 Runtime policy, catalog, and execution routing

- [ ] Replace `AgentTool` with a runtime-only policy record containing source, sensitivity,
  timeout, observation limit, and parallel-safety metadata.
- [ ] Fail startup if a model-visible local tool has no runtime-policy classification.
- [ ] Add `ToolCatalog` to discover canonical local and PostgreSQL descriptors, reject name
  collisions, apply per-request policy, and produce deterministic model definitions.
- [ ] Cache only canonical descriptors; never cache role- or user-filtered definitions.
- [ ] Keep `postgres_health` and raw Exa tools out of the model-visible catalog.
- [ ] Preserve policy-specific curated-domain narrowing during provider projection.
- [x] Route local calls through the in-memory FastMCP client and PostgreSQL calls through the
  HTTP client using catalog ownership.
- [x] Remove `_HANDLERS`, direct local dispatch, `_portable_schema`, and the PostgreSQL
  `_provider_schema` after all callers migrate.
- [ ] Remove the remaining pre-MCP local argument validation so FastMCP is the single input
  contract boundary; retain only execution-time business and authorization checks.

### 14.6 Startup, observability, and regression

- [ ] Validate local schemas, runtime-policy coverage, PostgreSQL discovery, health, duplicate
  names, and schema fingerprints during startup.
- [ ] Expose bounded readiness for server ownership, tool names, protocol version, and schema
  fingerprint without logging schemas or result rows.
- [x] Preserve query/attempt identity, deadlines, observation shaping, durable replay,
  visualization, final synthesis, and reconciliation behavior.
- [ ] Add forged-call, duplicate-name, missing-policy, concurrent-call, shutdown-timeout, and
  Docker local/PostgreSQL/web end-to-end tests.
- [ ] Run the full Workbench and NLQ backend suites plus available frontend checks.
- [ ] Update README, environment examples, architecture documentation, and rollout runbook.

### 14.7 Rollout and cleanup

- [ ] Add a temporary `WORKBENCH_MCP_LOCAL_EXECUTION` staging flag while both execution paths
  consume MCP-discovered schemas.
- [ ] Compare discovered schema fingerprints and result envelopes in staging.
- [ ] Enable in-memory local execution, canary it, and verify error/timeout/policy telemetry.
- [ ] Remove the staging flag, legacy local execution path, and obsolete tests after one
  stable release.

### FastMCP migration definition of done

- [x] All model-visible definitions originate from MCP discovery and use one provider adapter.
- [x] Local tools execute in memory; PostgreSQL remains remote and governed.
- [x] Owned tools use `success/data/error` without a duplicate result wrapper.
- [x] Policy is enforced during discovery and execution.
- [x] No MCP SDK v1 import, camel-case MCP field read, or duplicate schema generator remains.
- [ ] Full regression and Docker smoke verification pass.
