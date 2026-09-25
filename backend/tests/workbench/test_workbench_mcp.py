"""Protocol checks for the in-process Workbench FastMCP server."""

from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

import pytest
from fastmcp import Client
from fastmcp.exceptions import MCPError, ToolError

from app.mcp import workbench_client, workbench_server
from app.mcp.tool_catalog import ToolCatalog
from app.services.workbench import access
from app.services.workbench import agent_executor
from app.services.workbench.agent_tools import RUNTIME_TOOL_POLICIES
from app.services.workbench.results import SourceResult


@pytest.fixture(autouse=True)
def _connector_settings(monkeypatch):
    monkeypatch.setattr(
        access.settings, "workbench_external_connectors_enabled", True
    )
    monkeypatch.setattr(access.settings, "exa_mcp_enabled", True)


def _context(*, external: bool = True):
    policy = access.build_policy(
        role="admin", external_sources_enabled=external
    )
    return SimpleNamespace(
        user="alice",
        role="admin",
        conversation_id="conversation-1",
        turn_id="turn-1",
        question="What does PAR 30 mean?",
        deadline_s=5.0,
        catalog_version="test",
        private_entities=(),
        query_id=None,
        attempt_id=None,
        source_policy=policy,
    )


@pytest.mark.anyio
async def test_discovery_is_the_model_contract_source():
    names = await workbench_client.discover_model_tools()
    assert set(names) == set(RUNTIME_TOOL_POLICIES)

    catalog = ToolCatalog()
    await catalog.discover_local()
    definitions = await catalog.model_tool_definitions(
        _context().source_policy
    )
    assert {item["function"]["name"] for item in definitions} == set(
        RUNTIME_TOOL_POLICIES
    )
    assert all(item["function"]["strict"] is True for item in definitions)
    submit = next(
        item["function"]
        for item in definitions
        if item["function"]["name"] == "submit_final_answer"
    )
    discovered_submit = next(
        tool
        for tool in await workbench_client.list_tools()
        if tool.name == "submit_final_answer"
    )
    assert submit["description"] == discovered_submit.description


@pytest.mark.anyio
@pytest.mark.parametrize(
    "submission",
    [
        {
            "outcome": "clarify",
            "message": "Which period?",
            "suggestions": ["This month"],
        },
        {
            "outcome": "refuse",
            "message": "That is unavailable.",
            "reason_code": "not_in_data",
        },
    ],
)
async def test_owned_tool_content_contains_one_json_envelope(submission):
    async with Client(workbench_server.mcp, mode="legacy") as client:
        result = await client.call_tool(
            "submit_final_answer",
            {"submission": submission},
        )

    assert result.data["success"] is True
    assert set(result.data) == {"success", "data"}
    content_payload = json.loads(result.content[0].text)
    assert content_payload == {"success": True}
    assert result.data["data"]["terminal"] == submission
    assert "text" not in content_payload


@pytest.mark.anyio
async def test_in_memory_client_supports_concurrent_calls():
    async def invoke(index: int):
        return await workbench_client.call_tool(
            "submit_final_answer",
            {
                "submission": {
                    "outcome": "clarify",
                    "message": f"Question {index}?",
                    "suggestions": [],
                }
            },
            context=_context(),
        )

    results = await asyncio.gather(*(invoke(index) for index in range(5)))
    assert [item["terminal"]["message"] for item in results] == [
        f"Question {index}?" for index in range(5)
    ]


@pytest.mark.anyio
async def test_curated_tool_executes_through_in_memory_client():
    data = await workbench_client.call_tool(
        "search_curated_knowledge",
        {"domain": "concepts", "query": "PAR 30"},
        context=_context(),
    )

    assert data["kind"] == "card"
    assert data["card"]["source"] == "knowledge"
    assert "principal outstanding" in data["card"]["summary"]


@pytest.mark.anyio
async def test_web_tool_executes_through_in_memory_client(monkeypatch):
    async def web_handler(_args, _ctx):
        return SourceResult(
            source="web", card_type="brief", payload={}, summary="web result"
        )

    monkeypatch.setattr(agent_executor, "_search_public_web", web_handler)

    web = await workbench_client.call_tool(
        "search_public_web",
        {"search_query": "latest RBI repo rate"},
        context=_context(),
    )
    assert web["card"]["summary"] == "web result"


@pytest.mark.anyio
async def test_submit_final_answer_executes_through_in_memory_client():
    async with Client(workbench_server.mcp, mode="legacy") as client:
        result = await client.call_tool(
            "submit_final_answer",
            {
                "submission": {
                    "outcome": "answer",
                    "message": "",
                    "query_id": 1,
                    "view": "table",
                }
            },
            meta=workbench_client.execution_meta(_context()),
        )

    terminal = result.data["data"]["terminal"]
    assert terminal["outcome"] == "answer"
    assert terminal["synthesis"] == {
        "insights": "",
        "query_id": 1,
        "view": "table",
    }
    assert json.loads(result.content[0].text) == {"success": True}


@pytest.mark.anyio
async def test_fastmcp_rejects_extra_and_cross_field_invalid_arguments():
    async with Client(workbench_server.mcp, mode="legacy") as client:
        with pytest.raises(ToolError):
            await client.call_tool(
                "submit_final_answer",
                {
                    "submission": {
                        "outcome": "clarify",
                        "message": "Which period?",
                        "suggestions": [],
                        "unexpected": True,
                    }
                },
            )
        with pytest.raises((ToolError, MCPError)):
            await client.call_tool(
                "submit_final_answer",
                {
                    "submission": {
                        "outcome": "refuse",
                        "message": "I cannot do that.",
                        "reason_code": None,
                    }
                },
            )
        with pytest.raises((ToolError, MCPError)):
            await client.call_tool(
                "submit_final_answer",
                {
                    "submission": {
                        "outcome": "clarify",
                        "message": "Which period?",
                        "query_id": 1,
                    }
                },
            )
        with pytest.raises((ToolError, MCPError)):
            await client.call_tool(
                "submit_final_answer",
                {
                    "submission": {
                        "outcome": "answer",
                        "message": "Which period?",
                        "query_id": 1,
                        "view": "table",
                        "suggestions": ["This month"],
                    }
                },
            )
        with pytest.raises((ToolError, MCPError)):
            await client.call_tool(
                "submit_final_answer",
                {"submission": {"outcome": "clarify", "message": ""}},
            )
        with pytest.raises((ToolError, MCPError)):
            await client.call_tool(
                "submit_final_answer",
                {
                    "submission": {
                        "outcome": "refuse",
                        "message": "x" * 501,
                        "reason_code": "unsafe",
                    }
                },
            )


@pytest.mark.anyio
async def test_clarification_with_refusal_reason_reports_only_the_selected_branch():
    submission = {
        "outcome": "clarify",
        "message": (
            "No loan accounts were found associated with the customer name "
            "'sheelavathi' in the governed Gold schema tables. This could be due "
            "to a mismatch in the name provided or the customer not having any "
            "loan accounts in the system."
        ),
        "suggestions": [
            "Verify the spelling of the customer name 'sheelavathi'",
            "Check if the customer is linked to any loan accounts in the system",
            "Provide an alternative customer identifier such as customer_id for a more targeted search",
        ],
        "reason_code": "not_in_data",
    }
    async with Client(workbench_server.mcp, mode="legacy") as client:
        with pytest.raises(ToolError) as error:
            await client.call_tool(
                "submit_final_answer", {"submission": submission}
            )
        message = str(error.value)
        assert "1 validation error" in message
        assert "submission.clarify.reason_code" in message
        assert "extra_forbidden" in message
        assert "query_id" not in message
        submission.pop("reason_code")
        result = await client.call_tool(
            "submit_final_answer", {"submission": submission}
        )
        assert result.data["data"]["terminal"] == submission


@pytest.mark.anyio
@pytest.mark.parametrize(
    "fields",
    [
        {},
        {"reason_code": "unknown"},
        {"reason_code": "unsafe", "suggestions": []},
    ],
)
async def test_refusal_rejects_missing_invalid_or_mixed_fields(fields):
    async with Client(workbench_server.mcp, mode="legacy") as client:
        with pytest.raises(ToolError):
            await client.call_tool(
                "submit_final_answer",
                {
                    "submission": {
                        "outcome": "refuse",
                        "message": "Unavailable.",
                        **fields,
                    }
                },
            )


@pytest.mark.anyio
async def test_direct_forged_web_call_is_reauthorized_inside_server():
    context = _context(external=False)
    async with Client(workbench_server.mcp, mode="legacy") as client:
        with pytest.raises(ToolError, match="external source consent"):
            await client.call_tool(
                "search_public_web",
                {"search_query": "latest RBI repo rate"},
                meta=workbench_client.execution_meta(context),
            )
