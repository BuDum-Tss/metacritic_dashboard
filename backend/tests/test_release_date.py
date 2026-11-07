from datetime import date, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from app.db import repository
from app.db import session as db_session
from app.db.models import Game as GameRow
from app.db.session import init_db, make_engine, session_scope
from app.main import create_app
from app.sources.base import Game
from app.sources.metacritic.game_parser import parse_game

FIXTURES = Path(__file__).parent / "fixtures"
NOW = datetime(2026, 11, 7, 12, 0)


def read(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def test_release_date_comes_from_the_game_page():
    assert parse_game(read("phantom-blade-zero.html"), "phantom-blade-zero").release_date == date(2026, 10, 29)
    assert parse_game(read("stellar-blade-complete-edition.html"), "x").release_date == date(2026, 11, 5)


@pytest.mark.parametrize("value", ['"datePublished": "soon"', '"datePublished": ""', '"other": 1'])
def test_a_missing_or_odd_release_date_is_none(value):
    html = f'<script type="application/ld+json">{{"@type":"VideoGame","name":"X",{value}}}</script>'
    assert parse_game(html, "x").release_date is None


@pytest.fixture
def database(tmp_path, monkeypatch):
    engine = make_engine(str(tmp_path / "release.db"))
    init_db(engine)
    monkeypatch.setattr(db_session, "SessionLocal", sessionmaker(engine, expire_on_commit=False))


def make(slug="zelda", release=None) -> Game:
    return Game(slug=slug, url="u", title=slug.title(), release_date=release)


def stored(slug="zelda"):
    with session_scope() as s:
        return s.scalar(select(GameRow.release_date).where(GameRow.slug == slug))


def test_release_date_is_saved_and_corrected_on_a_later_visit(database):
    with session_scope() as s:
        repository.save_game(s, "fake", make(release=date(2026, 11, 5)), NOW)
    assert stored() == date(2026, 11, 5)

    with session_scope() as s:
        repository.save_game(s, "fake", make(release=date(2026, 11, 6)), NOW)
    assert stored() == date(2026, 11, 6)  # the site moved the release


def test_a_visit_without_the_date_keeps_the_known_one(database):
    with session_scope() as s:
        repository.save_game(s, "fake", make(release=date(2026, 11, 5)), NOW)
        repository.save_game(s, "fake", make(release=None), NOW)
    assert stored() == date(2026, 11, 5)


@pytest.fixture
def client(database):
    today = datetime.now().date()
    with session_scope() as s:
        repository.save_game(s, "fake", make("old", today - timedelta(days=30)), NOW)
        repository.save_game(s, "fake", make("fresh", today - timedelta(days=1)), NOW)
        repository.save_game(s, "fake", make("undated", None), NOW)
        repository.save_game(s, "fake", make("upcoming", today + timedelta(days=60)), NOW)
    with TestClient(create_app(scheduler_enabled=False)) as c:
        yield c


def titles(response) -> list[str]:
    return [item["title"] for item in response.json()["items"]]


def test_sort_by_release_puts_the_newest_first_and_unknown_dates_last(client):
    result = titles(client.get("/api/games?sort=release&order=desc"))
    assert result[:2] == ["Fresh", "Old"]
    assert set(result[2:]) == {"Undated", "Upcoming"}  # no date or still to come: last


def test_sort_by_release_ascending_keeps_unknown_dates_last(client):
    result = titles(client.get("/api/games?sort=release&order=asc"))
    assert result[:2] == ["Old", "Fresh"]
    assert set(result[2:]) == {"Undated", "Upcoming"}


def test_game_card_carries_the_release_date(client):
    game_id = client.get("/api/games?q=Fresh").json()["items"][0]["id"]
    expected = (datetime.now().date() - timedelta(days=1)).isoformat()
    assert client.get(f"/api/games/{game_id}").json()["release_date"] == expected
    undated = client.get("/api/games?q=Undated").json()["items"][0]["id"]
    assert client.get(f"/api/games/{undated}").json()["release_date"] is None
