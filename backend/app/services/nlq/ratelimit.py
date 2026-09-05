"""Per-user rate limiting and LLM concurrency caps (§7.6).

Two different resources are protected. Questions per minute bounds cost and abuse; the
concurrency semaphore bounds a self-hosted llama-server, which has a fixed number of
parallel slots and degrades badly when oversubscribed rather than queueing gracefully.

In-process counters. Correct for the single-backend deployment this runs on; a multi-replica
deployment would need Redis, and the limit would need moving before that happens.
"""

from __future__ import annotations

import asyncio
import threading
import time
from collections import defaultdict, deque

QUESTIONS_PER_MINUTE = 30
# One local inference at a time. On the deployed Qwen3.6 hybrid model, a second slot doing
# prefill drops the active slot from ~20 token/s to effectively zero and makes recurrent
# prompt-cache reuse unreliable. This in-process semaphore is paired with the shared-file
# lock in llm/client.py because the API and PostgreSQL MCP are separate processes.
MAX_CONCURRENT_LLM = 1

_windows: dict[str, deque[float]] = defaultdict(deque)
_lock = threading.Lock()
_llm_semaphore: asyncio.Semaphore | None = None


class RateLimitExceeded(RuntimeError):
    def __init__(self, retry_after: int) -> None:
        super().__init__(
            f"Too many questions. Please wait {retry_after}s before asking another."
        )
        self.retry_after = retry_after


def check_rate_limit(user: str, *, limit: int | None = None) -> None:
    """Sliding window per user. Raises RateLimitExceeded when over.

    The limit is read at call time rather than bound as a default argument, so changing
    QUESTIONS_PER_MINUTE actually takes effect instead of being frozen at import.
    """
    limit = QUESTIONS_PER_MINUTE if limit is None else limit
    now = time.monotonic()
    with _lock:
        window = _windows[user]
        while window and now - window[0] > 60.0:
            window.popleft()
        if len(window) >= limit:
            raise RateLimitExceeded(retry_after=max(1, int(60 - (now - window[0]))))
        window.append(now)


def llm_semaphore() -> asyncio.Semaphore:
    """Lazily created so it binds to the running loop rather than import-time state."""
    global _llm_semaphore
    if _llm_semaphore is None:
        _llm_semaphore = asyncio.Semaphore(MAX_CONCURRENT_LLM)
    return _llm_semaphore


def reset() -> None:
    """Test hook."""
    global _llm_semaphore
    with _lock:
        _windows.clear()
    _llm_semaphore = None
