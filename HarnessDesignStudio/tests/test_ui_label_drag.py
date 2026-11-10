# SPDX-FileCopyrightText: 2026 0h3xn4
# SPDX-License-Identifier: GPL-3.0-only
# mypy: disable-error-code="no-untyped-def,no-untyped-call,attr-defined,union-attr,arg-type"
"""REQ-GUI-13. Workshop feedback: a label on a line (the pill of an interface, the label of a
connection, the connector box at its ends) can be dragged, because it sometimes hides what the
person wants to read next to it, but it stays ON its line: it slides along it (the point of the
line nearest to the pointer, however far the pointer is) and goes with it when devices move or the
route is dragged. Where it was put is remembered as a `DiagramMark` in `diagram/marks.json`, a
fraction of the length of the line (an offset of release 1.14 and 1.15 is read as the nearest point
of the line); it is not in the model hash, and "Reset label and line positions" puts it back."""

import json
import math

import pytest

pytest.importorskip("PySide6")
pytestmark = pytest.mark.gui

from PySide6.QtCore import QPoint, QPointF, Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from harness_design_studio.core import linepos, routing  # noqa: E402
from harness_design_studio.core.io import layout  # noqa: E402
from harness_design_studio.core.io.loader import load_project  # noqa: E402
from harness_design_studio.core.io.saver import save_project  # noqa: E402
from harness_design_studio.core.model import DiagramMark  # noqa: E402
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


def on_line(item, point=None, *, eps: float = 0.6) -> bool:
    """Whether a point (default: the centre of the drawn label) lies on the line of the item."""
    point = point if point is not None else item._chip.center()
    return linepos.project(item.poly, (point.x(), point.y()))[2] < eps


def drag_hold(win, scene_point: QPointF, by: QPoint, *, steps: int = 3) -> QPoint:
    """Press and move, without letting go (what is on the screen while the button is down)."""
    v = win.view
    start = v.mapFromScene(scene_point)
    QTest.mousePress(v.viewport(), LEFT, pos=start)
    for k in range(1, steps + 1):
        QTest.mouseMove(v.viewport(), pos=start + by * k / steps)
    QApplication.processEvents()
    v.viewport().repaint()
    end: QPoint = start + by
    return end


def let_go(win, at: QPoint) -> None:
    QTest.mouseRelease(win.view.viewport(), LEFT, pos=at)
    QApplication.processEvents()
    win.view.viewport().repaint()


def test_dragging_the_pill_of_an_interface_slides_it_along_its_line_and_one_undo_puts_it_back(
    win,
) -> None:
    item = win.view.dscene.link_items[IF]
    home = QPointF(item._chip.center())
    h0, depth = layout.model_hash(win.ctl.project), undo_depth(win)
    cursor = home + QPointF(30.0, -90.0)  # the pointer goes far above the line
    drag(win, home, win.view.mapFromScene(cursor) - win.view.mapFromScene(home))
    mark = win.ctl.project.diagram_marks[f"interface:{IF}"]
    assert mark.t is not None and mark.dx is None and mark.dy is None  # a place on the line
    assert item.along_of(f"interface:{IF}") == mark.t
    win.view.grab()
    assert on_line(item)  # it never left the line
    # it is at the point of the line that is nearest to the pointer
    nearest = linepos.project(item.poly, (cursor.x(), cursor.y()))[1]
    assert (item._chip.center() - QPointF(*nearest)).manhattanLength() < 1.5
    assert item._chip_center == home  # the automatic place is where it was
    assert undo_depth(win) == depth + 1
    assert layout.model_hash(win.ctl.project) == h0  # a label is not the design
    assert win.ctl.is_selected("interface", IF)  # (a pill stays selectable)
    win.act_undo.trigger()
    assert f"interface:{IF}" not in win.ctl.project.diagram_marks
    assert item.along_of(f"interface:{IF}") is None
    win.view.grab()
    assert item._chip.center() == home
    win.act_redo.trigger()
    assert item.along_of(f"interface:{IF}") == mark.t


def test_the_pill_is_on_the_line_all_the_time_it_is_dragged_and_nothing_floats(win) -> None:
    item = win.view.dscene.link_items[IF]
    home = QPointF(item._chip.center())
    depth = undo_depth(win)
    end = drag_hold(win, home, QPoint(70, -120), steps=5)  # the button stays down
    assert on_line(item)  # (while it is dragged, not only when it is let go)
    assert not win.ctl.project.diagram_marks and undo_depth(win) == depth  # (nothing written yet)
    assert QApplication.overrideCursor() is not None
    assert QApplication.overrideCursor().shape() in (
        Qt.CursorShape.SizeHorCursor,
        Qt.CursorShape.SizeVerCursor,
        Qt.CursorShape.SizeAllCursor,
    )
    let_go(win, end)
    assert QApplication.overrideCursor() is None  # (the cursor is given back)
    assert on_line(item) and undo_depth(win) == depth + 1


def test_a_pill_dragged_far_in_every_direction_stays_on_the_line_and_inside_it(win) -> None:
    item = win.view.dscene.link_items[IF]
    spans = (
        (-4000, -4000), (4000, 4000), (-4000, 4000), (4000, -4000),
        (0, 900), (0, -900), (900, 0), (-900, 0), (35, 22),
    )  # fmt: skip
    for dx, dy in spans:
        win.view.fit()
        QApplication.processEvents()
        win.view.grab()
        drag(win, QPointF(item._chip.center()), QPoint(dx, dy), steps=4)
        win.view.grab()
        assert on_line(item), (dx, dy)
        t = item.along_of(f"interface:{IF}")
        assert t is not None and 0.0 <= t <= 1.0
        centre = item._chip.center()
        near_end = min(
            math.hypot(centre.x() - x, centre.y() - y) for x, y in (item.poly[0], item.poly[-1])
        )
        assert near_end >= item.margin_of(f"interface:{IF}") - 0.5  # (not into a device's edge)


def test_a_pill_dragged_round_a_corner_follows_the_corner(win) -> None:
    item = win.view.dscene.link_items[IF]
    (xa, ya), (xb, yb) = item.poly[1], item.poly[2]  # the vertical piece of the route
    assert xa == xb
    first = QPointF(item._chip.center())
    # the pointer is out to the right of the vertical piece: the pill is on that piece
    beside = QPointF(xa + 20, ya + 60)
    drag(win, first, win.view.mapFromScene(beside) - win.view.mapFromScene(first))
    win.view.grab()
    assert item._chip.center().x() == pytest.approx(xa, abs=0.2)
    assert ya <= item._chip.center().y() <= yb and on_line(item)
    # and on, far to the right and below: it went round the corner onto the last level piece
    low = QPointF(item._chip.center())
    to = QPointF(xa + 300, yb + 40)
    drag(win, low, win.view.mapFromScene(to) - win.view.mapFromScene(low))
    win.view.grab()
    assert on_line(item)
    assert item._chip.center().y() == pytest.approx(yb, abs=0.2)
    assert item._chip.center().x() > xa


def test_a_click_on_the_label_still_selects_and_a_small_wobble_is_a_click(win) -> None:
    item = win.view.dscene.link_items[IF]
    home = QPointF(item._chip.center())
    depth = undo_depth(win)
    drag(win, home, QPoint(2, 1))
    assert win.ctl.is_selected("interface", IF)
    assert not win.ctl.project.diagram_marks and undo_depth(win) == depth


def test_a_drag_that_ends_where_it_began_is_no_step(win) -> None:
    item = win.view.dscene.link_items[IF]
    home = QPointF(item._chip.center())
    depth = undo_depth(win)
    v = win.view
    start = v.mapFromScene(home)
    QTest.mousePress(v.viewport(), LEFT, pos=start)
    QTest.mouseMove(v.viewport(), pos=start + QPoint(30, -40))
    QTest.mouseMove(v.viewport(), pos=start)
    QTest.mouseRelease(v.viewport(), LEFT, pos=start)
    QApplication.processEvents()
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


def test_the_moved_pill_stays_attached_when_a_device_moves(win) -> None:
    item = win.view.dscene.link_items[IF]
    drag(win, QPointF(item._chip.center()), QPoint(60, -45))
    key = f"interface:{IF}"
    t = win.ctl.project.diagram_marks[key].t
    before = QPointF(item._chip.center())
    win.ctl.move_unit("RW1", 470.0, 330.0)
    QApplication.processEvents()
    win.view.grab()
    assert win.ctl.project.diagram_marks[key].t == t  # (the place along the line is kept)
    assert item.along_of(key) == t
    assert on_line(item)  # still on its line, which has changed
    assert item._chip.center() != before  # (and went with it)
    margin = item.margin_of(key)
    expect = linepos.place(item.poly, t, margin)
    assert (item._chip.center() - QPointF(*expect)).manhattanLength() < 0.5
    # the other device too, and back again with the undo
    win.ctl.move_unit("OBC", 30.0, 400.0)
    QApplication.processEvents()
    win.view.grab()
    assert on_line(item)
    win.act_undo.trigger()
    win.act_undo.trigger()
    win.view.grab()
    assert on_line(item) and (item._chip.center() - before).manhattanLength() < 0.5


def test_a_line_that_gets_much_shorter_keeps_the_pill_on_it_and_inside_it(win) -> None:
    item = win.view.dscene.link_items[IF]
    key = f"interface:{IF}"
    win.ctl.slide_mark(key, 0.97)  # right at the far end
    win.view.grab()
    far = QPointF(item._chip.center())
    assert on_line(item)
    win.ctl.move_unit("RW1", 330.0, 120.0)  # the devices come close: the line is short
    QApplication.processEvents()
    win.view.grab()
    assert win.ctl.project.diagram_marks[key].t == 0.97  # (the stored place is not spoilt)
    assert on_line(item)
    box = win.view.dscene.unit_items["RW1"].sceneBoundingRect()
    assert not box.contains(item._chip.center())
    win.ctl.move_unit("RW1", 470.0, 330.0)  # and long again: the place comes back
    QApplication.processEvents()
    win.view.grab()
    assert on_line(item) and item.along_of(key) == 0.97
    assert (
        item._chip.center() - far
    ).manhattanLength() > 1.0  # (a different line, so a different point)


def test_a_moved_pill_is_not_pushed_aside_by_the_tool_and_an_unmoved_one_still_is(win) -> None:
    sc = win.view.dscene
    item = sc.link_items[IF]
    other = sc.link_items["IF-PWR-RW1"]
    assert other.poly and other.along_of(other.mark_ids[0]) is None
    key = f"interface:{IF}"
    other_centre = QPointF(other._chip_center)
    # put the pill of IF on the other pill's place as near as its line allows
    win.ctl.slide_mark(key, linepos.project(item.poly, (other_centre.x(), other_centre.y()))[0])
    win.ctl.move_unit("RW1", 470.0, 345.0)  # everything is placed again
    QApplication.processEvents()
    win.view.grab()
    t = item.along_of(key)
    assert (
        item._chip.center() - QPointF(*linepos.place(item.poly, t, item.margin_of(key)))
    ).manhattanLength() < 0.5  # exactly where the person put it, overlap or not
    assert win.ctl.project.diagram_marks[key].t == t


def test_a_pill_stays_on_its_line_when_the_route_is_dragged(win) -> None:
    item = win.view.dscene.link_items[IF]
    key = f"interface:{IF}"
    win.ctl.slide_mark(key, 0.6)
    win.view.grab()
    t = item.along_of(key)
    x0 = item.poly[1][0]
    win.ctl.move_mark(ROUTE, 22.0, 0.0)  # the vertical piece moves across
    QApplication.processEvents()
    win.view.grab()
    assert item.poly[1][0] == pytest.approx(x0 + 22.0)
    assert item.along_of(key) == t and on_line(item)
    expect = linepos.place(item.poly, t, item.margin_of(key))
    assert (item._chip.center() - QPointF(*expect)).manhattanLength() < 0.5


def test_the_cursor_over_a_pill_says_which_way_it_slides(win) -> None:
    item = win.view.dscene.link_items[IF]
    key = f"interface:{IF}"
    centre = QPointF(item._chip.center())
    assert item.hover_cursor(centre) == Qt.CursorShape.SizeHorCursor  # (a level piece)
    assert item.hover_cursor(centre + QPointF(0, 300)) is None  # (not over the pill)
    first_piece = linepos.length(item.poly[:2])  # the pill goes 40 down the plumb piece
    win.ctl.slide_mark(key, (first_piece + 40.0) / linepos.length(item.poly))
    win.view.grab()
    mid = QPointF(item._chip.center())
    assert mid.x() == pytest.approx(item.poly[1][0], abs=0.2)
    assert item.hover_cursor(mid) == Qt.CursorShape.SizeVerCursor  # (the plumb piece)
    win.ctl.begin_link()  # Connect is the tool: nothing can be dragged
    assert item.hover_cursor(mid) is None
    win.ctl.end_connect()
    win.ctl.project.read_only = True
    assert item.hover_cursor(mid) is None


def test_reset_label_position_in_the_menu_puts_it_back_and_is_off_when_it_is_there(win) -> None:
    item = win.view.dscene.link_items[IF]

    def entry():
        menu = win.view.build_context_menu("interface", IF, QPointF(0, 0))
        return next(a for a in menu.actions() if a.text().startswith(strings.CM_RESET_LINE))

    home = QPointF(item._chip.center())
    assert not entry().isEnabled() and strings.CM_RESET_LINE_NONE in entry().text()
    drag(win, home, QPoint(30, -30))
    win.view.grab()
    assert entry().isEnabled() and item._chip.center() != home
    entry().trigger()
    win.view.grab()
    assert item.along_of(f"interface:{IF}") is None and not win.ctl.project.diagram_marks
    assert item._chip.center() == home  # (the place the tool gave it)
    win.act_undo.trigger()  # the reset is a step of its own
    assert win.ctl.project.diagram_marks


def test_the_label_of_a_connection_slides_along_its_line_the_same_way(tmp_path) -> None:
    win = window(tmp_path)
    assert link_up(win) == "L1"
    win.view.fit()
    win.view.viewport().repaint()
    QApplication.processEvents()
    win.view.grab()
    item = win.view.dscene.connection_items["L1"]
    home = QPointF(item._chip.center())
    h0, depth = layout.model_hash(win.ctl.project), undo_depth(win)
    cursor = home + QPointF(0.0, 140.0)  # far below the line
    drag(win, home, win.view.mapFromScene(cursor) - win.view.mapFromScene(home))
    mark = win.ctl.project.diagram_marks["link:L1"]
    assert mark.t is not None and mark.dx is None
    win.view.grab()
    assert on_line(item)
    assert undo_depth(win) == depth + 1 and layout.model_hash(win.ctl.project) == h0
    # a device moves: the label stays on the line, at the same place along it
    win.ctl.move_unit("OBC", 30.0, 400.0)
    QApplication.processEvents()
    win.view.grab()
    assert win.ctl.project.diagram_marks["link:L1"].t == mark.t
    assert on_line(item)
    expect = linepos.place(item.poly, mark.t, item.margin_of("link:L1"))
    assert (item._chip.center() - QPointF(*expect)).manhattanLength() < 0.5
    # the context menu puts it back
    menu = win.view.build_context_menu("link", "L1", QPointF(0, 0))
    next(a for a in menu.actions() if a.text().startswith(strings.CM_RESET_LINE)).trigger()
    assert item.along_of("link:L1") is None and not win.ctl.project.diagram_marks


def test_a_moved_pill_is_remembered_after_the_project_is_reopened(win, tmp_path) -> None:
    folder = tmp_path / "proj"
    item = win.view.dscene.link_items[IF]
    drag(win, QPointF(item._chip.center()), QPoint(40, 30))
    mark = win.ctl.project.diagram_marks[f"interface:{IF}"]
    save_project(win.ctl.project, folder)
    doc = json.loads((folder / "diagram" / "marks.json").read_text())
    assert doc == {"marks": [{"id": f"interface:{IF}", "t": mark.t}]}
    again = load_project(folder).project
    assert again.diagram_marks == {mark.id: mark}
    assert layout.model_hash(again) == layout.model_hash(win.ctl.project)
    win.ctl._install(again, None, None)
    win.view.fit()
    QApplication.processEvents()
    win.view.grab()
    shown = win.view.dscene.link_items[IF]
    assert shown.along_of(f"interface:{IF}") == mark.t and on_line(shown)


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


# ---- a mark of release 1.14 and 1.15: a free offset of the label --------------------------------
def reopened_with(win, tmp_path, marks):
    """The project, saved with `marks` in `diagram/marks.json` by an earlier tool, opened again."""
    folder = tmp_path / "old"
    save_project(win.ctl.project, folder)
    (folder / "diagram").mkdir(exist_ok=True)
    (folder / "diagram" / "marks.json").write_text(json.dumps({"marks": marks}))
    again = load_project(folder).project
    win.ctl._install(again, None, None)
    win.view.fit()
    QApplication.processEvents()
    win.view.grab()
    return folder


def test_an_offset_of_an_earlier_version_is_read_as_the_nearest_point_of_the_line(
    win, tmp_path
) -> None:
    key = f"interface:{IF}"
    h0 = layout.model_hash(win.ctl.project)
    item = win.view.dscene.link_items[IF]
    auto = QPointF(item._chip_center)
    folder = reopened_with(
        win, tmp_path, [{"dx": 40.0, "dy": -60.0, "id": key}, {"dx": 9.0, "dy": 0.0, "id": ROUTE}]
    )
    sc = win.view.dscene
    item = sc.link_items[IF]
    assert item.poly[1][0] == pytest.approx(item.auto_route[1][0] + 9.0)  # (the route is as it was)
    mark = win.ctl.project.diagram_marks[key]
    assert mark.t is not None and mark.dx is None and mark.dy is None  # now a place on the line
    expect = linepos.from_offset(item.auto_route, (auto.x(), auto.y()), 40.0, -60.0)
    assert on_line(item) and item._chip.center() != auto
    assert mark.t == pytest.approx(expect, abs=0.05)  # (the route moved a little: near enough)
    nearest = linepos.project(item.poly, (auto.x() + 40.0, auto.y() - 60.0))[1]
    assert (item._chip.center() - QPointF(*nearest)).manhattanLength() < 12.0
    assert win.ctl.project.diagram_marks[ROUTE].dx == 9.0  # (a route is still an offset)
    assert layout.model_hash(win.ctl.project) == h0
    assert undo_depth(win) == 0  # (nothing the person did: no step)
    # written in the new form on the next save, the route as it was
    save_project(win.ctl.project, folder)
    doc = json.loads((folder / "diagram" / "marks.json").read_text())
    assert doc["marks"] == [
        {"id": key, "t": mark.t},
        {"dx": 9.0, "dy": 0.0, "id": ROUTE},
    ]
    assert load_project(folder).project.diagram_marks == win.ctl.project.diagram_marks


def test_an_offset_of_an_earlier_version_for_a_far_away_label_ends_at_the_line_end(
    win, tmp_path
) -> None:
    key = f"interface:{IF}"
    reopened_with(win, tmp_path, [{"dx": 99000.0, "dy": 99000.0, "id": key}])
    item = win.view.dscene.link_items[IF]
    assert win.ctl.project.diagram_marks[key].t == 1.0
    assert on_line(item)


def test_the_offsets_of_the_connection_label_and_boxes_of_an_earlier_version_are_read_too(
    tmp_path,
) -> None:
    win = window(tmp_path)
    assert link_up(win) == "L1"
    win.ctl.set_mode("expert")
    win.view.fit()
    QApplication.processEvents()
    win.view.grab()
    item = win.view.dscene.connection_items["L1"]
    label_auto = QPointF(item._chip.center())
    end_auto = QPointF(item._end_rects[1].center())
    folder = tmp_path / "old"
    save_project(win.ctl.project, folder)
    (folder / "diagram").mkdir(exist_ok=True)
    marks = [
        {"dx": 25.0, "dy": 50.0, "id": "link:L1"},
        {"dx": -60.0, "dy": 30.0, "id": "end:L1:1"},
        {"dx": 7.0, "dy": 0.0, "id": "bend:L1"},
    ]
    (folder / "diagram" / "marks.json").write_text(json.dumps({"marks": marks}))
    win.ctl._install(load_project(folder).project, None, None)
    win.view.fit()
    QApplication.processEvents()
    win.view.grab()
    item = win.view.dscene.connection_items["L1"]
    got = win.ctl.project.diagram_marks
    assert got["link:L1"].t is not None and got["link:L1"].dx is None
    assert got["end:L1:1"].t is not None and got["end:L1:1"].dx is None
    assert got["bend:L1"].dx == 7.0 and got["bend:L1"].t is None
    assert on_line(item) and on_line(item, item._end_rects[1].center())
    assert item._chip.center() != label_auto and item._end_rects[1].center() != end_auto
    assert undo_depth(win) == 0


def test_an_offset_of_an_earlier_version_waits_while_the_line_is_not_drawn(win, tmp_path) -> None:
    """No line, no nearest point: the mark stays as it is (and is written back as it was)."""
    key = f"interface:{IF}"
    item = win.view.dscene.link_items[IF]
    assert item.legacy_places() == {}  # (nothing is old now)
    reopened_with(win, tmp_path, [{"dx": 40.0, "dy": -60.0, "id": key}])
    item = win.view.dscene.link_items[IF]
    item.poly = []
    win.ctl.project.diagram_marks[key] = DiagramMark(id=key, dx=1.0, dy=1.0)
    assert item.legacy_places() == {}


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


def test_the_connector_box_at_an_end_of_a_connection_slides_along_its_line(tmp_path) -> None:
    win, item = connection(tmp_path, expert=True)
    home = QPointF(item._end_rects[1].center())
    h0 = layout.model_hash(win.ctl.project)
    cursor = home + QPointF(-70.0, 60.0)  # far off the line, towards the other end
    drag(win, home, win.view.mapFromScene(cursor) - win.view.mapFromScene(home))
    mark = win.ctl.project.diagram_marks["end:L1:1"]
    assert (
        mark.t is not None and mark.dx is None and "end:L1:0" not in win.ctl.project.diagram_marks
    )
    win.view.grab()
    assert on_line(item, item._end_rects[1].center())
    assert item._end_rects[1].center() != home
    assert layout.model_hash(win.ctl.project) == h0
    # the device moves: the box goes with the line, at the same place along it
    win.ctl.move_unit("RW1", 470.0, 300.0)
    QApplication.processEvents()
    win.view.grab()
    assert item.along_of("end:L1:1") == mark.t
    assert on_line(item, item._end_rects[1].center())
    expect = linepos.place(item.poly, mark.t, item.margin_of("end:L1:1"))
    assert (item._end_rects[1].center() - QPointF(*expect)).manhattanLength() < 0.5
    # the other end box is where the tool puts it, and the label too
    assert item._end_rects[0].center() == item._auto["end:L1:0"].center()


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


def test_deleting_an_interface_forgets_the_place_of_its_pill_when_saved_and_undo_brings_it_back(
    win, tmp_path
) -> None:
    key = f"interface:{IF}"
    win.ctl.slide_mark(key, 0.7)
    win.ctl.select("interface", IF)
    assert win.ctl.delete_selected()
    save_project(win.ctl.project, tmp_path / "p")
    assert not (tmp_path / "p" / "diagram" / "marks.json").exists()
    win.act_undo.trigger()
    assert win.ctl.project.diagram_marks[key].t == 0.7  # (the place waited in memory)
    win.view.grab()
    assert on_line(win.view.dscene.link_items[IF])
    save_project(win.ctl.project, tmp_path / "p")
    doc = json.loads((tmp_path / "p" / "diagram" / "marks.json").read_text())
    assert doc == {"marks": [{"id": key, "t": 0.7}]}
