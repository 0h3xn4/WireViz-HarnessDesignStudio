"""`explain`: how a number of the design was made (D-191, step 1)."""

import argparse
import json
import sys
from pathlib import Path

from harness_design_studio.api import write_derivations
from harness_design_studio.cli.jsonout import Report
from harness_design_studio.core.derive import explain_object, render
from harness_design_studio.core.io.loader import load_project
from harness_design_studio.core.model import Project

COMMANDS = ("explain",)


def register(sub: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    p = sub.add_parser(
        "explain",
        help="explain how the numbers and decisions of a wire, harness, interface, connector, pin or part were made: equation, inputs with units and sources, steps",
        description="Show how the numbers and decisions of one object were made. For a wire: its length, "
        "the current its gauge may carry after derating, the voltage drop over it and its share of "
        "the mass, then its label, its colour, its shield group and the pins at its ends. For a harness: its mass, "
        "whether it is ready to build and each check behind that, its test limits, why its interfaces share it, its shield groups and its connectors; "
        "HARNESS.T001 explains the limits of one test. For an interface: which harness carries it and why, its connectors, the contact current and its pins. "
        "For a connector: why it is the connector (or the mating part) and its label; for CONNECTOR.PIN: why the signal is on that pin; for a shield group (W001-S1): why it exists and its ends. "
        "For a part: why the bill of materials has its quantity. For INTERFACE.CONNECTOR (the object of a current-over-contact finding): the limit of the contacts. For each: the equation, the inputs with "
        "their units and where each comes from (a key of config/*.json, a field of the design or "
        "the program), the intermediate results, what the result is checked against, and the "
        "assumptions built into the program that it rests on. The numbers are the ones `generate` "
        "and `drc` use. `--json` prints the same as data (a list). With `--all --out FOLDER` it writes "
        "every derivation of the project to FOLDER as `derivations.json` and `derivations.csv`: no "
        "time, user or path is in them, so the same design gives the same files; with `--json` as "
        "well it prints how many it wrote instead of the line of text. Without `--out` nothing "
        "is written.",
    )
    p.add_argument("project", type=Path, help="project folder")
    p.add_argument(
        "object",
        nargs="?",
        metavar="OBJECT",
        help="a wire (W001-001), a harness (W001), a test (W001.T001), an interface (IF-001), a connector (GPSU1-J01), a pin (MTQ1-J01.1), a shield group (W001-S1), a part (EX-WIRE-SINGLE) or INTERFACE.CONNECTOR (IF-001.GPSU1-J01)",
    )
    p.add_argument("--json", action="store_true", help="print the derivations as JSON")
    p.add_argument(
        "--all", action="store_true", help="every derivation of the project (instead of OBJECT)"
    )
    p.add_argument(
        "--out", type=Path, help="with --all: the folder for derivations.json and derivations.csv"
    )


def _write_all(project: Project, out: Path, rep: Report) -> int:
    written = write_derivations(project, out)
    rep.say(
        f"{written.count} derivations written to {out / 'derivations.json'} and "
        f"{out / 'derivations.csv'} ({written.without_value} without a value: see the column Missing)"
    )
    rep.put(**written.to_dict())
    return 0


def run(args: argparse.Namespace) -> int:
    if args.all == (args.object is not None):
        print("error: give either OBJECT or --all", file=sys.stderr)
        return 2
    if args.out is not None and not args.all:
        print("error: --out goes with --all", file=sys.stderr)
        return 2
    project = load_project(args.project).project
    if args.all:
        if args.out is None:
            print("error: --all needs --out FOLDER (the files are written there)", file=sys.stderr)
            return 2
        rep = Report(args.json)
        return rep.finish(_write_all(project, args.out, rep))
    found = explain_object(project, args.object)
    if args.json:
        print(json.dumps([d.to_dict() for d in found], indent=2, ensure_ascii=False))
        return 0
    print("\n\n".join(render(d) for d in found))
    from harness_design_studio.core import journal

    entries = journal.entries_for(project, args.object)
    if entries:  # a project with a journal: who changed this object, when, from what to what, why
        print(f"\nHistory of {args.object} (from the change journal):\n" + journal.render(entries))
    if all(not d.known for d in found):
        print("\nNothing could be explained yet: see what is not set above.", file=sys.stderr)
    return 0
