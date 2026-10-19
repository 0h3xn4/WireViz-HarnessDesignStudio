"""The token-to-palette table and the `QPalette` built from it.

The application style sheet does not contain a single colour: it names palette roles
(`palette(base)`, `palette(highlight)` ...). A theme switch therefore only sets another palette and
repolishes the widgets; re-setting a style sheet would cost 300 to 500 ms because Qt parses and
matches it again for every widget. Qt 6.11 has more roles than the old ones, so every token a rule
needs has a role of its own (`ROLES`); Fusion's own drawing is covered by the style sheet, so the
borrowed meaning of a role (`light` is the secondary text colour) never shows.
"""

from typing import Final

from PySide6.QtGui import QColor, QPalette

# token -> (role name as the style sheet spells it, the QPalette role)
R = QPalette.ColorRole
ROLES: Final[dict[str, tuple[str, QPalette.ColorRole]]] = {
    "bg.canvas": ("window", R.Window),
    "bg.surface": ("base", R.Base),
    "bg.raised": ("button", R.Button),
    "bg.hover": ("alternate-base", R.AlternateBase),
    "bg.selected": ("midlight", R.Midlight),
    "border.subtle": ("mid", R.Mid),
    "border.strong": ("dark", R.Dark),
    "border.control": ("shadow", R.Shadow),
    "text.primary": ("window-text", R.WindowText),
    "text.secondary": ("light", R.Light),
    "text.muted": ("placeholder-text", R.PlaceholderText),
    "accent": ("highlight", R.Highlight),
    "accent.hover": ("accent", R.Accent),
    "accent.text": ("highlighted-text", R.HighlightedText),
    "focus": ("link-visited", R.LinkVisited),
    "status.critical": ("bright-text", R.BrightText),
    "status.standby": ("link", R.Link),
    "status.caution": ("tooltip-base", R.ToolTipBase),
    "status.serious": ("tooltip-text", R.ToolTipText),
    "status.normal": ("button-text", R.ButtonText),  # (the style sheet colours button text itself)
}
# roles that repeat a token for the parts of Qt that read them (plain text)
_ALSO: Final[dict[str, tuple[QPalette.ColorRole, ...]]] = {"text.primary": (R.Text,)}


def role(token: str) -> str:
    """The style sheet's spelling of a token's colour: `palette(base)`."""
    return f"palette({ROLES[token][0]})"


def build_palette(t: dict[str, str]) -> QPalette:
    """A `QPalette` from the tokens, so every widget (also native dialogs and custom-painted widgets
    that read the palette) uses the theme's colours."""
    pal = QPalette()
    for token, (_, qt_role) in ROLES.items():
        pal.setColor(qt_role, QColor(t[token]))
        for extra in _ALSO.get(token, ()):
            pal.setColor(extra, QColor(t[token]))
    for qt_role in (R.WindowText, R.Text):
        pal.setColor(QPalette.ColorGroup.Disabled, qt_role, QColor(t["text.muted"]))
    return pal
