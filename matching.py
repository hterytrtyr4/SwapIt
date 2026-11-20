"""Smart swap matching engine (pure Python, no external services).

The goal: given a listing that *offers* item X and *wants* item Y, find
other users' listings that could complete a mutual exchange. All scores
come from the real database content — nothing is fabricated.

Score pipeline (0-100):
    1. Text normalisation (lowercase, punctuation strip, stopword removal).
    2. Token coverage  - how much of "wanted" text is covered by the other
       item's title/description/category (fuzzy token equality).
    3. Sequence similarity - difflib ratio over normalised strings.
    4. Category hint    - small boost when categories line up with the
       wanted text.
    5. A pair score is the geometric mean of both directions, so a
       one-sided match can never rank as a strong *mutual* match.
"""
from __future__ import annotations

import math
import re
from difflib import SequenceMatcher

STOPWORDS = {
    "a", "an", "and", "any", "are", "as", "at", "be", "by", "can", "do", "for",
    "from", "get", "give", "i", "if", "in", "into", "is", "it", "its", "like",
    "looking", "me", "mine", "my", "need", "needs", "of", "on", "one", "or",
    "our", "please", "some", "that", "the", "their", "them", "then", "this",
    "to", "trade", "up", "want", "wants", "with", "would", "you", "your",
    "exchange", "swap", "swapping", "buy", "purchase",
}

_NON_ALNUM = re.compile(r"[^a-z0-9\s]+")
_WS = re.compile(r"\s+")

# Weights for a single direction ("does item B satisfy A's wanted text?")
W_TOKEN = 0.55
W_SEQ = 0.45
PHRASE_BONUS = 8
CATEGORY_BONUS = 12

# Display threshold: pairs scoring below this are not surfaced as matches.
MATCH_THRESHOLD = 45


def normalize(text: str) -> str:
    """Lowercase, strip punctuation, drop stopwords, collapse whitespace."""
    if not text:
        return ""
    text = _NON_ALNUM.sub(" ", text.lower())
    tokens = [t for t in _WS.split(text) if t and t not in STOPWORDS]
    return " ".join(tokens)


def tokenize(text: str) -> list[str]:
    norm = normalize(text)
    return norm.split() if norm else []


def item_text(item) -> str:
    """All searchable text of a listing."""
    return f"{item.title} {item.description} {item.category} {item.condition}"


def _token_coverage(want_tokens: list[str], have_tokens: list[str]) -> float:
    """Fraction of wanted tokens found (fuzzily) among the item's tokens."""
    if not want_tokens:
        return 0.0
    if not have_tokens:
        return 0.0
    total = 0.0
    for w in want_tokens:
        best = 0.0
        for h in have_tokens:
            if w == h:
                best = 1.0
                break
            if w in h or h in w:  # 'book' vs 'books', 'physics' vs 'physicslab'
                best = max(best, 0.9)
                continue
            ratio = SequenceMatcher(None, w, h).ratio()
            best = max(best, ratio)
        if best >= 0.72:
            total += min(best, 1.0)
    return total / len(want_tokens)


def satisfy_score(wanted_text: str, item) -> float:
    """Score 0-100: how well `item` satisfies `wanted_text`."""
    want_norm = normalize(wanted_text)
    have_norm = normalize(item_text(item))
    if not want_norm or not have_norm:
        return 0.0

    want_tokens = want_norm.split()
    have_tokens = have_norm.split()

    coverage = _token_coverage(want_tokens, have_tokens)
    seq = SequenceMatcher(None, want_norm, have_norm).ratio()

    score = 100.0 * (W_TOKEN * coverage + W_SEQ * seq)

    # Phrase-level containment ("engineering book" inside the item text).
    if want_norm in have_norm or have_norm in want_norm:
        score += PHRASE_BONUS

    # Category hint: wanted text mentions the item's category word.
    cat = normalize(item.category)
    if cat and cat in want_norm:
        score += CATEGORY_BONUS

    return min(score, 100.0)


def pair_score(my_item, their_item) -> tuple[float, float, float]:
    """Mutual match score for `my_item` vs `their_item`.

    Returns (overall, direction_for_me, direction_for_them).
    """
    mine = satisfy_score(my_item.wanted_item, their_item)   # do they have what I want?
    theirs = satisfy_score(their_item.wanted_item, my_item)  # do I have what they want?
    overall = math.sqrt(mine * theirs)  # geometric mean => penalises one-sidedness
    return overall, mine, theirs


def find_matches_for_user(user, all_items, limit: int = 20) -> list[dict]:
    """Potential mutual matches between `user`'s available items and other
    users' available items. Every result is derived from real listings.

    Each result dict:
        my_item, their_item, owner_name, score, my_side, their_side
    """
    my_items = [
        i for i in all_items
        if i.user_id == user.id and i.status == "available"
    ]
    other_items = [
        i for i in all_items
        if i.user_id != user.id and i.status == "available"
    ]

    results: list[dict] = []
    for mine in my_items:
        for theirs in other_items:
            overall, side_me, side_them = pair_score(mine, theirs)
            if overall >= MATCH_THRESHOLD:
                results.append(
                    {
                        "my_item": mine,
                        "their_item": theirs,
                        "owner_name": theirs.user.name,
                        "score": round(overall),
                        "my_side": round(side_me),
                        "their_side": round(side_them),
                    }
                )

    results.sort(key=lambda r: r["score"], reverse=True)
    return results[:limit]


def score_between_items(item_a, item_b) -> int:
    """Convenience helper: overall mutual score between two listings."""
    return round(pair_score(item_a, item_b)[0])
