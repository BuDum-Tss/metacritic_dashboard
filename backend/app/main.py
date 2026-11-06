from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api import sync as sync_api
from app.db.session import engine, init_db
from app.scheduler import create_scheduler
from app.sources.base import GameSource
from app.sources.metacritic.source import MetacriticSource


def create_app(source: GameSource | None = None, scheduler_enabled: bool = True) -> FastAPI:
    source = source or MetacriticSource()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        init_db(engine)
        app.state.scheduler = create_scheduler(source) if scheduler_enabled else None
        if app.state.scheduler:
            app.state.scheduler.start()
        yield
        if app.state.scheduler:
            app.state.scheduler.shutdown(wait=False)

    app = FastAPI(title="Metacritic Dashboard", lifespan=lifespan)
    app.state.source = source
    app.state.scheduler = None
    app.include_router(sync_api.router)
    return app


app = create_app()
