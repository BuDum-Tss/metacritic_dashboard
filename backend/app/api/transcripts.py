"""Transcripts of the videos of a game: the state, and the request to build them."""

from typing import Literal

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query

from app.api.schemas import MomentOut, SegmentOut, TranscriptVideoOut, TranscriptsOut, VideoSummaryOut
from app.config import settings
from app.db import transcript_repository, video_repository, video_summary_repository
from app.db.session import session_scope
from app.services import transcripts as service
from app.services import video_summary

router = APIRouter(prefix="/api/games", tags=["transcripts"])

Kind = Literal["letsplay", "review"]


@router.get("/{game_id}/transcripts/{kind}", response_model=TranscriptsOut)
def get_transcripts(game_id: int, kind: Kind, video_id: str | None = Query(None, max_length=32)) -> TranscriptsOut:
    """The videos of the kind with their state. The text is given only for `video_id`: it is long."""
    with session_scope() as session:
        rows = transcript_repository.list_transcripts(session, game_id, kind)
        summaries = video_summary_repository.summaries_of_game(session, game_id)
        videos = [
            TranscriptVideoOut(
                video_id=row.video_id, title=row.title, position=row.position, status=row.status,
                source=row.source, language=row.language, duration_seconds=row.duration_seconds, error=row.error,
                summary_status=summaries.get(row.video_id, "none"),
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
            llm_enabled=bool(settings.llm_api_key),
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


# ------------------------------------------------------------------ the conclusion about a video
@router.get("/{game_id}/summaries/{video_id}", response_model=VideoSummaryOut)
def get_video_summary(game_id: int, video_id: str) -> VideoSummaryOut:
    with session_scope() as session:
        row = video_summary_repository.get_summary(session, game_id, video_id)
        return VideoSummaryOut(
            video_id=video_id,
            # queued by the migration, but nobody will build it without a model
            status=("none" if row.status == "pending" and not settings.llm_api_key else row.status) if row else "none",
            running=video_summary.is_running(game_id, video_id),
            llm_enabled=bool(settings.llm_api_key),
            text=row.text if row else None,
            moments=[MomentOut(**item) for item in (row.moments or [])] if row else [],
            error=row.error if row else None,
            model=row.model if row else None,
            updated_at=row.updated_at if row else None,
        )


@router.post("/{game_id}/summaries/{video_id}", status_code=202)
def request_video_summary(game_id: int, video_id: str, background: BackgroundTasks) -> dict[str, str]:
    """Build or rebuild the conclusion about a video whose transcript is ready; in the background."""
    with session_scope() as session:
        if transcript_repository.get_transcript(session, game_id, video_id) is None:
            raise HTTPException(status_code=404, detail="The video has no transcript")
    try:
        video_summary.start(game_id, video_id)
    except video_summary.ModelOff:
        raise HTTPException(status_code=400, detail="The model is not configured (no LLM_API_KEY)") from None
    except video_summary.NoTranscript:
        raise HTTPException(status_code=409, detail="The transcript of the video is not ready") from None
    except video_summary.AlreadyRunning:
        raise HTTPException(status_code=409, detail="The summary is already being built") from None
    background.add_task(video_summary.run_video_summary, game_id, video_id)
    return {"status": "started"}
