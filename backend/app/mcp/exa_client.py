"""Typed backend-only client for Exa's hosted Streamable HTTP MCP server."""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

from app.core.config import settings


class ExaMCPError(RuntimeError):
    """The Exa transport or remote tool returned unusable output."""


class ExaRateLimitError(ExaMCPError):
    """The free-tier or account quota rejected this request."""


@dataclass(slots=True)
class ExaToolResult:
    structured: dict[str, Any] | list[Any] | None
    text: str


def _error_detail(result: Any) -> str:
    return " ".join(
        getattr(item, "text", "") for item in result.content if getattr(item, "text", "")
    ).strip()


async def call_tool(name: str, arguments: dict[str, Any]) -> ExaToolResult:
    if not settings.exa_mcp_enabled:
        raise ExaMCPError("Exa web search is disabled.")
    if not settings.exa_api_key:
        raise ExaMCPError("Exa web search is enabled but EXA_API_KEY is missing.")

    timeout = timedelta(seconds=settings.exa_mcp_timeout_s)
    headers = {"x-api-key": settings.exa_api_key, "x-exa-source": "moneypal"}
    try:
        # The outer deadline also covers MCP session shutdown. Some hosted servers can
        # answer the tool and then leave termination waiting; a chat turn must still end.
        async with asyncio.timeout(settings.exa_mcp_timeout_s + 5):
            async with streamablehttp_client(
                settings.exa_mcp_url,
                headers=headers,
                timeout=settings.exa_mcp_timeout_s,
                sse_read_timeout=settings.exa_mcp_timeout_s,
                terminate_on_close=False,
            ) as (read_stream, write_stream, _get_session_id):
                async with ClientSession(
                    read_stream, write_stream, read_timeout_seconds=timeout,
                ) as session:
                    await session.initialize()
                    result = await session.call_tool(
                        name, arguments, read_timeout_seconds=timeout,
                    )
    except Exception as exc:  # transport libraries use several provider-specific types
        detail = str(exc)
        if "429" in detail or "rate limit" in detail.lower() or "quota" in detail.lower():
            raise ExaRateLimitError("Exa's web-search allowance has been reached.") from exc
        if isinstance(exc, TimeoutError):
            raise ExaMCPError("Exa MCP request timed out.") from exc
        raise ExaMCPError(f"Exa MCP request failed: {detail[:240]}") from exc

    if result.isError:
        detail = _error_detail(result) or f"Exa tool {name!r} failed"
        if "429" in detail or "rate limit" in detail.lower() or "quota" in detail.lower():
            raise ExaRateLimitError("Exa's web-search allowance has been reached.")
        raise ExaMCPError(detail[:500])

    structured: dict[str, Any] | list[Any] | None = result.structuredContent
    if isinstance(structured, dict) and set(structured) == {"result"}:
        structured = structured["result"]
    text = _error_detail(result)
    if not text and structured is not None:
        text = json.dumps(structured, default=str)
    if not text and structured is None:
        raise ExaMCPError(f"Exa tool {name!r} returned no content")
    return ExaToolResult(structured=structured, text=text)


async def search(
    query: str,
    *,
    num_results: int,
    include_domains: list[str] | None = None,
) -> ExaToolResult:
    arguments: dict[str, Any] = {
        "query": query,
        "numResults": max(1, min(settings.exa_search_max_results, num_results)),
    }
    if include_domains:
        arguments["includeDomains"] = include_domains
        return await call_tool("web_search_advanced_exa", arguments)
    return await call_tool("web_search_exa", arguments)


async def fetch(urls: list[str]) -> ExaToolResult:
    bounded = urls[: settings.exa_fetch_max_pages]
    if not bounded:
        raise ExaMCPError("No URLs were supplied to Exa fetch.")
    # The current hosted tool accepts one or more URLs through `urls`.
    return await call_tool("web_fetch_exa", {"urls": bounded})
