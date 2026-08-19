# Executive Assistant Plan — Answering the Top 50 Questions

**Goal:** move Genesis from *"one question → one chart"* to *"one question → a reasoned answer that can be drilled from board level to a single account, and ends in an action."*

**Scope of this document:** what has to be built, in what order, and — honestly — which of the 50 questions cannot be answered at all until the client supplies data that does not currently exist anywhere.

---

## 1. The real gap

The instinct is "add more metrics to the catalog." That is wrong. The catalog is in good shape (25 metrics, 16 dimensions, deterministic compile → SQL → chart, full lineage). Only ~4 of the 50 questions are blocked by a missing metric.

The 50 questions are blocked by **four missing capabilities** and **one missing data set**:

| # | Missing capability | Why the current architecture can't do it | Blocks |
|---|---|---|---|
| **C1** | **Multi-query answers.** A `QuerySpec` is *one* SQL statement producing *one* `ChartSpec`. "How is the business performing, and what are the 5 things I need to know?" is 8–12 queries plus a ranking of what is notable. | `PlanResult` has no route that produces more than one result. | Q1, 2, 5, 9, 19, 21, 27, 36, 42 |
| **C2** | **Explanation ("why").** The system reports *what* a number is. Fifteen of the 50 questions ask *why it moved*. That is a deterministic contribution decomposition (Δ split across dimensions, mix vs. rate effect), not an LLM opinion. | No such engine exists. Today "why did collections drop" becomes a plain breakdown, which does not answer it. | Q2, 7, 11, 20, 25, 31, 37, 38 |
| **C3** | **Targets and expectations.** "Above or below target", "off-target", "versus budget", "vs. expectations" — half of section A and B compare against a plan number that is not in the warehouse. | `compare_to` supports period-vs-period only. There is no target table, no target metric, no variance-to-plan chart. | Q3, 4, 5, 11, 12, 37 |
| **C4** | **Standing signals, not just answers.** "What are the emerging issues?", "What am I not asking?", "What decisions need my attention?" require the system to have *already scanned* the book and formed a ranked list of anomalies before the user asks. | Everything is request-scoped. Nothing runs on a schedule; nothing is stored as a finding. | Q8, 9, 10, 26, 41, 44, 45 |
| **D1** | **Data that does not exist.** No budget/plan, no branch master (therefore **no geography at all**), no channel, no opex/cost allocation, no HR, no legal case register, no audit findings, no strategy tracker, no collections agency/contact log. | Per `docs/ORACLE_VS_POSTGRES_GAP_ANALYSIS.md` §3.2: *"Branch name, address, city, state and district have no source in Oracle either."* | Q36–41, 46–50, plus the "region" rung of every drill chain |

The drill-down chain you described (`why → region → branch → segment → account → why → action`) is blocked at three points: the ladder is hardcoded three levels (`branch → product → scheme`, `charts.py:642`), there is no region, and it terminates at an aggregate — it never reaches accounts or an action.

---

## 2. Question triage — what is actually reachable

| Tier | Meaning | Questions | Count |
|---|---|---|---|
| **T1 — Reachable now** | Existing gold catalog + existing pipeline; needs catalog entries and prompt work only. | 6*, 13*, 16, 19, 21*, 24 | 6 |
| **T2 — Needs a new engine, data exists** | Build C1/C2/C4 on `bronze` as it stands today (incl. the untouched `genlnappl*` application tables). | 1, 2, 7, 8, 9, 10, 11†, 12, 14, 15, 17, 18, 20, 23, 25, 26, 27, 29, 31, 32*, 33, 35*, 41*, 42, 43, 44, 45, 46*, 50* | 29 |
| **T3 — Needs the Oracle migration batch** | `GENLNRCPT`/`GENLNRCPTDTL` (payment channel + receipt history), `LNACLED`/`LNACLED_OS` (transaction ledger), `GENLNRCPT_WAIVE`. Already scoped in the gap analysis. | 22, 28, 30, 39 | 4 |
| **T4 — Needs a new client feed** | The data does not exist in Oracle or PostgreSQL. No amount of engineering produces it. | 3, 4, 5, 34, 36, 37, 38, 40, 47, 48, 49 | 11 |

`*` = partially answerable — the product/branch/agent slice works, the geography or channel slice does not.
`†` = the "why" half works today's-data; the "vs target" half needs the T4 plan feed.

**Bottom line: 35 of 50 are reachable on data we hold. 4 more with a migration batch already specified. 11 require the client to give us something.**

### The T4 feeds to ask the client for (ranked by questions unlocked)

| Feed | Format | Unlocks |
|---|---|---|
| **Annual business plan / targets** — target value per metric × branch × product × month | One spreadsheet, refreshed quarterly | Q3, 4, 5, 11, 12 (and the whole "on track?" framing of Q1) |
| **Branch master** — branch code → name, city, district, state, region, channel | One spreadsheet, near-static | The `region` rung of *every* drill chain, Q6, 13, 21, 32 |
| **Cost & opex allocation** — cost centre → branch/product, monthly actual + budget | Tally export (see `TALLY_EXPORT_STEPS.md`) | Q36, 37, 38, 39, 40 |
| **Collections contact log** — account, attempt, channel, outcome, agency/agent | Operational system export | Q30, 32, 34 |
| Legal case register / audit observation log / strategic initiative tracker / HR headcount & productivity | Registers, likely spreadsheets today | Q47, 48, 49, 50 |

Recommendation: get the **first two** and the count reachable rises from 35 to 40. They are small, static, and cost the client an afternoon.

---

## 3. Architecture changes

Seven pieces. Each is additive — no existing route, contract or chart changes behaviour.

> **Status:** §3.2 (driver decomposition) and §3.4 (drill graph) are implemented, along with
> the conversation patterns in §4.1–4.3 and the next-question chips in §4.5. The rest of
> this section is still design.

### 3.1 `analysis` route — multi-query answers (C1)

The load-bearing change. Add a fifth planner route alongside `queryspec | sql | clarify | refuse`.

```python
# contracts.py
class AnalysisStep(_Model):
    id: str                    # "par_by_branch"
    spec: QuerySpec
    label: str

class AnalysisSpec(_Model):
    steps: list[AnalysisStep] = Field(min_length=1, max_length=12)
    compose: Literal["briefing", "drivers", "funnel", "quadrant", "vs_target", "cohort"]
    focus_metric: str | None = None

class AnalysisPlan(_Model):
    route: Literal["analysis"] = "analysis"
    analysis: AnalysisSpec
    confidence: float
    reasoning: str = ""
```

Execution: `analysis.py` runs each step through the **existing** compiler/executor (concurrently, one connection each), then hands the step results to a composer keyed on `compose`. Every number still comes from SQL; the LLM writes prose over pre-computed figures and never sees raw rows for `sensitive` sources.

Response shape: `AskResponse` gains `charts: list[ChartSpec]` and `narrative: str`. `chart` stays for single-result answers so nothing existing breaks.

**Composers:**
- `briefing` — N KPI steps → headline + ranked "what's notable" list (Q1, 19, 36)
- `drivers` — see 3.2
- `funnel` — ordered stage counts → conversion card (Q15, 16)
- `quadrant` — two metrics × one dimension → scatter with named quadrants (Q18: growth vs. credit quality)
- `vs_target` — see 3.3
- `cohort` — vintage matrix (Q24)

**Preset analyses.** Because `AnalysisSpec` is data, the high-value recurring questions ship as YAML presets (`catalog/defs/analyses/*.yaml`) rather than depending on the model to compose them. `portfolio_health`, `morning_briefing`, `collections_focus`, `funnel_health`, `concentration`. The planner's job shrinks to *picking a preset and binding its period/filters* — far more reliable than freeform composition, and each preset is a golden test.

*Files:* `nlq/analysis.py` (new), `nlq/contracts.py`, `nlq/planner.py`, `nlq/llm/schemas.py`, `nlq/llm/prompts.py`, `nlq/ask.py`, `catalog/defs/analyses/`.

### 3.2 Driver decomposition — the "why" engine (C2)

New deterministic service `nlq/drivers.py`. Given a metric, two periods, and a set of candidate dimensions:

1. Run the metric split by each candidate dimension for both periods.
2. For each member: `contribution = Δ_member`; `share = Δ_member / Δ_total`.
3. For ratio metrics (`grain: ratio` — PAR, collection efficiency, NPA), decompose into **mix effect** (weights changed) vs. **rate effect** (member ratios changed). Recomputing from numerator/denominator is already a catalog invariant, so this is exact rather than an approximation.
4. Rank by |contribution|, cut at 80% cumulative or top 6, roll the rest into "all others".
5. Recurse one level into the top contributor if a drill path exists (3.4).

Output: a **waterfall** `ChartType` (total Δ → contributors → new total) plus a templated sentence: *"Collection efficiency fell 4.2pp. 3.1pp of that is Branch 7 (rate effect, its efficiency fell 19pp on a stable book); 0.8pp is mix — gold loans shrank as a share."*

> Note: `contracts.py` currently documents waterfall as deliberately absent because "no question behind it in this catalog." That is no longer true — `drivers` is exactly the question behind it. Add it with that justification recorded.

This single engine answers Q2, 7, 11, 20, 25, 31, 38 and the "why" rung of every drill chain.

*Files:* `nlq/drivers.py` (new), `nlq/charts.py` (waterfall builder), `nlq/contracts.py`, frontend `WaterfallCard.tsx`.

### 3.3 Plan & target layer (C3)

- New table `public.plan_targets(fy, month, metric_id, branch, product, target_value, source, loaded_at)` — loaded from the client spreadsheet via an admin upload, versioned, with lineage (`source` names the file and row).
- New catalog file `catalog/defs/targets.yaml` registering a `target_<metric>` companion for each metric that has a plan line.
- `QuerySpec` gains `compare_to_target: bool`. When set, the compiler joins `plan_targets` at the query's grain and the chart builder emits a **variance** card: actual, target, Δ, Δ%, attainment %, and RAG status from thresholds in `targets.yaml`.
- A `plan` source in `sources.py` so "are we on track?" routes there.

Guardrail: if no target row exists for the requested slice, say so explicitly. Never interpolate a target — an invented target is worse than no answer.

*Files:* `services/plan_targets.py` (new), `catalog/defs/targets.yaml` (new), `nlq/compiler.py`, `nlq/charts.py`, `api/routes/admin.py` (upload).

### 3.4 Declarative drill graph — the chain (C1 + UX)

Replace the hardcoded ladder in `charts.py:642` with `catalog/defs/drill.yaml`:

```yaml
paths:
  - id: portfolio_geo
    label: Where
    levels: [region, branch, agent]       # region activates when the branch master lands
  - id: portfolio_what
    label: What
    levels: [product, scheme]
  - id: portfolio_who
    label: Who
    levels: [segment, borrower, loan_account]
terminal:
  entity: loan_account                    # the last rung is a worklist, not a chart
transitions:
  - from_any_level: true
    offer: [why, worklist]                # every level can ask "why" or "act"
```

The drill engine then offers, at every level, three kinds of next step:
1. **Deeper** — next level on the same path (branch → agent)
2. **Sideways** — first level of another path (branch → product)
3. **Explain / Act** — `why` (3.2) or `worklist` (3.5)

This is generated from the current `QuerySpec` + the graph, so the answer always carries its own next questions. The frontend renders them as chips under each card; clicking one is a normal `/nlq/execute` call with a derived spec — **no LLM in the loop**, so drilling is instant and cannot go wrong.

Your example chain becomes, end to end:

| Turn | Mechanism |
|---|---|
| "Why are collections down?" | `analysis` route → `drivers` composer |
| "Which regions?" | drill: `portfolio_geo[0]` (needs branch master) |
| "Which branches?" | drill: `portfolio_geo[1]` |
| "Which customer segments?" | sideways: `portfolio_who[0]` |
| "Which accounts?" | terminal: worklist card |
| "Why are those accounts not paying?" | per-account reason attribution from schedule + repayment history |
| "What action should we take?" | playbook lookup (3.5) |
| "Create today's collection priority list." | worklist preset, saved and exportable |

*Files:* `nlq/drilldown.py` (new), `catalog/defs/drill.yaml` (new), `nlq/charts.py`, `nlq/conversation.py`, frontend `NextQuestions.tsx` + `DrillBreadcrumb.tsx`.

### 3.5 Worklists and actions — where the chain ends (Q29, 35, 23)

An answer that stops at a chart is not usable by a collections team.

- New `card_type: "worklist"` — a ranked, account-level list with the reason each row is on it, sorted by a **transparent, rules-based priority score** defined in `catalog/defs/playbooks.yaml` (e.g. `0.4×overdue_amount_norm + 0.3×bucket_severity + 0.2×days_since_last_payment_norm + 0.1×ticket_size_norm`). Every weight visible in the lineage panel, every component clickable to its own drill.
- **Early-warning rules** (Q23) as YAML predicates over data we hold: first-instalment default, 2+ consecutive part-payments, bucket roll-forward two months running, sudden drop in payment ratio, schedule vs. actual divergence. Rules — not a model — so each flag states its own reason.
- **Persisted worklists** — `public.worklists` + `worklist_items` with assignment and status, so "today's priority list" is a durable object, exportable to CSV, and re-generable tomorrow.
- **Playbook lookup** (Q34) maps segment × bucket → recommended action from a client-ratified config. Config, not model judgement — the assistant retrieves the bank's own policy rather than inventing collections advice.

*Files:* `services/worklists/` (new: `rules.py`, `score.py`, `store.py`), `catalog/defs/playbooks.yaml`, `catalog/defs/ews_rules.yaml`, frontend `WorklistCard.tsx`.

### 3.6 Signals engine — standing findings (C4)

A scheduled scan (nightly + intraday for collections) over metric × dimension combinations:

- **Statistical:** z-score vs. trailing 8-period baseline, step changes, trend breaks, rank movements.
- **Threshold:** breaches of `targets.yaml` RAG bands and of regulatory/prudential limits.
- **Structural:** concentration (HHI, top-10 share) crossing policy limits — this *is* Q27.
- **Data health:** freshness, row-count deltas, null-rate spikes, reconciliation breaks — this *is* Q45, and it is the honest answer to "which data issues are affecting performance."

Findings land in `public.signals(detected_at, scope, metric, dimension, member, severity, direction, magnitude, baseline, spec_json, status)`, each carrying the `QuerySpec` that produced it — so every signal is one click from its evidence and its drill chain.

This makes Q8, 9, 10, 26, 41, 44, 45 answerable as *retrieval over pre-computed findings*, and it turns Q1's "5 things I need to know" from an open-ended generation into a ranked query over `signals` — which is why it will actually be trustworthy.

*Files:* `services/signals/` (new: `scan.py`, `detectors.py`, `store.py`, `rules.yaml`), a scheduler entry, new `signals` source in `sources.py` + node in `nodes.py`.

### 3.7 Prediction — narrow, governed, and clearly labelled (Q22, 28, 30)

The planner currently refuses all predictive questions (`prompts.py:69`). That is the right default and should stay the default for freeform forecasting. Relax it in exactly one place: a **registered, versioned, back-tested model** may answer.

- Scope: a delinquency-propensity score (30/60/90-day) and a payment-propensity score, trained on repayment history + schedule + vintage.
- Requires T3 data (`GENLNRCPT`, `LNACLED`) to be meaningful — payment behaviour is the signal.
- Delivered as a catalog metric with `grain: model_estimate`, always rendered with model version, training window, back-test AUC/KS and a top-features explanation on the card.
- Refusal logic changes from "any forecast" to "any forecast **not** produced by a registered model."

Sequence this **last**. Shipping a score before the ledger data exists produces a confident number nobody can defend — the fastest way to lose a director's trust in the whole product.

---

## 4. Conversation layer changes

`conversation.py` already does the hard part: a persisted anchor spec, structural follow-ups that skip the LLM, and visible sticky filters. It needs extending, not replacing.

1. **New structural patterns** — `why`, `why is that`, `which <dimension>`, `drill into <member>`, `show me the accounts`, `what should we do`, `who`. Each maps to a drill-graph transition or the driver engine. Still zero LLM calls.
2. **Deeper anchor** — carry the drill *path* (breadcrumb), not just the current spec, so "go back up" and "compare to the other branch" work.
3. **Longer memory for drilling** — `MAX_TURNS = 5` is too short for an eight-step chain; raise to 12 for structural turns, which cost no tokens. The workbench compaction pipeline (already built) handles the LLM-side budget.
4. **Persona presets** — CEO / Sales / Risk / Collections / Finance. A persona sets the default period, the preferred analyses, and the KPI set of the morning briefing. Surfaced as a switcher in the workbench header.
5. **Answer-carries-next-questions** — every card returns 3–5 chips from the drill graph, plus any `signals` attached to the slice on screen. This is what makes the assistant feel like it is thinking ahead rather than waiting.

---

## 5. Phasing

| Phase | Duration | Ships | Questions unlocked (cumulative) |
|---|---|---|---|
| **0 — Baseline** | 1 wk | 50-question eval harness extending `tests/nlq/golden/questions.yaml` and `tests/workbench/golden/routes.yaml`; each question labelled with its expected route, composer and tier. Client feed request sent (plan + branch master). | measures the true 8–10 we answer today |
| **1 — Chain** ✅ *shipped* | 2–3 wk | Drill graph (3.4), extended conversation patterns (4.1–4.3), next-question chips. | ~16 |
| **2 — Why** ✅ *shipped* | 2–3 wk | Driver decomposition + waterfall (3.2). | ~24 |
| **3 — Compose** | 2–3 wk | `analysis` route + preset analyses + funnel/quadrant/cohort composers; application-funnel catalog entries from `genlnappl*`; TAT/exception metrics from application dates + `appldocuplddtl`. | ~33 |
| **4 — Act** | 2 wk | Worklists, EWS rules, playbooks (3.5). | ~35 |
| **5 — Standing** | 2–3 wk | Signals engine + morning briefing + persona presets (3.6, 4.4). | ~35 answered *better*; Q8/9/10 become genuinely good |
| **6 — Plan** | 1–2 wk | Target layer (3.3) — starts the day the client spreadsheet arrives; can run parallel to 2–5. | ~40 |
| **7 — Predict** | 3 wk | Oracle migration batch (T3) then the governed score (3.7). | ~44 |
| **8 — Feeds** | client-paced | Cost/opex, legal, audit, HR, strategy registers. | 50 |

Phases 1–5 depend on nothing outside the team. Phase 6 onward is gated on the client.

---

## 6. How we know it works

- **Golden eval over all 50**, run in CI. Each question asserts route + composer + which tables the SQL touched — not the exact numbers, which move with the data.
- **Chain eval**: the eight-step collections chain as a single scripted test, asserting that each step is answered structurally (zero LLM calls) and that the breadcrumb stays coherent.
- **Numbers-never-invented invariant**: extend the existing lineage assertions so every figure in a composed narrative traces to a step id. A narrative containing a number absent from any step result fails the build.
- **Refusal honesty**: T4 questions must produce a *specific* refusal naming the missing feed ("I have no budget data — ask the finance team to load the plan file"), never a vague deflection and never a plausible-looking guess. This is the single highest-trust behaviour in the whole product.

---

## 7. Risks

| Risk | Mitigation |
|---|---|
| Composed briefings become a surface for LLM invention. | Composers are code; the model only writes prose over pre-computed step results and is never shown raw rows for sensitive sources. Numbers-never-invented test in CI. |
| The model composes bad ad-hoc analyses. | Preset analyses in YAML for everything high-value; planner picks and binds rather than composes. |
| The drill chain runs out of levels (no region, no channel). | Ship the drill graph with the levels we have; `region` is one YAML line the day the branch master arrives. |
| Latency of 8–12 step analyses. | Steps run concurrently; the existing plan/result cache keys on `QuerySpec.cache_key()` and already dedupes across steps; SSE streams each card as it lands. |
| Predictive scores erode trust. | Sequenced last, gated on ledger data, versioned with published back-test metrics, always labelled `model_estimate`. |
| Scope: 50 questions reads as 50 features. | It is 7 engines. Track progress by engine, not by question. |
