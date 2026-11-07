import json
from datetime import datetime, timedelta

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import sessionmaker

from app.db import repository
from app.db import review_repository as repo
from app.db import session as db_session
from app.db.models import AnalysisState
from app.db.models import Review as ReviewRow
from app.db.session import init_db, make_engine, session_scope
from app.llm import LLMError
from app.services import summaries
from app.services.summaries import SummaryError, build_prompt, parse_response
from app.sources.base import Game, PlatformScore, Review, ReviewBundle, ReviewStats

NOW = datetime(2026, 11, 7, 12, 0)

# what the queue hands over: the number of reviews and the tone split the crawl saw
CRITICS = repo.KindPlan(total=51, tones={"positive": 50, "mixed": 1})
USERS = repo.KindPlan(total=1405, tones={"positive": 1194, "mixed": 79, "negative": 132})


def make_reviews(kind: str, scores: list[int], prefix: str = "") -> list[Review]:
    return [
        Review(kind=kind, text=f"{prefix}{kind} text {i}", score=s, author=f"{kind[0]}{i}", date="Nov 1, 2026")
        for i, s in enumerate(scores)
    ]


class FakeSource:
    name = "fake"

    def __init__(self, reviews: list[Review]):
        self.reviews = reviews
        self.fetches = 0
        self.requested: list[tuple[str, ...]] = []

    def fetch_reviews(self, game: Game, kinds: tuple[str, ...] = ("critics", "users")) -> ReviewBundle:
        self.fetches += 1
        self.requested.append(tuple(kinds))
        return ReviewBundle(reviews=[r for r in self.reviews if r.kind in kinds], stats=ReviewStats())


class FakeLLM:
    model = "fake-model"

    def __init__(self, answer=None, error: Exception | None = None):
        self.answer = answer
        self.error = error
        self.prompts: list[str] = []

    def complete(self, system: str, user: str) -> str:
        self.prompts.append(user)
        if self.error:
            raise self.error
        if callable(self.answer):
            return self.answer(user)
        return self.answer or json.dumps(
            {
                "likes": [{"text": "Great combat", "reviews": ["R1", "R2"]}],
                "dislikes": [{"text": "Weak story", "reviews": ["R3"]}],
            }
        )


@pytest.fixture
def game_id(tmp_path, monkeypatch):
    engine = make_engine(str(tmp_path / "s.db"))
    init_db(engine)
    monkeypatch.setattr(db_session, "SessionLocal", sessionmaker(engine, expire_on_commit=False))
    game = Game(slug="zelda", url="u", title="Zelda", platforms=[PlatformScore(slug="pc", name="PC")])
    with session_scope() as s:
        return repository.save_game(s, "fake", game, NOW).game_id


GAME = Game(slug="zelda", url="u", title="Zelda")


def summary_count() -> int:
    with session_scope() as s:
        return s.scalar(select(func.count()).select_from(repo.ReviewSummary))


def checks() -> dict[str, tuple[datetime, int]]:
    with session_scope() as s:
        return {st.kind: (st.checked_at, st.total_reviews) for st in s.scalars(select(AnalysisState))}


def build(source, game_id, llm, plans, now=NOW) -> dict[str, str]:
    return summaries.build_summaries(source, GAME, game_id, plans, llm, now)


def test_both_summaries_are_created_with_points_linked_to_reviews(game_id):
    source = FakeSource(make_reviews("critics", [95, 90, 60, 80]) + make_reviews("users", [10, 9, 4, 8, 2]))

    assert build(source, game_id, FakeLLM(), {"critics": CRITICS, "users": USERS}) == {
        "critics": "created",
        "users": "created",
    }

    with session_scope() as session:
        critics = repo.latest_summary(session, game_id, "critics")
        users = repo.latest_summary(session, game_id, "users")
        assert (critics.sample_size, critics.total_reviews, critics.model) == (4, 51, "fake-model")
        assert (users.sample_size, users.total_reviews) == (5, 1405)
        likes = [p for p in users.points if p.kind == "like"]
        dislikes = [p for p in users.points if p.kind == "dislike"]
        assert [p.text for p in likes] == ["Great combat"]
        assert [p.text for p in dislikes] == ["Weak story"]
        assert len(likes[0].reviews) == 2 and len(dislikes[0].reviews) == 1
        assert session.scalar(select(func.count()).select_from(ReviewRow)) == 9
    assert checks() == {"critics": (NOW, 51), "users": (NOW, 1405)}  # remembered for the queue


def test_point_refers_to_the_review_the_model_cited(game_id):
    source = FakeSource(make_reviews("users", [10, 9, 4]))
    seen: dict[str, str] = {}

    def answer(prompt: str) -> str:
        seen["r2"] = next(line for line in prompt.splitlines() if line.startswith("[R2]"))
        return json.dumps({"likes": [{"text": "Fine", "reviews": ["R2"]}], "dislikes": []})

    build(source, game_id, FakeLLM(answer), {"users": USERS})

    with session_scope() as s:
        point = repo.latest_summary(s, game_id, "users").points[0]
        assert point.reviews[0].text in seen["r2"]


def test_prompt_carries_the_sentiment_and_the_critics_bias_note():
    sample = make_reviews("critics", [95, 90, 85])
    prompt = build_prompt("Zelda", "critics", sample, 51, {"positive": 50, "mixed": 1})
    assert "Sample: 3 reviews out of 51 in total." in prompt
    assert "50 positive, 1 mixed" in prompt
    assert "lean towards the highest scores" in prompt
    assert '[R1] ' in prompt and "/100" in prompt

    players = build_prompt("Zelda", "users", make_reviews("users", [9, 8, 7]), None, {})
    assert "lean towards" not in players and "/10" in players


def test_invented_review_ids_and_unsupported_points_are_dropped():
    answer = json.dumps(
        {
            "likes": [
                {"text": "Real", "reviews": ["R1", "R99", "R1"]},
                {"text": "Only invented", "reviews": ["R50"]},
                {"text": "No ids", "reviews": []},
            ],
            "dislikes": [{"text": "Ok", "reviews": ["r2", 3]}],
        }
    )
    likes, dislikes = parse_response(answer, count=3)
    assert likes == [("Real", [1])]
    assert dislikes == [("Ok", [2, 3])]


def test_answer_in_a_code_block_is_accepted():
    answer = '```json\n{"likes": [{"text": "A", "reviews": ["R1"]}], "dislikes": []}\n```'
    assert parse_response(answer, 2) == ([("A", [1])], [])


@pytest.mark.parametrize("answer", ["no json here", "{broken", '{"likes": [], "dislikes": []}', "[1, 2]"])
def test_unusable_answers_are_errors(answer):
    with pytest.raises(SummaryError):
        parse_response(answer, 3)


def test_a_sample_that_is_too_small_gives_no_summary_but_is_remembered(game_id):
    source = FakeSource(make_reviews("critics", [95, 90]))  # the site counted 3, but only 2 have a text
    llm = FakeLLM()
    assert build(source, game_id, llm, {"critics": repo.KindPlan(3, {})}) == {"critics": "too_few"}
    assert llm.prompts == []
    assert checks() == {"critics": (NOW, 3)}  # not asked about again until the number changes


def test_a_model_that_is_not_available_leaves_no_trace_so_the_next_run_tries_again(game_id):
    source = FakeSource(make_reviews("critics", [95, 90, 60]))
    result = build(source, game_id, FakeLLM(error=LLMError("down")), {"critics": CRITICS})
    assert result == {"critics": "model_unavailable"}
    assert summary_count() == 0
    assert checks() == {}


def test_an_unparsable_answer_leaves_no_summary_but_is_remembered(game_id):
    source = FakeSource(make_reviews("critics", [95, 90, 60]))
    assert build(source, game_id, FakeLLM("sorry, no"), {"critics": CRITICS}) == {"critics": "bad_answer"}
    assert summary_count() == 0
    assert checks() == {"critics": (NOW, 51)}  # the model answered: no more tokens until the reviews change


def test_the_same_sample_costs_no_tokens(game_id):
    reviews = make_reviews("users", [10, 9, 4])
    source = FakeSource(reviews)
    build(source, game_id, FakeLLM(), {"users": repo.KindPlan(1000, {})})

    llm = FakeLLM()
    later = NOW + timedelta(hours=25)
    # the site counts one more review, but our sample is the same
    assert build(source, game_id, llm, {"users": repo.KindPlan(1001, {})}, later) == {"users": "same_sample"}
    assert llm.prompts == []
    assert summary_count() == 1
    assert checks() == {"users": (later, 1001)}


def test_changed_reviews_add_a_new_version_and_reuse_the_known_ones(game_id):
    source = FakeSource(make_reviews("users", [10, 9, 4]))
    build(source, game_id, FakeLLM(), {"users": repo.KindPlan(3, {})})

    source.reviews = make_reviews("users", [10, 9, 4]) + make_reviews("users", [7], prefix="new ")
    later = NOW + timedelta(hours=25)
    assert build(source, game_id, FakeLLM(), {"users": repo.KindPlan(4, {})}, later) == {"users": "created"}

    assert summary_count() == 2
    with session_scope() as s:
        latest = repo.latest_summary(s, game_id, "users")
        assert latest.sample_size == 4
        assert latest.generated_at == later
        assert s.scalar(select(func.count()).select_from(ReviewRow)) == 4  # only the new one is added


def test_only_the_planned_kinds_are_requested(game_id):
    source = FakeSource(make_reviews("users", [10, 9, 4]) + make_reviews("critics", [90, 80, 60]))
    build(source, game_id, FakeLLM(), {"critics": CRITICS})
    assert source.requested == [("critics",)]  # the player pages are not requested
    assert set(checks()) == {"critics"}
