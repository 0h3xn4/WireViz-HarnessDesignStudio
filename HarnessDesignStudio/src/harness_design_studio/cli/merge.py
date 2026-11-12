# SPDX-FileCopyrightText: 2026 0h3xn4
# SPDX-License-Identifier: GPL-3.0-only
"""`merge-fix`: after a Git merge, when two people each pressed Generate or each added entries to
the change journal."""

import argparse
import sys
from pathlib import Path

from harness_design_studio.cli import quoted
from harness_design_studio.cli.jsonout import Report, add_json_flag
from harness_design_studio.core.errors import SaveError
from harness_design_studio.core.io.fs import atomic_write_bytes
from harness_design_studio.core.io.loader import load_project
from harness_design_studio.core.issues import errors
from harness_design_studio.core.mergefix import (
    GENERATION_FILE,
    JOURNAL_FILE,
    plan_merge_fix,
    record_journal_merge,
)
from harness_design_studio.core.model import JournalError

COMMANDS = ("merge-fix",)


def register(sub: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    p = sub.add_parser(
        "merge-fix",
        help="after a Git merge: keep this side of generated/generation.json and both sides of "
        "the journal, record the merge in the journal, generate, check",
        description="After a Git merge. When two people each pressed Generate, "
        "`generated/generation.json` conflicts: this command keeps this branch's version of that "
        "file, then runs `generate` (which writes the record again for the merged design) and "
        "`check`. When both added entries to the change journal (`journal.jsonl`), Git keeps the "
        "lines of both (`merge=union` in `.gitattributes`); if it stopped on the journal instead, "
        "this command keeps both sides' lines. Then it adds one `merge` entry to the journal that "
        "names the last entry of each side. It refuses, and changes nothing, when any other file "
        "of the project is in conflict, and it writes nothing itself apart from that record, the "
        "journal and what `generate` writes. Commit the result afterwards.",
    )
    p.add_argument("project", type=Path, help="project folder")
    add_json_flag(p)


def run(args: argparse.Namespace) -> int:
    rep = Report(args.json)
    return rep.finish(_run(args, rep))


def _merge_journal(folder: Path, rep: Report) -> str:
    """Add the merge entry to the journal; "" when done or not needed, else why not."""
    try:
        merged = record_journal_merge(folder)
    except (JournalError, SaveError) as exc:
        return f"the journal: {exc}"
    if merged:
        rep.say(
            f"{JOURNAL_FILE} holds the entries of {merged} lines of work: one merge entry that "
            "names them is added."
        )
    return ""


def _run(args: argparse.Namespace, rep: Report) -> int:
    from harness_design_studio.cli import main as cli

    folder: Path = args.project
    shown = quoted(folder)
    if not (folder / "project.json").is_file():
        print(f"error: {folder} is not a project folder.", file=sys.stderr)
        return 2
    plan = plan_merge_fix(folder)
    if plan.nothing_to_do:
        journal_path = folder / JOURNAL_FILE
        before = journal_path.read_bytes() if journal_path.is_file() else None
        why = _merge_journal(folder, rep)
        if why:
            print(f"error: {why} Nothing was changed.", file=sys.stderr)
            rep.put(result="refused", conflicts=[], problem=why, generate=None, check=None)
            return 1
        after = journal_path.read_bytes() if journal_path.is_file() else None
        if after == before:
            rep.say("Nothing to fix: no file of this project is in a Git merge conflict.")
            rep.put(result="nothing_to_fix", conflicts=[], problem="", generate=None, check=None)
        else:
            rep.say(
                "Done. Commit the journal now: `git add -A`, then `git commit` "
                "(or `git merge --continue`)."
            )
            rep.put(result="journal_merged", conflicts=[], problem="", generate=None, check=None)
        return 0
    if plan.others:
        print(
            "error: these files of the project are in conflict, and merge-fix only resolves "
            f"{GENERATION_FILE} and {JOURNAL_FILE}; nothing was changed:",
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
    record = GENERATION_FILE in plan.conflicts
    originals: dict[Path, bytes] = {}
    if plan.new_journal is not None:
        rep.say(f"{JOURNAL_FILE} is in conflict. Keeping the entries of both sides.")
        path = folder / JOURNAL_FILE
        originals[path] = path.read_bytes()
        atomic_write_bytes(path, plan.new_journal, backup=False, root=folder)
    if record:
        rep.say(
            f"{GENERATION_FILE} is in conflict. Keeping this branch's version of it; "
            "generate writes the record again for the merged design and check tests it."
        )
        path = folder / GENERATION_FILE
        originals[path] = path.read_bytes()
        if plan.new_record is not None:
            atomic_write_bytes(path, plan.new_record, backup=False, root=folder)
    loaded = load_project(folder)
    if loaded.has_errors or loaded.project.recovered:
        first = errors(loaded.issues)[0].render() if loaded.has_errors else "parts set aside"
        rep.put(result="undone", conflicts=[], problem="", generate=None, check=None)
        return _undo(folder, originals, f"the project has damaged files (first: {first})", 2, shown)
    journal_path = folder / JOURNAL_FILE
    if journal_path.is_file():
        originals.setdefault(journal_path, journal_path.read_bytes())
    why = _merge_journal(folder, rep)
    if why:
        rep.put(result="undone", conflicts=[], problem=why, generate=None, check=None)
        return _undo(folder, originals, why, 2, shown)
    generated = None
    if record:
        steps = Report(
            rep.as_json
        )  # the data of the two steps; in text mode they print as they run
        code = cli._generate(folder, steps) if rep.as_json else cli._generate(folder)
        generated = steps.result(code) if rep.as_json else None
        if code != 0:
            rep.put(result="undone", conflicts=[], problem="", generate=generated, check=None)
            return _undo(
                folder, originals, "generate did not accept the merged design", code, shown
            )
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
            "check reports errors: fix them as the message says. "
            + ("The record is written again." if record else "The journal is merged."),
            file=sys.stderr,
        )
        return code
    rep.say(
        "Done. "
        + ("The record is written again for the merged design. " if record else "")
        + "Commit the merge now: `git add -A`, then `git commit` (or `git merge --continue`)."
    )
    return 0


def _undo(folder: Path, originals: dict[Path, bytes], why: str, code: int, shown: str) -> int:
    """Put the files back as they were found: a refused fix leaves no trace."""
    for path, data in originals.items():
        atomic_write_bytes(path, data, backup=False, root=folder)
    print(
        f"error: {why}; merge-fix changed nothing. Run `harness-design-studio check {shown}` "
        "to see the problems and fix them first.",
        file=sys.stderr,
    )
    return code
