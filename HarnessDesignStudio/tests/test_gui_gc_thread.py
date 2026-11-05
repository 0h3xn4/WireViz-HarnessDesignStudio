"""The cyclic garbage collector runs on the GUI thread and nowhere else.

CI crashed with `Segmentation fault` in the perf step: the design rule check (a worker thread)
allocated enough to start Python's collector while the GUI thread was inside a generator
expression that calls into Qt, and CPython 3.14 reads the frame of such a generator from the other
thread (`_PyFrame_Traverse`). A Qt object in a reference cycle would likewise be destroyed by the
worker thread, which Qt does not allow. `gui/gc_policy.py` switches the automatic collector off
and collects from a timer on the GUI thread instead."""

import gc
import os
import subprocess
import sys
import textwrap
import threading
import weakref
from pathlib import Path

from PySide6.QtTest import QTest

import harness_design_studio

SRC = Path(harness_design_studio.__file__).resolve().parents[1]
ROOT = Path(__file__).resolve().parents[1]


class _Cycle:
    """An object that only the collector can free."""

    def __init__(self) -> None:
        self.me = self


def _churn(count: int = 60_000) -> list[weakref.ref[_Cycle]]:
    """Make cyclic garbage on the calling thread, enough to cross the collector's threshold many
    times over; returns weak references to some of it."""
    refs: list[weakref.ref[_Cycle]] = []
    for k in range(count):
        item = _Cycle()
        if k % 1000 == 0:
            refs.append(weakref.ref(item))
    return refs


def _collecting_threads(work: object) -> set[int]:
    """The ids of the threads on which the collector started while `work()` ran."""
    seen: set[int] = set()

    def note(phase: str, info: dict[str, int]) -> None:
        if phase == "start":
            seen.add(threading.get_ident())

    gc.callbacks.append(note)
    try:
        work()  # type: ignore[operator]
    finally:
        gc.callbacks.remove(note)
    return seen


def test_a_worker_thread_never_runs_the_collector(qapp) -> None:  # type: ignore[no-untyped-def]
    from harness_design_studio.gui.controller import EditorController

    EditorController()  # the editor takes the collector over when it starts

    def in_a_worker() -> None:
        worker = threading.Thread(target=_churn)
        worker.start()
        worker.join()

    assert _collecting_threads(in_a_worker) == set()


def test_the_gui_thread_collects_what_a_worker_left_behind(qapp) -> None:  # type: ignore[no-untyped-def]
    from harness_design_studio.gui import gc_policy
    from harness_design_studio.gui.controller import EditorController

    EditorController()
    refs: list[weakref.ref[_Cycle]] = []
    worker = threading.Thread(target=lambda: refs.extend(_churn()))
    worker.start()
    worker.join()
    assert any(r() is not None for r in refs)  # nothing has collected it yet
    where = _collecting_threads(lambda: QTest.qWait(3 * gc_policy.TICK_MS))
    assert where == {threading.get_ident()}  # the timer of the GUI thread ran it
    assert all(r() is None for r in refs)


def test_the_policy_takes_the_collector_back_when_something_switches_it_on(qapp) -> None:  # type: ignore[no-untyped-def]
    from harness_design_studio.gui import gc_policy

    assert gc_policy.install() and gc_policy.installed()
    gc.enable()
    try:
        gc_policy.collect_if_due()  # the next tick does this
        assert not gc.isenabled()
        refs = _churn()  # (made with the collector off: nothing ran yet)
        assert any(r() is not None for r in refs)
        assert gc_policy.collect_if_due()  # the counters are far over their threshold
        assert all(r() is None for r in refs)
        assert not gc_policy.collect_if_due()  # the pass reset them
    finally:
        gc_policy.install()


_CHILD = textwrap.dedent(
    """
    import os, sys
    from PySide6.QtCore import QRectF
    from PySide6.QtWidgets import QApplication

    app = QApplication([])
    from harness_design_studio.gui.controller import DrcWorker, EditorController
    from tools.bench_stress import build

    ctl = EditorController()
    project = build()  # 100 devices: a check that allocates for seconds
    rect = QRectF(0, 0, 10, 10)
    moved = [QRectF(100 + i, 100, 5, 5) for i in range(50)]
    worker = DrcWorker(project, (0, 0))
    worker.start()
    while worker.isRunning():  # what the canvas does while it redraws a link's label
        any(m.intersects(rect.adjusted(-2, -2, 2, 2)) for m in moved)
    worker.wait()
    assert worker.error is None, worker.error
    print("done")
    """
)


def test_a_check_beside_a_redraw_does_not_crash_the_program(tmp_path: Path) -> None:
    """The crash itself: a check allocating on its thread while the GUI thread runs a generator
    expression that calls Qt (the way `reroute` does) took the whole process down with a
    segmentation fault, with and without `coverage`. The check runs in a thread of this process
    here (`HARNESS_DRC_INPROCESS`) so that it allocates as much as the helper's reader does."""
    script = tmp_path / "check_beside_redraw.py"
    script.write_text(_CHILD, encoding="utf-8")
    env = {
        **os.environ,
        "PYTHONPATH": os.pathsep.join([str(SRC), str(ROOT)]),
        "QT_QPA_PLATFORM": "offscreen",
        "HARNESS_DRC_INPROCESS": "1",
        "XDG_CONFIG_HOME": str(tmp_path),
    }
    done = subprocess.run(  # noqa: S603 (this interpreter, a script written above)
        [sys.executable, "-X", "faulthandler", str(script)],
        env=env,
        capture_output=True,
        text=True,
        timeout=600,
        cwd=tmp_path,
    )
    assert done.returncode == 0, (done.returncode, done.stderr[:1500])
    assert done.stdout.strip().endswith("done")
