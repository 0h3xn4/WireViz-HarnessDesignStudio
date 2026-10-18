# mypy: disable-error-code="no-untyped-def,no-untyped-call"
"""SH-24: "Fix all (n)" in the Checks tab applies every one-click fix as ONE undo step, says how many
it will fix, and is disabled with its reason when there is nothing to fix, the project is read-only
or the rules are still running. Offscreen, in a real window."""

from pathlib import Path

import pytest

pytest.importorskip("PySide6")
pytestmark = pytest.mark.gui

from PySide6.QtWidgets import QApplication  # noqa: E402

from harness_design_studio.core import checks  # noqa: E402
from harness_design_studio.core.io.layout import model_hash  # noqa: E402
from harness_design_studio.core.samples import new_project  # noqa: E402
from harness_design_studio.core.vcs.snapshot import carried_interfaces  # noqa: E402
from harness_design_studio.gui import strings  # noqa: E402
from tests.gui_helpers import make_window  # noqa: E402
from tests.test_accessibility import unnamed  # noqa: E402
from tests.test_change_control import do_release, exported, full, releasable  # noqa: E402
from tests.test_fix_all import (  # noqa: E402
    drop_connectors_of_a_released_link,
    lose_connectors,
    project_with_fixable_findings,
)


@pytest.fixture
def win(qtbot, tmp_path: Path):
    w = make_window(tmp_path)
    qtbot.addWidget(w)
    w.ctl._install(project_with_fixable_findings(), None, None)
    w.go_to("checks")
    QApplication.processEvents()
    w.checks_panel.refresh()
    return w


def messages(win) -> list[tuple[str, bool]]:
    got: list[tuple[str, bool]] = []
    win.ctl.message.connect(lambda text, undoable: got.append((text, undoable)))
    return got


def test_the_button_says_how_many_problems_it_will_fix(win) -> None:
    n = len(checks.fixable(win.ctl.open_findings()))
    assert n >= 2 and win.ctl.fixable_count() == n
    b = win.checks_panel.fix_all_btn
    assert b.text() == f"Fix all ({n})" and b.accessibleName() == f"Fix all ({n})"
    assert b.isEnabled() and "one step" in b.toolTip() and f"{n} problems" in b.toolTip()
    assert checks.fix_summary(win.ctl.open_findings()) in b.toolTip()  # what kinds of fix it makes
    assert not b.icon().isNull() and not b.property("primary")  # Generate is the one primary button


def test_one_click_fixes_everything_that_has_a_fix_as_one_undo_step(win) -> None:
    ctl = win.ctl
    before, revision = model_hash(ctl.project), ctl.history.revision
    n = ctl.fixable_count()
    got = messages(win)
    win.checks_panel.fix_all_btn.click()
    assert ctl.history.revision == revision + 1  # ONE step
    assert got and got[-1][1] is True
    assert got[-1][0].startswith(f"Fixed {n} problems in one step: ")
    assert "Confirm connectors" not in got[-1][0]  # a person confirms an auto-filled choice
    assert ctl.history.next_undo_label == strings.STEP_FIX_ALL.format(n)
    assert not checks.fixable(ctl.open_findings())
    assert [f for f in ctl.open_findings() if f.rule == "unconfirmed"]  # still waiting for a person
    win.checks_panel.refresh()
    assert win.checks_panel.fix_all_btn.text() == f"Fix all ({ctl.fixable_count()})"
    ctl.undo()
    assert model_hash(ctl.project) == before  # one Undo takes them all back
    win.checks_panel.refresh()
    assert win.checks_panel.fix_all_btn.text() == f"Fix all ({n})"


def test_it_is_disabled_with_a_reason_when_nothing_has_a_fix(qtbot, tmp_path: Path) -> None:
    w = make_window(tmp_path)
    qtbot.addWidget(w)
    w.ctl._install(new_project("x"), None, None)
    w.go_to("checks")
    QApplication.processEvents()
    w.checks_panel.refresh()
    b = w.checks_panel.fix_all_btn
    assert b.text() == "Fix all (0)" and not b.isEnabled()
    assert strings.CHECKS_FIX_ALL_NONE in b.toolTip()
    assert b.accessibleDescription() == strings.CHECKS_FIX_ALL_NONE
    got = messages(w)
    revision = w.ctl.history.revision
    assert w.ctl.fix_all() is False  # called anyway: it says so and changes nothing
    assert w.ctl.history.revision == revision
    assert got[-1][0] == "Nothing could be fixed automatically."


def test_it_is_disabled_in_a_read_only_project_and_changes_nothing(win) -> None:
    win.ctl.project.read_only = True
    win.ctl.stateChanged.emit()
    win.checks_panel.refresh()
    b = win.checks_panel.fix_all_btn
    assert not b.isEnabled() and strings.WHY_READ_ONLY in b.toolTip()
    assert b.accessibleDescription() == strings.WHY_READ_ONLY
    before, got = model_hash(win.ctl.project), messages(win)
    assert win.ctl.fix_all() is False
    assert model_hash(win.ctl.project) == before and got[-1][0] == strings.READ_ONLY_REFUSAL


def test_it_does_not_wait_for_a_running_check_like_the_fix_button_of_a_card(
    win, monkeypatch
) -> None:
    monkeypatch.setattr(win.ctl, "drc_busy", lambda: True)
    win.checks_panel.refresh()
    assert win.checks_panel.fix_all_btn.isEnabled()


def test_the_button_is_named_and_reachable_by_keyboard(win) -> None:
    assert unnamed(win) == []
    b = win.checks_panel.fix_all_btn
    assert b.focusPolicy() & b.focusPolicy().TabFocus
    assert b.objectName() == "checks-fix-all"


def test_a_locked_finding_is_left_alone_and_named_in_the_message(qtbot, tmp_path: Path) -> None:
    from harness_design_studio.core.commands import History

    p = full()
    hid = releasable(p)
    iid = sorted(carried_interfaces(p.harnesses[hid]))[0]
    hist = History(p)
    do_release(p, hid, exported(p, tmp_path), hist)
    drop_connectors_of_a_released_link(p, iid)
    other = next(x for x in sorted(p.interfaces) if x != iid and x not in carried_interfaces(p.harnesses[hid]))  # fmt: skip
    lose_connectors(p, other)
    w = make_window(tmp_path / "w")
    qtbot.addWidget(w)
    w.ctl._install(p, None, None)
    got = messages(w)
    revision = w.ctl.history.revision
    assert w.ctl.fix_all() is True
    assert w.ctl.history.revision == revision + 1
    text = got[-1][0]
    assert "1 problem left alone" in text and "released" in text  # the one the release holds
    assert {f.object_id for f in checks.fixable(w.ctl.open_findings())} == {iid}
