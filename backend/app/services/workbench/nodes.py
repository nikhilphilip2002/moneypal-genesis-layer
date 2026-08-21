"""Source handlers. Each turns an intent into a renderable card.

Thin adapters over services that already exist — the loan-book pipeline and the macro RAG
store. No analytics or retrieval logic is duplicated here; a node's only job is to call the
right service and shape its output into the common `SourceResult` the graph streams.
"""

from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass, field
from typing import Any

from genesis_core import rag

from app.core.config import MACRO_COLLECTION, settings
from app.services.nlq.ask import AskContext, ask_once
from app.services.nlq.catalog import get_catalog
from app.services.nlq.catalog.retrieval import retrieve
from app.services.nlq.contracts import AskResponse
from app.services.nlq.normalization import normalize_lending_question
from app.services.workbench import models

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class SourceResult:
    source: str
    card_type: str  # "chart" | "analysis" | "worklist" | "briefing" | "brief" | "clarify" | "refusal" | "error"
    payload: dict[str, Any]
    summary: str = ""  # short, feeds the multi-source synthesis; never invents numbers
    sources: list[dict] = field(default_factory=list)


async def run_db(
    intent: str,
    *,
    conversation_id: str,
    user: str,
    role: str,
    access_mode: str | None = None,
    history_messages: list[dict[str, str]] | None = None,
) -> SourceResult:
    """Answer from the loan book via the existing NLQ pipeline.

    `ask_once` runs the full plan -> compile -> execute path and returns a rendered chart,
    a clarification, or a refusal — all of which are valid cards. We reuse it wholesale so
    the workbench and the legacy /nlq route can never diverge on the same question.
    """
    try:
        effective_mode = access_mode if access_mode in ("direct", "mcp") else settings.postgres_access_mode
        if effective_mode == "mcp":
            from app.mcp import postgres_client

            payload = await postgres_client.ask_loan_book(
                question=intent,
                conversation_id=conversation_id,
                user=user,
                role=role,
                history_messages=history_messages or [],
            )
            response = AskResponse.model_validate(payload)
        else:
            ctx = AskContext(
                question=intent, conversation_id=conversation_id, user=user, role=role,
                history_messages=history_messages or [],
            )
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
    if response.analysis is not None:
        # A multi-query answer. Its headline is already deterministic and templated from the
        # findings, so it is the right thing to hand the cross-source synthesis — passing the
        # whole briefing would invite the synthesiser to re-rank what the thresholds ranked.
        return SourceResult(
            source="db",
            card_type="analysis",
            payload=response.analysis.model_dump(mode="json"),
            summary=response.analysis.headline or response.plan_summary or "",
        )
    if response.briefing is not None:
        # The headline is already deterministic and templated from the signals, so it is the
        # right thing to hand the cross-source synthesis — passing the whole briefing would
        # invite the synthesiser to re-rank what the detectors ranked.
        return SourceResult(
            source="db",
            card_type="briefing",
            payload=response.briefing.model_dump(mode="json"),
            summary=response.briefing.headline or response.plan_summary or "",
        )
    if response.worklist is not None:
        # A list of accounts to act on. The summary names the count and the severity mix
        # rather than the accounts themselves — a cross-source synthesis has no business
        # restating borrower names, and the card already shows them to whoever may see them.
        alerts = sum(1 for item in response.worklist.items if item.severity == "alert")
        return SourceResult(
            source="db",
            card_type="worklist",
            payload=response.worklist.model_dump(mode="json"),
            summary=(
                f"{response.worklist.title}: {len(response.worklist.items)} accounts, "
                f"{alerts} needing immediate action."
            ),
        )
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


async def run_macro(
    intent: str, *, history_messages: list[dict[str, str]] | None = None,
) -> SourceResult:
    """Answer from published macro intelligence: retrieve, then synthesise locally.

    Retrieval is the existing Qdrant store. Synthesis deliberately does NOT use
    `rag.generate` (which targets Groq) — it goes through the workbench model router so a
    local-only deployment stays local. Macro sources are public, so if a deployment opts
    into a Groq burst this is where it is allowed.
    """
    try:
        # Qdrant and sentence-transformers are synchronous. Keep them off the event loop so
        # a slow remote vector store does not freeze every active workbench stream.
        chunks = await asyncio.to_thread(rag.search_multi, MACRO_COLLECTION, [intent])
    except Exception as exc:  # noqa: BLE001 - external retrieval must degrade per source
        logger.warning("workbench macro retrieval failed: %s", exc)
        return SourceResult(
            source="macro",
            card_type="error",
            payload={
                "message": "Macro intelligence is temporarily unavailable. The vector store did not respond.",
                "retryable": True,
            },
        )
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
                *(history_messages or []),
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


_KNOWLEDGE_SYSTEM = (
    "You explain stable lending and banking concepts in plain language. Answer the user's "
    "descriptive question in 2-4 concise sentences. Define the concept, state its unit or "
    "calculation when relevant, and distinguish easily confused terms. Use the governed "
    "catalog context below when it applies. Do not invent bank figures, current rates, laws, "
    "forecasts or recommendations; those belong to other sources."
)


async def run_knowledge(
    intent: str, *, history_messages: list[dict[str, str]] | None = None,
) -> SourceResult:
    """Explain stable concepts, grounded by relevant governed metric definitions."""
    question = normalize_lending_question(intent)
    cat = get_catalog()
    matched = retrieve(question, catalog=cat, use_vectors=False)
    context_lines: list[str] = []
    for metric_id in matched.metrics[:4]:
        metric = cat.metrics[metric_id]
        context_lines.append(
            f"- {metric.label} ({metric.unit}): {metric.formula}. {metric.caveat}".strip()
        )
    for dimension_id in matched.dimensions[:3]:
        dimension = cat.dimensions[dimension_id]
        if dimension.description:
            context_lines.append(f"- {dimension.label}: {dimension.description}")
    context = "\n".join(context_lines) or "No catalog definition matched; explain only the stable concept."

    client = models.for_step("synthesize", sensitive=False)
    try:
        result = await client.complete(
            messages=[
                {"role": "system", "content": _KNOWLEDGE_SYSTEM},
                *(history_messages or []),
                {"role": "user", "content": f"Question: {question}\n\nCatalog context:\n{context}"},
            ],
            max_tokens=350,
            temperature=0.1,
        )
        answer = result.text.strip()
    except Exception as exc:  # noqa: BLE001 - catalog fallback can still answer a definition
        logger.warning("workbench concept explanation failed: %s", exc)
        answer = _catalog_definition_fallback(matched.metrics, cat)
        if not answer:
            return SourceResult(
                source="knowledge",
                card_type="error",
                payload={"message": "The concept explainer is temporarily unavailable."},
            )

    return SourceResult(
        source="knowledge",
        card_type="brief",
        payload={"summary": answer, "sources": []},
        summary=answer,
    )


def _catalog_definition_fallback(metric_ids: list[str], catalog) -> str:
    if not metric_ids:
        return ""
    metric = catalog.metrics[metric_ids[0]]
    answer = f"{metric.label} is measured as {metric.formula.rstrip('.').lower()}."
    if metric.caveat:
        answer += " " + " ".join(metric.caveat.split())
    return answer


async def run_competitive(intent: str) -> SourceResult:
    """Retrieve question-specific competitor evidence and synthesize via Workbench policy.

    The legacy competitive service always generated a generic landscape with Groq. That
    made every pinned question identical and broke local-only deployments. This adapter
    selects the relevant institution collections, retrieves with the user's actual intent,
    and uses the same local-first model router as macro intelligence.
    """
    from app.services import institution_loader

    institutions = institution_loader.load_all()
    selected = _matching_institutions(intent, institutions) or institutions

    def retrieve_chunks() -> list[dict[str, Any]]:
        chunks: list[dict[str, Any]] = []
        for institution in selected:
            collection = institution.get("qdrant_collection")
            if not collection:
                continue
            try:
                hits = rag.search_multi(
                    collection, [intent], top_k=3, min_score=0.25, max_chunks=3,
                )
                for hit in hits:
                    enriched = dict(hit)
                    enriched.setdefault("document", institution.get("name", collection))
                    enriched["institution"] = institution.get("name", collection)
                    chunks.append(enriched)
            except Exception as exc:  # noqa: BLE001 - one bad collection must not erase peers
                logger.warning("competitive collection %s failed: %s", collection, exc)
        chunks.sort(key=lambda item: float(item.get("score", 0.0)), reverse=True)
        return chunks[:14]

    try:
        chunks = await asyncio.to_thread(retrieve_chunks)
    except Exception as exc:  # noqa: BLE001
        logger.warning("workbench competitive retrieval failed: %s", exc)
        chunks = []

    if not chunks:
        # Registry metadata is governed and remains useful when semantic retrieval is down.
        names = ", ".join(str(item.get("name", "")) for item in selected[:8] if item.get("name"))
        if names:
            answer = (
                f"The competitor registry identifies {names}. Detailed product, pricing, "
                "and performance evidence is currently unavailable from the indexed sources."
            )
            return SourceResult(
                source="competitive", card_type="brief",
                payload={"summary": answer, "sources": [], "degraded": True}, summary=answer,
            )
        return SourceResult(
            source="competitive", card_type="error",
            payload={"message": "Competitive intelligence is unavailable.", "retryable": True},
        )

    system = (
        "You are a competitive-intelligence analyst for a Karnataka co-operative lender. "
        "Answer the exact question using only the supplied indexed passages. Compare "
        "institutions directly when asked. Never invent rates, ticket sizes, turnaround "
        "times, market shares, or financial figures. If a requested fact is absent, answer "
        "the supported portion and state the gap briefly. Cite facts as (document, p.X). "
        "Use at most 180 words."
    )
    context = _format_chunks(chunks)
    try:
        completion = await models.for_step("synthesize", sensitive=False).complete(
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": f"Question: {intent}\n\nIndexed evidence:\n{context}"},
            ],
            max_tokens=550,
            temperature=0.1,
        )
        answer = completion.text.strip()
    except Exception as exc:  # noqa: BLE001 - retrieval evidence still has value
        logger.warning("workbench competitive synthesis failed: %s", exc)
        answer = _extractive_fallback(chunks, prefix="Relevant competitor evidence")

    sources = _source_refs(chunks)
    return SourceResult(
        source="competitive", card_type="brief",
        payload={"summary": answer, "sources": sources},
        summary=answer, sources=sources,
    )


def _matching_institutions(intent: str, institutions: list[dict]) -> list[dict]:
    normalized = re.sub(r"[^a-z0-9]+", " ", intent.lower()).strip()
    words = set(normalized.split())
    matched: list[dict] = []
    for institution in institutions:
        identity = " ".join(
            str(institution.get(field, "")) for field in ("id", "name", "type")
        ).lower()
        tokens = {token for token in re.findall(r"[a-z0-9]+", identity) if len(token) > 2}
        distinctive = {token for token in tokens if token not in {
            "bank", "cooperative", "urban", "state", "financial", "capital", "karnataka",
            "national",
        }}
        if distinctive and (distinctive & words or any(token in normalized for token in distinctive if len(token) > 4)):
            matched.append(institution)
    return matched


def _extractive_fallback(chunks: list[dict], *, prefix: str) -> str:
    excerpts: list[str] = []
    for chunk in chunks[:3]:
        text = " ".join(str(chunk.get("text", "")).split())
        if text:
            excerpts.append(text[:320].rstrip())
    return f"{prefix}: " + " ".join(excerpts) if excerpts else f"{prefix} is unavailable."


async def run_regulatory(intent: str) -> SourceResult:
    """Answer from regulatory intelligence. The question is matched to a regulation category
    and that category's grounded detail is returned; an unmatched question falls to the
    first category rather than guessing."""
    from app.services import rag as regulatory_rag
    from app.services import regulatory

    try:
        categories = regulatory.list_categories()
        if not categories:
            return SourceResult(source="regulatory", card_type="error",
                                payload={"message": "No regulatory categories are loaded."})
        chosen = _best_category(intent, categories)
        hits = await asyncio.to_thread(
            regulatory_rag.search_qdrant, chosen.qdrant_collection, intent, 8,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("workbench regulatory node failed: %s", exc)
        return SourceResult(source="regulatory", card_type="error",
                            payload={"message": "Regulatory intelligence is unavailable."})
    if not hits:
        # The existing service has an extractive fallback based on the registry config.
        try:
            return _intel_card("regulatory", regulatory.regulation_detail(chosen.id))
        except Exception as exc:  # noqa: BLE001
            logger.warning("workbench regulatory fallback failed: %s", exc)
            return SourceResult(source="regulatory", card_type="error",
                                payload={"message": "Regulatory intelligence is unavailable."})

    context = regulatory_rag.build_context(hits)
    system = (
        "You answer Indian lending-regulation questions for a bank director. Use only the "
        "provided RBI/regulatory passages and the supplied applicability metadata. Answer "
        "the exact question, not a generic compliance briefing. Distinguish an explicit "
        "rule from a related principle and say when entity-specific applicability must be "
        "confirmed. Never invent a threshold or effective date. Cite as (document, p.X)."
    )
    try:
        completion = await models.for_step("synthesize", sensitive=False).complete(
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": (
                    f"Question: {intent}\nCategory: {chosen.display_name}\n"
                    f"Applicability: {chosen.applicability}\nEffective date: {chosen.effective_date}"
                    f"\n\nEvidence:\n{context}"
                )},
            ],
            max_tokens=550,
            temperature=0.1,
        )
        answer = completion.text.strip()
    except Exception as exc:  # noqa: BLE001
        logger.warning("workbench regulatory synthesis failed: %s", exc)
        answer = _extractive_fallback(hits, prefix=f"Relevant {chosen.display_name} evidence")
    sources = _source_refs(hits)
    return SourceResult(
        source="regulatory", card_type="brief",
        payload={"summary": answer, "sources": sources},
        summary=answer, sources=sources,
    )


async def run_schema(intent: str, *, access_mode: str | None = None) -> SourceResult:
    """Answer 'how is the data organised' from the live schema graph. The card carries a
    trimmed node/edge list — the chat shows the shape; the full interactive graph opens on
    demand — which keeps the answer inside one viewport."""
    from app.services import db_schema

    try:
        effective_mode = access_mode if access_mode in ("direct", "mcp") else settings.postgres_access_mode
        if effective_mode == "mcp":
            from app.mcp import postgres_client

            graph = await postgres_client.curiosity_graph(search=intent or "")
        else:
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
    normalized = re.sub(r"[^a-z0-9]+", " ", intent.lower())
    words = {w for w in normalized.split() if len(w) > 2}
    aliases = {
        "prudential_norms": {
            "prudential", "exposure", "single borrower", "group borrower", "concentration",
            "npa", "non performing", "asset classification", "provisioning", "capital adequacy",
        },
        "master_directions": {
            "priority sector", "psl", "msme target", "gold loan", "secured lending",
        },
        "fair_practices_code": {
            "fair practices", "grievance", "recovery conduct", "customer protection",
        },
        "digital_lending": {"digital lending", "lsp", "dla", "fintech"},
        "kyc_aml": {"kyc", "aml", "money laundering", "customer due diligence"},
        "outsourcing": {"outsourcing", "vendor", "service provider"},
        "information_security": {"cyber", "information security", "incident", "technology risk"},
        "governance": {"governance", "board oversight", "director"},
    }
    best = categories[0]
    best_score = 0
    for cat in categories:
        label = f"{getattr(cat, 'display_name', '')} {getattr(cat, 'category', '')}".lower()
        score = sum(1 for w in words if w in label)
        for alias in aliases.get(getattr(cat, "id", ""), set()):
            if alias in normalized:
                score += 5 if " " in alias else 3
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
