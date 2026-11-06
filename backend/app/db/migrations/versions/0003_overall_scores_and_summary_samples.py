"""Overall scores of games and the full review sample of each summary.

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-07
"""
import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "game_overall_scores",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("game_id", sa.Integer(), sa.ForeignKey("games.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("score", sa.Float()),
        sa.Column("verdict", sa.String()),
        sa.Column("reviews_count", sa.Integer()),
        sa.Column("positive", sa.Integer()),
        sa.Column("mixed", sa.Integer()),
        sa.Column("negative", sa.Integer()),
        sa.Column("captured_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_overall_game_source_time", "game_overall_scores", ["game_id", "source", "captured_at"])
    op.create_table(
        "summary_reviews",
        sa.Column(
            "summary_id", sa.Integer(), sa.ForeignKey("review_summaries.id", ondelete="CASCADE"), primary_key=True
        ),
        sa.Column("review_id", sa.Integer(), sa.ForeignKey("reviews.id", ondelete="CASCADE"), primary_key=True),
    )


def downgrade() -> None:
    op.drop_table("summary_reviews")
    op.drop_index("ix_overall_game_source_time", table_name="game_overall_scores")
    op.drop_table("game_overall_scores")
