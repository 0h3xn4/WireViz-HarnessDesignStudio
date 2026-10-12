from pathlib import Path

import pytest

pytest.importorskip("PySide6")
pytestmark = pytest.mark.gui


def test_window_opens(qtbot, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    from PySide6.QtCore import QSettings

    from harness_design_studio.gui.app import create_window
    from harness_design_studio.gui.strings import APP_TITLE

    # a temporary ini: the test must not read or write the developer's own settings
    win = create_window(QSettings(str(tmp_path / "ui.ini"), QSettings.Format.IniFormat))
    qtbot.addWidget(win)
    win.show()
    assert APP_TITLE in win.windowTitle()
