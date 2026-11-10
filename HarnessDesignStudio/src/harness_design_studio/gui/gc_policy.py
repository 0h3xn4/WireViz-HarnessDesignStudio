# SPDX-FileCopyrightText: 2026 0h3xn4
# SPDX-License-Identifier: GPL-3.0-only
"""Cyclic garbage is collected on the GUI thread, and only there.

Python's collector runs on whichever thread happens to allocate the object that crosses its
threshold. The editor has worker threads (the design rule check, the autosave journal, the plan and
output jobs) that build tens of thousands of objects, so the collector kept starting on one of them
while the GUI thread was in the middle of a redraw. That is unsafe in two ways:

* a Qt object in a reference cycle (a graphics item, a widget wrapper) is destroyed by the thread
  that collects it, and Qt objects may only be destroyed on their own thread;
* CPython 3.14 walks the frame of a generator that another thread is running while it collects.
  If the GUI thread is inside a generator expression that calls into Qt, the stack of that frame
  is not in a state the walk can read, and the process dies with a segmentation fault in
  `_PyFrame_Traverse` (seen in CI under `coverage`, whose tracing makes the collector run often).

So the automatic collector is switched off when the first editor starts, and a timer on the GUI
thread runs it on the same schedule (`gc.get_count()` against `gc.get_threshold()`). Garbage that a
worker made waits at most one tick. The tests call `collect_if_due` between tests for the same
reason. Programs that are not the editor (the command line, the scripting interface) are not
touched.
"""

import gc

from PySide6.QtCore import QCoreApplication, QObject, QThread, QTimer

TICK_MS = 500  # how often the GUI thread looks whether a collection is due

_timer: QTimer | None = None


def collect_if_due() -> bool:
    """Run the collection that the automatic collector would have run by now (young, middle or
    full, by the same counters and thresholds), on the calling thread. True if one ran."""
    if gc.isenabled():  # something switched the collector back on: take it over again
        gc.disable()
    young, middle, old = gc.get_count()
    limit_young, limit_middle, limit_old = gc.get_threshold()
    if young <= limit_young:
        return False
    gc.collect(2 if old > limit_old else 1 if middle > limit_middle else 0)
    return True


def _alive(timer: QObject | None) -> bool:
    if timer is None:
        return False
    try:
        timer.objectName()
    except RuntimeError:  # the C++ object went with its application
        return False
    return True


def install() -> bool:
    """Take the automatic collector over on this (the GUI) thread. Safe to call again. Does
    nothing, and leaves the collector alone, without an application or off its thread: no timer
    could run the collections then."""
    global _timer
    app = QCoreApplication.instance()
    if app is None or QThread.currentThread() is not app.thread():
        return False
    if not _alive(_timer):
        _timer = QTimer(app)
        _timer.setInterval(TICK_MS)
        _timer.timeout.connect(collect_if_due)
        _timer.start()
    gc.disable()
    return True


def installed() -> bool:
    return _alive(_timer)
