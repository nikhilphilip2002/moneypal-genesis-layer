"""Explicit lifecycle management for persistent llama.cpp prompt-slot snapshots.

Nothing in this module runs in the request path. Operators invoke it after llama-server
and PostgreSQL MCP are ready, before exposing the backend to traffic.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from typing import Any, Awaitable, Callable
from urllib.parse import urlsplit, urlunsplit

import httpx

from app.core.config import settings
from app.mcp import postgres_client
from app.services.nlq.catalog import get_catalog
from app.services.workbench import models, prompts
from app.services.workbench.access import build_policy
from app.services.workbench.agent_tools import native_tool_definitions


WARMUP_QUESTION = "Check the governed data tools and prepare to answer a future bank question."


class SlotCacheError(RuntimeError):
    """A llama-server slot operation or safe warm-up failed."""


@dataclass(frozen=True, slots=True)
class SlotCacheIdentity:
    fingerprint: str
    filename: str
    model: str
    catalog_version: str
    prompt_sha256: str
    tools_sha256: str


@dataclass(frozen=True, slots=True)
class WarmupBundle:
    messages: list[dict[str, Any]]
    tools: list[dict[str, Any]]
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


def build_identity(
    *, messages: list[dict[str, Any]], tools: list[dict[str, Any]], catalog_version: str
) -> SlotCacheIdentity:
    prompt_hash = _sha256(messages)
    tools_hash = _sha256(tools)
    material = {
        "schema": 1,
        "model": settings.llm_model,
        "model_sha256": settings.llama_model_sha256,
        "llama_server_build_id": settings.llama_server_build_id,
        "chat_template_id": settings.llama_chat_template_id,
        "catalog_version": catalog_version,
        "messages_sha256": prompt_hash,
        "tools_sha256": tools_hash,
        "tool_choice": "required",
        "parallel_tool_calls": False,
    }
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
        catalog_version=catalog_version,
        prompt_sha256=prompt_hash,
        tools_sha256=tools_hash,
    )


async def build_warmup_bundle() -> WarmupBundle:
    """Build the real admin tool envelope around a constant, non-private question."""
    catalog = get_catalog()
    policy = build_policy(role="admin", external_sources_enabled=False)
    definitions = native_tool_definitions(policy, catalog=catalog)
    if policy.allows("db"):
        await postgres_client.discover_model_tools()
        definitions = [*postgres_client.model_tool_definitions(), *definitions]
    if not definitions:
        raise SlotCacheError("no native tools are available for slot warm-up")
    prompt = prompts.build_agent_prompt(
        question=WARMUP_QUESTION,
        tool_names=[definition["function"]["name"] for definition in definitions],
        catalog=catalog,
    )
    messages = list(prompt.messages)
    return WarmupBundle(
        messages=messages,
        tools=definitions,
        identity=build_identity(
            messages=messages, tools=definitions, catalog_version=catalog.version
        ),
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


async def warm_slot(bundle: WarmupBundle) -> dict[str, Any]:
    """Evaluate the stable prefix without executing any model-selected tool."""
    result = await models.client().complete(
        messages=bundle.messages,
        tools=bundle.tools,
        tool_choice="required",
        parallel_tool_calls=False,
        timeout_s=settings.llm_timeout_s,
        call_purpose="slot_cache_warmup",
        call_kind="warmup",
        prompt_version="workbench-agent-slot-v1",
        catalog_version=bundle.identity.catalog_version,
        prefix_hash=bundle.identity.prompt_sha256,
        max_output_tokens=512,
    )
    return {
        "finish_reason": result.finish_reason,
        "prompt_tokens": result.prompt_tokens,
        "cached_prompt_tokens": result.cached_prompt_tokens,
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
    "WarmupBundle",
    "build_identity",
    "build_warmup_bundle",
    "llama_server_root",
    "restore_or_warm",
    "slot_action",
    "warm_slot",
]
