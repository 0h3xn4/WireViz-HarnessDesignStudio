"""Logical-layer findings shown in the Problems panel and the to-do list.

M4 adds the full design rule check; these are the rules the block-diagram editor needs now.
Every finding says what is wrong, why it matters and (when safe) offers a fix.
"""

import hashlib
import re
from dataclasses import dataclass

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
                    True, project.waivers.get(fid),
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
    return sorted(out, key=lambda f: (order[f.severity], f.id))


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
                f"{n} unit{'s are' if n > 1 else ' is'} not connected to anything",
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
