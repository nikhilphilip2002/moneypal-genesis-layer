from __future__ import annotations

import json

import pytest

from app.services.nlq.llm import LLMProtocolError
from app.services.workbench import agent, history
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
    assert client.requests[-1]["tool_choice"] == {
        "type": "function",
        "function": {"name": "submit_final_answer"},
    }
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
    assert (
        client.requests[-1]["tool_choice"]["function"]["name"]
        == "submit_final_answer"
    )


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
