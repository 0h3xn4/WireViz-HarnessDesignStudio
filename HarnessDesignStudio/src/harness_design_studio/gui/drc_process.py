"""Runs the design rule check in a separate, long-lived process.

A Python thread shares the interpreter lock with the editor, so a big check made the interface
stall for hundreds of milliseconds at a time. A process has its own lock. The process starts on the
first check, is reused for later ones and ends with the editor (it exits when its pipe closes).
If it cannot be started, or dies, the check runs in the calling thread as before.
"""

import atexit
import contextlib
import gc
import os
import subprocess
import sys
import threading
import time
from collections.abc import Callable

from harness_design_studio.core import drc
from harness_design_studio.core.checks import Finding
from harness_design_studio.core.drc import worker
from harness_design_studio.core.model import Project

FLAG = "--drc-worker"  # how a frozen (packaged) program is told to act as the worker
PAUSE = 0.0005  # seconds between pieces
CHECK_TIMEOUT_S = 180.0  # a helper that has not finished by then is killed; the check runs here
DISABLE_ENV = "HARNESS_DRC_INPROCESS"  # set to 1 to run the check in a thread (tests, debugging)


def worker_command() -> list[str]:
    if getattr(sys, "frozen", False):
        return [sys.executable, FLAG]
    # -P: do not put the current folder on the module path (a planted module there would run)
    return [sys.executable, "-P", "-m", "harness_design_studio.core.drc.worker"]


class DrcProcess:
    """One child process; calls are serialised."""

    def __init__(self) -> None:
        self._proc: subprocess.Popen[bytes] | None = None
        self._lock = threading.Lock()

    @property
    def alive(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    def run(self, project: Project) -> list[Finding]:
        """Findings for a project. Raises if the process failed, sent something unusable or did not
        finish within CHECK_TIMEOUT_S (TimeoutError); the process is killed in each case."""
        with self._lock:
            proc = self._ensure()
            if proc.stdin is None or proc.stdout is None:
                self._kill()
                raise OSError("the rule check process has no pipes")
            found: list[Finding] = []
            # Building tens of thousands of result objects makes the collector run long full
            # passes, which stop every thread; nothing here is cyclic, so it waits until we are done.
            was_enabled = gc.isenabled()
            gc.disable()
            # A stuck helper is killed from a timer: that ends a blocked read or write at once
            expired = threading.Event()

            def expire() -> None:
                expired.set()
                with contextlib.suppress(OSError):
                    proc.kill()

            timer = threading.Timer(CHECK_TIMEOUT_S, expire)
            timer.daemon = True
            timer.start()
            try:
                for message in worker.project_messages(project):
                    worker.send(proc.stdin, message)
                    time.sleep(PAUSE)  # let the editor's thread have the interpreter between pieces
                while True:
                    reply = worker.receive(proc.stdout)
                    if not isinstance(reply, tuple) or not reply:
                        raise EOFError("the rule check process ended")
                    if reply[0] == "findings":
                        batch = reply[1]
                        if not isinstance(batch, list) or not all(
                            isinstance(f, Finding) for f in batch
                        ):
                            raise RuntimeError("the rule check process sent unusable results")
                        found.extend(batch)
                        time.sleep(PAUSE)
                    elif reply[0] == "done":
                        return found
                    else:
                        raise RuntimeError(f"the rule check failed:\n{reply[-1]}")
            except Exception:  # also a corrupt length or an unreadable reply
                self._kill()
                if expired.is_set():
                    raise TimeoutError("the rule check took too long") from None
                raise
            finally:
                timer.cancel()
                if was_enabled:
                    gc.enable()

    def abort(self) -> None:
        """End a check that is running (or stuck) at once, without waiting for it: the helper is
        killed, so the call blocked on its pipes fails and cleans up by itself."""
        proc = self._proc
        if proc is not None:
            with contextlib.suppress(OSError):
                proc.kill()

    def close(self) -> None:
        # Kill first, without the lock: a check that is stuck holds it, and ends as soon as its
        # pipes close. Then clean up once the lock is free.
        proc = self._proc
        if proc is not None:
            with contextlib.suppress(OSError):
                proc.kill()
        if self._lock.acquire(timeout=5):
            try:
                self._kill()
            finally:
                self._lock.release()

    def _ensure(self) -> subprocess.Popen[bytes]:
        if not self.alive:
            self._kill()
            self._proc = subprocess.Popen(  # noqa: S603 (our own program, fixed arguments)
                worker_command(),
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                close_fds=True,
            )
        if self._proc is None:
            raise OSError("the rule check process could not be started")
        return self._proc

    def _kill(self) -> None:
        proc, self._proc = self._proc, None
        if proc is None:
            return
        for stream in (proc.stdin, proc.stdout):
            try:
                if stream is not None:
                    stream.close()
            except OSError:
                pass
        try:
            proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()


_shared = DrcProcess()
atexit.register(_shared.close)


def abort_check() -> None:
    """Kill the helper if it is busy (the result is not wanted any more)."""
    _shared.abort()


def run_check(project: Project, cancelled: Callable[[], bool] | None = None) -> list[Finding]:
    """The rule check in the helper process; in this thread if that is switched off or fails
    (unless `cancelled()` says nobody wants the result any more: then the failure is raised)."""
    if cancelled is not None and cancelled():
        raise RuntimeError("the rule check was cancelled")
    if os.environ.get(DISABLE_ENV) == "1":
        return drc.run(project)
    try:
        return _shared.run(project)
    except Exception:  # a dead, stuck or confused helper must not decide the result
        if cancelled is not None and cancelled():
            raise
        return drc.run(project)
