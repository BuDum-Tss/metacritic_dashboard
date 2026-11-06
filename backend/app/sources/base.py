from dataclasses import dataclass, field
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
class Game:
    slug: str
    url: str
    title: str
    cover_url: str | None = None
    developer: str | None = None
    description: str | None = None
    video_url: str | None = None
    genres: list[str] = field(default_factory=list)
    platforms: list[PlatformScore] = field(default_factory=list)


class GameSource(Protocol):
    """A site games are collected from. The rest of the app depends only on this."""

    name: str

    def list_batch(self, batch_index: int, limit: int) -> list[str]:
        """Refs of the games of the day's `batch_index`-th batch (0-based)."""
        ...

    def fetch_game(self, ref: str) -> Game:
        """Load and parse one game completely."""
        ...
