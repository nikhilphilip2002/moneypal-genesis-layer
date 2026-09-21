# Workbench Query Attribution and Visual Reconciliation Plan

## Purpose

Make every database-backed Workbench answer explicitly declare which query results support
the final narrative, then let the backend validate that declaration before the frontend
renders any full visual cards.

The execution registry is the source of truth. The model may nominate query references, but
it cannot create, validate, or authorize them. The final answer event carries the reconciled
references, and history written under the new contract preserves that exact resolved state.

## Outcomes

- Every database query attempt has a stable identity before execution begins.
- Query identity survives execution, model observations, SSE events, persistence, reload,
  and rendering.
- The final model response follows a strict structured contract.
- Only successful, data-bearing, explicitly used results appear in the primary visual zone.
- Failed, empty, superseded, and unused queries remain available in a compact audit trail.
- Conceptual answers produce no empty visual placeholders.
- Pre-release records from the automatic-chart implementation are unsupported and removed
  during deployment; no rendering compatibility path is retained.
- A follow-up such as "visualize this" can turn a successful result from the same
  conversation into a new, explicitly attributed visual without rerunning SQL.
- New SQL executions never infer or emit a chart automatically. Every user-facing chart,
  KPI, or table is created through the validated `visualize_query_result` tool.

## Model-directed presentation

Add a strict `visualize_query_result` native tool. The model selects one of `kpi`, `line`,
`area`, `stacked_area`, `bar`, `grouped_bar`, `table`, `donut`, `scatter`, or `heatmap`,
plus the source fields and aggregation. Its compact arguments are `query_id`, `chart_type`,
`x`, `y`, `series`, and `aggregation`.

The backend resolves the source only from successful, data-bearing queries stored in the
same user-owned conversation. It validates field names, types, result completeness, chart
compatibility, and aggregation before creating a derived visual. The model never supplies
rows and cannot use a query from another conversation or user.

This tool is the only presentation boundary for new database results, not merely a
follow-up feature. After a database query succeeds, the model must call
`visualize_query_result` before final synthesis whenever the result needs to be shown. It
chooses a graphical type when the shape and request support one, and chooses `table` when
rows are the honest presentation. The query executor itself never chooses a chart type.

`aggregation=none` means the source already has one value at the desired `x`/`series`
grain. Other operations (`sum`, `avg`, `min`, `max`, `count`, `count_distinct`) combine
multiple source rows for the same `x`/`series` pair. Aggregation is rejected for truncated
results and invalid numeric inputs.

Each successful derived visual receives a current-turn `<turn_id>:vN` identifier and stores
its `source_query_id`. The tool observation returns the derived identifier; final synthesis
cites that identifier so current-turn reconciliation, SSE rendering, audit layout, and
new-format history reload use the same presentation path.

### Raw query result contract

A `<turn_id>:qN` record is evidence, not presentation. It stores a non-renderable result
payload containing rows, columns, unit hints, completeness/truncation, SQL lineage, and
execution metadata. It has `visual_available=false`, does not emit `source_card`, and is
visible to users only as compact execution progress plus SQL/lineage in the audit drawer.

The model observation still receives bounded rows and the stable `qN` identifier so it can
choose the correct `visualize_query_result` arguments. The durable registry retains the
complete authorized result needed by the visualization tool independently of observation
truncation.

A `<turn_id>:vN` record is presentation. It references `source_query_id`, contains the
validated `ChartSpec`, has `visual_available=true`, and is the only database card emitted
to the client. Deleting `qN` is not permitted because `vN`, narrative attribution, SQL
inspection, and audit history all depend on it.

### Required execution flow

```text
query call
  -> q1 raw result stored (no card emitted)
  -> visualize_query_result(q1, chart_type/fields/aggregation chosen by model)
  -> v1 validated ChartSpec stored and emitted
  -> final synthesis cites the reconciled evidence and v1 presentation
```

If the visualization request is invalid, the tool returns a typed repairable error and the
model corrects it within the existing turn budget. If no valid presentation is produced,
the backend must not resurrect automatic inference as a fallback.

## Decisions

### Identity model

Use separate logical and physical identifiers:

```json
{
  "query_id": "<turn_id>:q1",
  "attempt_id": "<turn_id>:q1:a1"
}
```

- `query_id` identifies the logical query result that can support an answer.
- `attempt_id` identifies one execution attempt, including retries and failures.
- The backend allocates both IDs before database execution.
- IDs are opaque outside the backend. Consumers compare them for equality and never parse
  sequence numbers for business logic.
- Existing provider `tool_call_id` values remain protocol identifiers. They are stored as
  correlations, not reused as query identity.

Corrected SQL is normally a new logical query. A retry of unchanged SQL after a transient
failure keeps the logical `query_id` and receives a new `attempt_id`.

### Provenance versus presentation

Keep these concepts distinct:

- `active_query_ids`: query results that directly support claims in the narrative.
- `visual_query_ids`: the subset selected for primary visual rendering.
- `excluded_queries`: the audit view of attempted logical queries that are not active.

The frontend renders a primary card only when its ID is in `visual_query_ids`, the registry
says that it is a successful derived `vN` record, and it has a valid visual payload. Raw
`qN` records can support narrative claims but can never enter the primary visual zone.

### Authority boundaries

- The model proposes `active_query_ids` and `visual_query_ids`.
- The backend owns execution status, row counts, visual availability, and deterministic
  exclusion reasons.
- The backend reconciles the model output against the turn registry.
- The client trusts only the reconciled fields in the final answer event or stored history.

## Contracts

### Query execution record

Introduce a typed backend record, colocated with the native-agent execution contracts:

```json
{
  "query_id": "turn_123:q2",
  "attempt_id": "turn_123:q2:a1",
  "tool_call_id": "call_provider_456",
  "tool_name": "query_portfolio",
  "status": "success",
  "purpose": "answer",
  "row_count": 14,
  "has_data": true,
  "visual_available": false,
  "supersedes_query_id": "turn_123:q1",
  "duration_ms": 87,
  "error_code": null
}
```

The raw query record additionally owns a durable, non-renderable `result_payload`. A derived
visual record uses `query_id=<turn_id>:vN`, `tool_name=visualize_query_result`,
`source_query_id=<source qN>`, and `visual_available=true`.

Allowed execution statuses are `pending`, `running`, `success`, `empty`, `error`,
`timeout`, and `cancelled`. Allowed purposes initially are `answer`, `discovery`,
`validation`, and `intermediate`.

The in-memory turn registry is keyed by `query_id`, retains ordered attempts, and stores the
renderable card separately from the bounded observation sent to the model.

### Model observation

Database observations must make attribution unambiguous while retaining the existing
bounded-observation behavior in `agent_executor.py`:

```json
{
  "query_reference": {
    "query_id": "turn_123:q2",
    "attempt_id": "turn_123:q2:a1"
  },
  "status": "success",
  "summary": "14 rows returned",
  "row_count": 14,
  "data": [],
  "truncated": {}
}
```

The identifier block, status, summary, and row count are never removed by observation
shaping. SQL prompts, redundant metadata, and oversized rows may still be clipped. Errors
carry the same identity block so the model can explicitly discard or replace them.

### Final synthesis

Extend the existing Workbench answer rather than adding a parallel response type:

```json
{
  "schema_version": 1,
  "status": "answered",
  "text": "Narrative insight...",
  "active_query_ids": ["turn_123:q2"],
  "visual_query_ids": ["turn_123:v1"],
  "excluded_queries": [
    {
      "query_id": "turn_123:q1",
      "reason_code": "execution_error",
      "reason": "The first query referenced an unavailable column."
    }
  ],
  "sources": ["db"],
  "citations": [],
  "unavailable_sources": [],
  "limitations": []
}
```

Initial exclusion reason codes:

- `execution_error`
- `timeout`
- `cancelled`
- `empty_result`
- `superseded`
- `discovery_only`
- `validation_only`
- `unused_by_synthesis`
- `invalid_model_reference`
- `visual_unavailable`

Operational reason codes are derived by the backend. The model may provide a semantic
explanation for a successful but unused result, but it cannot override execution facts.

## Reconciliation algorithm

At finalization:

1. Parse the final synthesis through a strict schema. Allow at most one bounded repair.
2. Deduplicate proposed IDs while preserving their first-seen order.
3. Reject IDs absent from the current turn's registry and record the anomaly for telemetry.
4. Remove queries whose final attempt is not `success` or whose result has no data.
5. Build `active_query_ids` from the remaining valid model references.
6. Build `visual_query_ids` only from successful derived `vN` records with valid visual
   payloads. A raw `qN` can be active evidence but can never be a visual reference.
7. Derive deterministic exclusions from the complete registry, supplementing them with
   sanitized model rationale where appropriate.
8. Persist and emit the same reconciled answer object.

### Fallback rules

- Conceptual/no-tool turn: preserve empty active and visual lists.
- Missing or malformed presentation attribution never promotes `qN`. The model receives a
  bounded repair opportunity; after that the turn fails closed with no visual card.
- Multiple successful queries with no valid attribution: render no primary visuals, retain
  all results in the audit drawer, and emit an attribution anomaly metric.
- Missing presentation fields are contract errors, not a signal to render stored query cards.

## Streaming protocol

Keep progress provisional and make the final answer the atomic layout commit.

Recommended lifecycle:

```text
query_registered -> query_started -> query_completed | query_failed
answer_delta (optional narrative preview)
answer (authoritative reconciled answer)
done
```

- Query lifecycle events include `turn_id`, `query_id`, and `attempt_id`.
- Lightweight progress rows replace full interactive cards during execution.
- `answer` contains reconciled active and visual IDs.
- `done` remains last and occurs exactly once.
- Replayed or out-of-order lifecycle events must be idempotent by `attempt_id`.
- If narrative tokens continue to stream, the UI treats them as provisional until the
  authoritative `answer` event arrives.

`source_card` remains the transport for derived `vN` presentations and non-database source
cards. Raw `qN` results never use it. All compatibility handling for automatically generated
database cards is removed.

## Persistence and pre-release reset

Increment `history.RECORD_VERSION` and store the following in each turn:

- ordered query registry records and attempts;
- raw, non-renderable result payloads on `qN` records;
- cards keyed by `query_id` rather than only source/order;
- raw model attribution for audit telemetry;
- reconciled `active_query_ids`, `visual_query_ids`, and exclusions inside `answer`;
- a schema version for the answer contract.

Cutover behavior:

- Increment `history.RECORD_VERSION` for the raw-result/derived-presentation contract.
- Do not migrate automatically inferred chart cards into the new format.
- Remove legacy card-display fallbacks and field-presence inference from history readers and
  the frontend.
- Clear pre-release Workbench conversation records during deployment, or reject them as an
  unsupported record version if any remain.
- New writers never downgrade or overwrite an unknown future record version.
- Transcript replay retains raw-query and derived-presentation references in durable tool
  observations.

## Backend implementation

Primary integration points:

- `backend/app/services/workbench/agent_contracts.py`: typed query and synthesis contracts.
- `backend/app/services/workbench/agent_executor.py`: allocate/pass IDs, standardize database
  observations, and attach IDs to cards.
- `backend/app/services/workbench/agent.py`: maintain the turn registry and lifecycle events.
- `backend/app/services/workbench/prompts.py`: attribution criteria and no-query directive.
- `backend/app/services/workbench/graph.py`: structured synthesis, reconciliation, final
  answer emission, and fail-closed behavior.
- `backend/app/services/workbench/history.py`: new-format persistence, strict version
  rejection, and exact replay; no automatic-chart migration.
- `backend/app/services/workbench/streaming.py`: preserve provisional versus authoritative
  answer semantics.

Implementation requirements:

- Allocate IDs in application code before crossing the PostgreSQL MCP boundary.
- Pass IDs in MCP metadata and return them unchanged where supported.
- Preserve complete results for history while keeping model observations bounded.
- Validate all model references against the current turn only.
- Never permit a model-provided ID to retrieve a result from another user, conversation, or
  turn.
- Emit counters for reconciliation changes, repairs, and rejected references.

## Prompt and model integration

Add explicit instructions to the native-agent system contract:

- Visuals are selected strictly from the final declared references after backend validation.
- Include a query when its values directly support a claim, metric, trend, table, or chart.
- Exclude errors, timeouts, empty results, discovery/validation checks, and superseded
  queries.
- Return empty query lists for conceptual answers that used no database evidence.
- Reference only identifiers present in tool observations.

Use provider-native structured decoding where available. The Pydantic synthesis contract is
the application boundary regardless of provider support. A provider that cannot enforce the
schema receives JSON-schema prompting plus one bounded validation repair; it must never fall
back to parsing identifiers from prose.

## Frontend implementation

Primary integration points:

- `frontend/lib/api.ts`: answer, card, query-event, and history types plus defensive parsing.
- `frontend/app/workbench/page.tsx`: retain provisional query/card state and commit the
  reconciled layout on `answer`.
- `frontend/components/workbench/ExecutionTrace.tsx`: lightweight query progress.
- `frontend/components/workbench/WorkbenchTurn.tsx`: primary visual zone and background
  query drawer.

Rendering rules:

- Before `answer`, show progress only; do not mount full chart/table components.
- After `answer`, render cards whose IDs appear in `visual_query_ids`.
- Put other executed queries in a collapsed audit drawer with status, row count, reason,
  query reference, and existing lineage/SQL controls where authorized.
- An empty visual list renders no placeholder.
- On history load, require the new record version and stored reconciled lists. Reject older
  records rather than inferring visibility from missing fields.
- Preserve card order from `visual_query_ids`, not network completion order.

## Verification

### Backend tests

- Stable ID allocation and retry/correction semantics.
- Identity preservation through MCP metadata, observation shaping, persistence, and replay.
- Strict synthesis validation and bounded repair.
- Deduplication, hallucinated-ID removal, error/empty filtering, and visual intersection.
- Fail-closed missing presentation attribution and legitimate zero-query behavior.
- Parallel queries completing out of order.
- Timeout followed by retry and failed query followed by corrected logical query.
- New-format history replay and unsupported old-version rejection.
- `answer` precedes the one final `done` event.

### Frontend tests

- No full visual before the final answer.
- One, multiple, and zero active visuals.
- Visual order follows reconciled IDs.
- Failed, abandoned, and unused results appear only in the audit drawer.
- Invalid or missing visual payload does not produce a broken card.
- Reload reproduces the exact filtered state.
- Pre-release automatic-chart history is rejected or deleted rather than rendered.
- Stream interruption retains progress without promoting provisional visuals.

### End-to-end scenarios

Cover the six requested scenarios: happy path, self-healing correction, multi-query
synthesis, abandoned query, pure conversation, and hallucinated reference. Also cover
parallel completion, retry, malformed synthesis, reconnect/replay, and one visualization
derived from multiple supporting queries.

## Observability

Record per turn without logging private result rows:

- attempted, successful, active, and visual query counts;
- executed-to-active ratio;
- invalid model reference count;
- error reference filtered count;
- structured-output repair rate;
- missing-presentation repair and failure rate;
- data-bearing answer with empty attribution rate;
- successful but unused query count, segmented by purpose and tool;
- unsupported pre-release record rejection count during cutover.

Alert on any cross-turn/cross-conversation reference, sustained increases in attribution
repair, or primary-card resolution failures.

## Rollout

1. Deploy the raw `qN` result contract and visualization reader together so no result becomes
   unreadable between versions.
2. Stop emitting database `source_card` events for `qN`, while retaining lifecycle progress.
3. Require model-directed `vN` presentation and monitor visualization repair, timeout, and
   missing-presentation rates.
4. Clear pre-release Workbench history and remove every legacy-card rendering branch before
   enabling the new build. Run the cleanup as a dry run first, then apply it:
   `PYTHONPATH=backend python backend/scripts/clear_pre_release_workbench_history.py`, followed
   by the same command with `--apply` after verifying the count.
5. Canary by stable user/conversation bucket, then make the no-inference path universal.

Rollback is a deployment rollback plus clearing any pre-release Workbench history written by
the incompatible build. The frontend compatibility flag is removed rather than retained.

## Acceptance criteria

- No visual card can be selected solely by a model-invented identifier.
- A failed, timed-out, empty, or superseded query never appears in the primary visual zone.
- The same successful query has the same `query_id` in execution, observations, events,
  storage, final answers, and history reloads.
- Conceptual turns with no database execution render zero cards.
- New SQL execution alone renders no chart, KPI, or table and emits no database
  `source_card`.
- Every new user-facing database presentation has a `vN` identifier and a valid
  `source_query_id` pointing to its raw `qN` evidence.
- The backend never invokes automatic chart-shape inference on the Workbench PostgreSQL path.
- History reload produces the same primary/audit partition as the live turn.
- All required backend and frontend tests pass in off, shadow, canary, and on modes.
