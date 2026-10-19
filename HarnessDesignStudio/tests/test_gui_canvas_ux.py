# mypy: disable-error-code="no-untyped-def,no-untyped-call"
"""The diagram canvas as a workspace (UX audit CV-1 to CV-29): selection of several items, align,
duplicate, navigation, search, context menu, legend, grid, delete questions, read-only messages,
drag preview. Driven like a user, offscreen, on the flatsat example."""

from pathlib import Path

import pytest

pytest.importorskip("PySide6")
from PySide6.QtCore import QEvent, QPoint, QPointF, Qt  # noqa: E402
from PySide6.QtGui import QContextMenuEvent, QMouseEvent, QWheelEvent  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication, QComboBox, QLabel  # noqa: E402

pytestmark = pytest.mark.gui

from harness_design_studio.core import edit, templates  # noqa: E402
from harness_design_studio.core.io.loader import load_project  # noqa: E402
from harness_design_studio.gui import strings  # noqa: E402
from harness_design_studio.gui.canvas import METRICS, CanvasMetrics, find_matches  # noqa: E402
from tests.gui_helpers import DialogScript, make_window, show_problems, unit_point  # noqa: E402

LEFT = Qt.MouseButton.LeftButton


@pytest.fixture
def win(qtbot, tmp_path: Path):
    folder = tmp_path / "flatsat"
    templates.create_project(folder, "flatsat")
    w = make_window(tmp_path)
    qtbot.addWidget(w)
    w.ctl._install(load_project(folder).project, None, None)
    w.view.fit()
    QApplication.processEvents()
    return w


@pytest.fixture
def plain(qtbot, tmp_path: Path):
    """The window with its sample project (three units), nothing generated."""
    w = make_window(tmp_path)
    qtbot.addWidget(w)
    QApplication.processEvents()
    return w


def click(win, uid: str, mods=Qt.KeyboardModifier.NoModifier) -> None:
    QTest.mouseClick(win.view.viewport(), LEFT, mods, unit_point(win, uid))


def wheel(win, *, angle=(0, 120), pixels=(0, 0), mods=Qt.KeyboardModifier.NoModifier, at=None):
    vp = win.view.viewport()
    pos = QPointF(at if at is not None else vp.rect().center())
    ev = QWheelEvent(
        pos, vp.mapToGlobal(pos), QPoint(*pixels), QPoint(*angle), Qt.MouseButton.NoButton,
        mods, Qt.ScrollPhase.NoScrollPhase, False,
    )  # fmt: skip
    QApplication.sendEvent(vp, ev)


def empty_spot(win) -> QPoint:
    """A viewport point with no unit and no link under it."""
    v = win.view
    for x in range(20, v.viewport().width() - 20, 17):
        for y in range(20, v.viewport().height() - 20, 17):
            pt = QPoint(x, y)
            item = v.itemAt(pt)
            if (item is None or item.zValue() < 0) and v.dscene.chip_at(v.mapToScene(pt)) is None:
                return pt
    raise AssertionError("no free spot")


def undo_depth(win) -> int:
    return len(win.ctl.history._undo)


# ---- CV-1 selecting several items ------------------------------------------------------------------


def test_the_controller_keeps_a_set_and_the_primary_item(win) -> None:
    c = win.ctl
    c.select("unit", "OBC1")
    assert c.selection.id == "OBC1" and len(c.selected) == 1  # single selection still works
    c.select_many([("unit", "PDU2"), ("unit", "RW1")])
    assert [s.id for s in c.selected] == ["PDU2", "RW1"] and c.selection.id == "RW1"
    c.toggle("unit", "OBC1")
    assert c.selected_ids("unit") == ["PDU2", "RW1", "OBC1"] and c.selection.id == "OBC1"
    c.toggle("unit", "OBC1")
    assert c.selected_ids("unit") == ["PDU2", "RW1"] and c.selection.id == "RW1"
    c.select(None)
    assert c.selection is None and c.selected == ()
    c.select_all()
    assert len(c.selected_ids("unit")) == 23 and len(c.selected_ids("interface")) == 44


def test_a_selection_set_directly_is_still_understood(win) -> None:
    from harness_design_studio.gui.controller import Selection

    win.ctl.selection = Selection("unit", "OBC1")  # older code assigns the attribute
    assert win.ctl.selected == (Selection("unit", "OBC1"),)
    assert win.ctl.is_selected("unit", "OBC1")


def test_selecting_signals_once_per_change(win) -> None:
    seen: list[int] = []
    win.ctl.selectionChanged.connect(lambda: seen.append(1))
    win.ctl.select_many([("unit", "OBC1"), ("unit", "PDU2")])
    win.ctl.select_many([("unit", "OBC1"), ("unit", "PDU2")])  # nothing changed
    assert seen == [1]


def test_shift_click_and_ctrl_click_add_and_remove_units(win) -> None:
    click(win, "OBC1")
    click(win, "PDU2", Qt.KeyboardModifier.ShiftModifier)
    click(win, "RW1", Qt.KeyboardModifier.ControlModifier)
    assert win.ctl.selected_ids("unit") == ["OBC1", "PDU2", "RW1"]
    click(win, "PDU2", Qt.KeyboardModifier.ControlModifier)
    assert win.ctl.selected_ids("unit") == ["OBC1", "RW1"]
    click(win, "RW2")  # a plain click picks one
    assert win.ctl.selected_ids("unit") == ["RW2"]


def test_a_plain_click_on_one_of_several_selected_picks_only_it_on_release(win) -> None:
    win.ctl.select_many([("unit", "OBC1"), ("unit", "PDU2")])
    click(win, "OBC1")
    assert win.ctl.selected_ids("unit") == ["OBC1"]


def test_rubber_band_selects_what_it_touches(win) -> None:
    v = win.view
    a, b = (v.dscene.unit_items[u] for u in ("OBC1", "BAT1"))
    top_left = v.mapFromScene(QPointF(min(a.pos().x(), b.pos().x()) - 20, a.pos().y() - 20))
    bottom_right = v.mapFromScene(QPointF(max(a.pos().x(), b.pos().x()) + 260, b.pos().y() + 60))
    assert v.itemAt(top_left) is None or v.itemAt(top_left).zValue() < 0
    QTest.mousePress(v.viewport(), LEFT, pos=top_left)
    QTest.mouseMove(
        v.viewport(),
        pos=QPoint((top_left.x() + bottom_right.x()) // 2, (top_left.y() + bottom_right.y()) // 2),
    )
    QTest.mouseMove(v.viewport(), pos=bottom_right)
    assert v._band is not None
    QTest.mouseRelease(v.viewport(), LEFT, pos=bottom_right)
    assert v._band is None
    picked = set(win.ctl.selected_ids("unit"))
    assert {
        "OBC1",
        "BAT1",
    } <= picked  # (the exact set depends on the lanes; the corners are enough)
    box = v.mapToScene(top_left).x(), v.mapToScene(bottom_right).x()
    assert all(
        box[0] - 240 <= v.dscene.unit_items[u].pos().x() <= box[1] for u in picked
    )  # nothing outside the band's columns was taken


def test_ctrl_a_selects_everything_in_the_diagram(win) -> None:
    win.view.setFocus()
    QTest.keyClick(win.view, Qt.Key.Key_A, Qt.KeyboardModifier.ControlModifier)
    assert len(win.ctl.selected_ids("unit")) == 23 and len(win.ctl.selected_ids("interface")) == 44


def test_the_properties_of_several_units_show_the_common_fields_and_edit_them_in_one_step(
    win,
) -> None:
    win.ctl.select_many([("unit", "RW1"), ("unit", "RW2")])
    QApplication.processEvents()
    assert win.props.findChild(QLabel, "multi-count") is not None
    side = win.props.findChild(QComboBox, "unit-side")
    assert side is not None and side.currentText() == "nominal"
    depth = undo_depth(win)
    side.setCurrentText("none")
    side.activated.emit(side.currentIndex())
    assert [win.ctl.project.units[u].side for u in ("RW1", "RW2")] == ["none", "none"]
    assert undo_depth(win) == depth + 1  # one undo step for both
    win.act_undo.trigger()
    assert [win.ctl.project.units[u].side for u in ("RW1", "RW2")] == ["nominal", "nominal"]


def test_different_values_read_different_and_stay_unless_edited(win) -> None:
    p = win.ctl.project
    one, two = sorted(p.interfaces)[:2]
    win.ctl.update_interface(one, voltage_v=28.0)
    win.ctl.update_interface(two, voltage_v=5.0)
    win.ctl.select_many([("interface", one), ("interface", two)])
    field = win.props.fields["multi-voltage_v"]
    assert field.text() == "" and field.placeholderText() == strings.MULTI_DIFFERENT
    field.editingFinished.emit()  # left alone: nothing changes
    assert (p.interfaces[one].voltage_v, p.interfaces[two].voltage_v) == (28.0, 5.0)
    field.setText("12")
    field.editingFinished.emit()
    assert (p.interfaces[one].voltage_v, p.interfaces[two].voltage_v) == (12.0, 12.0)


def test_deleting_several_items_is_one_confirmation_and_one_undo_step(plain) -> None:
    win = plain
    win.ctl.select_many([("unit", "OBC"), ("interface", "IF-TM-RW1")])
    before = (set(win.ctl.project.units), set(win.ctl.project.interfaces))
    seen: list[str] = []
    DialogScript(win, lambda d: seen.append(d.body.text()), accept=True)
    depth = undo_depth(win)
    win.delete_flow()
    assert "OBC" in seen[0] and "IF-TM-RW1" in seen[0] and len(seen) == 1
    assert "OBC" not in win.ctl.project.units and "IF-TM-RW1" not in win.ctl.project.interfaces
    assert undo_depth(win) == depth + 1
    win.act_undo.trigger()
    assert (set(win.ctl.project.units), set(win.ctl.project.interfaces)) == before


def test_a_selection_puts_all_its_links_in_focus_and_the_filter_takes_several_values(win) -> None:
    scene = win.view.dscene
    win.ctl.select_many([("unit", "RW1"), ("unit", "RW2")])
    from harness_design_studio.core import routing

    mine = (
        routing.focus(win.ctl.project, "unit", "RW1")[0]
        | routing.focus(win.ctl.project, "unit", "RW2")[0]
    )
    assert {i for i, link in scene.link_items.items() if link.opacity() == 1.0} == mine
    win.ctl.select(None)
    scene.set_filter("class", ["power", "rf"])
    keep = scene.matching_interfaces()
    assert keep and {scene._link_category(i) for i in keep} == {"power", "rf"}
    scene.set_filter(None)
    assert scene.filter is None


def test_the_tree_follows_and_drives_a_selection_of_several(win) -> None:
    """Was the Outline's test: a selection of several units shows in the tree, and Shift in the
    tree selects several on the diagram (the keyboard way to what the rubber band does)."""
    tree = win.project_tree
    QApplication.processEvents()

    def highlighted() -> set[tuple[str, str]]:
        rows = tree.view.selectionModel().selectedRows()
        return {(tree._node_at(i).kind, tree._node_at(i).id) for i in rows}

    win.ctl.select_many([("unit", "RW1"), ("unit", "RW2")])
    assert highlighted() == {("unit", "RW1"), ("unit", "RW2")}
    win.ctl.select(None)
    assert highlighted() == set()
    first, second = tree.child_ids("units")[:2]
    tree.view.setCurrentIndex(tree.index_for("unit", first))
    tree.view.setFocus()
    QTest.keyClick(tree.view, Qt.Key.Key_Down, Qt.KeyboardModifier.ShiftModifier)
    assert {(s.kind, s.id) for s in win.ctl.selected} == {("unit", first), ("unit", second)}
    assert highlighted() == {("unit", first), ("unit", second)}
    QTest.keyClick(tree.view, Qt.Key.Key_Up, Qt.KeyboardModifier.ShiftModifier)
    assert {(s.kind, s.id) for s in win.ctl.selected} == {("unit", first)}  # back to one


def test_dragging_one_of_several_selected_units_moves_them_together_as_one_step(win) -> None:
    v, p = win.view, win.ctl.project
    win.ctl.select_many([("unit", "RW1"), ("unit", "RW2")])
    before = {u: edit.position_of(p, u) for u in ("RW1", "RW2")}
    start = unit_point(win, "RW1")
    end = start + QPoint(0, 60)
    depth = undo_depth(win)
    QTest.mousePress(v.viewport(), LEFT, pos=start)
    QTest.mouseMove(v.viewport(), pos=start + QPoint(0, 30))
    QTest.mouseMove(v.viewport(), pos=end)
    QTest.mouseRelease(v.viewport(), LEFT, pos=end)
    after = {u: edit.position_of(p, u) for u in ("RW1", "RW2")}
    dy = {u: after[u][1] - before[u][1] for u in after}
    assert dy["RW1"] == dy["RW2"] != 0
    assert undo_depth(win) == depth + 1
    win.act_undo.trigger()
    assert {u: edit.position_of(p, u) for u in before} == before


# ---- CV-2 align, distribute, duplicate -------------------------------------------------------------


def test_align_and_distribute_are_menu_actions_with_reasons_and_one_undo_step(win) -> None:
    ids = ["RW1", "RW2", "RW3"]
    win.ctl.select("unit", "RW1")
    assert not win.align_actions["left"].isEnabled()
    assert win.align_actions["left"].toolTip() == strings.WHY_NEED_TWO_UNITS
    win.ctl.select_many([("unit", u) for u in ids])
    assert win.align_actions["left"].isEnabled() and win.distribute_actions["vertical"].isEnabled()
    p = win.ctl.project
    win.ctl.move_units({"RW1": (win.ctl.project.placements["RW1"].x + 20.0, 40.0)})
    depth = undo_depth(win)
    win.align_actions["left"].trigger()
    xs = {edit.position_of(p, u)[0] for u in ids}
    assert len(xs) == 1 and undo_depth(win) == depth + 1
    depth = undo_depth(win)
    win.align_actions["top"].trigger()
    assert len({edit.position_of(p, u)[1] for u in ids}) == 1 and undo_depth(win) == depth + 1
    menu_titles = [a.text() for a in win.menuBar().actions()]
    assert "Edit" in " ".join(menu_titles)
    edit_menu = next(
        a.menu() for a in win.menuBar().actions() if a.text().replace("&", "") == "Edit"
    )
    sub = {a.text() for a in edit_menu.actions() if a.menu() is not None}
    assert {strings.A_ALIGN, strings.A_DISTRIBUTE} <= sub


def test_ctrl_d_copies_the_selected_units_in_one_step_and_selects_the_copies(win) -> None:
    win.ctl.select_many([("unit", "RW1"), ("unit", "RW2")])
    win.view.setFocus()
    n, depth = len(win.ctl.project.units), undo_depth(win)
    QTest.keyClick(win.view, Qt.Key.Key_D, Qt.KeyboardModifier.ControlModifier)
    assert len(win.ctl.project.units) == n + 2 and undo_depth(win) == depth + 1
    assert len(win.ctl.selected_ids("unit")) == 2 and not set(win.ctl.selected_ids("unit")) & {
        "RW1",
        "RW2",
    }
    win.act_undo.trigger()
    assert len(win.ctl.project.units) == n


def test_duplicate_says_why_it_is_off(win) -> None:
    win.ctl.select(None)
    assert not win.act_duplicate.isEnabled()
    assert win.act_duplicate.toolTip() == strings.WHY_NEED_UNIT_SELECTED


# ---- CV-3 the wheel and panning ---------------------------------------------------------------------


def test_the_wheel_alone_scrolls_and_never_zooms(win) -> None:
    v = win.view
    v.zoom_100()
    scale = v.zoom_scale()
    v.verticalScrollBar().setValue(v.verticalScrollBar().maximum() // 2)
    y = v.verticalScrollBar().value()
    wheel(win, angle=(0, -120))
    assert v.zoom_scale() == scale and v.verticalScrollBar().value() > y
    x = v.horizontalScrollBar().value()
    wheel(win, angle=(0, -120), mods=Qt.KeyboardModifier.ShiftModifier)
    assert v.zoom_scale() == scale and v.horizontalScrollBar().value() > x


def test_a_trackpad_scrolls_in_pixels_both_ways(win) -> None:
    v = win.view
    v.zoom_100()
    v.horizontalScrollBar().setValue(100)
    v.verticalScrollBar().setValue(100)
    wheel(win, angle=(0, 0), pixels=(30, -25))
    assert (v.horizontalScrollBar().value(), v.verticalScrollBar().value()) == (70, 125)


def test_ctrl_wheel_zooms_about_the_pointer(win) -> None:
    v = win.view
    v.zoom_100()
    at = QPoint(300, 200)
    before = v.mapToScene(at)
    scale = v.zoom_scale()
    wheel(win, angle=(0, 120), mods=Qt.KeyboardModifier.ControlModifier, at=at)
    assert v.zoom_scale() > scale
    assert (v.mapToScene(at) - before).manhattanLength() < 0.6
    wheel(win, angle=(0, -240), mods=Qt.KeyboardModifier.ControlModifier, at=at)
    assert v.zoom_scale() < scale


def test_middle_button_and_space_drag_pan_without_moving_units(win) -> None:
    v = win.view
    v.zoom_100()
    v.horizontalScrollBar().setValue(200)
    v.verticalScrollBar().setValue(200)
    p = win.ctl.project
    positions = {u: edit.position_of(p, u) for u in p.units}
    depth = undo_depth(win)
    start = unit_point(win, "OBC1") if v.itemAt(unit_point(win, "OBC1")) else QPoint(300, 300)
    v.centerOn(v.dscene.unit_items["OBC1"])
    start = unit_point(win, "OBC1")
    hbar = v.horizontalScrollBar().value()
    send(v.viewport(), QEvent.Type.MouseButtonPress, start, Qt.MouseButton.MiddleButton)
    send(v.viewport(), QEvent.Type.MouseMove, start + QPoint(-40, 0), Qt.MouseButton.MiddleButton)
    send(
        v.viewport(),
        QEvent.Type.MouseButtonRelease,
        start + QPoint(-40, 0),
        Qt.MouseButton.MiddleButton,
    )
    assert v.horizontalScrollBar().value() == hbar + 40
    # Space held, then a left drag on a unit
    QTest.keyPress(v, Qt.Key.Key_Space)
    start = unit_point(win, "OBC1")
    hbar = v.horizontalScrollBar().value()
    send(v.viewport(), QEvent.Type.MouseButtonPress, start, LEFT)
    send(v.viewport(), QEvent.Type.MouseMove, start + QPoint(25, 0), LEFT)
    send(v.viewport(), QEvent.Type.MouseButtonRelease, start + QPoint(25, 0), LEFT)
    QTest.keyRelease(v, Qt.Key.Key_Space)
    assert v.horizontalScrollBar().value() == hbar - 25
    assert {u: edit.position_of(p, u) for u in p.units} == positions and undo_depth(win) == depth
    assert win.ctl.selection is None or win.ctl.selection.id != "OBC1"


def send(widget, kind, pos: QPoint, button) -> None:
    held = Qt.MouseButton.NoButton if kind == QEvent.Type.MouseButtonRelease else button
    ev = QMouseEvent(
        kind, QPointF(pos), QPointF(widget.mapToGlobal(pos)), button, held,
        Qt.KeyboardModifier.NoModifier,
    )  # fmt: skip
    QApplication.sendEvent(widget, ev)


# ---- CV-4 zoom commands -----------------------------------------------------------------------------


def test_f_fits_ctrl_0_is_100_percent_and_shift_f_zooms_to_the_selection(win) -> None:
    v = win.view
    seen: list[float] = []
    v.zoomChanged.connect(seen.append)
    v.zoom_100()
    v.setFocus()
    QTest.keyClick(v, Qt.Key.Key_F)
    fitted = v.zoom_scale()
    assert fitted < 0.5 and seen[-1] == fitted
    QTest.keyClick(v, Qt.Key.Key_0, Qt.KeyboardModifier.ControlModifier)
    assert v.zoom_scale() == pytest.approx(1.0) and win.zoom_level.text() == "100 %"
    win.ctl.select("unit", "RW3")
    QTest.keyClick(v, Qt.Key.Key_F, Qt.KeyboardModifier.ShiftModifier)
    assert v.zoom_scale() > fitted
    area = v.mapToScene(v.viewport().rect()).boundingRect()
    assert area.contains(v.dscene.unit_items["RW3"].sceneBoundingRect())


def test_f_does_nothing_when_the_keyboard_is_elsewhere(win) -> None:
    win.view.zoom_100()
    win.interface_table.view.setFocus()
    QTest.keyClick(win.interface_table.view, Qt.Key.Key_F)
    assert win.view.zoom_scale() == pytest.approx(1.0)


def test_the_zoom_controls_have_tooltips_with_their_shortcuts_and_the_scale_menu_is_renamed(
    win,
) -> None:
    assert "Ctrl+=" in win.zoom_in_btn.toolTip() and "Ctrl+-" in win.zoom_out_btn.toolTip()
    assert "(F)" in win.fit_btn.toolTip()
    assert "Ctrl+0" in win.zoom_level.toolTip()
    view_menu = next(
        a.menu() for a in win.menuBar().actions() if a.text().replace("&", "") == "View"
    )
    assert "Interface size" in [a.text() for a in view_menu.actions()]
    assert "UI scale" not in [a.text() for a in view_menu.actions()]


def test_clicking_the_zoom_level_returns_to_100_percent(win) -> None:
    win.view.fit()
    win.zoom_level.click()
    assert win.view.zoom_scale() == pytest.approx(1.0)


# ---- CV-5 legible default view ----------------------------------------------------------------------


def test_the_overview_text_is_about_twelve_screen_pixels_at_any_zoom(win) -> None:
    from PySide6.QtGui import QImage, QPainter

    item = win.view.dscene.unit_items["OBC1"]
    unit = win.ctl.project.units["OBC1"]
    for lod in (0.1, 0.2, 0.3, 0.4):
        img = QImage(300, 200, QImage.Format.Format_ARGB32)
        p = QPainter(img)
        p.scale(lod, lod)
        item._paint_overview(p, win.theme, unit, "", lod)
        screen_px = p.font().pixelSize() * lod
        p.end()
        assert 7.5 <= screen_px <= 14, (lod, screen_px)


def test_a_project_opens_readable_and_fit_never_shrinks_below_the_floor(qtbot, tmp_path) -> None:
    from tools.bench_stress import build

    w = make_window(tmp_path)
    qtbot.addWidget(w)
    w.ctl._install(build(), None, None)
    QApplication.processEvents()
    QTest.qWait(30)
    assert w.view.zoom_scale() >= METRICS.min_open_scale - 1e-9
    w.view.fit()
    assert w.view.zoom_scale() >= METRICS.min_fit_scale - 1e-9
    w.view.zoom_by(0.01)  # but the person can still zoom out to see everything
    assert w.view.zoom_scale() < METRICS.min_fit_scale


def test_the_map_and_legend_make_room_in_a_small_window(win) -> None:
    v = win.view
    big = v.minimap.size()
    assert v.legend.isVisibleTo(v) and v.minimap.isVisibleTo(v)
    win.resize(
        1280, 520
    )  # (the bottom panel is gone: a window this short is what is left of 640 px with it)
    QApplication.processEvents()
    assert not v.minimap.isVisibleTo(v) or v.minimap.size().height() < big.height()
    assert not v.legend.is_open  # starts folded where it would cover the diagram
    v.legend.toggle.click()  # the person can open it, and it stays open
    assert v.legend.is_open
    win.resize(1440, 900)
    QApplication.processEvents()
    assert v.legend.is_open


# ---- CV-11 open the plans from the diagram ----------------------------------------------------------


def test_double_click_and_enter_ask_for_the_plans(win) -> None:
    asked: list[tuple[str, str]] = []
    win.ctl.openRequested.connect(lambda k, i: asked.append((k, i)))
    QTest.mouseDClick(
        win.view.viewport(), LEFT, Qt.KeyboardModifier.NoModifier, unit_point(win, "RW1")
    )
    assert asked[-1] == ("unit", "RW1")
    link = win.view.dscene.link_items["IF-010"]
    win.view.zoom_100()  # (labels are drawn, and so can be clicked, from half scale up)
    win.view.centerOn(win.view.dscene.chip_rect("IF-010").center())
    chip = win.view.mapFromScene(win.view.dscene.chip_rect("IF-010").center())
    QTest.mouseDClick(win.view.viewport(), LEFT, Qt.KeyboardModifier.NoModifier, chip)
    assert asked[-1] == ("interface", "IF-010")
    asked.clear()
    win.view.dscene.unit_items["RW2"].setFocus()
    QTest.keyClick(win.view, Qt.Key.Key_Return)
    assert asked == [("unit", "RW2")]
    link.setFocus()
    QTest.keyClick(win.view, Qt.Key.Key_Return)
    assert asked[-1][0] == "interface"


def test_opening_a_link_shows_its_wire_in_the_harness_plans(win) -> None:
    # the Harness tab of the shell (the old plans panel of the bottom dock no longer takes it)
    win.ctl.request_open("interface", "IF-010")
    assert win.main_tabs.currentWidget() is win.harness_view
    assert win.harness_view.harness_id() == "W001"
    selection = win.harness_view.selection()
    assert selection is not None and selection[0] == "wire" and selection[1].startswith("W001")
    win.ctl.request_open("unit", "RW1")
    assert win.harness_view.harness_id() is not None


def test_a_link_with_no_plan_gets_a_toast_with_a_generate_button(plain) -> None:
    win = plain
    asked: list[bool] = []
    win.generate_flow = lambda: asked.append(True)  # type: ignore[method-assign]
    win.ctl.request_open("interface", "IF-TM-RW1")
    assert any("Not generated yet" in m for m in win.toasts.messages)
    button = win.toasts.findChild(type(win.generate_btn), "toast-action")
    assert button is not None and button.text() == strings.GENERATE
    button.click()
    assert asked == [True]


# ---- CV-12 the context menu ------------------------------------------------------------------------


def menu_texts(menu) -> list[str]:
    return [a.text().split("\t")[0] for a in menu.actions() if not a.isSeparator()]


def test_the_context_menu_of_a_unit_mirrors_the_window_actions(win) -> None:
    v = win.view
    shown = []
    v.exec_menu = lambda menu, at: shown.append(menu)
    pt = unit_point(win, "RW1")
    QApplication.sendEvent(
        v.viewport(),
        QContextMenuEvent(QContextMenuEvent.Reason.Mouse, pt, v.viewport().mapToGlobal(pt)),
    )
    assert win.ctl.selection.id == "RW1" and shown
    texts = menu_texts(shown[-1])
    assert strings.CM_OPEN_PLAN in texts
    assert any(t.startswith(strings.A_DUPLICATE) for t in texts)
    assert any(t.startswith(strings.A_ALIGN) for t in texts)  # disabled: one unit
    align = next(a for a in shown[-1].actions() if a.text().startswith(strings.A_ALIGN))
    assert not align.menu().isEnabled()
    assert "Select at least two" in align.text()  # the reason is in the entry
    delete = next(a for a in shown[-1].actions() if a.text().startswith(strings.DELETE))
    assert delete.isEnabled()


def test_the_context_menu_of_a_link_and_of_the_background(win) -> None:
    v = win.view
    menu = v.build_context_menu("interface", "IF-010", QPointF())
    assert strings.CM_OPEN_PLAN in menu_texts(menu) and any(
        t.startswith(strings.DELETE) for t in menu_texts(menu)
    )
    bg = v.build_context_menu(None, None, QPointF(500, 200))
    texts = menu_texts(bg)
    assert strings.CM_ADD_HERE in texts and any(t.startswith(strings.A_SELECT_ALL) for t in texts)
    assert any(t.startswith(strings.A_FIND) for t in texts)


def test_add_unit_here_puts_the_unit_where_the_menu_was_opened(win) -> None:
    v = win.view
    bg = v.build_context_menu(None, None, QPointF(1270, 900))
    add = next(a for a in bg.actions() if a.text() == strings.CM_ADD_HERE).menu()
    before = set(win.ctl.project.units)
    next(a for a in add.actions() if a.text() == edit.TEMPLATES["sensor"].label).trigger()
    new = (set(win.ctl.project.units) - before).pop()
    x, y = edit.position_of(win.ctl.project, new)
    assert abs(x - (1270 - 120)) <= 10 and abs(y - 900) <= 5


def test_a_disabled_entry_says_why_in_a_read_only_project(win) -> None:
    win.ctl.project.read_only = True
    win.ctl.stateChanged.emit()
    menu = win.view.build_context_menu(None, None, QPointF(10, 10))
    add = next(a for a in menu.actions() if a.text().startswith(strings.CM_ADD_HERE))
    assert strings.WHY_READ_ONLY in add.text()
    unit = win.view.build_context_menu("unit", "RW1", QPointF(10, 10))
    delete = next(a for a in unit.actions() if a.text().startswith(strings.DELETE))
    assert not delete.isEnabled() and strings.WHY_READ_ONLY in delete.text()


# ---- CV-13 search ----------------------------------------------------------------------------------


def test_find_matches_id_name_connector_and_type(win) -> None:
    p = win.ctl.project
    assert ("unit", "RW1") in find_matches(p, "rw1")
    first = next(iter(p.units.values()))
    assert ("unit", first.id) in find_matches(p, first.name.split()[0])
    conn = next(c for c in p.connectors.values() if c.role == "box" and c.unit_id)
    assert ("unit", conn.unit_id) in find_matches(p, conn.id)
    assert any(k == "interface" for k, _ in find_matches(p, "can"))
    assert find_matches(p, "no such thing xyz") == [] and find_matches(p, "  ") == []
    both = find_matches(p, "rw1 power")
    assert both and all(k == "interface" or i == "RW1" for k, i in both)


def test_ctrl_f_marks_every_match_and_enter_centres_on_each_in_turn(win) -> None:
    v = win.view
    v.zoom_100()
    v.setFocus()
    QTest.keyClick(v, Qt.Key.Key_F, Qt.KeyboardModifier.ControlModifier)
    assert v.search.isVisible() and v.search.edit.hasFocus()
    QTest.keyClicks(v.search.edit, "rw")
    marked = {k for k, state in v.dscene._highlight.items() if state}
    assert {("unit", "RW1"), ("unit", "RW2"), ("unit", "RW3"), ("unit", "RW4")} <= marked
    n = len(v.search.matches)
    assert v.search.count.text() == f"1 of {n}"
    centres = []
    for _ in range(3):
        QTest.keyClick(v.search.edit, Qt.Key.Key_Return)
        kind, ident = v.search.matches[v.search.index]
        item = v.dscene.unit_items.get(ident) if kind == "unit" else None
        if item is not None:
            centre = v.mapToScene(v.viewport().rect().center())
            assert (centre - item.sceneBoundingRect().center()).manhattanLength() < 220
        centres.append(ident)
    assert len(set(centres)) == 3 and v.search.count.text().startswith("4 of")
    QTest.keyClick(v.search.edit, Qt.Key.Key_Return, Qt.KeyboardModifier.ShiftModifier)
    assert v.search.index == 2
    QTest.keyClick(v.search.edit, Qt.Key.Key_Escape)
    assert not v.search.isVisible() and not any(v.dscene._highlight.values())


def test_search_finds_a_link_and_centres_on_its_label(win) -> None:
    v = win.view
    v.zoom_100()
    v.search.open_bar()
    v.search.edit.setText("IF-044")
    kind, ident = v.search.matches[v.search.index]
    assert (kind, ident) == ("interface", "IF-044")
    chip = v.dscene.chip_rect("IF-044").center()
    assert (v.mapToScene(v.viewport().rect().center()) - chip).manhattanLength() < 60


def test_go_to_centres_on_units_and_links(win) -> None:
    v = win.view
    v.zoom_100()
    win.show_object("RW4")
    centre = v.mapToScene(v.viewport().rect().center())
    assert (
        centre - v.dscene.unit_items["RW4"].sceneBoundingRect().center()
    ).manhattanLength() < 150
    win.show_object("IF-044")
    centre = v.mapToScene(v.viewport().rect().center())
    assert (centre - v.dscene.chip_rect("IF-044").center()).manhattanLength() < 60
    assert v.dscene.focusItem() is v.dscene.link_items["IF-044"]


# ---- CV-14 clickable link labels --------------------------------------------------------------------


def test_every_link_label_selects_its_own_link(win) -> None:
    v = win.view
    v.zoom_100()
    wrong = []
    for iid in sorted(v.dscene.link_items):
        chip = v.dscene.chip_rect(iid)
        win.ctl.select(None)
        v.centerOn(chip.center())
        QApplication.processEvents()
        QTest.mouseClick(
            v.viewport(), LEFT, Qt.KeyboardModifier.NoModifier, v.mapFromScene(chip.center())
        )
        if not (win.ctl.selection and win.ctl.selection.id == iid):
            wrong.append(iid)
    assert wrong == []


def test_the_label_is_part_of_the_links_shape_and_a_selected_link_lies_on_top(win) -> None:
    link = win.view.dscene.link_items["IF-010"]
    chip = win.view.dscene.chip_rect("IF-010")
    assert link.shape().contains(chip.center())
    win.ctl.select("interface", "IF-010")
    assert link.zValue() > max(
        other.zValue() for iid, other in win.view.dscene.link_items.items() if iid != "IF-010"
    )


# ---- CV-15 legend ----------------------------------------------------------------------------------


def test_the_legend_is_a_collapsible_overlay_listing_only_what_is_present(plain) -> None:
    win = plain
    labels = {label for _k, _p, label in win.legend._entries()}
    assert strings.REDUNDANT not in labels  # the sample has no redundant chain
    assert strings.AUTO_LEGEND not in labels
    win.ctl.redundant_copy("OBC")
    labels = {label for _k, _p, label in win.legend._entries()}
    assert strings.REDUNDANT in labels and strings.NOMINAL in labels
    assert win.view.legend.parentWidget() is win.view
    was_open = win.view.legend.is_open
    win.view.legend.toggle.click()
    assert win.view.legend.is_open != was_open
    assert win.view.legend.bar.isVisibleTo(win.view.legend) == (not was_open)


def test_view_show_legend_hides_it_and_is_remembered(plain, qtbot, tmp_path) -> None:
    win = plain
    assert win.view.legend.isVisibleTo(win.view)
    win.act_legend.setChecked(False)
    win._toggle_legend()
    assert not win.view.legend.isVisibleTo(win.view)
    assert win.settings.value("ui/legend", True, bool) is False
    win.settings.sync()
    w2 = make_window(tmp_path)
    qtbot.addWidget(w2)
    assert not w2.act_legend.isChecked() and not w2.view.legend.isVisibleTo(w2.view)


# ---- CV-16 minimap ---------------------------------------------------------------------------------


def test_dragging_in_the_map_moves_the_view_along(win) -> None:
    v, m = win.view, win.view.minimap
    v.zoom_100()
    send(m, QEvent.Type.MouseButtonPress, QPoint(30, 30), LEFT)
    first = v.mapToScene(v.viewport().rect().center())
    send(m, QEvent.Type.MouseMove, QPoint(120, 90), LEFT)
    second = v.mapToScene(v.viewport().rect().center())
    assert (second - first).manhattanLength() > 100
    send(m, QEvent.Type.MouseButtonRelease, QPoint(120, 90), LEFT)


def test_the_map_of_a_big_diagram_is_not_a_black_mass(qtbot, tmp_path) -> None:
    from tools.bench_stress import build

    w = make_window(tmp_path)
    qtbot.addWidget(w)
    w.ctl._install(build(), None, None)
    QApplication.processEvents()
    img = w.view.minimap.grab().toImage()
    dark = 0
    total = img.width() * img.height()
    bg = img.pixelColor(2, 2).lightness()
    for x in range(img.width()):
        for y in range(img.height()):
            if img.pixelColor(x, y).lightness() < bg * 0.35:
                dark += 1
    assert dark / total < 0.25, dark / total


# ---- CV-17 grid and snap ---------------------------------------------------------------------------


def test_the_grid_shows_from_half_scale_and_snap_can_be_switched_off(win) -> None:
    v = win.view
    v.zoom_100()
    on = v.viewport().grab().toImage()
    win.act_snap.setChecked(False)
    win._toggle_snap()
    off = v.viewport().grab().toImage()
    assert on != off  # the dots are gone
    win._toggle_snap()
    win.act_snap.setChecked(True)
    win._toggle_snap()
    v.zoom_by(0.3 / v.zoom_scale())
    low = v.viewport().grab().toImage()
    win.act_snap.setChecked(False)
    win._toggle_snap()
    assert low == v.viewport().grab().toImage()  # below half scale there is no grid either way


def drag_unit(win, uid, dx, dy) -> None:
    v = win.view
    start = unit_point(win, uid)
    QTest.mousePress(v.viewport(), LEFT, pos=start)
    QTest.mouseMove(v.viewport(), pos=start + QPoint(dx // 2, dy // 2))
    QTest.mouseMove(v.viewport(), pos=start + QPoint(dx, dy))
    QTest.mouseRelease(v.viewport(), LEFT, pos=start + QPoint(dx, dy))


def test_snap_to_grid_is_a_setting_and_alt_bypasses_it(win, monkeypatch) -> None:
    win.view.zoom_100()
    drag_unit(win, "RW1", 7, 13)
    x, y = edit.position_of(win.ctl.project, "RW1")
    assert x % 10 == 0 and y % 10 == 0
    win.act_snap.setChecked(False)
    win._toggle_snap()
    drag_unit(win, "RW2", 7, 13)
    x, y = edit.position_of(win.ctl.project, "RW2")
    assert x % 10 != 0 or y % 10 != 0
    win.act_snap.setChecked(True)
    win._toggle_snap()
    monkeypatch.setattr(
        QApplication,
        "keyboardModifiers",
        staticmethod(lambda: Qt.KeyboardModifier.AltModifier),
    )
    drag_unit(win, "RW3", 7, 13)
    x, y = edit.position_of(win.ctl.project, "RW3")
    assert x % 10 != 0 or y % 10 != 0


# ---- CV-18 delete questions and the shortcut -------------------------------------------------------


def test_deleting_an_interface_names_both_ends_and_the_plans(win) -> None:
    win.ctl.select("interface", "IF-010")
    seen: list[tuple[str, str]] = []
    DialogScript(win, lambda d: seen.append((d.windowTitle(), d.body.text())), accept=False)
    win.delete_flow()
    assert "IF-010" in win.ctl.project.interfaces  # cancelled
    title, body = seen[0]
    ends = [e.unit_id for e in win.ctl.project.interfaces["IF-010"].endpoints]
    assert all(u in body for u in ends) and "IF-010" in title
    assert "W001" in body and "wire" in body


def test_delete_works_from_the_diagram_the_tables_and_the_tree_but_not_from_other_panels(
    plain,
) -> None:
    win = plain
    DialogScript(win, accept=True)
    win.ctl.select("interface", "IF-TM-RW1")
    show_problems(win)
    win.problems.setFocus()
    QTest.keyClick(win.problems, Qt.Key.Key_Delete)
    assert "IF-TM-RW1" in win.ctl.project.interfaces  # a stray key in another panel does nothing
    win.view.setFocus()
    QTest.keyClick(win.view, Qt.Key.Key_Delete)
    assert "IF-TM-RW1" not in win.ctl.project.interfaces
    win.act_undo.trigger()
    win.show_interfaces()
    win.interface_table.view.setFocus()
    win.ctl.select("interface", "IF-TM-RW1")
    QTest.keyClick(win.interface_table.view, Qt.Key.Key_Delete)
    assert "IF-TM-RW1" not in win.ctl.project.interfaces
    win.act_undo.trigger()
    tree = win.project_tree  # and from the project tree (it took over from the Outline)
    tree.view.setCurrentIndex(tree.index_for("interface", "IF-TM-RW1"))
    win.ctl.select("interface", "IF-TM-RW1")
    tree.view.setFocus()
    QTest.keyClick(tree.view, Qt.Key.Key_Delete)
    assert "IF-TM-RW1" not in win.ctl.project.interfaces


# ---- CV-20 read-only refusals ----------------------------------------------------------------------


def test_read_only_refusals_say_why(win) -> None:
    win.ctl.project.read_only = True
    win.ctl.stateChanged.emit()
    drag_unit(win, "RW1", 0, 60)
    assert strings.READ_ONLY_REFUSAL in win.toasts.messages
    win.toasts.messages.clear()
    win.ctl.select("unit", "RW1")
    win.view.setFocus()
    QTest.keyClick(win.view, Qt.Key.Key_Delete)
    assert strings.READ_ONLY_REFUSAL in win.toasts.messages
    win.toasts.messages.clear()
    win.view.dscene.unit_items["RW1"].setFocus()
    QTest.keyClick(win.view, Qt.Key.Key_Down, Qt.KeyboardModifier.ShiftModifier)
    assert strings.READ_ONLY_REFUSAL in win.toasts.messages
    win.toasts.messages.clear()
    win.arrange_flow()
    assert strings.READ_ONLY_REFUSAL in win.toasts.messages


# ---- CV-24 dragging a unit among many ---------------------------------------------------------------


def test_dragging_draws_straight_previews_and_routes_once_on_release(win) -> None:
    v, scene = win.view, win.view.dscene
    v.zoom_100()
    v.centerOn(scene.unit_items["OBC1"])
    routed: list[int] = []
    real = scene._compute_routes

    def counting():
        routed.append(1)
        return real()

    scene._compute_routes = counting  # type: ignore[method-assign]
    start = unit_point(win, "OBC1")
    QTest.mousePress(v.viewport(), LEFT, pos=start)
    for k in range(1, 6):
        QTest.mouseMove(v.viewport(), pos=start + QPoint(0, 12 * k))
    assert routed == []  # nothing was routed while the mouse was down
    mine = scene._adj["OBC1"]
    assert mine and any(scene.link_items[i]._preview for i in mine)
    previews = [scene.link_items[i] for i in mine if scene.link_items[i]._preview]
    assert all(link.path().elementCount() == 2 for link in previews)  # a straight line
    QTest.mouseRelease(v.viewport(), LEFT, pos=start + QPoint(0, 60))
    assert routed  # the routes were worked out at the end
    assert not any(link._preview for link in scene.link_items.values())
    assert all(link.poly for link in scene.link_items.values())


def test_a_drag_that_ends_where_it_began_restores_the_routes(win) -> None:
    scene = win.view.dscene
    before = {i: list(link.poly) for i, link in scene.link_items.items()}
    start = unit_point(win, "OBC1")
    v = win.view
    QTest.mousePress(v.viewport(), LEFT, pos=start)
    QTest.mouseMove(v.viewport(), pos=start + QPoint(0, 40))
    QTest.mouseMove(v.viewport(), pos=start)
    QTest.mouseRelease(v.viewport(), LEFT, pos=start)
    assert {i: list(link.poly) for i, link in scene.link_items.items()} == before


# ---- CV-25 painting --------------------------------------------------------------------------------


def test_pens_and_fonts_are_cached_and_follow_the_theme(win) -> None:
    scene = win.view.dscene
    assert scene.pen("border", 2) is scene.pen("border", 2)
    assert scene.px_font(11) is scene.px_font(11)
    old = scene.pen("border", 2).color().name()
    win.theme.apply(QApplication.instance(), "dark")
    assert scene.pen("border", 2).color().name() != old


# ---- CV-27 arrange ---------------------------------------------------------------------------------


def test_arrange_has_a_shortcut_and_a_toolbar_button(win) -> None:
    assert win.act_arrange.shortcut().toString() == "Ctrl+Shift+L"
    assert win.arrange_btn.toolTip() == strings.ARRANGE_TIP
    win.ctl.move_units({"RW1": (900.0, 700.0)})
    depth = undo_depth(win)
    QTest.keyClick(
        win, Qt.Key.Key_L, Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier
    )
    assert undo_depth(win) == depth + 1


def test_a_big_diagram_is_arranged_in_a_worker(qtbot, tmp_path) -> None:
    from tools.bench_stress import build

    w = make_window(tmp_path)
    qtbot.addWidget(w)
    w.ctl._install(build(), None, None)
    w.ctl.move_units({"U001": (3000.0, 500.0)})
    depth = undo_depth(w)
    made: list[str] = []
    from harness_design_studio.gui import main_window

    real = main_window.ArrangeWorker.run

    def traced(self) -> None:
        made.append(self.__class__.__name__)
        real(self)

    main_window.ArrangeWorker.run = traced  # type: ignore[method-assign]
    try:
        w.arrange_flow()
    finally:
        main_window.ArrangeWorker.run = real  # type: ignore[method-assign]
    assert made == ["ArrangeWorker"] and undo_depth(w) == depth + 1


# ---- CV-28 empty states ----------------------------------------------------------------------------


def test_the_empty_diagram_and_the_diagram_without_links_say_what_to_do(qtbot, tmp_path) -> None:
    from harness_design_studio.core.samples import new_project

    w = make_window(tmp_path)
    qtbot.addWidget(w)
    w.ctl._install(new_project(), None, None)
    QApplication.processEvents()
    assert w.view.empty.isVisible()
    assert "Ctrl+K" in w.view.empty.text() and "Import" in w.view.empty.text()
    assert not w.view.empty.autoFillBackground()
    w.ctl.add_unit("computer")
    assert w.view.empty.isVisible() and "Press C to connect" in w.view.empty.text()
    w.ctl.add_unit("power")
    w.ctl.add_interface_between(next(iter(w.ctl.project.interface_types)), "OBC1", "PCDU1")
    assert not w.view.empty.isVisible()


# ---- CV-29 the numbers in one place ----------------------------------------------------------------


def test_the_canvas_numbers_live_in_one_dataclass() -> None:
    import dataclasses

    assert dataclasses.is_dataclass(CanvasMetrics) and CanvasMetrics().grid == METRICS.grid == 10
    with pytest.raises(dataclasses.FrozenInstanceError):
        METRICS.grid = 5  # type: ignore[misc]
    names = {f.name for f in dataclasses.fields(CanvasMetrics)}
    assert {"grid", "chip_h", "min_fit_scale", "minimap_size", "drag_preview_ms"} <= names


# ---- speed -----------------------------------------------------------------------------------------


@pytest.mark.perf
def test_dragging_a_unit_at_100_units_is_fast(qtbot, tmp_path) -> None:
    import time

    from tests.helpers import time_limit
    from tools.bench_stress import build

    w = make_window(tmp_path)
    qtbot.addWidget(w)
    w.ctl._install(build(), None, None)
    w.view.zoom_100()
    uid = sorted(w.ctl.project.units)[40]
    w.view.centerOn(w.view.dscene.unit_items[uid])
    QApplication.processEvents()
    start = unit_point(w, uid)
    QTest.mousePress(w.view.viewport(), LEFT, pos=start)
    QApplication.processEvents()
    spent = 0.0
    for k in range(
        1, 9
    ):  # the handler of each move, apart from the repaint (software drawing here)
        t0 = time.perf_counter()
        QTest.mouseMove(w.view.viewport(), pos=start + QPoint(0, 8 * k))
        spent += time.perf_counter() - t0
        QApplication.processEvents()
    per_move = spent / 8 * 1000
    QTest.mouseRelease(w.view.viewport(), LEFT, pos=start + QPoint(0, 64))
    assert per_move < time_limit(60), per_move  # was 400 to 1,200 ms: every link was routed
