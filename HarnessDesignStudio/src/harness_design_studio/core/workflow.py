# SPDX-FileCopyrightText: 2026 0h3xn4
# SPDX-License-Identifier: GPL-3.0-only
"""The workflow of the tool, in one place: what each step consumes and produces (S9, R6).

    steps = STEPS                                   # the nine steps, what each uses and makes
    status = workflow_status(project, folder)       # where this project stands in each step

The page *Follow the workflow* (`docs/user-manual/follow-the-workflow.md`), the command `workflow`,
`api.get_workflow` and the *What this step uses and makes* disclosure of the Next step page all read
this module, so they cannot disagree. A test makes the page's table from `STEPS` and fails when
the page and the code differ, and when a step names a project file, a configuration file, an output
file, a table of `export-data` or a command that the tool does not have.

An **item** is a named thing: a project file or collection (`logical/units/<subsystem>.json`), a
configuration file, a file of the written outputs (`harnesses/<harness>/tests.csv`), a table of
`export-data` or a file the person names. `<name>` stands for the part of a name that changes. The
**intermediates** of a step are the results it makes on the way that a person can look at, and,
where the tool allows it, change: the sizing of a wire, the groups of the segmentation, the pin
allocation, the readiness checks, the derived lengths.

The status is worked out from the project and the outputs folder, never invented: a step is
*blocked* by the steps before it that are not done, *pending* while engineering values or build data
are missing, *stale* when what it made is older than the design, and *attention* when something
needs a person (a check failed, a result of the as-built records is out of its limit). Nothing
here says that a design is approved or compliant.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

from harness_design_studio.core import asbuilt, configcheck
from harness_design_studio.core.generation_status import generation_status
from harness_design_studio.core.model import Project

# the kinds of item
PROJECT: Final = "project"  # a file or collection of the project folder
CONFIG: Final = "config"  # a configuration file of the project (`config/<name>.json`)
OUTPUT: Final = "output"  # a file of the written outputs
DATA: Final = "data"  # a table of `export-data`
FILE: Final = "file"  # a file a person names (an import, a template)
KINDS: Final = (PROJECT, CONFIG, OUTPUT, DATA, FILE)


@dataclass(frozen=True)
class Item:
    kind: str
    name: str

    def text(self) -> str:
        return f"*{self.name}*" if self.kind == FILE else f"`{self.name}`"

    def to_dict(self) -> dict[str, str]:
        return {"kind": self.kind, "name": self.name}


@dataclass(frozen=True)
class Inspect:
    """An intermediate result of a step: what it is, how to look at it, and how to change it
    ("" while it can only be looked at)."""

    what: str
    how: str  # a command or a place of the program
    change: str = ""

    def to_dict(self) -> dict[str, str]:
        return {"what": self.what, "how": self.how, "change": self.change}


@dataclass(frozen=True)
class StepDef:
    key: str
    title: str
    does: str  # one sentence
    consumes: tuple[Item, ...]
    produces: tuple[Item, ...]
    command: str  # the command that does it, "" when it is done on screen or by editing
    screen: str  # where on screen
    inspect: tuple[Inspect, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key, "title": self.title, "does": self.does, "command": self.command,
            "screen": self.screen,
            "consumes": [i.to_dict() for i in self.consumes],
            "produces": [i.to_dict() for i in self.produces],
            "inspect": [i.to_dict() for i in self.inspect],
        }  # fmt: skip


def _p(name: str) -> Item:
    return Item(PROJECT, name)


def _c(name: str) -> Item:
    return Item(CONFIG, f"config/{name}.json")


def _o(name: str) -> Item:
    return Item(OUTPUT, name)


def _d(name: str) -> Item:
    return Item(DATA, name)


STEPS: Final[tuple[StepDef, ...]] = (
    StepDef(
        "devices", "Define the devices",
        "Put the devices of the system in the project, each with its connectors and pins.",
        (_p("library/<category>.json"), Item(FILE, "a device or subsystem file (import-devices, import-subsystem)")),  # fmt: skip
        (_p("logical/units/<subsystem>.json"), _p("physical/connectors/<subsystem>.json")),
        "import-devices", "Devices; Edit > Add device",
        (Inspect("The pins of a device", "Devices tab", "edit them in the Devices tab"),),
    ),
    StepDef(
        "connect", "Connect them",
        "Say which devices talk to each other: interfaces of a type, or connections pin to pin.",
        (_p("logical/units/<subsystem>.json"), _p("logical/interface_types.json")),
        (_p("logical/interfaces/<subsystem>.json"), _p("logical/links.json")),
        "", "Model; Edit > Connect",
        (Inspect("The interfaces and their endpoints", "Interface table", "edit them in the table"),),
    ),
    StepDef(
        "configure", "Set the engineering values",
        "Give the project its derating, grounding, test limits and the choices of the models.",
        (_p("library/<category>.json"),),
        (_c("derating"), _c("generation"), _c("segmentation"), _c("model"), _c("naming"), _c("titleblock")),  # fmt: skip
        "config", "Design > Engineering values",
        (
            Inspect("Every setting, its value, its unit and where it comes from", "settings DIR", "config DIR --apply-profile, or the Engineering values window"),  # fmt: skip
            Inspect("What is still pending", "config DIR", "set the value; the file stays a placeholder until reviewed"),  # fmt: skip
        ),
    ),
    StepDef(
        "generate", "Generate the harnesses",
        "Allocate the pins, group the interfaces into harnesses, size and route the wires.",
        (_p("logical/units/<subsystem>.json"), _p("logical/interfaces/<subsystem>.json"), _p("logical/links.json"), _p("physical/connectors/<subsystem>.json"), _c("derating"), _c("generation"), _c("segmentation"), _c("model"), _c("naming")),  # fmt: skip
        (_p("physical/harnesses/<harness>.json"), _p("generated/generation.json")),
        "generate", "Design > Generate harnesses",
        (
            Inspect("The candidates and the limits that sized each wire", "explain DIR WIRE; export-data table wire_sizing", "override DIR WIRE FIELD VALUE --reason TEXT"),  # fmt: skip
            Inspect("The groups of the segmentation and why", "explain DIR HARNESS; export-data tables segmentation_groups, segmentation_interfaces", "the segmentation settings (settings DIR)"),  # fmt: skip
            Inspect("The allocation of the signals to the pins", "explain DIR CONNECTOR.PIN; export-data table pin_allocation", "lock a pin in the Devices tab"),  # fmt: skip
            Inspect("The derived lengths of the wires", "explain DIR WIRE; export-data tables lengths, segment_lengths", "import-lengths, or override a length"),  # fmt: skip
        ),
    ),
    StepDef(
        "check", "Check the design",
        "Run the design rules and see what is open; accept a finding with a reason only where the tool allows it.",
        (_p("physical/harnesses/<harness>.json"), _c("derating"), _c("model")),
        (_o("system/drc_findings.csv"), _o("system/drc_report.md"), _p("waivers.json")),
        "drc", "Checks",
        (
            Inspect("The limit or comparison behind each finding", "explain DIR --all; export-data tables rule_results, findings", "the settings the rule reads (settings DIR)"),  # fmt: skip
        ),
    ),
    StepDef(
        "build-data", "Enter the build data",
        "Give the wires strip lengths and the pins their termination, contact and crimp tool, and add accessories.",
        (_p("physical/harnesses/<harness>.json"), _p("library/contact.json"), Item(FILE, "a strip-length, contact, accessory or tool sheet (import-build-data)")),  # fmt: skip
        (_p("physical/harnesses/<harness>.json"), _p("library/contact.json")),
        "import-build-data", "Drawings; the wire and connector editors",
        (
            Inspect("What is ready to build and what is open", "explain DIR HARNESS; export-data table readiness", "enter the missing data; settings DIR names the checks that block"),  # fmt: skip
        ),
    ),
    StepDef(
        "outputs", "Write the outputs",
        "Write the build workbook, the tables and the exports, and check them against the design.",
        (_p("physical/harnesses/<harness>.json"), _c("generation"), _c("titleblock"), _c("naming"), _p("library/<category>.json")),  # fmt: skip
        (_o("harnesses/<harness>/<harness>_build.xlsx"), _o("harnesses/<harness>/tests.csv"), _o("harnesses/<harness>/wirelist.csv"), _o("system/bom.csv"), _o("system/provenance.json"), _o("manifest.json")),  # fmt: skip
        "export", "Design > Export",
        (
            Inspect("Every number as a table", "export-data DIR --out FOLDER", ""),
            Inspect("The test limits printed on the Tests sheet", "explain DIR HARNESS.T001; export-data table test_limits", "the three test limits in config/generation.json"),  # fmt: skip
        ),
    ),
    StepDef(
        "release", "Review and release",
        "Submit a harness for review, then release it: the release freezes what it was made from.",
        (_p("physical/harnesses/<harness>.json"), _o("manifest.json"), _p("waivers.json")),
        (_p("baselines/<harness>/<baseline>.json"), _p("changelog.json"), _o("system/revision_report.md"), _o("system/changelog.csv")),  # fmt: skip
        "release", "Revisions",
        (Inspect("What a release froze, and what changed since", "diff DIR HARNESS; log DIR HARNESS", "start a new revision (revise)"),),  # fmt: skip
    ),
    StepDef(
        "as-built", "Record what was built",
        "Write down serial and lot numbers, cut and strip lengths, tools and the measured test results, and compare them with the design and the test limits.",  # fmt: skip
        (_o("harnesses/<harness>/<harness>_build.xlsx"), Item(FILE, "the as-built sheet (export-asbuilt) filled in"), _c("generation")),  # fmt: skip
        (_p("asbuilt/records.json"), _p("imports/records.json"), _o("system/asbuilt_report.md"), _o("system/asbuilt_report.csv")),  # fmt: skip
        "import-asbuilt", "As-built",
        (
            Inspect("What is missing, out of its limit or different from the design", "asbuilt DIR; explain DIR HARNESS.T001", "import the sheet again with the corrected values"),  # fmt: skip
        ),
    ),
)  # fmt: skip
KEYS: Final[tuple[str, ...]] = tuple(s.key for s in STEPS)

# The words of the six steps of the Next step page and of the three steps of the top bar, by the key
# of the step they stand for: the screen takes them from here (`gui/strings.py`), so the two lists
# and the table of the workflow page are one source.
PAGE_LABELS: Final[dict[str, str]] = {
    "devices": "Add your devices",
    "connect": "Connect them",
    "generate": "Generate the harnesses",
    "check": "Check the design",
    "outputs": "Get the build sheets",
    "release": "Review and release",
}
BAR_LABELS: Final[dict[str, str]] = {"generate": "Generate", "check": "Check", "release": "Release"}
# the step of the workflow each result of the Next step page (`gui/next_step.py`) is about
NEXT_KEY_STEP: Final[dict[str, str]] = {
    "add_device": "devices",
    "connect": "connect",
    "make_harness": "generate",
    "generate": "generate",
    "check": "check",
    "fix": "check",
    "build_sheets": "outputs",
    "release": "release",
    "done": "as-built",
}


def step(key: str) -> StepDef:
    for s in STEPS:
        if s.key == key:
            return s
    raise KeyError(key)


# ---- the status of a project ---------------------------------------------------------------------

DONE = "done"
TODO = "todo"
PENDING = "pending"  # something is missing that a person has to enter
STALE = "stale"  # what the step made is older than the design
ATTENTION = "attention"  # something needs a person
BLOCKED = "blocked"  # a step before it has to be done first
STATES: Final = (DONE, TODO, PENDING, STALE, ATTENTION, BLOCKED)


@dataclass(frozen=True)
class StepStatus:
    key: str
    state: str
    detail: str
    blocked_by: tuple[str, ...] = ()  # the keys of the steps before it that are not done

    def to_dict(self) -> dict[str, Any]:
        return {"key": self.key, "state": self.state, "detail": self.detail,
                "blocked_by": list(self.blocked_by)}  # fmt: skip


@dataclass(frozen=True)
class Check:
    """What the check step needs to know (the editor has it already, so it passes it in)."""

    checked: bool
    errors: int  # open errors
    warnings: int = 0


@dataclass(frozen=True)
class WorkflowReport:
    """The steps with what each uses and makes, and where the project stands in each (the command
    `workflow`, `api.get_workflow`)."""

    steps: tuple[tuple[StepDef, StepStatus], ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "steps": [{**d.to_dict(), **s.to_dict(), "key": d.key} for d, s in self.steps]
        }  # fmt: skip


def workflow_report(
    project: Project, outputs_folder: Path | str | None = None, *, check: Check | None = None
) -> WorkflowReport:
    status = workflow_status(project, outputs_folder, check=check)
    return WorkflowReport(tuple(zip(STEPS, status, strict=True)))


def _plural(n: int, one: str, many: str | None = None) -> str:
    return f"{n} {one}" if n == 1 else f"{n} {many or one + 's'}"


def _build_data_open(project: Project) -> int:
    from harness_design_studio.core.outputs import buildsheet

    names = {"Wires without strip lengths", "Pins in use without a termination", "Pins in use without a contact part"}  # fmt: skip
    return sum(
        c.open
        for h in project.harnesses.values()
        for c in buildsheet.readiness(project, h)
        if c.label in names
    )


def _outputs_state(project: Project, folder: Path | str | None) -> str:
    if folder is None:
        return "unknown"
    from harness_design_studio.core.outputs.build import outputs_status

    return outputs_status(project, folder).state


def _run_checks(project: Project) -> Check:
    from harness_design_studio.core import checks, drc

    found = [f for f in [*checks.find(project), *drc.run(project)] if f.waiver is None]
    return Check(True, sum(f.severity == "error" for f in found), sum(f.severity == "warning" for f in found))  # fmt: skip


def workflow_status(
    project: Project, outputs_folder: Path | str | None = None, *, check: Check | None = None
) -> tuple[StepStatus, ...]:
    """Where the project stands in each step. `outputs_folder` is where the outputs were written
    (None: not known, the step says so); `check` is the result of the rule check when the caller
    has it (the editor), else the rules are run now."""
    out: dict[str, StepStatus] = {}
    harnesses = len(project.harnesses)
    gen = generation_status(project)
    by_hand = harnesses > 0 and all(not h.generated for h in project.harnesses.values())

    def put(key: str, state: str, detail: str, *needs: str) -> None:
        blocked = tuple(k for k in needs if out[k].state != DONE)
        if blocked and state == TODO:
            state = BLOCKED
        out[key] = StepStatus(key, state, detail, blocked if state == BLOCKED else ())

    put("devices", DONE if project.units or harnesses else TODO,
        _plural(len(project.units), "device") + "." if project.units else "No device yet.")  # fmt: skip
    connected = len(project.interfaces) + len(project.links)
    put("connect", DONE if connected or harnesses else TODO,
        f"{_plural(len(project.interfaces), 'interface')}, {_plural(len(project.links), 'connection')}.",  # fmt: skip
        "devices")  # fmt: skip
    todo = configcheck.missing(project)
    placeholders = len(project.placeholder_configs())
    if todo:
        put("configure", PENDING, f"{_plural(len(todo), 'engineering value')} still to set.")
    elif placeholders:
        put("configure", DONE, f"All values set; {_plural(placeholders, 'file')} still marked as placeholder.")  # fmt: skip
    else:
        put("configure", DONE, "All engineering values set.")
    if gen == "current" or by_hand:
        put("generate", DONE, _plural(harnesses, "harness", "harnesses") + (" (made by hand)." if by_hand else "."))  # fmt: skip
    elif gen == "stale":
        put("generate", STALE, "The design changed after the harnesses were generated.", "connect")  # fmt: skip
    else:
        put("generate", TODO, "Not generated yet.", "connect")
    if not harnesses:
        put("check", TODO, "Nothing to check yet.", "generate")
    else:
        result = check or _run_checks(project)
        if not result.checked:
            put("check", TODO, "Not checked since the last change.", "generate")
        elif result.errors:
            put("check", ATTENTION, f"{_plural(result.errors, 'rule')} failed with an error.")
        else:
            put("check", DONE, "No open error." + (f" {_plural(result.warnings, 'warning')} open." if result.warnings else ""))  # fmt: skip
    open_items = _build_data_open(project) if harnesses else 0
    if not harnesses:
        put("build-data", TODO, "No harness yet.", "generate")
    elif open_items:
        put("build-data", PENDING, f"{_plural(open_items, 'item')} of build data still open (strip lengths, terminations, contacts).")  # fmt: skip
    else:
        put("build-data", DONE, "Strip lengths, terminations and contacts are entered.")
    state = _outputs_state(project, outputs_folder)
    if not harnesses:
        put("outputs", TODO, "No harness yet.", "generate")
    elif state == "current":
        put("outputs", DONE, "The outputs match the design.")
    elif state in ("stale", "modified"):
        put("outputs", STALE, "The outputs are older than the design, or were changed after export.")  # fmt: skip
    elif state == "unknown":
        put("outputs", TODO, "The outputs folder was not looked at.", "generate")
    else:
        put("outputs", TODO, "No outputs written yet.", "generate", "check")
    released = sum(h.status == "released" for h in project.harnesses.values())
    if harnesses and released == harnesses:
        put("release", DONE, f"All {harnesses} released.")
    else:
        put("release", TODO, f"{released} of {harnesses} released.", "check", "outputs")
    report = asbuilt.asbuilt_report(project)
    if not report.has_records:
        put("as-built", TODO, "No as-built record yet.", "outputs")
    elif report.out_of_limit:
        put("as-built", ATTENTION, f"{_plural(report.out_of_limit, 'value')} out of the limit; {report.missing} missing.")  # fmt: skip
    elif report.missing:
        put("as-built", PENDING, f"{_plural(report.missing, 'value')} still to record.")
    else:
        put("as-built", DONE, f"{_plural(report.records, 'record')}; nothing missing.")
    return tuple(out[k] for k in KEYS)


# ---- the table of the page -----------------------------------------------------------------------


def _cell(items: tuple[Item, ...]) -> str:
    return "<br>".join(i.text() for i in items)


def table_markdown() -> str:
    """The table of the workflow page: one row for each step. The page holds exactly this text
    between its two markers; a test compares them."""
    rows = [
        "| Step | What it does | Uses | Makes | Command | On screen |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for s in STEPS:
        command = f"`harness-design-studio {s.command}`" if s.command else "-"
        rows.append(f"| **{s.title}** | {s.does} | {_cell(s.consumes)} | {_cell(s.produces)} | {command} | {s.screen} |")  # fmt: skip
    return "\n".join(rows)


def inspect_markdown() -> str:
    """The intermediates: one row for each, with the step it belongs to."""
    rows = [
        "| Step | Intermediate | Look at it | Change it |",
        "| --- | --- | --- | --- |",
    ]
    for s in STEPS:
        for i in s.inspect:
            rows.append(f"| {s.title} | {i.what} | {i.how} | {i.change or '-'} |")
    return "\n".join(rows)


__all__ = [
    "KEYS",
    "STATES",
    "STEPS",
    "Check",
    "Inspect",
    "Item",
    "StepDef",
    "StepStatus",
    "WorkflowReport",
    "inspect_markdown",
    "step",
    "table_markdown",
    "workflow_report",
    "workflow_status",
]
