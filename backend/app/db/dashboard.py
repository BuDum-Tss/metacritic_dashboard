"""Aggregates for the market dashboard: which games are successful, and why.

The games are few (hundreds, not millions), so each one is loaded once with its platforms and
genres and the blocks are computed in Python: simple and easy to test.
"""

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from statistics import mean, median

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db import review_repository
from app.db.models import Game
from app.db.queries import average_scores

HIT_CRITICS = 75  # a "hit": critics from 75 and players from 7.5, the green of Metacritic
HIT_USERS = 7.5
MIN_GENRE_GAMES = 3
MIN_RATINGS = 10  # a gap between critics and players says nothing on a handful of ratings
TOP_DIVERGENCES = 5
MIN_GAP = 10  # a smaller gap (in points of 100) is agreement: well-rated games differ by that much
RHYTHM_DAYS = 30
TREND_DAYS = 7  # the window of the moving averages


@dataclass
class GameStat:
    id: int
    title: str
    release_date: date | None
    first_seen_at: datetime
    critics: float | None  # the mean of the platform Metascores
    users: float | None  # the mean of the platform Userscores
    attention: int  # the number of player ratings over all platforms
    genres: list[str]


def half_up(value: float) -> int:
    return int(value + 0.5)


def _load(session: Session) -> list[GameStat]:
    games = session.scalars(select(Game).options(selectinload(Game.genres), selectinload(Game.platforms)))
    stats = []
    for game in games:
        critics, users = average_scores(game.platforms)
        stats.append(
            GameStat(
                id=game.id,
                title=game.title,
                release_date=game.release_date,
                first_seen_at=game.first_seen_at,
                critics=critics,
                users=users,
                attention=sum(p.user_reviews_count or 0 for p in game.platforms),
                genres=[g.name for g in game.genres],
            )
        )
    return stats


def _tiles(stats: list[GameStat], both: list[GameStat], now: datetime) -> dict:
    hits = [g for g in both if g.critics >= HIT_CRITICS and g.users >= HIT_USERS]
    return {
        "games_total": len(stats),
        "new_7d": sum(1 for g in stats if g.first_seen_at >= now - timedelta(days=7)),
        "hits_share": half_up(100 * len(hits) / len(both)) if both else None,
        "hits": len(hits),
        "rated_games": len(both),  # the games the share and the gap are counted over
        "avg_gap": round(mean(abs(g.critics - g.users * 10) for g in both), 1) if both else None,
    }


def _map(stats: list[GameStat]) -> dict:
    points = [g for g in stats if g.attention > 0 and (g.critics is not None or g.users is not None)]
    return {
        "points": [
            {
                "id": g.id,
                "title": g.title,
                "critics": half_up(g.critics) if g.critics is not None else None,
                "users": round(g.users, 1) if g.users is not None else None,
                "attention": g.attention,
            }
            for g in points
        ],
        "attention_median": int(median(g.attention for g in points)) if points else None,
    }


def _mean(values: list[float]) -> float | None:
    return round(mean(values), 1) if values else None


def _genres(stats: list[GameStat]) -> list[dict]:
    by_genre: dict[str, list[GameStat]] = {}
    for g in stats:
        for genre in g.genres:
            by_genre.setdefault(genre, []).append(g)
    rows = [
        {
            "genre": genre,
            "games": len(games),
            "avg_critics": _mean([g.critics for g in games if g.critics is not None]),
            "avg_users": _mean([g.users for g in games if g.users is not None]),
            # over the games that have player ratings; a genre without any has no value
            "avg_attention": half_up(mean(rated)) if (rated := [g.attention for g in games if g.attention > 0]) else None,
        }
        for genre, games in by_genre.items()
        if len(games) >= MIN_GENRE_GAMES
    ]
    rows.sort(key=lambda row: (-row["games"], row["genre"]))
    return rows


def _reason(session: Session, game_id: int, source: str) -> dict | None:
    """The main complaint of the side that is unhappy, from its latest summary."""
    summary = review_repository.latest_summary(session, game_id, source)
    point = next((p for p in summary.points if p.kind == "dislike"), None) if summary else None
    return {"source": source, "text": point.text} if point else None


def _divergences(session: Session, both: list[GameStat]) -> dict:
    eligible = [g for g in both if g.attention >= MIN_RATINGS]

    def gap(g: GameStat) -> float:
        return g.critics - g.users * 10

    def row(g: GameStat, unhappy: str) -> dict:
        return {
            "id": g.id,
            "title": g.title,
            "critics": half_up(g.critics),
            "users": round(g.users, 1),
            "gap": round(gap(g), 1),
            "reason": _reason(session, g.id, unhappy),
        }

    critics_love = sorted((g for g in eligible if gap(g) > MIN_GAP), key=gap, reverse=True)[:TOP_DIVERGENCES]
    players_love = sorted((g for g in eligible if gap(g) < -MIN_GAP), key=gap)[:TOP_DIVERGENCES]
    return {
        "critics_love": [row(g, "users") for g in critics_love],
        "players_love": [row(g, "critics") for g in players_love],
    }


def _rhythm(stats: list[GameStat], today: date) -> dict:
    start = today - timedelta(days=RHYTHM_DAYS - 1)
    earliest = start - timedelta(days=TREND_DAYS - 1)  # the first day needs its own window
    by_day: dict[date, list[GameStat]] = {}
    for g in stats:
        if g.release_date is not None and earliest <= g.release_date <= today:
            by_day.setdefault(g.release_date, []).append(g)

    days = []
    for i in range(RHYTHM_DAYS):
        day = start + timedelta(days=i)
        that_day = by_day.get(day, [])
        window = [g for k in range(TREND_DAYS) for g in by_day.get(day - timedelta(days=k), [])]
        days.append(
            {
                "date": day,
                "games": len(that_day),
                "avg_critics": _mean([g.critics for g in that_day if g.critics is not None]),
                "games_avg7": round(len(window) / TREND_DAYS, 1),
                "critics_avg7": _mean([g.critics for g in window if g.critics is not None]),
            }
        )
    return {
        "days": days,
        "coverage": {"with_date": sum(1 for g in stats if g.release_date is not None), "total": len(stats)},
    }


def build(session: Session, now: datetime) -> dict:
    stats = _load(session)
    both = [g for g in stats if g.critics is not None and g.users is not None]
    return {
        "tiles": _tiles(stats, both, now),
        "map": _map(stats),
        "genres": _genres(stats),
        "divergences": _divergences(session, both),
        "rhythm": _rhythm(stats, now.date()),
    }
