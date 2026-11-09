# SPDX-FileCopyrightText: 2026 0h3xn4
# SPDX-License-Identifier: GPL-3.0-only
"""`harness` command line entry point.

Exit codes: 0 ok (warnings allowed), 1 the project has errors or the step is blocked, 2 usage error
or unreadable project, 130 interrupted (Ctrl-C).
"""

import argparse
import contextlib
import os
import sys
from collections.abc import Iterator, Sequence
from pathlib import Path
from typing import Any

from harness_design_studio import __version__
from harness_design_studio.cli import (
    asbuilt_cmd,
    blocked_text,
    changes,
    data,
    explain,
    extensions_cmd,
    journal_cmd,
    merge,
    open_data,
    settings_cmd,
    start,
)
from harness_design_studio.cli.jsonout import Report, add_json_flag
from harness_design_studio.core import records
from harness_design_studio.core.errors import HarnessError, ProjectLockedError, TransactionError
from harness_design_studio.core.io import upgrade
from harness_design_studio.core.io.fs import ProjectLock
from harness_design_studio.core.io.loader import LoadResult, load_project
from harness_design_studio.core.io.migrate import current_version
from harness_design_studio.core.issues import Issue, errors
from harness_design_studio.core.units import with_area
from harness_design_studio.core.validation import validate_folder

PROG = "harness-design-studio"  # `harness` is kept as a short alias of the same command
MIGRATED = "Migrated; the original files are kept in a .migration-backup-* folder."
MIGRATED_CHECKED = (
    "Checked after the write: same model hash, same findings, baselines untouched, "
    "identical export."
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=PROG,
        description="Spacecraft harness design tool",
        epilog="`harness` still works as a short alias of this command.",
    )
    parser.add_argument("--version", action="store_true", help="print the tool version and exit")
    parser.add_argument(
        "--author",
        dest="journal_author",  # `generate --author` (with --run-record) has its own option
        default=None,
        metavar="NAME",
        help="who is making the changes of this run, for the change journal (before the command); "
        "default: the environment variable HARNESS_AUTHOR, else the name Git has, else the user",
    )
    sub = parser.add_subparsers(dest="command")
    for name, text in (
        ("validate", "check a project folder for errors and inconsistencies"),
        ("check", "validate, plus detect problems left behind by Git merges"),
        (
            "migrate",
            "upgrade an old-format project in place (originals are kept, the upgrade is "
            "recorded and checks itself; --dry-run only shows what it would do)",
        ),
        ("generate", "generate harnesses from the interfaces and save the project"),
        ("drc", "run the design rule check and print the report (waived findings included)"),
        (
            "export",
            "write the build workbook of every harness, the tables and exports to "
            "<project>/outputs and verify them (add --drawings for the PDF drawings)",
        ),
        ("verify", "independently verify the generated harnesses against the interfaces"),
    ):
        p = sub.add_parser(name, help=text, description=text)
        p.add_argument("project", type=Path, help="project folder")
        add_json_flag(p)
        if name == "verify":
            p.add_argument(
                "--outputs",
                action="store_true",
                help="also check <project>/outputs against the design",
            )
        if name == "migrate":
            p.add_argument(
                "--dry-run",
                action="store_true",
                help="load the project, upgrade it in memory and write nothing: print the files "
                "that would change, the objects by kind before and after, the model hash before "
                "and after and anything that could not be carried over; exit 0 only if nothing "
                "would be lost",
            )
        if name in ("generate", "export"):
            open_data.add_run_record_options(p)
        if name == "export":
            p.add_argument(
                "--drawings",
                action="store_true",
                help="also write the PDF and SVG drawings of the harnesses (off by default: "
                "the build workbook is the main output)",
            )
            p.add_argument(
                "--out",
                type=Path,
                default=None,
                help="the folder to write the outputs to (default: <project>/outputs)",
            )
    start.register(sub)
    journal_cmd.register(sub)
    merge.register(sub)
    explain.register(sub)
    open_data.register(sub)
    settings_cmd.register(sub)
    changes.register(sub)
    data.register(sub)
    asbuilt_cmd.register(sub)
    extensions_cmd.register(sub)
    return parser


def _print_report(result: LoadResult, extra: list[Issue]) -> int:
    issues = sorted([*result.issues, *extra])
    for issue in issues:
        print(issue.render())
    n_err = sum(i.severity == "error" for i in issues)
    n_warn = sum(i.severity == "warning" for i in issues)
    p = result.project
    print(
        f"{len(p.units)} devices, {len(p.interfaces)} interfaces, "
        f"{len(p.all_connectors())} connectors, {len(p.harnesses)} harnesses: "
        f"{n_err} error(s), {n_warn} warning(s)."
    )
    return 1 if n_err else 0


def _validate(path: Path, *, merge_check: bool, rep: Report | None = None) -> int:
    result, extra = validate_folder(path, merge_check=merge_check)
    if rep is not None and rep.as_json:
        outcome = records.validation_result(result, extra)
        rep.put(**outcome.to_dict())
        return 0 if outcome.ok else 1
    return _print_report(result, extra)


def _migrate(path: Path, rep: Report, *, dry_run: bool) -> int:
    """`migrate`: the dry run (`--dry-run`, writes nothing) or the upgrade with its record and its
    check after the write (`core.io.upgrade`)."""
    if dry_run:
        plan = upgrade.plan_upgrade(path)
        if plan is None:
            version = current_version()
            rep.say("Already up to date.")
            rep.put(
                dry_run=True, up_to_date=True, **upgrade.UpgradePlan(version, version).to_dict()
            )
            return rep.finish(0)
        for line in upgrade.render_plan(plan):
            rep.say(line)
        rep.put(dry_run=True, up_to_date=False, **plan.to_dict())
        return rep.finish(0 if plan.ok else 1)
    try:
        done = upgrade.upgrade_project(path)
    except upgrade.UpgradeError as exc:  # refused, or written, found wrong and put back
        print(f"error: {exc}", file=sys.stderr)
        for reason in exc.reasons:
            print(f"  {reason}", file=sys.stderr)
        return 1
    rep.say("Already up to date." if done is None else MIGRATED)
    if done is not None:
        rep.say(f"Format {done.from_version} to {done.to_version}. Record: {done.record}.")
        rep.say(MIGRATED_CHECKED)
    rep.put(
        migrated=done is not None,
        from_version=done.from_version if done else None,
        to_version=done.to_version if done else None,
        backup=done.backup if done else None,
        record=done.record if done else None,
        self_check=done.self_check if done else None,
    )
    return rep.finish(0)


def _generate(path: Path, rep: Report | None = None, args: argparse.Namespace | None = None) -> int:
    from harness_design_studio.core.generate.engine import generate_project
    from harness_design_studio.core.io.saver import save_project
    from harness_design_studio.core.outputs.build import DEFAULT_FOLDER
    from harness_design_studio.core.verify import verify_project

    rep = rep or Report()
    project = load_project(path).project
    if project.read_only:
        print("error: this project is read-only (saved by a newer tool version).", file=sys.stderr)
        return 2
    plan = generate_project(project)
    for f in plan.report.findings:
        rep.say(f"{f.severity}: [{f.code}] {with_area(f.message)}")  # mm² beside a gauge (D2)
    rep.say(plan.report.summary())
    report = verify_project(project)
    rep.say(report.summary())
    if plan.report.errors or not report.ok:
        print("Not saved: fix the errors above first.", file=sys.stderr)
        if rep.as_json:
            rep.put(**records.generate_result(plan, report, saved=False).to_dict())
        return 1
    save_project(project, path)
    if rep.as_json:
        rep.put(**records.generate_result(plan, report, saved=True).to_dict())
    if args is not None:
        open_data.write_record(project, path, path / DEFAULT_FOLDER, args, rep)
    if project.links and not project.interfaces:  # connections are exported as they are
        rep.say(
            f"{len(project.links)} connection(s) and no interface: Generate wires interfaces "
            "only. `export` writes the connection list without a harness."
        )
    return 0


def _export(
    path: Path,
    *,
    drawings: bool = False,
    out: Path | None = None,
    rep: Report | None = None,
    args: argparse.Namespace | None = None,
) -> int:
    from harness_design_studio.core.outputs.build import (
        DEFAULT_FOLDER,
        build_outputs,
        drawings_exported,
        write_outputs,
    )
    from harness_design_studio.core.outputs.verify import verify_outputs

    rep = rep or Report()
    project = load_project(path).project
    if not project.harnesses and not project.links:  # connections alone are enough (W2)
        print(
            "error: there are no harnesses to export; run `harness-design-studio generate` first.",
            file=sys.stderr,
        )
        if rep.as_json:
            rep.put(**records.export_refused("nothing_to_export").to_dict())
        return 1
    result = build_outputs(project, drawings=drawings)
    report = verify_outputs(project, result.files)
    for issue in report.issues:
        rep.say(f"{issue.severity}: [{issue.code}] {issue.message}")
    if not report.ok:
        print("Not written: the outputs failed their independent check.", file=sys.stderr)
        if rep.as_json:
            refused = records.export_refused(
                "outputs_failed_check", result.stamp.short, report.issues
            )
            rep.put(**refused.to_dict())
        return 1
    target = out if out is not None else path / DEFAULT_FOLDER
    had_drawings = drawings_exported(target)
    write_outputs(project, target, result)
    rep.say(f"{len(result.files)} files written to {target} (model {result.stamp.short}).")
    if args is not None:
        open_data.write_record(project, path, target, args, rep)
    if had_drawings and not drawings:
        rep.say(
            "The PDF drawings of the earlier export were removed; "
            "add --drawings to write them again."
        )
    if rep.as_json:
        written = records.export_result(
            result, report.issues, drawings_removed=had_drawings and not drawings
        )
        rep.put(**written.to_dict())
    return 0


def _drc(path: Path, rep: Report | None = None) -> int:
    from harness_design_studio.core.checks import find
    from harness_design_studio.core.drc import run
    from harness_design_studio.core.drc.report import render_markdown

    rep = rep or Report()
    project = load_project(path).project
    findings = sorted(
        [*find(project), *run(project)],
        key=lambda f: ({"error": 0, "warning": 1, "info": 2}[f.severity], f.id),
    )
    if rep.as_json:
        rep.put(**records.check_result(project, findings).to_dict())
    else:
        print(render_markdown(project, findings), end="")
    return 1 if any(f.severity == "error" and f.waiver is None for f in findings) else 0


def _verify(path: Path, outputs: bool = False, rep: Report | None = None) -> int:
    from harness_design_studio.core.verify import verify_project

    rep = rep or Report()
    project = load_project(path).project
    report = verify_project(project)
    if outputs:
        from harness_design_studio.core.outputs.build import DEFAULT_FOLDER
        from harness_design_studio.core.outputs.verify import read_folder, verify_outputs

        folder = path / DEFAULT_FOLDER
        if not folder.is_dir():
            print(
                "error: no outputs folder; run `harness-design-studio export` first.",
                file=sys.stderr,
            )
            return 1
        out = verify_outputs(project, read_folder(folder))
        report.issues += out.issues
        report.stale = report.stale or out.stale
    if rep.as_json:
        rep.put(**records.verify_result(report).to_dict())
        return 0 if report.ok else 1
    for issue in report.issues:
        print(f"{issue.severity}: [{issue.code}] {issue.message}")
    print(report.summary())
    if report.interfaces_checked and not report.wires_checked and not report.ok:
        print(
            "hint: there are no wires yet; run `harness-design-studio generate` first, then verify again."
        )
    return 0 if report.ok else 1


def _utf8_streams() -> None:
    """Redirected or piped output is UTF-8 on every platform (Windows would use the ANSI code page
    and fail on a name like `Sensor Ω ≤ 5 V ✓`). A real console keeps its own encoding but never fails."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        name = str(getattr(stream, "encoding", "") or "").lower().replace("-", "").replace("_", "")
        try:
            if name == "utf8":
                continue
            if stream.isatty():
                reconfigure(errors="replace")
            else:
                reconfigure(encoding="utf-8", errors="replace")
        except OSError, ValueError:  # a stream that cannot be changed stays as it is
            pass


def main(argv: Sequence[str] | None = None) -> int:
    _utf8_streams()
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:  # argparse exits on bad input; report it as a return code
        return 0 if exc.code in (0, None) else 2
    if args.version:
        print(f"harness {__version__}")
        return 0
    if args.command is None:
        parser.print_usage(sys.stderr)
        return 2
    from harness_design_studio.core import journal as journal_module

    journal_module.set_author(getattr(args, "author", None) or args.journal_author)
    real_stdout = sys.stdout
    sys.stdout = guard = _PipeGuard(real_stdout)
    try:
        return _run(args)
    finally:
        guard.flush()
        sys.stdout = real_stdout
        if guard.broken:
            _silence(real_stdout)


class _PipeGuard:
    """Stands in for stdout. When the reader goes away (`harness-design-studio generate | head -1`) the output
    is dropped and the command still finishes, so that it saves what it was asked to save."""

    def __init__(self, inner: Any) -> None:
        self._inner = inner
        self.broken = False

    def write(self, text: str) -> int:
        if not self.broken:
            try:
                return int(self._inner.write(text))
            except BrokenPipeError:
                self.broken = True
        return len(text)

    def flush(self) -> None:
        if not self.broken:
            try:
                self._inner.flush()
            except BrokenPipeError:
                self.broken = True

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)


def _silence(stream: Any) -> None:
    """Point the closed standard output at the null device so that the interpreter does not
    complain about the unwritten rest when it exits."""
    with contextlib.suppress(OSError, ValueError, AttributeError):
        os.dup2(os.open(os.devnull, os.O_WRONLY), stream.fileno())


def _run(args: argparse.Namespace) -> int:
    try:
        with _project_lock(args):
            return _dispatch(args)
    except KeyboardInterrupt:
        print(
            "interrupted. If it was saving, run `harness-design-studio validate` to check the project.",
            file=sys.stderr,
        )
        return 130
    except (ProjectLockedError, TransactionError) as exc:  # blocked, not misused
        print(blocked_text(exc), file=sys.stderr)
        return 1
    except HarnessError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except OSError as exc:  # a missing, unreadable or unwritable file: say it in words
        print(
            f"error: a file or folder could not be used ({exc.strerror or 'file problem'}).",
            file=sys.stderr,
        )
        return 2
    except ValueError as exc:  # includes validation errors of the data model and bad encodings
        print(f"error: {_plain(exc)}", file=sys.stderr)
        return 2
    except LookupError, RecursionError:
        print("error: the input is not in a form the tool can read.", file=sys.stderr)
        return 2


def _plain(exc: ValueError) -> str:
    """A validation error as field names and messages only (never the offending values)."""
    errors = getattr(exc, "errors", None)
    if callable(errors):
        try:
            parts = [
                f"{'.'.join(str(p) for p in e['loc']) or 'value'}: {e['msg']}" for e in errors()
            ]
            return "; ".join(parts[:3]) + (f" (+{len(parts) - 3} more)" if len(parts) > 3 else "")
        except TypeError, KeyError:
            pass
    return str(exc).splitlines()[0][:200] if str(exc) else "a value is not acceptable."


# Every command that reads or writes the project refuses a damaged project (exit 2) and says what
# it did not do; `validate` and `check` are the ones that report the damage.
NOTHING_DONE = {
    "migrate": "migrated", "export": "exported", "generate": "generated", "drc": "checked",
    "verify": "verified", "log": "listed", "diff": "compared", "compare": "compared",
    "config": "reported or changed", "library": "reported or changed",
    "review": "changed", "release": "released", "revise": "revised",
    "import-parts": "imported", "import-lengths": "imported", "import-netlist": "imported",
    "import-pinout": "imported", "export-pinout": "exported",
    "export-devices": "exported", "import-devices": "imported", "import-build-data": "imported",
    "export-subsystem": "exported", "import-subsystem": "imported", "explain": "explained", "settings": "reported or changed",
    "journal": "listed", "override": "changed", "deviation": "recorded",
    "import-plugin": "imported",
    "export-data": "exported",
    "imports": "listed",
    "workflow": "listed", "asbuilt": "reported", "import-asbuilt": "imported",
    "export-asbuilt": "exported",
}  # fmt: skip

MUTATING = {
    "generate", "export", "migrate", "review", "release", "revise", "merge-fix",
    "import-parts", "import-lengths", "import-netlist", "import-pinout", "import-devices",
    "import-build-data", "import-subsystem", "import-plugin",
}  # fmt: skip


@contextlib.contextmanager
def _project_lock(args: argparse.Namespace) -> Iterator[None]:
    """Commands that write take the same lock as the editor, so two writers never overlap."""
    path = getattr(args, "project", None)
    writes = (
        args.command in MUTATING
        or (args.command in journal_cmd.COMMANDS and journal_cmd.mutates(args))
        or (args.command in asbuilt_cmd.COMMANDS and asbuilt_cmd.mutates(args))
        or (
            args.command == "config"
            and (
                getattr(args, "ampacity_csv", None) is not None
                or getattr(args, "apply_profile", None) is not None
            )
        )
        or (args.command == "settings" and (args.set or args.annotate or args.no_annotate))
        or (
            args.command == "library"
            and any(
                getattr(args, k, None) is not None
                for k in ("library_name", "library_version", "library_source", "library_date")
            )
        )
    )
    if (
        not writes
        or getattr(args, "dry_run", False)
        or not isinstance(path, Path)
        or not path.is_dir()
        or not (path / "project.json").is_file()  # an empty or wrong folder gets no lock file
    ):
        yield
        return
    lock = ProjectLock(path)
    lock.acquire()
    try:
        yield
    finally:
        lock.release()


def _dispatch(args: argparse.Namespace) -> int:
    if args.command in start.COMMANDS:
        return start.run(args)
    if args.command in merge.COMMANDS:  # reads a project with conflict markers, so no damage check
        return merge.run(args)
    if args.command in NOTHING_DONE:
        for folder in (args.old, args.new) if args.command == "compare" else (args.project,):
            loaded = load_project(folder)
            probe = loaded.project
            if loaded.has_errors or probe.recovered:
                first = (
                    errors(loaded.issues)[0].render() if loaded.has_errors else "parts set aside"
                )
                print(
                    f"error: the project has damaged files (first: {first}); "
                    f"nothing was {NOTHING_DONE[args.command]}. "
                    "Run `harness-design-studio validate` to see them.",
                    file=sys.stderr,
                )
                return 2
            if args.command in ("migrate", "export") and probe.read_only:
                print(
                    "error: this project is read-only (saved by a newer tool version).",
                    file=sys.stderr,
                )
                return 2
    if args.command in journal_cmd.COMMANDS:
        return journal_cmd.run(args)
    if getattr(args, "author", None) and not getattr(args, "run_record", False):
        print("error: --author goes with --run-record", file=sys.stderr)
        return 2
    if args.command in explain.COMMANDS:
        return explain.run(args)
    if args.command in open_data.COMMANDS:
        return open_data.run(args)
    if args.command in settings_cmd.COMMANDS:
        return settings_cmd.run(args)
    if args.command in data.COMMANDS:
        return data.run(args)
    if args.command in changes.COMMANDS:
        return changes.run(args)
    if args.command in asbuilt_cmd.COMMANDS:
        return asbuilt_cmd.run(args)
    if args.command in extensions_cmd.COMMANDS:
        return extensions_cmd.run(args)
    rep = Report(args.json)
    if args.command == "migrate":
        return _migrate(args.project, rep, dry_run=args.dry_run)
    if args.command == "generate":
        return rep.finish(_generate(args.project, rep, args))
    if args.command == "export":
        return rep.finish(
            _export(args.project, drawings=args.drawings, out=args.out, rep=rep, args=args)
        )
    if args.command == "drc":
        return rep.finish(_drc(args.project, rep))
    if args.command == "verify":
        return rep.finish(_verify(args.project, args.outputs, rep))
    return rep.finish(_validate(args.project, merge_check=args.command == "check", rep=rep))


if __name__ == "__main__":
    raise SystemExit(main())
