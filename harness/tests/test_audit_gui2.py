"""Regression tests for the canvas, legend, tour and panel findings of the October audit (F2-*)."""

import pytest

pytest.importorskip("PySide6")
pytestmark = pytest.mark.gui

from PySide6.QtCore import QEvent, QPoint, QRectF, QSizeF, Qt  # noqa: E402
from PySide6.QtGui import QFont, QFontMetrics, QKeyEvent  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from harness_design_studio.core import edit  # noqa: E402
from harness_design_studio.core.samples import mini3, sat15  # noqa: E402
from harness_design_studio.gui import canvas, strings  # noqa: E402
from harness_design_studio.gui.main_window import MainWindow  # noqa: E402
from tests.gui_helpers import make_window, unit_point  # noqa: E402


@pytest.fixture
def win(qtbot, tmp_path):  # type: ignore[no-untyped-def]
    w = make_window(tmp_path)
    qtbot.addWidget(w)
    w.ctl._install(mini3(), None, None)
    QApplication.processEvents()
    return w


def _drag(win: MainWindow, unit_id: str, dx: int, dy: int) -> None:
    view = win.view.viewport()
    start = unit_point(win, unit_id)
    QTest.mousePress(view, Qt.MouseButton.LeftButton, pos=start)
    QTest.mouseMove(view, pos=start + QPoint(dx // 2, dy // 2))
    QTest.mouseMove(view, pos=start + QPoint(dx, dy))
    QTest.mouseRelease(view, Qt.MouseButton.LeftButton, pos=start + QPoint(dx, dy))
    QApplication.processEvents()


def _rect(win: MainWindow, unit_id: str) -> QRectF:
    item = win.view.dscene.unit_items[unit_id]
    return QRectF(item.pos(), QSizeF(canvas.W, item.height()))


# ---- F2-4 ---------------------------------------------------------------------------------------


def test_the_legend_is_redrawn_when_the_last_link_of_a_kind_goes_and_comes_back(win) -> None:  # type: ignore[no-untyped-def]
    calls: list[int] = []
    real = win.legend.update

    def spy() -> None:
        calls.append(1)
        real()

    win.legend.update = spy  # type: ignore[method-assign,assignment]
    win.ctl.select("interface", "IF-TM-RW1")  # the only RS-422 link
    assert win.ctl.delete_selected()
    assert calls
    assert "RS-422" not in [label for _k, _p, label in win.legend._entries()]
    calls.clear()
    win.ctl.undo()
    assert calls
    assert "RS-422" in [label for _k, _p, label in win.legend._entries()]


# ---- F2-5 ---------------------------------------------------------------------------------------


def test_the_outline_drops_its_highlighted_row_when_the_selection_is_cleared(win) -> None:  # type: ignore[no-untyped-def]
    win.tabs.setCurrentWidget(win.outline)
    QApplication.processEvents()
    win.ctl.select("unit", "OBC")
    assert len(win.outline.tree.selectedItems()) == 1
    win.ctl.select(None)
    assert win.outline.tree.selectedItems() == []


# ---- F2-6 ---------------------------------------------------------------------------------------


def test_a_unit_dragged_off_the_top_left_stays_in_the_scene(win) -> None:  # type: ignore[no-untyped-def]
    _drag(win, "RW1", -3000, -2000)
    item = win.view.dscene.unit_items["RW1"]
    assert item.pos().x() >= 0 and item.pos().y() >= 0
    assert win.view.scene().sceneRect().contains(_rect(win, "RW1"))
    x, y = edit.position_of(win.ctl.project, "RW1")
    assert x >= 0 and y >= 0  # what is saved is what is drawn


def test_a_unit_dropped_far_right_and_down_is_inside_the_scene_rectangle(win) -> None:  # type: ignore[no-untyped-def]
    win.ctl.move_unit("RW1", 9000.0, 7000.0)
    QApplication.processEvents()
    assert win.view.scene().sceneRect().contains(_rect(win, "RW1"))


def test_a_unit_with_a_negative_saved_position_is_still_reachable(win) -> None:  # type: ignore[no-untyped-def]
    win.ctl.move_unit("RW1", -400.0, -300.0)  # (a file edited by hand, or an older version)
    QApplication.processEvents()
    assert win.view.scene().sceneRect().contains(_rect(win, "RW1"))
    assert edit.position_of(win.ctl.project, "RW1") == (
        win.view.dscene.unit_items["RW1"].pos().x(),
        win.view.dscene.unit_items["RW1"].pos().y(),
    )


def test_nudging_a_unit_with_the_keyboard_stops_at_the_edge(win) -> None:  # type: ignore[no-untyped-def]
    win.ctl.move_unit("RW1", 0.0, 0.0)
    item = win.view.dscene.unit_items["RW1"]
    item.setFocus()
    event = QKeyEvent(
        QEvent.Type.KeyPress, Qt.Key.Key_Left, Qt.KeyboardModifier.ShiftModifier, "", False, 1
    )
    item.keyPressEvent(event)
    assert edit.position_of(win.ctl.project, "RW1")[0] >= 0


# ---- F2-7 ---------------------------------------------------------------------------------------


def test_the_tour_skips_steps_whose_target_is_not_on_screen(win) -> None:  # type: ignore[no-untyped-def]
    win.palette_panel.hide()  # what a high UI scale does to the left dock
    win.tour.start()
    seen: list[str] = []
    for _ in range(10):
        if not win.tour.active:
            break
        key = strings.TOUR_STEPS[win.tour.index][0]
        target = win.tour.targets[key]
        assert target.isVisibleTo(win), key
        seen.append(key)
        win.tour.next.click()
    assert seen and "palette" not in seen and "types" not in seen
    assert not win.tour.active


def test_the_tour_counts_only_the_steps_it_shows(win) -> None:  # type: ignore[no-untyped-def]
    win.palette_panel.hide()
    win.tour.start()
    assert "Step 1 of 3" in win.tour.title.text()
    win.tour.skip.click()


def test_starting_the_tour_on_a_window_that_is_gone_does_nothing(tmp_path) -> None:  # type: ignore[no-untyped-def]
    w = make_window(tmp_path)
    QApplication.processEvents()  # (let the start-up timers run first)
    tour = w.tour
    w.close()
    w.deleteLater()
    QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    tour.start()  # (the 200 ms timer of the first run can fire after the window is deleted)
    assert not tour.active


def test_starting_the_tour_on_a_closed_window_does_nothing(win) -> None:  # type: ignore[no-untyped-def]
    win.close()
    win.tour.start()
    assert not win.tour.active


# ---- F2-12 --------------------------------------------------------------------------------------


def test_dragging_a_unit_with_the_connect_tool_does_not_move_it(win) -> None:  # type: ignore[no-untyped-def]
    win.ctl.begin_connect("rs422")
    before = edit.position_of(win.ctl.project, "RW1")
    revision = win.ctl.history.revision
    _drag(win, "RW1", 110, 110)
    item = win.view.dscene.unit_items["RW1"]
    assert (item.pos().x(), item.pos().y()) == before
    assert edit.position_of(win.ctl.project, "RW1") == before
    assert win.ctl.history.revision == revision


# ---- F2-13 --------------------------------------------------------------------------------------


def test_expert_mode_grows_the_scene_to_hold_the_taller_units(win) -> None:  # type: ignore[no-untyped-def]
    win.ctl._install(sat15(), None, None)
    win.ctl.set_mode("expert")
    QApplication.processEvents()
    for uid in win.view.dscene.unit_items:
        assert win.view.scene().sceneRect().contains(_rect(win, uid)), uid
    win.ctl.set_mode("guided")
    QApplication.processEvents()
    for uid in win.view.dscene.unit_items:
        assert win.view.scene().sceneRect().contains(_rect(win, uid)), uid


# ---- F2-14 --------------------------------------------------------------------------------------


def test_the_label_registry_follows_the_numbers_of_an_edited_link(win) -> None:  # type: ignore[no-untyped-def]
    scene = win.view.dscene
    before = scene._chip_rects["IF-PWR-RW1"].width()
    assert win.ctl.update_interface("IF-PWR-RW1", voltage_v=28.5, max_current_a=123.456)
    after = scene._chip_rects["IF-PWR-RW1"].width()
    assert after > before + 40  # the numbers need room: the overlap check must know
    win.ctl.undo()
    assert scene._chip_rects["IF-PWR-RW1"].width() == before


# ---- F2-8 ---------------------------------------------------------------------------------------


def test_long_ids_and_connector_names_are_elided_with_an_ellipsis() -> None:
    font = QFont()
    font.setPixelSize(11)
    fm = QFontMetrics(font)
    long_id = "OBC-" + "X" * 40
    shown = canvas.elide(fm, long_id, canvas.W - 80)
    assert shown.endswith("…") and fm.horizontalAdvance(shown) <= canvas.W - 80
    name = "Backplane-Telemetry-Primary-J01"
    shown = canvas.elide(fm, name, 24.0, middle=True)
    assert "…" in shown and fm.horizontalAdvance(shown) <= 24
    assert canvas.elide(fm, "J01", 24.0, middle=True) == "J01"
    assert canvas.elide(fm, "OBC1", canvas.W - 80) == "OBC1"


# ---- F2-10 --------------------------------------------------------------------------------------


def test_a_newline_in_a_name_typed_into_the_table_is_refused(win) -> None:  # type: ignore[no-untyped-def]
    win.table.refresh()
    model = win.table.model
    messages: list[str] = []
    win.ctl.message.connect(lambda text, ok: messages.append(text))
    iid = model.ids[0]
    name = win.ctl.project.interfaces[iid].name
    revision = win.ctl.history.revision
    assert model.setData(model.index(0, 1), "line1\nline2") is False
    assert win.ctl.project.interfaces[iid].name == name
    assert win.ctl.history.revision == revision
    assert strings.NAME_ONE_LINE in messages
    assert model.setData(model.index(0, 1), "one line") is True
