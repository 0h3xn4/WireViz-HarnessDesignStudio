"""The navigation rail: one button per area, icon above label, down the left edge of the window.

    rail = NavRail(theme)
    rail.areaSelected.connect(window.set_area)
    rail.select("model")            # without a signal
    rail.set_collapsed(True)        # icons only

Settings sits at the bottom, away from the work areas. The rail holds no logic: it says which area
the person chose. Every button has an accessible name and a tooltip, so the icons-only form is
still usable with a screen reader and by hovering.
"""

from collections.abc import Collection

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from harness_design_studio.gui import areas, icons, strings
from harness_design_studio.gui.icons import tooltip_text
from harness_design_studio.gui.theme import ThemeManager

RAIL_PX = 72  # expanded width at 100 %
RAIL_COLLAPSED_PX = 48
ICON_PX = 20  # the brief: 20 px in the navigation rail


class NavRail(QFrame):
    areaSelected = Signal(str)

    def __init__(self, theme: ThemeManager, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.theme = theme
        self.collapsed = False  # the person's choice
        self.compact = False  # a short window: icons only, whatever the choice
        self.setObjectName("nav-rail")
        self.setProperty("rail", True)
        self.setAccessibleName(strings.RAIL_NAME)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(theme.space(4), theme.space(8), theme.space(4), theme.space(8))
        lay.setSpacing(theme.space(4))
        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        self.buttons: dict[str, QToolButton] = {}
        for a in areas.AREAS:
            button = QToolButton()
            button.setObjectName(f"rail-{a.key}")
            button.setProperty("rail", True)
            button.setCheckable(True)
            button.setText(a.title)
            button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
            button.setAccessibleName(a.title)
            button.setAccessibleDescription(a.tip)
            button.setToolTip(a.tip)
            button.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
            self.group.addButton(button)
            self.buttons[a.key] = button
            button.clicked.connect(lambda _c=False, key=a.key: self.areaSelected.emit(key))
            if a.key == "settings":
                lay.addStretch(1)  # Settings sits at the bottom
            lay.addWidget(button)
        self.toggle = QToolButton()
        self.toggle.setObjectName("rail-collapse")
        self.toggle.setProperty("rail", True)
        self.toggle.setProperty("iconOnly", True)
        self.toggle.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.toggle.clicked.connect(lambda _c=False: self.set_collapsed(not self.collapsed))
        lay.addWidget(self.toggle)
        theme.changed.connect(self._restyle)
        self.set_collapsed(False)

    # ---- state --------------------------------------------------------------------------------
    def select(self, key: str) -> None:
        """Mark an area as the current one (no signal)."""
        button = self.buttons[key]
        self.group.setExclusive(True)
        button.setChecked(True)

    def set_hidden(self, keys: Collection[str]) -> None:
        """List every area but these (a workspace may leave some out; they stay reachable by their
        keys and menus). The button of an area that is open stays checked."""
        for key, button in self.buttons.items():
            button.setVisible(key not in keys)

    def current(self) -> str:
        for key, button in self.buttons.items():
            if button.isChecked():
                return key
        return ""

    def set_collapsed(self, collapsed: bool) -> None:
        self.collapsed = collapsed
        self._apply_style()

    def set_compact(self, compact: bool) -> None:
        """A window too short for the labels (the window calls this when it is resized)."""
        if compact != self.compact:
            self.compact = compact
            self._apply_style()

    def icons_only(self) -> bool:
        return self.collapsed or self.compact

    def _apply_style(self) -> None:
        style = (
            Qt.ToolButtonStyle.ToolButtonIconOnly
            if self.icons_only()
            else Qt.ToolButtonStyle.ToolButtonTextUnderIcon
        )
        for button in self.buttons.values():
            button.setToolButtonStyle(style)
            button.setProperty("iconOnly", self.icons_only())
        self._restyle()

    def minimumSizeHint(self) -> QSize:  # noqa: N802
        """As small as the icons-only rail: the window may be short, and then the rail is that."""
        n = len(self.buttons) + 1
        h = n * self.theme.control_height() + (n + 1) * self.theme.space(4) + self.theme.space(16)
        return QSize(self.theme.px(RAIL_COLLAPSED_PX), h)

    def _restyle(self) -> None:
        t = self.theme
        for a in areas.AREAS:
            button = self.buttons[a.key]
            button.setIcon(icons.icon(a.icon, t))
            button.setIconSize(QSize(t.px(ICON_PX), t.px(ICON_PX)))
            button.setToolTip(tooltip_text(a.tip, ""))
        edge = t.px(RAIL_COLLAPSED_PX if self.icons_only() else RAIL_PX)
        self.setFixedWidth(edge)
        name = icons.icon("panel-open" if self.icons_only() else "panel-close", t)
        self.toggle.setIcon(name)
        self.toggle.setIconSize(QSize(t.px(16), t.px(16)))
        label = strings.RAIL_EXPAND if self.icons_only() else strings.RAIL_COLLAPSE
        self.toggle.setToolTip(label)
        self.toggle.setAccessibleName(label)
        for button in (*self.buttons.values(), self.toggle):
            button.style().unpolish(button)
            button.style().polish(button)
