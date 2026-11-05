# mypy: disable-error-code="no-untyped-def,no-untyped-call,attr-defined,union-attr,arg-type"
"""REQ-GUI-13. Workshop feedback: a label on a line (the pill of an interface, the label of a
connection) can be dragged, because it sometimes hides what the person wants to read next to it.
Where it was put is remembered as a `DiagramMark` in `diagram/marks.json`, an offset from the
automatic place (so it follows its line when devices move); it is not in the model hash, and
"Reset label position" puts it back."""

import json

import pytest

pytest.importorskip("PySide6")
pytestmark = pytest.mark.gui

from PySide6.QtCore import QPoint, QPointF, Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from harness_design_studio.core import routing  # noqa: E402
from harness_design_studio.core.io import layout  # noqa: E402
from harness_design_studio.core.io.loader import load_project  # noqa: E402
from harness_design_studio.core.io.saver import save_project  # noqa: E402
from harness_design_studio.core.samples import mini3, sat15  # noqa: E402
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
        return next(a for a in menu.actions() if a.text().startswith(strings.CM_RESET_LINE))

    assert not entry().isEnabled() and strings.CM_RESET_LINE_NONE in entry().text()
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


# ---- the route of an interface -------------------------------------------------------------------
ROUTE = f"route:{IF}"


def piece(item):
    """The middle of the movable vertical piece of the route, in scene units."""
    i = routing.trunk_index(item.poly)
    assert i is not None
    (x, y0), (_, y1) = item.poly[i], item.poly[i + 1]
    return QPointF(x, (y0 + y1) / 2)


def test_the_vertical_piece_of_an_interface_route_can_be_dragged_sideways(win) -> None:
    item = win.view.dscene.link_items[IF]
    x0 = piece(item).x()
    h0, depth = layout.model_hash(win.ctl.project), undo_depth(win)
    drag(win, piece(item), QPoint(14, 25))
    mark = win.ctl.project.diagram_marks[ROUTE]
    assert mark.dx != 0 and mark.dy == 0  # across only
    assert piece(item).x() == pytest.approx(x0 + mark.dx)
    assert item.auto_route[1][0] == x0  # (the router's own route is where it was)
    assert undo_depth(win) == depth + 1 and layout.model_hash(win.ctl.project) == h0
    assert not win.ctl.is_selected("interface", "IF-PWR-RW1")
    win.act_undo.trigger()  # one step
    assert ROUTE not in win.ctl.project.diagram_marks and piece(item).x() == pytest.approx(x0)
    win.act_redo.trigger()
    assert piece(item).x() == pytest.approx(x0 + mark.dx)


def assert_clear_of_devices(win, item) -> None:
    """Every piece is level or plumb, and none of them runs through the box of a device."""
    boxes = win.view.dscene.unit_boxes()
    for (xa, ya), (xb, yb) in zip(item.poly, item.poly[1:], strict=False):
        assert xa == xb or ya == yb
        for left, top, right, bottom in boxes:
            inside_x = min(xa, xb) < right and max(xa, xb) > left
            inside_y = min(ya, yb) < bottom and max(ya, yb) > top
            assert not (inside_x and inside_y), (item.interface_id, item.poly, (left, top))


def test_a_route_that_was_dragged_never_enters_a_device(win) -> None:
    item = win.view.dscene.link_items[IF]
    boxes = win.view.dscene.unit_boxes()
    for far in (-9000.0, 9000.0):
        win.ctl.move_mark(ROUTE, far, 0.0)
        QApplication.processEvents()
        win.view.grab()
        assert_clear_of_devices(win, item)
    # a drag with the pointer far past a device stops short of it
    win.ctl.reset_mark(ROUTE)
    QApplication.processEvents()
    win.view.grab()
    start = piece(item)
    drag(win, start, QPoint(3000, 0), steps=6)
    left_edge = max(b[2] for b in boxes if b[2] <= start.x())
    right_edge = min(b[0] for b in boxes if b[0] >= start.x())
    assert left_edge < piece(item).x() < right_edge
    assert_clear_of_devices(win, item)


def test_every_route_of_a_busy_diagram_stays_clear_of_the_devices_when_pushed_far(
    qtbot, tmp_path
) -> None:
    w = make_window(tmp_path)
    qtbot.addWidget(w)
    w.ctl._install(sat15(), None, None)
    w.view.fit()
    QApplication.processEvents()
    w.view.grab()
    items = {iid: it for iid, it in w.view.dscene.link_items.items() if it.poly}
    assert len(items) > 10
    for far in (-7000.0, 7000.0):
        for iid in items:
            w.ctl.move_mark(f"route:{iid}", far, 0.0)
        QApplication.processEvents()
        w.view.grab()
        for item in items.values():
            assert_clear_of_devices(w, item)
    assert all(m.dy == 0 for m in w.ctl.project.diagram_marks.values())


def test_the_moved_route_follows_when_a_device_moves_and_stays_clear_of_it(win) -> None:
    item = win.view.dscene.link_items[IF]
    win.ctl.move_mark(ROUTE, 30.0, 0.0)
    shift = QPointF(item.shift_of(ROUTE))
    win.ctl.move_unit("RW1", 520.0, 330.0)
    QApplication.processEvents()
    win.view.grab()
    assert win.ctl.project.diagram_marks[ROUTE].dx == shift.x()  # (the offset is kept)
    x = piece(item).x()
    assert x == pytest.approx(item.auto_route[routing.trunk_index(item.auto_route)][0] + 30.0)
    assert all(not (b[0] < x < b[2]) for b in win.view.dscene.unit_boxes() if b[1] < 400 < b[3])


def test_the_route_is_remembered_after_reopening_and_the_menu_resets_it(win, tmp_path) -> None:
    folder = tmp_path / "proj"
    item = win.view.dscene.link_items[IF]
    drag(win, piece(item), QPoint(10, 0))
    mark = win.ctl.project.diagram_marks[ROUTE]
    save_project(win.ctl.project, folder)
    doc = json.loads((folder / "diagram" / "marks.json").read_text())
    assert [m["id"] for m in doc["marks"]] == [ROUTE]
    again = load_project(folder).project
    assert again.diagram_marks == {ROUTE: mark}
    assert layout.model_hash(again) == layout.model_hash(win.ctl.project)
    win.ctl._install(again, None, None)
    win.view.fit()
    QApplication.processEvents()
    win.view.grab()
    item = win.view.dscene.link_items[IF]
    assert item.shift_of(ROUTE) == QPointF(mark.dx, mark.dy)
    assert piece(item).x() == pytest.approx(item.auto_route[1][0] + mark.dx)
    menu = win.view.build_context_menu("interface", IF, QPointF(0, 0))
    entry = next(a for a in menu.actions() if a.text().startswith(strings.CM_RESET_LINE))
    assert entry.isEnabled()
    entry.trigger()
    assert not win.ctl.project.diagram_marks and piece(item).x() == pytest.approx(
        item.auto_route[1][0]
    )
    win.act_undo.trigger()
    assert ROUTE in win.ctl.project.diagram_marks


def test_label_and_route_of_an_interface_are_both_reset_by_one_menu_entry(win) -> None:
    item = win.view.dscene.link_items[IF]
    drag(win, QPointF(item._chip.center()), QPoint(20, -30))
    drag(win, piece(item), QPoint(12, 0))
    assert {f"interface:{IF}", ROUTE} <= set(win.ctl.project.diagram_marks)
    menu = win.view.build_context_menu("interface", IF, QPointF(0, 0))
    next(a for a in menu.actions() if a.text().startswith(strings.CM_RESET_LINE)).trigger()
    assert not win.ctl.project.diagram_marks
    win.act_undo.trigger()  # one step brings both back
    assert {f"interface:{IF}", ROUTE} <= set(win.ctl.project.diagram_marks)


def test_deleting_an_interface_forgets_its_marks_when_saved_and_undo_brings_them_back(
    win, tmp_path
) -> None:
    item = win.view.dscene.link_items[IF]
    drag(win, piece(item), QPoint(12, 0))
    mark = win.ctl.project.diagram_marks[ROUTE]
    win.ctl.select("interface", IF)
    assert win.ctl.delete_selected()
    assert IF not in win.ctl.project.interfaces
    save_project(win.ctl.project, tmp_path / "p")
    assert not (tmp_path / "p" / "diagram" / "marks.json").exists()
    win.act_undo.trigger()
    assert win.ctl.project.interfaces[IF] and win.ctl.project.diagram_marks[ROUTE] == mark
    save_project(win.ctl.project, tmp_path / "p")
    assert (tmp_path / "p" / "diagram" / "marks.json").exists()


def test_the_connect_tool_and_a_read_only_project_do_not_drag_a_route(win) -> None:
    item = win.view.dscene.link_items[IF]
    at = piece(item)
    win.ctl.begin_link()
    drag(win, at, QPoint(20, 0))
    assert not win.ctl.project.diagram_marks
    win.ctl.end_connect()
    win.ctl.project.read_only = True
    drag(win, at, QPoint(20, 0))
    assert not win.ctl.project.diagram_marks
