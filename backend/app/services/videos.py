"""The video search: finds the let's play and the review of the games the crawl stored."""

import logging
from datetime import datetime, timedelta

from app.config import settings
from app.db import repository, video_repository
from app.db.session import session_scope
from app.services.pipelines import VIDEOS, exclusive
from app.videos.finder import VideoApi, VideoResult, find_video
from app.videos.youtube import QuotaExceeded, make_youtube_client

log = logging.getLogger(__name__)

SOURCE = "metacritic"  # the games the videos are searched for come from this source
OLD_GAME_RETRY_DAYS = 30  # an old game without a video is searched again this seldom
QUOTA_RESETS_AT_UTC_HOUR = 8  # the daily quota of the API resets at midnight Pacific time

# After the quota is used up the scheduled runs wait for the reset; the manual run still tries.
_quota_exhausted_until: datetime | None = None


def is_enabled() -> bool:
    """The video search needs a YouTube API key; without it the pipeline is off."""
    return bool(settings.youtube_api_key)


def next_check(found: bool, young: bool, now: datetime) -> datetime | None:
    """When a game is searched for a kind of video again; None: never."""
    if found:
        return now + timedelta(days=settings.videos_refresh_days) if young else None
    return now + timedelta(days=settings.videos_retry_days if young else OLD_GAME_RETRY_DAYS)


def _next_quota_reset(now: datetime) -> datetime:
    reset = now.replace(hour=QUOTA_RESETS_AT_UTC_HOUR, minute=0, second=0, microsecond=0)
    return reset if reset > now else reset + timedelta(days=1)


def run_videos(
    trigger: str,
    now: datetime | None = None,
    budget: int | None = None,
    api: VideoApi | None = None,
) -> int | None:
    """Search the videos that are due, for at most `budget` games.

    Returns the id of the sync run, or None when nothing was done: no API key, or the quota of
    the day is used up and the run is a scheduled one.
    """
    global _quota_exhausted_until
    now = now or repository.utcnow()
    with exclusive(VIDEOS):
        api = api or make_youtube_client()
        if api is None:
            log.info("video search is off: no YOUTUBE_API_KEY")
            return None
        if trigger == "schedule" and _quota_exhausted_until and now < _quota_exhausted_until:
            log.info("video search skipped: the YouTube quota is used up until %s", _quota_exhausted_until)
            return None
        return _run(trigger, now, budget or settings.videos_budget, api)


def _run(trigger: str, started: datetime, budget: int, api: VideoApi) -> int:
    global _quota_exhausted_until
    day_start = started.replace(hour=0, minute=0, second=0, microsecond=0)

    with session_scope() as session:
        batch_index = repository.count_successful_runs(session, SOURCE, day_start, VIDEOS)
        run_id = repository.start_run(session, SOURCE, trigger, batch_index, started, VIDEOS).id
    log.info("video run %d started (%s)", run_id, trigger)

    found = processed = failed = 0
    status, error = "success", None
    try:
        with session_scope() as session:
            queue = video_repository.video_queue(session, SOURCE, started, budget)
        found = len(queue)
        log.info("video run %d: %d games in the queue", run_id, found)

        for item in queue:
            details: dict[str, str] = {}
            failure = None
            try:
                young = (started - item.first_seen_at) < timedelta(days=settings.young_days)
                for kind in item.kinds:
                    result = find_video(api, item.title, kind, item.release_date, settings.videos_results)
                    with session_scope() as session:
                        # the run's own time: the queue and the age of the game are counted from it too
                        video_repository.save_video(
                            session, item.game_id, kind, result, started, next_check(result is not None, young, started)
                        )
                    details[kind] = _describe(result)
                processed += 1
                outcome = "found" if any(value != "none" for value in details.values()) else "none"
            except QuotaExceeded:
                raise
            except Exception as exc:
                log.exception("failed to search the videos of %s", item.slug)
                outcome, failure = "failed", f"{type(exc).__name__}: {exc}"
                failed += 1
            with session_scope() as session:
                repository.add_run_game(session, run_id, SOURCE, item.slug, outcome, details or None, failure)
                repository.update_progress(session, run_id, found, processed, failed)
    except QuotaExceeded:
        _quota_exhausted_until = _next_quota_reset(repository.utcnow())
        error = f"YouTube quota exhausted, scheduled runs wait until {_quota_exhausted_until:%Y-%m-%d %H:%M} UTC"
        log.warning("video run %d: %s", run_id, error)
    except Exception as exc:
        log.exception("video run %d failed", run_id)
        status, error = "failed", f"{type(exc).__name__}: {exc}"

    with session_scope() as session:
        repository.finish_run(session, run_id, status, repository.utcnow(), found, processed, failed, error)
    log.info("video run %d %s: found=%d processed=%d failed=%d", run_id, status, found, processed, failed)
    return run_id


def _describe(result: VideoResult | None) -> str:
    if result is None:
        return "none"
    return "playlist" if result.playlist_id else "video"
