"""The conclusion about a video: the windows, the bright moments, the links, the job and the API."""

import json
from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.db import repository, transcript_repository, video_summary_repository
from app.db import session as db_session
from app.db.session import init_db, make_engine, session_scope
from app.llm import LLMError
from app.main import create_app
from app.services import video_summary as service
from app.services.video_summary import (
    Moment,
    VideoSummaryError,
    check_links,
    make_windows,
    parse_moments,
    select_moments,
)
from app.sources.base import Game
from app.transcripts.captions import Segment

NOW = datetime(2026, 11, 9, 12, 0)


class FakeSource:
    name = "fake"

    def discover(self, limit):
        return []


class FakeLLM:
    model = "fake-model"

    def __init__(self, moments=None, conclusion="Trouble [with the camera](t=100) all along.", fail_on=None):
        self.moments = moments if moments is not None else [
            {"t": 100, "type": "problem", "topic": "controls", "note": "Fights the camera", "weight": 2}
        ]
        self.conclusion = conclusion
        self.fail_on = fail_on
        self.calls: list[tuple[str, str]] = []

    def complete(self, system, user):
        self.calls.append((system, user))
        if self.fail_on == len(self.calls):
            raise LLMError("HTTP 500")
        if "bright moments in" in system:
            return "Here you go: " + json.dumps({"moments": self.moments})
        return self.conclusion


@pytest.fixture
def client(tmp_path, monkeypatch):
    engine = make_engine(str(tmp_path / "vs.db"))
    init_db(engine)
    monkeypatch.setattr(db_session, "SessionLocal", sessionmaker(engine, expire_on_commit=False))
    monkeypatch.setattr(settings, "llm_api_key", "")
    service._running.clear()
    with session_scope() as session:
        repository.save_game(session, "metacritic", Game(slug="doom", url="u", title="Doom"), NOW)
        transcript_repository.sync_videos(session, 1, "letsplay", [("v1", "Part 1"), ("v2", "Part 2")], NOW)
        row = transcript_repository.get_transcript(session, 1, "v1")
        lines = [Segment(float(i * 10), f"line {i}") for i in range(30)]
        transcript_repository.save_done(session, row.id, "captions", "en", lines, 300, NOW)
    with TestClient(create_app(FakeSource(), scheduler_enabled=False)) as c:
        yield c


# ------------------------------------------------------------------ the pieces
def test_the_transcript_is_cut_into_windows_by_lines():
    segments = [{"start": i, "text": "x" * 20} for i in range(10)]  # 28 characters a line with the number
    windows = make_windows(segments, 100)
    assert [len(w) for w in windows] == [3, 3, 3, 1]
    assert windows[1][0] == (3, "x" * 20)
    assert make_windows([], 100) == []


def test_a_moment_is_snapped_to_a_real_line_and_checked():
    answer = json.dumps(
        {
            "moments": [
                {"t": 103, "type": "problem", "topic": "controls", "note": "ok", "weight": 9},
                {"t": 500, "type": "problem", "topic": "controls", "note": "far from any line"},
                {"t": 20, "type": "rant", "topic": "controls", "note": "unknown type"},
                {"t": 20, "type": "positive", "topic": "weather", "note": "unknown topic"},
                {"t": 20, "type": "positive", "topic": "story", "note": ""},
                {"t": "bad", "type": "positive", "topic": "story", "note": "no time"},
                "junk",
            ]
        }
    )
    moments = parse_moments(answer, [0, 20, 100, 110], limit=10)
    assert [(m.start, m.type, m.topic, m.weight) for m in moments] == [(100, "problem", "controls", 3), (20, "positive", "other", 1)]


def test_a_bad_answer_is_an_error_and_an_empty_one_is_fine():
    with pytest.raises(VideoSummaryError):
        parse_moments("no json here", [0], 5)
    assert parse_moments('{"moments": []}', [0], 5) == []


def test_close_moments_of_one_kind_are_merged_and_the_rest_cut_by_weight():
    weak, strong = Moment(10, "problem", "controls", "a", 1), Moment(20, "problem", "controls", "b", 3)
    other = Moment(25, "positive", "controls", "c", 1)
    assert [m.note for m in select_moments([weak, strong, other], 10)] == ["b", "c"]

    many = [Moment(i * 100, "positive", "story", str(i), 1 + i % 3) for i in range(9)]
    kept = select_moments(many, 4)
    assert len(kept) == 4 and [m.start for m in kept] == sorted(m.start for m in kept)
    assert sorted(m.weight for m in kept) == [2, 3, 3, 3]  # the three strongest, then the earliest of the rest
    assert 100 in [m.start for m in kept]


def test_links_lead_only_to_moments():
    moments = [Moment(100, "problem", "controls", "a"), Moment(500, "positive", "story", "b")]
    text = "[exact](t=100) and [near](t=520) and [nowhere](t=3000) and [plain] words"
    assert check_links(text, moments) == "[exact](t=100) and [near](t=500) and nowhere and [plain] words"


# ------------------------------------------------------------------ the job
def run(llm, video="v1"):
    service.start(1, video, llm)
    service.run_video_summary(1, video, llm)


def row(video="v1"):
    with session_scope() as session:
        found = video_summary_repository.get_summary(session, 1, video)
        return found.status, found.text, found.moments, found.error, found.model


def test_the_conclusion_is_built_from_the_moments_with_links(client):
    llm = FakeLLM()
    run(llm)
    status, text, moments, error, model = row()
    assert (status, error, model) == ("done", None, "fake-model")
    assert text == "Trouble [with the camera](t=100) all along."
    assert moments == [{"start": 100, "type": "problem", "topic": "controls", "note": "Fights the camera"}]
    assert len(llm.calls) == 2  # one window, then the conclusion
    assert "[100] line 10" in llm.calls[0][1]
    assert "[100] problem/controls: Fights the camera" in llm.calls[1][1]
    assert not service.is_running(1, "v1")


def test_every_window_goes_to_the_model(client, monkeypatch):
    monkeypatch.setattr(settings, "video_summary_chunk_chars", 120)
    llm = FakeLLM(moments=[])
    run(llm)  # no moments anywhere
    assert row()[0] == "failed" and "no bright moments" in row()[3]
    assert len(llm.calls) > 3 and all("bright moments in" in call[0] for call in llm.calls)


def test_a_failed_window_fails_the_job_and_frees_the_place(client):
    run(FakeLLM(fail_on=1))
    assert row()[0] == "failed" and "HTTP 500" in row()[3]
    assert not service.is_running(1, "v1")


def test_a_failed_conclusion_keeps_the_old_text(client):
    run(FakeLLM())
    run(FakeLLM(fail_on=2))
    status, text, *_ = row()
    assert status == "failed" and text == "Trouble [with the camera](t=100) all along."


# ------------------------------------------------------------------ the API
def test_the_state_without_a_summary(client):
    body = client.get("/api/games/1/summaries/v1").json()
    assert body["status"] == "none" and body["text"] is None and body["moments"] == [] and body["llm_enabled"] is False


def test_a_request_without_a_model_is_refused(client):
    assert client.post("/api/games/1/summaries/v1").status_code == 400


def test_a_request_needs_a_finished_transcript(client, monkeypatch):
    monkeypatch.setattr(settings, "llm_api_key", "key")
    assert client.post("/api/games/1/summaries/nope").status_code == 404
    assert client.post("/api/games/1/summaries/v2").status_code == 409  # the transcript is pending


def test_a_request_builds_the_summary(client, monkeypatch):
    monkeypatch.setattr(settings, "llm_api_key", "key")
    llm = FakeLLM()
    monkeypatch.setattr(service, "make_llm_client", lambda: llm)
    assert client.post("/api/games/1/summaries/v1").status_code == 202

    body = client.get("/api/games/1/summaries/v1").json()
    assert body["status"] == "done" and body["running"] is False and body["llm_enabled"] is True
    assert body["text"] == "Trouble [with the camera](t=100) all along."
    assert body["moments"] == [{"start": 100, "type": "problem", "topic": "controls", "note": "Fights the camera"}]
    assert body["model"] == "fake-model" and body["updated_at"].endswith("Z") or "+" in body["updated_at"]


def test_a_second_request_while_it_runs_is_refused(client, monkeypatch):
    monkeypatch.setattr(settings, "llm_api_key", "key")
    monkeypatch.setattr(service, "make_llm_client", lambda: FakeLLM())
    service.start(1, "v1")
    assert client.post("/api/games/1/summaries/v1").status_code == 409
    assert client.get("/api/games/1/summaries/v1").json()["running"] is True


def test_a_restart_cuts_short_a_running_summary(client):
    with session_scope() as session:
        video_summary_repository.mark_running(session, 1, "v1", NOW)
    with session_scope() as session:
        assert video_summary_repository.interrupt_running(session, NOW) == 1
    assert row()[0] == "failed" and row()[3] == "interrupted"


# ------------------------------------------------------------------ many videos at once
def add_transcript(video="v2", done=True):
    with session_scope() as session:
        row = transcript_repository.get_transcript(session, 1, video)
        transcript_repository.save_done(session, row.id, "captions", "en", [Segment(100.0, "line"), Segment(110.0, "more")], 20, NOW)


def statuses():
    with session_scope() as session:
        return video_summary_repository.summaries_of_game(session, 1)


def test_the_summary_is_built_for_every_video_with_a_transcript_and_no_summary(client):
    add_transcript("v2")
    llm = FakeLLM()
    service.build_missing(1, "letsplay", llm)
    assert statuses() == {"v1": "done", "v2": "done"}
    assert len(llm.calls) == 4

    service.build_missing(1, "letsplay", llm)  # nothing left to do
    assert len(llm.calls) == 4


def test_a_failed_summary_is_tried_again_and_a_pending_transcript_is_skipped(client):
    run(FakeLLM(fail_on=1))
    assert statuses() == {"v1": "failed"}
    service.build_missing(1, "letsplay", FakeLLM())
    assert statuses() == {"v1": "done"}  # v2 has no transcript yet: no summary


def test_without_a_model_nothing_is_built(client, monkeypatch):
    monkeypatch.setattr(service, "make_llm_client", lambda: None)
    service.build_missing(1, "letsplay")
    service.run_pending()
    assert statuses() == {}


def test_the_transcripts_request_builds_the_summaries_too(client, monkeypatch):
    from app.services import transcripts as transcripts_service

    with session_scope() as session:
        from app.db import video_repository
        from app.videos.finder import VideoResult

        video_repository.save_video(session, 1, "letsplay", VideoResult("v1", "Part 1", "Ann", 10), NOW, None)
    llm = FakeLLM()
    monkeypatch.setattr(service, "make_llm_client", lambda: llm)
    transcripts_service._running.clear()
    transcripts_service.begin(1, "letsplay")
    transcripts_service.run_transcripts(1, "letsplay", lambda video_id: ([Segment(100.0, "hi")], "en"), None, None)
    assert statuses() == {"v1": "done", "v2": "done"}  # the transcript of v2 was made by the same request


def test_queued_summaries_are_built_after_a_start(client):
    with session_scope() as session:
        video_summary_repository.mark_running(session, 1, "v1", NOW)
        row = video_summary_repository.get_summary(session, 1, "v1")
        row.status = "pending"
    service.run_pending(FakeLLM())
    assert statuses() == {"v1": "done"}


def test_the_state_of_the_videos_tells_the_summary_status(client, monkeypatch):
    monkeypatch.setattr(settings, "llm_api_key", "key")
    run(FakeLLM())
    from app.db import video_repository
    from app.videos.finder import VideoResult

    with session_scope() as session:
        video_repository.save_video(session, 1, "letsplay", VideoResult("v1", "Part 1", "Ann", 10), NOW, None)
    body = client.get("/api/games/1/transcripts/letsplay").json()
    assert body["llm_enabled"] is True
    assert {v["video_id"]: v["summary_status"] for v in body["videos"]} == {"v1": "done", "v2": "none"}


def test_a_queued_summary_without_a_model_shows_as_none(client):
    with session_scope() as session:
        video_summary_repository.mark_running(session, 1, "v1", NOW)
        video_summary_repository.get_summary(session, 1, "v1").status = "pending"
    assert client.get("/api/games/1/summaries/v1").json()["status"] == "none"


# ------------------------------------------------------------------ the migration
def test_the_migration_queues_the_summaries_of_the_finished_transcripts(client):
    import importlib.util
    from pathlib import Path

    path = Path(__file__).parents[1] / "app/db/migrations/versions/0015_queue_summaries_of_transcripts.py"
    spec = importlib.util.spec_from_file_location("migration_0015", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    engine = db_session.SessionLocal.kw["bind"]
    with engine.begin() as connection:
        assert module.queue_missing(connection) == 1  # v1 is finished, v2 is not
        assert module.queue_missing(connection) == 0
    assert statuses() == {"v1": "pending"}
