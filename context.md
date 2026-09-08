# MoneyPal LLM-Controlled Workbench — Project Context

Updated: 2026-09-08  
Branch: `fix/regex-removal`  
Working directory: `/home/null/Projects/moneypal`

## Project intent

The Workbench is being changed from phrase-specific application routing and one-shot LLM
planning into a bounded, provider-native tool-calling agent. The local LLM—Ling or Qwen—is the
semantic controller. It interprets the question and conversation, chooses one or more tools,
supplies complete arguments, sees every complete tool result or error, repairs its own calls,
and decides when to answer, clarify, or refuse.

The application remains the security and execution boundary. It determines which tools are
visible, validates typed arguments, enforces authorization and PII rules, validates generated
SQL through its AST, limits time/rows/rounds/tool calls, runs read-only operations, and persists
the conversation. Application code must not silently add a requested grouping, rewrite the
period, merge a follow-up through a question-specific rule, or turn assistant prose/JSON into
an executable tool call.

Provider-native function arguments are necessarily JSON objects. That is permitted. What is
prohibited is asking the assistant to print JSON in ordinary assistant content and parsing it
as a fallback tool call. The design also rejects a polymorphic `oneOf` mega-tool because it is
unreliable with llama-server and smaller local models. The exposed capabilities are separate,
flat, strict native functions.

The two production regressions driving this work are:

1. `interest collected schemewise` returned a single all-time total because the model's missing
   grouping was not corrected through a real agent loop.
2. `customers under vanitha` followed by `include tenure and sanctioned amount with the above
   details` lost the prior agent constraint/result context and generated a wrong-table column.

## Completed

### Agent control and tool execution

- Implemented a bounded LLM → native tool → complete result → LLM continuation loop.
- The LLM can call multiple authorized tools sequentially and synthesize a final response from
  all results. A regression test covers metric lookup followed by curated knowledge lookup.
- Successful results return to the model with `tool_choice="auto"`; the model chooses another
  tool or answers.
- Execution errors return to the model as typed tool observations. The model can select a
  different tool or make a corrected call.
- Invalid arguments emitted during a continuation are persisted as the exact assistant tool
  call plus an `INVALID_TOOL_ARGUMENTS` tool result, then replayed for another bounded model
  round.
- Hard controls remain outside the LLM: role/source policy, external consent, outbound PII
  policy, strict Pydantic contracts, shared deadline, maximum rounds, maximum calls, row limits,
  read-only database access, and SQL validation.
- No assistant-content JSON fallback was added. Native provider tool calls remain mandatory.

### Concrete native tool surface

The current agent registry exposes separate, flat tools:

- `query_metrics`
- `lookup_records`
- `run_validated_query`
- `inspect_loan_catalog`
- `run_analysis`
- `create_worklist`
- `generate_briefing`
- `search_curated_knowledge`
- `search_public_web`
- `finish_without_data`

`inspect_loan_catalog` is newly implemented. It is metadata-only and returns relevant governed
metrics, dimensions, tables, columns, synonyms, enum values, coverage warnings, and declared
joins. It never returns customer or loan rows. Its schema is flat and catalog table names are
injected as an enum at runtime.

### Removal of semantic application rewrites

- Removed the month/period regex canonicalizer from the native agent. The application no
  longer adds `month`, changes ordering, or rewrites conflicting/all-time periods after the
  model generates a call.
- Invalid period combinations now enter native repair instead of being silently mutated.
- The agent's `run_validated_query` path now calls text-to-SQL with
  `allow_reviewed_shortcuts=False`, preventing the legacy phrase-specific deterministic SQL
  helpers from taking control away from the native agent. Legacy callers retain compatibility.
- Scheme vocabulary was added to the governed catalog: `scheme wise`, `schemewise`, and
  `by scheme`.
- A live Ling selection probe previously confirmed that `interest collected schemewise`
  produced `query_metrics(metrics=[interest_collected], dimensions=[scheme])` without a
  scheme-specific application mutation.

### Complete results and conversation history

- Native tool replay now includes the complete card payload and all returned rows, plus summary,
  completeness, limitations, citations, evidence, facts, and lineage.
- New turns store an ordered `events` sequence beginning with the exact user message.
- Native assistant messages, exact calls, complete results/errors, route decisions, rendered
  cards, synthesis, final answers, refusals, and execution errors are recorded as events.
- Native transcript reconstruction now reads native messages/results from this ordered event
  stream. It uses `agent_exchanges` only as read compatibility for older stored records.
- Silent loss of an oversized native exchange was removed. If exact replay does not fit and
  explicit compaction cannot preserve it, `NativeTranscriptOverflow` is raised.
- Provider `reasoning_content`, when present, is retained in assistant messages.
- An exact regression stores and replays `customers under vanitha`, its lookup arguments, all
  30 test rows, SQL lineage, and bound agent-name parameter to the next turn.
- Named record lookups are no longer forced through the legacy mandatory-preflight route, so
  their native calls/results become part of the model-visible transcript.

### Nested generated-query visibility and SQL safety

- Each non-deterministic text-to-SQL attempt now records the request messages, assistant
  response, model/provider, candidate SQL, validation result, rejection reason, and validated
  SQL for every generation/repair round.
- That trace is attached to the `run_validated_query` tool result lineage, so the controlling
  LLM receives it with the SQL result instead of seeing only a rendered card.
- SQL AST validation now checks unqualified columns against the tables actually referenced by
  the statement. It rejects a column that exists in another Gold view but not the chosen view.
- It also rejects an unqualified column that is ambiguous across multiple joined views.
- This blocks the observed `disbursement_amount`-against-`semantic_loan_account` failure before
  PostgreSQL execution.

### Evaluation assets and verification completed so far

- Expanded the native-agent corpus from 108 to 120 unique prompts.
- The corpus covers every governed Gold view and gives each intent three paraphrases.
- Added dedicated interest-collected families for month, scheme, branch, and product grouping.
- Evaluation compares exact native tool names and structured arguments; it does not use regex
  to declare success or repair a model output.
- Confirmed before the latest trace/catalog additions: 204 focused tests passed.
- Confirmed after adding the catalog tool and removing semantic regex mutation: 67 agent,
  history, tool-contract, and executor tests passed.
- Confirmed after expanding the corpus: all 5 static 120-question corpus integrity/retrieval
  tests passed.
- Ruff and `git diff --check` had passed before the latest additions; they must be rerun.

## In Progress

### One fully unified history representation

The ordered event stream is now authoritative for native transcript replay, but consolidation
is incomplete:

- route-stage LLM responses are not yet persisted/replayed as first-class LLM events;
- some mandatory preflight and legacy paths still persist only rendered cards rather than the
  exact internal LLM/tool exchange;
- compatibility writes to `agent_exchanges` remain while old stored conversations exist;
- nested SQL trace is carried inside parent tool lineage rather than represented as separately
  addressable ordered events;
- final removal of split legacy/native history requires a storage migration and compatibility
  decision.

### Full model-visible repair coverage

- Initial invalid selection receives one native repair and is now persisted when a durable turn
  exists.
- Invalid continuation calls are model-visible and retryable.
- Generic execution failures can trigger cross-tool recovery.
- Remaining edge cases to test include unknown/forged continuation tool names, exhausted shared
  budgets, multiple invalid calls in one response, and exact provider behavior when a local
  model emits malformed native arguments.

### Ling and Qwen evaluation

- The reusable evaluator exists at `backend/scripts/evaluate_native_agent.py`.
- It records prompt, expected capability, native calls, response model, duration, pass/fail,
  and failure reason.
- The current corpus has 120 prompts. The identical corpus must be run against both models.
- Ling was probed for the scheme-wise regression, but a full 120-case report has not been run
  after the latest architecture changes.
- Qwen cannot be evaluated until the endpoint is actually serving its model identifier. Passing
  a Qwen name to the evaluator does not load or switch the server model.

### Verification after the latest edits

The latest combined focused test command was interrupted, so it must not be reported as a full
pass. No production containers have been rebuilt from the current uncommitted worktree.

## To Do

1. Persist route-stage LLM responses and their capability-selection observations without
   creating an invalid provider transcript.
2. Route mandatory preflight/remaining legacy execution through the same ordered event model,
   or explicitly retain only the deterministic saved-query/dashboard exceptions.
3. Decide and implement the stored-conversation migration that eventually removes
   `agent_exchanges` compatibility writes.
4. Add the complete Vanitha two-turn behavioral test: the second native call must retain the
   agent constraint and borrower identity fields while adding `number_of_emis` and
   `sanction_amount`.
5. Add model-loop cases for changing/removing filters, changing periods, drilling from an
   aggregate to accounts, misspelled `santioned`, and generated-SQL rejection followed by
   model-directed correction.
6. Verify that every generated-query table/column/join is limited to the catalog projection
   chosen for the tool call and return exact AST validation failures to the model.
7. Run Ruff, formatting checks, `git diff --check`, focused suites, then the complete backend
   test suite.
8. Run all 120 cases against the currently served Ling model and save the JSON report.
9. Serve Qwen on the configured endpoint, verify `/v1/models`, run the identical 120 cases,
   and compare failure categories and latency.
10. Improve only general system instructions, tool descriptions, and governed catalog
    vocabulary based on those reports. Do not add question-specific behavioral regex.
11. Verify `.env` and `.env.prod` remain ignored. Never stage or print their secrets.
12. Commit only task-owned files, push, rebuild `backend` and `postgres-mcp`, then repeat the
    production scheme-wise and Vanitha conversations end to end.

## Edited files in the current worktree

### Documentation

- `plan.md` — replaced the abstract plan with the implementation architecture and current
  status; updated again for this handoff.
- `TODO.md` — implementation checklist and earlier progress snapshot.
- `context.md` — this complete continuation handoff.
- `NLQ_LLM_HANDOFF.md` — intentionally deleted because the user requested replacing the old
  handoff with the new plan/context documents.

### Runtime code

- `backend/app/services/workbench/agent.py` — multi-tool continuation loop, model-visible
  execution/argument errors, history persistence, removal of semantic regex mutation.
- `backend/app/services/workbench/agent_contracts.py` — flat `InspectLoanCatalogArguments`.
- `backend/app/services/workbench/agent_tools.py` — catalog inspection registry/schema,
  permission filtering, and validation.
- `backend/app/services/workbench/agent_executor.py` — full result replay, catalog inspection
  handler, nested SQL trace exposure, and legacy shortcut disabling for native calls.
- `backend/app/services/workbench/history.py` — version-6 ordered events, lossless native replay,
  explicit overflow behavior, and event-based transcript reconstruction.
- `backend/app/services/workbench/graph.py` — native transcript overflow propagation and use of
  the model-controlled final result.
- `backend/app/services/workbench/router.py` — named record lookups remain on the native path.
- `backend/app/services/nlq/llm/client.py` — preserves provider reasoning content.
- `backend/app/services/nlq/text_to_sql.py` — optional legacy-shortcut gate and nested generation/
  validation trace.
- `backend/app/services/nlq/validator.py` — referenced-table-aware unqualified-column checks.
- `backend/app/services/nlq/catalog/defs/gold/dimensions.yaml` — genuine scheme-wise vocabulary.

### Tests and evaluation corpus

- `backend/tests/workbench/test_agent.py`
- `backend/tests/workbench/test_agent_executor.py`
- `backend/tests/workbench/test_agent_tools.py`
- `backend/tests/workbench/test_history.py`
- `backend/tests/workbench/test_prompts.py`
- `backend/tests/workbench/test_router.py`
- `backend/tests/workbench/test_agent_questions.py`
- `backend/tests/workbench/golden/agent_questions.yaml`
- `backend/tests/nlq/test_validator.py`

### Files deliberately not owned by this implementation

- `HACKY.md` and `REGEX_PLAN.md` are untracked user-provided audit/plan documents. They were
  read for context but must remain untouched and must not be included in a task commit unless
  the user explicitly requests it.
- `.env` and `.env.prod` contain production configuration and secrets. They remain ignored and
  must never be staged, committed, or printed.

## Safe continuation commands

Run the fast architectural suites first:

```bash
PYTHONPATH=backend UV_CACHE_DIR=/tmp/moneypal-uv-cache uv run pytest -q \
  backend/tests/workbench/test_agent.py \
  backend/tests/workbench/test_agent_executor.py \
  backend/tests/workbench/test_agent_tools.py \
  backend/tests/workbench/test_history.py \
  backend/tests/workbench/test_prompts.py \
  backend/tests/workbench/test_router.py \
  backend/tests/workbench/test_orchestrator.py \
  backend/tests/nlq/test_validator.py
```

Run the corpus integrity suite separately because catalog retrieval makes it slower:

```bash
PYTHONPATH=backend UV_CACHE_DIR=/tmp/moneypal-uv-cache uv run pytest -q \
  backend/tests/workbench/test_agent_questions.py
```

Then run Python lint and patch hygiene:

```bash
PYTHONPATH=backend UV_CACHE_DIR=/tmp/moneypal-uv-cache uv run ruff check \
  backend/app/services/workbench/agent.py \
  backend/app/services/workbench/agent_contracts.py \
  backend/app/services/workbench/agent_executor.py \
  backend/app/services/workbench/agent_tools.py \
  backend/app/services/workbench/graph.py \
  backend/app/services/workbench/history.py \
  backend/app/services/workbench/router.py \
  backend/app/services/nlq/llm/client.py \
  backend/app/services/nlq/text_to_sql.py \
  backend/app/services/nlq/validator.py
git diff --check
```

Do not run the live evaluator concurrently against the single local llama-server. Confirm the
served model through `/v1/models`, then run one model at a time. The evaluator is read-only and
does not execute warehouse queries:

```bash
PYTHONPATH=backend python -m scripts.evaluate_native_agent \
  --output /tmp/ling-native-agent.json
```

Use `--model <served-qwen-model-id>` only after the endpoint reports that exact Qwen model.

## Repository state and commit warning

The current implementation is uncommitted. The last visible commit before these edits was
`41b3d8ac docs: record NLQ production regressions`. Do not commit or push until the interrupted
verification is rerun and the remaining intended scope is agreed. When committing, exclude
`HACKY.md`, `REGEX_PLAN.md`, `.env`, and `.env.prod` unless the user explicitly changes that
instruction.
