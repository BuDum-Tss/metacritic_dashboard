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
    # the mean over platforms counts: Doom is (8.5 + 7.0) / 2 = 7.75
    assert titles(r) == ["Lonely", "Doom 100%", "Super Mario", "Zelda", "Quake", "No Scores Game"]


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


def test_search_finds_games_by_genre_too(client):
    assert titles(client.get("/api/games?q=shooter")) == ["Doom 100%", "Quake"]
    assert titles(client.get("/api/games?q=SHOOT")) == ["Doom 100%", "Quake"]  # a part of the genre, any case
    assert titles(client.get("/api/games?q=platformer")) == ["Super Mario"]


def test_search_looks_in_the_title_and_the_genres_without_doubling_a_game(client):
    # "action" is a genre of three games; "quake" is a title only; a game matching both ways is listed once
    assert titles(client.get("/api/games?q=action")) == ["Zelda", "Doom 100%", "No Scores Game"]
    assert titles(client.get("/api/games?q=quake")) == ["Quake"]
    assert client.get("/api/games?q=adventure").json()["total"] == 2


def test_search_by_genre_works_together_with_the_platform_filter(client):
    assert titles(client.get("/api/games?q=shooter&platform=ps5")) == ["Doom 100%"]
    assert titles(client.get("/api/games?q=adventure&platform=pc")) == ["Super Mario"]


def test_search_by_genre_escapes_wildcards(client):
    assert client.get("/api/games?q=Sh_oter").json()["total"] == 0
    assert client.get("/api/games?q=%25hooter").json()["total"] == 0


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


def test_game_without_summaries_has_empty_ones(client):
    game_id = client.get("/api/games?q=Zelda").json()["items"][0]["id"]
    assert client.get(f"/api/games/{game_id}").json()["summaries"] == {"critics": None, "users": None}


def test_game_card_carries_summaries_with_the_reviews_behind_each_point(client):
    from app.db import review_repository
    from app.sources.base import Review

    game_id = client.get("/api/games?q=Zelda").json()["items"][0]["id"]
    sample = [
        Review(kind="users", text="Loved the combat", score=10, author="ann", date="Nov 1, 2026", platform="PC"),
        Review(kind="users", text="Great visuals", score=9, author="bob", date="Nov 2, 2026"),
        Review(kind="users", text="Too short", score=4, author="cid", date="Nov 3, 2026"),
    ]
    with session_scope() as s:
        review_repository.save_summary(
            s, game_id, "users", sample, 311, "stub", "hash",
            likes=[("Combat and visuals shine", [1, 2])], dislikes=[("Too short", [3])], now=NOW,
        )

    summaries = client.get(f"/api/games/{game_id}").json()["summaries"]
    assert summaries["critics"] is None
    users = summaries["users"]
    assert (users["sample_size"], users["total_reviews"], users["model"]) == (3, 311, "stub")
    assert users["generated_at"].endswith("Z") or users["generated_at"].endswith("+00:00")

    reviews = {r["id"]: r for r in users["reviews"]}
    [like] = users["likes"]
    [dislike] = users["dislikes"]
    assert like["text"] == "Combat and visuals shine"
    assert sorted(reviews[i]["author"] for i in like["review_ids"]) == ["ann", "bob"]
    assert [reviews[i]["text"] for i in dislike["review_ids"]] == ["Too short"]
    assert reviews[like["review_ids"][0]].keys() >= {"id", "author", "score", "date", "text", "url", "platform"}


def test_game_card_carries_the_latest_overall_scores(client):
    from app.sources.base import OverallScore

    game_id = client.get("/api/games?q=Zelda").json()["items"][0]["id"]
    assert client.get(f"/api/games/{game_id}").json()["overall"] == {"critics": None, "users": None}

    def scores(critics: float, users: float | None) -> Game:
        return game("zelda", "Zelda", ["Action", "Adventure"], [("switch", 96, 9.0)]).__class__(
            slug="zelda", url="u", title="Zelda", genres=["Action", "Adventure"],
            platforms=[PlatformScore(slug="switch", name="SWITCH", metascore=96, userscore=9.0)],
            overall=[
                OverallScore("critics", critics, "Universal Acclaim", 51, 50, 1, 0),
                OverallScore("users", users, "Generally Favorable" if users else None, 1405, 1194, 79, 132),
            ],
        )

    with session_scope() as s:
        repository.save_game(s, "fake", scores(90.0, 8.5), NOW)
        repository.save_game(s, "fake", scores(91.0, None), datetime(2026, 11, 7, 10, 0))

    overall = client.get(f"/api/games/{game_id}").json()["overall"]
    assert overall["critics"]["score"] == 91.0  # the latest row wins
    assert (overall["critics"]["verdict"], overall["critics"]["reviews_count"]) == ("Universal Acclaim", 51)
    assert (overall["critics"]["positive"], overall["critics"]["mixed"], overall["critics"]["negative"]) == (50, 1, 0)
    assert overall["users"]["score"] is None and overall["users"]["verdict"] is None
    assert overall["critics"]["captured_at"].endswith("Z") or overall["critics"]["captured_at"].endswith("+00:00")


def test_summary_reviews_are_the_whole_sample_not_only_the_cited_ones(client):
    from app.db import review_repository
    from app.sources.base import Review

    game_id = client.get("/api/games?q=Zelda").json()["items"][0]["id"]
    sample = [
        Review(kind="users", text=f"review {i}", score=score, author=f"u{i}", date="Nov 1, 2026")
        for i, score in enumerate([10, 9, 4, 6])
    ]
    with session_scope() as s:
        review_repository.save_summary(
            s, game_id, "users", sample, 100, "stub", "h",
            likes=[("Fine", [1])], dislikes=[], now=NOW,
        )

    users = client.get(f"/api/games/{game_id}").json()["summaries"]["users"]
    assert sorted(r["text"] for r in users["reviews"]) == ["review 0", "review 1", "review 2", "review 3"]
    assert len(users["likes"][0]["review_ids"]) == 1


def scores(response) -> dict[str, tuple]:
    return {i["title"]: (i["score"]["critics"], i["score"]["users"]) for i in response.json()["items"]}


def test_every_game_has_one_score_the_mean_over_its_platforms(client):
    assert scores(client.get("/api/games")) == {
        "Zelda": (96, 9.0),
        "Doom 100%": (90, 7.8),  # (88 + 91) / 2 = 89.5 rounds half up; (8.5 + 7.0) / 2 = 7.75
        "Super Mario": (88, 8.0),  # (90 + 85) / 2 = 87.5; the platform without a userscore is skipped
        "Quake": (80, 9.5),
        "Lonely": (70, 6.0),
        "No Scores Game": (None, None),
    }


def test_score_follows_the_platform_filter(client):
    assert scores(client.get("/api/games?platform=pc")) == {
        "Doom 100%": (88, 8.5),
        "Super Mario": (85, None),
        "Quake": (80, 9.5),
        "Lonely": (70, 6.0),
        "No Scores Game": (None, None),
    }


def test_game_card_and_similar_games_carry_the_same_score(client):
    r = client.get("/api/games?q=Zelda").json()["items"][0]
    detail = client.get(f"/api/games/{r['id']}").json()
    assert detail["score"] == r["score"] == {"critics": 96, "users": 9.0}
    assert all("score" in similar for similar in detail["similar"])
    mario = next(s for s in detail["similar"] if s["title"] == "Super Mario")
    assert mario["score"] == {"critics": 88, "users": 8.0}


def add(*games: Game) -> None:
    with session_scope() as session:
        for item in games:
            repository.save_game(session, "fake", item, NOW)


def test_search_looks_in_the_developer(client):
    add(game("indie", "Indie Thing", ["Puzzle"], [("pc", 60, 6.0)], developer="Quiet Studio"))
    assert titles(client.get("/api/games?q=quiet")) == ["Indie Thing"]
    assert titles(client.get("/api/games?q=STUDIO")) == ["Indie Thing"]


def test_search_looks_in_the_description(client):
    add(game("farm", "Green Acres", [], [("pc", 60, 6.0)], description="A cozy farming simulator with goats"))
    assert titles(client.get("/api/games?q=farming")) == ["Green Acres"]
    assert titles(client.get("/api/games?q=GOATS")) == ["Green Acres"]


def test_the_words_of_the_query_may_belong_to_different_fields(client):
    add(game("indie", "Indie Thing", ["Puzzle"], [("pc", 60, 6.0)], developer="Quiet Studio", description="Slide blocks"))
    assert titles(client.get("/api/games?q=quiet indie")) == ["Indie Thing"]  # developer and title
    assert titles(client.get("/api/games?q=indie quiet")) == ["Indie Thing"]  # the order does not matter
    assert titles(client.get("/api/games?q=puzzle quiet blocks")) == ["Indie Thing"]  # genre, developer, description
    assert client.get("/api/games?q=quiet missing").json()["total"] == 0  # every word has to be found


def test_a_game_named_like_the_query_goes_before_the_ones_that_only_mention_it(client):
    add(game("fan", "Fan Game", [], [("pc", 99, 9.9)], description="A love letter to Super Mario and friends"))
    # the fan game has the better score, but Super Mario carries the name
    assert titles(client.get("/api/games?q=mario")) == ["Super Mario", "Fan Game"]
    assert titles(client.get("/api/games?q=mario&sort=metascore&order=asc")) == ["Super Mario", "Fan Game"]


def test_the_chosen_sort_still_rules_inside_the_groups(client):
    add(
        game("a", "Quest Alpha", [], [("pc", 50, 5.0)]),
        game("b", "Quest Beta", [], [("pc", 90, 9.0)]),
        game("c", "Dull", [], [("pc", 95, 9.5)], description="Not a quest for anyone"),
    )
    assert titles(client.get("/api/games?q=quest")) == ["Quest Beta", "Quest Alpha", "Dull"]
    assert titles(client.get("/api/games?q=quest&sort=title&order=asc")) == ["Quest Alpha", "Quest Beta", "Dull"]


def test_a_game_matching_in_several_fields_is_listed_once(client):
    add(game("dup", "Shooter Hero", ["Shooter"], [("pc", 60, 6.0)], developer="Shooter Works", description="shooter"))
    assert titles(client.get("/api/games?q=shooter")).count("Shooter Hero") == 1
    assert client.get("/api/games?q=shooter").json()["total"] == 3  # Doom, Quake and this one


def test_an_empty_or_blank_query_finds_everything(client):
    assert client.get("/api/games?q=").json()["total"] == 6
    assert client.get("/api/games?q=%20%20").json()["total"] == 6
