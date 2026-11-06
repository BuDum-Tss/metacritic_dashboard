import re

from bs4 import BeautifulSoup

GAME_HREF = re.compile(r"^/game/([^/]+)/?$")


def _slugs(anchors) -> list[str]:
    slugs: list[str] = []
    for a in anchors:
        m = GAME_HREF.match(a.get("href", ""))
        if m and m.group(1) not in slugs:
            slugs.append(m.group(1))
    return slugs


def parse_new_releases(html: str) -> list[str]:
    """Slugs of games from the New Releases carousel on /game/."""
    soup = BeautifulSoup(html, "html.parser")
    carousel = soup.find(attrs={"data-testid": "new-game-release-carousel"})
    if carousel is None:
        return []
    return _slugs(carousel.find_all("a", attrs={"data-testid": "product-card-content"}))


def parse_browse(html: str) -> list[str]:
    """Slugs of games from a SEE ALL (browse) page, in page order."""
    soup = BeautifulSoup(html, "html.parser")
    anchors = []
    for card in soup.find_all(attrs={"data-testid": "filter-results"}):
        a = card.find("a", href=GAME_HREF)
        if a is not None:
            anchors.append(a)
    return _slugs(anchors)
