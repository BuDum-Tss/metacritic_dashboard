import asyncio
import logging
from datetime import datetime, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.config import settings
from app.services.sync import SyncAlreadyRunning, run_cycle
from app.sources.base import GameSource

log = logging.getLogger(__name__)

JOB_ID = "sync"


async def scheduled_cycle(source: GameSource) -> None:
    try:
        await asyncio.to_thread(run_cycle, source, "schedule")
    except SyncAlreadyRunning:
        log.info("scheduled sync skipped: a cycle is already running")


def create_scheduler(source: GameSource) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone="UTC")
    extra = {"next_run_time": datetime.now(timezone.utc)} if settings.sync_run_on_startup else {}
    scheduler.add_job(
        scheduled_cycle,
        IntervalTrigger(hours=settings.sync_interval_hours),
        args=[source],
        id=JOB_ID,
        max_instances=1,
        coalesce=True,
        **extra,
    )
    return scheduler
