"""Strict frontmatter for wiki notes - five keys, logical session indices only.

Wall-clock time is banned from every committed artifact (a test greps for it):
timestamps would make the CI drift gate (`git diff --exit-code` after a fresh
run) fail on every re-run. Sessions are numbered 1, 2, 3, ... and those
integers are the only notion of time in the whole system.

`last_recalled_session == 0` means "never recalled".
"""
from __future__ import annotations

import re
from dataclasses import dataclass

DELIM = "---"
REQUIRED_KEYS: tuple[str, ...] = (
    "name",
    "hook",
    "created_session",
    "last_recalled_session",
    "recall_count",
)
_INT_KEYS = frozenset({"created_session", "last_recalled_session", "recall_count"})

WIKI_LINK_RE = re.compile(r"\[\[([a-z0-9][a-z0-9-]*)\]\]")
_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")


class FrontmatterError(ValueError):
    """Raised when a note file does not conform to the strict subset."""


@dataclass(frozen=True)
class NoteMeta:
    name: str
    hook: str
    created_session: int
    last_recalled_session: int
    recall_count: int


@dataclass(frozen=True)
class Note:
    meta: NoteMeta
    body: str

    def render(self) -> str:
        """Serialize deterministically: fixed key order, LF newlines."""
        m = self.meta
        lines = [
            DELIM,
            f"name: {m.name}",
            f"hook: {m.hook}",
            f"created_session: {m.created_session}",
            f"last_recalled_session: {m.last_recalled_session}",
            f"recall_count: {m.recall_count}",
            DELIM,
            "",
            self.body.rstrip("\n"),
            "",
        ]
        return "\n".join(lines)

    def links(self) -> list[str]:
        return sorted(set(WIKI_LINK_RE.findall(self.body)))


def normalize_title(title: str) -> str:
    """Kebab-case a title for exact-match lookup: 'Bakery Hours' -> 'bakery-hours'.

    This normalization IS the whole extend-before-create matcher. It is
    deliberately dumb: paraphrased duplicates ('clinic-hours' vs
    'walk-in-clinic-hours') will NOT merge, and the harness counts those
    misses honestly instead of hiding them behind a cleverness it can't test.
    """
    slug = re.sub(r"[^a-z0-9]+", "-", title.strip().lower()).strip("-")
    if not slug:
        raise FrontmatterError(f"title normalizes to nothing: {title!r}")
    return slug


def parse_note(text: str) -> Note:
    lines = text.split("\n")
    if not lines or lines[0] != DELIM:
        raise FrontmatterError("note must start with '---'")
    try:
        end = lines.index(DELIM, 1)
    except ValueError as exc:
        raise FrontmatterError("unterminated frontmatter block") from exc

    fields: dict[str, str] = {}
    for raw in lines[1:end]:
        if not raw.strip():
            continue
        key, sep, value = raw.partition(":")
        if not sep:
            raise FrontmatterError(f"malformed frontmatter line: {raw!r}")
        key = key.strip()
        if key not in REQUIRED_KEYS:
            raise FrontmatterError(f"unknown frontmatter key: {key!r}")
        if key in fields:
            raise FrontmatterError(f"duplicate frontmatter key: {key!r}")
        fields[key] = value.strip()

    missing = [k for k in REQUIRED_KEYS if k not in fields]
    if missing:
        raise FrontmatterError(f"missing frontmatter keys: {missing}")

    ints: dict[str, int] = {}
    for key in _INT_KEYS:
        try:
            ints[key] = int(fields[key])
        except ValueError as exc:
            raise FrontmatterError(f"{key} must be an integer, got {fields[key]!r}") from exc
        if ints[key] < 0:
            raise FrontmatterError(f"{key} must be >= 0, got {ints[key]}")

    name = fields["name"]
    if not _NAME_RE.match(name):
        raise FrontmatterError(f"name must be kebab-case, got {name!r}")

    body = "\n".join(lines[end + 1 :]).strip("\n")
    meta = NoteMeta(
        name=name,
        hook=fields["hook"],
        created_session=ints["created_session"],
        last_recalled_session=ints["last_recalled_session"],
        recall_count=ints["recall_count"],
    )
    return Note(meta=meta, body=body)
