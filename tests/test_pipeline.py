"""End-to-end guarantees: fixture integrity, determinism, no wall-clock time,
no network access, and the arcs the corpus promises (miss, false-CREATE,
prunes, exactly one decay).

These tests run the REAL pipeline into a temp copy of the repo layout, so they
prove the committed goldens are reproducible without touching them.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
FIXTURES = REPO / "fixtures"

# Dates (e.g. 1999-12-31), clock times with seconds (12:34:56), and ISO
# datetimes must never appear in generated artifacts. Fixture prose like
# "9am to 6pm" is fine — the ban is on machine timestamps, which would break
# the drift gate.
WALLCLOCK_RE = re.compile(r"\d{4}-\d{2}-\d{2}|\d{1,2}:\d{2}:\d{2}|\d{2}:\d{2}(?!am|pm)")

FORBIDDEN_IMPORTS = ("socket", "urllib", "http.client", "requests", "subprocess")


def run_demo(workdir: Path) -> None:
    """Copy the package + fixtures + README into workdir and run the demo there."""
    shutil.copytree(REPO / "src", workdir / "src")
    shutil.copytree(FIXTURES, workdir / "fixtures")
    shutil.copy(REPO / "README.md", workdir / "README.md")
    result = subprocess.run(  # noqa: S603 — running our own module under test
        [sys.executable, "-m", "wikimemlab", "demo", "--quiet"],
        cwd=workdir,
        env={**os.environ, "PYTHONPATH": str(workdir / "src")},
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def artifact_files(root: Path) -> list[Path]:
    out: list[Path] = []
    for sub in ("wiki", "runs", "report"):
        out.extend(sorted(p for p in (root / sub).rglob("*") if p.is_file()))
    out.append(root / "metrics.jsonl")
    return out


@pytest.fixture(scope="module")
def demo_run(tmp_path_factory: pytest.TempPathFactory) -> Path:
    workdir = tmp_path_factory.mktemp("run_a")
    run_demo(workdir)
    return workdir


class TestFixtureIntegrity:
    def test_milldale_shape(self) -> None:
        data = json.loads((FIXTURES / "milldale" / "sessions.json").read_text("utf-8"))
        sessions = data["sessions"]
        assert len(sessions) == 8
        tasks = [t for s in sessions for t in s["tasks"]]
        assert len(tasks) == 20
        corrections = [c for s in sessions for c in s["corrections"]]
        assert len(corrections) == 2  # both prune arcs

    def test_arcs_present(self) -> None:
        data = json.loads((FIXTURES / "milldale" / "sessions.json").read_text("utf-8"))
        learnings = [
            learning
            for s in data["sessions"]
            for t in s["tasks"]
            for learning in t["learnings"]
        ]
        intended = [(le["title"], le["intended"]) for le in learnings]
        assert ("bakery-hours", "EXTEND") in intended  # the extend arc
        assert ("walk-in-clinic-hours", "EXTEND") in intended  # paraphrase dup
        assert ("riverside-parking", "CREATE") in intended  # must-not-merge
        hooks = {le["title"]: le["hook"] for le in learnings}
        assert hooks["town-history"] == "assorted notes"  # the deliberate bad hook

    def test_every_task_has_labels_field(self) -> None:
        for corpus in ("milldale", "milldale_mini"):
            data = json.loads((FIXTURES / corpus / "sessions.json").read_text("utf-8"))
            for s in data["sessions"]:
                for t in s["tasks"]:
                    assert isinstance(t["relevant"], list)
                    assert t["answer"].strip()


class TestPipeline:
    def test_promised_arcs_happen(self, demo_run: Path) -> None:
        ops = [
            json.loads(line)
            for line in (demo_run / "runs" / "ops.jsonl").read_text("utf-8").splitlines()
            if line
        ]
        by_op: dict[str, list[dict[str, object]]] = {}
        for record in ops:
            by_op.setdefault(str(record["op"]), []).append(record)
        assert len(by_op["PRUNE"]) == 2
        assert [r["note"] for r in by_op["ARCHIVE"]] == ["school-play"]  # exactly one
        assert any(r["note"] == "bakery-hours" for r in by_op["EXTEND"])

    def test_miss_is_shown_in_transcript(self, demo_run: Path) -> None:
        transcript = (demo_run / "runs" / "milldale-session_07.md").read_text("utf-8")
        assert "MISS: town-history" in transcript

    def test_false_create_is_counted(self, demo_run: Path) -> None:
        rows = [
            json.loads(line)
            for line in (demo_run / "metrics.jsonl").read_text("utf-8").splitlines()
        ]
        sel = [r for r in rows if r["corpus"] == "milldale" and r["mode"] == "selective"]
        assert sum(r["false_create"] for r in sel) == 1
        assert sum(r["false_extend"] for r in sel) == 0

    def test_crossover_is_honest(self, demo_run: Path) -> None:
        rows = [
            json.loads(line)
            for line in (demo_run / "metrics.jsonl").read_text("utf-8").splitlines()
        ]
        big_sel = sum(
            r["context_tokens"]
            for r in rows
            if r["corpus"] == "milldale" and r["mode"] == "selective"
        )
        big_stuff = sum(
            r["context_tokens"]
            for r in rows
            if r["corpus"] == "milldale" and r["mode"] == "stuff"
        )
        mini = {
            r["mode"]: r["context_tokens"]
            for r in rows
            if r["corpus"] == "milldale-mini" and r["session"] == 2
        }
        assert big_sel < big_stuff  # selective wins on the full corpus
        assert mini["selective"] > mini["stuff"]  # stuffing wins on the mini corpus

    def test_no_wallclock_in_artifacts(self, demo_run: Path) -> None:
        hits: list[str] = []
        for path in artifact_files(demo_run):
            for lineno, line in enumerate(path.read_text("utf-8").splitlines(), 1):
                if WALLCLOCK_RE.search(line):
                    hits.append(f"{path.name}:{lineno}: {line.strip()[:70]}")
        assert not hits, f"wall-clock patterns in generated artifacts: {hits}"

    def test_transcripts_carry_mode_banner(self, demo_run: Path) -> None:
        for path in sorted((demo_run / "runs").glob("*session_*.md")):
            text = path.read_text("utf-8")
            assert "MODE: ScriptedAgent" in text, path.name


class TestDeterminism:
    def test_two_runs_are_byte_identical(
        self, demo_run: Path, tmp_path_factory: pytest.TempPathFactory
    ) -> None:
        second = tmp_path_factory.mktemp("run_b")
        run_demo(second)
        files_a = artifact_files(demo_run)
        files_b = artifact_files(second)
        rel_a = [p.relative_to(demo_run) for p in files_a]
        rel_b = [p.relative_to(second) for p in files_b]
        assert rel_a == rel_b
        for pa, pb in zip(files_a, files_b, strict=True):
            assert pa.read_bytes() == pb.read_bytes(), f"drift in {pa.name}"


class TestKeyless:
    def test_no_network_or_process_imports_in_package(self) -> None:
        for path in sorted((REPO / "src" / "wikimemlab").glob("*.py")):
            text = path.read_text("utf-8")
            for module in FORBIDDEN_IMPORTS:
                assert f"import {module}" not in text, f"{module} in {path.name}"

    def test_no_clock_or_unseeded_random_in_package(self) -> None:
        for path in sorted((REPO / "src" / "wikimemlab").glob("*.py")):
            text = path.read_text("utf-8")
            assert "datetime" not in text, path.name
            assert "time.time" not in text, path.name
            assert "import random" not in text, path.name


class TestBlocklist:
    def test_repo_passes_its_own_hygiene_gate(self) -> None:
        result = subprocess.run(  # noqa: S603 — running our own tool under test
            [sys.executable, str(REPO / "tools" / "blocklist_check.py")],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, result.stdout
