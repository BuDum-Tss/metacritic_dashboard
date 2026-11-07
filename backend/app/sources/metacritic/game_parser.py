import json
import re
from dataclasses import dataclass
from datetime import date
from urllib.parse import parse_qs, urlparse

from bs4 import BeautifulSoup

from app.sources.base import Game, OverallScore, PlatformScore, ReviewStats

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


def _overall(soup: BeautifulSoup) -> list[OverallScore]:
    """The overall Metascore and Userscore blocks of a game page."""
    blocks = (
        ("critics", "product-score", "Metascore", r"Metascore (\d+(?:\.\d+)?) out of 100", r"Based on ([\d,]+) Critic Reviews"),
        ("users", "user-reviews", "User score", r"User score (\d+(?:\.\d+)?) out of 10", r"Based on ([\d,]+) User Ratings?"),
    )
    result: list[OverallScore] = []
    for kind, testid, prefix, score_pattern, count_pattern in blocks:
        block = _testid(soup, testid)
        if block is None:
            continue
        # the first label is the overall score; "User score TBD" means there is none yet
        label = block.find(attrs={"aria-label": re.compile(f"^{prefix}")})
        m = re.match(score_pattern, label["aria-label"]) if label else None
        score = float(m.group(1)) if m else None
        sentiment = _testid(block, "global-score-sentiment")
        count = re.search(count_pattern, block.get_text(" ", strip=True))
        tones = _tones(block)
        result.append(
            OverallScore(
                kind=kind,
                score=score,
                verdict=sentiment.get_text(" ", strip=True) if sentiment and score is not None else None,
                reviews_count=_int(count.group(1)) if count else None,
                positive=tones.get("positive"),
                mixed=tones.get("mixed"),
                negative=tones.get("negative"),
            )
        )
    return result


def _release_date(ld: dict) -> date | None:
    """The release day from the JSON-LD `datePublished` ("2026-11-05"), None when absent or odd."""
    try:
        return date.fromisoformat(str(ld.get("datePublished"))[:10])
    except ValueError:
        return None


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
        release_date=_release_date(ld),
        genres=_genres(soup, ld),
        platforms=_platform_cards(soup),
        overall=_overall(soup),
    )


def _tones(block) -> dict[str, int]:
    """Counts of positive/mixed/negative reviews from labels like '50 positive reviews (98%)'."""
    tones: dict[str, int] = {}
    if block is None:
        return tones
    for element in block.find_all(attrs={"aria-label": re.compile(r"^[\d,]+ (positive|neutral|negative) reviews")}):
        m = re.match(r"([\d,]+) (positive|neutral|negative) reviews", element["aria-label"])
        tone = "mixed" if m.group(2) == "neutral" else m.group(2)
        tones[tone] = int(m.group(1).replace(",", ""))
    return tones


def parse_review_stats(html: str) -> ReviewStats:
    """Review totals and the tone split of a game page (for the platform the page shows)."""
    soup = BeautifulSoup(html, "html.parser")
    critics = _testid(soup, "product-score")
    users = _testid(soup, "user-reviews")
    critics_total = re.search(r"Based on ([\d,]+) Critic Reviews", critics.get_text(" ", strip=True)) if critics else None
    users_total = re.search(r"Based on ([\d,]+) User Ratings?", users.get_text(" ", strip=True)) if users else None
    return ReviewStats(
        critics_total=_int(critics_total.group(1)) if critics_total else None,
        users_total=_int(users_total.group(1)) if users_total else None,
        critics_tones=_tones(critics),
        users_tones=_tones(users),
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
