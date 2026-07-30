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

import logging
from dataclasses import dataclass, replace
from typing import Any

from pydantic import TypeAdapter, ValidationError

from app.services.nlq import cache
from app.services.nlq.catalog import Catalog, get_catalog
from app.services.nlq.compiler import CompileError, compile_spec
from app.services.nlq.contracts import (
    ClarifyPlan,
    PlanResult,
    QuerySpecPlan,
    RefusalPlan,
    SqlPlan,
)
from app.services.nlq.llm import LLMError, get_llm_client
from app.services.nlq.llm.prompts import PROMPT_VERSION, build_messages
from app.services.nlq.llm.schemas import plan_schema

logger = logging.getLogger(__name__)

CONFIDENCE_FLOOR = 0.6
_plan_adapter = TypeAdapter(PlanResult)


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


async def plan(
    question: str,
    *,
    catalog: Catalog | None = None,
    client=None,
) -> PlanOutcome:
    """Ask the model to route and structure a question."""
    cat = catalog or get_catalog()
    llm = client or get_llm_client()

    # Repeated and rehearsed questions skip the model entirely. The key carries the catalog
    # version, so a catalog edit — which can change what a question *should* plan to —
    # invalidates every cached plan rather than serving a stale one.
    cached = cache.get_plan(question, cat.version)
    if cached is not None:
        return replace(cached, duration_ms=0, attempts=0)

    schema = plan_schema(cat)

    messages = build_messages(question, catalog=cat)
    total_ms = 0
    attempts = 0
    previous_raw = ""
    error: str | None = None

    for attempt in range(2):  # initial + one repair
        attempts += 1
        if attempt == 1:
            messages = build_messages(
                question, catalog=cat, repair_error=error, previous_attempt=previous_raw
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
        if isinstance(parsed, QuerySpecPlan):
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
