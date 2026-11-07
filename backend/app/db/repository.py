import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import Game, GameOverallScore, GamePlatform, GamePlatformHistory, Genre, RunGame, SyncRun
from app.sources import base


def utcnow() -> datetime:
    """Naive UTC datetime: that is how times are stored."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


@dataclass
class SaveResult:
    game_id: int
    created: bool
    changed: bool  # descriptive fields changed (always True for a new game)
    first_seen_at: datetime


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
            next_check_at=now,  # due until the caller sets the schedule
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
    return SaveResult(game_id=row.id, created=created, changed=changed, first_seen_at=row.first_seen_at)


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


def known_slugs(session: Session, source: str, slugs: list[str]) -> set[str]:
    """Which of the given slugs are already in the database."""
    if not slugs:
        return set()
    return set(session.scalars(select(Game.slug).where(Game.source == source, Game.slug.in_(slugs))))


def due_slugs(session: Session, source: str, now: datetime, limit: int) -> list[str]:
    """Slugs of the games whose next check has come, the most overdue first."""
    query = (
        select(Game.slug)
        .where(Game.source == source, Game.next_check_at <= now)
        .order_by(Game.next_check_at.asc(), Game.id.asc())
        .limit(limit)
    )
    return list(session.scalars(query))


def set_next_check(session: Session, game_id: int, when: datetime) -> None:
    session.get(Game, game_id).next_check_at = when


def postpone(session: Session, source: str, slug: str, until: datetime) -> None:
    """Push the next check of a game that could not be loaded."""
    row = session.scalar(select(Game).where(Game.source == source, Game.slug == slug))
    if row is not None:
        row.next_check_at = until


def start_run(
    session: Session, source: str, trigger: str, batch_index: int, now: datetime, pipeline: str = "crawl"
) -> SyncRun:
    run = SyncRun(
        pipeline=pipeline, source=source, trigger=trigger, status="running", batch_index=batch_index, started_at=now
    )
    session.add(run)
    session.flush()
    return run


def add_run_game(
    session: Session,
    run_id: int,
    source: str,
    slug: str,
    outcome: str,
    details: dict | None = None,
    error: str | None = None,
) -> None:
    """Record that a run worked on a game. The title is taken from the stored game, if there is one."""
    game = session.scalar(select(Game).where(Game.source == source, Game.slug == slug))
    session.add(
        RunGame(
            run_id=run_id,
            game_id=game.id if game else None,
            slug=slug,
            title=game.title if game else None,
            outcome=outcome,
            details=details,
            error=error,
        )
    )


def list_run_games(session: Session, run_id: int) -> list[RunGame]:
    return list(session.scalars(select(RunGame).where(RunGame.run_id == run_id).order_by(RunGame.id)))


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


def count_successful_runs(session: Session, source: str, since: datetime, pipeline: str = "crawl") -> int:
    """Number of successful runs of a source at or after `since`: the next batch index of the day."""
    return session.scalar(
        select(func.count())
        .select_from(SyncRun)
        .where(
            SyncRun.pipeline == pipeline,
            SyncRun.source == source,
            SyncRun.status == "success",
            SyncRun.started_at >= since,
        )
    )


def load_source_game(session: Session, game_id: int) -> base.Game:
    """A stored game in the shape sources work with (enough to fetch its reviews)."""
    row = session.get(Game, game_id)
    return base.Game(
        slug=row.slug,
        url=row.url,
        title=row.title,
        platforms=[
            base.PlatformScore(
                slug=p.platform,
                name=p.name,
                metascore=p.metascore,
                critic_reviews_count=p.critic_reviews_count,
                userscore=p.userscore,
                user_reviews_count=p.user_reviews_count,
            )
            for p in row.platforms
        ],
    )
