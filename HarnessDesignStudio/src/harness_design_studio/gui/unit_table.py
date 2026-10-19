"""The Unit table: every unit of the design as a spreadsheet (name, chain and notes edit in place,
paste from Excel fills cells, several selected rows take one edit together).

    table = UnitTable(ctl, settings)                # the Units tab of the left panel

Edits go through the controller (`update_unit`, `update_unit_rows`), so each is one undo step and
respects locks and read-only mode. The selection follows the diagram both ways, like the
Interface table next to it.
"""

from collections import Counter

from PySide6.QtCore import (
    QAbstractTableModel,
    QItemSelectionModel,
    QModelIndex,
    QPersistentModelIndex,
    QSettings,
    QSortFilterProxyModel,
    Qt,
)
from PySide6.QtWidgets import (
    QComboBox,
    QHeaderView,
    QLineEdit,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from harness_design_studio.gui import strings
from harness_design_studio.gui.controller import Delta, EditorController
from harness_design_studio.gui.empty_state import attach_empty_state
from harness_design_studio.gui.sheet import SheetDelegate, install_sheet
from harness_design_studio.gui.theme import mono_item_font

COLUMNS = strings.UNIT_COLUMNS
EDITABLE = {1, 4, 7}
NUMERIC_COLUMNS = {5, 6}
MONO_COLUMNS = {0}
CHAINS = ["nominal", "redundant", "none"]


class UnitModel(QAbstractTableModel):
    def __init__(self, ctl: EditorController) -> None:
        super().__init__()
        self.ctl = ctl
        self.ids: list[str] = []
        self.links: Counter[str] = Counter()
        self.connectors: Counter[str] = Counter()
        self.reload()

    def reload(self) -> bool:
        """Follow the project; True when the rows changed (a reset), False when only values did."""
        p = self.ctl.project
        self.links = Counter(e.unit_id for i in p.interfaces.values() for e in i.endpoints)
        self.connectors = Counter(c.unit_id for c in p.connectors.values() if c.unit_id)
        ids = sorted(p.units)
        if ids == self.ids and ids:
            self.dataChanged.emit(self.index(0, 0), self.index(len(ids) - 1, len(COLUMNS) - 1))
            return False
        self.beginResetModel()
        self.ids = ids
        self.endResetModel()
        return True

    def rowCount(self, parent: QModelIndex | QPersistentModelIndex = QModelIndex()) -> int:  # noqa: B008, N802
        return 0 if parent.isValid() else len(self.ids)

    def columnCount(self, parent: QModelIndex | QPersistentModelIndex = QModelIndex()) -> int:  # noqa: B008, N802
        return 0 if parent.isValid() else len(COLUMNS)

    def headerData(  # noqa: N802
        self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole
    ) -> object:
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return COLUMNS[section]
        return None

    def is_editable(self, column: int) -> bool:
        return column in EDITABLE and not self.ctl.read_only

    def flags(self, index: QModelIndex | QPersistentModelIndex) -> Qt.ItemFlag:
        f = super().flags(index)
        if self.is_editable(index.column()):
            f |= Qt.ItemFlag.ItemIsEditable
        return f

    def search_text(self, row: int) -> str:
        u = self.ctl.project.units.get(self.ids[row])
        if u is None:
            return ""
        return " ".join([u.id, u.name, u.subsystem, u.zone or "", u.side, u.notes]).lower()

    def data(  # noqa: PLR0911
        self, index: QModelIndex | QPersistentModelIndex, role: int = Qt.ItemDataRole.DisplayRole
    ) -> object:
        if not index.isValid() or index.row() >= len(self.ids):
            return None
        u = self.ctl.project.units.get(self.ids[index.row()])
        if u is None:
            return None
        col = index.column()
        if role in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole):
            return [
                u.id, u.name, u.subsystem, u.zone or "", u.side,
                self.links[u.id], self.connectors[u.id],
                u.notes.replace("\n", " ") if role == Qt.ItemDataRole.DisplayRole else u.notes,
            ][col]  # fmt: skip
        if role == Qt.ItemDataRole.TextAlignmentRole and col in NUMERIC_COLUMNS:
            return int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        if role == Qt.ItemDataRole.FontRole and col in MONO_COLUMNS:
            return mono_item_font()
        if role == Qt.ItemDataRole.AccessibleTextRole:
            return f"{COLUMNS[col]} of {u.id}: {self.data(index, Qt.ItemDataRole.DisplayRole)}"
        return None

    def setData(  # noqa: N802
        self,
        index: QModelIndex | QPersistentModelIndex,
        value: object,
        role: int = Qt.ItemDataRole.EditRole,
    ) -> bool:
        if role != Qt.ItemDataRole.EditRole or index.column() not in EDITABLE:
            return False
        return self.set_cells([(index.row(), index.column(), str(value))])

    def set_cells(self, cells: list[tuple[int, int, str]]) -> bool:
        """Apply edits `(row, column, text)` as one undoable step; one invalid cell says why and
        nothing is changed."""
        changes: dict[str, dict[str, object]] = {}
        units = self.ctl.project.units
        for row, col, raw in cells:
            if col not in EDITABLE or not 0 <= row < len(self.ids):
                continue
            uid = self.ids[row]
            u = units[uid]
            field = changes.setdefault(uid, {})
            if col == 1:
                text = raw.strip()
                if "\n" in text or "\r" in text or not text:
                    self.ctl.message.emit(strings.NAME_ONE_LINE, False)
                    return False
                if text != u.name:
                    field["name"] = text
            elif col == 4:
                text = raw.strip()
                if text not in CHAINS:
                    self.ctl.message.emit(strings.CHAIN_HELP, False)
                    return False
                if text != u.side:
                    field["side"] = text
            else:
                text = raw.replace("\r\n", "\n").strip("\n")
                if text != u.notes:
                    field["notes"] = text
        changes = {uid: f for uid, f in changes.items() if f}
        if not changes:
            return True
        if len(cells) == 1:
            uid = next(iter(changes))
            return self.ctl.update_unit(uid, **changes[uid])
        return self.ctl.update_unit_rows(changes, strings.STEP_PASTE.format(len(cells)))


class _RowFilter(QSortFilterProxyModel):
    """Match every typed word against the ID, name, subsystem, zone, chain and notes."""

    words: tuple[str, ...] = ()

    def set_text(self, text: str) -> None:
        self.beginFilterChange()
        self.words = tuple(text.lower().split())
        self.endFilterChange()

    def filterAcceptsRow(  # noqa: N802
        self, source_row: int, source_parent: QModelIndex | QPersistentModelIndex
    ) -> bool:
        model = self.sourceModel()
        if not self.words or not isinstance(model, UnitModel):
            return True
        return all(w in model.search_text(source_row) for w in self.words)


class _ChainDelegate(SheetDelegate):
    def createEditor(  # noqa: N802
        self, parent: QWidget, option: object, index: QModelIndex | QPersistentModelIndex
    ) -> QWidget:
        cb = QComboBox(parent)
        cb.addItems(CHAINS)
        return cb

    def setEditorData(  # noqa: N802
        self, editor: QWidget, index: QModelIndex | QPersistentModelIndex
    ) -> None:
        editor.setCurrentText(str(index.data(Qt.ItemDataRole.EditRole)))  # type: ignore[attr-defined]


class UnitTable(QWidget):
    def __init__(self, ctl: EditorController, settings: QSettings | None = None) -> None:
        super().__init__()
        self.ctl = ctl
        self.setObjectName("unit-table")
        self.scale_factor = 1.0
        lay = QVBoxLayout(self)
        self.filter = QLineEdit()
        self.filter.setPlaceholderText(strings.UNIT_FILTER_PLACEHOLDER)
        self.filter.setAccessibleName(strings.UNIT_FILTER_PLACEHOLDER)
        self.filter.setClearButtonEnabled(True)
        lay.addWidget(self.filter)
        self.model = UnitModel(ctl)
        self.proxy = _RowFilter()
        self.proxy.setSourceModel(self.model)
        self.view = QTableView()
        self.view.setObjectName("units")
        self.view.setAccessibleName(strings.UNIT_TABLE)
        self.view.setModel(self.proxy)
        self.view.setSortingEnabled(True)
        self.view.sortByColumn(0, Qt.SortOrder.AscendingOrder)
        install_sheet(self.view, settings=settings, key="units", notify=self._notify)
        self.view.setItemDelegateForColumn(4, _ChainDelegate(self.view))
        header = self.view.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header.setStretchLastSection(True)
        self._apply_widths()
        self.view.verticalHeader().hide()
        lay.addWidget(self.view)
        attach_empty_state(self.view, strings.EMPTY_UNITS_TITLE, strings.EMPTY_UNITS_HINT)
        self.filter.textChanged.connect(self.proxy.set_text)
        self.view.selectionModel().selectionChanged.connect(self._row_selected)
        ctl.changed.connect(self._changed)
        ctl.selectionChanged.connect(self._sync_if_visible)
        self._busy = False
        self._dirty = False

    def _notify(self, text: str) -> None:
        self.ctl.message.emit(text, True)

    def _apply_widths(self) -> None:
        for col, width in enumerate((110, 220, 130, 110, 100, 90, 100)):
            self.view.setColumnWidth(col, round(width * self.scale_factor))

    def _changed(self, delta: Delta) -> None:
        if delta.full or delta.units or delta.interfaces or delta.tables:
            self._dirty = True
            if self.isVisible():
                self.refresh()

    def refresh(self) -> None:
        self._dirty = False
        if self.model.reload():
            self._apply_widths()
            self._sync_selection()

    def showEvent(self, event: object) -> None:  # noqa: N802
        super().showEvent(event)  # type: ignore[arg-type]
        if self._dirty:
            self.refresh()

    def _selected_ids(self) -> list[str]:
        sel = self.view.selectionModel()
        rows = sorted({i.row() for i in sel.selectedIndexes()}) if sel else []
        return [str(self.proxy.index(r, 0).data(Qt.ItemDataRole.DisplayRole)) for r in rows]

    def _row_selected(self) -> None:
        if self._busy:
            return
        ids = self._selected_ids()
        if not ids:
            return
        current = self.view.currentIndex()
        head = (
            str(self.proxy.index(current.row(), 0).data(Qt.ItemDataRole.DisplayRole))
            if current.isValid()
            else ids[-1]
        )
        self._busy = True
        try:
            if len(ids) == 1:
                self.ctl.select("unit", ids[0])
            else:
                self.ctl.select_many(
                    [("unit", i) for i in ids], primary=("unit", head if head in ids else ids[-1])
                )
        finally:
            self._busy = False

    def _sync_if_visible(self) -> None:
        if self.isVisible():
            self._sync_selection()

    def _sync_selection(self) -> None:
        if self._busy:
            return
        wanted = [x.id for x in self.ctl.selected if x.kind == "unit"]
        self._busy = True
        self.view.clearSelection()
        for uid in wanted:
            if uid in self.model.ids:
                idx = self.proxy.mapFromSource(self.model.index(self.model.ids.index(uid), 0))
                if idx.isValid():
                    self.view.selectionModel().select(
                        idx,
                        QItemSelectionModel.SelectionFlag.Select
                        | QItemSelectionModel.SelectionFlag.Rows,
                    )
        self._busy = False
