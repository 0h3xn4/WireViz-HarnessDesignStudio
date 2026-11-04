# mypy: disable-error-code="no-untyped-def,no-untyped-call,attr-defined,union-attr,arg-type"
"""REQ-GUI-13. Workshop feedback: a label on a line (the pill of an interface, the label of a
connection) can be dragged, because it sometimes hides what the person wants to read next to it.
Where it was put is remembered as a `DiagramMark` in `diagram/marks.json`, an offset from the
automatic place (so it follows its line when devices move); it is not in the model hash, and
"Reset label position" puts it back."""

import pytest

pytest.importorskip("PySide6")
pytestmark = pytest.mark.gui

from PySide6.QtCore import QPoint, QPointF, Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from harness_design_studio.core.io import layout  # noqa: E402
from harness_design_studio.core.io.loader import load_project  # noqa: E402
from harness_design_studio.core.io.saver import save_project  # noqa: E402
from harness_design_studio.core.samples import mini3  # noqa: E402
from harness_design_studio.gui import strings  # noqa: E402
from tests.gui_helpers import make_window  # noqa: E402
from tests.test_ui_links import link_up, window  # noqa: E402

LEFT = Qt.MouseButton.LeftButton
IF = "IF-TM-RW1"


@pytest.fixture
def win(qtbot, tmp_path):
    w = make_window(tmp_path)
    qtbot.addWidget(w)
    w.ctl._install(mini3(), None, None)
    w.view.fit()
    QApplication.processEvents()
    w.view.grab()
    return w


def drag(win, scene_point: QPointF, by: QPoint, *, steps: int = 3) -> None:
    v = win.view
    start = v.mapFromScene(scene_point)
    QTest.mousePress(v.viewport(), LEFT, pos=start)
    for k in range(1, steps + 1):
        QTest.mouseMove(v.viewport(), pos=start + by * k / steps)
    QTest.mouseRelease(v.viewport(), LEFT, pos=start + by)
    QApplication.processEvents()
    v.viewport().repaint()


def undo_depth(win) -> int:
    return len(win.ctl.history._undo)


def test_dragging_the_label_of_an_interface_moves_it_and_one_undo_puts_it_back(win) -> None:
    item = win.view.dscene.link_items[IF]
    home = QPointF(item._chip.center())
    h0, depth = layout.model_hash(win.ctl.project), undo_depth(win)
    drag(win, home, QPoint(50, 40))
    mark = win.ctl.project.diagram_marks[f"interface:{IF}"]
    assert (mark.dx, mark.dy) == (item.shift.x(), item.shift.y()) != (0.0, 0.0)
    win.view.grab()
    moved = item._chip.center() - home
    assert (moved.x(), moved.y()) == pytest.approx((mark.dx, mark.dy))
    assert item._chip_center == home  # the automatic place is where it was
    assert undo_depth(win) == depth + 1
    assert layout.model_hash(win.ctl.project) == h0  # a label is not the design
    win.act_undo.trigger()
    assert f"interface:{IF}" not in win.ctl.project.diagram_marks
    assert item.shift == QPointF(0.0, 0.0)
    win.act_redo.trigger()
    assert item.shift == QPointF(mark.dx, mark.dy)


def test_a_click_on_the_label_still_selects_and_a_small_wobble_is_a_click(win) -> None:
    item = win.view.dscene.link_items[IF]
    home = QPointF(item._chip.center())
    depth = undo_depth(win)
    drag(win, home, QPoint(2, 1))
    assert win.ctl.is_selected("interface", IF)
    assert not win.ctl.project.diagram_marks and undo_depth(win) == depth


def test_dragging_the_line_itself_moves_nothing(win) -> None:
    item = win.view.dscene.link_items[IF]
    spot = next(  # a point of the line away from the label and from the devices
        pt
        for pt in (item.path().pointAtPercent(k / 20) for k in range(3, 18))
        if not item._chip.adjusted(-8, -8, 8, 8).contains(pt)
        and not any(u.sceneBoundingRect().contains(pt) for u in win.view.dscene.unit_items.values())
    )
    drag(win, spot, QPoint(40, 40))
    assert not win.ctl.project.diagram_marks


def test_the_moved_label_follows_its_line_when_a_device_moves(win) -> None:
    item = win.view.dscene.link_items[IF]
    drag(win, QPointF(item._chip.center()), QPoint(0, 45))
    shift = QPointF(item.shift)
    assert shift.y() != 0
    win.ctl.move_unit("RW1", 470.0, 330.0)
    QApplication.processEvents()
    win.view.grab()
    assert item.shift == shift  # the offset is kept, not a point that goes stale
    seen = item._chip.center() - item._chip_center
    assert (seen.x(), seen.y()) == pytest.approx((shift.x(), shift.y()))


def test_reset_label_position_in_the_menu_puts_it_back_and_is_off_when_it_is_there(win) -> None:
    item = win.view.dscene.link_items[IF]

    def entry():
        menu = win.view.build_context_menu("interface", IF, QPointF(0, 0))
        return next(a for a in menu.actions() if a.text().startswith(strings.CM_RESET_LABEL))

    assert not entry().isEnabled() and strings.CM_RESET_LABEL_NONE in entry().text()
    drag(win, QPointF(item._chip.center()), QPoint(30, -30))
    assert entry().isEnabled()
    entry().trigger()
    assert item.shift == QPointF(0.0, 0.0) and not win.ctl.project.diagram_marks
    win.act_undo.trigger()  # the reset is a step of its own
    assert win.ctl.project.diagram_marks


def test_the_label_of_a_connection_moves_the_same_way(tmp_path) -> None:
    win = window(tmp_path)
    assert link_up(win) == "L1"
    win.view.fit()
    win.view.viewport().repaint()
    QApplication.processEvents()
    win.view.grab()
    item = win.view.dscene.connection_items["L1"]
    home = QPointF(item._chip.center())
    h0 = layout.model_hash(win.ctl.project)
    drag(win, home, QPoint(0, 60))
    mark = win.ctl.project.diagram_marks["link:L1"]
    assert mark.dy != 0
    win.view.grab()
    assert item._chip.center().y() == pytest.approx(home.y() + mark.dy)
    assert layout.model_hash(win.ctl.project) == h0
    # a device moves, the label keeps its offset from the line
    win.ctl.move_unit("OBC", 30.0, 400.0)
    QApplication.processEvents()
    win.view.grab()
    assert item.shift == QPointF(mark.dx, mark.dy)
    # the context menu puts it back
    menu = win.view.build_context_menu("link", "L1", QPointF(0, 0))
    next(a for a in menu.actions() if a.text().startswith(strings.CM_RESET_LINE)).trigger()
    assert item.shift == QPointF(0.0, 0.0) and not win.ctl.project.diagram_marks


def test_a_moved_label_is_remembered_after_the_project_is_reopened(win, tmp_path) -> None:
    folder = tmp_path / "proj"
    item = win.view.dscene.link_items[IF]
    drag(win, QPointF(item._chip.center()), QPoint(40, 30))
    mark = win.ctl.project.diagram_marks[f"interface:{IF}"]
    save_project(win.ctl.project, folder)
    assert (folder / "diagram" / "marks.json").exists()
    again = load_project(folder).project
    assert again.diagram_marks == {mark.id: mark}
    assert layout.model_hash(again) == layout.model_hash(win.ctl.project)
    win.ctl._install(again, None, None)
    win.view.fit()
    QApplication.processEvents()
    win.view.grab()
    assert win.view.dscene.link_items[IF].shift == QPointF(mark.dx, mark.dy)


def test_the_connect_tool_and_a_read_only_project_do_not_drag_labels(win) -> None:
    item = win.view.dscene.link_items[IF]
    home = QPointF(item._chip.center())
    win.ctl.begin_link()
    drag(win, home, QPoint(40, 40))
    assert not win.ctl.project.diagram_marks
    win.ctl.end_connect()
    win.ctl.project.read_only = True
    drag(win, home, QPoint(40, 40))
    assert not win.ctl.project.diagram_marks


def connection(tmp_path, *, expert: bool = False):
    win = window(tmp_path)
    assert link_up(win) == "L1"
    if expert:
        win.ctl.set_mode("expert")
    win.view.fit()
    QApplication.processEvents()
    win.view.viewport().repaint()
    win.view.grab()
    return win, win.view.dscene.connection_items["L1"]


def test_the_connector_box_at_an_end_of_a_connection_moves_with_its_line(tmp_path) -> None:
    win, item = connection(tmp_path, expert=True)
    home = QPointF(item._end_rects[1].center())
    drag(win, home, QPoint(0, 40))
    mark = win.ctl.project.diagram_marks["end:L1:1"]
    assert mark.dy != 0 and "end:L1:0" not in win.ctl.project.diagram_marks
    win.view.grab()
    assert item._end_rects[1].center().y() == pytest.approx(home.y() + mark.dy)
    win.ctl.move_unit("RW1", 470.0, 300.0)  # the device moves: the box keeps its offset
    QApplication.processEvents()
    win.view.grab()
    assert item.shift_of("end:L1:1") == QPointF(mark.dx, mark.dy)
    assert item._end_rects[1].center().y() - item.poly[-1][1] == pytest.approx(mark.dy)


def test_the_bend_of_a_connection_moves_across_only_and_never_into_a_device(tmp_path) -> None:
    win, item = connection(tmp_path)
    x0 = item.poly[1][0]
    piece = QPointF(x0, (item.poly[1][1] + item.poly[2][1]) / 2)
    h0 = layout.model_hash(win.ctl.project)
    drag(win, piece, QPoint(25, 20))
    mark = win.ctl.project.diagram_marks["bend:L1"]
    assert mark.dx != 0 and mark.dy == 0  # across only
    assert item.poly[1][0] == pytest.approx(x0 + mark.dx)
    assert layout.model_hash(win.ctl.project) == h0
    win.act_undo.trigger()
    assert item.poly[1][0] == pytest.approx(x0)
    # far to the left: the line stops short of the device it leaves
    win.ctl.move_mark("bend:L1", -5000.0, 0.0)
    xa = item.poly[0][0]
    assert item.poly[1][0] >= xa


def test_a_connection_line_clicked_off_its_pieces_is_not_dragged(tmp_path) -> None:
    win, item = connection(tmp_path)
    drag(win, QPointF(item.poly[0][0] + 5, item.poly[0][1]), QPoint(30, 30))
    assert not win.ctl.project.diagram_marks
