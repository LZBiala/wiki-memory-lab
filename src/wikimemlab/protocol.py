"""The librarian: the sole API through which anything touches the wiki.

Design rules this module enforces:
- Every mutation goes through one class, and every operation appends one line
  to an ops log WITH A WRITTEN REASON — the audit-log property the whole
  project exists to demonstrate.
- extend-before-create is exact normalized-title matching (see
  frontmatter.normalize_title). Paraphrased duplicates therefore CREATE — the
  harness counts those as false-CREATE instead of hiding them.
- prune() refuses an empty reason. A memory that deletes without saying why
  is not auditable.
- One decay rule, no knobs: a note neither created nor recalled in the last
  DECAY_WINDOW sessions is archived automatically at session end.
- The index is regenerated from disk after every mutation batch; an index
  that can drift from the notes is a second source of truth, i.e. a bug.
"""
from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

from wikimemlab.frontmatter import Note, NoteMeta, normalize_title, parse_note

DECAY_WINDOW = 5
INDEX_NAME = "index.md"
ARCHIVE_DIR = "archive"


class ProtocolError(ValueError):
    """Raised on operations that would corrupt the memory store."""


class Librarian:
    def __init__(self, wiki_dir: Path, ops_log_path: Path) -> None:
        self.wiki_dir = wiki_dir
        self.archive_dir = wiki_dir / ARCHIVE_DIR
        self.ops_log_path = ops_log_path
        self.wiki_dir.mkdir(parents=True, exist_ok=True)
        self.archive_dir.mkdir(parents=True, exist_ok=True)
        self.ops_log_path.parent.mkdir(parents=True, exist_ok=True)

    # ---------- reading ----------

    def note_paths(self) -> list[Path]:
        return sorted(p for p in self.wiki_dir.glob("*.md") if p.name != INDEX_NAME)

    def notes(self) -> dict[str, Note]:
        out: dict[str, Note] = {}
        for path in self.note_paths():
            note = parse_note(path.read_text(encoding="utf-8"))
            if note.meta.name != path.stem:
                raise ProtocolError(f"note name {note.meta.name!r} != filename {path.stem!r}")
            out[note.meta.name] = note
        return out

    def read_index(self) -> str:
        path = self.wiki_dir / INDEX_NAME
        if not path.exists():
            return ""
        return path.read_text(encoding="utf-8")

    # ---------- operations (each one logs, with a reason) ----------

    def recall(self, names: list[str], session: int, reason: str) -> list[Note]:
        """Load notes into context; stamps last_recalled_session/recall_count."""
        notes = self.notes()
        out: list[Note] = []
        for name in names:
            if name not in notes:
                raise ProtocolError(f"recall of unknown note {name!r}")
            note = notes[name]
            meta = replace(
                note.meta,
                last_recalled_session=session,
                recall_count=note.meta.recall_count + 1,
            )
            updated = Note(meta=meta, body=note.body)
            self._write_note(updated)
            self._log(session, "RECALL", name, reason)
            out.append(updated)
        if names:
            self.rebuild_index()
        return out

    def upsert(
        self, title: str, hook: str, body: str, session: int, reason: str
    ) -> tuple[str, str]:
        """EXTEND if a note with the same normalized title exists, else CREATE.

        Returns (op, name) where op is 'EXTEND' or 'CREATE'.
        """
        _require_reason(reason)
        name = normalize_title(title)
        notes = self.notes()
        if name in notes:
            existing = notes[name]
            merged = existing.body.rstrip("\n") + "\n" + body.strip("\n")
            self._write_note(Note(meta=existing.meta, body=merged))
            self._log(session, "EXTEND", name, reason)
            op = "EXTEND"
        else:
            meta = NoteMeta(
                name=name,
                hook=hook,
                created_session=session,
                last_recalled_session=0,
                recall_count=0,
            )
            self._write_note(Note(meta=meta, body=body.strip("\n")))
            self._log(session, "CREATE", name, reason)
            op = "CREATE"
        self.rebuild_index()
        return op, name

    def prune(self, name: str, session: int, reason: str) -> None:
        """Archive a note that has been proven wrong. Reason is mandatory."""
        _require_reason(reason)
        notes = self.notes()
        if name not in notes:
            raise ProtocolError(f"prune of unknown note {name!r}")
        self._archive(name)
        self._log(session, "PRUNE", name, reason)
        self.rebuild_index()

    def decay(self, session: int) -> list[str]:
        """Archive notes neither created nor recalled in DECAY_WINDOW sessions."""
        archived: list[str] = []
        for name, note in sorted(self.notes().items()):
            freshest = max(note.meta.created_session, note.meta.last_recalled_session)
            if freshest <= session - DECAY_WINDOW:
                self._archive(name)
                self._log(
                    session,
                    "ARCHIVE",
                    name,
                    f"decay rule: not created or recalled since session {freshest} "
                    f"(window {DECAY_WINDOW})",
                )
                archived.append(name)
        if archived:
            self.rebuild_index()
        return archived

    # ---------- maintenance ----------

    def rebuild_index(self) -> None:
        lines = ["# index", ""]
        for name, note in sorted(self.notes().items()):
            lines.append(f"- [[{name}]] — {note.meta.hook}")
        text = "\n".join(lines) + "\n"
        self._write_text(self.wiki_dir / INDEX_NAME, text)

    def check_invariants(self) -> None:
        """Index matches disk; no orphan links; all notes parse strictly."""
        notes = self.notes()  # parsing already enforced strictness
        on_disk = {f"- [[{n}]] — {note.meta.hook}" for n, note in notes.items()}
        in_index = {
            line for line in self.read_index().split("\n") if line.startswith("- [[")
        }
        if on_disk != in_index:
            raise ProtocolError("index does not match notes on disk")
        for name, note in sorted(notes.items()):
            for link in note.links():
                if link not in notes:
                    raise ProtocolError(f"orphan link [[{link}]] in note {name!r}")

    # ---------- internals ----------

    def _archive(self, name: str) -> None:
        src = self.wiki_dir / f"{name}.md"
        dst = self.archive_dir / f"{name}.md"
        self._write_text(dst, src.read_text(encoding="utf-8"))
        src.unlink()

    def _write_note(self, note: Note) -> None:
        self._write_text(self.wiki_dir / f"{note.meta.name}.md", note.render())

    def _log(self, session: int, op: str, name: str, reason: str) -> None:
        _require_reason(reason)
        record = {"session": session, "op": op, "note": name, "reason": reason}
        with self.ops_log_path.open("a", encoding="utf-8", newline="\n") as fh:
            fh.write(json.dumps(record, sort_keys=True) + "\n")

    @staticmethod
    def _write_text(path: Path, text: str) -> None:
        with path.open("w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)


def _require_reason(reason: str) -> None:
    if not reason.strip():
        raise ProtocolError("a written reason is mandatory for every operation")
