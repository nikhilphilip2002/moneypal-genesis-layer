# Workbench live smoke — 2026-09-04

Target: `http://100.70.118.31:4321/`

## Verdict

Core policy, routing, PostgreSQL MCP, Qdrant retrieval, and web transport are operational.
Canary expansion is blocked until the post-smoke fixes are deployed and the suite is rerun.
The current deployment's generic DB planner and common composer do not meet interactive
latency targets.

## LLM follow-up verification

The owner reported that the intended LLM process was not running. A subsequent check
confirmed `/api/nlq/health` returned LLM `HTTP 503` with `ask=false`. A uniquely tagged
planner request (`CHECK-LLM-20260904-UNIQUE`) remained at `planning` for 45 seconds, produced
no plan, and persisted no NLQ turn. Therefore this smoke does **not** establish that the
intended LLM was called. The earlier 700-token record is an application-reported response
from an unidentified or stale OpenAI-compatible endpoint and must be treated as an
endpoint/observability discrepancy until corroborated with llama-server access logs.

## Environment checks

- Frontend responds and redirects its root route with HTTP 307.
- `/api/health`: healthy.
- The initial `/api/nlq/health` check reported llama.cpp healthy; a subsequent check returned
  LLM `HTTP 503` with `ask=false`. PostgreSQL remained healthy as `nlq_readonly`, with a
  15-second statement timeout, 18 Gold views, and a healthy catalog.
- Workbench mode: local model; PostgreSQL transport: MCP.
- Source metadata correctly marks DB/schema/knowledge as consent-free and
  macro/competitive/regulatory/web as requiring external consent.

## Measured cases

| Case | Outcome | Total | First card | Model evidence |
|---|---|---:|---:|---|
| Macro requested, toggle off | Correct deterministic refusal; zero source attempts | 5,114 ms | n/a | No model call |
| Product-code DB lookup, toggle off | Correct chart and answer through PostgreSQL MCP | 752 ms | 563 ms | No model call; SQL execution 90 ms |
| Karnataka GDP, toggle on | Qdrant retrieved one cited passage | 88,442 ms | 452 ms | Composer 87,617 ms; 533 uncached input tokens; 700 output tokens; finish=`length`; zero cached tokens |
| Latest RBI repo search, toggle on | Web returned eight results but answer was correctly marked partial | 4,292 ms | 4,071 ms | No composer call because deployed normalization produced no excerpts |
| Total principal outstanding | Routing succeeded; DB source did not complete in the 60-second observation window | 59,853 ms before client cancellation | none | Direct `/nlq/ask` also remained in planning beyond 75 seconds |

The deterministic DB lookup proves Workbench → MCP → governed SQL → PostgreSQL → card and
answer is healthy. The generic DB failure is in model planning/queueing, not database health.

The composer row is application-reported telemetry, not independent proof that the intended
llama.cpp process executed it. The deployment owner reports that process received no call.
Because the response body identified `/root/Aroha/models/Qwen3.6-35B.gguf` while health
reported the configured `unsloth/Qwen3.5-9B-GGUF:UD-Q4_K_XL`, treat this as an endpoint,
proxy, or observability discrepancy until container configuration and server access logs are
reconciled.

## Defects found and repository fixes

1. Exa's JSON-in-text response was regex-parsed as bare URLs, causing serialized fields to
   appear inside URLs and leaving no excerpts. Normalization now recursively decodes MCP JSON
   wrappers and rejects quoted/backslash-contaminated URL fragments.
2. PostgreSQL MCP only applied transport/read deadlines; session shutdown could keep SSE open.
   The client now applies a whole-operation deadline including shutdown.
3. The rollout verifier's default DB case required the slow planner. It now uses a
   deterministic governed product lookup; planner latency remains a separate performance gate.
4. Docker builds pulled CUDA PyTorch and built the same Python image for three services. The
   Dockerfile now installs CPU PyTorch, Compose reuses one tagged backend image, and the root
   build context excludes the local `.venv` and test caches.
5. Unqualified current whole-book outstanding unnecessarily reached the LLM planner. It now
   resolves deterministically to the governed `principal_outstanding_book` metric and SQL.
6. Optional router/composer calls could consume provider retries without a whole-call bound.
   They now have 10/20-second deadlines, the composer is capped at 160 output tokens, and an
   extractive fallback is explicitly marked partial.
7. Root health did not prove model identity and the smoke verifier accepted fallbacks. Health
   now compares `/v1/models` with the configured model, and `--require-llm` fails rollout when
   the required model is unavailable or mismatched.

Regression evidence after these changes: Workbench 239 passed, 1 live-model test skipped;
scoped NLQ 857 passed, 90 environment-dependent skips; Compose configuration and Ruff checks
pass.

## Required rerun after deployment

1. Rebuild and deploy the backend/frontend images.
2. Run `backend/scripts/verify_workbench_rollout.py --require-llm` against the nginx `/api`
   origin. Do not continue if it reports an unavailable or mismatched model.
3. Recheck web URLs/excerpts and ensure the answer is no longer partial for parser reasons.
4. Confirm “Show our total principal outstanding” completes through deterministic governed
   SQL with zero model calls; separately measure a genuinely long-tail planner request.
5. Measure repeated composer calls to verify cache reads and p50/p95 latency.
6. Exercise competitive and regulatory sources with consent off and on.
