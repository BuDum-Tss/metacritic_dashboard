from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, field_validator


def as_utc(value: datetime | None) -> datetime | None:
    """Times are stored as naive UTC; the API always returns them with an explicit UTC offset."""
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


class SyncRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    trigger: str
    status: str
    source: str
    batch_index: int
    started_at: datetime
    finished_at: datetime | None
    games_found: int | None
    games_processed: int | None
    games_failed: int | None
    error: str | None

    _utc = field_validator("started_at", "finished_at")(as_utc)


class SyncStatus(BaseModel):
    running: bool
    interval_hours: int
    next_run_at: datetime | None
    current_run: SyncRunOut | None
    last_run: SyncRunOut | None

    _utc = field_validator("next_run_at")(as_utc)


class PlatformOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    platform: str
    name: str
    metascore: int | None
    userscore: float | None
    critic_reviews_count: int | None
    user_reviews_count: int | None


class GameShort(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    cover_url: str | None
    developer: str | None
    genres: list[str]
    platforms: list[PlatformOut]

    @field_validator("genres", mode="before")
    @classmethod
    def _genre_names(cls, value):
        return [getattr(g, "name", g) for g in value]


class GameDetail(GameShort):
    url: str
    description: str | None
    video_url: str | None
    first_seen_at: datetime
    updated_at: datetime
    last_processed_at: datetime
    similar: list[GameShort] = []

    _utc = field_validator("first_seen_at", "updated_at", "last_processed_at")(as_utc)


class GamePageOut(BaseModel):
    items: list[GameShort]
    total: int
    page: int
    page_size: int


class PlatformOption(BaseModel):
    platform: str
    name: str
    games: int
