# SPDX-FileCopyrightText: 2026 0h3xn4
# SPDX-License-Identifier: GPL-3.0-only
# mypy: disable-error-code="no-untyped-def,no-untyped-call,attr-defined,union-attr,arg-type"
"""REQ-GUI-13. Workshop feedback: "very confusing overlappings" on the diagram. The boxes of one
connection (the label and the connector box at each end) do not cover each other or a device, a
long label is cut with an ellipsis and read whole in the tooltip, the hint over a diagram without
connections keeps clear of the lane names and devices, and the tool row keeps "More" in the window
at 1000 px."""

import pytest

pytest.importorskip("PySide6")
pytestmark = pytest.mark.gui

from PySide6.QtCore import QPointF, QRectF  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from harness_design_studio.core.model import Pin  # noqa: E402
from harness_design_studio.gui import canvas_links  # noqa: E402
from harness_design_studio.gui.canvas import METRICS  # noqa: E402
from tests.test_ui_links import window  # noqa: E402


def draw(win) -> None:
    win.view.viewport().repaint()
    QApplication.processEvents()
    win.view.grab()


def level_link(tmp_path, role=None):
    """Two devices side by side in two lanes at one height, one connector-to-connector link whose
    pins carry no signal ("No interface type, 1 wire"), the connector boxes shown."""
    win = window(tmp_path, role)
    p = win.ctl.project
    p.connectors["RW1-J02"] = p.connectors["RW1-J02"].model_copy(
        update={"pins": [Pin(id=str(k)) for k in range(1, 6)]}
    )
    win.ctl.move_unit("OBC", 30.0, 170.0)
    assert win.ctl.add_link("OBC-J03", "RW1-J02", [("1", "1")]) == "L1"
    win.ctl.set_mode("expert")
    QApplication.processEvents()
    draw(win)
    return win, win.view.dscene.connection_items["L1"]


def unit_rects(win) -> list[QRectF]:
    return [  # the cards themselves (the bounding rectangle also holds the shadow)
        QRectF(u.pos().x(), u.pos().y(), METRICS.unit_w, u.height())
        for u in win.view.dscene.unit_items.values()
    ]


def test_the_boxes_of_one_connection_do_not_cover_each_other_or_a_device(tmp_path) -> None:
    win, item = level_link(tmp_path)
    boxes = [item._chip, *item._end_rects]
    assert len(boxes) == 3 and all(not b.isEmpty() for b in boxes)
    for k, a in enumerate(boxes):
        for b in boxes[k + 1 :]:
            assert not a.intersects(b), (a, b)
        for unit in unit_rects(win):
            assert not a.intersects(unit), (a, unit)


def test_the_boxes_stay_clear_when_the_devices_are_close(tmp_path) -> None:
    win, item = level_link(tmp_path)
    win.ctl.move_unit("RW1", 330.0, 170.0)  # the lanes are what keep them apart, so go to the edge
    QApplication.processEvents()
    draw(win)
    end_a, end_b = item._end_rects
    assert not end_a.intersects(end_b)
    assert not item._chip.intersects(end_a) and not item._chip.intersects(end_b)


def test_a_long_name_is_cut_with_an_ellipsis_and_the_tooltip_has_it_whole(tmp_path) -> None:
    win, item = level_link(tmp_path)
    name = "Primary power supply to the attitude control reaction wheel, redundant side B"
    assert win.ctl.rename_link("L1", name)
    draw(win)
    assert item._chip.width() <= canvas_links.CHIP_MAX_W + 0.5
    item.hoverEnterEvent(None)
    assert name in item.toolTip()


def test_the_hint_keeps_clear_of_the_lane_names_and_the_devices(tmp_path) -> None:
    win = window(tmp_path)
    win.show()
    for width in (1440, 1000):
        win.resize(width, 800)
        QApplication.processEvents()
        view = win.view
        assert view.empty.isVisible()
        hint = view.empty.geometry().translated(-view.viewport().geometry().topLeft())
        for zone in view.dscene.zone_items:
            title = view.mapFromScene(zone.mapToScene(QPointF(10, 4)))
            assert not hint.intersects(type(hint)(title.x(), title.y(), 60, 16)), (
                "the hint covers a lane name"
            )
        for unit in view.dscene.unit_items.values():
            assert not hint.intersects(view.mapFromScene(unit.sceneBoundingRect()).boundingRect())


def narrow(win, width: int) -> None:
    for _ in range(2):  # (the side panels close the first time the window crosses a width)
        win.resize(width, 800)
        QApplication.processEvents()


@pytest.mark.parametrize("role", ["systems", "electrical"])
def test_the_tool_row_fits_the_window_at_1000_px_with_the_connect_hint(tmp_path, role) -> None:
    win = window(tmp_path, role)
    win.ctl.begin_link()  # the longest hint
    narrow(win, 1000)
    assert win.minimumSizeHint().width() <= 1000
    assert win.width() == 1000
    bar = win.tool_row
    for k in range(bar.count()):
        w = bar.itemAt(k).widget()
        if w is not None and w.isVisible():
            right = w.mapTo(win, w.rect().topRight()).x()
            assert right <= win.width(), (w.objectName(), right)
    if role == "systems":
        assert win.tool_more.isVisible()
