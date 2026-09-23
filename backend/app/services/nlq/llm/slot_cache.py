"""Conversation-scoped llama.cpp slot snapshots.

The first real chat request fills the slot. No synthetic prompt is evaluated. A saved
snapshot contains private conversation content and must only be restored for its owner.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import httpx

from app.core.config import settings


class SlotCacheError(RuntimeError):
    """A llama-server slot operation failed."""


def llama_server_root(base_url: str) -> str:
    parsed = urlsplit(base_url.rstrip("/"))
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise SlotCacheError("LLM_BASE_URL must be an absolute HTTP(S) URL")
    path = parsed.path.rstrip("/")
    if path.endswith("/v1"):
        path = path[:-3]
    return urlunsplit((parsed.scheme, parsed.netloc, path, "", "")).rstrip("/")


def snapshot_filename(
    *, user: str, conversation_id: str, system_prompt: str, tool_schema_hash: str,
) -> str:
    """Bind a private snapshot to its owner, conversation, model and prompt contract."""
    material = json.dumps({
        "user": user,
        "conversation_id": conversation_id,
        "model": settings.llm_model,
        "compatibility_id": settings.llama_slot_compatibility_id,
        "system_prompt": system_prompt,
        "tool_schema_hash": tool_schema_hash,
    }, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()
    prefix = re.sub(r"[^A-Za-z0-9_.-]+", "-", settings.llama_slot_cache_prefix)
    prefix = prefix.strip(".-")[:48] or "moneypal-workbench"
    return f"{prefix}-{digest}.bin"


async def slot_action(
    action: str, *, filename: str | None = None,
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
            if settings.llm_api_key else None
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


__all__ = ["SlotCacheError", "llama_server_root", "snapshot_filename", "slot_action"]
