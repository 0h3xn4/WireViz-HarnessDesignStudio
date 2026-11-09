# SPDX-FileCopyrightText: 2026 0h3xn4
# SPDX-License-Identifier: GPL-3.0-only
"""D-203, D-208: the app shows the licence and the legal texts, and says so once at the first start.

The About page holds every text word for word and the full licence text (GPL-3.0 section 5(d));
the notice of the first start is a banner that blocks nothing, is closed once and is remembered on
this computer only.
"""

from pathlib import Path

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

from harness_design_studio.core import legal_texts
from harness_design_studio.gui import licences, strings
from tests.gui_helpers import make_window

ROOT = Path(__file__).resolve().parents[1]


def test_about_shows_every_legal_text_word_for_word(qtbot, tmp_path) -> None:  # type: ignore[no-untyped-def]
    win = make_window(tmp_path)
    qtbot.addWidget(win)
    page = win.settings_page
    page.show_section("about")
    QApplication.processEvents()
    shown = [label.text() for label in page.legal_labels]
    for name in (
        "DISCLAIMER",
        "INTENDED_USE",
        "PROJECT_STATUS",
        "NOT_REVIEWED",
        "AI_AUTHORSHIP",
        "COPYRIGHT_SCOPE",
        "NON_AFFILIATION",
        "TRADEMARKS",
        "PRIVACY_APP",
    ):
        assert getattr(legal_texts, name) in shown, name
    assert legal_texts.LICENCE in strings.ABOUT_LICENCE_PROJECT


def test_the_full_licence_text_is_in_the_dialog_and_is_the_licence_file() -> None:
    text = licences.text_of("program")
    assert text == (ROOT / "LICENSE").read_text(encoding="utf-8")
    assert "GNU GENERAL PUBLIC LICENSE" in text and "Version 3, 29 June 2007" in text
    assert licences.entries()[0].key == "program"


def test_the_notice_of_the_first_start_blocks_nothing_and_is_closed_once(qtbot, tmp_path) -> None:  # type: ignore[no-untyped-def]
    win = make_window(tmp_path, first_run=True)
    qtbot.addWidget(win)
    assert win.alerts.is_showing("legal")
    banner = win.alerts.banner("legal")
    assert banner is not None
    assert banner.label.text() == legal_texts.PROJECT_STATUS
    assert legal_texts.DISCLAIMER in banner.details.text()
    assert QApplication.activeModalWidget() is None  # nothing blocks the window
    banner.dismissed.emit("legal")
    QApplication.processEvents()
    assert not win.alerts.is_showing("legal")
    stored = QSettings(str(tmp_path / "ui.ini"), QSettings.Format.IniFormat)
    assert stored.value("legal/notice_done", False, bool) is True
    win.close()
    again = make_window(tmp_path, first_run=True)  # same settings file: not shown again
    qtbot.addWidget(again)
    assert not again.alerts.is_showing("legal")


def test_no_notice_when_it_is_not_a_first_start(qtbot, tmp_path) -> None:  # type: ignore[no-untyped-def]
    win = make_window(tmp_path, first_run=False)
    qtbot.addWidget(win)
    assert not win.alerts.is_showing("legal")
