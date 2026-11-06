import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from app.db import session as db_session
from app.db.session import init_db, make_engine
from app.main import create_app
from app.services import sync
from app.sources.base import Game as SourceGame


class FakeSource:
    name = "fake"

    def list_batch(self, batch_index: int, limit: int) -> list[str]:
        return ["a", "b"]

    def fetch_game(self, ref: str) -> SourceGame:
        return SourceGame(slug=ref, url=f"https://example.com/{ref}/", title=ref)


@pytest.fixture
def client(tmp_path, monkeypatch):
    engine = make_engine(str(tmp_path / "api.db"))
    init_db(engine)
    monkeypatch.setattr(db_session, "SessionLocal", sessionmaker(engine, expire_on_commit=False))
    with TestClient(create_app(FakeSource(), scheduler_enabled=False)) as c:
        yield c


def test_status_before_any_run(client):
    body = client.get("/api/sync/status").json()
    assert body["running"] is False
    assert body["interval_hours"] == 1
    assert body["next_run_at"] is None  # scheduler is disabled in tests
    assert body["current_run"] is None and body["last_run"] is None


def test_manual_run_is_accepted_and_logged(client):
    assert client.post("/api/sync/run").status_code == 202

    [run] = client.get("/api/sync/runs").json()
    assert (run["trigger"], run["status"], run["games_processed"]) == ("manual", "success", 2)
    assert client.get("/api/sync/status").json()["last_run"]["id"] == run["id"]


def test_manual_run_while_running_returns_409(client):
    assert sync._lock.acquire(blocking=False)
    try:
        assert client.get("/api/sync/status").json()["running"] is True
        assert client.post("/api/sync/run").status_code == 409
    finally:
        sync._lock.release()


def test_runs_are_newest_first_and_limited(client):
    for _ in range(3):
        client.post("/api/sync/run")
    ids = [r["id"] for r in client.get("/api/sync/runs?limit=2").json()]
    assert ids == [3, 2]


def test_times_are_returned_in_utc(client):
    client.post("/api/sync/run")
    [run] = client.get("/api/sync/runs").json()
    assert run["started_at"].endswith("Z") or run["started_at"].endswith("+00:00")
