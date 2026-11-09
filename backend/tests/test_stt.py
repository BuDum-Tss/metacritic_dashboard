"""The speech recognition through OpenRouter: the request and how the answer is put on the time line."""

import base64

import pytest

from app.transcripts import stt as stt_module
from app.transcripts.stt import OpenRouterStt, SttError


class Response:
    def __init__(self, status, body=None, text=""):
        self.status_code, self._body, self.text = status, body or {}, text

    def json(self):
        return self._body


@pytest.fixture
def recogniser(tmp_path, monkeypatch):
    monkeypatch.setattr(stt_module.time, "sleep", lambda _: None)
    chunk = tmp_path / "chunk000.mp3"
    chunk.write_bytes(b"sound")
    return OpenRouterStt("key", "openai/whisper-large-v3", 10, 5.0), chunk


def test_segments_are_moved_to_the_start_of_their_piece(recogniser, monkeypatch):
    stt, chunk = recogniser
    sent = []

    def post(url, json, headers, timeout):
        sent.append((url, json, headers))
        return Response(200, {"language": "en", "segments": [{"start": 1.5, "text": " Hi  there ", "speaker": 1}]})

    monkeypatch.setattr(stt_module.requests, "post", post)
    segments, language = stt._recognise(chunk, 600, None)

    assert [(s.start, s.text, s.speaker) for s in segments] == [(601.5, "Hi there", "1")]
    assert language == "en"
    url, body, headers = sent[0]
    assert url.endswith("/audio/transcriptions") and headers["Authorization"] == "Bearer key"
    assert body["model"] == "openai/whisper-large-v3"
    assert body["input_audio"] == {"data": base64.b64encode(b"sound").decode(), "format": "mp3"}
    assert body["response_format"] == "verbose_json"


def test_a_model_without_segments_gives_the_text_of_the_piece(recogniser, monkeypatch):
    stt, chunk = recogniser
    bodies = []

    def post(url, json, headers, timeout):
        bodies.append(dict(json))
        if "response_format" in json:
            return Response(400, text="verbose_json is not supported")
        return Response(200, {"text": "just the text"})

    monkeypatch.setattr(stt_module.requests, "post", post)
    segments, _ = stt._recognise(chunk, 1200, None)

    assert [(s.start, s.text) for s in segments] == [(1200, "just the text")]
    assert len(bodies) == 2 and "response_format" not in bodies[1]


def test_a_busy_service_is_asked_again(recogniser, monkeypatch):
    stt, chunk = recogniser
    answers = iter([Response(429), Response(200, {"text": "ok"})])
    monkeypatch.setattr(stt_module.requests, "post", lambda *a, **k: next(answers))
    assert stt._recognise(chunk, 0, None)[0][0].text == "ok"


def test_other_errors_are_not_retried(recogniser, monkeypatch):
    stt, chunk = recogniser
    calls = []
    monkeypatch.setattr(stt_module.requests, "post", lambda *a, **k: calls.append(1) or Response(401, text="bad key"))
    with pytest.raises(SttError, match="401"):
        stt._recognise(chunk, 0, None)
    assert len(calls) == 1
