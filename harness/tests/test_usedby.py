# mypy: disable-error-code="no-untyped-def,no-untyped-call"
"""SH-8: where a unit, interface, part or interface type is used (the inspector's "Used in")."""

from harness_design_studio.core import describe
from harness_design_studio.core.model import evolve
from harness_design_studio.core.usedby import Use, used_by
from tests.test_change_control import full, releasable


def ids(uses: list[Use], kind: str) -> list[str]:
    return [u.id for u in uses if u.kind == kind]


def test_an_interface_is_used_by_its_units_its_harness_and_its_wires() -> None:
    p = full()
    h = p.harnesses[releasable(p)]
    iid = h.interfaces[0]
    uses = used_by(p, "interface", iid)
    assert set(ids(uses, "unit")) == {e.unit_id for e in p.interfaces[iid].endpoints}
    assert ids(uses, "harness") == [h.id]
    assert set(ids(uses, "wire")) == {w.id for w in h.wires if w.interface_id == iid}
    assert all(u.via for u in uses)  # each use says in what way


def test_a_unit_is_used_by_its_interfaces_and_the_harnesses_that_carry_them() -> None:
    p = full()
    uid = next(iter(p.units))
    mine = {i.id for i in p.interfaces.values() if any(e.unit_id == uid for e in i.endpoints)}
    uses = used_by(p, "unit", uid)
    assert set(ids(uses, "interface")) == mine
    assert set(ids(uses, "harness")) == {
        h.id
        for h in p.harnesses.values()
        if mine & ({w.interface_id for w in h.wires} | set(h.interfaces))
    }


def test_an_interface_type_is_used_by_the_interfaces_of_that_type() -> None:
    p = full()
    tid = next(iter({i.type_id for i in p.interfaces.values()}))
    uses = used_by(p, "interface_type", tid)
    assert set(ids(uses, "interface")) == {i.id for i in p.interfaces.values() if i.type_id == tid}
    assert ids(used_by(p, "interface_type", "no-such-type"), "interface") == []


def test_a_part_is_used_by_connectors_on_units_and_in_harnesses_and_by_wires() -> None:
    p = full()
    h = p.harnesses[releasable(p)]
    cable = h.connectors[0]
    uses = used_by(p, "part", cable.part_id)
    assert h.id in ids(uses, "harness")
    boxes = [c for c in p.connectors.values() if c.part_id == cable.part_id and c.unit_id]
    assert set(ids(uses, "unit")) >= {c.unit_id for c in boxes if c.unit_id}
    wire_part = next(w.part_id for w in h.wires if w.part_id)
    assert {w.id for w in h.wires if w.part_id == wire_part} <= set(
        ids(used_by(p, "part", wire_part), "wire")
    )


def test_a_part_nobody_uses_has_no_uses() -> None:
    p = full()
    free = next(pid for pid in p.parts if not used_by(p, "part", pid))
    assert used_by(p, "part", free) == []


def test_unknown_kinds_and_ids_give_nothing() -> None:
    p = full()
    assert used_by(p, "config", "derating") == []
    assert used_by(p, "unit", "nope") == []


def test_the_order_is_stable_and_natural() -> None:
    p = full()
    a = used_by(p, "interface_type", next(iter({i.type_id for i in p.interfaces.values()})))
    assert a == used_by(p, "interface_type", next(iter({i.type_id for i in p.interfaces.values()})))
    order = [u.kind for u in a]
    assert order == sorted(order, key=["interface", "harness", "wire", "unit"].index)


def test_harness_state_has_a_word_for_each_stage_of_change_control() -> None:
    p = full()
    h = next(iter(p.harnesses.values()))
    assert describe.harness_state(h) == "draft"
    assert describe.harness_state(evolve(h, status="in_review")) == "in-review"
    assert describe.harness_state(evolve(h, status="released")) == "released"
    assert describe.harness_state(evolve(h, status="draft", revision="B")) == "revised"
