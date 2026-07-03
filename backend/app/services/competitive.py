"""Business logic for competitive intelligence (Team B)."""
from genesis_core import make_response, rag

from app import prompts
from app.core.config import LANDSCAPE_ANCHOR
from app.services import institution_loader as il


def list_institutions() -> list[dict]:
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


def profile(institution_id: str):
    inst = il.load_one(institution_id)
    if not inst:
        return None
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


def swot(institution_id: str):
    inst = il.load_one(institution_id)
    if not inst:
        return None
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
            "url": inst.get("source_urls", {}).get("annual_report", inst.get("website", "#")),
        },
        "ai_note": "[FACT] points are sourced from documents; [AI INTERPRETATION] points are analytical inferences.",
    }


def landscape():
    answer, _ = rag.ask(LANDSCAPE_ANCHOR, prompts.LANDSCAPE)
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
