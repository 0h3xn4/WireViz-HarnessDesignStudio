from pathlib import Path

import pytest

pytest.importorskip("PySide6")
pytestmark = pytest.mark.gui


def test_the_window_and_the_application_use_the_logo(qtbot, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    from PySide6.QtCore import QSettings
    from PySide6.QtWidgets import QApplication

    from harness_design_studio.gui.app import create_window
    from harness_design_studio.gui.appicon import PURPLE, SIZES

    win = create_window(QSettings(str(tmp_path / "ui.ini"), QSettings.Format.IniFormat))
    qtbot.addWidget(win)
    assert not win.windowIcon().isNull()
    assert not QApplication.windowIcon().isNull()
    assert {s.width() for s in win.windowIcon().availableSizes()} == set(SIZES)
    img = win.windowIcon().pixmap(64, 64).toImage()
    assert img.pixelColor(32, 4).name() == PURPLE  # the purple tile
    assert img.pixelColor(0, 0).alpha() == 0  # rounded corner
    assert img.pixelColor(16, 18).name() == "#ffffff"  # connector A
