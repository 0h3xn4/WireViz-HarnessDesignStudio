"""Import an approved-parts list (CSV, TSV, JSON or XLSX) into the project's parts library (D-12).
An export of a parts program such as InvenTree is such a list: its IPN column is read as the part ID,
its Name or Description as the description, its MPN as the part number (D-165); the file is read
offline, nothing connects to a server.

The tool does not know any program's list format, so columns are mapped by header name (with
common aliases) and the meaning of the approval column is stated by you: values you list as
approved, pending or rejected. A status that is not in any of your lists is an error for that
row; the tool never guesses whether a part is approved. Preview first, apply as one undo step.
"""

import re
from dataclasses import dataclass, field

from pydantic import ValidationError

from harness_design_studio.core.commands import Op, Put, SetLibraryInfo
from harness_design_studio.core.ids import ID_RE
from harness_design_studio.core.imports import ImportError_
from harness_design_studio.core.model import Part, Project, evolve
from harness_design_studio.core.model.library import PART_CATEGORIES
from harness_design_studio.core.vcs.release import valid_date

Table = list[list[str]]

FIELDS: tuple[tuple[str, str], ...] = (
    ("id", "Part ID"), ("category", "Category"), ("manufacturer", "Manufacturer"),
    ("part_number", "Part number"), ("description", "Description"), ("specification", "Specification"),
    ("approval", "Approval status"), ("pin_count", "Pin count"), ("mass_g", "Mass (g)"),
    ("mass_per_m_g", "Mass per metre (g/m)"), ("mates_with", "Mating part ID"),
)  # fmt: skip
_ALIASES = {
    "id": (
        "ipn",
        "partipn",
        "internalpartnumber",
        "id",
        "partid",
        "part",
        "item",
        "ref",
    ),  # InvenTree: the IPN is the name people use, its "ID" is a database number
    "category": ("category", "type", "class", "kind"),
    "manufacturer": ("manufacturer", "mfr", "vendor", "supplier", "maker"),
    "part_number": ("partnumber", "pn", "mpn", "partno", "number"),
    "description": ("description", "desc", "name", "title"),
    "specification": ("specification", "spec", "standard"),
    "approval": ("approval", "status", "approvalstatus", "eppl", "approved", "qualification"),
    "pin_count": ("pincount", "pins", "contacts", "positions"),
    "mass_g": ("massg", "mass", "weightg", "weight"),
    "mass_per_m_g": ("masspermg", "gpm", "massperm", "weightperm"),
    "mates_with": ("mateswith", "mate", "mating", "matingpart"),
}


@dataclass
class PartRow:
    row_number: int
    ok: bool
    message: str
    part_id: str = ""
    action: str = ""  # "added" | "updated"


@dataclass
class PartsPlan:
    rows: list[PartRow] = field(default_factory=list)
    ops: list[Op] = field(default_factory=list)

    @property
    def ok_count(self) -> int:
        return sum(r.ok for r in self.rows)


def guess_mapping(header: list[str]) -> dict[str, int]:
    norm = ["".join(ch for ch in h.lower() if ch.isalnum()) for h in header]
    if sum(h in _ALIASES["approval"] for h in norm) > 1:  # which one would be meant?
        raise ImportError_(
            "Two columns of the file are both about the approval status; keep only one."
        )
    out: dict[str, int] = {}
    used: set[int] = set()
    for key, _ in FIELDS:
        for alias in _ALIASES[key]:
            hit = next((i for i, h in enumerate(norm) if h == alias and i not in used), None)
            if hit is not None:
                out[key] = hit
                used.add(hit)
                break
    return out


def _category_word(text: str) -> str:
    """`Connectors/D-Sub` and `Wires` as a program with category trees exports them: the first step
    of the path that is one of the tool's six categories or its plural, as that category. Any other
    text is returned as it is (and then refused, never guessed)."""
    steps = [x.strip().lower() for x in re.split(r"[/>|\\]", text)]
    for step in steps:
        word = step[:-1] if step.endswith("s") and step[:-1] in PART_CATEGORIES else step
        if word in PART_CATEGORIES:
            return word
    return text.strip().lower()


def _words(values: list[str]) -> set[str]:
    return {v.strip().casefold() for v in values if v.strip()}


MAX_PIN_COUNT = 1000
_PLAIN = re.compile(r"[0-9]{1,15}(\.[0-9]{1,12})?")
_COMMA = re.compile(r"([0-9]{1,15}),([0-9]{1,12})")
_WHOLE = re.compile(r"[0-9]{1,6}(\.0+)?")


def _number(text: str) -> float | None:
    """A plain number: digits with a point, or with one decimal comma. Not 1e3, 1_0, -0, inf, a
    thousands separator (1,234 could be 1.234 or 1234) or digits of another script."""
    text = text.strip()
    if _PLAIN.fullmatch(text):
        return float(text)
    m = _COMMA.fullmatch(text)
    if m and len(m.group(2)) != 3:  # three digits after a comma: thousands or decimals?
        return float(f"{m.group(1)}.{m.group(2)}")
    return None


def _number_problem(text: str, label: str) -> str:
    if _COMMA.fullmatch(text.strip()):
        return f"{label} '{text}' could mean {text.replace(',', '.')} or a thousands separator; write it with a point"  # fmt: skip
    return f"{label} '{text}' is not a plain number (digits, with a point for decimals)"


def _field_message(exc: ValidationError) -> str:
    """The first problem of a part as 'Label: what is wrong', never the raw validation text."""
    labels = dict(FIELDS)
    err = exc.errors()[0]
    name = str(err["loc"][0]) if err["loc"] else "part"
    what = str(err["msg"]).removeprefix("Value error, ")
    return f"{labels.get(name, name)}: {what}"


def plan_parts_import(
    project: Project,
    table: Table,
    mapping: dict[str, int],
    *,
    approved: list[str],
    pending: list[str] | None = None,
    rejected: list[str] | None = None,
    default_category: str | None = None,
) -> PartsPlan:
    """One result per data row. `approved`, `pending` and `rejected` say what the values of the
    approval column mean in YOUR list."""
    ok_words, pend_words, rej_words = (
        _words(approved),
        _words(pending or []),
        _words(rejected or []),
    )
    overlap = (ok_words & rej_words) | (ok_words & pend_words) | (pend_words & rej_words)
    if overlap:
        raise ImportError_(
            f"'{sorted(overlap)[0]}' is listed under more than one of approved, pending and "
            "rejected; a value can mean only one of them."
        )
    plan = PartsPlan()
    seen: dict[str, Part] = {}
    first_row: dict[str, int] = {}
    by_fold = {p.casefold(): p for p in project.parts}
    for n, row in enumerate(table[1:], start=2):

        def cell(key: str, row: list[str] = row) -> str:
            i = mapping.get(key)
            return row[i].strip() if i is not None and i < len(row) else ""

        pid = cell("id") or cell("part_number")
        if not pid:
            plan.rows.append(PartRow(n, False, "The row has no part ID or part number"))
            continue
        if not ID_RE.fullmatch(pid) or pid.endswith("."):
            plan.rows.append(
                PartRow(
                    n,
                    False,
                    f"'{pid}' cannot be used as a part ID (letters, digits, - _ . and a letter first); put a usable ID in the ID column",
                    pid,
                )
            )
            continue
        if pid in first_row:
            plan.rows.append(
                PartRow(
                    n,
                    False,
                    f"'{pid}' is already in row {first_row[pid]} of this file; each part may appear once",
                    pid,
                )
            )
            continue
        clash = by_fold.get(pid.casefold())
        if clash is not None and clash != pid:
            plan.rows.append(
                PartRow(n, False, f"'{pid}' differs only in upper/lower case from '{clash}'", pid)
            )
            continue
        category = _category_word(cell("category") or default_category or "")
        old = seen.get(pid) or project.parts.get(pid)
        if category not in PART_CATEGORIES:
            if old is None or cell("category"):
                shown = category or "(empty)"
                plan.rows.append(
                    PartRow(
                        n,
                        False,
                        f"Category '{shown}' is not one of {', '.join(PART_CATEGORIES)}",
                        pid,
                    )
                )
                continue
            category = old.category
        status = cell("approval").casefold()
        if not status:
            approval = old.approval if old is not None else "pending"
        elif status in ok_words:
            approval = "approved"
        elif status in rej_words:
            approval = "not_approved"
        elif status in pend_words:
            approval = "pending"
        else:
            plan.rows.append(
                PartRow(
                    n,
                    False,
                    f"Approval status '{cell('approval')}' is not in your approved, pending or rejected lists; say what it means",
                    pid,
                )
            )
            continue
        changes: dict[str, object] = {
            "category": category,
            "approval": approval,
            "unverified": False,
        }
        problem = ""
        for key in ("manufacturer", "part_number", "description", "specification", "mates_with"):
            if cell(key):
                changes[key] = cell(key)
        for key in ("mass_g", "mass_per_m_g"):
            if cell(key):
                value = _number(cell(key))
                if value is None:
                    problem = problem or _number_problem(cell(key), dict(FIELDS)[key])
                changes[key] = value
        if cell("pin_count"):
            text = cell("pin_count")
            if _WHOLE.fullmatch(text) and 1 <= float(text) <= MAX_PIN_COUNT:
                changes["pin_count"] = int(float(text))
            else:
                problem = problem or (
                    f"Pin count '{text}' is not a whole number from 1 to {MAX_PIN_COUNT}"
                )
        if problem:
            plan.rows.append(PartRow(n, False, problem, pid))
            continue
        try:
            part = evolve(old, **changes) if old is not None else Part(id=pid, **changes)  # type: ignore[arg-type]
        except ValidationError as exc:
            plan.rows.append(PartRow(n, False, _field_message(exc), pid))
            continue
        except ValueError as exc:
            plan.rows.append(PartRow(n, False, str(exc).splitlines()[0][:120], pid))
            continue
        seen[pid] = part
        first_row[pid] = n
        by_fold.setdefault(pid.casefold(), pid)
        plan.rows.append(PartRow(n, True, "", pid, "updated" if pid in project.parts else "added"))
    for k, prow in enumerate(plan.rows):  # a mating part must exist (now or after this import)
        cand = seen.get(prow.part_id or "") if prow.ok else None
        if cand is not None and cand.mates_with and cand.mates_with not in {*project.parts, *seen}:
            plan.rows[k] = PartRow(
                prow.row_number,
                False,
                f"Mating part '{cand.mates_with}' is not in the library or in this file",
                prow.part_id,
            )
    good = {r.part_id for r in plan.rows if r.ok}
    plan.ops = [Put("parts", part) for part in seen.values() if part.id in good]
    return plan


def library_ops(
    project: Project,
    *,
    name: str | None = None,
    version: str | None = None,
    source: str | None = None,
    date: str | None = None,
) -> list[Op]:
    """Operations that record where the library comes from; fields left as None stay as they are.
    A bad value raises ImportError_ before anything changes; only a bad date gets the date message."""
    given = {k: v for k, v in (("name", name), ("version", version), ("source", source), ("date", date)) if v is not None}  # fmt: skip
    if not given:
        return []
    if date is not None and not valid_date(date):
        raise ImportError_("The library date must be written YYYY-MM-DD (for example 2026-10-08).")
    for key, value in given.items():  # say which field is wrong, and what is wrong with it
        try:
            evolve(project.library_info, **{key: value})
        except ValidationError as exc:
            what = str(exc.errors()[0]["msg"]).removeprefix("Value error, ")
            raise ImportError_(f"The library {key} is not acceptable: {what}.") from exc
    info = evolve(project.library_info, **given)
    return [] if info == project.library_info else [SetLibraryInfo(info)]


def describe_library(project: Project) -> str:
    """One line for people: name, version, source and date of the library."""
    i = project.library_info
    parts = [f"{i.name} (version {i.version})"]
    parts.append(f"source: {i.source}" if i.source else "source: not recorded")
    parts.append(f"data of {i.date}" if i.date else "date: not recorded")
    return ", ".join(parts)
