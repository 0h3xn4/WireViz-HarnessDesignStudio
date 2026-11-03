"""What an import records, and whether its source file has changed since.

Transparency work, step 6 (D-191, D-193; requirements R14 and R5 of the audit).

    report = start_report("lengths", path, root, rows_read=12)
    report.read_columns(header, {"harness": 0, "segment": 1, "length": 2})
    report.convert(row=2, field="length", read="5.0", unit="mm", stored="0.005 m", item="H1 / S1")
    for line in report.lines(): print(line)                      # the echo
    ops = record_ops(project, report.record())                  # one Put, or [] when unchanged

An `ImportReport` is what an importer found out about its file: the rows and columns it read, the
rows it dropped and why, the values it converted, the unit it assumed or was given. The echo
(`lines`) tells a person; `record()` is the same facts as a project entity (`imports/records.json`).
Neither holds a time, an operator or an absolute path: the tool never reads a clock into project
data, and a path is kept only when the file lies inside the project folder, relative to it.

`check_sources` compares the SHA-256 of every recorded source that can be reached now with the one
recorded, so a person can see that a file changed after it was imported.
"""

import hashlib
import unicodedata
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from harness_design_studio import __version__
from harness_design_studio.core.commands import Op, Put
from harness_design_studio.core.model import ImportRecord, Project
from harness_design_studio.core.model.imports import (
    KIND_WORDS,
    MAX_LISTED,
    ColumnUse,
    ConvertedValue,
    DroppedRow,
    record_id,
)

RECORDS_FILE = "imports/records.json"
ROW_NOUNS = {"netlist": "connector", "devices": "device", "subsystem": "device"}
ROW_PARTS = {"netlist": "component field"}  # what a thing that is left out is called
_BLOCK = 1 << 20


def clean(text: str, limit: int = 200) -> str:
    """`text` as something a record may hold: control, private-use and line-separator characters
    become a space, and a long text is cut with an ellipsis."""
    out = "".join(
        " " if unicodedata.category(c) in ("Cc", "Cs", "Co") or c in "  ﻿￾￿" else c for c in text
    ).strip()
    if len(out) > limit:
        out = out[: limit - 1].rstrip() + "…"
    return out


def number_text(value: float) -> str:
    """A stored number as plain digits, without trailing zeros (0.005, 12.7, 3)."""
    text = format(value, ".9f").rstrip("0").rstrip(".")
    return text or "0"


def file_sha256(path: Path | str) -> str:
    """The SHA-256 of a file's bytes, as 64 hexadecimal characters."""
    digest = hashlib.sha256()
    with Path(path).open("rb") as fh:
        while block := fh.read(_BLOCK):
            digest.update(block)
    return digest.hexdigest()


def project_relative(path: Path | str, root: Path | str | None) -> str | None:
    """`path` relative to the project folder (with `/`), or None when the file is not inside it
    (or the project has no folder yet): an absolute path is never kept."""
    if root is None:
        return None
    try:
        return Path(path).resolve().relative_to(Path(root).resolve()).as_posix()
    except ValueError, OSError:
        return None


def heading(header: Sequence[str], index: int) -> str:
    """The heading of column `index` as a record keeps it ("(column 3)" for a blank one)."""
    text = clean(header[index]) if 0 <= index < len(header) else ""
    return text or f"(column {index + 1})"


@dataclass(frozen=True)
class Conversion:
    """One value the import converted."""

    row: int
    field: str
    read: str
    unit: str
    stored: str
    item: str = ""

    def text(self) -> str:
        return f"{self.read} {self.unit} = {self.stored}" if self.read else f"({self.unit})"


@dataclass
class ImportReport:
    """Everything an importer found out about its source."""

    kind: str
    source_name: str
    sha256: str
    rows_read: int
    source_path: str | None = None
    sheet: str | None = None
    columns_read: list[tuple[str, str]] = field(default_factory=list)  # (heading, field)
    columns_ignored: list[str] = field(default_factory=list)
    dropped: list[tuple[int, str]] = field(default_factory=list)  # (row, reason)
    converted: list[Conversion] = field(default_factory=list)
    unit: str | None = None
    unit_given: bool = False
    unit_what: str = "values"  # what the unit is the unit of ("length", "mass" ...), for the echo
    unit_flag: str = ""  # the option that says it ("--unit"), for the echo
    notes: list[str] = field(default_factory=list)
    pin_types: dict[str, str] = field(default_factory=dict)

    @property
    def record_id(self) -> str:
        return record_id(self.kind, clean(self.source_name, 150))

    def read_columns(
        self, header: Sequence[str], mapping: Mapping[str, int], skip: Iterable[int] = ()
    ) -> None:
        """Which columns were read as which field, and which were left out. `skip` are columns that
        are neither (for example the empty cells of a workbook past the last heading)."""
        used = {index: name for name, index in mapping.items()}
        self.columns_read = [(heading(header, i), used[i]) for i in sorted(used)]
        left = set(skip)
        self.columns_ignored = [
            heading(header, i) for i in range(len(header)) if i not in used and i not in left
        ]

    def drop(self, row: int, reason: str) -> None:
        self.dropped.append((row, reason))

    def convert(
        self, *, row: int, field: str, read: str, unit: str, stored: str, item: str = ""
    ) -> None:
        self.converted.append(Conversion(row, field, read, unit, stored, item))

    def record(self) -> ImportRecord:
        """The facts as a project entity (at most `MAX_LISTED` rows of each list)."""
        return ImportRecord(
            id=self.record_id,
            kind=self.kind,  # type: ignore[arg-type]
            source_name=clean(self.source_name, 150),
            source_path=clean(self.source_path, 190) if self.source_path else None,
            sha256=self.sha256,
            sheet=clean(self.sheet) if self.sheet else None,
            tool_version=__version__,
            rows_read=self.rows_read,
            columns_read=[ColumnUse(column=c, field=f) for c, f in self.columns_read],
            columns_ignored=list(dict.fromkeys(self.columns_ignored)),
            dropped_count=len(self.dropped),
            rows_dropped=[
                DroppedRow(row=n, reason=clean(why, 1000) or "no reason given")
                for n, why in self.dropped[:MAX_LISTED]
            ],
            converted_count=len(self.converted),
            rows_converted=[
                ConvertedValue(
                    row=c.row,
                    field=c.field,
                    read=clean(c.read),
                    unit=c.unit,
                    stored=c.stored,
                    item=clean(c.item),
                )
                for c in self.converted[:MAX_LISTED]
            ],
            unit=self.unit,
            unit_given=self.unit_given,
            notes=[clean(n, 1000) for n in self.notes[:MAX_LISTED]],
            pin_types={clean(k): clean(v) for k, v in sorted(self.pin_types.items())},
        )

    def lines(self, *, converted: bool = True, already_warned: Iterable[str] = ()) -> list[str]:
        """The echo, one line each: what was read, the unit, the values converted (all of them
        unless `converted` is False) and a warning for every column that was left out (except the
        ones in `already_warned`, which the importer has named itself)."""
        what = KIND_WORDS.get(self.kind, self.kind)
        noun = ROW_NOUNS.get(self.kind, "row")
        sheet = f", sheet '{self.sheet}'" if self.sheet else ""
        out = [
            f"Read {self.rows_read} {noun}(s) of {what} from {self.source_name}{sheet} "
            f"(sha256 {self.sha256[:12]})."
        ]
        if self.columns_read:
            out.append("Columns read: " + ", ".join(f"{c} -> {f}" for c, f in self.columns_read))
        warned = {h.casefold() for h in already_warned}
        part = ROW_PARTS.get(self.kind, "column")
        for h in self.columns_ignored:
            if h.casefold() not in warned:
                out.append(f"warning: the {part} '{h}' is not read; its values are not imported.")
        if self.unit:
            how = (
                f"given with {self.unit_flag}"
                if self.unit_given
                else (f"assumed; {self.unit_flag} says another" if self.unit_flag else "assumed")
            )
            out.append(f"Unit: {self.unit_what} in {self.unit} ({how}).")
        if converted:
            out += [
                f"Converted, row {c.row}" + (f" ({c.item})" if c.item else "") + f": {c.text()}"
                for c in self.converted
            ]
        out += [f"note: {n}" for n in self.notes]
        return out

    def summary(self) -> str:
        return (
            f"{self.rows_read} read, {len(self.dropped)} dropped, {len(self.converted)} converted"
        )


def start_report(
    kind: str,
    path: Path | str,
    root: Path | str | None,
    *,
    rows_read: int,
    sheet: str | None = None,
    sha256: str | None = None,
) -> ImportReport:
    """An empty report for the file at `path`: its name, its path inside the project folder (None
    when outside), its SHA-256 (`sha256` when the caller has it already)."""
    p = Path(path)
    return ImportReport(
        kind=kind,
        source_name=p.name,
        sha256=sha256 or file_sha256(p),
        rows_read=rows_read,
        source_path=project_relative(p, root),
        sheet=sheet,
    )


def table_report(
    kind: str,
    path: Path | str,
    root: Path | str | None,
    table: Sequence[Sequence[str]],
    mapping: Mapping[str, int],
    *,
    sheet: str | None = None,
    first_data_row: int = 1,
    sha256: str | None = None,
) -> ImportReport:
    """The report of a table import: the rows after the heading row (from `first_data_row`), and
    the columns read by `mapping` (field -> column index)."""
    report = start_report(
        kind, path, root, rows_read=max(0, len(table) - first_data_row), sheet=sheet, sha256=sha256
    )
    if table:
        report.read_columns(table[0], mapping)
    return report


# ---- the record in the project -----------------------------------------------------------------


def record_ops(project: Project, record: ImportRecord) -> list[Op]:
    """The operation that stores `record`, replacing the earlier record of the same kind and source;
    none when the project holds this very record already (so importing the same file again does not
    change the project)."""
    if project.import_records.get(record.id) == record:
        return []
    return [Put("import_records", record)]


# ---- has a source changed? ---------------------------------------------------------------------

UNCHANGED = "unchanged"
CHANGED = "changed"
MISSING = "missing"
UNCHECKED = "unchecked"
STATUS_WORDS = {
    UNCHANGED: "unchanged",
    CHANGED: "source changed",
    MISSING: "source not found",
    UNCHECKED: "not checked (no path)",
}


@dataclass(frozen=True)
class SourceCheck:
    """One record and what is found now at its source."""

    record: ImportRecord
    status: str  # UNCHANGED, CHANGED, MISSING or UNCHECKED
    current_sha256: str | None = None
    path: str = ""  # where it was looked for ("" when nowhere)

    @property
    def word(self) -> str:
        return STATUS_WORDS[self.status]


Hasher = Callable[[Path], str]


def check_sources(
    project: Project,
    root: Path | str | None,
    given: Sequence[Path | str] = (),
    *,
    hasher: Hasher = file_sha256,
) -> list[SourceCheck]:
    """Compare the current SHA-256 of every recorded source with the recorded one.

    A source is reachable by its path inside the project folder, or by a file the person names in
    `given` (matched to the records with the same file name). A record with neither is `unchecked`,
    a reachable path with no file is `missing`. Records are listed in the order of their IDs."""
    named: dict[str, Path] = {}
    for g in given:
        named.setdefault(Path(g).name, Path(g))
    base = Path(root).resolve() if root is not None else None
    out: list[SourceCheck] = []
    for rid in sorted(project.import_records):
        rec = project.import_records[rid]
        target: Path | None = named.get(rec.source_name)
        if target is None and rec.source_path and base is not None:
            candidate = (base / rec.source_path).resolve()
            if candidate.is_relative_to(
                base
            ):  # a hand-edited record cannot point out of the folder
                target = candidate
        if target is None:
            out.append(SourceCheck(rec, UNCHECKED))
            continue
        try:
            now = hasher(target)
        except OSError:
            out.append(SourceCheck(rec, MISSING, None, str(target)))
            continue
        out.append(SourceCheck(rec, UNCHANGED if now == rec.sha256 else CHANGED, now, str(target)))
    return out


class CachedHasher:
    """`file_sha256` that reads a file again only when its size or modification time changed
    (the editor asks on every refresh of its status)."""

    def __init__(self) -> None:
        self._seen: dict[Path, tuple[int, int, str]] = {}

    def __call__(self, path: Path) -> str:
        info = path.stat()
        key = (info.st_size, info.st_mtime_ns)
        hit = self._seen.get(path)
        if hit is not None and hit[:2] == key:
            return hit[2]
        digest = file_sha256(path)
        self._seen[path] = (*key, digest)
        return digest


def changed_sources(checks: Iterable[SourceCheck]) -> list[SourceCheck]:
    return [c for c in checks if c.status == CHANGED]


__all__ = [
    "CHANGED",
    "MISSING",
    "RECORDS_FILE",
    "STATUS_WORDS",
    "UNCHANGED",
    "UNCHECKED",
    "CachedHasher",
    "Conversion",
    "ImportReport",
    "SourceCheck",
    "changed_sources",
    "check_sources",
    "clean",
    "file_sha256",
    "heading",
    "number_text",
    "project_relative",
    "record_ops",
    "start_report",
    "table_report",
]
