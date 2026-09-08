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
async def test_invalid_duplicate_period_is_returned_for_native_repair_not_rewritten(monkeypatch):
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
    with pytest.raises(Exception):
        await agent.select_calls(state)
    assert call.arguments["period"]["relative"] == "all_time"


@pytest.mark.anyio
@pytest.mark.parametrize(
    "question",
    [
        "interest collected monthwise till today",
        "i mean month wise",
        "show interest collected by-month",
    ],
)
async def test_application_does_not_invent_a_missing_month_dimension(monkeypatch, question):
    call = NativeToolCall(
        id="monthly",
        name="query_metrics",
        arguments={
            "metrics": ["interest_collected"],
            "dimensions": [],
            "filters": [],
            "having": [],
            "period": {
                "grain": "month", "start": None, "end": None, "relative": "all_time",
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
    assert arguments["dimensions"] == []
    assert arguments["order_by"] is None
    raw_arguments = json.loads(
        result.assistant_message["tool_calls"][0]["function"]["arguments"]
    )
    assert raw_arguments == {}


@pytest.mark.anyio
async def test_application_does_not_rewrite_a_conflicting_lifetime_period(monkeypatch):
    call = NativeToolCall(
        id="lifetime",
        name="query_metrics",
        arguments={
            "metrics": ["disbursement_total"],
            "dimensions": ["month"],
            "filters": [],
            "having": [],
            "period": {
                "grain": "month",
                "start": "2025-10-15",
                "end": "2026-09-07",
                "relative": "all_time",
            },
            "compare_to": None,
            "order_by": {"field": "month", "direction": "asc"},
            "limit": 5000,
            "as_share": False,
            "explain": False,
        },
    )
    response = _result(call)

    async def select(*_args, **_kwargs):
        return response

    monkeypatch.setattr(agent, "_select", select)
    state = _state()
    state["question"] = "show disbursement monthwise till today"
    with pytest.raises(Exception):
        await agent.select_calls(state)
    assert call.arguments["period"] == {
        "grain": "month",
        "start": "2025-10-15",
        "end": "2026-09-07",
        "relative": "all_time",
    }


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
async def test_single_native_db_card_returns_to_the_model_for_final_answer(monkeypatch):
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
    assert [call["tool_choice"] for call in calls] == ["required", "required", "auto"]
    assert [call["call_purpose"] for call in calls] == [
        "agent_route", "agent_select", "agent_continue",
    ]
    assert all("json_schema" not in call for call in calls)


@pytest.mark.anyio
async def test_execution_error_is_returned_to_llm_for_a_cross_tool_repair(monkeypatch):
    requests = []

    class FakeClient:
        async def complete(self, **kwargs):
            requests.append(kwargs)
            purpose = kwargs.get("call_purpose")
            if purpose == "agent_continue":
                return LLMResult(
                    text="One governed loan.", model="m", provider="llamacpp",
                    assistant_message={
                        "role": "assistant", "content": "One governed loan.",
                    },
                )
            if purpose == "agent_route":
                name = "query_metrics" if len(requests) == 1 else "run_validated_query"
                call = NativeToolCall(id=f"route_{len(requests)}", name=name, arguments={})
            elif len(requests) == 2:
                call = NativeToolCall(
                    id="failed_metric",
                    name="query_metrics",
                    arguments={
                        "metrics": ["par_30"],
                        "dimensions": [],
                        "period": {"relative": "today"},
                    },
                )
            else:
                call = NativeToolCall(
                    id="repaired_detail",
                    name="run_validated_query",
                    arguments={
                        "intent": "Show governed loan details",
                        "tables": ["gold.semantic_loan_account"],
                    },
                )
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

    async def execute(call, _ctx):
        if call.id == "failed_metric":
            raise RuntimeError("metric execution failed")
        return ExecutedAgentCall(
            call=call,
            card=SourceResult(
                source="db", card_type="chart",
                payload={"rows": [{"loan_account_number": "L1"}]},
                summary="One governed loan.",
                lineage={"sql": "SELECT loan_account_number FROM gold.semantic_loan_account"},
            ),
        )

    monkeypatch.setattr(models, "for_step", lambda *_args, **_kwargs: FakeClient())
    monkeypatch.setattr(agent, "execute_agent_call", execute)
    monkeypatch.setattr(history, "_ensure_table", lambda: False)
    monkeypatch.setattr(agent.settings, "workbench_agent_max_rounds", 3)
    history._MEMORY.clear()
    turn_id = history.begin_turn("execution-repair", "alice", "Show the loan details")
    state = {
        "question": "Show the loan details",
        "conversation_id": "execution-repair",
        "user": "alice",
        "role": "admin",
        "turn_id": turn_id,
        "history_messages": [],
        "agent_history_messages": [],
        "emit": asyncio.Queue(),
        "source_policy": access.build_policy(role="admin", external_sources_enabled=True),
        "timing": {
            "started_at": time.perf_counter(),
            "source_attempts": [],
            "source_completions": [],
        },
    }

    await agent.run(state)

    assert [request["call_purpose"] for request in requests] == [
        "agent_route", "agent_select", "agent_route", "agent_select", "agent_continue",
    ]
    reroute_messages = requests[2]["messages"]
    assert any(
        message.get("role") == "tool" and "metric execution failed" in message.get("content", "")
        for message in reroute_messages
    )
    record = history.get("execution-repair", user="alice")
    assert len(record.turns[0]["agent_exchanges"]) == 2
    replayed = str(record.turns[0]["agent_exchanges"])
    assert "metric execution failed" in replayed
    assert "repaired_detail" in replayed


@pytest.mark.anyio
async def test_model_can_call_multiple_resource_tools_before_answering(monkeypatch):
    requests = []
    continuation_count = 0

    class FakeClient:
        async def complete(self, **kwargs):
            nonlocal continuation_count
            requests.append(kwargs)
            purpose = kwargs.get("call_purpose")
            if purpose == "agent_route":
                call = NativeToolCall(id="route", name="query_metrics", arguments={})
            elif purpose == "agent_select":
                call = NativeToolCall(
                    id="metric",
                    name="query_metrics",
                    arguments={
                        "metrics": ["par_30"],
                        "dimensions": [],
                        "period": {"relative": "today"},
                    },
                )
            else:
                continuation_count += 1
                if continuation_count == 1:
                    call = NativeToolCall(
                        id="concept",
                        name="search_curated_knowledge",
                        arguments={"domain": "concepts", "query": "PAR 30 definition"},
                    )
                else:
                    return LLMResult(
                        text="The portfolio result and definition are shown together.",
                        model="m",
                        provider="llamacpp",
                        assistant_message={
                            "role": "assistant",
                            "content": "The portfolio result and definition are shown together.",
                        },
                    )
            return LLMResult(
                text="", model="m", provider="llamacpp", tool_calls=[call],
                assistant_message={
                    "role": "assistant", "content": None,
                    "tool_calls": [{
                        "id": call.id,
                        "type": "function",
                        "function": {
                            "name": call.name,
                            "arguments": json.dumps(call.arguments),
                        },
                    }],
                },
            )

    async def execute(call, _ctx):
        if call.name == "query_metrics":
            result = SourceResult(
                source="db",
                card_type="chart",
                payload={"rows": [{"par_30": 4.2}]},
                summary="PAR 30 is 4.2%.",
            )
        else:
            result = SourceResult(
                source="knowledge",
                card_type="brief",
                payload={"summary": "PAR 30 means principal overdue by more than 30 days."},
                summary="PAR 30 definition.",
            )
        return ExecutedAgentCall(call=call, card=result)

    monkeypatch.setattr(models, "for_step", lambda *_args, **_kwargs: FakeClient())
    monkeypatch.setattr(agent, "execute_agent_call", execute)
    monkeypatch.setattr(history, "_ensure_table", lambda: False)
    monkeypatch.setattr(agent.settings, "workbench_agent_max_rounds", 3)
    history._MEMORY.clear()
    turn_id = history.begin_turn(
        "multi-tool", "alice", "Show PAR 30 and explain what it means",
    )
    queue = asyncio.Queue()
    state = {
        "question": "Show PAR 30 and explain what it means",
        "conversation_id": "multi-tool",
        "user": "alice",
        "role": "admin",
        "turn_id": turn_id,
        "history_messages": [],
        "agent_history_messages": [],
        "emit": queue,
        "source_policy": access.build_policy(role="admin", external_sources_enabled=True),
        "timing": {
            "started_at": time.perf_counter(),
            "source_attempts": [],
            "source_completions": [],
        },
    }

    await agent.run(state)

    assert [request["call_purpose"] for request in requests] == [
        "agent_route", "agent_select", "agent_continue", "agent_continue",
    ]
    record = history.get("multi-tool", user="alice")
    assert len(record.turns[0]["agent_exchanges"]) == 2
    assert [
        exchange["calls"][0]["name"]
        for exchange in record.turns[0]["agent_exchanges"]
    ] == ["query_metrics", "search_curated_knowledge"]
    assert state["agent_final_result"].text.startswith("The portfolio result")


@pytest.mark.anyio
async def test_invalid_continuation_call_is_persisted_and_returned_to_model(monkeypatch):
    requests = []

    class FakeClient:
        async def complete(self, **kwargs):
            requests.append(kwargs)
            purpose = kwargs.get("call_purpose")
            if purpose == "agent_route":
                call = NativeToolCall(id="route", name="query_metrics", arguments={})
            elif purpose == "agent_select":
                call = NativeToolCall(
                    id="valid",
                    name="query_metrics",
                    arguments={
                        "metrics": ["par_30"],
                        "dimensions": [],
                        "period": {"relative": "today"},
                    },
                )
            elif len([item for item in requests if item.get("call_purpose") == "agent_continue"]) == 1:
                call = NativeToolCall(
                    id="invalid_next", name="query_metrics", arguments={},
                )
            else:
                return LLMResult(
                    text="PAR 30 is 4.2%.", model="m", provider="llamacpp",
                    assistant_message={"role": "assistant", "content": "PAR 30 is 4.2%."},
                )
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

    async def execute(call, _ctx):
        return ExecutedAgentCall(
            call=call,
            card=SourceResult(
                source="db", card_type="chart",
                payload={"rows": [{"par_30": 4.2}]}, summary="PAR 30 is 4.2%.",
            ),
        )

    monkeypatch.setattr(models, "for_step", lambda *_args, **_kwargs: FakeClient())
    monkeypatch.setattr(agent, "execute_agent_call", execute)
    monkeypatch.setattr(history, "_ensure_table", lambda: False)
    monkeypatch.setattr(agent.settings, "workbench_agent_max_rounds", 4)
    history._MEMORY.clear()
    turn_id = history.begin_turn("invalid-continuation", "alice", "Show PAR 30")
    state = {
        "question": "Show PAR 30",
        "conversation_id": "invalid-continuation",
        "user": "alice",
        "role": "admin",
        "turn_id": turn_id,
        "history_messages": [],
        "agent_history_messages": [],
        "emit": asyncio.Queue(),
        "source_policy": access.build_policy(role="admin", external_sources_enabled=True),
        "timing": {
            "started_at": time.perf_counter(),
            "source_attempts": [],
            "source_completions": [],
        },
    }

    await agent.run(state)

    continuation_requests = [
        request for request in requests if request.get("call_purpose") == "agent_continue"
    ]
    assert len(continuation_requests) == 2
    assert any(
        message.get("role") == "tool"
        and message.get("tool_call_id") == "invalid_next"
        and "INVALID_TOOL_ARGUMENTS" in message.get("content", "")
        for message in continuation_requests[1]["messages"]
    )
    record = history.get("invalid-continuation", user="alice")
    assert [
        exchange["calls"][0]["id"] for exchange in record.turns[0]["agent_exchanges"]
    ] == ["valid", "invalid_next"]


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
                call = (
                    NativeToolCall(
                        id="route", name="search_public_web", arguments={},
                    )
                    if kwargs.get("call_purpose") == "agent_route"
                    else selections.pop(0)
                )
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

    assert [request["tool_choice"] for request in requests] == [
        "required", "required", "required", "auto",
    ]
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
            if kwargs.get("call_purpose") == "agent_route":
                call = NativeToolCall(
                    id="route", name="search_public_web", arguments={},
                )
                return LLMResult(
                    text="", model="m", provider="llamacpp", tool_calls=[call],
                    assistant_message={"role": "assistant", "content": None},
                )
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
