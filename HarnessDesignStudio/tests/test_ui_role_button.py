# SPDX-FileCopyrightText: 2026 0h3xn4
# SPDX-License-Identifier: GPL-3.0-only
# mypy: disable-error-code="no-untyped-def,no-untyped-call,attr-defined,has-type"
"""The Role button of the top bar: the role is always visible and one click away.

It shows the role in words, lists the three roles (the same exclusive actions as View > Role), follows
a change made anywhere else, and stays in the bar in every role. Nothing else about roles changes."""

from pathlib import Path

import pytest

pytest.importorskip("PySide6")
pytestmark = pytest.mark.gui

from PySide6.QtCore import QSettings  # noqa: E402
from PySide6.QtWidgets import QToolButton  # noqa: E402

from harness_design_studio.gui import roles, strings  # noqa: E402
from harness_design_studio.gui.main_window import MainWindow  # noqa: E402
from harness_design_studio.gui.theme import ThemeManager  # noqa: E402


def make(qtbot, tmp_path: Path, **values: object) -> MainWindow:
    s = QSettings(str(tmp_path / "ui.ini"), QSettings.Format.IniFormat)
    for key, value in values.items():
        s.setValue(key.replace("__", "/"), value)
    s.sync()
    w = MainWindow(s, ThemeManager(), first_run=False)
    qtbot.addWidget(w)
    w.resize(1440, 900)
    return w


def test_the_button_shows_the_role_in_words(qtbot, tmp_path):
    w = make(qtbot, tmp_path, ui__role=roles.SYSTEMS)
    assert isinstance(w.role_btn, QToolButton)
    assert w.role_btn.text() == strings.ROLE_BUTTON.format(strings.ROLE_SYSTEMS)
    assert w.role_btn.parent() is not None and w.topbar.isAncestorOf(w.role_btn)


def test_the_button_lists_the_three_roles_and_switches(qtbot, tmp_path):
    w = make(qtbot, tmp_path, ui__role=roles.ELECTRICAL)
    menu = w.role_btn.menu()
    roles_part = menu.actions()[:3]
    assert [a.text().replace("&", "") for a in roles_part] == [
        strings.ROLE_SYSTEMS,
        strings.ROLE_ELECTRICAL,
        strings.ROLE_AIT,
    ]
    assert menu.actions()[3].isSeparator() and menu.actions()[4] is w.act_quick  # Quick mode
    assert len(menu.actions()) == 5
    assert [a.isChecked() for a in roles_part] == [False, True, False]
    menu.actions()[2].trigger()  # AIT engineer
    assert w.role == roles.AIT
    assert w.role_btn.text() == strings.ROLE_BUTTON.format(strings.ROLE_AIT)
    assert w.settings.value("ui/role") == roles.AIT


def test_the_button_follows_a_change_made_elsewhere(qtbot, tmp_path):
    w = make(qtbot, tmp_path, ui__role=roles.ELECTRICAL)
    w.act_role_systems.trigger()  # View > Role does the same
    assert w.role_btn.text() == strings.ROLE_BUTTON.format(strings.ROLE_SYSTEMS)
    w.set_role(roles.AIT)
    assert w.role_btn.text() == strings.ROLE_BUTTON.format(strings.ROLE_AIT)


@pytest.mark.parametrize("role", roles.ROLES)
def test_the_button_stays_in_every_role_and_has_names(qtbot, tmp_path, role):
    w = make(qtbot, tmp_path, ui__role=role)
    w.show()
    assert not w.role_btn.isHidden()
    assert w.role_btn.accessibleName() == strings.ROLE_BUTTON_NAME
    assert w.role_btn.toolTip() == strings.ROLE_BUTTON_TIP
