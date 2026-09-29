from __future__ import annotations

import asyncio
import hashlib
import os
import time
from contextlib import asynccontextmanager
from weakref import WeakValueDictionary

from app.core.config import settings
from app.services.nlq.llm.client import fcntl

_locks: WeakValueDictionary[str, asyncio.Lock] = WeakValueDictionary()


@asynccontextmanager
async def conversation_lock(conversation_id: str):
    digest = hashlib.sha256(conversation_id.encode()).hexdigest()[:2]
    lock = _locks.setdefault(digest, asyncio.Lock())
    async with asyncio.timeout(settings.nlq_request_budget_s):
        async with lock:
            if fcntl is None:
                yield
                return
            directory = (
                settings.nlq_llm_lock_path.parent / "workbench-conversations"
            )
            directory.mkdir(parents=True, exist_ok=True)
            descriptor = os.open(
                directory / f"{digest}.lock", os.O_CREAT | os.O_RDWR, 0o600
            )
            deadline = time.monotonic() + settings.nlq_request_budget_s
            try:
                while True:
                    try:
                        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
                        break
                    except BlockingIOError:
                        if time.monotonic() >= deadline:
                            raise TimeoutError(
                                "Another turn is still using this conversation"
                            )
                        await asyncio.sleep(0.05)
                yield
            finally:
                fcntl.flock(descriptor, fcntl.LOCK_UN)
                os.close(descriptor)
