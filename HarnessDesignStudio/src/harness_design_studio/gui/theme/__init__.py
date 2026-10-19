"""The theme package: tokens, palette, style sheet, widget style, fonts and the manager.

`gui/theme/tokens.py` is the one source of colours, type sizes, gaps and durations. Import the
manager and the helpers from here (`from harness_design_studio.gui.theme import ThemeManager`).
"""

from harness_design_studio.gui.theme.manager import (
    BASE_PX,
    MODES,
    ThemeManager,
    current_theme,
    mark_mono,
    mono_family,
    mono_item_font,
    os_scheme,
)
from harness_design_studio.gui.theme.palette import ROLES, build_palette
from harness_design_studio.gui.theme.qss import stylesheet

__all__ = [
    "BASE_PX",
    "MODES",
    "ROLES",
    "ThemeManager",
    "build_palette",
    "current_theme",
    "mark_mono",
    "mono_family",
    "mono_item_font",
    "os_scheme",
    "stylesheet",
]
