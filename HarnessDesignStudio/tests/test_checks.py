"""REQ-CHECK-01: logical findings, fixes, waivers and the to-do list."""

import pytest

from harness_design_studio.core import checks, edit
from harness_design_studio.core.commands import History
from harness_design_studio.core.model import Project
from harness_design_studio.core.samples import mini3, new_project


def run(p: Project, ops: list) -> None:  # type: ignore[type-arg]
    History(p).execute("x", ops)


def rules(p: Project) -> set[str]:
    return {f.rule for f in checks.open_findings(p)}


def two_unit_project() -> Project:
    p = new_project()
    for t in ("computer", "actuator"):
        run(p, edit.ops_add_unit(p, t)[0])
    return p


def test_clean_sample_has_no_warnings() -> None:
    assert [f for f in checks.find(mini3()) if f.severity != "info"] == []


def test_isolated_unit_info() -> None:
    p = two_unit_project()
    assert {f.object_id for f in checks.open_findings(p) if f.rule == "isolated"} == {"OBC1", "RW1"}
    todo = checks.todos(p)
    assert todo[0].text == "2 units are not connected to anything" and todo[0].kind == "unit"


def test_unconfirmed_then_confirm_fix() -> None:
    p = two_unit_project()
    run(p, edit.ops_add_interface(p, "rs422", "OBC1", "RW1")[0])
    f = next(f for f in checks.open_findings(p) if f.rule == "unconfirmed")
    assert f.fix_label == "Confirm connectors"
    ops, msg = checks.fix_ops(p, f)
    run(p, ops)
    assert "unconfirmed" not in rules(p) and "Confirmed" in msg


def test_no_connector_finding_and_fix() -> None:
    p = two_unit_project()
    ops, iid = edit.ops_add_interface(p, "rs422", "OBC1", "RW1")
    run(p, ops)
    i = p.interfaces[iid]
    from harness_design_studio.core.commands import Put
    from harness_design_studio.core.model import evolve

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
    f = next(f for f in checks.open_findings(p) if f.rule == "no-connector")
    assert checks.todos(p)[0].text == "1 interface has no connector assigned"
    ops, _ = checks.fix_ops(p, f)
    run(p, ops)
    assert "no-connector" not in rules(p) and "unconfirmed" in rules(p)  # chosen, but marked auto


def test_no_connector_fix_without_free_connector() -> None:
    p = two_unit_project()
    ops, iid = edit.ops_add_interface(p, "rs422", "OBC1", "RW1")
    run(p, ops)
    from harness_design_studio.core.commands import Put
    from harness_design_studio.core.model import evolve

    i = p.interfaces[iid]
    run(
        p,
        [
            Put(
                "interfaces",
                evolve(i, endpoints=[evolve(i.endpoints[0], connector_id=None), i.endpoints[1]]),
            )
        ],
    )
    for c in edit.unit_connectors(p, "OBC1"):
        run(p, [Put("connectors", evolve(c, carries=["discrete"]))])
    f = next(f for f in checks.open_findings(p) if f.rule == "no-connector")
    with pytest.raises(edit.EditError, match="no free connector"):
        checks.fix_ops(p, f)


def test_cross_strap_warning_fix_and_waiver() -> None:
    p = mini3()
    run(p, edit.ops_redundant_copy(p, "RW1").ops)
    cross = [f for f in checks.open_findings(p) if f.rule == "cross-strap"]
    assert {f.object_id for f in cross} == {"IF-PWR-RW1-R", "IF-TM-RW1-R"}
    assert all(
        f.can_waive and f.fix_label and f.fix_label.startswith("Connect to a redundant copy of")
        for f in cross
    )
    assert checks.todos(p)[-1].text == "2 warnings to fix or waive"
    # waive one: mandatory justification
    with pytest.raises(edit.EditError, match="at least 10"):
        checks.waive_op(cross[0], "short")
    run(p, [checks.waive_op(cross[0], "Cross-strap is intentional, see ICD 4.2")])
    assert len(p.waivers) == 1
    waived = next(f for f in checks.find(p) if f.waiver)
    assert waived.waiver and waived.waiver.justification.startswith("Cross-strap")
    assert {f.object_id for f in checks.open_findings(p) if f.rule == "cross-strap"} == {
        cross[1].object_id
    }
    # fix the other one, then no warning remains
    ops, msg = checks.fix_ops(p, cross[1])
    run(p, ops)
    assert (
        not [f for f in checks.open_findings(p) if f.severity == "warning"]
        and "redundant chain" in msg
    )


def test_non_waivable_and_non_fixable() -> None:
    p = two_unit_project()
    f = next(f for f in checks.open_findings(p) if f.rule == "isolated")
    with pytest.raises(edit.EditError, match="cannot be waived"):
        checks.waive_op(f, "a long enough justification")
    with pytest.raises(edit.EditError, match="no one-click fix"):
        checks.fix_ops(p, f)


def test_finding_ids_are_stable_and_bounded() -> None:
    long = "X" * 60
    fid = checks.finding_id("cross-strap", long)
    assert len(fid) <= 64 and fid == checks.finding_id("cross-strap", long)
    assert checks.finding_id("a", "b") == "a.b"


def test_the_logical_rule_table_in_the_rule_reference_matches_the_checks() -> None:
    """tools/gen_rule_docs.py writes its own table of these four rules; it must not drift."""
    from harness_design_studio.core.commands import Put
    from harness_design_studio.core.model import evolve
    from tools.gen_rule_docs import LOGICAL

    p = mini3()
    run(p, edit.ops_redundant_copy(p, "RW1").ops)  # cross-strap, unconfirmed
    run(p, edit.ops_add_unit(p, "computer")[0])  # isolated
    q = two_unit_project()
    ops, iid = edit.ops_add_interface(q, "rs422", "OBC1", "RW1")
    run(q, ops)
    ends = [evolve(e, connector_id=None, auto=False) for e in q.interfaces[iid].endpoints]
    run(q, [Put("interfaces", evolve(q.interfaces[iid], endpoints=ends))])  # no-connector
    seen = {f.rule: f.severity for f in checks.find(p) + checks.find(q)}
    assert {r for r, *_ in LOGICAL} <= set(seen)
    for rule, severity, *_ in LOGICAL:
        assert seen[rule] == severity, rule
