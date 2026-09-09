"""Native Workbench entry-point and terminal-error contracts."""

from __future__ import annotations

import json

import pytest

from app.services.nlq.llm import LLMProtocolError, LLMUnavailable
from app.services.workbench import graph
from app.services.workbench.agent import BudgetExhausted


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
