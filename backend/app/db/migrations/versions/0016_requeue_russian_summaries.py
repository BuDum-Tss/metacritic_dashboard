"""Build the summaries of the videos again, in English.

The first version of the request wrote them in Russian. Rows made by it go back to the queue; the old
text stays until the new one is ready. The downgrade does nothing.

Revision ID: 0016
Revises: 0015
Create Date: 2026-11-09
"""
import sqlalchemy as sa
from alembic import op

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None


def requeue_old(connection) -> int:
    """Put the summaries of prompt version 1 back to pending; returns how many."""
    result = connection.execute(
        sa.text("UPDATE video_summaries SET status = 'pending' WHERE status = 'done' AND prompt_version = 1")
    )
    return result.rowcount


def upgrade() -> None:
    requeue_old(op.get_bind())


def downgrade() -> None:
    pass
