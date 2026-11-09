"""Migration 0013: the transcripts stored before the subtitles were joined get their sentences."""

import importlib.util
from datetime import datetime
from pathlib import Path

from app.db import repository, transcript_repository
from app.db.session import init_db, make_engine, session_scope
from app.sources.base import Game
from app.transcripts.captions import Segment
from sqlalchemy.orm import sessionmaker

MIGRATION = Path(__file__).parents[1] / "app/db/migrations/versions/0013_merge_caption_sentences.py"
NOW = datetime(2026, 11, 9, 12, 0)


def load():
    spec = importlib.util.spec_from_file_location("migration_0013", MIGRATION)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_stored_subtitles_become_sentences_and_other_transcripts_stay(tmp_path):
    engine = make_engine(str(tmp_path / "m.db"))
    init_db(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    with session_scope(factory) as session:
        repository.save_game(session, "metacritic", Game(slug="z", url="u", title="Zelda"), NOW)
        transcript_repository.sync_videos(session, 1, "review", [("cap", "t"), ("stt", "t")], NOW)
        lines = [Segment(0, "So here we are"), Segment(2, "in the temple."), Segment(5, ">> Nice")]
        for video, source in (("cap", "captions"), ("stt", "stt")):
            row = transcript_repository.get_transcript(session, 1, video)
            transcript_repository.save_done(session, row.id, source, "en", lines, 6, NOW)

    with engine.begin() as connection:
        assert load().merge_stored(connection) == 1
        assert load().merge_stored(connection) == 0  # a second run changes nothing

    with session_scope(factory) as session:
        merged = transcript_repository.get_transcript(session, 1, "cap").segments
        assert [(s["start"], s["text"]) for s in merged] == [(0, "So here we are in the temple."), (5, "Nice")]
        assert len(transcript_repository.get_transcript(session, 1, "stt").segments) == 3
