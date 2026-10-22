"""A device library file: devices with their connectors and pinouts, kept outside any project, so
that a device that was defined once (down to each pin and its function) is reused in the next
project (D-165).

    data = export_devices(project, ["OBC1", "PCU1"])          # a dict that holds the devices
    data = merge_library(read_library(path), data)            # add to a file that already has some
    write_library(path, data)
    plan = plan_device_import(project, read_library(path), ["OBC1"])   # a preview and the ops

The file is JSON (`harness-device-library`, version 1) and holds, for each device, the unit, its box
connectors with every pin (signal, function, contact size, termination, fixed), and the library
parts and interface types that those connectors name, so the device is complete on its own. What
belongs to one project is left out: the interfaces and wires that were generated on the pins
(`interface_id`, `locked`), the zone of the unit, the harnesses. The parts keep the approval status
that the file says; the tool does not decide it again.

Importing adds a device; it never changes one that is in the project. A unit ID or a name that is
taken is replaced by the next free one (`OBC1` becomes `OBC1-2`) and the plan says so. A part or an
interface type that the project has already is kept as the project has it, and the plan names the
ones that differ. Nothing is written until the plan is applied as one undo step.
"""

import json
import re
import stat
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from harness_design_studio.core.commands import Op, Put
from harness_design_studio.core.errors import HarnessError
from harness_design_studio.core.ids import ID_RE
from harness_design_studio.core.io.fs import atomic_write_bytes
from harness_design_studio.core.model import (
    Connector,
    InterfaceType,
    Part,
    Pin,
    Project,
    Unit,
    evolve,
)

__all__ = [
    "FORMAT",
    "VERSION",
    "DeviceLibraryError",
    "DevicePlan",
    "DeviceRow",
    "device_names",
    "export_devices",
    "merge_library",
    "plan_device_import",
    "read_library",
    "write_library",
]

FORMAT = "harness-device-library"
VERSION = 1
MAX_BYTES = 8 * 1024 * 1024
MAX_DEVICES = 500
MAX_CONNECTORS = 64  # per device
MAX_PARTS = 5000
MAX_TYPES = 2000


class DeviceLibraryError(HarnessError):
    """The file or the request cannot be used; the message says why in plain words."""


# ---- reading and writing the file -----------------------------------------------------------


def read_library(path: Path | str) -> dict[str, Any]:
    """The checked content of a device library file (size, JSON, format, version)."""
    path = Path(path)
    try:
        info = path.stat()
    except OSError as exc:
        raise DeviceLibraryError(f"The file could not be read ({exc.strerror}).") from exc
    if not stat.S_ISREG(info.st_mode):
        raise DeviceLibraryError("That is not a regular file.")
    if info.st_size > MAX_BYTES:
        raise DeviceLibraryError("The file is too large to read (limit 8 MB).")
    try:
        raw = path.read_bytes()
        data = json.loads(raw.decode("utf-8-sig"))
    except (OSError, UnicodeError, ValueError, RecursionError) as exc:
        raise DeviceLibraryError(
            f"The file is not valid JSON text ({type(exc).__name__})."
        ) from exc
    return check_library(data)


def check_library(data: object) -> dict[str, Any]:
    if not isinstance(data, dict) or data.get("format") != FORMAT:
        raise DeviceLibraryError(
            f"This is not a device library file (its format is not '{FORMAT}')."
        )
    version = data.get("version")
    if not isinstance(version, int) or isinstance(version, bool) or version < 1:
        raise DeviceLibraryError("The file has no valid version number.")
    if version > VERSION:
        raise DeviceLibraryError(
            f"The file is version {version}; this program reads version {VERSION}. "
            "Use a newer program to read it."
        )
    for key, cap in (
        ("devices", MAX_DEVICES),
        ("parts", MAX_PARTS),
        ("interface_types", MAX_TYPES),
    ):
        value = data.get(key, [])
        if not isinstance(value, list) or not all(isinstance(v, dict) for v in value):
            raise DeviceLibraryError(f"'{key}' must be a list of records.")
        if len(value) > cap:
            raise DeviceLibraryError(f"The file has more than {cap} entries in '{key}'.")
    return data


def write_library(path: Path | str, data: dict[str, Any]) -> None:
    """Write the file in a stable form (sorted by ID, two-space indent), so a library kept in Git
    shows only what changed. The old file is kept as `.bak`."""
    text = json.dumps(check_library(data), indent=2, ensure_ascii=False) + "\n"
    atomic_write_bytes(Path(path), text.encode("utf-8"))


# ---- export ----------------------------------------------------------------------------------


def device_names(data: dict[str, Any]) -> list[tuple[str, str]]:
    """(unit ID, unit name) of every device in a library, in file order."""
    return [
        (str(d.get("unit", {}).get("id", "")), str(d.get("unit", {}).get("name", "")))
        for d in data.get("devices", [])
    ]


def _portable(pin: Pin) -> Pin:
    """The pin as the device has it. What belongs to the design of the device travels: a fixed
    signal, a signal and a lock that a person set by hand, the function, contact size and
    termination. What generation allocated in THIS project (a signal given for an interface, and
    the interface) does not."""
    if pin.fixed:
        return evolve(pin, interface_id=None, locked=False)
    if pin.interface_id is not None:
        return evolve(pin, signal=None, interface_id=None, locked=False)
    return pin


def export_devices(project: Project, unit_ids: list[str]) -> dict[str, Any]:
    """The devices `unit_ids` of the project as a library (a dict ready for `write_library`)."""
    if not unit_ids:
        raise DeviceLibraryError("Choose at least one device.")
    devices: list[dict[str, Any]] = []
    parts: dict[str, Part] = {}
    types: dict[str, InterfaceType] = {}
    for uid in dict.fromkeys(unit_ids):
        unit = project.units.get(uid)
        if unit is None:
            raise DeviceLibraryError(f"Device '{uid}' does not exist.")
        connectors = sorted(
            (c for c in project.connectors.values() if c.unit_id == uid), key=lambda c: c.id
        )
        out = []
        for c in connectors:
            c2 = evolve(c, pins=[_portable(p) for p in c.pins])
            out.append(c2.model_dump(mode="json"))
            todo = [c.part_id, *sorted({p.contact_part for p in c.pins if p.contact_part})]
            while todo:  # the part, the part it mates with and the contacts of its pins
                pid = todo.pop()
                part = project.parts.get(pid)
                if part is not None and pid not in parts:
                    parts[pid] = part
                    if part.mates_with:
                        todo.append(part.mates_with)
            for t in c.carries:
                if t in project.interface_types:
                    types[t] = project.interface_types[t]
        unit_data = evolve(unit, zone=None).model_dump(mode="json")
        devices.append({"unit": unit_data, "connectors": out})
    return {
        "format": FORMAT,
        "version": VERSION,
        "devices": devices,
        "parts": [parts[k].model_dump(mode="json") for k in sorted(parts)],
        "interface_types": [types[k].model_dump(mode="json") for k in sorted(types)],
    }


def merge_library(existing: dict[str, Any] | None, new: dict[str, Any]) -> dict[str, Any]:
    """`new` added to the content of an existing file: a device (same unit ID), part or interface
    type that is in both is replaced by the new one. The result is sorted by ID."""
    base = check_library(existing) if existing is not None else {}

    def merged(key: str, ident: Any) -> list[dict[str, Any]]:
        by_id = {ident(r): r for r in base.get(key, [])}
        by_id.update({ident(r): r for r in new.get(key, [])})
        return [by_id[k] for k in sorted(by_id)]

    return {
        "format": FORMAT,
        "version": VERSION,
        "devices": merged("devices", lambda d: str(d.get("unit", {}).get("id", ""))),
        "parts": merged("parts", lambda p: str(p.get("id", ""))),
        "interface_types": merged("interface_types", lambda t: str(t.get("id", ""))),
    }


# ---- import ----------------------------------------------------------------------------------


@dataclass
class DeviceRow:
    unit_id: str  # the ID in the file
    ok: bool
    message: str = ""
    new_id: str = ""  # the ID in the project
    connectors: int = 0
    pins: int = 0


@dataclass
class DevicePlan:
    rows: list[DeviceRow] = field(default_factory=list)
    ops: list[Op] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)  # what was kept, renamed, left out

    @property
    def ok_count(self) -> int:
        return sum(r.ok for r in self.rows)


def _problem(exc: ValidationError) -> str:
    err = exc.errors()[0]
    where = ".".join(str(x) for x in err["loc"])
    return f"{where}: {str(err['msg']).removeprefix('Value error, ')}" if where else str(err["msg"])


def _free_id(base: str, taken: set[str]) -> str:
    """`base` if it is free, else `base-2`, `base-3` ... (compared without regard to case)."""
    if base.casefold() not in taken:
        return base
    k = 2
    while True:
        suffix = f"-{k}"
        cand = base[: 64 - len(suffix)] + suffix
        if cand.casefold() not in taken:
            return cand
        k += 1


def plan_device_import(
    project: Project, data: dict[str, Any], unit_ids: list[str] | None = None
) -> DevicePlan:
    """What adding the devices `unit_ids` (all when None) of a library to the project would do.
    Each device is its own row; a device with a problem adds nothing and the others still do."""
    data = check_library(data)
    plan = DevicePlan()
    wanted = None if unit_ids is None else set(unit_ids)
    file_parts: dict[str, Part] = {}
    for rec in data.get("parts", []):
        try:
            p = Part.model_validate(rec)
        except ValidationError as exc:
            plan.notes.append(f"A part of the file was left out: {_problem(exc)}")
            continue
        file_parts[p.id] = p
    file_types: dict[str, InterfaceType] = {}
    for rec in data.get("interface_types", []):
        try:
            itype = InterfaceType.model_validate(rec)
        except ValidationError as exc:
            plan.notes.append(f"An interface type of the file was left out: {_problem(exc)}")
            continue
        file_types[itype.id] = itype

    unit_ids_taken = {u.casefold() for u in project.units}
    conn_ids_taken = {c.casefold() for c in project.all_connectors()}
    need_parts: dict[str, Part] = {}
    need_types: dict[str, InterfaceType] = {}
    ops: list[Op] = []
    seen_ids: set[str] = set()

    for rec in data.get("devices", []):
        raw_unit = rec.get("unit", {}) if isinstance(rec, dict) else {}
        uid = str(raw_unit.get("id", "")) if isinstance(raw_unit, dict) else ""
        if wanted is not None and uid not in wanted:
            continue
        row = DeviceRow(uid, False)
        plan.rows.append(row)
        if uid in seen_ids:
            row.message = "The file holds this device twice; only the first one is used."
            continue
        seen_ids.add(uid)
        try:
            unit = Unit.model_validate(raw_unit)
            raw_conns = rec.get("connectors", [])
            if not isinstance(raw_conns, list) or len(raw_conns) > MAX_CONNECTORS:
                raise DeviceLibraryError(f"A device holds up to {MAX_CONNECTORS} connectors.")
            conns = [Connector.model_validate(c) for c in raw_conns]
        except ValidationError as exc:
            row.message = _problem(exc)
            continue
        except DeviceLibraryError as exc:
            row.message = str(exc)
            continue
        if any(c.role != "box" or c.unit_id != unit.id for c in conns):
            row.message = "A connector of the device is not a box connector of this device."
            continue

        new_id = _free_id(unit.id, unit_ids_taken)
        if new_id != unit.id:
            plan.notes.append(f"{unit.id} is taken in this project; it is added as {new_id}.")
        row.new_id = new_id
        unit_ids_taken.add(new_id.casefold())
        new_unit = evolve(unit, id=new_id, zone=None)

        local_parts: dict[str, Part] = {}
        local_types: dict[str, InterfaceType] = {}
        new_conns: list[Connector] = []
        failed = ""
        used_ids: set[str] = set()
        for c in conns:
            tail = c.id[len(unit.id) + 1 :] if c.id.startswith(unit.id + "-") else c.name
            cid = f"{new_id}-{tail}"
            if not ID_RE.fullmatch(cid) or cid.casefold() in conn_ids_taken | used_ids:
                failed = f"The connector ID '{cid}' cannot be used or is taken."
                break
            used_ids.add(cid.casefold())
            if c.part_id not in project.parts and c.part_id not in file_parts:
                failed = f"Connector {c.name} names the part '{c.part_id}', which is neither in the project nor in the file."  # noqa: E501
                break
            if c.part_id not in project.parts:
                local_parts[c.part_id] = file_parts[c.part_id]
            elif c.part_id in file_parts and file_parts[c.part_id] != project.parts[c.part_id]:
                plan.notes.append(
                    f"Part {c.part_id} differs from the one in this project; the project's is kept."
                )
            carries: list[str] = []
            for t in c.carries:
                if t in project.interface_types:
                    carries.append(t)
                    if t in file_types and file_types[t] != project.interface_types[t]:
                        plan.notes.append(
                            f"Interface type {t} differs from the one in this project; the project's is kept."  # noqa: E501
                        )
                elif t in file_types:
                    carries.append(t)
                    local_types[t] = file_types[t]
                else:
                    plan.notes.append(
                        f"{new_id} {c.name}: interface type '{t}' is unknown and was left out."
                    )  # noqa: E501
            pins = [_portable(p) for p in c.pins]
            new_conns.append(evolve(c, id=cid, unit_id=new_id, carries=carries, pins=pins))
        if failed:
            row.message = failed
            unit_ids_taken.discard(new_id.casefold())
            continue
        # a part that is added brings the part it mates with, when the file has it
        todo = list(local_parts.values())
        while todo:
            part = todo.pop()
            m = part.mates_with
            if m and m not in project.parts and m not in local_parts:
                if m in file_parts:
                    local_parts[m] = file_parts[m]
                    todo.append(file_parts[m])
                else:
                    local_parts[part.id] = evolve(part, mates_with=None)
                    plan.notes.append(
                        f"Part {part.id}: the mating part '{m}' is not in the file; "
                        "the link was left out."
                    )
        need_parts.update(local_parts)
        need_types.update(local_types)
        conn_ids_taken |= used_ids
        ops.append(Put("units", new_unit))
        ops.extend(Put("connectors", c) for c in new_conns)
        row.ok = True
        row.connectors = len(new_conns)
        row.pins = sum(len(c.pins) for c in new_conns)

    if wanted is not None:
        for missing in sorted(wanted - seen_ids):
            plan.rows.append(DeviceRow(missing, False, "The file has no such device."))
    if ops:
        for p in need_parts.values():
            if p.unverified or p.approval != "approved":
                plan.notes.append(
                    f"Part {p.id} is added with the status '{p.approval}'"
                    + (" (example data)" if p.unverified else "")
                    + "; the file's status is not a decision of this project."
                )
        plan.ops = [Put("parts", p) for p in need_parts.values()]
        plan.ops += [Put("interface_types", t) for t in need_types.values()]
        plan.ops += ops
    return plan


_SAFE_NAME = re.compile(r"[^A-Za-z0-9._-]+")


def default_file_name(unit_ids: list[str]) -> str:
    """A file name for exported devices: the unit ID for one, `devices.json` for several."""
    return (_SAFE_NAME.sub("_", unit_ids[0]) if len(unit_ids) == 1 else "devices") + ".json"
