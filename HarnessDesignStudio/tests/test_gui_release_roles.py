"""REQ-CC-08, F-07 (1.9.0): the release dialogs with the project setting `release_distinct_roles`
on: a note says three different people are required, the name that Git has is the default, the
checker is asked for as required, and OK says in words which two names are the same. With the
setting off the dialogs are as they were."""

import pytest

pytest.importorskip("PySide6")
pytestmark = pytest.mark.gui

from harness_design_studio.core import configcheck  # noqa: E402
from harness_design_studio.core.io.saver import save_project  # noqa: E402
from harness_design_studio.core.samples import sat15_full  # noqa: E402
from harness_design_studio.gui import strings  # noqa: E402
from harness_design_studio.gui.dialogs import ChangeDialog  # noqa: E402
from tests.gui_helpers import DialogScript, make_window  # noqa: E402

REASON = "Test project: values are placeholders"


@pytest.fixture
def win(qtbot, tmp_path, monkeypatch):  # type: ignore[no-untyped-def]
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(tmp_path / "no-such-gitconfig"))
    w = make_window(tmp_path)
    qtbot.addWidget(w)
    save_project(sat15_full(), tmp_path / "proj")
    assert w.open_project(tmp_path / "proj")
    w.ctl.today = lambda: "2026-03-01"
    w.go_to("harness")
    return w


def hid_of(win) -> str:  # type: ignore[no-untyped-def]
    p = win.ctl.project
    return str(
        next(
            h.id
            for h in sorted(p.harnesses.values(), key=lambda x: x.id)
            if all(w.gauge_awg and w.length_m for w in h.wires)
        )
    )


def switch_on(win) -> None:  # type: ignore[no-untyped-def]
    plan = configcheck.plan_set_distinct_roles(win.ctl.project, True)
    assert win.ctl.run("Different people", plan.ops)


def shown(win, action: str, hid: str) -> ChangeDialog:  # type: ignore[no-untyped-def]
    script = DialogScript(win, accept=False)
    win.change_flow(action, hid)
    dlg = script.seen[0]
    assert isinstance(dlg, ChangeDialog)
    return dlg


def test_off_the_dialogs_have_no_note_and_the_checker_stays_optional(win) -> None:  # type: ignore[no-untyped-def]
    hid = hid_of(win)
    win.export_flow()
    dlg = shown(win, "release", hid)
    assert dlg.rule_note.isHidden() and dlg._roles_check is None
    dlg.by.setText("Ada")
    dlg.comment.setPlainText("A long enough comment")
    dlg.placeholder_reason.setText(REASON)
    dlg.parts_reason.setText(REASON)
    assert dlg.ok.isEnabled()  # no checker, as before
    assert shown(win, "review", hid).rule_note.isHidden()


def test_on_the_review_and_release_dialogs_say_three_people_are_needed(win) -> None:  # type: ignore[no-untyped-def]
    hid = hid_of(win)
    switch_on(win)
    review = shown(win, "review", hid)
    assert review.rule_note.text() == strings.ROLES_REVIEW_NOTE and not review.rule_note.isHidden()
    win.export_flow()
    dlg = shown(win, "release", hid)
    assert dlg.rule_note.text() == strings.ROLES_RELEASE_NOTE and not dlg.rule_note.isHidden()


def test_on_ok_waits_for_an_author_and_for_three_different_names(win) -> None:  # type: ignore[no-untyped-def]
    hid = hid_of(win)
    switch_on(win)
    script = DialogScript(win, lambda d: d.by.setText("Ann"))
    win.change_flow("review", hid)
    assert win.ctl.project.harnesses[hid].author == "Ann"
    win.export_flow()
    dlg = shown(win, "release", hid)
    dlg.comment.setPlainText("A long enough comment")
    dlg.placeholder_reason.setText(REASON)
    dlg.parts_reason.setText(REASON)
    dlg.by.setText("Ada")
    assert not dlg.ok.isEnabled() and "Name the person who checked it" in dlg.hint.text()
    dlg.checker.setText("ada")
    assert not dlg.ok.isEnabled() and "checker and the person who releases it" in dlg.hint.text()
    dlg.checker.setText("Ann")
    assert not dlg.ok.isEnabled() and "author and the checker" in dlg.hint.text()
    dlg.checker.setText("Bob")
    assert dlg.ok.isEnabled()
    del script


def test_on_a_harness_with_no_author_cannot_be_released_from_the_dialog(win) -> None:  # type: ignore[no-untyped-def]
    hid = hid_of(win)
    switch_on(win)
    win.export_flow()
    dlg = shown(win, "release", hid)
    dlg.by.setText("Ada")
    dlg.checker.setText("Bob")
    dlg.comment.setPlainText("A long enough comment")
    dlg.placeholder_reason.setText(REASON)
    dlg.parts_reason.setText(REASON)
    assert not dlg.ok.isEnabled() and "Nobody is recorded as the author" in dlg.hint.text()


def test_the_name_git_has_is_the_default_only_with_the_setting_on(  # type: ignore[no-untyped-def]
    win, tmp_path, monkeypatch
) -> None:
    cfg = tmp_path / "gitconfig"
    cfg.write_text("[user]\n\tname = Ann Author\n", encoding="utf-8")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(cfg))
    hid = hid_of(win)
    assert win._user_name() != "Ann Author"  # off: the name of the account, as before
    switch_on(win)
    assert win._user_name() == "Ann Author"
    dlg = shown(win, "review", hid)
    assert dlg.by.text() == "Ann Author" and dlg.by.toolTip() == strings.NAME_FROM_GIT_TIP
    win.settings.setValue("ui/user", "Saved Name")  # a name saved by the person comes first
    assert win._user_name() == "Saved Name"
    assert shown(win, "review", hid).by.toolTip() == ""
