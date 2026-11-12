# SPDX-FileCopyrightText: 2026 0h3xn4
# SPDX-License-Identifier: GPL-3.0-only
"""Two people each pressed Generate, or each changed the design with a journal: the files of a
Git merge, and the way out.

`generated/generation.json` holds a hash of the whole design, so when two branches each ran
Generate it conflicts at every merge, whatever else was edited. The change journal
(`journal.jsonl`, M7a, D-228) gets entries on both branches. The pieces that handle them:

* `GITATTRIBUTES`, written once into a new project (`new`, and the example projects ship it): it
  tells Git to treat the record as binary, so a conflict leaves no markers in it (it stays
  valid JSON, the editor and `check` can still read it) and keeps the version of the branch you
  are on; and to merge the journal with `merge=union`, which keeps the lines that both sides
  added, so the journal does not conflict. Everything else is text and merges line by line, as
  before. `add_journal_union` puts the journal's line into the `.gitattributes` of a project
  that gets a journal file later (a journal started, an upgrade from format 1).
* `plan_merge_fix`, behind the command `merge-fix`: it finds the files that are in conflict and
  answers whether the way out the manual describes applies (the record and the journal are the
  only files in conflict). `take_our_side` keeps our side of conflict markers (the record);
  `take_both_sides` keeps both (the journal, when Git merged it without `merge=union`). It never
  decides anything about any other file.
* `record_journal_merge`: after a merge the journal has the entries of two lines of work; it adds
  the one `merge` entry that names both (`core.journal.merge_rows`).

No Qt, no `git` program (see `core/vcs/gitindex.py`), no network.
"""

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

from harness_design_studio.core.errors import SaveError
from harness_design_studio.core.io.fs import atomic_write_bytes
from harness_design_studio.core.vcs.gitindex import unmerged_paths

__all__ = [
    "GENERATION_FILE",
    "GITATTRIBUTES",
    "JOURNAL_FILE",
    "MergeFixPlan",
    "add_journal_union",
    "conflict_files",
    "plan_merge_fix",
    "record_journal_merge",
    "take_both_sides",
    "take_our_side",
    "write_gitattributes",
]

GENERATION_FILE = "generated/generation.json"
JOURNAL_FILE = "journal.jsonl"
_RECORD_TEXT = (
    "# Written by Harness Design Studio (harness-design-studio new). Safe to edit or delete.\n"
    "#\n"
    "# generated/generation.json is the record of the last Generate. It holds a hash of the whole\n"
    "# design, so when two people each ran Generate on their own branch it conflicts at every\n"
    "# merge, whatever else they changed. Git treats it as a binary file: it writes no conflict\n"
    "# markers into it (the file stays valid JSON) and keeps the version of the branch you are\n"
    "# on. After the merge run:  harness-design-studio merge-fix PROJECT_FOLDER\n"
)
# The text of 1.x (before M7a): a `.gitattributes` that is still exactly this is replaced by
# `GITATTRIBUTES` when the project gets a journal file.
GITATTRIBUTES_1 = (
    _RECORD_TEXT
    + "# Every other file of the project is text and merges line by line.\n"
    + "generated/generation.json merge=binary linguist-generated=true\n"
)
JOURNAL_UNION = (
    "# journal.jsonl is the change journal, one entry per line. Git keeps the lines that both\n"
    "# sides of a merge added (merge=union), so it does not conflict; merge-fix then records the\n"
    "# merge in it.\n"
    "journal.jsonl merge=union\n"
)
GITATTRIBUTES = (
    _RECORD_TEXT
    + "# Every other file of the project is text and merges line by line, except the journal.\n"
    + "generated/generation.json merge=binary linguist-generated=true\n"
    + "#\n"
    + JOURNAL_UNION
)

MAX_FILE = 64 << 20  # a file larger than this is not searched for markers
_SKIP_DIRS = frozenset({".git", ".harness-recovery", "quarantine"})
_START = re.compile(rb"^<{7}(?: .*)?$", re.M)
_END = re.compile(rb"^>{7}(?: .*)?$", re.M)


def write_gitattributes(folder: Path) -> bool:
    """Write `.gitattributes` into a project folder unless one is there; True when written."""
    path = folder / ".gitattributes"
    if path.exists() or path.is_symlink():
        return False
    atomic_write_bytes(path, GITATTRIBUTES.encode("utf-8"), backup=False, root=folder)
    return True


def add_journal_union(folder: Path) -> str:
    """Make the `.gitattributes` of a project folder say `journal.jsonl merge=union` (M7a,
    D-228). Returns what was done: `written` (there was none: the whole text of `new` is
    written), `updated` (it was the text of 1.x, word for word, and is replaced by today's),
    `added` (the journal's lines are added at the end of a file someone wrote or changed),
    `present` (it names journal.jsonl already: left as it is) or `skipped` (a link, or a file that
    cannot be read or written: left as it is; the journal then merges line by line and
    `merge-fix` keeps both sides of a conflict in it)."""
    path = folder / ".gitattributes"
    try:
        if path.is_symlink() or (path.exists() and not path.is_file()):
            return "skipped"
        if not path.exists():
            atomic_write_bytes(path, GITATTRIBUTES.encode("utf-8"), backup=False, root=folder)
            return "written"
        data = path.read_bytes()
        text = data.decode("utf-8")
        if text == GITATTRIBUTES_1:
            atomic_write_bytes(path, GITATTRIBUTES.encode("utf-8"), backup=False, root=folder)
            return "updated"
        if any(line.split()[:1] == [JOURNAL_FILE] for line in text.splitlines()):
            return "present"
        joint = "" if not text or text.endswith("\n") else "\n"
        more = f"{joint}#\n# Added by Harness Design Studio.\n{JOURNAL_UNION}"
        atomic_write_bytes(path, data + more.encode("utf-8"), backup=False, root=folder)
        return "added"
    except OSError, ValueError, SaveError:
        return "skipped"


def has_markers(data: bytes) -> bool:
    return bool(_START.search(data) and _END.search(data))


def conflict_files(folder: Path) -> list[str]:
    """Files of the project folder (relative, with "/") that hold Git conflict markers, found by
    reading them, plus the files the Git index says are still unmerged (a file Git merged as
    binary has no markers). Sorted."""
    found: set[str] = set(unmerged_paths(folder) or [])
    for root, dirs, names in os.walk(folder):
        dirs[:] = [d for d in dirs if d not in _SKIP_DIRS and not d.startswith(".migration-backup")]
        for name in names:
            if name.endswith(".bak"):  # the copy of an earlier version, not part of the project
                continue
            path = Path(root) / name
            try:
                if path.is_symlink() or path.stat().st_size > MAX_FILE:
                    continue
                if has_markers(path.read_bytes()):
                    found.add(path.relative_to(folder).as_posix())
            except OSError:
                continue
    return sorted(found)


def take_our_side(data: bytes) -> bytes:
    """The file with every conflict hunk reduced to our side (the lines between `<<<<<<<` and
    `=======`; with the `diff3` style the common ancestor between `|||||||` and `=======` is
    dropped as well). Raises ValueError when the markers are not well formed."""
    out: list[bytes] = []
    state = "text"  # text, ours, base, theirs
    for line in data.splitlines(keepends=True):
        bare = line.rstrip(b"\r\n")
        if state == "text":
            if bare.startswith(b"<<<<<<<"):
                state = "ours"
            elif bare.startswith(b">>>>>>>"):
                raise ValueError("a conflict marker without its start")
            else:
                out.append(line)
        elif bare.startswith(b"<<<<<<<"):
            raise ValueError("conflict markers inside conflict markers")
        elif state == "ours":
            if bare.startswith(b"|||||||"):
                state = "base"
            elif bare == b"=======":
                state = "theirs"
            elif bare.startswith(b">>>>>>>"):
                raise ValueError("a conflict hunk without its middle line")
            else:
                out.append(line)
        elif state == "base":
            if bare == b"=======":
                state = "theirs"
        elif bare.startswith(b">>>>>>>"):  # theirs
            state = "text"
    if state != "text":
        raise ValueError("a conflict hunk without its end")
    return b"".join(out)


def take_both_sides(data: bytes) -> bytes:
    """The file with every conflict hunk replaced by our side's lines and then theirs (the common
    ancestor of the `diff3` style is dropped): what `merge=union` would have made. For the journal,
    whose lines are entries that only ever get added. Raises ValueError when the markers are not
    well formed."""
    out: list[bytes] = []
    state = "text"  # text, ours, base, theirs
    for line in data.splitlines(keepends=True):
        bare = line.rstrip(b"\r\n")
        if state == "text":
            if bare.startswith(b"<<<<<<<"):
                state = "ours"
            elif bare.startswith(b">>>>>>>") or bare == b"=======":
                raise ValueError("a conflict marker without its start")
            else:
                out.append(line)
        elif bare.startswith(b"<<<<<<<"):
            raise ValueError("conflict markers inside conflict markers")
        elif state == "ours":
            if bare.startswith(b"|||||||"):
                state = "base"
            elif bare == b"=======":
                state = "theirs"
            elif bare.startswith(b">>>>>>>"):
                raise ValueError("a conflict hunk without its middle line")
            else:
                out.append(line)
        elif state == "base":
            if bare == b"=======":
                state = "theirs"
        elif bare.startswith(b">>>>>>>"):  # theirs
            state = "text"
        else:
            out.append(line)
    if state != "text":
        raise ValueError("a conflict hunk without its end")
    return b"".join(x if x.endswith(b"\n") else x + b"\n" for x in out)


@dataclass(frozen=True)
class MergeFixPlan:
    """What `merge-fix` finds. `ok` is True only when the record and the journal are the only
    files in conflict."""

    conflicts: list[str] = field(default_factory=list)  # every file in conflict
    others: list[str] = field(default_factory=list)  # all of them except the record and journal
    record_has_markers: bool = False
    new_record: bytes | None = None  # our side of the record when it has markers
    problem: str = ""  # why the record or the journal cannot be taken
    new_journal: bytes | None = None  # both sides of the journal when it has markers

    @property
    def nothing_to_do(self) -> bool:
        return not self.conflicts

    @property
    def ok(self) -> bool:
        return bool(self.conflicts) and not self.others and not self.problem


def _journal_both_sides(folder: Path) -> tuple[bytes | None, str]:
    """Both sides of a journal in conflict, and why they cannot be taken ('' when they can)."""
    path = folder / JOURNAL_FILE
    try:
        data = path.read_bytes() if path.is_file() and not path.is_symlink() else b""
    except OSError:
        return None, "The journal cannot be read."
    if not has_markers(data):
        return None, ""
    try:
        return take_both_sides(data), ""
    except ValueError as exc:
        return None, f"The journal: {exc}."


def plan_merge_fix(folder: Path) -> MergeFixPlan:
    """Read-only: which files are in conflict, and the record and the journal as they will be
    kept."""
    conflicts = conflict_files(folder)
    others = [c for c in conflicts if c not in (GENERATION_FILE, JOURNAL_FILE)]
    journal, problem = _journal_both_sides(folder) if JOURNAL_FILE in conflicts else (None, "")
    if problem or GENERATION_FILE not in conflicts:
        return MergeFixPlan(conflicts, others, problem=problem, new_journal=journal)
    path = folder / GENERATION_FILE
    try:
        data = path.read_bytes() if path.is_file() and not path.is_symlink() else b""
    except OSError:
        return MergeFixPlan(conflicts, others, problem="The record cannot be read.")
    marked = has_markers(data)
    if marked:
        try:
            data = take_our_side(data)
        except ValueError as exc:
            return MergeFixPlan(conflicts, others, True, None, f"The record: {exc}.", journal)
    try:
        record = json.loads(data.decode("utf-8"))
    except ValueError:
        return MergeFixPlan(
            conflicts, others, marked, None, "The record is not valid JSON.", journal
        )
    if not isinstance(record, dict) or "input_hash" not in record:
        return MergeFixPlan(
            conflicts, others, marked, None, "The file is not a generation record.", journal
        )
    return MergeFixPlan(conflicts, others, marked, data if marked else None, "", journal)


def record_journal_merge(folder: Path) -> int:
    """Add the one `merge` entry to the journal of a project when Git kept the entries of more
    than one line of work (`core.journal.merge_rows`), and write only the journal. Returns how many
    lines of work it merged; 0 when there was nothing to record (no `journal.jsonl`, one head, or
    a project of another format). Raises `JournalError` when the journal is damaged and
    `SaveError` when it cannot be written."""
    from harness_design_studio.core import journal as journal_module
    from harness_design_studio.core.io import canonical
    from harness_design_studio.core.io.layout import journal_bytes, parse_file
    from harness_design_studio.core.io.migrate import current_version, schema_version_of
    from harness_design_studio.core.model import Journal, JournalEntry, JournalError

    path = folder / JOURNAL_FILE
    if not path.is_file() or path.is_symlink():
        return 0
    try:
        meta = canonical.loads_strict((folder / "project.json").read_bytes())
        if schema_version_of({"project.json": meta}) != current_version():
            return 0
        raws = parse_file(JOURNAL_FILE, path.read_bytes())["journal"]
        journal = Journal(JournalEntry.model_validate(r) for r in raws)
    except (OSError, ValueError, RecursionError) as exc:
        raise JournalError(f"The journal cannot be read: {exc}") from None
    heads = len(journal.heads())
    if heads < 2:
        return 0
    atomic_write_bytes(path, journal_bytes(journal_module.merged(journal)), root=folder)
    return heads
