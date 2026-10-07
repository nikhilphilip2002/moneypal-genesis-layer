"""Source handlers. Each turns an intent into a renderable card.

Thin adapters over services that already exist — the loan-book pipeline and the macro RAG
store. No analytics or retrieval logic is duplicated here; a node's only job is to call the
right service and shape its output into the common `SourceResult` the graph streams.
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
from typing import TYPE_CHECKING, Any

from genesis_core import rag

from app.core.config import MACRO_COLLECTION, EXTERNAL_CUSTOMER_COLLECTION
from app.services.nlq.catalog import get_catalog
from app.services.nlq.catalog.retrieval import retrieve
from app.services.nlq.db import readonly_cursor
from app.services.nlq.normalization import normalize_lending_question
from app.services.workbench.results import Evidence, SourceResult

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from app.services.workbench.access import SourceAccessPolicy


def _require_external(policy: "SourceAccessPolicy | None", source_id: str) -> None:
    if policy is not None:
        policy.require(source_id)


_CUSTOMER_ID_RE = re.compile(
    r"\b(?:customer|borrower|client)\s*(?:id|number|no\.?|#)\s*"
    r"(?:is|was|=|:|-)?\s*(?P<value>[0-9][0-9,]*(?:\.0+)?)\b",
    re.IGNORECASE,
)
_CUSTOMER_NUMBER_RE = re.compile(
    r"\b(?:customer|borrower|client)\s+(?P<value>\d{3,})\b",
    re.IGNORECASE,
)

# Application-owned read-only query over the governed `gold.*` views. The `nlq_readonly`
# role can only SELECT and the pool re-applies `default_transaction_read_only = on` on
# every checkout, so a customer profile can never be mutated from the Workbench.
_CUSTOMER_DB_SQL = (
    "SELECT customer.customer_id::text AS customer_id, "
    "customer.full_name AS customer_name, customer.customer_status, "
    "CONCAT_WS(', ', NULLIF(TRIM(customer.address_line1), ''), "
    "NULLIF(TRIM(customer.address_line2), ''), "
    "NULLIF(TRIM(customer.additional_address), '')) AS address, "
    "customer.city, customer.state, "
    "COALESCE(NULLIF(TRIM(customer.occupation_name), ''), "
    "NULLIF(TRIM(customer.occupation_type), ''), "
    "NULLIF(TRIM(customer.occupation_nature), '')) AS occupation, "
    "customer.home_branch_code, customer.home_branch_name, "
    "customer.agency_code, customer.agency_name, "
    "loan.loan_account_number::text AS loan_account_number, "
    "loan.product_name AS loan_product, "
    "loan.approved_amount AS approved_amount, loan.approved_on AS approved_on "
    "FROM gold.customers AS customer "
    "LEFT JOIN gold.loan_accounts AS loan "
    "ON customer.company_code = loan.company_code "
    "AND customer.customer_id = loan.customer_id "
    "WHERE LOWER(REGEXP_REPLACE(customer.customer_id::text, '\\.0+$', '')) = %s "
    "ORDER BY loan.approved_on DESC, loan.loan_account_number LIMIT 200"
)


def _clean_customer_id(value: str) -> str:
    text = str(value or "").strip().replace(",", "")
    if re.fullmatch(r"\d+\.0+", text):
        return text.split(".", 1)[0]
    return text


def _extract_customer_id(intent: str) -> str | None:
    """Pull a customer id out of e.g. "show me the details of customer id 10455"."""
    match = _CUSTOMER_ID_RE.search(intent) or _CUSTOMER_NUMBER_RE.search(intent)
    if not match:
        return None
    value = _clean_customer_id(match.group("value"))
    return value if value.isdigit() else None


def _read_customer_rows(customer_id: str) -> tuple[list[dict[str, Any]], int]:
    """Read the customer profile and linked loan accounts via the read-only pool."""
    started = time.perf_counter()
    with readonly_cursor() as (_conn, cur):
        cur.execute(_CUSTOMER_DB_SQL, (customer_id,))
        columns = [desc[0] for desc in cur.description] if cur.description else []
        rows = [dict(zip(columns, row)) for row in cur.fetchall()]
    return rows, int((time.perf_counter() - started) * 1000)


def _rupee(value: Any) -> str:
    if value in (None, ""):
        return "—"
    try:
        from app.services.nlq.narrator import format_value
        return format_value(float(value), "inr")
    except (TypeError, ValueError):
        return str(value)


def _as_date(value: Any) -> str:
    if value in (None, ""):
        return "—"
    return str(value)[:10]


def _branch_label(code: Any, name: Any) -> str:
    parts = [part for part in (str(name or "").strip(), str(code or "").strip()) if part]
    return " · ".join(parts) or "—"


def _agency_label(code: Any, name: Any) -> str:
    parts = [part for part in (str(name or "").strip(), str(code or "").strip()) if part]
    return " · ".join(parts) or "—"


def _customer_card_components(
    *, customer_id: str, db_rows: list[dict[str, Any]] | None,
    db_duration_ms: int, chunks: list[dict], db_unavailable: bool,
) -> tuple[dict[str, Any], str, bool, str]:
    """Compose the combined database + external (Qdrant) customer card.

    Returns (chart payload, narration, complete, limitation). The database section and the
    external section are separate rows of one table, so where a fact came from is always
    visible. When the database has the customer but Qdrant has nothing, a note row carries
    the "no external data on this customer" caveat into the rendered table too.
    """
    rows: list[dict[str, Any]] = []
    db_found = bool(db_rows)
    ext_found = bool(chunks)
    name = ""
    loan_rows: list[dict[str, Any]] = []

    if db_found:
        first = db_rows[0]
        name = str(first.get("customer_name") or "").strip()
        title = name or f"Customer {customer_id}"
        profile = [
            ("Customer ID", str(first.get("customer_id") or customer_id)),
            ("Name", name or "—"),
            ("Status", str(first.get("customer_status") or "—")),
            ("Address", str(first.get("address") or "—")),
            ("City", str(first.get("city") or "—")),
            ("State", str(first.get("state") or "—")),
            ("Occupation", str(first.get("occupation") or "—")),
            ("Home branch", _branch_label(first.get("home_branch_code"), first.get("home_branch_name"))),
            ("Agency", _agency_label(first.get("agency_code"), first.get("agency_name"))),
        ]
        for field, value in profile:
            rows.append({"section": "Database", "field": field, "value": value})
        loan_rows = [row for row in db_rows if str(row.get("loan_account_number") or "").strip()]
        for index, loan in enumerate(loan_rows[:6], start=1):
            rows.extend([
                {
                    "section": "Database",
                    "field": f"Linked loan {index} · account number",
                    "value": str(loan.get("loan_account_number") or "—"),
                },
                {
                    "section": "Database",
                    "field": f"Linked loan {index} · product",
                    "value": str(loan.get("loan_product") or "—"),
                },
                {
                    "section": "Database",
                    "field": f"Linked loan {index} · sanctioned amount",
                    "value": _rupee(loan.get("approved_amount")),
                },
                {
                    "section": "Database",
                    "field": f"Linked loan {index} · sanctioned on",
                    "value": _as_date(loan.get("approved_on")),
                },
            ])
        extra = len(loan_rows) - 6
        if extra > 0:
            rows.append({
                "section": "Database",
                "field": "Remaining loans",
                "value": f"{extra} additional linked loan account(s) in the database record.",
            })

    accounts = len({
        str(row.get("loan_account_number")) for row in loan_rows
        if str(row.get("loan_account_number") or "").strip()
    })

    for index, chunk in enumerate(chunks[:5], start=1):
        document = str(chunk.get("document") or chunk.get("source") or "External source")
        excerpt = " ".join(str(chunk.get("text") or "").split())
        rows.append({
            "section": "External (Qdrant)",
            "field": f"External evidence {index} · {document}",
            "value": excerpt[:600] or "—",
        })

    limitation = ""
    if db_found and not ext_found:
        title = name or f"Customer {customer_id}"
        rows.append({
            "section": "External (Qdrant)",
            "field": "External data",
            "value": "No external data available on this customer.",
        })
        limitation = "No external data available on this customer."
        summary = (
            f"Customer {customer_id} ({name}) is present in the database with {accounts:,} "
            f"linked loan account(s). No external data available on this customer."
        )
    elif db_found and ext_found:
        summary = (
            f"Customer {customer_id} ({name}) is present in the database with {accounts:,} "
            f"linked loan account(s); {len(chunks)} external (Qdrant) passage(s) were also "
            "retrieved and are listed separately below."
        )
    else:
        title = f"Customer {customer_id} — external evidence"
        limitation = (
            "The governed database record could not be read for this customer."
            if db_unavailable
            else "No governed database record was found for this customer id."
        )
        summary = (
            f"No database record{' could be read' if db_unavailable else ' was found'} for "
            f"customer {customer_id}; retrieved {len(chunks)} external (Qdrant) passage(s)."
        )

    payload = {
        "chart_type": "table",
        "title": title,
        "subtitle": "Database record and external (Qdrant) evidence, shown separately.",
        "x": None,
        "series_by": None,
        "series": [],
        "columns": [
            {
                "name": "section", "label": "Source", "unit": "text", "format": None,
                "sensitivity": "internal", "masked": False,
            },
            {
                "name": "field", "label": "Attribute / evidence", "unit": "text",
                "format": None, "sensitivity": "internal", "masked": False,
            },
            {
                "name": "value", "label": "Value", "unit": "text", "format": None,
                "sensitivity": "pii" if db_found else "internal", "masked": False,
            },
        ],
        "rows": rows,
        "summary": summary,
        "drilldown": None,
        "next_steps": [],
        "lineage": {
            "path": "validated_sql",
            "sql": _CUSTOMER_DB_SQL,
            "display_sql": _CUSTOMER_DB_SQL,
            "parameters": {"customer_id": customer_id},
            "source_tables": ["gold.customers", "gold.loan_accounts"],
            "formulas": {},
            "row_count": len(db_rows or []),
            "duration_ms": db_duration_ms,
            "as_of": None,
            "warnings": [],
            "unverified": False,
            "requires_signoff": [],
        },
    }
    return payload, summary, db_found and ext_found, limitation


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


async def run_macro(
    intent: str, *, policy: "SourceAccessPolicy | None" = None,
) -> SourceResult:
    """Retrieve published macro evidence; the native agent owns all prose."""
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


async def run_email(
    intent: str, *, policy: "SourceAccessPolicy | None" = None,
) -> SourceResult:
    """Retrieve mailbox evidence; the native agent owns all prose.

    Reads the ingested email collection through `email_intel`, which carries its own
    embedder and Qdrant client. Mail is the bank's own correspondence, so every hit is
    treated as internal evidence: the card is marked sensitive and the passages are never
    eligible for a public web synthesis.
    """
    _require_external(policy, "email")
    from app.services import email_intel

    # The question as written, plus a data-seeking phrasing with question words stripped.
    # Mail chunks are short, so a single literal question frequently misses a message
    # whose wording differs.
    queries = [intent]
    keywords = " ".join(
        word for word in intent.split() if word.lower() not in _EMAIL_QUERY_STOPWORDS
    )
    if keywords.strip():
        queries.append(keywords.strip())

    try:
        # The embedder and Qdrant client are synchronous; keep them off the event loop so a
        # cold model load cannot freeze every active workbench stream.
        chunks = await asyncio.to_thread(email_intel.search_multi, queries)
    except Exception as exc:  # noqa: BLE001 - external retrieval must degrade per source
        logger.warning("workbench email retrieval failed: %s", exc)
        return SourceResult(
            source="email",
            card_type="error",
            payload={
                "message": "Email intelligence is temporarily unavailable. The mailbox index did not respond.",
                "retryable": True,
            },
            sensitive=True,
        )
    if not chunks:
        return SourceResult(
            source="email",
            card_type="brief",
            payload={"summary": "No mailbox messages matched that question.", "sources": []},
            summary="No email context available.",
            complete=False,
            limitation="No mailbox messages matched the question.",
            sensitive=True,
        )

    sources = _email_source_refs(chunks)
    evidence = _chunk_evidence(chunks)
    messages = len({hit.get("email_id") for hit in chunks if hit.get("email_id")})
    summary = (
        f"Retrieved {len(evidence)} passage{'s' if len(evidence) != 1 else ''} "
        f"from {messages or len(chunks)} mailbox message{'s' if (messages or 1) != 1 else ''}."
    )
    # The card the console renders is richer than the citations the model reads: it carries
    # each cited message's body and its attachment so a citation can open a preview. The
    # lean `sources` above stay as they are — full bodies would bloat the model's evidence.
    card_sources = await asyncio.to_thread(_email_card_sources, chunks)
    return SourceResult(
        source="email",
        card_type="brief",
        payload={"summary": summary, "sources": card_sources},
        summary=summary,
        sources=sources,
        evidence=evidence,
        sensitive=True,
    )


_EMAIL_QUERY_STOPWORDS = {
    "a", "an", "and", "any", "are", "as", "at", "be", "did", "do", "does", "for", "from",
    "has", "have", "how", "i", "in", "is", "it", "me", "my", "of", "on", "or", "our", "please",
    "show", "that", "the", "their", "them", "there", "these", "they", "this", "to", "us",
    "was", "we", "were", "what", "when", "where", "which", "who", "why", "will", "with",
    "you", "your",
}


def _email_source_refs(chunks: list[dict]) -> list[dict]:
    """Cite a message, not a passage, so citations stay readable in an answer."""
    refs: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for chunk in chunks:
        key = (str(chunk.get("email_id") or ""), str(chunk.get("document") or ""))
        if key in seen:
            continue
        seen.add(key)
        received = chunk.get("received_at") or ""
        refs.append({
            "document": chunk.get("document") or "email",
            "subject": chunk.get("subject") or "",
            "sender": chunk.get("sender") or "",
            "date": str(received)[:10],
            "page": None,
            "score": round(float(chunk.get("score", 0.0)), 3),
        })
        if len(refs) >= 6:
            break
    return refs


def _email_card_sources(chunks: list[dict]) -> list[dict]:
    """Per-cited-message view data for the console's attachment/message viewer.

    One row per message, capped like the citations. For each it fetches the full body (an
    attachment hit's own text is the document's contents, not the mail, so the body is read
    separately) and describes the original attachment if there is one. Bodies are read once
    per message, so a message contributing several chunks costs one lookup, not one per
    chunk. Synchronous by design: the caller runs it in a worker thread.
    """
    from app.services import email_files, email_intel

    refs: list[dict] = []
    seen: set[tuple[str, str]] = set()
    body_cache: dict[str, str] = {}
    for chunk in chunks:
        email_id = str(chunk.get("email_id") or "")
        key = (email_id, str(chunk.get("document") or ""))
        if key in seen:
            continue
        seen.add(key)
        if email_id and email_id not in body_cache:
            body_cache[email_id] = email_intel.email_body(email_id)
        received = chunk.get("received_at") or ""
        refs.append({
            "document": chunk.get("document") or "email",
            "subject": chunk.get("subject") or "",
            "sender": chunk.get("sender") or "",
            "date": str(received)[:10],
            "score": round(float(chunk.get("score", 0.0)), 3),
            "body": body_cache.get(email_id, ""),
            "chunk_text": chunk.get("text") or "",
            "attachment": email_files.describe(
                chunk.get("file_path") or "", chunk.get("filename")
            ),
        })
        if len(refs) >= 6:
            break
    return refs


async def run_web(
    intent: str, *, user: str, policy: "SourceAccessPolicy",
    raise_policy_denials: bool = False,
    private_entities: tuple[str, ...] = (),
) -> SourceResult:
    """Retrieve fresh public evidence through Exa without exposing private bank context."""
    _require_external(policy, "web")
    from app.mcp import exa_client
    from app.services.workbench import outbound_policy, web

    try:
        query, web_evidence, _raw_text = await outbound_policy.retrieve_public(
            intent, user=user, policy=policy, private_entities=private_entities,
        )
    except (web.UnsafeWebQuery, outbound_policy.OutboundPolicyDenied) as exc:
        if raise_policy_denials:
            if isinstance(exc, outbound_policy.OutboundPolicyDenied):
                raise
            raise outbound_policy.OutboundPolicyDenied(str(exc)) from exc
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
    intent: str,
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
    from app.services import regulatory_rag
    from app.services import regulatory

    try:
        categories = regulatory.list_categories()
        if not categories:
            return SourceResult(source="regulatory", card_type="error",
                                payload={"message": "No regulatory categories are loaded."})
        chosen = _best_category(intent, categories)
        hits = await asyncio.to_thread(
            regulatory_rag.search, chosen.qdrant_collection, intent, 8,
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


async def run_customer(
    intent: str, *, policy: "SourceAccessPolicy | None" = None,
) -> SourceResult:
    """Answer customer detail questions from the governed database and the externally
    indexed Qdrant store, read-only.

    The database profile and the external passages are rendered as separate sections of one
    table so the origin of every fact is visible. Both accesses are strictly read-only: the
    Qdrant search never mutates, and the database query runs on the `nlq_readonly` pool,
    which re-applies `default_transaction_read_only = on` on every checkout.

    The governed database profile is internal data, so it is returned whenever the `db`
    source is allowed. The external (Qdrant) passages are consent-gated: when external
    source consent is not granted, the card degrades to the database-only section with a
    visible "no external data" note rather than failing the turn.
    """
    if policy is not None:
        policy.require("db")
    external_allowed = policy is None or policy.allows("customer")
    chunks: list[dict] = []
    if external_allowed:
        try:
            # Qdrant and sentence-transformers are synchronous. Keep them off the event
            # loop so a slow remote vector store does not freeze every active workbench
            # stream.
            chunks = await asyncio.to_thread(rag.search_multi, EXTERNAL_CUSTOMER_COLLECTION, [intent])
        except Exception as exc:  # noqa: BLE001 - external retrieval must degrade per source
            logger.warning("workbench customer retrieval failed: %s", exc)
            return SourceResult(
                source="customer",
                card_type="error",
                payload={
                    "message": "Customer intelligence is temporarily unavailable. The vector store did not respond.",
                    "retryable": True,
                },
            )

    customer_id = _extract_customer_id(intent)
    db_rows: list[dict[str, Any]] | None = None
    db_duration_ms = 0
    db_unavailable = False
    if customer_id is not None:
        try:
            db_rows, db_duration_ms = await asyncio.to_thread(_read_customer_rows, customer_id)
        except Exception as exc:  # noqa: BLE001 - the DB must degrade per source, never fail the turn
            logger.warning("workbench customer DB lookup failed for %s: %s", customer_id, exc)
            db_rows = None
            db_unavailable = True

    if not chunks and not db_rows:
        if db_unavailable:
            return SourceResult(
                source="customer",
                card_type="brief",
                payload={
                    "summary": "The governed database record could not be read for this customer.",
                    "sources": [],
                },
                summary="The customer database record could not be read.",
                complete=False,
                limitation="The governed database record could not be read for this customer.",
            )
        return SourceResult(
            source="customer",
            card_type="brief",
            payload={"summary": "No customer sources matched that question.", "sources": []},
            summary="No customer context available.",
            complete=False,
            limitation="No customer sources matched the question.",
        )

    payload, summary, complete, limitation = _customer_card_components(
        customer_id=customer_id or "",
        db_rows=db_rows,
        db_duration_ms=db_duration_ms,
        chunks=chunks,
        db_unavailable=db_unavailable,
    )
    return SourceResult(
        source="customer",
        card_type="chart",
        payload=payload,
        summary=summary,
        sources=_source_refs(chunks),
        evidence=_chunk_evidence(chunks),
        complete=complete,
        limitation=limitation,
        sensitive=bool(db_rows),
    )
