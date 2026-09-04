"""Source handlers. Each turns an intent into a renderable card.

Thin adapters over services that already exist — the loan-book pipeline and the macro RAG
store. No analytics or retrieval logic is duplicated here; a node's only job is to call the
right service and shape its output into the common `SourceResult` the graph streams.
"""

from __future__ import annotations

import asyncio
import logging
import re
from typing import TYPE_CHECKING, Any

from genesis_core import rag

from app.core.config import MACRO_COLLECTION, settings
from app.services.nlq.ask import AskContext, ask_once
from app.services.nlq.catalog import get_catalog
from app.services.nlq.catalog.retrieval import retrieve
from app.services.nlq.contracts import AskResponse
from app.services.nlq.normalization import normalize_lending_question
from app.services.workbench import models
from app.services.workbench.results import Evidence, SourceResult

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from app.services.workbench.access import SourceAccessPolicy


def _require_external(policy: "SourceAccessPolicy | None", source_id: str) -> None:
    if policy is not None:
        policy.require(source_id)


_INCOMPLETE_ANSWER_RE = re.compile(
    r"\b(?:does not|doesn't|do not|don't|did not|didn't)\s+(?:contain|provide|include|reference)|"
    r"\b(?:cannot|can't|unable to)\s+(?:compare|determine|assess|answer|align)|"
    r"\b(?:no|without)\s+(?:specific|quantitative|comparable|relevant)?\s*"
    r"(?:data|figure|figures|benchmark|benchmarks|evidence|target|targets|context)|"
    r"\b(?:data|evidence|benchmark|figures?)\s+(?:is|are)\s+(?:absent|missing|unavailable)|"
    r"\b(?:context|findings|passages|evidence)\s+lacks?\b|"
    r"\bdata gap\b",
    re.IGNORECASE,
)


def _answer_limitation(answer: str) -> str:
    """Return a short, machine-readable reason when retrieved evidence is incomplete."""
    if not _INCOMPLETE_ANSWER_RE.search(answer):
        return ""
    sentences = re.split(r"(?<=[.!?])\s+", " ".join(answer.split()))
    return next((sentence for sentence in sentences if _INCOMPLETE_ANSWER_RE.search(sentence)),
                "The requested evidence is incomplete.")[:320]


def _strip_unsupported_page_citations(answer: str, sources: list[dict]) -> str:
    """Do not display page numbers invented for chunks that carry no page metadata."""
    if any(source.get("page") not in (None, "") for source in sources):
        return answer
    return re.sub(r",\s*p\.?\s*\d+(?:\s*[-–]\s*\d+)?", "", answer, flags=re.IGNORECASE)


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
            sensitive=True,
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
            sensitive=True,
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
            sensitive=True,
        )
    if response.chart is not None:
        # The model ranks and phrases only compiler-checked drill actions. Keep this short
        # and failure-tolerant: chart delivery must never depend on suggestion generation.
        try:
            from app.services.workbench import suggestions

            if settings.workbench_personalize_suggestions:
                client = models.for_step("route", sensitive=True)
                response.chart.next_steps = await asyncio.wait_for(
                    suggestions.personalize(
                        question=intent,
                        summary=response.chart.summary,
                        steps=response.chart.next_steps,
                        client=client,
                    ),
                    timeout=4.0,
                )
        except Exception as exc:  # noqa: BLE001 - catalog steps remain the safe fallback
            logger.debug("contextual next-step generation unavailable: %s", exc)
        chart_lineage = getattr(response.chart, "lineage", None)
        lineage = (
            chart_lineage.model_dump(mode="json")
            if chart_lineage is not None and hasattr(chart_lineage, "model_dump")
            else {}
        )
        return SourceResult(
            source="db",
            card_type="chart",
            payload=response.chart.model_dump(mode="json"),
            summary=response.chart.summary or response.plan_summary or "",
            sensitive=True,
            lineage=lineage,
        )
    return SourceResult(source="db", card_type="error",
                        payload={"message": "No answer was produced.", "retryable": True})


async def run_macro(
    intent: str, *, history_messages: list[dict[str, str]] | None = None,
    policy: "SourceAccessPolicy | None" = None,
) -> SourceResult:
    """Retrieve published macro evidence; the common composer owns all prose."""
    _require_external(policy, "macro")
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
            complete=False,
            limitation="No macro sources matched the question.",
        )

    sources = _source_refs(chunks)
    evidence = _chunk_evidence(chunks)
    summary = f"Retrieved {len(evidence)} relevant macro passage{'s' if len(evidence) != 1 else ''}."
    return SourceResult(
        source="macro",
        card_type="brief",
        payload={"summary": summary, "sources": sources},
        summary=summary,
        sources=sources,
        evidence=evidence,
    )


async def run_web(
    intent: str, *, user: str, policy: "SourceAccessPolicy | None" = None,
) -> SourceResult:
    """Retrieve fresh public evidence through Exa without exposing private bank context."""
    _require_external(policy, "web")
    from app.mcp import exa_client
    from app.services.workbench import web

    try:
        query, web_evidence, _raw_text = await web.retrieve(intent, user=user)
    except web.UnsafeWebQuery as exc:
        return SourceResult(
            source="web", card_type="refusal",
            payload={"message": str(exc), "reason": "private_external_query", "examples": []},
        )
    except exa_client.ExaRateLimitError as exc:
        return SourceResult(
            source="web", card_type="error",
            payload={"message": str(exc), "retryable": False},
        )
    except Exception as exc:  # external failure is isolated to its source card
        logger.warning("workbench web retrieval failed: %s", exc)
        return SourceResult(
            source="web", card_type="error",
            payload={"message": "Live web intelligence is temporarily unavailable.", "retryable": True},
        )

    citations = [item.citation() for item in web_evidence]
    evidence = [
        Evidence(
            excerpt=item.excerpt,
            document=item.title,
            url=item.url,
            date=item.published_at or "",
            untrusted=True,
        )
        for item in web_evidence
        if item.excerpt
    ]
    summary = f"Retrieved {len(citations)} citable web result{'s' if len(citations) != 1 else ''} for: {query}"
    return SourceResult(
        source="web", card_type="brief",
        payload={
            "summary": summary,
            "sources": citations,
            "retrieved_at": web_evidence[0].retrieved_at,
            "sanitized_query": query,
        },
        summary=summary,
        sources=citations,
        evidence=evidence,
        complete=bool(evidence),
        limitation="" if evidence else "The web results contained no usable excerpt.",
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
    answer = _catalog_definition_fallback(matched.metrics, cat)
    if not answer and context_lines:
        answer = " ".join(line.removeprefix("- ") for line in context_lines[:2])
    if not answer:
        return SourceResult(
            source="knowledge", card_type="clarify",
            payload={"question": "Which governed lending or banking concept should I explain?"},
            complete=False,
        )

    return SourceResult(
        source="knowledge",
        card_type="brief",
        payload={"summary": answer, "sources": []},
        summary=answer,
        evidence=[Evidence(excerpt=line.removeprefix("- "), document="Governed catalog", untrusted=False)
                  for line in context_lines],
    )


def _catalog_definition_fallback(metric_ids: list[str], catalog) -> str:
    if not metric_ids:
        return ""
    metric = catalog.metrics[metric_ids[0]]
    answer = f"{metric.label} is measured as {metric.formula.rstrip('.').lower()}."
    if metric.caveat:
        answer += " " + " ".join(metric.caveat.split())
    return answer


async def run_competitive(
    intent: str, *, policy: "SourceAccessPolicy | None" = None,
) -> SourceResult:
    """Retrieve question-specific competitor evidence without per-source synthesis."""
    _require_external(policy, "competitive")
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
                evidence=[Evidence(excerpt=answer, document="Competitor registry", untrusted=False)],
                complete=False,
                limitation="Detailed competitive evidence is unavailable from indexed sources.",
            )
        return SourceResult(
            source="competitive", card_type="error",
            payload={"message": "Competitive intelligence is unavailable.", "retryable": True},
        )

    sources = _source_refs(chunks)
    evidence = _chunk_evidence(chunks)
    summary = (
        f"Retrieved {len(evidence)} competitive passage{'s' if len(evidence) != 1 else ''} "
        f"across {len({item.get('institution') for item in chunks if item.get('institution')})} institution(s)."
    )
    return SourceResult(
        source="competitive", card_type="brief",
        payload={"summary": summary, "sources": sources},
        summary=summary, sources=sources, evidence=evidence,
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


async def run_regulatory(
    intent: str, *, policy: "SourceAccessPolicy | None" = None,
) -> SourceResult:
    """Answer from regulatory intelligence. The question is matched to a regulation category
    and that category's grounded detail is returned; an unmatched question falls to the
    first category rather than guessing."""
    _require_external(policy, "regulatory")
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

    sources = _source_refs(hits)
    evidence = _chunk_evidence(hits)
    applicability = (
        f"Category: {chosen.display_name}. Applicability: {chosen.applicability}. "
        f"Effective date: {chosen.effective_date}."
    )
    evidence.insert(0, Evidence(
        excerpt=applicability, document="Regulatory registry", untrusted=False,
    ))
    summary = f"Retrieved {len(hits)} relevant {chosen.display_name} regulatory passage(s)."
    return SourceResult(
        source="regulatory", card_type="brief",
        payload={"summary": summary, "sources": sources},
        summary=summary, sources=sources, evidence=evidence,
    )


async def run_schema(intent: str, *, access_mode: str | None = None) -> SourceResult:
    """Answer 'how is the data organised' from the live schema graph. The card carries a
    trimmed node/edge list — the chat shows the shape; the full interactive graph opens on
    demand — which keeps the answer inside one viewport."""
    from app.services import curiosity_graph

    try:
        effective_mode = access_mode if access_mode in ("direct", "mcp") else settings.postgres_access_mode
        if effective_mode == "mcp":
            from app.mcp import postgres_client

            graph = await postgres_client.curiosity_graph(search=intent or "")
        else:
            graph = curiosity_graph.get_curiosity_graph()
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
    summary = f"{len(trimmed_nodes)} portfolio nodes, {len(trimmed_edges)} relationships."
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
    limitation = _answer_limitation(summary)
    return SourceResult(
        source=source,
        card_type="brief",
        payload={"summary": summary, "key_points": key_points, "sources": sources},
        summary=summary,
        sources=sources,
        evidence=[Evidence(
            excerpt=" ".join([summary, *key_points]),
            document=str(sources[0].get("document", "Regulatory registry")) if sources else "Regulatory registry",
            page=sources[0].get("page") if sources else None,
            untrusted=False,
        )] if summary or key_points else [],
        complete=not limitation,
        limitation=limitation,
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


def _chunk_evidence(chunks: list[dict]) -> list[Evidence]:
    return [
        Evidence(
            excerpt=str(chunk.get("text", "")),
            document=str(chunk.get("document") or chunk.get("source") or "source"),
            page=chunk.get("page"),
            score=float(chunk.get("score", 0.0)),
            untrusted=True,
        )
        for chunk in chunks
        if str(chunk.get("text", "")).strip()
    ]
