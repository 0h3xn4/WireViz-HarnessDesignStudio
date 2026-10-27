# mypy: disable-error-code="no-untyped-def,no-untyped-call,attr-defined,union-attr,arg-type"
"""E-F5 of the 1.8.0 audit: the keyboard and mouse path of a connection line on the diagram
(`gui/canvas_links.py`) had no test. Tab reaches the line, Enter opens the Link connectors window,
Space selects it, a double-click opens it, and the tooltip names the connectors."""

import pytest

pytest.importorskip("PySide6")
pytestmark = pytest.mark.gui

from PySide6.QtCore import QEvent, QPointF, Qt  # noqa: E402
from PySide6.QtGui import QKeyEvent  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication, QGraphicsSceneMouseEvent  # noqa: E402

from harness_design_studio.gui import strings  # noqa: E402
from harness_design_studio.gui.canvas_links import connection_route  # noqa: E402
from harness_design_studio.gui.link_dialog import LinkDialog  # noqa: E402
from tests.gui_helpers import DialogScript  # noqa: E402
from tests.test_ui_links import RS, link_up, window  # noqa: E402


@pytest.fixture
def line(tmp_path):
    win = window(tmp_path)
    assert link_up(win) == "L1"
    win.view.setFocus()
    QApplication.processEvents()
    opened: list[tuple[str, str]] = []
    win.ctl.openRequested.connect(lambda kind, ident: opened.append((kind, ident)))
    win.ctl.select_link(None)
    win.shown = DialogScript(win, accept=False)  # the Link connectors window opens, then Cancel
    return win, win.view.dscene.connection_items["L1"], opened


def test_tab_reaches_the_connection_line_after_the_devices(line) -> None:
    win, item, _opened = line
    order = win.view.focus_order()
    assert item in order and order.index(item) == len(order) - 1  # devices first, then the line
    for _ in range(len(order)):
        if win.view.dscene.focusItem() is item:
            break
        QTest.keyClick(win.view, Qt.Key.Key_Tab)
    assert win.view.dscene.focusItem() is item and item.hasFocus()
    QTest.keyClick(win.view, Qt.Key.Key_Backtab)  # and back to the device before it
    assert win.view.dscene.focusItem() is not item


def test_enter_on_the_focused_line_asks_for_the_link_window(line) -> None:
    win, item, opened = line
    item.setFocus(Qt.FocusReason.TabFocusReason)
    QTest.keyClick(win.view, Qt.Key.Key_Return)
    assert opened == [("link", "L1")]
    assert win.ctl.selected_link == "L1"
    (dialog,) = win.shown.seen  # the window that edits the pairs of this connection
    assert isinstance(dialog, LinkDialog) and dialog.objectName() == "link-dialog"
    assert dialog.table.model().rowCount() == 4


def test_space_selects_the_line_and_does_not_open_the_window(line) -> None:
    win, item, opened = line
    item.setFocus(Qt.FocusReason.TabFocusReason)
    QTest.keyClick(win.view, Qt.Key.Key_Space)  # the view acts on Space when it is let go
    assert win.ctl.selected_link == "L1" and opened == []
    win.ctl.select_link(None)
    item.keyPressEvent(_Key(Qt.Key.Key_Space))  # the item itself does the same
    assert win.ctl.selected_link == "L1" and opened == []
    item.keyPressEvent(_Key(Qt.Key.Key_Enter))
    assert opened == [("link", "L1")]


def test_another_key_is_left_to_qt(line) -> None:
    win, item, opened = line
    item.setFocus(Qt.FocusReason.TabFocusReason)
    event = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_X, Qt.KeyboardModifier.NoModifier)
    event.ignore()
    item.keyPressEvent(event)
    assert opened == [] and win.ctl.selected_link is None and not event.isAccepted()
    assert win.shown.seen == []


def test_a_double_click_asks_for_the_link_window_but_not_with_the_connect_tool(line) -> None:
    win, item, opened = line
    item.mouseDoubleClickEvent(_Mouse())
    assert opened == [("link", "L1")] and win.ctl.selected_link == "L1"
    assert len(win.shown.seen) == 1 and isinstance(win.shown.seen[0], LinkDialog)
    opened.clear()
    win.ctl.begin_connect(None)
    assert win.ctl.tool == "connect"
    item.mouseDoubleClickEvent(_Mouse())  # the Connect tool picks devices, it does not open
    assert opened == []
    ignored = _Mouse()
    item.mousePressEvent(ignored)
    assert ignored.ignored  # (the click goes on to the device under the pointer)


def test_a_click_selects_and_takes_the_focus(line) -> None:
    win, item, _opened = line
    item.mousePressEvent(_Mouse())
    assert win.ctl.selected_link == "L1" and item.hasFocus()
    other = _Mouse(Qt.MouseButton.RightButton)
    win.ctl.select_link(None)
    item.mousePressEvent(other)
    assert win.ctl.selected_link is None and other.accepted  # only the left button selects


def test_the_tooltip_names_the_connectors_the_pairs_and_the_harness(line) -> None:
    win, item, _opened = line
    html = item.tooltip_html()
    assert RS[0] in html and RS[1] in html and "RS-422" in html
    assert strings.LINK_TIP_NO_HARNESS in html and strings.LINK_TIP_OPEN in html
    assert strings.LINK_TIP_PATH not in html  # no harness yet, so no way through one
    item.hoverEnterEvent(None)
    assert item.toolTip() == html
    item.hoverLeaveEvent(None)
    # a harness made from the connection adds the way through it
    assert win.ctl.create_harness_from_link("L1")
    QApplication.processEvents()
    html = item.tooltip_html()
    assert strings.LINK_TIP_PATH in html and win.ctl.project.links["L1"].harness_id in html
    assert strings.LINK_TIP_NO_HARNESS not in html
    # a connection that is gone gives no tooltip
    win.ctl.undo()
    win.ctl.undo()
    assert item.tooltip_html() == ""


def test_the_tooltip_carries_what_the_review_says(tmp_path) -> None:
    win = window(tmp_path)
    assert win.ctl.add_link(*RS, [("1", "3"), ("2", "4")]) == "L1"  # two of four pins paired
    win.ctl.run_drc_now()
    QApplication.processEvents()
    item = win.view.dscene.connection_items["L1"]
    sentence = win.view.dscene.states.of("link", "L1").sentence()
    html = item.tooltip_html()
    if sentence:
        assert strings.LINK_TIP_CHECKS in html


def test_a_line_whose_device_is_gone_draws_nothing(line) -> None:
    win, item, _opened = line
    assert item.poly and not item.path().isEmpty()
    scene = win.view.dscene
    kept = scene.unit_items.pop("RW1")
    try:
        item.update_path()
        assert item.poly == [] and item.path().isEmpty()
        item.update_path()  # again: nothing to redraw
    finally:
        scene.unit_items["RW1"] = kept
    item.update_path()
    assert item.poly and not item.path().isEmpty()


def test_a_route_from_the_left_edge_of_the_right_device_meets_in_the_gap() -> None:
    assert connection_route((300.0, 10.0), "left", (100.0, 50.0), "right") == [
        (300.0, 10.0),
        (200.0, 10.0),
        (200.0, 50.0),
        (100.0, 50.0),
    ]
    assert connection_route((100.0, 10.0), "right", (300.0, 50.0), "left")[1] == (200.0, 10.0)


class _Key:
    def __init__(self, key):
        self._key = key
        self.accepted = False

    def key(self):
        return self._key

    def accept(self):
        self.accepted = True

    def ignore(self):
        self.accepted = False

    def isAccepted(self):
        return self.accepted


class _Mouse:
    def __init__(self, button=Qt.MouseButton.LeftButton):
        self._button = button
        self.accepted = False
        self.ignored = False

    def button(self):
        return self._button

    def accept(self):
        self.accepted = True

    def ignore(self):
        self.ignored = True

    def scenePos(self):
        return QPointF(0, 0)


_ = QGraphicsSceneMouseEvent  # (the stubs above stand in for it)
