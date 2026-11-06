from pathlib import Path

from app.parsers.game_parser import parse_game, parse_user_score
from app.parsers.list_parser import parse_browse, parse_new_releases

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


def test_developer_as_plain_text():
    html = (
        '<div data-testid="hero-summary-developer"><p>'
        '<span>Developer:</span> PHOSEPO</p></div>'
        '<script type="application/ld+json">{"@type":"VideoGame","name":"X"}</script>'
    )
    assert parse_game(html, "x").developer == "PHOSEPO"
