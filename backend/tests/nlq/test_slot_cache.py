from __future__ import annotations

import asyncio
import json

import httpx
import pytest

from app.core.config import settings
from app.services.nlq.llm.slot_cache import (
    SlotCacheError,
    llama_server_root,
    slot_action,
    snapshot_filename,
)


def test_llama_server_root_removes_only_v1_suffix():
    assert llama_server_root("http://llama:8080/v1/") == "http://llama:8080"
    assert llama_server_root("https://host/prefix/v1") == "https://host/prefix"
    assert llama_server_root("https://host/api") == "https://host/api"


def test_snapshot_identity_is_conversation_scoped_and_safe(monkeypatch):
    monkeypatch.setattr(settings, "llama_slot_cache_prefix", "Money Pal / Workbench")
    kwargs = dict(
        user="analyst@example.com", conversation_id="conversation-1",
        system_prompt="stable", tool_schema_hash="tools-v1",
    )
    first = snapshot_filename(**kwargs)
    assert first == snapshot_filename(**kwargs)
    assert first.startswith("Money-Pal-Workbench-")
    assert "analyst" not in first and "/" not in first
    assert first != snapshot_filename(**{**kwargs, "user": "other"})
    assert first != snapshot_filename(**{**kwargs, "conversation_id": "conversation-2"})
    assert first != snapshot_filename(**{**kwargs, "tool_schema_hash": "tools-v2"})
    monkeypatch.setattr(settings, "llm_model", "other-model")
    assert first != snapshot_filename(**kwargs)


def test_slot_action_uses_server_root_and_filename(monkeypatch):
    monkeypatch.setattr(settings, "llm_base_url", "http://llama:8080/v1")
    monkeypatch.setattr(settings, "llama_slot_id", 0)
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"id_slot": 0, "n_saved": 12})

    async def request():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await slot_action("save", filename="safe.bin", http_client=client)

    result = asyncio.run(request())
    assert result["n_saved"] == 12
    assert str(seen[0].url) == "http://llama:8080/slots/0?action=save"
    assert json.loads(seen[0].read()) == {"filename": "safe.bin"}


def test_slot_action_rejects_missing_filename():
    with pytest.raises(ValueError, match="filename is required"):
        asyncio.run(slot_action("restore"))


def test_slot_action_reports_http_failure(monkeypatch):
    monkeypatch.setattr(settings, "llm_base_url", "http://llama:8080/v1")

    async def request():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(lambda _: httpx.Response(404))
        ) as client:
            await slot_action("restore", filename="missing.bin", http_client=client)

    with pytest.raises(SlotCacheError, match="slot restore failed"):
        asyncio.run(request())
