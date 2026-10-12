"""Locks on released items. A released harness, the interfaces it carries, the box pins it uses,
the parts and interface types it uses and the configuration its checks read cannot be changed or
deleted; the only way forward is a new revision (vcs.release)."""

from harness_design_studio.core.commands import Delete, DeleteConfig, Op, Put, SetConfig
from harness_design_studio.core.errors import TransactionError
from harness_design_studio.core.model import (
    Connector,
    Harness,
    InterfaceInstance,
    InterfaceType,
    Part,
    Project,
    Unit,
)

from .snapshot import (
    carried_interfaces,
    frozen_values,
    used_interface_type_ids,
    used_part_ids,
)

_META = {"status", "revision", "checker", "approver", "released_on"}
COSMETIC_INTERFACE_FIELDS = {"name", "notes", "requirement_id"}  # may change after release
COSMETIC_UNIT_FIELDS = {"name", "notes", "zone"}  # may change after release
COSMETIC_PART_FIELDS = {"notes"}  # may change after release
COSMETIC_TYPE_FIELDS = {"name", "notes"}  # may change after release


def interface_design(i: InterfaceInstance) -> dict[str, object]:
    """The fields of an interface that decide its wires (everything except labels and notes)."""
    return i.model_dump(exclude=COSMETIC_INTERFACE_FIELDS)


def _is_new_revision(old: Harness, new: Harness) -> bool:
    """A released harness may only be replaced by its next revision: same content, status draft."""
    return (
        new.revision != old.revision
        and new.status == "draft"
        and new.model_dump(exclude=_META) == old.model_dump(exclude=_META)
    )


def _pins_equal(a: Connector, b: Connector, locked: set[str]) -> bool:
    ap = {p.id: p for p in a.pins if p.interface_id in locked}
    bp = {p.id: p for p in b.pins if p.id in ap}
    return ap == bp and (a.part_id, a.gender, a.keying) == (b.part_id, b.gender, b.keying)


def unit_design(u: Unit) -> dict[str, object]:
    """The fields of a unit that the released wiring depends on (not its label, notes or zone)."""
    return u.model_dump(exclude=COSMETIC_UNIT_FIELDS)


def part_design(p: Part) -> dict[str, object]:
    """The fields of a part that the released drawings, lists and checks depend on."""
    return p.model_dump(exclude=COSMETIC_PART_FIELDS)


def type_design(t: InterfaceType) -> dict[str, object]:
    """The fields of an interface type that decide the wires of its interfaces."""
    return t.model_dump(exclude=COSMETIC_TYPE_FIELDS)


def _names(owners: list[str]) -> str:
    return ", ".join(owners[:3]) + (f" and {len(owners) - 3} more" if len(owners) > 3 else "")


def check_locks(project: Project, ops: list[Op]) -> None:
    """Raise `TransactionError` if `ops` would change something released."""
    record_problems: list[str] = []
    for op in ops:
        if isinstance(op, Delete) and op.collection in ("baselines", "changelog"):
            record_problems.append(
                f"The {'baseline' if op.collection == 'baselines' else 'change log entry'} {op.key} is part of the release record and cannot be deleted."
            )
        elif isinstance(op, Put) and op.collection in ("baselines", "changelog"):
            old = getattr(project, op.collection).get(str(getattr(op.obj, "id", "")))
            if old is not None and old != op.obj:
                record_problems.append(
                    f"The release record {getattr(op.obj, 'id', '')} cannot be changed."
                )
    if record_problems:
        raise TransactionError(
            "This change was blocked because it touches the release record.",
            sorted(set(record_problems)),
        )
    released = {h.id: h for h in project.harnesses.values() if h.status == "released"}
    if not released:
        return
    owner = {i: h.id for h in released.values() for i in carried_interfaces(h)}
    box_owner = {
        c.mates_with: h.id for h in released.values() for c in h.connectors if c.mates_with
    }
    locked_ifaces = set(owner)
    unit_owner = {
        e.unit_id: owner[i]
        for i in sorted(locked_ifaces)
        if i in project.interfaces
        for e in project.interfaces[i].endpoints
    }
    part_owner: dict[str, str] = {}
    type_owner: dict[str, str] = {}
    if any(
        isinstance(op, Put | Delete) and op.collection in ("parts", "interface_types") for op in ops
    ):
        for rid in sorted(released, reverse=True):  # the first released harness (by ID) is named
            for pid in used_part_ids(project, released[rid]):
                part_owner[pid] = rid
            for tid in used_interface_type_ids(project, released[rid]):
                type_owner[tid] = rid
    problems: list[str] = []

    def why(hid: str) -> str:
        return f"{hid} is released (revision {released[hid].revision}); start a new revision to change it."

    for op in ops:
        if isinstance(op, SetConfig | DeleteConfig):
            name = op.config.name if isinstance(op, SetConfig) else op.name
            new_cfg = op.config if isinstance(op, SetConfig) else None
            if frozen_values(name, new_cfg) != frozen_values(name, project.config.get(name)):
                names = _names(sorted(released))
                problems.append(
                    f"Configuration '{name}' is used by the checks of the released harness(es) "
                    f"{names}. Start a new revision of them to change it."
                )
            continue
        if not isinstance(op, Put | Delete):
            continue
        key = op.key if isinstance(op, Delete) else str(getattr(op.obj, "id", ""))
        new = None if isinstance(op, Delete) else op.obj
        if op.collection == "harnesses" and key in released:
            if not (isinstance(new, Harness) and _is_new_revision(released[key], new)):
                problems.append(why(key))
        elif op.collection == "interfaces" and key in locked_ifaces:
            old_i = project.interfaces.get(key)
            changed = (
                not isinstance(new, InterfaceInstance)
                or old_i is None
                or interface_design(new) != interface_design(old_i)
            )
            if changed:
                problems.append(
                    f"Interface {key} is carried by {owner[key]}, which is released. "
                    + why(owner[key])
                )
        elif op.collection == "parts" and key in part_owner:
            old_p = project.parts.get(key)
            if not isinstance(new, Part) or old_p is None or part_design(new) != part_design(old_p):
                problems.append(
                    f"Part {key} is used by {part_owner[key]}, which is released. "
                    + why(part_owner[key])
                )
        elif op.collection == "interface_types" and key in type_owner:
            old_t = project.interface_types.get(key)
            if (
                not isinstance(new, InterfaceType)
                or old_t is None
                or type_design(new) != type_design(old_t)
            ):
                problems.append(
                    f"Interface type {key} is used by {type_owner[key]}, which is released. "
                    + why(type_owner[key])
                )
        elif op.collection == "units" and key in unit_owner:
            old_u = project.units.get(key)
            if not isinstance(new, Unit) or old_u is None or unit_design(new) != unit_design(old_u):
                problems.append(
                    f"Unit {key} is used by {unit_owner[key]}, which is released. "
                    + why(unit_owner[key])
                )
        elif op.collection == "connectors":
            old_c = project.connectors.get(key)
            if old_c is None:
                continue
            mine = {p.interface_id for p in old_c.pins if p.interface_id in locked_ifaces}
            hid = box_owner.get(key) or next((owner[i] for i in mine if i), None)
            if hid and not (
                isinstance(new, Connector) and _pins_equal(old_c, new, {i for i in mine if i})
            ):
                problems.append(f"Connector {key} is used by {hid}, which is released. " + why(hid))
    if problems:
        raise TransactionError(
            "This change was blocked because it touches released items.", sorted(set(problems))
        )
