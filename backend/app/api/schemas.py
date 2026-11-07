from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, Field, field_validator


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
    pipeline: str
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


class RunGameOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    game_id: int | None
    slug: str
    title: str | None
    outcome: str
    details: dict[str, str] | None
    error: str | None


class PipelineStatus(BaseModel):
    running: bool
    enabled: bool  # the analysis is off without a model
    interval_hours: int
    budget: int  # games per run
    next_run_at: datetime | None
    current_run: SyncRunOut | None
    last_run: SyncRunOut | None

    _utc = field_validator("next_run_at")(as_utc)


class SyncStatus(BaseModel):
    crawl: PipelineStatus
    analysis: PipelineStatus


class PlatformOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    platform: str
    name: str
    metascore: int | None
    userscore: float | None
    critic_reviews_count: int | None
    user_reviews_count: int | None


class ScoreOut(BaseModel):
    """The single score of a game: the average over its platforms."""

    critics: int | None = None  # Metascore scale, whole numbers
    users: float | None = None  # Userscore scale, one decimal


class GameShort(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    cover_url: str | None
    developer: str | None
    genres: list[str]
    platforms: list[PlatformOut]
    score: ScoreOut = Field(default_factory=ScoreOut)  # set by the API from the platforms

    @field_validator("genres", mode="before")
    @classmethod
    def _genre_names(cls, value):
        return [getattr(g, "name", g) for g in value]


class ReviewOut(BaseModel):
    id: int
    author: str | None
    score: int | None
    date: str | None
    text: str
    url: str | None
    platform: str | None


class PointOut(BaseModel):
    id: int
    text: str
    review_ids: list[int]


class SummaryOut(BaseModel):
    generated_at: datetime
    sample_size: int
    total_reviews: int | None
    model: str
    likes: list[PointOut]
    dislikes: list[PointOut]
    reviews: list[ReviewOut]  # the reviews the points refer to, by id

    _utc = field_validator("generated_at")(as_utc)


class SummariesOut(BaseModel):
    critics: SummaryOut | None = None
    users: SummaryOut | None = None


class OverallOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    score: float | None
    verdict: str | None
    reviews_count: int | None
    positive: int | None
    mixed: int | None
    negative: int | None
    captured_at: datetime

    _utc = field_validator("captured_at")(as_utc)


class OverallsOut(BaseModel):
    critics: OverallOut | None = None
    users: OverallOut | None = None


class GameDetail(GameShort):
    url: str
    description: str | None
    video_url: str | None
    first_seen_at: datetime
    updated_at: datetime
    last_processed_at: datetime
    similar: list[GameShort] = []
    overall: OverallsOut = Field(default_factory=OverallsOut)
    summaries: SummariesOut = Field(default_factory=SummariesOut)

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
