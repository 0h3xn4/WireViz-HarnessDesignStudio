"""Bundled fonts: IBM Plex Sans and Mono (Carbon's typefaces), loaded from the program itself.

Nothing is fetched and no system font is needed. If the files are missing the interface falls back
to the system font; the tokens name the fallbacks.
"""

from pathlib import Path

from PySide6.QtGui import QFontDatabase

from harness_design_studio.resources import fonts_path

UI_FAMILY = "IBM Plex Sans"
MONO_FAMILY = "IBM Plex Mono"

_loaded: list[str] | None = None


def _register(files: list[Path]) -> list[str]:
    families: list[str] = []
    for f in files:
        fid = QFontDatabase.addApplicationFont(str(f))
        if fid >= 0:
            families += [x for x in QFontDatabase.applicationFontFamilies(fid) if x not in families]
    return families


def load_fonts() -> list[str]:
    """Register the bundled fonts once; returns the family names that are available."""
    global _loaded
    if _loaded is not None:
        return _loaded
    families: list[str] = []
    folder = fonts_path()
    if folder is not None:
        families = _register(sorted(folder.glob("*.woff2")))
        if not {UI_FAMILY, MONO_FAMILY} <= set(families):
            # Qt on Windows cannot read WOFF2. The Windows package carries the same fonts as
            # TrueType files next to the WOFF2 ones (packaging/fonts/); the other packages do not.
            families += [x for x in _register(sorted(folder.glob("*.ttf"))) if x not in families]
    _loaded = families
    return families
