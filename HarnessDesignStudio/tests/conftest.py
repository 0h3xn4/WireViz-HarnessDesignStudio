import atexit
import os
import shutil
import sys
import tempfile
from collections.abc import Iterator

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# Safety net: a test that builds the editor with the default settings must not read or write the
# developer's own ~/.config (first-run tour, window geometry). Qt resolves the per-user ini
# folder from XDG_CONFIG_HOME on Linux.
_CONFIG_HOME = tempfile.mkdtemp(prefix="harness-tests-config-")
os.environ["XDG_CONFIG_HOME"] = _CONFIG_HOME
atexit.register(shutil.rmtree, _CONFIG_HOME, ignore_errors=True)

# Every process (the one that runs pytest and each pytest-xdist worker) imports this file and so has
# its own folder, which keeps parallel workers from sharing one settings file. A worker ends without
# running the atexit hook, so the folder is removed when pytest unconfigures as well.


def pytest_unconfigure(config: object) -> None:
    shutil.rmtree(_CONFIG_HOME, ignore_errors=True)


@pytest.fixture(autouse=True)
def _full_workspace_for_a_new_settings_file(monkeypatch: pytest.MonkeyPatch) -> None:
    """A settings file with no values gets the simple workspace (D-171), which opens a project on
    the Next step page. The tests written for the full workspace (the diagram, the tabs) build their
    windows on a new file, so they get Full unless a test asks for the real default."""
    from harness_design_studio.gui import next_step

    monkeypatch.setattr(next_step, "FIRST_RUN_WORKSPACE", "full")


@pytest.fixture(autouse=True)
def _close_the_windows_a_test_left_open() -> Iterator[None]:
    """Delete the top-level widgets a test created and did not close (most GUI tests build a
    window and walk away). Each one kept its timers and its child widgets alive for the rest of
    the process, so later tests got slower and slower (a layout test took 77 s after 160 left-over
    windows and 8 s on its own) and a worker grew to several GB. Windows that exist before the
    test starts (those of module-scoped fixtures) are left alone; the editor's own clean-up
    (`ctl.release`: timers, helper process, project lock) runs first."""
    if "PySide6.QtWidgets" not in sys.modules:
        yield  # a test that never imports Qt has nothing to close
        return
    from PySide6.QtCore import QEvent
    from PySide6.QtWidgets import QApplication

    # the list keeps their Python objects alive; before the first test there is no application
    before = QApplication.topLevelWidgets() if QApplication.instance() else []
    yield
    app = QApplication.instance()
    if app is None:
        return
    _release_stray_modifiers(app)
    for widget in QApplication.topLevelWidgets():
        if widget in before:
            continue
        release = getattr(getattr(widget, "ctl", None), "release", None)
        if callable(release):
            release()
        widget.hide()
        widget.deleteLater()
    app.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def _release_stray_modifiers(app: object) -> None:
    """`QTest.keyClick(w, key, Ctrl|Shift)` can leave Shift (or another modifier) pressed as far as
    `QGuiApplication.keyboardModifiers()` goes. A table with extended selection reads that state in
    `selectRow`, so the next test's selection came out toggled or empty. Release what is left."""
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QWidget

    held = QGuiApplication.keyboardModifiers()
    if held == Qt.KeyboardModifier.NoModifier:
        return
    target = QWidget()
    for modifier, key in (
        (Qt.KeyboardModifier.ShiftModifier, Qt.Key.Key_Shift),
        (Qt.KeyboardModifier.ControlModifier, Qt.Key.Key_Control),
        (Qt.KeyboardModifier.AltModifier, Qt.Key.Key_Alt),
        (Qt.KeyboardModifier.MetaModifier, Qt.Key.Key_Meta),
    ):
        if held & modifier:
            QTest.keyRelease(target, key)
    target.deleteLater()
