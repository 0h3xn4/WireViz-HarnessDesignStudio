# SPDX-FileCopyrightText: 2026 0h3xn4
# SPDX-License-Identifier: GPL-3.0-only
"""`workflow`, `asbuilt`, `import-asbuilt` and `export-asbuilt`: the steps of the tool and what each
uses and makes, and what the technicians recorded about the build (S9, R6)."""

import argparse
import sys
from pathlib import Path

from harness_design_studio.cli import blocked_text
from harness_design_studio.cli.jsonout import Report, add_json_flag
from harness_design_studio.core import asbuilt, workflow
from harness_design_studio.core.commands import History
from harness_design_studio.core.edit import EditError
from harness_design_studio.core.errors import HarnessError, TransactionError
from harness_design_studio.core.import_record import RECORDS_FILE
from harness_design_studio.core.imports import ImportError_
from harness_design_studio.core.io.loader import load_project
from harness_design_studio.core.io.saver import save_project

COMMANDS = ("workflow", "asbuilt", "import-asbuilt", "export-asbuilt")


def register(sub: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    w = sub.add_parser(
        "workflow",
        help="list the steps of the tool, what each uses and makes, the intermediates you can look at, and where the project stands in each",
        description="The workflow in one table: define the devices, connect them, set the engineering "
        "values, generate, check, enter the build data, write the outputs, release, record what was "
        "built. For each step: what it uses (project files, configuration, outputs), what it makes, "
        "the command and the place on screen, the intermediate results you can look at and, where the "
        "tool allows it, change (the sizing of a wire, the segmentation groups, the pin allocation, "
        "the readiness checks, the derived lengths), and where the project stands: done, to do, "
        "pending (values or build data are missing), stale (older than the design), needs attention "
        "(a check failed, an as-built value is out of its limit) or blocked (with the steps before it "
        "that are not done). The status is worked out from the project and, with --outputs, from "
        "the folder the outputs were written to; nothing is changed. The same table is the page "
        "docs/user-manual/follow-the-workflow.md.",
    )
    w.add_argument("project", type=Path, help="project folder")
    w.add_argument("--outputs", type=Path, default=None, metavar="FOLDER", help="the folder the outputs were written to (default: <project>/outputs)")  # fmt: skip
    add_json_flag(w)

    a = sub.add_parser(
        "asbuilt",
        help="report what was recorded about the build: complete, missing, out of the test limits, different from the design",
        description="Report the as-built records of a project (asbuilt/records.json): for each harness "
        "that has records, what is recorded, what is missing (serial number, who built and "
        "inspected, the lot of each part, the cut and strip lengths, the crimp tool and its "
        "calibration ID, the result and measured value of each test), each measured value against "
        "the test limits of the project (actual, limit, margin), and each cut or strip length "
        "against the designed value (no tolerance is applied unless the project sets asbuilt_cut_tolerance_mm or asbuilt_strip_tolerance_mm: the difference is listed, or, with a tolerance, within it or out of it). A value "
        "that is out of its limit is shown as such and stays so until a person records "
        "something else; the tool does not accept it and does not say that a harness passed or is "
        "compliant. A harness with no record is 'not started'. Exit code 1 when a value is out of its "
        "limit, or, with --complete, when anything is missing. `--json` prints the report as one "
        "document. The same report is written as system/asbuilt_report.md and .csv by `export` "
        "(only for a project that has records) and is the As-built sheet of the build workbook.",
    )
    a.add_argument("project", type=Path, help="project folder")
    a.add_argument("--complete", action="store_true", help="end with exit code 1 also when a value is missing")  # fmt: skip
    add_json_flag(a)

    i = sub.add_parser(
        "import-asbuilt",
        help="read the as-built sheet (CSV, TSV, XLSX) a technician filled in and keep its records in the project",
        description="Read a sheet written by `export-asbuilt` (or any table with the same headings) "
        "and keep what is in it in asbuilt/records.json. The columns are found by their headings; "
        "the unit of a number column is the one in its heading (m, mm, cm, in or ft for lengths; ohm "
        "or mOhm; Mohm or Gohm; V or kV) and every value that is converted, and every decimal comma "
        "that is read as a point, is listed. An empty cell never clears a recorded value. A row about "
        "a harness, wire, connector, pin or test that the design does not have is refused with the "
        "reason; if any row is refused, nothing is changed. The command echoes what it read, "
        "dropped and converted, and records the file (name, SHA-256, rows, conversions) in "
        "imports/records.json. When the project keeps a change journal, the records are entered in "
        "it with who and when; the records themselves hold neither. The records are not part of the "
        "model hash.",
    )
    i.add_argument("project", type=Path, help="project folder")
    i.add_argument("file", type=Path, help="the filled-in sheet (.csv, .tsv, .json or .xlsx)")
    i.add_argument("--dry-run", action="store_true", help="show the preview only")
    add_json_flag(i)

    e = sub.add_parser(
        "export-asbuilt",
        help="write the sheet a technician fills in: one row for each thing to record, the designed values filled in, the as-built columns empty",
        description="Write the as-built sheet to FILE (.csv or .xlsx): for each harness (or the one "
        "named with --harness) a row for the harness, each part lot, each wire (with its designed "
        "length and strip lengths), each connector, each crimped pin in use and each test of the "
        "Tests sheet (with its limit); the as-built columns are empty, or hold what is recorded "
        "already, so the sheet can be filled in again. Fill it in and read it back with "
        "`import-asbuilt`. The project is not changed.",
    )
    e.add_argument("project", type=Path, help="project folder")
    e.add_argument("file", type=Path, help="the sheet to write (.csv or .xlsx)")
    e.add_argument("--harness", default=None, metavar="ID", help="only this harness (default: all)")  # fmt: skip
    add_json_flag(e)


def mutates(args: argparse.Namespace) -> bool:
    """Whether the command writes the project (it then takes the project lock)."""
    return args.command == "import-asbuilt" and not args.dry_run


def run(args: argparse.Namespace) -> int:
    rep = Report(args.json)
    try:
        code = {
            "workflow": _workflow,
            "asbuilt": _asbuilt,
            "import-asbuilt": _import,
            "export-asbuilt": _export,
        }[args.command](args, rep)
    except TransactionError as exc:  # blocked, for example by a release
        print(blocked_text(exc), file=sys.stderr)
        return 1
    except (HarnessError, ImportError_, EditError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return rep.finish(code)


def _workflow(args: argparse.Namespace, rep: Report) -> int:
    project = load_project(args.project).project
    folder = args.outputs if args.outputs is not None else args.project / "outputs"
    report = workflow.workflow_report(project, folder)
    rep.put(**report.to_dict())
    marks = {"done": "done", "todo": "to do", "pending": "pending", "stale": "stale", "attention": "needs attention", "blocked": "blocked"}  # fmt: skip
    for n, (step, status) in enumerate(report.steps, start=1):
        rep.say(f"{n}. {step.title}: {marks[status.state]}. {status.detail}")
        if status.blocked_by:
            rep.say(f"   Blocked by: {', '.join(workflow.step(k).title for k in status.blocked_by)}.")  # fmt: skip
        rep.say(f"   Does: {step.does}")
        rep.say("   Uses: " + "; ".join(i.name for i in step.consumes))
        rep.say("   Makes: " + "; ".join(i.name for i in step.produces))
        if step.command:
            rep.say(f"   Command: harness-design-studio {step.command}")
        for item in step.inspect:
            rep.say(f"   Look at: {item.what} - {item.how}" + (f" (change: {item.change})" if item.change else ""))  # fmt: skip
    return 0


def _asbuilt(args: argparse.Namespace, rep: Report) -> int:
    project = load_project(args.project).project
    report = asbuilt.asbuilt_report(project)
    rep.put(**report.to_dict())
    if not report.has_records:
        rep.say("No as-built record in this project. `export-asbuilt` writes the sheet to fill in; `import-asbuilt` reads it back.")  # fmt: skip
        return 0
    for s in report.harnesses:
        if not s.started:
            rep.say(f"{s.harness_id}: not started")
            continue
        rep.say(
            f"{s.harness_id}: {'complete' if s.complete else 'incomplete'}; {s.recorded} of {s.needed} values recorded, "
            f"{s.missing} missing, {s.out_of_limit} out of limit, {s.within_limit} within limit, "
            f"{s.differs} different from the design, {s.not_compared} not compared, {s.stale} stale."
        )
    for status in (
        asbuilt.OUT,
        asbuilt.STALE,
        asbuilt.DIFFERS,
        asbuilt.NOT_COMPARED,
        asbuilt.MISSING,
    ):
        for ln in report.lines:
            if ln.status == status:
                what = f"{ln.harness_id} {ln.kind} {ln.subject}: {ln.field}"
                detail = ln.text or (f"{ln.actual} (designed or limit {ln.designed} {ln.unit})" if ln.status != asbuilt.MISSING else "to record")  # fmt: skip
                rep.say(f"{status.upper()}: {what}: {detail}")
    if report.out_of_limit:
        return 1
    return 1 if args.complete and (report.missing or not report.complete) else 0


def _import(args: argparse.Namespace, rep: Report) -> int:
    project = load_project(args.project).project
    if project.read_only:
        print("error: this project is read-only (saved by a newer tool version).", file=sys.stderr)
        return 2
    imp = asbuilt.read_import(project, args.file, args.project)
    for line in imp.report.lines():
        rep.say(line)
    plan = imp.plan
    counts = plan.counts()
    for r in plan.rows:
        rep.say(f"row {r.row_number}: {'OK ' + r.message if r.ok else 'ERROR ' + r.message}")
    rep.say(f"{counts['added']} added, {counts['changed']} changed, {counts['unchanged']} unchanged, {counts['refused']} refused, {counts['skipped']} left out (nothing recorded in them).")  # fmt: skip
    rep.put(
        dry_run=args.dry_run,
        changed=False,
        counts=counts,
        rows=[
            {
                "row": r.row_number,
                "ok": r.ok,
                "target": r.target,
                "action": r.action,
                "message": r.message,
            }
            for r in plan.rows
        ],  # fmt: skip
    )
    if rep.as_json:
        rep.put(**{"import": {**imp.report.record().model_dump(mode="json"), "record_written": False}})  # fmt: skip
    if counts["refused"]:
        rep.say("Nothing was changed.")
        return 1
    if args.dry_run:
        rep.say("Dry run: nothing was changed.")
        return 0
    if not imp.ops:
        rep.say("Already up to date.")
        return 0
    History(project).execute("Import as-built records", imp.ops)
    save_project(project, args.project)
    rep.say(f"As-built records kept in asbuilt/records.json; import record {imp.report.record_id} written to {RECORDS_FILE}.")  # fmt: skip
    rep.put(changed=True)
    if rep.as_json:
        rep.doc["import"]["record_written"] = True
    return 0


def _export(args: argparse.Namespace, rep: Report) -> int:
    project = load_project(args.project).project
    if not args.file.parent.is_dir():
        print(f"error: the folder {args.file.parent} does not exist; make it first or choose another place.", file=sys.stderr)  # fmt: skip
        return 2
    data = asbuilt.template_bytes(project, args.file.suffix, args.harness)
    rows = asbuilt.template_rows(project, args.harness)
    args.file.write_bytes(data)
    rep.say(f"{len(rows) - 1} rows written to {args.file}. Fill in the as-built columns and read the sheet back with `import-asbuilt`.")  # fmt: skip
    rep.put(rows=len(rows) - 1, columns=list(rows[0]), written=args.file.name)
    return 0
