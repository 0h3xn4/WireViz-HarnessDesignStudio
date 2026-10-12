"""Runs the design rule check in a separate, long-lived process.

A Python thread shares the interpreter lock with the editor, so a big check made the interface
stall for hundreds of milliseconds at a time. A process has its own lock. The process starts on the
first check, is reused for later ones and ends with the editor (it exits when its pipe closes).
If it cannot be started, or dies, the check runs in the calling thread as before.
"""

import atexit
import gc
import os
import subprocess
import sys
import threading
import time

from harness_design_studio.core import drc
from harness_design_studio.core.checks import Finding
from harness_design_studio.core.drc import worker
from harness_design_studio.core.model import Project

FLAG = "--drc-worker"  # how a frozen (packaged) program is told to act as the worker
PAUSE = 0.0005  # seconds between pieces
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
        """Findings for a project. Raises OSError/EOFError/RuntimeError if the process failed."""
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
            try:
                for message in worker.project_messages(project):
                    worker.send(proc.stdin, message)
                    time.sleep(PAUSE)  # let the editor's thread have the interpreter between pieces
                while True:
                    reply = worker.receive(proc.stdout)
                    if not isinstance(reply, tuple) or not reply:
                        raise EOFError("the rule check process ended")
                    if reply[0] == "findings":
                        found.extend(reply[1])
                        time.sleep(PAUSE)
                    elif reply[0] == "done":
                        return found
                    else:
                        raise RuntimeError(f"the rule check failed:\n{reply[-1]}")
            except (ValueError, EOFError, OSError):
                self._kill()
                raise
            finally:
                if was_enabled:
                    gc.enable()

    def close(self) -> None:
        with self._lock:
            self._kill()

    def _ensure(self) -> "subprocess.Popen[bytes]":
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


def run_check(project: Project) -> list[Finding]:
    """The rule check in the helper process; in this thread if that is switched off or fails."""
    if os.environ.get(DISABLE_ENV) == "1":
        return drc.run(project)
    try:
        return _shared.run(project)
    except (OSError, EOFError):
        return drc.run(project)
