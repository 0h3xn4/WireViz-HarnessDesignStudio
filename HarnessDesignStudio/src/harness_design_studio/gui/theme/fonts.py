"""Bundled fonts: Inter for the interface and JetBrains Mono for IDs, numbers and code (both SIL OFL).

They are loaded from the program itself with `QFontDatabase`; nothing is fetched and no system font
is needed. If the files are missing the interface falls back to the system font.
"""

from PySide6.QtGui import QFont, QFontDatabase

from harness_design_studio.gui.theme.tokens import FONT_MONO, FONT_UI
from harness_design_studio.resources import fonts_path

UI_FAMILY = FONT_UI
MONO_FAMILY = FONT_MONO

_loaded: list[str] | None = None


def load_fonts() -> list[str]:
    """Register the bundled fonts once; returns the family names that are available."""
    global _loaded
    if _loaded is not None:
        return _loaded
    families: list[str] = []
    folder = fonts_path()
    if folder is not None:
        for f in sorted(folder.glob("*.ttf")):
            fid = QFontDatabase.addApplicationFont(str(f))
            if fid >= 0:
                families += [
                    x for x in QFontDatabase.applicationFontFamilies(fid) if x not in families
                ]
    _loaded = families
    return families


def ui_family() -> str:
    """Inter when it is bundled and loaded, otherwise the system's default font."""
    if UI_FAMILY in load_fonts():
        return UI_FAMILY
    return QFontDatabase.systemFont(QFontDatabase.SystemFont.GeneralFont).family()


def mono_family() -> str:
    """JetBrains Mono when it is bundled and loaded, otherwise the system's fixed-width font."""
    if MONO_FAMILY in load_fonts():
        return MONO_FAMILY
    return QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont).family()


def weight(value: int) -> QFont.Weight:
    """The Qt weight for one of the three weights of the design language (400, 500, 600)."""
    return {400: QFont.Weight.Normal, 500: QFont.Weight.Medium, 600: QFont.Weight.DemiBold}[value]
