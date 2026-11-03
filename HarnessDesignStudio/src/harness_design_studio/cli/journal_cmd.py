"""`journal`, `override` and `deviation`: the change journal, deliberate overrides of generated values
and recorded deviations (D-191, S4)."""

import argparse
import json
import sys
from pathlib import Path

from harness_design_studio.cli import blocked_text
from harness_design_studio.core import checks, drc, journal, wires
from harness_design_studio.core.commands import Delete, History
from harness_design_studio.core.derive import explain_wire, render
from harness_design_studio.core.edit import EditError
from harness_design_studio.core.errors import TransactionError
from harness_design_studio.core.io.loader import load_project
from harness_design_studio.core.io.saver import save_project
from harness_design_studio.core.model import Project

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
        "has (`user.name`), else the user of the computer. `--json` prints the entries as data; "
        "`--object` selects one object (W001-001, wire:W001-001, derating.bundle_derating); "
        "`--since SEQ` the entries after number SEQ.",
    )
    j.add_argument("project", type=Path, help="project folder")
    j.add_argument("--json", action="store_true", help="print the entries as JSON")
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


def mutates(args: argparse.Namespace) -> bool:
    """Whether the command writes the project (it then takes the project lock)."""
    if args.command == "journal":
        return bool(args.start)
    if args.command == "override":
        return args.field is not None or args.clear is not None
    return args.command == "deviation" and (args.finding is not None)


def run(args: argparse.Namespace) -> int:
    return {"journal": _journal, "override": _override, "deviation": _deviation}[args.command](args)


def _journal(args: argparse.Namespace) -> int:
    project = load_project(args.project).project
    if args.start:
        if project.read_only:
            print(
                "error: this project is read-only (saved by a newer tool version).", file=sys.stderr
            )
            return 2
        if not journal.start(project):
            print("This project has a journal already.")
            return 0
        save_project(project, args.project)
        print(f"Journal started: {args.project / 'journal.json'}. Changes are recorded when the project is saved.")  # fmt: skip
        return 0
    if project.journal is None:
        if args.json:
            print("[]")
        else:
            print("This project has no change journal. `harness-design-studio journal DIR --start` starts one.")  # fmt: skip
        return 0
    entries = journal.entries_for(project, args.object, args.since)
    if args.json:
        print(json.dumps(journal.to_dicts(entries), indent=2, ensure_ascii=False))
    elif entries:
        print(journal.render(entries))
    else:
        print("No entries match.")
    return 0


def _override(args: argparse.Namespace) -> int:
    project = load_project(args.project).project
    if project.read_only:
        print("error: this project is read-only (saved by a newer tool version).", file=sys.stderr)
        return 2
    try:
        if args.clear is not None:
            ops = wires.plan_clear_override(project, args.wire, args.clear)
            label = f"Give {args.clear} of {args.wire} back to generation"
        elif args.field is None:
            h, w = wires.find_wire(project, args.wire)
            if not w.locked:
                print(f"Wire {w.id} has no override.")
                return 0
            return _show(project, w.id)
        else:
            if args.value is None:
                print("error: give the value (override DIR WIRE FIELD VALUE --reason TEXT).", file=sys.stderr)  # fmt: skip
                return 2
            ops = wires.plan_override(project, args.wire, args.field, args.value, args.reason)
            label = f"Override {args.field} of {args.wire}"
        History(project).execute(label, ops)
    except (EditError, TransactionError) as exc:
        print(blocked_text(exc), file=sys.stderr)
        return 1
    if not ops:
        print("Already up to date.")
        return 0
    save_project(project, args.project)
    if args.clear is not None:
        print(f"{args.clear} of {args.wire} is given back to generation: run `generate` to give it the design's value.")  # fmt: skip
        return 0
    return _show(project, args.wire, saved=True)


def _show(project: Project, wire_id: str, *, saved: bool = False) -> int:
    h, w = wires.find_wire(project, wire_id)
    if saved:
        print(f"Saved. Wire {wire_id} is overridden; it is kept when the harnesses are generated again.\n")  # fmt: skip
    if w.locked and not w.overrides:
        print(f"Wire {wire_id} is locked (no reason recorded): generation keeps its gauge, type, colour and length. Set a value with a reason to record why.")  # fmt: skip
        return 0
    found = explain_wire(project, wire_id)
    print("\n\n".join(render(d) for d in found[:3] if d.id in ("wire-override", "wire-current-limit")))  # fmt: skip
    return 0


def _findings(project: Project) -> dict[str, checks.Finding]:
    return {f.id: f for f in [*checks.find(project), *drc.run(project)]}


def _deviation(args: argparse.Namespace) -> int:
    project = load_project(args.project).project
    found = _findings(project)
    if args.finding is None:
        marked = sorted((f for f in found.values() if f.deviation), key=lambda f: f.id)
        if not marked:
            print("No deviations.")
            return 0
        for f in marked:
            why = f.waiver.justification if f.waiver is not None else ""
            by = journal.who_and_when(project, f.id)
            print(f"DEVIATION {f.id} ({f.rule}): {f.title}\n  reason: {why}" + (f"\n  {by}" if by else ""))  # fmt: skip
        return 0
    if project.read_only:
        print("error: this project is read-only (saved by a newer tool version).", file=sys.stderr)
        return 2
    finding = found.get(args.finding)
    if finding is None:
        print(f"error: there is no finding '{args.finding}' (see `drc`).", file=sys.stderr)
        return 2
    try:
        if args.remove:
            if not finding.deviation:
                print(f"error: {args.finding} is not a deviation.", file=sys.stderr)
                return 1
            History(project).execute(f"Take back the deviation {finding.id}", [Delete("waivers", finding.id)])  # fmt: skip
            save_project(project, args.project)
            print(f"The deviation {finding.id} is taken back; the finding is open again.")
            return 0
        if args.reason is None:
            print("error: a deviation needs a reason (--reason TEXT).", file=sys.stderr)
            return 2
        op = checks.deviate_op(finding, args.reason)
        History(project).execute(f"Deviation {finding.id}", [op])
    except (EditError, TransactionError) as exc:
        print(blocked_text(exc), file=sys.stderr)
        return 1
    save_project(project, args.project)
    print(f"DEVIATION recorded for {finding.id}: the error stays visible and is marked as a deviation. This accepts the error; it does not meet the requirement.")  # fmt: skip
    return 0
