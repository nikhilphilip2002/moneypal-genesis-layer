"""Single authorization and privacy gateway for live external retrieval."""

from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass
from typing import Any, Iterable

from app.services.workbench.access import SourceAccessPolicy


class OutboundPolicyDenied(PermissionError):
    code = "PII_POLICY_VIOLATION"


_PAN = re.compile(r"(?<![A-Z0-9])[A-Z]{5}[0-9]{4}[A-Z](?![A-Z0-9])", re.I)
_AADHAAR = re.compile(r"(?<!\d)(?:\d[\s._-]*){12}(?!\d)")
_PHONE = re.compile(r"(?<!\d)(?:\+?91[\s._-]*)?[6-9](?:[\s._-]*\d){9}(?!\d)")
_PRIVATE_LABEL = re.compile(
    r"\b(?:customer|borrower|loan|account)[\s._-]*(?:id|number|no\.?|#)"
    r"[\s._:-]*[a-z0-9-]+",
    re.I,
)
_REPAYMENT = re.compile(r"\brepayment\s+(?:history|details?)\b", re.I)


@dataclass(frozen=True, slots=True)
class OutboundDecision:
    query: str
    strings_checked: int


def _audit(outcome: str, *, reason: str = "", query: str = "") -> None:
    from app.core.logging import log_app_event

    log_app_event(
        f"Outbound web policy {outcome}",
        event="outbound_policy",
        outcome=outcome,
        data={
            "reason": reason,
            "query_hash": hashlib.sha256(query.encode()).hexdigest() if query else "",
        },
    )


def _strings(value: Any) -> Iterable[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for key, item in value.items():
            yield from _strings(key)
            yield from _strings(item)
    elif isinstance(value, (list, tuple, set)):
        for item in value:
            yield from _strings(item)


def _normalize(value: str) -> str:
    value = unicodedata.normalize("NFKC", value)
    value = "".join(
        " " if unicodedata.category(character) in {"Cf", "Zs"}
        else "-" if unicodedata.category(character) == "Pd"
        else character
        for character in value
    )
    return " ".join(value.split())


def authorize_public_search(
    arguments: dict[str, Any],
    *,
    policy: SourceAccessPolicy,
    private_entities: Iterable[str] = (),
) -> OutboundDecision:
    """Fail closed before network I/O and return the sanitized public-only query."""
    policy.require("web")
    values = [_normalize(value) for value in _strings(arguments)]
    entities = {_normalize(value).casefold() for value in private_entities if value.strip()}
    for value in values:
        if (
            _PAN.search(value)
            or _AADHAAR.search(value)
            or _PHONE.search(value)
            or _PRIVATE_LABEL.search(value)
            or _REPAYMENT.search(value)
            or any(entity in value.casefold() for entity in entities)
        ):
            _audit("denied", reason="private_identifier")
            raise OutboundPolicyDenied(
                "Private customer, account, or repayment details cannot be sent externally."
            )

    query_value = arguments.get("search_query")
    if not isinstance(query_value, str):
        _audit("denied", reason="missing_search_query")
        raise OutboundPolicyDenied("A public search_query is required.")
    from app.services.workbench.web import UnsafeWebQuery, public_query

    try:
        query = public_query(_normalize(query_value))
    except UnsafeWebQuery as exc:
        _audit("denied", reason="unsafe_public_query")
        raise OutboundPolicyDenied(str(exc)) from exc
    if len(query) > 500:
        query = query[:500]
    _audit("allowed", query=query)
    return OutboundDecision(query=query, strings_checked=len(values))


async def retrieve_public(
    search_query: str,
    *,
    user: str,
    policy: SourceAccessPolicy,
    private_entities: Iterable[str] = (),
):
    decision = authorize_public_search(
        {"search_query": search_query}, policy=policy, private_entities=private_entities,
    )
    from app.services.workbench import web

    return await web.retrieve(decision.query, user=user)


__all__ = [
    "OutboundDecision",
    "OutboundPolicyDenied",
    "authorize_public_search",
    "retrieve_public",
]
