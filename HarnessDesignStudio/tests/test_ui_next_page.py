# mypy: disable-error-code="no-untyped-def,no-untyped-call"
"""1.8.0 S1 (D-171): the Next step page and the Simple / Full setting."""

import pytest

pytest.importorskip("PySide6")
pytestmark = pytest.mark.gui

from PySide6.QtCore import QSettings, Qt  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from harness_design_studio.gui import areas, next_step, strings  # noqa: E402
from harness_design_studio.gui.main_window import MainWindow  # noqa: E402
from harness_design_studio.gui.next_page import NextStepPage  # noqa: E402
from harness_design_studio.gui.next_step import Next, NextInputs  # noqa: E402
from harness_design_studio.gui.next_step import next_step as step_for  # noqa: E402
from harness_design_studio.gui.theme import ThemeManager  # noqa: E402
from tests.ux_rel import app, themed  # noqa: E402

# ---- the page alone ----------------------------------------------------------------------------
RELEASABLE = NextInputs(
    units=3, interfaces=2, harnesses=2, generation="current", checked=True, outputs="current"
)
CASES = {
    "add_device": NextInputs(),
    "connect": NextInputs(units=2),
    "generate": NextInputs(units=2, interfaces=1),
    "check": NextInputs(units=2, interfaces=1, harnesses=1, generation="current"),
    "fix": NextInputs(
        units=2, interfaces=1, harnesses=1, generation="current", checked=True, failed=2
    ),
    "build_sheets": NextInputs(
        units=2, interfaces=1, harnesses=1, generation="current", checked=True
    ),
    "release": RELEASABLE,
    "done": NextInputs(
        units=3, interfaces=2, harnesses=2, generation="current", checked=True,
        outputs="current", released=2,
    ),
}  # fmt: skip


@pytest.fixture
def page(qtbot):
    app()
    calls: list[str] = []
    actions = {k: (lambda k=k: calls.append(k)) for k in (*CASES, "new_harness", "show_everything")}
    p = NextStepPage(themed(), actions=actions)
    p.calls = calls  # type: ignore[attr-defined]
    qtbot.addWidget(p)
    p.resize(900, 700)
    p.show()
    return p


@pytest.mark.parametrize("key", list(CASES))
def test_the_one_button_calls_the_flow_of_its_step(page, key) -> None:
    n = step_for(CASES[key])
    assert n.key == key
    page.show_next(n)
    assert page.title.text() == n.title and page.why.text() == n.why
    assert page.button.text() == n.button and page.button.isVisibleTo(page)
    assert page.button.property("primary") is True
    page.button.click()
    assert page.calls == [key]


def test_the_alternative_link_calls_new_harness_and_only_the_first_step_has_it(page) -> None:
    page.show_next(step_for(CASES["add_device"]))
    assert page.alternative_row.isVisibleTo(page)
    assert page.alternative_label.text() == "or make a harness by hand"
    assert page.alternative_button.text() == "New harness…"
    page.alternative_button.click()
    assert page.calls == ["new_harness"]
    page.show_next(step_for(CASES["connect"]))
    assert not page.alternative_row.isVisibleTo(page)


def test_busy_and_read_only_show_no_button(page) -> None:
    page.show_next(step_for(NextInputs(running="generate")))
    assert page.title.text() == "Working…" and not page.button.isVisibleTo(page)
    page.show_next(step_for(NextInputs(units=3, read_only=True)))
    assert not page.button.isVisibleTo(page) and "newer version" in page.why.text()
    words = [r.word.text() for r in page.rows]
    assert strings.NEXT_STATE_BLOCKED in words


def test_the_note_shows_only_when_there_is_one(page) -> None:
    page.show_next(step_for(CASES["build_sheets"]))
    assert not page.note.isVisibleTo(page)
    page.show_next(step_for(NextInputs(**{**CASES["build_sheets"].__dict__, "unchecked": 3})))
    assert page.note.isVisibleTo(page) and "engineering values" in page.note.text()


def test_the_six_steps_have_an_icon_and_a_word_each(page) -> None:
    page.show_next(step_for(CASES["generate"]))
    assert len(page.rows) == 6
    words = [r.word.text() for r in page.rows]
    assert words == ["done", "done", "next", "to do", "to do", "to do"]
    for r in page.rows:
        pm = r.icon_label.pixmap()
        assert pm is not None and not pm.isNull()
        assert r.accessibleName().endswith(r.word.text())
    assert page.rows[2].label.text() == "Generate the harnesses"


def test_showing_the_same_result_again_changes_nothing(page) -> None:
    n = step_for(CASES["check"])
    page.show_next(n)
    page.show_next(Next(**n.__dict__))
    assert page.shown() == n


def test_every_control_is_named_and_has_a_tooltip(page) -> None:
    for key in (*CASES, "busy", "read_only"):
        base = CASES.get(key, NextInputs(running="x") if key == "busy" else NextInputs(read_only=True))  # fmt: skip
        page.show_next(step_for(base))
        for b in (page.button, page.alternative_button, page.everything):
            if b.isVisibleTo(page):
                assert b.accessibleName().strip() and b.toolTip().strip(), (key, b.objectName())
    assert page.accessibleName() == strings.NEXT_TITLE
    assert page.title.objectName() == "next-title" and page.why.objectName() == "next-why"
    assert page.button.objectName() == "next-button"


def test_the_link_to_everything_is_for_the_simple_workspace(page) -> None:
    page.set_workspace("simple")
    assert page.everything.isVisibleTo(page) and page.everything.text() == "Show everything"
    page.everything.click()
    assert page.calls == ["show_everything"]
    page.set_workspace("full")
    assert not page.everything.isVisibleTo(page)


# ---- the window --------------------------------------------------------------------------------
def make(qtbot, tmp_path, name: str = "ui.ini") -> MainWindow:
    w = MainWindow(
        QSettings(str(tmp_path / name), QSettings.Format.IniFormat),
        ThemeManager(),
        first_run=False,
    )
    w.ask_choice = lambda t, x, b: 1  # type: ignore[assignment]
    qtbot.addWidget(w)
    w.resize(1440, 900)
    w.show()
    QApplication.processEvents()
    return w


@pytest.fixture
def first_run_default(monkeypatch):
    """The real default of a settings file with no values (conftest gives the other tests Full)."""
    monkeypatch.setattr(next_step, "FIRST_RUN_WORKSPACE", "simple")


def test_the_next_step_is_the_first_area_of_the_rail_and_a_page_of_its_own() -> None:
    assert areas.KEYS[0] == "next" and "next" in areas.PAGES
    a = areas.area("next")
    assert a.title == "Next step" and a.tabs == () and a.icon == "nav-next" and a.tip


def test_a_new_settings_file_starts_in_the_simple_workspace(qtbot, tmp_path, first_run_default):
    w = make(qtbot, tmp_path)
    assert w.workspace == "simple"
    assert w.area() == "next" and w.rail.current() == "next"
    assert w.area_stack.currentWidget() is w.next_page
    assert w.act_simple.isChecked() and not w.act_full.isChecked()
    assert w.settings.value("ui/workspace") == "simple"  # stored at once
    assert w.next_page.everything.isVisibleTo(w.next_page)
    assert w.settings_page.workspace_combo.currentData() == "simple"


def test_a_settings_file_with_values_starts_in_the_full_workspace(
    qtbot, tmp_path, first_run_default
):
    s = QSettings(str(tmp_path / "ui.ini"), QSettings.Format.IniFormat)
    s.setValue("ui/theme", "dark")  # somebody who used the editor before
    s.sync()
    w = make(qtbot, tmp_path)
    assert w.workspace == "full"
    assert w.area() == "model" and w.rail.current() == "model"
    assert w.act_full.isChecked() and w.settings.value("ui/workspace") == "full"
    assert not w.next_page.everything.isVisibleTo(w.next_page)
    # the Next step page is still there, through the rail
    w.rail.buttons["next"].click()
    assert w.area() == "next" and w.area_stack.currentWidget() is w.next_page


def test_the_choice_is_kept_by_the_second_window(qtbot, tmp_path, first_run_default):
    first = make(qtbot, tmp_path)
    assert first.workspace == "simple"
    first.act_full.trigger()  # View > Full
    assert first.workspace == "full" and first.settings.value("ui/workspace") == "full"
    assert first.settings_page.workspace_combo.currentData() == "full"
    first.settings.sync()
    second = make(qtbot, tmp_path)
    assert second.workspace == "full" and second.act_full.isChecked()
    assert second.area() == "model"
    second.act_simple.trigger()
    second.settings.sync()
    third = make(qtbot, tmp_path)
    assert third.workspace == "simple" and third.area() == "next"
    assert third.act_simple.isChecked() and not third.act_full.isChecked()


def test_the_settings_page_and_the_menu_are_two_views_of_one_setting(qtbot, tmp_path):
    w = make(qtbot, tmp_path)
    combo = w.settings_page.workspace_combo
    assert combo.accessibleName() == "Workspace" and combo.toolTip()
    combo.setCurrentIndex(combo.findData("simple"))
    combo.activated.emit(combo.currentIndex())
    assert w.workspace == "simple" and w.act_simple.isChecked()
    assert w.settings.value("ui/workspace") == "simple"
    w.act_full.trigger()
    assert combo.currentData() == "full"
    # the two actions come first in the View menu
    view = next(m for m in w.menuBar().findChildren(type(w.menu_add)) if m.title() == strings.M_VIEW)  # fmt: skip
    first = [a for a in view.actions() if not a.isSeparator()][:2]
    assert [a.objectName() for a in first] == ["act-workspace-simple", "act-workspace-full"]
    assert all(a.isCheckable() and a.toolTip() for a in first)


def test_a_hand_edited_value_falls_back(qtbot, tmp_path):
    s = QSettings(str(tmp_path / "ui.ini"), QSettings.Format.IniFormat)
    s.setValue("ui/workspace", "pink")
    s.sync()
    w = make(qtbot, tmp_path)
    assert w.workspace in ("simple", "full")
    assert w.settings.value("ui/workspace") == w.workspace


def test_the_simple_workspace_opens_a_project_on_the_next_step(qtbot, tmp_path, first_run_default):
    from tests.ux_rel import flatsat_controller

    ctl = flatsat_controller(tmp_path)
    root = ctl.root
    ctl.release()
    w = make(qtbot, tmp_path)
    w.set_area("model")
    assert root is not None and w.open_project(root)
    assert w.area() == "next" and w.next_page.isVisibleTo(w)
    w.act_full.trigger()
    w.set_area("checks")
    assert w.area() == "checks"  # switching the workspace does not move the person


def test_the_full_workspace_opens_a_project_where_it_does_today(qtbot, tmp_path):
    from tests.ux_rel import flatsat_controller

    ctl = flatsat_controller(tmp_path)
    root = ctl.root
    ctl.release()
    w = make(qtbot, tmp_path)
    assert w.workspace == "full"
    w.set_area("checks")
    assert root is not None and w.open_project(root)
    assert w.area() != "next"


def test_show_everything_switches_to_the_diagram(qtbot, tmp_path, first_run_default):
    w = make(qtbot, tmp_path)
    assert w.area() == "next"
    w.next_page.everything.click()
    assert w.workspace == "full" and w.area() == "model"
    assert w.settings.value("ui/workspace") == "full"
    assert w.act_full.isChecked() and w.settings_page.workspace_combo.currentData() == "full"


def test_the_first_run_tour_still_runs_over_the_next_step_page(qtbot, tmp_path, first_run_default):
    w = MainWindow(
        QSettings(str(tmp_path / "ui.ini"), QSettings.Format.IniFormat),
        ThemeManager(),
        first_run=True,
    )
    qtbot.addWidget(w)
    w.resize(1440, 900)
    w.show()
    qtbot.waitUntil(lambda: w.tour.active, timeout=3000)
    assert w.area() == "next"
    assert w.tour.card.isVisible()
    # the steps that point at the diagram are skipped while it is hidden; the others are shown
    shown = w.tour._shown_steps()
    assert shown and w.tour.index in shown
    w.tour.stop()
    assert w.settings.value("tour/done", False, bool) is True


# ---- the page follows the project --------------------------------------------------------------
def test_the_page_follows_the_project(qtbot, tmp_path, first_run_default, monkeypatch):
    w = make(qtbot, tmp_path)
    calls: list[str] = []
    w.ctl.new_project(tmp_path / "blank", "Blank")
    QApplication.processEvents()
    w._open_in_workspace()
    page = w.next_page
    assert page.key() == "add_device" and page.button.text() == "Add a device"
    assert page.alternative_row.isVisibleTo(page)
    # the button runs the real flow: a device appears, and the next step is to connect
    page.button.click()
    QApplication.processEvents()
    assert len(w.ctl.project.units) == 1
    assert page.key() == "connect" and page.button.text() == "Connect two devices"
    assert page.rows[0].word.text() == "done" and page.rows[1].word.text() == "next"
    # a second device is not yet a connection
    w.set_area("next")
    assert w.ctl.add_device() is not None
    QApplication.processEvents()
    assert page.key() == "connect"
    # the Connect button opens the diagram with the Connect tool
    page.button.click()
    assert w.ctl.tool == "connect"
    assert w.main_tabs.names()[w.main_tabs.currentIndex()] == "diagram"
    w.ctl.end_connect()
    # a connection: the next step is to generate
    a, b = w.ctl.add_unit("computer"), w.ctl.add_unit("power")
    assert a and b and w.ctl.add_interface_between("power_primary", b, a)
    QApplication.processEvents()
    assert page.key() == "generate"
    monkeypatch.setattr(w, "generate_flow", lambda: calls.append("generate"))
    w.set_area("next")
    page.button.click()
    assert calls == ["generate"]


def test_a_harness_by_hand_goes_straight_to_the_check(qtbot, tmp_path, first_run_default):
    w = make(qtbot, tmp_path)
    w.ctl.new_project(tmp_path / "blank", "Blank")
    QApplication.processEvents()
    w.set_area("next")
    w.ask_text = lambda title, label, default: "Hand harness"  # type: ignore[assignment]
    w.next_page.alternative_button.click()
    QApplication.processEvents()
    assert len(w.ctl.project.harnesses) == 1
    w.set_area("next")
    assert w.next_page.key() == "check"
    assert [r.word.text() for r in w.next_page.rows][:3] == ["done", "done", "done"]


def test_each_key_reaches_an_existing_flow_of_the_window(qtbot, tmp_path, monkeypatch):
    w = make(qtbot, tmp_path)
    seen: list[str] = []
    for name in (
        "add_device_flow", "new_harness_flow", "generate_flow", "check_flow", "export_dialog_flow",
    ):  # fmt: skip
        monkeypatch.setattr(w, name, lambda n=name: seen.append(n))
    monkeypatch.setattr(w, "go_to", lambda n: seen.append(f"go_to:{n}"))
    for key in (
        "add_device",
        "new_harness",
        "generate",
        "check",
        "build_sheets",
        "release",
        "done",
    ):
        w.next_page._call(key)
    assert seen == [
        "add_device_flow",
        "new_harness_flow",
        "generate_flow",
        "check_flow",
        "export_dialog_flow",
        "go_to:releases",
        "go_to:lists",
    ]
    seen.clear()
    monkeypatch.undo()
    w.next_page._call("fix")
    assert w.main_tabs.names()[w.main_tabs.currentIndex()] == "checks"
    assert w.checks_panel.result_filter() == "fail"


def test_a_read_only_project_offers_no_button(qtbot, tmp_path, first_run_default):
    from tests.ux_rel import flatsat_controller

    ctl = flatsat_controller(tmp_path)
    root = ctl.root
    # the folder stays locked by `ctl`, so the window opens it read-only
    w = make(qtbot, tmp_path)
    w.ask_choice = lambda t, x, b: 0  # type: ignore[assignment]  # "Open read-only"
    assert root is not None and w.open_project(root)
    assert w.ctl.read_only
    QApplication.processEvents()
    page = w.next_page
    assert page.key() == "read_only"
    assert not page.button.isVisibleTo(page) and "newer version" in page.why.text()
    assert not page.alternative_row.isVisibleTo(page)
    ctl.release()


def test_the_page_follows_a_running_job(qtbot, tmp_path, first_run_default):
    w = make(qtbot, tmp_path)
    w.busy = "generate"
    w._show_status(path=False)
    assert w.next_page.key() == "busy" and w.next_page.title.text() == "Working…"
    assert not w.next_page.button.isVisibleTo(w.next_page)
    w.busy = None
    w._show_status(path=False)
    assert w.next_page.key() != "busy" and w.next_page.button.isVisibleTo(w.next_page)


def test_the_rail_button_of_the_next_step_is_named_and_has_a_tooltip(qtbot, tmp_path):
    w = make(qtbot, tmp_path)
    b = w.rail.buttons["next"]
    assert b.accessibleName() == "Next step" and b.toolTip()
    assert list(w.rail.buttons)[0] == "next"
    assert b.focusPolicy() & Qt.FocusPolicy.TabFocus
