# Workbench simplification verification

Date: 2026-09-04

## Implemented outcome

- Plain async orchestration replaced LangGraph; the dependency and transitive lock entries
  were removed.
- Source access is consent ∩ role ∩ deployment, snapshotted once per request and enforced at
  routing, dispatch, pins, direct tools, Qdrant handlers, and the web boundary.
- The deterministic route corpus currently passes 11/11 source-set fixtures and makes zero
  router-model calls, exceeding the 95%/80% fixture gates. This is a local deterministic
  corpus result, not a production traffic claim.
- Macro, competitive, regulatory, and web handlers are retrieval-only. One evidence-bearing
  source uses one common composer call; several evidence-bearing sources still use one.
- DB/schema complete cards, governed catalog definitions, policy refusals, and deterministic
  routing do not invoke the user-facing composer.
- The canonical model transcript contains definitive user/assistant turns plus bounded
  checkpoint/session facts. Cards, SQL, lineage, raw rows, tool traces, planner JSON, and
  retrieved documents are excluded.

## Local checks

- Workbench: 242 passed, 1 live-model test skipped.
- NLQ excluding its HTTP module: 857 passed, 90 environment-dependent skips.
- The prior CCF Low ROI Scheme deterministic planner failure was fixed.
- Frontend TypeScript check passes.

The broader `backend/tests` collection cannot import NumPy in this sandbox because the
runtime image lacks `libstdc++.so.6`; its first failure occurs in the macro ingestor before
application tests execute. The deployment container must run that broader suite.

## Deployment evidence still required

Real p50/p95 token, cache-read/write, and latency measurements require the deployed model,
PostgreSQL, Qdrant, Exa, provider credentials, and production-like concurrency. Canary and
observation-window checklist items must be signed off in that environment; this repository
does not fabricate those measurements.

The first live smoke on 2026-09-04 is recorded in
`docs/workbench-live-smoke-2026-09-04.md`. It validates consent enforcement, deterministic
PostgreSQL MCP, Qdrant retrieval, and web transport, but blocks canary expansion on deployed
composer/planner latency and a web-result normalization defect fixed after that deployment.
The post-smoke repository also routes the common whole-book outstanding KPI without a model,
bounds optional routing/composition calls, marks extractive fallbacks partial, verifies the
served llama.cpp model identity, and requires LLM readiness in the rollout verifier.
