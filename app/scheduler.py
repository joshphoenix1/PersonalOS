"""APScheduler driver, wired into FastAPI lifespan.

Runs in-process alongside the API. On startup we fire each job once immediately
so the dashboard has fresh data within seconds of boot, then fall into cadence.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.config import settings
from app.db.init import prune_old
from app.ingest.markets import fetch_markets
from app.ingest.run import run_ingest
from app.ingest.weather import fetch_weather

log = logging.getLogger(__name__)

_scheduler: BackgroundScheduler | None = None


def _safe(fn, label: str):
    def _wrap():
        try:
            fn()
        except Exception:
            log.exception("%s job failed", label)
    _wrap.__name__ = f"safe_{label}"
    return _wrap


def start_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        return

    sched = BackgroundScheduler(timezone="UTC")

    # Stagger first runs by a few seconds so they don't collide on boot.
    now = datetime.now(timezone.utc)
    sched.add_job(
        _safe(run_ingest, "news"),
        trigger=IntervalTrigger(minutes=settings.news_interval_min),
        next_run_time=now + timedelta(seconds=2),
        id="news", max_instances=1, coalesce=True,
    )
    sched.add_job(
        _safe(fetch_markets, "markets"),
        trigger=IntervalTrigger(minutes=settings.news_interval_min),
        next_run_time=now + timedelta(seconds=5),
        id="markets", max_instances=1, coalesce=True,
    )
    sched.add_job(
        _safe(fetch_weather, "weather"),
        trigger=IntervalTrigger(minutes=settings.weather_interval_min),
        next_run_time=now + timedelta(seconds=8),
        id="weather", max_instances=1, coalesce=True,
    )
    sched.add_job(
        _safe(lambda: prune_old(), "prune"),
        trigger=IntervalTrigger(hours=24),
        next_run_time=now + timedelta(hours=6),
        id="prune", max_instances=1, coalesce=True,
    )

    sched.start()
    _scheduler = sched
    log.info("scheduler started: news=%dm markets=%dm weather=%dm",
             settings.news_interval_min, settings.news_interval_min, settings.weather_interval_min)


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
