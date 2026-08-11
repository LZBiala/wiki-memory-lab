"""The walkthrough page is quoted-and-TESTED, like everything else.

docs/index.html hand-carries transcript excerpts and claim numbers. The page
is not regenerated, so without these tests it would sit outside the drift
gate: a fixture change would self-heal the README and silently strand the
page. These tests parse the page itself (single source — no duplicated
strings here) and pin it to the transcripts and metrics.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
HTML = (REPO / "docs" / "index.html").read_text(encoding="utf-8")


def transcripts_text() -> str:
    parts = [
        p.read_text(encoding="utf-8")
        for p in sorted((REPO / "runs").glob("milldale-session_*.md"))
    ]
    return "\n".join(parts)


def metrics_rows() -> list[dict[str, object]]:
    return [
        json.loads(line)
        for line in (REPO / "metrics.jsonl").read_text(encoding="utf-8").splitlines()
        if line
    ]


class TestQuotedLinesAreVerbatim:
    def test_every_player_and_stage_line_appears_in_transcripts(self) -> None:
        quoted = re.findall(r'\bline: "(.*?)"', HTML) + re.findall(r'\bx: "(.*?)"', HTML)
        assert len(quoted) >= 15, "extraction regex found too few quoted lines"
        corpus = transcripts_text()
        for line in quoted:
            # "…" marks honest truncation of a verbatim prefix.
            prefix = line.split("…")[0]
            assert prefix in corpus, f"not verbatim in transcripts: {prefix[:70]}"


class TestCardNumbersMatchMetrics:
    def test_ratios_and_counts(self) -> None:
        rows = metrics_rows()

        def total(corpus: str, mode: str) -> int:
            return sum(
                int(r["context_tokens"])  # type: ignore[arg-type]
                for r in rows
                if r["corpus"] == corpus and r["mode"] == mode
            )

        sel, stuff = total("milldale", "selective"), total("milldale", "stuff")
        assert f"{sel / stuff:.2f}×" in HTML  # 0.61×
        assert f"{sel:,} vs {stuff:,}" in HTML  # 2,236 vs 3,654

        mini = {
            (r["mode"], r["session"]): r
            for r in rows
            if r["corpus"] == "milldale-mini"
        }
        m_sel = int(mini[("selective", 2)]["context_tokens"])  # type: ignore[arg-type]
        m_stuff = int(mini[("stuff", 2)]["context_tokens"])  # type: ignore[arg-type]
        assert f"{m_sel / m_stuff:.2f}×" in HTML  # 1.27×
        assert f"{int(mini[('stuff', 2)]['notes_live'])}-note" in HTML  # type: ignore[arg-type]

        sel_rows = [r for r in rows if r["corpus"] == "milldale" and r["mode"] == "selective"]
        hits = sum(int(r["pr_hits"]) for r in sel_rows)  # type: ignore[arg-type]
        n_rec = sum(int(r["pr_recalled"]) for r in sel_rows)  # type: ignore[arg-type]
        assert f"{hits / n_rec:.2f}" in HTML  # 0.95
        fc = sum(int(r["false_create"]) for r in sel_rows)  # type: ignore[arg-type]
        fe = sum(int(r["false_extend"]) for r in sel_rows)  # type: ignore[arg-type]
        assert f"{fc} / {fe}" in HTML  # 1 / 0

    def test_beat_count_in_copy_matches_the_array(self) -> None:
        n_beats = len(re.findall(r'\bline: "', HTML))
        words = {12: "Twelve", 13: "Thirteen", 14: "Fourteen", 15: "Fifteen"}
        assert words.get(n_beats, str(n_beats)) in HTML


class TestGapWidensIsMeasuredNotAsserted:
    """The README/page say the cumulative gap 'widens as the wiki grows'.
    That sentence must be a property of the data, not a hope: per-session
    context cost under stuffing must strictly exceed selective for every
    session after the first (equivalently, the cumulative gap is strictly
    increasing)."""

    def test_per_session_gap_positive_after_session_one(self) -> None:
        rows = metrics_rows()
        by = {
            (r["mode"], r["session"]): int(r["context_tokens"])  # type: ignore[arg-type]
            for r in rows
            if r["corpus"] == "milldale"
        }
        sessions = sorted({s for m, s in by if m == "selective"})
        for s in sessions[1:]:
            assert by[("stuff", s)] > by[("selective", s)], f"gap not widening at session {s}"
