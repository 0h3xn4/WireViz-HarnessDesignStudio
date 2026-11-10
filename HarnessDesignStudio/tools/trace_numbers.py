# SPDX-FileCopyrightText: 2026 0h3xn4
# SPDX-License-Identifier: GPL-3.0-only
"""The trace test of 16 real numbers, repeated (D-191, S10).

The audit (`docs/transparency_audit.md`, section 8) traced 16 numbers of the `flatsat` and
`first-steps` examples back to their inputs by reading code, files and documents, and none took less
than 3 minutes. This tool does the same with **only what the tool itself offers**: `explain` (the
Python interface `api.explain` and `api.explain_finding` give what the command gives), `export-data`
and `settings --json`. For each number it

* asks `explain` for the derivation of the object (the equation, the inputs, the steps),
* checks that the resolution is complete: every input names its source, nothing says "unknown",
  every configuration key it names is a setting of `settings --json`, every assumption it rests on
  is listed there, and a value that is not set is named in what is missing,
* compares the number with the same number in the files of `export-data`, where there is one,
* and measures how long all of that took, which must be under a minute.

    python -m tools.trace_numbers            # trace the 16 numbers, print the table with seconds
    python -m tools.trace_numbers --update   # write docs/transparency_trace_results.md
    python -m tools.trace_numbers --check    # exit 1 when that file is not what the tool writes

The file has no timing: a time varies from run to run, and the file must be the same bytes for the
same tool. It says "< 60 s" for each number; the seconds go to the screen only.
"""

import argparse
import contextlib
import csv
import io
import json
import re
import shutil
import sys
import tempfile
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from harness_design_studio import api
from harness_design_studio.cli.main import main as cli_main
from harness_design_studio.core.derive import Derivation, render

TARGET = Path(__file__).resolve().parent.parent / "docs" / "transparency_trace_results.md"
LIMIT_SECONDS = 60.0  # the definition of done (a): any number traced in under a minute
FLATSAT = "flatsat"
TIGHT = "flatsat-derated"  # the flatsat with a temperature factor of 0.2 (a value `settings --set` accepts), so that a rule fires
FIRST_STEPS = "first-steps"
TIGHT_TEMPERATURE_FACTOR = 0.2


@dataclass(frozen=True)
class Want:
    """What a resolution must contain: the kind of derivation, a part of its subject and, where the
    number is a value, the value (compared to 9 decimals) or, for a text, a part of the text."""

    kind: str
    subject: str = ""
    value: float | None = None
    text: str = ""


@dataclass(frozen=True)
class Cross:
    """The same number in the files of `export-data`: a table, the row (column -> text) and the
    column that holds it; `against` names what of the derivation it is compared with."""

    table: str
    row: tuple[tuple[str, str], ...]
    column: str
    against: str = "value"  # "value", or "check.actual", "check.limit", "check.margin"
    want: Want | None = None  # the derivation it is compared with (default: the first one wanted)


@dataclass(frozen=True)
class Row:
    n: int
    persona: str
    number: str  # the number or decision, in words
    audit_minutes: str  # what the audit took (the original table), for the comparison
    project: str  # FLATSAT, TIGHT or FIRST_STEPS
    command: str  # the command of the tool that gives it, with DIR for the project folder
    objects: tuple[str, ...] = ()  # the objects asked of `explain`
    finding: str = ""  # or a finding ID asked of `explain_finding`
    wants: tuple[Want, ...] = ()
    cross: tuple[Cross, ...] = ()
    settings: tuple[str, ...] = ()  # settings that `settings --json` must list for this number
    definitions: tuple[str, ...] = ()  # definitions it rests on, listed by `settings --json`
    pending: bool = False  # the number is "not set": the resolution names what is missing


# The 16 numbers of the audit (section 8), found again on the packaged examples. Where the audit's
# value has moved with the example, the row names the equivalent number.
ROWS: tuple[Row, ...] = (
    Row(
        1,
        "ELEC",
        "Gauge and derating factor of wire W001-001 (limit 1.08 A = 2 A x 0.6 x 0.9)",
        "12 (GUI) or 20 (files only)",
        FLATSAT,
        "harness-design-studio explain DIR W001-001",
        ("W001-001",),
        "",
        (Want("wire-current-limit", "W001-001", 1.08), Want("wire-voltage-drop", "W001-001")),
        (
            Cross("wire_sizing", (("Wire", "W001-001"),), "Derated current limit (A)"),
            Cross(
                "wire_sizing", (("Wire", "W001-001"),), "Bundle factor K", "input:Bundle factor K"
            ),
            Cross(
                "wire_sizing",
                (("Wire", "W001-001"),),
                "Gauge (AWG)",
                "input:Gauge",
                Want("wire-voltage-drop", "W001-001"),
            ),
        ),
        ("derating.ampacity_a_by_awg", "derating.bundle_derating", "derating.temperature_derating"),
        ("D-AWG", "D-LIMIT-TOLERANCE"),
    ),  # fmt: skip
    Row(
        2,
        "ELEC",
        "Voltage drop of wire W001-001 (0.458359 V)",
        "25",
        FLATSAT,
        "harness-design-studio explain DIR W001-001",
        ("W001-001",),
        "",
        (Want("wire-voltage-drop", "W001-001", 0.4583591010499786),),
        (Cross("wire_sizing", (("Wire", "W001-001"),), "Voltage drop (V)"),),
        (
            "generation.conductor_resistivity_ohm_m",
            "derating.max_voltage_drop_v",
            "model.return_path_conductors",
        ),
        ("D-AWG",),
    ),  # fmt: skip
    Row(
        3,
        "AIT",
        "Cut length of wire W001-001 (3.45 m = 3.25 m + 2 x 0.1 m)",
        "20",
        FLATSAT,
        "harness-design-studio explain DIR W001-001",
        ("W001-001",),
        "",
        (Want("wire-length", "W001-001", 3.45),),
        (
            Cross("lengths", (("Wire", "W001-001"),), "Length (m)"),
            Cross(
                "lengths",
                (("Wire", "W001-001"),),
                "Path through the segments (m)",
                "step:Path through the segments",
            ),
        ),
        ("generation.service_loop_m", "model.service_loops_per_wire"),
        (),
    ),  # fmt: skip
    Row(
        4,
        "SYS AIT",
        "Bill of materials metres of the wire part EX-WIRE-SINGLE (165.2 m)",
        "15",
        FLATSAT,
        "harness-design-studio explain DIR EX-WIRE-SINGLE",
        ("EX-WIRE-SINGLE",),
        "",
        (Want("part-bom", "EX-WIRE-SINGLE", 165.2),),
        (Cross("bom", (("Part", "EX-WIRE-SINGLE"),), "Quantity"),),
        (),
        (),
    ),  # fmt: skip
    Row(
        5,
        "SYS",
        "Mass of harness W001 (456.4 g, 502.04 g with the margin)",
        "15",
        FLATSAT,
        "harness-design-studio explain DIR W001",
        ("W001",),
        "",
        (Want("harness-mass", "W001", 456.4),),
        (
            Cross("mass", (("Harness", "W001"),), "Mass of what is known (g)"),
            Cross("mass", (("Harness", "W001"),), "Mass with margin (g)", "step:With margin"),
        ),
        ("generation.mass_margin_fraction", "model.mass_model"),
        (),
    ),  # fmt: skip
    Row(
        6,
        "SYS",
        "Why interfaces IF-010 to IF-018 share harness W001",
        "8",
        FLATSAT,
        "harness-design-studio explain DIR IF-010",
        ("IF-010",),
        "",
        (Want("segmentation", "W001", None, "aocs to aocs"),),
        (
            Cross(
                "segmentation_groups",
                (("Harness", "W001"),),
                "Interface IDs",
                "text:IF-010;IF-011;IF-012;IF-013;IF-014;IF-015;IF-016;IF-017;IF-018",
            ),
        ),
        ("segmentation.mode",),
        (),
    ),  # fmt: skip
    Row(
        7,
        "SYS ELEC",
        "Why PWR of IF-010 is on pin 1 of PDU2-J02",
        "10",
        FLATSAT,
        "harness-design-studio explain DIR PDU2-J02.1",
        ("PDU2-J02.1",),
        "",
        (Want("pin-allocation", "PDU2-J02", None, "PWR of IF-010 on pin 1"),),
        (Cross("pin_allocation", (("Connector", "PDU2-J02"), ("Pin", "1")), "Signal", "text:PWR"),),
        ("model.pin_allocation_categories",),
        (),
    ),  # fmt: skip
    Row(
        8,
        "SYS",
        "Why connector PDU2-J02 is the connector of IF-010",
        "10",
        FLATSAT,
        "harness-design-studio explain DIR IF-010",
        ("IF-010",),
        "",
        (Want("connector-choice", "PDU2-J02", None, "EX-MICROD-9-F"),),
        (),
        (),
        (),
    ),  # fmt: skip
    Row(
        9,
        "ELEC",
        "A current finding: actual current, limit and margin (the flatsat with a temperature factor of 0.2)",
        "8",
        TIGHT,
        "api.explain_finding(DIR, 'current-over-wire.W001-001') (the Explain button of the finding)",
        (),
        "current-over-wire.W001-001",
        (Want("wire-current-limit", "W001-001", 0.24),),
        (
            Cross("findings", (("Finding", "current-over-wire.W001-001"),), "Limit", "check.limit"),
            Cross(
                "findings", (("Finding", "current-over-wire.W001-001"),), "Actual", "check.actual"
            ),
            Cross(
                "findings", (("Finding", "current-over-wire.W001-001"),), "Margin", "check.margin"
            ),
        ),
        ("derating.temperature_derating",),
        ("D-LIMIT-TOLERANCE",),
    ),  # fmt: skip
    Row(
        10,
        "ELEC",
        "The EMC classes and the rule for them (none set in the example)",
        "5",
        FLATSAT,
        "harness-design-studio explain DIR IF-010; harness-design-studio settings DIR --json",
        ("IF-010",),
        "",
        (Want("segmentation", "W001", None, "class"),),
        (),
        (
            "emc.conflicting_class_pairs",
            "emc.same_class_one_bundle",
            "segregation.category_pairs_to_separate",
        ),
        (),
    ),  # fmt: skip
    Row(
        11,
        "ELEC",
        "Shield termination of shield group W001-S1",
        "10",
        FLATSAT,
        "harness-design-studio explain DIR W001-S1",
        ("W001-S1",),
        "",
        (Want("shield-group", "W001-S1", None, "end A backshell_360, end B floating"),),
        (),
        ("generation.shield_end_a", "generation.shield_end_b"),
        (),
    ),  # fmt: skip
    Row(
        12,
        "AIT",
        "Strip length, contact and crimp: 18 wires of W001 have no strip length, and the contact limit of IF-001 at GPSU1-J01 is 6 A",
        "3",
        FLATSAT,
        "harness-design-studio explain DIR W001; harness-design-studio explain DIR IF-001.GPSU1-J01",
        ("W001", "IF-001.GPSU1-J01"),
        "",
        (
            Want("readiness-check", "Wires without strip lengths", 18.0),
            Want("contact-current", "GPSU1-J01", 6.0),
        ),
        (
            Cross(
                "readiness",
                (("Harness", "W001"), ("Check", "Wires without strip lengths")),
                "Open",
                "value",
                Want("readiness-check", "Wires without strip lengths"),
            ),
        ),
        ("derating.contact_current_factor", "derating.contact_rating_key"),
        (),
    ),  # fmt: skip
    Row(
        13,
        "AIT",
        "Label text and colour of wire W001-001",
        "8",
        FLATSAT,
        "harness-design-studio explain DIR W001-001",
        ("W001-001",),
        "",
        (
            Want("wire-label", "W001-001", None, "W001-001 PWR to W001-P11.1"),
            Want("wire-colour", "W001-001", None, "red"),
        ),
        (),
        ("generation.wire_colour_by_signal",),
        (),
    ),  # fmt: skip
    Row(
        14,
        "AIT",
        "Test limits of harness W001: 1 ohm, 100 Mohm, 500 V",
        "4",
        FLATSAT,
        "harness-design-studio explain DIR W001",
        ("W001",),
        "",
        (
            Want("test-limit", "continuity limit", 1.0),
            Want("test-limit", "isolation limit", 100.0),
            Want("test-limit", "isolation voltage limit", 500.0),
        ),
        (
            Cross(
                "test_limits",
                (("Test", "T001"), ("Harness", "W001")),
                "Limit",
                "value",
                Want("test-limit", "continuity limit"),
            ),
        ),
        (
            "generation.test_continuity_max_ohm",
            "generation.test_isolation_min_mohm",
            "generation.test_isolation_voltage_v",
        ),
        (),
    ),  # fmt: skip
    Row(
        15,
        "AIT SYS",
        "Ready to build, harness W001",
        "5",
        FLATSAT,
        "harness-design-studio explain DIR W001",
        ("W001",),
        "",
        (Want("readiness", "W001", None, "yes"),),
        (
            Cross(
                "readiness",
                (("Harness", "W001"), ("Check", "Wires without a length")),
                "Ready to build",
                "text:yes",
            ),
        ),
        ("model.readiness_blocking",),
        (),
    ),  # fmt: skip
    Row(
        16,
        "SYS",
        "A gauge that is pending and a mass of 0 g in first-steps",
        "3",
        FIRST_STEPS,
        "harness-design-studio explain DIR W001-001; harness-design-studio explain DIR W001",
        ("W001-001", "W001"),
        "",
        (Want("wire-current-limit", "W001-001"), Want("harness-mass", "W001", 0.0)),
        (),
        ("derating.ampacity_a_by_awg", "derating.temperature_derating"),
        (),
        True,
    ),  # fmt: skip
)

_CONFIG = re.compile(r"config/(\w+)\.json: (\w+)")
_ID = re.compile(r"\b[A-Z][A-Z0-9]*-[A-Z0-9-]+\b")


class Session:
    """One project folder and what the public surfaces say about it, each asked once."""

    def __init__(self, folder: Path) -> None:
        self.folder = folder
        self._project: api.Project | None = None
        self._settings: dict[str, Any] | None = None
        self._tables: dict[str, list[dict[str, str]]] | None = None
        self._derivations: dict[str, list[Derivation]] = {}

    @property
    def project(self) -> api.Project:
        if self._project is None:
            self._project = api.load_project(self.folder)
        return self._project

    def explain(self, obj: str) -> list[Derivation]:
        if obj not in self._derivations:
            self._derivations[obj] = api.explain(self.project, obj)
        return self._derivations[obj]

    def explain_finding(self, finding: str) -> list[Derivation]:
        return api.explain_finding(self.project, finding)

    def settings(self) -> dict[str, Any]:
        """`settings DIR --json`, read as the command prints it."""
        if self._settings is None:
            self._settings = json.loads(command("settings", str(self.folder), "--json"))
        return self._settings

    def table(self, name: str) -> list[dict[str, str]]:
        """A table of `export-data`, read from its CSV file."""
        if self._tables is None:
            self._tables = {}
            with tempfile.TemporaryDirectory(prefix="trace-data-") as tmp:
                api.export_data(self.project, tmp)
                for path in sorted(Path(tmp).glob("*.csv")):
                    with path.open(newline="", encoding="utf-8") as handle:
                        self._tables[path.stem] = list(csv.DictReader(handle))
        return self._tables[name]


def command(*argv: str) -> str:
    """Run a command of the tool in this process and return what it printed."""
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = cli_main(list(argv))
    if code != 0:
        raise RuntimeError(
            f"harness-design-studio {' '.join(argv[:2])} ended with exit code {code}"
        )
    return out.getvalue()


def make_projects(base: Path) -> dict[str, Path]:
    """The three projects the numbers are traced on, made with the tool's own commands."""
    made = {FLATSAT: base / FLATSAT, FIRST_STEPS: base / FIRST_STEPS, TIGHT: base / TIGHT}
    api.create_project(made[FLATSAT], FLATSAT)
    api.create_project(made[FIRST_STEPS], FIRST_STEPS)
    if not api.generate(made[FIRST_STEPS]).ok:
        raise RuntimeError("first-steps did not generate")
    shutil.copytree(made[FLATSAT], made[TIGHT])
    command(
        "settings",
        str(made[TIGHT]),
        "--set",
        f"derating.temperature_derating={TIGHT_TEMPERATURE_FACTOR}",
    )
    return made


# ---- resolving one number --------------------------------------------------------------------------


@dataclass
class Resolution:
    row: Row
    problems: list[str] = field(default_factory=list)
    resolved: list[str] = field(default_factory=list)  # "kind subject = value", for the table
    inputs: list[tuple[str, str, str]] = field(
        default_factory=list
    )  # name, source, class of source
    assumptions: list[str] = field(default_factory=list)
    seconds: float = 0.0

    @property
    def complete(self) -> bool:
        return not self.problems


def source_class(source: str) -> str:
    """Where an input comes from, in five words: the configuration, the parts library, a value a
    person typed, the design (the model: a wire, an interface, a connector, a segment), or a
    derived number."""
    if source.startswith("config/"):
        return "configuration"
    low = source.lower()
    if (
        "parts library" in low
        or "wire part" in low
        or "connector part" in low
        or low.startswith("part ")
    ):
        return "library"
    if "typed by" in low:
        return "typed"
    if "see the derivation" in low or "derived" in low:
        return "derived"
    return "design"


def _check_input(res: Resolution, d: Derivation, settings_ids: set[str], files: set[str]) -> None:
    for i in d.inputs:
        where = f"{d.id} {d.subject}: input '{i.name}'"
        if not i.source or not i.source.strip():
            res.problems.append(f"{where} has no source")
            continue
        if "unknown" in i.source.lower() or "unknown" in i.name.lower():
            res.problems.append(f"{where} says unknown")
        for file, key in _CONFIG.findall(i.source):
            if f"{file}.{key}" not in settings_ids:
                res.problems.append(f"{where}: {file}.{key} is not a setting of `settings --json`")
        res.inputs.append((i.name, i.source, source_class(i.source)))
    for item in d.missing:
        if not item.strip():
            res.problems.append(f"{d.id} {d.subject}: an empty entry in what is missing")
        for word in re.findall(r"\b([a-z]+)\.([a-z_]+)\b", item):
            if word[0] in files and f"{word[0]}.{word[1]}" not in settings_ids:
                res.problems.append(f"{d.id}: missing '{word[0]}.{word[1]}' is not a setting")


def _find(found: list[Derivation], want: Want) -> Derivation | None:
    for d in found:
        if d.id != want.kind or want.subject not in d.subject + " " + d.quantity:
            continue
        if want.text and want.text not in (d.text or "") + " " + d.subject + " " + render(d):
            continue
        if want.value is not None and (d.value is None or abs(d.value - want.value) > 1e-9):
            continue
        return d
    return None


def _cross(res: Resolution, session: Session, c: Cross, found: list[Derivation], row: Row) -> None:
    rows = [r for r in session.table(c.table) if all(r.get(k) == v for k, v in c.row)]
    if len(rows) != 1:
        res.problems.append(f"export-data {c.table}: {len(rows)} rows for {dict(c.row)}")
        return
    cell = rows[0].get(c.column)
    if cell is None:
        res.problems.append(f"export-data {c.table} has no column {c.column}")
        return
    target = _find(found, c.want or row.wants[0])
    if target is None:
        res.problems.append(f"no derivation to compare with {c.table}.{c.column}")
        return
    how, _, rest = c.against.partition(":")
    ok = False
    label = c.against
    try:
        if how == "text":
            ok = cell == rest
        elif how == "step":
            steps = [s for s in target.steps if rest in s.label and s.value is not None]
            ok = bool(steps) and abs(steps[0].value - float(cell)) < 1e-9
        elif how == "input":
            values = [i.value for i in target.inputs if rest in i.name and i.value is not None]
            ok = bool(values) and abs(float(values[0]) - float(cell)) < 1e-9
        else:
            data = target.to_dict()
            value = (
                data["check"][how.partition(".")[2]] if how.startswith("check.") else target.value
            )
            ok = value is not None and abs(float(value) - float(cell)) < 1e-9
    except ValueError, TypeError:
        ok = False
    if not ok:
        res.problems.append(
            f"{c.table}.{c.column} = {cell!r} differs from the derivation ({label})"
        )


def resolve(row: Row, session: Session) -> Resolution:
    """Trace one number with the public surfaces only, and judge whether the trace is complete."""
    res = Resolution(row)
    start = time.perf_counter()
    try:
        settings = session.settings()
        settings_ids = {s["id"] for s in settings["settings"]}
        files = {sid.partition(".")[0] for sid in settings_ids}
        found: list[Derivation] = []
        for obj in row.objects:
            found.extend(session.explain(obj))
        if row.finding:
            found.extend(session.explain_finding(row.finding))
        if not found:
            res.problems.append("explain gave nothing")
        used: list[Derivation] = []
        for want in row.wants:
            d = _find(found, want)
            if d is None:
                res.problems.append(f"no derivation {want}")
                continue
            used.append(d)
            if not (d.equation and d.equation.strip()):
                res.problems.append(f"{d.id} {d.subject}: no equation")
            _check_input(res, d, settings_ids, files)
            ids = {a for a in d.assumptions}
            known = {a["id"] for a in settings["assumptions"]}
            for a in sorted(ids):
                if a not in known:
                    res.problems.append(f"{d.id}: assumption {a} is not listed by settings --json")
                elif a not in res.assumptions:
                    res.assumptions.append(a)
            text = f"{d.id} {d.subject} = " + (
                d.text
                if d.value is None and d.text
                else "not set"
                if d.value is None
                else f"{d.value:.9g} {d.unit}".strip()
            )  # noqa: E501
            res.resolved.append(text)
            if row.pending:
                if not d.missing:
                    res.problems.append(
                        f"{d.id} {d.subject}: expected a number that is not decided and says what is missing"
                    )  # noqa: E501
            elif d.missing:
                res.problems.append(f"{d.id} {d.subject}: is missing {d.missing}")
        for c in row.cross:
            _cross(res, session, c, found, row)
        listed = {s["id"]: s for s in settings["settings"]}
        for sid in row.settings:
            if sid not in listed:
                res.problems.append(f"settings --json does not list {sid}")
        known_defs = {d["id"] for d in settings["definitions"]}
        for did in row.definitions:
            if did not in known_defs:
                res.problems.append(f"settings --json does not list the definition {did}")
        if row.finding:
            check = next((d.check for d in used if d.check is not None), None)
            if check is None or check.passes:
                res.problems.append(
                    "the finding has no failing check with actual, limit and margin"
                )
        unresolved = [a for d in used for a in d.assumptions if not a]
        if unresolved:
            res.problems.append("an assumption without an ID")
    except Exception as exc:  # a trace that raises is a trace that failed
        res.problems.append(f"{type(exc).__name__}: {exc}")
    res.seconds = time.perf_counter() - start
    return res


def trace_all(base: Path, only: Callable[[Row], bool] | None = None) -> list[Resolution]:
    folders = make_projects(base)
    # one new session for each number: nothing is carried over from the number before, so the time
    # of a row is what it costs to trace that number from the project folder
    return [resolve(r, Session(folders[r.project])) for r in ROWS if only is None or only(r)]


# ---- the page ----------------------------------------------------------------------------------


def _cell(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ")


def render_page(results: list[Resolution]) -> str:
    """The page, without a time: the numbers, the commands, what each resolved to and its inputs."""
    lines = [
        "# The trace of 16 numbers, repeated",
        "",
        "Generated by `python -m tools.trace_numbers --update`; do not edit by hand. Decision D-191, stage S10 of "
        "[the plan](transparency_plan.md).",
        "",
        "The [audit](transparency_audit.md#8-the-trace-test-16-real-numbers) traced 16 real numbers back to their inputs by reading code, "
        "files and documents, and no number took under 3 minutes. This page is the same test made with only what the tool offers: "
        "`explain` (or `api.explain`), `export-data` and `settings --json`. For each number the test checks that the answer is "
        "complete (an equation; every input with a source; every configuration key it names is a setting that `settings --json` "
        "lists; every assumption it rests on is listed there; what is not set is named), that the number equals the same number "
        "in the files of `export-data` where those have it, and that all of it took less than a minute "
        "(`tests/test_trace_16_numbers.py`). The seconds are not in this file, so that it stays the same bytes for the same tool; "
        "`python -m tools.trace_numbers` prints them.",
        "",
        "The numbers are those of the packaged examples with their example engineering values (`flatsat`, `first-steps`), "
        "which are not engineering data. Where the value of the audit has moved with the example, the row names the equivalent number.",
        "",
        "## Contents",
        "",
        "- [The numbers](#the-numbers)",
        "- [What each one resolved to](#what-each-one-resolved-to)",
        "- [What this does not show](#what-this-does-not-show)",
        "",
        "## The numbers",
        "",
        "| # | User | Number or decision | Command (DIR is the project folder) | Audit, minutes | Now |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for r in results:
        verdict = "< 60 s" if r.complete else "NOT COMPLETE"
        lines.append(
            f"| {r.row.n} | {r.row.persona} | {_cell(r.row.number)} | `{_cell(r.row.command)}` | "
            f"{r.row.audit_minutes} | {verdict} |"
        )
    lines += ["", "## What each one resolved to", ""]
    for r in results:
        lines.append(f"### {r.row.n}. {r.row.number}")
        lines.append("")
        lines.append("Resolved to: " + "; ".join(f"`{_cell(x)}`" for x in r.resolved) + ".")
        classes = sorted({c for _n, _s, c in r.inputs})
        lines.append("")
        lines.append(
            f"{len(r.inputs)} input(s), each with its source"
            + (f" ({', '.join(classes)})" if classes else "")
            + (f"; rests on {', '.join(r.assumptions)}" if r.assumptions else "")
            + (f"; definitions {', '.join(r.row.definitions)}" if r.row.definitions else "")
            + (f"; settings {', '.join(r.row.settings)}" if r.row.settings else "")
            + "."
        )
        if r.inputs:
            lines.append("")
            lines.append("| Input | Source |")
            lines.append("| --- | --- |")
            shown = list(dict.fromkeys((n, s) for n, s, _c in r.inputs))
            for name, source in shown[:12]:
                lines.append(f"| {_cell(name)} | {_cell(source)} |")
            if len(shown) > 12:
                lines.append(f"| and {len(shown) - 12} more | the same kinds of source |")
        if r.row.pending:
            lines += [
                "",
                "Nothing is decided here, and the tool says why: every missing value is named by its configuration key or object.",
            ]  # noqa: E501
        lines.append("")
    lines += [
        "## What this does not show",
        "",
        "- It shows that each number can be traced with the tool in under a minute, not that the number is right for a programme: "
        "the example values are placeholders and the tool records no standard for them unless the project names one.",
        "- The time is that of a machine running the tool in one process; a person reading the derivation takes longer than the tool takes to give it. "
        "The audit's minutes were a person's; these are the tool's seconds, and the claim is that no step needs the code, a file search or a document any more.",
        "- The *decision* of a gauge (why 24 and not 26) is made by Generate: the derivations show the limits of the gauge that is on the wire, "
        "not the search that chose it, which is described on the [wire sizing](models/wire-sizing.md) page.",
        "- Nobody has looked at the screen for this test: the Why tab shows the same derivations (`render`), and its pixels are not part of it.",
        "",
        "Next: [the final audit](transparency_final_audit.md), [the audit](transparency_audit.md), [the models](models/README.md)",
        "",
    ]
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(
        description="Trace the 16 numbers of the audit with the public surfaces of the tool."
    )
    ap.add_argument(
        "--update", action="store_true", help="write docs/transparency_trace_results.md"
    )
    ap.add_argument("--check", action="store_true", help="exit 1 when that file is not current")
    args = ap.parse_args(argv)
    with tempfile.TemporaryDirectory(prefix="trace-numbers-") as tmp:
        results = trace_all(Path(tmp))
    for r in results:
        state = "complete" if r.complete else "NOT COMPLETE"
        print(f"{r.row.n:>2}  {r.seconds:6.2f} s  {state:<12} {r.row.number}")
        for p in r.problems:
            print(f"      - {p}")
    total = sum(r.seconds for r in results)
    print(
        f"{len(results)} numbers traced in {total:.1f} s; the slowest took {max(r.seconds for r in results):.2f} s (limit {LIMIT_SECONDS:g} s each)"
    )  # noqa: E501
    page = render_page(results)
    if args.update:
        TARGET.write_text(page, encoding="utf-8", newline="\n")
        print(f"written {TARGET}")
    if args.check and (not TARGET.exists() or TARGET.read_text(encoding="utf-8") != page):
        print(
            "docs/transparency_trace_results.md is not current: run python -m tools.trace_numbers --update"
        )
        return 1
    bad = [r for r in results if not r.complete or r.seconds >= LIMIT_SECONDS]
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
