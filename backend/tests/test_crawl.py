import threading
from datetime import datetime, timedelta

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.db import repository
from app.db import session as db_session
from app.db.models import Game, SyncRun
from app.db.session import init_db, make_engine, session_scope
from app.services import crawl
from app.services.pipelines import PipelineRunning, is_running
from app.sources.base import Game as SourceGame
from app.sources.base import PlatformScore

NOW = datetime(2026, 11, 6, 10, 0)


class FakeSource:
    name = "fake"

    def __init__(self, listed: list[str] = (), broken: set[str] = frozenset(), list_fails: bool = False):
        self.listed = list(listed)  # what the list of new games shows now, newest first
        self.broken = set(broken)
        self.list_fails = list_fails
        self.fetched: list[str] = []
        self.discovered_with: list[int] = []

    def discover(self, limit: int) -> list[str]:
        self.discovered_with.append(limit)
        if self.list_fails:
            raise RuntimeError("the list is down")
        return self.listed[:limit]

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


class Clock:
    def __init__(self):
        self.now = NOW

    def advance(self, **delta) -> datetime:
        self.now += timedelta(**delta)
        return self.now


@pytest.fixture
def clock(monkeypatch) -> Clock:
    clock = Clock()
    monkeypatch.setattr(repository, "utcnow", lambda: clock.now)
    return clock


@pytest.fixture(autouse=True)
def database(tmp_path, monkeypatch):
    engine = make_engine(str(tmp_path / "sync.db"))
    init_db(engine)
    monkeypatch.setattr(db_session, "SessionLocal", sessionmaker(engine, expire_on_commit=False))


def run(source, clock, budget=None) -> int:
    return crawl.run_crawl(source, "schedule", now=clock.now, budget=budget)


def runs() -> list[SyncRun]:
    with session_scope() as s:
        return list(s.scalars(select(SyncRun).order_by(SyncRun.id)))


def game_count() -> int:
    with session_scope() as s:
        return s.scalar(select(func.count()).select_from(Game))


def next_checks() -> dict[str, datetime]:
    with session_scope() as s:
        return {g.slug: g.next_check_at for g in s.scalars(select(Game))}


# ---------- discovery ----------


def test_new_games_are_found_saved_and_scheduled(clock):
    source = FakeSource(["a", "b", "c"])
    run_id = run(source, clock)

    [record] = runs()
    assert record.id == run_id
    assert (record.pipeline, record.status, record.trigger, record.source, record.batch_index) == (
        "crawl", "success", "schedule", "fake", 0
    )
    assert (record.games_found, record.games_processed, record.games_failed) == (3, 3, 0)
    assert record.finished_at is not None and record.error is None
    assert source.discovered_with == [settings.discovery_depth]
    assert game_count() == 3
    assert set(next_checks().values()) == {NOW + timedelta(hours=24)}  # young games come back daily


def test_known_games_are_not_fetched_again_before_their_time(clock):
    source = FakeSource(["a", "b"])
    run(source, clock)
    clock.advance(hours=1)
    run(source, clock)  # the list shows the same games, but they are known and not due yet
    assert source.fetched == ["a", "b"]


def test_the_run_number_of_the_day_is_counted(clock):
    source = FakeSource(["a"])
    run(source, clock)
    clock.advance(hours=1)
    run(source, clock)
    assert [r.batch_index for r in runs()] == [0, 1]


def test_a_failed_list_fails_the_run_and_saves_nothing(clock):
    run(FakeSource(list_fails=True), clock)
    [record] = runs()
    assert record.status == "failed" and "the list is down" in record.error
    assert game_count() == 0


def test_a_new_game_that_cannot_be_loaded_is_not_saved_and_found_again(clock):
    source = FakeSource(["a", "bad", "c"], broken={"bad"})
    run(source, clock)
    [record] = runs()
    assert record.status == "success"
    assert (record.games_found, record.games_processed, record.games_failed) == (3, 2, 1)
    assert game_count() == 2

    source.broken.clear()
    clock.advance(hours=1)
    run(source, clock)  # the list still shows it: it is a new game again
    assert game_count() == 3


# ---------- revisits ----------


def test_a_due_game_is_revisited_by_its_ref_even_after_it_left_the_list(clock):
    source = FakeSource(["a", "b"])
    run(source, clock)

    clock.advance(hours=25)
    source.listed = []  # the games dropped out of the list of new games
    run(source, clock)

    assert source.fetched == ["a", "b", "a", "b"]
    assert set(next_checks().values()) == {clock.now + timedelta(hours=24)}


def test_games_found_long_ago_are_revisited_weekly(clock):
    source = FakeSource(["a"])
    run(source, clock)

    clock.advance(days=settings.young_days + 1)
    run(source, clock)
    assert next_checks()["a"] == clock.now + timedelta(days=settings.revisit_old_days)


def test_a_revisit_that_fails_is_postponed_not_retried_every_run(clock):
    source = FakeSource(["a"])
    run(source, clock)

    clock.advance(hours=25)
    source.broken.add("a")
    run(source, clock)
    assert runs()[-1].games_failed == 1
    assert next_checks()["a"] == clock.now + timedelta(hours=24)

    clock.advance(hours=1)
    run(source, clock)  # not due yet: it is not asked for again
    assert source.fetched.count("a") == 2


def test_the_most_overdue_game_goes_first(clock):
    source = FakeSource(["a"])
    run(source, clock)  # "a" is due 24 hours after NOW
    clock.advance(hours=2)
    source.listed = ["b", "a"]
    run(source, clock)  # "b" is new, due 24 hours after NOW + 2 hours
    clock.advance(hours=23)  # now both are due, "a" for longer
    source.listed = []
    source.fetched.clear()
    run(source, clock, budget=1)
    assert source.fetched == ["a"]


# ---------- the budget ----------


def test_a_run_never_loads_more_games_than_the_budget(clock):
    source = FakeSource([f"g{i}" for i in range(30)])
    run(source, clock, budget=10)
    assert game_count() == 10
    assert runs()[-1].games_found == 10

    clock.advance(hours=1)
    run(source, clock, budget=10)  # the next ten of the list
    assert game_count() == 20


def test_new_games_come_first_and_revisits_take_what_is_left(clock):
    source = FakeSource(["old1", "old2", "old3", "old4"])
    run(source, clock)  # four known games
    clock.advance(hours=25)  # all four are due

    source.listed = ["new1", "new2", "new3"]  # fewer new games than places
    source.fetched.clear()
    run(source, clock, budget=5)
    assert source.fetched[:3] == ["new1", "new2", "new3"]
    assert len(source.fetched) == 5  # the two free places go to the revisits
    assert all(ref.startswith("old") for ref in source.fetched[3:])


def test_a_flood_of_new_games_uses_the_whole_budget(clock):
    source = FakeSource(["old1"])
    run(source, clock)
    clock.advance(hours=25)  # "old1" is due

    source.listed = [f"new{i}" for i in range(30)]
    source.fetched.clear()
    run(source, clock, budget=8)
    assert source.fetched == [f"new{i}" for i in range(8)]  # the revisit waits for the next run


# ---------- one run at a time ----------


def test_second_crawl_cannot_start_while_one_is_running():
    started, release = threading.Event(), threading.Event()

    class SlowSource(FakeSource):
        def discover(self, limit):
            started.set()
            release.wait(5)
            return []

    worker = threading.Thread(target=crawl.run_crawl, args=(SlowSource(), "schedule"))
    worker.start()
    assert started.wait(5)
    try:
        assert is_running("crawl")
        with pytest.raises(PipelineRunning):
            crawl.run_crawl(FakeSource(), "manual")
    finally:
        release.set()
        worker.join()
    assert not is_running("crawl")
