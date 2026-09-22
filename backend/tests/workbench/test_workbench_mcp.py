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
    monkeypatch.setattr(access.settings, "workbench_external_connectors_enabled", True)
    monkeypatch.setattr(access.settings, "exa_mcp_enabled", True)


def _context(*, external: bool = True):
    policy = access.build_policy(role="admin", external_sources_enabled=external)
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
    assert {item["function"]["name"] for item in definitions} == (
        set(RUNTIME_TOOL_POLICIES) - {"visualize_query_result"}
    )
    assert all(item["function"]["strict"] is True for item in definitions)


@pytest.mark.anyio
async def test_owned_tool_content_contains_one_json_envelope():
    async with Client(workbench_server.mcp, mode="legacy") as client:
        result = await client.call_tool(
            "finish_without_data",
            {
                "outcome": "clarify",
                "message": "Which period?",
                "suggestions": ["This month"],
                "reason_code": None,
            },
        )

    assert result.data["success"] is True
    assert set(result.data) == {"success", "data"}
    content_payload = json.loads(result.content[0].text)
    assert content_payload == result.data
    assert "text" not in content_payload


@pytest.mark.anyio
async def test_in_memory_client_supports_concurrent_calls():
    async def invoke(index: int):
        return await workbench_client.call_tool(
            "finish_without_data",
            {
                "outcome": "clarify",
                "message": f"Question {index}?",
                "suggestions": [],
                "reason_code": None,
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
async def test_web_and_visualization_tools_execute_through_in_memory_client(monkeypatch):
    async def web_handler(_args, _ctx):
        return SourceResult(
            source="web", card_type="brief", payload={}, summary="web result"
        )

    async def visual_handler(_args, _ctx):
        return SourceResult(
            source="db", card_type="chart", payload={}, summary="visual result"
        )

    monkeypatch.setattr(agent_executor, "_search_public_web", web_handler)
    monkeypatch.setattr(agent_executor, "_visualize_query_result", visual_handler)

    web = await workbench_client.call_tool(
        "search_public_web",
        {"search_query": "latest RBI repo rate"},
        context=_context(),
    )
    visual = await workbench_client.call_tool(
        "visualize_query_result",
        {
            "query_id": "turn-1:q1",
            "chart_type": "kpi",
            "x": None,
            "y": ["value"],
            "series": None,
            "aggregation": "none",
        },
        context=_context(),
    )

    assert web["card"]["summary"] == "web result"
    assert visual["card"]["summary"] == "visual result"


@pytest.mark.anyio
async def test_submit_final_answer_executes_through_in_memory_client():
    async with Client(workbench_server.mcp, mode="legacy") as client:
        result = await client.call_tool(
            "submit_final_answer",
            {"insights": "", "query_id": 1, "view": "table"},
        )

    terminal = result.data["data"]["terminal"]
    assert terminal["outcome"] == "answer"
    assert terminal["synthesis"] == {"insights": "", "query_id": 1, "view": "table"}
    assert json.loads(result.content[0].text) == {"success": True}


@pytest.mark.anyio
async def test_fastmcp_rejects_extra_and_cross_field_invalid_arguments():
    async with Client(workbench_server.mcp, mode="legacy") as client:
        with pytest.raises(ToolError):
            await client.call_tool(
                "finish_without_data",
                {
                    "outcome": "clarify",
                    "message": "Which period?",
                    "suggestions": [],
                    "reason_code": None,
                    "unexpected": True,
                },
            )
        with pytest.raises((ToolError, MCPError)):
            await client.call_tool(
                "finish_without_data",
                {
                    "outcome": "refuse",
                    "message": "I cannot do that.",
                    "suggestions": [],
                    "reason_code": None,
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
