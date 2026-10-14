"""Backend-authoritative reconciliation of model-declared query provenance."""

from __future__ import annotations

import re
from typing import Any, Sequence

from pydantic import BaseModel, ConfigDict, Field

from app.services.workbench.agent_contracts import (
    ExcludedQueryReference,
    FinalSynthesis,
    QueryEvidenceReference,
)


class ReconciledAttribution(BaseModel):
    model_config = ConfigDict(extra="forbid")

    active_query_ids: list[str] = Field(default_factory=list)
    visual_query_ids: list[str] = Field(default_factory=list)
    excluded_queries: list[ExcludedQueryReference] = Field(default_factory=list)
    invalid_query_ids: list[str] = Field(default_factory=list)
    fallback_used: bool = False


def next_query_number(
    registry: list[dict[str, Any]], *, prefix: str = "q"
) -> int:
    """Continue the visible query counter across saved conversation turns."""
    pattern = re.compile(rf":{re.escape(prefix)}(\d+)$")
    return 1 + max(
        (
            int(match.group(1))
            for record in registry
            if isinstance(record, dict)
            if (match := pattern.search(str(record.get("query_id") or "")))
        ),
        default=0,
    )


def resolve_current_query(
    registry: list[dict[str, Any]],
    query_number: int,
    *,
    prior_registry: Sequence[dict[str, Any]] = (),
) -> dict[str, Any] | None:
    """Resolve qN, preferring this turn when older conversations reused the number."""
    suffix = f":q{query_number}"
    matches = [
        record
        for record in [*prior_registry, *registry]
        if isinstance(record, dict)
        and str(record.get("query_id") or "").endswith(suffix)
        and record.get("source_query_id") is None
    ]
    return matches[-1] if matches else None


def _exclusion(
    record: dict[str, Any],
    *,
    superseded: bool = False,
) -> ExcludedQueryReference:
    status = str(record.get("status") or "error")
    purpose = str(record.get("purpose") or "answer")
    if status == "timeout":
        code, reason = "timeout", "The query timed out."
    elif status == "cancelled":
        code, reason = "cancelled", "The query was cancelled."
    elif status == "empty" or not record.get("has_data", False):
        if status in {"error", "pending", "running"}:
            code, reason = (
                "execution_error",
                "The query did not complete successfully.",
            )
        else:
            code, reason = "empty_result", "The query returned no rows."
    elif superseded:
        code, reason = (
            "superseded",
            "The query was replaced by a later result.",
        )
    elif purpose == "discovery":
        code, reason = (
            "discovery_only",
            "The query was used only for discovery.",
        )
    elif purpose == "validation":
        code, reason = (
            "validation_only",
            "The query was used only for validation.",
        )
    else:
        code, reason = (
            "unused_by_synthesis",
            "The final narrative did not use this result.",
        )
    return ExcludedQueryReference(
        query_id=str(record["query_id"]),
        reason_code=code,
        reason=reason,
    )


def reconcile_query_attribution(
    registry: list[dict[str, Any]],
    synthesis: FinalSynthesis,
    *,
    prior_registry: Sequence[dict[str, Any]] = (),
) -> ReconciledAttribution:
    """Validate the selected evidence; exclude unused executions from this turn only."""
    records = {
        str(record.get("query_id")): record
        for record in registry
        if isinstance(record, dict) and record.get("query_id")
    }
    superseded_ids = {
        str(record.get("supersedes_query_id"))
        for record in records.values()
        if record.get("supersedes_query_id")
    }
    active: list[str] = []
    invalid: list[str] = []
    visual: list[str] = []
    visual_numbers = {item.query_id for item in synthesis.visuals}
    for reference in synthesis.evidence:
        if not isinstance(reference, QueryEvidenceReference):
            continue
        selected_record = resolve_current_query(
            registry,
            reference.query_id,
            prior_registry=prior_registry,
        )
        if (
            selected_record is None
            or selected_record.get("status") != "success"
            or selected_record.get("has_data") is not True
        ):
            invalid.append(f"q{reference.query_id}")
            continue
        selected_id = str(selected_record["query_id"])
        if selected_id not in active:
            active.append(selected_id)
        if reference.query_id in visual_numbers and selected_id not in visual:
            visual.append(selected_id)

    excluded: list[ExcludedQueryReference] = []
    for query_id, record in records.items():
        if query_id in active or query_id in visual:
            continue
        if record.get("status") == "success" and record.get("has_data") is True:
            if record.get("purpose") == "answer":
                record["purpose"] = "intermediate"
        item = _exclusion(record, superseded=query_id in superseded_ids)
        excluded.append(item)
    return ReconciledAttribution(
        active_query_ids=active,
        visual_query_ids=visual,
        excluded_queries=excluded,
        invalid_query_ids=invalid,
        fallback_used=False,
    )


__all__ = ["ReconciledAttribution", "reconcile_query_attribution"]
