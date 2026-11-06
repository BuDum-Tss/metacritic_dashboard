from pathlib import Path

from app.sources.metacritic.game_parser import parse_game, parse_review_stats, parse_user_score
from app.sources.metacritic.list_parser import parse_browse, parse_new_releases
from app.sources.metacritic.review_parser import parse_game_page_reviews, parse_review_page

FIXTURES = Path(__file__).parent / "fixtures"


def read(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def test_new_releases_returns_20_unique_slugs():
    slugs = parse_new_releases(read("home.html"))
    assert len(slugs) == 20
    assert len(set(slugs)) == 20
    assert slugs[0] == "the-legend-of-zelda-ocarina-of-time-2026"


def test_browse_returns_50_slugs():
    slugs = parse_browse(read("browse.html"))
    assert len(slugs) == 50
    assert len(set(slugs)) == 50
    assert slugs[0] == "flashes-of-chaos"


def test_game_with_two_platforms():
    game = parse_game(read("phantom-blade-zero.html"), "phantom-blade-zero")
    assert game.title == "Phantom Blade Zero"
    assert game.developer == "S-Game"
    assert game.genres == ["Action Adventure"]
    assert game.cover_url and game.cover_url.startswith("https://")
    assert game.description and game.description.startswith("S-GAME presents")
    assert game.video_url
    platforms = {p.slug: p for p in game.platforms}
    assert set(platforms) == {"playstation-5", "pc"}
    assert platforms["playstation-5"].name == "PlayStation 5"
    assert platforms["playstation-5"].metascore == 86
    assert platforms["playstation-5"].critic_reviews_count == 46
    assert platforms["pc"].metascore == 88
    assert platforms["pc"].critic_reviews_count == 52


def test_game_with_one_platform():
    game = parse_game(read("stellar-blade-complete-edition.html"), "stellar-blade-complete-edition")
    assert game.developer == "SHIFT UP Corporation"
    assert [(p.slug, p.name, p.metascore) for p in game.platforms] == [
        ("nintendo-switch-2", "Nintendo Switch 2", 81)
    ]


def test_user_score():
    score = parse_user_score(read("phantom-blade-zero.html"))
    assert score.userscore == 8.7
    assert score.user_reviews_count == 1405


def test_user_score_tbd():
    score = parse_user_score(read("stellar-blade-complete-edition.html"))
    assert score.userscore is None


def test_critic_reviews_page():
    reviews = parse_review_page(read("phantom-critic-reviews.html"), "critics", "PC")
    assert len(reviews) == 10
    first = reviews[0]
    assert (first.kind, first.score, first.author, first.date) == ("critics", 100, "But Why Tho?", "Oct 25, 2026")
    assert first.text.startswith("A beautiful and horrific game")
    assert first.url == "https://butwhytho.net/2026/10/phantom-blade-zero-review-s-game-wuxia/"
    assert first.platform == "PC"
    assert len({r.key for r in reviews}) == 10


def test_user_reviews_page_skips_spoiler_placeholders():
    reviews = parse_review_page(read("phantom-user-reviews.html"), "users", "PC")
    assert len(reviews) == 45  # 50 cards, 5 of them hide the text behind a spoiler warning
    assert all(not r.text.startswith("[SPOILER") for r in reviews)
    assert all(r.kind == "users" and r.score is not None and r.author for r in reviews)
    assert {r.score for r in reviews} >= {10, 0}  # not only praise


def test_game_page_reviews_come_from_all_four_blocks_with_mixed_scores():
    reviews = parse_game_page_reviews(read("phantom-blade-zero.html"))
    critics = [r.score for r in reviews if r.kind == "critics"]
    users = [r.score for r in reviews if r.kind == "users"]
    assert sorted(critics) == [60, 85, 90, 90, 90, 95, 100]
    assert sorted(users) == [4, 4, 7, 7, 10, 10]  # the spoiler one is skipped


def test_review_stats_of_a_game_page():
    stats = parse_review_stats(read("phantom-blade-zero.html"))
    assert (stats.critics_total, stats.users_total) == (51, 1405)
    assert stats.critics_tones == {"positive": 50, "mixed": 1}
    assert stats.users_tones == {"positive": 1194, "mixed": 79, "negative": 132}


def test_developer_as_plain_text():
    html = (
        '<div data-testid="hero-summary-developer"><p>'
        '<span>Developer:</span> PHOSEPO</p></div>'
        '<script type="application/ld+json">{"@type":"VideoGame","name":"X"}</script>'
    )
    assert parse_game(html, "x").developer == "PHOSEPO"


def test_overall_scores_of_a_game_page():
    game = parse_game(read("phantom-blade-zero.html"), "phantom-blade-zero")
    overall = {o.kind: o for o in game.overall}
    critics, users = overall["critics"], overall["users"]
    assert (critics.score, critics.verdict, critics.reviews_count) == (88.0, "Generally Favorable", 51)
    assert (critics.positive, critics.mixed, critics.negative) == (50, 1, None)
    assert (users.score, users.verdict, users.reviews_count) == (8.7, "Generally Favorable", 1405)
    assert (users.positive, users.mixed, users.negative) == (1194, 79, 132)


def test_overall_user_score_is_empty_while_the_site_has_none():
    game = parse_game(read("stellar-blade-complete-edition.html"), "stellar-blade-complete-edition")
    overall = {o.kind: o for o in game.overall}
    assert overall["critics"].score == 81.0
    users = overall["users"]
    assert (users.score, users.verdict) == (None, None)  # "Available after 4 ratings" is not a verdict
