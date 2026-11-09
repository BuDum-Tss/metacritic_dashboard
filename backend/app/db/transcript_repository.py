"""Storage of the transcripts of the videos."""

from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.db.models import VideoTranscript
from app.transcripts.captions import Segment


def sync_videos(session: Session, game_id: int, kind: str, videos: list[tuple[str, str | None]], now: datetime) -> None:
    """Make sure every video of the playlist has a row: new ones are pending, known ones keep their text."""
    rows = {row.video_id: row for row in session.scalars(select(VideoTranscript).where(VideoTranscript.game_id == game_id))}
    for position, (video_id, title) in enumerate(videos):
        row = rows.get(video_id)
        if row is None:
            session.add(
                VideoTranscript(
                    game_id=game_id, kind=kind, video_id=video_id, position=position, title=title,
                    status="pending", updated_at=now,
                )
            )
        else:
            row.kind, row.position = kind, position
            row.title = title or row.title


def todo(session: Session, game_id: int, kind: str) -> list[VideoTranscript]:
    """The videos still to do, in the order of the playlist: everything that is not done."""
    return list(
        session.scalars(
            select(VideoTranscript)
            .where(VideoTranscript.game_id == game_id, VideoTranscript.kind == kind, VideoTranscript.status != "done")
            .order_by(VideoTranscript.position)
        )
    )


def set_status(session: Session, row_id: int, status: str, now: datetime, error: str | None = None) -> None:
    row = session.get(VideoTranscript, row_id)
    row.status, row.error, row.updated_at = status, error, now


def save_done(
    session: Session, row_id: int, source: str, language: str | None, segments: list[Segment],
    duration: int | None, now: datetime,
) -> None:
    row = session.get(VideoTranscript, row_id)
    row.status, row.error, row.updated_at = "done", None, now
    row.source, row.language = source, language
    row.duration_seconds = duration if duration is not None else int(segments[-1].start) if segments else None
    row.segments = [{"start": s.start, "text": s.text, "speaker": s.speaker} for s in segments]


def list_transcripts(session: Session, game_id: int, kind: str) -> list[VideoTranscript]:
    return list(
        session.scalars(
            select(VideoTranscript)
            .where(VideoTranscript.game_id == game_id, VideoTranscript.kind == kind)
            .order_by(VideoTranscript.position)
        )
    )


def get_transcript(session: Session, game_id: int, video_id: str) -> VideoTranscript | None:
    return session.scalar(
        select(VideoTranscript).where(VideoTranscript.game_id == game_id, VideoTranscript.video_id == video_id)
    )


def interrupt_running(session: Session, now: datetime) -> int:
    """After a restart nothing is running: what was running was cut short and is done again on request."""
    result = session.execute(
        update(VideoTranscript)
        .where(VideoTranscript.status == "running")
        .values(status="failed", error="interrupted", updated_at=now)
    )
    return result.rowcount
