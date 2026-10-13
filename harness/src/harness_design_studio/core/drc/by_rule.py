"""One result per design rule, for the Checks view: pass, fail, not checked or pending.

This only groups what the rules already found (`drc.run` and its `unchecked-config` notes) and
says which configuration values keep a rule silent. It runs no rule logic of its own, so the
findings, their IDs and the report files are untouched. Give it the findings of a check that
already ran (the worker process returns exactly `drc.run`'s list) and no rule runs twice.

States:
  fail         the rule found at least one problem that nobody has waived
  pending      the rule is silent until a value is supplied (a configuration file and key)
  not_checked  the rule ran but could not look at everything: a part without a rating, a wire
               without a gauge, or an analysis the tool cannot do
  pass         the rule ran, found nothing, and nothing was skipped
A rule with problems stays "fail" even when some of its objects were skipped; the notes say so.
"""

from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

from harness_design_studio.core import configcheck
from harness_design_studio.core.checks import Finding
from harness_design_studio.core.issues import Severity
from harness_design_studio.core.model import Project

from . import run as _drc_run
from .base import cfg, number
from .rules import RULES, _category_pairs, _emc_pairs

Status = Literal["pass", "fail", "not_checked", "pending"]
MissingKind = Literal["config", "data", "analysis"]
UNCHECKED = "unchecked-config"
VERIFY = "verify-mismatch"


@dataclass(frozen=True)
class MissingValue:
    """What a rule is waiting for. A configuration value names its file and key; a data gap
    (a part rating, a wire gauge) or an outside analysis carries the sentence the check gave."""

    kind: MissingKind
    what: str
    file: str | None = None
    key: str | None = None
    used_by: str = ""
    optional: bool = False  # a value of a standard profile, not on the hand-over list

    @property
    def where(self) -> str:
        return f"config/{self.file}.json: {self.key}" if self.file and self.key else ""


@dataclass(frozen=True)
class RuleResult:
    rule_id: str
    topic: str
    severity: Severity
    status: Status
    count: int  # open findings (waived ones are not counted)
    waived: int
    object_ids: tuple[str, ...]  # offending objects of the open findings, each once
    finding_ids: tuple[str, ...]  # IDs of the open findings, in the order `drc.run` gave them
    findings: tuple[Finding, ...]  # open and waived
    missing: tuple[MissingValue, ...] = ()
    notes: tuple[str, ...] = ()  # what the check said it did not check, word for word
    placeholder_files: tuple[str, ...] = ()  # files the rule reads that are still placeholders
    sources: tuple[str, ...] = ()


@dataclass(frozen=True)
class Summary:
    total: int
    passed: int
    failed: int
    not_checked: int
    pending: int
    pending_values: int  # distinct required values that keep rules pending or unchecked
    pending_optional_values: int  # the same for optional values of the standard profiles


# Configuration a rule reads, whether or not it is set (to name placeholder files).
READS: dict[str, tuple[tuple[str, str], ...]] = {
    "current-over-contact": (("derating", "contact_current_factor"),),
    "current-over-wire": (
        ("derating", "ampacity_a_by_awg"), ("derating", "bundle_derating"),
        ("derating", "temperature_derating"), ("derating", "bundle_factor_by_count"),
    ),
    "voltage-drop": (("derating", "max_voltage_drop_v"), ("generation", "conductor_resistivity_ohm_m")),
    "spare-pins-low": (("derating", "spare_pin_fraction"),),
    "shield-unterminated": (("generation", "shield_end_a"), ("generation", "shield_end_b")),
    "shield-wrong-end": (("generation", "shield_end_a"), ("generation", "shield_end_b")),
    "category-mixed": (("segregation", "category_pairs_to_separate"),),
    "emc-mixed": (("emc", "conflicting_class_pairs"),),
    "connector-voltage": (
        ("derating", "connector_voltage_factor_withstand"), ("derating", "connector_voltage_factor_rated"),
    ),
    "wire-voltage": (("derating", "wire_voltage_factor"),),
    "temperature-margin": (
        ("derating", "max_ambient_temperature_c"), ("derating", "connector_temperature_margin_c"),
        ("derating", "wire_temperature_margin_c"),
    ),
    "mating-cycles": (("derating", "max_mating_cycles"),),
    "shield-bonding": (("emc", "shield_bonding"),),
    "shield-parts": (("emc", "shield_bonding"),),
    "emc-class-split": (("emc", "same_class_one_bundle"),),
    "power-return-adjacent": (("generation", "power_return_gap_pins"),),
    "bundle-current": (("derating", "ampacity_a_by_awg"), ("derating", "bundle_factor_by_count")),
}  # fmt: skip


def _v(project: Project, file: str, key: str) -> object:
    return cfg(project, file).get(key)


def _unset(project: Project, *pairs: tuple[str, str]) -> list[tuple[str, str]]:
    return [(f, k) for f, k in pairs if _v(project, f, k) is None]


def _current_wire(project: Project) -> list[tuple[str, str]]:
    from .rules import _bundle_table_given

    d = cfg(project, "derating")
    out = _unset(project, ("derating", "ampacity_a_by_awg"))
    if d.get("bundle_derating") is None and not _bundle_table_given(d):
        out.append(("derating", "bundle_derating"))
    return out + _unset(project, ("derating", "temperature_derating"))


def _shield_unterminated(project: Project) -> list[tuple[str, str]]:
    pairs = (("generation", "shield_end_a"), ("generation", "shield_end_b"))
    gone = _unset(project, *pairs)
    return gone if len(gone) == 2 else []  # one of the two is enough for this rule


def _temperature(project: Project) -> list[tuple[str, str]]:
    margins = (
        ("derating", "connector_temperature_margin_c"),
        ("derating", "wire_temperature_margin_c"),
    )
    out = _unset(project, ("derating", "max_ambient_temperature_c"))
    gone = _unset(project, *margins)
    return out + (gone if len(gone) == 2 else [])


def _connector_voltage(project: Project) -> list[tuple[str, str]]:
    pairs = (
        ("derating", "connector_voltage_factor_withstand"),
        ("derating", "connector_voltage_factor_rated"),
    )
    gone = _unset(project, *pairs)
    return gone if len(gone) == 2 else []


def _gap(project: Project) -> list[tuple[str, str]]:
    gap = number(_v(project, "generation", "power_return_gap_pins"))
    return [] if gap is not None and 1 <= gap <= 1000 else [("generation", "power_return_gap_pins")]


def _is(file: str, key: str, value: object) -> Callable[[Project], list[tuple[str, str]]]:
    return lambda p: [] if _v(p, file, key) == value else [(file, key)]


# The values that keep a rule silent, exactly as the rule's own first lines test them.
GATES: dict[str, Callable[[Project], list[tuple[str, str]]]] = {
    "current-over-contact": lambda p: _unset(p, ("derating", "contact_current_factor")),
    "current-over-wire": _current_wire,
    "voltage-drop": lambda p: _unset(
        p, ("derating", "max_voltage_drop_v"), ("generation", "conductor_resistivity_ohm_m")
    ),
    "spare-pins-low": lambda p: _unset(p, ("derating", "spare_pin_fraction")),
    "shield-unterminated": _shield_unterminated,
    "shield-wrong-end": lambda p: _unset(
        p, ("generation", "shield_end_a"), ("generation", "shield_end_b")
    ),
    "category-mixed": lambda p: [] if _category_pairs(p) else [("segregation", "category_pairs_to_separate")],
    "emc-mixed": lambda p: [] if _emc_pairs(p) else [("emc", "conflicting_class_pairs")],
    "connector-voltage": _connector_voltage,
    "wire-voltage": lambda p: _unset(p, ("derating", "wire_voltage_factor")),
    "temperature-margin": _temperature,
    "mating-cycles": lambda p: _unset(p, ("derating", "max_mating_cycles")),
    "shield-bonding": _is("emc", "shield_bonding", "both_ends_backshell"),
    "shield-parts": lambda p: _unset(p, ("emc", "shield_bonding")),
    "emc-class-split": _is("emc", "same_class_one_bundle", True),
    "power-return-adjacent": _gap,
    "bundle-current": lambda p: _unset(
        p, ("derating", "ampacity_a_by_awg"), ("derating", "bundle_factor_by_count")
    ),
}  # fmt: skip

# Which rules an `unchecked-config` note belongs to (the note's object ID is the key), and how it
# is shown. "config": a value the note names; "data": a gap in the design data; "analysis": work
# outside the tool. Notes about a value that keeps a rule silent need no row of their own: the
# gate already reports that value.
Note = tuple[tuple[str, ...], MissingKind, tuple[str, str] | None]
NOTES: dict[str, Note] = {
    "derating": (("current-over-contact", "current-over-wire"), "config", None),
    "voltage-drop": (("voltage-drop",), "config", None),
    "grounding": (("shield-unterminated", "shield-wrong-end"), "config", None),
    "separation": (("category-mixed",), "config", None),
    "emc": (("emc-mixed",), "config", None),
    "spare-pins": (("spare-pins-low",), "config", None),
    "temperature": (("temperature-margin",), "config", None),
    "derating-gauge": (("current-over-wire", "bundle-current"), "config", ("derating", "ampacity_a_by_awg")),
    "bundle-factor": (("current-over-wire", "bundle-current"), "config", ("derating", "bundle_factor_by_count")),
    "temperature-connector-margin": (("temperature-margin",), "config", ("derating", "connector_temperature_margin_c")),
    "temperature-wire-margin": (("temperature-margin",), "config", ("derating", "wire_temperature_margin_c")),
    "wire-gauge": (("current-over-wire",), "data", None),
    "contact-rating": (("current-over-contact",), "data", None),
    "voltage-drop-wires": (("voltage-drop",), "data", None),
    "connector-voltage": (("connector-voltage",), "data", None),
    "wire-voltage": (("wire-voltage",), "data", None),
    "mating-cycles": (("mating-cycles",), "data", None),
    "temperature-connector-parts": (("temperature-margin",), "data", None),
    "temperature-wire-parts": (("temperature-margin",), "data", None),
    "shield-parts": (("shield-parts",), "data", None),
    "thermal-analysis": (("temperature-margin",), "analysis", None),
    "bundle-separation": (("emc-class-split", "shield-bonding"), "analysis", None),
    "partial-load": (("bundle-current",), "analysis", None),
}  # fmt: skip
_GATE_NOTES = frozenset(
    {"derating", "voltage-drop", "grounding", "separation", "emc", "spare-pins", "temperature"}
)


def _run(project: Project) -> list[Finding]:
    return _drc_run(project)


def _missing_config(project: Project, file: str, key: str) -> MissingValue:
    need = configcheck.need_for(file, key)
    required = any((n.file, n.key) == (file, key) for n in configcheck.NEEDS)
    return MissingValue(
        "config",
        need.what if need else key,
        file,
        key,
        need.used_by if need else "",
        optional=not required,
    )


def run_by_rule(project: Project, findings: list[Finding] | None = None) -> list[RuleResult]:
    """A result for each rule of `RULES`, in report order; a row for `verify-mismatch` follows
    only when the independent check found something. `findings` is the list `drc.run` gave (or
    the worker process sent back); without it the check runs here."""
    found = findings if findings is not None else _run(project)
    by_rule: dict[str, list[Finding]] = defaultdict(list)
    for f in found:
        by_rule[f.rule].append(f)
    notes: dict[str, list[tuple[str, str]]] = defaultdict(list)  # rule -> (note key, sentence)
    unowned: list[str] = []
    for f in by_rule.get(UNCHECKED, []):
        entry = NOTES.get(f.object_id)
        if entry is None:
            unowned.append(f.title)
            continue
        for rule_id in entry[0]:
            notes[rule_id].append((f.object_id, f.title))
    out = [
        _result(project, r.id, r.topic, r.severity, r.sources, by_rule, notes, unowned)
        for r in RULES
    ]
    if by_rule.get(VERIFY):
        out.append(
            _result(project, VERIFY, "Independent verification", "error", (), by_rule, notes, [])
        )
    return out


def _result(
    project: Project,
    rule_id: str,
    topic: str,
    severity: Severity,
    sources: tuple[str, ...],
    by_rule: dict[str, list[Finding]],
    notes: dict[str, list[tuple[str, str]]],
    unowned: list[str],
) -> RuleResult:
    allf = by_rule.get(rule_id, [])
    open_ = [f for f in allf if f.waiver is None]
    objects = tuple(dict.fromkeys(f.object_id for f in open_))
    gate = GATES.get(rule_id)
    pending = [_missing_config(project, f, k) for f, k in (gate(project) if gate else [])]
    seen_notes: list[str] = []
    missing = list(pending)
    for key, sentence in notes.get(rule_id, []):
        if key in _GATE_NOTES and pending:
            seen_notes.append(sentence)  # already explained by the missing values
            continue
        if key in _GATE_NOTES:
            continue  # the rule has what it needs; the note was about another rule
        _rules, kind, ref = NOTES[key]
        if sentence not in seen_notes:
            seen_notes.append(sentence)
        missing.append(_missing_config(project, *ref) if ref else MissingValue(kind, sentence))
    if rule_id == UNCHECKED:
        seen_notes = list(unowned)
        status: Status = "not_checked" if unowned else "pass"
        missing = [MissingValue("analysis", s) for s in unowned]
        count = len(open_)
    else:
        count = len(open_)
        if open_:
            status = "fail"
        elif pending:
            status = "pending"
        elif seen_notes:
            status = "not_checked"
        else:
            status = "pass"
    files = sorted(
        {
            f
            for f, k in READS.get(rule_id, ())
            if (c := project.config.get(f)) is not None and c.placeholder
        }
    )
    return RuleResult(
        rule_id, topic, severity, status, count, len(allf) - len(open_), objects,
        tuple(f.id for f in open_), tuple(allf), tuple(_unique(missing)), tuple(seen_notes),
        tuple(files), sources,
    )  # fmt: skip


def _unique(values: list[MissingValue]) -> list[MissingValue]:
    return list(dict.fromkeys(values))


def summary(results: list[RuleResult]) -> Summary:
    n: dict[str, int] = defaultdict(int)
    for r in results:
        n[r.status] += 1
    config = {(m.file, m.key, m.optional) for r in results for m in r.missing if m.kind == "config"}
    return Summary(
        len(results), n["pass"], n["fail"], n["not_checked"], n["pending"],
        sum(1 for *_x, optional in config if not optional),
        sum(1 for *_x, optional in config if optional),
    )  # fmt: skip
