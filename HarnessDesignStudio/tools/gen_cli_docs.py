"""Generate docs/CLI.md (every `harness-design-studio` command, its arguments and examples) from the
program's own argument parser, so the reference cannot drift from the commands. A test fails if the
committed file is stale. Usage: python -m tools.gen_cli_docs"""

import argparse
from pathlib import Path

from harness_design_studio.cli.jsonout import SHAPES
from harness_design_studio.cli.main import PROG, build_parser

TARGET = Path(__file__).resolve().parents[1] / "docs" / "CLI.md"

# command -> (group, examples). Examples are written by hand; a test checks every command has some.
GROUPS = (
    ("Start", ("new", "templates", "schema")),
    ("Check", ("validate", "check", "drc", "verify")),
    ("Explain", ("explain", "settings")),
    ("Overrides and change history", ("override", "deviation", "journal")),
    ("Generate and export", ("generate", "export", "export-data")),
    ("Team use with Git", ("merge-fix",)),
    (
        "Bring in data",
        (
            "config",
            "library",
            "import-parts",
            "import-lengths",
            "import-netlist",
            "import-pinout",
            "import-devices",
            "import-subsystem",
            "import-build-data",
            "imports",
        ),
    ),
    ("Write data out", ("export-pinout", "export-devices", "export-subsystem")),
    ("Review, release and change", ("review", "release", "revise", "diff", "log", "compare")),
    ("Maintenance", ("migrate",)),
)
EXAMPLES: dict[str, list[str]] = {
    "new": [
        "harness-design-studio new --list",
        "harness-design-studio new --list --json",
        'harness-design-studio new my-design --name "My first design"',
        "harness-design-studio new wheel-link --template first-steps",
    ],
    "explain": [
        "harness-design-studio explain wheel-link W001-001",
        "harness-design-studio explain wheel-link W001",
        "harness-design-studio explain wheel-link EX-WIRE-SINGLE",
        "harness-design-studio explain wheel-link --all --out wheel-link-derivations",
        "harness-design-studio explain wheel-link IF-001.GPSU1-J01",
        "harness-design-studio explain wheel-link W001-001 --json",
        "harness-design-studio explain wheel-link --all --out wheel-link-derivations --json",
    ],
    "templates": [
        "harness-design-studio templates my-templates",
        "harness-design-studio templates my-templates --json",
    ],
    "schema": [
        "harness-design-studio schema my-design/schemas",
        "harness-design-studio schema my-design/schemas --json",
    ],
    "validate": [
        "harness-design-studio validate my-design",
        "harness-design-studio validate my-design --json",
    ],
    "check": [
        "harness-design-studio check my-design",
        "harness-design-studio check my-design --json",
    ],
    "drc": [
        "harness-design-studio drc my-design > drc-report.md",
        "harness-design-studio drc my-design --json > drc-findings.json",
    ],
    "override": [
        'harness-design-studio override wheel-link W001-001 gauge_awg 20 --reason "Heater load added after CDR, see ECR-114"',
        "harness-design-studio override wheel-link W001-001 length_m 2.4 --reason 'Measured on the mock-up'",
        "harness-design-studio override wheel-link W001-001",
        "harness-design-studio override wheel-link W001-001 --clear gauge_awg",
    ],
    "deviation": [
        "harness-design-studio deviation wheel-link",
        'harness-design-studio deviation wheel-link current-over-wire.W001-001 --reason "Accepted by the PA board, NCR-17"',
        "harness-design-studio deviation wheel-link current-over-wire.W001-001 --remove",
    ],
    "journal": [
        "harness-design-studio journal wheel-link",
        "harness-design-studio journal wheel-link --start",
        "harness-design-studio journal wheel-link --object W001-001",
        "harness-design-studio journal wheel-link --since 12 --json",
        "harness-design-studio --author 'A. Engineer' override wheel-link W001-001 colour red --reason 'Colour code of the program'",
    ],
    "settings": [
        "harness-design-studio settings wheel-link",
        "harness-design-studio settings wheel-link --json",
        "harness-design-studio settings wheel-link --set model.service_loops_per_wire=0",
    ],
    "verify": [
        "harness-design-studio verify my-design",
        "harness-design-studio verify my-design --outputs",
        "harness-design-studio verify my-design --json",
    ],
    "generate": [
        "harness-design-studio generate my-design",
        "harness-design-studio generate my-design --json",
        "harness-design-studio generate my-design --run-record",
    ],
    "export": [
        "harness-design-studio export my-design",
        "harness-design-studio export my-design --drawings",
        "harness-design-studio export my-design --out my-outputs --json",
        'harness-design-studio export my-design --run-record --author "A. Engineer"',
    ],
    "export-data": [
        "harness-design-studio export-data my-design --out my-design-data",
        "harness-design-studio export-data my-design --out my-design-data --json",
        'harness-design-studio export-data my-design --out my-design-data --run-record --author "A. Engineer"',
    ],
    "config": [
        "harness-design-studio config my-design",
        "harness-design-studio config my-design --json",
        "harness-design-studio config my-design --ampacity-csv ampacity.csv",
        "harness-design-studio config my-design --apply-profile ecss-q-st-30-11c",
        'harness-design-studio config my-design --counterparts "TX=RX, MOSI=MISO, OUT=IN"',
    ],
    "library": [
        "harness-design-studio library my-design",
        "harness-design-studio library my-design --json",
        'harness-design-studio library my-design --library-version 4 --library-source "ESCC part data, supplier file" --library-date 2026-09-30',
    ],
    "import-parts": [
        "harness-design-studio import-parts my-design parts.csv --approved Approved --pending Review "
        "--rejected Rejected --dry-run",
        "harness-design-studio import-parts my-design parts.csv --approved Approved --dry-run --json",
        "harness-design-studio import-parts my-design connectors.xlsx --approved Yes --category connector",
        "harness-design-studio import-parts my-design erp-export.csv --approved Released --mass-unit kg",
    ],
    "import-lengths": [
        "harness-design-studio import-lengths my-design lengths.csv --unit mm --dry-run",
        "harness-design-studio import-lengths my-design lengths.csv --dry-run --json",
        "harness-design-studio import-lengths my-design lengths-in-inches.csv --unit in",
    ],
    "imports": [
        "harness-design-studio imports my-design",
        "harness-design-studio imports my-design --check",
        "harness-design-studio imports my-design --json --source cad/lengths.csv",
    ],
    "import-build-data": [
        "harness-design-studio import-build-data my-design strip-lengths.csv --dry-run",
        "harness-design-studio import-build-data my-design strip-lengths.csv --dry-run --json",
        "harness-design-studio import-build-data my-design pin-contacts.csv",
        "harness-design-studio import-build-data my-design accessories.csv",
        "harness-design-studio import-build-data my-design strip-lengths-in-inches.csv --unit in",
    ],
    "import-netlist": [
        "harness-design-studio import-netlist my-design wheel.net --device RW1 --prefix J "
        "--connector J1=RW1-J01 --signal-map CAN_H=CANH --dry-run",
        "harness-design-studio import-netlist my-design wheel.net --device RW1 --dry-run --json",
        "harness-design-studio import-netlist my-design wheel.net --device RW1 --pin-direction",
    ],
    "import-pinout": [
        "harness-design-studio import-pinout my-design gyro-pinout.csv --device GYRO1 --default-part MY-HD-9-F --dry-run",
        "harness-design-studio import-pinout my-design gyro-pinout.csv --device GYRO1 --default-part MY-HD-9-F --dry-run --json",
        'harness-design-studio import-pinout my-design icd.xlsx --device CAM1 --new-device "Camera" --part J1=MY-HD-9-F --part J2=MY-HD-15-M',
    ],
    "export-pinout": [
        "harness-design-studio export-pinout my-design --device GYRO1",
        "harness-design-studio export-pinout my-design --device GYRO1 -o gyro-pinout.xlsx",
        "harness-design-studio export-pinout my-design --device GYRO1 --json",
    ],
    "export-devices": [
        "harness-design-studio export-devices my-design device-library.json --device GYRO1",
        "harness-design-studio export-devices my-design device-library.json --device OBC1 --device PCU1",
        "harness-design-studio export-devices my-design device-library.json --device OBC1 --json",
    ],
    "import-devices": [
        "harness-design-studio import-devices my-design device-library.json --list",
        "harness-design-studio import-devices my-design device-library.json --dry-run --json",
        "harness-design-studio import-devices my-design device-library.json --device GYRO1 --dry-run",
    ],
    "export-subsystem": [
        'harness-design-studio export-subsystem my-design wheel-drive.json --device OBC1 --device RW1 --name "Wheel drive"',
        'harness-design-studio export-subsystem my-design wheel-drive.json --device OBC1 --name "Wheel drive" --json',
    ],
    "import-subsystem": [
        "harness-design-studio import-subsystem my-design wheel-drive.json --show",
        "harness-design-studio import-subsystem my-design wheel-drive.json --dry-run",
        "harness-design-studio import-subsystem my-design wheel-drive.json --dry-run --json",
    ],
    "review": [
        'harness-design-studio review my-design W001 --by "A. Engineer"',
        'harness-design-studio review my-design W001 --by "A. Engineer" --json',
    ],
    "release": [
        'harness-design-studio release my-design W001 --by "A. Engineer" --comment "First release" '
        '--checker "B. Checker"',
        'harness-design-studio release my-design W001 --by "A. Engineer" --comment "First release" --json',
    ],
    "revise": [
        'harness-design-studio revise my-design W001 --by "A. Engineer" --comment "Connector change"',
        'harness-design-studio revise my-design W001 --by "A. Engineer" --comment "Connector change" --json',
    ],
    "diff": [
        "harness-design-studio diff my-design W001",
        "harness-design-studio diff my-design W001 --from A",
        "harness-design-studio diff my-design W001 --json",
    ],
    "log": [
        "harness-design-studio log my-design",
        "harness-design-studio log my-design W001",
        "harness-design-studio log my-design --json",
    ],
    "compare": [
        "harness-design-studio compare old-checkout new-checkout",
        "harness-design-studio compare old-checkout new-checkout --json",
    ],
    "migrate": [
        "harness-design-studio migrate my-design",
        "harness-design-studio migrate my-design --json",
    ],
    "merge-fix": [
        "harness-design-studio merge-fix my-design",
        "harness-design-studio merge-fix my-design --json",
    ],
}


def _subparsers() -> dict[str, argparse.ArgumentParser]:
    parser = build_parser()
    action = next(a for a in parser._actions if isinstance(a, argparse._SubParsersAction))
    return dict(action.choices)


def _name(action: argparse.Action) -> str:
    if action.option_strings:
        text = ", ".join(action.option_strings)
        if action.nargs != 0:
            text += f" {action.metavar or action.dest.upper()}"
        return text
    return str(action.metavar or action.dest)


# arguments that have no help text in the program
FALLBACK_HELP = {
    "project": "the project folder",
    "file": "the file to read",
    "netlist": "the netlist file to read",
    "dry_run": "show what would be done and change nothing",
    "old": "the project folder to compare from",
    "new": "the project folder to compare with",
}


def _detail(action: argparse.Action) -> str:
    text = (action.help or FALLBACK_HELP.get(action.dest, "")).replace("|", "\\|")
    notes = []
    if isinstance(action, argparse._AppendAction):
        notes.append("repeatable")
    if action.choices and action.option_strings:
        notes.append("one of " + ", ".join(sorted(map(str, action.choices))))
    if (
        action.option_strings
        and action.default not in (None, False, [])
        and f"default {action.default}" not in text  # the help already says it
    ):
        notes.append(f"default {action.default}")
    return text + (f" ({'; '.join(notes)})" if notes else "")


def _json_section() -> list[str]:
    """The `--json` section: what every command with the option prints, made from `SHAPES`."""
    by_shape: dict[tuple[str, ...], list[str]] = {}
    for cmd, keys in SHAPES.items():
        by_shape.setdefault(keys, []).append(cmd)
    lines = [
        "",
        "## JSON output",
        "",
        "Every command that has a result in data form takes `--json`. The usual text lines are "
        "then not printed; one JSON document is, and the exit code is the one the command has "
        "without the option (the table above). It has no time, no user name and no absolute path, "
        "its lists are in a fixed order (by ID, as the text shows them) and the same design gives "
        "the same bytes, so it can be compared and kept in Git. `ok` comes first and is true when "
        "the exit code is 0. A command that cannot run at all (a project that cannot be read, a "
        "wrong option) writes its message to the standard error as before and prints nothing to the "
        "standard output; a command that ran and was refused (`generate` with errors, `export` that "
        "failed its check, `release` that is blocked) still prints its document, with `ok` false and "
        "the reasons in it. The same documents are what the Python interface gives "
        "([`user-manual/script-the-tool.md`](user-manual/script-the-tool.md)).",
        "",
        "`explain OBJECT --json` prints a list of derivations and `settings --json` the document of "
        "settings, definitions and assumptions, both as they did before (neither has an `ok`); "
        "`explain --all --out FOLDER --json` prints the document below. "
        "`export --out FOLDER` writes the outputs to FOLDER instead of `<project>/outputs`. "
        "`export` and `generate` take `--run-record [--author NAME]`: the record of the run "
        "(`run_record.json`) is then written into the outputs folder, outside every hash, and "
        "their document gains the key `run_record` (the name of the file); without the option "
        "no record is written and the document is as listed. "
        "`config` prints every engineering value with its unit, its use, whether it is set and "
        "where it came from, and the values it refused, in the order of the hand-over list.",
        "",
        "| Command | Keys of the document |",
        "| --- | --- |",
    ]
    for keys, cmds in by_shape.items():
        names = ", ".join(f"`{c}`" for c in cmds)
        lines.append(f"| {names} | {', '.join(f'`{k}`' for k in keys)} |")
    return lines


def render() -> str:
    subs = _subparsers()
    listed = {c for _, cmds in GROUPS for c in cmds}
    assert listed == set(subs), f"commands not in a group: {sorted(set(subs) ^ listed)}"
    lines = [
        "# Command line reference",
        "",
        "Generated from the program by `python -m tools.gen_cli_docs`; do not edit by hand. "
        "`project` is a project folder. Run `harness-design-studio COMMAND --help` for the same text in a terminal. "
        "`harness` still works as a short alias of `harness-design-studio` (the same program).",
        "",
        "## Exit codes",
        "",
        "| Code | Meaning |",
        "| --- | --- |",
        "| 0 | success (warnings are allowed) |",
        "| 1 | the project has errors, or a step is blocked (for example a release, or an import or `config` that found problems and changed nothing, or an import of a file with nothing in it) |",
        "| 2 | usage error, or a project or file that could not be read |",
        "| 130 | interrupted with Ctrl-C |",
        "",
        "A project with damaged files (a file that is not valid, a link, over 64 MB or unreadable) "
        "is refused with exit 2 and the damaged file named by every command that reports on it or "
        "changes it: `drc`, `verify`, `export`, `generate`, `config`, `library`, `log`, `diff`, "
        "`compare`, `review`, `release`, `revise`, `migrate` and the imports. Only `validate` and "
        "`check` read it and list the damage (exit 1), so you can see what to repair. "
        "With Ctrl-C a command prints `interrupted` and ends with 130 (if it was saving, run "
        "`harness-design-studio validate`). A reader that closes the pipe (`harness-design-studio generate | head -1`) does "
        "not stop the command: it still finishes and saves.",
        "",
        "An import whose file says what the project already holds changes nothing, prints "
        "`Already up to date.` and ends with 0, so it can run again on every build. "
        "Every command that changes a project takes the same lock as the app, so the two never write "
        "at once. The commands that import data (`import-parts`, `import-lengths`, `import-build-data`, `import-netlist`, `import-pinout`, `import-devices`) "
        "accept `--dry-run`: they show what they would do and change nothing; "
        "`config --ampacity-csv` does not. "
        "The option `--author NAME` (given before the command) names who is making the changes "
        "of a run in the change journal of a project that has one; the environment variable "
        "`HARNESS_AUTHOR` does the same, and without either the journal uses the name Git has "
        "(`user.name`), then the user of the computer.",
        "",
        "What an import prints. Every import that reads a file says what it read before it lists "
        "the rows: `Read 12 row(s) of segment lengths from lengths.csv (sha256 117043908312).`, "
        "`Columns read: harness -> harness, segment -> segment, length -> length`, a line "
        "`warning: the column 'Notes' is not read; its values are not imported.` for every column "
        "that is left out, and the unit: `Unit: length in mm (assumed; --unit says another).` or "
        "`Unit: length in in (given with --unit).`. A value that is converted is shown with the "
        "value as written, its unit and the value stored: `Converted, row 2 (ZZ-1): 0.25 kg = 250 g`; "
        "`import-lengths` shows it on the line of its row, `row 2: OK W001 / W001-L1: 850 mm = 0.85 m`. "
        "A row that is dropped says why: `row 3: ERROR Harness 'W009' does not exist`. "
        "An import that is applied (not with `--dry-run`) records the file in the project, in "
        "`imports/records.json` (kind, file name, SHA-256, rows read, rows dropped with the reason, "
        "values converted, columns read and left out, unit, tool version; no time and no absolute "
        "path), and ends with `Import record: lengths:lengths.csv written to imports/records.json.`; "
        "importing the same file again replaces its record, and an unchanged file changes nothing. "
        "`harness-design-studio imports` lists the records and shows whether a source file has "
        "changed since. With `--json` every import prints the same facts as the last key, `import` "
        "(the record, with `record_written` true when this run wrote it, and the `warnings` of "
        "`import-build-data`), and `imports --json` prints `records_file`, `count`, "
        "`sources_changed` and the `imports` with their `status` and `current_sha256`.",
        "",
        "The examples show the form of each command with example names. They do not all work "
        "on any project: `release` is blocked until its conditions are met (placeholder "
        "configuration, unapproved parts, missing gauges and lengths; see "
        "[`GETTING_STARTED.md`](GETTING_STARTED.md)), and `revise` works only on a released "
        "harness.",
        "",
        "## Contents",
        "",
        "- [JSON output](#json-output): `--json` on every command that has a result in data form",
    ]
    for title, cmds in GROUPS:
        lines.append(f"- {title}: " + ", ".join(f"[`{c}`](#{PROG}-{c})" for c in cmds))
    lines += _json_section()
    for title, cmds in GROUPS:
        lines += ["", f"## {title}"]
        for cmd in cmds:
            p = subs[cmd]
            actions = [a for a in p._actions if not isinstance(a, argparse._HelpAction)]
            positional = [a for a in actions if not a.option_strings]
            usage = " ".join(
                [f"{PROG} {cmd}"]
                + [f"[{_name(a)}]" if a.nargs == "?" else _name(a) for a in positional]
                + (["[options]"] if len(positional) != len(actions) else [])
            )
            lines += [
                "",
                f"### {PROG} {cmd}",
                "",
                p.description or p.format_usage(),
                "",
                f"`{usage}`",
            ]
            if actions:
                lines += ["", "| Argument | Meaning |", "| --- | --- |"]
                lines += [f"| `{_name(a)}` | {_detail(a)} |" for a in actions]
            lines += ["", "Examples:", "", "```"] + EXAMPLES[cmd] + ["```"]
    return "\n".join(lines) + "\n"


def main() -> None:
    TARGET.write_text(render())
    print(f"wrote {TARGET}")


if __name__ == "__main__":
    main()
