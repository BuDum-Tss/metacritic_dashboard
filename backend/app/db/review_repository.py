"""Reviews and their summaries."""

from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.db.models import Review, ReviewSummary, SummaryPoint
from app.sources import base

KINDS = ("critics", "users")

# a point of a summary: its text and the 1-based positions (in the sample) of the reviews behind it
Point = tuple[str, list[int]]


def due_kinds(session: Session, game_id: int, now: datetime, interval_hours: int) -> list[str]:
    """Review kinds whose summary is missing or older than the minimal refresh interval."""
    latest = dict(
        session.execute(
            select(ReviewSummary.source, func.max(ReviewSummary.generated_at))
            .where(ReviewSummary.game_id == game_id)
            .group_by(ReviewSummary.source)
        ).all()
    )
    threshold = now - timedelta(hours=interval_hours)
    return [kind for kind in KINDS if kind not in latest or latest[kind] <= threshold]


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
