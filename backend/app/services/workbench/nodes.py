"""Source handlers. Each turns an intent into a renderable card.

Thin adapters over services that already exist — the loan-book pipeline and the macro RAG
store. No analytics or retrieval logic is duplicated here; a node's only job is to call the
right service and shape its output into the common `SourceResult` the graph streams.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from genesis_core import rag

from app.core.config import MACRO_COLLECTION
from app.services.nlq.ask import AskContext, ask_once
from app.services.workbench import models

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class SourceResult:
    source: str
    card_type: str  # "chart" | "brief" | "clarify" | "refusal" | "error"
    payload: dict[str, Any]
    summary: str = ""  # short, feeds the multi-source synthesis; never invents numbers
    sources: list[dict] = field(default_factory=list)


async def run_db(intent: str, *, conversation_id: str, user: str, role: str) -> SourceResult:
    """Answer from the loan book via the existing NLQ pipeline.

    `ask_once` runs the full plan -> compile -> execute path and returns a rendered chart,
    a clarification, or a refusal — all of which are valid cards. We reuse it wholesale so
    the workbench and the legacy /nlq route can never diverge on the same question.
    """
    ctx = AskContext(question=intent, conversation_id=conversation_id, user=user, role=role)
    try:
        response = await ask_once(ctx)
    except Exception as exc:  # noqa: BLE001 - a source failure degrades to a card, not a 500
        logger.warning("workbench db node failed: %s", exc)
        return SourceResult(
            source="db",
            card_type="error",
            payload={"message": "The loan book could not answer that.", "retryable": True},
        )

    if response.status == "clarify" and response.clarification is not None:
        return SourceResult(source="db", card_type="clarify",
                            payload=response.clarification.model_dump(mode="json"))
    if response.status == "refused" and response.refusal is not None:
        return SourceResult(source="db", card_type="refusal",
                            payload=response.refusal.model_dump(mode="json"))
    if response.chart is not None:
        return SourceResult(
            source="db",
            card_type="chart",
            payload=response.chart.model_dump(mode="json"),
            summary=response.chart.summary or response.plan_summary or "",
        )
    return SourceResult(source="db", card_type="error",
                        payload={"message": "No answer was produced.", "retryable": True})


_MACRO_SYSTEM = (
    "You are a macroeconomic analyst for a Karnataka co-operative bank. Answer the question "
    "strictly from the provided context passages. Cite figures as (document, p.X) using the "
    "passage metadata. If the context does not contain the answer, say so in one sentence "
    "rather than guessing. Be concise: at most ~150 words."
)


async def run_macro(intent: str) -> SourceResult:
    """Answer from published macro intelligence: retrieve, then synthesise locally.

    Retrieval is the existing Qdrant store. Synthesis deliberately does NOT use
    `rag.generate` (which targets Groq) — it goes through the workbench model router so a
    local-only deployment stays local. Macro sources are public, so if a deployment opts
    into a Groq burst this is where it is allowed.
    """
    chunks = rag.search_multi(MACRO_COLLECTION, [intent])
    if not chunks:
        return SourceResult(
            source="macro",
            card_type="brief",
            payload={"summary": "No macro sources matched that question.", "sources": []},
            summary="No macro context available.",
        )

    context = _format_chunks(chunks)
    client = models.for_step("synthesize", sensitive=False)
    try:
        result = await client.complete(
            messages=[
                {"role": "system", "content": _MACRO_SYSTEM},
                {"role": "user", "content": f"Question: {intent}\n\nContext:\n{context}"},
            ],
            max_tokens=500,
            temperature=0.2,
        )
        answer = result.text.strip()
    except Exception as exc:  # noqa: BLE001
        logger.warning("workbench macro synthesis failed: %s", exc)
        return SourceResult(
            source="macro",
            card_type="error",
            payload={"message": "Macro synthesis is unavailable.", "retryable": True},
        )

    sources = _source_refs(chunks)
    return SourceResult(
        source="macro",
        card_type="brief",
        payload={"summary": answer, "sources": sources},
        summary=answer,
        sources=sources,
    )


async def run_competitive(intent: str) -> SourceResult:
    """Answer from competitive intelligence. The landscape brief is the general view; it
    needs no institution id, which makes it the right default for a free-form question."""
    from app.services import competitive

    try:
        resp = competitive.landscape()
    except Exception as exc:  # noqa: BLE001
        logger.warning("workbench competitive node failed: %s", exc)
        return SourceResult(source="competitive", card_type="error",
                            payload={"message": "Competitive intelligence is unavailable."})
    return _intel_card("competitive", resp)


async def run_regulatory(intent: str) -> SourceResult:
    """Answer from regulatory intelligence. The question is matched to a regulation category
    and that category's grounded detail is returned; an unmatched question falls to the
    first category rather than guessing."""
    from app.services import regulatory

    try:
        categories = regulatory.list_categories()
        if not categories:
            return SourceResult(source="regulatory", card_type="error",
                                payload={"message": "No regulatory categories are loaded."})
        chosen = _best_category(intent, categories)
        resp = regulatory.regulation_detail(chosen.id)
    except Exception as exc:  # noqa: BLE001
        logger.warning("workbench regulatory node failed: %s", exc)
        return SourceResult(source="regulatory", card_type="error",
                            payload={"message": "Regulatory intelligence is unavailable."})
    return _intel_card("regulatory", resp)


async def run_schema(intent: str) -> SourceResult:
    """Answer 'how is the data organised' from the live schema graph. The card carries a
    trimmed node/edge list — the chat shows the shape; the full interactive graph opens on
    demand — which keeps the answer inside one viewport."""
    from app.services import db_schema

    try:
        graph = db_schema.get_db_schema_graph(search_term=intent or None)
    except Exception as exc:  # noqa: BLE001
        logger.warning("workbench schema node failed: %s", exc)
        return SourceResult(source="schema", card_type="error",
                            payload={"message": "The schema graph is unavailable."})

    raw_nodes = graph.get("nodes", []) or []
    raw_edges = graph.get("edges", []) or []
    trimmed_nodes = [{"id": n.get("id"), "label": n.get("label") or n.get("name") or n.get("id")}
                     for n in raw_nodes]
    trimmed_edges = [{"source": e.get("source"), "target": e.get("target"),
                      "label": e.get("label", "")} for e in raw_edges]
    summary = f"{len(trimmed_nodes)} tables, {len(trimmed_edges)} relationships."
    return SourceResult(
        source="schema",
        card_type="schema",
        payload={
            "nodes": trimmed_nodes,
            "edges": trimmed_edges,
            "node_count": len(trimmed_nodes),
            "edge_count": len(trimmed_edges),
            "search_term": intent,
        },
        summary=summary,
    )


def _intel_card(source: str, resp) -> SourceResult:
    """Shape an IntelligenceResponse into a brief card."""
    summary = getattr(resp, "summary", "") or ""
    key_points = list(getattr(resp, "key_points", []) or [])
    ref = getattr(resp, "source", None)
    sources = []
    if ref is not None:
        sources = [{
            "document": getattr(ref, "document", None) or getattr(resp, "title", source),
            "page": getattr(ref, "page", None),
        }]
    return SourceResult(
        source=source,
        card_type="brief",
        payload={"summary": summary, "key_points": key_points, "sources": sources},
        summary=summary,
        sources=sources,
    )


def _best_category(intent: str, categories: list):
    """Pick the category whose name best overlaps the question; first category on a tie or
    no overlap. Deliberately simple — a keyword hit is enough to route, and the category's
    own grounded detail does the real work."""
    words = {w for w in intent.lower().split() if len(w) > 3}
    best = categories[0]
    best_score = 0
    for cat in categories:
        label = f"{getattr(cat, 'display_name', '')} {getattr(cat, 'category', '')}".lower()
        score = sum(1 for w in words if w in label)
        if score > best_score:
            best, best_score = cat, score
    return best


def _format_chunks(chunks: list[dict]) -> str:
    parts = []
    for chunk in chunks:
        doc = chunk.get("document") or chunk.get("source") or "source"
        page = chunk.get("page")
        tag = f"[{doc}" + (f", p.{page}" if page else "") + "]"
        parts.append(f"{tag}\n{chunk.get('text', '').strip()}")
    return "\n\n".join(parts)


def _source_refs(chunks: list[dict]) -> list[dict]:
    refs = []
    for chunk in chunks[:6]:
        refs.append({
            "document": chunk.get("document") or chunk.get("source") or "source",
            "page": chunk.get("page"),
            "score": round(float(chunk.get("score", 0.0)), 3),
        })
    return refs
