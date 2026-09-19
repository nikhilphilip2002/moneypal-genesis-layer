# Workbench Query Attribution and Visual Reconciliation Plan

## Purpose

Make every database-backed Workbench answer explicitly declare which query results support
the final narrative, then let the backend validate that declaration before the frontend
renders any full visual cards.

The execution registry is the source of truth. The model may nominate query references, but
it cannot create, validate, or authorize them. The final answer event carries the reconciled
references, and conversation history preserves that exact resolved state.

## Outcomes

- Every database query attempt has a stable identity before execution begins.
- Query identity survives execution, model observations, SSE events, persistence, reload,
  and rendering.
- The final model response follows a strict structured contract.
- Only successful, data-bearing, explicitly used results appear in the primary visual zone.
- Failed, empty, superseded, and unused queries remain available in a compact audit trail.
- Conceptual answers produce no empty visual placeholders.
- Old conversation records remain readable.

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

The frontend renders a primary card only when its ID is in `visual_query_ids` and the
registry says that it has a valid visual payload. This prevents a cited scalar or diagnostic
result from being forced into a chart.

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
  "visual_available": true,
  "supersedes_query_id": "turn_123:q1",
  "duration_ms": 87,
  "error_code": null
}
```

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
  "visual_query_ids": ["turn_123:q2"],
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
6. Build `visual_query_ids` by intersecting the proposed visual IDs with active IDs and
   registry entries that contain a valid visual payload.
7. Derive deterministic exclusions from the complete registry, supplementing them with
   sanitized model rationale where appropriate.
8. Persist and emit the same reconciled answer object.

### Fallback rules

- Conceptual/no-tool turn: preserve empty active and visual lists.
- One-query compatibility fallback: infer the only successful, data-bearing query only if
  structured attribution is missing or malformed, the query purpose is `answer`, and the
  answer contains data-derived content. Do not override an explicit valid empty list.
- Multiple successful queries with no valid attribution: render no primary visuals, retain
  all results in the audit drawer, and emit an attribution anomaly metric.
- Missing historic fields: display all successful historic cards, matching current behavior.

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

For compatibility, `source_card` can continue during the flag-controlled rollout, but the
client must retain it without mounting the full visualization until final reconciliation.

## Persistence and migration

Increment `history.RECORD_VERSION` and store the following in each turn:

- ordered query registry records and attempts;
- cards keyed by `query_id` rather than only source/order;
- raw model attribution for audit telemetry;
- reconciled `active_query_ids`, `visual_query_ids`, and exclusions inside `answer`;
- a schema version for the answer contract.

Migration/read behavior:

- Existing records with no attribution fields are marked legacy at read time.
- Legacy turns expose all successful stored cards as active and visual.
- Do not fabricate query IDs into old persisted JSON merely to render it.
- New writers never downgrade or overwrite an unknown future record version.
- Transcript replay retains query references in durable tool observations.

## Backend implementation

Primary integration points:

- `backend/app/services/workbench/agent_contracts.py`: typed query and synthesis contracts.
- `backend/app/services/workbench/agent_executor.py`: allocate/pass IDs, standardize database
  observations, and attach IDs to cards.
- `backend/app/services/workbench/agent.py`: maintain the turn registry and lifecycle events.
- `backend/app/services/workbench/prompts.py`: attribution criteria and no-query directive.
- `backend/app/services/workbench/graph.py`: structured synthesis, reconciliation, final
  answer emission, and fallback behavior.
- `backend/app/services/workbench/history.py`: record-version migration and exact replay.
- `backend/app/services/workbench/streaming.py`: preserve provisional versus authoritative
  answer semantics.

Implementation requirements:

- Allocate IDs in application code before crossing the PostgreSQL MCP boundary.
- Pass IDs in MCP metadata and return them unchanged where supported.
- Preserve complete results for history while keeping model observations bounded.
- Validate all model references against the current turn only.
- Never permit a model-provided ID to retrieve a result from another user, conversation, or
  turn.
- Emit counters for reconciliation changes and fallbacks.

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
- On history load, use stored reconciled lists. Apply the legacy fallback only when the
  fields are absent, not when they are explicitly empty.
- Preserve card order from `visual_query_ids`, not network completion order.

## Verification

### Backend tests

- Stable ID allocation and retry/correction semantics.
- Identity preservation through MCP metadata, observation shaping, persistence, and replay.
- Strict synthesis validation and bounded repair.
- Deduplication, hallucinated-ID removal, error/empty filtering, and visual intersection.
- Conservative single-query fallback and legitimate zero-query behavior.
- Parallel queries completing out of order.
- Timeout followed by retry and failed query followed by corrected logical query.
- History migration and unknown-version protection.
- `answer` precedes the one final `done` event.

### Frontend tests

- No full visual before the final answer.
- One, multiple, and zero active visuals.
- Visual order follows reconciled IDs.
- Failed, abandoned, and unused results appear only in the audit drawer.
- Invalid or missing visual payload does not produce a broken card.
- Reload reproduces the exact filtered state.
- Legacy history still displays successful cards.
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
- single-query fallback rate;
- data-bearing answer with empty attribution rate;
- successful but unused query count, segmented by purpose and tool;
- history fallback usage by record version.

Alert on any cross-turn/cross-conversation reference, sustained increases in attribution
repair, or primary-card resolution failures.

## Rollout

1. Add contracts, registry, persistence fields, reconciliation, and telemetry with rendering
   behavior unchanged.
2. Run attribution in shadow mode and compare proposed, reconciled, and currently displayed
   cards.
3. Enable deferred visual rendering and audit drawer behind a frontend flag for internal
   users.
4. Canary by stable user/conversation bucket and monitor correctness plus latency.
5. Make reconciled rendering the default while keeping the legacy-history read fallback.
6. Remove compatibility `source_card` rendering only after supported clients consume query
   lifecycle and final attribution fields.

Immediate rollback is the frontend filtering flag. Backend IDs and persisted attribution are
additive and remain safe to collect during rollback.

## Acceptance criteria

- No visual card can be selected solely by a model-invented identifier.
- A failed, timed-out, empty, or superseded query never appears in the primary visual zone.
- The same successful query has the same `query_id` in execution, observations, events,
  storage, final answers, and history reloads.
- Conceptual turns with no database execution render zero cards.
- History reload produces the same primary/audit partition as the live turn.
- All required backend and frontend tests pass in off, shadow, canary, and on modes.
