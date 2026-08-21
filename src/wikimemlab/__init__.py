"""wikimemlab - long-term memory for AI agents as a human-readable markdown wiki.

The premise, stated so it can be attacked: an agent's long-term memory can live
in plain markdown files - an index skimmed at session start, one concept per
note, selective recall of only the notes a task needs, extend-before-create
write-back, prune-with-a-written-reason, and a single decay rule - and the
token cost, retrieval quality, and protocol behavior of that design can be
measured deterministically, with zero API keys, in CI.

What this package deliberately CANNOT measure:
- whether a live LLM would follow the protocol unprompted (the bundled agent
  is scripted; its write-backs are rule-driven, so every number here
  characterizes the harness and the protocol, never model capability);
- open-ended answer quality (answers are fixture-scripted);
- retrieval quality beyond this corpus (the same author wrote the tasks,
  hooks, and relevance labels, so precision/recall figures are upper bounds).

Those limits are not footnotes; they are printed into the report legend and
the README. The honest product is the memory protocol, its audit log, and a
harness that regenerates every published number from a fixed seed.
"""
from __future__ import annotations

__version__ = "1.0.0"
