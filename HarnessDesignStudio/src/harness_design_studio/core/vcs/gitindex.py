"""Which files are in a Git merge conflict: the paths with a stage above 0 in the index.

Like `gitinfo`, this reads the repository's own file (`.git/index`, versions 2, 3 and 4) and never
starts the `git` program (D-164). Nothing is written. A damaged or unknown index gives "not known"
(None), never a crash or a hang. A conflict in a file that Git treats as binary (see the
`.gitattributes` of a new project) leaves no markers in the file, so the index is the only place
that says the file is still in conflict.

    unmerged_paths(project_folder)    # ["generated/generation.json"], [] or None, relative to the folder
"""

import struct
from pathlib import Path

from harness_design_studio.core.vcs.gitinfo import find_work_tree

__all__ = ["unmerged_paths"]

MAX_INDEX = 256 << 20  # an index larger than this is not read
_FIXED = 62  # bytes of an entry before its name: times, numbers, hash (SHA-1), flags
_EXTENDED = 0x4000  # the entry has two more bytes of flags (index version 3 and 4)


class _Unreadable(Exception):
    pass


def unmerged_paths(start: Path) -> list[str] | None:
    """Sorted paths (relative to `start`, with "/") that are in conflict in the repository that
    contains `start`, only those at or below `start`. [] when there is none; None when there is no
    repository or its index cannot be read."""
    found = find_work_tree(start)
    if found is None:
        return None
    work, git_dir, _ = found
    index = git_dir / "index"
    try:
        if not index.is_file():
            return []
        if index.stat().st_size > MAX_INDEX:
            return None
        names = _conflicted(index.read_bytes())
        base = start.resolve().relative_to(work).as_posix()
    except _Unreadable, OSError, ValueError, UnicodeError, struct.error, IndexError:
        return None
    prefix = "" if base == "." else base + "/"
    return sorted({n[len(prefix) :] for n in names if n.startswith(prefix)})


def _conflicted(data: bytes) -> list[str]:
    if data[:4] != b"DIRC" or len(data) < 12:
        raise _Unreadable("header")
    version, count = struct.unpack(">II", data[4:12])
    if version not in (2, 3, 4):
        raise _Unreadable("version")
    out: list[str] = []
    pos, previous = 12, b""
    for _ in range(count):
        start = pos
        (flags,) = struct.unpack(">H", data[pos + 60 : pos + 62])
        fixed = _FIXED
        if flags & _EXTENDED:
            if version < 3:
                raise _Unreadable("extended flags in version 2")
            fixed += 2
        pos += fixed
        if version == 4:
            strip, pos = _offset(data, pos)
            end = data.index(b"\0", pos)
            if strip > len(previous):
                raise _Unreadable("name")
            name = previous[: len(previous) - strip] + data[pos:end]
            pos = end + 1
            previous = name
        else:
            end = data.index(b"\0", pos)
            name = data[pos:end]
            pos = start + ((fixed + len(name) + 8) & ~7)  # padded to a multiple of 8, 1 to 8 NULs
        if pos > len(data):
            raise _Unreadable("entry")
        if (flags >> 12) & 3:
            out.append(name.decode("utf-8", errors="replace"))
    return out


def _offset(data: bytes, pos: int) -> tuple[int, int]:
    """The variable-length number of index version 4 (the bytes of the name to strip)."""
    c = data[pos]
    pos += 1
    value = c & 127
    while c & 128:
        c = data[pos]
        pos += 1
        value = ((value + 1) << 7) | (c & 127)
    return value, pos
