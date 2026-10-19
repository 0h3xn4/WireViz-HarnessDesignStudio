"""REQ-UX-04: the interface uses the bundled Inter and JetBrains Mono fonts; nothing is fetched."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")
pytestmark = pytest.mark.gui

from PySide6.QtGui import QFont, QFontInfo, QGuiApplication  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from harness_design_studio.gui.theme import ThemeManager, fonts  # noqa: E402
from harness_design_studio.gui.theme.tokens import FONT_MONO, FONT_UI, WEIGHTS  # noqa: E402
from harness_design_studio.resources import fonts_path  # noqa: E402


def test_the_font_files_and_their_licences_ship_with_the_program() -> None:
    folder = fonts_path()
    assert folder is not None
    names = {p.name for p in folder.iterdir()}
    assert {
        "Inter-Regular.ttf",
        "Inter-Medium.ttf",
        "Inter-SemiBold.ttf",
        "JetBrainsMono-Regular.ttf",
        "JetBrainsMono-Medium.ttf",
        "OFL-1.1-Inter.txt",
        "OFL-1.1-JetBrains-Mono.txt",
    } <= names
    assert not any("plex" in n.lower() for n in names)
    for licence in ("OFL-1.1-Inter.txt", "OFL-1.1-JetBrains-Mono.txt"):
        assert "SIL OPEN FONT LICENSE" in (folder / licence).read_text(encoding="utf-8")


def test_the_theme_applies_the_bundled_ui_font() -> None:
    app = QApplication.instance() or QApplication([])
    assert {fonts.UI_FAMILY, fonts.MONO_FAMILY} <= set(fonts.load_fonts())
    ThemeManager().apply(app)  # type: ignore[arg-type]
    assert QGuiApplication.font().family() == fonts.UI_FAMILY


def test_tokens_name_the_bundled_families() -> None:
    assert (FONT_UI, FONT_MONO) == ("Inter", "JetBrains Mono")
    assert fonts.UI_FAMILY == FONT_UI and fonts.MONO_FAMILY == FONT_MONO


def test_the_three_weights_of_the_design_language_exist() -> None:
    QApplication.instance() or QApplication([])
    fonts.load_fonts()
    assert WEIGHTS == (400, 500, 600)
    for weight in WEIGHTS:
        f = QFont(FONT_UI)
        f.setPixelSize(13)
        f.setWeight(fonts.weight(weight))
        assert QFontInfo(f).family() == FONT_UI
        assert QFontInfo(f).weight() == weight


def test_tabular_figures_are_available_for_numbers() -> None:
    app = QApplication.instance() or QApplication([])
    theme = ThemeManager()
    theme.apply(app)  # type: ignore[arg-type]
    f = theme.font("small", tabular=True)
    assert f.family() == FONT_UI and f.pixelSize() == theme.type("small")
