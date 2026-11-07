"""When a game is visited again, and how many games a run takes."""

from datetime import datetime, timedelta

from app.config import settings


def next_check(first_seen_at: datetime, now: datetime) -> datetime:
    """Young games (found less than `young_days` ago) come back daily, older ones weekly."""
    if now - first_seen_at < timedelta(days=settings.young_days):
        return now + timedelta(hours=settings.revisit_young_hours)
    return now + timedelta(days=settings.revisit_old_days)


def failure_backoff(now: datetime) -> datetime:
    """A game that could not be loaded is not asked for again at once."""
    return now + timedelta(hours=settings.revisit_young_hours)
