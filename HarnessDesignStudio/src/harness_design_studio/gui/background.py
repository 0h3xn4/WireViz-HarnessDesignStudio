"""Work that must not run on the UI thread, cached by the editor's state token.

`JobRunner(ctl)` runs one function per `(kind, key)` at a time in a `QThread` and hands the finished
`Job` to its `done` signal on the UI thread. The function should work on a private copy of the
project (`edit.clone_with(project, [])`, cheap because entities are immutable), like `PlanWorker` and
`DrcWorker`. A request made while the same `(kind, key)` is still running replaces the one waiting
behind it, so a burst of edits costs one extra run, not one per edit.
"""

from collections.abc import Callable
from time import perf_counter
from typing import Any

from PySide6.QtCore import QCoreApplication, QElapsedTimer, QObject, QThread, Signal

from harness_design_studio.gui.controller import EditorController, reason_of


class Job(QThread):
    """One run of `fn()` off the UI thread; `value` holds the result, or `error` the reason."""

    def __init__(
        self, fn: Callable[[], Any], token: tuple[int, int], kind: str, key: Any = None
    ) -> None:
        super().__init__()
        self.fn, self.token, self.kind, self.key = fn, token, kind, key
        self.value: Any = None
        self.error: str | None = None
        self.ms = 0.0

    def run(self) -> None:
        t0 = perf_counter()
        try:
            self.value = self.fn()
        except Exception as exc:  # shown as the reason, never as a pass
            self.error = reason_of(exc)
        self.ms = (perf_counter() - t0) * 1000


class JobRunner(QObject):
    done = Signal(object)  # the finished Job

    def __init__(self, ctl: EditorController) -> None:
        super().__init__()
        self.ctl = ctl
        self._running: dict[tuple[str, Any], Job] = {}
        self._waiting: dict[tuple[str, Any], Callable[[], Any]] = {}

    def start(self, kind: str, key: Any, fn: Callable[[], Any]) -> None:
        """Run `fn` in the background for the editor's current state token."""
        slot = (kind, key)
        token = self.ctl.state_token
        running = self._running.get(slot)
        if running is not None:
            if running.token != token:
                self._waiting[slot] = fn  # newer than the running one: run it afterwards
            return
        job = Job(fn, token, kind, key)
        self._running[slot] = job
        job.finished.connect(lambda j=job: self._finished(j))
        job.start()

    def busy(self) -> bool:
        return bool(self._running)

    def is_current(self, job: Job) -> bool:
        """Was the job started for the state the editor is in now?"""
        return job.token == self.ctl.state_token

    def _finished(self, job: Job) -> None:
        job.wait()
        slot = (job.kind, job.key)
        if self._running.get(slot) is job:
            del self._running[slot]
        again = self._waiting.pop(slot, None)
        if again is not None:
            self.start(job.kind, job.key, again)
        self.done.emit(job)

    def wait_idle(self, timeout_ms: int = 10000) -> bool:
        """Wait, keeping the event loop going, until everything started has been delivered. For
        tests and screenshots; the window never needs it."""
        clock = QElapsedTimer()
        clock.start()
        while self._running and clock.elapsed() < timeout_ms:
            QCoreApplication.processEvents()
            for job in list(self._running.values()):
                job.wait(5)
        QCoreApplication.processEvents()
        return not self._running
