"""Choosing the reviews that go to the model: representative, bounded, reproducible."""

import random
from dataclasses import replace

from app.sources.base import Review

TONES = ("positive", "mixed", "negative")
MIN_PER_TONE = 3


def tone(kind: str, score: float) -> str:
    """Tone of a review on the Metacritic scale: critics 0-100, users 0-10."""
    if kind == "critics":
        return "positive" if score >= 75 else "mixed" if score >= 50 else "negative"
    return "positive" if score >= 7.5 else "mixed" if score >= 5 else "negative"


def quotas(sizes: dict[str, int], limit: int, min_each: int = MIN_PER_TONE) -> dict[str, int]:
    """How many reviews to take per tone: shares proportional to the tone's size, at least
    `min_each` from every non-empty tone."""
    taken = {t: min(n, min_each) for t, n in sizes.items()}
    spare = {t: sizes[t] - taken[t] for t in sizes}
    room = limit - sum(taken.values())
    total_spare = sum(spare.values())
    if total_spare <= room:
        return dict(sizes)  # everything fits
    if room <= 0:
        return taken

    shares = {t: room * spare[t] / total_spare for t in sizes}
    for t in sizes:
        taken[t] += int(shares[t])
    leftover = limit - sum(taken.values())
    for t in sorted(sizes, key=lambda t: shares[t] - int(shares[t]), reverse=True):
        if leftover <= 0:
            break
        if taken[t] < sizes[t]:
            taken[t] += 1
            leftover -= 1
    return taken


def build_sample(reviews: list[Review], kind: str, limit: int, text_limit: int, seed: str) -> list[Review]:
    """Deduplicated reviews of one kind: stratified by tone up to `limit`, texts cut to
    `text_limit`, order shuffled but reproducible for the same reviews and seed."""
    pool: list[Review] = []
    seen: set[str] = set()
    for review in sorted(reviews, key=lambda r: r.key):  # input order must not matter
        if review.kind != kind or review.score is None or review.key in seen:
            continue
        seen.add(review.key)
        pool.append(review)

    rng = random.Random(seed)
    groups = {t: [r for r in pool if tone(kind, r.score) == t] for t in TONES}
    take = quotas({t: len(g) for t, g in groups.items()}, limit)

    chosen: list[Review] = []
    for t in TONES:
        group = groups[t]
        rng.shuffle(group)
        chosen += group[: take[t]]
    rng.shuffle(chosen)
    # the key stays that of the full text
    return [replace(r, text=r.text[:text_limit]) for r in chosen]
