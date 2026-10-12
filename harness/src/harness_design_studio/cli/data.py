"""Commands that bring outside data into a project: config, import-parts, import-lengths."""

import argparse
import sys
from pathlib import Path

from harness_design_studio.core import configcheck, standard_profiles
from harness_design_studio.core.commands import History, SetConfig
from harness_design_studio.core.errors import HarnessError
from harness_design_studio.core.generate.lengths import plan_length_import
from harness_design_studio.core.imports import ImportError_, read_table, read_table_sheet
from harness_design_studio.core.io.loader import load_project
from harness_design_studio.core.io.saver import save_project
from harness_design_studio.core.library_import import (
    describe_library,
    guess_mapping,
    library_ops,
    plan_parts_import,
)

COMMANDS = ("config", "library", "import-parts", "import-lengths", "import-netlist")
UNITS = {"mm": 0.001, "m": 1.0, "cm": 0.01}


def register(sub: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    c = sub.add_parser(
        "config",
        help="list missing or invalid engineering values; optionally load an ampacity table",
        description="Hand-over checklist for the engineering values (derating, grounding, test limits ...). Exit 1 while something is missing or invalid.",
    )
    c.add_argument("project", type=Path)
    c.add_argument(
        "--ampacity-csv",
        type=Path,
        default=None,
        help="CSV with a gauge column and an amperes column; sets derating.ampacity_a_by_awg",
    )
    c.add_argument(
        "--apply-profile",
        default=None,
        metavar="NAME",
        help="fill the unset values from a standard profile (ecss-q-st-30-11c, ecss-e-st-20-07c); "
        "values you already set are kept; the files stay placeholders until you review them",
    )
    lib = sub.add_parser(
        "library",
        help="show or set where the parts library comes from (name, version, source, date)",
        description="Without options: print the library's name, version, source and date. With options: record them. The date is the date of the data (YYYY-MM-DD) and is entered by you; the tool never reads the clock into a project.",
    )
    lib.add_argument("project", type=Path)
    _library_options(lib)
    pp = sub.add_parser(
        "import-parts",
        help="import an approved-parts list (CSV or XLSX)",
        description="Import parts with their approval status. Say what the approval values in your list mean; unknown values are rejected, never guessed.",
    )
    pp.add_argument("project", type=Path)
    pp.add_argument("file", type=Path)
    pp.add_argument(
        "--approved",
        action="append",
        default=[],
        help="a value of the approval column that means approved (repeat)",
    )
    pp.add_argument(
        "--pending", action="append", default=[], help="a value that means not decided yet (repeat)"
    )
    pp.add_argument(
        "--rejected", action="append", default=[], help="a value that means not approved (repeat)"
    )
    pp.add_argument(
        "--category",
        default=None,
        help="category for rows that have none (connector, contact, backshell, wire, sleeving, label)",
    )
    pp.add_argument("--dry-run", action="store_true", help="show the preview only")
    _library_options(pp)
    nn = sub.add_parser(
        "import-netlist",
        help="read unit connector pinouts from a KiCad netlist",
        description="Create or update the box connectors of one unit from a KiCad netlist (the .net file the schematic editor exports, or kicad-cli sch export netlist; S-expression and XML both work). Pins get fixed signals; generation connects interfaces to the pin of the same name. See docs/KICAD.md.",
    )
    nn.add_argument("project", type=Path)
    nn.add_argument("netlist", type=Path)
    nn.add_argument(
        "--unit", required=True, help="the unit these connectors belong to, for example OBC1"
    )
    nn.add_argument(
        "--ref",
        action="append",
        default=[],
        help="reference of a connector in the netlist, for example J1 (repeat; default: every component starting with --prefix)",
    )
    nn.add_argument(
        "--prefix", default="J", help="reference prefix that marks connectors (default J)"
    )
    nn.add_argument(
        "--connector",
        action="append",
        default=[],
        metavar="REF=ID",
        help="connector ID for a reference, for example J1=OBC1-J01 (default: the symbol field HarnessConnector, else <unit>-<ref>)",
    )
    nn.add_argument(
        "--part",
        action="append",
        default=[],
        metavar="REF=PART",
        help="library part for a new connector (default: the symbol field HarnessPart, or the existing connector's part)",
    )
    nn.add_argument(
        "--signal-map",
        action="append",
        default=[],
        metavar="NAME=SIGNAL|FILE",
        help="translate a KiCad net name to an interface signal name (repeatable), or a CSV (net name, signal) or JSON object file of such pairs",
    )
    nn.add_argument(
        "--pin-function",
        action="store_true",
        help="use the pin names of the symbol instead of the net names as signals",
    )
    nn.add_argument("--dry-run", action="store_true")
    ll = sub.add_parser(
        "import-lengths",
        help="import routing segment lengths (CSV or XLSX: harness, segment, length)",
        description="Import segment lengths, for example exported from the mechanical CAD (KiCad users: see docs/IMPORTS.md).",
    )
    ll.add_argument("project", type=Path)
    ll.add_argument("file", type=Path)
    ll.add_argument(
        "--unit", choices=sorted(UNITS), default="mm", help="unit of the length column (default mm)"
    )
    ll.add_argument("--dry-run", action="store_true")


def _library_options(p: argparse.ArgumentParser) -> None:
    p.add_argument(
        "--library-name", dest="library_name", default=None, help="name of the parts library"
    )
    p.add_argument(
        "--library-version", dest="library_version", default=None, help="version of the parts data"
    )
    p.add_argument(
        "--library-source",
        dest="library_source",
        default=None,
        help="where the data comes from (default for import-parts: the file name and its SHA-256)",
    )  # noqa: E501
    p.add_argument(
        "--library-date",
        dest="library_date",
        default=None,
        metavar="YYYY-MM-DD",
        help="date of the data",
    )


def run(args: argparse.Namespace) -> int:
    try:
        project = load_project(args.project).project
        if args.command == "config":
            return _config(project, args)
        if args.command == "library":
            return _library(project, args)
        if project.read_only:
            print(
                "error: this project is read-only (saved by a newer tool version).", file=sys.stderr
            )
            return 2
        if args.command == "import-netlist":
            return _netlist(project, args)
        table, sheet = read_table_sheet(args.file)
        if sheet is not None:
            print(f"Reading sheet '{sheet}' (the first visible sheet of the workbook).")
        if args.command == "import-parts":
            return _parts(project, table, args)
        return _lengths(project, table, args)
    except (HarnessError, ImportError_) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


def _config(project, args: argparse.Namespace) -> int:  # type: ignore[no-untyped-def]
    if args.ampacity_csv is not None:
        table, problems = configcheck.plan_ampacity_import(read_table_raw(args.ampacity_csv))
        if problems:
            for p in problems:
                print(f"error: {p}", file=sys.stderr)
            print("Nothing was changed.", file=sys.stderr)
            return 1
        cfg = configcheck.with_value(project.config["derating"], "ampacity_a_by_awg", table)
        History(project).execute("Load ampacity table", [SetConfig(cfg)])
        invalid = [
            i for i in configcheck.validate(project) if i.object_id == "derating.ampacity_a_by_awg"
        ]
        if invalid:
            print(f"error: {invalid[0].message}", file=sys.stderr)
            print("Nothing was changed.", file=sys.stderr)
            return 1
        save_project(project, args.project)
        print(
            f'Loaded {len(table)} gauges into config/derating.json. Review it, then set "placeholder": false when the file is complete.'
        )
    if args.apply_profile is not None:
        try:
            plan = standard_profiles.plan_profile(project, args.apply_profile)
        except ValueError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        if plan.configs:
            History(project).execute(
                f"Apply profile {args.apply_profile}", [SetConfig(c) for c in plan.configs]
            )
            save_project(project, args.project)
        for s in plan.applied:
            print(f"set {s.file}.{s.key} = {s.value!r}  ({s.source}: {s.note})")
        for s, current in plan.kept:
            print(f"kept {s.file}.{s.key} = {current!r}; the profile says {s.value!r} ({s.source})")
        print(
            f"Profile {args.apply_profile}: {len(plan.applied)} value(s) set, {len(plan.kept)} kept. "
            "These values come from the supplied standard and still need an engineer's review; "
            'the files stay "placeholder": true until you set it to false.'
        )
    text, ok = configcheck.report(project)
    print(text)
    return 0 if ok else 1


def read_table_raw(path: Path) -> list[list[str]]:

    return read_table(path)  # one reader for every file: size limit, regular files only, delimiters


def _parts(project, table: list[list[str]], args: argparse.Namespace) -> int:  # type: ignore[no-untyped-def]
    if not table:
        print("error: the file is empty.", file=sys.stderr)
        return 2
    mapping = guess_mapping(table[0])
    if "id" not in mapping and "part_number" not in mapping:
        print("error: no column looks like a part ID or part number.", file=sys.stderr)
        return 2
    plan = plan_parts_import(
        project,
        table,
        mapping,
        approved=args.approved,
        pending=args.pending,
        rejected=args.rejected,
        default_category=args.category,
    )
    for r in plan.rows:
        print(
            f"row {r.row_number}: {'OK ' + r.action + ' ' + r.part_id if r.ok else 'ERROR ' + r.message}"
        )
    bad = [r for r in plan.rows if not r.ok]
    print(f"{plan.ok_count} part(s) ready, {len(bad)} row(s) with problems.")
    if args.dry_run or bad:
        print("Nothing was changed." if bad else "Dry run: nothing was changed.")
        return 1 if bad else 0
    source = args.library_source or _file_source(args.file)
    ops = [
        *plan.ops,
        *library_ops(
            project,
            name=args.library_name,
            version=args.library_version,
            source=source,
            date=args.library_date,
        ),
    ]
    History(project).execute("Import parts", ops)
    save_project(project, args.project)
    print(f"Imported {plan.ok_count} part(s). {describe_library(project)}.")
    return 0


def _file_source(path: Path) -> str:
    """The imported file's name and a short checksum, so the origin can be told later."""
    import hashlib

    digest = hashlib.sha256(path.read_bytes()).hexdigest()[:12]
    return f"{path.name} (sha256 {digest})"


def _library(project, args: argparse.Namespace) -> int:  # type: ignore[no-untyped-def]
    ops = library_ops(
        project,
        name=args.library_name,
        version=args.library_version,
        source=args.library_source,
        date=args.library_date,
    )
    if ops:
        History(project).execute("Record the parts library source", ops)
        save_project(project, args.project)
    print(describe_library(project) + ".")
    return 0


def _lengths(project, table: list[list[str]], args: argparse.Namespace) -> int:  # type: ignore[no-untyped-def]
    if len(table) < 2:
        print(
            "error: the file has no rows to import (headings and at least one row).",
            file=sys.stderr,
        )
        return 2
    plan = plan_length_import(project, table, scale=UNITS[args.unit])
    for r in plan.rows:
        print(f"row {r.row_number}: {'OK' if r.ok else 'ERROR ' + r.message}")
    bad = [r for r in plan.rows if not r.ok]
    print(f"{len(plan.rows) - len(bad)} length(s) ready, {len(bad)} row(s) with problems.")
    if plan.hint:
        print(plan.hint)
    if args.dry_run or bad:
        print("Nothing was changed." if bad else "Dry run: nothing was changed.")
        return 1 if bad else 0
    History(project).execute("Import segment lengths", plan.ops)
    save_project(project, args.project)
    print("Lengths imported. Generate harnesses again to update the wire lengths.")
    return 0


def _pairs(items: list[str], what: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for item in items:
        key, sep, value = item.partition("=")
        if not sep or not key.strip() or not value.strip():
            raise ImportError_(f"{what} '{item}' must look like REF=VALUE")
        out[key.strip()] = value.strip()
    return out


def _signal_map(items: list[str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for item in items:
        if "=" in item:
            key, _, value = item.partition("=")
            if not key.strip() or not value.strip():
                raise ImportError_(f"Signal map '{item}' must look like NAME=SIGNAL.")
            out[key.strip()] = value.strip()
        else:
            out.update(_signal_map_file(Path(item)))
    return out


def _signal_map_file(path: Path) -> dict[str, str]:
    import json

    try:
        if path.suffix.lower() == ".json":
            raw = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict) or not all(
                isinstance(k, str) and isinstance(v, str) for k, v in raw.items()
            ):
                raise ImportError_("The signal map must be a JSON object of text to text.")
            return dict(raw)
        rows = read_table_raw(path)
    except (OSError, ValueError, RecursionError) as exc:
        raise ImportError_(f"The signal map could not be read ({exc}).") from exc
    if rows and rows[0][0].strip().lower() in ("net", "name", "kicad", "from", "net name"):
        rows = rows[1:]
    return {
        r[0].strip(): r[1].strip() for r in rows if len(r) >= 2 and r[0].strip() and r[1].strip()
    }


def _netlist(project, args: argparse.Namespace) -> int:  # type: ignore[no-untyped-def]
    from harness_design_studio.core.kicad import plan_netlist_import, read_netlist

    plan = plan_netlist_import(
        project, read_netlist(args.netlist), args.unit, refs=args.ref or None, prefix=args.prefix,
        connector_ids=_pairs(args.connector, "--connector"), parts=_pairs(args.part, "--part"),
        signal_map=_signal_map(args.signal_map), use_pin_function=args.pin_function,
    )  # fmt: skip
    for r in plan.rows:
        print(
            f"{r.ref or '-'}: "
            + (
                f"OK {r.action} {r.connector_id} ({r.pins} signal pin(s))"
                if r.ok
                else f"ERROR {r.message}"
            )
        )
    for w in plan.warnings:
        print(f"warning: {w}")
    if plan.unmatched_signals:
        print(
            "Signals that match no interface type (map them with --signal-map, or ignore if they are not interfaces):"
        )
        for name in sorted(plan.unmatched_signals):
            print(f"  {name}: {', '.join(plan.unmatched_signals[name][:4])}")
    bad = [r for r in plan.rows if not r.ok]
    if args.dry_run or bad or not plan.ops:
        print(
            "Nothing was changed."
            if bad
            else "Dry run: nothing was changed."
            if args.dry_run
            else "Nothing to import."
        )
        return 1 if bad or not plan.ops else 0
    History(project).execute("Import connector pinouts from KiCad", plan.ops)
    save_project(project, args.project)
    print(
        f"Imported {plan.ok_count} connector(s). Generate harnesses again to connect interfaces to the fixed pins."
    )
    return 0
