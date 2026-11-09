# SPDX-FileCopyrightText: 2026 0h3xn4
# SPDX-License-Identifier: GPL-3.0-only
"""Batch: generate, check and export several projects and write one summary table.

Run it with no arguments to try it on two of the bundled examples (made in a temporary folder), or
name the project folders you want::

    python batch_projects.py summary.csv path/to/project-a path/to/project-b

`generate` and `export` write into each project folder, exactly as the commands of the same name
do, so run it on copies or on projects kept in Git. The table has one row for each project and
is the same every time the design is the same: no time, no user name, no path.
"""

import csv
import sys
import tempfile
from pathlib import Path

from harness_design_studio.api import (
    create_project,
    export,
    generate,
    load_project,
    run_checks,
)

EXAMPLES = ("first-steps", "minimal-satellite")
COLUMNS = (
    "project",
    "devices",
    "interfaces",
    "harnesses",
    "wires",
    "generate_ok",
    "open_errors",
    "open_warnings",
    "open_notes",
    "output_files",
    "model_hash",
)


def process(folder: Path) -> dict[str, object]:
    """Generate, check and export one project; return its row of the table."""
    made = generate(folder)  # plans the harnesses and saves them (not when there is an error)
    checks = run_checks(folder)
    exported = export(folder)  # the build workbook and every table, without the PDF drawings
    project = load_project(folder)
    return {
        "project": project.meta.name,
        "devices": len(project.units),
        "interfaces": len(project.interfaces),
        "harnesses": len(project.harnesses),
        "wires": made.wires_checked,
        "generate_ok": made.ok,
        "open_errors": checks.open_errors,
        "open_warnings": checks.open_warnings,
        "open_notes": checks.open_notes,
        "output_files": len(exported.files),
        "model_hash": checks.model_hash,
    }


def write_table(rows: list[dict[str, object]], target: Path) -> Path:
    """One CSV file for all the projects."""
    with target.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    return target


def main(argv: list[str]) -> int:
    target = Path(argv[0]) if argv else Path("batch-summary.csv")
    if argv[1:]:
        write_table([process(Path(p)) for p in argv[1:]], target)
        return 0
    with tempfile.TemporaryDirectory() as work:  # no folders named: try the bundled examples
        rows = []
        for name in EXAMPLES:
            folder = Path(work) / name
            create_project(folder, name)
            rows.append(process(folder))
        write_table(rows, target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
