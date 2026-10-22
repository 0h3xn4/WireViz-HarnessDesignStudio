"""The Settings area: appearance, editing, the project's values, keyboard shortcuts, About, Licences.

    page = SettingsPage(theme, set_workspace=..., set_theme=..., set_scale=..., set_reduce_motion=..., set_mode=...,
                        set_snap=..., set_labels=..., open_values=..., shortcut_rows=...,
                        settings_file="...")
    page.sync(theme_mode="dark", scale=125, mode="expert", workspace="full", reduce_motion=False, snap=True, labels=False)

The page only shows and calls back; the window changes the setting, stores it and applies it at once
(`MainWindow.set_theme_mode`, `set_scale`, `set_reduce_motion` ...). Every control here has a twin in
a menu or on Ctrl+K, so `sync` follows whatever changed it. A section list on the left, the section
on the right.
"""

import platform
from collections.abc import Callable

from PySide6 import __version__ as pyside_version
from PySide6.QtCore import QModelIndex, Qt, qVersion
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from harness_design_studio import __version__
from harness_design_studio.gui import licences, strings
from harness_design_studio.gui.empty_state import attach_empty_state
from harness_design_studio.gui.tables import Column, DictTableModel, TableView
from harness_design_studio.gui.theme import ThemeManager, mark_mono

SCALES = (100, 125, 150, 200)
THEMES = (
    ("system", strings.SETTINGS_THEME_SYSTEM),
    ("light", strings.SETTINGS_THEME_LIGHT),
    ("dark", strings.SETTINGS_THEME_DARK),
)
MODES = (("guided", strings.GUIDED), ("expert", strings.EXPERT))
WORKSPACES = (("simple", strings.WORKSPACE_SIMPLE), ("full", strings.WORKSPACE_FULL))
SECTIONS = (
    ("appearance", strings.SETTINGS_SECTION_APPEARANCE),
    ("editing", strings.SETTINGS_SECTION_EDITING),
    ("project", strings.SETTINGS_SECTION_PROJECT),
    ("shortcuts", strings.SETTINGS_SECTION_SHORTCUTS),
    ("about", strings.SETTINGS_SECTION_ABOUT),
    ("licences", strings.SETTINGS_SECTION_LICENCES),
)


def _section(
    theme: ThemeManager, key: str, title: str, *, wide: bool = False
) -> tuple[QScrollArea, QVBoxLayout]:
    """One scrolling section: a title and a column that is never wider than a readable line (a
    section that holds a table takes all the width there is, up to 900 px)."""
    scroll = QScrollArea()
    scroll.setObjectName(f"settings-section-{key}")
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QFrame.Shape.NoFrame)
    scroll.setAccessibleName(title)
    body = QWidget()
    outer = QHBoxLayout(body)
    outer.setContentsMargins(theme.space(24), theme.space(24), theme.space(24), theme.space(24))
    column = QVBoxLayout()
    column.setSpacing(theme.space(12))
    outer.addLayout(column, 1)
    if not wide:
        outer.addStretch(1)
    heading = QLabel(title)
    heading.setProperty("title", True)
    column.addWidget(heading)
    scroll.setWidget(body)
    body.setMaximumWidth(theme.px(900))
    return scroll, column


def _muted(text: str) -> QLabel:
    label = QLabel(text)
    label.setWordWrap(True)
    label.setProperty("muted", True)
    return label


def _check(text: str, tip: str, object_name: str) -> QCheckBox:
    box = QCheckBox(text)
    box.setObjectName(object_name)
    box.setAccessibleName(text)
    box.setToolTip(tip)
    return box


class SettingsPage(QWidget):
    def __init__(
        self,
        theme: ThemeManager,
        *,
        set_workspace: Callable[[str], None],
        set_theme: Callable[[str], None],
        set_scale: Callable[[int], None],
        set_reduce_motion: Callable[[bool], None],
        set_mode: Callable[[str], None],
        set_snap: Callable[[bool], None],
        set_labels: Callable[[bool], None],
        open_values: Callable[[], None],
        shortcut_rows: Callable[[], list[tuple[str, str]]],
        settings_file: str = "",
    ) -> None:
        super().__init__()
        self.theme = theme
        self._shortcut_rows = shortcut_rows
        self.setObjectName("settings-page")
        self.setAccessibleName(strings.SETTINGS_TITLE)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        self.sections = QListWidget()
        self.sections.setObjectName("settings-sections")
        self.sections.setAccessibleName(strings.SETTINGS_SECTIONS_NAME)
        self.sections.setFixedWidth(theme.px(200))
        self.sections.setProperty("nav", True)
        self.stack = QStackedWidget()
        self.stack.setObjectName("settings-stack")
        lay.addWidget(self.sections)
        lay.addWidget(self.stack, 1)
        self._keys: list[str] = []
        self.pages: dict[str, QScrollArea] = {}

        # ---- appearance
        page, col = self._add("appearance")
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
        self.scale_combo.setToolTip(strings.SETTINGS_SCALE_HINT)
        for pct in SCALES:
            self.scale_combo.addItem(f"{pct} %", pct)
        self.scale_combo.activated.connect(lambda i: set_scale(int(self.scale_combo.itemData(i))))
        form.addRow(strings.SETTINGS_THEME, self.theme_combo)
        form.addRow(strings.SETTINGS_SCALE, self.scale_combo)
        col.addLayout(form)
        col.addWidget(_muted(strings.SETTINGS_SCALE_HINT))
        self.motion_box = _check(
            strings.SETTINGS_REDUCE_MOTION,
            strings.SETTINGS_REDUCE_MOTION_TIP,
            "settings-reduce-motion",
        )
        self.motion_box.clicked.connect(lambda on: set_reduce_motion(bool(on)))
        col.addWidget(self.motion_box)
        col.addWidget(_muted(strings.SETTINGS_REDUCE_MOTION_TIP))
        col.addStretch(1)

        # ---- editing
        page, col = self._add("editing")
        self.workspace_combo = QComboBox()
        self.workspace_combo.setObjectName("settings-workspace")
        self.workspace_combo.setAccessibleName(strings.SETTINGS_WORKSPACE)
        self.workspace_combo.setToolTip(strings.SETTINGS_WORKSPACE_HINT)
        for key, text in WORKSPACES:
            self.workspace_combo.addItem(text, key)
        self.workspace_combo.activated.connect(
            lambda i: set_workspace(str(self.workspace_combo.itemData(i)))
        )
        workspace_form = QFormLayout()
        workspace_form.addRow(strings.SETTINGS_WORKSPACE, self.workspace_combo)
        col.addLayout(workspace_form)
        col.addWidget(_muted(strings.SETTINGS_WORKSPACE_HINT))
        self.mode_combo = QComboBox()
        self.mode_combo.setObjectName("settings-mode")
        self.mode_combo.setAccessibleName(strings.SETTINGS_MODE)
        for key, text in MODES:
            self.mode_combo.addItem(text, key)
        self.mode_combo.activated.connect(lambda i: set_mode(str(self.mode_combo.itemData(i))))
        edit_form = QFormLayout()
        edit_form.addRow(strings.SETTINGS_MODE, self.mode_combo)
        col.addLayout(edit_form)
        self.snap_box = _check(strings.SETTINGS_SNAP, strings.SETTINGS_SNAP_TIP, "settings-snap")
        self.snap_box.clicked.connect(lambda on: set_snap(bool(on)))
        self.labels_box = _check(
            strings.SETTINGS_LABELS, strings.SETTINGS_LABELS_TIP, "settings-labels"
        )
        self.labels_box.clicked.connect(lambda on: set_labels(bool(on)))
        col.addWidget(self.snap_box)
        col.addWidget(_muted(strings.SETTINGS_SNAP_TIP))
        col.addWidget(self.labels_box)
        col.addWidget(_muted(strings.SETTINGS_LABELS_TIP))
        col.addStretch(1)

        # ---- project
        page, col = self._add("project")
        col.addWidget(_muted(strings.SETTINGS_PROJECT_TEXT))
        self.values_btn = QPushButton(strings.SETTINGS_PROJECT_BUTTON)
        self.values_btn.setObjectName("settings-values")
        self.values_btn.setAccessibleName(strings.SETTINGS_PROJECT_BUTTON.rstrip("…"))
        self.values_btn.clicked.connect(lambda _c=False: open_values())
        col.addWidget(self.values_btn, 0, Qt.AlignmentFlag.AlignLeft)
        col.addStretch(1)

        # ---- shortcuts
        page, col = self._add("shortcuts", wide=True)
        col.addWidget(_muted(strings.SETTINGS_SHORTCUTS_TEXT))
        self.shortcut_filter = QLineEdit()
        self.shortcut_filter.setObjectName("settings-shortcut-filter")
        self.shortcut_filter.setAccessibleName(strings.SETTINGS_SHORTCUTS_FILTER_NAME)
        self.shortcut_filter.setPlaceholderText(strings.SETTINGS_SHORTCUTS_FILTER)
        self.shortcut_filter.setClearButtonEnabled(True)
        col.addWidget(self.shortcut_filter)
        self.shortcut_model = DictTableModel(
            [
                Column("action", strings.SHORTCUT_COLUMNS[0]),
                Column("keys", strings.SHORTCUT_COLUMNS[1], mono=True),
            ],
            [],
            theme,
        )
        self.shortcut_table = TableView(
            self.shortcut_model, theme, name=strings.SHORTCUTS_TABLE_NAME
        )
        self.shortcut_table.setObjectName("settings-shortcuts")
        self.shortcut_filter.textChanged.connect(self.shortcut_table.proxy.set_text)
        attach_empty_state(
            self.shortcut_table, strings.SHORTCUTS_EMPTY, strings.SHORTCUTS_EMPTY_HINT
        )
        self.shortcut_table.setMinimumHeight(theme.px(320))
        col.addWidget(self.shortcut_table, 1)

        # ---- about
        page, col = self._add("about")
        name = QLabel(strings.ABOUT_TITLE)
        name.setProperty("title", True)
        col.addWidget(name)
        self.version_label = QLabel(strings.ABOUT_VERSION.format(__version__))
        self.version_label.setObjectName("settings-version")
        mark_mono(self.version_label)
        col.addWidget(self.version_label)
        col.addWidget(_muted(strings.ABOUT_OFFLINE))
        self.runtime_label = QLabel(
            strings.ABOUT_RUNTIME.format(platform.python_version(), qVersion(), pyside_version)
        )
        self.runtime_label.setObjectName("settings-runtime")
        col.addWidget(self.runtime_label)
        self.file_label = QLabel(strings.ABOUT_SETTINGS_FILE.format(settings_file))
        self.file_label.setObjectName("settings-file")
        self.file_label.setWordWrap(True)
        self.file_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.file_label.setVisible(bool(settings_file))
        col.addWidget(self.file_label)
        col.addWidget(_muted(strings.ABOUT_LICENCE_PROJECT))
        col.addStretch(1)

        # ---- licences
        page, col = self._add("licences", wide=True)
        col.addWidget(_muted(strings.LICENCES_TEXT))
        self.licence_model = DictTableModel(
            [
                Column("name", strings.LICENCE_COLUMNS[0]),
                Column("licence", strings.LICENCE_COLUMNS[1]),
                Column("use", strings.LICENCE_COLUMNS[2]),
            ],
            [{"name": c.name, "licence": c.licence, "use": c.use} for c in licences.entries()],
            theme,
        )
        self.licence_table = TableView(self.licence_model, theme, name=strings.LICENCES_TABLE_NAME)
        self.licence_table.setObjectName("settings-licences")
        self.licence_table.setSelectionBehavior(TableView.SelectionBehavior.SelectRows)
        self.licence_table.setSelectionMode(TableView.SelectionMode.SingleSelection)
        self.licence_table.setMaximumHeight(theme.px(160))
        self.licence_table.horizontalHeader().setStretchLastSection(True)
        col.addWidget(self.licence_table)
        self.licence_text = QPlainTextEdit()
        self.licence_text.setObjectName("settings-licence-text")
        self.licence_text.setAccessibleName(strings.LICENCES_TEXT_NAME)
        self.licence_text.setReadOnly(True)
        mark_mono(self.licence_text)
        self.licence_text.setMinimumHeight(theme.px(240))
        col.addWidget(self.licence_text, 1)
        self.licence_table.selectionModel().currentRowChanged.connect(self._licence_picked)

        for _key, text in SECTIONS:
            self.sections.addItem(text)
        self.sections.currentRowChanged.connect(self._section_changed)
        self.sections.setCurrentRow(0)
        self.show_licence("inter")

    # ---- sections -------------------------------------------------------------------------------
    def _add(self, key: str, *, wide: bool = False) -> tuple[QScrollArea, QVBoxLayout]:
        title = dict(SECTIONS)[key]
        scroll, column = _section(self.theme, key, title, wide=wide)
        self.stack.addWidget(scroll)
        self.pages[key] = scroll
        self._keys.append(key)
        return scroll, column

    def show_section(self, key: str) -> None:
        self.sections.setCurrentRow(self._keys.index(key))

    def current_section(self) -> str:
        return self._keys[self.stack.currentIndex()]

    def _section_changed(self, row: int) -> None:
        if row < 0:
            return
        self.stack.setCurrentIndex(row)
        if self._keys[row] == "shortcuts":
            self.refresh_shortcuts()

    def showEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        super().showEvent(event)
        if self.current_section() == "shortcuts":
            self.refresh_shortcuts()

    def refresh_shortcuts(self) -> None:
        """Read the window's actions again (they change with the project and the mode)."""
        rows = [{"action": a, "keys": k} for a, k in self._shortcut_rows()]
        rows += [{"action": a, "keys": k} for a, k in strings.SHORTCUTS_EXTRA]
        self.shortcut_model.set_rows(rows)

    # ---- licences -------------------------------------------------------------------------------
    def _licence_picked(self, current: QModelIndex, _previous: QModelIndex) -> None:
        if not current.isValid():
            return
        source = self.licence_table.proxy.mapToSource(current)
        self.show_licence(licences.entries()[source.row()].key)

    def show_licence(self, key: str) -> None:
        self.licence_text.setPlainText(licences.text_of(key))

    # ---- follow the window ----------------------------------------------------------------------
    def sync(
        self,
        *,
        theme_mode: str,
        scale: int,
        mode: str,
        workspace: str,
        reduce_motion: bool,
        snap: bool,
        labels: bool,
    ) -> None:
        """Show what the window has now (it changes through the menus, the palette and here)."""
        for combo, value in ((self.theme_combo, theme_mode), (self.scale_combo, scale), (self.mode_combo, mode), (self.workspace_combo, workspace)):  # fmt: skip
            i = combo.findData(value)
            if i >= 0 and combo.currentIndex() != i:
                combo.blockSignals(True)
                combo.setCurrentIndex(i)
                combo.blockSignals(False)
        for box, value in ((self.motion_box, reduce_motion), (self.snap_box, snap), (self.labels_box, labels)):  # fmt: skip
            if box.isChecked() != value:
                box.blockSignals(True)
                box.setChecked(value)
                box.blockSignals(False)
