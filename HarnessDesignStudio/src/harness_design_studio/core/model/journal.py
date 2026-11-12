# SPDX-FileCopyrightText: 2026 0h3xn4
# SPDX-License-Identifier: GPL-3.0-only
"""The change journal: who changed what, when, from what to what and why (S4, D-191, R8).

The journal is a file of its own (`journal.jsonl`, one entry per line, since format 2 and M7a,
D-228; `journal.json` before) and exists only in a project that has chosen to keep one. It is
**append-only**: an entry is never changed or removed. Who and when live here and nowhere else: not
in the design files, not in the model hash and not in any written output, so the same design still
gives the same bytes.

The chain. Each entry carries a short chain value: a hash of its content and of the chain value
of the entry before it **on its own line of work** (its `parent`). Two people who each add entries
on their own Git branch therefore both have valid entries after Git has kept both sides' lines
(`merge=union`), and a changed entry (its hash no longer fits) or a removed one (an entry that
follows it names a parent that is not there) is still found when the file is read
(`Journal.verify`). The entries written before M7a (format 1, in `journal.json`) keep their chain
values as they are: such an entry has a number `seq` and no `parent`, and its parent is the entry
numbered one less, as before.

The order. The entries are read in an order that does not depend on the order of the lines (Git
may put the two sides of a merge either way round): the entries of format 1 first, by their
number, then every other entry after its parent, and among the entries that may come next the one
with the earliest `when`, then author, then id (the chain value). The number an entry shows (`seq`)
is its place in that order; only an entry of format 1 stores it.
"""

import hashlib
import heapq
import json
from collections.abc import Iterable, Iterator
from typing import Annotated, Any

from pydantic import Field, StringConstraints

from harness_design_studio.core.errors import HarnessError

from .base import Entity, Label, Name, Text

KINDS: tuple[str, ...] = (
    "edit",  # a person changed a design input
    "config",  # a configuration value
    "override",  # a generated value was set by hand (the reason is in the model)
    "waiver",  # a finding was accepted (the justification is in the waiver)
    "approval",  # the approval of a part
    "release",  # a review, a release or a new revision
    "generate",  # generation changed a harness (one entry per harness)
    "import",  # many objects arrived in one step
    "deviation",  # an error of an electrical rule was accepted and stays visible
    "start",  # the journal was started
    "asbuilt",  # an as-built record was added, changed or removed (S9)
    "merge",  # two lines of work were merged (`merge-fix`, M7a)
)
OTHER_KIND = "other"
# A kind this tool does not know is read and kept as it is (a later tool may add kinds, such as a
# sign-off) and shown as "other" (`shown_kind`): a new kind needs no new file format.
JournalKind = Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_-]{0,39}$")]
When = Annotated[
    str, StringConstraints(pattern=r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$")
]
Chain = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{16}$")]
FIRST_CHAIN = "0" * 16


def shown_kind(kind: str) -> str:
    """The kind as a person sees it: a kind this tool does not know is "other"."""
    return kind if kind in KINDS else OTHER_KIND


class JournalError(HarnessError):
    """An entry of the journal was asked to change, or the journal is damaged."""


class JournalEntry(Entity):
    # The place of the entry in the order of the journal, from 1. An entry of format 1 stores it
    # (it is part of its chain value); any other entry does not, and 0 means "not placed yet".
    seq: Annotated[int, Field(ge=0)] = 0
    when: When  # UTC, to the second
    author: Name
    kind: JournalKind
    object: Name  # for example "wire:W001-001", "config:derating.bundle_derating"
    field: Label = ""
    old: Any = None  # a JSON value, shortened when big
    new: Any = None
    reason: Text = ""
    tool_version: Label = ""
    chain: Chain
    # The chain value of the entry before this one on its own line of work (FIRST_CHAIN for the
    # first); None for an entry of format 1, whose parent is the entry numbered one less.
    parent: Chain | None = None

    @property
    def id(self) -> str:
        """The id of the entry: its chain value (a hash of its content and of its parent)."""
        return self.chain

    @property
    def first_format(self) -> bool:
        """An entry written before M7a (it has a number and no parent)."""
        return self.parent is None

    def stored(self) -> dict[str, Any]:
        """The entry as its line holds it: an entry of format 1 with its number and without a
        parent, exactly as it was written; any other with its parent and without a number."""
        data = self.model_dump(mode="json")
        if self.parent is None:
            data.pop("parent")
        else:
            data.pop("seq")
        return data

    def content(self) -> dict[str, Any]:
        """Everything the line holds but the chain value, for computing it."""
        data = self.stored()
        data.pop("chain")
        return data


def chain_of(previous: str, entry: dict[str, Any]) -> str:
    """The chain value of an entry (a dict without `chain`) whose parent has the chain value
    `previous`."""
    text = json.dumps(entry, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(f"{previous}\n{text}".encode()).hexdigest()[:16]


def _merged_heads(entry: JournalEntry) -> list[str]:
    """The entries a `merge` entry names (`new.heads`); [] for any other entry."""
    if entry.kind != "merge" or not isinstance(entry.new, dict):
        return []
    heads = entry.new.get("heads")
    return [h for h in heads if isinstance(h, str)] if isinstance(heads, list) else []


class Journal:
    """The entries of a project's journal. Entries can only be added. Iterating gives them in the
    order of the journal (see the module text); `lines` gives them in the order of the file, the
    order in which they were read or added, which is how they are written back, so that a save
    only ever adds lines at the end."""

    __slots__ = ("_entries", "_lines")

    def __init__(self, entries: Iterable[JournalEntry] = ()) -> None:
        lines = _unique(entries)
        self._entries: tuple[JournalEntry, ...] = _ordered(lines)
        # the lines hold the numbered entries too, so that a journal made from them (one more save)
        # numbers again only what moved
        placed = {e.chain: e for e in self._entries}
        self._lines: tuple[JournalEntry, ...] = tuple(placed[e.chain] for e in lines)

    # ---- reading -------------------------------------------------------------------------------
    @property
    def entries(self) -> tuple[JournalEntry, ...]:
        return self._entries

    @property
    def lines(self) -> tuple[JournalEntry, ...]:
        """The entries in the order of the file."""
        return self._lines

    def __len__(self) -> int:
        return len(self._entries)

    def __iter__(self) -> Iterator[JournalEntry]:
        return iter(self._entries)

    def __getitem__(self, index: int) -> JournalEntry:
        return self._entries[index]

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Journal) and self._entries == other._entries

    __hash__ = None  # type: ignore[assignment]

    def __repr__(self) -> str:
        return f"Journal({len(self._entries)} entries)"

    @property
    def last_chain(self) -> str:
        """The chain value a new entry follows: the last entry in the order of the journal."""
        return self._entries[-1].chain if self._entries else FIRST_CHAIN

    def heads(self) -> list[JournalEntry]:
        """The entries that no other entry follows or names in a merge, in the order of the
        journal: one for a journal with one line of work, more after Git kept the entries of two
        branches until `merge-fix` records the merge."""
        followed: set[str] = set()
        numbered = [e for e in self._entries if e.first_format]
        followed.update(e.chain for e in numbered[:-1])
        for e in self._entries:
            if e.parent is not None:
                followed.add(e.parent)
            followed.update(_merged_heads(e))
        return [e for e in self._entries if e.chain not in followed]

    def verify(self) -> None:
        """Raise `JournalError` when an entry does not fit its chain value or follows an entry that
        is not there (an entry was changed, removed or put in)."""
        _ordered(self._lines)

    # ---- adding --------------------------------------------------------------------------------
    def appended(self, rows: Iterable[dict[str, Any]]) -> Journal:
        """A journal with `rows` (dicts of the fields of an entry but `seq`, `parent` and `chain`)
        added after the last entry. This journal is not changed."""
        added: list[JournalEntry] = []
        previous = self.last_chain
        for row in rows:
            draft = JournalEntry.model_validate({**row, "parent": previous, "chain": FIRST_CHAIN})
            body = draft.model_dump(mode="json")
            body["chain"] = chain_of(previous, draft.content())
            entry = JournalEntry.model_validate(body)
            added.append(entry)
            previous = entry.chain
        if not added:
            return self
        return Journal((*self._lines, *added))

    # ---- what is refused -----------------------------------------------------------------------
    def _refuse(self, *_: object, **__: object) -> None:
        raise JournalError("The journal is append-only: an entry cannot be changed or removed.")

    __setitem__ = __delitem__ = _refuse
    amend = remove = replace = insert = pop = clear = _refuse


def _unique(entries: Iterable[JournalEntry]) -> tuple[JournalEntry, ...]:
    """The entries without the second copy of a line (Git keeps a line twice when both branches
    added the same one). Two different entries with the same id are a damaged journal."""
    seen: dict[str, dict[str, Any]] = {}
    kept: list[JournalEntry] = []
    for line, e in enumerate(entries, start=1):
        held = seen.get(e.chain)
        if held is None:
            seen[e.chain] = e.stored()
            kept.append(e)
        elif held != e.stored():
            raise JournalError(
                f"the entry on line {line} has the id of another entry but not its content: "
                "an entry was changed after it was written"
            )
    return tuple(kept)


def _ordered(lines: tuple[JournalEntry, ...]) -> tuple[JournalEntry, ...]:
    """Check every entry and return them in the order of the journal, numbered from 1."""
    numbered = sorted((e for e in lines if e.first_format), key=lambda e: e.seq)
    previous = FIRST_CHAIN
    for n, e in enumerate(numbered, start=1):
        if e.seq != n:
            raise JournalError(
                f"entry {n} has the number {e.seq}: an entry was removed, inserted or moved"
            )
        if e.chain != chain_of(previous, e.content()):
            raise JournalError(f"entry {n} was changed after it was written")
        previous = e.chain
    known = {FIRST_CHAIN, *(e.chain for e in lines)}
    children: dict[str, list[JournalEntry]] = {}
    for line, e in enumerate(lines, start=1):
        if e.parent is None:
            continue
        if e.chain != chain_of(e.parent, e.content()):
            raise JournalError(f"the entry on line {line} was changed after it was written")
        if e.parent not in known:
            raise JournalError(
                f"the entry on line {line} follows an entry that is not in the journal: "
                "an entry was removed"
            )
        if any(h not in known for h in _merged_heads(e)):
            raise JournalError(
                f"the merge entry on line {line} names an entry that is not in the journal: "
                "an entry was removed"
            )
        children.setdefault(e.parent, []).append(e)
    order = list(numbered)
    ready: list[tuple[str, str, str, int]] = []
    pending: dict[int, JournalEntry] = {}

    def free(parent: str) -> None:
        for child in children.pop(parent, ()):
            pending[id(child)] = child
            heapq.heappush(ready, (child.when, child.author, child.chain, id(child)))

    free(FIRST_CHAIN)
    for e in numbered:
        free(e.chain)
    while ready:
        e = pending.pop(heapq.heappop(ready)[3])
        order.append(e)
        free(e.chain)
    if len(order) != len(lines):  # (a loop of parents: only a forged file can hold one)
        raise JournalError("entries of the journal follow each other in a circle")
    return tuple(
        e if e.seq == n else e.model_copy(update={"seq": n}) for n, e in enumerate(order, start=1)
    )
