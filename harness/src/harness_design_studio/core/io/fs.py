"""File-system safety: atomic writes, safe names, long Windows paths, single-instance lock."""

import errno
import fcntl
import hashlib
import json
import os
import platform
import re
import shutil
import sys
import tempfile
import time
import unicodedata
from pathlib import Path
from types import TracebackType

from harness_design_studio.core.errors import ProjectLockedError, SaveError
from harness_design_studio.core.ids import RESERVED

LOCK_NAME = ".harness.lock"


def long_path(path: Path) -> Path:
    """On Windows, prefix absolute paths with `\\\\?\\` so paths over 260 characters work."""
    if sys.platform == "win32":
        text = str(path.resolve())
        if not text.startswith("\\\\?\\"):
            prefix = "\\\\?\\UNC\\" if text.startswith("\\\\") else "\\\\?\\"
            return Path(prefix + (text[2:] if text.startswith("\\\\") else text))
    return path


def slug(name: str) -> str:
    """File-name-safe, lower-case grouping name. Only groups files; loading never depends on it."""
    text = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii").lower()
    text = re.sub(r"[^a-z0-9_-]+", "-", text).strip("-")
    if not text:
        text = "x" + hashlib.sha256(name.encode("utf-8")).hexdigest()[:8]
    if text.split(".")[0] in RESERVED:
        text = "_" + text
    return text[:60]


def _explain(exc: OSError, path: Path) -> str:
    code = exc.errno
    if code == errno.ENOSPC:
        return f"The disk is full, so '{path.name}' could not be saved."
    if code in (errno.EACCES, errno.EPERM, errno.EROFS):
        return f"The folder is read-only or you lack permission to write '{path.name}'."
    if code == errno.ENAMETOOLONG:
        return f"The path to '{path.name}' is too long for this file system."
    return f"'{path.name}' could not be saved ({exc.strerror or 'file system error'})."


def _temp_beside(target: Path) -> tuple[int, Path]:
    """A new, empty temp file next to `target`: unique name, created exclusively and without
    following a link, so a planted file or link of that name can never be written through."""
    fd, name = tempfile.mkstemp(dir=target.parent, prefix=f".{target.name}.", suffix=".tmp")
    return fd, Path(name)


def atomic_write_bytes(
    path: Path, data: bytes, *, backup: bool = True, root: Path | None = None, durable: bool = True
) -> None:
    """Write via temp file, flush, fsync and rename. A crash never leaves a half-written file.
    With `root`, the file must stay inside it (no folder on the way may be a link out of it).
    `durable=False` skips the fsyncs (for files that are rebuilt on demand, such as outputs)."""
    target = long_path(path)
    tmp: Path | None = None
    bak_tmp: Path | None = None
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        if root is not None and escapes_root(long_path(root), target.parent):
            raise SaveError(
                f"'{path.name}' would be written outside the project folder (a link leads out "
                "of it), so nothing was written."
            )
        mode = (target.stat().st_mode & 0o777) if target.exists() else 0o644
        fd, tmp = _temp_beside(target)
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
            fh.flush()
            if durable:
                os.fsync(fh.fileno())
        os.chmod(tmp, mode)
        if backup and target.exists():
            # copy to a temp file and rename it over the backup, so a link named ".bak" is
            # replaced and never followed
            fd, bak_tmp = _temp_beside(target)
            os.close(fd)
            shutil.copyfile(target, bak_tmp)
            os.replace(bak_tmp, target.with_name(target.name + ".bak"))
            bak_tmp = None
        os.replace(tmp, target)
        tmp = None
        if durable:
            _fsync_dir(target.parent)
    except OSError as exc:
        raise SaveError(_explain(exc, path)) from exc
    finally:
        for leftover in (tmp, bak_tmp):
            if leftover is not None:
                leftover.unlink(missing_ok=True)


def escapes_root(root: Path, path: Path) -> bool:
    """True if `path` (after following links) is not inside `root`, e.g. a linked project folder."""
    try:
        return not path.resolve().is_relative_to(root.resolve())
    except (OSError, RuntimeError):
        return True


def _fsync_dir(directory: Path) -> None:
    if sys.platform == "win32":
        return
    try:
        fd = os.open(directory, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(fd)
    except OSError:  # some network file systems refuse; the rename itself already succeeded
        pass
    finally:
        os.close(fd)


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


class ProjectLock:
    """Detects the same project open twice. The lock file holds only pid, host and start time."""

    def __init__(self, root: Path) -> None:
        self.path = long_path(root) / LOCK_NAME
        self._held = False

    def acquire(self) -> None:
        """Take the lock. The whole decision runs under a guard (flock on a sidecar file), so no
        other process can delete our fresh lock between our check and our create."""
        info = {"pid": os.getpid(), "host": platform.node(), "since": int(time.time())}
        guard = self.path.with_name(self.path.name + ".takeover")
        try:
            fd = os.open(guard, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
        except OSError as exc:
            raise SaveError(_explain(exc, guard)) from exc
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            try:
                if self.path.exists() or self.path.is_symlink():
                    if self._is_live_foreign_lock():
                        raise ProjectLockedError(
                            "This project is already open in another instance of the tool. "
                            "Close it there first, or open this copy read-only."
                        )
                    self.path.unlink(missing_ok=True)  # stale lock from a crashed session
                self._create_atomically(info)
                self._held = True
            except FileExistsError:
                raise ProjectLockedError("Could not take the project lock; try again.") from None
            except OSError as exc:
                raise SaveError(_explain(exc, self.path)) from exc
        finally:
            os.close(fd)  # closing releases the flock

    def _create_atomically(self, info: dict[str, object]) -> None:
        """Create the lock file with its content already in it. Creating it empty and filling it in
        afterwards lets another process read it half written, call it stale and delete it."""
        tmp = self.path.with_name(f"{self.path.name}.{os.getpid()}.{os.urandom(4).hex()}.tmp")
        try:
            fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(info, fh)
                fh.flush()
                os.fsync(fh.fileno())
            os.link(tmp, self.path)  # fails with FileExistsError if somebody holds the lock
        finally:
            tmp.unlink(missing_ok=True)

    def _is_live_foreign_lock(self) -> bool:
        try:
            info = json.loads(self.path.read_text(encoding="utf-8"))
            pid, host = int(info["pid"]), str(info["host"])
        except (OSError, ValueError, KeyError, TypeError):
            return False  # unreadable lock: treat as stale
        if host != platform.node():
            return True  # another machine (shared drive): cannot verify, assume alive
        return _pid_alive(pid)  # includes this very process: a second open must be refused

    def release(self) -> None:
        if self._held:
            self.path.unlink(missing_ok=True)
            self._held = False

    def __enter__(self) -> "ProjectLock":
        self.acquire()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.release()
