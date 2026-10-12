"""Change-control commands: review, release, revise, diff, compare, log."""

import argparse
import sys
from datetime import date
from pathlib import Path

from harness_design_studio.cli import blocked_text
from harness_design_studio.core.commands import History
from harness_design_studio.core.errors import HarnessError, SaveError
from harness_design_studio.core.io.loader import load_project
from harness_design_studio.core.io.saver import save_project
from harness_design_studio.core.vcs import diff as vdiff
from harness_design_studio.core.vcs.release import (
    ReleasePlan,
    plan_new_revision,
    plan_release,
    plan_submit_review,
)
from harness_design_studio.core.vcs.report import baselines_of, changelog_rows, working_diff

COMMANDS = ("review", "release", "revise", "diff", "compare", "log")
OPTIONS = {
    "by": "--by", "comment": "--comment", "checker": "--checker", "date": "--date",
    "reason": "--accept-placeholders / --accept-unapproved-parts",
}  # fmt: skip


def register(sub: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    def add(name: str, text: str, *, harness: bool = True) -> argparse.ArgumentParser:
        p = sub.add_parser(name, help=text, description=text)
        p.add_argument("project", type=Path, help="project folder")
        if harness:
            p.add_argument("harness", help="harness ID, for example W001")
        return p

    def who(p: argparse.ArgumentParser, comment: bool) -> None:
        p.add_argument("--by", required=True, help="your name (recorded in the change log)")
        if comment:
            p.add_argument(
                "--comment", required=True, help="what changed or why (at least 10 characters)"
            )
        p.add_argument("--date", default=None, help="YYYY-MM-DD (default: today)")

    who(add("review", "submit a draft harness for review"), False)
    r = add(
        "release",
        "release a harness: baseline, change log entry and lock (blocked while checks fail)",
    )
    who(r, True)
    r.add_argument("--checker", default=None, help="who checked it (title block)")
    r.add_argument(
        "--accept-placeholders",
        metavar="REASON",
        default=None,
        help="release although configuration files are still placeholders: the reason "
        "(at least 10 characters) is kept in the change log and the baseline",
    )
    r.add_argument(
        "--accept-unapproved-parts",
        metavar="REASON",
        default=None,
        help="release although the harness uses parts that are not approved (or are example "
        "data): the reason (at least 10 characters) is kept in the change log and the baseline",
    )
    who(add("revise", "start a new revision of a released harness"), True)
    d = add("diff", "show what changed in a harness since a baseline (or between two baselines)")
    d.add_argument(
        "--from",
        dest="rev_from",
        default=None,
        help="baseline revision to compare from (default: latest)",
    )
    d.add_argument(
        "--to",
        dest="rev_to",
        default=None,
        help="baseline revision to compare to (default: the working design)",
    )
    c = sub.add_parser(
        "compare",
        help="compare two project folders (for example two Git checkouts)",
        description="Compare two project folders object by object.",
    )
    c.add_argument("old", type=Path)
    c.add_argument("new", type=Path)
    log = add("log", "print the change log", harness=False)
    log.add_argument("harness", nargs="?", default=None, help="limit to one harness")


NOT_COMPARED = (
    "Not compared: the generation record, the contents of baselines (only their revision, date, "
    "name, comment and hash), and the files of the outputs folders."
)


def _today(value: str | None) -> str:
    """An empty --date is a mistake (the date check names it), not a request for today."""
    return date.today().isoformat() if value is None else value


def _apply(path: Path, plan: ReleasePlan) -> int:
    if not plan.ok:
        for b in plan.blockers:
            option = OPTIONS.get(b.about or "")
            where = f"{option}: " if option else ""
            print(f"blocked: [{b.code}] {where}{b.message}", file=sys.stderr)
        return 2 if any(b.code == "no_harness" for b in plan.blockers) else 1
    return 0


def run(args: argparse.Namespace) -> int:
    cmd = args.command
    if cmd == "compare":
        diff = vdiff.diff_projects(load_project(args.old).project, load_project(args.new).project)
        print(
            vdiff.render_markdown(
                "Project comparison", diff, before=str(args.old), after=str(args.new)
            ),
            end="",
        )
        print(NOT_COMPARED)
        return 0
    project = load_project(args.project).project
    if cmd == "log":
        if args.harness is not None and args.harness not in project.harnesses:
            print(f"error: harness {args.harness} does not exist.", file=sys.stderr)
            return 2
        for row in changelog_rows(project, args.harness):
            print(" | ".join(row))
        return 0
    if cmd == "diff":
        return _diff(project, args)
    if project.read_only:
        print("error: this project is read-only (saved by a newer tool version).", file=sys.stderr)
        return 2
    when = _today(args.date)
    folder = args.project / "outputs"
    if cmd == "review":
        plan = plan_submit_review(project, args.harness, by=args.by, when=when)
    elif cmd == "release":
        plan = plan_release(
            project,
            args.harness,
            by=args.by,
            checker=args.checker,
            comment=args.comment,
            when=when,
            outputs_folder=folder,
            accept_placeholders=args.accept_placeholders,
            accept_unapproved_parts=args.accept_unapproved_parts,
        )
    else:
        plan = plan_new_revision(project, args.harness, by=args.by, comment=args.comment, when=when)
    blocked = _apply(args.project, plan)
    if blocked:
        return blocked
    try:
        History(project).execute(plan.label, plan.ops)
        save_project(project, args.project)
    except HarnessError as exc:
        print(blocked_text(exc), file=sys.stderr)
        return 2 if isinstance(exc, SaveError) else 1
    print(f"{plan.label}: done.")
    if cmd == "release":
        return _restamp(args.project)
    return 0


RESTAMP_HINT = (
    "The release was recorded (see `harness log`); only the outputs still show the old status. "
    "Fix the problem, then run `harness export` to re-stamp them."
)


def _restamp(path: Path) -> int:
    """After a release the title blocks must show the new status, so write the outputs again."""
    from harness_design_studio.core.outputs.build import (
        DEFAULT_FOLDER,
        build_outputs,
        write_outputs,
    )
    from harness_design_studio.core.outputs.verify import verify_outputs

    try:
        project = load_project(path).project
        built = build_outputs(project)
        if not verify_outputs(project, built.files).ok:
            print(
                "error: the re-exported outputs failed their independent check; nothing was written.",
                file=sys.stderr,
            )
            print(RESTAMP_HINT, file=sys.stderr)
            return 1
        write_outputs(project, path / DEFAULT_FOLDER, built)
    except (HarnessError, OSError) as exc:
        print(f"error: the outputs could not be re-stamped ({_why(exc)}).", file=sys.stderr)
        print(RESTAMP_HINT, file=sys.stderr)
        return 2
    print(f"Outputs re-exported with the released status ({len(built.files)} files).")
    return 0


def _why(exc: Exception) -> str:
    if isinstance(exc, OSError):
        return exc.strerror or "file problem"
    return str(exc).rstrip(".")


def _diff(project: "object", args: argparse.Namespace) -> int:
    from harness_design_studio.core.model import Project

    assert isinstance(project, Project)  # noqa: S101 - narrowing for the type checker
    h = project.harnesses.get(args.harness)
    if h is None:
        print(f"error: harness {args.harness} does not exist.", file=sys.stderr)
        return 2
    bases = {b.revision: b for b in baselines_of(project, h.id)}
    if not bases:
        print(f"error: {h.id} has no baseline yet; release it first.", file=sys.stderr)
        return 2
    start = bases.get(args.rev_from) if args.rev_from else list(bases.values())[-1]
    if start is None:
        print(f"error: {h.id} has no baseline for revision {args.rev_from}.", file=sys.stderr)
        return 2
    if args.rev_to:
        end = bases.get(args.rev_to)
        if end is None:
            print(f"error: {h.id} has no baseline for revision {args.rev_to}.", file=sys.stderr)
            return 2
        diff = vdiff.diff_snapshots(start.snapshot, end.snapshot)
        print(
            vdiff.render_markdown(f"{h.id}: revision {start.revision} to {end.revision}", diff),
            end="",
        )
    else:
        diff = working_diff(project, h, start)
        print(
            vdiff.render_markdown(
                f"{h.id}: working design against revision {start.revision}", diff
            ),
            end="",
        )
    return 0
