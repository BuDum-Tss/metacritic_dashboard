from fastapi import APIRouter

from app.api.schemas import DashboardOut
from app.db import dashboard, repository
from app.db.session import session_scope

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("", response_model=DashboardOut)
def get_dashboard() -> DashboardOut:
    with session_scope() as session:
        return DashboardOut(**dashboard.build(session, repository.utcnow()))
