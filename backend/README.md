# Moneypal Genesis Regulatory Backend

FastAPI backend for RBI/NBFC regulatory intelligence using direct RAG.

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Add keys/settings to `.env`:

```env
GROQ_API_KEY=your_key_here
QDRANT_URL=http://localhost:6333
EMBEDDING_MODEL=BAAI/bge-m3
```

Start Qdrant:

```powershell
docker run -p 6333:6333 -v ${PWD}\qdrant_storage:/qdrant/storage qdrant/qdrant
```

Ingest the existing PDFs:

```powershell
python backend/scripts/ingest.py regulatory
```

For offline testing without Qdrant:

```powershell
python backend/scripts/ingest.py regulatory --no-qdrant
```

Run the API:

```powershell
uvicorn app.main:app --app-dir backend --reload --port 8000
```

## Endpoints

- `GET /health`
- `GET /regulatory/categories`
- `GET /regulatory/{category_id}`
- `GET /regulatory/alerts`

## Workbench architecture

`POST /workbench/ask` uses an ordinary async select → concurrent dispatch → answer flow.
PostgreSQL loan-book access is available by default. `external_sources_enabled=true` permits
the role/deployment intersection of macro, competitive, regulatory, and web sources for that
conversation. The same immutable policy gates pins and direct Workbench tools.

Qdrant and web handlers return bounded typed evidence. They do not make per-source language-
model calls; one common grounded composer handles all retrieved evidence. The durable
Workbench record is the only prose transcript. NLQ conversation state contains structured
query anchors only and is not a second chat history.
