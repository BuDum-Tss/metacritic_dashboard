"""Transcripts of the videos of a game: the state, and the request to build them."""

from typing import Literal

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query

from app.api.schemas import SegmentOut, TranscriptVideoOut, TranscriptsOut
from app.config import settings
from app.db import transcript_repository, video_repository
from app.db.session import session_scope
from app.services import transcripts as service

router = APIRouter(prefix="/api/games", tags=["transcripts"])

Kind = Literal["letsplay", "review"]


@router.get("/{game_id}/transcripts/{kind}", response_model=TranscriptsOut)
def get_transcripts(game_id: int, kind: Kind, video_id: str | None = Query(None, max_length=32)) -> TranscriptsOut:
    """The videos of the kind with their state. The text is given only for `video_id`: it is long."""
    with session_scope() as session:
        rows = transcript_repository.list_transcripts(session, game_id, kind)
        videos = [
            TranscriptVideoOut(
                video_id=row.video_id, title=row.title, position=row.position, status=row.status,
                source=row.source, language=row.language, duration_seconds=row.duration_seconds, error=row.error,
            )
            for row in rows
        ]
        segments = None
        chosen = next((row for row in rows if row.video_id == video_id), None)
        if chosen is not None and chosen.status == "done":
            segments = [SegmentOut(**item) for item in chosen.segments or []]
        return TranscriptsOut(
            kind=kind,
            running=service.is_running(game_id, kind),
            stt_enabled=bool(settings.openrouter_api_key),
            videos=videos,
            segments=segments,
        )


@router.post("/{game_id}/transcripts/{kind}", status_code=202)
def request_transcripts(game_id: int, kind: Kind, background: BackgroundTasks) -> dict[str, str]:
    """Build the transcript of the videos not done yet; in the background."""
    with session_scope() as session:
        if not any(row.kind == kind for row in video_repository.list_videos(session, game_id)):
            raise HTTPException(status_code=404, detail="The game has no video of this kind")
    try:
        service.begin(game_id, kind)
    except service.AlreadyRunning:
        raise HTTPException(status_code=409, detail="The transcript is already being built") from None
    background.add_task(service.run_transcripts, game_id, kind)
    return {"status": "started"}
