from datetime import datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, Index, Integer, String, Table, Text, UniqueConstraint
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
    first_seen_at: Mapped[datetime] = mapped_column(DateTime)
    updated_at: Mapped[datetime] = mapped_column(DateTime)
    last_processed_at: Mapped[datetime] = mapped_column(DateTime, index=True)

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


class ReviewSummary(Base):
    """Append-only versions of review summaries; the latest per (game, source) is current."""

    __tablename__ = "review_summaries"
    __table_args__ = (Index("ix_summary_game_source_time", "game_id", "source", "generated_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    game_id: Mapped[int] = mapped_column(ForeignKey("games.id", ondelete="CASCADE"))
    source: Mapped[str] = mapped_column(String)  # "critics" | "users"
    likes: Mapped[str | None] = mapped_column(Text)
    dislikes: Mapped[str | None] = mapped_column(Text)
    reviews_hash: Mapped[str] = mapped_column(String)
    generated_at: Mapped[datetime] = mapped_column(DateTime)


class SyncRun(Base):
    __tablename__ = "sync_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
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
