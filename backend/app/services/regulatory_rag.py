"""Regulatory policy adapter over the shared ``genesis_core.rag`` engine."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from genesis_core import rag

from app.core.config import settings

logger = logging.getLogger(__name__)

REGULATORY_SYSTEM = (
    "You are a concise regulatory intelligence analyst for Indian NBFC leadership. "
    "Use only the supplied context, preserve source meaning, and do not invent obligations."
)


def search_local_index(
    collection_name: str, query: str, limit: int = 6
) -> list[dict[str, Any]]:
    """Search the ingestion JSONL when the shared Qdrant service is unavailable."""
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
            scored.append((len(query_terms & terms), item))
    scored.sort(key=lambda row: row[0], reverse=True)
    matched = [item for score, item in scored[:limit] if score > 0]
    return matched or [item for _, item in scored[:limit]]


def search(
    collection_name: str, query: str, limit: int = 6
) -> list[dict[str, Any]]:
    """Use the shared vector engine, falling back to the regulatory local index."""
    try:
        hits = rag.search(collection_name, query, top_k=limit)
        return [
            {
                **hit,
                "document": hit.get("source") or "Document",
            }
            for hit in hits
        ]
    except Exception as exc:  # noqa: BLE001 - the local index is an intentional fallback
        logger.warning("Qdrant regulatory search unavailable: %s", exc)
        return search_local_index(collection_name, query, limit)


def build_context(hits: list[dict[str, Any]], max_chars: int = 9000) -> str:
    parts: list[str] = []
    total = 0
    for hit in hits:
        document = hit.get("document") or hit.get("source") or "Document"
        page = hit.get("page") or hit.get("page_number")
        label = f"{document} p.{page}" if page else document
        block = f"[{label}]\n{hit.get('text', '')}"
        if total + len(block) > max_chars:
            break
        parts.append(block)
        total += len(block)
    return "\n\n".join(parts)


def generate_brief(prompt: str, hits: list[dict[str, Any]]) -> str | None:
    """Generate through the repository's shared grounded RAG client."""
    try:
        return rag.generate(prompt, hits, system=REGULATORY_SYSTEM)
    except Exception as exc:  # noqa: BLE001 - extractive fallback remains available
        logger.warning("Regulatory generation unavailable: %s", exc)
        return None


def extractive_regulatory_summary(
    category_name: str, context: str, effective_date: str
) -> str:
    sentences = re.split(r"(?<=[.!?])\s+", context)
    selected = [
        sentence.strip()
        for sentence in sentences
        if len(sentence.strip()) > 60
    ][:8]
    body = (
        " ".join(selected[:4])
        or "No indexed source text was available for this category."
    )
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
    sentences = [
        sentence.strip()
        for sentence in re.split(
            r"(?<=[.!?])\s+", re.sub(r"\*\*.*?\*\*", "", text)
        )
        if len(sentence.strip()) > 40
    ]
    return sentences[:5]
