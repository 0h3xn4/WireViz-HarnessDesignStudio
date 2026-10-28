"""Autosave journal: the latest state of an open project, kept inside the project folder.

After a crash or power loss the journal holds everything up to the last committed change. It lives
in `<project>/.harness-recovery/` (never outside the project folder, never in logs).
"""

import base64
import contextlib
import json
import re
import secrets
from pathlib import Path

from .errors import SaveError
from .io.canonical import dumps
from .io.fs import atomic_write_bytes, long_path
from .io.layout import serialize
from .io.loader import LoadResult, load_from_files
from .model import Project, QuarantinedItem

JOURNAL_DIR = ".harness-recovery"
JOURNAL_FILE = "session.json"


def damaged_files(project: Project) -> list[str]:
    """The files (relative paths, sorted) that could not be loaded: a whole file that did not
    parse, and the files that hold an item that was set aside. Empty for a complete project."""
    names = {q.file for q in project.quarantine if q.file} | set(project.quarantine_files)
    return sorted(names)


def journal_path(root: Path | str) -> Path:
    return long_path(Path(root)) / JOURNAL_DIR / JOURNAL_FILE


# The JSON text of each file's bytes, by the identity of the bytes object. `serialize` hands out the
# same bytes object for a file that did not change, so only an edited file is encoded again.
_FRAGMENTS: dict[int, tuple[bytes, bytes]] = {}


def journal_bytes(project: Project, *, base_fingerprint: str | None = None) -> bytes:
    """The journal text of `project`: what `canonical.dumps` makes of the payload below. The files
    that did not change since the last call are not encoded again (audit A-9: 14 MB of text were
    escaped from scratch after every edit); the result is the same bytes either way."""
    global _FRAGMENTS
    files = serialize(project)
    names = sorted(files)
    token = f"fragment-{secrets.token_hex(8)}-"
    payload = {
        "base_fingerprint": base_fingerprint,
        "files": {rel: f"{token}{n}" for n, rel in enumerate(names)},
        # what could not be loaded must survive a restore, or the restored project would look
        # complete and could overwrite the original folder
        "quarantine": [
            {"file": q.file, "kind": q.kind, "reason": q.reason, "raw": q.raw}
            for q in project.quarantine
        ],
        "quarantine_files": {
            name: base64.b64encode(raw).decode("ascii")
            for name, raw in project.quarantine_files.items()
        },
    }
    frame = dumps(payload)  # short: a placeholder stands where each file goes
    keep: dict[int, tuple[bytes, bytes]] = {}
    fragments: list[bytes] = []
    for rel in names:
        data = files[rel]
        hit = _FRAGMENTS.get(id(data))
        if hit is None or hit[0] is not data:
            hit = (data, json.dumps(data.decode("utf-8"), ensure_ascii=False).encode("utf-8"))
        keep[id(data)] = hit
        fragments.append(hit[1])
    _FRAGMENTS = keep
    pieces = re.split(rb'"' + token.encode("ascii") + rb'(\d+)"', frame)
    out = [pieces[0]]
    for k in range(1, len(pieces), 2):
        out.append(fragments[int(pieces[k])])
        out.append(pieces[k + 1])
    return b"".join(out)


def write_journal_bytes(root: Path | str, data: bytes) -> None:
    atomic_write_bytes(journal_path(root), data, backup=False)


def write_journal(
    project: Project, root: Path | str, *, base_fingerprint: str | None = None
) -> None:
    write_journal_bytes(root, journal_bytes(project, base_fingerprint=base_fingerprint))


def clear_journal(root: Path | str) -> None:
    path = journal_path(root)
    path.unlink(missing_ok=True)
    with contextlib.suppress(OSError):
        path.parent.rmdir()


def has_journal(root: Path | str) -> bool:
    return journal_path(root).is_file()


def journal_differs_from_disk(root: Path | str) -> bool:
    """True if the journal holds changes that were never saved to the project files."""
    try:
        payload = json.loads(journal_path(root).read_text(encoding="utf-8"))
        base = Path(root)
        disk = serialize(load_from_files(_read_files(base)).project)
        return {k: v.encode() for k, v in payload["files"].items()} != disk
    except OSError, ValueError, KeyError, TypeError, AttributeError, RecursionError, SaveError:
        return False


def _read_files(base: Path) -> dict[str, object]:
    from .io.loader import read_tree

    parsed, _, _ = read_tree(base)
    return parsed


def read_journal(root: Path | str) -> LoadResult | None:
    """Load the journalled state, or None if there is no usable journal."""
    path = journal_path(root)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        files = {rel: json.loads(text) for rel, text in payload["files"].items()}
    except OSError, ValueError, KeyError, TypeError, AttributeError, RecursionError:
        return None
    result = load_from_files(files)
    try:
        result.project.quarantine.extend(
            QuarantinedItem(str(q["file"]), str(q["kind"]), str(q["reason"]), q["raw"])
            for q in payload.get("quarantine", [])
        )
        result.project.quarantine_files.update(
            {n: base64.b64decode(raw) for n, raw in payload.get("quarantine_files", {}).items()}
        )
    except KeyError, TypeError, ValueError, AttributeError:
        return None
    return result
