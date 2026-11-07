import hashlib
from dataclasses import dataclass, field
from datetime import date
from typing import Protocol


@dataclass
class PlatformScore:
    slug: str
    name: str
    metascore: int | None = None
    critic_reviews_count: int | None = None
    userscore: float | None = None
    user_reviews_count: int | None = None


@dataclass
class OverallScore:
    """The overall score of critics or users as the site shows it at the top of a game page."""

    kind: str  # "critics" | "users"
    score: float | None = None  # Metascore 0-100 or Userscore 0-10; None while the site has no score
    verdict: str | None = None  # e.g. "Generally Favorable"
    reviews_count: int | None = None
    positive: int | None = None
    mixed: int | None = None
    negative: int | None = None


@dataclass
class Game:
    slug: str
    url: str
    title: str
    cover_url: str | None = None
    developer: str | None = None
    description: str | None = None
    video_url: str | None = None
    release_date: date | None = None  # the day the game came out
    genres: list[str] = field(default_factory=list)
    platforms: list[PlatformScore] = field(default_factory=list)
    overall: list[OverallScore] = field(default_factory=list)


@dataclass
class Review:
    kind: str  # "critics" | "users"
    text: str
    score: int | None = None
    author: str | None = None
    date: str | None = None
    url: str | None = None
    platform: str | None = None
    key: str = ""  # stable identity: sites do not give review ids

    def __post_init__(self) -> None:
        if not self.key:
            raw = "\x1f".join([self.kind, self.author or "", self.date or "", str(self.score), self.text])
            self.key = hashlib.sha256(raw.encode()).hexdigest()


@dataclass
class ReviewStats:
    """Totals and the tone split of all reviews of a game, as the site reports them."""

    critics_total: int | None = None
    users_total: int | None = None
    critics_tones: dict[str, int] = field(default_factory=dict)  # positive / mixed / negative
    users_tones: dict[str, int] = field(default_factory=dict)


@dataclass
class ReviewBundle:
    reviews: list[Review] = field(default_factory=list)
    stats: ReviewStats = field(default_factory=ReviewStats)


class GameSource(Protocol):
    """A site games are collected from. The rest of the app depends only on this."""

    name: str

    def discover(self, limit: int) -> list[str]:
        """Refs of the newest `limit` games, newest first. Used only to find new games."""
        ...

    def fetch_game(self, ref: str) -> Game:
        """Load and parse one game completely."""
        ...

    def fetch_reviews(self, game: Game, kinds: tuple[str, ...] = ("critics", "users")) -> ReviewBundle:
        """Collect the reviews of the given kinds available for a game, plus the site's totals."""
        ...
