"""The session loop, the baselines, and the metrics they emit.

One selective run drives everything:
- Sessions execute in order: load index -> per task (recall -> answer ->
  write-backs) -> corrections -> decay -> transcript + metrics.
- At each SESSION START the rendered wiki files are snapshotted in memory.
  The two baselines replay those IDENTICAL snapshots — stuff-everything
  loads every rendered file, no-memory loads nothing — so the token
  comparison is controlled: same wiki state, different loading policy.
- Metrics land in metrics.jsonl, one JSON object per (corpus, mode, session),
  floats pin-formatted as strings so the CI drift gate never trips on
  representation noise.

Nothing here reads a clock, an environment variable, or the network.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from wikimemlab.agents import Agent, Task
from wikimemlab.frontmatter import Note
from wikimemlab.protocol import Librarian
from wikimemlab.tokens import proxy_tokens

Emit = Callable[[str], None]


def _fmt(x: float) -> str:
    return f"{x:.2f}"


@dataclass
class SessionMetrics:
    corpus: str
    mode: str
    session: int
    notes_live: int
    index_tokens: int
    recalled_tokens: int
    context_tokens: int
    precision: str | None
    recall: str | None
    misses: int
    pr_hits: int = 0
    pr_recalled: int = 0
    pr_relevant: int = 0
    ops: dict[str, int] = field(default_factory=dict)
    false_extend: int = 0
    false_create: int = 0
    failed_tasks: int = 0

    def to_json(self) -> str:
        return json.dumps(self.__dict__, sort_keys=True)


@dataclass(frozen=True)
class RunResult:
    metrics: list[SessionMetrics]
    snapshots: dict[int, dict[str, str]]  # session -> {name: rendered text}


def load_corpus(path: Path) -> dict[str, object]:
    with path.open(encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, dict) or "sessions" not in data or "corpus" not in data:
        raise ValueError(f"malformed corpus file: {path}")
    return data


def _task_from(raw: dict[str, object]) -> Task:
    return Task(
        id=str(raw["id"]),
        prompt=str(raw["prompt"]),
        relevant=tuple(str(r) for r in raw.get("relevant", [])),  # type: ignore[union-attr]
        answer=str(raw["answer"]),
    )


def run_selective(
    corpus_path: Path,
    wiki_dir: Path,
    runs_dir: Path,
    agent: Agent,
    emit: Emit,
) -> RunResult:
    """The hero run: real wiki on disk, transcripts, metrics, snapshots."""
    data = load_corpus(corpus_path)
    corpus = str(data["corpus"])
    lib = Librarian(wiki_dir=wiki_dir, ops_log_path=runs_dir / "ops.jsonl")
    metrics: list[SessionMetrics] = []
    snapshots: dict[int, dict[str, str]] = {}

    for raw_session in data["sessions"]:  # type: ignore[union-attr]
        session = int(raw_session["session"])
        notes_at_start = lib.notes()
        snapshots[session] = {n: note.render() for n, note in notes_at_start.items()}

        index_text = lib.read_index()
        index_tok = proxy_tokens(index_text)
        lines: list[str] = [
            f"# {corpus} — session {session:02d}",
            agent.banner if hasattr(agent, "banner") else f"MODE: {agent.name}",
            "",
            f"INDEX loaded: {len(notes_at_start)} notes / {index_tok} tokens",
        ]
        emit(lines[0])
        emit(lines[3])

        recalled_union: dict[str, Note] = {}
        hits = 0
        n_recalled = 0
        n_relevant = 0
        misses = 0
        false_extend = 0
        false_create = 0
        ops_count: dict[str, int] = {}

        def bump(op: str) -> None:
            ops_count[op] = ops_count.get(op, 0) + 1

        for raw_task in raw_session["tasks"]:
            task = _task_from(raw_task)
            metas = [n.meta for n in lib.notes().values()]
            chosen = agent.choose_recall(task.prompt, metas)
            recalled = lib.recall(chosen, session, f"needed for task {task.id}")
            for note in recalled:
                recalled_union[note.meta.name] = note
                bump("RECALL")

            lines.append("")
            lines.append(f"## task {task.id} — \"{task.prompt}\"")
            if recalled:
                tok = sum(proxy_tokens(n.render()) for n in recalled)
                names = ", ".join(n.meta.name for n in recalled)
                lines.append(f"RECALL: {names} ({len(recalled)} note(s) / {tok} tokens)")
            else:
                lines.append("RECALL: (none)")
            emit(lines[-1])

            hits += len(set(chosen) & set(task.relevant))
            n_recalled += len(chosen)
            n_relevant += len(task.relevant)
            for name in task.relevant:
                if name not in chosen:
                    misses += 1
                    lines.append(
                        f"MISS: {name} (labeled relevant, not recalled — "
                        f"its hook gave the scorer nothing to match)"
                    )
                    emit(lines[-1])

            lines.append(f"ANSWER: {agent.answer(task, recalled)}")

            for learning in raw_task.get("learnings", []):
                op, name = lib.upsert(
                    title=str(learning["title"]),
                    hook=str(learning["hook"]),
                    body=str(learning["body"]),
                    session=session,
                    reason=str(learning["reason"]),
                )
                bump(op)
                intended = str(learning["intended"]).upper()
                suffix = ""
                if intended != op:
                    if op == "CREATE":
                        false_create += 1
                        suffix = " [intended EXTEND — counted as false-CREATE]"
                    else:
                        false_extend += 1
                        suffix = " [intended CREATE — counted as false-EXTEND]"
                lines.append(f"WRITE-BACK: {op} {name} — {learning['reason']}{suffix}")
                emit(lines[-1])

        for correction in raw_session.get("corrections", []):
            prune_name = str(correction["prune"])
            reason = str(correction["reason"])
            lib.prune(prune_name, session, reason)
            bump("PRUNE")
            lines.append("")
            lines.append(f"CORRECTION: PRUNE {prune_name} — {reason}")
            emit(lines[-1])
            replacement = correction.get("replacement")
            if replacement:
                op, name = lib.upsert(
                    title=str(replacement["title"]),
                    hook=str(replacement["hook"]),
                    body=str(replacement["body"]),
                    session=session,
                    reason=f"replacement for pruned {prune_name}",
                )
                bump(op)
                lines.append(f"CORRECTION: {op} {name} — replacement for pruned {prune_name}")
                emit(lines[-1])

        archived = lib.decay(session)
        for name in archived:
            bump("ARCHIVE")
            lines.append(
                f"DECAY: ARCHIVE {name} — not created or recalled inside the decay window"
            )
            emit(lines[-1])

        lib.check_invariants()

        recalled_tok = sum(proxy_tokens(n.render()) for n in recalled_union.values())
        context_tok = index_tok + recalled_tok
        precision = _fmt(hits / n_recalled) if n_recalled else None
        recall_rate = _fmt(hits / n_relevant) if n_relevant else None
        lines.append("")
        lines.append(
            f"SESSION {session:02d} TOTALS: index {index_tok} + recalled {recalled_tok}"
            f" = {context_tok} context tokens"
        )
        emit(lines[-1])
        lines.append("")

        transcript = runs_dir / f"{corpus}-session_{session:02d}.md"
        transcript.parent.mkdir(parents=True, exist_ok=True)
        with transcript.open("w", encoding="utf-8", newline="\n") as fh:
            fh.write("\n".join(lines))

        metrics.append(
            SessionMetrics(
                corpus=corpus,
                mode="selective",
                session=session,
                notes_live=len(lib.notes()),
                index_tokens=index_tok,
                recalled_tokens=recalled_tok,
                context_tokens=context_tok,
                precision=precision,
                recall=recall_rate,
                misses=misses,
                pr_hits=hits,
                pr_recalled=n_recalled,
                pr_relevant=n_relevant,
                ops=dict(sorted(ops_count.items())),
                false_extend=false_extend,
                false_create=false_create,
            )
        )

    return RunResult(metrics=metrics, snapshots=snapshots)


def run_baselines(
    corpus_path: Path, snapshots: dict[int, dict[str, str]], runs_dir: Path
) -> list[SessionMetrics]:
    """Replay the selective run's per-session snapshots under other policies.

    stuff-everything: context = every rendered note file (no index needed).
    no-memory: context = nothing; tasks with ground-truth relevant notes are
    counted as failed (there is nothing to answer them from).
    """
    data = load_corpus(corpus_path)
    corpus = str(data["corpus"])
    out: list[SessionMetrics] = []
    summary: list[str] = [f"# {corpus} — baseline replays", ""]

    for raw_session in data["sessions"]:  # type: ignore[union-attr]
        session = int(raw_session["session"])
        snapshot = snapshots[session]
        stuff_tok = sum(proxy_tokens(text) for text in snapshot.values())
        needy = sum(1 for t in raw_session["tasks"] if t.get("relevant"))
        out.append(
            SessionMetrics(
                corpus=corpus,
                mode="stuff",
                session=session,
                notes_live=len(snapshot),
                index_tokens=0,
                recalled_tokens=stuff_tok,
                context_tokens=stuff_tok,
                precision=None,
                recall=None,
                misses=0,
            )
        )
        out.append(
            SessionMetrics(
                corpus=corpus,
                mode="nomemory",
                session=session,
                notes_live=len(snapshot),
                index_tokens=0,
                recalled_tokens=0,
                context_tokens=0,
                precision=None,
                recall=None,
                misses=0,
                failed_tasks=needy,
            )
        )
        summary.append(
            f"session {session:02d}: stuff-everything loads {len(snapshot)} notes / "
            f"{stuff_tok} tokens; no-memory loads 0 and fails {needy} task(s) that "
            f"needed remembered facts"
        )

    summary.append("")
    summary.append(
        "Method: both baselines replay the IDENTICAL per-session wiki snapshots "
        "produced by the selective run — same memory state, different loading policy."
    )
    summary.append("")
    path = runs_dir / f"{corpus}-baselines.md"
    with path.open("w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(summary))
    return out


def write_metrics(path: Path, metrics: list[SessionMetrics]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as fh:
        for m in metrics:
            fh.write(m.to_json() + "\n")
