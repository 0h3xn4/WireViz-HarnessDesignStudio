"""The scripting interface of Harness Design Studio: what the tool does, as Python functions.

Everything the command line and the editor do for an engineer can be done from a script. This
module is the stable way to do it. It has no Qt in it (a test imports it with PySide6 blocked), it
prints nothing, it never ends the program, and it takes and gives plain data: folders as paths or
text, results as small dataclasses that also have `to_dict()` (the dictionary is what the
command line prints with `--json`, so a script and a shell pipeline see the same thing).

It adds no behaviour of its own. Each function calls the function of the tool that the command
line calls, so a number from here is the number `generate`, `drc` or `export` gives. The same
design gives the same answer: nothing in a result is a time, a user name or an absolute path.

A short example::

    from harness_design_studio.api import create_project, generate, run_checks

    create_project("my-design", "flatsat")
    generate("my-design")
    result = run_checks("my-design")
    print(result.open_errors, result.open_warnings)

Two kinds of function:

* **Reading** (`run_checks`, `explain`, `explain_all`, `explain_finding`, `get_config`,
  `write_derivations`, `export_data`) takes a project folder or a `Project` you loaded, and changes
  no project (the last two write files into the folder you name, and nowhere else).
* **Changing** (`create_project`, `generate`, `export`, `set_config`) takes a folder, takes the same
  lock as the editor and the command line, and writes what the command of the same name writes.
  Give `export` an `out` folder to write the outputs somewhere else.

Errors are exceptions from one tree rooted at `HarnessError` (listed in `__all__`). A step that is
refused for a reason of the design, such as a generation with errors, is not an exception: it is a
result with `ok` false and the reasons in it, as the command ends with exit code 1.

The names in `__all__` and the signatures of the functions are frozen by a test
(`tests/fixtures/api_snapshot.json`); see `docs/developer/api-stability.md` for the rules.
"""

import contextlib
import os
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from harness_design_studio.core import asbuilt, change_ops, configcheck, journal, records, workflow
from harness_design_studio.core.asbuilt import AsBuiltImportResult, AsBuiltReport
from harness_design_studio.core.checks import Finding, find
from harness_design_studio.core.commands import History
from harness_design_studio.core.derive import Derivation, explain_object
from harness_design_studio.core.derive import explain_finding as _explain_finding
from harness_design_studio.core.derive_export import explain_all as _explain_all
from harness_design_studio.core.derive_export import to_csv_bytes, to_json_bytes
from harness_design_studio.core.drc import run as _run_rules
from harness_design_studio.core.edit import EditError
from harness_design_studio.core.errors import (
    HarnessError,
    LoadError,
    ProjectLockedError,
    SaveError,
    TransactionError,
)
from harness_design_studio.core.io.fs import ProjectLock
from harness_design_studio.core.io.layout import model_hash
from harness_design_studio.core.io.loader import load_project as _load_project
from harness_design_studio.core.io.saver import save_project as _save_project
from harness_design_studio.core.issues import errors
from harness_design_studio.core.model import Project
from harness_design_studio.core.records import (
    CheckResult,
    ConfigReport,
    ConfigValue,
    DataFiles,
    DerivationFiles,
    DeviationRecord,
    DeviationReport,
    ExportedFile,
    ExportResult,
    FindingRecord,
    GenerateResult,
    IssueRecord,
    JournalRecord,
    JournalReport,
    OverrideRecord,
    OverrideResult,
    RuleInfo,
    SettingRecord,
    TemplateInfo,
    ValidationResult,
    VerifyResult,
)
from harness_design_studio.core.templates import TemplateError
from harness_design_studio.core.templates import create_project as _create_project
from harness_design_studio.core.validation import validate_folder
from harness_design_studio.core.wires import find_wire
from harness_design_studio.core.workflow import WorkflowReport

__all__ = [
    "API_VERSION",
    "AsBuiltImportResult",
    "AsBuiltReport",
    "CheckResult",
    "ConfigReport",
    "ConfigValue",
    "ConfigValueError",
    "DataFiles",
    "Derivation",
    "DerivationFiles",
    "DeviationRecord",
    "DeviationReport",
    "EditError",
    "ExportResult",
    "ExportedFile",
    "FindingRecord",
    "GenerateResult",
    "HarnessError",
    "IssueRecord",
    "JournalRecord",
    "JournalReport",
    "LoadError",
    "NoOutputsError",
    "PathLike",
    "OverrideRecord",
    "OverrideResult",
    "Project",
    "ProjectDamagedError",
    "ProjectLockedError",
    "ProjectSource",
    "ReadOnlyProjectError",
    "RuleInfo",
    "SaveError",
    "SettingRecord",
    "TemplateError",
    "TemplateInfo",
    "TransactionError",
    "ValidationResult",
    "VerifyResult",
    "WorkflowReport",
    "accept_deviation",
    "clear_override",
    "create_project",
    "explain",
    "explain_all",
    "explain_finding",
    "export",
    "export_data",
    "generate",
    "get_asbuilt",
    "get_config",
    "get_journal",
    "get_overrides",
    "get_settings",
    "get_workflow",
    "import_asbuilt",
    "list_deviations",
    "list_extensions",
    "list_rules",
    "list_templates",
    "load_project",
    "remove_deviation",
    "run_checks",
    "save_project",
    "set_config",
    "set_override",
    "start_journal",
    "validate",
    "verify",
    "write_asbuilt_sheet",
    "write_derivations",
]

API_VERSION = 1
"""The version of this interface. It goes up when a name or a signature in `__all__` is removed or
changed in a way that can break a script; adding a name or an optional argument does not change
it. `tests/fixtures/api_snapshot.json` holds the value the snapshot was made with."""

PathLike = str | os.PathLike[str]
ProjectSource = Project | PathLike
"""Where a reading function gets its project: one you loaded, or a project folder."""


# ---- errors ------------------------------------------------------------------------------------
#
# The tree, from the root: HarnessError (everything the tool raises on purpose)
#   LoadError              the folder is not a project, or cannot be read
#     ProjectDamagedError  it is a project with damaged files (the command line: exit 2)
#   SaveError              a file could not be written; the earlier files are left as they were
#   ProjectLockedError     the project is open in the editor or in another script
#   TransactionError       a change was refused (a released harness, an inconsistent result)
#   EditError              a change that cannot be done, with the reason
#     ConfigValueError     a configuration value that is not acceptable
#   TemplateError          an unknown example, or a folder that is not empty
#   ReadOnlyProjectError   the project was saved by a newer version of the tool
#   NoOutputsError         there is no outputs folder to check


class ProjectDamagedError(LoadError):
    """A project with damaged files: nothing is done with it. `issues` lists what is wrong; the
    `validate` function reports the same without refusing."""

    def __init__(self, message: str, issues: tuple[IssueRecord, ...] = ()) -> None:
        super().__init__(message)
        self.issues = issues


class ReadOnlyProjectError(HarnessError):
    """The project was saved by a newer version of the tool, so it can be read but not changed."""


class ConfigValueError(EditError):
    """A configuration value the tool does not accept: an unknown key, a value that is not a
    number, or one outside its range (a factor above 1, an ampacity that falls with wire size)."""


class NoOutputsError(HarnessError):
    """`verify(..., outputs=True)` found no outputs folder; run `export` first."""


# ---- helpers -----------------------------------------------------------------------------------


def _load(folder: PathLike) -> Project:
    """The project of a folder, or the exception the command line turns into exit code 2."""
    loaded = _load_project(Path(folder))
    if loaded.has_errors or loaded.project.recovered:
        first = errors(loaded.issues)[0].render() if loaded.has_errors else "parts set aside"
        raise ProjectDamagedError(
            f"the project has damaged files (first: {first}); nothing was done. "
            "`validate` lists them.",
            records.issue_records(sorted(loaded.issues)),
        )
    return loaded.project


def _project(source: ProjectSource) -> Project:
    return source if isinstance(source, Project) else _load(source)


def _writable(project: Project) -> None:
    if project.read_only:
        raise ReadOnlyProjectError("this project is read-only (saved by a newer tool version).")


@contextlib.contextmanager
def _locked(folder: Path) -> Iterator[None]:
    """The lock the editor and the command line take while they write; none for a folder that is
    not a project (loading then says so)."""
    if not (folder / "project.json").is_file():
        yield
        return
    lock = ProjectLock(folder)
    lock.acquire()
    try:
        yield
    finally:
        lock.release()


def _findings(project: Project) -> list[Finding]:
    """The findings `drc` prints: the logical layer and the rules, errors first, then by ID."""
    return sorted(
        [*find(project), *_run_rules(project)],
        key=lambda f: ({"error": 0, "warning": 1, "info": 2}[f.severity], f.id),
    )


# ---- projects ----------------------------------------------------------------------------------


def load_project(folder: PathLike) -> Project:
    """Open a project folder. Raises `LoadError` for a folder that is not a project and
    `ProjectDamagedError` for a project with damaged files (use `validate` to see what is wrong).
    Format upgrades are done in memory; nothing is written."""
    return _load(folder)


def save_project(project: Project, folder: PathLike) -> None:
    """Write a project to a folder, as the editor saves it. Takes the project lock. Raises
    `ReadOnlyProjectError` for a project saved by a newer version of the tool."""
    _writable(project)
    path = Path(folder)
    with _locked(path):
        _save_project(project, path)


def list_templates() -> list[TemplateInfo]:
    """The example projects `create_project` can start from, in the order of `new --list`."""
    return records.template_infos()


def create_project(
    folder: PathLike, template: str = "blank", name: str | None = None, *, journal: bool = True
) -> Project:
    """Make a new project folder from an example (see `list_templates`) and return the project.
    The folder must not exist or must be empty (`TemplateError` otherwise); `name` replaces the
    project name of the example. Like the command `new`, it starts a change journal
    (`journal.json`) unless `journal` is false."""
    return _create_project(Path(folder), template, name, journal=journal)


# ---- checking ----------------------------------------------------------------------------------


def validate(folder: PathLike, *, merge_check: bool = False) -> ValidationResult:
    """The command `validate`: read the files, then check the whole project. With `merge_check`
    it is `check`: also files that differ from the tool's own formatting, and released harnesses
    that were edited. A damaged project is reported here (in `issues`), not refused."""
    loaded, extra = validate_folder(Path(folder), merge_check=merge_check)
    return records.validation_result(loaded, extra)


def run_checks(source: ProjectSource) -> CheckResult:
    """The command `drc`: every rule of the design rule check, plus the checks of the logical
    layer. Findings are sorted errors first, then by ID; waived ones are included and marked.
    Changes nothing."""
    project = _project(source)
    return records.check_result(project, _findings(project))


def list_extensions(source: ProjectSource) -> dict[str, Any]:
    """The command `extensions`: what is registered for a project, built-in and extension items
    together, with the declarative files and Python plug-ins of its `extensions/` folder and whether
    each is enabled and trusted (the same document as `extensions --json`). Python code is not
    loaded by asking. Changes nothing."""
    from harness_design_studio.core.extensions.manager import listing

    return listing(_project(source))


def list_rules() -> list[RuleInfo]:
    """The design rules, in the order of the report. Static: it needs no project."""
    return records.rule_infos()


def verify(folder: PathLike, *, outputs: bool = False) -> VerifyResult:
    """The command `verify`: the independent check of the harnesses against the interfaces. With
    `outputs=True` also the `outputs` folder of the project against the design; `NoOutputsError`
    when there is none. Changes nothing."""
    from harness_design_studio.core.outputs.build import DEFAULT_FOLDER
    from harness_design_studio.core.outputs.verify import read_folder, verify_outputs
    from harness_design_studio.core.verify import verify_project

    path = Path(folder)
    project = _load(path)
    report = verify_project(project)
    if outputs:
        target = path / DEFAULT_FOLDER
        if not target.is_dir():
            raise NoOutputsError("there is no outputs folder; run `export` first.")
        out = verify_outputs(project, read_folder(target))
        report.issues += out.issues
        report.stale = report.stale or out.stale
    return records.verify_result(report)


# ---- generating and exporting ------------------------------------------------------------------


def generate(
    folder: PathLike, *, run_record: bool = False, operator: str | None = None
) -> GenerateResult:
    """The command `generate`: plan the harnesses from the interfaces, apply the plan, check it
    independently and save the project. Nothing is saved when there is an error (`ok` is false and
    `findings` and `verify_issues` say why). Released harnesses and locked pins and wires are kept.
    Takes the project lock. Raises `ReadOnlyProjectError` for a project saved by a newer version.
    With `run_record=True` and a saved result, `run_record.json` (time, operator, tool version,
    model hash) is written into the `outputs` folder of the project, outside every hash; `operator`
    names who ran it (else `HARNESS_AUTHOR`, the Git name, the user of the system)."""
    from harness_design_studio.core.generate.engine import generate_project
    from harness_design_studio.core.verify import verify_project

    path = Path(folder)
    with _locked(path):
        project = _load(path)
        _writable(project)
        plan = generate_project(project)
        report = verify_project(project)
        ok = not plan.report.errors and report.ok
        if ok:
            _save_project(project, path)
            if run_record:
                _write_run_record(project, path / "outputs", operator, path)
    return records.generate_result(plan, report, saved=ok)


def export(
    folder: PathLike,
    out: PathLike | None = None,
    *,
    drawings: bool = False,
    run_record: bool = False,
    operator: str | None = None,
) -> ExportResult:
    """The command `export`: build every output file of the project, check them independently and
    write them to `out` (default: the `outputs` folder of the project). The PDF and SVG drawings of
    the harnesses are written only with `drawings=True`. Takes the project lock. Nothing is written
    (`written` is false, `blocked` says why) when there is nothing to export or the independent
    check of the outputs fails. With `run_record=True` a written export also gets `run_record.json`
    next to its manifest (time, operator, tool version, model hash): it is not listed in the
    manifest and is in no hash; `operator` is as for `generate`."""
    from harness_design_studio.core.outputs.build import (
        DEFAULT_FOLDER,
        build_outputs,
        drawings_exported,
        write_outputs,
    )
    from harness_design_studio.core.outputs.verify import verify_outputs

    path = Path(folder)
    with _locked(path):
        project = _load(path)
        _writable(project)
        if not project.harnesses and not project.links:  # connections alone are enough
            return records.export_refused("nothing_to_export")
        built = build_outputs(project, drawings=drawings)
        report = verify_outputs(project, built.files)
        if not report.ok:
            return records.export_refused("outputs_failed_check", built.stamp.short, report.issues)
        target = Path(out) if out is not None else path / DEFAULT_FOLDER
        had_drawings = drawings_exported(target)
        write_outputs(project, target, built)
        if run_record:
            _write_run_record(project, target, operator, path)
    return records.export_result(
        built, report.issues, drawings_removed=had_drawings and not drawings
    )


def _write_run_record(
    project: Project, folder: Path, operator: str | None, project_folder: Path
) -> None:
    from harness_design_studio.core import run_record

    run_record.write_for(project, folder, operator=operator, project_folder=project_folder)


def export_data(
    source: ProjectSource,
    out: PathLike,
    *,
    run_record: bool = False,
    operator: str | None = None,
) -> DataFiles:
    """The command `export-data`: write every intermediate and final result of the project to the
    folder `out` as JSON and CSV (wire sizing, segmentation, pin allocation, rule results,
    readiness, lengths, mass, bill of materials, findings, test limits, settings), with
    `configuration.json` and `provenance.json`. A script can recompute the numbers from these files
    alone (`docs/user-manual/export-the-data.md`). The same design gives the same bytes; no file
    holds a time, a user name or a path. With `run_record=True`, `run_record.json` (time, operator,
    tool version, model hash) is written beside them; it is not part of the set. Changes no
    project. Returns the names of the files written."""
    from harness_design_studio.core import run_record as record
    from harness_design_studio.core.open_data import write_data

    project = _project(source)
    folder = Path(out)
    files = write_data(project, folder)
    named = ""
    if run_record:
        project_folder = None if isinstance(source, Project) else Path(source)
        named = record.write_for(
            project, folder, operator=operator, project_folder=project_folder
        ).name
    return DataFiles(tuple(sorted(files)), model_hash(project)[:12], named)


# ---- explaining --------------------------------------------------------------------------------


def explain(source: ProjectSource, object_id: str) -> list[Derivation]:
    """How the numbers of one object were made: a wire (its length, current limit, voltage drop
    and mass), a harness (its mass), a part (why the bill of materials has its quantity) or
    `INTERFACE.CONNECTOR` (the contact current limit). The command `explain`. `Derivation.to_dict()`
    is the plain form. `EditError` when the ID is none of these."""
    return explain_object(_project(source), object_id)


def explain_all(source: ProjectSource) -> list[Derivation]:
    """Every derivation of the project in a fixed order (what `explain --all` writes)."""
    return _explain_all(_project(source))


def explain_finding(source: ProjectSource, finding_id: str) -> list[Derivation]:
    """The calculation behind a finding of `run_checks`, as the editor's *Explain* shows it: for a
    finding of `current-over-wire` or `voltage-drop` the derivation of the wire, for
    `current-over-contact` the derivation of the contact limit. An empty list for a finding of
    another rule, which has no calculation to show. `EditError` when no finding has this ID."""
    project = _project(source)
    found = {f.id: f for f in _findings(project)}
    if finding_id not in found:
        raise EditError(f"There is no finding '{finding_id}'.")
    finding = found[finding_id]
    return _explain_finding(project, finding.rule, finding.object_id)


def write_derivations(source: ProjectSource, out: PathLike) -> DerivationFiles:
    """Write every derivation of the project to the folder `out` as `derivations.json` and
    `derivations.csv` (the command `explain --all --out`). The same design gives the same bytes."""
    project = _project(source)
    found = _explain_all(project)
    folder = Path(out)
    folder.mkdir(parents=True, exist_ok=True)
    files = (folder / "derivations.json", folder / "derivations.csv")
    files[0].write_bytes(to_json_bytes(project, found))
    files[1].write_bytes(to_csv_bytes(found))
    return DerivationFiles(files, len(found), sum(1 for d in found if d.value is None))


# ---- configuration -----------------------------------------------------------------------------


def get_config(source: ProjectSource) -> ConfigReport:
    """The engineering values in force: each value of the hand-over list and of the standard
    profiles with its unit, what it is used for, whether it is set, and where it came from; and
    the problems of values that are set (the command `config` without options)."""
    return records.config_report(_project(source))


def get_settings(source: ProjectSource) -> list[SettingRecord]:
    """Every setting the results depend on with the value in force for the project and where it
    comes from (the command `settings`): the project's own value, the tool's default, or not set."""
    return records.setting_records(_project(source))


def set_config(
    folder: PathLike, file: str, key: str, value: object, *, placeholder: bool | None = None
) -> ConfigValue:
    """Set one engineering value of `config/<file>.json` and save the project; the value is
    checked like the editor and `config` check it (a factor above 1, an ampacity that falls as the
    wire gets bigger, a value that is not a number are refused with `ConfigValueError`; a release
    that froze the value refuses with `TransactionError`). `value` may be a number, text as a
    person types it (`"0,5 V"`, `"power + analog"`, `"20: 5, 22: 3.5"`) or a ready value; `None` or
    empty text clears it. `placeholder` also sets the file's review flag (False: reviewed).
    Takes the project lock. Returns the value as it is now."""
    path = Path(folder)
    with _locked(path):
        project = _load(path)
        _writable(project)
        plan = configcheck.plan_set_value(project, file, key, value, placeholder=placeholder)
        if not plan.ok:
            raise ConfigValueError(plan.error or "the value is not acceptable.")
        History(project).execute(f"Set {file}.{key}", plan.ops)
        _save_project(project, path)
    return records.config_report(project).value(file, key)


# ---- overrides, deviations and the change journal ----------------------------------------------
#
# The functions that change a project take `author=`: the name the journal records for the change
# (default: the environment variable HARNESS_AUTHOR, else the name Git has, else the user of the
# computer). A project that keeps no journal records nobody.


@contextlib.contextmanager
def _as(author: str | None) -> Iterator[None]:
    journal.set_author(author)
    try:
        yield
    finally:
        journal.set_author(None)


def get_journal(
    source: ProjectSource, *, object_id: str | None = None, since: int = 0
) -> JournalReport:
    """The change journal of a project (the command `journal`): who changed what, when, from what
    to what and why. `object_id` selects one object (`W001-001`, `wire:W001-001`,
    `derating.bundle_derating`), `since` the entries numbered above it. A project that keeps no
    journal gives `has_journal` false and no entries."""
    return records.journal_report(_project(source), object_id, since)


def start_journal(folder: PathLike, *, author: str | None = None) -> bool:
    """Give a project a change journal (writes `journal.json`). False when it has one already.
    Takes the project lock."""
    path = Path(folder)
    with _locked(path), _as(author):
        project = _load(path)
        _writable(project)
        started = journal.start(project)
        if started:
            _save_project(project, path)
    return started


def get_overrides(source: ProjectSource, wire_id: str) -> OverrideResult:
    """The values of a wire that were set by hand, with their reasons, and the derivation
    *Overridden by the engineer* (the command `override DIR WIRE`). Raises `EditError` for a wire
    that does not exist."""
    project = _project(source)
    find_wire(project, wire_id)
    return records.override_result(project, wire_id, "show", False)


def set_override(
    folder: PathLike,
    wire_id: str,
    field: str,
    value: object,
    reason: str,
    *,
    author: str | None = None,
) -> OverrideResult:
    """Set `field` (`gauge_awg`, `part_id`, `colour` or `length_m`) of a generated wire by hand
    and say why (the command `override DIR WIRE FIELD VALUE --reason TEXT`). The value is kept when
    the harnesses are generated again. A missing reason, a wire drawn by hand or a field that
    cannot be overridden raises `EditError`; a released harness raises `TransactionError`. Takes the
    project lock."""
    path = Path(folder)
    with _locked(path), _as(author):
        project = _load(path)
        _writable(project)
        changed = change_ops.set_override(project, wire_id, field, value, reason)
        if changed:
            _save_project(project, path)
    return records.override_result(project, wire_id, "set", changed)


def clear_override(
    folder: PathLike, wire_id: str, field: str, *, author: str | None = None
) -> OverrideResult:
    """Give `field` of the wire back to generation (the command `override DIR WIRE --clear FIELD`):
    the next `generate` gives it the design's value. Takes the project lock."""
    path = Path(folder)
    with _locked(path), _as(author):
        project = _load(path)
        _writable(project)
        changed = change_ops.clear_override(project, wire_id, field)
        if changed:
            _save_project(project, path)
    return records.override_result(project, wire_id, "clear", changed)


def list_deviations(source: ProjectSource) -> list[DeviationRecord]:
    """The errors of electrical rules that a person accepted as deviations (the command
    `deviation DIR`), with the reason and, when the project keeps a journal, who and when."""
    return list(records.deviation_records(_project(source)))


def accept_deviation(
    folder: PathLike, finding_id: str, reason: str, *, author: str | None = None
) -> DeviationReport:
    """Accept the error `finding_id` of an electrical rule as a recorded deviation, with a reason
    of at least 10 characters (the command `deviation DIR FINDING --reason TEXT`). The error stays
    visible and is marked DEVIATION; it does not meet the requirement. Raises `EditError` for an
    unknown finding, a rule that takes no deviation or a short reason. Takes the project lock."""
    path = Path(folder)
    with _locked(path), _as(author):
        project = _load(path)
        _writable(project)
        finding = change_ops.accept_deviation(project, finding_id, reason)
        _save_project(project, path)
    marked = tuple(d for d in records.deviation_records(project) if d.id == finding.id)
    return DeviationReport("record", finding.id, marked)


def remove_deviation(
    folder: PathLike, finding_id: str, *, author: str | None = None
) -> DeviationReport:
    """Take a deviation back (`deviation DIR FINDING --remove`); the finding is open again. Raises
    `EditError` when the finding is not a deviation. Takes the project lock."""
    path = Path(folder)
    with _locked(path), _as(author):
        project = _load(path)
        _writable(project)
        finding = change_ops.remove_deviation(project, finding_id)
        _save_project(project, path)
    return DeviationReport("remove", finding.id, ())


# ---- workflow and as-built records (S9) ---------------------------------------------------------


def get_workflow(source: ProjectSource, *, outputs: PathLike | None = None) -> WorkflowReport:
    """The steps of the tool, what each uses and makes, the intermediates you can look at, and
    where the project stands in each step (the command `workflow`). `outputs` is the folder the
    outputs were written to (default: `outputs` in the project folder, when `source` is a folder).
    Changes nothing."""
    project = _project(source)
    folder: Path | None = Path(outputs) if outputs is not None else None
    if folder is None and not isinstance(source, Project):
        folder = Path(source) / "outputs"
    return workflow.workflow_report(project, folder)


def get_asbuilt(source: ProjectSource) -> AsBuiltReport:
    """What was recorded about the build and how it compares with the design and the project's
    test limits: what is missing, what is out of its limit, what differs from the design (the
    command `asbuilt`). It never says that anything passed. A project with no record gives a
    report with `records` 0."""
    return asbuilt.asbuilt_report(_project(source))


def write_asbuilt_sheet(
    source: ProjectSource, file: PathLike, *, harness: str | None = None
) -> Path:
    """Write the sheet a technician fills in (the command `export-asbuilt`): `.csv` or `.xlsx`,
    one row for each thing to record with the designed values filled in. Returns the file."""
    project = _project(source)
    path = Path(file)
    path.write_bytes(asbuilt.template_bytes(project, path.suffix, harness))
    return path


def import_asbuilt(
    folder: PathLike, file: PathLike, *, dry_run: bool = False, author: str | None = None
) -> AsBuiltImportResult:
    """Read the filled-in as-built sheet at `file` and keep its records in the project (the command
    `import-asbuilt`; `dry_run` changes nothing). A row about something the design does not have is
    refused with its reason, and then nothing is changed (`changed` false, `counts["refused"]`).
    A file that is not an as-built sheet raises `ImportError_`'s base, `HarnessError`. The import is
    recorded in `imports/records.json`; a project that keeps a journal enters the records in it with
    `author`. Takes the project lock unless `dry_run`."""
    path = Path(folder)
    with contextlib.ExitStack() as stack:
        if not dry_run:
            stack.enter_context(_locked(path))
        stack.enter_context(_as(author))
        project = _load(path)
        _writable(project)
        imp = asbuilt.read_import(project, Path(file), path)
        changed = False
        if not dry_run and imp.ops and imp.plan.bad_count == 0:
            History(project).execute("Import as-built records", imp.ops)
            _save_project(project, path)
            changed = True
    return asbuilt.AsBuiltImportResult(
        dry_run, changed, imp.plan.counts(), tuple(imp.plan.rows), tuple(imp.report.lines())
    )
