from datetime import datetime

import pytest

from app.videos import youtube
from app.videos.youtube import QuotaExceeded, YouTubeClient, YouTubeError


class Response:
    def __init__(self, status=200, body=None):
        self.status_code = status
        self._body = body or {}
        self.reason = "reason"

    def json(self):
        return self._body


class Requests:
    """Stands in for requests.get: serves the prepared answers and remembers the calls."""

    def __init__(self, *answers):
        self.answers = list(answers)
        self.calls = []

    def __call__(self, url, params, timeout):
        self.calls.append((url, params))
        return self.answers.pop(0)


@pytest.fixture
def client():
    return YouTubeClient("secret", timeout=5, retries=1)


def use(monkeypatch, *answers) -> Requests:
    requests_get = Requests(*answers)
    monkeypatch.setattr(youtube.requests, "get", requests_get)
    monkeypatch.setattr(youtube.time, "sleep", lambda seconds: None)
    return requests_get


def test_a_search_asks_for_embeddable_english_leaning_videos_by_views(client, monkeypatch):
    get = use(monkeypatch, Response(body={"items": [{"id": {"videoId": "a"}}, {"id": {"videoId": "b"}}]}))
    ids = client.search_videos("Doom let's play", datetime(2026, 10, 22), 15)

    assert ids == ["a", "b"]
    url, params = get.calls[0]
    assert url.endswith("/search")
    assert params["order"] == "viewCount"
    assert params["videoEmbeddable"] == "true"
    assert params["relevanceLanguage"] == "en"
    assert params["publishedAfter"] == "2026-10-22T00:00:00Z"
    assert params["key"] == "secret"


def test_video_details_carry_views_time_and_language(client, monkeypatch):
    item = {
        "id": "a",
        "snippet": {
            "title": "Doom Review",
            "channelTitle": "IGN",
            "channelId": "c1",
            "publishedAt": "2026-11-02T15:30:00Z",
            "defaultAudioLanguage": "en-US",
        },
        "statistics": {"viewCount": "1234"},
        "status": {"embeddable": True},
    }
    hidden = {"id": "b", "snippet": {"title": "x", "defaultLanguage": "de"}, "statistics": {}, "status": {}}
    use(monkeypatch, Response(body={"items": [item, hidden]}))

    first, second = client.get_videos(["a", "b"])
    assert (first.title, first.channel, first.views, first.embeddable) == ("Doom Review", "IGN", 1234, True)
    assert first.published_at == datetime(2026, 11, 2, 15, 30)
    assert first.language == "en-US"
    assert (second.views, second.embeddable, second.language, second.published_at) == (None, False, "de", None)


def test_no_ids_means_no_request(client, monkeypatch):
    get = use(monkeypatch)
    assert client.get_videos([]) == []
    assert get.calls == []


def test_the_playlist_search_leans_to_english_too(client, monkeypatch):
    get = use(monkeypatch, Response(body={"items": [{"id": {"playlistId": "PL1"}, "snippet": {"title": "Doom"}}]}))
    [playlist] = client.search_playlists("Doom", "chan")
    assert (playlist.id, playlist.title) == ("PL1", "Doom")
    assert get.calls[0][1]["relevanceLanguage"] == "en"
    assert get.calls[0][1]["channelId"] == "chan"


def test_an_exhausted_quota_is_told_apart_from_other_errors(client, monkeypatch):
    quota = {"error": {"message": "quota", "errors": [{"reason": "quotaExceeded"}]}}
    use(monkeypatch, Response(403, quota))
    with pytest.raises(QuotaExceeded):
        client.search_videos("x")

    forbidden = {"error": {"message": "key invalid", "errors": [{"reason": "keyInvalid"}]}}
    use(monkeypatch, Response(400, forbidden))
    with pytest.raises(YouTubeError) as error:
        client.search_videos("x")
    assert not isinstance(error.value, QuotaExceeded)
    assert "keyInvalid" in str(error.value)


def test_a_server_error_is_retried_once_then_reported(client, monkeypatch):
    get = use(monkeypatch, Response(503), Response(200, {"items": []}))
    assert client.search_videos("x") == []
    assert len(get.calls) == 2

    use(monkeypatch, Response(503), Response(503))
    with pytest.raises(YouTubeError):
        client.search_videos("x")
