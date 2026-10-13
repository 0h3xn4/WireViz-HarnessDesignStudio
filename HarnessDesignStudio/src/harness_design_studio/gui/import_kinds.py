"""What the import wizard can import, and how each kind is planned. No Qt in here.

Every kind reads a file and asks the planner the command line asks (`harness-design-studio import-parts`,
`import-lengths`, `import-netlist`, `config --ampacity-csv`, and the interface planner of the
existing import dialog); this module only turns their results into one shape the wizard shows:
rows with an exact reason each, the operations that apply them, and what stays pending. Nothing is
invented: a file format is whatever the planner reads, and the columns, words and units are the
ones the command line asks for.

    source = read_source("parts", path)
    options = default_options("parts", source)
    plan = plan_import(project, source, options)       # an `ImportPlanView`; the project is unchanged
    ctl.run(plan.label, plan.ops, message=...)         # one undo step, "Import 12 rows"
"""

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final

from harness_design_studio.core import configcheck, edit
from harness_design_studio.core.commands import History, Op, Put, SetConfig
from harness_design_studio.core.errors import HarnessError, TransactionError
from harness_design_studio.core.generate.lengths import plan_length_import
from harness_design_studio.core.imports import (
    FIELDS as INTERFACE_FIELDS,
)
from harness_design_studio.core.imports import (
    ImportError_,
    Table,
    plan_interface_import,
    read_table,
    read_table_sheet,
)
from harness_design_studio.core.imports import guess_mapping as guess_interface_mapping
from harness_design_studio.core.kicad import Netlist, plan_netlist_import, read_netlist
from harness_design_studio.core.library_import import (
    FIELDS as PART_FIELDS,
)
from harness_design_studio.core.library_import import (
    guess_mapping as guess_part_mapping,
)
from harness_design_studio.core.library_import import (
    library_ops,
    plan_parts_import,
)
from harness_design_studio.core.model import Project
from harness_design_studio.core.model.library import PART_CATEGORIES
from harness_design_studio.gui import strings

PREVIEW_ROWS: Final = 20  # rows of the live preview on the mapping page
LENGTH_UNITS: Final = {
    "mm": 0.001,
    "cm": 0.01,
    "m": 1.0,
}  # as `harness-design-studio import-lengths --unit`
AMPACITY_KEY: Final = ("derating", "ampacity_a_by_awg")


@dataclass(frozen=True)
class KindInfo:
    key: str
    title: str
    summary: str
    filters: str  # file chooser filter
    uses_table: bool = True


KINDS: Final[tuple[KindInfo, ...]] = (
    KindInfo(
        "interfaces",
        strings.IMP_KIND_INTERFACES,
        strings.IMP_KIND_INTERFACES_TIP,
        strings.IMP_FILTER_TABLES,
    ),  # fmt: skip
    KindInfo(
        "parts", strings.IMP_KIND_PARTS, strings.IMP_KIND_PARTS_TIP, strings.IMP_FILTER_TABLES
    ),  # fmt: skip
    KindInfo(
        "lengths", strings.IMP_KIND_LENGTHS, strings.IMP_KIND_LENGTHS_TIP, strings.IMP_FILTER_TABLES
    ),  # fmt: skip
    KindInfo(
        "values", strings.IMP_KIND_VALUES, strings.IMP_KIND_VALUES_TIP, strings.IMP_FILTER_TABLES
    ),  # fmt: skip
    KindInfo(
        "netlist",
        strings.IMP_KIND_NETLIST,
        strings.IMP_KIND_NETLIST_TIP,
        strings.IMP_FILTER_NETLIST,
        False,
    ),  # fmt: skip
)
KIND_BY_KEY: Final = {k.key: k for k in KINDS}

# the columns of the live preview, per kind
PREVIEW_COLUMNS: Final = {
    "interfaces": ("Row", "Interface", "Type", "From", "To", "Redundancy"),
    "parts": ("Row", "Part", "Category", "Part number", "Approval in the file"),
    "lengths": ("Row", "Harness", "Segment", "Length"),
    "values": ("Row", "Wire gauge (AWG)", "Ampacity (A)"),
    "netlist": ("Reference", "Connector", "Pins"),
}


# ---- reading the file ---------------------------------------------------------------------------


@dataclass
class Source:
    """A file that was read: a table (rows of text, the first is the header) or a netlist."""

    kind: str
    path: Path
    table: Table = field(default_factory=list)
    sheet: str | None = None
    netlist: Netlist | None = None

    @property
    def name(self) -> str:
        return self.path.name

    @property
    def rows(self) -> int:
        """Data rows of a table, components of a netlist."""
        if self.netlist is not None:
            return len(self.netlist.components)
        return max(0, len(self.table) - (0 if self.kind == "values" else 1))

    def library_source(self) -> str:
        """The file's name and a short checksum, so the origin of the parts can be told later (the
        same text `harness-design-studio import-parts` records)."""
        digest = hashlib.sha256(self.path.read_bytes()).hexdigest()[:12]
        return f"{self.path.name} (sha256 {digest})"


def read_source(kind: str, path: Path | str) -> Source:
    """Read the file for `kind`; raises `ImportError_` (or a `HarnessError`) with a sentence a
    person can act on."""
    p = Path(path)
    try:
        if kind == "netlist":
            return Source(kind, p, netlist=read_netlist(p))
        if kind == "values":
            return Source(kind, p, table=read_table(p))
        table, sheet = read_table_sheet(p)
        return Source(kind, p, table=table, sheet=sheet)
    except OSError as exc:
        raise ImportError_(f"The file could not be read ({exc.strerror}).") from exc


# ---- the choices ---------------------------------------------------------------------------------


@dataclass
class Options:
    """Everything the person can choose on the mapping page. Only the part for the kind is used."""

    mapping: dict[str, int] = field(default_factory=dict)  # interfaces and parts: field -> column
    approved: list[str] = field(default_factory=list)  # parts: what the approval column says
    pending: list[str] = field(default_factory=list)
    rejected: list[str] = field(default_factory=list)
    category: str = ""  # parts: for rows that have none
    length_unit: str = "mm"  # lengths
    unit_id: str = ""  # netlist: the unit the connectors belong to
    prefix: str = "J"
    refs: list[str] = field(default_factory=list)
    connector_ids: dict[str, str] = field(default_factory=dict)
    parts: dict[str, str] = field(default_factory=dict)
    signal_map: dict[str, str] = field(default_factory=dict)
    pin_function: bool = False


def mapping_fields(kind: str) -> tuple[tuple[str, str], ...]:
    """(key, label) of the fields a table kind lets you match to columns."""
    if kind == "interfaces":
        return INTERFACE_FIELDS
    if kind == "parts":
        return PART_FIELDS
    return ()


def default_options(kind: str, source: Source) -> Options:
    """The choices the command line would make: columns guessed from the headings."""
    options = Options()
    if source.table and kind == "interfaces":
        options.mapping = guess_interface_mapping(source.table[0])
    elif source.table and kind == "parts":
        options.mapping = guess_part_mapping(source.table[0])
    return options


def parse_words(text: str) -> list[str]:
    """ "Approved, EPPL; Released" -> ["Approved", "EPPL", "Released"]."""
    return [w.strip() for w in re.split(r"[,;\n]", text) if w.strip()]


def parse_pairs(text: str, what: str) -> dict[str, str]:
    """ "J1=OBC-J01" lines (or comma-separated) -> {"J1": "OBC-J01"}; a malformed entry raises
    `ImportError_` naming it."""
    out: dict[str, str] = {}
    for item in parse_words(text):
        key, sep, value = item.partition("=")
        if not sep or not key.strip() or not value.strip():
            raise ImportError_(strings.IMP_BAD_PAIR.format(what, item))
        out[key.strip()] = value.strip()
    return out


# ---- one shape for every plan -----------------------------------------------------------------


@dataclass(frozen=True)
class PlanRow:
    number: str  # the row of the file, or the reference of a connector
    item: str  # what the row is about ("IF-010", "J1 -> OBC1-J1")
    state: str  # "pass" | "fail" | "warning" (a key of gui.states.STATES)
    result: str  # "Will add", "Skipped" ...
    reason: str  # why, exactly as the planner says it ("" when fine)

    @property
    def ok(self) -> bool:
        return self.state != "fail"


@dataclass
class ImportPlanView:
    kind: str
    rows: list[PlanRow] = field(default_factory=list)
    ops: list[Op] = field(default_factory=list)
    preview: list[list[str]] = field(default_factory=list)  # cells per plan row (`PREVIEW_COLUMNS`)
    pending: list[tuple[str, str]] = field(default_factory=list)  # (item, what stays open)
    notes: list[str] = field(default_factory=list)  # hints that apply to the whole file
    problem: str = ""  # the whole import cannot go ahead (nothing to import, refused ...)
    partial: bool = False  # True: rows with a problem are skipped and the others imported
    next_step: str = ""
    total_rows: int = 0

    @property
    def ok_count(self) -> int:
        return sum(r.state == "pass" for r in self.rows)

    @property
    def bad_count(self) -> int:
        return sum(r.state == "fail" for r in self.rows)

    @property
    def importable(self) -> bool:
        """Something can be imported and nothing stops it."""
        if self.problem or not self.ok_count or not self.ops:
            return False
        return self.partial or self.bad_count == 0

    @property
    def label(self) -> str:
        """The name of the undo step: "Import 12 rows"."""
        n = self.ok_count
        return strings.IMP_LABEL.format(n, "" if n == 1 else "s")


_HINTS = (
    (re.compile(r"use --part (\S+)=PART"), lambda m: strings.IMP_HINT_PART.format(m.group(1))),
    (re.compile(r"use --connector (\S+)=ID"), lambda m: strings.IMP_HINT_ID.format(m.group(1))),
    (re.compile(r"Name the connectors with --ref"), lambda m: strings.IMP_HINT_REF),
    (re.compile(r"map it with --signal-map"), lambda m: strings.IMP_HINT_MAP),
)


def plain(message: str) -> str:
    """A planner message with the command-line option names turned into the wizard's own words
    ("use --part J1=PART" -> "enter J1=PART in “Part for each connector”")."""
    for pattern, repl in _HINTS:
        message = pattern.sub(repl, message)
    return message


def _blocked(project: Project, label: str, ops: list[Op]) -> str:
    """Would the change be refused (a released harness, a locked configuration, an inconsistent
    result)? Asked on a copy, as `--dry-run` does; "" when it would go through."""
    try:
        History(edit.clone_with(project, [])).execute(label, ops)
    except TransactionError as exc:
        return f"{exc} {' '.join(exc.problems[:2])}".strip()
    except HarnessError as exc:
        return str(exc)
    return ""


def plan_import(project: Project, source: Source, options: Options) -> ImportPlanView:
    """Plan the import. Never changes the project; never raises for a problem with the data (it
    is in the plan)."""
    try:
        plan = _PLANNERS[source.kind](project, source, options)
    except (HarnessError, ValueError) as exc:  # for example two approval columns
        return ImportPlanView(source.kind, problem=plain(str(exc)))
    if plan.ops and not plan.problem and (plan.partial or plan.bad_count == 0):
        refused = _blocked(project, plan.label, plan.ops)
        if refused:
            plan.problem = strings.IMP_BLOCKED.format(refused)
    return plan


# ---- interfaces --------------------------------------------------------------------------------


def _plan_interfaces(project: Project, source: Source, options: Options) -> ImportPlanView:
    view = ImportPlanView("interfaces", partial=True, next_step=strings.IMP_NEXT_INTERFACES)
    if len(source.table) < 2:
        view.problem = strings.IMP_EMPTY
        return view
    plan = plan_interface_import(project, source.table, options.mapping)
    view.ops = plan.ops
    view.total_rows = len(plan.rows)
    for r in plan.rows:
        iid = r.values[0] or "(no ID)"
        view.rows.append(
            PlanRow(
                str(r.row_number), iid, "pass" if r.ok else "fail",
                strings.IMP_WILL_ADD if r.ok else strings.IMP_SKIPPED, r.message,
            )
        )  # fmt: skip
        view.preview.append([str(r.row_number), *r.values])
        if r.ok:
            view.pending.append((iid, strings.IMP_P_AUTO))
    return view


# ---- approved parts ---------------------------------------------------------------------------


def _plan_parts(project: Project, source: Source, options: Options) -> ImportPlanView:
    view = ImportPlanView("parts", next_step=strings.IMP_NEXT_PARTS)
    table, mapping = source.table, options.mapping
    if len(table) < 2:
        view.problem = strings.IMP_EMPTY
        return view
    if "id" not in mapping and "part_number" not in mapping:
        view.problem = strings.IMP_NEED_ID_COLUMN
        return view
    if options.category and options.category not in PART_CATEGORIES:
        view.problem = f"Category '{options.category}' is not one of {', '.join(PART_CATEGORIES)}"
        return view
    plan = plan_parts_import(
        project, table, mapping, approved=options.approved, pending=options.pending,
        rejected=options.rejected, default_category=options.category or None,
    )  # fmt: skip
    view.total_rows = len(plan.rows)
    wanted = ("id", "category", "part_number", "approval")

    def cell(row: list[str], key: str) -> str:
        i = mapping.get(key)
        return row[i].strip() if i is not None and i < len(row) else ""

    pending_ids = {
        str(getattr(op.obj, "id", ""))
        for op in plan.ops
        if isinstance(op, Put) and getattr(op.obj, "approval", "") == "pending"
    }
    for r in plan.rows:
        row = table[r.row_number - 1]
        name = r.part_id or "(no ID)"
        result = (strings.IMP_WILL_UPDATE if r.action == "updated" else strings.IMP_WILL_ADD) if r.ok else strings.IMP_SKIPPED  # fmt: skip
        view.rows.append(PlanRow(str(r.row_number), name, "pass" if r.ok else "fail", result, r.message))  # fmt: skip
        view.preview.append([str(r.row_number), cell(row, wanted[0]) or cell(row, "part_number"), *(cell(row, k) for k in wanted[1:])])  # fmt: skip
        if r.ok and r.part_id in pending_ids:
            view.pending.append((name, strings.IMP_P_PART_PENDING))
    source_text = source.library_source()
    view.ops = [*plan.ops, *library_ops(project, source=source_text)]
    view.notes.append(strings.IMP_PARTS_SOURCE.format(source_text))
    return view


# ---- segment lengths --------------------------------------------------------------------------


def _plan_lengths(project: Project, source: Source, options: Options) -> ImportPlanView:
    view = ImportPlanView("lengths", next_step=strings.IMP_NEXT_LENGTHS)
    if len(source.table) < 2:
        view.problem = strings.IMP_EMPTY
        return view
    plan = plan_length_import(project, source.table, scale=LENGTH_UNITS[options.length_unit])
    view.ops = plan.ops
    view.total_rows = len(plan.rows)
    for r in plan.rows:
        hid, sid, text = r.values
        item = f"{hid} / {sid}" if hid or sid else "(empty row)"
        view.rows.append(
            PlanRow(
                str(r.row_number),
                item,
                "pass" if r.ok else "fail",
                strings.IMP_WILL_SET if r.ok else strings.IMP_SKIPPED,
                r.message,
            )  # fmt: skip
        )
        view.preview.append([str(r.row_number), hid, sid, f"{text} {options.length_unit}" if text else ""])  # fmt: skip
    if plan.hint:
        view.notes.append(plan.hint)
    return view


# ---- engineering values: the ampacity table ---------------------------------------------------------


_ROW_PROBLEM = re.compile(r"Row (\d+): (.*)")


def _plan_values(project: Project, source: Source, options: Options) -> ImportPlanView:
    view = ImportPlanView("values", next_step=strings.IMP_NEXT_VALUES)
    file, key = AMPACITY_KEY
    if file not in project.config:
        view.problem = strings.IMP_NO_DERATING
        return view
    table, problems = configcheck.plan_ampacity_import(source.table)
    by_row: dict[int, str] = {}
    general: list[str] = []
    for text in problems:
        m = _ROW_PROBLEM.fullmatch(text)
        if m:
            by_row.setdefault(int(m.group(1)), m.group(2))
        else:
            general.append(text)
    view.total_rows = len(source.table)
    for n, row in enumerate(source.table, start=1):
        first = row[0].strip() if row else ""
        if n == 1 and not first.lstrip("-").isdigit() and n not in by_row:
            continue  # the heading row
        bad = by_row.get(n)
        gauge = first
        amps = row[1].strip() if len(row) > 1 else ""
        view.rows.append(
            PlanRow(str(n), f"AWG {gauge}" if gauge else "(empty row)", "fail" if bad else "pass",
                    strings.IMP_SKIPPED if bad else strings.IMP_WILL_SET, bad or ""),
        )  # fmt: skip
        view.preview.append([str(n), gauge, amps])
    if general and not view.rows:
        view.problem = general[0]
    elif general:
        view.notes.extend(general)
    if table and not problems:
        cfg = configcheck.with_value(project.config[file], key, table)
        view.ops = [SetConfig(cfg)]
        old = project.config[file].values.get(key)
        if old == table:
            view.problem = strings.IMP_VALUES_SAME
            view.ops = []
            return view
        if isinstance(old, dict) and old:
            view.notes.append(f"The table with {len(old)} gauges in the derating values is replaced by this one with {len(table)}.")  # fmt: skip
        if project.config[file].placeholder:
            view.pending.append((f"config/{file}.json", strings.IMP_P_CONFIG))
        clone = edit.clone_with(
            project, view.ops
        )  # the same check the command line runs afterwards
        invalid = [i for i in configcheck.validate(clone) if i.object_id == f"{file}.{key}"]
        if invalid:
            view.problem = invalid[0].message
            view.ops = []
    return view


# ---- a KiCad netlist ----------------------------------------------------------------------------


def _plan_netlist(project: Project, source: Source, options: Options) -> ImportPlanView:
    view = ImportPlanView("netlist", next_step=strings.IMP_NEXT_NETLIST)
    if not options.unit_id:
        view.problem = strings.IMP_NO_UNIT
        return view
    if source.netlist is None:
        view.problem = strings.IMP_EMPTY
        return view
    plan = plan_netlist_import(
        project, source.netlist, options.unit_id, refs=options.refs or None, prefix=options.prefix,
        connector_ids=options.connector_ids, parts=options.parts, signal_map=options.signal_map,
        use_pin_function=options.pin_function,
    )  # fmt: skip
    view.ops = plan.ops
    view.total_rows = len(plan.rows)
    for r in plan.rows:
        item = f"{r.ref or '-'} → {r.connector_id}" if r.connector_id else (r.ref or "-")
        result = (strings.IMP_WILL_UPDATE if r.action == "updated" else strings.IMP_WILL_ADD) if r.ok else strings.IMP_SKIPPED  # fmt: skip
        view.rows.append(PlanRow(r.ref or "-", item, "pass" if r.ok else "fail", result, plain(r.message)))  # fmt: skip
        view.preview.append([r.ref or "-", r.connector_id, f"{r.pins} signal pin(s)" if r.ok else ""])  # fmt: skip
    for w in plan.warnings:
        view.rows.append(PlanRow("", strings.IMP_WARNING, "warning", strings.IMP_WARNING, plain(w)))
    for name, where in sorted(plan.unmatched_signals.items()):
        view.pending.append((name, strings.IMP_P_SIGNAL.format(", ".join(where[:3]))))
    if not plan.ops and not view.problem and not any(r.state == "fail" for r in view.rows):
        view.problem = strings.IMP_EMPTY
    return view


_PLANNERS = {
    "interfaces": _plan_interfaces,
    "parts": _plan_parts,
    "lengths": _plan_lengths,
    "values": _plan_values,
    "netlist": _plan_netlist,
}
