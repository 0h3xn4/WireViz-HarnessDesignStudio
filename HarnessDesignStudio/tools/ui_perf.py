# mypy: allow-untyped-calls, no-warn-unused-ignores
"""Start-up, tab switching, theme switch, UI scale and selection timings of the editor on the flatsat
example (offscreen). The baseline before the UI overhaul is in docs/ui/PERF_BASELINE.md.
Usage: python -m tools.ui_perf"""

import shutil
import statistics
import sys
import tempfile
import time
from pathlib import Path

t_start = time.perf_counter()
from PySide6.QtCore import QSettings  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from harness_design_studio.gui.main_window import MainWindow  # noqa: E402
from harness_design_studio.gui.theme import ThemeManager  # noqa: E402
from harness_design_studio.resources import examples_path  # noqa: E402

TABS = ("harness", "lists", "checks", "releases", "devices")


def _ms(since: float) -> float:
    return (time.perf_counter() - since) * 1000


def _pump(app: QApplication, seconds: float) -> None:
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        app.processEvents()
        time.sleep(0.02)


def main() -> int:
    t_import = _ms(t_start)
    app = QApplication.instance() or QApplication(sys.argv)
    assert isinstance(app, QApplication)
    root = examples_path()
    assert root is not None
    tmp = Path(tempfile.mkdtemp())
    shutil.copytree(root / "projects" / "flatsat", tmp / "flatsat")
    settings = QSettings(str(tmp / "ui.ini"), QSettings.Format.IniFormat)
    t = time.perf_counter()
    win = MainWindow(settings, ThemeManager(), first_run=False)
    t_ctor = _ms(t)
    t = time.perf_counter()
    win.resize(1440, 900)
    win.show()
    app.processEvents()
    t_show = _ms(t)
    t = time.perf_counter()
    assert win.open_project(tmp / "flatsat")
    app.processEvents()
    t_open = _ms(t)
    print(
        f"import {t_import:.0f} ms | MainWindow() {t_ctor:.0f} | show {t_show:.0f} | "
        f"open flatsat {t_open:.0f} | total {t_import + t_ctor + t_show + t_open:.0f}"
    )
    _pump(app, 3)
    for name in TABS:
        times = []
        for _ in range(5):
            win.go_to("diagram")
            app.processEvents()
            t = time.perf_counter()
            win.go_to(name)
            app.processEvents()
            times.append(_ms(t))
        print(
            f"tab {name}: first {times[0]:.0f} ms, median {statistics.median(times):.0f}, "
            f"max {max(times):.0f}"
        )
    for mode in ("dark", "light", "dark"):
        t = time.perf_counter()
        win.set_theme_mode(mode)
        app.processEvents()
        print(f"theme switch to {mode}: {_ms(t):.0f} ms")
    for scale in (125, 150, 100):
        t = time.perf_counter()
        win.scale_actions[scale].trigger()
        app.processEvents()
        print(f"UI scale {scale}: {_ms(t):.0f} ms")
    times = []
    for unit in list(win.ctl.project.units)[:10]:
        t = time.perf_counter()
        win.ctl.select("unit", unit)
        app.processEvents()
        times.append(_ms(t))
    print(f"select unit: median {statistics.median(times):.0f} ms, max {max(times):.0f}")
    win.hide()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
