from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, field_validator


def as_utc(value: datetime | None) -> datetime | None:
    """Times are stored as naive UTC; the API always returns them with an explicit UTC offset."""
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


class SyncRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    trigger: str
    status: str
    source: str
    batch_index: int
    started_at: datetime
    finished_at: datetime | None
    games_found: int | None
    games_processed: int | None
    games_failed: int | None
    error: str | None

    _utc = field_validator("started_at", "finished_at")(as_utc)


class SyncStatus(BaseModel):
    running: bool
    interval_hours: int
    next_run_at: datetime | None
    current_run: SyncRunOut | None
    last_run: SyncRunOut | None

    _utc = field_validator("next_run_at")(as_utc)
