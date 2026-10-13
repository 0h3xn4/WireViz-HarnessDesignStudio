"""Theme: turns the design tokens into a Qt palette and style sheet (system, light, dark, UI scale).

Every colour, font size and gap in the program comes from here: `theme.color(token)`,
`theme.type(name)` (12 / 13 / 16 / 20 px), `theme.space(n)` (4 / 8 / 12 / 16 / 24 / 32 px),
`theme.font(...)` and `theme.mono_font()` (IBM Plex Mono for pin numbers, part numbers, hashes and
paths). Widgets pick up the rules with properties (`primary`, `danger`, `align`, `mono`, `muted`,
`heading`) instead of calling `setStyleSheet` themselves.
"""

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QColor, QFont, QFontDatabase, QGuiApplication, QPalette
from PySide6.QtWidgets import QApplication, QWidget

from harness_design_studio.gui import fonts
from harness_design_studio.gui.tokens import CONTROL_HEIGHT, DARK, LIGHT, SPACING, TYPE_SCALE

BASE_PX = TYPE_SCALE["base"]
MODES = ("system", "light", "dark")  # what the person chooses; "system" follows the OS scheme


_current: "ThemeManager | None" = None


def current_theme() -> "ThemeManager":
    """The theme manager that was applied last (a default light one before any), for widgets built
    without a reference to the main window's. Connect to its `changed` signal to follow it."""
    global _current
    if _current is None:
        _current = ThemeManager()
    return _current


def os_scheme() -> str:
    """The colour scheme the operating system asks for: "dark" or "light" (also when it says
    nothing, as the offscreen platform does)."""
    if QGuiApplication.instance() is None:
        return "light"
    return "dark" if QGuiApplication.styleHints().colorScheme() == Qt.ColorScheme.Dark else "light"


def mono_family() -> str:
    """IBM Plex Mono when it is bundled and loaded, otherwise the system's fixed-width font."""
    if fonts.MONO_FAMILY in fonts.load_fonts():
        return fonts.MONO_FAMILY
    return QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont).family()


def mono_item_font() -> QFont:
    """A font for table cells and fields that sets only the family, so the size comes from the
    view (and follows the UI scale)."""
    f = QFont()
    f.setFamily(mono_family())
    f.setStyleHint(QFont.StyleHint.Monospace)
    return f


def mark_mono(widget: QWidget) -> None:
    """Show a widget's text in the monospace font (the `mono` rule of the style sheet)."""
    widget.setProperty("mono", True)
    widget.style().unpolish(widget)
    widget.style().polish(widget)


def build_palette(t: dict[str, str]) -> QPalette:
    """A `QPalette` from the tokens, so widgets the style sheet does not reach (native dialogs,
    custom-painted widgets that read the palette) use the same colours."""
    pal = QPalette()
    roles = {
        QPalette.ColorRole.Window: t["bg"],
        QPalette.ColorRole.WindowText: t["text"],
        QPalette.ColorRole.Base: t["bg"],
        QPalette.ColorRole.AlternateBase: t["surface"],
        QPalette.ColorRole.Text: t["text"],
        QPalette.ColorRole.Button: t["surface"],
        QPalette.ColorRole.ButtonText: t["text"],
        QPalette.ColorRole.BrightText: t["error"],
        QPalette.ColorRole.Highlight: t["primary"],
        QPalette.ColorRole.HighlightedText: t["on-primary"],
        QPalette.ColorRole.ToolTipBase: t["surface"],
        QPalette.ColorRole.ToolTipText: t["text"],
        QPalette.ColorRole.PlaceholderText: t["text-muted"],
        QPalette.ColorRole.Link: t["info"],
        QPalette.ColorRole.LinkVisited: t["focus"],
        QPalette.ColorRole.Light: t["bg"],
        QPalette.ColorRole.Midlight: t["surface"],
        QPalette.ColorRole.Mid: t["surface-2"],
        QPalette.ColorRole.Dark: t["border"],
        QPalette.ColorRole.Shadow: t["border"],
    }
    for role, value in roles.items():
        pal.setColor(role, QColor(value))
    for role in (
        QPalette.ColorRole.WindowText,
        QPalette.ColorRole.Text,
        QPalette.ColorRole.ButtonText,
    ):
        pal.setColor(QPalette.ColorGroup.Disabled, role, QColor(t["text-muted"]))
    return pal


class ThemeManager(QObject):
    """Holds the current theme and UI scale; widgets that custom-paint listen to `changed`.

    `mode` is the choice ("system", "light" or "dark"); `name` is what is shown ("light" or
    "dark"). With mode "system" the theme follows the operating system, also while the program
    runs.
    """

    changed = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.mode = "system"
        self.name = "light"
        self.scale = 1.0
        self._app: QApplication | None = None
        self._watching = False

    # ---- tokens and units ------------------------------------------------------------------
    @property
    def tokens(self) -> dict[str, str]:
        return DARK if self.name == "dark" else LIGHT

    def color(self, token: str) -> QColor:
        return QColor(self.tokens[token])

    def px(self, value: float) -> int:
        return max(1, round(value * self.scale))

    def type(self, name: str) -> int:
        """Font size in px for a step of the type scale ("sm" 12, "base" 13, "md" 16, "lg" 20),
        times the UI scale."""
        return self.px(TYPE_SCALE[name])

    def space(self, n: int) -> int:
        """A gap in px: n must be on the spacing scale (4, 8, 12, 16, 24 or 32); times the UI
        scale."""
        if n not in SPACING:
            raise ValueError(f"{n} px is not on the spacing scale {SPACING}")
        return self.px(n)

    def control_height(self) -> int:
        """The one height of buttons, combo boxes and line edits."""
        return self.px(CONTROL_HEIGHT)

    def icon_size(self, step: int = 16) -> int:
        """Edge of an icon in px (16 by default; 12, 16, 24 or 32 on the spacing scale)."""
        return self.px(step)

    # ---- fonts -----------------------------------------------------------------------------
    def font(
        self,
        role: str = "base",
        *,
        mono: bool = False,
        bold: bool = False,
        tabular: bool = False,
    ) -> QFont:
        """A font for painting: the UI font (IBM Plex Sans) or, with `mono`, IBM Plex Mono, at a
        step of the type scale. `tabular` turns on tabular figures (digits of equal width)."""
        f = QFont()
        if mono:
            f.setFamily(mono_family())
            f.setStyleHint(QFont.StyleHint.Monospace)
        elif fonts.UI_FAMILY in fonts.load_fonts():
            f.setFamily(fonts.UI_FAMILY)
        f.setPixelSize(self.type(role))
        f.setBold(bold)
        if tabular:
            f.setFeature(QFont.Tag("tnum"), 1)
        return f

    def mono_font(self, role: str = "base", *, bold: bool = False) -> QFont:
        """IBM Plex Mono (or the system's fixed-width font) for pin numbers, part numbers,
        requirement IDs, hashes and paths."""
        return self.font(role, mono=True, bold=bold)

    # ---- applying --------------------------------------------------------------------------
    def apply(self, app: QApplication, name: str | None = None, scale: float | None = None) -> None:
        """Set the mode ("system", "light" or "dark"; None keeps it) and the UI scale, then
        rebuild the palette, the fonts and the style sheet."""
        global _current
        _current = self
        self._app = app
        if name is not None:
            self.mode = name if name in MODES else "light"
        if scale is not None:
            self.scale = max(1.0, min(2.0, scale))
        self.name = os_scheme() if self.mode == "system" else self.mode
        if not self._watching:
            self._watching = True
            QGuiApplication.styleHints().colorSchemeChanged.connect(self._os_changed)
        font = QFont(app.font())
        if fonts.UI_FAMILY in fonts.load_fonts():
            font.setFamily(fonts.UI_FAMILY)
        font.setPixelSize(self.type("base"))
        app.setFont(font)
        app.setPalette(build_palette(self.tokens))
        app.setStyleSheet(stylesheet(self.tokens, self.scale, mono_family()))
        self.changed.emit()

    def _os_changed(self, _scheme: object = None) -> None:
        if self.mode == "system" and self._app is not None and os_scheme() != self.name:
            self.apply(self._app)


def stylesheet(t: dict[str, str], scale: float, mono: str = "monospace") -> str:
    def px(v: float) -> str:
        return f"{max(1, round(v * scale))}px"

    base, small = px(TYPE_SCALE["base"]), px(TYPE_SCALE["sm"])
    s4, s8, s12, s16 = px(4), px(8), px(12), px(16)
    # one height for every control: the box (min-height plus the 1 px border above and below)
    inner = f"{max(1, round(CONTROL_HEIGHT * scale) - 2)}px"
    icon = px(16)
    return f"""
QWidget {{ background: {t["bg"]}; color: {t["text"]}; font-size: {base}; }}
QWidget[mono="true"] {{ font-family: "{mono}"; }}
QMainWindow, QDialog {{ background: {t["bg"]}; }}
QToolBar {{ background: {t["surface"]}; border-bottom: 1px solid {t["border"]}; spacing: {s4}; padding: {s4}; }}
QMenuBar {{ background: {t["surface"]}; }}
QMenuBar::item:selected, QMenu::item:selected {{ background: {t["primary"]}; color: {t["on-primary"]}; }}
QMenu {{ background: {t["surface"]}; border: 1px solid {t["border"]}; }}
QMenu::item:disabled {{ color: {t["text-muted"]}; }}
QDockWidget {{ border: 1px solid {t["border"]}; font-size: {base}; }}
QDockWidget::title {{ background: {t["surface"]}; padding: {s8}; }}
QStatusBar {{ background: {t["surface"]}; color: {t["text-muted"]}; border-top: 1px solid {t["border"]}; font-size: {small}; }}
QStatusBar::item {{ border: none; }}
QPushButton, QToolButton {{ background: {t["surface"]}; border: 1px solid {t["border"]}; border-radius: 0; padding: 0 {s12}; min-height: {inner}; max-height: {inner}; qproperty-iconSize: {icon} {icon}; }}
QToolButton[iconOnly="true"] {{ padding: 0 {s8}; min-width: {inner}; }}
QPushButton:hover:enabled, QToolButton:hover:enabled {{ background: {t["surface-2"]}; }}
QPushButton:disabled, QToolButton:disabled {{ color: {t["text-muted"]}; border-color: {t["surface-2"]}; }}
QPushButton[primary="true"] {{ background: {t["primary"]}; color: {t["on-primary"]}; border-color: {t["primary"]}; font-weight: 600; }}
QPushButton[primary="true"]:hover:enabled {{ background: {t["primary"]}; }}
QPushButton[danger="true"] {{ border-color: {t["error"]}; color: {t["error"]}; }}
QPushButton[align="left"] {{ text-align: left; }}
QToolButton:checked, QPushButton:checked {{ background: {t["primary"]}; color: {t["on-primary"]}; border-color: {t["primary"]}; }}
QPushButton:focus, QToolButton:focus, QLineEdit:focus, QComboBox:focus, QTextEdit:focus, QPlainTextEdit:focus {{ border: 2px solid {t["focus"]}; }}
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {{ background: {t["surface"]}; border: 1px solid {t["surface-2"]}; border-bottom: 1px solid {t["border"]}; border-radius: 0; padding: 0 {s8}; min-height: {inner}; max-height: {inner}; }}
QTextEdit, QPlainTextEdit {{ background: {t["surface"]}; border: 1px solid {t["surface-2"]}; border-bottom: 1px solid {t["border"]}; border-radius: 0; padding: {s4} {s8}; }}
QLineEdit[invalid="true"] {{ border: 2px solid {t["error"]}; }}
QComboBox QAbstractItemView {{ background: {t["bg"]}; selection-background-color: {t["primary"]}; selection-color: {t["on-primary"]}; }}
QTabWidget::pane {{ border: 1px solid {t["border"]}; top: -1px; }}
QTabBar::tab {{ background: {t["surface"]}; padding: {s8} {s16}; border: 1px solid {t["surface-2"]}; border-bottom: 2px solid transparent; }}
QTabBar::tab:selected {{ background: {t["bg"]}; font-weight: 600; border-bottom: 2px solid {t["primary"]}; }}
QTabBar::tab:focus {{ border: 2px solid {t["focus"]}; }}
QTableView, QListWidget {{ background: {t["bg"]}; alternate-background-color: {t["surface"]}; gridline-color: {t["surface-2"]}; selection-background-color: {t["primary"]}; selection-color: {t["on-primary"]}; border: 1px solid {t["border"]}; }}
QTableView {{ font-size: {small}; }}
QHeaderView::section {{ background: {t["surface"]}; color: {t["text-muted"]}; border: 0; border-bottom: 1px solid {t["border"]}; padding: {s4}; }}
QScrollArea {{ border: none; }}
QLabel[muted="true"] {{ color: {t["text-muted"]}; }}
QLabel[error="true"] {{ color: {t["error"]}; }}
QLabel[heading="true"] {{ color: {t["text-muted"]}; font-weight: 600; text-transform: uppercase; }}
QFrame[card="true"] {{ background: {t["bg"]}; border: 1px solid {t["border"]}; border-radius: 0; }}
QFrame[card="true"][severity="warning"] {{ border-left: {px(6)} solid {t["warning"]}; }}
QFrame[card="true"][severity="error"] {{ border-left: {px(6)} solid {t["error"]}; }}
QFrame[card="true"][severity="info"] {{ border-left: {px(6)} solid {t["info"]}; }}
QFrame[banner="true"] {{ background: {t["surface-2"]}; border: 1px solid {t["warning"]}; }}
QFrame[banner="true"][severity="error"] {{ border: 1px solid {t["error"]}; border-left: {px(6)} solid {t["error"]}; }}
QFrame[banner="true"][severity="info"] {{ border: 1px solid {t["info"]}; border-left: {px(6)} solid {t["info"]}; }}
QToolTip {{ background: {t["surface"]}; color: {t["text"]}; border: 1px solid {t["border"]}; padding: {s4}; }}
QProgressBar {{ border: 1px solid {t["border"]}; border-radius: 0; text-align: center; }}
QProgressBar::chunk {{ background: {t["primary"]}; }}
"""
