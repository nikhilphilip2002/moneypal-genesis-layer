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

---

## Technology Stack

- **Frontend:** Next.js (TypeScript), Tailwind CSS, Lucide Icons, Radix UI.
- **Backend:** FastAPI (Python), Uvicorn.
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
│   │   ├── models/         # Pydantic schema declarations
│   │   └── services/       # RAG logic, loaders, cache, and search engines
│   ├── data/               # Source PDFs / Text documents (ingestion inputs)
│   ├── registry/           # Configuration files for institutions & regulations
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
```

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
