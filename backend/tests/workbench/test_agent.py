from __future__ import annotations

import asyncio
import contextlib
import json
import time

import pytest

from app.services.nlq.llm import LLMProtocolError, LLMResult, NativeToolCall
from app.services.workbench import access, agent, history, models, outbound_policy
from app.services.workbench.agent_tools import AgentToolAccessDenied
from app.services.workbench.agent_executor import ExecutedAgentCall, RawQueryResult
from app.services.workbench.results import SourceResult


@pytest.fixture(autouse=True)
def _settings(monkeypatch):
    from app.mcp import postgres_client

    monkeypatch.setattr(access.settings, "workbench_external_connectors_enabled", True)
    monkeypatch.setattr(access.settings, "exa_mcp_enabled", True)
    monkeypatch.setattr(agent.settings, "workbench_agent_max_tool_calls", 6)
    monkeypatch.setitem(
        postgres_client._model_tools,
        "query",
        {
            "type": "function",
            "function": {
                "name": "query",
                "description": "Run governed read-only SQL.",
                "parameters": {
                    "type": "object",
                    "properties": {"sql": {"type": "string"}},
                    "required": ["sql"],
                    "additionalProperties": False,
                },
                "strict": True,
            },
        },
    )


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
        _result(NativeToolCall(id="bad", name="retired_query_tool", arguments={})),
        _result(NativeToolCall(
            id="good",
            name="query",
            arguments={"sql": "SELECT par_30 FROM gold.daily_loan_status LIMIT 1"},
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
    assert "TOOL_NOT_FOUND" in repair_seen[1][-1]["content"]


@pytest.mark.anyio
async def test_grouped_null_filter_receives_native_repair(monkeypatch):
    bad = NativeToolCall(
        id="bad_null",
        name="query_metrics",
        arguments={},
    )
    good = NativeToolCall(
        id="good",
        name="query",
        arguments={"sql": "SELECT agent_code FROM gold.agents WHERE agent_code IS NOT NULL"},
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
    assert "TOOL_NOT_FOUND" in repair_seen[1][-1]["content"]


def test_explicit_missing_value_request_allows_null_filter():
    call = NativeToolCall(
        id="missing_agent",
        name="query",
        arguments={"sql": "SELECT agent_code FROM gold.agents WHERE agent_code IS NULL"},
    )
    state = _state()
    state["question"] = "show customers without an assigned agent"

    assert agent._preflight(_result(call), state) == []


@pytest.mark.anyio
async def test_invalid_duplicate_period_is_returned_for_native_repair_not_rewritten(monkeypatch):
    call = NativeToolCall(
        id="year",
        name="query",
        arguments={"sql": "SELECT approved_on FROM gold.loan_accounts LIMIT 100"},
    )
    response = _result(call)

    async def select(*_args, **_kwargs):
        return response

    monkeypatch.setattr(agent, "_select", select)
    state = _state()
    state["question"] = "loan disbursed month wise in 2026"
    result = await agent.select_calls(state)
    assert result.tool_calls[0].arguments == call.arguments


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
        name="query",
        arguments={"sql": "SELECT interest_collected FROM gold.loan_repayments LIMIT 100"},
    )
    response = _result(call)

    async def select(*_args, **_kwargs):
        return response

    monkeypatch.setattr(agent, "_select", select)
    state = _state()
    state["question"] = question
    result = await agent.select_calls(state)

    arguments = result.tool_calls[0].arguments
    assert arguments == call.arguments
    raw_arguments = json.loads(
        result.assistant_message["tool_calls"][0]["function"]["arguments"]
    )
    assert raw_arguments == {}


@pytest.mark.anyio
async def test_application_does_not_rewrite_a_conflicting_lifetime_period(monkeypatch):
    call = NativeToolCall(
        id="lifetime",
        name="query",
        arguments={"sql": "SELECT amount_given FROM gold.loan_accounts LIMIT 5000"},
    )
    response = _result(call)

    async def select(*_args, **_kwargs):
        return response

    monkeypatch.setattr(agent, "_select", select)
    state = _state()
    state["question"] = "show disbursement monthwise till today"
    result = await agent.select_calls(state)
    assert result.tool_calls[0].arguments == call.arguments




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
    assert "query" in observed[0]["authorized_tools"]
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
    id="call_1", name="query",
    arguments={"sql": "SELECT par_30 FROM gold.daily_loan_status LIMIT 1"},
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


def _raw(call):
    lineage = {
        "path": "postgres_mcp",
        "sql": "SELECT par_30 FROM gold.daily_loan_status LIMIT 1",
    }
    return ExecutedAgentCall(
        call=call,
        raw_result=RawQueryResult(
            payload={
                "title": "PAR 30",
                "columns": [{
                    "name": "value", "label": "PAR 30", "unit": "percent",
                    "sensitivity": "internal",
                }],
                "rows": [{"value": 4.2}],
                "lineage": lineage,
            },
            summary="Query returned 1 row(s).",
            lineage=lineage,
            row_count=1,
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
        monkeypatch.setattr(models, "client", lambda: client)
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
async def test_new_chat_restores_system_slot_before_first_model_call(scripted, monkeypatch):
    order = []

    def response(_kwargs):
        order.append("model")
        return _text_response("Ready.")

    client = scripted([response], lambda _call, _ctx: None)
    state = _run_state("new-chat")
    state["_restore_system_slot"] = True

    async def build_bundle():
        return object()

    async def restore(bundle):
        assert bundle is not None
        order.append("cache")
        return {"outcome": "restored"}

    @contextlib.asynccontextmanager
    async def gate():
        yield

    monkeypatch.setattr(agent, "build_warmup_bundle", build_bundle)
    monkeypatch.setattr(agent, "restore_or_warm", restore)
    monkeypatch.setattr(agent, "request_gate", gate)

    await agent.run(state)

    assert order == ["cache", "model"]
    assert "_restore_system_slot" not in state
    assert len(client.requests) == 1


@pytest.mark.anyio
async def test_strict_final_answer_tool_drives_reconciled_answer(scripted):
    def final_response(request):
        observation = next(
            json.loads(message["content"])
            for message in reversed(request["messages"])
            if message.get("role") == "tool"
        )
        assert observation["query_reference"]["query_id"] == 1
        return _tool_response(NativeToolCall(
            id="final-answer",
            name="submit_final_answer",
            arguments={
                "insights": "PAR 30 is 4.2%.", "query_id": 1, "view": "kpi",
            },
        ))

    from app.services.workbench import agent_executor

    async def execute(call, context):
        if call.name == "query":
            return _raw(call)
        return await agent_executor.execute_agent_call(call, context)

    client = scripted([_tool_response(_PAR_30), final_response], execute)
    state = _run_state("structured-final")
    await agent.run(state)

    answer_frame = next(frame for frame in _frames(state) if frame.startswith("event: answer\n"))
    answer = json.loads(answer_frame.split("data: ", 1)[1])
    assert answer["text"] == "PAR 30 is 4.2%."
    assert answer["active_query_ids"] == [f"{state['turn_id']}:q1"]
    assert answer["visual_query_ids"] == [f"{state['turn_id']}:q1"]
    assert answer["query_id"] == 1
    assert answer["view"] == "kpi"
    assert answer["attribution_fallback_used"] is False
    assert client.requests[-1]["tool_choice"] == "auto"


@pytest.mark.anyio
async def test_invalid_final_answer_contract_is_repaired_once(scripted, monkeypatch):
    monkeypatch.setattr(agent.settings, "workbench_agent_max_rounds", 4)
    invalid_final = NativeToolCall(
        id="invalid-final", name="submit_final_answer",
        arguments={"insights": "", "query_id": 99, "view": "kpi"},
    )

    def repaired_final(request):
        observations = [
            json.loads(message["content"])
            for message in request["messages"] if message.get("role") == "tool"
        ]
        assert any(item.get("code") == "INVALID_TOOL_ARGUMENTS" for item in observations)
        return _tool_response(NativeToolCall(
            id="valid-final", name="submit_final_answer",
            arguments={"insights": "", "query_id": 1, "view": "kpi"},
        ))

    from app.services.workbench import agent_executor

    async def execute(call, context):
        if call.name == "query":
            return _raw(call)
        return await agent_executor.execute_agent_call(call, context)

    scripted(
        [
            _tool_response(_PAR_30), _tool_response(invalid_final), repaired_final,
        ], execute,
    )
    state = _run_state("final-repair")
    await agent.run(state)

    assert state["attribution_repairs"] == 1
    answer_frame = next(
        frame for frame in _frames(state) if frame.startswith("event: answer\n")
    )
    answer = json.loads(answer_frame.split("data: ", 1)[1])
    assert answer["text"] == ""
    assert answer["query_id"] == 1


@pytest.mark.anyio
async def test_last_round_result_is_shown_without_forcing_synthesis(
    scripted, monkeypatch,
):
    """The model sees the tool result and remains free to call a tool or return content."""
    monkeypatch.setattr(agent.settings, "workbench_agent_max_rounds", 2)
    client = scripted(
        [_tool_response(_PAR_30), _text_response("PAR 30 stands at 4.2% this month.")],
        lambda call, _ctx: _async(_card(call)),
    )
    state = _run_state("min-rounds")
    await agent.run(state)

    assert [call["tool_choice"] for call in client.requests] == ["auto", "auto"]
    assert client.requests[1]["call_purpose"] == "agent_continue"
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
    invalid = NativeToolCall(id="bad", name="retired_query_tool", arguments={})
    client = scripted([_tool_response(invalid)] * 3, lambda call, _ctx: _async(_card(call)))
    state = _run_state("always-invalid")

    with pytest.raises(agent.BudgetExhausted):
        await agent.run(state)

    assert [call["tool_choice"] for call in client.requests] == ["auto"] * 3
    assert [
        sum(1 for message in request["messages"] if message.get("role") == "tool")
        for request in client.requests
    ] == [0, 1, 2]
    assert all(
        "TOOL_NOT_FOUND" in message["content"]
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
        id="failed_metric", name="query",
        arguments={"sql": "SELECT par_30 FROM gold.daily_loan_status LIMIT 1"},
    )
    repaired = NativeToolCall(
        id="repaired_detail", name="query",
        arguments={"sql": "SELECT loan_account_number FROM gold.loan_accounts LIMIT 1"},
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
                lineage={"sql": "SELECT loan_account_number FROM gold.loan_accounts LIMIT 1"},
            ),
        )

    client = scripted(
        [_tool_response(failed), _tool_response(repaired), _text_response("One governed loan.")],
        execute,
    )
    state = _run_state("execution-repair", "Show the loan details")
    await agent.run(state)

    assert [request["call_purpose"] for request in client.requests] == [
        "agent_continue", "agent_continue", "agent_continue",
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
    assert not any('"card_type": "error"' in frame for frame in frames)
    assert any("event: query_failed" in frame for frame in frames)
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
        id="bad", name="query",
        arguments={"sql": "SELECT schemes FROM gold.loan_repayments LIMIT 100"},
    )
    good = NativeToolCall(
        id="good", name="query",
        arguments={"sql": "SELECT scheme_code FROM gold.loan_accounts LIMIT 100"},
    )

    async def execute(call, _ctx):
        if call.id == "bad":
            raise RuntimeError("unknown column schemes; did you mean scheme")
        return _card(call)

    client = scripted(
        [_tool_response(bad), _tool_response(good), _text_response("Shown by scheme.")],
        execute,
    )
    state = _run_state("error-context", "interest collected")
    await agent.run(state)

    def hints(request):
        return next(
            message["content"] for message in request["messages"]
            if message.get("role") == "user" and "USER QUESTION" in message.get("content", "")
        )

    assert seen[0] == ""
    assert seen[1].startswith("unknown column schemes")
    assert seen[2] == ""  # the successful round clears the supplement
    assert hints(client.requests[0]) != hints(client.requests[1])
    assert "must appear in `dimensions`" in hints(client.requests[1])
    # The observation itself carries the governed list, so the model can repair.
    observation = next(
        json.loads(message["content"]) for message in client.requests[1]["messages"]
        if message.get("role") == "tool"
    )
    assert observation["code"] == "SOURCE_UNAVAILABLE"
    assert "scheme" in observation["message"]


@pytest.mark.anyio
async def test_model_can_call_multiple_resource_tools_before_answering(scripted, monkeypatch):
    monkeypatch.setattr(agent.settings, "workbench_agent_max_rounds", 4)
    concept = NativeToolCall(
        id="concept", name="search_curated_knowledge",
        arguments={"domain": "concepts", "query": "PAR 30 definition"},
    )

    async def execute(call, _ctx):
        if call.name == "query":
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
        "agent_continue", "agent_continue", "agent_continue",
    ]
    record = history.get("multi-tool", user="alice")
    assert len(record.turns[0]["agent_exchanges"]) == 2
    assert [
        exchange["calls"][0]["name"] for exchange in record.turns[0]["agent_exchanges"]
    ] == ["query", "search_curated_knowledge"]
    assert state["agent_final_result"].text.startswith("The portfolio result")


@pytest.mark.anyio
async def test_invalid_continuation_call_is_persisted_and_returned_to_model(
    scripted, monkeypatch,
):
    monkeypatch.setattr(agent.settings, "workbench_agent_max_rounds", 4)
    valid = NativeToolCall(
        id="valid", name="query",
        arguments={"sql": "SELECT par_30 FROM gold.daily_loan_status LIMIT 1"},
    )
    invalid_next = NativeToolCall(
        id="invalid_next", name="retired_query_tool", arguments={},
    )
    client = scripted(
        [_tool_response(valid), _tool_response(invalid_next), _text_response("PAR 30 is 4.2%.")],
        lambda call, _ctx: _async(_card(call)),
    )
    state = _run_state("invalid-continuation")
    await agent.run(state)

    continuation_requests = [
        request for request in client.requests if request.get("call_purpose") == "agent_continue"
    ]
    assert len(continuation_requests) == 3
    assert any(
        message.get("role") == "tool"
        and message.get("tool_call_id") == "invalid_next"
        and "TOOL_NOT_FOUND" in message.get("content", "")
        for message in continuation_requests[2]["messages"]
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
    invalid = NativeToolCall(id="bad", name="retired_query_tool", arguments={})
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
    assert json.loads(exchange["tools"][1]["content"])["code"] == "TOOL_NOT_FOUND"
    observed = [
        message for message in client.requests[1]["messages"] if message.get("role") == "tool"
    ]
    assert [message["tool_call_id"] for message in observed] == ["call_1", "bad"]
    assert state["_agent_budget"].calls_used == 2


@pytest.mark.anyio
async def test_outbound_policy_denial_gets_one_native_repair(scripted, monkeypatch):
    monkeypatch.setattr(agent.settings, "workbench_agent_max_rounds", 3)
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

    def choose_model():
        return real_client

    monkeypatch.setattr(models, "client", choose_model)
    state = _run_state("web-repair", "Search")
    await agent.run(state)

    assert [request["tool_choice"] for request in client.requests] == [
        "auto", "auto", "auto",
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
    assert all(request["tool_choice"] == "auto" for request in client.requests)
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
    invalid = NativeToolCall(id="bad", name="retired_query_tool", arguments={})
    scripted(
        [_tool_response(invalid), _tool_response(_PAR_30)],
        lambda call, _ctx: _async(_card(call)),
    )
    state = _run_state("late-data")
    await agent.run(state)

    answer = next(
        json.loads(frame.split("data: ", 1)[1])
        for frame in _frames(state)
        if "event: answer" in frame and '"status"' in frame
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
