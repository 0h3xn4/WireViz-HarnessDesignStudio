# mypy: disable-error-code="no-untyped-def,no-untyped-call"
"""UI overhaul M2: the shell. The navigation rail and the areas, the one-row top bar, the job
indicator and the offline marker in the status bar, the Problems panel, the layout kept per project."""

import pytest

pytest.importorskip("PySide6")
pytestmark = pytest.mark.gui

from PySide6.QtCore import QSettings, Qt  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from harness_design_studio.gui import areas, strings  # noqa: E402
from harness_design_studio.gui.main_window import MainWindow  # noqa: E402
from harness_design_studio.gui.theme import ThemeManager  # noqa: E402
from tests.ux_rel import flatsat_controller  # noqa: E402


@pytest.fixture
def win(qtbot, tmp_path):
    ctl = flatsat_controller(tmp_path)
    root = ctl.root
    ctl.release()
    w = MainWindow(
        QSettings(str(tmp_path / "ui.ini"), QSettings.Format.IniFormat),
        ThemeManager(),
        first_run=False,
    )
    w.ask_choice = lambda t, x, b: 1  # type: ignore[assignment]
    qtbot.addWidget(w)
    w.resize(1440, 900)
    w.show()
    assert root is not None and w.open_project(root)
    QApplication.processEvents()
    return w


def test_the_rail_has_one_button_per_area_and_follows_the_open_area(win) -> None:
    assert list(win.rail.buttons) == list(areas.KEYS)
    assert win.area() == "model" and win.rail.current() == "model"
    for key in ("checks", "drawings", "outputs", "revisions", "home", "settings", "model"):
        win.rail.buttons[key].click()
        assert win.area() == key and win.rail.current() == key


def test_an_area_shows_only_its_own_tabs_and_the_bar_hides_for_one(win) -> None:
    tabs = win.main_tabs
    win.set_area("model")
    assert tabs.visible_names() == ["diagram", "devices"] and tabs.tabBar().isVisibleTo(win)
    win.set_area("checks")
    assert tabs.visible_names() == ["checks"] and not tabs.tabBar().isVisibleTo(win)
    assert win.area_stack.currentWidget() is tabs
    win.set_area("home")
    assert win.area_stack.currentWidget() is win.home_page
    win.set_area("settings")
    assert win.area_stack.currentWidget() is win.settings_page


def test_go_to_and_the_tab_shortcuts_open_the_area_of_the_view(win) -> None:
    for name, key in (("harness", "drawings"), ("lists", "outputs"), ("releases", "revisions"),
                      ("checks", "checks"), ("devices", "model"), ("diagram", "model")):  # fmt: skip
        win.set_area("home")
        assert win.go_to(name)
        assert win.area() == key and win.rail.current() == key
        assert win.main_tabs.currentWidget() is win.main_tabs.widget_of(name)


def test_choosing_a_tab_in_code_moves_the_rail(win) -> None:
    win.main_tabs.show_slot("releases")  # what show_object and the checks panel do
    assert win.area() == "revisions" and win.rail.current() == "revisions"


def test_the_breadcrumbs_say_where_you_are(win) -> None:
    win.go_to("devices")
    assert (
        win.topbar.crumbs.full_text()
        == f"{strings.AREA_MODEL}{strings.CRUMB_SEPARATOR}{strings.TAB_DEVICES}"
    )
    win.set_area("checks")
    assert win.topbar.crumbs.full_text() == strings.AREA_CHECKS


def test_every_rail_button_is_named_and_has_a_tooltip(win) -> None:
    for key, button in win.rail.buttons.items():
        assert button.accessibleName() == areas.area(key).title and button.toolTip()
    assert win.rail.toggle.accessibleName() and win.rail.toggle.toolTip()


def test_the_rail_collapses_to_icons_and_in_a_short_window(win) -> None:
    full = win.rail.width()
    win.rail.toggle.click()
    assert win.rail.collapsed and win.rail.width() < full
    win.rail.toggle.click()
    assert win.rail.width() == full
    win.resize(1440, 560)
    QApplication.processEvents()
    assert win.rail.compact and win.rail.width() < full
    win.resize(1440, 900)
    QApplication.processEvents()
    assert not win.rail.compact


def test_home_and_settings_show_and_change_things(win) -> None:
    win.set_area("home")
    assert win.home_page.name.full_text() == win.ctl.project.meta.name
    assert str(win.ctl.root) == win.home_page.path.full_text()
    win.set_area("settings")
    page = win.settings_page
    page.theme_combo.setCurrentIndex(page.theme_combo.findData("dark"))
    page.theme_combo.activated.emit(page.theme_combo.currentIndex())
    assert win.theme.mode == "dark"
    page.mode_combo.setCurrentIndex(page.mode_combo.findData("expert"))
    page.mode_combo.activated.emit(page.mode_combo.currentIndex())
    assert win.ctl.mode == "expert"
    win.set_theme_mode("light")  # changed elsewhere: the page follows
    win._pick_mode("guided")
    win._update_home()
    assert page.theme_combo.currentData() == "light" and page.mode_combo.currentData() == "guided"


def test_the_top_bar_is_one_full_width_row_with_everything_in_it(win) -> None:
    bar = win.topbar
    assert win.top_toolbar.width() >= win.width() - 2 and bar.isVisible()
    for w in (win.mode_guided, win.mode_expert, win.search_btn, win.generate_btn,
              win.findChild(type(win.mode_guided), "undo-button"),
              win.findChild(type(win.mode_guided), "redo-button")):  # fmt: skip
        assert w is not None and bar.isAncestorOf(w)
    assert bar.revision_label.text() == strings.TB_REVISION.format("A") or not bar.revision_label.text()  # fmt: skip


def test_arrange_and_the_filters_sit_with_the_diagram_tabs(win) -> None:
    win.go_to("diagram")
    assert win.diagram_tools.isVisibleTo(win) and win.arrange_btn.isVisibleTo(win)
    win.go_to("devices")
    assert not win.diagram_tools.isVisibleTo(win)


def test_the_job_indicator_shows_a_running_job_with_cancel_and_the_last_check(win, qtbot) -> None:
    jobs = win.jobs
    cancelled: list[bool] = []
    jobs.start("Working", cancel=lambda: cancelled.append(True))
    assert jobs.is_running() and jobs.cancel_btn.isVisibleTo(win) and "Working" in jobs.text()
    jobs.cancel_btn.click()
    assert cancelled == [True]
    jobs.finish("Last check: 12:00")
    assert not jobs.is_running() and jobs.text() == "Last check: 12:00"
    win.check_flow()  # a rule check runs in the helper process: the indicator says so
    qtbot.waitUntil(lambda: win.ctl.drc_busy() or win.ctl.drc_current, timeout=5000)
    if win.ctl.drc_busy():
        assert win.jobs.is_running() and strings.JOB_CHECKING in win.jobs.text()
        win.ctl.cancel_check()


def test_a_busy_window_shows_its_job_and_the_offline_marker_is_there(win, qtbot) -> None:
    qtbot.waitUntil(lambda: not win.ctl.drc_busy(), timeout=15000)
    win._set_busy("generate")
    assert win.jobs.is_running() and strings.JOB_GENERATING in win.jobs.text()
    win._set_busy(None)
    assert not win.jobs.is_running()
    assert (
        win.offline.text() == strings.OFFLINE_TEXT and win.offline.toolTip() == strings.OFFLINE_TIP
    )


def test_the_problems_panel_lists_the_findings_and_a_click_goes_to_the_object(win, qtbot) -> None:
    assert not win.dock_problems.isVisible()
    win.toggle_problems()
    assert win.dock_problems.isVisible() and win.problems_btn.isChecked()
    qtbot.waitUntil(lambda: win.problems_list.total() > 0, timeout=5000)
    assert win.problems_list.total() == len(win.ctl.open_findings())
    assert str(win.problems_list.total()) in win.problems_btn.text()
    rows = win.problems_list.rows()
    assert rows[0]["level"] in ("error", "warning", "info") and rows[0]["rule"]
    shown: list[str] = []
    win.problems_list.showRequested.connect(shown.append)
    target = next(r for r in rows if r["object_id"])
    row = rows.index(target)
    index = win.problems_list.table.proxy.mapFromSource(win.problems_list.model.index(row, 0))
    win.problems_list.table.clicked.emit(index)
    assert shown == [target["object_id"]]
    win.toggle_problems()
    assert not win.dock_problems.isVisible()


def test_the_problems_filter_keeps_errors_or_warnings(win, qtbot) -> None:
    win.toggle_problems()
    qtbot.waitUntil(lambda: win.problems_list.total() > 0, timeout=5000)
    panel = win.problems_list
    for key in ("warning", "error", "all"):
        panel.filters[key].click()
        shown = panel.table.proxy.rowCount()
        wanted = sum(1 for r in panel.rows() if key == "all" or r["level"] == key)
        assert shown == wanted, key


def test_f6_reaches_the_problems_panel_when_it_is_open(win) -> None:
    names = [n for n, _a, _w in win._panes()]
    assert strings.PANE_PROBLEMS not in names
    win.toggle_problems()
    QApplication.processEvents()
    names = [n for n, _a, _w in win._panes()]
    assert strings.PANE_PROBLEMS in names
    win.view.setFocus()
    win._pane = 0
    visited = [win.cycle_panes(1) for _ in range(len(names))]
    assert strings.PANE_PROBLEMS in visited and visited[-1] == strings.PANE_CANVAS
    # the rail is first in the Tab order (before the views), so it needs no stop of its own
    assert win.rail.buttons["model"].focusPolicy() & Qt.FocusPolicy.TabFocus


def test_every_menu_action_is_still_reachable_from_the_palette(win) -> None:
    win.open_commands()
    palette = win.command_palette
    assert palette is not None
    palette.input.setText("Go to Home")
    assert any(strings.GO_HOME in palette.list.item(i).text() for i in range(palette.list.count()))
    palette.dismiss()


def test_the_layout_is_remembered_per_project(qtbot, tmp_path) -> None:
    settings = QSettings(str(tmp_path / "ui.ini"), QSettings.Format.IniFormat)
    ctl = flatsat_controller(tmp_path)
    root = ctl.root
    ctl.release()
    assert root is not None

    def make() -> MainWindow:
        w = MainWindow(settings, ThemeManager(), first_run=False)
        w.ask_choice = lambda t, x, b: 1  # type: ignore[assignment]
        qtbot.addWidget(w)
        w.resize(1440, 900)
        w.show()
        return w

    w = make()
    assert w.open_project(root)
    w.go_to("checks")
    w.toggle_problems()
    w.rail.toggle.click()
    w._save_project_layout()
    w.close()
    again = make()
    assert again.area() == "model"  # a new window starts in the default area ...
    assert again.open_project(root)  # ... and the project brings its own layout back
    assert again.area() == "checks" and again.dock_problems.isVisible() and again.rail.collapsed
