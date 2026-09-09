# MoneyPal Workbench — Current Project Context

Updated: 2026-09-09
Branch: `fix/regex-removal`
Base commit: `9e1c1d3 fix(workbench): retry native tool protocol failures`
Architecture authority: `PLAN.md`; live execution ledger: `TODO.md`

## Current goal

Give the Workbench LLM agent direct access to the PostgreSQL MCP server's authorized native
read tool and the complete governed Gold-layer schema from its first request. The application
must enforce authorization, PII, catalog, SQL, cost, timeout, row-limit, and read-only boundaries
without choosing database behavior for the model or invoking a nested SQL-planning LLM.

The running application, model server, PostgreSQL MCP server, and database are on a different
machine from this workspace. This checkout can provide static and in-process validation only;
live startup, tokenizer, database, and conversation smoke checks must run on that deployment
machine.

## Implemented architecture

- `graph.run_workbench` invokes one provider-native agent loop. There is no behavioral router,
  legacy fallback, canary/shadow mode, or prose-parsed tool call.
- Backend startup loads the Gold catalog, builds/caches a deterministic complete agent schema
  block by catalog version, and attempts PostgreSQL MCP discovery and health validation.
- The stable agent prompt contains all 18 governed Gold tables, 537 catalogued columns, 8 joins,
  40 metrics, 40 dimensions, compact enums, restrictions, units, grains, PII flags, and catalog
  version. The current block is 37,624 characters; exact deployed-tokenizer measurement remains
  pending.
- The PostgreSQL MCP server advertises backend-only `postgres_health` and model-facing native
  `query(sql)`. There is no `query_gold` alias or Workbench semantic wrapper.
- The backend calls MCP `list_tools`, checks the deployment allowlist
  `POSTGRES_MCP_MODEL_TOOLS=query`, and forwards the discovered name, description, and input
  schema to the model without renaming or semantic rewriting.
- Model-facing in-process database tools were removed: `query_metrics`, `lookup_records`,
  `run_analysis`, `create_worklist`, `generate_briefing`, `run_validated_query`, and
  `inspect_loan_catalog`.
- The remaining model tools are non-database tools: `search_curated_knowledge` for concepts and
  external indexed sources, consent-gated `search_public_web`, and `finish_without_data`.
- Every model-authored SQL call is dispatched by its discovered name through PostgreSQL MCP.
  Trusted user/role/effective-source metadata is attached by the backend and is not part of model
  arguments; the MCP server independently rejects calls whose frozen policy omits `db`.
- PostgreSQL MCP validates a single read-only `SELECT` against the governed Gold catalog, applies
  PII and declared-join policy, runs the existing EXPLAIN/cost and row/statement limits, and
  executes as `nlq_readonly`.
- Structured validation, execution, timeout, transport, and unexpected tool errors return to the
  same model as tool observations while the shared round/call/deadline budget permits repair;
  there is no configuration switch that stops argument repair early.
- The frontend and Workbench request no longer expose a Direct/MCP selector or `data_access`.
  The composer shows a fixed PostgreSQL MCP label.
- Root `/health` reports cached PostgreSQL MCP discovery/readiness and cached Gold schema status
  without making network calls. Frontend LLM readiness still checks only provider `/health`
  status, once initially plus three retries; it does not inspect model names or paths.

Dedicated `/nlq`, worklist, analysis, briefing, Curiosity Graph, and optional composer-completion
services remain separate non-agent surfaces. Their existing governed database adapters were not
deleted as part of this model-tool migration.

## Safety and policy boundaries

- Role, deployment, external-consent, pin, curated-domain, and live-web authorization are frozen
  per request and rechecked immediately before execution.
- Source pins narrow the effective tool set and cannot broaden it. PostgreSQL MCP definitions are
  added only when the frozen policy includes the `db` source.
- Model tool arguments never contain trusted role or user authorization.
- SQL rejects DDL/DML, multiple statements, `SELECT *`, system or ungoverned schemas, unknown
  columns, unsafe functions, and undeclared joins.
- Complete durable tool events are retained; observations returned to the model are bounded.
- Private customer/account/staff data cannot be sent to public web tools.

## Verification completed in this checkout

- Python compilation for `backend/app` passes.
- Frontend `npx tsc --noEmit` passes.
- `git diff --check` passes.
- In-process MCP inspection exposes only `postgres_health` and `query`; the translated provider
  schema for `query` is a strict object containing required string argument `sql`.
- In-process invalid `DROP` and `SELECT *` calls return structured retryable
  `SQL_VALIDATION_ERROR` results.
- Static scans show no active Workbench registry/executor references to retired database tools;
  remaining names in history/compaction are compatibility handling for persisted old turns.
- No regression suites were added or run, per the user's instruction. Ruff is unavailable in the
  current virtual environment.

## Deployment-machine checks still required

1. Start/rebuild `postgres-mcp`, backend, frontend, and nginx on the remote deployment machine.
2. Confirm `/api/health` reports `workbench.postgres_mcp.status=ok`, tool `query`, and
   `workbench.gold_schema.status=ok` with the expected catalog version.
3. Measure the 37,624-character schema block with the deployed model tokenizer and verify enough
   headroom in the configured 32K context.
4. Capture the first real model request and confirm it contains the complete catalog-versioned
   schema and discovered `query` contract.
5. Smoke-test aggregate, record-field expansion (sanction amount and tenure/EMIs), join, ranking,
   filter, and multi-turn follow-up requests.
6. Smoke-test invalid column/join, unsafe SQL, timeout, MCP disconnect, authorization denial, and
   truncation; confirm errors return to the model for correction while budget remains.
7. Record deployed model id, prompt/catalog versions, commit, commands, latency, and outcomes in
   `TODO.md`/the rollout record.

## Known follow-up

The MCP client currently opens a bounded stateless streamable-HTTP session for discovery and each
call. A reusable managed session with bounded reconnect remains an optimization after its
lifecycle is validated against the deployed MCP transport. Correctness does not depend on it.
