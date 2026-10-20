"""Who made the last change: the last commit of the Git repository a project folder lives in.

The tool never starts the `git` program (D-164): it reads the repository's own files, read-only —
`HEAD`, the branch file or `packed-refs`, then the commit object, either loose (one zlib file) or
inside a pack (`.idx` version 2 and `.pack`, with the delta forms Git uses for commits). Nothing is
written, nothing is run, no hook or configuration of the repository is read, and no network is used.
Every read has a size limit, so a damaged or hostile `.git` folder gives "not known", never a hang
or a crash.

    info = last_commit(project_folder)       # None when there is no repository or it cannot be read
    info.author, info.when, info.subject, info.short, info.branch

Only the name of the author is kept, not the e-mail address. The commit is the last one of the whole
repository, not the last one that touched the project; changes made since it (not yet committed) are
not seen. The window says both.
"""

import re
import zlib
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

__all__ = ["CommitInfo", "find_git_dir", "last_commit"]

MAX_OBJECT = 1 << 20  # a commit larger than 1 MiB is not read
MAX_DELTA_DEPTH = 64
MAX_UP = 12  # parent folders searched for `.git`
_HEX = re.compile(r"[0-9a-f]{40}")
_REF = re.compile(r"refs/[A-Za-z0-9._/@+-]+")
COMMIT, OFS_DELTA, REF_DELTA = 1, 6, 7


@dataclass(frozen=True)
class CommitInfo:
    commit: str  # the 40-character id
    author: str
    when: str  # "2026-10-20 09:53 +0000"
    subject: str
    branch: str  # "" for a detached HEAD

    @property
    def short(self) -> str:
        return self.commit[:7]


class _Unreadable(Exception):
    pass


def find_git_dir(start: Path) -> tuple[Path, Path] | None:
    """(git dir, common dir) of the repository that contains `start`, or None. A `.git` file
    (a linked worktree or a submodule) points to the git dir; objects and refs of a linked
    worktree live in the common dir."""
    try:
        here = start.resolve()
    except OSError:
        return None
    for folder in [here, *list(here.parents)[:MAX_UP]]:
        dot = folder / ".git"
        try:
            if dot.is_dir():
                git_dir = dot
            elif dot.is_file():
                text = dot.read_text(encoding="utf-8", errors="replace")[:4096]
                m = re.match(r"gitdir:\s*(.+)", text.strip())
                if not m:
                    return None
                git_dir = (folder / m.group(1).strip()).resolve()
                if not git_dir.is_dir():
                    return None
            else:
                continue
            common = git_dir
            cf = git_dir / "commondir"
            if cf.is_file():
                common = (git_dir / cf.read_text(encoding="utf-8").strip()[:4096]).resolve()
            return git_dir, common
        except (OSError, UnicodeError):
            return None
    return None


def last_commit(start: Path) -> CommitInfo | None:
    """The last commit of the repository around `start`, or None when there is none or it cannot be
    read (no repository, nothing committed yet, a shallow or damaged one, an object store the
    reader does not know)."""
    found = find_git_dir(start)
    if found is None:
        return None
    git_dir, common = found
    try:
        branch, sha = _head(git_dir, common)
        raw = _read_object(common, sha)
        return _parse_commit(sha, raw, branch)
    except (_Unreadable, OSError, zlib.error, ValueError, IndexError, UnicodeError):
        return None


# ---- references ---------------------------------------------------------------------------


def _head(git_dir: Path, common: Path) -> tuple[str, str]:
    text = _read_text(git_dir / "HEAD").strip()
    if _HEX.fullmatch(text):
        return "", text
    if not text.startswith("ref:"):
        raise _Unreadable("HEAD")
    ref = text[4:].strip()
    if not _REF.fullmatch(ref) or ".." in ref or ref.endswith(("/", ".lock")):
        raise _Unreadable("ref name")
    return ref.removeprefix("refs/heads/"), _resolve_ref(git_dir, common, ref)


def _resolve_ref(git_dir: Path, common: Path, ref: str) -> str:
    for base in (git_dir, common):
        f = base / ref
        if f.is_file():
            sha = _read_text(f).strip()
            if _HEX.fullmatch(sha):
                return sha
    packed = common / "packed-refs"
    if packed.is_file():
        for line in _read_text(packed).splitlines():
            if line.endswith(" " + ref) and _HEX.fullmatch(line[:40]):
                return line[:40]
    raise _Unreadable("no commit yet")


def _read_text(path: Path, limit: int = 1 << 20) -> str:
    with path.open("rb") as f:
        return f.read(limit).decode("utf-8", errors="replace")


# ---- objects ------------------------------------------------------------------------------


def _read_object(common: Path, sha: str) -> bytes:
    loose = common / "objects" / sha[:2] / sha[2:]
    if loose.is_file():
        d = zlib.decompressobj()
        with loose.open("rb") as f:
            data = d.decompress(f.read(MAX_OBJECT), MAX_OBJECT)
        head, _, body = data.partition(b"\0")
        word, _, size = head.partition(b" ")
        if word != b"commit" or int(size) != len(body):
            raise _Unreadable("not a commit")
        return body
    for idx in sorted((common / "objects" / "pack").glob("pack-*.idx")):
        offset = _pack_offset(idx, bytes.fromhex(sha))
        if offset is not None:
            kind, body = _pack_object(idx.with_suffix(".pack"), idx, offset, 0)
            if kind != COMMIT:
                raise _Unreadable("not a commit")
            return body
    raise _Unreadable("object not found")


def _pack_offset(idx: Path, raw: bytes) -> int | None:
    """Offset of the object in the pack (version 2 index), or None when it is not in it."""
    with idx.open("rb") as f:
        head = f.read(8 + 256 * 4)
        if head[:8] != b"\xfftOc\0\0\0\2":
            raise _Unreadable("index version")
        fan = [int.from_bytes(head[8 + 4 * i : 12 + 4 * i], "big") for i in range(256)]
        total = fan[255]
        lo, hi = (fan[raw[0] - 1] if raw[0] else 0), fan[raw[0]]
        names = 8 + 256 * 4
        while lo < hi:
            mid = (lo + hi) // 2
            f.seek(names + 20 * mid)
            got = f.read(20)
            if got == raw:
                f.seek(names + 20 * total + 4 * total + 4 * mid)
                off = int.from_bytes(f.read(4), "big")
                if off & 0x80000000:
                    f.seek(names + 28 * total + 8 * (off & 0x7FFFFFFF))
                    off = int.from_bytes(f.read(8), "big")
                return off
            if got < raw:
                lo = mid + 1
            else:
                hi = mid
    return None


def _inflate(f: "object", limit: int = MAX_OBJECT) -> bytes:
    d = zlib.decompressobj()
    out = bytearray()
    while not d.eof:
        chunk = f.read(4096)  # type: ignore[attr-defined]
        if not chunk:
            raise _Unreadable("truncated pack")
        out += d.decompress(chunk, limit + 1 - len(out))
        if len(out) > limit:
            raise _Unreadable("object too large")
    return bytes(out)


def _pack_object(pack: Path, idx: Path, offset: int, depth: int) -> tuple[int, bytes]:
    if depth > MAX_DELTA_DEPTH:
        raise _Unreadable("delta chain too deep")
    with pack.open("rb") as f:
        f.seek(offset)
        b = f.read(1)[0]
        kind, size, shift = (b >> 4) & 7, b & 15, 4
        while b & 0x80:
            b = f.read(1)[0]
            size |= (b & 0x7F) << shift
            shift += 7
            if shift > 63:
                raise _Unreadable("size")
        if kind == OFS_DELTA:
            b = f.read(1)[0]
            back = b & 0x7F
            while b & 0x80:
                b = f.read(1)[0]
                back = ((back + 1) << 7) | (b & 0x7F)
            base_ref: int | bytes = offset - back
        elif kind == REF_DELTA:
            base_ref = f.read(20)
        else:
            base_ref = 0
        if kind not in (COMMIT, OFS_DELTA, REF_DELTA, 2, 3, 4):
            raise _Unreadable("object type")
        data = _inflate(f)
    if kind == OFS_DELTA:
        base_kind, base = _pack_object(pack, idx, int(base_ref), depth + 1)
    elif kind == REF_DELTA:
        at = _pack_offset(idx, bytes(base_ref))
        if at is None:
            raise _Unreadable("delta base outside this pack")
        base_kind, base = _pack_object(pack, idx, at, depth + 1)
    else:
        if len(data) != size:
            raise _Unreadable("size mismatch")
        return kind, data
    return base_kind, _apply_delta(base, data)


def _varint(data: bytes, at: int) -> tuple[int, int]:
    n = shift = 0
    while True:
        b = data[at]
        at += 1
        n |= (b & 0x7F) << shift
        shift += 7
        if not b & 0x80:
            return n, at


def _apply_delta(base: bytes, delta: bytes) -> bytes:
    src, at = _varint(delta, 0)
    dst, at = _varint(delta, at)
    if src != len(base) or dst > MAX_OBJECT:
        raise _Unreadable("delta size")
    out = bytearray()
    while at < len(delta):
        op = delta[at]
        at += 1
        if op & 0x80:
            off = size = 0
            for i in range(4):
                if op & (1 << i):
                    off |= delta[at] << (8 * i)
                    at += 1
            for i in range(3):
                if op & (0x10 << i):
                    size |= delta[at] << (8 * i)
                    at += 1
            size = size or 0x10000
            if off + size > len(base):
                raise _Unreadable("delta copy")
            out += base[off : off + size]
        elif op:
            out += delta[at : at + op]
            at += op
        else:
            raise _Unreadable("delta op")
    if len(out) != dst:
        raise _Unreadable("delta result")
    return bytes(out)


# ---- the commit -----------------------------------------------------------------------------


def _parse_commit(sha: str, raw: bytes, branch: str) -> CommitInfo:
    head, _, message = raw.decode("utf-8", errors="replace").partition("\n\n")
    author = ""
    for line in head.splitlines():
        if line.startswith("author "):
            author = line[7:]
            break
    m = re.fullmatch(r"(.*?)\s*<[^>]*>\s+(\d+)\s+([+-]\d{4})", author)
    if m is None:
        raise _Unreadable("author line")
    name, stamp, tz = m.group(1), int(m.group(2)), m.group(3)
    minutes = (int(tz[1:3]) * 60 + int(tz[3:5])) * (-1 if tz[0] == "-" else 1)
    when = datetime.fromtimestamp(stamp, timezone(timedelta(minutes=minutes)))
    subject = message.strip().splitlines()[0] if message.strip() else ""
    return CommitInfo(
        commit=sha,
        author=name,
        when=when.strftime("%Y-%m-%d %H:%M ") + tz,
        subject=subject[:200],
        branch=branch,
    )
