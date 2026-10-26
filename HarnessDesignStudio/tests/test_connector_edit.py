# mypy: disable-error-code="no-untyped-def,no-untyped-call,no-any-return"
"""REQ-HARN-02. Workshop feedback M3: editing a cable connector (part, gender, keying, name, pins) of a
harness made by hand and of a generated harness, where the edit locks against Generate; files stay
byte-identical while nothing is edited."""

import json

import pytest

from harness_design_studio.core.commands import History, apply_ops
from harness_design_studio.core.connector_edit import (
    is_edited,
    plan_add_pins,
    plan_delete_pin,
    plan_edit_connector,
    plan_edit_pin,
    plan_rename_pin,
    plan_reset_connector,
    suggested_gender,
)
from harness_design_studio.core.drc import run
from harness_design_studio.core.edit import EditError
from harness_design_studio.core.generate.engine import generate_project, plan_generation
from harness_design_studio.core.integrity import check_integrity
from harness_design_studio.core.io.layout import model_hash, serialize
from harness_design_studio.core.manual_harness import plan_add_connector, plan_new_harness
from harness_design_studio.core.model import evolve
from harness_design_studio.core.outputs.build import build_outputs
from harness_design_studio.core.samples import new_project, sat15
from harness_design_studio.core.verify import verify_project
from harness_design_studio.core.wires import plan_add_wire


def mine():
    """A project with a harness made by hand: two 9-pin male connectors and one wire."""
    p = new_project("Scratch")
    ops, hid = plan_new_harness(p, "Heater harness")
    apply_ops(p, ops)
    ids = []
    for _ in range(2):
        ops, cid = plan_add_connector(p, hid, part_id="EX-DSUB-9-M")
        apply_ops(p, ops)
        ids.append(cid)
    apply_ops(p, plan_add_wire(p, hid, ids[0], "1", ids[1], "1", signal="HEATER"))
    return p, hid, ids


def generated():
    p = sat15()
    generate_project(p)
    return p, "W001", [c.id for c in p.harnesses["W001"].connectors]


def conn(p, hid, cid):
    return next(c for c in p.harnesses[hid].connectors if c.id == cid)


def regenerate(p) -> None:
    apply_ops(p, plan_generation(p).ops)


# ---- a harness made by hand -----------------------------------------------------------------------


def test_part_gender_keying_and_name_of_a_connector_of_your_own_harness():
    p, hid, (a, _b) = mine()
    ops = plan_edit_connector(
        p, hid, a, part_id="EX-DSUB-9-F", gender="female", keying="Key A", name="Heater end"
    )
    apply_ops(p, ops)
    c = conn(p, hid, a)
    assert (c.part_id, c.gender, c.keying, c.name, c.locked) == (
        "EX-DSUB-9-F",
        "female",
        "Key A",
        "Heater end",
        False,
    )
    assert len(c.pins) == 9  # the pins are not touched
    apply_ops(p, plan_edit_connector(p, hid, a, keying="  "))
    assert conn(p, hid, a).keying is None  # empty clears it


def test_the_suggested_gender_is_what_the_library_says():
    p, _hid, _ids = mine()
    assert suggested_gender(p, "EX-DSUB-9-F") == "female"
    assert suggested_gender(p, "EX-DSUB-9-M") == "male"
    assert suggested_gender(p, "nothing") == "unspecified"


@pytest.mark.parametrize(
    ("changes", "words"),
    [
        ({"part_id": "nothing"}, "not a connector part"),
        ({"gender": "both"}, "gender is one of"),
        ({"name": ""}, "needs a name"),
        ({"name": "P2"}, "called 'P2' already"),
        ({"colour": "red"}, "no field"),
    ],
)
def test_a_wrong_value_says_why_and_changes_nothing(changes, words):
    p, hid, (a, _b) = mine()
    before = model_hash(p)
    with pytest.raises(EditError, match=words):
        plan_edit_connector(p, hid, a, **changes)
    assert model_hash(p) == before


def test_a_wire_part_is_not_a_connector_part():
    p, hid, (a, _b) = mine()
    wire_part = next(x.id for x in p.parts.values() if x.category == "wire")
    with pytest.raises(EditError, match="not a connector part"):
        plan_edit_connector(p, hid, a, part_id=wire_part)


def test_an_edit_that_changes_nothing_gives_no_ops():
    p, hid, (a, _b) = mine()
    assert plan_edit_connector(p, hid, a, part_id="EX-DSUB-9-M", gender="male") == []
    assert plan_edit_pin(p, hid, a, "1", function="") == []
    assert plan_reset_connector(p, hid, a) == []


def test_one_undo_step_and_redo():
    p, hid, (a, _b) = mine()
    before = model_hash(p)
    hist = History(p)
    hist.execute("edit connector", plan_edit_connector(p, hid, a, gender="female", keying="K"))
    after = model_hash(p)
    assert after != before
    hist.undo()
    assert model_hash(p) == before
    hist.redo()
    assert model_hash(p) == after


def test_the_signal_role_and_details_of_a_pin():
    p, hid, (a, _b) = mine()
    ops = plan_edit_pin(
        p,
        hid,
        a,
        "3",
        signal="HEATER +",
        role="power",
        function="Heater supply",
        termination="solder",
        contact_size="20",
    )
    apply_ops(p, ops)
    pin = next(x for x in conn(p, hid, a).pins if x.id == "3")
    assert (pin.signal, pin.role, pin.function, pin.termination, pin.contact_size) == (
        "HEATER +",
        "power",
        "Heater supply",
        "solder",
        "20",
    )
    apply_ops(p, plan_edit_pin(p, hid, a, "3", signal="", role=""))
    pin = next(x for x in conn(p, hid, a).pins if x.id == "3")
    assert (pin.signal, pin.role) == (None, "")
    with pytest.raises(EditError, match="role is one of"):
        plan_edit_pin(p, hid, a, "3", role="boss")
    with pytest.raises(EditError, match="termination is one of"):
        plan_edit_pin(p, hid, a, "3", termination="glue")
    with pytest.raises(EditError, match="no pin"):
        plan_edit_pin(p, hid, a, "99", signal="x")
    with pytest.raises(EditError, match="not a contact part"):
        plan_edit_pin(p, hid, a, "3", contact_part="EX-DSUB-9-M")
    with pytest.raises(EditError, match="no field"):
        plan_edit_pin(p, hid, a, "3", colour="x")


def test_a_pin_is_added_renamed_and_deleted_and_wires_follow_a_rename():
    p, hid, (a, b) = mine()
    # the 9-pin part is full: a tenth pin needs a bigger part
    with pytest.raises(EditError, match="at least one pin"):
        plan_add_pins(p, hid, a, [])
    with pytest.raises(EditError, match="has 9 pins"):
        plan_add_pins(p, hid, a, ["10"])
    apply_ops(p, plan_edit_connector(p, hid, a, part_id="EX-DSUB-15-M"))
    apply_ops(p, plan_add_pins(p, hid, a, ["10", "A11"]))
    assert [x.id for x in conn(p, hid, a).pins][-2:] == ["10", "A11"]
    with pytest.raises(EditError, match="has a pin '10' already"):
        plan_add_pins(p, hid, a, ["10"])
    with pytest.raises(EditError, match="cannot be used as a pin name"):
        plan_add_pins(p, hid, a, ["a b"])
    apply_ops(p, plan_rename_pin(p, hid, a, "1", "A1"))
    w = p.harnesses[hid].wires[0]
    assert (w.from_connector, w.from_pin, w.to_pin) == (a, "A1", "1")
    assert [x.id for x in conn(p, hid, a).pins][0] == "A1"
    with pytest.raises(EditError, match="has a pin 'a11' already"):
        plan_rename_pin(p, hid, a, "A1", "a11")
    assert plan_rename_pin(p, hid, a, "A1", "A1") == []
    with pytest.raises(EditError, match="has wires"):
        plan_delete_pin(p, hid, a, "A1")
    apply_ops(p, plan_delete_pin(p, hid, a, "A11"))
    assert "A11" not in [x.id for x in conn(p, hid, a).pins]
    assert [f for f in check_integrity(p) if f.severity == "error"] == []
    assert b  # (the other end is untouched)


def test_the_edited_harness_still_checks_and_builds():
    p, hid, (a, b) = mine()
    apply_ops(p, plan_edit_connector(p, hid, a, part_id="EX-DSUB-9-F", gender="female"))
    apply_ops(p, plan_edit_pin(p, hid, a, "1", signal="HEATER", role="power"))
    assert [x for x in check_integrity(p) if x.severity == "error"] == []
    assert verify_project(p).ok
    text = build_outputs(p).files[f"harnesses/{hid}/pinouts.csv"].decode()
    assert "EX-DSUB-9-F" in text and "HEATER" in text
    assert [f.id for f in run(p) if f.severity == "error"] == []
    assert b


def test_a_released_harness_and_a_read_only_project_refuse():
    p, hid, (a, _b) = mine()
    p.harnesses[hid] = evolve(p.harnesses[hid], status="released")
    for call in (
        lambda: plan_edit_connector(p, hid, a, gender="female"),
        lambda: plan_edit_pin(p, hid, a, "1", signal="x"),
        lambda: plan_rename_pin(p, hid, a, "1", "Z"),
        lambda: plan_reset_connector(p, hid, a),
    ):
        with pytest.raises(EditError, match="released"):
            call()
    p2, hid2, (a2, _b2) = mine()
    p2.read_only = True
    with pytest.raises(EditError, match="read-only"):
        plan_edit_connector(p2, hid2, a2, gender="female")


def test_unknown_harness_connector_and_a_device_connector():
    p, hid, (a, _b) = mine()
    with pytest.raises(EditError, match="does not exist"):
        plan_edit_connector(p, "W999", a, gender="female")
    with pytest.raises(EditError, match="not a connector of"):
        plan_edit_connector(p, hid, "W001-P9", gender="female")
    other = sat15()
    generate_project(other)
    with pytest.raises(EditError, match="not a connector of"):
        plan_edit_connector(other, "W001", "OBC1-J01", gender="female")


# ---- a harness made by Generate -------------------------------------------------------------------


def test_nothing_is_written_while_no_connector_is_edited():
    p, _hid, _ids = generated()
    for name, data in serialize(p).items():
        if name.startswith("physical/harnesses/"):
            for c in json.loads(data)["connectors"]:
                assert "locked" not in c


def test_an_edit_of_a_generated_connector_locks_it_and_generation_keeps_it():
    p, hid, (a, b) = generated()
    box_pins = [x.id for x in p.connectors[conn(p, hid, a).mates_with].pins]
    ops = plan_edit_connector(p, hid, a, part_id="EX-MICROD-9-F", gender="female", keying="B")
    apply_ops(p, ops)
    apply_ops(p, plan_edit_pin(p, hid, a, "2", signal="MY SIGNAL", function="My function"))
    c = conn(p, hid, a)
    assert c.locked and is_edited(p, hid, a) and not is_edited(p, hid, b)
    regenerate(p)
    c = conn(p, hid, a)
    assert (c.part_id, c.gender, c.keying, c.locked) == ("EX-MICROD-9-F", "female", "B", True)
    pin = next(x for x in c.pins if x.id == "2")
    assert (pin.signal, pin.function) == ("MY SIGNAL", "My function")
    assert [x.id for x in c.pins] == box_pins  # the pin IDs follow the device
    other = conn(p, hid, b)
    assert not other.locked and other.part_id == "EX-MICROD-9-M"  # the other end is Generate's
    assert plan_generation(p).ops == []  # a second plan is empty


def test_generation_twice_is_byte_identical_with_an_edited_connector():
    p, hid, (a, _b) = generated()
    apply_ops(p, plan_edit_connector(p, hid, a, gender="female"))
    regenerate(p)
    first = serialize(p)
    regenerate(p)
    assert serialize(p) == first


def test_a_reset_gives_the_connector_back_at_the_next_generate():
    p, hid, (a, _b) = generated()
    original = conn(p, hid, a)
    apply_ops(p, plan_edit_connector(p, hid, a, part_id="EX-MICROD-9-F", gender="female"))
    regenerate(p)
    assert conn(p, hid, a).part_id == "EX-MICROD-9-F"
    apply_ops(p, plan_reset_connector(p, hid, a))
    assert not conn(p, hid, a).locked
    regenerate(p)
    assert conn(p, hid, a) == original


def test_a_generated_connector_refuses_what_follows_the_device():
    p, hid, (a, _b) = generated()
    with pytest.raises(EditError, match="comes from its ID"):
        plan_edit_connector(p, hid, a, name="Renamed")
    with pytest.raises(EditError, match="Cable contact"):
        plan_edit_pin(p, hid, a, "1", contact_part="x")
    for call in (
        lambda: plan_add_pins(p, hid, a, ["99"]),
        lambda: plan_delete_pin(p, hid, a, "1"),
        lambda: plan_rename_pin(p, hid, a, "1", "Z"),
    ):
        with pytest.raises(EditError, match="Devices tab"):
            call()


def test_an_edited_connector_that_generation_cannot_keep_is_named_in_a_warning():
    p, hid, (a, _b) = generated()
    apply_ops(p, plan_edit_connector(p, hid, a, gender="female"))
    box_id = conn(p, hid, a).mates_with
    # the device connector goes away (its interfaces too): the cable end cannot be carried over
    gone = {
        i.id for i in p.interfaces.values() if any(e.connector_id == box_id for e in i.endpoints)
    }
    for iid in gone:
        del p.interfaces[iid]
    report = plan_generation(p).report
    text = " ".join(f.message for f in report.findings)
    assert "locked_data_lost" in {f.code for f in report.findings}
    assert f"the edited connector {a}" in text


def test_the_contact_of_a_pin_still_follows_the_device_on_an_edited_connector():
    from harness_design_studio.core.model import Part

    p, hid, (a, _b) = generated()
    p.parts["EX-CRIMP-22"] = Part(id="EX-CRIMP-22", category="contact")
    box_id = conn(p, hid, a).mates_with
    apply_ops(p, plan_edit_connector(p, hid, a, gender="female"))
    apply_ops(p, plan_edit_pin(p, hid, a, "1", function="mine"))
    box = p.connectors[box_id]
    pins = [evolve(x, contact_part="EX-CRIMP-22") if x.id == "1" else x for x in box.pins]
    p.connectors[box_id] = evolve(box, pins=pins)
    regenerate(p)
    pin = next(x for x in conn(p, hid, a).pins if x.id == "1")
    assert (pin.function, pin.contact_part) == ("mine", "EX-CRIMP-22")
