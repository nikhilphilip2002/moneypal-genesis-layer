"""Protocol contract for the hosted Exa MCP client without making network calls."""

from __future__ import annotations

from contextlib import asynccontextmanager
from types import SimpleNamespace

import pytest

from app.core.config import settings
from app.mcp import exa_client


@pytest.mark.anyio
async def test_api_key_is_sent_as_header_not_url(monkeypatch):
    seen = {}

    @asynccontextmanager
    async def fake_transport(url, **kwargs):
        seen["url"] = url
        seen["headers"] = kwargs["headers"]
        yield "read", "write", lambda: None

    class FakeSession:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def initialize(self):
            return None

        async def call_tool(self, name, arguments, **kwargs):
            seen["tool"] = name
            seen["arguments"] = arguments
            return SimpleNamespace(
                isError=False,
                structuredContent={"results": []},
                content=[SimpleNamespace(text='{"results": []}')],
            )

    monkeypatch.setattr(exa_client, "streamablehttp_client", fake_transport)
    monkeypatch.setattr(exa_client, "ClientSession", FakeSession)
    monkeypatch.setattr(settings, "exa_mcp_enabled", True)
    monkeypatch.setattr(settings, "exa_api_key", "test-secret")
    monkeypatch.setattr(
        settings, "exa_mcp_url", "https://mcp.exa.ai/mcp?tools=web_search_exa"
    )

    await exa_client.search("latest RBI release", num_results=5)

    assert seen["headers"]["x-api-key"] == "test-secret"
    assert "test-secret" not in seen["url"]
    assert seen["tool"] == "web_search_exa"
    assert seen["arguments"]["numResults"] == 5


@pytest.mark.anyio
async def test_remote_rate_limit_gets_a_safe_typed_error(monkeypatch):
    @asynccontextmanager
    async def failing_transport(*args, **kwargs):
        raise RuntimeError("HTTP 429 rate limit")
        yield  # pragma: no cover

    monkeypatch.setattr(exa_client, "streamablehttp_client", failing_transport)
    monkeypatch.setattr(settings, "exa_mcp_enabled", True)
    monkeypatch.setattr(settings, "exa_api_key", "test-secret")

    with pytest.raises(exa_client.ExaRateLimitError, match="allowance"):
        await exa_client.search("latest RBI release", num_results=5)
