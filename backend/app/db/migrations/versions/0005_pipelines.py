"""Two pipelines: the pipeline of a run and the state of the review analysis.

Runs made before this migration were all crawls, hence the default.

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-07
"""
import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "sync_runs",
        sa.Column("pipeline", sa.String(), nullable=False, server_default="crawl"),
    )
    op.create_table(
        "analysis_state",
        sa.Column("game_id", sa.Integer(), sa.ForeignKey("games.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("kind", sa.String(), primary_key=True),
        sa.Column("checked_at", sa.DateTime(), nullable=False),
        sa.Column("total_reviews", sa.Integer(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("analysis_state")
    op.drop_column("sync_runs", "pipeline")
