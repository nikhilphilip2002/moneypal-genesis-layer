"""Business logic for macro-economic intelligence (Team A)."""
from genesis_core import make_response, rag

from app import prompts
from app.core.config import MACRO_COLLECTION


def _brief(title, prompt, key_points, document, url, ai_note, confidence="medium", queries=None):
    answer, sources = rag.ask(MACRO_COLLECTION, prompt, queries=queries)
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


def snapshot():
    return _brief(
        "India Economic Snapshot",
        prompts.SNAPSHOT,
        ["GDP growth (current FY)", "CPI inflation", "MSME credit growth", "Employment trend"],
        "Government of India Economic Survey",
        "https://www.indiabudget.gov.in/economicsurvey/",
        "GDP and inflation figures are from the Economic Survey; forward-looking views are AI interpretation.",
        confidence="high",
        queries=prompts.SNAPSHOT_QUERIES,
    )


def karnataka():
    return _brief(
        "Karnataka Economic Landscape",
        prompts.KARNATAKA,
        ["Karnataka GSDP & growth", "MSME units & employment", "Credit gap", "Active lending schemes"],
        "MOSPI & Karnataka Economic Survey",
        "https://www.mospi.gov.in/",
        "State data from MOSPI and the Karnataka Economic Survey; credit-gap estimates are AI interpretation.",
        confidence="medium",
        queries=prompts.KARNATAKA_QUERIES,
    )


def msme():
    return _brief(
        "MSME Lending Trends",
        prompts.MSME,
        ["MSME credit outstanding", "NPA trends", "Formal vs informal split", "Digital lending gap"],
        "MSME Ministry Annual Report & SIDBI MSME Pulse",
        "https://msme.gov.in/",
        "Credit and NPA figures from official reports; market-gap estimates are AI interpretation.",
        confidence="high",
        queries=prompts.MSME_QUERIES,
    )


def briefing():
    return _brief(
        "AI Executive Brief — Macro Intelligence",
        prompts.BRIEFING,
        ["Credit environment", "Karnataka opportunity", "Risk watch", "Strategic move for GICC"],
        "Economic Survey + RBI Annual Report + MSME Ministry",
        "https://www.indiabudget.gov.in/economicsurvey/",
        "AI-synthesised from multiple official sources; statistics are sourced, strategy is AI interpretation.",
        confidence="high",
        queries=prompts.BRIEFING_QUERIES,
    )
