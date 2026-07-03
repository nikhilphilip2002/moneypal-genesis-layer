"""Module 2 — Competitive Intelligence API (Team B).

Run:  uvicorn main:app --port 8002 --reload
Docs: docs/TEAM_B_COMPETITIVE.md
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "shared"))

from fastapi import FastAPI  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402

import routes  # noqa: E402

app = FastAPI(title="Moneypal Genesis — Competitive Intelligence")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(routes.router)


@app.get("/health")
def health():
    return {"status": "ok", "module": "competitive"}
