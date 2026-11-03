"""`journal`, `override` and `deviation`: the change journal, deliberate overrides of generated values
and recorded deviations (D-191, S4)."""

import argparse
import sys
from pathlib import Path

from harness_design_studio.cli import blocked_text
from harness_design_studio.cli.jsonout import Report, add_json_flag
from harness_design_studio.core import change_ops, journal, records, wires
from harness_design_studio.core.derive import render
from harness_design_studio.core.edit import EditError
from harness_design_studio.core.errors import TransactionError
from harness_design_studio.core.io.loader import load_project
from harness_design_studio.core.io.saver import save_project

COMMANDS = ("journal", "override", "deviation")


def register(sub: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    j = sub.add_parser(
        "journal",
        help="print the change journal of a project (who changed what, when, from what to what and why); --start begins one",
        description="The change journal: an entry for every change of a design input, a configuration "
        "value, an override, a waiver or deviation, a part approval and a release, with who made it, "
        "when (UTC), the value before and after, and the reason where the model holds one. Entries "
        "are made when the project is saved, so every way of changing it is recorded; generation is "
        "one entry for each harness. The journal is the file journal.json, which a project has only "
        "if you start one (`new` starts one; `--start` starts one for an existing project): it is "
        "append-only, an entry cannot be changed or removed, and a damaged journal is reported by "
        "`validate`. It is not part of the model hash or of any written output. The author is the "
        "global option `--author`, else the environment variable HARNESS_AUTHOR, else the name Git "
        "has (`user.name`), else the user of the computer. `--json` prints the entries as one document; "
        "`--object` selects one object (W001-001, wire:W001-001, derating.bundle_derating); "
        "`--since SEQ` the entries after number SEQ.",
    )
    j.add_argument("project", type=Path, help="project folder")
    add_json_flag(j)
    j.add_argument(
        "--since", type=int, default=0, metavar="SEQ", help="only entries numbered above SEQ"
    )
    j.add_argument("--object", default=None, metavar="ID", help="only entries about this object")
    j.add_argument("--start", action="store_true", help="start a journal for a project that has none (writes journal.json)")  # fmt: skip

    o = sub.add_parser(
        "override",
        help="set a gauge, wire type, colour or length of a generated wire in place of the design's value, with a reason; or give it back",
        description="Override a value of a generated wire deliberately: `override DIR WIRE FIELD VALUE "
        "--reason TEXT` (FIELD is gauge_awg, part_id, colour or length_m). A reason is required and is "
        "refused when it is empty. The tool keeps the value when the harnesses are generated again, "
        "records the reason with the wire (who and when in the journal), flags the wire everywhere, "
        "and explains the consequences: the value the design would give, and the current limit and "
        "voltage drop of the value you set. `--clear FIELD` gives one field back to generation (the "
        "value is cleared; the next `generate` gives the wire the design's value). With no FIELD it "
        "shows the overrides of the wire. A released harness cannot be changed.",
    )
    o.add_argument("project", type=Path, help="project folder")
    o.add_argument("wire", help="wire ID, for example W001-001")
    o.add_argument("field", nargs="?", default=None, help="gauge_awg, part_id, colour or length_m")
    o.add_argument("value", nargs="?", default=None, help="the value to set")
    o.add_argument("--reason", default=None, help="why (required with a value)")
    o.add_argument("--clear", default=None, metavar="FIELD", help="give this field back to generation")  # fmt: skip
    add_json_flag(o)

    d = sub.add_parser(
        "deviation",
        help="list the deviations of a project, accept an error of an electrical rule as a recorded deviation, or take one back",
        description="A deviation accepts an error of an electrical rule (wire current, voltage drop, "
        "contact current, bundle current, working voltage, temperature margin) with a reason, keeps "
        "it visible everywhere marked as a deviation, and lets a release go on. `deviation DIR` lists "
        "them, with who and when from the journal; `deviation DIR FINDING --reason TEXT` records one "
        "(FINDING is the finding ID of `drc`, for example current-over-wire.W001-001; the reason is "
        "at least 10 characters); `--remove` takes it back. A deviation does not meet the "
        "requirement: it records that a person accepted the error.",
    )
    d.add_argument("project", type=Path, help="project folder")
    d.add_argument("finding", nargs="?", default=None, help="the finding ID")
    d.add_argument("--reason", default=None, help="why the error is accepted (at least 10 characters)")  # fmt: skip
    d.add_argument("--remove", action="store_true", help="take the deviation back")
    add_json_flag(d)


def mutates(args: argparse.Namespace) -> bool:
    """Whether the command writes the project (it then takes the project lock)."""
    if args.command == "journal":
        return bool(args.start)
    if args.command == "override":
        return args.field is not None or args.clear is not None
    return args.command == "deviation" and (args.finding is not None)


def run(args: argparse.Namespace) -> int:
    rep = Report(args.json)
    code = {"journal": _journal, "override": _override, "deviation": _deviation}[args.command](
        args, rep
    )
    return rep.finish(code)


def _read_only() -> int:
    print("error: this project is read-only (saved by a newer tool version).", file=sys.stderr)
    return 2


def _journal(args: argparse.Namespace, rep: Report) -> int:
    project = load_project(args.project).project
    if args.start:
        if project.read_only:
            return _read_only()
        started = journal.start(project)
        if started:
            save_project(project, args.project)
            rep.say(f"Journal started: {args.project / 'journal.json'}. Changes are recorded when the project is saved.")  # fmt: skip
        else:
            rep.say("This project has a journal already.")
        rep.put(started=started, file="journal.json")
        return 0
    report = records.journal_report(project, args.object, args.since)
    rep.put(**report.to_dict())
    if project.journal is None:
        rep.say("This project has no change journal. `harness-design-studio journal DIR --start` starts one.")  # fmt: skip
    elif report.entries:
        rep.say(journal.render(journal.entries_for(project, args.object, args.since)))
    else:
        rep.say("No entries match.")
    return 0


def _override(args: argparse.Namespace, rep: Report) -> int:
    project = load_project(args.project).project
    if project.read_only:
        return _read_only()
    try:
        if args.clear is not None:
            action, changed = "clear", change_ops.clear_override(project, args.wire, args.clear)
        elif args.field is None:
            action, changed = "show", False
            wires.find_wire(project, args.wire)
        else:
            if args.value is None:
                print("error: give the value (override DIR WIRE FIELD VALUE --reason TEXT).", file=sys.stderr)  # fmt: skip
                return 2
            action = "set"
            changed = change_ops.set_override(project, args.wire, args.field, args.value, args.reason)  # fmt: skip
    except (EditError, TransactionError) as exc:
        print(blocked_text(exc), file=sys.stderr)
        return 1
    if changed:
        save_project(project, args.project)
    result = records.override_result(project, args.wire, action, changed)
    rep.put(**result.to_dict())
    w = wires.find_wire(project, args.wire)[1]
    if action == "clear":
        if changed:
            rep.say(f"{args.clear} of {args.wire} is given back to generation: run `generate` to give it the design's value.")  # fmt: skip
        else:
            rep.say("Already up to date.")
    elif action == "set" and not changed:
        rep.say("Already up to date.")
    elif result.derivation is not None:
        if changed:
            rep.say(f"Saved. Wire {args.wire} is overridden; it is kept when the harnesses are generated again.\n")  # fmt: skip
        from harness_design_studio.core.derive import explain_wire

        rep.say("\n\n".join(render(d) for d in explain_wire(project, args.wire) if d.id in ("wire-override", "wire-current-limit")))  # fmt: skip
    elif w.locked:
        rep.say(f"Wire {args.wire} is locked (no reason recorded): generation keeps its gauge, type, colour and length. Set a value with a reason to record why.")  # fmt: skip
    else:
        rep.say(f"Wire {w.id} has no override.")
    return 0


def _deviation(args: argparse.Namespace, rep: Report) -> int:
    project = load_project(args.project).project
    if args.finding is None:
        found = records.deviation_records(project)
        rep.put(**records.DeviationReport("list", "", found).to_dict())
        if not found:
            rep.say("No deviations.")
        for d in found:
            rep.say(f"DEVIATION {d.id} ({d.rule}): {d.title}\n  reason: {d.reason}" + (f"\n  {d.by}" if d.by else ""))  # fmt: skip
        return 0
    if project.read_only:
        return _read_only()
    try:
        if args.remove:
            finding = change_ops.remove_deviation(project, args.finding)
            action = "remove"
        else:
            if args.reason is None:
                print("error: a deviation needs a reason (--reason TEXT).", file=sys.stderr)
                return 2
            finding = change_ops.accept_deviation(project, args.finding, args.reason)
            action = "record"
    except EditError as exc:
        # an unknown finding is a wrong argument (exit 2); the other refusals are exit 1
        unknown = str(exc).startswith("there is no finding")
        print(f"error: {exc}" if unknown or args.remove else blocked_text(exc), file=sys.stderr)
        return 2 if unknown else 1
    except TransactionError as exc:
        print(blocked_text(exc), file=sys.stderr)
        return 1
    save_project(project, args.project)
    if action == "remove":
        rep.say(f"The deviation {finding.id} is taken back; the finding is open again.")
        marked: tuple[records.DeviationRecord, ...] = ()
    else:
        rep.say(f"DEVIATION recorded for {finding.id}: the error stays visible and is marked as a deviation. This accepts the error; it does not meet the requirement.")  # fmt: skip
        marked = tuple(d for d in records.deviation_records(project) if d.id == finding.id)
    rep.put(**records.DeviationReport(action, finding.id, marked).to_dict())
    return 0
