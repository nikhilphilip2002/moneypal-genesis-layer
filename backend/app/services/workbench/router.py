"""Question -> which source(s). The workbench's one routing decision.

A single local-LLM call, constrained by a grammar-JSON schema built from the source
registry, so the model can only pick sources that exist and that the role may see. This is
the same discipline as the NLQ planner: structure the output, and a whole class of
malformed answers becomes impossible rather than merely unlikely.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

from app.services.nlq.catalog.retrieval import retrieve
from app.services.nlq.llm import LLMError
from app.services.nlq.normalization import normalize_lending_question
from app.services.workbench import models
from app.services.workbench.sources import (
    ROUTER_FEW_SHOTS,
    router_system_prompt,
    route_schema,
    visible_sources,
)

logger = logging.getLogger(__name__)

_STRUCTURAL_QUERY = re.compile(
    r"\b(?:schema|database|table|column|relationship|join|erd|diagram|foreign\s+key)\b",
    re.IGNORECASE,
)
_VALUE_CUES = re.compile(
    r"\b(?:our|right\s+now|today|all[ -]?time|how\s+many|how\s+much|total|sum|"
    r"top|bottom|best|worst|rank(?:ed|ing)?|zero|various|different|distinct|available|"
    r"list|show|split|composition|amount\s+paid|customer\s*(?:id|number|no\.?|#)|"
    r"loan\s+accounts?|repayment\s+history|payment\s+history|"
    r"agents?\s+(?:name|details?|profile)|details?\s+(?:of|for)\s+(?:agnt|agent)\s*\d+|"
    r"what\s+(?:are|is)\s+(?:the\s+)?branches|branches?\s+(?:are|is)\s+there|"
    r"collected|outstanding|sanction(?:ed)?|disburs(?:ed|ement)|"
    r"share\s+capital|capital\s+share|equity\s+shares?|capital\s+reserves?|"
    r"reserves?\s+(?:and\s+)?surplus|reserve\s+shares?\w*|product\s+code|"
    r"by\s+(?:product|scheme|branch|status)|"
    r"based\s+on\s+(?:product|scheme|branch))\b",
    re.IGNORECASE,
)
_DESCRIPTIVE_CUES = re.compile(
    r"^\s*(?:what\s+(?:is|does|are)|explain|describe|define|how\s+is|how\s+does|"
    r"what\s+is\s+the\s+difference|difference\s+between|meaning\s+of)\b",
    re.IGNORECASE,
)

_HYBRID_SOURCE_CUES: dict[str, re.Pattern[str]] = {
    "competitive": re.compile(
        r"\b(?:competitor|competitive|peer|nbfc|microfinance|fintech|co[ -]?lending|"
        r"market offering|industry inclusion|turnaround|\bbenchmark)\b", re.IGNORECASE,
    ),
    "regulatory": re.compile(
        r"\b(?:regulat|prudential|priority sector|psl|cgtmse|exposure limit|guideline)\b",
        re.IGNORECASE,
    ),
    "macro": re.compile(
        r"\b(?:macro|inflation|repo|gsdp|gdp|national|economic|industrial growth|"
        r"gold price|seasonal|credit conditions|state[ -]?wide)\b", re.IGNORECASE,
    ),
}
_INTERNAL_BOOK_CUES = re.compile(
    r"\b(?:our|loan\s+book|portfolio|loans?|borrowers?|customers?|agents?|branches?|"
    r"disburs\w*|sanction\w*|repay\w*|collection\w*|outstanding|delinquen\w*|"
    r"scheme|product|share\s+capital|capital\s+share|equity\s+shares?|"
    r"capital\s+reserves?|reserves?\s+(?:and\s+)?surplus|reserve\s+shares?\w*)\b",
    re.IGNORECASE,
)


def _external_only_source(question: str, visible_ids: list[str]) -> str | None:
    """Identify a plainly external fact when no internal-book comparison is requested."""
    if _INTERNAL_BOOK_CUES.search(question):
        return None
    for source_id in ("macro", "competitive", "regulatory"):
        cue = _HYBRID_SOURCE_CUES[source_id]
        if source_id in visible_ids and cue.search(question):
            return source_id
    return None


def _asks_for_loan_book_values(question: str) -> bool:
    return not _STRUCTURAL_QUERY.search(question) and bool(_VALUE_CUES.search(question))


def _matches_loan_book_catalog(question: str) -> bool:
    """Return whether curated Gold metadata substantively matches the question.

    This lexical-only guard is deliberately local and cheap. It prevents a routing model
    from claiming that a catalogued subject does not exist while leaving the NLQ planner
    responsible for deciding whether and how it can be queried.
    """
    result = retrieve(question, use_vectors=False)
    return any(
        hit.lexical >= 1.0 and hit.doc.kind in {"table", "metric", "dimension"}
        for hit in result.hits
    )


def _db_subquestion(question: str) -> str:
    """Best-effort internal task when an older router omits source-specific intents."""
    lowered = question.lower()
    patterns = (
        (("msme portfolio", "msme book"), "Show our MSME portfolio size and monthly growth."),
        (("par 30",), "What is our current PAR 30?"),
        (("interest rate", "loan rates"), "Show loan count and outstanding by interest rate."),
        (("collection efficiency",), "Show our collection efficiency by product and branch."),
        (("gold loan",), "Show monthly gold-loan disbursement trend."),
        (("branch-level disbursement", "branch level disbursement"), "Show disbursement by branch."),
        (("ticket size",), "What is our average sanctioned loan amount by product?"),
        (("repayment schedule",), "Show monthly scheduled, due, and repaid amounts."),
        (("delinquency", "sidbi"), "Show MSME delinquency and PAR 30 by scheme."),
        (("liquidity", "vintage"), "Show repayment vintage, outstanding, PAR and NPA trends."),
        (("scheme-wise concentration", "scheme wise concentration"), "Show portfolio outstanding and share by scheme."),
        (("sanction-to-disbursement", "sanction to disbursement"), "Show total sanctioned amount, disbursed amount, and their conversion ratio."),
        (("floating-rate", "floating rate"), "Show loan count and outstanding by contractual interest rate."),
        (("gender diversity",), "Show borrower count and share by gender."),
        (("top 10 borrower",), "Show top 10 borrowers by principal outstanding and their share of the portfolio."),
        (("dpd bucket migration",), "Show monthly loan count and outstanding by DPD bucket."),
        (("business loan disbursement",), "Show monthly business and MSME loan disbursement trend."),
        (("retail loan collection",), "Show collection efficiency by retail loan product."),
        (("portfolio risk profile",), "Show current PAR 30, NPA ratio, DPD buckets, and principal outstanding."),
        (("branch expansion",), "Show branch status, opening date, loan count, disbursement, and outstanding for the named locations."),
    )
    for cues, task in patterns:
        if any(cue in lowered for cue in cues):
            return task
    # Removing the external half is safer than sending a comparison request to a source
    # that is intentionally unaware of market/regulatory data.
    internal = re.split(r"\b(?:compare[sd]?\s+(?:with|against)|against|benchmark(?:ed)?\s+against|align(?:s|ed)?\s+with)\b", question, maxsplit=1, flags=re.IGNORECASE)[0]
    return internal.strip(" ,.?-") or question


@dataclass(slots=True)
class RouteDecision:
    route: str  # "dispatch" | "refuse"
    sources: list[str] = field(default_factory=list)
    intent: str = ""
    reason: str = ""
    message: str = ""
    model: str = ""
    # A multi-source question is not itself a valid question for every source. For
    # example, the loan-book planner should receive "our collection efficiency", not
    # "compare our collection efficiency with regional peers". The router may provide
    # one focused task per source; handlers fall back to `intent` when it does not.
    source_intents: dict[str, str] = field(default_factory=dict)


def _fallback(role: str, question: str) -> RouteDecision:
    """When routing itself fails, default to the loan book if the role can see it.

    A degraded router should still answer the common case rather than refuse everything.
    `db` is the modal source; if the role cannot see it, fall to the first visible one.
    """
    visible = visible_sources(role)
    if not visible:
        return RouteDecision(route="refuse", reason="out_of_scope",
                             message="No sources are available for your role.")
    visible_ids = [source.id for source in visible]
    chosen: list[str] = []
    if "db" in visible_ids and (
        _asks_for_loan_book_values(question) or _matches_loan_book_catalog(question)
    ):
        chosen.append("db")
    for source_id, cue in _HYBRID_SOURCE_CUES.items():
        if source_id in visible_ids and cue.search(question) and source_id not in chosen:
            chosen.append(source_id)
    if not chosen:
        chosen = ["db" if "db" in visible_ids else visible_ids[0]]
    source_intents: dict[str, str] = {}
    if len(chosen) > 1:
        if "db" in chosen:
            source_intents["db"] = _db_subquestion(question)
        source_intents.update({source: question for source in chosen if source != "db"})
    return RouteDecision(
        route="dispatch", sources=chosen, intent=question,
        source_intents=source_intents, model="fallback",
    )


async def route(
    question: str,
    *,
    role: str,
    pinned: str | None = None,
    history_messages: list[dict[str, str]] | None = None,
) -> RouteDecision:
    """Decide which source(s) answer this question.

    A `pinned` source the role may see is a deterministic override — the user has chosen the
    source, so there is nothing to route and the model is not called. A pin the role cannot
    see (or an unknown one) is dropped, and normal routing runs: pinning must never widen
    access beyond what the role already has.
    """
    normalized = normalize_lending_question(question)

    if pinned:
        visible_ids = [s.id for s in visible_sources(role)]
        if pinned in visible_ids:
            return RouteDecision(
                route="dispatch", sources=[pinned], intent=normalized, model="pinned"
            )

    client = models.for_step("route", sensitive=True)
    messages = [{"role": "system", "content": router_system_prompt(role)}]
    for user_text, assistant_json in ROUTER_FEW_SHOTS:
        messages.append({"role": "user", "content": user_text})
        messages.append({"role": "assistant", "content": assistant_json})
    messages.extend(history_messages or [])
    messages.append({"role": "user", "content": normalized})

    try:
        result = await client.complete(
            messages=messages,
            json_schema=route_schema(role),
            max_tokens=300,
            temperature=0.0,
        )
        payload = result.json()
    except (LLMError, ValueError) as exc:
        logger.warning("workbench router failed, falling back: %s", exc)
        return _fallback(role, normalized)

    if not isinstance(payload, dict):
        return _fallback(role, normalized)

    visible_ids = [s.id for s in visible_sources(role)]
    external_only = _external_only_source(normalized, visible_ids)
    catalog_match = "db" in visible_ids and _matches_loan_book_catalog(normalized)
    value_intent = (
        external_only is None
        and catalog_match
        and _asks_for_loan_book_values(normalized)
    )
    route_value = payload.get("route")
    if route_value == "refuse":
        if external_only is not None:
            return RouteDecision(
                route="dispatch", sources=[external_only], intent=normalized,
                model="catalog",
            )
        if catalog_match:
            source = "db" if value_intent or "knowledge" not in visible_ids else "knowledge"
            return RouteDecision(
                route="dispatch", sources=[source], intent=normalized, model="catalog"
            )
        return RouteDecision(
            route="refuse",
            reason=str(payload.get("reason", "out_of_scope")),
            message=str(payload.get("message", "")),
            model=result.model,
        )

    # dispatch — keep only known, role-visible source ids, in a stable order.
    chosen = [s for s in payload.get("sources", []) if s in visible_ids]
    # De-duplicate while preserving order.
    seen: set[str] = set()
    chosen = [s for s in chosen if not (s in seen or seen.add(s))]
    if external_only is not None:
        chosen = [external_only]
    # Deterministic coverage guard for hybrid questions. The model remains responsible for
    # normal routing, but a missed external half must not turn a comparison into a DB-only
    # judgement or refusal.
    if "db" in chosen or value_intent:
        for source_id, cue in _HYBRID_SOURCE_CUES.items():
            if source_id in visible_ids and cue.search(normalized) and source_id not in chosen:
                chosen.append(source_id)
    if value_intent:
        chosen = [source for source in chosen if source != "knowledge"]
    elif (
        catalog_match
        and _DESCRIPTIVE_CUES.search(normalized)
        and chosen == ["db"]
        and "knowledge" in visible_ids
    ):
        chosen = ["knowledge"]
    if value_intent and "db" not in chosen:
        chosen.insert(0, "db")
    if not chosen:
        return _fallback(role, normalized)

    raw_source_intents = payload.get("source_intents") or {}
    if not isinstance(raw_source_intents, dict):
        raw_source_intents = {}
    source_intents = {
        source: str(value).strip()
        for source, value in raw_source_intents.items()
        if source in chosen and isinstance(value, str) and value.strip()
    }
    if len(chosen) > 1:
        source_intents.setdefault("db", _db_subquestion(normalized))
        for source in chosen:
            source_intents.setdefault(source, normalized)

    return RouteDecision(
        route="dispatch",
        sources=chosen,
        intent=str(payload.get("intent", normalized)) or normalized,
        source_intents=source_intents,
        model=result.model,
    )
