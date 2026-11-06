from app.sources.base import Game, PlatformScore, Review, ReviewBundle
from app.sources.metacritic.client import HttpClient
from app.sources.metacritic.game_parser import BASE_URL, parse_game, parse_review_stats, parse_user_score
from app.sources.metacritic.list_parser import parse_browse, parse_new_releases
from app.sources.metacritic.review_parser import parse_game_page_reviews, parse_review_page

NEW_RELEASES_URL = f"{BASE_URL}/game/"
SEE_ALL_URL = f"{BASE_URL}/browse/game/all/all/all-time/new/"
SEE_ALL_PAGE_SIZE = 50
CRITIC_PLATFORMS = 2  # critic pages are taken for this many platforms with the most critic reviews


def _top_platforms(platforms: list[PlatformScore], attr: str, count: int) -> list[PlatformScore]:
    with_reviews = [p for p in platforms if (getattr(p, attr) or 0) > 0]
    return sorted(with_reviews, key=lambda p: getattr(p, attr), reverse=True)[:count]


class MetacriticSource:
    name = "metacritic"

    def __init__(self, client: HttpClient | None = None) -> None:
        self._client = client or HttpClient()
        self._last_page: tuple[str, str] | None = None  # (slug, html) of the last game page

    def list_batch(self, batch_index: int, limit: int) -> list[str]:
        """Batch 0 is New Releases; batch n >= 1 is SEE ALL starting at (n - 1) * limit."""
        if batch_index == 0:
            return parse_new_releases(self._client.get(NEW_RELEASES_URL))[:limit]

        position = (batch_index - 1) * limit
        page = position // SEE_ALL_PAGE_SIZE + 1
        skip = position % SEE_ALL_PAGE_SIZE
        slugs: list[str] = []
        while len(slugs) < skip + limit:
            page_slugs = parse_browse(self._client.get(SEE_ALL_URL, params={"page": page}))
            if not page_slugs:
                break
            slugs.extend(page_slugs)
            page += 1
        return slugs[skip : skip + limit]

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

    def fetch_reviews(self, game: Game) -> ReviewBundle:
        """Reviews from the game page and the review pages (only the HTML of the site is used)."""
        if self._last_page and self._last_page[0] == game.slug:
            main_html = self._last_page[1]
        else:
            main_html = self._client.get(f"{BASE_URL}/game/{game.slug}/")

        reviews: list[Review] = parse_game_page_reviews(main_html)
        for platform in _top_platforms(game.platforms, "critic_reviews_count", CRITIC_PLATFORMS):
            html = self._client.get(
                f"{BASE_URL}/game/{game.slug}/critic-reviews/", params={"platform": platform.slug}
            )
            reviews += parse_review_page(html, "critics", platform.name)
        for platform in _top_platforms(game.platforms, "user_reviews_count", 1):
            html = self._client.get(f"{BASE_URL}/game/{game.slug}/user-reviews/", params={"platform": platform.slug})
            reviews += parse_review_page(html, "users", platform.name)
        return ReviewBundle(reviews=reviews, stats=parse_review_stats(main_html))
