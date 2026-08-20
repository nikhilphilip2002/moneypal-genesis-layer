"""Natural-language query API (§9).

`/nlq/execute` is deliberately LLM-free: it is what makes drill-downs instant, saved
questions reliable, and dashboards buildable on the same engine. `/nlq/ask` adds the
language layer on top of it.
"""

from __future__ import annotations

import logging

import uuid

from fastapi import APIRouter, Header, HTTPException, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.services.nlq import audit, conversation
from app.services.nlq import db as nlq_db
from app.services.nlq.ask import AskContext, ask_stream
from app.services.nlq.catalog import get_catalog
from app.services.nlq.compiler import CompileError
from app.services.nlq.contracts import ChartSpec, Filter, QuerySpec, Worklist
from app.services.nlq.executor import ExecutionError
from app.services.nlq.llm import get_llm_client
from app.services.nlq.pipeline import run_spec
from app.services.nlq.ratelimit import RateLimitExceeded, check_rate_limit
from app.services import worklists
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
            "ask": llm.get("status") == "ok" and database.get("status") == "ok",
            "text_to_sql": False,  # Phase 3
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


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1000)
    conversation_id: str | None = None


def _identity(authorization: str | None) -> tuple[str, str]:
    """Extract (user, role) from the mock token.

    Mock auth is what exists today (auth.py:13). Every PII decision downstream is only as
    strong as this, which is why §7.4 makes replacing it a go-live blocker rather than a
    nice-to-have.
    """
    from app.api.routes.auth import USERS

    token = (authorization or "").removeprefix("Bearer ").strip()
    username = token.removeprefix("mock-token-") if token.startswith("mock-token-") else ""
    user = USERS.get(username)
    return (username or "anonymous", user["role"] if user else "anonymous")


@router.post("/ask")
async def ask(req: AskRequest, authorization: str | None = Header(default=None)):
    """Ask a question in English. Streams SSE stages: stage, plan, chart|clarify|refusal, done."""
    username, role = _identity(authorization)
    try:
        check_rate_limit(username)
    except RateLimitExceeded as exc:
        raise HTTPException(429, str(exc), headers={"Retry-After": str(exc.retry_after)}) from exc

    ctx = AskContext(
        question=req.question,
        conversation_id=req.conversation_id or uuid.uuid4().hex[:12],
        user=username,
        role=role,
    )
    return StreamingResponse(
        ask_stream(ctx),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # nginx must not buffer the stage events away
        },
    )


@router.get("/conversations/{conversation_id}")
def get_conversation(conversation_id: str):
    state = conversation.load(conversation_id)
    return {
        "conversation_id": conversation_id,
        "turns": [t.model_dump(mode="json") for t in state.turns],
        "active_spec": state.active_spec.model_dump(mode="json") if state.active_spec else None,
        "sticky_filters": conversation.sticky_filters(state),
    }


@router.delete("/conversations/{conversation_id}", status_code=204)
def clear_conversation(conversation_id: str):
    conversation.clear(conversation_id)


class FeedbackRequest(BaseModel):
    turn_id: str
    verdict: str = Field(pattern="^(up|down)$")
    comment: str = ""


@router.post("/feedback")
def submit_feedback(req: FeedbackRequest):
    """Every thumbs-down becomes a golden-set case — this is the catalog backlog."""
    recorded = audit.record_feedback(req.turn_id, req.verdict, req.comment)
    if not recorded:
        raise HTTPException(404, "Unknown turn, or the audit log is unavailable.")
    return {"recorded": True}


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


@router.get("/suggestions")
def suggestions(conversation_id: str | None = None):
    """Next questions to offer. Context-aware when there is an anchor to build on."""
    catalog = get_catalog()
    if conversation_id:
        state = conversation.load(conversation_id)
        if state.active_spec:
            metric = catalog.metrics.get(state.active_spec.metrics[0])
            current = set(state.active_spec.dimensions)
            follow_ups = [
                f"and by {catalog.dimensions[d].label.lower()}?"
                for d in ("branch", "product", "scheme", "month")
                if d not in current and d in catalog.dimensions
            ][:3]
            if metric:
                return {"suggestions": follow_ups, "based_on": metric.label}
    return {"suggestions": EXAMPLE_QUESTIONS[:4], "based_on": None}


EXAMPLE_QUESTIONS = [
    "What was our disbursement by branch last quarter?",
    "Show collection efficiency by product this financial year",
    "What is PAR 30 right now?",
    "How many loans did we sanction each month in FY26?",
    "Which schemes have the largest outstanding?",
    "Break down the portfolio by DPD bucket",
]
