"""Storage of the conclusions about the videos."""

from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.db.models import VideoSummary, VideoTranscript


def get_summary(session: Session, game_id: int, video_id: str) -> VideoSummary | None:
    return session.scalar(select(VideoSummary).where(VideoSummary.game_id == game_id, VideoSummary.video_id == video_id))


def mark_running(session: Session, game_id: int, video_id: str, now: datetime) -> None:
    """A new request: the old text is kept until the new one is ready, so a failure loses nothing."""
    row = get_summary(session, game_id, video_id)
    if row is None:
        session.add(VideoSummary(game_id=game_id, video_id=video_id, status="running", updated_at=now))
    else:
        row.status, row.error, row.updated_at = "running", None, now


def save_done(session: Session, game_id: int, video_id: str, text: str, moments: list[dict], model: str, version: int, now: datetime) -> None:
    row = get_summary(session, game_id, video_id)
    row.status, row.error, row.updated_at = "done", None, now
    row.text, row.moments, row.model, row.prompt_version = text, moments, model, version


def save_failed(session: Session, game_id: int, video_id: str, error: str, now: datetime) -> None:
    row = get_summary(session, game_id, video_id)
    row.status, row.error, row.updated_at = "failed", error, now


def finished_transcript(session: Session, game_id: int, video_id: str) -> VideoTranscript | None:
    """The transcript of the video when it is ready, else None."""
    row = session.scalar(
        select(VideoTranscript).where(VideoTranscript.game_id == game_id, VideoTranscript.video_id == video_id)
    )
    return row if row is not None and row.status == "done" else None


def interrupt_running(session: Session, now: datetime) -> int:
    result = session.execute(
        update(VideoSummary).where(VideoSummary.status == "running").values(status="failed", error="interrupted", updated_at=now)
    )
    return result.rowcount


def videos_without_summary(session: Session, game_id: int, kind: str) -> list[str]:
    """Videos of the kind with a ready transcript and no ready summary (one that is being built is left alone)."""
    rows = session.execute(
        select(VideoTranscript.video_id, VideoSummary.status)
        .outerjoin(VideoSummary, (VideoSummary.game_id == VideoTranscript.game_id) & (VideoSummary.video_id == VideoTranscript.video_id))
        .where(VideoTranscript.game_id == game_id, VideoTranscript.kind == kind, VideoTranscript.status == "done")
        .order_by(VideoTranscript.position)
    ).all()
    return [video_id for video_id, status in rows if status not in ("done", "running")]


def pending(session: Session) -> list[tuple[int, str]]:
    """(game, video) of the queued summaries whose transcript is ready: made by the migration for transcripts that already existed."""
    rows = session.execute(
        select(VideoSummary.game_id, VideoSummary.video_id)
        .join(VideoTranscript, (VideoSummary.game_id == VideoTranscript.game_id) & (VideoSummary.video_id == VideoTranscript.video_id))
        .where(VideoSummary.status == "pending", VideoTranscript.status == "done")
        .order_by(VideoSummary.id)
    ).all()
    return [(game_id, video_id) for game_id, video_id in rows]


def summaries_of_game(session: Session, game_id: int) -> dict[str, str]:
    """video id -> status of its summary."""
    return {row.video_id: row.status for row in session.scalars(select(VideoSummary).where(VideoSummary.game_id == game_id))}
