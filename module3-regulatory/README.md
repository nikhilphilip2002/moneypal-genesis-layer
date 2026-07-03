# Module 3 — Regulatory Intelligence (Team C)

Port **8003** · one Qdrant collection per category · Full brief: `docs/TEAM_C_REGULATORY.md`

## Config-driven categories
Each regulation category is one JSON in `./regulations/`. Three examples are included
(`master_directions`, `digital_lending`, `kyc_aml`). Create the remaining 6 from the brief.

## Build
1. Create the 9 category JSONs in `./regulations/`.
2. Download RBI PDFs into `./data/` (filename must match each JSON's `source_doc`).
3. `python ingest.py` — ingests each PDF into its category collection.
4. `uvicorn main:app --port 8003 --reload`
5. Curate `alerts.py` for the dashboard widget.

## Endpoints
`GET /regulatory/categories` · `/regulatory/alerts` · `/regulatory/{category_id}` · `/health`

Each regulation detail must follow the 5-section structure: Executive Summary,
Applicability, Business Impact, Compliance Actions, Effective Date.
