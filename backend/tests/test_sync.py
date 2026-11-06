import threading
from datetime import datetime

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import sessionmaker

from app.db import session as db_session
from app.db.models import Game, ReviewSummary, SyncRun
from app.db.session import init_db, make_engine, session_scope
from app.services import sync
from app.sources.base import Game as SourceGame
from app.sources.base import PlatformScore, Review, ReviewBundle

NOW = datetime(2026, 11, 6, 10, 0)


class FakeSource:
    name = "fake"

    def __init__(self, batches: dict[int, list[str]], broken: set[str] = frozenset()):
        self.batches = batches
        self.broken = broken
        self.fetched: list[str] = []
        self.requested: list[int] = []

    def list_batch(self, batch_index: int, limit: int) -> list[str]:
        self.requested.append(batch_index)
        if batch_index not in self.batches:
            raise RuntimeError("no such batch")
        return self.batches[batch_index]

    def fetch_game(self, ref: str) -> SourceGame:
        self.fetched.append(ref)
        if ref in self.broken:
            raise ValueError("cannot parse")
        return SourceGame(
            slug=ref,
            url=f"https://example.com/{ref}/",
            title=ref.title(),
            platforms=[PlatformScore(slug="pc", name="PC", metascore=80)],
        )


@pytest.fixture(autouse=True)
def database(tmp_path, monkeypatch):
    engine = make_engine(str(tmp_path / "sync.db"))
    init_db(engine)
    monkeypatch.setattr(db_session, "SessionLocal", sessionmaker(engine, expire_on_commit=False))


def runs() -> list[SyncRun]:
    with session_scope() as s:
        return list(s.scalars(select(SyncRun).order_by(SyncRun.id)))


def game_count() -> int:
    with session_scope() as s:
        return s.scalar(select(func.count()).select_from(Game))


def test_successful_cycle_saves_games_and_logs_the_run():
    source = FakeSource({0: ["a", "b", "c"]})
    run_id = sync.run_cycle(source, "schedule", now=NOW)

    [run] = runs()
    assert run.id == run_id
    assert (run.status, run.trigger, run.source, run.batch_index) == ("success", "schedule", "fake", 0)
    assert (run.games_found, run.games_processed, run.games_failed) == (3, 3, 0)
    assert run.finished_at is not None and run.error is None
    assert game_count() == 3


def test_next_cycle_takes_next_batch():
    source = FakeSource({0: ["a"], 1: ["b"]})
    sync.run_cycle(source, "schedule", now=NOW)
    sync.run_cycle(source, "manual", now=NOW)
    assert source.requested == [0, 1]
    assert [r.batch_index for r in runs()] == [0, 1]


def test_new_day_starts_from_batch_zero_again():
    source = FakeSource({0: ["a"], 1: ["b"]})
    sync.run_cycle(source, "schedule", now=NOW)
    sync.run_cycle(source, "schedule", now=datetime(2026, 11, 7, 0, 5))
    assert source.requested == [0, 0]


def test_broken_game_does_not_stop_the_batch():
    source = FakeSource({0: ["a", "bad", "c"]}, broken={"bad"})
    sync.run_cycle(source, "schedule", now=NOW)
    [run] = runs()
    assert run.status == "success"
    assert (run.games_found, run.games_processed, run.games_failed) == (3, 2, 1)
    assert game_count() == 2


def test_games_processed_today_are_skipped():
    source = FakeSource({0: ["a", "b"], 1: ["b", "c"]})
    sync.run_cycle(source, "schedule", now=NOW)
    source.fetched.clear()
    sync.run_cycle(source, "schedule", now=NOW)
    assert source.fetched == ["c"]


def test_failed_batch_is_retried_with_the_same_index():
    source = FakeSource({})
    sync.run_cycle(source, "schedule", now=NOW)
    [run] = runs()
    assert run.status == "failed" and "no such batch" in run.error

    source.batches[0] = ["a"]
    sync.run_cycle(source, "schedule", now=NOW)
    assert source.requested == [0, 0]
    assert [r.status for r in runs()] == ["failed", "success"]


def test_second_cycle_cannot_start_while_one_is_running():
    started, release = threading.Event(), threading.Event()

    class SlowSource(FakeSource):
        def list_batch(self, batch_index, limit):
            started.set()
            release.wait(5)
            return []

    worker = threading.Thread(target=sync.run_cycle, args=(SlowSource({}), "schedule"))
    worker.start()
    assert started.wait(5)
    try:
        assert sync.is_running()
        with pytest.raises(sync.SyncAlreadyRunning):
            sync.run_cycle(FakeSource({0: []}), "manual")
    finally:
        release.set()
        worker.join()
    assert not sync.is_running()


class ReviewingSource(FakeSource):
    """A source that also has reviews, so summaries can be built."""

    def __init__(self, *args, fail_reviews: bool = False, **kwargs):
        super().__init__(*args, **kwargs)
        self.fail_reviews = fail_reviews
        self.review_fetches: list[str] = []

    def fetch_reviews(self, game):
        self.review_fetches.append(game.slug)
        if self.fail_reviews:
            raise RuntimeError("review pages are down")
        reviews = [
            Review(kind=kind, text=f"{kind} text {i}", score=score, author=f"{kind[0]}{i}", date="Nov 1, 2026")
            for kind in ("critics", "users")
            for i, score in enumerate([90, 80, 40] if kind == "critics" else [9, 8, 3])
        ]
        return ReviewBundle(reviews=reviews)


class StubLLM:
    model = "stub"

    def complete(self, system: str, user: str) -> str:
        return '{"likes": [{"text": "Good", "reviews": ["R1"]}], "dislikes": [{"text": "Bad", "reviews": ["R2"]}]}'


def summary_count() -> int:
    with session_scope() as s:
        return s.scalar(select(func.count()).select_from(ReviewSummary))


def test_cycle_builds_summaries_when_a_model_is_given():
    source = ReviewingSource({0: ["a", "b"]})
    sync.run_cycle(source, "schedule", now=NOW, llm=StubLLM())
    assert source.review_fetches == ["a", "b"]
    assert summary_count() == 4  # critics and users for each of the two games


def test_cycle_builds_no_summaries_without_a_model():
    source = ReviewingSource({0: ["a", "b"]})
    sync.run_cycle(source, "schedule", now=NOW)
    assert source.review_fetches == []
    assert summary_count() == 0


def test_failing_summaries_do_not_fail_the_game_or_the_run():
    source = ReviewingSource({0: ["a", "b"]}, fail_reviews=True)
    sync.run_cycle(source, "schedule", now=NOW, llm=StubLLM())
    [run] = runs()
    assert run.status == "success"
    assert (run.games_processed, run.games_failed) == (2, 0)
    assert game_count() == 2
