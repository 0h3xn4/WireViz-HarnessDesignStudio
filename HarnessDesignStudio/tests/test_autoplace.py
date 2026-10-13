"""REQ-EDIT-02: units saved without positions get deterministic, non-overlapping ones."""

from harness_design_studio.core import edit
from harness_design_studio.core.commands import apply_ops
from harness_design_studio.core.io.loader import load_project
from tests.helpers import FIXTURES


def test_m1_format_project_gets_distinct_positions() -> None:
    project = load_project(FIXTURES / "m1_project").project
    assert project.placements == {}
    ops = edit.ops_autoplace(project)
    assert len(ops) == len(project.units)
    apply_ops(project, ops)
    pts = [(p.x, p.y) for p in project.placements.values()]
    assert len(set(pts)) == len(pts)
    assert edit.ops_autoplace(project) == []  # nothing left to place


def test_autoplace_is_deterministic_and_respects_zones() -> None:
    a = load_project(FIXTURES / "m1_project").project
    b = load_project(FIXTURES / "m1_project").project
    assert edit.ops_autoplace(a) == edit.ops_autoplace(b)
    apply_ops(a, edit.ops_autoplace(a))
    for u in a.units.values():
        assert edit.zone_of_x(a, a.placements[u.id].x) == u.zone
