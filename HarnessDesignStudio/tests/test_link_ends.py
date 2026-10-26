# mypy: disable-error-code="no-untyped-def,no-untyped-call"
"""REQ-GUI-13. Workshop feedback M3: what the diagram shows at the two ends of a connection (the
connector, its pins, the pins the connection pairs) and the way through the harness made from it."""

from harness_design_studio.core.commands import apply_ops
from harness_design_studio.core.links import (
    link_ends,
    link_path,
    plan_add_link,
    plan_create_harness,
)
from harness_design_studio.core.model import evolve
from tests.helpers import pinout_project


def linked():
    p = pinout_project()
    p.harnesses, p.interfaces, p.baselines = {}, {}, {}
    ops, lid = plan_add_link(p, "OBC-J01", "RW1-J02")
    apply_ops(p, ops)
    return p, lid


def test_the_ends_name_the_connector_its_pins_and_the_pins_paired():
    p, lid = linked()
    a, b = link_ends(p, p.links[lid])
    assert (a.connector_id, a.name, a.pins, a.used) == (
        "OBC-J01",
        p.connectors["OBC-J01"].name,
        5,
        4,
    )
    assert (b.connector_id, b.pins, b.used) == ("RW1-J02", 5, 4)


def test_a_connector_that_is_gone_shows_its_id_and_no_pins():
    p, lid = linked()
    del p.connectors["RW1-J02"]
    _a, b = link_ends(p, p.links[lid])
    assert (b.name, b.pins, b.used) == ("RW1-J02", 0, 0)


def test_the_path_is_empty_until_a_harness_is_made_then_runs_through_both_cable_ends():
    p, lid = linked()
    assert link_path(p, p.links[lid]) == []
    ops, hid = plan_create_harness(p, lid)
    apply_ops(p, ops)
    path = link_path(p, p.links[lid])
    h = p.harnesses[hid]
    cables = {c.mates_with: c.id for c in h.connectors}
    assert path == ["OBC-J01", cables["OBC-J01"], cables["RW1-J02"], "RW1-J02"]


def test_a_cable_connector_that_is_gone_is_left_out_and_a_missing_harness_gives_nothing():
    p, lid = linked()
    ops, hid = plan_create_harness(p, lid)
    apply_ops(p, ops)
    h = p.harnesses[hid]
    kept = [c for c in h.connectors if c.mates_with == "OBC-J01"]
    p.harnesses[hid] = evolve(h, connectors=kept, wires=[])
    assert link_path(p, p.links[lid]) == ["OBC-J01", kept[0].id, "RW1-J02"]
    del p.harnesses[hid]
    assert link_path(p, p.links[lid]) == []
