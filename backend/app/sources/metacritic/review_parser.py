import re

from bs4 import BeautifulSoup

from app.sources.base import Review

SPOILER_PLACEHOLDER = "[SPOILER ALERT"


def _testid(parent, name: str):
    return parent.find(attrs={"data-testid": name})


def _cards(cards, kind: str, platform: str | None) -> list[Review]:
    reviews: list[Review] = []
    for card in cards:
        quote = _testid(card, "review-quote-text")
        text = quote.get_text(" ", strip=True) if quote else ""
        # a spoiler review has no text in the HTML, only a placeholder line
        if not text or text.startswith(SPOILER_PLACEHOLDER):
            continue

        score_tag = card.find(attrs={"aria-label": re.compile(r"out of \d+")})
        m = re.search(r"(\d+(?:\.\d+)?) out of", score_tag["aria-label"]) if score_tag else None
        score = round(float(m.group(1))) if m else None

        header = _testid(card, "review-card-header")
        author = header.get_text(" ", strip=True) if header else ""
        parts = author.split(" ", 1)
        if score is not None and len(parts) == 2 and parts[0] == str(score):
            author = parts[1]  # the score badge text comes first

        date = _testid(card, "review-card-date")
        link = _testid(card, "review-full-review-link")
        card_platform = _testid(card, "review-platform")
        reviews.append(
            Review(
                kind=kind,
                text=text,
                score=score,
                author=author or None,
                date=date.get_text(strip=True) if date else None,
                url=link.get("href") if link else None,
                platform=card_platform.get_text(strip=True) if card_platform else platform,
            )
        )
    return reviews


def parse_review_page(html: str, kind: str, platform: str | None = None) -> list[Review]:
    """Reviews from /critic-reviews/ or /user-reviews/ (kind: "critics" or "users")."""
    soup = BeautifulSoup(html, "html.parser")
    return _cards(soup.find_all(attrs={"data-testid": "review-card"}), kind, platform)


def parse_game_page_reviews(html: str) -> list[Review]:
    """The reviews shown on the game page itself: a mixed selection of critics and users."""
    soup = BeautifulSoup(html, "html.parser")
    # the cards sit in critic-reviews, critic-reviews-bottom, user-reviews and user-reviews-bottom
    reviews: list[Review] = []
    for card in soup.find_all(attrs={"data-testid": "review-card"}):
        ancestors = [p.get("data-testid", "") for p in card.parents if hasattr(p, "get")]
        if any(a.startswith("critic-reviews") for a in ancestors):
            reviews += _cards([card], "critics", None)
        elif any(a.startswith("user-reviews") for a in ancestors):
            reviews += _cards([card], "users", None)
    return reviews
