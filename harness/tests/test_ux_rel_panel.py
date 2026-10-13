# mypy: disable-error-code="no-untyped-def,no-untyped-call"
"""SC-16: the Releases tab (timeline, differences, per-harness actions), standalone and on flatsat."""

from pathlib import Path

import pytest

pytest.importorskip("PySide6")
pytestmark = pytest.mark.gui

from PySide6.QtCore import QModelIndex, Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QAbstractButton, QAbstractItemView, QComboBox, QWidget  # noqa: E402

from harness_design_studio.core.commands import Put  # noqa: E402
from harness_design_studio.core.model import evolve  # noqa: E402
from harness_design_studio.core.vcs.release import plan_new_revision  # noqa: E402
from harness_design_studio.gui import strings  # noqa: E402
from harness_design_studio.gui.releases_panel import (  # noqa: E402
    ReleasesPanel,
    diff_table_rows,
    harness_state,
)
from harness_design_studio.gui.states import STATE_ROLE  # noqa: E402
from tests.test_accessibility import unnamed  # noqa: E402
from tests.ux_rel import collect, flatsat_controller, release_all, settings, themed  # noqa: E402


@pytest.fixture
def ctl(qtbot, tmp_path: Path):
    themed()
    return flatsat_controller(tmp_path)


@pytest.fixture
def released(ctl):
    assert release_all(ctl) == ["W001", "W003"]
    return ctl


def make_panel(qtbot, ctl, tmp_path: Path) -> ReleasesPanel:
    panel = ReleasesPanel(ctl, themed(), settings=settings(tmp_path))
    qtbot.addWidget(panel)
    panel.resize(1100, 700)
    panel.show()
    return panel


def revise_and_edit(ctl, hid="W001") -> None:
    plan = plan_new_revision(ctl.project, hid, by="Ada", comment="Second look at the wires", when="2026-03-02")  # fmt: skip
    assert ctl.apply_change(plan, "revised")
    h = ctl.project.harnesses[hid]
    wire = evolve(h.wires[0], colour="red", length_m=2.5)
    assert ctl.run("tweak", [Put("harnesses", evolve(h, wires=[wire, *h.wires[1:]]))])


def column(panel: ReleasesPanel, key: str) -> int:
    return panel.timeline_model.column_index(key)


def test_an_empty_project_says_what_to_do(qtbot, ctl, tmp_path) -> None:
    panel = make_panel(qtbot, ctl, tmp_path)
    assert panel.timeline_empty.isVisible()
    assert "Submit a draft for review" in panel.timeline_empty.text()
    assert panel.summary.text() == strings.REL_DIFF_NEED_HARNESS
    assert not panel.action_enabled("release")
    assert panel.action_note.isVisible() and panel.action_note.text() == strings.REL_CHOOSE_HARNESS


def test_the_timeline_lists_every_step_with_state_chips(qtbot, released, tmp_path) -> None:
    panel = make_panel(qtbot, released, tmp_path)
    model = panel.timeline_model
    assert model.rowCount() == 2
    assert not panel.timeline_empty.isVisible()
    ev, base = column(panel, "event"), column(panel, "baseline")
    assert model.state_at(0, ev) == "released" and model.text_at(0, ev) == "released"
    assert model.state_at(0, base) == "released" and model.text_at(0, base) == "Baseline A"
    assert [model.text_at(r, column(panel, "harness")) for r in range(2)] == ["W001", "W003"]
    view_index = panel.timeline.proxy.index(0, ev)
    assert view_index.data(STATE_ROLE) == "released"


def test_a_review_and_a_new_revision_get_their_own_chips(qtbot, released, tmp_path) -> None:
    from harness_design_studio.core.vcs.release import plan_submit_review

    p = released.project
    draft = next(h for h in sorted(p.harnesses) if p.harnesses[h].status == "draft")
    plan = plan_submit_review(p, draft, by="Ada", when="2026-03-02")
    assert released.apply_change(plan, "review")
    revise_and_edit(released)
    panel = make_panel(qtbot, released, tmp_path)
    ev = column(panel, "event")
    kinds = {panel.timeline_model.text_at(r, ev): panel.timeline_model.state_at(r, ev) for r in range(panel.timeline_model.rowCount())}  # fmt: skip
    assert kinds == {
        "released": "released",
        "submitted for review": "in-review",
        "new revision started": "revised",
    }
    # a new revision has no frozen copy of its own: the baseline cell stays empty, not "none"
    rows = panel.timeline_model.rows()
    revised = next(r for r in rows if r["kind"] == "new_revision")
    assert panel.timeline_model.text_at(rows.index(revised), column(panel, "baseline")) == ""
    assert panel.timeline_model.state_at(rows.index(revised), column(panel, "baseline")) is None


def test_choosing_a_harness_filters_the_timeline_and_names_its_state(qtbot, released, tmp_path) -> None:  # fmt: skip
    panel = make_panel(qtbot, released, tmp_path)
    assert panel.harness.count() == 1 + len(released.project.harnesses)
    assert panel.select_harness("W003")
    assert [r["harness"] for r in panel.timeline_model.rows()] == ["W003"]
    assert panel.state.state() == "released" and "A" in (panel.state.text() or "")
    assert panel.select_harness("W002")
    assert panel.timeline_empty.isVisible()
    assert panel.timeline_empty.text() == strings.REL_EMPTY_ONE.format("W002")
    assert panel.state.state() == "draft"
    assert not panel.select_harness("W404")


def test_actions_follow_the_state_and_emit_signals(qtbot, released, tmp_path) -> None:
    panel = make_panel(qtbot, released, tmp_path)
    asked = collect(panel.changeRequested)
    release_spy = collect(panel.releaseRequested)
    revise_spy = collect(panel.reviseRequested)
    review_spy = collect(panel.submitReviewRequested)
    panel.select_harness("W001")  # released
    assert panel.action_enabled("revise")
    assert not panel.action_enabled("release") and not panel.action_enabled("review")
    assert "released" in panel.action_buttons["release"].toolTip()  # a disabled button says why
    panel.action_buttons["revise"].click()
    panel.select_harness("W002")  # a draft
    assert panel.action_enabled("review") and panel.action_enabled("release")
    assert not panel.action_enabled("revise")
    panel.action_buttons["release"].click()
    panel.action_buttons["review"].click()
    assert asked == [("revise", "W001"), ("release", "W002"), ("review", "W002")]
    assert release_spy == [("W002",)]
    assert revise_spy == [("W001",)]
    assert review_spy == [("W002",)]


def test_a_read_only_project_offers_no_action(qtbot, released, tmp_path) -> None:
    released.project.read_only = True
    panel = make_panel(qtbot, released, tmp_path)
    panel.select_harness("W002")
    assert not any(panel.action_enabled(a) for a in panel.action_buttons)
    assert strings.REL_READ_ONLY in panel.action_buttons["release"].toolTip()


def test_selecting_a_timeline_line_selects_its_harness_for_the_actions(qtbot, released, tmp_path) -> None:  # fmt: skip
    panel = make_panel(qtbot, released, tmp_path)
    assert panel.harness.currentData() == ""
    seen = collect(panel.harnessChanged)
    panel.timeline.selectRow(1)
    assert panel.current_harness() == "W003"
    assert panel.action_enabled("revise")
    assert seen[-1] == ("W003",)


def test_differences_group_by_kind_with_counts_and_no_raw_none(qtbot, released, tmp_path) -> None:
    revise_and_edit(released)
    panel = make_panel(qtbot, released, tmp_path)
    panel.select_harness("W001")
    # revision A (the baseline) against the working design is the default
    assert panel.before.currentData() == "A" and panel.after.currentData() == ""
    assert "compared with" in panel.summary.text()
    names = [panel.group_model.item(r).text() for r in range(panel.group_model.rowCount())]
    assert names[0].startswith(strings.REL_ALL_KINDS)
    assert any(n.startswith("Wire: 1 changed") for n in names)
    assert any(n.startswith("Harness: 1 changed") for n in names)
    rows = panel.diff_model.rows()
    assert rows
    for row in rows:
        for key in ("change", "kind", "id", "field", "before", "after"):
            assert "None" not in str(row[key]) and row[key] is not None
    changed = [r for r in rows if r["kind"] == "Wire" and r["field"] == "Length (m)"]
    assert changed and (changed[0]["before"], changed[0]["after"]) == ("3.45", "2.5")
    cleared = [r for r in rows if r["field"] == "Approver"]
    assert cleared and cleared[0]["after"] == "(none)"  # a cleared value reads "(none)", not None
    # one kind only
    panel.select_group("wire")
    assert {r["kind"] for r in panel.diff_model.rows()} == {"Wire"}
    panel.select_group(None)
    assert len({r["kind"] for r in panel.diff_model.rows()}) > 1


def test_compare_two_revisions_and_the_same_revision(qtbot, released, tmp_path) -> None:
    revise_and_edit(released)
    panel = make_panel(qtbot, released, tmp_path)
    assert panel.compare("W001", "A", None)
    assert panel.diff_model.rowCount() > 0
    assert not panel.compare("W001", "Z", None)
    panel.after.setCurrentIndex(panel.after.findData("A"))  # revision A with revision A
    assert panel.summary.text() == strings.REL_DIFF_SAME
    assert panel.diff_model.rowCount() == 0 and not panel.mark.isEnabled()


def test_a_harness_without_a_baseline_says_so(qtbot, released, tmp_path) -> None:
    panel = make_panel(qtbot, released, tmp_path)
    panel.select_harness("W002")
    assert panel.summary.text() == strings.REL_DIFF_NO_BASE.format("W002")
    assert not panel.before.isEnabled() and not panel.mark.isEnabled()


def test_an_unchanged_released_harness_has_no_differences(qtbot, released, tmp_path) -> None:
    panel = make_panel(qtbot, released, tmp_path)
    panel.select_harness("W001")
    assert panel.summary.text() == strings.REL_DIFF_NONE.format("Revision A", "Working design")
    assert panel.group_model.rowCount() == 1  # only "All kinds (0)"
    assert not panel.mark.isEnabled()


def test_mark_on_diagram_goes_through_the_controller(qtbot, released, tmp_path) -> None:
    revise_and_edit(released)
    panel = make_panel(qtbot, released, tmp_path)
    panel.select_harness("W001")
    marks = collect(released.marksChanged)
    assert panel.mark.isEnabled()
    panel.mark.click()
    assert released.diff_marks.get("W001") == "changed"
    assert len(marks) == 1
    panel.clear.click()
    assert released.diff_marks == {}


def test_the_diff_rows_say_added_and_removed_in_words() -> None:
    from harness_design_studio.core.vcs.timeline import DiffGroup, DiffRow

    g = DiffGroup(
        "wire",
        "Wire",
        (
            DiffRow("added", "wire", "Wire", "W9", "", "", "", ""),
            DiffRow("removed", "wire", "Wire", "W8", "", "", "", ""),
            DiffRow("changed", "wire", "Wire", "W7", "colour", "Colour", "(none)", "red"),
        ),
    )
    rows = diff_table_rows([g])
    assert (rows[0]["change"], rows[0]["before"], rows[0]["field"]) == ("Added", strings.REL_DID_NOT_EXIST, strings.REL_WHOLE_OBJECT)  # fmt: skip
    assert (rows[1]["change"], rows[1]["after"]) == ("Removed", strings.REL_NO_LONGER)
    assert rows[2]["before"] == "(none)"


def test_harness_state_words(released) -> None:
    p = released.project
    assert harness_state(p, "W001") == "released"
    assert harness_state(p, "W002") == "draft"
    revise_and_edit(released)
    assert harness_state(released.project, "W001") == "revised"


def test_the_panel_follows_the_project(qtbot, ctl, tmp_path) -> None:
    panel = make_panel(qtbot, ctl, tmp_path)
    assert panel.timeline_model.rowCount() == 0
    release_all(ctl)
    assert panel.timeline_model.rowCount() == 2  # a visible panel refreshes itself
    assert panel.harness.itemText(panel.harness.findData("W001")).startswith("W001 — Released")


def test_keyboard_only(qtbot, released, tmp_path) -> None:
    panel = make_panel(qtbot, released, tmp_path)
    reached: list[QWidget] = []
    panel.harness.setFocus()
    for _ in range(14):
        w = panel.focusWidget()
        if w is not None and w not in reached:
            reached.append(w)
        QTest.keyClick(w or panel, Qt.Key.Key_Tab)
    names = {w.objectName() for w in reached}
    assert {"releases-harness", "releases-timeline"} <= names
    # pick a harness with the keys, then press the focused action button with Space
    panel.harness.setFocus()
    QTest.keyClick(panel.harness, Qt.Key.Key_Down)  # W001
    assert panel.current_harness() == "W001"
    spy = collect(panel.changeRequested)
    panel.action_buttons["revise"].setFocus()
    QTest.keyClick(panel.action_buttons["revise"], Qt.Key.Key_Space)
    assert spy == [("revise", "W001")]
    # the table is reachable and moves with the arrows
    panel.timeline.setFocus()
    QTest.keyClick(panel.timeline, Qt.Key.Key_Down)
    assert panel.timeline.currentIndex().isValid()


def test_every_control_has_a_name(qtbot, released, tmp_path) -> None:
    panel = make_panel(qtbot, released, tmp_path)
    panel.select_harness("W001")
    assert unnamed(panel) == []
    for b in panel.findChildren(QAbstractButton):
        if not b.objectName().startswith("qt_"):  # Qt's own corner button of a table
            assert b.toolTip(), b.objectName()
    for c in panel.findChildren(QComboBox):
        assert c.accessibleName()
    for v in panel.findChildren(QAbstractItemView):
        if v.objectName().startswith("releases-"):  # not the pop-up list of a combo box
            assert v.accessibleName()
    assert isinstance(panel.group_index("wire"), QModelIndex)
