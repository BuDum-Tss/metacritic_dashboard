"""Way 1 of the transcript: the English subtitles of the video YouTube already has."""

import html
import logging
import re
from dataclasses import dataclass

from youtube_transcript_api import YouTubeTranscriptApi

log = logging.getLogger(__name__)

LANGUAGES = ["en", "en-US", "en-GB"]
SENTENCE_END = re.compile(r"[.!?…][\"')\]]*$")
SPEAKER_CHANGE = re.compile(r"\s*>{2,}\s*")  # ">>" in subtitles: the next person speaks
MAX_SENTENCE_CHARS = 240  # automatic subtitles often have no punctuation: such a run is cut here
MAX_SENTENCE_SECONDS = 25


@dataclass
class Segment:
    start: float  # seconds from the start of the video
    text: str
    speaker: str | None = None


class CaptionsUnavailable(Exception):
    """The video has no usable subtitles, or YouTube refused to give them (it blocks many servers)."""


REASONS = {
    "RequestBlocked": "YouTube blocked the request",
    "IpBlocked": "YouTube blocked the request",
    "TranscriptsDisabled": "the author turned the subtitles off",
    "NoTranscriptFound": "no English subtitles",
    "VideoUnavailable": "the video is unavailable",
}


def _reason(exc: Exception) -> str:
    return REASONS.get(type(exc).__name__, type(exc).__name__)


def merge_sentences(pieces: list[Segment]) -> list[Segment]:
    """Join the short pieces of subtitles (a line every second or two) into sentences.

    A sentence ends where a piece ends with . ! ? or ...; without punctuation it is cut when it
    gets too long in characters or in time, so a transcript stays readable either way. The marker
    ">>" of the subtitles means another person starts to speak: it ends the sentence and is dropped.
    """
    sentences: list[Segment] = []
    parts: list[str] = []
    start = 0.0

    def flush() -> None:
        nonlocal parts
        if parts:
            sentences.append(Segment(start, " ".join(parts)))
        parts = []

    for piece in pieces:
        for index, chunk in enumerate(SPEAKER_CHANGE.split(piece.text)):
            if index:
                flush()
            if not chunk:
                continue
            if not parts:
                start = piece.start
            elif len(" ".join(parts)) + len(chunk) > MAX_SENTENCE_CHARS or piece.start - start > MAX_SENTENCE_SECONDS:
                flush()
                start = piece.start
            parts.append(chunk)
            if SENTENCE_END.search(chunk):
                flush()
    flush()
    return sentences


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
    return merge_sentences(segments), transcript.language_code
