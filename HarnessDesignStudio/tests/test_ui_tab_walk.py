# mypy: disable-error-code="no-untyped-def,no-untyped-call,attr-defined,union-attr,arg-type"
"""D3 of the 1.8.0 audit: Tab leaves a table. Qt's table view keeps Tab for "next cell" and never lets
go, so a keyboard user with a row selected could not reach the buttons below the Link connectors
pair table, the library list or any table of the main window. The walk below SELECTS a row first
(a new window without a current row hid the problem) and counts the presses. The spreadsheet-style
tables (the pin table of the Devices tab, the Units and Interfaces tabs) keep Tab for the next cell
and leave with Ctrl+Tab."""

from pathlib import Path

import pytest

pytest.importorskip("PySide6")
pytestmark = pytest.mark.gui

from PySide6.QtCore import QSettings, Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication, QTableView, QWidget  # noqa: E402

from harness_design_studio.core.commands import apply_ops  # noqa: E402
from harness_design_studio.core.library_folder import save_devices  # noqa: E402
from harness_design_studio.core.links import plan_add_link  # noqa: E402
from harness_design_studio.core.samples import new_project  # noqa: E402
from harness_design_studio.gui.link_dialog import LinkDialog  # noqa: E402
from harness_design_studio.gui.main_window import MainWindow  # noqa: E402
from harness_design_studio.gui.theme import ThemeManager  # noqa: E402
from tests.gui_helpers import action_named, make_window  # noqa: E402
from tests.helpers import pinout_project  # noqa: E402
from tests.test_ux_devices import custom  # noqa: E402
from tests.ux_rel import flatsat_controller  # noqa: E402

PRESSES = 6  # a table must hand focus on within this many Tab presses


def _inside(table: QWidget, widget: QWidget | None) -> bool:
    return widget is table or (widget is not None and table.isAncestorOf(widget))


def presses_to_leave(table: QTableView, *, ctrl: bool = False, cap: int = 40) -> int:
    """Focus `table` with its first row selected, press Tab (or Ctrl+Tab) until focus is outside
    it. Returns the number of presses, `cap` when it never left."""
    assert table.model() is not None and table.model().rowCount() > 0, table.objectName()
    table.setFocus()
    QApplication.processEvents()
    table.setCurrentIndex(table.model().index(0, 0))
    table.selectRow(0)
    assert table.currentIndex().isValid()
    mod = Qt.KeyboardModifier.ControlModifier if ctrl else Qt.KeyboardModifier.NoModifier
    for n in range(1, cap + 1):
        focus = QApplication.focusWidget()
        assert _inside(table, focus), f"focus left {table.objectName()} unexpectedly"
        QTest.keyClick(focus, Qt.Key.Key_Tab, mod)
        QApplication.processEvents()
        if not _inside(table, QApplication.focusWidget()):
            return n
    return cap


def tab_until(start: QWidget, goal: QWidget, cap: int = 25) -> int:
    """Tab presses from `start` to `goal` (cap + 1 when never reached)."""
    for n in range(1, cap + 1):
        focus = QApplication.focusWidget()
        QTest.keyClick(focus, Qt.Key.Key_Tab)
        QApplication.processEvents()
        if QApplication.focusWidget() is goal:
            return n
    return cap + 1


def linked_project():
    p = pinout_project()
    for a, b in (("OBC-J01", "RW1-J02"), ("PCDU-J02", "OBC-J02")):
        ops, _ = plan_add_link(p, a, b)
        apply_ops(p, ops)
    return p


# ---- the Link connectors window, editing the pairs of a connection -----------------------------


def test_tab_walks_out_of_the_pair_table_to_the_buttons(qtbot) -> None:
    _ = QApplication.instance() or QApplication([])
    dlg = LinkDialog(None, ThemeManager(), linked_project(), link_id="L1")
    qtbot.addWidget(dlg)
    dlg.show()
    QApplication.processEvents()
    assert dlg.table.model().rowCount() > 0 and not dlg.table.tabKeyNavigation()
    assert presses_to_leave(dlg.table) <= PRESSES
    assert tab_until(dlg.table, dlg.ok, cap=30) <= 30  # the Save button below is reachable


# ---- the library window ---------------------------------------------------------------------------


def test_tab_walks_out_of_the_library_list_to_the_buttons(qtbot, tmp_path: Path) -> None:
    lib_dir = tmp_path / "shared"
    lib_dir.mkdir()
    save_devices(lib_dir, linked_project(), ["PCDU"])
    save_devices(lib_dir, linked_project(), ["RW1"])
    win = make_window(tmp_path)
    qtbot.addWidget(win)
    win.ctl._install(new_project(), None, None)
    win.set_library_folder(str(lib_dir))
    action_named(win, "act-library").trigger()
    lib = win.library_window
    qtbot.addWidget(lib)
    assert lib.jobs.wait_idle()
    assert lib.list.model().rowCount() >= 2
    assert presses_to_leave(lib.list) <= PRESSES
    lib.list.setFocus()
    lib.list.selectRow(0)
    assert tab_until(lib.list, lib.close_btn, cap=40) <= 40


# ---- the tables of the main window ------------------------------------------------------------------


@pytest.fixture
def win(qtbot, tmp_path):
    ctl = flatsat_controller(tmp_path)
    root = ctl.root
    ctl.release()  # the window takes the project's lock
    w = MainWindow(
        QSettings(str(tmp_path / "ui.ini"), QSettings.Format.IniFormat),
        ThemeManager(),
        first_run=False,
    )
    w.ask_choice = lambda t, x, b: 1  # type: ignore[assignment]
    qtbot.addWidget(w)
    w.resize(1440, 900)
    w.show()
    assert root is not None and w.open_project(root)
    QApplication.processEvents()
    return w


@pytest.fixture
def devices_win(qtbot, tmp_path):
    """A window on GYRO1 with one connector that has notes (so the notes table is shown)."""
    w = make_window(tmp_path)
    qtbot.addWidget(w)
    w.ctl._install(custom(), None, None)
    w.go_to("devices")
    assert w.devices_view.show_unit("GYRO1")
    QApplication.processEvents()
    return w


def _table(win: MainWindow, name: str) -> QTableView:
    found = [
        t for t in win.findChildren(QTableView) if t.objectName() == name and t.isVisibleTo(win)
    ]
    assert len(found) == 1, f"{name}: {len(found)} visible tables"
    return found[0]


@pytest.mark.parametrize(
    "name", ["devices-note-table", "devices-connector-table", "devices-preview-table"]
)
def test_tab_leaves_the_tables_of_the_devices_tab(devices_win, name: str) -> None:
    table = _table(devices_win, name)
    assert not table.tabKeyNavigation()
    assert presses_to_leave(table) <= PRESSES


@pytest.mark.parametrize(
    ("tab", "name"),
    [
        ("harness", "harness-wire-table"),
        ("harness", "harness-pin-table"),
        ("lists", "list-wirelist"),
    ],
)
def test_tab_leaves_the_tables_of_the_harness_and_lists_tabs(win, tab: str, name: str) -> None:
    win.go_to(tab)
    QApplication.processEvents()
    table = _table(win, name)
    assert not table.tabKeyNavigation()
    assert presses_to_leave(table) <= PRESSES


def test_the_pin_table_keeps_tab_for_cells_and_ctrl_tab_leaves(devices_win) -> None:
    table = _table(devices_win, "devices-pin-table")
    assert table.tabKeyNavigation()
    assert "Ctrl+Tab" in table.toolTip()
    assert presses_to_leave(table, cap=12) == 12  # Tab walks the cells, as a spreadsheet does
    assert presses_to_leave(table, ctrl=True) == 1
    # Ctrl+Shift+Tab goes back to the control before the table
    table.setFocus()
    QTest.keyClick(
        table,
        Qt.Key.Key_Backtab,
        Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier,
    )
    assert not _inside(table, QApplication.focusWidget())


@pytest.mark.parametrize(
    ("show", "name"), [("show_interfaces", "interfaces"), ("show_units", "units")]
)
def test_the_units_and_interfaces_tabs_keep_tab_for_cells_and_ctrl_tab_leaves(
    win, show: str, name: str
) -> None:
    getattr(win, show)()
    QApplication.processEvents()
    table = _table(win, name)
    assert table.tabKeyNavigation() and "Ctrl+Tab" in table.toolTip()
    if table.model().rowCount():
        assert presses_to_leave(table, ctrl=True) == 1
