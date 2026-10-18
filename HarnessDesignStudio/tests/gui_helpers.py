"""Helpers for driving the Qt editor in tests (offscreen)."""

from pathlib import Path

from PySide6.QtCore import QPoint, QPointF, QSettings, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialog

from harness_design_studio.gui.canvas import UnitItem
from harness_design_studio.gui.main_window import MainWindow
from harness_design_studio.gui.theme import ThemeManager


def _discard(title: str, text: str, buttons: list[str]) -> int:
    """Default for unattended tests: pick the 'discard' style answer (second button)."""
    return 1


def make_window(tmp_path: Path, *, first_run: bool = False, journal_ms: int = 20) -> MainWindow:
    _ = QApplication.instance() or QApplication([])  # a QApplication must exist
    settings = QSettings(str(tmp_path / "ui.ini"), QSettings.Format.IniFormat)
    win = MainWindow(settings, ThemeManager(), journal_delay_ms=journal_ms, first_run=first_run)
    win.ask_choice = _discard  # type: ignore[assignment]
    win.resize(1440, 900)
    win.show()
    return win


def show_problems(win: MainWindow):  # type: ignore[no-untyped-def]
    """Bring the problems list to the front (the Problems tab of the right panel) and return it.
    Hidden panels refresh lazily, so tests that read its cards call this first."""
    win.dock_right.show()
    win.inspector.show_tab("problems")
    QApplication.processEvents()
    return win.problems


def action_named(win: MainWindow, name: str):  # type: ignore[no-untyped-def]
    """The window's `QAction` with this object name ("menu-add-payload", "menu-connect-can", ...)."""
    from PySide6.QtGui import QAction

    for act in win.findChildren(QAction):
        if act.objectName() == name:
            return act
    raise AssertionError(f"no action {name!r}")


def add_unit(win: MainWindow, template_id: str) -> None:
    """What the Palette's "＋ <kind>" button did: Edit > Add unit > <kind>."""
    action_named(win, f"menu-add-{template_id}").trigger()


def pick_connect_type(win: MainWindow, type_id: str) -> None:
    """What the Palette's interface type button did: Edit > Connect with > <type> (the arrow next
    to the Connect tool lists the same actions); picking the active type again turns the tool off."""
    action_named(win, f"menu-connect-{type_id}").trigger()


def unit_point(win: MainWindow, unit_id: str, *, port: str | None = None) -> QPoint:
    """Viewport position inside a unit item (its header, or a named connector row in Expert mode)."""
    item = win.view.dscene.unit_items[unit_id]
    if port is not None:
        k = [c.id for c in item.connectors()].index(port)
        local = QPointF(item.port_rect(k).center())
    else:
        local = QPointF(60, 12)
    return win.view.mapFromScene(item.mapToScene(local))


def click_unit(win: MainWindow, unit_id: str, *, port: str | None = None) -> None:
    QTest.mouseClick(
        win.view.viewport(), Qt.MouseButton.LeftButton, pos=unit_point(win, unit_id, port=port)
    )


def click_link(win: MainWindow, interface_id: str) -> None:
    link = win.view.dscene.link_items[interface_id]
    pt = win.view.mapFromScene(link._chip_center)
    QTest.mouseClick(win.view.viewport(), Qt.MouseButton.LeftButton, pos=pt)


def unit_item(win: MainWindow, unit_id: str) -> UnitItem:
    return win.view.dscene.unit_items[unit_id]


class DialogScript:
    """Replaces `run_dialog`: calls `fn(dialog)` and returns Accepted/Rejected as `accept` says."""

    def __init__(self, win: MainWindow, fn=None, accept: bool = True) -> None:  # type: ignore[no-untyped-def]
        self.win, self.fn, self.accept = win, fn, accept
        self.seen: list[QDialog] = []
        win.run_dialog = self  # type: ignore[assignment]

    def __call__(self, dialog: QDialog) -> int:
        self.seen.append(dialog)
        if self.fn:
            self.fn(dialog)
        return int(QDialog.DialogCode.Accepted if self.accept else QDialog.DialogCode.Rejected)


def new_project_answers(
    win: MainWindow,
    folder: Path,
    name: str,
    *,
    template: str | None = None,
    accept: bool = True,
) -> list[QDialog]:
    """Replaces `run_dialog` for "New project": fills the one new-project dialog (folder, name and,
    when given, the example) and answers OK or Cancel. Returns the dialogs that were shown."""
    shown: list[QDialog] = []

    def run(dlg: QDialog) -> int:
        shown.append(dlg)
        dlg.folder.setText(str(folder))  # type: ignore[attr-defined]
        dlg.name.setText(name)  # type: ignore[attr-defined]
        if template is not None:
            assert dlg.select_template(template)  # type: ignore[attr-defined]
        return int(QDialog.DialogCode.Accepted if accept else QDialog.DialogCode.Rejected)

    win.run_dialog = run
    return shown
