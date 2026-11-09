from datetime import date, datetime

from sqlalchemy import (
    JSON,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Table,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


game_genres = Table(
    "game_genres",
    Base.metadata,
    Column("game_id", ForeignKey("games.id", ondelete="CASCADE"), primary_key=True),
    Column("genre_id", ForeignKey("genres.id", ondelete="CASCADE"), primary_key=True),
)


class Game(Base):
    __tablename__ = "games"
    __table_args__ = (UniqueConstraint("source", "slug"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    source: Mapped[str] = mapped_column(String)
    slug: Mapped[str] = mapped_column(String)
    url: Mapped[str] = mapped_column(String)
    title: Mapped[str] = mapped_column(String)
    cover_url: Mapped[str | None] = mapped_column(String)
    developer: Mapped[str | None] = mapped_column(String)
    description: Mapped[str | None] = mapped_column(Text)
    video_url: Mapped[str | None] = mapped_column(String)
    content_hash: Mapped[str | None] = mapped_column(String)
    release_date: Mapped[date | None] = mapped_column(Date, index=True)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime)
    updated_at: Mapped[datetime] = mapped_column(DateTime)
    last_processed_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    next_check_at: Mapped[datetime] = mapped_column(DateTime, index=True)  # when to visit the game again

    genres: Mapped[list["Genre"]] = relationship(secondary=game_genres, order_by="Genre.name")
    platforms: Mapped[list["GamePlatform"]] = relationship(
        back_populates="game", cascade="all, delete-orphan", order_by="GamePlatform.platform"
    )


class Genre(Base):
    __tablename__ = "genres"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String, unique=True)


class GamePlatform(Base):
    """Current metrics of a game on a platform."""

    __tablename__ = "game_platforms"

    game_id: Mapped[int] = mapped_column(ForeignKey("games.id", ondelete="CASCADE"), primary_key=True)
    platform: Mapped[str] = mapped_column(String, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String)
    metascore: Mapped[int | None] = mapped_column(Integer)
    userscore: Mapped[float | None] = mapped_column(Float)
    critic_reviews_count: Mapped[int | None] = mapped_column(Integer)
    user_reviews_count: Mapped[int | None] = mapped_column(Integer)
    updated_at: Mapped[datetime] = mapped_column(DateTime)

    game: Mapped[Game] = relationship(back_populates="platforms")


class GamePlatformHistory(Base):
    """Append-only metric snapshots, one per platform on every crawl."""

    __tablename__ = "game_platform_history"
    __table_args__ = (Index("ix_history_game_platform_time", "game_id", "platform", "captured_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    game_id: Mapped[int] = mapped_column(ForeignKey("games.id", ondelete="CASCADE"))
    platform: Mapped[str] = mapped_column(String)
    metascore: Mapped[int | None] = mapped_column(Integer)
    userscore: Mapped[float | None] = mapped_column(Float)
    critic_reviews_count: Mapped[int | None] = mapped_column(Integer)
    user_reviews_count: Mapped[int | None] = mapped_column(Integer)
    captured_at: Mapped[datetime] = mapped_column(DateTime)


class GameOverallScore(Base):
    """Append-only overall scores of critics/users as shown at the top of the game page."""

    __tablename__ = "game_overall_scores"
    __table_args__ = (Index("ix_overall_game_source_time", "game_id", "source", "captured_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    game_id: Mapped[int] = mapped_column(ForeignKey("games.id", ondelete="CASCADE"))
    source: Mapped[str] = mapped_column(String)  # "critics" | "users"
    score: Mapped[float | None] = mapped_column(Float)
    verdict: Mapped[str | None] = mapped_column(String)
    reviews_count: Mapped[int | None] = mapped_column(Integer)
    positive: Mapped[int | None] = mapped_column(Integer)
    mixed: Mapped[int | None] = mapped_column(Integer)
    negative: Mapped[int | None] = mapped_column(Integer)
    captured_at: Mapped[datetime] = mapped_column(DateTime)


class Review(Base):
    """A review from the sample a summary was built on. Reused by later summaries."""

    __tablename__ = "reviews"
    __table_args__ = (UniqueConstraint("game_id", "source", "external_key"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    game_id: Mapped[int] = mapped_column(ForeignKey("games.id", ondelete="CASCADE"))
    source: Mapped[str] = mapped_column(String)  # "critics" | "users"
    external_key: Mapped[str] = mapped_column(String)
    platform: Mapped[str | None] = mapped_column(String)
    author: Mapped[str | None] = mapped_column(String)
    score: Mapped[int | None] = mapped_column(Integer)
    reviewed_at: Mapped[str | None] = mapped_column(String)
    text: Mapped[str] = mapped_column(Text)
    url: Mapped[str | None] = mapped_column(String)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime)


summary_point_reviews = Table(
    "summary_point_reviews",
    Base.metadata,
    Column("point_id", ForeignKey("summary_points.id", ondelete="CASCADE"), primary_key=True),
    Column("review_id", ForeignKey("reviews.id", ondelete="CASCADE"), primary_key=True),
)


summary_reviews = Table(
    "summary_reviews",
    Base.metadata,
    Column("summary_id", ForeignKey("review_summaries.id", ondelete="CASCADE"), primary_key=True),
    Column("review_id", ForeignKey("reviews.id", ondelete="CASCADE"), primary_key=True),
)


class ReviewSummary(Base):
    """Append-only versions of review summaries; the latest per (game, source) is current."""

    __tablename__ = "review_summaries"
    __table_args__ = (Index("ix_summary_game_source_time", "game_id", "source", "generated_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    game_id: Mapped[int] = mapped_column(ForeignKey("games.id", ondelete="CASCADE"))
    source: Mapped[str] = mapped_column(String)  # "critics" | "users"
    reviews_hash: Mapped[str] = mapped_column(String)
    sample_size: Mapped[int] = mapped_column(Integer)
    total_reviews: Mapped[int | None] = mapped_column(Integer)
    model: Mapped[str] = mapped_column(String)
    prompt_version: Mapped[int] = mapped_column(Integer)  # the prompt that made it; older ones are redone
    analysis: Mapped[list | None] = mapped_column(JSON)  # the model's verdict on every review
    generated_at: Mapped[datetime] = mapped_column(DateTime)

    points: Mapped[list["SummaryPoint"]] = relationship(
        back_populates="summary", cascade="all, delete-orphan", order_by="SummaryPoint.position"
    )
    reviews: Mapped[list[Review]] = relationship(secondary=summary_reviews, order_by="Review.id")


class SummaryPoint(Base):
    __tablename__ = "summary_points"

    id: Mapped[int] = mapped_column(primary_key=True)
    summary_id: Mapped[int] = mapped_column(ForeignKey("review_summaries.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String)  # "like" | "dislike"
    position: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)

    summary: Mapped[ReviewSummary] = relationship(back_populates="points")
    reviews: Mapped[list[Review]] = relationship(secondary=summary_point_reviews, order_by="Review.id")


class AnalysisState(Base):
    """When the reviews of a game were last checked and how many there were: the analysis
    does not come back to a game until that number changes."""

    __tablename__ = "analysis_state"

    game_id: Mapped[int] = mapped_column(ForeignKey("games.id", ondelete="CASCADE"), primary_key=True)
    kind: Mapped[str] = mapped_column(String, primary_key=True)  # "critics" | "users"
    checked_at: Mapped[datetime] = mapped_column(DateTime)
    total_reviews: Mapped[int] = mapped_column(Integer)


class GameVideo(Base):
    """The video found on YouTube for a game: one row per kind ("letsplay" | "review").

    video_id is the video shown on the page (the most popular one, or the first of the playlist
    of a multi-part let's play); it is NULL when nothing was found. next_check_at NULL: never again.
    """

    __tablename__ = "game_videos"
    __table_args__ = (UniqueConstraint("game_id", "kind"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    game_id: Mapped[int] = mapped_column(ForeignKey("games.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String)
    video_id: Mapped[str | None] = mapped_column(String)
    title: Mapped[str | None] = mapped_column(String)
    channel: Mapped[str | None] = mapped_column(String)
    views: Mapped[int | None] = mapped_column(Integer)
    playlist_id: Mapped[str | None] = mapped_column(String)
    checked_at: Mapped[datetime] = mapped_column(DateTime)
    next_check_at: Mapped[datetime | None] = mapped_column(DateTime, index=True)


class SyncRun(Base):
    __tablename__ = "sync_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    pipeline: Mapped[str] = mapped_column(String)  # "crawl" | "analysis" | "videos"
    trigger: Mapped[str] = mapped_column(String)  # "schedule" | "manual"
    status: Mapped[str] = mapped_column(String)  # "running" | "success" | "failed"
    source: Mapped[str] = mapped_column(String)
    batch_index: Mapped[int] = mapped_column(Integer)
    started_at: Mapped[datetime] = mapped_column(DateTime)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)
    games_found: Mapped[int | None] = mapped_column(Integer)
    games_processed: Mapped[int | None] = mapped_column(Integer)
    games_failed: Mapped[int | None] = mapped_column(Integer)
    error: Mapped[str | None] = mapped_column(Text)


class RunGame(Base):
    """A game a pipeline run worked on, with the outcome. Written as the run goes."""

    __tablename__ = "run_games"

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("sync_runs.id", ondelete="CASCADE"), index=True)
    game_id: Mapped[int | None] = mapped_column(ForeignKey("games.id", ondelete="SET NULL"))
    slug: Mapped[str] = mapped_column(String)
    title: Mapped[str | None] = mapped_column(String)
    outcome: Mapped[str] = mapped_column(String)
    details: Mapped[dict | None] = mapped_column(JSON)
    error: Mapped[str | None] = mapped_column(Text)
