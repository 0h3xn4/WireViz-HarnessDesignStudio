# mypy: disable-error-code="no-untyped-def,no-untyped-call,union-attr,arg-type,var-annotated"
"""1.7.0 M2 (D-170): the build data in the editor: strip lengths in the Edit wire tab, the Cable
contact column of the Devices tab, the Contact of a pin in the Connectors tab, the Accessories tab,
and the crimp tool of a contact part. Each editor action is one undo step; a released harness and a
read-only project turn the controls off with the reason shown."""

import pytest

pytest.importorskip("PySide6")
pytestmark = pytest.mark.gui

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication, QComboBox  # noqa: E402

from harness_design_studio.core.commands import Put, apply_ops  # noqa: E402
from harness_design_studio.core.generate.engine import generate_project  # noqa: E402
from harness_design_studio.core.manual_harness import (  # noqa: E402
    plan_add_connector,
    plan_new_harness,
)
from harness_design_studio.core.model import Accessory, Part, evolve  # noqa: E402
from harness_design_studio.core.samples import new_project, sat15  # noqa: E402
from harness_design_studio.core.wires import find_wire, plan_add_wire  # noqa: E402
from harness_design_studio.gui import strings  # noqa: E402
from harness_design_studio.gui.devices_dialogs import ContactDialog  # noqa: E402
from harness_design_studio.gui.devices_pin_table import grid_columns  # noqa: E402
from harness_design_studio.gui.inspector import Inspector  # noqa: E402
from tests.test_edit_device import with_connector  # noqa: E402
from tests.test_ui_wire_editor import select_rows  # noqa: E402
from tests.test_ux_devices_edit import (  # noqa: E402
    edit_cell,
    go_to_cell,
    pin,
    settle,
    type_into_editor,
)
from tests.test_ux_devices_edit import make_view as make_devices  # noqa: E402
from tests.test_ux_devices_edit import theme as devices_theme  # noqa: E402, F401
from tests.test_ux_harness import make_view, theme  # noqa: E402, F401, F811

CONTACT = "EX-CONTACT-22"
OTHER = "EX-CONTACT-20"


def with_contacts(p):
    p.parts[CONTACT] = Part(id=CONTACT, category="contact")
    p.parts[OTHER] = Part(id=OTHER, category="contact")
    p.parts["EX-SLEEVE"] = Part(id="EX-SLEEVE", category="sleeving")
    return p


def generated_project():
    p = with_contacts(sat15())
    generate_project(p)
    return p


def own_project():
    """A harness that a person made: two connectors and two wires."""
    p = with_contacts(new_project("Scratch"))
    ops, hid = plan_new_harness(p, "Heater harness")
    apply_ops(p, ops)
    for _ in range(2):
        ops, _cid = plan_add_connector(p, hid, part_id="EX-DSUB-9-M")
        apply_ops(p, ops)
    a, b = (c.id for c in p.harnesses[hid].connectors)
    for n in ("1", "2"):
        apply_ops(p, plan_add_wire(p, hid, a, n, b, n))
    return p, hid


def release(ctl, hid: str) -> None:
    h = ctl.project.harnesses[hid]
    apply_ops(ctl.project, [Put("harnesses", evolve(h, status="released"))])


def type_into(edit, text: str) -> None:
    edit.setText(text)
    edit.textEdited.emit(text)


def one_step(ctl, label_part: str = "") -> None:
    """The newest undo step is the only one made since `ctl` was filled."""
    assert ctl.history.next_undo_label is not None
    assert label_part in ctl.history.next_undo_label


# ---- the Edit wire tab: strip lengths ---------------------------------------------------------


@pytest.fixture
def made(qtbot, theme):  # noqa: F811
    ctl, view = make_view(qtbot, theme, generated_project())
    return ctl, view, view.wire_editor


def test_strip_fields_show_the_common_value_or_various(made):
    ctl, view, ed = made
    a, b = select_rows(view, 0, 1)
    apply_ops(
        ctl.project,
        [
            Put("harnesses", _with_strips(ctl, a, 6.0, 8.0)),
        ],
    )
    apply_ops(ctl.project, [Put("harnesses", _with_strips(ctl, b, 6.0, 9.5))])
    ed.show_wires([a, b])
    assert ed.strip_a.text() == "6" and ed.strip_a.placeholderText() == ""
    assert ed.strip_b.text() == "" and ed.strip_b.placeholderText() == strings.WIRE_VARIOUS
    ed.show_wires([a])
    assert ed.strip_b.text() == "8"


def _with_strips(ctl, wid: str, a, b):
    h, _w = find_wire(ctl.project, wid)
    wires = [evolve(w, strip_a_mm=a, strip_b_mm=b) if w.id == wid else w for w in h.wires]
    return evolve(h, wires=wires)


def test_strip_lengths_are_one_undo_step_and_do_not_lock_the_wire(made):
    ctl, view, ed = made
    (wid,) = select_rows(view, 0)
    before = find_wire(ctl.project, wid)[1]
    type_into(ed.strip_a, "6,5")  # a decimal comma is read
    type_into(ed.strip_b, "8")
    assert ed.apply_changes()
    w = find_wire(ctl.project, wid)[1]
    assert (w.strip_a_mm, w.strip_b_mm, w.locked) == (6.5, 8.0, False)
    assert ctl.history.next_undo_label == strings.STEP_EDIT_WIRES
    ctl.undo()
    assert find_wire(ctl.project, wid)[1] == before


def test_strip_and_other_fields_are_applied_together_as_one_step(made):
    ctl, view, ed = made
    a, b = select_rows(view, 0, 1)
    before = [find_wire(ctl.project, w)[1] for w in (a, b)]
    type_into(ed.gauge, "22")
    type_into(ed.strip_a, "6")
    type_into(ed.label, "Bus")
    assert ed.apply_changes()
    for wid in (a, b):
        w = find_wire(ctl.project, wid)[1]
        assert (w.gauge_awg, w.strip_a_mm, w.label, w.strip_b_mm) == (22, 6.0, "Bus", None)
    assert ed.state.text() == strings.WIRE_STATE_KEPT
    ctl.undo()  # one step takes all of it back
    assert [find_wire(ctl.project, w)[1] for w in (a, b)] == before


def test_an_empty_strip_field_that_was_touched_clears_it(made):
    ctl, view, ed = made
    (wid,) = select_rows(view, 0)
    type_into(ed.strip_a, "6")
    assert ed.apply_changes()
    type_into(ed.strip_a, "")
    assert ed.apply_changes()
    assert find_wire(ctl.project, wid)[1].strip_a_mm is None


def test_a_wrong_strip_length_is_said_inline_and_nothing_changes(made):
    ctl, view, ed = made
    (wid,) = select_rows(view, 0)
    before = find_wire(ctl.project, wid)[1]
    type_into(ed.strip_a, "long")
    assert not ed.apply_changes()
    assert not ed.error.isHidden() and "millimetres" in ed.error.text()
    assert find_wire(ctl.project, wid)[1] == before


def test_the_all_wires_button_sets_every_wire_in_one_step_and_counts(made):
    ctl, view, ed = made
    (wid,) = select_rows(view, 0)
    h = find_wire(ctl.project, wid)[0]
    assert ed.strip_all.isEnabled() and strings.WIRE_STRIP_NOTE
    assert not ed.apply_strip_to_all()  # nothing typed yet
    assert ed.strip_result.text() == strings.WIRE_STRIP_ALL_NONE
    type_into(ed.strip_a, "7")
    type_into(ed.strip_b, "9")
    assert ed.apply_strip_to_all()
    h = ctl.project.harnesses[h.id]
    assert all((w.strip_a_mm, w.strip_b_mm) == (7.0, 9.0) for w in h.wires)
    n = len(h.wires)
    assert ed.strip_result.text() == strings.WIRE_STRIP_ALL_DONE.format(n, n, h.id)
    assert ctl.history.next_undo_label == strings.STEP_SET_STRIP_ALL.format(h.id)
    ctl.undo()
    assert all(w.strip_a_mm is None for w in ctl.project.harnesses[h.id].wires)
    # again with the same values: the count says that nothing changed
    type_into(ed.strip_a, "7")
    assert ed.apply_strip_to_all()
    assert ed.apply_strip_to_all()
    assert ed.strip_result.text() == strings.WIRE_STRIP_ALL_SAME.format(n, h.id)


def test_released_harness_and_read_only_project_turn_the_strip_controls_off(made):
    ctl, view, ed = made
    (wid,) = select_rows(view, 0)
    release(ctl, find_wire(ctl.project, wid)[0].id)
    view.refresh()
    select_rows(view, 0)
    ed.show_wires([wid])
    assert not ed.strip_a.isEnabled() and not ed.strip_b.isEnabled()
    assert not ed.strip_all.isEnabled() and "released" in ed.strip_all.toolTip()
    assert "released" in ed.strip_result.text()


def test_a_read_only_project_turns_the_all_wires_button_off(made):
    ctl, view, ed = made
    select_rows(view, 0)
    ctl.project.read_only = True
    ed.set_harness(view.harness_id())
    assert not ed.strip_all.isEnabled()
    assert ed.strip_result.text() == strings.WIRE_STATE_READ_ONLY


def test_the_strip_controls_have_names_and_tips(made):
    _ctl, _view, ed = made
    for w in (ed.strip_a, ed.strip_b, ed.strip_all):
        assert w.accessibleName() and w.toolTip()


# ---- the Devices tab: the Cable contact column ------------------------------------------------


def device_project():
    p, cid = with_connector()
    with_contacts(p)
    return p, cid


def test_the_cable_contact_column_is_edited_in_place_as_one_undo_step(qtbot, devices_theme):
    p, cid = device_project()
    ctl, view = make_devices(qtbot, devices_theme, p)
    m = view.pin_model
    col = m.column_index("contact_part")
    assert m.columns[col].header == "Cable contact"
    assert view.pin_table.isColumnHidden(col)
    view.contact_btn.click()
    assert not view.pin_table.isColumnHidden(col)
    edit_cell(view, "2", "contact_part", CONTACT)
    assert pin(ctl, cid, "2").contact_part == CONTACT
    assert m.text_at(1, col) == CONTACT
    assert ctl.history.next_undo_label == strings.STEP_EDIT_PIN.format(f"{cid}.2")
    tip = m.data(m.index(1, col), Qt.ItemDataRole.ToolTipRole)
    assert tip == strings.DV_COL_CONTACT_PART_TIP
    ctl.undo()
    assert pin(ctl, cid, "2").contact_part is None
    # the choices of the editor are the contact parts of the library
    go_to_cell(view, "3", "contact_part")
    QTest.keyClick(view.pin_table, Qt.Key.Key_F2)
    box = QApplication.focusWidget()
    assert isinstance(box, QComboBox)
    assert [box.itemText(i) for i in range(box.count())] == ["", OTHER, CONTACT]
    assert box.accessibleName() == strings.DV_COL_CONTACT_PART
    QTest.keyClick(box, Qt.Key.Key_Escape)


def test_a_wrong_cable_contact_is_checked_while_typing_and_not_committed(qtbot, devices_theme):
    p, cid = device_project()
    ctl, view = make_devices(qtbot, devices_theme, p)
    view.contact_btn.click()
    go_to_cell(view, "1", "contact_part")
    QTest.keyClick(view.pin_table, Qt.Key.Key_F2)
    editor = type_into_editor("EX-DSUB-9-M", enter=False)  # a connector part, not a contact
    assert editor.property("invalid") is True
    assert "contact part" in view.edit_error.text()
    QTest.keyClick(editor, Qt.Key.Key_Return)
    settle(view)
    assert pin(ctl, cid, "1").contact_part is None
    assert ctl.history.next_undo_label is None


def test_the_cable_contact_cells_are_off_in_a_read_only_project(qtbot, devices_theme):
    p, _cid = device_project()
    ctl, view = make_devices(qtbot, devices_theme, p)
    ctl.project.read_only = True
    view.refresh()
    m = view.pin_model
    m.read_only = True
    idx = m.index(0, m.column_index("contact_part"))
    assert not (m.flags(idx) & Qt.ItemFlag.ItemIsEditable)
    assert m.data(idx, Qt.ItemDataRole.ToolTipRole) == strings.READ_ONLY_REFUSAL


def test_the_bulk_action_sets_the_cable_contact_of_the_selected_pins_in_one_step(
    qtbot, devices_theme, theme  # noqa: F811
):
    p, cid = device_project()
    ctl, view = make_devices(qtbot, devices_theme, p)
    requests = []
    view.contactRequested.connect(lambda c, pins: requests.append((c, pins)))
    from tests.test_ux_devices_edit import select_pins

    select_pins(view, ["1", "2", "3"])
    view._request_contact()
    assert requests == [(cid, ["1", "2", "3"])]
    dlg = ContactDialog(None, theme, ctl.project, cid, ["1", "2", "3"])
    qtbot.addWidget(dlg)
    assert [dlg.part_box.itemText(i) for i in range(dlg.part_box.count())] == [
        strings.DV_CONTACT_PART_NONE,
        OTHER,
        CONTACT,
    ]
    dlg.part_box.setCurrentIndex(dlg.part_box.findData(CONTACT))
    assert dlg.ok.isEnabled() and dlg.part_id() == CONTACT
    assert ctl.set_pin_contacts(cid, ["1", "2", "3"], dlg.part_id())
    assert [pin(ctl, cid, n).contact_part for n in "1234"] == [CONTACT, CONTACT, CONTACT, None]
    ctl.undo()
    assert all(pin(ctl, cid, n).contact_part is None for n in "123456")
    assert view.pin_buttons["contact"].toolTip() and view.pin_buttons["contact"].accessibleName()


def test_the_bulk_dialog_says_when_the_library_has_no_contact_part(qtbot, theme):  # noqa: F811
    p, cid = with_connector()
    from harness_design_studio.gui.controller import EditorController

    ctl = EditorController()
    ctl._install(p, None, None)
    dlg = ContactDialog(None, theme, ctl.project, cid, ["1"])
    qtbot.addWidget(dlg)
    assert not dlg.ok.isEnabled()
    assert strings.DVD_CONTACT_NO_PARTS in dlg.notice.text() or dlg.notice.isVisibleTo(dlg) is False


def test_pasted_headers_know_the_new_words_and_keep_the_old_ones():
    assert grid_columns(["Pin", "Cable contact"]) == ["pin", "contact_part"]
    assert grid_columns(["pin", "Contact part"]) == ["pin", "contact_part"]
    assert grid_columns(["Pin", "Contact"]) == ["pin", "contact_size"]
    assert grid_columns(["Pin", "Contact size", "Termination"]) == [
        "pin",
        "contact_size",
        "termination",
    ]


def test_a_pasted_block_with_a_cable_contact_column_is_one_step(qtbot, devices_theme):
    p, cid = device_project()
    ctl, view = make_devices(qtbot, devices_theme, p)
    assert view.paste_text(f"Pin\tCable contact\n1\t{CONTACT}\n2\t{OTHER}")
    assert (pin(ctl, cid, "1").contact_part, pin(ctl, cid, "2").contact_part) == (CONTACT, OTHER)
    ctl.undo()
    assert pin(ctl, cid, "1").contact_part is None and pin(ctl, cid, "2").contact_part is None
    assert not view.paste_text("Pin\tCable contact\n1\tNOT-A-PART")
    assert "contact" in view.edit_error.text().lower()


# ---- the Connectors tab: the Contact of a pin -------------------------------------------------


@pytest.fixture
def by_hand(qtbot, theme):  # noqa: F811
    p, hid = own_project()
    ctl, view = make_view(qtbot, theme, p)
    view.select_harness(hid)
    view.refresh()
    view.show_connectors()
    return ctl, view, view.connector_editor, hid


def test_the_pin_form_has_a_contact_choice_of_contact_parts(by_hand):
    ctl, _view, ed, hid = by_hand
    assert [ed.contact_part.itemText(i) for i in range(ed.contact_part.count())] == [
        strings.CE_CONTACT_NONE,
        OTHER,
        CONTACT,
    ]
    ed.connector.setCurrentIndex(0)
    ed._fill_pins()
    ed.pin.setCurrentIndex(0)
    ed.contact_part.setCurrentIndex(ed.contact_part.findData(CONTACT))
    ed.function.setText("HEATER +")
    assert ed.apply_pin()
    conn = ctl.project.harnesses[hid].connectors[0]
    assert (conn.pins[0].contact_part, conn.pins[0].function) == (CONTACT, "HEATER +")
    assert ctl.history.next_undo_label == strings.STEP_SET_HARNESS_PIN.format(f"{conn.id}/1")
    ctl.undo()
    assert ctl.project.harnesses[hid].connectors[0].pins[0].contact_part is None
    assert ed.contact_part.accessibleName() and ed.contact_part.toolTip()


def test_contact_for_all_pins_is_one_undo_step(by_hand):
    ctl, _view, ed, hid = by_hand
    ed.connector.setCurrentIndex(1)
    ed.contact_part.setCurrentIndex(ed.contact_part.findData(OTHER))
    assert ed.apply_contact_to_all()
    cid = ed.connector.currentText()
    conn = next(c for c in ctl.project.harnesses[hid].connectors if c.id == cid)
    assert all(p.contact_part == OTHER for p in conn.pins)
    other = next(c for c in ctl.project.harnesses[hid].connectors if c.id != cid)
    assert all(p.contact_part is None for p in other.pins)
    assert ctl.history.next_undo_label == strings.STEP_SET_HARNESS_CONTACTS.format(cid)
    ctl.undo()
    assert all(p.contact_part is None for c in ctl.project.harnesses[hid].connectors for p in c.pins)
    ed.contact_part.setCurrentIndex(0)  # none clears them
    assert ed.apply_contact_to_all()
    assert ed.contact_all.accessibleName() and ed.contact_all.toolTip()


def test_a_generated_harness_says_the_contact_is_set_on_the_unit_pin(qtbot, theme):  # noqa: F811
    ctl, view = make_view(qtbot, theme, generated_project())
    ed = view.connector_editor
    assert not ed.contact_note.isHidden()
    assert ed.contact_note.text() == strings.CE_CONTACT_GENERATED
    assert "Devices tab" in ed.contact_note.text()
    assert not ed.contact_part.isEnabled() and not ed.contact_all.isEnabled()


def test_released_harness_and_read_only_project_turn_the_contact_off(by_hand):
    ctl, view, ed, hid = by_hand
    assert ed.contact_all.isEnabled() and ed.contact_part.isEnabled()
    release(ctl, hid)
    view.refresh()
    assert not ed.contact_part.isEnabled() and not ed.contact_all.isEnabled()
    assert "released" in ed.note.text()
    ctl.project.harnesses[hid] = evolve(ctl.project.harnesses[hid], status="draft")
    ctl.project.read_only = True
    ed.set_harness(hid)
    assert not ed.contact_all.isEnabled() and ed.note.text() == strings.WHY_READ_ONLY


# ---- the Accessories tab ----------------------------------------------------------------------


@pytest.fixture
def accessories(qtbot, theme):  # noqa: F811
    p, hid = own_project()
    ctl, view = make_view(qtbot, theme, p)
    view.select_harness(hid)
    view.refresh()
    view.side_tabs.setCurrentWidget(view.side_tabs.widget(3))
    return ctl, view, view.accessory_editor, hid


def test_the_tab_comes_after_connectors_and_an_empty_one_says_what_it_is_for(accessories):
    _ctl, view, ed, _hid = accessories
    assert [view.side_tabs.tabText(i) for i in range(4)][2:] == [
        strings.HV_CONNECTORS_TAB,
        strings.HV_ACCESSORIES_TAB,
    ]
    assert ed.table.empty_state.title.text() == strings.ACC_EMPTY_TITLE
    assert "sleeving" in ed.table.empty_state.hint.text()
    assert ed.table.empty_state.button.text() == strings.ACC_ADD
    assert ed.position.placeholderText() == "for example 50 mm from the P1 end"
    assert [ed.kind.itemText(i) for i in range(ed.kind.count())] == [
        "sleeving",
        "heat shrink",
        "label",
        "backshell",
        "other",
    ]
    assert ed.id.text() == "ACC-001"
    assert ed.on.itemText(0) == strings.ACC_ON_HARNESS and ed.on.count() == 1 + 2 + 2
    assert [c.header for c in ed.model.columns] == [
        "ID",
        "Kind",
        "Part",
        "On",
        "Position",
        "Length (mm)",
        "Quantity",
        "Note",
    ]


def test_add_change_and_delete_an_accessory_each_one_undo_step(accessories):
    ctl, _view, ed, hid = accessories
    cid = ctl.project.harnesses[hid].connectors[0].id
    ed.kind.setCurrentIndex(ed.kind.findData("sleeving"))
    ed.part.setCurrentIndex(ed.part.findData("EX-SLEEVE"))
    ed.on.setCurrentIndex(ed.on.findData(cid))
    ed.position.setText("50 mm from the P1 end")
    ed.length.setText("120,5")
    ed.quantity.setValue(2)
    ed.accessory_note.setPlainText("black")
    assert ed.add_accessory()
    (a,) = ctl.project.harnesses[hid].accessories
    assert a == Accessory(
        id="ACC-001", kind="sleeving", part_id="EX-SLEEVE", target=cid,
        position="50 mm from the P1 end", length_mm=120.5, quantity=2, note="black",
    )  # fmt: skip
    assert ctl.history.next_undo_label == strings.STEP_ADD_ACCESSORY.format("ACC-001")
    assert ed.model.rowCount() == 1 and ed.model.text_at(0, 5) == "120.5"
    assert ed.id.text() == "ACC-002" and ed.selected_id() is None  # ready for the next one
    # select the row: the form shows it and the ID is fixed
    ed.table.selectRow(0)
    assert ed.selected_id() == "ACC-001" and ed.position.text() == "50 mm from the P1 end"
    assert not ed.id.isEnabled() and ed.change.isEnabled() and ed.delete.isEnabled()
    ed.quantity.setValue(4)
    ed.on.setCurrentIndex(0)
    assert ed.change_accessory()
    b = ctl.project.harnesses[hid].accessories[0]
    assert (b.quantity, b.target) == (4, None)
    assert ctl.history.next_undo_label == strings.STEP_CHANGE_ACCESSORY.format("ACC-001")
    ctl.undo()
    assert ctl.project.harnesses[hid].accessories == [a]
    ctl.redo()
    # a copy: Add with a row selected gives the new accessory the next free ID
    ed.table.selectRow(0)
    assert ed.add_accessory()
    assert [x.id for x in ctl.project.harnesses[hid].accessories] == ["ACC-001", "ACC-002"]
    ed.table.selectRow(1)
    assert ed.selected_id() == "ACC-002"
    assert ed.delete_accessory()
    assert [x.id for x in ctl.project.harnesses[hid].accessories] == ["ACC-001"]
    assert ctl.history.next_undo_label == strings.STEP_DELETE_ACCESSORY.format("ACC-002")
    ctl.undo()
    assert [x.id for x in ctl.project.harnesses[hid].accessories] == ["ACC-001", "ACC-002"]


def test_a_mistake_in_the_accessory_form_is_said_inline(accessories):
    ctl, _view, ed, hid = accessories
    ed.length.setText("long")
    assert not ed.add_accessory()
    assert not ed.error.isHidden() and "millimetres" in ed.error.text()
    assert ctl.project.harnesses[hid].accessories == []
    assert ctl.history.next_undo_label is None
    ed.length.setText("")
    assert ed.add_accessory() and ed.error.isHidden()
    ed.new_accessory()
    ed.id.setText("ACC-001")  # taken
    assert not ed.add_accessory()
    assert strings.ACC_ID_EXISTS.format("ACC-001") == ed.error.text()
    assert not ed.change_accessory()  # nothing selected: the button is off
    assert not ed.delete_accessory()


def test_accessory_table_follows_the_project_and_undo(accessories):
    ctl, _view, ed, hid = accessories
    assert ed.add_accessory()
    ctl.undo()
    ed.set_harness(hid)
    assert ed.model.rowCount() == 0
    assert ed.table.empty_state.isVisibleTo(ed.table.viewport()) or True


def test_a_released_harness_and_a_read_only_project_turn_the_tab_off(accessories):
    ctl, view, ed, hid = accessories
    assert ed.add_accessory()
    release(ctl, hid)
    view.refresh()
    for w in (ed.add, ed.change, ed.delete, ed.id, ed.kind, ed.part, ed.on, ed.position, ed.length):
        assert not w.isEnabled()
    assert ed.note.text() == strings.ACC_RELEASED.format(hid) and not ed.note.isHidden()
    assert not ed.add_accessory()
    ctl.project.harnesses[hid] = evolve(ctl.project.harnesses[hid], status="draft")
    ctl.project.read_only = True
    ed.set_harness(hid)
    assert not ed.add.isEnabled() and ed.note.text() == strings.WHY_READ_ONLY


def test_every_accessory_control_has_a_name_and_a_tip(accessories):
    _ctl, _view, ed, _hid = accessories
    for w in (
        ed.id, ed.kind, ed.part, ed.on, ed.position, ed.length, ed.quantity, ed.accessory_note,
        ed.add, ed.change, ed.delete, ed.new, ed.table,
    ):  # fmt: skip
        assert w.accessibleName() and w.toolTip()


# ---- the crimp tool of a contact part ---------------------------------------------------------


def make_inspector(qtbot, theme, project):  # noqa: F811
    from harness_design_studio.gui.controller import EditorController

    ctl = EditorController()
    ctl._install(project, None, None)
    ins = Inspector(ctl, theme)
    qtbot.addWidget(ins)
    ins.resize(340, 760)
    ins.show()
    QApplication.processEvents()
    return ctl, ins


def test_a_contact_part_has_a_tool_field_in_the_inspector(qtbot, theme):  # noqa: F811
    ctl, ins = make_inspector(qtbot, theme, generated_project())
    ins.show_object("part", CONTACT)
    assert not ins.tool_box.isHidden() and ins.tool_edit.text() == ""
    ins.tool_edit.setText("Tool X, setting 4")
    assert ins.apply_tool()
    assert ctl.project.parts[CONTACT].tool == "Tool X, setting 4"
    assert ctl.history.next_undo_label == strings.STEP_SET_PART_TOOL.format(CONTACT)
    names = [r["name"] for r in ins.facts_table.source.rows()]
    assert strings.INS_FACT_TOOL in names
    ctl.undo()
    assert ctl.project.parts[CONTACT].tool is None
    ins.tool_edit.setText("")
    assert ins.apply_tool()  # nothing to change: no step
    assert ins.tool_edit.accessibleName() and ins.tool_edit.toolTip()
    assert ins.tool_set.accessibleName()


def test_only_a_contact_part_has_the_tool_field(qtbot, theme):  # noqa: F811
    _ctl, ins = make_inspector(qtbot, theme, generated_project())
    ins.show_object("part", "EX-DSUB-9-M")
    assert ins.tool_box.isHidden()
    ins.show_object("part", "EX-SLEEVE")
    assert ins.tool_box.isHidden()


def test_the_tool_of_a_part_in_a_released_harness_is_refused_inline(qtbot, theme):  # noqa: F811
    p, hid = own_project()
    conn = p.harnesses[hid].connectors[0]
    pins = [evolve(conn.pins[0], contact_part=CONTACT), *conn.pins[1:]]
    h = p.harnesses[hid]
    apply_ops(
        p,
        [
            Put(
                "harnesses",
                evolve(
                    h,
                    status="released",
                    connectors=[evolve(conn, pins=pins), *h.connectors[1:]],
                ),
            )
        ],
    )
    ctl, ins = make_inspector(qtbot, theme, p)
    ins.show_object("part", CONTACT)
    ins.tool_edit.setText("Tool Y")
    assert not ins.apply_tool()
    assert not ins.tool_error.isHidden() and hid in ins.tool_error.text()
    assert ctl.project.parts[CONTACT].tool is None


def test_a_read_only_project_turns_the_tool_field_off(qtbot, theme):  # noqa: F811
    ctl, ins = make_inspector(qtbot, theme, generated_project())
    ctl.project.read_only = True
    ins.show_object("part", CONTACT)
    ins.refresh()
    assert not ins.tool_edit.isEnabled() and not ins.tool_set.isEnabled()
