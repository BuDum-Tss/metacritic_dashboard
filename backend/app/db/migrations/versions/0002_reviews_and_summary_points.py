"""Review sample storage and structured summaries.

review_summaries gets sample_size, total_reviews and model and loses the likes/dislikes text
columns (the points live in summary_points now). The old table never held data, so it is
recreated instead of altered.

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-07
"""
import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_index("ix_summary_game_source_time", table_name="review_summaries")
    op.drop_table("review_summaries")

    op.create_table(
        "reviews",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("game_id", sa.Integer(), sa.ForeignKey("games.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("external_key", sa.String(), nullable=False),
        sa.Column("platform", sa.String()),
        sa.Column("author", sa.String()),
        sa.Column("score", sa.Integer()),
        sa.Column("reviewed_at", sa.String()),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("url", sa.String()),
        sa.Column("first_seen_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("game_id", "source", "external_key"),
    )
    op.create_table(
        "review_summaries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("game_id", sa.Integer(), sa.ForeignKey("games.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("reviews_hash", sa.String(), nullable=False),
        sa.Column("sample_size", sa.Integer(), nullable=False),
        sa.Column("total_reviews", sa.Integer()),
        sa.Column("model", sa.String(), nullable=False),
        sa.Column("generated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_summary_game_source_time", "review_summaries", ["game_id", "source", "generated_at"])
    op.create_table(
        "summary_points",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "summary_id", sa.Integer(), sa.ForeignKey("review_summaries.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
    )
    op.create_table(
        "summary_point_reviews",
        sa.Column(
            "point_id", sa.Integer(), sa.ForeignKey("summary_points.id", ondelete="CASCADE"), primary_key=True
        ),
        sa.Column("review_id", sa.Integer(), sa.ForeignKey("reviews.id", ondelete="CASCADE"), primary_key=True),
    )


def downgrade() -> None:
    op.drop_table("summary_point_reviews")
    op.drop_table("summary_points")
    op.drop_index("ix_summary_game_source_time", table_name="review_summaries")
    op.drop_table("review_summaries")
    op.drop_table("reviews")

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
