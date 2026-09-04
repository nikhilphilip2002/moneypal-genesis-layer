"""Purpose-aware LLM telemetry shared by NLQ and Workbench.

The HTTP client records one entry for every logical model request.  A request may contain
provider retries; those retries remain attached to the same entry so call-budget reports can
distinguish planned work from transport recovery.  Workbench installs a per-turn collector
with a context variable, which is inherited by the fan-out tasks created with
``asyncio.gather``.

Prompt fingerprints intentionally contain no prompt text.  They prove that a stable prefix
is byte-identical without copying schema, private context, or user questions into metrics.
"""

from __future__ import annotations

import contextvars
import hashlib
import json
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from typing import Any, Iterator, Literal, Sequence


CallPurpose = Literal[
    "route",
    "db_plan",
    "sql_generate",
    "sql_repair",
    "vector_compose",
    "final_compose",
    "suggestions",
    "compaction",
    "unspecified",
]
CallKind = Literal["planned", "repair", "warmup"]

CALL_PURPOSES: tuple[str, ...] = (
    "route",
    "db_plan",
    "sql_generate",
    "sql_repair",
    "vector_compose",
    "final_compose",
    "suggestions",
    "compaction",
)


def stable_hash(value: str | bytes) -> str:
    """Return a version-independent SHA-256 fingerprint for exact prefix bytes."""
    raw = value.encode("utf-8") if isinstance(value, str) else value
    return hashlib.sha256(raw).hexdigest()


def serialize_messages(messages: Sequence[dict[str, str]]) -> bytes:
    """Serialize messages deterministically for byte-stability tests and fingerprints."""
    return json.dumps(
        list(messages), ensure_ascii=False, separators=(",", ":"), sort_keys=True,
    ).encode("utf-8")


def prefix_hash(messages: Sequence[dict[str, str]]) -> str:
    return stable_hash(serialize_messages(messages))


@dataclass(frozen=True, slots=True)
class CallRecord:
    purpose: str
    call_kind: str
    provider: str
    model: str
    prompt_version: str
    catalog_version: str
    prefix_hash: str
    prompt_tokens: int
    cached_prompt_tokens: int
    cache_write_prompt_tokens: int
    uncached_prompt_tokens: int
    completion_tokens: int
    duration_ms: int
    attempts: int
    retries: int
    finish_reason: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


_collector: contextvars.ContextVar[list[CallRecord] | None] = contextvars.ContextVar(
    "llm_call_collector", default=None,
)


@contextmanager
def collect_calls() -> Iterator[list[CallRecord]]:
    """Collect model calls made in this async context and its child tasks."""
    records: list[CallRecord] = []
    token = _collector.set(records)
    try:
        yield records
    finally:
        _collector.reset(token)


def record_call(record: CallRecord) -> None:
    records = _collector.get()
    if records is not None:
        records.append(record)


def summarize_calls(records: Sequence[CallRecord]) -> dict[str, Any]:
    """Return turn-level totals while retaining a context-size-compatible prompt value.

    ``prompt_tokens`` historically represented the size of one conversation-bearing call
    and is consumed by the compaction budget.  It therefore remains the largest individual
    prompt.  Additive cost totals use explicit ``total_*`` names.
    """
    weighted_input_units = sum(
        item.uncached_prompt_tokens
        + item.cache_write_prompt_tokens * 1.25
        + item.cached_prompt_tokens * 0.10
        for item in records
    )
    return {
        "model_call_count": len(records),
        "prompt_tokens": max((item.prompt_tokens for item in records), default=0),
        "total_prompt_tokens": sum(item.prompt_tokens for item in records),
        "cached_prompt_tokens": sum(item.cached_prompt_tokens for item in records),
        "cache_write_prompt_tokens": sum(item.cache_write_prompt_tokens for item in records),
        "uncached_prompt_tokens": sum(item.uncached_prompt_tokens for item in records),
        "completion_tokens": sum(item.completion_tokens for item in records),
        "model_duration_ms": sum(item.duration_ms for item in records),
        "retry_count": sum(item.retries for item in records),
        # Provider-neutral token-equivalent work. Currency reporting can multiply these
        # categories by the deployed provider's current price without losing detail.
        "weighted_input_units": round(weighted_input_units, 2),
        "calls": [item.to_dict() for item in records],
    }


def call_counts(records: Sequence[CallRecord]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for record in records:
        counts[record.purpose] = counts.get(record.purpose, 0) + 1
    return counts


def budget_violations(
    records: Sequence[CallRecord], limits: dict[str, int],
) -> dict[str, tuple[int, int]]:
    """Return ``purpose -> (actual, limit)`` for model-call budget test failures."""
    counts = call_counts(records)
    return {
        purpose: (counts.get(purpose, 0), limit)
        for purpose, limit in limits.items()
        if counts.get(purpose, 0) > limit
    }


__all__ = [
    "CALL_PURPOSES",
    "CallKind",
    "CallPurpose",
    "CallRecord",
    "collect_calls",
    "budget_violations",
    "call_counts",
    "prefix_hash",
    "record_call",
    "serialize_messages",
    "stable_hash",
    "summarize_calls",
]
