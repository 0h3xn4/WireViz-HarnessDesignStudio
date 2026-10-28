"""What a baseline stores: one harness and the design objects it depends on."""

from typing import Any

from harness_design_studio.core.model import ConfigFile, Harness, Link, Project, Snapshot, evolve

# What a release freezes, besides the harness itself (docs/FILE_FORMAT.md, "What a release freezes").
# Configuration that checks and outputs of an existing harness read; the rest (segmentation,
# naming, and the generation values that only decide how new harnesses are made) stays editable.
FROZEN_CONFIG_FILES = ("derating", "emc", "segregation", "titleblock")
FROZEN_GENERATION_KEYS = (
    "conductor_resistivity_ohm_m",
    "mass_margin_fraction",
    "power_return_gap_pins",
    "shield_end_a",
    "shield_end_b",
    "test_continuity_max_ohm",
    "test_isolation_min_mohm",
    "test_isolation_voltage_v",
)  # fmt: skip


def normalize(h: Harness) -> Harness:
    """Lists in a fixed order (by ID), so equal harnesses compare equal however they were built."""
    return evolve(
        h,
        connectors=sorted(h.connectors, key=lambda x: x.id),
        wires=sorted(h.wires, key=lambda x: x.id),
        splices=sorted(h.splices, key=lambda x: x.id),
        shields=sorted(h.shields, key=lambda x: x.id),
        branch_points=sorted(h.branch_points, key=lambda x: x.id),
        segments=sorted(h.segments, key=lambda x: x.id),
        interfaces=sorted(h.interfaces),
    )


def carried_interfaces(h: Harness) -> set[str]:
    return {w.interface_id for w in h.wires if w.interface_id} | set(h.interfaces)


def wire_pins(h: Harness) -> dict[str, set[str]]:
    """Box connector ID -> the IDs of its pins that the wires of the harness reach (1.9.0). A
    wire ends on a cable connector of the harness; that connector plugs into a box connector
    (`mates_with`) and its pin has the same ID as the box pin. A hand-made harness or one made
    from a link has no interface to say which pins it uses, so its wires say it."""
    plug = {c.id: c.mates_with for c in h.connectors if c.mates_with}
    out: dict[str, set[str]] = {}
    for w in h.wires:
        for connector, pin in ((w.from_connector, w.from_pin), (w.to_connector, w.to_pin)):
            if connector in plug:
                out.setdefault(plug[connector], set()).add(pin)
    return out


def _box_ids(h: Harness, interfaces: list[Any]) -> set[str]:
    boxes = {c.mates_with for c in h.connectors if c.mates_with}
    return boxes | {e.connector_id for i in interfaces for e in i.endpoints if e.connector_id}


def locked_pins(project: Project, h: Harness) -> dict[str, set[str]]:
    """Box connector ID -> its pins that a release of `h` freezes: the pins that carry an
    interface of the harness (allocated by Generate) and the pins its wires reach (1.9.0)."""
    carried = carried_interfaces(h)
    out = {
        c.id: {p.id for p in c.pins if p.interface_id in carried}
        for c in project.connectors.values()
        if any(p.interface_id in carried for p in c.pins)
    }
    for box, ids in wire_pins(h).items():
        if box in project.connectors:
            out.setdefault(box, set()).update(ids)
    return out


def used_part_ids(project: Project, h: Harness) -> set[str]:
    """Parts a harness depends on: its connectors, its wires, the contacts on its pins and its
    accessories, the box connectors it plugs into (or that carry its interfaces), and the
    counterpart part each connector part names."""
    interfaces = [
        project.interfaces[i] for i in sorted(carried_interfaces(h)) if i in project.interfaces
    ]
    ids = {c.part_id for c in h.connectors} | {w.part_id for w in h.wires if w.part_id}
    ids |= {p.contact_part for c in h.connectors for p in c.pins if p.contact_part}  # 1.7.0
    ids |= {a.part_id for a in h.accessories if a.part_id}  # 1.7.0
    ids |= {
        project.connectors[b].part_id for b in _box_ids(h, interfaces) if b in project.connectors
    }
    ids |= {
        part.mates_with
        for pid in ids
        if (part := project.parts.get(pid)) is not None and part.mates_with
    }
    return ids


def used_interface_type_ids(project: Project, h: Harness) -> set[str]:
    """Interface types of the interfaces a harness carries."""
    return {project.interfaces[i].type_id for i in carried_interfaces(h) if i in project.interfaces}


def frozen_values(name: str, config: ConfigFile | None) -> dict[str, Any] | None:
    """The part of one configuration file a release freezes, or None if the file is not frozen
    (or missing). The `placeholder` flag is not part of it: it records a review, not a value."""
    if config is None:
        return None
    if name in FROZEN_CONFIG_FILES:
        return dict(config.values)
    if name == "generation":
        return {k: config.values[k] for k in FROZEN_GENERATION_KEYS if k in config.values}
    return None


def frozen_config(project: Project) -> dict[str, dict[str, Any]]:
    """The configuration values a release freezes (see FROZEN_*), by file name."""
    out: dict[str, dict[str, Any]] = {}
    for name in sorted(project.config):
        values = frozen_values(name, project.config[name])
        if values is not None:
            out[name] = values
    return out


def snapshot_for(project: Project, h: Harness) -> Snapshot:
    interfaces = [
        project.interfaces[i] for i in sorted(carried_interfaces(h)) if i in project.interfaces
    ]
    units = sorted(
        {e.unit_id for i in interfaces for e in i.endpoints if e.unit_id in project.units}
    )
    boxes = _box_ids(h, interfaces)
    related = related_ids(project, h)
    return Snapshot(
        units=[project.units[u] for u in units],
        interfaces=interfaces,
        connectors=[project.connectors[c] for c in sorted(boxes) if c in project.connectors],
        harnesses=[normalize(h)],
        parts=[project.parts[p] for p in sorted(used_part_ids(project, h)) if p in project.parts],
        interface_types=[
            project.interface_types[t]
            for t in sorted(used_interface_type_ids(project, h))
            if t in project.interface_types
        ],
        config=frozen_config(project),
        waivers=[
            w
            for _, w in sorted(project.waivers.items())
            if w.object_id in related or w.object_id.split(".")[0] in related
        ],
        links=links_of(project, h) or None,  # None (left out of the file) when it has none
    )


def links_of(project: Project, h: Harness) -> list[Link]:
    """The links the harness was made from (M2), by ID."""
    return [x for _, x in sorted(project.links.items()) if x.harness_id == h.id]


def related_ids(project: Project, h: Harness) -> set[str]:
    """Every object ID that belongs to the harness (for scoping verifier and rule findings)."""
    ids = (
        {h.id} | {c.id for c in h.connectors} | {w.id for w in h.wires} | {s.id for s in h.shields}
    )
    ids |= carried_interfaces(h)
    ids |= {c.mates_with for c in h.connectors if c.mates_with}
    ids |= {
        e.connector_id
        for i in carried_interfaces(h)
        if i in project.interfaces
        for e in project.interfaces[i].endpoints
        if e.connector_id
    }
    return ids
