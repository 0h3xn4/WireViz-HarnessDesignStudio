# mypy: disable-error-code="no-untyped-def,no-untyped-call"
"""UI overhaul M3: the workflow steps in the top bar, the lock banner on released data, Home with
recent projects and examples, and the empty state of a table."""

import shutil
from pathlib import Path

import pytest

pytest.importorskip("PySide6")
pytestmark = pytest.mark.gui

from PySide6.QtCore import QSettings  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from harness_design_studio.gui import recent, strings  # noqa: E402
from harness_design_studio.gui.empty_state import attach_empty_state  # noqa: E402
from harness_design_studio.gui.main_window import MainWindow  # noqa: E402
from harness_design_studio.gui.tables import Column, DictTableModel, TableView  # noqa: E402
from harness_design_studio.gui.theme import ThemeManager  # noqa: E402
from tests.ux_rel import flatsat_controller, release_all  # noqa: E402


def make_window(qtbot, tmp_path, *, release: bool, name: str = "flatsat") -> MainWindow:
    ctl = flatsat_controller(tmp_path)
    root = ctl.root
    ctl.release()
    w = MainWindow(
        QSettings(str(tmp_path / "ui.ini"), QSettings.Format.IniFormat),
        ThemeManager(),
        first_run=False,
    )
    w.ask_choice = lambda t, x, b: 1  # type: ignore[assignment]
    w.examples_folder = lambda: tmp_path / "examples"  # type: ignore[assignment]
    qtbot.addWidget(w)
    w.resize(1440, 900)
    w.show()
    assert root is not None and w.open_project(root)
    if release:
        assert release_all(w.ctl)
    QApplication.processEvents()
    return w


@pytest.fixture
def released(qtbot, tmp_path):
    return make_window(qtbot, tmp_path, release=True)


@pytest.fixture
def draft(qtbot, tmp_path):
    return make_window(qtbot, tmp_path, release=False)


def test_the_steps_are_in_the_topbar_and_say_what_is_next(draft) -> None:
    steps = draft.topbar.steps()
    assert [s.key for s in steps] == ["generate", "review", "release"]
    assert all(b.isVisibleTo(draft) for b in draft.topbar.steps_buttons)
    assert draft.topbar.release_btn.isVisibleTo(draft)


def test_released_steps_count_the_released_harnesses(released) -> None:
    steps = {s.key: s for s in released.topbar.steps()}
    assert "2 of 8" in steps["release"].detail  # W001 and W003 of eight
    button = released.topbar.steps_buttons[2]
    assert button.property("step") == steps["release"].state
    assert steps["release"].tooltip in button.toolTip()


def test_the_lock_banner_names_the_released_harness_wherever_it_is_edited(released) -> None:
    c = released.ctl
    released.set_area("revisions")
    assert released.releases_panel.select_harness("W001")
    QApplication.processEvents()
    assert released.alerts.is_showing("locked")
    banner = released.alerts.banner("locked")
    assert banner is not None and "W001" in banner.text()
    released.releases_panel.select_harness("W002")  # a draft: nothing is locked in front of you
    QApplication.processEvents()
    assert not released.alerts.is_showing("locked")
    # a unit that a released harness uses
    locked = [u for u in c.project.units if c.state_index().of("unit", u).locks]
    assert locked
    c.select("unit", locked[0])
    for area in ("model", "checks", "outputs"):
        released.set_area(area)
        QApplication.processEvents()
        assert released.alerts.is_showing("locked"), area
    c.select(None)
    released.set_area("model")
    QApplication.processEvents()
    assert not released.alerts.is_showing("locked")


def test_no_lock_banner_without_a_released_harness(draft) -> None:
    for area in ("model", "drawings", "revisions", "outputs", "checks"):
        draft.set_area(area)
        QApplication.processEvents()
        assert not draft.alerts.is_showing("locked")


def test_a_read_only_project_offers_no_way_out_of_the_lock(released) -> None:
    released.ctl.project.read_only = True
    released.set_area("revisions")
    released._update_lock_banner()
    banner = released.alerts.banner("locked")
    if banner is not None and released.alerts.is_showing("locked"):
        assert strings.LOCK_BANNER_ACTION not in banner.text()


# ---- Home ------------------------------------------------------------------------------------
def test_opening_a_project_puts_it_first_on_home(draft) -> None:
    entries = recent.load(draft.settings)
    assert entries and entries[0].path == str(draft.ctl.root)
    assert entries[0].units > 0 and entries[0].harnesses > 0
    assert draft.home_page.recent_rows


def test_the_flatsat_example_opens_as_a_copy_that_stays(draft, tmp_path) -> None:
    draft.open_example_flow("flatsat")
    copy = tmp_path / "examples" / "flatsat"
    assert (copy / "project.yaml").exists() or any(copy.iterdir())
    assert draft.ctl.root == copy
    marker = copy / "my-note.txt"
    marker.write_text("kept")
    draft.open_example_flow("flatsat")  # the second time it opens the copy, it does not overwrite
    assert marker.read_text() == "kept"


def test_the_example_button_is_the_main_action_on_home(draft) -> None:
    assert "flatsat" in draft.home_page.example_buttons
    assert draft.home_page.example_buttons["flatsat"].property("primary") is True


def test_a_recent_project_that_is_gone_says_so_and_can_be_forgotten(draft, tmp_path) -> None:
    ghost = tmp_path / "gone"
    shutil.copytree(draft.ctl.root, ghost)
    recent.remember(draft.settings, recent.RecentEntry(path=str(ghost), name="Gone"))
    shutil.rmtree(ghost)
    draft._update_home()
    draft.open_recent_flow(str(ghost))
    assert draft.ctl.root != ghost
    draft.forget_recent(str(ghost))
    assert all(e.path != str(ghost) for e in recent.load(draft.settings))


def test_recent_list_is_newest_first_without_duplicates_and_capped(tmp_path) -> None:
    s = QSettings(str(tmp_path / "r.ini"), QSettings.Format.IniFormat)
    for k in range(recent.LIMIT + 3):
        recent.remember(s, recent.RecentEntry(path=f"/p/{k}"))
    recent.remember(s, recent.RecentEntry(path="/p/5"))
    paths = [e.path for e in recent.load(s)]
    assert paths[0] == "/p/5" and len(paths) == recent.LIMIT and len(set(paths)) == len(paths)
    assert (
        recent.remember(s, recent.RecentEntry(path="/p/5")) is False
    )  # unchanged: nothing written


def test_a_damaged_recent_value_reads_as_empty(tmp_path) -> None:
    s = QSettings(str(tmp_path / "r.ini"), QSettings.Format.IniFormat)
    s.setValue(recent.KEY, "{not json")
    assert recent.load(s) == []
    s.setValue(recent.KEY, '[1, {"path": 3}, {"path": "/ok"}]')
    assert [e.path for e in recent.load(s)] == ["/ok"]


# ---- empty state -----------------------------------------------------------------------------
def test_a_table_without_rows_shows_its_empty_state_and_a_filter_says_no_match(qtbot) -> None:
    theme = ThemeManager()
    model = DictTableModel([Column("name", "Name")], [], theme)
    view = TableView(model, theme, name="T")
    qtbot.addWidget(view)
    view.resize(400, 300)
    called: list[int] = []
    state = attach_empty_state(
        view, "Empty", "Add one", action="Add", on_action=lambda: called.append(1)
    )
    view.show()
    QApplication.processEvents()
    assert state.isVisibleTo(view) and state.title.text() == "Empty"
    assert state.button is not None and state.button.isVisibleTo(state)
    state.button.click()
    assert called == [1]
    view.set_rows([{"name": "a"}, {"name": "b"}])
    assert not state.isVisible()
    view.proxy.set_predicate(lambda row: False)
    assert state.isVisibleTo(view) and state.title.text() == strings.EMPTY_FILTERED_TITLE
    assert state.button is not None and not state.button.isVisibleTo(state)
    view.proxy.set_predicate(None)
    assert not state.isVisible()
    view.set_rows([])
    assert state.title.text() == "Empty"


def test_the_interface_and_plan_tables_have_an_empty_state(draft) -> None:
    assert hasattr(draft.interface_table.view, "empty_state")
