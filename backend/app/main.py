import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api import dashboard as dashboard_api
from app.api import games as games_api
from app.api import sync as sync_api
from app.api import transcripts as transcripts_api
from app.db import repository, transcript_repository, video_summary_repository
from app.db.session import engine, init_db, session_scope
from app.scheduler import create_scheduler
from app.services import video_summary
from app.sources.base import GameSource
from app.sources.metacritic.source import MetacriticSource


def create_app(source: GameSource | None = None, scheduler_enabled: bool = True) -> FastAPI:
    # the pipelines run side by side, so each gets its own source (its own connection and
    # pause between requests); a source passed in, as in the tests, serves both
    crawl_source = source or MetacriticSource()
    analysis_source = source or MetacriticSource()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        init_db(engine)
        with session_scope() as session:
            transcript_repository.interrupt_running(session, repository.utcnow())
            video_summary_repository.interrupt_running(session, repository.utcnow())
        # the summaries queued by the migration are built in the background, the start does not wait for them
        threading.Thread(target=video_summary.run_pending, daemon=True).start()
        app.state.scheduler = create_scheduler(crawl_source, analysis_source) if scheduler_enabled else None
        if app.state.scheduler:
            app.state.scheduler.start()
        yield
        if app.state.scheduler:
            app.state.scheduler.shutdown(wait=False)

    app = FastAPI(title="Metacritic Dashboard", lifespan=lifespan)
    app.state.crawl_source = crawl_source
    app.state.analysis_source = analysis_source
    app.state.scheduler = None
    app.include_router(sync_api.router)
    app.include_router(games_api.router)
    app.include_router(transcripts_api.router)
    app.include_router(dashboard_api.router)
    return app


app = create_app()
