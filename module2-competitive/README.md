# Module 2 — Competitive Intelligence (Team B)

Port **8002** · one Qdrant collection per institution · Full brief: `docs/TEAM_B_COMPETITIVE.md`

## Config-driven institutions
Each institution is one JSON in `./institutions/`. **Add an institution = add a JSON file.**
Three examples are included (`kinara_capital`, `ksfc`, `sidbi`). Create the remaining 8
from the list in the brief.

## Build
1. Create the 11 institution JSONs in `./institutions/`.
2. Collect public docs into `./data/<institution_id>/` (annual reports, website text, news).
3. `python ingest.py` — ingests each institution into its own collection.
4. `uvicorn main:app --port 8002 --reload`

## Endpoints
`GET /competitive/institutions` · `/institutions/{id}` · `/institutions/{id}/swot` · `/landscape` · `/health`

SWOT must label every point `[FACT]` or `[AI INTERPRETATION]` — this is scored.
