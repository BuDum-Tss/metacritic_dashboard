from datetime import date, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.db import repository, video_repository
from app.db import session as db_session
from app.db.models import GameVideo, RunGame, SyncRun
from app.db.session import init_db, make_engine, session_scope
from app.services import videos
from app.services.pipelines import PipelineRunning, exclusive
from app.sources.base import Game
from app.videos.youtube import PlaylistInfo, QuotaExceeded, VideoInfo

NOW = datetime(2026, 11, 9, 12, 0)


class FakeApi:
    """A YouTube with one fitting letsplay and one review for every game, except the listed ones."""

    def __init__(self, nothing_for: set[str] = frozenset(), broken_for: set[str] = frozenset(), quota_after: int | None = None):
        self.nothing_for = set(nothing_for)
        self.broken_for = set(broken_for)
        self.quota_after = quota_after  # the number of searches before the quota is used up
        self.searches: list[str] = []

    def search_videos(self, query, published_after=None, limit=15):
        if self.quota_after is not None and len(self.searches) >= self.quota_after:
            raise QuotaExceeded("search: quotaExceeded")
        self.searches.append(query)
        title = query.rsplit(" ", 2 if query.endswith("let's play") else 1)[0]
        if title in self.broken_for:
            raise RuntimeError("YouTube is down")
        return [] if title in self.nothing_for else [f"{title}|{query.split()[-1]}"]

    def get_videos(self, ids):
        videos_ = []
        for id in ids:
            title, kind = id.split("|")
            word = "Review" if kind == "review" else "Let's Play"
            videos_.append(VideoInfo(id, f"{title} {word}", "Chan", "c1", 1000, True))
        return videos_

    def search_playlists(self, query, channel_id, limit=5):
        return []

    def first_playlist_video(self, playlist_id):
        return None


@pytest.fixture(autouse=True)
def database(tmp_path, monkeypatch):
    engine = make_engine(str(tmp_path / "videos.db"))
    init_db(engine)
    monkeypatch.setattr(db_session, "SessionLocal", sessionmaker(engine, expire_on_commit=False))
    monkeypatch.setattr(videos, "_quota_exhausted_until", None)
    monkeypatch.setattr(settings, "youtube_api_key", "key")


def add_game(slug: str, seen: datetime = NOW - timedelta(days=1), release: date | None = date(2026, 11, 1)) -> None:
    game = Game(slug=slug, url=f"https://example.com/{slug}/", title=slug.title(), release_date=release)
    with session_scope() as session:
        repository.save_game(session, "metacritic", game, seen)


def rows() -> dict[tuple[str, str], GameVideo]:
    with session_scope() as session:
        from app.db.models import Game as GameRow

        slugs = dict(session.execute(select(GameRow.id, GameRow.slug)).all())
        return {(slugs[r.game_id], r.kind): r for r in session.scalars(select(GameVideo))}


def run(api, **kwargs) -> int | None:
    return videos.run_videos("schedule", now=kwargs.pop("now", NOW), api=api, **kwargs)


def test_a_run_finds_both_kinds_and_writes_the_journal():
    add_game("doom")
    run_id = run(FakeApi())

    found = rows()
    assert found[("doom", "letsplay")].video_id == "Doom|play"  # the ids come from the fake
    assert found[("doom", "review")].video_id == "Doom|review"
    assert {kind for _, kind in found} == {"letsplay", "review"}
    assert all(row.views == 1000 and row.channel == "Chan" for row in found.values())

    with session_scope() as session:
        run_ = session.get(SyncRun, run_id)
        assert (run_.pipeline, run_.status, run_.games_found, run_.games_processed, run_.games_failed) == (
            "videos", "success", 1, 1, 0
        )
        [game] = list(session.scalars(select(RunGame)))
        assert (game.slug, game.outcome, game.details) == ("doom", "found", {"letsplay": "video", "review": "video"})


def test_the_next_check_depends_on_the_result_and_the_age_of_the_game():
    add_game("young")
    add_game("nothing")
    add_game("old", seen=NOW - timedelta(days=90))
    run(FakeApi(nothing_for={"Nothing"}), budget=10)

    found = rows()
    assert found[("young", "review")].next_check_at == NOW + timedelta(days=settings.videos_refresh_days)
    assert found[("nothing", "review")].video_id is None
    assert found[("nothing", "review")].next_check_at == NOW + timedelta(days=settings.videos_retry_days)
    assert found[("old", "review")].next_check_at is None  # an old game with a video is not searched again


def test_a_game_without_any_video_is_recorded_as_none():
    add_game("quiet")
    run_id = run(FakeApi(nothing_for={"Quiet"}))
    with session_scope() as session:
        [game] = list(session.scalars(select(RunGame).where(RunGame.run_id == run_id)))
    assert (game.outcome, game.details) == ("none", {"letsplay": "none", "review": "none"})


def test_the_newest_games_come_first_and_the_budget_limits_a_run():
    add_game("a", seen=NOW - timedelta(days=3))
    add_game("b", seen=NOW - timedelta(days=1))
    add_game("c", seen=NOW - timedelta(days=2))
    api = FakeApi()
    run(api, budget=2)
    assert {slug for slug, _ in rows()} == {"b", "c"}
    assert len(api.searches) == 4  # two games, two kinds each


def test_games_not_out_yet_are_left_alone_but_a_game_without_a_date_is_not():
    add_game("future", release=NOW.date() + timedelta(days=5))
    add_game("undated", release=None)
    run(FakeApi(), budget=10)
    assert {slug for slug, _ in rows()} == {"undated"}


def test_what_is_found_is_not_searched_again_until_its_check_is_due():
    add_game("doom")
    api = FakeApi()
    run(api)
    searches = len(api.searches)

    run(api, now=NOW + timedelta(days=1))
    assert len(api.searches) == searches  # nothing is due

    run(api, now=NOW + timedelta(days=settings.videos_refresh_days, minutes=1))
    assert len(api.searches) == searches + 2  # both kinds are due


def test_a_failing_game_is_counted_and_the_others_go_on():
    add_game("bad", seen=NOW - timedelta(hours=1))
    add_game("good", seen=NOW - timedelta(days=1))
    run_id = run(FakeApi(broken_for={"Bad"}))
    with session_scope() as session:
        run_ = session.get(SyncRun, run_id)
        outcomes = {g.slug: g.outcome for g in session.scalars(select(RunGame))}
    assert (run_.status, run_.games_processed, run_.games_failed) == ("success", 1, 1)
    assert outcomes == {"bad": "failed", "good": "found"}
    assert ("bad", "letsplay") not in rows()  # no row: the game stays in the queue


def test_the_quota_ends_the_run_and_the_scheduled_runs_wait_for_the_reset():
    add_game("a")
    add_game("b", seen=NOW - timedelta(hours=1))
    run_id = run(FakeApi(quota_after=2))  # the first game is done, the second hits the quota

    with session_scope() as session:
        run_ = session.get(SyncRun, run_id)
    assert run_.status == "success" and "quota" in run_.error
    assert (run_.games_processed, run_.games_failed) == (1, 0)
    assert {slug for slug, _ in rows()} == {"b"}  # the newest game was done first

    api = FakeApi()
    assert run(api, now=NOW) is None  # a scheduled run waits...
    assert api.searches == []
    assert videos.run_videos("manual", now=NOW, api=api) is not None  # ...a manual one tries
    assert run(api, now=NOW.replace(hour=8) + timedelta(days=1)) is not None  # after the reset all is normal


def test_without_a_key_nothing_is_done(monkeypatch):
    monkeypatch.setattr(settings, "youtube_api_key", "")
    add_game("doom")
    assert videos.is_enabled() is False
    assert videos.run_videos("manual", now=NOW) is None
    with session_scope() as session:
        assert session.scalar(select(SyncRun)) is None


def test_a_second_run_cannot_start_while_one_is_running():
    with exclusive("videos"):
        with pytest.raises(PipelineRunning):
            videos.run_videos("manual", now=NOW, api=FakeApi())


def test_next_check_rules():
    assert videos.next_check(True, True, NOW) == NOW + timedelta(days=settings.videos_refresh_days)
    assert videos.next_check(True, False, NOW) is None
    assert videos.next_check(False, True, NOW) == NOW + timedelta(days=settings.videos_retry_days)
    assert videos.next_check(False, False, NOW) == NOW + timedelta(days=30)


def test_queue_orders_never_searched_before_overdue():
    add_game("old_check", seen=NOW - timedelta(days=5))
    add_game("fresh")
    run(FakeApi(), budget=10)
    with session_scope() as session:
        for kind in ("letsplay", "review"):  # make the first game overdue
            video_repository.save_video(session, 1, kind, None, NOW, NOW + timedelta(days=1))
    add_game("brand_new", seen=NOW + timedelta(days=2) - timedelta(days=1))
    with session_scope() as session:
        queue = video_repository.video_queue(session, "metacritic", NOW + timedelta(days=3), 10)
    assert [item.slug for item in queue] == ["brand_new", "old_check"]
