"""The transcripts of the videos: subtitles, speech recognition, playlists, the API."""

from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.db import repository, transcript_repository, video_repository
from app.db import session as db_session
from app.db.session import init_db, make_engine, session_scope
from app.main import create_app
from app.services import transcripts as service
from app.sources.base import Game
from app.transcripts.captions import CaptionsUnavailable, Segment
from app.transcripts.stt import SttError, SttResult
from app.videos.finder import VideoResult
from app.videos.youtube import YouTubeError

NOW = datetime(2026, 11, 9, 12, 0)


class FakeSource:
    name = "fake"

    def discover(self, limit):
        return []


class FakeCaptions:
    """Subtitles for the videos in `have`; the others have none."""

    def __init__(self, have: set[str]) -> None:
        self.have = have
        self.asked: list[str] = []

    def __call__(self, video_id):
        self.asked.append(video_id)
        if video_id not in self.have:
            raise CaptionsUnavailable("TranscriptsDisabled")
        return [Segment(0.0, f"hello from {video_id}"), Segment(7.5, "second phrase")], "en"


class FakeStt:
    def __init__(self, minutes: dict[str, int] | None = None, fail: set[str] = frozenset()) -> None:
        self.minutes = minutes or {}
        self.fail = fail
        self.done: list[str] = []

    def probe(self, video_id):
        return self.minutes.get(video_id, 10) * 60

    def transcribe(self, video_id):
        if video_id in self.fail:
            raise SttError("OpenRouter: HTTP 500")
        self.done.append(video_id)
        return SttResult([Segment(1.0, f"spoken {video_id}", "0")], "en")


class FakeYouTube:
    def __init__(self, ids: list[str]) -> None:
        self.ids = ids

    def playlist_videos(self, playlist_id, limit):
        return [(i, f"Part {n}") for n, i in enumerate(self.ids, 1)][:limit]


@pytest.fixture
def client(tmp_path, monkeypatch):
    engine = make_engine(str(tmp_path / "transcripts.db"))
    init_db(engine)
    monkeypatch.setattr(db_session, "SessionLocal", sessionmaker(engine, expire_on_commit=False))
    monkeypatch.setattr(settings, "openrouter_api_key", "")
    service._running.clear()
    with session_scope() as session:
        repository.save_game(session, "metacritic", Game(slug="doom", url="u", title="Doom"), NOW)
    with TestClient(create_app(FakeSource(), scheduler_enabled=False)) as c:
        yield c


def save_video(kind="letsplay", video_id="v1", playlist_id=None):
    with session_scope() as session:
        video_repository.save_video(
            session, 1, kind, VideoResult(video_id, "Doom Let's Play", "Ann", 10, playlist_id=playlist_id), NOW, None
        )


def run(captions, stt=None, youtube=None, kind="letsplay"):
    service.begin(1, kind)
    service.run_transcripts(1, kind, captions, stt or None, youtube)


def states(kind="letsplay"):
    with session_scope() as session:
        return {r.video_id: (r.status, r.source) for r in transcript_repository.list_transcripts(session, 1, kind)}


# ------------------------------------------------------------------ the service
def test_subtitles_are_taken_first(client):
    save_video()
    stt = FakeStt()
    run(FakeCaptions({"v1"}), stt)
    assert states() == {"v1": ("done", "captions")}
    assert stt.done == []
    with session_scope() as session:
        row = transcript_repository.get_transcript(session, 1, "v1")
        assert row.segments[0] == {"start": 0.0, "text": "hello from v1", "speaker": None}
        assert row.language == "en"


def test_without_subtitles_the_speech_is_recognised(client):
    save_video()
    run(FakeCaptions(set()), FakeStt())
    assert states() == {"v1": ("done", "stt")}
    with session_scope() as session:
        row = transcript_repository.get_transcript(session, 1, "v1")
        assert row.segments == [{"start": 1.0, "text": "spoken v1", "speaker": "0"}]
        assert row.duration_seconds == 600


def test_without_subtitles_and_a_key_the_video_fails_with_a_reason(client):
    save_video()
    run(FakeCaptions(set()))
    assert states() == {"v1": ("failed", None)}
    with session_scope() as session:
        assert "OPENROUTER_API_KEY" in transcript_repository.get_transcript(session, 1, "v1").error


def test_a_long_video_is_not_recognised(client, monkeypatch):
    monkeypatch.setattr(settings, "stt_max_video_minutes", 60)
    save_video()
    stt = FakeStt({"v1": 360})
    run(FakeCaptions(set()), stt)
    assert states() == {"v1": ("failed", None)}
    assert stt.done == []
    with session_scope() as session:
        assert "too long" in transcript_repository.get_transcript(session, 1, "v1").error


def test_a_recognition_error_is_kept(client):
    save_video()
    run(FakeCaptions(set()), FakeStt(fail={"v1"}))
    with session_scope() as session:
        assert "HTTP 500" in transcript_repository.get_transcript(session, 1, "v1").error


def test_every_video_of_a_playlist_is_done(client):
    save_video(video_id="a", playlist_id="PL1")
    run(FakeCaptions({"a", "b", "c"}), youtube=FakeYouTube(["a", "b", "c"]))
    assert states() == {i: ("done", "captions") for i in "abc"}
    with session_scope() as session:
        assert [r.position for r in transcript_repository.list_transcripts(session, 1, "letsplay")] == [0, 1, 2]


def test_a_second_request_does_only_the_videos_not_done(client):
    save_video(video_id="a", playlist_id="PL1")
    first = FakeCaptions({"a", "c"})
    run(first, youtube=FakeYouTube(["a", "b", "c"]))
    assert states() == {"a": ("done", "captions"), "b": ("failed", None), "c": ("done", "captions")}

    second = FakeCaptions({"a", "b", "c"})
    run(second, youtube=FakeYouTube(["a", "b", "c"]))
    assert second.asked == ["b"]  # the done ones are left alone
    assert states() == {i: ("done", "captions") for i in "abc"}


def test_a_playlist_that_grew_gets_its_new_videos(client):
    save_video(video_id="a", playlist_id="PL1")
    run(FakeCaptions({"a", "b"}), youtube=FakeYouTube(["a"]))
    run(FakeCaptions({"a", "b"}), youtube=FakeYouTube(["a", "b"]))
    assert states() == {"a": ("done", "captions"), "b": ("done", "captions")}


def test_the_budget_of_a_request_leaves_the_rest_for_the_next_one(client, monkeypatch):
    monkeypatch.setattr(settings, "stt_budget_minutes", 50)
    save_video(video_id="a", playlist_id="PL1")
    stt = FakeStt({"a": 30, "b": 30, "c": 10})
    run(FakeCaptions(set()), stt, FakeYouTube(["a", "b", "c"]))
    # a takes 30 of 50, b would not fit and waits, c fits
    assert states() == {"a": ("done", "stt"), "b": ("pending", None), "c": ("done", "stt")}
    run(FakeCaptions(set()), stt, FakeYouTube(["a", "b", "c"]))
    assert states()["b"] == ("done", "stt")


def test_a_broken_playlist_falls_back_to_the_shown_video(client):
    class Broken:
        def playlist_videos(self, playlist_id, limit):
            raise YouTubeError("boom")

    save_video(video_id="a", playlist_id="PL1")
    run(FakeCaptions({"a"}), youtube=Broken())
    assert states() == {"a": ("done", "captions")}


def test_the_place_of_a_task_is_taken_once(client):
    service.begin(1, "letsplay")
    with pytest.raises(service.AlreadyRunning):
        service.begin(1, "letsplay")
    service.begin(1, "review")  # another kind has its own place


def test_a_restart_cuts_short_what_was_running(client):
    save_video()
    with session_scope() as session:
        transcript_repository.sync_videos(session, 1, "letsplay", [("v1", "t")], NOW)
        row = transcript_repository.get_transcript(session, 1, "v1")
        transcript_repository.set_status(session, row.id, "running", NOW)
    with session_scope() as session:
        assert transcript_repository.interrupt_running(session, NOW) == 1
    assert states() == {"v1": ("failed", None)}


# ------------------------------------------------------------------ the API
def test_the_state_of_a_game_without_transcripts_is_empty(client):
    body = client.get("/api/games/1/transcripts/letsplay").json()
    assert body == {"kind": "letsplay", "running": False, "stt_enabled": False, "videos": [], "segments": None}


def test_a_request_without_a_video_is_refused(client):
    assert client.post("/api/games/1/transcripts/letsplay").status_code == 404
    assert client.post("/api/games/1/transcripts/other").status_code == 422


def test_a_request_builds_the_transcript(client, monkeypatch):
    save_video()
    monkeypatch.setattr(service, "fetch_captions", FakeCaptions({"v1"}))
    assert client.post("/api/games/1/transcripts/letsplay").status_code == 202

    body = client.get("/api/games/1/transcripts/letsplay?video_id=v1").json()
    assert body["running"] is False
    assert [(v["video_id"], v["status"], v["source"]) for v in body["videos"]] == [("v1", "done", "captions")]
    assert body["segments"] == [
        {"start": 0.0, "text": "hello from v1", "speaker": None},
        {"start": 7.5, "text": "second phrase", "speaker": None},
    ]


def test_the_text_is_given_only_for_the_asked_video(client, monkeypatch):
    save_video()
    monkeypatch.setattr(service, "fetch_captions", FakeCaptions({"v1"}))
    client.post("/api/games/1/transcripts/letsplay")
    assert client.get("/api/games/1/transcripts/letsplay").json()["segments"] is None
    assert client.get("/api/games/1/transcripts/letsplay?video_id=nope").json()["segments"] is None


def test_a_request_while_the_task_runs_is_refused(client):
    save_video()
    service.begin(1, "letsplay")
    assert client.post("/api/games/1/transcripts/letsplay").status_code == 409
    assert client.get("/api/games/1/transcripts/letsplay").json()["running"] is True
