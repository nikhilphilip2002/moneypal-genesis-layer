"""Reusable governed execution services shared by legacy NLQ and native tools.

Planning, streaming, audit, and response rendering remain with their callers. This module
owns the non-streaming execution boundary so identical reviewed plans have identical data,
masking, chart, lineage, worklist, analysis, and briefing behavior.
"""

from __future__ import annotations

from datetime import date

from app.services.nlq import analysis, lookup
from app.services.nlq.catalog import Catalog
from app.services.nlq.contracts import Filter, LookupPlan, Period, QuerySpec
from app.services.nlq.pipeline import run_spec


def metrics(
    spec: QuerySpec, *, catalog: Catalog | None, today: date | None, role: str,
):
    return run_spec(spec, catalog=catalog, today=today, role=role)


def records(plan: LookupPlan, *, catalog: Catalog | None, role: str):
    return lookup.run(plan, role=role, catalog=catalog)


def reviewed_analysis(
    analysis_id: str,
    *,
    catalog: Catalog | None,
    period: Period | None,
    filters: list[Filter],
    today: date | None,
    role: str,
):
    spec = analysis.build(analysis_id, catalog=catalog, period=period, filters=filters)
    return analysis.run(spec, catalog=catalog, today=today, role=role)


def reviewed_worklist(
    worklist_id: str,
    *,
    catalog: Catalog | None,
    as_of: date | None,
    filters: list[Filter],
    limit: int | None,
    role: str,
):
    from app.services import worklists

    return worklists.build(
        worklist_id,
        catalog=catalog,
        as_of=as_of,
        filters=filters,
        limit=limit,
        role=role,
    )


def reviewed_briefing(
    persona_id: str, *, catalog: Catalog | None, today: date | None, role: str,
):
    from app.services import signals

    return signals.briefing(persona_id, catalog=catalog, today=today, role=role)


__all__ = [
    "metrics",
    "records",
    "reviewed_analysis",
    "reviewed_briefing",
    "reviewed_worklist",
]
