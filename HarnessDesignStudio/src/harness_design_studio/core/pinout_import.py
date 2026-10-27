"""Import a device's pinout from a spreadsheet (CSV or XLSX) as a plan: nothing changes until the
person confirms. One row of the sheet is one pin: the connector it belongs to, its name or number,
the signal on it, whether the device fixes it, a contact size, a termination, a function (free text;
a sheet with only a Function column and no Signal column reads it as the signal, as before) and the
contact part the cable side uses (a part of category contact; the heading `Cable contact`, or
`Contact` next to a Pin heading) and a direction (`Direction`: in, out or bidirectional; empty
leaves it unset, 1.9.0).

The tool knows no program's table format: columns are matched by their headings (with common
aliases), the way the parts import does. Columns it cannot store (remarks,
a voltage) are named in a warning and left out; the file format has no field for them.
Every row gets a result with its exact reason, a sheet with a bad row is not imported at all, and
what is imported is one `History` step ("Import pinout (2 connectors, 36 pins)").
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from . import devices, edit
from .commands import Op
from .edit import EditError
from .errors import HarnessError
from .imports import MAX_BYTES, ImportError_, parse_csv, read_table_sheet
from .model import Project

Table = list[list[str]]

FIELDS: tuple[tuple[str, str], ...] = (
    ("connector", "Connector"),
    ("pin", "Pin"),
    ("signal", "Signal"),
    ("mode", "Mode"),
    ("contact_size", "Contact size"),
    ("termination", "Termination"),
    ("function", "Function"),
    ("contact_part", "Cable contact"),
    ("direction", "Direction"),
    ("part", "Part"),
    ("gender", "Gender"),
)
_ALIASES = {
    "connector": ("connector", "conn", "connectorid", "connectorname", "ref", "reference"),
    "pin": ("pin", "pinid", "pinnumber", "pinno", "pinname", "contact", "number"),
    "signal": ("signal", "signalname", "net", "netname", "function"),
    "mode": ("mode", "allocation", "fixed"),
    "contact_size": ("contactsize", "size", "gauge", "contactgauge"),
    "termination": ("termination", "term", "terminationtype"),
    "function": (
        "function",
        "pinfunction",
        "functiondescription",
    ),  # "function" alone means the signal
    # "contact" alone is the pin when the sheet has no other pin heading (as it always was)
    "contact_part": ("cablecontact", "contactpart", "cablecontactpart", "contact"),
    "direction": ("direction", "pindirection", "dir", "iomode"),
    "part": ("part", "partid", "partnumber", "connectorpart"),
    "gender": ("gender", "sex"),
}
# headings the file format has no field for: named in a warning, never written
_UNSTORED = frozenset(
    {
        "description", "remarks", "remark", "notes", "note", "comment",
        "comments", "voltage", "current", "class",
    }
)  # fmt: skip
_YES = frozenset({"yes", "y", "true", "x", "1", "fixed"})
_GENDER_WORDS = {
    "male": "male", "m": "male", "plug": "male", "pin": "male", "pins": "male",
    "female": "female", "f": "female", "socket": "female", "receptacle": "female",
}  # fmt: skip


def read_pinout_table(path: Path | str) -> tuple[Table, str | None]:
    """Read a pinout sheet. A CSV file written by this tool starts with a comment line (`# ...`,
    docs/OUTPUTS.md); it is skipped. In a workbook written by this tool the first sheet is the
    "About" sheet; it is passed over, so what `export-pinout` writes can be read back."""
    p = Path(path)
    if p.suffix.lower() in (".csv", ".tsv"):
        try:
            raw = p.read_bytes()[: MAX_BYTES + 1]
            text = raw.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise ImportError_(
                "The file is not UTF-8 text. Save it as CSV UTF-8 and try again."
            ) from exc
        except OSError as exc:
            raise ImportError_(f"The file could not be read ({exc.strerror}).") from exc
        if text.startswith("# "):
            text = text.partition("\n")[2]
        return parse_csv(text), None
    return read_table_sheet(p, skip_sheets=("About",))


def _norm(text: str) -> str:
    return "".join(ch for ch in text.lower() if ch.isalnum())


def guess_mapping(header: list[str]) -> dict[str, int]:
    """Which column is which field, by heading (the first column that matches wins; a column is
    used once)."""
    norm = [_norm(h) for h in header]
    out: dict[str, int] = {}
    used: set[int] = set()
    for key, _label in FIELDS:
        for alias in _ALIASES[key]:
            hit = next((i for i, h in enumerate(norm) if h == alias and i not in used), None)
            if hit is not None:
                out[key] = hit
                used.add(hit)
                break
    return out


def unstored_columns(header: list[str], mapping: dict[str, int]) -> list[str]:
    """Headings of columns that carry something the project file cannot hold."""
    mapped = set(mapping.values())
    return [h for i, h in enumerate(header) if i not in mapped and _norm(h) in _UNSTORED]


@dataclass
class PinoutRow:
    row_number: int
    ok: bool
    message: str
    connector: str = ""  # the connector ID the row goes to
    pin: str = ""


@dataclass
class PinoutPlan:
    rows: list[PinoutRow] = field(default_factory=list)
    ops: list[Op] = field(default_factory=list)
    connectors: list[str] = field(default_factory=list)  # connector IDs that are added or changed
    added: list[str] = field(default_factory=list)  # ... of which new
    unchanged: list[str] = field(default_factory=list)  # connectors the table leaves as they are
    pins: int = 0
    unmatched_signals: dict[str, list[str]] = field(default_factory=dict)  # signal -> "J01.A1"
    warnings: list[str] = field(default_factory=list)
    unit_id: str = ""
    new_unit: bool = False

    @property
    def ok_count(self) -> int:
        return sum(r.ok for r in self.rows)

    @property
    def bad_count(self) -> int:
        return sum(not r.ok for r in self.rows)

    @property
    def importable(self) -> bool:
        return bool(self.ops) and self.bad_count == 0

    @property
    def label(self) -> str:
        n, p = len(self.connectors), self.pins
        return (
            f"Import pinout ({n} connector{'s' if n != 1 else ''}, {p} pin{'s' if p != 1 else ''})"
        )


def plan_pinout_import(
    project: Project,
    table: Table,
    mapping: dict[str, int],
    *,
    unit_id: str,
    new_unit_name: str | None = None,
    subsystem: str | None = None,
    parts: dict[str, str] | None = None,
    default_part: str | None = None,
    gender: str | None = None,
    connector: str | None = None,
    replace: bool = False,
) -> PinoutPlan:
    """One result per data row of `table` (the first row is the header). `unit_id` is an existing
    unit, or a new device when `new_unit_name` is given. `parts` maps a connector as the sheet
    names it (`J1`) to a library part for a connector that does not exist yet; `default_part` is
    used for the others; a `Part` column of the sheet does the same per row. Without a Connector
    column every row goes to `connector` (default `J01`). With `replace` the pins the sheet does
    not name are dropped from a connector that already exists. Nothing is invented: a missing part
    or a bad value is a refused row, never a guess."""
    plan = PinoutPlan(unit_id=unit_id)
    if "pin" not in mapping:
        raise ImportError_("The file needs a Pin column (a heading such as Pin or Pin number).")
    header = table[0] if table else []
    plan.warnings += [
        f"Column '{h}' is not imported: a pin has no field for it."
        for h in unstored_columns(header, mapping)
    ]
    work = edit.clone_with(project, [])  # the plan is built step by step on a copy
    if unit_id not in work.units:
        if not new_unit_name:
            raise ImportError_(
                f"Device '{unit_id}' does not exist. Name the new device to create it."
            )
        unit_ops, _ = devices.ops_add_device(
            work, unit_id=unit_id, name=new_unit_name, subsystem=subsystem
        )
        plan.ops += unit_ops
        work = edit.clone_with(work, unit_ops)
        plan.new_unit = True
    parts = parts or {}
    by_connector: dict[str, list[tuple[int, dict[str, str]]]] = {}
    names: dict[str, str] = {}  # casefolded connector name -> the name as first written
    order: list[str] = []
    fixed_column = "mode" in mapping and _norm(header[mapping["mode"]]) == "fixed"

    for n, row in enumerate(table[1:], start=2):

        def cell(key: str, row: list[str] = row) -> str:
            i = mapping.get(key)
            return row[i].strip() if i is not None and i < len(row) else ""

        if not any(c.strip() for c in row):
            continue
        shown = cell("connector") or connector or "J01"
        already = _find_connector(work, unit_id, shown)  # the sheet may use the name or the ID
        name = names.setdefault((already.id if already else shown).casefold(), shown)
        record = {k: cell(k) for k, _ in FIELDS if k in mapping}
        if fixed_column:  # a "Fixed" column holds yes/no, not a mode word
            record["mode"] = "fixed" if record.get("mode", "").casefold() in _YES else ""
        if not cell("pin"):
            plan.rows.append(PinoutRow(n, False, "The pin is empty", name, ""))
            continue
        if name not in by_connector:
            by_connector[name] = []
            order.append(name)
        by_connector[name].append((n, record))

    seen_rows: list[tuple[int, PinoutRow]] = []
    for name in order:
        rows = by_connector[name]
        existing = _find_connector(work, unit_id, name)
        cid = existing.id if existing is not None else ""
        ops: list[Op] = []
        is_new = existing is None
        if existing is None:
            part_id = (
                next((r["part"] for _n, r in rows if r.get("part")), "")
                or parts.get(name, "")
                or default_part
                or ""
            )
            if not part_id:
                msg = f"No part for the new connector {name}: give one for it (--part {name}=PART) or one for all"
                plan.rows += [PinoutRow(n, False, msg, name, r.get("pin", "")) for n, r in rows]
                continue
            sheet_gender = next((r["gender"] for _n, r in rows if r.get("gender")), "") or (
                gender or ""
            )
            word = _GENDER_WORDS.get(sheet_gender.strip().casefold()) if sheet_gender else None
            if sheet_gender and word is None:
                msg = f"The gender '{sheet_gender}' is not male or female"
                plan.rows += [PinoutRow(n, False, msg, name, r.get("pin", "")) for n, r in rows]
                continue
            try:
                new_ops, cid = devices.ops_add_connector(
                    work, unit_id, part_id=part_id, name=name if _usable_name(name) else None,
                    gender=word, pin_ids=[],
                )  # fmt: skip
            except (EditError, HarnessError) as exc:
                plan.rows += [
                    PinoutRow(n, False, str(exc), name, r.get("pin", "")) for n, r in rows
                ]
                continue
            ops += new_ops
            work = edit.clone_with(work, new_ops)
        sheet = [{k: v for k, v in r.items() if k in devices.ROW_COLUMNS} for _n, r in rows]
        pins = devices.plan_pin_rows(
            work, cid, sheet, replace=replace or is_new, row_numbers=[n for n, _r in rows]
        )
        if pins.issues:
            bad: set[int] = set()
            for issue in pins.issues:
                src = issue.row or rows[0][0]
                bad.add(src)
                plan.rows.append(PinoutRow(src, False, issue.reason, name, issue.pin))
            for n, r in rows:  # the rows without a problem are listed too (nothing is imported)
                if n not in bad:
                    plan.rows.append(PinoutRow(n, True, "ok", name, r["pin"]))
            continue
        try:
            set_ops = devices.ops_set_pinout(work, cid, list(pins.pins))
        except (EditError, HarnessError) as exc:
            plan.rows += [PinoutRow(n, False, str(exc), name, r.get("pin", "")) for n, r in rows]
            continue
        same = not is_new and not set_ops  # the table says what the connector already holds
        ops += set_ops
        work = edit.clone_with(work, set_ops)
        plan.ops += ops
        if same:
            plan.unchanged.append(cid)
        else:
            plan.connectors.append(cid)
            plan.pins += len(rows)
        if is_new:
            plan.added.append(cid)
        known = {s.name for t in work.interface_types.values() for s in t.signals}
        for _n, r in rows:
            sig = r.get("signal", "")
            if sig and sig not in known:
                plan.unmatched_signals.setdefault(sig, []).append(f"{cid} pin {r['pin']}")
        for n, r in rows:
            word = "added" if is_new else "unchanged" if same else "updated"
            seen_rows.append((n, PinoutRow(n, True, word, cid, r["pin"])))
    plan.rows += [r for _n, r in seen_rows]
    plan.rows.sort(key=lambda r: r.row_number)
    if plan.bad_count:
        plan.ops = []  # a sheet with a bad row is not imported at all
    return plan


def _usable_name(name: str) -> bool:
    return bool(name) and len(name) <= 200


def _find_connector(project: Project, unit_id: str, name: str):  # type: ignore[no-untyped-def]
    for c in edit.unit_connectors(project, unit_id):
        if name.casefold() in (c.id.casefold(), c.name.casefold()):
            return c
    return None
