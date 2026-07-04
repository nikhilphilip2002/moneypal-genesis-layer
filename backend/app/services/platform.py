"""Platform administration + cross-collection semantic search (Moneypal Administrator)."""
from genesis_core import rag
from genesis_core.config import settings

from app.core.config import MACRO_COLLECTION
from app.services import institution_loader as il
from app.services import reg_loader as rl

# GICC onboarding journey — Genesis phases from the developer brief (section 9).
ONBOARDING = {
    "client": "GICC",
    "client_url": "https://GICCLtd.com",
    "platform": "Moneypal Genesis Layer",
    "phases": [
        {"name": "Institutional Intelligence", "status": "active",
         "detail": "Macro, competitive and regulatory intelligence via the Aroha RAG framework"},
        {"name": "Prosper & Tally Migration", "status": "upcoming",
         "detail": "Migrate operational data into Canonical Business Objects"},
        {"name": "NEST Platform", "status": "upcoming",
         "detail": "Aggregate Block creation, BI, RIM and DNBS reporting"},
    ],
}


def _all_collections() -> list[tuple[str, str, str]]:
    """(collection, label, module) for every configured intelligence collection."""
    out = [(MACRO_COLLECTION, "Macro-economic Intelligence", "Macro")]
    for inst in il.load_all():
        out.append((inst["qdrant_collection"], inst["name"], "Competitive"))
    for reg in rl.load_all():
        out.append((reg["qdrant_collection"], reg["display_name"], "Regulatory"))
    return out


def status() -> dict:
    """Health + registry + vector-store status for the admin panel."""
    collections: list[dict] = []
    qdrant_ok = True
    try:
        client = rag.get_qdrant()
        existing = {c.name for c in client.get_collections().collections}
        for name, label, module in _all_collections():
            count = None
            if name in existing:
                count = client.count(collection_name=name).count
            collections.append({
                "collection": name,
                "label": label,
                "module": module,
                "indexed": name in existing,
                "vectors": count,
            })
    except Exception:
        qdrant_ok = False
        collections = [
            {"collection": name, "label": label, "module": module, "indexed": False, "vectors": None}
            for name, label, module in _all_collections()
        ]

    return {
        "qdrant": {"ok": qdrant_ok, "host": settings.qdrant_host, "port": settings.qdrant_port},
        "llm": {"model": settings.groq_model, "configured": bool(settings.groq_api_key)},
        "embeddings": {"model": settings.embed_model},
        "registries": {"institutions": len(il.load_all()), "regulations": len(rl.load_all())},
        "collections": collections,
        "onboarding": ONBOARDING,
    }


def search(query: str, top_k_per_collection: int = 2, limit: int = 8) -> list[dict]:
    """Semantic search across every indexed collection, best matches first."""
    client = rag.get_qdrant()
    existing = {c.name for c in client.get_collections().collections}
    results: list[dict] = []
    seen: set[int] = set()  # several reg categories share source PDFs — dedupe chunks
    for name, label, module in _all_collections():
        if name not in existing:
            continue
        for hit in rag.search(name, query, top_k=top_k_per_collection):
            key = hash(hit["text"][:300])
            if key in seen:
                continue
            seen.add(key)
            results.append({
                "module": module,
                "collection_label": label,
                "text": hit["text"][:600],
                "source": hit["source"],
                "page": hit["page"],
                "score": hit["score"],
            })
    results.sort(key=lambda r: r["score"], reverse=True)
    return results[:limit]


ASK_PROMPT = (
    "Answer the question below for GICC leadership using only the context. "
    "For a factual question: maximum 2 short paragraphs (~120 words), or a tight "
    "bullet list if the question enumerates. For a briefing/synthesis request "
    "(top risks, board briefing, compliance posture): use short labelled sections "
    "or numbered points, maximum ~250 words. Cite inline as (document, p.X), or "
    "just (document) when the source has no page. If the indexed sources cannot "
    "answer, say exactly what is missing in one sentence. Mark inferences "
    "[AI INTERPRETATION]. No preamble.\n\n"
    "QUESTION: {question}"
)


def _registry_context() -> list[dict]:
    """Structured platform knowledge injected into every Ask call.

    Priorities, effective dates and active alerts live in the registry — not in
    PDF text — so questions like 'what needs immediate action?' can't be answered
    by vector search alone."""
    rows: list[dict] = []
    cats = rl.load_all()
    if cats:
        lines = [
            f"- {c['display_name']}: priority {c.get('priority', 'medium')}"
            + (f", effective {c['effective_date']}" if c.get("effective_date") else "")
            + (f" — {c['applicability']}" if c.get("applicability") else "")
            for c in cats
        ]
        rows.append({
            "text": "RBI regulation categories tracked for GICC (with priority set by "
            "the intelligence team):\n" + "\n".join(lines),
            "source": "GICC regulatory registry",
            "page": None,
        })
    try:
        from app.services.regulatory import regulatory_alerts

        lines = [
            f"- [{a.severity.upper()}] {a.title} ({a.category}): {a.summary} "
            f"Required action: {a.action_required}"
            for a in regulatory_alerts()
        ]
        rows.append({
            "text": "Active regulatory alerts for GICC:\n" + "\n".join(lines),
            "source": "Genesis regulatory alerts",
            "page": None,
        })
    except Exception:
        pass
    return rows


def ask(question: str, limit: int = 10) -> dict:
    """Ask Genesis: cross-collection retrieval + one grounded, cited answer."""
    hits = search(question, top_k_per_collection=2, limit=limit)
    strong = [h for h in hits if h["score"] >= 0.4]
    if not strong and not _registry_context():
        return {
            "question": question,
            "answer": "The indexed intelligence collections do not contain material "
            "relevant to this question. Try rephrasing, or check whether the topic "
            "has been ingested (Administration → Intelligence Management).",
            "results": hits,
        }
    try:
        answer = rag.generate(ASK_PROMPT.format(question=question), _registry_context() + strong)
    except Exception:
        # LLM unavailable (e.g. daily rate limit) — retrieval still has value.
        answer = (
            "AI synthesis is temporarily unavailable (LLM rate limit). The most "
            "relevant source excerpts are shown below — citations remain valid."
        )
    return {"question": question, "answer": answer, "results": strong}
