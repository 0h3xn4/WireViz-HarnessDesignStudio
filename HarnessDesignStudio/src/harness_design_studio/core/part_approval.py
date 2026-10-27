"""Approving a part from the Next step page (Release 1.9, W1).

The program never approves a part by itself (`devices.ops_add_part` makes every part `pending` and
`unverified`). This is the plan for the case where a PERSON presses **Approve** on the Next step
page after the window named the part and said what approving means. It sets the two fields the
model already has (`approval` and `unverified`) and nothing else: no field is added, and a part that
a person marked *not approved* is never turned around here (that is a decision for the parts list).

    why = approval_blocker(project, "EX-MICROD-9-F")     # "" when it can be approved
    ops = ops_approve_part(project, "EX-MICROD-9-F")     # raises EditError with the reason
"""

from .commands import Op, Put
from .edit import EditError
from .model import Project, evolve
from .vcs.lockview import field_lock_reason


def approval_blocker(project: Project, part_id: str) -> str:
    """Why the part cannot be approved here, in a plain sentence, or "" when it can."""
    if project.read_only:
        return "This project is read-only (saved by a newer tool version). Use Save as."
    part = project.parts.get(part_id)
    if part is None:
        return f"Part '{part_id}' is not in the parts list."
    if part.approval == "approved" and not part.unverified:
        return f"Part {part_id} is approved already."
    if part.approval == "not_approved":
        return (
            f"Part {part_id} was marked as not approved. Change that in the parts list, "
            "not from here."
        )
    return field_lock_reason(project, "part", part_id, "approval") or ""


def ops_approve_part(project: Project, part_id: str) -> list[Op]:
    """Mark the part approved and no longer example data."""
    if why := approval_blocker(project, part_id):
        raise EditError(why)
    return [Put("parts", evolve(project.parts[part_id], approval="approved", unverified=False))]
