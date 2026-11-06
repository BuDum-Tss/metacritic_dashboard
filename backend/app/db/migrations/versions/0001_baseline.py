"""Baseline: the schema of the first deployment (before review summaries).

Revision ID: 0001
Revises:
Create Date: 2026-11-07
"""
import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "games",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("slug", sa.String(), nullable=False),
        sa.Column("url", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("cover_url", sa.String()),
        sa.Column("developer", sa.String()),
        sa.Column("description", sa.Text()),
        sa.Column("video_url", sa.String()),
        sa.Column("content_hash", sa.String()),
        sa.Column("first_seen_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("last_processed_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("source", "slug"),
    )
    op.create_index("ix_games_last_processed_at", "games", ["last_processed_at"])

    op.create_table(
        "genres",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False, unique=True),
    )
    op.create_table(
        "game_genres",
        sa.Column("game_id", sa.Integer(), sa.ForeignKey("games.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("genre_id", sa.Integer(), sa.ForeignKey("genres.id", ondelete="CASCADE"), primary_key=True),
    )
    op.create_table(
        "game_platforms",
        sa.Column("game_id", sa.Integer(), sa.ForeignKey("games.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("platform", sa.String(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("metascore", sa.Integer()),
        sa.Column("userscore", sa.Float()),
        sa.Column("critic_reviews_count", sa.Integer()),
        sa.Column("user_reviews_count", sa.Integer()),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_game_platforms_platform", "game_platforms", ["platform"])

    op.create_table(
        "game_platform_history",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("game_id", sa.Integer(), sa.ForeignKey("games.id", ondelete="CASCADE"), nullable=False),
        sa.Column("platform", sa.String(), nullable=False),
        sa.Column("metascore", sa.Integer()),
        sa.Column("userscore", sa.Float()),
        sa.Column("critic_reviews_count", sa.Integer()),
        sa.Column("user_reviews_count", sa.Integer()),
        sa.Column("captured_at", sa.DateTime(), nullable=False),
    )
    op.create_index(
        "ix_history_game_platform_time", "game_platform_history", ["game_id", "platform", "captured_at"]
    )

    op.create_table(
        "review_summaries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("game_id", sa.Integer(), sa.ForeignKey("games.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("likes", sa.Text()),
        sa.Column("dislikes", sa.Text()),
        sa.Column("reviews_hash", sa.String(), nullable=False),
        sa.Column("generated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_summary_game_source_time", "review_summaries", ["game_id", "source", "generated_at"])

    op.create_table(
        "sync_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("trigger", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("batch_index", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("finished_at", sa.DateTime()),
        sa.Column("games_found", sa.Integer()),
        sa.Column("games_processed", sa.Integer()),
        sa.Column("games_failed", sa.Integer()),
        sa.Column("error", sa.Text()),
    )


def downgrade() -> None:
    for table in (
        "sync_runs",
        "review_summaries",
        "game_platform_history",
        "game_platforms",
        "game_genres",
        "genres",
        "games",
    ):
        op.drop_table(table)
