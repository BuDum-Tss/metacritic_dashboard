import asyncio
import logging
from datetime import datetime, timedelta, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.config import settings
from app.services.analysis import run_analysis
from app.services.crawl import run_crawl
from app.services.pipelines import ANALYSIS, CRAWL, VIDEOS, PipelineRunning
from app.services.videos import run_videos
from app.sources.base import GameSource

log = logging.getLogger(__name__)


async def scheduled_crawl(source: GameSource) -> None:
    try:
        await asyncio.to_thread(run_crawl, source, "schedule")
    except PipelineRunning:
        log.info("scheduled crawl skipped: the previous one is still running")


async def scheduled_analysis(source: GameSource) -> None:
    try:
        await asyncio.to_thread(run_analysis, source, "schedule")
    except PipelineRunning:
        log.info("scheduled analysis skipped: the previous one is still running")


async def scheduled_videos() -> None:
    try:
        await asyncio.to_thread(run_videos, "schedule")
    except PipelineRunning:
        log.info("scheduled video search skipped: the previous one is still running")


def create_scheduler(crawl_source: GameSource, analysis_source: GameSource) -> AsyncIOScheduler:
    """Three independent jobs: the crawl starts at once, the analysis and the video search later."""
    scheduler = AsyncIOScheduler(timezone="UTC")
    now = datetime.now(timezone.utc)
    offset = timedelta(minutes=settings.analysis_offset_minutes)

    crawl_interval = timedelta(hours=settings.crawl_interval_hours)
    analysis_interval = timedelta(hours=settings.analysis_interval_hours)
    videos_interval = timedelta(hours=settings.videos_interval_hours)
    videos_offset = timedelta(minutes=settings.videos_offset_minutes)
    if settings.sync_run_on_startup:
        crawl_first, analysis_first, videos_first = now, now + offset, now + videos_offset
    else:
        crawl_first = now + crawl_interval
        analysis_first = crawl_first + offset
        videos_first = crawl_first + videos_offset

    scheduler.add_job(
        scheduled_crawl,
        IntervalTrigger(seconds=int(crawl_interval.total_seconds())),
        args=[crawl_source],
        id=CRAWL,
        max_instances=1,
        coalesce=True,
        next_run_time=crawl_first,
    )
    scheduler.add_job(
        scheduled_analysis,
        IntervalTrigger(seconds=int(analysis_interval.total_seconds())),
        args=[analysis_source],
        id=ANALYSIS,
        max_instances=1,
        coalesce=True,
        next_run_time=analysis_first,
    )
    scheduler.add_job(
        scheduled_videos,
        IntervalTrigger(seconds=int(videos_interval.total_seconds())),
        id=VIDEOS,
        max_instances=1,
        coalesce=True,
        next_run_time=videos_first,
    )
    return scheduler
