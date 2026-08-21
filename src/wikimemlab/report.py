"""The single source of truth for every published number.

report.py reads metrics.jsonl and renders (a) the hero SVG - hand-rolled,
dependency-free, with the harness disclaimer inside the legend so it survives
screenshots - and (b) the claims block injected into README.md between
AUTOGEN markers. No figure in the README is ever typed by hand: CI reruns
everything and `git diff --exit-code` fails the build if any number drifts.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

AUTOGEN_BEGIN = "<!-- AUTOGEN:BEGIN - rendered by report.py from metrics.jsonl; do not edit by hand -->"
AUTOGEN_END = "<!-- AUTOGEN:END -->"
DISCLAIMER = "scripted agent - measures the harness, not model capability"

_COLORS = {"selective": "#2563eb", "stuff": "#dc2626", "nomemory": "#6b7280"}
_LABELS = {
    "selective": "selective recall (index + recalled notes)",
    "stuff": "stuff-everything (all notes, every session)",
    "nomemory": "no memory (loads nothing, fails recall tasks)",
}


@dataclass(frozen=True)
class Row:
    corpus: str
    mode: str
    session: int
    data: dict[str, object]

    def tokens(self) -> int:
        return int(self.data["context_tokens"])  # type: ignore[arg-type]


def load_rows(metrics_path: Path) -> list[Row]:
    rows: list[Row] = []
    with metrics_path.open(encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            data = json.loads(line)
            rows.append(
                Row(
                    corpus=str(data["corpus"]),
                    mode=str(data["mode"]),
                    session=int(data["session"]),
                    data=data,
                )
            )
    return rows


def _series(rows: list[Row], corpus: str, mode: str) -> list[tuple[int, int]]:
    pts = [(r.session, r.tokens()) for r in rows if r.corpus == corpus and r.mode == mode]
    return sorted(pts)


def render_svg(rows: list[Row], corpus: str = "milldale") -> str:
    """Hand-rolled line chart: context tokens per session, three modes."""
    width, height = 760, 420
    ml, mr, mt, mb = 60, 20, 34, 96
    plot_w, plot_h = width - ml - mr, height - mt - mb

    all_series = {mode: _series(rows, corpus, mode) for mode in _COLORS}
    sessions = sorted({s for pts in all_series.values() for s, _ in pts})
    y_max_raw = max((t for pts in all_series.values() for _, t in pts), default=1)
    y_max = ((y_max_raw // 100) + 1) * 100

    def x_of(session: int) -> float:
        if len(sessions) == 1:
            return ml + plot_w / 2
        frac = (session - sessions[0]) / (sessions[-1] - sessions[0])
        return ml + frac * plot_w

    def y_of(tokens: int) -> float:
        return mt + plot_h * (1 - tokens / y_max)

    parts: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" font-family="monospace" font-size="12">',
        f'<rect width="{width}" height="{height}" fill="#ffffff"/>',
        f'<text x="{ml}" y="20" font-size="14" fill="#111111">'
        f"context tokens per session - {corpus} corpus (proxy tokens = chars/4)</text>",
    ]

    for i in range(0, y_max + 1, max(100, y_max // 4 // 100 * 100 or 100)):
        y = y_of(i)
        parts.append(
            f'<line x1="{ml}" y1="{y:.1f}" x2="{width - mr}" y2="{y:.1f}" '
            f'stroke="#e5e7eb" stroke-width="1"/>'
        )
        parts.append(f'<text x="{ml - 8}" y="{y + 4:.1f}" text-anchor="end" fill="#374151">{i}</text>')

    for s in sessions:
        x = x_of(s)
        parts.append(
            f'<text x="{x:.1f}" y="{mt + plot_h + 18}" text-anchor="middle" fill="#374151">{s}</text>'
        )
    parts.append(
        f'<text x="{ml + plot_w / 2:.1f}" y="{mt + plot_h + 34}" text-anchor="middle" '
        f'fill="#374151">session</text>'
    )

    for mode, pts in all_series.items():
        if not pts:
            continue
        coords = " ".join(f"{x_of(s):.1f},{y_of(t):.1f}" for s, t in pts)
        dash = ' stroke-dasharray="6 4"' if mode == "nomemory" else ""
        parts.append(
            f'<polyline points="{coords}" fill="none" stroke="{_COLORS[mode]}" '
            f'stroke-width="2.5"{dash}/>'
        )

    legend_y = height - 52
    for i, mode in enumerate(("selective", "stuff", "nomemory")):
        y = legend_y + i * 16
        parts.append(
            f'<line x1="{ml}" y1="{y}" x2="{ml + 26}" y2="{y}" stroke="{_COLORS[mode]}" '
            f'stroke-width="2.5"/>'
        )
        parts.append(f'<text x="{ml + 34}" y="{y + 4}" fill="#111111">{_LABELS[mode]}</text>')
    parts.append(
        f'<text x="{ml}" y="{legend_y - 12}" fill="#991b1b" font-size="12">'
        f"{DISCLAIMER}</text>"
    )
    parts.append("</svg>")
    return "\n".join(parts) + "\n"


def _totals(rows: list[Row], corpus: str, mode: str) -> int:
    return sum(t for _, t in _series(rows, corpus, mode))


def _cumulative(points: list[tuple[int, int]]) -> list[tuple[int, int]]:
    out: list[tuple[int, int]] = []
    running = 0
    for session, tokens in points:
        running += tokens
        out.append((session, running))
    return out


def render_cumulative_svg(rows: list[Row], corpus: str = "milldale") -> str:
    """Cumulative context cost, selective vs stuff - the gap IS the savings.

    Same honesty rules as the hero chart: proxy tokens, scripted agent, and
    the disclaimer lives inside the legend so screenshots keep it. The final
    freed-token figure is computed from the same rows the claims table uses.
    """
    width, height = 760, 420
    ml, mr, mt, mb = 70, 20, 34, 84
    plot_w, plot_h = width - ml - mr, height - mt - mb

    sel = _cumulative(_series(rows, corpus, "selective"))
    stuff = _cumulative(_series(rows, corpus, "stuff"))
    if not sel or not stuff:
        return ""
    if [s for s, _ in sel] != [s for s, _ in stuff]:
        raise ValueError("cumulative chart requires matching session sets")
    sessions = [s for s, _ in sel]
    y_max_raw = max(stuff[-1][1], sel[-1][1])
    y_max = ((y_max_raw // 500) + 1) * 500
    saved = stuff[-1][1] - sel[-1][1]
    saved_pct = 100.0 * saved / stuff[-1][1] if stuff[-1][1] else 0.0

    def x_of(session: int) -> float:
        if len(sessions) == 1:
            return ml + plot_w / 2
        frac = (session - sessions[0]) / (sessions[-1] - sessions[0])
        return ml + frac * plot_w

    def y_of(tokens: int) -> float:
        return mt + plot_h * (1 - tokens / y_max)

    parts: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" font-family="monospace" font-size="12">',
        f'<rect width="{width}" height="{height}" fill="#ffffff"/>',
        f'<text x="{ml}" y="20" font-size="14" fill="#111111">'
        f"cumulative context tokens - {corpus} corpus (the gap is the freed budget)</text>",
    ]

    for i in range(0, y_max + 1, 500):
        y = y_of(i)
        parts.append(
            f'<line x1="{ml}" y1="{y:.1f}" x2="{width - mr}" y2="{y:.1f}" '
            f'stroke="#e5e7eb" stroke-width="1"/>'
        )
        parts.append(
            f'<text x="{ml - 8}" y="{y + 4:.1f}" text-anchor="end" fill="#374151">{i}</text>'
        )
    for s in sessions:
        parts.append(
            f'<text x="{x_of(s):.1f}" y="{mt + plot_h + 18}" text-anchor="middle" '
            f'fill="#374151">{s}</text>'
        )
    parts.append(
        f'<text x="{ml + plot_w / 2:.1f}" y="{mt + plot_h + 34}" text-anchor="middle" '
        f'fill="#374151">session</text>'
    )

    # shaded gap between the two cumulative curves
    gap_pts = [f"{x_of(s):.1f},{y_of(t):.1f}" for s, t in stuff]
    gap_pts += [f"{x_of(s):.1f},{y_of(t):.1f}" for s, t in reversed(sel)]
    parts.append(
        f'<polygon points="{" ".join(gap_pts)}" fill="#2563eb" opacity="0.08"/>'
    )
    for pts, color in ((stuff, _COLORS["stuff"]), (sel, _COLORS["selective"])):
        coords = " ".join(f"{x_of(s):.1f},{y_of(t):.1f}" for s, t in pts)
        parts.append(
            f'<polyline points="{coords}" fill="none" stroke="{color}" stroke-width="2.5"/>'
        )

    end_y = (y_of(sel[-1][1]) + y_of(stuff[-1][1])) / 2
    parts.append(
        f'<text x="{width - mr - 6}" y="{end_y:.1f}" text-anchor="end" fill="#1d4ed8" '
        f'font-weight="bold">{saved} proxy tokens freed ({saved_pct:.1f}%)</text>'
    )

    legend_y = height - 40
    for i, (mode, label) in enumerate(
        (("stuff", "stuff-everything (cumulative)"), ("selective", "selective recall (cumulative)"))
    ):
        y = legend_y + i * 16
        parts.append(
            f'<line x1="{ml}" y1="{y}" x2="{ml + 26}" y2="{y}" stroke="{_COLORS[mode]}" '
            f'stroke-width="2.5"/>'
        )
        parts.append(f'<text x="{ml + 34}" y="{y + 4}" fill="#111111">{label}</text>')
    parts.append(
        f'<text x="{ml}" y="{legend_y - 12}" fill="#991b1b" font-size="12">{DISCLAIMER}</text>'
    )
    parts.append("</svg>")
    return "\n".join(parts) + "\n"


def _glob_bytes(path: Path, pattern: str) -> int:
    return sum(len(p.read_bytes()) for p in sorted(path.glob(pattern)))


def render_claims(rows: list[Row], wiki_dir: Path, runs_dir: Path) -> str:
    """The claims-as-SLOs block: claim / number / how measured / honest caveat."""
    sel_total = _totals(rows, "milldale", "selective")
    stuff_total = _totals(rows, "milldale", "stuff")
    ratio = sel_total / stuff_total if stuff_total else 0.0

    mini_sel = [r for r in rows if r.corpus == "milldale-mini" and r.mode == "selective"]
    mini_stuff = [r for r in rows if r.corpus == "milldale-mini" and r.mode == "stuff"]
    mini_measure_sel = max(mini_sel, key=lambda r: r.session).tokens() if mini_sel else 0
    mini_measure_stuff = max(mini_stuff, key=lambda r: r.session).tokens() if mini_stuff else 0
    mini_ratio = mini_measure_sel / mini_measure_stuff if mini_measure_stuff else 0.0

    sel_rows = [r for r in rows if r.corpus == "milldale" and r.mode == "selective"]
    hits = sum(int(r.data.get("pr_hits", 0)) for r in sel_rows)  # type: ignore[arg-type]
    n_rec = sum(int(r.data.get("pr_recalled", 0)) for r in sel_rows)  # type: ignore[arg-type]
    n_rel = sum(int(r.data.get("pr_relevant", 0)) for r in sel_rows)  # type: ignore[arg-type]
    precision = hits / n_rec if n_rec else 0.0
    recall = hits / n_rel if n_rel else 0.0
    misses = sum(int(r.data.get("misses", 0)) for r in sel_rows)  # type: ignore[arg-type]
    f_create = sum(int(r.data.get("false_create", 0)) for r in sel_rows)  # type: ignore[arg-type]
    f_extend = sum(int(r.data.get("false_extend", 0)) for r in sel_rows)  # type: ignore[arg-type]

    ops_total: dict[str, int] = {}
    for r in sel_rows:
        for op, count in dict(r.data.get("ops", {})).items():  # type: ignore[arg-type]
            ops_total[op] = ops_total.get(op, 0) + int(count)

    last = max(sel_rows, key=lambda r: r.session)
    last_stuff = max(
        (r for r in rows if r.corpus == "milldale" and r.mode == "stuff"),
        key=lambda r: r.session,
    )
    notes_live = int(last.data["notes_live"])  # type: ignore[arg-type]
    index_tok = int(last.data["index_tokens"])  # type: ignore[arg-type]
    per_note = index_tok / notes_live if notes_live else 0.0
    overhead = index_tok / last_stuff.tokens() if last_stuff.tokens() else 0.0

    # Byte comparison, measured to match its own row text exactly: the wiki
    # INCLUDING its archive (pruned notes are stored, not deleted, so they are
    # part of the memory footprint) vs ONLY the transcripts of the corpus this
    # wiki was distilled from - not the mini corpus, not baseline summaries.
    wiki_bytes = _glob_bytes(wiki_dir, "*.md") + _glob_bytes(wiki_dir / "archive", "*.md")
    transcript_bytes = _glob_bytes(runs_dir, "milldale-session_*.md")

    n_sessions = len(sel_rows)
    mini_notes = max(
        (int(r.data["notes_live"]) for r in mini_stuff), default=0  # type: ignore[arg-type]
    )

    lines = [
        "| claim | number (regenerated by CI) | how measured | honest caveat |",
        "|---|---|---|---|",
        (
            "| Selective recall loads fewer context tokens than stuffing the whole wiki "
            f"| **{sel_total} vs {stuff_total} proxy tokens over {n_sessions} sessions "
            f"(ratio {ratio:.2f})** | identical fixture suite, three loading policies; "
            "baselines replay the selective run's per-session wiki snapshots; proxy "
            "tokens = chars/4 | the ratio is the claim, not the absolute counts; it "
            "depends on corpus size and task locality - see the crossover row |"
        ),
        (
            "| Crossover: below a small corpus size, stuffing is cheaper "
            f"| **mini corpus ({mini_notes} notes): selective {mini_measure_sel} vs stuff "
            f"{mini_measure_stuff} proxy tokens (ratio {mini_ratio:.2f})** | same "
            f"harness on a corpus of {mini_notes} notes whose tasks touch most of it | "
            "selective recall pays the index every session; on a small, hot corpus "
            "that overhead is pure loss - the design only wins when the wiki outgrows "
            "its working set |"
        ),
        (
            "| One-line hooks recover the labeled relevant notes "
            f"| **precision {precision:.2f} / recall {recall:.2f} "
            f"({hits}/{n_rec} recalled correct, {hits}/{n_rel} relevant found, "
            f"{misses} shown miss(es))** | author-written ground-truth labels on the "
            "main corpus only (the crossover mini corpus is measured in its own row); "
            "the runner logs actual recalls | an upper bound by "
            "construction - the same author wrote tasks, hooks, and labels; the "
            "deliberately lazy hook produces the shown miss |"
        ),
        (
            "| Protocol conformance (labeled as such, not a benchmark) "
            f"| **ops: {json.dumps(ops_total, sort_keys=True)}; false-CREATE "
            f"{f_create}, false-EXTEND {f_extend}** | counted from the ops log and "
            "final wiki state of the deterministic run; adversarial fixtures push the "
            "title matcher in both failure directions | proves the harness enforces "
            "the protocol and characterizes the matcher - not whether a live model "
            "would follow the protocol unprompted |"
        ),
        (
            "| The index is the standing price of selective recall "
            f"| **{index_tok} proxy tokens for {notes_live} notes "
            f"(~{per_note:.1f}/note, {overhead:.2f} of full-corpus cost at session "
            f"{last.session})** "
            "| measured directly from the generated index and final corpus | one-line "
            "hooks are a design commitment - hooks that bloat into paragraphs erode "
            "exactly the savings claimed here |"
        ),
        (
            "| Memory stays smaller than what it remembers "
            f"| **final wiki {wiki_bytes} bytes (live notes + index + archive) vs "
            f"{transcript_bytes} bytes of the session transcripts it was distilled "
            "from** | byte sizes of the main-corpus wiki including archived notes vs "
            "that corpus's session transcripts only | growth depends on the "
            "extend/prune discipline the protocol enforces; a corpus without "
            "corrections would grow differently |"
        ),
    ]

    saved = stuff_total - sel_total
    saved_pct = 100.0 * saved / stuff_total if stuff_total else 0.0
    lines.append("")
    lines.append(
        f"Cumulative over the main corpus: selective recall freed **{saved} proxy "
        f"tokens ({saved_pct:.1f}%)** of context budget vs loading everything - and "
        "the gap widens as the wiki grows "
        "([report/cumulative.svg](report/cumulative.svg)). Same caveats as the first "
        "row: proxy tokens, ratio-not-absolutes, corpus- and locality-dependent."
    )
    return "\n".join(lines)


def inject_readme(readme_path: Path, block: str) -> None:
    text = readme_path.read_text(encoding="utf-8")
    begin = text.index(AUTOGEN_BEGIN)
    end = text.index(AUTOGEN_END) + len(AUTOGEN_END)
    new = text[:begin] + AUTOGEN_BEGIN + "\n\n" + block + "\n\n" + AUTOGEN_END + text[end:]
    with readme_path.open("w", encoding="utf-8", newline="\n") as fh:
        fh.write(new)
