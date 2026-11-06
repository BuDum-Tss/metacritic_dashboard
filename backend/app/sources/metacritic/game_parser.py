import json
import re
from dataclasses import dataclass
from urllib.parse import parse_qs, urlparse

from bs4 import BeautifulSoup

from app.sources.base import Game, PlatformScore

BASE_URL = "https://www.metacritic.com"


@dataclass
class UserScore:
    userscore: float | None = None
    user_reviews_count: int | None = None


def _testid(soup: BeautifulSoup, name: str):
    return soup.find(attrs={"data-testid": name})


def _int(text: str | None) -> int | None:
    m = re.search(r"\d[\d,]*", text or "")
    return int(m.group(0).replace(",", "")) if m else None


def _json_ld(soup: BeautifulSoup) -> dict:
    for tag in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(tag.string or "")
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict) and data.get("@type") == "VideoGame":
            return data
    return {}


def _developer(soup: BeautifulSoup) -> str | None:
    block = _testid(soup, "hero-summary-developer")
    if block is None:
        return None
    # developer is a link for known companies and plain text otherwise
    text = block.get_text(" ", strip=True).removeprefix("Developer:").strip()
    return text or None


def _genres(soup: BeautifulSoup, ld: dict) -> list[str]:
    details = _testid(soup, "game-details")
    if details is not None:
        for span in details.find_all("span"):
            if span.get_text(strip=True) == "Genres:":
                items = span.find_next("ul")
                if items is not None:
                    return [li.get_text(strip=True) for li in items.find_all("li")]
    genre = ld.get("genre")
    if isinstance(genre, list):
        return genre
    return [genre] if genre else []


def _platform_cards(soup: BeautifulSoup) -> list[PlatformScore]:
    block = _testid(soup, "all-platforms")
    if block is None:
        return []
    platforms: list[PlatformScore] = []
    for card in block.find_all(attrs={"data-testid": "product-score-card"}):
        slug = parse_qs(urlparse(card.get("href", "")).query).get("platform", [None])[0]
        icon = card.find(attrs={"title": True})
        if not slug or icon is None:
            continue
        score = card.find(attrs={"aria-label": re.compile(r"^Metascore")})
        label = score.get("aria-label", "") if score else ""
        m = re.match(r"Metascore (\d+) out of 100", label)
        count = re.search(r"Based on ([\d,]+) Critic Reviews", card.get_text(" ", strip=True))
        platforms.append(
            PlatformScore(
                slug=slug,
                name=icon["title"],
                metascore=int(m.group(1)) if m else None,
                critic_reviews_count=_int(count.group(1)) if count else None,
            )
        )
    return platforms


def parse_game(html: str, slug: str) -> Game:
    """Parse a game page. Platforms come without user scores (see parse_user_score)."""
    soup = BeautifulSoup(html, "html.parser")
    ld = _json_ld(soup)

    title = ld.get("name")
    if not title:
        h1 = soup.find("h1")
        title = h1.get_text(strip=True) if h1 else None
    if not title:
        raise ValueError(f"game title not found: {slug}")

    trailer = ld.get("trailer") or {}
    return Game(
        slug=slug,
        url=f"{BASE_URL}/game/{slug}/",
        title=title,
        cover_url=ld.get("image"),
        developer=_developer(soup),
        description=ld.get("description") or None,
        video_url=trailer.get("embedUrl") or trailer.get("contentUrl"),
        genres=_genres(soup, ld),
        platforms=_platform_cards(soup),
    )


def parse_user_score(html: str) -> UserScore:
    """User score and the number of user ratings from a game page."""
    soup = BeautifulSoup(html, "html.parser")
    block = _testid(soup, "user-reviews")
    if block is None:
        return UserScore()
    label = block.find(attrs={"aria-label": re.compile(r"^User score")})
    m = re.match(r"User score (\d+(?:\.\d+)?) out of 10", label.get("aria-label", "")) if label else None
    count = re.search(r"Based on ([\d,]+) User Ratings?", block.get_text(" ", strip=True))
    return UserScore(
        userscore=float(m.group(1)) if m else None,
        user_reviews_count=_int(count.group(1)) if count else None,
    )
