"""The editable pin table of the Devices tab: a `TableView` over a model whose cells can be edited,
with the keyboard of a spreadsheet and inline validation.

Keys (the table has the focus): arrows, Tab and Shift+Tab move between cells (Tab leaves the table
after the last one); F2 or Enter edits the cell; in the editor Enter commits and goes down, Esc
cancels; Insert adds a pin after this one; Delete clears the signal of the selected pins;
Shift+Delete deletes the selected pins (after a line that says what it touches); Space cycles the
mode of the selected pins; Ctrl+L fills the selected pins from an interface type; Ctrl+Enter
assigns them to an interface; Ctrl+V pastes tab-separated cells from a spreadsheet; Ctrl+C and
Ctrl+Shift+C copy.

The table never changes the project: an edited cell is announced with `cellEdited(row, key, value)`
and the Devices view runs it through the controller as one named undo step.
"""

from collections.abc import Callable, Iterable, Sequence
from typing import Any

from PySide6.QtCore import (
    QAbstractItemModel,
    QEvent,
    QModelIndex,
    QObject,
    QPersistentModelIndex,
    QSettings,
    QSortFilterProxyModel,
    Qt,
    Signal,
)
from PySide6.QtGui import QKeyEvent, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QAbstractItemDelegate,
    QAbstractItemView,
    QComboBox,
    QLineEdit,
    QStyleOptionViewItem,
    QWidget,
)

from harness_design_studio.core import devices
from harness_design_studio.core.edit import EditError
from harness_design_studio.gui import strings
from harness_design_studio.gui.states import StateDelegate
from harness_design_studio.gui.tables import Column, DictTableModel, Row, TableView
from harness_design_studio.gui.theme import ThemeManager

EDITABLE = ("pin", "signal", "mode", "contact_size", "termination")
Validator = Callable[[str, dict[str, Any], str], str | None]


def _source(
    model: QAbstractItemModel | None, index: QModelIndex | QPersistentModelIndex
) -> tuple[DictTableModel | None, int, int]:
    """(the table model, row, column) behind an index of the table (which sorts through a proxy)."""
    if isinstance(model, QSortFilterProxyModel):
        mapped = model.mapToSource(index)
        return _source(model.sourceModel(), mapped)
    if isinstance(model, DictTableModel):
        return model, index.row(), index.column()
    return None, -1, -1


def _row(model: QAbstractItemModel, index: QModelIndex | QPersistentModelIndex) -> dict[str, Any]:
    source, r, _c = _source(model, index)
    if source is None:
        return {}
    row = source.row(r)
    return dict(row) if isinstance(row, dict) else {}


class PinModel(DictTableModel):
    """The pin table's model: the cells of `EDITABLE` columns can be edited unless the project is
    read-only or a release locks the pin (`row["lock"]`); the pin name also needs the connector's
    pin set not to be frozen (`row["pin_frozen"]`). An edit does not change the row: it is
    announced with `cellEdited` and the table shows the new value when the project has changed."""

    cellEdited = Signal(int, str, object)

    def __init__(
        self, columns: Sequence[Column], rows: Iterable[Row], theme: ThemeManager | None = None
    ) -> None:
        super().__init__(columns, rows, theme)
        self.read_only = False

    def why_not_editable(self, index: QModelIndex | QPersistentModelIndex) -> str | None:
        """The reason a cell of an editable column cannot be edited, or None."""
        if not index.isValid() or self.columns[index.column()].key not in EDITABLE:
            return None
        if self.read_only:
            return strings.READ_ONLY_REFUSAL
        row = self.row(index.row())
        if not isinstance(row, dict):
            return None
        if row.get("lock"):
            return str(row["lock"])
        if self.columns[index.column()].key == "pin" and row.get("pin_frozen"):
            return str(row["pin_frozen"])
        return None

    def flags(self, index: QModelIndex | QPersistentModelIndex) -> Qt.ItemFlag:
        base = super().flags(index)
        if (
            index.isValid()
            and self.columns[index.column()].key in EDITABLE
            and self.why_not_editable(index) is None
        ):
            return base | Qt.ItemFlag.ItemIsEditable
        return base

    def setData(  # noqa: N802
        self,
        index: QModelIndex | QPersistentModelIndex,
        value: Any,
        role: int = Qt.ItemDataRole.EditRole,
    ) -> bool:
        if role != Qt.ItemDataRole.EditRole or not (self.flags(index) & Qt.ItemFlag.ItemIsEditable):
            return False
        self.cellEdited.emit(index.row(), str(self.columns[index.column()].key), value)
        return True

    def data(
        self, index: QModelIndex | QPersistentModelIndex, role: int = Qt.ItemDataRole.DisplayRole
    ) -> Any:
        if role == Qt.ItemDataRole.ToolTipRole and index.isValid():
            why = self.why_not_editable(index)
            if why:
                return why
        return super().data(index, role)


def _line(box: QComboBox) -> QLineEdit:
    """The text field of an editable combo box."""
    line = box.lineEdit()
    if line is None:
        raise ValueError("the combo box is not editable")
    return line


def _set_invalid(editor: QWidget, message: str | None) -> None:
    editor.setProperty("invalid", bool(message))
    editor.setToolTip(message or "")
    style = editor.style()
    style.unpolish(editor)
    style.polish(editor)


class PinDelegate(StateDelegate):
    """Draws the state chips like every table and makes the editors of the editable cells: a text
    field for the pin and the contact size, a combo box with the signals of the project (and free
    text) for the signal, combo boxes for the mode and the termination. While the person types,
    `validator(key, row, text)` says what is wrong and the editor is marked invalid; a value that
    is wrong is not committed."""

    def __init__(
        self,
        theme: ThemeManager,
        signals: Callable[[], list[tuple[str, str]]],
        validator: Validator,
        report: Callable[[str], None],
        parent: QObject | None = None,
    ) -> None:
        super().__init__(theme, parent)  # type: ignore[arg-type]
        self._signals, self._validator, self._report = signals, validator, report

    def _key(self, index: QModelIndex | QPersistentModelIndex) -> str:
        source, _r, c = _source(index.model(), index)
        return str(source.columns[c].key) if source is not None else ""

    def createEditor(  # noqa: N802
        self,
        parent: QWidget,
        option: QStyleOptionViewItem,
        index: QModelIndex | QPersistentModelIndex,
    ) -> QWidget:  # (None for a cell that is not edited: the view then does not edit)
        key = self._key(index)
        model = index.model()
        row = _row(model, index) if model is not None else {}
        if key not in EDITABLE:
            return None  # type: ignore[return-value]
        editor: QWidget
        if key == "mode":
            box = QComboBox(parent)
            for mode, word in strings.DV_MODE.items():
                box.addItem(word, mode)
            box.setAccessibleName(strings.DV_COL_MODE)
            editor = box
        elif key == "termination":
            box = QComboBox(parent)
            box.addItem("", "unspecified")
            box.addItem(strings.DV_TERMINATION["crimp"], "crimp")
            box.addItem(strings.DV_TERMINATION["solder"], "solder")
            box.setAccessibleName(strings.DV_COL_TERMINATION)
            editor = box
        elif key == "signal":
            box = QComboBox(parent)
            box.setEditable(True)
            box.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)  # (Enter must not add an item)
            box.addItem("", "")
            for name, group in self._signals():
                box.addItem(f"{name}  ({group})", name)
            box.setAccessibleName(strings.DV_COL_SIGNAL)
            box.setToolTip(strings.DV_SIGNAL_EDIT_TIP)
            _line(box).textChanged.connect(lambda t: self._check(box, key, row, t))
            editor = box
        else:
            line = QLineEdit(parent)
            line.setAccessibleName(
                strings.DV_COL_PIN if key == "pin" else strings.DV_COL_CONTACT_SIZE
            )
            line.textChanged.connect(lambda t: self._check(line, key, row, t))
            editor = line
        return editor

    def _check(self, editor: QWidget, key: str, row: dict[str, Any], text: str) -> None:
        message = self._validator(key, row, text)
        _set_invalid(editor, message)
        self._report(message or "")

    def setEditorData(  # noqa: N802
        self, editor: QWidget, index: QModelIndex | QPersistentModelIndex
    ) -> None:
        key = self._key(index)
        row = _row(index.model(), index)
        if isinstance(editor, QComboBox):
            if key == "signal":
                _line(editor).setText(str(row.get("signal") or ""))
            elif key == "mode":
                editor.setCurrentIndex(max(0, editor.findData(row.get("mode_key", "free"))))
            else:
                editor.setCurrentIndex(
                    max(0, editor.findData(row.get("termination_key", "unspecified")))
                )
        elif isinstance(editor, QLineEdit):
            editor.setText(str(row.get(key) or ""))
            editor.selectAll()

    def setModelData(  # noqa: N802
        self,
        editor: QWidget,
        model: QAbstractItemModel,
        index: QModelIndex | QPersistentModelIndex,
    ) -> None:
        key = self._key(index)
        row = _row(model, index)
        value: Any
        if isinstance(editor, QComboBox):
            if key == "signal":
                text = _line(editor).text().strip()
                pos = editor.findText(_line(editor).text())
                data = editor.itemData(pos) if pos >= 0 else None
                value = data if isinstance(data, str) and data else text
            else:
                value = editor.currentData()
        elif isinstance(editor, QLineEdit):
            value = editor.text().strip()
        else:
            return
        message = self._validator(key, row, str(value))
        if message:
            self._report(message)
            return
        self._report("")
        model.setData(index, value, Qt.ItemDataRole.EditRole)

    def updateEditorGeometry(  # noqa: N802
        self,
        editor: QWidget,
        option: QStyleOptionViewItem,
        index: QModelIndex | QPersistentModelIndex,
    ) -> None:
        editor.setGeometry(option.rect)


class PinTable(TableView):
    """`TableView` with the editing keys of the module text. Requests are signals; the Devices
    view acts on them."""

    insertRequested = Signal()
    deleteRequested = Signal()  # Shift+Delete
    clearRequested = Signal()  # Delete
    cycleModeRequested = Signal()  # Space
    fillRequested = Signal()  # Ctrl+L
    assignRequested = Signal()  # Ctrl+Enter
    pasteRequested = Signal()  # Ctrl+V

    def __init__(
        self,
        model: PinModel,
        theme: ThemeManager,
        *,
        name: str,
        settings: QSettings | None = None,
        key: str | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(model, theme, name=name, settings=settings, key=key, parent=parent)
        self._editing_setup()
        self.pin_model = model
        for seq, signal in (
            (QKeySequence.StandardKey.Paste, self.pasteRequested),
            (QKeySequence("Ctrl+L"), self.fillRequested),
            (QKeySequence("Ctrl+Return"), self.assignRequested),
            (QKeySequence("Ctrl+Enter"), self.assignRequested),
        ):
            sc = QShortcut(seq, self)
            sc.setContext(Qt.ShortcutContext.WidgetShortcut)
            sc.activated.connect(signal)

    def _editing_setup(self) -> None:
        self.setEditTriggers(
            QAbstractItemView.EditTrigger.DoubleClicked
            | QAbstractItemView.EditTrigger.EditKeyPressed
        )
        self.setTabKeyNavigation(True)

    def _restyle(self) -> None:
        super()._restyle()  # (the shared look turns editing off)
        self._editing_setup()

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        key = event.key()
        mods = event.modifiers()
        editing = self.state() == QAbstractItemView.State.EditingState
        if not editing:
            if key == Qt.Key.Key_Insert and not mods:
                self.insertRequested.emit()
                return
            if key == Qt.Key.Key_Delete:
                (
                    self.deleteRequested
                    if mods & Qt.KeyboardModifier.ShiftModifier
                    else self.clearRequested
                ).emit()
                return
            if key == Qt.Key.Key_Space and not mods:
                self.cycleModeRequested.emit()
                return
            if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_F2) and not mods:
                # F2 edits on every system (Qt does it on Windows and Linux only)
                index = self.currentIndex()
                if index.isValid() and self.model().flags(index) & Qt.ItemFlag.ItemIsEditable:
                    self.edit(index)
                return
        super().keyPressEvent(event)

    def closeEditor(  # noqa: N802
        self, editor: QWidget, hint: QAbstractItemDelegate.EndEditHint
    ) -> None:
        """Enter commits and goes down (the delegate closes the editor with `SubmitModelCache`)."""
        super().closeEditor(editor, hint)
        if hint == QAbstractItemDelegate.EndEditHint.SubmitModelCache:
            index = self.currentIndex()
            below = self.model().index(index.row() + 1, index.column())
            if below.isValid():
                self.setCurrentIndex(below)

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:  # noqa: N802
        return super().eventFilter(obj, event)


def clipboard_grid(text: str) -> list[list[str]]:
    """Tab-separated text (as a spreadsheet copies it) as rows of cells. A trailing empty line is
    ignored; cells keep their inner spaces; a cell in quotes (as a spreadsheet writes one that
    holds a tab or a line break) is read without them."""
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    while lines and lines[-1] == "":
        lines.pop()
    out = []
    for line in lines:
        cells = [c.strip() for c in line.split("\t")]
        out.append(
            [
                c[1:-1].replace('""', '"') if len(c) >= 2 and c[0] == c[-1] == '"' else c
                for c in cells
            ]
        )
    return out


HEADER_WORDS = {
    "pin": "pin", "pin name": "pin", "pin number": "pin", "signal": "signal", "signal name": "signal",
    "mode": "mode", "contact size": "contact_size", "contact": "contact_size", "termination": "termination",
}  # fmt: skip


def grid_columns(first_row: Sequence[str]) -> list[str] | None:
    """The columns a pasted block names in its first row (`Pin`, `Signal`, `Mode`, `Contact size`,
    `Termination`, any case; a name that is not one of them is left out and its cells ignored), or
    None when the first row is not a header (it holds no recognised name)."""
    names = [HEADER_WORDS.get(c.strip().casefold()) for c in first_row]
    if not any(names):
        return None
    return [n or "" for n in names]


def plan_paste(
    project: Any, connector_id: str, current: tuple[str | None, str | None], text: str
) -> tuple[list[dict[str, str]], str]:
    """Rows for `ops_paste_rows` from clipboard text, and the label of the undo step. `current` is
    the (pin, column) the cursor is in. A first row of column names is a header (rows name their
    pins and add new ones); otherwise the cells go to the pins from the cursor down, one column
    per editable column from the cursor's column on. Raises `EditError` with a plain sentence."""
    grid = clipboard_grid(text)
    if not grid or not any(any(c for c in line) for line in grid):
        raise EditError(strings.DV_PASTE_EMPTY)
    columns = grid_columns(grid[0])
    if columns is not None:
        if "pin" not in columns:
            raise EditError(strings.DV_PASTE_NEEDS_PIN)
        body = grid[1:]
        keep = [k for k, name in enumerate(columns) if name]
        rows = devices.rows_from_grid(
            project,
            connector_id,
            None,
            [columns[k] for k in keep],
            [[line[k] if k < len(line) else "" for k in keep] for line in body],
        )
    else:
        pin, column = current
        if column not in devices.GRID_COLUMNS:
            raise EditError(strings.DV_PASTE_PICK_CELL)
        start = devices.GRID_COLUMNS.index(column)
        width = max(len(line) for line in grid)
        names = list(devices.GRID_COLUMNS[start : start + width])
        if "pin" in names and names[0] != "pin":
            names = names[: names.index("pin")]  # (columns after Pin make no sense without it)
        rows = devices.rows_from_grid(project, connector_id, pin, names, grid)
    n = len(rows)
    label = strings.STEP_PASTE_PINS.format(
        strings.DV_N_PINS[0 if n == 1 else 1].format(n), project.connectors[connector_id].name
    )
    return rows, label
