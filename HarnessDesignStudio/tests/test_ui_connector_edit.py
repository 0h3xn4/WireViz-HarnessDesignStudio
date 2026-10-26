# mypy: disable-error-code="no-untyped-def,no-untyped-call"
"""REQ-HARN-02. Workshop feedback M3: the Connectors tab edits a connector (part, gender, keying, name)
and its pins (signal, role, function, add, rename, delete), on a harness made by hand and, as an edit
that Generate keeps, on a generated harness; every control is named and has a tooltip."""

import pytest

pytest.importorskip("PySide6")
pytestmark = pytest.mark.gui

from harness_design_studio.core.commands import apply_ops  # noqa: E402
from harness_design_studio.core.generate.engine import (  # noqa: E402
    generate_project,
    plan_generation,
)
from harness_design_studio.core.manual_harness import (  # noqa: E402
    plan_add_connector,
    plan_new_harness,
)
from harness_design_studio.core.model import evolve  # noqa: E402
from harness_design_studio.core.samples import new_project, sat15  # noqa: E402
from harness_design_studio.core.wires import plan_add_wire  # noqa: E402
from harness_design_studio.gui import strings  # noqa: E402
from tests.test_ux_harness import make_view, theme  # noqa: E402, F401, F811


def by_hand():
    p = new_project("Scratch")
    ops, hid = plan_new_harness(p, "By hand")
    apply_ops(p, ops)
    for _ in range(2):
        ops, _cid = plan_add_connector(p, hid, part_id="EX-DSUB-9-M")
        apply_ops(p, ops)
    a, b = [c.id for c in p.harnesses[hid].connectors]
    apply_ops(p, plan_add_wire(p, hid, a, "1", b, "1", signal="HEATER"))
    return p, hid, a, b


@pytest.fixture
def mine(qtbot, theme):  # noqa: F811
    p, hid, a, b = by_hand()
    ctl, view = make_view(qtbot, theme, p)
    view.select_harness(hid)
    view.refresh()
    ed = view.connector_editor
    ed.connector.setCurrentIndex(ed.connector.findText(a))
    ed._fill_pins()
    return ctl, view, ed, hid, a, b


@pytest.fixture
def generated(qtbot, theme):  # noqa: F811
    p = sat15()
    generate_project(p)
    ctl, view = make_view(qtbot, theme, p)
    view.select_harness("W001")
    view.refresh()
    ed = view.connector_editor
    ed.connector.setCurrentIndex(0)
    ed._fill_pins()
    return ctl, view, ed, "W001", ed.connector.currentText()


def conn(ctl, hid, cid):
    return next(c for c in ctl.project.harnesses[hid].connectors if c.id == cid)


def test_every_new_control_has_a_name_and_a_tooltip(mine):
    _ctl, _view, ed, *_ = mine
    for w in (
        ed.edit_part, ed.gender, ed.keying, ed.edit_name, ed.edit_apply, ed.reset, ed.signal,
        ed.role, ed.pin_id, ed.pin_add, ed.pin_rename, ed.pin_delete,
    ):  # fmt: skip
        assert w.accessibleName() and w.toolTip(), w.objectName()
    assert "unit" not in " ".join(
        v for k, v in vars(strings).items() if k.startswith("CE_") and isinstance(v, str)
    ).lower().replace("community", "")


def test_the_connector_fields_show_the_connector(mine):
    _ctl, _view, ed, _hid, a, _b = mine
    assert ed.connector.currentText() == a
    assert ed.edit_part.currentData() == "EX-DSUB-9-M"
    assert ed.gender.currentData() == "male"
    assert ed.edit_name.text() == "P1" and ed.keying.text() == ""
    assert ed.edit_state.isHidden() and ed.reset.isHidden()


def test_a_part_gender_keying_and_name_are_applied_in_one_undo_step(mine):
    ctl, _view, ed, hid, a, _b = mine
    ed.edit_part.setCurrentIndex(ed.edit_part.findData("EX-DSUB-9-F"))
    ed._part_chosen()  # (what picking in the list does)
    assert ed.gender.currentData() == "female"  # the part says it: offered
    ed.keying.setText("Key B")
    ed.edit_name.setText("Heater end")
    assert ed.apply_connector()
    c = conn(ctl, hid, a)
    assert (c.part_id, c.gender, c.keying, c.name) == (
        "EX-DSUB-9-F",
        "female",
        "Key B",
        "Heater end",
    )
    ctl.undo()
    c = conn(ctl, hid, a)
    assert (c.part_id, c.gender, c.keying, c.name) == ("EX-DSUB-9-M", "male", None, "P1")
    ctl.redo()
    assert conn(ctl, hid, a).keying == "Key B"


def test_a_wrong_name_is_said_under_the_form_and_nothing_changes(mine):
    ctl, _view, ed, hid, a, _b = mine
    before = conn(ctl, hid, a)
    ed.edit_name.setText("P2")
    assert not ed.apply_connector()
    assert "called 'P2' already" in ed.error.text() and not ed.error.isHidden()
    assert conn(ctl, hid, a) == before
    ed.edit_name.setText("P1")
    assert (
        ed.apply_connector() and ed.edit_state.isHidden()
    )  # nothing to change: said, not an error
    assert ed.error.text() == strings.CE_EDIT_NOTHING


def test_a_part_with_other_pins_says_so(mine):
    _ctl, _view, ed, *_ = mine
    ed.edit_part.setCurrentIndex(ed.edit_part.findData("EX-DSUB-15-M"))
    ed._part_chosen()
    assert not ed.pin_count.isHidden()
    assert ed.pin_count.text() == strings.CE_PIN_COUNT.format(15, 9) + strings.CE_PIN_COUNT_ADD


def test_signal_role_and_function_of_a_pin(mine):
    ctl, _view, ed, hid, a, _b = mine
    ed.pin.setCurrentIndex(ed.pin.findText("3"))
    ed._show_pin()
    ed.signal.setText("HEATER +")
    ed.role.setCurrentIndex(ed.role.findData("power"))
    ed.function.setText("Heater supply")
    assert ed.apply_pin()
    pin = next(p for p in conn(ctl, hid, a).pins if p.id == "3")
    assert (pin.signal, pin.role, pin.function) == ("HEATER +", "power", "Heater supply")
    ed._show_pin()
    assert ed.signal.text() == "HEATER +" and ed.role.currentData() == "power"


def test_pins_are_added_renamed_and_deleted(mine):
    ctl, _view, ed, hid, a, _b = mine
    ed.edit_part.setCurrentIndex(ed.edit_part.findData("EX-DSUB-15-M"))
    assert ed.apply_connector()
    ed.pin_id.setText("10, A11")
    assert ed.add_pins()
    assert [p.id for p in conn(ctl, hid, a).pins][-2:] == ["10", "A11"]
    ed.pin.setCurrentIndex(ed.pin.findText("1"))
    ed.pin_id.setText("A1")
    assert ed.rename_pin()
    w = ctl.project.harnesses[hid].wires[0]
    assert (w.from_connector, w.from_pin) == (a, "A1")  # the wire followed
    ed.pin.setCurrentIndex(ed.pin.findText("A1"))
    assert not ed.delete_pin() and "has wires" in ed.error.text()
    ed.pin.setCurrentIndex(ed.pin.findText("A11"))
    assert ed.delete_pin()
    assert "A11" not in [p.id for p in conn(ctl, hid, a).pins]


def test_a_released_harness_and_a_read_only_project_turn_every_edit_off(mine):
    ctl, view, ed, hid, a, _b = mine
    ctl.project.harnesses[hid] = evolve(ctl.project.harnesses[hid], status="released")
    ed.set_harness(hid)
    for w in (ed.edit_apply, ed.edit_name, ed.gender, ed.set_pin, ed.pin_add, ed.pin_rename):
        assert not w.isEnabled(), w.objectName()
    assert "released" in ed.note.text()
    ctl.project.harnesses[hid] = evolve(ctl.project.harnesses[hid], status="draft")
    ctl.project.read_only = True
    ed.set_harness(hid)
    assert not ed.edit_apply.isEnabled() and ed.note.text() == strings.WHY_READ_ONLY
    assert view


# ---- a harness made by Generate -------------------------------------------------------------------


def test_a_generated_harness_still_adds_nothing_but_edits_a_connector(generated):
    _ctl, _view, ed, hid, _cid = generated
    assert not ed.add.isEnabled() and "made by Generate" in ed.note.text()
    for w in (ed.edit_part, ed.gender, ed.keying, ed.edit_apply, ed.signal, ed.role, ed.set_pin):
        assert w.isEnabled(), w.objectName()
    for w in (ed.edit_name, ed.pin_add, ed.pin_rename, ed.pin_delete, ed.contact_part, ed.delete):
        assert not w.isEnabled(), w.objectName()
    assert not ed.pin_note.isHidden() and ed.edit_state.text() == strings.CE_EDIT_STATE_GENERATED
    assert ed.edit_name.toolTip() == strings.CE_EDIT_NAME_FIXED


def test_an_edit_on_a_generated_harness_is_kept_by_generate_and_can_be_given_back(generated):
    ctl, _view, ed, hid, cid = generated
    original = conn(ctl, hid, cid)
    ed.gender.setCurrentIndex(ed.gender.findData("female"))
    ed.keying.setText("B")
    assert ed.apply_connector()
    c = conn(ctl, hid, cid)
    assert c.locked and (c.gender, c.keying) == ("female", "B")
    assert ed.edit_state.text() == strings.CE_EDIT_STATE_MINE and not ed.reset.isHidden()
    apply_ops(ctl.project, plan_generation(ctl.project).ops)
    assert (conn(ctl, hid, cid).gender, conn(ctl, hid, cid).keying) == ("female", "B")
    assert ed.reset_connector()
    assert not conn(ctl, hid, cid).locked
    apply_ops(ctl.project, plan_generation(ctl.project).ops)
    assert conn(ctl, hid, cid) == original


def test_a_pin_edit_on_a_generated_harness_locks_the_connector(generated):
    ctl, _view, ed, hid, cid = generated
    ed.pin.setCurrentIndex(0)
    ed._show_pin()
    ed.function.setText("My function")
    assert ed.apply_pin()
    c = conn(ctl, hid, cid)
    assert c.locked and c.pins[0].function == "My function"
    ctl.undo()
    assert not conn(ctl, hid, cid).locked
