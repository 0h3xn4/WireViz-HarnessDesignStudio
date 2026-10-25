# mypy: disable-error-code="no-untyped-def,no-untyped-call,attr-defined"
"""Workshop feedback M1: View > Show problem notices. Off, the notices nobody asked for are gone
(Problems button and count, count on the inspector tab, top-bar chip, corner chip, badges, the
pending-values link, the out-of-date banner); the banners that say why something cannot be done,
the Check button, the Checks, the Problems panel and the error text of dialogs always stay."""

import time
from pathlib import Path

import pytest

pytest.importorskip("PySide6")
from PySide6.QtCore import QSettings  # noqa: E402
from PySide6.QtWidgets import QApplication, QCheckBox  # noqa: E402

pytestmark = pytest.mark.gui

from harness_design_studio.core import templates  # noqa: E402
from harness_design_studio.core.io.loader import load_project  # noqa: E402
from harness_design_studio.gui import strings  # noqa: E402
from harness_design_studio.gui.main_window import MainWindow  # noqa: E402
from harness_design_studio.gui.theme import ThemeManager  # noqa: E402
from tests.ux_rel import flatsat_controller, release_all  # noqa: E402


def window(qtbot, tmp_path: Path, *, workspace: str | None = None, name: str = "ui.ini"):
    settings = QSettings(str(tmp_path / name), QSettings.Format.IniFormat)
    if workspace is not None:
        settings.setValue("ui/workspace", workspace)
        settings.sync()
    w = MainWindow(settings, ThemeManager(), first_run=False)
    w.ask_choice = lambda t, x, b: 1  # type: ignore[assignment]
    qtbot.addWidget(w)
    w.resize(1440, 900)
    w.show()
    QApplication.processEvents()
    return w


def load_flatsat(w: MainWindow, tmp_path: Path) -> None:
    folder = tmp_path / "flatsat"
    templates.create_project(folder, "flatsat")
    w.ctl._install(load_project(folder).project, None, None)
    w.set_area("model")
    w.view.fit()
    QApplication.processEvents()
    w.ctl.run_drc_now()
    w.view.dscene.refresh_states()
    w._update_hash()
    QApplication.processEvents()


@pytest.fixture
def win(qtbot, tmp_path: Path):
    w = window(qtbot, tmp_path)
    load_flatsat(w, tmp_path)
    return w


def marks(w: MainWindow) -> int:
    """How many objects the diagram marks with a problem, warning, pending or unchecked badge."""
    s = w.view.dscene.states
    return sum(1 for k in s.keys() if s.of(*k).badges())  # noqa: SIM118 (an index, not a dict)


def stale(w: MainWindow) -> None:
    assert w.ctl.update_unit("OBC1", name="Main computer")
    w._update_hash()


# ---- the action, its place and its defaults ---------------------------------------------------


def test_the_action_is_checkable_named_and_in_the_view_menu(win) -> None:
    act = win.act_problem_notices
    assert act.isCheckable() and act.objectName() == "act-problem-notices"
    assert act.text() == strings.A_PROBLEM_NOTICES == "Show problem notices"
    for hidden in ("Problems button", "inspector tab", "top bar", "diagram", "out-of-date banner"):
        assert hidden in act.toolTip()
    view_menu = next(m for m in win.menuBar().findChildren(type(win.menu_add)) if m.title() == strings.M_VIEW)  # fmt: skip
    entries = [a.text() for a in view_menu.actions() if a.text()]
    assert entries.index(strings.A_PROBLEM_NOTICES) <= 5  # near the top of the menu
    assert win.problem_notices_on() is True


def test_full_starts_with_the_notices_on_and_simple_with_them_off(qtbot, tmp_path) -> None:
    full = window(qtbot, tmp_path, workspace="full", name="full.ini")
    assert full.problem_notices_on() and full.problems_btn.isVisibleTo(full)
    simple = window(qtbot, tmp_path, workspace="simple", name="simple.ini")
    assert not simple.problem_notices_on()
    assert not simple.act_problem_notices.isChecked()
    assert not simple.problems_btn.isVisibleTo(simple)
    assert not simple.topbar.chip.isVisibleTo(simple)
    assert not simple.pending_link.isVisibleTo(simple)


def test_each_workspace_keeps_its_own_choice_under_its_own_key(qtbot, tmp_path) -> None:
    w = window(qtbot, tmp_path, workspace="full")
    w.act_problem_notices.trigger()  # Full: off
    assert w.settings.value("ui/problem_notices", None, bool) is False
    w.set_workspace("simple")
    assert not w.problem_notices_on()  # (Simple has its own default, off)
    w.act_problem_notices.trigger()  # Simple: on
    assert w.settings.value("ui/simple/problem_notices", None, bool) is True
    assert w.problems_btn.isVisibleTo(w)
    w.set_workspace("full")
    assert not w.problem_notices_on() and not w.problems_btn.isVisibleTo(w)
    w.set_workspace("simple")
    assert w.problem_notices_on() and w.problems_btn.isVisibleTo(w)


def test_a_second_window_on_the_same_settings_file_restores_it(qtbot, tmp_path) -> None:
    a = window(qtbot, tmp_path, workspace="full")
    a.act_problem_notices.trigger()
    a.settings.sync()
    b = window(qtbot, tmp_path, workspace="full")
    assert not b.problem_notices_on() and not b.problems_btn.isVisibleTo(b)
    assert not b.settings_page.notices_box.isChecked()
    b.act_problem_notices.trigger()
    b.settings.sync()
    c = window(qtbot, tmp_path, workspace="full")
    assert c.problem_notices_on() and c.problems_btn.isVisibleTo(c)


def test_the_settings_page_has_the_control_and_both_ways_follow_each_other(win) -> None:
    box = win.settings_page.notices_box
    assert isinstance(box, QCheckBox) and box.objectName() == "settings-problem-notices"
    assert box.text() == strings.SETTINGS_PROBLEM_NOTICES and box.toolTip() and box.accessibleName()  # fmt: skip
    assert box.isChecked()
    box.click()
    assert not win.problem_notices_on() and not box.isChecked()
    win.act_problem_notices.trigger()
    assert win.problem_notices_on() and box.isChecked()
    win.set_area("settings")
    win.settings_page.show_section("editing")
    assert box.isVisibleTo(win.settings_page)


# ---- what it hides ----------------------------------------------------------------------------


def test_the_status_bar_button_and_the_count_go_and_come_back(win) -> None:
    assert win.problems_btn.isVisibleTo(win) and "(" in win.problems_btn.text()
    win.act_problem_notices.trigger()
    assert not win.problems_btn.isVisibleTo(win)
    win.act_problem_notices.trigger()
    assert win.problems_btn.isVisibleTo(win)


def test_the_inspector_tab_loses_its_count(win) -> None:
    tabs = win.inspector.tabs
    assert "(" in tabs.tabText(2)  # "Problems (n)": the flatsat has findings
    win.act_problem_notices.trigger()
    assert tabs.tabText(2) == strings.INS_TAB_PROBLEMS
    win.ctl.run_drc_now()  # a new result does not bring it back
    assert tabs.tabText(2) == strings.INS_TAB_PROBLEMS
    win.act_problem_notices.trigger()
    assert "(" in tabs.tabText(2)


def test_the_top_bar_chip_goes_and_the_steps_stay(win) -> None:
    assert win.topbar.chip.isVisibleTo(win)
    win.act_problem_notices.trigger()
    assert not win.topbar.chip.isVisibleTo(win)
    assert all(b.isVisibleTo(win) for b in win.topbar.steps_buttons)
    assert win.topbar.check_btn.isVisibleTo(win) and win.topbar.check_btn.isEnabled()
    stale(win)  # (a change does not bring it back)
    assert not win.topbar.chip.isVisibleTo(win)
    win.act_problem_notices.trigger()
    assert win.topbar.chip.isVisibleTo(win)


def test_the_corner_chip_of_the_diagram_goes(win) -> None:
    win.view.status.refresh()
    assert win.view.status.isVisibleTo(win.view) and win.view.status.states()
    win.act_problem_notices.trigger()
    assert not win.view.status.isVisibleTo(win.view)
    win.view.status.refresh()  # (the timer reads it again after a change)
    assert not win.view.status.isVisibleTo(win.view)
    win.act_problem_notices.trigger()
    assert win.view.status.isVisibleTo(win.view)


def test_badges_on_cards_and_links_go_and_come_back(win) -> None:
    scene = win.view.dscene
    assert marks(win) > 0
    unit = next(u for u in win.ctl.project.units if scene.states.of("unit", u).badges())
    link = next(
        (i for i in win.ctl.project.interfaces if scene.states.of("interface", i).badges()), None
    )
    assert link is not None
    win.act_problem_notices.trigger()
    assert marks(win) == 0
    assert scene.states.of("unit", unit).badges() == [] and scene.states.of("interface", link).badges() == []  # fmt: skip
    win.ctl.update_unit("OBC1", name="Another")  # a change and a new check: still quiet
    scene.refresh_states()
    win.ctl.run_drc_now()
    scene.refresh_states()
    assert marks(win) == 0
    win.act_problem_notices.trigger()
    assert marks(win) > 0 and scene.states.of("unit", unit).badges()


def test_the_lock_and_auto_marks_stay_when_the_notices_are_off(qtbot, tmp_path) -> None:
    ctl = flatsat_controller(tmp_path / "src")
    assert release_all(ctl, ["W001"]) == ["W001"]
    ctl.save()
    ctl.release()
    w = window(qtbot, tmp_path)
    assert ctl.root is not None
    w.ctl.open_path(ctl.root)
    w.ctl.run_drc_now()
    w.view.dscene.refresh_states()
    index = w.ctl.state_index()
    locked = [u for u in w.ctl.project.units if index.of("unit", u).locks]
    auto = [u for u in w.ctl.project.units if index.of("unit", u).auto]
    assert locked and auto
    w.act_problem_notices.trigger()
    shown = w.view.dscene.states
    assert all(shown.of("unit", u).locks == index.of("unit", u).locks for u in locked)
    assert all(shown.of("unit", u).auto == index.of("unit", u).auto for u in auto)
    assert all(shown.of("unit", u).problems == 0 for u in w.ctl.project.units)


def test_the_pending_values_link_goes(win) -> None:
    assert win.pending_link.text() and win.pending_link.isVisibleTo(win)
    win.act_problem_notices.trigger()
    assert not win.pending_link.isVisibleTo(win)
    win.act_problem_notices.trigger()
    assert win.pending_link.isVisibleTo(win)


def test_the_out_of_date_banner_goes_and_comes_back(win) -> None:
    stale(win)
    assert win.alerts.is_showing("stale")
    win.act_problem_notices.trigger()
    assert not win.alerts.is_showing("stale")
    stale_again = win.ctl.update_unit("OBC1", name="Main computer 2")
    assert stale_again
    win._update_hash()
    assert not win.alerts.is_showing("stale")
    win.act_problem_notices.trigger()
    assert win.alerts.is_showing("stale")


def test_switching_it_is_quick_and_repaints_only_what_changed(win) -> None:
    scene = win.view.dscene
    painted: list[object] = []
    for u, item in scene.unit_items.items():
        if scene.states.of("unit", u).clear:
            item.update = lambda _u=u: painted.append(_u)  # type: ignore[method-assign]
    started = time.perf_counter()
    win.act_problem_notices.trigger()
    QApplication.processEvents()
    win.act_problem_notices.trigger()
    QApplication.processEvents()
    assert (time.perf_counter() - started) < 1.0  # (two switches, with the offscreen repaints)
    assert painted == []  # an object with nothing to show is not touched
    t = time.perf_counter()
    win.act_problem_notices.trigger()
    assert (time.perf_counter() - t) * 1000 < 400


# ---- what it never hides ----------------------------------------------------------------------


def test_the_banners_that_explain_why_stay(win, tmp_path) -> None:
    win.act_problem_notices.trigger()
    win.ctl.project.read_only = True
    win._update_banner()
    assert win.banner.isVisibleTo(win) and strings.BANNER_READ_ONLY in win.banner.label.text()
    win.ctl.project.read_only = False
    win.ctl.project.quarantine_files = {"logical/units/x.json": b"{"}
    win._update_banner()
    assert win.banner.isVisibleTo(win) and win.banner.label.text() == strings.BANNER_RECOVERED
    win.ctl.project.quarantine_files = {}
    win.ctl.sample = True
    win._update_banner()
    assert win.banner.isVisibleTo(win) and win.banner.label.text() == strings.BANNER_SAMPLE


def test_the_lock_banner_and_failed_jobs_stay(qtbot, tmp_path) -> None:
    ctl = flatsat_controller(tmp_path / "src")
    assert release_all(ctl, ["W001"]) == ["W001"]
    ctl.save()
    ctl.release()
    w = window(qtbot, tmp_path)
    assert ctl.root is not None
    w.ctl.open_path(ctl.root)
    w.act_problem_notices.trigger()
    w.set_area("revisions")
    assert w.releases_panel.select_harness("W001")
    QApplication.processEvents()
    assert w.alerts.is_showing("locked")
    w._job_failed("Generate did not finish")
    assert w.alerts.is_showing("job")


def test_check_checks_and_the_problems_panel_still_work(win, qtbot) -> None:
    win.act_problem_notices.trigger()
    assert win.topbar.check_btn.isEnabled() and win.act_check.isEnabled()
    win.act_check.trigger()
    qtbot.waitUntil(lambda: not win.ctl.drc_busy(), timeout=20000)
    assert win.toasts.messages[-1].startswith(strings.CHECK_FINISHED.split("{")[0])
    win.go_to("checks")
    assert win.checks_panel.isVisibleTo(win)
    assert not win.dock_problems.isVisibleTo(win)
    win.act_problems.trigger()  # View > Problems panel (Ctrl+Shift+M)
    assert win.dock_problems.isVisibleTo(win) and win.problems_list.count.text()


def test_the_next_step_page_and_dialog_errors_ignore_the_switch(win) -> None:
    win.act_problem_notices.trigger()
    win.set_area("next")
    assert win.next_page.isVisibleTo(win) and win.next_page.title.text()
    from harness_design_studio.gui.devices_dialogs import NewDeviceDialog

    dlg = NewDeviceDialog(win, win.theme, win.ctl.project)
    dlg.show()
    dlg.name.setText("x")
    dlg.device_id.setText("")
    assert dlg.notice.isVisibleTo(dlg) and "needs an ID" in dlg.notice.text()


def test_the_checks_area_keeps_its_rows(win) -> None:
    win.act_problem_notices.trigger()
    win.go_to("checks")
    assert win.checks_panel.isVisibleTo(win)
    assert win.checks_panel.table.model().rowCount() > 0
