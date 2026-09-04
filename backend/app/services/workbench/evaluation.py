"""Deterministic Workbench evaluation fixtures and telemetry aggregation.

The fixture corpus is intentionally provider-independent. CI can route it with fake tools;
staging can run the same corpus against deployed PostgreSQL, Qdrant, web, and model services.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import ceil
from typing import Any, Iterable


@dataclass(frozen=True, slots=True)
class RouteFixture:
    id: str
    question: str
    sources: tuple[str, ...]
    external_modes: tuple[bool, ...] = (False, True)
    pinned: str | None = None
    history: tuple[tuple[str, str], ...] = ()


ROUTE_FIXTURES = (
    RouteFixture("db_metric", "Show our PAR 30 by branch", ("db",), (False, True)),
    RouteFixture("db_lookup", "Loan details for customer ID 128", ("db",), (False, True)),
    RouteFixture("db_followup", "and by branch?", ("db",), (False, True), history=(
        ("user", "Show our PAR 30"), ("assistant", "PAR 30 was 4.2%."),
    )),
    RouteFixture("schema", "Show loan account table relationships", ("schema",), (False, True)),
    RouteFixture("knowledge", "What does PAR 30 mean?", ("knowledge",), (False, True)),
    RouteFixture("macro", "Explain Karnataka GDP growth trends", ("macro",), (True,)),
    RouteFixture("competitive", "Who competes for MSME borrowers?", ("competitive",), (True,)),
    RouteFixture("regulatory", "Explain RBI priority sector rules", ("regulatory",), (True,)),
    RouteFixture("web", "Search the web for the latest RBI repo announcement", ("web",), (True,)),
    RouteFixture(
        "mixed", "Compare our loan growth with Karnataka GDP growth", ("db", "macro"), (True,),
    ),
    RouteFixture("pinned_macro", "outlook", ("macro",), (True,), pinned="macro"),
)


def percentile(values: Iterable[int | float], percent: int) -> float:
    ordered = sorted(float(value) for value in values)
    if not ordered:
        return 0.0
    index = max(0, min(len(ordered) - 1, ceil((percent / 100) * len(ordered)) - 1))
    return ordered[index]


def usage_summary(turns: Iterable[dict[str, Any]]) -> dict[str, Any]:
    calls: dict[str, list[int]] = {}
    latency: dict[str, list[int]] = {"first_event_ms": [], "first_card_ms": [], "total_ms": []}
    for turn in turns:
        usage = turn.get("usage") or {}
        for call in usage.get("calls") or []:
            calls.setdefault(str(call.get("purpose", "unspecified")), []).append(
                int(call.get("uncached_prompt_tokens", 0))
            )
        timing = turn.get("timing") or {}
        for field in latency:
            latency[field].append(int(timing.get(field, 0)))
    return {
        "purposes": {
            purpose: {"count": len(values), "p50_uncached": percentile(values, 50),
                      "p95_uncached": percentile(values, 95)}
            for purpose, values in sorted(calls.items())
        },
        "latency": {
            field: {"p50": percentile(values, 50), "p95": percentile(values, 95)}
            for field, values in latency.items()
        },
    }


__all__ = ["ROUTE_FIXTURES", "RouteFixture", "percentile", "usage_summary"]
