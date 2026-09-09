# MoneyPal Native Tool-Calling Workbench — Project Context

Updated: 2026-09-09
Branch: `fix/regex-removal`
Base commit: `da98a64 refactor(workbench): remove regex-based agent corrections`
Authority: `plan.md`; live checklist: `TODO.md`

Phases A through E are complete. Phase F implementation is complete in the working tree and
awaits final validation. Phase G documentation is in progress. `HACKY.md` and `REGEX_PLAN.md`
are historical and are not implementation authorities.

## Architecture

Workbench has one execution path: `graph.run_workbench` invokes `agent.run` exactly once. The
provider returns native function calls; the application validates, authorizes, executes, and
records them. There is no behavioral source router, legacy orchestrator, native-to-legacy
fallback, rollout mode, percentage assignment, text-parsed tool call, or hidden text-to-SQL
shortcut.

The LLM chooses capabilities and semantic arguments from the full policy-authorized tool
schemas. Catalog retrieval supplies advisory governed metadata but does not narrow schemas,
suppress tools, choose a tool, or rewrite arguments. The compatibility `route` SSE/history
event reports sources and tool names derived from the first validated native response.

## Current implementation

- Deleted `workbench/router.py`, `workbench/orchestrator.py`, the router prompt/schema, router
  evaluators, route fixtures, and legacy orchestration tests.
- Removed agent `off`, `shadow`, and `canary` modes and their environment/configuration fields.
  Startup logs `workbench execution=native_only`.
- Replaced the routing decision type with neutral `ExecutionDecision` metadata populated from
  model-selected calls.
- Pinned sources narrow `SourceAccessPolicy.effective_sources` before tools are exposed. Role,
  deployment availability, consent, and pin policy are rechecked immediately before execution.
- Native failures end in one outcome: a typed tool observation while repair is possible, a
  refusal/clarification, or one SSE error with a stable code. Terminal codes include
  `CONTEXT_CAPACITY`, `AGENT_BUDGET_EXHAUSTED`, `AGENT_TIMEOUT`, `MODEL_UNAVAILABLE`,
  `MODEL_PROTOCOL_ERROR`, `MODEL_ERROR`, and `WORKBENCH_INTERNAL`.
- Public-web safety rejects mixed/private queries instead of silently rewriting the model's
  search argument.
- `text_to_sql.generate` always uses model SQL generation followed by governed validation.
  Automatic interest-rate, directory, ranked collection, and named-borrower SQL builders and
  their shortcut-only tests were removed. Explicit reviewed native preset tools remain.
- Full authorized enums remain in every native schema. Question-specific catalog context never
  removes a metric, dimension, filter, table, or tool.
- Record version is 7. Ordered native events are the replay authority; complete durable tool
  results are retained while model observations are bounded.
- SQL prompt version is `sql-v3-qualified-columns`; agent prompt version is
  `workbench-native-agent-v3-full-schema`.

## Safety boundaries retained

- Role, deployment, external-consent, pin, curated-domain, and live-web authorization.
- Strict closed tool schemas and Pydantic validation before execution.
- PII/outbound checks and refusal of unsafe public-search arguments.
- Catalog metric/dimension/table governance, SQL AST validation, parameter binding, row limits,
  and execution through the read-only database role.
- One shared turn budget for model rounds, tool calls, deadline, transcript capacity, and
  synthesis repair; bounded observations do not truncate durable audit history.
- Numeric claims are grounded against source facts and deterministic derived facts.

## Validation state

Implementation-time checks completed:

- Python compilation of application and scripts passed.
- Focused Ruff passed for every changed application/script file.
- The application and native Workbench modules import successfully from the project virtualenv.
- `git diff --check` passed after the implementation and documentation updates.
- Static searches found none of the retired Workbench symbols or configuration names. The
  remaining `workbench.router` spelling is FastAPI's `APIRouter` instance, not a behavioral
  router.

The offline native conversation corpus passed 24/24. Its current transcripts already contain
only the current round's nudge, so the two previously reported incorrect expectations were not
present and required no edit.

The complete backend suite was attempted but cannot be treated as a result in this environment:
macro/Qdrant tests fail while importing NumPy because `libstdc++.so.6` is unavailable, and a
later asyncio thread test stalled. The frontend build could not start because dependencies are
not installed (`next: command not found`). These environment gaps remain unchecked in Phase F7;
run them in the deployment environment or after installing its dependencies. Cross-model
comparison remains out of scope.

## Deployment and migration

This working tree is not recorded as deployed. The served model id and final commit are not yet
known and must be captured after validation. The version-7 production history migration status
is also unknown. Keep legacy `agent_exchanges` compatibility writes until that migration has run
and its rollback window has passed.

## Final commands

Run from the repository root after implementation cleanup is complete:

```bash
UV_CACHE_DIR=/tmp/moneypal-uv-cache PYTHONPATH=backend uv run --offline pytest -q \
  backend/tests/workbench/test_agent_conversations.py -p no:cacheprovider
UV_CACHE_DIR=/tmp/moneypal-uv-cache PYTHONPATH=backend uv run --offline pytest -q \
  backend/tests -p no:cacheprovider
UV_CACHE_DIR=/tmp/moneypal-uv-cache uv run --offline ruff check <changed-python-files>
git diff --check
```

Then run the native evaluator once against the deployed model and record model id,
prompt/catalog versions, commit, commands, pass counts, latency, and failure categories here.
