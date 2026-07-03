# Moneypal Genesis Layer — Buildathon Master Plan
**Duration:** 24 Hours | **Delivery:** Tomorrow
**4 Teams: You (Integration Lead) + Team A (Macro) + Team B (Competitive) + Team C (Regulatory)**

---

## Tech Stack

| Layer | Choice | Why |
|-------|--------|-----|
| Frontend | Next.js 15 + Tailwind CSS + shadcn/ui | Fast to build, responsive, clean |
| Backend | FastAPI (Python 3.11) — 3 separate services | One per module, easy to run |
| Vector Store | Qdrant (Docker) | Shared across all 3 modules, production-grade, rich filtering |
| Embeddings | BAAI/bge-m3 (local via sentence-transformers) | 8192-token context — handles long financial PDFs |
| LLM | Groq API — llama-3.3-70b-versatile | Fast inference, free tier, executive-quality summaries |
| RAG Approach | Direct — no framework | qdrant-client + sentence-transformers + groq + pypdf only. Full control, easy to debug, looks production-grade to judges |
| Auth | Hardcoded JWT — 4 demo users | Sufficient for buildathon |

---

## Port Allocation

```
Frontend       →  localhost:3000
Backend (App)  →  localhost:8000  (unified: /macro, /competitive, /regulatory)
Qdrant         →  localhost:6333  (shared by all modules)
```

---

## Demo Credentials

| Username | Password | Role | Landing Page |
|----------|----------|------|--------------|
| moneypal_admin | admin123 | Moneypal Administrator | Full platform |
| gicc_admin | admin123 | GICC Administrator | Dashboard + competitive + regulatory |
| gicc_policy | policy123 | GICC Policy Maker | Regulatory + competitive |
| gicc_director | director123 | GICC Director | Executive dashboard only |

---

## Shared Response Contract (All Teams Must Follow)

Every API endpoint across all 3 modules returns the same shape:

- **title** — name of the intelligence item
- **summary** — AI-generated executive summary (3–4 paragraphs max)
- **key_points** — 3 to 5 bullet points
- **source** — document name + URL back to original source
- **ai_note** — one sentence distinguishing AI interpretation from sourced fact
- **last_updated** — date
- **confidence** — high / medium / low

> This is the most important alignment to do in Hour 0. Integration Lead defines it, all teams follow it.

---

## Folder Structure

```
moneypal-genesis/
├── packages/genesis_core/ ← Shared engine (schema, direct RAG helpers)
├── backend/               ← Unified FastAPI instance (All Teams)
│   ├── app/
│   │   ├── api/routes/    ← macro.py (A), competitive.py (B), regulatory.py (C)
│   │   └── services/      ← macro.py (A), competitive.py (B), regulatory.py (C)
│   ├── registry/          ← institutions/ (B), regulations/ (C)
│   ├── scripts/           ← ingest.py (unified ingestion script)
│   └── data/              ← macro/, competitive/, regulatory/ (local PDFs, gitignored)
└── frontend/              ← Next.js Web Console (Integration Lead)
```

---

---

# HOUR 0–2: Foundation (All Teams Together)

Do not split yet. Everyone does this first.

### Infrastructure
- Start Qdrant via Docker — one person runs it, everyone points to that machine's IP
- Verify it's up by hitting the health endpoint

### Dependency Download (Critical — Do This Now)
- Download the bge-m3 embedding model on **every machine** — it's ~570MB, do it in Hour 0 not mid-sprint
- Install Python packages: `fastapi uvicorn qdrant-client sentence-transformers groq python-dotenv pypdf`
- Install Node packages for frontend: Next.js 15, shadcn/ui, recharts, lucide-react
- No RAG framework needed — we go Direct (qdrant-client + sentence-transformers + groq only)

### Repo Setup
- Create monorepo, push all folder structure
- Integration Lead commits two shared files — all teams pull before starting:
  - `shared/schema.py` — the response contract (Pydantic model)
  - `shared/rag_helpers.py` — three functions: `embed_text()`, `search_qdrant()`, `generate_with_groq()`. Teams import these, do not rewrite them
- Everyone confirms their FastAPI service starts and returns 200 on `/health`

### Environment
- Create a `.env` file with `GROQ_API_KEY` — everyone uses the same key
- Set Qdrant host and port in env

> **End of Hour 2:** Qdrant running. bge-m3 downloaded everywhere. Unified FastAPI service starts clean on 8000. Next.js runs on 3000.

---

---

# TEAM A — Module 1: Macro-economic Intelligence
**Port 8000 (/macro) | Qdrant collection: `macro_intel`**

## What You Build
An executive intelligence service covering India's macro economy and Karnataka's MSME lending landscape.

---

## Hour 2–5: Data Collection + Ingestion

### Documents to Download
- Government of India Economic Survey — indiabudget.gov.in/economicsurvey
- MOSPI data — mospi.gov.in
- Ministry of MSME Annual Report — msme.gov.in
- Indian Economy presentation — DocSend link provided in brief
- RBI Annual Report (credit growth section) — rbi.org.in

Save all PDFs into your `backend/data/macro/` folder. Run ingestion to index everything: `python scripts/ingest.py macro`.

---

## Hour 5–14: Build the 4 Endpoints

### 1. `/macro/snapshot` — Economic Snapshot Widget
Answers: What is the current state of India's economy relevant to MSME lending?
- India GDP growth rate (current year)
- Inflation rate
- Credit growth in MSME sector
- Employment trends
- Source: Economic Survey + RBI Annual Report

### 2. `/macro/karnataka` — Karnataka Economy
Answers: What is Karnataka's economic landscape for lending?
- Karnataka GSDP and growth rate
- Key sectors: manufacturing, agriculture, services, IT
- MSME unit count and employment in Karnataka
- Financial inclusion status
- Active government MSME lending schemes (state + central)
- Source: MOSPI + Karnataka state budget documents

### 3. `/macro/msme` — MSME Lending Trends
Answers: What are the MSME credit trends nationally and in Karnataka?
- Total MSME credit outstanding
- NPA levels in the MSME segment
- Formal vs informal credit split
- Digital lending penetration
- Key lending challenges: collateral, documentation, credit history
- Source: MSME Ministry Annual Report + SIDBI data

### 4. `/macro/briefing` — AI Executive Brief
Answers: What is the single most important economic briefing for GICC leadership today?
This is the most important endpoint. It synthesises all 3 above into one crisp director-level briefing covering:
- Headline: one sentence on the most critical economic development
- Context: macro environment for MSME lending
- Karnataka focus: local lending opportunity
- Risk watch: 2–3 bullet risks
- Opportunity: one strategic opportunity for GICC
Source: cite all documents used

---

## AI Note Rule (All 4 Endpoints)
Every response must include a clear `ai_note` that says something like:
> "Summary generated from Economic Survey 2024. GDP figures are sourced from official documents. Forward-looking statements on credit growth are AI interpretation."

---

## Hour 14: Handoff Checklist
- All 4 endpoints return data in the shared schema format
- Every response has `source.url` pointing to the real document
- Every response has `ai_note` distinguishing fact from AI interpretation
- CORS is open so frontend can call you

---

---

# TEAM B — Module 2: Competitive Intelligence
**Port 8000 (/competitive) | Qdrant: one collection per institution e.g. `comp_kinara_capital`**

## What You Build
An intelligence service mapping the competitive lending landscape in Karnataka with profiles and AI-generated SWOT for 11 institutions.

---

## Hour 2–4: Institution Config System

Create one JSON file per institution inside the `backend/registry/institutions/` folder. This is how you satisfy the brief's requirement that "institutions can be added without software changes" — adding a new institution means adding a JSON file, nothing else.

Each JSON must contain:
- id (slug, e.g. `kinara_capital`)
- name
- type (NBFC, Co-operative Bank, State Financial Institution, etc.)
- website
- headquarters
- msme_focus (true/false)
- source_docs (list of filenames in your data folder)
- source_urls (website URL + annual report URL)
- qdrant_collection name

### Institutions to Create Configs For
1. Karnataka State Financial Corporation (KSFC)
2. Karnataka State Co-operative Apex Bank
3. Kinara Capital
4. National Co-operative Bank
5. Belagavi District Central Co-operative Bank
6. Belgaum Industrial Co-operative Bank
7. Kaujalgi Urban Co-operative Bank
8. Bellary Urban Co-operative Bank
9. Bhatkal Urban Co-operative Bank
10. South Canara District Central Co-operative Bank — scdcc.bank.in
11. SIDBI — sidbi.in/en (benchmark, not competitor)

---

## Hour 4–7: Data Collection + Ingestion

For each institution collect whatever is publicly available and save to `data/{institution_id}/`:
- Website About / Products page (save as .txt by copying content)
- Annual Report PDF (search "{name} annual report 2023 filetype:pdf")
- Credit rating reports if available
- News articles (paste relevant content as .txt)

Run ingestion for each institution: `python scripts/ingest.py competitive`.

---

## Hour 7–14: Build the 4 Endpoints

### 1. `GET /competitive/institutions` — Institution List
Returns a list of all institutions (id, name, type) loaded from the JSON configs. No RAG needed — just reads the JSON folder.

### 2. `GET /competitive/institutions/{id}` — Full Institution Profile
For the given institution, run RAG over its Qdrant collection and generate:
- Overview: what they do, who they serve
- Key products and loan types
- MSME lending focus: ticket sizes, segments, geography
- Public financial highlights: AUM, loan book, NPA if available
- Geographic presence: districts, branches
- Strategic positioning: what makes them distinctive
Source: cite the institution's public documents

### 3. `GET /competitive/institutions/{id}/swot` — AI SWOT Analysis
For the given institution, generate a SWOT from a competitor analysis perspective. Critical detail: every SWOT point must be labeled either `[FACT]` if it comes from a document, or `[AI INTERPRETATION]` if it is inferred. End with a "Strategic Observation" paragraph on what GICC should know about this competitor.

### 4. `GET /competitive/landscape` — Competitive Landscape Overview
Cross-institution executive summary answering:
- Who are the major players and how are they positioned?
- What products and interest rate ranges are typical?
- Which customer segments are most contested?
- Where are the gaps — underserved areas or segments?
- What are the strategic implications for GICC?

---

## Hour 14: Handoff Checklist
- All 4 endpoints working and returning shared schema format
- SWOT clearly labels [FACT] vs [AI INTERPRETATION] on every point
- Adding a new institution only requires a new JSON file — no Python changes
- CORS open for frontend

---

---

# TEAM C — Module 3: Regulatory Intelligence
**Port 8000 (/regulatory) | Qdrant: one collection per category e.g. `reg_digital_lending`**

## What You Build
An executive regulatory intelligence service covering RBI regulations applicable to NBFCs with assets below ₹500 crore, specifically relevant to GICC.

---

## Hour 2–4: Regulation Config System

Create one JSON file per regulation category inside the `backend/registry/regulations/` folder.

Each JSON must contain:
- id (slug, e.g. `digital_lending`)
- display_name
- category
- rbi_url (link to the actual RBI page)
- source_doc (PDF filename in your data folder)
- qdrant_collection name
- applicability (who this applies to)
- effective_date

### Categories to Create Configs For
1. Master Directions (NBFC) — main source URL provided in brief
2. Prudential Norms
3. Fair Practices Code
4. KYC / AML
5. Digital Lending
6. Outsourcing
7. Governance
8. Information Security
9. Circulars and Notifications (recent ones)

---

## Hour 4–7: Data Collection + Ingestion

### Primary Source
RBI Master Directions for NBFCs — URL provided in brief. Download the PDF.

### Also Download
- Digital Lending Guidelines PDF
- KYC Master Directions PDF
- Fair Practices Code PDF
- Information Security Directions PDF
- Outsourcing Guidelines PDF
- Any recent RBI circulars relevant to small NBFCs

All from rbi.org.in. Run ingestion for each category: `python scripts/ingest.py regulatory`.

---

## Hour 7–14: Build the 3 Endpoints

### 1. `GET /regulatory/categories` — Category List
Returns all regulation categories from JSON configs. No RAG needed — just reads the folder. Returns id, display_name, applicability, effective_date for each.

### 2. `GET /regulatory/{category_id}` — Regulation Detail
For the given category, run RAG and generate a structured executive briefing covering exactly these 5 sections:
- **Executive Summary** — 2–3 sentences on what this regulation does
- **Applicability** — Who does it apply to? Specifically address NBFCs below ₹500 crore
- **Business Impact** — What does GICC need to change or comply with? Be specific
- **Compliance Actions** — 3–5 actionable bullet points
- **Effective Date** — from the config JSON

Tone: actionable, not legal. Written for a director, not a lawyer.
Source: cite specific sections of the RBI document.

### 3. `GET /regulatory/alerts` — Regulatory Alerts Widget
Returns a hardcoded list of 3–5 current high-priority regulatory alerts for the dashboard. Each alert has:
- title
- category
- severity (high / medium)
- one-sentence summary
- action required
- source_url back to RBI
- ai_note

This is for the dashboard widget. Keep it punchy — one line per alert.

---

## Hour 14: Handoff Checklist
- All 3 endpoints working and returning shared schema format
- Regulation detail follows the 5-section structure exactly
- Alerts are concise and actionable
- Every response links back to the RBI source URL
- CORS open for frontend

---

---

# YOU — Integration Lead: Web Application
**Frontend: Next.js 15 + Tailwind + shadcn/ui | Port 3000**

## What You Build
The full web application shell: login, role-based routing, dashboard, and all three module pages. You wire together everything the three module teams produce.

---

## Hour 2–4: Auth + App Shell

### Login Page
- Simple username + password form
- Validate against the 4 hardcoded demo users
- Store role in localStorage
- Redirect to appropriate landing page per role

### App Shell (Layout)
- Header with Moneypal logo (left) + "Genesis Intelligence Console" (centre) + GICC logo (right)
- Sidebar navigation — links shown depend on user role
- Footer: "Powered by Aroha Corporate Intelligence Framework"
- RoleGuard component: wraps every page, redirects to login if no valid session

### Navigation per Role
- **GICC Director** → Dashboard only
- **GICC Policy Maker** → Regulatory, Competitive
- **GICC Administrator** → Dashboard, Competitive, Regulatory
- **Moneypal Administrator** → Everything

---

## Hour 4–8: Shared Components (Build These First — All Pages Use Them)

### IntelligenceCard
The core display unit used on every page. Shows:
- Title + confidence badge (green/yellow/red)
- AI-generated summary
- Key points as bullet list
- Source link with external link icon (always visible)
- AI note in small italic text at bottom (always visible)

### SourceBadge
Small inline component — document name as a clickable link that opens the source URL in a new tab. Appears on every AI-generated piece of content.

### SWOTCard
Four-quadrant card showing Strengths (green), Weaknesses (red), Opportunities (blue), Threats (orange). Each quadrant lists bullet points from the SWOT endpoint response.

### AIBriefPanel
Full-width panel for the executive briefing — larger text, headline prominent, structured sections visible.

### LoadingCard
Skeleton placeholder shown while API calls are in flight — prevents layout shift.

---

## Hour 8–10: Dashboard Page (Most Important)

The landing page for GICC Director. Answers "What should GICC leadership know today?"

### Layout — 6 Widgets

**Row 1 (2/3 + 1/3 split)**
- AI Executive Brief (large, left) — from `/macro/briefing`
- Regulatory Alerts (right column) — from `/regulatory/alerts`, shown as coloured alert cards

**Row 2 (1/2 + 1/2 split)**
- Economic Snapshot — from `/macro/snapshot`
- Karnataka Lending Landscape — from `/competitive/landscape`

**Row 3 (full width)**
- Recently Updated Intelligence — static list of 4–5 items linking to each module
- Action Items — 3 hardcoded items that look real (e.g. "Review Digital Lending compliance checklist")

### Important Rules for Dashboard
- Use mock/hardcoded data while APIs are not ready — build the UI first
- Every widget must show a SourceBadge linking to the original document
- Every AI insight must show the ai_note below it
- Show loading skeleton while data is fetching

---

## Hour 10–12: Module Pages

### Macro Page (`/macro`)
- 3 cards: Economic Snapshot, Karnataka Economy, MSME Trends
- One full-width AI Executive Brief at the top
- Simple data display, no charts needed (keep it clean)

### Competitive Page (`/competitive`)
- Grid of institution cards (name, type, HQ)
- Click a card → slide-out side panel (shadcn Sheet component) showing:
  - Full institution profile (IntelligenceCard)
  - SWOT (SWOTCard)
  - Source links
- Search/filter bar at top to filter by institution type

### Regulatory Page (`/regulatory`)
- Accordion list — one row per regulation category
- Expand a row → shows the 5-section regulation detail (IntelligenceCard)
- Colour-coded severity badges
- Source link to RBI for each regulation

---

## Hour 12–14: Wire Real APIs

- Replace all mock data with real fetch calls to the 3 module backends
- Test every role — login as each of the 4 users and check navigation is correct
- Verify SourceBadge appears on every AI-generated card
- Verify ai_note appears below every summary

---

## Hour 14–20: Integration + Polish

- Work with each module team to fix any mismatched response formats
- Add error states (if an API is down, show a graceful message not a crash)
- Mobile responsiveness check — Tailwind makes this straightforward
- Consistent spacing, font sizes, and colours across all pages
- Both logos clearly visible in header on all pages

---

---

# 24-Hour Timeline

| Time | You (Integration) | Team A (Macro) | Team B (Competitive) | Team C (Regulatory) |
|------|------------------|----------------|----------------------|---------------------|
| 0–2h | Repo, scaffold Next.js, define shared schema | Setup, download bge-m3 | Setup, create institution JSONs | Setup, create regulation JSONs |
| 2–4h | Login + auth + app shell | Download + ingest PDFs | Download institution data | Download RBI PDFs |
| 4–6h | Dashboard skeleton (mock data) | Build snapshot + karnataka endpoints | Run ingestion | Run ingestion |
| 6–8h | Build shared components | Build MSME + briefing endpoints | Build institution profile endpoint | Build regulation detail endpoint |
| 8–10h | Dashboard page complete | Test + fix endpoints | Build SWOT endpoint | Build alerts endpoint |
| 10–12h | Competitive + Regulatory pages | Polish responses + CORS | Build landscape endpoint | Test all endpoints |
| 12–14h | Wire all real APIs, remove mocks | Handoff | Handoff | Handoff |
| 14–18h | Integration bugs, all 4 role views working | On standby | On standby | On standby |
| 18–20h | Mobile check, visual polish | — | — | — |
| 20–22h | Demo rehearsal | — | — | — |
| 22–24h | DELIVER | — | — | — |

---

# Sync Checkpoints (Integration Lead Owns These)

| Time | What to Check |
|------|---------------|
| Hour 2 | Qdrant running, bge-m3 downloaded everywhere, shared schema committed, all services start |
| Hour 6 | Each module has at least one endpoint returning real non-empty data |
| Hour 10 | All module endpoints done, integration begins with real data |
| Hour 14 | All 4 role views navigable, real data on dashboard |
| Hour 20 | Demo rehearsal complete, all data showing correctly |

---

# Evaluation — Where to Focus

| Area | Weight | How to Score Here |
|------|--------|-------------------|
| Software Architecture | 30% | Monorepo, shared schema, config-driven institution/regulation registry, 3 independent services |
| Product Thinking | 20% | Dashboard answers "what should GICC know today?" — not a data dump |
| User Experience | 20% | Role-based views, clean cards, source badges visible, loading states |
| AI Integration | 15% | Every insight cites source, ai_note on every card distinguishing fact from AI |
| Engineering Quality | 15% | No console errors, consistent naming, schema followed by all teams |

---

# Demo Script (Rehearse This in Hour 22)

**Step 1 — Login as GICC Director**
Go to dashboard → read AI Executive Brief → click source link → show it opens the real document

**Step 2 — Login as GICC Policy Maker**
Go to Regulatory → open Digital Lending → show the 5 sections (summary, applicability, business impact, compliance actions, effective date) → point to source badge and ai_note

**Step 3 — Login as GICC Administrator**
Go to Competitive → click Kinara Capital → open SWOT → show [FACT] vs [AI INTERPRETATION] labels on each point

**Step 4 — Login as Moneypal Administrator**
Show full platform access — all pages accessible

**What to say about architecture (30 seconds):**
"Each module is an independent FastAPI service with its own Qdrant collection. Institutions and regulations are config-driven JSON files — adding a new institution requires zero code changes. Every AI summary cites its source document and explicitly separates factual data from AI interpretation. The shared response schema keeps all three modules in sync with the frontend."

---

# The Single Most Important Thing

> The judges are financial executives evaluating product thinking, not engineers evaluating algorithms.
> The GICC Director dashboard is your showcase.
> Make it answer "What should GICC leadership know today?" clearly, beautifully, and with every insight traced back to its source.
> Everything else supports that one screen.
