"""In-memory FastMCP client for Moneypal-owned Workbench tools."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from fastmcp import Client
from fastmcp.exceptions import ToolError

from app.mcp.provider_schema import provider_tool_definition
from app.mcp.results import require_owned_data
from app.mcp.workbench_server import mcp


_tools: dict[str, Any] = {}
_initialization_error = "Workbench MCP tools have not been discovered."
_protocol_version = ""


class WorkbenchMCPError(RuntimeError):
    """A local MCP call failed validation or execution."""

    code = "INVALID_TOOL_ARGUMENTS"
    retryable = True


def execution_meta(ctx: Any) -> dict[str, Any]:
    policy = ctx.source_policy
    return {
        "workbench_user": ctx.user,
        "workbench_role": ctx.role,
        "workbench_conversation_id": ctx.conversation_id,
        "workbench_turn_id": ctx.turn_id,
        "workbench_question": ctx.question,
        "workbench_deadline_s": ctx.deadline_s,
        "workbench_catalog_version": ctx.catalog_version,
        "workbench_private_entities": list(ctx.private_entities),
        "workbench_external_sources_enabled": policy.external_sources_enabled,
        "workbench_pinned_source": policy.pinned_source,
        "source_policy_version": policy.version,
        "workbench_effective_sources": list(policy.effective_sources),
        "workbench_query_id": ctx.query_id,
        "workbench_attempt_id": ctx.attempt_id,
    }


async def list_tools():
    global _protocol_version
    # Legacy mode still uses an in-memory JSON-RPC transport and safely handles handlers
    # that offload blocking retrieval with asyncio.to_thread. Direct-dispatch mode currently
    # waits indefinitely during client shutdown after such a call.
    async with Client(mcp, mode="legacy") as client:
        tools = await client.list_tools()
        _protocol_version = str(getattr(client, "protocol_version", "") or "")
        return tools


async def discover_model_tools() -> list[str]:
    global _initialization_error
    tools = await list_tools()
    discovered = {tool.name: tool for tool in tools}
    _tools.clear()
    _tools.update(discovered)
    # Project every schema at startup so unsupported contracts fail before a model request.
    for tool in _tools.values():
        provider_tool_definition(tool)
    _initialization_error = ""
    return list(_tools)


def canonical_model_definitions() -> list[dict[str, Any]]:
    if not _tools:
        raise RuntimeError(_initialization_error)
    return [
        deepcopy(provider_tool_definition(_tools[name]))
        for name in sorted(_tools)
    ]


def readiness() -> dict[str, Any]:
    return {
        "status": "ok" if _tools else "unavailable",
        "tools": list(_tools),
        "detail": _initialization_error,
        "protocol_version": _protocol_version,
    }


async def call_tool(
    name: str,
    arguments: dict[str, Any],
    *,
    context: Any,
) -> dict[str, Any]:
    try:
        async with Client(mcp, mode="legacy") as client:
            result = await client.call_tool(
                name,
                arguments,
                meta=execution_meta(context),
            )
    except ToolError as exc:
        raise WorkbenchMCPError(str(exc)) from exc
    return require_owned_data(result, tool_name=name)


__all__ = [
    "call_tool",
    "canonical_model_definitions",
    "discover_model_tools",
    "execution_meta",
    "list_tools",
    "readiness",
    "WorkbenchMCPError",
]
