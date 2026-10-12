"""Design rule check (DRC): `run(project)` returns every finding with waivers applied."""

from dataclasses import replace

from harness_design_studio.core.checks import Finding
from harness_design_studio.core.commands import Op
from harness_design_studio.core.model import Project

from .rules import RULES

_ORDER = {"error": 0, "warning": 1, "info": 2}


def apply_waivers(project: Project, findings: list[Finding]) -> list[Finding]:
    return [replace(f, waiver=project.waivers.get(f.id)) if f.can_waive else f for f in findings]


def run(project: Project) -> list[Finding]:
    """All findings (waived ones carry their waiver), sorted by severity then ID."""
    found = [f for rule in RULES for f in rule.run(project)]
    # the independent verifier also reports mismatches between interfaces and wires
    found += _verifier_findings(project)
    return sorted(apply_waivers(project, found), key=lambda f: (_ORDER[f.severity], f.id))


_MISMATCH_WHY = (
    "The wires do not match the interfaces they should implement, so the harness would "
    "not carry the intended signals. To fix it: regenerate the harnesses, or correct the wiring by hand."
)
_OUTDATED_WHY = (
    "The design changed after the harness plans were generated, so the plans and outputs may no "
    "longer describe it. To fix it: generate the harnesses again, then export again."
)


def _verifier_findings(project: Project) -> list[Finding]:
    import hashlib

    from harness_design_studio.core.checks import finding_id
    from harness_design_studio.core.verify import verify_project

    if not project.harnesses:
        return []
    out = []
    for issue in verify_project(project).issues:
        if issue.severity != "error":
            continue
        # the message is part of the ID: several findings can share a code and an object
        # (one per missing signal), and every finding needs an ID of its own
        digest = hashlib.sha256(issue.message.encode()).hexdigest()[:6]
        obj = f"{issue.code}.{issue.object_id or 'design'}.{digest}"  # no enumeration index: stable IDs
        out.append(
            Finding(
                finding_id("verify-mismatch", obj), "verify-mismatch", "error", issue.object_id or obj,
                issue.message,
                _OUTDATED_WHY if issue.code == "outputs_outdated" else _MISMATCH_WHY,
                "Regenerate harnesses", False,
            )
        )  # fmt: skip
    return out


def fix_ops(project: Project, finding: Finding) -> tuple[list[Op], str] | None:
    """One-click fixes for design rule findings (None if the rule has none)."""
    if finding.rule in ("signal-unassigned", "verify-mismatch"):
        from harness_design_studio.core.edit import EditError
        from harness_design_studio.core.generate.engine import plan_generation

        plan = plan_generation(project)
        if plan.empty:
            raise EditError(
                "Regenerating would change nothing; this harness is drawn by hand or released, so fix it there."
            )
        return list(plan.ops), "Regenerated the harnesses from the interfaces."
    return None


def locate(project: Project, object_id: str) -> tuple[str, str] | None:
    """Where to show a finding: ("unit" | "interface" | "harness", id), or None if it has no place."""
    if object_id in project.units:
        return "unit", object_id
    if object_id in project.interfaces:
        return "interface", object_id
    if object_id in project.harnesses:
        return "harness", object_id
    box = project.connectors.get(object_id)
    if box is not None and box.unit_id:
        return "unit", box.unit_id
    for h in project.harnesses.values():
        if any(w.id == object_id for w in h.wires) or any(c.id == object_id for c in h.connectors):
            return "harness", h.id
    parts = object_id.split(".")
    if parts[0] == "shield-parts" and len(parts) > 2 and parts[1] in project.harnesses:
        return "harness", parts[1]
    if parts[0] == "emc-class" and len(parts) > 2 and parts[2] in project.units:
        return "unit", parts[2]
    head = parts[0]
    return locate(project, head) if head != object_id else None


__all__ = ["RULES", "apply_waivers", "fix_ops", "locate", "run"]
