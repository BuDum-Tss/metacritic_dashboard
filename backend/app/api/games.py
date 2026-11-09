from typing import Literal

from fastapi import APIRouter, HTTPException, Query

from app.api.schemas import (
    GameDetail,
    GamePageOut,
    GameShort,
    OverallOut,
    OverallsOut,
    PlatformOption,
    PointOut,
    ReviewOut,
    ScoreOut,
    SummariesOut,
    SummaryOut,
    VideoOut,
)
from app.db import queries, review_repository, video_repository
from app.db.models import Game, GameVideo, ReviewSummary
from app.db.session import session_scope

router = APIRouter(prefix="/api/games", tags=["games"])


@router.get("", response_model=GamePageOut)
def list_games(
    q: str | None = Query(None, max_length=100),
    platform: str | None = None,
    sort: Literal["metascore", "userscore", "release", "title", "updated"] = "metascore",
    order: Literal["asc", "desc"] = "desc",
    page: int = Query(1, ge=1),
    page_size: int = Query(24, ge=1, le=100),
) -> GamePageOut:
    with session_scope() as session:
        result = queries.list_games(session, q, platform, sort, order, page, page_size)
        return GamePageOut(
            items=[_short(game, platform) for game in result.items],
            total=result.total,
            page=page,
            page_size=page_size,
        )


@router.get("/platforms", response_model=list[PlatformOption])
def list_platforms() -> list[PlatformOption]:
    with session_scope() as session:
        return [
            PlatformOption(platform=slug, name=name, games=count)
            for slug, name, count in queries.list_platforms(session)
        ]


@router.get("/{game_id}", response_model=GameDetail)
def get_game(game_id: int) -> GameDetail:
    with session_scope() as session:
        game = queries.get_game(session, game_id)
        if game is None:
            raise HTTPException(status_code=404, detail="Game not found")
        detail = GameDetail.model_validate(game)
        detail.score = _score(game)
        detail.videos = [_video_out(row) for row in video_repository.list_videos(session, game_id)]
        detail.similar = [_short(other) for other in queries.similar_games(session, game)]
        overall = queries.latest_overall(session, game_id)
        detail.overall = OverallsOut(**{kind: OverallOut.model_validate(row) for kind, row in overall.items()})
        found = review_repository.latest_summaries(session, game_id)
        detail.summaries = SummariesOut(**{kind: _summary_out(summary) for kind, summary in found.items()})
        return detail


def _video_out(row: GameVideo) -> VideoOut:
    watch = f"https://www.youtube.com/watch?v={row.video_id}"
    return VideoOut(
        kind=row.kind,
        video_id=row.video_id,
        title=row.title,
        channel=row.channel,
        views=row.views,
        url=f"{watch}&list={row.playlist_id}" if row.playlist_id else watch,
        playlist_url=f"https://www.youtube.com/playlist?list={row.playlist_id}" if row.playlist_id else None,
    )


def _score(game: Game, platform: str | None = None) -> ScoreOut:
    critics, users = queries.average_scores(game.platforms, platform)
    return ScoreOut(
        critics=int(critics + 0.5) if critics is not None else None,  # half up, not to the even
        users=round(users, 1) if users is not None else None,
    )


def _short(game: Game, platform: str | None = None) -> GameShort:
    item = GameShort.model_validate(game)
    item.score = _score(game, platform)
    return item


def _summary_out(summary: ReviewSummary) -> SummaryOut:
    points = {"like": [], "dislike": []}
    for point in summary.points:
        points[point.kind].append(PointOut(id=point.id, text=point.text, review_ids=[r.id for r in point.reviews]))
    return SummaryOut(
        generated_at=summary.generated_at,
        sample_size=summary.sample_size,
        total_reviews=summary.total_reviews,
        model=summary.model,
        likes=points["like"],
        dislikes=points["dislike"],
        reviews=[
            ReviewOut(
                id=r.id, author=r.author, score=r.score, date=r.reviewed_at, text=r.text, url=r.url, platform=r.platform
            )
            for r in summary.reviews  # the whole sample, already ordered by id
        ],
    )
