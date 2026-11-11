# SPDX-FileCopyrightText: 2026 0h3xn4
# SPDX-License-Identifier: GPL-3.0-only
# mypy: disable-error-code="no-untyped-def,no-untyped-call"
"""Text that was cut although there was room, or that made a panel wider than itself (found by
the end-to-end test of 1.17.1 at the default window size of 1360 x 860 with a wide left panel):
the project name in the top bar, the cards and tabs of the right panel, the messages over the
diagram and the hint of the Connect tool."""

import pytest

pytest.importorskip("PySide6")
pytestmark = pytest.mark.gui

from PySide6.QtCore import QSize, Qt  # noqa: E402
from PySide6.QtWidgets import (  # noqa: E402
    QApplication,
    QGraphicsView,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QWidget,
)

from harness_design_studio.core import templates  # noqa: E402
from harness_design_studio.gui.main_window import ToastHost  # noqa: E402
from harness_design_studio.gui.shell import ElidedLabel  # noqa: E402
from harness_design_studio.gui.wrap_label import SOFT_BREAK, breakable  # noqa: E402
from tests.gui_helpers import make_window, show_problems  # noqa: E402

LONG_MESSAGE = (
    "Interface IF-002 added. Connectors were chosen for you and are marked Auto until you "
    "confirm them."
)


def settle() -> None:
    for _ in range(3):
        QApplication.processEvents()


# ---- the name in the top bar --------------------------------------------------------------------


def test_an_elided_label_shows_its_whole_new_text_when_there_is_room(qtbot) -> None:
    """The name of a project opened from Home was drawn "Wheel…k E2E" in a bar with room for it:
    the label's size hint followed the new text, but the layout was not told."""
    row = QWidget()
    qtbot.addWidget(row)
    lay = QHBoxLayout(row)
    name = ElidedLabel("A")
    name.setSizePolicy(name.sizePolicy().Policy.Preferred, name.sizePolicy().Policy.Preferred)
    rest = ElidedLabel("Diagram")
    lay.addWidget(name)
    lay.addWidget(rest, 1)
    row.resize(600, 40)
    row.show()
    settle()
    name.set_full_text("Wheel link E2E")
    settle()
    assert name.width() >= name.sizeHint().width()
    assert name.shown_text() == "Wheel link E2E"


# ---- the right panel ----------------------------------------------------------------------------


@pytest.fixture
def narrow_right(qtbot, tmp_path):
    """The window at its default size with a wide left panel and a right panel of 260 px, on a
    project whose check has to-do lines, warnings and notes with long setting names."""
    folder = tmp_path / "proj"
    templates.create_project(folder, "first-steps", "Wheel link E2E")
    win = make_window(tmp_path)
    qtbot.addWidget(win)
    assert win.open_project(folder)
    win.ctl.run_drc_now()
    win.resize(1360, 860)
    win.go_to("releases")
    panel = show_problems(win)
    win.resizeDocks([win.dock_left, win.dock_right], [426, 260], Qt.Orientation.Horizontal)
    settle()
    return win, panel


def test_the_problem_cards_wrap_to_the_width_of_the_right_panel(narrow_right) -> None:
    win, panel = narrow_right
    body = panel.widget()
    cards = [w for w in body.findChildren(QWidget) if w.property("card")]
    assert cards and body.findChild(QPushButton, "todo-0") is not None  # cards and to-do lines
    assert any(SOFT_BREAK in lab.text() for lab in body.findChildren(QLabel))  # a long name
    room = panel.viewport().width()
    assert body.width() <= room
    assert not panel.horizontalScrollBar().isVisible()
    for w in body.findChildren(QWidget):
        if w.isVisible():
            right = w.mapTo(body, w.rect().topRight()).x()
            assert right < room, f"{w.objectName() or type(w).__name__} reaches past the panel"


def test_the_first_tab_of_the_right_panel_is_not_cut(narrow_right) -> None:
    win, _panel = narrow_right
    bar = win.inspector.tabs.tabBar()
    assert win.inspector.tabs.currentIndex() == 2  # Problems, the tab that scrolled the others
    first, last = bar.tabRect(0), bar.tabRect(bar.count() - 1)
    assert first.left() >= 0 and last.right() < bar.width()
    assert first.width() >= bar.tabSizeHint(0).width()  # "Inspector" whole, not "ector"


def test_a_long_name_gets_soft_breaks_and_short_words_do_not() -> None:
    text = "the margin (derating.connector_temperature_margin_c) is not set: see docs/X.md"
    out = breakable(text)
    assert out.replace(SOFT_BREAK, "") == text
    assert f"derating.{SOFT_BREAK}connector_{SOFT_BREAK}temperature" in out
    assert "docs/X.md" in out  # a short word stays as it is


# ---- the messages over the diagram --------------------------------------------------------------


def toast_buttons_inside(view: QGraphicsView, host: ToastHost) -> None:
    room = view.viewport().width()
    buttons = [b for b in host.findChildren(QPushButton) if b.isVisible()]
    assert {b.objectName() for b in buttons} >= {"toast-undo", "toast-close"}
    for b in buttons:
        left = b.mapTo(view, b.rect().topLeft()).x()
        right = b.mapTo(view, b.rect().topRight()).x()
        assert left >= 0 and right < room, f"{b.objectName()} is cut off ({right} >= {room})"
        assert b.width() >= b.minimumSizeHint().width()
    for label in host.findChildren(QLabel, "toast-text"):
        assert label.height() >= label.heightForWidth(label.width())  # the text is not cut


def test_a_message_is_never_wider_than_a_narrow_diagram(qtbot) -> None:
    view = QGraphicsView()
    qtbot.addWidget(view)
    view.resize(320, 400)  # the text used to be at least 240 px wide, whatever the room
    view.show()
    host = ToastHost(view)
    host.show_message(LONG_MESSAGE, lambda: None, 0)
    settle()
    toast_buttons_inside(view, host)


def test_a_message_follows_the_diagram_when_a_side_panel_makes_it_narrow(qtbot) -> None:
    view = QGraphicsView()
    qtbot.addWidget(view)
    view.resize(900, 400)
    view.show()
    host = ToastHost(view)
    host.show_message(LONG_MESSAGE, lambda: None, 0)
    host.show_message("Enter a number in the unit shown, for example 2.5.", None, 0)
    settle()
    view.resize(QSize(420, 400))  # the left panel is dragged wider
    settle()
    toast_buttons_inside(view, host)


# ---- the hint of the Connect tool --------------------------------------------------------------


def test_the_connect_hint_is_never_cut_in_its_slot(qtbot, tmp_path) -> None:
    folder = tmp_path / "proj"
    templates.create_project(folder, "first-steps", "Wheel link E2E")
    win = make_window(tmp_path)
    qtbot.addWidget(win)
    assert win.open_project(folder)
    win.resize(1360, 860)
    win.go_to("diagram")
    win.dock_left.show()
    win.dock_right.show()
    win.resizeDocks([win.dock_left, win.dock_right], [280, 310], Qt.Orientation.Horizontal)
    win.ctl.begin_connect("power_primary")
    settle()
    hint = win.hint
    assert "Primary power" in hint.text()
    assert hint.height() >= hint.heightForWidth(hint.width())  # every line of it shows
