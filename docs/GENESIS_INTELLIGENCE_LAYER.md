# Genesis Intelligence Layer — Sprint 1 Build Plan

Source: `docs/Moneypal Genesis Intelligence Layer.pdf` (Sprint 1 Briefing, Jul 14 – Aug 3, 2026)

## Why

Moneypal's core systems (LOS/LMS, GL) record transactions but don't answer management
questions ("Is the business becoming stronger?", "What would our regulator worry about?").
Genesis sits **above** those operational systems and continuously interprets them into
intelligence — it does not modify source systems.

## Scope (Sprint 1)

- **Institution type:** Lenders only (client: GICC, Ltd). Architecture must stay generic
  enough to later support Banks and Marketplace Operators, but only Lender intelligence
  ships this sprint.
- **Data sources:**
  - **Prosper** (LOS/LMS) — Oracle data dump, snapshot 30 June 2026. Customers, loans,
    repayments, collections, loan lifecycle, portfolio data.
  - **Tally ERP** (GL) — Chart of accounts, trial balance, journal entries, P&L, balance
    sheet, financial transactions.

## Three Personas

| Persona | Question | Cares about |
|---|---|---|
| **Business** | "How is my business doing?" | Portfolio growth, disbursements, collections, customer growth, product/branch performance, portfolio quality, early warning indicators (defaults/missed repayments and default-risk signalling), business trends, competitor sentiment |
| **Finance** | "How are our investments doing?" | Financial metrics, ROI per portfolio |
| **GRC** | "What does the regulator think about us?" | Due regulatory submissions, as-on-date/filed returns, regulatory ratios, portfolio concentration, overdue accounts, provisioning, internal controls, policy breaches, risk indicators, audit readiness, compliance status — should feel like a regulator looking over the institution's shoulder |

## What to Build — Three Modules

### Module 1: Economic Intelligence
Health of the lending business — growth, product performance, collections, risk.
**Output:** Business Dashboard, Portfolio Dashboard, Growth Dashboard, Collections Dashboard.

### Module 2: Competitive Intelligence
**Not** external competitor benchmarking in Sprint 1 — compare the institution against
itself: month/quarter/year-over-year, branch/product/officer comparisons.
**Output:** Trend analysis, variance reports, performance rankings.

### Module 3: Regulatory Intelligence
Generate the DNBS report as on 30-06-2026.
**Note:** Unlike Modules 1 & 2 (which carry forward), this specific deliverable does not
carry into the next sprint — it's a one-time Sprint 1 output.

## Technical Architecture

```
Prosper (LOS/LMS) ─┐
                    ├──> Genesis Intelligence Layer ──┬──> Business Intelligence
Tally ERP (GL)  ────┘                                 ├──> Finance Intelligence
                                                       └──> Regulatory Intelligence
```

Genesis reads operational data and converts it into management intelligence; it never
writes back to Prosper or Tally.

## Design Principle

"Not building reports — building answers." Every chart answers one management question,
every screen reduces decision time, every number should lead naturally to the next
question. Think executive advisor, not database developer.

## Definition of Done

A lender logs into Genesis and can immediately answer:
- **Business:** "How is my business doing?"
- **Finance:** "How are our investments doing?"
- **GRC:** "If the regulator visited today, what would concern them?"

Success = a CEO, CFO, and Compliance Officer can each spend 5 minutes in Genesis and
leave with a better understanding of the institution than before. Not measured by
dashboard count.

## Out of Scope (Sprint 1)

Banks, Marketplace Operators, AI-generated recommendations, predictive analytics,
industry benchmarking, credit bureau integration, RBI reporting automation, workflow
automation, mobile applications. Deferred to future sprints.

---

## Relationship to the Existing Codebase

The repo already has a working Genesis platform (`docs/BUILDATHON_PLAN.md`), but it
solves a **different problem**: it's a RAG layer over unstructured PDFs (macro economy
reports, competitor annual reports, RBI regulations) — `backend/app/services/{macro,
competitive,regulatory}.py`, one Qdrant collection per topic, executive summaries via
Groq.

This Sprint 1 brief is **transactional**, not document-RAG: the inputs are structured
data dumps (Prosper Oracle export, Tally ERP export), and the outputs are computed
metrics/dashboards, not LLM summaries of PDFs. It's a new, parallel pipeline. Reuse from
the existing stack:

- **Shared response contract** (`backend/app/models/schema.py` — `IntelligenceResponse`
  with `source`, `ai_note`, `confidence`) — reuse this shape for consistency, but most
  Module 1/2 numbers are *facts* computed from ledger/loan data, not AI interpretation,
  so `ai_note` should mostly read "Computed directly from Prosper/Tally source data" and
  `confidence` will almost always be `high`.
- **`backend/app/services/intelligence.py`** (dashboard aggregation, recent items, action
  items) is the right home for a new "Recently Updated" feed once Genesis dashboards
  exist.
- Existing competitive module (`Team B`) already does self-vs-market intelligence for 11
  institutions — informative pattern for Module 2, but Module 2 in this sprint is
  strictly **self-comparison** (GICC vs GICC, no external institutions), so it needs a
  new service, not a reuse of `competitive.py`.
- The `registry/` config-driven pattern (JSON per institution/regulation, "add a file, no
  code change") is worth carrying into Genesis for **branches / products / loan officers**
  — e.g. `registry/branches/*.json` — so Module 2 comparisons don't hardcode entity lists.

---

## Proposed Data Model

### Ingestion layer (new)
Both sources are point-in-time dumps (Prosper snapshot 30-Jun-2026, Tally export), not
live feeds — Sprint 1 does **not** need real-time sync. Land them as-is, transform once.

```
backend/data/genesis/
├── prosper/          # raw Oracle dump exports (CSV/XLSX per table)
└── tally/             # raw Tally XML/CSV exports
```

```
backend/app/services/genesis/
├── ingest_prosper.py   # load raw dump -> normalized tables (customers, loans, repayments, collections)
├── ingest_tally.py     # load raw GL export -> normalized tables (coa, journals, trial_balance)
├── warehouse.py        # SQLite/Postgres warehouse the dashboards query against
└── metrics.py          # pure functions: growth_rate(), par_30(), roi_by_portfolio(), etc.
```

### Core entities (from Prosper)

| Table | Key fields | Feeds |
|---|---|---|
| `customers` | customer_id, branch_id, onboarded_date, segment | Customer growth |
| `loans` | loan_id, customer_id, product_id, branch_id, officer_id, disbursed_amount, disbursed_date, status, tenure | Disbursements, portfolio growth, product/branch performance |
| `repayments` | repayment_id, loan_id, due_date, paid_date, due_amount, paid_amount | Collections, PAR/overdue |
| `collections` | collection_id, loan_id, collected_date, amount, method | Collections efficiency |
| `loan_lifecycle` | loan_id, stage, stage_date | Early warning indicators, default signalling |
| `portfolio` | as_of_date, branch_id, product_id, outstanding_principal, par_30/60/90 | Portfolio quality |

### Core entities (from Tally)

| Table | Key fields | Feeds |
|---|---|---|
| `chart_of_accounts` | account_id, name, type, parent_id | GL structure for all financial metrics |
| `journal_entries` | entry_id, account_id, date, debit, credit, narration | ROI, financial metrics |
| `trial_balance` | account_id, as_of_date, balance | P&L / balance sheet snapshots |
| `profit_loss` | account_id, period, amount | Finance module |
| `balance_sheet` | account_id, as_of_date, amount | Finance module |

### Derived / computed layer
Metrics are **computed, not stored as opinions** — e.g. `par_30 = overdue_30d_principal /
total_outstanding_principal`, `roi = net_income(portfolio) / avg_investment(portfolio)`.
Keep `metrics.py` as pure functions over the warehouse tables so every dashboard number
is traceable back to a formula and a source table (satisfies "every number should lead
naturally to the next question").

---

## Dashboard-Level Spec

### Module 1 — Economic Intelligence

**Business Dashboard** (top-level, answers "How is my business doing?")
| Tile | Question | Calculation | Source |
|---|---|---|---|
| Portfolio Growth (MoM/YoY) | Is lending growing? | Δ outstanding_principal over period | `portfolio` |
| Disbursement Trend | Are we disbursing more/less? | Σ disbursed_amount by period | `loans` |
| Collection Efficiency | Are we collecting well? | Σ paid_amount / Σ due_amount | `repayments` |
| New Customers | Where is growth coming from? | count(customers) by branch/period | `customers` |
| Portfolio at Risk (PAR 30/60/90) | Where is risk increasing? | overdue principal buckets / outstanding | `portfolio`, `repayments` |

**Portfolio Dashboard**
- Outstanding by product, by branch (stacked bar)
- Product performance ranking (disbursed volume, PAR, avg ticket size)
- Portfolio quality trend line (PAR 30/60/90 over last 12 months)

**Growth Dashboard**
- Disbursement growth rate (MoM, QoQ, YoY)
- Customer growth funnel (new vs repeat borrowers)
- Branch-level growth heatmap

**Collections Dashboard**
- Collections vs due, by branch/officer
- Days Past Due (DPD) distribution
- Early warning list: loans with 1-2 missed payments (leading indicator, not prediction — Sprint 1 excludes predictive analytics, so this is a rules-based flag: e.g. "2+ consecutive missed repayments," not a model)

### Module 2 — Competitive (Self) Intelligence

Not cross-institution — GICC vs GICC across time and internal dimensions.

| View | Comparison | Output |
|---|---|---|
| Period-over-period | This month/quarter/year vs prior | Variance report (Δ and Δ%) per key metric |
| Branch comparison | All branches, same period | Ranked table: disbursement, collection efficiency, PAR |
| Product comparison | All products, same period | Ranked table: volume, growth, PAR |
| Officer comparison | All loan officers, same period | Ranked table: disbursement, collection rate |

Implementation: one generic `compare(dimension, metric, period_a, period_b)` function
in `metrics.py` reused across branch/product/officer/time comparisons — avoid four
near-duplicate services.

### Module 3 — Regulatory Intelligence

Single deliverable: **DNBS report as on 30-06-2026**. This is a fixed-format regulatory
return (RBI's DNBS return for NBFCs) — needs the exact schedule/field layout of that
specific return mapped from `portfolio`, `loans`, `trial_balance`. Because this doesn't
carry into Sprint 2, treat it as a **one-off report generator script**, not a dashboard:
`backend/scripts/generate_dnbs_report.py --as-of 2026-06-30` producing the filled return
(PDF/XLS in the prescribed DNBS layout). Don't over-invest in a UI for it.

The GRC "regulator looking over your shoulder" framing applies more directly to a
**dashboard view** built on top of the same warehouse (portfolio concentration, overdue
accounts, provisioning, policy breach flags) — worth doing alongside the DNBS script
since the underlying data is the same, even though it's not explicitly required by the
brief's three deliverables.

---

## Proposed Tech Stack (Extending Existing Stack)

| Layer | Choice | Why |
|---|---|---|
| Ingestion | Python scripts, pandas/polars | Prosper/Tally dumps are one-time batch loads (CSV/XLSX/XML), no streaming needed |
| Warehouse | SQLite for Sprint 1 (single snapshot, single client) → Postgres when multi-tenant (Banks/Marketplace) lands | Avoid infra overhead for a one-time snapshot; schema is portable to Postgres later |
| Backend | New `backend/app/api/routes/genesis.py` + `services/genesis/` inside the **existing** FastAPI app | Keeps one unified service instead of spinning up a 4th port |
| Frontend | New routes under existing Next.js app (`frontend/app/genesis/...`), reusing `IntelligenceCard`/`LoadingCard` components | Dashboards are charts, not RAG cards — will need new `MetricTile`, `TrendChart`, `RankingTable` components (recharts, already a planned dependency) |
| Regulatory report | Standalone script producing DNBS output file, invoked manually or via a `/genesis/regulatory/dnbs` trigger endpoint | One-off deliverable, no need for a persistent service |

## Your Role (Platform Engineer)

Per `docs/PLATFORM_ENGINEER_WEEK1.md`, you're not one of the module owners designing
Business/Finance/GRC logic — you're the infra/plumbing role that makes their designs
runnable and compatible, without breaking the live Gen 1 app. Applied to this sprint:

- **Own the warehouse.** Stand up the SQLite/Postgres store that `ingest_prosper.py` /
  `ingest_tally.py` write into and that `metrics.py` and the dashboards query — the
  module owners design the schema/metrics, you make sure there's a real place for it to
  run.
- **Own the drop zone.** Provide `backend/data/genesis/{prosper,tally}/` (or equivalent)
  as a real, working location to land the Oracle dump and Tally export so ingestion can
  be tested against real files, not assumptions.
- **Wire it into the existing app, safely.** Land the new `genesis.py` routes/service
  inside the current FastAPI app and Next.js frontend without disrupting the live client
  app (Gen 1) — new schema/namespace/branch, not touching production paths.
- **Catch cross-spec mismatches.** If the Prosper ingestion's field names don't match
  what the Module 1/2 metric functions expect, or the DNBS field mapping assumes a
  `portfolio` column that ingestion doesn't produce, you're the one who notices first
  because you're trying to wire it end-to-end — flag it, don't just quietly patch around
  it.
- **Not your call:** the metric formulas (PAR calculation, ROI definition), the dashboard
  tile layouts, or the DNBS field mapping itself — those are module-owner decisions, per
  the "you don't design the business logic" boundary in the Week 1 doc.
- **Open question to raise with the PM:** is this Sprint 1 (Prosper/Tally dashboards) a
  separate, simpler pipeline running in parallel to the NEST/NAB event-sourcing work, or
  does it sit on top of NAB once that exists? That determines whether you're provisioning
  a plain warehouse now or an event store that Genesis later reads through.

---

## Open Questions Before Implementation

1. What exact file formats are the Prosper Oracle dump and Tally export in (CSV table
   dump vs XML)? Determines the ingestion parser.
2. Is there a fixed DNBS return template/schema to map fields against, or does it need to
   be sourced from RBI separately?
3. Single-tenant (GICC only) for Sprint 1 — confirm no need to abstract institution_id
   yet, even though the brief says the architecture should stay generic for Banks/
   Marketplace Operators later.
