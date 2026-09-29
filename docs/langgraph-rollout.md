# Workbench LangGraph rollout

Workbench uses LangGraph for all turns. The previous orchestration loop and engine selection setting have been removed. The graph uses the existing model client, MCP tools, API/SSE events, and final-answer renderer. Successful database-backed turns require validated final submission; missing or invalid submission triggers bounded finalization, then an explicit error if recovery fails. Plain-text and external-source answers retain their existing paths.

## Storage

Production defaults to `WORKBENCH_HISTORY_REQUIRE_DURABLE=true`. PostgreSQL history must be reachable. Initialization adds a `revision bigint NOT NULL DEFAULT 0` column to `public.workbench_conversations`; existing version 9 conversation records remain supported. Revision checks reject stale writes and ownership changes. Same-conversation requests are serialized using locks under the existing shared `NLQ_LLM_LOCK_PATH` parent directory. All API workers must share that filesystem, as the current Docker Compose services do.

The final answer is saved before its authoritative SSE event is emitted. Network delivery may still be interrupted; reloading the conversation recovers the saved answer. Graph nodes are not automatically resumed after a process restart. Existing durable conversation history provides memory between turns.

`WORKBENCH_HISTORY_CACHE_ENTRIES=32` and `WORKBENCH_HISTORY_CACHE_BYTES=33554432` bound cached records and replay by entry count and serialized byte size; Python object overhead is additional. Each read checks the database revision and timestamp. Cache misses, eviction, and backend restarts reload durable history. `WORKBENCH_HISTORY_REQUIRE_DURABLE=false` is available for isolated development/tests; its memory fallback does not survive restart or eviction.

## Model cache

`LLAMA_PROMPT_CACHE_ENABLED=true` explicitly sends `cache_prompt=true` and `id_slot=LLAMA_SLOT_ID`. Disable it for a server that does not accept llama.cpp request extensions. Keep the current server `--parallel 1 --cache-prompt` configuration on constrained hardware and the shared model request lock for all callers.

The full governed schema remains cached by catalog version. Final model request context is retained for replay, including catalog hints and native messages, to preserve the common prompt prefix across follow-ups. Compaction continues to retain full historical events while reducing model context. Its model requests now count against the turn budget.

`LLAMA_SLOT_SNAPSHOTS_ENABLED=false` remains the default until actual reuse is verified on the deployed model/server. When enabled, each model request restores its own conversation snapshot, calls the model, then saves under the shared gate. This prevents a per-turn initialization flag from incorrectly assuming the slot still belongs to that conversation after other work runs.

Snapshot names incorporate owner, conversation, endpoint, model, prompt, tool schema, context size, reasoning replay setting, and `LLAMA_CACHE_EPOCH`. Change `LLAMA_CACHE_EPOCH` when deploying new model weights, tokenizer, template, or incompatible server/cache configuration under the same model name. Catalog or prompt changes naturally produce new identities.

Before enabling disk snapshots, configure the private llama-server snapshot directory with a filesystem quota and a host retention job. Expiring a snapshot must only cause a cold request; it does not delete conversation history. Snapshot files are on the model server, so the API cannot enforce their disk retention. Measure snapshot save/restore overhead as well as cached tokens before enabling this on slow disks.

## Verification

Install synchronized dependencies using the project's normal `uv sync --locked` or container build. LangGraph is pinned to 1.2.12 in both dependency manifests.

Run the critical regressions:

```bash
.venv/bin/python -m pytest backend/tests/workbench/test_agent.py backend/tests/workbench/test_workflow.py backend/tests/workbench/test_history_cache.py backend/tests/workbench/test_graph.py backend/tests/nlq/test_slot_cache.py backend/tests/nlq/test_llm_client.py -q
RUN_HISTORY_POSTGRES_TESTS=1 .venv/bin/python -m pytest backend/tests/workbench/test_history_postgres.py -q
```

The PostgreSQL integration test creates a session-local temporary table and checks reload, cached reads, conflicting revisions, and ownership protection.

With a deployed API and model reachable, set `WORKBENCH_API_TOKEN` and run:

```bash
.venv/bin/python -m backend.scripts.verify_workbench_cache --base-url http://localhost:8000 --output /tmp/workbench-cache-report.json --require-cache-hits
```

This performs an initial database question, a follow-up, another conversation, and a return to the first conversation. It writes timing and token-usage results without answer rows. A positive cached-token count is only a minimum smoke check: inspect per-call counts and server prefill logs to confirm reuse of most of the eligible schema/history prefix. Compare cold/warm runs, compaction, cache-epoch changes, and returning to saved conversations after a server restart. Measure memory and snapshot disk usage on the target host.

Run the existing `scripts.verify_workbench_rollout` smoke test for source permissions, tool contracts, and representative answers, and verify query/chart rendering and cancellation in the browser. The graph's forced named tool choice must be exercised against the actual model and chat template before production rollout.

If final rendering, history replay, or latency regresses, redeploy the previous application release. Keep the additive history column. Older application binaries will ignore request-context events and can lose the prompt-prefix performance improvement; retained native exchanges and full history remain available.

## Verification status during implementation

The configured LLM endpoint was unreachable. Live named-tool enforcement, prompt/KV cache hit rate, restart snapshot reuse, and target-hardware latency remain unverified. Snapshots have not been enabled and no deployment has been performed.

The broad Workbench/NLQ regression run exposed five failures that also reproduce on untouched HEAD: a frontend source assertion expecting `BackgroundQueryDrawer`, an outdated PAR-30 expected value, missing catalog columns, missing dimension columns, and stale catalog row counts. Backend-wide Ruff and ty also have pre-existing failures. These are separate from the migration gates.

Final results: 1,244 backend tests passed, 22 skipped, and those same five baseline tests failed. This run included the PostgreSQL temporary-table test and cancellation tests using actual local TCP sockets. All four frontend tests passed. Ruff passes on every changed Python file, and focused ty checks pass on the new workflow, lock, verification script, and new tests. Backend-wide checks remain at the baseline of 10 Ruff errors and 408 ty diagnostics. `git diff --check` passes.

The cache verification command was exercised offline with simulated successful answers and both cache-hit and cache-miss usage reports; its real-server run remains pending. No live cache speedup is claimed.
