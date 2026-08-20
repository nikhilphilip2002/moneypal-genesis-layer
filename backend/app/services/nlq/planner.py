"""Question -> PlanResult. The one place an LLM decides anything.

Routing policy (§2.4):
  queryspec, confidence >= 0.6, validates against the catalog -> compile and execute
  queryspec that fails validation                             -> one repair round-trip,
                                                                 then demote to `sql`
  sql                                                         -> text-to-SQL (Phase 3)
  clarify / refuse                                            -> return, execute nothing

The confidence floor matters more than it looks. A model that is unsure has usually picked
a plausible neighbouring metric — collection efficiency instead of amount collected — and
that produces a confident, wrong, entirely credible number. Below the floor we ask.
"""

from __future__ import annotations

import calendar
import logging
import re
from dataclasses import dataclass, replace
from datetime import date
from typing import Any

from pydantic import TypeAdapter, ValidationError

from app.services.nlq import cache
from app.services.nlq.catalog import Catalog, get_catalog
from app.services.nlq.catalog.retrieval import retrieve
from app.services.nlq.compiler import CompileError, compile_spec
from app.services.nlq.contracts import (
    AnalysisPlan,
    BriefingPlan,
    ClarifyPlan,
    PlanResult,
    Period,
    QuerySpecPlan,
    RefusalPlan,
    SqlPlan,
    WorklistPlan,
)
from app.services.nlq.llm import LLMError, get_llm_client
from app.services.nlq.llm.prompts import PROMPT_VERSION, build_messages
from app.services.nlq.llm.schemas import plan_schema
from app.services.nlq.normalization import normalize_lending_question
from app.services.nlq.text_to_sql import (
    named_borrower_disbursed_name,
    named_borrower_principal_name,
)

logger = logging.getLogger(__name__)

CONFIDENCE_FLOOR = 0.6
_plan_adapter = TypeAdapter(PlanResult)

_BORROWER_COUNT_RE = re.compile(
    r"\b(?:how\s+many\s+(?:borrowers?|customers?|clients?)|"
    r"(?:borrower|customer|client)\s+count|count\s+of\s+(?:borrowers?|customers?|clients?))\b",
    re.IGNORECASE,
)
_AGENT_CODE_RE = re.compile(
    r"\b(?:agent|agnt)\s*[-:# ]*(?P<code>[a-z0-9_-]+)\b", re.IGNORECASE
)
_MONTHS = {
    name.lower(): number
    for number, name in enumerate(calendar.month_name)
    if name
}
_DISBURSEMENT_RE = re.compile(r"\bdisburse(?:ment|ments|d)?\b", re.IGNORECASE)
_NAMED_MONTH_RE = re.compile(
    r"\b(?P<month>" + "|".join(_MONTHS) + r")\s+(?P<year>20\d{2})\b",
    re.IGNORECASE,
)
_MONTHLY_RE = re.compile(r"\b(?:monthly|each\s+month|by\s+month)\b", re.IGNORECASE)
_BY_BRANCH_RE = re.compile(r"\bby\s+branch\b", re.IGNORECASE)
_BY_SCHEME_RE = re.compile(r"\b(?:by\s+scheme|rank(?:ing)?\s+schemes?)\b", re.IGNORECASE)
_COMPARE_RE = re.compile(r"\b(?:compare|versus|vs\.?|compared\s+(?:with|to))\b", re.IGNORECASE)
_DISTINCT_BORROWERS_RE = re.compile(
    r"\b(?:distinct|unique)\s+(?:borrowers?|customers?|clients?)\b", re.IGNORECASE
)
_LOAN_RECEIPT_RE = re.compile(
    r"\b(?:received|got|were\s+sanctioned|were\s+given)\s+loans?\b|"
    r"\bloans?\s+(?:received|sanctioned)\b",
    re.IGNORECASE,
)
_TOP_BORROWERS_RE = re.compile(
    r"\btop(?:\s+(?P<limit>\d{1,4}))?\s+(?:borrowers?|customers?|clients?)\b",
    re.IGNORECASE,
)
_TOP_AGENTS_RE = re.compile(
    r"\btop(?:\s+(?P<limit>\d{1,4}))?\s+agents?\b|"
    r"\bwhich\s+agents?\s+(?:have|has)\s+(?:the\s+)?most\s+"
    r"(?:linked\s+)?(?:borrowers?|customers?|loans?)\b|"
    r"\bagents?\s+(?:with|having)\s+(?:the\s+)?most\s+"
    r"(?:linked\s+)?(?:borrowers?|customers?|loans?)\b",
    re.IGNORECASE,
)
_AGENT_DIRECTORY_RE = re.compile(
    r"\b(?:agent\s+(?:details?|directory|profiles?|names?)|"
    r"(?:list|show)\s+(?:all\s+)?agents?)\b|"
    r"\bagents?\b[^?]{0,100}\b(?:names?|designations?|branch(?:es|\s+codes?)?|"
    r"mobiles?|phones?|emails?|role(?:s|\s+codes?)?|joined|linked\s+(?:loan|customer|borrower))\b",
    re.IGNORECASE,
)
_BY_PRODUCT_RE = re.compile(r"\bby\s+(?:loan\s+)?product\b", re.IGNORECASE)
_OPEN_CLOSED_RE = re.compile(
    r"\b(?:open\s+(?:and|or|vs\.?|versus)\s+closed|"
    r"closed\s+(?:and|or|vs\.?|versus)\s+open)\b",
    re.IGNORECASE,
)
_INTEREST_RATE_RE = re.compile(r"\binterest\s+rates?\b", re.IGNORECASE)
_INTEREST_RATE_AMOUNT_RE = re.compile(
    r"\b(?:total|sum(?:med)?)\b[^?]{0,40}\binterest\s+rate\b|"
    r"\binterest\s+rate\s+(?:amount|total)\b",
    re.IGNORECASE,
)
_VARIOUS_INTEREST_RATES_RE = re.compile(
    r"\b(?:various|different|distinct|available|list|range\s+of)\b[^?]{0,40}"
    r"\binterest\s+rates?\b|\bwhat\s+(?:are|is)\b[^?]{0,30}\binterest\s+rates?\b",
    re.IGNORECASE,
)
_INTEREST_BY_SCHEME_RE = re.compile(
    r"\binterest\s+rates?\b[^?]{0,50}\b(?:by|based\s+on|for\s+each)\s+(?:scheme|scheme\s+name)\b|"
    r"\b(?:by|based\s+on)\s+(?:scheme|scheme\s+name)\b[^?]{0,50}\binterest\s+rates?\b",
    re.IGNORECASE,
)
_SCHEME_AMOUNT_PAID_RE = re.compile(
    r"\b(?:scheme|scheme\s+name)\b[^?]{0,60}\b(?:amount\s+paid|paid\s+amount|"
    r"collections?|repayments?)\b|"
    r"\b(?:amount\s+paid|paid\s+amount|collections?|repayments?)\b[^?]{0,60}"
    r"\b(?:by|per|for\s+each)\s+(?:scheme|scheme\s+name)\b",
    re.IGNORECASE,
)
_TOTAL_SANCTIONED_RE = re.compile(
    r"\b(?:total|overall)\b[^?]{0,50}\b(?:loan\s+)?(?:amount\s+)?sanction(?:ed)?\b|"
    r"\btotal\s+sanctioned\s+(?:loan\s+)?amount\b",
    re.IGNORECASE,
)
_VINTAGE_PERFORMANCE_RE = re.compile(
    r"\bvintage performance\b|\b(?:origination )?cohort performance\b|\bmonth[s]? on book\b",
    re.IGNORECASE,
)
_EXPLICIT_TIME_SCOPE_RE = re.compile(
    r"\b(?:today|yesterday|this|last|past|previous|month|quarter|year|fy\s*\d+|"
    r"financial\s+year|calendar\s+year|20\d{2})\b",
    re.IGNORECASE,
)

_KNOWN_DATA_GAPS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"\bannual business plan\b",
        r"\b(?:above|below|against|off)(?:\s+or\s+(?:above|below))?[ -]?"
        r"(?:target|budget|expectation)s?\b",
        r"\b(?:different|variance)\s+from\s+budget\b",
        r"\bon track\b[^?]{0,50}\b(?:plan|target|initiative)s?\b",
        r"\bsales funnel\b|\bacquisition process\b|\bfunnel stage",
        r"\bapproval rates?\b",
        r"\bprofitability\b|\bcontribution margin\b|\bmaking and losing money\b",
        r"\bcost overruns?\b|\bcost of acquisition\b|\bCAC\b",
        r"\boperational bottlenecks?\b|\bturnaround time\b|\brework\b",
        r"\bcustomer (?:tickets?|complaints?|experience)\b",
        r"\blegal matters?\b|\blegal cases?\b|\bcontracts? or cases?\b",
        r"\baudit observations?\b|\bcontrol failures?\b",
        r"\bstrategic initiatives?\b|\bOKRs?\b",
        r"\bcompliance (?:or regulatory )?exceptions?\b|\bregulatory exceptions?\b",
        r"\b(?:people|capability) gaps?\b",
        r"\bsales teams?\b[^?]{0,50}\bunderperform",
    )
)

_DATA_HEALTH_RE = re.compile(
    r"\b(?:technology|data|etl|pipeline)\b[^?]{0,80}"
    r"\b(?:issues?|freshness|delay|latency|impacting|performance)\b",
    re.IGNORECASE,
)


def _enterprise_coverage_plan(question: str) -> PlanResult | None:
    """Fast, reviewed routing for capabilities the catalog can prove or disprove.

    Known missing domains must not spend two model calls generating plausible SQL against
    neighbouring loan-book tables. Data-health questions are the exception: scheduled
    freshness signals already provide governed evidence through the CEO briefing.
    """
    if _DATA_HEALTH_RE.search(question):
        return BriefingPlan(
            persona_id="ceo",
            confidence=1.0,
            reasoning="scheduled data-health signals and current executive indicators",
        )
    if any(pattern.search(question) for pattern in _KNOWN_DATA_GAPS):
        return RefusalPlan(reason="not_in_data")
    return None


def _common_business_plan(question: str) -> PlanResult | None:
    """Reviewed plans for short, high-frequency questions the small model confuses.

    These are semantic patterns, not exact question strings.  Time-qualified variants stay
    with the planner because their period still needs to be resolved.
    """
    if _VINTAGE_PERFORMANCE_RE.search(question):
        return QuerySpecPlan(
            spec={
                "metrics": ["vintage_par30_rate", "vintage_npa_rate"],
                "dimensions": ["vintage_origination_month", "month"],
                "period": {"relative": "all_time"},
            },
            confidence=1.0,
            reasoning="governed origination cohorts measured across available report months",
        )

    if _INTEREST_RATE_AMOUNT_RE.search(question):
        return ClarifyPlan(
            question=(
                "An interest rate is a percentage, so it cannot be totaled as a money amount. "
                "Would you like interest collected, interest due, or the average interest rate?"
            ),
            suggestions=[
                "What is the total interest collected?",
                "What is the total interest due?",
                "What is the average interest rate?",
            ],
        )

    explicitly_all_time = bool(re.search(r"\ball[ -]?time\b|\bwhole\s+book\b", question, re.I))
    if _EXPLICIT_TIME_SCOPE_RE.search(question) and not explicitly_all_time:
        return None

    if _BORROWER_COUNT_RE.search(question) and _BY_PRODUCT_RE.search(question):
        return QuerySpecPlan(
            spec={
                "metrics": ["customer_count"],
                "dimensions": ["product"],
                "period": {"relative": "all_time"},
            },
            confidence=1.0,
            reasoning="distinct borrowers grouped by governed product",
        )

    if _OPEN_CLOSED_RE.search(question) and re.search(r"\b(?:loan|account)s?\b", question, re.I):
        return QuerySpecPlan(
            spec={
                "metrics": ["loan_count"],
                "dimensions": ["open_closed_status"],
                "period": {"relative": "all_time"},
                "as_share": True,
            },
            confidence=1.0,
            reasoning="loan accounts split into governed open and closed lifecycle states",
        )

    if _INTEREST_BY_SCHEME_RE.search(question):
        return QuerySpecPlan(
            spec={
                "metrics": ["avg_interest_rate"],
                "dimensions": ["scheme"],
                "period": {"relative": "all_time"},
            },
            confidence=1.0,
            reasoning="sanction-weighted average interest rate grouped by loan scheme",
        )

    if _VARIOUS_INTEREST_RATES_RE.search(question):
        return SqlPlan(
            intent="list the distinct account interest rates and loan count at each rate",
            tables=["gold.loan_account_master"],
            confidence=1.0,
            reasoning="a distinct rate distribution is a governed column-list query",
        )

    if _SCHEME_AMOUNT_PAID_RE.search(question):
        metric = "interest_collected" if re.search(r"\binterest\s+paid\b", question, re.I) else (
            "principal_collected" if re.search(r"\bprincipal\s+paid\b", question, re.I)
            else "amount_collected"
        )
        return QuerySpecPlan(
            spec={
                "metrics": [metric],
                "dimensions": ["scheme"],
                "period": {"relative": "all_time"},
            },
            confidence=1.0,
            reasoning="paid amount grouped by the governed loan scheme",
        )

    if _TOTAL_SANCTIONED_RE.search(question):
        return QuerySpecPlan(
            spec={
                "metrics": ["sanctioned_amount"],
                "dimensions": [],
                "period": {"relative": "all_time"},
            },
            confidence=1.0,
            reasoning="total sanctioned amount across the full available loan book",
        )
    return None


def _catalog_tables_for(question: str, catalog: Catalog) -> list[str]:
    """Return Gold tables backed by a strong curated lexical match."""
    result = retrieve(question, catalog=catalog, use_vectors=False)
    if not any(
        hit.lexical >= 1.0 and hit.doc.kind in {"table", "column", "metric", "dimension"}
        for hit in result.hits
    ):
        return []
    return result.tables


@dataclass(slots=True)
class PlanOutcome:
    plan: PlanResult
    attempts: int
    prompt_version: str
    model: str
    provider: str
    duration_ms: int
    repaired: bool = False
    raw: str = ""


def _agent_borrower_count_plan(question: str) -> QuerySpecPlan | None:
    """Deterministically handle either word order: 'under agent45 how many borrowers'."""
    if not _BORROWER_COUNT_RE.search(question):
        return None
    match = _AGENT_CODE_RE.search(question)
    if match is None:
        return None
    code = match.group("code").strip().lower()
    values = [code]
    operational = re.fullmatch(r"(?:agent|agnt)?[-_ ]*(?P<number>\d+)", code)
    if operational is not None:
        number = operational.group("number")
        values.extend([number, f"agent{number}", f"agnt{number}"])
    values = list(dict.fromkeys(values))
    return QuerySpecPlan(
        spec={
            "metrics": ["customer_count"],
            "filters": [{"field": "agent", "op": "in", "value": values}],
            "period": {"relative": "all_time"},
        },
        confidence=1.0,
        reasoning="distinct borrowers filtered by the governed loan-account agent code",
    )


def _named_month_borrower_count_plan(question: str) -> QuerySpecPlan | None:
    """Distinct borrowers with sanctioned loans in one explicit calendar month."""
    if not _DISTINCT_BORROWERS_RE.search(question) or not _LOAN_RECEIPT_RE.search(question):
        return None
    matches = list(_NAMED_MONTH_RE.finditer(question))
    if len(matches) != 1:
        return None
    match = matches[0]
    year = int(match.group("year"))
    month = _MONTHS[match.group("month").lower()]
    return QuerySpecPlan(
        spec={
            "metrics": ["customer_count"],
            "period": {
                "start": date(year, month, 1),
                "end": date(year, month, calendar.monthrange(year, month)[1]),
            },
        },
        confidence=1.0,
        reasoning="distinct borrowers with loans sanctioned in the explicit calendar month",
    )


def _top_borrowers_plan(question: str) -> QuerySpecPlan | None:
    """Default an unqualified top-borrower ranking to current principal outstanding."""
    match = _TOP_BORROWERS_RE.search(question)
    if match is None:
        return None
    requested_limit = match.group("limit")
    limit = max(1, min(int(requested_limit), 5000)) if requested_limit else 10
    return QuerySpecPlan(
        spec={
            "metrics": ["principal_outstanding_book"],
            "dimensions": ["borrower"],
            "period": {"relative": "today"},
            "order_by": {"field": "principal_outstanding_book", "direction": "desc"},
            "limit": limit,
        },
        confidence=1.0,
        reasoning="top borrowers ranked by current governed principal outstanding",
    )


def _top_agents_plan(question: str) -> QuerySpecPlan | None:
    """Rank governed agents by their current linked loans or linked borrowers."""
    match = _TOP_AGENTS_RE.search(question)
    if match is None:
        return None
    requested_limit = match.groupdict().get("limit")
    limit = max(1, min(int(requested_limit), 5000)) if requested_limit else 10
    by_customers = bool(re.search(r"\b(?:borrowers?|customers?)\b", question, re.I))
    metric = "customer_count" if by_customers else "agent_linked_loans"
    dimension = "loan_agent" if by_customers else "agent_profile"
    period = "all_time" if by_customers else "today"
    return QuerySpecPlan(
        spec={
            "metrics": [metric],
            "dimensions": [dimension],
            "period": {"relative": period},
            "order_by": {"field": metric, "direction": "desc"},
            "limit": limit,
        },
        confidence=1.0,
        reasoning=(
            "governed agents ranked by current linked borrowers"
            if by_customers
            else "governed agents ranked by current linked loans"
        ),
    )


def _agent_directory_plan(question: str) -> SqlPlan | None:
    """Route requested agent profile fields to reviewed deterministic SQL generation."""
    if _AGENT_DIRECTORY_RE.search(question) is None:
        return None
    return SqlPlan(
        intent=question,
        tables=["gold.agent_master"],
        confidence=1.0,
        reasoning="requested fields from the governed current agent directory",
    )


def _named_month_disbursement_plan(question: str) -> QuerySpecPlan | None:
    """Resolve explicit month bounds while preserving requested grouping dimensions."""
    if not _DISBURSEMENT_RE.search(question):
        return None
    matches = list(_NAMED_MONTH_RE.finditer(question))
    if not matches:
        return None

    first, last = matches[0], matches[-1]
    start_year = int(first.group("year"))
    start_month = _MONTHS[first.group("month").lower()]
    end_year = int(last.group("year"))
    end_month = _MONTHS[last.group("month").lower()]
    start = date(start_year, start_month, 1)
    end = date(end_year, end_month, calendar.monthrange(end_year, end_month)[1])

    if _COMPARE_RE.search(question) and len(matches) == 2:
        first_end = date(start_year, start_month, calendar.monthrange(start_year, start_month)[1])
        second_start = date(end_year, end_month, 1)
        second_end = date(end_year, end_month, calendar.monthrange(end_year, end_month)[1])
        return QuerySpecPlan(
            spec={
                "metrics": ["disbursement_total"],
                "period": {"start": start, "end": first_end},
                "compare_to": {"start": second_start, "end": second_end},
            },
            confidence=1.0,
            reasoning="explicit disbursement months resolved as a period comparison",
        )

    if start > end:
        return None

    dimensions: list[str] = []
    if _MONTHLY_RE.search(question):
        dimensions.append("month")
    if _BY_BRANCH_RE.search(question):
        dimensions.append("branch")
    if _BY_SCHEME_RE.search(question):
        dimensions.append("scheme")
    return QuerySpecPlan(
        spec={
            "metrics": ["disbursement_total"],
            "dimensions": dimensions,
            "period": {"start": start, "end": end},
        },
        confidence=1.0,
        reasoning="explicit disbursement period and breakdown resolved deterministically",
    )


async def plan(
    question: str,
    *,
    catalog: Catalog | None = None,
    client=None,
    history_messages: list[dict[str, str]] | None = None,
) -> PlanOutcome:
    """Ask the model to route and structure a question."""
    cat = catalog or get_catalog()
    normalized_question = normalize_lending_question(question)
    planning_question = _resolve_chart_request(normalized_question, history_messages or [])

    common = _common_business_plan(planning_question)
    if common is not None:
        return PlanOutcome(
            plan=common,
            attempts=0,
            prompt_version=PROMPT_VERSION,
            model="deterministic",
            provider="catalog",
            duration_ms=0,
        )

    enterprise = _enterprise_coverage_plan(planning_question)
    if enterprise is not None:
        return PlanOutcome(
            plan=enterprise,
            attempts=0,
            prompt_version=PROMPT_VERSION,
            model="deterministic",
            provider="catalog",
            duration_ms=0,
        )

    top_borrowers = _top_borrowers_plan(planning_question)
    if top_borrowers is not None:
        return PlanOutcome(
            plan=top_borrowers,
            attempts=0,
            prompt_version=PROMPT_VERSION,
            model="deterministic",
            provider="catalog",
            duration_ms=0,
        )

    top_agents = _top_agents_plan(planning_question)
    if top_agents is not None:
        return PlanOutcome(
            plan=top_agents,
            attempts=0,
            prompt_version=PROMPT_VERSION,
            model="deterministic",
            provider="catalog",
            duration_ms=0,
        )

    agent_directory = _agent_directory_plan(planning_question)
    if agent_directory is not None:
        return PlanOutcome(
            plan=agent_directory,
            attempts=0,
            prompt_version=PROMPT_VERSION,
            model="deterministic",
            provider="catalog",
            duration_ms=0,
        )

    borrower_count = _named_month_borrower_count_plan(planning_question)
    if borrower_count is not None:
        return PlanOutcome(
            plan=borrower_count,
            attempts=0,
            prompt_version=PROMPT_VERSION,
            model="deterministic",
            provider="catalog",
            duration_ms=0,
        )

    month_disbursement = _named_month_disbursement_plan(planning_question)
    if month_disbursement is not None:
        return PlanOutcome(
            plan=month_disbursement,
            attempts=0,
            prompt_version=PROMPT_VERSION,
            model="deterministic",
            provider="catalog",
            duration_ms=0,
        )

    agent_count = _agent_borrower_count_plan(planning_question)
    if agent_count is not None:
        return PlanOutcome(
            plan=agent_count,
            attempts=0,
            prompt_version=PROMPT_VERSION,
            model="deterministic",
            provider="catalog",
            duration_ms=0,
        )

    # A named-borrower filter is outside QuerySpec by design. Route this reviewed intent
    # deterministically so the model cannot drop the name and answer with the whole book.
    if (
        named_borrower_principal_name(planning_question)
        or named_borrower_disbursed_name(planning_question)
    ):
        return PlanOutcome(
            plan=SqlPlan(
                intent=planning_question,
                tables=["gold.loan_account_master"],
                confidence=1.0,
                reasoning="named-borrower principal lookup uses governed SQL",
            ),
            attempts=0,
            prompt_version=PROMPT_VERSION,
            model="deterministic",
            provider="catalog",
            duration_ms=0,
        )

    llm = client or get_llm_client()

    # Repeated and rehearsed questions skip the model entirely. The key carries the catalog
    # version, so a catalog edit — which can change what a question *should* plan to —
    # invalidates every cached plan rather than serving a stale one.
    # A context-free plan is reusable; a context-aware plan belongs to this conversation.
    # Reusing it in another session would be a cross-session memory leak.
    cached = cache.get_plan(planning_question, cat.version) if not history_messages else None
    if cached is not None:
        return replace(cached, duration_ms=0, attempts=0)

    schema = plan_schema(cat)

    messages = build_messages(
        planning_question, catalog=cat, history_messages=history_messages or []
    )
    total_ms = 0
    attempts = 0
    previous_raw = ""
    error: str | None = None

    for attempt in range(2):  # initial + one repair
        attempts += 1
        if attempt == 1:
            messages = build_messages(
                planning_question,
                catalog=cat,
                repair_error=error,
                previous_attempt=previous_raw,
                history_messages=history_messages or [],
            )
        try:
            result = await llm.complete(
                messages=messages, json_schema=schema, max_tokens=700, temperature=0.0
            )
        except LLMError as exc:
            logger.warning("NLQ planner LLM call failed: %s", exc)
            raise

        total_ms += result.duration_ms
        previous_raw = result.text

        try:
            parsed = _parse(result.json(), cat)
            parsed = _enforce_relative_period(planning_question, parsed)
            parsed = _enforce_explicit_semantics(planning_question, parsed)
            if isinstance(parsed, RefusalPlan) and parsed.reason in {
                "not_in_data",
                "out_of_scope",
            }:
                matched_tables = _catalog_tables_for(planning_question, cat)
                if matched_tables:
                    parsed = SqlPlan(
                        intent=planning_question,
                        tables=matched_tables,
                        confidence=0.7,
                        reasoning="curated Gold catalog overrides an unsupported data refusal",
                    )
        except (PlanValidationError, ValidationError, LLMError) as exc:
            error = str(exc)
            logger.info("NLQ plan rejected on attempt %d: %s", attempts, error)
            continue

        outcome = PlanOutcome(
            plan=parsed,
            attempts=attempts,
            prompt_version=PROMPT_VERSION,
            model=result.model,
            provider=result.provider,
            duration_ms=total_ms,
            repaired=attempts > 1,
            raw=result.text,
        )
        # Only successful plans are cached. Caching a refusal or a clarification would
        # freeze a decision the next catalog change might legitimately reverse.
        if isinstance(parsed, QuerySpecPlan) and not history_messages:
            cache.put_plan(planning_question, cat.version, outcome)
        return outcome

    # Both attempts failed validation. Demoting to the SQL fallback is the plan's policy,
    # and it keeps the failure honest: that path shows its SQL and is marked unverified.
    logger.info("NLQ planner demoting to text-to-SQL after %d attempts: %s", attempts, error)
    return PlanOutcome(
        plan=SqlPlan(
            intent=planning_question,
            tables=[],
            confidence=0.3,
            reasoning=f"planner validation failed: {error}"[:500],
        ),
        attempts=attempts,
        prompt_version=PROMPT_VERSION,
        model=getattr(llm, "model", ""),
        provider=getattr(llm, "provider", ""),
        duration_ms=total_ms,
        repaired=True,
        raw=previous_raw,
    )


class PlanValidationError(ValueError):
    """The model produced a structurally valid plan that the catalog rejects."""


_RELATIVE_PERIOD_PHRASES = (
    (
        re.compile(
            r"\b(?:(?:this|current)\s+(?:financial|fiscal)\s+year|this\s+fy|this\s+year)\b",
            re.I,
        ),
        "fy_to_date",
    ),
    (re.compile(r"\b(?:last|past|previous)\s+90\s+days?\b", re.I), "last_90_days"),
    (re.compile(r"\b(?:last|past|previous)\s+30\s+days?\b", re.I), "last_30_days"),
    (re.compile(r"\b(?:last|past|previous)\s+12\s+months?\b", re.I), "last_12_months"),
)
_EXPLICIT_PERIOD_ANCHOR = re.compile(
    r"\b(?:ending|ended|as\s+of|up\s+to|through)\b|\b20\d{2}\b", re.I
)

_DONUT_SUFFIX = re.compile(
    r"(?:[,.]?\s*)\b(?:in|as)\s+(?:a\s+)?donut(?:\s+(?:chart|graph))?\s*[?.!]*$",
    re.I,
)
_DONUT_ONLY = re.compile(
    r"^\s*(?:(?:show|display|render|make)\s+)?(?:(?:it|this|that)\s+)?"
    r"(?:(?:in|as)\s+)?(?:a\s+)?donut(?:\s+(?:chart|graph))?\s*[?.!]*$",
    re.I,
)
_SHARE_WORDS = re.compile(r"\b(?:share|mix|composition|split)\b", re.I)
_OVERDUE_PRINCIPAL = re.compile(
    r"\b(?:overdue[- ]principal|principal[- ]overdue|principal\s+(?:in\s+)?arrears)\b",
    re.I,
)
_PAR_30 = re.compile(r"\bpar\s*[- ]?30\b", re.I)


def _resolve_chart_request(
    question: str, history_messages: list[dict[str, str]]
) -> str:
    """Turn presentation wording into analytic intent before it reaches the planner.

    The model plans data; the application draws it. Removing a trailing chart instruction
    prevents a capable model from replying that it cannot render graphics. A chart-only
    follow-up reuses the previous user question from this conversation.
    """
    if _DONUT_ONLY.fullmatch(question):
        previous = next(
            (
                str(message.get("content", "")).strip()
                for message in reversed(history_messages)
                if message.get("role") == "user" and str(message.get("content", "")).strip()
            ),
            "",
        )
        if previous:
            return f"{previous} Show the result as a share or composition."
    if _DONUT_SUFFIX.search(question):
        base = _DONUT_SUFFIX.sub("", question).strip()
        return f"{base} Show the result as a share or composition."
    return question


def _enforce_explicit_semantics(question: str, parsed: PlanResult) -> PlanResult:
    """Protect explicit business words from plausible neighbouring-metric guesses."""
    if not isinstance(parsed, QuerySpecPlan):
        return parsed
    spec = parsed.spec
    updates: dict[str, Any] = {}
    if _SHARE_WORDS.search(question) and not spec.as_share:
        updates["as_share"] = True
    if (
        _OVERDUE_PRINCIPAL.search(question)
        and not _PAR_30.search(question)
        and spec.metrics != ["overdue_principal"]
    ):
        updates["metrics"] = ["overdue_principal"]
    if not updates:
        return parsed
    corrected = spec.model_copy(update=updates)
    return parsed.model_copy(update={"spec": corrected})


def _enforce_relative_period(question: str, parsed: PlanResult) -> PlanResult:
    """Keep explicit relative phrases relative instead of accepting guessed dates.

    The model does not receive the wall-clock date because the stable system prompt is KV
    cacheable. It must therefore emit the closed relative-period token; if it instead
    invents concrete dates, the query can silently land outside the warehouse's history.
    An explicit user-supplied anchor ("90 days ending 31 March 2026") is left alone.
    """
    if not isinstance(parsed, QuerySpecPlan) or _EXPLICIT_PERIOD_ANCHOR.search(question):
        return parsed
    for pattern, relative in _RELATIVE_PERIOD_PHRASES:
        if pattern.search(question) and parsed.spec.period.relative != relative:
            corrected = parsed.spec.model_copy(update={"period": Period(relative=relative)})
            return parsed.model_copy(update={"spec": corrected})
    return parsed


def _parse(payload: Any, catalog: Catalog) -> PlanResult:
    """Validate the model's JSON against the contracts, then against the catalog."""
    if not isinstance(payload, dict):
        raise PlanValidationError(f"expected a JSON object, got {type(payload).__name__}")

    route = payload.get("route")
    if route not in (
        "queryspec", "analysis", "worklist", "briefing", "sql", "clarify", "refuse",
    ):
        raise PlanValidationError(f"unknown route {route!r}")

    # Only keep the fields belonging to the chosen route: models routinely emit the whole
    # union, and `extra="forbid"` would otherwise reject an otherwise-correct plan.
    trimmed = _trim_to_route(payload, route)

    try:
        parsed = _plan_adapter.validate_python(trimmed)
    except ValidationError as exc:
        raise PlanValidationError(_first_error(exc)) from exc

    if isinstance(parsed, BriefingPlan):
        if parsed.persona_id not in catalog.personas:
            raise PlanValidationError(f"unknown persona {parsed.persona_id!r}")

    if isinstance(parsed, WorklistPlan):
        if parsed.worklist_id not in catalog.worklists.presets:
            raise PlanValidationError(f"unknown worklist {parsed.worklist_id!r}")
        if parsed.confidence < CONFIDENCE_FLOOR:
            return ClarifyPlan(
                question="I am not confident I understood that. Could you rephrase it?",
                suggestions=_suggestions(catalog),
            )

    if isinstance(parsed, AnalysisPlan):
        if parsed.analysis_id not in catalog.analyses:
            raise PlanValidationError(f"unknown analysis {parsed.analysis_id!r}")
        if parsed.confidence < CONFIDENCE_FLOOR:
            return ClarifyPlan(
                question="I am not confident I understood that. Could you rephrase it?",
                suggestions=_suggestions(catalog),
            )

    if isinstance(parsed, QuerySpecPlan):
        if parsed.confidence < CONFIDENCE_FLOOR:
            # Not an error — a low-confidence guess is exactly when to ask instead.
            return ClarifyPlan(
                question="I am not confident I understood that. Could you rephrase it?",
                suggestions=_suggestions(catalog),
            )
        try:
            compile_spec(parsed.spec, catalog)
        except CompileError as exc:
            raise PlanValidationError(str(exc)) from exc

    return parsed


_ROUTE_FIELDS = {
    "queryspec": {"route", "spec", "confidence", "reasoning"},
    "analysis": {"route", "analysis_id", "period", "filters", "confidence", "reasoning"},
    "worklist": {"route", "worklist_id", "filters", "limit", "confidence", "reasoning"},
    "briefing": {"route", "persona_id", "confidence", "reasoning"},
    "sql": {"route", "intent", "tables", "confidence", "reasoning"},
    "clarify": {"route", "question", "suggestions"},
    "refuse": {"route", "reason", "message", "examples"},
}


def _trim_to_route(payload: dict[str, Any], route: str) -> dict[str, Any]:
    keep = _ROUTE_FIELDS[route]
    trimmed = {k: v for k, v in payload.items() if k in keep and v is not None}
    if (
        route in ("queryspec", "analysis", "worklist", "briefing", "sql")
        and "confidence" not in trimmed
    ):
        trimmed["confidence"] = 0.7
    if route == "refuse" and "reason" not in trimmed:
        trimmed["reason"] = "out_of_scope"
    if route == "clarify" and "question" not in trimmed:
        trimmed["question"] = "Could you say which measure and period you mean?"
    return trimmed


def _first_error(exc: ValidationError) -> str:
    error = exc.errors()[0]
    location = ".".join(str(p) for p in error["loc"])
    return f"{location}: {error['msg']}"


def _suggestions(catalog: Catalog) -> list[str]:
    return [
        "What was our disbursement by branch last quarter?",
        "What is our PAR 30 right now?",
        "Collection efficiency by product this financial year",
    ]


def refusal_examples(question: str = "", reason: str = "") -> list[str]:
    """Return reviewed, answerable pivots for a refusal.

    The model never authors these. Topic matching only selects among questions backed by
    an existing analysis or worklist; it does not decide a metric or manufacture a new
    capability. The generic catalog examples remain the safe fallback.
    """
    normalized = question.lower()
    if reason == "predictive" and re.search(
        r"\b(?:delinquen|default|portfolio quality|credit risk|npa|par)\w*\b", normalized
    ):
        return [
            "Which borrowers show early warning signs of default?",
            "How healthy is our credit portfolio right now?",
            "PAR 30 by product and branch right now",
        ]
    if re.search(r"\bcollection\w*\b.*\b(?:strategy|approach|contact)\b", normalized):
        return [
            "Show today's collections priority list",
            "Collection efficiency by branch this financial year",
            "Which delinquency buckets have the highest overdue balance?",
        ]
    if re.search(r"\b(?:growth potential|potential for growth|grow fastest)\b", normalized):
        return [
            "Which products have the best combination of growth and credit quality?",
            "Disbursement by product this financial year",
            "PAR 30 by product right now",
        ]
    if re.search(r"\b(?:business plan|target|budget|cost overrun)\w*\b", normalized):
        return [
            "How is the business performing today, and what are the 5 things I need to know?",
            "Disbursement by branch this financial year",
            "How healthy is our credit portfolio right now?",
        ]
    if re.search(r"\b(?:anomal|leakage|unusual pattern|control failure)\w*\b", normalized):
        return [
            "What has changed materially in the loan book this month?",
            "How healthy is our credit portfolio right now?",
            "Which borrowers show early warning signs of default?",
        ]
    return _suggestions(get_catalog())
