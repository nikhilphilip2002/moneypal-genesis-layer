"""Workbench usage and latency telemetry aggregation."""

from __future__ import annotations

from math import ceil
from typing import Any, Iterable


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


__all__ = ["percentile", "usage_summary"]
