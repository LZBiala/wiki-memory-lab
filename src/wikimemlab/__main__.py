"""CLI: `python -m wikimemlab demo` — the whole lab, from clean state, no keys.

Wipes the generated artifact dirs (wiki/, runs/, report/), replays both fixture
corpora with the ScriptedAgent, replays the baselines against the identical
per-session snapshots, writes metrics.jsonl, renders the hero SVG, and injects
the claims table into README.md. CI runs exactly this and then
`git diff --exit-code`: if anything drifts from what is committed, the build
fails. `--quiet` prints nothing (CI mode); the default streams the sessions.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from wikimemlab.agents import ScriptedAgent
from wikimemlab.report import inject_readme, load_rows, render_claims, render_svg
from wikimemlab.runner import run_baselines, run_selective, write_metrics

REPO_ROOT = Path(__file__).resolve().parents[2]
WIKI_DIR = REPO_ROOT / "wiki"
RUNS_DIR = REPO_ROOT / "runs"
REPORT_DIR = REPO_ROOT / "report"
METRICS = REPO_ROOT / "metrics.jsonl"
README = REPO_ROOT / "README.md"
FIXTURES = REPO_ROOT / "fixtures"


def _clean_tree(path: Path) -> None:
    """Delete every FILE under path but tolerate directories that refuse to go.

    File-sync tools (and open Explorer windows) hold directory handles on
    Windows and make rmdir fail with access-denied; files always unlink fine.
    Git tracks no empty directories, so a leftover empty folder cannot cause
    drift — only a stale FILE could, and those are all removed here.
    """
    if not path.exists():
        return
    for p in sorted(path.rglob("*"), reverse=True):
        if p.is_file():
            p.unlink()
        else:
            try:
                p.rmdir()
            except OSError:
                pass  # a held directory handle is harmless; see docstring
    try:
        path.rmdir()
    except OSError:
        pass


def _clean() -> None:
    for path in (WIKI_DIR, RUNS_DIR, REPORT_DIR):
        _clean_tree(path)
    if METRICS.exists():
        METRICS.unlink()


def demo(quiet: bool) -> int:
    # Fail fast when not run from a source checkout: REPO_ROOT is derived from
    # this file's location, and cleaning artifact dirs anywhere else (e.g. a
    # site-packages parent under a plain non-editable install) must not happen.
    if not (FIXTURES / "milldale" / "sessions.json").exists():
        print(
            "wikimemlab demo must run from a source checkout "
            "(pip install -e . or PYTHONPATH=src) — fixtures not found at "
            f"{FIXTURES}",
            file=sys.stderr,
        )
        return 1

    emit = (lambda _line: None) if quiet else print
    agent = ScriptedAgent()

    emit(agent.banner)
    emit("")
    _clean()

    all_metrics = []
    result = run_selective(
        corpus_path=FIXTURES / "milldale" / "sessions.json",
        wiki_dir=WIKI_DIR,
        runs_dir=RUNS_DIR,
        agent=agent,
        emit=emit,
    )
    all_metrics.extend(result.metrics)
    all_metrics.extend(
        run_baselines(FIXTURES / "milldale" / "sessions.json", result.snapshots, RUNS_DIR)
    )

    emit("")
    emit("--- crossover corpus (milldale-mini) ---")
    mini = run_selective(
        corpus_path=FIXTURES / "milldale_mini" / "sessions.json",
        wiki_dir=RUNS_DIR / "mini-wiki",
        runs_dir=RUNS_DIR,
        agent=agent,
        emit=emit,
    )
    all_metrics.extend(mini.metrics)
    all_metrics.extend(
        run_baselines(
            FIXTURES / "milldale_mini" / "sessions.json", mini.snapshots, RUNS_DIR
        )
    )

    write_metrics(METRICS, all_metrics)
    rows = load_rows(METRICS)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    svg = render_svg(rows)
    with (REPORT_DIR / "hero.svg").open("w", encoding="utf-8", newline="\n") as fh:
        fh.write(svg)
    inject_readme(README, render_claims(rows, WIKI_DIR, RUNS_DIR))

    emit("")
    emit("Done. Look around:")
    emit("  wiki/            the agent's memory — plain markdown, open it in any editor")
    emit("  runs/            session transcripts; every RECALL/EXTEND/CREATE/PRUNE has a written reason")
    emit("  report/hero.svg  the token curves (disclaimer lives inside the legend)")
    emit("  metrics.jsonl    every number the README publishes, regenerated just now")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="wikimemlab")
    sub = parser.add_subparsers(dest="command", required=True)
    p_demo = sub.add_parser("demo", help="run the full lab from clean state (no keys)")
    p_demo.add_argument("--quiet", action="store_true", help="print nothing (CI mode)")
    args = parser.parse_args(argv)
    if args.command == "demo":
        return demo(quiet=args.quiet)
    return 2


if __name__ == "__main__":
    sys.exit(main())
