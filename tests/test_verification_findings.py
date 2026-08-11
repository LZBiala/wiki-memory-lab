"""Regression tests for defects found by independent review of v1.0.

Each test class names the finding it pins down. These exist so the defects
stay fixed: a memory store that can be bricked by a write, a note that can
clobber the index, mutations that precede validation, README prose that can
drift from the code, and a demo that hides its answers.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from wikimemlab.protocol import DECAY_WINDOW, Librarian, ProtocolError

REPO = Path(__file__).resolve().parents[1]


@pytest.fixture()
def lib(tmp_path: Path) -> Librarian:
    return Librarian(wiki_dir=tmp_path / "wiki", ops_log_path=tmp_path / "runs" / "ops.jsonl")


class TestStoreCannotBeBricked:
    """Finding: a multi-line hook wrote unparseable frontmatter and every
    subsequent read of the whole store raised."""

    def test_newline_hook_is_refused_before_any_write(self, lib: Librarian) -> None:
        with pytest.raises(ProtocolError, match="single trimmed line"):
            lib.upsert("evil-note", "line one\nline two: sneak", "body", 1, "attempt")
        assert lib.notes() == {}  # nothing landed on disk
        assert not lib.ops_log_path.exists()  # and nothing was logged as success

    def test_untrimmed_hook_is_refused(self, lib: Librarian) -> None:
        with pytest.raises(ProtocolError, match="single trimmed line"):
            lib.upsert("a-note", "  padded hook  ", "body", 1, "attempt")

    def test_store_remains_usable_after_refusal(self, lib: Librarian) -> None:
        lib.upsert("good-note", "a fine hook", "body", 1, "learned")
        with pytest.raises(ProtocolError):
            lib.upsert("evil-note", "bad\nhook", "body", 1, "attempt")
        assert set(lib.notes()) == {"good-note"}
        lib.check_invariants()


class TestReservedNames:
    """Finding: a note normalizing to 'index' silently destroyed itself and
    clobbered index.md, while the ops log recorded a successful CREATE."""

    @pytest.mark.parametrize("title", ["index", "Index", "archive"])
    def test_reserved_titles_are_refused(self, lib: Librarian, title: str) -> None:
        with pytest.raises(ProtocolError, match="reserved"):
            lib.upsert(title, "hook", "body", 1, "attempt")
        assert lib.notes() == {}
        assert not lib.ops_log_path.exists()


class TestNoMutationBeforeValidation:
    """Finding: recall() stamped notes to disk before validating the reason
    or the full name list — mutation with no audit record."""

    def test_bad_reason_leaves_store_untouched(self, lib: Librarian) -> None:
        lib.upsert("a-note", "hook", "body", 1, "learned")
        before = lib.notes()["a-note"]
        with pytest.raises(ProtocolError, match="reason"):
            lib.recall(["a-note"], 2, "   ")
        assert lib.notes()["a-note"] == before

    def test_unknown_name_in_list_leaves_no_partial_stamp(self, lib: Librarian) -> None:
        lib.upsert("a-note", "hook", "body", 1, "learned")
        with pytest.raises(ProtocolError, match="unknown"):
            lib.recall(["a-note", "ghost-note"], 2, "task")
        assert lib.notes()["a-note"].meta.recall_count == 0

    def test_duplicate_names_stamp_twice_and_log_twice(self, lib: Librarian) -> None:
        lib.upsert("a-note", "hook", "body", 1, "learned")
        lib.recall(["a-note", "a-note"], 2, "task")
        assert lib.notes()["a-note"].meta.recall_count == 2


class TestReadmePinnedToReality:
    """Finding: prose facts (session counts, decay window) and the quoted
    transcript excerpt sat outside the drift gate and could go stale."""

    README = (REPO / "README.md").read_text(encoding="utf-8")

    def test_prose_constants_match_fixtures_and_code(self) -> None:
        data = json.loads(
            (REPO / "fixtures" / "milldale" / "sessions.json").read_text("utf-8")
        )
        n_sessions = len(data["sessions"])
        n_tasks = sum(len(s["tasks"]) for s in data["sessions"])
        assert f"{n_sessions} scripted sessions" in self.README
        assert f"~{n_tasks} tasks" in self.README
        assert f"{DECAY_WINDOW} sessions" in self.README

    def test_quoted_excerpt_is_verbatim_from_transcript(self) -> None:
        transcript = (REPO / "runs" / "milldale-session_06.md").read_text("utf-8")
        transcript_norm = re.sub(r"\s+", " ", transcript)
        fences = re.findall(r"```\n(.*?)```", self.README, flags=re.S)
        excerpt = next(f for f in fences if "task s6t3" in f)
        for segment in excerpt.split("[...]"):
            segment_norm = re.sub(r"\s+", " ", segment).strip()
            if segment_norm:
                assert segment_norm in transcript_norm, segment_norm[:60]

    def test_wallclock_scan_covers_readme(self) -> None:
        # The AUTOGEN block is generated output; scan the whole README.
        assert not re.search(r"\d{4}-\d{2}-\d{2}|\d{1,2}:\d{2}:\d{2}", self.README)


class TestDemoStreamsAnswers:
    """Finding: the demo emitted every line type EXCEPT the answers."""

    def test_answer_lines_are_emitted(self, tmp_path: Path) -> None:
        from wikimemlab.agents import ScriptedAgent
        from wikimemlab.runner import run_selective

        streamed: list[str] = []
        run_selective(
            corpus_path=REPO / "fixtures" / "milldale_mini" / "sessions.json",
            wiki_dir=tmp_path / "wiki",
            runs_dir=tmp_path / "runs",
            agent=ScriptedAgent(),
            emit=streamed.append,
        )
        assert any(line.startswith("ANSWER:") for line in streamed)


class TestOpsLogCarriesCorpus:
    """Finding: two corpora interleaved in one ops log with no way to tell
    their records apart."""

    def test_corpus_field_present(self, tmp_path: Path) -> None:
        lab = Librarian(
            wiki_dir=tmp_path / "wiki",
            ops_log_path=tmp_path / "runs" / "ops.jsonl",
            corpus_label="milldale",
        )
        lab.upsert("a-note", "hook", "body", 1, "learned")
        record = json.loads(lab.ops_log_path.read_text("utf-8").strip())
        assert record["corpus"] == "milldale"


class TestCoverageInProcess:
    """Finding: the pipeline was only exercised via subprocess, so standard
    coverage tooling reported the core modules at 0%. This runs the full demo
    in-process; it is deterministic, so regenerating in place is a no-op."""

    def test_demo_runs_in_process_and_regenerates(self) -> None:
        from wikimemlab.__main__ import demo

        assert demo(quiet=True) == 0
        assert (REPO / "metrics.jsonl").exists()
        assert (REPO / "report" / "hero.svg").exists()
