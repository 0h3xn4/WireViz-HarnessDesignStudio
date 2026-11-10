# SPDX-FileCopyrightText: 2026 0h3xn4
# SPDX-License-Identifier: GPL-3.0-only
"""`merge-fix`: after a Git merge, when two people each pressed Generate."""

import argparse
import sys
from pathlib import Path

from harness_design_studio.cli import quoted
from harness_design_studio.cli.jsonout import Report, add_json_flag
from harness_design_studio.core.io.fs import atomic_write_bytes
from harness_design_studio.core.io.loader import load_project
from harness_design_studio.core.issues import errors
from harness_design_studio.core.mergefix import GENERATION_FILE, plan_merge_fix

COMMANDS = ("merge-fix",)


def register(sub: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    p = sub.add_parser(
        "merge-fix",
        help="after a Git merge stopped on generated/generation.json: keep this side, generate, check",
        description="After a Git merge in which two people each pressed Generate, "
        "`generated/generation.json` conflicts. This command keeps this branch's version of that "
        "one file, then runs `generate` (which writes the record again for the merged design) "
        "and `check`. It refuses, and changes nothing, when any other file of the project is in "
        "conflict, and it writes nothing itself apart from that record and what `generate` "
        "writes. Commit the result afterwards.",
    )
    p.add_argument("project", type=Path, help="project folder")
    add_json_flag(p)


def run(args: argparse.Namespace) -> int:
    rep = Report(args.json)
    return rep.finish(_run(args, rep))


def _run(args: argparse.Namespace, rep: Report) -> int:
    from harness_design_studio.cli import main as cli

    folder: Path = args.project
    shown = quoted(folder)
    if not (folder / "project.json").is_file():
        print(f"error: {folder} is not a project folder.", file=sys.stderr)
        return 2
    plan = plan_merge_fix(folder)
    if plan.nothing_to_do:
        rep.say("Nothing to fix: no file of this project is in a Git merge conflict.")
        rep.put(result="nothing_to_fix", conflicts=[], problem="", generate=None, check=None)
        return 0
    if plan.others:
        print(
            "error: these files of the project are in conflict, and merge-fix only resolves "
            f"{GENERATION_FILE}; nothing was changed:",
            file=sys.stderr,
        )
        for rel in plan.others:
            print(f"  {rel}", file=sys.stderr)
        print(
            "Resolve them by hand (the manual says how for each file), then run "
            f"`harness-design-studio merge-fix {shown}` again.",
            file=sys.stderr,
        )
        rep.put(
            result="refused", conflicts=list(plan.others), problem="", generate=None, check=None
        )
        return 1
    if plan.problem:
        print(f"error: {plan.problem} Nothing was changed.", file=sys.stderr)
        rep.put(result="refused", conflicts=[], problem=plan.problem, generate=None, check=None)
        return 1
    rep.say(
        f"{GENERATION_FILE} is the only file in conflict. Keeping this branch's version of it; "
        "generate writes the record again for the merged design and check tests it."
    )
    path = folder / GENERATION_FILE
    original = path.read_bytes()
    if plan.new_record is not None:
        atomic_write_bytes(path, plan.new_record, backup=False, root=folder)
    loaded = load_project(folder)
    if loaded.has_errors or loaded.project.recovered:
        first = errors(loaded.issues)[0].render() if loaded.has_errors else "parts set aside"
        rep.put(result="undone", conflicts=[], problem="", generate=None, check=None)
        return _undo(path, original, f"the project has damaged files (first: {first})", 2, shown)
    steps = Report(rep.as_json)  # the data of the two steps; in text mode they print as they run
    code = cli._generate(folder, steps) if rep.as_json else cli._generate(folder)
    generated = steps.result(code) if rep.as_json else None
    if code != 0:
        rep.put(result="undone", conflicts=[], problem="", generate=generated, check=None)
        return _undo(path, original, "generate did not accept the merged design", code, shown)
    rep.say("--- check")
    steps = Report(rep.as_json)
    code = (
        cli._validate(folder, merge_check=True, rep=steps)
        if rep.as_json
        else cli._validate(folder, merge_check=True)
    )
    checked = steps.result(code) if rep.as_json else None
    rep.put(result="fixed", conflicts=[], problem="", generate=generated, check=checked)
    if code != 0:
        print(
            "check reports errors: fix them as the message says. The record is written again.",
            file=sys.stderr,
        )
        return code
    rep.say(
        "Done. The record is written again for the merged design. Commit the merge now: "
        "`git add -A`, then `git commit` (or `git merge --continue`)."
    )
    return 0


def _undo(path: Path, original: bytes, why: str, code: int, shown: str) -> int:
    """Put the record back as it was found: a refused fix leaves no trace."""
    atomic_write_bytes(path, original, backup=False, root=path.parent.parent)
    print(
        f"error: {why}; merge-fix changed nothing. Run `harness-design-studio check {shown}` "
        "to see the problems and fix them first.",
        file=sys.stderr,
    )
    return code
