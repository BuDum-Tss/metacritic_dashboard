"""The release date of a game: games.release_date.

Existing games get it on their next visit. The column is added without a table rebuild:
SQLite would delete child rows while dropping the old games table with foreign keys on.

Revision ID: 0007
Revises: 0006
Create Date: 2026-11-07
"""
import sqlalchemy as sa
from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("games", sa.Column("release_date", sa.Date()))
    op.create_index("ix_games_release_date", "games", ["release_date"])


def downgrade() -> None:
    op.drop_index("ix_games_release_date", table_name="games")
    op.drop_column("games", "release_date")
