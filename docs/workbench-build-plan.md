# Genesis Workbench — Build Plan (historical)

> Superseded by `plan.md` and the plain-async, deterministic-first implementation. This
> document describes the original LangGraph build and is retained only for provenance.

A single chat interface ("workbench") that replaces the multi-module navigation. One LLM
orchestrator understands each query, routes it to the right knowledge source (DB / macro /
competitive / regulatory / schema), and renders every answer as a compact, single-viewport
card. Inference runs **completely locally** by default; Groq stays wired but off. The chat
carries a **"+"** capability menu and a **guidebot** (first-run tour + persistent helper).

## Locked decisions

- **Workbench = full replacement.** Chat is the app. The 8 module pages become in-chat cards.
  Left rail reduces to New / History / Saved views.
- **Completely local inference.** Local `llama-server` drives every step. Groq client stays
  in the codebase but disabled; an opt-in toggle allows a Groq burst for speed. Loan-book
  data never leaves the machine unless the user explicitly opts in.
- **Orchestration via LangGraph.** A state graph routes and fans out. The existing
  `nlq/llm/client.py` (grammar-guaranteed JSON on llama.cpp) is kept as the LLM node — we do
  **not** swap it for LangChain's provider wrapper, so small-model routing stays reliable.
- **"+" menu** = tools/actions · attach file · pin source · model/mode switch. Registry-driven.
- **Guidebot** = first-run spotlight tour + persistent "?" helper.
- **No hardcoded questions.** The orchestrator routes from a *source catalog* that describes
  what each source contains, exactly like the NLQ planner routes from the metric catalog.
  `docs/questions.md` is an eval set, never a lookup table.
- **Dense, single-viewport-first.** Each answer fits a viewport; detail collapses behind
  expanders. Desktop-first; mobile gets a simplified single column.

## Reused infrastructure (already present)

- `nlq/llm/client.py` — provider-agnostic (`llamacpp` + `groq`), grammar JSON. → model router base.
- `/ask` page — streaming SSE chat (`ChatThread` + `AskBar`). → evolves into the workbench.
- Domain services — `macro.py`, `competitive.py`, `regulatory.py` / `dnbs02_*`,
  `db_schema.py`, `nlq/*`, `rag.py` (Qdrant + bge-m3). → become orchestrator tools/nodes.
- `public.nlq_conversations` (Postgres jsonb) — conversation state. → extend for durable history.

---

## Architecture — the orchestrator graph

```
user turn
   │
   ▼
[rewrite]  standalone-ify follow-ups (reuse nlq REWRITE_SYSTEM_PROMPT)
   │
   ▼
[route]    one local-LLM call, grammar JSON → { sources:[...], intent, pinned?, refuse?/clarify? }
   │           system prompt = SOURCE CATALOG (describes each source's contents, not questions)
   ├── refuse / clarify ─────────────► emit event, stop
   │
   ▼
[dispatch] fan out to selected source nodes (parallel):
   ├── db_node          → nlq planner+compiler+executor  → ChartSpec
   ├── macro_node       → macro.brief / rag              → BriefCard
   ├── competitive_node → competitive profile/landscape  → SWOT/ProfileCard
   ├── regulatory_node  → dnbs02 read/summary            → RegCard (+ export action)
   └── schema_node      → db_schema.get_db_schema_graph  → SchemaGraphCard
   │
   ▼
[synthesize]  if >1 source: one local-LLM pass writes a short merged lead over the cards.
              Numbers come only from source cards — the synthesizer never invents figures.
   │
   ▼
stream typed SSE events → workbench renders cards
```

Single source is the common path and stays as fast as today. The graph only adds latency
when a query genuinely spans sources.

---

## Backend

### 1. Dependencies & config
- Add `langgraph` (+ minimal `langchain-core`) to `backend/requirements.txt`; rebuild image.
- `core/config.py`: `WORKBENCH_LOCAL_ONLY=true` (default), `WORKBENCH_ROUTER_MODEL`,
  `WORKBENCH_SYNTH_MODEL` (may equal the router model), `GROQ_OPT_IN=false`.

### 2. Model router — `services/workbench/models.py`
- Wrap the existing `get_llm_client()` in a policy: `for_step("route"|"synthesize"|"db_plan")`
  returns a client. Local-only forces `llamacpp`. Groq only when `GROQ_OPT_IN` **and** the
  step is non-sensitive (macro/competitive/regulatory synthesis) **and** the user opted in.
- Config seam so router and synthesizer can point at two different local models later without
  code change.

### 3. Source catalog — `services/workbench/sources.py`
- Declarative registry, one entry per source: `id`, `label`, `describes` (what data it holds,
  in plain words), `example_intents` (for the router prompt, illustrative not exhaustive),
  `handler`, `roles`. This is the analogue of the metric catalog: adding a source or refining
  its `describes` string generalizes routing to new phrasings — **no question list**.

### 4. Orchestrator graph — `services/workbench/graph.py`
- LangGraph `StateGraph`: nodes `rewrite → route → dispatch → synthesize`. State carries the
  conversation, rewritten question, chosen sources, per-source results, and emitted events.
- `route` uses grammar JSON (schema built from the source registry) — the model can only pick
  registered sources, mirroring how the NLQ planner can only pick catalog metrics.
- Node handlers are thin adapters over existing services (no logic duplicated).

### 5. Tool registry — `services/workbench/tools.py`
- Declarative tools for the "+" menu and heavy actions: `generate_dnbs_excel`,
  `compare_institutions`, `export`, `add_competitor`, `show_schema`, `attach_file`. Each:
  `id`, `label`, `params_schema`, `roles`, `handler`, `render`. New use cases are added here
  declaratively — this is the extensibility the "+" promises.

### 6. API + streaming — `api/routes/workbench.py`
- `POST /api/v1/workbench/ask` (SSE). Keep the existing event protocol; add event types:
  `route` (chosen sources), `source_start`/`source_card` (per source), `synthesis` (token
  stream of the merged lead), plus existing `stage`/`clarify`/`refusal`/`error`/`done`.
- `POST /api/v1/workbench/tool/{id}` for "+" actions; long ones (DNBS Excel) return a job id
  and stream progress.

### 7. Persistence — extend conversation store
- New durable table `public.workbench_conversations` (no idle expiry) + list endpoint for the
  History rail. Reuse the `nlq_conversations` jsonb pattern and sticky-filter chips.

### 8. Attachments (phased) — `services/workbench/attachments.py`
- Upload → chunk (`rag.chunk_text`) → embed (bge-m3) → Qdrant collection scoped to the
  conversation. A `attachment` source node retrieves over it. Deferred to Phase 3.

---

## Frontend

### 1. Workbench page — replace `/ask`, make it `/`
- New `app/workbench/page.tsx` (or repoint `/`). Layout: slim left rail (New / History /
  Saved), center thread, bottom composer. Remove module routes from `AppSidebar`; keep them
  as internal card renderers, not nav destinations.

### 2. Card system — `components/workbench/cards/`
- One `<WorkbenchCard>` shell (title, source badge, collapse, actions) wrapping renderers:
  `KpiCard`, `ChartCard` (reuse `ChartRenderer`), `BriefCard` (reuse `BriefRenderer`),
  `SwotCard`, `RegCard`, `SchemaGraphCard` (reuse `DBSchemaGraph`), `MultiSourceCard`
  (synthesis lead + stacked collapsible source cards).
- **Density rules:** every card opens at a compact height; secondary detail (SQL/lineage,
  full tables, mermaid) is behind an expander. Latest answer auto-fits the viewport; the
  thread virtualizes older turns.

### 3. Composer + "+" — `components/workbench/Composer.tsx`
- Evolve `AskBar`. "+" opens a popover backed by the tool registry: Tools/actions, Attach
  file, Pin source (DB/Macro/Competitive/Regulatory), Model/mode switch (incl. fully-local
  ↔ Groq-burst). Pinned source is passed to `route` and shown as a dismissible chip.

### 4. Guidebot — `components/workbench/Guidebot.tsx`
- First-run: spotlight steps over composer, "+", a sample card, the History rail (state in
  localStorage; re-launchable from Help). Persistent: "?" bottom-right that answers
  "how do I…" from a small static capability doc (local model, no new source).

---

## Phasing (MVP-first)

- **Phase 1 — Skeleton + DB/Macro. ✅ DONE.** LangGraph graph with `route` over a 2-source
  catalog (db, macro), workbench page, card shell, `WorkbenchCard` + `ChartCard`/`BriefCard`,
  extended SSE. One chat answers both a loan-book number and a macro brief, routed
  automatically, fully local.
- **Phase 2 — All sources + multi-source. ✅ DONE (TDD, 24 tests).** Added competitive,
  regulatory, schema sources + node adapters via a dispatch-table registry; `synthesize`
  node emits a merged lead only when >1 source contributes; role-gated source registry;
  frontend brief `key_points` + schema card. Workbench promoted to the landing page; the
  redundant Ask Genesis nav entry removed (route still resolves). Full module-nav teardown
  is held until the workbench backend is smoke-tested against the live stack.
- **Phase 3 — "+" tools + attachments. 🔶 IN PROGRESS.**
  - ✅ Pin-source wired end-to-end (TDD): a role-validated deterministic override that
    bypasses the router; can only narrow, never widen, access.
  - ✅ Tool registry (TDD): declarative `tools.py` with role-gated `run_tool`; `GET
    /workbench/tools` + `POST /workbench/tool/{id}` (403/404 enforced at the edge); "+"
    Tools submenu populated from the registry, results appended as cards. Two v1 tools
    (`show_schema`, `competitor_landscape`); new actions are one registry entry.
  - ⬜ Attachments → Qdrant ingestion + retrieval (needs live Qdrant to smoke-test).
  - ⬜ Model/mode switch made functional from the composer.
- **Phase 4 — Guidebot + density polish + durable history. ✅ DONE.**
  - Durable history (TDD, 5 tests): `history.py` (Postgres + in-memory fallback), `GET
    /workbench/conversations` + `/{id}`, turns recorded in the graph, `conversation` SSE
    event threads the id; frontend History rail (New + recent, click to recap).
  - Guidebot: first-run spotlight tour (localStorage, replayable) + persistent "?" helper
    with a static local FAQ (no model, never fabricates).
  - Density: collapsible source cards, slim rail, compact composer — single-viewport-first.
- **Phase 5 — Routing eval. ✅ DONE (TDD, 4 tests + live skip).** `eval.py` model-agnostic
  scorer + `golden/routes.yaml` (18 cases from questions.md as a **fixture, not a lookup**);
  scored on source-set equality at the admin role; `python -m app.services.workbench.eval`
  CLI and a `WB_EVAL_LIVE=1` pytest gate (≥0.8). New 👎 feedback becomes a new golden case;
  fixes go into catalog descriptions/few-shots, never a per-question rule.

## Open risks / to validate during build

- **Local routing reliability** on the chosen model — mitigated by grammar JSON, but the
  source-catalog prompt needs the same care as the metric catalog. Measure with Phase 5 eval.
- **Synthesis latency** of a larger local model for merged narratives — may justify splitting
  router (small) and synthesizer (larger) models; the config seam is there for it.
- **Multi-source correctness** — the synthesizer must cite only source-card numbers; enforce
  by passing structured card values, not free text, into the synthesis prompt.
