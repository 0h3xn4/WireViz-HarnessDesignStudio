"""Commands for getting started: create a project from an example, copy the import templates."""

import argparse
import sys
from pathlib import Path

from harness_design_studio.core import templates

COMMANDS = ("new", "templates", "schema")


def register(sub: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    n = sub.add_parser(
        "new",
        help="create a new project from an example (blank, first-steps, minimal-satellite, small-satellite, flatsat)",
        description="Create a project folder from one of the bundled examples. "
        "`harness new --list` shows them. The folder must not exist yet or be empty.",
    )
    n.add_argument("folder", type=Path, nargs="?", help="the new project folder")
    n.add_argument("--template", default="blank", help="which example to start from")
    n.add_argument("--name", default=None, help="project name (default: the example's name)")
    n.add_argument("--list", action="store_true", help="list the examples and exit")
    t = sub.add_parser(
        "templates",
        help="copy the import templates (CSV files, netlist, scripts, checklist) to a folder",
        description="Copy the bundled templates for the imports, CI scripts and the review "
        "checklist. The folder must not exist yet or be empty.",
    )
    t.add_argument("folder", type=Path, help="where to put the templates")
    sc = sub.add_parser(
        "schema",
        help="write JSON Schemas of the project files (for editors that complete and check JSON)",
        description="Write one JSON Schema per kind of project file, made from the program's own "
        "model, and a settings fragment that maps the files to them. For people who edit project "
        "files by hand. Nothing is downloaded. The folder must not exist yet or be empty.",
    )
    sc.add_argument(
        "folder", type=Path, help="where to put the schemas (for example my-design/schemas)"
    )


def run(args: argparse.Namespace) -> int:
    if args.command == "schema":
        return _schema(args.folder)
    if args.command == "templates":
        files = templates.copy_import_templates(args.folder)
        print(
            f"{len(files)} files written to {args.folder}. Start with {args.folder / 'README.md'}."
        )
        return 0
    if args.list:
        for t in templates.TEMPLATES:
            print(f"{t.name:18} {t.summary}")
        return 0
    if args.folder is None:
        print("error: give the folder for the new project (or use --list).", file=sys.stderr)
        return 2
    project = templates.create_project(args.folder, args.template, args.name)
    print(
        f"Project '{project.meta.name}' created in {args.folder} "
        f"({len(project.units)} units, {len(project.interfaces)} interfaces).\n"
        f"Next: harness validate {args.folder}   or open it in the app (File > Open project)."
    )
    return 0


def _schema(folder: Path) -> int:
    from harness_design_studio.core import schemas

    if folder.exists() and (not folder.is_dir() or any(folder.iterdir())):
        print(f"error: {folder} exists and is not an empty folder.", file=sys.stderr)
        return 2
    folder.mkdir(parents=True, exist_ok=True)
    docs = schemas.schemas()
    for name, schema in docs.items():
        (folder / f"{name}.schema.json").write_text(schemas.dumps(schema), encoding="utf-8")
    (folder / "editor-settings.json").write_text(
        schemas.dumps(schemas.editor_settings()), encoding="utf-8"
    )
    print(
        f'{len(docs)} schemas written to {folder}. In VS Code, copy the "json.schemas" entry of '
        f"{folder / 'editor-settings.json'} into the .vscode/settings.json of the project "
        "(the schemas folder must sit inside the project folder as schemas/)."
    )
    return 0
