# Verified Codebase Cleanup Audit

**Project:** MoneyPal
**Verified:** 16 September 2026
**Scope:** Current working tree under `/home/null/Projects/moneypal`

---

## Executive Summary

The earlier version of this audit mixed valid cleanup candidates with stale line counts,
unsupported clone totals, and active endpoints incorrectly classified as dead. This revision
records only findings that can be supported by the current repository.

| Area | Verified result |
| :--- | :--- |
| Unreachable source removal completed | 27 files, approximately 6,039 physical lines |
| Frontend dependency removal completed | 18 packages plus their unused transitive packages |
| Declaration-only backend symbols resolved | 12 removed; `close_pool()` wired into shutdown |
| Legacy conversational implementations removed | NLQ planner/evaluator and stale Workbench evaluator corpora |
| API endpoints requiring an ownership/deprecation decision | 8 endpoints |
| Endpoints incorrectly classified as dead in the prior audit | 5 endpoints; all are retained |
| Benchmark inventory used by the previous 6,148-line total | 7 files, not 8 |
| Archive inventory | 30 files, 1,718,572 bytes |

The exact previous claims of **141 `jscpd` clones**, **1,872 duplicated lines**, **26 unused
TypeScript types**, and **12 major duplication patterns** are not retained. No reproducible
command, configuration, tool version, symbol list, or generated report exists in the repository
for those totals.

Static absence of an in-repository caller does not prove that a public API is unused by external
clients. API removals therefore require a deprecation decision, not an immediate deletion.

### Cleanup progress

The verified cleanup passes are complete:

- Removed the 27 unreachable source files recorded in Section 2.
- Removed the 18 direct frontend dependencies recorded in Section 5 and regenerated the lockfile.
- Removed unreachable frontend API exports, the obsolete role hook/cache, and `_format_chunks()`.
- Removed all verified Ruff `F401` and `F841` findings.
- Restored the missing NLQ route identity helper caught by the final `F821` pass and added
  regression coverage for known and anonymous tokens.
- Consolidated backend demo-token identity parsing across auth, NLQ, and Workbench routes.
- Replaced six duplicated frontend authorization effects with a shared `useRequireAuth()` guard
  and tightened the shared user-role response type.
- Consolidated exact, compact, and Indian-grouped currency formatting across customer details,
  portfolio graphs, NLQ charts, and DNBS reports while retaining their display precision.
- Replaced unsafe page-level error casts with an `unknown`-safe helper, made the shared API request
  boundary generic, and removed three caller-free analytics client methods.
- Removed straightforward unused frontend imports and the toast debug log.
- Replaced `next lint` with ESLint 9 flat configuration.
- Removed Workbench node tests for production adapters that no longer exist.
- Removed the unreachable NLQ conversational planner, its LLM prompt/schema layer, evaluator, and
  planner-only tests after verifying there was no application, route, scheduler, or script caller.
- Removed the stale native-agent evaluator and its retired tool-name corpora.
- Wired the NLQ database pool into application shutdown.
- Kept every API deprecation candidate, active NLQ execution infrastructure and endpoints, RAG
  implementations, catalog YAML, archives, and benchmark scripts unchanged.

---

## 1. Current Workbench and NLQ Architecture

`workbench` and `nlq` are not competing implementations that can be reduced to one directory.
They now serve different layers:

```text
Frontend chat
  -> POST /workbench/ask
  -> Workbench native-tool agent
  -> PostgreSQL MCP
  -> NLQ catalog, PII policy, SQL validator, executor and chart builder
  -> PostgreSQL Gold views
```

- `POST /workbench/ask` is the canonical conversational endpoint. The frontend calls it from
  [`frontend/app/workbench/page.tsx`](frontend/app/workbench/page.tsx).
- The legacy frontend `/ask` page only redirects old bookmarks to `/workbench`.
- There is no `POST /nlq/ask` route. The existing test suite explicitly expects it to return 404.
- The `/nlq/execute` endpoint remains active and powers the Workbench Portfolio Dashboard.
- Workbench database calls go through PostgreSQL MCP, which directly imports the NLQ catalog,
  database adapter, PII rules, validator, executor, and SQL metadata helpers.
- Workbench also reuses NLQ contracts, chart construction, LLM client/messages, catalog retrieval,
  normalization, and telemetry.

**Decision:** Do not delete `backend/app/services/nlq/`. Any cleanup must distinguish the legacy
NLQ conversational planner from the governed query infrastructure still used by Workbench,
signals, worklists, dashboards, and PostgreSQL MCP.

---

## 2. Removed Unreachable Source

The following files had no active import or entrypoint and were removed in the first cleanup pass.

### 2.1 Root and backend

1. `main.py`
   - Initial `uv init` hello-world program.
   - The deployed entrypoint is `backend/app/main.py` through Uvicorn.
2. `test.py`
   - Standalone PostgreSQL diagnostic with a hardcoded LAN default and development credentials.
   - It is outside configured pytest discovery (`backend/tests`).
3. `backend/app/services/nlq/governed_execution.py`
   - Wrapper module with no importers.
   - Active code calls `pipeline.run_spec`, lookup, analysis, worklist, and briefing services
     directly.

### 2.2 Frontend components and hook

These 18 components and one hook are outside the active Next.js import graph:

1. `frontend/components/AppSidebar.tsx`
2. `frontend/components/ConditionalHeader.tsx`
3. `frontend/components/NavBar.tsx`
4. `frontend/components/intel/GenesisSearch.tsx`
5. `frontend/components/intel/OnboardingRibbon.tsx`
6. `frontend/components/intel/StreamingBrief.tsx`
7. `frontend/components/mobile/MobileTabBar.tsx`
8. `frontend/components/mobile/MobileTopNav.tsx`
9. `frontend/components/workbench/Guidebot.tsx`
10. `frontend/components/ui/command.tsx`
11. `frontend/components/ui/markdown-renderer.tsx`
12. `frontend/components/ui/pagination.tsx`
13. `frontend/components/ui/popover.tsx`
14. `frontend/components/ui/progress.tsx`
15. `frontend/components/ui/radio-group.tsx`
16. `frontend/components/ui/scroll-area.tsx`
17. `frontend/components/ui/sidebar.tsx`
18. `frontend/components/ui/tooltip.tsx`
19. `frontend/hooks/use-mobile.tsx`

### 2.3 Explicitly retained test

`frontend/lib/api-stream.test.cjs` is **not dead code**. The root README documents:

```bash
cd frontend && node --test lib/api-stream.test.cjs
```

The command currently passes. Keep this file and consider exposing it as an npm `test` script.

### 2.4 Retired conversational evaluators

The following five source files were also removed after an import and entrypoint audit:

1. `backend/app/services/nlq/planner.py`
2. `backend/app/services/nlq/eval.py`
3. `backend/app/services/nlq/llm/prompts.py`
4. `backend/app/services/nlq/llm/schemas.py`
5. `backend/scripts/evaluate_native_agent.py`

The first four implemented the old `/nlq/ask` conversational planner, an endpoint that no longer
exists. The fifth encoded retired Workbench tool names and semantic-table assumptions. Their
planner/evaluator-only tests and golden corpora were removed with them. The active QuerySpec golden
corpus remains because it still validates the retained compiler.

---

## 3. Resolved Declaration-Only Symbols

Repository-wide searches outside documentation found only the declaration for twelve symbols; all
twelve were removed. The thirteenth finding was a valid resource-lifecycle helper and was wired into
the FastAPI lifespan shutdown path instead:

| Symbol | Former location | Resolution |
| :--- | :--- | :--- |
| `clear_graph_cache()`, `_snapshot_info()`, `_accounts_and_agents()` | `curiosity_graph.py` | Removed |
| `specs_for_sheet()`, `written_specs()` | `dnbs02_spec.py` | Removed |
| `cached_result()` | `nlq/cache.py` | Removed |
| `clear_cache()` | `nlq/catalog/lookups.py` | Removed |
| `_has_additive_metric()` | `nlq/compiler.py` | Removed |
| `MetricGrain` | `nlq/contracts.py` | Removed |
| `rewrite_schema()` | `nlq/llm/schemas.py` | Removed with the retired planner schema module |
| `refusal_examples()` | `nlq/planner.py` | Removed with the retired planner |
| `normalize_collection_name()` | `rag.py` | Removed |
| `close_pool()` | `nlq/db.py` | Retained and called during application shutdown |

The following frontend/backend symbols were also removed during the cleanup:

| Symbol | Former location | Result |
| :--- | :--- | :--- |
| `useUserRole()` | `frontend/lib/useUserRole.ts` | Removed with its now-unnecessary role cache |
| `streamBriefing()` | `frontend/lib/api.ts` | Removed after `StreamingBrief.tsx` deletion |
| `intelligence` client object | `frontend/lib/api.ts` | Removed; backend endpoints remain pending deprecation review |
| `health` client object | `frontend/lib/api.ts` | Removed |
| `_format_chunks()` | `backend/app/services/workbench/nodes.py` | Removed |

---

## 4. API Endpoint Verification

### 4.1 Active endpoints that must be retained

The prior audit incorrectly marked these endpoints as dead:

| Endpoint | Active caller |
| :--- | :--- |
| `GET /competitive/institutions/{institution_id}/swot` | `frontend/app/competitive/page.tsx` |
| `GET /nlq/worklists/{worklist_id}/export` | `frontend/components/workbench/WorkbenchTurn.tsx` |
| `POST /nlq/signals/{fingerprint}/status` | `frontend/components/nlq/BriefingCard.tsx` |
| `GET /regulatory/reports/{report_id}/periods` | `frontend/components/intel/DNBSReport.tsx` |
| `GET /regulatory/reports/{report_id}/export` | `frontend/components/intel/DNBSReport.tsx` |

`/nlq/execute` is also active through `frontend/components/workbench/PortfolioDashboard.tsx`.

The worklist and signal actions are wired through active renderers, although the current native
Workbench tool registry may no longer produce new `worklist` or `briefing` cards. Confirm whether
saved conversation history or external clients still depend on those card types before simplifying
them.

### 4.2 Deprecation-review candidates

These endpoints have no active frontend caller in the current tree:

| Endpoint | Current evidence | Required decision |
| :--- | :--- | :--- |
| `GET /intelligence/recent` | Former unused client wrapper removed; no in-repository caller | Confirm external/dashboard consumers, then deprecate or remove |
| `GET /intelligence/action-items` | Former unused client wrapper removed; no in-repository caller | Confirm external/dashboard consumers, then deprecate or remove |
| `POST /intelligence/search` | Its only caller was removed with unreachable `GenesisSearch.tsx` | Prefer Workbench curated-search tools |
| `POST /intelligence/ask` | Its only caller was removed with unreachable `GenesisSearch.tsx` | Prefer `POST /workbench/ask` |
| `GET /macro/briefing/stream` | Its only caller was removed with unreachable `StreamingBrief.tsx` | Retain only if external SSE clients exist |
| `GET /admin/customers/{customer_id}/details` | Former unused client wrapper removed; backend test covers route behavior | Decide whether it remains a supported API |
| `POST /auth/session/refresh/` | No caller; frontend stores but never uses `refreshToken` | Implement a valid refresh flow or remove both token and endpoint |
| `POST /nlq/worklists/{worklist_id}/status` | Former unused client wrapper removed; no UI caller | Retain only if worklist assignment remains planned/supported |

The refresh endpoint currently returns `mock-token-refresh`, which `/auth/me/` cannot resolve to a
known user. It is not merely unused; it would be invalid if the frontend began calling it.

---

## 5. Removed Frontend Dependencies

### 5.1 Completely unreferenced packages

1. `@headlessui/react`
2. `@heroicons/react`
3. `@radix-ui/react-collapsible`
4. `@radix-ui/react-icons`
5. `@radix-ui/react-radio-group`
6. `@radix-ui/react-toast`
7. `axios`
8. `date-fns`
9. `react-syntax-highlighter`
10. `@types/react-syntax-highlighter` (development dependency)

`frontend/components/ui/radio-group.tsx` is a local implementation and does not import
`@radix-ui/react-radio-group`.

### 5.2 Packages referenced only by unreachable components

1. `cmdk` — `ui/command.tsx`
2. `@radix-ui/react-popover` — `ui/popover.tsx`
3. `@radix-ui/react-progress` — `ui/progress.tsx`
4. `@radix-ui/react-scroll-area` — `ui/scroll-area.tsx`
5. `@radix-ui/react-tooltip` — `ui/tooltip.tsx` and `ui/sidebar.tsx`
6. `react-markdown` — `ui/markdown-renderer.tsx`
7. `remark-breaks` — `ui/markdown-renderer.tsx`
8. `remark-gfm` — `ui/markdown-renderer.tsx`

These packages were removed in the same change as their final importing files, and
`package-lock.json` was regenerated by npm.

---

## 6. Lint and Debug Findings

The first pass removed 10 unused imports (`F401`) and the unused assignment (`F841`) at
`backend/app/services/dnbs02_lineage.py`. A focused Ruff check for both rules now passes.

Ruff still identifies two `ERA001` comments. They are false positives for this audit:

- `# Expected: YYYY-MM` documents accepted input syntax.
- The weighted-ratio calculation in `test_drivers.py` explains an assertion.

They are explanatory comments, not disabled code, and should remain or be rewritten as prose rather
than deleted as dead code.

The production `console.log("Toast:", props)` was removed from
`frontend/components/ui/use-toast.ts`. The active toast hook and Toaster remain.

`npm run lint` now uses ESLint 9 flat configuration and exits successfully. The initial baseline
still reports 25 warnings, primarily third-party graph/chart callback types and React Compiler
migration
diagnostics. Those checks remain visible as warnings for a later component-hardening pass.

---

## 7. Duplication Findings

### 7.1 RAG implementations: overlap, not a safe deletion

`packages/genesis_core/src/genesis_core/rag.py` and `backend/app/services/rag.py` both provide
embedding, Qdrant, chunking, and generation utilities, but they are not simple clones:

- They use different settings objects and embedding-model names.
- Their chunking units differ (words versus characters).
- The backend version provides a guarded hash fallback and local-index search fallback.
- They use different LLM clients and error-handling behavior.
- `genesis_core.rag` owns ingestion and streaming functionality absent from the backend module.
- Regulatory code and Workbench intentionally call the backend implementation, while macro,
  competitive, policy, and platform code use `genesis_core.rag`.

Consolidation remains worthwhile, but it requires an explicit compatibility contract and migration
tests. Do not delete `backend/app/services/rag.py` after merely moving “missing methods.”

### 7.2 Inactive parent catalog definitions

The NLQ loader explicitly selects `backend/app/services/nlq/catalog/defs/gold`. The six YAML files
directly under `defs/` are inactive legacy definitions totaling 1,490 lines.

Each differs from its Gold counterpart; they are not verbatim duplicates. Delete or move them to
`archive/` only after confirming no external catalog tooling consumes the old paths.

### 7.3 Smaller structural duplication

- `institution_loader.py` and `reg_loader.py` repeat the same JSON registry operations, but are not
  byte-for-byte clones. A generic registry is optional and should retain domain-specific validation.
- PDF page extraction is repeated in `genesis_core.rag`, `backend/scripts/ingest.py`, and the macro
  extractor, with different exception policies. A shared primitive should make that policy explicit.
- Backend and `genesis_core` response models overlap but are not identical: page support, defaults,
  and required fields differ. The drift should be resolved in favor of one API contract.
- **Resolved:** six frontend pages now share `useRequireAuth()` and one validated `UserRole`
  contract instead of repeating client-side role guards and casts.
- **Resolved:** customer, schema graph, NLQ chart, and DNBS report components now share exact,
  compact, and Indian-grouped formatters while retaining context-specific precision.
- `AIBriefPanel` and the expanded state of `IntelligenceCard` share briefing body rendering. Extract
  the common body while leaving their distinct card/header behavior intact.

### 7.4 Benchmark suite

The earlier 6,148-line figure is the total for these seven files:

1. `scripts/chains_500_loanbook.py`
2. `scripts/run_100_executive_loanbook_chains.py`
3. `scripts/run_100_queries.py`
4. `scripts/run_200_loanbook_queries.py`
5. `scripts/run_200_mixed_queries.py`
6. `scripts/run_500_loanbook_benchmark.py`
7. `scripts/run_50_executive_queries.py`

There is clear semantic duplication in environment loading, SSE decoding, result models,
conversation loops, percentile calculations, checkpoint writing, and Markdown reports. Exact clone
percentages are intentionally omitted until a reproducible detector is added.

Recommended direction:

1. Move question and chain corpora into data-only modules or JSON fixtures.
2. Extract shared SSE, result, reporting, checkpoint, and environment helpers.
3. Expose one CLI with explicit single-turn, multi-turn, and reconciliation modes.
4. Preserve corpus metadata and output compatibility before deleting runners.

---

## 8. Prioritized Cleanup Plan

### Phase 0: Establish a green baseline — completed

1. **Completed:** Repair the frontend ESLint configuration.
2. **Completed:** Remove or migrate stale Workbench tests for deleted adapters, the retired
   `schema` source, and old database tool names.
3. **Completed:** Run backend unit tests with unreachable database suites skipped by bounded
   connectivity checks; document the separate macro runtime failure in Section 9.

### Phase 1: High-confidence source and dependency cleanup — completed

1. **Completed:** Remove `main.py`, `test.py`, and
   `backend/app/services/nlq/governed_execution.py`.
2. **Completed:** Remove the 18 unreachable frontend components and `use-mobile.tsx`.
3. **Completed:** Retain and verify `frontend/lib/api-stream.test.cjs`.
4. **Completed:** Remove `useUserRole()`, its obsolete cache, `streamBriefing()`, and unreachable
   client exports after removing their consumers.
5. **Completed:** Uninstall the 18 packages in Section 5 and regenerate the lockfile.
6. **Completed:** Apply the 10 Ruff unused-import fixes and remove only the unused `cell` assignment—not the two
   explanatory comments.
7. **Completed:** Remove the toast debug log while retaining the active hook.

### Phase 2: API deprecation

1. Inventory access logs, deployed consumers, scripts, and external integrations for the eight
   candidates in Section 4.2.
2. Mark supported public APIs explicitly.
3. Deprecate or remove unused wrappers and endpoints together.
4. Resolve authentication refresh as a feature decision: implement it correctly or remove both the
   unused stored refresh token and backend route.

### Phase 3: NLQ migration boundary — completed

1. **Completed:** Retain the NLQ catalog, contracts, PII rules, DB layer, validator, executor, SQL
   metadata, charting, lookup completions, and LLM primitives used by Workbench/MCP.
2. **Completed:** Build a module-level import map for the old planner, schemas, evaluator, and tests.
3. **Completed:** Remove the isolated conversational planner stack and update operational docs.
4. **Deferred by design:** Any rename of retained `nlq` infrastructure is an architectural change,
   not required for cleanup.

### Phase 4: Refactoring

1. Consolidate benchmark infrastructure.
2. **Completed:** six role-gated pages now use `useRequireAuth()`, and shared INR formatters retain
   the distinct precision required by account details, compact cards, charts, and regulatory tables.
3. Resolve the duplicate response contract.
4. Design and test a single RAG interface before migrating callers.
5. Decide whether inactive parent catalog YAML belongs in version control or archive history.

---

## 9. Verification Record

Commands executed during this revision:

| Check | Result |
| :--- | :--- |
| `cd frontend && node --test lib/api-stream.test.cjs` | Pass: 1 test |
| `cd frontend && npx tsc --noEmit` | Pass |
| `uv run ruff check backend --select F401,F821,F841` | Pass |
| `cd frontend && npm run lint` | Pass with 25 migration warnings |
| `uv run pytest -q backend/tests/nlq backend/tests/workbench` | Pass: 1,018; skip: 98 integration tests |
| `uv run pytest -q backend/tests --ignore=backend/tests/macro` | Pass: 1,079; skip: 160 integration tests |
| `uv run pytest -q backend/tests/macro` | Environment-blocked: 10 pass, 13 fail because NumPy cannot load missing `libstdc++.so.6` |
| `cd frontend && npm run build` | Pass: optimized Next.js production build and 14 static routes |
| `git diff --check` | Pass |

No live PostgreSQL, Qdrant, browser, or external API smoke test was used to declare an endpoint dead.
The 160 integration skips reflect unavailable external services or fixtures. Those checks remain
required before API or data-path removal. The macro failures are an environment dependency issue,
not assertion failures in the cleanup changes.
