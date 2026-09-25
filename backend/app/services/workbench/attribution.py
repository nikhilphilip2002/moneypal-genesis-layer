"""Backend-authoritative reconciliation of model-declared query provenance."""

from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.services.workbench.agent_contracts import ExcludedQueryReference, FinalSynthesis


class ReconciledAttribution(BaseModel):
    model_config = ConfigDict(extra="forbid")

    active_query_ids: list[str] = Field(default_factory=list)
    visual_query_ids: list[str] = Field(default_factory=list)
    excluded_queries: list[ExcludedQueryReference] = Field(default_factory=list)
    invalid_query_ids: list[str] = Field(default_factory=list)
    fallback_used: bool = False


def next_query_number(registry: list[dict[str, Any]], *, prefix: str = "q") -> int:
    """Continue the visible query counter across saved conversation turns."""
    pattern = re.compile(rf":{re.escape(prefix)}(\d+)$")
    return 1 + max((
        int(match.group(1))
        for record in registry if isinstance(record, dict)
        if (match := pattern.search(str(record.get("query_id") or "")))
    ), default=0)


def resolve_current_query(
    registry: list[dict[str, Any]], query_number: int,
    *, prior_registry: list[dict[str, Any]] = (),
) -> dict[str, Any] | None:
    """Resolve qN, preferring this turn when older conversations reused the number."""
    suffix = f":q{query_number}"
    matches = [
        record for record in [*prior_registry, *registry]
        if isinstance(record, dict)
        and str(record.get("query_id") or "").endswith(suffix)
        and record.get("source_query_id") is None
    ]
    return matches[-1] if matches else None


def _exclusion(
    record: dict[str, Any], *, superseded: bool = False,
) -> ExcludedQueryReference:
    status = str(record.get("status") or "error")
    purpose = str(record.get("purpose") or "answer")
    if status == "timeout":
        code, reason = "timeout", "The query timed out."
    elif status == "cancelled":
        code, reason = "cancelled", "The query was cancelled."
    elif status == "empty" or not record.get("has_data", False):
        if status in {"error", "pending", "running"}:
            code, reason = "execution_error", "The query did not complete successfully."
        else:
            code, reason = "empty_result", "The query returned no rows."
    elif superseded:
        code, reason = "superseded", "The query was replaced by a later result."
    elif purpose == "discovery":
        code, reason = "discovery_only", "The query was used only for discovery."
    elif purpose == "validation":
        code, reason = "validation_only", "The query was used only for validation."
    else:
        code, reason = "unused_by_synthesis", "The final narrative did not use this result."
    return ExcludedQueryReference(
        query_id=str(record["query_id"]), reason_code=code, reason=reason,
    )


def reconcile_query_attribution(
    registry: list[dict[str, Any]],
    synthesis: FinalSynthesis,
    *, prior_registry: list[dict[str, Any]] = (),
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
    selected_record = resolve_current_query(
        registry, synthesis.query_id, prior_registry=prior_registry,
    )
    selected_id = (
        str(selected_record.get("query_id")) if selected_record is not None else ""
    )
    valid_selection = (
        selected_record is not None
        and selected_record.get("status") == "success"
        and selected_record.get("has_data") is True
    )
    invalid = [] if valid_selection else [f"q{synthesis.query_id}"]
    active = [selected_id] if valid_selection else []
    # The final-answer tool creates the single card directly from the selected query.
    visual = list(active)

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
