"""Repo hygiene gate: fails the build if any blocked term appears anywhere.

This file was the FIRST commit in this repository, before any source code,
and it runs on every CI push. The intent: this is a clean-room public project;
nothing from any private workspace (project vocabulary, fixture domains,
identifiers) may leak into it, and no unexplained domain vocabulary may creep
in later. The check is deliberately dumb — a case-insensitive scan with
word boundaries where needed — because a gate you can reason about beats a
clever one you cannot.

Usage:  python tools/blocklist_check.py        (exit 0 = clean, 1 = hits)
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

# Substring patterns: match anywhere, case-insensitive.
SUBSTRING_TERMS: list[str] = [
    # private-workspace vocabulary and paths
    "lzbelieve",
    "second-brain-os",
    "obsidian",
    "investoros",
    "all-weather",
    # trading / finance domain (this repo's fixtures are town errands, never finance)
    "tradingview",
    "backtest",
    "sharpe",
    "drawdown",
    "candlestick",
    "crypto",
    "bitcoin",
    "portfolio",
    "ticker",
    "ohlcv",
]

# Word-boundary patterns: short words that appear inside innocent longer words
# (e.g. "rep" in "report", "pine" in "pipeline"), so they get \b fences.
WORD_TERMS: list[str] = [
    # operator vocabulary from the private system
    "chairman",
    "chamber",
    "persona",
    "rep",
    "reps",
    "desk",
    # seat / agent names from the private system
    "aurora",
    "socrates",
    "kamogawa",
    "ippo",
    # private defect-registry row ids (P1..P99)
    r"p\d{1,2}",
    # finance words that are innocent inside longer words
    "pine",
    "btc",
    "sma",
    "ema",
    "rsi",
    "macd",
]

SKIP_DIRS = {".git", "__pycache__", ".pytest_cache", ".ruff_cache", "node_modules"}
SKIP_FILES = {"blocklist_check.py"}  # the list itself names the terms it bans
TEXT_SUFFIXES = {".py", ".md", ".json", ".jsonl", ".yml", ".yaml", ".toml",
                 ".txt", ".svg", ".cfg", ".ini", ""}

PATTERN = re.compile(
    "|".join(
        [re.escape(t) for t in SUBSTRING_TERMS]
        + [rf"\b{t}\b" for t in WORD_TERMS]
    ),
    re.IGNORECASE,
)


def iter_files(root: Path) -> list[Path]:
    out: list[Path] = []
    for path in sorted(root.rglob("*")):
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if not path.is_file() or path.name in SKIP_FILES:
            continue
        if path.suffix.lower() in TEXT_SUFFIXES:
            out.append(path)
    return out


def scan(root: Path) -> list[str]:
    hits: list[str] = []
    for path in iter_files(root):
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for lineno, line in enumerate(text.splitlines(), start=1):
            match = PATTERN.search(line)
            if match:
                rel = path.relative_to(root)
                hits.append(f"{rel}:{lineno}: '{match.group(0)}' in: {line.strip()[:90]}")
    return hits


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    hits = scan(root)
    if hits:
        print(f"BLOCKLIST: {len(hits)} hit(s) — the build fails until they are gone.")
        for hit in hits:
            print(f"  {hit}")
        return 1
    print("BLOCKLIST: clean.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
