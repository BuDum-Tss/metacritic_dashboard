"""A small client of the YouTube Data API v3: only the calls the video search needs."""

import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone

import requests

from app.config import settings

log = logging.getLogger(__name__)

API_URL = "https://www.googleapis.com/youtube/v3"
QUOTA_REASONS = {"quotaExceeded", "dailyLimitExceeded"}


class YouTubeError(Exception):
    pass


class QuotaExceeded(YouTubeError):
    """The daily quota of the API key is used up: nothing works until it resets."""


@dataclass
class VideoInfo:
    id: str
    title: str
    channel: str
    channel_id: str
    views: int | None
    embeddable: bool
    published_at: datetime | None = None  # naive UTC
    language: str | None = None  # the language the video says it is in, e.g. "en-US"


@dataclass
class PlaylistInfo:
    id: str
    title: str


class YouTubeClient:
    def __init__(self, api_key: str, timeout: float, retries: int = 2) -> None:
        self._key = api_key
        self._timeout = timeout
        self._retries = retries

    def _get(self, path: str, params: dict) -> dict:
        params = {**params, "key": self._key}
        last_error: Exception | None = None
        for attempt in range(self._retries + 1):
            if attempt:
                time.sleep(2 * attempt)
            try:
                response = requests.get(f"{API_URL}/{path}", params=params, timeout=self._timeout)
            except requests.RequestException as exc:
                last_error = YouTubeError(f"{path}: {exc}")
                continue
            if response.status_code == 200:
                return response.json()
            if response.status_code >= 500:
                last_error = YouTubeError(f"{path}: HTTP {response.status_code}")
                continue
            raise _api_error(path, response)
        raise last_error  # type: ignore[misc]

    def search_videos(self, query: str, published_after: datetime | None = None, limit: int = 15) -> list[str]:
        """Ids of embeddable videos for the query, the most viewed first (100 quota units)."""
        params = {
            "part": "id",
            "type": "video",
            "q": query,
            "order": "viewCount",
            "videoEmbeddable": "true",
            "relevanceLanguage": "en",  # a hint: YouTube prefers English videos
            "maxResults": limit,
        }
        if published_after:
            params["publishedAfter"] = published_after.strftime("%Y-%m-%dT%H:%M:%SZ")
        data = self._get("search", params)
        return [item["id"]["videoId"] for item in data.get("items", []) if item.get("id", {}).get("videoId")]

    def get_videos(self, ids: list[str]) -> list[VideoInfo]:
        """Title, channel, views and whether the video can be embedded (1 quota unit)."""
        if not ids:
            return []
        data = self._get("videos", {"part": "snippet,statistics,status", "id": ",".join(ids), "maxResults": len(ids)})
        videos = []
        for item in data.get("items", []):
            views = item.get("statistics", {}).get("viewCount")  # hidden by some channels
            videos.append(
                VideoInfo(
                    id=item["id"],
                    title=item["snippet"]["title"],
                    channel=item["snippet"].get("channelTitle", ""),
                    channel_id=item["snippet"].get("channelId", ""),
                    views=int(views) if views is not None else None,
                    embeddable=bool(item.get("status", {}).get("embeddable", False)),
                    published_at=_parse_time(item["snippet"].get("publishedAt")),
                    language=item["snippet"].get("defaultAudioLanguage") or item["snippet"].get("defaultLanguage"),
                )
            )
        return videos

    def search_playlists(self, query: str, channel_id: str, limit: int = 5) -> list[PlaylistInfo]:
        """Playlists of a channel for the query, the most relevant first (100 quota units)."""
        data = self._get(
            "search",
            {
                "part": "snippet",
                "type": "playlist",
                "q": query,
                "channelId": channel_id,
                "relevanceLanguage": "en",
                "maxResults": limit,
            },
        )
        return [
            PlaylistInfo(id=item["id"]["playlistId"], title=item["snippet"]["title"])
            for item in data.get("items", [])
            if item.get("id", {}).get("playlistId")
        ]

    def first_playlist_video(self, playlist_id: str) -> str | None:
        """Id of the first video of a playlist (1 quota unit)."""
        data = self._get("playlistItems", {"part": "contentDetails", "playlistId": playlist_id, "maxResults": 1})
        items = data.get("items", [])
        return items[0]["contentDetails"].get("videoId") if items else None


def _parse_time(value: str | None) -> datetime | None:
    """YouTube times look like 2026-11-05T12:00:00Z; stored as naive UTC like everywhere else."""
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc).replace(tzinfo=None)


def _api_error(path: str, response: requests.Response) -> YouTubeError:
    reason, message = "", response.reason or ""
    try:
        error = response.json()["error"]
        message = error.get("message", message)
        reason = (error.get("errors") or [{}])[0].get("reason", "")
    except (ValueError, KeyError):
        pass
    if reason in QUOTA_REASONS:
        return QuotaExceeded(f"{path}: {reason}")
    return YouTubeError(f"{path}: HTTP {response.status_code} {reason} {message}".strip())


def make_youtube_client() -> YouTubeClient | None:
    """The client from the settings, or None when no API key is set."""
    if not settings.youtube_api_key:
        return None
    return YouTubeClient(settings.youtube_api_key, settings.request_timeout_seconds)
