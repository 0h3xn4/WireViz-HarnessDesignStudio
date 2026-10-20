"""Commands that bring outside data into a project (config, import-parts, import-lengths,
import-netlist, import-pinout) and one that writes a device's pinout out (export-pinout)."""

import argparse
import sys
from pathlib import Path

from harness_design_studio.cli import blocked_text
from harness_design_studio.core import configcheck, edit, standard_profiles
from harness_design_studio.core.commands import History, Op, SetConfig
from harness_design_studio.core.errors import HarnessError, TransactionError
from harness_design_studio.core.generate.lengths import plan_length_import
from harness_design_studio.core.generation_status import generation_status
from harness_design_studio.core.imports import ImportError_, read_table, read_table_sheet
from harness_design_studio.core.io.loader import load_project
from harness_design_studio.core.io.saver import save_project
from harness_design_studio.core.library_import import (
    describe_library,
    guess_mapping,
    library_ops,
    plan_parts_import,
)

COMMANDS = (
    "config", "library", "import-parts", "import-lengths", "import-netlist", "import-pinout",
    "export-pinout", "export-devices", "import-devices",
)  # fmt: skip
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
        help="import an approved-parts list (CSV, TSV, JSON or XLSX; also an InvenTree export)",
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
        description="Create or update the box connectors of one unit from a KiCad netlist (the .net file the schematic editor exports, or kicad-cli sch export netlist; S-expression and XML both work). Pins get fixed signals; generation connects interfaces to the pin of the same name. The user guide has a chapter on it.",
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
    pn = sub.add_parser(
        "import-pinout",
        help="import a device's pinout from a spreadsheet (CSV or XLSX)",
        description="Create or update the box connectors of one unit from a table: one row per pin with the connector, the pin, the signal, whether the device fixes it, a contact size and a termination. Columns are matched by their headings (Connector, Pin, Signal, Mode or Fixed, Contact size, Termination, Part, Gender); columns the project cannot store, such as a description or a voltage, are named in a warning and left out. A row with a problem stops the whole import; nothing is changed then. A new connector needs a library part (a Part column, --part J1=PART or --default-part). The user guide has a chapter on it.",
    )
    pn.add_argument("project", type=Path)
    pn.add_argument("file", type=Path)
    pn.add_argument(
        "--unit", required=True, help="the unit the connectors belong to, for example GYRO1"
    )
    pn.add_argument(
        "--new-device",
        default=None,
        metavar="NAME",
        help="make the unit as a new device with this name when it does not exist",
    )
    pn.add_argument(
        "--subsystem", default=None, help="subsystem of a new device (default: the most used one)"
    )
    pn.add_argument(
        "--part",
        action="append",
        default=[],
        metavar="REF=PART",
        help="library part for a new connector, for example J1=MY-HD-9-F (repeat)",
    )
    pn.add_argument(
        "--default-part", default=None, help="library part for new connectors that have none"
    )
    pn.add_argument(
        "--gender",
        choices=["male", "female"],
        default=None,
        help="gender of new connectors (default: the part's)",
    )
    pn.add_argument(
        "--connector",
        default=None,
        help="connector for rows of a table that has no Connector column (default J01)",
    )
    pn.add_argument(
        "--column",
        action="append",
        default=[],
        metavar="FIELD=HEADING",
        help="use this column for a field when the headings are not recognised, for example pin=Contact (repeat)",
    )
    pn.add_argument(
        "--replace",
        action="store_true",
        help="drop the pins of an existing connector that the table does not name (default: keep them)",
    )
    pn.add_argument("--dry-run", action="store_true", help="show the preview only")
    xp = sub.add_parser(
        "export-pinout",
        help="write one device's pinout as CSV or XLSX",
        description="Write the rows of system/box_pinouts.csv that belong to one unit (connector, pin, signal, interface, wires, spare) to a file, or to the screen as CSV. The format follows the file name (.csv or .xlsx). The rows are the ones export writes, so the file compares with an interface control document.",
    )
    xp.add_argument("project", type=Path)
    xp.add_argument("--unit", required=True, help="the unit to write, for example GYRO1")
    xp.add_argument(
        "--output",
        "-o",
        type=Path,
        default=None,
        help="the file to write (default: CSV on the screen)",
    )
    xd = sub.add_parser(
        "export-devices",
        help="save devices with their connectors and pinouts to a device library file",
        description="Write one or more units, their box connectors with every pin (signal, function, contact size, termination), and the parts and interface types they name to a device library file (JSON). A file that exists is added to: a device with the same ID is replaced, the others stay. What generation allocated in this project does not travel.",
    )
    xd.add_argument("project", type=Path)
    xd.add_argument("file", type=Path, help="the device library file to write or add to")
    xd.add_argument(
        "--unit",
        action="append",
        required=True,
        help="a unit to save, for example GYRO1 (repeat for more)",
    )
    idv = sub.add_parser(
        "import-devices",
        help="add devices from a device library file to the project",
        description="Add the devices of a device library file with their connectors, pinouts, parts and interface types. A device never replaces one of the project: a taken ID gets the next free one (GYRO1 becomes GYRO1-2). Parts and interface types the project already has are kept as they are. Use --list to see what the file holds.",
    )
    idv.add_argument("project", type=Path)
    idv.add_argument("file", type=Path)
    idv.add_argument(
        "--unit",
        action="append",
        default=[],
        help="a device of the file to add (repeat; default: all)",
    )
    idv.add_argument("--list", action="store_true", help="list the devices of the file and stop")
    idv.add_argument("--dry-run", action="store_true", help="show the preview only")
    ll = sub.add_parser(
        "import-lengths",
        help="import routing segment lengths (CSV or XLSX: harness, segment, length, in this order)",
        description="Import segment lengths, for example exported from the mechanical CAD. The columns are read by position (harness, segment, length), not by their headings. Numbers are written with a point (12.5) or, in a quoted cell, a decimal comma (12,5).",
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
        if args.command == "export-pinout":
            return _export_pinout(project, args)
        if args.command == "export-devices":
            return _export_devices(project, args)
        if project.read_only:
            print(
                "error: this project is read-only (saved by a newer tool version).", file=sys.stderr
            )
            return 2
        if args.command == "import-netlist":
            return _netlist(project, args)
        if args.command == "import-devices":
            return _import_devices(project, args)
        if args.command == "import-pinout":
            from harness_design_studio.core.pinout_import import read_pinout_table

            table, sheet = read_pinout_table(args.file)
        else:
            table, sheet = read_table_sheet(args.file)
        if sheet is not None:
            print(f"Reading sheet '{sheet}' (the first visible sheet of the workbook).")
        if args.command == "import-parts":
            return _parts(project, table, args)
        if args.command == "import-pinout":
            return _pinout(project, table, args)
        return _lengths(project, table, args)
    except TransactionError as exc:  # blocked (for example by a release), not misused
        print(blocked_text(exc), file=sys.stderr)
        return 1
    except (HarnessError, ImportError_) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


def _would_be_blocked(project, label: str, ops: list[Op]) -> bool:  # type: ignore[no-untyped-def]
    """Dry runs ask the same question as the real run: would the change be refused (a released
    harness, a release record, an inconsistent result)? It is tried on a copy and then dropped."""
    try:
        History(edit.clone_with(project, [])).execute(label, ops)
    except TransactionError as exc:
        print(blocked_text(exc), file=sys.stderr)
        print("Dry run: this import would be blocked. Nothing was changed.")
        return True
    return False


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
        was_current = generation_status(project) == "current"
        if plan.configs:
            History(project).execute(
                f"Apply profile {args.apply_profile}", [SetConfig(c) for c in plan.configs]
            )
            save_project(project, args.project)
        for s in plan.applied:
            print(f"set {s.file}.{s.key} = {s.value!r}  ({s.source}: {s.note})")
        for s, current in plan.kept:
            print(f"kept {s.file}.{s.key} = {current!r}; the profile says {s.value!r} ({s.source})")
        if was_current and generation_status(project) == "stale":
            print(
                "The profile changes values the generator reads, so the harness plans are now "
                "out of date. Run `harness-design-studio generate` again, then export again."
            )
        marked = [f"config/{n}.json" for n in project.placeholder_configs()]
        print(
            f"Profile {args.apply_profile}: {len(plan.applied)} value(s) set, {len(plan.kept)} kept. "
            "These values come from the supplied standard and still need an engineer's review."
        )
        print(
            f'Files marked "placeholder": true now: {", ".join(marked)}. Set it to false in a '
            "file when its values have been reviewed."
            if marked
            else 'No configuration file is marked "placeholder": true.'
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
    if bad:
        print("Nothing was changed.")
        return 1
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
    if args.dry_run:
        if _would_be_blocked(project, "Import parts", ops):
            return 1
        print("Dry run: nothing was changed.")
        return 0
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
    if bad:
        print("Nothing was changed.")
        return 1
    if args.dry_run:
        if _would_be_blocked(project, "Import segment lengths", plan.ops):
            return 1
        print("Dry run: nothing was changed.")
        return 0
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
    if (
        args.dry_run
        and not bad
        and plan.ops
        and _would_be_blocked(project, "Import connector pinouts from KiCad", plan.ops)
    ):
        return 1
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


def _pinout(project, table: list[list[str]], args: argparse.Namespace) -> int:  # type: ignore[no-untyped-def]
    from harness_design_studio.core.pinout_import import FIELDS, guess_mapping, plan_pinout_import

    mapping = guess_mapping(table[0]) if table else {}
    labels = {key for key, _ in FIELDS}
    for key, heading in _pairs(args.column, "--column").items():
        if key not in labels:
            raise ImportError_(f"--column: '{key}' is not a field ({', '.join(sorted(labels))}).")
        found = [i for i, h in enumerate(table[0]) if h.strip().casefold() == heading.casefold()]
        if not found:
            raise ImportError_(f"--column: the file has no column headed '{heading}'.")
        mapping[key] = found[0]
    plan = plan_pinout_import(
        project, table, mapping, unit_id=args.unit, new_unit_name=args.new_device,
        subsystem=args.subsystem, parts=_pairs(args.part, "--part"), default_part=args.default_part,
        gender=args.gender, connector=args.connector, replace=args.replace,
    )  # fmt: skip
    for r in plan.rows:
        if not r.ok:
            print(f"row {r.row_number}: ERROR {r.message}")
    for cid in plan.connectors:
        verb = "added" if cid in plan.added else "updated"
        n = sum(1 for r in plan.rows if r.ok and r.connector == cid)
        print(f"{cid}: OK {verb} ({n} pin(s))")
    for w in plan.warnings:
        print(f"warning: {w}")
    if plan.unmatched_signals:
        print(
            "Signals that match no interface type (nothing can connect to them until a type has them):"
        )
        for name in sorted(plan.unmatched_signals):
            print(f"  {name}: {', '.join(plan.unmatched_signals[name][:4])}")
    if plan.bad_count:
        print("Nothing was changed.")
        return 1
    if not plan.ops:
        print("Nothing to import.")
        return 1
    if args.dry_run:
        if _would_be_blocked(project, plan.label, plan.ops):
            return 1
        print("Dry run: nothing was changed.")
        return 0
    History(project).execute(plan.label, plan.ops)
    save_project(project, args.project)
    print(
        f"Imported {len(plan.connectors)} connector(s), {plan.pins} pin(s). "
        "Generate harnesses again to connect interfaces to the pins."
    )
    return 0


def _export_devices(project, args: argparse.Namespace) -> int:  # type: ignore[no-untyped-def]
    from harness_design_studio.core import device_library as dl

    data = dl.export_devices(project, args.unit)
    existing = dl.read_library(args.file) if args.file.exists() else None
    dl.write_library(args.file, dl.merge_library(existing, data))
    n = sum(len(d["connectors"]) for d in data["devices"])
    print(f"Saved {len(args.unit)} device(s) ({n} connector(s)) to {args.file}.")
    return 0


def _import_devices(project, args: argparse.Namespace) -> int:  # type: ignore[no-untyped-def]
    from harness_design_studio.core import device_library as dl

    data = dl.read_library(args.file)
    if args.list:
        for uid, name in dl.device_names(data):
            print(f"{uid}: {name}")
        return 0
    plan = dl.plan_device_import(project, data, args.unit or None)
    for r in plan.rows:
        print(
            f"{r.unit_id}: "
            + (
                f"OK as {r.new_id} ({r.connectors} connector(s), {r.pins} pin(s))"
                if r.ok
                else f"ERROR {r.message}"
            )
        )
    for note in plan.notes:
        print(f"note: {note}")
    bad = [r for r in plan.rows if not r.ok]
    if args.dry_run and not bad and plan.ops and _would_be_blocked(project, "Add devices from a library file", plan.ops):  # fmt: skip
        return 1
    if args.dry_run or bad or not plan.ops:
        print(
            "Nothing was changed."
            if bad
            else "Dry run: nothing was changed."
            if args.dry_run
            else "Nothing to import."
        )
        return 1 if bad or not plan.ops else 0
    History(project).execute("Add devices from a library file", plan.ops)
    save_project(project, args.project)
    print(f"Added {plan.ok_count} device(s). Generate harnesses again to connect interfaces to them.")  # fmt: skip
    return 0


def _export_pinout(project, args: argparse.Namespace) -> int:  # type: ignore[no-untyped-def]
    from harness_design_studio.core import devices
    from harness_design_studio.core.outputs import exports
    from harness_design_studio.core.outputs.stamp import csv_bytes, stamp_of

    table = devices.pinout_table(project, args.unit)
    if len(table) < 2:
        print(f"error: unit '{args.unit}' has no connectors to write.", file=sys.stderr)
        return 1
    stamp = stamp_of(project)
    if args.output is None:
        sys.stdout.write(csv_bytes(table, stamp).decode("utf-8"))
        return 0
    if args.output.suffix.lower() == ".xlsx":
        data = exports.xlsx_bytes({"Pinout": table}, stamp)
    else:
        data = csv_bytes(table, stamp)
    try:
        args.output.write_bytes(data)
    except OSError as exc:
        print(f"error: the file could not be written ({exc.strerror}).", file=sys.stderr)
        return 2
    print(f"Wrote {args.output} ({len(table) - 1} pin row(s) of {args.unit}).")
    return 0
