from datetime import date, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from app.db import dashboard, repository
from app.db import review_repository as reviews
from app.db import session as db_session
from app.db.session import init_db, make_engine, session_scope
from app.main import create_app
from app.sources.base import Game, PlatformScore, Review

NOW = datetime(2026, 11, 7, 12, 0)


def add(session, slug, genres, platforms, release=None, seen=NOW) -> int:
    """platforms: (slug, metascore, userscore, critic reviews, user ratings)"""
    game = Game(
        slug=slug,
        url=f"https://example.com/{slug}/",
        title=slug.title(),
        genres=genres,
        release_date=release,
        platforms=[
            PlatformScore(slug=s, name=s.upper(), metascore=m, userscore=u, critic_reviews_count=c, user_reviews_count=n)
            for s, m, u, c, n in platforms
        ],
    )
    return repository.save_game(session, "fake", game, seen).game_id


def summarize(session, game_id, kind, dislike):
    sample = [Review(kind=kind, text=f"{kind} {i}", score=5, author=str(i)) for i in range(3)]
    reviews.save_summary(
        session, game_id, kind, sample, 100, "stub", "hash",
        likes=[("Nice", [1])], dislikes=[(dislike, [2])], now=NOW,
    )


@pytest.fixture
def database(tmp_path, monkeypatch):
    engine = make_engine(str(tmp_path / "dash.db"))
    init_db(engine)
    monkeypatch.setattr(db_session, "SessionLocal", sessionmaker(engine, expire_on_commit=False))


@pytest.fixture
def market(database):
    """A small market with known numbers (today is 2026-11-07)."""
    with session_scope() as s:
        ids = {
            # two platforms: Metascore (90 + 88) / 2 = 89, Userscore (9.0 + 8.6) / 2 = 8.8, 800 ratings
            "hit": add(s, "hit", ["Action", "RPG"], [("pc", 90, 9.0, 40, 500), ("ps5", 88, 8.6, 30, 300)], date(2026, 11, 6)),
            "good": add(s, "good", ["Action"], [("pc", 80, 8.0, 20, 100)], date(2026, 11, 6), NOW - timedelta(days=2)),
            "critics_love": add(s, "critics_love", ["Action"], [("pc", 90, 4.0, 30, 200)], date(2026, 11, 5)),
            "players_love": add(s, "players_love", ["RPG"], [("pc", 55, 9.0, 10, 400)], date(2026, 11, 5)),
            "meh": add(s, "meh", ["Action"], [("pc", 51, 5.0, 5, 50)], date(2026, 11, 1)),
            "few_ratings": add(s, "few_ratings", ["RPG"], [("pc", 95, 3.0, 5, 5)], date(2026, 10, 20)),
            "no_scores": add(s, "no_scores", [], [("pc", None, None, None, None)], None, NOW - timedelta(days=10)),
            "upcoming": add(s, "upcoming", [], [("pc", 70, 7.0, 5, 20)], date(2026, 12, 25)),
        }
        summarize(s, ids["critics_love"], "users", "Too grindy")
        summarize(s, ids["players_love"], "critics", "Slow story")
    return ids


def build() -> dict:
    with session_scope() as s:
        return dashboard.build(s, NOW)


def test_tiles(market):
    tiles = build()["tiles"]
    assert tiles["games_total"] == 8
    assert tiles["new_7d"] == 7  # all but the one seen ten days ago
    # of the 7 games with both scores only "hit" and "good" are hits (critics >= 75 and players >= 7.5)
    assert tiles["hits_share"] == 29
    # |critics - players x 10|: 1, 0, 50, 35, 1, 65, 0
    assert tiles["avg_gap"] == pytest.approx(21.7)


def test_success_map_has_games_with_attention_and_a_median(market):
    result = build()["map"]
    points = {p["title"]: p for p in result["points"]}
    assert "No_Scores" not in points and len(points) == 7  # no ratings, no point
    assert points["Hit"] == {"id": market["hit"], "title": "Hit", "critics": 89, "users": 8.8, "attention": 800}
    assert result["attention_median"] == 100  # of 5, 20, 50, 100, 200, 400, 800


def test_genres_need_three_games_and_carry_averages(market):
    genres = {g["genre"]: g for g in build()["genres"]}
    assert set(genres) == {"Action", "RPG"}  # both have exactly 3 or more games
    action = genres["Action"]  # hit, good, critics_love, meh
    assert action["games"] == 4
    assert action["avg_critics"] == pytest.approx(77.5, abs=0.05)
    assert action["avg_attention"] == 288  # (800 + 100 + 200 + 50) / 4 = 287.5, half up
    assert genres["RPG"]["games"] == 3
    assert [g["genre"] for g in build()["genres"]] == ["Action", "RPG"]  # the most games first


def test_a_genre_with_two_games_is_left_out(database):
    with session_scope() as s:
        add(s, "a", ["Rare"], [("pc", 80, 8.0, 1, 10)])
        add(s, "b", ["Rare"], [("pc", 70, 7.0, 1, 10)])
    assert build()["genres"] == []


def test_divergences_name_who_is_unhappy_and_why(market):
    result = build()["divergences"]
    loved_by_critics = result["critics_love"]
    assert loved_by_critics[0]["title"] == "Critics_Love"
    assert (loved_by_critics[0]["critics"], loved_by_critics[0]["users"], loved_by_critics[0]["gap"]) == (90, 4.0, 50.0)
    assert loved_by_critics[0]["reason"] == {"source": "users", "text": "Too grindy"}
    assert all(item["gap"] > 0 for item in loved_by_critics)

    [loved_by_players] = result["players_love"]
    assert loved_by_players["title"] == "Players_Love"
    assert loved_by_players["gap"] == -35.0
    assert loved_by_players["reason"] == {"source": "critics", "text": "Slow story"}


def test_divergences_skip_games_with_few_ratings_and_have_no_reason_without_a_summary(market):
    result = build()["divergences"]
    titles = [item["title"] for item in result["critics_love"] + result["players_love"]]
    assert "Few_Ratings" not in titles  # a gap of 65 on five ratings says nothing
    hit = next(item for item in result["critics_love"] if item["title"] == "Hit")
    assert hit["reason"] is None


def test_rhythm_counts_releases_by_day_with_moving_averages(market):
    rhythm = build()["rhythm"]
    days = {d["date"]: d for d in rhythm["days"]}
    assert len(rhythm["days"]) == 30
    assert rhythm["days"][0]["date"] == date(2026, 10, 9) and rhythm["days"][-1]["date"] == date(2026, 11, 7)

    assert (days[date(2026, 11, 6)]["games"], days[date(2026, 11, 6)]["avg_critics"]) == (2, 84.5)  # 89 and 80
    assert (days[date(2026, 11, 5)]["games"], days[date(2026, 11, 5)]["avg_critics"]) == (2, 72.5)  # 90 and 55
    assert days[date(2026, 11, 7)]["games"] == 0 and days[date(2026, 11, 7)]["avg_critics"] is None
    # the week 11-01 .. 11-07 has 5 releases with Metascores 89, 80, 90, 55, 51
    assert days[date(2026, 11, 7)]["games_avg7"] == 0.7
    assert days[date(2026, 11, 7)]["critics_avg7"] == 73.0
    assert days[date(2026, 11, 1)]["games_avg7"] == 0.1  # only "meh" in 10-26 .. 11-01


def test_rhythm_ignores_future_and_unknown_dates_and_reports_coverage(market):
    rhythm = build()["rhythm"]
    assert sum(d["games"] for d in rhythm["days"]) == 6  # not the upcoming game, not the one without a date
    assert rhythm["coverage"] == {"with_date": 7, "total": 8}


def test_an_empty_market_gives_empty_blocks(database):
    result = build()
    assert result["tiles"] == {"games_total": 0, "new_7d": 0, "hits_share": None, "avg_gap": None}
    assert result["map"] == {"points": [], "attention_median": None}
    assert result["genres"] == []
    assert result["divergences"] == {"critics_love": [], "players_love": []}
    assert len(result["rhythm"]["days"]) == 30
    assert all(d["games"] == 0 and d["critics_avg7"] is None for d in result["rhythm"]["days"])


def test_dashboard_endpoint_serves_the_blocks(market):
    with TestClient(create_app(scheduler_enabled=False)) as client:
        body = client.get("/api/dashboard").json()
    assert set(body) == {"tiles", "map", "genres", "divergences", "rhythm"}
    assert body["tiles"]["games_total"] == 8
    assert len(body["map"]["points"]) == 7
    assert len(body["rhythm"]["days"]) == 30
