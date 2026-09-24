"""Native Workbench entry-point and terminal-error contracts."""

from __future__ import annotations

import asyncio
import json
import time

import pytest
from starlette.responses import StreamingResponse

from app.services.nlq.llm import (
    LLMIncomplete,
    LLMProtocolError,
    LLMResponseBlocked,
    LLMUnavailable,
    LLMResult,
)
from app.services.workbench import graph
from app.services.workbench.agent import BudgetExhausted
from app.services.workbench.results import SourceResult


@pytest.fixture(autouse=True)
def _memory_only_history(monkeypatch):
    monkeypatch.setattr(graph.history, "_ensure_table", lambda: False)
    graph.history._MEMORY.clear()
    yield
    graph.history._MEMORY.clear()


async def _collect(**kwargs) -> list[tuple[str, dict]]:
    events: list[tuple[str, dict]] = []
    async for frame in graph.run_workbench(**kwargs):
        name = ""
        body = ""
        for line in frame.splitlines():
            if line.startswith("event: "):
                name = line[7:].strip()
            elif line.startswith("data: "):
                body += line[6:]
        if name:
            events.append((name, json.loads(body) if body else {}))
    return events


def _run(question: str = "q"):
    return _collect(
        question=question,
        conversation_id="c1",
        user="alice",
        role="admin",
        external_sources_enabled=True,
    )


@pytest.mark.anyio
async def test_every_request_enters_native_agent_once(monkeypatch):
    calls = []

    async def native_run(state):
        calls.append(state["question"])
        await state["emit"].put(graph.sse("answer", {
            "status": "answered", "text": "done", "sources": [], "citations": [],
            "unavailable_sources": [], "limitations": [],
        }))

    from app.services.workbench import agent

    monkeypatch.setattr(agent, "run", native_run)
    events = await _run("show portfolio")

    assert calls == ["show portfolio"]
    assert [name for name, _data in events] == [
        "conversation", "stage", "answer", "done",
    ]


@pytest.mark.anyio
async def test_closing_stream_cancels_model_and_persists_terminal_trace(monkeypatch):
    from app.services.workbench import agent

    entered = asyncio.Event()

    async def select(*_args, **_kwargs):
        entered.set()
        await asyncio.Event().wait()

    monkeypatch.setattr(agent, "_select", select)
    monkeypatch.setattr(agent, "get_catalog", lambda: object())
    stream = graph.run_workbench(
        question="cancel probe", conversation_id="stream-cancel",
        user="alice", role="admin",
    )
    try:
        frames = []
        while True:
            frame = await asyncio.wait_for(anext(stream), timeout=5)
            frames.append(frame)
            if '"id": "model-1"' in frame:
                break
        await asyncio.wait_for(entered.wait(), timeout=5)
    finally:
        await asyncio.wait_for(stream.aclose(), timeout=5)

    record = graph.history.get("stream-cancel", user="alice")
    assert record is not None
    turn = record.turns[-1]
    assert turn["status"] == "partial"
    model_trace = [
        step for step in turn["execution_trace"] if step["id"] == "model-1"
    ]
    assert [step["status"] for step in model_trace] == ["running", "error"]


@pytest.mark.anyio
async def test_explicit_cancel_stops_owned_turn_without_stream_disconnect(monkeypatch):
    from app.services.workbench import agent

    entered = asyncio.Event()

    async def select(*_args, **_kwargs):
        entered.set()
        await asyncio.Event().wait()

    monkeypatch.setattr(agent, "_select", select)
    monkeypatch.setattr(agent, "get_catalog", lambda: object())
    stream = graph.run_workbench(
        question="cancel probe", conversation_id="explicit-cancel",
        user="alice", role="admin",
    )
    try:
        first = json.loads((await anext(stream)).split("data: ", 1)[1])
        assert first["conversation_id"] == "explicit-cancel"
        turn_id = first["turn_id"]
        while True:
            frame = await asyncio.wait_for(anext(stream), timeout=5)
            if '"id": "model-1"' in frame:
                break
        await asyncio.wait_for(entered.wait(), timeout=5)

        assert graph.cancel_active_turn("explicit-cancel", "bob", turn_id) is False
        assert graph.cancel_active_turn("explicit-cancel", "alice", turn_id) is True
        remaining = [frame async for frame in stream]
        assert any(frame.startswith("event: done\n") for frame in remaining)
    finally:
        await stream.aclose()

    assert graph.cancel_active_turn("explicit-cancel", "alice", turn_id) is False
    record = graph.history.get("explicit-cancel", user="alice")
    assert record is not None
    turn = record.turns[-1]
    assert turn["status"] == "partial"
    assert turn["execution_trace"][-1]["status"] == "error"


@pytest.mark.anyio
async def test_asgi_disconnect_cancels_silent_model_request(monkeypatch):
    from app.services.workbench import agent

    entered = asyncio.Event()
    disconnected = asyncio.Queue()

    async def select(*_args, **_kwargs):
        entered.set()
        await asyncio.Event().wait()

    async def receive():
        return await disconnected.get()

    async def send(_message):
        pass

    monkeypatch.setattr(agent, "_select", select)
    monkeypatch.setattr(agent, "get_catalog", lambda: object())
    response = StreamingResponse(graph.run_workbench(
        question="cancel probe", conversation_id="asgi-cancel",
        user="alice", role="admin",
    ))
    scope = {"type": "http", "asgi": {"spec_version": "2.3"}, "method": "POST"}
    task = asyncio.create_task(response(scope, receive, send))
    try:
        await asyncio.wait_for(entered.wait(), timeout=5)
        await disconnected.put({"type": "http.disconnect"})
        await asyncio.wait_for(task, timeout=5)
    finally:
        if not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    record = graph.history.get("asgi-cancel", user="alice")
    assert record is not None
    turn = record.turns[-1]
    assert turn["status"] == "partial"
    assert turn["execution_trace"][-1]["status"] == "error"


@pytest.mark.anyio
async def test_only_first_message_marks_slot_as_new_chat(monkeypatch):
    flags = []

    async def native_run(state):
        flags.append(state.get("_slot_new_chat"))
        await state["emit"].put(graph.sse("answer", {
            "status": "answered", "text": "done", "sources": [], "citations": [],
            "unavailable_sources": [], "limitations": [],
        }))

    from app.services.workbench import agent

    monkeypatch.setattr(agent, "run", native_run)
    await _run("first")
    await _run("second")

    assert flags == [True, False]


@pytest.mark.anyio
async def test_native_transcript_overflow_is_recorded_and_visible(monkeypatch):
    def overflow(*_args, **_kwargs):
        raise graph.history.NativeTranscriptOverflow("complete native conversation exceeds")

    monkeypatch.setattr(graph.history, "build_native_transcript", overflow)
    events = await _run("and by scheme?")

    assert [name for name, _data in events] == ["conversation", "error", "done"]
    error = events[1][1]
    assert error["message"] == graph.CONTEXT_FULL_MESSAGE
    assert error["retryable"] is False
    assert error["code"] == graph.CONTEXT_CAPACITY_CODE
    record = graph.history.get("c1", user="alice")
    assert record is not None
    assert record.turns[-1]["error"] == graph.CONTEXT_FULL_MESSAGE


@pytest.mark.anyio
@pytest.mark.parametrize(("failure", "code", "retryable"), [
    (BudgetExhausted("spent"), "AGENT_BUDGET_EXHAUSTED", False),
    (TimeoutError("late"), "AGENT_TIMEOUT", True),
    (LLMUnavailable("offline"), "MODEL_UNAVAILABLE", True),
    (LLMIncomplete("truncated"), "MODEL_INCOMPLETE", True),
    (LLMResponseBlocked("filtered"), "MODEL_RESPONSE_BLOCKED", False),
    (LLMProtocolError("invalid"), "MODEL_PROTOCOL_ERROR", True),
])
async def test_native_failures_emit_one_typed_error(monkeypatch, failure, code, retryable):
    from app.services.workbench import agent

    async def native_run(_state):
        raise failure

    monkeypatch.setattr(agent, "run", native_run)
    events = await _run()

    errors = [data for name, data in events if name == "error"]
    assert len(errors) == 1
    assert errors[0]["code"] == code
    assert errors[0]["retryable"] is retryable
    assert events[-1][0] == "done"


def _answer_state(model_text: str, registry: list[dict]):
    return {
        "emit": asyncio.Queue(),
        "conversation_id": "c-answer", "user": "alice", "turn_id": "turn-answer",
        "timing": {"started_at": time.perf_counter()},
        "results": [SourceResult(
            source="db", card_type="chart", payload={"rows": [{"value": 1}]},
            summary="One row.",
        )],
        "query_registry": registry,
        "agent_final_result": LLMResult(
            text=model_text, model="m", provider="test",
            assistant_message={"role": "assistant", "content": model_text},
        ),
    }


def _successful_query(query_id: str = "turn-answer:q1") -> dict:
    return {
        "query_id": query_id, "attempt_id": f"{query_id}:a1",
        "tool_call_id": "call-1", "tool_name": "query", "status": "success",
        "purpose": "answer", "row_count": 1, "has_data": True,
        "visual_available": False, "duration_ms": 1,
    }


def _successful_visual(query_id: str = "turn-answer:v1") -> dict:
    return {
        "query_id": query_id, "attempt_id": f"{query_id}:a1",
        "tool_call_id": "call-v1", "tool_name": "visualize_query_result",
        "status": "success", "purpose": "answer", "row_count": 1,
        "has_data": True, "visual_available": True, "duration_ms": 1,
        "source_query_id": "turn-answer:q1",
    }


@pytest.mark.anyio
async def test_answer_results_reconciles_structured_query_references():
    state = _answer_state(json.dumps({
        "insights": "The value is one.", "query_id": 1, "view": "table",
    }), [_successful_query()])

    await graph.answer_results(state)

    frame = state["emit"].get_nowait()
    assert frame.startswith("event: answer\n")
    answer = json.loads(frame.split("data: ", 1)[1])
    assert answer["text"] == "The value is one."
    assert answer["active_query_ids"] == ["turn-answer:q1"]
    assert answer["visual_query_ids"] == ["turn-answer:q1"]
    assert answer["query_id"] == 1
    assert answer["view"] == "table"
    assert answer["invalid_query_ids"] == []
    assert answer["attribution_fallback_used"] is False


@pytest.mark.anyio
async def test_plain_text_does_not_infer_query_attribution():
    state = _answer_state("The value is one.", [_successful_query()])

    await graph.answer_results(state)
    answer = json.loads(state["emit"].get_nowait().split("data: ", 1)[1])

    assert answer["active_query_ids"] == []
    assert answer["visual_query_ids"] == []
    assert answer["attribution_fallback_used"] is False


@pytest.mark.anyio
async def test_plain_text_conceptual_answer_needs_no_query():
    state = _answer_state("PAR means portfolio at risk.", [])
    state["results"] = []

    await graph.answer_results(state)
    answer = json.loads(state["emit"].get_nowait().split("data: ", 1)[1])

    assert answer["status"] == "answered"
    assert answer["text"] == "PAR means portfolio at risk."
    assert answer["active_query_ids"] == []
    assert answer["visual_query_ids"] == []
