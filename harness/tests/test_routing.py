"""The drawing rules of the diagram that do not need Qt (core/routing.py)."""

from itertools import combinations

from harness_design_studio.core import routing
from harness_design_studio.core.routing import Geometry, RouteLink, route_links
from harness_design_studio.core.samples import new_project, sat15


def test_a_link_leaves_on_the_edge_that_faces_the_other_end() -> None:
    assert routing.side_toward(1, 2, "right") == "right"
    assert routing.side_toward(2, 1, "right") == "left"
    assert routing.side_toward(0, 3, "left") == "right"
    assert routing.side_toward(3, 0, "right") == "left"
    assert routing.side_toward(2, 2, "left") == "left"  # inside a lane: the default edge
    assert routing.side_toward(2, 2, "right") == "right"


def test_a_link_inside_a_lane_leaves_away_from_the_middle_when_there_is_room() -> None:
    assert routing.same_lane_side(1, 4, "right") == "left"  # the gap on its left is free
    assert routing.same_lane_side(2, 4, "left") == "right"
    assert routing.same_lane_side(0, 4, "right") == "right"  # nothing on its left: stay
    assert routing.same_lane_side(3, 4, "left") == "left"
    assert routing.same_lane_side(0, 1, "right") == "right"


def test_links_are_ordered_by_the_height_of_their_other_end() -> None:
    links = [("IF-3", 300.0), ("IF-1", 500.0), ("IF-2", 300.0), ("IF-4", 40.0)]
    assert routing.order_links(links) == ["IF-4", "IF-2", "IF-3", "IF-1"]
    assert routing.order_links([]) == []


def test_focus_of_an_interface_and_of_a_unit() -> None:
    p = sat15()
    iid = sorted(p.interfaces)[0]
    links, units = routing.focus(p, "interface", iid)
    assert links == {iid} and units == {e.unit_id for e in p.interfaces[iid].endpoints}
    uid = sorted(p.units)[0]
    links, units = routing.focus(p, "unit", uid)
    assert links and uid in units
    assert all(any(e.unit_id == uid for e in p.interfaces[i].endpoints) for i in links)
    assert routing.focus(p, "unit", "NOPE") == (set(), set())
    assert routing.focus(p, "interface", "NOPE") == (set(), set())
    assert routing.focus(new_project(), "unit", "X") == (set(), set())


def test_partner_is_the_unit_at_the_other_end() -> None:
    p = sat15()
    i = p.interfaces[sorted(p.interfaces)[0]]
    a, b = (e.unit_id for e in i.endpoints)
    assert routing.partner(p, i.id, a) == b and routing.partner(p, i.id, b) == a
    assert routing.partner(p, "NOPE", a) is None


# ---- the router ------------------------------------------------------------------------------

# four lanes of 176 px wide units, 254 px of free space between them
GEO = Geometry(
    gaps={0: (206.0, 460.0), 1: (636.0, 890.0), 2: (1066.0, 1320.0)},
    edges={0: (30.0, 206.0), 1: (460.0, 636.0), 2: (890.0, 1066.0), 3: (1320.0, 1496.0)},
    blocks={k: [(40.0, 200.0), (260.0, 420.0), (480.0, 640.0)] for k in range(4)},
)


def link(
    iid: str,
    ua: str,
    ub: str,
    la: int,
    lb: int,
    ya: float,
    yb: float,
    style: str = "data",
    side: str = "right",
) -> RouteLink:
    if la < lb:
        a, b = (GEO.edges[la][1], ya), (GEO.edges[lb][0], yb)
    elif la > lb:
        a, b = (GEO.edges[la][0], ya), (GEO.edges[lb][1], yb)
    else:
        x = GEO.edges[la][1] if side == "right" else GEO.edges[la][0]
        a, b = (x, ya), (x, yb)
    return RouteLink(iid, ua, ub, la, lb, a, b, side, style)


def segments(points: list[routing.Point]) -> list[tuple[routing.Point, routing.Point]]:
    return list(zip(points, points[1:], strict=False))


def crossings(routes: dict[str, list[routing.Point]]) -> int:
    """Number of places where a vertical piece of one link crosses a horizontal piece of another."""
    count = 0
    for (_, p), (_, q) in combinations(sorted(routes.items()), 2):
        for (a1, a2), (b1, b2) in [(s, t) for s in segments(p) for t in segments(q)] + [
            (t, s) for s in segments(p) for t in segments(q)
        ]:
            if a1[0] == a2[0] and b1[1] == b2[1]:  # a vertical and a horizontal
                x, y = a1[0], b1[1]
                if min(a1[1], a2[1]) < y < max(a1[1], a2[1]) and min(b1[0], b2[0]) < x < max(
                    b1[0], b2[0]
                ):
                    count += 1
    return count


def test_every_route_is_orthogonal_and_joins_its_two_ends() -> None:
    links = [
        link("L1", "A", "B", 0, 1, 100, 300),
        link("L2", "C", "D", 1, 2, 500, 120),
        link("L3", "E", "F", 2, 1, 300, 520),  # given right to left
        link("L4", "G", "H", 1, 1, 100, 300, side="left"),
    ]
    routes = route_links(links, GEO)
    assert set(routes) == {"L1", "L2", "L3", "L4"}
    for each in links:
        pts = routes[each.id]
        assert pts[0] == each.a and pts[-1] == each.b, each.id
        assert all(p[0] == q[0] or p[1] == q[1] for p, q in segments(pts)), each.id


def test_links_of_one_unit_and_kind_share_one_trunk() -> None:
    links = [link(f"L{k}", "HUB", f"T{k}", 0, 1, 100 + 30 * k, 80 + 140 * k) for k in range(4)]
    routes = route_links(links, GEO)
    bends = {r[1][0] for r in routes.values()}
    assert len(bends) == 1  # one trunk: the first bend of every link is at the same x
    assert 206 < bends.pop() < 460


def test_different_units_or_kinds_get_their_own_track_inside_the_gap() -> None:
    links = [
        link("L1", "A", "X", 0, 1, 100, 300),
        link("L2", "B", "Y", 0, 1, 150, 350),
        link("L3", "A", "Z", 0, 1, 180, 400, style="power"),  # another kind: another trunk
    ]
    routes = route_links(links, GEO)
    xs = {i: routes[i][1][0] for i in routes}
    assert len(set(xs.values())) == 3
    assert all(206 + routing.TRACK_MARGIN <= x <= 460 - routing.TRACK_MARGIN for x in xs.values())


def test_tracks_are_ordered_so_that_independent_links_do_not_cross() -> None:
    # two links that go down by the same amount, one under the other: no crossing in any case
    routes = route_links(
        [link("L1", "A", "X", 0, 1, 100, 200), link("L2", "B", "Y", 0, 1, 300, 400)], GEO
    )
    assert crossings(routes) == 0
    # nested spans: the order of the tracks must not make it worse than the best order
    nested = [link("L1", "A", "X", 0, 1, 100, 400), link("L2", "B", "Y", 0, 1, 200, 300)]
    assert crossings(route_links(nested, GEO)) <= 1


def test_a_link_across_lanes_goes_through_the_free_space_between_units() -> None:
    routes = route_links([link("L", "A", "B", 0, 3, 100, 580)], GEO)
    pts = routes["L"]
    middle = [
        (p, q) for p, q in segments(pts) if p[1] == q[1] and p[0] != q[0] and 460 < p[0] < 1320
    ]
    assert middle, pts
    for p, q in segments(pts):
        if p[1] == q[1] and min(p[0], q[0]) <= 636 and max(p[0], q[0]) >= 890:  # crosses lane 2
            assert not any(top - 6 < p[1] < bottom + 6 for top, bottom in GEO.blocks[2]), p


def test_links_inside_a_lane_run_on_a_spine_outside_it_nearer_when_shorter() -> None:
    routes = route_links(
        [
            link("S1", "H", "U1", 1, 1, 100, 300, side="right"),
            link("S2", "H", "U2", 1, 1, 100, 560, side="right"),
            link("S3", "K", "U3", 1, 1, 520, 560, side="right"),
        ],
        GEO,
    )
    spine = {i: max(p[0] for p in routes[i]) for i in routes}
    assert all(x > GEO.edges[1][1] for x in spine.values())
    assert spine["S3"] < spine["S1"] <= spine["S2"]  # S1 and S2 share a group and a spine
    left = route_links([link("S", "H", "U", 1, 1, 100, 300, side="left")], GEO)["S"]
    assert min(p[0] for p in left) < GEO.edges[1][0]


def test_routing_is_deterministic_and_independent_of_the_order_of_the_input() -> None:
    links = [
        link(f"L{k}", f"U{k % 3}", f"V{k % 4}", k % 2, 1 + k % 3, 100 + 40 * k, 500 - 30 * k)
        for k in range(12)
        if k % 2 != 1 + k % 3
    ]
    first = route_links(links, GEO)
    assert route_links(list(reversed(links)), GEO) == first
    assert route_links(links, GEO) == first


def test_a_gap_with_many_trunks_squeezes_the_tracks_instead_of_overflowing() -> None:
    links = [link(f"L{k:02d}", f"A{k}", f"B{k}", 0, 1, 100 + 7 * k, 700 - 7 * k) for k in range(60)]
    routes = route_links(links, GEO)
    xs = [r[1][0] for r in routes.values()]
    assert min(xs) >= 206 and max(xs) <= 460
