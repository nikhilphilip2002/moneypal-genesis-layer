"""Persistent llama.cpp snapshot of the Workbench's initial system prompt only."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from typing import Any, Awaitable, Callable
from urllib.parse import urlsplit, urlunsplit

import httpx

from app.core.config import settings
from app.services.workbench import prompts


WARMUP_USER_MESSAGE = "Initialize the system prompt cache."


class SlotCacheError(RuntimeError):
    """A llama-server slot operation or safe warm-up failed."""


@dataclass(frozen=True, slots=True)
class SlotCacheIdentity:
    fingerprint: str
    filename: str
    model: str
    system_prompt_sha256: str


@dataclass(frozen=True, slots=True)
class WarmupBundle:
    messages: list[dict[str, Any]]
    identity: SlotCacheIdentity


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def _sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def llama_server_root(base_url: str) -> str:
    """Convert an OpenAI-compatible ``.../v1`` URL to llama-server's root URL."""
    parsed = urlsplit(base_url.rstrip("/"))
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise SlotCacheError("LLM_BASE_URL must be an absolute HTTP(S) URL")
    path = parsed.path.rstrip("/")
    if path.endswith("/v1"):
        path = path[:-3]
    return urlunsplit((parsed.scheme, parsed.netloc, path, "", "")).rstrip("/")


def build_identity(*, system_prompt: str) -> SlotCacheIdentity:
    """Fingerprint exactly the two approved inputs: model ID and system prompt."""
    prompt_hash = _sha256(system_prompt)
    material = {"model": settings.llm_model, "system_prompt": system_prompt}
    fingerprint = _sha256(material)
    prefix = re.sub(
        r"[^A-Za-z0-9_.-]+", "-", settings.llama_slot_cache_prefix
    ).strip(".-")[:48]
    if not prefix:
        prefix = "moneypal-workbench"
    filename = f"{prefix}-{fingerprint}.bin"
    return SlotCacheIdentity(
        fingerprint=fingerprint,
        filename=filename,
        model=settings.llm_model,
        system_prompt_sha256=prompt_hash,
    )


async def build_warmup_bundle() -> WarmupBundle:
    """Build the system prompt plus the minimal user turn required by Qwen's template."""
    system_prompt = prompts.build_agent_system_prompt()
    messages = [
        {
            "role": "system",
            "content": [{
                "type": "text",
                "text": system_prompt,
                "prompt_cache_breakpoint": {"mode": "explicit"},
            }],
        },
        {"role": "user", "content": WARMUP_USER_MESSAGE},
    ]
    return WarmupBundle(
        messages=messages,
        identity=build_identity(system_prompt=system_prompt),
    )


async def slot_action(
    action: str,
    *,
    filename: str | None = None,
    http_client: httpx.AsyncClient | None = None,
) -> dict[str, Any]:
    if action not in {"save", "restore", "erase"}:
        raise ValueError(f"unsupported slot action: {action}")
    if action != "erase" and not filename:
        raise ValueError(f"filename is required for slot action {action}")
    owns_client = http_client is None
    client = http_client or httpx.AsyncClient(timeout=settings.llm_timeout_s)
    try:
        headers = (
            {"Authorization": f"Bearer {settings.llm_api_key}"}
            if settings.llm_api_key
            else None
        )
        response = await client.post(
            f"{llama_server_root(settings.llm_base_url)}/slots/{settings.llama_slot_id}",
            params={"action": action},
            json={"filename": filename} if filename else None,
            headers=headers,
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise SlotCacheError(f"llama-server {action} returned a non-object response")
        return payload
    except (httpx.HTTPError, ValueError) as exc:
        raise SlotCacheError(f"llama-server slot {action} failed: {exc}") from exc
    finally:
        if owns_client:
            await client.aclose()


async def warm_slot(
    bundle: WarmupBundle, *, http_client: httpx.AsyncClient | None = None
) -> dict[str, Any]:
    """Render and evaluate only the system message, generating zero tokens."""
    headers = (
        {"Authorization": f"Bearer {settings.llm_api_key}"}
        if settings.llm_api_key
        else None
    )
    root = llama_server_root(settings.llm_base_url)
    owns_client = http_client is None
    client = http_client or httpx.AsyncClient(timeout=settings.llm_timeout_s)
    try:
        templated = await client.post(
            f"{root}/apply-template",
            json={"messages": bundle.messages},
            headers=headers,
        )
        templated.raise_for_status()
        prompt = templated.json().get("prompt")
        if not isinstance(prompt, str) or not prompt:
            raise SlotCacheError("llama-server apply-template returned no prompt")
        evaluated = await client.post(
            f"{root}/completion",
            json={
                "prompt": prompt,
                "n_predict": 0,
                "cache_prompt": True,
                "id_slot": settings.llama_slot_id,
            },
            headers=headers,
        )
        evaluated.raise_for_status()
        payload = evaluated.json()
        if not isinstance(payload, dict):
            raise SlotCacheError("llama-server completion returned a non-object response")
    except SlotCacheError:
        raise
    except (httpx.HTTPError, ValueError) as exc:
        raise SlotCacheError(f"llama-server system-prompt prefill failed: {exc}") from exc
    finally:
        if owns_client:
            await client.aclose()
    timings = payload.get("timings") if isinstance(payload.get("timings"), dict) else {}
    return {
        "generated_tokens": 0,
        "prompt_tokens": int(timings.get("prompt_n", 0) or 0),
        "cached_prompt_tokens": int(timings.get("cache_n", 0) or 0),
    }


async def restore_or_warm(
    bundle: WarmupBundle,
    *,
    action: Callable[..., Awaitable[dict[str, Any]]] = slot_action,
    warmer: Callable[[WarmupBundle], Awaitable[dict[str, Any]]] = warm_slot,
) -> dict[str, Any]:
    """Restore the compatible snapshot, or replace the slot and create it."""
    try:
        restored = await action("restore", filename=bundle.identity.filename)
        return {"outcome": "restored", "identity": asdict(bundle.identity), "slot": restored}
    except SlotCacheError as restore_error:
        erased = await action("erase")
        warmup = await warmer(bundle)
        saved = await action("save", filename=bundle.identity.filename)
        return {
            "outcome": "warmed_and_saved",
            "identity": asdict(bundle.identity),
            "restore_error": str(restore_error),
            "erase": erased,
            "warmup": warmup,
            "slot": saved,
        }


__all__ = [
    "SlotCacheError",
    "SlotCacheIdentity",
    "WARMUP_USER_MESSAGE",
    "WarmupBundle",
    "build_identity",
    "build_warmup_bundle",
    "llama_server_root",
    "restore_or_warm",
    "slot_action",
    "warm_slot",
]
