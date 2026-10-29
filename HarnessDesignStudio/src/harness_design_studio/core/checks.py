"""Logical-layer findings shown in the Problems panel and the to-do list.

M4 adds the full design rule check; these are the rules the block-diagram editor needs now.
Every finding says what is wrong, why it matters and (when safe) offers a fix.
"""

import hashlib
import re
from collections.abc import Iterable
from dataclasses import dataclass, replace

from . import edit
from .commands import Op, Put
from .issues import Severity
from .model import Project, Waiver, evolve


@dataclass(frozen=True)
class Finding:
    id: str  # stable: "<rule>.<object>"
    rule: str
    severity: Severity
    object_id: str
    title: str
    why: str
    fix_label: str | None = None
    can_waive: bool = False
    waiver: Waiver | None = None  # set when the finding has been waived
    sources: tuple[str, ...] = ()  # IDs of the standard requirements the rule serves
    waiver_changed: bool = False  # a waiver exists but the finding changed since: it does not apply

    @property
    def why_cited(self) -> str:
        """The explanation followed by the requirement IDs (reports and exports)."""
        return f"{self.why} Requirement: {', '.join(self.sources)}." if self.sources else self.why


@dataclass(frozen=True)
class Todo:
    text: str
    kind: str  # "unit" | "interface" | "tab"
    target: str


def safe_id(text: str) -> str:
    """`text` as a valid ID: other characters become '_' and a short hash keeps names apart
    (signal names such as TX+ are not allowed in IDs)."""
    cleaned = re.sub(r"[^A-Za-z0-9_.-]", "_", text).rstrip(".") or "x"
    if cleaned == text:
        return text
    return cleaned[:52] + "." + hashlib.sha256(text.encode()).hexdigest()[:8]


def finding_hash(finding: Finding) -> str:
    """A short hash of what a finding says (its rule and its statement of this one problem), kept in
    a waiver so that a finding that changes later is not silently still waived."""
    return hashlib.sha256(f"{finding.rule}\n{finding.title}".encode()).hexdigest()[:12]


def with_waiver(project: Project, finding: Finding) -> Finding:
    """`finding` with its waiver set, when one exists and still fits the finding. A waiver that
    records a `finding_hash` which no longer matches does not apply (`waiver_changed` is set)."""
    waiver = project.waivers.get(finding.id)
    if waiver is None or not finding.can_waive:
        return finding
    if waiver.finding_hash is not None and waiver.finding_hash != finding_hash(finding):
        return replace(finding, waiver_changed=True)
    return replace(finding, waiver=waiver)


def finding_id(rule: str, object_id: str) -> str:
    raw = safe_id(f"{rule}.{object_id}")
    if len(raw) <= 64:
        return raw
    return raw[:52] + "." + hashlib.sha256(raw.encode()).hexdigest()[:8]


def _nominal_end(project: Project, interface_id: str) -> str | None:
    i = project.interfaces[interface_id]
    for e in i.endpoints:
        unit = project.units.get(e.unit_id)  # missing in a project loaded with errors
        if unit is not None and unit.side == "nominal":
            return e.unit_id
    return None


def find(project: Project) -> list[Finding]:
    """All findings, waived ones included (with `waiver` set), sorted by severity then ID."""
    out: list[Finding] = []
    connected: set[str] = set()
    for i in project.interfaces.values():
        units = [project.units[e.unit_id] for e in i.endpoints if e.unit_id in project.units]
        connected.update(u.id for u in units)
        sides = {u.side for u in units}
        if {"nominal", "redundant"} <= sides:
            nominal = _nominal_end(project, i.id)
            fid = finding_id("cross-strap", i.id)
            out.append(
                Finding(
                    fid, "cross-strap", "warning", i.id,
                    f"{i.id} connects the nominal chain to the redundant chain",
                    "One unit is nominal and the other redundant. A cross-strap like this means one failure "
                    "could affect both chains, so reviewers will ask about it.",
                    f"Connect to a redundant copy of {nominal}" if nominal else None,
                    True, None,
                )
            )  # fmt: skip
        if any(e.connector_id is None for e in i.endpoints):
            out.append(
                Finding(
                    finding_id("no-connector", i.id), "no-connector", "info", i.id,
                    f"{i.id} has no connector chosen on at least one end",
                    "Without connectors the interface cannot become wires. The tool can choose free connectors for you.",
                    "Choose connectors automatically",
                )
            )  # fmt: skip
        elif any(e.auto for e in i.endpoints):
            out.append(
                Finding(
                    finding_id("unconfirmed", i.id), "unconfirmed", "info", i.id,
                    f"{i.id} uses connectors the tool chose for you",
                    "Auto-filled choices are marked until a person confirms them, so nobody assumes they were reviewed.",
                    "Confirm connectors",
                )
            )  # fmt: skip
    for link in project.links.values():  # a connection between two connectors joins the devices
        for cid in (link.a_connector, link.b_connector):
            c = project.connectors.get(cid)
            if c is not None and c.unit_id:
                connected.add(c.unit_id)
    for u in project.units.values():
        if u.id not in connected:
            out.append(
                Finding(
                    finding_id("isolated", u.id), "isolated", "info", u.id,
                    f"{u.id} is not connected to anything yet",
                    "Units without interfaces get no wires, so they will not appear in any harness plan.",
                )
            )  # fmt: skip
    order = {"error": 0, "warning": 1, "info": 2}
    return sorted((with_waiver(project, f) for f in out), key=lambda f: (order[f.severity], f.id))


def open_findings(project: Project) -> list[Finding]:
    return [f for f in find(project) if f.waiver is None]


def fix_ops(project: Project, finding: Finding) -> tuple[list[Op], str]:
    """Operations that resolve the finding, and a one-line message for the user."""
    if finding.rule == "cross-strap":
        ops, tid = edit.ops_complete_chain(project, finding.object_id)
        return (
            ops,
            f"Connected {finding.object_id} to {tid}. Both ends are now on the redundant chain.",
        )
    if finding.rule == "unconfirmed":
        return edit.ops_confirm_interface(
            project, finding.object_id
        ), f"Confirmed the connectors of {finding.object_id}."
    if finding.rule == "no-connector":
        return _assign_connectors(
            project, finding.object_id
        ), f"Chose connectors for {finding.object_id}."
    from . import drc

    fixed = drc.fix_ops(project, finding)
    if fixed is not None:
        return fixed
    raise edit.EditError("There is no one-click fix for this finding.")


def _assign_connectors(project: Project, interface_id: str) -> list[Op]:
    i = project.interfaces[interface_id]
    eps = []
    taken: set[str] = set()
    for e in i.endpoints:
        if e.connector_id is None:
            free = [
                c for c in edit.free_connectors(project, e.unit_id, i.type_id) if c.id not in taken
            ]
            if not free:
                raise edit.EditError(f"{e.unit_id} has no free connector for {i.type_id}.")
            taken.add(free[0].id)
            eps.append(evolve(e, connector_id=free[0].id, auto=True))
        else:
            eps.append(e)
    return [Put("interfaces", evolve(i, endpoints=eps))]


def waive_op(finding: Finding, justification: str) -> Op:
    if not finding.can_waive:
        raise edit.EditError("This finding cannot be waived.")
    try:
        waiver = Waiver(
            id=finding.id,
            rule=finding.rule,
            object_id=safe_id(finding.object_id),
            justification=justification.strip(),
            finding_hash=finding_hash(finding),
        )
    except ValueError as exc:  # a justification that is too short or too long, for example
        raise edit.EditError(
            "The reason is not acceptable: it needs at least 10 characters, no more than 2000, and no control characters."
        ) from exc
    return Put("waivers", waiver)


def todos(project: Project) -> list[Todo]:
    return todos_from(find(project))


def todos_from(all_findings: list[Finding]) -> list[Todo]:
    findings = [f for f in all_findings if f.waiver is None]
    out: list[Todo] = []
    isolated = [f for f in findings if f.rule == "isolated"]
    if isolated:
        n = len(isolated)
        out.append(
            Todo(
                f"{n} device{'s are' if n > 1 else ' is'} not connected to anything",
                "unit",
                isolated[0].object_id,
            )
        )
    missing = [f for f in findings if f.rule == "no-connector"]
    if missing:
        n = len(missing)
        out.append(
            Todo(
                f"{n} interface{'s have' if n > 1 else ' has'} no connector assigned",
                "interface",
                missing[0].object_id,
            )
        )
    auto = [f for f in findings if f.rule == "unconfirmed"]
    if auto:
        n = len(auto)
        out.append(
            Todo(
                f"{n} auto-filled connector assignment{'s' if n > 1 else ''} to review",
                "interface",
                auto[0].object_id,
            )
        )
    warnings = [f for f in findings if f.severity == "warning"]
    if warnings:
        n = len(warnings)
        out.append(Todo(f"{n} warning{'s' if n > 1 else ''} to fix or waive", "tab", "problems"))
    return out


# ---- "Fix all": every one-click fix as one transaction (SH-24) ---------------------------------

# findings that are put right by generating the harnesses again: one plan covers all of them
REGENERATE_RULES: frozenset[str] = frozenset({"signal-unassigned", "verify-mismatch"})


@dataclass(frozen=True)
class FixAllPlan:
    """What "Fix all" does: the operations in the order they were worked out (to run as one
    transaction), the findings they resolve, and the findings it leaves alone with the reason."""

    ops: list[Op]
    fixed: list[Finding]
    skipped: list[tuple[Finding, str]]


# findings whose fix records that a person looked at something: "Fix all" never does that for them
# (the button on the finding itself still does)
PERSON_ONLY_RULES: frozenset[str] = frozenset({"unconfirmed"})


def fixable(findings: Iterable[Finding]) -> list[Finding]:
    """The open findings "Fix all" puts right in one step: those that have a one-click fix, in the
    order given, except the ones only a person may settle (confirming a connector the tool chose)."""
    return [
        f for f in findings if f.waiver is None and f.fix_label and f.rule not in PERSON_ONLY_RULES
    ]


def fix_summary(findings: Iterable[Finding]) -> str:
    """What a "Fix all" over these findings does, by kind of fix, biggest first: "Confirm
    connectors (40), Choose connectors automatically (2)". Empty when nothing has a fix."""
    counts: dict[str, int] = {}
    for f in fixable(findings):
        counts[f.fix_label or ""] = counts.get(f.fix_label or "", 0) + 1
    ordered = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    return ", ".join(f"{label} ({n})" for label, n in ordered)


def fix_all_plan(project: Project, findings: Iterable[Finding]) -> FixAllPlan:
    """Work out every one-click fix of `findings`. The fixes are made one after the other on a
    scratch copy of the project, so a later fix sees the connectors an earlier one took. A fix that
    a release lock refuses, or that no longer applies after the ones before it, is left out and
    named in `skipped`. Fixes that regenerate the harnesses come last and count once. The project
    itself is not changed: run `ops` through `History` as one step."""
    from .commands import apply_ops
    from .errors import HarnessError, TransactionError
    from .vcs.locks import check_locks

    def reason(exc: HarnessError) -> str:
        if isinstance(exc, TransactionError) and exc.problems:
            return exc.problems[0]
        return str(exc)

    work = edit.clone_with(project, [])
    ops: list[Op] = []
    fixed: list[Finding] = []
    skipped: list[tuple[Finding, str]] = []
    todo = fixable(findings)
    for f in (f for f in todo if f.rule not in REGENERATE_RULES):
        try:
            made, _message = fix_ops(work, f)
            check_locks(project, made)
        except (HarnessError, KeyError) as exc:
            skipped.append((f, reason(exc) if isinstance(exc, HarnessError) else str(exc)))
            continue
        apply_ops(work, made)
        ops.extend(made)
        fixed.append(f)
    again = [f for f in todo if f.rule in REGENERATE_RULES]
    if again:
        try:
            made, _message = fix_ops(work, again[0])
            check_locks(project, made)
        except (HarnessError, KeyError) as exc:
            why = reason(exc) if isinstance(exc, HarnessError) else str(exc)
            skipped.extend((f, why) for f in again)
        else:
            ops.extend(made)
            fixed.extend(again)
    return FixAllPlan(ops, fixed, skipped)
