"""Long-lived worker — runs the macro refresh on a weekly schedule.

Weekly, not daily: the Economic Survey and MOSPI release on a monthly-or-slower
cadence, so a daily crawl re-downloads tens of megabytes to discover nothing had
changed. Default is Sunday 10:00 IST, all four fields env-driven.

The process keeps bge-m3 resident, so the scheduled run pays no model cold start.
Keep it alive with the OS service manager (compose ``restart: unless-stopped``,
systemd ``Restart=always``, or pm2).
"""
from __future__ import annotations

import logging

from genesis_core import rag

from app.core.config import settings

from . import pipeline

log = logging.getLogger("macro.scheduler")


def _run_once(force: bool = False) -> None:
    try:
        summary = pipeline.run(force=force)
    except Exception:
        # A scheduled run must never kill the worker — log and wait for next week.
        log.exception("macro refresh failed")
        return
    pipeline.print_summary(summary)


def main() -> int:
    from apscheduler.schedulers.blocking import BlockingScheduler
    from apscheduler.triggers.cron import CronTrigger

    if settings.macro_run_on_startup:
        log.info("MACRO_RUN_ON_STARTUP=true — running a refresh now")
        rag.get_embedder()
        _run_once()
    else:
        # Load the model anyway so the first scheduled run is not the one that pays
        # the ~2 GB download/load cost.
        log.info("Warming the embedding model ...")
        rag.get_embedder()

    scheduler = BlockingScheduler(timezone=settings.macro_schedule_tz)
    scheduler.add_job(
        _run_once,
        trigger=CronTrigger(
            day_of_week=settings.macro_schedule_day,
            hour=settings.macro_schedule_hour,
            minute=settings.macro_schedule_minute,
        ),
        id="macro_weekly_refresh",
        name="Macro Intelligence weekly refresh",
        # A missed window (host asleep, deploy in flight) should still run when the
        # worker comes back, but only once.
        misfire_grace_time=6 * 3600,
        coalesce=True,
        max_instances=1,
        kwargs={"force": False},
    )
    log.info(
        "Scheduler started — weekly refresh on %s at %02d:%02d %s, collection=%s",
        settings.macro_schedule_day,
        settings.macro_schedule_hour,
        settings.macro_schedule_minute,
        settings.macro_schedule_tz,
        settings.macro_collection,
    )
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        log.info("Scheduler stopped.")
    return 0
