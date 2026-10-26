"""The Connectors tab of the Harness tab: add a cable connector to a harness that you made, edit a
connector (part, gender, keying, name), set the signal, role, function, termination, contact size and
contact (a part of category contact) of its pins, add, rename and delete pins, give all pins of a
connector one contact, and delete a connector without wires.

    editor = ConnectorEditor(ctl, theme)
    editor.set_harness("W001")

A harness made by Generate takes no connectors here (Generate would replace them): the tab says so.
A connector of such a harness can be edited, though: the edit makes it yours (`Connector.locked`) and
Generate keeps it; its name, its pins and their contacts follow the device, and the tab says so.
A released harness and a read-only project turn everything off. Mistakes are said in words under the
form, never in a message box. The plans are in `core/manual_harness.py`, `core/connector_edit.py` and
`core/build_data.py`. On a harness made by Generate the contact comes from the pin of the device
(Devices tab, column Cable contact), and the tab says so.
"""

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from harness_design_studio.core.build_data import plan_set_contacts
from harness_design_studio.core.commands import Op
from harness_design_studio.core.connector_edit import (
    plan_add_pins,
    plan_delete_pin,
    plan_edit_connector,
    plan_edit_pin,
    plan_rename_pin,
    plan_reset_connector,
    suggested_gender,
)
from harness_design_studio.core.devices import contact_part_choices
from harness_design_studio.core.edit import EditError
from harness_design_studio.core.manual_harness import plan_add_connector, plan_delete_connector
from harness_design_studio.core.model import Connector, Harness
from harness_design_studio.gui import strings
from harness_design_studio.gui.controller import EditorController
from harness_design_studio.gui.icons import icon_button
from harness_design_studio.gui.theme import ThemeManager


def _field(widget: QWidget, name: str, text: str, tip: str) -> QWidget:
    widget.setObjectName(name)
    widget.setAccessibleName(text)
    widget.setToolTip(tip)
    return widget


class ConnectorEditor(QWidget):
    """Add and delete cable connectors and set their pins, for a harness made by hand."""

    connectorAdded = Signal(str)

    def __init__(self, ctl: EditorController, theme: ThemeManager) -> None:
        super().__init__()
        self.ctl = ctl
        self.setObjectName("connector-editor")
        self._hid: str | None = None
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(theme.space(8))
        self.note = QLabel()
        self.note.setObjectName("connector-editor-note")
        self.note.setWordWrap(True)
        self.note.setProperty("muted", True)
        root.addWidget(self.note)

        title = QLabel(strings.CE_ADD_TITLE)
        title.setProperty("heading", True)
        root.addWidget(title)
        form = QFormLayout()
        form.setHorizontalSpacing(theme.space(8))
        form.setVerticalSpacing(theme.space(4))
        self.part = QComboBox()
        self.plugs_into = QComboBox()
        self.name = QLineEdit()
        self.pins = QLineEdit()
        for widget, name, text, tip in (
            (self.part, "connector-part", strings.CE_PART, strings.CE_PART_TIP),
            (
                self.plugs_into,
                "connector-plugs-into",
                strings.CE_PLUGS_INTO,
                strings.CE_PLUGS_INTO_TIP,
            ),
            (self.name, "connector-name", strings.CE_NAME, strings.CE_NAME_TIP),
            (self.pins, "connector-pins", strings.CE_PINS, strings.CE_PINS_TIP),
        ):
            form.addRow(text, _field(widget, name, text, tip))
        root.addLayout(form)
        self.add = QPushButton()
        self.add.setObjectName("connector-add")
        self.add.setProperty("primary", True)
        icon_button(self.add, "pass", theme, strings.CE_ADD_TIP, text=strings.CE_ADD)
        root.addWidget(self.add)

        edit_title = QLabel(strings.CE_EDIT_TITLE)
        edit_title.setProperty("heading", True)
        root.addSpacing(theme.space(8))
        root.addWidget(edit_title)
        edit_form = QFormLayout()
        edit_form.setHorizontalSpacing(theme.space(8))
        edit_form.setVerticalSpacing(theme.space(4))
        self.connector = QComboBox()
        self.edit_part = QComboBox()
        self.gender = QComboBox()
        for key, label in strings.CE_GENDERS:
            self.gender.addItem(label, key)
        self.keying = QLineEdit()
        self.edit_name = QLineEdit()
        for widget, name, text, tip in (
            (self.connector, "connector-pick", strings.CE_CONNECTOR, strings.CE_CONNECTOR_TIP),
            (self.edit_part, "connector-edit-part", strings.CE_PART, strings.CE_EDIT_PART_TIP),
            (self.gender, "connector-edit-gender", strings.CE_GENDER, strings.CE_GENDER_TIP),
            (self.keying, "connector-edit-keying", strings.CE_KEYING, strings.CE_KEYING_TIP),
            (self.edit_name, "connector-edit-name", strings.CE_NAME, strings.CE_EDIT_NAME_TIP),
        ):
            edit_form.addRow(text, _field(widget, name, text, tip))
        root.addLayout(edit_form)
        self.pin_count = QLabel()
        self.pin_count.setObjectName("connector-pin-count")
        self.pin_count.setWordWrap(True)
        self.pin_count.setProperty("muted", True)
        self.pin_count.setVisible(False)
        root.addWidget(self.pin_count)
        self.edit_state = QLabel()
        self.edit_state.setObjectName("connector-edit-state")
        self.edit_state.setWordWrap(True)
        self.edit_state.setProperty("muted", True)
        root.addWidget(self.edit_state)
        self.edit_apply = QPushButton()
        self.edit_apply.setObjectName("connector-edit-apply")
        icon_button(
            self.edit_apply, "pass", theme, strings.CE_EDIT_APPLY_TIP, text=strings.CE_EDIT_APPLY
        )
        self.reset = QPushButton()
        self.reset.setObjectName("connector-reset")
        icon_button(self.reset, "unlock", theme, strings.CE_RESET_TIP, text=strings.CE_RESET)
        self.reset.setVisible(False)
        root.addWidget(self.edit_apply)
        root.addWidget(self.reset)

        pin_title = QLabel(strings.CE_PIN_TITLE)
        pin_title.setProperty("heading", True)
        root.addSpacing(theme.space(8))
        root.addWidget(pin_title)
        pin_form = QFormLayout()
        pin_form.setHorizontalSpacing(theme.space(8))
        pin_form.setVerticalSpacing(theme.space(4))
        self.pin = QComboBox()
        self.signal = QLineEdit()
        self.role = QComboBox()
        for key, label in strings.CE_ROLES:
            self.role.addItem(label, key)
        self.function = QLineEdit()
        self.termination = QComboBox()
        for key, label in strings.CE_TERMINATIONS:
            self.termination.addItem(label, key)
        self.contact = QLineEdit()
        self.contact_part = QComboBox()
        for widget, name, text, tip in (
            (self.pin, "connector-pin", strings.CE_PIN, strings.CE_PIN),
            (self.signal, "connector-signal", strings.CE_SIGNAL, strings.CE_SIGNAL_TIP),
            (self.role, "connector-role", strings.CE_ROLE, strings.CE_ROLE_TIP),
            (self.function, "connector-function", strings.CE_FUNCTION, strings.CE_FUNCTION_TIP),
            (
                self.termination,
                "connector-termination",
                strings.CE_TERMINATION,
                strings.CE_TERMINATION_TIP,
            ),
            (self.contact, "connector-contact", strings.CE_CONTACT, strings.CE_CONTACT_TIP),
            (
                self.contact_part,
                "connector-contact-part",
                strings.CE_CONTACT_PART,
                strings.CE_CONTACT_PART_TIP,
            ),
        ):
            pin_form.addRow(text, _field(widget, name, text, tip))
        root.addLayout(pin_form)
        self.contact_note = QLabel(strings.CE_CONTACT_GENERATED)
        self.contact_note.setObjectName("connector-contact-note")
        self.contact_note.setWordWrap(True)
        self.contact_note.setProperty("muted", True)
        self.contact_note.setVisible(False)
        root.addWidget(self.contact_note)
        self.set_pin = QPushButton()
        self.set_pin.setObjectName("connector-set-pin")
        icon_button(self.set_pin, "pass", theme, strings.CE_SET_PIN_TIP, text=strings.CE_SET_PIN)
        self.contact_all = QPushButton()
        self.contact_all.setObjectName("connector-contact-all")
        icon_button(
            self.contact_all,
            "pass",
            theme,
            strings.CE_CONTACT_ALL_TIP,
            text=strings.CE_CONTACT_ALL,
        )
        root.addWidget(self.set_pin)
        root.addWidget(self.contact_all)

        self.pin_id = QLineEdit()
        id_form = QFormLayout()
        id_form.setHorizontalSpacing(theme.space(8))
        id_form.addRow(
            strings.CE_PIN_ID,
            _field(self.pin_id, "connector-pin-id", strings.CE_PIN_ID, strings.CE_PIN_ID_TIP),
        )
        root.addLayout(id_form)
        pin_row = QHBoxLayout()
        self.pin_add = QPushButton()
        self.pin_add.setObjectName("connector-pin-add")
        icon_button(self.pin_add, "plus", theme, strings.CE_PIN_ADD_TIP, text=strings.CE_PIN_ADD)
        self.pin_rename = QPushButton()
        self.pin_rename.setObjectName("connector-pin-rename")
        icon_button(
            self.pin_rename, "pass", theme, strings.CE_PIN_RENAME_TIP, text=strings.CE_PIN_RENAME
        )
        self.pin_delete = QPushButton()
        self.pin_delete.setObjectName("connector-pin-delete")
        icon_button(
            self.pin_delete, "close", theme, strings.CE_PIN_DELETE_TIP, text=strings.CE_PIN_DELETE
        )
        for b in (self.pin_add, self.pin_rename, self.pin_delete):
            pin_row.addWidget(b)
        root.addLayout(pin_row)
        self.pin_note = QLabel(strings.CE_PINS_FROM_DEVICE)
        self.pin_note.setObjectName("connector-pin-note")
        self.pin_note.setWordWrap(True)
        self.pin_note.setProperty("muted", True)
        self.pin_note.setVisible(False)
        root.addWidget(self.pin_note)
        self.delete = QPushButton()
        self.delete.setObjectName("connector-delete")
        icon_button(self.delete, "close", theme, strings.CE_DELETE_TIP, text=strings.CE_DELETE)
        root.addSpacing(theme.space(8))
        root.addWidget(self.delete)

        self.error = QLabel()
        self.error.setObjectName("connector-editor-error")
        self.error.setWordWrap(True)
        self.error.setProperty("error", True)
        self.error.setVisible(False)
        root.addWidget(self.error)
        root.addStretch(1)

        self.add.clicked.connect(self.add_connector)
        self.name.returnPressed.connect(self.add_connector)
        self.pins.returnPressed.connect(self.add_connector)
        self.set_pin.clicked.connect(self.apply_pin)
        for line in (self.signal, self.function, self.contact):
            line.returnPressed.connect(self.apply_pin)
        self.contact_all.clicked.connect(self.apply_contact_to_all)
        self.delete.clicked.connect(self.delete_connector)
        self.edit_apply.clicked.connect(self.apply_connector)
        for line in (self.keying, self.edit_name):
            line.returnPressed.connect(self.apply_connector)
        self.reset.clicked.connect(self.reset_connector)
        self.pin_add.clicked.connect(self.add_pins)
        self.pin_id.returnPressed.connect(self.add_pins)
        self.pin_rename.clicked.connect(self.rename_pin)
        self.pin_delete.clicked.connect(self.delete_pin)
        self.connector.activated.connect(lambda _i: self._fill_pins())
        self.pin.activated.connect(lambda _i: self._show_pin())
        self.edit_part.activated.connect(lambda _i: self._part_chosen())
        self.set_harness(None)

    # ---- what is shown ---------------------------------------------------------------------
    def set_harness(self, harness_id: str | None) -> None:
        """Show the connectors of this harness (None: nothing)."""
        self._hid = harness_id
        p = self.ctl.project
        h = p.harnesses.get(harness_id or "")
        keep = (
            self.part.currentData(),
            self.plugs_into.currentData(),
            self.connector.currentText(),
        )
        self.part.clear()
        for part in sorted(
            (x for x in p.parts.values() if x.category == "connector"), key=lambda x: x.id
        ):
            self.part.addItem(part.id, part.id)
        self.part.setCurrentIndex(max(0, self.part.findData(keep[0])))
        used = {c.mates_with for c in (h.connectors if h else []) if c.mates_with}
        self.plugs_into.clear()
        self.plugs_into.addItem(strings.CE_NOTHING, None)
        for c in sorted(p.connectors.values(), key=lambda x: x.id):
            if c.role == "box" and c.id not in used:
                self.plugs_into.addItem(f"{c.id} ({c.unit_id})", c.id)
        self.plugs_into.setCurrentIndex(max(0, self.plugs_into.findData(keep[1])))
        self.connector.clear()
        if h is not None:
            self.connector.addItems(sorted(c.id for c in h.connectors))
            self.connector.setCurrentIndex(max(0, self.connector.findText(keep[2])))
        self._fill_contacts()
        self._fill_pins()
        reason = self._reason()
        self.note.setText(reason)
        self.note.setVisible(bool(reason))
        generated = h is not None and h.generated
        self.contact_note.setVisible(generated)
        self.pin_note.setVisible(generated and not self._shut())
        shut = h is None or self._shut()
        own = not shut and not generated  # a harness you made: connectors and pins can be added
        for w in (self.part, self.plugs_into, self.name, self.pins, self.add):
            w.setEnabled(own)
        has = not shut and self.connector.count() > 0
        for w in (
            self.connector,
            self.edit_part,
            self.gender,
            self.keying,
            self.edit_apply,
            self.reset,
            self.pin,
            self.signal,
            self.role,
            self.function,
            self.termination,
            self.contact,
            self.set_pin,
        ):
            w.setEnabled(has)
        for w in (
            self.edit_name,
            self.contact_part,
            self.contact_all,
            self.delete,
            self.pin_id,
            self.pin_add,
            self.pin_rename,
            self.pin_delete,
        ):
            w.setEnabled(has and own)
        self.edit_name.setToolTip(
            strings.CE_EDIT_NAME_FIXED if generated else strings.CE_EDIT_NAME_TIP
        )

    def _fill_contacts(self) -> None:
        """The contact parts of the library (and none) for the Contact choice."""
        keep = self.contact_part.currentData()
        self.contact_part.clear()
        self.contact_part.addItem(strings.CE_CONTACT_NONE, None)
        for part_id in contact_part_choices(self.ctl.project):
            self.contact_part.addItem(part_id, part_id)
        self.contact_part.setCurrentIndex(max(0, self.contact_part.findData(keep)))

    def _shut(self) -> bool:
        """True when nothing can be changed: a read-only project or a released harness."""
        h = self.ctl.project.harnesses.get(self._hid or "")
        return h is None or self.ctl.read_only or h.status == "released"

    def _reason(self) -> str:
        """Why something cannot be changed here ("" when everything can)."""
        h = self.ctl.project.harnesses.get(self._hid or "")
        if h is None:
            return ""
        if self.ctl.read_only:
            return strings.WHY_READ_ONLY
        if h.status == "released":
            return strings.CE_RELEASED.format(h.id)
        if h.generated:
            return strings.CE_GENERATED.format(h.id)
        return ""

    def _selected(self) -> tuple[Harness | None, Connector | None]:
        h = self.ctl.project.harnesses.get(self._hid or "")
        c = next(
            (x for x in (h.connectors if h else []) if x.id == self.connector.currentText()), None
        )
        return h, c

    def _fill_pins(self) -> None:
        _h, c = self._selected()
        keep = self.pin.currentText()
        self.pin.clear()
        if c is not None:
            self.pin.addItems([p.id for p in c.pins])
            self.pin.setCurrentIndex(max(0, self.pin.findText(keep)))
        self._show_connector()
        self._show_pin()

    def _show_connector(self) -> None:
        """The values of the selected connector in the Edit connector fields."""
        h, c = self._selected()
        self.edit_part.clear()
        for part in sorted(
            (x for x in self.ctl.project.parts.values() if x.category == "connector"),
            key=lambda x: x.id,
        ):
            self.edit_part.addItem(part.id, part.id)
        if c is not None and self.edit_part.findData(c.part_id) < 0:
            self.edit_part.addItem(c.part_id, c.part_id)  # (a part that left the library)
        self.edit_part.setCurrentIndex(max(0, self.edit_part.findData(c.part_id if c else None)))
        self.gender.setCurrentIndex(max(0, self.gender.findData(c.gender if c else "unspecified")))
        if not self.keying.hasFocus():
            self.keying.setText((c.keying or "") if c is not None else "")
        if not self.edit_name.hasFocus():
            self.edit_name.setText(c.name if c is not None else "")
        generated = h is not None and h.generated
        self.reset.setVisible(c is not None and c.locked)
        self.edit_state.setText(
            ""
            if c is None or not generated
            else strings.CE_EDIT_STATE_MINE
            if c.locked
            else strings.CE_EDIT_STATE_GENERATED
        )
        self.edit_state.setVisible(bool(self.edit_state.text()))
        self._show_pin_count()

    def _show_pin_count(self) -> None:
        _h, c = self._selected()
        part = self.ctl.project.parts.get(self.edit_part.currentData() or "")
        wanted = part.pin_count if part is not None else None
        text = ""
        if c is not None and wanted is not None and wanted != len(c.pins):
            h = self.ctl.project.harnesses.get(self._hid or "")
            text = strings.CE_PIN_COUNT.format(wanted, len(c.pins))
            if h is not None and not h.generated:
                text += strings.CE_PIN_COUNT_ADD
        self.pin_count.setText(text)
        self.pin_count.setVisible(bool(text))

    def _part_chosen(self) -> None:
        """A part was picked: the gender it says is offered (change it if it is wrong)."""
        said = suggested_gender(self.ctl.project, str(self.edit_part.currentData() or ""))
        if said != "unspecified":
            self.gender.setCurrentIndex(max(0, self.gender.findData(said)))
        self._show_pin_count()

    def _show_pin(self) -> None:
        _h, c = self._selected()
        pin = next((p for p in (c.pins if c else []) if p.id == self.pin.currentText()), None)
        if self.function.hasFocus() or self.contact.hasFocus() or self.signal.hasFocus():
            return
        self.signal.setText((pin.signal or "") if pin is not None else "")
        self.role.setCurrentIndex(max(0, self.role.findData(pin.role if pin is not None else "")))
        self.function.setText((pin.function or "") if pin is not None else "")
        self.contact.setText((pin.contact_size or "") if pin is not None else "")
        i = self.termination.findData(pin.termination if pin is not None else "unspecified")
        self.termination.setCurrentIndex(max(0, i))
        wanted = pin.contact_part if pin is not None else None
        if wanted is not None and self.contact_part.findData(wanted) < 0:
            self.contact_part.addItem(wanted, wanted)  # (a part that left the library: still shown)
        self.contact_part.setCurrentIndex(max(0, self.contact_part.findData(wanted)))
        if not self.pin_id.hasFocus():
            self.pin_id.setText(pin.id if pin is not None else "")

    def _say(self, text: str) -> None:
        self.error.setText(text)
        self.error.setVisible(bool(text))

    def _run(self, label: str, ops: list[Op]) -> bool:
        """Run the ops as one undo step and show the connector as it is now (the harness view
        would do so a moment later)."""
        if not self.ctl.run(label, ops):
            return False
        self.set_harness(self._hid)
        return True

    # ---- the actions -----------------------------------------------------------------------
    def add_connector(self) -> bool:
        if self._hid is None or not self.add.isEnabled():
            return False
        mate = self.plugs_into.currentData()
        try:
            ops, cid = plan_add_connector(
                self.ctl.project,
                self._hid,
                part_id=None if mate else (self.part.currentData() or None),
                mates_with=mate,
                name=self.name.text(),
                pin_ids=[t.strip() for t in self.pins.text().split(",")]
                if self.pins.text().strip()
                else None,
            )
        except EditError as exc:
            self._say(str(exc))
            return False
        if not self.ctl.run(strings.STEP_ADD_HARNESS_CONNECTOR.format(self._hid), ops):
            return False
        self._say("")
        self.name.clear()
        self.pins.clear()
        self.connectorAdded.emit(cid)
        return True

    def apply_connector(self) -> bool:
        """Set the part, gender, keying and name of the selected connector (one undo step). On a
        generated harness the name is left alone and the connector becomes yours."""
        cid = self.connector.currentText()
        if self._hid is None or not cid or not self.edit_apply.isEnabled():
            return False
        h, _c = self._selected()
        changes: dict[str, object] = {
            "part_id": self.edit_part.currentData(),
            "gender": self.gender.currentData(),
            "keying": self.keying.text(),
        }
        if h is not None and not h.generated:
            changes["name"] = self.edit_name.text()
        try:
            ops = plan_edit_connector(self.ctl.project, self._hid, cid, **changes)
        except EditError as exc:
            self._say(str(exc))
            return False
        if not ops:
            self._say(strings.CE_EDIT_NOTHING)
            return True
        self._say("")
        return self._run(strings.STEP_EDIT_CONNECTOR.format(cid), ops)

    def reset_connector(self) -> bool:
        """Give an edited connector of a generated harness back to Generate."""
        cid = self.connector.currentText()
        if self._hid is None or not cid or not self.reset.isEnabled():
            return False
        try:
            ops = plan_reset_connector(self.ctl.project, self._hid, cid)
        except EditError as exc:
            self._say(str(exc))
            return False
        self._say("")
        return not ops or self._run(strings.STEP_RESET_CONNECTOR.format(cid), ops)

    def apply_pin(self) -> bool:
        cid, pin = self.connector.currentText(), self.pin.currentText()
        if self._hid is None or not cid or not pin:
            return False
        h, _c = self._selected()
        changes: dict[str, object] = {
            "signal": self.signal.text(),
            "role": self.role.currentData(),
            "function": self.function.text(),
            "termination": self.termination.currentData(),
            "contact_size": self.contact.text(),
        }
        if h is not None and not h.generated:
            changes["contact_part"] = self.contact_part.currentData()
        try:
            ops = plan_edit_pin(self.ctl.project, self._hid, cid, pin, **changes)
        except EditError as exc:
            self._say(str(exc))
            return False
        self._say("")
        return not ops or self._run(strings.STEP_SET_HARNESS_PIN.format(f"{cid}/{pin}"), ops)

    def add_pins(self) -> bool:
        """Add the pins listed in Pin ID (separated by commas) to the selected connector."""
        cid = self.connector.currentText()
        if self._hid is None or not cid or not self.pin_add.isEnabled():
            return False
        try:
            ops = plan_add_pins(
                self.ctl.project, self._hid, cid, [t.strip() for t in self.pin_id.text().split(",")]
            )
        except EditError as exc:
            self._say(str(exc))
            return False
        self._say("")
        return self._run(strings.STEP_ADD_PINS.format(cid), ops)

    def rename_pin(self) -> bool:
        """Give the selected pin the ID in Pin ID; the wires on it follow."""
        cid, pin = self.connector.currentText(), self.pin.currentText()
        if self._hid is None or not cid or not pin or not self.pin_rename.isEnabled():
            return False
        try:
            ops = plan_rename_pin(self.ctl.project, self._hid, cid, pin, self.pin_id.text().strip())
        except EditError as exc:
            self._say(str(exc))
            return False
        self._say("")
        return not ops or self._run(strings.CE_STEP_RENAME_PIN.format(f"{cid}/{pin}"), ops)

    def delete_pin(self) -> bool:
        """Delete the selected pin (it must have no wires)."""
        cid, pin = self.connector.currentText(), self.pin.currentText()
        if self._hid is None or not cid or not pin or not self.pin_delete.isEnabled():
            return False
        try:
            ops = plan_delete_pin(self.ctl.project, self._hid, cid, pin)
        except EditError as exc:
            self._say(str(exc))
            return False
        self._say("")
        return self._run(strings.STEP_DELETE_PIN.format(f"{cid}/{pin}"), ops)

    def apply_contact_to_all(self) -> bool:
        """Give every pin of the selected connector the contact chosen in Contact."""
        cid = self.connector.currentText()
        if self._hid is None or not cid or not self.contact_all.isEnabled():
            return False
        try:
            ops = plan_set_contacts(
                self.ctl.project, self._hid, cid, None, self.contact_part.currentData()
            )
        except EditError as exc:
            self._say(str(exc))
            return False
        self._say("")
        return not ops or self.ctl.run(strings.STEP_SET_HARNESS_CONTACTS.format(cid), ops)

    def delete_connector(self) -> bool:
        cid = self.connector.currentText()
        if self._hid is None or not cid:
            return False
        try:
            ops = plan_delete_connector(self.ctl.project, self._hid, cid)
        except EditError as exc:
            self._say(str(exc))
            return False
        self._say("")
        return self.ctl.run(strings.STEP_DELETE_HARNESS_CONNECTOR.format(cid), ops)
