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
        f"Write the competitor intelligence profile of {inst['name']} for GICC's strategy team.\n"
        f"Format exactly:\n"
        f"WHO THEY ARE: overview, customer base, geographic presence, cited.\n"
        f"PRODUCTS & PRICING: key loan products, ticket sizes and rates, cited.\n"
        f"FINANCIAL STRENGTH: AUM/loan book/NPA where available, cited; if absent, "
        f"say 'not available in indexed sources'.\n"
        f"THREAT TO GICC: 2-3 sentences on where {inst['name']} overlaps with or "
        f"threatens GICC's MSME segments, marked [AI INTERPRETATION].\n"
        f"Maximum ~170 words."
    )
    queries = [f"{inst['name']} {q}" for q in prompts.PROFILE_QUERIES]
    answer, sources = rag.ask(inst["qdrant_collection"], prompt, queries=queries)
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
        f"Karnataka MSME lender (GICC).\n{prompts.SWOT_RULES}"
    )
    queries = [f"{inst['name']} {q}" for q in prompts.PROFILE_QUERIES]
    answer, _ = rag.ask(inst["qdrant_collection"], prompt, queries=queries)
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
    # Landscape spans lenders: retrieve from every institution collection, not one anchor.
    chunks: list[dict] = []
    for inst in il.load_all():
        try:
            chunks += rag.search_multi(
                inst["qdrant_collection"], prompts.LANDSCAPE_QUERIES, top_k=2, max_chunks=3
            )
        except Exception:
            continue  # unindexed collection — skip
    chunks.sort(key=lambda h: h["score"], reverse=True)
    if chunks:
        answer = rag.generate(prompts.LANDSCAPE, chunks[:14])
    else:
        answer, _ = rag.ask(LANDSCAPE_ANCHOR, prompts.LANDSCAPE, queries=prompts.LANDSCAPE_QUERIES)
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
