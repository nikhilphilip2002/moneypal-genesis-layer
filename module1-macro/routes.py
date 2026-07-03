"""Macro-economic intelligence endpoints. All return the shared IntelligenceResponse."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "shared"))

from fastapi import APIRouter  # noqa: E402

import prompts  # noqa: E402
import rag_helpers as rag  # noqa: E402
from schema import IntelligenceResponse, make_response  # noqa: E402

router = APIRouter(prefix="/macro", tags=["macro"])
COLLECTION = "macro_intel"


def _brief(title, prompt, key_points, document, url, ai_note, confidence="medium"):
    """Retrieve + generate + wrap in the shared schema."""
    answer, sources = rag.ask(COLLECTION, prompt)
    page = str(sources[0]["page"]) if sources and sources[0].get("page") else None
    return make_response(
        title=title,
        summary=answer,
        key_points=key_points,
        document=document,
        url=url,
        page=page,
        ai_note=ai_note,
        confidence=confidence,
    )


@router.get("/snapshot", response_model=IntelligenceResponse)
def snapshot():
    return _brief(
        "India Economic Snapshot",
        prompts.SNAPSHOT,
        ["GDP growth (current FY)", "CPI inflation", "MSME credit growth", "Employment trend"],
        "Government of India Economic Survey",
        "https://www.indiabudget.gov.in/economicsurvey/",
        "GDP and inflation figures are from the Economic Survey; forward-looking views are AI interpretation.",
        confidence="high",
    )


@router.get("/karnataka", response_model=IntelligenceResponse)
def karnataka():
    return _brief(
        "Karnataka Economic Landscape",
        prompts.KARNATAKA,
        ["Karnataka GSDP & growth", "MSME units & employment", "Credit gap", "Active lending schemes"],
        "MOSPI & Karnataka Economic Survey",
        "https://www.mospi.gov.in/",
        "State data from MOSPI and the Karnataka Economic Survey; credit-gap estimates are AI interpretation.",
        confidence="medium",
    )


@router.get("/msme", response_model=IntelligenceResponse)
def msme():
    return _brief(
        "MSME Lending Trends",
        prompts.MSME,
        ["MSME credit outstanding", "NPA trends", "Formal vs informal split", "Digital lending gap"],
        "MSME Ministry Annual Report & SIDBI MSME Pulse",
        "https://msme.gov.in/",
        "Credit and NPA figures from official reports; market-gap estimates are AI interpretation.",
        confidence="high",
    )


@router.get("/briefing", response_model=IntelligenceResponse)
def briefing():
    return _brief(
        "AI Executive Brief — Macro Intelligence",
        prompts.BRIEFING,
        ["Credit environment", "Karnataka opportunity", "Risk watch", "Strategic move for GICC"],
        "Economic Survey + RBI Annual Report + MSME Ministry",
        "https://www.indiabudget.gov.in/economicsurvey/",
        "AI-synthesised from multiple official sources; statistics are sourced, strategy is AI interpretation.",
        confidence="high",
    )
