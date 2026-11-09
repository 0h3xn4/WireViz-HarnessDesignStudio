# SPDX-FileCopyrightText: 2026 0h3xn4
# SPDX-License-Identifier: GPL-3.0-only
# mypy: disable-error-code="no-untyped-def,no-untyped-call,attr-defined,union-attr,arg-type,type-arg,assignment,index"
"""REQ-GUI-22. Owner feedback: "fixing the panel size is annoying, because I can't move around
devices as I wish, they are basically trapped." What trapped them was a clamp of every position to
zero (the drag, Shift+arrow, Add here, align) and a scene that did not grow, and scroll, while a
device or cable was carried past the edge. Now a device goes anywhere, past the old edge and below
zero, the scene grows and the view follows, nothing snaps back, one move is one undo step, the
positions are written and read exactly as before, Fit still shows everything, and the exported and
written block diagrams frame every device."""

import pytest

pytest.importorskip("PySide6")
pytestmark = pytest.mark.gui

from PySide6.QtCore import QPoint, QPointF, QRectF, Qt  # noqa: E402
from PySide6.QtGui import QWheelEvent  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from harness_design_studio.core import edit  # noqa: E402
from harness_design_studio.core.io import layout  # noqa: E402
from harness_design_studio.core.io.saver import save_project  # noqa: E402
from harness_design_studio.core.outputs.canvas import item_bounds  # noqa: E402
from harness_design_studio.gui import diagram_export  # noqa: E402
from tests.test_ui_tactile_connect import World  # noqa: E402

LEFT = Qt.MouseButton.LeftButton


def world(tmp_path, *, snap: bool = False, scroll: bool = False) -> World:
    w = World(tmp_path, quick=False, mode="expert", scroll=scroll)
    w.view.set_snap(snap)
    return w


def header(w: World, uid: str) -> QPointF:
    p = w.scene.unit_items[uid].pos()
    return QPointF(p.x() + 100, p.y() + 14)


def pos(w: World, uid: str) -> tuple[float, float]:
    return edit.position_of(w.project, uid)


def test_a_device_dragged_past_the_top_left_corner_stays_below_zero(qtbot, tmp_path) -> None:
    w = world(tmp_path)
    start = header(w, "OBC")
    w.drag(start, start + QPointF(-300, -200))
    assert pos(w, "OBC") == (60.0 - 300, 70.0 - 200) == (-240.0, -130.0)
    assert w.scene.unit_items["OBC"].pos() == QPointF(-240, -130)  # the item agrees with the model


def test_a_device_dragged_far_to_the_right_and_down_stays_where_it_was_dropped(
    qtbot, tmp_path
) -> None:
    w = world(tmp_path)
    start = header(w, "RW1")
    w.drag(start, start + QPointF(900, 700))
    assert pos(w, "RW1") == (520.0 + 900, 190.0 + 700)


def test_nothing_snaps_back_when_the_event_loop_runs_on(qtbot, tmp_path) -> None:
    w = world(tmp_path)
    start = header(w, "OBC")
    w.drag(start, start + QPointF(-500, -300))
    for _ in range(5):
        QTest.qWait(30)
    w.settle()
    assert pos(w, "OBC") == (-440.0, -230.0) and w.scene.unit_items["OBC"].pos() == QPointF(
        -440, -230
    )
    w.win.ctl.undo()
    assert pos(w, "OBC") == (60.0, 70.0)
    w.win.ctl.redo()
    assert w.scene.unit_items["OBC"].pos() == QPointF(-440, -230)


def test_the_scene_grows_to_hold_a_device_dragged_beyond_it_and_the_view_can_scroll_there(
    qtbot, tmp_path
) -> None:
    w = world(tmp_path)
    old = QRectF(w.scene.sceneRect())
    start = header(w, "RW1")
    w.press(start)
    for k in range(1, 9):
        w.move(start + QPointF(260 * k, 0))
        assert w.scene.sceneRect().contains(w.scene.unit_items["RW1"].sceneBoundingRect())
    w.release(start + QPointF(260 * 8, 0))
    rect = w.scene.sceneRect()
    assert rect.right() > old.right() + 1000 and rect.contains(
        w.scene.unit_items["RW1"].sceneBoundingRect()
    )
    w.view.horizontalScrollBar().setValue(w.view.horizontalScrollBar().maximum())
    assert (
        w.view.mapToScene(w.view.viewport().rect().bottomRight()).x() >= 520 + 2080
    )  # the view reaches it


def test_the_scene_grows_to_the_left_and_up_too(qtbot, tmp_path) -> None:
    w = world(tmp_path)
    start = header(w, "OBC")
    w.drag(start, start + QPointF(-900, -600))
    rect = w.scene.sceneRect()
    assert rect.left() <= -840 and rect.top() <= -530
    assert (
        w.view.horizontalScrollBar().minimum() <= -840
        and w.view.verticalScrollBar().minimum() <= -530
    )


def test_one_move_past_the_edge_is_one_undo_step(qtbot, tmp_path) -> None:
    w = world(tmp_path)
    start = header(w, "PCDU")
    w.drag(start, start + QPointF(-700, 900))
    assert w.steps() == 1
    w.win.ctl.undo()
    assert pos(w, "PCDU") == (60.0, 330.0) and w.steps() == 0


def test_a_selection_moved_together_keeps_its_shape_past_the_edge(qtbot, tmp_path) -> None:
    w = world(tmp_path)
    w.win.ctl.select_many([("unit", "OBC"), ("unit", "PCDU")])
    start = header(w, "OBC")
    w.drag(start, start + QPointF(-200, -100))
    assert pos(w, "OBC") == (-140.0, -30.0) and pos(w, "PCDU") == (
        -140.0,
        230.0,
    )  # 260 apart as before
    assert w.steps() == 1


def test_shift_arrow_moves_a_device_below_zero(qtbot, tmp_path) -> None:
    w = world(tmp_path)
    w.win.ctl.move_unit("OBC", 0.0, 0.0)
    w.settle()
    w.win.ctl.select("unit", "OBC")
    item = w.scene.unit_items["OBC"]
    item.setFocus()
    QTest.keyClick(w.view.viewport(), Qt.Key.Key_Left, Qt.KeyboardModifier.ShiftModifier)
    QTest.keyClick(w.view.viewport(), Qt.Key.Key_Up, Qt.KeyboardModifier.ShiftModifier)
    assert pos(w, "OBC") == (-10.0, -10.0)


def test_with_snap_to_grid_on_a_device_below_zero_lands_on_the_grid(qtbot, tmp_path) -> None:
    w = world(tmp_path, snap=True)
    start = header(w, "OBC")
    w.drag(start, start + QPointF(-283, -197))
    x, y = pos(w, "OBC")
    assert (x, y) == (-220.0, -130.0)


def test_a_device_added_at_a_point_below_zero_is_put_there(qtbot, tmp_path) -> None:
    w = world(tmp_path)
    before = set(w.project.units)
    w.view._add_here("payload", QPointF(-400, -300))
    (uid,) = set(w.project.units) - before
    x, y = pos(w, uid)
    assert x < 0 and y < 0


def test_reopening_the_project_keeps_every_position(qtbot, tmp_path) -> None:
    w = world(tmp_path)
    start = header(w, "OBC")
    w.drag(start, start + QPointF(-400, -250))
    start = header(w, "RW1")
    w.drag(start, start + QPointF(1500, 900))
    folder = tmp_path / "saved"
    save_project(w.project, folder)
    expect = {uid: pos(w, uid) for uid in w.project.units}
    w2 = World(tmp_path / "reopen", quick=False, mode="expert")
    w2.win.ctl.open_path(folder)
    w2.settle()
    assert {uid: pos(w2, uid) for uid in w2.project.units} == expect
    assert w2.scene.unit_items["OBC"].pos() == QPointF(*expect["OBC"])
    assert w2.scene.sceneRect().contains(w2.scene.unit_items["RW1"].sceneBoundingRect())
    assert layout.model_hash(w2.project) == layout.model_hash(w.project)


def test_dragging_a_device_to_the_edge_of_the_view_scrolls_the_view_and_the_device_follows(
    qtbot, tmp_path
) -> None:
    w = world(tmp_path, scroll=True)
    item = w.scene.unit_items["OBC"]
    left = w.view.mapToScene(QPoint(0, 0)).x()
    start = w.at(header(w, "OBC"))
    vw = w.view.viewport().width()
    QTest.mousePress(w.view.viewport(), LEFT, pos=start)
    for k in range(1, 6):
        QTest.mouseMove(
            w.view.viewport(), pos=QPoint(start.x() + (vw - 6 - start.x()) * k // 5, start.y())
        )
        QApplication.processEvents()
    x0 = item.pos().x()
    for _ in range(300):
        QTest.qWait(10)
        if item.pos().x() > x0 + 600:
            break
    QTest.mouseRelease(w.view.viewport(), LEFT, pos=QPoint(vw - 6, start.y()))
    QApplication.processEvents()
    assert w.view.mapToScene(QPoint(0, 0)).x() > left + 400  # the view scrolled
    assert item.pos().x() > x0 + 600 and pos(w, "OBC")[0] == item.pos().x()
    assert not w.view.unit_drag


def test_the_view_does_not_scroll_while_the_device_is_in_the_middle(qtbot, tmp_path) -> None:
    w = world(tmp_path, scroll=True)
    start = header(w, "OBC")
    w.press(start)  # (picking a device may bring it fully into view: look after that)
    left = w.view.mapToScene(QPoint(0, 0))
    w.move(start + QPointF(40, 30))
    QTest.qWait(150)
    w.release(start + QPointF(40, 30))
    assert w.view.mapToScene(QPoint(0, 0)) == left


def test_fit_still_shows_every_device_even_far_out(qtbot, tmp_path) -> None:
    w = world(tmp_path)
    w.win.ctl.move_unit("RW1", 3000.0, 1800.0)
    w.win.ctl.move_unit("OBC", -1500.0, -900.0)
    w.settle()
    w.view.fit()
    w.settle()
    box = w.view.viewport().rect()
    for uid in ("OBC", "PCDU", "RW1"):
        r = w.view.mapFromScene(w.scene.unit_items[uid].sceneBoundingRect()).boundingRect()
        assert box.contains(r), (uid, r, box)


def test_the_view_can_still_be_panned_and_zoomed_beyond_the_old_edge(qtbot, tmp_path) -> None:
    w = world(tmp_path)
    start = header(w, "RW1")
    w.drag(start, start + QPointF(1800, 0))
    w.view.horizontalScrollBar().setValue(w.view.horizontalScrollBar().maximum())
    before = w.view.horizontalScrollBar().value()
    mid = w.view.viewport().rect().center()
    QTest.mousePress(w.view.viewport(), Qt.MouseButton.MiddleButton, pos=mid)
    QTest.mouseMove(w.view.viewport(), pos=mid + QPoint(200, 0))
    QTest.mouseRelease(w.view.viewport(), Qt.MouseButton.MiddleButton, pos=mid + QPoint(200, 0))
    assert w.view.horizontalScrollBar().value() == before - 200  # pan with the middle button
    scale = w.view.zoom_scale()
    ev = QWheelEvent(
        QPointF(mid), QPointF(w.view.viewport().mapToGlobal(mid)), QPoint(0, 0), QPoint(0, 120),
        Qt.MouseButton.NoButton, Qt.KeyboardModifier.ControlModifier, Qt.ScrollPhase.NoScrollPhase, False,
    )  # fmt: skip
    QApplication.sendEvent(w.view.viewport(), ev)
    assert w.view.zoom_scale() > scale  # Ctrl+wheel zooms


def test_dragging_with_space_held_pans_and_moves_no_device(qtbot, tmp_path) -> None:
    w = world(tmp_path)
    w.view.set_snap(False)
    start = header(w, "OBC")
    QTest.keyPress(w.view, Qt.Key.Key_Space)
    w.drag(start, start + QPointF(-120, -60))
    QTest.keyRelease(w.view, Qt.Key.Key_Space)
    assert pos(w, "OBC") == (60.0, 70.0) and w.steps() == 0


def test_the_scene_extent_is_worked_out_again_after_a_device_comes_back(qtbot, tmp_path) -> None:
    w = world(tmp_path)
    rect0 = QRectF(w.scene.sceneRect())
    start = header(w, "RW1")
    w.drag(start, start + QPointF(2200, 1200))
    assert w.scene.sceneRect().right() > rect0.right() + 1500
    w.win.ctl.undo()
    w.settle()
    assert w.scene.sceneRect().right() <= rect0.right() + 256


def test_export_diagram_frames_every_device_when_they_are_far_out(qtbot, tmp_path) -> None:
    w = world(tmp_path)
    w.win.ctl.move_unit("OBC", -4000.0, -3000.0)
    w.win.ctl.move_unit("RW1", 90000.0, 70000.0)
    w.win.ctl.add_link("OBC-J01", "RW1-J02", [("1", "3")])
    sheet = diagram_export.diagram_sheet(w.project)
    assert sheet is not None
    for it in sheet.items:
        x0, y0, x1, y1 = item_bounds(it)
        assert (
            x0 >= -1e-9 and y0 >= -1e-9 and x1 <= sheet.width + 1e-9 and y1 <= sheet.height + 1e-9
        )
    texts = " ".join(getattr(it, "s", "") for it in sheet.items)
    assert all(uid in texts for uid in ("OBC", "RW1", "PCDU"))
    written = diagram_export.write_diagram(w.project, tmp_path / "far")
    assert sorted(p.suffix for p in written) == [".pdf", ".png", ".svg"] and all(
        p.stat().st_size for p in written
    )
