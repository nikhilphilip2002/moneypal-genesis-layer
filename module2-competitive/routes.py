"""Competitive intelligence endpoints."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "shared"))

from fastapi import APIRouter, HTTPException  # noqa: E402

import institution_loader as il  # noqa: E402
import rag_helpers as rag  # noqa: E402
from schema import IntelligenceResponse, make_response  # noqa: E402

router = APIRouter(prefix="/competitive", tags=["competitive"])


@router.get("/institutions")
def list_institutions():
    return [
        {
            "id": i["id"],
            "name": i["name"],
            "type": i["type"],
            "headquarters": i.get("headquarters"),
            "msme_focus": i.get("msme_focus", True),
            "website": i.get("website"),
        }
        for i in il.load_all()
    ]


@router.get("/institutions/{institution_id}", response_model=IntelligenceResponse)
def institution_profile(institution_id: str):
    inst = il.load_one(institution_id)
    if not inst:
        raise HTTPException(404, "Institution not found")

    prompt = (
        f"Write a competitor intelligence profile of {inst['name']} for GICC's strategy "
        f"team. Cover: overview and customers; key loan products and ticket sizes; MSME "
        f"focus (segments, geography); public financial highlights (AUM, loan book, NPA "
        f"if available); geographic presence; and strategic positioning. Be factual; "
        f"flag estimates. 4-5 paragraphs."
    )
    answer, sources = rag.ask(inst["qdrant_collection"], prompt)
    page = str(sources[0]["page"]) if sources and sources[0].get("page") else None
    return make_response(
        title=f"{inst['name']} — Institution Profile",
        summary=answer,
        key_points=[
            f"Type: {inst['type']}",
            f"HQ: {inst.get('headquarters', 'N/A')}",
            "MSME-focused lender" if inst.get("msme_focus") else "Broad lender",
            "Karnataka presence",
        ],
        document=f"{inst['name']} public disclosures",
        url=inst.get("source_urls", {}).get("website", inst.get("website", "#")),
        page=page,
        ai_note="Profile from public documents; financials are sourced, estimates are AI interpretation.",
        confidence=inst.get("confidence", "medium"),
    )


@router.get("/institutions/{institution_id}/swot")
def institution_swot(institution_id: str):
    inst = il.load_one(institution_id)
    if not inst:
        raise HTTPException(404, "Institution not found")

    prompt = (
        f"Generate a SWOT analysis of {inst['name']} from the perspective of a competing "
        f"Karnataka MSME lender (GICC). Label every point [FACT] if sourced or "
        f"[AI INTERPRETATION] if inferred. Format:\n"
        f"STRENGTHS:\n- ...\nWEAKNESSES:\n- ...\nOPPORTUNITIES:\n- ...\nTHREATS:\n- ...\n"
        f"STRATEGIC OBSERVATION: one paragraph on what GICC should know about this competitor."
    )
    answer, _ = rag.ask(inst["qdrant_collection"], prompt)
    return {
        "institution": inst["name"],
        "swot_analysis": answer,
        "source": {
            "document": f"{inst['name']} annual report & public disclosures",
            "url": inst.get("source_urls", {}).get(
                "annual_report", inst.get("website", "#")
            ),
        },
        "ai_note": "[FACT] points are sourced from documents; [AI INTERPRETATION] points are analytical inferences.",
    }


@router.get("/landscape", response_model=IntelligenceResponse)
def landscape():
    # Uses one well-documented collection as an anchor; refine to a dedicated
    # comp_landscape collection if you ingest a cross-institution summary.
    anchor = "comp_sidbi"
    prompt = (
        "Give an executive overview of the Karnataka MSME lending landscape. Cover: "
        "major players and positioning; typical products and rate ranges; the most "
        "contested customer segments; market gaps / underserved areas; and the strategic "
        "implication for a co-operative bank (GICC). Be specific, not generic."
    )
    answer, _ = rag.ask(anchor, prompt)
    return make_response(
        title="Karnataka MSME Lending Landscape",
        summary=answer,
        key_points=[
            "Major players mapped",
            "Co-operatives strong in rural credit",
            "NBFCs compete on speed",
            "Underserved micro-segment",
        ],
        document="Public disclosures — multiple institutions",
        url="https://www.sidbi.in/en/",
        ai_note="Landscape synthesised from public disclosures; market-share estimates are AI interpretation.",
        confidence="medium",
    )
