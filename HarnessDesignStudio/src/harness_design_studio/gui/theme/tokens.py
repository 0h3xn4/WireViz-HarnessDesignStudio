"""Design tokens: the single source of every GUI colour, type size, gap, radius and duration.

No Qt imports on purpose: the QSS (`qss.py`), the palette (`palette.py`) and every painter read
these values, and the tests read them without a display. Nothing else in `gui/` names a colour, a
font family or a font size (a test fails if it does).

Colours are the brief's starting values (docs/ui/UI_OVERHAUL.md), tuned only where WCAG 2.2 AA
asked for it (D-150): the text-like colours are darkened on the light theme and lightened on the dark
theme until they reach 4.5:1 on every surface (`canvas`, `surface`, `raised`, `hover`); the dark
accent needs dark text on it. Status colours follow the Astro UX taxonomy (critical, serious, caution,
normal, standby, off). Colour is never the only carrier of meaning: states also have an icon and a
word (gui/states.py) and signal categories differ by label, icon and line weight.

The legacy names (`bg`, `surface`, `primary`, `error` ...) are aliases of the new tokens, kept so
the existing painters and tests keep working; they are retired as the screens are rebuilt.
Contrast and separation are verified in tests/test_tokens.py and tests/test_theme_contrast.py.
"""

from typing import Final

# ---- colours ------------------------------------------------------------------------------------

_LIGHT_NEW: Final[dict[str, str]] = {
    "bg.canvas": "#F7F7F8",
    "bg.surface": "#FFFFFF",
    "bg.raised": "#FFFFFF",  # lifted by a shadow, not by a colour
    "bg.hover": "#F0F1F3",
    "bg.selected": "#E9EFFD",  # the accent at 10 % over the surface
    "border.subtle": "#E4E5E9",
    "border.strong": "#D0D3D9",
    "border.control": "#838B95",  # outline of an input or a check box (3:1 as WCAG 1.4.11 asks)
    "text.primary": "#16181D",
    "text.secondary": "#50565F",
    "text.muted": "#646A72",
    "accent": "#1E5EEA",
    "accent.text": "#FFFFFF",  # text and icons on an accent fill
    "accent.hover": "#1A52D0",  # an accent fill under the pointer or pressed
    "focus": "#1E5EEA",
    "status.critical": "#D40002",
    "status.serious": "#B24700",
    "status.caution": "#8D6007",
    "status.normal": "#19784A",
    "status.standby": "#0B6DB2",
    "status.off": "#646A72",
    "diff.added": "#DFECE6",  # tinted backgrounds: the status colour at 14 % over the surface
    "diff.removed": "#F9DBDC",
    "diff.changed": "#EFE9DC",
    "state.autofill": "#8D6007",
    "state.pending": "#0A6D6D",
    "state.notchecked": "#5C626F",
    "paper": "#FFFFFF",  # the drawing sheet stays white in both themes
    "pasteboard": "#8A8A94",
    "cat-power": "#B83014",
    "cat-data": "#000080",
    "cat-analog": "#235C53",
    "cat-rf": "#9933CC",
    "cat-pyro": "#5C0000",
    "cat-discrete": "#5500FF",
    "cat-ground": "#3A0953",
}

_DARK_NEW: Final[dict[str, str]] = {
    "bg.canvas": "#0B0D10",
    "bg.surface": "#111418",
    "bg.raised": "#171B21",
    "bg.hover": "#1D222A",
    "bg.selected": "#1A273D",  # the accent at 16 % over the surface
    "border.subtle": "#222832",
    "border.strong": "#2E3540",
    "border.control": "#6B7380",
    "text.primary": "#E7E9EC",
    "text.secondary": "#A1A8B3",
    "text.muted": "#868E99",
    "accent": "#4C8DFF",
    "accent.text": "#0B0D10",
    "accent.hover": "#78A3FF",
    "focus": "#4C8DFF",
    "status.critical": "#FF4D4F",
    "status.serious": "#FF8A3D",
    "status.caution": "#F5B83D",
    "status.normal": "#3DD68C",
    "status.standby": "#56B4F5",
    "status.off": "#868E99",
    "diff.added": "#172F28",
    "diff.removed": "#321C20",
    "diff.changed": "#312B1D",
    "state.autofill": "#F5B83D",
    "state.pending": "#3DDBD9",
    "state.notchecked": "#C1C7CD",
    "paper": "#FFFFFF",
    "pasteboard": "#3A3A3A",
    "cat-power": "#DDFF33",
    "cat-data": "#33FFFF",
    "cat-analog": "#9EF075",
    "cat-rf": "#E566FF",
    "cat-pyro": "#F07575",
    "cat-discrete": "#B89C14",
    "cat-ground": "#46A6B9",
}

# The logo's colours (docs/img/logo.svg); the same in both themes, drawn by gui/appicon.py.
BRAND: Final[dict[str, str]] = {"purple": "#4a1fb8", "amber": "#f2b04a", "white": "#ffffff"}

# legacy name -> new token (the value is looked up in the theme's own table)
LEGACY_ALIAS: Final[dict[str, str]] = {
    "bg": "bg.canvas",
    "surface": "bg.surface",
    "surface-2": "bg.hover",
    "border": "border.control",
    "text": "text.primary",
    "text-muted": "text.muted",
    "primary": "accent",
    "on-primary": "accent.text",
    "error": "status.critical",
    "warning": "status.caution",
    "success": "status.normal",
    "info": "status.standby",
    "auto-fill": "state.autofill",
    "locked": "text.secondary",
    "released": "status.normal",
    "pending": "state.pending",
    "not-checked": "state.notchecked",
    "stale": "status.serious",
}


def _with_aliases(new: dict[str, str]) -> dict[str, str]:
    out = dict(new)
    for legacy, token in LEGACY_ALIAS.items():
        out[legacy] = new[token]
    return out


LIGHT: Final[dict[str, str]] = _with_aliases(_LIGHT_NEW)
DARK: Final[dict[str, str]] = _with_aliases(_DARK_NEW)

# Tokens that carry text or icons (tests check 4.5:1 on every surface) and the surfaces they sit on.
SURFACES: Final[tuple[str, ...]] = ("bg.canvas", "bg.surface", "bg.raised", "bg.hover")
TEXT_TOKENS: Final[tuple[str, ...]] = (
    "text.primary",
    "text.secondary",
    "text.muted",
    "accent",
    "status.critical",
    "status.serious",
    "status.caution",
    "status.normal",
    "status.standby",
    "status.off",
    "state.autofill",
    "state.pending",
    "state.notchecked",
)

# ---- categories (diagram line colours, with label, icon and weight as non-colour cues) ----------

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

# Model categories without their own colour share one with a related category.
CATEGORY_ALIAS: Final[dict[str, str]] = {"thermal": "analog", "other": "ground"}


def style_category(category: str) -> str:
    """The category used to draw an interface-type category."""
    key = CATEGORY_ALIAS.get(category, category)
    return key if key in CATEGORIES else "data"


# ---- type, space, shape, motion -----------------------------------------------------------------

FONT_UI: Final[str] = "Inter"  # bundled (resources/fonts), registered by theme/fonts.py
FONT_MONO: Final[str] = "JetBrains Mono"  # IDs, pin numbers, part numbers, hashes, paths, logs
FONT_UI_FALLBACK: Final[str] = "Segoe UI"
# Sizes in px at 100 %: caption, small and table cells, body (the base), section title, page title,
# display. Weights are 400, 500 and 600 only. Code asks the theme (`theme.type(name)`).
TYPE_SCALE: Final[dict[str, int]] = {
    "caption": 11,
    "small": 12,
    "base": 13,
    "section": 15,
    "title": 18,
    "display": 22,
}
WEIGHTS: Final[tuple[int, ...]] = (400, 500, 600)
SPACING: Final[tuple[int, ...]] = (4, 8, 12, 16, 24, 32)  # the 4 px grid; `theme.space(n)`
CONTROL_HEIGHT: Final[int] = 32  # buttons, combo boxes and line edits at 100 %
CONTROL_HEIGHT_COMPACT: Final[int] = 28
ROW_HEIGHT: Final[int] = 26  # table rows
RADIUS_CONTROL: Final[int] = 6
RADIUS_PANEL: Final[int] = 8  # panels, popovers, dialogs
FOCUS_RING: Final[int] = 2
# The zoomed-out diagram draws unit IDs in scene units (not UI px) so they stay readable far away.
OVERVIEW_FONT_PX: Final[int] = 22
# Shadows only lift floating things (menus, popovers, dialogs, toasts): blur, y offset, alpha.
SHADOW: Final[tuple[int, int, int]] = (16, 4, 60)
MOTION_FAST_MS: Final[int] = 120  # hover
MOTION_BASE_MS: Final[int] = 180  # panel open and close, toasts


# ---- contrast helpers ---------------------------------------------------------------------------


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
