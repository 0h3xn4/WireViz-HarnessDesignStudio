"""One dialog for a new project: folder, name and what to start from, with the problems said next
to the field. It replaces the chain "choose folder", "type the name" and (for an example) "choose
the example" of three separate pop-ups.

    dlg = NewProjectDialog(theme, parent)
    if dlg.exec() == QDialog.DialogCode.Accepted:
        request = dlg.request()        # NewProjectRequest(folder, name, template)

The dialog only collects and checks the three answers; the window creates the project (for the
template "blank" with `ctl.new_project(folder, name)`, otherwise with
`core.templates.create_project(folder, template, name)` and then opens the folder), so everything
that can fail there still reports through the window.
"""

import os
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QModelIndex, Qt
from PySide6.QtGui import QStandardItem, QStandardItemModel
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListView,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from harness_design_studio.core.templates import TEMPLATES, TemplateInfo
from harness_design_studio.gui import icons, strings
from harness_design_studio.gui.theme import ThemeManager, mark_mono

BLANK = "blank"  # the template that is the plain "New project"
MAX_NAME = 200  # as `ProjectMeta.name`
AskFolder = Callable[[str], str | None]


@dataclass(frozen=True)
class NewProjectRequest:
    """What the person asked for; the folder does not exist yet or is empty."""

    folder: Path
    name: str
    template: str  # a name in `core.templates.TEMPLATES`; "blank" is the empty project

    @property
    def is_blank(self) -> bool:
        return self.template == BLANK


def _ask_folder(title: str) -> str | None:
    path = QFileDialog.getExistingDirectory(None, title)
    return path or None


def check_folder(text: str) -> str:
    """Why a folder cannot take a new project, in a sentence ("" when it can). The folder may not
    exist yet; then the nearest folder above it that exists must be writable."""
    text = text.strip()
    if not text:
        return strings.NP_ERR_FOLDER_NONE
    folder = Path(text).expanduser()
    if folder.is_symlink():
        return strings.NP_ERR_FOLDER_LINK
    if folder.exists():
        if not folder.is_dir():
            return strings.NP_ERR_FOLDER_FILE
        if (folder / "project.json").exists():
            return strings.FOLDER_HAS_PROJECT
        if any(folder.iterdir()):
            return strings.CHOOSE_EMPTY_NEW
    base = folder
    while not base.exists() and base != base.parent:
        base = base.parent
    if not base.is_dir() or not os.access(base, os.W_OK | os.X_OK):
        return strings.NP_ERR_FOLDER_WRITE.format(base)
    return ""


def check_name(text: str) -> str:
    """Why a project name cannot be used ("" when it can)."""
    name = text.strip()
    if not name:
        return strings.NP_ERR_NAME_NONE
    if len(name) > MAX_NAME:
        return strings.NP_ERR_NAME_LONG.format(len(name))
    if any(ord(c) < 32 or ord(c) == 127 for c in name):
        return strings.NP_ERR_NAME_CHARS
    return ""


def template_title(info: TemplateInfo) -> str:
    return strings.NP_EMPTY_TITLE if info.name == BLANK else info.title


class NewProjectDialog(QDialog):
    """Folder, name and starting point of a new project, checked as you type."""

    def __init__(
        self,
        theme: ThemeManager,
        parent: QWidget | None = None,
        *,
        ask_folder: AskFolder | None = None,
        start_folder: str | Path | None = None,
        template: str = BLANK,
    ) -> None:
        super().__init__(parent)
        self.theme = theme
        self.ask_folder: AskFolder = ask_folder or _ask_folder
        self.setObjectName("new-project-dialog")
        self.setWindowTitle(strings.NP_TITLE)
        self.setAccessibleName(strings.NP_ACCESSIBLE)
        self.setMinimumWidth(theme.px(560))
        self._name_typed = False
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel(f"<h3>{strings.NP_TITLE}</h3>"))
        form = QFormLayout()
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        # folder
        self.folder = QLineEdit(str(start_folder) if start_folder else "")
        self.folder.setObjectName("new-folder")
        self.folder.setAccessibleName(strings.NP_FOLDER)
        self.folder.setToolTip(strings.NP_FOLDER_TIP)
        mark_mono(self.folder)
        self.browse = QPushButton()
        self.browse.setObjectName("new-browse")
        icons.icon_button(self.browse, "folder-open", theme, strings.NP_BROWSE_TIP, text=strings.NP_BROWSE)  # fmt: skip
        self.browse.setToolTip(strings.NP_BROWSE_TIP)
        row = QHBoxLayout()
        row.addWidget(self.folder, 1)
        row.addWidget(self.browse)
        self.folder_error = self._error_label("new-folder-error")
        col = QVBoxLayout()
        col.addLayout(row)
        col.addWidget(self.folder_error)
        form.addRow(strings.NP_FOLDER, col)
        # name
        self.name = QLineEdit()
        self.name.setObjectName("new-name")
        self.name.setAccessibleName(strings.NP_NAME)
        self.name.setToolTip(strings.NP_NAME_TIP)
        self.name_error = self._error_label("new-name-error")
        col2 = QVBoxLayout()
        col2.addWidget(self.name)
        col2.addWidget(self.name_error)
        form.addRow(strings.NP_NAME, col2)
        # what to start from
        self.templates = QListView()
        self.templates.setObjectName("new-template")
        self.templates.setAccessibleName(strings.NP_TEMPLATE_NAME)
        self.templates.setToolTip(strings.NP_TEMPLATE_TIP)
        self.templates.setEditTriggers(QListView.EditTrigger.NoEditTriggers)
        self.templates.setMinimumHeight(theme.px(130))
        self.model = QStandardItemModel(self.templates)
        for info in TEMPLATES:
            item = QStandardItem(template_title(info))
            item.setData(info.name, Qt.ItemDataRole.UserRole)
            item.setToolTip(info.summary)
            item.setEditable(False)
            self.model.appendRow(item)
        self.templates.setModel(self.model)
        self.summary = QLabel()
        self.summary.setObjectName("new-template-summary")
        self.summary.setWordWrap(True)
        self.summary.setProperty("muted", True)
        col3 = QVBoxLayout()
        col3.addWidget(self.templates)
        col3.addWidget(self.summary)
        form.addRow(strings.NP_TEMPLATE, col3)
        lay.addLayout(form)
        # buttons and the hint that says what is missing
        self.hint = QLabel()
        self.hint.setObjectName("new-hint")
        self.hint.setWordWrap(True)
        self.hint.setProperty("muted", True)
        lay.addWidget(self.hint)
        buttons = QHBoxLayout()
        buttons.addStretch(1)
        self.cancel = QPushButton(strings.CANCEL)
        self.cancel.setObjectName("new-cancel")
        self.cancel.setToolTip(f"{strings.CANCEL} (Esc)")
        self.ok = QPushButton()
        self.ok.setObjectName("new-create")
        icons.icon_button(self.ok, "export", theme, strings.NP_CREATE_TIP, text=strings.NP_CREATE, role="on-primary")  # fmt: skip
        self.ok.setToolTip(strings.NP_CREATE_TIP)
        self.ok.setProperty("primary", True)
        self.ok.setDefault(True)
        buttons.addWidget(self.cancel)
        buttons.addWidget(self.ok)
        lay.addLayout(buttons)
        # wiring
        self.browse.clicked.connect(self.choose_folder)
        self.folder.textChanged.connect(self._folder_changed)
        self.name.textEdited.connect(self._name_edited)
        self.name.textChanged.connect(self._validate)
        sel = self.templates.selectionModel()
        if sel is not None:
            sel.currentChanged.connect(self._template_changed)
        self.cancel.clicked.connect(self.reject)
        self.ok.clicked.connect(self.accept)
        self.select_template(template)
        self._folder_changed(self.folder.text())  # a start folder gives the first name

    def _error_label(self, name: str) -> QLabel:
        label = QLabel()
        label.setObjectName(name)
        label.setWordWrap(True)
        label.setProperty("error", True)
        label.hide()
        return label

    # ---- the three answers ----------------------------------------------------------------------

    def choose_folder(self) -> None:
        picked = self.ask_folder(strings.NEW_FOLDER)
        if picked:
            self.folder.setText(picked)

    def _folder_changed(self, text: str) -> None:
        if not self._name_typed:  # until the name is typed, it follows the folder (as before)
            stem = Path(text.strip()).name if text.strip() else ""
            self.name.blockSignals(True)
            self.name.setText(stem)
            self.name.blockSignals(False)
        self._validate()

    def _name_edited(self, _text: str) -> None:
        self._name_typed = True

    def select_template(self, name: str) -> bool:
        for r in range(self.model.rowCount()):
            if self.model.item(r).data(Qt.ItemDataRole.UserRole) == name:
                self.templates.setCurrentIndex(self.model.index(r, 0))
                self._template_changed(self.model.index(r, 0))
                return True
        return False

    def template(self) -> str:
        index = self.templates.currentIndex()
        return str(index.data(Qt.ItemDataRole.UserRole)) if index.isValid() else BLANK

    def _template_changed(self, index: QModelIndex, _previous: QModelIndex | None = None) -> None:
        info = next((t for t in TEMPLATES if t.name == index.data(Qt.ItemDataRole.UserRole)), None)
        self.summary.setText(info.summary if info is not None else "")

    # ---- checking -------------------------------------------------------------------------------

    def errors(self) -> dict[str, str]:
        """The problems by field ("folder", "name"); empty when the answers can be used."""
        found = {"folder": check_folder(self.folder.text()), "name": check_name(self.name.text())}
        return {k: v for k, v in found.items() if v}

    def _validate(self) -> None:
        errors = self.errors()
        typed = bool(self.folder.text().strip())
        # an untouched empty folder field is not an error yet, only a missing answer
        shown_folder = errors.get("folder", "") if typed else ""
        shown_name = errors.get("name", "") if self._name_typed or typed else ""
        for label, text in ((self.folder_error, shown_folder), (self.name_error, shown_name)):
            label.setText(text)
            label.setVisible(bool(text))
        self.folder.setProperty("invalid", bool(shown_folder))
        self.name.setProperty("invalid", bool(shown_name))
        for w in (self.folder, self.name):
            w.style().unpolish(w)
            w.style().polish(w)
        missing = []
        if "folder" in errors:
            missing.append(strings.NP_HINT_FOLDER if not typed else strings.NP_HINT_FOLDER_FIX)
        if "name" in errors:
            missing.append(strings.NP_HINT_NAME if not self.name.text().strip() else strings.NP_HINT_NAME_FIX)  # fmt: skip
        self.hint.setText(strings.NP_HINT_HEAD.format("; ".join(missing)) if missing else "")
        self.hint.setVisible(bool(missing))
        self.ok.setEnabled(not errors)
        self.ok.setToolTip(strings.NP_CREATE_TIP if not errors else self.hint.text())

    def request(self) -> NewProjectRequest | None:
        """The answers, or None while a problem is shown."""
        if self.errors():
            return None
        return NewProjectRequest(
            Path(self.folder.text().strip()).expanduser(), self.name.text().strip(), self.template()
        )
