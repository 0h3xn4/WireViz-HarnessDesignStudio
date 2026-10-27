"""Export: one dialog for choosing, running and reading the result of an export of the outputs.

    dlg = ExportDialog(ctl, theme, parent, settings=settings)
    dlg.exported.connect(window.after_export)      # ExportResult: files are on disk
    dlg.exec()                                     # or: result = dlg.run()  (blocking, no window)

What it shows, left to right and top to bottom: the output folder (read-only: the project's
`outputs` folder), what the export writes as a tree of harnesses x document types, and on the right
the progress with Cancel and then the list of files written (path, document, harness, size) with
Reveal in folder, Open and a picture of the selected drawing.

The export ALWAYS writes the full set of the harnesses (`core.outputs.build.write_outputs` deletes
the files that are not in the new set and the independent check expects every harness, see
`tests/test_outputs_subset.py`). The one choice is the check box "Include the PDF drawings" (decision
D-169: the build workbook is the main output, the PDF and SVG drawings are optional): it is ticked
at the start when the folder's last export had drawings (`drawings_exported`), else not, and the
tree shows the drawing documents only while it is ticked. The tick marks in the tree choose only
what the result list shows and what "Copy selection to folder..." copies; all are ticked at the start.

The build and its independent check run in `OutputsWorker` (the window's own worker) off the UI
thread; the files are written on the UI thread exactly as `MainWindow.export_flow` does. A failed
check or a write error is an inline notice that stays (never a pop-up); nothing is written then.
"""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QEventLoop, QItemSelectionModel, QSettings, Qt, QUrl, Signal
from PySide6.QtGui import (
    QDesktopServices,
    QKeySequence,
    QShortcut,
    QStandardItem,
    QStandardItemModel,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QSplitter,
    QStackedWidget,
    QTreeView,
    QVBoxLayout,
    QWidget,
)

from harness_design_studio.core import edit, recovery
from harness_design_studio.core.errors import HarnessError
from harness_design_studio.core.io.fs import atomic_write_bytes
from harness_design_studio.core.model import Project
from harness_design_studio.core.outputs import drawing, system
from harness_design_studio.core.outputs.build import (
    MANIFEST,
    OutputSet,
    drawings_exported,
    write_outputs,
)
from harness_design_studio.core.outputs.canvas import Sheet
from harness_design_studio.core.outputs.stamp import Stamp
from harness_design_studio.core.verify import VerifyReport
from harness_design_studio.gui import export_docs, icons, strings
from harness_design_studio.gui.controller import EditorController
from harness_design_studio.gui.export_docs import Document
from harness_design_studio.gui.notice import InlineNotice
from harness_design_studio.gui.preview import SheetView
from harness_design_studio.gui.states import StateChip
from harness_design_studio.gui.tables import Column, DictTableModel, TableView
from harness_design_studio.gui.theme import ThemeManager, mark_mono

if TYPE_CHECKING:
    from harness_design_studio.gui.main_window import OutputsWorker

Opener = Callable[[QUrl], bool]
AskFolder = Callable[[str], str | None]
_LAST = {
    "none": strings.EXP_LAST_NONE,
    "current": strings.EXP_LAST_CURRENT,
    "stale": strings.EXP_LAST_STALE,
    "modified": strings.EXP_LAST_MODIFIED,
    "unreadable": strings.EXP_LAST_UNREADABLE,
}
MAX_DETAILS = 6  # problems of a failed check listed in the notice


def default_worker(project: Project) -> OutputsWorker:
    """The window's `OutputsWorker` (imported late: the main window imports this module)."""
    from harness_design_studio.gui.main_window import OutputsWorker

    return OutputsWorker(project)


def _ask_folder(title: str) -> str | None:
    path = QFileDialog.getExistingDirectory(None, title)
    return path or None


def human_size(n: int) -> str:
    """ "512 B", "12.3 kB", "1.4 MB" (decimal, as file managers show)."""
    if n < 1000:
        return f"{n} B"
    if n < 1_000_000:
        return f"{n / 1000:.1f} kB"
    return f"{n / 1_000_000:.1f} MB"


def reveal_url(path: Path) -> QUrl:
    """The URL that shows `path` in the file manager: its folder (a folder shows itself). Linux
    file managers have no portable "select this file", so the folder is opened."""
    folder = path if path.is_dir() else path.parent
    return QUrl.fromLocalFile(str(folder))


def open_url(path: Path) -> QUrl:
    """The URL that opens `path` with the program the system uses for it."""
    return QUrl.fromLocalFile(str(path))


# The only kinds of file the program writes to an outputs folder. Open hands a file to the system,
# which would run a script or a shortcut that someone put in a shared project.
OPENABLE_SUFFIXES = frozenset(
    {".csv", ".xlsx", ".pdf", ".svg", ".md", ".json", ".yaml", ".txt", ".png"}
)


def may_open(path: Path, *, listed: bool = True) -> bool:
    """Whether Open may hand `path` to the system: the manifest lists it (`listed`) and it is one of
    the kinds above. A file that only sits in the folder is never opened."""
    return listed and path.suffix.lower() in OPENABLE_SUFFIXES


_DAMAGED_SHOWN = 5  # file names the notice for a damaged project lists


@dataclass(frozen=True)
class ExportedFile:
    rel: str  # path inside the outputs folder, "harnesses/W001/wirelist.csv"
    path: Path  # the file on disk
    size: int  # bytes
    doc: Document


@dataclass
class ExportResult:
    """What an export wrote. `files` holds the whole set, the manifest included."""

    folder: Path
    files: list[ExportedFile]
    stamp: str  # the short model hash the outputs were made from
    project: Project  # the private copy the outputs were built from (for the drawing previews)
    built: OutputSet

    @property
    def count(self) -> int:
        return len(self.files)


def scope_label(project: Project, scope: str) -> str:
    """ "W001  Power harness", "System documents" (the manifest has no scope)."""
    if scope == export_docs.SYSTEM:
        return strings.EXP_SYSTEM
    h = project.harnesses.get(scope)
    return strings.EXP_HARNESS_ITEM.format(scope, h.name) if h is not None else scope


def sheet_of(project: Project, stamp: Stamp, ref: export_docs.SheetRef) -> Sheet | None:
    """The drawing sheet a file shows, drawn from the design data like the file itself."""
    try:
        if ref[0] == "harness":
            h = project.harnesses[ref[1]]
            return drawing.harness_sheets(project, h, stamp, ref[2])[ref[3]]
        if ref[1] == "block_diagram":
            return system.block_diagram(project, stamp)
        return system.harness_overview(project, stamp)
    except KeyError, IndexError, ValueError:
        return None


class ExportResultPanel(QWidget):
    """The files an export wrote, with Reveal in folder, Open and a picture of the selected drawing.

    `set_result` fills it; `set_filter` shows only some files (the ticked documents). Reveal and
    Open hand a URL to `opener` (`QDesktopServices.openUrl` unless a test replaces it). Open refuses a
    file of a kind the program does not write and says so with `not_opened`."""

    not_opened = Signal(str)

    def __init__(
        self,
        theme: ThemeManager,
        *,
        settings: QSettings | None = None,
        opener: Opener | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.theme = theme
        self.opener: Opener = opener or QDesktopServices.openUrl
        self.setObjectName("export-result")
        self.setAccessibleName(strings.EXP_RESULT_NAME)
        self.result: ExportResult | None = None
        self._rows: list[dict[str, Any]] = []
        self._filter: set[str] | None = None
        self._sheets: dict[export_docs.SheetRef, Sheet | None] = {}
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self.summary = QLabel()
        self.summary.setObjectName("export-summary")
        self.summary.setWordWrap(True)
        self.summary.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.showing = QLabel()
        self.showing.setObjectName("export-showing")
        self.showing.setProperty("muted", True)
        lay.addWidget(self.summary)
        lay.addWidget(self.showing)
        cols = [
            Column("rel", strings.EXP_COLUMNS["path"], mono=True, tooltip="full_path", width=320),
            Column("doc", strings.EXP_COLUMNS["doc"], width=190),
            Column("scope", strings.EXP_COLUMNS["harness"], width=130),
            Column(
                "size",
                strings.EXP_COLUMNS["size"],
                numeric=True,
                fmt=lambda v: human_size(int(v or 0)),
                width=80,
            ),  # fmt: skip
        ]
        self.model = DictTableModel(cols, [], theme)
        self.table = TableView(
            self.model, theme, name=strings.EXP_RESULT_NAME, settings=settings, key="export-files"
        )
        self.table.setObjectName("export-files")
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        lay.addWidget(self.table, 1)
        low = QHBoxLayout()
        buttons = QVBoxLayout()
        self.path_label = QLabel(strings.EXP_SELECTED_NONE)
        self.path_label.setObjectName("export-selected-path")
        self.path_label.setWordWrap(True)
        self.path_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        mark_mono(self.path_label)
        buttons.addWidget(self.path_label)
        row = QHBoxLayout()
        self.reveal_btn = QPushButton()
        self.reveal_btn.setObjectName("export-reveal")
        icons.icon_button(self.reveal_btn, "reveal", theme, strings.EXP_REVEAL_TIP, text=strings.EXP_REVEAL)  # fmt: skip
        self.open_btn = QPushButton()
        self.open_btn.setObjectName("export-open")
        icons.icon_button(self.open_btn, "folder-open", theme, strings.EXP_OPEN_TIP, text=strings.EXP_OPEN)  # fmt: skip
        self.folder_btn = QPushButton()
        self.folder_btn.setObjectName("export-reveal-folder")
        icons.icon_button(self.folder_btn, "reveal", theme, strings.EXP_REVEAL_FOLDER_TIP, text=strings.EXP_REVEAL_FOLDER)  # fmt: skip
        for b, tip in (
            (self.reveal_btn, strings.EXP_REVEAL_TIP),
            (self.open_btn, strings.EXP_OPEN_TIP),
            (self.folder_btn, strings.EXP_REVEAL_FOLDER_TIP),
        ):
            b.setToolTip(tip)
            row.addWidget(b)
        row.addStretch(1)
        buttons.addLayout(row)
        buttons.addStretch(1)
        low.addLayout(buttons, 1)
        preview = QVBoxLayout()
        self.preview_stack = QStackedWidget()
        self.preview_stack.setObjectName("export-preview")
        self.preview_stack.setAccessibleName(strings.EXP_PREVIEW_NAME)
        self.sheet_view = SheetView(theme)
        self.sheet_view.setObjectName("export-sheet")
        self.sheet_view.setAccessibleName(strings.EXP_PREVIEW_NAME)
        self.sheet_view.setMinimumSize(theme.px(240), theme.px(160))
        self.sheet_view.setMaximumHeight(theme.px(220))
        self.preview_note = QLabel(strings.EXP_PREVIEW_HINT)
        self.preview_note.setObjectName("export-preview-note")
        self.preview_note.setProperty("muted", True)
        self.preview_note.setWordWrap(True)
        self.preview_note.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_stack.addWidget(self.preview_note)
        self.preview_stack.addWidget(self.sheet_view)
        caption = QLabel(strings.EXP_PREVIEW_CAPTION)
        caption.setProperty("muted", True)
        caption.setWordWrap(True)
        preview.addWidget(self.preview_stack)
        preview.addWidget(caption)
        low.addLayout(preview, 1)
        lay.addLayout(low)
        self.reveal_btn.clicked.connect(self.reveal_selected)
        self.open_btn.clicked.connect(self.open_selected)
        self.folder_btn.clicked.connect(self.reveal_folder)
        self.table.doubleClicked.connect(lambda _i: self.open_selected())
        sel = self.table.selectionModel()
        if sel is not None:
            sel.selectionChanged.connect(lambda *_: self._selection_changed())
        for keys, handler in (("Return", self.open_selected), ("Ctrl+Return", self.reveal_selected)):  # fmt: skip
            for k in (keys, keys.replace("Return", "Enter")):
                sc = QShortcut(QKeySequence(k), self.table)
                sc.setContext(Qt.ShortcutContext.WidgetShortcut)
                sc.activated.connect(handler)
        self._selection_changed()

    # ---- content ----------------------------------------------------------------------------

    def set_result(self, result: ExportResult | None) -> None:
        self.result = result
        self._sheets.clear()
        self._filter = None
        if result is None:
            self.model.set_rows([])
            self.summary.setText("")
            self.showing.setText("")
            self._selection_changed()
            return
        self._rows = [self._row(result, f) for f in result.files]
        self.summary.setText(
            strings.EXP_RESULT_HEAD.format(result.count, result.folder, result.stamp)
        )
        self._apply_filter()

    def _row(self, result: ExportResult, f: ExportedFile) -> dict[str, Any]:
        scope = (
            strings.EXP_WHOLE_FOLDER
            if f.doc.scope == ""
            else strings.EXP_SYSTEM_SCOPE
            if f.doc.scope == export_docs.SYSTEM
            else f.doc.scope
        )
        return {
            "rel": f.rel,
            "doc": f.doc.label,
            "scope": scope,
            "size": f.size,
            "full_path": str(f.path),
        }

    def set_filter(self, rels: set[str] | None) -> None:
        """Show only these files (None: all). The manifest is always shown: it is part of what
        was written, even though a copy leaves it out."""
        self._filter = rels
        self._apply_filter()

    def _apply_filter(self) -> None:
        result = self.result
        if result is None:
            return
        shown = [
            r
            for r, f in zip(self._rows, result.files, strict=True)
            if self._filter is None or f.rel in self._filter or f.rel == export_docs.MANIFEST
        ]
        kept = [f.rel for f in self.selected_files()]  # the selected file stays selected
        self.model.set_rows(shown)
        if kept:
            self.select_file(kept[0])
        hidden = len(shown) != result.count
        self.showing.setText(strings.EXP_SHOWING.format(len(shown), result.count) if hidden else "")
        self.showing.setVisible(hidden)
        self._selection_changed()

    def visible_files(self) -> list[ExportedFile]:
        result = self.result
        if result is None:
            return []
        by_rel = {f.rel: f for f in result.files}
        return [by_rel[str(r["rel"])] for r in self.model.rows() if isinstance(r, Mapping)]

    def selected_files(self) -> list[ExportedFile]:
        result = self.result
        if result is None:
            return []
        by_rel = {f.rel: f for f in result.files}
        return [by_rel[str(r["rel"])] for r in self.table.selected_rows() if isinstance(r, Mapping)]

    def select_file(self, rel: str) -> bool:
        """Select the row of a file (False if it is not shown)."""
        for i in range(self.table.proxy.rowCount()):
            row = self.table.row_at(self.table.proxy.index(i, 0))
            if isinstance(row, Mapping) and row.get("rel") == rel:
                sel = self.table.selectionModel()
                if sel is None:
                    return False
                index = self.table.proxy.index(i, 0)
                sel.setCurrentIndex(index, QItemSelectionModel.SelectionFlag.NoUpdate)
                sel.select(
                    index,
                    QItemSelectionModel.SelectionFlag.ClearAndSelect
                    | QItemSelectionModel.SelectionFlag.Rows,
                )
                return True
        return False

    # ---- actions ---------------------------------------------------------------------------

    def _selection_changed(self) -> None:
        files = self.selected_files()
        one = files[0] if files else None
        self.reveal_btn.setEnabled(one is not None)
        self.open_btn.setEnabled(one is not None)
        self.folder_btn.setEnabled(self.result is not None)
        self.path_label.setText(str(one.path) if one else strings.EXP_SELECTED_NONE)
        self._show_preview(one)

    def reveal_selected(self) -> QUrl | None:
        """Show the selected file in its folder; returns the URL handed to the system."""
        files = self.selected_files()
        if not files:
            return None
        url = reveal_url(files[0].path)
        self.opener(url)
        return url

    def open_selected(self) -> QUrl | None:
        files = self.selected_files()
        if not files:
            return None
        if not may_open(files[0].path):
            self.not_opened.emit(
                strings.OUT_NOT_OPENED
            )  # the dialog shows it with the folder offered
            return None
        url = open_url(files[0].path)
        self.opener(url)
        return url

    def reveal_folder(self) -> QUrl | None:
        if self.result is None:
            return None
        url = reveal_url(self.result.folder)
        self.opener(url)
        return url

    # ---- the picture --------------------------------------------------------------------------

    def _show_preview(self, f: ExportedFile | None) -> None:
        sheet = None
        note = strings.EXP_PREVIEW_HINT
        if f is not None:
            ref = export_docs.sheet_ref(f.rel)
            if ref is None:
                note = strings.EXP_PREVIEW_NONE
            elif self.result is not None:
                if ref not in self._sheets:
                    self._sheets[ref] = sheet_of(self.result.project, self.result.built.stamp, ref)
                sheet = self._sheets[ref]
                if sheet is None:
                    note = strings.EXP_PREVIEW_NONE
        self.sheet_view.set_sheet(sheet)
        self.preview_note.setText(note)
        self.preview_stack.setCurrentWidget(self.sheet_view if sheet is not None else self.preview_note)  # fmt: skip

    def previewing(self) -> bool:
        """True when a drawing is shown (not the note)."""
        return self.preview_stack.currentWidget() is self.sheet_view


class ExportDialog(QDialog):
    """Choose, run and read an export. See the module text for the whole picture."""

    exported = Signal(object)  # ExportResult, after the files are on disk
    failed = Signal(str)  # why nothing was written (also shown in the dialog)
    cancelled = Signal()
    progressed = Signal(float, str)
    finishedExport = Signal(bool)  # every ending of a run: True when files were written
    selectionChanged = Signal()  # the ticked documents changed

    def __init__(
        self,
        ctl: EditorController,
        theme: ThemeManager,
        parent: QWidget | None = None,
        *,
        settings: QSettings | None = None,
        worker_factory: Callable[[Project], OutputsWorker] | None = None,
        ask_folder: AskFolder | None = None,
        opener: Opener | None = None,
    ) -> None:
        super().__init__(parent)
        self.ctl, self.theme, self.settings = ctl, theme, settings
        self.worker_factory = worker_factory or default_worker
        self.ask_folder: AskFolder = ask_folder or _ask_folder
        self.opener: Opener = opener or QDesktopServices.openUrl
        self.setObjectName("export-dialog")
        self.setWindowTitle(strings.EXP_TITLE)
        self.setAccessibleName(strings.EXP_ACCESSIBLE)
        self.resize(theme.px(1000), theme.px(620))
        self.setMinimumSize(theme.px(760), theme.px(480))
        self.export_result: ExportResult | None = None
        self.worker: OutputsWorker | None = None
        self._token: tuple[int, int] | None = None
        self._project: Project | None = None
        self._bulk = False
        self._last_ok = False
        lay = QVBoxLayout(self)

        # ---- header: title, last export, folder ------------------------------------------
        head = QHBoxLayout()
        title = QLabel(f"<h3>{strings.EXP_TITLE}</h3>")
        head.addWidget(title)
        head.addStretch(1)
        self.last = QLabel()
        self.last.setObjectName("export-last")
        self.last.setProperty("muted", True)
        self.stale_chip = StateChip(theme, "stale")
        self.stale_chip.setObjectName("export-stale")
        head.addWidget(self.stale_chip)
        head.addWidget(self.last)
        lay.addLayout(head)
        frow = QHBoxLayout()
        flabel = QLabel(strings.EXP_FOLDER)
        self.folder = QLineEdit()
        self.folder.setObjectName("export-folder")
        self.folder.setReadOnly(True)
        self.folder.setAccessibleName(strings.EXP_FOLDER)
        self.folder.setToolTip(strings.EXP_FOLDER_TIP)
        mark_mono(self.folder)
        flabel.setBuddy(self.folder)
        frow.addWidget(flabel)
        frow.addWidget(self.folder, 1)
        lay.addLayout(frow)
        self.notice = InlineNotice(theme)
        self.notice.setObjectName("export-notice")
        lay.addWidget(self.notice)

        # ---- body: tree | pages ------------------------------------------------------------
        split = QSplitter(Qt.Orientation.Horizontal)
        split.setObjectName("export-split")
        split.setChildrenCollapsible(False)
        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 0, 0)
        tree_title = QLabel(strings.EXP_TREE_NAME)
        tree_title.setProperty("heading", True)
        ll.addWidget(tree_title)
        self.tree = QTreeView()
        self.tree.setObjectName("export-tree")
        self.tree.setAccessibleName(strings.EXP_TREE_NAME)
        self.tree.setToolTip(strings.EXP_TREE_TIP)
        self.tree.setHeaderHidden(True)
        self.tree.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.model = QStandardItemModel(self.tree)
        self.tree.setModel(self.model)
        ll.addWidget(self.tree, 1)
        sel_row = QHBoxLayout()
        self.all_btn = QPushButton()
        self.all_btn.setObjectName("export-select-all")
        icons.icon_button(self.all_btn, "pass", theme, strings.EXP_SELECT_ALL_TIP, text=strings.EXP_SELECT_ALL)  # fmt: skip
        self.none_btn = QPushButton()
        self.none_btn.setObjectName("export-select-none")
        icons.icon_button(self.none_btn, "close", theme, strings.EXP_SELECT_NONE_TIP, text=strings.EXP_SELECT_NONE)  # fmt: skip
        self.all_btn.setToolTip(strings.EXP_SELECT_ALL_TIP)
        self.none_btn.setToolTip(strings.EXP_SELECT_NONE_TIP)
        sel_row.addWidget(self.all_btn)
        sel_row.addWidget(self.none_btn)
        sel_row.addStretch(1)
        ll.addLayout(sel_row)
        self.drawings = QCheckBox(strings.EXP_DRAWINGS)
        self.drawings.setObjectName("export-drawings")
        self.drawings.setAccessibleName(strings.EXP_DRAWINGS_NAME)
        self.drawings.setToolTip(strings.EXP_DRAWINGS_TIP)
        folder = self.output_folder()
        self.drawings.setChecked(folder is not None and drawings_exported(folder))
        ll.addWidget(self.drawings)
        split.addWidget(left)

        self.pages = QStackedWidget()
        self.pages.setObjectName("export-pages")
        info = QWidget()
        il = QVBoxLayout(info)
        self.note = QLabel(strings.EXP_FULL_NOTE)
        self.note.setObjectName("export-note")
        self.note.setWordWrap(True)
        self.note.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        il.addWidget(self.note)
        il.addStretch(1)
        self.pages.addWidget(info)
        run = QWidget()
        rl = QVBoxLayout(run)
        rl.addStretch(1)
        self.stage = QLabel(strings.EXP_RUNNING)
        self.stage.setObjectName("export-stage")
        self.bar = QProgressBar()
        self.bar.setObjectName("export-progress")
        self.bar.setAccessibleName(strings.EXP_PROGRESS_NAME)
        self.bar.setRange(0, 100)
        self.cancel_btn = QPushButton()
        self.cancel_btn.setObjectName("export-cancel")
        icons.icon_button(self.cancel_btn, "close", theme, strings.EXP_CANCEL_TIP, text=strings.CANCEL)  # fmt: skip
        self.cancel_btn.setToolTip(strings.EXP_CANCEL_TIP)
        rl.addWidget(self.stage)
        rl.addWidget(self.bar)
        rl.addWidget(self.cancel_btn, 0, Qt.AlignmentFlag.AlignLeft)
        rl.addStretch(1)
        self.pages.addWidget(run)
        self.result_panel = ExportResultPanel(theme, settings=settings, opener=self._open)
        self.result_panel.not_opened.connect(self._show_not_opened)
        self.pages.addWidget(self.result_panel)
        split.addWidget(self.pages)
        split.setStretchFactor(0, 1)
        split.setStretchFactor(1, 3)
        lay.addWidget(split, 1)

        # ---- buttons -----------------------------------------------------------------------
        bottom = QHBoxLayout()
        self.open_after = QCheckBox(strings.EXP_OPEN_AFTER)
        self.open_after.setObjectName("export-open-after")
        self.open_after.setAccessibleName(strings.EXP_OPEN_AFTER)
        self.open_after.setToolTip(strings.EXP_OPEN_AFTER_TIP)
        if settings is not None:
            self.open_after.setChecked(str(settings.value("export/open_after", "false")) == "true")
        bottom.addWidget(self.open_after)
        bottom.addStretch(1)
        self.copy_btn = QPushButton()
        self.copy_btn.setObjectName("export-copy")
        icons.icon_button(self.copy_btn, "export", theme, strings.EXP_COPY_TIP, text=strings.EXP_COPY)  # fmt: skip
        self.copy_btn.setToolTip(strings.EXP_COPY_TIP)
        self.close_btn = QPushButton()
        self.close_btn.setObjectName("export-close")
        icons.icon_button(self.close_btn, "close", theme, strings.EXP_CLOSE_TIP, text=strings.CLOSE)  # fmt: skip
        self.close_btn.setToolTip(strings.EXP_CLOSE_TIP)
        self.export_btn = QPushButton()
        self.export_btn.setObjectName("export-run")
        icons.icon_button(self.export_btn, "export", theme, strings.EXP_BUTTON_TIP, text=strings.EXP_BUTTON, role="on-primary")  # fmt: skip
        self.export_btn.setToolTip(strings.EXP_BUTTON_TIP)
        self.export_btn.setProperty("primary", True)
        self.export_btn.setDefault(True)
        bottom.addWidget(self.copy_btn)
        bottom.addWidget(self.close_btn)
        bottom.addWidget(self.export_btn)
        lay.addLayout(bottom)

        # ---- wiring ------------------------------------------------------------------------
        self.model.itemChanged.connect(self._item_changed)
        self.all_btn.clicked.connect(lambda: self.set_all_checked(True))
        self.none_btn.clicked.connect(lambda: self.set_all_checked(False))
        self.export_btn.clicked.connect(self.start)
        self.cancel_btn.clicked.connect(self.cancel)
        self.close_btn.clicked.connect(self.reject)
        self.copy_btn.clicked.connect(lambda: self.copy_selection())
        self.open_after.toggled.connect(self._remember_open_after)
        self.drawings.toggled.connect(self._drawings_toggled)
        self.refresh()

    # ---- the folder and what blocks an export -------------------------------------------------

    def _open(self, url: QUrl) -> bool:
        return self.opener(url)

    def _show_not_opened(self, text: str) -> None:
        def folder() -> None:
            self.result_panel.reveal_folder()

        self.notice.show_notice(
            "warning",
            text,
            button=strings.EXP_REVEAL_FOLDER,
            tooltip=strings.EXP_REVEAL_FOLDER_TIP,
            callback=folder,
        )

    def output_folder(self) -> Path | None:
        return self.ctl.outputs_folder()

    def blocker(self) -> str | None:
        """Why an export cannot start now ("unsaved" when only a saved project helps), else None."""
        if self.ctl.read_only:
            return strings.EXPORT_READ_ONLY
        if self.ctl.project.recovered:
            return strings.EXPORT_DAMAGED
        if self.output_folder() is None:
            return "unsaved"
        if not self.ctl.project.harnesses:
            return strings.EXPORT_NO_HARNESSES
        return None

    def refresh(self) -> None:
        """Read the project again: folder, what blocks the export, the tree (before a result)."""
        folder = self.output_folder()
        self.folder.setText(str(folder) if folder is not None else strings.EXP_FOLDER_UNSAVED)
        state = self.ctl.outputs_state() if folder is not None else "none"
        self.last.setText(_LAST.get(state, strings.EXP_LAST_NONE))
        self.stale_chip.setVisible(state == "stale")
        if self.export_result is None:
            self._build_tree(None)
        self._show_blocker()
        self._sync_buttons()

    def _show_blocker(self) -> None:
        reason = self.blocker()
        if reason is None:
            if self.notice.property("kind") == "blocker":
                self.notice.clear()
            return
        self.notice.setProperty("kind", "blocker")
        if reason == "unsaved":
            self.notice.show_notice(
                "warning",
                strings.EXP_BLOCK_UNSAVED,
                button=strings.EXP_SAVE_PROJECT,
                tooltip=strings.EXP_SAVE_PROJECT_TIP,
                callback=self._save_clicked,
            )
        elif reason == strings.EXPORT_DAMAGED:
            files = recovery.damaged_files(self.ctl.project)
            details = [*files[:_DAMAGED_SHOWN]]
            if len(files) > _DAMAGED_SHOWN:
                details.append(strings.EXP_DAMAGED_MORE.format(len(files) - _DAMAGED_SHOWN))
            self.notice.show_notice("warning", reason, details=details)
        else:
            self.notice.show_notice("warning", reason)

    def _save_clicked(self) -> None:
        self.save_project()

    def save_project(self) -> bool:
        """Ask for an empty folder and save the project there (the outputs go next to it)."""
        folder = self.ask_folder(strings.SAVE_AS_FOLDER)
        if not folder:
            return False
        try:
            self.ctl.save_as(Path(folder))
        except (HarnessError, OSError, ValueError) as exc:
            self.notice.setProperty("kind", "error")
            self.notice.show_notice("error", self._explain(exc, folder))
            return False
        self.notice.clear()
        self.refresh()
        return True

    @staticmethod
    def _explain(exc: Exception, folder: str | Path | None) -> str:
        if isinstance(exc, HarnessError):
            return str(exc)
        if isinstance(exc, ValueError):
            return strings.SAVE_BAD_TEXT
        where = f" in {folder}" if folder else ""
        reason = getattr(exc, "strerror", None) or strings.FOLDER_UNUSABLE
        return strings.FILE_ERROR.format(where=where, reason=reason)

    def _drawings_toggled(self, _on: bool) -> None:
        """The drawing documents come into or leave the planned tree (the tree of a result is the
        list of files written and stays until the next export)."""
        if self.export_result is None:
            self._build_tree(None)

    def _remember_open_after(self, on: bool) -> None:
        if self.settings is not None:
            self.settings.setValue("export/open_after", "true" if on else "false")

    @property
    def running(self) -> bool:
        return self.worker is not None

    def _sync_buttons(self) -> None:
        busy = self.running
        can = self.blocker() is None and not busy
        self.export_btn.setEnabled(can)
        self.export_btn.setText(
            strings.EXP_AGAIN if self.export_result is not None else strings.EXP_BUTTON
        )
        self.tree.setEnabled(not busy)
        self.all_btn.setEnabled(not busy)
        self.none_btn.setEnabled(not busy)
        self.copy_btn.setVisible(self.export_result is not None)
        self.copy_btn.setEnabled(self.export_result is not None and not busy)
        self.open_after.setEnabled(not busy)
        self.drawings.setEnabled(not busy)

    # ---- the tree -----------------------------------------------------------------------------

    def _unchecked(self) -> set[tuple[str, str]]:
        out: set[tuple[str, str]] = set()
        for top in range(self.model.rowCount()):
            parent = self.model.item(top)
            for r in range(parent.rowCount()):
                child = parent.child(r)
                if child.checkState() == Qt.CheckState.Unchecked:
                    out.add((str(parent.data(Qt.ItemDataRole.UserRole)), str(child.data(Qt.ItemDataRole.UserRole))))  # fmt: skip
        return out

    def _build_tree(self, files: list[ExportedFile] | None) -> None:
        """The harness x document tree: planned from the build layout before an export, from the
        files written after it. Ticks the user removed stay removed."""
        unchecked = self._unchecked()
        project = self._project or self.ctl.project
        counts: dict[tuple[str, str], int] = {}
        scopes: dict[str, list[str]] = {}
        labels: dict[tuple[str, str], str] = {}
        if files is None:
            for scope, docs in export_docs.planned_layout(
                project.harnesses, self.drawings.isChecked()
            ):
                scopes[scope] = [d.key for d in docs]
                for d in docs:
                    labels[(scope, d.key)] = d.label
        else:
            for f in files:
                if f.doc.scope == "":
                    continue
                counts[(f.doc.scope, f.doc.key)] = counts.get((f.doc.scope, f.doc.key), 0) + 1
                labels[(f.doc.scope, f.doc.key)] = f.doc.label
            order = [*sorted(project.harnesses), export_docs.SYSTEM]
            known = [s for s in order if any(s == k[0] for k in counts)]
            extra = sorted({k[0] for k in counts} - set(order))
            planned = {key: i for i, key in enumerate(d.key for d in (*export_docs.HARNESS_DOCS, *export_docs.SYSTEM_DOCS))}  # fmt: skip
            for scope in [*known, *extra]:
                keys = sorted((k[1] for k in counts if k[0] == scope), key=lambda k: (planned.get(k, 10_000), k))  # fmt: skip
                scopes[scope] = keys
        self._bulk = True
        try:
            self.model.clear()
            for scope, keys in scopes.items():
                total = sum(counts.get((scope, k), 0) for k in keys)
                text = scope_label(project, scope)
                if files is not None:
                    text = strings.EXP_COUNT_ITEM.format(text, total)
                top = QStandardItem(text)
                top.setCheckable(True)
                top.setEditable(False)
                top.setData(scope, Qt.ItemDataRole.UserRole)
                top.setCheckState(Qt.CheckState.Checked)
                for key in keys:
                    child_text = labels[(scope, key)]
                    n = counts.get((scope, key), 0)
                    if files is not None and n > 1:
                        child_text = strings.EXP_COUNT_ITEM.format(child_text, n)
                    child = QStandardItem(child_text)
                    child.setCheckable(True)
                    child.setEditable(False)
                    child.setData(key, Qt.ItemDataRole.UserRole)
                    child.setCheckState(
                        Qt.CheckState.Unchecked
                        if (scope, key) in unchecked
                        else Qt.CheckState.Checked
                    )
                    top.appendRow(child)
                self.model.appendRow(top)
        finally:
            self._bulk = False
        self.tree.expandToDepth(0)

    def _item_changed(self, item: QStandardItem) -> None:
        """A harness follows its documents (all, some or none ticked) and ticks them all when it is
        ticked itself."""
        if self._bulk:
            return
        self._bulk = True
        try:
            parent = item.parent()
            if parent is None:  # a harness: its state goes to every document
                if item.checkState() != Qt.CheckState.PartiallyChecked:
                    for r in range(item.rowCount()):
                        item.child(r).setCheckState(item.checkState())
            else:  # a document: the harness shows all, some or none of them
                states = {parent.child(r).checkState() for r in range(parent.rowCount())}
                if states == {Qt.CheckState.Checked}:
                    parent.setCheckState(Qt.CheckState.Checked)
                elif states == {Qt.CheckState.Unchecked}:
                    parent.setCheckState(Qt.CheckState.Unchecked)
                else:
                    parent.setCheckState(Qt.CheckState.PartiallyChecked)
        finally:
            self._bulk = False
        self._selection_changed()

    def _selection_changed(self) -> None:
        self.result_panel.set_filter(
            self.selected_paths() if self.export_result is not None else None
        )
        self.selectionChanged.emit()

    def set_all_checked(self, on: bool) -> None:
        self._bulk = True
        try:
            state = Qt.CheckState.Checked if on else Qt.CheckState.Unchecked
            for top in range(self.model.rowCount()):
                parent = self.model.item(top)
                parent.setCheckState(state)
                for r in range(parent.rowCount()):
                    parent.child(r).setCheckState(state)
        finally:
            self._bulk = False
        self._selection_changed()

    def set_checked(self, scope: str, key: str | None, on: bool) -> bool:
        """Tick or untick a harness (all its documents) or one document type. False if absent."""
        state = Qt.CheckState.Checked if on else Qt.CheckState.Unchecked
        for top in range(self.model.rowCount()):
            parent = self.model.item(top)
            if str(parent.data(Qt.ItemDataRole.UserRole)) != scope:
                continue
            if key is None:
                parent.setCheckState(state)  # _item_changed ticks its documents
                return True
            for r in range(parent.rowCount()):
                if str(parent.child(r).data(Qt.ItemDataRole.UserRole)) == key:
                    parent.child(r).setCheckState(state)
                    return True
        return False

    def checked_documents(self) -> set[tuple[str, str]]:
        """(scope, document key) of every ticked document type."""
        out: set[tuple[str, str]] = set()
        for top in range(self.model.rowCount()):
            parent = self.model.item(top)
            for r in range(parent.rowCount()):
                child = parent.child(r)
                if child.checkState() == Qt.CheckState.Checked:
                    out.add((str(parent.data(Qt.ItemDataRole.UserRole)), str(child.data(Qt.ItemDataRole.UserRole))))  # fmt: skip
        return out

    def selected_paths(self) -> set[str]:
        """The files of the ticked documents (the manifest is never among them)."""
        if self.export_result is None:
            return set()
        ticked = self.checked_documents()
        return {
            f.rel
            for f in self.export_result.files
            if f.doc.scope != "" and (f.doc.scope, f.doc.key) in ticked
        }

    # ---- running ------------------------------------------------------------------------------

    def start(self) -> bool:
        """Start the export without waiting (the window stays responsive); False if something
        blocks it or one is running. Watch `exported`, `failed`, `cancelled` or `finishedExport`."""
        if self.running or self.blocker() is not None:
            self._show_blocker()
            return False
        self.notice.setProperty("kind", None)
        self.notice.clear()
        self._token = self.ctl.state_token
        self._project = edit.clone_with(self.ctl.project, [])
        worker = self.worker_factory(self._project)
        worker.drawings = self.drawings.isChecked()
        self.worker = worker
        worker.progressed.connect(self._on_progress)
        worker.finished.connect(self._worker_done)
        self.bar.setValue(0)
        self.stage.setText(strings.EXP_RUNNING)
        self.pages.setCurrentIndex(1)
        self._sync_buttons()
        worker.start()
        self.cancel_btn.setFocus()
        return True

    def _on_progress(self, fraction: float, text: str) -> None:
        self.bar.setValue(int(fraction * 100))
        self.stage.setText(text)
        self.progressed.emit(fraction, text)

    def cancel(self) -> None:
        if self.worker is not None:
            self.worker.cancel()

    def run(self) -> ExportResult | None:
        """Export and wait for the end (a local event loop, so the window stays responsive);
        returns what was written, or None when it was blocked, cancelled or failed (the dialog
        says why)."""
        loop = QEventLoop(self)
        self.finishedExport.connect(loop.quit)
        try:
            if not self.start():
                return None
            loop.exec()
        finally:
            self.finishedExport.disconnect(loop.quit)
        return self.export_result if self._last_ok else None

    def _end(self, ok: bool) -> None:
        self.worker = None
        self._last_ok = ok
        # the list of an earlier export stays on screen when this one did not write anything
        self.pages.setCurrentIndex(2 if self.export_result is not None else 0)
        self._sync_buttons()
        self.export_btn.setFocus()
        self.finishedExport.emit(ok)

    def _fail(self, message: str, details: list[str] | None = None) -> None:
        self.notice.setProperty("kind", "error")
        self.notice.show_notice("error", message, details=details)
        self.failed.emit(message)
        self._end(False)

    def _worker_done(self) -> None:
        worker = self.worker
        if worker is None:
            return
        worker.wait()
        folder = self.output_folder()
        if worker.result is None or worker.report is None:
            if worker.error:
                self._fail(strings.EXPORT_ERROR.format(worker.error))
            else:
                self.notice.setProperty("kind", "info")
                self.notice.show_notice("info", strings.EXPORT_CANCELLED)
                self.cancelled.emit()
                self._end(False)
            return
        if self._token != self.ctl.state_token:  # edited while it was built: it describes old data
            self._fail(strings.EXP_NOTE_CHANGED)
            return
        built, report = worker.result, worker.report
        if not report.ok:
            self._fail(*self._check_failure(report))
            return
        if folder is None:
            self._fail(strings.EXPORT_SAVE_FIRST)
            return
        try:
            write_outputs(self.ctl.project, folder, built)
        except (HarnessError, OSError) as exc:
            self._fail(strings.EXP_WRITE_FAILED.format(self._explain(exc, folder)))
            return
        project = self._project or self.ctl.project
        result = ExportResult(folder, self._listing(folder, built), built.stamp.short, project, built)  # fmt: skip
        self.export_result = result
        self._build_tree(result.files)
        self.result_panel.set_result(result)
        self._selection_changed()
        self.notice.clear()
        state = self.ctl.outputs_state()
        self.last.setText(_LAST.get(state, strings.EXP_LAST_NONE))
        self.stale_chip.setVisible(state == "stale")
        self.exported.emit(result)
        if self.open_after.isChecked():
            self.opener(reveal_url(folder))
        self._end(True)

    @staticmethod
    def _check_failure(report: VerifyReport) -> tuple[str, list[str]]:
        errors = report.errors
        shown = [i.message for i in errors[:MAX_DETAILS]]
        if len(errors) > MAX_DETAILS:
            shown.append(strings.AND_MORE.format(len(errors) - MAX_DETAILS))
        return strings.EXP_CHECK_FAILED.format(len(errors)), shown

    @staticmethod
    def _listing(folder: Path, built: OutputSet) -> list[ExportedFile]:
        files = [
            ExportedFile(rel, folder / rel, len(data), export_docs.classify(rel))
            for rel, data in sorted(built.files.items())
        ]
        manifest = folder / MANIFEST
        size = manifest.stat().st_size if manifest.is_file() else 0
        files.append(ExportedFile(MANIFEST, manifest, size, export_docs.classify(MANIFEST)))
        return files

    # ---- copy ---------------------------------------------------------------------------------

    def copy_selection(self, folder: str | Path | None = None) -> int:
        """Copy the ticked documents' files (not the manifest) to an empty folder, keeping the
        folder layout; the bytes are those that were written. Returns the number of files copied
        (0 when nothing was copied; the reason is shown in the dialog)."""
        result = self.export_result
        if result is None:
            return 0
        rels = sorted(self.selected_paths())
        if not rels:
            self.notice.setProperty("kind", "error")
            self.notice.show_notice("warning", strings.EXP_COPY_NONE)
            return 0
        chosen = str(folder) if folder is not None else self.ask_folder(strings.EXP_COPY_FOLDER)
        if not chosen:
            return 0
        dest = Path(chosen)
        if dest.exists() and (not dest.is_dir() or any(dest.iterdir())):
            self.notice.setProperty("kind", "error")
            self.notice.show_notice("error", strings.EXP_COPY_NOT_EMPTY)
            return 0
        try:
            for rel in rels:
                if not export_docs.is_safe(rel):
                    raise HarnessError(f"'{rel}' is not a path inside the outputs folder.")
                atomic_write_bytes(dest / rel, result.built.files[rel], backup=False, root=dest, durable=False)  # fmt: skip
        except (HarnessError, OSError) as exc:
            self.notice.setProperty("kind", "error")
            self.notice.show_notice("error", self._explain(exc, dest))
            return 0
        self.notice.setProperty("kind", "info")
        self.notice.show_notice(
            "info",
            strings.EXP_COPY_DONE.format(len(rels), dest),
            button=strings.EXP_REVEAL,
            tooltip=strings.EXP_REVEAL_TIP,
            callback=lambda: self._reveal(dest),
        )
        return len(rels)

    def _reveal(self, path: Path) -> None:
        self.opener(reveal_url(path))

    # ---- closing ------------------------------------------------------------------------------

    def reject(self) -> None:
        """Esc or Close: while an export runs this stops it (nothing is written) and waits."""
        if self.worker is not None:
            worker = self.worker
            worker.cancel()
            worker.wait()
            self._worker_done()
        super().reject()
