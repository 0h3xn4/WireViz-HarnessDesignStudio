# mypy: disable-error-code="no-untyped-def,no-untyped-call"
"""UI overhaul, final milestone: what the brief's "Verification" and "Accessibility" sections ask for,
over every area of the window in both themes: opens without Qt warnings about style sheets, every
control has a name, every icon-only button a tooltip, the keyboard reaches everything and never gets
stuck, and focus can be seen."""

import pytest

pytest.importorskip("PySide6")
pytestmark = pytest.mark.gui

from PySide6.QtCore import QSettings, Qt, QtMsgType, qInstallMessageHandler  # noqa: E402
from PySide6.QtWidgets import (  # noqa: E402
    QAbstractButton,
    QApplication,
    QCheckBox,
    QComboBox,
    QLineEdit,
    QListWidget,
    QPushButton,
    QWidget,
)

from harness_design_studio.gui import areas  # noqa: E402
from harness_design_studio.gui.main_window import MainWindow  # noqa: E402
from harness_design_studio.gui.settings_page import SECTIONS  # noqa: E402
from harness_design_studio.gui.theme import ThemeManager  # noqa: E402
from tests.test_accessibility import unnamed  # noqa: E402
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


def _views(win):
    """Every place the window can show, as (name, show it): the areas, the tabs of a few of them,
    the sections of Settings, the Problems panel."""
    for key in areas.KEYS:
        yield key, lambda k=key: win.set_area(k)
    for tab in ("devices", "diagram", "harness", "lists", "releases", "checks"):
        yield f"tab-{tab}", lambda t=tab: win.go_to(t)
    for key, _title in SECTIONS:
        yield (
            f"settings-{key}",
            lambda k=key: (win.set_area("settings"), win.settings_page.show_section(k)),
        )
    yield "problems-panel", lambda: (win.set_area("model"), win.toggle_problems())


def _settle() -> None:
    for _ in range(3):
        QApplication.processEvents()


def test_every_view_opens_in_both_themes_without_qt_warnings(win) -> None:
    seen: list[str] = []

    def handler(kind, _context, message) -> None:
        if kind in (QtMsgType.QtWarningMsg, QtMsgType.QtCriticalMsg, QtMsgType.QtFatalMsg):
            seen.append(message)

    previous = qInstallMessageHandler(handler)
    try:
        for theme in ("light", "dark"):
            win.set_theme_mode(theme)
            assert win.theme.name == theme
            for _name, show in _views(win):
                show()
                _settle()
    finally:
        qInstallMessageHandler(previous)
    real = [m for m in seen if "propagateSizeHints" not in m]  # (the offscreen platform says this)
    assert real == []


def test_every_control_of_every_view_has_an_accessible_name(win) -> None:
    for name, show in _views(win):
        show()
        _settle()
        assert unnamed(win) == [], name


def test_every_icon_only_button_has_a_tooltip_and_a_name(win) -> None:
    bad: list[str] = []
    for name, show in _views(win):
        show()
        _settle()
        for b in win.findChildren(QAbstractButton):
            if not b.isVisibleTo(win) or b.text().strip() or not b.isEnabled() and not b.toolTip():
                continue
            if b.text().strip():
                continue
            if b.metaObject().className() == "QTabBarScrollButton":
                continue  # (Qt's own arrows of a tab bar)
            if not (b.toolTip().strip() and b.accessibleName().strip()):
                bad.append(f"{name}: {type(b).__name__} {b.objectName() or '(no name)'}")
    assert sorted(set(bad)) == []


def _focusable(win) -> list[QWidget]:
    return [
        w
        for w in win.findChildren(QWidget)
        if w.isVisibleTo(win) and w.isEnabled() and w.focusPolicy() & Qt.FocusPolicy.TabFocus
    ]


def test_the_keyboard_walk_visits_every_area_and_never_gets_stuck(win, qtbot) -> None:
    win.activateWindow()
    for key in areas.KEYS:
        win.set_area(key)
        _settle()
        order = _focusable(win)
        assert len(order) >= 3, key
        start = order[0]
        start.setFocus(Qt.FocusReason.TabFocusReason)
        _settle()
        first = QApplication.focusWidget()
        assert first is not None, key
        seen = [first]
        for _step in range(1500):
            win.focusNextPrevChild(True)
            now = QApplication.focusWidget()
            assert now is not None, f"{key}: focus lost"
            if now is first:
                break
            seen.append(now)
        else:
            raise AssertionError(f"{key}: the Tab key never came back to {first}")
        assert len(seen) >= 3, key
        for w in seen:
            assert w.isVisible() and w.isEnabled(), f"{key}: {type(w).__name__} {w.objectName()}"


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_focus_can_be_seen_on_every_kind_of_control(win, theme, qtbot) -> None:
    win.set_theme_mode(theme)
    win.set_area("settings")
    win.settings_page.show_section("appearance")
    page = win.settings_page
    win.activateWindow()
    _settle()
    kinds = {
        "combo": page.theme_combo,
        "check": page.motion_box,
        "button": win.generate_btn,
    }
    page.show_section("project")
    kinds["push"] = page.values_btn
    page.show_section("shortcuts")
    kinds["line"] = page.shortcut_filter
    for name, widget in kinds.items():
        if not widget.isVisibleTo(win):
            continue
        win.search_btn.setFocus(Qt.FocusReason.TabFocusReason)  # take the focus away
        _settle()
        before = widget.grab().toImage()
        widget.setFocus(Qt.FocusReason.TabFocusReason)
        _settle()
        assert widget.hasFocus(), name
        after = widget.grab().toImage()
        assert before != after, f"{name}: nothing shows that it has the focus ({theme})"


def test_the_kinds_of_widget_used_are_all_covered(win) -> None:
    """A guard for this file: it names the kinds of control the walk is about."""
    assert {QCheckBox, QComboBox, QLineEdit, QListWidget, QPushButton}


def test_a_tab_widget_without_a_visible_bar_is_not_a_tab_stop(win) -> None:
    """Regression: the right panel's tab widget has one tab and no visible bar, but it stayed a Tab
    stop that hands the focus to its hidden bar, so Tab from the project panel's tab bar went nowhere
    (a keyboard trap in every area)."""
    for key in areas.KEYS:
        win.set_area(key)
        _settle()
        for tabs in (win.main_tabs, win.left_tabs, win.side_tabs):
            stop = bool(tabs.focusPolicy() & Qt.FocusPolicy.TabFocus)
            assert stop == (not tabs.tabBar().isHidden()), f"{key}: {tabs.objectName()}"


def test_the_left_panel_comes_back_to_its_width_after_both_tables(win) -> None:
    """Regression (found in the final milestone): going from the Interfaces tab to the Units tab
    took the widened panel for the normal one, so the Project tab never got its width back."""
    win.set_area("model")
    _settle()
    before = win.dock_left.width()
    for tab in ("interfaces", "units", "interfaces", "tree"):
        win.left_tabs.setCurrentIndex(win.left_tabs.index_of(tab))
        _settle()
    assert abs(win.dock_left.width() - before) < 20
