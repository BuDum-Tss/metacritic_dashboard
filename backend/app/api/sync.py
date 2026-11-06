import logging

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Request
from sqlalchemy import select

from app.api.schemas import SyncRunOut, SyncStatus
from app.config import settings
from app.db.models import SyncRun
from app.db.session import session_scope
from app.scheduler import JOB_ID
from app.services import sync
from app.sources.base import GameSource

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/sync", tags=["sync"])


def _run_manually(source: GameSource) -> None:
    try:
        sync.run_cycle(source, "manual")
    except sync.SyncAlreadyRunning:
        log.info("manual sync skipped: a cycle is already running")


@router.get("/status", response_model=SyncStatus)
def get_status(request: Request) -> SyncStatus:
    scheduler = request.app.state.scheduler
    job = scheduler.get_job(JOB_ID) if scheduler else None

    with session_scope() as session:
        runs = select(SyncRun).order_by(SyncRun.id.desc())
        current = session.scalar(runs.where(SyncRun.status == "running"))
        last = session.scalar(runs.where(SyncRun.status != "running"))
        return SyncStatus(
            running=sync.is_running(),
            interval_hours=settings.sync_interval_hours,
            next_run_at=job.next_run_time if job else None,
            current_run=SyncRunOut.model_validate(current) if current else None,
            last_run=SyncRunOut.model_validate(last) if last else None,
        )


@router.post("/run", status_code=202)
def run_now(request: Request, background: BackgroundTasks) -> dict:
    if sync.is_running():
        raise HTTPException(status_code=409, detail="A sync cycle is already running")
    background.add_task(_run_manually, request.app.state.source)
    return {"status": "accepted"}


@router.get("/runs", response_model=list[SyncRunOut])
def list_runs(limit: int = Query(20, ge=1, le=200)) -> list[SyncRunOut]:
    with session_scope() as session:
        rows = session.scalars(select(SyncRun).order_by(SyncRun.id.desc()).limit(limit))
        return [SyncRunOut.model_validate(row) for row in rows]
