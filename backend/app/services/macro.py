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
        "",
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
        "",
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
        "",
        confidence="high",
        queries=prompts.MSME_QUERIES,
    )


# Shared so the cached and streamed briefing paths produce an identical envelope.
_BRIEFING_META = dict(
    title="Macro Intelligence",
    key_points=["Credit environment", "Karnataka opportunity", "Risk watch", "Strategic move for GICC"],
    document="Economic Survey + RBI Annual Report + MSME Ministry",
    url="https://www.indiabudget.gov.in/economicsurvey/",
    ai_note="",
    confidence="high",
)


def briefing_response(summary: str, sources: list[dict]):
    """Wrap a (streamed or batch) briefing body in the standard response envelope."""
    page = str(sources[0]["page"]) if sources and sources[0].get("page") else None
    return make_response(summary=summary, page=page, **_BRIEFING_META)


def briefing():
    answer, sources = rag.ask(MACRO_COLLECTION, prompts.BRIEFING, queries=prompts.BRIEFING_QUERIES)
    return briefing_response(answer, sources)


def briefing_stream():
    """Retrieve context, then return (sources, token_generator) for the briefing.

    Retrieval runs up front so the caller can build the final response envelope
    from the same sources once streaming completes.
    """
    sources = rag.search_multi(MACRO_COLLECTION, prompts.BRIEFING_QUERIES)
    return sources, rag.generate_stream(prompts.BRIEFING, sources)
