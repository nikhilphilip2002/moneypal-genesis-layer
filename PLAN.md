# PostgreSQL MCP-Native Workbench Plan

Updated: 2026-09-09
Branch: `fix/regex-removal`
Checklist: `TODO.md`

## 1. Goal

The Workbench LLM receives the complete governed Gold-layer schema in its stable prompt from
the first model request and receives the PostgreSQL MCP server's own authorized tools through
MCP discovery. The main agent calls those MCP tools directly, sees their result or structured
error, and decides whether to retry, call a non-database source, clarify, refuse, or answer.

The model-facing tool boundary will be:

- the read-only tools advertised by the configured PostgreSQL MCP server: the only tools that
  access the loan-book PostgreSQL database;
- `search_curated_knowledge`: non-database concepts, macro, competitive, and regulatory data;
- `search_public_web`: live public information;
- `finish_without_data`: clarification or governed refusal.

The application continues to own authorization and safety. Giving the LLM control of SQL and
tool selection does not give it permission to bypass role policy, PII controls, the Gold
allowlist, SQL validation, cost limits, timeouts, row limits, or read-only execution.

## 2. Baseline findings before Phase I

- The Workbench model currently receives locally defined native tools, not tools discovered
  from the PostgreSQL MCP server.
- `query_metrics`, `lookup_records`, `run_analysis`, `create_worklist`, `generate_briefing`, and
  `run_validated_query` execute through in-process database services and ignore MCP mode.
- The current PostgreSQL MCP server exposes `postgres_health`, `ask_loan_book`, and
  `curiosity_graph`. It does not expose a validated Gold SQL execution primitive.
- `ask_loan_book` invokes the older NLQ planning pipeline, so exposing it to the main agent
  would create a nested-agent path and take SQL control away from the Workbench model.
- The initial Workbench prompt contains only question-retrieved catalog hints. Tool schemas
  expose all metric, dimension, and table identifiers, but the model does not initially receive
  all 537 columns and all declared joins.
- The frontend Direct/MCP selector sends `data_access`, but normal native database tools bypass
  that selection.

## 2.1 Implementation status

The initial Phase I vertical slice is implemented in the working tree:

- the internal FastMCP PostgreSQL server advertises only backend `postgres_health` and the
  model-facing native `query(sql)` tool;
- the backend discovers and validates that tool through MCP `list_tools`;
- the Workbench agent receives discovered MCP definitions plus non-database tools;
- all locally defined Workbench database tools and executor handlers are removed;
- the complete compact Gold schema is cached at backend startup and included in the stable agent
  system prefix (37,624 characters, approximately 9.4K tokens by the provisional characters/4
  estimate; deployed-tokenizer measurement remains required);
- active Workbench API/frontend `data_access` selection is removed and replaced with a read-only
  PostgreSQL MCP status label.

The root `/health` response reports the cached MCP discovery state and cached Gold schema version
without performing network I/O. Remaining work includes a reusable MCP session,
deployed-tokenizer measurement, live container/database smoke validation on the deployment
machine, and final operational evidence.

## 3. Target architecture

```text
Backend startup
  -> load and validate the governed Gold catalog
  -> build one immutable, catalog-versioned Gold schema prompt
  -> initialize PostgreSQL MCP and discover its tool contracts with list_tools
  -> cache the schema prefix and model-facing MCP definition
  -> optionally warm the local LLM's stable prompt prefix

Workbench turn
  -> LLM receives stable instructions + complete Gold schema + authorized tools
  -> LLM calls an authorized PostgreSQL MCP tool using its native contract
  -> PostgreSQL MCP authorizes, bounds, and executes the operation
  -> result or structured error returns to the same LLM
  -> LLM retries within the existing turn budget or writes the final answer
```

The LLM endpoint is stateless: schema initialization means building and caching an identical
system-prompt prefix at backend startup and including it in every model request. It does not
mean uploading schema state permanently into the model. A startup warm-up may populate the
llama.cpp KV/prompt cache, but correctness must never depend on that cache surviving.

## 4. PostgreSQL MCP access

### 4.1 Expose the MCP server's native tools

Do not create a local semantic wrapper such as `query_gold`. During backend startup, connect to
the configured PostgreSQL MCP endpoint, call `list_tools`, and retain the server's exact tool
names, descriptions, and input schemas. Translate those discovered contracts only as required by
the LLM provider's native function-calling format; do not rename them or change their semantics.

The selected PostgreSQL MCP implementation must advertise enough read-only capability to execute
SQL against the Gold schema. Schema metadata is already supplied in the first model request, so
the current server intentionally advertises one model-facing native tool, `query(sql)`. Its exact
description and input schema come from MCP discovery; `POSTGRES_MCP_MODEL_TOOLS=query` is the
deployment authorization allowlist, not a locally renamed wrapper. If the MCP implementation is
replaced, update that allowlist to the replacement server's actual safe read-tool names.

Only safe read capabilities discovered from this server may be exposed to the model. The MCP
server and database role, not a model-facing Workbench wrapper, must enforce that they:

- accept exactly one `SELECT` statement;
- allow only catalogued `gold.*` tables and columns;
- reject DDL, DML, multiple statements, `SELECT *`, system schemas, and ungoverned schemas;
- validate aliases, scopes, CTEs, subqueries, unions, functions, and declared joins;
- apply role and PII policy received from trusted backend context rather than model arguments;
- connect only as `nlq_readonly`;
- run the existing `EXPLAIN`/cost gate before reading rows;
- apply the statement timeout and maximum row limit;
- return structured metadata or query results through the native MCP result contract;
- return validation, policy, timeout, transport, and execution failures as structured errors.

Do not let the model supply its own user or role. The backend attaches authenticated identity and
the frozen effective-source policy as trusted MCP request metadata. The MCP server independently
rejects `query` unless that metadata authorizes the `db` source.

### 4.2 Existing MCP tools

- Keep `postgres_health` for backend readiness and diagnostics; do not expose it to the LLM.
- Remove `ask_loan_book` from the MCP server because it invokes the nested legacy NLQ planner.
- Remove `curiosity_graph` from the MCP server; the standalone graph keeps its dedicated API and
  is not a Workbench model tool.

### 4.3 MCP client lifecycle

Update `backend/app/mcp/postgres_client.py` to initialize MCP during application startup, call
`list_tools`, filter the discovered tools through the configured read-only allowlist and source
policy, and reuse a managed session where supported. Per-call reconnect remains a fallback, not
the normal path. Transport failures must become typed, retryable tool observations.

## 5. Gold schema available from the first model request

Build a compact, complete, deterministic projection containing:

- every qualified Gold table name, description, grain, restriction, and coverage warning;
- every governed column name, business label, unit, and PII classification;
- all declared joins, key pairs, direction, cardinality, and caveats;
- every governed metric with formula, unit, grain, base table, and physical dependencies;
- every dimension with its table/column mapping and type;
- compact governed enum values needed to write filters;
- the catalog version.

Do not insert the current verbose YAML unchanged. Create a deduplicated agent schema block that
leaves sufficient room in the 32K context for tool definitions, conversation history, results,
and the answer. Cache it by catalog version during backend startup.

Move this block into the stable system prefix in
`backend/app/services/workbench/prompts.py`. Question-specific retrieval may remain as a short
relevance hint, but it must not determine which schema definitions the model is allowed to see.

## 6. Model-facing tool cleanup

Remove these database tools from `AGENT_TOOLS` and from the Workbench executor dispatch table:

- `query_metrics`
- `lookup_records`
- `run_analysis`
- `create_worklist`
- `generate_briefing`
- `run_validated_query`
- `inspect_loan_catalog`

Do not immediately delete their underlying domain services: dedicated non-chat APIs or UI pages
may still use them. First remove them only from the Workbench agent path, then delete code proven
unreachable in a separate cleanup step.

Add the authorized tool definitions returned by PostgreSQL MCP discovery to the model's tool
list without introducing local database tool names. Keep `search_curated_knowledge`, but remove
its `schema` domain because schema is supplied in the stable prompt and database access belongs
exclusively to PostgreSQL MCP. Keep `search_public_web` and `finish_without_data`.

Pinned-source and consent policy may narrow the available tools. A loan-book-only turn should
expose the authorized read-only PostgreSQL MCP tools and `finish_without_data`.

## 7. Agent execution and retry behavior

Update the executor so every discovered PostgreSQL MCP tool dispatches by its original name and
arguments through the PostgreSQL MCP client. Remove direct calls from the Workbench agent to
governed metric/record execution and the legacy local SQL-generation workflow.

Return all recoverable MCP failures to the same model as structured tool observations containing:

- stable error code;
- safe human-readable message;
- relevant table/column/join details when safe;
- retryability;
- MCP call reference.

The existing round, tool-call, request-deadline, cancellation, authorization, and context limits
remain hard boundaries. A failed query does not end the turn while a safe correction is possible
within those limits.

## 8. API and frontend cleanup

Remove `data_access` from the Workbench request, graph state, agent execution context, frontend
API client, and page state. Remove the Direct adapter/MCP selector from the Composer. Production
deployment configuration determines the PostgreSQL boundary.

The UI may display read-only connection status such as `Loan book - PostgreSQL MCP`; it must not
offer a path that bypasses the required MCP boundary.

Keep the existing frontend LLM `/health` readiness check status-only. PostgreSQL MCP readiness is
a backend responsibility and should be reported through backend health/diagnostic metadata, not
through frontend model-name checks.

## 9. Migration sequence

1. Select or configure the PostgreSQL MCP server and inspect its native tools with `list_tools`.
2. Add backend startup catalog initialization and the compact stable schema prefix.
3. Add MCP initialization, read-only tool filtering, contract validation, and generic MCP dispatch.
4. Expose the discovered PostgreSQL MCP tools alongside existing tools temporarily and verify
   result/error replay.
5. Remove all model-facing in-process database tools and their executor handlers.
6. Narrow non-database tool domains and verify role, consent, and pin filtering.
7. Remove `data_access` and the frontend connection selector.
8. Retire the nested `ask_loan_book` Workbench path and remove unreachable adapters.
9. Update architecture documentation and deployment configuration.
10. Perform focused static checks and live smoke validation. Do not add or run the deferred
    regression suite unless the user re-enables it.

At every step, update `TODO.md` immediately: mark an item complete only after its code change and
focused verification are complete, record blockers explicitly, and keep this plan synchronized
when the implementation design changes.

## 10. Acceptance criteria

- The first Workbench model request contains the complete compact Gold schema.
- The Workbench model receives only database tools discovered from the configured PostgreSQL MCP
  server; it receives no locally defined database tools.
- The main model uses the MCP server's native query capability; no nested planner or
  SQL-generating LLM runs for the call.
- No model-initiated Workbench database request executes through the API process's direct
  adapter. Dedicated non-chat APIs and optional composer completions remain separate migration
  scopes until explicitly retired or moved behind MCP.
- Every SQL statement is validated and executed inside the PostgreSQL MCP boundary as
  `nlq_readonly`.
- Recoverable validation and execution errors return to the same model for correction.
- Non-database tools access only their declared sources.
- The frontend no longer lets users choose a direct PostgreSQL path.
- Audit lineage records model SQL, validated SQL, catalog version, MCP tool call, tables, duration,
  returned-row count, truncation, and errors.
- Representative single-turn and follow-up smoke scenarios succeed against the deployed model.

## 11. Living-document rule

`PLAN.md` is the architectural authority and `TODO.md` is the execution ledger. Implementation
work must update both in the same change whenever scope, sequencing, contracts, or completion
state changes. A checkbox is not evidence by itself; the corresponding code and focused
verification must exist before it is checked.
