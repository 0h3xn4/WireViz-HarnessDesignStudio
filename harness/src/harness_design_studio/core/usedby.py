"""Where an object is used: the interfaces, harnesses, wires and units that depend on a unit, an
interface, a library part or an interface type.

Pure functions of the project (no Qt), for the "Used in" section of the inspector. They only read
what the project says and never guess: a part is used where a connector or a wire names it, an
interface type where an interface has it. The order is fixed (interfaces, harnesses, wires, units;
natural order of the IDs inside each group), so the same project always lists the same way.
"""

from dataclasses import dataclass

from harness_design_studio.core.model import Harness, Project
from harness_design_studio.core.vcs.snapshot import carried_interfaces

KINDS = ("unit", "interface", "part", "interface_type")  # what `used_by` can be asked about
_ORDER = ("interface", "harness", "wire", "unit")


@dataclass(frozen=True)
class Use:
    """One place that uses the asked-for object."""

    kind: str  # "interface" | "harness" | "wire" | "unit"
    id: str
    via: str  # the way it is used, in plain words ("link to PCDU1", "connector J01")
    harness_id: str | None = None  # for a wire: the harness it is in


def _natural(text: str) -> tuple[tuple[int, int | str], ...]:
    out: list[tuple[int, int | str]] = []
    number = ""
    for ch in text + "\0":
        if ch.isdigit():
            number += ch
            continue
        if number:
            out.append((0, int(number)))
            number = ""
        if ch != "\0":
            out.append((1, ch.casefold()))
    return tuple(out)


def _harnesses_carrying(project: Project, interface_ids: set[str]) -> list[Harness]:
    return [
        h
        for h in sorted(project.harnesses.values(), key=lambda x: _natural(x.id))
        if interface_ids & carried_interfaces(h)
    ]


def _wires_of(project: Project, interface_ids: set[str]) -> list[Use]:
    out: list[Use] = []
    for h in project.harnesses.values():
        for w in h.wires:
            if w.interface_id in interface_ids:
                label = f"{w.signal} in {h.id}" if w.signal else f"in {h.id}"
                out.append(Use("wire", w.id, label, h.id))
    return out


def _ordered(uses: list[Use]) -> list[Use]:
    seen: set[tuple[str, str]] = set()
    unique = []
    for u in uses:
        if (u.kind, u.id) not in seen:
            seen.add((u.kind, u.id))
            unique.append(u)
    return sorted(unique, key=lambda u: (_ORDER.index(u.kind), _natural(u.id)))


def _other_end(project: Project, interface_id: str, unit_id: str) -> str:
    ends = [e.unit_id for e in project.interfaces[interface_id].endpoints if e.unit_id != unit_id]
    return ends[0] if ends else unit_id


def _unit_uses(project: Project, unit_id: str) -> list[Use]:
    if unit_id not in project.units:
        return []
    mine = {
        i.id for i in project.interfaces.values() if any(e.unit_id == unit_id for e in i.endpoints)
    }
    uses = [Use("interface", i, f"link to {_other_end(project, i, unit_id)}") for i in mine]
    uses += [
        Use("harness", h.id, "carries " + ", ".join(sorted(mine & carried_interfaces(h))))
        for h in _harnesses_carrying(project, mine)
    ]
    return uses + _wires_of(project, mine)


def _interface_uses(project: Project, interface_id: str) -> list[Use]:
    i = project.interfaces.get(interface_id)
    if i is None:
        return []
    uses = [
        Use(
            "unit",
            e.unit_id,
            "end " + ("A" if k == 0 else "B") + (f", {e.connector_id}" if e.connector_id else ""),
        )
        for k, e in enumerate(i.endpoints)
    ]
    uses += [
        Use("harness", h.id, "carries it") for h in _harnesses_carrying(project, {interface_id})
    ]
    return uses + _wires_of(project, {interface_id})


def _type_uses(project: Project, type_id: str) -> list[Use]:
    mine = {i.id for i in project.interfaces.values() if i.type_id == type_id}
    uses = [Use("interface", i, "has this type") for i in mine]
    uses += [
        Use("harness", h.id, "carries one of them") for h in _harnesses_carrying(project, mine)
    ]
    return uses + _wires_of(project, mine)


def _part_uses(project: Project, part_id: str) -> list[Use]:
    uses: list[Use] = []
    boxes = {c.id: c for c in project.connectors.values() if c.part_id == part_id}
    for c in boxes.values():
        if c.unit_id:
            uses.append(Use("unit", c.unit_id, f"connector {c.name}"))
    for i in project.interfaces.values():
        for e in i.endpoints:
            if e.connector_id in boxes:
                uses.append(Use("interface", i.id, f"connector {boxes[e.connector_id].name}"))
    for h in project.harnesses.values():
        cables = [c for c in h.connectors if c.part_id == part_id]
        if cables:
            uses.append(Use("harness", h.id, "connector " + ", ".join(c.name for c in cables)))
        for w in h.wires:
            if w.part_id == part_id:
                uses.append(Use("wire", w.id, f"wire part in {h.id}", h.id))
    return uses


def used_by(project: Project, kind: str, object_id: str) -> list[Use]:
    """The places that use `object_id` of `kind` ("unit", "interface", "part" or "interface_type");
    another kind, or an ID that does not exist, gives an empty list."""
    if kind == "unit":
        uses = _unit_uses(project, object_id)
    elif kind == "interface":
        uses = _interface_uses(project, object_id)
    elif kind == "interface_type":
        uses = _type_uses(project, object_id)
    elif kind == "part":
        uses = _part_uses(project, object_id)
    else:
        uses = []
    return _ordered(uses)
