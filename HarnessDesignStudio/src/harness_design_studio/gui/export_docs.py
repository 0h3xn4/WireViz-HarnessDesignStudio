"""Which document is which: the output file names of `core.outputs.build.build_outputs` as document
types a person recognises ("Wire list", "Drawing sheets (SVG)", "Block diagram"), grouped by harness
and "System". The export dialog shows this as the harness x document tree, and the result list
names the document of every file with it.

The layout is the one `build_outputs` writes (a test builds a project and checks that every file is
recognised and every document type here occurs), so a new output file shows up as its own file name
until it is added below; nothing is ever hidden because it is unknown.
"""

import re
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Final, Literal

from harness_design_studio.core.outputs.buildsheet import FILE_SUFFIX as BUILD_SUFFIX

MANIFEST: Final = "manifest.json"  # written beside the outputs; never part of a copy
SYSTEM: Final = "system"  # the scope of the files that cover all harnesses together


@dataclass(frozen=True)
class DocType:
    key: str
    label: str
    kind: str  # the file kind in words: "CSV", "PDF", "SVG" ...


# Per harness: the build workbook first (the main output, D-169), then the others in the order
# build_outputs writes them. The workbooks and the drawings are named after the harness or the
# sheet size.
HARNESS_DOCS: Final[tuple[DocType, ...]] = (
    DocType("build", "Build workbook", "XLSX"),
    DocType("wirelist", "Wire list", "CSV"),
    DocType("pinouts", "Pinouts", "CSV"),
    DocType("bom", "Bill of materials", "CSV"),
    DocType("mass_length", "Mass and length", "CSV"),
    DocType("tests", "Test table", "CSV"),
    DocType("labels", "Labels", "CSV"),
    DocType("wireviz", "WireViz description", "YAML"),
    DocType("workbook", "Workbook (all tables)", "XLSX"),
    DocType("drawing_a4", "Drawing, A4", "PDF"),
    DocType("drawing_a3", "Drawing, A3", "PDF"),
    DocType("drawing_svg", "Drawing sheets, A3", "SVG"),
)
# Written only for a harness that has accessories (D-170), so not in the list every harness shows.
OPTIONAL_HARNESS_DOCS: Final[tuple[DocType, ...]] = (DocType("accessories", "Accessories", "CSV"),)
DRAWING_KEYS: Final = frozenset({"drawing_a4", "drawing_a3", "drawing_svg"})  # only with drawings
SYSTEM_DOCS: Final[tuple[DocType, ...]] = (
    DocType("sys_bom", "Bill of materials, all harnesses", "CSV"),
    DocType("sys_mass_length", "Mass and length, all harnesses", "CSV"),
    DocType("sys_mating", "Mating matrix", "CSV"),
    DocType("sys_traceability", "Traceability", "CSV"),
    DocType("sys_box_pinouts", "Unit connector pinouts", "CSV"),
    DocType("sys_drc_findings", "Design rule findings", "CSV"),
    DocType("sys_drc_report", "Design rule report", "Markdown"),
    DocType("sys_changelog", "Change log", "CSV"),
    DocType("sys_revision_report", "Revision report", "Markdown"),
    DocType("sys_export", "Project export", "JSON"),
    DocType("sys_provenance", "Provenance of the generated values", "JSON"),
    DocType("sys_workbook", "System workbook (all tables)", "XLSX"),
    DocType("sys_block_diagram", "Block diagram", "SVG and PDF"),
    DocType("sys_overview", "Harness overview", "SVG and PDF"),
)
MANIFEST_DOC: Final = DocType("manifest", "Manifest", "JSON")
DOCS: Final[dict[str, DocType]] = {d.key: d for d in (*HARNESS_DOCS, *OPTIONAL_HARNESS_DOCS, *SYSTEM_DOCS, MANIFEST_DOC)}

_HARNESS_FILES: Final = {
    "wirelist.csv": "wirelist",
    "pinouts.csv": "pinouts",
    "bom.csv": "bom",
    "mass_length.csv": "mass_length",
    "tests.csv": "tests",
    "labels.csv": "labels",
    "accessories.csv": "accessories",
    "wireviz.yaml": "wireviz",
    "drawing_A4.pdf": "drawing_a4",
    "drawing_A3.pdf": "drawing_a3",
}
_SYSTEM_FILES: Final = {
    "bom.csv": "sys_bom",
    "mass_length.csv": "sys_mass_length",
    "mating_matrix.csv": "sys_mating",
    "traceability.csv": "sys_traceability",
    "box_pinouts.csv": "sys_box_pinouts",
    "drc_findings.csv": "sys_drc_findings",
    "drc_report.md": "sys_drc_report",
    "changelog.csv": "sys_changelog",
    "revision_report.md": "sys_revision_report",
    "export.json": "sys_export",
    "provenance.json": "sys_provenance",
    "system.xlsx": "sys_workbook",
    "block_diagram.svg": "sys_block_diagram",
    "block_diagram.pdf": "sys_block_diagram",
    "harness_overview.svg": "sys_overview",
    "harness_overview.pdf": "sys_overview",
}
_SVG_SHEET = re.compile(r"drawing_A3_s(\d+)\.svg")


@dataclass(frozen=True)
class Document:
    """What one written file is: the scope it belongs to ("W001", "system", or "" for the
    manifest) and its document type."""

    rel: str
    scope: str
    key: str  # a key of `DOCS`, or the file name for a file this module does not know
    label: str
    kind: str


def classify(rel: str) -> Document:
    """The document a file of the output set is."""
    if rel == MANIFEST:
        return Document(rel, "", MANIFEST_DOC.key, MANIFEST_DOC.label, MANIFEST_DOC.kind)
    parts = rel.split("/")
    name = parts[-1]
    if len(parts) == 3 and parts[0] == "harnesses":
        hid = parts[1]
        key = _HARNESS_FILES.get(name)
        if key is None and name == f"{hid}.xlsx":
            key = "workbook"
        if key is None and name == f"{hid}{BUILD_SUFFIX}":
            key = "build"
        if key is None and _SVG_SHEET.fullmatch(name):
            key = "drawing_svg"
        if key is not None:
            d = DOCS[key]
            return Document(rel, hid, d.key, d.label, d.kind)
        return Document(rel, hid, rel, name, name.rpartition(".")[2].upper())
    if len(parts) == 2 and parts[0] == SYSTEM and name in _SYSTEM_FILES:
        d = DOCS[_SYSTEM_FILES[name]]
        return Document(rel, SYSTEM, d.key, d.label, d.kind)
    scope = parts[1] if len(parts) == 3 and parts[0] == "harnesses" else parts[0] if len(parts) > 1 else ""  # fmt: skip
    return Document(rel, scope, rel, name, name.rpartition(".")[2].upper() if "." in name else "")


def harness_docs(drawings: bool = True) -> tuple[DocType, ...]:
    """The document types of one harness; the drawings only when they are exported."""
    return HARNESS_DOCS if drawings else tuple(d for d in HARNESS_DOCS if d.key not in DRAWING_KEYS)


def planned_layout(
    harness_ids: Iterable[str], drawings: bool = True
) -> list[tuple[str, tuple[DocType, ...]]]:
    """The tree before anything is written: each harness with its document types, then the
    system documents."""
    docs = harness_docs(drawings)
    return [*((hid, docs) for hid in sorted(harness_ids)), (SYSTEM, SYSTEM_DOCS)]


SheetRef = tuple[Literal["harness"], str, str, int] | tuple[Literal["system"], str]


def sheet_ref(rel: str) -> SheetRef | None:
    """The drawing sheet a file shows, if it is one: ("harness", id, "A3", index) for a harness
    drawing (the first sheet of a PDF, the numbered sheet of an SVG), ("system", "block_diagram")
    or ("system", "harness_overview"). None for tables and other files."""
    parts = rel.split("/")
    name = parts[-1]
    if len(parts) == 3 and parts[0] == "harnesses":
        m = _SVG_SHEET.fullmatch(name)
        if m:
            return ("harness", parts[1], "A3", int(m.group(1)) - 1)
        if name in ("drawing_A4.pdf", "drawing_A3.pdf"):
            return ("harness", parts[1], name[8:10], 0)
    if len(parts) == 2 and parts[0] == SYSTEM:
        stem = name.rpartition(".")[0]
        if stem in ("block_diagram", "harness_overview") and name.endswith((".svg", ".pdf")):
            return ("system", stem)
    return None


def is_safe(rel: str) -> bool:
    """A path that stays inside the folder it is written to: relative, no "..", not the manifest."""
    parts = rel.split("/")
    return bool(rel) and not rel.startswith("/") and ".." not in parts and rel != MANIFEST
