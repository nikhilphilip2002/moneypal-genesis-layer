from __future__ import annotations

import asyncio
import json

import pytest

from app.core.tool_names import (
    ASK_CLARIFICATION,
    QUERY,
    SEARCH_CURATED_KNOWLEDGE,
    SEARCH_PUBLIC_WEB,
    VISUALIZE_RESULT,
)
from app.services.nlq.catalog import get_catalog
from app.services.nlq.llm import NativeToolCall
from app.services.workbench import access, agent_executor
from app.services.workbench.agent_executor import (
    AgentExecutionContext,
    AgentExecutionError,
    AgentToolTimeout,
    RawQueryResult,
)
from app.services.workbench.results import SourceResult


@pytest.fixture(autouse=True)
def _connectors(monkeypatch):
    from app.mcp import postgres_client

    monkeypatch.setattr(
        access.settings, "workbench_external_connectors_enabled", True
    )
    monkeypatch.setattr(access.settings, "exa_mcp_enabled", True)
    monkeypatch.setitem(
        postgres_client._model_tools,
        QUERY,
        {
            "type": "function",
            "function": {
                "name": QUERY,
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


def _context(*, external=True):
    return AgentExecutionContext(
        user="alice",
        role="admin",
        conversation_id="c1",
        turn_id="t1",
        source_policy=access.build_policy(
            role="admin",
            external_sources_enabled=external,
        ),
        deadline_s=5.0,
        catalog=get_catalog(),
    )


@pytest.mark.anyio
async def test_validated_call_dispatches_and_replay_is_lossless(monkeypatch):
    async def fake_handler(call, _ctx):
        assert call.arguments == {
            "sql": "SELECT par_30 FROM gold.daily_loan_status LIMIT 1"
        }
        return RawQueryResult(
            payload={"rows": [{"private": "never replay this"}]},
            summary="PAR 30 is 4.2%.",
            lineage={"sql": "never replay this"},
            row_count=1,
        )

    monkeypatch.setattr(agent_executor, "_execute_postgres_mcp", fake_handler)
    executed = await agent_executor.execute_agent_call(
        NativeToolCall(
            id="call_1",
            name=QUERY,
            arguments={
                "sql": "SELECT par_30 FROM gold.daily_loan_status LIMIT 1"
            },
        ),
        _context(),
    )

    replay = executed.result_payload()
    assert replay["status"] == "ok"
    assert replay["summary"] == "PAR 30 is 4.2%."
    assert replay["payload"]["rows"] == [{"private": "never replay this"}]
    assert replay["lineage"] == {"sql": "never replay this"}
    assert executed.observation_message()["tool_call_id"] == "call_1"


@pytest.mark.anyio
async def test_database_query_reference_reaches_mcp_and_observation(
    monkeypatch,
):
    from app.mcp import postgres_client

    seen_meta = None

    async def call_tool(_name, _arguments, *, meta=None):
        nonlocal seen_meta
        seen_meta = meta
        return {
            "status": "ok",
            "rows": [{"value": 1}],
            "columns": ["value"],
            "row_count": 1,
            "duration_ms": 2,
            "validated_sql": "SELECT 1",
            "citations": [{"document": "original"}],
            "lineage": {"upstream": "original"},
        }

    monkeypatch.setattr(postgres_client, "call_tool", call_tool)
    context = _context()
    context = AgentExecutionContext(
        user=context.user,
        role=context.role,
        conversation_id=context.conversation_id,
        turn_id=context.turn_id,
        source_policy=context.source_policy,
        deadline_s=context.deadline_s,
        catalog=context.catalog,
        query_id="t1:q1",
        attempt_id="t1:q1:a1",
    )
    executed = await agent_executor.execute_agent_call(
        NativeToolCall(
            id="provider-call", name=QUERY, arguments={"sql": "SELECT 1"}
        ),
        context,
    )

    assert seen_meta is not None
    assert seen_meta["workbench_query_id"] == "t1:q1"
    assert seen_meta["workbench_attempt_id"] == "t1:q1:a1"
    assert json.loads(executed.observation_message()["content"])[
        "query_reference"
    ] == {
        "query_id": 1,
        "attempt": 1,
    }

    observation = json.loads(executed.observation_message()["content"])
    assert observation["payload"]["citations"] == [{"document": "original"}]
    assert observation["payload"]["lineage"] == {"upstream": "original"}
    assert observation["payload"]["validated_sql"] == "SELECT 1"


@pytest.mark.anyio
async def test_terminal_call_executes_no_data_handler():
    executed = await agent_executor.execute_agent_call(
        NativeToolCall(
            id="call_2",
            name=ASK_CLARIFICATION,
            arguments={'suggestions': ['This month'], 'question': 'Which period?'},
        ),
        _context(),
    )
    assert executed.card is None
    assert executed.terminal is not None
    assert executed.terminal["outcome"] == "clarify"


@pytest.mark.anyio
async def test_visualization_call_is_nonterminal():
    executed = await agent_executor.execute_agent_call(
        NativeToolCall(
            id="call-final",
            name=VISUALIZE_RESULT,
            arguments={'query_id': 1, 'view': 'kpi'},
        ),
        _context(),
    )

    assert executed.card is None
    assert executed.terminal is None
    assert executed.visual == {"query_id": 1, "view": "kpi"}
    assert json.loads(executed.observation_message()["content"]) == {"success": True}


@pytest.mark.anyio
async def test_handler_timeout_is_typed(monkeypatch):
    async def stalled(_call, _ctx):
        await asyncio.sleep(1)

    monkeypatch.setattr(agent_executor, "_execute_postgres_mcp", stalled)
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
                name=QUERY,
                arguments={"sql": "SELECT 1"},
            ),
            context,
        )


@pytest.mark.anyio
async def test_postgres_statement_timeout_keeps_typed_retry_feedback(
    monkeypatch,
):
    from app.mcp import postgres_client

    async def timed_out(*_args, **_kwargs):
        return {
            "status": "error",
            "code": "QUERY_TIMEOUT",
            "message": "Rewrite it to scan less data and do not repeat the same SQL.",
            "detail": "QueryCanceled: canceling statement due to statement timeout",
            "retryable": True,
        }

    monkeypatch.setattr(postgres_client, "call_tool", timed_out)
    call = NativeToolCall(
        id="call-timeout", name=QUERY, arguments={"sql": "SELECT 1"}
    )

    with pytest.raises(AgentExecutionError) as caught:
        await agent_executor._execute_postgres_mcp(call, _context())

    assert caught.value.code == "QUERY_TIMEOUT"
    assert caught.value.retryable is True
    assert "do not repeat the same SQL" in str(caught.value)


@pytest.mark.anyio
async def test_postgres_mcp_rejects_mismatched_returned_query_identity(
    monkeypatch,
):
    from app.mcp import postgres_client

    async def mismatched(*_args, **_kwargs):
        return {
            "status": "ok",
            "rows": [{"value": 1}],
            "columns": ["value"],
            "query_id": "another-turn:q9",
            "attempt_id": "another-turn:q9:a1",
        }

    monkeypatch.setattr(postgres_client, "call_tool", mismatched)
    context = _context()
    context = AgentExecutionContext(
        user=context.user,
        role=context.role,
        conversation_id=context.conversation_id,
        turn_id=context.turn_id,
        source_policy=context.source_policy,
        deadline_s=context.deadline_s,
        catalog=context.catalog,
        query_id="t1:q1",
        attempt_id="t1:q1:a1",
    )

    with pytest.raises(
        AgentExecutionError, match="mismatched query identifier"
    ):
        await agent_executor.execute_agent_call(
            NativeToolCall(
                id="call-mismatch", name=QUERY, arguments={"sql": "SELECT 1"}
            ),
            context,
        )


@pytest.mark.anyio
async def test_web_call_is_reauthorized_before_handler(monkeypatch):
    from app.mcp import workbench_client

    called = False

    async def fake_call(*_args, **_kwargs):
        nonlocal called
        called = True

    monkeypatch.setattr(workbench_client, "call_tool", fake_call)
    with pytest.raises(Exception, match="external source consent"):
        await agent_executor.execute_agent_call(
            NativeToolCall(
                id="call_4",
                name=SEARCH_PUBLIC_WEB,
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
            SEARCH_CURATED_KNOWLEDGE,
            {"domain": "concepts", "query": "PAR 30"},
            "knowledge",
        ),
        (SEARCH_PUBLIC_WEB, {"search_query": "latest RBI repo rate"}, "web"),
    ],
)
async def test_each_nonterminal_tool_dispatches_through_in_memory_mcp(
    monkeypatch,
    name,
    arguments,
    source,
):
    from app.mcp import workbench_client

    seen = {}

    async def call_tool(tool_name, parsed_arguments, *, context):
        seen["name"] = tool_name
        seen["arguments"] = parsed_arguments
        seen["context"] = context
        card = SourceResult(
            source=source, card_type="brief", payload={}, summary="ok"
        )
        return {"kind": "card", "card": card.as_dict()}

    monkeypatch.setattr(workbench_client, "call_tool", call_tool)
    result = await agent_executor.execute_agent_call(
        NativeToolCall(id=f"call_{name}", name=name, arguments=arguments),
        _context(),
    )
    assert result.card is not None
    assert result.card.summary == "ok"
    assert seen["name"] == name
    assert seen["arguments"] == arguments
    assert seen["context"].conversation_id == "c1"


# --- Observations are bounded; durable replay is not ---------------------------------


def _large_lookup(rows: int = 5000) -> agent_executor.ExecutedAgentCall:
    raw_result = RawQueryResult(
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
        lineage={
            "sql": "SELECT ... LIMIT 5000",
            "params": {"agent_name": "vanitha"},
        },
        row_count=rows,
    )
    return agent_executor.ExecutedAgentCall(
        call=NativeToolCall(id="call_big", name=QUERY, arguments={}),
        raw_result=raw_result,
    )


@pytest.mark.parametrize("large_cell", [False, True])
@pytest.mark.parametrize("complete", [False, True])
def test_query_preview_keeps_reference_and_durable_rows(
    monkeypatch, large_cell, complete,
):
    monkeypatch.setattr(
        agent_executor.settings,
        "workbench_agent_observation_max_chars",
        5_000,
        raising=False,
    )
    executed = _large_lookup()
    executed.query_id = "t1:q1"
    executed.attempt_id = "t1:q1:a1"
    assert executed.raw_result is not None
    original = executed.raw_result
    if large_cell:
        original.payload["rows"][0]["borrower_name"] = "x" * 10000
    executed.raw_result = RawQueryResult(
        payload=original.payload,
        summary=original.summary,
        lineage=original.lineage,
        row_count=original.row_count,
        complete=complete,
        observation_payload={
            **original.payload,
            "warnings": [] if complete else ["More rows match the query."],
        },
    )

    from app.services.workbench import history

    monkeypatch.setattr(history, "_ensure_table", lambda: False)
    monkeypatch.setattr(history, "_MEMORY", {})
    history.begin_turn("c1", "alice", "Question")
    executed.context = _context()
    durable = json.dumps(
        executed.result_payload(), default=str, separators=(",", ":")
    )
    content = executed.observation_message()["content"]
    observation = json.loads(content)
    assert len(content) <= 2000
    assert observation["query_reference"] == {"query_id": 1, "attempt": 1}
    assert observation["row_count"] == 5000
    assert observation["complete"] is complete
    assert observation["preview_only"] is True
    assert len(observation["payload"]["rows"]) <= 5
    assert observation["payload"]["columns"] == original.payload["columns"]
    assert observation["payload"]["warnings"] == (
        [] if complete else ["More rows match the query."]
    )
    assert observation["presentation"]["query_id"] == 1
    assert observation["presentation"]["view"] == "table"
    assert observation["presentation"]["uses_full_stored_result"] is True
    assert observation["output_reference"] == {
        "tool": "read_tool_output",
        "id": "call_big",
        "total_length": len(durable),
        "offset": 0,
    }
    assert history._MEMORY[("alice", "c1")].tool_outputs == {
        "call_big": durable
    }


def test_small_results_replay_unchanged():
    executed = _large_lookup(rows=3)

    durable = executed.result_payload()
    text = executed.observation_message()["content"]
    observation = json.loads(text)

    assert observation["payload"]["rows"] == durable["payload"]["rows"]
    assert "truncated" not in observation


def test_shape_observation_caps_facts_and_drops_evidence_before_clipping_summary():
    payload = {
        "status": "ok",
        "source": "db",
        "card_type": "chart",
        "payload": {"rows": []},
        "summary": "s" * 400,
        "evidence": [{"text": "e" * 300}],
        "lineage": {"sql": "x" * 300},
        "facts": [{"id": str(index)} for index in range(100)],
    }
    shaped = agent_executor.shape_observation(
        payload, limit_chars=450, max_facts=5
    )

    assert len(shaped["facts"]) == 5
    assert shaped["truncated"]["facts_omitted"] == 95
    assert shaped["truncated"]["dropped"] == ["evidence", "lineage"]
    assert len(json.dumps(shaped, separators=(",", ":"))) <= 450
    assert shaped["truncated"]["summary_clipped"] is True
    assert shaped["status"] == "ok"


def test_shape_observation_never_drops_query_reference():
    payload = {
        "status": "ok",
        "query_reference": {"query_id": "turn:q1", "attempt_id": "turn:q1:a1"},
        "payload": {"rows": [{"value": "x" * 2000}]},
        "summary": "large result",
    }

    shaped = agent_executor.shape_observation(payload, limit_chars=350)

    assert shaped["query_reference"] == {
        "query_id": "turn:q1",
        "attempt_id": "turn:q1:a1",
    }
    assert shaped["status"] == "ok"


def test_shape_observation_drops_oversized_scalar_payload():
    shaped = agent_executor.shape_observation(
        {
            "status": "ok",
            "query_reference": {"query_id": 1, "attempt": 1},
            "payload": {"document": "x" * 20_000},
            "summary": "large result",
        },
        limit_chars=350,
    )

    assert len(json.dumps(shaped, separators=(",", ":"))) <= 350
    assert shaped["query_reference"] == {"query_id": 1, "attempt": 1}
    assert "payload" not in shaped
    assert "payload" in shaped["truncated"]["dropped"]
