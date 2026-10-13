# mypy: allow-untyped-calls
"""Time editor interactions on a stress-size project (offscreen). Usage: python -m tools.bench_gui"""

import sys
import tempfile
import time
from pathlib import Path

from PySide6.QtWidgets import QApplication

from harness_design_studio.gui.canvas import DiagramView
from harness_design_studio.gui.controller import EditorController
from harness_design_studio.gui.main_window import MainWindow
from harness_design_studio.gui.theme import ThemeManager
from tools.bench_stress import build


def idle(wait_ms: int = 450) -> None:
    """Let timers from the previous edit (lists, overview map, status hash) finish first."""
    from PySide6.QtCore import QEventLoop, QTimer

    loop = QEventLoop()
    QTimer.singleShot(wait_ms, loop.quit)
    loop.exec()


def ms(fn):  # type: ignore[no-untyped-def]
    idle()
    t = time.perf_counter()
    fn()
    QApplication.processEvents()
    return round((time.perf_counter() - t) * 1000)


def main() -> None:
    app = QApplication.instance() or QApplication(sys.argv)
    theme = ThemeManager()
    assert isinstance(app, QApplication)
    theme.apply(app, "light", 1.0)
    from PySide6.QtCore import QSettings

    win = MainWindow(
        QSettings(str(Path(tempfile.mkdtemp()) / "ui.ini"), QSettings.Format.IniFormat),
        theme,
        first_run=False,
    )
    win.resize(1440, 900)
    win.show()
    ctl: EditorController = win.ctl
    import os

    if os.environ.get("SWITCH"):
        sys.setswitchinterval(float(os.environ["SWITCH"]))
    if os.environ.get("NODRC"):
        ctl._start_drc = lambda: None  # type: ignore[method-assign]
    view: DiagramView = win.view
    project = build()
    print("install + autoplace", ms(lambda: ctl._install(project, None, None)), "ms")
    print("fit (all 200 units, 2000 links visible)", ms(view.fit), "ms")
    for name, fn in (
        ("select unit", lambda: ctl.select("unit", "U005")),
        ("select other unit", lambda: ctl.select("unit", "U006")),
        ("rename unit name", lambda: ctl.update_unit("U001", name="renamed")),
        ("move unit", lambda: ctl.move_unit("U003", 500, 300)),
    ):
        print(f"{name:28}", [ms(fn) for _ in range(3)], "ms")
    # undo and redo are timed in whole cycles (add, undo, redo, undo): the first undo after
    # start-up pays for one-off work and says little about the next ones
    cycles = [
        (ms(lambda: ctl.add_unit("computer")), ms(ctl.undo), ms(ctl.redo), ms(ctl.undo))
        for _ in range(3)
    ]
    for label, column in (("add unit", 0), ("undo", 1), ("redo", 2), ("undo (again)", 3)):
        print(f"{label:28}", [c[column] for c in cycles], "ms")
    print(f"{'full repaint (grab)':28}", [ms(lambda: view.grab()) for _ in range(3)], "ms")
    win.tabs.setCurrentIndex(0)
    print("problems tab visible: change", ms(lambda: ctl.update_unit("U002", name="x")), "ms")
    win.tabs.setCurrentIndex(2)
    print("table tab visible: change", ms(lambda: ctl.update_unit("U002", name="y")), "ms")
    ctl.release()


if __name__ == "__main__":
    main()
