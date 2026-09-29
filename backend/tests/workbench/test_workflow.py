from __future__ import annotations

import json

import pytest

from app.services.nlq.llm import LLMProtocolError
from app.services.workbench import agent, history
from ..nlq.test_llm_client import _client, _ok, _tool_ok
from .test_agent import (
    _PAR_30,
    _async,
    _final_response,
    _frames,
    _raw,
    _run_state,
    _settings,
    _text_response,
    _tool_response,
    scripted,
)

__all__ = ["_settings", "scripted"]


@pytest.mark.anyio
async def test_finalization_sends_string_choice_through_http_client(
    scripted, monkeypatch
):
    scripted([], lambda call, _ctx: _async(_raw(call)))
    monkeypatch.setattr(agent.settings, "workbench_agent_max_rounds", 3)
    requests = []
    query_message = _tool_response(_PAR_30).assistant_message
    final_message = _final_response("PAR 30 is 4.2%.").assistant_message
    assert query_message is not None
    assert final_message is not None
    query = query_message["tool_calls"][0]
    final = final_message["tool_calls"][0]

    def handler(request):
        payload = json.loads(request.content)
        requests.append(payload)
        assert isinstance(payload.get("tool_choice", "auto"), str)
        if len(requests) == 1:
            assert "query" in {
                tool["function"]["name"] for tool in payload["tools"]
            }
            return _tool_ok(query)
        if len(requests) == 2:
            return _ok("PAR 30 is 4.2%.")
        assert payload["tool_choice"] == "required"
        assert [
            tool["function"]["name"] for tool in payload["tools"]
        ] == ["submit_final_answer"]
        assert any(
            query in message.get("tool_calls", [])
            for message in payload["messages"]
        )
        assert any(
            message.get("role") == "tool"
            and message.get("tool_call_id") == _PAR_30.id
            for message in payload["messages"]
        )
        return _tool_ok(final)

    client = _client(handler)
    monkeypatch.setattr(client, "count_input_tokens", None)
    monkeypatch.setattr(agent.models, "client", lambda: client)
    state = _run_state("graph-string-choice")
    await agent.run(state)

    assert len(requests) == 3
    answers = [
        json.loads(frame.split("data: ", 1)[1])
        for frame in _frames(state)
        if frame.startswith("event: answer\n")
    ]
    assert len(answers) == 1
    assert answers[0]["query_id"] == 1
    assert answers[0]["view"] == "table"


@pytest.mark.anyio
async def test_missing_submission_routes_to_finalization_and_renders(scripted):
    client = scripted(
        [
            _tool_response(_PAR_30),
            _text_response("PAR 30 is 4.2%."),
            _final_response("PAR 30 is 4.2%."),
        ],
        lambda call, _ctx: _async(_raw(call)),
    )
    state = _run_state("graph-missing-final")
    await agent.run(state)

    assert len(client.requests) == 3
    assert client.requests[-1]["tool_choice"] == "required"
    assert [
        tool["function"]["name"] for tool in client.requests[-1]["tools"]
    ] == ["submit_final_answer"]
    assert "query" in {
        tool["function"]["name"] for tool in client.requests[0]["tools"]
    }
    assert client.requests[0]["messages"][0] == client.requests[-1]["messages"][0]
    answers = [
        json.loads(frame.split("data: ", 1)[1])
        for frame in _frames(state)
        if frame.startswith("event: answer\n")
    ]
    assert len(answers) == 1
    assert answers[0]["query_id"] == 1
    assert answers[0]["view"] == "table"
    assert answers[0]["active_query_ids"] == [f"{state['turn_id']}:q1"]
    record = history.get(state["conversation_id"], user="alice")
    assert record is not None
    assert record.turns[0]["answer"]["query_id"] == 1


@pytest.mark.anyio
async def test_last_round_is_reserved_for_submission(scripted, monkeypatch):
    monkeypatch.setattr(agent.settings, "workbench_agent_max_rounds", 2)
    client = scripted(
        [_tool_response(_PAR_30), _final_response("PAR 30 is 4.2%.")],
        lambda call, _ctx: _async(_raw(call)),
    )
    await agent.run(_run_state("graph-reserved-final"))
    assert client.requests[-1]["call_purpose"] == "agent_synthesize"
    assert client.requests[-1]["tool_choice"] == "required"
    assert [
        tool["function"]["name"] for tool in client.requests[-1]["tools"]
    ] == ["submit_final_answer"]


@pytest.mark.anyio
async def test_ignored_finalization_fails_explicitly_with_bounded_requests(
    scripted, monkeypatch
):
    monkeypatch.setattr(agent.settings, "workbench_agent_max_rounds", 5)
    client = scripted(
        [
            _tool_response(_PAR_30),
            *[_text_response("Here is the answer.")] * 3,
        ],
        lambda call, _ctx: _async(_raw(call)),
    )
    state = _run_state("graph-ignored-final")
    with pytest.raises(LLMProtocolError, match="Final submission"):
        await agent.run(state)
    assert len(client.requests) == 4
    assert not any(
        frame.startswith("event: answer\n") for frame in _frames(state)
    )


@pytest.mark.anyio
async def test_other_tools_cannot_execute_during_finalization(
    scripted, monkeypatch
):
    monkeypatch.setattr(agent.settings, "workbench_agent_max_rounds", 4)
    executed = []

    async def execute(call, _ctx):
        executed.append(call.name)
        return _raw(call)

    client = scripted(
        [
            _tool_response(_PAR_30),
            _text_response("Done"),
            _tool_response(_PAR_30),
            _final_response("Done"),
        ],
        execute,
    )
    await agent.run(_run_state("graph-final-tools"))
    assert executed == ["query"]
    assert any(
        "Only submit_final_answer" in str(message)
        for message in client.requests[-1]["messages"]
    )


@pytest.mark.anyio
async def test_followup_preserves_previous_model_request_prefix(scripted):
    client = scripted(
        [
            _tool_response(_PAR_30),
            _final_response("PAR 30 is 4.2%."),
            _text_response("It was 4.2%."),
        ],
        lambda call, _ctx: _async(_raw(call)),
    )
    state = _run_state("graph-prefix")
    await agent.run(state)
    history.complete_turn(state["conversation_id"], "alice", state["turn_id"])
    prior_messages = client.requests[-1]["messages"]
    state["agent_history_messages"] = history.build_native_transcript(
        state["conversation_id"], user="alice"
    )
    state["prior_query_registry"] = state["query_registry"]
    state["query_registry"] = []
    state["question"] = "What was that value?"
    state["turn_id"] = history.begin_turn(
        state["conversation_id"], "alice", state["question"]
    )
    await agent.run(state)
    followup_messages = client.requests[-1]["messages"]
    assert followup_messages[: len(prior_messages)] == prior_messages


@pytest.mark.anyio
async def test_snapshot_is_restored_between_interleaved_requests(
    scripted, monkeypatch
):
    monkeypatch.setattr(agent.settings, "llama_slot_snapshots_enabled", True)
    calls = []
    scripted([_text_response("Ready.")] * 3, lambda *_: None)

    async def snapshot(action, *, filename):
        calls.append((action, filename))
        return {"id_slot": 0}

    monkeypatch.setattr(agent, "slot_action", snapshot)
    first = _run_state("snapshot-a")
    second = _run_state("snapshot-b")
    agent._budget(first)
    agent._budget(second)
    await agent._select(first, tool_choice="auto")
    await agent._select(second, tool_choice="auto")
    await agent._select(first, tool_choice="auto")
    assert [action for action, _ in calls] == ["restore", "save"] * 3
    assert calls[0][1] == calls[4][1]
    assert calls[0][1] != calls[2][1]
