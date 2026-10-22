# mypy: disable-error-code="no-untyped-def,no-untyped-call"
"""UI overhaul M9: the Settings area. Sections for appearance, editing, the project, keyboard shortcuts,
About and Licences; every setting applies at once, is kept for the next start, and the page follows
the menus and Ctrl+K that change the same things."""

import pytest

pytest.importorskip("PySide6")
pytestmark = pytest.mark.gui

from PySide6.QtCore import QSettings, Qt  # noqa: E402
from PySide6.QtWidgets import (  # noqa: E402
    QApplication,
    QCheckBox,
    QComboBox,
    QLineEdit,
    QListWidget,
    QPushButton,
)

from harness_design_studio import __version__  # noqa: E402
from harness_design_studio.gui import licences, strings  # noqa: E402
from harness_design_studio.gui.main_window import MainWindow  # noqa: E402
from harness_design_studio.gui.settings_page import SECTIONS  # noqa: E402
from harness_design_studio.gui.theme import ThemeManager  # noqa: E402
from tests.ux_rel import flatsat_controller  # noqa: E402


def _window(qtbot, ini):
    w = MainWindow(QSettings(str(ini), QSettings.Format.IniFormat), ThemeManager(), first_run=False)
    w.ask_choice = lambda t, x, b: 1  # type: ignore[assignment]
    qtbot.addWidget(w)
    w.resize(1440, 900)
    w.show()
    QApplication.processEvents()
    return w


@pytest.fixture
def win(qtbot, tmp_path):
    ctl = flatsat_controller(tmp_path)
    root = ctl.root
    ctl.release()
    w = _window(qtbot, tmp_path / "ui.ini")
    assert root is not None and w.open_project(root)
    w.set_area("settings")
    QApplication.processEvents()
    return w


def _click(box) -> None:
    box.click()
    QApplication.processEvents()


def test_the_page_has_six_sections_each_with_a_name(win) -> None:
    page = win.settings_page
    assert [page.sections.item(i).text() for i in range(page.sections.count())] == [
        t for _k, t in SECTIONS
    ]
    for key, title in SECTIONS:
        assert page.pages[key].accessibleName() == title
    assert page.sections.accessibleName() and page.current_section() == "appearance"
    for key, _t in SECTIONS:
        page.show_section(key)
        assert page.stack.currentWidget() is page.pages[key]


def test_every_control_of_the_page_has_an_accessible_name_and_takes_the_keyboard(win) -> None:
    page = win.settings_page
    kinds = (QCheckBox, QComboBox, QPushButton, QLineEdit, QListWidget)
    controls = [w for k in kinds for w in page.findChildren(k)]
    assert len(controls) >= 8
    for w in controls:
        name = w.accessibleName() or (w.text() if hasattr(w, "text") else "")
        assert name, w.objectName()
        assert w.focusPolicy() != Qt.FocusPolicy.NoFocus, w.objectName()


def test_the_theme_the_scale_and_reduce_motion_apply_at_once_and_are_kept(
    qtbot, win, tmp_path
) -> None:
    page = win.settings_page
    page.theme_combo.setCurrentIndex(page.theme_combo.findData("dark"))
    page.theme_combo.activated.emit(page.theme_combo.currentIndex())
    assert win.theme.name == "dark"
    page.scale_combo.setCurrentIndex(page.scale_combo.findData(125))
    page.scale_combo.activated.emit(page.scale_combo.currentIndex())
    assert win.theme.scale == 1.25
    _click(page.motion_box)
    assert win.theme.reduce_motion and win.theme.motion() == 0 and win.act_reduce_motion.isChecked()
    win.settings.sync()
    w2 = _window(qtbot, tmp_path / "ui.ini")  # the next start
    assert (w2.theme.mode, w2.theme.scale, w2.theme.reduce_motion) == ("dark", 1.25, True)
    page2 = w2.settings_page
    assert page2.theme_combo.currentData() == "dark" and page2.scale_combo.currentData() == 125
    assert page2.motion_box.isChecked()


def test_mode_snap_and_labels_apply_at_once_and_are_kept(qtbot, win, tmp_path) -> None:
    page = win.settings_page
    page.mode_combo.setCurrentIndex(page.mode_combo.findData("expert"))
    page.mode_combo.activated.emit(page.mode_combo.currentIndex())
    assert win.ctl.mode == "expert"
    assert page.snap_box.isChecked() and win.view.dscene.snap_to_grid
    _click(page.snap_box)
    assert not win.view.dscene.snap_to_grid and not win.act_snap.isChecked()
    assert not page.labels_box.isChecked() and not win.view.dscene.show_all_labels
    _click(page.labels_box)
    assert win.view.dscene.show_all_labels and win.act_labels.isChecked()
    win.settings.sync()
    w2 = _window(qtbot, tmp_path / "ui.ini")
    assert w2.ctl.mode == "expert"
    assert not w2.view.dscene.snap_to_grid and w2.view.dscene.show_all_labels
    p2 = w2.settings_page
    assert p2.mode_combo.currentData() == "expert"
    assert not p2.snap_box.isChecked() and p2.labels_box.isChecked()


def test_the_page_follows_the_menus_and_the_palette(win) -> None:
    page = win.settings_page
    win.act_snap.trigger()
    win.act_labels.trigger()
    win.act_reduce_motion.trigger()
    assert (
        not page.snap_box.isChecked()
        and page.labels_box.isChecked()
        and page.motion_box.isChecked()
    )
    win.set_theme_mode("dark")
    assert page.theme_combo.currentData() == "dark"
    names = [e.label for e in win.palette_entries()]
    assert strings.SETTINGS_REDUCE_MOTION in names  # reachable with Ctrl+K as well


def test_reduce_motion_turns_qt_effects_off_and_puts_them_back(qapp, monkeypatch) -> None:
    """(The offscreen platform allows no effects, so Qt's switches are replaced by a dictionary.
    The test needs the application object: without one, `set_reduce_motion` changes nothing.)"""
    from harness_design_studio.gui.theme.manager import MOTION_EFFECTS

    state = {e: True for e in MOTION_EFFECTS}
    state[MOTION_EFFECTS[-1]] = False  # one that was off to begin with stays off
    start = dict(state)
    monkeypatch.setattr(QApplication, "isEffectEnabled", staticmethod(lambda e: state[e]))
    monkeypatch.setattr(
        QApplication, "setEffectEnabled", staticmethod(lambda e, on=True: state.__setitem__(e, on))
    )
    theme = ThemeManager()
    theme.set_reduce_motion(True)
    assert theme.motion() == 0 and theme.motion(base=True) == 0
    assert not any(state.values())
    theme.set_reduce_motion(False)
    assert state == start and theme.motion() > 0


def test_the_shortcuts_list_has_every_key_of_the_window_and_filters(win) -> None:
    page = win.settings_page
    page.show_section("shortcuts")
    rows = {r["action"]: r["keys"] for r in page.shortcut_model.rows()}  # type: ignore[index]
    undo = win.act_undo
    assert rows[undo.text().replace("&", "")] == undo.shortcut().toString(
        undo.shortcut().SequenceFormat.NativeText
    )
    for action, keys in strings.SHORTCUTS_EXTRA:
        assert rows[action] == keys
    every = page.shortcut_table.proxy.rowCount()
    page.shortcut_filter.setText("undo")
    shown = page.shortcut_table.proxy.rowCount()
    assert 1 <= shown < every
    page.shortcut_filter.setText("zzzz no such key")
    QApplication.processEvents()
    assert page.shortcut_table.proxy.rowCount() == 0
    assert page.shortcut_table.empty_state.isVisibleTo(page.shortcut_table)  # type: ignore[attr-defined]
    page.shortcut_filter.clear()
    assert page.shortcut_table.proxy.rowCount() == every


def test_every_shortcut_is_listed_once_per_key(win) -> None:
    keys = [k for _a, k in win.shortcut_rows()]
    assert keys and all(keys)
    assert [a for a, _k in win.shortcut_rows()] == sorted(
        (a for a, _k in win.shortcut_rows()), key=str.lower
    )


def test_about_is_a_section_not_a_message_box(win) -> None:
    win.set_area("home")
    win.act_about.trigger()  # (a message box would block the test)
    assert win.area() == "settings" and win.settings_page.current_section() == "about"
    page = win.settings_page
    assert __version__ in page.version_label.text()
    assert "Qt" in page.runtime_label.text()
    assert page.file_label.text().endswith(win.settings.fileName())


def test_licences_lists_every_component_with_its_text(win) -> None:
    page = win.settings_page
    page.show_section("licences")
    assert page.licence_model.rowCount() == len(licences.entries()) == 4
    for i, c in enumerate(licences.entries()):
        page.licence_table.selectRow(i)
        QApplication.processEvents()
        text = page.licence_text.toPlainText()
        assert text.strip(), c.key
        assert text == licences.text_of(c.key)
    assert "SIL OPEN FONT LICENSE" in licences.text_of("inter").upper()
    assert "SIL OPEN FONT LICENSE" in licences.text_of("jetbrains").upper()
    assert "ISC" in licences.text_of("lucide") and "MIT" in licences.text_of("lucide")
    assert "LGPL" in licences.text_of("qt") or "Lesser" in licences.text_of("qt")


def test_the_package_licence_report_uses_the_same_text() -> None:
    from tools import collect_licences

    assert collect_licences.LUCIDE_LICENCES is licences.LUCIDE_LICENCES
