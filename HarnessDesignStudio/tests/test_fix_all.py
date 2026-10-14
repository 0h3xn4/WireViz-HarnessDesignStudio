"""SH-24 (core): `checks.fix_all_plan` turns every one-click fix of the open findings into the
operations of ONE transaction, worked out one after the other on a copy of the project."""

from dataclasses import replace
from pathlib import Path

from harness_design_studio.core import checks, edit
from harness_design_studio.core.commands import History, Put
from harness_design_studio.core.io.layout import model_hash
from harness_design_studio.core.model import Project, Waiver, evolve
from harness_design_studio.core.samples import mini3, new_project
from harness_design_studio.core.vcs.snapshot import carried_interfaces
from tests.test_change_control import do_release, exported, full, releasable


def run(p: Project, ops: list) -> None:  # type: ignore[type-arg]
    History(p).execute("x", ops)


def lose_connectors(p: Project, iid: str) -> None:
    i = p.interfaces[iid]
    run(
        p,
        [
            Put(
                "interfaces",
                evolve(
                    i, endpoints=[evolve(e, connector_id=None, auto=False) for e in i.endpoints]
                ),
            )
        ],
    )


def project_with_fixable_findings() -> Project:
    """Four units, two links whose connectors the tool chose (`unconfirmed`) and a third that
    lost its connectors (`no-connector`)."""
    p = new_project()
    for t in ("computer_xl", "actuator", "actuator", "actuator"):
        run(p, edit.ops_add_unit(p, t)[0])
    for other in ("RW1", "RW2"):
        ops, _iid = edit.ops_add_interface(p, "rs422", "OBC1", other)
        run(p, ops)
    ops, third = edit.ops_add_interface(p, "rs422", "OBC1", "RW3")
    run(p, ops)
    lose_connectors(p, third)
    return p


def test_fixable_lists_only_open_findings_that_have_a_fix() -> None:
    p = project_with_fixable_findings()
    fixable = checks.fixable(checks.open_findings(p))
    assert {f.rule for f in fixable} == {"unconfirmed", "no-connector"}
    assert all(f.fix_label and f.waiver is None for f in fixable)
    assert not [f for f in fixable if f.rule == "isolated"]  # an isolated unit has no fix


def test_the_summary_names_the_kinds_of_fix_biggest_first() -> None:
    p = project_with_fixable_findings()
    summary = checks.fix_summary(checks.open_findings(p))
    labels = [part.rsplit(" (", 1)[0] for part in summary.split(", ")]
    assert labels[0] == "Confirm connectors" and "Choose connectors automatically" in labels
    assert summary.startswith("Confirm connectors (2)") and summary.endswith("(1)")
    assert checks.fix_summary([]) == ""


def test_a_waived_finding_is_not_fixable() -> None:
    p = project_with_fixable_findings()
    f = next(f for f in checks.open_findings(p) if f.rule == "unconfirmed")
    waiver = Waiver(id=f.id, rule=f.rule, object_id=f.object_id, justification="Accepted for now")
    assert checks.fixable([replace(f, waiver=waiver)]) == []


def test_the_plan_resolves_every_fixable_finding_in_one_transaction_and_changes_nothing_itself() -> (
    None
):
    p = project_with_fixable_findings()
    findings = checks.open_findings(p)
    before = model_hash(p)
    plan = checks.fix_all_plan(p, findings)
    assert model_hash(p) == before  # planning only
    assert plan.skipped == []
    assert {f.id for f in plan.fixed} == {f.id for f in checks.fixable(findings)}
    chosen = {f.object_id for f in plan.fixed if f.rule == "no-connector"}
    hist = History(p)
    hist.execute("Fix all", plan.ops)
    # what was fixed is gone; a connector the tool chose for a link that had none is, as with the
    # single fix, marked auto and waits for a person to confirm it (never confirmed on the quiet)
    left = checks.fixable(checks.open_findings(p))
    assert {(f.rule, f.object_id) for f in left} == {("unconfirmed", i) for i in chosen} and chosen
    hist.undo()  # one step takes every fix back
    assert model_hash(p) == before


def test_a_later_fix_sees_the_connectors_an_earlier_one_took() -> None:
    """Two links of one unit that both lost their connectors must not get the same one."""
    p = new_project()
    for t in ("computer_xl", "actuator", "actuator"):
        run(p, edit.ops_add_unit(p, t)[0])
    ids = []
    for other in ("RW1", "RW2"):
        ops, iid = edit.ops_add_interface(p, "rs422", "OBC1", other)
        run(p, ops)
        ids.append(iid)
    for iid in ids:
        lose_connectors(p, iid)
    plan = checks.fix_all_plan(p, checks.open_findings(p))
    assert len([f for f in plan.fixed if f.rule == "no-connector"]) == 2
    run(p, plan.ops)
    used = [e.connector_id for iid in ids for e in p.interfaces[iid].endpoints]
    assert None not in used and len(set(used)) == len(used)


def test_a_clean_project_has_nothing_to_fix() -> None:
    p = mini3()
    plan = checks.fix_all_plan(p, checks.open_findings(p))
    assert (plan.ops, plan.fixed, plan.skipped) == ([], [], [])


def test_a_fix_that_a_release_lock_refuses_is_left_alone_with_the_reason(tmp_path: Path) -> None:
    p = full()
    hid = releasable(p)
    iid = sorted(carried_interfaces(p.harnesses[hid]))[0]
    i = p.interfaces[iid]
    hist = History(p)
    hist.execute("auto", [Put("interfaces", evolve(i, endpoints=[evolve(e, auto=True) for e in i.endpoints]))])  # fmt: skip
    do_release(p, hid, exported(p, tmp_path), hist)
    findings = checks.open_findings(p)
    plan = checks.fix_all_plan(p, findings)
    skipped = {f.object_id: why for f, why in plan.skipped}
    assert iid in skipped and "released" in skipped[iid]
    assert iid not in {f.object_id for f in plan.fixed}
    assert plan.fixed  # the others are still fixed
    hist.execute("Fix all", plan.ops)  # and what remains passes the release locks as one step
    left = {f.object_id for f in checks.fixable(checks.open_findings(p))}
    assert left == {iid}
