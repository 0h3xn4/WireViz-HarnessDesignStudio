# SPDX-FileCopyrightText: 2026 0h3xn4
# SPDX-License-Identifier: GPL-3.0-only
"""As-built capture: what was built and measured, compared with what was designed (S9, R6).

    report = asbuilt_report(project)            # complete, missing, out of limit, differs from design
    table = template_rows(project)              # the sheet a technician fills in (designed values prefilled)
    plan = plan_asbuilt_import(project, table)  # the same sheet read back: rows, ops, conversions

The build workbook is a document to write on; this module is how what was written comes back. The
records are `AsBuiltRecord`s (`asbuilt/records.json`, optional, not in the model hash). Nothing here
reads a clock, a login or a path, and nothing says that a harness *passed*: a result is **within
its limit**, **out of its limit**, **not compared** (the limit is not set) or **missing**, and a
result that is out of its limit stays so until a person records something else; the tool never
accepts it. A deviation of the design can be accepted with the tool's own mechanism (`deviation`)
where it applies; an as-built result is not a finding of a design rule.

What is expected of a harness that has records (a harness with none is *not started*, and nothing
is missing from it): its serial number and the names of who built and who inspected it; the lot of
each wire part and connector part it uses; the cut length of every wire (and its strip lengths where
the design has them); the crimp tool and its calibration ID for every pin in use that is crimped;
the result and the measured value of every test of the Tests sheet. The limits are the project's
test limits (`config/generation.json`), the ones the Tests sheet prints. A length is compared with
the designed length: the difference is listed, and no tolerance is applied unless the project sets
one (`asbuilt_cut_tolerance_mm`, `asbuilt_strip_tolerance_mm`, assumption A-ASBUILT-TOLERANCE); with
one set, a difference within it is **within limit** and a larger one is **out of limit**, like a test.
"""

import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from typing import Any

from pydantic import ValidationError

from harness_design_studio.core.commands import Op, Put
from harness_design_studio.core.generate.lengths import LENGTH_UNITS_M, wire_length
from harness_design_studio.core.import_record import (
    ImportReport,
    clean,
    number_text,
    table_report,
)
from harness_design_studio.core.imports import ImportError_
from harness_design_studio.core.model import AsBuiltRecord, Harness, Project, evolve
from harness_design_studio.core.model.asbuilt import AS_BUILT_KINDS, ASBUILT_FILE, record_id
from harness_design_studio.core.outputs import tables

Table = list[list[str]]

# the statuses of a line of the report
RECORDED = "recorded"  # a value is there and there is nothing to compare it with
MISSING = "missing"
WITHIN = "within limit"
OUT = "out of limit"
NOT_COMPARED = "not compared"  # the limit of the project is not set
DIFFERS = "differs from design"
AS_DESIGNED = "as designed"
STALE = "stale record"  # the record is about something the design no longer has
NOT_STARTED = "not started"

TOLERANCE = 1e-9  # two numbers closer than this are the same number (the rounding of a file)

# the number of an as-built field for a limit: field -> (the key of config/generation.json, unit)
LIMIT_KEYS = {
    "continuity_ohm": ("test_continuity_max_ohm", "ohm"),
    "isolation_mohm": ("test_isolation_min_mohm", "Mohm"),
    "test_voltage_v": ("test_isolation_voltage_v", "V"),
}


# the tolerance of a length: the name of the value -> the key of config/generation.json (millimetres)
TOLERANCE_KEYS = {
    "cut length": "asbuilt_cut_tolerance_mm",
    "strip A": "asbuilt_strip_tolerance_mm",
    "strip B": "asbuilt_strip_tolerance_mm",
}


@dataclass(frozen=True)
class LengthCheck:
    """A recorded length against the designed one and the tolerance of the project (A-ASBUILT-TOLERANCE).
    The one calculation the report and the explanation share."""

    key: str  # the key of config/generation.json
    tolerance_mm: float
    difference: float  # recorded minus designed, in the unit of the value
    distance_mm: float  # how far from the design, either way
    room_mm: float  # tolerance minus distance: positive, room left; negative, exceeded by
    within: bool
    scale: float  # millimetres in one unit of the value


def length_check(
    project: Project, field_name: str, unit: str, actual: float, designed: float
) -> LengthCheck | None:
    """None while the project sets no tolerance for this length (no tolerance is applied). A
    distance equal to the tolerance is within it."""
    key = TOLERANCE_KEYS[field_name]
    tolerance = tables.limit_value(project, key)
    if tolerance is None or tolerance < 0:
        return None
    scale = 1000.0 if unit == "m" else 1.0
    diff = round(actual - designed, 9)
    distance = round(abs(diff) * scale, 9)
    room = round(tolerance - distance, 9)
    return LengthCheck(key, tolerance, diff, distance, room, room >= 0, scale)


@dataclass(frozen=True)
class Line:
    """One line of the report: one value of one thing."""

    harness_id: str
    kind: str  # harness | part | wire | connector | pin | test
    subject: str
    field: str  # the name of the value, with its unit: "cut length (m)"
    status: str
    actual: float | str | None = None
    designed: float | str | None = None  # the designed value, or the limit
    unit: str = ""
    margin: float | None = None  # for a limit: room left (positive) or exceeded by (negative)
    text: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "harness": self.harness_id, "kind": self.kind, "subject": self.subject,
            "field": self.field, "status": self.status, "actual": self.actual,
            "designed": self.designed, "unit": self.unit, "margin": self.margin, "text": self.text,
        }  # fmt: skip


@dataclass(frozen=True)
class HarnessStatus:
    harness_id: str
    started: bool
    needed: int = 0
    recorded: int = 0
    missing: int = 0
    out_of_limit: int = 0
    within_limit: int = 0
    not_compared: int = 0
    differs: int = 0
    stale: int = 0

    @property
    def complete(self) -> bool:
        return self.started and self.missing == 0 and self.stale == 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "harness": self.harness_id, "started": self.started, "complete": self.complete,
            "needed": self.needed, "recorded": self.recorded, "missing": self.missing,
            "out_of_limit": self.out_of_limit, "within_limit": self.within_limit,
            "not_compared": self.not_compared, "differs_from_design": self.differs,
            "stale_records": self.stale,
        }  # fmt: skip


@dataclass(frozen=True)
class AsBuiltReport:
    lines: tuple[Line, ...]
    harnesses: tuple[HarnessStatus, ...]
    records: int

    @property
    def has_records(self) -> bool:
        return self.records > 0

    def count(self, status: str) -> int:
        return sum(1 for ln in self.lines if ln.status == status)

    @property
    def missing(self) -> int:
        return self.count(MISSING)

    @property
    def out_of_limit(self) -> int:
        return self.count(OUT)

    @property
    def complete(self) -> bool:
        started = [h for h in self.harnesses if h.started]
        return bool(started) and all(h.complete for h in started)

    def to_dict(self) -> dict[str, Any]:
        return {
            "records": self.records,
            "complete": self.complete,
            "missing": self.missing,
            "out_of_limit": self.out_of_limit,
            "within_limit": self.count(WITHIN),
            "not_compared": self.count(NOT_COMPARED),
            "differs_from_design": self.count(DIFFERS),
            "stale_records": self.count(STALE),
            "harnesses": [h.to_dict() for h in self.harnesses],
            "lines": [ln.to_dict() for ln in self.lines if ln.status != AS_DESIGNED],
        }


# ---- what the design has ------------------------------------------------------------------------


def _used_pins(h: Harness) -> set[tuple[str, str]]:
    used: set[tuple[str, str]] = set()
    for w in h.wires:
        used.add((w.from_connector, w.from_pin))
        used.add((w.to_connector, w.to_pin))
    return used


def _crimped_pins(h: Harness) -> list[str]:
    used = _used_pins(h)
    return sorted(
        f"{c.id}.{p.id}"
        for c in h.connectors
        for p in c.pins
        if (c.id, p.id) in used and p.termination == "crimp"
    )


def _parts_of(h: Harness) -> list[str]:
    ids = {w.part_id for w in h.wires if w.part_id} | {c.part_id for c in h.connectors if c.part_id}
    return sorted(ids)


def _tests(project: Project, h: Harness) -> dict[str, list[str]]:
    return {r[0]: r for r in tables.tests(project, h)[1:]}


def _started(project: Project) -> set[str]:
    return {r.harness_id for r in project.asbuilt.values()}


def _get(project: Project, kind: str, hid: str, subject: str) -> AsBuiltRecord | None:
    return project.asbuilt.get(record_id(kind, hid, subject))


# ---- the report ---------------------------------------------------------------------------------


def _limit(project: Project, field_name: str) -> float | None:
    return tables.limit_value(project, LIMIT_KEYS[field_name][0])


def _value_line(
    h: str, kind: str, subject: str, field_name: str, unit: str, actual: float | None,
    designed: float | None, *, needed: bool = True, scale: float = 1.0,
    check: LengthCheck | None = None,
) -> Line | None:  # fmt: skip
    """A value that is compared with a designed value: missing, as designed, or differs (with the
    difference). `scale` is the factor from the unit to the one that the difference is shown in.
    With a `check` (the project set a tolerance for this length) a difference is within the tolerance
    or out of it, like a test result against its limit."""
    label = f"{field_name} ({unit})"
    if actual is None:
        return Line(h, kind, subject, label, MISSING, None, designed, unit) if needed else None
    if designed is None:
        return Line(h, kind, subject, label, RECORDED, actual, None, unit)
    diff = round(actual - designed, 9)
    if abs(diff) < TOLERANCE:
        return Line(h, kind, subject, label, AS_DESIGNED, actual, designed, unit, 0.0)
    shown = f"{diff * scale:+g} mm" if scale != 1.0 else f"{diff:+g} {unit}"
    built = f"{actual:g} {unit} was built, {designed:g} {unit} is designed ({shown})"
    if check is not None:
        room = round(check.room_mm / check.scale, 9)  # in the unit of the value
        verdict = (
            "within the tolerance" if check.within else f"OUT OF TOLERANCE by {-check.room_mm:g} mm"
        )
        return Line(
            h, kind, subject, label, WITHIN if check.within else OUT, actual, designed, unit, room,
            f"{built}; tolerance +/-{check.tolerance_mm:g} mm (config/generation.json: {check.key}, A-ASBUILT-TOLERANCE): {verdict}",
        )  # fmt: skip
    return Line(
        h, kind, subject, label, DIFFERS, actual, designed, unit, diff,
        f"{built}; no tolerance applied",
    )  # fmt: skip


def _text_line(h: str, kind: str, subject: str, label: str, value: str) -> Line:
    return Line(h, kind, subject, label, RECORDED if value else MISSING, value or None)


def _test_lines(
    project: Project, hid: str, tid: str, rec: AsBuiltRecord | None, row: Sequence[str] | None
) -> list[Line]:
    """The lines of one test: the result recorded, and the measured value against the limit."""
    out: list[Line] = []
    if rec is not None and (row is None or (rec.test_type or row[1]) != row[1] or (rec.tested or row[7]) != row[7]):  # fmt: skip
        return [Line(hid, "test", tid, "test", STALE, None, None, "", None, "the test list of the design changed: this test is not the test that was recorded")]  # fmt: skip
    if row is None:
        return out
    kind = row[1]
    result = rec.result if rec else None
    if result is None:
        out.append(Line(hid, "test", tid, "result", MISSING))
    measured = rec.continuity_ohm if (rec and kind == "continuity") else rec.isolation_mohm if rec else None  # fmt: skip
    field_name = "continuity_ohm" if kind == "continuity" else "isolation_mohm"
    unit = LIMIT_KEYS[field_name][1]
    label = ("continuity resistance" if kind == "continuity" else "insulation resistance") + f" ({unit})"  # fmt: skip
    limit = _limit(project, field_name)
    if measured is None:
        out.append(Line(hid, "test", tid, label, MISSING, None, limit, unit))
    elif limit is None:
        out.append(Line(hid, "test", tid, label, NOT_COMPARED, measured, None, unit, None, f"the limit {LIMIT_KEYS[field_name][0]} is not set"))  # fmt: skip
    else:
        upper = (
            kind == "continuity"
        )  # continuity: at most the limit; insulation: at least the limit
        margin = round(limit - measured if upper else measured - limit, 9)
        within = margin >= 0
        word = "at most" if upper else "at least"
        out.append(Line(hid, "test", tid, label, WITHIN if within else OUT, measured, limit, unit, margin, f"{measured:g} {unit} measured, limit {word} {limit:g} {unit}"))  # fmt: skip
    note = (
        row[8] if len(row) > 8 else ""
    )  # the `Deviations` cell: an override or a deviation of the wire
    if note and measured is not None:
        ln = out[-1]
        out[-1] = replace(ln, text=f"{ln.text}; design: {note}" if ln.text else f"design: {note}")
    if kind == "isolation":
        volts = _limit(project, "test_voltage_v")
        applied = rec.test_voltage_v if rec else None
        line = _value_line(hid, "test", tid, "test voltage", "V", applied, volts)
        if line is not None:
            out.append(line)
    measured_out = next((i for i, ln in enumerate(out) if ln.status == OUT), None)
    if result == "pass" and measured_out is not None:
        ln = out[measured_out]
        out[measured_out] = Line(ln.harness_id, ln.kind, ln.subject, ln.field, OUT, ln.actual, ln.designed, ln.unit, ln.margin, ln.text + "; recorded as passed: the tool does not accept it")  # fmt: skip
    if result == "fail" and measured_out is None:
        out.append(Line(hid, "test", tid, "result", OUT, None, None, "", None, "recorded as failed by the person who tested"))  # fmt: skip
    return out


def harness_lines(project: Project, h: Harness) -> list[Line]:
    """Every line of one harness that has records, in a fixed order."""
    hid = h.id
    lines: list[Line] = []
    rec = _get(project, "harness", hid, hid)
    serials = ", ".join(rec.serial_numbers) if rec else ""
    lines.append(_text_line(hid, "harness", hid, "serial number", serials))
    lines.append(_text_line(hid, "harness", hid, "built by", rec.built_by if rec else ""))
    lines.append(_text_line(hid, "harness", hid, "inspected by", rec.inspected_by if rec else ""))
    for pid in _parts_of(h):
        pr = _get(project, "part", hid, pid)
        lines.append(_text_line(hid, "part", pid, "lot", pr.lot if pr else ""))
    for w in sorted(h.wires, key=lambda x: x.id):
        wr = _get(project, "wire", hid, w.id)
        length = wire_length(h, w)
        cut = wr.cut_length_m if wr else None
        strip_a = wr.strip_a_mm if wr else None
        strip_b = wr.strip_b_mm if wr else None
        for line in (
            _value_line(
                hid, "wire", w.id, "cut length", "m", cut, length, scale=1000.0,
                check=None if cut is None or length is None else length_check(project, "cut length", "m", cut, length),
            ),
            _value_line(
                hid, "wire", w.id, "strip A", "mm", strip_a, w.strip_a_mm,
                needed=w.strip_a_mm is not None,
                check=None if strip_a is None or w.strip_a_mm is None else length_check(project, "strip A", "mm", strip_a, w.strip_a_mm),
            ),
            _value_line(
                hid, "wire", w.id, "strip B", "mm", strip_b, w.strip_b_mm,
                needed=w.strip_b_mm is not None,
                check=None if strip_b is None or w.strip_b_mm is None else length_check(project, "strip B", "mm", strip_b, w.strip_b_mm),
            ),
        ):  # fmt: skip
            if line is not None:
                lines.append(line)
    for pin in _crimped_pins(h):
        pr = _get(project, "pin", hid, pin)
        lines.append(_text_line(hid, "pin", pin, "crimp tool", pr.crimp_tool if pr else ""))
        lines.append(_text_line(hid, "pin", pin, "crimp tool calibration ID", pr.crimp_tool_calibration_id if pr else ""))  # fmt: skip
    rows = _tests(project, h)
    for tid, row in rows.items():
        lines += _test_lines(project, hid, tid, _get(project, "test", hid, tid), row)
    # records about things the design no longer has
    known = _known_subjects(h, rows)
    for r in sorted(project.asbuilt.values(), key=lambda x: x.id):
        if r.harness_id == hid and (r.kind, r.subject) not in known and r.kind != "test":
            lines.append(Line(hid, r.kind, r.subject, r.kind, STALE, None, None, "", None, f"the design has no {r.kind} {r.subject}"))  # fmt: skip
        if r.harness_id == hid and r.kind == "test" and r.subject not in rows:
            lines.append(Line(hid, "test", r.subject, "test", STALE, None, None, "", None, "the design has no such test"))  # fmt: skip
    return lines


def _known_subjects(h: Harness, rows: Mapping[str, Any]) -> set[tuple[str, str]]:
    known = {("harness", h.id)}
    known |= {("part", p) for p in _parts_of(h)} | {("wire", w.id) for w in h.wires}
    known |= {("connector", c.id) for c in h.connectors}
    known |= {("pin", f"{c.id}.{p.id}") for c in h.connectors for p in c.pins}
    return known


def asbuilt_report(project: Project) -> AsBuiltReport:
    """The report of the project: for each harness (by ID) *not started* when it has no record,
    else its lines and counts. A project with no record at all has a report with no line."""
    started = _started(project)
    lines: list[Line] = []
    statuses: list[HarnessStatus] = []
    for hid in sorted(project.harnesses):
        if hid not in started:
            statuses.append(HarnessStatus(hid, False))
            continue
        mine = harness_lines(project, project.harnesses[hid])
        lines += mine
        statuses.append(_status(hid, mine))
    for hid in sorted(started - set(project.harnesses)):  # a record of a harness that is gone
        n = sum(1 for r in project.asbuilt.values() if r.harness_id == hid)
        lines.append(Line(hid, "harness", hid, "harness", STALE, None, None, "", None, f"the design has no harness {hid}; {n} record(s) are about it"))  # fmt: skip
        statuses.append(HarnessStatus(hid, True, stale=1))
    return AsBuiltReport(tuple(lines), tuple(statuses), len(project.asbuilt))


def _status(hid: str, lines: list[Line]) -> HarnessStatus:
    def n(s: str) -> int:
        return sum(1 for ln in lines if ln.status == s)

    needed = sum(1 for ln in lines if ln.status != STALE and not (ln.field == "result" and ln.status == OUT))  # fmt: skip
    recorded = needed - n(MISSING)
    return HarnessStatus(
        hid, True, needed, recorded, n(MISSING), n(OUT), n(WITHIN), n(NOT_COMPARED), n(DIFFERS), n(STALE)
    )  # fmt: skip


# ---- the report as a table, for the written output and the workbook ----------------------------

REPORT_HEADER = [
    "Harness", "Kind", "Item", "Value", "Status", "Actual", "Designed or limit", "Unit",
    "Margin", "Note",
]  # fmt: skip


def report_rows(project: Project, harness_id: str | None = None) -> Table:
    """The lines of the report as plain rows (every line, as designed ones too)."""
    rep = asbuilt_report(project)
    rows: Table = [list(REPORT_HEADER)]
    for ln in rep.lines:
        if harness_id is not None and ln.harness_id != harness_id:
            continue
        rows.append([
            ln.harness_id, ln.kind, ln.subject, ln.field, ln.status,
            _cell(ln.actual), _cell(ln.designed), ln.unit, _cell(ln.margin), ln.text,
        ])  # fmt: skip
    return rows


def _cell(v: float | str | None) -> str:
    if v is None:
        return ""
    return tables.data_num(v) if isinstance(v, float) else str(v)


def report_markdown(project: Project, stamp_line: str) -> str:
    """The as-built report as text to print. It says what was recorded and how it compares; it does
    not say that anything passed."""
    rep = asbuilt_report(project)
    out = [f"<!-- {stamp_line} -->", "# As-built report", ""]
    out.append(
        "This report lists what the technicians recorded (`asbuilt/records.json`) and compares it "
        "with the design and with the test limits of the project. A result that is out of its limit "
        "is shown as such and stays so until a person records something else; the tool does not "
        "accept it. This report is not a sign-off and does not say that a harness is compliant."
    )
    out += ["", "## Summary", ""]
    out.append("| Harness | State | Needed | Recorded | Missing | Out of limit | Within limit | Not compared | Differs from design | Stale |")  # fmt: skip
    out.append("| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |")
    for s in rep.harnesses:
        state = ("complete" if s.complete else "incomplete") if s.started else NOT_STARTED
        out.append(f"| {s.harness_id} | {state} | {s.needed} | {s.recorded} | {s.missing} | {s.out_of_limit} | {s.within_limit} | {s.not_compared} | {s.differs} | {s.stale} |")  # fmt: skip
    for title, status in (("Out of limit", OUT), ("Missing", MISSING), ("Differs from design", DIFFERS), ("Stale records", STALE), ("Not compared", NOT_COMPARED)):  # fmt: skip
        lines = [ln for ln in rep.lines if ln.status == status]
        if not lines:
            continue
        out += ["", f"## {title}", "", "| Harness | Item | Value | Actual | Designed or limit | Margin | Note |", "| --- | --- | --- | ---: | ---: | ---: | --- |"]  # fmt: skip
        for ln in lines:
            out.append(f"| {ln.harness_id} | {ln.kind} {ln.subject} | {ln.field} | {_cell(ln.actual)} | {_cell(ln.designed)} | {_cell(ln.margin)} | {_md(ln.text)} |")  # fmt: skip
    notes = [r for r in sorted(project.asbuilt.values(), key=lambda x: x.id) if r.nonconformance or r.notes]  # fmt: skip
    if notes:
        out += ["", "## Notes and non-conformances", "", "| Record | Notes | Non-conformance |", "| --- | --- | --- |"]  # fmt: skip
        out += [f"| {r.id} | {_md(r.notes)} | {_md(r.nonconformance)} |" for r in notes]
    return "\n".join(out) + "\n"


def _md(text: str) -> str:
    return " ".join(text.split()).replace("|", "\\|")


def asbuilt_fingerprint(project: Project) -> str:
    """A short hash of the records, for the manifest of the outputs ('' while there are none): the
    outputs are out of date when the records changed, though the design did not."""
    if not project.asbuilt:
        return ""
    import hashlib
    import json

    data = [r.model_dump(mode="json") for r in sorted(project.asbuilt.values(), key=lambda x: x.id)]
    return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()


# ---- the sheet a technician fills in ------------------------------------------------------------

TEMPLATE_HEADER = [
    "Kind", "Harness", "Item", "Description", "Designed length (m)", "Designed strip A (mm)",
    "Designed strip B (mm)", "Limit",
    "Serial number", "Lot", "Cut length (m)", "Strip A (mm)", "Strip B (mm)", "Crimp tool",
    "Crimp tool calibration ID", "Built by", "Inspected by", "Test type", "Tested", "Result",
    "Continuity (ohm)", "Isolation (Mohm)", "Test voltage (V)", "Notes", "Non-conformance",
]  # fmt: skip
# the columns that describe the design and are not read back
REFERENCE_FIELDS = ("Description", "Designed length (m)", "Designed strip A (mm)", "Designed strip B (mm)", "Limit")  # fmt: skip
# the as-built columns, in the order of the template, and the field of the record each one is
_FIELD_OF = {
    "Serial number": "serial_numbers", "Lot": "lot", "Cut length (m)": "cut_length_m",
    "Strip A (mm)": "strip_a_mm", "Strip B (mm)": "strip_b_mm", "Crimp tool": "crimp_tool",
    "Crimp tool calibration ID": "crimp_tool_calibration_id", "Built by": "built_by",
    "Inspected by": "inspected_by", "Test type": "test_type", "Tested": "tested",
    "Result": "result", "Continuity (ohm)": "continuity_ohm", "Isolation (Mohm)": "isolation_mohm",
    "Test voltage (V)": "test_voltage_v", "Notes": "notes", "Non-conformance": "nonconformance",
}  # fmt: skip


def _shown(rec: AsBuiltRecord | None, name: str) -> str:
    """What the record holds in the column `name`, as a cell ('' when nothing)."""
    if rec is None:
        return ""
    v = getattr(rec, _FIELD_OF[name])
    if isinstance(v, list):
        return "; ".join(v)
    return "" if v in (None, "") else _cell(v)


def _row(
    kind: str, hid: str, item: str, desc: str, designed: Sequence[str], rec: AsBuiltRecord | None,
    fixed: Mapping[str, str] | None = None,
) -> list[str]:  # fmt: skip
    """One row of the sheet: the key, the designed values, then what is recorded (or, for the
    columns that identify a test, what the design says, so the sheet is read back safely)."""
    head = [kind, hid, item, desc, *designed]
    cells = []
    for name in TEMPLATE_HEADER[len(head) :]:
        if name in _FIELD_OF:
            cells.append(_shown(rec, name) or (fixed or {}).get(name, ""))
        else:
            cells.append("")
    return head + cells


def template_rows(project: Project, harness_id: str | None = None) -> Table:
    """The sheet for the technician: one row for each thing that can be recorded, the designed
    values filled in and the as-built columns empty (or holding what is recorded already, so the
    sheet can be filled in again and imported again). All harnesses, or one."""
    rows: Table = [list(TEMPLATE_HEADER)]
    for hid in sorted(project.harnesses) if harness_id is None else [harness_id]:
        h = project.harnesses.get(hid)
        if h is None:
            raise ImportError_(f"Harness '{hid}' does not exist.")
        rows.append(_row("harness", hid, hid, h.name, ["", "", "", ""], _get(project, "harness", hid, hid)))  # fmt: skip
        for pid in _parts_of(h):
            rows.append(_row("part", hid, pid, "lot of this part in the harness", ["", "", "", ""], _get(project, "part", hid, pid)))  # fmt: skip
        for w in sorted(h.wires, key=lambda x: x.id):
            designed = [tables.data_num(wire_length(h, w)), tables.data_num(w.strip_a_mm), tables.data_num(w.strip_b_mm), ""]  # fmt: skip
            rows.append(_row("wire", hid, w.id, f"{w.from_connector}.{w.from_pin} to {w.to_connector}.{w.to_pin}", designed, _get(project, "wire", hid, w.id)))  # fmt: skip
        for c in sorted(h.connectors, key=lambda x: x.id):
            rows.append(_row("connector", hid, c.id, c.part_id, ["", "", "", ""], _get(project, "connector", hid, c.id)))  # fmt: skip
        for pin in _crimped_pins(h):
            rows.append(_row("pin", hid, pin, "crimped pin in use", ["", "", "", ""], _get(project, "pin", hid, pin)))  # fmt: skip
        for tid, t in _tests(project, h).items():
            limit = t[5] + (f" at {t[6]}" if t[6] else "")
            rows.append(_row("test", hid, tid, f"{t[2]} to {t[3]}", ["", "", "", limit], _get(project, "test", hid, tid), {"Test type": t[1], "Tested": t[7]}))  # fmt: skip
    return rows


# ---- reading the sheet back ---------------------------------------------------------------------

# the headings that mean a field (lower case, letters and digits only, the unit in brackets left out)
_ALIASES: dict[str, tuple[str, ...]] = {
    "kind": ("kind",),
    "harness": ("harness", "harnessid"),
    "item": ("item", "subject", "id"),
    "serial_numbers": ("serialnumber", "serialnumbers", "serial", "sn"),
    "lot": ("lot", "lotbatch", "batch", "lotnumber"),
    "cut_length_m": ("cutlength", "actualcutlength"),
    "strip_a_mm": ("stripa",),
    "strip_b_mm": ("stripb",),
    "crimp_tool": ("crimptool", "tool"),
    "crimp_tool_calibration_id": (
        "crimptoolcalibrationid",
        "toolcalibrationid",
        "calibrationid",
        "calibration",
    ),  # fmt: skip
    "built_by": ("builtby", "builder"),
    "inspected_by": ("inspectedby", "inspector"),
    "test_type": ("testtype",),
    "tested": ("tested",),
    "result": ("result",),
    "continuity_ohm": ("continuity", "continuityresistance"),
    "isolation_mohm": ("isolation", "insulation", "isolationresistance"),
    "test_voltage_v": ("testvoltage", "voltage"),
    "notes": ("notes", "note"),
    "nonconformance": ("nonconformance", "ncr", "nonconformances"),
}
_REFERENCE = ("description", "designedlength", "designedstripa", "designedstripb", "limit", "designed")  # fmt: skip
# field -> (the unit it is stored in, the units a heading may say and their factor to the stored one)
_UNITS: dict[str, tuple[str, dict[str, float]]] = {
    "cut_length_m": ("m", {u: f for u, f in LENGTH_UNITS_M.items()}),
    "strip_a_mm": ("mm", {u: f / LENGTH_UNITS_M["mm"] for u, f in LENGTH_UNITS_M.items()}),
    "strip_b_mm": ("mm", {u: f / LENGTH_UNITS_M["mm"] for u, f in LENGTH_UNITS_M.items()}),
    "continuity_ohm": ("ohm", {"ohm": 1.0, "mOhm": 1e-3}),
    "isolation_mohm": ("Mohm", {"Mohm": 1.0, "Gohm": 1e3}),
    "test_voltage_v": ("V", {"V": 1.0, "kV": 1e3}),
}
_NUMBERS = frozenset(_UNITS)
_WORDS = {  # the name of a field in the echo, with its unit
    "cut_length_m": "cut length (m)", "strip_a_mm": "strip A (mm)", "strip_b_mm": "strip B (mm)",
    "continuity_ohm": "continuity (ohm)", "isolation_mohm": "isolation (Mohm)",
    "test_voltage_v": "test voltage (V)", "serial_numbers": "serial number",
    "crimp_tool_calibration_id": "crimp tool calibration ID",
}  # fmt: skip
_PAREN = re.compile(r"\(([^)]*)\)")
KIND_TEXT = ", ".join(AS_BUILT_KINDS)


def _norm(text: str) -> str:
    return "".join(ch for ch in _PAREN.sub("", text).lower() if ch.isalnum())


@dataclass
class AsBuiltRow:
    row_number: int
    ok: bool
    message: str
    target: str = ""  # kind:harness:item
    action: str = ""  # added, changed or unchanged


@dataclass
class AsBuiltPlan:
    rows: list[AsBuiltRow] = field(default_factory=list)
    ops: list[Op] = field(default_factory=list)
    mapping: dict[str, int] = field(default_factory=dict)
    units: dict[str, str] = field(default_factory=dict)  # field -> the unit its column was read in
    skipped: int = 0  # rows with nothing recorded in them (the sheet as it was handed out)
    # (row, field, the cell as written, unit it was read in, the value as stored with its unit)
    conversions: list[tuple[int, str, str, str, str]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def bad_count(self) -> int:
        return sum(not r.ok for r in self.rows)

    def counts(self) -> dict[str, int]:
        out = {"added": 0, "changed": 0, "unchanged": 0, "refused": self.bad_count, "skipped": self.skipped}  # fmt: skip
        for r in self.rows:
            if r.ok:
                out[r.action] += 1
        return out


def _mapping(header: list[str]) -> tuple[dict[str, int], dict[str, str], list[int]]:
    """Which column is which field, the unit each number column says, and the columns that only
    describe the design (read as nothing and not warned about)."""
    norm = [_norm(h) for h in header]
    mapping: dict[str, int] = {}
    units: dict[str, str] = {}
    for key, aliases in _ALIASES.items():
        hit = next((i for i, n in enumerate(norm) if n in aliases and i not in mapping.values()), None)  # fmt: skip
        if hit is not None:
            mapping[key] = hit
            said = _PAREN.search(header[hit])
            if key in _NUMBERS and said and said.group(1).strip():
                units[key] = said.group(1).strip()
    skip = [i for i, n in enumerate(norm) if n in _REFERENCE]
    return mapping, units, skip


def _number(text: str, key: str, unit: str | None) -> tuple[float, str | None]:
    """The number of a cell in the stored unit, and a note of how it was converted (a decimal
    comma, a unit other than the stored one), else None."""
    stored, factors = _UNITS[key]
    said = unit or stored
    if said not in factors:
        raise ValueError(f"the unit '{said}' is not one of {', '.join(factors)}")
    plain = text.strip()
    comma = "," in plain and "." not in plain
    try:
        value = float(plain.replace(",", ".") if comma else plain)
    except ValueError:
        raise ValueError(f"'{text.strip()}' is not a number") from None
    if value != value or abs(value) == float("inf"):
        raise ValueError(f"'{text.strip()}' is not a number")
    converted = round(value * factors[said] / factors[stored], 9) if said != stored else value
    note = None
    if said != stored or comma:
        note = f"{number_text(converted)} {stored}"
    return converted, note


def plan_asbuilt_import(project: Project, table: Table) -> AsBuiltPlan:
    """One result per data row of `table` (the first row is the heading row) and the operations of
    the rows that are accepted. The columns are found by their headings, the unit of a number
    column is the one in its heading (the stored unit when it says none), an empty cell leaves what
    is recorded as it is (it never clears), and a row about something the design does not have is
    refused with the reason. Nothing is invented: a value that cannot be read refuses its row."""
    header = table[0] if table else []
    mapping, units, skip = _mapping(header)
    missing = [k for k in ("kind", "harness", "item") if k not in mapping]
    if missing:
        raise ImportError_(
            f"The column headings are not those of an as-built sheet: {', '.join(missing)} "
            f"{'is' if len(missing) == 1 else 'are'} missing. Write the sheet with "
            "`harness-design-studio export-asbuilt` and fill it in."
        )
    plan = AsBuiltPlan(mapping=mapping, units=units)
    for key, said in sorted(units.items()):
        if said not in _UNITS[key][1]:
            plan.warnings.append(f"The heading unit '{said}' of {key} is not one of {', '.join(_UNITS[key][1])}; it is read in {_UNITS[key][0]}.")  # fmt: skip
    pending: dict[str, AsBuiltRecord] = {}
    for n, row in enumerate(table[1:], start=2):
        if not any(c.strip() for c in row):
            continue

        def cell(key: str, row: list[str] = row) -> str:
            i = mapping.get(key)
            return row[i].strip() if i is not None and i < len(row) else ""

        try:
            rid, rec, action, message = _read_row(project, pending, cell, units, plan, n)
        except ValueError as exc:
            plan.rows.append(AsBuiltRow(n, False, str(exc)))
            continue
        if rec is None:
            plan.skipped += 1
            continue
        pending[rid] = rec
        plan.rows.append(AsBuiltRow(n, True, message, rid, action))
    if plan.bad_count == 0:
        for rid, rec in sorted(pending.items()):
            if project.asbuilt.get(rid) != rec:
                plan.ops.append(Put("asbuilt", rec))
    return plan


def _check_subject(project: Project, kind: str, hid: str, item: str, cell: Callable[[str], str]) -> tuple[Harness, dict[str, str]]:  # fmt: skip
    """The harness, and for a test what the design says of it; ValueError when the design has no such thing."""
    h = project.harnesses.get(hid)
    if h is None:
        raise ValueError(f"Harness '{hid}' does not exist.")
    fixed: dict[str, str] = {}
    if kind == "harness" and item != hid:
        raise ValueError(f"The item of a harness row is the harness ID ({hid}), not '{item}'.")
    if kind == "part" and item not in _parts_of(h):
        raise ValueError(f"{item} is not a part of a wire or connector of {hid}.")
    if kind == "wire" and not any(w.id == item for w in h.wires):
        raise ValueError(f"'{item}' is not a wire of {hid}.")
    if kind == "connector" and not any(c.id == item for c in h.connectors):
        raise ValueError(f"'{item}' is not a connector of {hid}.")
    if kind == "pin" and not any(f"{c.id}.{p.id}" == item for c in h.connectors for p in c.pins):
        raise ValueError(f"'{item}' is not a pin (CONNECTOR.PIN) of {hid}.")
    if kind == "test":
        t = _tests(project, h).get(item)
        if t is None:
            raise ValueError(f"{hid} has no test {item} on its Tests sheet.")
        fixed = {"test_type": t[1], "tested": t[7]}
        for key in ("test_type", "tested"):
            if cell(key) and cell(key) != fixed[key]:
                raise ValueError(f"{item} is {t[1]} of {t[7]} in this project; the file says '{cell(key)}' for {key.replace('_', ' ')}. The test list changed: export the sheet again.")  # fmt: skip
    return h, fixed


def _read_row(
    project: Project, pending: dict[str, AsBuiltRecord], cell: Callable[[str], str],
    units: Mapping[str, str], plan: AsBuiltPlan, n: int,
) -> tuple[str, AsBuiltRecord | None, str, str]:  # fmt: skip
    kind = cell("kind").casefold()
    if kind not in AS_BUILT_KINDS:
        raise ValueError(f"The kind '{cell('kind')}' is not one of {KIND_TEXT}.")
    hid, item = cell("harness"), cell("item")
    if not hid or not item:
        raise ValueError("The harness or the item is empty.")
    _h, fixed = _check_subject(project, kind, hid, item, cell)
    rid = record_id(kind, hid, item)
    before = pending.get(rid) or project.asbuilt.get(rid)
    changes: dict[str, Any] = {}
    for key in _ALIASES:
        if key in ("kind", "harness", "item") or not cell(key):
            continue
        text = cell(key)
        try:
            if key in _NUMBERS:
                value, note = _number(text, key, units.get(key))
                changes[key] = value
                if note is not None:
                    plan.conversions.append((n, key, text, units.get(key) or _UNITS[key][0], note))
            elif key == "serial_numbers":
                changes[key] = [clean(s, 200) for s in re.split(r"[;\n]", text) if s.strip()]
            elif key == "result":
                word = text.casefold()
                if word not in ("pass", "fail"):
                    raise ValueError(f"'{text}' is not pass or fail")
                changes[key] = word
            else:
                changes[key] = clean(text, 5000 if key in ("notes", "nonconformance") else 200)
        except ValueError as exc:
            raise ValueError(f"{_WORDS.get(key, key.replace('_', ' '))}: {exc}.") from None
    for key, given in fixed.items():
        if key not in changes and not (before and getattr(before, key)):
            changes[key] = given
    if not changes or all(k in fixed for k in changes) and before is None:
        return rid, None, "", ""
    base = before or AsBuiltRecord(id=rid, kind=kind, harness_id=hid, subject=item)  # type: ignore[arg-type]
    try:
        rec = evolve(base, **changes)
    except ValidationError as exc:
        first = exc.errors()[0]
        loc = ".".join(str(p) for p in first.get("loc", ())) or "value"
        raise ValueError(
            f"{_WORDS.get(loc, loc.replace('_', ' '))}: {first.get('msg', 'not acceptable')}."
        ) from None
    if rec == project.asbuilt.get(rid):
        return rid, rec, "unchanged", f"{kind} {item}: as recorded"
    action = "changed" if rid in project.asbuilt or rid in pending else "added"
    said = (
        ", ".join(_WORDS.get(k, k.replace("_", " ")) for k in changes if k not in fixed)
        or "identified"
    )
    return rid, rec, action, f"{kind} {item}: {said}"


def asbuilt_import_report(
    path: Any, root: Any, table: Table, plan: AsBuiltPlan, *, sheet: str | None = None
) -> ImportReport:
    """What the import read, dropped and converted, as the other imports echo it (`imports/records.json`)."""
    mapping = dict(plan.mapping)
    report = table_report("asbuilt", path, root, table, mapping, sheet=sheet)
    _m, _u, skip = _mapping(table[0] if table else [])
    report.read_columns(table[0] if table else [], mapping, skip)
    for r in plan.rows:
        if not r.ok:
            report.drop(r.row_number, r.message)
    ok_rows = {r.row_number for r in plan.rows if r.ok}
    for row, key, text, said, stored in plan.conversions:
        if row in ok_rows:
            report.convert(row=row, field=key, read=text, unit=said, stored=stored)
    if plan.skipped:
        report.notes.append(
            f"{plan.skipped} row(s) had no as-built value in them and were left out."
        )
    report.notes += plan.warnings
    return report


@dataclass
class AsBuiltImport:
    """Everything an import of a sheet found out, before anything is changed."""

    table: Table
    sheet: str | None
    plan: AsBuiltPlan
    report: ImportReport
    ops: list[Op]  # the records and the import record, as one undo step


@dataclass(frozen=True)
class AsBuiltImportResult:
    """What `import_asbuilt` did: the counts (added, changed, unchanged, refused, left out), one
    result for each row that held something, and the lines the command echoes."""

    dry_run: bool
    changed: bool
    counts: dict[str, int]
    rows: tuple[AsBuiltRow, ...]
    echo: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "dry_run": self.dry_run, "changed": self.changed, "counts": self.counts,
            "rows": [
                {"row": r.row_number, "ok": r.ok, "target": r.target, "action": r.action, "message": r.message}
                for r in self.rows
            ],
        }  # fmt: skip


def read_import(project: Project, path: Any, root: Any) -> AsBuiltImport:
    """Read the sheet at `path` (CSV, TSV, JSON or XLSX; the *About* sheet of a workbook the tool
    wrote is passed over), plan its rows, and make the import record. Nothing is changed. Raises
    `ImportError_` when the file cannot be read or is not an as-built sheet."""
    from harness_design_studio.core.import_record import record_ops
    from harness_design_studio.core.imports import read_table_sheet

    table, sheet = read_table_sheet(path, skip_sheets=("About",))
    if len(table) < 2:
        raise ImportError_("The file has no rows to import (headings and at least one row).")
    plan = plan_asbuilt_import(project, table)
    report = asbuilt_import_report(path, root, table, plan, sheet=sheet)
    ops = [*plan.ops, *record_ops(project, report.record())] if plan.bad_count == 0 else []
    return AsBuiltImport(table, sheet, plan, report, ops)


def template_bytes(project: Project, suffix: str, harness_id: str | None = None) -> bytes:
    """The sheet for the technician as a file: `.csv` (UTF-8, the stamp line first, which the
    importer skips) or `.xlsx`. The same project gives the same bytes."""
    from harness_design_studio.core.outputs.exports import xlsx_bytes
    from harness_design_studio.core.outputs.stamp import csv_bytes, stamp_of

    rows = template_rows(project, harness_id)
    stamp = stamp_of(project)
    if suffix.lower() == ".xlsx":
        return xlsx_bytes({"As-built": rows}, stamp)
    if suffix.lower() == ".csv":
        return csv_bytes(rows, stamp)
    raise ImportError_("The sheet is written as .csv or .xlsx.")


__all__ = [
    "ASBUILT_FILE",
    "AsBuiltImport",
    "AsBuiltImportResult",
    "REPORT_HEADER",
    "TEMPLATE_HEADER",
    "AsBuiltPlan",
    "AsBuiltReport",
    "HarnessStatus",
    "Line",
    "asbuilt_fingerprint",
    "asbuilt_import_report",
    "asbuilt_report",
    "harness_lines",
    "plan_asbuilt_import",
    "read_import",
    "report_markdown",
    "report_rows",
    "template_bytes",
    "template_rows",
]
