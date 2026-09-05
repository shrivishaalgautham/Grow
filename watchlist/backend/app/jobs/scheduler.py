import logging

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI

from app import clock
from app.cache import cache
from app.config import settings
from app.jobs.daily import run_daily
from app.jobs.refresh import refresh_tick
from app.notify.dispatch import dispatch

log = logging.getLogger(__name__)

LOCK_TTL_S = 55

_scheduler: BackgroundScheduler | None = None


def refresh_job() -> None:
    now = clock.now()
    if settings.scheduler_market_hours_only and clock.market_status(now) != "open":
        return
    if not cache.set_nx("refresh:lock", "1", LOCK_TTL_S):
        log.info("refresh skipped=lock_held")
        return
    refresh_tick(now)


def notify_job() -> None:
    now = clock.now()
    if settings.scheduler_market_hours_only and clock.market_status(now) != "open":
        return
    dispatch(now)


def start_scheduler(app: FastAPI) -> None:
    global _scheduler
    if settings.replay_date:
        log.info("scheduler disabled reason=replay_date date=%s", settings.replay_date)
        return
    scheduler = BackgroundScheduler(timezone="Asia/Kolkata")
    scheduler.add_job(
        refresh_job,
        "interval",
        seconds=settings.refresh_hot_seconds,
        id="refresh",
        max_instances=1,
        coalesce=True,
    )
    scheduler.add_job(
        notify_job,
        "interval",
        seconds=settings.notify_interval_seconds,
        id="notify",
        max_instances=1,
        coalesce=True,
    )
    scheduler.add_job(
        run_daily,
        "cron",
        day_of_week="mon-fri",
        hour=16,
        minute=0,
        id="daily",
        max_instances=1,
        coalesce=True,
    )
    scheduler.start()
    _scheduler = scheduler
    app.state.scheduler = scheduler
    log.info(
        "scheduler started refresh_seconds=%d market_hours_only=%s",
        settings.refresh_hot_seconds,
        settings.scheduler_market_hours_only,
    )


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler is None:
        return
    _scheduler.shutdown(wait=False)
    _scheduler = None
    log.info("scheduler stopped")
