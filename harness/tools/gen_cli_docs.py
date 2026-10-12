"""Generate docs/CLI.md (every `harness` command with its arguments and examples) from the
program's own argument parser, so the reference cannot drift from the commands. A test fails if the
committed file is stale. Usage: python -m tools.gen_cli_docs"""

import argparse
from pathlib import Path

from harness_design_studio.cli.main import build_parser

TARGET = Path(__file__).resolve().parents[1] / "docs" / "CLI.md"

# command -> (group, examples). Examples are written by hand; a test checks every command has some.
GROUPS = (
    ("Start", ("new", "templates", "schema")),
    ("Check", ("validate", "check", "drc", "verify")),
    ("Generate and export", ("generate", "export")),
    ("Bring in data", ("config", "library", "import-parts", "import-lengths", "import-netlist")),
    ("Review, release and change", ("review", "release", "revise", "diff", "log", "compare")),
    ("Maintenance", ("migrate",)),
)
EXAMPLES: dict[str, list[str]] = {
    "new": [
        "harness new --list",
        'harness new my-design --name "My first design"',
        "harness new wheel-link --template first-steps",
    ],
    "templates": ["harness templates my-templates"],
    "schema": ["harness schema my-design/schemas"],
    "validate": ["harness validate my-design"],
    "check": ["harness check my-design"],
    "drc": ["harness drc my-design > drc-report.md"],
    "verify": ["harness verify my-design", "harness verify my-design --outputs"],
    "generate": ["harness generate my-design"],
    "export": ["harness export my-design"],
    "config": [
        "harness config my-design",
        "harness config my-design --ampacity-csv ampacity.csv",
        "harness config my-design --apply-profile ecss-q-st-30-11c",
    ],
    "library": [
        "harness library my-design",
        'harness library my-design --library-version 4 --library-source "ESCC part data, supplier file" --library-date 2026-09-30',
    ],
    "import-parts": [
        "harness import-parts my-design parts.csv --approved Approved --pending Review "
        "--rejected Rejected --dry-run",
        "harness import-parts my-design connectors.xlsx --approved Yes --category connector",
    ],
    "import-lengths": ["harness import-lengths my-design lengths.csv --unit mm --dry-run"],
    "import-netlist": [
        "harness import-netlist my-design wheel.net --unit RW1 --prefix J "
        "--connector J1=RW1-J01 --signal-map CAN_H=CANH --dry-run",
    ],
    "review": ['harness review my-design W001 --by "A. Engineer"'],
    "release": [
        'harness release my-design W001 --by "A. Engineer" --comment "First release" '
        '--checker "B. Checker"',
    ],
    "revise": ['harness revise my-design W001 --by "A. Engineer" --comment "Connector change"'],
    "diff": ["harness diff my-design W001", "harness diff my-design W001 --from A"],
    "log": ["harness log my-design", "harness log my-design W001"],
    "compare": ["harness compare old-checkout new-checkout"],
    "migrate": ["harness migrate my-design"],
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
        "`project` is a project folder. Run `harness COMMAND --help` for the same text in a terminal.",
        "",
        "## Exit codes",
        "",
        "| Code | Meaning |",
        "| --- | --- |",
        "| 0 | success (warnings are allowed) |",
        "| 1 | the project has errors, or a step is blocked (for example a release) |",
        "| 2 | usage error, or a project or file that could not be read |",
        "",
        "Every command that changes a project takes the same lock as the app, so the two never write "
        "at once. The commands that import data (`import-parts`, `import-lengths`, `import-netlist`) "
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
        lines.append(f"- {title}: " + ", ".join(f"[`{c}`](#harness-{c})" for c in cmds))
    for title, cmds in GROUPS:
        lines += ["", f"## {title}"]
        for cmd in cmds:
            p = subs[cmd]
            actions = [a for a in p._actions if not isinstance(a, argparse._HelpAction)]
            positional = [a for a in actions if not a.option_strings]
            usage = " ".join(
                [f"harness {cmd}"]
                + [f"[{_name(a)}]" if a.nargs == "?" else _name(a) for a in positional]
                + (["[options]"] if len(positional) != len(actions) else [])
            )
            lines += [
                "",
                f"### harness {cmd}",
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
