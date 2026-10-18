# mypy: disable-error-code="no-untyped-def,no-untyped-call"
"""CV-6 / CV-7 / CV-8: the index of what the diagram says about each object (problems, pending
values, not checked, auto-filled connectors, release locks). Pure data: no window."""

from pathlib import Path

import pytest

from harness_design_studio.core import checks, drc, templates
from harness_design_studio.core.checks import Finding
from harness_design_studio.core.io.loader import load_project
from harness_design_studio.core.model import Project, evolve
from harness_design_studio.core.vcs import lockview
from harness_design_studio.gui.canvas_state import (
    EMPTY,
    NO_INDEX,
    ObjectState,
    badge_text,
    build_index,
)
from tests.test_vcs_lockview import released


@pytest.fixture
def project(tmp_path: Path) -> Project:
    templates.create_project(tmp_path / "f", "flatsat")
    return load_project(tmp_path / "f").project


def finding(object_id: str, severity: str = "warning", rule: str = "r", waived: bool = False):
    from harness_design_studio.core.model import Waiver

    return Finding(
        id=f"{rule}.{object_id}",
        rule=rule,
        severity=severity,  # type: ignore[arg-type]
        object_id=object_id,
        title="t",
        why="w",
        waiver=Waiver(
            id=f"{rule}.{object_id}",
            rule=rule,
            object_id=object_id,
            justification="accepted for now",
        )
        if waived
        else None,
    )


def any_wire(p: Project):
    return next((h, w) for h in p.harnesses.values() for w in h.wires if w.interface_id)


# ---- findings land on the unit or link they are about -----------------------------------------------


def test_findings_are_counted_on_the_unit_or_link_by_severity(project) -> None:
    uid, iid = "OBC1", next(iter(project.interfaces))
    idx = build_index(
        project,
        [finding(uid, "error"), finding(uid), finding(uid), finding(iid, "error")],
    )
    u, i = idx.of("unit", uid), idx.of("interface", iid)
    assert (u.errors, u.warnings, u.problems) == (1, 2, 3)
    assert (i.errors, i.warnings) == (1, 0)
    assert idx.finding_ids("unit", uid) == ("r.OBC1", "r.OBC1", "r.OBC1")  # for a filtered list


def test_info_findings_and_waived_ones_are_not_counted(project) -> None:
    idx = build_index(
        project,
        [finding("OBC1", "info"), finding("OBC1", "warning", waived=True)],
    )
    assert idx.of("unit", "OBC1").problems == 0


def test_a_finding_on_a_box_connector_counts_on_its_unit(project) -> None:
    box = next(c for c in project.connectors.values() if c.role == "box" and c.unit_id == "OBC1")
    assert build_index(project, [finding(box.id)]).of("unit", "OBC1").warnings == 1


def test_a_finding_on_a_wire_counts_on_the_link_it_carries(project) -> None:
    _h, wire = any_wire(project)
    idx = build_index(project, [finding(wire.id, "error")])
    assert idx.of("interface", wire.interface_id).errors == 1
    assert idx.finding_ids("interface", wire.interface_id) == (f"r.{wire.id}",)


def test_a_finding_on_a_part_counts_on_every_unit_that_uses_it(project) -> None:
    box = next(c for c in project.connectors.values() if c.role == "box")
    users = {
        c.unit_id
        for c in project.connectors.values()
        if c.role == "box" and c.part_id == box.part_id
    }
    idx = build_index(project, [finding(box.part_id)])
    assert {u for u in project.units if idx.of("unit", u).warnings} == users


def test_a_finding_that_belongs_to_no_unit_or_link_is_left_out(project) -> None:
    h = next(iter(project.harnesses))
    idx = build_index(project, [finding(h), finding("unchecked"), finding("a.b.c")])
    assert not [k for k in idx.keys() if idx.of(*k).problems]  # noqa: SIM118


def test_the_real_flatsat_findings_reach_the_cards(project) -> None:
    """The audit's flatsat: 28 problems and none on the canvas. Now the lookalike connector
    warnings and the unapproved parts sit on the units they are about."""
    found = [f for f in checks.find(project) + drc.run(project) if f.waiver is None]
    idx = build_index(project, found)
    on_units = sum(idx.of("unit", u).warnings + idx.of("unit", u).errors for u in project.units)
    assert on_units >= 14
    assert idx.of("unit", "HTR1").warnings >= 1


# ---- CV-8: pending values and auto-filled connectors ------------------------------------------------


def test_missing_voltage_and_current_are_pending_on_the_link_and_sum_up_on_the_unit(
    project,
) -> None:
    power = [
        i
        for i in project.interfaces.values()
        if project.interface_types[i.type_id].category == "power"
    ]
    for i in power:
        project.interfaces[i.id] = evolve(i, voltage_v=None, max_current_a=None)
    idx = build_index(project, [])
    assert idx.of("interface", power[0].id).pending == 2
    unit = power[0].endpoints[0].unit_id
    expected = sum(2 for i in power if unit in {e.unit_id for e in i.endpoints})
    assert idx.of("unit", unit).pending == expected


def test_a_data_link_is_never_pending(project) -> None:
    can = next(i for i in project.interfaces.values() if i.type_id == "can")
    assert build_index(project, [], checked=True).of("interface", can.id).pending == 0


def test_auto_connectors_are_counted_per_unit_and_link(project) -> None:
    idx = build_index(project, [])
    total = sum(e.auto for i in project.interfaces.values() for e in i.endpoints)
    assert sum(idx.of("unit", u).auto for u in project.units) == total > 0
    one = next(i for i in project.interfaces.values() if any(e.auto for e in i.endpoints))
    assert idx.of("interface", one.id).auto == sum(e.auto for e in one.endpoints)


# ---- not checked ------------------------------------------------------------------------------------


def test_without_a_check_result_every_object_is_not_checked(project) -> None:
    idx = build_index(project, [], checked=False)
    assert idx.of("unit", "OBC1").not_checked == 1 and not idx.checked
    assert idx.of("interface", next(iter(project.interfaces))).not_checked == 1
    after = build_index(project, [], checked=True)
    assert after.of("unit", "OBC1").not_checked == 0 and after.checked


def test_a_pass_is_not_the_same_as_not_checked(project) -> None:
    """P2: an object with a result and no problem shows nothing; an unchecked one shows a badge."""
    passed = build_index(project, [], checked=True).of("unit", "SA1")
    unchecked = build_index(project, [], checked=False).of("unit", "SA1")
    assert passed.badges() == [] and unchecked.badges() == [("not-checked", 1)]


# ---- release locks ----------------------------------------------------------------------------------


def test_a_release_locks_units_links_and_connectors_with_harness_and_revision(tmp_path) -> None:
    p, hid = released(tmp_path)
    rev = p.harnesses[hid].revision
    locked = lockview.locked_objects(p)
    idx = build_index(p, [], locked)
    assert locked
    iid = next(k[1] for k in locked if k[0] == "interface")
    assert idx.of("interface", iid).locks == ((hid, rev),)
    assert idx.of("interface", iid).lock_text == f"{hid} {rev}"
    uid = next(k[1] for k in locked if k[0] == "unit")
    assert idx.of("unit", uid).locks == ((hid, rev),)
    box = next(k[1] for k in locked if k[0] == "box_connector")
    assert idx.of("connector", box).locks == ((hid, rev),)
    assert idx.of("connector", box).not_checked == 0  # (a connector carries a lock only)


def test_a_draft_project_has_no_locks(project) -> None:
    idx = build_index(project, [], lockview.locked_objects(project))
    assert not any(idx.of("unit", u).locks for u in project.units)


def test_the_lock_text_names_the_first_harness_and_counts_the_rest() -> None:
    s = ObjectState(locks=(("W001", "A"), ("W002", "B"), ("W003", "A")))
    assert s.lock_text == "W001 A +2"
    assert ObjectState().lock_text == ""


# ---- the value object -------------------------------------------------------------------------------


def test_badges_come_most_serious_first_with_their_counts() -> None:
    s = ObjectState(errors=2, warnings=1, pending=3, not_checked=1)
    assert s.badges() == [("fail", 2), ("warning", 1), ("pending", 3), ("not-checked", 1)]
    assert s.sentence().startswith("2 problems, 1 warning, 3 values still to enter")
    assert EMPTY.badges() == [] and EMPTY.clear and not s.clear


def test_a_badge_never_writes_more_than_99_and_not_checked_writes_no_one() -> None:
    assert badge_text(7, "fail") == "7" and badge_text(250, "warning") == "99+"
    assert badge_text(1, "not-checked") == "" and badge_text(3, "not-checked") == "3"


# ---- changes: only what differs is repainted ---------------------------------------------------------


def test_changed_from_names_exactly_the_objects_whose_marks_differ(project) -> None:
    a = build_index(project, [finding("OBC1"), finding("RW1")])
    b = build_index(project, [finding("OBC1"), finding("RW1"), finding("RW1"), finding("ST1")])
    assert b.changed_from(a) == {("unit", "RW1"), ("unit", "ST1")}
    c = build_index(project, [finding("OBC1")])
    assert c.changed_from(a) == {("unit", "RW1")}  # a mark that went away counts too
    assert a.changed_from(a) == set()
    assert a.changed_from(NO_INDEX) >= {("unit", "OBC1"), ("unit", "RW1")}


def test_present_lists_what_the_legend_may_show(project) -> None:
    none = build_index(project, [], checked=True)
    assert none.present()[:2] == (False, False)
    some = build_index(project, [finding("OBC1", "error"), finding("RW1")], checked=False)
    fail, warn, _pend, locked, unchecked = some.present()
    assert fail and warn and unchecked and not locked


@pytest.mark.perf
def test_building_the_index_is_fast_at_stress_size() -> None:
    """The index is rebuilt a moment after every edit: 200 units and 2000 links with thousands
    of findings must stay far below the edit budget."""
    import time

    from tools.bench_stress import build

    p = build()
    found = [finding(u, "warning", f"r{k}") for u in p.units for k in range(10)]
    found += [finding(i, "error") for i in p.interfaces]
    t = time.perf_counter()
    idx = build_index(p, found)
    took = (time.perf_counter() - t) * 1000
    assert idx.of("interface", next(iter(p.interfaces))).errors == 1
    assert took < 300 * 3, took
