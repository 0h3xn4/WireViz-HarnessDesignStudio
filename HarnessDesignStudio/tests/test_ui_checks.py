# mypy: disable-error-code="no-untyped-def,no-untyped-call"
"""UI overhaul M5: the Problems panel and the Checks tab. A click goes to every kind of object a
finding can name, an out-of-date result says so at once, and a row opens its details."""

import pytest

pytest.importorskip("PySide6")
pytestmark = pytest.mark.gui

from PySide6.QtCore import QSettings, Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from harness_design_studio.gui import strings  # noqa: E402
from harness_design_studio.gui.inspector import TABS  # noqa: E402
from harness_design_studio.gui.main_window import MainWindow  # noqa: E402
from harness_design_studio.gui.theme import ThemeManager  # noqa: E402
from tests.ux_rel import flatsat_controller, release_all  # noqa: E402


@pytest.fixture
def win(qtbot, tmp_path):
    ctl = flatsat_controller(tmp_path)
    root = ctl.root
    ctl.release()
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


def test_a_finding_goes_to_its_object_for_every_kind_of_object(win) -> None:
    c = win.ctl
    p = c.project
    # generate harnesses so that wires and cable connectors exist
    assert release_all(c, ["W001"]) == ["W001"]
    h = p.harnesses["W001"]
    box = next(x for x in p.connectors.values() if x.unit_id)
    messages: list[str] = []
    win.toasts.show_message = lambda text, undo=None: messages.append(text)  # type: ignore[assignment,method-assign]

    win.show_object("PDU2")  # a unit: on the diagram, selected
    assert win.main_tabs.currentWidget() is win.main_tabs.widget_of("diagram")
    assert c.selection is not None and (c.selection.kind, c.selection.id) == ("unit", "PDU2")

    win.show_object("IF-001")  # an interface
    assert (c.selection.kind, c.selection.id) == ("interface", "IF-001")  # type: ignore[union-attr]

    win.show_object(box.id)  # a connector of a unit: the unit
    assert (c.selection.kind, c.selection.id) == ("unit", box.unit_id)  # type: ignore[union-attr]

    win.show_object(h.wires[0].id)  # a wire: its harness, in Drawings
    assert win.area() == "drawings"
    win.set_area("model")
    win.show_object("W001")  # a harness
    assert win.area() == "drawings"

    part = next(iter(p.parts))  # a part: in Devices
    win.show_object(part)
    assert win.area() == "model"
    assert win.main_tabs.currentWidget() is win.main_tabs.widget_of("devices")

    name = next(iter(p.config))  # an engineering value file: its window
    win.show_object(name)
    dialog = win.checks_panel.config_dialog()
    assert dialog is not None and dialog.isVisible()
    dialog.close()

    win.show_object("no-such-object")  # nothing to show says so
    assert messages and messages[-1] == strings.NOTHING_TO_SHOW


def test_an_out_of_date_result_says_so_at_once_and_a_new_check_is_on_its_way(win, qtbot) -> None:
    c = win.ctl
    c.run_drc_now()
    win.go_to("checks")
    QApplication.processEvents()
    panel = win.checks_panel
    assert not panel.stale.isVisibleTo(panel)
    c.update_unit("PDU2", name="Changed after the check")
    QApplication.processEvents()
    assert c.drc_scheduled and not c.drc_current
    assert panel.stale.isVisibleTo(panel) and panel.stale.text() == strings.CHECKS_STALE
    assert panel.stale.toolTip() == strings.CHECKS_STALE_SOON
    c.run_drc_now()
    QApplication.processEvents()
    assert not panel.stale.isVisibleTo(panel)


def test_a_cancelled_check_does_not_claim_a_new_one_is_coming(win) -> None:
    c = win.ctl
    c.run_drc_now()
    c.update_unit("PDU2", name="Changed")
    c._drc_timer.stop()  # (the person pressed Cancel before it began)
    win.go_to("checks")
    win.checks_panel.refresh()
    assert win.checks_panel.status.text() == strings.CHECKS_CANCELLED
    assert win.checks_panel.stale.toolTip() == strings.CHECKS_STALE_TIP


def test_a_problem_row_opens_its_details_and_goes_to_the_object(win, qtbot) -> None:
    win.toggle_problems()
    qtbot.waitUntil(lambda: win.problems_list.total() > 0, timeout=5000)
    panel = win.problems_list
    rows = panel.rows()
    row = next(i for i, r in enumerate(rows) if r.get("object_id"))
    target = rows[row]["object_id"]
    index = panel.table.proxy.mapFromSource(panel.model.index(row, 0))
    asked: list[str] = []
    panel.detailsRequested.connect(asked.append)
    panel._details(index)
    assert asked == [target]
    win._problem_details(target)
    assert win.dock_right.isVisible()
    assert win.side_tabs.currentWidget() is win.inspector
    assert win.inspector.tabs.currentIndex() == TABS.index("problems")


def test_the_row_menu_offers_go_to_and_details(win, qtbot) -> None:
    win.toggle_problems()
    qtbot.waitUntil(lambda: win.problems_list.total() > 0, timeout=5000)
    panel = win.problems_list
    rect = panel.table.visualRect(panel.table.proxy.index(0, 1))
    panel._menu(rect.center())
    texts = [a.text() for a in panel.menu.actions()]
    assert texts[1] == strings.PROBLEMS_DETAILS and texts[0].startswith("Go to ")
    panel.menu.close()


def test_shift_enter_in_the_problems_table_asks_for_details(win, qtbot) -> None:
    win.toggle_problems()
    qtbot.waitUntil(lambda: win.problems_list.total() > 0, timeout=5000)
    panel = win.problems_list
    asked: list[str] = []
    panel.detailsRequested.connect(asked.append)
    panel.table.setFocus()
    panel.table.setCurrentIndex(panel.table.proxy.index(0, 0))
    QTest.keyClick(panel.table, Qt.Key.Key_Return, Qt.KeyboardModifier.ShiftModifier)
    assert len(asked) == 1
