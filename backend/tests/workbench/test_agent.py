from __future__ import annotations

import asyncio
import json
import time

import pytest

from app.services.nlq.llm import LLMProtocolError, LLMResult, NativeToolCall
from app.services.workbench import access, agent, history, models, outbound_policy
from app.services.workbench.agent_executor import ExecutedAgentCall
from app.services.workbench.results import SourceResult


@pytest.fixture(autouse=True)
def _settings(monkeypatch):
    monkeypatch.setattr(access.settings, "workbench_external_connectors_enabled", True)
    monkeypatch.setattr(access.settings, "exa_mcp_enabled", True)
    monkeypatch.setattr(agent.settings, "workbench_agent_argument_repairs", 1)
    monkeypatch.setattr(agent.settings, "workbench_agent_max_tool_calls", 6)


def _state():
    return {
        "question": "Show PAR 30",
        "history_messages": [],
        "source_policy": access.build_policy(role="admin", external_sources_enabled=True),
    }


def _result(call=None, *, content=""):
    calls = [call] if call else []
    raw = [] if call is None else [{
        "id": call.id,
        "type": "function",
        "function": {"name": call.name, "arguments": "{}"},
    }]
    return LLMResult(
        text=content,
        model="m",
        provider="llamacpp",
        tool_calls=calls,
        assistant_message={"role": "assistant", "content": content, "tool_calls": raw},
    )


@pytest.mark.anyio
async def test_content_only_json_is_not_a_selection(monkeypatch):
    async def select(*_args, **_kwargs):
        return _result(content='{"name":"query_metrics"}')

    monkeypatch.setattr(agent, "_select", select)
    with pytest.raises(LLMProtocolError, match="no tool_calls"):
        await agent.select_calls(_state())


@pytest.mark.anyio
async def test_invalid_arguments_receive_one_native_repair(monkeypatch):
    responses = [
        _result(NativeToolCall(id="bad", name="query_metrics", arguments={})),
        _result(NativeToolCall(
            id="good",
            name="query_metrics",
            arguments={
                "metrics": ["par_30"],
                "dimensions": [],
                "period": {"relative": "this_month"},
            },
        )),
    ]
    repair_seen = []

    async def select(_state, *, repair_messages=None):
        repair_seen.append(repair_messages)
        return responses.pop(0)

    monkeypatch.setattr(agent, "_select", select)
    result = await agent.select_calls(_state())
    assert result.tool_calls[0].id == "good"
    assert repair_seen[0] is None
    assert repair_seen[1][-1]["tool_call_id"] == "bad"
    assert "INVALID_TOOL_ARGUMENTS" in repair_seen[1][-1]["content"]


@pytest.mark.anyio
async def test_explicit_calendar_year_canonicalizes_duplicate_relative_period(monkeypatch):
    call = NativeToolCall(
        id="year",
        name="query_metrics",
        arguments={
            "metrics": ["disbursement_total"],
            "dimensions": ["month"],
            "filters": [],
            "having": [],
            "period": {
                "grain": "month", "start": "2026-01-01", "end": "2026-12-31",
                "relative": "all_time",
            },
            "compare_to": None,
            "order_by": {"field": "month", "direction": "asc"},
            "limit": 100,
            "as_share": False,
            "explain": False,
        },
    )
    response = _result(call)

    async def select(*_args, **_kwargs):
        return response

    monkeypatch.setattr(agent, "_select", select)
    state = _state()
    state["question"] = "loan disbursed month wise in 2026"
    result = await agent.select_calls(state)

    assert result.tool_calls[0].arguments["period"]["relative"] is None
    raw_arguments = json.loads(
        result.assistant_message["tool_calls"][0]["function"]["arguments"]
    )
    assert raw_arguments["period"]["relative"] is None


@pytest.mark.anyio
@pytest.mark.parametrize(
    "question",
    [
        "interest collected monthwise till today",
        "i mean month wise",
        "show interest collected by-month",
    ],
)
async def test_explicit_month_grain_is_preserved(monkeypatch, question):
    call = NativeToolCall(
        id="monthly",
        name="query_metrics",
        arguments={
            "metrics": ["interest_collected"],
            "dimensions": [],
            "filters": [],
            "having": [],
            "period": {
                "grain": None, "start": None, "end": None, "relative": "all_time",
            },
            "compare_to": None,
            "order_by": None,
            "limit": 100,
            "as_share": False,
            "explain": False,
        },
    )
    response = _result(call)

    async def select(*_args, **_kwargs):
        return response

    monkeypatch.setattr(agent, "_select", select)
    state = _state()
    state["question"] = question
    result = await agent.select_calls(state)

    arguments = result.tool_calls[0].arguments
    assert arguments["dimensions"] == ["month"]
    assert arguments["order_by"] == {"field": "month", "direction": "asc"}
    raw_arguments = json.loads(
        result.assistant_message["tool_calls"][0]["function"]["arguments"]
    )
    assert raw_arguments["dimensions"] == ["month"]
    assert raw_arguments["order_by"] == {"field": "month", "direction": "asc"}


@pytest.mark.anyio
async def test_unauthorized_domain_fails_without_a_repair_round(monkeypatch):
    state = _state()
    state["source_policy"] = access.build_policy(
        role="admin", external_sources_enabled=False,
    )
    attempts = 0

    async def select(_state, *, repair_messages=None):
        nonlocal attempts
        attempts += 1
        assert repair_messages is None
        return _result(NativeToolCall(
            id="forged",
            name="search_curated_knowledge",
            arguments={"domain": "regulatory", "query": "RBI rules"},
        ))

    monkeypatch.setattr(agent, "_select", select)
    with pytest.raises(Exception, match="external source consent"):
        await agent.select_calls(state)
    assert attempts == 1


def test_canary_assignment_is_stable(monkeypatch):
    monkeypatch.setattr(agent.settings, "workbench_agent_mode", "canary")
    monkeypatch.setattr(agent.settings, "workbench_agent_canary_percent", 50)
    first = agent.assigned_mode("conversation", "alice")
    assert first in {"on", "off"}
    assert agent.assigned_mode("conversation", "alice") == first


@pytest.mark.anyio
async def test_single_native_db_card_uses_its_grounded_summary_without_resynthesis(monkeypatch):
    calls = []
    native_call = NativeToolCall(
        id="call_1",
        name="query_metrics",
        arguments={
            "metrics": ["par_30"],
            "dimensions": [],
            "period": {"relative": "this_month"},
        },
    )

    class FakeClient:
        async def complete(self, **kwargs):
            calls.append(kwargs)
            if kwargs.get("tool_choice") == "required":
                return LLMResult(
                    text="", model="m", provider="llamacpp", tool_calls=[native_call],
                    assistant_message={
                        "role": "assistant", "content": None,
                        "tool_calls": [{
                            "id": "call_1", "type": "function",
                            "function": {
                                "name": "query_metrics",
                                "arguments": '{"metrics":["par_30"],"dimensions":[],"period":{"relative":"this_month"}}',
                            },
                        }],
                    },
                )
            return LLMResult(text="PAR 30 is 4.2%.", model="m", provider="llamacpp")

    async def execute(call, _ctx):
        return ExecutedAgentCall(
            call=call,
            card=SourceResult(
                source="db", card_type="chart",
                payload={
                    "title": "PAR 30", "summary": "PAR 30 is 4.2%.",
                    "columns": [{"name": "value", "label": "PAR 30", "unit": "percent"}],
                    "rows": [{"value": 4.2}],
                },
                summary="PAR 30 is 4.2%.", sensitive=True,
            ),
        )

    monkeypatch.setattr(models, "for_step", lambda *_args, **_kwargs: FakeClient())
    monkeypatch.setattr(agent, "execute_agent_call", execute)
    monkeypatch.setattr(history, "_ensure_table", lambda: False)
    history._MEMORY.clear()
    turn_id = history.begin_turn("c1", "alice", "Show PAR 30")
    queue = asyncio.Queue()
    state = {
        "question": "Show PAR 30", "conversation_id": "c1", "user": "alice",
        "role": "admin", "turn_id": turn_id, "history_messages": [],
        "agent_history_messages": [], "emit": queue,
        "source_policy": access.build_policy(role="admin", external_sources_enabled=True),
        "timing": {"started_at": time.perf_counter(), "source_attempts": [], "source_completions": []},
    }
    await agent.run(state)
    frames = []
    while not queue.empty():
        frames.append(await queue.get())

    assert any("event: route" in frame for frame in frames)
    assert any("event: source_start" in frame for frame in frames)
    assert any("event: source_card" in frame for frame in frames)
    assert any("event: answer" in frame and "4.2%" in frame for frame in frames)
    assert [call["tool_choice"] for call in calls] == ["required"]
    assert all("json_schema" not in call for call in calls)


@pytest.mark.anyio
async def test_outbound_policy_denial_gets_one_native_repair(monkeypatch):
    requests = []
    model_policies = []
    selections = [
        NativeToolCall(
            id="web_bad", name="search_public_web",
            arguments={"search_query": "customer ID secret-42 latest news"},
        ),
        NativeToolCall(
            id="web_good", name="search_public_web",
            arguments={"search_query": "latest RBI repo rate"},
        ),
    ]

    class FakeClient:
        async def complete(self, **kwargs):
            requests.append(kwargs)
            if kwargs.get("tool_choice") == "required":
                call = selections.pop(0)
                return LLMResult(
                    text="", model="m", provider="llamacpp", tool_calls=[call],
                    assistant_message={
                        "role": "assistant", "content": None,
                        "tool_calls": [{
                            "id": call.id, "type": "function",
                            "function": {
                                "name": call.name,
                                "arguments": json.dumps(call.arguments),
                            },
                        }],
                    },
                )
            return LLMResult(text="RBI evidence retrieved.", model="m", provider="llamacpp")

    async def execute(call, _ctx):
        if call.id == "web_bad":
            raise outbound_policy.OutboundPolicyDenied("private query denied")
        return ExecutedAgentCall(
            call=call,
            card=SourceResult(
                source="web", card_type="brief", payload={},
                summary="RBI evidence retrieved.",
            ),
        )

    def choose_model(*_args, **kwargs):
        model_policies.append(kwargs)
        return FakeClient()

    monkeypatch.setattr(models, "for_step", choose_model)
    monkeypatch.setattr(agent, "execute_agent_call", execute)
    monkeypatch.setattr(history, "_ensure_table", lambda: False)
    monkeypatch.setattr(agent.settings, "workbench_agent_max_rounds", 3)
    history._MEMORY.clear()
    turn_id = history.begin_turn("web-repair", "alice", "Search")
    queue = asyncio.Queue()
    state = {
        "question": "Search", "conversation_id": "web-repair", "user": "alice",
        "role": "admin", "turn_id": turn_id, "history_messages": [],
        "agent_history_messages": [], "emit": queue,
        "source_policy": access.build_policy(role="admin", external_sources_enabled=True),
        "timing": {
            "started_at": time.perf_counter(), "source_attempts": [],
            "source_completions": [],
        },
    }
    await agent.run(state)

    assert [request["tool_choice"] for request in requests] == ["required", "required", "none"]
    record = history.get("web-repair", user="alice")
    assert len(record.turns[0]["agent_exchanges"]) == 2
    assert "secret-42" not in str(record.turns[0]["agent_exchanges"])
    assert all(policy["sensitive"] is True for policy in model_policies)


@pytest.mark.anyio
async def test_second_outbound_policy_denial_becomes_refusal(monkeypatch):
    counter = 0

    class FakeClient:
        async def complete(self, **kwargs):
            nonlocal counter
            counter += 1
            call = NativeToolCall(
                id=f"bad_{counter}", name="search_public_web",
                arguments={"search_query": "customer ID secret-42"},
            )
            return LLMResult(
                text="", model="m", provider="llamacpp", tool_calls=[call],
                assistant_message={
                    "role": "assistant", "content": None,
                    "tool_calls": [{
                        "id": call.id, "type": "function",
                        "function": {"name": call.name, "arguments": "{}"},
                    }],
                },
            )

    async def deny(_call, _ctx):
        raise outbound_policy.OutboundPolicyDenied("private query denied")

    monkeypatch.setattr(models, "for_step", lambda *_args, **_kwargs: FakeClient())
    monkeypatch.setattr(agent, "execute_agent_call", deny)
    monkeypatch.setattr(history, "_ensure_table", lambda: False)
    monkeypatch.setattr(agent.settings, "workbench_agent_max_rounds", 3)
    history._MEMORY.clear()
    turn_id = history.begin_turn("web-refuse", "alice", "Search")
    queue = asyncio.Queue()
    state = {
        "question": "Search", "conversation_id": "web-refuse", "user": "alice",
        "role": "admin", "turn_id": turn_id, "history_messages": [],
        "agent_history_messages": [], "emit": queue,
        "source_policy": access.build_policy(role="admin", external_sources_enabled=True),
        "timing": {
            "started_at": time.perf_counter(), "source_attempts": [],
            "source_completions": [],
        },
    }
    await agent.run(state)
    frames = []
    while not queue.empty():
        frames.append(await queue.get())

    assert counter == 2
    assert any("event: refusal" in frame and "private customer" in frame for frame in frames)
