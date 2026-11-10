# SPDX-FileCopyrightText: 2026 0h3xn4
# SPDX-License-Identifier: GPL-3.0-only
"""Every artefact carries the generator version and the model hash it was made from."""

import csv
import io
import re
from dataclasses import dataclass

from harness_design_studio import __version__
from harness_design_studio.core import legal_texts
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

    @property
    def meta(self) -> str:
        """The stamp and the notice in one line (the description of an SVG, the data of a PDF)."""
        return f"{self.line}. {self.notice}"

    @property
    def notice(self) -> str:
        """The short notice every generated document carries (decision D-210): the tool, its
        version and "Provided as is, without warranty. Verify before use."."""
        return legal_texts.output_notice("harness-design-studio", self.version)


def stamp_of(project: Project) -> Stamp:
    return Stamp(__version__, model_hash(project))


Table = list[list[str]]  # first row is the header


def with_notice(markdown: str, stamp: Stamp) -> str:
    """A Markdown report with the notice as a visible note under its first line (the stamp as an
    HTML comment)."""
    first, _, rest = markdown.partition("\n")
    return f"{first}\n> {stamp.notice}\n\n{rest}"


def readme_text(stamp: Stamp) -> str:
    """`README.txt` of an outputs folder: the notice and where each kind of file carries it. The
    JSON files cannot hold a comment, so for them this file is where the notice is (D-210)."""
    return (
        "Harness Design Studio: the written files of this folder\n"
        "======================================================\n\n"
        f"{stamp.line}\n{stamp.notice}\n\n"
        f"{legal_texts.DISCLAIMER}\n\n{legal_texts.INTENDED_USE}\n\n"
        "Where the notice is: a comment line at the top of every .csv and .yaml file; a notes row "
        "(the sheet About, and under the title of a build workbook) and the print footer of every "
        ".xlsx file; a line in the title block or at the top of every drawing (.svg and .pdf); a "
        "note under the first line of every .md report. The .json files (system/export.json and "
        "system/provenance.json) and the open data cannot hold a comment: for them the notice is "
        "this file.\n\n"
        "Pending and placeholder values stay marked in the files: pending, (example data), "
        "PLACEHOLDER, Complete: no, not checked.\n"
    )


NOTICE_TAIL = legal_texts.OUTPUT_NOTICE.split(". ", 1)[1]  # the end of every notice line


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


unescape_cell = _unsafe  # for the importers: they read the tool's own CSV files back (D-193)


def csv_bytes(table: Table, stamp: Stamp, delimiter: str = ",") -> bytes:
    """CSV with LF line endings (`delimiter` "\\t" for a .tsv file). The first two lines are comments:
    `# <stamp>` and `# <notice>`; readers skip lines starting with `#` (documented in docs/OUTPUTS.md)."""
    buf = io.StringIO()
    buf.write(f"# {stamp.line}\n# {stamp.notice}\n")
    w = csv.writer(buf, lineterminator="\n", delimiter=delimiter)
    w.writerows([[_safe(c) for c in row] for row in table])
    return buf.getvalue().encode()


def parse_csv(data: bytes) -> Table:
    """Inverse of `csv_bytes` (used by the independent output verifier)."""
    lines = data.decode().splitlines(keepends=True)
    if lines and lines[0].startswith("# "):  # only the stamp line: a cell may hold "# ..." text
        lines = lines[1:]
        if lines and lines[0].startswith("# ") and lines[0].rstrip("\r\n").endswith(NOTICE_TAIL):
            lines = lines[1:]  # and the notice line under it
    return [[_unsafe(c) for c in row] for row in csv.reader(io.StringIO("".join(lines)))]
