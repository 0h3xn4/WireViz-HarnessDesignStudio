"""File-system safety: atomic writes, safe names, long Windows paths, single-instance lock."""

import errno
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

if sys.platform == "win32":
    import msvcrt
else:
    import fcntl

LOCK_NAME = ".harness.lock"
# Windows opens files in text mode unless told otherwise; elsewhere the flags do not exist
_BINARY = getattr(os, "O_BINARY", 0)
_NOFOLLOW = getattr(os, "O_NOFOLLOW", 0)


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
        is_link = target.is_symlink()  # a link is replaced by the new file, never read through
        mode = (
            (target.stat().st_mode & 0o777) if target.exists() and not is_link else _new_file_mode()
        )
        fd, tmp = _temp_beside(target)
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
            fh.flush()
            if durable:
                os.fsync(fh.fileno())
        os.chmod(tmp, mode)
        if backup and target.exists() and not is_link:
            # copy to a temp file and rename it over the backup, so a link named ".bak" is
            # replaced and never followed; a linked target has no backup (it would copy the
            # content of whatever the link points at into the project)
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


def _new_file_mode() -> int:
    """Mode of a new file: 0o666 without the bits the user's umask removes. Linux tells it in
    /proc; elsewhere a scratch file is created and looked at (changing the umask to read it
    would let a file made by another thread in that moment be created world-writable)."""
    try:
        for line in Path("/proc/self/status").read_text(encoding="ascii").splitlines():
            if line.startswith("Umask:"):
                return 0o666 & ~int(line.split()[1], 8)
    except (OSError, ValueError, IndexError):
        pass
    if sys.platform == "win32":
        return 0o666  # Windows keeps no permission bits beyond read-only
    try:
        probe = Path(tempfile.gettempdir()) / f".umask-probe.{os.getpid()}.{os.urandom(4).hex()}"
        fd = os.open(probe, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o666)
        try:
            return os.fstat(fd).st_mode & 0o777
        finally:
            os.close(fd)
            probe.unlink(missing_ok=True)
    except OSError:
        return 0o644


# `.<name>.<8 random characters>.tmp`: what `_temp_beside` makes (and a killed save leaves behind)
_TEMP_NAME = re.compile(
    r"^\..+\.json(?:\.bak)?\.[a-z0-9_]{8}\.tmp$|^\.gitignore\.[a-z0-9_]{8}\.tmp$"
)


def sweep_stale_temp_files(root: Path, folders: tuple[str, ...]) -> list[str]:
    """Remove temp files that a killed save left in the project (the caller holds the project
    lock, so none of them is in use). Links are never followed. Returns the names removed."""
    removed: list[str] = []
    base = long_path(root)
    for top in ("", *folders):
        start = base / top if top else base
        if start.is_symlink() or not start.is_dir():
            continue
        for current, dirs, names in os.walk(start, followlinks=False):
            if not top:
                dirs[:] = []  # the project folder itself only; the managed folders are listed
            for name in names:
                path = Path(current) / name
                if _TEMP_NAME.match(name) and not path.is_symlink():
                    try:
                        path.unlink()
                    except OSError:
                        continue
                    removed.append(path.relative_to(base).as_posix())
    return sorted(removed)


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


def _boot_id() -> str | None:
    """Identifies this start of the operating system (Linux only; None elsewhere)."""
    try:
        return Path("/proc/sys/kernel/random/boot_id").read_text(encoding="ascii").strip() or None
    except OSError:
        return None


def _start_time(pid: int) -> str | None:
    """When process `pid` started, in clock ticks since boot (Linux /proc; None elsewhere).
    Together with the pid it names one process, even after the number has been reused."""
    try:
        text = Path(f"/proc/{pid}/stat").read_text(encoding="ascii", errors="replace")
        return text.rsplit(")", 1)[1].split()[19]  # field 22; the name (field 2) may hold spaces
    except (OSError, IndexError):
        return None


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if sys.platform == "win32":
        # os.kill(pid, 0) would end the process there. A lock held by another process is told
        # apart in acquire() by whether its file can be removed; here only this process counts.
        return pid == os.getpid()
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


_LOCK_OFFSET = 1 << 20  # Windows: the byte that stands for "this lock file is held" (far beyond
# the few bytes of text in the file, so other processes can still read it)


def _byte_lock(fd: int) -> bool:
    """Windows: try to lock the marker byte of an open lock file; False if another handle has it."""
    if sys.platform == "win32":
        os.lseek(fd, _LOCK_OFFSET, os.SEEK_SET)
        try:
            msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
            return True
        except OSError:
            return False
        finally:
            os.lseek(fd, 0, os.SEEK_SET)
    return False


def _byte_unlock(fd: int) -> None:
    if sys.platform == "win32":
        os.lseek(fd, _LOCK_OFFSET, os.SEEK_SET)
        try:
            msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
        except OSError:
            pass
        finally:
            os.lseek(fd, 0, os.SEEK_SET)


def _lock_guard(fd: int) -> None:
    """Wait for the exclusive lock on the guard file (released when the file is closed)."""
    if sys.platform == "win32":
        while True:  # LK_LOCK itself waits a whole second between its tries, so try quickly here
            try:
                msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
                return
            except OSError:
                time.sleep(0.005)
    fcntl.flock(fd, fcntl.LOCK_EX)


class ProjectLock:
    """Detects the same project open twice. The lock file holds only pid, host and start time."""

    def __init__(self, root: Path) -> None:
        self.path = long_path(root) / LOCK_NAME
        self._held = False
        self._fd: int | None = None  # Windows: the open lock file

    def acquire(self) -> None:
        """Take the lock. The whole decision runs under a guard (a lock on a sidecar file), so no
        other process can delete our fresh lock between our check and our create."""
        info: dict[str, object] = {
            "pid": os.getpid(),
            "host": platform.node(),
            "since": int(time.time()),
        }
        if (boot := _boot_id()) is not None:
            info["boot"] = boot
        if (start := _start_time(os.getpid())) is not None:
            info["start"] = start
        guard = self.path.with_name(self.path.name + ".takeover")
        if not self._worth_locking():
            return
        try:
            fd = os.open(guard, os.O_RDWR | os.O_CREAT | _NOFOLLOW | _BINARY, 0o600)
        except OSError as exc:
            raise SaveError(_explain(exc, guard)) from exc
        try:
            _lock_guard(fd)
            try:
                if self.path.exists() or self.path.is_symlink():
                    if (holder := self._holder()) is not None:
                        raise ProjectLockedError(holder)
                    self._remove_stale()
                self._create(info)
                self._held = True
            except FileExistsError:
                raise ProjectLockedError("Could not take the project lock; try again.") from None
            except OSError as exc:
                raise SaveError(_explain(exc, self.path)) from exc
        finally:
            os.close(fd)  # closing releases the guard

    def _remove_stale(self) -> None:
        """Delete a lock file nobody holds."""
        try:
            self.path.unlink(missing_ok=True)
        except PermissionError:
            if sys.platform != "win32":
                raise
            raise ProjectLockedError(self._held_message(self._pid_in_file())) from None

    def _locked_by_a_live_holder(self) -> bool:
        """Windows: True if another handle (also of this process) holds the marker byte. A file that
        cannot be opened or probed counts as held: nothing is guessed."""
        try:
            fd = os.open(self.path, os.O_RDWR | _BINARY)
        except FileNotFoundError:
            return False
        except OSError:
            return True
        try:
            if _byte_lock(fd):
                _byte_unlock(fd)
                return False
            return True
        finally:
            os.close(fd)

    def _pid_in_file(self) -> int | str:
        try:
            return int(json.loads(self.path.read_text(encoding="utf-8"))["pid"])
        except (OSError, ValueError, KeyError, TypeError):
            return "?"

    def _held_message(self, pid: int | str) -> str:
        return (
            f"This project is already open in another instance of the tool (process {pid}). "
            f"Close it there first (lock file: '{self.path}')."
        )

    def _create(self, info: dict[str, object]) -> None:
        if sys.platform == "win32":
            self._create_open(info)
        else:
            self._create_atomically(info)

    def _create_open(self, info: dict[str, object]) -> None:
        """Windows: create the file and keep it open, with a byte-range lock on its marker byte,
        until release(). When this process dies the system drops the lock, so the next one can
        tell the file is stale."""
        flags = os.O_RDWR | os.O_CREAT | os.O_EXCL | _BINARY
        fd = os.open(self.path, flags, 0o600)
        self._fd = fd
        _byte_lock(fd)  # held until release() or until this process ends
        os.write(fd, json.dumps(info).encode("utf-8"))
        os.fsync(fd)

    def _create_atomically(self, info: dict[str, object]) -> None:
        """Create the lock file with its content already in it. Creating it empty and filling it in
        afterwards lets another process read it half written, call it stale and delete it."""
        tmp = self.path.with_name(f"{self.path.name}.{os.getpid()}.{os.urandom(4).hex()}.tmp")
        try:
            fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | _NOFOLLOW, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(info, fh)
                fh.flush()
                os.fsync(fh.fileno())
            os.link(tmp, self.path)  # fails with FileExistsError if somebody holds the lock
        finally:
            tmp.unlink(missing_ok=True)

    def _worth_locking(self) -> bool:
        """A folder that is neither a project nor empty gets no lock (and no helper file in it):
        there is nothing to protect, and the command reports that it is not a project."""
        root = self.path.parent
        try:
            return (
                not root.is_dir()
                or (root / "project.json").exists()
                or self.path.exists()
                or self.path.is_symlink()
                or self.path.with_name(self.path.name + ".takeover").exists()  # someone locks now
                or not any(root.iterdir())
            )
        except OSError:
            return True

    def _holder(self) -> str | None:
        """None if the lock file is stale (nobody holds it), else the plain-language reason why
        the project counts as open. Nothing is guessed: what cannot be checked counts as held."""
        try:
            info = json.loads(self.path.read_text(encoding="utf-8"))
            pid, host = int(info["pid"]), str(info["host"])
        except (OSError, ValueError, KeyError, TypeError):
            return None  # unreadable lock: treat as stale
        boot, start = info.get("boot"), info.get("start")
        ours = _boot_id()
        same_boot = isinstance(boot, str) and ours is not None and boot == ours
        if host != platform.node() and not same_boot:
            return (
                f"This project is already open on another computer ('{host}'), or that computer "
                "left it locked. That cannot be checked from here. If you are sure nobody has it "
                f"open, delete the lock file '{self.path}' and try again."
            )
        if isinstance(boot, str) and ours is not None and boot != ours:
            return None  # written before the last restart of this computer
        if sys.platform == "win32":
            return self._held_message(pid) if self._locked_by_a_live_holder() else None
        if not _pid_alive(pid):  # includes this very process: a second open must be refused
            return None
        if isinstance(start, str) and (now := _start_time(pid)) is not None and now != start:
            return None  # the process number now belongs to another program
        return self._held_message(pid)

    def release(self) -> None:
        if self._held:
            if self._fd is not None:
                os.close(self._fd)
                self._fd = None
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
