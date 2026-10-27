# mypy: disable-error-code="no-untyped-def,no-untyped-call,no-any-return"
"""REQ-WIRE-06, REQ-PIN-03, REQ-ACC-01 (1.7.0 M2, D-170): the build data a technician needs (strip lengths, contacts, accessories, crimp
tools): the edit plans, what generation keeps, the Devices pin edit, the import and the parts
import column."""

import json
from pathlib import Path

import pytest

from harness_design_studio.cli.main import main as cli_main
from harness_design_studio.core import build_data, devices
from harness_design_studio.core.build_data_import import detect_kind, plan_build_data_import
from harness_design_studio.core.commands import Delete, History, Put, apply_ops
from harness_design_studio.core.edit import EditError
from harness_design_studio.core.generate.engine import generate_project, plan_generation
from harness_design_studio.core.imports import ImportError_, read_table
from harness_design_studio.core.integrity import check_integrity
from harness_design_studio.core.io.layout import model_hash, serialize
from harness_design_studio.core.io.loader import load_project
from harness_design_studio.core.io.saver import save_project
from harness_design_studio.core.issues import errors
from harness_design_studio.core.library_import import guess_mapping, plan_parts_import
from harness_design_studio.core.manual_harness import (
    plan_add_connector,
    plan_new_harness,
    plan_set_pin,
)
from harness_design_studio.core.model import Accessory, Part, evolve
from harness_design_studio.core.pinout_import import guess_mapping as pinout_mapping
from harness_design_studio.core.pinout_import import plan_pinout_import
from harness_design_studio.core.samples import new_project, sat15
from harness_design_studio.core.wires import plan_add_wire
from harness_design_studio.resources import examples_path

CONTACT = "EX-CONTACT-22"
TEMPLATES = examples_path() / "templates"  # type: ignore[operator]
NEW_KEYS = ("strip_a_mm", "strip_b_mm", "contact_part", "accessories", '"tool"')


def with_contact(p):
    p.parts[CONTACT] = Part(id=CONTACT, category="contact")
    return p


@pytest.fixture
def generated():
    p = with_contact(sat15())
    generate_project(p)
    return p


@pytest.fixture
def own():
    """A project with a harness that a person made: two connectors and two wires."""
    p = with_contact(new_project("Scratch"))
    ops, hid = plan_new_harness(p, "Heater harness")
    apply_ops(p, ops)
    for _ in range(2):
        ops, _cid = plan_add_connector(p, hid, part_id="EX-DSUB-9-M")
        apply_ops(p, ops)
    a, b = (c.id for c in p.harnesses[hid].connectors)
    for pin in ("1", "2"):
        apply_ops(p, plan_add_wire(p, hid, a, pin, b, pin))
    return p


def hid_of(p) -> str:
    return next(iter(p.harnesses))


def first_harness(p):
    return next(h for h in p.harnesses.values() if h.wires and len(h.interfaces) == 1)


def multi_wire_harness(p):
    """W009 has four wires; it stays when the signal of its first wire is dropped."""
    return p.harnesses["W009"]


def drop_signal_of(p, w):
    """Take the signals of a wire out of its interface type: generation cannot carry the wire."""
    t = p.interface_types[p.interfaces[w.interface_id].type_id]
    gone = set(w.signal.split("/"))
    apply_ops(p, [Put("interface_types", evolve(t, signals=[x for x in t.signals if x.name not in gone]))])  # fmt: skip


def regenerate(p):
    apply_ops(p, plan_generation(p).ops)


def lost_findings(p):
    return [f for f in plan_generation(p).report.findings if f.code == "locked_data_lost"]


# ---- the fields are optional and sparse ------------------------------------------------------------


def test_a_project_without_build_data_has_no_new_keys_in_its_files(generated):
    for name, data in serialize(generated).items():
        text = data.decode("utf-8")
        assert not any(key in text for key in NEW_KEYS), (name, key_in(text))


def key_in(text):
    return [k for k in NEW_KEYS if k in text]


def test_a_project_with_build_data_loads_back_identical(tmp_path, generated):
    h = first_harness(generated)
    w = h.wires[0]
    c = h.connectors[0]
    apply_ops(generated, build_data.plan_set_strip(generated, h.id, [w.id], strip_a_mm=6.5))
    apply_ops(
        generated,
        build_data.plan_set_accessory(
            generated,
            h.id,
            Accessory(id="ACC-001", kind="sleeving", target=c.id, length_mm=120, quantity=2),
        ),
    )
    apply_ops(generated, build_data.plan_set_part_tool(generated, CONTACT, "Tool X, setting 4"))
    box = generated.connectors[c.mates_with]
    apply_ops(
        generated, devices.ops_set_pin(generated, box.id, box.pins[0].id, contact_part=CONTACT)
    )
    save_project(generated, tmp_path / "p")
    back = load_project(tmp_path / "p").project
    assert serialize(back) == serialize(generated)
    assert back.harnesses[h.id].accessories == generated.harnesses[h.id].accessories
    assert back.harnesses[h.id].wires[0].strip_a_mm == 6.5
    assert back.parts[CONTACT].tool == "Tool X, setting 4"
    assert back.connectors[box.id].pins[0].contact_part == CONTACT
    assert errors(check_integrity(back)) == []


# ---- strip lengths ---------------------------------------------------------------------------------


def test_strip_lengths_are_set_on_the_listed_wires_and_do_not_lock_them(generated):
    h = first_harness(generated)
    a, b = h.wires[0], h.wires[1]
    apply_ops(
        generated,
        build_data.plan_set_strip(generated, h.id, [a.id], strip_a_mm=6, strip_b_mm="7,5"),
    )
    now = {w.id: w for w in generated.harnesses[h.id].wires}
    assert (now[a.id].strip_a_mm, now[a.id].strip_b_mm) == (6.0, 7.5)
    assert not now[a.id].locked
    assert (now[b.id].strip_a_mm, now[b.id].strip_b_mm) == (None, None)


def test_a_strip_end_that_is_not_given_stays_and_none_clears(generated):
    h = first_harness(generated)
    wid = h.wires[0].id
    apply_ops(
        generated, build_data.plan_set_strip(generated, h.id, [wid], strip_a_mm=6, strip_b_mm=5)
    )
    apply_ops(generated, build_data.plan_set_strip(generated, h.id, [wid], strip_b_mm=None))
    w = generated.harnesses[h.id].wires[0]
    assert (w.strip_a_mm, w.strip_b_mm) == (6.0, None)
    assert build_data.plan_set_strip(generated, h.id, [wid], strip_a_mm=6) == []  # nothing changes


@pytest.mark.parametrize("value", [-1, 100001, "abc", True, float("nan")])
def test_a_strip_length_outside_0_to_100000_is_refused(generated, value):
    h = first_harness(generated)
    with pytest.raises(EditError, match="strip length"):
        build_data.plan_set_strip(generated, h.id, [h.wires[0].id], strip_a_mm=value)


def test_strip_plans_name_what_is_wrong(generated):
    h = first_harness(generated)
    with pytest.raises(EditError, match="'NOPE' is not a wire of"):
        build_data.plan_set_strip(generated, h.id, ["NOPE"], strip_a_mm=6)
    with pytest.raises(EditError, match="No wire is selected"):
        build_data.plan_set_strip(generated, h.id, [], strip_a_mm=6)
    with pytest.raises(EditError, match="Give a strip length"):
        build_data.plan_set_strip(generated, h.id, [h.wires[0].id])
    with pytest.raises(EditError, match="does not exist"):
        build_data.plan_set_strip(generated, "W999", ["x"], strip_a_mm=6)


def test_strip_all_sets_every_wire_of_the_harness(generated):
    h = first_harness(generated)
    apply_ops(generated, build_data.plan_set_strip_all(generated, h.id, strip_a_mm=6, strip_b_mm=6))
    assert all((w.strip_a_mm, w.strip_b_mm) == (6.0, 6.0) for w in generated.harnesses[h.id].wires)
    other = next(x for x in generated.harnesses.values() if x.id != h.id)
    assert all(w.strip_a_mm is None for w in other.wires)


def test_every_plan_refuses_a_released_harness(generated):
    h = first_harness(generated)
    apply_ops(generated, [Put("harnesses", evolve(h, status="released", revision="A"))])
    box = generated.connectors[h.connectors[0].mates_with]
    for call in (
        lambda: build_data.plan_set_strip(generated, h.id, [h.wires[0].id], strip_a_mm=6),
        lambda: build_data.plan_set_strip_all(generated, h.id, strip_a_mm=6),
        lambda: build_data.plan_set_contacts(generated, h.id, h.connectors[0].id, None, CONTACT),
        lambda: build_data.plan_set_accessory(
            generated, h.id, Accessory(id="ACC-001", kind="other")
        ),
        lambda: build_data.plan_delete_accessory(generated, h.id, "ACC-001"),
    ):
        with pytest.raises(EditError, match="is released"):
            call()
    assert box.id  # the unit's pin is not part of the harness


# ---- contacts and tools ----------------------------------------------------------------------------


def test_a_contact_is_set_on_pins_of_a_harness_a_person_made(own):
    hid = hid_of(own)
    a = own.harnesses[hid].connectors[0]
    apply_ops(own, build_data.plan_set_contacts(own, hid, a.id, ["1", "2"], CONTACT))
    pins = {p.id: p.contact_part for p in own.harnesses[hid].connectors[0].pins}
    assert pins["1"] == pins["2"] == CONTACT and pins["3"] is None
    apply_ops(own, build_data.plan_set_contacts(own, hid, a.id, None, CONTACT))
    assert all(p.contact_part == CONTACT for p in own.harnesses[hid].connectors[0].pins)
    apply_ops(own, build_data.plan_set_contacts(own, hid, a.id, ["1"], None))
    assert own.harnesses[hid].connectors[0].pins[0].contact_part is None
    assert build_data.plan_set_contacts(own, hid, a.id, ["2"], CONTACT) == []


def test_a_generated_harness_says_to_set_the_contact_on_the_unit_pin(generated):
    h = first_harness(generated)
    with pytest.raises(EditError, match="device's pin in the Devices tab"):
        build_data.plan_set_contacts(generated, h.id, h.connectors[0].id, ["1"], CONTACT)


def test_a_contact_must_be_a_contact_part_of_the_library(own):
    hid = hid_of(own)
    cid = own.harnesses[hid].connectors[0].id
    with pytest.raises(EditError, match="not a contact part"):
        build_data.plan_set_contacts(own, hid, cid, ["1"], "EX-DSUB-9-M")  # a connector part
    with pytest.raises(EditError, match="not a contact part"):
        build_data.plan_set_contacts(own, hid, cid, ["1"], "NO-SUCH-PART")
    with pytest.raises(EditError, match="no pin 'Z9'"):
        build_data.plan_set_contacts(own, hid, cid, ["Z9"], CONTACT)
    with pytest.raises(EditError, match="not a connector of"):
        build_data.plan_set_contacts(own, hid, "NOPE", None, CONTACT)


def test_the_tool_belongs_to_a_contact_part_and_can_be_cleared(own):
    apply_ops(own, build_data.plan_set_part_tool(own, CONTACT, "  Crimp tool Z  "))
    assert own.parts[CONTACT].tool == "Crimp tool Z"
    apply_ops(own, build_data.plan_set_part_tool(own, CONTACT, None))
    assert own.parts[CONTACT].tool is None
    with pytest.raises(EditError, match="not a contact part"):
        build_data.plan_set_part_tool(own, "EX-DSUB-9-M", "x")
    with pytest.raises(EditError, match="does not exist"):
        build_data.plan_set_part_tool(own, "NOPE", "x")
    with pytest.raises(EditError, match="no more than|1 to 200"):
        build_data.plan_set_part_tool(own, CONTACT, "x" * 201)


def test_the_tool_of_a_contact_a_released_harness_uses_cannot_change(own):
    hid = hid_of(own)
    a = own.harnesses[hid].connectors[0]
    apply_ops(own, build_data.plan_set_contacts(own, hid, a.id, ["1"], CONTACT))
    apply_ops(own, [Put("harnesses", evolve(own.harnesses[hid], status="released"))])
    with pytest.raises(EditError, match="released"):
        build_data.plan_set_part_tool(own, CONTACT, "new tool")


# ---- accessories -----------------------------------------------------------------------------------


def test_accessories_are_added_replaced_and_deleted_by_id(own):
    hid = hid_of(own)
    h = own.harnesses[hid]
    assert build_data.plan_next_accessory_id(h) == "ACC-001"
    wire = h.wires[0].id
    sleeve = Accessory(
        id="ACC-002", kind="sleeving", target=wire, position="whole wire", quantity=3
    )
    apply_ops(own, build_data.plan_set_accessory(own, hid, sleeve))
    apply_ops(own, build_data.plan_set_accessory(own, hid, Accessory(id="ACC-001", kind="other")))
    h = own.harnesses[hid]
    assert [a.id for a in h.accessories] == ["ACC-001", "ACC-002"]  # as they are saved
    assert build_data.plan_next_accessory_id(h) == "ACC-003"
    apply_ops(own, build_data.plan_set_accessory(own, hid, evolve(sleeve, quantity=5)))
    assert [a.quantity for a in own.harnesses[hid].accessories] == [1, 5]
    assert build_data.plan_set_accessory(own, hid, evolve(sleeve, quantity=5)) == []
    apply_ops(own, build_data.plan_delete_accessory(own, hid, "ACC-001"))
    assert [a.id for a in own.harnesses[hid].accessories] == ["ACC-002"]
    with pytest.raises(EditError, match="not an accessory"):
        build_data.plan_delete_accessory(own, hid, "ACC-009")


def test_an_accessory_can_sit_on_a_connector_a_wire_or_the_harness(own):
    hid = hid_of(own)
    h = own.harnesses[hid]
    for n, target in enumerate((h.connectors[0].id, h.wires[0].id, None), start=1):
        acc = Accessory(id=f"ACC-00{n}", kind="label", target=target)
        apply_ops(own, build_data.plan_set_accessory(own, hid, acc))
    assert errors(check_integrity(own)) == []


@pytest.mark.parametrize(
    ("data", "message"),
    [
        ({"id": "ACC-1", "kind": "tape"}, "kind is one of"),
        ({"id": "ACC-1", "kind": "other", "target": "NOPE"}, "not a connector or a wire"),
        ({"id": "ACC-1", "kind": "other", "part_id": "NOPE"}, "not a part of the library"),
        ({"id": "ACC-1", "kind": "other", "length_mm": -1}, "between 0 and"),
        ({"id": "ACC-1", "kind": "other", "length_mm": 100001}, "between 0 and"),
        ({"id": "ACC-1", "kind": "other", "quantity": 0}, "quantity"),
        ({"id": "ACC-1", "kind": "other", "quantity": 10000}, "quantity"),
        ({"id": "ACC-1", "kind": "other", "quantity": "two"}, "quantity"),
        ({"id": "ACC-1", "kind": "other", "position": "a" * 201}, "1 to 200"),
        ({"id": "ACC-1", "kind": "other", "position": "a\x07b"}, "control characters"),
        ({"id": "ACC-1", "kind": "other", "note": "a\x00b"}, "control characters"),
        ({"id": "ACC-1", "kind": "other", "colour": "red"}, "no field 'colour'"),
        ({"id": "", "kind": "other"}, "needs an ID"),
        ({"id": "1 bad id", "kind": "other"}, "not valid"),
    ],
)
def test_an_accessory_that_is_not_valid_is_refused(own, data, message):
    with pytest.raises(EditError, match=message):
        build_data.plan_set_accessory(own, hid_of(own), data)


def test_an_accessory_may_name_any_library_part_and_text_numbers_are_read(own):
    hid = hid_of(own)
    data = {
        "id": "ACC-001", "kind": "heat_shrink", "part_id": CONTACT, "length_mm": "30,5",
        "quantity": "4", "position": "  near P1 ", "note": "",
    }  # fmt: skip
    apply_ops(own, build_data.plan_set_accessory(own, hid, data))
    a = own.harnesses[hid].accessories[0]
    assert (a.length_mm, a.quantity, a.position, a.part_id) == (30.5, 4, "near P1", CONTACT)


# ---- the Devices tab pin and the manual harness pin -------------------------------------------------


def unit_pin(p):
    c = next(c for c in p.connectors.values() if c.role == "box")
    return c.id, c.pins[0].id


def test_a_box_pin_takes_a_contact_part_and_checks_it(generated):
    cid, pin = unit_pin(generated)
    apply_ops(generated, devices.ops_set_pin(generated, cid, pin, contact_part=CONTACT))
    assert generated.connectors[cid].pins[0].contact_part == CONTACT
    row = devices.pin_rows(generated, cid)[0]
    assert row.contact_part == CONTACT
    with pytest.raises(EditError, match="not a contact part"):
        devices.ops_set_pin(generated, cid, pin, contact_part="NOPE")
    apply_ops(generated, devices.ops_set_pin(generated, cid, pin, contact_part=""))
    assert generated.connectors[cid].pins[0].contact_part is None


def test_pasted_rows_fill_the_contact_and_a_bad_part_is_a_row_issue(generated):
    cid, pin = unit_pin(generated)
    rows = [{"pin": pin, "contact_part": CONTACT}]
    apply_ops(generated, devices.ops_paste_rows(generated, cid, rows))
    assert generated.connectors[cid].pins[0].contact_part == CONTACT
    plan = devices.plan_pin_rows(generated, cid, [{"pin": pin, "contact_part": "NOPE"}])
    assert [i.reason for i in plan.issues] == ["'NOPE' is not a contact part of the library (category contact)"]  # fmt: skip
    assert "contact_part" in devices.GRID_COLUMNS


def test_the_bulk_fill_sets_several_pins_in_one_step(generated):
    cid, _pin = unit_pin(generated)
    ids = [p.id for p in generated.connectors[cid].pins[:3]]
    history = History(generated)
    history.execute("Fill contacts", devices.ops_set_contacts(generated, cid, ids, CONTACT))
    pins = generated.connectors[cid].pins
    assert [p.contact_part for p in pins[:3]] == [CONTACT] * 3 and pins[3].contact_part is None
    history.undo()
    assert all(p.contact_part is None for p in generated.connectors[cid].pins)
    with pytest.raises(EditError, match="not a contact part"):
        devices.ops_set_contacts(generated, cid, ids, "NOPE")
    with pytest.raises(EditError, match="No pin is selected"):
        devices.ops_set_contacts(generated, cid, [], CONTACT)


def test_the_pinout_import_reads_cable_contact_and_contact_next_to_pin(generated):
    cid, pin = unit_pin(generated)
    for heading in ("Cable contact", "Contact"):
        table = [["Connector", "Pin", heading], [cid, pin, CONTACT]]
        mapping = pinout_mapping(table[0])
        assert mapping["contact_part"] == 2 and mapping["pin"] == 1
        plan = plan_pinout_import(
            generated, table, mapping, unit_id=generated.connectors[cid].unit_id
        )
        assert plan.importable, [r.message for r in plan.rows]
        work = generated
        apply_ops(work, plan.ops)
        assert work.connectors[cid].pins[0].contact_part == CONTACT
        apply_ops(work, devices.ops_set_pin(work, cid, pin, contact_part=""))


def test_a_sheet_with_only_a_contact_heading_still_means_the_pin():
    assert pinout_mapping(["Connector", "Contact", "Signal"]) == {
        "connector": 0, "pin": 1, "signal": 2,
    }  # fmt: skip


def test_a_manual_pin_takes_a_contact_part_and_a_mating_connector_copies_it(generated, own):
    hid = hid_of(own)
    a = own.harnesses[hid].connectors[0]
    apply_ops(own, plan_set_pin(own, hid, a.id, "1", contact_part=CONTACT))
    assert own.harnesses[hid].connectors[0].pins[0].contact_part == CONTACT
    with pytest.raises(EditError, match="not a contact part"):
        plan_set_pin(own, hid, a.id, "1", contact_part="EX-DSUB-9-M")
    cid, pin = unit_pin(generated)
    apply_ops(generated, devices.ops_set_pin(generated, cid, pin, contact_part=CONTACT))
    ops, hid2 = plan_new_harness(generated, "By hand")
    apply_ops(generated, ops)
    ops, new = plan_add_connector(generated, hid2, mates_with=cid)
    apply_ops(generated, ops)
    pins = {p.id: p for p in generated.harnesses[hid2].connectors[0].pins}
    assert pins[pin].contact_part == CONTACT and new


# ---- generation keeps what a person entered ---------------------------------------------------------


def test_strip_lengths_survive_generation_like_a_note(generated):
    h = first_harness(generated)
    wid = h.wires[0].id
    apply_ops(
        generated, build_data.plan_set_strip(generated, h.id, [wid], strip_a_mm=6, strip_b_mm=5)
    )
    before = serialize(generated)
    plan = plan_generation(generated)
    assert plan.ops == []  # byte-identical regeneration
    regenerate(generated)
    assert serialize(generated) == before
    w = next(x for x in generated.harnesses[h.id].wires if x.id == wid)
    assert (w.strip_a_mm, w.strip_b_mm) == (6.0, 5.0) and not w.locked


def test_a_strip_length_that_cannot_be_carried_over_is_reported(generated):
    h = multi_wire_harness(generated)
    w = h.wires[0]
    apply_ops(generated, build_data.plan_set_strip(generated, h.id, [w.id], strip_a_mm=6))
    drop_signal_of(generated, w)
    lost = lost_findings(generated)
    assert len(lost) == 1 and w.id in lost[0].message
    assert "wire with a strip length" in lost[0].message and lost[0].object_id == h.id


def test_a_labelled_wire_with_a_strip_length_is_reported_as_a_labelled_wire(generated):
    h = multi_wire_harness(generated)
    w = h.wires[0]
    apply_ops(generated, build_data.plan_set_strip(generated, h.id, [w.id], strip_a_mm=6))
    apply_ops(generated, [Put("harnesses", evolve(generated.harnesses[h.id], wires=[evolve(w, note="x"), *h.wires[1:]]))])  # fmt: skip
    drop_signal_of(generated, w)
    assert "wire with a label or note" in lost_findings(generated)[0].message


def test_a_unit_pin_contact_is_copied_to_the_cable_pin(generated):
    h = first_harness(generated)
    cable = h.connectors[0]
    box = generated.connectors[cable.mates_with]
    apply_ops(
        generated, devices.ops_set_pin(generated, box.id, box.pins[0].id, contact_part=CONTACT)
    )
    regenerate(generated)
    now = next(c for c in generated.harnesses[h.id].connectors if c.id == cable.id)
    assert now.pins[0].contact_part == CONTACT
    assert all(p.contact_part is None for p in now.pins[1:])
    assert plan_generation(generated).ops == []


def test_accessories_stay_while_their_target_exists(generated):
    h = first_harness(generated)
    cable, wire = h.connectors[0].id, h.wires[0].id
    for acc in (
        Accessory(id="ACC-001", kind="sleeving", target=cable, length_mm=100),
        Accessory(id="ACC-002", kind="heat_shrink", target=wire, quantity=2),
        Accessory(id="ACC-003", kind="label"),
    ):
        apply_ops(generated, build_data.plan_set_accessory(generated, h.id, acc))
    before = serialize(generated)
    assert plan_generation(generated).ops == []
    regenerate(generated)
    assert serialize(generated) == before
    assert [a.id for a in generated.harnesses[h.id].accessories] == [
        "ACC-001",
        "ACC-002",
        "ACC-003",
    ]
    assert errors(check_integrity(generated)) == []


def test_accessories_that_cannot_be_kept_are_listed(generated):
    h = multi_wire_harness(generated)
    w = h.wires[0]
    acc = Accessory(id="ACC-001", kind="heat_shrink", target=w.id)
    apply_ops(generated, build_data.plan_set_accessory(generated, h.id, acc))
    keep = Accessory(id="ACC-002", kind="sleeving", target=h.wires[2].id)
    apply_ops(generated, build_data.plan_set_accessory(generated, h.id, keep))
    apply_ops(
        generated,
        build_data.plan_set_accessory(generated, h.id, Accessory(id="ACC-003", kind="label")),
    )
    drop_signal_of(generated, w)
    lost = lost_findings(generated)
    assert len(lost) == 1 and f"the accessory ACC-001 (heat shrink on {w.id})" in lost[0].message
    assert "ACC-002" not in lost[0].message and "ACC-003" not in lost[0].message
    regenerate(generated)
    assert [a.id for a in generated.harnesses[h.id].accessories] == ["ACC-002", "ACC-003"]
    assert errors(check_integrity(generated)) == []


def test_accessories_of_a_harness_that_goes_are_listed_too(generated):
    h = first_harness(generated)
    apply_ops(
        generated,
        build_data.plan_set_accessory(generated, h.id, Accessory(id="ACC-001", kind="label")),
    )
    apply_ops(generated, [Delete("interfaces", i) for i in h.interfaces])
    lost = [f for f in lost_findings(generated) if f.object_id == h.id]
    assert lost and "the accessory ACC-001 (label on the harness)" in lost[0].message


# ---- the import -------------------------------------------------------------------------------------


def write(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8")
    return path


def folder(tmp_path, project) -> Path:
    save_project(project, tmp_path / "p")
    return tmp_path / "p"


def test_the_kind_is_found_from_the_headings_in_any_case():
    kinds = {
        "strips": ["harness", "WIRE", "strip a (mm)", "Strip B (mm)", "Other"],
        "contacts": ["Connector", "PIN", "contact"],
        "accessories": ["Harness", "Kind", "Part", "Target", "Length (mm)", "Quantity"],
        "tools": ["Part", "Crimp tool"],
    }
    for kind, header in kinds.items():
        assert detect_kind(header)[0] == kind
    with pytest.raises(ImportError_, match="Expected strip lengths: Wire, Strip A"):
        detect_kind(["Name", "Value"])


def test_strip_lengths_are_imported_with_and_without_a_harness_column(tmp_path, generated):
    h = first_harness(generated)
    a, b = h.wires[0].id, h.wires[1].id
    p = folder(tmp_path, generated)
    f = write(
        tmp_path / "s.csv",
        f"Harness,Wire,Strip A (mm),Strip B (mm),Comment\n{h.id},{a},6,7,x\n,{b},5,,y\n",
    )
    assert cli_main(["import-build-data", str(p), str(f)]) == 0
    now = {w.id: w for w in load_project(p).project.harnesses[h.id].wires}
    assert (now[a].strip_a_mm, now[a].strip_b_mm) == (6.0, 7.0)
    assert (now[b].strip_a_mm, now[b].strip_b_mm) == (5.0, None)  # an empty cell leaves it


def test_a_dry_run_writes_nothing_and_prints_the_counts(tmp_path, capsys, generated):
    h = first_harness(generated)
    wid = h.wires[0].id
    p = folder(tmp_path, generated)
    f = write(tmp_path / "s.csv", f"Wire,Strip A (mm)\n{wid},6\n")
    before = model_hash(load_project(p).project)
    assert cli_main(["import-build-data", str(p), str(f), "--dry-run"]) == 0
    out = capsys.readouterr().out
    assert "1 added, 0 changed, 0 unchanged, 0 refused." in out and "Dry run" in out
    assert model_hash(load_project(p).project) == before
    assert cli_main(["import-build-data", str(p), str(f)]) == 0
    capsys.readouterr()
    assert cli_main(["import-build-data", str(p), str(f)]) == 0
    out = capsys.readouterr().out
    assert "0 added, 0 changed, 1 unchanged, 0 refused." in out
    assert "Already up to date." in out and "Build data imported" not in out  # C-5
    write(f, f"Wire,Strip A (mm)\n{wid},7\n")
    assert cli_main(["import-build-data", str(p), str(f), "--dry-run"]) == 0
    assert "0 added, 1 changed" in capsys.readouterr().out


def test_a_refused_row_stops_everything_and_says_why(tmp_path, capsys, generated):
    h = first_harness(generated)
    wid = h.wires[0].id
    p = folder(tmp_path, generated)
    f = write(tmp_path / "s.csv", f"Wire,Strip A (mm)\n{wid},6\nNOPE,5\n{wid},-3\n")
    before = model_hash(load_project(p).project)
    assert cli_main(["import-build-data", str(p), str(f)]) == 1
    out = capsys.readouterr().out
    assert "row 3: ERROR Wire 'NOPE' does not exist." in out and "row 4: ERROR" in out
    assert "1 added, 0 changed, 0 unchanged, 2 refused." in out and "Nothing was changed." in out
    assert model_hash(load_project(p).project) == before


def test_a_wire_id_in_two_harnesses_needs_a_harness_column(generated):
    """The checks forbid it, but a damaged project can have it: the row says what to add."""
    one, two = list(generated.harnesses.values())[:2]
    w = one.wires[0]
    twin = evolve(two.wires[0], id=w.id)
    apply_ops(generated, [Put("harnesses", evolve(two, wires=[twin, *two.wires[1:]]))])
    plan = plan_build_data_import(generated, [["Wire", "Strip A (mm)"], [w.id, "6"]])
    assert [r.ok for r in plan.rows] == [False] and "add a Harness column" in plan.rows[0].message
    plan = plan_build_data_import(
        generated, [["Harness", "Wire", "Strip A (mm)"], [one.id, w.id, "6"]]
    )
    assert plan.bad_count == 0


def test_headings_of_no_kind_exit_2_and_name_the_expected_ones(tmp_path, capsys, generated):
    p = folder(tmp_path, generated)
    f = write(tmp_path / "x.csv", "Name,Value\na,1\n")
    assert cli_main(["import-build-data", str(p), str(f)]) == 2
    err = capsys.readouterr().err
    assert (
        "Expected strip lengths: Wire, Strip A (mm), Strip B (mm)" in err and "Name, Value" in err
    )
    assert cli_main(["import-build-data", str(p), str(tmp_path / "nope.csv")]) == 2
    write(f, "Wire,Strip A (mm)\n")
    assert cli_main(["import-build-data", str(p), str(f)]) == 2


def test_contacts_and_their_tool_are_imported_for_a_harness_a_person_made(tmp_path, own):
    hid = hid_of(own)
    a = own.harnesses[hid].connectors[0].id
    p = folder(tmp_path, own)
    f = write(tmp_path / "c.csv", f"Harness,Connector,Pin,Contact,Tool\n{hid},{a},1,{CONTACT},Tool Z\n,{a},2,{CONTACT},Tool Z\n")  # fmt: skip
    assert cli_main(["import-build-data", str(p), str(f)]) == 0
    q = load_project(p).project
    pins = {x.id: x.contact_part for x in q.harnesses[hid].connectors[0].pins}
    assert pins["1"] == pins["2"] == CONTACT and q.parts[CONTACT].tool == "Tool Z"


def test_a_contact_row_of_a_generated_harness_is_refused_with_the_reason(
    tmp_path, capsys, generated
):
    h = first_harness(generated)
    p = folder(tmp_path, generated)
    f = write(tmp_path / "c.csv", f"Harness,Connector,Pin,Contact\n{h.id},{h.connectors[0].id},1,{CONTACT}\n")  # fmt: skip
    assert cli_main(["import-build-data", str(p), str(f)]) == 1
    assert "device's pin in the Devices tab" in capsys.readouterr().out


def test_two_tools_for_one_contact_in_a_file_are_refused(tmp_path, capsys, own):
    hid = hid_of(own)
    a = own.harnesses[hid].connectors[0].id
    p = folder(tmp_path, own)
    f = write(tmp_path / "c.csv", f"Connector,Pin,Contact,Tool\n{a},1,{CONTACT},T1\n{a},2,{CONTACT},T2\n")  # fmt: skip
    assert cli_main(["import-build-data", str(p), str(f)]) == 1
    assert "has the tool 'T1' in an earlier row" in capsys.readouterr().out


def test_accessories_are_imported_numbered_and_not_added_twice(tmp_path, capsys, own):
    hid = hid_of(own)
    h = own.harnesses[hid]
    p = folder(tmp_path, own)
    text = (
        "Harness,Kind,Part,Target,Position,Length (mm),Quantity,Note\n"
        f"{hid},sleeving,,{h.wires[0].id},whole wire,,2,first\n"
        f"{hid},Heat Shrink,,{h.connectors[0].id},near the connector,30,1,second\n"
    )
    f = write(tmp_path / "a.csv", text)
    assert cli_main(["import-build-data", str(p), str(f)]) == 0
    acc = load_project(p).project.harnesses[hid].accessories
    assert [(a.id, a.kind, a.quantity, a.length_mm) for a in acc] == [
        ("ACC-001", "sleeving", 2, None),
        ("ACC-002", "heat_shrink", 1, 30.0),
    ]
    assert cli_main(["import-build-data", str(p), str(f)]) == 0  # the same file again
    assert "0 added, 0 changed, 2 unchanged, 0 refused." in capsys.readouterr().out
    assert len(load_project(p).project.harnesses[hid].accessories) == 2


def test_an_accessory_with_an_id_is_replaced_and_a_bad_one_is_refused(tmp_path, capsys, own):
    hid = hid_of(own)
    p = folder(tmp_path, own)
    f = write(tmp_path / "a.csv", f"ID,Harness,Kind,Quantity\nACC-007,{hid},label,1\n")
    assert cli_main(["import-build-data", str(p), str(f)]) == 0
    write(f, f"ID,Harness,Kind,Quantity\nACC-007,{hid},label,3\n")
    assert cli_main(["import-build-data", str(p), str(f)]) == 0
    acc = load_project(p).project.harnesses[hid].accessories
    assert [(a.id, a.quantity) for a in acc] == [("ACC-007", 3)]
    write(f, f"Harness,Kind,Target\n{hid},tape,\nNOPE,label,\n{hid},label,GHOST\n")
    capsys.readouterr()
    assert cli_main(["import-build-data", str(p), str(f)]) == 1
    out = capsys.readouterr().out
    assert "kind is one of" in out and "Harness 'NOPE' does not exist" in out
    assert "'GHOST' is not a connector or a wire" in out and "3 refused" in out


def test_part_tools_are_imported(tmp_path, own):
    p = folder(tmp_path, own)
    f = write(tmp_path / "t.csv", f"Part,Tool\n{CONTACT},Tool Q\n")
    assert cli_main(["import-build-data", str(p), str(f)]) == 0
    assert load_project(p).project.parts[CONTACT].tool == "Tool Q"


def test_the_import_is_one_undoable_step_and_a_released_harness_blocks_it(own):
    hid = hid_of(own)
    a = own.harnesses[hid].connectors[0].id
    table = [["Connector", "Pin", "Contact"], [a, "1", CONTACT], [a, "2", CONTACT]]
    plan = plan_build_data_import(own, table)
    assert plan.bad_count == 0 and len(plan.ops) == 1  # one Put for the harness
    history = History(own)
    before = model_hash(own)
    history.execute(plan.label, plan.ops)
    history.undo()
    assert model_hash(own) == before
    apply_ops(own, [Put("harnesses", evolve(own.harnesses[hid], status="released"))])
    assert plan_build_data_import(own, table).bad_count == 2


def test_the_shipped_templates_are_read_as_their_kind():
    for name, kind in (
        ("strip-lengths.csv", "strips"),
        ("pin-contacts.csv", "contacts"),
        ("accessories.csv", "accessories"),
    ):
        table = read_table(TEMPLATES / name)
        assert detect_kind(table[0])[0] == kind, name
        assert len(table) >= 3
        assert all("EXAMPLE" in " ".join(row) for row in table[1:]), name


def test_the_template_rows_import_into_a_matching_project(own):
    """The accessories template names W001 and its wires; a harness made by hand has them."""
    hid = hid_of(own)
    wires = [w.id for w in own.harnesses[hid].wires]
    conns = [c.id for c in own.harnesses[hid].connectors]
    table = read_table(TEMPLATES / "accessories.csv")
    rows = [table[0]]
    for r in table[1:]:
        r = list(r)
        r[1] = hid
        r[4] = {"W001-001": wires[0], "W001-P1": conns[0]}.get(r[4], r[4])
        rows.append(r)
    plan = plan_build_data_import(own, rows)
    assert plan.bad_count == 0, [r.message for r in plan.rows]


# ---- the parts import --------------------------------------------------------------------------------


@pytest.mark.parametrize("heading", ["Tool", "Crimp tool", "crimp TOOL"])
def test_the_parts_import_reads_the_tool_of_a_contact_part(heading):
    p = new_project("x")
    table = [
        ["Part ID", "Category", heading],
        ["C-1", "contact", "Tool Q"],
        ["K-1", "connector", "ignored"],
    ]
    plan = plan_parts_import(p, table, guess_mapping(table[0]), approved=[], default_category=None)
    assert all(r.ok for r in plan.rows), [r.message for r in plan.rows]
    apply_ops(p, plan.ops)
    assert p.parts["C-1"].tool == "Tool Q" and p.parts["K-1"].tool is None


def test_a_part_import_without_a_tool_column_keeps_the_tool():
    p = with_contact(new_project("x"))
    apply_ops(p, build_data.plan_set_part_tool(p, CONTACT, "Tool Q"))
    table = [["Part ID", "Category", "Description"], [CONTACT, "contact", "22 AWG contact"]]
    plan = plan_parts_import(p, table, guess_mapping(table[0]), approved=[])
    apply_ops(p, plan.ops)
    assert p.parts[CONTACT].tool == "Tool Q" and p.parts[CONTACT].description == "22 AWG contact"


def test_the_parts_json_reads_the_tool_too(tmp_path):
    text = json.dumps([{"IPN": "C-9", "category": "contact", "Crimp tool": "Z"}])
    f = write(tmp_path / "parts.json", text)
    table = read_table(f)
    p = new_project("x")
    plan = plan_parts_import(p, table, guess_mapping(table[0]), approved=[])
    apply_ops(p, plan.ops)
    assert p.parts["C-9"].tool == "Z"


def test_a_device_library_file_carries_the_contact_parts_of_its_pins(generated):
    """Found by the documents: the file named a pin's contact but not the part, so a project that
    imported the device had a reference to a part it did not have."""
    from harness_design_studio.core.device_library import export_devices

    box = next(c for c in generated.connectors.values() if c.unit_id and c.pins)
    pins = [evolve(box.pins[0], contact_part=CONTACT), *box.pins[1:]]
    generated.connectors[box.id] = evolve(box, pins=pins)
    library = export_devices(generated, [box.unit_id])
    assert CONTACT in {part["id"] for part in library["parts"]}


def test_a_contact_or_an_accessory_part_that_is_not_in_the_library_is_an_error(generated):
    from harness_design_studio.core.integrity import check_integrity

    box = next(c for c in generated.connectors.values() if c.pins)
    pins = [evolve(box.pins[0], contact_part="NO-SUCH-CONTACT"), *box.pins[1:]]
    generated.connectors[box.id] = evolve(box, pins=pins)
    assert "unknown_part" in {i.code for i in check_integrity(generated)}
