"""Small typed client for the internal PostgreSQL MCP server."""

from __future__ import annotations

import asyncio
from copy import deepcopy
from datetime import timedelta
from typing import Any

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

from app.core.config import settings


class PostgresMCPError(RuntimeError):
    """The MCP transport or remote tool returned an error."""

    code = "MCP_TOOL_ERROR"
    retryable = True


MCP_SHUTDOWN_GRACE_S = 5.0
_BACKEND_ONLY_TOOLS = frozenset({"postgres_health"})
_model_tools: dict[str, dict[str, Any]] = {}
_initialization_error = "PostgreSQL MCP tools have not been discovered."


def _provider_schema(value: Any) -> Any:
    """Remove presentation-only JSON Schema fields and close object shapes for providers."""
    if isinstance(value, list):
        return [_provider_schema(item) for item in value]
    if not isinstance(value, dict):
        return value
    projected = {
        key: _provider_schema(item)
        for key, item in value.items()
        if key not in {"title", "$schema"}
    }
    if projected.get("type") == "object":
        projected["additionalProperties"] = False
    return projected


async def call_tool(
    name: str,
    arguments: dict[str, Any],
    *,
    meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    timeout = timedelta(seconds=settings.postgres_mcp_timeout_s)
    try:
        # Bound connection, tool execution, and session shutdown together. A remote tool
        # may continue working after its HTTP client disconnects; without this outer
        # deadline, an MCP context-manager shutdown can leave the Workbench SSE stream open
        # beyond the configured read timeout.
        async with asyncio.timeout(
            settings.postgres_mcp_timeout_s + MCP_SHUTDOWN_GRACE_S
        ):
            async with streamablehttp_client(
                settings.postgres_mcp_url,
                timeout=settings.postgres_mcp_timeout_s,
                sse_read_timeout=settings.postgres_mcp_timeout_s,
                terminate_on_close=False,
            ) as (read_stream, write_stream, _get_session_id):
                async with ClientSession(
                    read_stream,
                    write_stream,
                    read_timeout_seconds=timeout,
                ) as session:
                    await session.initialize()
                    result = await session.call_tool(
                        name, arguments, read_timeout_seconds=timeout, meta=meta,
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

    if result.isError:
        detail = " ".join(
            getattr(item, "text", "") for item in result.content if getattr(item, "text", "")
        )
        raise PostgresMCPError(detail or f"MCP tool {name!r} failed")

    payload = result.structuredContent
    if isinstance(payload, dict) and set(payload) == {"result"}:
        payload = payload["result"]
    if not isinstance(payload, dict):
        raise PostgresMCPError(f"MCP tool {name!r} returned no structured object")
    return payload


async def discover_model_tools() -> list[dict[str, Any]]:
    """Discover and authorize the PostgreSQL MCP server's native model-facing tools."""
    global _initialization_error
    forbidden = _BACKEND_ONLY_TOOLS.intersection(settings.postgres_mcp_model_tools)
    if forbidden:
        _model_tools.clear()
        _initialization_error = (
            "Backend-only PostgreSQL MCP tool(s) cannot be exposed to the model: "
            + ", ".join(sorted(forbidden))
        )
        raise PostgresMCPError(_initialization_error)
    timeout = timedelta(seconds=settings.postgres_mcp_timeout_s)
    try:
        async with asyncio.timeout(
            settings.postgres_mcp_timeout_s + MCP_SHUTDOWN_GRACE_S
        ):
            async with streamablehttp_client(
                settings.postgres_mcp_url,
                timeout=settings.postgres_mcp_timeout_s,
                sse_read_timeout=settings.postgres_mcp_timeout_s,
                terminate_on_close=False,
            ) as (read_stream, write_stream, _get_session_id):
                async with ClientSession(
                    read_stream,
                    write_stream,
                    read_timeout_seconds=timeout,
                ) as session:
                    await session.initialize()
                    result = await session.list_tools()
    except Exception as exc:  # noqa: BLE001 - retained for readiness diagnostics
        _model_tools.clear()
        _initialization_error = f"PostgreSQL MCP discovery failed: {type(exc).__name__}: {exc}"
        raise PostgresMCPError(_initialization_error) from exc

    discovered = {tool.name: tool for tool in result.tools}
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
        parameters = _provider_schema(deepcopy(tool.inputSchema))
        if not isinstance(parameters, dict) or parameters.get("type") != "object":
            _model_tools.clear()
            _initialization_error = f"PostgreSQL MCP tool {name!r} has an invalid input schema"
            raise PostgresMCPError(_initialization_error)
        _model_tools[name] = {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description or "PostgreSQL MCP tool",
                "parameters": parameters,
                "strict": True,
            },
        }
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
    }


async def health() -> dict[str, Any]:
    return await call_tool("postgres_health", {})
