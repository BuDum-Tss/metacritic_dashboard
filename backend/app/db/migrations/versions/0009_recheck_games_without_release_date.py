"""Games without a release date are due for a visit now.

The release date is read from the game page, but the games visited before it was collected would
get their date only at their next scheduled visit, a day later. Marking them due fills the field
(and the dashboard charts that need it) in the next crawl runs. Only the schedule changes: the
data of the games is not touched.

Not reversible in a useful way: the earlier schedule is not kept, and the downgrade does nothing.

Revision ID: 0009
Revises: 0008
Create Date: 2026-11-07
"""
from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("UPDATE games SET next_check_at = '1970-01-01 00:00:00' WHERE release_date IS NULL")


def downgrade() -> None:
    pass
