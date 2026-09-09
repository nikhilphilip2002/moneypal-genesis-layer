from __future__ import annotations

import asyncio
import json
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


# --- Observations are bounded; durable replay is not ---------------------------------


def _large_lookup(rows: int = 5000) -> agent_executor.ExecutedAgentCall:
    card = SourceResult(
        source="db",
        card_type="chart",
        payload={
            "columns": ["customer_id", "borrower_name", "sanction_amount"],
            "rows": [
                {
                    "customer_id": f"C{index:05d}",
                    "borrower_name": f"Customer {index}",
                    "sanction_amount": 100000 + index,
                }
                for index in range(rows)
            ],
        },
        summary=f"{rows} customers under Vanitha.",
        sensitive=True,
        lineage={"sql": "SELECT ... LIMIT 5000", "params": {"agent_name": "vanitha"}},
    )
    return agent_executor.ExecutedAgentCall(
        call=NativeToolCall(id="call_big", name="lookup_records", arguments={}),
        card=card,
    )


def test_observation_is_bounded_while_durable_replay_keeps_every_row(monkeypatch):
    monkeypatch.setattr(
        agent_executor.settings, "workbench_agent_observation_max_chars", 12_000,
        raising=False,
    )
    executed = _large_lookup()

    durable = json.loads(executed.replay_message()["content"])
    observation = json.loads(executed.observation_message()["content"])

    assert len(durable["payload"]["rows"]) == 5000
    assert len(executed.observation_message()["content"]) <= 12_000
    kept = observation["payload"]["rows"]
    assert 0 < len(kept) < 5000
    assert kept == durable["payload"]["rows"][: len(kept)]
    assert observation["truncated"]["reason"] == "observation_limit"
    assert observation["truncated"]["rows_total"] == 5000
    assert observation["truncated"]["rows_omitted"] == 5000 - len(kept)
    assert observation["summary"] == durable["summary"]
    assert observation["lineage"]["params"] == {"agent_name": "vanitha"}
    assert executed.observation_message()["tool_call_id"] == "call_big"


def test_small_results_replay_unchanged_apart_from_the_sql_prompt_trace():
    executed = _large_lookup(rows=30)
    executed.card.lineage = {
        **executed.card.lineage,
        "text_to_sql": {
            "model": "ling", "provider": "llamacpp", "attempts": 2,
            "trace": [
                {
                    "round": 1, "call_purpose": "sql_generate", "model": "ling",
                    "provider": "llamacpp",
                    "request_messages": [{"role": "system", "content": "SECRET PROMPT DDL"}],
                    "assistant_message": {"role": "assistant", "content": "{}",
                                          "reasoning_content": "thinking"},
                    "candidate_sql": "SELECT disbursement_amount FROM gold.semantic_loan_account",
                    "validation": {"status": "rejected", "error": "column does not exist"},
                },
                {
                    "round": 2, "call_purpose": "sql_repair", "model": "ling",
                    "provider": "llamacpp",
                    "request_messages": [{"role": "system", "content": "SECRET PROMPT DDL"}],
                    "candidate_sql": "SELECT sanction_amount FROM gold.semantic_loan_account",
                    "validated_sql": "SELECT sanction_amount FROM gold.semantic_loan_account LIMIT 5000",
                    "validation": {"status": "accepted", "tables": ["gold.semantic_loan_account"]},
                },
            ],
        },
    }

    durable = json.loads(executed.replay_message()["content"])
    text = executed.observation_message()["content"]
    observation = json.loads(text)

    assert "SECRET PROMPT DDL" in json.dumps(durable)
    assert "SECRET PROMPT DDL" not in text
    assert "thinking" not in text
    assert observation["payload"]["rows"] == durable["payload"]["rows"]
    assert "truncated" not in observation
    trace = observation["lineage"]["text_to_sql"]["trace"]
    assert [item["round"] for item in trace] == [1, 2]
    assert trace[0]["validation"]["status"] == "rejected"
    assert trace[1]["validated_sql"].startswith("SELECT sanction_amount")
    assert "request_messages" not in trace[0] and "assistant_message" not in trace[0]


def test_shape_observation_caps_facts_and_drops_evidence_before_clipping_summary():
    payload = {
        "status": "ok", "source": "db", "card_type": "chart",
        "payload": {"rows": []},
        "summary": "s" * 400,
        "evidence": [{"text": "e" * 300}],
        "lineage": {"sql": "x" * 300},
        "facts": [{"id": str(index)} for index in range(100)],
    }
    shaped = agent_executor.shape_observation(payload, limit_chars=450, max_facts=5)

    assert len(shaped["facts"]) == 5
    assert shaped["truncated"]["facts_omitted"] == 95
    assert shaped["truncated"]["dropped"] == ["evidence", "lineage"]
    assert len(json.dumps(shaped, separators=(",", ":"))) <= 450
    assert shaped["truncated"]["summary_clipped"] is True
    assert shaped["status"] == "ok"
