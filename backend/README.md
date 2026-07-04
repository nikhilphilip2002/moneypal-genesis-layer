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
