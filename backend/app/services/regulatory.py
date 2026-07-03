"""Business logic for regulatory intelligence (Team C)."""
from genesis_core import make_response, rag

from app.services import reg_loader as rl
from app.services.alerts_data import ALERTS


def list_categories() -> list[dict]:
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


def get_alerts() -> list[dict]:
    return ALERTS


def detail(category_id: str):
    reg = rl.load_one(category_id)
    if not reg:
        return None
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
