"""REQ-EDIT-01: edits that the diagram canvas makes on several units at once (headless):
align, distribute, duplicate, move together, delete together and the impact of deleting a link."""

import pytest

from harness_design_studio.core import edit
from harness_design_studio.core.commands import History, Put
from harness_design_studio.core.integrity import check_integrity
from harness_design_studio.core.issues import errors
from harness_design_studio.core.model import Placement, Project
from harness_design_studio.core.samples import new_project, sat15


def run(p: Project, label: str, ops: list) -> None:  # type: ignore[type-arg]
    History(p).execute(label, ops)
    assert errors(check_integrity(p)) == []


def placed_y(ops: list) -> dict[str, float]:  # type: ignore[type-arg]
    return {o.obj.id: o.obj.y for o in ops if isinstance(o, Put) and isinstance(o.obj, Placement)}


@pytest.fixture
def five() -> Project:
    p = new_project()
    for t in ("computer", "power", "actuator", "sensor", "payload"):
        ops, _ = edit.ops_add_unit(p, t)
        run(p, "add", ops)
    return p


def place(p: Project, uid: str, x: float, y: float) -> None:
    run(p, "move", edit.ops_move_unit(p, uid, x, y))


def test_align_left_puts_every_left_edge_on_the_leftmost(five: Project) -> None:
    ids = sorted(five.units)[:3]
    for k, uid in enumerate(ids):
        place(five, uid, 100.0 + 30 * k, 40.0 + 200 * k)
    run(five, "align", edit.ops_align(five, ids, "left"))
    assert {five.placements[u].x for u in ids} == {100.0}
    assert [five.placements[u].y for u in ids] == [40.0, 240.0, 440.0]  # heights untouched


def test_align_top_bottom_and_middle(five: Project) -> None:
    a, b = sorted(five.units)[:2]
    place(five, a, 50.0, 100.0)
    place(five, b, 50.0, 500.0)
    heights = {a: 100.0, b: 60.0}
    ops = edit.ops_align(five, [a, b], "top", heights)
    assert placed_y(ops) == {b: 100.0}
    ops = edit.ops_align(five, [a, b], "bottom", heights)
    moved = placed_y(ops)
    assert moved == {a: 460.0}  # the lowest bottom edge is b's, at 560; a is 100 high
    ops = edit.ops_align(five, [a, b], "vmiddle", heights)
    moved = placed_y(ops)
    assert moved[a] + 50 == moved[b] + 30  # the two middles are on one line


def test_align_needs_two_units_and_a_known_mode(five: Project) -> None:
    a = sorted(five.units)[0]
    with pytest.raises(edit.EditError, match="at least two"):
        edit.ops_align(five, [a], "left")
    with pytest.raises(edit.EditError, match="Unknown"):
        edit.ops_align(five, sorted(five.units)[:2], "diagonal")
    with pytest.raises(edit.EditError, match="does not exist"):
        edit.ops_align(five, [a, "NOPE"], "left")


def test_distribute_gives_equal_gaps_and_keeps_the_outer_two(five: Project) -> None:
    ids = sorted(five.units)[:4]
    ys = [40.0, 140.0, 260.0, 600.0]
    for uid, y in zip(ids, ys, strict=True):
        place(five, uid, 30.0, y)
    heights = dict.fromkeys(ids, 50.0)
    run(five, "spread", edit.ops_distribute(five, ids, "vertical", heights))
    got = [five.placements[u].y for u in ids]
    assert got[0] == 40.0 and got[-1] == 600.0
    gaps = [got[k + 1] - got[k] - 50.0 for k in range(3)]
    assert max(gaps) - min(gaps) <= 1.0
    assert all(g > 0 for g in gaps)


def test_distribute_refuses_two_units_and_overlap(five: Project) -> None:
    ids = sorted(five.units)[:3]
    with pytest.raises(edit.EditError, match="at least three"):
        edit.ops_distribute(five, ids[:2], "horizontal")
    for uid, y in zip(ids, (40.0, 60.0, 80.0), strict=True):
        place(five, uid, 30.0, y)
    with pytest.raises(edit.EditError, match="too close"):
        edit.ops_distribute(five, ids, "vertical", dict.fromkeys(ids, 100.0))


def test_a_layout_edit_that_changes_nothing_gives_no_ops(five: Project) -> None:
    ids = sorted(five.units)[:2]
    for uid in ids:
        place(five, uid, 70.0, 100.0 + 300 * ids.index(uid))
    assert edit.ops_align(five, ids, "left") == []


def test_duplicate_copies_the_connectors_but_not_the_links() -> None:
    p = sat15()
    obc = next(u for u in p.units if p.units[u].side == "nominal" and edit.unit_connectors(p, u))
    n_units, n_ifs = len(p.units), len(p.interfaces)
    ops, new_id = edit.ops_duplicate_unit(p, obc)
    run(p, "dup", ops)
    assert len(p.units) == n_units + 1 and len(p.interfaces) == n_ifs
    assert new_id not in (obc, f"{obc}-R") and p.units[new_id].name.endswith("(copy)")
    assert [c.part_id for c in edit.unit_connectors(p, new_id)] == [
        c.part_id for c in edit.unit_connectors(p, obc)
    ]
    assert all(pin.interface_id is None for c in edit.unit_connectors(p, new_id) for pin in c.pins)
    assert new_id in p.placements


def test_duplicate_twice_gives_two_different_ids() -> None:
    p = new_project()
    ops, uid = edit.ops_add_unit(p, "computer")
    run(p, "add", ops)
    ids = []
    for _ in range(2):
        ops, new_id = edit.ops_duplicate_unit(p, uid)
        run(p, "dup", ops)
        ids.append(new_id)
    assert len(set(ids)) == 2 and uid not in ids


def test_move_units_is_one_step(five: Project) -> None:
    ids = sorted(five.units)[:2]
    history = History(five)
    before = len(history._undo) if hasattr(history, "_undo") else None
    ops = edit.ops_move_units(five, {ids[0]: (500.0, 40.0), ids[1]: (500.0, 300.0)})
    history.execute("move", ops)
    assert (five.placements[ids[0]].x, five.placements[ids[1]].y) == (500.0, 300.0)
    history.undo()
    assert five.placements[ids[0]].x != 500.0
    assert before is None or len(history._undo) == before


def test_delete_many_removes_each_link_once() -> None:
    p = sat15()
    uid = max(p.units, key=lambda u: edit.delete_impact(p, u).interfaces.__len__())
    impact = edit.delete_impact(p, uid)
    assert impact.interfaces  # the unit has links
    both = [impact.interfaces[0]]  # one of its own links, also named on its own
    other_unit = next(u for u in sorted(p.units) if u != uid)
    ops = edit.ops_delete_many(p, [uid], both)
    keys = [(o.collection, o.key) for o in ops]  # type: ignore[union-attr]
    assert len(keys) == len(set(keys))
    run(p, "delete", ops)
    assert uid not in p.units and not any(i in p.interfaces for i in impact.interfaces)
    assert other_unit in p.units


def test_interface_impact_names_both_ends_and_the_plans() -> None:
    from harness_design_studio.core.samples import sat15_full

    p = sat15_full()
    wired = next(
        i
        for i in sorted(p.interfaces)
        if any(w.interface_id == i for h in p.harnesses.values() for w in h.wires)
    )
    impact = edit.interface_impact(p, wired)
    assert len(impact.ends) == 2 and impact.type_name
    assert impact.plan_wires or impact.blocked_by_harnesses
    bare = new_project()
    with pytest.raises(edit.EditError):
        edit.interface_impact(bare, "IF-001")
