import threading
from datetime import datetime, timedelta

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import sessionmaker

from app.db import repository
from app.db import review_repository as repo
from app.db import session as db_session
from app.db.models import AnalysisState, ReviewSummary, SyncRun
from app.db.session import init_db, make_engine, session_scope
from app.llm import LLMError
from app.services import analysis, crawl, summaries
from app.services.pipelines import PipelineRunning, is_running
from app.sources.base import Game, OverallScore, PlatformScore, Review, ReviewBundle, ReviewStats

NOW = datetime(2026, 11, 7, 12, 0)
INTERVAL = 24  # settings.summary_min_interval_hours


class Source:
    """Serves reviews for any game; remembers what it was asked."""

    name = "fake"

    def __init__(self, fail_for: set[str] = frozenset(), short_for: set[str] = frozenset()):
        self.fail_for = set(fail_for)
        self.short_for = set(short_for)  # games with only two reviews with a text
        self.fetched: list[tuple[str, tuple[str, ...]]] = []
        self.requests_for_games = 0

    def discover(self, limit):
        return []

    def fetch_reviews(self, game: Game, kinds=("critics", "users")) -> ReviewBundle:
        self.fetched.append((game.slug, tuple(kinds)))
        if game.slug in self.fail_for:
            raise RuntimeError("review pages are down")
        reviews = [
            Review(kind=kind, text=f"{game.slug} {kind} text {i}", score=score, author=f"{kind[0]}{i}", date="Nov 1, 2026")
            for kind in kinds
            for i, score in enumerate([90, 80, 40] if kind == "critics" else [9, 8, 3])
        ]
        if game.slug in self.short_for:
            reviews = reviews[:2] + reviews[3:5]
        return ReviewBundle(reviews=reviews, stats=ReviewStats())


class LLM:
    model = "stub"

    def __init__(self, error: Exception | None = None):
        self.error = error
        self.calls = 0

    def complete(self, system: str, user: str) -> str:
        self.calls += 1
        if self.error:
            raise self.error
        return '{"likes": [{"text": "Good", "reviews": ["R1"]}], "dislikes": [{"text": "Bad", "reviews": ["R2"]}]}'


@pytest.fixture(autouse=True)
def database(tmp_path, monkeypatch):
    engine = make_engine(str(tmp_path / "analysis.db"))
    init_db(engine)
    monkeypatch.setattr(db_session, "SessionLocal", sessionmaker(engine, expire_on_commit=False))


def add_game(slug: str, critics: int | None = 10, users: int | None = 10, at: datetime = NOW) -> int:
    """A game as the crawl stores it: with the number of reviews the site showed."""
    overall = []
    if critics is not None:
        overall.append(OverallScore("critics", 80, "Generally Favorable", critics, critics, 0, 0))
    if users is not None:
        overall.append(OverallScore("users", 8.0, "Generally Favorable", users, users, 0, 0))
    game = Game(
        slug=slug,
        url=f"https://example.com/{slug}/",
        title=slug.title(),
        platforms=[PlatformScore(slug="pc", name="PC", critic_reviews_count=critics, user_reviews_count=users)],
        overall=overall,
    )
    with session_scope() as s:
        return repository.save_game(s, "fake", game, at).game_id


def queue(now=NOW, limit=10):
    with session_scope() as s:
        return repo.analysis_queue(s, "fake", now, limit, INTERVAL)


def slugs(items) -> list[str]:
    return [item.slug for item in items]


def analyze(source, llm, now=NOW, budget=None, monkeypatch=None) -> int | None:
    return analysis.run_analysis(source, "schedule", now=now, budget=budget, llm=llm)


def set_total(slug: str, kind: str, total: int, at: datetime) -> None:
    """The crawl saw a different number of reviews."""
    with session_scope() as s:
        game = repository.save_game(
            s,
            "fake",
            Game(
                slug=slug, url="u", title=slug.title(),
                platforms=[
                    PlatformScore(
                        slug="pc", name="PC",
                        critic_reviews_count=total if kind == "critics" else 10,  # the other kind is as add_game made it
                        user_reviews_count=total if kind == "users" else 10,
                    )
                ],
                overall=[OverallScore(kind, 80, "x", total, total, 0, 0)],
            ),
            at,
        )
        assert game.game_id


# ---------- the queue is chosen from the database ----------


def test_games_with_too_few_reviews_are_not_queued():
    add_game("few", critics=2, users=2)
    add_game("none", critics=None, users=None)
    add_game("enough", critics=3, users=0)
    items = queue()
    assert slugs(items) == ["enough"]
    assert list(items[0].plans) == ["critics"]  # only the kind that has enough reviews
    assert items[0].plans["critics"].total == 3


def test_never_analyzed_games_come_first_the_newest_first():
    add_game("old")
    add_game("newer")
    add_game("newest")
    assert slugs(queue()) == ["newest", "newer", "old"]


def test_the_queue_is_limited():
    for i in range(5):
        add_game(f"g{i}")
    assert len(queue(limit=2)) == 2


def test_a_checked_game_waits_for_its_reviews_to_change():
    add_game("a")
    with session_scope() as s:
        for kind in ("critics", "users"):
            repo.record_check(s, 1, kind, 10, NOW)

    assert queue(NOW + timedelta(hours=48)) == []  # nothing changed, however long ago it was

    set_total("a", "users", 25, NOW + timedelta(hours=1))
    assert queue(NOW + timedelta(hours=2)) == []  # changed, but the check is not old enough
    items = queue(NOW + timedelta(hours=25))
    assert slugs(items) == ["a"] and list(items[0].plans) == ["users"]  # only the kind that changed
    assert items[0].plans["users"].total == 25


def test_games_whose_reviews_changed_go_after_the_never_analyzed_and_the_oldest_check_first():
    for slug in ("first", "second", "fresh"):
        add_game(slug, critics=10, users=None)
    with session_scope() as s:
        repo.record_check(s, 1, "critics", 10, NOW - timedelta(days=3))
        repo.record_check(s, 2, "critics", 10, NOW - timedelta(days=5))
    set_total("first", "critics", 20, NOW)
    set_total("second", "critics", 20, NOW)
    assert slugs(queue(NOW + timedelta(days=1))) == ["fresh", "second", "first"]


def test_the_tone_split_comes_from_the_overall_score():
    add_game("a", critics=3, users=None)
    [item] = queue()
    assert item.plans["critics"].tones == {"positive": 3, "mixed": 0, "negative": 0}


def test_a_summary_of_an_older_prompt_is_queued_again_after_the_never_analyzed():
    add_game("outdated", critics=10, users=None)
    add_game("never", critics=10, users=None)
    sample = [Review(kind="critics", text=f"text {i}", score=90, author=f"a{i}", date="d") for i in range(3)]
    with session_scope() as s:
        repo.save_summary(
            s, 1, "critics", sample, 10, "m", "h", likes=[("a", [1])], dislikes=[], now=NOW, prompt_version=1
        )
        repo.record_check(s, 1, "critics", 10, NOW)
    later = NOW + timedelta(hours=1)  # the reviews did not change: only the prompt is outdated

    with session_scope() as s:
        items = repo.analysis_queue(s, "fake", later, 10, INTERVAL, prompt_version=2)
        assert slugs(items) == ["never", "outdated"]
        assert list(items[1].plans) == ["critics"]
        assert slugs(repo.analysis_queue(s, "fake", later, 10, INTERVAL, prompt_version=1)) == ["never"]


# ---------- the run ----------


def runs() -> list[SyncRun]:
    with session_scope() as s:
        return list(s.scalars(select(SyncRun).order_by(SyncRun.id)))


def summary_count() -> int:
    with session_scope() as s:
        return s.scalar(select(func.count()).select_from(ReviewSummary))


def test_a_run_builds_the_summaries_and_logs_itself_as_an_analysis():
    add_game("a")
    add_game("b")
    source, llm = Source(), LLM()
    run_id = analyze(source, llm)

    [record] = runs()
    assert record.id == run_id
    assert (record.pipeline, record.status, record.trigger) == ("analysis", "success", "schedule")
    assert (record.games_found, record.games_processed, record.games_failed) == (2, 2, 0)
    assert summary_count() == 4  # critics and users of two games
    assert llm.calls == 4


def test_a_second_run_with_nothing_changed_asks_neither_the_site_nor_the_model():
    add_game("a")
    source, llm = Source(), LLM()
    analyze(source, llm)
    source.fetched.clear()
    calls = llm.calls

    analyze(source, llm, now=NOW + timedelta(days=3))

    assert source.fetched == [] and llm.calls == calls
    assert runs()[-1].games_found == 0


def test_a_run_never_takes_more_games_than_the_budget():
    for i in range(5):
        add_game(f"g{i}")
    analyze(Source(), LLM(), budget=2)
    assert runs()[-1].games_found == 2
    with session_scope() as s:
        assert s.scalar(select(func.count()).select_from(AnalysisState)) == 4


def test_a_broken_game_does_not_stop_the_others():
    add_game("good")
    add_game("bad")
    source = Source(fail_for={"bad"})
    analyze(source, LLM())
    [record] = runs()
    assert record.status == "success"
    assert (record.games_processed, record.games_failed) == (1, 1)
    assert summary_count() == 2  # the good game's two summaries


def test_a_model_outage_does_not_use_up_the_games():
    add_game("a")
    analyze(Source(), LLM(error=LLMError("down")))
    assert summary_count() == 0
    assert [item.slug for item in queue()] == ["a"]  # still in the queue for the next run


def test_without_a_model_the_analysis_does_nothing(monkeypatch):
    add_game("a")
    monkeypatch.setattr(analysis, "make_llm_client", lambda: None)
    source = Source()
    assert analysis.run_analysis(source, "schedule", now=NOW) is None
    assert runs() == [] and source.fetched == []


def run_games(run_id: int) -> list[tuple]:
    with session_scope() as s:
        return [(g.slug, g.title, g.outcome, g.details, g.error) for g in repository_list(s, run_id)]


def repository_list(session, run_id):
    return repository.list_run_games(session, run_id)


def test_every_game_of_the_run_is_listed_with_what_happened_to_it():
    add_game("good")
    add_game("bad")
    add_game("tiny")
    run_id = analyze(Source(fail_for={"bad"}, short_for={"tiny"}), LLM())

    items = {slug: rest for slug, *rest in run_games(run_id)}
    created = {"critics": "created", "users": "created"}
    assert items["good"] == ["Good", "summarized", created, None]
    assert items["tiny"] == ["Tiny", "checked", {"critics": "too_few", "users": "too_few"}, None]  # nothing to summarize
    title, outcome, details, error = items["bad"]
    assert (title, outcome, details) == ("Bad", "failed", None) and "review pages are down" in error


def test_a_game_the_model_could_not_be_asked_about_is_listed_as_to_retry():
    add_game("a")
    run_id = analyze(Source(), LLM(error=LLMError("down")))
    [(slug, title, outcome, details, error)] = run_games(run_id)
    assert (slug, outcome, error) == ("a", "retry", None)
    assert details == {"critics": "model_unavailable", "users": "model_unavailable"}


def test_the_games_appear_in_the_journal_as_the_run_goes():
    add_game("a")
    add_game("b")
    seen: list[int] = []

    class Watching(Source):
        def fetch_reviews(self, game, kinds=("critics", "users")):
            with session_scope() as s:  # what the monitoring page would read meanwhile
                seen.append(len(repository.list_run_games(s, runs()[-1].id)))
            return super().fetch_reviews(game, kinds)

    analyze(Watching(), LLM())
    assert seen == [0, 1]  # the first game is already listed while the second is being worked on


def test_a_run_rebuilds_the_summaries_of_an_older_prompt_and_then_leaves_them_alone(monkeypatch):
    add_game("a")
    monkeypatch.setattr(summaries, "PROMPT_VERSION", 1)
    analyze(Source(), LLM())
    assert summary_count() == 2

    monkeypatch.setattr(summaries, "PROMPT_VERSION", 2)
    llm = LLM()
    analyze(Source(), llm, now=NOW + timedelta(hours=1))
    assert llm.calls == 2 and summary_count() == 4  # both kinds, as new versions
    with session_scope() as s:
        for kind in ("critics", "users"):
            assert repo.latest_summary(s, 1, kind).prompt_version == 2

    nothing = LLM()
    analyze(Source(), nothing, now=NOW + timedelta(hours=2))
    assert nothing.calls == 0  # up to date now


# ---------- the pipelines are independent ----------


def test_a_running_crawl_does_not_block_the_analysis():
    add_game("a")
    started, release = threading.Event(), threading.Event()

    class SlowCrawlSource(Source):
        def discover(self, limit):
            started.set()
            release.wait(5)
            return []

    worker = threading.Thread(target=crawl.run_crawl, args=(SlowCrawlSource(), "schedule"))
    worker.start()
    assert started.wait(5)
    try:
        assert is_running("crawl") and not is_running("analysis")
        assert analyze(Source(), LLM()) is not None  # the analysis runs while the crawl is busy
    finally:
        release.set()
        worker.join()


def test_a_second_analysis_cannot_start_while_one_is_running():
    add_game("a")
    started, release = threading.Event(), threading.Event()

    class SlowSource(Source):
        def fetch_reviews(self, game, kinds=("critics", "users")):
            started.set()
            release.wait(5)
            return super().fetch_reviews(game, kinds)

    worker = threading.Thread(target=analyze, args=(SlowSource(), LLM()))
    worker.start()
    assert started.wait(5)
    try:
        assert is_running("analysis")
        with pytest.raises(PipelineRunning):
            analyze(Source(), LLM())
    finally:
        release.set()
        worker.join()
    assert not is_running("analysis")


# ---------- the number of reviews is counted over all platforms ----------


def add_multiplatform(slug: str, critics: tuple, users: tuple, at: datetime = NOW) -> int:
    """A game with a platform per number: the review counts of each platform."""
    names = ["pc", "ps5", "switch"]
    game = Game(
        slug=slug,
        url=f"https://example.com/{slug}/",
        title=slug.title(),
        platforms=[
            PlatformScore(slug=name, name=name.upper(), critic_reviews_count=c, user_reviews_count=u)
            for name, c, u in zip(names, critics, users)
        ],
        overall=[OverallScore("critics", 80, "x", 5, 5, 0, 0), OverallScore("users", 8, "x", 9, 9, 0, 0)],
    )
    with session_scope() as s:
        return repository.save_game(s, "fake", game, at).game_id


def test_critics_are_summed_over_platforms_and_players_ratings_are_not():
    add_multiplatform("multi", critics=(5, 7, None), users=(9, 9, 9))
    [item] = queue()
    assert item.plans["critics"].total == 12  # 5 + 7: every platform has its own critic reviews
    assert item.plans["users"].total == 9  # the same number on every platform: not 27


def test_a_new_review_on_another_platform_brings_the_game_back_to_the_queue():
    game_id = add_multiplatform("multi", critics=(5, 7, None), users=(9, 9, 9))
    with session_scope() as s:
        repo.record_check(s, game_id, "critics", 12, NOW)
        repo.record_check(s, game_id, "users", 9, NOW)
    later = NOW + timedelta(hours=INTERVAL + 1)
    assert queue(later) == []  # nothing changed

    add_multiplatform("multi", critics=(5, 8, None), users=(9, 9, 9), at=later)  # one more critic on PS5
    assert slugs(queue(later)) == ["multi"]
