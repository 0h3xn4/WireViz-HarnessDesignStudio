"""REQ-GUI-17. Release 1.9 W1: approving a part from the Next step page (a person presses it)."""

import pytest

from harness_design_studio.core.commands import History
from harness_design_studio.core.edit import EditError
from harness_design_studio.core.model import evolve
from harness_design_studio.core.part_approval import approval_blocker, ops_approve_part
from harness_design_studio.core.samples import new_project

PART = "EX-MICROD-9-F"


def test_a_pending_example_part_can_be_approved() -> None:
    p = new_project()
    assert p.parts[PART].approval == "pending" and p.parts[PART].unverified
    assert approval_blocker(p, PART) == ""
    History(p).execute("approve", ops_approve_part(p, PART))
    assert p.parts[PART].approval == "approved" and not p.parts[PART].unverified


def test_only_that_part_changes() -> None:
    p = new_project()
    before = {k: v for k, v in p.parts.items() if k != PART}
    History(p).execute("approve", ops_approve_part(p, PART))
    assert {k: v for k, v in p.parts.items() if k != PART} == before


def test_an_approved_part_a_missing_part_and_a_rejected_part_are_refused() -> None:
    p = new_project()
    History(p).execute("approve", ops_approve_part(p, PART))
    assert "approved already" in approval_blocker(p, PART)
    assert "not in the parts list" in approval_blocker(p, "NOPE")
    p.parts["EX-DSUB-9-M"] = evolve(p.parts["EX-DSUB-9-M"], approval="not_approved")
    assert "not approved" in approval_blocker(p, "EX-DSUB-9-M")
    for part in (PART, "NOPE", "EX-DSUB-9-M"):
        with pytest.raises(EditError):
            ops_approve_part(p, part)


def test_a_read_only_project_is_refused() -> None:
    p = new_project()
    p.read_only = True
    assert "read-only" in approval_blocker(p, PART)
