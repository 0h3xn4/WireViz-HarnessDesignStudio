# mypy: disable-error-code="no-untyped-def,no-untyped-call,attr-defined,has-type,union-attr"
"""Quick mode: a view setting (`ui/quick`) on top of any role for a person who only wants a block
diagram quickly. It changes what the window shows, never a project file, the model hash or a written
output; every hidden thing stays in the menus and in Ctrl+K; turning it off gives back exactly the
layout of the role."""

from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("PySide6")
pytestmark = pytest.mark.gui

from PySide6.QtCore import QSettings  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from harness_design_studio.core.io.layout import model_hash  # noqa: E402
from harness_design_studio.core.samples import mini3  # noqa: E402
from harness_design_studio.gui import areas, roles, strings  # noqa: E402
from harness_design_studio.gui.main_window import MainWindow  # noqa: E402
from harness_design_studio.gui.states import STATE_ROLE  # noqa: E402
from harness_design_studio.gui.theme import ThemeManager  # noqa: E402
from harness_design_studio.gui.topbar import ShellStatus, TopBar  # noqa: E402


def make(qtbot, tmp_path: Path, *, first_run=False, width=1440, name="ui.ini", **values):
    s = QSettings(str(tmp_path / name), QSettings.Format.IniFormat)
    for key, value in values.items():
        s.setValue(key.replace("__", "/"), value)
    s.sync()
    w = MainWindow(s, ThemeManager(), first_run=first_run)
    w.ask_choice = lambda t, x, b: 1
    qtbot.addWidget(w)
    w.resize(width, 900)
    w.show()
    QApplication.processEvents()
    return w


def look(w: MainWindow) -> dict[str, Any]:
    """What the person sees, for comparing before and after."""
    t = w.topbar
    return {
        "rail": {k: b.isVisibleTo(w.rail) for k, b in w.rail.buttons.items()},
        "bar": {
            n: getattr(t, n).isVisibleTo(t)
            for n in ("generate_btn", "check_btn", "release_btn", "export_btn", "chip",
                      "hash_label", "revision_label", "export_diagram_btn")
        },
        "chevrons": [c.isVisibleTo(t) for c in t.chevrons],
        "modes": (w.mode_guided.isVisibleTo(w), w.mode_expert.isVisibleTo(w)),
        "quick": w.quick_btn.isVisibleTo(w),
        "notices": w.problem_notices_on(),
        "problems_btn": w.problems_btn.isVisibleTo(w),
        "area": w.area(),
    }  # fmt: skip


# ---- the pure rule ------------------------------------------------------------------------------
def test_quick_lists_the_model_home_and_settings_for_every_role() -> None:
    for role in roles.ROLES:
        assert set(areas.KEYS) - set(areas.hidden_in(role, True)) == {"home", "model", "settings"}
        assert areas.hidden_in(role) == areas.hidden_in(role, False)  # (off: the role as before)
    assert areas.hidden_in("systems") == ("home", "drawings", "outputs", "asbuilt")
    assert {"checks", "revisions", "drawings", "outputs", "next"} <= set(
        areas.hidden_in("electrical", True)
    )


# ---- the switch ---------------------------------------------------------------------------------
def test_it_is_off_by_default_and_found_in_the_role_menu_the_view_menu_settings_and_the_palette(
    qtbot, tmp_path
) -> None:
    w = make(qtbot, tmp_path, ui__role=roles.ELECTRICAL)
    assert not w.quick_on() and not w.settings.value("ui/quick", False, bool)
    actions = w.role_btn.menu().actions()
    assert actions[3].isSeparator() and actions[4] is w.act_quick
    assert w.act_quick.isCheckable() and w.act_quick.text() == strings.A_QUICK == "Quick mode"
    assert any(w.act_quick in a.menu().actions() for a in w.menuBar().actions() if a.menu())
    assert w.settings_page.quick_box.text() == strings.SETTINGS_QUICK
    assert strings.A_QUICK in [e.label for e in w.palette_entries()]
    assert not w.quick_btn.isVisibleTo(w)


@pytest.mark.parametrize("role", roles.ROLES)
def test_the_rail_keeps_the_model_home_and_settings_and_the_open_area(
    qtbot, tmp_path, role
) -> None:
    w = make(qtbot, tmp_path, ui__role=role)
    w.set_area("checks")
    w.act_quick.trigger()
    assert w.quick_on() and w.settings.value("ui/quick", False, bool)
    seen = look(w)["rail"]
    assert seen == {k: k in ("home", "model", "settings", "checks") for k in areas.KEYS}
    w.set_area("model")  # (the open area went: it was only listed while it was open)
    assert look(w)["rail"] == {k: k in areas.QUICK_LISTED for k in areas.KEYS}
    assert all(w.rail.buttons[k].isEnabled() for k in areas.KEYS)  # (hidden, not locked)


@pytest.mark.parametrize("role", roles.ROLES)
def test_the_top_bar_is_calm_and_shows_export_diagram(qtbot, tmp_path, role) -> None:
    w = make(qtbot, tmp_path, ui__role=role)
    w.act_quick.trigger()
    t = w.topbar
    bar = look(w)["bar"]
    assert bar["export_diagram_btn"] and not any(
        bar[n] for n in ("generate_btn", "check_btn", "release_btn", "export_btn", "chip")
    )
    assert not any(c.isVisibleTo(t) for c in t.chevrons)
    assert w.quick_btn.isVisibleTo(w) and w.role_btn.isVisibleTo(w)
    assert w.search_btn.isVisibleTo(w) and t.name_label.isVisibleTo(t)
    assert not w.mode_guided.isVisibleTo(w)
    assert t.export_diagram_btn.text() == strings.TB_EXPORT_DIAGRAM
    asked: list[str] = []

    def ask(title: str, name: str, flt: str) -> str | None:
        asked.append(name)
        return None

    w.ask_save_path = ask
    t.export_diagram_btn.click()
    assert len(asked) == 1  # it is Export diagram (File > Export diagram…)
    assert w.act_generate.shortcut().toString() == "Ctrl+G"  # (hidden, not removed)


@pytest.mark.parametrize("role", roles.ROLES)
def test_turning_it_off_gives_back_exactly_the_layout_of_the_role(qtbot, tmp_path, role) -> None:
    w = make(qtbot, tmp_path, ui__role=role)
    before = look(w)
    w.act_quick.trigger()
    assert look(w) != before
    w.act_quick.trigger()
    assert not w.quick_on() and look(w) == before
    assert w.settings.value("ui/quick", True, bool) is False


def test_problem_notices_are_forced_off_and_come_back(qtbot, tmp_path) -> None:
    w = make(qtbot, tmp_path, ui__role=roles.ELECTRICAL)
    assert w.problem_notices_on() and w.topbar.chip.isVisibleTo(w.topbar)
    w.act_quick.trigger()
    assert not w.problem_notices_on()
    assert not w.topbar.chip.isVisibleTo(w.topbar) and not w.problems_btn.isVisibleTo(w)
    assert not w.act_problem_notices.isEnabled() and not w.settings_page.notices_box.isEnabled()
    assert w.act_problem_notices.isChecked()  # (the person's own choice is kept)
    assert not w.view.dscene.problem_notices
    w.act_quick.trigger()
    assert w.problem_notices_on() and w.act_problem_notices.isEnabled()
    assert w.topbar.chip.isVisibleTo(w.topbar) and w.view.dscene.problem_notices


def test_the_automatic_check_progress_is_not_shown_in_quick_and_comes_back(
    qtbot, tmp_path, monkeypatch
) -> None:
    w = make(qtbot, tmp_path, ui__role=roles.ELECTRICAL)
    monkeypatch.setattr(w.ctl, "drc_busy", lambda: True)
    w._update_jobs()
    assert w.jobs.is_running() and strings.JOB_CHECKING in w.jobs.text()  # (without Quick mode)
    w.act_quick.trigger()
    assert not w.jobs.is_running()  # (turning Quick mode on hides it at once)
    w._on_check_state()  # (the check goes on in the background and says nothing)
    assert not w.jobs.is_running() and not w.jobs.cancel_btn.isVisibleTo(w)
    w._check_asked = True  # (a check the person asked for, Ctrl+K > Check, still shows)
    w._update_jobs()
    assert w.jobs.is_running() and strings.JOB_CHECKING in w.jobs.text()
    w._check_asked = False
    w._update_jobs()
    assert not w.jobs.is_running()
    w.act_quick.trigger()
    assert w.jobs.is_running() and strings.JOB_CHECKING in w.jobs.text()  # (back when left)


def test_the_pending_chips_of_the_tree_are_not_shown_in_quick_and_come_back(
    qtbot, tmp_path
) -> None:
    w = make(qtbot, tmp_path, ui__role=roles.ELECTRICAL)
    tree = w.project_tree
    before = tree.state_of("root", "config")
    assert before is not None and before[0] == "pending" and before[1].endswith("pending")
    names = [n for n in w.ctl.project.config if tree.state_of("config", n)]
    assert names
    w.act_quick.trigger()
    assert tree.state_of("root", "config") is None
    assert all(tree.state_of("config", n) is None for n in names)
    root = tree.model.roots["config"]
    assert tree.model.data(tree.model.index_of(root), STATE_ROLE) is None
    assert tree.view.itemDelegate().quiet and tree.model.quiet
    assert "pending" not in tree.model.accessible_text(tree.model.find("config", names[0]))
    w.act_quick.trigger()
    assert tree.state_of("root", "config") == before
    assert all(tree.state_of("config", n) for n in names)
    assert not tree.view.itemDelegate().quiet and not tree.model.quiet


def test_the_stale_plan_banner_is_not_shown_in_quick_and_comes_back(qtbot, tmp_path) -> None:
    w = make(qtbot, tmp_path, ui__role=roles.ELECTRICAL)
    stale = ShellStatus(generation="stale", outputs="stale", has_harnesses=True)
    w._update_alerts(stale)
    assert w.alerts.banner("stale") is not None  # (without Quick mode it shows)
    w.act_quick.trigger()
    w._update_alerts(stale)
    assert w.alerts.banner("stale") is None or w.alerts.banner("stale").isHidden()
    w.act_quick.trigger()
    w._update_alerts(stale)
    assert w.alerts.banner("stale") is not None and not w.alerts.banner("stale").isHidden()


def test_it_is_separate_from_the_role_and_its_layout_memory(qtbot, tmp_path) -> None:
    w = make(qtbot, tmp_path, ui__role=roles.ELECTRICAL)
    w.act_quick.trigger()
    w.set_role(roles.SYSTEMS)
    assert w.quick_on() and w.role == roles.SYSTEMS  # a role change keeps Quick mode
    w.set_role(roles.AIT)
    assert w.quick_on() and look(w)["rail"]["model"]  # (AIT leaves the Model out; Quick lists it)
    assert w.settings.value("ui/quick", False, bool) is True
    assert not any(k.endswith("/quick") and k != "ui/quick" for k in w.settings.allKeys())
    w.act_quick.trigger()
    w.set_role(roles.ELECTRICAL)
    assert look(w)["rail"] == {k: k not in areas.hidden_in("electrical") for k in areas.KEYS}


def test_it_is_remembered_across_a_restart_and_needs_no_restart(qtbot, tmp_path) -> None:
    w = make(qtbot, tmp_path, ui__role=roles.SYSTEMS)
    w.act_quick.trigger()
    w.settings.sync()
    w2 = make(qtbot, tmp_path, name="ui.ini")
    assert w2.quick_on() and w2.quick_btn.isVisibleTo(w2) and w2.topbar.export_diagram_btn.isVisibleTo(w2.topbar)  # fmt: skip
    assert w2.rail.buttons["checks"].isHidden()


def test_the_settings_checkbox_and_the_role_button_menu_switch_it(qtbot, tmp_path) -> None:
    w = make(qtbot, tmp_path, ui__role=roles.ELECTRICAL)
    w.settings_page.quick_box.click()
    assert w.quick_on() and w.act_quick.isChecked() and w.quick_btn.isVisibleTo(w)
    w.role_btn.menu().actions()[4].trigger()
    assert not w.quick_on() and not w.settings_page.quick_box.isChecked()
    w.quick_btn.setVisible(True)
    w.act_quick.setChecked(True)
    w.quick_btn.click()  # the indicator leaves Quick mode
    assert not w.quick_on()


def test_it_changes_nothing_in_the_project_or_its_hash(qtbot, tmp_path) -> None:
    w = make(qtbot, tmp_path, ui__role=roles.SYSTEMS)
    w.ctl._install(mini3(), None, None)
    h, token, dirty = model_hash(w.ctl.project), w.ctl.state_token, w.ctl.dirty
    w.act_quick.trigger()
    w.act_quick.trigger()
    assert (model_hash(w.ctl.project), w.ctl.state_token, w.ctl.dirty) == (h, token, dirty)
    assert not w.ctl.history.can_undo


def test_every_hidden_thing_is_still_reachable(qtbot, tmp_path) -> None:
    w = make(qtbot, tmp_path, ui__role=roles.SYSTEMS)
    w.act_quick.trigger()
    labels = [e.label for e in w.palette_entries()]
    for text in (strings.A_GENERATE, strings.A_CHECK, strings.A_EXPORT, strings.A_RELEASE):
        assert text in labels
    for key in ("checks", "outputs", "revisions", "next"):
        w.set_area(key)
        assert w.area() == key and w.rail.buttons[key].isVisibleTo(w.rail)  # listed while open
    assert w.go_to("checks")


# ---- the tour, the first-start question, the page a project opens on, the sample banner ---------
def test_no_tour_and_no_role_question_in_quick(qtbot, tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(roles, "FIRST_RUN_ROLE", None)
    asked: list[object] = []

    def run(dlg: object) -> int:
        asked.append(dlg)
        return 1

    w = make(qtbot, tmp_path, first_run=True, ui__quick=True)
    w.run_dialog = run
    QApplication.processEvents()
    qtbot.wait(400)
    assert asked == [] and not w.tour.active and w._role_to_ask is False
    assert w.role == roles.ELECTRICAL


def test_turning_it_on_ends_the_tour_for_good(qtbot, tmp_path) -> None:
    w = make(qtbot, tmp_path, ui__role=roles.ELECTRICAL)
    assert not w.settings.value("tour/done", False, bool)
    w.act_quick.trigger()
    assert w.settings.value("tour/done", False, bool)
    w.act_quick.trigger()  # (and it stays done after leaving Quick mode)
    assert w.settings.value("tour/done", False, bool)


@pytest.mark.parametrize("role", [roles.SYSTEMS, roles.AIT, roles.ELECTRICAL])
def test_a_project_opened_in_quick_lands_on_the_diagram(qtbot, tmp_path, role) -> None:
    w = make(qtbot, tmp_path, ui__role=role, ui__quick=True)
    assert w.area() == "model" and w.rail.current() == "model"
    w.set_area("home")
    w._open_for_role()
    assert w.area() == "model"
    w2 = make(qtbot, tmp_path, name="other.ini", ui__role=roles.SYSTEMS)
    assert w2.area() == "next"  # (without Quick the Systems role still starts on Next step)
    w2.act_quick.trigger()
    assert w2.area() == "model"  # (the page the person was on is not on the rail any more)


def test_the_sample_banner_stays_and_is_short_in_quick(qtbot, tmp_path) -> None:
    w = make(qtbot, tmp_path, ui__role=roles.SYSTEMS)
    assert w.ctl.sample and w.banner.isVisibleTo(w)
    assert w.banner.label.text() == strings.BANNER_SAMPLE
    w.act_quick.trigger()
    assert w.banner.isVisibleTo(w) and w.banner.label.text() == strings.BANNER_SAMPLE_QUICK
    assert len(strings.BANNER_SAMPLE_QUICK) < len(strings.BANNER_SAMPLE)
    assert w.banner.button.isVisibleTo(w.banner)  # (Save a copy stays)
    w.act_quick.trigger()
    assert w.banner.label.text() == strings.BANNER_SAMPLE


# ---- the top bar folds in Quick mode ------------------------------------------------------------
@pytest.mark.parametrize("width", [1440, 1000, 700])
def test_the_quick_top_bar_fits_at_every_width(qtbot, width) -> None:
    bar = TopBar(ThemeManager())
    qtbot.addWidget(bar)
    bar.apply(ShellStatus(name="Test rig", dirty=True, revision="A", model_hash="1a2b3c4d"))
    bar.resize(width, 40)
    bar.show()
    full = bar.level()
    bar.set_quick(True)
    QApplication.processEvents()
    assert bar.quick() and bar.level() <= full  # (a calmer bar never folds more)
    assert bar.export_diagram_btn.isVisibleTo(bar) and not bar.export_btn.isVisibleTo(bar)
    for w in (bar.generate_btn, bar.check_btn, bar.release_btn, bar.chip, *bar.chevrons):
        assert not w.isVisibleTo(bar)
    assert not bar.hash_label.isVisibleTo(bar) and not bar.revision_label.isVisibleTo(bar)
    assert bar.export_diagram_btn.geometry().right() <= bar.width()
    assert bar.lay.sizeHint().width() <= max(bar.width(), 1) + 160  # (the name may shrink)
    bar.set_quick(False)
    assert bar.generate_btn.isVisibleTo(bar) and bar.export_btn.isVisibleTo(bar)
    assert not bar.export_diagram_btn.isVisibleTo(bar)


def test_the_export_diagram_button_loses_its_word_before_it_is_cut(qtbot) -> None:
    bar = TopBar(ThemeManager())
    qtbot.addWidget(bar)
    bar.set_quick(True)
    bar.show()
    bar._set_level(3)  # the last fold: icons only (the tooltip and the accessible name stay)
    assert bar.export_diagram_btn.text() == "" and bar.export_diagram_btn.property("iconOnly")
    assert bar.export_diagram_btn.accessibleName() == strings.TB_EXPORT_DIAGRAM
    bar.resize(1440, 40)
    QApplication.processEvents()
    assert bar.level() == 0 and bar.export_diagram_btn.text() == strings.TB_EXPORT_DIAGRAM


def test_the_quick_bar_with_the_windows_widgets_folds_at_a_narrow_width(qtbot, tmp_path) -> None:
    w = make(qtbot, tmp_path, ui__role=roles.SYSTEMS, ui__quick=True, width=1000)
    t = w.topbar
    assert t.export_diagram_btn.isVisibleTo(t) and t.export_diagram_btn.geometry().right() <= t.width()  # fmt: skip
    w.resize(1440, 900)
    QApplication.processEvents()
    assert t.level() == 0 and t.export_diagram_btn.text() == strings.TB_EXPORT_DIAGRAM


def test_the_notices_switch_of_the_bar_does_not_bring_the_chip_back_in_quick(qtbot) -> None:
    bar = TopBar(ThemeManager())
    qtbot.addWidget(bar)
    bar.show()
    bar.set_quick(True)
    bar.set_notices(True)
    assert not bar.chip.isVisibleTo(bar)
    bar.set_quick(False)
    assert bar.chip.isVisibleTo(bar)
