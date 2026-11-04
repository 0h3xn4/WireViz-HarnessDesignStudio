"""The results of the tool as plain data: small frozen dataclasses with `to_dict()`.

This is the one place where a result of `generate`, `drc`, `verify`, `export`, `validate` or
`config` is turned into data. The scripting interface (`harness_design_studio.api`) returns these
objects, and the command line prints `to_dict()` of the same objects with `--json`, so a script and
a shell pipeline cannot disagree. Nothing here computes a design result: every number comes from
the function the commands already call, and nothing in a record is a time, a user name or an
absolute path. No Qt.
"""

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from harness_design_studio.core.checks import Finding
from harness_design_studio.core.issues import Issue

if TYPE_CHECKING:
    from harness_design_studio.core.generate.engine import GenerationPlan
    from harness_design_studio.core.io.loader import LoadResult
    from harness_design_studio.core.model import Project
    from harness_design_studio.core.outputs.build import OutputSet
    from harness_design_studio.core.verify import VerifyReport


@dataclass(frozen=True)
class IssueRecord:
    """One problem found in the files or in a check: `severity` is "error", "warning" or "info"."""

    severity: str
    code: str
    message: str
    location: str | None = None  # a file of the project, relative to its folder
    object_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "severity": self.severity,
            "code": self.code,
            "message": self.message,
            "location": self.location,
            "object_id": self.object_id,
        }


@dataclass(frozen=True)
class FindingRecord:
    """One finding of the design rule check (`run_checks`). `waived` findings carry the reason."""

    id: str
    rule: str
    severity: str
    object_id: str
    title: str
    why: str
    sources: tuple[str, ...]
    can_waive: bool
    waived: bool
    waiver_justification: str
    waiver_changed: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "rule": self.rule,
            "severity": self.severity,
            "object_id": self.object_id,
            "title": self.title,
            "why": self.why,
            "sources": list(self.sources),
            "can_waive": self.can_waive,
            "waived": self.waived,
            "waiver_justification": self.waiver_justification,
            "waiver_changed": self.waiver_changed,
        }


@dataclass(frozen=True)
class ValidationResult:
    """What `validate` reports: the size of the project and every issue, sorted. `ok` is false
    when there is an error (the command line ends with exit code 1)."""

    ok: bool
    devices: int
    interfaces: int
    connectors: int
    harnesses: int
    errors: int
    warnings: int
    issues: tuple[IssueRecord, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "devices": self.devices,
            "interfaces": self.interfaces,
            "connectors": self.connectors,
            "harnesses": self.harnesses,
            "errors": self.errors,
            "warnings": self.warnings,
            "issues": [i.to_dict() for i in self.issues],
        }


@dataclass(frozen=True)
class GenerateResult:
    """What `generate` did. `ok` is false, and nothing was saved, when generation or the
    independent check found an error. The lists hold harness IDs (`kept_locks`: `connector.pin`)."""

    ok: bool
    saved: bool
    added: tuple[str, ...]
    changed: tuple[str, ...]
    unchanged: tuple[str, ...]
    removed: tuple[str, ...]
    frozen: tuple[str, ...]
    kept_locks: tuple[str, ...]
    findings: tuple[IssueRecord, ...]
    interfaces_checked: int
    wires_checked: int
    verify_issues: tuple[IssueRecord, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "saved": self.saved,
            "added": list(self.added),
            "changed": list(self.changed),
            "unchanged": list(self.unchanged),
            "removed": list(self.removed),
            "frozen": list(self.frozen),
            "kept_locks": list(self.kept_locks),
            "findings": [f.to_dict() for f in self.findings],
            "interfaces_checked": self.interfaces_checked,
            "wires_checked": self.wires_checked,
            "verify_issues": [i.to_dict() for i in self.verify_issues],
        }


@dataclass(frozen=True)
class CheckResult:
    """The design rule check: every finding, open or waived, errors first, then by ID. `ok` is
    false when an error is open (the command line `drc` ends with exit code 1)."""

    ok: bool
    model_hash: str  # the first 12 characters, as in the report and the outputs
    rules_run: int
    open_errors: int
    open_warnings: int
    open_notes: int
    waived: int
    placeholder_config: tuple[str, ...]
    findings: tuple[FindingRecord, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "model_hash": self.model_hash,
            "rules_run": self.rules_run,
            "open_errors": self.open_errors,
            "open_warnings": self.open_warnings,
            "open_notes": self.open_notes,
            "waived": self.waived,
            "placeholder_config": list(self.placeholder_config),
            "findings": [f.to_dict() for f in self.findings],
        }


@dataclass(frozen=True)
class VerifyResult:
    """The independent check of the harnesses against the interfaces (and, with `outputs=True`,
    of the outputs folder against the design). `stale` is true when the plans or the outputs are
    older than the design."""

    ok: bool
    interfaces_checked: int
    wires_checked: int
    stale: bool
    issues: tuple[IssueRecord, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "interfaces_checked": self.interfaces_checked,
            "wires_checked": self.wires_checked,
            "stale": self.stale,
            "issues": [i.to_dict() for i in self.issues],
        }


@dataclass(frozen=True)
class ExportedFile:
    """One output file: its path below the outputs folder, its size and its SHA-256."""

    path: str
    bytes: int
    sha256: str

    def to_dict(self) -> dict[str, Any]:
        return {"path": self.path, "bytes": self.bytes, "sha256": self.sha256}


@dataclass(frozen=True)
class ExportResult:
    """What `export` did. `written` is false when the outputs were refused: `blocked` then says
    why ("nothing_to_export" or "outputs_failed_check") and `issues` holds what the independent
    check found. `model_hash` is the first 12 characters, the same as in every file's stamp."""

    ok: bool
    written: bool
    blocked: str
    model_hash: str
    drawings_removed: bool
    files: tuple[ExportedFile, ...]
    issues: tuple[IssueRecord, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "written": self.written,
            "blocked": self.blocked,
            "model_hash": self.model_hash,
            "drawings_removed": self.drawings_removed,
            "file_count": len(self.files),
            "files": [f.to_dict() for f in self.files],
            "issues": [i.to_dict() for i in self.issues],
        }


@dataclass(frozen=True)
class ConfigValue:
    """One engineering value of `config/*.json`: where it is, what it is for, and what it is now.
    `value` is as stored (None: not set); `source` says where a set value comes from."""

    file: str
    key: str
    label: str
    unit: str
    kind: str  # "number", "choice", "pairs", "table" or "flag"
    choices: tuple[str, ...]
    what: str
    used_by: str
    value: Any
    display: str
    placeholder: bool  # the file is still marked as a placeholder: nobody has reviewed it
    source: str
    missing: bool
    optional: bool  # a value of a standard profile, not on the hand-over list
    locked: str | None  # why a release forbids changing it

    def to_dict(self) -> dict[str, Any]:
        return {
            "file": self.file,
            "key": self.key,
            "label": self.label,
            "unit": self.unit,
            "kind": self.kind,
            "choices": list(self.choices),
            "what": self.what,
            "used_by": self.used_by,
            "value": self.value,
            "display": self.display,
            "placeholder": self.placeholder,
            "source": self.source,
            "missing": self.missing,
            "optional": self.optional,
            "locked": self.locked,
        }


@dataclass(frozen=True)
class ConfigReport:
    """The engineering values in force (`get_config`). `ok` is true when every value of the
    hand-over list is set and valid, as `config` ends with exit code 0 then. `problems` are values
    that are set but not acceptable."""

    ok: bool
    set_count: int  # of the hand-over list (not the optional values)
    total: int
    values: tuple[ConfigValue, ...]
    problems: tuple[IssueRecord, ...]
    placeholder_files: tuple[str, ...]  # files of the hand-over list still marked as placeholders
    waiting_for_decision: tuple[str, ...]  # files that wait for an owner decision, not a value
    counterpart_pairs: int | None  # None: the table the tool ships with is used
    release_distinct_roles: bool
    comment_warnings: tuple[IssueRecord, ...] = ()  # stale `_about` comments (opt-in), a warning

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "set_count": self.set_count,
            "total": self.total,
            "values": [v.to_dict() for v in self.values],
            "problems": [p.to_dict() for p in self.problems],
            "placeholder_files": list(self.placeholder_files),
            "waiting_for_decision": list(self.waiting_for_decision),
            "counterpart_pairs": self.counterpart_pairs,
            "release_distinct_roles": self.release_distinct_roles,
            "comment_warnings": [w.to_dict() for w in self.comment_warnings],
        }

    def value(self, file: str, key: str) -> ConfigValue:
        """The entry for `config/<file>.json` and `key`; `KeyError` when there is none."""
        for v in self.values:
            if (v.file, v.key) == (file, key):
                return v
        raise KeyError(f"{file}.{key}")


def _plain(value: Any) -> Any:
    """Tuples as lists, so that a value is what JSON gives back."""
    if isinstance(value, tuple | list):
        return [_plain(v) for v in value]
    if isinstance(value, dict):
        return {k: _plain(v) for k, v in value.items()}
    return value


@dataclass(frozen=True)
class SettingRecord:
    """One setting the results depend on, with the value in force for a project. `origin` says where
    the value comes from: "project" (set in a file of `config/`), "default" (the tool's own, the
    behaviour before the setting existed) or "unset" (nothing). Same entry as `settings --json`."""

    id: str  # "<file>.<key>", for example "model.service_loops_per_wire"
    label: str
    unit: str
    value: Any
    origin: str
    placeholder: bool  # the file that holds it is still marked as not reviewed
    default: Any
    what: str
    used_by: str
    source: str
    range: str
    assumption: str  # the ID of the assumption this setting parameterises

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "unit": self.unit,
            "value": _plain(self.value),
            "origin": self.origin,
            "placeholder": self.placeholder,
            "default": _plain(self.default),
            "what": self.what,
            "used_by": self.used_by,
            "source": self.source,
            "range": self.range,
            "assumption": self.assumption,
        }


@dataclass(frozen=True)
class RuleInfo:
    """One design rule: what it checks, why it matters and how to fix a finding of it."""

    id: str
    severity: str
    topic: str
    why: str
    how: str
    can_waive: bool
    sources: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "severity": self.severity,
            "topic": self.topic,
            "why": self.why,
            "how": self.how,
            "can_waive": self.can_waive,
            "sources": list(self.sources),
        }


@dataclass(frozen=True)
class TemplateInfo:
    """An example project the tool ships with (`create_project` makes a project from it)."""

    name: str
    title: str
    summary: str

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "title": self.title, "summary": self.summary}


@dataclass(frozen=True)
class DerivationFiles:
    """What `write_derivations` wrote: the files (JSON, then CSV), how many derivations, and how
    many of them have no value yet because an input is not set."""

    files: tuple[Path, ...]
    count: int
    without_value: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "count": self.count,
            "without_value": self.without_value,
            "files": [p.name for p in self.files],
        }


@dataclass(frozen=True)
class DataFiles:
    """What `export_data` wrote: the files (by name, in order), the first 12 characters of the
    model hash they were made from, and the name of the run record when one was asked for."""

    files: tuple[str, ...]
    model_hash: str
    run_record: str = ""

    @property
    def count(self) -> int:
        return len(self.files)

    def to_dict(self) -> dict[str, Any]:
        return {
            "count": self.count,
            "model_hash": self.model_hash,
            "files": list(self.files),
            "run_record": self.run_record,
        }


# ---- from the objects of the tool ------------------------------------------------------------


def issue_records(issues: list[Issue]) -> tuple[IssueRecord, ...]:
    return tuple(
        IssueRecord(i.severity, i.code, i.message, i.location, i.object_id) for i in issues
    )


def finding_record(f: Finding) -> FindingRecord:
    return FindingRecord(
        f.id, f.rule, f.severity, f.object_id, f.title, f.why, tuple(f.sources), f.can_waive,
        f.waiver is not None, f.waiver.justification if f.waiver is not None else "",
        f.waiver_changed,
    )  # fmt: skip


def validation_result(loaded: LoadResult, extra: list[Issue]) -> ValidationResult:
    """The issues of loading and of the checks after it, sorted as `validate` prints them."""
    issues = sorted([*loaded.issues, *extra])
    errors = sum(i.severity == "error" for i in issues)
    p = loaded.project
    return ValidationResult(
        ok=errors == 0,
        devices=len(p.units),
        interfaces=len(p.interfaces),
        connectors=len(p.all_connectors()),
        harnesses=len(p.harnesses),
        errors=errors,
        warnings=sum(i.severity == "warning" for i in issues),
        issues=issue_records(issues),
    )


def generate_result(plan: GenerationPlan, report: VerifyReport, saved: bool) -> GenerateResult:
    r = plan.report
    return GenerateResult(
        ok=not r.errors and report.ok,
        saved=saved,
        added=tuple(r.added),
        changed=tuple(r.changed),
        unchanged=tuple(r.unchanged),
        removed=tuple(r.removed),
        frozen=tuple(r.frozen),
        kept_locks=tuple(r.kept_locks),
        findings=tuple(
            IssueRecord(f.severity, f.code, f.message, None, f.object_id) for f in r.findings
        ),
        interfaces_checked=report.interfaces_checked,
        wires_checked=report.wires_checked,
        verify_issues=issue_records(report.issues),
    )


def check_result(project: Project, found: list[Finding]) -> CheckResult:
    """`found` is what `drc` prints: the findings of the logical layer and of the rules, errors
    first, then by ID."""
    from harness_design_studio.core.drc import all_rules
    from harness_design_studio.core.io.layout import model_hash

    open_ = [f for f in found if f.waiver is None]
    return CheckResult(
        ok=not any(f.severity == "error" for f in open_),
        model_hash=model_hash(project)[:12],
        rules_run=len(all_rules(project)),
        open_errors=sum(f.severity == "error" for f in open_),
        open_warnings=sum(f.severity == "warning" for f in open_),
        open_notes=sum(f.severity == "info" for f in open_),
        waived=len(found) - len(open_),
        placeholder_config=tuple(sorted(n for n, c in project.config.items() if c.placeholder)),
        findings=tuple(finding_record(f) for f in found),
    )


def verify_result(report: VerifyReport) -> VerifyResult:
    return VerifyResult(
        report.ok, report.interfaces_checked, report.wires_checked, report.stale,
        issue_records(report.issues),
    )  # fmt: skip


def export_result(
    built: OutputSet, issues: list[Issue], *, drawings_removed: bool = False
) -> ExportResult:
    """An export that was written: every file with its size and SHA-256, in path order."""
    files = tuple(
        ExportedFile(rel, len(data), hashlib.sha256(data).hexdigest())
        for rel, data in sorted(built.files.items())
    )
    return ExportResult(
        True, True, "", built.stamp.short, drawings_removed, files, issue_records(issues)
    )


def export_refused(
    reason: str, model_hash: str = "", issues: list[Issue] | None = None
) -> ExportResult:
    """An export that was not written: `reason` is "nothing_to_export" or "outputs_failed_check"."""
    return ExportResult(False, False, reason, model_hash, False, (), issue_records(issues or []))


def config_report(project: Project) -> ConfigReport:
    """The engineering values in force, and what is wrong with them (see `config`)."""
    from harness_design_studio.core import configcheck, counterparts
    from harness_design_studio.core.vcs import roles

    todo, problems = configcheck.missing(project), configcheck.validate(project)
    needed = {n.file for n in configcheck.NEEDS}
    decisions = ("segmentation", "titleblock")
    table = project.config.get(counterparts.CONFIG_FILE)
    pairs = table.values.get(counterparts.CONFIG_KEY) if table is not None else None
    values = configcheck.engineering_values(project, include_optional=True)
    return ConfigReport(
        ok=not todo and not problems,
        set_count=len(configcheck.NEEDS) - len(todo),
        total=len(configcheck.NEEDS),
        values=tuple(
            ConfigValue(
                v.file, v.key, v.label, v.unit, v.kind, tuple(v.choices), v.what, v.used_by,
                v.value, v.display, v.placeholder, v.source, v.missing, v.optional, v.locked,
            )
            for v in values
        ),
        problems=issue_records(problems),
        placeholder_files=tuple(
            sorted(n for n, c in project.config.items() if c.placeholder and n in needed)
        ),
        waiting_for_decision=tuple(
            sorted(
                n
                for n, c in project.config.items()
                if c.placeholder and n in decisions and n not in needed
            )
        ),
        counterpart_pairs=(
            len(pairs)
            if isinstance(pairs, list) and counterparts.check_pairs(pairs) is None
            else None
        ),
        release_distinct_roles=roles.distinct_roles_on(project),
        comment_warnings=issue_records(configcheck.annotation_issues(project)),
    )  # fmt: skip


def setting_records(project: Project) -> list[SettingRecord]:
    """Every setting with the value in force, in the order of `settings`."""
    from harness_design_studio.core import settings

    return [
        SettingRecord(
            r.setting.id, r.setting.label, r.setting.unit, r.value, r.origin, r.placeholder,
            r.setting.default, r.setting.what, r.setting.used_by, r.setting.source,
            r.setting.range, r.setting.assumption,
        )
        for r in settings.rows(project)
    ]  # fmt: skip


def rule_infos() -> list[RuleInfo]:
    from harness_design_studio.core.drc.rules import RULES

    return [
        RuleInfo(r.id, r.severity, r.topic, r.why, r.how, r.can_waive, tuple(r.sources))
        for r in RULES
    ]


def template_infos() -> list[TemplateInfo]:
    from harness_design_studio.core.templates import TEMPLATES

    return [TemplateInfo(t.name, t.title, t.summary) for t in TEMPLATES]


# ---- the change journal, overrides and deviations (S4) -------------------------------------------
#
# Unlike the records above, a journal record holds a time and a name: they are in the project's
# `journal.json`, so the same project still gives the same record.


@dataclass(frozen=True)
class JournalRecord:
    """One entry of the change journal (`get_journal`)."""

    seq: int
    when: str
    author: str
    kind: str
    object: str
    field: str
    old: Any
    new: Any
    reason: str
    tool_version: str
    chain: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "seq": self.seq, "when": self.when, "author": self.author, "kind": self.kind,
            "object": self.object, "field": self.field, "old": self.old, "new": self.new,
            "reason": self.reason, "tool_version": self.tool_version, "chain": self.chain,
        }  # fmt: skip


@dataclass(frozen=True)
class JournalReport:
    """The journal of a project: `has_journal` is false for a project that keeps none."""

    has_journal: bool
    entries: tuple[JournalRecord, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "has_journal": self.has_journal,
            "count": len(self.entries),
            "entries": [e.to_dict() for e in self.entries],
        }


@dataclass(frozen=True)
class OverrideRecord:
    """A value of a wire set by hand: the field (`gauge_awg`, `part_id`, `colour`, `length_m`), the
    value now on the wire and the reason given."""

    field: str
    value: Any
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {"field": self.field, "value": self.value, "reason": self.reason}


@dataclass(frozen=True)
class OverrideResult:
    """What `set_override`, `clear_override` and `get_overrides` report for a wire. `action` is
    "set", "clear" or "show"; `changed` is false when nothing had to be written. `derivation` is
    the derivation *Overridden by the engineer* (None when the wire has no override)."""

    wire: str
    action: str
    changed: bool
    overrides: tuple[OverrideRecord, ...]
    derivation: Any = None  # a core.derive.Derivation

    def to_dict(self) -> dict[str, Any]:
        return {
            "wire": self.wire,
            "action": self.action,
            "changed": self.changed,
            "overrides": [o.to_dict() for o in self.overrides],
            "derivation": self.derivation.to_dict() if self.derivation is not None else None,
        }


@dataclass(frozen=True)
class DeviationRecord:
    """An error of an electrical rule that a person accepted, with the reason and, when the project
    keeps a journal, `by NAME on DATE`."""

    id: str
    rule: str
    title: str
    reason: str
    by: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id, "rule": self.rule, "title": self.title, "reason": self.reason,
            "by": self.by,
        }  # fmt: skip


@dataclass(frozen=True)
class DeviationReport:
    """The deviations of a project, or the one just recorded or taken back (`action` is "list",
    "record" or "remove"; `finding` is its finding ID or empty)."""

    action: str
    finding: str
    deviations: tuple[DeviationRecord, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "finding": self.finding,
            "count": len(self.deviations),
            "deviations": [d.to_dict() for d in self.deviations],
        }


def journal_report(project: Project, object_id: str | None = None, since: int = 0) -> JournalReport:
    from harness_design_studio.core import journal

    entries = journal.entries_for(project, object_id, since)
    return JournalReport(
        project.journal is not None,
        tuple(JournalRecord(**e.model_dump(mode="json")) for e in entries),
    )


def override_records(project: Project, wire_id: str) -> tuple[OverrideRecord, ...]:
    from harness_design_studio.core.wires import find_wire

    _h, w = find_wire(project, wire_id)
    return tuple(OverrideRecord(f, getattr(w, f), w.overrides[f]) for f in sorted(w.overrides))


def override_result(project: Project, wire_id: str, action: str, changed: bool) -> OverrideResult:
    from harness_design_studio.core.derive import explain_wire

    found = [d for d in explain_wire(project, wire_id) if d.id == "wire-override"]
    return OverrideResult(
        wire_id, action, changed, override_records(project, wire_id), found[0] if found else None
    )


def deviation_records(project: Project) -> tuple[DeviationRecord, ...]:
    from harness_design_studio.core import checks, journal
    from harness_design_studio.core.drc import run as run_rules

    found = {f.id: f for f in [*checks.find(project), *run_rules(project)]}
    marked = sorted((f for f in found.values() if f.deviation), key=lambda f: f.id)
    return tuple(
        DeviationRecord(
            f.id,
            f.rule,
            f.title,
            f.waiver.justification if f.waiver is not None else "",
            journal.who_and_when(project, f.id),
        )
        for f in marked
    )
