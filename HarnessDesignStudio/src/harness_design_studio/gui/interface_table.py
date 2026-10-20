"""The Interface table: every interface of the design as a sortable, filterable table whose cells
edit in place (name, redundancy, maximum current, requirement ID).

    table = InterfaceTable(ctl)                      # the Interfaces tab of the window
    table.newInterfaceRequested.connect(window.new_interface_flow)

It is the keyboard and screen-reader alternative to the diagram: the arrow keys move between rows,
Enter or F2 edits a cell, Delete removes the selected interface (through the window's Delete flow),
and the selection follows the diagram both ways. Every edit goes through the controller
(`ctl.update_interface`), so it is one undo step and respects locks and read-only mode.
"""

from PySide6.QtCore import (
    QAbstractTableModel,
    QItemSelectionModel,
    QModelIndex,
    QPersistentModelIndex,
    QSettings,
    QSortFilterProxyModel,
    Qt,
    Signal,
)
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLineEdit,
    QPushButton,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from harness_design_studio.core.model import InterfaceInstance
from harness_design_studio.gui import strings
from harness_design_studio.gui.controller import Delta, EditorController
from harness_design_studio.gui.empty_state import attach_empty_state
from harness_design_studio.gui.panels import format_number, parse_optional_float
from harness_design_studio.gui.sheet import SheetDelegate, install_sheet
from harness_design_studio.gui.theme import mono_item_font

COLUMNS = strings.INTERFACE_COLUMNS
EDITABLE = {1, 5, 6, 7}
NUMERIC_COLUMNS = {6}  # right-aligned, the unit is in the header
MONO_COLUMNS = {0, 7}  # ID and requirement ID read in the monospace font
CHAINS = ["nominal", "redundant", "none"]


class InterfaceModel(QAbstractTableModel):
    def __init__(self, ctl: EditorController) -> None:
        super().__init__()
        self.ctl = ctl
        self.ids: list[str] = []
        self.reload()

    def reload(self) -> bool:
        """Follow the project. Returns True when the rows changed (a reset); the same rows only get
        new values, which keeps column widths and selection and is much cheaper with many rows."""
        ids = sorted(self.ctl.project.interfaces)
        if ids == self.ids and ids:
            self.dataChanged.emit(self.index(0, 0), self.index(len(ids) - 1, len(COLUMNS) - 1))
            return False
        self.beginResetModel()
        self.ids = ids
        self.endResetModel()
        return True

    def rowCount(self, parent: QModelIndex | QPersistentModelIndex = QModelIndex()) -> int:  # noqa: B008
        return 0 if parent.isValid() else len(self.ids)

    def columnCount(self, parent: QModelIndex | QPersistentModelIndex = QModelIndex()) -> int:  # noqa: B008
        return 0 if parent.isValid() else len(COLUMNS)

    def headerData(
        self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole
    ) -> object:
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return COLUMNS[section]
        return None

    def flags(self, index: QModelIndex | QPersistentModelIndex) -> Qt.ItemFlag:
        f = super().flags(index)
        if index.column() in EDITABLE and not self.ctl.read_only:
            f |= Qt.ItemFlag.ItemIsEditable
        return f

    def search_text(self, row: int) -> str:
        i = self.ctl.project.interfaces.get(self.ids[row])
        if i is None:
            return ""
        t = self.ctl.project.interface_types.get(i.type_id)
        parts = [i.id, i.name, i.type_id, t.name if t else "", i.requirement_id or "", i.redundancy]
        parts += [e.unit_id for e in i.endpoints]
        return " ".join(parts).lower()

    def _end(self, i: InterfaceInstance, k: int) -> str:
        e = i.endpoints[k]
        name = e.unit_id
        if self.ctl.mode == "expert" and e.connector_id:
            c = self.ctl.project.connectors.get(e.connector_id)
            name += f".{c.name}" if c else ""
        return name + (" (auto)" if e.auto else "")

    def data(
        self, index: QModelIndex | QPersistentModelIndex, role: int = Qt.ItemDataRole.DisplayRole
    ) -> object:
        if not index.isValid() or index.row() >= len(self.ids):
            return None
        i = self.ctl.project.interfaces.get(self.ids[index.row()])
        if i is None:
            return None
        col = index.column()
        if role in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole):
            t = self.ctl.project.interface_types.get(i.type_id)
            return [
                i.id, i.name, t.name if t else i.type_id, self._end(i, 0), self._end(i, 1), i.redundancy,
                format_number(i.max_current_a), i.requirement_id or "",
            ][col]  # fmt: skip
        if role == Qt.ItemDataRole.TextAlignmentRole and col in NUMERIC_COLUMNS:
            return int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        if role == Qt.ItemDataRole.AccessibleTextRole:
            return f"{COLUMNS[col]} of {i.id}: {self.data(index, Qt.ItemDataRole.DisplayRole)}"
        if role == Qt.ItemDataRole.FontRole and col in MONO_COLUMNS:
            return mono_item_font()  # IDs and requirement IDs
        return None

    def is_editable(self, column: int) -> bool:
        return column in EDITABLE and not self.ctl.read_only

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
        """Apply edits `(row, column, text)` as one undoable step. Every cell is checked first;
        one that is not valid says why and nothing is changed."""
        changes: dict[str, dict[str, object]] = {}
        for row, col, raw in cells:
            if col not in EDITABLE or not 0 <= row < len(self.ids):
                continue
            iid = self.ids[row]
            text = raw.strip()
            field = changes.setdefault(iid, {})
            if col == 1:
                if (
                    "\n" in text or "\r" in text
                ):  # a name is one line (the form field cannot hold more)
                    self.ctl.message.emit(strings.NAME_ONE_LINE, False)
                    return False
                field["name"] = text
            elif col == 5:
                if text not in CHAINS:
                    self.ctl.message.emit(strings.CHAIN_HELP, False)
                    return False
                field["redundancy"] = text
            elif col == 6:
                num, err = parse_optional_float(text)
                if err:
                    self.ctl.message.emit(err, False)
                    return False
                if num != self.ctl.project.interfaces[iid].max_current_a:
                    field["max_current_a"] = num
            else:
                field["requirement_id"] = text or None
        changes = {iid: f for iid, f in changes.items() if f}
        if not changes:
            return True  # nothing differs: not an edit
        if len(cells) == 1:
            iid = next(iter(changes))
            return self.ctl.update_interface(iid, **changes[iid])
        return self.ctl.update_interface_rows(changes, strings.STEP_PASTE.format(len(cells)))


class _RowFilter(QSortFilterProxyModel):
    """Match every word typed against the ID, name, type (name and ID), units and requirement."""

    words: tuple[str, ...] = ()  # the typed words as they are (not a pattern)

    def set_text(self, text: str) -> None:
        self.beginFilterChange()
        self.words = tuple(text.lower().split())
        self.endFilterChange()

    def filterAcceptsRow(
        self, source_row: int, source_parent: QModelIndex | QPersistentModelIndex
    ) -> bool:
        model = self.sourceModel()
        if not self.words or not isinstance(model, InterfaceModel):
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


class InterfaceTable(QWidget):
    newInterfaceRequested = Signal()

    def __init__(self, ctl: EditorController, settings: QSettings | None = None) -> None:
        super().__init__()
        self.ctl = ctl
        self.setObjectName("interface-table")
        self.scale_factor = 1.0
        lay = QVBoxLayout(self)
        top = QHBoxLayout()
        self.filter = QLineEdit()
        self.filter.setPlaceholderText(strings.FILTER_PLACEHOLDER)
        self.filter.setAccessibleName(strings.FILTER_PLACEHOLDER)
        self.filter.setClearButtonEnabled(True)
        self.add_btn = QPushButton(strings.NEW_INTERFACE)
        self.add_btn.setObjectName("new-interface")
        self.add_btn.clicked.connect(self.newInterfaceRequested)
        top.addWidget(self.filter, 1)
        top.addWidget(self.add_btn)
        lay.addLayout(top)
        self.model = InterfaceModel(ctl)
        self.proxy = _RowFilter()
        self.proxy.setSourceModel(self.model)
        self.proxy.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.proxy.setFilterKeyColumn(-1)
        self.view = QTableView()
        self.view.setObjectName("interfaces")
        self.view.setAccessibleName(strings.INTERFACE_TABLE)
        self.view.setModel(self.proxy)
        self.view.setSortingEnabled(True)
        self.view.sortByColumn(0, Qt.SortOrder.AscendingOrder)  # IF-001 first
        install_sheet(self.view, settings=settings, key="interfaces", notify=self._notify)
        self.view.setItemDelegateForColumn(5, _ChainDelegate(self.view))
        header = self.view.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header.setStretchLastSection(True)
        self._apply_widths()
        self.view.verticalHeader().hide()
        lay.addWidget(self.view)
        attach_empty_state(
            self.view,
            strings.EMPTY_INTERFACES_TITLE,
            strings.EMPTY_INTERFACES_HINT,
            action=strings.EMPTY_INTERFACES_ACTION,
            on_action=self.newInterfaceRequested.emit,
        )
        self.filter.textChanged.connect(self._set_filter)
        self.view.selectionModel().selectionChanged.connect(self._row_selected)
        ctl.changed.connect(self._changed)
        ctl.modeChanged.connect(self._mode_changed)
        ctl.selectionChanged.connect(self._sync_if_visible)
        ctl.stateChanged.connect(lambda: self.add_btn.setEnabled(not ctl.read_only))
        self._busy = False
        self._dirty = False

    def _mode_changed(self) -> None:
        self._dirty = True
        if self.isVisible():
            self.refresh()

    def _set_filter(self, text: str) -> None:
        self.proxy.set_text(text)

    def _changed(self, delta: Delta) -> None:
        if delta.full or delta.interfaces or delta.units:
            self._dirty = True
            if self.isVisible():
                self.refresh()

    def _apply_widths(self) -> None:
        for col, width in enumerate((120, 260, 150, 130, 130, 100, 70)):
            self.view.setColumnWidth(col, self.ctl_scale(width))

    def ctl_scale(self, px: int) -> int:
        return round(px * self.scale_factor)

    def refresh(self) -> None:
        self._dirty = False
        if self.model.reload():  # a model reset restores default column widths
            self._apply_widths()
            self._sync_selection()

    def showEvent(self, event: object) -> None:
        super().showEvent(event)  # type: ignore[arg-type]
        if self._dirty:
            self.refresh()

    def _notify(self, text: str) -> None:
        self.ctl.message.emit(text, True)

    def _selected_ids(self) -> list[str]:
        """The interfaces that have a selected cell, in the order shown."""
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
        self._busy = True
        try:
            if len(ids) == 1:
                self.ctl.select("interface", ids[0])
            else:
                head = (
                    str(self.proxy.index(current.row(), 0).data(Qt.ItemDataRole.DisplayRole))
                    if current.isValid() and str(self.proxy.index(current.row(), 0).data()) in ids
                    else ids[-1]
                )
                self.ctl.select_many([("interface", i) for i in ids], primary=("interface", head))
        finally:
            self._busy = False

    def _sync_if_visible(self) -> None:
        if self.isVisible():
            self._sync_selection()

    def _sync_selection(self) -> None:
        if self._busy:
            return
        wanted = [x.id for x in self.ctl.selected if x.kind == "interface"]
        self._busy = True
        self.view.clearSelection()
        for iid in wanted:
            if iid in self.model.ids:
                src = self.model.index(self.model.ids.index(iid), 0)
                idx = self.proxy.mapFromSource(src)
                if idx.isValid():
                    self.view.selectionModel().select(
                        idx,
                        QItemSelectionModel.SelectionFlag.Select
                        | QItemSelectionModel.SelectionFlag.Rows,
                    )
        self._busy = False
