"""Editing operations for the block diagram. Pure functions: they build lists of `Op`s.

Nothing here mutates a project. The GUI runs the returned ops through `History.execute`, so every
edit is a transaction that is rolled back if it would leave the project inconsistent.
"""

from __future__ import annotations

from dataclasses import dataclass

from .commands import Delete, Op, Put, SetConfig, SetZones
from .describe import part_gender
from .errors import HarnessError
from .model import (
    Connector,
    Endpoint,
    InterfaceInstance,
    Pin,
    Placement,
    Project,
    Unit,
    evolve,
)
from .model.config import ConfigFile

LANE_WIDTH = 470.0
LANE_X0 = 10.0
UNIT_W = 240.0
UNIT_FOOTPRINT_H = 150.0  # smallest room a unit gets, whatever its size
SLOT_STEP = 70.0
PORT_ROW = 28.0  # height of one connector row of a unit drawn in expert mode
UNIT_GAP = 24.0  # empty space kept between two stacked units
MAX_DIAGRAM_HEIGHT = 200_000.0  # no unit is placed lower than this


def expert_height(connector_count: int) -> float:
    """Height of a unit in expert mode: a header and one row per connector."""
    return 46 + PORT_ROW * connector_count


def guided_height(link_count: int) -> float:
    """Height of a unit in guided mode: it grows with the number of links that end on it."""
    return 70 + 14 * max(0, link_count - 2)


def unit_footprints(project: Project) -> dict[str, float]:
    """The room every unit needs: its taller height of the two modes, so that switching the mode
    never makes units overlap. One pass over the project, whatever its size."""
    connectors: dict[str, int] = {}
    for c in project.connectors.values():
        if c.role == "box" and c.unit_id is not None:
            connectors[c.unit_id] = connectors.get(c.unit_id, 0) + 1
    links: dict[str, int] = {}
    for i in project.interfaces.values():
        for uid in {e.unit_id for e in i.endpoints}:
            links[uid] = links.get(uid, 0) + 1
    floor = UNIT_FOOTPRINT_H - UNIT_GAP
    return {
        uid: max(floor, expert_height(connectors.get(uid, 0)), guided_height(links.get(uid, 0)))
        for uid in project.units
    }


def unit_footprint(project: Project, unit_id: str) -> float:
    return unit_footprints(project).get(unit_id, UNIT_FOOTPRINT_H - UNIT_GAP)


class EditError(HarnessError):
    """An edit that cannot be done; the message says why in plain language."""


# ---- templates ---------------------------------------------------------------------------------


@dataclass(frozen=True)
class ConnectorTemplate:
    part_id: str
    carries: tuple[str, ...]


@dataclass(frozen=True)
class UnitTemplate:
    id: str
    label: str
    prefix: str
    subsystem: str
    connectors: tuple[ConnectorTemplate, ...]


_POWER = {"power_primary", "power_secondary", "heater"}
_MICROD_BY_TYPES = {1: 9, 2: 15, 3: 21, 4: 25}  # distinct interface types on one connector -> pins


def _box_part(carries: tuple[str, ...]) -> str:
    """The baseline connector (D-130) for a unit connector that carries these interface types:
    SMA for RF, an RJ45 for Ethernet, otherwise the Micro-D size that fits the number of types."""
    if carries == ("rf_coax",):
        return "EX-SMA-F"
    if carries == ("ethernet",):
        return "EX-RJ45-F"
    if set(carries) <= _POWER:
        return "EX-MICROD-9-F"
    return f"EX-MICROD-{_MICROD_BY_TYPES.get(len(carries), 31)}-F"


def _t(id_: str, label: str, prefix: str, sub: str, *conns: tuple[str, ...]) -> UnitTemplate:
    return UnitTemplate(
        id_, label, prefix, sub, tuple(ConnectorTemplate(_box_part(c), c) for c in conns)
    )


_COMMS = ("rs422", "rs485", "can")  # the baseline communication standards (D-130)

TEMPLATES: dict[str, UnitTemplate] = {
    t.id: t
    for t in (
        _t("computer", "Computer", "OBC", "avionics", (*_COMMS, "discrete"), ("power_primary",), ("rs422", "can"), ("ethernet",)),
        _t("power", "Power unit", "PCDU", "power", ("power_primary",), ("power_primary",), ("discrete", "rs422")),
        _t("actuator", "Actuator (wheel)", "RW", "aocs", ("power_primary",), _COMMS),
        _t("sensor", "Sensor (star tracker)", "ST", "aocs", ("power_primary",), ("rs422", "rs485")),
        _t("payload", "Payload", "PL", "payload", ("power_primary",), ("ethernet",), _COMMS, ("rf_coax",)),
        _t("transceiver", "Transceiver", "TRX", "comms", ("power_primary",), ("rs422", "can"), ("rf_coax",)),
        _t("pyro", "Pyro unit", "PYRO", "mechanisms", ("power_primary",), ("pyro",), ("discrete",)),
        _t("computer_xl", "Computer (many interfaces)", "OBC", "avionics", ("power_primary",), *[(*_COMMS, "discrete", "analog", "thermistor")] * 11, ("ethernet",), ("ethernet",)),
        _t("pdu", "Power distribution unit", "PCDU", "power", *[("power_primary",)] * 10, ("heater",), ("can", "rs422")),
        _t("battery", "Battery", "BAT", "power", ("power_primary",), ("can", "rs422")),
        _t("solar_array", "Solar array", "SA", "power", ("power_primary",), ("thermistor",)),
        _t("sun_sensor", "Sun sensor", "SS", "aocs", ("power_primary",), ("analog",)),
        _t("magnetorquer", "Magnetorquer", "MTQ", "aocs", ("power_primary",), ("discrete",)),
        _t("heater_panel", "Heater panel", "HTR", "thermal", ("heater",), ("thermistor",)),
    )
}  # fmt: skip


# ---- ids and placement -------------------------------------------------------------------------


def _taken(ids: set[str]) -> set[str]:
    return {i.casefold() for i in ids}


def _connector_owners(project: Project) -> set[str]:
    """Casefolded `<unit>` parts of connector IDs `<unit>-Jnn`: a renamed unit keeps its old connector IDs,
    so the old unit ID is not free for a new unit (its connectors would be overwritten)."""
    return {c.id.rsplit("-", 1)[0].casefold() for c in project.connectors.values() if "-" in c.id}


def next_unit_id(project: Project, prefix: str) -> tuple[str, int]:
    taken = _taken(set(project.units)) | _connector_owners(project)
    n = 1
    while f"{prefix}{n}".casefold() in taken:
        n += 1
    return f"{prefix}{n}", n


def next_interface_id(project: Project, extra: set[str] | None = None) -> str:
    taken = _taken(set(project.interfaces) | (extra or set()))
    n = 1
    while f"IF-{n:03d}".casefold() in taken:
        n += 1
    return f"IF-{n:03d}"


def effective_zones(project: Project) -> list[str]:
    zones = list(project.zones)
    extra = sorted({u.zone for u in project.units.values() if u.zone and u.zone not in zones})
    return zones + extra


def lane_index(lane_count: int, x: float) -> int:
    """Lane (0-based) of a unit whose left edge is at `x`."""
    centre = x + UNIT_W / 2
    return max(0, min(lane_count - 1, int((centre - LANE_X0) // LANE_WIDTH)))


def lane_index_of_x(project: Project, x: float) -> int:
    return lane_index(len(effective_zones(project)), x)


def zone_of_x(project: Project, x: float) -> str:
    return effective_zones(project)[lane_index_of_x(project, x)]


def lane_x(index: int) -> float:
    return LANE_X0 + index * LANE_WIDTH + 20


def position_of(project: Project, unit_id: str) -> tuple[float, float]:
    p = project.placements.get(unit_id)
    if p is not None:
        return p.x, p.y
    return free_slot(project, project.units[unit_id].zone)


def ops_autoplace(project: Project) -> list[Op]:
    """Positions for units that have none (e.g. projects saved before layouts existed).

    Deterministic: units are placed in (zone, ID) order, each in the first free slot of its lane,
    and each placement is visible to the next so units never stack.
    """
    missing = sorted(
        (u for u in project.units.values() if u.id not in project.placements),
        key=lambda u: (u.zone or "", u.id),
    )
    if not missing:
        return []
    from copy import copy

    scratch = copy(project)
    scratch.placements = dict(project.placements)
    ops: list[Op] = []
    for u in missing:
        x, y = free_slot(scratch, u.zone)
        place = Placement(id=u.id, x=x, y=y)
        scratch.placements[u.id] = place
        ops.append(Put("placements", place))
    return ops


def ops_arrange(project: Project) -> list[Op]:
    """Tidy the diagram: units stay in their lanes (zones); inside each lane they are ordered
    to shorten and uncross links (barycenter ordering from the neighbouring lanes, a few sweeps),
    then stacked top to bottom without overlap. Deterministic; one undo step."""
    zones = effective_zones(project)
    lanes: dict[int, list[str]] = {k: [] for k in range(len(zones))}
    for uid in sorted(project.units):
        zone = project.units[uid].zone
        lane = (
            zones.index(zone)
            if zone in zones
            else lane_index_of_x(project, position_of(project, uid)[0])
        )
        lanes[lane].append(uid)
    lane_of = {u: k for k, units in lanes.items() for u in units}
    neighbours: dict[str, set[str]] = {u: set() for u in project.units}
    for i in project.interfaces.values():
        ends = [e.unit_id for e in i.endpoints if e.unit_id in project.units]
        for a in ends:
            neighbours[a].update(b for b in ends if b != a)
    order = {u: float(pos) for units in lanes.values() for pos, u in enumerate(units)}
    # start from the current vertical order so a tidy diagram stays put
    for units in lanes.values():
        units.sort(key=lambda u: (position_of(project, u)[1], u))
        order.update({u: float(pos) for pos, u in enumerate(units)})

    def centre(u: str) -> float:
        others = [order[n] for n in neighbours[u] if lane_of[n] != lane_of[u]]
        return sum(others) / len(others) if others else order[u]

    for _sweep in range(4):
        for k in sorted(lanes):
            lanes[k].sort(key=lambda u: (centre(u), u))
            order.update({u: float(pos) for pos, u in enumerate(lanes[k])})
    room = unit_footprints(project)
    ops: list[Op] = []
    for k, units in sorted(lanes.items()):
        y = 40.0
        for uid in units:
            x = lane_x(k)
            now = project.placements.get(uid)
            if now is None or (now.x, now.y) != (x, y):
                ops.append(Put("placements", Placement(id=uid, x=x, y=y)))
            y += room[uid] + UNIT_GAP
    return ops


def free_slot(
    project: Project, zone: str | None = None, height: float | None = None
) -> tuple[float, float]:
    """First position in the preferred lane (then the others) that overlaps no placed unit.
    `height` is the room the new unit needs (default: the smallest footprint)."""
    zones = effective_zones(project)
    need = height if height is not None else UNIT_FOOTPRINT_H - UNIT_GAP
    room = unit_footprints(project)
    placed = [
        (p.x, p.y, room[uid]) for uid, p in project.placements.items() if uid in project.units
    ]
    if zone in zones:
        order = [zones.index(zone)]  # the caller asked for this lane: stay in it
    else:  # no preference: fill the emptiest lane first so the diagram stays balanced
        counts = [
            sum(1 for px, _, _ in placed if lane_index_of_x(project, px) == i)
            for i in range(len(zones))
        ]
        order = sorted(range(len(zones)), key=lambda i: (counts[i], i))
    for lane in order:
        x = lane_x(lane)
        y = 40.0
        while y < MAX_DIAGRAM_HEIGHT:
            if not any(
                abs(px - x) < UNIT_W + 10 and y < py + ph + UNIT_GAP and py < y + need + UNIT_GAP
                for px, py, ph in placed
            ):
                return x, y
            y += SLOT_STEP
    raise EditError("There is no room left in the diagram for another unit.")


# ---- compatibility (prevent errors instead of reporting them) -----------------------------------


@dataclass(frozen=True)
class Compat:
    ok: bool
    short: str = ""
    why: str = ""


def interface_using(project: Project, connector_id: str) -> InterfaceInstance | None:
    for i in project.interfaces.values():
        if any(e.connector_id == connector_id for e in i.endpoints):
            return i
    return None


def unit_connectors(project: Project, unit_id: str) -> list[Connector]:
    return sorted(
        (c for c in project.connectors.values() if c.unit_id == unit_id and c.role == "box"),
        key=lambda c: c.id,
    )


def carries(connector: Connector, type_id: str) -> bool:
    return not connector.carries or type_id in connector.carries


def free_connectors(project: Project, unit_id: str, type_id: str) -> list[Connector]:
    return [
        c
        for c in unit_connectors(project, unit_id)
        if carries(c, type_id) and interface_using(project, c.id) is None
    ]


def _type_name(project: Project, type_id: str) -> str:
    t = project.interface_types.get(type_id)
    return t.name if t else type_id


def unit_compat(
    project: Project, type_id: str, unit_id: str, source_unit: str | None = None
) -> Compat:
    """Can `unit_id` take an interface of this type (Guided mode: connector chosen automatically)?"""
    if type_id not in project.interface_types:
        return Compat(
            False, "Unknown interface type", f"Interface type '{type_id}' does not exist."
        )
    if source_unit == unit_id:
        return Compat(False, "Same unit", "A unit cannot be connected to itself.")
    if not free_connectors(project, unit_id, type_id):
        name = _type_name(project, type_id)
        return Compat(
            False,
            f"No free {name} connector",
            f'{unit_id} has no free {name} connector. Use a unit template that has one (for example "Computer (many interfaces)").',
        )
    return Compat(True)


def connector_compat(
    project: Project, type_id: str, connector_id: str, source_unit: str | None = None
) -> Compat:
    """Can this exact connector take an interface of this type (Expert mode)?"""
    c = project.connectors.get(connector_id)
    if c is None or c.role != "box" or c.unit_id is None:
        return Compat(
            False, "Not a unit connector", f"'{connector_id}' is not a connector of a unit."
        )
    if source_unit == c.unit_id:
        return Compat(False, "Same unit", "A unit cannot be connected to itself.")
    used = interface_using(project, connector_id)
    if used is not None:
        return Compat(
            False, "In use", f"{c.name} already carries {used.id}. One interface per connector."
        )
    if not carries(c, type_id):
        names = ", ".join(_type_name(project, t) for t in c.carries)
        return Compat(
            False,
            "Wrong type",
            f"{c.name} does not carry {_type_name(project, type_id)} (it carries {names}).",
        )
    return Compat(True)


# ---- unit operations ---------------------------------------------------------------------------


def ops_add_unit(
    project: Project,
    template_id: str,
    x: float | None = None,
    y: float | None = None,
    *,
    unit_id: str | None = None,
    name: str | None = None,
) -> tuple[list[Op], str]:
    """Ops that add a unit made from a template. The ID comes from the template's prefix unless
    `unit_id` is given (it must be free); `name` replaces the generated name."""
    tpl = TEMPLATES.get(template_id)
    if tpl is None:
        raise EditError(f"Unknown unit template '{template_id}'.")
    missing = sorted({c.part_id for c in tpl.connectors} - set(project.parts))
    if missing:
        raise EditError(
            f"The parts library lacks {', '.join(missing)}; add the starter parts first."
        )
    if unit_id is None:
        uid, n = next_unit_id(project, tpl.prefix)
        unit_name = name or f"{tpl.label} {n}"
    else:
        uid = unit_id
        if uid.casefold() in _taken(set(project.units)) | _connector_owners(project):
            raise EditError(f"ID {uid} is already used.")
        unit_name = name or f"{tpl.label} {uid}"
    if x is None or y is None:
        x, y = free_slot(project, None, expert_height(len(tpl.connectors)))
    zone = zone_of_x(project, x)
    ops: list[Op] = [
        Put(
            "units",
            Unit(id=uid, name=unit_name, subsystem=tpl.subsystem, zone=zone, side="nominal"),
        ),
        Put("placements", Placement(id=uid, x=x, y=y)),
    ]
    for k, ct in enumerate(tpl.connectors, start=1):
        part = project.parts[ct.part_id]
        pins = [Pin(id=str(i)) for i in range(1, (part.pin_count or 0) + 1)]
        ops.append(
            Put(
                "connectors",
                Connector(
                    id=f"{uid}-J{k:02d}",
                    name=f"J{k:02d}",
                    role="box",
                    part_id=ct.part_id,
                    unit_id=uid,
                    gender=part_gender(part),  # a part that says male or female sets it
                    carries=list(ct.carries),
                    pins=pins,
                ),
            )
        )
    return ops, uid


@dataclass(frozen=True)
class DeleteImpact:
    interfaces: tuple[str, ...]
    connectors: tuple[str, ...]
    blocked_by_harnesses: tuple[str, ...]


def delete_impact(project: Project, unit_id: str) -> DeleteImpact:
    conns = {c.id for c in unit_connectors(project, unit_id)}
    ifs = sorted(
        i.id for i in project.interfaces.values() if any(e.unit_id == unit_id for e in i.endpoints)
    )
    blocked = sorted(
        h.id
        for h in project.harnesses.values()
        if (not h.generated or h.status == "released")  # generated plans just become outdated
        and any(
            w.from_connector in conns or w.to_connector in conns or w.interface_id in ifs
            for w in h.wires
        )
    )
    return DeleteImpact(tuple(ifs), tuple(sorted(conns)), tuple(blocked))


def ops_delete_unit(project: Project, unit_id: str) -> list[Op]:
    if unit_id not in project.units:
        raise EditError(f"Unit '{unit_id}' does not exist.")
    impact = delete_impact(project, unit_id)
    if impact.blocked_by_harnesses:
        raise EditError(
            f"{unit_id} cannot be deleted: {_blocked_text(project, impact.blocked_by_harnesses)}"
        )
    ops: list[Op] = [Delete("interfaces", i) for i in impact.interfaces]
    ops += [Delete("connectors", c) for c in impact.connectors]
    gone = {unit_id, *impact.interfaces, *impact.connectors}
    ops += _waiver_deletes(project, gone)
    if unit_id in project.placements:
        ops.append(Delete("placements", unit_id))
    ops.append(Delete("units", unit_id))
    return ops


def ops_delete_interface(project: Project, interface_id: str) -> list[Op]:
    if interface_id not in project.interfaces:
        raise EditError(f"Interface '{interface_id}' does not exist.")
    users = sorted(
        h.id
        for h in project.harnesses.values()
        if (not h.generated or h.status == "released")
        and any(w.interface_id == interface_id for w in h.wires)
    )
    if users:
        raise EditError(f"{interface_id} cannot be deleted: {_blocked_text(project, users)}")
    return [Delete("interfaces", interface_id), *_waiver_deletes(project, {interface_id})]


def _blocked_text(project: Project, harness_ids: tuple[str, ...] | list[str]) -> str:
    """What to do about harnesses that stop a deletion (released ones and hand-made ones)."""
    released = [h for h in harness_ids if project.harnesses[h].status == "released"]
    by_hand = [h for h in harness_ids if h not in released]
    parts = []
    if released:
        parts.append(
            f"{', '.join(released)} is released. Start a new revision of it first "
            "(Harness plans, New revision) so it can be changed."
        )
    if by_hand:
        parts.append(
            f"{', '.join(by_hand)} was made by hand and has wires for it. "
            "Delete that harness first (Harness plans, Delete harness)."
        )
    return " ".join(parts)


def _waiver_deletes(project: Project, object_ids: set[str]) -> list[Op]:
    """Waivers about objects that no longer exist would only confuse the next reader."""
    return [
        Delete("waivers", w.id)
        for w in project.waivers.values()
        if w.object_id in object_ids or w.object_id.split(".")[0] in object_ids
    ]


def ops_delete_harness(project: Project, harness_id: str) -> list[Op]:
    """Delete a draft harness (a generated one comes back at the next generate)."""
    h = project.harnesses.get(harness_id)
    if h is None:
        raise EditError(f"Harness '{harness_id}' does not exist.")
    if h.status == "released":
        raise EditError(
            f"{harness_id} is released and cannot be deleted. Start a new revision to change it."
        )
    return [Delete("harnesses", harness_id)]


def ops_move_unit(project: Project, unit_id: str, x: float, y: float) -> list[Op]:
    unit = project.units[unit_id]
    ops: list[Op] = [Put("placements", Placement(id=unit_id, x=x, y=y))]
    zone = zone_of_x(project, x)
    if unit.zone != zone:
        ops.append(Put("units", evolve(unit, zone=zone)))
    return ops


def ops_add_zone(project: Project, name: str) -> list[Op]:
    name = name.strip()
    if not name:
        raise EditError("A zone needs a name.")
    if name.casefold() in {z.casefold() for z in effective_zones(project)}:
        raise EditError(f"A zone called '{name}' already exists.")
    return [SetZones((*project.zones, name))]


def ops_rename_unit(project: Project, old: str, new: str) -> list[Op]:
    if old not in project.units:
        raise EditError(f"Unit '{old}' does not exist.")
    if new == old:
        return []
    if new.casefold() in _taken(set(project.units) - {old}):
        raise EditError(f"ID {new} is already used.")
    foreign = {
        c.id.rsplit("-", 1)[0].casefold()
        for c in project.connectors.values()
        if "-" in c.id and c.unit_id != old
    }
    if new.casefold() in foreign:
        raise EditError(f"ID {new} is already used as the start of other connector IDs.")
    unit = evolve(project.units[old], id=new)  # validates the new ID format
    ops: list[Op] = [Put("units", unit), Delete("units", old)]
    if old in project.placements:
        p = project.placements[old]
        ops += [Put("placements", evolve(p, id=new)), Delete("placements", old)]
    for c in unit_connectors(project, old):
        ops.append(Put("connectors", evolve(c, unit_id=new)))
    for i in project.interfaces.values():
        if any(e.unit_id == old for e in i.endpoints):
            eps = [evolve(e, unit_id=new) if e.unit_id == old else e for e in i.endpoints]
            ops.append(Put("interfaces", evolve(i, endpoints=eps)))
    return ops


# ---- interface operations ----------------------------------------------------------------------


def ops_add_interface(
    project: Project,
    type_id: str,
    from_unit: str,
    to_unit: str,
    from_connector: str | None = None,
    to_connector: str | None = None,
    *,
    interface_id: str | None = None,
    name: str | None = None,
    redundancy: str | None = None,
    avoid_connectors: set[str] | None = None,
) -> tuple[list[Op], str]:
    """Add an interface; connectors not given are chosen automatically and marked `auto`."""
    chosen: list[tuple[str, str, bool]] = []
    for unit_id, conn_id in ((from_unit, from_connector), (to_unit, to_connector)):
        if unit_id not in project.units:
            raise EditError(f"Unit '{unit_id}' does not exist.")
        if conn_id is None:
            compat = unit_compat(
                project, type_id, unit_id, from_unit if unit_id == to_unit else None
            )
            if not compat.ok:
                raise EditError(compat.why)
            free = [
                c
                for c in free_connectors(project, unit_id, type_id)
                if c.id not in (avoid_connectors or set())
            ]
            if not free:
                raise EditError(f"{unit_id} has no free {_type_name(project, type_id)} connector.")
            chosen.append((unit_id, free[0].id, True))
        else:
            compat = connector_compat(
                project, type_id, conn_id, from_unit if unit_id == to_unit else None
            )
            if not compat.ok:
                raise EditError(compat.why)
            chosen.append((unit_id, conn_id, False))
    iid = interface_id or next_interface_id(project)
    side = project.units[from_unit].side
    inst = InterfaceInstance(
        id=iid,
        name=name or f"{_type_name(project, type_id)} {from_unit} to {to_unit}",
        type_id=type_id,
        endpoints=[Endpoint(unit_id=u, connector_id=c, auto=a) for u, c, a in chosen],
        redundancy=redundancy if redundancy is not None else ("none" if side == "none" else side),  # type: ignore[arg-type]
    )
    return [Put("interfaces", inst)], iid


def ops_confirm_interface(project: Project, interface_id: str) -> list[Op]:
    i = project.interfaces[interface_id]
    return [Put("interfaces", evolve(i, endpoints=[evolve(e, auto=False) for e in i.endpoints]))]


def twin_id(unit_id: str) -> str:
    return f"{unit_id}-R"


@dataclass(frozen=True)
class RedundantCopy:
    ops: list[Op]
    twin_id: str
    skipped: tuple[str, ...]  # interfaces that could not be mirrored (no free connector)


def ops_redundant_copy(project: Project, unit_id: str) -> RedundantCopy:
    """Copy a nominal unit as its redundant twin and mirror its interfaces (names end in -R)."""
    unit = project.units.get(unit_id)
    if unit is None:
        raise EditError(f"Unit '{unit_id}' does not exist.")
    if unit.side == "redundant":
        raise EditError(f"{unit_id} is already on the redundant chain.")
    tid = twin_id(unit_id)
    if tid.casefold() in _taken(set(project.units)):
        raise EditError(f"{unit_id} already has a redundant copy ({tid}).")
    ops = _twin_unit_ops(project, unit)
    # Work on a scratch view so mirrored interfaces see the twin's connectors.
    scratch = clone_with(project, ops)
    skipped: list[str] = []
    for i in sorted(project.interfaces.values(), key=lambda x: x.id):
        if i.redundancy == "redundant" or not any(e.unit_id == unit_id for e in i.endpoints):
            continue
        other = next((e for e in i.endpoints if e.unit_id != unit_id), None)
        if other is None:
            continue
        other_twin = (
            twin_id(other.unit_id) if twin_id(other.unit_id) in scratch.units else other.unit_id
        )
        mine = next(e for e in i.endpoints if e.unit_id == unit_id)
        from_a = i.endpoints[0].unit_id == unit_id
        f_unit, t_unit = (tid, other_twin) if from_a else (other_twin, tid)
        f_conn = _twin_connector(mine, tid) if from_a else None
        t_conn = None if from_a else _twin_connector(mine, tid)
        iid = f"{i.id}-R"
        try:
            new_ops, _ = ops_add_interface(
                scratch,
                i.type_id,
                f_unit,
                t_unit,
                f_conn,
                t_conn,
                interface_id=iid,
                name=f"{i.name} (redundant)",
                redundancy="redundant",
            )
        except EditError:
            skipped.append(i.id)
            continue
        ops += new_ops
        scratch = clone_with(scratch, new_ops)
    return RedundantCopy(ops, tid, tuple(skipped))


def _twin_connector(endpoint: Endpoint, tid: str) -> str | None:
    if endpoint.connector_id is None:
        return None
    suffix = endpoint.connector_id.rsplit("-", 1)[-1]
    return f"{tid}-{suffix}"


def _twin_unit_ops(project: Project, unit: Unit) -> list[Op]:
    tid = twin_id(unit.id)
    lane = lane_index_of_x(project, position_of(project, unit.id)[0])
    zones = effective_zones(project)
    target_zone = zones[(lane + 1) % len(zones)] if len(zones) > 1 else zones[0]
    x, y = free_slot(project, target_zone, unit_footprint(project, unit.id))
    twin = evolve(
        unit, id=tid, name=f"{unit.name} (redundant)", side="redundant", zone=zone_of_x(project, x)
    )
    ops: list[Op] = [Put("units", twin), Put("placements", Placement(id=tid, x=x, y=y))]
    for c in unit_connectors(project, unit.id):
        suffix = c.id.rsplit("-", 1)[-1]
        new_id = f"{tid}-{suffix}"
        if new_id.casefold() in {x.casefold() for x in project.connectors}:
            raise EditError(f"Cannot make the redundant copy: connector {new_id} already exists.")
        ops.append(Put("connectors", evolve(c, id=new_id, unit_id=tid)))
    return ops


def ops_complete_chain(project: Project, interface_id: str) -> tuple[list[Op], str]:
    """Fix for a cross-strap: move the nominal end of the interface onto a redundant twin."""
    i = project.interfaces[interface_id]
    nominal = [
        e
        for e in i.endpoints
        if e.unit_id in project.units and project.units[e.unit_id].side == "nominal"
    ]
    if not nominal:
        raise EditError("This interface has no nominal end to replace.")
    end = nominal[0]
    tid = twin_id(end.unit_id)
    ops: list[Op] = []
    scratch = project
    if tid not in project.units:
        ops += _twin_unit_ops(project, project.units[end.unit_id])
        scratch = clone_with(project, ops)
    conn = _twin_connector(end, tid)
    if conn is None or not connector_compat(scratch, i.type_id, conn).ok:
        free = free_connectors(scratch, tid, i.type_id)
        if not free:
            raise EditError(f"{tid} has no free {_type_name(project, i.type_id)} connector.")
        conn = free[0].id
    eps = [
        Endpoint(unit_id=tid, connector_id=conn, auto=end.auto) if e is end else e
        for e in i.endpoints
    ]
    ops.append(Put("interfaces", evolve(i, endpoints=eps, redundancy="redundant")))
    return ops, tid


def clone_with(project: Project, ops: list[Op]) -> Project:
    """A scratch copy of `project` with `ops` applied (entities are immutable, so copies are cheap)."""
    from copy import copy

    from .commands import apply_ops

    dup = copy(project)
    for name in (
        "units",
        "interface_types",
        "interfaces",
        "connectors",
        "harnesses",
        "parts",
        "placements",
        "waivers",
        "baselines",
        "changelog",
        "config",
    ):
        setattr(dup, name, dict(getattr(project, name)))
    dup.zones = list(project.zones)
    apply_ops(dup, ops)
    return dup


def ops_set_endpoint_connector(
    project: Project, interface_id: str, index: int, connector_id: str
) -> list[Op]:
    """Expert mode: choose the exact connector for one end of an interface (marks it confirmed)."""
    i = project.interfaces[interface_id]
    end = i.endpoints[index]
    if end.connector_id == connector_id:
        return []
    compat = connector_compat(project, i.type_id, connector_id, None)
    if not compat.ok:
        raise EditError(compat.why)
    c = project.connectors[connector_id]
    if c.unit_id != end.unit_id:
        raise EditError(f"{connector_id} is not a connector of {end.unit_id}.")
    eps = [
        Endpoint(unit_id=end.unit_id, connector_id=connector_id, auto=False) if k == index else e
        for k, e in enumerate(i.endpoints)
    ]
    return [Put("interfaces", evolve(i, endpoints=eps))]


def ops_set_connector_part(project: Project, connector_id: str, part_id: str) -> list[Op]:
    c = project.connectors[connector_id]
    part = project.parts.get(part_id)
    if part is None or part.category != "connector":
        raise EditError(f"'{part_id}' is not a connector part in the library.")
    if part.pin_count is not None and len(c.pins) > part.pin_count:
        raise EditError(
            f"{connector_id} has {len(c.pins)} pins but {part_id} only has {part.pin_count}."
        )
    return [Put("connectors", evolve(c, part_id=part_id))]


def ops_update_interface(project: Project, interface_id: str, **changes: object) -> list[Op]:
    """Change plain fields (name, redundancy, max_current_a, voltage_v, requirement_id, notes)."""
    allowed = {
        "name",
        "redundancy",
        "max_current_a",
        "voltage_v",
        "requirement_id",
        "notes",
        "flow",
    }
    bad = set(changes) - allowed
    if bad:
        raise EditError(f"These interface fields cannot be changed here: {', '.join(sorted(bad))}.")
    return [Put("interfaces", evolve(project.interfaces[interface_id], **changes))]


def ops_update_unit(project: Project, unit_id: str, **changes: object) -> list[Op]:
    allowed = {"name", "side", "notes", "mass_relevant"}
    bad = set(changes) - allowed
    if bad:
        raise EditError(f"These unit fields cannot be changed here: {', '.join(sorted(bad))}.")
    return [Put("units", evolve(project.units[unit_id], **changes))]


def signal_names(project: Project) -> list[str]:
    """Signal names (PWR, RTN, CANH ...), sorted: those of the interface types the project's
    interfaces use, or of all interface types while no interface exists yet."""
    used = {i.type_id for i in project.interfaces.values()}
    types = [t for t in project.interface_types.values() if t.id in used] or list(
        project.interface_types.values()
    )
    return sorted({sig.name for t in types for sig in t.signals})


def wire_colour_map(project: Project) -> dict[str, str]:
    """The wire colour set for each signal name (`generation.wire_colour_by_signal`), if any."""
    cfg = project.config.get("generation")
    got = cfg.values.get("wire_colour_by_signal") if cfg is not None else None
    return {str(k): str(v) for k, v in got.items()} if isinstance(got, dict) else {}


def ops_set_wire_colours(project: Project, colours: dict[str, str]) -> list[Op]:
    """Ops that set the wire colour of each signal; an empty colour removes the entry. The wires
    take the colours the next time the harnesses are generated."""
    old = project.config["generation"]
    values = dict(old.values)
    kept = {k: v for k, v in sorted(colours.items()) if v}
    if kept:
        values["wire_colour_by_signal"] = kept
    else:
        values.pop("wire_colour_by_signal", None)
    if values == old.values:
        return []
    return [SetConfig(ConfigFile(name="generation", placeholder=old.placeholder, values=values))]
