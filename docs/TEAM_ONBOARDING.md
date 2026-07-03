# Team Onboarding — Moneypal Genesis Layer

Repo: **https://github.com/nikhilphilip2002/moneypal-genesis-layer.git**

Read this first. It tells you how to clone, which branch to work on, what is already
in the repo, and the rules everyone follows.

---

## 0. Prerequisites (do these once, at the start)

- **WiFi:** connect to `Aroha_T1` or `Aroha_G1` (required to reach the shared Qdrant at `192.168.1.183:6333`)
- **Python 3.11+** and **pip**
- The shared **Groq API key** (ask the Integration Lead) — goes into your `.env`
- Node 20+ and pnpm (frontend only — Integration Lead)

---

## 1. Clone the repo

```bash
git clone https://github.com/nikhilphilip2002/moneypal-genesis-layer.git
cd moneypal-genesis-layer
```

---

## 2. Switch to your team's branch

| Team | Module | Branch | Port |
|------|--------|--------|------|
| A | Macro-economic Intelligence | `team-a-macro` | 8000 (/macro) |
| B | Competitive Intelligence | `team-b-competitive` | 8000 (/competitive) |
| C | Regulatory Intelligence | `team-c-regulatory` | 8000 (/regulatory) |
| — | Frontend / Integration | `main` | 3000 |

```bash
git switch team-a-macro        # Team A  (or team-b-competitive / team-c-regulatory)
```

Work inside your respective routes and services files within [backend/app/](file:///home/null/Projects/moneypal/backend/app). Do not edit `packages/genesis_core/` — if the shared engine needs changing, tell the Integration Lead.

---

## 3. What is already in the repo (built by the Integration Lead)

```
moneypal-genesis-layer/
├── packages/genesis_core/     ← DO NOT EDIT. The shared engine you import.
│   └── src/genesis_core/
│       ├── schema.py          response contract (IntelligenceResponse, make_response)
│       ├── rag.py             Direct RAG: ingest_folder / search / generate / ask
│       └── config.py          settings (Qdrant, Groq, bge-m3) via pydantic-settings
├── backend/                   ← Unified FastAPI Application (All Teams)
│   ├── app/
│   │   ├── main.py            FastAPI setup containing all routers
│   │   ├── prompts.py         Prompts mapping dictionary
│   │   ├── api/routes/        Thin route handlers for macro, competitive, and regulatory
│   │   └── services/          Business/RAG logic handlers for each domain
│   ├── registry/              JSON files for institutions (B) and regulations (C)
│   ├── scripts/               ingest.py (Unified ingestion script)
│   ├── Dockerfile
│   └── data/                  macro/, competitive/, regulatory/ (gitignored local PDFs)
├── scripts/                   download_model.py · smoke_test.py
├── requirements.txt           one-shot backend setup
├── docker-compose.yml         runs the unified backend service
├── .env.example               copy to .env, add your Groq key
├── assets/                    Moneypal + GICC logos
└── docs/                      plans, per-team briefs, Qdrant setup, this file
```

Each domain already **runs** and its endpoints are already wired to the shared RAG
engine. Your job is: **get good data in, and sharpen the prompts** — not rebuild plumbing.
Business logic lives in `app/services/`, endpoints in `app/api/routes/`, prompts in
`app/prompts.py` (or inline in the service). Import the engine with `from genesis_core import rag, make_response`.

Read your module's deep brief before starting:
- Team A → `docs/TEAM_A_MACRO.md`
- Team B → `docs/TEAM_B_COMPETITIVE.md`
- Team C → `docs/TEAM_C_REGULATORY.md`
- Everyone → `docs/QDRANT_SETUP.md`

---

## 4. Set up your environment

```bash
pip install -r requirements.txt   # installs genesis-core (editable) + fastapi + uvicorn
cp .env.example .env              # then paste the Groq key into .env
python scripts/download_model.py  # downloads bge-m3 (~570MB), once
```

Verify the pipeline works before you build:

```bash
python scripts/smoke_test.py      # must print "SMOKE TEST PASSED"
```

---

## 5. Build your module

In short:

1. Collect source documents → put them in [backend/data/](file:///home/null/Projects/moneypal/backend/data)
   - Team A: `backend/data/macro/`
   - Team B: `backend/data/competitive/<institution_id>/`
   - Team C: `backend/data/regulatory/` (filenames must match JSON's `source_doc`)
2. Create the config JSONs your module needs:
   - Team B: inside [backend/registry/institutions/](file:///home/null/Projects/moneypal/backend/registry/institutions)
   - Team C: inside [backend/registry/regulations/](file:///home/null/Projects/moneypal/backend/registry/regulations)
3. Run ingestion: `cd backend && python scripts/ingest.py [macro|competitive|regulatory]`
4. Run the API: `cd backend && uvicorn app.main:app --port 8000 --reload`
5. Test: `curl http://localhost:8000/health` then hit your endpoints
6. Refine prompts in [backend/app/prompts.py](file:///home/null/Projects/moneypal/backend/app/prompts.py) until summaries read like an executive briefing

---

## 6. Golden rules

- **Response shape:** every endpoint returns the shared `IntelligenceResponse`. Use `make_response(...)`.
- **Every AI insight cites its source** and its `ai_note` separates fact from AI interpretation. This is scored.
- **Qdrant:** collections use `create_collection` (never recreate) — see `shared/rag_helpers.ensure_collection`. Never wipe another team's collection.
- **Collection names:** Team A `macro_intel`; Team B `comp_<institution>`; Team C `reg_<category>`.
- **Data is gitignored** — do not commit PDFs or the `data/` folders. Commit code and config JSONs only.
- **Commit as yourself**, with plain human commit messages. Do not add any AI / "generated by" attribution.

---

## 7. Commit & push your work

```bash
git add .
git commit -m "Ingest macro sources and refine snapshot prompt"
git push origin team-a-macro     # push to YOUR branch, not main
```

Pull the latest shared code from main when the Integration Lead updates it:

```bash
git fetch origin
git merge origin/main            # brings shared/ updates into your branch
```

When your module is ready, tell the Integration Lead — they merge your branch into
`main` and wire it into the frontend.

---

## 8. Checkpoints (Integration Lead tracks these)

| Time | Target |
|------|--------|
| Hour 2 | Env set up, `smoke_test.py` passes, on Aroha WiFi |
| Hour 6 | At least one endpoint returns real, non-empty data |
| Hour 10 | All endpoints working, pushed to your branch |
| Hour 14 | Merged to main, Integration Lead wiring it into the UI |

Questions or blocked? Ping the Integration Lead — don't sit stuck.
