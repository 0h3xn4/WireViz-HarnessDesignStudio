# mypy: allow-untyped-calls, no-warn-unused-ignores
"""Pictures of the flatsat example in the real editor (offscreen) for docs/FLATSAT_EXAMPLE.md:
the whole diagram, and the same diagram with one unit in focus. Usage: python -m tools.flatsat_screenshots"""

import sys
import tempfile
import time
from pathlib import Path

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

from harness_design_studio.core import templates
from harness_design_studio.gui.main_window import MainWindow
from harness_design_studio.gui.theme import ThemeManager

OUT = Path(__file__).resolve().parents[1] / "docs" / "img"


def _wait(ms: int) -> None:
    """Let the event loop run (a sleep, so background threads are not starved)."""
    end = time.monotonic() + ms / 1000
    while time.monotonic() < end:
        QApplication.processEvents()
        time.sleep(0.02)


def main() -> int:
    QApplication.instance() or QApplication(sys.argv)
    tmp = Path(tempfile.mkdtemp())
    templates.create_project(tmp / "flatsat", "flatsat")
    win = MainWindow(
        QSettings(str(tmp / "ui.ini"), QSettings.Format.IniFormat), ThemeManager(), first_run=False
    )
    win.resize(1600, 1000)  # a big window, so the diagram and its legend have room
    win.show()
    for dock in (win.dock_left, win.dock_right):
        dock.hide()  # the pictures are of the diagram only
    _wait(300)
    assert win.open_project(tmp / "flatsat")
    _wait(1500)  # the marks on the diagram are worked out a moment after the project opens
    win.view.fit()
    _wait(500)
    win.view.grab().save(str(OUT / "flatsat-overview.png"))
    win.ctl.select("unit", "PDU2")
    _wait(500)
    win.view.grab().save(str(OUT / "flatsat-focus.png"))
    print("flatsat-overview.png, flatsat-focus.png")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
