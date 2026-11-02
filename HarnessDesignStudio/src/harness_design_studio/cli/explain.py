"""`explain`: how a number of the design was made (D-191, step 1)."""

import argparse
import json
import sys
from pathlib import Path

from harness_design_studio.core.derive import explain_object, render
from harness_design_studio.core.io.loader import load_project

COMMANDS = ("explain",)


def register(sub: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    p = sub.add_parser(
        "explain",
        help="explain how the numbers of a wire, a harness or a part were made: equation, inputs with units and sources, steps",
        description="Show how the numbers of one wire or one harness were made. For a wire: its length, "
        "the current its gauge may carry after derating, the voltage drop over it and its share of "
        "the mass. For a harness: its mass. For a part: why the bill of materials has its quantity. For each: the equation, the inputs with "
        "their units and where each comes from (a key of config/*.json, a field of the design or "
        "the program), the intermediate results, what the result is checked against, and the "
        "assumptions built into the program that it rests on. The numbers are the ones `generate` "
        "and `drc` use. Nothing is changed or written. `--json` prints the same as data.",
    )
    p.add_argument("project", type=Path, help="project folder")
    p.add_argument(
        "object",
        metavar="OBJECT",
        help="a wire (W001-001), a harness (W001) or a part (EX-WIRE-SINGLE)",
    )
    p.add_argument("--json", action="store_true", help="print the derivations as JSON")


def run(args: argparse.Namespace) -> int:
    project = load_project(args.project).project
    found = explain_object(project, args.object)
    if args.json:
        print(json.dumps([d.to_dict() for d in found], indent=2, ensure_ascii=False))
        return 0
    print("\n\n".join(render(d) for d in found))
    if all(d.value is None for d in found):
        print("\nNothing could be explained yet: see what is not set above.", file=sys.stderr)
    return 0
