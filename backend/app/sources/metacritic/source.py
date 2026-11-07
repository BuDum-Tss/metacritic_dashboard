from app.sources.base import Game, PlatformScore, Review, ReviewBundle
from app.sources.metacritic.client import HttpClient
from app.sources.metacritic.game_parser import BASE_URL, parse_game, parse_review_stats, parse_user_score
from app.sources.metacritic.list_parser import parse_browse, parse_new_releases
from app.sources.metacritic.review_parser import parse_game_page_reviews, parse_review_page

NEW_RELEASES_URL = f"{BASE_URL}/game/"
SEE_ALL_URL = f"{BASE_URL}/browse/game/all/all/all-time/new/"


def _with_reviews(platforms: list[PlatformScore], attr: str) -> list[PlatformScore]:
    """The platforms of a game that have reviews of the kind: each has pages of its own."""
    return [p for p in platforms if (getattr(p, attr) or 0) > 0]


class MetacriticSource:
    name = "metacritic"

    def __init__(self, client: HttpClient | None = None) -> None:
        self._client = client or HttpClient()
        self._last_page: tuple[str, str] | None = None  # (slug, html) of the last game page

    def discover(self, limit: int) -> list[str]:
        """New Releases first, then SEE ALL page by page until `limit` games are collected."""
        refs = parse_new_releases(self._client.get(NEW_RELEASES_URL))
        seen = set(refs)
        page = 1
        while len(refs) < limit:
            slugs = parse_browse(self._client.get(SEE_ALL_URL, params={"page": page}))
            fresh = [slug for slug in slugs if slug not in seen]
            if not fresh:  # the end of the list, or a page that adds nothing
                break
            refs += fresh
            seen.update(fresh)
            page += 1
        return refs[:limit]

    def fetch_game(self, ref: str) -> Game:
        url = f"{BASE_URL}/game/{ref}/"
        main_html = self._client.get(url)
        self._last_page = (ref, main_html)
        game = parse_game(main_html, ref)

        for platform in game.platforms:
            # the page shows the user score of one platform; with a single platform it is ours
            html = main_html if len(game.platforms) == 1 else self._client.get(url, params={"platform": platform.slug})
            score = parse_user_score(html)
            platform.userscore = score.userscore
            platform.user_reviews_count = score.user_reviews_count
        return game

    def _game_page(self, slug: str) -> str:
        if self._last_page and self._last_page[0] == slug:
            return self._last_page[1]
        return self._client.get(f"{BASE_URL}/game/{slug}/")

    def fetch_reviews(self, game: Game, kinds: tuple[str, ...] = ("critics", "users")) -> ReviewBundle:
        """Reviews from the game page and the review pages (only the HTML of the site is used)."""
        main_html = self._game_page(game.slug)
        reviews: list[Review] = [r for r in parse_game_page_reviews(main_html) if r.kind in kinds]
        if "critics" in kinds:
            for platform in _with_reviews(game.platforms, "critic_reviews_count"):
                html = self._client.get(
                    f"{BASE_URL}/game/{game.slug}/critic-reviews/", params={"platform": platform.slug}
                )
                reviews += parse_review_page(html, "critics", platform.name)
        if "users" in kinds:
            for platform in _with_reviews(game.platforms, "user_reviews_count"):
                html = self._client.get(
                    f"{BASE_URL}/game/{game.slug}/user-reviews/", params={"platform": platform.slug}
                )
                reviews += parse_review_page(html, "users", platform.name)
        return ReviewBundle(reviews=reviews, stats=parse_review_stats(main_html))
