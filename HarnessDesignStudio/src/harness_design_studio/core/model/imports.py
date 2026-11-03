"""The import record: what each import read, dropped and converted (transparency work, D-193).

One record per source file and kind, kept in `imports/records.json`. The file is optional: a
project that never imported anything has none, and its files, its model hash and its outputs are
as they were. The record is *not* part of the model hash and is never written into an output file;
it is part of the project, so load, save, undo and the autosave journal carry it.

It holds no time and no operator (the tool never reads a clock into project data) and no absolute
path: the file name, and a path relative to the project folder only when the file lies inside it.
"""

from typing import Annotated, ClassVar, Literal

from pydantic import Field, StringConstraints

from .base import Entity, Label, Name, SparseEntity, Text

# the kinds of import the tool has (the file names of the templates where there is one)
ImportKind = Literal[
    "parts",
    "interfaces",
    "lengths",
    "strip-lengths",
    "pin-contacts",
    "accessories",
    "part-tools",
    "pinout",
    "netlist",
    "ampacity",
    "devices",
    "subsystem",
]
IMPORT_KINDS: tuple[str, ...] = (
    "parts", "interfaces", "lengths", "strip-lengths", "pin-contacts", "accessories",
    "part-tools", "pinout", "netlist", "ampacity", "devices", "subsystem",
)  # fmt: skip
KIND_WORDS: dict[str, str] = {
    "parts": "approved parts",
    "interfaces": "interfaces",
    "lengths": "segment lengths",
    "strip-lengths": "strip lengths",
    "pin-contacts": "pin contacts",
    "accessories": "accessories",
    "part-tools": "part tools",
    "pinout": "device pinout",
    "netlist": "KiCad netlist",
    "ampacity": "ampacity table",
    "devices": "device library",
    "subsystem": "subsystem library",
}
MAX_LISTED = 200  # rows listed in one record; the counts are always the whole number
Sha256 = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
Count = Annotated[int, Field(ge=0)]
RowNumber = Annotated[int, Field(ge=1)]


class ColumnUse(Entity):
    """A column of the file that was read, and the field it was read as."""

    column: Label  # the heading as the file wrote it ("(column 3)" when it had none)
    field: Name


class DroppedRow(Entity):
    """A row that was not imported, with the reason."""

    row: RowNumber  # 1-based, the heading row is row 1
    reason: Text


class ConvertedValue(SparseEntity):
    """A value that was converted: what the file said, the unit it was read in, what was stored."""

    OMIT_WHEN_DEFAULT: ClassVar[frozenset[str]] = frozenset({"item"})

    row: RowNumber
    field: Name
    read: Label  # the cell as written
    unit: Name  # the unit it was read in
    stored: Name  # the value as stored, with its unit (for example "0.005 m")
    item: Label = ""  # what the row is about (for example "H1 / S1")


class ImportRecord(SparseEntity):
    """What one import read, dropped and converted. `id` is `<kind>:<source name>`: importing the
    same source again replaces its record."""

    OMIT_WHEN_DEFAULT: ClassVar[frozenset[str]] = frozenset(
        {
            "source_path", "sheet", "unit", "unit_given", "columns_read", "columns_ignored",
            "rows_dropped", "rows_converted", "notes", "pin_types",
        }
    )  # fmt: skip

    id: Name
    kind: ImportKind
    source_name: Name  # the file name, no folder
    source_path: Name | None = None  # relative to the project folder, only when the file is inside
    sha256: Sha256  # of the source file's bytes
    sheet: Name | None = None  # the sheet of a workbook that was read
    tool_version: Name
    rows_read: Count
    columns_read: list[ColumnUse] = []
    columns_ignored: list[Label] = []
    dropped_count: Count = 0
    rows_dropped: list[DroppedRow] = []  # the first MAX_LISTED
    converted_count: Count = 0
    rows_converted: list[ConvertedValue] = []  # the first MAX_LISTED
    unit: Name | None = None  # the unit the values were read in (assumed, or given)
    unit_given: bool = False  # True: the person said it; False: the tool assumed it
    notes: list[Text] = []  # other things the import read from the source (the KiCad design source)
    pin_types: dict[Name, Name] = {}  # KiCad netlist: "J1.3" -> the pin type the netlist gave


def record_id(kind: str, source_name: str) -> str:
    return f"{kind}:{source_name}"


__all__ = [
    "IMPORT_KINDS",
    "KIND_WORDS",
    "MAX_LISTED",
    "ColumnUse",
    "ConvertedValue",
    "DroppedRow",
    "ImportKind",
    "ImportRecord",
    "record_id",
]
