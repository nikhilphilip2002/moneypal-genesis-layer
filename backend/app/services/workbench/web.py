"""Governed live-web retrieval for the Workbench.

Only a sanitized public subquestion crosses this boundary. Search results are untrusted
evidence: they are bounded, normalized, ranked by the curated authority registry, and then
passed to synthesis as quoted context rather than executable instructions.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import yaml

from app.core.config import BASE_DIR, settings
from app.mcp import exa_client


class UnsafeWebQuery(ValueError):
    pass


_PRIVATE_PATTERNS = (
    re.compile(r"\b(?:customer|borrower)\s*(?:id|number|no\.?|#)\s*[:#-]?\s*[a-z0-9-]+", re.I),
    re.compile(r"\b(?:loan|account)\s*(?:id|number|no\.?|#)\s*[:#-]?\s*[a-z0-9-]+", re.I),
    re.compile(r"\b(?:phone|mobile|aadhaar|pan)\s*(?:number|no\.?|#)?\s*[:#-]?\s*[a-z0-9-]+", re.I),
    re.compile(r"\brepayment history (?:for|of)\b", re.I),
    re.compile(
        r"\b(?:named\s+)?(?:borrower|customer)\s+"
        r"(?!trends?\b|segments?\b|market\b|behaviou?r\b|demand\b)"
        r"[A-Za-z][A-Za-z.'-]+(?:\s+[A-Za-z][A-Za-z.'-]+){0,3}\b",
        re.I,
    ),
)
_COMPARISON_SPLIT = re.compile(
    r"\b(?:compare(?:d)?\s+(?:with|against)|versus|vs\.?|against|benchmark(?:ed)?\s+against)\b",
    re.I,
)
_INTERNAL_GENERIC = re.compile(
    r"\b(?:our|loan book|portfolio|borrowers?|customers?|accounts?|repayments?|"
    r"collections?|outstanding|disbursements?|sanctions?)\b",
    re.I,
)
_EXTERNAL_ANCHOR = re.compile(
    r"\b(?:RBI|MoSPI|India|Karnataka|IMF|World Bank|OECD|UN|government|industry|"
    r"market|economy|economic|inflation|GDP|GVA|CPI|IIP|repo|fiscal|trade|FDI|news)\b",
    re.I,
)


def public_query(question: str) -> str:
    """Return a public-only query or reject content that must stay inside the bank."""
    text = " ".join(question.split()).strip()
    if not text:
        raise UnsafeWebQuery("A public web-search question is required.")
    for pattern in _PRIVATE_PATTERNS:
        if pattern.search(text):
            raise UnsafeWebQuery("Private customer or account details cannot be sent to web search.")

    # In a hybrid comparison, keep the explicitly external side and discard the internal
    # side. The DB node receives its own separate intent from the router.
    parts = _COMPARISON_SPLIT.split(text, maxsplit=1)
    if len(parts) == 2:
        external = next(
            (part.strip(" ,.?-") for part in reversed(parts) if _EXTERNAL_ANCHOR.search(part)),
            "",
        )
        if external:
            text = external
    if _INTERNAL_GENERIC.search(text) and not _EXTERNAL_ANCHOR.search(text):
        raise UnsafeWebQuery("Internal banking questions must use the governed loan-book source.")
    return text[:600]


@dataclass(frozen=True, slots=True)
class Authority:
    id: str
    label: str
    tier: int
    domains: tuple[str, ...]
    topics: tuple[str, ...]


@dataclass(slots=True)
class WebEvidence:
    title: str
    url: str
    publisher: str
    domain: str
    excerpt: str
    published_at: str | None
    retrieved_at: str
    source_tier: int
    primary: bool

    def citation(self) -> dict[str, Any]:
        return {
            "document": self.title,
            "title": self.title,
            "url": self.url,
            "publisher": self.publisher,
            "domain": self.domain,
            "published_at": self.published_at,
            "retrieved_at": self.retrieved_at,
            "source_tier": self.source_tier,
            "primary": self.primary,
        }


def _load_authorities() -> tuple[Authority, ...]:
    path = BASE_DIR / "registry" / "economic_web_sources.yaml"
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return tuple(
        Authority(
            id=str(item["id"]), label=str(item["label"]), tier=int(item["tier"]),
            domains=tuple(item.get("domains", [])), topics=tuple(item.get("topics", [])),
        )
        for item in raw.get("sources", [])
    )


AUTHORITIES = _load_authorities()
_BY_DOMAIN = {
    domain.lower(): authority for authority in AUTHORITIES for domain in authority.domains
}

_TOPIC_CUES: dict[str, re.Pattern[str]] = {
    "gdp": re.compile(r"\b(?:gdp|gva|national accounts?|economic growth)\b", re.I),
    "inflation": re.compile(r"\b(?:inflation|cpi|wpi|price index)\b", re.I),
    "employment": re.compile(r"\b(?:employment|unemployment|plfs|labou?r)\b", re.I),
    "monetary_policy": re.compile(r"\b(?:repo|reverse repo|monetary policy|policy rate)\b", re.I),
    "banking": re.compile(r"\b(?:banking|bank credit|deposits?|npa|nbfc)\b", re.I),
    "budget": re.compile(r"\b(?:budget|government receipts?|government expenditure)\b", re.I),
    "fiscal": re.compile(r"\b(?:fiscal|deficit|public debt)\b", re.I),
    "trade": re.compile(r"\b(?:trade|exports?|imports?|dgft|balance of payments)\b", re.I),
    "fdi": re.compile(r"\b(?:fdi|foreign direct investment)\b", re.I),
    "tax": re.compile(r"\b(?:tax|gst|income tax)\b", re.I),
    "policy": re.compile(r"\b(?:policy|scheme|bill|legislation|parliament)\b", re.I),
    "news": re.compile(r"\b(?:news|announcement|latest|recent|today|current)\b", re.I),
}


def _topics(query: str) -> set[str]:
    matched = {topic for topic, cue in _TOPIC_CUES.items() if cue.search(query)}
    return matched or {"macro"}


def domains_for(query: str, tier: int) -> list[str]:
    topics = _topics(query)
    domains = [
        domain
        for authority in AUTHORITIES
        if authority.tier == tier and topics.intersection(authority.topics)
        for domain in authority.domains
    ]
    return list(dict.fromkeys(domains))


_TRACKING_KEYS = {"fbclid", "gclid", "mc_cid", "mc_eid"}


def _canonical_url(value: str) -> str | None:
    try:
        parsed = urlsplit(value.strip().rstrip(".,);]"))
    except ValueError:
        return None
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None
    query = urlencode([
        (key, val) for key, val in parse_qsl(parsed.query, keep_blank_values=True)
        if not key.lower().startswith("utm_") and key.lower() not in _TRACKING_KEYS
    ])
    return urlunsplit((parsed.scheme, parsed.netloc.lower(), parsed.path, query, ""))


def _authority(domain: str) -> Authority | None:
    host = domain.lower().removeprefix("www.")
    return next(
        (authority for key, authority in _BY_DOMAIN.items() if host == key or host.endswith(f".{key}")),
        None,
    )


def _candidate_results(structured: Any) -> list[dict[str, Any]]:
    if isinstance(structured, list):
        return [item for item in structured if isinstance(item, dict)]
    if not isinstance(structured, dict):
        return []
    for key in ("results", "data", "items"):
        value = structured.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
        if isinstance(value, dict):
            nested = _candidate_results(value)
            if nested:
                return nested
    return []


_MARKDOWN_LINK = re.compile(r"\[([^\]]{1,240})\]\((https?://[^\s)]+)\)")
_BARE_URL = re.compile(r"https?://[^\s<>\]})]+")


def normalize(result: exa_client.ExaToolResult) -> list[WebEvidence]:
    retrieved = datetime.now(UTC).isoformat()
    evidence: list[WebEvidence] = []
    for item in _candidate_results(result.structured):
        raw_url = str(item.get("url") or item.get("id") or "")
        url = _canonical_url(raw_url)
        if not url:
            continue
        host = urlsplit(url).netloc.removeprefix("www.")
        authority = _authority(host)
        title = str(item.get("title") or item.get("name") or host)[:300]
        excerpt = str(
            item.get("summary") or item.get("text") or item.get("highlight")
            or item.get("snippet") or ""
        )[:4000]
        evidence.append(WebEvidence(
            title=title, url=url, publisher=authority.label if authority else host,
            domain=host, excerpt=excerpt,
            published_at=str(item.get("publishedDate") or item.get("published_at") or "") or None,
            retrieved_at=retrieved, source_tier=authority.tier if authority else 5,
            primary=bool(authority and authority.tier <= 2),
        ))

    if not evidence:
        links = _MARKDOWN_LINK.findall(result.text)
        if not links:
            links = [(urlsplit(url).netloc, url) for url in _BARE_URL.findall(result.text)]
        for title, raw_url in links:
            url = _canonical_url(raw_url)
            if not url:
                continue
            host = urlsplit(url).netloc.removeprefix("www.")
            authority = _authority(host)
            evidence.append(WebEvidence(
                title=title.strip() or host, url=url,
                publisher=authority.label if authority else host, domain=host,
                excerpt="", published_at=None, retrieved_at=retrieved,
                source_tier=authority.tier if authority else 5,
                primary=bool(authority and authority.tier <= 2),
            ))

    unique: dict[str, WebEvidence] = {}
    for item in evidence:
        unique.setdefault(item.url, item)
    return sorted(unique.values(), key=lambda item: item.source_tier)


_cache: dict[str, tuple[float, exa_client.ExaToolResult, list[WebEvidence]]] = {}
_daily: dict[tuple[str, str], int] = {}


def _consume_search(user: str, today: str) -> None:
    usage_key = (user, today)
    if _daily.get(usage_key, 0) >= settings.exa_daily_user_limit:
        raise exa_client.ExaRateLimitError("Your daily live-web search allowance has been reached.")
    _daily[usage_key] = _daily.get(usage_key, 0) + 1


async def retrieve(question: str, *, user: str) -> tuple[str, list[WebEvidence], str]:
    query = public_query(question)
    cache_key = query.casefold()
    cached = _cache.get(cache_key)
    if cached and time.monotonic() - cached[0] <= settings.exa_cache_ttl_s:
        return query, cached[2], cached[1].text

    today = datetime.now(UTC).date().isoformat()
    # Search the most relevant official sources first. Lower tiers are a fallback, never a
    # peer vote that can out-rank an available regulator or statistics agency.
    result: exa_client.ExaToolResult | None = None
    evidence: list[WebEvidence] = []
    for tier in (1, 2, 3):
        domains = domains_for(query, tier)
        if not domains:
            continue
        _consume_search(user, today)
        result = await exa_client.search(
            query, num_results=settings.exa_search_max_results, include_domains=domains,
        )
        evidence = normalize(result)[: settings.exa_search_max_results]
        if evidence:
            break
    if result is None:
        _consume_search(user, today)
        result = await exa_client.search(query, num_results=settings.exa_search_max_results)
        evidence = normalize(result)[: settings.exa_search_max_results]
    if not evidence:
        raise exa_client.ExaMCPError("Exa returned no citable web results.")
    _cache[cache_key] = (time.monotonic(), result, evidence)
    return query, evidence, result.text


def context(raw_text: str, evidence: list[WebEvidence]) -> str:
    header = json.dumps([asdict(item) for item in evidence], ensure_ascii=False, default=str)
    return f"NORMALIZED SOURCES:\n{header}\n\nUNTRUSTED SEARCH CONTENT:\n{raw_text[:16000]}"
