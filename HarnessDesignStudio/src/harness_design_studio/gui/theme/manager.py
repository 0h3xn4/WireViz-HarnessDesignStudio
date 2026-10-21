"""Theme manager: the current theme (system, light, dark), the UI scale, fonts and units.

Every colour, font size and gap in the program comes from here: `theme.color(token)`,
`theme.type(name)` (11 / 12 / 13 / 15 / 18 / 22 px), `theme.space(n)` (4 / 8 / 12 / 16 / 24 / 32 px),
`theme.font(...)` and `theme.mono_font()` (JetBrains Mono for pin numbers, part numbers, hashes and
paths). Widgets pick up the rules of the style sheet with properties (`primary`, `danger`, `align`,
`mono`, `muted`, `heading`) instead of calling `setStyleSheet` themselves.

Switching between light and dark does not touch the style sheet (see palette.py): it sets the other
palette and repolishes the widgets, and widgets that custom-paint listen to `changed`.
"""

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QColor, QFont, QGuiApplication
from PySide6.QtWidgets import QApplication, QWidget

from harness_design_studio.gui import timing
from harness_design_studio.gui.theme import fonts
from harness_design_studio.gui.theme.palette import build_palette
from harness_design_studio.gui.theme.qss import stylesheet
from harness_design_studio.gui.theme.style import ThemeStyle
from harness_design_studio.gui.theme.tokens import (
    CONTROL_HEIGHT,
    CONTROL_HEIGHT_COMPACT,
    DARK,
    LIGHT,
    MOTION_BASE_MS,
    MOTION_FAST_MS,
    RADIUS_CONTROL,
    RADIUS_PANEL,
    ROW_HEIGHT,
    SPACING,
    TYPE_SCALE,
)

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
    """JetBrains Mono when it is bundled and loaded, otherwise the system's fixed-width font."""
    return fonts.mono_family()


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


MOTION_EFFECTS = (
    Qt.UIEffect.UI_AnimateMenu,
    Qt.UIEffect.UI_FadeMenu,
    Qt.UIEffect.UI_AnimateCombo,
    Qt.UIEffect.UI_AnimateTooltip,
    Qt.UIEffect.UI_FadeTooltip,
    Qt.UIEffect.UI_AnimateToolBox,
)


class ThemeManager(QObject):
    """Holds the current theme and UI scale; widgets that custom-paint listen to `changed`.

    `mode` is the choice ("system", "light" or "dark"); `name` is what is shown ("light" or
    "dark"). With mode "system" the theme follows the operating system, also while the program
    runs. `reduce_motion` turns the short transitions off (`motion(ms)` gives 0 then).
    """

    changed = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.mode = "system"
        self.name = "light"
        self.scale = 1.0
        self.reduce_motion = False
        self._effects: dict[Qt.UIEffect, bool] | None = (
            None  # Qt's own effects before we changed any
        )
        self._app: QApplication | None = None
        self._watching = False
        self._sheet_scale: float | None = None  # the scale the installed style sheet was made for
        self._style: ThemeStyle | None = None

    # ---- tokens and units ------------------------------------------------------------------
    @property
    def tokens(self) -> dict[str, str]:
        return DARK if self.name == "dark" else LIGHT

    def color(self, token: str) -> QColor:
        return QColor(self.tokens[token])

    def px(self, value: float) -> int:
        return max(1, round(value * self.scale))

    def type(self, name: str) -> int:
        """Font size in px for a step of the type scale ("caption" 11, "small" 12, "base" 13,
        "section" 15, "title" 18, "display" 22), times the UI scale."""
        return self.px(TYPE_SCALE[name])

    def space(self, n: int) -> int:
        """A gap in px: n must be on the spacing scale (4, 8, 12, 16, 24 or 32); times the UI
        scale."""
        if n not in SPACING:
            raise ValueError(f"{n} px is not on the spacing scale {SPACING}")
        return self.px(n)

    def control_height(self, compact: bool = False) -> int:
        """The one height of buttons, combo boxes and line edits (28 px when compact)."""
        return self.px(CONTROL_HEIGHT_COMPACT if compact else CONTROL_HEIGHT)

    def row_height(self) -> int:
        """The height of a table row."""
        return self.px(ROW_HEIGHT)

    def radius(self, panel: bool = False) -> int:
        """Corner radius in px: 6 for controls, 8 for panels, popovers and dialogs."""
        return self.px(RADIUS_PANEL if panel else RADIUS_CONTROL)

    def icon_size(self, step: int = 16) -> int:
        """Edge of an icon in px (16 by default; 12, 16, 24 or 32 on the spacing scale)."""
        return self.px(step)

    def set_reduce_motion(self, on: bool) -> None:
        """Reduce motion: `motion()` gives 0 and Qt stops its own fades and slides of menus, lists
        and tooltips (what each was before is put back when it is turned off)."""
        self.reduce_motion = on
        if QApplication.instance() is None:
            return
        if self._effects is None:
            self._effects = {e: QApplication.isEffectEnabled(e) for e in MOTION_EFFECTS}
        for effect, was in self._effects.items():
            QApplication.setEffectEnabled(effect, was and not on)

    def motion(self, base: bool = False) -> int:
        """Duration in ms of a transition (120 for hover, 180 for panels and toasts); 0 when the
        person asked to reduce motion."""
        return 0 if self.reduce_motion else (MOTION_BASE_MS if base else MOTION_FAST_MS)

    # ---- fonts -----------------------------------------------------------------------------
    def font(
        self,
        role: str = "base",
        *,
        mono: bool = False,
        weight: int = 400,
        bold: bool = False,
        tabular: bool = False,
    ) -> QFont:
        """A font for painting: the UI font (Inter) or, with `mono`, JetBrains Mono, at a step of
        the type scale and one of the weights 400, 500 and 600 (`bold` means 600). `tabular`
        turns on tabular figures (digits of equal width)."""
        f = QFont()
        if mono:
            f.setFamily(mono_family())
            f.setStyleHint(QFont.StyleHint.Monospace)
        else:
            f.setFamily(fonts.ui_family())
        f.setPixelSize(self.type(role))
        f.setWeight(fonts.weight(600 if bold else weight))
        if tabular:
            f.setFeature(QFont.Tag("tnum"), 1)
        return f

    def mono_font(self, role: str = "base", *, bold: bool = False) -> QFont:
        """JetBrains Mono (or the system's fixed-width font) for pin numbers, part numbers,
        requirement IDs, hashes and paths."""
        return self.font(role, mono=True, bold=bold)

    # ---- applying --------------------------------------------------------------------------
    def apply(self, app: QApplication, name: str | None = None, scale: float | None = None) -> None:
        """Set the mode ("system", "light" or "dark"; None keeps it) and the UI scale.

        The first call, and a change of scale, installs the style, the font and the style sheet.
        A change of theme only sets the palette and repolishes the widgets."""
        with timing.timed(f"theme apply ({name or self.mode}, scale {scale or self.scale})"):
            self._apply(app, name, scale)

    def _apply(self, app: QApplication, name: str | None, scale: float | None) -> None:
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
        # Tab reaches every control, not only text fields
        QGuiApplication.styleHints().setTabFocusBehavior(Qt.TabFocusBehavior.TabFocusAllControls)
        if self._style is None:
            # one widget style on every system: the look comes from the tokens, and the native
            # Windows style differs in keyboard focus and in how cells are edited
            self._style = ThemeStyle()
            app.setStyle(self._style)
        scale_changed = self._sheet_scale != self.scale
        self._style.scale = self.scale
        if scale_changed:
            font = QFont(app.font())
            font.setFamily(fonts.ui_family())
            font.setPixelSize(self.type("base"))
            font.setWeight(fonts.weight(400))
            font.setFeature(
                QFont.Tag("tnum"), 1
            )  # digits of equal width: columns of numbers line up
            app.setFont(font)
        app.setPalette(build_palette(self.tokens))
        if scale_changed:
            app.setStyleSheet(stylesheet(self.scale, mono_family()))
            self._sheet_scale = self.scale
        else:
            self._repolish(app)
        self.changed.emit()

    @staticmethod
    def _repolish(app: QApplication) -> None:
        """Make the widgets read the new palette (the style sheet names palette roles).

        Visible widgets are polished again now. Hidden ones (most of them: the other tabs, closed
        dialogs) are only unpolished and marked as not polished, so Qt polishes them with the new
        palette the first time they are shown; polishing all of them at once would take 5 times as
        long for pages nobody looks at."""
        not_polished = Qt.WidgetAttribute.WA_WState_Polished
        for w in app.allWidgets():
            style = w.style()
            style.unpolish(w)
            if w.isVisible():
                style.polish(w)
                w.update()
            else:
                w.setAttribute(not_polished, False)

    def _os_changed(self, _scheme: object = None) -> None:
        if self.mode == "system" and self._app is not None and os_scheme() != self.name:
            self.apply(self._app)
