"""Generate docs/CLI.md (every `harness-design-studio` command, its arguments and examples) from the
program's own argument parser, so the reference cannot drift from the commands. A test fails if the
committed file is stale. Usage: python -m tools.gen_cli_docs"""

import argparse
from pathlib import Path

from harness_design_studio.cli.main import PROG, build_parser

TARGET = Path(__file__).resolve().parents[1] / "docs" / "CLI.md"

# command -> (group, examples). Examples are written by hand; a test checks every command has some.
GROUPS = (
    ("Start", ("new", "templates", "schema")),
    ("Check", ("validate", "check", "drc", "verify")),
    ("Generate and export", ("generate", "export")),
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
        ),
    ),
    ("Write data out", ("export-pinout", "export-devices", "export-subsystem")),
    ("Review, release and change", ("review", "release", "revise", "diff", "log", "compare")),
    ("Maintenance", ("migrate",)),
)
EXAMPLES: dict[str, list[str]] = {
    "new": [
        "harness-design-studio new --list",
        'harness-design-studio new my-design --name "My first design"',
        "harness-design-studio new wheel-link --template first-steps",
    ],
    "templates": ["harness-design-studio templates my-templates"],
    "schema": ["harness-design-studio schema my-design/schemas"],
    "validate": ["harness-design-studio validate my-design"],
    "check": ["harness-design-studio check my-design"],
    "drc": ["harness-design-studio drc my-design > drc-report.md"],
    "verify": [
        "harness-design-studio verify my-design",
        "harness-design-studio verify my-design --outputs",
    ],
    "generate": ["harness-design-studio generate my-design"],
    "export": [
        "harness-design-studio export my-design",
        "harness-design-studio export my-design --drawings",
    ],
    "config": [
        "harness-design-studio config my-design",
        "harness-design-studio config my-design --ampacity-csv ampacity.csv",
        "harness-design-studio config my-design --apply-profile ecss-q-st-30-11c",
        'harness-design-studio config my-design --counterparts "TX=RX, MOSI=MISO, OUT=IN"',
    ],
    "library": [
        "harness-design-studio library my-design",
        'harness-design-studio library my-design --library-version 4 --library-source "ESCC part data, supplier file" --library-date 2026-09-30',
    ],
    "import-parts": [
        "harness-design-studio import-parts my-design parts.csv --approved Approved --pending Review "
        "--rejected Rejected --dry-run",
        "harness-design-studio import-parts my-design connectors.xlsx --approved Yes --category connector",
    ],
    "import-lengths": [
        "harness-design-studio import-lengths my-design lengths.csv --unit mm --dry-run"
    ],
    "import-build-data": [
        "harness-design-studio import-build-data my-design strip-lengths.csv --dry-run",
        "harness-design-studio import-build-data my-design pin-contacts.csv",
        "harness-design-studio import-build-data my-design accessories.csv",
    ],
    "import-netlist": [
        "harness-design-studio import-netlist my-design wheel.net --device RW1 --prefix J "
        "--connector J1=RW1-J01 --signal-map CAN_H=CANH --dry-run",
    ],
    "import-pinout": [
        "harness-design-studio import-pinout my-design gyro-pinout.csv --device GYRO1 --default-part MY-HD-9-F --dry-run",
        'harness-design-studio import-pinout my-design icd.xlsx --device CAM1 --new-device "Camera" --part J1=MY-HD-9-F --part J2=MY-HD-15-M',
    ],
    "export-pinout": [
        "harness-design-studio export-pinout my-design --device GYRO1",
        "harness-design-studio export-pinout my-design --device GYRO1 -o gyro-pinout.xlsx",
    ],
    "export-devices": [
        "harness-design-studio export-devices my-design device-library.json --device GYRO1",
        "harness-design-studio export-devices my-design device-library.json --device OBC1 --device PCU1",
    ],
    "import-devices": [
        "harness-design-studio import-devices my-design device-library.json --list",
        "harness-design-studio import-devices my-design device-library.json --device GYRO1 --dry-run",
    ],
    "export-subsystem": [
        'harness-design-studio export-subsystem my-design wheel-drive.json --device OBC1 --device RW1 --name "Wheel drive"',
    ],
    "import-subsystem": [
        "harness-design-studio import-subsystem my-design wheel-drive.json --show",
        "harness-design-studio import-subsystem my-design wheel-drive.json --dry-run",
    ],
    "review": ['harness-design-studio review my-design W001 --by "A. Engineer"'],
    "release": [
        'harness-design-studio release my-design W001 --by "A. Engineer" --comment "First release" '
        '--checker "B. Checker"',
    ],
    "revise": [
        'harness-design-studio revise my-design W001 --by "A. Engineer" --comment "Connector change"'
    ],
    "diff": [
        "harness-design-studio diff my-design W001",
        "harness-design-studio diff my-design W001 --from A",
    ],
    "log": ["harness-design-studio log my-design", "harness-design-studio log my-design W001"],
    "compare": ["harness-design-studio compare old-checkout new-checkout"],
    "migrate": ["harness-design-studio migrate my-design"],
    "merge-fix": ["harness-design-studio merge-fix my-design"],
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
        "`config --ampacity-csv` does not.",
        "",
        "The examples show the form of each command with example names. They do not all work "
        "on any project: `release` is blocked until its conditions are met (placeholder "
        "configuration, unapproved parts, missing gauges and lengths; see "
        "[`GETTING_STARTED.md`](GETTING_STARTED.md)), and `revise` works only on a released "
        "harness.",
        "",
        "## Contents",
        "",
    ]
    for title, cmds in GROUPS:
        lines.append(f"- {title}: " + ", ".join(f"[`{c}`](#{PROG}-{c})" for c in cmds))
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
