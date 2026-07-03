# Module 1 — Macro-economic Intelligence (Team A)

Port **8001** · Qdrant collection **`macro_intel`** · Full brief: `docs/TEAM_A_MACRO.md`

## Setup
```bash
pip install -r ../requirements.txt
cp ../.env.example ../.env        # add GROQ_API_KEY
python ../shared/download_model.py
```

## Build
1. Download source PDFs into `./data/` (Economic Survey, MOSPI, MSME report, RBI, SIDBI).
2. `python ingest.py` — indexes everything into `macro_intel`.
3. `uvicorn main:app --port 8001 --reload`
4. Refine the prompts in `prompts.py` and the sources in `routes.py`.

## Endpoints
`GET /macro/snapshot` · `/macro/karnataka` · `/macro/msme` · `/macro/briefing` · `/health`

The routes are already wired to the shared pipeline — your job is good data + sharp prompts.
