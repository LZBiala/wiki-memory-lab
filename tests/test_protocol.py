"""Contract tests for the librarian.

Guarantees: extend-before-create routing (including the honest paraphrase
false-CREATE), mandatory reasons, prune/tombstone mechanics, the exact decay
window edge, index/disk consistency, and orphan-link detection.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from wikimemlab.protocol import DECAY_WINDOW, Librarian, ProtocolError


@pytest.fixture()
def lib(tmp_path: Path) -> Librarian:
    return Librarian(wiki_dir=tmp_path / "wiki", ops_log_path=tmp_path / "runs" / "ops.jsonl")


def ops(lib: Librarian) -> list[dict[str, object]]:
    if not lib.ops_log_path.exists():
        return []
    lines = lib.ops_log_path.read_text(encoding="utf-8").strip().split("\n")
    return [json.loads(line) for line in lines if line]


class TestUpsert:
    def test_create_then_extend_same_title(self, lib: Librarian) -> None:
        op1, name1 = lib.upsert("Bakery Hours", "Bakery opening hours", "Opens 7am.", 1, "learned")
        op2, name2 = lib.upsert("bakery-hours", "ignored on extend", "Sat 8am-1pm.", 4, "weekend info")
        assert (op1, name1) == ("CREATE", "bakery-hours")
        assert (op2, name2) == ("EXTEND", "bakery-hours")
        note = lib.notes()["bakery-hours"]
        assert "Opens 7am." in note.body and "Sat 8am-1pm." in note.body
        # extend keeps the original hook - hooks are index identity, not content
        assert note.meta.hook == "Bakery opening hours"

    def test_paraphrased_duplicate_creates_honestly(self, lib: Librarian) -> None:
        lib.upsert("clinic-hours", "Clinic hours", "Mon-Fri 9-5.", 5, "learned")
        op, name = lib.upsert("walk-in-clinic-hours", "Walk-in hours", "Sat 10-2.", 6, "learned")
        assert op == "CREATE"  # the documented matcher limitation, kept visible
        assert set(lib.notes()) == {"clinic-hours", "walk-in-clinic-hours"}

    def test_empty_reason_is_refused(self, lib: Librarian) -> None:
        with pytest.raises(ProtocolError, match="reason"):
            lib.upsert("x-note", "hook", "body", 1, "   ")


class TestPrune:
    def test_prune_moves_to_archive_and_logs_reason(self, lib: Librarian) -> None:
        lib.upsert("bus-schedule", "Bus times", "Route 4 hourly.", 2, "learned")
        lib.prune("bus-schedule", 6, "contradicted by session 6 notice")
        assert "bus-schedule" not in lib.notes()
        assert (lib.archive_dir / "bus-schedule.md").exists()
        last = ops(lib)[-1]
        assert last["op"] == "PRUNE" and "contradicted" in str(last["reason"])

    def test_prune_unknown_note_is_an_error(self, lib: Librarian) -> None:
        with pytest.raises(ProtocolError, match="unknown"):
            lib.prune("ghost-note", 1, "reason")

    def test_prune_requires_reason(self, lib: Librarian) -> None:
        lib.upsert("a-note", "hook", "body", 1, "learned")
        with pytest.raises(ProtocolError, match="reason"):
            lib.prune("a-note", 2, "")

    def test_prune_then_recreate_same_title(self, lib: Librarian) -> None:
        lib.upsert("pharmacy-hours", "Old hours", "9-6.", 3, "learned")
        lib.prune("pharmacy-hours", 7, "new owner posted new hours")
        op, _ = lib.upsert("pharmacy-hours", "New hours", "8-8.", 7, "recreated")
        assert op == "CREATE"
        assert lib.notes()["pharmacy-hours"].meta.created_session == 7


class TestRecallAndDecay:
    def test_recall_stamps_session_and_count(self, lib: Librarian) -> None:
        lib.upsert("town-map", "Layout of Milldale", "Main St runs north.", 1, "learned")
        lib.recall(["town-map"], 3, "task needed directions")
        meta = lib.notes()["town-map"].meta
        assert meta.last_recalled_session == 3 and meta.recall_count == 1

    def test_recall_unknown_note_is_an_error(self, lib: Librarian) -> None:
        with pytest.raises(ProtocolError, match="unknown"):
            lib.recall(["ghost-note"], 1, "reason")

    def test_decay_window_edge_exact(self, lib: Librarian) -> None:
        lib.upsert("stale-note", "hook", "body", 1, "learned")
        # freshest touch = session 1; survives through session DECAY_WINDOW ...
        assert lib.decay(DECAY_WINDOW) == []
        # ... and is archived at session DECAY_WINDOW + 1 (1 <= 6 - 5)
        assert lib.decay(DECAY_WINDOW + 1) == ["stale-note"]
        assert (lib.archive_dir / "stale-note.md").exists()

    def test_recall_resets_the_decay_clock(self, lib: Librarian) -> None:
        lib.upsert("kept-note", "hook", "body", 1, "learned")
        lib.recall(["kept-note"], 4, "used")
        assert lib.decay(DECAY_WINDOW + 1) == []  # freshest 4 > 6 - 5


class TestInvariants:
    def test_index_matches_disk_after_operations(self, lib: Librarian) -> None:
        lib.upsert("a-note", "first hook", "body", 1, "learned")
        lib.upsert("b-note", "second hook", "body", 1, "learned")
        lib.prune("a-note", 2, "superseded")
        lib.check_invariants()
        assert "[[b-note]]" in lib.read_index()
        assert "[[a-note]]" not in lib.read_index()

    def test_orphan_link_is_detected(self, lib: Librarian) -> None:
        lib.upsert("a-note", "hook", "See [[missing-note]].", 1, "learned")
        with pytest.raises(ProtocolError, match="orphan"):
            lib.check_invariants()

    def test_every_operation_logged_with_reason(self, lib: Librarian) -> None:
        lib.upsert("a-note", "hook", "body", 1, "learned in session 1")
        lib.recall(["a-note"], 2, "task needed it")
        lib.prune("a-note", 3, "proven wrong")
        recorded = ops(lib)
        assert [o["op"] for o in recorded] == ["CREATE", "RECALL", "PRUNE"]
        assert all(str(o["reason"]).strip() for o in recorded)
