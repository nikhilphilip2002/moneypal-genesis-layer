# shared/ — the contract every module builds on

Two files all three modules import. **Do not fork or rewrite these** — if something
needs to change, change it here so all modules stay in sync.

## Files

- **`schema.py`** — the response contract (`IntelligenceResponse`, `SourceRef`,
  `make_response(...)`). Every endpoint returns this shape.
- **`rag_helpers.py`** — the Direct RAG pipeline: `ingest_folder` / `ingest_files`,
  `search`, `generate`, and `ask` (retrieve + generate in one call).
- **`download_model.py`** — pre-download bge-m3 (~570MB). Run once per machine.
- **`smoke_test.py`** — end-to-end proof the pipeline works.

## How a module uses it

```python
import sys; sys.path.append("../shared")
import rag_helpers as rag
from schema import make_response

# ingestion script (run once, offline):
rag.ingest_folder("macro_intel", "./data")

# inside a FastAPI route:
answer, sources = rag.ask("macro_intel", "Summarise India's GDP outlook for MSME lenders")
top = sources[0]
return make_response(
    title="India Economic Snapshot",
    summary=answer,
    key_points=[...],
    document=top["source"], url="https://...", page=str(top["page"]),
    ai_note="Figures sourced from the Economic Survey; outlook is AI interpretation.",
    confidence="high",
)
```

## Setup

```bash
pip install -r ../requirements.txt
cp ../.env.example ../.env      # then paste your GROQ_API_KEY
python download_model.py         # once
python smoke_test.py             # verify everything works
```

## Rules

- Collection naming: `macro_intel`, `comp_<institution>`, `reg_<category>`. See `docs/QDRANT_SETUP.md`.
- `ensure_collection` uses **create-if-missing** — it never wipes an existing collection.
- Must be on `Aroha_T1` / `Aroha_G1` WiFi to reach Qdrant.
