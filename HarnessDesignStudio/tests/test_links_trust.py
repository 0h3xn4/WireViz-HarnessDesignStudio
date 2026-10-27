# mypy: disable-error-code="no-untyped-def,no-untyped-call,no-any-return"
"""REQ-GUI-11, REQ-DRC-05. 1.8.1 trust fixes for links: one-directional signals are not a direction
conflict (B-03), counterparts are found by words and transmit to transmit is never paired
(F-01, F-12, A-10), a heater pair is its own loop (B-15), a device joined only by a link is not
isolated (F-09), a device connector takes one plug (A-1, B-01), a harness made from a link is checked
against the link (C-1, A-15). No Qt."""

from functools import lru_cache

import pytest

from harness_design_studio.cli.main import main
from harness_design_studio.core import checks
from harness_design_studio.core.commands import History, apply_ops
from harness_design_studio.core.edit import EditError, clone_with
from harness_design_studio.core.generate.engine import plan_generation
from harness_design_studio.core.integrity import check_integrity
from harness_design_studio.core.io.loader import load_project
from harness_design_studio.core.io.saver import save_project
from harness_design_studio.core.links import (
    check_link,
    name_relation,
    plan_add_link,
    plan_create_harness,
    plan_delete_link,
    plan_set_pairs,
    propose_pairs,
    same_side,
)
from harness_design_studio.core.manual_harness import plan_add_connector, plan_new_harness
from harness_design_studio.core.model import (
    Connector,
    Endpoint,
    InterfaceInstance,
    Pin,
    Unit,
    evolve,
)
from harness_design_studio.core.model.config import ConfigFile
from harness_design_studio.core.outputs.build import build_outputs
from harness_design_studio.core.outputs.verify import verify_outputs
from harness_design_studio.core.samples import new_project
from harness_design_studio.core.verify import link_issues, verify_project
from harness_design_studio.core.wires import plan_add_wire
from harness_design_studio.resources import examples_path
from tests.helpers import pinout_project

EXAMPLES = examples_path()
assert EXAMPLES is not None
FLATSAT = EXAMPLES / "projects" / "flatsat"


@lru_cache(maxsize=1)
def _flatsat():
    return load_project(FLATSAT).project


def flatsat():
    """The flatsat example as a pinout-first project: its generated harnesses and the interface
    allocation of its pins are taken away, so links can be drawn on the pinouts (the pins keep
    their signals)."""
    p = clone_with(_flatsat(), [])
    p.harnesses.clear()
    for cid, c in list(p.connectors.items()):
        p.connectors[cid] = evolve(c, pins=[evolve(x, interface_id=None) for x in c.pins])
    return p


def set_pins(p, cid, *signals):
    p.connectors[cid] = p.connectors[cid].model_copy(
        update={"pins": [Pin(id=str(k + 1), signal=s) for k, s in enumerate(signals)]}
    )


def pairs_of(r):
    return [(x.a_pin, x.b_pin) for x in r.pairs]


def codes(findings):
    return sorted({f.code for f in findings})


# ---- B-03: one-directional signals ------------------------------------------------------------


@pytest.mark.parametrize(
    ("a", "b", "want"),
    [
        ("SS1-J02", "RIU1-J04", [("1", "1"), ("2", "2")]),  # analog SIG+ / SIG-
        ("RIU1-J06", "MTQ1-J02", [("1", "1"), ("2", "2")]),  # discrete SIG + RTN
    ],
)
def test_one_directional_signals_are_proposed_and_raise_no_direction_error(a, b, want):
    p = flatsat()
    assert pairs_of(propose_pairs(p, a, b)) == want
    ops, lid = plan_add_link(p, a, b)
    apply_ops(p, ops)
    assert check_link(p, p.links[lid]) == []


def test_one_directional_pairs_made_by_hand_are_not_a_conflict():
    p = flatsat()
    ops, lid = plan_add_link(p, "SS1-J02", "RIU1-J04", [("1", "1"), ("2", "2")])
    apply_ops(p, ops)
    assert "link_direction_conflict" not in codes(check_link(p, p.links[lid]))


@pytest.mark.parametrize("types", [("lvds", ["D+", "D-"]), ("pyro", ["FIRE+", "FIRE-"])])
def test_lvds_and_pyro_pairs_are_proposed(types):
    p = pinout_project()
    set_pins(p, "OBC-J03", *types[1])
    set_pins(p, "PCDU-J03", *types[1])
    r = propose_pairs(p, "OBC-J03", "PCDU-J03")
    assert pairs_of(r) == [("1", "1"), ("2", "2")]


def test_two_way_types_still_report_output_against_output():
    p = pinout_project()  # RS-422 TX+ out, RX+ in: judged
    ops, lid = plan_add_link(p, "OBC-J01", "RW1-J02", [("1", "1"), ("3", "3")])
    apply_ops(p, ops)
    assert "link_direction_conflict" in codes(check_link(p, p.links[lid]))


# ---- F-01, F-12, A-10: counterparts by words --------------------------------------------------

VENDOR = ["UART_TX", "UART_RX", "SPW_DOUT+", "SPW_DOUT-", "SPW_DIN+", "SPW_DIN-"]


def test_vendor_style_names_pair_transmit_with_receive():
    p = pinout_project()
    set_pins(p, "OBC-J01", *VENDOR)
    set_pins(p, "RW1-J02", *VENDOR)
    r = propose_pairs(p, "OBC-J01", "RW1-J02")
    assert pairs_of(r) == [("1", "2"), ("2", "1"), ("3", "5"), ("4", "6"), ("5", "3"), ("6", "4")]
    assert r.unpaired_a == () and r.unpaired_b == ()


def test_the_other_device_may_name_the_same_pins_the_other_way_round():
    p = pinout_project()
    set_pins(p, "OBC-J01", "UART_TX", "UART_RX")
    set_pins(p, "RW1-J02", "UART_RX", "UART_TX")
    assert pairs_of(propose_pairs(p, "OBC-J01", "RW1-J02")) == [("1", "1"), ("2", "2")]


@pytest.mark.parametrize(
    ("x", "y"),
    [
        ("TXD+", "RXD+"),
        ("TX_P", "RX_P"),
        ("TX_N", "RX_N"),
        ("TX1", "RX1"),
        ("DOUT", "DIN"),
        ("MOSI", "MISO"),
        ("SDO", "SDI"),
        ("SPW_DOUT-", "SPW_DIN-"),
        ("UART1_TX", "UART1_RX"),
        ("UART_TX", "RX"),  # a prefix on one side only
    ],
)
def test_counterpart_words(x, y):
    assert name_relation(x, y) == "counterpart" == name_relation(y, x)
    p = pinout_project()
    set_pins(p, "OBC-J03", x)
    set_pins(p, "PCDU-J03", y)
    assert pairs_of(propose_pairs(p, "OBC-J03", "PCDU-J03")) == [("1", "1")]


@pytest.mark.parametrize(
    ("x", "y"),
    [("TX_P", "RX_N"), ("TX1", "RX2"), ("UART1_TX", "UART2_RX"), ("TX+", "RX-"), ("A", "B")],
)
def test_words_that_do_not_fit_are_no_counterpart(x, y):
    assert name_relation(x, y) == ""


def test_equal_names_with_a_transmit_word_are_never_paired():
    p = pinout_project()
    set_pins(p, "OBC-J03", "UART_TX", "SPW_DOUT+", "UART_RX", "MOSI")
    set_pins(p, "PCDU-J03", "UART_TX", "SPW_DOUT+", "UART_RX", "MOSI")
    r = propose_pairs(p, "OBC-J03", "PCDU-J03")
    # UART_TX meets UART_RX, MOSI has no partner and stays alone
    assert pairs_of(r) == [("1", "3"), ("3", "1")]
    assert r.unpaired_a == ("2", "4") and r.unpaired_b == ("2", "4")
    text = " ".join(r.notes)
    assert "SPW_DOUT+ on pin 2" in text and "look like transmit to transmit" in text
    assert "MOSI on pin 4" in text


def test_equal_receive_names_are_never_paired_either():
    p = pinout_project()
    set_pins(p, "OBC-J03", "DIN")
    set_pins(p, "PCDU-J03", "DIN")
    r = propose_pairs(p, "OBC-J03", "PCDU-J03")
    assert r.pairs == () and any("receive to receive" in n for n in r.notes)


def test_a_and_b_and_other_equal_names_still_pair_by_name():
    p = pinout_project()
    set_pins(p, "OBC-J03", "A", "B", "SYNC")
    set_pins(p, "PCDU-J03", "A", "B", "SYNC")
    assert pairs_of(propose_pairs(p, "OBC-J03", "PCDU-J03")) == [("1", "1"), ("2", "2"), ("3", "3")]


def test_same_side_names_only_when_equal_and_in_the_family():
    assert same_side("uart_tx", "UART_TX") == "transmit"
    assert same_side("DIN", "din") == "receive"
    assert same_side("UART_TX", "UART_RX") == ""
    assert same_side("PWR", "PWR") == ""
    assert same_side("", "") == ""


def test_an_existing_transmit_to_transmit_pair_is_a_warning():
    p = pinout_project()
    set_pins(p, "OBC-J03", "UART_TX", "UART_RX")
    set_pins(p, "PCDU-J03", "UART_TX", "UART_RX")
    ops, lid = plan_add_link(p, "OBC-J03", "PCDU-J03", [("1", "1"), ("2", "2")])
    apply_ops(p, ops)
    fs = check_link(p, p.links[lid])
    mism = [f for f in fs if f.code == "link_signal_mismatch"]
    assert len(mism) == 2
    assert "transmit to transmit" in mism[0].message and "receive to receive" in mism[1].message
    assert all(f.severity == "warning" for f in mism)


def test_a_crossed_pair_of_the_same_names_has_no_finding():
    p = pinout_project()
    set_pins(p, "OBC-J03", "UART_TX", "UART_RX")
    set_pins(p, "PCDU-J03", "UART_TX", "UART_RX")
    ops, lid = plan_add_link(p, "OBC-J03", "PCDU-J03", [("1", "2"), ("2", "1")])
    apply_ops(p, ops)
    assert check_link(p, p.links[lid]) == []


# ---- B-15: a heater pair is a loop ------------------------------------------------------------


def test_a_heater_pair_needs_no_extra_return():
    p = flatsat()
    ops, lid = plan_add_link(p, "PCDU1-J11", "HTR1-J01")
    apply_ops(p, ops)
    assert check_link(p, p.links[lid]) == []


def test_power_without_a_return_is_still_reported():
    p = pinout_project()
    set_pins(p, "PCDU-J02", "PWR", None)
    set_pins(p, "OBC-J02", "PWR", None)
    ops, lid = plan_add_link(p, "PCDU-J02", "OBC-J02", [("1", "1")])
    apply_ops(p, ops)
    assert "link_power_without_return" in codes(check_link(p, p.links[lid]))


def test_one_heater_wire_alone_is_still_reported():
    p = flatsat()
    ops, lid = plan_add_link(p, "PCDU1-J11", "HTR1-J01", [("1", "1")])
    apply_ops(p, ops)
    assert "link_power_without_return" in codes(check_link(p, p.links[lid]))


# ---- F-09: links are connections --------------------------------------------------------------


def test_a_device_joined_only_by_a_link_is_not_isolated():
    p = pinout_project()
    p.interfaces.clear()  # nothing but the link may join them
    before = {f.object_id for f in checks.find(p) if f.rule == "isolated"}
    ops, _ = plan_add_link(p, "OBC-J01", "RW1-J02")
    apply_ops(p, ops)
    after = {f.object_id for f in checks.find(p) if f.rule == "isolated"}
    assert {"OBC", "RW1"} <= before
    assert not ({"OBC", "RW1"} & after)


# ---- A-1, B-01: a device connector takes one plug ----------------------------------------------


def shared_project(mode="per_connector_pair"):
    """Devices A, B, C; IF-1 A-J01 to B-J01 and IF-2 A-J01 to C-J01 (one connector, two partners)."""
    p = new_project("shared")
    old = p.config["segmentation"]
    p.config["segmentation"] = ConfigFile(
        name="segmentation", placeholder=True, values={**old.values, "mode": mode}
    )
    p.zones = ["z1", "z2"]
    for uid, zone in (("A", "z1"), ("B", "z1"), ("C", "z2")):
        p.units[uid] = Unit(id=uid, name=uid, subsystem="s", zone=zone, side="nominal")
        cid = f"{uid}-J01"
        p.connectors[cid] = Connector(
            id=cid, name="J01", role="box", part_id="EX-MICROD-25-F", unit_id=uid,
            gender="female", pins=[Pin(id=str(k + 1)) for k in range(25)],
        )  # fmt: skip
    for iid, tid, other in (("IF-1", "rs422", "B"), ("IF-2", "can", "C")):
        p.interfaces[iid] = InterfaceInstance(
            id=iid, name=iid, type_id=tid,
            endpoints=[Endpoint(unit_id="A", connector_id="A-J01"), Endpoint(unit_id=other, connector_id=f"{other}-J01")],
        )  # fmt: skip
    return p


def hand_harness(p, box_a, box_b, *pairs, name):
    """A harness drawn by hand: a cable plug on each device connector and one wire per pair."""
    scratch = History(p)
    ops, hid = plan_new_harness(p, name)
    scratch.execute("harness", ops)
    cable = {}
    for box in (box_a, box_b):
        ops, cid = plan_add_connector(p, hid, mates_with=box)
        scratch.execute("connector", ops)
        cable[box] = cid
    for a, b in pairs:
        scratch.execute("wire", plan_add_wire(p, hid, cable[box_a], a, cable[box_b], b))
    return hid


def codes_of(issues):
    return sorted({i.code for i in issues})


def test_generate_reports_a_second_plug_on_one_connector_and_builds_the_same():
    for mode in ("per_connector_pair", "per_unit_pair", "per_zone_pair"):
        p = shared_project(mode)
        plan = plan_generation(p)
        found = [f for f in plan.report.findings if f.code == "box_connector_shared"]
        assert len(found) == 1 and found[0].severity == "warning" and found[0].object_id == "A-J01"
        assert "A-J01" in found[0].message and "one plug" in found[0].message
        assert len(plan.harnesses) == 2  # what is built is not changed, only reported


def test_one_plug_per_connector_makes_no_finding():
    p = shared_project()
    del p.interfaces["IF-2"]
    assert not [f for f in plan_generation(p).report.findings if f.code == "box_connector_shared"]


def test_integrity_warns_when_two_cable_connectors_mate_one_device_connector():
    p = pinout_project()
    assert "box_connector_mated_twice" not in codes_of(check_integrity(p))
    one = hand_harness(p, "OBC-J01", "RW1-J02", ("1", "3"), name="one")
    two = hand_harness(p, "OBC-J01", "PCDU-J03", ("1", "1"), name="two")
    found = [i for i in check_integrity(p) if i.code == "box_connector_mated_twice"]
    assert len(found) == 1 and found[0].severity == "warning" and found[0].object_id == "OBC-J01"
    plugs = [
        c.id for h in (one, two) for c in p.harnesses[h].connectors if c.mates_with == "OBC-J01"
    ]
    assert all(c in found[0].message for c in plugs) and "OBC-J01" in found[0].message
    assert "unit" not in found[0].message.lower()
    wired = [i for i in check_integrity(p) if i.code == "box_pin_wired_twice"]
    assert len(wired) == 1 and "Pin 1 of OBC-J01" in wired[0].message
    assert [i for i in check_integrity(p) if i.severity == "error"] == []  # still loads and saves


def test_two_plugs_on_one_connector_without_a_shared_pin_say_only_the_first():
    p = pinout_project()
    hand_harness(p, "OBC-J01", "RW1-J02", ("1", "3"), name="one")
    hand_harness(p, "OBC-J01", "PCDU-J03", ("2", "1"), name="two")
    assert codes_of(check_integrity(p)).count("box_connector_mated_twice") == 1
    assert "box_pin_wired_twice" not in codes_of(check_integrity(p))


def test_add_link_refuses_a_connector_that_has_a_plug_already():
    p = pinout_project()
    hand_harness(p, "OBC-J01", "RW1-J02", ("1", "3"), name="one")
    with pytest.raises(EditError) as err:
        plan_add_link(p, "OBC-J01", "RW1-J02")
    assert "OBC-J01" in str(err.value) and "one plug" in str(err.value)


def test_link_deleted_and_made_again_cannot_get_a_second_harness():
    p = pinout_project()
    ops, lid = plan_add_link(p, "OBC-J01", "RW1-J02")
    apply_ops(p, ops)
    ops, hid = plan_create_harness(p, lid)
    apply_ops(p, ops)
    apply_ops(p, plan_delete_link(p, lid))
    with pytest.raises(EditError, match="cable plug on it already"):
        plan_add_link(p, "OBC-J01", "RW1-J02")


def test_create_harness_refuses_a_connector_another_harness_plugs_into():
    p = pinout_project()
    ops, lid = plan_add_link(p, "OBC-J01", "RW1-J02")
    apply_ops(p, ops)
    hand_harness(p, "OBC-J01", "PCDU-J03", ("1", "1"), name="other")
    with pytest.raises(EditError, match="OBC-J01 has a cable plug on it already"):
        plan_create_harness(p, lid)


def test_a_pin_that_an_interface_uses_is_refused_and_not_proposed():
    p = pinout_project()
    c = p.connectors["OBC-J01"]
    pins = [evolve(x, interface_id="IF-TM-RW1") if x.id in ("1", "2") else x for x in c.pins]
    p.connectors["OBC-J01"] = evolve(c, pins=pins)
    with pytest.raises(EditError, match="Pin 1 of OBC-J01 is used by interface IF-TM-RW1"):
        plan_add_link(p, "OBC-J01", "RW1-J02", [("1", "3")])
    r = propose_pairs(p, "OBC-J01", "RW1-J02")
    assert [x.a_pin for x in r.pairs] == ["3", "4"]
    assert any("Pins 1, 2 of OBC-J01" in n for n in r.notes)
    ops, lid = plan_add_link(p, "OBC-J01", "RW1-J02")  # the default pairing skips them
    apply_ops(p, ops)
    assert [x.a_pin for x in p.links[lid].pairs] == ["3", "4"]


# ---- C-1, A-15: a harness made from a link is checked against the link -------------------------


def link_harness_project():
    p = pinout_project()
    ops, lid = plan_add_link(p, "OBC-J01", "RW1-J02")
    apply_ops(p, ops)
    ops, hid = plan_create_harness(p, lid)
    apply_ops(p, ops)
    return p, lid, hid


def change_wire(p, hid, wire_id, **fields):
    h = p.harnesses[hid]
    p.harnesses[hid] = evolve(
        h, wires=[evolve(w, **fields) if w.id == wire_id else w for w in h.wires]
    )


def test_an_untouched_link_harness_matches_its_link():
    p, lid, hid = link_harness_project()
    assert link_issues(p) == []
    assert not [i for i in verify_project(p).issues if i.code == "link_wire_mismatch"]


def test_a_wire_moved_to_another_pin_is_a_link_error_everywhere():
    p, lid, hid = link_harness_project()
    change_wire(p, hid, f"{hid}-001", to_pin="5")
    found = [i for i in verify_project(p).errors if i.code == "link_wire_mismatch"]
    assert len(found) == 2 and all(i.object_id == lid for i in found)
    text = " ".join(i.message for i in found)
    assert "pin 1 of OBC-J01" in text and "pin 5 of RW1-J02" in text and f"link {lid}" in text
    assert "unit" not in text.lower()
    out = verify_outputs(p, build_outputs(p, drawings=False).files)
    assert "link_wire_mismatch" in codes_of(out.errors)


def test_a_wire_with_another_signal_is_a_link_error():
    p, lid, hid = link_harness_project()
    change_wire(p, hid, f"{hid}-002", signal="GND")
    found = link_issues(p)
    assert len(found) == 1 and "carries GND" in found[0].message


def test_a_missing_or_extra_wire_is_a_link_error():
    p, lid, hid = link_harness_project()
    h = p.harnesses[hid]
    p.harnesses[hid] = evolve(h, wires=h.wires[1:])
    assert (
        len(link_issues(p)) == 1 and "has no wire between those pins" in link_issues(p)[0].message
    )
    p, lid, hid = link_harness_project()
    h = p.harnesses[hid]
    p.harnesses[hid] = evolve(h, wires=[*h.wires, evolve(h.wires[0], id=f"{hid}-099", to_pin="5")])
    assert any("does not pair" in i.message for i in link_issues(p))


def test_a_link_pairing_changed_after_the_harness_was_made_is_caught():
    p, lid, hid = link_harness_project()
    apply_ops(p, plan_set_pairs(p, lid, [("1", "4"), ("2", "3"), ("3", "2"), ("4", "1")]))
    assert link_issues(p)


def test_a_link_with_no_harness_and_a_harness_with_no_link_are_not_checked():
    p = pinout_project()
    ops, lid = plan_add_link(p, "OBC-J01", "RW1-J02")
    apply_ops(p, ops)
    assert link_issues(p) == []
    hand_harness(p, "OBC-J02", "PCDU-J02", ("1", "1"), name="free")
    assert link_issues(p) == []


def test_a_link_naming_a_harness_with_no_plug_on_an_end_is_an_error_and_a_warning():
    p, lid, hid = link_harness_project()
    h = p.harnesses[hid]
    p.harnesses[hid] = evolve(h, connectors=[evolve(h.connectors[0], mates_with=None), h.connectors[1]], wires=[])  # fmt: skip
    issue = [i for i in check_integrity(p) if i.code == "link_harness_not_mated"]
    assert len(issue) == 1 and issue[0].severity == "warning" and "plugs into" in issue[0].message
    assert link_issues(p) and link_issues(p)[0].severity == "error"


def test_two_links_that_claim_one_harness_are_a_warning():
    p, lid, hid = link_harness_project()
    apply_ops(p, plan_set_pairs(p, lid, [("1", "3"), ("2", "4"), ("3", "1"), ("4", "2")]))
    ops, other = plan_add_link(p, "OBC-J02", "PCDU-J02")
    apply_ops(p, ops)
    p.links[other] = evolve(p.links[other], harness_id=hid)
    found = [i for i in check_integrity(p) if i.code == "link_harness_shared"]
    assert len(found) == 1 and found[0].severity == "warning"
    assert lid in found[0].message and other in found[0].message


def test_the_command_line_fails_with_a_plain_message(tmp_path, capsys):
    p, lid, hid = link_harness_project()
    change_wire(p, hid, f"{hid}-001", to_pin="5")
    folder = tmp_path / "q"
    save_project(p, folder)
    for cmd in ("validate", "check"):
        assert main([cmd, str(folder)]) == 1
        assert "link_wire_mismatch" in capsys.readouterr().out
    assert main(["verify", str(folder)]) == 1
    assert "link_wire_mismatch" in capsys.readouterr().out
    assert main(["export", str(folder)]) == 1
    assert "link_wire_mismatch" in capsys.readouterr().out
