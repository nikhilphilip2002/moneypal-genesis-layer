"""Question -> which source(s). The workbench's one routing decision.

A single local-LLM call, constrained by a grammar-JSON schema built from the source
registry, so the model can only pick sources that exist and that the role may see. This is
the same discipline as the NLQ planner: structure the output, and a whole class of
malformed answers becomes impossible rather than merely unlikely.
"""

from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from app.core.config import settings
from app.services.nlq.catalog.retrieval import retrieve
from app.services.nlq.llm import LLMError
from app.services.nlq.normalization import normalize_lending_question
from app.services.workbench import models, prompts
from app.services.workbench.sources import (
    route_schema,
    visible_sources,
)

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from app.services.workbench.access import SourceAccessPolicy

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
_STRUCTURAL_FOLLOWUP_CUE = re.compile(
    r"^\s*(?:and\s+|now\s+|also\s+|what\s+about\s+|how\s+about\s+)?"
    r"(?:by\s+|for\s+|in\s+|over\s+|with\s+|without\s+|top\s+|bottom\s+)",
    re.IGNORECASE,
)

_HYBRID_SOURCE_CUES: dict[str, re.Pattern[str]] = {
    "competitive": re.compile(
        r"\b(?:competitor|competitive|compet(?:e|es|ing)|rival|peer|nbfc|microfinance|fintech|co[ -]?lending|"
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

_WEB_FRESHNESS_CUES = re.compile(
    r"\b(?:latest|today|current|currently|recent|newly published|up[ -]?to[ -]?date|"
    r"real[ -]?time|right now|breaking|news|announcement|this week|this month)\b",
    re.IGNORECASE,
)
_WEB_PUBLIC_CUES = re.compile(
    r"\b(?:RBI|MoSPI|government|ministry|PIB|India Budget|Economic Survey|IMF|"
    r"World Bank|OECD|United Nations|market|industry|economy|economic|inflation|"
    r"GDP|GVA|CPI|IIP|repo|policy rate|fiscal|trade|exports?|imports?|FDI|scheme|"
    r"legislation|competitor|NBFC|MSME)\b",
    re.IGNORECASE,
)
_EXPLICIT_WEB_CUES = re.compile(
    r"\b(?:search|look up|find|check)\s+(?:the\s+)?(?:web|internet|online)\b|"
    r"\b(?:on the web|on the internet|online sources?)\b",
    re.IGNORECASE,
)
_DESTRUCTIVE_CUES = re.compile(
    r"\b(?:drop|truncate|delete|update|insert|alter|grant|revoke)\b.{0,30}\b(?:table|database|rows?|records?)\b",
    re.IGNORECASE,
)


def _requires_web(question: str, visible_ids: list[str]) -> bool:
    if "web" not in visible_ids:
        return False
    return bool(
        _EXPLICIT_WEB_CUES.search(question)
        or (_WEB_FRESHNESS_CUES.search(question) and _WEB_PUBLIC_CUES.search(question))
    )


def _external_only_source(question: str, visible_ids: list[str]) -> str | None:
    """Identify a plainly external fact when no internal-book comparison is requested."""
    if _INTERNAL_BOOK_CUES.search(question):
        return None
    if _requires_web(question, visible_ids):
        return "web"
    for source_id in ("macro", "competitive", "regulatory"):
        cue = _HYBRID_SOURCE_CUES[source_id]
        if source_id in visible_ids and cue.search(question):
            return source_id
    return None


def _is_record_lookup(question: str) -> bool:
    """Whether the governed record-lookup grammar already owns this question.

    A question the NLQ module can answer deterministically from Gold is a loan-book value
    question by definition, whatever words it uses. Deferring to that grammar keeps a terse
    phrasing ("agent 45 phone number") out of the concepts source, which can only describe
    what a phone number is.
    """
    from app.services.nlq import lookup

    return lookup.detect(question) is not None


def _asks_for_loan_book_values(question: str) -> bool:
    if _STRUCTURAL_QUERY.search(question):
        return False
    return bool(_VALUE_CUES.search(question)) or _is_record_lookup(question)


def _resolve_db_structural_followup(
    question: str, history_messages: list[dict[str, str]],
) -> str | None:
    """Bind an unmistakable refinement to a previous loan-book question."""
    if not history_messages or not _STRUCTURAL_FOLLOWUP_CUE.search(question):
        return None
    previous = next(
        (
            str(message.get("content", "")).strip()
            for message in reversed(history_messages)
            if message.get("role") == "user" and str(message.get("content", "")).strip()
        ),
        "",
    )
    if not previous or not (
        _asks_for_loan_book_values(previous) or _matches_loan_book_catalog(previous)
    ):
        return None
    suffix = re.sub(
        r"^\s*(?:and|now|also|what\s+about|how\s+about)\s+",
        "", question, count=1, flags=re.IGNORECASE,
    ).strip()
    return f"{previous.rstrip(' ?.')} {suffix}".strip()


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
    limitations: list[dict[str, str]] = field(default_factory=list)
    policy_version: str = ""
    confidence: float = 0.0
    fallback_used: bool = False
    ambiguity_class: str = ""
    effective_sources: tuple[str, ...] = ()


def _deterministic_route(
    question: str, *, visible_ids: list[str], policy_version: str,
) -> RouteDecision | None:
    """Select only high-confidence lexical/catalog routes; return None when ambiguous."""
    common = {"policy_version": policy_version, "effective_sources": tuple(visible_ids)}
    if _DESTRUCTIVE_CUES.search(question):
        return RouteDecision(
            route="refuse", reason="unsafe_operation",
            message="The Workbench is read-only and cannot modify or delete data.",
            model="deterministic", confidence=1.0, **common,
        )
    if "schema" in visible_ids and _STRUCTURAL_QUERY.search(question):
        return RouteDecision(
            route="dispatch", sources=["schema"], intent=question,
            reason="explicit_schema_cue", model="deterministic", confidence=0.99, **common,
        )
    if _requires_web(question, visible_ids):
        from app.services.workbench.web import public_query

        try:
            public_intent = public_query(question)
        except ValueError:
            return RouteDecision(
                route="refuse", reason="private_external_query",
                message="Private bank or customer details cannot be sent to web search.",
                model="deterministic", confidence=1.0, **common,
            )
        if "db" in visible_ids and _INTERNAL_BOOK_CUES.search(question):
            return RouteDecision(
                route="dispatch", sources=["db", "web"], intent=question,
                source_intents={"db": _db_subquestion(question), "web": public_intent},
                reason="fresh_public_comparison", model="deterministic", confidence=0.97,
                **common,
            )
        return RouteDecision(
            route="dispatch", sources=["web"], intent=question,
            source_intents={"web": public_intent}, reason="fresh_or_explicit_web",
            model="deterministic", confidence=0.99, **common,
        )

    external = [
        source_id for source_id, cue in _HYBRID_SOURCE_CUES.items()
        if source_id in visible_ids and cue.search(question)
    ]
    db_match = "db" in visible_ids and (
        _asks_for_loan_book_values(question) or _matches_loan_book_catalog(question)
    )
    internal = bool(
        _asks_for_loan_book_values(question)
        or re.search(r"\b(?:our|loan\s+book|portfolio)\b", question, re.IGNORECASE)
    )
    if external:
        chosen = (["db"] if internal and "db" in visible_ids else []) + external
        intents = {source: question for source in chosen}
        if "db" in chosen:
            intents["db"] = _db_subquestion(question)
        return RouteDecision(
            route="dispatch", sources=chosen, intent=question, source_intents=intents,
            reason="external_semantic_cue" if len(chosen) == 1 else "explicit_comparison",
            model="deterministic", confidence=0.96, **common,
        )
    if db_match:
        descriptive = bool(_DESCRIPTIVE_CUES.search(question)) and not _asks_for_loan_book_values(question)
        source = "knowledge" if descriptive and "knowledge" in visible_ids else "db"
        return RouteDecision(
            route="dispatch", sources=[source], intent=question,
            reason="catalog_definition" if source == "knowledge" else "governed_db_catalog",
            model="deterministic", confidence=0.98, **common,
        )
    if "knowledge" in visible_ids and _DESCRIPTIVE_CUES.search(question):
        return RouteDecision(
            route="dispatch", sources=["knowledge"], intent=question,
            reason="stable_definition", model="deterministic", confidence=0.9, **common,
        )
    return None


def _fallback(
    role: str, question: str,
    allowed_source_ids: tuple[str, ...] | list[str] | set[str] | None = None,
) -> RouteDecision:
    """When routing itself fails, default to the loan book if the role can see it.

    A degraded router should still answer the common case rather than refuse everything.
    `db` is the modal source; if the role cannot see it, fall to the first visible one.
    """
    visible = visible_sources(role, allowed_source_ids)
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
    if _requires_web(question, visible_ids):
        if not _INTERNAL_BOOK_CUES.search(question):
            chosen = ["web"]
        elif "db" in chosen:
            chosen = [source for source in chosen if source not in {"macro", "competitive", "regulatory"}]
            chosen.append("web")
        else:
            chosen = ["web"]
    if not chosen:
        return RouteDecision(
            route="refuse", reason="clarification_required",
            message="Please clarify whether you want loan-book data, a definition, or external evidence.",
            model="fallback", confidence=0.0, fallback_used=True,
            ambiguity_class="no_high_confidence_cue",
            effective_sources=tuple(visible_ids),
        )
    source_intents: dict[str, str] = {}
    if len(chosen) > 1:
        if "db" in chosen:
            source_intents["db"] = _db_subquestion(question)
        source_intents.update({source: question for source in chosen if source != "db"})
        if "web" in chosen:
            from app.services.workbench.web import public_query
            try:
                source_intents["web"] = public_query(question)
            except ValueError:
                chosen = [source for source in chosen if source != "web"]
                source_intents.pop("web", None)
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
    policy: "SourceAccessPolicy | None" = None,
) -> RouteDecision:
    """Decide which source(s) answer this question.

    A `pinned` source the role may see is a deterministic override — the user has chosen the
    source, so there is nothing to route and the model is not called. A pin the role cannot
    see (or an unknown one) is dropped, and normal routing runs: pinning must never widen
    access beyond what the role already has.
    """
    # A bare record refinement ("along with names") names no source of its own. Routing on
    # the question it refines keeps the follow-up with the loan book instead of handing a
    # fragment to a model that will guess.
    from app.services.nlq import lookup

    db_followup = _resolve_db_structural_followup(question, history_messages or [])
    resolved = db_followup or lookup.resolve_followup(question, history_messages or [])
    normalized = normalize_lending_question(resolved)
    structural_followup = db_followup is not None or (
        bool(history_messages) and resolved.strip() != question.strip()
    )

    if policy is None:
        from app.services.workbench.access import build_policy

        # Direct callers retain legacy behavior. The HTTP/graph entry point always passes
        # an explicit immutable policy whose request default is external access off.
        policy = build_policy(role=role, external_sources_enabled=True)
    allowed_source_ids = policy.effective_sources

    from app.services.workbench.access import SOURCE_GROUPS, is_external

    # The governed lookup grammar and structurally resolved DB follow-ups already identify
    # both source and intent. Sending them to a model can only add latency or lose an exact
    # identifier, so bind them to the loan book before model routing.
    if "db" in allowed_source_ids and (
        _is_record_lookup(normalized)
        or (
            structural_followup
            and (_asks_for_loan_book_values(normalized) or _matches_loan_book_catalog(normalized))
        )
    ):
        return RouteDecision(
            route="dispatch",
            sources=["db"],
            intent=normalized,
            source_intents={"db": normalized} if structural_followup else {},
            model="catalog",
            policy_version=policy.version,
            confidence=1.0,
            effective_sources=tuple(allowed_source_ids),
        )

    if pinned and pinned in SOURCE_GROUPS and is_external(pinned) and not policy.allows(pinned):
        consent_missing = not policy.external_sources_enabled
        return RouteDecision(
            route="refuse",
            reason="external_consent_required" if consent_missing else "source_unavailable",
            message=(
                "Enable “Use external sources” to access macro, competitive, regulatory, "
                "or live web information."
                if consent_missing
                else "That external source is not available for your role or this deployment."
            ),
            model="policy",
            policy_version=policy.version,
            confidence=1.0,
            effective_sources=tuple(allowed_source_ids),
        )

    requested_external: list[str] = []
    if _requires_web(normalized, ["web"]):
        requested_external.append("web")
    else:
        for source_id, cue in _HYBRID_SOURCE_CUES.items():
            if cue.search(normalized):
                requested_external.append(source_id)
    blocked_external = [
        source_id for source_id in requested_external
        if is_external(source_id) and not policy.allows(source_id)
    ]
    if blocked_external:
        consent_missing = not policy.external_sources_enabled
        internal_part = (
            "db" in allowed_source_ids
            and (
                _asks_for_loan_book_values(normalized)
                or re.search(r"\b(?:our|loan\s+book|portfolio)\b", normalized, re.IGNORECASE)
            )
        )
        if internal_part:
            return RouteDecision(
                route="dispatch",
                sources=["db"],
                intent=normalized,
                source_intents={"db": _db_subquestion(normalized)},
                limitations=[{
                    "source": ",".join(blocked_external),
                    "reason": (
                        "External sources are off, so this answer includes only the supported "
                        "loan-book portion."
                        if consent_missing
                        else "The requested external source is unavailable, so this answer "
                        "includes only the supported loan-book portion."
                    ),
                }],
                model="policy",
                policy_version=policy.version,
                confidence=1.0,
                effective_sources=tuple(allowed_source_ids),
            )
        return RouteDecision(
            route="refuse",
            reason="external_consent_required" if consent_missing else "source_unavailable",
            message=(
                "Enable “Use external sources” to access macro, competitive, regulatory, "
                "or live web information."
                if consent_missing
                else "The requested external source is not available for your role or this deployment."
            ),
            model="policy",
            policy_version=policy.version,
            confidence=1.0,
            effective_sources=tuple(allowed_source_ids),
        )

    if pinned:
        visible_ids = [s.id for s in visible_sources(role, allowed_source_ids)]
        if pinned in visible_ids:
            return RouteDecision(
                route="dispatch", sources=[pinned], intent=normalized, model="pinned",
                reason="authorized_pin", policy_version=policy.version, confidence=1.0,
                effective_sources=tuple(allowed_source_ids),
            )
        return RouteDecision(
            route="refuse", reason="source_unavailable",
            message="That pinned source is unknown or unavailable for your role.",
            model="policy", policy_version=policy.version, confidence=1.0,
            effective_sources=tuple(allowed_source_ids),
        )

    if settings.workbench_deterministic_routing:
        deterministic = _deterministic_route(
            normalized,
            visible_ids=[s.id for s in visible_sources(role, allowed_source_ids)],
            policy_version=policy.version,
        )
        if deterministic is not None:
            return deterministic

    client = models.for_step("route", sensitive=True)
    prompt = prompts.build_router_prompt(
        role=role, question=normalized, history_messages=history_messages,
        allowed_source_ids=allowed_source_ids,
    )

    try:
        async with asyncio.timeout(settings.workbench_router_timeout_s):
            result = await client.complete(
                messages=prompt.messages,
                json_schema=route_schema(role, allowed_source_ids),
                timeout_s=settings.workbench_router_timeout_s,
                call_purpose="route",
                prompt_version=prompt.version,
                prefix_hash=prompt.prefix_hash,
                max_output_tokens=300,
            )
        payload = result.json()
        from app.core.logging import log_parsed_output

        log_parsed_output(
            "Workbench router response parsed",
            event="router_decision",
            schema_name="workbench_route_schema",
            parsed=payload,
            duration_ms=getattr(result, "duration_ms", 0.0),
            status="success",
        )
    except (LLMError, TimeoutError, ValueError) as exc:
        logger.warning("workbench router failed, falling back: %s", exc)
        from app.core.logging import log_parsed_output

        log_parsed_output(
            f"Workbench router parse failed: {exc}",
            event="router_decision",
            schema_name="workbench_route_schema",
            status="fallback",
            error=str(exc),
        )
        decision = _fallback(role, normalized, allowed_source_ids)
        decision.policy_version = policy.version
        decision.fallback_used = True
        decision.ambiguity_class = "router_failure"
        decision.effective_sources = tuple(allowed_source_ids)
        return decision

    if not isinstance(payload, dict):
        decision = _fallback(role, normalized, allowed_source_ids)
        decision.policy_version = policy.version
        decision.fallback_used = True
        decision.ambiguity_class = "malformed_router_output"
        decision.effective_sources = tuple(allowed_source_ids)
        return decision

    visible_ids = [s.id for s in visible_sources(role, allowed_source_ids)]
    external_only = _external_only_source(normalized, visible_ids)
    web_required = _requires_web(normalized, visible_ids)
    # The record grammar is itself curated Gold metadata, so a question it recognises is a
    # catalog match whether or not the lexical retriever scores one.
    catalog_match = "db" in visible_ids and (
        _is_record_lookup(normalized) or _matches_loan_book_catalog(normalized)
    )
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
                model="catalog", policy_version=policy.version, confidence=1.0,
                fallback_used=True, ambiguity_class="model_false_refusal",
                effective_sources=tuple(allowed_source_ids),
            )
        if catalog_match:
            source = "db" if value_intent or "knowledge" not in visible_ids else "knowledge"
            return RouteDecision(
                route="dispatch", sources=[source], intent=normalized, model="catalog",
                policy_version=policy.version, confidence=1.0, fallback_used=True,
                ambiguity_class="model_false_refusal", effective_sources=tuple(allowed_source_ids),
            )
        return RouteDecision(
            route="refuse",
            reason=str(payload.get("reason", "out_of_scope")),
            message=str(payload.get("message", "")),
            model=result.model,
            policy_version=policy.version,
            confidence=0.6,
            fallback_used=True,
            ambiguity_class="model_refusal",
            effective_sources=tuple(allowed_source_ids),
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
    if web_required:
        if value_intent or ("db" in chosen and _INTERNAL_BOOK_CUES.search(normalized)):
            chosen = [source for source in chosen if source not in {"macro", "competitive", "regulatory", "web"}]
            chosen.append("web")
        else:
            chosen = ["web"]
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
        decision = _fallback(role, normalized, allowed_source_ids)
        decision.policy_version = policy.version
        return decision

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
    if "web" in chosen:
        from app.services.workbench.web import public_query
        try:
            source_intents["web"] = public_query(
                source_intents.get("web") or normalized
            )
        except ValueError:
            chosen = [source for source in chosen if source != "web"]
            source_intents.pop("web", None)
            if not chosen:
                decision = _fallback(role, normalized, allowed_source_ids)
                decision.policy_version = policy.version
                return decision

    return RouteDecision(
        route="dispatch",
        sources=chosen,
        intent=str(payload.get("intent", normalized)) or normalized,
        source_intents=source_intents,
        model=result.model,
        policy_version=policy.version,
        confidence=0.7,
        fallback_used=True,
        ambiguity_class="lexical_ambiguity",
        effective_sources=tuple(allowed_source_ids),
    )
