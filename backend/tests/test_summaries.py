import json
from datetime import datetime, timedelta

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import sessionmaker

from app.db import repository
from app.db import review_repository as repo
from app.db import session as db_session
from app.db.models import Review as ReviewRow
from app.db.session import init_db, make_engine, session_scope
from app.llm import LLMError
from app.services import summaries
from app.services.summaries import SummaryError, build_prompt, parse_response
from app.sources.base import Game, PlatformScore, Review, ReviewBundle, ReviewStats

NOW = datetime(2026, 11, 7, 12, 0)


def make_reviews(kind: str, scores: list[int], prefix: str = "") -> list[Review]:
    return [
        Review(kind=kind, text=f"{prefix}{kind} text {i}", score=s, author=f"{kind[0]}{i}", date="Nov 1, 2026")
        for i, s in enumerate(scores)
    ]


class FakeSource:
    name = "fake"

    def __init__(self, reviews: list[Review], stats: ReviewStats | None = None):
        self.reviews = reviews
        self.stats = stats or ReviewStats()
        self.fetches = 0

    def fetch_reviews(self, game: Game) -> ReviewBundle:
        self.fetches += 1
        return ReviewBundle(reviews=list(self.reviews), stats=self.stats)


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


def test_both_summaries_are_created_with_points_linked_to_reviews(game_id):
    source = FakeSource(
        make_reviews("critics", [95, 90, 60, 80]) + make_reviews("users", [10, 9, 4, 8, 2]),
        ReviewStats(critics_total=51, users_total=1405, users_tones={"positive": 1194, "mixed": 79, "negative": 132}),
    )
    llm = FakeLLM()

    assert summaries.summarize_game(source, GAME, game_id, llm, NOW) == 2

    with session_scope() as s:
        critics = repo.latest_summary(s, game_id, "critics")
        users = repo.latest_summary(s, game_id, "users")
        assert (critics.sample_size, critics.total_reviews, critics.model) == (4, 51, "fake-model")
        assert (users.sample_size, users.total_reviews) == (5, 1405)
        likes = [p for p in users.points if p.kind == "like"]
        dislikes = [p for p in users.points if p.kind == "dislike"]
        assert [p.text for p in likes] == ["Great combat"]
        assert [p.text for p in dislikes] == ["Weak story"]
        assert len(likes[0].reviews) == 2 and len(dislikes[0].reviews) == 1
        assert s.scalar(select(func.count()).select_from(ReviewRow)) == 9


def test_point_refers_to_the_review_the_model_cited(game_id):
    source = FakeSource(make_reviews("users", [10, 9, 4]))
    seen: dict[str, str] = {}

    def answer(prompt: str) -> str:
        seen["prompt"] = prompt
        line = next(l for l in prompt.splitlines() if l.startswith("[R2]"))
        seen["r2"] = line
        return json.dumps({"likes": [{"text": "Fine", "reviews": ["R2"]}], "dislikes": []})

    summaries.summarize_game(source, GAME, game_id, FakeLLM(answer), NOW)

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


def test_too_few_reviews_give_no_summary(game_id):
    source = FakeSource(make_reviews("critics", [95, 90]))
    llm = FakeLLM()
    assert summaries.summarize_game(source, GAME, game_id, llm, NOW) == 0
    assert llm.prompts == []


def test_a_model_failure_leaves_no_summary_and_does_not_raise(game_id):
    source = FakeSource(make_reviews("critics", [95, 90, 60]))
    assert summaries.summarize_game(source, GAME, game_id, FakeLLM(error=LLMError("down")), NOW) == 0
    assert summary_count() == 0


def test_unparsable_answer_leaves_no_summary(game_id):
    source = FakeSource(make_reviews("critics", [95, 90, 60]))
    assert summaries.summarize_game(source, GAME, game_id, FakeLLM("sorry, no"), NOW) == 0
    assert summary_count() == 0


def test_summary_is_not_rebuilt_within_the_minimal_interval(game_id):
    source = FakeSource(make_reviews("users", [10, 9, 4]) + make_reviews("critics", [90, 80, 60]))
    summaries.summarize_game(source, GAME, game_id, FakeLLM(), NOW)
    fetches = source.fetches

    source.reviews = make_reviews("users", [10, 9, 4], prefix="new ") + make_reviews("critics", [95, 85, 55])
    llm = FakeLLM()
    assert summaries.summarize_game(source, GAME, game_id, llm, NOW + timedelta(hours=23)) == 0
    assert source.fetches == fetches  # not even the review pages are requested
    assert llm.prompts == []


def test_a_kind_without_a_summary_is_tried_again_next_time(game_id):
    source = FakeSource(make_reviews("users", [10, 9, 4]))  # no critic reviews yet
    summaries.summarize_game(source, GAME, game_id, FakeLLM(), NOW)

    source.reviews += make_reviews("critics", [90, 80, 60])
    assert summaries.summarize_game(source, GAME, game_id, FakeLLM(), NOW + timedelta(hours=1)) == 1
    with session_scope() as s:
        assert repo.latest_summary(s, game_id, "critics") is not None


def test_unchanged_reviews_after_the_interval_keep_the_summary(game_id):
    source = FakeSource(make_reviews("users", [10, 9, 4]))
    summaries.summarize_game(source, GAME, game_id, FakeLLM(), NOW)

    llm = FakeLLM()
    assert summaries.summarize_game(source, GAME, game_id, llm, NOW + timedelta(hours=25)) == 0
    assert llm.prompts == []
    assert summary_count() == 1


def test_changed_reviews_after_the_interval_add_a_new_version(game_id):
    source = FakeSource(make_reviews("users", [10, 9, 4]))
    summaries.summarize_game(source, GAME, game_id, FakeLLM(), NOW)

    source.reviews = make_reviews("users", [10, 9, 4]) + make_reviews("users", [7], prefix="new ")
    assert summaries.summarize_game(source, GAME, game_id, FakeLLM(), NOW + timedelta(hours=25)) == 1

    assert summary_count() == 2
    with session_scope() as s:
        latest = repo.latest_summary(s, game_id, "users")
        assert latest.sample_size == 4
        assert latest.generated_at == NOW + timedelta(hours=25)
        # the three old reviews are reused, only the new one is added
        assert s.scalar(select(func.count()).select_from(ReviewRow)) == 4
