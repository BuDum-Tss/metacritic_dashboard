"""The schedule of revisits: games.next_check_at.

Existing games get the epoch as their next check, so they are the most overdue and are visited
first. The column is added without a table rebuild: SQLite would delete child rows while
dropping the old games table with foreign keys on.

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-07
"""
import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "games",
        sa.Column("next_check_at", sa.DateTime(), nullable=False, server_default="1970-01-01 00:00:00"),
    )
    op.create_index("ix_games_next_check_at", "games", ["next_check_at"])


def downgrade() -> None:
    op.drop_index("ix_games_next_check_at", table_name="games")
    op.drop_column("games", "next_check_at")
