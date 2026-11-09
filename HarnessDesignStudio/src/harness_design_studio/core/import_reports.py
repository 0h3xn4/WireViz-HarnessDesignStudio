# SPDX-FileCopyrightText: 2026 0h3xn4
# SPDX-License-Identifier: GPL-3.0-only
"""The import report of each kind of import, made from the plan the importer made.

One function per importer (see `import_record`) turns its plan into what was read, dropped and
converted. Shared by the command line and the import wizard, so both say the same. Nothing here
changes a project.
"""

from collections.abc import Sequence
from pathlib import Path

from harness_design_studio.core.build_data_import import BuildDataPlan
from harness_design_studio.core.generate.lengths import LengthPlan
from harness_design_studio.core.import_record import (
    ImportReport,
    clean,
    heading,
    number_text,
    start_report,
    table_report,
)
from harness_design_studio.core.imports import ImportPlan
from harness_design_studio.core.kicad import Netlist, NetlistPlan
from harness_design_studio.core.library_import import PartsPlan, rating_columns
from harness_design_studio.core.model import Project
from harness_design_studio.core.pinout_import import PinoutPlan

Table = Sequence[Sequence[str]]
Root = Path | str | None

LENGTH_COLUMNS = {"harness": 0, "segment": 1, "length": 2}  # import-lengths reads by position
BUILD_KINDS = {
    "strips": "strip-lengths",
    "contacts": "pin-contacts",
    "accessories": "accessories",
    "tools": "part-tools",
}


def lengths_report(
    path: Path | str,
    root: Root,
    table: Table,
    plan: LengthPlan,
    *,
    unit: str,
    unit_given: bool,
    sheet: str | None = None,
    sha256: str | None = None,
) -> ImportReport:
    """Segment lengths: every accepted row is a converted value (what the file said, the unit,
    the metres stored), every refused row is a dropped row with its reason."""
    report = table_report("lengths", path, root, table, LENGTH_COLUMNS, sheet=sheet, sha256=sha256)
    report.unit, report.unit_given = unit, unit_given
    report.unit_what, report.unit_flag = "length", "--unit"
    for r in plan.rows:
        if r.ok and r.metres is not None:
            report.convert(
                row=r.row_number,
                field="length",
                read=r.values[2],
                unit=unit,
                stored=f"{number_text(r.metres)} m",
                item=f"{r.values[0]} / {r.values[1]}",
            )
        elif not r.ok:
            report.drop(r.row_number, r.message)
    return report


def parts_report(
    path: Path | str,
    root: Root,
    project: Project,
    table: Table,
    mapping: dict[str, int],
    plan: PartsPlan,
    *,
    mass_unit: str,
    unit_given: bool,
    sheet: str | None = None,
    sha256: str | None = None,
) -> ImportReport:
    """Approved parts: the columns read include the rating columns, a mass read in another unit
    than grams is a converted value."""
    ratings = rating_columns(project, list(table[0]) if table else [], mapping)
    every = {**mapping, **{f"ratings.{k}": i for k, i in ratings.items()}}
    report = table_report("parts", path, root, table, every, sheet=sheet, sha256=sha256)
    if "mass_g" in mapping or "mass_per_m_g" in mapping:
        report.unit, report.unit_given = mass_unit, unit_given
        report.unit_what, report.unit_flag = "mass", "--mass-unit"
    for r in plan.rows:
        if not r.ok:
            report.drop(r.row_number, r.message)
            continue
        for key, text, grams in r.converted:
            per_m = "/m" if key == "mass_per_m_g" else ""
            report.convert(
                row=r.row_number,
                field=key,
                read=text,
                unit=f"{mass_unit}{per_m}",
                stored=f"{number_text(grams)} g{per_m}",
                item=r.part_id,
            )
    return report


def build_data_report(
    path: Path | str,
    root: Root,
    table: Table,
    plan: BuildDataPlan,
    *,
    unit: str,
    unit_given: bool,
    sheet: str | None = None,
    sha256: str | None = None,
) -> ImportReport:
    """Build data: the kind comes from the headings; lengths are stored in millimetres, and a
    length that was converted, or whose decimal comma was read as a point, is listed."""
    report = table_report(
        BUILD_KINDS[plan.kind], path, root, table, plan.mapping, sheet=sheet, sha256=sha256
    )
    if {"strip_a_mm", "strip_b_mm", "length_mm"} & set(plan.mapping):
        report.unit, report.unit_given = unit, unit_given
        report.unit_what, report.unit_flag = "length", "--unit"
    ok_rows = {r.row_number for r in plan.rows if r.ok}
    for r in plan.rows:
        if not r.ok:
            report.drop(r.row_number, r.message)
    for n, key, text, said, mm in plan.conversions:
        if n in ok_rows:
            report.convert(row=n, field=key, read=text, unit=said, stored=f"{mm} mm")
    report.notes += plan.warnings
    return report


def pinout_report(
    path: Path | str,
    root: Root,
    table: Table,
    mapping: dict[str, int],
    plan: PinoutPlan,
    *,
    sheet: str | None = None,
    sha256: str | None = None,
) -> ImportReport:
    """A device pinout: the columns read are the ones `mapping` names (headings and --column)."""
    report = table_report("pinout", path, root, table, mapping, sheet=sheet, sha256=sha256)
    for r in plan.rows:
        if not r.ok:
            report.drop(r.row_number, r.message)
    return report


def interfaces_report(
    path: Path | str,
    root: Root,
    table: Table,
    mapping: dict[str, int],
    plan: ImportPlan,
    *,
    sheet: str | None = None,
    sha256: str | None = None,
) -> ImportReport:
    report = table_report("interfaces", path, root, table, mapping, sheet=sheet, sha256=sha256)
    for r in plan.rows:
        if not r.ok:
            report.drop(r.row_number, r.message)
    return report


def netlist_report(
    path: Path | str,
    root: Root,
    netlist: Netlist,
    plan: NetlistPlan,
    *,
    use_pin_type_direction: bool = False,
    sha256: str | None = None,
) -> ImportReport:
    """A KiCad netlist: one row per connector component. The design source (the name of the
    schematic file only) and the pin type of every imported pin are kept; the value and the
    footprint of the components are named as not imported."""
    report = start_report("netlist", path, root, rows_read=len(plan.rows), sha256=sha256)
    report.columns_ignored = list(plan.ignored_fields)
    if netlist.source:
        report.notes.append(
            "KiCad design source: " + clean(netlist.source.replace("\\", "/").rsplit("/", 1)[-1])
        )
    if use_pin_type_direction:
        report.notes.append(
            "The pin types input, output and bidirectional also set the direction of pins that "
            "had none."
        )
    report.pin_types = dict(plan.pin_types)
    for n, r in enumerate(plan.rows, start=1):
        if not r.ok:
            report.drop(n, f"{r.ref or '-'}: {r.message}")
    return report


def ampacity_report(
    path: Path | str,
    root: Root,
    table: Table,
    *,
    sheet: str | None = None,
    sha256: str | None = None,
) -> ImportReport:
    """The ampacity table (gauge, amperes), read by position; a heading row is optional."""
    first = table[0][0].strip() if table and table[0] else ""
    has_header = bool(table) and not first.lstrip("-").isdigit()
    report = start_report(
        "ampacity",
        path,
        root,
        rows_read=len(table) - (1 if has_header else 0),
        sheet=sheet,
        sha256=sha256,
    )
    head = list(table[0]) if has_header else []
    report.columns_read = [
        (heading(head, 0), "gauge (AWG)"),
        (heading(head, 1), "current (A)"),
    ]
    report.columns_ignored = [heading(head, i) for i in range(2, len(head))]
    report.unit, report.unit_what, report.unit_flag = "A", "current", ""
    return report


def library_file_report(
    kind: str,
    path: Path | str,
    root: Root,
    count: int,
    notes: Sequence[str] = (),
    *,
    sha256: str | None = None,
) -> ImportReport:
    """A device or subsystem library file: not a table; the report is the file and how many
    devices it held."""
    report = start_report(kind, path, root, rows_read=count, sha256=sha256)
    report.notes += list(notes)
    return report
