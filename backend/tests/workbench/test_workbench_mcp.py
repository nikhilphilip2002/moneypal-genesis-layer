"""Protocol checks for the in-process Workbench FastMCP server."""

from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

import pytest
from fastmcp import Client
from fastmcp.exceptions import MCPError, ToolError

from app.core.tool_names import (
    SEARCH_CURATED_KNOWLEDGE,
    SEARCH_PUBLIC_WEB,
    VISUALIZE_RESULT,
    ASK_CLARIFICATION,
    REFUSE_REQUEST,
)
from app.mcp import workbench_client, workbench_server
from app.mcp.tool_catalog import ToolCatalog
from app.services.workbench import access, agent_executor
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
    definitions = await catalog.model_tool_definitions(_context().source_policy)
    assert {item["function"]["name"] for item in definitions} == set(
        RUNTIME_TOOL_POLICIES
    )
    assert all(item["function"]["strict"] is True for item in definitions)
    submit = next(
        item["function"]
        for item in definitions
        if item["function"]["name"] == VISUALIZE_RESULT
    )
    discovered_submit = next(
        tool
        for tool in await workbench_client.list_tools()
        if tool.name == VISUALIZE_RESULT
    )
    assert submit["description"] == discovered_submit.description
    assert set(submit["parameters"]["properties"]) == {"query_id", "view"}


@pytest.mark.anyio
@pytest.mark.parametrize("name,arguments,outcome", [
    (ASK_CLARIFICATION, {"question": "Which period?", "suggestions": ["This month"]}, "clarify"),
    (REFUSE_REQUEST, {"message": "Unavailable", "reason_code": "not_in_data"}, "refuse"),
])
async def test_terminal_tools_return_one_envelope(name, arguments, outcome):
    async with Client(workbench_server.mcp, mode="legacy") as client:
        result = await client.call_tool(name, arguments)
    assert result.data["success"] is True
    assert json.loads(result.content[0].text) == {"success": True}
    assert result.data["data"]["terminal"]["outcome"] == outcome


@pytest.mark.anyio
async def test_in_memory_client_supports_concurrent_calls():
    async def invoke(index):
        return await workbench_client.call_tool(
            ASK_CLARIFICATION, {"question": f"Question {index}?", "suggestions": []}, context=_context(),
        )
    results = await asyncio.gather(*(invoke(index) for index in range(5)))
    assert [item["terminal"]["message"] for item in results] == [f"Question {index}?" for index in range(5)]


@pytest.mark.anyio
async def test_visualization_is_nonterminal():
    result = await workbench_client.call_tool(
        VISUALIZE_RESULT, {"query_id": 1, "view": "table"}, context=_context(),
    )
    assert result == {"kind": "visual", "visual": {"query_id": 1, "view": "table"}}


@pytest.mark.anyio
@pytest.mark.parametrize("name,arguments", [
    (VISUALIZE_RESULT, {"query_id": 1, "view": "table", "message": "extra"}),
    (VISUALIZE_RESULT, {"query_id": 1, "view": "table", "outcome": "answer"}),
    (VISUALIZE_RESULT, {"query_id": 0, "view": "table"}),
    (VISUALIZE_RESULT, {"query_id": 1, "view": "unknown"}),
    (ASK_CLARIFICATION, {"question": "", "suggestions": []}),
    (ASK_CLARIFICATION, {"question": "Which?", "suggestions": [], "reason_code": "unsafe"}),
    (ASK_CLARIFICATION, {"question": "Which?", "suggestions": ["a", "b", "c", "d"]}),
    (REFUSE_REQUEST, {"message": "No", "reason_code": "unknown"}),
    (REFUSE_REQUEST, {"message": "No", "reason_code": "unsafe", "suggestions": []}),
])
async def test_tools_reject_invalid_or_mixed_arguments(name, arguments):
    async with Client(workbench_server.mcp, mode="legacy") as client:
        with pytest.raises((ToolError, MCPError)):
            await client.call_tool(name, arguments, meta=workbench_client.execution_meta(_context()))




@pytest.mark.anyio
async def test_direct_forged_web_call_is_reauthorized_inside_server():
    context = _context(external=False)
    async with Client(workbench_server.mcp, mode="legacy") as client:
        with pytest.raises(ToolError, match="external source consent"):
            await client.call_tool(
                SEARCH_PUBLIC_WEB,
                {"search_query": "latest RBI repo rate"},
                meta=workbench_client.execution_meta(context),
            )


@pytest.mark.anyio
async def test_curated_tool_executes_through_in_memory_client():
    data = await workbench_client.call_tool(
        SEARCH_CURATED_KNOWLEDGE,
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
        SEARCH_PUBLIC_WEB,
        {"search_query": "latest RBI repo rate"},
        context=_context(),
    )
    assert web["card"]["summary"] == "web result"
