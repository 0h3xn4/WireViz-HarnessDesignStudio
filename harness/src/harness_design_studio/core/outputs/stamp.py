"""Every artefact carries the generator version and the model hash it was made from."""

import csv
import io
import re
from dataclasses import dataclass

from harness_design_studio import __version__
from harness_design_studio.core.io.layout import model_hash
from harness_design_studio.core.model import Project


@dataclass(frozen=True)
class Stamp:
    version: str
    model_hash: str

    @property
    def short(self) -> str:
        return self.model_hash[:12]

    @property
    def line(self) -> str:
        return f"harness-design-studio {self.version} model {self.short}"


def stamp_of(project: Project) -> Stamp:
    return Stamp(__version__, model_hash(project))


Table = list[list[str]]  # first row is the header


_TRIGGERS = ("=", "+", "-", "@", "\t", "\r")
_PLAIN_NUMBER = re.compile(r"[+-]?(\d+\.?\d*|\.\d+)([eE][+-]?\d+)?")


def _safe(cell: str) -> str:
    """Spreadsheet programs run cells that start with = + - @ (or a tab or carriage return) as
    formulas; mark such text with a leading apostrophe. A plain number such as -5 is left alone.
    A cell that already starts with apostrophes followed by such a character gets one more, so
    `_unsafe` can always undo exactly one."""
    core = cell.lstrip("'")
    if core[:1] in _TRIGGERS and (core != cell or not _PLAIN_NUMBER.fullmatch(cell)):
        return "'" + cell
    return cell


def _unsafe(cell: str) -> str:
    """Inverse of `_safe`."""
    return cell[1:] if cell[:1] == "'" and cell.lstrip("'")[:1] in _TRIGGERS else cell


def csv_bytes(table: Table, stamp: Stamp) -> bytes:
    """CSV with LF line endings. The first line is a comment `# <stamp>`; readers skip lines
    starting with `#` (documented in docs/OUTPUTS.md)."""
    buf = io.StringIO()
    buf.write(f"# {stamp.line}\n")
    w = csv.writer(buf, lineterminator="\n")
    w.writerows([[_safe(c) for c in row] for row in table])
    return buf.getvalue().encode()


def parse_csv(data: bytes) -> Table:
    """Inverse of `csv_bytes` (used by the independent output verifier)."""
    lines = data.decode().splitlines(keepends=True)
    if lines and lines[0].startswith("# "):  # only the stamp line: a cell may hold "# ..." text
        lines = lines[1:]
    return [[_unsafe(c) for c in row] for row in csv.reader(io.StringIO("".join(lines)))]
