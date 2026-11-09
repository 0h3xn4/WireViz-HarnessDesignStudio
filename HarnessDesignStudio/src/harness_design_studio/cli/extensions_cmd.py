# SPDX-FileCopyrightText: 2026 0h3xn4
# SPDX-License-Identifier: GPL-3.0-only
"""`extensions`, `trust` and `import-plugin`: what a project's extensions are, which Python code may
run, and the readers that plug-ins add (D-191 (5), S8)."""

import argparse
import sys
from pathlib import Path
from typing import Any

from harness_design_studio.cli.jsonout import Report, add_json_flag
from harness_design_studio.core.commands import History
from harness_design_studio.core.extensions import manager, plugins, trust
from harness_design_studio.core.io.loader import load_project
from harness_design_studio.core.io.saver import save_project

COMMANDS = ("extensions", "trust", "import-plugin")

SANDBOX_NOTE = (
    "A plug-in runs with your rights: it can read and write the files you can and use the network "
    "of this computer. The tool has no sandbox. Trust it only if you have read it or you trust who wrote it."
)


def register(sub: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    e = sub.add_parser(
        "extensions",
        help="list what is registered for a project: the built-in rules, fields, tables and importers and those of its extensions, and whether each is enabled and trusted",
        description="Lists the extensions of a project (the folder `extensions/`): the declarative files "
        "(rules, tables and lookup tables written as data) and the Python plug-ins, each with its "
        "name, version, source, SHA-256, whether the project enables it and, for Python code, whether "
        "you trust it. Without options it lists what the extensions add; with --all it lists the "
        "built-in items too. Nothing in the folder runs unless the project enables it in "
        "`extensions/enabled.json`, and Python code is not even imported unless you have also trusted "
        "that exact code (`trust`). --enable NAME and --disable NAME change enabled.json (NAME is a "
        "file such as min-gauge.json, or the name of a plug-in). Exit 1 while something the project "
        "enables is not applied.",
    )
    e.add_argument("project", type=Path, help="project folder")
    e.add_argument("--all", action="store_true", help="also list the built-in items")
    e.add_argument(
        "--docs",
        action="store_true",
        help="print the rules of the extensions as a Markdown page, in the form of docs/RULES.md (why, how to fix, requirement IDs, the file or plug-in each comes from)",
    )
    e.add_argument(
        "--enable",
        action="append",
        default=[],
        metavar="NAME",
        help="enable a declarative file (its file name) or a plug-in (its name) in extensions/enabled.json; repeat for several",
    )
    e.add_argument(
        "--disable",
        action="append",
        default=[],
        metavar="NAME",
        help="take a file or a plug-in out of extensions/enabled.json; repeat for several",
    )
    add_json_flag(e)
    t = sub.add_parser(
        "trust",
        help="show what a Python plug-in is and trust it (or take trust back); the code is not run before you do",
        description="Python code is never loaded unless the project enables it and you trusted that exact "
        "code. Without NAME this lists the plug-ins of the project and whether each is trusted. With "
        "NAME it shows what the code is (name, version, file, SHA-256, number of lines) and asks you "
        "to type the plug-in's name to confirm; --yes confirms without asking (for scripts). The trust "
        "is kept in YOUR settings folder, not in the project, so a project you clone cannot trust "
        "itself; it is tied to the hash, so a change of the code takes it away. --revoke takes trust "
        "back. " + SANDBOX_NOTE,
    )
    t.add_argument("project", type=Path, help="project folder")
    t.add_argument("name", nargs="?", metavar="NAME", help="the plug-in (as `extensions` lists it)")
    t.add_argument("--revoke", action="store_true", help="take back the trust of this plug-in")
    t.add_argument("--yes", action="store_true", help="confirm without asking (for scripts)")
    add_json_flag(t)
    i = sub.add_parser(
        "import-plugin",
        help="read a file with an importer that a trusted plug-in provides",
        description="Run an importer registered by a plug-in of the project (see `extensions`) on a "
        "file. The importer proposes the changes; --dry-run shows them and changes nothing.",
    )
    i.add_argument("project", type=Path, help="project folder")
    i.add_argument("importer", metavar="NAME", help="the importer, as `extensions` lists it")
    i.add_argument("file", type=Path, help="the file to read")
    i.add_argument("--dry-run", action="store_true", help="show the preview only")
    add_json_flag(i)


# ---- extensions -------------------------------------------------------------------------------------------


def _change_enabled(root: Path, enable: list[str], disable: list[str], rep: Report) -> int:
    declarative, plugin_names, problems, _present = manager.read_enabled(root)
    if problems:
        print(f"error: {problems[0].render()}; fix extensions/enabled.json first.", file=sys.stderr)
        return 2
    folder = root / manager.FOLDER
    files = (
        {p.name for p in folder.glob("*.json") if p.name != manager.ENABLED_FILE}
        if folder.is_dir()
        else set()
    )
    names = {c.name for c in plugins.project_candidates(root) + plugins.installed_candidates()}
    for name in [*enable, *disable]:
        if name not in files and name not in names:
            print(
                f"error: '{name}' is neither a file in extensions/ nor a plug-in (see `extensions`).",
                file=sys.stderr,
            )
            return 2
    for name in enable:
        (declarative if name in files else plugin_names).append(name)
    for name in disable:
        declarative[:] = [d for d in declarative if d != name]
        plugin_names[:] = [p for p in plugin_names if p != name]
    manager.write_enabled(root, declarative, plugin_names)
    rep.say(
        f"extensions/enabled.json written: {len(set(declarative))} file(s), {len(set(plugin_names))} plug-in(s)."
    )
    return 0


def _short(sha: str) -> str:
    return sha[:12]


def _extensions(args: argparse.Namespace) -> int:
    rep = Report(args.json)
    root: Path = args.project
    if args.enable or args.disable:
        code = _change_enabled(root, args.enable, args.disable, rep)
        if code:
            return code
    project = load_project(root).project
    if args.docs:
        print(manager.rules_markdown(project), end="")
        return 0
    doc = manager.listing(project)
    problems = manager.problems(project)
    ext_items = [i for i in doc["items"] if i["source"] != "built-in"]
    shown = doc["items"] if args.all else ext_items
    if rep.as_json:
        rep.put(**doc)
        return rep.finish(1 if problems else 0)
    if not doc["has_folder"]:
        rep.say("This project has no extensions folder. Nothing is added to the tool.")
        built = len(doc["items"])
        rep.say(
            f"{built} built-in items are registered (rules, fields, models, tables, importers); `--all` lists them."
        )
        if args.all:
            _print_items(rep, shown)
        return 0
    rep.say("Declarative files (data, no code):")
    for f in doc["files"]:
        rep.say(
            f"  {f['file']:48} {f['name']} {f['version']} sha256 {_short(f['sha256'])}  "
            f"{'enabled' if f['enabled'] else 'not enabled'}, {f['status']}; "
            f"{f['rules']} rule(s), {f['tables']} table(s), {f['lookups']} lookup(s)"
        )
    if not doc["files"]:
        rep.say("  none")
    rep.say("Python plug-ins (code; need to be enabled and trusted):")
    for p in doc["plugins"]:
        rep.say(
            f"  {p['name']:28} {p['version']} {','.join(p['kinds']) or '-'}  {p['where']}  sha256 {_short(p['sha256'])}  "
            f"{'enabled' if p['enabled'] else 'not enabled'}, {'trusted' if p['trusted'] else 'not trusted'}: {p['state']}"
            + (f" ({p['message']})" if p["message"] and p["state"] not in ("disabled",) else "")
        )
    if not doc["plugins"]:
        rep.say("  none")
    rep.say("Registered items" + ("" if args.all else " added by extensions") + ":")
    _print_items(rep, shown)
    if not args.all:
        rep.say(
            f"  ({len(doc['items']) - len(ext_items)} built-in items not listed; --all lists them)"
        )
    for issue in doc["issues"]:
        where = f"{issue['file']}:{issue['line']}" if issue["line"] else issue["file"]
        rep.say(
            f"{issue['severity']}: {where}: "
            + (f"{issue['path']}: " if issue["path"] else "")
            + issue["message"]
        )
    return rep.finish(1 if problems else 0)


def _print_items(rep: Report, items: list[dict[str, Any]]) -> None:
    if not items:
        rep.say("  none")
    for it in items:
        trusted = (
            "built-in"
            if it["source"] == "built-in"
            else (
                "data" if it["trusted"] is None else ("trusted" if it["trusted"] else "not trusted")
            )
        )
        rep.say(
            f"  {it['kind']:9} {str(it['name']):40} {it['source']:11} {str(it['origin']):44} {it['version']:8} "
            f"{str(it['sha256'])[:12]:12} {'enabled' if it['enabled'] else 'not enabled'}, {trusted}"
        )


# ---- trust ------------------------------------------------------------------------------------------------


def _describe(c: plugins.Candidate) -> list[str]:
    return [
        f"  name:      {c.name}",
        f"  version:   {c.version}",
        f"  kinds:     {', '.join(c.kinds)}",
        f"  where:     {c.where}",
        f"  sha256:    {c.sha256}",
        f"  lines:     {c.lines}",
        *([f"  what:      {c.description}"] if c.description else []),
    ]


def _trust(args: argparse.Namespace) -> int:
    rep = Report(args.json)
    root: Path = args.project
    ext = manager.discover(root)
    candidates = plugins.project_candidates(root) + plugins.installed_candidates()
    if args.name is None:
        infos = ext.plugins if ext else ()
        for p in infos:
            rep.say(
                f"{p.name}  {p.version}  {p.where}  sha256 {_short(p.sha256)}  {'trusted' if p.trusted else 'not trusted'}, {p.state}"
            )
        if not infos:
            rep.say("This project has no Python plug-ins.")
        rep.put(
            action="list",
            name="",
            version="",
            sha256="",
            lines=0,
            where="",
            trusted=False,
            changed=False,
        )
        return rep.finish(0)
    found = next((c for c in candidates if c.name == args.name), None)
    if found is None:
        print(f"error: no plug-in named '{args.name}' (see `extensions`).", file=sys.stderr)
        return 2
    if args.revoke:
        n = trust.revoke(found.name)
        rep.say(f"Trust of {found.name} taken back." if n else f"{found.name} was not trusted.")
        rep.put(
            action="revoke",
            name=found.name,
            version=found.version,
            sha256=found.sha256,
            lines=found.lines,
            where=found.where,
            trusted=False,
            changed=n > 0,
        )
        return rep.finish(0)
    if not found.usable:
        print(f"error: {found.name} cannot be trusted: {found.problem}.", file=sys.stderr)
        return 2
    already = trust.is_trusted(found.name, found.sha256)
    for line in ("This is the code you are asked to trust:", *_describe(found), "", SANDBOX_NOTE):
        rep.say(line)
    if ext is not None and found.name not in ext.enabled_plugins:
        rep.say(
            f"Note: this project does not enable {found.name} (extensions/enabled.json); trusting it does not enable it."
        )
    changed = False
    if already:
        rep.say("This exact code is already trusted.")
    elif args.yes or _confirmed(found.name, rep):
        trust.trust(found.name, found.sha256, found.version, found.where)
        changed = True
        rep.say(
            f"{found.name} is trusted on this computer (this exact code, sha256 {_short(found.sha256)})."
        )
    else:
        rep.put(
            action="trust",
            name=found.name,
            version=found.version,
            sha256=found.sha256,
            lines=found.lines,
            where=found.where,
            trusted=False,
            changed=False,
        )
        rep.say("Not trusted: nothing was changed.")
        return rep.finish(1)
    rep.put(
        action="trust",
        name=found.name,
        version=found.version,
        sha256=found.sha256,
        lines=found.lines,
        where=found.where,
        trusted=True,
        changed=changed,
    )
    return rep.finish(0)


def _confirmed(name: str, rep: Report) -> bool:
    """Ask for the plug-in's name, typed. Without a person to ask (--json, no terminal) the answer is no."""
    if rep.as_json or not sys.stdin or not sys.stdin.isatty():
        rep.say("There is nobody to ask here. Run it in a terminal, or add --yes.")
        return False
    print(
        f"Type the name of the plug-in ({name}) to trust this code, or press Enter to cancel: ",
        end="",
        flush=True,
    )
    return sys.stdin.readline().strip() == name


# ---- import-plugin -----------------------------------------------------------------------------------------


def _import_plugin(args: argparse.Namespace) -> int:
    rep = Report(args.json)
    project = load_project(args.project).project
    rt = manager.runtime(project)
    importer = rt.importers.get(args.importer) if rt is not None else None
    if importer is None:
        print(
            f"error: no importer named '{args.importer}' from an enabled and trusted plug-in (see `extensions`).",
            file=sys.stderr,
        )
        return 2
    if project.read_only:
        print("error: this project is read-only (saved by a newer tool version).", file=sys.stderr)
        return 2
    try:
        result = importer.read(project, args.file)
    except Exception as exc:  # the importer is a plug-in's: whatever it raises is reported
        print(
            f"error: the importer {args.importer} stopped: {type(exc).__name__}: {str(exc)[:200]}",
            file=sys.stderr,
        )
        return 1
    for line in result.rows:
        rep.say(f"  {line}")
    for note in result.notes:
        rep.say(f"note: {note}")
    changed = bool(result.ops)
    if changed and not args.dry_run:
        History(project).execute(f"Import with {args.importer}", list(result.ops))
        save_project(project, args.project)
        rep.say(f"{len(result.ops)} change(s) saved.")
    elif not changed:
        rep.say("Already up to date.")
    else:
        rep.say(f"{len(result.ops)} change(s) would be made (dry run).")
    rep.put(
        dry_run=args.dry_run,
        changed=changed and not args.dry_run,
        importer=args.importer,
        rows=list(result.rows),
        notes=list(result.notes),
    )
    return rep.finish(0)


def run(args: argparse.Namespace) -> int:
    if args.command == "extensions":
        return _extensions(args)
    if args.command == "trust":
        return _trust(args)
    return _import_plugin(args)
