from app.sources.base import Game
from app.sources.metacritic.client import HttpClient
from app.sources.metacritic.game_parser import BASE_URL, parse_game, parse_user_score
from app.sources.metacritic.list_parser import parse_browse, parse_new_releases

NEW_RELEASES_URL = f"{BASE_URL}/game/"
SEE_ALL_URL = f"{BASE_URL}/browse/game/all/all/all-time/new/"
SEE_ALL_PAGE_SIZE = 50


class MetacriticSource:
    name = "metacritic"

    def __init__(self, client: HttpClient | None = None) -> None:
        self._client = client or HttpClient()

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
        game = parse_game(main_html, ref)

        for platform in game.platforms:
            # the page shows the user score of one platform; with a single platform it is ours
            html = main_html if len(game.platforms) == 1 else self._client.get(url, params={"platform": platform.slug})
            score = parse_user_score(html)
            platform.userscore = score.userscore
            platform.user_reviews_count = score.user_reviews_count
        return game
