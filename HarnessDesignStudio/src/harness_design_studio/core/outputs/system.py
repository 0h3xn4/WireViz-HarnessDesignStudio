"""System-level diagrams: the block diagram (interfaces by category) and the harness overview
(harnesses coloured by nominal/redundant). Zone lanes, deterministic placement. Colours are dark
enough to print, and every distinction also has a dash pattern, so greyscale prints stay readable."""

from dataclasses import dataclass

from harness_design_studio.core.links import derived_interfaces
from harness_design_studio.core.model import Project

from .canvas import Line, Rect, Sheet, Text, fit
from .stamp import Stamp

# category -> (colour, dash). Dash is None for solid. Colours have contrast >= 3:1 on white.
CATEGORY_STYLE: dict[str, tuple[str, tuple[float, float] | None]] = {
    "power": ("#8c2d04", None),
    "data": ("#08519c", None),
    "analog": ("#006d2c", (4.0, 1.5)),
    "rf": ("#6a3d9a", (1.0, 1.0)),
    "pyro": ("#b10026", (1.0, 1.0)),
    "discrete": ("#525252", (4.0, 1.5)),
    "thermal": ("#7f5800", (4.0, 1.5)),
    "ground": ("#252525", None),
    "other": ("#636363", None),
}
REDUNDANT_DASH = (2.5, 1.5)
NOMINAL_COLOR, REDUNDANT_COLOR = "#08519c", "#8c4a00"
BOX_W, BOX_H, LANE_W, ROW_H = 44.0, 12.0, 70.0, 17.0


@dataclass(frozen=True)
class Edge:
    a: str
    b: str
    label: str
    color: str
    dash: tuple[float, float] | None
    tag: str = ""  # a short text written beside the line (the ID of a connection), else none


def _layout(project: Project) -> tuple[dict[str, tuple[float, float]], float, float]:
    lanes: dict[str, list[str]] = {}
    order = list(project.zones)
    for uid in sorted(project.units):
        z = project.units[uid].zone or "(no zone)"
        if z not in order:
            order.append(z)
        lanes.setdefault(z, []).append(uid)
    order = [z for z in order if z in lanes]
    pos: dict[str, tuple[float, float]] = {}
    top = 22.0
    for k, z in enumerate(order):
        for r, uid in enumerate(lanes[z]):
            pos[uid] = (10.0 + k * LANE_W, top + r * ROW_H)
    rows = max((len(v) for v in lanes.values()), default=1)
    return pos, 20.0 + len(order) * LANE_W, top + rows * ROW_H + 40.0


def _slot(slots: dict[str, int], unit: str, y: float) -> float:
    """Spread the link ends along the box edge so they do not all meet in one point."""
    k = slots[unit] = slots.get(unit, -1) + 1
    return y + 1.5 + (k % 8) * (BOX_H - 3.0) / 7.0


def _diagram(
    project: Project,
    stamp: Stamp,
    title: str,
    edges: list[Edge],
    legend: list[tuple[str, str, tuple[float, float] | None]],
) -> Sheet:
    pos, w, h = _layout(project)
    legend_y = max((y for _x, y in pos.values()), default=20.0) + BOX_H + 16.0  # below every box
    sheet = Sheet(max(420.0, w), max(297.0, h, legend_y + 5.0 * len(legend) + 8.0), title=title)
    sheet.add(Rect(2, 2, sheet.width - 4, sheet.height - 4, width=0.5))
    sheet.add(Text(8, 10, fit(title, sheet.width - 16, 4.2), size=4.2, bold=True))
    sheet.add(Text(8, 16, fit(stamp.line, sheet.width - 16, 2.6), size=2.6, color="#555555"))
    for z in sorted(
        {project.units[u].zone or "(no zone)" for u in pos},
        key=lambda z: min(pos[u][0] for u in pos if (project.units[u].zone or "(no zone)") == z),
    ):
        x = min(pos[u][0] for u in pos if (project.units[u].zone or "(no zone)") == z)
        sheet.add(Text(x, 20.0, fit(z, LANE_W - 4, 2.8), size=2.8, color="#555555"))
    seen: dict[tuple[str, str], int] = {}
    slots: dict[str, int] = {}
    for e in edges:
        if e.a not in pos or e.b not in pos:
            continue
        key = (min(e.a, e.b), max(e.a, e.b))
        k = seen[key] = seen.get(key, -1) + 1
        (ax, ay), (bx, by) = pos[e.a], pos[e.b]
        off = (k - 0.0) * 1.1
        right_a, right_b = ax + BOX_W, bx + BOX_W
        if abs(ax - bx) < 1e-6:  # same lane: link on the right side
            x = right_a + 3.0 + off
            sheet.add(Line(right_a, ay + BOX_H / 2, x, ay + BOX_H / 2, color=e.color, dash=e.dash))
            sheet.add(Line(x, ay + BOX_H / 2, x, by + BOX_H / 2, color=e.color, dash=e.dash))
            sheet.add(Line(x, by + BOX_H / 2, right_b, by + BOX_H / 2, color=e.color, dash=e.dash))
            if e.tag:
                sheet.add(Text(x + 1.0, (ay + by) / 2 + BOX_H / 2, e.tag, size=2.0, color=e.color))
        else:
            (sx, sy, sid), (tx, ty, tid) = (
                ((right_a, ay, e.a), (bx, by, e.b))
                if ax < bx
                else ((ax, ay, e.a), (right_b, by, e.b))
            )
            y1, y2 = _slot(slots, sid, sy), _slot(slots, tid, ty)
            sheet.add(Line(sx, y1, tx, y2, color=e.color, dash=e.dash))
            if e.tag:
                sheet.add(Text((sx + tx) / 2, (y1 + y2) / 2 - 0.8, e.tag, size=2.0, color=e.color))
    for uid, (x, y) in pos.items():
        u = project.units[uid]
        sheet.add(Rect(x, y, BOX_W, BOX_H, width=0.4, fill="#ffffff"))
        sheet.add(Text(x + 1.5, y + 4.6, fit(uid, BOX_W - 3, 3.0), size=3.0, bold=True))
        sheet.add(Text(x + 1.5, y + 9.0, fit(u.name, BOX_W - 3, 2.4), size=2.4, color="#555555"))
    lx, ly = 8.0, legend_y
    for k, (name, color, dash) in enumerate(legend):
        sheet.add(
            Line(
                lx,
                ly + k * 5.0 - 1.0,
                lx + 12.0,
                ly + k * 5.0 - 1.0,
                width=0.6,
                color=color,
                dash=dash,
            )
        )
        sheet.add(Text(lx + 15.0, ly + k * 5.0, name, size=2.6))
    return sheet


def _link_edges(project: Project) -> list[Edge]:
    """One edge for each connection of two connectors (M2), in the style of what it carries: the
    category of the interface type most of its pairs belong to ("other" when no type fits), and
    the ID of the connection written beside the line so the diagram can be read against the
    connection list."""
    most: dict[str, tuple[int, str]] = {}  # link -> (pairs, category) of the biggest group
    for di in derived_interfaces(project):
        if di.type_id and (di.link_id not in most or len(di.pairs) > most[di.link_id][0]):
            most[di.link_id] = (len(di.pairs), project.interface_types[di.type_id].category)
    edges = []
    for link in sorted(project.links.values(), key=lambda x: x.id):
        a, b = project.connectors.get(link.a_connector), project.connectors.get(link.b_connector)
        if a is None or b is None or not a.unit_id or not b.unit_id or a.unit_id == b.unit_id:
            continue  # (a connection joins two different devices; anything else is not drawn)
        color, dash = CATEGORY_STYLE.get(
            most.get(link.id, (0, "other"))[1], CATEGORY_STYLE["other"]
        )
        edges.append(Edge(a.unit_id, b.unit_id, link.id, color, dash, tag=link.id))
    return edges


def block_diagram(project: Project, stamp: Stamp) -> Sheet:
    edges = []
    for i in sorted(project.interfaces.values(), key=lambda x: x.id):
        if len(i.endpoints) != 2 or i.type_id not in project.interface_types:
            continue
        color, dash = CATEGORY_STYLE.get(
            project.interface_types[i.type_id].category, CATEGORY_STYLE["other"]
        )
        if i.redundancy == "redundant":
            dash = REDUNDANT_DASH
        edges.append(Edge(i.endpoints[0].unit_id, i.endpoints[1].unit_id, i.id, color, dash))
    edges += _link_edges(project)
    legend = [
        (f"{c} (solid or dashed by type)", s[0], s[1])
        for c, s in CATEGORY_STYLE.items()
        if c != "other"
    ]
    legend.append(("redundant chain: short dashes", "#000000", REDUNDANT_DASH))
    return _diagram(project, stamp, f"Block diagram: {project.meta.name}", edges, legend)


def _harness_edges(project: Project) -> list[Edge]:
    edges: list[Edge] = []
    for h in sorted(project.harnesses.values(), key=lambda x: x.id):
        units = sorted(
            {
                box.unit_id
                for c in h.connectors
                if (box := project.connectors.get(c.mates_with or "")) is not None and box.unit_id
            }
        )
        if len(units) < 2:
            continue
        sides = {
            project.interfaces[w.interface_id].redundancy
            for w in h.wires
            if w.interface_id in project.interfaces
        }
        redundant = "redundant" in sides
        for k, first in enumerate(units):  # a harness joins every pair of its units
            for second in units[k + 1 :]:
                edges.append(
                    Edge(
                        first,
                        second,
                        h.id,
                        REDUNDANT_COLOR if redundant else NOMINAL_COLOR,
                        REDUNDANT_DASH if redundant else None,
                    )
                )
    return edges


def harness_overview(project: Project, stamp: Stamp) -> Sheet:
    edges = _harness_edges(project)
    legend = [
        ("nominal harness: solid", NOMINAL_COLOR, None),
        ("redundant harness: dashed", REDUNDANT_COLOR, REDUNDANT_DASH),
    ]
    return _diagram(project, stamp, f"Harness overview: {project.meta.name}", edges, legend)
