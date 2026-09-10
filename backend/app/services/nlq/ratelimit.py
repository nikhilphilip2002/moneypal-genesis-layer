"""Concurrency cap for the shared LLM endpoint."""

from __future__ import annotations

import asyncio
# One local inference at a time. On the deployed Qwen3.6 hybrid model, a second slot doing
# prefill drops the active slot from ~20 token/s to effectively zero and makes recurrent
# prompt-cache reuse unreliable. This in-process semaphore is paired with the shared-file
# lock in llm/client.py because the API and PostgreSQL MCP are separate processes.
MAX_CONCURRENT_LLM = 1

_llm_semaphore: asyncio.Semaphore | None = None


def llm_semaphore() -> asyncio.Semaphore:
    """Lazily created so it binds to the running loop rather than import-time state."""
    global _llm_semaphore
    if _llm_semaphore is None:
        _llm_semaphore = asyncio.Semaphore(MAX_CONCURRENT_LLM)
    return _llm_semaphore


def reset() -> None:
    """Test hook."""
    global _llm_semaphore
    _llm_semaphore = None
