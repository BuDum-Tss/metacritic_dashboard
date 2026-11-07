"""The prompt version and the model's review-by-review analysis of a summary.

Summaries made before this migration were made by the first prompt, hence version 1; they are
built again once the current prompt is newer.

Revision ID: 0008
Revises: 0007
Create Date: 2026-11-07
"""
import sqlalchemy as sa
from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "review_summaries",
        sa.Column("prompt_version", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column("review_summaries", sa.Column("analysis", sa.JSON()))


def downgrade() -> None:
    op.drop_column("review_summaries", "analysis")
    op.drop_column("review_summaries", "prompt_version")
