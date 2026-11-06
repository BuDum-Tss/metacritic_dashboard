from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from app.db import repository
from app.db import session as db_session
from app.db.queries import similarity
from app.db.session import init_db, make_engine, session_scope
from app.main import create_app
from app.sources.base import Game, PlatformScore

NOW = datetime(2026, 11, 6, 10, 0)


def game(slug, title, genres, platforms, **kwargs) -> Game:
    return Game(
        slug=slug,
        url=f"https://example.com/{slug}/",
        title=title,
        genres=genres,
        platforms=[PlatformScore(slug=s, name=s.upper(), metascore=m, userscore=u) for s, m, u in platforms],
        **kwargs,
    )


GAMES = [
    game("zelda", "Zelda", ["Action", "Adventure"], [("switch", 96, 9.0)]),
    game("mario", "Super Mario", ["Platformer", "Adventure"], [("switch", 90, 8.0), ("pc", 85, None)]),
    game("doom", "Doom 100%", ["Shooter", "Action"], [("pc", 88, 8.5), ("ps5", 91, 7.0)]),
    game("tbd", "No Scores Game", ["Action"], [("pc", None, None)]),
    game("quake", "Quake", ["Shooter"], [("pc", 80, 9.5)]),
    game("lonely", "Lonely", [], [("pc", 70, 6.0)]),
]


@pytest.fixture
def client(tmp_path, monkeypatch):
    engine = make_engine(str(tmp_path / "games.db"))
    init_db(engine)
    monkeypatch.setattr(db_session, "SessionLocal", sessionmaker(engine, expire_on_commit=False))
    with session_scope() as s:
        for g in GAMES:
            repository.save_game(s, "fake", g, NOW)
    with TestClient(create_app(scheduler_enabled=False)) as c:
        yield c


def titles(response) -> list[str]:
    return [item["title"] for item in response.json()["items"]]


def test_default_sort_is_metascore_desc_with_unrated_last(client):
    r = client.get("/api/games")
    assert r.json()["total"] == 6
    assert titles(r) == ["Zelda", "Doom 100%", "Super Mario", "Quake", "Lonely", "No Scores Game"]


def test_sort_by_userscore_ascending_keeps_unrated_last(client):
    r = client.get("/api/games?sort=userscore&order=asc")
    # the best userscore over platforms counts: Doom is 8.5, not 7.0
    assert titles(r) == ["Lonely", "Super Mario", "Doom 100%", "Zelda", "Quake", "No Scores Game"]


def test_platform_filter_sorts_by_that_platforms_score(client):
    r = client.get("/api/games?platform=pc")
    assert titles(r) == ["Doom 100%", "Super Mario", "Quake", "Lonely", "No Scores Game"]
    r = client.get("/api/games?platform=ps5")
    assert titles(r) == ["Doom 100%"]


def test_search_by_title_is_case_insensitive_and_escapes_wildcards(client):
    assert titles(client.get("/api/games?q=mar")) == ["Super Mario"]
    assert titles(client.get("/api/games?q=100%25")) == ["Doom 100%"]
    assert titles(client.get("/api/games?q=%25")) == ["Doom 100%"]
    assert client.get("/api/games?q=nothing").json()["total"] == 0


def test_pagination(client):
    r = client.get("/api/games?page=2&page_size=4").json()
    assert (r["total"], r["page"], r["page_size"], len(r["items"])) == (6, 2, 4, 2)


def test_list_item_has_short_info(client):
    item = client.get("/api/games?q=mar").json()["items"][0]
    assert item["genres"] == ["Adventure", "Platformer"]
    assert [(p["platform"], p["metascore"], p["userscore"]) for p in item["platforms"]] == [
        ("pc", 85, None),
        ("switch", 90, 8.0),
    ]


def test_platforms_for_filter(client):
    options = client.get("/api/games/platforms").json()
    assert options[0] == {"platform": "pc", "name": "PC", "games": 5}
    assert {o["platform"] for o in options} == {"pc", "switch", "ps5"}


def test_game_detail_with_similar_games(client):
    zelda_id = client.get("/api/games?q=zelda").json()["items"][0]["id"]
    detail = client.get(f"/api/games/{zelda_id}").json()
    assert detail["title"] == "Zelda"
    assert detail["url"] == "https://example.com/zelda/"
    assert detail["updated_at"].endswith(("Z", "+00:00"))
    # Jaccard on genres: the unrated game (only Action) 0.5; Mario 1/3 + shared platform bonus; Doom 1/3
    assert [g["title"] for g in detail["similar"]] == ["No Scores Game", "Super Mario", "Doom 100%"]


def test_game_without_genres_has_no_similar(client):
    lonely_id = client.get("/api/games?q=lonely").json()["items"][0]["id"]
    assert client.get(f"/api/games/{lonely_id}").json()["similar"] == []


def test_unknown_game_is_404(client):
    assert client.get("/api/games/9999").status_code == 404


def test_invalid_sort_is_rejected(client):
    assert client.get("/api/games?sort=nonsense").status_code == 422


def test_similarity_math():
    assert similarity({1, 2}, {1, 2}, set(), set()) == 1.0
    assert similarity({1, 2}, {2, 3}, {"pc"}, {"pc"}) == pytest.approx(1 / 3 + 0.05)
    assert similarity({1}, {2}, {"pc"}, {"pc"}) == 0.0  # no common genre: platforms alone do not count
    assert similarity(set(), {1}, set(), set()) == 0.0
