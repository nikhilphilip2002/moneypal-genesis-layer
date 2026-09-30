from __future__ import annotations

import json
import math
from types import SimpleNamespace

import pytest

from app.core.config import settings
from app.services.nlq.llm.client import (
    LLMContextOverflow,
    LLMError,
    LLMIncomplete,
)
from app.services.nlq.llm.messages import ChatMessage
from app.services.workbench import history
from app.services.workbench.compaction.request import (
    active_messages,
    exchange_boundaries,
    prepare_request,
    summarize_messages,
)


class CountingClient:
    def __init__(self, window=2000):
        self.window = window
        self.summaries = []
        self.counts = []

    async def context_window(self):
        return self.window

    async def count_input_tokens(self, messages, tools=None):
        self.counts.append((messages, tools))
        return math.ceil(len(json.dumps([messages, tools])) / 4)

    async def complete(self, **kwargs):
        self.summaries.append(kwargs)
        assert (
            await self.count_input_tokens(kwargs["messages"])
            + kwargs["max_output_tokens"]
            < self.window
        )
        return SimpleNamespace(
            text="Query q1 established loans of 42. Continue the comparison.",
            tool_calls=[],
        )


def exchange(call_id, content) -> list[ChatMessage]:
    return [
        {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": call_id,
                    "type": "function",
                    "function": {"name": "query", "arguments": "{}"},
                }
            ],
        },
        {"role": "tool", "tool_call_id": call_id, "content": content},
    ]


@pytest.fixture(autouse=True)
def setup(monkeypatch):
    monkeypatch.setattr(settings, "workbench_compaction_enabled", True)
    monkeypatch.setattr(settings, "workbench_reserve_tokens", 400)
    monkeypatch.setattr(settings, "workbench_compaction_max_tokens", 150)
    monkeypatch.setattr(history, "_ensure_table", lambda: False)
    history._MEMORY.clear()
    yield
    history._MEMORY.clear()


@pytest.mark.anyio
async def test_compacts_oldest_prefix_keeps_recent_exchanges_and_reuses_checkpoint():
    client = CountingClient()
    state = {}
    events: list[str] = []

    async def on_compaction(status: str) -> None:
        events.append(status)

    current: ChatMessage = {
        "role": "user",
        "content": "Compare with last month",
    }
    recent = exchange("q2", "recent result")
    messages: list[ChatMessage] = [
        {"role": "system", "content": "System policy"},
        {"role": "user", "content": "old question"},
        *exchange("q1", "old evidence " * 1500),
        {"role": "assistant", "content": "older conclusion"},
        current,
        *recent,
        {"role": "user", "content": "Continue"},
    ]
    tools = [{"schema": "tool schema " * 100}]
    prepared, output, count = await prepare_request(
        state,
        client,
        messages,
        tools,
        current_question=current,
        on_compaction=on_compaction,
    )
    assert events == ["running", "complete"]
    assert prepared[0] == messages[0]
    assert prepared[-4:] == [current, *recent, messages[-1]]
    assert not any(m.get("tool_call_id") == "q1" for m in prepared)
    assert count + output < client.window
    assert client.summaries
    assert "old evidence" in json.dumps(client.summaries)
    assert "recent result" not in json.dumps(client.summaries)
    assert client.counts[-1][1] == tools
    summaries = len(client.summaries)
    again, _, _ = await prepare_request(
        state,
        client,
        messages,
        tools,
        current_question=current,
        on_compaction=on_compaction,
    )
    assert again == prepared
    assert len(client.summaries) == summaries
    assert events == ["running", "complete"]


@pytest.mark.anyio
async def test_compaction_survives_reload_and_followup_without_changing_messages():
    turn = history.begin_turn("c", "u", "current question")
    current: ChatMessage = {"role": "user", "content": "current question"}
    messages: list[ChatMessage] = [
        {"role": "system", "content": "System"},
        current,
        *exchange("old", "large old tool result " * 1000),
        *exchange("new", "latest observation"),
    ]
    history.append_messages("c", "u", turn, messages)
    state = {"conversation_id": "c", "user": "u", "turn_id": turn}
    client = CountingClient()
    prepared, _, _ = await prepare_request(
        state,
        client,
        messages,
        [],
        current_question=current,
    )
    assert prepared[-3:] == [current, *messages[-2:]]
    assert history.load_messages("c", user="u") == messages
    record = history.get("c", user="u")
    assert record is not None
    assert active_messages(record.messages, record.compaction) == prepared
    assert record.compaction is not None
    assert "messages" not in record.compaction
    final: ChatMessage = {"role": "assistant", "content": "original answer "}
    history.append_messages("c", "u", turn, [final])
    history.complete_turn("c", "u", turn)
    followup = history.begin_turn("c", "u", "followup")
    question: ChatMessage = {"role": "user", "content": "followup"}
    history.start_turn_messages("c", "u", followup, messages[0], question)
    record = history.get("c", user="u")
    assert record is not None
    again, _, _ = await prepare_request(
        {"_request_compaction": record.compaction},
        client,
        record.messages,
        [],
        current_question=question,
    )
    assert again == [*prepared, final, question]
    assert record.messages == [*messages, final, question]


@pytest.mark.anyio
async def test_summary_failure_keeps_history_intact():
    class BrokenClient(CountingClient):
        async def complete(self, **kwargs):
            raise LLMError("summary unavailable")

    turn = history.begin_turn("c", "u", "question")
    state = {"conversation_id": "c", "user": "u", "turn_id": turn}
    events: list[str] = []

    async def on_compaction(status: str) -> None:
        events.append(status)

    record = history.get("c", user="u")
    assert record is not None
    assert record is not None
    before = json.dumps(record.turns)
    current: ChatMessage = {"role": "user", "content": "question"}
    messages: list[ChatMessage] = [
        {"role": "system", "content": "policy"},
        {"role": "user", "content": "old " * 4000},
        current,
    ]
    with pytest.raises(LLMError, match="summary unavailable"):
        await prepare_request(
            state,
            BrokenClient(),
            messages,
            [],
            current_question=current,
            on_compaction=on_compaction,
        )
    assert events == ["running", "error"]
    assert "_request_compaction" not in state
    record = history.get("c", user="u")
    assert record is not None
    assert record is not None
    assert json.dumps(record.turns) == before


@pytest.mark.anyio
async def test_oversized_current_question_fails_without_dropping_it():
    client = CountingClient()
    current: ChatMessage = {"role": "user", "content": "huge question " * 1000}
    with pytest.raises(LLMContextOverflow, match="current question"):
        await prepare_request(
            {},
            client,
            [{"role": "system", "content": "policy"}, current],
            [],
            current_question=current,
        )
    assert client.summaries == []


def test_boundary_never_splits_parallel_tool_results():
    first = exchange("a", "one")
    second = exchange("b", "two")
    first[0].get("tool_calls", []).extend(second[0].get("tool_calls", []))
    assert exchange_boundaries([first[0], first[1], second[1]]) == [0, 3]


@pytest.mark.anyio
async def test_summarization_shrinks_chunks_on_server_overflow():
    class SmallerRuntime(CountingClient):
        async def complete(self, **kwargs):
            if len(json.dumps(kwargs["messages"])) > 2000:
                raise LLMContextOverflow("smaller runtime context window")
            return await super().complete(**kwargs)

    client = SmallerRuntime()
    summary = await summarize_messages(
        client,
        [{"role": "user", "content": "history " * 1000}],
        previous="",
        window=client.window,
    )
    assert summary
    assert len(client.summaries) > 1


@pytest.mark.anyio
async def test_summarization_shrinks_chunks_after_incomplete_output():
    class ShorterChunks(CountingClient):
        incomplete_attempts = 0

        async def complete(self, **kwargs):
            if len(json.dumps(kwargs["messages"])) > 2000:
                self.incomplete_attempts += 1
                raise LLMIncomplete("truncated")
            return await super().complete(**kwargs)

    client = ShorterChunks()
    summary = await summarize_messages(
        client,
        [{"role": "user", "content": "history " * 1000}],
        previous="",
        window=client.window,
    )
    assert summary
    assert client.incomplete_attempts > 0


@pytest.mark.anyio
async def test_repeated_compaction_summarizes_only_newly_removed_messages():
    client = CountingClient()
    state = {}
    current: ChatMessage = {"role": "user", "content": "initial objective"}
    messages: list[ChatMessage] = [
        {"role": "system", "content": "policy"},
        current,
        *exchange("first", "first evidence " * 1500),
        *exchange("recent", "recent evidence"),
    ]
    await prepare_request(
        state, client, messages, [], current_question=current
    )
    previous_count = len(client.summaries)
    next_question: ChatMessage = {"role": "user", "content": "new objective"}
    messages.extend(
        [
            {"role": "assistant", "content": "first answer"},
            next_question,
            *exchange("second", "second evidence " * 1500),
            *exchange("latest", "latest result"),
        ]
    )
    prepared, _, _ = await prepare_request(
        state,
        client,
        messages,
        [],
        current_question=next_question,
    )
    summarized = json.dumps(client.summaries[previous_count:])
    assert "first evidence" not in summarized
    assert "initial objective" in summarized
    assert "second evidence" in summarized
    assert prepared[-3:] == [next_question, *messages[-2:]]


@pytest.mark.anyio
async def test_incomplete_summary_does_not_advance_checkpoint():
    class IncompleteClient(CountingClient):
        async def complete(self, **kwargs):
            raise LLMIncomplete("truncated after reasoning")

    client = IncompleteClient()
    state = {}
    current: ChatMessage = {"role": "user", "content": "current question"}
    messages: list[ChatMessage] = [
        {"role": "system", "content": "policy"},
        {"role": "user", "content": "unique old fact " * 1000},
        current,
    ]
    with pytest.raises(LLMIncomplete, match="truncated after reasoning"):
        await prepare_request(
            state,
            client,
            messages,
            [],
            current_question=current,
        )
    assert "_request_compaction" not in state


@pytest.mark.anyio
async def test_unusable_summary_does_not_advance_checkpoint():
    class EmptyClient(CountingClient):
        async def complete(self, **kwargs):
            return SimpleNamespace(text="", tool_calls=[])

    state = {}
    current: ChatMessage = {"role": "user", "content": "current question"}
    messages: list[ChatMessage] = [
        {"role": "system", "content": "policy"},
        {"role": "user", "content": "unique old fact " * 1000},
        current,
    ]
    with pytest.raises(LLMError, match="no usable summary"):
        await prepare_request(
            state,
            EmptyClient(),
            messages,
            [],
            current_question=current,
        )
    assert "_request_compaction" not in state


@pytest.mark.anyio
async def test_compaction_protects_last_two_turns_from_summarizer():
    client = CountingClient(window=3000)
    state = {}
    current: ChatMessage = {"role": "user", "content": "turn 3 question"}
    messages: list[ChatMessage] = [
        {"role": "system", "content": "System policy"},
        {"role": "user", "content": "turn 1 question " * 800},
        {"role": "assistant", "content": "turn 1 answer"},
        {"role": "user", "content": "turn 2 question"},
        {"role": "assistant", "content": "turn 2 answer"},
        current,
    ]
    prepared, _, _ = await prepare_request(
        state,
        client,
        messages,
        [],
        current_question=current,
    )
    assert client.summaries
    summarized_str = json.dumps(client.summaries)
    assert "turn 1 question" in summarized_str
    assert "turn 2 question" not in summarized_str
    assert "turn 3 question" not in summarized_str
    assert prepared[-3:] == [
        {"role": "user", "content": "turn 2 question"},
        {"role": "assistant", "content": "turn 2 answer"},
        current,
    ]


@pytest.mark.anyio
async def test_compaction_allows_up_to_forty_percent_window(monkeypatch):
    monkeypatch.setattr(settings, "workbench_compaction_max_tokens", None)
    client = CountingClient(window=10000)
    state = {}
    current: ChatMessage = {"role": "user", "content": "q"}
    messages: list[ChatMessage] = [
        {"role": "system", "content": "policy"},
        {"role": "user", "content": "large " * 6500},
        current,
    ]
    await prepare_request(
        state,
        client,
        messages,
        [],
        current_question=current,
    )
    assert client.summaries
    assert client.summaries[0]["max_output_tokens"] == 4000


@pytest.mark.anyio
async def test_compaction_env_override_takes_precedence(monkeypatch):
    monkeypatch.setattr(settings, "workbench_compaction_max_tokens", 6000)
    client = CountingClient(window=10000)
    state = {}
    current: ChatMessage = {"role": "user", "content": "q"}
    messages: list[ChatMessage] = [
        {"role": "system", "content": "policy"},
        {"role": "user", "content": "large " * 6500},
        current,
    ]
    await prepare_request(
        state,
        client,
        messages,
        [],
        current_question=current,
    )
    assert client.summaries
    assert client.summaries[0]["max_output_tokens"] == 6000


@pytest.mark.anyio
async def test_summary_near_output_limit_still_fits_prepared_request(
    monkeypatch,
):
    monkeypatch.setattr(settings, "workbench_compaction_max_tokens", None)

    class LongSummaryClient(CountingClient):
        async def complete(self, **kwargs):
            self.summaries.append(kwargs)
            return SimpleNamespace(
                text="S" * (kwargs["max_output_tokens"] * 4 - 100),
                tool_calls=[],
            )

    client = LongSummaryClient(window=10000)
    current: ChatMessage = {"role": "user", "content": "current question"}
    messages: list[ChatMessage] = [
        {"role": "system", "content": "policy"},
        {"role": "user", "content": "large old fact " * 3000},
        current,
    ]
    _, _, tokens_after = await prepare_request(
        {},
        client,
        messages,
        [],
        current_question=current,
    )
    assert client.summaries[0]["max_output_tokens"] == 4000
    assert tokens_after <= 10000 - 2500 - 256
