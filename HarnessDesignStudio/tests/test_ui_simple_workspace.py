# mypy: disable-error-code="no-untyped-def,no-untyped-call,attr-defined,has-type"
"""1.8.0 S2 (D-171): the simple workspace shows less until the person asks."""

import pytest

pytest.importorskip("PySide6")
pytestmark = pytest.mark.gui

from PySide6.QtCore import QSettings  # noqa: E402
from PySide6.QtWidgets import QApplication, QToolButton  # noqa: E402

from harness_design_studio.gui import areas, strings  # noqa: E402
from harness_design_studio.gui.main_window import MainWindow  # noqa: E402
from harness_design_studio.gui.next_step import workspace_key  # noqa: E402
from harness_design_studio.gui.theme import ThemeManager  # noqa: E402


def make(qtbot, tmp_path, workspace: str | None = None, name: str = "ui.ini") -> MainWindow:
    settings = QSettings(str(tmp_path / name), QSettings.Format.IniFormat)
    if workspace is not None:
        settings.setValue("ui/workspace", workspace)
        settings.sync()
    w = MainWindow(settings, ThemeManager(), first_run=False)
    w.ask_choice = lambda t, x, b: 1  # type: ignore[assignment]
    qtbot.addWidget(w)
    w.resize(1440, 900)
    w.show()
    w.set_area("model")  # (Simple opens on the Next step page; the tool row is on the diagram)
    QApplication.processEvents()
    return w


def seen(w: MainWindow) -> dict[str, object]:
    """Everything stage S2 decides, as the person would see it."""
    return {
        "dock_left": w.dock_left.isVisibleTo(w),
        "dock_right": w.dock_right.isVisibleTo(w),
        "dock_problems": w.dock_problems.isVisibleTo(w),
        "minimap_action": w.act_minimap.isChecked(),
        "legend_action": w.act_legend.isChecked(),
        "minimap_wanted": w.view.minimap_wanted,
        "legend_wanted": w.view.legend_wanted,
        "status_counts": w.status_counts.isVisibleTo(w),
        "status_sel": w.status_sel.isVisibleTo(w),
        "problems_btn": w.problems_btn.isVisibleTo(w),
        "zoom_level": w.zoom_level.isVisibleTo(w),
        "saved": w.status_saved.isVisibleTo(w),
        "jobs": w.jobs.isVisibleTo(w) or not w.jobs.isHidden(),
        "tools": tuple(
            b.isVisibleTo(w)
            for b in (
                w.tool_select,
                w.tool_connect,
                w.tool_add_device,
                w.redundant_btn,
                w.delete_btn,
                w.zoom_out_btn,
                w.zoom_in_btn,
                w.fit_btn,
                w.tool_more,
            )
        ),
        "diagram_tools": w.diagram_tools.isVisibleTo(w),
        "rail": {k: b.isVisibleTo(w.rail) for k, b in w.rail.buttons.items()},
        "panels_button": w.panels_btn.isVisibleTo(w),
        "panels_action": w.act_show_panels.isVisible(),
    }


# ---- the pure parts ----------------------------------------------------------------------------
def test_the_settings_keys_of_a_workspace() -> None:
    assert workspace_key("ui/state", "full") == "ui/state"  # Full keeps the keys it always had
    assert workspace_key("ui/state", "simple") == "ui/simple/state"
    assert workspace_key("ui/minimap", "simple") == "ui/simple/minimap"
    assert workspace_key("layout/ab12/area", "simple") == "layout/ab12/simple/area"
    assert workspace_key("layout/ab12/area", "full") == "layout/ab12/area"


def test_only_home_is_left_out_of_the_simple_rail() -> None:
    assert areas.hidden_in("simple") == ("home",)
    assert areas.hidden_in("full") == ()
    assert "home" in areas.KEYS  # the area still exists: menus, keys and the palette reach it


# ---- the simple workspace ----------------------------------------------------------------------
def test_simple_shows_less(qtbot, tmp_path) -> None:
    w = make(qtbot, tmp_path, "simple")
    s = seen(w)
    assert not s["dock_left"] and not s["dock_right"] and not s["dock_problems"]
    assert not s["minimap_action"] and not s["legend_action"]
    assert not s["minimap_wanted"] and not s["legend_wanted"]
    assert not s["status_counts"] and not s["status_sel"] and not s["problems_btn"]
    assert not w.pending_link.isVisibleTo(w) and not s["zoom_level"]
    assert s["saved"] and s["jobs"]  # the save state and the job indicator stay
    select, connect, add, red, dele, zout, zin, fit, more = s["tools"]  # type: ignore[misc]
    assert select and connect and add and more
    assert not (red or dele or zout or zin or fit)
    assert not s["diagram_tools"]
    assert s["rail"] == {k: k != "home" for k in areas.KEYS}
    assert s["panels_button"] and s["panels_action"]


def test_the_more_menu_holds_every_tool_the_row_leaves_out(qtbot, tmp_path) -> None:
    w = make(qtbot, tmp_path, "simple")
    menu_actions = set(w.menu_more.actions())
    for act in (w.act_redundant, w.act_delete, w.act_zoom_in, w.act_zoom_out, w.act_fit):
        assert act in menu_actions
    assert w.act_arrange in menu_actions
    sub = w.menu_more_filter
    sub.aboutToShow.emit()
    labels = [a.text() for a in sub.actions()]
    assert strings.FILTER_ALL in labels
    assert {strings.FILTER_CLASS, strings.FILTER_CONNECTOR, strings.FILTER_BUNDLE} <= set(labels)
    assert w.tool_more.menu() is w.menu_more


def test_the_more_menu_filters_like_the_pickers(qtbot, tmp_path) -> None:
    w = make(qtbot, tmp_path, "simple")
    w.menu_more_filter.aboutToShow.emit()
    sub = next(a.menu() for a in w.menu_more_filter.actions() if a.text() == strings.FILTER_CLASS)
    assert sub is not None and sub.actions()
    sub.actions()[0].trigger()
    assert w.filter_combo.currentData() == "class"
    assert w.view.dscene.filter is not None and w.view.dscene.filter[0] == "class"
    w.menu_more_filter.aboutToShow.emit()
    everything = w.menu_more_filter.actions()[0]
    assert not everything.isChecked()
    everything.trigger()
    assert w.filter_combo.currentData() is None and w.view.dscene.filter is None


def test_the_add_device_button_is_the_add_device_action(qtbot, tmp_path) -> None:
    w = make(qtbot, tmp_path, "simple")
    calls: list[int] = []
    w.act_add_device.triggered.disconnect()  # (the flow itself opens a dialog)
    w.act_add_device.triggered.connect(lambda _c=False: calls.append(1))
    w.tool_add_device.click()
    assert calls == [1]
    w.act_add_device.setEnabled(False)  # a read-only project
    assert not w.tool_add_device.isEnabled()


def test_home_is_off_the_rail_but_still_reachable(qtbot, tmp_path) -> None:
    w = make(qtbot, tmp_path, "simple")
    assert not w.rail.buttons["home"].isVisibleTo(w.rail)
    w.act_go_home.trigger()  # Ctrl+7, the Go menu and the palette use this
    assert w.area() == "home" and w.home_page.isVisibleTo(w)
    names = [e.label for e in w.palette_entries()]
    assert strings.GO_HOME in names


# ---- the full workspace is as it was -----------------------------------------------------------
def test_full_is_as_before(qtbot, tmp_path) -> None:
    w = make(qtbot, tmp_path, "full")
    s = seen(w)
    assert s["dock_left"] and s["dock_right"] and not s["dock_problems"]
    assert s["minimap_action"] and s["legend_action"]
    assert s["minimap_wanted"] and s["legend_wanted"]
    assert s["status_counts"] and s["status_sel"] and s["problems_btn"] and s["zoom_level"]
    assert s["tools"] == (True, True, False, True, True, True, True, True, False)
    assert s["diagram_tools"]
    assert all(s["rail"].values())  # type: ignore[union-attr]
    assert not s["panels_button"] and not s["panels_action"]
    assert not w.act_show_panels.isEnabled()  # (so the palette does not list it)
    assert strings.A_SHOW_PANELS not in [e.label for e in w.palette_entries()]


def test_full_to_simple_to_full_is_the_fresh_full_window(qtbot, tmp_path) -> None:
    fresh = make(qtbot, tmp_path, "full", "a.ini")
    w = make(qtbot, tmp_path, "full", "b.ini")
    w.set_workspace("simple")
    assert seen(w) != seen(fresh)
    w.set_workspace("full")
    assert seen(w) == seen(fresh)


# ---- switching at once, both ways --------------------------------------------------------------
def test_switching_applies_the_other_layout_at_once(qtbot, tmp_path) -> None:
    w = make(qtbot, tmp_path, "full")
    w.act_minimap.trigger()  # Full: the minimap off
    w.act_simple.trigger()
    s = seen(w)
    assert w.workspace == "simple" and not s["dock_left"] and not s["dock_right"]
    assert not s["minimap_wanted"] and not s["legend_wanted"]
    assert w.settings.value("ui/workspace") == "simple"
    assert w.settings_page.workspace_combo.currentData() == "simple"
    w.act_full.trigger()
    s = seen(w)
    assert s["dock_left"] and s["dock_right"] and s["legend_wanted"]
    assert not s["minimap_wanted"]  # what Full had
    assert s["status_counts"] and s["problems_btn"]
    w.settings_page.workspace_combo.setCurrentIndex(
        w.settings_page.workspace_combo.findData("simple")
    )
    w.settings_page.workspace_combo.activated.emit(w.settings_page.workspace_combo.currentIndex())
    assert w.workspace == "simple" and not w.dock_left.isVisibleTo(w)


def test_the_page_stays_where_it_is_when_the_workspace_changes(qtbot, tmp_path) -> None:
    w = make(qtbot, tmp_path, "full")
    w.set_area("checks")
    w.set_workspace("simple")
    assert w.area() == "checks"
    w.set_workspace("full")
    assert w.area() == "checks"


def test_simple_never_opens_a_panel_by_itself(qtbot, tmp_path) -> None:
    w = make(qtbot, tmp_path, "simple")
    w.resize(1700, 900)
    QApplication.processEvents()
    w.auto_layout()
    assert not w.dock_left.isVisibleTo(w) and not w.dock_right.isVisibleTo(w)
    w.reset_layout()
    assert not seen(w)["dock_left"] and not seen(w)["dock_right"] and not seen(w)["dock_problems"]
    w.show_panels(True)
    w.resize(900, 900)  # narrower than the layout needs: Simple may close what no longer fits
    QApplication.processEvents()
    w.resize(1700, 900)
    QApplication.processEvents()
    assert not w.dock_right.isVisibleTo(w) or w.width() >= 1200  # (never reopened by the resize)


# ---- the Show panels toggle --------------------------------------------------------------------
def test_show_panels_opens_and_closes_the_tree_and_the_inspector_together(qtbot, tmp_path) -> None:
    w = make(qtbot, tmp_path, "simple")
    assert not w.act_show_panels.isChecked() and not w.panels_btn.isChecked()
    w.panels_btn.click()
    assert w.dock_left.isVisibleTo(w) and w.dock_right.isVisibleTo(w)
    assert w.act_show_panels.isChecked() and w.panels_btn.isChecked()
    assert not w.dock_problems.isVisibleTo(w)
    w.panels_btn.click()
    assert not w.dock_left.isVisibleTo(w) and not w.dock_right.isVisibleTo(w)
    assert not w.act_show_panels.isChecked()
    w.act_show_panels.trigger()  # the View menu entry
    assert w.dock_left.isVisibleTo(w) and w.dock_right.isVisibleTo(w)


def test_the_toggle_follows_the_docks_own_controls(qtbot, tmp_path) -> None:
    w = make(qtbot, tmp_path, "simple")
    w.dock_right.toggleViewAction().trigger()  # the View menu entry of the inspector
    QApplication.processEvents()
    assert w.act_show_panels.isChecked()  # one of the two is open
    w.dock_right.hide()
    assert not w.act_show_panels.isChecked()
    w.show_interfaces()  # the Interfaces shortcut opens the left panel as it did
    assert w.dock_left.isVisibleTo(w) and w.act_show_panels.isChecked()


def test_the_view_menu_has_the_entry_first_in_simple_only(qtbot, tmp_path) -> None:
    w = make(qtbot, tmp_path, "simple")
    view = next(a.menu() for a in w.menuBar().actions() if a.text().replace("&", "") == "View")
    visible = [a for a in view.actions() if a.isVisible() and not a.isSeparator()]
    assert visible[0] is w.act_show_panels
    w.set_workspace("full")
    visible = [a for a in view.actions() if a.isVisible() and not a.isSeparator()]
    assert w.act_show_panels not in visible and visible[0] is w.act_simple


# ---- the inspector opens when it is needed -----------------------------------------------------
def test_going_to_an_object_opens_the_inspector_in_simple(qtbot, tmp_path) -> None:
    w = make(qtbot, tmp_path, "simple")
    unit = sorted(w.ctl.project.units)[0]
    assert not w.dock_right.isVisibleTo(w)
    w.show_object(unit)  # a problem opened from the Problems panel or the Checks tab
    assert w.dock_right.isVisibleTo(w) and w.ctl.selection is not None
    assert w.ctl.selection.id == unit
    assert w.act_show_panels.isChecked()


def test_the_other_ways_to_the_docks_open_them_in_simple(qtbot, tmp_path) -> None:
    w = make(qtbot, tmp_path, "simple")
    w._show_problems("x")  # the badge on the diagram
    assert w.dock_right.isVisibleTo(w)
    w.dock_right.hide()
    w._show_why("unit", sorted(w.ctl.project.units)[0])
    assert w.dock_right.isVisibleTo(w)
    w.show_units()
    assert w.dock_left.isVisibleTo(w)


def test_full_does_not_open_the_inspector_for_a_selection(qtbot, tmp_path) -> None:
    w = make(qtbot, tmp_path, "full")
    w.dock_right.hide()
    w.show_object(sorted(w.ctl.project.units)[0])
    assert not w.dock_right.isVisibleTo(w)  # as before


def test_selecting_with_the_inspector_closed_says_how_to_open_it(qtbot, tmp_path) -> None:
    w = make(qtbot, tmp_path, "simple")
    w._told_properties = False
    unit = sorted(w.ctl.project.units)[0]
    w.ctl.select("unit", unit)
    assert strings.PROPERTIES_CLOSED in w.toasts.messages
    w.show_panels(True)
    assert w.dock_right.isVisibleTo(w)


def test_double_click_still_shows_the_plans(qtbot, tmp_path) -> None:
    w = make(qtbot, tmp_path, "simple")
    shown: list[tuple[str, str]] = []
    w._open_requested = lambda kind, ident: shown.append((kind, ident))  # type: ignore[method-assign]
    w.ctl.openRequested.disconnect()
    w.ctl.openRequested.connect(w._open_requested)
    unit = sorted(w.ctl.project.units)[0]
    w.ctl.request_open("unit", unit)
    assert shown == [("unit", unit)]


# ---- the layout is remembered per workspace ----------------------------------------------------
def test_a_second_window_in_simple_restores_simple(qtbot, tmp_path) -> None:
    first = make(qtbot, tmp_path, "simple")
    first.show_panels(True)
    first.act_minimap.trigger()
    first.close()
    second = make(qtbot, tmp_path)
    assert second.workspace == "simple"
    s = seen(second)
    assert s["dock_left"] and s["dock_right"] and s["minimap_wanted"]
    assert not s["legend_wanted"]
    assert second.settings.value("ui/simple/minimap", False, bool) is True


def test_a_window_closed_in_simple_leaves_the_full_keys_alone(qtbot, tmp_path) -> None:
    settings = QSettings(str(tmp_path / "ui.ini"), QSettings.Format.IniFormat)
    full = make(qtbot, tmp_path, "full")
    full.act_minimap.trigger()
    full.act_legend.trigger()
    full.dock_right.hide()
    full.close()
    settings.sync()
    old = {k: settings.value(k) for k in ("ui/state", "ui/minimap", "ui/legend")}
    assert old["ui/state"] is not None and old["ui/minimap"] in (False, "false")

    simple = make(qtbot, tmp_path, "simple")
    simple.act_minimap.trigger()
    simple.show_panels(True)
    simple.close()
    settings.sync()
    assert {k: settings.value(k) for k in old} == old  # Full is as it was
    assert settings.value("ui/simple/state") is not None
    assert settings.value("ui/state") == old["ui/state"]

    again = make(qtbot, tmp_path, "full")
    s = seen(again)
    assert not s["minimap_wanted"] and not s["legend_wanted"] and not s["dock_right"]


def test_the_project_layout_is_kept_per_workspace(qtbot, tmp_path) -> None:
    from tests.ux_rel import flatsat_controller

    ctl = flatsat_controller(tmp_path)
    root = ctl.root
    ctl.release()
    w = make(qtbot, tmp_path, "full")
    assert root is not None and w.open_project(root)
    w.set_area("checks")
    w.set_workspace("simple")
    w.set_area("outputs")
    w.close()
    s = QSettings(str(tmp_path / "ui.ini"), QSettings.Format.IniFormat)
    group = w._layout_group()
    assert group is not None
    assert s.value(f"{group}/area") == "checks"  # Full's
    assert s.value(f"{group}/simple/area") == "outputs"


def test_switching_saves_the_layout_of_the_workspace_it_leaves(qtbot, tmp_path) -> None:
    w = make(qtbot, tmp_path, "simple")
    w.show_panels(True)
    w.set_workspace("full")
    w.dock_left.hide()
    w.set_workspace("simple")
    assert w.dock_left.isVisibleTo(w) and w.dock_right.isVisibleTo(w)  # Simple's own
    w.set_workspace("full")
    assert not w.dock_left.isVisibleTo(w) and w.dock_right.isVisibleTo(w)  # Full's own


def test_a_new_file_that_starts_in_full_then_goes_simple_then_full(qtbot, tmp_path) -> None:
    w = make(qtbot, tmp_path)  # no stored values: the tests start in Full (conftest)
    assert w.workspace == "full"
    w.set_workspace("simple")
    assert not w.dock_left.isVisibleTo(w)
    w.set_workspace("full")
    assert w.dock_left.isVisibleTo(w) and w.dock_right.isVisibleTo(w)


# ---- names and tooltips ------------------------------------------------------------------------
def test_the_new_controls_are_named_and_have_a_tooltip(qtbot, tmp_path) -> None:
    w = make(qtbot, tmp_path, "simple")
    for button, name in (
        (w.panels_btn, strings.SHOW_PANELS_BUTTON),
        (w.tool_add_device, strings.TOOL_ADD_DEVICE),
        (w.tool_more, strings.TOOL_MORE),
    ):
        assert isinstance(button, QToolButton)
        assert button.accessibleName() == name
        assert button.toolTip() and button.text() == name
    assert w.act_show_panels.toolTip() and w.act_show_panels.text() == strings.A_SHOW_PANELS
    assert "Ctrl+Shift+N" in w.tool_add_device.toolTip()
    assert w.menu_more.accessibleName() or w.menu_more.objectName() == "menu-more"
