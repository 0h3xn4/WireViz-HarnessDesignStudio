"""The library window: a window of its own, beside the editor, with the devices and subsystems of the
library folder (workshop feedback M4, D-175).

    win = LibraryWindow(ctl, theme, settings, parent=main_window)
    win.set_folder("/mnt/shared/harness-library")      # the setting is kept by the main window
    win.show()

Left, a search field, a filter (devices / subsystems) and the list of what the folder holds. Right,
a preview: the connectors and pins of a device, or the devices and connections of a subsystem. Below,
*Add to project* (one undo step, never replaces anything) with the number of these devices, and
*Save selection to library…* (the devices selected in the project). The window shares the editor's
controller, so an addition is an ordinary edit with undo; it is not modal, follows the theme, and
keeps its own size and place (`library/geometry`), apart from the editor's layout. The folder is
read in a helper thread (it may be on a slow drive); nothing is written unless the person saves.
The headless logic is in `core.library_folder`, `core.subsystem_library` and `core.copies`.
"""

from collections.abc import Callable
from pathlib import Path
from typing import Any

from PySide6.QtCore import QModelIndex, QSettings, Qt, Signal
from PySide6.QtGui import QAction, QCloseEvent, QKeySequence, QShowEvent
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QSplitter,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from harness_design_studio.core import copies, library_folder
from harness_design_studio.core import device_library as dl
from harness_design_studio.core import subsystem_library as sl
from harness_design_studio.core.commands import Op
from harness_design_studio.core.edit import EditError, clone_with
from harness_design_studio.core.errors import HarnessError
from harness_design_studio.core.library_folder import LibraryEntry, LibraryScan
from harness_design_studio.core.model import Project
from harness_design_studio.gui import strings
from harness_design_studio.gui.background import Job, JobRunner
from harness_design_studio.gui.controller import EditorController
from harness_design_studio.gui.devices_dialogs import _PlannerDialog
from harness_design_studio.gui.icons import icon_button
from harness_design_studio.gui.notice import InlineNotice
from harness_design_studio.gui.tables import Column, DictTableModel, TableView
from harness_design_studio.gui.theme import ThemeManager, mark_mono

SETTINGS_FOLDER = "library/folder"
SETTINGS_GEOMETRY = "library/geometry"
SETTINGS_SPLIT = "library/split"

_COUNT = {
    "connectors": strings.LIB_N_CONNECTORS,
    "pins": strings.LIB_N_PINS,
    "devices": strings.LIB_N_DEVICES,
    "connections": strings.LIB_N_CONNECTIONS,
}


def _n(kind: str, n: int) -> str:
    one, many = _COUNT[kind]
    return (one if n == 1 else many).format(n)


def contents_of(entry: LibraryEntry) -> str:
    """The Contents cell: what the entry holds, in words."""
    if entry.kind == "device":
        return f"{_n('connectors', entry.connectors)}, {_n('pins', entry.pins)}"
    return (
        f"{_n('devices', entry.devices)}, {_n('connectors', entry.connectors)}, "
        f"{_n('connections', entry.connections)}"
    )


# ---- save to the library --------------------------------------------------------------------


class SaveToLibraryDialog(_PlannerDialog):
    """Save the selected devices to the library folder: as devices, or as one subsystem with a
    name. The reason a save cannot be done shows under the fields; Save stays off until it can."""

    def __init__(
        self,
        parent: QWidget | None,
        theme: ThemeManager,
        project: Project,
        unit_ids: list[str],
        folder: str,
    ) -> None:
        super().__init__(parent, theme, strings.LIB_SAVE_TITLE, "library-save-dialog")
        self.project, self.unit_ids, self.folder = project, list(unit_ids), folder
        self.lay.addWidget(QLabel(strings.LIB_SAVE_SELECTED.format(", ".join(self.unit_ids))))
        self.as_devices = QRadioButton(strings.LIB_SAVE_AS_DEVICES)
        self.as_devices.setObjectName("library-save-devices")
        self.as_devices.setAccessibleName(strings.LIB_SAVE_AS_DEVICES)
        self.as_devices.setToolTip(strings.LIB_SAVE_AS_DEVICES_TIP)
        self.as_subsystem = QRadioButton(strings.LIB_SAVE_AS_SUBSYSTEM)
        self.as_subsystem.setObjectName("library-save-subsystem")
        self.as_subsystem.setAccessibleName(strings.LIB_SAVE_AS_SUBSYSTEM)
        self.as_subsystem.setToolTip(strings.LIB_SAVE_AS_SUBSYSTEM_TIP)
        many = len(self.unit_ids) > 1
        (self.as_subsystem if many else self.as_devices).setChecked(True)
        self.lay.addWidget(QLabel(strings.LIB_SAVE_AS))
        self.lay.addWidget(self.as_devices)
        self.lay.addWidget(self.as_subsystem)
        form = QFormLayout()
        self.name = QLineEdit()
        self.name.setObjectName("library-save-name")
        self.name.setAccessibleName(strings.LIB_SAVE_NAME)
        self.name.setToolTip(strings.LIB_SAVE_NAME_TIP)
        self.description = QLineEdit()
        self.description.setObjectName("library-save-description")
        self.description.setAccessibleName(strings.LIB_SAVE_DESCRIPTION)
        self.description.setToolTip(strings.LIB_SAVE_DESCRIPTION_TIP)
        form.addRow(strings.LIB_SAVE_NAME, self.name)
        form.addRow(strings.LIB_SAVE_DESCRIPTION, self.description)
        self.lay.addLayout(form)
        self.info = QLabel()
        self.info.setObjectName("library-save-info")
        self.info.setProperty("muted", True)
        self.info.setWordWrap(True)
        self.lay.addWidget(self.info)
        for w in (self.as_devices, self.as_subsystem):
            w.toggled.connect(self.revalidate)
        self.name.textChanged.connect(self.revalidate)
        self._finish(strings.LIB_SAVE_OK)
        if self.ok is not None:
            self.ok.setToolTip(strings.LIB_SAVE_OK_TIP)
            self.ok.setAccessibleName(strings.LIB_SAVE_OK)

    def is_subsystem(self) -> bool:
        return self.as_subsystem.isChecked()

    def check(self) -> str | None:
        subsystem = self.is_subsystem()
        self.name.setEnabled(subsystem)
        self.description.setEnabled(subsystem)
        kept = sl.connections_between(self.project, self.unit_ids)
        left = sl.left_out_connections(self.project, self.unit_ids)
        lines = []
        if subsystem:
            lines.append(strings.LIB_SAVE_KEPT.format(_n("connections", kept)))
        if left:
            lines.append(strings.LIB_SAVE_LEFT_OUT.format(_n("connections", left)))
        if subsystem and self.name.text().strip():
            lines.append(
                strings.LIB_SAVE_FILE.format(
                    sl.default_file_name(self.name.text().strip()), self.folder
                )
            )
        self.info.setText(" ".join(lines))
        if not subsystem:
            return None
        name = self.name.text().strip()
        if not name:
            return strings.LIB_SAVE_NEEDS_NAME
        if (Path(self.folder) / sl.default_file_name(name)).exists():
            return strings.LIB_SAVE_EXISTS.format(sl.default_file_name(name))
        return None


# ---- the window -----------------------------------------------------------------------------


class LibraryWindow(QWidget):
    """The non-modal library window (see the module text)."""

    folderChangeRequested = Signal()
    added = Signal(list)  # the IDs of the devices that were added to the project

    def __init__(
        self,
        ctl: EditorController,
        theme: ThemeManager,
        settings: QSettings,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent, Qt.WindowType.Window)
        self.ctl, self.theme, self.settings = ctl, theme, settings
        self.setObjectName("library-window")
        self.setWindowTitle(strings.LIB_TITLE)
        self.setAccessibleName(strings.LIB_TITLE)
        self.run_dialog: Callable[[QDialog], int] = lambda dlg: dlg.exec()
        self.jobs = JobRunner(ctl)
        self.jobs.done.connect(self._job_done)
        self.folder = str(settings.value(SETTINGS_FOLDER, "") or "")
        self.scan: LibraryScan | None = None
        self.entry: LibraryEntry | None = None
        self.entry_data: dict[str, Any] | None = None
        self._shown_once = False
        self._shown: list[LibraryEntry] = []
        self._build()
        ctl.selectionChanged.connect(self._update_buttons)
        ctl.stateChanged.connect(self._update_buttons)
        ctl.changed.connect(lambda _d: self._update_buttons())
        self.refresh()

    # ---- building -----------------------------------------------------------------------------
    def _build(self) -> None:
        theme = self.theme
        outer = QVBoxLayout(self)
        outer.setContentsMargins(theme.space(12), theme.space(12), theme.space(12), theme.space(12))
        outer.setSpacing(theme.space(8))
        head = QHBoxLayout()
        head.addWidget(QLabel(strings.LIB_FOLDER_LABEL))
        self.folder_label = QLabel()
        self.folder_label.setObjectName("library-folder")
        self.folder_label.setAccessibleName(strings.LIB_FOLDER_LABEL)
        self.folder_label.setToolTip(strings.LIB_FOLDER_TIP)
        self.folder_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        mark_mono(self.folder_label)
        head.addWidget(self.folder_label, 1)
        self.change_btn = QPushButton()
        self.change_btn.setObjectName("library-change")
        icon_button(
            self.change_btn, "folder-open", theme, strings.LIB_CHANGE_TIP, text=strings.LIB_CHANGE
        )
        self.change_btn.clicked.connect(self.folderChangeRequested.emit)
        self.refresh_btn = QPushButton()
        self.refresh_btn.setObjectName("library-refresh")
        icon_button(
            self.refresh_btn,
            "refresh",
            theme,
            strings.LIB_REFRESH_TIP,
            "F5",
            text=strings.LIB_REFRESH,
        )
        self.refresh_btn.clicked.connect(self.refresh)
        head.addWidget(self.change_btn)
        head.addWidget(self.refresh_btn)
        outer.addLayout(head)
        self.folder_notice = InlineNotice(theme)
        self.folder_notice.setObjectName("library-folder-notice")
        outer.addWidget(self.folder_notice)

        split = QSplitter(Qt.Orientation.Horizontal)
        split.setObjectName("library-split")
        split.setChildrenCollapsible(False)
        self.split = split
        # the list
        left = QWidget()
        lv = QVBoxLayout(left)
        lv.setContentsMargins(0, 0, 0, 0)
        row = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setObjectName("library-search")
        self.search.setAccessibleName(strings.LIB_SEARCH_NAME)
        self.search.setToolTip(strings.LIB_SEARCH_TIP)
        self.search.setPlaceholderText(strings.LIB_SEARCH_PLACEHOLDER)
        self.search.setClearButtonEnabled(True)
        self.kind = QComboBox()
        self.kind.setObjectName("library-kind")
        self.kind.setAccessibleName(strings.LIB_KIND_NAME)
        self.kind.setToolTip(strings.LIB_KIND_TIP)
        for key, text in (
            ("all", strings.LIB_KIND_ALL),
            ("device", strings.LIB_KIND_DEVICES),
            ("subsystem", strings.LIB_KIND_SUBSYSTEMS),
        ):
            self.kind.addItem(text, key)
        row.addWidget(self.search, 1)
        row.addWidget(self.kind)
        lv.addLayout(row)
        self.list_model = DictTableModel(
            [
                Column("kind", strings.LIB_COLUMNS[0], width=80),
                Column("id", strings.LIB_COLUMNS[1], mono=True, width=70),
                Column("name", strings.LIB_COLUMNS[2], width=160),
                Column("contents", strings.LIB_COLUMNS[3]),
            ],
            [],
            theme,
        )
        self.list = TableView(self.list_model, theme, name=strings.LIB_LIST_NAME)
        self.list.setObjectName("library-list")
        self.list.setToolTip(strings.LIB_LIST_TIP)
        self.list.setSelectionBehavior(TableView.SelectionBehavior.SelectRows)
        self.list.setSelectionMode(TableView.SelectionMode.SingleSelection)
        self.list.horizontalHeader().setStretchLastSection(True)
        self.empty_title = QLabel()
        self.empty_title.setObjectName("library-empty-title")
        self.empty_title.setProperty("heading", True)
        self.empty_title.setWordWrap(True)
        self.empty_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_hint = QLabel()
        self.empty_hint.setObjectName("library-empty-hint")
        self.empty_hint.setProperty("muted", True)
        self.empty_hint.setWordWrap(True)
        self.empty_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_choose = QPushButton(strings.LIB_EMPTY_CHOOSE)
        self.empty_choose.setObjectName("library-empty-choose")
        self.empty_choose.setAccessibleName(strings.LIB_EMPTY_CHOOSE.rstrip("…"))
        self.empty_choose.setToolTip(strings.A_LIBRARY_FOLDER_TIP)
        self.empty_choose.clicked.connect(self.folderChangeRequested.emit)
        empty = QWidget()
        empty.setObjectName("library-empty")
        ev = QVBoxLayout(empty)
        ev.addStretch(1)
        ev.addWidget(self.empty_title)
        ev.addWidget(self.empty_hint)
        ev.addWidget(self.empty_choose, 0, Qt.AlignmentFlag.AlignHCenter)
        ev.addStretch(2)
        self.list_stack = QStackedWidget()
        self.list_stack.addWidget(self.list)
        self.list_stack.addWidget(empty)
        lv.addWidget(self.list_stack, 1)
        split.addWidget(left)
        # the preview
        right = QWidget()
        rv = QVBoxLayout(right)
        rv.setContentsMargins(0, 0, 0, 0)
        self.preview_title = QLabel(strings.LIB_PREVIEW_NONE)
        self.preview_title.setObjectName("library-preview-title")
        self.preview_title.setProperty("title", True)
        self.preview_title.setWordWrap(True)
        self.preview_title.setAccessibleName(strings.LIB_PREVIEW_NAME)
        self.preview_text = QLabel()
        self.preview_text.setObjectName("library-preview-text")
        self.preview_text.setWordWrap(True)
        self.preview_text.setProperty("muted", True)
        self.preview_text.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.pin_model = DictTableModel(
            [
                Column("connector", strings.LIB_PREVIEW_PIN_COLUMNS[0], mono=True),
                Column("pin", strings.LIB_PREVIEW_PIN_COLUMNS[1], mono=True),
                Column("signal", strings.LIB_PREVIEW_PIN_COLUMNS[2], mono=True),
                Column("function", strings.LIB_PREVIEW_PIN_COLUMNS[3]),
            ],
            [],
            theme,
        )
        self.pin_table = TableView(self.pin_model, theme, name=strings.LIB_PREVIEW_TABLE_PINS)
        self.pin_table.setObjectName("library-preview-pins")
        self.pin_table.horizontalHeader().setStretchLastSection(True)
        self.sub_model = DictTableModel(
            [
                Column("kind", strings.LIB_PREVIEW_SUB_COLUMNS[0]),
                Column("item", strings.LIB_PREVIEW_SUB_COLUMNS[1], mono=True),
                Column("detail", strings.LIB_PREVIEW_SUB_COLUMNS[2]),
            ],
            [],
            theme,
        )
        self.sub_table = TableView(self.sub_model, theme, name=strings.LIB_PREVIEW_TABLE_SUB)
        self.sub_table.setObjectName("library-preview-subsystem")
        self.sub_table.horizontalHeader().setStretchLastSection(True)
        self.preview_stack = QStackedWidget()
        self.preview_stack.addWidget(self.pin_table)
        self.preview_stack.addWidget(self.sub_table)
        rv.addWidget(self.preview_title)
        rv.addWidget(self.preview_text)
        rv.addWidget(self.preview_stack, 1)
        split.addWidget(right)
        split.setStretchFactor(0, 4)
        split.setStretchFactor(1, 5)
        outer.addWidget(split, 1)

        self.result_notice = InlineNotice(theme)
        self.result_notice.setObjectName("library-result-notice")
        outer.addWidget(self.result_notice)
        buttons = QHBoxLayout()
        self.number = QSpinBox()
        self.number.setObjectName("library-number")
        self.number.setAccessibleName(strings.LIB_NUMBER)
        self.number.setToolTip(strings.LIB_NUMBER_TIP)
        self.number.setRange(1, copies.MAX_DEVICES)
        self.number.setValue(1)
        buttons.addWidget(QLabel(strings.LIB_NUMBER))
        buttons.addWidget(self.number)
        buttons.addStretch(1)
        self.save_btn = QPushButton()
        self.save_btn.setObjectName("library-save")
        icon_button(self.save_btn, "export", theme, strings.LIB_SAVE_TIP, text=strings.LIB_SAVE)
        self.add_btn = QPushButton()
        self.add_btn.setObjectName("library-add")
        self.add_btn.setProperty("primary", True)
        icon_button(self.add_btn, "plus", theme, strings.LIB_ADD_TIP, "Enter", text=strings.LIB_ADD)
        self.close_btn = QPushButton(strings.LIB_CLOSE)
        self.close_btn.setObjectName("library-close")
        self.close_btn.setAccessibleName(strings.LIB_CLOSE)
        self.close_btn.setToolTip(strings.LIB_CLOSE_TIP)
        buttons.addWidget(self.save_btn)
        buttons.addWidget(self.add_btn)
        buttons.addWidget(self.close_btn)
        outer.addLayout(buttons)

        self.save_btn.clicked.connect(self.save_flow)
        self.add_btn.clicked.connect(self.add_flow)
        self.close_btn.clicked.connect(self.close)
        self.search.textChanged.connect(self._fill_list)
        self.kind.currentIndexChanged.connect(lambda _i: self._fill_list())
        self.list.selectionModel().currentRowChanged.connect(self._row_changed)
        self.list.activated.connect(lambda _i: self.add_flow())
        find = QAction(self)
        find.setShortcut(QKeySequence("Ctrl+F"))
        find.triggered.connect(self._focus_search)
        self.addAction(find)
        leave = QAction(self)
        leave.setShortcut(QKeySequence("Esc"))
        leave.triggered.connect(self.close)
        self.addAction(leave)
        again = QAction(self)
        again.setShortcut(QKeySequence("F5"))
        again.triggered.connect(self.refresh)
        self.addAction(again)
        self.setTabOrder(self.search, self.kind)
        self.setTabOrder(self.kind, self.list)
        self.resize(theme.px(1120), theme.px(620))
        self._show_empty(strings.LIB_EMPTY_NO_FOLDER, strings.LIB_EMPTY_NO_FOLDER_HINT, True)

    def _focus_search(self) -> None:
        self.search.setFocus()
        self.search.selectAll()

    # ---- the folder -----------------------------------------------------------------------------
    def set_folder(self, folder: str) -> None:
        """Use another library folder ('' for none) and read it."""
        self.folder = folder
        self.refresh()

    def refresh(self) -> None:
        """Read the folder again (in a helper thread)."""
        self.folder_label.setText(self.folder or strings.LIB_FOLDER_NONE)
        self.folder_label.setProperty("muted", not self.folder)
        self.result_notice.clear()
        self.entry_data = None  # read again with the folder
        self.refresh_btn.setEnabled(bool(self.folder))
        if not self.folder:
            self.scan = None
            self._fill_list()
            return
        folder = self.folder
        self.jobs.start("library-scan", folder, lambda: library_folder.scan_folder(folder))

    def _job_done(self, job: Job) -> None:
        if job.kind == "library-scan":
            if job.key != self.folder:
                return  # an answer for a folder that is not chosen any more
            if job.error is not None:
                self.scan = LibraryScan(Path(self.folder), error=job.error)
            else:
                self.scan = job.value
            self._scan_ready()
        elif job.kind == "library-entry":
            if self.entry is None or job.key != self.entry.key:
                return
            self._entry_ready(job)

    def _scan_ready(self) -> None:
        scan = self.scan
        if scan is None:
            return
        if scan.error:
            self.folder_notice.show_notice("error", scan.error)
        elif scan.problems:
            self.folder_notice.show_notice(
                "warning",
                strings.LIB_DAMAGED.format(len(scan.problems)),
                details=[str(p) for p in scan.problems[:8]]
                + ([f"… +{len(scan.problems) - 8}"] if len(scan.problems) > 8 else []),
            )
        else:
            self.folder_notice.clear()
        self._fill_list()

    # ---- the list ---------------------------------------------------------------------------------
    def _wanted(self) -> list[LibraryEntry]:
        scan = self.scan
        if scan is None or scan.error:
            return []
        kind = str(self.kind.currentData())
        words = self.search.text().lower().split()
        out = []
        for e in scan.entries:
            if kind != "all" and e.kind != kind:
                continue
            hay = f"{e.id} {e.name} {e.description} {e.subsystem} {e.file}".lower()
            if all(w in hay for w in words):
                out.append(e)
        return out

    def _fill_list(self) -> None:
        wanted = self._wanted()
        self._shown = wanted
        keep = self.entry.key if self.entry is not None else None
        rows = [
            {
                "kind": strings.LIB_KIND_DEVICE
                if e.kind == "device"
                else strings.LIB_KIND_SUBSYSTEM,
                "id": e.id,
                "name": e.name,
                "contents": contents_of(e),
                "key": e.key,
            }
            for e in wanted
        ]
        self.list_model.set_rows(rows)
        scan = self.scan
        if wanted:
            self.list_stack.setCurrentIndex(0)
            row = next((i for i, e in enumerate(wanted) if e.key == keep), 0)
            self.list.selectRow(row)
            self._select(wanted[row])
        else:
            self._select(None)
            if scan is None:
                self._show_empty(
                    strings.LIB_EMPTY_NO_FOLDER, strings.LIB_EMPTY_NO_FOLDER_HINT, True
                )
            elif scan.error:
                self._show_empty(strings.LIB_EMPTY_UNREADABLE, scan.error, True)
            elif scan.entries:
                self._show_empty(strings.LIB_EMPTY_NOMATCH, strings.LIB_EMPTY_NOMATCH_HINT, False)
            else:
                self._show_empty(strings.LIB_EMPTY_FOLDER, strings.LIB_EMPTY_FOLDER_HINT, False)
        self._update_buttons()

    def _show_empty(self, title: str, hint: str, choose: bool) -> None:
        self.empty_title.setText(title)
        self.empty_hint.setText(hint)
        self.empty_choose.setVisible(choose)
        self.list_stack.setCurrentIndex(1)

    def _row_changed(self, current: QModelIndex, _previous: QModelIndex) -> None:
        if not current.isValid():
            return
        source = self.list.proxy.mapToSource(current)
        shown = self._shown
        if 0 <= source.row() < len(shown):
            self._select(shown[source.row()])

    def current_entry(self) -> LibraryEntry | None:
        return self.entry

    def select_entry(self, key: str) -> bool:
        """Choose the entry with this key in the list (for tests and after a save)."""
        for i, e in enumerate(self._shown):
            if e.key == key:
                self.list.selectRow(
                    self.list.proxy.mapFromSource(self.list_model.index(i, 0)).row()
                )
                self._select(e)
                return True
        return False

    # ---- the preview ------------------------------------------------------------------------------
    def _select(self, entry: LibraryEntry | None) -> None:
        same = entry is not None and self.entry is not None and entry.key == self.entry.key
        if same and self.entry_data is not None:
            return
        self.entry, self.entry_data = entry, None
        self.result_notice.clear()
        if entry is None:
            self.preview_title.setText(strings.LIB_PREVIEW_NONE)
            self.preview_text.setText("")
            self.pin_model.set_rows([])
            self.sub_model.set_rows([])
            self._update_buttons()
            return
        self.preview_title.setText(
            f"{entry.id}  {entry.name}".strip() if entry.kind == "device" else entry.name
        )
        self.preview_text.setText(strings.LIB_PREVIEW_LOADING)
        self.pin_model.set_rows([])
        self.sub_model.set_rows([])
        folder = self.folder

        def load() -> dict[str, Any]:
            return library_folder.load_entry(folder, entry)

        self.jobs.start("library-entry", entry.key, load)
        self._update_buttons()

    def _entry_ready(self, job: Job) -> None:
        entry = self.entry
        if entry is None:
            return
        if job.error is not None:
            self.preview_text.setText(strings.LIB_PREVIEW_ERROR.format(job.error))
            self.entry_data = None
            self._update_buttons()
            return
        data = job.value
        self.entry_data = data
        rows = library_folder.describe_entry(data, entry)
        if entry.kind == "device":
            self.pin_model.set_rows(rows)
            self.preview_stack.setCurrentWidget(self.pin_table)
            text = [contents_of(entry)]
        else:
            self.sub_model.set_rows(rows)
            self.preview_stack.setCurrentWidget(self.sub_table)
            text = [entry.description] if entry.description else []
            text.append(contents_of(entry))
            if data.get("notes"):
                text.append(str(data["notes"]))
        if entry.kind == "device" and entry.description:
            text.insert(0, entry.description)
        text.append(strings.LIB_FILE.format(entry.file))
        self.preview_text.setText("\n".join(text))
        self._update_buttons()

    # ---- buttons ----------------------------------------------------------------------------------
    def _update_buttons(self) -> None:
        entry = self.entry
        ready = entry is not None and self.entry_data is not None
        ro = self.ctl.read_only
        self.add_btn.setEnabled(ready and not ro)
        self.add_btn.setToolTip(
            strings.LIB_ADD_READ_ONLY
            if ro
            else strings.LIB_ADD_TIP
            if ready
            else strings.LIB_ADD_NONE
        )
        is_device = entry is not None and entry.kind == "device"
        self.number.setEnabled(is_device and not ro)
        self.number.setToolTip(
            strings.LIB_NUMBER_TIP if is_device or entry is None else strings.LIB_NUMBER_SUBSYSTEM
        )
        if not is_device:
            self.number.setValue(1)
        selected = self.ctl.selected_ids("unit")
        usable = bool(self.folder) and self.scan is not None and not self.scan.error
        self.save_btn.setEnabled(bool(selected) and usable)
        self.save_btn.setToolTip(
            strings.LIB_SAVE_NO_FOLDER
            if not usable
            else strings.LIB_SAVE_TIP
            if selected
            else strings.LIB_SAVE_NONE
        )

    # ---- add to the project -----------------------------------------------------------------------
    def plan_add(self) -> tuple[list[Op], list[str], str, list[str]]:
        """(ops, IDs of the new devices, the name of the undo step, notes) for the chosen entry and
        number. Raises a `HarnessError` (the sentence says what is wrong)."""
        entry, data = self.entry, self.entry_data
        if entry is None or data is None:
            raise EditError(strings.LIB_ADD_NONE)
        project = self.ctl.project
        if entry.kind == "subsystem":
            plan = sl.plan_subsystem_import(project, data)
            if not plan.ok:
                raise EditError(plan.problem)
            return (
                plan.ops,
                [r.new_id for r in plan.rows if r.ok],
                strings.STEP_LIB_ADD_SUBSYSTEM.format(plan.name),
                plan.notes,
            )
        device_plan = dl.plan_device_import(project, data, [entry.id])
        row = device_plan.rows[0] if device_plan.rows else None
        if row is None or not row.ok:
            raise EditError(f"{entry.id}: {row.message if row else strings.LIB_PREVIEW_ERROR}")
        ops = sl.with_placements(project, device_plan.ops)
        ids = [row.new_id]
        notes = list(device_plan.notes)
        count = int(self.number.value())
        if count > 1:
            more = copies.plan_copies(clone_with(project, ops), row.new_id, count)
            ops += more.ops
            ids += list(more.new_ids)
            if more.skipped:
                notes.append(strings.REDUNDANT_SKIPPED.format(len(more.skipped), ", ".join(more.skipped)).strip())  # fmt: skip
        return ops, ids, strings.STEP_LIB_ADD_DEVICE.format(", ".join(ids)), notes

    def add_flow(self) -> None:
        """Add to project: one undo step; the notice under the list says what was added."""
        if not self.add_btn.isEnabled():
            if self.ctl.read_only:
                self.ctl.refuse_read_only()
            return
        try:
            ops, ids, label, notes = self.plan_add()
        except HarnessError as exc:
            self.result_notice.show_notice("error", str(exc))
            return
        entry = self.entry
        if entry is None:
            return
        if entry.kind == "subsystem":
            n_conn = sum(1 for o in ops if getattr(o, "collection", "") == "links")
            message = strings.LIB_ADDED_SUBSYSTEM.format(
                entry.name, _n("devices", len(ids)), _n("connections", n_conn)
            )
        else:
            message = strings.LIB_ADDED.format(", ".join(ids))
        if not self.ctl.run(label, ops, message=message):
            return
        self.result_notice.show_notice("info", message, details=notes or None)
        if ids:
            self.ctl.select("unit", ids[0])
        self.added.emit(ids)

    # ---- save the selection -----------------------------------------------------------------------
    def save_flow(self) -> None:
        """Save selection to library…: asks devices or a subsystem, then writes into the folder."""
        selected = self.ctl.selected_ids("unit")
        if not selected or not self.folder:
            return
        dlg = SaveToLibraryDialog(self, self.theme, self.ctl.project, selected, self.folder)
        if self.run_dialog(dlg) != QDialog.DialogCode.Accepted:
            return
        try:
            if dlg.is_subsystem():
                name = dlg.name.text().strip()
                path = library_folder.save_subsystem(
                    self.folder, self.ctl.project, selected, name, dlg.description.text()
                )
                message = strings.LIB_SAVED_SUBSYSTEM.format(name, path.name)
            else:
                path = library_folder.save_devices(self.folder, self.ctl.project, selected)
                message = strings.LIB_SAVED_DEVICES.format(", ".join(selected), path.name)
        except (HarnessError, OSError) as exc:
            text = str(exc) if isinstance(exc, HarnessError) else str(exc.strerror or exc)
            self.result_notice.show_notice("error", text)
            return
        self.refresh()
        self.result_notice.show_notice("info", message)

    # ---- the window's own place ---------------------------------------------------------------------
    def showEvent(self, event: QShowEvent) -> None:  # noqa: N802
        super().showEvent(event)
        if not self._shown_once:
            self._shown_once = True
            geometry = self.settings.value(SETTINGS_GEOMETRY)
            if geometry is not None:
                self.restoreGeometry(geometry)
            sizes = self.settings.value(SETTINGS_SPLIT)
            if isinstance(sizes, list) and len(sizes) == 2:
                self.split.setSizes([int(s) for s in sizes])
            else:
                total = max(self.split.width(), 1)
                self.split.setSizes([total // 2, total // 2])
        self.search.setFocus()

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        self.settings.setValue(SETTINGS_GEOMETRY, self.saveGeometry())
        self.settings.setValue(SETTINGS_SPLIT, self.split.sizes())
        self.jobs.wait_idle(500)  # (a thread must not outlive the window that started it)
        super().closeEvent(event)
