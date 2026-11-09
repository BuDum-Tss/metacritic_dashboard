"""Transcripts of the videos of the games.

One row per game and video; the text itself is a JSON list of phrases with their time.
The downgrade drops the table: the transcripts are built again on request.

Revision ID: 0012
Revises: 0011
Create Date: 2026-11-09
"""
import sqlalchemy as sa
from alembic import op

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "video_transcripts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("game_id", sa.Integer(), sa.ForeignKey("games.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("video_id", sa.String(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("title", sa.String()),
        sa.Column("status", sa.String(), nullable=False, server_default="pending"),
        sa.Column("source", sa.String()),
        sa.Column("language", sa.String()),
        sa.Column("duration_seconds", sa.Integer()),
        sa.Column("segments", sa.JSON()),
        sa.Column("error", sa.Text()),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("game_id", "video_id"),
    )


def downgrade() -> None:
    op.drop_table("video_transcripts")
