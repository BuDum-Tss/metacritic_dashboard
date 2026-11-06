from typing import Literal

from fastapi import APIRouter, HTTPException, Query

from app.api.schemas import GameDetail, GamePageOut, GameShort, PlatformOption
from app.db import queries
from app.db.session import session_scope

router = APIRouter(prefix="/api/games", tags=["games"])


@router.get("", response_model=GamePageOut)
def list_games(
    q: str | None = Query(None, max_length=100),
    platform: str | None = None,
    sort: Literal["metascore", "userscore", "title", "updated"] = "metascore",
    order: Literal["asc", "desc"] = "desc",
    page: int = Query(1, ge=1),
    page_size: int = Query(24, ge=1, le=100),
) -> GamePageOut:
    with session_scope() as session:
        result = queries.list_games(session, q, platform, sort, order, page, page_size)
        return GamePageOut(
            items=[GameShort.model_validate(game) for game in result.items],
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
        detail.similar = [GameShort.model_validate(other) for other in queries.similar_games(session, game)]
        return detail
