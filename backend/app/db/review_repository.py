"""Reviews and their summaries."""

from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session, selectinload

from app.db.models import AnalysisState, Game, GameOverallScore, Review, ReviewSummary, SummaryPoint
from app.sources import base

KINDS = ("critics", "users")

# a point of a summary: its text and the 1-based positions (in the sample) of the reviews behind it
Point = tuple[str, list[int]]


MIN_REVIEWS = 3  # fewer reviews of a kind give no summary


@dataclass
class KindPlan:
    """What the analysis knows about one kind of reviews of a game before it asks the site."""

    total: int  # the number of reviews as the crawl last saw it
    tones: dict[str, int]  # positive / mixed / negative


@dataclass
class QueueItem:
    game_id: int
    slug: str
    plans: dict[str, KindPlan]
    priority: tuple


def analysis_queue(session: Session, source: str, now: datetime, limit: int, interval_hours: int) -> list[QueueItem]:
    """The games whose reviews are worth a look, chosen from the database alone.

    A kind of reviews of a game is queued when there are at least MIN_REVIEWS of them and it was
    never checked, or the number changed since the last check and the check is older than
    `interval_hours`. Never checked games come first (the newest first), then the longest unchecked.
    """
    threshold = now - timedelta(hours=interval_hours)
    items: dict[int, QueueItem] = {}
    for kind in KINDS:
        latest = (
            select(func.max(GameOverallScore.id))
            .where(GameOverallScore.source == kind)
            .group_by(GameOverallScore.game_id)
        )
        query = (
            select(
                Game.id,
                Game.slug,
                GameOverallScore.reviews_count,
                GameOverallScore.positive,
                GameOverallScore.mixed,
                GameOverallScore.negative,
                AnalysisState.checked_at,
                AnalysisState.total_reviews,
            )
            .join(GameOverallScore, GameOverallScore.game_id == Game.id)
            .outerjoin(AnalysisState, and_(AnalysisState.game_id == Game.id, AnalysisState.kind == kind))
            .where(
                Game.source == source,
                GameOverallScore.id.in_(latest),
                GameOverallScore.reviews_count >= MIN_REVIEWS,
            )
        )
        for game_id, slug, total, positive, mixed, negative, checked_at, checked_total in session.execute(query):
            if checked_at is None:
                priority = (0, -game_id)
            elif checked_total != total and checked_at <= threshold:
                priority = (1, checked_at.timestamp())
            else:
                continue
            tones = {
                name: count
                for name, count in (("positive", positive), ("mixed", mixed), ("negative", negative))
                if count is not None
            }
            item = items.setdefault(game_id, QueueItem(game_id, slug, {}, priority))
            item.plans[kind] = KindPlan(total, tones)
            item.priority = min(item.priority, priority)
    return sorted(items.values(), key=lambda item: item.priority)[:limit]


def record_check(session: Session, game_id: int, kind: str, total: int, now: datetime) -> None:
    """Remember that the reviews of a game were checked while there were `total` of them."""
    state = session.get(AnalysisState, (game_id, kind))
    if state is None:
        session.add(AnalysisState(game_id=game_id, kind=kind, checked_at=now, total_reviews=total))
    else:
        state.checked_at = now
        state.total_reviews = total


@dataclass
class SummaryMark:
    """What is needed to decide whether a summary is still right, without loading its points."""

    generated_at: datetime
    total_reviews: int | None
    reviews_hash: str


def summary_marks(session: Session, game_id: int) -> dict[str, SummaryMark]:
    marks: dict[str, SummaryMark] = {}
    for kind in KINDS:
        row = session.execute(
            select(ReviewSummary.generated_at, ReviewSummary.total_reviews, ReviewSummary.reviews_hash)
            .where(ReviewSummary.game_id == game_id, ReviewSummary.source == kind)
            .order_by(ReviewSummary.generated_at.desc(), ReviewSummary.id.desc())
            .limit(1)
        ).first()
        if row is not None:
            marks[kind] = SummaryMark(*row)
    return marks


def latest_summary(session: Session, game_id: int, kind: str) -> ReviewSummary | None:
    query = (
        select(ReviewSummary)
        .where(ReviewSummary.game_id == game_id, ReviewSummary.source == kind)
        .order_by(ReviewSummary.generated_at.desc(), ReviewSummary.id.desc())
        .limit(1)
        .options(
            selectinload(ReviewSummary.points).selectinload(SummaryPoint.reviews),
            selectinload(ReviewSummary.reviews),
        )
    )
    return session.scalar(query)


def latest_summaries(session: Session, game_id: int) -> dict[str, ReviewSummary]:
    found = {kind: latest_summary(session, game_id, kind) for kind in KINDS}
    return {kind: summary for kind, summary in found.items() if summary is not None}


def save_summary(
    session: Session,
    game_id: int,
    kind: str,
    sample: list[base.Review],
    total: int | None,
    model: str,
    digest: str,
    likes: list[Point],
    dislikes: list[Point],
    now: datetime,
) -> ReviewSummary:
    """Store the sample reviews (reused when already known), the summary and its points."""
    rows: list[Review] = []
    for review in sample:
        row = session.scalar(
            select(Review).where(
                Review.game_id == game_id, Review.source == kind, Review.external_key == review.key
            )
        )
        if row is None:
            row = Review(
                game_id=game_id,
                source=kind,
                external_key=review.key,
                platform=review.platform,
                author=review.author,
                score=review.score,
                reviewed_at=review.date,
                text=review.text,
                url=review.url,
                first_seen_at=now,
            )
            session.add(row)
        rows.append(row)
    session.flush()

    summary = ReviewSummary(
        game_id=game_id,
        source=kind,
        reviews_hash=digest,
        sample_size=len(sample),
        total_reviews=total,
        model=model,
        generated_at=now,
    )
    for point_kind, points in (("like", likes), ("dislike", dislikes)):
        for position, (text, positions) in enumerate(points):
            summary.points.append(
                SummaryPoint(
                    kind=point_kind,
                    position=position,
                    text=text,
                    reviews=[rows[p - 1] for p in positions],
                )
            )
    summary.reviews = rows  # the whole sample, of which the points cite a part
    session.add(summary)
    session.flush()
    return summary
