from pathlib import Path

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


def test_batch_zero_is_new_releases():
    source = MetacriticSource(FakeClient())
    assert len(source.list_batch(0, 20)) == 20


def test_first_see_all_batch_reads_page_one():
    client = FakeClient()
    slugs = MetacriticSource(client).list_batch(1, 20)
    assert len(slugs) == 20
    assert [params for _, params in client.calls] == [{"page": 1}]


def test_batch_crossing_page_boundary_loads_next_page():
    client = FakeClient()
    slugs = MetacriticSource(client).list_batch(3, 20)  # SEE ALL positions 40..59
    assert len(slugs) == 20
    assert [params for _, params in client.calls] == [{"page": 1}, {"page": 2}]


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
    assert sorted(p["platform"] for p in critic_calls) == ["pc", "playstation-5"]  # two platforms with critic reviews
    assert len(user_calls) == 1  # one platform for user reviews
    assert len(urls) == 3  # the game page itself is not requested again

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
