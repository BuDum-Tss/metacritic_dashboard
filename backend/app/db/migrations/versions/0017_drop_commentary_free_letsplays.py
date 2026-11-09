"""Drop the let's plays without commentary and the game movies found earlier.

A video without the voice of the player says nothing to summarise. The rows of the found video, its
transcripts and summaries are removed; the game is searched again as a game without a let's play.
The downgrade does nothing: the videos are found again by the search.

Revision ID: 0017
Revises: 0016
Create Date: 2026-11-09
"""
import sqlalchemy as sa
from alembic import op

from app.videos.finder import NO_COMMENTARY

revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None


def drop_commentary_free(connection) -> int:
    """Remove the let's plays whose title says "no commentary" or "game movie"; returns how many games were affected."""
    rows = connection.execute(
        sa.text("SELECT game_id, title FROM game_videos WHERE kind = 'letsplay' AND title IS NOT NULL")
    ).all()
    games = {game_id for game_id, title in rows if NO_COMMENTARY.search(title.lower().replace("\u2019", "'"))}
    for game_id in games:
        arg = {"game": game_id}
        connection.execute(
            sa.text(
                "DELETE FROM video_summaries WHERE game_id = :game AND video_id IN ("
                "SELECT video_id FROM video_transcripts WHERE game_id = :game AND kind = 'letsplay' "
                "UNION SELECT video_id FROM game_videos WHERE game_id = :game AND kind = 'letsplay')"
            ),
            arg,
        )
        connection.execute(sa.text("DELETE FROM video_transcripts WHERE game_id = :game AND kind = 'letsplay'"), arg)
        connection.execute(sa.text("DELETE FROM game_videos WHERE game_id = :game AND kind = 'letsplay'"), arg)
    return len(games)


def upgrade() -> None:
    drop_commentary_free(op.get_bind())


def downgrade() -> None:
    pass
