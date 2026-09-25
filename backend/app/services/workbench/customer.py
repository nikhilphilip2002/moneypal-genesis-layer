"""External customer profile retrieval service grounded in Qdrant.

Retrieves approved records from External_customer_details using exact payload filtering on
the canonical customer ID. Never infers customer identity from embedding similarity.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from qdrant_client import QdrantClient
from qdrant_client.http import models as qm

from app.core.config import settings
from app.services.workbench.results import Evidence, SourceResult

logger = logging.getLogger(__name__)

# Approved fields permitted in outbound customer profile payload
APPROVED_FIELDS = frozenset({
    "customer_id",
    "customer_name",
    "occupation",
    "city",
    "district",
    "channel",
    "external_source",
    "source_name",
    "scraped_snippet",
})


def _get_qdrant_client() -> QdrantClient:
    return QdrantClient(
        url=settings.qdrant_url,
        api_key=settings.qdrant_api_key,
        timeout=settings.qdrant_timeout,
    )


def _query_qdrant_sync(
    canonical_id: str,
    collection_name: str,
) -> list[dict[str, Any]]:
    client = _get_qdrant_client()
    payload_filter = qm.Filter(
        must=[
            qm.FieldCondition(
                key="customer_id",
                match=qm.MatchValue(value=canonical_id),
            )
        ]
    )
    points, _ = client.scroll(
        collection_name=collection_name,
        scroll_filter=payload_filter,
        limit=50,
        with_payload=True,
        with_vectors=False,
    )
    records: list[dict[str, Any]] = []
    for point in points:
        payload = point.payload or {}
        # Authoritative customer_id match verification
        if str(payload.get("customer_id", "")).strip() == canonical_id:
            sanitized = {
                k: payload[k]
                for k in APPROVED_FIELDS
                if k in payload and payload[k] is not None
            }
            records.append(sanitized)
    return records


async def lookup_customer_profile(
    customer_id: str,
    *,
    collection_name: str | None = None,
) -> SourceResult:
    """Look up customer profile by exact canonical customer ID.
    
    Returns a bounded SourceResult with source="customer", sensitive=True,
    approved fields only, provenance citations, and a clear no-match state.
    """
    canonical_id = str(customer_id).strip()
    if not canonical_id:
        return SourceResult(
            source="customer",
            card_type="profile",
            payload={
                "customer_id": "",
                "found": False,
                "records": [],
                "message": "A valid, non-empty customer ID is required.",
            },
            summary="A valid customer ID is required to look up a customer profile.",
            complete=False,
            limitation="No customer ID provided.",
            sensitive=True,
        )

    target_collection = collection_name or settings.external_customer_collection

    try:
        records = await asyncio.to_thread(_query_qdrant_sync, canonical_id, target_collection)
    except Exception as exc:  # noqa: BLE001 - external retrieval degrades gracefully
        logger.warning("customer profile lookup failed for customer_id=%r: %s", canonical_id, exc)
        return SourceResult(
            source="customer",
            card_type="error",
            payload={
                "message": "External customer intelligence is temporarily unavailable.",
                "retryable": True,
            },
            summary="External customer intelligence is temporarily unavailable.",
            complete=False,
            sensitive=True,
        )

    if not records:
        return SourceResult(
            source="customer",
            card_type="profile",
            payload={
                "customer_id": canonical_id,
                "found": False,
                "records": [],
                "message": f"No external profile found for customer ID {canonical_id}.",
            },
            summary=f"No external profile found for customer ID {canonical_id}.",
            complete=False,
            limitation=f"No external profile matched customer ID {canonical_id}.",
            sensitive=True,
        )

    # Aggregate records and build evidence + citations
    evidence: list[Evidence] = []
    sources: list[dict[str, Any]] = []
    seen_urls: set[str] = set()

    primary_name = next((r.get("customer_name") for r in records if r.get("customer_name")), "")
    primary_occupation = next((r.get("occupation") for r in records if r.get("occupation")), "")
    primary_city = next((r.get("city") for r in records if r.get("city")), "")
    primary_district = next((r.get("district") for r in records if r.get("district")), "")
    channels = sorted({str(r.get("channel")) for r in records if r.get("channel")})

    for r in records:
        snippet = str(r.get("scraped_snippet") or "").strip()
        doc = str(r.get("source_name") or "").strip()
        url = str(r.get("external_source") or "").strip()
        if snippet:
            evidence.append(
                Evidence(
                    excerpt=snippet,
                    document=doc or "External Customer Profile",
                    url=url,
                    untrusted=True,
                )
            )
        if url and url not in seen_urls:
            seen_urls.add(url)
            sources.append({
                "document": doc or "External Profile",
                "title": doc or "External Profile",
                "name": doc or "External Profile",
                "url": url,
                "channel": r.get("channel", ""),
            })

    name_str = f" ({primary_name})" if primary_name else ""
    summary = (
        f"Retrieved external customer profile for customer ID {canonical_id}{name_str} "
        f"across {len(records)} record(s) from external vector store (Qdrant). "
        "EXTERNAL PROFILE ONLY: This source provides external social/web profile annotations. "
        "It does NOT contain internal loan accounts, KYC documents, or loan-book data. "
        "For loan-book figures, accounts, or KYC, query PostgreSQL views gold.customers "
        f"and gold.loan_accounts using the query tool for customer_id = '{canonical_id}'."
    )

    return SourceResult(
        source="customer",
        card_type="profile",
        payload={
            "customer_id": canonical_id,
            "found": True,
            "customer_name": primary_name,
            "occupation": primary_occupation,
            "city": primary_city,
            "district": primary_district,
            "channels": channels,
            "records": records,
        },
        summary=summary,
        sources=sources,
        evidence=evidence,
        complete=True,
        sensitive=True,
    )
