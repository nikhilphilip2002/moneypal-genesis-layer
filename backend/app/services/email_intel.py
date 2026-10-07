"""Email intelligence — retrieval over the ingested mailbox collection.

The mailbox corpus lives in its own Qdrant collection, embedded by a *different* model
from the one Genesis uses for macro, competitive and regulatory documents (see
``EMAIL_EMBEDDING_MODEL``). Two collections can sit in the same Qdrant server, but their
vectors are only comparable inside the space that produced them, so this module owns its
embedder and its client and never calls ``genesis_core.rag``.

Ingestion is owned by the separate email service, which keeps this module read-only: it
searches, it never writes, and it never drops or recreates a collection that holds mail.
"""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any

from app.core.config import settings

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_embedder():
    """Load the mailbox embedding model once, on first use.

    Kept separate from ``genesis_core.rag.get_embedder`` deliberately: that one is cached
    per-process under a different model, and two SentenceTransformer instances of different
    sizes cannot be swapped per query.
    """
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(settings.email_embedding_model)


@lru_cache(maxsize=1)
def get_client():
    from qdrant_client import QdrantClient

    return QdrantClient(
        url=settings.email_qdrant_url,
        api_key=settings.email_qdrant_api_key or None,
        timeout=settings.email_qdrant_timeout,
        check_compatibility=False,
    )


def collection() -> str:
    return settings.email_collection


def is_available() -> bool:
    """True when the mailbox collection is present in the configured Qdrant server."""
    try:
        names = {c.name for c in get_client().get_collections().collections}
    except Exception as exc:  # noqa: BLE001 - availability must never raise into a turn
        logger.warning("email collection check failed: %s", exc)
        return False
    return collection() in names


def _clean(value: Any) -> str:
    return " ".join(str(value or "").split())


def search(query: str, top_k: int | None = None) -> list[dict[str, Any]]:
    """Return the best mailbox passages for ``query``.

    Each hit keeps the mail metadata the ingestion service stored alongside the chunk
    (subject, sender, recipients, received time, attachment filename) so a source
    citation names the message rather than an anonymous passage.
    """
    top_k = top_k or settings.email_top_k
    vector = get_embedder().encode(query, normalize_embeddings=True).tolist()
    points = get_client().query_points(
        collection_name=collection(),
        query=vector,
        limit=top_k,
        with_payload=True,
    ).points

    hits: list[dict[str, Any]] = []
    for point in points:
        payload = point.payload or {}
        text = _clean(payload.get("text"))
        if not text:
            continue
        subject = _clean(payload.get("subject")) or "email"
        filename = _clean(payload.get("filename")) or "email body"
        sender = _clean(payload.get("sender"))
        # `source` in the ingested payload is the chunk origin ("body" / "attachment"),
        # not a document name, so the citation label is built from subject + filename.
        label = subject if filename == "email body" else f"{subject} - {filename}"
        hits.append({
            "text": text,
            "subject": subject,
            "sender": sender,
            "received_at": _clean(payload.get("received_at")),
            "email_id": _clean(payload.get("email_id")),
            "conversation_id": _clean(payload.get("conversation_id")),
            "filename": filename,
            # The relative location of the original binary, empty for body-only chunks.
            # Left as the payload has it: email_files.resolve() is what decides whether a
            # path is safe to serve, and the console must not pre-judge that.
            "file_path": _clean(payload.get("file_path")),
            "chunk_source": _clean(payload.get("source")),
            "source": label,
            "document": label,
            "score": round(float(point.score), 4),
        })
    return hits


def email_body(email_id: str, max_chars: int = 4000) -> str:
    """The message text for one mail, reassembled from its body chunks.

    A retrieved hit is often an *attachment* chunk, whose text is the document's contents
    rather than the mail the user actually sent. The console's viewer shows both, so the
    body is fetched separately here. Chunks are stored in order, and they are joined with a
    blank line so paragraph breaks survive.
    """
    if not email_id:
        return ""

    from qdrant_client import models

    try:
        points, _ = get_client().scroll(
            collection_name=collection(),
            scroll_filter=models.Filter(
                must=[
                    models.FieldCondition(
                        key="email_id", match=models.MatchValue(value=email_id)
                    ),
                    models.FieldCondition(
                        key="source", match=models.MatchValue(value="body")
                    ),
                ]
            ),
            limit=64,
            with_payload=True,
        )
    except Exception as exc:  # noqa: BLE001 - a missing body must not fail the turn
        logger.warning("email body lookup failed for %s: %s", email_id, exc)
        return ""

    ordered = sorted(
        (p.payload or {} for p in points),
        key=lambda payload: payload.get("chunk_index") or 0,
    )
    parts = [_clean(payload.get("text")) for payload in ordered]
    return "\n\n".join(part for part in parts if part)[:max_chars]


def search_multi(queries: list[str]) -> list[dict[str, Any]]:
    """Run several focused queries, dedupe, and keep the strongest passages.

    Mirrors the document sources' multi-query behaviour: one question often needs a
    data-seeking phrasing ("vehicle loan documents") as well as the literal wording.
    """
    seen: set[int] = set()
    merged: list[dict[str, Any]] = []
    for query in queries:
        for hit in search(query):
            if hit["score"] < settings.email_min_score:
                continue
            key = hash(hit["text"][:300])
            if key in seen:
                continue
            seen.add(key)
            merged.append(hit)
    merged.sort(key=lambda hit: hit["score"], reverse=True)
    return merged[: settings.email_max_chunks]


def stats() -> dict[str, Any]:
    """Collection shape, for the health endpoint and operator debugging."""
    try:
        info = get_client().get_collection(collection())
    except Exception as exc:  # noqa: BLE001
        return {"available": False, "error": str(exc)}
    vectors = getattr(info.config.params, "vectors", None)
    size = getattr(vectors, "size", None)
    return {
        "available": True,
        "collection": collection(),
        "points": info.points_count,
        "vector_size": size,
        "embedding_model": settings.email_embedding_model,
        "url": settings.email_qdrant_url,
    }
