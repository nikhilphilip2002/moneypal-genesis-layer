"""Small typed client for the internal PostgreSQL MCP server."""

from __future__ import annotations

import asyncio
from copy import deepcopy
from typing import Any

from fastmcp import Client

from app.core.config import settings
from app.mcp.provider_schema import ProviderSchemaError, provider_tool_definition
from app.mcp.results import OwnedToolResultError, require_owned_data


class PostgresMCPError(RuntimeError):
    """The MCP transport or remote tool returned an error."""

    code = "MCP_TOOL_ERROR"
    retryable = True


MCP_SHUTDOWN_GRACE_S = 5.0
_BACKEND_ONLY_TOOLS = frozenset({"postgres_health"})
_model_tools: dict[str, dict[str, Any]] = {}
_initialization_error = "PostgreSQL MCP tools have not been discovered."
_protocol_version = ""


async def call_tool(
    name: str,
    arguments: dict[str, Any],
    *,
    meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    try:
        # Bound connection, tool execution, and session shutdown together. A remote tool
        # may continue working after its HTTP client disconnects; without this outer
        # deadline, an MCP context-manager shutdown can leave the Workbench SSE stream open
        # beyond the configured read timeout.
        async with asyncio.timeout(
            settings.postgres_mcp_timeout_s + MCP_SHUTDOWN_GRACE_S
        ):
            async with Client(
                settings.postgres_mcp_url,
                timeout=settings.postgres_mcp_timeout_s,
            ) as client:
                result = await client.call_tool(
                    name,
                    arguments,
                    timeout=settings.postgres_mcp_timeout_s,
                    meta=meta,
                )
    except TimeoutError as exc:
        raise PostgresMCPError(
            f"PostgreSQL MCP tool {name!r} timed out after "
            f"{settings.postgres_mcp_timeout_s:g} seconds"
        ) from exc
    except Exception as exc:  # noqa: BLE001 - normalize transport failures for the agent
        raise PostgresMCPError(
            f"PostgreSQL MCP tool {name!r} failed: {type(exc).__name__}: {exc}"
        ) from exc

    try:
        return require_owned_data(result, tool_name=name)
    except OwnedToolResultError as exc:
        if exc.code != "MCP_TOOL_ERROR":
            return {
                "status": "error",
                **exc.details,
                "code": exc.code,
                "message": str(exc),
                "retryable": exc.retryable,
            }
        raise PostgresMCPError(str(exc)) from exc


async def discover_model_tools() -> list[dict[str, Any]]:
    """Discover and authorize the PostgreSQL MCP server's native model-facing tools."""
    global _initialization_error, _protocol_version
    forbidden = _BACKEND_ONLY_TOOLS.intersection(settings.postgres_mcp_model_tools)
    if forbidden:
        _model_tools.clear()
        _initialization_error = (
            "Backend-only PostgreSQL MCP tool(s) cannot be exposed to the model: "
            + ", ".join(sorted(forbidden))
        )
        raise PostgresMCPError(_initialization_error)
    try:
        async with asyncio.timeout(
            settings.postgres_mcp_timeout_s + MCP_SHUTDOWN_GRACE_S
        ):
            async with Client(
                settings.postgres_mcp_url,
                timeout=settings.postgres_mcp_timeout_s,
            ) as client:
                discovered_tools = await client.list_tools()
                _protocol_version = str(
                    getattr(client, "protocol_version", "") or ""
                )
    except Exception as exc:  # noqa: BLE001 - retained for readiness diagnostics
        _model_tools.clear()
        _initialization_error = f"PostgreSQL MCP discovery failed: {type(exc).__name__}: {exc}"
        raise PostgresMCPError(_initialization_error) from exc

    discovered = {tool.name: tool for tool in discovered_tools}
    missing = [
        name for name in settings.postgres_mcp_model_tools if name not in discovered
    ]
    if missing:
        _model_tools.clear()
        _initialization_error = (
            "PostgreSQL MCP is missing authorized tool(s): " + ", ".join(missing)
        )
        raise PostgresMCPError(_initialization_error)

    _model_tools.clear()
    for name in settings.postgres_mcp_model_tools:
        tool = discovered[name]
        try:
            definition = provider_tool_definition(tool)
        except ProviderSchemaError as exc:
            _model_tools.clear()
            _initialization_error = (
                f"PostgreSQL MCP tool {name!r} has an invalid input schema: {exc}"
            )
            raise PostgresMCPError(_initialization_error)
        _model_tools[name] = definition
    _initialization_error = ""
    return model_tool_definitions()


async def initialize() -> dict[str, Any]:
    global _initialization_error
    definitions = await discover_model_tools()
    health_payload = await health()
    if health_payload.get("status") not in {"ok", "healthy"}:
        _model_tools.clear()
        _initialization_error = str(
            health_payload.get("detail") or "PostgreSQL MCP health check failed"
        )
        raise PostgresMCPError(_initialization_error)
    return {
        "status": "ok",
        "tools": [item["function"]["name"] for item in definitions],
    }


def model_tool_definitions() -> list[dict[str, Any]]:
    return [deepcopy(definition) for definition in _model_tools.values()]


def is_model_tool(name: str) -> bool:
    return name in _model_tools


def readiness() -> dict[str, Any]:
    return {
        "status": "ok" if _model_tools else "unavailable",
        "tools": list(_model_tools),
        "detail": _initialization_error,
        "protocol_version": _protocol_version,
    }


async def health() -> dict[str, Any]:
    return await call_tool("postgres_health", {})
