# mypy: disable-error-code="no-untyped-def,no-untyped-call,no-any-return"
"""REQ-DRC-05. Release 1.9 (W3): the direction a person set on a pin (`Pin.direction`) decides the
review of a link and the pairing proposal before the interface types and before any name does.
No Qt."""

from harness_design_studio.core.commands import apply_ops
from harness_design_studio.core.edit import clone_with
from harness_design_studio.core.links import (
    check_link,
    plan_add_link,
    plan_create_harness,
    propose_pairs,
)
from harness_design_studio.core.model import Pin
from tests.helpers import pinout_project


def codes(findings):
    return sorted({f.code for f in findings})


def set_pins(p, cid, *pins):
    p.connectors[cid] = p.connectors[cid].model_copy(update={"pins": list(pins)})


def pairs_of(r):
    return [(x.a_pin, x.b_pin) for x in r.pairs]


# ---- the link checks ----------------------------------------------------------------------------


def linked_with_directions(a_dir, b_dir, signal="SIG+", other=None):
    """Two connectors with one pin each named `signal` (and `other` on the far side), joined."""
    p = pinout_project()
    set_pins(p, "OBC-J03", Pin(id="1", signal=signal, direction=a_dir))
    set_pins(p, "PCDU-J03", Pin(id="1", signal=other or signal, direction=b_dir))
    return p


def test_two_outputs_set_on_the_pins_are_a_conflict_even_for_a_signal_the_types_exempt():
    p = linked_with_directions("", "")  # analog SIG+ at both ends: no direction error without them
    ops, lid = plan_add_link(p, "OBC-J03", "PCDU-J03")
    apply_ops(p, ops)
    assert "link_direction_conflict" not in codes(check_link(p, p.links[lid]))
    q = linked_with_directions("out", "out")
    ops, lid = plan_add_link(q, "OBC-J03", "PCDU-J03", [("1", "1")])
    apply_ops(q, ops)
    (f,) = [x for x in check_link(q, q.links[lid]) if x.code == "link_direction_conflict"]
    assert "both are outputs" in f.message


def test_an_output_meeting_an_input_set_by_hand_is_fine_and_so_is_bidirectional():
    for a, b in (("out", "in"), ("in", "out"), ("bidir", "out"), ("in", "bidir"), ("out", "")):
        p = linked_with_directions(a, b, signal="DATA")
        ops, lid = plan_add_link(p, "OBC-J03", "PCDU-J03", [("1", "1")])
        apply_ops(p, ops)
        assert "link_direction_conflict" not in codes(check_link(p, p.links[lid])), (a, b)


def test_a_direction_on_the_pin_beats_the_interface_type():
    p = pinout_project()  # OBC-J01 pin 1 is TX+ (an output in RS-422), RW1-J02 pin 3 is RX+ (input)
    ops, lid = plan_add_link(p, "OBC-J01", "RW1-J02", [("1", "3")])
    apply_ops(p, ops)
    assert "link_direction_conflict" not in codes(check_link(p, p.links[lid]))
    c = p.connectors["RW1-J02"]  # the person says this pin is an output after all
    pins = [x.model_copy(update={"direction": "out"}) if x.id == "3" else x for x in c.pins]
    p.connectors["RW1-J02"] = c.model_copy(update={"pins": pins})
    assert "link_direction_conflict" in codes(check_link(p, p.links[lid]))


def test_the_proposal_pairs_equal_transmit_names_when_both_directions_say_it_fits():
    p = linked_with_directions("", "", signal="UART_TX")
    assert pairs_of(propose_pairs(p, "OBC-J03", "PCDU-J03")) == []  # the names look TX to TX
    q = linked_with_directions("out", "in", signal="UART_TX")  # a vendor names every pin its way
    assert pairs_of(propose_pairs(q, "OBC-J03", "PCDU-J03")) == [("1", "1")]
    ops, lid = plan_add_link(q, "OBC-J03", "PCDU-J03")
    apply_ops(q, ops)
    assert "link_signal_mismatch" not in codes(check_link(q, q.links[lid]))
    one = linked_with_directions("out", "", signal="UART_TX")  # only one end says: the name decides
    assert pairs_of(propose_pairs(one, "OBC-J03", "PCDU-J03")) == []
    two = linked_with_directions("out", "", signal="UART_TX")
    ops, lid = plan_add_link(two, "OBC-J03", "PCDU-J03", [("1", "1")])
    apply_ops(two, ops)
    assert "link_signal_mismatch" in codes(check_link(two, two.links[lid]))


def test_the_proposal_does_not_pair_two_outputs_the_pins_say_are_outputs():
    p = linked_with_directions("out", "out", signal="DATA")
    r = propose_pairs(p, "OBC-J03", "PCDU-J03")
    assert pairs_of(r) == [] and any("both are outputs" in n for n in r.notes)
    q = linked_with_directions("out", "in", signal="DATA")
    assert pairs_of(propose_pairs(q, "OBC-J03", "PCDU-J03")) == [("1", "1")]


def test_a_harness_made_from_a_link_does_not_copy_the_direction_to_the_cable():
    p = linked_with_directions("out", "in", signal="DATA")
    ops, lid = plan_add_link(p, "OBC-J03", "PCDU-J03")
    apply_ops(p, ops)
    ops, hid = plan_create_harness(clone_with(p, []), lid)
    q = clone_with(p, ops)
    assert all(pin.direction == "" for c in q.harnesses[hid].connectors for pin in c.pins)
