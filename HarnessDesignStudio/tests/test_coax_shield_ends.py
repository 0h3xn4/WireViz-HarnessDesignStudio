# mypy: disable-error-code="no-untyped-def,no-untyped-call,no-any-return"
"""Release 1.10, D-182: the outer conductor of a coax is bonded at both ends whatever the grounding
concept of the project says about other shields; the other kinds of group follow the concept."""

import pytest

from harness_design_studio.core import drc
from harness_design_studio.core.commands import Put, apply_ops
from harness_design_studio.core.generate.engine import plan_generation
from harness_design_studio.core.io.loader import load_project
from harness_design_studio.core.manual_harness import plan_add_connector, plan_new_harness
from harness_design_studio.core.model import evolve
from harness_design_studio.core.model.config import ConfigFile
from harness_design_studio.core.model.physical import COAX_SHIELD_END
from harness_design_studio.core.samples import new_project
from harness_design_studio.core.wires import plan_add_wire, plan_group_wires
from harness_design_studio.resources import examples_path


def _set_ends(project, a, b) -> None:
    old = project.config["generation"]
    project.config["generation"] = ConfigFile(
        name="generation",
        placeholder=old.placeholder,
        values={**old.values, "shield_end_a": a, "shield_end_b": b},
    )


def _flatsat():
    root = examples_path()
    assert root is not None
    return load_project(root / "projects" / "flatsat").project


def _ends_by_kind(project) -> dict[str, set[tuple[str, str]]]:
    found: dict[str, set[tuple[str, str]]] = {}
    for h in project.harnesses.values():
        for s in h.shields:
            found.setdefault(s.kind, set()).add((s.end_a, s.end_b))
    return found


@pytest.mark.parametrize(
    "ends",
    [("backshell_360", "floating"), ("pigtail", "pigtail"), (None, None)],
    ids=["360-floating", "pigtail-pigtail", "unset"],
)
def test_generation_bonds_a_coax_at_both_ends_and_leaves_the_others_to_the_concept(ends):
    p = _flatsat()
    _set_ends(p, *ends)
    apply_ops(p, plan_generation(p).ops)
    found = _ends_by_kind(p)
    assert found["coax"] == {(COAX_SHIELD_END, COAX_SHIELD_END)}
    want = tuple(e if e is not None else "floating" for e in ends)
    assert found["twisted_pair"] == {
        want
    }  # unchanged: they follow the concept (or the placeholder)


def test_a_coax_that_a_person_groups_is_bonded_at_both_ends_too():
    p = new_project("Scratch")
    ops, hid = plan_new_harness(p, "Sensor harness")
    apply_ops(p, ops)
    cids = []
    for _ in range(2):
        ops, cid = plan_add_connector(p, hid, part_id="EX-DSUB-9-M")
        apply_ops(p, ops)
        cids.append(cid)
    for k in (1, 2, 3):
        apply_ops(p, plan_add_wire(p, hid, cids[0], str(k), cids[1], str(k), signal=f"S{k}"))
    _set_ends(p, "pigtail", "floating")
    wires = [w.id for w in p.harnesses[hid].wires]
    apply_ops(p, plan_group_wires(p, wires[:1], "coax"))
    apply_ops(p, plan_group_wires(p, wires[1:], "overall_shield"))
    ends = {s.kind: (s.end_a, s.end_b) for s in p.harnesses[hid].shields}
    assert ends["coax"] == (COAX_SHIELD_END, COAX_SHIELD_END)
    assert ends["overall_shield"] == ("pigtail", "floating")


def _hits(project, rule_id: str) -> list[str]:
    return [f.id for f in drc.run(project) if f.id.startswith(rule_id)]


def test_the_shield_rules_do_not_blame_a_coax_for_the_grounding_concept():
    p = _flatsat()
    _set_ends(p, "backshell_360", "floating")  # the concept of the flatsat example
    apply_ops(p, plan_generation(p).ops)
    coax = [(h.id, s.id) for h in p.harnesses.values() for s in h.shields if s.kind == "coax"]
    assert coax, "the flatsat example has a coax"
    wrong = _hits(p, "shield-wrong-end")
    unterminated = _hits(p, "shield-unterminated")
    for hid, sid in coax:
        assert not any(f"{hid}.{sid}" in h for h in wrong)
        assert not any(f"{hid}.{sid}" in h for h in unterminated)


def test_a_coax_that_was_edited_to_float_is_still_reported_as_unterminated():
    p = _flatsat()
    _set_ends(p, "backshell_360", "backshell_360")
    apply_ops(p, plan_generation(p).ops)
    h = next(h for h in p.harnesses.values() if any(s.kind == "coax" for s in h.shields))
    floating = [
        evolve(s, end_a="floating", end_b="floating") if s.kind == "coax" else s for s in h.shields
    ]
    apply_ops(p, [Put("harnesses", evolve(h, shields=floating))])
    assert any(h.id in x for x in _hits(p, "shield-unterminated")), (
        "a floating coax is still a finding"
    )
