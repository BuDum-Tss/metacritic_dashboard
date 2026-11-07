"""The analysis: reads the reviews of the games the crawl stored and builds their summaries."""

import logging
from datetime import datetime

from app.config import settings
from app.db import repository, review_repository
from app.db.session import session_scope
from app.llm import LLMClient, make_llm_client
from app.services import summaries
from app.services.pipelines import ANALYSIS, exclusive
from app.sources.base import GameSource

log = logging.getLogger(__name__)


def is_enabled() -> bool:
    """The analysis needs a model; without an API key it is off."""
    return bool(settings.llm_api_key)


def run_analysis(
    source: GameSource,
    trigger: str,
    now: datetime | None = None,
    budget: int | None = None,
    llm: LLMClient | None = None,
) -> int | None:
    """Build the summaries that are due, for at most `budget` games.

    Returns the id of the sync run, or None when there is no model and nothing was done.
    """
    with exclusive(ANALYSIS):
        llm = llm or make_llm_client()
        if llm is None:
            log.info("analysis is off: no LLM_API_KEY")
            return None
        return _run(source, trigger, now or repository.utcnow(), budget or settings.analysis_budget, llm)


def _run(source: GameSource, trigger: str, started: datetime, budget: int, llm: LLMClient) -> int:
    day_start = started.replace(hour=0, minute=0, second=0, microsecond=0)

    with session_scope() as session:
        batch_index = repository.count_successful_runs(session, source.name, day_start, ANALYSIS)
        run_id = repository.start_run(session, source.name, trigger, batch_index, started, ANALYSIS).id
    log.info("analysis run %d started: %s (%s)", run_id, source.name, trigger)

    found = processed = failed = 0
    try:
        # the queue comes from the database alone: no request to the site
        with session_scope() as session:
            queue = review_repository.analysis_queue(
                session, source.name, started, budget, settings.summary_min_interval_hours
            )
        found = len(queue)
        log.info("analysis run %d: %d games in the queue", run_id, found)

        for item in queue:
            details, error = None, None
            try:
                with session_scope() as session:
                    game = repository.load_source_game(session, item.game_id)
                details = summaries.build_summaries(
                    source, game, item.game_id, item.plans, llm, repository.utcnow()
                )
                processed += 1
                results = set(details.values())
                outcome = "summarized" if "created" in results else "retry" if "model_unavailable" in results else "checked"
            except Exception as exc:
                log.exception("failed to analyze game %s", item.slug)
                outcome, error = "failed", f"{type(exc).__name__}: {exc}"
                failed += 1
            with session_scope() as session:
                repository.add_run_game(session, run_id, source.name, item.slug, outcome, details, error)
                repository.update_progress(session, run_id, found, processed, failed)

        status, error = "success", None
    except Exception as exc:
        log.exception("analysis run %d failed", run_id)
        status, error = "failed", f"{type(exc).__name__}: {exc}"

    with session_scope() as session:
        repository.finish_run(session, run_id, status, repository.utcnow(), found, processed, failed, error)
    log.info("analysis run %d %s: found=%d processed=%d failed=%d", run_id, status, found, processed, failed)
    return run_id
