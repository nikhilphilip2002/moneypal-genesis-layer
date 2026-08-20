"""When the scan runs.

A plain asyncio loop rather than a scheduler dependency. There is exactly one job, it has no
calendar, and the failure mode that matters is "it silently stopped" — which a background task
with an explicit log line makes visible and a cron entry in a container nobody restarts does
not.

The scan runs off the event loop because it is synchronous psycopg2 work on the shared
read-only pool, and it takes the smallest slice of that pool of anything in the product. A
director's question must never wait for the nightly scan.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from datetime import datetime, timezone

from app.services.signals import scan, store

logger = logging.getLogger(__name__)

INTERVAL_S = 6 * 60 * 60
"""Four times a day. Nightly is the obvious cadence and is wrong for collections: arrears
move during the working day, and a signal that arrives tomorrow morning about this afternoon
has already cost a day of calls."""

STARTUP_DELAY_S = 60
"""Long enough for the warehouse connection to settle after a deploy. A scan that fails on
boot logs a scary error about a database that is merely still starting."""


async def run_forever(*, interval_s: int = INTERVAL_S) -> None:
    """Scan, store, sleep, repeat. Never raises — a failed scan is logged and retried."""
    await asyncio.sleep(STARTUP_DELAY_S)
    while True:
        await run_once()
        await asyncio.sleep(interval_s)


async def run_once() -> None:
    started = datetime.now(timezone.utc)
    try:
        report = await asyncio.to_thread(scan.run)
        new = await asyncio.to_thread(store.record, report.signals)
        logger.info(
            "signal scan: %d scopes, %d signals (%d new), %d abstained, %d failed, %dms",
            report.scopes_run, len(report.signals), new,
            len(report.abstained), report.scopes_failed, report.duration_ms,
        )
        # Abstention is a result, and one worth seeing in the log: a scan that has abstained
        # on the same scope for months is a scope whose data never arrived.
        if report.abstained:
            logger.info("signal scan abstained on: %s", ", ".join(report.abstained))
        for warning in report.warnings:
            logger.warning("signal scan: %s", warning)
    except Exception as exc:  # noqa: BLE001 - the loop must survive anything
        logger.exception("signal scan failed after %s: %s", started, exc)


def start(app_state) -> asyncio.Task | None:
    """Launch the loop as a background task, if scanning is enabled."""
    from app.core.config import settings

    if not getattr(settings, "signals_scan_enabled", True):
        logger.info("signal scan disabled by configuration")
        return None
    task = asyncio.create_task(
        run_forever(interval_s=getattr(settings, "signals_scan_interval_s", INTERVAL_S))
    )
    app_state.signal_scan_task = task
    return task


async def stop(task: asyncio.Task | None) -> None:
    if task is None or task.done():
        return
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task


__all__ = ["INTERVAL_S", "run_forever", "run_once", "start", "stop"]
