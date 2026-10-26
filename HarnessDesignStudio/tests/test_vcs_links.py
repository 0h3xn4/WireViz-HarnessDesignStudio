"""REQ-GUI-12, REQ-IO-02. M2a: change control sees links. A link is a diffable object; the link of a harness that is
released is locked with it, is kept in its baseline and is checked against it."""

from pathlib import Path

import pytest

from harness_design_studio.core.commands import Delete, History, Put, apply_ops
from harness_design_studio.core.errors import TransactionError
from harness_design_studio.core.model import Link, PinPair, Project, evolve
from harness_design_studio.core.vcs import lockview
from harness_design_studio.core.vcs.consistency import release_integrity
from harness_design_studio.core.vcs.diff import (
    KIND_NAMES,
    SCREEN_KIND_NAMES,
    diff_projects,
    flatten_snapshot,
    render_markdown,
)
from harness_design_studio.core.vcs.locks import check_locks
from harness_design_studio.core.vcs.release import plan_new_revision
from tests.helpers import pinout_project
from tests.test_change_control import WHEN, do_release, exported, full, releasable


def pairs(*items: tuple[str, str]) -> list[PinPair]:
    return [PinPair(a_pin=a, b_pin=b) for a, b in items]


def test_a_link_is_a_diffable_object_with_readable_pairs() -> None:
    before = pinout_project()
    after = pinout_project()
    after.links["L1"] = Link(
        id="L1", a_connector="OBC-J01", b_connector="RW1-J02", pairs=pairs(("1", "3"))
    )
    d = diff_projects(before, after)
    assert [(c.kind, c.id, c.change) for c in d.changes] == [("link", "L1", "added")]
    before.links["L1"] = after.links["L1"]
    after.links["L1"] = evolve(after.links["L1"], pairs=pairs(("1", "3"), ("2", "4")), name="Data")
    d = diff_projects(before, after)
    (c,) = d.changes
    assert c.change == "changed"
    fields = {f.name: (f.before, f.after) for f in c.fields}
    assert fields["pairs"] == (["1-3"], ["1-3", "2-4"]) and fields["name"] == (
        None,
        "Data",
    )  # an empty name is left out
    text = render_markdown("Changes", d)
    assert "Link `L1`" in text and "1-3, 2-4" in text
    assert KIND_NAMES["link"] == SCREEN_KIND_NAMES["link"] == "Link"


def test_a_project_without_links_has_no_link_in_its_diff() -> None:
    assert diff_projects(pinout_project(), pinout_project()).empty


def released(tmp_path: Path) -> tuple[Project, str, History]:
    p = full()
    hid = releasable(p)
    h = p.harnesses[hid]
    a, b = (c.mates_with for c in h.connectors[:2])
    assert a and b and p.connectors[a].unit_id != p.connectors[b].unit_id
    p.links["L1"] = Link(id="L1", a_connector=a, b_connector=b, harness_id=hid)
    hist = do_release(p, hid, exported(p, tmp_path))
    return p, hid, hist


def test_the_link_of_a_released_harness_is_locked_with_the_reason(tmp_path: Path) -> None:
    p, hid, _hist = released(tmp_path)
    ref = lockview.LockRef(hid, p.harnesses[hid].revision)
    assert lockview.locked_objects(p)[("link", "L1")] == [ref]
    why = lockview.lock_reason(p, "link", "L1")
    assert (
        why
        == f"Link L1 belongs to {hid}, which is released. {hid} is released (revision A); start a new revision to change it."
    )
    assert lockview.field_lock_reason(p, "link", "L1", "pairs") == why
    assert lockview.release_locks(p, hid).links == ("L1",)
    assert "Link" in lockview.KIND_LABELS["link"]


@pytest.mark.parametrize("what", ["change", "delete", "claim"])
def test_edits_of_a_locked_link_are_refused(tmp_path: Path, what: str) -> None:
    p, hid, hist = released(tmp_path)
    link = p.links["L1"]
    op: Put | Delete
    if what == "change":
        op = Put("links", evolve(link, pairs=pairs(("1", "1"))))
    elif what == "delete":
        op = Delete("links", "L1")
    else:  # a new link may not say it made a released harness
        op = Put(
            "links",
            Link(
                id="L2", a_connector=link.a_connector, b_connector=link.b_connector, harness_id=hid
            ),
        )
    with pytest.raises(TransactionError) as exc:
        check_locks(p, [op])
    assert any(f"belongs to {hid}, which is released" in x for x in exc.value.problems)
    with pytest.raises(TransactionError):
        hist.execute("edit", [op])
    assert p.links["L1"] == link and "L2" not in p.links


def test_a_link_of_a_draft_harness_and_a_link_with_no_harness_can_change(tmp_path: Path) -> None:
    p, hid, _hist = released(tmp_path)
    check_locks(p, [Put("links", Link(id="L2", a_connector="x", b_connector="y"))])
    revision = plan_new_revision(p, hid, by="Ada", comment="a long enough comment", when=WHEN)
    assert revision.ok
    History(p).execute(revision.label, revision.ops)
    assert lockview.lock_reason(p, "link", "L1") is None
    check_locks(p, [Delete("links", "L1")])


def test_the_baseline_keeps_the_link_and_a_change_made_behind_the_tool_is_found(
    tmp_path: Path,
) -> None:
    p, hid, _hist = released(tmp_path)
    baseline = p.baselines[f"{hid}.A"]
    assert baseline.snapshot.links == [p.links["L1"]]
    assert ("link", "L1") in flatten_snapshot(baseline.snapshot)
    assert not [i for i in release_integrity(p) if i.object_id == hid]
    apply_ops(
        p, [Put("links", evolve(p.links["L1"], pairs=pairs(("1", "1"))))]
    )  # bypasses the locks
    (issue,) = [i for i in release_integrity(p) if i.object_id == hid]
    assert (
        issue.code == "released_modified"
        and "link L1 it was made from was changed" in issue.message
    )


def test_a_baseline_of_a_harness_without_a_link_has_no_links_key(tmp_path: Path) -> None:
    p = full()
    hid = releasable(p)
    do_release(p, hid, exported(p, tmp_path))
    snapshot = p.baselines[f"{hid}.A"].snapshot
    assert snapshot.links is None and "links" not in snapshot.model_dump(mode="json")
