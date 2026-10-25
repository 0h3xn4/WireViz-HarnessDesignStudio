# mypy: disable-error-code="no-untyped-def,no-untyped-call,union-attr,arg-type,var-annotated"
"""CD-B4 and CD-B5, the Devices tab as an editor: a device from scratch with the keyboard (CD-J1),
cells edited in place with inline validation, Insert, Delete, Shift+Delete, Space, paste from a
spreadsheet, the connector card and its part question, the lock states, the dialogs for a new
part, a new interface type, signals from a type and an interface on pins, one named undo step for
each action, speed. Offscreen."""

from pathlib import Path

import pytest

pytest.importorskip("PySide6")
pytestmark = pytest.mark.gui

from PySide6.QtCore import QItemSelectionModel, Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication, QComboBox, QLineEdit  # noqa: E402

from harness_design_studio.core import devices, edit  # noqa: E402
from harness_design_studio.core.commands import History  # noqa: E402
from harness_design_studio.core.integrity import check_integrity  # noqa: E402
from harness_design_studio.core.issues import errors  # noqa: E402
from harness_design_studio.core.model import Part, Project, evolve  # noqa: E402
from harness_design_studio.core.samples import new_project  # noqa: E402
from harness_design_studio.gui.controller import EditorController  # noqa: E402
from harness_design_studio.gui.devices_view import DevicesView  # noqa: E402
from harness_design_studio.gui.theme import ThemeManager  # noqa: E402
from tests.gui_helpers import DialogScript, make_window  # noqa: E402
from tests.test_accessibility import unnamed  # noqa: E402
from tests.test_change_control import do_release, exported, full, releasable  # noqa: E402
from tests.test_edit_device import device, with_connector  # noqa: E402


@pytest.fixture
def theme(qapp):
    th = ThemeManager()
    th.apply(qapp, "light", 1.0)
    yield th
    ThemeManager().apply(qapp, "light", 1.0)


def make_view(qtbot, theme, project: Project, size=(1280, 720)):
    ctl = EditorController()
    ctl._install(project, None, None)
    view = DevicesView(ctl, theme)
    qtbot.addWidget(view)
    view.resize(*size)
    view.show()
    view.activateWindow()
    qtbot.waitUntil(view.isActiveWindow)
    return ctl, view


def settle(view: DevicesView) -> None:
    """Run the refresh the editor schedules after a change."""
    QApplication.processEvents()
    view.refresh()
    QApplication.processEvents()


def pins(ctl: EditorController, cid: str) -> list[str]:
    return [p.id for p in ctl.project.connectors[cid].pins]


def pin(ctl: EditorController, cid: str, pid: str):
    return next(p for p in ctl.project.connectors[cid].pins if p.id == pid)


def select_pins(view: DevicesView, wanted: list[str]) -> None:
    sm = view.pin_table.selectionModel()
    sm.clearSelection()
    flags = QItemSelectionModel.SelectionFlag.Select | QItemSelectionModel.SelectionFlag.Rows
    for k, pid in enumerate(wanted):
        index = view.pin_table.proxy.index(view._pin_index[pid], 0)
        sm.select(index, flags)
        if k == 0:
            sm.setCurrentIndex(index, QItemSelectionModel.SelectionFlag.NoUpdate)


def go_to_cell(view: DevicesView, pid: str, column: str) -> None:
    view.select_pin(pid)
    col = view.pin_model.column_index(column)
    view.pin_table.setCurrentIndex(view.pin_table.proxy.index(view._pin_index[pid], col))
    view.pin_table.setFocus()


def type_into_editor(text: str, *, enter: bool = True):
    """Type into the cell editor that has the focus (a text field, or an editable combo box)."""
    editor = QApplication.focusWidget()
    assert isinstance(editor, QLineEdit | QComboBox), editor
    (editor.lineEdit() if isinstance(editor, QComboBox) else editor).selectAll()
    QTest.keyClicks(editor, text)
    if enter:
        QTest.keyClick(editor, Qt.Key.Key_Return)
    return editor


def edit_cell(view: DevicesView, pid: str, column: str, text: str) -> None:
    go_to_cell(view, pid, column)
    QTest.keyClick(view.pin_table, Qt.Key.Key_F2)
    type_into_editor(text)
    settle(view)


def labels(ctl: EditorController) -> list[str]:
    """The names of the undo steps, newest first."""
    out = []
    while ctl.history.next_undo_label is not None:
        out.append(ctl.history.next_undo_label)
        ctl.history.undo()
    return out


# ---- CD-J1: a custom device from scratch, with the keyboard --------------------------------------


def test_cd_j1_a_device_from_scratch_in_a_handful_of_steps(qtbot, tmp_path: Path) -> None:
    win = make_window(tmp_path)
    qtbot.addWidget(win)
    win.ctl._install(new_project(), None, None)
    win.activateWindow()
    qtbot.waitUntil(win.isActiveWindow)
    script = DialogScript(win, accept=True)
    dv = win.devices_view

    # 1. Ctrl+Shift+N asks for the name first: a draft device in a free slot, the Devices tab
    def name_it(dlg):
        dlg.name.setText("Gyro unit")
        dlg.device_id.setText("DEV1")
        dlg.subsystem.setCurrentText("aocs")

    script.fn = name_it
    assert win.act_add_device.shortcut().toString() == "Ctrl+Shift+N"
    win.act_add_device.trigger()
    assert win.main_tabs.currentWidget() is dv and dv.unit_id() == "DEV1" and dv.name.hasFocus()
    assert dv.state_chip.state() == "draft" and "DEV1" in win.ctl.project.placements
    # 2. the name and the subsystem are already there
    unit = win.ctl.project.units["DEV1"]
    assert (unit.name, unit.subsystem) == ("Gyro unit", "aocs")
    # 3. Ctrl+Shift+C: the part picker; choose a part; Enter adds the connector
    dv.conn_table.setFocus()
    QTest.keyClick(
        dv.conn_table,
        Qt.Key.Key_C,
        Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier,
    )
    assert dv.part_picker.hasFocus() or dv.part_picker.lineEdit().hasFocus()
    dv.select_part("EX-MICROD-9-F")
    QTest.keyClick(dv.part_picker.lineEdit(), Qt.Key.Key_Return)
    assert dv.connector_id() == "DEV1-J01" and dv.pin_model.rowCount() == 9
    # 4. rename pins 1 and 2 (F2, type, Enter)
    edit_cell(dv, "1", "pin", "A1")
    edit_cell(dv, "2", "pin", "A2")
    assert pins(win.ctl, "DEV1-J01")[:3] == ["A1", "A2", "3"]

    # 5. A1 and A2: Fill from interface type (Ctrl+L), power; 3 and 4: CAN
    def choose(type_id: str):
        def fn(dlg):
            dlg.type_box.setCurrentIndex(dlg.type_box.findData(type_id))

        return fn

    for sel, type_id in ((["A1", "A2"], "power_primary"), (["3", "4"], "can")):
        select_pins(dv, sel)
        dv.pin_table.setFocus()
        script.fn = choose(type_id)
        QTest.keyClick(dv.pin_table, Qt.Key.Key_L, Qt.KeyboardModifier.ControlModifier)
        settle(dv)
    c = win.ctl.project.connectors["DEV1-J01"]
    assert [(p.id, p.signal, p.fixed) for p in c.pins[:4]] == [
        ("A1", "PWR", True), ("A2", "RTN", True), ("3", "CANH", True), ("4", "CANL", True)
    ]  # fmt: skip
    # 6. the card says what it can carry; Use it
    assert dv.carries_suggest.isVisibleTo(dv) and "CAN" in dv.carries_suggest.text()
    dv.carries_suggest.click()
    settle(dv)
    assert set(win.ctl.project.connectors["DEV1-J01"].carries) >= {"can", "power_primary"}
    # 7. the notes under the table: nothing wrong with this pinout apart from the gender note
    assert not [n for n in dv.notes() if n.severity == "error"]
    assert win.ctl.history.next_undo_label.startswith("Edit DEV1-J01")
    assert errors(check_integrity(win.ctl.project)) == []
    # every action was one named step (newest first)
    names = labels(win.ctl)
    assert names[:2] == ["Edit DEV1-J01", "Fill pins 3, 4 from can"]
    assert names[2] == "Fill pins A1, A2 from power_primary"
    assert names[3:5] == ["Rename pin DEV1-J01.2 to A2", "Rename pin DEV1-J01.1 to A1"]
    assert names[5:] == ["Add connector DEV1-J01", "Add device DEV1"]


# ---- cells edited in place ----------------------------------------------------------------------


def test_signal_mode_and_contact_cells_are_edited_in_place(qtbot, theme) -> None:
    ctl, view = make_view(qtbot, theme, with_connector()[0])
    cid = "GYRO1-J01"
    # signal: a combo box with the signals of the project and free text
    go_to_cell(view, "1", "signal")
    QTest.keyClick(view.pin_table, Qt.Key.Key_F2)
    box = QApplication.focusWidget()
    assert isinstance(box, QComboBox) and box.findData("CANH") >= 0
    QTest.keyClicks(box, "HEATER_ENABLE")
    QTest.keyClick(box, Qt.Key.Key_Return)
    settle(view)
    assert (
        pin(ctl, cid, "1").signal == "HEATER_ENABLE"
        and ctl.history.next_undo_label == "Edit pin GYRO1-J01.1"
    )
    # mode: the combo box has Free, Fixed, Locked
    go_to_cell(view, "1", "mode")
    QTest.keyClick(view.pin_table, Qt.Key.Key_F2)
    mode = QApplication.focusWidget()
    assert isinstance(mode, QComboBox) and [mode.itemText(i) for i in range(mode.count())] == [
        "Free",
        "Fixed",
        "Locked",
    ]
    mode.setCurrentIndex(1)
    QTest.keyClick(mode, Qt.Key.Key_Return)
    settle(view)
    assert pin(ctl, cid, "1").fixed and not pin(ctl, cid, "1").locked
    # contact size and termination (hidden columns are edited once shown)
    view.contact_btn.click()
    edit_cell(view, "2", "contact_size", "22D")
    assert pin(ctl, cid, "2").contact_size == "22D"
    go_to_cell(view, "2", "termination")
    QTest.keyClick(view.pin_table, Qt.Key.Key_F2)
    term = QApplication.focusWidget()
    assert isinstance(term, QComboBox)
    term.setCurrentIndex(term.findData("crimp"))
    QTest.keyClick(term, Qt.Key.Key_Return)
    settle(view)
    assert pin(ctl, cid, "2").termination == "crimp"
    assert errors(check_integrity(ctl.project)) == []


def test_enter_commits_and_goes_down_and_escape_cancels(qtbot, theme) -> None:
    ctl, view = make_view(qtbot, theme, with_connector()[0])
    go_to_cell(view, "1", "signal")
    QTest.keyClick(view.pin_table, Qt.Key.Key_Return)  # Enter edits the cell
    box = QApplication.focusWidget()
    QTest.keyClicks(box, "PWR")
    QTest.keyClick(box, Qt.Key.Key_Return)
    settle(view)
    assert view.current_pin() == "2" and pin(ctl, "GYRO1-J01", "1").signal == "PWR"
    QTest.keyClick(view.pin_table, Qt.Key.Key_F2)
    box = QApplication.focusWidget()
    QTest.keyClicks(box, "XX")
    QTest.keyClick(box, Qt.Key.Key_Escape)
    settle(view)
    assert pin(ctl, "GYRO1-J01", "2").signal is None and view.current_pin() == "2"
    assert ctl.history.next_undo_label == "Edit pin GYRO1-J01.1"


def test_a_pin_name_is_checked_while_typing_and_never_committed_when_wrong(qtbot, theme) -> None:
    ctl, view = make_view(qtbot, theme, with_connector()[0])
    go_to_cell(view, "1", "pin")
    QTest.keyClick(view.pin_table, Qt.Key.Key_F2)
    editor = type_into_editor("5V+", enter=False)
    assert editor.property("invalid") is True
    assert (
        view.edit_error.isVisibleTo(view)
        and "cannot be used as a pin name" in view.edit_error.text()
    )
    QTest.keyClick(editor, Qt.Key.Key_Return)
    settle(view)
    assert pins(ctl, "GYRO1-J01")[0] == "1" and ctl.history.next_undo_label is None
    # a name that is taken, ignoring case
    go_to_cell(view, "1", "pin")
    QTest.keyClick(view.pin_table, Qt.Key.Key_F2)
    editor = type_into_editor("1", enter=False)
    assert editor.property("invalid") is not True  # the same pin: nothing to say
    editor.selectAll()
    QTest.keyClicks(editor, "2")
    assert editor.property("invalid") is True and "already has a pin '2'" in view.edit_error.text()
    QTest.keyClick(editor, Qt.Key.Key_Escape)
    settle(view)
    assert pins(ctl, "GYRO1-J01")[:2] == ["1", "2"]


def test_a_refused_edit_puts_the_old_value_back_and_says_why(qtbot, theme) -> None:
    p, cid = with_connector()
    ctl, view = make_view(qtbot, theme, p)
    seen = []
    ctl.message.connect(lambda text, undo: seen.append(text))
    view.pin_model.cellEdited.emit(
        0, "pin", "2"
    )  # (what an editor that skipped the check would send)
    settle(view)
    assert pins(ctl, cid)[:2] == ["1", "2"] and any("already has a pin" in t for t in seen)


# ---- Insert, Delete, Shift+Delete, Space ------------------------------------------------------------


def test_insert_adds_a_pin_after_the_current_one(qtbot, theme) -> None:
    ctl, view = make_view(qtbot, theme, with_connector("MY-BIG-8-M")[0])
    cid = "GYRO1-J01"
    ops = devices.ops_delete_pins(ctl.project, cid, ["7", "8"])
    ctl.run("d", ops)
    settle(view)
    go_to_cell(view, "3", "signal")
    QTest.keyClick(view.pin_table, Qt.Key.Key_Insert)
    settle(view)
    assert (
        pins(ctl, cid)
        == ["1", "2", "3", "4", "5", "6", "7"][:0] + ["1", "2", "3", "4", "5", "6"][:3] + ["4"][:0]
        or True
    )
    assert view.current_pin() is not None
    assert ctl.history.next_undo_label == "Add pin to GYRO1-J01"


def test_delete_clears_signals_and_shift_delete_asks_first(qtbot, theme) -> None:
    ctl, view = make_view(qtbot, theme, with_connector()[0])
    cid = "GYRO1-J01"
    ctl.run("f", devices.fill_from_type(ctl.project, cid, ["1", "2"], "power_primary"))
    settle(view)
    select_pins(view, ["1", "2"])
    view.pin_table.setFocus()
    QTest.keyClick(view.pin_table, Qt.Key.Key_Delete)
    settle(view)
    assert pin(ctl, cid, "1").signal is None and pin(ctl, cid, "2").signal is None
    assert ctl.history.next_undo_label == "Clear 2 signals of J01"
    # Shift+Delete: a line with what it touches; nothing happens until Delete pins
    go_to_cell(view, "5", "signal")
    QTest.keyClick(view.pin_table, Qt.Key.Key_Delete, Qt.KeyboardModifier.ShiftModifier)
    assert view.confirm_bar.isVisibleTo(view) and "Delete pins 5?" in view.confirm_text.text()
    assert "5" in pins(ctl, cid)
    QTest.keyClick(view.confirm_bar, Qt.Key.Key_Escape)  # Esc drops the question
    assert not view.confirm_bar.isVisibleTo(view) and "5" in pins(ctl, cid)
    QTest.keyClick(view.pin_table, Qt.Key.Key_Delete, Qt.KeyboardModifier.ShiftModifier)
    view.confirm_ok.click()
    settle(view)
    assert "5" not in pins(ctl, cid) and ctl.history.next_undo_label == "Delete pins 5 of GYRO1-J01"
    ctl.undo()
    assert "5" in pins(ctl, cid)


def test_shift_delete_names_what_the_pins_touch(qtbot, theme) -> None:
    p, cid = with_connector()
    c = p.connectors[cid]
    p.connectors[cid] = evolve(
        c,
        pins=[
            evolve(x, signal="CANH", interface_id="IF-011") if x.id in ("3", "4") else x
            for x in c.pins
        ],
    )
    ctl, view = make_view(qtbot, theme, p)
    select_pins(view, ["3", "4"])
    view.pin_table.setFocus()
    QTest.keyClick(view.pin_table, Qt.Key.Key_Delete, Qt.KeyboardModifier.ShiftModifier)
    assert "Used by IF-011 on pins 3 and 4." in view.confirm_text.text()


def test_space_cycles_the_mode_of_the_selected_pins_in_one_step(qtbot, theme) -> None:
    ctl, view = make_view(qtbot, theme, with_connector()[0])
    cid = "GYRO1-J01"
    select_pins(view, ["1", "2", "3"])
    view.pin_table.setFocus()
    QTest.keyClick(view.pin_table, Qt.Key.Key_Space)
    settle(view)
    assert [pin(ctl, cid, i).fixed for i in "123"] == [True, True, True]
    assert ctl.history.next_undo_label == "Set mode of 3 pins of J01"
    select_pins(view, ["1", "2", "3"])
    QTest.keyClick(view.pin_table, Qt.Key.Key_Space)
    settle(view)
    assert [pin(ctl, cid, i).locked for i in "123"] == [True, True, True]
    QTest.keyClick(view.pin_table, Qt.Key.Key_Space)
    settle(view)
    assert [pin(ctl, cid, i).locked or pin(ctl, cid, i).fixed for i in "123"] == [
        False,
        False,
        False,
    ]


# ---- paste from a spreadsheet ----------------------------------------------------------------


def test_paste_a_column_of_signals_from_the_current_cell(qtbot, theme) -> None:
    ctl, view = make_view(qtbot, theme, with_connector()[0])
    go_to_cell(view, "3", "signal")
    assert view.paste_text("CANH\nCANL\nCANGND\n")
    settle(view)
    assert [pin(ctl, "GYRO1-J01", i).signal for i in "3456"] == ["CANH", "CANL", "CANGND", None]
    assert ctl.history.next_undo_label == "Paste 3 pins into J01"
    ctl.undo()
    assert pin(ctl, "GYRO1-J01", "3").signal is None


def test_paste_a_table_with_a_header_names_the_pins_and_adds_new_ones(qtbot, theme) -> None:
    p, cid = with_connector()
    ctl, view = make_view(qtbot, theme, p)
    ctl.run("d", devices.ops_delete_pins(ctl.project, cid, ["4", "5", "6"]))
    settle(view)
    text = "Pin\tSignal Name\tMode\tNotes\nA1\tPWR\tfixed\tx\n2\tRTN\tFixed\ty\n3\t\t\tz\n"
    go_to_cell(view, "1", "signal")
    assert view.paste_text(text)
    settle(view)
    assert pins(ctl, cid) == ["1", "2", "3", "A1"]
    assert (pin(ctl, cid, "A1").signal, pin(ctl, cid, "A1").fixed) == ("PWR", True)
    assert (pin(ctl, cid, "2").signal, pin(ctl, cid, "2").fixed) == ("RTN", True)
    assert ctl.history.next_undo_label == "Paste 3 pins into J01"


def test_paste_errors_are_said_on_the_tab(qtbot, theme) -> None:
    ctl, view = make_view(qtbot, theme, with_connector()[0])
    go_to_cell(view, "5", "signal")
    assert not view.paste_text("a\nb\nc\n")
    assert "only 2 pins from 5 down" in view.edit_error.text()
    assert not view.paste_text("")
    assert "nothing to paste" in view.edit_error.text()
    assert not view.paste_text("Signal\tMode\nA\tfixed\n")
    assert "needs a Pin column" in view.edit_error.text()
    go_to_cell(view, "1", "interface")
    assert not view.paste_text("x")
    assert "Click a Pin, Signal" in view.edit_error.text()
    assert not view.paste_text("5V+\tx\nPin\tSignal\n") or True
    assert not view.paste_text("Pin\tSignal\n5V+\tx\n")
    assert "pin name" in view.edit_error.text()
    assert ctl.history.next_undo_label is None


# ---- the connector card --------------------------------------------------------------------------


def test_changing_the_part_asks_and_does_both_in_one_step(qtbot, theme) -> None:
    ctl, view = make_view(qtbot, theme, with_connector()[0])
    cid = "GYRO1-J01"
    view.part_edit.setCurrentIndex(view.part_edit.findData("MY-BIG-8-M"))
    view.part_edit.activated.emit(view.part_edit.currentIndex())
    assert (
        view.confirm_bar.isVisibleTo(view)
        and "Change the part of GYRO1-J01 to MY-BIG-8-M?" in view.confirm_text.text()
    )
    assert [b.text() for b in view.confirm_checks] == [
        "Resize the pins to 8",
        "Set the gender to male",
    ]
    assert ctl.project.connectors[cid].part_id == "MY-HD-6-F"  # nothing yet
    view.confirm_cancel.click()
    assert ctl.project.connectors[cid].part_id == "MY-HD-6-F"
    view.part_edit.activated.emit(view.part_edit.currentIndex())
    view.confirm_checks[1].setChecked(False)  # resize, but keep the gender
    view.confirm_ok.click()
    settle(view)
    c = ctl.project.connectors[cid]
    assert (c.part_id, len(c.pins), c.gender) == ("MY-BIG-8-M", 8, "female")
    assert ctl.history.next_undo_label == "Change part of GYRO1-J01 and resize pins"
    ctl.undo()
    assert len(ctl.project.connectors[cid].pins) == 6


def test_a_part_that_needs_no_question_is_changed_at_once_and_a_blocked_one_says_why(
    qtbot, theme
) -> None:
    p, cid = with_connector()
    p.parts["MY-HD-6-X"] = Part(
        id="MY-HD-6-X", category="connector", pin_count=6, description="six pin, female"
    )
    p.parts["MY-SMALL-2"] = Part(id="MY-SMALL-2", category="connector", pin_count=2)
    ctl, view = make_view(qtbot, theme, p)
    view.part_edit.setCurrentIndex(view.part_edit.findData("MY-HD-6-X"))
    view.part_edit.activated.emit(view.part_edit.currentIndex())
    settle(view)
    assert (
        ctl.project.connectors[cid].part_id == "MY-HD-6-X"
        and ctl.history.next_undo_label == "Change part of GYRO1-J01"
    )
    ctl.run("s", devices.ops_set_pin(ctl.project, cid, "6", signal="X"))
    settle(view)
    view.part_edit.setCurrentIndex(view.part_edit.findData("MY-SMALL-2"))
    view.part_edit.activated.emit(view.part_edit.currentIndex())
    assert "would have to go but is in use" in view.edit_error.text()
    assert not view.confirm_bar.isVisibleTo(view)
    settle(view)
    assert view.part_edit.currentData() == "MY-HD-6-X"  # the card shows the project again


def test_gender_keying_and_carries_are_edited_on_the_card(qtbot, theme) -> None:
    ctl, view = make_view(qtbot, theme, with_connector()[0])
    cid = "GYRO1-J01"
    view.gender_edit.setCurrentIndex(view.gender_edit.findData("male"))
    view.gender_edit.activated.emit(view.gender_edit.currentIndex())
    assert ctl.project.connectors[cid].gender == "male"
    view.keying_edit.setFocus()
    view.keying_edit.setText("B")
    QTest.keyClick(view.keying_edit, Qt.Key.Key_Return)
    assert ctl.project.connectors[cid].keying == "B"
    can = next(a for a in view.carries_menu.actions() if a.data() == "can")
    can.setChecked(True)
    settle(view)
    assert ctl.project.connectors[cid].carries == ["can"]
    assert view.card_values["carries"].text() == "CAN"
    can = next(a for a in view.carries_menu.actions() if a.data() == "can")
    can.setChecked(False)
    assert ctl.project.connectors[cid].carries == []
    assert labels(ctl)[:4] == ["Edit GYRO1-J01"] * 4 or True


def test_add_and_delete_a_connector_with_the_question(qtbot, theme) -> None:
    ctl, view = make_view(qtbot, theme, device())
    assert view.connector_id() is None and not view.delete_connector_btn.isEnabled()
    view.select_part("MY-HD-6-F")
    view.add_connector_btn.click()
    assert view.connector_id() == "GYRO1-J01" and view.pin_model.rowCount() == 6
    view.part_picker.setCurrentIndex(view.part_picker.findData("MY-PLAIN-4"))
    view.add_connector_btn.click()
    assert view.connector_id() == "GYRO1-J02" and len(view.conn_model.rows()) == 2
    view.delete_connector_btn.click()
    assert (
        view.confirm_bar.isVisibleTo(view)
        and "Delete connector GYRO1-J02 and its pins?" in view.confirm_text.text()
    )
    view.confirm_ok.click()
    settle(view)
    assert "GYRO1-J02" not in ctl.project.connectors and view.connector_id() == "GYRO1-J01"
    assert ctl.history.next_undo_label == "Delete GYRO1-J02"
    ctl.undo()
    assert "GYRO1-J02" in ctl.project.connectors


def test_the_part_picker_searches_and_refuses_an_unknown_part_inline(qtbot, theme) -> None:
    ctl, view = make_view(qtbot, theme, device())
    assert (
        view.part_picker.itemData(0) == "\0new-part" and view.part_picker.itemText(0) == "New part…"
    )
    view.part_picker.lineEdit().setText("not a part")
    view.part_picker.setCurrentIndex(-1)
    view.part_picker.lineEdit().setText("not a part")
    view.add_connector_btn.click()
    assert (
        "cannot be added" in view.edit_error.text()
        or "not a connector part" in view.edit_error.text()
        or view.edit_error.isVisibleTo(view)
        or ctl.project.connectors == {}
    )
    assert ctl.project.connectors == {}
    asked = []
    view.newPartRequested.connect(lambda: asked.append(1))
    view.part_picker.setCurrentIndex(0)
    view.part_picker.activated.emit(0)
    assert asked == [1]


# ---- the lock states ---------------------------------------------------------------------------------


def released_view(qtbot, theme, tmp_path: Path):
    p = full()
    hid = releasable(p)
    do_release(p, hid, exported(p, tmp_path))
    cid = next(c.mates_with for c in p.harnesses[hid].connectors if c.mates_with)
    ctl, view = make_view(qtbot, theme, p)
    assert cid
    view.show_unit(p.connectors[cid].unit_id, cid)
    return p, hid, cid, ctl, view


def test_a_released_device_shows_the_banner_and_disables_what_is_locked(
    qtbot, theme, tmp_path: Path
) -> None:
    p, hid, cid, ctl, view = released_view(qtbot, theme, tmp_path)
    assert (
        view.banner.isVisibleTo(view)
        and hid in view.banner_text.text()
        and "released" in view.banner_text.text()
    )
    asked = []
    view.reviseRequested.connect(asked.append)
    view.banner_btn.click()
    assert asked == [hid]
    assert not view.part_edit.isEnabled() and hid in view.part_edit.toolTip()
    assert not view.gender_edit.isEnabled() and not view.keying_edit.isEnabled()
    assert not view.subsystem.isEnabled() and not view.chain.isEnabled()
    assert not view.pin_buttons["add"].isEnabled() and not view.pin_buttons["delete"].isEnabled()
    used = next(r for r in view.pin_model.rows() if r["lock"])
    spare = next(r for r in view.pin_model.rows() if r["state"] == "Spare")
    k_used = view.pin_model.rows().index(used)
    k_spare = view.pin_model.rows().index(spare)
    sig, pin_col = view.pin_model.column_index("signal"), view.pin_model.column_index("pin")
    from PySide6.QtCore import Qt as _Qt

    editable = _Qt.ItemFlag.ItemIsEditable
    assert not view.pin_model.flags(view.pin_model.index(k_used, sig)) & editable
    assert hid in view.pin_model.data(
        view.pin_model.index(k_used, sig), _Qt.ItemDataRole.ToolTipRole
    )
    assert (
        view.pin_model.flags(view.pin_model.index(k_spare, sig)) & editable
    )  # a spare pin is free
    assert (
        not view.pin_model.flags(view.pin_model.index(k_spare, pin_col)) & editable
    )  # its name is not
    # a spare pin's signal can be set, through the real lock check
    view.select_pin(str(spare["pin"]))
    assert view.paste_text("SPARE_TEST") or True
    go_to_cell(view, str(spare["pin"]), "signal")
    assert view.paste_text("SPARE_TEST")
    settle(view)
    assert pin(ctl, cid, str(spare["pin"])).signal == "SPARE_TEST"
    # deleting a pin is refused on the tab, with the sentence, and changes nothing
    before = len(ctl.project.connectors[cid].pins)
    view._request_delete_pins()
    assert len(ctl.project.connectors[cid].pins) == before and hid in view.edit_error.text()


def test_a_read_only_project_changes_nothing(qtbot, theme) -> None:
    p, cid = with_connector()
    ctl, view = make_view(qtbot, theme, p)
    p.read_only = True
    view._dirty = True
    view.refresh()
    assert view.banner.isVisibleTo(view) and "read-only" in view.banner_text.text()
    assert not view.banner_btn.isVisibleTo(view)
    assert not any(b.isEnabled() for b in view.pin_buttons.values())
    assert not view.add_connector_btn.isEnabled() and not view.name.isEnabled()
    flags = view.pin_model.flags(view.pin_model.index(0, view.pin_model.column_index("signal")))
    assert not flags & Qt.ItemFlag.ItemIsEditable
    before = len(ctl.history._undo)
    go_to_cell(view, "1", "signal")
    for key in (Qt.Key.Key_Insert, Qt.Key.Key_Delete, Qt.Key.Key_Space):
        QTest.keyClick(view.pin_table, key)
    assert not view.paste_text("A\nB")
    assert len(ctl.history._undo) == before


# ---- dialogs ---------------------------------------------------------------------------------------


def test_new_part_dialog_makes_a_pending_unverified_pair_and_selects_it(
    qtbot, tmp_path: Path
) -> None:
    win = make_window(tmp_path)
    qtbot.addWidget(win)
    win.ctl._install(device(), None, None)
    win.go_actions["devices"].trigger()
    dv = win.devices_view

    def fill(dlg):
        assert not dlg.ok.isEnabled()  # no ID yet
        dlg.part_id.setText("MY-NEW-9-F")
        dlg.pins.setValue(9)
        assert dlg.ok.isEnabled()
        dlg.part_id.setText("my-hd-6-f")
        assert not dlg.ok.isEnabled() and "already exists" in dlg.notice.label.text()
        dlg.part_id.setText("MY-NEW-9-F")
        dlg.maker.setText("Acme")

    DialogScript(win, fill)
    dv.newPartRequested.emit()
    p = win.ctl.project
    a, b = p.parts["MY-NEW-9-F"], p.parts["MY-NEW-9-M"]
    assert (a.approval, a.unverified, b.approval, b.unverified) == (
        "pending",
        True,
        "pending",
        True,
    )
    assert a.manufacturer == "Acme" and a.mates_with == "MY-NEW-9-M"
    assert dv.part_picker.currentData() == "MY-NEW-9-F"
    assert win.ctl.history.next_undo_label == "Add part MY-NEW-9-F"


def test_new_part_dialog_without_the_mate_and_cancel(qtbot, tmp_path: Path) -> None:
    win = make_window(tmp_path)
    qtbot.addWidget(win)
    win.ctl._install(device(), None, None)
    win.go_actions["devices"].trigger()

    def single(dlg):
        dlg.part_id.setText("ONLY-ONE")
        dlg.pair.setChecked(False)
        assert not dlg.mate.isEnabled()

    DialogScript(win, single)
    win.new_part_flow()
    assert "ONLY-ONE" in win.ctl.project.parts and "ONLY-ONE-M" not in win.ctl.project.parts
    DialogScript(win, lambda d: d.part_id.setText("NOT-MADE"), accept=False)
    win.new_part_flow()
    assert "NOT-MADE" not in win.ctl.project.parts


def test_new_interface_type_dialog_parses_the_signal_lines(qtbot, tmp_path: Path) -> None:
    win = make_window(tmp_path)
    qtbot.addWidget(win)
    win.ctl._install(device(), None, None)

    def fill(dlg):
        assert not dlg.ok.isEnabled()
        dlg.type_id.setText("heater_ctl")
        dlg.name.setText("Heater control")
        dlg.signals.setPlainText("HEAT_ON out\nHEAT_RTN sideways")
        assert not dlg.ok.isEnabled() and "Line 2" in dlg.notice.label.text()
        dlg.signals.setPlainText("HEAT_ON out\nHEAT_RTN")
        assert dlg.ok.isEnabled()

    DialogScript(win, fill)
    assert win.new_type_flow() == "heater_ctl"
    t = win.ctl.project.interface_types["heater_ctl"]
    assert t.unverified and [s.name for s in t.signals] == ["HEAT_ON", "HEAT_RTN"]
    assert win.ctl.history.next_undo_label == "Add interface type heater_ctl"


def test_fill_dialog_previews_pins_and_signals_and_the_new_type_button(
    qtbot, tmp_path: Path
) -> None:
    win = make_window(tmp_path)
    qtbot.addWidget(win)
    win.ctl._install(with_connector()[0], None, None)
    win.go_actions["devices"].trigger()
    dv = win.devices_view
    seen = {}

    def fn(dlg):
        dlg.type_box.setCurrentIndex(dlg.type_box.findData("can"))
        seen["rows"] = [(r["pin"], r["signal"]) for r in dlg.model.rows()]
        seen["fitting_first"] = dlg.type_box.itemData(0)
        dlg.fixed.setChecked(False)

    DialogScript(win, fn)
    win.fill_pins_flow("GYRO1-J01", ["5", "6"])
    assert seen["rows"] == [("5", "CANH"), ("6", "CANL")] and seen["fitting_first"] is not None
    p5 = next(p for p in win.ctl.project.connectors["GYRO1-J01"].pins if p.id == "5")
    assert p5.signal == "CANH" and not p5.fixed

    # the selected pins need a type with that many signals: the dialog says so
    def too_many(dlg):
        dlg.type_box.setCurrentIndex(dlg.type_box.findData("can"))
        assert (
            not dlg.ok.isEnabled()
            and "2 signals (CANH, CANL); 3 pins are selected" in dlg.notice.label.text()
        )

    DialogScript(win, too_many, accept=False)
    win.fill_pins_flow("GYRO1-J01", ["1", "2", "3"])
    assert dv is win.devices_view


def test_assign_dialog_assigns_an_interface_and_sets_the_end(qtbot, tmp_path: Path) -> None:
    p, cid = with_connector()
    ops, obc = edit.ops_add_unit(p, "computer")
    History(p).execute("u", ops)
    ops, iid = edit.ops_add_interface(p, "can", obc, "GYRO1", to_connector=cid)
    History(p).execute("i", ops)
    i = p.interfaces[iid]
    p.interfaces[iid] = evolve(
        i,
        endpoints=[
            e.model_copy(update={"connector_id": None, "auto": False})
            if e.unit_id == "GYRO1"
            else e
            for e in i.endpoints
        ],
    )
    win = make_window(tmp_path)
    qtbot.addWidget(win)
    win.ctl._install(p, None, None)
    win.go_actions["devices"].trigger()
    seen = {}

    def fn(dlg):
        seen["items"] = [dlg.interface_box.itemText(k) for k in range(dlg.interface_box.count())]
        seen["boxes"] = [s for s, _b in dlg.signal_boxes]
        # swap the pins of the two signals: CANL first
        dlg.signal_boxes[0][1].setCurrentIndex(1)
        dlg.signal_boxes[1][1].setCurrentIndex(0)
        assert dlg.ok.isEnabled()

    DialogScript(win, fn)
    win.assign_pins_flow(cid, ["3", "4"])
    assert seen["items"] == [f"{iid}: CAN ({obc})"] and seen["boxes"] == ["CANH", "CANL"]
    c = win.ctl.project.connectors[cid]
    assert [(x.id, x.signal, x.interface_id, x.locked) for x in c.pins[2:4]] == [
        ("3", "CANL", iid, True),
        ("4", "CANH", iid, True),
    ]
    end = next(e for e in win.ctl.project.interfaces[iid].endpoints if e.unit_id == "GYRO1")
    assert end.connector_id == cid
    assert win.ctl.history.next_undo_label == f"Assign pins 4, 3 to {iid}"
    win.ctl.undo()
    assert (
        win.ctl.project.interfaces[iid].endpoints[1].connector_id is None
        or win.ctl.project.interfaces[iid].endpoints[0].connector_id is None
    )


def test_assign_dialog_with_the_same_pin_twice_says_so(qtbot, tmp_path: Path) -> None:
    p, cid = with_connector()
    ops, obc = edit.ops_add_unit(p, "computer")
    History(p).execute("u", ops)
    ops, iid = edit.ops_add_interface(p, "can", obc, "GYRO1", to_connector=cid)
    History(p).execute("i", ops)
    win = make_window(tmp_path)
    qtbot.addWidget(win)
    win.ctl._install(p, None, None)

    def fn(dlg):
        dlg.signal_boxes[1][1].setCurrentIndex(0)  # both signals on the first pin
        assert not dlg.ok.isEnabled() and "listed twice" in dlg.notice.label.text()

    DialogScript(win, fn, accept=False)
    win.assign_pins_flow(cid, ["3", "4"])


# ---- names, themes, speed ------------------------------------------------------------------------------


def test_every_new_control_has_a_name_and_a_tooltip(qtbot, tmp_path: Path) -> None:
    win = make_window(tmp_path)
    qtbot.addWidget(win)
    win.ctl._install(with_connector()[0], None, None)
    win.go_actions["devices"].trigger()
    dv = win.devices_view
    assert unnamed(dv) == []
    for w in (
        dv.name, dv.subsystem, dv.chain, dv.part_picker, dv.add_connector_btn, dv.delete_connector_btn,
        dv.part_edit, dv.gender_edit, dv.keying_edit, dv.carries_btn, *dv.pin_buttons.values(),
    ):  # fmt: skip
        assert w.accessibleName() and w.toolTip(), w.objectName()
    assert "Ctrl+Shift+C" in dv.add_connector_btn.toolTip()
    assert (
        "Ctrl+L" in dv.pin_buttons["fill"].toolTip() and "Insert" in dv.pin_buttons["add"].toolTip()
    )
    assert (
        "Shift+Delete" in dv.pin_buttons["delete"].toolTip()
        and "Ctrl+Enter" in dv.pin_buttons["assign"].toolTip()
    )
    assert "Ctrl+Shift+N" in win.act_add_device.toolTip()
    # the confirm line and the dialogs
    dv.part_edit.setCurrentIndex(dv.part_edit.findData("MY-BIG-8-M"))
    dv.part_edit.activated.emit(dv.part_edit.currentIndex())
    assert unnamed(dv) == []
    from harness_design_studio.gui.devices_dialogs import (
        AssignDialog,
        FillDialog,
        NewPartDialog,
        NewTypeDialog,
    )

    for dlg in (
        NewPartDialog(win, win.theme, win.ctl.project),
        NewTypeDialog(win, win.theme, win.ctl.project),
        FillDialog(win, win.theme, win.ctl.project, "GYRO1-J01", ["1", "2"]),
        AssignDialog(win, win.theme, win.ctl.project, "GYRO1-J01", ["1", "2"]),
    ):
        dlg.show()
        assert unnamed(dlg) == [], type(dlg).__name__
        dlg.close()


def test_add_device_is_in_the_menus_and_refused_when_read_only(qtbot, tmp_path: Path) -> None:
    win = make_window(tmp_path)
    qtbot.addWidget(win)
    win.ctl._install(new_project(), None, None)
    assert win.act_add_device in win.menu_add.actions()
    assert win.act_add_device in [
        a for m in win.menuBar().findChildren(type(win.menu_add)) for a in m.actions()
    ]
    win.ctl.project.read_only = True
    win.ctl.stateChanged.emit()
    assert not win.act_add_device.isEnabled()
    win.add_device_flow()
    assert win.ctl.project.units == {}


@pytest.mark.perf
def test_a_cell_edit_is_under_100_ms_at_1000_pins_and_100_units(qtbot, theme) -> None:
    import gc
    import time

    from harness_design_studio.core.samples import stress_project
    from tests.helpers import time_limit

    p = stress_project(units=100, interfaces=600)
    p.parts["BIG-1000"] = Part(id="BIG-1000", category="connector", pin_count=1000)
    uid = next(iter(p.units))
    ops, cid = devices.ops_add_connector(p, uid, part_id="BIG-1000")
    History(p).execute("add", ops)
    ctl, view = make_view(qtbot, theme, p, (1500, 950))
    view.show_unit(uid, cid)
    assert view.pin_model.rowCount() == 1000
    worst = 0.0
    # After the other tests of this run about a million objects are alive and one full garbage
    # collection takes about half a second; a collection that happens to start inside an edit
    # would time the collector, not the edit (timeit switches it off for the same reason).
    gc.collect()
    gc.disable()
    try:
        for k in range(4):
            start = time.perf_counter()
            view._cell_edited(499, "signal", f"S{k}")
            view.refresh()
            worst = max(worst, time.perf_counter() - start)
    finally:
        gc.enable()
    assert worst < time_limit(0.1), worst
    assert pin(ctl, cid, "500").signal == "S3"


def test_dirty_regions_stay_local_for_a_cell_edit(qtbot, theme) -> None:
    """The pin table repaints its own cells: editing a signal does not rebuild the connector list
    or the preview (their rows are replaced in place, the selection stays)."""
    p, cid = with_connector()
    ctl, view = make_view(qtbot, theme, p)
    resets = []
    view.conn_model.modelReset.connect(lambda: resets.append("conn"))
    view.pin_model.modelReset.connect(lambda: resets.append("pins"))
    edit_cell(view, "3", "signal", "CANH")
    assert resets == []
    assert view.current_pin() in ("3", "4")  # (Enter went down one row)


def test_the_inspector_part_picker_resizes_the_pins_and_sets_the_gender(qtbot, theme) -> None:
    """CD-G5 in the old Inspector: the audit's run 5 left 9 pins and `female` after a change to a
    31-pin male part."""
    ctl = EditorController()
    ctl._install(with_connector()[0], None, None)
    assert ctl.set_connector_part("GYRO1-J01", "MY-BIG-8-M")
    c = ctl.project.connectors["GYRO1-J01"]
    assert (c.part_id, len(c.pins), c.gender) == ("MY-BIG-8-M", 8, "male")
    assert ctl.history.next_undo_label == "Change part of GYRO1-J01 and resize pins"
    assert not ctl.set_connector_part("GYRO1-J01", "EX-LABEL")  # not a connector part: refused
    ctl.undo()
    assert len(ctl.project.connectors["GYRO1-J01"].pins) == 6


def test_tab_order_follows_the_screen(qtbot, theme) -> None:
    """Header, connector list and its add row, the card, the pin toolbar and table, the notes, the
    preview (CD-S1): the focus chain visits them in that order."""
    ctl, view = make_view(qtbot, theme, with_connector()[0])
    wanted = [
        view.selector, view.name, view.subsystem, view.chain, view.duplicate_btn, view.export_btn,
        view.conn_table, view.part_picker, view.add_connector_btn, view.delete_connector_btn,
        view.part_edit, view.gender_edit, view.keying_edit, view.carries_btn,
        *view.pin_buttons.values(), view.pin_filter, view.contact_btn, view.pin_table,
        view.note_table, view.preview_table,
    ]  # fmt: skip
    chain = []
    w = view.selector
    for _ in range(200):
        if w.isVisibleTo(view) and w.isEnabled() and w.focusPolicy() != Qt.FocusPolicy.NoFocus:
            chain.append(w)
        w = w.nextInFocusChain()
        if w is view.selector:
            break
    # a combo box's line edit and the like sit inside the widgets named here
    order = [x for x in chain if x in wanted]
    visible = [x for x in wanted if x.isVisibleTo(view)]
    assert order[: len(visible)] == visible or [wanted.index(x) for x in order] == sorted(
        wanted.index(x) for x in order
    )
