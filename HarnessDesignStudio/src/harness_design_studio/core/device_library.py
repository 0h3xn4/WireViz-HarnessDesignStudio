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
taken is replaced by the next free one (`OBC1` becomes `OBC1-2`) and the plan says so. A part (a
connector part or the contact part of a pin) or an interface type that the project has already is
kept as the project has it, and the plan names the ones that differ. Nothing is written until the
plan is applied as one undo step.

Saving a device into a file that holds a device of the same ID that differs is refused with a
`LibraryConflict` unless the caller says `replace=True` (or saves it under a new ID). Even then a
part never gets a lower approval than the file has: the file's approval is kept and a note says so.
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
from harness_design_studio.core.io import canonical
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
    "DeviceConflict",
    "DeviceLibraryError",
    "DevicePlan",
    "DeviceRow",
    "LibraryConflict",
    "connector_tail",
    "device_differences",
    "device_names",
    "export_devices",
    "find_conflicts",
    "json_problem",
    "merge_library",
    "merge_with_notes",
    "plan_device_import",
    "read_library",
    "record_problem",
    "save_devices_to_file",
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
        data = canonical.loads_strict(path.read_bytes())
    except OSError as exc:
        raise DeviceLibraryError(f"The file could not be read ({exc.strerror}).") from exc
    except (ValueError, RecursionError) as exc:
        raise DeviceLibraryError(json_problem(exc)) from exc
    return check_library(data)


def json_problem(exc: Exception) -> str:
    """Why a library file is not valid JSON, in plain words: where, and what, never a Python
    name."""
    if isinstance(exc, RecursionError):
        return "The file is nested too deeply to read."
    if isinstance(exc, json.JSONDecodeError):
        return f"The file is not valid JSON at line {exc.lineno}, column {exc.colno}: {exc.msg}."
    if isinstance(exc, UnicodeDecodeError):
        return f"The file is not valid UTF-8 text at byte {exc.start}."
    if isinstance(exc, canonical.DuplicateKeyError):
        key = str(exc).split("'")[1] if "'" in str(exc) else ""
        return (
            f"The file has the key '{key}' twice in one record, "
            "so it is not clear which value is meant."
        )
    if isinstance(exc, canonical.LoneSurrogateError):
        return "The file contains a text escape (\\ud800 to \\udfff) that is not valid text."
    return "The file is not valid JSON text (it holds a number or word that JSON does not allow)."


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


def _dicts(value: object) -> list[dict[str, Any]]:
    """The records of a list; anything else (a number, a text, null) gives no records."""
    return [v for v in value if isinstance(v, dict)] if isinstance(value, list) else []


def _unit_of(rec: object) -> dict[str, Any]:
    unit = rec.get("unit") if isinstance(rec, dict) else None
    return unit if isinstance(unit, dict) else {}


def device_names(data: dict[str, Any]) -> list[tuple[str, str]]:
    """(unit ID, unit name) of every device in a library, in file order."""
    return [
        (str(_unit_of(d).get("id", "")), str(_unit_of(d).get("name", "")))
        for d in _dicts(data.get("devices", []))
    ]


def record_problem(rec: object) -> str:
    """Why a device record of a file cannot even be read (a number where a list belongs ...), in
    plain words; an empty text when its shape is fine. Whether its values are good is for
    `plan_device_import` to say."""
    if not isinstance(rec, dict):
        return "the device is not a record."
    if "unit" in rec and not isinstance(rec["unit"], dict):
        return "'unit' must be a record."
    conns = rec.get("connectors", [])
    if not isinstance(conns, list) or not all(isinstance(c, dict) for c in conns):
        return "'connectors' must be a list of records."
    for c in conns:
        pins = c.get("pins", [])
        if not isinstance(pins, list) or not all(isinstance(p, dict) for p in pins):
            return f"the pins of connector {c.get('id', '')} must be a list of records."
    return ""


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


def connector_tail(connector_id: str, unit_id: str) -> str:
    """The part of a connector ID that stays when the device gets another ID: what follows the
    device ID, else what follows the first '-', else the whole ID (`OBC-J01` is `J01`, and so is
    `OBC9-J01` of a device that was renamed; `J1` stays `J1`)."""
    if connector_id.startswith(unit_id + "-"):
        return connector_id[len(unit_id) + 1 :]
    head, dash, tail = connector_id.partition("-")
    return tail if dash and tail else head


def export_devices(
    project: Project, unit_ids: list[str], new_ids: dict[str, str] | None = None
) -> dict[str, Any]:
    """The devices `unit_ids` of the project as a library (a dict ready for `write_library`).
    `new_ids` gives a device another ID in the file (`{"RW1": "RW1-2"}`), its connectors with it;
    the project is not touched."""
    if not unit_ids:
        raise DeviceLibraryError("Choose at least one device.")
    devices: list[dict[str, Any]] = []
    parts: dict[str, Part] = {}
    types: dict[str, InterfaceType] = {}
    for uid in dict.fromkeys(unit_ids):
        unit = project.units.get(uid)
        if unit is None:
            raise DeviceLibraryError(f"Device '{uid}' does not exist.")
        nid = (new_ids or {}).get(uid, uid)
        if nid != uid and not ID_RE.fullmatch(nid):
            raise DeviceLibraryError(f"'{nid}' cannot be used as a device ID.")
        connectors = sorted(
            (c for c in project.connectors.values() if c.unit_id == uid), key=lambda c: c.id
        )
        out = []
        for c in connectors:
            c2 = evolve(c, pins=[_portable(p) for p in c.pins])
            if nid != uid:
                cid = f"{nid}-{connector_tail(c.id, uid)}"
                if not ID_RE.fullmatch(cid):
                    raise DeviceLibraryError(
                        f"{nid} is too long to build the connector IDs of {uid} from it."
                    )
                c2 = evolve(c2, id=cid, unit_id=nid)
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
        unit_data = evolve(unit, id=nid, zone=None).model_dump(mode="json")
        devices.append({"unit": unit_data, "connectors": out})
    return {
        "format": FORMAT,
        "version": VERSION,
        "devices": devices,
        "parts": [parts[k].model_dump(mode="json") for k in sorted(parts)],
        "interface_types": [types[k].model_dump(mode="json") for k in sorted(types)],
    }


_RANK = {"not_approved": 0, "pending": 1, "approved": 2}


def _ident_of(rec: Any, *path: str) -> str:
    for key in path:
        rec = rec.get(key, {}) if isinstance(rec, dict) else {}
    return str(rec) if rec != {} else ""


def merge_with_notes(
    existing: dict[str, Any] | None, new: dict[str, Any], *, replace: bool = True
) -> tuple[dict[str, Any], list[str]]:
    """`new` added to the content of an existing file, and what was kept (as sentences).

    A device (same unit ID) that is in both is replaced by the new one. A part or interface type
    that is in both and differs is replaced by the new one when `replace` is True, else the file's
    is kept; the approval of a part is never lowered (approved > pending > not approved): the
    file's approval is kept. The result is sorted by ID."""
    base = check_library(existing) if existing is not None else {}
    notes: list[str] = []

    def merged(key: str, ident: Any, label: str, part: bool = False) -> list[dict[str, Any]]:
        by_id = {ident(r): r for r in _dicts(base.get(key, []))}
        for rec in _dicts(new.get(key, [])):
            k = ident(rec)
            old = by_id.get(k)
            if old is None or key == "devices":
                by_id[k] = rec
            elif old == rec:
                continue
            elif not replace:
                notes.append(f"{label} {k} differs from the one in the file; the file's is kept.")
            else:
                if part:
                    was, now = old.get("approval", "pending"), rec.get("approval", "pending")
                    if _RANK.get(now, 1) < _RANK.get(was, 1):
                        rec = {x: v for x, v in rec.items() if x != "approval"}
                        if "approval" in old:
                            rec["approval"] = old["approval"]
                        notes.append(
                            f"Part {k} is '{was}' in the file and '{now}' in this project; "
                            f"the file's status '{was}' is kept."
                        )
                by_id[k] = rec
        return [by_id[k] for k in sorted(by_id)]

    return {
        "format": FORMAT,
        "version": VERSION,
        "devices": merged("devices", lambda d: _ident_of(d, "unit", "id"), "Device"),
        "parts": merged("parts", lambda p: _ident_of(p, "id"), "Part", True),
        "interface_types": merged(
            "interface_types", lambda t: _ident_of(t, "id"), "Interface type"
        ),
    }, notes


def merge_library(existing: dict[str, Any] | None, new: dict[str, Any]) -> dict[str, Any]:
    """`new` added to the content of an existing file: a device (same unit ID), part or interface
    type that is in both is replaced by the new one (a part keeps the better approval of the two).
    The result is sorted by ID. Whether that is wanted is for the caller to ask first, see
    `save_devices_to_file`."""
    return merge_with_notes(existing, new, replace=True)[0]


# ---- saving into a file that has the device already ------------------------------------------


def _count(n: int, one: str, many: str) -> str:
    return f"{n} {one if n == 1 else many}"


@dataclass(frozen=True)
class DeviceConflict:
    """A device of the file with the same ID as one to be saved, but not the same content.
    `pins` and `fields` say how much differs; `suggested_id` is a free ID for the new one."""

    unit_id: str
    pins: int
    fields: int
    suggested_id: str

    def differs_in(self) -> str:
        """'3 pins', '1 field' or '3 pins and 1 field': how much differs, in words."""
        parts = []
        if self.pins:
            parts.append(_count(self.pins, "pin", "pins"))
        if self.fields or not parts:
            parts.append(_count(self.fields, "field", "fields"))
        return " and ".join(parts)


class LibraryConflict(DeviceLibraryError):
    """A file holds a device of the same ID that differs, and nobody said to replace it."""

    def __init__(self, file: str, conflicts: list[DeviceConflict]) -> None:
        self.file = file
        self.conflicts = conflicts
        what = "; ".join(f"{c.unit_id} (differs in {c.differs_in()})" for c in conflicts)
        super().__init__(
            f"{file} has {'this device' if len(conflicts) == 1 else 'these devices'} already "
            f"and {'it differs' if len(conflicts) == 1 else 'they differ'}: {what}. "
            "Nothing was changed."
        )


def _normal(rec: dict[str, Any]) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    """(unit, connectors by ID) of a device record, as the model would write them, so that a file
    written by another version compares equal when the content is the same."""
    unit, conns = _unit_of(rec), _dicts(rec.get("connectors", []))
    try:
        u = Unit.model_validate(unit).model_dump(mode="json")
        cs = {c.id: c.model_dump(mode="json") for c in map(Connector.model_validate, conns)}
    except (ValidationError, ValueError):
        u, cs = unit, {str(c.get("id", i)): c for i, c in enumerate(conns)}
    return u, cs


def device_differences(old: dict[str, Any], new: dict[str, Any]) -> tuple[int, int]:
    """(pins, fields) in which two device records differ: pins that differ or exist on one side
    only, and other fields of the device or its connectors. (0, 0) when they are the same."""
    (uo, co), (un, cn) = _normal(old), _normal(new)
    fields = sum(uo.get(k) != un.get(k) for k in set(uo) | set(un))
    pins = 0
    for cid in set(co) | set(cn):
        a, b = co.get(cid), cn.get(cid)
        if a is None or b is None:
            n = len((a or b or {}).get("pins", []))
            pins += n
            fields += 0 if n else 1
            continue
        fields += sum(a.get(k) != b.get(k) for k in (set(a) | set(b)) - {"pins"})
        pa = {str(p.get("id")): p for p in _dicts(a.get("pins", []))}
        pb = {str(p.get("id")): p for p in _dicts(b.get("pins", []))}
        pins += sum(pa.get(k) != pb.get(k) for k in set(pa) | set(pb))
    return pins, fields


def find_conflicts(existing: dict[str, Any] | None, new: dict[str, Any]) -> list[DeviceConflict]:
    """The devices of `new` that the file `existing` has under the same ID with other content."""
    if existing is None:
        return []
    old = {_ident_of(d, "unit", "id"): d for d in _dicts(existing.get("devices", []))}
    taken = {k.casefold() for k in old}
    out = []
    for rec in _dicts(new.get("devices", [])):
        uid = _ident_of(rec, "unit", "id")
        if uid in old:
            pins, fields = device_differences(old[uid], rec)
            if pins or fields:
                out.append(DeviceConflict(uid, pins, fields, _free_id(uid, taken)))
    return out


def save_devices_to_file(
    path: Path | str,
    project: Project,
    unit_ids: list[str],
    *,
    replace: bool = False,
    new_ids: dict[str, str] | None = None,
    notes: list[str] | None = None,
) -> Path:
    """Add the devices to a device library file (made if it is not there). Returns the path.

    A device of the same ID that the file has already and that differs is NOT replaced: the call
    raises `LibraryConflict` (the file is not touched) unless `replace` is True. `new_ids` saves a
    device under another ID instead (`{"RW1": "RW1-2"}`). Whatever was kept on the way (a part
    whose approval is not lowered) is added to `notes` as sentences."""
    target = Path(path)
    data = export_devices(project, unit_ids, new_ids)
    existing = read_library(target) if target.exists() else None
    conflicts = find_conflicts(existing, data)
    if conflicts and not replace:
        raise LibraryConflict(target.name, conflicts)
    merged, kept = merge_with_notes(existing, data, replace=replace)
    write_library(target, merged)
    if notes is not None:
        notes.extend(kept)
    return target


# ---- import ----------------------------------------------------------------------------------


@dataclass
class DeviceRow:
    unit_id: str  # the ID in the file
    ok: bool
    message: str = ""
    new_id: str = ""  # the ID in the project
    connectors: int = 0
    pins: int = 0
    connector_ids: dict[str, str] = field(
        default_factory=dict
    )  # ID in the file -> ID in the project


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


def _bring(
    project: Project,
    file_parts: dict[str, Part],
    local_parts: dict[str, Part],
    notes: list[str],
    part_id: str,
) -> None:
    """A part a device names (its connector or the contact of a pin): taken from the file when the
    project does not have it; one the project has is never replaced (a note says when the file's
    differs)."""
    if part_id not in project.parts:
        local_parts[part_id] = file_parts[part_id]
    elif part_id in file_parts and file_parts[part_id] != project.parts[part_id]:
        note = f"Part {part_id} differs from the one in this project; the project's is kept."
        if note not in notes:
            notes.append(note)


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

        renumber = 0
        for c in conns:
            cid = f"{new_id}-{connector_tail(c.id, unit.id)}"
            if not ID_RE.fullmatch(cid) or cid.casefold() in conn_ids_taken | used_ids:
                # the tail of the old ID does not fit (taken twice in the file ...): number it
                while True:
                    renumber += 1
                    cid = f"{new_id}-J{renumber:02d}"
                    if cid.casefold() not in conn_ids_taken | used_ids:
                        break
                if not ID_RE.fullmatch(cid):
                    failed = (
                        f"The device ID {new_id} is too long to build the ID of connector "
                        f"{c.name} from it (an ID holds up to 64 characters)."
                    )
                    break
            used_ids.add(cid.casefold())
            if c.part_id not in project.parts and c.part_id not in file_parts:
                failed = f"Connector {c.name} names the part '{c.part_id}', which is neither in the project nor in the file."  # noqa: E501
                break
            _bring(project, file_parts, local_parts, plan.notes, c.part_id)
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
            pins = []
            for pin in map(_portable, c.pins):
                cp = pin.contact_part
                if cp and cp not in project.parts and cp not in file_parts:
                    plan.notes.append(
                        f"{new_id} {c.name} pin {pin.id}: the contact part '{cp}' is neither in "
                        "the project nor in the file; the pin is added without it."
                    )
                    pin = evolve(pin, contact_part=None)
                elif cp:
                    _bring(project, file_parts, local_parts, plan.notes, cp)
                pins.append(pin)
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
        row.connector_ids = {old.id: new.id for old, new in zip(conns, new_conns, strict=True)}
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
