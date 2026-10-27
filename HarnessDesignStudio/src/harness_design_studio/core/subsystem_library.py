"""A subsystem library file: a set of devices with the connections between them, kept outside any
project, so that a subsystem that was designed once (a star tracker pair, a power chain) is added to
the next project in one step (workshop feedback M4, D-175).

    data = export_subsystem(project, ["OBC1", "RW1"], "Wheel drive", "OBC and a wheel")
    write_subsystem(path, data)
    plan = plan_subsystem_import(project, read_subsystem(path))      # a preview and the ops

The file is JSON (`harness-subsystem-library`, version 1) and holds ONE subsystem: its `name`, a
`description`, optional `notes`, its `devices` (the same record as a device library file: the unit,
its box connectors with every pin), the `parts` and `interface_types` those connectors name, and its
`connections` (the links of `logical/links.json`, written with the connector IDs of the file, so a
connection means the same thing when the devices get other IDs in a project). The links that leave
the subsystem (the other end is a device that is not in it) are left out.

Importing adds the devices (a taken ID becomes the next free one, as in `plan_device_import`), sets
the subsystem of every added device to the name of the subsystem, adds the connections between the
new connectors, and places the devices in a free place of one lane. It never changes an object of
the project. A subsystem is all or nothing: when one device or one connection cannot be added the
plan has no ops and says which, in plain words. Nothing is written until the plan is applied as one
undo step.
"""

import json
import stat
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pydantic import TypeAdapter, ValidationError

from harness_design_studio.core import device_library as dl
from harness_design_studio.core.commands import Op, Put
from harness_design_studio.core.edit import (
    EditError,
    clone_with,
    expert_height,
    free_slot,
    zone_of_x,
)
from harness_design_studio.core.errors import HarnessError
from harness_design_studio.core.io import canonical
from harness_design_studio.core.io.fs import atomic_write_bytes, slug
from harness_design_studio.core.links import plan_add_link
from harness_design_studio.core.model import Link, Placement, Project, Unit, evolve
from harness_design_studio.core.model.base import Name, Text
from harness_design_studio.core.wires import used_ids

__all__ = [
    "FORMAT",
    "MAX_DEVICES",
    "VERSION",
    "SubsystemError",
    "SubsystemPlan",
    "connections_between",
    "default_file_name",
    "export_subsystem",
    "left_out_connections",
    "plan_subsystem_import",
    "read_subsystem",
    "subsystem_summary",
    "with_placements",
    "write_subsystem",
]

FORMAT = "harness-subsystem-library"
VERSION = 1
MAX_BYTES = dl.MAX_BYTES
MAX_DEVICES = 100  # in one subsystem
MAX_CONNECTIONS = 2000

_NAME = TypeAdapter(Name)
_TEXT = TypeAdapter(Text)


class SubsystemError(HarnessError):
    """The file or the request cannot be used; the message says why in plain words."""


# ---- reading and writing the file -----------------------------------------------------------


def read_subsystem(path: Path | str) -> dict[str, Any]:
    """The checked content of a subsystem library file (size, JSON, format, version, shape)."""
    path = Path(path)
    try:
        info = path.stat()
    except OSError as exc:
        raise SubsystemError(f"The file could not be read ({exc.strerror}).") from exc
    if not stat.S_ISREG(info.st_mode):
        raise SubsystemError("That is not a regular file.")
    if info.st_size > MAX_BYTES:
        raise SubsystemError("The file is too large to read (limit 8 MB).")
    try:
        data = canonical.loads_strict(path.read_bytes())
    except OSError as exc:
        raise SubsystemError(f"The file could not be read ({exc.strerror}).") from exc
    except (ValueError, RecursionError) as exc:
        raise SubsystemError(dl.json_problem(exc)) from exc
    return check_subsystem(data)


def check_subsystem(data: object) -> dict[str, Any]:
    """`data` when it is a subsystem library of a version this program reads, else a
    `SubsystemError` that says what is wrong."""
    if not isinstance(data, dict) or data.get("format") != FORMAT:
        raise SubsystemError(
            f"This is not a subsystem library file (its format is not '{FORMAT}')."
        )
    version = data.get("version")
    if not isinstance(version, int) or isinstance(version, bool) or version < 1:
        raise SubsystemError("The file has no valid version number.")
    if version > VERSION:
        raise SubsystemError(
            f"The file is version {version}; this program reads version {VERSION}. "
            "Use a newer program to read it."
        )
    name = data.get("name")
    if not isinstance(name, str) or not name.strip():
        raise SubsystemError("The subsystem has no name.")
    try:
        _NAME.validate_python(name.strip())
        _TEXT.validate_python(data.get("description", ""))
        _TEXT.validate_python(data.get("notes", ""))
    except ValidationError as exc:
        raise SubsystemError(f"The name, description or notes cannot be used: {_why(exc)}") from exc
    for key, cap in (
        ("devices", MAX_DEVICES),
        ("connections", MAX_CONNECTIONS),
        ("parts", dl.MAX_PARTS),
        ("interface_types", dl.MAX_TYPES),
    ):
        value = data.get(key, [])
        if not isinstance(value, list) or not all(isinstance(v, dict) for v in value):
            raise SubsystemError(f"'{key}' must be a list of records.")
        if len(value) > cap:
            raise SubsystemError(f"The file has more than {cap} entries in '{key}'.")
    if not data.get("devices"):
        raise SubsystemError("The subsystem has no devices.")
    for rec in data["devices"]:
        problem = dl.record_problem(rec)
        if problem:
            unit = rec.get("unit")
            who = str(unit.get("id", "")) if isinstance(unit, dict) else ""
            raise SubsystemError(f"The device {who or '(without an ID)'} cannot be read: {problem}")
    for rec in data.get("connections", []):
        if not isinstance(rec.get("pairs", []), list):
            raise SubsystemError(
                f"The connection {rec.get('id', '')} cannot be read: 'pairs' must be a list."
            )
    return data


def write_subsystem(path: Path | str, data: dict[str, Any]) -> None:
    """Write the file in a stable form (two-space indent, sorted by ID), so a library kept in Git
    shows only what changed."""
    text = json.dumps(check_subsystem(data), indent=2, ensure_ascii=False) + "\n"
    atomic_write_bytes(Path(path), text.encode("utf-8"))


def default_file_name(name: str) -> str:
    """The file name for a subsystem called `name` (the name made safe for a file system)."""
    return f"subsystem-{slug(name)}.json"


def _why(exc: ValidationError) -> str:
    err = exc.errors()[0]
    return str(err["msg"]).removeprefix("Value error, ")


def subsystem_summary(data: dict[str, Any]) -> tuple[int, int, int]:
    """(devices, connectors, connections) of a checked subsystem."""
    devices = data.get("devices", [])
    connectors = sum(
        len(d.get("connectors", [])) if isinstance(d.get("connectors", []), list) else 0
        for d in devices
        if isinstance(d, dict)
    )
    return len(devices), connectors, len(data.get("connections", []))


# ---- export ----------------------------------------------------------------------------------


def export_subsystem(
    project: Project,
    unit_ids: list[str],
    name: str,
    description: str = "",
    notes: str = "",
) -> dict[str, Any]:
    """The devices `unit_ids` of the project and the connections between them as a subsystem (a
    dict ready for `write_subsystem`). A connection with an end outside the devices is left out."""
    clean = (name or "").strip()
    if not clean:
        raise SubsystemError("A subsystem needs a name.")
    try:
        _NAME.validate_python(clean)
        _TEXT.validate_python(description or "")
        _TEXT.validate_python(notes or "")
    except ValidationError as exc:
        raise SubsystemError(f"The name, description or notes cannot be used: {_why(exc)}") from exc
    chosen = list(dict.fromkeys(unit_ids))
    if len(chosen) > MAX_DEVICES:
        raise SubsystemError(f"A subsystem holds up to {MAX_DEVICES} devices.")
    devices = dl.export_devices(project, chosen)  # raises for no device or an unknown one
    owner = {c.id: c.unit_id for c in project.connectors.values()}
    inside = set(chosen)
    links: list[dict[str, Any]] = []
    for link in sorted(project.links.values(), key=lambda x: x.id):
        if owner.get(link.a_connector) in inside and owner.get(link.b_connector) in inside:
            links.append(evolve(link, harness_id="").model_dump(mode="json"))
    return {
        "format": FORMAT,
        "version": VERSION,
        "name": clean,
        "description": (description or "").strip(),
        "notes": (notes or "").strip(),
        "devices": devices["devices"],
        "parts": devices["parts"],
        "interface_types": devices["interface_types"],
        "connections": links,
    }


def left_out_connections(project: Project, unit_ids: list[str]) -> int:
    """How many connections have one end on a chosen device and the other end elsewhere (they are
    not part of the subsystem), for the line under the save window."""
    owner = {c.id: c.unit_id for c in project.connectors.values()}
    inside = set(unit_ids)
    return sum(
        1
        for link in project.links.values()
        if (owner.get(link.a_connector) in inside) != (owner.get(link.b_connector) in inside)
    )


def connections_between(project: Project, unit_ids: list[str]) -> int:
    """How many connections join two of the chosen devices."""
    owner = {c.id: c.unit_id for c in project.connectors.values()}
    inside = set(unit_ids)
    return sum(
        1
        for link in project.links.values()
        if owner.get(link.a_connector) in inside and owner.get(link.b_connector) in inside
    )


# ---- import ----------------------------------------------------------------------------------


@dataclass
class SubsystemPlan:
    """What adding a subsystem would do. `ok` is False when nothing can be added; `problem` then
    says why. `rows` has one row per device of the file; `new_ids` maps a device ID of the file to
    the ID it gets in the project."""

    name: str = ""
    ok: bool = False
    problem: str = ""
    rows: list[dl.DeviceRow] = field(default_factory=list)
    ops: list[Op] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    connections: int = 0

    @property
    def new_ids(self) -> dict[str, str]:
        return {r.unit_id: r.new_id for r in self.rows if r.ok}

    @property
    def device_count(self) -> int:
        return sum(r.ok for r in self.rows)


def _as_device_library(data: dict[str, Any]) -> dict[str, Any]:
    return {
        "format": dl.FORMAT,
        "version": dl.VERSION,
        "devices": data.get("devices", []),
        "parts": data.get("parts", []),
        "interface_types": data.get("interface_types", []),
    }


def with_placements(project: Project, ops: list[Op], *, one_lane: bool = True) -> list[Op]:
    """`ops` with a place on the diagram for every unit they add that has none: the first in the
    emptiest lane, the others in the same lane while there is room (so a subsystem stays together).
    The unit's zone follows the place, as it does for a device added by hand."""
    scratch = clone_with(project, ops)
    out: list[Op] = []
    lane: str | None = None
    for op in ops:
        if not (isinstance(op, Put) and op.collection == "units" and isinstance(op.obj, Unit)):
            out.append(op)
            continue
        unit = op.obj
        if unit.id in project.placements:
            out.append(op)
            continue
        height = expert_height(sum(1 for c in scratch.connectors.values() if c.unit_id == unit.id))
        x, y = free_slot(scratch, lane if one_lane else None, height)
        zone = zone_of_x(scratch, x) or None
        if one_lane and lane is None:
            lane = zone
        placement = Placement(id=unit.id, x=x, y=y)
        scratch = clone_with(scratch, [Put("placements", placement)])
        out.append(Put("units", evolve(unit, zone=zone)))
        out.append(Put("placements", placement))
    return out


def plan_subsystem_import(
    project: Project, data: dict[str, Any], *, place: bool = True
) -> SubsystemPlan:
    """What adding the subsystem in `data` to the project would do (see the module text)."""
    data = check_subsystem(data)
    name = str(data["name"]).strip()
    plan = SubsystemPlan(name=name)
    if project.read_only:
        plan.problem = "This project is read-only (saved by a newer tool version). Use Save as."
        return plan
    devs = dl.plan_device_import(project, _as_device_library(data))
    plan.rows = devs.rows
    plan.notes = list(devs.notes)
    bad = next((r for r in devs.rows if not r.ok), None)
    if bad is not None:
        plan.problem = f"The device {bad.unit_id} cannot be added: {bad.message}"
        return plan
    if not devs.rows:
        plan.problem = "The subsystem has no devices."
        return plan
    ops: list[Op] = []
    for op in devs.ops:  # the subsystem of every added device is the name of this subsystem
        if isinstance(op, Put) and op.collection == "units" and isinstance(op.obj, Unit):
            ops.append(Put("units", evolve(op.obj, subsystem=name)))
        else:
            ops.append(op)
    scratch = clone_with(project, ops)
    connector_map = {cid: new for r in devs.rows if r.ok for cid, new in r.connector_ids.items()}
    link_ops: list[Op] = []
    taken_link_ids = set(project.links)
    for rec in data.get("connections", []):
        try:
            link = Link.model_validate(rec)
        except ValidationError as exc:
            plan.problem = f"A connection of the file cannot be used: {_why(exc)}"
            return plan
        a, b = connector_map.get(link.a_connector), connector_map.get(link.b_connector)
        if a is None or b is None:
            plan.problem = (
                f"The connection {link.id} joins {link.a_connector} and {link.b_connector}, "
                "which are not both connectors of the devices in the file."
            )
            return plan
        busy = {i.casefold() for i in used_ids(scratch) | taken_link_ids}
        wanted = link.id if link.id.casefold() not in busy else None
        try:
            new_ops, lid = plan_add_link(
                scratch,
                a,
                b,
                [(p.a_pin, p.b_pin) for p in link.pairs],
                name=link.name,
                link_id=wanted,
            )
        except (EditError, ValidationError, ValueError) as exc:
            plan.problem = f"The connection {link.id} cannot be added: {exc}"
            return plan
        if wanted is None:
            plan.notes.append(f"The connection {link.id} is added as {lid}.")
        made = new_ops[0]
        if not isinstance(made, Put):  # (plan_add_link gives one Put)
            plan.problem = f"The connection {link.id} cannot be added."
            return plan
        if link.note:
            made = Put("links", evolve(made.obj, note=link.note))
        link_ops.append(made)
        taken_link_ids.add(lid)
        scratch = clone_with(scratch, [made])
    plan.connections = len(link_ops)
    ops += link_ops
    plan.ops = with_placements(project, ops) if place else ops
    plan.ok = True
    return plan
