"""Backend-authoritative reconciliation of model-declared query provenance."""

from __future__ import annotations

from typing import Any, Iterable

from pydantic import BaseModel, ConfigDict, Field

from app.services.workbench.agent_contracts import ExcludedQueryReference, FinalSynthesis


class ReconciledAttribution(BaseModel):
    model_config = ConfigDict(extra="forbid")

    active_query_ids: list[str] = Field(default_factory=list)
    visual_query_ids: list[str] = Field(default_factory=list)
    excluded_queries: list[ExcludedQueryReference] = Field(default_factory=list)
    invalid_query_ids: list[str] = Field(default_factory=list)
    fallback_used: bool = False


def _ordered_unique(values: Iterable[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if isinstance(value, str) and value))


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
    *,
    allow_single_query_fallback: bool = False,
) -> ReconciledAttribution:
    """Validate model references against this turn's actual database executions."""

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
    proposed_active = _ordered_unique(synthesis.active_query_ids)
    eligible = {
        query_id for query_id, record in records.items()
        if record.get("status") == "success" and record.get("has_data") is True
    }
    derived_by_source: dict[str, str] = {}
    derived_visuals: list[str] = []
    for query_id, record in records.items():
        source_query_id = str(record.get("source_query_id") or "")
        if (
            query_id in eligible
            and record.get("tool_name") == "visualize_query_result"
            and record.get("visual_available") is True
        ):
            derived_visuals.append(query_id)
            if source_query_id:
                # Registry order is execution order, so a later successful visualization
                # replaces an earlier rendering of the same source result.
                derived_by_source[source_query_id] = query_id

    current_derived_visuals = [
        query_id for query_id in derived_visuals
        if derived_by_source.get(str(records[query_id].get("source_query_id") or ""))
        == query_id
    ]

    invalid = [
        query_id for query_id in proposed_active
        if query_id not in records and query_id not in derived_by_source
    ]

    def resolve(query_id: str, *, prefer_derived: bool = False) -> str | None:
        if prefer_derived and query_id in derived_by_source:
            return derived_by_source[query_id]
        if query_id in eligible:
            return query_id
        derived = derived_by_source.get(query_id)
        return derived if derived in eligible else None

    active = _ordered_unique(
        resolved for query_id in proposed_active
        if (resolved := resolve(query_id)) is not None
    )

    fallback_used = False
    if not active and allow_single_query_fallback:
        fallback_candidates = [
            query_id for query_id, record in records.items()
            if query_id in eligible and record.get("purpose", "answer") == "answer"
        ]
        if len(fallback_candidates) == 1:
            active = fallback_candidates
            fallback_used = True

    proposed_visual = _ordered_unique(synthesis.visual_query_ids)
    visual = _ordered_unique(
        resolved for query_id in proposed_visual
        if (
            (resolved := resolve(query_id, prefer_derived=True)) is not None
            and records[resolved].get("visual_available") is True
        )
    )
    selected_derived = any(query_id in current_derived_visuals for query_id in visual)
    if current_derived_visuals and not selected_derived:
        # A successful visualization call is an explicit presentation action. If the
        # synthesis forgets its returned :vN identifier, promote the latest derived card
        # instead of hiding both the source and the requested visual in the audit drawer.
        visual = _ordered_unique([
            *(query_id for query_id in visual if query_id not in derived_visuals),
            *current_derived_visuals,
        ])
        fallback_used = True
    for query_id in visual:
        if query_id not in active:
            active.append(query_id)
    if fallback_used and not visual:
        visual = [
            query_id for query_id in active
            if records[query_id].get("visual_available") is True
        ]

    model_exclusions = {item.query_id: item for item in synthesis.excluded_queries}
    excluded: list[ExcludedQueryReference] = []
    for query_id, record in records.items():
        if query_id in active:
            continue
        model_item = model_exclusions.get(query_id)
        if record.get("status") == "success" and record.get("has_data") is True:
            if model_item is not None and model_item.reason_code == "discovery_only":
                record["purpose"] = "discovery"
            elif model_item is not None and model_item.reason_code == "validation_only":
                record["purpose"] = "validation"
            elif record.get("purpose") == "answer":
                record["purpose"] = "intermediate"
        item = _exclusion(record, superseded=query_id in superseded_ids)
        if (
            item.reason_code == "unused_by_synthesis"
            and model_item is not None
            and model_item.reason_code == "superseded"
        ):
            item.reason_code = "superseded"
            item.reason = "The query was replaced by a later result."
        # The backend owns operational reason codes. Model rationale is accepted only for
        # a successful result the synthesis chose not to use, and Pydantic already bounds it.
        if (
            item.reason_code in {
                "unused_by_synthesis", "discovery_only", "validation_only", "superseded",
            }
            and model_item is not None
            and model_item.reason.strip()
        ):
            item.reason = model_item.reason.strip()
        excluded.append(item)
    return ReconciledAttribution(
        active_query_ids=active,
        visual_query_ids=visual,
        excluded_queries=excluded,
        invalid_query_ids=invalid,
        fallback_used=fallback_used,
    )


__all__ = ["ReconciledAttribution", "reconcile_query_attribution"]
