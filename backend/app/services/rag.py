from __future__ import annotations

import hashlib
import json
import math
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.core.config import settings


def normalize_collection_name(value: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9_]+", "_", value.lower()).strip("_")
    return f"{settings.collection_prefix}{value}"


def chunk_text(text: str, chunk_size: int = 1800, overlap: int = 250) -> list[str]:
    clean = re.sub(r"\s+", " ", text).strip()
    if not clean:
        return []
    chunks: list[str] = []
    start = 0
    while start < len(clean):
        end = min(start + chunk_size, len(clean))
        chunks.append(clean[start:end])
        if end == len(clean):
            break
        start = max(end - overlap, start + 1)
    return chunks


def _hash_embedding(text: str, size: int = 1024) -> list[float]:
    vector = [0.0] * size
    tokens = re.findall(r"[a-zA-Z0-9]+", text.lower())
    for token in tokens:
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        idx = int.from_bytes(digest[:4], "big") % size
        vector[idx] += 1.0
    norm = math.sqrt(sum(v * v for v in vector)) or 1.0
    return [v / norm for v in vector]


@lru_cache
def _embedding_model() -> Any | None:
    try:
        from sentence_transformers import SentenceTransformer

        return SentenceTransformer(settings.embedding_model)
    except Exception:
        return None


def embed_text(text: str) -> list[float]:
    model = _embedding_model()
    if model is None:
        return _hash_embedding(text, settings.vector_size)
    vector = model.encode(text, normalize_embeddings=True)
    return vector.tolist()


@lru_cache
def qdrant_client() -> Any:
    from qdrant_client import QdrantClient

    return QdrantClient(
        url=settings.qdrant_url,
        api_key=settings.qdrant_api_key,
        timeout=settings.qdrant_timeout,
    )


def search_qdrant(collection_name: str, query: str, limit: int = 6) -> list[dict[str, Any]]:
    try:
        client = qdrant_client()
        hits = client.search(
            collection_name=collection_name,
            query_vector=embed_text(query),
            limit=limit,
            with_payload=True,
        )
        return [dict(hit.payload or {}, score=hit.score) for hit in hits]
    except Exception:
        return search_local_index(collection_name, query, limit)


def search_local_index(collection_name: str, query: str, limit: int = 6) -> list[dict[str, Any]]:
    if not settings.local_index_path.exists():
        return []
    query_terms = set(re.findall(r"[a-zA-Z0-9]+", query.lower()))
    scored: list[tuple[int, dict[str, Any]]] = []
    with settings.local_index_path.open("r", encoding="utf-8") as file:
        for line in file:
            item = json.loads(line)
            if item.get("collection") != collection_name:
                continue
            text = item.get("text", "")
            terms = set(re.findall(r"[a-zA-Z0-9]+", text.lower()))
            score = len(query_terms & terms)
            scored.append((score, item))
    scored.sort(key=lambda row: row[0], reverse=True)
    return [item for score, item in scored[:limit] if score > 0] or [item for _, item in scored[:limit]]


def build_context(hits: list[dict[str, Any]], max_chars: int = 9000) -> str:
    parts: list[str] = []
    total = 0
    for hit in hits:
        label = f"{hit.get('document', 'Document')} p.{hit.get('page', '?')}"
        text = hit.get("text", "")
        block = f"[{label}]\n{text}"
        if total + len(block) > max_chars:
            break
        parts.append(block)
        total += len(block)
    return "\n\n".join(parts)


def generate_with_groq(prompt: str) -> str | None:
    if not settings.groq_api_key:
        return None
    try:
        from groq import Groq

        client = Groq(api_key=settings.groq_api_key)
        completion = client.chat.completions.create(
            model=settings.groq_model,
            messages=[
                {
                    "role": "system",
                    "content": "You are a concise regulatory intelligence analyst for Indian NBFC leadership.",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
        )
        return completion.choices[0].message.content
    except Exception:
        return None


def extractive_regulatory_summary(category_name: str, context: str, effective_date: str) -> str:
    sentences = re.split(r"(?<=[.!?])\s+", context)
    selected = [sentence.strip() for sentence in sentences if len(sentence.strip()) > 60][:8]
    body = " ".join(selected[:4]) or "No indexed source text was available for this category."
    return (
        f"**Executive Summary**\n{body[:900]}\n\n"
        f"**Applicability**\nThis briefing is prepared for NBFC leadership, with specific attention to NBFCs below Rs. 500 crore where the cited RBI text applies or creates governance expectations.\n\n"
        f"**Business Impact**\nGICC should review policies, operating controls, board reporting, customer communication, and evidence retention against the cited RBI requirements for {category_name}.\n\n"
        f"**Compliance Actions**\n"
        f"- Map the category requirements to current GICC policies and owners.\n"
        f"- Create an evidence checklist for board, audit, and operational review.\n"
        f"- Track open compliance gaps with target closure dates.\n"
        f"- Preserve source circulars and management approvals for inspection readiness.\n\n"
        f"**Effective Date**\n{effective_date}"
    )


def key_points_from_text(text: str) -> list[str]:
    bullets = re.findall(r"^- (.+)$", text, flags=re.MULTILINE)
    if bullets:
        return bullets[:5]
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", re.sub(r"\*\*.*?\*\*", "", text)) if len(s.strip()) > 40]
    return sentences[:5]
