"""Queue the summaries of the transcripts that already exist.

Every finished transcript without a summary gets a "pending" row in video_summaries; the service
builds them in the background after it starts (when the model is configured).
The downgrade removes the rows that were never built.

Revision ID: 0015
Revises: 0014
Create Date: 2026-11-09
"""
import sqlalchemy as sa
from alembic import op

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


def queue_missing(connection) -> int:
    """Add the pending rows; returns how many were added."""
    done = connection.execute(
        sa.text(
            "INSERT INTO video_summaries (game_id, video_id, status, updated_at) "
            "SELECT t.game_id, t.video_id, 'pending', CURRENT_TIMESTAMP FROM video_transcripts t "
            "WHERE t.status = 'done' AND NOT EXISTS ("
            "SELECT 1 FROM video_summaries s WHERE s.game_id = t.game_id AND s.video_id = t.video_id)"
        )
    )
    return done.rowcount


def upgrade() -> None:
    queue_missing(op.get_bind())


def downgrade() -> None:
    op.execute("DELETE FROM video_summaries WHERE status = 'pending'")
