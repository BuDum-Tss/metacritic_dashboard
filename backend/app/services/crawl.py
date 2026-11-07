"""The crawl: finds new games in the lists and keeps the known ones up to date."""

import logging
from datetime import datetime

from app.config import settings
from app.db import repository
from app.db.session import session_scope
from app.services import schedule
from app.services.pipelines import CRAWL, exclusive
from app.sources.base import GameSource

log = logging.getLogger(__name__)


def run_crawl(source: GameSource, trigger: str, now: datetime | None = None, budget: int | None = None) -> int:
    """Load new games and the known games that are due. Returns the id of the sync run.

    At most `budget` games are loaded: the new ones first, then the revisits.
    """
    with exclusive(CRAWL):
        return _run(source, trigger, now or repository.utcnow(), budget or settings.crawl_budget)


def _process(source: GameSource, ref: str) -> None:
    """Load a game by its own ref, store it and schedule the next visit."""
    game = source.fetch_game(ref)
    now = repository.utcnow()
    with session_scope() as session:
        saved = repository.save_game(session, source.name, game, now)
    with session_scope() as session:
        repository.set_next_check(session, saved.game_id, schedule.next_check(saved.first_seen_at, now))


def _postpone(source: GameSource, ref: str) -> None:
    try:
        with session_scope() as session:
            repository.postpone(session, source.name, ref, schedule.failure_backoff(repository.utcnow()))
    except Exception:
        log.exception("could not postpone %s", ref)


def _run(source: GameSource, trigger: str, started: datetime, budget: int) -> int:
    day_start = started.replace(hour=0, minute=0, second=0, microsecond=0)

    with session_scope() as session:
        batch_index = repository.count_successful_runs(session, source.name, day_start, CRAWL)
        run_id = repository.start_run(session, source.name, trigger, batch_index, started, CRAWL).id
    log.info("crawl run %d started: %s (%s)", run_id, source.name, trigger)

    found = processed = failed = 0
    try:
        discovered = source.discover(settings.discovery_depth)
        with session_scope() as session:
            known = repository.known_slugs(session, source.name, discovered)
            due = repository.due_slugs(session, source.name, started, budget)
        new = [ref for ref in discovered if ref not in known]

        new_take = new[:budget]
        due_take = due[: budget - len(new_take)]
        work = [(ref, True) for ref in new_take] + [(ref, False) for ref in due_take]
        found = len(work)
        log.info(
            "crawl run %d: %d new, %d to revisit (%d new and %d due waiting)",
            run_id, len(new_take), len(due_take), len(new), len(due),
        )

        for ref, is_new in work:
            try:
                _process(source, ref)
                processed += 1
            except Exception:
                log.exception("failed to process game %s", ref)
                failed += 1
                if not is_new:
                    _postpone(source, ref)  # a new game that failed is simply found again by the next run
            with session_scope() as session:
                repository.update_progress(session, run_id, found, processed, failed)

        status, error = "success", None
    except Exception as exc:
        log.exception("crawl run %d failed", run_id)
        status, error = "failed", f"{type(exc).__name__}: {exc}"

    with session_scope() as session:
        repository.finish_run(session, run_id, status, repository.utcnow(), found, processed, failed, error)
    log.info("crawl run %d %s: found=%d processed=%d failed=%d", run_id, status, found, processed, failed)
    return run_id
