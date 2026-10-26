# mypy: disable-error-code="no-untyped-def,no-untyped-call,no-any-return"
"""REQ-WIRE-07. Workshop feedback M3: change the kind, the wires and the shield ends of a group that a
person made (twisted pair, shielded pair, quad, coax, overall shield); a group of the interface type is
refused; Generate keeps the change; files stay byte-identical while no group is changed."""

import json

import pytest

from harness_design_studio.core.commands import History, apply_ops
from harness_design_studio.core.edit import EditError
from harness_design_studio.core.generate.engine import generate_project, plan_generation
from harness_design_studio.core.io.layout import model_hash, serialize
from harness_design_studio.core.manual_harness import plan_add_connector, plan_new_harness
from harness_design_studio.core.model import evolve
from harness_design_studio.core.samples import new_project, sat15
from harness_design_studio.core.wires import (
    SHIELD_ENDS,
    plan_add_wire,
    plan_group_wires,
    plan_regroup,
    plan_set_group_ends,
    plan_ungroup_all,
)


def mine(wires: int = 4):
    """A harness made by hand with `wires` wires, none of them in a group yet."""
    p = new_project("Scratch")
    ops, hid = plan_new_harness(p, "Sensor harness")
    apply_ops(p, ops)
    ids = []
    for _ in range(2):
        ops, cid = plan_add_connector(p, hid, part_id="EX-DSUB-9-M")
        apply_ops(p, ops)
        ids.append(cid)
    for k in range(1, wires + 1):
        apply_ops(p, plan_add_wire(p, hid, ids[0], str(k), ids[1], str(k), signal=f"S{k}"))
    return p, hid, [w.id for w in p.harnesses[hid].wires]


def group(p, hid, wire_ids, kind):
    apply_ops(p, plan_group_wires(p, wire_ids, kind))
    return p.harnesses[hid].shields[-1].id


def shield(p, hid, gid):
    return next(s for s in p.harnesses[hid].shields if s.id == gid)


def test_the_kind_of_a_group_changes_and_the_wires_stay():
    p, hid, w = mine()
    gid = group(p, hid, w[:2], "twisted_pair")
    apply_ops(p, plan_regroup(p, gid, kind="shielded_pair"))
    s = shield(p, hid, gid)
    assert (s.kind, s.wire_ids, s.manual) == ("shielded_pair", w[:2], True)


def test_a_group_can_become_a_quad_or_an_overall_shield_when_its_wires_fit():
    p, hid, w = mine()
    gid = group(p, hid, w[:2], "twisted_pair")
    with pytest.raises(EditError, match="quad is made of 4 wires, not 2"):
        plan_regroup(p, gid, kind="quad")
    apply_ops(p, plan_regroup(p, gid, kind="quad", wire_ids=w))
    assert shield(p, hid, gid).wire_ids == sorted(w) and shield(p, hid, gid).kind == "quad"
    apply_ops(p, plan_regroup(p, gid, kind="overall_shield", wire_ids=w[:3]))
    assert shield(p, hid, gid).wire_ids == sorted(w[:3])
    with pytest.raises(EditError, match="coax is made of 1 wire, not 3"):
        plan_regroup(p, gid, kind="coax")
    apply_ops(p, plan_regroup(p, gid, kind="coax", wire_ids=[w[0]]))
    assert shield(p, hid, gid).kind == "coax"


def test_the_ends_of_the_shield_are_set_alone_or_with_the_kind():
    p, hid, w = mine()
    gid = group(p, hid, w[:2], "shielded_pair")
    assert shield(p, hid, gid).end_a == "floating"  # (generation settings are a placeholder)
    apply_ops(p, plan_regroup(p, gid, end_a="backshell_360", end_b="pigtail"))
    s = shield(p, hid, gid)
    assert (s.kind, s.end_a, s.end_b) == ("shielded_pair", "backshell_360", "pigtail")
    apply_ops(p, plan_regroup(p, gid, kind="overall_shield", end_b="floating"))
    s = shield(p, hid, gid)
    assert (s.kind, s.end_a, s.end_b) == ("overall_shield", "backshell_360", "floating")
    assert SHIELD_ENDS == ("backshell_360", "pigtail", "floating")
    with pytest.raises(EditError, match="shield end B is one of"):
        plan_regroup(p, gid, end_b="welded")


def test_several_groups_get_the_same_ends_in_one_step():
    p, hid, w = mine()
    a = group(p, hid, w[:2], "shielded_pair")
    b = group(p, hid, w[2:], "shielded_pair")
    before = model_hash(p)
    hist = History(p)
    hist.execute(
        "ends", plan_set_group_ends(p, [a, b], end_a="backshell_360", end_b="backshell_360")
    )
    assert {shield(p, hid, g).end_a for g in (a, b)} == {"backshell_360"}
    hist.undo()
    assert model_hash(p) == before
    hist.redo()
    assert {shield(p, hid, g).end_b for g in (a, b)} == {"backshell_360"}
    assert plan_set_group_ends(p, [a], end_a="backshell_360") == []  # nothing new
    with pytest.raises(EditError, match="No group is selected"):
        plan_set_group_ends(p, [], end_a="pigtail")
    with pytest.raises(EditError, match="Say how the shield ends"):
        plan_set_group_ends(p, [a])
    with pytest.raises(EditError, match="does not exist"):
        plan_set_group_ends(p, ["nope"], end_a="pigtail")


def test_a_wire_of_another_group_or_another_harness_is_refused():
    p, hid, w = mine()
    a = group(p, hid, w[:2], "twisted_pair")
    group(p, hid, w[2:], "twisted_pair")
    with pytest.raises(EditError, match="already in twisted pair"):
        plan_regroup(p, a, kind="quad", wire_ids=w)
    with pytest.raises(EditError, match="is not in W001"):
        plan_regroup(p, a, wire_ids=[w[0], "W009-0001"])


def test_nothing_changes_gives_no_ops_and_one_kind_change_is_one_undo():
    p, hid, w = mine()
    gid = group(p, hid, w[:2], "twisted_pair")
    assert plan_regroup(p, gid, kind="twisted_pair", wire_ids=w[:2]) == []
    before = model_hash(p)
    hist = History(p)
    hist.execute("regroup", plan_regroup(p, gid, kind="shielded_pair", end_a="pigtail"))
    hist.undo()
    assert model_hash(p) == before


def test_a_group_of_the_interface_type_and_a_released_harness_are_refused():
    p = sat15()
    generate_project(p)
    gid = p.harnesses["W001"].shields[0].id
    with pytest.raises(EditError, match="construction of the interface type"):
        plan_regroup(p, gid, kind="shielded_pair")
    with pytest.raises(EditError, match="construction of the interface type"):
        plan_set_group_ends(p, [gid], end_a="pigtail")
    q, hid, w = mine()
    gid = group(q, hid, w[:2], "twisted_pair")
    q.harnesses[hid] = evolve(q.harnesses[hid], status="released")
    with pytest.raises(EditError, match="released"):
        plan_regroup(q, gid, kind="shielded_pair")
    r, hid, w = mine()
    gid = group(r, hid, w[:2], "twisted_pair")
    with pytest.raises(EditError, match="A group is one of"):
        plan_regroup(r, gid, kind="triple")


def test_generation_keeps_a_regrouped_group_of_a_person():
    p = sat15()
    generate_project(p)
    h = p.harnesses["W009"]  # shielded pairs from the interface type
    ops, hid = plan_new_harness(p, "Mine")
    apply_ops(p, ops)
    for _ in range(2):
        ops, _cid = plan_add_connector(p, hid, part_id="EX-DSUB-9-M")
        apply_ops(p, ops)
    a, b = [c.id for c in p.harnesses[hid].connectors]
    for k in (1, 2):
        apply_ops(p, plan_add_wire(p, hid, a, str(k), b, str(k)))
    ids = [w.id for w in p.harnesses[hid].wires]
    gid = group(p, hid, ids, "twisted_pair")
    apply_ops(p, plan_regroup(p, gid, kind="shielded_pair", end_a="backshell_360"))
    apply_ops(p, plan_generation(p).ops)
    s = shield(p, hid, gid)
    assert (s.kind, s.end_a, s.wire_ids) == ("shielded_pair", "backshell_360", ids)
    assert h.shields  # (the generated harness is untouched by all this)


def test_files_hold_nothing_new_until_a_group_is_changed():
    p, hid, w = mine()
    gid = group(p, hid, w[:2], "twisted_pair")
    base = serialize(p)
    assert plan_regroup(p, gid, kind="twisted_pair") == []
    assert serialize(p) == base
    data = json.loads(base[f"physical/harnesses/{hid}.json"])
    assert set(data["shields"][0]) == {"id", "kind", "wire_ids", "end_a", "end_b", "manual"}
    apply_ops(p, plan_ungroup_all(p, [gid]))
    assert shield_count(p, hid) == 0


def shield_count(p, hid):
    return len(p.harnesses[hid].shields)
