"""Native Workbench entry-point and terminal-error contracts."""

from __future__ import annotations

import asyncio
import json
import time

import httpx
import pytest
from openai import AsyncOpenAI
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


@pytest.mark.anyio
async def test_stream_loads_previous_queries_into_turn_state(monkeypatch):
    from app.services.workbench import agent, history

    monkeypatch.setattr(history, "_ensure_table", lambda: False)
    prior_turn = history.begin_turn("stream-reuse", "alice", "First question")
    history.set_query_registry(
        "stream-reuse",
        "alice",
        prior_turn,
        [
            {
                "query_id": f"{prior_turn}:q1",
                "status": "success",
                "has_data": True,
            }
        ],
    )
    seen = []

    async def capture(state):
        seen.append((state["query_registry"], state["prior_query_registry"]))

    monkeypatch.setattr(agent, "run", capture)
    events = [
        frame
        async for frame in graph.run_workbench(
            question="Show it as a table",
            conversation_id="stream-reuse",
            user="alice",
            role="admin",
        )
    ]

    assert events[-1].startswith("event: done\n")
    assert seen == [
        (
            [],
            [
                {
                    "query_id": f"{prior_turn}:q1",
                    "status": "success",
                    "has_data": True,
                }
            ],
        )
    ]


@pytest.mark.anyio
@pytest.mark.parametrize("response_started", [False, True])
@pytest.mark.parametrize("explicit_stop", [False, True])
async def test_stop_disconnects_upstream_tcp_connection(
    monkeypatch,
    response_started,
    explicit_stop,
):
    """Use the real SDK/HTTP transport, including cancellation before SSE headers."""
    from app.services.nlq.llm.client import (
        OpenAICompatibleClient,
        _ProviderProfile,
    )
    from app.services.workbench import agent

    received = asyncio.Event()
    upstream_closed = asyncio.Event()
    disconnected = asyncio.Queue()
    requests = []
    turn = {}
    handlers = set()

    async def upstream(reader, writer):
        handlers.add(asyncio.current_task())
        try:
            headers = await reader.readuntil(b"\r\n\r\n")
            length = next(
                int(line.split(b":", 1)[1])
                for line in headers.split(b"\r\n")
                if line.lower().startswith(b"content-length:")
            )
            requests.append(json.loads(await reader.readexactly(length)))
            if response_started:
                writer.write(
                    b"HTTP/1.1 200 OK\r\nContent-Type: text/event-stream\r\n"
                    b"Connection: close\r\n\r\n"
                    b'data: {"choices":[{"index":0,"delta":{"content":"hello"}}]}\n\n'
                )
                await writer.drain()
            received.set()
            assert await reader.read() == b""
            upstream_closed.set()
        finally:
            writer.close()
            await writer.wait_closed()
            handlers.discard(asyncio.current_task())

    server = await asyncio.start_server(upstream, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    client = OpenAICompatibleClient(
        profile=_ProviderProfile(
            name="llamacpp",
            base_url=f"http://127.0.0.1:{port}/v1",
            api_key="k",
            supports_json_schema=True,
            supports_native_tools=True,
        ),
        model="test",
    )

    async def select(*_args, **_kwargs):
        return await client.complete(messages=[])

    async def receive():
        return await disconnected.get()

    async def send(message):
        body = message.get("body", b"").decode()
        if body.startswith("event: conversation\n"):
            turn.update(json.loads(body.split("data: ", 1)[1]))

    monkeypatch.setattr(agent, "_select", select)
    monkeypatch.setattr(agent, "get_catalog", lambda: object())
    response = StreamingResponse(
        graph.run_workbench(
            question="cancel probe",
            conversation_id="tcp-cancel",
            user="alice",
            role="admin",
        )
    )
    scope = {"type": "http", "asgi": {"spec_version": "2.3"}, "method": "POST"}
    task = asyncio.create_task(response(scope, receive, send))
    try:
        await asyncio.wait_for(received.wait(), 5)
        if explicit_stop:
            assert graph.cancel_active_turn(
                "tcp-cancel", "alice", turn["turn_id"]
            )
        await disconnected.put({"type": "http.disconnect"})
        await asyncio.wait_for(task, 5)
        await asyncio.wait_for(upstream_closed.wait(), 5)
        assert len(requests) == 1
        assert requests[0]["stream"] is True
        assert not graph._active_turn_tasks
    finally:
        if not task.done():
            task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        await client.aclose()
        server.close()
        await server.wait_closed()
        for handler in list(handlers):
            handler.cancel()
        await asyncio.gather(*handlers, return_exceptions=True)


@pytest.mark.anyio
@pytest.mark.parametrize("explicit_stop", [False, True])
async def test_disconnect_waits_for_llm_connection_close(
    monkeypatch, explicit_stop
):
    """Transport cleanup must survive both ASGI cancellation and a preceding Stop."""
    from app.services.nlq.llm.client import (
        OpenAICompatibleClient,
        _ProviderProfile,
    )
    from app.services.workbench import agent

    entered = asyncio.Event()
    closing = asyncio.Event()
    release_close = asyncio.Event()
    closed = asyncio.Event()
    disconnected = asyncio.Queue()
    turn = {}
    requests = []
    compactions = []

    class Stream(httpx.AsyncByteStream):
        async def __aiter__(self):
            entered.set()
            await asyncio.Event().wait()
            yield b""

        async def aclose(self):
            closing.set()
            await release_close.wait()
            closed.set()

    def handler(request):
        requests.append(request)
        return httpx.Response(200, stream=Stream())

    client = OpenAICompatibleClient(
        profile=_ProviderProfile(
            name="llamacpp",
            base_url="http://stub/v1",
            api_key="k",
            supports_json_schema=True,
            supports_native_tools=True,
        ),
        model="test",
    )
    client._client = AsyncOpenAI(
        api_key="k",
        base_url="http://stub/v1",
        max_retries=0,
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    client._client._platform = "Linux"

    async def select(*_args, **_kwargs):
        return await client.complete(messages=[])

    async def compact(*args):
        compactions.append(args)

    async def receive():
        return await disconnected.get()

    async def send(message):
        body = message.get("body", b"").decode()
        if body.startswith("event: conversation\n"):
            turn.update(json.loads(body.split("data: ", 1)[1]))

    monkeypatch.setattr(agent, "_select", select)
    monkeypatch.setattr(agent, "get_catalog", lambda: object())
    monkeypatch.setattr(graph.settings, "workbench_compaction_enabled", True)
    monkeypatch.setattr(
        "app.services.workbench.compaction.maybe_compact", compact
    )
    response = StreamingResponse(
        graph.run_workbench(
            question="cancel probe",
            conversation_id="transport-cancel",
            user="alice",
            role="admin",
        )
    )
    scope = {"type": "http", "asgi": {"spec_version": "2.3"}, "method": "POST"}
    task = asyncio.create_task(response(scope, receive, send))
    try:
        await asyncio.wait_for(entered.wait(), 5)
        if explicit_stop:
            assert graph.cancel_active_turn(
                "transport-cancel", "alice", turn["turn_id"]
            )
            await asyncio.wait_for(closing.wait(), 5)
            # A duplicate Stop must not interrupt an in-progress socket close either.
            assert graph.cancel_active_turn(
                "transport-cancel", "alice", turn["turn_id"]
            )
        await disconnected.put({"type": "http.disconnect"})
        await asyncio.wait_for(closing.wait(), 5)
        # Let the disconnect listener and cancelled response task run during close.
        for _ in range(10):
            await asyncio.sleep(0)
        release_close.set()
        await asyncio.wait_for(task, 5)
        assert closed.is_set(), (
            "Cancellation interrupted the upstream connection close"
        )
        assert len(requests) == 1
        assert compactions == [], "Stop must not start another model request"
        assert not graph._active_turn_tasks
    finally:
        release_close.set()
        if not task.done():
            task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        await client.aclose()


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
        await state["emit"].put(
            graph.sse(
                "answer",
                {
                    "status": "answered",
                    "text": "done",
                    "sources": [],
                    "citations": [],
                    "unavailable_sources": [],
                    "limitations": [],
                },
            )
        )

    from app.services.workbench import agent

    monkeypatch.setattr(agent, "run", native_run)
    events = await _run("show portfolio")

    assert calls == ["show portfolio"]
    assert [name for name, _data in events] == [
        "conversation",
        "stage",
        "answer",
        "done",
    ]


@pytest.mark.anyio
async def test_closing_stream_cancels_model_and_persists_terminal_trace(
    monkeypatch,
):
    from app.services.workbench import agent

    entered = asyncio.Event()

    async def select(*_args, **_kwargs):
        entered.set()
        await asyncio.Event().wait()

    monkeypatch.setattr(agent, "_select", select)
    monkeypatch.setattr(agent, "get_catalog", lambda: object())
    stream = graph.run_workbench(
        question="cancel probe",
        conversation_id="stream-cancel",
        user="alice",
        role="admin",
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
async def test_explicit_cancel_stops_owned_turn_without_stream_disconnect(
    monkeypatch,
):
    from app.services.workbench import agent

    entered = asyncio.Event()

    async def select(*_args, **_kwargs):
        entered.set()
        await asyncio.Event().wait()

    monkeypatch.setattr(agent, "_select", select)
    monkeypatch.setattr(agent, "get_catalog", lambda: object())
    stream = graph.run_workbench(
        question="cancel probe",
        conversation_id="explicit-cancel",
        user="alice",
        role="admin",
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

        assert (
            graph.cancel_active_turn("explicit-cancel", "bob", turn_id)
            is False
        )
        assert (
            graph.cancel_active_turn("explicit-cancel", "alice", turn_id)
            is True
        )
        remaining = [frame async for frame in stream]
        assert any(frame.startswith("event: done\n") for frame in remaining)
    finally:
        await stream.aclose()

    assert (
        graph.cancel_active_turn("explicit-cancel", "alice", turn_id) is False
    )
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
    response = StreamingResponse(
        graph.run_workbench(
            question="cancel probe",
            conversation_id="asgi-cancel",
            user="alice",
            role="admin",
        )
    )
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
        await state["emit"].put(
            graph.sse(
                "answer",
                {
                    "status": "answered",
                    "text": "done",
                    "sources": [],
                    "citations": [],
                    "unavailable_sources": [],
                    "limitations": [],
                },
            )
        )

    from app.services.workbench import agent

    monkeypatch.setattr(agent, "run", native_run)
    await _run("first")
    await _run("second")

    assert flags == [True, False]


@pytest.mark.anyio
async def test_native_transcript_overflow_is_recorded_and_visible(monkeypatch):
    def overflow(*_args, **_kwargs):
        raise graph.history.NativeTranscriptOverflow(
            "complete native conversation exceeds"
        )

    monkeypatch.setattr(graph.history, "build_native_transcript", overflow)
    events = await _run("and by scheme?")

    assert [name for name, _data in events] == [
        "conversation",
        "error",
        "done",
    ]
    error = events[1][1]
    assert error["message"] == graph.CONTEXT_FULL_MESSAGE
    assert error["retryable"] is False
    assert error["code"] == graph.CONTEXT_CAPACITY_CODE
    record = graph.history.get("c1", user="alice")
    assert record is not None
    assert record.turns[-1]["error"] == graph.CONTEXT_FULL_MESSAGE


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("failure", "code", "retryable"),
    [
        (BudgetExhausted("spent"), "AGENT_BUDGET_EXHAUSTED", False),
        (TimeoutError("late"), "AGENT_TIMEOUT", True),
        (LLMUnavailable("offline"), "MODEL_UNAVAILABLE", True),
        (LLMIncomplete("truncated"), "MODEL_INCOMPLETE", True),
        (LLMResponseBlocked("filtered"), "MODEL_RESPONSE_BLOCKED", False),
        (LLMProtocolError("invalid"), "MODEL_PROTOCOL_ERROR", True),
    ],
)
async def test_native_failures_emit_one_typed_error(
    monkeypatch, failure, code, retryable
):
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
        "conversation_id": "c-answer",
        "user": "alice",
        "turn_id": "turn-answer",
        "timing": {"started_at": time.perf_counter()},
        "results": [
            SourceResult(
                source="db",
                card_type="chart",
                payload={"rows": [{"value": 1}]},
                summary="One row.",
            )
        ],
        "query_registry": registry,
        "agent_final_result": LLMResult(
            text=model_text,
            model="m",
            provider="test",
            assistant_message={"role": "assistant", "content": model_text},
        ),
    }


def _successful_query(query_id: str = "turn-answer:q1") -> dict:
    return {
        "query_id": query_id,
        "attempt_id": f"{query_id}:a1",
        "tool_call_id": "call-1",
        "tool_name": "query",
        "status": "success",
        "purpose": "answer",
        "row_count": 1,
        "has_data": True,
        "visual_available": False,
        "duration_ms": 1,
    }


@pytest.mark.anyio
async def test_answer_results_reconciles_structured_query_references():
    state = _answer_state(
        json.dumps(
            {
                "insights": "The value is one.",
                "query_id": 1,
                "view": "table",
            }
        ),
        [_successful_query()],
    )

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
