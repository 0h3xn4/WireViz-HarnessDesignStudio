# SPDX-FileCopyrightText: 2026 0h3xn4
# SPDX-License-Identifier: GPL-3.0-only
"""`export-data`: every intermediate and final result as JSON and CSV (D-191, S5), and the
`--run-record` option of `generate` and `export`."""

import argparse
from pathlib import Path

from harness_design_studio import api
from harness_design_studio.cli.jsonout import Report
from harness_design_studio.core import run_record
from harness_design_studio.core.model import Project

COMMANDS = ("export-data",)

RUN_RECORD_HELP = (
    "also write run_record.json (time in UTC, operator, tool version, platform, Python version, "
    "model hash) next to the files: it is outside every hash, and written only with this option"
)
AUTHOR_HELP = (
    "with --run-record: who ran it (default: the environment variable HARNESS_AUTHOR, then the "
    "Git user.name, then the user of the system)"
)


def add_run_record_options(p: argparse.ArgumentParser) -> None:
    """`--run-record` and `--author`, worded the same for every command that has them."""
    p.add_argument("--run-record", action="store_true", help=RUN_RECORD_HELP)
    p.add_argument("--author", metavar="NAME", default=None, help=AUTHOR_HELP)


def register(sub: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    p = sub.add_parser(
        "export-data",
        help="write every intermediate and final result (wire sizing, rule results, lengths, mass, bill of materials and more) as JSON and CSV, so a number can be reproduced from the files alone",
        description="Write the numbers behind the outputs to FOLDER as open data. For each result "
        "a JSON file (with a format number, the tool version, the model hash, the columns with "
        "their units and the rows) and a CSV file with the same rows and the unit in each "
        "heading: wire_sizing (current, gauge and its cross-section in mm², ampacity, the "
        "derating factors, the bundle size, the limit, the length, the voltage drop and its "
        "limit and margin, the part), segmentation_groups and segmentation_interfaces, "
        "pin_allocation, rule_results (actual, limit, margin, verdict), readiness, lengths (with "
        "the basis of each), mass and mass_wires, bom and bom_contributions, findings, "
        "test_limits and settings (every setting in force with its value, unit and origin); "
        "also configuration.json (the configuration files as the tool used them, with their "
        "placeholder flags) and provenance.json (tool version, model hash, the files imported, "
        "and a hash of every other file written). No file holds a time, a user name or a path, "
        "so the same design written twice gives the same bytes. With --run-record, "
        "run_record.json is written beside them (time, operator, tool version): it is not part "
        "of the set. The project is not changed. `--json` prints the list of files.",
    )
    p.add_argument("project", type=Path, help="project folder")
    p.add_argument(
        "--out", type=Path, required=True, help="the folder for the files (made if missing)"
    )
    add_run_record_options(p)
    p.add_argument("--json", action="store_true", help="print the list of files as JSON")


def write_record(
    project: Project, project_folder: Path, target: Path, args: argparse.Namespace, rep: Report
) -> None:
    """With `--run-record`, write the record of this run into `target` and say so (and, with
    `--json`, name the file in the document under `run_record`)."""
    if not args.run_record:
        return
    path = run_record.write_for(
        project, target, operator=args.author, project_folder=project_folder
    )
    rep.say(f"The record of this run (time, operator, versions) is {path}.")
    rep.put(run_record=path.name)


def run(args: argparse.Namespace) -> int:
    rep = Report(args.json)
    written = api.export_data(
        args.project, args.out, run_record=args.run_record, operator=args.author
    )
    rep.say(
        f"{written.count} data files written to {args.out} (model {written.model_hash})."
        + (f" The record of this run is {written.run_record}." if written.run_record else "")
    )
    rep.put(**written.to_dict())
    return rep.finish(0)
