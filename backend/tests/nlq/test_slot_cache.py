from __future__ import annotations

import asyncio
import json

import httpx

from app.core.config import settings
from app.services.nlq.llm.slot_cache import (
    SlotCacheError,
    WarmupBundle,
    build_identity,
    llama_server_root,
    restore_or_warm,
    slot_action,
    warm_slot,
)


def _bundle() -> WarmupBundle:
    messages = [{"role": "system", "content": "stable"}]
    return WarmupBundle(
        messages=messages,
        identity=build_identity(system_prompt="stable"),
    )


def test_llama_server_root_removes_only_v1_suffix():
    assert llama_server_root("http://llama:8080/v1/") == "http://llama:8080"
    assert llama_server_root("https://host/prefix/v1") == "https://host/prefix"
    assert llama_server_root("https://host/api") == "https://host/api"


def test_identity_is_deterministic_and_safe(monkeypatch):
    monkeypatch.setattr(settings, "llama_slot_cache_prefix", "Money Pal / Workbench")
    first = _bundle().identity
    second = _bundle().identity

    assert first == second
    assert first.filename.startswith("Money-Pal-Workbench-")
    assert "/" not in first.filename

    changed = build_identity(system_prompt="changed")
    assert changed.fingerprint != first.fingerprint

    monkeypatch.setattr(settings, "llm_model", "different-model-id")
    model_changed = _bundle().identity
    assert model_changed.fingerprint != first.fingerprint


def test_restore_success_skips_warmup():
    calls: list[tuple[str, str | None]] = []

    async def action(name: str, *, filename: str | None = None):
        calls.append((name, filename))
        return {"id_slot": 0, "n_restored": 100}

    async def warmer(_bundle):  # pragma: no cover - must not be reached
        raise AssertionError("warm-up ran after a successful restore")

    bundle = _bundle()
    result = asyncio.run(restore_or_warm(bundle, action=action, warmer=warmer))

    assert result["outcome"] == "restored"
    assert calls == [("restore", bundle.identity.filename)]


def test_restore_miss_erases_warms_and_saves():
    calls: list[tuple[str, str | None]] = []

    async def action(name: str, *, filename: str | None = None):
        calls.append((name, filename))
        if name == "restore":
            raise SlotCacheError("snapshot missing")
        return {"id_slot": 0}

    async def warmer(_bundle):
        calls.append(("warm", None))
        return {"prompt_tokens": 123}

    bundle = _bundle()
    result = asyncio.run(restore_or_warm(bundle, action=action, warmer=warmer))

    assert result["outcome"] == "warmed_and_saved"
    assert calls == [
        ("restore", bundle.identity.filename),
        ("erase", None),
        ("warm", None),
        ("save", bundle.identity.filename),
    ]


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
    assert seen[0].read() == b'{"filename":"safe.bin"}'


def test_warm_slot_applies_template_and_generates_no_tokens(monkeypatch):
    monkeypatch.setattr(settings, "llm_base_url", "http://llama:8080/v1")
    monkeypatch.setattr(settings, "llama_slot_id", 0)
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path == "/apply-template":
            return httpx.Response(200, json={"prompt": "rendered-system-prompt"})
        return httpx.Response(200, json={"timings": {"prompt_n": 321}})

    async def request():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await warm_slot(_bundle(), http_client=client)

    result = asyncio.run(request())

    assert [item.url.path for item in requests] == ["/apply-template", "/completion"]
    assert json.loads(requests[0].read()) == {"messages": _bundle().messages}
    completion = json.loads(requests[1].read())
    assert completion == {
        "prompt": "rendered-system-prompt",
        "n_predict": 0,
        "cache_prompt": True,
        "id_slot": 0,
    }
    assert result == {
        "generated_tokens": 0,
        "prompt_tokens": 321,
        "cached_prompt_tokens": 0,
    }
