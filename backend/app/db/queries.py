"""Read queries for the API."""

from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.db.models import Game, GameOverallScore, GamePlatform, game_genres

SORTS = ("metascore", "userscore", "title", "updated")
SIMILAR_LIMIT = 6


@dataclass
class GamePage:
    items: list[Game]
    total: int


def list_games(
    session: Session,
    q: str | None = None,
    platform: str | None = None,
    sort: str = "metascore",
    order: str = "desc",
    page: int = 1,
    page_size: int = 24,
) -> GamePage:
    # the score of a game is the average over its platforms (or the chosen one); NULLs are skipped
    scores = select(
        GamePlatform.game_id,
        func.avg(GamePlatform.metascore).label("metascore"),
        func.avg(GamePlatform.userscore).label("userscore"),
    ).group_by(GamePlatform.game_id)
    if platform:
        scores = scores.where(GamePlatform.platform == platform)
    scores = scores.subquery()

    query = select(Game).outerjoin(scores, scores.c.game_id == Game.id)
    if platform:
        query = query.where(scores.c.game_id.is_not(None))
    if q:
        escaped = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        query = query.where(Game.title.ilike(f"%{escaped}%", escape="\\"))

    total = session.scalar(select(func.count()).select_from(query.subquery()))

    column = {
        "metascore": scores.c.metascore,
        "userscore": scores.c.userscore,
        "title": func.lower(Game.title),
        "updated": Game.first_seen_at,
    }[sort]
    direction = column.asc() if order == "asc" else column.desc()
    if sort in ("metascore", "userscore"):
        direction = direction.nulls_last()  # games without a score always go last
    query = query.order_by(direction, Game.id.desc()).limit(page_size).offset((page - 1) * page_size)
    query = query.options(selectinload(Game.genres), selectinload(Game.platforms))
    return GamePage(items=list(session.scalars(query)), total=total)


def get_game(session: Session, game_id: int) -> Game | None:
    return session.scalar(
        select(Game)
        .where(Game.id == game_id)
        .options(selectinload(Game.genres), selectinload(Game.platforms))
    )


def list_platforms(session: Session) -> list[tuple[str, str, int]]:
    """(slug, name, number of games), most popular first."""
    rows = session.execute(
        select(GamePlatform.platform, func.max(GamePlatform.name), func.count())
        .group_by(GamePlatform.platform)
        .order_by(func.count().desc(), GamePlatform.platform)
    )
    return [(slug, name, count) for slug, name, count in rows]


def similarity(genres_a: set[int], genres_b: set[int], platforms_a: set[str], platforms_b: set[str]) -> float:
    """Jaccard similarity of genres plus a small bonus for shared platforms."""
    if not genres_a or not genres_b:
        return 0.0
    jaccard = len(genres_a & genres_b) / len(genres_a | genres_b)
    shared_platforms = len(platforms_a & platforms_b)
    return jaccard + 0.05 * shared_platforms if jaccard else 0.0


def _best_metascore(game: Game) -> int:
    return max((p.metascore for p in game.platforms if p.metascore is not None), default=-1)


def similar_games(session: Session, game: Game, limit: int = SIMILAR_LIMIT) -> list[Game]:
    genre_ids = {g.id for g in game.genres}
    if not genre_ids:
        return []
    platforms = {p.platform for p in game.platforms}

    candidates = session.scalars(
        select(Game)
        .join(game_genres, game_genres.c.game_id == Game.id)
        .where(game_genres.c.genre_id.in_(genre_ids), Game.id != game.id)
        .distinct()
        .options(selectinload(Game.genres), selectinload(Game.platforms))
    )
    scored = []
    for other in candidates:
        score = similarity(genre_ids, {g.id for g in other.genres}, platforms, {p.platform for p in other.platforms})
        if score > 0:
            scored.append((score, _best_metascore(other), other))
    scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return [other for _, _, other in scored[:limit]]


def latest_overall(session: Session, game_id: int) -> dict[str, GameOverallScore]:
    """The latest overall score of critics and of users of a game."""
    result: dict[str, GameOverallScore] = {}
    for source in ("critics", "users"):
        row = session.scalar(
            select(GameOverallScore)
            .where(GameOverallScore.game_id == game_id, GameOverallScore.source == source)
            .order_by(GameOverallScore.captured_at.desc(), GameOverallScore.id.desc())
            .limit(1)
        )
        if row is not None:
            result[source] = row
    return result


def average_scores(platforms, platform: str | None = None) -> tuple[float | None, float | None]:
    """The single score of a game: the mean of the platform scores that exist, critics and users
    separately. With `platform` only that platform counts. (None, None) when there is nothing."""
    chosen = [p for p in platforms if platform is None or p.platform == platform]
    critics = [p.metascore for p in chosen if p.metascore is not None]
    users = [p.userscore for p in chosen if p.userscore is not None]
    return (
        sum(critics) / len(critics) if critics else None,
        sum(users) / len(users) if users else None,
    )
