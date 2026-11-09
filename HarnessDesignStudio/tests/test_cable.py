# SPDX-FileCopyrightText: 2026 0h3xn4
# SPDX-License-Identifier: GPL-3.0-only
# mypy: disable-error-code="no-untyped-def,no-untyped-call,no-any-return,arg-type,attr-defined"
"""REQ-GUI-21. Tactile connecting, the part with no screen in it: the cable in hand as a state
machine (`gui/cable.py`: press, drag distance, release, click, Esc, the loose end), snapping to a
port, what a port accepts, the orthogonal line of the rubber band, the scroll at the edge of the
view, and the planner that plugs an end of a connection into another connector
(`core.links.plan_move_link_end`). No Qt."""

import pytest

from harness_design_studio.core.commands import apply_ops
from harness_design_studio.core.edit import EditError
from harness_design_studio.core.io.layout import model_hash
from harness_design_studio.core.links import plan_add_link, plan_move_link_end
from harness_design_studio.gui import cable as cb
from tests.helpers import pinout_project

A = cb.Port("OBC", "OBC-J01", 270.0, 116.0, "right")
B = cb.Port("RW1", "RW1-J02", 470.0, 254.0, "left")
B_PORT = cb.Landing("port", B, "RW1")


def bare():
    p = pinout_project()
    p.harnesses.clear()
    p.interfaces.clear()
    return p


def linked():
    p = bare()
    ops, lid = plan_add_link(p, "OBC-J01", "RW1-J02")
    apply_ops(p, ops)
    return p, lid


# ---- the gesture --------------------------------------------------------------------------------


def test_a_press_is_a_click_until_the_pointer_goes_the_drag_distance() -> None:
    c = cb.Cable()
    c.press(A, (270, 116))
    assert c.state == cb.PRESSED and not c.active
    assert not c.move((272, 117), scale=1.0)  # a wobble
    assert c.state == cb.PRESSED
    assert c.move((300, 120), scale=1.0)
    assert c.state == cb.CARRY and c.active


def test_the_drag_distance_is_in_screen_pixels_so_it_follows_the_zoom() -> None:
    c = cb.Cable()
    c.press(A, (0, 0))
    assert not c.move((2, 0), scale=1.0)  # 2 px at 100 %
    c.release((2, 0), cb.Landing())
    c.press(A, (0, 0))
    assert c.move((2, 0), scale=3.0)  # 6 px at 300 %


def test_a_click_on_a_port_is_a_click_and_nothing_stays_in_hand() -> None:
    c = cb.Cable()
    c.press(A, (270, 116))
    out = c.release((270, 116), cb.Landing())
    assert (out.kind, out.start) == ("click", cb.NEW)
    assert c.state == cb.IDLE and c.draft is None


def test_releasing_on_a_port_connects_the_two_ports() -> None:
    c = cb.Cable()
    c.press(A, (270, 116))
    c.move((400, 200))
    out = c.release((470, 254), B_PORT)
    assert (out.kind, out.anchor, out.target) == ("connect", A, B)
    assert c.state == cb.IDLE and c.draft is None


def test_releasing_on_a_card_connects_to_the_device_and_the_tool_picks_the_connector() -> None:
    c = cb.Cable()
    c.press(A, (270, 116))
    c.move((400, 200))
    out = c.release((500, 220), cb.Landing("card", unit_id="RW1"))
    assert (out.kind, out.target, out.target_unit) == ("connect", None, "RW1")


def test_releasing_on_empty_ground_leaves_a_loose_end_that_is_only_a_draft() -> None:
    c = cb.Cable()
    c.press(A, (270, 116))
    c.move((400, 200))
    out = c.release((400, 200), cb.Landing())
    assert out.kind == "loose"
    assert c.draft == cb.Draft(A, (400, 200))
    assert c.state == cb.IDLE and not c.active
    assert c.shown() == (A, (400, 200))  # it is still drawn


def test_a_loose_end_is_picked_up_by_a_drag_and_plugged_in() -> None:
    c = cb.Cable()
    c.press(A, (0, 0))
    c.move((50, 0))
    c.release((50, 0), cb.Landing())
    assert c.grab_draft((50, 0))
    c.move((120, 40))
    out = c.release((470, 254), B_PORT)
    assert (out.kind, out.anchor, out.target) == ("connect", A, B)
    assert c.draft is None  # the draft is used up


def test_a_loose_end_dropped_on_empty_ground_again_just_moves() -> None:
    c = cb.Cable()
    c.press(A, (0, 0))
    c.move((50, 0))
    c.release((50, 0), cb.Landing())
    c.grab_draft((50, 0))
    c.move((90, 70))
    assert c.release((90, 70), cb.Landing()).kind == "loose"
    assert c.draft == cb.Draft(A, (90, 70))


def test_a_click_on_a_loose_end_holds_it_and_the_next_click_puts_it_down() -> None:
    c = cb.Cable()
    c.press(A, (0, 0))
    c.move((50, 0))
    c.release((50, 0), cb.Landing())
    c.grab_draft((50, 0))
    out = c.release((50, 0), cb.Landing())  # a click, no drag
    assert (out.kind, out.start) == ("click", cb.DRAFT)
    assert c.state == cb.HOLD and c.active
    assert c.move((200, 80))  # it follows with no button
    assert c.pos == (200, 80)
    done = c.put_down((470, 254), B_PORT)
    assert done.kind == "connect" and c.state == cb.IDLE and c.draft is None


def test_esc_puts_the_cable_away_and_drops_the_draft() -> None:
    c = cb.Cable()
    c.press(A, (0, 0))
    c.move((50, 0))
    assert c.cancel().kind == "cancel" and c.state == cb.IDLE and c.draft is None
    c.press(A, (0, 0))
    c.move((50, 0))
    c.release((50, 0), cb.Landing())
    assert c.draft is not None
    assert c.cancel().kind == "dropped" and c.draft is None
    assert c.cancel().kind == "none"  # nothing left to put away


def test_a_refused_target_puts_the_cable_away_and_says_why() -> None:
    c = cb.Cable()
    c.press(A, (0, 0))
    c.move((50, 0))
    out = c.release((60, 0), cb.Landing("port", A, "OBC"), refused=cb.SAME_DEVICE)
    assert (out.kind, out.reason) == ("refused", cb.SAME_DEVICE)
    assert c.state == cb.IDLE and c.draft is None


def test_a_refused_drop_of_a_loose_end_keeps_the_draft_where_it_was() -> None:
    c = cb.Cable()
    c.press(A, (0, 0))
    c.move((50, 0))
    c.release((50, 0), cb.Landing())
    c.grab_draft((50, 0))
    c.move((300, 0))
    assert (
        c.release((300, 0), cb.Landing("port", A, "OBC"), refused=cb.SAME_DEVICE).kind == "refused"
    )
    assert c.draft == cb.Draft(A, (50, 0))


def test_one_loose_cable_at_a_time() -> None:
    c = cb.Cable()
    c.press(A, (0, 0))
    c.move((50, 0))
    c.release((50, 0), cb.Landing())
    c.press(B, (10, 10))  # a new cable begins
    assert c.draft is None


# ---- picking up the end of a connection ---------------------------------------------------------


def test_the_end_of_a_connection_moves_to_another_port_and_the_old_one_is_kept_until_then() -> None:
    c = cb.Cable()
    c.press(A, (470, 254), start=cb.REPLUG, replaces="L1", end="b")
    c.move((420, 300))
    other = cb.Port("PCDU", "PCDU-J01", 270.0, 356.0, "right")
    out = c.release((270, 356), cb.Landing("port", other, "PCDU"))
    assert (out.kind, out.replaces, out.end, out.target) == ("replug", "L1", "b", other)


def test_an_end_put_back_where_it_came_from_changes_nothing() -> None:
    c = cb.Cable()
    c.press(A, (470, 254), start=cb.REPLUG, replaces="L1", end="b")
    c.move((420, 300))
    assert c.release((470, 254), B_PORT, unchanged=True).kind == "cancel"


def test_an_end_released_on_empty_ground_becomes_a_loose_end_that_still_names_its_connection() -> (
    None
):
    c = cb.Cable()
    c.press(A, (470, 254), start=cb.REPLUG, replaces="L1", end="b")
    c.move((420, 300))
    out = c.release((420, 300), cb.Landing())
    assert out.kind == "loose" and c.draft == cb.Draft(A, (420, 300), "L1", "b")
    assert c.cancel().kind == "dropped"  # Esc: the connection was never touched


# ---- what a port accepts ------------------------------------------------------------------------


def test_a_port_of_another_device_with_free_pins_takes_the_cable() -> None:
    p = bare()
    occ = cb.Occupancy.of(p)
    assert cb.refusal(p, occ, A, B) == ""
    assert cb.refusal(p, occ, A, cb.Port("RW1")) == ""  # the device as a whole


def test_a_port_of_the_same_device_refuses() -> None:
    p = bare()
    occ = cb.Occupancy.of(p)
    assert cb.refusal(p, occ, A, cb.Port("OBC", "OBC-J02")) == cb.SAME_DEVICE
    assert cb.refusal(p, occ, A, cb.Port("OBC")) == cb.SAME_DEVICE


def test_a_connector_with_every_pin_in_a_connection_refuses() -> None:
    p = bare()
    ops, lid = plan_add_link(p, "OBC-J01", "RW1-J02", [(str(k), str(k)) for k in range(1, 6)])
    apply_ops(p, ops)
    occ = cb.Occupancy.of(p)
    assert occ.free_pins(p, "RW1-J02") == (0, 5)
    assert cb.refusal(p, occ, cb.Port("PCDU", "PCDU-J01"), B) == cb.FULL
    # the connection being moved does not hold its own pins
    assert cb.refusal(p, cb.Occupancy.of(p, ignoring=lid), cb.Port("PCDU", "PCDU-J01"), B) == ""


def test_a_connector_with_a_cable_plug_on_it_refuses() -> None:
    p = bare()
    occ = cb.Occupancy(plugs=frozenset({"RW1-J02"}))
    assert cb.refusal(p, occ, A, B) == cb.PLUGGED


def test_the_pins_of_the_connection_being_moved_do_not_count_as_used() -> None:
    p, lid = linked()
    assert cb.Occupancy.of(p).free_pins(p, "OBC-J01")[0] == 1
    assert cb.Occupancy.of(p, ignoring=lid).free_pins(p, "OBC-J01")[0] == 5


def test_a_device_total_counts_its_connectors_and_free_pins() -> None:
    p = bare()
    occ = cb.Occupancy.of(p)
    n, free, total = occ.device_free(p, "OBC")
    assert n == 3 and free == total == 5 + 3 + 3


# ---- geometry -----------------------------------------------------------------------------------


def test_snapping_takes_the_nearest_port_within_the_radius_in_screen_pixels() -> None:
    ports = [A, B]
    assert cb.nearest(ports, (475, 250), 1.0) == B
    assert cb.nearest(ports, (500, 250), 1.0) is None  # 30 px away
    assert cb.nearest(ports, (500, 250), 0.25) == B  # zoomed out 30 scene units are 7.5 px
    assert cb.nearest([], (0, 0), 1.0) is None


def test_snapping_prefers_the_nearer_of_two_ports_and_the_first_on_a_tie() -> None:
    near, far = cb.Port("A", "a1", 10, 10), cb.Port("A", "a2", 10, 24)
    assert cb.nearest([far, near], (10, 14), 1.0) == near
    left, right = cb.Port("A", "x", 0, 0), cb.Port("A", "y", 10, 0)
    assert cb.nearest([left, right], (5, 0), 1.0) == left


def test_the_rubber_band_runs_in_right_angles_and_meets_a_facing_point_halfway() -> None:
    pts = cb.route(A, (470.0, 254.0))
    assert pts[0] == A.at and pts[-1] == (470.0, 254.0)
    assert pts[1] == (370.0, 116.0) and pts[2] == (370.0, 254.0)
    for (x0, y0), (x1, y1) in zip(pts, pts[1:], strict=False):
        assert x0 == x1 or y0 == y1


def test_the_rubber_band_goes_round_when_the_point_is_behind_the_port() -> None:
    pts = cb.route(A, (100.0, 300.0))  # a right-hand port, the point to its left
    assert pts[1][0] == A.x + cb.OUT and pts[2][0] == pts[1][0]
    assert pts[-1] == (100.0, 300.0)
    left = cb.Port("RW1", "RW1-J02", 470.0, 254.0, "left")
    assert cb.route(left, (700.0, 100.0))[1][0] == 470.0 - cb.OUT


def test_the_plug_points_the_way_the_last_piece_runs() -> None:
    assert cb.plug_direction([(0, 0), (10, 0)]) == (1.0, 0.0)
    assert cb.plug_direction([(0, 0), (0, 0), (0, -5)]) == (0.0, -1.0)
    assert cb.plug_direction([(1, 1), (1, 1)]) == (1.0, 0.0)  # no length: a default


def test_the_plug_of_a_plugged_in_end_sits_a_little_way_out_along_the_line() -> None:
    poly = [(100.0, 50.0), (150.0, 50.0), (150.0, 90.0), (200.0, 90.0)]
    assert cb.plug_spot(poly, True) == (100.0 + cb.PLUG_OFFSET, 50.0)
    assert cb.plug_spot(poly, False) == (200.0 - cb.PLUG_OFFSET, 90.0)
    assert cb.plug_spot([(5.0, 5.0), (5.0, 5.0)], True) == (5.0, 5.0)


@pytest.mark.parametrize(
    ("at", "expected"),
    [
        ((500.0, 300.0), (0.0, 0.0)),  # the middle: no scroll
        ((1000.0, 300.0), (cb.SCROLL_PX, 0.0)),  # past the right edge: the top speed
        ((0.0, 300.0), (-cb.SCROLL_PX, 0.0)),
        ((500.0, 600.0), (0.0, cb.SCROLL_PX)),
        ((500.0, -50.0), (0.0, -cb.SCROLL_PX)),
    ],
)
def test_the_view_scrolls_when_the_cable_nears_its_edge(at, expected) -> None:
    assert cb.edge_scroll(1000.0, 600.0, at) == expected


def test_the_scroll_gets_faster_the_nearer_the_pointer_is_to_the_edge() -> None:
    slow = cb.edge_scroll(1000.0, 600.0, (1000.0 - cb.EDGE_PX * 0.75, 300.0))[0]
    fast = cb.edge_scroll(1000.0, 600.0, (1000.0 - cb.EDGE_PX * 0.25, 300.0))[0]
    assert 0 < slow < fast < cb.SCROLL_PX


# ---- moving an end of a connection (the model operation) ----------------------------------------


def test_plugging_an_end_into_another_connector_keeps_the_id_and_the_name_and_pairs_again() -> None:
    p, lid = linked()
    ops, connector = plan_move_link_end(p, lid, "b", "PCDU-J01")
    assert connector == "PCDU-J01" and len(ops) == 1
    apply_ops(p, ops)
    link = p.links[lid]
    assert (link.id, link.a_connector, link.b_connector) == (lid, "OBC-J01", "PCDU-J01")
    assert all(pair.b_pin in {x.id for x in p.connectors["PCDU-J01"].pins} for pair in link.pairs)


def test_the_other_end_can_move_too_and_the_pins_it_held_are_free_for_the_new_pairs() -> None:
    p, lid = linked()
    ops, connector = plan_move_link_end(
        p, lid, "a", "OBC-J03"
    )  # the same device, another connector
    apply_ops(p, ops)
    assert (p.links[lid].a_connector, p.links[lid].b_connector) == ("OBC-J03", "RW1-J02")


def test_naming_only_the_device_lets_the_tool_pick_the_connector() -> None:
    p, lid = linked()
    ops, connector = plan_move_link_end(p, lid, "b", unit_id="PCDU")
    assert connector.startswith("PCDU-J")
    apply_ops(p, ops)
    assert p.connectors[p.links[lid].b_connector].unit_id == "PCDU"


def test_putting_an_end_back_on_its_connector_is_no_change() -> None:
    p, lid = linked()
    assert plan_move_link_end(p, lid, "b", "RW1-J02") == ([], "RW1-J02")


def test_an_end_cannot_go_to_the_device_at_the_other_end() -> None:
    p, lid = linked()
    with pytest.raises(EditError, match="same device"):
        plan_move_link_end(p, lid, "b", "OBC-J02")
    with pytest.raises(EditError):
        plan_move_link_end(p, lid, "b", unit_id="OBC")


def test_an_end_is_refused_when_a_harness_was_made_from_the_connection() -> None:
    from harness_design_studio.core.links import plan_create_harness

    p, lid = linked()
    ops, _hid = plan_create_harness(p, lid)
    apply_ops(p, ops)
    with pytest.raises(EditError, match="harness"):
        plan_move_link_end(p, lid, "b", "PCDU-J01")


def test_a_cable_plug_on_the_new_connector_refuses_it() -> None:
    p, lid = linked()
    p2 = bare()
    ops2, lid2 = plan_add_link(p2, "OBC-J02", "PCDU-J02")
    apply_ops(p2, ops2)
    from harness_design_studio.core.links import plan_create_harness

    ops3, _ = plan_create_harness(p2, lid2)
    apply_ops(p2, ops3)
    ops4, lid4 = plan_add_link(p2, "OBC-J01", "RW1-J02")
    apply_ops(p2, ops4)
    with pytest.raises(EditError, match="cable plug"):
        plan_move_link_end(p2, lid4, "b", "PCDU-J02")


def test_a_device_with_no_connector_and_a_missing_name_are_refused_with_a_reason() -> None:
    p, lid = linked()
    with pytest.raises(EditError, match="Name the connector"):
        plan_move_link_end(p, lid, "b")
    with pytest.raises(EditError, match="'a' or 'b'"):
        plan_move_link_end(p, lid, "c", "PCDU-J01")
    with pytest.raises(EditError, match="does not exist"):
        plan_move_link_end(p, "L99", "b", "PCDU-J01")
    for cid in [c for c in p.connectors if p.connectors[c].unit_id == "PCDU"]:
        del p.connectors[cid]
    with pytest.raises(EditError, match="no connector yet"):
        plan_move_link_end(p, lid, "b", unit_id="PCDU")


def test_moving_an_end_changes_the_model_hash_as_any_connection_does_and_undo_restores_it() -> None:
    from harness_design_studio.core.commands import History

    p, lid = linked()
    before = model_hash(p)
    h = History(p)
    ops, _ = plan_move_link_end(p, lid, "b", "PCDU-J01")
    h.execute("move end", ops)
    assert model_hash(p) != before
    h.undo()
    assert model_hash(p) == before
