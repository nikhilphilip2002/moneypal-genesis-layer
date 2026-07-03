# Team B — Module 2: Competitive Intelligence
**Port: 8002 | Qdrant: one collection per institution | Duration: 24 Hours**

---

## Your Mission

Build the intelligence engine that answers: **"Who are GICC's competitors in Karnataka MSME lending, and what should GICC know about each of them?"**

You are building a competitor analysis tool for financial executives — not a directory listing. Every output should help GICC's leadership understand the competitive landscape and identify their strategic position.

---

## Your 4 API Endpoints

| Endpoint | Purpose | Used Where |
|----------|---------|------------|
| `GET /competitive/institutions` | List all institutions | Institution grid page |
| `GET /competitive/institutions/{id}` | Full profile for one institution | Institution detail drawer |
| `GET /competitive/institutions/{id}/swot` | AI SWOT analysis | SWOT card in drawer |
| `GET /competitive/landscape` | Cross-institution executive overview | Dashboard widget |

---

## Shared Response Format (You Must Follow This)

Every endpoint returns exactly this structure. Copy the schema file from the Integration Lead before starting.

- **title** — name of the intelligence item
- **summary** — AI-generated executive summary (3–4 paragraphs max)
- **key_points** — 3 to 5 bullet points
- **source** — document name + URL back to original source
- **ai_note** — one sentence distinguishing AI interpretation from sourced fact
- **last_updated** — today's date
- **confidence** — high / medium / low

---

---

## HOUR 0–2: Setup (With All Teams)

- Install all Python packages: fastapi, uvicorn, qdrant-client, sentence-transformers, groq, python-dotenv, pypdf
- Download bge-m3 model — run the download script the Integration Lead provides. Do this now, it is 570MB
- Set up `.env` file with `GROQ_API_KEY` and Qdrant host/port
- Confirm FastAPI starts and returns 200 on `/health`
- Pull the shared schema from the repo

---

## HOUR 2–4: Build the Institution Config System

This is the most architecturally important thing you do. The brief explicitly says "institutions must be addable without software changes." Your config-driven JSON system is how you satisfy that requirement — and it is worth significant marks on Software Architecture (30% of evaluation).

---

### How It Works

Every institution is defined by a single JSON file in your `institutions/` folder. Your Python code reads all JSON files from that folder at startup — so adding an institution means dropping in a new JSON file and restarting, with zero code changes.

---

### JSON Structure for Each Institution

Each file must contain these fields:

- **id** — URL-safe slug (e.g. `kinara_capital`, `ksfc`, `sidbi`)
- **name** — Full institution name
- **type** — Classification: `NBFC`, `Co-operative Bank`, `State Financial Institution`, `Development Finance Institution`
- **website** — Official website URL
- **headquarters** — City, State
- **msme_focus** — true or false
- **founded** — Year (if publicly known)
- **source_docs** — List of filenames stored in `data/{id}/` folder
- **source_urls** — Object containing `website` URL and `annual_report` URL if available
- **qdrant_collection** — Name of the Qdrant collection for this institution (e.g. `comp_kinara_capital`)

---

### The 11 Institutions — Create a JSON for Each

**1. Karnataka State Financial Corporation (KSFC)**
- Type: State Financial Institution
- Website: ksfc.in
- Focus: Long-term credit to SSI and MSMEs in Karnataka
- Collection name: `comp_ksfc`

**2. Karnataka State Co-operative Apex Bank (KSCAB)**
- Type: Co-operative Bank (Apex)
- Website: kscab.org
- Focus: Apex body for co-operative credit in Karnataka, agricultural and MSME credit
- Collection name: `comp_kscab`

**3. Kinara Capital**
- Type: NBFC
- Website: kinaracapital.com
- Focus: Collateral-free MSME loans, home-based businesses, micro-manufacturers
- Collection name: `comp_kinara_capital`

**4. National Co-operative Bank**
- Type: Co-operative Bank
- Website: nationalcoopbank.com (search for current URL)
- Focus: Urban co-operative banking, MSME and retail credit
- Collection name: `comp_national_coop`

**5. Belagavi District Central Co-operative Bank**
- Type: District Central Co-operative Bank
- Focus: Agricultural and MSME credit in Belagavi district
- Collection name: `comp_belagavi_dccb`

**6. Belgaum Industrial Co-operative Bank**
- Type: Co-operative Bank
- Focus: Industrial and MSME credit in Belagavi (Belgaum) region
- Collection name: `comp_belgaum_industrial`

**7. Kaujalgi Urban Co-operative Bank**
- Type: Urban Co-operative Bank
- Focus: Urban retail and MSME credit
- Collection name: `comp_kaujalgi`

**8. Bellary Urban Co-operative Bank**
- Type: Urban Co-operative Bank
- Focus: Urban MSME and retail credit in Bellary district
- Collection name: `comp_bellary_urban`

**9. Bhatkal Urban Co-operative Bank**
- Type: Urban Co-operative Bank
- Focus: Coastal Karnataka urban credit, trade finance
- Collection name: `comp_bhatkal_urban`

**10. South Canara District Central Co-operative Bank (SCDCC Bank)**
- Type: District Central Co-operative Bank
- Website: scdcc.bank.in (URL provided in brief)
- Focus: Agricultural and MSME credit in Dakshina Kannada district
- Collection name: `comp_scdcc`

**11. SIDBI**
- Type: Development Finance Institution
- Website: sidbi.in/en (URL provided in brief)
- Focus: MSME ecosystem — refinancing, direct credit, startup funding. Use as benchmark not competitor
- Collection name: `comp_sidbi`

---

## HOUR 4–7: Data Collection

For each institution collect as much publicly available information as possible. Save everything into `data/{institution_id}/` folder.

---

### What to Collect for Each Institution

**Priority 1 — Always try to get:**
- Annual Report PDF — search "{institution name} annual report 2023 filetype:pdf" on Google
- Website About page — copy and paste the text into a `.txt` file
- Website Products/Loans page — copy and paste into a `.txt` file

**Priority 2 — Get if available:**
- Credit rating report (CRISIL, CARE, ICRA, India Ratings)
- Investor presentation PDF
- News articles about the institution — search "{name} news 2023 2024" and paste relevant articles into a `.txt` file
- RBI inspection reports if published

**Priority 3 — Synthesise if nothing else available:**
- If no PDF exists, write a `{id}_summary.txt` with what you know from the website and public sources. Even a 300-word summary is better than nothing for RAG.

---

### Data Collection Split (Suggested)

With 2 people on this module, split the 11 institutions:

**Person 1:** KSFC, KSCAB, Kinara Capital, National Co-op Bank, Belagavi DCCB, SCDCC Bank
**Person 2:** Belgaum Industrial, Kaujalgi Urban, Bellary Urban, Bhatkal Urban, SIDBI

Both run ingestion simultaneously once data is collected.

---

### Realistic Expectations

Some of these institutions are small and have minimal online presence. That is okay. Kinara Capital and SIDBI will have the most data. Smaller co-operative banks may only have a website about page and one annual report. Work with what is available and note the confidence level accordingly:
- Comprehensive annual report + website = `"confidence": "high"`
- Website only + news = `"confidence": "medium"`
- Very limited public data = `"confidence": "low"`

---

## HOUR 7–9: Ingestion

We go Direct — no RAG framework. The pipeline is:

1. **Load** — read all files in `data/{institution_id}/` using pypdf (PDFs) and plain file reading (TXT files)
2. **Chunk** — split text into ~500-word segments with ~50-word overlap
3. **Embed** — pass each chunk through bge-m3 via sentence-transformers → 1024-dimension vector
4. **Store** — upsert vector + chunk text + metadata (institution_id, source filename) into that institution's Qdrant collection

Use the shared `rag_helpers.py` from the Integration Lead for the embed and store functions.

For each institution:
1. Confirm all files are in `data/{institution_id}/`
2. Run the ingestion script pointing at that folder and collection name
3. Verify with a test search: embed "What loans does {institution} offer?" → search Qdrant → check returned chunks make sense

Each institution gets its own isolated Qdrant collection. This is critical — queries for Kinara Capital only search Kinara Capital documents, preventing cross-contamination between institutions.

---

## HOUR 9–14: Build the 4 Endpoints

---

### Endpoint 1: `GET /competitive/institutions` — Institution List

This endpoint does not need RAG. It just reads all JSON files from your `institutions/` folder and returns a summary list.

**Returns for each institution:**
- id
- name
- type
- headquarters
- msme_focus (true/false)
- website URL

**This is how the frontend draws the institution grid.** No AI involved — just JSON config reading.

---

### Endpoint 2: `GET /competitive/institutions/{id}` — Full Institution Profile

**What the frontend shows:** A detailed side panel when a user clicks an institution card. This is the main intelligence view.

**For the given institution, run RAG over its collection and generate:**

**Overview**
What does this institution do? Who are its primary customers? What is its stated mission or positioning?

**Key Products and Loan Types**
What loan products do they offer? What are the ticket sizes (minimum/maximum loan amounts)? What are the typical interest rate ranges? What collateral do they require (or do they offer collateral-free loans like Kinara)?

**MSME Focus**
How much of their portfolio is MSME? Which MSME segments do they target — micro, small, or medium? Which industries or sectors? Manufacturing, trade, services?

**Public Financial Highlights**
Total loan book / AUM if available. NPA ratio if mentioned. Number of customers / borrowers. Branch count. Any revenue or profit figures mentioned in public documents.

**Geographic Presence**
Which districts or regions do they operate in? Do they have a Karnataka-only focus or wider reach? Number of branches and their locations.

**Strategic Positioning**
What is their competitive advantage? Speed? Low interest rates? Community relationships? Technology? What kind of borrower trusts them over a bank?

**Prompt direction:** Frame this as a competitor intelligence report for GICC's strategy team. Be factual where data exists. Flag estimates clearly. Keep it to 4–5 paragraphs.

**Confidence:** Match to data quality (high/medium/low as described above)

**Source:** The institution's own published documents

**ai_note example:** "Profile generated from Kinara Capital's Annual Report 2023 and website disclosures. Loan book size from published report; interest rate range is AI interpretation from product page descriptions."

---

### Endpoint 3: `GET /competitive/institutions/{id}/swot` — AI SWOT Analysis

**What the frontend shows:** A 4-quadrant SWOT card inside the institution detail panel. This is one of the most impressive features of the module.

**This is the most important endpoint to get right.**

The SWOT must follow this exact format:

**STRENGTHS:**
- [FACT] Point sourced from a document
- [AI INTERPRETATION] Point inferred from data

**WEAKNESSES:**
- [FACT] or [AI INTERPRETATION] for each point

**OPPORTUNITIES:**
- [FACT] or [AI INTERPRETATION] for each point

**THREATS:**
- [FACT] or [AI INTERPRETATION] for each point

**STRATEGIC OBSERVATION:**
One paragraph on what GICC should specifically know about this competitor — what threat do they pose, or what gap do they leave that GICC could exploit?

**Why the [FACT] / [AI INTERPRETATION] labeling matters:**
The brief's AI Principles section explicitly requires distinguishing fact from AI interpretation. The judges will look for this. It is an explicit evaluation criterion. Do not skip it.

**Prompt direction:** Ask the RAG engine to generate a SWOT from the perspective of a competing financial institution (GICC) analysing this institution's strength in Karnataka MSME lending. Require it to label every point.

**Confidence:** Same as the profile endpoint for that institution

**Source:** Same documents as the profile

**ai_note:** State that SWOT points labeled [FACT] are sourced from published documents, and [AI INTERPRETATION] points are analytical inferences.

---

### Endpoint 4: `GET /competitive/landscape` — Competitive Landscape Overview

**What the frontend shows:** A dashboard widget answering "What is the Karnataka MSME lending landscape?"

**This is a cross-institution synthesis, not a single-institution view.** 

You have two options for implementation:
- Create a separate Qdrant collection called `comp_landscape` that ingests a curated summary text of all institutions
- Or query one well-documented institution (e.g. SIDBI) whose reports discuss the overall MSME ecosystem

**What the response must cover:**

**Market Overview**
Who are the dominant players? What is the rough market share split between state institutions, co-operative banks, and NBFCs?

**Product Landscape**
What loan products and ticket sizes are available in this market? Where is there clustering (everyone offers the same thing)? Where are the gaps?

**Competitive Battlegrounds**
Which customer segments are the most fought-over? Micro-manufacturers? Urban traders? Agricultural-adjacent MSMEs?

**Market Gaps**
Where are borrowers underserved? Which geographies have low penetration? Which MSME types cannot get formal credit easily?

**Strategic Implication for GICC**
Given this landscape, where does GICC have a natural advantage? What should they do to differentiate?

**Prompt direction:** Frame as an executive market briefing for a co-operative bank's board. Be strategic and specific. Avoid generic statements like "there is opportunity in MSMEs" — say which segments, which districts, which product types.

**Confidence:** medium (cross-institution synthesis involves interpretation)

**Source:** Cite SIDBI and any institution whose annual report discusses the market broadly

---

## HOUR 14: Handoff to Integration Lead

### Handoff Checklist

**Config System**
- [ ] All 11 institutions have a JSON config file in `institutions/` folder
- [ ] Adding a new institution only requires adding a JSON file — no Python changes needed
- [ ] All institution IDs are URL-safe slugs (lowercase, underscores, no spaces)

**Response Format**
- [ ] All endpoints return the shared schema format
- [ ] `source.url` is a real working URL for every institution
- [ ] `ai_note` is present and meaningful on every response
- [ ] SWOT response has [FACT] and [AI INTERPRETATION] labels on every point

**Content Quality**
- [ ] Institution list returns all 11 institutions
- [ ] Profile for Kinara Capital is the most detailed (most data available)
- [ ] Every SWOT has a STRATEGIC OBSERVATION paragraph
- [ ] Landscape overview covers at least 3 of the 4 required sections

**Technical**
- [ ] CORS is open — Integration Lead can call your API from localhost:3000
- [ ] `/health` returns 200
- [ ] All 4 endpoints return 200 (no 500 errors)
- [ ] Response time under 30 seconds

---

## Common Mistakes to Avoid

**Mistake 1: Generic SWOT with no specifics**
Bad: "Strength: Strong community presence"
Good: "[FACT] Kinara Capital has disbursed over ₹3,000 crore to 1.5 lakh MSMEs across Karnataka (Annual Report 2023)"

**Mistake 2: Skipping [FACT] / [AI INTERPRETATION] labels in SWOT**
This is explicitly evaluated. Every SWOT point must be labeled. No exceptions.

**Mistake 3: Same SWOT for every institution**
The SWOT should be specific to each institution. If Kinara Capital and KSFC have the same SWOT, your prompts are not institution-specific enough.

**Mistake 4: Hardcoding institution data in Python**
If your institution data is hardcoded in Python rather than in JSON config files, you fail the "extensible without code changes" requirement — which is directly stated in the brief.

**Mistake 5: Using the wrong Qdrant collection**
Each institution has its own collection. If your endpoint queries the wrong collection, you will get KSFC data for a Kinara Capital request. Double-check your collection name mapping.

---

## What a Winning Response Looks Like

The judges will login as GICC Administrator, go to Competitive Intelligence, click on Kinara Capital, and see:
1. A profile that clearly explains who Kinara Capital is and what they do in MSME lending — specific, not generic
2. A SWOT with [FACT] and [AI INTERPRETATION] labels on every point and a STRATEGIC OBSERVATION paragraph that tells GICC something actionable
3. A source link that opens a real Kinara Capital document

Then they will look at the institution grid and check if SIDBI and a small co-operative bank like Kaujalgi also have profiles — testing the extensibility of your system.

If the config system works cleanly and the SWOT is specific and labeled, you have won Module 2.
