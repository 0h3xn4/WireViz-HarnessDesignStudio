"""Pick a connector as a family, a number of pins and a gender (Release 1.9, W1).

One small widget for the two places that add a first connector without the Devices tab: the dialog
**Add device** and the **Add a connector** window of the connection window. It lists the connector
parts of the library (`core.first_connector`); the part behind the choice is `part_id()`. With
`optional` the first family is "No connector yet" and the other two boxes are off.

    picker = ConnectorPicker(project, optional=True)
    picker.part_id()      # "EX-MICROD-15-F", or "" for no connector
"""

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QComboBox, QFormLayout, QWidget

from harness_design_studio.core.first_connector import ConnectorChoice, connector_choices
from harness_design_studio.core.model import Project
from harness_design_studio.gui import strings


class ConnectorPicker(QWidget):
    changed = Signal()

    def __init__(self, project: Project, *, optional: bool = False) -> None:
        super().__init__()
        self.optional = optional
        self.setObjectName("connector-picker")
        self._choices = connector_choices(project)
        self.family = self._box("connector-family", strings.CPICK_FAMILY, strings.CPICK_FAMILY_TIP)
        self.pins = self._box("connector-pins", strings.CPICK_PINS, strings.CPICK_PINS_TIP)
        self.gender = self._box("connector-gender", strings.CPICK_GENDER, strings.CPICK_GENDER_TIP)
        form = QFormLayout(self)
        form.setContentsMargins(0, 0, 0, 0)
        form.addRow(strings.CPICK_FAMILY, self.family)
        form.addRow(strings.CPICK_PINS, self.pins)
        form.addRow(strings.CPICK_GENDER, self.gender)
        if optional:
            self.family.addItem(strings.CPICK_NONE, "")
        seen: set[str] = set()
        for c in self._choices:
            if c.family not in seen:
                seen.add(c.family)
                self.family.addItem(c.label, c.family)
        self.family.currentIndexChanged.connect(lambda _i: self._family_changed())
        self.pins.currentIndexChanged.connect(lambda _i: self._pins_changed())
        self.gender.currentIndexChanged.connect(lambda _i: self.changed.emit())
        self._family_changed()

    @staticmethod
    def _box(name: str, accessible: str, tip: str) -> QComboBox:
        box = QComboBox()
        box.setObjectName(name)
        box.setAccessibleName(accessible)
        box.setToolTip(tip)
        return box

    def available(self) -> bool:
        """The library has a connector part to pick."""
        return bool(self._choices)

    def _of_family(self) -> list[ConnectorChoice]:
        key = self.family.currentData()
        return [c for c in self._choices if c.family == key] if key else []

    def _family_changed(self) -> None:
        mine = self._of_family()
        self.pins.blockSignals(True)
        self.pins.clear()
        for n in sorted({c.pin_count for c in mine}):
            self.pins.addItem(str(n), n)
        self.pins.blockSignals(False)
        self.pins.setEnabled(bool(mine))
        self._pins_changed(emit=False)
        self.changed.emit()

    def _pins_changed(self, emit: bool = True) -> None:
        n = self.pins.currentData()
        mine = [c for c in self._of_family() if c.pin_count == n]
        self.gender.blockSignals(True)
        self.gender.clear()
        for c in mine:
            self.gender.addItem(strings.DV_GENDER[c.gender], c.part_id)
        self.gender.blockSignals(False)
        self.gender.setEnabled(len(mine) > 1)
        if emit:
            self.changed.emit()

    def part_id(self) -> str:
        """The part of the choice, "" when none (the first family of an optional picker)."""
        return str(self.gender.currentData() or "")

    def select(self, part_id: str) -> bool:
        """Show this part (for tests and for a caller that knows what it wants)."""
        c = next((c for c in self._choices if c.part_id == part_id), None)
        if c is None:
            return False
        self.family.setCurrentIndex(self.family.findData(c.family))
        self.pins.setCurrentIndex(self.pins.findData(c.pin_count))
        self.gender.setCurrentIndex(self.gender.findData(part_id))
        return True
