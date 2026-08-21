"""Contract tests for the strict frontmatter subset.

The guarantees under test:
1. render() -> parse_note() round-trips byte-identically (determinism).
2. Unknown, duplicate, or missing keys are ERRORS, never warnings.
3. Session fields are non-negative integers (logical time only).
4. normalize_title is the dumb, documented matcher - no cleverness.
"""
from __future__ import annotations

import pytest

from wikimemlab.frontmatter import (
    FrontmatterError,
    Note,
    NoteMeta,
    normalize_title,
    parse_note,
)


def make_note(**overrides: object) -> Note:
    meta = NoteMeta(
        name="bakery-hours",
        hook="Opening hours for the Milldale bakery on Main Street",
        created_session=1,
        last_recalled_session=0,
        recall_count=0,
    )
    body = "Opens 7am weekdays.\nSee also [[town-map]]."
    fields = {"meta": meta, "body": body}
    fields.update(overrides)  # type: ignore[arg-type]
    return Note(**fields)  # type: ignore[arg-type]


class TestRoundTrip:
    def test_render_parse_round_trip_is_identity(self) -> None:
        note = make_note()
        assert parse_note(note.render()) == note

    def test_render_twice_is_byte_identical(self) -> None:
        note = make_note()
        assert note.render() == note.render()

    def test_render_uses_lf_only(self) -> None:
        assert "\r" not in make_note().render()

    def test_trailing_newlines_in_body_are_normalized(self) -> None:
        a = make_note(body="line one\n\n\n")
        b = make_note(body="line one")
        assert parse_note(a.render()) == parse_note(b.render())


class TestStrictness:
    def test_unknown_key_is_an_error(self) -> None:
        text = make_note().render().replace("recall_count: 0", "recall_count: 0\ncreated: 2026")
        with pytest.raises(FrontmatterError, match="unknown"):
            parse_note(text)

    def test_missing_key_is_an_error(self) -> None:
        text = make_note().render().replace("recall_count: 0\n", "")
        with pytest.raises(FrontmatterError, match="missing"):
            parse_note(text)

    def test_duplicate_key_is_an_error(self) -> None:
        text = make_note().render().replace("recall_count: 0", "recall_count: 0\nrecall_count: 1")
        with pytest.raises(FrontmatterError, match="duplicate"):
            parse_note(text)

    def test_non_integer_session_is_an_error(self) -> None:
        text = make_note().render().replace("created_session: 1", "created_session: one")
        with pytest.raises(FrontmatterError, match="integer"):
            parse_note(text)

    def test_negative_session_is_an_error(self) -> None:
        text = make_note().render().replace("recall_count: 0", "recall_count: -1")
        with pytest.raises(FrontmatterError, match=">= 0"):
            parse_note(text)

    def test_missing_opening_delimiter_is_an_error(self) -> None:
        with pytest.raises(FrontmatterError, match="start"):
            parse_note("name: x\n")

    def test_unterminated_block_is_an_error(self) -> None:
        with pytest.raises(FrontmatterError, match="unterminated"):
            parse_note("---\nname: x\n")

    def test_non_kebab_name_is_an_error(self) -> None:
        text = make_note().render().replace("name: bakery-hours", "name: Bakery Hours")
        with pytest.raises(FrontmatterError, match="kebab"):
            parse_note(text)


class TestNormalizeTitle:
    @pytest.mark.parametrize(
        ("title", "expected"),
        [
            ("Bakery Hours", "bakery-hours"),
            ("bakery-hours", "bakery-hours"),
            ("  Bakery   Hours  ", "bakery-hours"),
            ("Bakery_Hours!", "bakery-hours"),
        ],
    )
    def test_normalization(self, title: str, expected: str) -> None:
        assert normalize_title(title) == expected

    def test_paraphrases_do_not_normalize_together(self) -> None:
        # The documented limitation: the matcher is exact, so a paraphrased
        # duplicate becomes a second note (counted as false-CREATE upstream).
        assert normalize_title("clinic hours") != normalize_title("walk-in clinic hours")

    def test_empty_title_is_an_error(self) -> None:
        with pytest.raises(FrontmatterError):
            normalize_title("!!!")


class TestLinks:
    def test_links_are_extracted_sorted_unique(self) -> None:
        note = make_note(body="See [[town-map]] and [[bus-route-7]] and [[town-map]].")
        assert note.links() == ["bus-route-7", "town-map"]
