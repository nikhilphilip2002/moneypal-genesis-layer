from __future__ import annotations

import json
import math
from types import SimpleNamespace

import pytest

from app.core.config import settings
from app.services.nlq.llm.client import LLMContextOverflow, LLMError, LLMIncomplete
from app.services.nlq.llm.messages import ChatMessage
from app.services.workbench import history
from app.services.workbench.compaction.request import (
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
        has_inflight=True,
    )
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
        has_inflight=True,
    )
    assert again == prepared
    assert len(client.summaries) == summaries


@pytest.mark.anyio
async def test_compacts_within_current_turn_and_replays_durable_checkpoint():
    old_turn = history.begin_turn("c", "u", "older question")
    history.set_synthesis("c", "u", old_turn, "older answer")
    history.complete_turn("c", "u", old_turn)
    turn = history.begin_turn("c", "u", "current question")
    current: ChatMessage = {"role": "user", "content": "current question"}
    state = {"conversation_id": "c", "user": "u", "turn_id": turn}
    recent = exchange("new", "latest observation")
    messages: list[ChatMessage] = [
        {"role": "system", "content": "System"},
        {
            "role": "system",
            "content": "Previous summary: preserve this objective",
        },
        current,
        *exchange("old", "large old tool result " * 1000),
        *recent,
        {"role": "user", "content": "Continue"},
    ]
    client = CountingClient()
    prepared, _, _ = await prepare_request(
        state,
        client,
        messages,
        [],
        current_question=current,
        has_inflight=True,
    )
    assert current in prepared
    assert "preserve this objective" in json.dumps(client.summaries)
    assert "current question" not in json.dumps(client.summaries)
    history.set_synthesis("c", "u", turn, "new final answer")
    history.complete_turn("c", "u", turn)
    replay = history.build_native_transcript(
        "c", user="u", enforce_budget=False
    )
    assert replay == [
        *prepared[1:],
        {"role": "assistant", "content": "new final answer"},
    ]
    record = history.get("c", user="u")
    assert record is not None
    assert len(record.turns) == 2
    assert "older answer" not in json.dumps(replay)


@pytest.mark.anyio
async def test_summary_failure_keeps_history_intact():
    class BrokenClient(CountingClient):
        async def complete(self, **kwargs):
            raise LLMError("summary unavailable")

    turn = history.begin_turn("c", "u", "question")
    state = {"conversation_id": "c", "user": "u", "turn_id": turn}
    record = history.get("c", user="u")
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
            has_inflight=False,
        )
    assert "_request_compaction" not in state
    record = history.get("c", user="u")
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
            has_inflight=False,
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
async def test_later_turn_merges_checkpoint_and_does_not_restore_legacy_summary():
    client = CountingClient()
    old_turn = history.begin_turn("c", "u", "initial question")
    history.complete_turn("c", "u", old_turn)
    history.set_compaction(
        "c",
        "u",
        {
            "summary": "legacy checkpoint",
            "first_kept_turn_id": old_turn,
        },
    )
    for index in range(2):
        previous = history.build_native_transcript(
            "c", user="u", enforce_budget=False
        )
        turn = history.begin_turn("c", "u", f"question {index}")
        current: ChatMessage = {"role": "user", "content": f"question {index}"}
        state = {
            "conversation_id": "c",
            "user": "u",
            "turn_id": turn,
            "agent_history_messages": previous,
        }
        prepared, _, _ = await prepare_request(
            state,
            client,
            [
                {"role": "system", "content": "policy"},
                *previous,
                current,
                *exchange(f"large-{index}", "older observation " * 1500),
                *exchange(f"recent-{index}", "latest observation"),
                {"role": "user", "content": "continue"},
            ],
            [],
            current_question=current,
            has_inflight=True,
        )
        history.complete_turn("c", "u", turn)
        replay = history.build_native_transcript(
            "c", user="u", enforce_budget=False
        )
        assert replay == prepared[1:]
        assert (
            len([message for message in replay if message["role"] == "system"])
            == 1
        )
        assert "legacy checkpoint" not in json.dumps(replay)
    record = history.get("c", user="u")
    assert record is not None
    assert len(record.turns) == 3


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
        {"role": "system", "content": "existing checkpoint"},
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
            has_inflight=False,
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
        {"role": "system", "content": "existing checkpoint"},
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
            has_inflight=False,
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
        has_inflight=False,
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
        has_inflight=False,
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
        has_inflight=False,
    )
    assert client.summaries
    assert client.summaries[0]["max_output_tokens"] == 6000


@pytest.mark.anyio
async def test_summary_near_output_limit_still_fits_prepared_request(monkeypatch):
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
        has_inflight=False,
    )
    assert client.summaries[0]["max_output_tokens"] == 4000
    assert tokens_after <= 10000 - 2500 - 256


@pytest.mark.anyio
async def test_summary_output_limit_shrinks_to_keep_recent_turns(monkeypatch):
    monkeypatch.setattr(settings, "workbench_compaction_max_tokens", None)
    monkeypatch.setattr(settings, "workbench_keep_recent_turns", 2)

    class LongSummaryClient(CountingClient):
        async def complete(self, **kwargs):
            self.summaries.append(kwargs)
            return SimpleNamespace(
                text="S" * (kwargs["max_output_tokens"] * 4 - 100),
                tool_calls=[],
            )

    client = LongSummaryClient(window=3000)
    current: ChatMessage = {"role": "user", "content": "current question"}
    recent: ChatMessage = {"role": "user", "content": "recent fact " * 500}
    messages: list[ChatMessage] = [
        {"role": "system", "content": "policy"},
        {"role": "user", "content": "large old fact " * 1000},
        {"role": "assistant", "content": "old answer"},
        recent,
        {"role": "assistant", "content": "recent answer"},
        current,
    ]
    prepared, _, tokens_after = await prepare_request(
        {},
        client,
        messages,
        [],
        current_question=current,
        has_inflight=False,
    )
    assert client.summaries[0]["max_output_tokens"] < 1200
    assert recent in prepared
    assert tokens_after <= 3000 - 400 - 93
