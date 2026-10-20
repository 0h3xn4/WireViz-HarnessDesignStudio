"""Spreadsheet behaviour for the tables of the model: paste from Excel, bulk edit, Enter to edit and
a menu that shows and hides columns.

    install_sheet(view, settings=settings, key="interfaces")    # a QTableView whose model has `set_cells`

The model decides what a cell is worth (it owns the validation and the controller call); this module
only turns keys and the clipboard into `model.set_cells([(source_row, column, text), ...])`, which
the model applies as one undoable step, so pasting 500 rows is one Ctrl+Z.

A model that can be edited this way offers:

    is_editable(column) -> bool
    set_cells(cells: list[tuple[int, int, str]]) -> bool        # source rows, never proxy rows
"""

from __future__ import annotations

import csv
import io
import json
from collections.abc import Callable, Sequence
from typing import Any, Protocol

from PySide6.QtCore import (
    QAbstractItemModel,
    QEvent,
    QModelIndex,
    QObject,
    QPersistentModelIndex,
    QSettings,
    QSortFilterProxyModel,
    Qt,
)
from PySide6.QtGui import QGuiApplication, QKeyEvent, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QAbstractItemView,
    QMenu,
    QStyledItemDelegate,
    QTableView,
    QWidget,
)

from . import strings


class SheetModel(Protocol):
    def is_editable(self, column: int) -> bool: ...
    def set_cells(self, cells: list[tuple[int, int, str]]) -> bool: ...


def parse_tsv(text: str) -> list[list[str]]:
    """The cells of text copied from Excel, LibreOffice or this program: tab-separated, a cell
    that holds a tab, a line break or a quote is in quotes, and the last line break is not a row."""
    if not text:
        return []
    body = (
        text[:-2] if text.endswith("\r\n") else text[:-1] if text.endswith(("\n", "\r")) else text
    )
    reader = csv.reader(io.StringIO(body, newline=""), delimiter="\t", quotechar='"')
    return [row for row in reader]


def source_model(
    view: QAbstractItemView,
) -> tuple[QAbstractItemModel, QSortFilterProxyModel | None]:
    model = view.model()
    if isinstance(model, QSortFilterProxyModel):
        return model.sourceModel(), model
    return model, None


def to_source_row(proxy: QSortFilterProxyModel | None, index: QModelIndex) -> int:
    return proxy.mapToSource(index).row() if proxy is not None else index.row()


def selected_cells(view: QAbstractItemView) -> list[QModelIndex]:
    """The selected cells in reading order (top to bottom, left to right)."""
    sel = view.selectionModel()
    cells = list(sel.selectedIndexes()) if sel else []
    cells.sort(key=lambda i: (i.row(), i.column()))
    return cells


def paste_text(view: QTableView, text: str) -> tuple[int, int]:
    """Put `text` into the table starting at the top-left selected cell: a single value fills every
    selected cell, a block fills the cells below and to the right of the start. Returns (cells
    given to the model, cells that fell outside the table or were read-only)."""
    source, proxy = source_model(view)
    if not isinstance(source, QAbstractItemModel) or not hasattr(source, "set_cells"):
        return (0, 0)
    matrix = parse_tsv(text)
    if not matrix:
        return (0, 0)
    selected = selected_cells(view)
    if not selected:
        current = view.currentIndex()
        if not current.isValid():
            return (0, 0)
        selected = [current]
    model: Any = source
    cells: list[tuple[int, int, str]] = []
    skipped = 0
    if len(matrix) == 1 and len(matrix[0]) == 1 and len(selected) > 1:
        value = matrix[0][0]
        for idx in selected:
            if model.is_editable(idx.column()):
                cells.append((to_source_row(proxy, idx), idx.column(), value))
            else:
                skipped += 1
    else:
        start = selected[0]
        rows = view.model().rowCount()
        cols = view.model().columnCount()
        for r, line in enumerate(matrix):
            for c, value in enumerate(line):
                row, col = start.row() + r, start.column() + c
                if row >= rows or col >= cols or not model.is_editable(col):
                    skipped += 1
                    continue
                cells.append((to_source_row(proxy, view.model().index(row, col)), col, value))
    if cells:
        model.set_cells(cells)
    return (len(cells), skipped)


def selected_same_column(view: QAbstractItemView, index: QModelIndex) -> list[QModelIndex]:
    """The selected cells in the column of `index`, when `index` is one of several selected rows
    (what a bulk edit applies to); otherwise just `index`."""
    cells = [i for i in selected_cells(view) if i.column() == index.column()]
    if len(cells) > 1 and any(i.row() == index.row() for i in cells):
        return cells
    return [index]


class SheetDelegate(QStyledItemDelegate):
    """Writes an edit to every selected row of the column when several rows are selected (bulk
    edit), as one step. With one row selected it is the ordinary delegate."""

    def setModelData(  # noqa: N802
        self,
        editor: QWidget,
        model: QAbstractItemModel,
        index: QModelIndex | QPersistentModelIndex,
    ) -> None:
        view = self.parent()
        source, proxy = source_model(view) if isinstance(view, QAbstractItemView) else (model, None)
        if not (isinstance(view, QAbstractItemView) and hasattr(source, "set_cells")):
            super().setModelData(editor, model, index)
            return
        text = self.editor_text(editor)
        targets = selected_same_column(view, view.model().index(index.row(), index.column()))
        src: Any = source
        src.set_cells([(to_source_row(proxy, t), t.column(), text) for t in targets])

    @staticmethod
    def editor_text(editor: QWidget) -> str:
        prop = editor.metaObject().userProperty()
        value = prop.read(editor) if prop.isValid() else ""
        return str(value if value is not None else "")


class _SheetKeys(QObject):
    """Return or Enter edits the current cell (the arrow keys move; Esc closes the editor and keeps the
    old value); Ctrl+V pastes."""

    def __init__(self, view: QTableView, notify: Callable[[str], None] | None) -> None:
        super().__init__(view)
        self.view = view
        self.notify = notify
        view.installEventFilter(self)
        paste = QShortcut(QKeySequence.StandardKey.Paste, view)
        paste.setContext(Qt.ShortcutContext.WidgetShortcut)
        paste.activated.connect(self.paste)

    def paste(self) -> None:
        text = QGuiApplication.clipboard().text()
        if not text or self.view.state() == QAbstractItemView.State.EditingState:
            return
        done, skipped = paste_text(self.view, text)
        if self.notify is not None and (done or skipped):
            self.notify(
                strings.SHEET_PASTED.format(done)
                + (strings.SHEET_PASTED_SKIPPED.format(skipped) if skipped else "")
            )

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:  # noqa: N802
        if (
            obj is self.view
            and isinstance(event, QKeyEvent)
            and event.type() == QEvent.Type.KeyPress
            and event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter)
            and not event.modifiers()
            and self.view.state() != QAbstractItemView.State.EditingState
        ):
            index = self.view.currentIndex()
            if index.isValid() and bool(index.flags() & Qt.ItemFlag.ItemIsEditable):
                self.view.edit(index)
                return True
        return False


# ---- columns that can be hidden --------------------------------------------------------------------


class ColumnMenu(QObject):
    """A context menu on the header with a tick per column. The hidden columns are kept in the
    program's settings under `tables/<key>/hidden`; the first column (the ID) cannot be hidden."""

    def __init__(
        self,
        view: QTableView,
        settings: QSettings | None,
        key: str | None,
        *,
        locked: Sequence[int] = (0,),
    ) -> None:
        super().__init__(view)
        self.view = view
        self.settings = settings if key else None
        self.path = f"tables/{key}/hidden"
        self.locked = tuple(locked)
        head = view.horizontalHeader()
        head.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        head.customContextMenuRequested.connect(self.show_menu)
        self.restore()

    def titles(self) -> list[str]:
        model = self.view.model()
        return [
            str(model.headerData(c, Qt.Orientation.Horizontal, Qt.ItemDataRole.DisplayRole))
            for c in range(model.columnCount())
        ]

    def hidden(self) -> list[int]:
        return [c for c in range(self.view.model().columnCount()) if self.view.isColumnHidden(c)]

    def set_hidden(self, column: int, hidden: bool) -> None:
        if hidden and column in self.locked:
            return
        self.view.setColumnHidden(column, hidden)
        if self.settings is not None:
            self.settings.setValue(self.path, json.dumps(self.hidden()))

    def restore(self) -> None:
        if self.settings is None:
            return
        try:
            wanted = json.loads(str(self.settings.value(self.path, "[]")))
        except ValueError:
            return
        cols = self.view.model().columnCount()
        for c in wanted if isinstance(wanted, list) else []:
            if isinstance(c, int) and 0 <= c < cols and c not in self.locked:
                self.view.setColumnHidden(c, True)

    def show_menu(self, pos: Any) -> None:
        menu = QMenu(self.view)
        menu.setAccessibleName(strings.SHEET_COLUMNS_MENU)
        title = menu.addAction(strings.SHEET_COLUMNS_MENU)
        title.setEnabled(False)
        for c, text in enumerate(self.titles()):
            act = menu.addAction(text)
            act.setCheckable(True)
            act.setChecked(not self.view.isColumnHidden(c))
            act.setEnabled(c not in self.locked)
            act.toggled.connect(lambda shown, col=c: self.set_hidden(col, not shown))
        menu.popup(self.view.horizontalHeader().mapToGlobal(pos))
        self.menu = menu  # (kept for tests)


def install_sheet(
    view: QTableView,
    *,
    settings: QSettings | None = None,
    key: str | None = None,
    notify: Callable[[str], None] | None = None,
) -> SheetDelegate:
    """Make `view` behave like a spreadsheet (see the module text). Returns its delegate, which the
    caller may hand to `setItemDelegateForColumn` for special columns it subclasses."""
    view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectItems)
    view.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
    view.setEditTriggers(
        QAbstractItemView.EditTrigger.DoubleClicked
        | QAbstractItemView.EditTrigger.EditKeyPressed
        | QAbstractItemView.EditTrigger.AnyKeyPressed
    )
    delegate = SheetDelegate(view)
    view.setItemDelegate(delegate)
    view.keys = _SheetKeys(view, notify)  # type: ignore[attr-defined]
    view.column_menu = ColumnMenu(view, settings, key)  # type: ignore[attr-defined]
    return delegate
