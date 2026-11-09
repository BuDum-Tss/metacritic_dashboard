"""Way 1 of the transcript: the English subtitles of the video YouTube already has."""

import html
import logging
from dataclasses import dataclass

from youtube_transcript_api import YouTubeTranscriptApi

log = logging.getLogger(__name__)

LANGUAGES = ["en", "en-US", "en-GB"]


@dataclass
class Segment:
    start: float  # seconds from the start of the video
    text: str
    speaker: str | None = None


class CaptionsUnavailable(Exception):
    """The video has no usable subtitles, or YouTube refused to give them (it blocks many servers)."""


def _reason(exc: Exception) -> str:
    lines = str(exc).strip().splitlines()
    return f"{type(exc).__name__}: {lines[0]}" if lines else type(exc).__name__


def fetch_captions(video_id: str) -> tuple[list[Segment], str]:
    """The subtitles as segments and their language; the ones made by the author come first."""
    try:
        available = YouTubeTranscriptApi().list(video_id)
        try:
            transcript = available.find_manually_created_transcript(LANGUAGES)
        except Exception:
            transcript = available.find_generated_transcript(LANGUAGES)
        fetched = transcript.fetch()
    except Exception as exc:
        raise CaptionsUnavailable(_reason(exc)) from exc

    segments = []
    for snippet in fetched:
        text = " ".join(html.unescape(snippet.text).split())
        if text:
            segments.append(Segment(start=float(snippet.start), text=text))
    if not segments:
        raise CaptionsUnavailable("the subtitles are empty")
    return segments, transcript.language_code
