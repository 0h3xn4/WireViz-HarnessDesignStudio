"""Rules for drawing the links of the diagram that do not depend on Qt, so that they can be tested.

A dense diagram is readable when links are routed like a wiring diagram, not drawn as curves:

- a link leaves a unit on the edge that faces the unit at its other end (never through its box);
- the links on one edge are ordered by the height of their other ends (parallel links cross less);
- links run in right angles. The links of one unit, of one kind, between two lanes share one
  vertical **trunk** with short branches to each end, and every trunk has its own track in the gap
  between the lanes, ordered to cross as little as possible;
- a link between lanes that are not neighbours crosses the lanes in between through the free space
  between their units, not through a unit;
- links between two units of one lane run on a **spine** outside the lane;
- a selection puts the links it concerns in focus while everything else fades.

`route_links` is pure geometry: the editor gives it the end points and the room, it returns the
corner points of every link.
"""

from collections import Counter
from dataclasses import dataclass

from .model import Project

Point = tuple[float, float]
Key = tuple[str, str, str]  # ("L" or "R", the unit the trunk belongs to, style)


def side_toward(own_lane: int, other_lane: int, default: str) -> str:
    """The edge of a unit a link leaves from: the one that faces the unit at the other end. A link
    inside one lane leaves from the `default` edge (the one facing the middle of the diagram)."""
    if other_lane > own_lane:
        return "right"
    if other_lane < own_lane:
        return "left"
    return default


def order_links(links: list[tuple[str, float]]) -> list[str]:
    """Link IDs from top to bottom, ordered by the height of the unit at the other end (then by
    ID), so a link to a higher unit leaves higher up and parallel links do not cross."""
    return [iid for iid, _ in sorted(links, key=lambda t: (t[1], t[0]))]


def partner(project: Project, interface_id: str, unit_id: str) -> str | None:
    """The unit at the other end of an interface, or None for a link that ends twice on one unit."""
    i = project.interfaces.get(interface_id)
    if i is None:
        return None
    others = [e.unit_id for e in i.endpoints if e.unit_id != unit_id]
    return others[0] if others else None


def focus(project: Project, kind: str, ident: str) -> tuple[set[str], set[str]]:
    """(interface IDs, unit IDs) a selection concerns: an interface and its two units, or a unit,
    all its interfaces and the units at their other ends. Empty sets when it no longer exists."""
    if kind == "interface":
        i = project.interfaces.get(ident)
        if i is None:
            return set(), set()
        return {i.id}, {e.unit_id for e in i.endpoints}
    if kind == "unit" and ident in project.units:
        links = {
            i.id
            for i in project.interfaces.values()
            if any(e.unit_id == ident for e in i.endpoints)
        }
        units = {ident} | {e.unit_id for iid in links for e in project.interfaces[iid].endpoints}
        return links, units
    return set(), set()


def same_lane_side(lane: int, lanes: int, default: str) -> str:
    """The edge for a link between two units of one lane: the edge away from the middle of the
    diagram when a lane on that side can hold the curve, so these links stay out of the busy
    channel between the middle lanes. Otherwise the `default` edge."""
    outer = "left" if default == "right" else "right"
    room = lane > 0 if outer == "left" else lane < lanes - 1
    return outer if room else default


# ---- orthogonal routing with trunks -------------------------------------------------------------

TRACK_MARGIN = 14.0  # empty space kept next to the units on each side of a gap
TRACK_STEP = 16.0  # largest distance between two trunks in a gap
SPINE_BASE = 18.0  # distance of the first spine from the lane's units
SPINE_STEP = 12.0  # distance between spines
CORRIDOR_PAD = 12.0  # distance of a corridor from the units next to it
MAX_ORDERED = 40  # trunks of one gap that are ordered by counting crossings (more: by position)


@dataclass(frozen=True)
class RouteLink:
    """One link to route. `a` and `b` are its end points on the edges of its two units, `side` the
    edge unit A is left from (the edge of unit B is the same for a link inside one lane), `style`
    what links must have in common to share a trunk (their kind and whether they are redundant)."""

    id: str
    unit_a: str
    unit_b: str
    lane_a: int
    lane_b: int
    a: Point
    b: Point
    side: str
    style: str


@dataclass(frozen=True)
class Geometry:
    """The room: for every lane the x of the right edge of its units and of the left edge of the
    next lane's units (`gaps[k]` lies between lane k and k + 1), the outermost edges of its units,
    and the (top, bottom) of every unit in it."""

    gaps: dict[int, tuple[float, float]]
    edges: dict[int, tuple[float, float]]
    blocks: dict[int, list[tuple[float, float]]]


@dataclass(frozen=True)
class _Group:
    left: tuple[float, ...]  # heights where its members enter the trunk from the left
    right: tuple[float, ...]  # heights where its members leave the trunk to the right
    lo: float
    hi: float


def _group(members: list[tuple[str, float, float]]) -> _Group:
    left = tuple(y for _, y, _ in members)
    right = tuple(y for _, _, y in members)
    ys = left + right
    return _Group(left, right, min(ys), max(ys))


def _cost(g: _Group, h: _Group) -> int:
    """Crossings if the trunk of `g` runs left of the trunk of `h`: the branches of `g` to the right
    pass `h`'s trunk, and the branches of `h` to the left pass `g`'s trunk."""
    return sum(1 for y in g.right if h.lo < y < h.hi) + sum(1 for y in h.left if g.lo < y < g.hi)


def _order(keys: list[Key], groups: dict[Key, _Group]) -> list[Key]:
    """Trunks from left to right: first by their mean height, then neighbours are swapped while that
    saves a crossing (a few passes). Deterministic."""
    order = sorted(
        keys, key=lambda k: (sum(groups[k].left + groups[k].right) / (2 * len(groups[k].left)), k)
    )
    if len(order) > MAX_ORDERED:
        return order
    for _ in range(6):
        swapped = False
        for i in range(len(order) - 1):
            g, h = order[i], order[i + 1]
            if _cost(groups[h], groups[g]) < _cost(groups[g], groups[h]):
                order[i], order[i + 1] = h, g
                swapped = True
        if not swapped:
            break
    return order


def _tracks(gap: tuple[float, float], order: list[Key]) -> dict[Key, float]:
    """The x of every trunk of a gap, evenly spread and centred between the lanes."""
    lo, hi = (gap[0], gap[1]) if gap[0] <= gap[1] else (gap[1], gap[0])
    mid = (lo + hi) / 2
    n = len(order)
    if n <= 1:
        return {k: mid for k in order}
    step = min(TRACK_STEP, max(0.0, (hi - lo - 2 * TRACK_MARGIN) / (n - 1)))
    start = mid - step * (n - 1) / 2
    return {k: start + step * i for i, k in enumerate(order)}


def _corridor(geo: Geometry, lanes: range, y_ref: float) -> float:
    """A height where a link can cross the given lanes without touching a unit, as near as possible
    to `y_ref`: in the free space between two units (or above or below all of them)."""
    blocked = [b for k in lanes for b in geo.blocks.get(k, [])]
    if not blocked:
        return y_ref
    candidates = {y_ref}
    for top, bottom in blocked:
        candidates.update((top - CORRIDOR_PAD, bottom + CORRIDOR_PAD))
    free = [y for y in candidates if all(not (top - 6 < y < bottom + 6) for top, bottom in blocked)]
    return min(free, key=lambda y: (abs(y - y_ref), y)) if free else y_ref


def _span(ys: list[float]) -> float:
    return max(ys) - min(ys)


def _simplify(points: list[Point]) -> list[Point]:
    """Without repeated points and without points in the middle of a straight run."""
    out: list[Point] = []
    for p in points:
        if not out or p != out[-1]:
            out.append(p)
    k = 1
    while k < len(out) - 1:
        a, b, c = out[k - 1], out[k], out[k + 1]
        if (a[0] == b[0] == c[0]) or (a[1] == b[1] == c[1]):
            del out[k]
        else:
            k += 1
    return out


def _route_cross(
    cross: list[tuple[str, str, str, int, int, Point, Point, str]], geo: Geometry
) -> dict[str, list[Point]]:
    """Links between two lanes, given with the left unit first: (id, left unit, right unit, left
    lane, right lane, point on the left, point on the right, style)."""
    fan_left: Counter[tuple[int, str, str]] = Counter()
    fan_right: Counter[tuple[int, str, str]] = Counter()
    for _, ul, ur, ll, lr, _, _, style in cross:
        if lr - ll == 1:
            fan_left[(ll, style, ul)] += 1
            fan_right[(ll, style, ur)] += 1
    legs: dict[int, dict[Key, list[tuple[str, float, float]]]] = {}
    plan: dict[str, tuple[int, Key, int, Key, float | None]] = {}
    for iid, ul, ur, ll, lr, pl, pr, style in sorted(cross, key=lambda t: t[0]):
        if lr - ll == 1:
            left_wins = fan_left[(ll, style, ul)] >= fan_right[(ll, style, ur)]
            key = ("L", ul, style) if left_wins else ("R", ur, style)
            legs.setdefault(ll, {}).setdefault(key, []).append((iid, pl[1], pr[1]))
            plan[iid] = (ll, key, ll, key, None)
        else:
            yc = _corridor(geo, range(ll + 1, lr), pl[1])
            k1, k2 = ("L", ul, style), ("R", ur, style)
            legs.setdefault(ll, {}).setdefault(k1, []).append((iid, pl[1], yc))
            legs.setdefault(lr - 1, {}).setdefault(k2, []).append((iid, yc, pr[1]))
            plan[iid] = (ll, k1, lr - 1, k2, yc)
    tracks: dict[tuple[int, Key], float] = {}
    for gap, members in legs.items():
        groups = {key: _group(m) for key, m in members.items()}
        order = _order(sorted(groups), groups)
        for key, x in _tracks(geo.gaps[gap], order).items():
            tracks[(gap, key)] = x
    out: dict[str, list[Point]] = {}
    for iid, _ul, _ur, _ll, _lr, pl, pr, _style in cross:
        g1, k1, g2, k2, corridor = plan[iid]
        x1 = tracks[(g1, k1)]
        if corridor is None:
            out[iid] = _simplify([pl, (x1, pl[1]), (x1, pr[1]), pr])
        else:
            x2 = tracks[(g2, k2)]
            out[iid] = _simplify([pl, (x1, pl[1]), (x1, corridor), (x2, corridor), (x2, pr[1]), pr])
    return out


def _route_same(same: list[RouteLink], geo: Geometry) -> dict[str, list[Point]]:
    """Links between two units of one lane: a spine outside the lane, nearer for shorter spans."""
    fan: Counter[tuple[int, str, str, str]] = Counter()
    for link in same:
        for unit in (link.unit_a, link.unit_b):
            fan[(link.lane_a, link.side, link.style, unit)] += 1
    members: dict[tuple[int, str, tuple[str, str]], list[RouteLink]] = {}
    for link in sorted(same, key=lambda x: x.id):
        count = {
            u: fan[(link.lane_a, link.side, link.style, u)] for u in (link.unit_a, link.unit_b)
        }
        hub = max(sorted(count), key=lambda u: count[u])
        members.setdefault((link.lane_a, link.side, (link.style, hub)), []).append(link)
    out: dict[str, list[Point]] = {}
    by_edge: dict[tuple[int, str], list[tuple[str, str]]] = {}
    for lane, side, key in members:
        by_edge.setdefault((lane, side), []).append(key)
    for (lane, side), keys in by_edge.items():
        spans = {
            key: _span([y for link in members[(lane, side, key)] for y in (link.a[1], link.b[1])])
            for key in keys
        }

        left, right = geo.edges.get(lane, (0.0, 0.0))
        for rank, key in enumerate(sorted(keys, key=lambda k: (spans[k], k))):
            group = members[(lane, side, key)]
            xs = [p[0] for link in group for p in (link.a, link.b)]
            reach = SPINE_BASE + SPINE_STEP * rank
            x = max(right, max(xs)) + reach if side == "right" else min(left, min(xs)) - reach
            for link in group:
                out[link.id] = _simplify([link.a, (x, link.a[1]), (x, link.b[1]), link.b])
    return out


def route_links(links: list[RouteLink], geo: Geometry) -> dict[str, list[Point]]:
    """The corner points of every link, in right angles, from its end A to its end B. The room must
    hold the gap on each side of the lanes a link joins (`ValueError` names the link otherwise)."""
    for link in links:
        lo, hi = sorted((link.lane_a, link.lane_b))
        if lo != hi and (lo not in geo.gaps or hi - 1 not in geo.gaps):
            raise ValueError(
                f"Link '{link.id}' joins lane {lo} and lane {hi}, but the room has no gap "
                f"{lo if lo not in geo.gaps else hi - 1} for it."
            )
    cross = []
    same = []
    for link in links:
        if link.lane_a == link.lane_b:
            same.append(link)
        elif link.lane_a < link.lane_b:
            cross.append(
                (
                    link.id,
                    link.unit_a,
                    link.unit_b,
                    link.lane_a,
                    link.lane_b,
                    link.a,
                    link.b,
                    link.style,
                )
            )
        else:
            cross.append(
                (
                    link.id,
                    link.unit_b,
                    link.unit_a,
                    link.lane_b,
                    link.lane_a,
                    link.b,
                    link.a,
                    link.style,
                )
            )
    routes = _route_cross(cross, geo)
    routes.update(_route_same(same, geo))
    # a link that was given with its right end first is returned from its end A to its end B
    by_id = {link.id: link for link in links}
    return {iid: (pts if pts[0] == by_id[iid].a else pts[::-1]) for iid, pts in routes.items()}
