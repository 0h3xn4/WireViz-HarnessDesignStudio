# mypy: disable-error-code="no-untyped-def,no-untyped-call"
"""SH-6, SH-7, SC-21: the five bottom tabs (Problems, To-do, Interface table, Harness plans, Outline),
the bottom dock and the Palette tab are gone, and every function they had is in its new place:
the Problems tab of the right panel (with the To do lines), the Interfaces tab of the left panel,
the Harness tab (More menu), the project tree (multiple selection, Delete) and the Connect arrow.
Offscreen, in a real window."""

from pathlib import Path

import pytest

pytest.importorskip("PySide6")
pytestmark = pytest.mark.gui

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtGui import QAction  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import (  # noqa: E402
    QApplication,
    QDockWidget,
    QLabel,
    QLineEdit,
    QMenu,
    QPushButton,
)

from harness_design_studio.core import edit  # noqa: E402
from harness_design_studio.core.generate.engine import generate_project  # noqa: E402
from harness_design_studio.core.samples import sat15_full  # noqa: E402
from harness_design_studio.gui import strings  # noqa: E402
from tests.gui_helpers import (  # noqa: E402
    DialogScript,
    action_named,
    add_unit,
    make_window,
    pick_connect_type,
    show_problems,
)
from tests.test_accessibility import unnamed  # noqa: E402


@pytest.fixture
def win(qtbot, tmp_path: Path):
    w = make_window(tmp_path)
    qtbot.addWidget(w)
    return w


@pytest.fixture
def gen(qtbot, tmp_path: Path):
    """A window with the generated sat15_full example (harnesses W001 and more)."""
    w = make_window(tmp_path)
    qtbot.addWidget(w)
    p = sat15_full()
    generate_project(p)
    w.ctl._install(p, None, None)
    QApplication.processEvents()
    return w


# ---- what is gone ----------------------------------------------------------------------------------


def test_there_is_no_bottom_dock_no_palette_and_no_old_plans_panel(win) -> None:
    docks = {d.objectName() for d in win.findChildren(QDockWidget)}
    assert docks == {"dock-project", "dock-properties", "dock-problems"}  # (the last is M2's list)
    for name in (
        "dock_bottom",
        "tabs",
        "todo",
        "outline",
        "harness_panel",
        "palette_panel",
        "table",
    ):
        assert not hasattr(win, name), name
    assert win.left_tabs.names() == ["tree", "interfaces"]
    from harness_design_studio.gui import panels

    for cls in ("PalettePanel", "TodoPanel", "HarnessPanel", "OutlinePanel", "InterfaceTable"):
        assert not hasattr(panels, cls), cls


def test_a_short_window_hides_no_panel_for_lack_of_height(win) -> None:
    win.resize(1440, 900)
    win.auto_layout()
    win.resize(1440, 600)
    QApplication.processEvents()
    assert not win.dock_left.isHidden() and not win.dock_right.isHidden()


def test_the_view_menu_toggles_only_the_two_side_panels(win) -> None:
    view = next(a.menu() for a in win.menuBar().actions() if a.text().replace("&", "") == "View")
    texts = [a.text().replace("&", "") for a in view.actions()]
    assert "Problems and status" not in texts
    assert win.dock_left.toggleViewAction() in view.actions()
    assert win.dock_right.toggleViewAction() in view.actions()


# ---- the Palette: add units, connect with a type, import ------------------------------------------


def test_every_kind_of_unit_can_be_added_without_the_palette(win) -> None:
    for tid in edit.TEMPLATES:
        n = len(win.ctl.project.units)
        add_unit(win, tid)
        assert len(win.ctl.project.units) == n + 1, tid


def test_the_projects_add_button_opens_the_list_of_unit_kinds(win, monkeypatch) -> None:
    shown: list[QMenu] = []
    monkeypatch.setattr(win.menu_add, "exec", lambda *a, **k: shown.append(win.menu_add))
    win.project_tree.add_actions["unit"].trigger()
    assert shown == [win.menu_add]
    names = {a.objectName() for a in win.menu_add.actions() if a.objectName()}
    # every kind of unit, and the way to add a device of one's own (the Devices tab, Ctrl+Shift+N)
    assert names == {f"menu-add-{t}" for t in edit.TEMPLATES} | {"act-add-device"}


def test_the_connect_arrow_lists_every_interface_type_and_ticks_the_one_in_use(win) -> None:
    assert win.tool_connect.menu() is win.menu_connect
    types = sorted(win.ctl.project.interface_types)
    assert [a.objectName() for a in win.menu_connect.actions()] == [
        f"menu-connect-{t}" for t in types
    ]
    assert not any(a.isChecked() for a in win.menu_connect.actions())
    pick_connect_type(win, "rs422")
    assert win.ctl.tool == "connect" and win.ctl.connect_type == "rs422"
    assert [a.objectName() for a in win.menu_connect.actions() if a.isChecked()] == [
        "menu-connect-rs422"
    ]
    pick_connect_type(win, "can")  # another type moves the tick
    assert [a.objectName() for a in win.menu_connect.actions() if a.isChecked()] == [
        "menu-connect-can"
    ]
    pick_connect_type(win, "can")  # the active type again turns the tool off
    assert win.ctl.tool == "select"
    assert not any(a.isChecked() for a in win.menu_connect.actions())


def test_the_connect_button_has_a_menu_arrow_a_name_and_a_tooltip(win) -> None:
    from PySide6.QtWidgets import QToolButton

    b = win.tool_connect
    assert b.popupMode() == QToolButton.ToolButtonPopupMode.MenuButtonPopup
    assert b.accessibleName() == strings.TOOL_CONNECT and "arrow" in b.toolTip()
    assert "(C)" in b.toolTip()


def test_the_interface_import_is_in_the_file_menu_the_tree_and_ctrl_k(win) -> None:
    assert win.act_import.shortcut().toString() == "Ctrl+Shift+I"
    assert "Imports" in strings.TREE_ROOTS["imports"]
    labels = [e.label for e in win.palette_entries()]
    assert strings.A_IMPORT in labels


# ---- the To-do tab: its lines are the top of the Problems tab -------------------------------------


def test_the_todo_lines_are_at_the_top_of_the_problems_tab_with_their_count(win) -> None:
    add_unit(win, "pyro")  # a unit that is connected to nothing
    problems = show_problems(win)
    heading = problems.findChild(QLabel, "todo-heading")
    assert heading is not None and heading.text() == "TO DO (1)"
    line = problems.findChild(QPushButton, "todo-0")
    assert line is not None and "not connected to anything" in line.text()
    assert line.property("align") == "left" and line.styleSheet() == ""
    win.ctl.select(None)
    line.click()  # a click shows the unit
    assert win.ctl.selection is not None and win.ctl.selection.id == "PYRO1"
    # the to-do lines come before the problem cards in the layout
    order = [problems.lay.itemAt(i).widget() for i in range(problems.lay.count())]
    names = [w.objectName() for w in order if w is not None]
    assert names.index("todo-heading") < min(
        (i for i, n in enumerate(names) if n.startswith("finding-")), default=len(names)
    )


def test_the_warnings_line_scrolls_to_the_first_card_and_the_list_is_empty_when_done(gen) -> None:
    problems = show_problems(gen)
    gen.ctl.run_drc_now()
    problems.refresh()
    lines = [b for b in problems.findChildren(QPushButton) if b.objectName().startswith("todo-")]
    assert lines or not gen.ctl.todos()
    for text, kind, target in ((t.text, t.kind, t.target) for t in gen.ctl.todos()):
        if kind == "tab":
            line = next(b for b in lines if text in b.text())
            line.click()  # nothing to select: it scrolls (and must not raise)
            assert target == "problems"


def test_the_problems_tab_title_carries_the_count_the_bottom_tab_had(win) -> None:
    add_unit(win, "computer")
    errors, warnings = win.problems.counts()
    text = win.inspector.tabs.tabText(2)
    assert text == (f"Problems ({errors + warnings})" if errors + warnings else "Problems")


def test_the_problems_list_keeps_its_name_and_the_side_tabs_are_named(win) -> None:
    assert win.problems.accessibleName() == strings.PROBLEMS
    for tabs in (win.left_tabs, win.side_tabs):
        assert tabs.accessibleName()
    for name in win.left_tabs.names():
        win.left_tabs.setCurrentIndex(win.left_tabs.index_of(name))
        assert unnamed(win) == [], name


# ---- the Interface table: the keyboard alternative to the diagram ---------------------------------


def test_the_interface_table_is_the_second_left_tab_with_a_shortcut_and_a_go_entry(win) -> None:
    act = action_named(win, "act-go-interfaces")
    assert act.shortcut().toString() == "Ctrl+Shift+T"
    assert act in win.menu_go.actions()
    assert act.text().replace("&", "") in [e.label for e in win.palette_entries()]
    win.dock_left.hide()
    act.trigger()
    assert win.dock_left.isVisible()
    assert win.left_tabs.currentWidget() is win.interface_table
    assert win.dock_left.windowTitle() == strings.TAB_INTERFACES
    assert win.interface_table.view.hasFocus() or win.interface_table.view.isVisible()
    assert win.interface_table.view.accessibleName() == strings.INTERFACE_TABLE


def test_the_left_panel_widens_for_the_interface_table_and_narrows_back(win) -> None:
    win.resize(1440, 900)
    win.auto_layout()
    QApplication.processEvents()
    before = win.dock_left.width()
    win.show_interfaces()
    QApplication.processEvents()
    assert win.dock_left.width() > before + 100
    win.left_tabs.setCurrentIndex(win.left_tabs.index_of("tree"))
    QApplication.processEvents()
    assert abs(win.dock_left.width() - before) < 20


def test_the_arrow_keys_move_between_interfaces_and_the_diagram_follows(win) -> None:
    win.show_interfaces()
    table = win.interface_table
    table.refresh()
    view = table.view
    view.setFocus()
    view.selectRow(0)
    first = win.ctl.selection
    assert first is not None and first.kind == "interface"
    QTest.keyClick(view, Qt.Key.Key_Down)
    second = win.ctl.selection
    assert second is not None and second.kind == "interface" and second.id != first.id


def test_a_cell_is_edited_from_the_keyboard_as_one_undo_step(win) -> None:
    win.show_interfaces()
    table = win.interface_table
    table.refresh()
    index = table.proxy.index(0, 1)  # the Name column
    iid = table.proxy.index(0, 0).data()
    view = table.view
    view.setFocus()
    view.setCurrentIndex(index)
    depth = win.ctl.history.revision
    view.edit(index)
    editors = view.viewport().findChildren(QLineEdit)  # the cell editor F2 or typing opens
    assert len(editors) == 1
    editors[0].setText("Renamed from the table")
    QTest.keyClick(editors[0], Qt.Key.Key_Return)
    QApplication.processEvents()  # the delegate commits when the editor closes
    assert win.ctl.project.interfaces[iid].name == "Renamed from the table"
    assert win.ctl.history.revision == depth + 1
    win.ctl.undo()
    assert win.ctl.project.interfaces[iid].name != "Renamed from the table"


def test_the_interface_table_filters_and_the_new_interface_button_opens_the_form(win) -> None:
    win.show_interfaces()
    table = win.interface_table
    table.refresh()
    total = table.proxy.rowCount()
    assert total == len(win.ctl.project.interfaces)
    table.filter.setText("zzzz-no-such-interface")
    assert table.proxy.rowCount() == 0
    table.filter.setText("")
    asked: list[bool] = []
    win.new_interface_flow = lambda: asked.append(True)  # type: ignore[method-assign]
    table.newInterfaceRequested.disconnect()
    table.newInterfaceRequested.connect(win.new_interface_flow)
    table.add_btn.click()
    assert asked == [True]


# ---- the Outline: the project tree takes its place ---------------------------------------------------


def test_shift_arrows_in_the_tree_select_several_units_and_back_to_one(win) -> None:
    tree = win.project_tree
    first, second = tree.child_ids("units")[:2]
    tree.view.setCurrentIndex(tree.index_for("unit", first))
    tree.view.setFocus()
    QTest.keyClick(tree.view, Qt.Key.Key_Down, Qt.KeyboardModifier.ShiftModifier)
    assert {(s.kind, s.id) for s in win.ctl.selected} == {("unit", first), ("unit", second)}
    rows = {tree._node_at(i).id for i in tree.view.selectionModel().selectedRows()}
    assert rows == {first, second}  # the highlight is not lost when the controller answers
    QTest.keyClick(tree.view, Qt.Key.Key_Up, Qt.KeyboardModifier.ShiftModifier)
    assert [(s.kind, s.id) for s in win.ctl.selected] == [("unit", first)]


def test_the_selection_of_several_on_the_diagram_shows_in_the_tree_and_clears(win) -> None:
    tree = win.project_tree
    a, b = tree.child_ids("units")[:2]
    win.ctl.select_many([("unit", a), ("unit", b)])
    assert {tree._node_at(i).id for i in tree.view.selectionModel().selectedRows()} == {a, b}
    win.ctl.select("unit", a)  # back to one: the second row is not left highlighted
    assert {tree._node_at(i).id for i in tree.view.selectionModel().selectedRows()} == {a}


def test_delete_in_the_tree_deletes_the_row_with_the_cursor_not_a_stale_selection(win) -> None:
    tree = win.project_tree
    victim = "OBC"
    other = "PCDU"
    win.ctl.select("unit", other)  # the diagram has another unit selected
    tree.view.setCurrentIndex(tree.index_for("unit", victim))
    tree.view.setFocus()
    seen: list[str] = []
    DialogScript(win, lambda d: seen.append(d.windowTitle()), accept=False)
    QTest.keyClick(tree.view, Qt.Key.Key_Delete)
    assert seen and victim in seen[0]  # the confirmation names the unit under the cursor
    assert victim in win.ctl.project.units and other in win.ctl.project.units  # cancelled


def test_delete_on_a_part_row_of_the_tree_does_nothing(win) -> None:
    tree = win.project_tree
    parts = tree.child_ids("parts")
    if not parts:
        pytest.skip("the sample has no parts")
    win.ctl.select("unit", "OBC")
    tree.view.setCurrentIndex(tree.index_for("part", parts[0]))
    tree.view.setFocus()
    script = DialogScript(win, accept=True)
    QTest.keyClick(tree.view, Qt.Key.Key_Delete)
    assert not script.seen and "OBC" in win.ctl.project.units


# ---- Harness plans: what the Harness tab and the menus offer now -----------------------------------


def test_the_more_menu_has_changes_change_log_and_delete_and_follows_the_state(gen) -> None:
    view = gen.harness_view
    gen.go_to("harness")
    hid = sorted(gen.ctl.project.harnesses)[0]
    assert view.select_harness(hid)
    more = view.more_actions
    assert [a.text() for a in view.more_menu.actions()] == [
        strings.CHANGES,
        strings.HISTORY,
        strings.DELETE_HARNESS,
    ]
    assert more["history"].isEnabled() and more["delete"].isEnabled()
    assert not more["changes"].isEnabled()  # no baseline yet
    assert view.more_button.accessibleName() and view.more_button.toolTip()
    gen.ctl.project.read_only = True
    gen.ctl.stateChanged.emit()
    assert not more["delete"].isEnabled() and more["history"].isEnabled()


def test_more_menu_items_open_the_flows_of_the_old_plans_buttons(gen) -> None:
    calls: list[tuple[str, str]] = []
    gen.change_flow = lambda action, hid: calls.append((action, hid))  # type: ignore[method-assign]
    gen.go_to("harness")
    hid = sorted(gen.ctl.project.harnesses)[0]
    gen.harness_view.select_harness(hid)
    gen.harness_view.more_actions["history"].trigger()
    gen.harness_view.more_actions["delete"].trigger()
    assert calls == [("history", hid), ("delete", hid)]


def test_the_design_menu_has_the_harness_steps_that_act_on_the_harness_in_view(gen) -> None:
    calls: list[tuple[str, str]] = []
    gen.change_flow = lambda action, hid: calls.append((action, hid))  # type: ignore[method-assign]
    names = {a.objectName() for a in gen.menu_design.actions()}
    assert {"act-changes", "act-history", "act-delete-harness"} <= names
    gen.go_to("harness")
    hid = sorted(gen.ctl.project.harnesses)[1]
    gen.harness_view.select_harness(hid)
    action_named(gen, "act-history").trigger()
    action_named(gen, "act-delete-harness").trigger()
    assert calls == [("history", hid), ("delete", hid)]
    labels = [e.label for e in gen.palette_entries()]
    assert strings.A_DELETE_HARNESS.replace("…", "…") in labels


def test_a_design_menu_step_with_several_harnesses_and_none_in_view_opens_releases(gen) -> None:
    gen.go_to("diagram")
    gen.harness_view._hid = None
    gen.releases_panel.select_harness = lambda _h: None  # type: ignore[method-assign]
    assert len(gen.ctl.project.harnesses) > 1
    gen.harness_step("history")
    assert gen.main_tabs.currentWidget() is gen.releases_panel
    assert gen.toasts.messages[-1] == strings.NO_HARNESS_FOR_ACTION


def test_a_delete_step_is_refused_in_a_read_only_project(gen) -> None:
    gen.ctl.project.read_only = True
    n = len(gen.ctl.project.harnesses)
    script = DialogScript(gen, accept=True)
    gen.harness_view.select_harness(sorted(gen.ctl.project.harnesses)[0])
    gen.harness_step("delete")
    assert not script.seen and len(gen.ctl.project.harnesses) == n


def test_the_tree_context_menu_of_a_harness_has_the_change_control_steps(gen) -> None:
    tree = gen.project_tree
    hid = sorted(gen.ctl.project.harnesses)[0]
    menu = tree.build_menu("harness", hid)
    steps = {
        a.objectName(): a for a in menu.actions() if a.objectName().startswith("tree-harness-")
    }
    assert set(steps) == {
        "tree-harness-review",
        "tree-harness-release",
        "tree-harness-revise",
        "tree-harness-changes",
        "tree-harness-history",
        "tree-harness-delete",
    }
    assert steps["tree-harness-review"].isEnabled() and steps["tree-harness-release"].isEnabled()
    assert not steps["tree-harness-revise"].isEnabled()  # a draft is not revised
    assert not steps["tree-harness-changes"].isEnabled()  # nothing to compare with yet
    calls: list[tuple[str, str]] = []
    gen.change_flow = lambda action, h: calls.append((action, h))  # type: ignore[method-assign]
    steps["tree-harness-history"].trigger()
    assert calls == [("history", hid)]
    assert not [
        a for a in tree.build_menu("unit", "OBC1").actions() if "harness-" in a.objectName()
    ]


def test_a_released_harness_cannot_be_deleted_from_the_menu_and_a_draft_can(gen) -> None:
    hid = sorted(gen.ctl.project.harnesses)[0]
    tree = gen.project_tree
    gen.ctl.project.harnesses[hid] = edit_status(gen.ctl.project.harnesses[hid], "released")
    steps = {a.objectName(): a for a in tree.build_menu("harness", hid).actions()}
    assert not steps["tree-harness-delete"].isEnabled()
    assert steps["tree-harness-revise"].isEnabled()


def edit_status(h, status: str):
    from harness_design_studio.core.model import evolve

    return evolve(h, status=status)


# ---- the harness list, the check and the outputs line: the Harness tab chips ------------------------


def test_the_harness_tab_shows_what_the_plans_tab_said(gen) -> None:
    view = gen.harness_view
    gen.go_to("harness")
    view.refresh()
    assert view.wait_idle()
    assert (
        view.gen_chip.state() == "pass" and strings.GEN_STATUS["current"] in view.gen_chip.toolTip()
    )
    assert view.verify_chip.state() == "pass"
    assert view.outputs_chip.state() == "not-checked"  # not saved: no outputs yet
    assert view.selector.count() == len(gen.ctl.project.harnesses)
    h = gen.ctl.project.harnesses[view.harness_id()]
    assert view.wire_model.rowCount() == len(h.wires)  # the wire table, with a Colour column
    assert view.wire_model.column_index("colour") >= 0
    assert gen.project_tree.child_ids("harnesses") == sorted(gen.ctl.project.harnesses)


def test_a_diagram_double_click_still_lands_on_the_wire_in_the_harness_tab(gen) -> None:
    iid = sorted(gen.ctl.project.interfaces)[0]
    gen.ctl.request_open("interface", iid)
    assert gen.main_tabs.currentWidget() is gen.harness_view
    selection = gen.harness_view.selection()
    assert selection is not None and selection[0] == "wire"


# ---- layout ------------------------------------------------------------------------------------------


def test_f6_visits_the_project_panel_the_inspector_and_back(win) -> None:
    win.resize(1440, 900)
    win.auto_layout()
    win.show()
    win.activateWindow()
    QApplication.processEvents()
    win.view.setFocus()
    win._pane = 0
    names = [win.cycle_panes(1) for _ in range(3)]
    assert names == [strings.PANE_TREE, strings.PANE_INSPECTOR, strings.PANE_CANVAS]


def test_the_menu_and_toolbar_actions_have_no_leftovers_from_the_bottom_panel(win) -> None:
    texts = [a.text() for a in win.findChildren(QAction)]
    for old in ("Problems and status", "Harness plans", "Outline"):
        assert old not in texts
