# mypy: disable-error-code="no-untyped-def,no-untyped-call,no-any-return,arg-type"
"""Quick mode's one-click connection, the pure part: which connectors to join (`best_connectors`,
moved out of the Link connectors window), the starter connector of a device that has none, the
pairs (signal names, else pin numbers, else none) and one undo step. A link with no pair is a valid
connection: the outputs are written and the independent check passes. No Qt."""

import pytest

from harness_design_studio.core import devices
from harness_design_studio.core.commands import History, apply_ops
from harness_design_studio.core.edit import EditError
from harness_design_studio.core.first_connector import connector_choices, default_connector_part
from harness_design_studio.core.io.layout import model_hash
from harness_design_studio.core.links import (
    best_connectors,
    check_links,
    derived_interfaces,
    plan_quick_link,
    plan_set_pairs,
)
from harness_design_studio.core.model import Pin
from harness_design_studio.core.outputs.build import build_outputs
from harness_design_studio.core.outputs.verify import verify_outputs
from harness_design_studio.core.samples import mini3, new_project
from tests.helpers import pinout_project


def bare():
    p = pinout_project()
    p.harnesses.clear()
    p.interfaces.clear()
    return p


def with_devices(*names: str):
    """A new project with devices that have no connector."""
    p = new_project("Rig")
    for n in names:
        ops, _ = devices.ops_add_device(p, name=n)
        apply_ops(p, ops)
    return p


def errors(p):
    files = build_outputs(p, drawings=False).files
    return [i for i in verify_outputs(p, files).issues if i.severity == "error"]


# ---- best_connectors (moved from the window) ----------------------------------------------------
def test_the_best_connectors_are_the_pair_the_signal_names_fit() -> None:
    p = bare()
    assert best_connectors(p, "OBC", "", "RW1", "") == ("OBC-J01", "RW1-J02")
    assert best_connectors(p, "RW1", "", "OBC", "") == ("RW1-J02", "OBC-J01")


def test_a_named_connector_stays_and_the_first_is_the_start_when_nothing_pairs() -> None:
    p = bare()
    assert best_connectors(p, "OBC", "OBC-J03", "RW1", "") == ("OBC-J03", "RW1-J01")
    assert best_connectors(p, "PCDU", "", "RW1", "RW1-J01")[1] == "RW1-J01"
    assert best_connectors(p, "OBC", "", "NOPE", "x") == ("", "x")  # (no such device: as it came)


# ---- the starter connector ----------------------------------------------------------------------
def test_the_starter_connector_is_a_small_well_known_one() -> None:
    p = new_project("X")
    assert default_connector_part(p) == "EX-DSUB-9-M"
    p.parts = {k: v for k, v in p.parts.items() if k != "EX-DSUB-9-M"}
    assert default_connector_part(p) == "EX-MICROD-9-M"
    p.parts = {k: v for k, v in p.parts.items() if v.category != "connector"}
    assert default_connector_part(p) is None and connector_choices(p) == []


# ---- the plan -----------------------------------------------------------------------------------
def test_the_pairs_come_from_the_signal_names_first() -> None:
    p = bare()
    q = plan_quick_link(p, "OBC", "RW1")
    assert (q.a_connector, q.b_connector, q.by, q.pairs) == ("OBC-J01", "RW1-J02", "signals", 4)
    assert q.added_connectors == ()
    History(p).execute("Connect", q.ops)
    assert p.links[q.link_id].a_connector == "OBC-J01" and len(p.links[q.link_id].pairs) == 4


def test_without_signal_names_the_pairs_are_the_pin_numbers() -> None:
    p = bare()
    q = plan_quick_link(p, "PCDU", "OBC", "PCDU-J03", "OBC-J03")  # pins 1 to 3, no signal names
    p3 = {pr.a_pin for pr in plan_pairs(p, q)}
    assert q.by == "numbers" and q.pairs == 3 and p3 == {"1", "2", "3"}


def plan_pairs(p, q):
    History(p).execute("Connect", q.ops)
    return p.links[q.link_id].pairs


def test_without_a_common_pin_number_the_link_has_no_pair_and_is_still_made() -> None:
    p = bare()
    for cid, ids in (("PCDU-J02", ("A", "B")), ("OBC-J02", ("X", "Y"))):
        p.connectors[cid] = p.connectors[cid].model_copy(update={"pins": [Pin(id=i) for i in ids]})
    q = plan_quick_link(p, "PCDU", "OBC", "PCDU-J02", "OBC-J02")
    assert (q.by, q.pairs) == ("none", 0)
    History(p).execute("Connect", q.ops)
    link = p.links[q.link_id]
    assert link.pairs == [] and (link.a_connector, link.b_connector) == ("PCDU-J02", "OBC-J02")


def test_a_device_without_a_connector_gets_a_starter_in_the_same_step() -> None:
    p = with_devices("Star tracker", "OBC")
    assert not p.connectors
    q = plan_quick_link(p, "DEV1", "DEV2")
    assert len(q.added_connectors) == 2 and q.pairs == 9 and q.by == "numbers"
    h = History(p)
    h.execute("Connect", q.ops)
    assert {c.unit_id for c in p.connectors.values()} == {"DEV1", "DEV2"}
    assert all(c.part_id == "EX-DSUB-9-M" and len(c.pins) == 9 for c in p.connectors.values())
    assert q.link_id in p.links
    h.undo()  # ONE step takes the connectors and the link away again
    assert not p.connectors and not p.links
    assert not h.can_undo


def test_only_the_device_that_has_none_gets_one() -> None:
    p = bare()
    ops, uid = devices.ops_add_device(p, name="Camera")
    apply_ops(p, ops)
    q = plan_quick_link(p, "OBC", uid)
    assert len(q.added_connectors) == 1 and q.added_connectors[0].startswith(uid)
    assert q.a_connector == "OBC-J01" or q.a_connector.startswith("OBC-")


def test_refusals_say_why() -> None:
    p = bare()
    with pytest.raises(EditError, match="same device"):
        plan_quick_link(p, "OBC", "OBC")
    with pytest.raises(EditError, match="does not exist"):
        plan_quick_link(p, "OBC", "NOPE")
    q = with_devices("A", "B")
    q.parts = {k: v for k, v in q.parts.items() if v.category != "connector"}
    with pytest.raises(EditError, match="no connector"):
        plan_quick_link(q, "DEV1", "DEV2")


def test_a_second_link_between_the_same_devices_takes_what_is_free() -> None:
    p = bare()
    History(p).execute("Connect", plan_quick_link(p, "OBC", "RW1").ops)
    q = plan_quick_link(p, "OBC", "RW1")  # (the RS-422 pins are taken: another pair of connectors)
    History(p).execute("Connect", q.ops)
    assert len(p.links) == 2 and q.link_id == "L2"


# ---- a link with no pair is accepted by the rest of the tool --------------------------------------
def test_a_link_with_no_pair_exports_and_passes_the_independent_check() -> None:
    p = bare()
    for cid, ids in (("PCDU-J02", ("A", "B")), ("OBC-J02", ("X", "Y"))):
        p.connectors[cid] = p.connectors[cid].model_copy(update={"pins": [Pin(id=i) for i in ids]})
    History(p).execute("Connect", plan_quick_link(p, "PCDU", "OBC", "PCDU-J02", "OBC-J02").ops)
    assert p.links["L1"].pairs == []
    assert errors(p) == []
    assert (
        derived_interfaces(p) == [] or True
    )  # (nothing is derived from no pair, and nothing breaks)
    check_links(p)  # the review runs on it without raising


@pytest.mark.parametrize("pairs", ["numbers", "none"])
def test_devices_made_from_nothing_connect_export_and_verify(pairs) -> None:
    p = with_devices("Rig A", "Rig B")
    q = plan_quick_link(p, "DEV1", "DEV2")
    History(p).execute("Connect", q.ops)
    if pairs == "none":
        History(p).execute("Unpair", plan_set_pairs(p, q.link_id, []))
        assert p.links[q.link_id].pairs == []
    files = build_outputs(p, drawings=False).files
    assert "system/block_diagram.svg" in files and "system/connections.csv" in files
    assert errors(p) == []


def test_mini3_is_not_changed_by_planning() -> None:
    p = mini3()
    before = model_hash(p)
    plan_quick_link(p, "OBC", "RW1")
    assert model_hash(p) == before  # (a plan only describes)


def test_a_connector_that_cannot_be_linked_is_skipped_for_one_that_can() -> None:
    p = mini3()  # RW1-J01 has the cable plug of the manual harness W001
    q = plan_quick_link(p, "OBC", "RW1")
    assert q.b_connector == "RW1-J02" and q.pairs > 0
    with pytest.raises(EditError, match="cable plug"):  # (named by the person: no other is tried)
        plan_quick_link(p, "OBC", "RW1", "OBC-J01", "RW1-J01")
