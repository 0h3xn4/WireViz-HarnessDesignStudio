"""SC-16 / SC-2 data: the change log as rows, and a diff as rows grouped by kind, with values a
person can read (no raw None, no Python reprs)."""

from pathlib import Path

from harness_design_studio.core import edit
from harness_design_studio.core.commands import Put
from harness_design_studio.core.model import Project, evolve
from harness_design_studio.core.vcs import diff as vd
from harness_design_studio.core.vcs import timeline
from harness_design_studio.core.vcs.release import plan_new_revision
from harness_design_studio.core.vcs.report import changelog_rows
from tests.test_change_control import WHEN, do_release, exported, full, releasable


def two_revisions(tmp_path: Path) -> tuple[Project, str]:
    p = full()
    hid = releasable(p)
    hist = do_release(p, hid, exported(p, tmp_path))
    plan = plan_new_revision(p, hid, by="Ada", when=WHEN, comment="Second look at the wires")
    assert plan.ok, [b.message for b in plan.blockers]
    hist.execute(plan.label, plan.ops)
    h = p.harnesses[hid]
    wire = evolve(h.wires[0], gauge_awg=22, colour="red")
    hist.execute("tweak", [Put("harnesses", evolve(h, wires=[wire, *h.wires[1:]]))])
    return p, hid


def test_the_timeline_has_one_row_per_entry_with_the_same_words_as_the_log(tmp_path: Path) -> None:
    p, hid = two_revisions(tmp_path)
    rows = timeline.timeline(p)
    log = changelog_rows(p)[1:]
    assert [r.id for r in rows] == [row[0] for row in log]
    assert [r.event for r in rows] == [row[3] for row in log]
    assert [(r.harness_id, r.revision, r.by, r.when, r.comment) for r in rows] == [
        (row[1], row[2], row[4], row[5], row[6]) for row in log
    ]
    assert {r.kind for r in rows} == {"release", "new_revision"}
    assert timeline.timeline(p, "W999") == []
    assert all(r.harness_id == hid for r in timeline.timeline(p, hid))


def test_rows_say_whether_a_baseline_exists_to_compare(tmp_path: Path) -> None:
    p, hid = two_revisions(tmp_path)
    rows = timeline.timeline(p, hid)
    by_kind = {r.kind: r for r in rows}
    assert by_kind["release"].has_baseline is True
    assert by_kind["new_revision"].has_baseline is False


def test_comments_are_one_line(tmp_path: Path) -> None:
    p, hid = two_revisions(tmp_path)
    assert all("\n" not in r.comment for r in timeline.timeline(p))


def test_a_project_without_a_log_has_an_empty_timeline() -> None:
    assert timeline.timeline(full()) == []


def test_compare_revisions_uses_the_baselines_and_the_working_design(tmp_path: Path) -> None:
    p, hid = two_revisions(tmp_path)
    work = timeline.compare_revisions(p, hid, "A")
    assert not work.empty
    kinds = {c.kind for c in work.changes}
    assert "wire" in kinds
    assert timeline.compare_revisions(p, hid, "A", "A").empty


def test_unknown_revisions_are_a_plain_error(tmp_path: Path) -> None:
    import pytest

    p, hid = two_revisions(tmp_path)
    with pytest.raises(timeline.ReleaseError, match="revision Z"):
        timeline.compare_revisions(p, hid, "Z")


def test_values_never_show_python_none_or_reprs() -> None:
    assert timeline.format_value(None) == "(none)"
    assert timeline.format_value([]) == "(empty)"
    assert timeline.format_value({}) == "(empty)"
    assert timeline.format_value({"20": 5.0, "22": None}) == "20: 5.0, 22: (none)"
    assert timeline.format_value([{"id": "W1"}, {"id": "W2"}]) == "W1, W2"
    assert timeline.format_value(["a", None]) == "a, (none)"
    assert timeline.format_value(True) == "True"
    assert "None" not in timeline.format_value({"a": {"b": None}})
    assert len(timeline.format_value("x" * 200)) == 80


def test_scalar_values_read_exactly_like_the_diff_reports() -> None:
    for v in (None, 3, 2.5, "text", ["a", "b"], [], "x" * 100, [{"id": "W1"}]):
        assert timeline.format_value(v) == vd._show(v)


def test_diff_rows_are_flat_and_readable(tmp_path: Path) -> None:
    p, hid = two_revisions(tmp_path)
    diff = timeline.compare_revisions(p, hid, "A")
    rows = timeline.diff_rows(diff)
    assert rows and all(isinstance(r, timeline.DiffRow) for r in rows)
    assert all("None" not in r.before + r.after for r in rows)
    gauge = next(r for r in rows if r.field == "gauge_awg")
    assert (gauge.change, gauge.kind_name, gauge.label) == ("changed", "Wire", "Gauge AWG")
    assert gauge.after == "22" and gauge.before != gauge.after
    table = vd.to_table(diff)[1:]
    assert len(rows) == len(table)
    assert [(r.change, r.kind, r.id, r.field, r.before, r.after) for r in rows] == [
        tuple(t) for t in table
    ]


def test_diff_groups_follow_the_kind_order_and_hold_all_rows() -> None:
    d = vd.Diff([
        vd.ObjectChange("wire", "W1-001", "changed", (vd.FieldChange("colour", None, "red"),)),
        vd.ObjectChange("unit", "OBC", "added"),
        vd.ObjectChange("wire", "W1-002", "removed"),
        vd.ObjectChange("harness", "W1", "changed", (vd.FieldChange("status", "draft", "released"),)),
    ])  # fmt: skip
    groups = timeline.diff_groups(d)
    assert [g.kind for g in groups] == [
        k for k in vd.KIND_NAMES if k in {"unit", "harness", "wire"}
    ]
    assert [g.name for g in groups] == ["Unit", "Harness", "Wire"]
    wire = groups[-1]
    assert [r.id for r in wire.rows] == ["W1-001", "W1-002"]
    assert wire.rows[0].before == "(none)" and wire.rows[0].after == "red"
    assert wire.counts == {"added": 0, "removed": 1, "changed": 1}
    assert sum(len(g.rows) for g in groups) == len(timeline.diff_rows(d))
    assert timeline.diff_groups(vd.Diff()) == []


def test_an_unknown_kind_is_still_shown() -> None:
    d = vd.Diff([vd.ObjectChange("gizmo", "G1", "added")])
    [g] = timeline.diff_groups(d)
    assert g.kind == "gizmo" and g.name == "gizmo"


def test_nothing_in_it_changes_the_project(tmp_path: Path) -> None:
    p, hid = two_revisions(tmp_path)
    clone = edit.clone_with(p, [])
    timeline.timeline(p)
    timeline.diff_groups(timeline.compare_revisions(p, hid, "A"))
    assert clone.baselines == p.baselines and clone.changelog == p.changelog
