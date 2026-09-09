from __future__ import annotations

import asyncio
import json
import time

import pytest

from app.services.nlq.llm import LLMProtocolError, LLMResult, NativeToolCall
from app.services.workbench import access, agent, history, models, outbound_policy
from app.services.workbench.agent_tools import AgentToolAccessDenied
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
async def test_grouped_null_filter_receives_native_repair(monkeypatch):
    bad = NativeToolCall(
        id="bad_null",
        name="query_metrics",
        arguments={
            "metrics": ["customer_count"],
            "dimensions": ["loan_agent"],
            "filters": [{"field": "loan_agent", "op": "is_null", "value": None}],
            "period": {"relative": "all_time"},
            "order_by": {"field": "customer_count", "direction": "desc"},
            "limit": 50,
        },
    )
    good = NativeToolCall(
        id="good",
        name="query_metrics",
        arguments={
            "metrics": ["customer_count"],
            "dimensions": ["loan_agent"],
            "filters": [],
            "period": {"relative": "all_time"},
            "order_by": {"field": "customer_count", "direction": "desc"},
            "limit": 50,
        },
    )
    responses = [_result(bad), _result(good)]
    repair_seen = []

    async def select(_state, *, repair_messages=None):
        repair_seen.append(repair_messages)
        return responses.pop(0)

    monkeypatch.setattr(agent, "_select", select)
    state = _state()
    state["question"] = "list the agents with highest customer count"
    result = await agent.select_calls(state)

    assert result.tool_calls == [good]
    assert "cannot group by loan_agent while filtering" in repair_seen[1][-1]["content"]


def test_explicit_missing_value_request_allows_null_filter():
    call = NativeToolCall(
        id="missing_agent",
        name="query_metrics",
        arguments={
            "metrics": ["customer_count"],
            "dimensions": [],
            "filters": [{"field": "loan_agent", "op": "is_null", "value": None}],
            "period": {"relative": "all_time"},
        },
    )
    state = _state()
    state["question"] = "show customers without an assigned agent"

    assert agent._preflight(_result(call), state) == []


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
async def test_unauthorized_domain_is_a_policy_observation_then_fails(monkeypatch):
    """A denied tool call is shown to the model once; when the budget ends it is raised."""
    monkeypatch.setattr(agent.settings, "workbench_agent_max_rounds", 2)
    state = _state()
    state["source_policy"] = access.build_policy(
        role="admin", external_sources_enabled=False,
    )
    attempts = 0
    observed = []

    async def select(_state, *, repair_messages=None):
        nonlocal attempts
        attempts += 1
        if repair_messages is not None:
            observed.extend(
                json.loads(message["content"])
                for message in repair_messages if message.get("role") == "tool"
            )
        return _result(NativeToolCall(
            id="forged",
            name="search_curated_knowledge",
            arguments={"domain": "regulatory", "query": "RBI rules"},
        ))

    monkeypatch.setattr(agent, "_select", select)
    with pytest.raises(AgentToolAccessDenied, match="external source consent"):
        await agent.select_calls(state)
    assert attempts == 2
    assert [item["code"] for item in observed] == ["POLICY_DENIED"]
    assert "external source consent" in observed[0]["message"]
    # The denial names what remains authorized so the model can choose again.
    assert "query_metrics" in observed[0]["authorized_tools"]
    assert "search_public_web" not in observed[0]["authorized_tools"]
    assert state["_agent_budget"].rounds_used == 2
    assert state["_agent_budget"].calls_used == 2


@pytest.mark.anyio
async def test_forged_tool_name_is_a_model_visible_observation_then_fails(monkeypatch):
    from app.services.workbench.agent_tools import AgentToolNotFound

    monkeypatch.setattr(agent.settings, "workbench_agent_max_rounds", 2)
    state = _state()
    attempts = 0
    observed = []

    async def select(_state, *, repair_messages=None):
        nonlocal attempts
        attempts += 1
        if repair_messages is not None:
            observed.extend(
                json.loads(message["content"])
                for message in repair_messages if message.get("role") == "tool"
            )
        return _result(NativeToolCall(
            id="forged", name="drop_all_tables", arguments={},
        ))

    monkeypatch.setattr(agent, "_select", select)
    with pytest.raises(AgentToolNotFound):
        await agent.select_calls(state)
    assert attempts == 2
    assert [item["code"] for item in observed] == ["TOOL_NOT_FOUND"]


# --- One loop, one budget -----------------------------------------------------------------
#
# Every LLM request is one round. The helpers below script a fake provider by request
# index so a test can state exactly what the model returned on each round.


def _tool_response(*calls: NativeToolCall) -> LLMResult:
    return LLMResult(
        text="", model="m", provider="llamacpp", tool_calls=list(calls),
        assistant_message={
            "role": "assistant", "content": None,
            "tool_calls": [{
                "id": call.id, "type": "function",
                "function": {"name": call.name, "arguments": json.dumps(call.arguments)},
            } for call in calls],
        },
    )


def _text_response(text: str) -> LLMResult:
    return LLMResult(
        text=text, model="m", provider="llamacpp",
        assistant_message={"role": "assistant", "content": text},
    )


class _ScriptedClient:
    """Returns ``script[i]`` for the i-th request, recording every request."""

    def __init__(self, script):
        self.script = list(script)
        self.requests = []

    async def complete(self, **kwargs):
        self.requests.append(kwargs)
        step = self.script[len(self.requests) - 1]
        return step(kwargs) if callable(step) else step

    async def health(self):
        return {"status": "ok"}


_PAR_30 = NativeToolCall(
    id="call_1", name="query_metrics",
    arguments={"metrics": ["par_30"], "dimensions": [], "period": {"relative": "this_month"}},
)


def _card(call, **overrides):
    return ExecutedAgentCall(
        call=call,
        card=SourceResult(
            source="db", card_type="chart",
            payload={
                "title": "PAR 30", "summary": "PAR 30 is 4.2%.",
                "columns": [{"name": "value", "label": "PAR 30", "unit": "percent"}],
                "rows": [{"value": 4.2}],
            },
            summary="PAR 30 is 4.2%.", sensitive=True, **overrides,
        ),
    )


def _run_state(conversation_id: str, question: str = "Show PAR 30", *, external=True):
    history._MEMORY.clear()
    turn_id = history.begin_turn(conversation_id, "alice", question)
    return {
        "question": question, "conversation_id": conversation_id, "user": "alice",
        "role": "admin", "turn_id": turn_id, "history_messages": [],
        "agent_history_messages": [], "emit": asyncio.Queue(),
        "source_policy": access.build_policy(role="admin", external_sources_enabled=external),
        "timing": {
            "started_at": time.perf_counter(), "source_attempts": [],
            "source_completions": [],
        },
    }


async def _async(value):
    return value


def _frames(state):
    frames = []
    while not state["emit"].empty():
        frames.append(state["emit"].get_nowait())
    return frames


@pytest.fixture
def scripted(monkeypatch):
    """Install a scripted provider and an executor; returns (install, client_holder)."""
    monkeypatch.setattr(history, "_ensure_table", lambda: False)
    holder = {}

    def install(script, execute):
        client = _ScriptedClient(script)
        holder["client"] = client
        monkeypatch.setattr(models, "for_step", lambda *_args, **_kwargs: client)
        monkeypatch.setattr(agent, "execute_agent_call", execute)
        return client

    return install


def test_turn_budget_counts_every_request_and_every_attempted_call():
    budget = agent.TurnBudget(max_rounds=2, max_calls=3, deadline=time.perf_counter() + 60)
    budget.charge_round("agent_select")
    budget.charge_call(2)
    assert budget.rounds_remaining == 1
    assert budget.calls_remaining == 1
    budget.charge_round("agent_synthesize")
    with pytest.raises(agent.BudgetExhausted):
        budget.charge_round("agent_continue")
    with pytest.raises(agent.BudgetExhausted):
        budget.charge_call(2)
    # Every attempted call is counted, including the ones that overran the cap.
    assert budget.snapshot() == {
        "rounds_used": 2, "max_rounds": 2, "calls_used": 4, "max_calls": 3,
    }
    assert issubclass(agent.BudgetExhausted, LLMProtocolError)
    spent = agent.TurnBudget(max_rounds=2, max_calls=3, deadline=time.perf_counter() - 1)
    assert spent.expired
    with pytest.raises(TimeoutError):
        spent.remaining_s(10.0)


@pytest.mark.anyio
async def test_single_native_db_card_returns_to_the_model_for_final_answer(scripted):
    """One selection call with every authorized tool, then the model answers from the
    tool result. No route/select split, no narrowed schema."""
    client = scripted(
        [_tool_response(_PAR_30), _text_response("PAR 30 is 4.2%.")],
        lambda call, _ctx: _async(_card(call)),
    )
    state = _run_state("c1")
    await agent.run(state)
    frames = _frames(state)

    assert any("event: route" in frame for frame in frames)
    assert any("event: source_start" in frame for frame in frames)
    assert any("event: source_card" in frame for frame in frames)
    assert any("event: answer" in frame and "4.2%" in frame for frame in frames)
    assert [call["tool_choice"] for call in client.requests] == ["required", "auto"]
    assert [call["call_purpose"] for call in client.requests] == [
        "agent_select", "agent_continue",
    ]
    assert all("json_schema" not in call for call in client.requests)
    offered = [tool["function"]["name"] for tool in client.requests[0]["tools"]]
    assert "query_metrics" in offered and "run_validated_query" in offered
    dimensions = next(
        tool for tool in client.requests[0]["tools"]
        if tool["function"]["name"] == "query_metrics"
    )["function"]["parameters"]["properties"]["dimensions"]
    assert "maxItems" not in dimensions
    assert "month" in dimensions["items"]["enum"]
    assert state["_agent_budget"].snapshot() == {
        "rounds_used": 2, "max_rounds": 5, "calls_used": 1, "max_calls": 6,
    }


@pytest.mark.anyio
async def test_last_round_result_is_shown_to_the_model_in_a_synthesis_only_call(
    scripted, monkeypatch,
):
    """B3: with the minimum budget the tool executed on round 1 is still shown to the
    model on round 2 with tool_choice="none", and the answer is the model's text."""
    monkeypatch.setattr(agent.settings, "workbench_agent_max_rounds", 2)
    client = scripted(
        [_tool_response(_PAR_30), _text_response("PAR 30 stands at 4.2% this month.")],
        lambda call, _ctx: _async(_card(call)),
    )
    state = _run_state("min-rounds")
    await agent.run(state)

    assert [call["tool_choice"] for call in client.requests] == ["required", "none"]
    assert client.requests[1]["call_purpose"] == "agent_synthesize"
    synthesis_messages = client.requests[1]["messages"]
    assert any(
        message.get("role") == "tool" and message.get("tool_call_id") == "call_1"
        and "4.2" in message.get("content", "")
        for message in synthesis_messages
    )
    assert state["agent_final_result"].text == "PAR 30 stands at 4.2% this month."
    assert any(
        "event: answer" in frame and "stands at 4.2%" in frame for frame in _frames(state)
    )
    assert state["_agent_budget"].rounds_used == 2


@pytest.mark.anyio
async def test_failure_path_spends_exactly_max_rounds_requests(scripted, monkeypatch):
    """B1: with max_rounds=3 and a model that never repairs, the model sees exactly
    three requests, each carrying the previous observation, and the turn ends with a
    BudgetExhausted protocol error, never a fabricated call."""
    monkeypatch.setattr(agent.settings, "workbench_agent_max_rounds", 3)
    invalid = NativeToolCall(id="bad", name="query_metrics", arguments={})
    client = scripted([_tool_response(invalid)] * 3, lambda call, _ctx: _async(_card(call)))
    state = _run_state("always-invalid")

    with pytest.raises(agent.BudgetExhausted):
        await agent.run(state)

    assert [call["tool_choice"] for call in client.requests] == ["required"] * 3
    assert [
        sum(1 for message in request["messages"] if message.get("role") == "tool")
        for request in client.requests
    ] == [0, 1, 2]
    assert all(
        "INVALID_TOOL_ARGUMENTS" in message["content"]
        for message in client.requests[2]["messages"] if message.get("role") == "tool"
    )
    assert state["_agent_budget"].snapshot() == {
        "rounds_used": 3, "max_rounds": 3, "calls_used": 3, "max_calls": 6,
    }
    assert not any("finish_without_data" in frame for frame in _frames(state))


@pytest.mark.anyio
async def test_execution_error_is_returned_to_llm_for_a_cross_tool_repair(
    scripted, monkeypatch,
):
    monkeypatch.setattr(agent.settings, "workbench_agent_max_rounds", 3)
    failed = NativeToolCall(
        id="failed_metric", name="query_metrics",
        arguments={"metrics": ["par_30"], "dimensions": [], "period": {"relative": "today"}},
    )
    repaired = NativeToolCall(
        id="repaired_detail", name="run_validated_query",
        arguments={"intent": "Show governed loan details", "tables": ["gold.semantic_loan_account"]},
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

    client = scripted(
        [_tool_response(failed), _tool_response(repaired), _text_response("One governed loan.")],
        execute,
    )
    state = _run_state("execution-repair", "Show the loan details")
    await agent.run(state)

    assert [request["call_purpose"] for request in client.requests] == [
        "agent_select", "agent_select", "agent_synthesize",
    ]
    assert any(
        message.get("role") == "tool" and "metric execution failed" in message.get("content", "")
        for message in client.requests[1]["messages"]
    )
    record = history.get("execution-repair", user="alice")
    assert len(record.turns[0]["agent_exchanges"]) == 2
    replayed = str(record.turns[0]["agent_exchanges"])
    assert "metric execution failed" in replayed
    assert "repaired_detail" in replayed
    frames = _frames(state)
    assert any('"card_type": "error"' in frame for frame in frames)
    assert any("event: answer" in frame and "One governed loan" in frame for frame in frames)


@pytest.mark.anyio
async def test_catalog_context_is_recomputed_from_the_latest_tool_error(
    scripted, monkeypatch,
):
    """B4: an error naming an unknown dimension surfaces the governed one next round."""
    monkeypatch.setattr(agent.settings, "workbench_agent_max_rounds", 3)
    seen = []
    original = agent.prompts.build_agent_catalog_context

    def spy(question, catalog=None, *, supplement=""):
        seen.append(supplement)
        return original(question, catalog, supplement=supplement)

    monkeypatch.setattr(agent.prompts, "build_agent_catalog_context", spy)
    bad = NativeToolCall(
        id="bad", name="query_metrics",
        arguments={
            "metrics": ["interest_collected"], "dimensions": ["schemes"],
            "period": {"relative": "all_time"},
        },
    )
    good = NativeToolCall(
        id="good", name="query_metrics",
        arguments={
            "metrics": ["interest_collected"], "dimensions": ["scheme"],
            "period": {"relative": "all_time"},
        },
    )
    client = scripted(
        [_tool_response(bad), _tool_response(good), _text_response("Shown by scheme.")],
        lambda call, _ctx: _async(_card(call)),
    )
    state = _run_state("error-context", "interest collected")
    await agent.run(state)

    def hints(request):
        return next(
            message["content"] for message in request["messages"]
            if message.get("role") == "user" and "USER QUESTION" in message.get("content", "")
        )

    assert seen[0] == ""
    assert seen[1].startswith("unknown dimension(s): schemes")
    assert seen[2] == ""  # the successful round clears the supplement
    assert hints(client.requests[0]) != hints(client.requests[1])
    assert "must appear in `dimensions`" in hints(client.requests[1])
    # The observation itself carries the governed list, so the model can repair.
    observation = next(
        json.loads(message["content"]) for message in client.requests[1]["messages"]
        if message.get("role") == "tool"
    )
    assert observation["code"] == "INVALID_TOOL_ARGUMENTS"
    assert "scheme" in observation["message"]


@pytest.mark.anyio
async def test_model_can_call_multiple_resource_tools_before_answering(scripted, monkeypatch):
    monkeypatch.setattr(agent.settings, "workbench_agent_max_rounds", 4)
    concept = NativeToolCall(
        id="concept", name="search_curated_knowledge",
        arguments={"domain": "concepts", "query": "PAR 30 definition"},
    )

    async def execute(call, _ctx):
        if call.name == "query_metrics":
            result = SourceResult(
                source="db", card_type="chart", payload={"rows": [{"par_30": 4.2}]},
                summary="PAR 30 is 4.2%.",
            )
        else:
            result = SourceResult(
                source="knowledge", card_type="brief",
                payload={"summary": "PAR 30 means principal overdue by more than 30 days."},
                summary="PAR 30 definition.",
            )
        return ExecutedAgentCall(call=call, card=result)

    client = scripted(
        [
            _tool_response(_PAR_30), _tool_response(concept),
            _text_response("The portfolio result and definition are shown together."),
        ],
        execute,
    )
    state = _run_state("multi-tool", "Show PAR 30 and explain what it means")
    await agent.run(state)

    assert [request["call_purpose"] for request in client.requests] == [
        "agent_select", "agent_continue", "agent_continue",
    ]
    record = history.get("multi-tool", user="alice")
    assert len(record.turns[0]["agent_exchanges"]) == 2
    assert [
        exchange["calls"][0]["name"] for exchange in record.turns[0]["agent_exchanges"]
    ] == ["query_metrics", "search_curated_knowledge"]
    assert state["agent_final_result"].text.startswith("The portfolio result")


@pytest.mark.anyio
async def test_invalid_continuation_call_is_persisted_and_returned_to_model(
    scripted, monkeypatch,
):
    monkeypatch.setattr(agent.settings, "workbench_agent_max_rounds", 4)
    valid = NativeToolCall(
        id="valid", name="query_metrics",
        arguments={"metrics": ["par_30"], "dimensions": [], "period": {"relative": "today"}},
    )
    invalid_next = NativeToolCall(id="invalid_next", name="query_metrics", arguments={})
    client = scripted(
        [_tool_response(valid), _tool_response(invalid_next), _text_response("PAR 30 is 4.2%.")],
        lambda call, _ctx: _async(_card(call)),
    )
    state = _run_state("invalid-continuation")
    await agent.run(state)

    continuation_requests = [
        request for request in client.requests if request.get("call_purpose") == "agent_continue"
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
async def test_partially_invalid_batch_keeps_replay_parity(scripted, monkeypatch):
    """B2: a batch with one valid and one invalid call persists one tool message per
    call; the valid call is executed and gets its real observation."""
    monkeypatch.setattr(agent.settings, "workbench_agent_max_rounds", 3)
    invalid = NativeToolCall(id="bad", name="query_metrics", arguments={})
    client = scripted(
        [_tool_response(_PAR_30, invalid), _text_response("PAR 30 is 4.2%.")],
        lambda call, _ctx: _async(_card(call)),
    )
    state = _run_state("partial-batch")
    await agent.run(state)

    record = history.get("partial-batch", user="alice")
    exchange = record.turns[0]["agent_exchanges"][0]
    assert [call["id"] for call in exchange["calls"]] == ["call_1", "bad"]
    assert [message["tool_call_id"] for message in exchange["tools"]] == ["call_1", "bad"]
    assert json.loads(exchange["tools"][0]["content"])["status"] == "ok"
    assert json.loads(exchange["tools"][1]["content"])["code"] == "INVALID_TOOL_ARGUMENTS"
    observed = [
        message for message in client.requests[1]["messages"] if message.get("role") == "tool"
    ]
    assert [message["tool_call_id"] for message in observed] == ["call_1", "bad"]
    assert state["_agent_budget"].calls_used == 2


@pytest.mark.anyio
async def test_outbound_policy_denial_gets_one_native_repair(scripted, monkeypatch):
    monkeypatch.setattr(agent.settings, "workbench_agent_max_rounds", 3)
    model_policies = []
    web_bad = NativeToolCall(
        id="web_bad", name="search_public_web",
        arguments={"search_query": "customer ID secret-42 latest news"},
    )
    web_good = NativeToolCall(
        id="web_good", name="search_public_web",
        arguments={"search_query": "latest RBI repo rate"},
    )

    async def execute(call, _ctx):
        if call.id == "web_bad":
            raise outbound_policy.OutboundPolicyDenied("private query denied")
        return ExecutedAgentCall(
            call=call,
            card=SourceResult(
                source="web", card_type="brief", payload={}, summary="RBI evidence retrieved.",
            ),
        )

    client = scripted(
        [_tool_response(web_bad), _tool_response(web_good), _text_response("RBI evidence retrieved.")],
        execute,
    )
    real_client = client

    def choose_model(*_args, **kwargs):
        model_policies.append(kwargs)
        return real_client

    monkeypatch.setattr(models, "for_step", choose_model)
    state = _run_state("web-repair", "Search")
    await agent.run(state)

    assert [request["tool_choice"] for request in client.requests] == [
        "required", "required", "none",
    ]
    denial = next(
        json.loads(message["content"]) for message in client.requests[1]["messages"]
        if message.get("role") == "tool" and message.get("tool_call_id") == "web_bad"
    )
    assert denial["code"] == "POLICY_DENIED"
    assert denial["denied"] == {"tool": "search_public_web", "source": "web", "policy": "outbound_privacy"}
    assert "finish_without_data" in denial["authorized_tools"]
    record = history.get("web-repair", user="alice")
    assert len(record.turns[0]["agent_exchanges"]) == 2
    assert "secret-42" not in str(record.turns[0]["agent_exchanges"])
    assert all(policy["sensitive"] is True for policy in model_policies)
    # A privacy denial is not an error card the user sees; the repaired search is.
    frames = _frames(state)
    assert not any('"card_type": "error"' in frame for frame in frames)
    assert any("event: source_card" in frame and '"source": "web"' in frame for frame in frames)


@pytest.mark.anyio
async def test_unresolved_policy_denial_ends_with_an_application_refusal(scripted, monkeypatch):
    """B2: the model keeps sending private data; when the budget ends the application
    refuses in its own name. No finish_without_data call is fabricated."""
    monkeypatch.setattr(agent.settings, "workbench_agent_max_rounds", 3)

    counter = 0

    def bad(_kwargs):
        nonlocal counter
        counter += 1
        return _tool_response(NativeToolCall(
            id=f"bad_{counter}", name="search_public_web",
            arguments={"search_query": "customer ID secret-42"},
        ))

    async def deny(_call, _ctx):
        raise outbound_policy.OutboundPolicyDenied("private query denied")

    client = scripted([bad, bad, bad], deny)
    state = _run_state("web-refuse", "Search")
    await agent.run(state)
    frames = _frames(state)

    assert len(client.requests) == 3
    assert all(request["tool_choice"] == "required" for request in client.requests)
    refusal = next(
        json.loads(frame.split("data: ", 1)[1]) for frame in frames if "event: refusal" in frame
    )
    assert "private customer" in refusal["text"]
    assert refusal["origin"] == "application"
    assert refusal["reason"] == "POLICY_DENIED"
    record = history.get("web-refuse", user="alice")
    assert record.turns[0]["answer"]["origin"] == "application"
    assert len(record.turns[0]["agent_exchanges"]) == 3
    assert all(
        call["name"] == "search_public_web"
        for exchange in record.turns[0]["agent_exchanges"] for call in exchange["calls"]
    )


@pytest.mark.anyio
async def test_model_refusal_keeps_its_origin(scripted):
    finish = NativeToolCall(
        id="finish", name="finish_without_data",
        arguments={
            "outcome": "refuse", "message": "I cannot share that.", "suggestions": [],
            "reason_code": "unsafe",
        },
    )

    async def execute(call, ctx):
        from app.services.workbench.agent_executor import execute_agent_call

        return await execute_agent_call(call, ctx)

    scripted([_tool_response(finish)], execute)
    state = _run_state("model-refusal", "Give me the customer's Aadhaar")
    await agent.run(state)

    refusal = next(
        json.loads(frame.split("data: ", 1)[1])
        for frame in _frames(state) if "event: refusal" in frame
    )
    assert refusal["origin"] == "model"
    assert refusal["text"] == "I cannot share that."
    assert state["_agent_budget"].rounds_used == 1


@pytest.mark.anyio
async def test_budget_spent_after_data_answers_from_the_result_with_a_limitation(
    scripted, monkeypatch,
):
    """Nothing is retrieved until the last round; the result still reaches the user,
    marked as answered without the model's synthesis."""
    monkeypatch.setattr(agent.settings, "workbench_agent_max_rounds", 2)
    invalid = NativeToolCall(id="bad", name="query_metrics", arguments={})
    scripted(
        [_tool_response(invalid), _tool_response(_PAR_30)],
        lambda call, _ctx: _async(_card(call)),
    )
    state = _run_state("late-data")
    await agent.run(state)

    answer = next(
        json.loads(frame.split("data: ", 1)[1])
        for frame in _frames(state) if "event: answer" in frame
    )
    assert answer["status"] == "partial"
    assert answer["text"] == "PAR 30 is 4.2%."
    assert any(item["source"] == "agent" for item in answer["limitations"])
    assert "agent_final_result" not in state


@pytest.mark.anyio
async def test_deadline_is_checked_in_the_loop_condition(scripted, monkeypatch):
    monkeypatch.setattr(agent.settings, "nlq_request_budget_s", 0.0)
    client = scripted([_tool_response(_PAR_30)], lambda call, _ctx: _async(_card(call)))
    state = _run_state("deadline")
    with pytest.raises(TimeoutError):
        await agent.run(state)
    assert client.requests == []
