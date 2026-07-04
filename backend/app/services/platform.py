"""Platform administration + cross-collection semantic search (Moneypal Administrator)."""
import re
from functools import lru_cache

from genesis_core import rag
from genesis_core.config import settings

from app.core.config import MACRO_COLLECTION
from app.services import institution_loader as il
from app.services import reg_loader as rl

# Directory/lookup collections (name registries, tabular lists) are answered by
# lexical matching, not vector similarity — semantic search over a table of
# company names scores ~0.03 and gets filtered out. These get keyword retrieval.
LEXICAL_COLLECTIONS = {"reg_nbfc_bank_list"}
# Question scaffolding — stripped from the query to leave the company name.
_QUERY_STOPWORDS = {
    "is", "the", "a", "an", "of", "as", "with", "in", "on", "for", "to", "and",
    "does", "do", "list", "show", "find", "all", "entries", "related", "mention",
    "registered", "registration", "details", "available", "information", "search",
    "companies", "containing", "word", "name", "names", "match", "matching",
    "nbfc", "nbfcs", "arc", "arcs", "rbi", "bank", "listed", "entity", "entities",
    "active", "cancelled", "or", "status", "what", "which", "are", "any",
}
# Ubiquitous company-name suffixes — present in almost every NBFC row, so they
# make poor *distinctive* terms, but stay in the phrase used for exact matching.
_COMPANY_SUFFIXES = {
    "finance", "financial", "capital", "services", "service", "limited", "ltd",
    "private", "pvt", "company", "co", "corporation", "india", "holdings",
    "investment", "investments", "fin", "leasing", "credit",
}

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


@lru_cache(maxsize=4)
def _lexical_index(collection: str) -> list[dict]:
    """Load every chunk of a directory collection once, for keyword matching."""
    client = rag.get_qdrant()
    rows: list[dict] = []
    offset = None
    while True:
        points, offset = client.scroll(
            collection_name=collection, limit=256, offset=offset,
            with_payload=True, with_vectors=False,
        )
        for p in points:
            payload = p.payload or {}
            text = payload.get("text", "")
            rows.append({
                "text": text,
                "lower": text.lower(),
                "source": payload.get("document") or payload.get("source"),
                "page": payload.get("page"),
            })
        if offset is None:
            break
    return rows


def _lexical_hits(collection: str, query: str, top_k: int) -> list[dict]:
    """Rank chunks by how many meaningful query terms they contain (substring)."""
    # phrase_terms keeps company suffixes ("bajaj finance"); core_terms are the
    # distinctive tokens for base scoring ("bajaj").
    phrase_terms = [t for t in re.findall(r"[a-zA-Z0-9&.]+", query.lower())
                    if t not in _QUERY_STOPWORDS and len(t) > 1]
    core_terms = [t for t in phrase_terms if t not in _COMPANY_SUFFIXES] or phrase_terms
    if not core_terms:
        return []
    phrase = " ".join(phrase_terms)
    scored: list[tuple[float, dict]] = []
    for row in _lexical_index(collection):
        matches = sum(1 for t in core_terms if t in row["lower"])
        if not matches:
            continue
        score = float(matches)
        if len(phrase_terms) > 1 and phrase in row["lower"]:
            score += 5  # strong bonus: the exact company name appears verbatim
        scored.append((score, row))
    scored.sort(key=lambda x: x[0], reverse=True)
    hits: list[dict] = []
    for score, row in scored[:top_k]:
        # Center the excerpt on the match — the entity can sit deep in a long
        # table chunk and would otherwise be lost to downstream truncation.
        anchor = phrase if phrase in row["lower"] else core_terms[0]
        pos = row["lower"].find(anchor)
        start = max(0, pos - 120)
        excerpt = row["text"][start:start + 480]
        hits.append({
            "text": ("…" if start else "") + excerpt.strip() + "…",
            "source": row["source"],
            "page": row["page"],
            # Synthetic relevance so lexical hits survive the >=0.4 Ask threshold.
            "score": min(0.99, 0.5 + 0.08 * score),
        })
    return hits


def search(query: str, top_k_per_collection: int = 2, limit: int = 8) -> list[dict]:
    """Search across every indexed collection, best matches first.

    Prose collections use vector similarity; directory/lookup collections
    (LEXICAL_COLLECTIONS) use keyword matching."""
    client = rag.get_qdrant()
    existing = {c.name for c in client.get_collections().collections}
    results: list[dict] = []
    seen: set[int] = set()  # several reg categories share source PDFs — dedupe chunks
    for name, label, module in _all_collections():
        if name not in existing:
            continue
        if name in LEXICAL_COLLECTIONS:
            hits = _lexical_hits(name, query, top_k=max(top_k_per_collection, 3))
        else:
            hits = rag.search(name, query, top_k=top_k_per_collection)
        for hit in hits:
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
    "answer, say exactly what is missing in one sentence. No preamble.\n\n"
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
