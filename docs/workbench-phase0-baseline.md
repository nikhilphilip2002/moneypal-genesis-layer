# Workbench Phase 0 Baseline

Date: 2026-09-04

The existing 200-question execution benchmark is the pre-simplification functional and
latency baseline. It completed 200 requests with:

- expected source observed: 168/200 (84%);
- answered: 158; partial: 31; clarification: 2; refused: 7; errors: 2;
- average latency: 24.09 seconds;
- median latency: 15.04 seconds;
- p95 latency: 76.18 seconds.

The benchmark does not contain provider usage for every request, so it is not sufficient to
ratify per-purpose token or model-call budgets. The Phase 0 instrumentation now records call
purpose/kind, provider, model, prompt and catalog versions, stable-prefix hash, prompt,
cached, cache-write, uncached and completion tokens, duration, retries and finish reason.
These fields are aggregated under each persisted Workbench turn and exposed by the
conversation API. A production-like rerun is still required for p50/p95 call and token
baselines and cache-reuse proof.

## Initial local verification record

- Workbench suite excluding the HTTP `TestClient` module: 194 passed, 1 live-model test
  skipped.
- Focused changed-path suite: 127 passed.
- NLQ suite excluding its HTTP `TestClient` module: 850 passed, 90 skipped, 1 pre-existing
  deterministic catalog failure. The failing case interprets “Show sanctioned amount in
  CCF Low ROI Scheme” as a named-borrower lookup instead of a scheme-filtered QuerySpec;
  the changed telemetry path is not reached.
- FastAPI's `TestClient` hangs even on `/health` in this environment and reports that the
  installed Starlette test client is deprecated in favor of `httpx2`. Workbench and NLQ API
  modules therefore remain unverified here until the test-client dependency is repaired.
- Frontend TypeScript check passed.
- Frontend production build passed; only the repository's existing stale Browserslist data
  warning was emitted.
- Targeted Ruff checks for the changed core modules pass. A repository-wide Ruff run still
  reports 19 pre-existing findings in unrelated or previously unchanged files.

Source: repository `benchmark.md`, generated 2026-08-26.

## Post-refactor verification update

The HTTP harness was migrated from deprecated `TestClient` usage to HTTPX ASGI transport,
and synchronous Workbench GET handlers were made async. The Workbench API suite now runs
without the prior deadlock. The full local Workbench suite passes 242 tests with one live-
model test skipped. The NLQ suite (excluding its separate legacy HTTP module) passes 857
tests with 90 environment-dependent skips; the previously documented CCF Low ROI Scheme
planner failure is fixed.
