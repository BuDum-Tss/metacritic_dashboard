"""Videos found on YouTube for the games.

One row per game and kind of video (let's play, review); the row also says when to search again.
The downgrade drops the table: the videos are found again by the search.

Revision ID: 0011
Revises: 0010
Create Date: 2026-11-09
"""
import sqlalchemy as sa
from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "game_videos",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("game_id", sa.Integer(), sa.ForeignKey("games.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("video_id", sa.String()),
        sa.Column("title", sa.String()),
        sa.Column("channel", sa.String()),
        sa.Column("views", sa.Integer()),
        sa.Column("playlist_id", sa.String()),
        sa.Column("checked_at", sa.DateTime(), nullable=False),
        sa.Column("next_check_at", sa.DateTime()),
        sa.UniqueConstraint("game_id", "kind"),
    )
    op.create_index("ix_game_videos_next_check_at", "game_videos", ["next_check_at"])


def downgrade() -> None:
    op.drop_index("ix_game_videos_next_check_at", table_name="game_videos")
    op.drop_table("game_videos")
