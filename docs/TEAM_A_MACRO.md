# Team A — Module 1: Macro-economic Intelligence
**Port: 8001 | Qdrant Collection: `macro_intel` | Duration: 24 Hours**

---

## Your Mission

Build the intelligence backbone that answers: **"What is the economic context for MSME lending in Karnataka?"**

You are not building a data warehouse. You are building an executive briefing engine. Every output should be something a GICC Director can read in 2 minutes and act on.

---

## Your 4 API Endpoints

| Endpoint | Purpose | Dashboard Widget |
|----------|---------|-----------------|
| `GET /macro/snapshot` | India economic snapshot | Economic Snapshot widget |
| `GET /macro/karnataka` | Karnataka economy overview | Karnataka Lending Landscape widget |
| `GET /macro/msme` | MSME lending trends | Used in macro page |
| `GET /macro/briefing` | AI Executive Brief | AI Executive Brief widget (most important) |

---

## Shared Response Format (You Must Follow This)

Every endpoint returns exactly this structure. The Integration Lead defines the schema file. Copy it into your project before starting.

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
- Download bge-m3 model — run the download script the Integration Lead provides. This takes time, do it now
- Set up your `.env` file with `GROQ_API_KEY` and Qdrant host/port
- Confirm FastAPI starts and returns 200 on `/health`
- Pull the shared schema from the repo

---

## HOUR 2–5: Data Collection

This is the most important prep work. The quality of your RAG output depends entirely on the quality of documents you ingest. Be thorough here.

---

### Documents to Download

**1. Government of India Economic Survey**
- URL: indiabudget.gov.in/economicsurvey
- What to get: The latest Economic Survey PDF (current year)
- Key sections to look for: GDP growth, inflation, credit growth, employment, MSME chapter
- Save as: `economic_survey_2024.pdf`

**2. MOSPI (Ministry of Statistics)**
- URL: mospi.gov.in
- What to get: National Accounts Statistics PDF or Statistical Year Book
- Key sections: GDP data, sector-wise growth, employment statistics
- Save as: `mospi_statistics_2024.pdf`

**3. Ministry of MSME Annual Report**
- URL: msme.gov.in → Publications → Annual Report
- What to get: Latest annual report PDF
- Key sections: MSME credit, employment, Karnataka-specific data if any, government schemes
- Save as: `msme_annual_report_2024.pdf`

**4. Indian Economy Presentation**
- URL: DocSend link provided in the buildathon brief
- Download and save as: `india_economy_presentation.pdf`

**5. RBI Annual Report**
- URL: rbi.org.in → Publications → Annual Report
- What to get: Sections on credit growth, MSME lending, monetary policy
- Save as: `rbi_annual_report_2024.pdf`

**6. RBI Report on Trend and Progress of Banking**
- URL: rbi.org.in → Publications
- Key sections: Credit to MSME sector, NPA data, priority sector lending
- Save as: `rbi_trend_progress_2024.pdf`

**7. Karnataka State Budget / Economic Survey**
- Search: "Karnataka economic survey 2024 PDF" or visit finance.karnataka.gov.in
- Key sections: GSDP, sector contributions, MSME, financial inclusion
- Save as: `karnataka_economic_survey_2024.pdf`

**8. SIDBI MSME Pulse Report**
- URL: sidbi.in → Reports
- What to get: Latest MSME Pulse or credit gap report
- Key data: MSME credit outstanding, formal vs informal split, regional data
- Save as: `sidbi_msme_pulse_2024.pdf`

---

### Where to Save Everything

Put all files into your `data/` folder. The ingestion script reads everything from that folder automatically.

---

### Tips for Data Collection

- If a PDF is very large (100+ pages), you do not need the entire document. Download it but focus ingestion on relevant chapters if possible
- If a PDF link is broken, search Google for "{document name} filetype:pdf" — government documents are usually mirrored
- Copy important data tables from websites as `.txt` files if PDFs are not available
- Do not spend more than 90 minutes on collection — move to ingestion

---

## HOUR 5–7: Ingestion

Once your documents are in the `data/` folder, run ingestion.

### What Ingestion Does

We go Direct — no RAG framework. You wire the three tools yourself. The pipeline is only 4 steps:

1. **Load** — read every PDF in your `data/` folder using pypdf, extract raw text page by page
2. **Chunk** — split each document into segments of ~500 words with ~50-word overlap. You control this — smaller chunks = more precise retrieval, larger chunks = more context per result
3. **Embed** — pass each chunk through bge-m3 via sentence-transformers → get a 1024-dimension vector (handles up to 8192 tokens per chunk, which is why we chose it over MiniLM)
4. **Store** — upsert each vector + the original chunk text + metadata (source filename, page number) into Qdrant collection `macro_intel`

The Integration Lead will provide a shared `rag_helpers.py` with the embed and search functions. Import from there — do not write your own embedding logic.

### After Ingestion

Verify it worked by running a test query against the Qdrant collection. Ask it something simple like "What is India's GDP growth rate?" and check that it returns relevant chunks.

If ingestion returns 0 documents — check that your PDFs are not scanned images (image-only PDFs cannot be read). If they are scanned, find a text version or copy the text manually.

---

## HOUR 7–14: Build the 4 Endpoints

---

### Endpoint 1: `/macro/snapshot` — Economic Snapshot

**What the frontend shows:** A card on the dashboard answering "What is India's current economic state?"

**What your RAG prompt must extract:**
- India GDP growth rate for the current financial year
- Current inflation rate (CPI)
- RBI repo rate / monetary policy stance
- Credit growth percentage (overall and MSME-specific)
- Employment situation (headline number)

**How the query works (Direct approach):**
Embed your prompt using bge-m3 → search Qdrant for top 5 similar chunks → build a context string from those chunks → send context + prompt to Groq → return the generated response in the shared schema format.

**Prompt direction:**
Ask Groq to act as a briefing officer for a financial institution director. Request a concise snapshot covering GDP, inflation, credit growth, and employment. Keep it to 3 short paragraphs. Cite the specific document and data point for every number mentioned.

**Confidence level:** high (if you have Economic Survey data)

**Source to cite:** Government of India Economic Survey 2024

**ai_note example:** "GDP and inflation figures are from the Economic Survey 2024 (official government data). Credit growth projections are AI interpretation based on RBI trend data."

---

### Endpoint 2: `/macro/karnataka` — Karnataka Economy

**What the frontend shows:** A card on the dashboard answering "What is Karnataka's lending landscape?"

**What your RAG prompt must extract:**
- Karnataka GSDP and growth rate
- Key economic sectors and their contribution (IT, manufacturing, agriculture, services)
- Number of MSME units in Karnataka and employment they generate
- Financial inclusion metrics — bank branch density, credit penetration
- Active central and state government schemes for MSME lending (PM Mudra Yojana, Stand Up India, Karnataka Udyog Mitra, etc.)
- Any Karnataka-specific credit gaps or underserved districts

**Prompt direction:**
Ask for an executive briefing on Karnataka's economic landscape for a co-operative bank considering MSME expansion. Focus on the lending opportunity — what is the market size, who is underserved, what schemes support lending.

**Confidence level:** medium (Karnataka-specific data may be less complete)

**Source to cite:** MOSPI data + Karnataka Economic Survey

**ai_note example:** "Karnataka GSDP data from MOSPI. MSME unit counts from Ministry of MSME Annual Report. Credit gap estimates are AI-derived from national averages applied to Karnataka's economic share."

---

### Endpoint 3: `/macro/msme` — MSME Lending Trends

**What the frontend shows:** A card on the macro page for the Policy Maker and Admin roles

**What your RAG prompt must extract:**
- Total MSME credit outstanding in India (₹ crore)
- Year-on-year growth rate of MSME credit
- NPA levels in the MSME portfolio (national average %)
- Formal vs informal credit split — what percentage of MSMEs rely on informal sources
- Digital lending penetration in MSME space
- Key lending barriers: lack of collateral, thin credit bureau files, documentation issues
- Priority sector lending targets for MSME and compliance levels

**Prompt direction:**
Ask for a strategic analysis of MSME lending trends for a Karnataka co-operative bank looking to grow its MSME book. Focus on the opportunity (credit gap) and the risks (NPA trends). Make it actionable — what should a lender do differently based on these trends.

**Confidence level:** high

**Source to cite:** MSME Ministry Annual Report 2024 + SIDBI MSME Pulse + RBI Trend and Progress

**ai_note example:** "Credit outstanding and NPA figures sourced from RBI Trend and Progress Report 2024. Digital lending penetration estimate is AI interpretation based on SIDBI MSME Pulse data."

---

### Endpoint 4: `/macro/briefing` — AI Executive Brief (Most Important)

**What the frontend shows:** The largest, most prominent widget on the GICC Director's dashboard. This is the first thing a judge sees.

**What your RAG prompt must extract and structure:**

This prompt synthesises everything from the other 3 endpoints into one crisp director-level briefing. It must follow this exact structure:

**HEADLINE**
One sentence — the single most important economic development for MSME lenders in Karnataka right now.

**MACRO CONTEXT**
2 paragraphs on the national economic environment. Cover: is India's economy expanding or contracting, what is the credit environment, is the RBI in an easing or tightening cycle, what does this mean for a lender.

**KARNATAKA FOCUS**
1 paragraph on Karnataka specifically. What is the MSME lending opportunity here, which sectors are growing, where is credit demand concentrated.

**RISK WATCH**
3 bullet points on risks: inflation risk, NPA risk, regulatory risk, or macro slowdown risk — whatever is most relevant from the data.

**OPPORTUNITY**
1 paragraph on the strategic opportunity for GICC. What should they do given this macro environment.

**Prompt direction:**
Frame the prompt as if you are the Chief Intelligence Officer of Moneypal writing the weekly executive briefing for the Director of GICC. Be decisive and specific. Cite at least 3 different source documents. Numbers make the briefing credible — use them.

**Confidence level:** high

**Source to cite:** Economic Survey 2024 + RBI Annual Report + MSME Ministry Report

**ai_note example:** "This briefing is AI-generated by synthesising Economic Survey 2024, RBI Annual Report, and MSME Ministry data. Macro statistics are from official sources. Strategic recommendations are AI interpretation and should be validated with the institution's leadership team."

---

## HOUR 14: Handoff to Integration Lead

Before you hand off, check every endpoint against this list:

### Handoff Checklist

**Response Format**
- [ ] All 4 endpoints return the shared schema format (title, summary, key_points, source, ai_note, last_updated, confidence)
- [ ] `source.url` is a real, working URL for every endpoint — not a placeholder
- [ ] `source.document` names the actual document (not "Document 1")
- [ ] `ai_note` is present and meaningful on every response
- [ ] `key_points` has 3–5 items on every response

**Content Quality**
- [ ] Snapshot includes at least 2 real numbers (GDP %, inflation %)
- [ ] Karnataka endpoint mentions at least one state-specific data point
- [ ] MSME endpoint covers formal vs informal credit split
- [ ] Briefing follows the 5-section structure (Headline, Macro Context, Karnataka Focus, Risk Watch, Opportunity)

**Technical**
- [ ] CORS is open — Integration Lead can call your API from localhost:3000
- [ ] `/health` returns 200
- [ ] All 4 endpoints return 200 (no 500 errors)
- [ ] Response time under 30 seconds (Groq is fast, but RAG adds time)

---

## Common Mistakes to Avoid

**Mistake 1: Generic summaries with no numbers**
Bad: "India's economy is growing at a healthy pace."
Good: "India's GDP grew at 7.2% in FY2024-25, driven by services and manufacturing, with MSME credit growing at 14% year-on-year."

**Mistake 2: Missing source attribution**
Every number must come from a document. If you cannot point to the source, label it as AI interpretation in the ai_note.

**Mistake 3: Too much text**
The summary should be readable in 90 seconds. If your summary is 10 paragraphs, cut it to 3.

**Mistake 4: Ingesting bad documents**
If a PDF is scanned (image-only), bge-m3 cannot read it. Test ingestion output early — do not discover this at Hour 12.

**Mistake 5: Spending too long on data collection**
90 minutes max on collection. Ship with what you have. An incomplete briefing from real data beats a comprehensive briefing with no sources.

---

## What a Winning Response Looks Like

The judges will login as GICC Director and see the AI Executive Brief on the dashboard. They will ask:
1. Does it answer "what should I know today?" — Yes/No
2. Does it cite real documents? — Yes/No
3. Does it distinguish fact from AI interpretation? — Yes/No
4. Are the numbers credible? — Yes/No

If all 4 are yes, you have won Module 1.
