"""Way 2 of the transcript: the speech of the video recognised by a model through OpenRouter.

yt-dlp downloads the sound, ffmpeg cuts it into pieces that fit into one request, every piece
is sent to the transcription endpoint and the segments are put back on one time line.
"""

import base64
import logging
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

import requests

from app.config import settings
from app.transcripts.captions import Segment

log = logging.getLogger(__name__)

ENDPOINT = "https://openrouter.ai/api/v1/audio/transcriptions"


class SttError(Exception):
    pass


@dataclass
class SttResult:
    segments: list[Segment]
    language: str | None


class OpenRouterStt:
    def __init__(self, api_key: str, model: str, chunk_minutes: int, timeout: float, retries: int = 2) -> None:
        self._key = api_key
        self._model = model
        self._chunk_seconds = chunk_minutes * 60
        self._timeout = timeout
        self._retries = retries

    # ----------------------------------------------------------- the sound
    def probe(self, video_id: str) -> int:
        """The length of the video in seconds."""
        out = self._run([sys.executable, "-m", "yt_dlp", "--no-playlist", "--print", "duration", _url(video_id)])
        try:
            return int(float(out.strip().splitlines()[-1]))
        except (ValueError, IndexError) as exc:
            raise SttError(f"cannot get the length of the video: {out.strip()[:200]}") from exc

    def transcribe(self, video_id: str) -> SttResult:
        with tempfile.TemporaryDirectory(prefix="stt-") as tmp:
            folder = Path(tmp)
            self._run(
                [
                    sys.executable, "-m", "yt_dlp", "--no-playlist", "-f", "bestaudio",
                    "-o", str(folder / "audio.%(ext)s"), _url(video_id),
                ]
            )
            source = next(folder.glob("audio.*"), None)
            if source is None:
                raise SttError("the sound of the video was not downloaded")
            self._run(
                [
                    "ffmpeg", "-nostdin", "-loglevel", "error", "-i", str(source), "-vn", "-ac", "1", "-ar", "16000",
                    "-b:a", "32k", "-f", "segment", "-segment_time", str(self._chunk_seconds),
                    "-reset_timestamps", "1", str(folder / "chunk%03d.mp3"),
                ]
            )
            chunks = sorted(folder.glob("chunk*.mp3"))
            if not chunks:
                raise SttError("the sound could not be cut into pieces")

            segments: list[Segment] = []
            language = None
            for index, chunk in enumerate(chunks):
                part, language = self._recognise(chunk, index * self._chunk_seconds, language)
                segments.extend(part)
        if not segments:
            raise SttError("no speech was recognised")
        return SttResult(segments, language)

    @staticmethod
    def _run(command: list[str]) -> str:
        try:
            done = subprocess.run(command, capture_output=True, text=True, timeout=3600)
        except FileNotFoundError as exc:
            raise SttError(f"{command[0]} is not installed") from exc
        except subprocess.TimeoutExpired as exc:
            raise SttError(f"{Path(command[0]).name} took too long") from exc
        if done.returncode != 0:
            raise SttError(f"{Path(command[0]).name} failed: {(done.stderr or done.stdout).strip()[-300:]}")
        return done.stdout

    # ------------------------------------------------------- the recognition
    def _recognise(self, chunk: Path, offset: float, language: str | None) -> tuple[list[Segment], str | None]:
        body = {
            "model": self._model,
            "input_audio": {"data": base64.b64encode(chunk.read_bytes()).decode(), "format": "mp3"},
            "language": "en",
            "response_format": "verbose_json",
        }
        try:
            data = self._post(body)
        except SttError as exc:
            if "HTTP 400" not in str(exc):
                raise
            # the model cannot give the segments: the text of the piece with the time of its start
            body.pop("response_format")
            data = self._post(body)

        segments = []
        for item in data.get("segments") or []:
            text = " ".join(str(item.get("text", "")).split())
            if text:
                speaker = item.get("speaker_label") or item.get("speaker")
                segments.append(
                    Segment(offset + float(item.get("start", 0)), text, None if speaker is None else str(speaker))
                )
        if not segments:
            text = " ".join(str(data.get("text", "")).split())
            if text:
                segments.append(Segment(offset, text))
        return segments, data.get("language") or language or "en"

    def _post(self, body: dict) -> dict:
        headers = {"Authorization": f"Bearer {self._key}", "Content-Type": "application/json"}
        last: Exception | None = None
        for attempt in range(self._retries + 1):
            if attempt:
                time.sleep(3 * attempt)
            try:
                response = requests.post(ENDPOINT, json=body, headers=headers, timeout=self._timeout)
            except requests.RequestException as exc:
                last = SttError(f"OpenRouter: {exc}")
                continue
            if response.status_code == 200:
                return response.json()
            message = f"OpenRouter: HTTP {response.status_code} {response.text.strip()[:200]}"
            if response.status_code in (429, 500, 502, 503, 504, 524, 529):
                last = SttError(message)
                continue
            raise SttError(message)
        raise last  # type: ignore[misc]


def _url(video_id: str) -> str:
    return f"https://www.youtube.com/watch?v={video_id}"


def make_stt() -> OpenRouterStt | None:
    """The recogniser from the settings, or None without an OpenRouter key."""
    if not settings.openrouter_api_key:
        return None
    return OpenRouterStt(
        settings.openrouter_api_key, settings.stt_model, settings.stt_chunk_minutes, settings.stt_timeout_seconds
    )
