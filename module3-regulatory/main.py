"""Module 3 — Regulatory Intelligence API (Team C).

Run:  uvicorn main:app --port 8003 --reload
Docs: docs/TEAM_C_REGULATORY.md

Note: the parametric route /{category_id} is registered after /categories and
/alerts so those literal paths take precedence.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "shared"))

from fastapi import FastAPI  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402

import routes  # noqa: E402

app = FastAPI(title="Moneypal Genesis — Regulatory Intelligence")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(routes.router)


@app.get("/health")
def health():
    return {"status": "ok", "module": "regulatory"}
