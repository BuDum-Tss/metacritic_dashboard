from dataclasses import dataclass, field


@dataclass
class PlatformScore:
    slug: str
    name: str
    metascore: int | None = None
    critic_reviews_count: int | None = None
    userscore: float | None = None
    user_reviews_count: int | None = None


@dataclass
class UserScore:
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
