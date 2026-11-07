from pathlib import Path

from app.sources.metacritic.list_parser import parse_browse, parse_new_releases
from app.sources.metacritic.source import NEW_RELEASES_URL, MetacriticSource

FIXTURES = Path(__file__).parent / "fixtures"


class FakeClient:
    """Serves saved pages; every SEE ALL page is the same fixture."""

    def __init__(self, game_page: str = "phantom-blade-zero.html"):
        self.game_page = game_page
        self.calls: list[tuple[str, dict | None]] = []

    def get(self, url: str, params: dict | None = None) -> str:
        self.calls.append((url, params))
        if url == NEW_RELEASES_URL:
            name = "home.html"
        elif "/browse/" in url:
            name = "browse.html"
        elif "/critic-reviews/" in url:
            name = "phantom-critic-reviews.html"
        elif "/user-reviews/" in url:
            name = "phantom-user-reviews.html"
        else:
            name = self.game_page
        return (FIXTURES / name).read_text(encoding="utf-8")


def slugs_of(name: str, parser) -> list[str]:
    return parser((FIXTURES / name).read_text(encoding="utf-8"))


def test_discover_starts_with_new_releases_then_see_all():
    client = FakeClient()
    refs = MetacriticSource(client).discover(60)
    new_releases = slugs_of("home.html", parse_new_releases)
    assert refs[:20] == new_releases
    assert len(refs) == 60 and len(set(refs)) == 60  # a game of both lists is counted once
    assert [params for _, params in client.calls] == [None, {"page": 1}]


def test_discover_goes_through_the_pages_until_nothing_new_is_added():
    client = FakeClient()  # every SEE ALL page is the same fixture: page 2 adds nothing
    refs = MetacriticSource(client).discover(500)
    expected = set(slugs_of("home.html", parse_new_releases)) | set(slugs_of("browse.html", parse_browse))
    assert set(refs) == expected and len(refs) == len(expected)
    assert [params for _, params in client.calls] == [None, {"page": 1}, {"page": 2}]


def test_discover_with_a_small_limit_needs_no_see_all_page():
    client = FakeClient()
    assert len(MetacriticSource(client).discover(5)) == 5
    assert len(client.calls) == 1


def test_fetch_game_loads_user_score_per_platform():
    client = FakeClient()
    game = MetacriticSource(client).fetch_game("phantom-blade-zero")
    assert len(game.platforms) == 2
    assert all(p.userscore == 8.7 for p in game.platforms)
    assert [params for _, params in client.calls] == [None, {"platform": "playstation-5"}, {"platform": "pc"}]


def test_fetch_game_with_single_platform_makes_one_request():
    client = FakeClient("stellar-blade-complete-edition.html")
    game = MetacriticSource(client).fetch_game("stellar-blade-complete-edition")
    assert len(game.platforms) == 1
    assert len(client.calls) == 1


def test_fetch_reviews_collects_every_html_source():
    client = FakeClient()
    source = MetacriticSource(client)
    game = source.fetch_game("phantom-blade-zero")
    client.calls.clear()

    bundle = source.fetch_reviews(game)

    urls = [(url.split("/game/")[1], params) for url, params in client.calls]
    critic_calls = [p for u, p in urls if "critic-reviews" in u]
    user_calls = [p for u, p in urls if "user-reviews" in u]
    assert sorted(p["platform"] for p in critic_calls) == ["pc", "playstation-5"]  # every platform with critic reviews
    assert sorted(p["platform"] for p in user_calls) == ["pc", "playstation-5"]  # ...and with player ratings
    assert len(urls) == 4  # the game page itself is not requested again

    critics = [r for r in bundle.reviews if r.kind == "critics"]
    users = [r for r in bundle.reviews if r.kind == "users"]
    assert len(critics) == 2 + 5 + 10 + 10  # game page blocks + two critic pages
    assert len(users) > 40
    assert bundle.stats.critics_total == 51
    assert bundle.stats.users_total == 1405
    assert bundle.stats.users_tones == {"positive": 1194, "mixed": 79, "negative": 132}


def test_fetch_reviews_without_a_prior_fetch_loads_the_game_page():
    client = FakeClient()
    source = MetacriticSource(client)
    game = source.fetch_game("phantom-blade-zero")
    other = MetacriticSource(FakeClient())  # a source that has not seen the page
    other.fetch_reviews(game)
    assert any(url.endswith("/game/phantom-blade-zero/") for url, _ in other._client.calls)


def test_game_without_reviews_pages_makes_no_extra_requests():
    client = FakeClient("stellar-blade-complete-edition.html")
    source = MetacriticSource(client)
    game = source.fetch_game("stellar-blade-complete-edition")
    for platform in game.platforms:
        platform.critic_reviews_count = None
        platform.user_reviews_count = None
    client.calls.clear()

    source.fetch_reviews(game)
    assert client.calls == []


def test_fetch_reviews_loads_only_the_pages_of_the_requested_kinds():
    client = FakeClient()
    source = MetacriticSource(client)
    game = source.fetch_game("phantom-blade-zero")
    client.calls.clear()

    bundle = source.fetch_reviews(game, ("users",))

    urls = [url for url, _ in client.calls]
    assert len(urls) == 2 and all("user-reviews" in url for url in urls)  # a page per platform, no critic pages
    assert {r.kind for r in bundle.reviews} == {"users"}


def test_every_platform_with_reviews_is_fetched_and_those_without_are_skipped():
    from app.sources.base import Game, PlatformScore

    client = FakeClient()
    source = MetacriticSource(client)
    game = Game(
        slug="phantom-blade-zero",
        url="u",
        title="X",
        platforms=[
            PlatformScore(slug="a", name="A", critic_reviews_count=5, user_reviews_count=5),
            PlatformScore(slug="b", name="B", critic_reviews_count=3, user_reviews_count=None),
            PlatformScore(slug="c", name="C", critic_reviews_count=None, user_reviews_count=None),
            PlatformScore(slug="d", name="D", critic_reviews_count=0, user_reviews_count=2),
        ],
    )
    source.fetch_reviews(game)

    pages = [(url.split("/game/phantom-blade-zero/")[1], params["platform"]) for url, params in client.calls if params]
    assert sorted(p for u, p in pages if u.startswith("critic-reviews")) == ["a", "b"]
    assert sorted(p for u, p in pages if u.startswith("user-reviews")) == ["a", "d"]
