# Moneypal Genesis Intelligence Console

An advanced regulatory, competitive, and macro-economic intelligence dashboard designed for **GICC** (a Karnataka co-operative bank) to assist in credit assessment and regulatory compliance. Powered by the **Aroha RAG Framework**, utilizing FastAPI, Next.js, Groq, and Qdrant.

---

## Key Features

1. **Macro-Economic Intelligence:** Real-time dashboards monitoring growth, state-level indicators (Karnataka), MSME lending trends, and executive briefings.
2. **Competitive Intelligence:** Config-driven profiles, automated SWOT analyses, and lending landscape briefings of competing Karnataka MSME lenders.
3. **Regulatory Intelligence:** Real-time compliance monitoring of RBI directions, digital lending controls, KYC/AML obligations, and structured alert priorities.
4. **Interactive Ask Genesis:** Semantic search and natural-language QA grounded in vector storage with inline document citations.
5. **Config-Driven Architecture:** Registering a new regulation or competitor institution is completely metadata-driven (requires adding a JSON configuration under `backend/registry/`).
6. **Smart Brief Cache:** SQLite-backed brief cache that keeps LLM responses stable with instant page switches and supports query-time forcing (`?refresh=1`) to regenerate responses.
7. **Hybrid Search System:** Dense vector semantic search for prose text, combined with an optimized lexical/keyword substring matcher for tabular lists and name registries (e.g. the NBFC/Bank list).
8. **Governed Live-Web Intelligence:** Exa's hosted MCP server supplies fresh public economic evidence with official-source prioritization, clickable citations, free-tier controls, and a deterministic privacy boundary that prevents customer or loan-account data from leaving the bank.

---

## Technology Stack

- **Frontend:** Next.js (TypeScript), Tailwind CSS, Lucide Icons, Radix UI.
- **Backend:** FastAPI (Python), Uvicorn.
- **Orchestration:** Plain async Workbench with deterministic-first governed source routing.
- **MCP:** Python MCP client for internal PostgreSQL access and hosted Exa web search.
- **Vector DB:** Qdrant (Tailscale shared/local container).
- **Embeddings:** `BAAI/bge-m3` (1024-dimension).
- **LLM Engine:** Groq API (`llama-3.3-70b-versatile`).

---

## Directory Structure

```text
├── backend/
│   ├── app/
│   │   ├── api/            # API endpoints (macro, competitive, regulatory, admin)
│   │   ├── core/           # Settings & configuration loader
│   │   ├── mcp/            # PostgreSQL and Exa MCP clients/servers
│   │   ├── models/         # Pydantic schema declarations
│   │   └── services/       # RAG, Workbench routing, cache, and search engines
│   ├── data/               # Source PDFs / Text documents (ingestion inputs)
│   ├── registry/           # Institutions, regulations, and trusted web sources
│   └── scripts/            # Ingestion and server execution scripts
├── frontend/
│   ├── app/                # Next.js pages and routes
│   ├── components/         # React dashboard widgets & core UI components
│   └── lib/                # API client calls and hooks
├── Regulations/            # Structured directories of official RBI PDFs
└── packages/
    └── genesis_core/       # Shared Python core package (Qdrant & Groq wrapper)
```

---

## Setup & Running Guide

### 1. Environment Configuration
Create a `.env` file at the root of the project:

```env
GROQ_API_KEY=your-primary-key
GROQ_API_KEY_SECONDARY=your-failover-key
GROQ_MODEL=llama-3.3-70b-versatile
QDRANT_URL=http://localhost:6333
QDRANT_HOST=localhost
QDRANT_PORT=6333
EMBEDDING_MODEL=BAAI/bge-m3
REGULATIONS_DIR=/path/to/Regulations

# Public live-web intelligence — backend only
EXA_MCP_ENABLED=true
EXA_MCP_URL=https://mcp.exa.ai/mcp?tools=web_search_exa,web_fetch_exa,web_search_advanced_exa
EXA_API_KEY=your-exa-api-key
EXA_MCP_TIMEOUT_S=30
EXA_SEARCH_MAX_RESULTS=8
EXA_FETCH_MAX_PAGES=2
EXA_CACHE_TTL_S=3600
EXA_DAILY_USER_LIMIT=10
```

Never use an `EXA_API_KEY` name prefixed with `NEXT_PUBLIC_`; the browser must not receive
the key. The backend sends it to Exa using the `x-api-key` MCP request header.

Production secrets may be maintained in a Git-ignored `.env.prod`, but the current Python
settings loader and `docker-compose.yml` read `.env`. Copy or merge the production values
into `.env` during deployment, or explicitly change the deployment to load `.env.prod`.

### 2. Ingest Source Documents
To embed and ingest PDF circulars/disclosures into the Qdrant database:
```bash
# Ingest regulatory collections
python backend/scripts/ingest.py regulatory

# Ingest competitor collections
python backend/scripts/ingest.py competitive
```

### 3. Run the Backend API
Run the FastAPI application from the `backend/` directory:
```bash
uvicorn app.main:app --app-dir backend --port 8000 --reload
```

*Note: For NixOS systems, run the `backend/scripts/run_backend.sh` script to set correct dynamic linking paths (`LD_LIBRARY_PATH`) for precompiled libraries.*

### 4. Run the Frontend Dashboard
Start the Next.js development server from the `frontend/` directory:
```bash
npm run dev
```
Open [http://localhost:3000](http://localhost:3000) in your browser.

### 5. Run the Complete Docker Stack

```bash
docker compose up -d --build
```

The Workbench is available at `/workbench`. After changing Exa environment settings,
restart the backend so its cached settings are reloaded.

---

## Exa MCP Live-Web Intelligence

The Workbench treats Exa as a governed `web` source rather than giving the language model
unrestricted access to arbitrary tools.

```text
Next.js Workbench
        ↓
FastAPI + plain async orchestrator
        ├── db         → governed PostgreSQL
        ├── macro      → local Qdrant retrieval
        ├── regulatory → local regulatory index
        └── web        → Exa remote MCP → public internet
                     ↓
              one common composer
```

The integration uses Exa's hosted Streamable HTTP endpoint. `web_search_exa` handles normal
lookups, `web_search_advanced_exa` applies trusted-domain filters, and `web_fetch_exa` is
available for bounded page retrieval. See the [canonical Exa MCP documentation](https://docs.exa.ai/reference/exa-mcp).

### Routing Rules

- New conversations use the governed PostgreSQL loan book by default. One conversation-
  scoped **Use external sources** toggle enables macro, competitive, regulatory, and live
  web sources together, subject to role and deployment availability.
- Omitting `external_sources_enabled` is equivalent to `false`. External pins and direct
  Workbench tools cannot bypass this policy.
- Fresh public questions containing cues such as `latest`, `current`, `today`, `recent`,
  `news`, or an explicit request to search online route to `web`.
- Stable economic questions continue to use the local `macro` index, avoiding unnecessary
  external calls and preserving the existing curated corpus.
- Questions comparing bank performance with fresh public benchmarks route to `db + web`.
  Each source receives a separate task.
- Deterministic routing guards enforce these rules even if the routing model returns an
  incorrect source or is unavailable.
- Vector and web handlers return bounded evidence rather than generating separate prose.
  One common composer handles one or many retrieved sources, while complete DB/schema cards
  and deterministic refusals bypass composition.
- Disabling `WORKBENCH_EXTERNAL_CONNECTORS_ENABLED` removes every connector-backed source;
  disabling `EXA_MCP_ENABLED` additionally removes live web even when consent is on.

### Privacy Boundary

Only sanitized public subquestions may cross the Exa boundary. The backend blocks queries
containing customer IDs, loan-account identifiers, phone/Aadhaar/PAN details, named borrower
lookups, or repayment histories. In a mixed question, internal figures remain on the
governed database path while Exa receives only the external benchmark request.

Retrieved pages are untrusted evidence. Synthesis is instructed to ignore embedded webpage
instructions, use only retrieved facts, prefer primary sources, expose conflicts, and
distinguish a document's publication date from the statistical period it reports.

### Economic Source Priority

The maintained registry is `backend/registry/economic_web_sources.yaml`:

1. Indian primary sources: RBI, RBI DBIE, MoSPI, India Budget/Economic Survey, DEA, NITI
   Aayog, DPIIT, Commerce, DGFT, PIB, and Data.gov.in.
2. International primary sources: IMF, World Bank, OECD, and United Nations.
3. Secondary analysis: PRS India, IBEF, Grant Thornton India, and ClearTax.
4. Educational sources are retained as a final reference tier and are not allowed to
   override available primary evidence.

Search proceeds tier by tier and stops when citable higher-authority evidence is found.
Canonical URLs are deduplicated and tracking parameters are removed before display.

### Free-Tier Controls

- Search results are capped at 10 and default to 8.
- Full-page retrieval is capped at two pages by default.
- Repeated queries are cached for one hour.
- Each user has a configurable daily search allowance.
- Provider 429 responses and transport timeouts become isolated source cards rather than
  failing the entire Workbench turn.
- MCP session setup, tool execution, and shutdown are covered by an outer deadline.

### Functional Smoke Questions

Live web:

```text
What is the latest RBI repo rate announcement?
What is India's latest published CPI inflation figure?
Search the internet for the latest MoSPI GDP release.
```

Stable local macro:

```text
Explain Karnataka GDP growth trends.
How does inflation affect MSME borrowing?
```

Hybrid database and live web:

```text
Compare our loan growth against the latest RBI bank credit growth.
```

Privacy rejection:

```text
Search online for customer ID 42.
Find repayment history for borrower Anitha Rao on the web.
```

The first group should show `Live web` with clickable citations, the stable questions should
show `Macro`, the hybrid question should show `Loan book` and `Live web`, and the final group
must be blocked before any Exa tool call.

### Verification

```bash
PYTHONPATH=backend:packages/genesis_core/src \
  .venv/bin/pytest -q \
  backend/tests/workbench/test_exa_mcp.py \
  backend/tests/workbench/test_web.py \
  backend/tests/workbench/test_router.py \
  backend/tests/workbench/test_graph.py

ruff check backend/app/mcp/exa_client.py backend/app/services/workbench/web.py

cd frontend
npx tsc --noEmit
npm run build
```
