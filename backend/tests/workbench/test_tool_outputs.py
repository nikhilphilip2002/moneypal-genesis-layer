import json
from dataclasses import replace

import pytest

from app.core.config import Settings, settings
from app.core.tool_names import READ_TOOL_OUTPUT, SEARCH_CURATED_KNOWLEDGE
from app.mcp import workbench_client
from app.services.nlq.llm import NativeToolCall
from app.services.workbench import access, history
from app.services.workbench.agent_executor import (
    AgentExecutionContext,
    ExecutedAgentCall,
    execute_agent_call,
)
from app.services.workbench.results import Evidence, SourceResult


@pytest.fixture
def context(monkeypatch):
    monkeypatch.setattr(history, "_ensure_table", lambda: False)
    monkeypatch.setattr(history, "_MEMORY", {})
    monkeypatch.setattr(settings, "workbench_external_connectors_enabled", True)
    monkeypatch.setattr(settings, "workbench_tool_output_page_chars", 137)
    monkeypatch.setattr(settings, "workbench_agent_observation_max_chars", 1000)
    turn_id = history.begin_turn("outputs", "alice", "Question")
    return AgentExecutionContext(
        user="alice",
        role="admin",
        conversation_id="outputs",
        turn_id=turn_id,
        source_policy=access.build_policy(
            role="admin", external_sources_enabled=True
        ),
        deadline_s=30,
    )


def oversized(context):
    return ExecutedAgentCall(
        call=NativeToolCall(
            id="large", name=SEARCH_CURATED_KNOWLEDGE, arguments={}
        ),
        context=context,
        card=SourceResult(
            source="macro",
            card_type="text",
            payload={"text": "α😀" * 300},
            summary="Full result",
            sources=[{"url": "https://example.com"}],
            evidence=[Evidence(excerpt="evidence" * 30)],
            lineage={"original": "lineage" * 30},
        ),
    )


@pytest.mark.anyio
async def test_reconstruct_complete_content_through_mcp(context):
    executed = oversized(context)
    expected = json.dumps(
        executed.result_payload(), default=str, separators=(",", ":")
    )
    initial, footer = executed.observation_message()["content"].split(
        "\n\n[Tool output clipped] "
    )
    offset = json.loads(footer.splitlines()[0])["next_offset"]
    parts = [initial]
    while True:
        result = await execute_agent_call(
            NativeToolCall(
                id=f"page-{offset}",
                name=READ_TOOL_OUTPUT,
                arguments={"id": "large", "offset": offset},
            ),
            context,
        )
        page = json.loads(result.observation_message()["content"])
        assert len(page["content"]) <= 137
        assert page["next_offset"] == offset + len(page["content"])
        parts.append(page["content"])
        offset = page["next_offset"]
        if not page["has_more"]:
            break
    assert "".join(parts) == expected
    assert history._record_payload(history._MEMORY[("alice", "outputs")])[
        "tool_outputs"
    ] == {"large": expected}
    end = history.read_tool_output(
        "outputs", "alice", "large", len(expected), context.source_policy
    )
    assert end == {
        "content": "",
        "next_offset": len(expected),
        "has_more": False,
    }


@pytest.mark.anyio
@pytest.mark.parametrize(
    "change", ["owner", "conversation", "source", "deployment"]
)
async def test_reads_recheck_access(context, monkeypatch, change):
    oversized(context).observation_message()
    if change == "owner":
        context = replace(context, user="bob")
    elif change == "conversation":
        history.begin_turn("other", "alice", "Question")
        context = replace(context, conversation_id="other")
    elif change == "source":
        context = replace(
            context,
            source_policy=access.build_policy(
                role="admin", external_sources_enabled=False
            ),
        )
    else:
        monkeypatch.setattr(
            settings, "workbench_external_connectors_enabled", False
        )
    with pytest.raises(workbench_client.WorkbenchMCPError):
        await workbench_client.call_tool(
            READ_TOOL_OUTPUT, {"id": "large", "offset": 0}, context=context
        )


@pytest.mark.anyio
@pytest.mark.parametrize(
    "arguments, message",
    [
        ({"id": "missing", "offset": 0}, "Unknown tool output ID"),
        ({"id": "large", "offset": 100000}, "Invalid offset"),
        ({"id": "large", "offset": -1}, "greater than or equal"),
        ({"id": "large", "offset": 1.5}, "integer"),
        ({"id": "large", "offset": True}, "integer"),
        ({"id": "large", "offset": 0, "limit": 10}, "limit"),
    ],
)
async def test_invalid_reads(context, arguments, message):
    oversized(context).observation_message()
    with pytest.raises(workbench_client.WorkbenchMCPError, match=message):
        await workbench_client.call_tool(
            READ_TOOL_OUTPUT, arguments, context=context
        )


def test_small_result_is_not_stored(context):
    executed = oversized(context)
    executed.card = SourceResult(
        source="macro", card_type="text", payload={"text": "short"}
    )
    assert (
        json.loads(executed.observation_message()["content"])
        == executed.result_payload()
    )
    assert history._MEMORY[("alice", "outputs")].tool_outputs == {}


def test_page_size_configuration(monkeypatch):
    monkeypatch.setenv("WORKBENCH_TOOL_OUTPUT_PAGE_CHARS", "73")
    assert Settings().workbench_tool_output_page_chars == 73


@pytest.mark.anyio
async def test_complete_mcp_card_survives_normalization(context, monkeypatch):
    original = {
        "source": "macro",
        "kind": "text",
        "payload": {"text": "x" * 2000},
        "summary": "Full result",
        "sources": [{"url": "https://example.com"}],
        "evidence": [{"excerpt": "x" * 5000}],
        "lineage": {"original": "preserve"},
        "extra": {"nested": "preserve"},
    }

    async def call_tool(*args, **kwargs):
        return {"kind": "card", "card": original}

    monkeypatch.setattr(workbench_client, "call_tool", call_tool)
    result = await execute_agent_call(
        NativeToolCall(
            id="original",
            name=SEARCH_CURATED_KNOWLEDGE,
            arguments={"domain": "macro", "query": "test"},
        ),
        context,
    )
    result.observation_message()
    stored = json.loads(
        history._MEMORY[("alice", "outputs")].tool_outputs["original"]
    )
    for key in ("payload", "evidence", "lineage", "extra"):
        assert stored[key] == original[key]
    assert stored["citations"] == original["sources"]


def test_outputs_reload_from_persisted_history(context, monkeypatch):
    from contextlib import contextmanager

    from app.services import db_schema

    oversized(context).observation_message()
    record = history._MEMORY[("alice", "outputs")]
    payload = json.dumps(history._record_payload(record))
    expected = record.tool_outputs.copy()

    class Cursor:
        def execute(self, sql, params):
            assert params == ("outputs", ["alice"], "alice")

        def fetchone(self):
            return (
                record.title,
                payload,
                record.updated_at,
                "alice",
                record.record_version,
            )

    class Connection:
        def rollback(self):
            pass

    @contextmanager
    def db_cursor():
        yield Connection(), Cursor()

    monkeypatch.setattr(db_schema, "db_cursor", db_cursor)
    monkeypatch.setattr(history, "_ensure_table", lambda: True)
    history._MEMORY.clear()
    loaded = history.get("outputs", user="alice")
    assert loaded is not None
    assert loaded.tool_outputs == expected
    page = history.read_tool_output(
        "outputs", "alice", "large", 0, context.source_policy
    )
    assert page["content"] == expected["large"][:137]
