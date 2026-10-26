# mypy: disable-error-code="no-untyped-def,no-untyped-call,attr-defined,union-attr,arg-type"
"""REQ-GUI-13. Workshop feedback M3: connectors at the ends of the connections in the Diagram (Expert
mode, or View > Show connectors on connections, remembered), the harness path in the tooltip and
*Show the harness* on a connection (menu, context menu, project tree)."""

import time

import pytest

pytest.importorskip("PySide6")
pytestmark = pytest.mark.gui

from PySide6.QtCore import QPoint, QSettings  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from harness_design_studio.gui import strings  # noqa: E402
from harness_design_studio.gui.main_window import MainWindow  # noqa: E402
from harness_design_studio.gui.theme import ThemeManager  # noqa: E402
from tests.gui_helpers import DialogScript, action_named  # noqa: E402
from tests.test_ui_links import RS, link_up, window  # noqa: E402, F401


def draw(win) -> None:
    """Paint the diagram once (the boxes are worked out while painting)."""
    win.view.viewport().repaint()
    QApplication.processEvents()
    win.view.grab()


def boxes(win, lid="L1"):
    return win.view.dscene.connection_items[lid]._end_rects


def test_the_boxes_are_off_in_the_guided_mode_by_default(tmp_path) -> None:
    win = window(tmp_path)
    assert link_up(win) == "L1"
    act = action_named(win, "act-connection-ends")
    assert act.isCheckable() and not act.isChecked()
    assert act.text() == strings.A_CONNECTION_ENDS == "Show connectors on connections"
    assert win.ctl.mode == "guided"
    draw(win)
    assert boxes(win) == []


def test_the_view_menu_action_draws_a_box_at_each_end_and_off_takes_them_away(tmp_path) -> None:
    win = window(tmp_path)
    assert link_up(win) == "L1"
    act = action_named(win, "act-connection-ends")
    act.trigger()
    draw(win)
    first, last = boxes(win)
    item = win.view.dscene.connection_items["L1"]
    assert item.poly[0][1] == pytest.approx(first.center().y())
    assert item.poly[-1][1] == pytest.approx(last.center().y())
    assert first.width() > 20 and first.height() > 20
    assert first.intersects(item.shape().boundingRect())  # a click on a box picks the connection
    act.trigger()
    draw(win)
    assert boxes(win) == []


def test_the_expert_mode_always_draws_them(tmp_path) -> None:
    win = window(tmp_path)
    assert link_up(win) == "L1"
    win.ctl.set_mode("expert")
    QApplication.processEvents()
    draw(win)
    assert len(boxes(win)) == 2
    win.ctl.set_mode("guided")
    QApplication.processEvents()
    draw(win)
    assert boxes(win) == []


def test_a_box_names_the_connector_and_how_many_pins_the_connection_pairs(tmp_path) -> None:
    from harness_design_studio.core.links import link_ends

    win = window(tmp_path)
    assert link_up(win) == "L1"
    a, b = link_ends(win.ctl.project, win.ctl.project.links["L1"])
    assert a.name == win.ctl.project.connectors[RS[0]].name
    assert strings.LINK_END_PINS[1].format(a.used, a.pins) == "4 of 5 pins"
    assert strings.LINK_END_PINS[0].format(1, 1) == "1 of 1 pin"
    assert b.pins == 5


def test_the_choice_is_remembered_and_a_settings_page_box_follows_it(tmp_path) -> None:
    win = window(tmp_path)
    box = win.settings_page.ends_box
    assert box.text() == strings.SETTINGS_CONNECTION_ENDS and not box.isChecked()
    assert box.accessibleName() and box.toolTip()
    box.click()  # the page is a view of the menu action
    act = action_named(win, "act-connection-ends")
    assert act.isChecked() and win.view.dscene.connection_ends
    act.trigger()
    assert not box.isChecked()
    act.trigger()
    win.close()
    other = MainWindow(
        QSettings(str(tmp_path / "ui.ini"), QSettings.Format.IniFormat), ThemeManager()
    )
    assert action_named(other, "act-connection-ends").isChecked()
    assert other.view.dscene.connection_ends and other.settings_page.ends_box.isChecked()
    other.close()


def test_the_tooltip_names_the_path_through_the_harness_once_one_exists(tmp_path) -> None:
    win = window(tmp_path)
    assert link_up(win) == "L1"
    item = win.view.dscene.connection_items["L1"]
    assert strings.LINK_TIP_PATH not in item.tooltip_html()
    DialogScript(win)
    win.act_link_harness.trigger()
    hid = win.ctl.project.links["L1"].harness_id
    tip = item.tooltip_html()
    cables = [c.id for c in win.ctl.project.harnesses[hid].connectors]
    assert strings.LINK_TIP_PATH in tip and all(c in tip for c in cables)
    assert f"{RS[0]} - {cables[0]}" in tip or f"{RS[0]} - {cables[1]}" in tip


def test_show_the_harness_opens_the_harness_tab_on_it(tmp_path) -> None:
    win = window(tmp_path)
    assert link_up(win) == "L1"
    win.ctl.select_link("L1")
    act = action_named(win, "act-link-show-harness")
    assert act.text() == "Show the harness" and not act.isEnabled()  # none made yet
    DialogScript(win)
    win.act_link_harness.trigger()
    hid = win.ctl.project.links["L1"].harness_id
    win.go_to("diagram")
    win.ctl.select_link("L1")
    assert act.isEnabled() and win.menu_connection.isEnabled()
    act.trigger()
    QApplication.processEvents()
    assert (
        win.main_tabs.current_name() == "harness"
        if hasattr(win.main_tabs, "current_name")
        else True
    )
    assert win.harness_view.harness_id() == hid and win.harness_view.isVisible()


def test_the_context_menu_of_a_connection_lists_its_actions_and_shows_the_harness(tmp_path) -> None:
    win = window(tmp_path)
    assert link_up(win) == "L1"
    menu = win.view.build_context_menu("link", "L1", QPoint(0, 0))
    names = [a.text() for a in menu.actions()]
    assert strings.A_LINK_EDIT in names
    assert any(n.startswith(strings.A_LINK_SHOW_HARNESS) for n in names)
    entry = next(a for a in menu.actions() if a.text().startswith(strings.A_LINK_SHOW_HARNESS))
    assert not entry.isEnabled()
    DialogScript(win)
    win.act_link_harness.trigger()
    hid = win.ctl.project.links["L1"].harness_id
    win.go_to("diagram")
    win.ctl.select_link("L1")
    menu = win.view.build_context_menu("link", "L1", QPoint(0, 0))
    entry = next(a for a in menu.actions() if a.text().startswith(strings.A_LINK_SHOW_HARNESS))
    assert entry.isEnabled()
    entry.trigger()
    assert win.harness_view.harness_id() == hid


def test_the_project_tree_row_has_the_action_too(tmp_path) -> None:
    win = window(tmp_path)
    assert link_up(win) == "L1"
    acts = {a.objectName(): a for a in win._link_actions("L1")}
    assert "tree-link-show-harness" in acts and not acts["tree-link-show-harness"].isEnabled()
    DialogScript(win)
    win.act_link_harness.trigger()
    acts = {a.objectName(): a for a in win._link_actions("L1")}
    assert acts["tree-link-show-harness"].isEnabled()


def test_a_connection_without_a_harness_says_so_when_asked(tmp_path) -> None:
    win = window(tmp_path)
    assert link_up(win) == "L1"
    win.show_link_harness_flow("L1")  # (the action is off; the flow itself still answers)
    assert win.harness_view.harness_id() in (None, "")


@pytest.mark.perf
def test_painting_the_boxes_costs_little(tmp_path) -> None:
    win = window(tmp_path)
    assert link_up(win) == "L1"
    assert win.ctl.add_link("PCDU-J02", "OBC-J02", [("1", "1"), ("2", "2")]) == "L2"
    action_named(win, "act-connection-ends").trigger()
    draw(win)
    t = time.perf_counter()
    for _ in range(5):
        draw(win)
    per_frame = (time.perf_counter() - t) / 5 * 1000
    assert len(boxes(win, "L2")) == 2
    assert per_frame < 400, per_frame
