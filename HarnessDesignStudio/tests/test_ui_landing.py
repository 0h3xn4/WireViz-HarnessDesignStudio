# SPDX-FileCopyrightText: 2026 0h3xn4
# SPDX-License-Identifier: GPL-3.0-only
# mypy: disable-error-code="no-untyped-def,no-untyped-call,attr-defined,union-attr,arg-type,method-assign"
"""REQ-GUI-29 (D-223). The program starts on Home, a landing page, and opens no project by itself:
not the one that was open when it was closed (the settings key `project/last` of 1.17 and before is
read by nothing and removed). Home lists New project, Open project, the examples and the recent
projects, newest first; *Clear list* empties the list after a question and touches no project
folder. Closing the window releases the project's lock and writes only the window's own settings.

The start is played through `app.main()` itself (its event loop replaced), so the test sees what a
person sees when the program starts.
"""

from pathlib import Path

import pytest

pytest.importorskip("PySide6")
pytestmark = pytest.mark.gui

from PySide6.QtCore import QSettings  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from harness_design_studio.core import templates  # noqa: E402
from harness_design_studio.core.io.fs import LOCK_NAME  # noqa: E402
from harness_design_studio.gui import app as app_module  # noqa: E402
from harness_design_studio.gui import recent, strings  # noqa: E402
from harness_design_studio.gui.main_window import LEGACY_LAST_PROJECT, MainWindow  # noqa: E402


def settings_at(tmp_path: Path, name: str = "ui.ini", **values: object) -> QSettings:
    s = QSettings(str(tmp_path / name), QSettings.Format.IniFormat)
    s.setValue("tour/done", True)
    s.setValue("legal/notice_done", True)
    for key, value in values.items():
        s.setValue(key.replace("__", "/"), value)
    s.sync()
    return s


def project(tmp_path: Path, name: str) -> Path:
    folder = tmp_path / name
    templates.create_project(folder, "first-steps", name)
    return folder


def start(qtbot, monkeypatch: pytest.MonkeyPatch, settings: QSettings) -> MainWindow:
    """Run `app.main()` as the program does, with these settings and without its event loop."""
    made: list[MainWindow] = []
    create = app_module.create_window

    def recorded(*args, **kwargs):
        win = create(*args, **kwargs)
        win.ask_choice = lambda title, text, buttons: len(buttons) - 1  # (no one is there)
        made.append(win)
        return win

    monkeypatch.setattr(app_module, "make_settings", lambda: settings)
    monkeypatch.setattr(app_module, "create_window", recorded)
    monkeypatch.setattr(QApplication, "exec", lambda self: 0)
    code = app_module.main()
    assert code == 0
    (win,) = made
    qtbot.addWidget(win)
    QApplication.processEvents()
    return win


def on_landing(win: MainWindow) -> bool:
    return (
        win.landing()
        and win.area() == "home"
        and win.home_page.isVisibleTo(win)
        and win.home_page.landing_note.isVisibleTo(win)
        and not win.home_page.project_card.isVisibleTo(win)
        and not win.top_toolbar.isVisibleTo(win)
        and not win.statusBar().isVisibleTo(win)
        and not win.banner.isVisibleTo(win)
        and not any(d.isVisibleTo(win) for d in (win.dock_left, win.dock_right, win.dock_problems))
    )


def test_a_start_with_a_saved_last_project_shows_home_and_opens_nothing(
    qtbot, monkeypatch, tmp_path
) -> None:
    last = project(tmp_path, "worked-on")
    settings = settings_at(tmp_path, project__last=str(last))
    win = start(qtbot, monkeypatch, settings)
    assert on_landing(win)
    assert win.ctl.root is None  # no project folder is open
    assert not (last / LOCK_NAME).exists()  # ... and the last one is not locked by this program
    assert not settings.contains(LEGACY_LAST_PROJECT)  # the old key is gone, without an error
    for key in ("new", "open", "example"):  # the ways to start are on the page
        assert win.home_page.buttons[key].isVisibleTo(win)


def test_an_old_settings_file_with_a_damaged_last_project_starts_too(
    qtbot, monkeypatch, tmp_path
) -> None:
    settings = settings_at(tmp_path, project__last="\x00 not a folder")
    win = start(qtbot, monkeypatch, settings)
    assert on_landing(win) and win.ctl.root is None


def test_a_recent_project_is_one_click_and_the_landing_page_ends(
    qtbot, monkeypatch, tmp_path
) -> None:
    folder = project(tmp_path, "kept")
    settings = settings_at(tmp_path)
    recent.remember(settings, recent.RecentEntry(path=str(folder), name="kept"))
    win = start(qtbot, monkeypatch, settings)
    assert on_landing(win) and len(win.home_page.recent_rows) == 1
    open_btn = win.home_page.recent_rows[0].findChild(
        type(win.home_page.clear_btn), "home-recent-open"
    )
    open_btn.click()
    QApplication.processEvents()
    assert win.ctl.root == folder
    assert not win.landing() and win.area() == "model"  # a project opened from Home: the diagram
    assert win.top_toolbar.isVisibleTo(win) and win.statusBar().isVisibleTo(win)
    assert win.dock_left.isVisibleTo(win)  # the panels came back as they were
    assert not settings.contains(LEGACY_LAST_PROJECT)  # opening writes no "last project"
    win.set_area("home")
    assert win.home_page.project_card.isVisibleTo(win)  # Home now shows the open project
    assert not win.home_page.landing_note.isVisibleTo(win)


def test_going_to_another_area_ends_the_landing_page(qtbot, monkeypatch, tmp_path) -> None:
    win = start(qtbot, monkeypatch, settings_at(tmp_path))
    win.set_area("model")
    assert not win.landing() and win.top_toolbar.isVisibleTo(win)
    assert win.ctl.sample and win.banner.isVisibleTo(win)  # the sample says what it is
    win.set_area("home")
    assert not win.landing()  # (the landing page is the start only)


def test_an_edit_on_the_landing_page_ends_it(qtbot, monkeypatch, tmp_path) -> None:
    win = start(qtbot, monkeypatch, settings_at(tmp_path))
    win.ctl.add_unit("sensor")  # (as Edit > Add device does from the menu)
    QApplication.processEvents()
    assert not win.landing() and win.top_toolbar.isVisibleTo(win)


def test_the_tour_from_the_landing_page_goes_to_the_work(qtbot, monkeypatch, tmp_path) -> None:
    win = start(qtbot, monkeypatch, settings_at(tmp_path))
    win._start_tour()
    assert not win.landing() and win.area() == "model" and win.tour.active
    win.tour.stop()


def test_clear_list_asks_first_and_empties_only_the_list(qtbot, monkeypatch, tmp_path) -> None:
    folders = [project(tmp_path, name) for name in ("one", "two")]
    settings = settings_at(tmp_path)
    for f in folders:
        recent.remember(settings, recent.RecentEntry(path=str(f), name=f.name))
    win = start(qtbot, monkeypatch, settings)
    page = win.home_page
    assert page.clear_btn.isVisibleTo(win) and len(page.recent_rows) == 2
    asked: list[tuple[str, list[str]]] = []

    def answer(index: int):
        def ask(title: str, text: str, buttons: list[str]) -> int:
            asked.append((title, buttons))
            return index

        return ask

    win.ask_choice = answer(1)  # Cancel: nothing changes
    page.clear_btn.click()
    assert asked == [(strings.HOME_CLEAR_TITLE, [strings.HOME_CLEAR_OK, strings.CANCEL])]
    assert [e.path for e in recent.load(settings)] == [str(f) for f in reversed(folders)]
    assert len(page.recent_rows) == 2 and page.clear_btn.isVisibleTo(win)
    win.ask_choice = answer(0)  # Clear list
    page.clear_btn.click()
    assert recent.load(settings) == [] and page.recent_rows == []
    assert page.recent_empty.isVisibleTo(win) and not page.clear_btn.isVisibleTo(win)
    assert all((f / "project.json").is_file() for f in folders)  # the folders are untouched
    settings.sync()
    text = (tmp_path / "ui.ini").read_text(encoding="utf-8")
    assert all(str(f) not in text for f in folders)  # no name or folder is left in the file


def test_clear_list_is_hidden_while_the_list_is_empty(qtbot, monkeypatch, tmp_path) -> None:
    win = start(qtbot, monkeypatch, settings_at(tmp_path))
    assert recent.load(win.settings) == []
    assert not win.home_page.clear_btn.isVisibleTo(win)
    assert win.home_page.recent_empty.isVisibleTo(win)


def test_the_recent_projects_are_newest_first(qtbot, monkeypatch, tmp_path) -> None:
    folders = [project(tmp_path, name) for name in ("first", "second", "third")]
    win = start(qtbot, monkeypatch, settings_at(tmp_path))
    for f in folders:
        opened = win.open_project(f)
        assert opened
    win.open_project(folders[0])  # opened again: first again, not twice
    win.set_area("home")
    QApplication.processEvents()
    assert [e.name for e in recent.load(win.settings)] == ["first", "third", "second"]
    titles = [
        row.findChildren(type(win.home_page.landing_note))[0].text()
        for row in win.home_page.recent_rows
    ]
    assert titles == ["first", "third", "second"]


def test_closing_releases_the_project_and_writes_no_last_project(
    qtbot, monkeypatch, tmp_path
) -> None:
    folder = project(tmp_path, "closing")
    settings = settings_at(tmp_path)
    win = start(qtbot, monkeypatch, settings)
    opened = win.open_project(folder)
    assert opened
    assert (folder / LOCK_NAME).exists()  # held while it is open
    closed = win.close()
    assert closed
    assert not (folder / LOCK_NAME).exists()  # released on close
    settings.sync()
    assert not settings.contains(LEGACY_LAST_PROJECT)
    assert settings.contains("ui/geometry")  # the window's own settings are kept
    assert [e.path for e in recent.load(settings)] == [str(folder)]  # and the recent list
    # the next start: Home again, nothing opened
    again = start(qtbot, monkeypatch, settings)
    assert on_landing(again) and again.ctl.root is None


def test_closing_on_the_landing_page_keeps_the_stored_panels(qtbot, monkeypatch, tmp_path) -> None:
    settings = settings_at(tmp_path)
    first = start(qtbot, monkeypatch, settings)
    first.set_area("model")  # leave the landing page, then close: the layout is stored
    closed = first.close()
    assert closed
    settings.sync()
    stored = settings.value("ui/state")
    second = start(qtbot, monkeypatch, settings)
    assert on_landing(second)
    closed = second.close()  # closed on the landing page, where the panels were put away
    assert closed
    settings.sync()
    assert settings.value("ui/state") == stored
    third = start(qtbot, monkeypatch, settings)
    third.set_area("model")
    assert third.dock_left.isVisibleTo(third) and third.top_toolbar.isVisibleTo(third)
