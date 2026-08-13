"""The orchestrator: rewrite -> route -> dispatch -> synthesize, as a LangGraph.

Why a graph and not a straight function: the dispatch step fans out to N sources and, for
multi-source questions, a synthesis step runs only after they all return. Expressing that
as an explicit state machine keeps the control flow legible and leaves a clean place to add
nodes (competitive, regulatory, attachments) without reworking the sequence.

Streaming: LangGraph drives the DAG while nodes push SSE frames onto an asyncio.Queue as
soon as they have something to show. The endpoint drains the queue, so per-source cards
appear the moment each source finishes rather than after the whole graph completes.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, AsyncIterator, NotRequired, TypedDict

from langgraph.graph import END, START, StateGraph

from app.services.workbench import history, models, nodes, router
from app.services.workbench.nodes import SourceResult

logger = logging.getLogger(__name__)


def sse(event: str, data: Any) -> str:
    return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"


class WorkbenchState(TypedDict):
    question: str
    conversation_id: str
    user: str
    role: str
    emit: "asyncio.Queue[str | None]"
    pinned: NotRequired[str | None]
    data_access: NotRequired[str | None]
    decision: NotRequired[router.RouteDecision]
    results: NotRequired[list[SourceResult]]


async def _route_node(state: WorkbenchState) -> dict[str, Any]:
    emit = state["emit"]
    await emit.put(sse("stage", {"stage": "routing"}))
    decision = await router.route(
        state["question"], role=state["role"], pinned=state.get("pinned"),
    )
    if decision.route == "dispatch":
        await emit.put(sse("route", {"sources": decision.sources, "intent": decision.intent,
                                     "model": decision.model}))
    # Record the turn for the History rail. Best-effort: a history failure must never break
    # the answer, so it is swallowed here.
    try:
        chosen = decision.sources if decision.route == "dispatch" else []
        history.record_turn(state["conversation_id"], state["question"], chosen)
    except Exception:  # noqa: BLE001
        logger.warning("workbench history record failed", exc_info=True)
    return {"decision": decision}


async def _h_db(intent: str, state: WorkbenchState) -> SourceResult:
    # The router may paraphrase `intent` while selecting sources. Never send that rewrite
    # into governed NLQ: borrower names, account identifiers, periods, and distinctions
    # such as principal vs interest must remain byte-for-byte as the user supplied them.
    return await nodes.run_db(
        state["question"],
        conversation_id=state["conversation_id"], user=state["user"], role=state["role"],
        access_mode=state.get("data_access"),
    )


async def _h_macro(intent: str, _state: WorkbenchState) -> SourceResult:
    return await nodes.run_macro(intent)


async def _h_competitive(intent: str, _state: WorkbenchState) -> SourceResult:
    return await nodes.run_competitive(intent)


async def _h_regulatory(intent: str, _state: WorkbenchState) -> SourceResult:
    return await nodes.run_regulatory(intent)


async def _h_schema(intent: str, _state: WorkbenchState) -> SourceResult:
    return await nodes.run_schema(intent, access_mode=_state.get("data_access"))


# source id -> handler. Adding a source is a new entry here plus a catalog entry — the
# dispatch node itself never changes.
_HANDLERS = {
    "db": _h_db,
    "macro": _h_macro,
    "competitive": _h_competitive,
    "regulatory": _h_regulatory,
    "schema": _h_schema,
}


async def _dispatch_node(state: WorkbenchState) -> dict[str, Any]:
    emit = state["emit"]
    decision = state.get("decision") or router.RouteDecision(route="refuse", reason="out_of_scope")

    if decision.route == "refuse":
        await emit.put(sse("refusal", {"route": "refuse", "reason": decision.reason,
                                       "message": decision.message}))
        return {"results": []}

    async def run_one(source_id: str) -> SourceResult:
        await emit.put(sse("source_start", {"source": source_id}))
        handler = _HANDLERS.get(source_id)
        if handler is None:
            result = SourceResult(source=source_id, card_type="error",
                                  payload={"message": f"Unknown source {source_id}."})
        else:
            try:
                result = await handler(decision.intent, state)
            except Exception as exc:  # noqa: BLE001 - isolate unavailable dependencies
                logger.exception("workbench source %s failed", source_id)
                result = SourceResult(
                    source=source_id,
                    card_type="error",
                    payload={
                        "message": f"{source_id.title()} intelligence is temporarily unavailable.",
                        "retryable": True,
                    },
                )
        await emit.put(sse("source_card", {
            "source": result.source, "card_type": result.card_type, **result.payload,
        }))
        return result

    # Fan out. Results stream as each finishes; the ordered list is kept for synthesis.
    results = await asyncio.gather(*(run_one(s) for s in decision.sources))
    return {"results": list(results)}


_SYNTH_SYSTEM = (
    "You are briefing a bank director. Write 2-3 sentences that tie together the findings "
    "below into one answer to their question. Use ONLY the facts and figures given — never "
    "add or alter a number. If the findings do not fully answer the question, say what is "
    "missing in one clause."
)


async def _synthesize_node(state: WorkbenchState) -> dict[str, Any]:
    emit = state["emit"]
    results = [
        r for r in state.get("results", [])
        if r.card_type in ("chart", "brief") and r.summary.strip()
    ]
    # Only worth a merged lead when more than one source actually contributed.
    if len(results) < 2:
        return {}

    findings = "\n".join(f"- [{r.source}] {r.summary}" for r in results if r.summary)
    client = models.for_step("synthesize", sensitive=any(r.source == "db" for r in results))
    try:
        result = await client.complete(
            messages=[
                {"role": "system", "content": _SYNTH_SYSTEM},
                {"role": "user", "content": f"Question: {state['question']}\n\nFindings:\n{findings}"},
            ],
            max_tokens=300,
            temperature=0.2,
        )
        await emit.put(sse("synthesis", {"text": result.text.strip()}))
    except Exception as exc:  # noqa: BLE001 - synthesis is a nicety; cards already streamed
        logger.warning("workbench synthesis failed: %s", exc)
    return {}


def _build_graph():
    graph = StateGraph(WorkbenchState)
    graph.add_node("route", _route_node)
    graph.add_node("dispatch", _dispatch_node)
    graph.add_node("synthesize", _synthesize_node)
    graph.add_edge(START, "route")
    graph.add_edge("route", "dispatch")
    graph.add_edge("dispatch", "synthesize")
    graph.add_edge("synthesize", END)
    return graph.compile()


_COMPILED = None


def _compiled():
    global _COMPILED
    if _COMPILED is None:
        _COMPILED = _build_graph()
    return _COMPILED


async def run_workbench(
    *, question: str, conversation_id: str, user: str, role: str, pinned: str | None = None,
    data_access: str | None = None,
) -> AsyncIterator[str]:
    """Run one turn, yielding SSE frames as the graph produces them."""
    emit: "asyncio.Queue[str | None]" = asyncio.Queue()
    # Announce the conversation id first so the client can thread follow-ups and the History
    # rail onto it.
    yield sse("conversation", {"conversation_id": conversation_id})
    yield sse("stage", {"stage": "understanding"})

    state: WorkbenchState = {
        "question": question, "conversation_id": conversation_id,
        "user": user, "role": role, "emit": emit, "pinned": pinned,
        "data_access": data_access,
    }

    async def drive() -> None:
        try:
            await _compiled().ainvoke(state)
        except Exception:  # noqa: BLE001 - surface as an error frame, never a 500
            logger.exception("workbench graph failed")
            await emit.put(sse("error", {"message": "The workbench hit an error.",
                                         "retryable": True}))
        finally:
            await emit.put(None)  # sentinel: the graph is done producing frames

    task = asyncio.create_task(drive())
    try:
        while True:
            frame = await emit.get()
            if frame is None:
                break
            yield frame
    finally:
        if not task.done():
            task.cancel()
    yield sse("done", {})
