"""Two people each pressed Generate: the file that always conflicts, and the way out.

`generated/generation.json` holds a hash of the whole design, so when two branches each ran
Generate it conflicts at every merge, whatever else was edited. Two pieces handle that:

* `GITATTRIBUTES`, written once into a new project (`new`, and the example projects ship it): it
  tells Git to treat that one file as binary, so a conflict leaves no markers in it (it stays
  valid JSON, the editor and `check` can still read it) and keeps the version of the branch you
  are on. Everything else is text and merges line by line, as before.
* `plan_merge_fix`, behind the command `merge-fix`: it finds the files that are in conflict and
  answers whether the one way out the manual describes applies (the record is the only file in
  conflict). `take_our_side` keeps our side of conflict markers. It never decides anything about
  any other file.

No Qt, no `git` program (see `core/vcs/gitindex.py`), no network.
"""

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

from harness_design_studio.core.io.fs import atomic_write_bytes
from harness_design_studio.core.vcs.gitindex import unmerged_paths

__all__ = [
    "GENERATION_FILE",
    "GITATTRIBUTES",
    "MergeFixPlan",
    "conflict_files",
    "plan_merge_fix",
    "take_our_side",
    "write_gitattributes",
]

GENERATION_FILE = "generated/generation.json"
GITATTRIBUTES = (
    "# Written by Harness Design Studio (harness-design-studio new). Safe to edit or delete.\n"
    "#\n"
    "# generated/generation.json is the record of the last Generate. It holds a hash of the whole\n"
    "# design, so when two people each ran Generate on their own branch it conflicts at every\n"
    "# merge, whatever else they changed. Git treats it as a binary file: it writes no conflict\n"
    "# markers into it (the file stays valid JSON) and keeps the version of the branch you are\n"
    "# on. After the merge run:  harness-design-studio merge-fix PROJECT_FOLDER\n"
    "# Every other file of the project is text and merges line by line.\n"
    "generated/generation.json merge=binary linguist-generated=true\n"
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


@dataclass(frozen=True)
class MergeFixPlan:
    """What `merge-fix` finds. `ok` is True only when the record is the one file in conflict."""

    conflicts: list[str] = field(default_factory=list)  # every file in conflict
    others: list[str] = field(default_factory=list)  # all of them except the record
    record_has_markers: bool = False
    new_record: bytes | None = None  # our side of the record when it has markers
    problem: str = ""  # why the record cannot be taken (markers not well formed, not JSON)

    @property
    def nothing_to_do(self) -> bool:
        return not self.conflicts

    @property
    def ok(self) -> bool:
        return bool(self.conflicts) and not self.others and not self.problem


def plan_merge_fix(folder: Path) -> MergeFixPlan:
    """Read-only: which files are in conflict, and the record as it will be kept."""
    conflicts = conflict_files(folder)
    others = [c for c in conflicts if c != GENERATION_FILE]
    if GENERATION_FILE not in conflicts:
        return MergeFixPlan(conflicts, others)
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
            return MergeFixPlan(conflicts, others, True, None, f"The record: {exc}.")
    try:
        record = json.loads(data.decode("utf-8"))
    except ValueError:
        return MergeFixPlan(conflicts, others, marked, None, "The record is not valid JSON.")
    if not isinstance(record, dict) or "input_hash" not in record:
        return MergeFixPlan(conflicts, others, marked, None, "The file is not a generation record.")
    return MergeFixPlan(conflicts, others, marked, data if marked else None)
