from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.db import repository, video_repository
from app.db import session as db_session
from app.db.session import init_db, make_engine, session_scope
from app.main import create_app
from app.services import videos
from app.sources.base import Game
from app.videos.finder import VideoResult

NOW = datetime(2026, 11, 9, 12, 0)


class FakeSource:
    name = "fake"

    def discover(self, limit):
        return []


class FakeYouTube:
    def search_videos(self, query, published_after=None, limit=15):
        return []

    def get_videos(self, ids):
        return []


@pytest.fixture
def client(tmp_path, monkeypatch):
    engine = make_engine(str(tmp_path / "api_videos.db"))
    init_db(engine)
    monkeypatch.setattr(db_session, "SessionLocal", sessionmaker(engine, expire_on_commit=False))
    monkeypatch.setattr(videos, "_quota_exhausted_until", None)
    monkeypatch.setattr(settings, "youtube_api_key", "")
    with session_scope() as session:
        repository.save_game(session, "metacritic", Game(slug="doom", url="u", title="Doom"), NOW)
    with TestClient(create_app(FakeSource(), scheduler_enabled=False)) as c:
        yield c


def save(kind: str, result: VideoResult | None) -> None:
    with session_scope() as session:
        video_repository.save_video(session, 1, kind, result, NOW, None)


def test_a_game_without_videos_has_an_empty_list(client):
    assert client.get("/api/games/1").json()["videos"] == []


def test_the_card_lists_the_videos_letsplay_first(client):
    save("review", VideoResult("rev1", "Doom Review", "Critic Chan", 2_500))
    save("letsplay", VideoResult("lp1", "Doom Let's Play", "Ann", 1_200_000))

    found = client.get("/api/games/1").json()["videos"]
    assert [(v["kind"], v["video_id"], v["title"], v["channel"], v["views"]) for v in found] == [
        ("letsplay", "lp1", "Doom Let's Play", "Ann", 1_200_000),
        ("review", "rev1", "Doom Review", "Critic Chan", 2_500),
    ]
    assert found[0]["url"] == "https://www.youtube.com/watch?v=lp1"
    assert found[0]["playlist_url"] is None


def test_a_multi_part_lets_play_has_a_playlist_link(client):
    save("letsplay", VideoResult("p1", "Doom Let's Play - Part 1", "Ann", 100, playlist_id="PL42"))
    [video] = client.get("/api/games/1").json()["videos"]
    assert video["video_id"] == "p1"
    assert video["playlist_url"] == "https://www.youtube.com/playlist?list=PL42"
    assert video["url"] == "https://www.youtube.com/watch?v=p1&list=PL42"


def test_a_kind_that_was_searched_but_not_found_is_not_listed(client):
    save("letsplay", None)
    save("review", VideoResult("rev1", "Doom Review", "Chan", 1))
    assert [v["kind"] for v in client.get("/api/games/1").json()["videos"]] == ["review"]


def test_the_status_shows_the_video_pipeline_and_that_it_is_off_without_a_key(client):
    status = client.get("/api/sync/status").json()["videos"]
    assert status["enabled"] is False
    assert status["running"] is False
    assert status["budget"] == settings.videos_budget
    assert status["interval_hours"] == settings.videos_interval_hours


def test_the_video_search_cannot_be_started_without_a_key(client):
    assert client.post("/api/sync/run?pipeline=videos").status_code == 400


def test_a_manual_video_run_is_accepted_and_logged(client, monkeypatch):
    monkeypatch.setattr(settings, "youtube_api_key", "key")
    monkeypatch.setattr(videos, "make_youtube_client", lambda: FakeYouTube())

    assert client.get("/api/sync/status").json()["videos"]["enabled"] is True
    assert client.post("/api/sync/run?pipeline=videos").status_code == 202

    [run] = client.get("/api/sync/runs?pipeline=videos").json()
    assert (run["pipeline"], run["trigger"], run["status"]) == ("videos", "manual", "success")
    assert run["games_processed"] == 1
    assert client.get("/api/sync/runs?pipeline=crawl").json() == []


def test_the_video_search_cannot_be_started_twice(client, monkeypatch):
    monkeypatch.setattr(settings, "youtube_api_key", "key")
    with videos.exclusive("videos"):
        assert client.post("/api/sync/run?pipeline=videos").status_code == 409
