"""Choosing the video of a game: the most viewed one that is really about the game."""

import re
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Protocol

from app.videos.youtube import PlaylistInfo, VideoInfo

LETSPLAY = "letsplay"
REVIEW = "review"
KINDS = (LETSPLAY, REVIEW)

QUERY_SUFFIX = {LETSPLAY: "let's play", REVIEW: "review"}

# a title of the right kind says so; this keeps out videos that only share some words with the game
KIND_WORDS = {
    LETSPLAY: re.compile(r"let'?s play|walkthrough|playthrough|gameplay|\bpart\b|\bepisode\b"),
    REVIEW: re.compile(r"review"),
}

# "Part 1", "Episode 3", "Ep. 2", "Pt 4", "#5"
SERIES = re.compile(r"\b(?:part|episode|ep|pt)\.?\s*#?\s*\d+|#\s*\d+")

# ": Complete Edition", " - Definitive Edition", ": The Remastered Collection"
EDITION_SUFFIX = re.compile(r"\s*[:\-–—]\s*[^:\-–—]*\b(?:edition|remastered|remake|collection|cut)\s*$", re.IGNORECASE)

# reviews come out under embargo a few days before the release, so the period starts a bit earlier
PUBLISHED_BEFORE_RELEASE = timedelta(days=14)


class VideoApi(Protocol):
    def search_videos(self, query: str, published_after: datetime | None = None, limit: int = 15) -> list[str]: ...

    def get_videos(self, ids: list[str]) -> list[VideoInfo]: ...

    def search_playlists(self, query: str, channel_id: str, limit: int = 5) -> list[PlaylistInfo]: ...

    def first_playlist_video(self, playlist_id: str) -> str | None: ...


@dataclass
class VideoResult:
    video_id: str
    title: str
    channel: str
    views: int | None
    playlist_id: str | None = None


def normalize(text: str) -> str:
    """Lower case, no apostrophes, no punctuation, single spaces: "Marvel's  Game!" -> "marvels game"."""
    text = text.lower().replace("’", "'").replace("'", "")
    return " ".join(re.sub(r"[^\w\s]", " ", text).split())


def title_variants(title: str) -> list[str]:
    """The game title as videos may name it: in full and without an edition suffix."""
    variants = [normalize(title)]
    short = normalize(EDITION_SUFFIX.sub("", title))
    if short and short not in variants:
        variants.append(short)
    return variants


def mentions_game(text: str, variants: list[str]) -> bool:
    text = normalize(text)
    return any(variant in text for variant in variants)


def _release_start(release_date: date | None) -> datetime | None:
    """The earliest moment a video of the game may be published: 14 days before the release day (UTC)."""
    return datetime.combine(release_date, time.min) - PUBLISHED_BEFORE_RELEASE if release_date else None


def _published_after(video: VideoInfo, start: datetime | None) -> bool:
    """A video is not older than the start of the period; one with an unknown time is not turned away."""
    return start is None or video.published_at is None or video.published_at >= start


def find_video(api: VideoApi, game_title: str, kind: str, release_date: date | None, limit: int = 15) -> VideoResult | None:
    """The most viewed video of the kind about the game; for a multi-part let's play the first
    video of its playlist, with the playlist. None when nothing fits."""
    variants = title_variants(game_title)
    start = _release_start(release_date)
    ids = api.search_videos(f"{game_title} {QUERY_SUFFIX[kind]}", start, limit)

    fitting = [
        video
        for video in api.get_videos(ids)
        if video.embeddable
        and is_english(video)
        and _published_after(video, start)
        and mentions_game(video.title, variants)
        and KIND_WORDS[kind].search(_plain(video.title))
    ]
    if not fitting:
        return None
    best = max(fitting, key=lambda video: video.views or 0)

    result = VideoResult(video_id=best.id, title=best.title, channel=best.channel, views=best.views)
    if kind == LETSPLAY and SERIES.search(_plain(best.title)):
        _use_playlist(api, game_title, variants, best, result, start)
    return result


def is_english(video: VideoInfo) -> bool:
    """English video: by the language it says it is in, and when it says nothing, by the letters
    of its title (a title with Cyrillic, Chinese, Arabic... letters is not English)."""
    if video.language:
        return video.language.lower().split("-")[0] == "en"
    return all(unicodedata.name(char, "").startswith("LATIN") for char in video.title if char.isalpha())


def _plain(title: str) -> str:
    return title.lower().replace("’", "'")


def _use_playlist(
    api: VideoApi, game_title: str, variants: list[str], best: VideoInfo, result: VideoResult, start: datetime | None
) -> None:
    """Point the result at the first video of the channel's playlist of this game, if there is one."""
    playlists = api.search_playlists(f"{game_title} {QUERY_SUFFIX[LETSPLAY]}", best.channel_id)
    playlist = next((p for p in playlists if mentions_game(p.title, variants)), None)
    if playlist is None:
        return
    first_id = api.first_playlist_video(playlist.id)
    if first_id is None:
        return
    first = next((v for v in api.get_videos([first_id]) if v.embeddable and is_english(v) and _published_after(v, start)), None)
    if first is None:
        return  # the first video cannot be shown, is older than the period or is not English: keep the most viewed one
    result.video_id, result.title, result.channel, result.views = first.id, first.title, first.channel, first.views
    result.playlist_id = playlist.id
