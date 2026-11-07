import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.db import session as db_session
from app.db.session import init_db, make_engine
from app.main import create_app
from app.services import analysis, pipelines
from app.sources.base import Game as SourceGame
from app.sources.base import Review, ReviewBundle, ReviewStats


class FakeSource:
    name = "fake"

    def discover(self, limit: int) -> list[str]:
        return ["a", "b"]

    def fetch_game(self, ref: str) -> SourceGame:
        from app.sources.base import OverallScore

        return SourceGame(
            slug=ref,
            url=f"https://example.com/{ref}/",
            title=ref,
            overall=[OverallScore("critics", 80, "x", 5, 5, 0, 0), OverallScore("users", 8, "x", 5, 5, 0, 0)],
        )

    def fetch_reviews(self, game, kinds=("critics", "users")) -> ReviewBundle:
        reviews = [
            Review(kind=kind, text=f"{kind} {i}", score=s, author=f"{kind[0]}{i}", date="Nov 1, 2026")
            for kind in kinds
            for i, s in enumerate([90, 80, 40] if kind == "critics" else [9, 8, 3])
        ]
        return ReviewBundle(reviews=reviews, stats=ReviewStats())


class StubLLM:
    model = "stub"

    def complete(self, system: str, user: str) -> str:
        return '{"likes": [{"text": "Good", "reviews": ["R1"]}], "dislikes": []}'


@pytest.fixture
def client(tmp_path, monkeypatch):
    engine = make_engine(str(tmp_path / "api.db"))
    init_db(engine)
    monkeypatch.setattr(db_session, "SessionLocal", sessionmaker(engine, expire_on_commit=False))
    with TestClient(create_app(FakeSource(), scheduler_enabled=False)) as c:
        yield c


@pytest.fixture
def model(monkeypatch):
    """A configured model: the key is set and the client is a stub."""
    monkeypatch.setattr(settings, "llm_api_key", "test-key")
    monkeypatch.setattr(analysis, "make_llm_client", lambda: StubLLM())


def test_status_of_both_pipelines_before_any_run(client):
    body = client.get("/api/sync/status").json()
    crawl, analysis_ = body["crawl"], body["analysis"]
    assert crawl["running"] is False and crawl["enabled"] is True
    assert (crawl["interval_hours"], crawl["budget"]) == (settings.crawl_interval_hours, settings.crawl_budget)
    assert (analysis_["interval_hours"], analysis_["budget"]) == (
        settings.analysis_interval_hours,
        settings.analysis_budget,
    )
    assert crawl["next_run_at"] is None and analysis_["next_run_at"] is None  # no scheduler in tests
    assert crawl["current_run"] is None and crawl["last_run"] is None


def test_the_analysis_is_off_without_a_model(client):
    assert client.get("/api/sync/status").json()["analysis"]["enabled"] is False
    response = client.post("/api/sync/run", params={"pipeline": "analysis"})
    assert response.status_code == 400 and "LLM_API_KEY" in response.json()["detail"]


def test_status_shows_the_analysis_on_with_a_model(client, model):
    assert client.get("/api/sync/status").json()["analysis"]["enabled"] is True


def test_manual_crawl_is_accepted_and_logged_as_a_crawl(client):
    assert client.post("/api/sync/run", params={"pipeline": "crawl"}).status_code == 202

    [run] = client.get("/api/sync/runs").json()
    assert (run["pipeline"], run["trigger"], run["status"], run["games_processed"]) == ("crawl", "manual", "success", 2)
    status = client.get("/api/sync/status").json()
    assert status["crawl"]["last_run"]["id"] == run["id"]
    assert status["analysis"]["last_run"] is None  # the pipelines have their own runs


def test_manual_analysis_builds_the_summaries_of_the_crawled_games(client, model):
    client.post("/api/sync/run", params={"pipeline": "crawl"})
    assert client.post("/api/sync/run", params={"pipeline": "analysis"}).status_code == 202

    runs = client.get("/api/sync/runs", params={"pipeline": "analysis"}).json()
    assert [(r["pipeline"], r["status"], r["games_processed"]) for r in runs] == [("analysis", "success", 2)]
    game = client.get("/api/games").json()["items"][0]
    assert client.get(f"/api/games/{game['id']}").json()["summaries"]["critics"]["model"] == "stub"


def test_the_pipeline_is_required_and_checked(client):
    assert client.post("/api/sync/run").status_code == 422
    assert client.post("/api/sync/run", params={"pipeline": "nope"}).status_code == 422


def test_running_crawl_gives_409_and_does_not_block_the_analysis(client, model):
    assert pipelines._locks["crawl"].acquire(blocking=False)
    try:
        status = client.get("/api/sync/status").json()
        assert status["crawl"]["running"] is True and status["analysis"]["running"] is False
        assert client.post("/api/sync/run", params={"pipeline": "crawl"}).status_code == 409
        assert client.post("/api/sync/run", params={"pipeline": "analysis"}).status_code == 202
    finally:
        pipelines._locks["crawl"].release()


def test_runs_can_be_filtered_and_are_newest_first_and_limited(client):
    for _ in range(3):
        client.post("/api/sync/run", params={"pipeline": "crawl"})
    ids = [r["id"] for r in client.get("/api/sync/runs?limit=2").json()]
    assert ids == [3, 2]
    assert client.get("/api/sync/runs", params={"pipeline": "analysis"}).json() == []


def test_times_are_returned_in_utc(client):
    client.post("/api/sync/run", params={"pipeline": "crawl"})
    [run] = client.get("/api/sync/runs").json()
    assert run["started_at"].endswith("Z") or run["started_at"].endswith("+00:00")
