# SPDX-FileCopyrightText: 2026 0h3xn4
# SPDX-License-Identifier: GPL-3.0-only
"""GUI entry point."""

import sys

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

from harness_design_studio.gui.appicon import app_icon
from harness_design_studio.gui.main_window import MainWindow
from harness_design_studio.gui.theme import ThemeManager


def make_settings() -> QSettings:
    """Per-user UI settings (mode, theme, scale, the window's layout, the recent projects). No
    design data is stored here, and not which project was open last: the program starts on Home."""
    return QSettings(
        QSettings.Format.IniFormat, QSettings.Scope.UserScope, "HarnessDesigner", "HarnessDesigner"
    )


def create_window(
    settings: QSettings | None = None, *, first_run: bool | None = None
) -> MainWindow:
    if QApplication.instance() is None:
        QApplication(sys.argv)
    QApplication.setWindowIcon(app_icon())
    QApplication.setDesktopFileName("harness-design-studio")  # the launcher entry, for Wayland
    # the window class on X11 (the launcher's StartupWMClass); without this it is the name of the
    # executable, which differs between the packaged program, the pip command and its alias
    QApplication.setApplicationName("harness-design-studio")
    theme = ThemeManager()
    win = MainWindow(settings or make_settings(), theme, first_run=first_run)
    win.setWindowIcon(app_icon())
    return win


def main() -> int:
    if "--version" in sys.argv[1:]:
        from harness_design_studio import __version__

        print(f"harness-design-studio {__version__}")
        return 0
    app = QApplication.instance() or QApplication(sys.argv)
    win = create_window(make_settings())
    # The landing page: Home, with no project opened. The project that was open when the program
    # was closed is not opened again (D-223); the recent projects are one click away on Home.
    win.show_landing()
    win.show()
    return int(app.exec())


if __name__ == "__main__":
    raise SystemExit(main())
