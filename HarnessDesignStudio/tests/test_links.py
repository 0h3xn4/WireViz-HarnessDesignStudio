# mypy: disable-error-code="no-untyped-def,no-untyped-call,no-any-return"
"""M2a: links, the pinout first. Pairing by signal name, the planners and their refusals, what a link
carries, the review, the harness made from a link, and the save/load round trip. No Qt."""

import random

import pytest

from harness_design_studio.core.commands import Delete, History, Put, apply_ops
from harness_design_studio.core.devices import ops_set_pin
from harness_design_studio.core.edit import EditError
from harness_design_studio.core.errors import TransactionError
from harness_design_studio.core.generate.engine import plan_generation
from harness_design_studio.core.integrity import check_integrity
from harness_design_studio.core.io.layout import serialize
from harness_design_studio.core.io.loader import load_project
from harness_design_studio.core.io.saver import save_project
from harness_design_studio.core.links import (
    check_link,
    check_links,
    derived_interfaces,
    effective_role,
    name_relation,
    natural_key,
    plan_add_link,
    plan_create_harness,
    plan_delete_link,
    plan_rename_link,
    plan_set_pairs,
    propose_pairs,
)
from harness_design_studio.core.model import Link, Pin, PinPair, evolve
from harness_design_studio.core.samples import mini3
from harness_design_studio.core.verify import verify_project
from tests.helpers import pinout_project

RS = ("OBC-J01", "RW1-J02")  # RS-422 pins 1 to 4: TX+, TX-, RX+, RX-
PWR = ("PCDU-J02", "OBC-J02")  # pins 1 and 2: PWR, RTN


def pairs(*items):
    return [PinPair(a_pin=a, b_pin=b) for a, b in items]


def set_pins(p, cid, *signals):
    """Give a connector pins 1..n with these signals (None: no signal)."""
    p.connectors[cid] = p.connectors[cid].model_copy(
        update={"pins": [Pin(id=str(k + 1), signal=s) for k, s in enumerate(signals)]}
    )


def linked(p, a, b, *items, **kw):
    ops, lid = plan_add_link(p, a, b, [tuple(x) for x in items] or None, **kw)
    apply_ops(p, ops)
    return lid


# ---- pairing by signal name --------------------------------------------------------------------


def test_signal_names_relate_when_equal_or_the_two_ends_of_a_line():
    assert name_relation("PWR", "pwr") == "equal"
    for a, b in (
        ("TX", "RX"),
        ("RXD", "TXD"),
        ("TX+", "RX+"),
        ("TX-", "RX-"),
        ("TXP", "RXP"),
        ("RXN", "TXN"),
    ):
        assert name_relation(a, b) == "counterpart", (a, b)
    assert name_relation("TX+", "RX-") == ""
    assert name_relation("TX", "TX+") == ""
    assert name_relation(None, "TX") == "" and name_relation("", "") == ""


def test_pins_are_read_in_natural_order():
    assert sorted(["10", "2", "A10", "A2", "1"], key=natural_key) == ["1", "2", "10", "A2", "A10"]


def test_a_transmit_pin_pairs_with_a_receive_pin_by_name_not_by_position():
    p = pinout_project()
    r = propose_pairs(p, *RS)
    assert [(x.a_pin, x.b_pin) for x in r.pairs] == [("1", "3"), ("2", "4"), ("3", "1"), ("4", "2")]
    assert r.unpaired_a == ("5",) and r.unpaired_b == ("5",)  # a pin with no signal is left over
    assert r.notes == ()


def test_power_and_return_pair_with_themselves():
    r = propose_pairs(pinout_project(), *PWR)
    assert [(x.a_pin, x.b_pin) for x in r.pairs] == [("1", "1"), ("2", "2")]
    assert r.unpaired_a == ("3",) and r.unpaired_b == ("3",)


def test_a_bidirectional_signal_pairs_with_the_same_name():
    p = pinout_project()
    set_pins(p, "OBC-J03", "CANL", "CANH")
    set_pins(p, "PCDU-J03", "CANH", "CANL")
    r = propose_pairs(p, "OBC-J03", "PCDU-J03")
    assert [(x.a_pin, x.b_pin) for x in r.pairs] == [("1", "2"), ("2", "1")]


def test_output_against_output_and_input_against_input_do_not_pair_and_are_named():
    p = pinout_project()
    set_pins(p, "OBC-J03", "TX+", "RX-")
    set_pins(p, "PCDU-J03", "TX+", "RX-")
    r = propose_pairs(p, "OBC-J03", "PCDU-J03")
    assert r.pairs == ()
    assert r.unpaired_a == ("1", "2") and r.unpaired_b == ("1", "2")
    assert any("both are outputs" in n and "TX+" in n for n in r.notes)
    assert any("both are inputs" in n and "RX-" in n for n in r.notes)


def test_counterparts_with_no_known_direction_cross_over():
    p = pinout_project()
    set_pins(p, "OBC-J03", "TXD", "RXD")  # no interface type has these names
    set_pins(p, "PCDU-J03", "TXD", "RXD")
    r = propose_pairs(p, "OBC-J03", "PCDU-J03")
    assert [(x.a_pin, x.b_pin) for x in r.pairs] == [("1", "2"), ("2", "1")]


def test_a_pin_is_used_once():
    p = pinout_project()
    set_pins(p, "OBC-J03", "PWR", "PWR", "RTN")
    set_pins(p, "PCDU-J03", "PWR", "RTN")
    r = propose_pairs(p, "OBC-J03", "PCDU-J03")
    assert [(x.a_pin, x.b_pin) for x in r.pairs] == [("1", "1"), ("3", "2")]
    assert r.unpaired_a == ("2",) and r.unpaired_b == ()


def test_the_proposal_does_not_depend_on_the_order_the_pins_are_listed_in():
    p = pinout_project()
    first = propose_pairs(p, *RS)
    for cid in RS:
        pins = list(p.connectors[cid].pins)
        random.Random(7).shuffle(pins)
        p.connectors[cid] = p.connectors[cid].model_copy(update={"pins": pins})
    assert propose_pairs(p, *RS) == first == propose_pairs(p, *RS)


def test_a_proposal_leaves_out_pins_that_another_link_has():
    p = pinout_project()
    linked(p, *RS, ("1", "3"))
    r = propose_pairs(p, "OBC-J01", "PCDU-J03")  # OBC pin 1 is taken
    assert "1" not in r.unpaired_a
    assert any("already paired in link L1" in n for n in r.notes)


def test_the_proposal_needs_connectors_of_two_different_devices():
    p = pinout_project()
    with pytest.raises(EditError, match="same device"):
        propose_pairs(p, "OBC-J01", "OBC-J02")
    with pytest.raises(EditError, match="not a connector of a device"):
        propose_pairs(p, "OBC-J01", "W001-P1")
    with pytest.raises(EditError, match="not a connector of a device"):
        propose_pairs(p, "OBC-J01", "NOPE")


# ---- the planners ------------------------------------------------------------------------------


def test_a_link_gets_the_next_free_id_and_the_proposed_pairs():
    p = pinout_project()
    ops, lid = plan_add_link(p, *RS, name="  Wheel data ")
    assert lid == "L1"
    assert isinstance(ops[0], Put) and ops[0].collection == "links"
    History(p).execute("Link connectors", ops)
    link = p.links["L1"]
    assert (link.name, link.a_connector, link.b_connector, link.harness_id) == (
        "Wheel data",
        *RS,
        "",
    )
    assert [(x.a_pin, x.b_pin) for x in link.pairs] == [
        ("1", "3"),
        ("2", "4"),
        ("3", "1"),
        ("4", "2"),
    ]
    assert linked(p, *PWR) == "L2"
    assert check_integrity(p) == []


def test_a_link_accepts_pairs_and_an_id_and_checks_them():
    p = pinout_project()
    _ops, lid = plan_add_link(p, *RS, [("1", "3")], link_id="WHEEL1")
    assert lid == "WHEEL1"
    for bad, text in (
        ([("1", "99")], "no pin '99'"),
        ([("1", "3"), ("1", "4")], "two pairs"),
        ([("1", "3"), ("2", "3")], "two pairs"),
        ([("1",)], "A pair is"),
    ):
        with pytest.raises(EditError, match=text):
            plan_add_link(p, *RS, bad)  # type: ignore[arg-type]
    for ident in ("OBC", "bad id", "W001"):
        with pytest.raises(EditError):
            plan_add_link(p, *RS, [], link_id=ident)
    with pytest.raises(EditError, match="two different devices"):
        plan_add_link(p, "OBC-J01", "OBC-J02")


def test_a_pin_cannot_be_in_two_links_but_a_connector_can():
    p = pinout_project()
    linked(p, *RS, ("1", "3"))
    with pytest.raises(EditError, match=r"Pin 1 of OBC-J01 is already paired in link L1"):
        plan_add_link(p, "OBC-J01", "PCDU-J03", [("1", "1")])
    assert linked(p, "OBC-J01", "PCDU-J03", ("2", "1")) == "L2"


def test_pairs_change_and_a_link_is_renamed_and_deleted():
    p = pinout_project()
    h = History(p)
    lid = linked(p, *RS)
    h.execute("Change pairs", plan_set_pairs(p, lid, [("1", "3"), ("2", "4")]))
    assert len(p.links[lid].pairs) == 2
    assert plan_set_pairs(p, lid, [("1", "3"), ("2", "4")]) == []
    with pytest.raises(EditError, match="no pin '9'"):
        plan_set_pairs(p, lid, [("9", "3")])
    h.execute("Rename", plan_rename_link(p, lid, "Data"))
    assert p.links[lid].name == "Data"
    h.execute("Rename", plan_rename_link(p, lid, ""))
    assert p.links[lid].name == ""
    with pytest.raises(EditError, match="does not exist"):
        plan_rename_link(p, "L9", "x")
    h.execute("Delete link", plan_delete_link(p, lid))
    assert p.links == {}
    h.undo()
    assert lid in p.links


def test_a_read_only_project_refuses_every_plan():
    p = pinout_project()
    lid = linked(p, *RS)
    p.read_only = True
    for call in (
        lambda: plan_add_link(p, *PWR),
        lambda: plan_set_pairs(p, lid, []),
        lambda: plan_rename_link(p, lid, "x"),
        lambda: plan_delete_link(p, lid),
        lambda: plan_create_harness(p, lid),
    ):
        with pytest.raises(EditError, match="read-only"):
            call()


# ---- what a link carries -----------------------------------------------------------------------


def test_the_pairs_of_a_link_are_grouped_by_the_interface_type_of_their_signals():
    p = pinout_project()
    set_pins(p, "OBC-J03", "CANH", "CANL", "PWR", "RTN")
    set_pins(p, "PCDU-J03", "CANH", "CANL", "PWR", "RTN")
    lid = linked(p, "OBC-J03", "PCDU-J03")
    got = derived_interfaces(p)
    assert [(d.link_id, d.type_id, d.label) for d in got[:1]] == [(lid, "can", "CAN, 2 wires")]
    assert got[1].label == "Primary power or Secondary power, 2 wires"  # the two types are equal
    assert got[1].type_id == "power_primary" and got[1].alternatives == (
        "power_primary",
        "power_secondary",
    )
    assert [(x.a_pin, x.b_pin) for x in got[0].pairs] == [("1", "1"), ("2", "2")]


def test_a_pair_no_type_explains_is_named_as_such_and_nothing_is_stored():
    p = pinout_project()
    set_pins(p, "OBC-J03", "XYZ")
    set_pins(p, "PCDU-J03", "XYZ")
    linked(p, "OBC-J03", "PCDU-J03")
    (d,) = derived_interfaces(p)
    assert (d.type_id, d.label) == ("", "No interface type, 1 wire")
    assert "label" not in serialize(p)["logical/links.json"].decode()
    assert derived_interfaces(mini3()) == []


# ---- roles -------------------------------------------------------------------------------------


def test_the_role_is_the_one_given_or_the_one_the_signal_name_says():
    p = pinout_project()
    c = p.connectors["OBC-J01"]
    assert effective_role(Pin(id="1"), p) == ""
    assert effective_role(Pin(id="1", signal="PWR"), p) == "power"
    assert effective_role(Pin(id="1", signal="HTR+"), p) == "power"  # a heater type is a power type
    assert effective_role(Pin(id="1", signal="RTN"), p) == "return"
    assert effective_role(Pin(id="1", signal="gnd"), p) == "ground"
    assert effective_role(Pin(id="1", signal="TX+"), p, c) == "signal"
    assert effective_role(Pin(id="1", signal="XYZ"), p) == "signal"
    assert effective_role(Pin(id="1", signal="PWR", role="spare"), p) == "spare"
    assert effective_role(Pin(id="1", role="shield"), p) == "shield"


def test_a_pin_role_is_set_through_the_device_planner_and_cleared_with_empty():
    p = pinout_project()
    h = History(p)
    h.execute("Role", ops_set_pin(p, "OBC-J01", "5", role="spare"))
    assert p.connectors["OBC-J01"].pins[4].role == "spare"
    h.execute("Role", ops_set_pin(p, "OBC-J01", "5", role=""))
    assert p.connectors["OBC-J01"].pins[4].role == ""
    with pytest.raises(EditError, match="pin role"):
        ops_set_pin(p, "OBC-J01", "5", role="boss")


# ---- the review --------------------------------------------------------------------------------


def codes(p, link):
    return sorted(f.code for f in check_link(p, link))


def test_a_link_with_the_proposed_pairs_has_nothing_to_report():
    p = pinout_project()
    linked(p, *RS)
    linked(p, *PWR)
    assert check_links(p) == []


def test_a_pin_with_a_signal_that_no_pair_uses_is_reported_on_either_side():
    p = pinout_project()
    lid = linked(p, *RS, ("2", "4"), ("3", "1"), ("4", "2"))
    found = [f for f in check_link(p, p.links[lid]) if f.code == "link_pin_unpaired"]
    assert [f.pin for f in found] == ["OBC-J01.1", "RW1-J02.3"]
    assert all(f.severity == "warning" and lid in f.message for f in found)
    assert "Spare" in found[0].message


def test_a_spare_pin_and_a_pin_of_another_link_are_not_reported_as_unpaired():
    p = pinout_project()
    lid = linked(p, *RS, ("2", "4"), ("3", "1"), ("4", "2"))
    History(p).execute("Spare", ops_set_pin(p, "OBC-J01", "1", role="spare"))
    set_pins(p, "PCDU-J03", "RX+")
    linked(p, "PCDU-J03", "RW1-J02", ("1", "3"))  # RW1-J02 pin 3 is in another link now
    assert [f for f in check_link(p, p.links[lid]) if f.code == "link_pin_unpaired"] == []


def test_output_against_output_is_an_error():
    p = pinout_project()
    lid = linked(p, *RS, ("1", "1"), ("2", "4"))
    (f,) = [f for f in check_link(p, p.links[lid]) if f.code == "link_direction_conflict"]
    assert f.severity == "error" and f.pin == "OBC-J01.1" and "outputs" in f.message
    assert "Pair the pin" in f.message


def test_input_against_input_is_an_error():
    p = pinout_project()
    lid = linked(p, *RS, ("3", "3"))
    (f,) = [f for f in check_link(p, p.links[lid]) if f.code == "link_direction_conflict"]
    assert "Nothing drives the pair" in f.message


def test_signal_names_that_differ_are_a_warning_and_a_missing_name_too():
    p = pinout_project()
    lid = linked(p, *RS, ("1", "2"), ("5", "3"))
    got = [f for f in check_link(p, p.links[lid]) if f.code == "link_signal_mismatch"]
    assert [f.severity for f in got] == ["warning", "warning"]
    assert "TX+ and TX-" in got[0].message and "has no signal" in got[1].message


def test_power_without_a_return_is_a_warning_and_a_return_role_cures_it():
    p = pinout_project()
    lid = linked(p, *PWR, ("1", "1"))
    (f,) = [f for f in check_link(p, p.links[lid]) if f.code == "link_power_without_return"]
    assert f.severity == "warning" and "return" in f.message and "1-1" in f.message
    # RTN is the return by its name; a pair of two unnamed pins with the role Return counts too
    History(p).execute("Role", ops_set_pin(p, "PCDU-J02", "3", role="return"))
    History(p).execute("Role", ops_set_pin(p, "OBC-J02", "3", role="return"))
    History(p).execute("Pairs", plan_set_pairs(p, lid, [("1", "1"), ("3", "3")]))
    assert "link_power_without_return" not in codes(p, p.links[lid])


def test_a_pin_in_two_pairs_or_two_links_is_an_error():
    p = pinout_project()
    p.links["L1"] = Link(
        id="L1", a_connector=RS[0], b_connector=RS[1], pairs=pairs(("1", "3"), ("1", "4"))
    )
    p.links["L2"] = Link(
        id="L2", a_connector=RS[0], b_connector="PCDU-J03", pairs=pairs(("2", "1"))
    )
    p.links["L3"] = Link(
        id="L3", a_connector="PCDU-J03", b_connector=RS[1], pairs=pairs(("2", "4"))
    )
    assert [f.pin for f in check_link(p, p.links["L1"]) if f.code == "link_pin_reused"] == [
        "OBC-J01.1",
        "RW1-J02.4",
    ]
    assert codes(p, p.links["L2"]).count("link_pin_reused") == 0  # OBC pin 2 is only in L2


def test_a_connector_or_pin_that_is_gone_is_dangling():
    p = pinout_project()
    lid = linked(p, *RS)
    del p.connectors["RW1-J02"]
    assert codes(p, p.links[lid]) == ["link_dangling"]
    p2 = pinout_project()
    lid = linked(p2, *RS)
    p2.connectors["OBC-J01"] = p2.connectors["OBC-J01"].model_copy(update={"pins": []})
    assert "link_dangling" in codes(p2, p2.links[lid])


def test_the_messages_say_device_not_unit():
    p = pinout_project()
    linked(p, *RS, ("1", "1"), ("3", "3"))
    set_pins(p, "PCDU-J03", "XYZ")
    for f in check_links(p):
        assert "unit" not in f.message.lower()
    with pytest.raises(EditError) as err:
        plan_add_link(p, "OBC-J01", "OBC-J02")
    assert "unit" not in str(err.value).lower()


# ---- Create harness ----------------------------------------------------------------------------


def test_a_harness_is_made_from_a_link_in_one_undo_step():
    p = pinout_project()
    lid = linked(p, *RS)
    h = History(p)
    before = h.revision
    ops, hid = plan_create_harness(p, lid)
    h.execute("Create harness", ops)
    assert h.revision == before + 1
    harness = p.harnesses[hid]
    assert hid == "W002" and harness.generated is False and harness.status == "draft"
    assert harness.name == "OBC to RW1"
    assert sorted(c.mates_with for c in harness.connectors) == sorted(RS)
    assert all(c.role == "cable" for c in harness.connectors)
    assert len(harness.wires) == 4 and all(w.manual for w in harness.wires)
    cable = {c.mates_with: c.id for c in harness.connectors}
    ends = {(w.from_connector, w.from_pin, w.to_connector, w.to_pin) for w in harness.wires}
    assert (cable["OBC-J01"], "1", cable["RW1-J02"], "3") in ends
    assert sorted(w.signal for w in harness.wires) == ["RX+/TX+", "RX-/TX-", "TX+/RX+", "TX-/RX-"]
    assert all(
        (w.gauge_awg, w.part_id, w.colour, w.length_m) == (None, None, None, None)
        for w in harness.wires
    )
    assert p.links[lid].harness_id == hid
    h.undo()
    assert hid not in p.harnesses and p.links[lid].harness_id == ""
    h.redo()
    assert p.links[lid].harness_id == hid


def test_the_harness_of_a_link_passes_integrity_and_the_verifier():
    p = pinout_project()
    del p.interfaces["IF-TM-RW1"]  # the interface-first way would want wires for its pins
    for cid in ("OBC-J03", "PCDU-J03"):
        set_pins(p, cid, "TX+", "TX-", "RX+", "RX-")
    linked(p, "OBC-J03", "PCDU-J03")
    linked(p, *PWR)
    for lid in ("L1", "L2"):
        ops, _hid = plan_create_harness(p, lid)
        History(p).execute("Create harness", ops)
    assert [i for i in check_integrity(p) if i.severity == "error"] == []
    report = verify_project(p)
    assert report.ok, [i.message for i in report.issues]


def test_generate_leaves_the_harness_of_a_link_alone():
    p = pinout_project()
    lid = linked(p, *RS)
    ops, hid = plan_create_harness(p, lid)
    History(p).execute("Create harness", ops)
    snapshot = p.harnesses[hid]
    plan = plan_generation(p)
    apply_ops(p, plan.ops)
    assert p.harnesses[hid] == snapshot and p.links[lid].harness_id == hid
    assert plan.report.removed == []


def test_create_harness_refuses_with_a_reason():
    p = pinout_project()
    empty = linked(p, *PWR, ("3", "3"))
    p.links[empty] = evolve(p.links[empty], pairs=[])
    with pytest.raises(EditError, match="no pairs"):
        plan_create_harness(p, empty)
    lid = linked(p, *RS)
    ops, hid = plan_create_harness(p, lid)
    History(p).execute("Create harness", ops)
    with pytest.raises(EditError, match=f"has the harness {hid} already"):
        plan_create_harness(p, lid)
    with pytest.raises(EditError, match="does not exist"):
        plan_create_harness(p, "L9")


def test_a_harness_name_that_is_taken_gets_the_link_id():
    p = pinout_project()
    a = linked(p, *RS, name="Data")
    b = linked(p, *PWR, name="data")
    for lid in (a, b):
        ops, _ = plan_create_harness(p, lid)
        History(p).execute("Create harness", ops)
    assert sorted(h.name for h in p.harnesses.values() if not h.name.startswith("PCDU")) != []
    assert len({h.name.casefold() for h in p.harnesses.values()}) == len(p.harnesses)


def test_deleting_the_harness_clears_the_link_and_deleting_a_device_takes_its_links():
    from harness_design_studio.core.devices import ops_delete_connector
    from harness_design_studio.core.edit import ops_delete_harness, ops_delete_unit

    p = pinout_project()
    lid = linked(p, *RS)
    ops, hid = plan_create_harness(p, lid)
    History(p).execute("Create harness", ops)
    with pytest.raises(EditError, match="has wires"):  # the hand-made harness blocks the connector
        ops_delete_connector(p, "OBC-J01")
    History(p).execute("Delete harness", ops_delete_harness(p, hid))
    assert p.links[lid].harness_id == "" and check_integrity(p) == []
    History(p).execute("Delete device", ops_delete_unit(p, "OBC"))
    assert p.links == {} and check_integrity(p) == []


def test_a_pin_in_a_link_cannot_be_deleted_or_renamed_before_the_link_changes():
    from harness_design_studio.core.devices import ops_delete_pins, ops_rename_pin

    p = pinout_project()
    linked(p, *RS)
    with pytest.raises(EditError, match="paired in link L1"):
        ops_delete_pins(p, "OBC-J01", ["1"])
    with pytest.raises(EditError, match="paired in link L1"):
        ops_rename_pin(p, "OBC-J01", "1", "A1")
    assert ops_delete_pins(p, "OBC-J01", ["5"])  # the unpaired pin can go


# ---- files -------------------------------------------------------------------------------------


def test_links_and_pin_roles_survive_save_and_load(tmp_path):
    p = pinout_project()
    lid = linked(p, *RS, name="Wheel data")
    History(p).execute("Role", ops_set_pin(p, "OBC-J01", "5", role="spare"))
    ops, hid = plan_create_harness(p, lid)
    History(p).execute("Create harness", ops)
    save_project(p, tmp_path / "p")
    r = load_project(tmp_path / "p")
    assert not r.has_errors
    assert r.project.links == p.links and r.project.links[lid].harness_id == hid
    assert r.project.connectors["OBC-J01"].pins[4].role == "spare"


def test_a_project_without_links_or_roles_writes_the_files_it_always_wrote():
    p = mini3()
    files = serialize(p)
    assert "logical/links.json" not in files
    assert b'"role": ""' not in b"".join(v for k, v in files.items() if k.startswith("physical/"))
    assert b"links" not in files["logical/layout.json"]


def test_delete_op_of_a_link_is_undone():
    p = pinout_project()
    lid = linked(p, *RS)
    h = History(p)
    h.execute("x", [Delete("links", lid)])
    assert p.links == {}
    h.undo()
    assert lid in p.links
    with pytest.raises(TransactionError):  # a link to a connector that is not there is refused
        h.execute("x", [Put("links", Link(id="L7", a_connector="OBC-J01", b_connector="NOPE"))])
