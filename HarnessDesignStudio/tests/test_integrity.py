"""REQ-INTEGRITY-01: every referential rule has a positive and a negative test."""

from collections.abc import Callable

import pytest

from harness_design_studio.core.integrity import check_integrity
from harness_design_studio.core.model import (
    Accessory,
    BranchPoint,
    Connector,
    Endpoint,
    Harness,
    Link,
    Part,
    Pin,
    PinPair,
    Project,
    Segment,
    ShieldGroup,
    Splice,
    Unit,
    evolve,
)
from harness_design_studio.core.samples import mini3


def codes(p: Project) -> set[str]:
    return {i.code for i in check_integrity(p)}


def test_sample_is_consistent() -> None:
    assert check_integrity(mini3()) == []


def _w1(p: Project) -> Harness:
    return p.harnesses["W001"]


def case_unknown_interface_type(p: Project) -> None:
    p.interfaces["IF-TM-RW1"] = evolve(p.interfaces["IF-TM-RW1"], type_id="nope")


def case_unknown_unit(p: Project) -> None:
    i = p.interfaces["IF-TM-RW1"]
    p.interfaces[i.id] = evolve(i, endpoints=[Endpoint(unit_id="GHOST"), i.endpoints[1]])


def case_too_few_endpoints(p: Project) -> None:
    i = p.interfaces["IF-TM-RW1"]
    p.interfaces[i.id] = evolve(i, endpoints=[i.endpoints[0]])


def case_bad_endpoint_connector(p: Project) -> None:
    i = p.interfaces["IF-TM-RW1"]
    p.interfaces[i.id] = evolve(
        i, endpoints=[Endpoint(unit_id="OBC", connector_id="RW1-J02"), i.endpoints[1]]
    )


def case_unknown_part(p: Project) -> None:
    p.connectors["OBC-J01"] = evolve(p.connectors["OBC-J01"], part_id="NOPE")


def case_wrong_part_category(p: Project) -> None:
    p.connectors["OBC-J01"] = evolve(p.connectors["OBC-J01"], part_id="EX-WIRE-SINGLE")


def case_too_many_pins(p: Project) -> None:
    p.parts["EX-MICROD-9-F"] = evolve(p.parts["EX-MICROD-9-F"], pin_count=2)


def case_box_unknown_unit(p: Project) -> None:
    p.connectors["OBC-J01"] = evolve(p.connectors["OBC-J01"], unit_id="GHOST")


def case_cable_has_unit(p: Project) -> None:
    h = _w1(p)
    c = evolve(h.connectors[0], unit_id="OBC")
    p.harnesses["W001"] = evolve(h, connectors=[c, h.connectors[1]])


def case_cable_outside_harness(p: Project) -> None:
    p.connectors["X"] = Connector(id="X", name="x", role="cable", part_id="EX-DSUB-9-F")


def case_box_in_harness(p: Project) -> None:
    h = _w1(p)
    c = Connector(id="BOX-IN-H", name="x", role="box", part_id="EX-DSUB-9-F", unit_id="OBC")
    p.harnesses["W001"] = evolve(h, connectors=[*h.connectors, c])


def case_duplicate_pin(p: Project) -> None:
    c = p.connectors["OBC-J01"]
    p.connectors[c.id] = evolve(c, pins=[Pin(id="1"), Pin(id="1")])


def case_dangling_wire_connector(p: Project) -> None:
    h = _w1(p)
    w = evolve(h.wires[0], to_connector="GHOST")
    p.harnesses["W001"] = evolve(h, wires=[w, h.wires[1]])


def case_dangling_wire_pin(p: Project) -> None:
    h = _w1(p)
    w = evolve(h.wires[0], to_pin="99")
    p.harnesses["W001"] = evolve(h, wires=[w, h.wires[1]])


def case_wire_to_itself(p: Project) -> None:
    h = _w1(p)
    w = evolve(h.wires[0], to_connector=h.wires[0].from_connector, to_pin=h.wires[0].from_pin)
    p.harnesses["W001"] = evolve(h, wires=[w, h.wires[1]])


def case_wire_part(p: Project) -> None:
    h = _w1(p)
    w = evolve(h.wires[0], part_id="EX-DSUB-9-F")
    p.harnesses["W001"] = evolve(h, wires=[w, h.wires[1]])


def case_wire_interface(p: Project) -> None:
    h = _w1(p)
    w = evolve(h.wires[0], interface_id="GHOST")
    p.harnesses["W001"] = evolve(h, wires=[w, h.wires[1]])


def case_duplicate_wire_id(p: Project) -> None:
    h = _w1(p)

    def rename(cid: str) -> str:
        return cid.replace("W001", "W002")

    p.harnesses["W002"] = evolve(
        h,
        id="W002",
        connectors=[evolve(c, id=rename(c.id)) for c in h.connectors],
        wires=[
            evolve(w, from_connector=rename(w.from_connector), to_connector=rename(w.to_connector))
            for w in h.wires
        ],
    )


def case_shield_dangling(p: Project) -> None:
    h = _w1(p)
    p.harnesses["W001"] = evolve(
        h, shields=[ShieldGroup(id="S1", kind="overall_shield", wire_ids=["GHOST"])]
    )


def case_splice_dangling(p: Project) -> None:
    h = _w1(p)
    p.harnesses["W001"] = evolve(h, splices=[Splice(id="SP1", name="s", wire_ids=["GHOST"])])


def case_segment_dangling(p: Project) -> None:
    h = _w1(p)
    p.harnesses["W001"] = evolve(
        h, segments=[Segment(id="S1", from_node="W001-P1", to_node="GHOST")]
    )


def case_accessory_dangling(p: Project) -> None:
    h = _w1(p)
    p.harnesses["W001"] = evolve(
        h, accessories=[Accessory(id="ACC-1", kind="sleeving", target="GHOST")]
    )


def case_contact_unknown(p: Project) -> None:
    box = next(c for c in p.connectors.values() if c.pins)
    pins = [evolve(box.pins[0], contact_part="NO-SUCH-CONTACT"), *box.pins[1:]]
    p.connectors[box.id] = evolve(box, pins=pins)


def case_contact_wrong_category(p: Project) -> None:
    box = next(c for c in p.connectors.values() if c.pins)
    pins = [evolve(box.pins[0], contact_part=box.part_id), *box.pins[1:]]  # a connector part
    p.connectors[box.id] = evolve(box, pins=pins)


def case_accessory_unknown_part(p: Project) -> None:
    h = _w1(p)
    p.harnesses["W001"] = evolve(
        h, accessories=[Accessory(id="ACC-1", kind="sleeving", part_id="NO-SUCH-PART")]
    )


def case_duplicate_accessory(p: Project) -> None:
    h = _w1(p)
    p.harnesses["W001"] = evolve(
        h,
        accessories=[Accessory(id="ACC-1", kind="label"), Accessory(id="ACC-1", kind="other")],
    )


def case_duplicate_branch(p: Project) -> None:
    h = _w1(p)
    p.harnesses["W001"] = evolve(
        h, branch_points=[BranchPoint(id="B1", name="b"), BranchPoint(id="B1", name="c")]
    )


def case_casefold_unit(p: Project) -> None:
    p.units["obc"] = Unit(id="obc", name="x", subsystem="s")


def case_duplicate_connector_across(p: Project) -> None:
    h = _w1(p)
    c = Connector(id="OBC-J01", name="x", role="cable", part_id="EX-DSUB-9-F")
    p.harnesses["W001"] = evolve(h, connectors=[*h.connectors, c])


def case_duplicate_signal(p: Project) -> None:
    t = p.interface_types["rs422"]
    p.interface_types["rs422"] = evolve(t, signals=[t.signals[0], t.signals[0]])


# REQ-DRC-05: the integrity codes of links (dangling_link, link_pin_missing, link_pin_reused,
# link_same_device) each have a negative case below.
def _link(p: Project, **kw: object) -> None:
    fields: dict[str, object] = {
        "id": "L1",
        "a_connector": "OBC-J01",
        "b_connector": "RW1-J02",
        "pairs": [PinPair(a_pin="1", b_pin="1")],
    }
    p.links["L1"] = Link(**{**fields, **kw})  # type: ignore[arg-type]


def case_dangling_link(p: Project) -> None:
    _link(p, b_connector="NOPE-J01")


def case_link_pin_missing(p: Project) -> None:
    _link(p, pairs=[PinPair(a_pin="1", b_pin="99")])


def case_link_pin_reused(p: Project) -> None:
    _link(p, pairs=[PinPair(a_pin="1", b_pin="1"), PinPair(a_pin="1", b_pin="2")])


def case_link_pin_reused_across_links(p: Project) -> None:
    _link(p)
    p.links["L2"] = Link(
        id="L2",
        a_connector="OBC-J01",
        b_connector="PCDU-J03",
        pairs=[PinPair(a_pin="1", b_pin="1")],
    )


def case_link_same_device(p: Project) -> None:
    _link(p, b_connector="OBC-J02")


def case_link_harness_missing(p: Project) -> None:
    _link(p, harness_id="W404")


NEGATIVE: list[tuple[str, Callable[[Project], None], str]] = [
    ("dangling_link", case_dangling_link, "dangling_link"),
    ("link_pin_missing", case_link_pin_missing, "link_pin_missing"),
    ("link_pin_reused", case_link_pin_reused, "link_pin_reused"),
    ("link_pin_reused_across", case_link_pin_reused_across_links, "link_pin_reused"),
    ("link_same_device", case_link_same_device, "link_same_device"),
    ("link_harness_missing", case_link_harness_missing, "unknown_harness"),
    ("unknown_interface_type", case_unknown_interface_type, "unknown_interface_type"),
    ("unknown_unit", case_unknown_unit, "unknown_unit"),
    ("too_few_endpoints", case_too_few_endpoints, "too_few_endpoints"),
    ("bad_endpoint_connector", case_bad_endpoint_connector, "bad_endpoint_connector"),
    ("unknown_part", case_unknown_part, "unknown_part"),
    ("wrong_part_category", case_wrong_part_category, "wrong_part_category"),
    ("too_many_pins", case_too_many_pins, "too_many_pins"),
    ("box_unknown_unit", case_box_unknown_unit, "unknown_unit"),
    ("cable_has_unit", case_cable_has_unit, "cable_connector_has_unit"),
    ("cable_outside_harness", case_cable_outside_harness, "cable_connector_outside_harness"),
    ("box_in_harness", case_box_in_harness, "box_in_harness"),
    ("duplicate_pin", case_duplicate_pin, "duplicate_pin"),
    ("dangling_wire_connector", case_dangling_wire_connector, "dangling_wire"),
    ("dangling_wire_pin", case_dangling_wire_pin, "dangling_wire"),
    ("wire_to_itself", case_wire_to_itself, "wire_to_itself"),
    ("wire_part", case_wire_part, "unknown_part"),
    ("wire_interface", case_wire_interface, "unknown_interface"),
    ("duplicate_wire_id", case_duplicate_wire_id, "duplicate_id"),
    ("shield_dangling", case_shield_dangling, "dangling_wire"),
    ("splice_dangling", case_splice_dangling, "dangling_wire"),
    ("segment_dangling", case_segment_dangling, "dangling_segment"),
    ("accessory_dangling", case_accessory_dangling, "dangling_accessory"),
    ("contact_unknown", case_contact_unknown, "unknown_part"),
    ("contact_wrong_category", case_contact_wrong_category, "wrong_part_category"),
    ("accessory_unknown_part", case_accessory_unknown_part, "unknown_part"),
    ("accessory_duplicate", case_duplicate_accessory, "duplicate_id"),
    ("duplicate_branch", case_duplicate_branch, "duplicate_id"),
    ("casefold_unit", case_casefold_unit, "duplicate_id"),
    ("duplicate_connector_across", case_duplicate_connector_across, "duplicate_id"),
    ("duplicate_signal", case_duplicate_signal, "duplicate_signal"),
]


@pytest.mark.parametrize(("name", "mutate", "code"), NEGATIVE, ids=[n[0] for n in NEGATIVE])
def test_rule_fires(name: str, mutate: Callable[[Project], None], code: str) -> None:
    p = mini3()
    mutate(p)
    assert code in codes(p), name


def test_all_rule_codes_have_negative_test() -> None:
    """Every code that integrity.py can report appears in NEGATIVE (or, for the stale-data
    warnings, in another test file); a new code without a test fails here."""
    import re
    from pathlib import Path

    src = (Path(__file__).parents[1] / "src/harness_design_studio/core/integrity.py").read_text(
        encoding="utf-8"
    )
    reported = set(
        re.findall(
            r'(?:_err\(|_orphan\([^,"]+, |Issue\(\s*"(?:warning|error)",\s*)"([a-z]+(?:_[a-z]+)+)"',
            src,
        )
    )
    assert len(reported) >= 18, reported  # the pattern still finds the codes
    tested = {c for _, _, c in NEGATIVE}
    others = "".join(
        p.read_text(encoding="utf-8")
        for p in Path(__file__).parent.glob("test_*.py")
        if p.name != "test_integrity.py"
    )
    missing = sorted(c for c in reported - tested if f'"{c}"' not in others)
    assert not missing, missing


def test_a_new_part_is_pending_until_someone_approves_it() -> None:
    assert Part(id="X", category="wire").approval == "pending"
