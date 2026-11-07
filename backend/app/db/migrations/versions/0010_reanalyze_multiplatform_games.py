"""Games with several platforms are analyzed again with the reviews of every platform.

The reviews used to come from the top two platforms for critics and from one for players, and the
total was the number of the platform the game page shows. Now every platform counts, so the
summaries of the games with several platforms are outdated. Their last check is moved into the
past and the number of reviews it saw is set to -1, which never equals a real number: the queue
of the analysis takes these games in its next runs instead of waiting for a day.

Only the state of the analysis changes. The summaries stay until new ones replace them.
The downgrade does nothing: the earlier state is not kept.

Revision ID: 0010
Revises: 0009
Create Date: 2026-11-07
"""
from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE analysis_state
        SET checked_at = '1970-01-01 00:00:00', total_reviews = -1
        WHERE game_id IN (SELECT game_id FROM game_platforms GROUP BY game_id HAVING COUNT(*) > 1)
        """
    )


def downgrade() -> None:
    pass
