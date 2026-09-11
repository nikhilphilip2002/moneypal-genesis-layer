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


def test_public_web_trace_never_exposes_pre_policy_query_text():
    call = NativeToolCall(
        id="web-1", name="search_public_web",
        arguments={"search_query": "private customer name and account"},
    )

    assert agent._trace_arguments(call)["search_query"] == (
        "[redacted after policy evaluation]"
    )
