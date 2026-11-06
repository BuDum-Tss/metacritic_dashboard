import logging
import threading
from datetime import datetime

from app.config import settings
from app.db import repository
from app.db.session import session_scope
from app.sources.base import GameSource

log = logging.getLogger(__name__)

_lock = threading.Lock()


class SyncAlreadyRunning(Exception):
    pass


def is_running() -> bool:
    return _lock.locked()


def run_cycle(source: GameSource, trigger: str, now: datetime | None = None, batch_size: int | None = None) -> int:
    """Process one batch of games from `source`. Returns the id of the sync run."""
    if not _lock.acquire(blocking=False):
        raise SyncAlreadyRunning
    try:
        return _run(source, trigger, now or repository.utcnow(), batch_size or settings.batch_size)
    finally:
        _lock.release()


def _run(source: GameSource, trigger: str, started: datetime, batch_size: int) -> int:
    day_start = started.replace(hour=0, minute=0, second=0, microsecond=0)

    with session_scope() as session:
        batch_index = repository.count_successful_runs(session, source.name, day_start)
        run_id = repository.start_run(session, source.name, trigger, batch_index, started).id
    log.info("sync run %d started: %s batch %d (%s)", run_id, source.name, batch_index, trigger)

    found = processed = failed = 0
    try:
        refs = source.list_batch(batch_index, batch_size)
        with session_scope() as session:
            done_today = repository.processed_since(session, source.name, day_start)
        refs = [ref for ref in refs if ref not in done_today]
        found = len(refs)

        for ref in refs:
            try:
                game = source.fetch_game(ref)
                with session_scope() as session:
                    repository.save_game(session, source.name, game, repository.utcnow())
                processed += 1
            except Exception:
                log.exception("failed to process game %s", ref)
                failed += 1
            with session_scope() as session:
                repository.update_progress(session, run_id, found, processed, failed)

        status, error = "success", None
    except Exception as exc:
        log.exception("sync run %d failed", run_id)
        status, error = "failed", f"{type(exc).__name__}: {exc}"

    with session_scope() as session:
        repository.finish_run(session, run_id, status, repository.utcnow(), found, processed, failed, error)
    log.info("sync run %d %s: found=%d processed=%d failed=%d", run_id, status, found, processed, failed)
    return run_id
