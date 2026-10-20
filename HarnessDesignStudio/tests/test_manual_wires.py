# mypy: disable-error-code="no-untyped-def,no-untyped-call,no-any-return"
"""1.4.0 M2: wires that a person draws between two pins, kept by generation, and several wires on
one pin (the design rule `pin-shared`)."""

import json

import pytest

from harness_design_studio.core.commands import Delete, History, Put, apply_ops
from harness_design_studio.core.drc import RULES, run
from harness_design_studio.core.edit import EditError
from harness_design_studio.core.generate.engine import generate_project, plan_generation
from harness_design_studio.core.io.layout import model_hash, serialize
from harness_design_studio.core.model import evolve
from harness_design_studio.core.samples import sat15
from harness_design_studio.core.wires import (
    find_wire,
    pin_choices,
    plan_add_wire,
    plan_delete_wire,
    plan_wire_edit,
)


@pytest.fixture
def project():
    p = sat15()
    generate_project(p)
    return p


def harness(p):
    return next(h for h in sorted(p.harnesses.values(), key=lambda h: h.id) if h.wires)


def free_pins(p, h, n=2):
    """Pins of the cable connectors of `h` that no wire uses."""
    used = {(w.from_connector, w.from_pin) for w in h.wires} | {
        (w.to_connector, w.to_pin) for w in h.wires
    }
    out = [(c.id, pin.id) for c in h.connectors for pin in c.pins if (c.id, pin.id) not in used]
    assert len(out) >= n
    return out


def add(p, h, **kw):
    (c1, p1), (c2, p2) = free_pins(p, h)[:2]
    ops = plan_add_wire(p, h.id, c1, p1, c2, p2, **kw)
    apply_ops(p, ops)
    return next(w for w in p.harnesses[h.id].wires if w.manual)


def test_add_a_wire_between_two_pins(project):
    h = harness(project)
    w = add(project, h, signal="HEATER", colour="red", gauge_awg=22, label="Heat", note="by hand")
    assert w.manual and w.interface_id is None and w.signal == "HEATER"
    assert (w.colour, w.gauge_awg, w.label, w.note) == ("red", 22, "Heat", "by hand")
    assert w.id not in {x.id for x in h.wires}


def test_manual_is_written_only_when_set(project):
    h = harness(project)
    before = serialize(project)
    add(project, h)
    data = json.loads(serialize(project)[f"physical/harnesses/{h.id}.json"])
    assert sum(1 for x in data["wires"] if x.get("manual")) == 1
    assert sum(1 for x in data["wires"] if "manual" not in x) == len(h.wires)
    assert serialize(project) != before


def test_a_wrong_end_is_said_in_words(project):
    h = harness(project)
    c = h.connectors[0].id
    with pytest.raises(EditError, match="not a connector"):
        plan_add_wire(project, h.id, "NOPE", "1", c, h.connectors[0].pins[0].id)
    with pytest.raises(EditError, match="no pin"):
        plan_add_wire(project, h.id, c, "ZZZ", c, h.connectors[0].pins[0].id)
    pin = h.connectors[0].pins[0].id
    with pytest.raises(EditError, match="same pin"):
        plan_add_wire(project, h.id, c, pin, c, pin)
    with pytest.raises(EditError, match="does not exist"):
        plan_add_wire(project, "NOPE", c, pin, c, pin)


def test_generation_keeps_the_wire_a_person_drew(project):
    h = harness(project)
    w = add(project, h, signal="HEATER")
    apply_ops(project, plan_generation(project).ops)
    again = find_wire(project, w.id)[1]
    assert again == w
    assert plan_generation(project).ops == []  # a second plan is empty


def test_generation_does_not_reuse_the_id_of_a_manual_wire(project):
    h = harness(project)
    w = add(project, h)
    source = project.interfaces[next(x.interface_id for x in h.wires if x.interface_id)]
    apply_ops(project, [Put("interfaces", evolve(source, id="IF-DUP", name="a second link"))])
    plan = plan_generation(project)
    apply_ops(project, plan.ops)
    ids = [x.id for hh in project.harnesses.values() for x in hh.wires]
    assert len(ids) == len(set(ids))
    assert find_wire(project, w.id)[1].manual


def test_generation_says_when_it_cannot_keep_a_manual_wire(project):
    h = harness(project)
    w = add(project, h)
    for iid in {x.interface_id for x in h.wires if x.interface_id}:
        apply_ops(project, [Delete("interfaces", iid)])
    plan = plan_generation(project)  # the harness has nothing left to carry, so it goes
    text = " ".join(f.message for f in plan.report.findings)
    assert w.id in text and "drew" in text


def test_move_an_end_of_a_manual_wire_only(project):
    h = harness(project)
    w = add(project, h)
    c, p = free_pins(project, project.harnesses[h.id], 3)[2]
    apply_ops(project, plan_wire_edit(project, [w.id], {"to_connector": c, "to_pin": p}))
    got = find_wire(project, w.id)[1]
    assert (got.to_connector, got.to_pin) == (c, p)
    generated = next(x for x in h.wires if x.interface_id)
    with pytest.raises(EditError, match="follow its interface"):
        plan_wire_edit(project, [generated.id], {"to_pin": p})
    with pytest.raises(EditError, match="no pin"):
        plan_wire_edit(project, [w.id], {"to_pin": "ZZZ"})


def test_delete_a_manual_wire_but_not_a_generated_one(project):
    h = harness(project)
    w = add(project, h)
    hist = History(project)
    before = model_hash(project)
    hist.execute("delete wire", plan_delete_wire(project, w.id))
    assert all(x.id != w.id for x in project.harnesses[h.id].wires)
    hist.undo()
    assert model_hash(project) == before
    generated = next(x for x in h.wires if x.interface_id)
    with pytest.raises(EditError, match="generated"):
        plan_delete_wire(project, generated.id)


def test_a_released_harness_refuses_add_move_and_delete(project):
    h = harness(project)
    w = add(project, h)
    apply_ops(project, [Put("harnesses", evolve(project.harnesses[h.id], status="released"))])
    (c1, p1), (c2, p2) = free_pins(project, project.harnesses[h.id])[:2]
    with pytest.raises(EditError, match="released"):
        plan_add_wire(project, h.id, c1, p1, c2, p2)
    with pytest.raises(EditError, match="released"):
        plan_delete_wire(project, w.id)
    with pytest.raises(EditError, match="released"):
        plan_wire_edit(project, [w.id], {"to_pin": p2, "to_connector": c2})


def test_two_wires_on_one_pin_are_pointed_out_by_a_rule(project):
    assert "pin-shared" in {r.id for r in RULES}
    h = harness(project)
    assert not [f for f in run(project) if f.rule == "pin-shared"]
    w = h.wires[0]
    other = next(c for c in h.connectors if c.id != w.from_connector)
    apply_ops(
        project,
        plan_add_wire(project, h.id, w.from_connector, w.from_pin, other.id, other.pins[-1].id),
    )
    found = [f for f in run(project) if f.rule == "pin-shared"]
    assert any(f"{w.from_connector}.{w.from_pin}" in f.object_id for f in found)
    assert all(f.severity == "warning" for f in found)


def test_the_pinout_lists_both_wires_of_a_shared_pin(project):
    from harness_design_studio.core.outputs.tables import pinouts

    h = harness(project)
    w = h.wires[0]
    other = next(c for c in h.connectors if c.id != w.from_connector)
    apply_ops(
        project,
        plan_add_wire(project, h.id, w.from_connector, w.from_pin, other.id, other.pins[-1].id),
    )
    rows = pinouts(project, project.harnesses[h.id])
    row = next(r for r in rows[1:] if r[0] == w.from_connector and r[4] == w.from_pin)
    assert len(row[7].split(";")) == 2


def test_the_outputs_and_the_verifier_accept_a_manual_wire(project):
    from harness_design_studio.core.outputs.build import build_outputs
    from harness_design_studio.core.outputs.verify import verify_outputs

    h = harness(project)
    w = add(project, h, signal="HEATER")
    files = dict(build_outputs(project).files)
    assert verify_outputs(project, files).ok
    wl = files[f"harnesses/{h.id}/wirelist.csv"].decode()
    assert w.id in wl and "HEATER" in wl


def test_pin_choices_lists_the_pins_of_each_cable_connector(project):
    h = harness(project)
    choices = pin_choices(project, h.id)
    assert set(choices) == {c.id for c in h.connectors}
    assert all(pins for pins in choices.values())
