"""REQ-CC-06 (placeholder gate, D-135) and M6: review, release, baselines, locks on released items, new revisions, the diff engine,
the change log and its outputs."""

import json
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from harness_design_studio.cli.main import main as cli_main
from harness_design_studio.core import drc, edit
from harness_design_studio.core.commands import Delete, History, Op, Put
from harness_design_studio.core.errors import TransactionError
from harness_design_studio.core.generate.engine import plan_generation
from harness_design_studio.core.io.layout import model_hash
from harness_design_studio.core.io.loader import load_project
from harness_design_studio.core.io.saver import save_project
from harness_design_studio.core.model import Project, Wire, evolve
from harness_design_studio.core.outputs.build import (
    build_outputs,
    outputs_content_state,
    outputs_status,
    write_outputs,
)
from harness_design_studio.core.outputs.stamp import csv_bytes, parse_csv, stamp_of
from harness_design_studio.core.outputs.verify import read_folder, verify_outputs
from harness_design_studio.core.samples import sat15, sat15_full
from harness_design_studio.core.vcs import diff as vd
from harness_design_studio.core.vcs.hashing import content_hash
from harness_design_studio.core.vcs.release import (
    next_revision,
    plan_new_revision,
    plan_release,
    plan_submit_review,
    release_blockers,
    unapproved_parts,
)
from harness_design_studio.core.vcs.report import (
    baselines_of,
    changelog_rows,
    revision_report,
    working_diff,
)

WHEN = "2026-03-01"
_BASE: Project | None = None


def full() -> Project:
    global _BASE
    if _BASE is None:
        _BASE = sat15_full()
    return edit.clone_with(_BASE, [])


REASON = "Test project: values are placeholders"


def releasable(p: Project) -> str:
    return next(
        h.id
        for h in sorted(p.harnesses.values(), key=lambda x: x.id)
        if all(w.gauge_awg and w.length_m for w in h.wires)
    )


def exported(p: Project, tmp: Path) -> Path:
    folder = tmp / "outputs"
    write_outputs(p, folder)
    return folder


def do_release(
    p: Project,
    hid: str,
    folder: Path,
    hist: History | None = None,
    when: str = WHEN,
    comment: str = "First release for the CDR",
) -> History:
    plan = plan_release(
        p, hid, by="Ada", checker="Bob", comment=comment, when=when, outputs_folder=folder,
        accept_placeholders=REASON, accept_unapproved_parts=REASON,
    )  # fmt: skip
    assert plan.ok, [b.message for b in plan.blockers]
    hist = hist or History(p)
    hist.execute(plan.label, plan.ops)
    return hist


def codes(p: Project, hid: str, folder: Path | None, **kw: str) -> set[str]:
    args = {
        "by": "Ada", "comment": "a long enough comment", "when": WHEN,
        "accept_placeholders": REASON, "accept_unapproved_parts": REASON,
    }  # fmt: skip
    args.update(kw)
    return {b.code for b in release_blockers(p, hid, outputs_folder=folder, **args)}


# ---- the placeholder gate (D-135) -------------------------------------------------------------------


def test_placeholder_configuration_blocks_a_release_without_a_reason(tmp_path: Path) -> None:
    p = full()
    hid = releasable(p)
    folder = exported(p, tmp_path)
    assert p.placeholder_configs()
    assert "placeholder_config" in codes(p, hid, folder, accept_placeholders=None)  # type: ignore[arg-type]
    short = codes(p, hid, folder, accept_placeholders="short")
    assert "placeholder_reason_short" in short and "placeholder_config" not in short
    ok = codes(p, hid, folder)
    assert not ok & {"placeholder_config", "placeholder_reason_short"}


def test_a_reviewed_configuration_releases_without_a_reason(tmp_path: Path) -> None:
    p = full()
    hid = releasable(p)
    folder = exported(p, tmp_path)
    for name, cfg in list(p.config.items()):
        p.config[name] = evolve(cfg, placeholder=False)
    assert not p.placeholder_configs()
    assert "placeholder_config" not in codes(p, hid, folder, accept_placeholders=None)  # type: ignore[arg-type]
    plan = plan_release(
        p, hid, by="Ada", checker=None, comment="Reviewed values", when=WHEN, outputs_folder=folder
    )
    assert not any(b.code.startswith("placeholder") for b in plan.blockers)
    if plan.ok:  # no note is added when nothing rests on placeholders
        History(p).execute(plan.label, plan.ops)
        assert next(iter(p.changelog.values())).comment == "Reviewed values"


def test_the_reason_and_the_files_are_kept_in_the_change_log_and_the_baseline(
    tmp_path: Path,
) -> None:
    p = full()
    hid = releasable(p)
    names = p.placeholder_configs()
    do_release(p, hid, exported(p, tmp_path))
    entry = next(iter(p.changelog.values()))
    for text in (entry.comment, p.baselines[f"{hid}.A"].comment):
        assert REASON in text and "Ada" in text
        assert all(n in text for n in names)


def test_a_comment_too_long_for_the_baseline_is_a_blocker_not_a_crash(tmp_path: Path) -> None:
    p = full()
    hid = releasable(p)
    folder = exported(p, tmp_path)
    assert "comment_long" in codes(p, hid, folder, comment="x" * 1990)


# ---- the unapproved-parts gate (D-136) --------------------------------------------------------------


def _approve_all_parts(p: Project, hid: str) -> None:
    h = p.harnesses[hid]
    for pid in {c.part_id for c in h.connectors} | {w.part_id for w in h.wires if w.part_id}:
        part = p.parts.get(pid)
        if part is not None:
            p.parts[pid] = evolve(part, approval="approved", unverified=False)


def test_unapproved_parts_block_a_release_without_a_reason(tmp_path: Path) -> None:
    p = full()
    hid = releasable(p)
    folder = exported(p, tmp_path)
    assert unapproved_parts(p, p.harnesses[hid])
    assert "parts_unapproved" in codes(p, hid, folder, accept_unapproved_parts=None)  # type: ignore[arg-type]
    short = codes(p, hid, folder, accept_unapproved_parts="short")
    assert "parts_reason_short" in short and "parts_unapproved" not in short
    assert not codes(p, hid, folder) & {"parts_unapproved", "parts_reason_short"}


def test_approved_parts_release_without_a_reason(tmp_path: Path) -> None:
    p = full()
    hid = releasable(p)
    folder = exported(p, tmp_path)
    _approve_all_parts(p, hid)
    assert unapproved_parts(p, p.harnesses[hid]) == []
    assert "parts_unapproved" not in codes(p, hid, folder, accept_unapproved_parts=None)  # type: ignore[arg-type]


def test_a_missing_rejected_or_example_part_counts_as_unapproved() -> None:
    p = full()
    hid = releasable(p)
    _approve_all_parts(p, hid)
    h = p.harnesses[hid]
    pid = h.wires[0].part_id
    assert pid is not None
    base = p.parts[pid]
    for changed in (
        evolve(base, approval="pending"),
        evolve(base, approval="not_approved"),
        evolve(base, unverified=True),
    ):
        p.parts[pid] = changed
        assert unapproved_parts(p, h) == [pid]
    del p.parts[pid]
    assert unapproved_parts(p, h) == [pid]


def test_the_parts_reason_is_kept_in_the_change_log_and_the_baseline(tmp_path: Path) -> None:
    p = full()
    hid = releasable(p)
    ids = unapproved_parts(p, p.harnesses[hid])
    do_release(p, hid, exported(p, tmp_path))
    entry = next(iter(p.changelog.values()))
    for text in (entry.comment, p.baselines[f"{hid}.A"].comment):
        assert REASON in text and ids[0] in text and "not approved" in text


# ---- revisions -------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "before,after", [("A", "B"), ("Y", "Z"), ("Z", "AA"), ("AZ", "BA"), ("ZZ", "AAA")]
)
def test_next_revision(before: str, after: str) -> None:
    assert next_revision(before) == after


def test_next_revision_needs_letters() -> None:
    from harness_design_studio.core.vcs.release import ReleaseError

    with pytest.raises(ReleaseError):
        next_revision("1.0")


# ---- release gate ----------------------------------------------------------------------------------


def test_release_is_blocked_until_outputs_are_exported(tmp_path: Path) -> None:
    p = full()
    hid = releasable(p)
    assert codes(p, hid, None) == {"outputs_unsaved"}
    assert codes(p, hid, tmp_path / "outputs") == {"outputs_missing"}
    folder = exported(p, tmp_path)
    assert codes(p, hid, folder) == set()


def test_release_needs_name_comment_and_date(tmp_path: Path) -> None:
    p = full()
    hid = releasable(p)
    folder = exported(p, tmp_path)
    assert "no_name" in codes(p, hid, folder, by=" ")
    assert "comment_short" in codes(p, hid, folder, comment="too short")
    assert "bad_date" in codes(p, hid, folder, when="1 March")
    assert "no_harness" in codes(p, "NOPE", folder)


def test_stale_outputs_block_the_release(tmp_path: Path) -> None:
    p = full()
    hid = releasable(p)
    folder = exported(p, tmp_path)
    unit = next(iter(p.units.values()))
    History(p).execute("rename", [Put("units", evolve(unit, name="Renamed"))])
    assert "outputs_stale" in codes(p, hid, folder)


def test_undecided_gauges_and_unknown_lengths_block_the_release(tmp_path: Path) -> None:
    p = sat15()
    from harness_design_studio.core.generate.engine import generate_project

    generate_project(p)
    hid = sorted(p.harnesses)[0]
    folder = exported(p, tmp_path)
    got = codes(p, hid, folder)
    assert {"gauge_pending", "length_unknown"} <= got


def test_stale_generation_blocks_the_release(tmp_path: Path) -> None:
    p = full()
    hid = releasable(p)
    folder = exported(p, tmp_path)
    unit = next(iter(p.units.values()))
    History(p).execute("rename", [Put("units", evolve(unit, name="Renamed"))])
    assert "generation_stale" in codes(p, hid, folder)


def test_rule_and_verifier_errors_block_the_release(tmp_path: Path) -> None:
    p = full()
    hid = releasable(p)
    h = p.harnesses[hid]
    c = h.connectors[0]
    box = p.connectors[c.mates_with or ""]
    from harness_design_studio.core.commands import apply_ops

    apply_ops(
        p,
        [
            Put("connectors", evolve(box, gender="male")),
            Put("harnesses", evolve(h, connectors=[evolve(c, gender="male"), *h.connectors[1:]])),
        ],
    )
    folder = exported(p, tmp_path)
    assert "rule_error" in codes(p, hid, folder)
    p2 = full()
    h2 = p2.harnesses[hid]
    w = h2.wires[0]
    cable = next(x for x in h2.connectors if x.id == w.to_connector)
    other = next(x.id for x in cable.pins if x.id not in (w.to_pin, w.from_pin))
    apply_ops(p2, [Put("harnesses", evolve(h2, wires=[evolve(w, to_pin=other), *h2.wires[1:]]))])
    folder2 = exported(p2, tmp_path / "second")
    assert "verify_error" in codes(p2, hid, folder2)


def test_waived_warnings_do_not_block_and_errors_elsewhere_do_not_block(tmp_path: Path) -> None:
    p = full()
    hid = releasable(p)
    other = next(h for h in p.harnesses.values() if h.id != hid)
    from harness_design_studio.core.commands import apply_ops

    w = other.wires[0]
    apply_ops(
        p,
        [Put("harnesses", evolve(other, wires=[evolve(w, to_connector="NOPE"), *other.wires[1:]]))],
    )  # error elsewhere
    folder = exported(p, tmp_path)
    assert codes(p, hid, folder) == set()


def test_a_harness_without_wires_cannot_be_released(tmp_path: Path) -> None:
    p = full()
    hid = releasable(p)
    h = p.harnesses[hid]
    from harness_design_studio.core.commands import apply_ops

    apply_ops(p, [Put("harnesses", evolve(h, wires=[], shields=[]))])
    assert "no_wires" in codes(p, hid, exported(p, tmp_path))


# ---- release, baseline, change log, locks --------------------------------------------------------


def test_release_writes_baseline_changelog_and_locks(tmp_path: Path) -> None:
    p = full()
    hid = releasable(p)
    folder = exported(p, tmp_path)
    before_content = content_hash(p)
    do_release(p, hid, folder)
    h = p.harnesses[hid]
    assert (h.status, h.revision, h.approver, h.checker, h.author, h.released_on) == (
        "released",
        "A",
        "Ada",
        "Bob",
        "Ada",
        WHEN,
    )
    b = p.baselines[f"{hid}.A"]
    assert b.comment.startswith("First release for the CDR") and REASON in b.comment
    assert b.snapshot.harnesses[0].status == "released"
    assert {i.id for i in b.snapshot.interfaces} == {
        w.interface_id for w in h.wires if w.interface_id
    }
    assert [e.kind for e in p.changelog.values()] == ["release"]
    assert content_hash(p) == before_content  # release bookkeeping does not change the content
    assert outputs_content_state(p, folder) == "current"
    assert outputs_status(p, folder).state == "stale"  # the files still say "draft"


def test_released_harness_cannot_be_edited_or_deleted(tmp_path: Path) -> None:
    p = full()
    hid = releasable(p)
    hist = do_release(p, hid, exported(p, tmp_path))
    h = p.harnesses[hid]
    w = h.wires[0]
    cases: list[list[Op]] = [
        [Put("harnesses", evolve(h, name="Renamed"))],
        [Put("harnesses", evolve(h, wires=[evolve(w, colour="RED"), *h.wires[1:]]))],
        [Delete("harnesses", hid)],
    ]
    for ops in cases:
        with pytest.raises(TransactionError) as err:
            hist.execute("edit", ops)
        assert "released" in " ".join(err.value.problems)
    assert p.harnesses[hid] == h


def test_released_items_protect_their_interfaces_and_pins(tmp_path: Path) -> None:
    p = full()
    hid = releasable(p)
    hist = do_release(p, hid, exported(p, tmp_path))
    h = p.harnesses[hid]
    iid = next(w.interface_id for w in h.wires if w.interface_id)
    i = p.interfaces[iid]
    with pytest.raises(TransactionError):
        hist.execute("delete", [Delete("interfaces", iid)])
    with pytest.raises(TransactionError):
        hist.execute(
            "retype", [Put("interfaces", evolve(i, endpoints=list(reversed(i.endpoints))))]
        )
    hist.execute(
        "rename", [Put("interfaces", evolve(i, name="Renamed interface"))]
    )  # harmless edits stay possible
    box = p.connectors[h.connectors[0].mates_with or ""]
    pin = next(x for x in box.pins if x.interface_id == iid)
    pins = [evolve(x, signal="CHANGED") if x is pin else x for x in box.pins]
    with pytest.raises(TransactionError):
        hist.execute("pin", [Put("connectors", evolve(box, pins=pins))])
    with pytest.raises(TransactionError):
        hist.execute("delete connector", [Delete("connectors", box.id)])
    unit = p.units[box.unit_id or ""]
    hist.execute("rename unit", [Put("units", evolve(unit, name="Another name"))])


def test_regeneration_leaves_released_harnesses_alone(tmp_path: Path) -> None:
    p = full()
    hid = releasable(p)
    do_release(p, hid, exported(p, tmp_path))
    before = p.harnesses[hid]
    plan = plan_generation(p)
    from harness_design_studio.core.commands import apply_ops

    apply_ops(p, plan.ops)
    assert p.harnesses[hid] == before and hid in plan.report.frozen


def test_release_can_be_undone_in_the_session(tmp_path: Path) -> None:
    p = full()
    hid = releasable(p)
    before = model_hash(p)
    hist = do_release(p, hid, exported(p, tmp_path))
    hist.undo()
    assert model_hash(p) == before and not p.baselines and not p.changelog


def test_cannot_release_twice_or_reuse_a_baseline(tmp_path: Path) -> None:
    p = full()
    hid = releasable(p)
    folder = exported(p, tmp_path)
    do_release(p, hid, folder)
    assert "already_released" in codes(p, hid, folder)


# ---- new revision ---------------------------------------------------------------------------------


def test_new_revision_unlocks_keeps_the_baseline_and_can_be_released_again(tmp_path: Path) -> None:
    p = full()
    hid = releasable(p)
    folder = exported(p, tmp_path)
    hist = do_release(p, hid, folder)
    assert not plan_new_revision(p, hid, by="Ada", comment="short", when=WHEN).ok
    plan = plan_new_revision(
        p, hid, by="Ada", comment="Change the colours for the build", when="2026-04-01"
    )
    hist.execute(plan.label, plan.ops)
    h = p.harnesses[hid]
    assert (h.revision, h.status, h.approver, h.released_on) == ("B", "draft", None, None)
    assert f"{hid}.A" in p.baselines
    w = h.wires[0]
    hist.execute(
        "colour", [Put("harnesses", evolve(h, wires=[evolve(w, colour="WHT"), *h.wires[1:]]))]
    )
    diff = working_diff(p, p.harnesses[hid], p.baselines[f"{hid}.A"])
    assert {(c.kind, c.id) for c in diff.changes} == {("harness", hid), ("wire", w.id)}
    folder2 = tmp_path / "second"
    write_outputs(p, folder2)
    do_release(p, hid, folder2, hist, when="2026-04-02", comment="Second release, colours added")
    assert p.harnesses[hid].revision == "B" and set(p.baselines) == {f"{hid}.A", f"{hid}.B"}
    assert [e.kind for e in p.changelog.values()] == ["release", "new_revision", "release"]
    assert [e.id for e in p.changelog.values()] == ["C0001", "C0002", "C0003"]


def test_new_revision_of_a_draft_is_refused() -> None:
    p = full()
    hid = releasable(p)
    assert "not_released" in {
        b.code
        for b in plan_new_revision(p, hid, by="Ada", comment="long enough text", when=WHEN).blockers
    }


# ---- review ---------------------------------------------------------------------------------------


def test_submit_for_review_and_regeneration_resets_it() -> None:
    p = full()
    hid = releasable(p)
    plan = plan_submit_review(p, hid, by="Ada", when=WHEN)
    History(p).execute(plan.label, plan.ops)
    assert (p.harnesses[hid].status, p.harnesses[hid].author) == ("in_review", "Ada")
    assert "not_draft" in {b.code for b in plan_submit_review(p, hid, by="Ada", when=WHEN).blockers}
    from harness_design_studio.core.commands import apply_ops

    apply_ops(p, plan_generation(p).ops)  # nothing changed: still in review
    assert p.harnesses[hid].status == "in_review"
    iface = p.interfaces[p.harnesses[hid].interfaces[0]]
    apply_ops(p, [Put("interfaces", evolve(iface, max_current_a=0.5))])
    apply_ops(p, plan_generation(p).ops)
    assert p.harnesses[hid].status == "draft" and p.harnesses[hid].checker is None


# ---- consistency after merges ---------------------------------------------------------------------


def test_released_harness_edited_behind_the_tools_back_is_an_error(tmp_path: Path) -> None:
    p = full()
    hid = releasable(p)
    do_release(p, hid, exported(p, tmp_path))
    assert not [f for f in drc.run(p) if f.rule == "released-modified"]
    h = p.harnesses[hid]
    from harness_design_studio.core.commands import apply_ops

    apply_ops(
        p, [Put("harnesses", evolve(h, name="Edited in a text editor"))]
    )  # bypasses the locks
    found = [f for f in drc.run(p) if f.rule == "released-modified"]
    assert found and found[0].severity == "error" and not found[0].can_waive


def test_cli_check_reports_a_tampered_release(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    p = full()
    hid = releasable(p)
    do_release(p, hid, exported(p, tmp_path))
    save_project(p, tmp_path / "p")
    assert cli_main(["check", str(tmp_path / "p")]) == 0
    path = tmp_path / "p" / "physical" / "harnesses" / f"{hid}.json"
    data = json.loads(path.read_text())
    data["name"] = "Tampered"
    path.write_text(json.dumps(data, indent=1, sort_keys=True) + "\n")
    assert cli_main(["check", str(tmp_path / "p")]) == 1
    assert "released_modified" in capsys.readouterr().out


def test_baselines_and_changelog_survive_save_and_load(tmp_path: Path) -> None:
    p = full()
    hid = releasable(p)
    do_release(p, hid, exported(p, tmp_path))
    save_project(p, tmp_path / "p")
    assert (tmp_path / "p" / "baselines" / hid / f"{hid}.A.json").is_file() and (
        tmp_path / "p" / "changelog.json"
    ).is_file()
    q = load_project(tmp_path / "p").project
    assert q.baselines == p.baselines and q.changelog == p.changelog
    assert model_hash(q) == model_hash(p)


# ---- diff engine ---------------------------------------------------------------------------------


def test_diff_of_identical_designs_is_empty() -> None:
    p = full()
    assert vd.diff_projects(p, edit.clone_with(p, [])).empty


def test_diff_lists_added_removed_and_changed_exactly() -> None:
    a = full()
    b = edit.clone_with(a, [])
    hid = releasable(a)
    h = b.harnesses[hid]
    w0, w1 = h.wires[0], h.wires[1]
    new_wire = Wire(
        id="W-NEW-1",
        from_connector=w0.from_connector,
        from_pin="8",
        to_connector=w0.to_connector,
        to_pin="8",
        signal="X",
    )
    edited = evolve(h, wires=[evolve(w0, colour="RED"), new_wire, *h.wires[2:]])  # w1 removed
    unit = next(iter(b.units.values()))
    from harness_design_studio.core.commands import apply_ops

    apply_ops(
        b,
        [
            Put("harnesses", edited),
            Put("units", evolve(unit, name="Renamed")),
            Delete("interfaces", "IF-022"),
        ],
    )
    d = vd.diff_projects(a, b)
    got = {(c.change, c.kind, c.id) for c in d.changes}
    assert got == {
        ("changed", "wire", w0.id), ("added", "wire", "W-NEW-1"), ("removed", "wire", w1.id),
        ("changed", "unit", unit.id), ("removed", "interface", "IF-022"),
    }  # fmt: skip
    colour = next(c for c in d.changes if c.id == w0.id).fields
    assert [(f.name, f.before, f.after) for f in colour] == [("colour", None, "RED")]
    assert d.counts() == {"added": 1, "removed": 2, "changed": 2}
    assert d.affected() == {unit.id: "changed", "IF-022": "removed"}


def test_diff_sees_pin_and_shield_changes_as_their_own_objects() -> None:
    a = full()
    b = edit.clone_with(a, [])
    h = next(x for x in b.harnesses.values() if x.shields)
    c = h.connectors[0]
    pins = [evolve(c.pins[0], signal="Z"), *c.pins[1:]]
    s = h.shields[0]
    from harness_design_studio.core.commands import apply_ops

    apply_ops(
        b,
        [
            Put(
                "harnesses",
                evolve(
                    h,
                    connectors=[evolve(c, pins=pins), *h.connectors[1:]],
                    shields=[evolve(s, end_a="pigtail"), *h.shields[1:]],
                ),
            )
        ],
    )
    d = vd.diff_projects(a, b)
    assert {(c_.kind, c_.id) for c_ in d.changes} == {
        ("cable_pin", f"{c.id}.{c.pins[0].id}"),
        ("shield", s.id),
    }


@settings(max_examples=25, deadline=None)
@given(
    st.lists(
        st.tuples(st.integers(0, 40), st.sampled_from(["colour", "remove", "gauge"])),
        min_size=0,
        max_size=8,
        unique_by=lambda t: t[0],
    )
)
def test_diff_property_matches_the_mutations(edits: list[tuple[int, str]]) -> None:
    a = full()
    hid = releasable(a)
    h = a.harnesses[hid]
    wires = list(h.wires)
    expected: set[tuple[str, str, str]] = set()
    new: list[Wire] = []
    for k, w in enumerate(wires):
        todo = next((kind for idx, kind in edits if idx % len(wires) == k), None)
        if todo == "remove":
            expected.add(("removed", "wire", w.id))
            continue
        if todo == "colour":
            w = evolve(w, colour="COLOUR-X")
            expected.add(("changed", "wire", w.id))
        elif todo == "gauge":
            w = evolve(w, gauge_awg=(w.gauge_awg or 20) + 1)
            expected.add(("changed", "wire", w.id))
        new.append(w)
    edited = evolve(h, wires=new, shields=[])
    b = edit.clone_with(a, [Put("harnesses", edited)])
    got = {(c.change, c.kind, c.id) for c in vd.diff_projects(a, b).changes if c.kind == "wire"}
    assert got == expected


def test_diff_markdown_and_table_are_readable_and_deterministic() -> None:
    a = full()
    b = edit.clone_with(a, [])
    unit = next(iter(b.units.values()))
    from harness_design_studio.core.commands import apply_ops

    apply_ops(b, [Put("units", evolve(unit, name="Renamed"))])
    d = vd.diff_projects(a, b)
    text = vd.render_markdown("T", d, before="old", after="new")
    assert text == vd.render_markdown("T", d, before="old", after="new")
    assert "1 changed" in text and "Unit `" in text and "name:" in text
    assert vd.to_table(d)[1][:3] == ["changed", "unit", unit.id]
    assert "No differences" in vd.render_markdown("T", vd.diff_projects(a, a))


def test_compare_command_on_two_project_folders(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    a = full()
    b = edit.clone_with(a, [])
    unit = next(iter(b.units.values()))
    from harness_design_studio.core.commands import apply_ops

    apply_ops(b, [Put("units", evolve(unit, name="Renamed"))])
    save_project(a, tmp_path / "a")
    save_project(b, tmp_path / "b")
    assert cli_main(["compare", str(tmp_path / "a"), str(tmp_path / "b")]) == 0
    assert f"Unit `{unit.id}`" in capsys.readouterr().out


# ---- outputs --------------------------------------------------------------------------------------


def test_title_block_and_revision_outputs_after_a_release(tmp_path: Path) -> None:
    p = full()
    hid = releasable(p)
    folder = exported(p, tmp_path)
    do_release(p, hid, folder)
    built = build_outputs(p)
    svg = built.files[f"harnesses/{hid}/drawing_A3_s1.svg"].decode()
    for needle in ("released", "Ada", "Bob", WHEN):
        assert needle in svg
    log = parse_csv(built.files["system/changelog.csv"])
    assert log[1][:4] == ["C0001", hid, "A", "released"] and log[1][6].startswith(
        "First release for the CDR"
    )
    report = built.files["system/revision_report.md"].decode()
    assert hid in report and "First release for the CDR" in report
    assert verify_outputs(p, built.files).ok


def test_verifier_catches_changelog_problems(tmp_path: Path) -> None:
    p = full()
    hid = releasable(p)
    do_release(p, hid, exported(p, tmp_path))
    files = build_outputs(p).files
    table = parse_csv(files["system/changelog.csv"])
    table.pop(1)
    files["system/changelog.csv"] = csv_bytes(table, stamp_of(p))
    assert "out_changelog" in {i.code for i in verify_outputs(p, files).errors}
    files = build_outputs(p).files
    files["system/revision_report.md"] = files["system/revision_report.md"].replace(
        hid.encode(), b"XXXX"
    )
    assert "out_changelog" in {i.code for i in verify_outputs(p, files).errors}


def test_revision_report_shows_differences_between_revisions(tmp_path: Path) -> None:
    p = full()
    hid = releasable(p)
    folder = exported(p, tmp_path)
    hist = do_release(p, hid, folder)
    plan = plan_new_revision(p, hid, by="Ada", comment="Rework colours here", when="2026-04-01")
    hist.execute(plan.label, plan.ops)
    h = p.harnesses[hid]
    hist.execute(
        "c", [Put("harnesses", evolve(h, wires=[evolve(h.wires[0], colour="WHT"), *h.wires[1:]]))]
    )
    text = revision_report(p, stamp_of(p).line)
    assert "working design against revision A" in text and "colour: (none) -> WHT" in text
    assert len(baselines_of(p, hid)) == 1 and len(changelog_rows(p, hid)) == 3


def test_empty_revision_report() -> None:
    assert "No harness has been put into review" in revision_report(full(), "x")


# ---- CLI ------------------------------------------------------------------------------------------


def test_cli_full_change_control_cycle(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    p = full()
    hid = releasable(p)
    proj = tmp_path / "p"
    save_project(p, proj)
    args = [str(proj), hid]
    assert (
        cli_main(["release", *args, "--by", "Ada", "--comment", "First release for CDR"]) == 1
    )  # no outputs yet
    assert cli_main(["export", str(proj)]) == 0
    assert cli_main(["release", *args, "--by", "Ada", "--comment", "short"]) == 1
    assert (  # placeholders without a reason are refused
        cli_main(["release", *args, "--by", "Ada", "--comment", "First release for CDR"]) == 1
    )
    assert (
        cli_main(
            [
                "release",
                *args,
                "--by",
                "Ada",
                "--checker",
                "Bob",
                "--comment",
                "First release for CDR",
                "--accept-placeholders",
                REASON,
                "--accept-unapproved-parts",
                REASON,
                "--date",
                WHEN,
            ]
        )
        == 0
    )
    out = capsys.readouterr().out
    assert "released" in out.lower() and "re-exported" in out
    q = load_project(proj).project
    assert q.harnesses[hid].status == "released"
    assert verify_outputs(q, read_folder(proj / "outputs")).ok  # re-stamped: current and consistent
    assert outputs_status(q, proj / "outputs").state == "current"
    assert cli_main(["verify", str(proj), "--outputs"]) == 0
    assert (
        cli_main(
            [
                "revise",
                *args,
                "--by",
                "Ada",
                "--comment",
                "Rework for the build",
                "--date",
                "2026-04-01",
            ]
        )
        == 0
    )
    assert cli_main(["diff", *args]) == 0
    text = capsys.readouterr().out
    assert "revision: A -> B" in text
    assert cli_main(["diff", *args, "--from", "A", "--to", "A"]) == 0
    assert cli_main(["diff", *args, "--from", "Q"]) == 2
    assert cli_main(["log", str(proj)]) == 0
    assert "new revision started" in capsys.readouterr().out
    assert cli_main(["review", *args, "--by", "Ada", "--date", "2026-04-02"]) == 0


def test_cli_diff_needs_a_baseline(tmp_path: Path) -> None:
    p = full()
    save_project(p, tmp_path / "p")
    assert cli_main(["diff", str(tmp_path / "p"), releasable(p)]) == 2
    assert cli_main(["diff", str(tmp_path / "p"), "NOPE"]) == 2
