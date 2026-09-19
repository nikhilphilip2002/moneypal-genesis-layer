from __future__ import annotations

import asyncio
import json
import time

import pytest

from app.api.routes.workbench import _turn_for_api
from app.services.nlq.llm import NativeToolCall
from app.services.workbench import agent, history
from app.services.workbench.agent_executor import ExecutedAgentCall
from app.services.workbench.results import SourceResult


def _sse_payload(frame: str) -> tuple[str, dict]:
    lines = frame.strip().splitlines()
    event = lines[0].removeprefix("event: ")
    payload = json.loads(lines[1].removeprefix("data: "))
    return event, payload


def test_query_ids_distinguish_retry_attempts_from_corrected_sql(monkeypatch):
    from app.mcp import postgres_client

    monkeypatch.setattr(postgres_client, "is_model_tool", lambda name: name == "query")
    state = {"turn_id": "turn-retry", "query_registry": []}
    original = NativeToolCall(id="call-1", name="query", arguments={"sql": "SELECT 1"})
    first = agent._register_database_queries(state, [original])["call-1"]
    first["status"] = "timeout"

    retry = NativeToolCall(id="call-2", name="query", arguments={"sql": "SELECT 1"})
    second = agent._register_database_queries(state, [retry])["call-2"]
    second["status"] = "success"
    corrected = NativeToolCall(id="call-3", name="query", arguments={"sql": "SELECT 2"})
    third = agent._register_database_queries(state, [corrected])["call-3"]

    assert first["query_id"] == second["query_id"] == "turn-retry:q1"
    assert first["attempt_id"] == "turn-retry:q1:a1"
    assert second["attempt_id"] == "turn-retry:q1:a2"
    assert third["query_id"] == "turn-retry:q2"
    assert third["attempt_id"] == "turn-retry:q2:a1"


def test_visualization_call_gets_current_turn_derived_id(monkeypatch):
    from app.mcp import postgres_client

    monkeypatch.setattr(postgres_client, "is_model_tool", lambda _name: False)
    state = {"turn_id": "turn-visual", "query_registry": []}
    call = NativeToolCall(
        id="visual-call", name="visualize_query_result",
        arguments={
            "query_id": "older:q1", "chart_type": "bar", "x": "scheme",
            "y": ["amount"], "series": None, "aggregation": "none",
        },
    )

    record = agent._register_database_queries(state, [call])["visual-call"]

    assert record["query_id"] == "turn-visual:v1"
    assert record["attempt_id"] == "turn-visual:v1:a1"
    assert record["source_query_id"] == "older:q1"


@pytest.mark.anyio
async def test_tool_trace_streams_running_then_completed_with_arguments(monkeypatch):
    call = NativeToolCall(id="call-1", name="query", arguments={"sql": "SELECT 1"})

    async def execute(_call, _context):
        return ExecutedAgentCall(
            call=_call,
            card=SourceResult(
                source="db", card_type="chart", payload={"rows": [{"value": 1}]},
                summary="Returned one row.",
            ),
        )

    monkeypatch.setattr(agent, "execute_agent_call", execute)
    monkeypatch.setattr(agent, "get_agent_tool", lambda _name: type("Tool", (), {"parallel_safe": False})())
    from app.mcp import postgres_client
    monkeypatch.setattr(postgres_client, "is_model_tool", lambda name: name == "query")

    state = {
        "emit": asyncio.Queue(), "trace": [], "turn_id": "turn-1",
        "timing": {
            "started_at": time.perf_counter(), "source_attempts": [],
            "source_completions": [],
        },
    }
    items = await agent._execute_batch(state, object(), [call])

    frames = []
    while not state["emit"].empty():
        frames.append(_sse_payload(state["emit"].get_nowait()))
    trace = [payload for event, payload in frames if event == "trace"]
    assert [step["status"] for step in trace] == ["running", "complete"]
    assert trace[0]["arguments"] == {"sql": "SELECT 1"}
    assert trace[1]["detail"] == "Returned one row."
    assert trace[1]["duration_ms"] >= 0
    assert items[0].duration_ms >= 0
    assert items[0].query_id == "turn-1:q1"
    lifecycle = [(event, payload) for event, payload in frames if event.startswith("query_")]
    assert [event for event, _payload in lifecycle] == [
        "query_registered", "query_started", "query_completed",
    ]
    assert {payload["query_id"] for _event, payload in lifecycle} == {"turn-1:q1"}
    assert lifecycle[-1][1]["status"] == "success"
    source_card = next(payload for event, payload in frames if event == "source_card")
    assert source_card["query_id"] == "turn-1:q1"


@pytest.mark.anyio
async def test_cancelled_database_query_is_finalized_in_registry(monkeypatch):
    call = NativeToolCall(id="call-cancel", name="query", arguments={"sql": "SELECT 1"})
    entered = asyncio.Event()

    async def execute(_call, _context):
        entered.set()
        await asyncio.Event().wait()

    monkeypatch.setattr(agent, "execute_agent_call", execute)
    monkeypatch.setattr(
        agent, "get_agent_tool",
        lambda _name: type("Tool", (), {"parallel_safe": False})(),
    )
    from app.mcp import postgres_client
    monkeypatch.setattr(postgres_client, "is_model_tool", lambda name: name == "query")
    state = {
        "emit": asyncio.Queue(), "trace": [], "turn_id": "turn-cancel",
        "timing": {
            "started_at": time.perf_counter(), "source_attempts": [],
            "source_completions": [],
        },
    }

    task = asyncio.create_task(agent._execute_batch(state, object(), [call]))
    await entered.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert state["query_registry"][0]["status"] == "cancelled"
    frames = []
    while not state["emit"].empty():
        frames.append(_sse_payload(state["emit"].get_nowait()))
    failed = next(payload for event, payload in frames if event == "query_failed")
    assert failed["error_code"] == "CANCELLED"


def test_saved_conversation_returns_execution_trace(monkeypatch):
    history._MEMORY.clear()
    monkeypatch.setattr(history, "_ensure_table", lambda: False)
    turn_id = history.begin_turn("trace-conversation", "alice", "Show PAR 30")
    trace = [{
        "id": "model-1", "kind": "model", "status": "complete",
        "label": "Model deciding next action", "detail": "Selected 1 tool call(s)",
        "elapsed_ms": 12, "duration_ms": 10,
    }]
    history.set_execution_trace(
        "trace-conversation", "alice", turn_id, trace=trace,
    )

    record = history.get("trace-conversation", user="alice")
    assert record is not None
    assert _turn_for_api(record.turns[0])["execution_trace"] == trace


def test_saved_conversation_returns_query_registry(monkeypatch):
    history._MEMORY.clear()
    monkeypatch.setattr(history, "_ensure_table", lambda: False)
    turn_id = history.begin_turn("query-conversation", "alice", "Show PAR 30")
    registry = [{
        "query_id": f"{turn_id}:q1", "attempt_id": f"{turn_id}:q1:a1",
        "tool_call_id": "provider-call", "tool_name": "query", "status": "success",
        "purpose": "answer", "row_count": 1, "has_data": True,
        "visual_available": True, "duration_ms": 4, "error_code": None,
    }]
    history.set_query_registry(
        "query-conversation", "alice", turn_id, registry,
    )

    record = history.get("query-conversation", user="alice")
    assert record is not None
    assert _turn_for_api(record.turns[0])["query_registry"] == registry


def test_history_api_preserves_exact_reconciled_visual_partition(monkeypatch):
    history._MEMORY.clear()
    monkeypatch.setattr(history, "_ensure_table", lambda: False)
    turn_id = history.begin_turn("visual-history", "alice", "Show the trend")
    q1, q2 = f"{turn_id}:q1", f"{turn_id}:q2"
    registry = [
        {
            "query_id": q1, "attempt_id": f"{q1}:a1", "tool_call_id": "c1",
            "tool_name": "query", "query_fingerprint": "1" * 64,
            "status": "success", "purpose": "answer", "row_count": 2,
            "has_data": True, "visual_available": True, "duration_ms": 1,
        },
        {
            "query_id": q2, "attempt_id": f"{q2}:a1", "tool_call_id": "c2",
            "tool_name": "query", "query_fingerprint": "2" * 64,
            "status": "error", "purpose": "answer", "row_count": None,
            "has_data": False, "visual_available": False, "duration_ms": 1,
            "error_code": "COMPILE_REJECTED",
        },
    ]
    history.set_query_registry("visual-history", "alice", turn_id, registry)
    history.add_card("visual-history", "alice", turn_id, {
        "source": "db", "card_type": "chart", "query_id": q1,
        "attempt_id": f"{q1}:a1", "payload": {"rows": [{"value": 1}]},
    })
    history.set_answer("visual-history", "alice", turn_id, {
        "schema_version": 1, "status": "answered", "text": "The trend increased.",
        "active_query_ids": [q1], "visual_query_ids": [q1],
        "excluded_queries": [{
            "query_id": q2, "reason_code": "execution_error",
            "reason": "The query failed.",
        }],
        "sources": ["db"], "citations": [], "unavailable_sources": [],
        "limitations": [],
    })
    history.complete_turn("visual-history", "alice", turn_id)

    record = history.get("visual-history", user="alice")
    restored = _turn_for_api(record.turns[0])
    assert restored["answer"]["visual_query_ids"] == [q1]
    assert restored["answer"]["excluded_queries"][0]["query_id"] == q2
    assert restored["query_registry"] == registry
    assert restored["cards"][0]["query_id"] == q1


def test_public_web_trace_never_exposes_pre_policy_query_text():
    call = NativeToolCall(
        id="web-1", name="search_public_web",
        arguments={"search_query": "private customer name and account"},
    )

    assert agent._trace_arguments(call)["search_query"] == (
        "[redacted after policy evaluation]"
    )
