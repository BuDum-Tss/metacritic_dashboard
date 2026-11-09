"""Storage of the videos found on YouTube and the queue of the games to search them for."""

from dataclasses import dataclass, field
from datetime import date, datetime

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.db.models import Game, GameVideo
from app.videos.finder import KINDS, VideoResult


@dataclass
class QueueItem:
    game_id: int
    slug: str
    title: str
    release_date: date | None
    first_seen_at: datetime
    kinds: list[str] = field(default_factory=list)  # the kinds of video to search for


def video_queue(session: Session, source: str, now: datetime, limit: int) -> list[QueueItem]:
    """Games with a kind of video to search for: it has no row yet or its check is due.

    Games that are not out yet are left alone: nobody has made videos about them. First come the
    games with a kind that was never searched (the newest games first), then the overdue checks,
    the most overdue first.
    """
    games = session.execute(
        select(Game.id, Game.slug, Game.title, Game.release_date, Game.first_seen_at)
        .where(Game.source == source, or_(Game.release_date.is_(None), Game.release_date <= now.date()))
    ).all()
    rows: dict[tuple[int, str], GameVideo] = {
        (row.game_id, row.kind): row for row in session.scalars(select(GameVideo))
    }

    never, overdue = [], []
    for game_id, slug, title, release_date, first_seen_at in games:
        item = QueueItem(game_id, slug, title, release_date, first_seen_at)
        oldest_due: datetime | None = None
        missing = False
        for kind in KINDS:
            row = rows.get((game_id, kind))
            if row is None:
                missing = True
                item.kinds.append(kind)
            elif row.next_check_at is not None and row.next_check_at <= now:
                item.kinds.append(kind)
                oldest_due = min(oldest_due or row.next_check_at, row.next_check_at)
        if missing:
            never.append(item)
        elif item.kinds:
            overdue.append((oldest_due, item))

    never.sort(key=lambda item: item.first_seen_at, reverse=True)
    overdue.sort(key=lambda pair: pair[0])
    return (never + [item for _, item in overdue])[:limit]


def save_video(
    session: Session,
    game_id: int,
    kind: str,
    result: VideoResult | None,
    now: datetime,
    next_check_at: datetime | None,
) -> None:
    """Store the outcome of a search: the video, or nothing found (the row says when to try again)."""
    row = session.scalar(select(GameVideo).where(GameVideo.game_id == game_id, GameVideo.kind == kind))
    if row is None:
        row = GameVideo(game_id=game_id, kind=kind)
        session.add(row)
    row.video_id = result.video_id if result else None
    row.title = result.title if result else None
    row.channel = result.channel if result else None
    row.views = result.views if result else None
    row.playlist_id = result.playlist_id if result else None
    row.checked_at = now
    row.next_check_at = next_check_at


def list_videos(session: Session, game_id: int) -> list[GameVideo]:
    """The videos found for a game: the let's play first, then the review."""
    rows = session.scalars(select(GameVideo).where(GameVideo.game_id == game_id, GameVideo.video_id.is_not(None)))
    return sorted(rows, key=lambda row: KINDS.index(row.kind))
