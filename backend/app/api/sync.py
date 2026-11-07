import logging
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Request
from sqlalchemy import select

from app.api.schemas import PipelineStatus, RunGameOut, SyncRunOut, SyncStatus
from app.config import settings
from app.db import repository
from app.db.models import SyncRun
from app.db.session import session_scope
from app.services import analysis, crawl
from app.services.pipelines import ANALYSIS, CRAWL, PipelineRunning, is_running
from app.sources.base import GameSource

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/sync", tags=["sync"])

PipelineName = Literal["crawl", "analysis"]


def _run_crawl(source: GameSource) -> None:
    try:
        crawl.run_crawl(source, "manual")
    except PipelineRunning:
        log.info("manual crawl skipped: it is already running")


def _run_analysis(source: GameSource) -> None:
    try:
        analysis.run_analysis(source, "manual")
    except PipelineRunning:
        log.info("manual analysis skipped: it is already running")


def _pipeline_status(request: Request, pipeline: str) -> PipelineStatus:
    scheduler = request.app.state.scheduler
    job = scheduler.get_job(pipeline) if scheduler else None
    interval, budget, enabled = {
        CRAWL: (settings.crawl_interval_hours, settings.crawl_budget, True),
        ANALYSIS: (settings.analysis_interval_hours, settings.analysis_budget, analysis.is_enabled()),
    }[pipeline]

    with session_scope() as session:
        runs = select(SyncRun).where(SyncRun.pipeline == pipeline).order_by(SyncRun.id.desc())
        current = session.scalar(runs.where(SyncRun.status == "running"))
        last = session.scalar(runs.where(SyncRun.status != "running"))
        return PipelineStatus(
            running=is_running(pipeline),
            enabled=enabled,
            interval_hours=interval,
            budget=budget,
            next_run_at=job.next_run_time if job else None,
            current_run=SyncRunOut.model_validate(current) if current else None,
            last_run=SyncRunOut.model_validate(last) if last else None,
        )


@router.get("/status", response_model=SyncStatus)
def get_status(request: Request) -> SyncStatus:
    return SyncStatus(
        crawl=_pipeline_status(request, CRAWL),
        analysis=_pipeline_status(request, ANALYSIS),
    )


@router.post("/run", status_code=202)
def run_now(request: Request, background: BackgroundTasks, pipeline: PipelineName = Query(...)) -> dict:
    if pipeline == ANALYSIS and not analysis.is_enabled():
        raise HTTPException(status_code=400, detail="The analysis is off: no LLM_API_KEY is set")
    if is_running(pipeline):
        raise HTTPException(status_code=409, detail=f"The {pipeline} is already running")
    if pipeline == CRAWL:
        background.add_task(_run_crawl, request.app.state.crawl_source)
    else:
        background.add_task(_run_analysis, request.app.state.analysis_source)
    return {"status": "accepted"}


@router.get("/runs", response_model=list[SyncRunOut])
def list_runs(
    limit: int = Query(20, ge=1, le=200), pipeline: PipelineName | None = None
) -> list[SyncRunOut]:
    with session_scope() as session:
        query = select(SyncRun).order_by(SyncRun.id.desc()).limit(limit)
        if pipeline:
            query = query.where(SyncRun.pipeline == pipeline)
        return [SyncRunOut.model_validate(row) for row in session.scalars(query)]


@router.get("/runs/{run_id}/games", response_model=list[RunGameOut])
def list_run_games(run_id: int) -> list[RunGameOut]:
    """The games a run worked on, in the order it did. Runs from before the journal have none."""
    with session_scope() as session:
        if session.get(SyncRun, run_id) is None:
            raise HTTPException(status_code=404, detail="Run not found")
        return [RunGameOut.model_validate(row) for row in repository.list_run_games(session, run_id)]
