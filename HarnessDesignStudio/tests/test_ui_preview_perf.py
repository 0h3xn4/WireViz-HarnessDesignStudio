# mypy: disable-error-code="no-untyped-def,no-untyped-call"
"""UI overhaul M6: fit, zoom and pan of a drawing paint a frame in under 50 ms on the flatsat sheet."""

import time

import pytest

from tests.helpers import time_limit

pytest.importorskip("PySide6")
pytestmark = [pytest.mark.gui, pytest.mark.perf]

from PySide6.QtCore import QSettings  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from harness_design_studio.gui.main_window import MainWindow  # noqa: E402
from harness_design_studio.gui.theme import ThemeManager  # noqa: E402
from tests.ux_rel import flatsat_controller  # noqa: E402


@pytest.fixture
def sheet(qtbot, tmp_path):
    ctl = flatsat_controller(tmp_path)
    root = ctl.root
    ctl.release()
    win = MainWindow(
        QSettings(str(tmp_path / "ui.ini"), QSettings.Format.IniFormat),
        ThemeManager(),
        first_run=False,
    )
    qtbot.addWidget(win)
    win.resize(1440, 900)
    win.show()
    assert root is not None and win.open_project(root)
    win.go_to("harness")
    QApplication.processEvents()
    win.harness_view.wait_idle()
    QApplication.processEvents()
    return win.harness_view.preview.view


def frame_ms(sv, change) -> float:
    change()
    t = time.perf_counter()
    sv.viewport().grab()  # one full paint of what is visible
    return (time.perf_counter() - t) * 1000


def test_fit_zoom_and_pan_paint_a_frame_in_under_50_ms(sheet) -> None:
    sv = sheet
    assert sv.scene() is not None
    frame_ms(sv, sv.fit)  # warm up (fonts, caches)
    fit = min(frame_ms(sv, sv.fit) for _ in range(5))
    zoom = min(frame_ms(sv, sv.zoom_in) for _ in range(3))
    sv.zoom_to(4.0)
    bar = sv.horizontalScrollBar()
    pan = min(frame_ms(sv, lambda k=k: bar.setValue(bar.value() + 40 * (k + 1))) for k in range(5))
    assert max(fit, zoom, pan) < time_limit(50), (fit, zoom, pan)
