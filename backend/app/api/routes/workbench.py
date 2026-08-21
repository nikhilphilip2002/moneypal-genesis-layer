"""Workbench API — one unified chat that routes to every intelligence source.

`/workbench/ask` streams SSE frames: understanding, routing, route, source_start,
source_card, synthesis, refusal, error, done. The card frames carry a `card_type` the
frontend maps to a renderer (chart, brief, clarify, refusal).
"""

from __future__ import annotations

import logging
import uuid
from typing import Literal

from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.services.workbench import history, models, tools
from app.services.workbench.graph import run_workbench
from app.services.workbench.sources import visible_sources
from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/workbench", tags=["workbench"])


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


@router.get("/sources")
def sources(authorization: str | None = Header(default=None)):
    """The sources this role can reach — drives the '+' pin-source menu and the mode badge."""
    _, role = _identity(authorization)
    return {
        "mode": models.active_mode(),
        "data_access": settings.postgres_access_mode,
        "sources": [
            {"id": s.id, "label": s.label, "describes": s.describes, "sensitive": s.sensitive}
            for s in visible_sources(role)
        ],
    }


@router.get("/conversations")
def list_conversations(limit: int = 50, authorization: str | None = Header(default=None)):
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
def get_conversation(conversation_id: str, authorization: str | None = Header(default=None)):
    username, _ = _identity(authorization)
    rec = history.get(conversation_id, user=username)
    if rec is None:
        raise HTTPException(404, "Unknown conversation.")
    return {
        "conversation_id": rec.conversation_id,
        "title": rec.title,
        "updated_at": rec.updated_at.isoformat(),
        "record_version": rec.record_version,
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
        "legacy_answer_unavailable": legacy,
    }


@router.get("/tools")
def list_tools(authorization: str | None = Header(default=None)):
    """Tools this role may run — populates the '+' menu."""
    _, role = _identity(authorization)
    return {
        "tools": [
            {"id": t.id, "label": t.label, "description": t.description,
             "kind": t.kind, "params": t.params}
            for t in tools.visible_tools(role)
        ],
    }


class ToolRequest(BaseModel):
    params: dict = Field(default_factory=dict)


@router.post("/tool/{tool_id}")
async def run_tool(tool_id: str, req: ToolRequest | None = None,
                   authorization: str | None = Header(default=None)):
    """Run a '+' tool. Access is enforced here, not just hidden in the menu."""
    _, role = _identity(authorization)
    params = req.params if req else {}
    try:
        result = await tools.run_tool(tool_id, role=role, params=params)
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
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
