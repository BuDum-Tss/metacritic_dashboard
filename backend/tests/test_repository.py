from dataclasses import replace
from datetime import datetime, timedelta

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import sessionmaker

from app.db import repository
from app.db.models import Game, GamePlatformHistory, Genre
from app.db.session import init_db, make_engine, session_scope
from app.sources.base import Game as SourceGame
from app.sources.base import PlatformScore

T0 = datetime(2026, 11, 6, 10, 0)


@pytest.fixture
def factory(tmp_path):
    engine = make_engine(str(tmp_path / "test.db"))
    init_db(engine)
    return sessionmaker(engine, expire_on_commit=False)


def make_game(**kwargs) -> SourceGame:
    game = SourceGame(
        slug="zelda",
        url="https://www.metacritic.com/game/zelda/",
        title="Zelda",
        description="desc",
        developer="Nintendo",
        genres=["Action", "Adventure"],
        platforms=[PlatformScore(slug="switch-2", name="Nintendo Switch 2", metascore=96, userscore=9.1)],
    )
    return replace(game, **kwargs)


def test_save_new_game(factory):
    with session_scope(factory) as s:
        result = repository.save_game(s, "metacritic", make_game(), T0)
    assert result.created and result.changed
    with session_scope(factory) as s:
        row = s.scalar(select(Game))
        assert row.title == "Zelda"
        assert [g.name for g in row.genres] == ["Action", "Adventure"]
        assert [(p.platform, p.metascore, p.userscore) for p in row.platforms] == [("switch-2", 96, 9.1)]


def test_resave_unchanged_game_only_touches_processing_time_and_adds_history(factory):
    with session_scope(factory) as s:
        repository.save_game(s, "metacritic", make_game(), T0)
    later = T0 + timedelta(hours=1)
    new_scores = [PlatformScore(slug="switch-2", name="Nintendo Switch 2", metascore=97, userscore=9.2)]
    with session_scope(factory) as s:
        result = repository.save_game(s, "metacritic", make_game(platforms=new_scores), later)
    assert not result.created and not result.changed
    with session_scope(factory) as s:
        row = s.scalar(select(Game))
        assert row.updated_at == T0
        assert row.last_processed_at == later
        assert row.platforms[0].metascore == 97
        history = s.scalars(select(GamePlatformHistory).order_by(GamePlatformHistory.captured_at)).all()
        assert [(h.metascore, h.captured_at) for h in history] == [(96, T0), (97, later)]


def test_changed_description_updates_game(factory):
    with session_scope(factory) as s:
        repository.save_game(s, "metacritic", make_game(), T0)
    later = T0 + timedelta(hours=1)
    with session_scope(factory) as s:
        result = repository.save_game(
            s, "metacritic", make_game(description="new", genres=["Action"]), later
        )
    assert result.changed
    with session_scope(factory) as s:
        row = s.scalar(select(Game))
        assert row.description == "new"
        assert row.updated_at == later
        assert [g.name for g in row.genres] == ["Action"]
        assert s.scalar(select(func.count()).select_from(Genre)) == 2  # genres are shared, not deleted


def test_same_slug_in_different_sources_are_different_games(factory):
    with session_scope(factory) as s:
        repository.save_game(s, "metacritic", make_game(), T0)
        repository.save_game(s, "steam", make_game(), T0)
        assert s.scalar(select(func.count()).select_from(Game)) == 2


def test_failed_save_rolls_back(factory):
    with pytest.raises(RuntimeError):
        with session_scope(factory) as s:
            repository.save_game(s, "metacritic", make_game(), T0)
            raise RuntimeError
    with session_scope(factory) as s:
        assert s.scalar(select(func.count()).select_from(Game)) == 0


def test_processed_since(factory):
    with session_scope(factory) as s:
        repository.save_game(s, "metacritic", make_game(slug="old"), T0 - timedelta(days=1))
        repository.save_game(s, "metacritic", make_game(slug="today"), T0)
        assert repository.processed_since(s, "metacritic", T0.replace(hour=0)) == {"today"}


def test_sync_runs_count_only_successful_of_the_day(factory):
    day = T0.replace(hour=0)
    with session_scope(factory) as s:
        ok = repository.start_run(s, "metacritic", "schedule", 0, T0)
        repository.finish_run(s, ok, "success", T0, found=20, processed=20)
        bad = repository.start_run(s, "metacritic", "manual", 1, T0)
        repository.finish_run(s, bad, "failed", T0, error="boom")
        yesterday = repository.start_run(s, "metacritic", "schedule", 0, T0 - timedelta(days=1))
        repository.finish_run(s, yesterday, "success", T0 - timedelta(days=1))
        assert repository.count_successful_runs(s, "metacritic", day) == 1
