"""Small typed client for the internal PostgreSQL MCP server."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

from app.core.config import settings


class PostgresMCPError(RuntimeError):
    """The MCP transport or remote tool returned an error."""


async def call_tool(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    timeout = timedelta(seconds=settings.postgres_mcp_timeout_s)
    async with streamablehttp_client(
        settings.postgres_mcp_url,
        timeout=settings.postgres_mcp_timeout_s,
        sse_read_timeout=settings.postgres_mcp_timeout_s,
    ) as (read_stream, write_stream, _get_session_id):
        async with ClientSession(
            read_stream,
            write_stream,
            read_timeout_seconds=timeout,
        ) as session:
            await session.initialize()
            result = await session.call_tool(name, arguments, read_timeout_seconds=timeout)

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


async def ask_loan_book(*, question: str, conversation_id: str, user: str, role: str) -> dict[str, Any]:
    return await call_tool("ask_loan_book", {
        "question": question,
        "conversation_id": conversation_id,
        "user": user,
        "role": role,
    })


async def curiosity_graph(**arguments: Any) -> dict[str, Any]:
    return await call_tool("curiosity_graph", arguments)


async def health() -> dict[str, Any]:
    return await call_tool("postgres_health", {})
