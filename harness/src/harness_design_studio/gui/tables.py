"""Shared table code: one model, one proxy, one view setup, TSV copy and saved column widths.

Every list of rows in the program is a `QTableView` over a `QAbstractTableModel`, never a
`QTableWidget` filled cell by cell:

    cols = [
        Column("id", "Wire", mono=True),
        Column("gauge", "Gauge", unit="AWG", numeric=True, state="gauge_state"),
        Column("length", "Length", unit="m", numeric=True, fmt=lambda v: f"{v:g}"),
    ]
    view = TableView(DictTableModel(cols, rows, theme), theme, name="Wire list",
                     settings=settings, key="wires")

A column says how its cells look: unit suffix in the header, alignment (numbers right-aligned with
tabular figures), monospace (pin, wire and part numbers), a state (pending, locked ... painted by
`StateDelegate` as icon + word + pattern), a tooltip and a sort key. Ctrl+C copies the selected
cells as tab-separated text (Ctrl+Shift+C adds the header row), and column widths and the sort
order are saved per table.
"""

import re
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Final, Literal

from PySide6.QtCore import (
    QAbstractTableModel,
    QModelIndex,
    QObject,
    QPersistentModelIndex,
    QSettings,
    QSortFilterProxyModel,
    Qt,
    QTimer,
)
from PySide6.QtGui import QFont, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QHeaderView,
    QTableView,
    QWidget,
)

from harness_design_studio.gui import strings
from harness_design_studio.gui.states import STATE_ROLE, STATES, StateDelegate
from harness_design_studio.gui.theme import ThemeManager, mono_item_font

SORT_ROLE: Final = int(Qt.ItemDataRole.UserRole) + 2  # what a cell sorts by (any comparable value)
ROW_ROLE: Final = int(Qt.ItemDataRole.UserRole) + 3  # the whole row (dict or tuple) of a cell

Row = Mapping[Any, Any] | Sequence[Any]
Align = Literal["left", "right", "center"]
Spec = str | int | Callable[[Row], Any] | None  # a field of the row, or a function of the row

_ALIGN: Final = {
    "left": Qt.AlignmentFlag.AlignLeft,
    "right": Qt.AlignmentFlag.AlignRight,
    "center": Qt.AlignmentFlag.AlignHCenter,
}


@dataclass(frozen=True)
class Column:
    """How one column reads its rows and looks.

    `key`      field of the row: a dict key or a tuple index.
    `header`   header text; `unit` is added as "Length (m)".
    `numeric`  right-aligned with tabular figures, sorted as numbers (blank cells first).
    `align`    "left", "right" or "center"; default right for numbers, else left.
    `mono`     monospace font (pin, wire and part numbers, IDs, hashes, paths).
    `state`    a field of the row (or a function of the row) holding a state key of
               `gui.states.STATES`, or None: the cell is then painted as a chip.
    `tooltip`  a field of the row or a function of the row giving the cell's tooltip.
    `sort_key` function of the cell value giving what to sort by (default: natural order of the
               text, or the number).
    `fmt`      function of the cell value giving the shown text (default: str(value), "" for None).
    `width`    initial width in px at 100 % scale; 0 means fit the content.
    """

    key: str | int
    header: str
    unit: str = ""
    numeric: bool = False
    align: Align | None = None
    mono: bool = False
    state: Spec = None
    tooltip: Spec = None
    sort_key: Callable[[Any], Any] | None = None
    fmt: Callable[[Any], str] | None = None
    width: int = 0

    @property
    def title(self) -> str:
        return (
            strings.TABLE_HEADER_UNIT.format(self.header, self.unit) if self.unit else self.header
        )

    @property
    def alignment(self) -> Align:
        return self.align or ("right" if self.numeric else "left")


_NATURAL = re.compile(r"(\d+)")


def natural_key(text: str) -> tuple[tuple[int, int | str], ...]:
    """Sort key that orders "J2" before "J10" and ignores case."""
    return tuple(
        (0, int(part)) if part.isdigit() else (1, part.casefold())
        for part in _NATURAL.split(text)
        if part != ""
    )


def _get(row: Row, key: str | int) -> Any:
    if isinstance(row, Mapping):
        return row.get(key)
    if isinstance(key, int) and -len(row) <= key < len(row):
        return row[key]
    return None


def _spec_value(spec: Spec, row: Row) -> Any:
    if spec is None:
        return None
    if callable(spec):
        return spec(row)
    return _get(row, spec)


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


class DictTableModel(QAbstractTableModel):
    """Read-only table model over rows given as dicts or tuples, described by `Column`s."""

    def __init__(
        self,
        columns: Sequence[Column],
        rows: Iterable[Row] = (),
        theme: ThemeManager | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.columns: list[Column] = list(columns)
        self._rows: list[Row] = list(rows)
        self.theme = theme
        self._mono = mono_item_font()
        self._tabular = QFont()
        self._tabular.setFeature(QFont.Tag("tnum"), 1)

    # ---- rows ----------------------------------------------------------------------------
    def rows(self) -> list[Row]:
        return list(self._rows)

    def row(self, i: int) -> Row:
        return self._rows[i]

    def set_rows(self, rows: Iterable[Row]) -> None:
        """Replace all rows (the view loses its selection)."""
        self.beginResetModel()
        self._rows = list(rows)
        self.endResetModel()

    def update_rows(self, rows: Iterable[Row]) -> bool:
        """Follow new data. The same number of rows only gets new values (selection, scroll
        position and widths stay; cheaper with many rows); otherwise this is `set_rows`. Returns
        True when the rows were replaced."""
        new = list(rows)
        if len(new) != len(self._rows) or not new:
            self.set_rows(new)
            return True
        self._rows = new
        self.dataChanged.emit(
            self.index(0, 0), self.index(len(new) - 1, max(0, len(self.columns) - 1))
        )
        return False

    def column_index(self, key: str | int) -> int:
        for i, c in enumerate(self.columns):
            if c.key == key:
                return i
        raise KeyError(key)

    # ---- the Qt model interface ----------------------------------------------------------
    def rowCount(self, parent: QModelIndex | QPersistentModelIndex = QModelIndex()) -> int:  # noqa: B008, N802
        return 0 if parent.isValid() else len(self._rows)

    def columnCount(self, parent: QModelIndex | QPersistentModelIndex = QModelIndex()) -> int:  # noqa: B008, N802
        return 0 if parent.isValid() else len(self.columns)

    def flags(self, index: QModelIndex | QPersistentModelIndex) -> Qt.ItemFlag:
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags
        return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable

    def text_at(self, row: int, col: int) -> str:
        """The text shown in a cell."""
        c = self.columns[col]
        value = _get(self._rows[row], c.key)
        if c.fmt is not None:
            return c.fmt(value)
        return "" if value is None else str(value)

    def state_at(self, row: int, col: int) -> str | None:
        state = _spec_value(self.columns[col].state, self._rows[row])
        return state if isinstance(state, str) and state in STATES else None

    def sort_value(self, row: int, col: int) -> Any:
        c = self.columns[col]
        value = _get(self._rows[row], c.key)
        if c.sort_key is not None:
            return c.sort_key(value)
        if c.numeric:
            return _number(value)
        return natural_key("" if value is None else str(value))

    def headerData(  # noqa: N802
        self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole
    ) -> Any:
        if orientation == Qt.Orientation.Vertical:
            return str(section + 1) if role == Qt.ItemDataRole.DisplayRole else None
        if not 0 <= section < len(self.columns):
            return None
        c = self.columns[section]
        if role in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.ToolTipRole):
            return c.title
        if role == Qt.ItemDataRole.TextAlignmentRole:
            return int(_ALIGN[c.alignment] | Qt.AlignmentFlag.AlignVCenter)
        return None

    def data(
        self, index: QModelIndex | QPersistentModelIndex, role: int = Qt.ItemDataRole.DisplayRole
    ) -> Any:
        if not index.isValid() or not 0 <= index.row() < len(self._rows):
            return None
        r, k = index.row(), index.column()
        c = self.columns[k]
        row = self._rows[r]
        if role == Qt.ItemDataRole.DisplayRole:
            return self.text_at(r, k)
        if role == Qt.ItemDataRole.EditRole:
            return _get(row, c.key)
        if role == Qt.ItemDataRole.TextAlignmentRole:
            return int(_ALIGN[c.alignment] | Qt.AlignmentFlag.AlignVCenter)
        if role == Qt.ItemDataRole.FontRole:
            if c.mono:
                return self._mono
            return self._tabular if c.numeric else None
        if role == STATE_ROLE:
            return self.state_at(r, k)
        if role == SORT_ROLE:
            return self.sort_value(r, k)
        if role == ROW_ROLE:
            return row
        if role == Qt.ItemDataRole.ToolTipRole:
            tip = _spec_value(c.tooltip, row)
            if tip:
                return str(tip)
            state = self.state_at(r, k)
            return STATES[state].label if state else None
        if role == Qt.ItemDataRole.AccessibleTextRole:
            state = self.state_at(r, k)
            text = self.text_at(r, k)
            shown = f"{STATES[state].label} {text}".strip() if state else text
            return f"{c.title}: {shown}"
        return None


class TableProxy(QSortFilterProxyModel):
    """Sorting by `SORT_ROLE` (numbers as numbers, "J2" before "J10") and filtering by typed
    words, by state and by a row predicate; the three combine."""

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.setSortRole(SORT_ROLE)
        self.setDynamicSortFilter(True)
        self.setSortCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self._words: tuple[str, ...] = ()
        self._states: frozenset[str] | None = None
        self._predicate: Callable[[Row], bool] | None = None

    def set_text(self, text: str) -> None:
        """Keep rows where every typed word occurs in some cell (case-insensitive)."""
        self.beginFilterChange()
        self._words = tuple(text.lower().split())
        self.endFilterChange()

    def set_states(self, states: Iterable[str] | None) -> None:
        """Keep rows with a cell in one of these states (None: all rows)."""
        self.beginFilterChange()
        self._states = None if states is None else frozenset(states)
        self.endFilterChange()

    def set_predicate(self, predicate: Callable[[Row], bool] | None) -> None:
        self.beginFilterChange()
        self._predicate = predicate
        self.endFilterChange()

    def lessThan(  # noqa: N802
        self, left: QModelIndex | QPersistentModelIndex, right: QModelIndex | QPersistentModelIndex
    ) -> bool:
        a, b = left.data(SORT_ROLE), right.data(SORT_ROLE)
        if a is None or b is None:  # blank cells come first
            return a is None and b is not None
        try:
            return bool(a < b)
        except TypeError:  # mixed kinds: fall back to the text
            return str(a) < str(b)

    def filterAcceptsRow(  # noqa: N802
        self, source_row: int, source_parent: QModelIndex | QPersistentModelIndex
    ) -> bool:
        model = self.sourceModel()
        if not isinstance(model, DictTableModel):
            return True
        if self._predicate is not None and not self._predicate(model.row(source_row)):
            return False
        n = len(model.columns)
        if self._states is not None and not any(
            model.state_at(source_row, k) in self._states for k in range(n)
        ):
            return False
        if self._words:
            text = " ".join(model.text_at(source_row, k) for k in range(n)).lower()
            return all(w in text for w in self._words)
        return True


# ---- copy as TSV ---------------------------------------------------------------------------


def _clean(text: str) -> str:
    return text.replace("\t", " ").replace("\r", " ").replace("\n", " ")


def copy_tsv(view: QAbstractItemView, *, headers: bool = False, clipboard: bool = True) -> str:
    """The selected cells as tab-separated text, in the order shown (sorted, columns as arranged),
    one line per row; gaps in a ragged selection stay empty. With `headers` the first line holds
    the column titles (units included). The text goes on the clipboard unless `clipboard` is
    False; it is also returned."""
    model, sel = view.model(), view.selectionModel()
    if model is None or sel is None:
        return ""
    cells = {(i.row(), i.column()) for i in sel.selectedIndexes()}
    if not cells:
        return ""
    columns = sorted({c for _, c in cells})
    if isinstance(view, QTableView):
        head = view.horizontalHeader()
        columns = [c for c in columns if not view.isColumnHidden(c)]
        columns.sort(key=head.visualIndex)
    rows = sorted({r for r, _ in cells})
    lines: list[str] = []
    if headers:
        lines.append(
            "\t".join(
                _clean(str(model.headerData(c, Qt.Orientation.Horizontal) or "")) for c in columns
            )
        )
    for r in rows:
        lines.append(
            "\t".join(
                _clean(str(model.index(r, c).data(Qt.ItemDataRole.DisplayRole) or ""))
                if (r, c) in cells
                else ""
                for c in columns
            )
        )
    text = "\n".join(lines)
    if clipboard:
        QApplication.clipboard().setText(text)
    return text


def install_copy(view: QAbstractItemView) -> list[QShortcut]:
    """Make Ctrl+C copy the selected cells as TSV and Ctrl+Shift+C the same with the header row."""
    plain = QShortcut(QKeySequence.StandardKey.Copy, view)
    plain.setContext(Qt.ShortcutContext.WidgetShortcut)
    plain.activated.connect(lambda: copy_tsv(view))
    with_headers = QShortcut(QKeySequence("Ctrl+Shift+C"), view)
    with_headers.setContext(Qt.ShortcutContext.WidgetShortcut)
    with_headers.activated.connect(lambda: copy_tsv(view, headers=True))
    return [plain, with_headers]


# ---- saved column widths -------------------------------------------------------------------


class ColumnWidths(QObject):
    """Restores and saves the column widths and sort order of one table under `tables/<key>/`."""

    def __init__(self, view: QTableView, settings: QSettings, key: str) -> None:
        super().__init__(view)
        self.view, self.settings, self.group = view, settings, f"tables/{key}"
        self.restored = False
        self.has_saved = False  # True when saved widths were applied
        self.busy = False  # True while the program (not the person) changes widths
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(300)
        self._timer.timeout.connect(self.save)
        head = view.horizontalHeader()
        head.sectionResized.connect(self._changed)
        head.sortIndicatorChanged.connect(self._changed)
        self.restore()

    def _changed(self, *_: object) -> None:
        if not self.busy and self.restored:
            self._timer.start()

    def restore(self) -> bool:
        """Apply the saved widths if the model has its columns by now; True when it did."""
        if self.restored:
            return True
        model = self.view.model()
        n = model.columnCount() if model is not None else 0
        if n == 0:
            return False
        head = self.view.horizontalHeader()
        raw = str(self.settings.value(f"{self.group}/widths", "") or "")
        try:
            widths = [int(x) for x in raw.split(",")] if raw else []
        except ValueError:
            widths = []
        self.busy = True
        try:
            if len(widths) == n and all(w > 0 for w in widths):
                for i, w in enumerate(widths):
                    head.resizeSection(i, w)
            sort = str(self.settings.value(f"{self.group}/sort", "") or "")
            if self.view.isSortingEnabled() and ":" in sort:
                col, _, order = sort.partition(":")
                if col.isdigit() and int(col) < n:
                    head.setSortIndicator(
                        int(col),
                        Qt.SortOrder.DescendingOrder
                        if order == "d"
                        else Qt.SortOrder.AscendingOrder,
                    )
        finally:
            self.busy = False
        self.has_saved = len(widths) == n
        self.restored = True
        return True

    def save(self) -> None:
        head = self.view.horizontalHeader()
        n = head.count()
        if n == 0:
            return
        self.settings.setValue(
            f"{self.group}/widths", ",".join(str(head.sectionSize(i)) for i in range(n))
        )
        order = "d" if head.sortIndicatorOrder() == Qt.SortOrder.DescendingOrder else "a"
        col = head.sortIndicatorSection() if self.view.isSortingEnabled() else -1
        self.settings.setValue(f"{self.group}/sort", f"{col}:{order}" if col >= 0 else "")


def persist_widths(view: QTableView, settings: QSettings, key: str) -> ColumnWidths:
    """Save the column widths and sort order of `view` in `settings` (as `tables/<key>/...`, a
    moment after the person changes them) and restore them now, or as soon as the model has its
    columns. Returns the helper; `.has_saved` says whether saved widths were applied."""
    helper = ColumnWidths(view, settings, key)
    model = view.model()
    if not helper.restored and model is not None:
        model.modelReset.connect(helper.restore)
        model.columnsInserted.connect(helper.restore)
    return helper


# ---- the view --------------------------------------------------------------------------------


def style_table(view: QTableView, theme: ThemeManager) -> None:
    """The look every table shares: header stays in view while rows scroll, no row numbers,
    cell selection (so Ctrl+C copies what is marked), alternating rows, no wrapping, clickable
    headers with a sort arrow, row height from the font."""
    view.setObjectName(view.objectName() or "table")
    view.setAlternatingRowColors(True)
    view.setWordWrap(False)
    view.setTextElideMode(Qt.TextElideMode.ElideRight)
    view.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectItems)
    view.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
    view.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
    view.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
    view.setShowGrid(False)
    view.verticalHeader().setVisible(False)
    head = view.horizontalHeader()
    head.setSectionsClickable(True)
    head.setSortIndicatorShown(True)
    head.setHighlightSections(False)
    head.setStretchLastSection(True)
    head.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
    head.setMinimumSectionSize(theme.px(40))
    head.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
    height = view.fontMetrics().height() + theme.space(8)
    view.verticalHeader().setDefaultSectionSize(height)
    view.verticalHeader().setMinimumSectionSize(height)


class TableView(QTableView):
    """A table over a `DictTableModel` with sorting and filtering (`proxy`), state chips, TSV
    copy and, when `settings` and `key` are given, saved column widths."""

    def __init__(
        self,
        model: DictTableModel,
        theme: ThemeManager,
        *,
        name: str,
        settings: QSettings | None = None,
        key: str | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.theme = theme
        self.source = model
        self.proxy = TableProxy(self)
        self.proxy.setSourceModel(model)
        self.setModel(self.proxy)
        self.setAccessibleName(name)
        self.setToolTip(strings.TABLE_COPY_TIP)
        self.setSortingEnabled(True)
        self.sortByColumn(-1, Qt.SortOrder.AscendingOrder)  # rows in the order given until a click
        style_table(self, theme)
        self.setItemDelegate(StateDelegate(theme, self))
        install_copy(self)
        self._widths = persist_widths(self, settings, key) if settings and key else None
        self._sized = bool(self._widths and self._widths.has_saved)
        self._fit_columns()
        model.modelReset.connect(self._fit_columns)
        theme.changed.connect(self._restyle)

    def _restyle(self) -> None:
        style_table(self, self.theme)

    def _fit_columns(self) -> None:
        """Give columns their `width` or fit them to the content (once, unless widths were
        saved)."""
        fixed = any(c.width for c in self.source.columns)
        if self._sized or (self.source.rowCount() == 0 and not fixed):
            return
        head = self.horizontalHeader()
        helper = self._widths
        if helper is not None:
            helper.busy = True
        try:
            self.resizeColumnsToContents()
            for k, c in enumerate(self.source.columns):
                if c.width:
                    head.resizeSection(k, self.theme.px(c.width))
                else:
                    wanted = head.sectionSize(k) + self.theme.space(8)
                    head.resizeSection(k, min(wanted, self.theme.px(320)))
        finally:
            if helper is not None:
                helper.busy = False
        self._sized = self.source.rowCount() > 0

    def set_rows(self, rows: Iterable[Row]) -> None:
        self.source.set_rows(rows)

    def row_at(self, index: QModelIndex) -> Row:
        """The row of a cell index of this view (a proxy index)."""
        return self.source.row(self.proxy.mapToSource(index).row())

    def selected_rows(self) -> list[Row]:
        """The rows that have a selected cell, in the order shown."""
        sel = self.selectionModel()
        rows = sorted({i.row() for i in sel.selectedIndexes()}) if sel else []
        return [self.source.row(self.proxy.mapToSource(self.proxy.index(r, 0)).row()) for r in rows]

    def copy_selection(self, *, headers: bool = False) -> str:
        return copy_tsv(self, headers=headers)
