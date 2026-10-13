"""GUI entry point."""

import sys
from pathlib import Path

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

from harness_design_studio.gui.appicon import app_icon
from harness_design_studio.gui.main_window import MainWindow
from harness_design_studio.gui.theme import ThemeManager


def make_settings() -> QSettings:
    """Per-user UI settings (mode, theme, scale, last project). No design data is stored here."""
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
    settings = make_settings()
    win = create_window(settings)
    last = settings.value("project/last")
    if last and Path(str(last), "project.json").is_file():
        win.open_project(Path(str(last)))
    win.show()
    return int(app.exec())


if __name__ == "__main__":
    raise SystemExit(main())
