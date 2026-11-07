"""The games every pipeline run worked on, with the outcome.

Runs made before this migration have no games in the journal.

Revision ID: 0006
Revises: 0005
Create Date: 2026-11-07
"""
import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "run_games",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("run_id", sa.Integer(), sa.ForeignKey("sync_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("game_id", sa.Integer(), sa.ForeignKey("games.id", ondelete="SET NULL")),
        sa.Column("slug", sa.String(), nullable=False),
        sa.Column("title", sa.String()),
        sa.Column("outcome", sa.String(), nullable=False),
        sa.Column("details", sa.JSON()),
        sa.Column("error", sa.Text()),
    )
    op.create_index("ix_run_games_run_id", "run_games", ["run_id"])


def downgrade() -> None:
    op.drop_index("ix_run_games_run_id", table_name="run_games")
    op.drop_table("run_games")
