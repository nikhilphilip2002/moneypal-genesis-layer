from __future__ import annotations

import asyncio

import pytest

from app.services.nlq.catalog import get_catalog
from app.services.nlq.llm import NativeToolCall
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
async def test_validated_call_dispatches_and_replay_is_bounded(monkeypatch):
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
    assert "rows" not in replay
    assert "sql" not in replay
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
