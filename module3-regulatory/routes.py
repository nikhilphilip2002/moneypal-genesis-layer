"""Regulatory intelligence endpoints."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "shared"))

from fastapi import APIRouter, HTTPException  # noqa: E402

import alerts as alerts_data  # noqa: E402
import rag_helpers as rag  # noqa: E402
import reg_loader as rl  # noqa: E402
from schema import IntelligenceResponse, make_response  # noqa: E402

router = APIRouter(prefix="/regulatory", tags=["regulatory"])


@router.get("/categories")
def list_categories():
    return [
        {
            "id": r["id"],
            "display_name": r["display_name"],
            "applicability": r.get("applicability"),
            "effective_date": r.get("effective_date"),
            "priority": r.get("priority", "medium"),
            "rbi_url": r.get("rbi_url"),
        }
        for r in rl.load_all()
    ]


@router.get("/alerts")
def get_alerts():
    return alerts_data.ALERTS


@router.get("/{category_id}", response_model=IntelligenceResponse)
def regulation_detail(category_id: str):
    reg = rl.load_one(category_id)
    if not reg:
        raise HTTPException(404, "Regulation category not found")

    prompt = (
        f"Brief the Director and Policy Maker of GICC (a Karnataka co-operative bank / "
        f"NBFC under Rs 500 crore) on the {reg['display_name']} issued by RBI. Translate "
        f"legalese into business actions. Structure exactly as:\n"
        f"EXECUTIVE SUMMARY: 2-3 sentences.\n"
        f"APPLICABILITY: who it applies to; specifically address NBFCs under Rs 500 crore.\n"
        f"BUSINESS IMPACT: 3-5 specific operational changes GICC must make.\n"
        f"COMPLIANCE ACTIONS: 4-6 actionable bullets.\n"
        f"EFFECTIVE DATE: {reg.get('effective_date', 'see source')}.\n"
        f"Actionable, not legal. Cite specific sections."
    )
    answer, sources = rag.ask(reg["qdrant_collection"], prompt)
    page = str(sources[0]["page"]) if sources and sources[0].get("page") else None
    return make_response(
        title=reg["display_name"],
        summary=answer,
        key_points=[
            f"Applies to: {reg.get('applicability', 'NBFCs')}",
            f"Effective: {reg.get('effective_date', 'N/A')}",
            f"Priority: {reg.get('priority', 'medium')}",
            "Source: RBI",
        ],
        document=reg["display_name"],
        url=reg.get("rbi_url", "https://rbi.org.in/"),
        page=page,
        ai_note="Summary from RBI directions. Not legal advice — verify actions with a compliance officer.",
        confidence="high",
    )
