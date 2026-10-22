"""The Accessories tab of the Harness tab: the sleeving, heat shrink, labels and backshells of the
selected harness, one table and a form to add, change and delete one.

    editor = AccessoryEditor(ctl, theme)
    editor.set_harness("W001")

The table lists ID, kind, part, what it is on, position, length (mm), quantity and note. Selecting a
row puts it into the form; **Change accessory** saves the form into it, **Add accessory** adds the
form as a new accessory (a selected row's ID is not reused: the new one gets the next free ID) and
**Delete accessory** removes it. Each is one undo step (`core/build_data.py`). A mistake is said in
words under the form, never in a message box. Everything is disabled for a released harness and a
read-only project, with the reason shown. A harness without accessories says what they are for.
"""

from typing import Any

from PySide6.QtCore import QModelIndex
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from harness_design_studio.core.build_data import (
    check_accessory,
    plan_delete_accessory,
    plan_next_accessory_id,
    plan_set_accessory,
)
from harness_design_studio.core.edit import EditError
from harness_design_studio.core.model import Accessory, Harness
from harness_design_studio.gui import strings
from harness_design_studio.gui.controller import EditorController
from harness_design_studio.gui.empty_state import attach_empty_state
from harness_design_studio.gui.icons import icon_button
from harness_design_studio.gui.tables import Column, DictTableModel, TableView
from harness_design_studio.gui.theme import ThemeManager

KIND_WORDS = dict(strings.ACC_KINDS)

COLUMNS = [
    Column("id", strings.ACC_COL_ID, mono=True, width=72),
    Column("kind", strings.ACC_COL_KIND, width=88),
    Column("part", strings.ACC_COL_PART, mono=True, width=104),
    Column("on", strings.ACC_COL_ON, mono=True, width=96),
    Column("position", strings.ACC_COL_POSITION, width=150),
    Column("length", strings.ACC_COL_LENGTH, numeric=True, width=84),
    Column("quantity", strings.ACC_COL_QUANTITY, numeric=True, width=72),
    Column("note", strings.ACC_COL_NOTE, width=150),
]


def accessory_rows(h: Harness | None) -> list[dict[str, Any]]:
    """The rows of the table (no Qt): one per accessory of the harness, in the order saved."""
    if h is None:
        return []
    return [
        {
            "id": a.id,
            "kind": KIND_WORDS.get(a.kind, a.kind),
            "part": a.part_id or "",
            "on": a.target or strings.ACC_ON_HARNESS,
            "position": a.position or "",
            "length": f"{a.length_mm:g}" if a.length_mm is not None else "",
            "quantity": a.quantity,
            "note": a.note,
        }
        for a in h.accessories
    ]


class AccessoryEditor(QWidget):
    """A table of the accessories of a harness and the form that adds, changes and deletes one."""

    def __init__(self, ctl: EditorController, theme: ThemeManager) -> None:
        super().__init__()
        self.ctl = ctl
        self.setObjectName("accessory-editor")
        self._hid: str | None = None
        self._selected: str | None = None
        self._filling = False
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(theme.space(8))
        self.note = QLabel()
        self.note.setObjectName("accessory-editor-note")
        self.note.setWordWrap(True)
        self.note.setProperty("muted", True)
        root.addWidget(self.note)

        self.model = DictTableModel(COLUMNS, (), theme)
        self.table = TableView(self.model, theme, name=strings.ACC_TABLE_NAME.format(""))
        self.table.setObjectName("accessory-table")
        self.table.setMinimumHeight(theme.px(150))
        self.table.setMaximumHeight(theme.px(220))
        attach_empty_state(
            self.table,
            strings.ACC_EMPTY_TITLE,
            strings.ACC_EMPTY_HINT,
            action=strings.ACC_ADD,
            on_action=self._add_clicked,
        )
        root.addWidget(self.table)

        form = QFormLayout()
        form.setHorizontalSpacing(theme.space(8))
        form.setVerticalSpacing(theme.space(4))
        self.id = QLineEdit()
        self.kind = QComboBox()
        for key, word in strings.ACC_KINDS:
            self.kind.addItem(word, key)
        self.part = QComboBox()
        self.on = QComboBox()
        self.position = QLineEdit()
        self.position.setPlaceholderText(strings.ACC_POSITION_PLACEHOLDER)
        self.length = QLineEdit()
        self.quantity = QSpinBox()
        self.quantity.setRange(1, 9999)
        self.accessory_note = QPlainTextEdit()
        self.accessory_note.setFixedHeight(theme.px(56))
        for widget, name, text, tip in (
            (self.id, "accessory-id", strings.ACC_ID, strings.ACC_ID_TIP),
            (self.kind, "accessory-kind", strings.ACC_KIND, strings.ACC_KIND_TIP),
            (self.part, "accessory-part", strings.ACC_PART, strings.ACC_PART_TIP),
            (self.on, "accessory-on", strings.ACC_ON, strings.ACC_ON_TIP),
            (self.position, "accessory-position", strings.ACC_POSITION, strings.ACC_POSITION_TIP),
            (self.length, "accessory-length", strings.ACC_LENGTH, strings.ACC_LENGTH_TIP),
            (self.quantity, "accessory-quantity", strings.ACC_QUANTITY, strings.ACC_QUANTITY_TIP),
            (
                self.accessory_note,
                "accessory-note",
                strings.ACC_NOTE,
                strings.ACC_NOTE_TIP,
            ),
        ):
            widget.setObjectName(name)
            widget.setAccessibleName(text)
            widget.setToolTip(tip)
            form.addRow(text, widget)
        root.addLayout(form)

        self.error = QLabel()
        self.error.setObjectName("accessory-editor-error")
        self.error.setWordWrap(True)
        self.error.setProperty("error", True)
        self.error.setVisible(False)
        root.addWidget(self.error)

        buttons = QHBoxLayout()
        self.add = QPushButton()
        self.add.setObjectName("accessory-add")
        self.add.setProperty("primary", True)
        icon_button(self.add, "plus", theme, strings.ACC_ADD_TIP, text=strings.ACC_ADD)
        self.change = QPushButton()
        self.change.setObjectName("accessory-change")
        icon_button(self.change, "pass", theme, strings.ACC_CHANGE_TIP, text=strings.ACC_CHANGE)
        self.delete = QPushButton()
        self.delete.setObjectName("accessory-delete")
        icon_button(self.delete, "close", theme, strings.ACC_DELETE_TIP, text=strings.ACC_DELETE)
        self.new = QPushButton()
        self.new.setObjectName("accessory-new")
        icon_button(self.new, "refresh", theme, strings.ACC_NEW_TIP, text=strings.ACC_NEW)
        for b in (self.add, self.change):
            buttons.addWidget(b)
        root.addLayout(buttons)
        more = QHBoxLayout()
        more.addWidget(self.delete)
        more.addWidget(self.new)
        root.addLayout(more)
        root.addStretch(1)

        self.add.clicked.connect(self.add_accessory)
        self.change.clicked.connect(self.change_accessory)
        self.delete.clicked.connect(self.delete_accessory)
        self.new.clicked.connect(self.new_accessory)
        for w in (self.id, self.position, self.length):
            w.returnPressed.connect(self._enter)
        sm = self.table.selectionModel()
        if sm is not None:
            sm.currentRowChanged.connect(lambda _c, _p: self._row_selected())
        self.table.activated.connect(self._activated)
        self.set_harness(None)

    # ---- what is shown ---------------------------------------------------------------------
    def harness_id(self) -> str | None:
        return self._hid

    def selected_id(self) -> str | None:
        """The ID of the accessory selected in the table (the one the form shows), or None."""
        return self._selected

    def set_harness(self, harness_id: str | None) -> None:
        """Show the accessories of this harness (None: nothing). A form with unsaved typing keeps
        it; the choices (parts, connectors, wires) follow the project."""
        same = harness_id == self._hid
        self._hid = harness_id
        p = self.ctl.project
        h = p.harnesses.get(harness_id or "")
        self.table.setAccessibleName(strings.ACC_TABLE_NAME.format(harness_id or ""))
        self._fill_choices(h)
        rows = accessory_rows(h)
        sel = self._selected
        if not (same and rows == self.model.rows()):  # (the form keeps what is typed in it)
            self.table.set_rows(rows)
            if sel is not None and h is not None and any(a.id == sel for a in h.accessories):
                self._select(sel)
            else:
                self._selected = None
                self._show(None)
        reason = self._reason()
        self.note.setText(reason or (strings.ACC_NO_HARNESS if h is None else ""))
        self.note.setVisible(bool(self.note.text()))
        on = h is not None and not reason
        for w in (
            self.id,
            self.kind,
            self.part,
            self.on,
            self.position,
            self.length,
            self.quantity,
            self.accessory_note,
            self.add,
            self.new,
        ):
            w.setEnabled(on)
        self.change.setEnabled(on and self._selected is not None)
        self.delete.setEnabled(on and self._selected is not None)
        self.id.setEnabled(on and self._selected is None)  # (an accessory keeps its ID)
        btn = self.table.empty_state.button  # type: ignore[attr-defined]
        if btn is not None:
            btn.setEnabled(on)

    def _reason(self) -> str:
        """Why nothing can be changed here ("" when something can)."""
        h = self.ctl.project.harnesses.get(self._hid or "")
        if h is None:
            return ""
        if self.ctl.read_only:
            return strings.WHY_READ_ONLY
        if h.status == "released":
            return strings.ACC_RELEASED.format(h.id)
        return ""

    def _fill_choices(self, h: Harness | None) -> None:
        keep = (self.part.currentData(), self.on.currentData())
        self._filling = True
        try:
            self.part.clear()
            self.part.addItem(strings.ACC_PART_NONE, None)
            for part in sorted(self.ctl.project.parts.values(), key=lambda x: x.id):
                self.part.addItem(part.id, part.id)
                self.part.setItemData(
                    self.part.count() - 1, part.category, 3
                )  # (Qt.ToolTipRole: its category)
            self.on.clear()
            self.on.addItem(strings.ACC_ON_HARNESS, None)
            if h is not None:
                for cid in sorted(c.id for c in h.connectors):
                    self.on.addItem(cid, cid)
                for wid in sorted(w.id for w in h.wires):
                    self.on.addItem(wid, wid)
            self.part.setCurrentIndex(max(0, self.part.findData(keep[0])))
            self.on.setCurrentIndex(max(0, self.on.findData(keep[1])))
        finally:
            self._filling = False

    def _show(self, a: Accessory | None) -> None:
        """Put an accessory into the form (None: an empty form with the next free ID)."""
        h = self.ctl.project.harnesses.get(self._hid or "")
        self._filling = True
        try:
            self.id.setText(a.id if a is not None else (plan_next_accessory_id(h) if h else ""))
            self.kind.setCurrentIndex(max(0, self.kind.findData(a.kind if a else "sleeving")))
            self.part.setCurrentIndex(max(0, self.part.findData(a.part_id if a else None)))
            self.on.setCurrentIndex(max(0, self.on.findData(a.target if a else None)))
            self.position.setText((a.position or "") if a else "")
            self.length.setText(f"{a.length_mm:g}" if a and a.length_mm is not None else "")
            self.quantity.setValue(a.quantity if a else 1)
            self.accessory_note.setPlainText(a.note if a else "")
        finally:
            self._filling = False

    def _select(self, accessory_id: str) -> None:
        for r, row in enumerate(self.model.rows()):
            if isinstance(row, dict) and row["id"] == accessory_id:
                self.table.selectRow(self.table.proxy.mapFromSource(self.model.index(r, 0)).row())
                break

    def _row_selected(self) -> None:
        rows = self.table.selected_rows()
        row = rows[0] if rows and isinstance(rows[0], dict) else None
        h = self.ctl.project.harnesses.get(self._hid or "")
        found = next((a for a in (h.accessories if h else []) if row and a.id == row["id"]), None)
        self._selected = found.id if found is not None else None
        self._show(found if found is not None else None)
        on = h is not None and not self._reason()
        self.change.setEnabled(on and found is not None)
        self.delete.setEnabled(on and found is not None)
        self.id.setEnabled(on and found is None)
        self._say("")

    def _activated(self, index: QModelIndex) -> None:
        if index.isValid():
            self.position.setFocus()

    def _add_clicked(self) -> None:
        self.add_accessory()

    def _enter(self) -> None:
        (self.change_accessory if self._selected is not None else self.add_accessory)()

    def _say(self, text: str) -> None:
        self.error.setText(text)
        self.error.setVisible(bool(text))

    # ---- the form --------------------------------------------------------------------------
    def _values(self, accessory_id: str) -> dict[str, object]:
        return {
            "id": accessory_id,
            "kind": self.kind.currentData(),
            "part_id": self.part.currentData(),
            "target": self.on.currentData(),
            "position": self.position.text(),
            "length_mm": self.length.text(),
            "quantity": self.quantity.value(),
            "note": self.accessory_note.toPlainText(),
        }

    # ---- the actions -----------------------------------------------------------------------
    def new_accessory(self) -> None:
        """Clear the selection and the form to describe a new accessory."""
        self.table.clearSelection()
        self._selected = None
        self._show(None)
        self.id.setEnabled(self.add.isEnabled())
        self.change.setEnabled(False)
        self.delete.setEnabled(False)
        self._say("")

    def add_accessory(self) -> bool:
        """Add the form as a new accessory; True when it was added."""
        h = self.ctl.project.harnesses.get(self._hid or "")
        if h is None or not self.add.isEnabled():
            return False
        if self._selected is not None:
            aid = plan_next_accessory_id(h)  # a copy of the selected one: its own ID
        else:
            aid = self.id.text().strip() or plan_next_accessory_id(h)
            if any(a.id == aid for a in h.accessories):
                self._say(strings.ACC_ID_EXISTS.format(aid))
                return False
        try:
            new = check_accessory(self.ctl.project, h.id, self._values(aid))
            ops = plan_set_accessory(self.ctl.project, h.id, new)
        except EditError as exc:
            self._say(str(exc))
            return False
        if not self.ctl.run(strings.STEP_ADD_ACCESSORY.format(aid), ops):
            return False
        self._say("")
        self._selected = aid
        self.set_harness(h.id)
        self.new_accessory()
        return True

    def change_accessory(self) -> bool:
        """Save the form into the selected accessory; True when it was saved."""
        h = self.ctl.project.harnesses.get(self._hid or "")
        if h is None or not self.change.isEnabled():
            return False
        aid = self._selected
        if aid is None:
            self._say(strings.ACC_NONE_SELECTED)
            return False
        try:
            ops = plan_set_accessory(self.ctl.project, h.id, self._values(aid))
        except EditError as exc:
            self._say(str(exc))
            return False
        if ops and not self.ctl.run(strings.STEP_CHANGE_ACCESSORY.format(aid), ops):
            return False
        self._say("")
        self.set_harness(h.id)
        return True

    def delete_accessory(self) -> bool:
        """Delete the selected accessory; True when it was deleted."""
        h = self.ctl.project.harnesses.get(self._hid or "")
        if h is None or not self.delete.isEnabled():
            return False
        aid = self._selected
        if aid is None:
            self._say(strings.ACC_NONE_SELECTED)
            return False
        try:
            ops = plan_delete_accessory(self.ctl.project, h.id, aid)
        except EditError as exc:
            self._say(str(exc))
            return False
        if not self.ctl.run(strings.STEP_DELETE_ACCESSORY.format(aid), ops):
            return False
        self._say("")
        self._selected = None
        self.set_harness(h.id)
        self.new_accessory()
        return True
