"""Bounded, read-only retrieval of private external customer/agent evidence."""

from __future__ import annotations

import asyncio
from typing import Literal
from urllib.parse import quote

import requests

from app.core.config import settings
from app.services.nlq.pii import PII_ROLES, may_see_pii
from app.services.workbench.access import SourceAccessPolicy
from app.services.workbench.results import Evidence, SourceResult


LookupBy = Literal["id", "name"]


def _lookup(
    identifier: str, entity_type: str, lookup_by: LookupBy = "id"
) -> tuple[list[dict], bool]:
    if lookup_by == "name":
        field = "agent_name" if entity_type == "agent" else "customer_name"
        conditions = [{"key": field, "match": {"text": identifier}}]
    else:
        values: list[str | int] = [identifier]
        if identifier.isdecimal() and str(int(identifier)) == identifier:
            values.append(int(identifier))
        field = "agent_id" if entity_type == "agent" else "customer_id"
        conditions = [
            {"key": field, "match": {"value": value}} for value in values
        ]
    response = requests.post(
        f"{settings.customer_details_qdrant_url.rstrip('/')}/collections/"
        f"{quote(settings.customer_details_collection, safe='')}/points/scroll",
        headers={"api-key": settings.qdrant_api_key} if settings.qdrant_api_key else {},
        json={
            "filter": {"should": conditions},
            "limit": 6, "with_payload": True, "with_vector": False,
        },
        timeout=(3.0, 12.0),
    )
    response.raise_for_status()
    result = response.json()["result"]
    points = result["points"]
    if not isinstance(points, list) or any(
        not isinstance(point, dict) or not isinstance(point.get("payload"), dict)
        for point in points
    ):
        raise ValueError("Invalid Qdrant result")
    return [point.get("payload") or {} for point in points], result.get("next_page_offset") is not None


async def search_customer_details(
    identifier: str, *, entity_type: Literal["customer", "agent"],
    role: str, policy: SourceAccessPolicy, lookup_by: LookupBy = "id",
) -> SourceResult:
    policy.require_customer_details()
    try:
        records, more = await asyncio.to_thread(
            _lookup, identifier.strip(), entity_type, lookup_by
        )
    except (requests.RequestException, ValueError, KeyError, TypeError):
        message = "External data is temporarily unavailable. The loan book result is still available."
        return SourceResult(
            source="db", card_type="customer_360", sensitive=True, complete=False,
            summary=message, limitation=message,
            payload={"status": "unavailable", "entity_type": entity_type, "message": message, "records": []},
        )

    permitted = role in PII_ROLES and may_see_pii(role)
    displayed: list[dict] = []
    evidence: list[Evidence] = []
    # Only expose known fields. Unknown payloads and free text may contain arbitrary PII.
    for record in records:
        if permitted:
            details = {
                key: str(record[key])[:1600]
                for key in (
                    "customer_id", "customer_name", "agent_id", "agent_name",
                    "occupation", "city", "district", "channel", "source_name",
                ) if record.get(key) is not None
            }
            snippet = str(record.get("scraped_snippet") or record.get("text") or "")[:1600]
            document = str(record.get("source_name") or "Qdrant external details")[:200]
        else:
            details = {"identity": "[masked]"}
            snippet = "External evidence found. Personal details and document text are hidden for your role."
            document = "Qdrant external details"
        displayed.append({"details": details, "snippet": snippet, "source": document})
        evidence.append(Evidence(excerpt=snippet, document=document))
    message = (
        f"Found {len(displayed)} external evidence record(s) for this {entity_type}."
        if displayed
        else f"Couldn't find external data for this {entity_type}."
    )
    limitation = "Showing the first 6 matching external records." if more else ""
    return SourceResult(
        source="db", card_type="customer_360", sensitive=True,
        summary=message, evidence=evidence, complete=not more, limitation=limitation,
        payload={
            "status": "found" if displayed else "not_found", "entity_type": entity_type,
            "lookup_by": lookup_by, "message": message, "records": displayed,
            "limitation": limitation,
        },
    )
