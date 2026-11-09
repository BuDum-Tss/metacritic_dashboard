import asyncio
from datetime import timedelta

from app.config import settings
from app.scheduler import create_scheduler


class Nothing:
    name = "fake"


def jobs(monkeypatch=None):
    """Start a paused scheduler (nothing runs) and read the jobs' first run times."""

    async def read():
        scheduler = create_scheduler(Nothing(), Nothing())
        scheduler.start(paused=True)
        try:
            crawl, analysis = scheduler.get_job("crawl"), scheduler.get_job("analysis")
            return crawl.next_run_time, analysis.next_run_time, crawl.trigger.interval, analysis.trigger.interval
        finally:
            scheduler.shutdown(wait=False)

    return asyncio.run(read())


def test_two_jobs_the_analysis_half_an_hour_after_the_crawl():
    crawl_first, analysis_first, crawl_every, analysis_every = jobs()
    assert analysis_first - crawl_first == timedelta(minutes=settings.analysis_offset_minutes) == timedelta(minutes=30)
    assert crawl_every == timedelta(hours=settings.crawl_interval_hours)
    assert analysis_every == timedelta(hours=settings.analysis_interval_hours)


def test_the_offset_holds_when_the_crawl_does_not_start_at_once(monkeypatch):
    monkeypatch.setattr(settings, "sync_run_on_startup", False)
    crawl_first, analysis_first, *_ = jobs()
    assert analysis_first - crawl_first == timedelta(minutes=30)


def test_the_intervals_are_set_separately(monkeypatch):
    monkeypatch.setattr(settings, "crawl_interval_hours", 2)
    monkeypatch.setattr(settings, "analysis_interval_hours", 6)
    *_, crawl_every, analysis_every = jobs()
    assert (crawl_every, analysis_every) == (timedelta(hours=2), timedelta(hours=6))


def video_job():
    """The first run time and the interval of the video search job, and the crawl's first run."""

    async def read():
        scheduler = create_scheduler(Nothing(), Nothing())
        scheduler.start(paused=True)
        try:
            crawl, videos = scheduler.get_job("crawl"), scheduler.get_job("videos")
            return crawl.next_run_time, videos.next_run_time, videos.trigger.interval
        finally:
            scheduler.shutdown(wait=False)

    return asyncio.run(read())


def test_the_video_search_is_a_third_job_45_minutes_after_the_crawl():
    crawl_first, videos_first, every = video_job()
    assert videos_first - crawl_first == timedelta(minutes=settings.videos_offset_minutes) == timedelta(minutes=45)
    assert every == timedelta(hours=settings.videos_interval_hours)


def test_the_video_offset_holds_when_the_crawl_does_not_start_at_once(monkeypatch):
    monkeypatch.setattr(settings, "sync_run_on_startup", False)
    crawl_first, videos_first, _ = video_job()
    assert videos_first - crawl_first == timedelta(minutes=45)
