# mypy: disable-error-code="no-untyped-def,no-untyped-call"
"""UI overhaul M4: the model tables as spreadsheets: paste from Excel, bulk edit, Enter to edit,
Esc to cancel, the column menu, one undo step for a paste."""

import json

import pytest

pytest.importorskip("PySide6")
pytestmark = pytest.mark.gui

from PySide6.QtCore import QItemSelectionModel, QSettings, Qt  # noqa: E402
from PySide6.QtGui import QGuiApplication  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from harness_design_studio.gui import strings  # noqa: E402
from harness_design_studio.gui.main_window import MainWindow  # noqa: E402
from harness_design_studio.gui.sheet import parse_tsv, paste_text  # noqa: E402
from harness_design_studio.gui.theme import ThemeManager  # noqa: E402
from tests.ux_rel import flatsat_controller  # noqa: E402


@pytest.fixture
def win(qtbot, tmp_path):
    ctl = flatsat_controller(tmp_path)
    root = ctl.root
    ctl.release()
    w = MainWindow(
        QSettings(str(tmp_path / "ui.ini"), QSettings.Format.IniFormat),
        ThemeManager(),
        first_run=False,
    )
    w.ask_choice = lambda t, x, b: 1  # type: ignore[assignment]
    qtbot.addWidget(w)
    w.resize(1600, 900)
    w.show()
    assert root is not None and w.open_project(root)
    QApplication.processEvents()
    return w


def shown(win, which: str):
    """The Interface or Unit table, shown (a hidden table reads the project when it appears)."""
    (win.show_interfaces if which == "interfaces" else win.show_units)()
    QApplication.processEvents()
    return win.interface_table if which == "interfaces" else win.unit_table


def select_block(view, top: int, left: int, bottom: int, right: int) -> None:
    sel = view.selectionModel()
    sel.clearSelection()
    model = view.model()
    from PySide6.QtCore import QItemSelection

    sel.select(
        QItemSelection(model.index(top, left), model.index(bottom, right)),
        QItemSelectionModel.SelectionFlag.ClearAndSelect,
    )
    sel.setCurrentIndex(model.index(top, left), QItemSelectionModel.SelectionFlag.NoUpdate)


def names(win) -> dict[str, str]:
    return {i.id: i.name for i in win.ctl.project.interfaces.values()}


# ---- the text ---------------------------------------------------------------------------------
def test_tsv_reads_what_excel_and_this_program_copy() -> None:
    assert parse_tsv("a\tb\nc\td\n") == [["a", "b"], ["c", "d"]]
    assert parse_tsv("a\tb\r\nc\td\r\n") == [["a", "b"], ["c", "d"]]
    assert parse_tsv('"a\tb"\t"say ""hi"""\n') == [["a\tb", 'say "hi"']]
    assert parse_tsv('"two\nlines"\tx') == [["two\nlines", "x"]]
    assert parse_tsv("x") == [["x"]]
    assert parse_tsv("a\t\tc\n") == [["a", "", "c"]]  # an empty cell stays a cell
    assert parse_tsv("") == []


# ---- the Interface table -----------------------------------------------------------------------
def test_pasting_a_block_into_the_interface_table_is_one_undo_step(win) -> None:
    t = shown(win, "interfaces")
    before = names(win)
    ids = list(before)
    rows = t.proxy.rowCount()
    assert rows >= 3
    select_block(t.view, 0, 1, 0, 1)  # Name of the first row
    done, skipped = paste_text(t.view, "Alpha\nBeta\nGamma")
    assert (done, skipped) == (3, 0)
    after = names(win)
    first = [str(t.proxy.index(r, 0).data()) for r in range(3)]
    assert [after[i] for i in first] == ["Alpha", "Beta", "Gamma"]
    win.ctl.undo()  # one step puts all three back
    assert names(win) == before
    assert set(ids) == set(names(win))


def test_a_full_row_copied_from_the_table_pastes_back_leaving_the_read_only_cells(win) -> None:
    t = shown(win, "interfaces")
    rows = [[str(t.proxy.index(r, c).data()) for c in range(8)] for r in range(2)]
    rows[0][1] = "Renamed"
    rows[0][6] = "7.5"
    select_block(t.view, 0, 0, 0, 0)
    done, skipped = paste_text(t.view, "\n".join("\t".join(r) for r in rows))
    assert (done, skipped) == (8, 8)  # ID, Type, From and To of both rows are read-only
    i = win.ctl.project.interfaces[rows[0][0]]
    assert i.name == "Renamed" and i.max_current_a == 7.5


def test_one_value_fills_every_selected_cell(win) -> None:
    t = shown(win, "interfaces")
    select_block(t.view, 0, 7, 3, 7)  # Requirement of four rows
    done, _ = paste_text(t.view, "REQ-X-1")
    assert done == 4
    got = {i.requirement_id for i in win.ctl.project.interfaces.values()}
    assert "REQ-X-1" in got
    n = sum(1 for i in win.ctl.project.interfaces.values() if i.requirement_id == "REQ-X-1")
    assert n == 4
    win.ctl.undo()
    assert all(i.requirement_id != "REQ-X-1" for i in win.ctl.project.interfaces.values())


def test_a_bad_cell_stops_the_whole_paste_and_says_why(win) -> None:
    t = shown(win, "interfaces")
    before = names(win)
    messages: list[str] = []
    win.ctl.message.connect(lambda text, _undo: messages.append(text))
    select_block(t.view, 0, 5, 0, 5)  # Chain
    paste_text(t.view, "nominal\nwrong")
    assert names(win) == before
    assert {i.redundancy for i in win.ctl.project.interfaces.values()} <= {
        "nominal",
        "redundant",
        "none",
    }
    assert strings.CHAIN_HELP in messages


def test_text_that_is_not_a_number_is_refused_in_the_current_column(win) -> None:
    t = shown(win, "interfaces")
    select_block(t.view, 0, 6, 0, 6)
    messages: list[str] = []
    win.ctl.message.connect(lambda text, _undo: messages.append(text))
    before = {i.id: i.max_current_a for i in win.ctl.project.interfaces.values()}
    paste_text(t.view, "lots")
    assert {i.id: i.max_current_a for i in win.ctl.project.interfaces.values()} == before
    assert messages


def test_a_read_only_project_takes_no_paste(win) -> None:
    win.ctl.project.read_only = True
    t = shown(win, "interfaces")
    select_block(t.view, 0, 1, 0, 1)
    before = names(win)
    done, skipped = paste_text(t.view, "Nope")
    assert done == 0 and names(win) == before


def test_bulk_edit_applies_one_edit_to_every_selected_row(win) -> None:
    t = shown(win, "interfaces")

    def chains() -> list[str]:
        return [
            win.ctl.project.interfaces[str(t.proxy.index(r, 0).data())].redundancy for r in range(3)
        ]

    before = chains()
    select_block(t.view, 0, 5, 2, 5)  # Chain of three rows
    index = t.proxy.index(1, 5)
    delegate = t.view.itemDelegateForColumn(5)
    editor = delegate.createEditor(t.view, None, index)
    editor.setCurrentText("redundant" if before[1] != "redundant" else "none")
    delegate.setModelData(editor, t.proxy, index)
    assert chains() == [editor.currentText()] * 3
    win.ctl.undo()
    assert chains() == before


def test_enter_edits_the_current_cell_and_escape_keeps_the_old_text(win, qtbot) -> None:
    t = shown(win, "interfaces")
    t.view.setCurrentIndex(t.proxy.index(0, 1))
    old = str(t.proxy.index(0, 1).data())
    QTest.keyClick(t.view, Qt.Key.Key_Return)
    assert t.view.state() == t.view.State.EditingState
    editor = t.view.indexWidget(t.proxy.index(0, 1))
    editor.setText("Typed and abandoned")
    QTest.keyClick(editor, Qt.Key.Key_Escape)
    QApplication.processEvents()
    assert t.view.state() != t.view.State.EditingState
    assert str(t.proxy.index(0, 1).data()) == old
    # and Enter, text, Enter commits
    QApplication.processEvents()
    QTest.keyClick(t.view, Qt.Key.Key_Return)
    editor = t.view.indexWidget(t.proxy.index(0, 1))
    assert editor is not None
    editor.setText("Committed by key")
    QTest.keyClick(editor, Qt.Key.Key_Return)
    QApplication.processEvents()
    assert str(t.proxy.index(0, 1).data()) == "Committed by key"


def test_ctrl_v_pastes_from_the_clipboard(win, qtbot) -> None:
    t = shown(win, "interfaces")
    select_block(t.view, 0, 1, 0, 1)
    QGuiApplication.clipboard().setText("From the clipboard\nSecond")
    t.view.setFocus()
    QTest.keyClick(t.view, Qt.Key.Key_V, Qt.KeyboardModifier.ControlModifier)
    assert str(t.proxy.index(0, 1).data()) == "From the clipboard"
    assert str(t.proxy.index(1, 1).data()) == "Second"


def test_the_numeric_column_is_right_aligned_and_has_its_unit_in_the_header(win) -> None:
    t = shown(win, "interfaces")
    assert "(A)" in str(t.proxy.headerData(6, Qt.Orientation.Horizontal))
    align = t.proxy.index(0, 6).data(Qt.ItemDataRole.TextAlignmentRole)
    assert int(align) & int(Qt.AlignmentFlag.AlignRight)


def test_ids_read_in_the_monospace_font(win) -> None:
    t = shown(win, "interfaces")
    assert t.proxy.index(0, 0).data(Qt.ItemDataRole.FontRole) is not None
    assert t.proxy.index(0, 7).data(Qt.ItemDataRole.FontRole) is not None


def test_columns_can_be_hidden_and_the_choice_is_kept(win) -> None:
    t = shown(win, "interfaces")
    menu = t.view.column_menu
    menu.set_hidden(3, True)
    menu.set_hidden(0, True)  # the ID stays
    assert t.view.isColumnHidden(3) and not t.view.isColumnHidden(0)
    saved = json.loads(str(win.settings.value("tables/interfaces/hidden")))
    assert saved == [3]
    win.settings.sync()
    from harness_design_studio.gui.interface_table import InterfaceTable

    again = InterfaceTable(win.ctl, win.settings)
    assert again.view.isColumnHidden(3)


def test_the_header_menu_lists_every_column_with_a_tick(win) -> None:
    t = shown(win, "interfaces")
    t.view.column_menu.show_menu(t.view.horizontalHeader().rect().center())
    actions = [a for a in t.view.column_menu.menu.actions() if a.isCheckable()]
    assert [a.text() for a in actions] == list(strings.INTERFACE_COLUMNS)
    assert actions[0].isChecked() and not actions[0].isEnabled()
    t.view.column_menu.menu.close()


def test_selecting_several_rows_selects_those_interfaces(win) -> None:
    t = shown(win, "interfaces")
    select_block(t.view, 0, 0, 2, 7)
    QApplication.processEvents()
    ids = {str(t.proxy.index(r, 0).data()) for r in range(3)}
    assert {s.id for s in win.ctl.selected if s.kind == "interface"} == ids


# ---- the Unit table ----------------------------------------------------------------------------
def unit_names(win) -> dict[str, str]:
    return {u.id: u.name for u in win.ctl.project.units.values()}


def test_the_unit_table_lists_every_unit_with_its_counts(win) -> None:
    t = shown(win, "units")
    assert t.proxy.rowCount() == len(win.ctl.project.units)
    row = {t.proxy.index(r, 0).data(): r for r in range(t.proxy.rowCount())}
    r = row["PDU2"]
    assert t.proxy.index(r, 1).data() == win.ctl.project.units["PDU2"].name
    links = sum(
        1
        for i in win.ctl.project.interfaces.values()
        if any(e.unit_id == "PDU2" for e in i.endpoints)
    )
    assert t.proxy.index(r, 5).data() == links


def test_unit_names_paste_as_one_undo_step_and_the_id_is_read_only(win) -> None:
    t = shown(win, "units")
    before = unit_names(win)
    select_block(t.view, 0, 0, 0, 1)  # ID and Name of the first row
    done, skipped = paste_text(t.view, "BAT1\tBattery pack\nGPSU1\tGPS unit")
    assert done == 2 and skipped == 2
    ids = [str(t.proxy.index(r, 0).data()) for r in range(2)]
    after = unit_names(win)
    assert [after[i] for i in ids] == ["Battery pack", "GPS unit"]
    win.ctl.undo()
    assert unit_names(win) == before


def test_an_empty_unit_name_is_refused(win) -> None:
    t = shown(win, "units")
    before = unit_names(win)
    select_block(t.view, 0, 1, 0, 1)
    paste_text(t.view, "  ")
    assert unit_names(win) == before


def test_unit_notes_may_hold_several_lines(win) -> None:
    t = shown(win, "units")
    select_block(t.view, 0, 7, 0, 7)
    paste_text(t.view, '"first\nsecond"')
    uid = str(t.proxy.index(0, 0).data())
    assert win.ctl.project.units[uid].notes == "first\nsecond"


def test_the_unit_table_follows_the_diagram_selection(win) -> None:
    win.ctl.select("unit", "PDU2")
    win.show_units()
    QApplication.processEvents()
    rows = {i.row() for i in win.unit_table.view.selectionModel().selectedIndexes()}
    assert {str(win.unit_table.proxy.index(r, 0).data()) for r in rows} == {"PDU2"}


def test_the_unit_table_opens_with_its_own_shortcut(win) -> None:
    win.act_go_units.trigger()
    assert win.left_tabs.currentWidget() is win.unit_table
    assert win.dock_left.windowTitle() == strings.TAB_UNITS
    assert win.focusWidget() is win.unit_table.view


def test_every_saved_table_gets_the_column_menu(qtbot, tmp_path) -> None:
    from harness_design_studio.gui.tables import Column, DictTableModel, TableView

    theme = ThemeManager()
    settings = QSettings(str(tmp_path / "t.ini"), QSettings.Format.IniFormat)
    model = DictTableModel([Column("a", "A"), Column("b", "B")], [{"a": 1, "b": 2}], theme)
    view = TableView(model, theme, name="T", settings=settings, key="demo")
    qtbot.addWidget(view)
    assert view.column_menu is not None
    view.column_menu.set_hidden(1, True)
    assert view.isColumnHidden(1)
    again = TableView(model, theme, name="T", settings=settings, key="demo")
    qtbot.addWidget(again)
    assert again.isColumnHidden(1)
    assert TableView(model, theme, name="T").column_menu is None  # no key, nothing to keep it in


def test_the_unit_table_has_a_new_unit_button_that_asks_the_window(win) -> None:
    t = shown(win, "units")
    asked: list[bool] = []
    t.newUnitRequested.disconnect()  # (the window's own handler opens a menu and waits for a click)
    t.newUnitRequested.connect(lambda: asked.append(True))
    t.add_btn.click()
    assert asked == [True] and t.add_btn.text() == strings.NEW_UNIT
    win.ctl.project.read_only = True
    win.ctl.stateChanged.emit()
    assert not t.add_btn.isEnabled()
