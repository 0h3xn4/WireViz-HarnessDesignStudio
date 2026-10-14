"""REQ-UX-04: the interface uses the bundled IBM Plex fonts (Carbon's typefaces); nothing is fetched."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")
pytestmark = pytest.mark.gui

from PySide6.QtGui import QGuiApplication  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from harness_design_studio.gui import fonts  # noqa: E402
from harness_design_studio.gui.theme import ThemeManager  # noqa: E402
from harness_design_studio.resources import fonts_path  # noqa: E402


def test_the_font_files_and_their_licence_ship_with_the_program() -> None:
    folder = fonts_path()
    assert folder is not None
    names = {p.name for p in folder.iterdir()}
    assert {
        "IBMPlexSans-Regular.woff2",
        "IBMPlexMono-Regular.woff2",
        "OFL-1.1-IBM-Plex.txt",
    } <= names
    assert "SIL OPEN FONT LICENSE" in (folder / "OFL-1.1-IBM-Plex.txt").read_text(encoding="utf-8")


def test_the_theme_applies_the_bundled_ui_font() -> None:
    app = QApplication.instance() or QApplication([])
    assert {fonts.UI_FAMILY, fonts.MONO_FAMILY} <= set(fonts.load_fonts())
    ThemeManager().apply(app)  # type: ignore[arg-type]
    assert QGuiApplication.font().family() == fonts.UI_FAMILY


def test_tokens_name_the_bundled_families_first() -> None:
    from harness_design_studio.gui.tokens import FONT_MONO, FONT_UI

    assert FONT_UI.startswith("'IBM Plex Sans'") and FONT_MONO.startswith("'IBM Plex Mono'")
