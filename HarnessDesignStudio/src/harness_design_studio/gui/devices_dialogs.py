"""Small dialogs of the Devices tab: a new connector part (with its mating half), a new interface
type, signals from an interface type on selected pins, and an interface on selected pins.

Each dialog asks the headless planner (`core.devices`) whether what is typed can be done, shows the
planner's own sentence under the fields while typing (never a message box) and keeps its OK button
off until it can. The dialog only collects values; the window runs them through the controller as
one named undo step.
"""

from collections.abc import Callable, Sequence
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from harness_design_studio.core import copies, devices
from harness_design_studio.core.device_library import DevicePlan, device_names, plan_device_import
from harness_design_studio.core.edit import EditError
from harness_design_studio.core.errors import HarnessError
from harness_design_studio.core.model import Project
from harness_design_studio.core.model.logical import Category
from harness_design_studio.gui import strings
from harness_design_studio.gui.notice import InlineNotice
from harness_design_studio.gui.tables import Column, DictTableModel, TableView
from harness_design_studio.gui.theme import ThemeManager

CATEGORIES: tuple[str, ...] = tuple(Category.__args__)  # type: ignore[attr-defined]


def _buttons(dialog: QDialog, ok_text: str) -> tuple[QPushButton, QHBoxLayout]:
    row = QHBoxLayout()
    row.addStretch(1)
    cancel = QPushButton(strings.CANCEL)
    cancel.setObjectName("dlg-cancel")
    cancel.clicked.connect(dialog.reject)
    ok = QPushButton(ok_text)
    ok.setObjectName("dlg-ok")
    ok.setProperty("primary", True)
    ok.setAutoDefault(True)
    ok.setDefault(True)
    ok.clicked.connect(dialog.accept)
    row.addWidget(cancel)
    row.addWidget(ok)
    return ok, row


def _field(edit: QLineEdit, name: str, tip: str, placeholder: str = "") -> QLineEdit:
    edit.setAccessibleName(name)
    edit.setToolTip(tip)
    if placeholder:
        edit.setPlaceholderText(placeholder)
    return edit


class _PlannerDialog(QDialog):
    """A dialog that asks a planner whether the values can be used: `check()` returns the
    planner's sentence (or None); it is shown in an inline notice and keeps OK off."""

    def __init__(self, parent: QWidget | None, theme: ThemeManager, title: str, name: str) -> None:
        super().__init__(parent)
        self.theme = theme
        self.setWindowTitle(title)
        self.setObjectName(name)
        self.setAccessibleName(title)
        self.lay = QVBoxLayout(self)
        self.notice = InlineNotice(theme)
        self.ok: QPushButton | None = None

    def _finish(self, ok_text: str) -> None:
        self.lay.addWidget(self.notice)
        self.ok, row = _buttons(self, ok_text)
        self.lay.addLayout(row)
        self.notice.hide()
        self.revalidate()

    def check(self) -> str | None:  # pragma: no cover - overridden
        return None

    def revalidate(self, *_: object) -> None:
        try:
            problem = self.check()
        except (EditError, HarnessError, ValueError) as exc:
            problem = str(exc)
        if problem:
            self.notice.show_notice("error", problem)
        else:
            self.notice.clear()
        if self.ok is not None:
            self.ok.setEnabled(problem is None)


# ---- a new device --------------------------------------------------------------------------------


class NewDeviceDialog(_PlannerDialog):
    """The name of a new device, asked before it exists. The ID follows the name until the person
    edits it; the subsystem is optional (the project's most used one is the default). The reason
    a device cannot be added shows under the fields; OK stays off until it can."""

    def __init__(self, parent: QWidget | None, theme: ThemeManager, project: Project) -> None:
        super().__init__(parent, theme, strings.NEWDEV_TITLE, "devices-new-device-dialog")
        self.project = project
        self._suggested = ""
        form = QFormLayout()
        self.name = _field(
            QLineEdit(), strings.NEWDEV_NAME, strings.NEWDEV_NAME_TIP, strings.NEWDEV_NAME_HINT
        )
        self.name.setObjectName("new-device-name")
        self.device_id = _field(QLineEdit(), strings.NEWDEV_ID, strings.NEWDEV_ID_TIP)
        self.device_id.setObjectName("new-device-id")
        self.subsystem = QComboBox()
        self.subsystem.setObjectName("new-device-subsystem")
        self.subsystem.setEditable(True)
        self.subsystem.setAccessibleName(strings.NEWDEV_SUBSYSTEM)
        self.subsystem.setToolTip(strings.NEWDEV_SUBSYSTEM_TIP)
        default = devices.default_subsystem(project)
        self.subsystem.addItems(sorted({u.subsystem for u in project.units.values()} | {default}))
        self.subsystem.setCurrentText(default)
        form.addRow(strings.NEWDEV_NAME, self.name)
        form.addRow(strings.NEWDEV_ID, self.device_id)
        form.addRow(strings.NEWDEV_SUBSYSTEM, self.subsystem)
        self.number = QSpinBox()
        self.number.setObjectName("new-device-number")
        self.number.setAccessibleName(strings.NEWDEV_NUMBER)
        self.number.setToolTip(strings.NEWDEV_NUMBER_TIP)
        self.number.setRange(1, copies.MAX_DEVICES)
        self.number.setValue(1)
        form.addRow(strings.NEWDEV_NUMBER, self.number)
        self.lay.addLayout(form)
        note = QLabel(strings.NEWDEV_NOTE)
        note.setProperty("muted", True)
        note.setWordWrap(True)
        self.lay.addWidget(note)
        self.name.textChanged.connect(self._name_changed)
        self.device_id.textChanged.connect(self.revalidate)
        self.number.valueChanged.connect(self.revalidate)
        self._finish(strings.NEWDEV_OK)
        self.name.setFocus()

    def _name_changed(self, text: str) -> None:
        """The ID follows the name while it still holds what the name suggested."""
        if self.device_id.text() == self._suggested:
            self._suggested = devices.suggest_device_id(self.project, text)
            self.device_id.setText(self._suggested)
        self.revalidate()

    def values(self) -> dict[str, Any]:
        return {
            "name": self.name.text().strip(),
            "unit_id": self.device_id.text().strip(),
            "subsystem": self.subsystem.currentText().strip() or None,
        }

    def count(self) -> int:
        """The number of these devices (1: just the one)."""
        return int(self.number.value())

    def check(self) -> str | None:
        v = self.values()
        problem = devices.check_new_device(self.project, v["unit_id"], v["name"])
        if not problem and self.count() > 1:
            taken = [
                c for c in copies.copy_ids(v["unit_id"], self.count())
                if c.casefold() in {u.casefold() for u in self.project.units}
            ]  # fmt: skip
            if taken:
                return f"ID {taken[0]} is already used by another device."
        return problem or None


# ---- a new connector part ------------------------------------------------------------------------


class NewPartDialog(_PlannerDialog):
    """A connector part for the library, and, when asked, its mating half. Both are made
    `pending` and `unverified`: the tool never approves a part."""

    def __init__(self, parent: QWidget | None, theme: ThemeManager, project: Project) -> None:
        super().__init__(parent, theme, strings.DVD_PART_TITLE, "devices-new-part-dialog")
        self.project = project
        form = QFormLayout()
        self.part_id = _field(QLineEdit(), strings.DVD_PART_ID, strings.DVD_PART_ID_TIP)
        self.part_id.setObjectName("new-part-id")
        self.pins = QSpinBox()
        self.pins.setObjectName("new-part-pins")
        self.pins.setRange(1, 1000)
        self.pins.setValue(9)
        self.pins.setAccessibleName(strings.DVD_PART_PINS)
        self.pins.setToolTip(strings.DVD_PART_PINS_TIP)
        self.gender = QComboBox()
        self.gender.setObjectName("new-part-gender")
        self.gender.setAccessibleName(strings.DVD_PART_GENDER)
        self.gender.setToolTip(strings.DVD_PART_GENDER_TIP)
        self.gender.addItem(strings.DV_GENDER["female"], "female")
        self.gender.addItem(strings.DV_GENDER["male"], "male")
        self.maker = _field(QLineEdit(), strings.DVD_PART_MAKER, strings.DVD_PART_MAKER_TIP)
        self.maker.setObjectName("new-part-maker")
        self.number = _field(QLineEdit(), strings.DVD_PART_NUMBER, strings.DVD_PART_NUMBER_TIP)
        self.number.setObjectName("new-part-number")
        self.description = _field(
            QLineEdit(), strings.DVD_PART_DESCRIPTION, strings.DVD_PART_DESCRIPTION_TIP
        )
        self.description.setObjectName("new-part-description")
        self.pair = QCheckBox(strings.DVD_PART_PAIR)
        self.pair.setObjectName("new-part-pair")
        self.pair.setChecked(True)
        self.pair.setAccessibleName(strings.DVD_PART_PAIR)
        self.pair.setToolTip(strings.DVD_PART_PAIR_TIP)
        self.mate = _field(QLineEdit(), strings.DVD_PART_MATE, strings.DVD_PART_MATE_TIP)
        self.mate.setObjectName("new-part-mate")
        for label, widget in (
            (strings.DVD_PART_ID, self.part_id),
            (strings.DVD_PART_PINS, self.pins),
            (strings.DVD_PART_GENDER, self.gender),
            (strings.DVD_PART_MAKER, self.maker),
            (strings.DVD_PART_NUMBER, self.number),
            (strings.DVD_PART_DESCRIPTION, self.description),
        ):
            form.addRow(label, widget)
        form.addRow("", self.pair)
        form.addRow(strings.DVD_PART_MATE, self.mate)
        self.lay.addLayout(form)
        note = QLabel(strings.DVD_PART_NOTE)
        note.setProperty("muted", True)
        note.setWordWrap(True)
        self.lay.addWidget(note)
        for w in (self.part_id, self.maker, self.number, self.description, self.mate):
            w.textChanged.connect(self.revalidate)
        self.pins.valueChanged.connect(self.revalidate)
        self.gender.currentIndexChanged.connect(self.revalidate)
        self.pair.toggled.connect(self._pair_toggled)
        self._finish(strings.DVD_PART_OK)
        self.part_id.setFocus()

    def _pair_toggled(self, on: bool) -> None:
        self.mate.setEnabled(on)
        self.revalidate()

    def values(self) -> tuple[bool, dict[str, Any]]:
        """(with a mating half?, the fields for the controller)."""
        fields: dict[str, Any] = {
            "part_id": self.part_id.text().strip(),
            "pin_count": self.pins.value(),
            "gender": self.gender.currentData(),
            "manufacturer": self.maker.text(),
            "part_number": self.number.text(),
            "description": self.description.text(),
        }
        if self.pair.isChecked():
            fields["mate_id"] = self.mate.text().strip() or None
        return self.pair.isChecked(), fields

    def check(self) -> str | None:
        pair, fields = self.values()
        if not fields["part_id"]:
            return strings.DVD_PART_NEEDS_ID
        if pair:
            devices.ops_add_part_pair(self.project, **fields)
        else:
            devices.ops_add_part(self.project, **fields)
        return None


# ---- a new interface type -----------------------------------------------------------------------


class NewTypeDialog(_PlannerDialog):
    """An interface type: ID, name, category and one line per signal. Marked `unverified`."""

    def __init__(self, parent: QWidget | None, theme: ThemeManager, project: Project) -> None:
        super().__init__(parent, theme, strings.DVD_TYPE_TITLE, "devices-new-type-dialog")
        self.project = project
        form = QFormLayout()
        self.type_id = _field(QLineEdit(), strings.DVD_TYPE_ID, strings.DVD_TYPE_ID_TIP)
        self.type_id.setObjectName("new-type-id")
        self.name = _field(QLineEdit(), strings.DVD_TYPE_NAME, strings.DVD_TYPE_NAME_TIP)
        self.name.setObjectName("new-type-name")
        self.category = QComboBox()
        self.category.setObjectName("new-type-category")
        self.category.setAccessibleName(strings.DVD_TYPE_CATEGORY)
        self.category.setToolTip(strings.DVD_TYPE_CATEGORY_TIP)
        for c in CATEGORIES:
            self.category.addItem(c, c)
        self.category.setCurrentIndex(self.category.findData("data"))
        self.signals = QPlainTextEdit()
        self.signals.setObjectName("new-type-signals")
        self.signals.setAccessibleName(strings.DVD_TYPE_SIGNALS)
        self.signals.setToolTip(strings.DVD_TYPE_SIGNALS_TIP)
        self.signals.setPlaceholderText(strings.DVD_TYPE_SIGNALS_EXAMPLE)
        self.signals.setTabChangesFocus(True)
        form.addRow(strings.DVD_TYPE_ID, self.type_id)
        form.addRow(strings.DVD_TYPE_NAME, self.name)
        form.addRow(strings.DVD_TYPE_CATEGORY, self.category)
        form.addRow(strings.DVD_TYPE_SIGNALS, self.signals)
        self.lay.addLayout(form)
        hint = QLabel(strings.DVD_TYPE_HINT)
        hint.setProperty("muted", True)
        hint.setWordWrap(True)
        self.lay.addWidget(hint)
        self.type_id.textChanged.connect(self.revalidate)
        self.name.textChanged.connect(self.revalidate)
        self.signals.textChanged.connect(self.revalidate)
        self.category.currentIndexChanged.connect(self.revalidate)
        self._finish(strings.DVD_TYPE_OK)
        self.type_id.setFocus()

    def values(self) -> dict[str, Any]:
        return {
            "type_id": self.type_id.text().strip(),
            "name": self.name.text(),
            "category": self.category.currentData(),
            "signals": devices.parse_signal_lines(self.signals.toPlainText()),
        }

    def check(self) -> str | None:
        if not self.type_id.text().strip():
            return strings.DVD_TYPE_NEEDS_ID
        devices.ops_add_interface_type(self.project, **self.values())
        return None


# ---- signals from an interface type on selected pins ---------------------------------------------


class FillDialog(_PlannerDialog):
    """Pick an interface type; its signals go on the selected pins in order (CANH, CANL, ...)."""

    def __init__(
        self,
        parent: QWidget | None,
        theme: ThemeManager,
        project: Project,
        connector_id: str,
        pin_ids: Sequence[str],
        on_new_type: Callable[[], None] | None = None,
    ) -> None:
        super().__init__(parent, theme, strings.DVD_FILL_TITLE, "devices-fill-dialog")
        self.project, self.connector_id, self.pin_ids = project, connector_id, list(pin_ids)
        self.wants_new_type = False
        self.type_box = QComboBox()
        self.type_box.setObjectName("fill-type")
        self.type_box.setAccessibleName(strings.DVD_FILL_TYPE)
        self.type_box.setToolTip(strings.DVD_FILL_TYPE_TIP)
        types = sorted(project.interface_types.values(), key=lambda t: (t.name.casefold(), t.id))
        fitting = [t for t in types if len(t.signals) == len(self.pin_ids)]
        for t in fitting + [t for t in types if t not in fitting]:
            self.type_box.addItem(f"{t.name}: {len(t.signals)} signals", t.id)
        self.lay.addWidget(QLabel(strings.DVD_FILL_PINS.format(", ".join(self.pin_ids))))
        self.lay.addWidget(self.type_box)
        self.model = DictTableModel(
            [
                Column("pin", strings.DV_COL_PIN, mono=True, width=70),
                Column("signal", strings.DV_COL_SIGNAL, mono=True, width=130),
                Column("direction", strings.DV_COL_DIRECTION, width=90),
            ],
            (),
            theme,
        )
        self.table = TableView(self.model, theme, name=strings.DVD_FILL_PREVIEW)
        self.table.setObjectName("fill-preview")
        self.table.setMaximumHeight(theme.px(200))
        self.lay.addWidget(self.table)
        self.fixed = QCheckBox(strings.DVD_FILL_FIXED)
        self.fixed.setObjectName("fill-fixed")
        self.fixed.setChecked(True)
        self.fixed.setAccessibleName(strings.DVD_FILL_FIXED)
        self.fixed.setToolTip(strings.DVD_FILL_FIXED_TIP)
        self.lay.addWidget(self.fixed)
        self.new_type = QPushButton(strings.DVD_NEW_TYPE)
        self.new_type.setObjectName("fill-new-type")
        self.new_type.setToolTip(strings.DVD_NEW_TYPE_TIP)
        self.new_type.setAccessibleName(strings.DVD_NEW_TYPE)
        self.new_type.clicked.connect(self._new_type)
        self.lay.addWidget(self.new_type, 0, Qt.AlignmentFlag.AlignLeft)
        self.type_box.currentIndexChanged.connect(self._refill)
        self.fixed.toggled.connect(self.revalidate)
        self._finish(strings.DVD_FILL_OK)
        self._refill()

    def _new_type(self) -> None:
        self.wants_new_type = True
        self.reject()

    def type_id(self) -> str:
        return str(self.type_box.currentData() or "")

    def _refill(self, *_: object) -> None:
        t = self.project.interface_types.get(self.type_id())
        rows = []
        if t is not None:
            for k, s in enumerate(t.signals):
                pin = self.pin_ids[k] if k < len(self.pin_ids) else ""
                rows.append({"pin": pin, "signal": s.name, "direction": s.direction})
        self.model.set_rows(rows)
        self.revalidate()

    def check(self) -> str | None:
        if not self.type_id():
            return strings.DVD_FILL_NO_TYPE
        devices.fill_from_type(
            self.project,
            self.connector_id,
            self.pin_ids,
            self.type_id(),
            fixed=self.fixed.isChecked(),
        )
        return None


# ---- the cable contact of selected pins -----------------------------------------------------------


class ContactDialog(_PlannerDialog):
    """Pick a contact part (or none); it becomes the cable contact of the selected pins."""

    def __init__(
        self,
        parent: QWidget | None,
        theme: ThemeManager,
        project: Project,
        connector_id: str,
        pin_ids: Sequence[str],
    ) -> None:
        super().__init__(parent, theme, strings.DVD_CONTACT_TITLE, "devices-contact-dialog")
        self.project, self.connector_id, self.pin_ids = project, connector_id, list(pin_ids)
        self.part_box = QComboBox()
        self.part_box.setObjectName("contact-part")
        self.part_box.setAccessibleName(strings.DVD_CONTACT_PART)
        self.part_box.setToolTip(strings.DVD_CONTACT_PART_TIP)
        self.part_box.addItem(strings.DV_CONTACT_PART_NONE, "")
        for part_id in devices.contact_part_choices(project):
            self.part_box.addItem(part_id, part_id)
        self.lay.addWidget(QLabel(strings.DVD_CONTACT_PINS.format(", ".join(self.pin_ids))))
        self.lay.addWidget(self.part_box)
        self.part_box.currentIndexChanged.connect(self.revalidate)
        self._finish(strings.DVD_CONTACT_OK)

    def part_id(self) -> str:
        return str(self.part_box.currentData() or "")

    def check(self) -> str | None:
        if self.part_box.count() == 1:
            return strings.DVD_CONTACT_NO_PARTS
        devices.ops_set_contacts(self.project, self.connector_id, self.pin_ids, self.part_id())
        return None


# ---- an interface on selected pins ---------------------------------------------------------------


class AssignDialog(_PlannerDialog):
    """Pick an interface that ends on this device; each of its signals gets one of the selected
    pins (in order, and changeable). The pins become locked to the interface."""

    def __init__(
        self,
        parent: QWidget | None,
        theme: ThemeManager,
        project: Project,
        connector_id: str,
        pin_ids: Sequence[str],
    ) -> None:
        super().__init__(parent, theme, strings.DVD_ASSIGN_TITLE, "devices-assign-dialog")
        self.project, self.connector_id, self.pin_ids = project, connector_id, list(pin_ids)
        self.wants_new_interface = False
        unit = project.connectors[connector_id].unit_id
        self.interface_box = QComboBox()
        self.interface_box.setObjectName("assign-interface")
        self.interface_box.setAccessibleName(strings.DVD_ASSIGN_INTERFACE)
        self.interface_box.setToolTip(strings.DVD_ASSIGN_INTERFACE_TIP)
        for i in sorted(project.interfaces.values(), key=lambda x: x.id):
            if any(e.unit_id == unit for e in i.endpoints):
                t = project.interface_types.get(i.type_id)
                others = ", ".join(e.unit_id for e in i.endpoints if e.unit_id != unit)
                label = f"{i.id}: {t.name if t else i.type_id}" + (f" ({others})" if others else "")
                self.interface_box.addItem(label, i.id)
        self.lay.addWidget(QLabel(strings.DVD_ASSIGN_PINS.format(", ".join(self.pin_ids))))
        self.lay.addWidget(self.interface_box)
        self.form_host = QWidget()
        self.form = QFormLayout(self.form_host)
        self.lay.addWidget(self.form_host)
        self.signal_boxes: list[tuple[str, QComboBox]] = []
        self.new_interface = QPushButton(strings.DVD_NEW_INTERFACE)
        self.new_interface.setObjectName("assign-new-interface")
        self.new_interface.setAccessibleName(strings.DVD_NEW_INTERFACE)
        self.new_interface.setToolTip(strings.DVD_NEW_INTERFACE_TIP)
        self.new_interface.clicked.connect(self._new_interface)
        self.lay.addWidget(self.new_interface, 0, Qt.AlignmentFlag.AlignLeft)
        self.interface_box.currentIndexChanged.connect(self._rebuild)
        self._finish(strings.DVD_ASSIGN_OK)
        self._rebuild()

    def _new_interface(self) -> None:
        self.wants_new_interface = True
        self.reject()

    def interface_id(self) -> str:
        return str(self.interface_box.currentData() or "")

    def _rebuild(self, *_: object) -> None:
        while self.form.rowCount():
            self.form.removeRow(0)
        self.signal_boxes = []
        i = self.project.interfaces.get(self.interface_id())
        t = self.project.interface_types.get(i.type_id) if i else None
        if t is not None:
            for k, s in enumerate(t.signals):
                box = QComboBox()
                box.setObjectName(f"assign-pin-{s.name}")
                box.setAccessibleName(strings.DVD_ASSIGN_PIN_FOR.format(s.name))
                box.setToolTip(strings.DVD_ASSIGN_PIN_FOR.format(s.name))
                for pid in self.pin_ids:
                    box.addItem(pid, pid)
                if k < len(self.pin_ids):
                    box.setCurrentIndex(k)
                box.currentIndexChanged.connect(self.revalidate)
                self.form.addRow(f"{s.name} ({s.direction})", box)
                self.signal_boxes.append((s.name, box))
        self.revalidate()

    def assignment(self) -> tuple[list[str], list[str]]:
        """(pins, signals) in the order of the signals, as the planner takes them."""
        pins = [str(b.currentData()) for _s, b in self.signal_boxes]
        return pins, [s for s, _b in self.signal_boxes]

    def check(self) -> str | None:
        if not self.interface_id():
            return strings.DVD_ASSIGN_NONE
        pins, signals = self.assignment()
        devices.ops_assign_pins(self.project, self.connector_id, pins, self.interface_id(), signals)
        return None


# ---- devices from a library file -----------------------------------------------------------------


class LibraryDialog(_PlannerDialog):
    """The devices of a device library file with a tick box each, and under them what adding the
    ticked ones would do (new IDs, parts kept, anything left out). OK stays off until a ticked
    device can be added."""

    def __init__(
        self, parent: QWidget | None, theme: ThemeManager, project: Project, data: dict[str, Any]
    ) -> None:
        super().__init__(parent, theme, strings.DV_LIB_TITLE, "devices-library-dialog")
        self.project, self.data = project, data
        self.devices = QListWidget()
        self.devices.setObjectName("library-devices")
        self.devices.setAccessibleName(strings.DV_LIB_LIST)
        self.devices.setToolTip(strings.DV_LIB_LIST_TIP)
        for uid, name in device_names(data):
            item = QListWidgetItem(strings.DV_LIB_ITEM.format(uid, name))
            item.setData(Qt.ItemDataRole.UserRole, uid)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked)
            self.devices.addItem(item)
        self.devices.itemChanged.connect(self.revalidate)
        self.preview = QLabel()
        self.preview.setObjectName("library-preview")
        self.preview.setProperty("muted", True)
        self.preview.setWordWrap(True)
        self.lay.addWidget(QLabel(strings.DV_LIB_LIST))
        self.lay.addWidget(self.devices)
        self.lay.addWidget(self.preview)
        self._plan: DevicePlan | None = None
        self._chosen: list[str] = []
        self._finish(strings.DV_LIB_ADD_BUTTON)

    def selected(self) -> list[str]:
        out = []
        for k in range(self.devices.count()):
            item = self.devices.item(k)
            if item is not None and item.checkState() == Qt.CheckState.Checked:
                out.append(str(item.data(Qt.ItemDataRole.UserRole)))
        return out

    def plan(self) -> DevicePlan:
        """What adding the ticked devices does now (the ops are for the controller)."""
        chosen = self.selected()
        if self._plan is None or self._chosen != chosen:
            self._chosen = chosen
            self._plan = plan_device_import(self.project, self.data, chosen)
        return self._plan

    def check(self) -> str | None:
        chosen = self.selected()
        if not chosen:
            self.preview.setText("")
            return strings.DV_LIB_NONE
        plan = self.plan()
        lines = [
            strings.DV_LIB_ROW_OK.format(r.unit_id, r.new_id, r.connectors, r.pins)
            for r in plan.rows
            if r.ok
        ]
        self.preview.setText(" ".join(lines + plan.notes))
        bad = next((r for r in plan.rows if not r.ok), None)
        if bad is not None:
            return f"{bad.unit_id}: {bad.message}"
        return None
