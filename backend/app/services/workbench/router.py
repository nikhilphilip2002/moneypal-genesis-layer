"""Question -> which source(s). The workbench's one routing decision.

A single local-LLM call, constrained by a grammar-JSON schema built from the source
registry, so the model can only pick sources that exist and that the role may see. This is
the same discipline as the NLQ planner: structure the output, and a whole class of
malformed answers becomes impossible rather than merely unlikely.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from app.services.nlq.catalog.retrieval import retrieve
from app.services.nlq.llm import LLMError
from app.services.workbench import models
from app.services.workbench.sources import (
    ROUTER_FEW_SHOTS,
    router_system_prompt,
    route_schema,
    visible_sources,
)

logger = logging.getLogger(__name__)


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


@dataclass(slots=True)
class RouteDecision:
    route: str  # "dispatch" | "refuse"
    sources: list[str] = field(default_factory=list)
    intent: str = ""
    reason: str = ""
    message: str = ""
    model: str = ""


def _fallback(role: str, question: str) -> RouteDecision:
    """When routing itself fails, default to the loan book if the role can see it.

    A degraded router should still answer the common case rather than refuse everything.
    `db` is the modal source; if the role cannot see it, fall to the first visible one.
    """
    visible = visible_sources(role)
    if not visible:
        return RouteDecision(route="refuse", reason="out_of_scope",
                             message="No sources are available for your role.")
    default = "db" if any(s.id == "db" for s in visible) else visible[0].id
    return RouteDecision(route="dispatch", sources=[default], intent=question)


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
    if pinned:
        visible_ids = [s.id for s in visible_sources(role)]
        if pinned in visible_ids:
            return RouteDecision(route="dispatch", sources=[pinned], intent=question, model="pinned")

    client = models.for_step("route", sensitive=True)
    messages = [{"role": "system", "content": router_system_prompt(role)}]
    for user_text, assistant_json in ROUTER_FEW_SHOTS:
        messages.append({"role": "user", "content": user_text})
        messages.append({"role": "assistant", "content": assistant_json})
    messages.extend(history_messages or [])
    messages.append({"role": "user", "content": question})

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
        return _fallback(role, question)

    if not isinstance(payload, dict):
        return _fallback(role, question)

    visible_ids = [s.id for s in visible_sources(role)]
    catalog_match = "db" in visible_ids and _matches_loan_book_catalog(question)
    route_value = payload.get("route")
    if route_value == "refuse":
        if catalog_match:
            return RouteDecision(
                route="dispatch", sources=["db"], intent=question, model="catalog"
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
    if catalog_match and "db" not in chosen:
        chosen.insert(0, "db")
    if not chosen:
        return _fallback(role, question)

    return RouteDecision(
        route="dispatch",
        sources=chosen,
        intent=str(payload.get("intent", question)) or question,
        model=result.model,
    )
