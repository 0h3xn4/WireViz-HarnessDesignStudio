"""Design tokens: the single source for GUI colours, type, spacing. No Qt imports on purpose.

The tokens follow the IBM Carbon design system (the White and Gray 100 themes, IBM Plex type) with
the status tones darkened where our stricter rule needs AA text contrast on every surface.

The clickable prototype (tools/build_prototype.py) and the real GUI both read these values.
Colour is never the only carrier of meaning: signal categories also differ by label, icon and
line weight; redundancy is a dashed line. Category colours were chosen to stay apart under
simulated colour blindness. Contrast and separation are verified in tests/test_tokens.py.
"""

from typing import Final

LIGHT: Final[dict[str, str]] = {  # IBM Carbon "White" theme (darker status tones for AA text)
    "bg": "#FFFFFF",
    "surface": "#F4F4F4",
    "surface-2": "#E8E8E8",
    "border": "#6F6F6F",
    "text": "#161616",
    "text-muted": "#525252",
    "primary": "#0353E9",
    "on-primary": "#FFFFFF",
    "focus": "#6A2FD8",
    "error": "#A2191F",
    "warning": "#684E00",
    "success": "#0E6027",
    "info": "#0043CE",
    "auto-fill": "#7A5C00",
    "locked": "#525252",
    "released": "#0E6027",
    "cat-power": "#B83014",
    "cat-data": "#000080",
    "cat-analog": "#235C53",
    "cat-rf": "#9933CC",
    "cat-pyro": "#5C0000",
    "cat-discrete": "#5500FF",
    "cat-ground": "#3A0953",
}

DARK: Final[dict[str, str]] = {  # IBM Carbon "Gray 100" theme
    "bg": "#161616",
    "surface": "#262626",
    "surface-2": "#393939",
    "border": "#8D8D8D",
    "text": "#F4F4F4",
    "text-muted": "#C6C6C6",
    "primary": "#78A9FF",
    "on-primary": "#161616",
    "focus": "#FFFFFF",
    "error": "#FF8389",
    "warning": "#F1C21B",
    "success": "#42BE65",
    "info": "#78A9FF",
    "auto-fill": "#F1C21B",
    "locked": "#C6C6C6",
    "released": "#42BE65",
    "cat-power": "#DDFF33",
    "cat-data": "#33FFFF",
    "cat-analog": "#9EF075",
    "cat-rf": "#E566FF",
    "cat-pyro": "#F07575",
    "cat-discrete": "#B89C14",
    "cat-ground": "#46A6B9",
}

CATEGORIES: Final[dict[str, dict[str, str]]] = {
    # name -> label, icon glyph (also drawn on the line), line weight in px
    "power": {"label": "Power", "icon": "P", "weight": "3.5"},
    "data": {"label": "Data", "icon": "D", "weight": "2"},
    "analog": {"label": "Analog", "icon": "A", "weight": "1.5"},
    "rf": {"label": "RF", "icon": "R", "weight": "2.5"},
    "pyro": {"label": "Pyro", "icon": "!", "weight": "4"},
    "discrete": {"label": "Discrete", "icon": "d", "weight": "1.5"},
    "ground": {"label": "Ground", "icon": "G", "weight": "1"},
}

# Model categories without their own design-system colour share one with a related category.
CATEGORY_ALIAS: Final[dict[str, str]] = {"thermal": "analog", "other": "ground"}


def style_category(category: str) -> str:
    """The design-system category used to draw an interface-type category."""
    key = CATEGORY_ALIAS.get(category, category)
    return key if key in CATEGORIES else "data"


FONT_UI: Final[str] = (
    "'IBM Plex Sans', 'Segoe UI', system-ui, sans-serif"  # bundled, see gui/fonts.py
)
FONT_MONO: Final[str] = "'IBM Plex Mono', Consolas, monospace"
# Type scale in px (base 14, ratio ~1.2) and spacing on a 4/8 px grid.
TYPE_SCALE: Final[dict[str, int]] = {"xs": 11, "sm": 12, "base": 14, "md": 16, "lg": 20, "xl": 24}
SPACING: Final[tuple[int, ...]] = (4, 8, 12, 16, 24, 32, 48)


def _lin(c: int) -> float:
    s = c / 255
    return s / 12.92 if s <= 0.03928 else ((s + 0.055) / 1.055) ** 2.4


def luminance(hex_colour: str) -> float:
    r, g, b = (int(hex_colour[i : i + 2], 16) for i in (1, 3, 5))
    return 0.2126 * _lin(r) + 0.7152 * _lin(g) + 0.0722 * _lin(b)


def contrast(a: str, b: str) -> float:
    """WCAG 2.x contrast ratio between two #RRGGBB colours."""
    hi, lo = sorted((luminance(a), luminance(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)
