import asyncio
import contextlib

import pytest

from app.core.config import settings
from app.services.workbench.conversation_lock import conversation_lock


@pytest.mark.anyio
async def test_cancelled_turn_releases_conversation_for_waiting_turn(
    monkeypatch, tmp_path
):
    monkeypatch.setattr(settings, "nlq_llm_lock_path", tmp_path / "llm.lock")
    entered = asyncio.Event()
    second_started = asyncio.Event()
    second_entered = asyncio.Event()

    async def first():
        async with conversation_lock("shared-conversation"):
            entered.set()
            await asyncio.Event().wait()

    async def second():
        second_started.set()
        async with conversation_lock("shared-conversation"):
            second_entered.set()

    first_task = asyncio.create_task(first())
    second_task = None
    try:
        await asyncio.wait_for(entered.wait(), timeout=1)
        second_task = asyncio.create_task(second())
        await asyncio.wait_for(second_started.wait(), timeout=1)
        assert not second_entered.is_set()
        first_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await first_task
        await asyncio.wait_for(second_task, timeout=1)
        assert second_entered.is_set()
    finally:
        first_task.cancel()
        if second_task is not None:
            second_task.cancel()
        await asyncio.gather(
            first_task,
            *([second_task] if second_task else []),
            return_exceptions=True,
        )
