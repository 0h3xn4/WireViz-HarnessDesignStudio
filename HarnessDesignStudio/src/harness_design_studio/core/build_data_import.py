"""Import the build data from a table (CSV, TSV, JSON or XLSX read by `imports.read_table_sheet`).

    plan = plan_build_data_import(project, table)      # table[0] is the header row
    plan.kind, plan.rows, plan.ops, plan.counts()

The kind of table is told by its column headings (any case, other columns are ignored):

- strip lengths: `Wire`, `Strip A (mm)` and/or `Strip B (mm)`; `Harness` is optional while the wire
  ID is unique in the project;
- pin contacts: `Connector`, `Pin`, `Contact` (a contact part of the library) and optionally
  `Harness` and `Tool` (the crimp tool of that contact part);
- accessories: `Harness`, `Kind`, and optionally `ID`, `Part`, `Target`, `Position`,
  `Length (mm)`, `Quantity`, `Note`; a row without an ID is numbered ACC-001, ACC-002 ...;
- part tools: `Part`, `Tool`.

Every data row gets a result with its reason; the rows are planned with `build_data` one after the
other on a scratch copy of the project, so a later row sees an earlier one. An empty cell leaves
the value as it is (it never clears). Nothing is invented and nothing is written here: the ops are
one undo step for the caller, who decides what a refused row means.
"""

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field

from . import build_data
from .commands import Op, Put, apply_ops
from .edit import EditError, clone_with
from .errors import HarnessError
from .imports import ImportError_
from .model import Harness, Project

Table = list[list[str]]

# kind -> field -> the headings that mean it (lower case, letters and digits only)
_HEADINGS: dict[str, dict[str, tuple[str, ...]]] = {
    "strips": {
        "harness": ("harness", "harnessid"),
        "wire": ("wire", "wireid"),
        "strip_a_mm": ("stripamm", "stripa"),
        "strip_b_mm": ("stripbmm", "stripb"),
    },
    "contacts": {
        "harness": ("harness", "harnessid"),
        "connector": ("connector", "connectorid"),
        "pin": ("pin", "pinid"),
        "contact": ("contact", "contactpart", "cablecontact"),
        "tool": ("tool", "crimptool"),
    },
    "accessories": {
        "harness": ("harness", "harnessid"),
        "id": ("id", "accessoryid"),
        "kind": ("kind", "type"),
        "part": ("part", "partid"),
        "target": ("target", "appliesto"),
        "position": ("position",),
        "length_mm": ("lengthmm", "length"),
        "quantity": ("quantity", "qty"),
        "note": ("note", "notes"),
    },
    "tools": {
        "part": ("part", "partid"),
        "tool": ("tool", "crimptool"),
    },
}
_NEEDS: dict[str, tuple[tuple[str, ...], ...]] = {  # kind -> groups of which one field is needed
    "strips": (("wire",), ("strip_a_mm", "strip_b_mm")),
    "contacts": (("connector",), ("pin",), ("contact",)),
    "accessories": (("harness",), ("kind",)),
    "tools": (("part",), ("tool",)),
}
KINDS: tuple[str, ...] = tuple(_NEEDS)  # the order decides when a table fits several
KIND_LABELS = {
    "strips": "Import strip lengths",
    "contacts": "Import pin contacts",
    "accessories": "Import accessories",
    "tools": "Import part tools",
}
EXPECTED = (
    "strip lengths: Wire, Strip A (mm), Strip B (mm) (Harness is optional); "
    "pin contacts: Harness, Connector, Pin, Contact (Tool is optional); "
    "accessories: Harness, Kind, Part, Target, Position, Length (mm), Quantity, Note "
    "(ID is optional); part tools: Part, Tool"
)


@dataclass
class BuildRow:
    row_number: int
    ok: bool
    message: str  # what the row does, or why it is refused
    target: str = ""  # the wire, pin, accessory or part the row is about
    action: str = ""  # "added", "changed" or "unchanged" for an accepted row


@dataclass
class BuildDataPlan:
    kind: str
    rows: list[BuildRow] = field(default_factory=list)
    ops: list[Op] = field(default_factory=list)

    @property
    def bad_count(self) -> int:
        return sum(not r.ok for r in self.rows)

    @property
    def label(self) -> str:
        return KIND_LABELS[self.kind]

    def counts(self) -> dict[str, int]:
        """The rows by result: added, changed, unchanged and refused."""
        out = {"added": 0, "changed": 0, "unchanged": 0, "refused": self.bad_count}
        for r in self.rows:
            if r.ok:
                out[r.action] += 1
        return out


def _norm(text: str) -> str:
    return "".join(ch for ch in text.lower() if ch.isalnum())


def _mapping(kind: str, header: list[str]) -> dict[str, int]:
    """Which column is which field of `kind`, by heading (the first column that matches wins)."""
    norm = [_norm(h) for h in header]
    out: dict[str, int] = {}
    for key, aliases in _HEADINGS[kind].items():
        hit = next((i for i, h in enumerate(norm) if h in aliases and i not in out.values()), None)
        if hit is not None:
            out[key] = hit
    return out


def detect_kind(header: list[str]) -> tuple[str, dict[str, int]]:
    """The kind of table the headings describe and its column mapping, or an ImportError_ that
    names the headings it expected."""
    for kind in KINDS:
        mapping = _mapping(kind, header)
        if all(any(k in mapping for k in group) for group in _NEEDS[kind]):
            return kind, mapping
    shown = ", ".join(h.strip() for h in header if h.strip()) or "none"
    raise ImportError_(
        f"The column headings are not those of any kind of build data. Expected {EXPECTED}. "
        f"The file has: {shown}."
    )


def plan_build_data_import(project: Project, table: Table) -> BuildDataPlan:
    """One result per data row of `table` (the first row is the header) and the ops of the rows
    that are accepted. The kind comes from the headings (`detect_kind`)."""
    kind, mapping = detect_kind(table[0] if table else [])
    plan = BuildDataPlan(kind)
    work = clone_with(project, [])  # rows are planned one after the other on a copy
    read = _READERS[kind](project)
    all_ops: list[Op] = []
    for n, row in enumerate(table[1:], start=2):
        if not any(c.strip() for c in row):
            continue

        def cell(key: str, row: list[str] = row) -> str:
            i = mapping.get(key)
            return row[i].strip() if i is not None and i < len(row) else ""

        try:
            target, action, message, ops = read(work, cell)
        except (EditError, HarnessError) as exc:
            plan.rows.append(BuildRow(n, False, str(exc), ""))
            continue
        apply_ops(work, ops)
        all_ops += ops
        plan.rows.append(BuildRow(n, True, message, target, action))
    plan.ops = _collapse(all_ops) if plan.bad_count == 0 else []
    return plan


def _collapse(ops: list[Op]) -> list[Op]:
    """The last `Put` of each object only: a harness that several rows changed is written once."""
    last: dict[tuple[str, str], Put] = {}
    for op in ops:
        if isinstance(op, Put):
            last[(op.collection, str(getattr(op.obj, "id", "")))] = op
    return list(last.values())


# ---- one reader per kind: (work project, cell) -> (target, action, message, ops) -------------

Result = tuple[str, str, str, list[Op]]
Cell = Callable[[str], str]


def _owner(index: Mapping[str, list[str]], harness: str, what: str, ident: str) -> str:
    """The harness a wire or connector is in: the one named, or the only one that has it."""
    if harness:
        return harness
    found = index.get(ident, [])
    if not found:
        raise EditError(f"{what} '{ident}' does not exist.")
    if len(found) > 1:
        raise EditError(
            f"{what} '{ident}' is in several harnesses ({', '.join(found)}); "
            "add a Harness column to say which."
        )
    return found[0]


def _strips(project: Project) -> Callable[[Project, Cell], Result]:
    index: dict[str, list[str]] = {}
    for h in sorted(project.harnesses.values(), key=lambda h: h.id):
        for w in h.wires:
            index.setdefault(w.id, []).append(h.id)

    def read(work: Project, cell: Cell) -> Result:
        wid = cell("wire")
        if not wid:
            raise EditError("The wire is empty.")
        hid = _owner(index, cell("harness"), "Wire", wid)
        given = {k: cell(k) for k in ("strip_a_mm", "strip_b_mm") if cell(k)}
        if not given:
            raise EditError(f"Wire {wid} has no strip length in this row.")
        ops = build_data.plan_set_strip(
            work,
            hid,
            [wid],
            strip_a_mm=given.get("strip_a_mm", build_data.UNSET),
            strip_b_mm=given.get("strip_b_mm", build_data.UNSET),
        )
        wire = next(w for w in work.harnesses[hid].wires if w.id == wid)
        after_h = next(
            (op.obj for op in ops if isinstance(op, Put) and isinstance(op.obj, Harness)),
            work.harnesses[hid],
        )
        new = next(w for w in after_h.wires if w.id == wid)
        parts, actions = [], []
        for key, label in (("strip_a_mm", "A"), ("strip_b_mm", "B")):
            if key not in given:
                continue
            before, after = getattr(wire, key), getattr(new, key)
            if before == after:
                actions.append("unchanged")
                parts.append(f"strip {label} {after:g} mm (as it was)")
            elif before is None:
                actions.append("added")
                parts.append(f"strip {label} {after:g} mm")
            else:
                actions.append("changed")
                parts.append(f"strip {label} {after:g} mm (was {before:g} mm)")
        return wid, _worst(actions), ", ".join(parts), ops

    return read


def _worst(actions: list[str]) -> str:
    """One word for a row that did several things: changed beats added beats unchanged."""
    for word in ("changed", "added"):
        if word in actions:
            return word
    return "unchanged"


def _contacts(project: Project) -> Callable[[Project, Cell], Result]:
    index: dict[str, list[str]] = {}
    for h in sorted(project.harnesses.values(), key=lambda h: h.id):
        for c in h.connectors:
            index.setdefault(c.id, []).append(h.id)
    tools: dict[str, str] = {}  # contact part -> the tool this file gave it

    def read(work: Project, cell: Cell) -> Result:
        cid, pin, contact, tool = cell("connector"), cell("pin"), cell("contact"), cell("tool")
        if not cid or not pin:
            raise EditError("The connector or the pin is empty.")
        if not contact:
            raise EditError(f"Pin {pin} of {cid} has no contact in this row.")
        hid = _owner(index, cell("harness"), "Connector", cid)
        ops: list[Op] = []
        if tool:  # the tool is checked first: a refused tool refuses the row, nothing is half done
            if tools.get(contact, tool) != tool:
                raise EditError(f"{contact} has the tool '{tools[contact]}' in an earlier row.")
            ops += build_data.plan_set_part_tool(work, contact, tool)
        ops += build_data.plan_set_contacts(work, hid, cid, [pin], contact)
        if tool:
            tools[contact] = tool
        before = next(
            p for c in work.harnesses[hid].connectors if c.id == cid for p in c.pins if p.id == pin
        )
        if before.contact_part == contact:
            verb = "changed" if tool and ops else "unchanged"
        else:
            verb = "added" if before.contact_part is None else "changed"
        said = f"contact {contact}" + (f", tool {tool}" if tool else "")
        return f"{cid}.{pin}", verb, said, ops

    return read


def _accessories(project: Project) -> Callable[[Project, Cell], Result]:
    def read(work: Project, cell: Cell) -> Result:
        hid = cell("harness")
        h = work.harnesses.get(hid)
        if h is None:
            raise EditError(f"Harness '{hid}' does not exist." if hid else "The harness is empty.")
        kind = cell("kind").casefold().replace(" ", "_").replace("-", "_")
        data: dict[str, object] = {
            "kind": kind,
            "part_id": cell("part"),
            "target": cell("target"),
            "position": cell("position"),
            "length_mm": cell("length_mm"),
            "quantity": cell("quantity") or 1,
            "note": cell("note"),
        }
        given = cell("id")
        data["id"] = given or build_data.plan_next_accessory_id(h)
        new = build_data.check_accessory(work, hid, data)
        if not given:  # the same row again is not another accessory
            for a in h.accessories:
                if a.model_dump(exclude={"id"}) == new.model_dump(exclude={"id"}):
                    return a.id, "unchanged", f"{a.id} is in the harness already", []
        ops = build_data.plan_set_accessory(work, hid, new)
        if not ops:
            return new.id, "unchanged", f"{new.id} is as it was", []
        action = "changed" if any(a.id == new.id for a in h.accessories) else "added"
        return new.id, action, f"{kind.replace('_', ' ')} on {new.target or 'the harness'}", ops

    return read


def _tools(project: Project) -> Callable[[Project, Cell], Result]:
    seen: dict[str, str] = {}

    def read(work: Project, cell: Cell) -> Result:
        pid, tool = cell("part"), cell("tool")
        if not pid:
            raise EditError("The part is empty.")
        if not tool:
            raise EditError(f"Part {pid} has no tool in this row.")
        if seen.get(pid, tool) != tool:
            raise EditError(f"{pid} has the tool '{seen[pid]}' in an earlier row.")
        before = work.parts[pid].tool if pid in work.parts else None
        ops = build_data.plan_set_part_tool(work, pid, tool)
        seen[pid] = tool
        action = "unchanged" if not ops else "added" if before is None else "changed"
        return pid, action, f"tool {tool}", ops

    return read


_READERS: dict[str, Callable[[Project], Callable[[Project, Cell], Result]]] = {
    "strips": _strips,
    "contacts": _contacts,
    "accessories": _accessories,
    "tools": _tools,
}

__all__ = [
    "KINDS",
    "BuildDataPlan",
    "BuildRow",
    "detect_kind",
    "plan_build_data_import",
]
