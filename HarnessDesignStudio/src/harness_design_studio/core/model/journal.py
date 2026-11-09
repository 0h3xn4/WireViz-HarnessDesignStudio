# SPDX-FileCopyrightText: 2026 0h3xn4
# SPDX-License-Identifier: GPL-3.0-only
"""The change journal: who changed what, when, from what to what and why (S4, D-191, R8).

The journal is a file of its own (`journal.json`) and exists only in a project that has chosen
to keep one. It is **append-only**: an entry is never changed or removed. Each entry carries a
short chain value made from the one before it, so a changed, removed or inserted entry is found
when the file is read (`Journal.verify`). Who and when live here and nowhere else: not in the
design files, not in the model hash and not in any written output, so the same design still gives
the same bytes.
"""

import hashlib
import json
from collections.abc import Iterable, Iterator
from typing import Annotated, Any, Literal

from pydantic import Field, StringConstraints

from harness_design_studio.core.errors import HarnessError

from .base import Entity, Label, Name, Text

JournalKind = Literal[
    "edit",  # a person changed a design input
    "config",  # a configuration value
    "override",  # a generated value was set by hand (the reason is in the model)
    "waiver",  # a finding was accepted (the justification is in the waiver)
    "approval",  # the approval of a part
    "release",  # a review, a release or a new revision
    "generate",  # generation changed a harness (one entry per harness)
    "import",  # many objects arrived in one step
    "deviation",  # an error of an electrical rule was accepted and stays visible
    "asbuilt",  # an as-built record was added, changed or removed (S9)
    "start",  # the journal was started
]
KINDS: tuple[str, ...] = (
    "edit", "config", "override", "waiver", "approval", "release", "generate", "import",
    "deviation", "start", "asbuilt",
)  # fmt: skip
When = Annotated[
    str, StringConstraints(pattern=r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$")
]
Chain = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{16}$")]
FIRST_CHAIN = "0" * 16


class JournalError(HarnessError):
    """An entry of the journal was asked to change, or the journal is damaged."""


class JournalEntry(Entity):
    seq: Annotated[int, Field(ge=1)]  # 1, 2, 3 ...: no gap
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

    def content(self) -> dict[str, Any]:
        """Everything but the chain value, for computing it."""
        data = self.model_dump(mode="json")
        data.pop("chain")
        return data


def chain_of(previous: str, entry: dict[str, Any]) -> str:
    """The chain value of an entry (a dict without `chain`) that follows the one with `previous`."""
    text = json.dumps(entry, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(f"{previous}\n{text}".encode()).hexdigest()[:16]


class Journal:
    """The entries of a project's journal, in order. Entries can only be added at the end."""

    __slots__ = ("_entries",)

    def __init__(self, entries: Iterable[JournalEntry] = ()) -> None:
        self._entries: tuple[JournalEntry, ...] = tuple(entries)
        self.verify()

    # ---- reading -------------------------------------------------------------------------------
    @property
    def entries(self) -> tuple[JournalEntry, ...]:
        return self._entries

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
        return self._entries[-1].chain if self._entries else FIRST_CHAIN

    def verify(self) -> None:
        """Raise `JournalError` when the sequence has a gap or an entry does not fit the chain."""
        previous = FIRST_CHAIN
        for n, e in enumerate(self._entries, start=1):
            if e.seq != n:
                raise JournalError(
                    f"entry {n} has the number {e.seq}: an entry was removed, inserted or moved"
                )
            if e.chain != chain_of(previous, e.content()):
                raise JournalError(f"entry {n} was changed after it was written")
            previous = e.chain

    # ---- adding --------------------------------------------------------------------------------
    def appended(self, rows: Iterable[dict[str, Any]]) -> Journal:
        """A journal with `rows` (dicts of the fields of an entry but `seq` and `chain`) added at
        the end. This journal is not changed."""
        entries = list(self._entries)
        previous = self.last_chain
        for row in rows:
            draft = JournalEntry.model_validate(
                {**row, "seq": len(entries) + 1, "chain": FIRST_CHAIN}
            )
            body = draft.model_dump(mode="json")
            body["chain"] = chain_of(previous, draft.content())
            entry = JournalEntry.model_validate(body)
            entries.append(entry)
            previous = entry.chain
        return Journal(entries)

    # ---- what is refused -----------------------------------------------------------------------
    def _refuse(self, *_: object, **__: object) -> None:
        raise JournalError("The journal is append-only: an entry cannot be changed or removed.")

    __setitem__ = __delitem__ = _refuse
    amend = remove = replace = insert = pop = clear = _refuse
