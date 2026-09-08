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
async def test_lifetime_flow_phrase_canonicalizes_conflicting_period(monkeypatch):
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
    result = await agent.select_calls(state)

    period = result.tool_calls[0].arguments["period"]
    assert period == {
        "grain": "month", "start": None, "end": None, "relative": "all_time",
    }
    raw_arguments = json.loads(
        result.assistant_message["tool_calls"][0]["function"]["arguments"]
    )
    assert raw_arguments["period"] == period


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
    assert [call["tool_choice"] for call in calls] == ["required", "required"]
    assert [call["call_purpose"] for call in calls] == ["agent_route", "agent_select"]
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
        "required", "required", "required", "none",
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


@pytest.mark.parametrize(
    ("question", "expected_dimension", "expected_group_col"),
    [
        ("interest collected schemewise", "scheme", "scheme_code"),
        ("interest collected scheme wise", "scheme", "scheme_code"),
        ("interest collected scheme-wise", "scheme", "scheme_code"),
        ("interest collected by scheme", "scheme", "scheme_code"),
        ("disbursements branchwise", "branch", "application_branch_code"),
        ("disbursements branch wise", "branch", "application_branch_code"),
        ("disbursements branch-wise", "branch", "application_branch_code"),
        ("disbursements by branch", "branch", "application_branch_code"),
        ("disbursements productwise", "product", "product_code"),
        ("disbursements product wise", "product", "product_code"),
        ("disbursements product-wise", "product", "product_code"),
        ("disbursements by product", "product", "product_code"),
        ("disbursements monthwise", "month", "disbursement_date"),
        ("disbursements month wise", "month", "disbursement_date"),
        ("disbursements month-wise", "month", "disbursement_date"),
        ("disbursements by month", "month", "disbursement_date"),
    ],
)
def test_explicit_non_time_grouping_preserved_and_compiled(
    question: str, expected_dimension: str, expected_group_col: str,
):
    from app.services.nlq.catalog import get_catalog
    from app.services.nlq.compiler import compile_spec
    from app.services.nlq.contracts import Period, QuerySpec

    cat = get_catalog()
    metric = "interest_collected" if "interest" in question else "disbursement_total"
    call = NativeToolCall(
        id="c1",
        name="query_metrics",
        arguments={
            "metrics": [metric],
            "dimensions": [],
            "period": {"relative": "all_time"},
        },
    )
    result = _result(call)
    state = {"question": question, "_agent_catalog": cat}
    agent._canonicalize_native_arguments(result, state)

    # 1. Assert returned tool arguments contain the explicit dimension
    assert expected_dimension in call.arguments["dimensions"]

    # 2. Assert compiling QuerySpec produces valid SQL with GROUP BY
    spec = QuerySpec(
        metrics=[metric],
        dimensions=call.arguments["dimensions"],
        period=Period(relative="all_time"),
    )
    compiled = compile_spec(spec, cat)
    assert "GROUP BY" in compiled.sql
    assert expected_group_col in compiled.sql


@pytest.mark.anyio
@pytest.mark.parametrize(
    "followup_question",
    [
        "include tenure and santioned amount with the above details",
        "also add tenure and sanction amount",
        "with the above details, include tenure and sanction amount",
        "add tenure and sanctioned amount to the above",
    ],
)
async def test_multiturn_elliptical_followup_preserves_bindings(
    monkeypatch, followup_question: str,
):
    from app.services.nlq.catalog import get_catalog
    from app.services.nlq.validator import ValidationError, validate
    from app.services.workbench.agent_contracts import RunValidatedQueryArguments

    history._MEMORY.clear()
    monkeypatch.setattr(history, "_ensure_table", lambda: False)

    conv_id = "test-multiturn-conv"
    user = "analyst"

    # Turn 1: Lookup customers under vanitha
    turn_1 = history.begin_turn(conv_id, user, "customers under vanitha")
    history.set_data_binding(
        conv_id, user, turn_1,
        {
            "tool": "lookup_records",
            "tables": ["gold.semantic_loan_account"],
            "output_fields": ["customer_id", "customer_name"],
            "filters": [{"field": "agent_name", "operator": "eq", "value": "vanitha"}],
            "entity": {"selector": "agent_name", "value": "vanitha", "detail": "agent_customers"},
            "intent": "customers under agent vanitha",
        },
    )
    history.complete_turn(conv_id, user, turn_1)

    # Verify data query binding was persisted
    last_binding = history.get_last_data_binding(conv_id, user=user)
    assert last_binding is not None
    assert last_binding["entity"]["value"] == "vanitha"

    # Turn 2: Follow-up requesting tenure and sanctioned amount
    turn_2 = history.begin_turn(conv_id, user, followup_question)
    state = {
        "question": followup_question,
        "conversation_id": conv_id,
        "user": user,
        "role": "admin",
        "turn_id": turn_2,
        "history_messages": [],
        "agent_history_messages": [],
        "source_policy": access.build_policy(role="admin", external_sources_enabled=True),
        "_agent_catalog": get_catalog(),
    }

    # Test follow-up resolution and canonicalization
    class RouteClient:
        async def complete(self, **kwargs):
            purpose = kwargs.get("call_purpose")
            if purpose == "agent_route":
                return LLMResult(
                    text="", model="m", provider="llamacpp",
                    tool_calls=[NativeToolCall(id="r1", name="run_validated_query", arguments={})],
                    assistant_message={"role": "assistant", "content": None},
                )
            # Argument fill stage
            call = NativeToolCall(
                id="f1",
                name="run_validated_query",
                arguments={
                    "intent": followup_question,
                    "tables": ["gold.semantic_loan_account"],
                },
            )
            return LLMResult(
                text="", model="m", provider="llamacpp",
                tool_calls=[call],
                assistant_message={"role": "assistant", "content": None, "tool_calls": [{
                    "id": "f1", "type": "function",
                    "function": {"name": "run_validated_query", "arguments": json.dumps(call.arguments)},
                }]},
            )

    monkeypatch.setattr(models, "for_step", lambda *_args, **_kwargs: RouteClient())
    selection = await agent.select_calls(state)

    assert len(selection.tool_calls) == 1
    selected_call = selection.tool_calls[0]
    assert selected_call.name == "run_validated_query"
    args = RunValidatedQueryArguments.model_validate(selected_call.arguments)

    # Assert retained table
    assert args.tables == ["gold.semantic_loan_account"]

    # Assert retained entity constraint (vanitha) and retained/added fields in resolved intent
    assert "vanitha" in args.intent
    assert "customer ID" in args.intent
    assert "customer name" in args.intent
    assert "sanction amount" in args.intent
    assert "tenure" in args.intent

    # Assert table-scoped validation rejects wrong-table column disbursement_amount
    invalid_sql = (
        "SELECT lam.customer_id, lam.customer_name, lam.disbursement_amount, lam.number_of_emis "
        "FROM gold.semantic_loan_account AS lam WHERE LOWER(lam.agent_name) LIKE '%vanitha%' LIMIT 100"
    )
    with pytest.raises(ValidationError, match="column 'disbursement_amount' does not exist on gold.semantic_loan_account"):
        validate(invalid_sql, allow_pii=True, allowed_pii_columns={"customer_name", "agent_name"})

    # Assert table-scoped validation accepts real governed columns
    valid_sql = (
        "SELECT lam.customer_id, lam.customer_name, lam.sanction_amount, lam.number_of_emis "
        "FROM gold.semantic_loan_account AS lam WHERE LOWER(lam.agent_name) LIKE '%vanitha%' LIMIT 100"
    )
    validated = validate(valid_sql, allow_pii=True, allowed_pii_columns={"customer_name", "agent_name"})
    assert validated.sql
