"""`settings`: what the tool assumes for this project, and the values it uses (D-191, S2)."""

import argparse
import json
import sys
from pathlib import Path

from harness_design_studio.core import configcheck, settings
from harness_design_studio.core.commands import History, SetConfig
from harness_design_studio.core.io.loader import load_project
from harness_design_studio.core.io.saver import save_project
from harness_design_studio.core.model import ConfigFile

COMMANDS = ("settings",)


def register(sub: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    p = sub.add_parser(
        "settings",
        help="list every setting the results depend on, the assumptions built into the tool and where each value comes from",
        description="The Assumptions page on the command line. For every setting: the value in force, "
        "its unit, whether it is set by the project, the tool's own default (the behaviour before "
        "the setting existed) or not set, what depends on it and where the number comes from; then "
        "the assumptions built into the tool, each with the settings that parameterise it, and the "
        "fixed definitions. `--json` prints the same as data. `--set FILE.KEY=VALUE` (VALUE is JSON, "
        "for example model.service_loops_per_wire=0) changes one value; it is refused, and nothing "
        "is changed, when the value is outside its range.",
    )
    p.add_argument("project", type=Path, help="project folder")
    p.add_argument("--json", action="store_true", help="print the settings as JSON")
    p.add_argument(
        "--set",
        action="append",
        default=[],
        metavar="FILE.KEY=VALUE",
        help="set one value (VALUE as JSON, for example model.service_loops_per_wire=0); repeat for several",
    )


def _set(project, args: argparse.Namespace) -> int:  # type: ignore[no-untyped-def]
    for item in args.set:
        target, sep, raw = item.partition("=")
        file, dot, key = target.partition(".")
        if not (sep and dot and settings.setting(file, key)):
            print(
                f"error: '{item}' is not FILE.KEY=VALUE of a setting (see `settings`).",
                file=sys.stderr,
            )
            return 2
        try:
            value = json.loads(raw)
        except ValueError:
            value = raw  # a bare word
        cfg = project.config.get(file) or ConfigFile(name=file, placeholder=False, values={})
        History(project).execute(
            f"Set {file}.{key}", [SetConfig(configcheck.with_value(cfg, key, value))]
        )
    invalid = [i for i in configcheck.validate(project) if i.severity == "error"]
    if invalid:
        print(f"error: {invalid[0].message}", file=sys.stderr)
        print("Nothing was changed.", file=sys.stderr)
        return 1
    save_project(project, args.project)
    print(f"{len(args.set)} value(s) set.")
    return 0


def run(args: argparse.Namespace) -> int:
    project = load_project(args.project).project
    if args.set:
        code = _set(project, args)
        if code:
            return code
    if args.json:
        print(json.dumps(settings.to_dict(project), indent=2, ensure_ascii=False, sort_keys=False))
    elif not args.set:
        print(settings.render(project))
    return 0
