# mypy: disable-error-code="no-untyped-def,no-untyped-call,no-any-return"
"""A harness built from nothing: a new harness, its cable connectors, pins and wires, with no
interface behind it. Generate leaves it alone; checks, outputs, review and release work as for any
other harness."""

import pytest

from harness_design_studio.core.commands import History, apply_ops
from harness_design_studio.core.drc import run
from harness_design_studio.core.edit import EditError
from harness_design_studio.core.generate.engine import generate_project, plan_generation
from harness_design_studio.core.integrity import check_integrity
from harness_design_studio.core.manual_harness import (
    is_own,
    plan_add_connector,
    plan_delete_connector,
    plan_new_harness,
    plan_set_pin,
)
from harness_design_studio.core.model import evolve
from harness_design_studio.core.model.config import ConfigFile
from harness_design_studio.core.outputs.build import build_outputs
from harness_design_studio.core.samples import new_project, sat15
from harness_design_studio.core.verify import verify_project
from harness_design_studio.core.wires import plan_add_wire, plan_wire_edit


def blank():
    """A project with starter parts and no unit."""
    return new_project("Scratch")


def make(p, name="Heater harness"):
    ops, hid = plan_new_harness(p, name)
    apply_ops(p, ops)
    return hid


def two_connectors(p, hid, part="EX-DSUB-9-M"):
    ids = []
    for _ in range(2):
        ops, cid = plan_add_connector(p, hid, part_id=part)
        apply_ops(p, ops)
        ids.append(cid)
    return ids


def test_a_new_harness_is_an_empty_draft_that_generation_did_not_make():
    p = blank()
    hid = make(p)
    h = p.harnesses[hid]
    assert (h.id, h.name, h.status, h.generated) == ("W001", "Heater harness", "draft", False)
    assert (h.connectors, h.wires, h.interfaces) == ([], [], [])
    assert make(p, "Second") == "W002"


def test_the_harness_name_is_checked():
    p = blank()
    make(p)
    with pytest.raises(EditError, match="needs a name"):
        plan_new_harness(p, "   ")
    with pytest.raises(EditError, match="exists already"):
        plan_new_harness(p, "heater HARNESS")
    with pytest.raises(EditError, match="1 to 200"):
        plan_new_harness(p, "a\x00b")


def test_the_naming_pattern_of_the_project_is_used():
    p = blank()
    values = {
        **p.config["naming"].values,
        "harness": "HX-{n:02d}",
        "cable_connector": "{harness}.C{n}",
    }
    p.config["naming"] = ConfigFile(name="naming", placeholder=False, values=values)
    hid = make(p)
    assert hid == "HX-01"
    ops, cid = plan_add_connector(p, hid, part_id="EX-DSUB-9-M")
    assert cid == "HX-01.C1"


def test_a_free_standing_connector_has_the_pins_of_its_part():
    p = blank()
    hid = make(p)
    ops, cid = plan_add_connector(p, hid, part_id="EX-DSUB-9-M")
    apply_ops(p, ops)
    c = p.harnesses[hid].connectors[0]
    assert (c.id, c.name, c.role, c.part_id, c.mates_with) == (
        cid,
        "P1",
        "cable",
        "EX-DSUB-9-M",
        None,
    )
    assert [x.id for x in c.pins] == [str(i) for i in range(1, 10)]
    assert c.gender == "male"
    assert cid == "W001-P1"
    ops, second = plan_add_connector(p, hid, part_id="EX-DSUB-9-F", name="Heater end")
    assert second == "W001-P2"
    apply_ops(p, ops)
    assert p.harnesses[hid].connectors[1].name == "Heater end"


def test_the_pins_can_be_named():
    p = blank()
    hid = make(p)
    ops, _ = plan_add_connector(p, hid, part_id="EX-DSUB-9-M", pin_ids=["A1", "A2", "B1"])
    apply_ops(p, ops)
    assert [x.id for x in p.harnesses[hid].connectors[0].pins] == ["A1", "A2", "B1"]
    with pytest.raises(EditError, match="listed twice"):
        plan_add_connector(p, hid, part_id="EX-DSUB-9-M", pin_ids=["A", "a"])
    with pytest.raises(EditError, match="9 pins"):
        plan_add_connector(p, hid, part_id="EX-DSUB-9-M", pin_ids=[str(i) for i in range(10)])
    with pytest.raises(EditError, match="cannot be used as a pin name"):
        plan_add_connector(p, hid, part_id="EX-DSUB-9-M", pin_ids=["a b"])


def test_a_connector_needs_a_real_connector_part():
    p = blank()
    hid = make(p)
    with pytest.raises(EditError, match="Choose the connector part"):
        plan_add_connector(p, hid)
    with pytest.raises(EditError, match="not a connector part"):
        plan_add_connector(p, hid, part_id="nothing")
    wire_part = next(x.id for x in p.parts.values() if x.category == "wire")
    with pytest.raises(EditError, match="not a connector part"):
        plan_add_connector(p, hid, part_id=wire_part)
    with pytest.raises(EditError, match="role is one of"):
        plan_add_connector(p, hid, part_id="EX-DSUB-9-M", role="plug")


def test_a_connector_that_plugs_into_a_unit_copies_its_side():
    p = sat15()
    box = next(c for c in sorted(p.connectors.values(), key=lambda c: c.id) if c.pins)
    hid = make(p)
    ops, cid = plan_add_connector(p, hid, mates_with=box.id)
    apply_ops(p, ops)
    c = next(x for x in p.harnesses[hid].connectors if x.id == cid)
    assert c.mates_with == box.id and c.role == "cable"
    assert [x.id for x in c.pins] == [x.id for x in box.pins]
    assert c.keying == box.keying
    flip = {"male": "female", "female": "male"}.get(box.gender)
    if flip:
        assert c.gender == flip
    with pytest.raises(EditError, match="has a connector for"):
        plan_add_connector(p, hid, mates_with=box.id)
    with pytest.raises(EditError, match="not a connector of a unit"):
        plan_add_connector(p, hid, mates_with="nope")
    with pytest.raises(EditError, match="Only a cable connector"):
        plan_add_connector(p, hid, mates_with=box.id, role="inline")


def test_wires_are_drawn_between_the_new_connectors_and_the_harness_checks_and_builds():
    p = blank()
    hid = make(p)
    a, b = two_connectors(p, hid)
    apply_ops(p, plan_add_wire(p, hid, a, "1", b, "1", signal="HEATER", colour="red", gauge_awg=22))
    apply_ops(p, plan_add_wire(p, hid, a, "2", b, "2", signal="RETURN"))
    assert [x for x in check_integrity(p) if x.severity == "error"] == []
    assert verify_project(p).ok
    files = build_outputs(p).files
    assert f"harnesses/{hid}/wirelist.csv" in files
    text = files[f"harnesses/{hid}/wirelist.csv"].decode()
    assert "HEATER" in text and "RETURN" in text
    assert [f.id for f in run(p) if f.severity == "error"] == []  # the design checks run on it


def test_generation_leaves_a_harness_made_by_hand_alone():
    p = sat15()
    generate_project(p)
    before = set(p.harnesses)
    hid = make(p)
    a, b = two_connectors(p, hid)
    apply_ops(p, plan_add_wire(p, hid, a, "1", b, "1", signal="X"))
    apply_ops(p, plan_set_pin(p, hid, a, "1", function="HEATER +"))
    snapshot = p.harnesses[hid]
    plan = plan_generation(p)
    apply_ops(p, plan.ops)
    assert p.harnesses[hid] == snapshot
    assert set(p.harnesses) == before | {hid}
    assert plan.report.removed == []


def test_the_pins_can_be_given_a_function_a_termination_and_a_contact_size():
    p = blank()
    hid = make(p)
    a, _b = two_connectors(p, hid)
    apply_ops(p, plan_set_pin(p, hid, a, "3", function="HEATER +", termination="solder"))
    apply_ops(p, plan_set_pin(p, hid, a, "3", contact_size="22"))
    pin = next(x for x in p.harnesses[hid].connectors[0].pins if x.id == "3")
    assert (pin.function, pin.termination, pin.contact_size) == ("HEATER +", "solder", "22")
    apply_ops(p, plan_set_pin(p, hid, a, "3", function="  ", termination="unspecified"))
    pin = next(x for x in p.harnesses[hid].connectors[0].pins if x.id == "3")
    assert (pin.function, pin.termination) == (None, "unspecified")
    with pytest.raises(EditError, match="termination is one of"):
        plan_set_pin(p, hid, a, "3", termination="glue")
    with pytest.raises(EditError, match="no pin"):
        plan_set_pin(p, hid, a, "99", function="x")
    with pytest.raises(EditError, match="no field"):
        plan_set_pin(p, hid, a, "3", signal="x")
    with pytest.raises(EditError, match="not a connector of"):
        plan_set_pin(p, hid, "nope", "3", function="x")


def test_a_connector_with_wires_stays_until_the_wires_go():
    p = blank()
    hid = make(p)
    a, b = two_connectors(p, hid)
    apply_ops(p, plan_add_wire(p, hid, a, "1", b, "1"))
    with pytest.raises(EditError, match="has wires"):
        plan_delete_connector(p, hid, a)
    from harness_design_studio.core.wires import plan_delete_wires

    apply_ops(p, plan_delete_wires(p, [p.harnesses[hid].wires[0].id]))
    apply_ops(p, plan_delete_connector(p, hid, a))
    assert [c.id for c in p.harnesses[hid].connectors] == [b]
    with pytest.raises(EditError, match="not a connector of"):
        plan_delete_connector(p, hid, a)


def test_a_generated_harness_refuses_connectors():
    p = sat15()
    generate_project(p)
    gen = next(h for h in p.harnesses.values() if h.generated)
    assert not is_own(p, gen.id)
    with pytest.raises(EditError, match="made by Generate"):
        plan_add_connector(p, gen.id, part_id="EX-DSUB-9-M")
    with pytest.raises(EditError, match="made by Generate"):
        plan_delete_connector(p, gen.id, gen.connectors[0].id)
    with pytest.raises(EditError, match="does not exist"):
        plan_add_connector(p, "nope", part_id="EX-DSUB-9-M")


def test_a_released_harness_refuses_changes():
    p = blank()
    hid = make(p)
    a, _b = two_connectors(p, hid)
    apply_ops(
        p,
        [
            __import__("harness_design_studio.core.commands", fromlist=["Put"]).Put(
                "harnesses", evolve(p.harnesses[hid], status="released")
            )
        ],
    )
    assert not is_own(p, hid)
    with pytest.raises(EditError, match="is released"):
        plan_add_connector(p, hid, part_id="EX-DSUB-9-M")
    with pytest.raises(EditError, match="is released"):
        plan_delete_connector(p, hid, a)
    with pytest.raises(EditError, match="is released"):
        plan_set_pin(p, hid, a, "1", function="x")


def test_a_read_only_project_refuses_everything():
    p = blank()
    hid = make(p)
    p.read_only = True
    with pytest.raises(EditError, match="read-only"):
        plan_new_harness(p, "Another")
    with pytest.raises(EditError, match="read-only"):
        plan_add_connector(p, hid, part_id="EX-DSUB-9-M")


def test_every_step_is_one_undo_step_and_the_wire_editor_works_on_the_new_wires():
    p = blank()
    hist = History(p)
    ops, hid = plan_new_harness(p, "By hand")
    hist.execute("New harness", ops)
    ops, a = plan_add_connector(p, hid, part_id="EX-DSUB-9-M")
    hist.execute("Add connector", ops)
    ops, b = plan_add_connector(p, hid, part_id="EX-DSUB-9-F")
    hist.execute("Add connector", ops)
    hist.execute("Add wire", plan_add_wire(p, hid, a, "1", b, "1", signal="S"))
    wid = p.harnesses[hid].wires[0].id
    hist.execute("Edit wire", plan_wire_edit(p, [wid], {"colour": "blue"}))
    assert p.harnesses[hid].wires[0].colour == "blue"
    for _ in range(5):
        hist.undo()
    assert hid not in p.harnesses
    hist.redo()
    assert hid in p.harnesses
