"""Referential integrity of a project. Runs on every load, save and transaction."""

from collections import Counter
from collections.abc import Callable, Iterable
from functools import partial

from .issues import Issue
from .model import Connector, Harness, Project


def _err(code: str, message: str, object_id: str | None = None) -> Issue:
    return Issue("error", code, message, None, object_id)


def _casefold_duplicates(kind: str, ids: Iterable[str]) -> list[Issue]:
    counts = Counter(i.casefold() for i in ids)
    return [
        _err(
            "duplicate_id",
            f"Two {kind} have IDs that differ only by upper/lower case ('{k}'). "
            "Windows treats them as the same file name; rename one.",
            k,
        )
        for k, n in sorted(counts.items())
        if n > 1
    ]


def _orphan(h: Harness | None, code: str, message: str, object_id: str | None = None) -> Issue:
    """Data left behind in *generated* harnesses by a later edit is stale (warning), otherwise an error."""
    if h is not None and h.generated:
        return Issue(
            "warning",
            code,
            message + " The harness plans are outdated; generate again.",
            None,
            object_id,
        )
    return _err(code, message, object_id)


def _check_harness_lazy(
    project: Project, h: Harness, wires: Counter[str], pins: Callable[[], dict[str, frozenset[str]]]
) -> list[Issue]:
    return _check_harness(project, h, wires, pins())


_CACHE: dict[tuple[int, str], tuple[object, tuple[int, ...], list[Issue]]] = {}


def _check_connector(project: Project, c: Connector, owner: str) -> list[Issue]:
    out: list[Issue] = []
    for pin in c.pins:
        if pin.contact_part is None:
            continue
        contact = project.parts.get(pin.contact_part)
        if contact is None:
            out.append(_err("unknown_part", f"Pin '{pin.id}' of connector '{c.id}' uses the contact '{pin.contact_part}', which is not in the parts library.", c.id))  # fmt: skip
        elif contact.category != "contact":
            out.append(_err("wrong_part_category", f"Pin '{pin.id}' of connector '{c.id}' uses '{pin.contact_part}' as its contact, which is not a contact part.", c.id))  # fmt: skip
    part = project.parts.get(c.part_id)
    if part is None:
        out.append(
            _err(
                "unknown_part",
                f"Connector '{c.id}' uses part '{c.part_id}', which is not in the parts library.",
                c.id,
            )
        )
    elif part.category != "connector":
        out.append(
            _err("wrong_part_category", f"Connector '{c.id}' uses '{c.part_id}', which is not a "
                 "connector part.", c.id)
        )  # fmt: skip
    elif part.pin_count is not None and len(c.pins) > part.pin_count:
        out.append(
            _err(
                "too_many_pins",
                f"Connector '{c.id}' has {len(c.pins)} pins but part '{part.id}' only has "
                f"{part.pin_count}.",
                c.id,
            )
        )
    if c.role == "box":
        if c.unit_id is None or c.unit_id not in project.units:
            out.append(
                _err(
                    "unknown_unit",
                    f"Box connector '{c.id}' does not belong to an existing unit.",
                    c.id,
                )
            )
        if owner != "project":
            out.append(_err("box_in_harness", f"Box connector '{c.id}' is stored inside harness '{owner}'.", c.id))  # fmt: skip
    else:
        if c.unit_id is not None:
            out.append(_err("cable_connector_has_unit", f"Connector '{c.id}' is not a box connector but names a unit.", c.id))  # fmt: skip
        if owner == "project":
            out.append(_err("cable_connector_outside_harness", f"Connector '{c.id}' is a cable/in-line connector and must belong to a harness.", c.id))  # fmt: skip
    if c.mates_with is not None and c.mates_with not in project.connectors:
        owner_h = project.harnesses.get(owner)
        out.append(
            _orphan(
                owner_h,
                "unknown_mate",
                f"Connector '{c.id}' mates with '{c.mates_with}', which does not exist.",
                c.id,
            )
        )
    out.extend(
        Issue(
            "warning",
            "unknown_carried_type",
            f"Connector '{c.id}' is meant for interface type '{t}', which does not exist.",
            None,
            c.id,
        )  # fmt: skip
        for t in c.carries
        if t not in project.interface_types
    )
    for pin in c.pins:
        if pin.interface_id is not None and pin.interface_id not in project.interfaces:
            out.append(Issue("warning", "orphan_pin_assignment", f"Pin {pin.id} of '{c.id}' was allocated for interface '{pin.interface_id}', which no longer exists. Generate again to release it.", None, c.id))  # fmt: skip
    pin_counts = Counter(p.id for p in c.pins)
    out.extend(
        _err("duplicate_pin", f"Connector '{c.id}' lists pin '{pid}' more than once.", c.id)
        for pid, n in sorted(pin_counts.items())
        if n > 1
    )
    return out


def _check_harness(
    project: Project, h: Harness, all_wires: Counter[str], box_pins: dict[str, frozenset[str]]
) -> list[Issue]:
    out: list[Issue] = []
    local = {c.id: c for c in h.connectors}
    pins_of = {**box_pins, **{cid: frozenset(p.id for p in c.pins) for cid, c in local.items()}}
    if len(local) != len(h.connectors):
        out.append(
            _err("duplicate_id", f"Harness '{h.id}' lists the same connector ID twice.", h.id)
        )
    reachable = {**project.connectors, **local}
    wire_ids = {w.id for w in h.wires}
    for w in h.wires:
        if all_wires[w.id] > 1:
            out.append(_err("duplicate_id", f"Wire ID '{w.id}' is used more than once in the project.", w.id))  # fmt: skip
        for cid, pin in ((w.from_connector, w.from_pin), (w.to_connector, w.to_pin)):
            conn = reachable.get(cid)
            if conn is None:
                out.append(_err("dangling_wire", f"Wire '{w.id}' ends on connector '{cid}', which does not exist (or is not part of harness '{h.id}').", w.id))  # fmt: skip
            elif pin not in pins_of[cid]:
                out.append(_err("dangling_wire", f"Wire '{w.id}' ends on pin '{pin}' of connector '{cid}', but that pin does not exist.", w.id))  # fmt: skip
        if (w.from_connector, w.from_pin) == (w.to_connector, w.to_pin):
            out.append(_err("wire_to_itself", f"Wire '{w.id}' starts and ends on the same pin ('{w.from_pin}' of connector '{w.from_connector}'). Connect its other end to a different pin or delete the wire.", w.id))  # fmt: skip
        if w.part_id is not None:
            part = project.parts.get(w.part_id)
            if part is None or part.category != "wire":
                out.append(_err("unknown_part", f"Wire '{w.id}' uses '{w.part_id}', which is not a wire part in the library.", w.id))  # fmt: skip
        if w.interface_id is not None and w.interface_id not in project.interfaces:
            out.append(_orphan(h, "unknown_interface", f"Wire '{w.id}' traces to interface '{w.interface_id}', which does not exist.", w.id))  # fmt: skip
    for iid in h.interfaces:
        if iid not in project.interfaces:
            out.append(_orphan(h, "unknown_interface", f"Harness '{h.id}' lists interface '{iid}', which does not exist.", h.id))  # fmt: skip
    groups = [(g.id, g.wire_ids) for g in h.shields]
    groups += [(g.id, g.wire_ids) for g in h.splices]
    for gid, members in groups:
        missing = sorted(set(members) - wire_ids)
        if missing:
            out.append(_err("dangling_wire", f"'{gid}' in harness '{h.id}' refers to wires that do not exist: {', '.join(missing)}.", gid))  # fmt: skip
    nodes = set(local) | {b.id for b in h.branch_points}
    for s in h.segments:
        for node in (s.from_node, s.to_node):
            if node not in nodes:
                out.append(_err("dangling_segment", f"Segment '{s.id}' in harness '{h.id}' ends at '{node}', which is not a connector or branch point of this harness.", s.id))  # fmt: skip
    wire_or_connector = wire_ids | set(local)
    for a in h.accessories:
        if a.part_id is not None and a.part_id not in project.parts:
            out.append(_err("unknown_part", f"Accessory '{a.id}' in harness '{h.id}' uses part '{a.part_id}', which is not in the parts library.", a.id))  # fmt: skip
        if a.target is not None and a.target not in wire_or_connector:
            out.append(_err("dangling_accessory", f"Accessory '{a.id}' in harness '{h.id}' belongs to '{a.target}', which is not a connector or a wire of this harness.", a.id))  # fmt: skip
    for kind, ids in (
        ("accessories", [a.id for a in h.accessories]),
        ("shield groups", [s.id for s in h.shields]),
        ("splices", [s.id for s in h.splices]),
        ("segments", [s.id for s in h.segments]),
        ("branch points", [b.id for b in h.branch_points]),
    ):
        for dup, n in sorted(Counter(ids).items()):
            if n > 1:
                out.append(_err("duplicate_id", f"Harness '{h.id}' has {n} {kind} with ID '{dup}'.", dup))  # fmt: skip
    return out


def _check_parts_and_records(project: Project) -> list[Issue]:
    """Parts that mate with nothing real, and release records that belong to no harness."""
    out: list[Issue] = []
    for part in project.parts.values():
        mate = part.mates_with
        if mate is not None and (mate == part.id or mate not in project.parts):
            what = "itself" if mate == part.id else f"'{mate}', which is not in the parts library"
            out.append(_err("unknown_mate_part", f"Part '{part.id}' mates with {what}.", part.id))
    for b in project.baselines.values():
        if b.harness_id not in project.harnesses:
            out.append(_err("unknown_harness", f"Baseline '{b.id}' belongs to harness '{b.harness_id}', which does not exist.", b.id))  # fmt: skip
        if b.id != f"{b.harness_id}.{b.revision}":
            out.append(_err("baseline_id_mismatch", f"Baseline '{b.id}' is not called '{b.harness_id}.{b.revision}', as its harness and revision say.", b.id))  # fmt: skip
    out.extend(
        Issue(
            "warning",
            "unknown_harness",
            f"Change log entry '{e.id}' is about harness '{e.harness_id}', which no longer exists.",
            None,
            e.id,
        )  # fmt: skip
        for e in project.changelog.values()
        if e.harness_id not in project.harnesses
    )
    return out


def check_integrity(project: Project) -> list[Issue]:
    """Return every consistency problem; an empty list means the model is internally consistent."""
    out: list[Issue] = []
    for kind, ids in (
        ("units", project.units), ("interfaces", project.interfaces),
        ("interface types", project.interface_types), ("parts", project.parts),
        ("harnesses", project.harnesses), ("baselines", project.baselines),
    ):  # fmt: skip
        out.extend(_casefold_duplicates(kind, ids))
    out.extend(_check_parts_and_records(project))
    all_connectors = [c.id for c in project.connectors.values()]
    all_connectors += [c.id for h in project.harnesses.values() for c in h.connectors]
    out.extend(_casefold_duplicates("connectors", set(all_connectors)))
    for cid, n in sorted(Counter(all_connectors).items()):
        if n > 1:
            out.append(_err("duplicate_id", f"Connector ID '{cid}' is used {n} times; connector IDs must be unique across the whole project.", cid))  # fmt: skip

    for t in project.interface_types.values():
        names = Counter(s.name for s in t.signals)
        out.extend(
            _err("duplicate_signal", f"Interface type '{t.id}' defines signal '{n}' twice.", t.id)
            for n, c in sorted(names.items())
            if c > 1
        )
    for i in project.interfaces.values():
        if i.type_id not in project.interface_types:
            out.append(_err("unknown_interface_type", f"Interface '{i.id}' uses interface type '{i.type_id}', which does not exist.", i.id))  # fmt: skip
        if len(i.endpoints) < 2:
            out.append(_err("too_few_endpoints", f"Interface '{i.id}' connects fewer than two units.", i.id))  # fmt: skip
        for e in i.endpoints:
            if e.unit_id not in project.units:
                out.append(_err("unknown_unit", f"Interface '{i.id}' refers to unit '{e.unit_id}', which does not exist.", i.id))  # fmt: skip
            if e.connector_id is not None:
                conn = project.connectors.get(e.connector_id)
                if conn is None or conn.unit_id != e.unit_id:
                    out.append(_err("bad_endpoint_connector", f"Interface '{i.id}' uses connector '{e.connector_id}', which is not a connector of unit '{e.unit_id}'.", i.id))  # fmt: skip
    out.extend(
        Issue(
            "warning",
            "orphan_placement",
            f"A diagram position exists for '{pid}', which is not a unit.",
            None,
            pid,
        )
        for pid in sorted(set(project.placements) - set(project.units))
    )
    wire_counts = Counter(w.id for h in project.harnesses.values() for w in h.wires)
    # Results per connector and harness are reused while the objects (immutable) and everything
    # they are checked against are unchanged; this keeps an edit at stress size well under 100 ms.
    token = (
        hash(frozenset(project.units)),
        hash(frozenset(map(id, project.connectors.values()))),
        hash(frozenset(project.interfaces)),
        hash(frozenset((p.id, p.category, p.pin_count) for p in project.parts.values())),
        hash(frozenset(k for k, n in wire_counts.items() if n > 1)),
        hash(frozenset(project.interface_types)),
        hash(frozenset(h.id for h in project.harnesses.values() if h.generated)),
    )
    seen: dict[tuple[int, str], tuple[object, tuple[int, ...], list[Issue]]] = {}

    def cached(obj: object, owner: str, compute: Callable[[], list[Issue]]) -> list[Issue]:
        key = (id(obj), owner)
        hit = _CACHE.get(key)
        if hit is None or hit[0] is not obj or hit[1] != token:
            hit = (obj, token, compute())
        seen[key] = hit
        return hit[2]

    for c in project.connectors.values():
        out.extend(cached(c, "project", partial(_check_connector, project, c, "project")))
    box_pins: dict[str, frozenset[str]] | None = None

    def pins() -> dict[str, frozenset[str]]:
        nonlocal box_pins
        if box_pins is None:
            box_pins = {
                cid: frozenset(p.id for p in c.pins) for cid, c in project.connectors.items()
            }
        return box_pins

    for h in project.harnesses.values():
        for c in h.connectors:
            out.extend(cached(c, h.id, partial(_check_connector, project, c, h.id)))
        out.extend(
            cached(h, "harness", partial(_check_harness_lazy, project, h, wire_counts, pins))
        )
    _CACHE.clear()
    _CACHE.update(seen)
    return out
