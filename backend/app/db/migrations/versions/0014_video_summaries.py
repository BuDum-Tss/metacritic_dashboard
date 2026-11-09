"""Conclusions about the videos built from their transcripts.

One row per game and video. The downgrade drops the table: the conclusions are built again on request.

Revision ID: 0014
Revises: 0013
Create Date: 2026-11-09
"""
import sqlalchemy as sa
from alembic import op

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "video_summaries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("game_id", sa.Integer(), sa.ForeignKey("games.id", ondelete="CASCADE"), nullable=False),
        sa.Column("video_id", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="running"),
        sa.Column("text", sa.Text()),
        sa.Column("moments", sa.JSON()),
        sa.Column("model", sa.String()),
        sa.Column("prompt_version", sa.Integer()),
        sa.Column("error", sa.Text()),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("game_id", "video_id"),
    )


def downgrade() -> None:
    op.drop_table("video_summaries")
