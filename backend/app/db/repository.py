import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import Game, GameOverallScore, GamePlatform, GamePlatformHistory, Genre, SyncRun
from app.sources import base


def utcnow() -> datetime:
    """Naive UTC datetime: that is how times are stored."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


@dataclass
class SaveResult:
    game_id: int
    created: bool
    changed: bool  # descriptive fields changed (always True for a new game)


def content_hash(game: base.Game) -> str:
    """Hash of the descriptive fields; metrics are not included, they are versioned separately."""
    payload = {
        "title": game.title,
        "cover_url": game.cover_url,
        "developer": game.developer,
        "description": game.description,
        "video_url": game.video_url,
        "genres": sorted(game.genres),
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def _genres(session: Session, names: list[str]) -> list[Genre]:
    result = []
    for name in sorted(set(names)):
        genre = session.scalar(select(Genre).where(Genre.name == name))
        if genre is None:
            genre = Genre(name=name)
            session.add(genre)
        result.append(genre)
    return result


def save_game(session: Session, source: str, game: base.Game, now: datetime) -> SaveResult:
    """Create or update a game with its genres and platforms. Metrics are always snapshotted."""
    digest = content_hash(game)
    row = session.scalar(select(Game).where(Game.source == source, Game.slug == game.slug))
    created = row is None
    changed = created or row.content_hash != digest

    genres = _genres(session, game.genres) if changed else None  # queries first: they autoflush
    if created:
        row = Game(
            source=source,
            slug=game.slug,
            url=game.url,
            title=game.title,
            first_seen_at=now,
            updated_at=now,
            last_processed_at=now,
        )
        session.add(row)
    if changed:
        row.url = game.url
        row.title = game.title
        row.cover_url = game.cover_url
        row.developer = game.developer
        row.description = game.description
        row.video_url = game.video_url
        row.genres = genres
        row.content_hash = digest
        row.updated_at = now
    row.last_processed_at = now
    session.flush()

    _save_platforms(session, row, game.platforms, now)
    for overall in game.overall:
        session.add(
            GameOverallScore(
                game_id=row.id,
                source=overall.kind,
                score=overall.score,
                verdict=overall.verdict,
                reviews_count=overall.reviews_count,
                positive=overall.positive,
                mixed=overall.mixed,
                negative=overall.negative,
                captured_at=now,
            )
        )
    return SaveResult(game_id=row.id, created=created, changed=changed)


def _save_platforms(session: Session, row: Game, platforms: list[base.PlatformScore], now: datetime) -> None:
    current = {p.platform: p for p in row.platforms}
    for score in platforms:
        entry = current.get(score.slug)
        if entry is None:
            entry = GamePlatform(game_id=row.id, platform=score.slug)
            row.platforms.append(entry)
        entry.name = score.name
        entry.metascore = score.metascore
        entry.userscore = score.userscore
        entry.critic_reviews_count = score.critic_reviews_count
        entry.user_reviews_count = score.user_reviews_count
        entry.updated_at = now
        session.add(
            GamePlatformHistory(
                game_id=row.id,
                platform=score.slug,
                metascore=score.metascore,
                userscore=score.userscore,
                critic_reviews_count=score.critic_reviews_count,
                user_reviews_count=score.user_reviews_count,
                captured_at=now,
            )
        )
    session.flush()


def processed_since(session: Session, source: str, since: datetime) -> set[str]:
    """Slugs of games already processed at or after `since`."""
    rows = session.scalars(select(Game.slug).where(Game.source == source, Game.last_processed_at >= since))
    return set(rows)


def start_run(session: Session, source: str, trigger: str, batch_index: int, now: datetime) -> SyncRun:
    run = SyncRun(source=source, trigger=trigger, status="running", batch_index=batch_index, started_at=now)
    session.add(run)
    session.flush()
    return run


def update_progress(session: Session, run_id: int, found: int, processed: int, failed: int) -> None:
    run = session.get(SyncRun, run_id)
    run.games_found = found
    run.games_processed = processed
    run.games_failed = failed
    session.flush()


def finish_run(
    session: Session,
    run_id: int,
    status: str,
    now: datetime,
    found: int = 0,
    processed: int = 0,
    failed: int = 0,
    error: str | None = None,
) -> None:
    update_progress(session, run_id, found, processed, failed)
    run = session.get(SyncRun, run_id)
    run.status = status
    run.finished_at = now
    run.error = error
    session.flush()


def count_successful_runs(session: Session, source: str, since: datetime) -> int:
    """Number of successful runs of a source at or after `since`: the next batch index of the day."""
    return session.scalar(
        select(func.count())
        .select_from(SyncRun)
        .where(SyncRun.source == source, SyncRun.status == "success", SyncRun.started_at >= since)
    )
