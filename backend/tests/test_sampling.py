from collections import Counter
from random import Random

from app.services.sampling import build_sample, quotas, tone
from app.sources.base import Review


def reviews(kind: str, scores: list[int]) -> list[Review]:
    return [
        Review(kind=kind, text=f"{kind} review number {i} " + "x" * 50, score=score, author=f"a{i}", date="Nov 1, 2026")
        for i, score in enumerate(scores)
    ]


def test_tone_on_the_metacritic_scale():
    assert [tone("critics", s) for s in (100, 75, 74, 50, 49, 0)] == [
        "positive", "positive", "mixed", "mixed", "negative", "negative"
    ]
    assert [tone("users", s) for s in (10, 8, 7, 5, 4, 0)] == [
        "positive", "positive", "mixed", "mixed", "negative", "negative"
    ]


def test_quotas_take_everything_when_it_fits():
    assert quotas({"positive": 10, "mixed": 5, "negative": 2}, limit=40) == {"positive": 10, "mixed": 5, "negative": 2}


def test_quotas_are_proportional_with_a_minimum_per_tone():
    taken = quotas({"positive": 800, "mixed": 100, "negative": 20}, limit=40)
    assert sum(taken.values()) == 40
    assert taken["negative"] >= 3 and taken["mixed"] >= 3
    assert taken["positive"] > taken["mixed"] > taken["negative"]


def test_quotas_never_exceed_the_size_of_a_tone():
    taken = quotas({"positive": 100, "mixed": 100, "negative": 1}, limit=40)
    assert taken["negative"] == 1
    assert sum(taken.values()) == 40


def test_sample_respects_the_limit_and_keeps_every_tone():
    pool = reviews("users", [10] * 60 + [6] * 8 + [2] * 5)
    sample = build_sample(pool, "users", limit=30, text_limit=600, seed="1:users")
    assert len(sample) == 30
    tones = Counter(tone("users", r.score) for r in sample)
    assert tones["mixed"] >= 3 and tones["negative"] >= 3


def test_sample_keeps_only_the_wanted_kind_and_drops_duplicates():
    pool = reviews("critics", [90, 80]) + reviews("users", [9, 9, 9])
    pool += pool[:1]  # the same critic review twice
    sample = build_sample(pool, "critics", limit=30, text_limit=600, seed="1:critics")
    assert sorted(r.score for r in sample) == [80, 90]


def test_sample_drops_reviews_without_a_score():
    pool = reviews("users", [9, 8, 7]) + [Review(kind="users", text="no score", score=None)]
    assert len(build_sample(pool, "users", limit=30, text_limit=600, seed="s")) == 3


def test_sample_is_reproducible_whatever_the_input_order():
    pool = reviews("users", [10] * 50 + [6] * 10 + [1] * 6)
    shuffled = pool[:]
    Random(7).shuffle(shuffled)
    first = build_sample(pool, "users", limit=30, text_limit=600, seed="5:users")
    second = build_sample(shuffled, "users", limit=30, text_limit=600, seed="5:users")
    assert [r.key for r in first] == [r.key for r in second]


def test_long_text_is_cut_but_the_key_stays_the_same():
    [review] = reviews("users", [9])
    review.text = "y" * 2000
    [cut] = build_sample([review], "users", limit=30, text_limit=600, seed="s")
    assert len(cut.text) == 600
    assert cut.key == review.key
