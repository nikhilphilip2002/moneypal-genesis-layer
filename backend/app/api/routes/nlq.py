"""Natural-language query API (§9).

`/nlq/execute` is deliberately LLM-free: it is what makes drill-downs instant, saved
questions reliable and dashboards buildable without a conversational endpoint.
"""

from __future__ import annotations

import logging


from fastapi import APIRouter, Header, HTTPException, Response
from pydantic import BaseModel, Field

from app.services.nlq import db as nlq_db
from app.services.nlq.catalog import get_catalog
from app.services.nlq.compiler import CompileError
from app.services.nlq.contracts import ChartSpec, Filter, QuerySpec, Worklist
from app.services.nlq.executor import ExecutionError
from app.services.nlq.llm import get_llm_client
from app.services.nlq.pipeline import run_spec
from app.services import signals, worklists
from app.services.worklists import store as worklist_store

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/nlq", tags=["nlq"])


@router.get("/health")
async def health():
    """Drives the ask bar's offline state.

    Always 200 — a degraded LLM is a product state, not an error. The frontend disables
    free-text asking when `llm.status != "ok"` while saved QuerySpecs keep running, which
    is only possible because `/nlq/execute` has no LLM dependency.
    """
    llm = await get_llm_client().health()
    database = nlq_db.health()
    try:
        catalog = get_catalog()
        catalog_state = {
            "version": catalog.version,
            "metrics": len(catalog.metrics),
            "dimensions": len(catalog.dimensions),
            "status": "ok",
        }
    except Exception as exc:  # noqa: BLE001 - health must always answer
        logger.exception("NLQ catalog failed to load")
        catalog_state = {"status": "error", "detail": str(exc)[:300]}

    degraded = (
        llm.get("status") != "ok"
        or database.get("status") != "ok"
        or catalog_state["status"] != "ok"
    )
    return {
        "status": "degraded" if degraded else "ok",
        "llm": llm,
        "db": database,
        "catalog": catalog_state,
        "capabilities": {
            "execute": database.get("status") == "ok" and catalog_state["status"] == "ok",
        },
    }


@router.get("/catalog")
def catalog_summary():
    """Powers autocomplete and the example-question chips.

    Exposes labels, units and formulas — never the underlying column names, which are
    meaningless to a user and would leak schema.
    """
    catalog = get_catalog()
    return {
        "version": catalog.version,
        "metrics": [
            {
                "id": m.id,
                "label": m.label,
                "unit": m.unit,
                "grain": m.grain,
                "formula": m.formula,
                "synonyms": list(m.synonyms),
                "requires_signoff": m.requires_signoff,
                "caveat": " ".join(m.caveat.split()) if m.caveat else "",
            }
            for m in catalog.metrics.values()
        ],
        "dimensions": [
            {
                "id": d.id,
                "label": d.label,
                "type": d.type,
                "synonyms": list(d.synonyms),
                "cardinality": d.cardinality,
            }
            for d in catalog.dimensions.values()
        ],
        "example_questions": EXAMPLE_QUESTIONS,
    }


class ExecuteRequest(BaseModel):
    query_spec: QuerySpec


@router.post("/execute", response_model=ChartSpec)
def execute_spec(req: ExecuteRequest) -> ChartSpec:
    """Run a QuerySpec and return a rendered chart. No LLM involved."""
    try:
        return run_spec(req.query_spec)
    except CompileError as exc:
        # 422: the spec is structurally valid but semantically refused (wrong grain,
        # undeclared join). The message is written for the user.
        raise HTTPException(422, str(exc)) from exc
    except ExecutionError as exc:
        logger.error("NLQ execution failed: %s", exc.detail)
        raise HTTPException(503, str(exc)) from exc


# --------------------------------------------------------------------------------------
# Worklists — generating, saving, working and exporting a list of accounts
# --------------------------------------------------------------------------------------


class WorklistRequest(BaseModel):
    worklist_id: str
    filters: list[Filter] = Field(default_factory=list)
    limit: int | None = Field(default=None, ge=1, le=200)
    save: bool = Field(
        default=False,
        description="Freeze this list so it can be assigned and worked. A generated list is "
        "a view; a saved one is a record, and re-running the rules tomorrow would silently "
        "drop an account someone already called.",
    )


@router.post("/worklist", response_model=Worklist)
def generate_worklist(req: WorklistRequest, authorization: str | None = Header(default=None)):
    """Run a worklist preset. No LLM involved — the rules and the score are catalog config."""
    user, role = _identity(authorization)
    try:
        result = worklists.build(
            req.worklist_id, filters=list(req.filters), limit=req.limit, role=role
        )
    except worklists.WorklistError as exc:
        raise HTTPException(422, str(exc)) from exc
    except ExecutionError as exc:
        logger.error("worklist execution failed: %s", exc.detail)
        raise HTTPException(503, str(exc)) from exc

    if req.save:
        saved = worklist_store.save(result, owner=user)
        result.id = saved.worklist_id
    return result


@router.get("/worklists")
def list_worklists(authorization: str | None = Header(default=None)):
    """The presets available, and the lists already being worked."""
    user, _role = _identity(authorization)
    catalog = get_catalog()
    return {
        "presets": [
            {
                "id": preset.id,
                "title": preset.title,
                "description": preset.description,
                "rules": [catalog.worklists.rules[r].label for r in preset.rules
                          if r in catalog.worklists.rules],
            }
            for preset in catalog.worklists.presets.values()
        ],
        "saved": [
            {
                "worklist_id": s.worklist_id,
                "preset_id": s.preset_id,
                "title": s.title,
                "created_at": s.created_at,
                "item_count": s.item_count,
                "open_count": s.open_count,
            }
            for s in worklist_store.list_recent(owner=user)
        ],
        # Named on the API as well as the card: a consumer building a dashboard on this
        # should know which signals are absent rather than infer completeness from silence.
        "unavailable": [
            {"rule": entry.get("rule", ""), "needs": entry.get("needs", "")}
            for entry in catalog.worklists.unavailable
        ],
    }


class WorklistStatusRequest(BaseModel):
    account: str
    status: str
    note: str = ""
    assigned_to: str = ""


@router.post("/worklists/{worklist_id}/status")
def set_worklist_status(
    worklist_id: str,
    req: WorklistStatusRequest,
    authorization: str | None = Header(default=None),
):
    """Record what a person did about one account. Only a person calls this — nothing in
    the product infers that an account was contacted."""
    user, _role = _identity(authorization)
    try:
        saved = worklist_store.set_status(
            worklist_id, req.account, req.status,
            owner=user, note=req.note, assigned_to=req.assigned_to,
        )
    except worklist_store.WorklistStoreError as exc:
        raise HTTPException(404, str(exc)) from exc
    return {"worklist_id": saved.worklist_id, "statuses": saved.statuses}


@router.get("/worklists/{worklist_id}/export")
def export_worklist(worklist_id: str, authorization: str | None = Header(default=None)):
    """The saved list as CSV, because that is how it reaches a branch.

    Re-exports the frozen snapshot rather than re-running the rules: a list half-worked
    since this morning must export as the list that was worked.
    """
    user, _role = _identity(authorization)
    saved = worklist_store.get(worklist_id, owner=user)
    if saved is None:
        raise HTTPException(404, "Unknown worklist.")
    return Response(
        content=worklists.to_csv(saved.worklist),
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="{saved.preset_id}-{worklist_id[:8]}.csv"'
        },
    )


# --------------------------------------------------------------------------------------
# Signals and the morning briefing
# --------------------------------------------------------------------------------------


@router.get("/signals")
def list_signals(
    scope: str | None = None,
    severity: str | None = None,
    limit: int = 20,
):
    """The findings the scan has already made. Retrieval, not analysis.

    Deliberately not a "run the scan now" endpoint: a scan on demand would take seconds,
    hold read-only connections a user is waiting on, and return the same thing the scheduled
    one already stored.
    """
    catalog = get_catalog()
    stored = signals.open_signals(
        scopes=[scope] if scope else None,
        severities=[severity] if severity else None,
        limit=min(limit, 100),
    )
    return {
        "signals": [
            {
                **item.signal.model_dump(mode="json"),
                "status": item.status,
                "first_seen_at": item.first_seen_at,
                "last_seen_at": item.last_seen_at,
                "standing": item.is_standing,
            }
            for item in stored
        ],
        "scopes": [
            {"id": s.id, "label": s.label, "metric": s.metric, "why": s.why}
            for s in catalog.signals.scopes.values()
        ],
        # Named rather than implied. A reader who does not know variance-to-plan is missing
        # will read an empty feed as a clean book.
        "unavailable": [
            {"detector": entry.get("detector", ""), "needs": entry.get("needs", "")}
            for entry in catalog.signals.unavailable
        ],
    }


class SignalStatusRequest(BaseModel):
    status: str = Field(pattern="^(open|acknowledged|resolved)$")


@router.post("/signals/{fingerprint}/status")
def set_signal_status(
    fingerprint: str,
    req: SignalStatusRequest,
    authorization: str | None = Header(default=None),
):
    """Acknowledge or resolve one finding.

    Acknowledging says "I have seen this", not "this is fixed" — acknowledged signals stay in
    the feed, because a standing deterioration must not disappear by being read.
    """
    user, _role = _identity(authorization)
    try:
        stored = signals.set_status(fingerprint, req.status, user=user)
    except signals.SignalStoreError as exc:
        raise HTTPException(404, str(exc)) from exc
    return {"fingerprint": fingerprint, "status": stored.status}


@router.get("/personas")
def list_personas():
    """The desks a briefing can be prepared for.

    A persona reorders and preselects. It never changes a metric, a threshold or a filter —
    PAR 30 is PAR 30 at every desk, and a persona that redefined one would give two people
    different answers to the same question with no way to discover why.
    """
    catalog = get_catalog()
    return {
        "personas": [
            {
                "id": p.id,
                "label": p.label,
                "description": p.description,
                "default_period": p.default_period,
                "analyses": list(p.analyses),
                "worklists": list(p.worklists),
            }
            for p in catalog.personas.values()
        ]
    }


@router.get("/briefing/{persona_id}")
def get_briefing(
    persona_id: str,
    include_worklists: bool = True,
    authorization: str | None = Header(default=None),
):
    """One desk's morning read: what is notable, where the book stands, who to call."""
    _user, role = _identity(authorization)
    try:
        return signals.briefing(persona_id, role=role, include_worklists=include_worklists)
    except signals.BriefingError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ExecutionError as exc:
        logger.error("briefing failed: %s", exc.detail)
        raise HTTPException(503, str(exc)) from exc


EXAMPLE_QUESTIONS = [
    "What was our disbursement by branch last quarter?",
    "Show collection efficiency by product this financial year",
    "What is PAR 30 right now?",
    "How many loans did we sanction each month in FY26?",
    "Which schemes have the largest outstanding?",
    "Break down the portfolio by DPD bucket",
]
