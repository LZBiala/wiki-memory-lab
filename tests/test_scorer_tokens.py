"""Contract tests for the lexical scorer and the token proxy.

Guarantees: deterministic ordering (score desc, name asc), the MIN_SCORE
threshold, the documented no-stemming limitation, and the chars/4 proxy.
"""
from __future__ import annotations

import pytest

from wikimemlab.frontmatter import NoteMeta
from wikimemlab.scorer import MIN_SCORE, TOP_K, recall_names, score_note, words
from wikimemlab.tokens import proxy_tokens


def meta(name: str, hook: str) -> NoteMeta:
    return NoteMeta(
        name=name, hook=hook, created_session=1, last_recalled_session=0, recall_count=0
    )


BAKERY = meta("bakery-hours", "Opening hours for the Milldale bakery on Main Street")
MARKET = meta("farmers-market", "The Saturday farmers market on the town square")
BAD_HOOK = meta("town-history", "assorted notes")  # the deliberately lazy hook


class TestScoring:
    def test_name_words_count_double(self) -> None:
        task = words("what time does the bakery open")
        # 'bakery' hits the name (2) - 'open' does NOT match 'opening' (no stemming)
        assert score_note(task, BAKERY) == 2

    def test_hook_words_count_single(self) -> None:
        task = words("directions to main street")
        # 'main' + 'street' are hook-only words
        assert score_note(task, BAKERY) == 2

    def test_no_stemming_is_a_real_limitation(self) -> None:
        task = words("where can i park near the river")
        riverside_park = meta("riverside-park", "Picnic tables and trails")
        # 'park' matches the NAME word 'park' exactly -> the known imprecision
        assert score_note(task, riverside_park) == 2
        # but 'parking' in a name would NOT match 'park':
        parking = meta("riverside-parking", "Gravel lot")
        assert score_note(task, parking) == 0

    def test_bad_hook_scores_zero_on_its_own_topic(self) -> None:
        task = words("when was the old mill founded")
        assert score_note(task, BAD_HOOK) == 0


class TestRecall:
    def test_threshold_excludes_weak_matches(self) -> None:
        names = recall_names("what time does the bakery open", [BAKERY, MARKET, BAD_HOOK])
        assert names == ["bakery-hours"]

    def test_deterministic_tie_break_by_name(self) -> None:
        a = meta("apple-stand", "fresh apples daily")
        b = meta("berry-stand", "fresh berries daily")
        names = recall_names("who has fresh fruit daily", [b, a])
        assert names == ["apple-stand", "berry-stand"]  # equal score -> name asc

    def test_top_k_cap(self) -> None:
        metas = [meta(f"note-{i}", "the annual town parade route") for i in range(6)]
        names = recall_names("where does the annual parade route go", metas)
        assert len(names) == TOP_K

    def test_min_score_is_at_least_two(self) -> None:
        # A single stray hook-word hit must not trigger recall.
        assert MIN_SCORE >= 2


class TestProxyTokens:
    @pytest.mark.parametrize(
        ("text", "expected"),
        [("", 0), ("abcd", 1), ("abcde", 2), ("a" * 400, 100)],
    )
    def test_chars_over_four(self, text: str, expected: int) -> None:
        assert proxy_tokens(text) == expected
