"""The two areas that are pages of their own: Home and Settings.

    home = HomePage(theme, new=..., open_=..., example=..., sample=...)
    home.show_project(name, path, summary)
    settings = SettingsPage(theme, set_theme=..., set_scale=..., set_mode=..., open_values=...)
    settings.sync(theme_mode="dark", scale=125, mode="expert")

Both only show and call back; the window does the work. Home is the first screen of a project:
what is open and how to start another. Settings holds what used to hide in the View menu (theme,
interface size, mode) and points to the project's configuration (the engineering values).
"""

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from harness_design_studio.gui import strings
from harness_design_studio.gui.shell import ElidedLabel
from harness_design_studio.gui.theme import ThemeManager, mark_mono

SCALES = (100, 125, 150, 200)
THEMES = (
    ("system", strings.SETTINGS_THEME_SYSTEM),
    ("light", strings.SETTINGS_THEME_LIGHT),
    ("dark", strings.SETTINGS_THEME_DARK),
)
MODES = (("guided", strings.GUIDED), ("expert", strings.EXPERT))


def _page(theme: ThemeManager, name: str, title: str) -> tuple[QScrollArea, QVBoxLayout]:
    """A scrolling page with a title and a column that is never wider than a readable line."""
    scroll = QScrollArea()
    scroll.setObjectName(name)
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QFrame.Shape.NoFrame)
    scroll.setAccessibleName(title)
    body = QWidget()
    outer = QHBoxLayout(body)
    column = QVBoxLayout()
    column.setSpacing(theme.space(16))
    outer.setContentsMargins(theme.space(24), theme.space(24), theme.space(24), theme.space(24))
    outer.addLayout(column, 1)
    outer.addStretch(1)
    heading = QLabel(title)
    heading.setProperty("title", True)
    heading.setAccessibleName(title)
    column.addWidget(heading)
    scroll.setWidget(body)
    body.setMaximumWidth(theme.px(900))
    return scroll, column


def _card(theme: ThemeManager, heading: str) -> tuple[QFrame, QVBoxLayout]:
    card = QFrame()
    card.setProperty("card", True)
    lay = QVBoxLayout(card)
    lay.setContentsMargins(theme.space(16), theme.space(12), theme.space(16), theme.space(16))
    lay.setSpacing(theme.space(8))
    label = QLabel(heading)
    label.setProperty("heading", True)
    lay.addWidget(label)
    return card, lay


class HomePage(QScrollArea):
    def __init__(
        self,
        theme: ThemeManager,
        *,
        new: Callable[[], None],
        open_: Callable[[], None],
        example: Callable[[], None],
        sample: Callable[[], None],
    ) -> None:
        super().__init__()
        page, column = _page(theme, "home-page", strings.HOME_TITLE)
        self.setObjectName("home-page")
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setWidget(page.takeWidget())
        self.setAccessibleName(strings.HOME_TITLE)
        card, lay = _card(theme, strings.HOME_PROJECT)
        self.name = ElidedLabel()
        self.name.setProperty("title", True)
        self.name.setObjectName("home-name")
        self.name.setAccessibleName(strings.HOME_PROJECT)
        self.path = ElidedLabel()
        self.path.setObjectName("home-path")
        mark_mono(self.path)
        self.path.setProperty("muted", True)
        self.summary = QLabel()
        self.summary.setObjectName("home-summary")
        self.summary.setProperty("muted", True)
        for w in (self.name, self.path, self.summary):
            lay.addWidget(w)
        column.addWidget(card)
        start, start_lay = _card(theme, strings.HOME_ACTIONS)
        row = QHBoxLayout()
        self.buttons: dict[str, QPushButton] = {}
        for key, text, callback in (
            ("new", strings.HOME_NEW, new),
            ("open", strings.HOME_OPEN, open_),
            ("example", strings.HOME_EXAMPLE, example),
            ("sample", strings.HOME_SAMPLE, sample),
        ):
            b = QPushButton(text)
            b.setObjectName(f"home-{key}")
            b.setAccessibleName(text.rstrip("…"))
            b.clicked.connect(lambda _c=False, cb=callback: cb())
            row.addWidget(b)
            self.buttons[key] = b
        row.addStretch(1)
        start_lay.addLayout(row)
        column.addWidget(start)
        column.addStretch(1)

    def show_project(self, name: str, path: str, summary: str) -> None:
        self.name.set_full_text(name)
        self.path.set_full_text(path or strings.HOME_NO_PROJECT)
        self.summary.setText(summary)


class SettingsPage(QScrollArea):
    def __init__(
        self,
        theme: ThemeManager,
        *,
        set_theme: Callable[[str], None],
        set_scale: Callable[[int], None],
        set_mode: Callable[[str], None],
        open_values: Callable[[], None],
    ) -> None:
        super().__init__()
        page, column = _page(theme, "settings-page", strings.SETTINGS_TITLE)
        self.setObjectName("settings-page")
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setWidget(page.takeWidget())
        self.setAccessibleName(strings.SETTINGS_TITLE)
        look, look_lay = _card(theme, strings.SETTINGS_APPEARANCE)
        form = QFormLayout()
        self.theme_combo = QComboBox()
        self.theme_combo.setObjectName("settings-theme")
        self.theme_combo.setAccessibleName(strings.SETTINGS_THEME)
        for key, text in THEMES:
            self.theme_combo.addItem(text, key)
        self.theme_combo.activated.connect(lambda i: set_theme(str(self.theme_combo.itemData(i))))
        self.scale_combo = QComboBox()
        self.scale_combo.setObjectName("settings-scale")
        self.scale_combo.setAccessibleName(strings.SETTINGS_SCALE)
        for pct in SCALES:
            self.scale_combo.addItem(f"{pct} %", pct)
        self.scale_combo.activated.connect(lambda i: set_scale(int(self.scale_combo.itemData(i))))
        form.addRow(strings.SETTINGS_THEME, self.theme_combo)
        form.addRow(strings.SETTINGS_SCALE, self.scale_combo)
        look_lay.addLayout(form)
        column.addWidget(look)
        edit, edit_lay = _card(theme, strings.SETTINGS_EDITOR)
        self.mode_combo = QComboBox()
        self.mode_combo.setObjectName("settings-mode")
        self.mode_combo.setAccessibleName(strings.SETTINGS_MODE)
        for key, text in MODES:
            self.mode_combo.addItem(text, key)
        self.mode_combo.activated.connect(lambda i: set_mode(str(self.mode_combo.itemData(i))))
        edit_form = QFormLayout()
        edit_form.addRow(strings.SETTINGS_MODE, self.mode_combo)
        edit_lay.addLayout(edit_form)
        column.addWidget(edit)
        proj, proj_lay = _card(theme, strings.SETTINGS_PROJECT)
        note = QLabel(strings.SETTINGS_PROJECT_TEXT)
        note.setWordWrap(True)
        note.setProperty("muted", True)
        proj_lay.addWidget(note)
        self.values_btn = QPushButton(strings.SETTINGS_PROJECT_BUTTON)
        self.values_btn.setObjectName("settings-values")
        self.values_btn.setAccessibleName(strings.SETTINGS_PROJECT_BUTTON.rstrip("…"))
        self.values_btn.clicked.connect(lambda _c=False: open_values())
        proj_lay.addWidget(self.values_btn, 0, Qt.AlignmentFlag.AlignLeft)
        column.addWidget(proj)
        column.addStretch(1)
        self._group = QButtonGroup(self)  # (keeps the page's controls in one tab group)

    def sync(self, *, theme_mode: str, scale: int, mode: str) -> None:
        """Show what the window has now (it changes through the menus, the palette and here)."""
        for combo, value in ((self.theme_combo, theme_mode), (self.scale_combo, scale), (self.mode_combo, mode)):  # fmt: skip
            i = combo.findData(value)
            if i >= 0 and combo.currentIndex() != i:
                combo.blockSignals(True)
                combo.setCurrentIndex(i)
                combo.blockSignals(False)
