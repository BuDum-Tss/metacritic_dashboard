"""The two pipelines of the service and the lock that keeps each of them to one run at a time."""

import threading
from collections.abc import Iterator
from contextlib import contextmanager

CRAWL = "crawl"  # finds games and loads their pages
ANALYSIS = "analysis"  # reads the reviews and builds the summaries
VIDEOS = "videos"  # finds the let's play and the review of a game on YouTube
PIPELINES = (CRAWL, ANALYSIS, VIDEOS)

_locks = {name: threading.Lock() for name in PIPELINES}


class PipelineRunning(Exception):
    pass


def is_running(pipeline: str) -> bool:
    return _locks[pipeline].locked()


@contextmanager
def exclusive(pipeline: str) -> Iterator[None]:
    """Hold the pipeline for a run; raise PipelineRunning when it is already running."""
    lock = _locks[pipeline]
    if not lock.acquire(blocking=False):
        raise PipelineRunning(pipeline)
    try:
        yield
    finally:
        lock.release()
