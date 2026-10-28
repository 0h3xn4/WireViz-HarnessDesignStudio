"""Referential integrity of a project. Runs on every load, save and transaction."""

from collections import Counter
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from functools import partial
from typing import NamedTuple

from .issues import Issue
from .model import Connector, Harness, Project


def _warn(code: str, message: str, object_id: str | None = None) -> Issue:
    return Issue("warning", code, message, None, object_id)


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
                    f"Box connector '{c.id}' does not belong to an existing device.",
                    c.id,
                )
            )
        if owner != "project":
            out.append(_err("box_in_harness", f"Box connector '{c.id}' is stored inside harness '{owner}'.", c.id))  # fmt: skip
    else:
        if c.unit_id is not None:
            out.append(_err("cable_connector_has_unit", f"Connector '{c.id}' is not a box connector but names a device.", c.id))  # fmt: skip
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


def _check_harness(project: Project, h: Harness, all_wires: Counter[str]) -> list[Issue]:
    out: list[Issue] = []
    local = {c.id: c for c in h.connectors}
    pin_sets: dict[str, frozenset[str]] = {}

    def reach(cid: str) -> Connector | None:
        """The connector a wire end names: one of the harness first, then a device connector."""
        found = local.get(cid)
        return found if found is not None else project.connectors.get(cid)

    def pins_of(cid: str, conn: Connector) -> frozenset[str]:
        if cid not in pin_sets:
            pin_sets[cid] = frozenset(p.id for p in conn.pins)
        return pin_sets[cid]

    if len(local) != len(h.connectors):
        out.append(
            _err("duplicate_id", f"Harness '{h.id}' lists the same connector ID twice.", h.id)
        )
    wire_ids = {w.id for w in h.wires}
    for w in h.wires:
        if all_wires[w.id] > 1:
            out.append(_err("duplicate_id", f"Wire ID '{w.id}' is used more than once in the project.", w.id))  # fmt: skip
        for cid, pin in ((w.from_connector, w.from_pin), (w.to_connector, w.to_pin)):
            conn = reach(cid)
            if conn is None:
                out.append(_err("dangling_wire", f"Wire '{w.id}' ends on connector '{cid}', which does not exist (or is not part of harness '{h.id}').", w.id))  # fmt: skip
            elif pin not in pins_of(cid, conn):
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


def mating_plugs(harnesses: Iterable[Harness]) -> dict[str, list[tuple[str, str]]]:
    """Box connector ID -> the cable connectors that plug into it, as (harness ID, cable connector
    ID), sorted. One entry per box connector; more than one plug on it is a mistake."""
    out: dict[str, list[tuple[str, str]]] = {}
    for h in harnesses:
        for c in h.connectors:
            if c.mates_with is not None:
                out.setdefault(c.mates_with, []).append((h.id, c.id))
    return {box: sorted(plugs) for box, plugs in sorted(out.items())}


def _words_list(items: list[str]) -> str:
    return items[0] if len(items) == 1 else f"{', '.join(items[:-1])} and {items[-1]}"


def _check_mating(project: Project) -> list[Issue]:
    """A connector of a device takes one cable plug, and a pin of it is wired by one harness
    (warnings: the project still loads, nothing is blocked; they are about what would be built)."""
    out: list[Issue] = []
    for box_id, plugs in mating_plugs(project.harnesses.values()).items():
        if len(plugs) < 2 or box_id not in project.connectors:
            continue
        names = [f"{cid} (harness {hid})" for hid, cid in plugs]
        out.append(_warn("box_connector_mated_twice", f"The device connector {box_id} has {len(plugs)} cable plugs on it: {_words_list(names)}. A connector takes one plug. Keep one harness for it, or join the wires into one harness with a branch.", box_id))  # fmt: skip
        by_cable = {cid: hid for hid, cid in plugs}
        users: dict[str, set[str]] = {}
        for h in project.harnesses.values():
            for w in h.wires:
                for cid, pin in ((w.from_connector, w.from_pin), (w.to_connector, w.to_pin)):
                    if by_cable.get(cid) == h.id:
                        users.setdefault(pin, set()).add(h.id)
        shared = sorted((p for p, hs in users.items() if len(hs) > 1), key=_pin_key)
        if shared:
            who = sorted({h for p in shared for h in users[p]})
            shown = ", ".join(shared[:6]) + (" ..." if len(shared) > 6 else "")
            out.append(_warn("box_pin_wired_twice", f"Pin{'s' if len(shared) > 1 else ''} {shown} of {box_id} {'are' if len(shared) > 1 else 'is'} wired by two harnesses ({_words_list(who)}). A pin carries one wire. Keep the wire in one harness.", box_id))  # fmt: skip
    return out


def _pin_key(pin_id: str) -> tuple[int, str]:
    return (0, pin_id.zfill(8)) if pin_id.isdigit() else (1, pin_id)


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


def _check_links(project: Project) -> list[Issue]:
    """Links (M2): both connectors exist and belong to two different devices, every paired pin
    exists, no pin is paired twice (in the link or in another link), the harness exists."""
    out: list[Issue] = []
    used: dict[tuple[str, str], str] = {}  # (connector, pin) -> the first link that pairs it
    claimed: dict[str, str] = {}  # harness -> the first link that says it made it
    for link in sorted(project.links.values(), key=lambda x: x.id):
        ends = {"a": project.connectors.get(link.a_connector), "b": project.connectors.get(link.b_connector)}  # fmt: skip
        for side, cid in (("a", link.a_connector), ("b", link.b_connector)):
            conn = ends[side]
            if conn is None or conn.role != "box":
                out.append(_err("dangling_link", f"Link '{link.id}' joins connector '{cid}', which is not a connector of a device in this project. Delete the link or choose another connector.", link.id))  # fmt: skip
        a, b = ends["a"], ends["b"]
        if link.a_connector == link.b_connector or (
            a is not None and b is not None and a.unit_id is not None and a.unit_id == b.unit_id
        ):
            out.append(_err("link_same_device", f"Link '{link.id}' joins two connectors of the same device. A link joins connectors of two different devices.", link.id))  # fmt: skip
        pins = {
            "a": {p.id for p in a.pins} if a is not None else None,
            "b": {p.id for p in b.pins} if b is not None else None,
        }
        mine: set[tuple[str, str]] = set()
        for pair in link.pairs:
            for side, cid, pid in (("a", link.a_connector, pair.a_pin), ("b", link.b_connector, pair.b_pin)):  # fmt: skip
                known = pins[side]
                if known is not None and pid not in known:
                    out.append(_err("link_pin_missing", f"Link '{link.id}' pairs pin '{pid}' of connector '{cid}', but that pin does not exist. Change the pairing or add the pin.", link.id))  # fmt: skip
                key = (cid, pid)
                if key in mine:
                    out.append(_err("link_pin_reused", f"Link '{link.id}' pairs pin '{pid}' of connector '{cid}' more than once. A pin belongs to one pair.", link.id))  # fmt: skip
                elif key in used and used[key] != link.id:
                    out.append(_err("link_pin_reused", f"Pin '{pid}' of connector '{cid}' is paired in link '{used[key]}' and in link '{link.id}'. A pin belongs to one link.", link.id))  # fmt: skip
                mine.add(key)
        for key in mine:
            used.setdefault(key, link.id)
        if link.harness_id and link.harness_id not in project.harnesses:
            out.append(_err("unknown_harness", f"Link '{link.id}' says it made harness '{link.harness_id}', which does not exist. Clear the harness of the link.", link.id))  # fmt: skip
        elif link.harness_id:
            h = project.harnesses[link.harness_id]
            if link.harness_id in claimed:
                out.append(_warn("link_harness_shared", f"Links '{claimed[link.harness_id]}' and '{link.id}' both say they made harness '{link.harness_id}'. A harness is made from one link; delete one of the links.", link.id))  # fmt: skip
            claimed.setdefault(link.harness_id, link.id)
            plugged = {c.mates_with for c in h.connectors}
            lacking = [box for box in (link.a_connector, link.b_connector) if box not in plugged]
            if lacking:
                out.append(_warn("link_harness_not_mated", f"Link '{link.id}' says it made harness '{h.id}', but {h.id} has no cable connector that plugs into {_words_list(lacking)}. Make the harness again from the link, or delete the link.", link.id))  # fmt: skip
    return out


def _connector_id_issues(project: Project) -> list[Issue]:
    """A connector ID is unique across the device connectors and the connectors of every harness."""
    out: list[Issue] = []
    all_connectors = [c.id for c in project.connectors.values()]
    all_connectors += [c.id for h in project.harnesses.values() for c in h.connectors]
    out.extend(_casefold_duplicates("connectors", set(all_connectors)))
    for cid, n in sorted(Counter(all_connectors).items()):
        if n > 1:
            out.append(_err("duplicate_id", f"Connector ID '{cid}' is used {n} times; connector IDs must be unique across the whole project.", cid))  # fmt: skip
    return out


def _type_issues(project: Project) -> list[Issue]:
    out: list[Issue] = []
    for t in project.interface_types.values():
        names = Counter(s.name for s in t.signals)
        out.extend(
            _err("duplicate_signal", f"Interface type '{t.id}' defines signal '{n}' twice.", t.id)
            for n, c in sorted(names.items())
            if c > 1
        )
    return out


def _interface_issues(project: Project) -> list[Issue]:
    out: list[Issue] = []
    for i in project.interfaces.values():
        if i.type_id not in project.interface_types:
            out.append(_err("unknown_interface_type", f"Interface '{i.id}' uses interface type '{i.type_id}', which does not exist.", i.id))  # fmt: skip
        if len(i.endpoints) < 2:
            out.append(_err("too_few_endpoints", f"Interface '{i.id}' connects fewer than two devices.", i.id))  # fmt: skip
        for e in i.endpoints:
            if e.unit_id not in project.units:
                out.append(_err("unknown_unit", f"Interface '{i.id}' refers to device '{e.unit_id}', which does not exist.", i.id))  # fmt: skip
            if e.connector_id is not None:
                conn = project.connectors.get(e.connector_id)
                if conn is None or conn.unit_id != e.unit_id:
                    out.append(_err("bad_endpoint_connector", f"Interface '{i.id}' uses connector '{e.connector_id}', which is not a connector of device '{e.unit_id}'.", i.id))  # fmt: skip
    return out


def _placement_issues(project: Project) -> list[Issue]:
    return [
        Issue(
            "warning",
            "orphan_placement",
            f"A diagram position exists for '{pid}', which is not a device.",
            None,
            pid,
        )
        for pid in sorted(set(project.placements) - set(project.units))
    ]


# The collections whose keys must differ only by more than upper/lower case, with the word the
# message uses for them.
_CASEFOLD_KINDS = (
    ("units", "units"), ("interfaces", "interfaces"), ("links", "links"),
    ("interface types", "interface_types"), ("parts", "parts"), ("harnesses", "harnesses"),
    ("baselines", "baselines"),
)  # fmt: skip


def check_integrity(project: Project) -> list[Issue]:
    """Return every consistency problem; an empty list means the model is internally consistent."""
    out: list[Issue] = []
    for kind, name in _CASEFOLD_KINDS:
        out.extend(_casefold_duplicates(kind, getattr(project, name)))
    out.extend(_check_parts_and_records(project))
    out.extend(_connector_id_issues(project))
    out.extend(_type_issues(project))
    out.extend(_interface_issues(project))
    out.extend(_placement_issues(project))
    if project.links:
        out.extend(_check_links(project))
    if project.harnesses:
        out.extend(_check_mating(project))
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
    for h in project.harnesses.values():
        for c in h.connectors:
            out.extend(cached(c, h.id, partial(_check_connector, project, c, h.id)))
        out.extend(cached(h, "harness", partial(_check_harness, project, h, wire_counts)))
    _CACHE.clear()
    _CACHE.update(seen)
    return out


# ---- the same errors, found again only where the project changed ------------------------------

ErrorKey = tuple[str, str, str | None, str | None]  # `Issue.key()` of an error
_TRACKED = (
    "parts", "units", "interface_types", "interfaces", "links", "connectors", "harnesses",
    "placements", "baselines", "changelog",
)  # fmt: skip
_MISSING = object()
_NONE: frozenset[str] = frozenset()


class _News(NamedTuple):
    """What differs from the last look: the collections with a key added, removed or replaced, and
    those with a key added or removed (only these matter to a check that asked "is there one?")."""

    reads: list[tuple[str, set[str]]]
    exists: list[tuple[str, set[str]]]


def _error_keys(issues: Iterable[Issue]) -> tuple[ErrorKey, ...]:
    return tuple(i.key() for i in issues if i.severity == "error")


@dataclass(frozen=True, slots=True)
class _Memo:
    """What the errors of one object were found against. They are still right while the object is
    the same one (entities are immutable), none of the objects it read has changed (`reads` and
    `exists`: collection -> the keys looked at) and no wire ID it looked at has become, or stopped
    being, a duplicate (`wires`)."""

    obj: object
    reads: dict[str, frozenset[str]]
    exists: dict[str, frozenset[str]]
    wires: frozenset[str]


@dataclass(slots=True)
class _Reads:
    """What a check looked at besides its own object (a superset, warnings included): `reads`
    are objects whose content mattered, `exists` are keys of which only the presence mattered."""

    reads: dict[str, set[str]] = field(default_factory=lambda: {n: set() for n in _TRACKED})
    exists: dict[str, set[str]] = field(default_factory=lambda: {n: set() for n in _TRACKED})

    def connector(self, c: Connector, owner: str) -> None:
        """What `_check_connector` looks at."""
        self.reads["parts"] |= {
            c.part_id,
            *(p.contact_part for p in c.pins if p.contact_part is not None),
        }
        if c.unit_id is not None:
            self.exists["units"].add(c.unit_id)
        if c.mates_with is not None:
            self.exists["connectors"].add(c.mates_with)
        self.reads["harnesses"].add(owner)  # its `generated` flag decides error or warning
        self.exists["interface_types"] |= set(c.carries)
        self.exists["interfaces"] |= {p.interface_id for p in c.pins if p.interface_id is not None}

    def harness(self, h: Harness) -> None:
        """What `_check_harness` looks at (the checks of its connectors are added separately)."""
        self.reads["parts"] |= {w.part_id for w in h.wires if w.part_id is not None}
        self.reads["parts"] |= {a.part_id for a in h.accessories if a.part_id is not None}
        self.reads["connectors"] |= {w.from_connector for w in h.wires}
        self.reads["connectors"] |= {w.to_connector for w in h.wires}
        self.exists["interfaces"] |= {w.interface_id for w in h.wires if w.interface_id is not None}
        self.exists["interfaces"] |= set(h.interfaces)
        self.reads["harnesses"].add(h.id)

    def frozen(self) -> tuple[dict[str, frozenset[str]], dict[str, frozenset[str]]]:
        return (
            {n: frozenset(v) for n, v in self.reads.items()},
            {n: frozenset(v) for n, v in self.exists.items()},
        )


class IntegrityTracker:
    """The errors of `check_integrity`, kept up to date edit by edit (audit A-8).

    `History.execute` used to run the whole check twice per edit (before and after) and the check
    started over whenever any connector changed. The tracker remembers which object stood under
    every key the last time it looked, finds what is different now (a pass over the keys, no
    checking), and checks again only the objects that changed or that read something that changed.
    Entities are immutable, so "the same object" means "the same content". The answer is the same
    as `Counter(i.key() for i in errors(check_integrity(project)))` after any change, including
    changes made without `History` (generation, a restore, a test); `tests/test_integrity_tracker.py`
    compares the two on generated projects and random edits. Only errors are tracked: the checks
    that can only warn (a diagram position of no device, a box connector with two plugs) are not
    run, and a test fails if one of them ever reports an error.
    """

    def __init__(self, project: Project) -> None:
        self.project = project
        self._seen: dict[str, dict[str, object]] = {name: {} for name in _TRACKED}
        self._started = False
        self._total: Counter[ErrorKey] = Counter()
        self._pieces: dict[object, tuple[ErrorKey, ...]] = {}
        self._wire_counts: Counter[str] = Counter()
        self._harness_memo: dict[str, _Memo] = {}
        self._box_memo: dict[str, _Memo] = {}
        self._interface_refs: frozenset[str] = _NONE  # connectors the interface endpoints name
        self._link_reads: frozenset[str] = _NONE  # connectors and harnesses the links look at
        self._link_harnesses: frozenset[str] = _NONE
        self.checked = 0  # objects checked again by the latest call (what the tests count)

    # ---- the answer ---------------------------------------------------------------------------

    def errors(self) -> Counter[ErrorKey]:
        """How often each error (severity, code, location, object) is present now."""
        self._sync()
        return Counter(self._total)

    # ---- bookkeeping ---------------------------------------------------------------------------

    def _set(self, name: object, keys: tuple[ErrorKey, ...]) -> None:
        old = self._pieces.get(name, ())
        if old == keys:
            return
        for k in old:
            n = self._total[k] - 1
            if n > 0:
                self._total[k] = n
            else:
                del self._total[k]
        for k in keys:
            self._total[k] += 1
        if keys:
            self._pieces[name] = keys
        else:
            self._pieces.pop(name, None)

    def _diff(self, name: str) -> tuple[set[str], set[str], dict[str, object]]:
        """(keys added, removed or replaced; keys added or removed; the old objects)."""
        now: dict[str, object] = getattr(self.project, name)
        seen = self._seen[name]
        changed: set[str] = set()
        members: set[str] = set()
        old: dict[str, object] = {}
        for key, obj in now.items():
            before = seen.get(key, _MISSING)
            if before is not obj:
                changed.add(key)
                if before is _MISSING:
                    members.add(key)
                else:
                    old[key] = before
        if len(seen) + len(members) != len(now):  # something was removed
            for key in [k for k in seen if k not in now]:
                changed.add(key)
                members.add(key)
                old[key] = seen[key]
        for key in changed:
            if key in now:
                seen[key] = now[key]
            else:
                del seen[key]
        return changed, members, old

    # ---- the pass ------------------------------------------------------------------------------

    def _sync(self) -> None:
        p = self.project
        first = not self._started
        self._started = True
        changed: dict[str, set[str]] = {}
        members: dict[str, set[str]] = {}
        olds: dict[str, dict[str, object]] = {}
        for name in _TRACKED:
            changed[name], members[name], olds[name] = self._diff(name)
        self.checked = 0

        # wire IDs: which ones are used twice (a harness that holds one reads that)
        dup_changed: set[str] = set()
        connector_ids_changed = False
        if changed["harnesses"]:
            counts = self._wire_counts
            gone: list[Harness] = []
            come: list[Harness] = []
            for key in changed["harnesses"]:
                old_h = olds["harnesses"].get(key)
                new_h = p.harnesses.get(key)
                if isinstance(old_h, Harness):
                    gone.append(old_h)
                if new_h is not None:
                    come.append(new_h)
                old_ids = (
                    tuple(c.id for c in old_h.connectors) if isinstance(old_h, Harness) else ()
                )
                new_ids = tuple(c.id for c in new_h.connectors) if new_h is not None else ()
                connector_ids_changed = connector_ids_changed or old_ids != new_ids
            touched = {w.id for h in (*gone, *come) for w in h.wires}
            was_dup = {w for w in touched if counts[w] > 1}
            for h in gone:
                for w in h.wires:
                    counts[w.id] -= 1
            for h in come:
                for w in h.wires:
                    counts[w.id] += 1
            for wire_id in touched:
                if counts[wire_id] <= 0:
                    del counts[wire_id]
            dup_changed = {w for w in touched if (counts[w] > 1) != (w in was_dup)}

        # the keys that are the same by name in several collections (case-folded)
        for kind, name in _CASEFOLD_KINDS:
            if first or members[name]:
                self._set(("keys", name), _error_keys(_casefold_duplicates(kind, getattr(p, name))))
        if first or any(changed[n] for n in ("parts", "baselines", "changelog")) or members["harnesses"]:  # fmt: skip
            self._set("records", _error_keys(_check_parts_and_records(p)))
        if first or changed["connectors"] or connector_ids_changed:
            self._set("connector ids", _error_keys(_connector_id_issues(p)))
        if first or changed["interface_types"]:
            self._set("types", _error_keys(_type_issues(p)))
        if (
            first
            or changed["interfaces"]
            or members["interface_types"]
            or members["units"]
            or not self._interface_refs.isdisjoint(changed["connectors"])
        ):
            self._set("interfaces", _error_keys(_interface_issues(p)))
            self._interface_refs = frozenset(
                e.connector_id
                for i in p.interfaces.values()
                for e in i.endpoints
                if e.connector_id is not None
            )
        if (
            first
            or changed["links"]
            or members["harnesses"]
            or not self._link_reads.isdisjoint(changed["connectors"])
            or not self._link_harnesses.isdisjoint(changed["harnesses"])
        ):
            self._set("links", _error_keys(_check_links(p)) if p.links else ())
            self._link_reads = frozenset(
                c for x in p.links.values() for c in (x.a_connector, x.b_connector)
            )
            self._link_harnesses = frozenset(x.harness_id for x in p.links.values() if x.harness_id)

        news = _News(
            [(n, keys) for n, keys in changed.items() if keys],
            [(n, keys) for n, keys in members.items() if keys],
        )
        self._refresh_boxes(news)
        self._refresh_harnesses(news, dup_changed)

    @staticmethod
    def _stale(memo: _Memo | None, obj: object, news: _News) -> bool:
        if memo is None or memo.obj is not obj:
            return True
        reads, exists = memo.reads, memo.exists
        return any(not reads[name].isdisjoint(keys) for name, keys in news.reads) or any(
            not exists[name].isdisjoint(keys) for name, keys in news.exists
        )

    def _refresh_boxes(self, news: _News) -> None:
        p = self.project
        for key in [k for k in self._box_memo if k not in p.connectors]:
            del self._box_memo[key]
            self._set(("box", key), ())
        for key, c in p.connectors.items():
            if self._stale(self._box_memo.get(key), c, news):
                seen = _Reads()
                seen.connector(c, "project")
                keys = _error_keys(_check_connector(p, c, "project"))
                self._box_memo[key] = _Memo(c, *seen.frozen(), _NONE)
                self._set(("box", key), keys)
                self.checked += 1

    def _refresh_harnesses(self, news: _News, dup_changed: set[str]) -> None:
        p = self.project
        for key in [k for k in self._harness_memo if k not in p.harnesses]:
            del self._harness_memo[key]
            self._set(("harness", key), ())
        for key, h in p.harnesses.items():
            memo = self._harness_memo.get(key)
            if self._stale(memo, h, news) or (
                dup_changed and memo is not None and not memo.wires.isdisjoint(dup_changed)
            ):
                seen = _Reads()
                seen.harness(h)
                issues: list[Issue] = []
                for c in h.connectors:
                    seen.connector(c, h.id)
                    issues.extend(_check_connector(p, c, h.id))
                issues.extend(_check_harness(p, h, self._wire_counts))
                keys = _error_keys(issues)
                wire_ids = frozenset(w.id for w in h.wires)
                self._harness_memo[key] = _Memo(h, *seen.frozen(), wire_ids)
                self._set(("harness", key), keys)
                self.checked += 1
