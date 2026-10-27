"""The library folder: a folder that anyone points the tool at (a shared drive, a Git checkout)
and that holds device library files and subsystem library files (workshop feedback M4, D-175).

    scan = scan_folder(Path("/mnt/shared/harness-library"))
    for e in scan.entries: print(e.kind, e.name, e.file)
    data = load_entry(scan.folder, scan.entries[0])             # re-read from disk
    path = save_devices(folder, project, ["OBC1"])             # only when the person says so
    path = save_subsystem(folder, project, ["OBC1", "RW1"], "Wheel drive")

The tool is offline: this is plain file reading, never a network call. Sharing is the job of the
drive or the repository around the folder. The folder is only read, except by `save_devices` and
`save_subsystem`, which the person starts with *Save to library*. A file that cannot be read does
not stop the others: it is listed in `LibraryScan.problems` with a plain sentence. A file whose JSON
is not one of the two library formats (a `package.json` next to them) is skipped without a word.
"""

import os
import stat
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from harness_design_studio.core import device_library as dl
from harness_design_studio.core import subsystem_library as sl
from harness_design_studio.core.device_library import DeviceConflict, LibraryConflict
from harness_design_studio.core.errors import HarnessError
from harness_design_studio.core.io import canonical
from harness_design_studio.core.model import Project

__all__ = [
    "DeviceConflict",
    "LibraryConflict",
    "LibraryEntry",
    "LibraryError",
    "LibraryProblem",
    "LibraryScan",
    "describe_entry",
    "load_entry",
    "save_devices",
    "save_subsystem",
    "scan_folder",
]

MAX_FILES = 2000  # JSON files looked at in one folder
MAX_DEPTH = 3  # folders below the library folder that are looked into

Kind = Literal["device", "subsystem"]


class LibraryError(HarnessError):
    """The library folder or a request to it cannot be used; the message says why."""


@dataclass(frozen=True)
class LibraryEntry:
    """One thing the library offers: a device of a device file, or the subsystem of a subsystem
    file. `file` is the path inside the library folder (with `/`)."""

    kind: Kind
    key: str  # unique in a scan
    id: str  # the device ID in the file; empty for a subsystem
    name: str
    description: str
    file: str
    devices: int = 1
    connectors: int = 0
    pins: int = 0
    connections: int = 0
    subsystem: str = ""  # the subsystem a device was saved with, for the search


@dataclass(frozen=True)
class LibraryProblem:
    file: str
    message: str

    def __str__(self) -> str:
        return f"{self.file}: {self.message}"


@dataclass
class LibraryScan:
    folder: Path
    entries: list[LibraryEntry] = field(default_factory=list)
    problems: list[LibraryProblem] = field(default_factory=list)
    error: str = ""  # the folder itself cannot be used: why, in plain words
    skipped: int = 0  # JSON files that are not library files


def _folder_problem(folder: Path) -> str:
    try:
        info = folder.stat()
    except FileNotFoundError:
        return f"The folder {folder} does not exist. Is the drive connected?"
    except PermissionError:
        return f"You may not open the folder {folder}."
    except OSError as exc:
        return f"The folder {folder} could not be opened ({exc.strerror})."
    if not stat.S_ISDIR(info.st_mode):
        return f"{folder} is not a folder."
    if not os.access(folder, os.R_OK | os.X_OK):
        return f"You may not read the folder {folder}."
    return ""


def _json_files(folder: Path) -> tuple[list[Path], str]:
    """The `.json` files in the folder and in the folders below it (hidden folders such as `.git`
    and links are not followed), sorted by path; and a sentence when the list was cut short."""
    found: list[Path] = []
    cut = ""

    def walk(here: Path, depth: int) -> None:
        nonlocal cut
        try:
            names = sorted(os.listdir(here), key=str.casefold)
        except OSError:
            return
        for name in names:
            if len(found) >= MAX_FILES:
                cut = f"Only the first {MAX_FILES} files were looked at."
                return
            path = here / name
            if name.startswith(".") or path.is_symlink():
                continue
            if path.is_dir():
                if depth < MAX_DEPTH:
                    walk(path, depth + 1)
            elif name.casefold().endswith(".json") and path.is_file():
                found.append(path)

    walk(folder, 1)
    return found, cut


def scan_folder(folder: Path | str) -> LibraryScan:
    """Everything the library folder offers. Never raises: a folder that cannot be used gives a
    scan with `error` set; a file that cannot be used gives an entry in `problems`."""
    root = Path(folder)
    scan = LibraryScan(root)
    scan.error = _folder_problem(root)
    if scan.error:
        return scan
    files, cut = _json_files(root)
    if cut:
        scan.problems.append(LibraryProblem(".", cut))
    for path in files:
        rel = path.relative_to(root).as_posix()
        try:
            _scan_file(scan, path, rel)
        except HarnessError as exc:
            scan.problems.append(LibraryProblem(rel, str(exc)))
        except (OSError, ValueError, UnicodeError, RecursionError) as exc:
            scan.problems.append(LibraryProblem(rel, _read_words(exc)))
        except Exception:  # noqa: BLE001  (a promise: one bad file never hides the good ones)
            scan.problems.append(LibraryProblem(rel, "The file has a form that cannot be read."))
    scan.entries.sort(key=lambda e: (e.kind, e.name.casefold(), e.id.casefold(), e.file))
    return scan


def _scan_file(scan: LibraryScan, path: Path, rel: str) -> None:
    """Read one file (once) and add its entries, its skip or its problems to the scan."""
    data = _read_json(path)
    fmt = data.get("format") if isinstance(data, dict) else None
    if fmt == dl.FORMAT:
        entries, problems = _device_entries(rel, dl.check_library(data))
        scan.entries += entries
        scan.problems += [LibraryProblem(rel, text) for text in problems]
    elif fmt == sl.FORMAT:
        scan.entries.append(_subsystem_entry(rel, sl.check_subsystem(data)))
    else:
        scan.skipped += 1


def _read_words(exc: Exception) -> str:
    if isinstance(exc, OSError):
        return f"The file could not be read ({exc.strerror})."
    return dl.json_problem(exc)


def _read_json(path: Path) -> Any:
    """The content of a JSON file: strict (a key twice is refused), size checked."""
    info = path.stat()
    if info.st_size > dl.MAX_BYTES:
        raise LibraryError("The file is too large to read (limit 8 MB).")
    return canonical.loads_strict(path.read_bytes())


def _device_entries(rel: str, data: dict[str, Any]) -> tuple[list[LibraryEntry], list[str]]:
    """(the devices of a checked device file, a sentence for each device that cannot be listed)."""
    out: list[LibraryEntry] = []
    problems: list[str] = []
    seen: set[str] = set()
    for rec in data.get("devices", []):
        unit = rec.get("unit", {}) if isinstance(rec, dict) else {}
        if not isinstance(unit, dict) or not unit.get("id"):
            problems.append("A device of the file has no usable 'unit' record with an ID.")
            continue
        uid = str(unit["id"])
        bad = dl.record_problem(rec)
        if bad:
            problems.append(f"The device {uid} is not listed: {bad}")
            continue
        if uid in seen:
            problems.append(f"The device {uid} is in the file twice; only the first is listed.")
            continue
        seen.add(uid)
        conns = rec.get("connectors", [])
        out.append(
            LibraryEntry(
                "device",
                f"{rel}#{uid}",
                uid,
                str(unit.get("name", uid)),
                str(unit.get("notes", "")),
                rel,
                1,
                len(conns),
                sum(len(c.get("pins", [])) for c in conns),
                0,
                str(unit.get("subsystem", "")),
            )
        )
    return out, problems


def _subsystem_entry(rel: str, data: dict[str, Any]) -> LibraryEntry:
    n_dev, n_conn, n_links = sl.subsystem_summary(data)
    pins = sum(
        len(c.get("pins", []))
        for d in data.get("devices", [])
        for c in d.get("connectors", [])
        if isinstance(c, dict)
    )
    return LibraryEntry(
        "subsystem",
        rel,
        "",
        str(data["name"]).strip(),
        str(data.get("description", "")),
        rel,
        n_dev,
        n_conn,
        pins,
        n_links,
    )


def load_entry(folder: Path | str, entry: LibraryEntry) -> dict[str, Any]:
    """The checked data of the file an entry came from, read again from the disk."""
    path = Path(folder) / entry.file
    if entry.kind == "device":
        return dl.read_library(path)
    return sl.read_subsystem(path)


# ---- the preview ------------------------------------------------------------------------------


def _records(value: object) -> list[dict[str, Any]]:
    return [v for v in value if isinstance(v, dict)] if isinstance(value, list) else []


def describe_entry(data: dict[str, Any], entry: LibraryEntry) -> list[dict[str, str]]:
    """Rows for the preview of an entry. A device gives one row for each pin (connector, pin,
    signal, function); a subsystem gives one row for each device and for each connection (kind,
    item, detail). Plain strings, so a table can show them as they are. A record of a form that
    is not expected is left out, never an error."""
    if entry.kind == "device":
        return _device_rows(data, entry.id)
    rows: list[dict[str, str]] = []
    for rec in _records(data.get("devices", [])):
        unit = rec.get("unit", {})
        unit = unit if isinstance(unit, dict) else {}
        conns = _records(rec.get("connectors", []))
        rows.append(
            {
                "kind": "Device",
                "item": f"{unit.get('id', '')}  {unit.get('name', '')}".strip(),
                "detail": f"{len(conns)} connector(s), "
                f"{sum(len(_records(c.get('pins', []))) for c in conns)} pin(s)",
            }
        )
    for rec in _records(data.get("connections", [])):
        n = len(_records(rec.get("pairs", [])))
        rows.append(
            {
                "kind": "Connection",
                "item": f"{rec.get('a_connector', '')} - {rec.get('b_connector', '')}",
                "detail": f"{n} pair(s) of pins" + (f", {rec['name']}" if rec.get("name") else ""),
            }
        )
    return rows


def _device_rows(data: dict[str, Any], unit_id: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for rec in _records(data.get("devices", [])):
        unit = rec.get("unit", {})
        if not isinstance(unit, dict) or unit.get("id") != unit_id:
            continue
        for c in _records(rec.get("connectors", [])):
            pins = _records(c.get("pins", []))
            if not pins:
                rows.append(
                    {
                        "connector": str(c.get("name", c.get("id", ""))),
                        "pin": "",
                        "signal": "",
                        "function": "",
                    }
                )
            for p in pins:
                rows.append(
                    {
                        "connector": str(c.get("name", c.get("id", ""))),
                        "pin": str(p.get("id", "")),
                        "signal": str(p.get("signal") or ""),
                        "function": str(p.get("function") or ""),
                    }
                )
    return rows


# ---- saving (only when the person asks) ------------------------------------------------------


def _writable_folder(folder: Path) -> None:
    problem = _folder_problem(folder)
    if problem:
        raise LibraryError(problem)
    if not os.access(folder, os.W_OK):
        raise LibraryError(f"You may not write in the folder {folder}. Ask who owns the library.")


def save_devices(
    folder: Path | str,
    project: Project,
    unit_ids: list[str],
    *,
    replace: bool = False,
    new_ids: dict[str, str] | None = None,
    notes: list[str] | None = None,
) -> Path:
    """Add the devices to a device library file in the folder (`GYRO1.json` for one device,
    `devices.json` for several). A device with the same ID in that file that differs is not
    replaced: `LibraryConflict` says which and how much differs (`replace=True` replaces it,
    `new_ids={"GYRO1": "GYRO1-2"}` saves it under another ID). A part never gets a lower
    approval than the file has; what was kept is added to `notes`. Returns the path."""
    root = Path(folder)
    _writable_folder(root)
    path = root / dl.default_file_name(unit_ids)
    return dl.save_devices_to_file(
        path, project, unit_ids, replace=replace, new_ids=new_ids, notes=notes
    )


def save_subsystem(
    folder: Path | str,
    project: Project,
    unit_ids: list[str],
    name: str,
    description: str = "",
    notes: str = "",
) -> Path:
    """Write a subsystem library file in the folder. A file that exists is never replaced: the
    name must be a new one. Returns the path."""
    root = Path(folder)
    _writable_folder(root)
    data = sl.export_subsystem(project, unit_ids, name, description, notes)
    path = root / sl.default_file_name(name)
    if path.exists():
        raise LibraryError(
            f"The library has a subsystem file {path.name} already. Choose another name, "
            "or delete that file if it is out of date."
        )
    sl.write_subsystem(path, data)
    return path
