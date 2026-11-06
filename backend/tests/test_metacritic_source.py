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
