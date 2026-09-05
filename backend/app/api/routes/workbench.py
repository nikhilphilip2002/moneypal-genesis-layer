"""Workbench API — one unified chat that routes to every intelligence source.

`/workbench/ask` streams SSE frames: understanding, routing, route, source_start,
source_card, synthesis, refusal, error, done. The card frames carry a `card_type` the
frontend maps to a renderer (chart, brief, clarify, refusal).
"""

from __future__ import annotations

import asyncio
import logging
import re
import threading
import time
import uuid
from typing import Literal

from fastapi import APIRouter, Header, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.services.workbench import access, history, models, tools
from app.services.workbench.graph import run_workbench
from app.services.workbench.sources import visible_sources
from app.services.nlq import lookup as record_lookup
from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/workbench", tags=["workbench"])

COMPLETION_DB_RETRY_S = 10.0
_completion_db_retry_after = 0.0
_completion_in_flight = False
_COMPLETION_INTENT_CUES = re.compile(
    r"\b(?:show|give|what|which|how|explain|compare|list|find|search|latest|total|top|"
    r"bottom|loan|repay|sanction|disburse|collect|outstanding|principal|interest|amount|"
    r"balance|portfolio|branch|product|scheme|macro|regulat|competitor)\w*\b",
    re.IGNORECASE,
)


def _completion_query_allowed(q: str, kind: str) -> bool:
    """Accept explicit entity lookups; reject ordinary question prose for `kind=all`."""
    text = " ".join(q.split()).strip()
    if len(text) < 2:
        return False
    if kind != "all":
        return True
    if _COMPLETION_INTENT_CUES.search(text):
        return False
    words = text.split()
    return len(words) == 1 or all(word[:1].isupper() for word in words)


async def _completion_results(q: str, kind: str) -> list[dict]:
    """Run optional synchronous SQL without blocking the API event loop.

    A dedicated daemon thread avoids coupling application shutdown to a stuck completion
    query. The in-flight gate is released by the worker callback, even if the HTTP client
    disconnects before the query finishes.
    """
    global _completion_db_retry_after, _completion_in_flight

    loop = asyncio.get_running_loop()
    future: asyncio.Future[list[dict]] = loop.create_future()

    def deliver(results: list[dict] | None, error: BaseException | None) -> None:
        global _completion_db_retry_after, _completion_in_flight

        _completion_in_flight = False
        if error is not None:
            _completion_db_retry_after = time.monotonic() + COMPLETION_DB_RETRY_S
            logger.warning(
                "Workbench completion lookup unavailable; suppressing retries for %.0fs: %s",
                COMPLETION_DB_RETRY_S,
                error,
            )
        if future.done():
            return
        if error is not None:
            future.set_exception(error)
        else:
            future.set_result(results or [])

    def query() -> None:
        try:
            results = record_lookup.completions(q, kind)
        except BaseException as exc:  # noqa: BLE001 - carried back to the event loop
            loop.call_soon_threadsafe(deliver, None, exc)
        else:
            loop.call_soon_threadsafe(deliver, results, None)

    threading.Thread(target=query, name="workbench-completion", daemon=True).start()
    return await future


def _identity(authorization: str | None) -> tuple[str, str]:
    """(user, role) from the mock token — same scheme as the NLQ route."""
    from app.api.routes.auth import USERS

    token = (authorization or "").removeprefix("Bearer ").strip()
    username = token.removeprefix("mock-token-") if token.startswith("mock-token-") else ""
    user = USERS.get(username)
    return (username or "anonymous", user["role"] if user else "anonymous")


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    conversation_id: str | None = None
    # "+" -> Pin a source. A deterministic override; the router validates it against the
    # role's visible set, so it can never widen access.
    pinned_source: str | None = None
    data_access: Literal["direct", "mcp"] | None = None
    external_sources_enabled: bool = False


@router.get("/sources")
async def sources(authorization: str | None = Header(default=None)):
    """The sources this role can reach — drives the '+' pin-source menu and the mode badge."""
    _, role = _identity(authorization)
    return {
        "mode": models.active_mode(),
        "data_access": settings.postgres_access_mode,
        "sources": access.source_metadata(role),
    }


@router.get("/conversations")
async def list_conversations(limit: int = 50, authorization: str | None = Header(default=None)):
    """Recent conversations for the History rail, most-recent first."""
    username, _ = _identity(authorization)
    return {
        "conversations": [
            {"conversation_id": c.conversation_id, "title": c.title,
             "updated_at": c.updated_at.isoformat(), "turn_count": c.turn_count}
            for c in history.list_recent(limit=limit, user=username)
        ],
    }


@router.get("/conversations/{conversation_id}")
async def get_conversation(conversation_id: str, authorization: str | None = Header(default=None)):
    username, _ = _identity(authorization)
    rec = history.get(conversation_id, user=username)
    if rec is None:
        raise HTTPException(404, "Unknown conversation.")
    return {
        "conversation_id": rec.conversation_id,
        "title": rec.title,
        "updated_at": rec.updated_at.isoformat(),
        "record_version": rec.record_version,
        "external_sources_enabled": rec.external_sources_enabled,
        "turns": [_turn_for_api(turn) for turn in rec.turns],
    }


def _turn_for_api(turn: dict) -> dict:
    """Normalize version-1 question/source stubs into the renderable v2 contract."""
    question = str(turn.get("question", ""))
    sources = list(turn.get("sources", []) or [])
    route = turn.get("route") or {"sources": sources, "intent": question, "model": "legacy"}
    legacy = "cards" not in turn
    return {
        "id": turn.get("id") or f"legacy-{abs(hash((question, turn.get('at', ''))))}",
        "question": question,
        "route": route,
        "sources": sources,
        "cards": list(turn.get("cards", []) or []),
        "answer": turn.get("answer") or (
            {"status": "answered", "text": turn.get("synthesis"), "sources": sources,
             "citations": [], "unavailable_sources": []}
            if turn.get("synthesis") else None
        ),
        "synthesis": turn.get("synthesis"),
        "refusal": turn.get("refusal"),
        "error": turn.get("error"),
        "status": turn.get("status", "complete"),
        "created_at": turn.get("created_at") or turn.get("at"),
        "completed_at": turn.get("completed_at"),
        "usage": turn.get("usage"),
        "timing": turn.get("timing"),
        "source_policy": turn.get("source_policy") or {
            "version": "legacy",
            "external_sources_enabled": False,
            "effective_sources": sources,
        },
        "legacy_answer_unavailable": legacy,
    }


@router.get("/tools")
async def list_tools(authorization: str | None = Header(default=None)):
    """Tools this role may run — populates the '+' menu."""
    _, role = _identity(authorization)
    return {
        "tools": [
            {"id": t.id, "label": t.label, "description": t.description,
             "kind": t.kind, "params": t.params, "source_id": t.source_id}
            for t in tools.visible_tools(role)
        ],
    }


@router.get("/completions")
async def chat_completions(
    q: str = Query(default="", max_length=100),
    kind: Literal["all", "borrower", "customer", "account", "agent"] = "all",
    authorization: str | None = Header(default=None),
):
    """Bounded borrower/account/agent suggestions for Tab completion in chat."""
    global _completion_db_retry_after, _completion_in_flight

    _username, role = _identity(authorization)
    if (
        "db" not in {source.id for source in visible_sources(role)}
        or not _completion_query_allowed(q, kind)
    ):
        return {"query": q, "kind": kind, "results": []}

    # Completion is optional UI assistance. Never let a dead database turn it into a
    # request storm or block the event loop while the user types. One request probes the
    # database; overlapping and cooldown-period requests degrade immediately to no hints.
    if time.monotonic() < _completion_db_retry_after or _completion_in_flight:
        return {"query": q, "kind": kind, "results": []}
    _completion_in_flight = True
    try:
        results = await _completion_results(q, kind)
    except Exception:  # noqa: BLE001 - optional suggestions fail closed
        results = []
    return {"query": q, "kind": kind, "results": results}


class ToolRequest(BaseModel):
    params: dict = Field(default_factory=dict)
    external_sources_enabled: bool = False


@router.post("/tool/{tool_id}")
async def run_tool(tool_id: str, req: ToolRequest | None = None,
                   authorization: str | None = Header(default=None)):
    """Run a '+' tool. Access is enforced here, not just hidden in the menu."""
    _, role = _identity(authorization)
    params = req.params if req else {}
    try:
        result = await tools.run_tool(
            tool_id, role=role, params=params,
            external_sources_enabled=bool(req and req.external_sources_enabled),
        )
    except tools.ToolNotFound as exc:
        raise HTTPException(404, f"Unknown tool: {tool_id}") from exc
    except tools.ToolAccessError as exc:
        raise HTTPException(403, "You do not have access to that tool.") from exc
    return {"source": result.source, "card_type": result.card_type, **result.payload}


@router.post("/ask")
async def ask(req: AskRequest, authorization: str | None = Header(default=None)):
    """Ask anything. The orchestrator picks the source(s) and streams cards back."""
    username, role = _identity(authorization)
    if (
        req.conversation_id
        and history.exists(req.conversation_id)
        and history.get(req.conversation_id, user=username) is None
    ):
        # Do not reveal whose conversation it is or permit a caller to take it over by
        # posting the same id.
        raise HTTPException(404, "Unknown conversation.")
    conversation_id = req.conversation_id or uuid.uuid4().hex[:12]
    return StreamingResponse(
        run_workbench(
            question=req.question,
            conversation_id=conversation_id,
            user=username,
            role=role,
            pinned=req.pinned_source,
            data_access=req.data_access,
            external_sources_enabled=req.external_sources_enabled,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
