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
from app.services.nlq.compiler import CompileError, compile_spec
from app.services.nlq.contracts import (
    ClarifyPlan,
    PlanResult,
    Period,
    QuerySpecPlan,
    SqlPlan,
)
from app.services.nlq.llm import LLMError, get_llm_client
from app.services.nlq.llm.prompts import PROMPT_VERSION, build_messages
from app.services.nlq.llm.schemas import plan_schema
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
_AGENT_CODE_RE = re.compile(r"\bagent\s*[-:# ]*(?P<code>[a-z0-9_-]+)\b", re.IGNORECASE)
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
    r"\btop\s+(?P<limit>\d{1,4})\s+(?:borrowers?|customers?|clients?)\b",
    re.IGNORECASE,
)


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
    code = match.group("code").strip()
    values = [code, f"agent{code}"] if not code.lower().startswith("agent") else [code]
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
    limit = max(1, min(int(match.group("limit")), 5000))
    return QuerySpecPlan(
        spec={
            "metrics": ["principal_outstanding"],
            "dimensions": ["borrower"],
            "period": {"relative": "today"},
            "order_by": {"field": "principal_outstanding", "direction": "desc"},
            "limit": limit,
        },
        confidence=1.0,
        reasoning="top borrowers ranked by current governed principal outstanding",
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
    planning_question = _resolve_chart_request(question, history_messages or [])

    top_borrowers = _top_borrowers_plan(question)
    if top_borrowers is not None:
        return PlanOutcome(
            plan=top_borrowers,
            attempts=0,
            prompt_version=PROMPT_VERSION,
            model="deterministic",
            provider="catalog",
            duration_ms=0,
        )

    borrower_count = _named_month_borrower_count_plan(question)
    if borrower_count is not None:
        return PlanOutcome(
            plan=borrower_count,
            attempts=0,
            prompt_version=PROMPT_VERSION,
            model="deterministic",
            provider="catalog",
            duration_ms=0,
        )

    month_disbursement = _named_month_disbursement_plan(question)
    if month_disbursement is not None:
        return PlanOutcome(
            plan=month_disbursement,
            attempts=0,
            prompt_version=PROMPT_VERSION,
            model="deterministic",
            provider="catalog",
            duration_ms=0,
        )

    agent_count = _agent_borrower_count_plan(question)
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
    if named_borrower_principal_name(question) or named_borrower_disbursed_name(question):
        return PlanOutcome(
            plan=SqlPlan(
                intent=question,
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
    cached = cache.get_plan(question, cat.version) if not history_messages else None
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
            cache.put_plan(question, cat.version, outcome)
        return outcome

    # Both attempts failed validation. Demoting to the SQL fallback is the plan's policy,
    # and it keeps the failure honest: that path shows its SQL and is marked unverified.
    logger.info("NLQ planner demoting to text-to-SQL after %d attempts: %s", attempts, error)
    return PlanOutcome(
        plan=SqlPlan(
            intent=question,
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
    if route not in ("queryspec", "sql", "clarify", "refuse"):
        raise PlanValidationError(f"unknown route {route!r}")

    # Only keep the fields belonging to the chosen route: models routinely emit the whole
    # union, and `extra="forbid"` would otherwise reject an otherwise-correct plan.
    trimmed = _trim_to_route(payload, route)

    try:
        parsed = _plan_adapter.validate_python(trimmed)
    except ValidationError as exc:
        raise PlanValidationError(_first_error(exc)) from exc

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
    "sql": {"route", "intent", "tables", "confidence", "reasoning"},
    "clarify": {"route", "question", "suggestions"},
    "refuse": {"route", "reason", "message", "examples"},
}


def _trim_to_route(payload: dict[str, Any], route: str) -> dict[str, Any]:
    keep = _ROUTE_FIELDS[route]
    trimmed = {k: v for k, v in payload.items() if k in keep and v is not None}
    if route in ("queryspec", "sql") and "confidence" not in trimmed:
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


def refusal_examples() -> list[str]:
    return _suggestions(get_catalog())
