"""Agents: the ABC anyone can implement, and the scripted one that ships.

ScriptedAgent is deterministic on purpose: recall choices come from the
lexical scorer, answers come from the fixture script, and write-backs are
rule-driven. Every number in the README is produced by this agent, which is
exactly why none of those numbers say anything about model capability - they
characterize the memory protocol and the harness around it.

A live-model adapter deliberately does NOT ship in v1.0. The interface below
is the documented seam for one (see the README's bring-your-own-model
section); keeping it out of the codebase keeps every published surface honest
about what was measured.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from wikimemlab.frontmatter import Note, NoteMeta
from wikimemlab.scorer import recall_names


@dataclass(frozen=True)
class Task:
    """One fixture task: the prompt, ground-truth labels, and scripted output."""

    id: str
    prompt: str
    relevant: tuple[str, ...]
    answer: str


class Agent(ABC):
    """The seam between a mind and the memory protocol.

    Implementations decide WHICH notes to recall and WHAT to answer; the
    librarian (protocol.py) remains the only way to touch the wiki.
    """

    name: str

    @abstractmethod
    def choose_recall(self, prompt: str, metas: list[NoteMeta]) -> list[str]:
        """Names of notes to load for this prompt, in deterministic order."""

    @abstractmethod
    def answer(self, task: Task, recalled: list[Note]) -> str:
        """The reply for the task given the recalled notes."""


class ScriptedAgent(Agent):
    name = "ScriptedAgent"
    banner = "MODE: ScriptedAgent - deterministic, zero API keys; write-backs are rule-driven"

    def choose_recall(self, prompt: str, metas: list[NoteMeta]) -> list[str]:
        return recall_names(prompt, metas)

    def answer(self, task: Task, recalled: list[Note]) -> str:
        if recalled:
            names = ", ".join(note.meta.name for note in recalled)
            return f"{task.answer} (from notes: {names})"
        return f"{task.answer} (no notes recalled)"
