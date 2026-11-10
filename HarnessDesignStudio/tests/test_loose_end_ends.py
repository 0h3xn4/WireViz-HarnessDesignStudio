# SPDX-FileCopyrightText: 2026 0h3xn4
# SPDX-License-Identifier: GPL-3.0-only
# mypy: disable-error-code="no-untyped-def,no-untyped-call,arg-type,attr-defined,index"
"""REQ-GUI-28: which ends of the cables drawn by hand the diagram draws, and which connector a drop
on a device means (`core/cable_ends.py`, M4c). No Qt."""

import pytest

from harness_design_studio.core import cable_ends
from harness_design_studio.core.commands import apply_ops
from harness_design_studio.core.edit import EditError
from harness_design_studio.core.links import plan_add_link, plan_create_harness
from harness_design_studio.core.manual_harness import (
    plan_add_loose_end,
    plan_cable_from_port,
    plan_new_harness,
    plan_plug_loose_end,
    plan_unplug,
)
from tests.test_loose_end import labelled


def test_a_project_without_a_cable_drawn_by_hand_draws_no_end() -> None:
    p = labelled()
    assert cable_ends.drawn_ends(p) == [] and cable_ends.all_loose_ends(p) == []


def test_a_loose_end_hangs_on_the_port_of_its_cable_and_a_plugged_end_runs_to_its_port() -> None:
    p = labelled()
    r = plan_cable_from_port(p, "OBC-J01")
    apply_ops(p, r.ops)
    (end,) = cable_ends.drawn_ends(p)
    assert (end.connector_id, end.loose, end.anchor, end.anchor_unit, end.index) == (
        r.loose_id,
        True,
        "OBC-J01",
        "OBC",
        0,
    )
    assert end.pins == 4 and cable_ends.pos_mark(r.loose_id) == f"pos:{r.loose_id}"
    apply_ops(p, plan_plug_loose_end(p, r.harness_id, r.loose_id, "RW1-J02"))
    (end,) = cable_ends.drawn_ends(p)
    assert (end.loose, end.target, end.target_unit) == (False, "RW1-J02", "RW1")
    owner = cable_ends.harness_of(p, r.loose_id)
    assert owner is not None and owner.id == r.harness_id
    apply_ops(p, plan_unplug(p, r.harness_id, r.near_id))  # its anchor goes: the end follows
    (end,) = cable_ends.drawn_ends(p)
    assert end.anchor == "RW1-J02" and end.loose and end.connector_id == r.near_id


def test_a_cable_with_both_ends_loose_is_listed_but_not_drawn() -> None:
    p = labelled()
    r = plan_cable_from_port(p, "OBC-J01")
    apply_ops(p, r.ops)
    apply_ops(p, plan_unplug(p, r.harness_id, r.near_id))
    assert cable_ends.drawn_ends(p) == []
    assert [c.id for _h, c in cable_ends.all_loose_ends(p)] == sorted([r.near_id, r.loose_id])


def test_a_harness_made_from_a_connection_draws_only_its_loose_ends() -> None:
    p = labelled()
    ops, lid = plan_add_link(p, "OBC-J01", "RW1-J02")
    apply_ops(p, ops)
    ops, hid = plan_create_harness(p, lid)
    apply_ops(p, ops)
    assert cable_ends.drawn_ends(p) == []  # the connection's own line shows it
    ops, cid = plan_add_loose_end(p, hid, pin_ids=["9"])
    apply_ops(p, ops)
    assert [e.connector_id for e in cable_ends.drawn_ends(p)] == [cid]


def test_a_new_cable_from_a_device_goes_into_its_first_free_connector() -> None:
    p = labelled()
    assert cable_ends.free_port(p, "OBC") == "OBC-J01"
    apply_ops(p, plan_cable_from_port(p, "OBC-J01").ops)
    assert cable_ends.free_port(p, "OBC") == "OBC-J02"  # J01 has a cable plug on it now


def test_a_loose_end_dropped_on_a_device_takes_the_connector_whose_pin_names_fit() -> None:
    p = labelled()
    r = plan_cable_from_port(p, "OBC-J01")
    apply_ops(p, r.ops)
    assert cable_ends.plug_port(p, r.harness_id, r.loose_id, "RW1") == "RW1-J02"
    ops, hid = plan_new_harness(p, "Lonely")
    apply_ops(p, ops)
    ops, cid = plan_add_loose_end(p, hid, pin_ids=["1"])
    apply_ops(p, ops)
    with pytest.raises(EditError, match="no connector"):
        cable_ends.plug_port(p, hid, cid, "NOPE")
