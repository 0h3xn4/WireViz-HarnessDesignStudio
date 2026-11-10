# SPDX-FileCopyrightText: 2026 0h3xn4
# SPDX-License-Identifier: GPL-3.0-only
# mypy: disable-error-code="no-untyped-def,no-untyped-call,no-any-return,arg-type,attr-defined,index,union-attr"
"""REQ-CC-10: a harness with a loose cable end cannot be released (M4a of the 2.0 programme, D-200
(e), D-201). The blocker `loose_end_unresolved` can be waived with a reason of its own
(`--accept-loose-ends`, at least 10 characters, kept in the change log and the baseline); the waiver
for parts that are not approved does not cover it, the part `TBD-CONNECTOR` is no longer listed as
an unapproved part, plugging the end or giving it a part lifts the blocker, and sending a harness
for review is not blocked by it."""

from pathlib import Path

import pytest

from harness_design_studio.cli.main import main
from harness_design_studio.core.commands import History, Put, apply_ops
from harness_design_studio.core.generate.engine import generate_project
from harness_design_studio.core.io.loader import load_project
from harness_design_studio.core.io.saver import save_project
from harness_design_studio.core.manual_harness import (
    LOOSE,
    TBD_PART_ID,
    plan_plug_loose_end,
    plan_resolve_loose_end,
)
from harness_design_studio.core.outputs.build import write_outputs
from harness_design_studio.core.vcs.hashing import content_hash
from harness_design_studio.core.vcs.release import (
    plan_release,
    plan_submit_review,
    unapproved_parts,
)
from tests.helpers import copy_project
from tests.loose_support import build_loose

WAIVERS = dict(
    accept_placeholders="placeholders are fine here", accept_unapproved_parts="example parts, all"
)


@pytest.fixture(scope="module")
def loose_root(tmp_path_factory) -> Path:
    root = build_loose(tmp_path_factory.mktemp("loose") / "p")
    p = load_project(root).project
    generate_project(p)  # plans current: the release gate asks for it
    save_project(p, root)
    return root


def common(out: Path) -> dict[str, object]:
    return dict(
        by="Ada",
        checker="Bob",
        comment="Release of W013",
        when="2026-11-08",
        outputs_folder=out,
        **WAIVERS,
    )


def test_a_loose_end_blocks_a_release_and_the_parts_waiver_does_not_cover_it(loose_root, tmp_path):
    p = load_project(copy_project(loose_root, tmp_path / "p")).project
    out = tmp_path / "outputs"
    write_outputs(p, out)
    plan = plan_release(p, "W013", **common(out))  # both older waivers given
    assert [b.code for b in plan.blockers] == ["loose_end_unresolved"]
    assert "--accept-loose-ends REASON" in plan.blockers[0].message
    assert "W013-P2" in plan.blockers[0].message
    short = plan_release(p, "W013", accept_loose_ends="x", **common(out))
    assert [b.code for b in short.blockers] == ["loose_end_reason_short"]
    assert short.blockers[0].about == "reason"
    ok = plan_release(p, "W013", accept_loose_ends="the end waits for the supplier", **common(out))
    assert ok.ok
    note = [o for o in ok.ops if isinstance(o, Put) and o.collection == "changelog"][0].obj.comment
    assert "Released with a loose end (W013-P2); accepted by Ada: the end waits" in note
    assert "TBD-CONNECTOR" not in note  # the open end is not "a part that is not approved"


def test_the_stand_in_part_is_not_an_unapproved_part(loose_root):
    p = load_project(loose_root).project
    assert TBD_PART_ID not in unapproved_parts(p, p.harnesses["W013"])
    assert TBD_PART_ID in {c.part_id for c in p.harnesses["W013"].connectors}  # it is in use


def test_resolving_the_end_lifts_the_blocker(loose_root, tmp_path):
    p = load_project(copy_project(loose_root, tmp_path / "p")).project
    apply_ops(p, plan_resolve_loose_end(p, "W013", "W013-P2", "EX-MICROD-9-M"))
    out = tmp_path / "outputs"
    write_outputs(p, out)
    assert plan_release(p, "W013", **common(out)).ok


def test_plugging_the_end_lifts_the_blocker(loose_root, tmp_path):
    p = load_project(copy_project(loose_root, tmp_path / "p")).project
    apply_ops(p, plan_plug_loose_end(p, "W013", "W013-P2", "RIU1-J11"))
    assert [c.role for c in p.harnesses["W013"].connectors if c.id == "W013-P2"] == ["cable"]
    out = tmp_path / "outputs"
    write_outputs(p, out)
    assert plan_release(p, "W013", **common(out)).ok


def test_a_loose_end_does_not_block_sending_a_harness_for_review(loose_root, tmp_path):
    p = load_project(copy_project(loose_root, tmp_path / "p")).project
    plan = plan_submit_review(p, "W013", by="Ada", when="2026-11-08")
    assert plan.ok, [b.message for b in plan.blockers]


def test_a_frozen_baseline_still_matches_after_a_loose_end_is_released(loose_root, tmp_path):
    root = copy_project(loose_root, tmp_path / "p")
    p = load_project(root).project
    out = tmp_path / "outputs"
    write_outputs(p, out)
    plan = plan_release(
        p, "W013", accept_loose_ends="the end waits for the supplier", **common(out)
    )
    History(p).execute(plan.label, plan.ops)
    save_project(p, root)
    q = load_project(root).project
    assert q.baselines["W013.A"].content_hash == content_hash(q)
    snap = q.baselines["W013.A"].snapshot.harnesses[0]
    assert [c.role for c in snap.connectors if c.id == "W013-P2"] == [LOOSE]
    assert TBD_PART_ID in {x.id for x in q.baselines["W013.A"].snapshot.parts}  # frozen with it
    entry = next(e for e in q.changelog.values() if e.kind == "release")
    assert "Released with a loose end (W013-P2)" in entry.comment
    assert q.baselines["W013.A"].comment == entry.comment


def _args(folder: Path, *more: str) -> list[str]:
    return [
        "release", str(folder), "W013", "--by", "Ada", "--checker", "Bob",
        "--comment", "Release of W013 for the bench", "--date", "2026-11-08",
        "--accept-placeholders", "placeholders are fine here",
        "--accept-unapproved-parts", "example parts, all of them", *more,
    ]  # fmt: skip


def test_the_command_is_blocked_then_released_with_a_reason_kept_in_the_change_log(
    loose_root, tmp_path, capsys: pytest.CaptureFixture[str]
) -> None:
    folder = copy_project(loose_root, tmp_path / "p")
    write_outputs(load_project(folder).project, folder / "outputs")
    assert main(_args(folder)) == 1
    err = capsys.readouterr().err
    assert "blocked: [loose_end_unresolved]" in err and "--accept-loose-ends REASON" in err
    assert main(_args(folder, "--accept-loose-ends", "short")) == 1
    err = capsys.readouterr().err
    assert "[loose_end_reason_short]" in err and "--accept-loose-ends" in err
    reason = "The end goes into the customer's connector, ordered with the unit"
    assert main(_args(folder, "--accept-loose-ends", reason)) == 0
    project = load_project(folder).project
    assert project.harnesses["W013"].status == "released"
    entry = next(e for e in project.changelog.values() if e.kind == "release")
    assert "[Released with a loose end (W013-P2);" in entry.comment
    assert f"accepted by Ada: {reason}]" in entry.comment
