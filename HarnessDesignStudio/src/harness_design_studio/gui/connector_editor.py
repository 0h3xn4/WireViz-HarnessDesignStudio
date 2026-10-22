"""The Connectors tab of the Harness tab: add a cable connector to a harness that you made, set the
function, termination, contact size and contact (a part of category contact) of its pins, give all
pins of a connector one contact, and delete a connector without wires.

    editor = ConnectorEditor(ctl, theme)
    editor.set_harness("W001")

A harness made by Generate takes no connectors here (Generate would replace them): the tab says so
and stays disabled. The same holds for a released harness and a read-only project. Mistakes are
said in words under the form, never in a message box. The plans are in `core/manual_harness.py`
and `core/build_data.py`. On a harness made by Generate the contact comes from the pin of the unit
(Devices tab, column Cable contact), and the tab says so.
"""

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from harness_design_studio.core.build_data import plan_set_contacts
from harness_design_studio.core.devices import contact_part_choices
from harness_design_studio.core.edit import EditError
from harness_design_studio.core.manual_harness import (
    plan_add_connector,
    plan_delete_connector,
    plan_set_pin,
)
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

        pin_title = QLabel(strings.CE_PIN_TITLE)
        pin_title.setProperty("heading", True)
        root.addSpacing(theme.space(8))
        root.addWidget(pin_title)
        pin_form = QFormLayout()
        pin_form.setHorizontalSpacing(theme.space(8))
        pin_form.setVerticalSpacing(theme.space(4))
        self.connector = QComboBox()
        self.pin = QComboBox()
        self.function = QLineEdit()
        self.termination = QComboBox()
        for key, label in strings.CE_TERMINATIONS:
            self.termination.addItem(label, key)
        self.contact = QLineEdit()
        self.contact_part = QComboBox()
        for widget, name, text, tip in (
            (self.connector, "connector-pick", strings.CE_CONNECTOR, strings.CE_CONNECTOR_TIP),
            (self.pin, "connector-pin", strings.CE_PIN, strings.CE_PIN),
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
        self.delete = QPushButton()
        self.delete.setObjectName("connector-delete")
        icon_button(self.delete, "close", theme, strings.CE_DELETE_TIP, text=strings.CE_DELETE)
        root.addWidget(self.set_pin)
        root.addWidget(self.contact_all)
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
        self.function.returnPressed.connect(self.apply_pin)
        self.contact.returnPressed.connect(self.apply_pin)
        self.contact_all.clicked.connect(self.apply_contact_to_all)
        self.delete.clicked.connect(self.delete_connector)
        self.connector.activated.connect(lambda _i: self._fill_pins())
        self.pin.activated.connect(lambda _i: self._show_pin())
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
        self.contact_note.setVisible(h is not None and h.generated)
        on = h is not None and not reason
        for w in (self.part, self.plugs_into, self.name, self.pins, self.add):
            w.setEnabled(on)
        has = on and self.connector.count() > 0
        for w in (
            self.connector,
            self.pin,
            self.function,
            self.termination,
            self.contact,
            self.contact_part,
        ):
            w.setEnabled(has)
        self.set_pin.setEnabled(has)
        self.contact_all.setEnabled(has)
        self.delete.setEnabled(has)

    def _fill_contacts(self) -> None:
        """The contact parts of the library (and none) for the Contact choice."""
        keep = self.contact_part.currentData()
        self.contact_part.clear()
        self.contact_part.addItem(strings.CE_CONTACT_NONE, None)
        for part_id in contact_part_choices(self.ctl.project):
            self.contact_part.addItem(part_id, part_id)
        self.contact_part.setCurrentIndex(max(0, self.contact_part.findData(keep)))

    def _reason(self) -> str:
        """Why nothing can be changed here ("" when something can)."""
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

    def _fill_pins(self) -> None:
        h = self.ctl.project.harnesses.get(self._hid or "")
        c = next(
            (x for x in (h.connectors if h else []) if x.id == self.connector.currentText()), None
        )
        keep = self.pin.currentText()
        self.pin.clear()
        if c is not None:
            self.pin.addItems([p.id for p in c.pins])
            self.pin.setCurrentIndex(max(0, self.pin.findText(keep)))
        self._show_pin()

    def _show_pin(self) -> None:
        h = self.ctl.project.harnesses.get(self._hid or "")
        c = next(
            (x for x in (h.connectors if h else []) if x.id == self.connector.currentText()), None
        )
        pin = next((p for p in (c.pins if c else []) if p.id == self.pin.currentText()), None)
        if self.function.hasFocus() or self.contact.hasFocus():
            return
        self.function.setText((pin.function or "") if pin is not None else "")
        self.contact.setText((pin.contact_size or "") if pin is not None else "")
        i = self.termination.findData(pin.termination if pin is not None else "unspecified")
        self.termination.setCurrentIndex(max(0, i))
        wanted = pin.contact_part if pin is not None else None
        if wanted is not None and self.contact_part.findData(wanted) < 0:
            self.contact_part.addItem(wanted, wanted)  # (a part that left the library: still shown)
        self.contact_part.setCurrentIndex(max(0, self.contact_part.findData(wanted)))

    def _say(self, text: str) -> None:
        self.error.setText(text)
        self.error.setVisible(bool(text))

    # ---- the three actions -----------------------------------------------------------------
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

    def apply_pin(self) -> bool:
        cid, pin = self.connector.currentText(), self.pin.currentText()
        if self._hid is None or not cid or not pin:
            return False
        try:
            ops = plan_set_pin(
                self.ctl.project,
                self._hid,
                cid,
                pin,
                function=self.function.text(),
                termination=self.termination.currentData(),
                contact_size=self.contact.text(),
                contact_part=self.contact_part.currentData(),
            )
        except EditError as exc:
            self._say(str(exc))
            return False
        self._say("")
        return self.ctl.run(strings.STEP_SET_HARNESS_PIN.format(f"{cid}/{pin}"), ops)

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
