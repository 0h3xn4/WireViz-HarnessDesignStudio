"""What a release locks, in a form a view can show: which objects are locked and by which
harness revision, the sentence that explains it, which fields stay editable, and what releasing
a harness will lock. It only reads; the rules themselves stay in `locks.check_locks`, whose
sentences it repeats word for word (a test compares them), so a field the inspector disables
for a reason is refused for the same reason if it is edited anyway."""

from collections import defaultdict
from dataclasses import dataclass
from typing import Any, NamedTuple

from harness_design_studio.core.model import Connector, Harness, Project

from .diff import KIND_NAMES
from .locks import (
    COSMETIC_INTERFACE_FIELDS,
    COSMETIC_PART_FIELDS,
    COSMETIC_TYPE_FIELDS,
    COSMETIC_UNIT_FIELDS,
)
from .release import ReleaseError
from .snapshot import (
    FROZEN_CONFIG_FILES,
    FROZEN_GENERATION_KEYS,
    carried_interfaces,
    frozen_values,
    used_interface_type_ids,
    used_part_ids,
)

# Object kinds, named as in the diff (`diff.KIND_NAMES`): "unit", "interface", "interface_type",
# "part", "box_connector", "box_pin", "harness", "cable_connector", "cable_pin", "wire", "splice",
# "shield", "branch_point", "segment", "config".
KINDS = (
    "harness", "interface", "unit", "box_connector", "box_pin", "wire", "cable_connector",
    "cable_pin", "splice", "shield", "branch_point", "segment", "accessory", "part", "interface_type",
    "config",
)  # fmt: skip
_CHILDREN = (
    ("cable_connector", "connectors"), ("wire", "wires"), ("splice", "splices"),
    ("shield", "shields"), ("branch_point", "branch_points"), ("segment", "segments"),
    ("accessory", "accessories"),
)  # fmt: skip
# What `check_locks` compares on a box connector that is in use (besides the pins that are used).
LOCKED_CONNECTOR_FIELDS = frozenset({"part_id", "gender", "keying"})
KIND_LABELS = {**KIND_NAMES, "config": "Configuration file"}


class LockRef(NamedTuple):
    """A released harness and its revision; it compares equal to `(harness_id, revision)`."""

    harness_id: str
    revision: str


def _released(project: Project) -> list[Harness]:
    return [
        h for h in sorted(project.harnesses.values(), key=lambda x: x.id) if h.status == "released"
    ]


def _locked_pins(project: Project, h: Harness) -> dict[str, list[str]]:
    """Box connector ID -> its pins that carry an interface of the harness (those are locked)."""
    carried = carried_interfaces(h)
    return {
        c.id: [p.id for p in c.pins if p.interface_id in carried]
        for c in project.connectors.values()
        if any(p.interface_id in carried for p in c.pins)
    }


def locked_objects(project: Project) -> dict[tuple[str, str], list[LockRef]]:
    """(kind, id) -> the released harnesses (by ID) that lock it. Empty without a release.
    A box connector and a unit are locked in their design fields only (see `cosmetic_fields`)."""
    out: dict[tuple[str, str], list[LockRef]] = defaultdict(list)
    for h in _released(project):
        ref = LockRef(h.id, h.revision)

        def add(kind: str, oid: str, ref: LockRef = ref) -> None:
            if ref not in out[(kind, oid)]:
                out[(kind, oid)].append(ref)

        add("harness", h.id)
        for kind, attr in _CHILDREN:
            for child in getattr(h, attr):
                add(kind, child.id)
                if kind == "cable_connector":
                    for pin in child.pins:
                        add("cable_pin", f"{child.id}.{pin.id}")
        ifaces = sorted(i for i in carried_interfaces(h) if i in project.interfaces)
        for iid in ifaces:
            add("interface", iid)
            for e in project.interfaces[iid].endpoints:
                add("unit", e.unit_id)
        pins = _locked_pins(project, h)
        for box in sorted({c.mates_with for c in h.connectors if c.mates_with} | set(pins)):
            add("box_connector", box)
        for box, pin_ids in sorted(pins.items()):
            for pid in pin_ids:
                add("box_pin", f"{box}.{pid}")
        for pid in sorted(used_part_ids(project, h)):
            add("part", pid)
        for tid in sorted(used_interface_type_ids(project, h)):
            add("interface_type", tid)
        for name in sorted(project.config):
            if frozen_values(name, project.config[name]) is not None:
                add("config", name)
    return {k: v for k, v in out.items() if v}


def _why(ref: LockRef) -> str:
    return f"{ref.harness_id} is released (revision {ref.revision}); start a new revision to change it."


Locked = dict[tuple[str, str], list[LockRef]]


def lock_reason(
    project: Project, kind: str, object_id: str, locked: Locked | None = None
) -> str | None:
    """The sentence that says why an object cannot be changed, or None if it is not locked.
    When several released harnesses lock it, the first by ID is named, as in the refusal.
    Pass `locked` (from `locked_objects`) to ask about many objects without scanning again."""
    refs = (locked if locked is not None else locked_objects(project)).get((kind, object_id))
    if not refs:
        return None
    ref = refs[0]
    if kind == "interface":
        return f"Interface {object_id} is carried by {ref.harness_id}, which is released. " + _why(
            ref
        )
    if kind == "part":
        return f"Part {object_id} is used by {ref.harness_id}, which is released. " + _why(ref)
    if kind == "interface_type":
        return (
            f"Interface type {object_id} is used by {ref.harness_id}, which is released. "
            + _why(ref)
        )
    if kind == "unit":
        return f"Unit {object_id} is used by {ref.harness_id}, which is released. " + _why(ref)
    if kind in ("box_connector", "box_pin"):
        box = object_id.split(".", 1)[0]
        return f"Connector {box} is used by {ref.harness_id}, which is released. " + _why(ref)
    if kind == "config":
        names = ", ".join(r.harness_id for r in refs[:3])
        names += f" and {len(refs) - 3} more" if len(refs) > 3 else ""
        return (
            f"Configuration '{object_id}' is used by the checks of the released harness(es) "
            f"{names}. Start a new revision of them to change it."
        )
    return _why(ref)  # the harness, and everything inside it (wires, cable connectors, pins ...)


def cosmetic_fields(kind: str) -> frozenset[str]:
    """The fields of an object kind that may change after a release (`check_locks` lets them
    through). Everything else on a locked object is refused; kinds not listed have none."""
    named = {
        "interface": COSMETIC_INTERFACE_FIELDS,
        "unit": COSMETIC_UNIT_FIELDS,
        "part": COSMETIC_PART_FIELDS,
        "interface_type": COSMETIC_TYPE_FIELDS,
    }
    if kind in named:
        return frozenset(named[kind])
    if kind == "box_connector":
        return frozenset(Connector.model_fields) - LOCKED_CONNECTOR_FIELDS - {"id", "pins"}
    return frozenset()


def config_key_locked(project: Project, file: str, key: str, locked: Locked | None = None) -> bool:
    """Does a release freeze this value? A file that is frozen as a whole freezes every key; of
    `generation` only the values that checks and outputs read (`snapshot.FROZEN_GENERATION_KEYS`)."""
    if ("config", file) not in (locked if locked is not None else locked_objects(project)):
        return False
    return file in FROZEN_CONFIG_FILES or (file == "generation" and key in FROZEN_GENERATION_KEYS)


def field_lock_reason(
    project: Project, kind: str, object_id: str, field: str, locked: Locked | None = None
) -> str | None:
    """Why this one field cannot be edited (None: it can). A cosmetic field of a locked object can."""
    if locked is None:
        locked = locked_objects(project)
    if kind == "config":
        if config_key_locked(project, object_id, field, locked):
            return lock_reason(project, kind, object_id, locked)
        return None
    if field in cosmetic_fields(kind):
        return None
    return lock_reason(project, kind, object_id, locked)


# ---- what a release will lock --------------------------------------------------------------------


@dataclass(frozen=True)
class ConfigLock:
    """A configuration file a release freezes, with the frozen values."""

    name: str
    placeholder: bool  # still marked as a placeholder: the values are not reviewed
    values: dict[str, Any]
    unset: tuple[str, ...]  # frozen keys that have no value yet (released as "not set")


@dataclass(frozen=True)
class ReleaseLocks:
    harness_id: str
    revision: str
    wires: tuple[str, ...]
    cable_connectors: tuple[str, ...]
    cable_pins: tuple[str, ...]  # "connector.pin"
    box_connectors: tuple[str, ...]
    box_pins: tuple[str, ...]  # "connector.pin": the pins that carry the harness's interfaces
    interfaces: tuple[str, ...]
    units: tuple[str, ...]
    parts: tuple[str, ...]
    interface_types: tuple[str, ...]
    config_files: tuple[ConfigLock, ...]

    @property
    def placeholder_files(self) -> tuple[str, ...]:
        return tuple(sorted(c.name for c in self.config_files if c.placeholder))

    def counts(self) -> dict[str, int]:
        return {
            "wires": len(self.wires),
            "pins": len(self.cable_pins) + len(self.box_pins),
            "interfaces": len(self.interfaces),
            "parts": len(self.parts),
            "interface_types": len(self.interface_types),
            "config_files": len(self.config_files),
        }


def release_locks(project: Project, harness_id: str) -> ReleaseLocks:
    """What releasing `harness_id` locks, from the design as it is now."""
    h = project.harnesses.get(harness_id)
    if h is None:
        raise ReleaseError(f"There is no harness {harness_id}.")
    ifaces = sorted(i for i in carried_interfaces(h) if i in project.interfaces)
    pins = _locked_pins(project, h)
    config = []
    for name in sorted(project.config):
        frozen = frozen_values(name, project.config[name])
        if frozen is not None:
            config.append(
                ConfigLock(
                    name,
                    project.config[name].placeholder,
                    dict(frozen),
                    tuple(sorted(k for k, v in frozen.items() if v is None)),
                )
            )
    return ReleaseLocks(
        harness_id=h.id,
        revision=h.revision,
        wires=tuple(sorted(w.id for w in h.wires)),
        cable_connectors=tuple(sorted(c.id for c in h.connectors)),
        cable_pins=tuple(sorted(f"{c.id}.{p.id}" for c in h.connectors for p in c.pins)),
        box_connectors=tuple(
            sorted({c.mates_with for c in h.connectors if c.mates_with} | set(pins))
        ),
        box_pins=tuple(sorted(f"{b}.{p}" for b, ids in pins.items() for p in ids)),
        interfaces=tuple(ifaces),
        units=tuple(sorted({e.unit_id for i in ifaces for e in project.interfaces[i].endpoints})),
        parts=tuple(sorted(used_part_ids(project, h))),
        interface_types=tuple(sorted(used_interface_type_ids(project, h))),
        config_files=tuple(config),
    )
