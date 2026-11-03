"""Overrides and deviations as operations on a loaded project (S4, D-191).

The command line (`override`, `deviation`) and the scripting interface (`api.set_override` and
the others) both call these functions, so they cannot disagree. Each one changes the project in
memory as one undo step and returns; the caller saves. A refusal is an `EditError` (the change
cannot be done, with the reason) or a `TransactionError` (a released harness)."""

from harness_design_studio.core import checks, drc
from harness_design_studio.core.commands import Delete, History
from harness_design_studio.core.edit import EditError
from harness_design_studio.core.model import Project
from harness_design_studio.core.wires import plan_clear_override, plan_override


def set_override(
    project: Project, wire_id: str, field: str, value: object, reason: str | None
) -> bool:
    """Set `field` of a generated wire by hand, with the reason. False when the wire has this
    value and reason already (nothing was changed)."""
    ops = plan_override(project, wire_id, field, value, reason)
    if ops:
        History(project).execute(f"Override {field} of {wire_id}", ops)
    return bool(ops)


def clear_override(project: Project, wire_id: str, field: str) -> bool:
    """Give `field` of the wire back to generation. False when it was not overridden."""
    ops = plan_clear_override(project, wire_id, field)
    if ops:
        History(project).execute(f"Give {field} of {wire_id} back to generation", ops)
    return bool(ops)


def findings_by_id(project: Project) -> dict[str, checks.Finding]:
    return {f.id: f for f in [*checks.find(project), *drc.run(project)]}


def _finding(project: Project, finding_id: str) -> checks.Finding:
    found = findings_by_id(project).get(finding_id)
    if found is None:
        raise EditError(f"there is no finding '{finding_id}' (see `drc`).")
    return found


def accept_deviation(project: Project, finding_id: str, reason: str | None) -> checks.Finding:
    """Accept the error `finding_id` of an electrical rule as a recorded deviation."""
    finding = _finding(project, finding_id)
    if reason is None:
        raise EditError("a deviation needs a reason.")
    History(project).execute(f"Deviation {finding.id}", [checks.deviate_op(finding, reason)])
    return finding


def remove_deviation(project: Project, finding_id: str) -> checks.Finding:
    """Take a deviation back; the finding is open again."""
    finding = _finding(project, finding_id)
    if not finding.deviation:
        raise EditError(f"{finding_id} is not a deviation.")
    History(project).execute(
        f"Take back the deviation {finding.id}", [Delete("waivers", finding.id)]
    )
    return finding
