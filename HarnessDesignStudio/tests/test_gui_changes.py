"""M6 (GUI): review, release, new revision, changes (with marks on the diagram) and change log."""

import pytest

pytest.importorskip("PySide6")
pytestmark = pytest.mark.gui

from harness_design_studio.core.commands import Put  # noqa: E402
from harness_design_studio.core.io.saver import save_project  # noqa: E402
from harness_design_studio.core.model import evolve  # noqa: E402
from harness_design_studio.core.samples import sat15_full  # noqa: E402
from harness_design_studio.gui.dialogs import ChangeDialog, DiffDialog, HistoryDialog  # noqa: E402
from tests.gui_helpers import DialogScript, make_window  # noqa: E402


@pytest.fixture
def win(qtbot, tmp_path):  # type: ignore[no-untyped-def]
    w = make_window(tmp_path)
    qtbot.addWidget(w)
    p = sat15_full()
    save_project(p, tmp_path / "proj")
    assert w.open_project(tmp_path / "proj")
    w.ctl.today = lambda: "2026-03-01"
    w.go_to("harness")
    return w


def releasable(win) -> str:  # type: ignore[no-untyped-def]
    p = win.ctl.project
    return str(
        next(
            h.id
            for h in sorted(p.harnesses.values(), key=lambda x: x.id)
            if all(w.gauge_awg and w.length_m for w in h.wires)
        )
    )


def fill(by: str = "Ada", comment: str = "First release for the CDR", checker: str = "Bob"):  # type: ignore[no-untyped-def]
    def fn(d: ChangeDialog) -> None:
        d.by.setText(by)
        d.checker.setText(checker)
        d.comment.setPlainText(comment)
        d.placeholder_reason.setText("Test project: values are placeholders")
        d.parts_reason.setText("Test project: example parts")

    return fn


def select(win, hid: str) -> None:  # type: ignore[no-untyped-def]
    assert win.harness_view.select_harness(hid)


def test_buttons_follow_the_status_of_the_selected_harness(win) -> None:  # type: ignore[no-untyped-def]
    hid = releasable(win)
    select(win, hid)
    view = win.harness_view
    b, more = (
        view.action_buttons,
        view.more_actions,
    )  # the change-control buttons of the Harness tab
    assert b["review"].isEnabled() and b["release"].isEnabled() and not b["revise"].isEnabled()
    assert not more["changes"].isEnabled() and more["history"].isEnabled()
    assert more["delete"].isEnabled()  # a draft can be deleted


def test_release_dialog_lists_blockers_and_disables_ok(win) -> None:  # type: ignore[no-untyped-def]
    hid = releasable(win)
    script = DialogScript(win, accept=False)
    win.change_flow("release", hid)
    dlg = script.seen[0]
    assert isinstance(dlg, ChangeDialog)
    assert "outputs" in dlg.status.text().lower()  # not exported yet
    dlg.by.setText("Ada")
    dlg.comment.setPlainText("A long enough comment")
    assert not dlg.ok.isEnabled()  # a blocker is still there


def test_release_dialog_asks_for_a_reason_while_values_are_placeholders(win) -> None:  # type: ignore[no-untyped-def]
    hid = releasable(win)
    win.export_flow()
    script = DialogScript(win, accept=False)
    win.change_flow("release", hid)
    dlg = script.seen[0]
    assert isinstance(dlg, ChangeDialog) and dlg.blockers == []  # outputs are exported
    dlg.by.setText("Ada")
    dlg.comment.setPlainText("A long enough comment")
    assert not dlg.ok.isEnabled()  # the reason is missing
    assert dlg.accepted_placeholders() is None
    dlg.placeholder_reason.setText("short")
    assert not dlg.ok.isEnabled()
    dlg.placeholder_reason.setText("Practice project, demo values")
    assert dlg.accepted_placeholders() == "Practice project, demo values"
    assert not dlg.ok.isEnabled()  # the example parts need a reason too
    assert dlg.accepted_unapproved_parts() is None
    dlg.parts_reason.setText("Too short")
    assert not dlg.ok.isEnabled()  # too short
    dlg.parts_reason.setText("Example parts, practice only")
    assert dlg.ok.isEnabled() and dlg.accepted_unapproved_parts() == "Example parts, practice only"


def test_full_cycle_release_lock_new_revision_changes_and_log(win, qtbot) -> None:  # type: ignore[no-untyped-def]
    hid = releasable(win)
    win.export_flow()  # outputs must be exported before a release
    select(win, hid)
    DialogScript(win, fill())
    win.change_flow("release", hid)
    h = win.ctl.project.harnesses[hid]
    assert (h.status, h.approver, h.checker) == ("released", "Ada", "Bob")
    view = win.harness_view
    view.refresh()
    assert view.release_chip.state() == "released"  # the chip beside the harness name
    assert win.project_tree.state_of("harness", hid)[0] == "released"  # and the row in the tree
    # locked: editing is refused with a plain message
    assert not win.ctl.run("edit", [Put("harnesses", evolve(h, name="Nope"))])
    assert "released" in win.toasts.messages[-1]
    # new revision unlocks
    DialogScript(win, fill(comment="Rework the colours"))
    win.change_flow("revise", hid)
    assert win.ctl.project.harnesses[hid].revision == "B"
    w = win.ctl.project.harnesses[hid].wires[0]
    h2 = win.ctl.project.harnesses[hid]
    assert win.ctl.run(
        "colour", [Put("harnesses", evolve(h2, wires=[evolve(w, colour="WHT"), *h2.wires[1:]]))]
    )
    # changes dialog marks the diagram
    script = DialogScript(win)
    win.change_flow("changes", hid)
    dlg = script.seen[0]
    assert isinstance(dlg, DiffDialog) and not dlg.diff.empty
    dlg.mark.click()
    assert win.ctl.diff_marks.get(hid) == "changed"
    clear = dlg.findChild(type(dlg.mark), "diff-clear")
    assert clear is not None
    clear.click()
    assert win.ctl.diff_marks == {}
    # change log
    script = DialogScript(win)
    win.change_flow("history", hid)
    hist = script.seen[0]
    assert isinstance(hist, HistoryDialog) and hist.list.count() == 2


def test_undo_takes_a_release_back(win) -> None:  # type: ignore[no-untyped-def]
    hid = releasable(win)
    win.export_flow()
    DialogScript(win, fill())
    win.change_flow("release", hid)
    win.ctl.undo()
    assert win.ctl.project.harnesses[hid].status == "draft" and not win.ctl.project.baselines


def test_review_flow(win) -> None:  # type: ignore[no-untyped-def]
    hid = releasable(win)
    DialogScript(win, fill(comment=""))
    win.change_flow("review", hid)
    assert win.ctl.project.harnesses[hid].status == "in_review"


def test_changes_without_a_baseline_says_so(win) -> None:  # type: ignore[no-untyped-def]
    win.change_flow("changes", releasable(win))
    assert "no baseline" in win.toasts.messages[-1].lower()


def test_marks_are_drawn_and_cleared_on_project_change(win) -> None:  # type: ignore[no-untyped-def]
    unit = next(iter(win.ctl.project.units))
    win.ctl.set_marks({unit: "changed"})
    win.view.dscene.refresh_all()
    win.view.grab()  # paints the marked unit without errors
    win.ctl._install(sat15_full(), None, None)
    assert win.ctl.diff_marks == {}
