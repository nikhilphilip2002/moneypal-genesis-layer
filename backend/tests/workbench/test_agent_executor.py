from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from app.services.nlq.catalog import get_catalog
from app.services.nlq.llm import NativeToolCall
from app.services.nlq.text_to_sql import SqlAttempt
from app.services.workbench import access, agent_executor
from app.services.workbench.agent_executor import AgentExecutionContext, AgentToolTimeout
from app.services.workbench.results import SourceResult


@pytest.fixture(autouse=True)
def _connectors(monkeypatch):
    monkeypatch.setattr(access.settings, "workbench_external_connectors_enabled", True)
    monkeypatch.setattr(access.settings, "exa_mcp_enabled", True)


def _context(*, external=True):
    return AgentExecutionContext(
        user="alice",
        role="admin",
        conversation_id="c1",
        turn_id="t1",
        source_policy=access.build_policy(
            role="admin", external_sources_enabled=external,
        ),
        deadline_s=5.0,
        catalog=get_catalog(),
    )


@pytest.mark.anyio
async def test_validated_call_dispatches_and_replay_is_lossless(monkeypatch):
    async def fake_handler(args, _ctx):
        assert args.metrics == ["par_30"]
        return SourceResult(
            source="db",
            card_type="chart",
            payload={"rows": [{"private": "never replay this"}]},
            summary="PAR 30 is 4.2%.",
            lineage={"sql": "never replay this"},
        )

    monkeypatch.setitem(agent_executor._HANDLERS, "query_metrics", fake_handler)
    executed = await agent_executor.execute_agent_call(
        NativeToolCall(
            id="call_1",
            name="query_metrics",
            arguments={
                "metrics": ["par_30"],
                "dimensions": [],
                "period": {"relative": "this_month"},
            },
        ),
        _context(),
    )

    replay = executed.replay_payload()
    assert replay["status"] == "ok"
    assert replay["summary"] == "PAR 30 is 4.2%."
    assert replay["payload"]["rows"] == [{"private": "never replay this"}]
    assert replay["lineage"] == {"sql": "never replay this"}
    assert executed.replay_message()["tool_call_id"] == "call_1"


@pytest.mark.anyio
async def test_terminal_call_executes_no_data_handler():
    executed = await agent_executor.execute_agent_call(
        NativeToolCall(
            id="call_2",
            name="finish_without_data",
            arguments={
                "outcome": "clarify",
                "message": "Which period?",
                "suggestions": ["This month"],
                "reason_code": None,
            },
        ),
        _context(),
    )
    assert executed.card is None
    assert executed.terminal["outcome"] == "clarify"


@pytest.mark.anyio
async def test_catalog_inspection_returns_governed_columns_and_declared_metadata():
    executed = await agent_executor.execute_agent_call(
        NativeToolCall(
            id="catalog_1",
            name="inspect_loan_catalog",
            arguments={
                "topic": "sanction amount and number of EMIs",
                "tables": ["gold.semantic_loan_account"],
            },
        ),
        _context(),
    )

    payload = executed.card.payload
    loan_table = next(
        table for table in payload["tables"]
        if table["name"] == "gold.semantic_loan_account"
    )
    column_names = {column["name"] for column in loan_table["columns"]}
    assert "sanction_amount" in column_names
    assert "number_of_emis" in column_names
    assert payload["catalog_version"] == get_catalog().version
    assert executed.replay_payload()["payload"] == payload


@pytest.mark.anyio
async def test_validated_query_exposes_nested_llm_trace_and_disables_regex_shortcuts(
    monkeypatch,
):
    generation_kwargs = {}
    trace = [{
        "round": 1,
        "request_messages": [{"role": "user", "content": "show details"}],
        "assistant_message": {"role": "assistant", "content": '{"sql":"SELECT 1"}'},
        "candidate_sql": "SELECT 1",
        "validated_sql": "SELECT 1",
        "validation": {"status": "accepted", "tables": []},
    }]

    async def generate(_intent, **kwargs):
        generation_kwargs.update(kwargs)
        return SqlAttempt(
            sql="SELECT 1", validated=True, attempts=1,
            model="local-model", provider="llamacpp", trace=trace,
        )

    chart = SimpleNamespace(
        lineage=SimpleNamespace(model_dump=lambda mode: {"sql": "SELECT 1"}),
        model_dump=lambda mode: {"rows": [{"value": 1}]},
        summary="One row.",
    )
    monkeypatch.setattr(agent_executor.text_to_sql, "generate", generate)
    monkeypatch.setattr(agent_executor, "run_sql", lambda *_args, **_kwargs: chart)

    executed = await agent_executor.execute_agent_call(
        NativeToolCall(
            id="sql_1",
            name="run_validated_query",
            arguments={"intent": "show details", "tables": []},
        ),
        _context(),
    )

    assert generation_kwargs["allow_reviewed_shortcuts"] is False
    nested = executed.replay_payload()["lineage"]["text_to_sql"]
    assert nested["trace"] == trace
    assert nested["model"] == "local-model"


@pytest.mark.anyio
async def test_handler_timeout_is_typed(monkeypatch):
    async def stalled(_args, _ctx):
        await asyncio.sleep(1)

    monkeypatch.setitem(agent_executor._HANDLERS, "query_metrics", stalled)
    context = _context()
    context = AgentExecutionContext(
        user=context.user,
        role=context.role,
        conversation_id=context.conversation_id,
        turn_id=context.turn_id,
        source_policy=context.source_policy,
        deadline_s=0.001,
        catalog=context.catalog,
    )
    with pytest.raises(AgentToolTimeout):
        await agent_executor.execute_agent_call(
            NativeToolCall(
                id="call_3",
                name="query_metrics",
                arguments={
                    "metrics": ["par_30"],
                    "dimensions": [],
                    "period": {"relative": "this_month"},
                },
            ),
            context,
        )


@pytest.mark.anyio
async def test_web_call_is_reauthorized_before_handler(monkeypatch):
    called = False

    async def fake_handler(_args, _ctx):
        nonlocal called
        called = True

    monkeypatch.setitem(agent_executor._HANDLERS, "search_public_web", fake_handler)
    with pytest.raises(Exception, match="external source consent"):
        await agent_executor.execute_agent_call(
            NativeToolCall(
                id="call_4",
                name="search_public_web",
                arguments={"search_query": "latest RBI repo rate"},
            ),
            _context(external=False),
        )
    assert called is False


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("name", "arguments", "source"),
    [
        (
            "query_metrics",
            {"metrics": ["par_30"], "dimensions": [], "period": {"relative": "today"}},
            "db",
        ),
        (
            "lookup_records",
            {"selector": "customer_id", "value": "42", "detail": "customer_summary"},
            "db",
        ),
        ("run_analysis", {"analysis_id": "portfolio_health"}, "db"),
        ("create_worklist", {"worklist_id": "collections_today"}, "db"),
        ("generate_briefing", {"persona_id": "ceo"}, "db"),
        ("run_validated_query", {"intent": "catalog miss", "tables": []}, "db"),
        (
            "inspect_loan_catalog",
            {"topic": "sanction amount and tenure", "tables": []},
            "schema",
        ),
        (
            "search_curated_knowledge",
            {"domain": "concepts", "query": "PAR 30"},
            "knowledge",
        ),
        ("search_public_web", {"search_query": "latest RBI repo rate"}, "web"),
    ],
)
async def test_each_nonterminal_tool_dispatches_to_its_registered_handler(
    monkeypatch, name, arguments, source,
):
    seen = []

    async def handler(parsed, _ctx):
        seen.append(type(parsed).__name__)
        return SourceResult(source=source, card_type="brief", payload={}, summary="ok")

    monkeypatch.setitem(agent_executor._HANDLERS, name, handler)
    result = await agent_executor.execute_agent_call(
        NativeToolCall(id=f"call_{name}", name=name, arguments=arguments),
        _context(),
    )
    assert result.card.summary == "ok"
    assert seen
