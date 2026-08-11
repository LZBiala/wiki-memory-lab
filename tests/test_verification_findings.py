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
        records = [
            json.loads(line)
            for line in lib.ops_log_path.read_text("utf-8").splitlines()
            if line
        ]
        assert sum(1 for r in records if r["op"] == "RECALL") == 2


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


class TestBlocklistSeparatorVariants:
    """Finding: multi-part banned terms spelled with underscores, spaces,
    dots, slashes, or no separator evaded the token matcher. Verified here
    with a synthetic term so no real banned vocabulary appears in this file."""

    def test_all_separator_spellings_are_caught(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "blocklist_check", REPO / "tools" / "blocklist_check.py"
        )
        assert spec is not None and spec.loader is not None
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        synthetic = {mod._hash("zz-audit-probe"), mod._hash("zzauditprobe")}
        monkeypatch.setattr(mod, "HASHED_TERMS", frozenset(synthetic))
        for spelling in (
            "zz-audit-probe",
            "zz_audit_probe",
            "zz audit probe",
            "zz.audit.probe",
            "zz/audit/probe",
            "zzauditprobe",
            "prefix zz_audit_probe suffix",
        ):
            assert mod._token_hits(spelling), spelling
        assert not mod._token_hits("an innocent line about the town bakery")


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


class TestExtendAfterEmptyBody:
    """Finding: extending a note created with an empty body was spuriously
    refused by the write-time round-trip guard (a manufactured leading
    newline). The merge now strips it."""

    def test_empty_body_note_can_be_extended(self, lib: Librarian) -> None:
        op1, _ = lib.upsert("empty-note", "a hook", "", 1, "created empty")
        op2, _ = lib.upsert("empty-note", "ignored", "now some content", 2, "filled in")
        assert (op1, op2) == ("CREATE", "EXTEND")
        assert lib.notes()["empty-note"].body == "now some content"


class TestCoverageInProcess:
    """Finding: the pipeline was only exercised via subprocess, so standard
    coverage tooling reported the core modules at 0%. This runs the full demo
    in-process — against a TEMP COPY of the repo layout (fixtures + README),
    never the real working tree, so an interrupted test cannot leave committed
    artifacts deleted mid-regeneration."""

    def test_demo_runs_in_process_and_regenerates(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import shutil

        import wikimemlab.__main__ as main_mod

        shutil.copytree(REPO / "fixtures", tmp_path / "fixtures")
        shutil.copy(REPO / "README.md", tmp_path / "README.md")
        monkeypatch.setattr(main_mod, "FIXTURES", tmp_path / "fixtures")
        monkeypatch.setattr(main_mod, "README", tmp_path / "README.md")
        monkeypatch.setattr(main_mod, "WIKI_DIR", tmp_path / "wiki")
        monkeypatch.setattr(main_mod, "RUNS_DIR", tmp_path / "runs")
        monkeypatch.setattr(main_mod, "REPORT_DIR", tmp_path / "report")
        monkeypatch.setattr(main_mod, "METRICS", tmp_path / "metrics.jsonl")

        assert main_mod.demo(quiet=True) == 0
        assert (tmp_path / "metrics.jsonl").exists()
        assert (tmp_path / "report" / "hero.svg").exists()
        assert (tmp_path / "report" / "cumulative.svg").exists()
        # The temp regeneration must be byte-identical to the committed goldens.
        committed = (REPO / "metrics.jsonl").read_bytes()
        assert (tmp_path / "metrics.jsonl").read_bytes() == committed
