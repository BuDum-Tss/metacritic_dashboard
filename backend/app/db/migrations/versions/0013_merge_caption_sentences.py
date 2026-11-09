"""Join the subtitles already stored as one line per second or two into sentences.

The transcripts made before the subtitles were joined (for example the one of Zelda) keep their
text and time but get the same sentences as the new ones, and lose the ">>" speaker markers.
The downgrade does nothing: the short lines cannot be restored.

Revision ID: 0013
Revises: 0012
Create Date: 2026-11-09
"""
import json

import sqlalchemy as sa
from alembic import op

from app.transcripts.captions import Segment, merge_sentences

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def merge_stored(connection) -> int:
    """Merge the segments of every transcript made from subtitles; returns how many were changed."""
    rows = connection.execute(
        sa.text("SELECT id, segments FROM video_transcripts WHERE source = 'captions' AND segments IS NOT NULL")
    ).all()
    changed = 0
    for row_id, raw in rows:
        stored = json.loads(raw) if isinstance(raw, str) else raw
        merged = merge_sentences([Segment(item["start"], item["text"]) for item in stored])
        new = [{"start": s.start, "text": s.text, "speaker": s.speaker} for s in merged]
        if new != stored:
            connection.execute(
                sa.text("UPDATE video_transcripts SET segments = :segments WHERE id = :id"),
                {"segments": json.dumps(new), "id": row_id},
            )
            changed += 1
    return changed


def upgrade() -> None:
    merge_stored(op.get_bind())


def downgrade() -> None:
    pass
