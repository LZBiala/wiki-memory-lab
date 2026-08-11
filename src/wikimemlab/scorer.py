"""Lexical hook scorer: the whole retrieval story, kept dumb on purpose.

recall(task_text) works by exact word overlap between the task and each
index line (note name words count double, hook words count single). No
stemming, no embeddings, no fuzziness — so "open" does not match "opening"
and "park" does not match "parking". Those misses are demonstrated in the
fixtures rather than papered over: a memory system's index is only as good
as its hooks, and the deliberately-bad-hook note in the corpus shows exactly
what a lazy hook costs.

Constants are named and fixed; changing them changes published numbers, and
CI will fail the build until the committed artifacts are regenerated.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from wikimemlab.frontmatter import NoteMeta

TOP_K = 3
MIN_SCORE = 2
NAME_WEIGHT = 2
HOOK_WEIGHT = 1

_WORD_RE = re.compile(r"[a-z0-9']+")

# Tiny fixed stopword list: common glue words that would otherwise let every
# hook match every task. Deliberately short and visible.
STOPWORDS = frozenset(
    (
        "a an and are at by can do does for from how i in is it of on or the to "
        "what when where which who will you your"
    ).split()
)


def words(text: str) -> frozenset[str]:
    return frozenset(_WORD_RE.findall(text.lower())) - STOPWORDS


@dataclass(frozen=True)
class Scored:
    name: str
    score: int


def score_note(task_words: frozenset[str], meta: NoteMeta) -> int:
    name_words = words(meta.name.replace("-", " "))
    hook_words = words(meta.hook) - name_words
    return NAME_WEIGHT * len(task_words & name_words) + HOOK_WEIGHT * len(
        task_words & hook_words
    )


def recall_names(task_text: str, metas: list[NoteMeta]) -> list[str]:
    """Top-k note names for a task, deterministic: score desc, then name asc."""
    task_words = words(task_text)
    scored = [Scored(m.name, score_note(task_words, m)) for m in metas]
    eligible = [s for s in scored if s.score >= MIN_SCORE]
    eligible.sort(key=lambda s: (-s.score, s.name))
    return [s.name for s in eligible[:TOP_K]]
