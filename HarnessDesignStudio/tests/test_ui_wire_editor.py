# mypy: disable-error-code="no-untyped-def,no-untyped-call"
"""1.4.0 M1: the Edit wire form of the Harness tab (gauge, type, colour, length, label, note)."""

import pytest

pytest.importorskip("PySide6")
pytestmark = pytest.mark.gui

from PySide6.QtCore import QItemSelectionModel  # noqa: E402

from harness_design_studio.core.commands import apply_ops  # noqa: E402
from harness_design_studio.core.generate.engine import generate_project  # noqa: E402
from harness_design_studio.core.model import Part  # noqa: E402
from harness_design_studio.core.samples import sat15  # noqa: E402
from harness_design_studio.core.wires import find_wire, plan_add_wire  # noqa: E402
from harness_design_studio.gui import strings  # noqa: E402
from tests.test_ux_harness import make_view, theme  # noqa: E402, F401, F811


def project():
    p = sat15()
    generate_project(p)
    p.parts["EX-WIRE-22"] = Part(id="EX-WIRE-22", category="wire")
    return p


def select_rows(view, *rows: int) -> list[str]:
    """Select these rows of the wire table (source rows) and return their wire IDs."""
    table = view.wire_table
    sm = table.selectionModel()
    sm.clearSelection()
    ids = []
    for n, r in enumerate(rows):
        idx = table.proxy.mapFromSource(table.proxy.sourceModel().index(r, 0))
        flag = (
            QItemSelectionModel.SelectionFlag.ClearAndSelect
            if n == 0
            else QItemSelectionModel.SelectionFlag.Select
        )
        sm.select(idx, flag | QItemSelectionModel.SelectionFlag.Rows)
        if n == 0:
            sm.setCurrentIndex(idx, QItemSelectionModel.SelectionFlag.NoUpdate)
        ids.append(view._wire_data[r]["id"])
    return ids


@pytest.fixture
def made(qtbot, theme):  # noqa: F811
    ctl, view = make_view(qtbot, theme, project())
    return ctl, view, view.wire_editor


def test_the_form_is_a_tab_beside_why_and_empty_until_a_wire_is_selected(made):
    _ctl, view, ed = made
    assert [view.side_tabs.tabText(i) for i in range(2)] == [
        strings.HV_WHY_TITLE,
        strings.HV_EDIT_TAB,
    ]
    assert ed.title.text() == strings.WIRE_EDIT_NONE
    assert not ed.apply.isEnabled()


def test_selecting_a_wire_shows_its_values(made):
    ctl, view, ed = made
    (wid,) = select_rows(view, 0)
    assert ed.wire_ids() == [wid]
    h, w = find_wire(ctl.project, wid)
    assert wid in ed.title.text() and w.from_connector in ed.title.text()
    assert ed.apply.isEnabled()
    assert ed.state.text() == strings.WIRE_STATE_GENERATED


def test_apply_sets_the_touched_fields_locks_the_wire_and_is_one_undo_step(made):
    ctl, view, ed = made
    (wid,) = select_rows(view, 0)
    before = find_wire(ctl.project, wid)[1]
    ed.gauge.setText("22")
    ed.gauge.textEdited.emit("22")
    ed.colour.setCurrentText("red")
    ed.colour.lineEdit().textEdited.emit("red")
    ed.note.setPlainText("check the crimp")
    assert ed.apply_changes()
    w = find_wire(ctl.project, wid)[1]
    assert (w.gauge_awg, w.colour, w.note, w.locked) == (22, "red", "check the crimp", True)
    assert w.label == before.label and w.length_m == before.length_m  # untouched
    assert ed.state.text() == strings.WIRE_STATE_KEPT
    ctl.undo()
    assert find_wire(ctl.project, wid)[1] == before


def test_several_wires_take_one_edit_and_keep_what_they_do_not_share(made):
    ctl, view, ed = made
    a, b = select_rows(view, 0, 1)
    assert ed.wire_ids() == [a, b]
    assert ed.title.text() == strings.WIRE_EDIT_MANY.format(2)
    ed.label.setText("Bus")
    ed.label.textEdited.emit("Bus")
    assert ed.apply_changes()
    assert find_wire(ctl.project, a)[1].label == "Bus"
    assert find_wire(ctl.project, b)[1].label == "Bus"
    assert find_wire(ctl.project, a)[1].locked is False  # a label alone does not lock


def test_a_wrong_value_is_said_in_words_and_nothing_changes(made):
    ctl, view, ed = made
    (wid,) = select_rows(view, 0)
    before = find_wire(ctl.project, wid)[1]
    ed.gauge.setText("abc")
    ed.gauge.textEdited.emit("abc")
    assert not ed.apply_changes()
    assert not ed.error.isHidden() and "whole number" in ed.error.text()
    assert find_wire(ctl.project, wid)[1] == before


def test_reset_gives_the_wire_back_to_generation(made):
    ctl, view, ed = made
    (wid,) = select_rows(view, 0)
    ed.gauge.setText("20")
    ed.gauge.textEdited.emit("20")
    ed.apply_changes()
    assert find_wire(ctl.project, wid)[1].locked
    assert ed.reset_wires()
    assert find_wire(ctl.project, wid)[1].locked is False
    assert ed.state.text() == strings.WIRE_STATE_GENERATED


def test_a_released_harness_turns_the_form_off_and_says_why(made):
    ctl, view, ed = made
    (wid,) = select_rows(view, 0)
    h, _w = find_wire(ctl.project, wid)
    from harness_design_studio.core.commands import Put
    from harness_design_studio.core.model import evolve

    apply_ops(ctl.project, [Put("harnesses", evolve(h, status="released"))])
    view.refresh()
    select_rows(view, 0)
    ed.show_wires([wid])
    assert not ed.apply.isEnabled() and not ed.gauge.isEnabled()
    assert "released" in ed.state.text()


def test_a_read_only_project_turns_the_form_off(made):
    ctl, view, ed = made
    (wid,) = select_rows(view, 0)
    ctl.project.read_only = True
    ed.show_wires([wid])
    assert not ed.apply.isEnabled()
    assert ed.state.text() == strings.WIRE_STATE_READ_ONLY


def test_every_control_has_an_accessible_name_and_a_tooltip(made):
    _ctl, _view, ed = made
    for w in (ed.gauge, ed.part, ed.colour, ed.length, ed.label, ed.note, ed.apply, ed.reset):
        assert w.accessibleName()
        assert w.toolTip()


# ---- 1.4.0 M2: wires that a person draws --------------------------------------------------------


def pick(box, text):
    """Choose `text` in a combo box the way a click does."""
    i = box.findText(text)
    assert i >= 0, (text, [box.itemText(n) for n in range(box.count())])
    box.setCurrentIndex(i)
    box.activated.emit(i)


def free_pin_pair(ctl, hid):
    h = ctl.project.harnesses[hid]
    used = {(w.from_connector, w.from_pin) for w in h.wires} | {
        (w.to_connector, w.to_pin) for w in h.wires
    }
    free = [(c.id, p.id) for c in h.connectors for p in c.pins if (c.id, p.id) not in used]
    return free[0], free[1]


def test_the_new_wire_form_adds_a_wire_that_stays_selected_for_editing(made):
    ctl, view, ed = made
    hid = view.harness_id()
    (c1, p1), (c2, p2) = free_pin_pair(ctl, hid)
    form = ed.new_form
    pick(form.start.connector, c1)
    pick(form.start.pin, p1)
    pick(form.end.connector, c2)
    pick(form.end.pin, p2)
    form.signal.setText("HEATER")
    assert form.add_wire()
    mine = [w for w in ctl.project.harnesses[hid].wires if w.manual]
    assert len(mine) == 1
    w = mine[0]
    assert (w.from_connector, w.from_pin, w.to_connector, w.to_pin) == (c1, p1, c2, p2)
    assert w.signal == "HEATER" and w.interface_id is None
    assert ed.wire_ids() == [w.id]  # the new wire is the selection
    assert not ed.ends.isHidden() and not ed.delete.isHidden()
    assert ed.state.text() == strings.WIRE_STATE_MANUAL
    ctl.undo()
    assert not any(x.manual for x in ctl.project.harnesses[hid].wires)


def test_the_form_says_why_a_wire_cannot_be_added(made):
    ctl, view, ed = made
    form = ed.new_form
    form.end.connector.setCurrentIndex(form.start.connector.currentIndex())
    form.end._fill_pins()
    form.end.pin.setCurrentIndex(form.start.pin.currentIndex())
    assert not form.add_wire()
    assert not form.error.isHidden() and "same pin" in form.error.text()


def test_the_ends_of_a_wire_that_you_drew_can_be_moved_but_not_those_of_a_generated_wire(made):
    ctl, view, ed = made
    hid = view.harness_id()
    (c1, p1), (c2, p2) = free_pin_pair(ctl, hid)
    ctl.run("add wire", plan_add_wire(ctl.project, hid, c1, p1, c2, p2))
    view.refresh()
    wid = next(w.id for w in ctl.project.harnesses[hid].wires if w.manual)
    view.select("wire", wid)
    view._update_wire_editor()
    assert ed.wire_ids() == [wid] and not ed.ends.isHidden()
    other = free_pin_pair(ctl, hid)[0]
    pick(ed.to_end.connector, other[0])
    pick(ed.to_end.pin, other[1])
    assert ed.apply_changes()
    got = find_wire(ctl.project, wid)[1]
    assert (got.to_connector, got.to_pin) == other
    generated = next(w.id for w in ctl.project.harnesses[hid].wires if not w.manual)
    view.select("wire", generated)
    view._update_wire_editor()
    assert ed.ends.isHidden() and ed.delete.isHidden()


def test_delete_removes_the_wires_that_you_drew(made):
    ctl, view, ed = made
    hid = view.harness_id()
    h = ctl.project.harnesses[hid]
    pairs = free_pin_pair(ctl, hid)
    ctl.run("add wire", plan_add_wire(ctl.project, hid, *pairs[0], *pairs[1]))
    ids = [w.id for w in ctl.project.harnesses[hid].wires if w.manual]
    view.refresh()
    view.select("wire", ids[0])
    view._update_wire_editor()
    assert ed.delete_wires()
    assert not [w for w in ctl.project.harnesses[hid].wires if w.manual]
    assert len(ctl.project.harnesses[hid].wires) == len(h.wires)


def test_a_released_harness_turns_the_new_wire_form_off(made):
    ctl, view, ed = made
    h = ctl.project.harnesses[view.harness_id()]
    from harness_design_studio.core.commands import Put
    from harness_design_studio.core.model import evolve

    apply_ops(ctl.project, [Put("harnesses", evolve(h, status="released"))])
    view.refresh()
    assert not ed.new_form.add.isEnabled()
