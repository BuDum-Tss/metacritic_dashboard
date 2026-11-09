"""The transcript of a video of a game, built on request.

The text comes from the subtitles of YouTube; without them the speech is recognised (OpenRouter).
A playlist is done video by video; what is already done is not touched, so a second request
finishes the rest.
"""

import logging
import threading
from collections.abc import Callable

from app.config import settings
from app.db import repository, transcript_repository, video_repository
from app.db.session import session_scope
from app.transcripts.captions import CaptionsUnavailable, Segment, fetch_captions
from app.transcripts.stt import SttError, make_stt
from app.videos.youtube import YouTubeError, make_youtube_client

log = logging.getLogger(__name__)

_running: set[tuple[int, str]] = set()
_lock = threading.Lock()


class AlreadyRunning(Exception):
    pass


class NoVideo(Exception):
    """The game has no video of this kind."""


def is_running(game_id: int, kind: str) -> bool:
    return (game_id, kind) in _running


def begin(game_id: int, kind: str) -> None:
    """Take the place of the only task of the game; AlreadyRunning when it is taken."""
    with _lock:
        if (game_id, kind) in _running:
            raise AlreadyRunning
        _running.add((game_id, kind))


def run_transcripts(
    game_id: int,
    kind: str,
    captions: Callable[[str], tuple[list[Segment], str]] | None = None,
    stt=None,
    youtube=None,
) -> None:
    """Do every video of the game that is not done yet. The place must be taken with `begin`; never raises."""
    try:
        captions = captions or fetch_captions
        stt = stt if stt is not None else make_stt()
        _run(game_id, kind, captions, stt, youtube)
    except Exception:
        log.exception("transcript of game %d (%s) failed", game_id, kind)
    finally:
        with _lock:
            _running.discard((game_id, kind))


def _videos(game_id: int, kind: str, youtube) -> list[tuple[str, str | None]]:
    """The videos to transcribe: all of the playlist, otherwise the one shown on the page."""
    with session_scope() as session:
        row = next((v for v in video_repository.list_videos(session, game_id) if v.kind == kind), None)
        if row is None:
            raise NoVideo
        shown = [(row.video_id, row.title)]
        playlist_id = row.playlist_id
    if not playlist_id:
        return shown
    youtube = youtube or make_youtube_client()
    if youtube is None:
        return shown
    try:
        found = youtube.playlist_videos(playlist_id, settings.transcript_max_playlist_videos)
    except YouTubeError as exc:
        log.warning("cannot read the playlist %s: %s", playlist_id, exc)
        return shown
    return found or shown


def _run(game_id: int, kind: str, captions, stt, youtube) -> None:
    videos = _videos(game_id, kind, youtube)
    with session_scope() as session:
        transcript_repository.sync_videos(session, game_id, kind, videos, repository.utcnow())
        todo = [(row.id, row.video_id) for row in transcript_repository.todo(session, game_id, kind)]
        for row_id, _ in todo:
            transcript_repository.set_status(session, row_id, "pending", repository.utcnow())

    spent_minutes = 0.0
    for row_id, video_id in todo:
        with session_scope() as session:
            transcript_repository.set_status(session, row_id, "running", repository.utcnow())
        try:
            segments, language, source, duration = _transcribe(video_id, captions, stt, spent_minutes)
        except _BudgetSpent:
            # the money for this request is used up: the video waits for the next one
            with session_scope() as session:
                transcript_repository.set_status(session, row_id, "pending", repository.utcnow())
            continue
        except Exception as exc:
            log.warning("transcript of %s failed: %s", video_id, exc)
            with session_scope() as session:
                transcript_repository.set_status(session, row_id, "failed", repository.utcnow(), str(exc)[:500])
            continue
        if source == "stt":
            spent_minutes += (duration or 0) / 60
        with session_scope() as session:
            transcript_repository.save_done(session, row_id, source, language, segments, duration, repository.utcnow())


class _BudgetSpent(Exception):
    pass


def _transcribe(video_id: str, captions, stt, spent_minutes: float):
    try:
        segments, language = captions(video_id)
        return segments, language, "captions", None
    except CaptionsUnavailable as exc:
        reason = str(exc)
    if stt is None:
        raise RuntimeError(f"no subtitles ({reason}); speech recognition is off: no OPENROUTER_API_KEY")

    try:
        seconds = stt.probe(video_id)
        if seconds / 60 > settings.stt_max_video_minutes:
            raise RuntimeError(
                f"no subtitles, and the video is too long for speech recognition "
                f"({seconds // 60} min, the limit is {settings.stt_max_video_minutes})"
            )
        if spent_minutes + seconds / 60 > settings.stt_budget_minutes:
            raise _BudgetSpent
        result = stt.transcribe(video_id)
    except SttError as exc:
        raise RuntimeError(f"no subtitles ({reason}); speech recognition failed: {exc}") from exc
    return result.segments, result.language, "stt", seconds
