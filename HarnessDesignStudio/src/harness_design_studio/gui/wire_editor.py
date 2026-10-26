"""The Edit wire form of the Harness tab: gauge, type, colour, length, label and note of the
selected wires, and a button that gives them back to generation.

    editor = WireEditor(ctl, theme)
    editor.show_wires(["W001-0001", "W001-0002"])        # the selection of the wire table

A field that shows its common value (or "various" when the wires differ) changes nothing until the
person types in it; Apply then sets only the fields that were touched, on every selected wire, as
one undo step. Gauge, type, colour and length lock the wire, so Generate keeps them; label and note
are always kept. Mistakes are said in words under the form, never in a message box. Everything is
disabled for a released harness and for a read-only project, with the reason shown.

The strip lengths (Strip A at the From end, Strip B at the To end, 1.7.0) are in the same form: they
are applied with the other touched fields as one undo step and never lock the wire. A button gives
every wire of the harness the lengths in the two fields (`core/build_data.py`).
"""

from collections.abc import Callable, Sequence

from PySide6.QtCore import Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from harness_design_studio.core.build_data import plan_set_strip, plan_set_strip_all
from harness_design_studio.core.commands import Op, Put
from harness_design_studio.core.edit import EditError
from harness_design_studio.core.model import Harness, ShieldGroup, Wire, evolve
from harness_design_studio.core.wirecolours import COLOURS
from harness_design_studio.core.wires import (
    find_wire,
    group_of,
    new_wire_id,
    pin_choices,
    plan_add_wire,
    plan_delete_wires,
    plan_group_wires,
    plan_set_labels,
    plan_ungroup_all,
    plan_wire_edit,
    plan_wire_reset,
    wire_part_choices,
)
from harness_design_studio.gui import strings
from harness_design_studio.gui.controller import EditorController
from harness_design_studio.gui.harness_edit_dialogs import BulkWireDialog, ChangeGroupDialog
from harness_design_studio.gui.icons import icon_button
from harness_design_studio.gui.theme import ThemeManager

FIELDS = ("gauge_awg", "part_id", "colour", "length_m", "label", "note")
STRIP_FIELDS = (
    "strip_a_mm",
    "strip_b_mm",
)  # (planned by core/build_data.py, not by plan_wire_edit)


def _common(values: Sequence[object]) -> object | None:
    """The value all wires share, or None when they differ."""
    first = values[0]
    return first if all(v == first for v in values) else None


class _EndPicker(QWidget):
    """A connector and a pin of that connector, as two lists."""

    changed = Signal()

    def __init__(self, name: str, text: str, tip: str) -> None:
        super().__init__()
        self.setObjectName(name)
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        self.connector = QComboBox()
        self.pin = QComboBox()
        for box, suffix, label in (
            (self.connector, "connector", strings.WIRE_CONNECTOR),
            (self.pin, "pin", strings.WIRE_PIN),
        ):
            box.setObjectName(f"{name}-{suffix}")
            box.setAccessibleName(f"{text} {label.lower()}")
            box.setToolTip(tip)
            row.addWidget(box, 2 if suffix == "connector" else 1)
        self._choices: dict[str, list[str]] = {}
        self._filling = False
        self.connector.activated.connect(lambda _i: self._connector_chosen())
        self.pin.activated.connect(lambda _i: self.changed.emit())

    def fill(self, choices: dict[str, list[str]], connector: str = "", pin: str = "") -> None:
        self._filling = True
        try:
            self._choices = choices
            self.connector.clear()
            self.connector.addItems(list(choices))
            self.connector.setCurrentIndex(max(0, self.connector.findText(connector)))
            self._fill_pins(pin)
        finally:
            self._filling = False

    def _fill_pins(self, pin: str = "") -> None:
        self.pin.clear()
        self.pin.addItems(self._choices.get(self.connector.currentText(), []))
        self.pin.setCurrentIndex(max(0, self.pin.findText(pin)))

    def _connector_chosen(self) -> None:
        self._fill_pins()
        self.changed.emit()

    def value(self) -> tuple[str, str]:
        return self.connector.currentText(), self.pin.currentText()

    def set_enabled(self, on: bool) -> None:
        self.connector.setEnabled(on)
        self.pin.setEnabled(on)


class NewWireForm(QWidget):
    """Add a wire that you draw between two pins of the connectors of the harness."""

    wireAdded = Signal(str)

    def __init__(self, ctl: EditorController, theme: ThemeManager) -> None:
        super().__init__()
        self.ctl = ctl
        self.setObjectName("new-wire-form")
        self._hid: str | None = None
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(theme.space(8))
        title = QLabel(strings.WIRE_NEW)
        title.setProperty("heading", True)
        root.addWidget(title)
        form = QFormLayout()
        form.setHorizontalSpacing(theme.space(8))
        form.setVerticalSpacing(theme.space(4))
        self.start = _EndPicker(
            "new-wire-from", strings.WIRE_FROM, strings.WIRE_END_TIP.format("start")
        )
        self.end = _EndPicker("new-wire-to", strings.WIRE_TO, strings.WIRE_END_TIP.format("end"))
        self.signal = QLineEdit()
        self.signal.setObjectName("new-wire-signal")
        self.signal.setAccessibleName(strings.WIRE_SIGNAL)
        self.signal.setToolTip(strings.WIRE_SIGNAL_TIP)
        form.addRow(strings.WIRE_FROM, self.start)
        form.addRow(strings.WIRE_TO, self.end)
        form.addRow(strings.WIRE_SIGNAL, self.signal)
        root.addLayout(form)
        self.error = QLabel()
        self.error.setObjectName("new-wire-error")
        self.error.setWordWrap(True)
        self.error.setProperty("error", True)
        self.error.setVisible(False)
        root.addWidget(self.error)
        self.add = QPushButton()
        self.add.setObjectName("new-wire-add")
        icon_button(self.add, "pass", theme, strings.WIRE_ADD_TIP, text=strings.WIRE_ADD)
        root.addWidget(self.add)
        self.add.clicked.connect(self.add_wire)
        self.signal.returnPressed.connect(self.add_wire)
        self.set_harness(None)

    def set_harness(self, harness_id: str | None) -> None:
        """Offer the connectors and pins of this harness (None: nothing to choose from)."""
        self._hid = harness_id
        choices: dict[str, list[str]] = {}
        if harness_id is not None and harness_id in self.ctl.project.harnesses:
            choices = pin_choices(self.ctl.project, harness_id)
        keep = (self.start.value(), self.end.value())
        self.start.fill(choices, *keep[0])
        self.end.fill(choices, *keep[1])
        if choices and keep[0] == keep[1] == ("", ""):
            self.end.pin.setCurrentIndex(min(1, self.end.pin.count() - 1))
        self._enable()

    def _enable(self) -> None:
        h = self.ctl.project.harnesses.get(self._hid or "")
        on = h is not None and h.status != "released" and not self.ctl.read_only
        for w in (self.add, self.signal):
            w.setEnabled(on)
        self.start.set_enabled(on)
        self.end.set_enabled(on)

    def add_wire(self) -> bool:
        if self._hid is None:
            self._say(strings.WIRE_NEW_NO_HARNESS)
            return False
        (c1, p1), (c2, p2) = self.start.value(), self.end.value()
        try:
            ops = plan_add_wire(
                self.ctl.project, self._hid, c1, p1, c2, p2, signal=self.signal.text()
            )
            wid = new_wire_id(self.ctl.project, self._hid)
        except EditError as exc:
            self._say(str(exc))
            return False
        if not self.ctl.run(strings.STEP_ADD_WIRE, ops):
            return False
        self._say("")
        self.signal.clear()
        self.wireAdded.emit(wid)
        return True

    def _say(self, text: str) -> None:
        self.error.setText(text)
        self.error.setVisible(bool(text))


class LabelsForm(QWidget):
    """The label of the harness and of one of its cable connectors (what `labels.csv` prints)."""

    def __init__(self, ctl: EditorController, theme: ThemeManager) -> None:
        super().__init__()
        self.ctl = ctl
        self.setObjectName("labels-form")
        self._hid: str | None = None
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(theme.space(8))
        title = QLabel(strings.LABELS_TITLE)
        title.setProperty("heading", True)
        root.addWidget(title)
        form = QFormLayout()
        form.setHorizontalSpacing(theme.space(8))
        form.setVerticalSpacing(theme.space(4))
        self.harness_label = QLineEdit()
        self.connector = QComboBox()
        self.connector_label = QLineEdit()
        for widget, name, text, tip in (
            (
                self.harness_label,
                "labels-harness",
                strings.LABELS_HARNESS,
                strings.LABELS_HARNESS_TIP,
            ),
            (
                self.connector,
                "labels-connector",
                strings.LABELS_CONNECTOR,
                strings.LABELS_CONNECTOR_TIP,
            ),
            (
                self.connector_label,
                "labels-connector-label",
                strings.LABELS_CONNECTOR_LABEL,
                strings.LABELS_CONNECTOR_LABEL_TIP,
            ),
        ):
            widget.setObjectName(name)
            widget.setAccessibleName(text)
            widget.setToolTip(tip)
            form.addRow(text, widget)
        root.addLayout(form)
        self.error = QLabel()
        self.error.setObjectName("labels-error")
        self.error.setWordWrap(True)
        self.error.setProperty("error", True)
        self.error.setVisible(False)
        root.addWidget(self.error)
        self.apply = QPushButton()
        self.apply.setObjectName("labels-apply")
        icon_button(self.apply, "pass", theme, strings.LABELS_APPLY_TIP, text=strings.LABELS_APPLY)
        root.addWidget(self.apply)
        self.apply.clicked.connect(self.apply_labels)
        self.connector.activated.connect(lambda _i: self._show_connector())
        self.harness_label.returnPressed.connect(self.apply_labels)
        self.connector_label.returnPressed.connect(self.apply_labels)
        self.set_harness(None)

    def set_harness(self, harness_id: str | None) -> None:
        """Show the labels of this harness and of its cable connectors."""
        keep = self.connector.currentText()
        self._hid = harness_id
        h = self.ctl.project.harnesses.get(harness_id or "")
        self.connector.clear()
        if h is not None:
            self.connector.addItems(sorted(c.id for c in h.connectors))
            self.connector.setCurrentIndex(max(0, self.connector.findText(keep)))
        if not self.harness_label.hasFocus():
            self.harness_label.setText((h.label or "") if h is not None else "")
        self._show_connector()
        on = h is not None and h.status != "released" and not self.ctl.read_only
        for w in (self.harness_label, self.connector, self.connector_label, self.apply):
            w.setEnabled(on)

    def _show_connector(self) -> None:
        h = self.ctl.project.harnesses.get(self._hid or "")
        c = next(
            (c for c in (h.connectors if h else []) if c.id == self.connector.currentText()), None
        )
        if not self.connector_label.hasFocus():
            self.connector_label.setText((c.label or "") if c is not None else "")

    def apply_labels(self) -> bool:
        if self._hid is None or not self.apply.isEnabled():
            return False
        cid = self.connector.currentText()
        try:
            ops = plan_set_labels(
                self.ctl.project,
                self._hid,
                harness=self.harness_label.text(),
                connectors={cid: self.connector_label.text()} if cid else None,
            )
        except EditError as exc:
            self.error.setText(str(exc))
            self.error.setVisible(True)
            return False
        self.error.setVisible(False)
        return not ops or self.ctl.run(strings.STEP_SET_LABELS, ops)


class WireEditor(QWidget):
    wireAdded = Signal(str)

    def __init__(self, ctl: EditorController, theme: ThemeManager) -> None:
        super().__init__()
        self.ctl = ctl
        self.theme = theme
        self.setObjectName("wire-editor")
        self._ids: list[str] = []
        self._touched: set[str] = set()
        self._filling = False
        self.run_dialog: Callable[[QDialog], int] = lambda dlg: dlg.exec()  # (the window sets it)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(theme.space(8))
        self.title = QLabel(strings.WIRE_EDIT_NONE)
        self.title.setObjectName("wire-editor-title")
        self.title.setWordWrap(True)
        root.addWidget(self.title)

        form = QFormLayout()
        form.setHorizontalSpacing(theme.space(8))
        form.setVerticalSpacing(theme.space(4))
        self.gauge = QLineEdit()
        self.part = QComboBox()
        self.colour = QComboBox()
        self.colour.setEditable(True)
        self.length = QLineEdit()
        self.strip_a = QLineEdit()
        self.strip_b = QLineEdit()
        self.label = QLineEdit()
        self.note = QPlainTextEdit()
        self.note.setFixedHeight(theme.px(56))
        for widget, name, text, tip in (
            (self.gauge, "wire-gauge", strings.WIRE_GAUGE, strings.WIRE_GAUGE_TIP),
            (self.part, "wire-type", strings.WIRE_TYPE, strings.WIRE_TYPE_TIP),
            (self.colour, "wire-colour", strings.WIRE_COLOUR, strings.WIRE_COLOUR_TIP),
            (self.length, "wire-length", strings.WIRE_LENGTH, strings.WIRE_LENGTH_TIP),
            (self.strip_a, "wire-strip-a", strings.WIRE_STRIP_A, strings.WIRE_STRIP_A_TIP),
            (self.strip_b, "wire-strip-b", strings.WIRE_STRIP_B, strings.WIRE_STRIP_B_TIP),
            (self.label, "wire-label", strings.WIRE_LABEL, strings.WIRE_LABEL_TIP),
            (self.note, "wire-note", strings.WIRE_NOTE, strings.WIRE_NOTE_TIP),
        ):
            widget.setObjectName(name)
            widget.setAccessibleName(text)
            widget.setToolTip(tip)
            form.addRow(text, widget)
        root.addLayout(form)
        strip_note = QLabel(strings.WIRE_STRIP_NOTE)
        strip_note.setObjectName("wire-strip-note")
        strip_note.setWordWrap(True)
        strip_note.setProperty("muted", True)
        root.addWidget(strip_note)

        self.ends = QWidget()  # the ends of a wire that you drew
        ends_form = QFormLayout(self.ends)
        ends_form.setContentsMargins(0, 0, 0, 0)
        ends_form.setHorizontalSpacing(theme.space(8))
        ends_form.setVerticalSpacing(theme.space(4))
        self.from_end = _EndPicker(
            "wire-from", strings.WIRE_FROM, strings.WIRE_END_TIP.format("start")
        )
        self.to_end = _EndPicker("wire-to", strings.WIRE_TO, strings.WIRE_END_TIP.format("end"))
        ends_form.addRow(strings.WIRE_FROM, self.from_end)
        ends_form.addRow(strings.WIRE_TO, self.to_end)
        self.ends.setVisible(False)
        root.addWidget(self.ends)

        self.state = QLabel()
        self.state.setObjectName("wire-editor-state")
        self.state.setWordWrap(True)
        self.state.setProperty("muted", True)
        root.addWidget(self.state)
        self.error = QLabel()
        self.error.setObjectName("wire-editor-error")
        self.error.setWordWrap(True)
        self.error.setProperty("error", True)
        self.error.setVisible(False)
        root.addWidget(self.error)

        self.apply = QPushButton()
        self.apply.setObjectName("wire-apply")
        self.apply.setProperty("primary", True)
        icon_button(self.apply, "pass", theme, strings.WIRE_APPLY_TIP, text=strings.WIRE_APPLY)
        self.reset = QPushButton()
        self.reset.setObjectName("wire-reset")
        icon_button(self.reset, "unlock", theme, strings.WIRE_RESET_TIP, text=strings.WIRE_RESET)
        root.addWidget(self.apply)
        root.addWidget(self.reset)
        self.strip_all = QPushButton()
        self.strip_all.setObjectName("wire-strip-all")
        icon_button(
            self.strip_all, "pass", theme, strings.WIRE_STRIP_ALL_TIP, text=strings.WIRE_STRIP_ALL
        )
        root.addWidget(self.strip_all)
        self.strip_result = QLabel()
        self.strip_result.setObjectName("wire-strip-result")
        self.strip_result.setWordWrap(True)
        self.strip_result.setProperty("muted", True)
        self.strip_result.setVisible(False)
        root.addWidget(self.strip_result)
        self.bulk_btn = QPushButton()
        self.bulk_btn.setObjectName("wire-bulk")
        icon_button(self.bulk_btn, "pass", theme, strings.WIRE_BULK_TIP, text=strings.WIRE_BULK)
        root.addWidget(self.bulk_btn)
        self.delete = QPushButton()
        self.delete.setObjectName("wire-delete")
        icon_button(self.delete, "close", theme, strings.WIRE_DELETE_TIP, text=strings.WIRE_DELETE)
        self.delete.setVisible(False)
        root.addWidget(self.delete)
        self.group_label = QLabel()
        self.group_label.setObjectName("wire-group-label")
        self.group_label.setProperty("muted", True)
        root.addWidget(self.group_label)
        group_row = QHBoxLayout()
        self.group_kind = QComboBox()
        self.group_kind.setObjectName("wire-group-kind")
        self.group_kind.setAccessibleName(strings.WIRE_GROUP_KIND)
        self.group_kind.setToolTip(strings.WIRE_GROUP_KIND_TIP)
        for kind, label in strings.WIRE_GROUP_KINDS:
            self.group_kind.addItem(label, kind)
        self.group_btn = QPushButton()
        self.group_btn.setObjectName("wire-group")
        icon_button(
            self.group_btn, "harness", theme, strings.WIRE_GROUP_TIP, text=strings.WIRE_GROUP
        )
        self.ungroup_btn = QPushButton()
        self.ungroup_btn.setObjectName("wire-ungroup")
        icon_button(
            self.ungroup_btn, "unlock", theme, strings.WIRE_UNGROUP_TIP, text=strings.WIRE_UNGROUP
        )
        group_row.addWidget(self.group_kind, 1)
        group_row.addWidget(self.group_btn)
        group_row.addWidget(self.ungroup_btn)
        root.addLayout(group_row)
        self.change_group_btn = QPushButton()
        self.change_group_btn.setObjectName("wire-change-group")
        icon_button(
            self.change_group_btn,
            "harness",
            theme,
            strings.WIRE_CHANGE_GROUP_TIP,
            text=strings.WIRE_CHANGE_GROUP,
        )
        self.change_group_btn.setVisible(False)
        root.addWidget(self.change_group_btn)
        self._hid: str | None = None
        self.new_form = NewWireForm(ctl, theme)
        self.new_form.wireAdded.connect(self.wireAdded)
        root.addSpacing(theme.space(8))
        root.addWidget(self.new_form)
        self.labels_form = LabelsForm(ctl, theme)
        root.addSpacing(theme.space(8))
        root.addWidget(self.labels_form)
        root.addStretch(1)

        self.apply.clicked.connect(self.apply_changes)
        self.reset.clicked.connect(self.reset_wires)
        self.strip_all.clicked.connect(self.apply_strip_to_all)
        self.delete.clicked.connect(self.delete_wires)
        self.group_btn.clicked.connect(self.group_wires)
        self.ungroup_btn.clicked.connect(self.ungroup_wires)
        self.change_group_btn.clicked.connect(self.change_group)
        self.bulk_btn.clicked.connect(self.bulk_edit)
        self.from_end.changed.connect(lambda: self._touched.update({"from_connector", "from_pin"}))
        self.to_end.changed.connect(lambda: self._touched.update({"to_connector", "to_pin"}))
        for w in (self.gauge, self.length, self.strip_a, self.strip_b, self.label):
            w.textEdited.connect(lambda _t, w=w: self._touch(w))
        self.part.activated.connect(lambda _i: self._touch(self.part))
        self.colour.activated.connect(lambda _i: self._touch(self.colour))
        colour_edit = self.colour.lineEdit()
        if colour_edit is not None:
            colour_edit.setAccessibleName(strings.WIRE_COLOUR)
            colour_edit.textEdited.connect(lambda _t: self._touch(self.colour))
        self.note.textChanged.connect(lambda: self._touch(self.note))
        for w in (self.gauge, self.length, self.strip_a, self.strip_b, self.label):
            w.returnPressed.connect(self.apply_changes)
        QShortcut(QKeySequence("Ctrl+Return"), self, self.apply_changes)
        self._names = {
            self.gauge: "gauge_awg",
            self.part: "part_id",
            self.colour: "colour",
            self.length: "length_m",
            self.strip_a: "strip_a_mm",
            self.strip_b: "strip_b_mm",
            self.label: "label",
            self.note: "note",
        }
        self.show_wires([])

    # ---- the selection ---------------------------------------------------------------------
    @property
    def dirty(self) -> bool:
        """True while the person has typed something that is not applied yet."""
        return bool(self._touched)

    def wire_ids(self) -> list[str]:
        return list(self._ids)

    def show_wires(self, wire_ids: Sequence[str]) -> None:
        """Show the wires (those that still exist), reading their values from the project."""
        p = self.ctl.project
        found: list[tuple[str, Wire]] = []
        for wid in wire_ids:
            try:
                found.append((wid, find_wire(p, wid)[1]))
            except EditError:
                continue
        self._ids = [wid for wid, _w in found]
        self._touched.clear()
        self.error.setVisible(False)
        self._filling = True
        try:
            self._fill([w for _i, w in found])
        finally:
            self._filling = False
        self._show_ends()
        self._enable()

    def set_harness(self, harness_id: str | None) -> None:
        """The harness whose connectors the *New wire* form offers."""
        self._hid = harness_id
        self.new_form.set_harness(harness_id)
        self.labels_form.set_harness(harness_id)
        self._enable_strip_all()

    def _selected(self) -> list[Wire]:
        return [find_wire(self.ctl.project, wid)[1] for wid in self._ids]

    def _groups(self, wires: list[Wire]) -> list[ShieldGroup]:
        """The groups the wires are in, by ID."""
        found: dict[str, ShieldGroup] = {}
        for w in wires:
            g = group_of(find_wire(self.ctl.project, w.id)[0], w.id)
            if g is not None:
                found[g.id] = g
        return [found[k] for k in sorted(found)]

    def _show_ends(self) -> None:
        """The ends of a single wire that you drew; the Delete button for wires that you drew."""
        wires = self._selected()
        manual = bool(wires) and all(w.manual for w in wires)
        self.delete.setVisible(manual)
        groups = self._groups(wires)
        self.ungroup_btn.setVisible(any(g.manual for g in groups))
        self.change_group_btn.setVisible(len(groups) == 1 and groups[0].manual)
        self.group_label.setText(
            ", ".join(strings.WIRE_IN_GROUP.format(g.kind.replace("_", " "), g.id) for g in groups)
        )
        one = len(wires) == 1 and wires[0].manual
        self.ends.setVisible(one)
        if one:
            w = wires[0]
            h, _w = find_wire(self.ctl.project, w.id)
            choices = pin_choices(self.ctl.project, h.id)
            self.from_end.fill(choices, w.from_connector, w.from_pin)
            self.to_end.fill(choices, w.to_connector, w.to_pin)

    def _fill(self, wires: list[Wire]) -> None:
        choices = wire_part_choices(self.ctl.project)
        self.part.clear()
        self.part.addItems(["", *choices])
        self.colour.clear()
        self.colour.addItems(["", *[name for name, _code, _hex in COLOURS]])
        if not wires:
            self.title.setText(strings.WIRE_EDIT_NONE)
            for field in (self.gauge, self.length, self.strip_a, self.strip_b, self.label):
                field.clear()
                field.setPlaceholderText("")
            self.part.setCurrentIndex(0)
            self.colour.setCurrentIndex(0)
            self.note.clear()
            self.state.setText("")
            return
        if len(wires) == 1:
            w = wires[0]
            self.title.setText(
                f"{strings.WIRE_EDIT_ONE.format(w.id)}: "
                + strings.WIRE_EDIT_FROM_TO.format(
                    f"{w.from_connector}.{w.from_pin}", f"{w.to_connector}.{w.to_pin}"
                )
            )
        else:
            self.title.setText(strings.WIRE_EDIT_MANY.format(len(wires)))
        for widget, attr in (
            (self.gauge, "gauge_awg"),
            (self.length, "length_m"),
            (self.strip_a, "strip_a_mm"),
            (self.strip_b, "strip_b_mm"),
            (self.label, "label"),
        ):
            value = _common([getattr(w, attr) for w in wires])
            widget.setText("" if value is None else _text(value))
            widget.setPlaceholderText(
                strings.WIRE_VARIOUS if value is None and len(wires) > 1 else ""
            )
        part = _common([w.part_id for w in wires])
        self.part.setCurrentIndex(max(0, self.part.findText(part)) if isinstance(part, str) else 0)
        colour = _common([w.colour for w in wires])
        self.colour.setCurrentText(colour if isinstance(colour, str) else "")
        note = _common([w.note for w in wires])
        self.note.setPlainText(note if isinstance(note, str) else "")
        kept = {w.locked for w in wires}
        self.state.setText(
            (strings.WIRE_STATE_MANUAL if len(wires) == 1 else strings.WIRE_STATE_MANUAL_MANY)
            if all(w.manual for w in wires)
            else strings.WIRE_STATE_MIXED
            if len(kept) > 1
            else strings.WIRE_STATE_KEPT
            if kept == {True}
            else strings.WIRE_STATE_GENERATED
        )

    def _enable(self) -> None:
        """Enable the form, or say why it is off."""
        p = self.ctl.project
        reason = ""
        if self.ctl.read_only:
            reason = strings.WIRE_STATE_READ_ONLY
        else:
            for wid in self._ids:
                h, _w = find_wire(p, wid)
                if h.status == "released":
                    reason = strings.WIRE_STATE_RELEASED.format(h.id, h.revision)
                    break
        on = bool(self._ids) and not reason
        for field in (
            self.gauge,
            self.part,
            self.colour,
            self.length,
            self.strip_a,
            self.strip_b,
            self.label,
            self.note,
        ):
            field.setEnabled(on)
        self.apply.setEnabled(on)
        self.reset.setEnabled(on)
        self.delete.setEnabled(on)
        self.group_btn.setEnabled(on)
        self.group_kind.setEnabled(on)
        self.ungroup_btn.setEnabled(on)
        self.change_group_btn.setEnabled(on)
        self.from_end.set_enabled(on)
        self.to_end.set_enabled(on)
        self.new_form.set_harness(self.new_form._hid)
        self._enable_strip_all()
        if reason:
            self.state.setText(reason)

    def _enable_strip_all(self) -> None:
        """The all-wires button needs a harness that can change; if not, it says why."""
        h = self.ctl.project.harnesses.get(self._hid or "")
        reason = ""
        if self.ctl.read_only:
            reason = strings.WIRE_STATE_READ_ONLY
        elif h is not None and h.status == "released":
            reason = strings.WIRE_STATE_RELEASED.format(h.id, h.revision)
        self.strip_all.setEnabled(h is not None and not reason and bool(h.wires))
        self.bulk_btn.setEnabled(h is not None and not reason and bool(h.wires))
        self.bulk_btn.setToolTip(reason or strings.WIRE_BULK_TIP)
        if not self._ids:  # no wire selected: the two fields still serve the all-wires button
            for field in (self.strip_a, self.strip_b):
                field.setEnabled(h is not None and not reason)
        self.strip_all.setToolTip(reason or strings.WIRE_STRIP_ALL_TIP)
        if reason:
            self.strip_result.setText(reason)
        self.strip_result.setVisible(bool(reason) or bool(self.strip_result.text()))

    def _touch(self, widget: QWidget) -> None:
        if not self._filling:
            self._touched.add(self._names[widget])

    # ---- the buttons -----------------------------------------------------------------------
    def _strip_values(self) -> dict[str, str]:
        """The strip lengths that were touched, as typed (a decimal comma is read by the plan)."""
        text = {"strip_a_mm": self.strip_a.text(), "strip_b_mm": self.strip_b.text()}
        return {k: v for k, v in text.items() if k in self._touched}

    def _changes(self) -> dict[str, object]:
        values: dict[str, object] = {
            "gauge_awg": self.gauge.text(),
            "part_id": self.part.currentText(),
            "colour": self.colour.currentText(),
            "length_m": self.length.text(),
            "label": self.label.text(),
            "note": self.note.toPlainText(),
        }
        values["from_connector"], values["from_pin"] = self.from_end.value()
        values["to_connector"], values["to_pin"] = self.to_end.value()
        return {k: v for k, v in values.items() if k in self._touched and k not in STRIP_FIELDS}

    def _say(self, text: str) -> None:
        self.error.setText(text)
        self.error.setVisible(bool(text))

    def apply_changes(self) -> bool:
        """Set the touched fields on the selected wires. False (and a reason on screen) when the
        edit was refused, True when it was done or there was nothing to do."""
        if not self._ids or not self.apply.isEnabled():
            return False
        changes, strip = self._changes(), self._strip_values()
        if not changes and not strip:
            self._say(strings.WIRE_NOTHING_CHANGED)
            return True
        try:
            ops = self._plan(changes, strip)
        except EditError as exc:
            self._say(str(exc))
            return False
        ids = list(self._ids)
        if not self.ctl.run(strings.STEP_EDIT_WIRES, ops):
            return False
        self.show_wires(ids)
        return True

    def _plan(self, changes: dict[str, object], strip: dict[str, str]) -> list[Op]:
        """The ops for the touched fields: the edit and the strip lengths in one `Put` per
        harness, so that they are one undo step."""
        project = self.ctl.project
        ops = plan_wire_edit(project, self._ids, changes) if changes else []
        by_harness: dict[str, list[str]] = {}
        for wid in self._ids:
            by_harness.setdefault(find_wire(project, wid)[0].id, []).append(wid)
        for hid, ids in by_harness.items() if strip else ():
            for op in plan_set_strip(project, hid, ids, **strip):
                ops = _merge_strip(ops, op, ids)
        return ops

    def apply_strip_to_all(self) -> bool:
        """Give every wire of the harness the strip lengths in the two fields (a field that was
        touched counts, empty or not; an untouched empty field is left alone)."""
        if self._hid is None:
            self._say_strip(strings.WIRE_STRIP_ALL_NO_HARNESS)
            return False
        if not self.strip_all.isEnabled():
            return False
        wanted = {
            key: edit.text()
            for key, edit in (("strip_a_mm", self.strip_a), ("strip_b_mm", self.strip_b))
            if key in self._touched or edit.text().strip()
        }
        if not wanted:
            self._say_strip(strings.WIRE_STRIP_ALL_NONE)
            return False
        h = self.ctl.project.harnesses[self._hid]
        try:
            ops = plan_set_strip_all(self.ctl.project, self._hid, **wanted)
        except EditError as exc:
            self._say_strip(str(exc))
            return False
        new = next(
            (op.obj for op in ops if isinstance(op, Put) and isinstance(op.obj, Harness)), None
        )
        changed = 0 if new is None else sum(a != b for a, b in zip(h.wires, new.wires, strict=True))
        if ops and not self.ctl.run(strings.STEP_SET_STRIP_ALL.format(h.id), ops):
            return False
        self._touched.difference_update(wanted)
        ids = list(self._ids)
        keep = set(self._touched)
        self.show_wires(ids)
        self._touched.update(keep)
        self._say_strip(
            strings.WIRE_STRIP_ALL_DONE.format(changed, len(h.wires), h.id)
            if changed
            else strings.WIRE_STRIP_ALL_SAME.format(len(h.wires), h.id)
        )
        return True

    def _say_strip(self, text: str) -> None:
        self.strip_result.setText(text)
        self.strip_result.setVisible(bool(text))

    def delete_wires(self) -> bool:
        """Delete the selected wires that you drew."""
        if not self._ids or not self.delete.isEnabled():
            return False
        try:
            ops = plan_delete_wires(self.ctl.project, self._ids)
        except EditError as exc:
            self._say(str(exc))
            return False
        if not self.ctl.run(strings.STEP_DELETE_WIRES, ops):
            return False
        self.show_wires([])
        return True

    def group_wires(self) -> bool:
        """Twist or shield the selected wires together as one group."""
        if not self._ids or not self.group_btn.isEnabled():
            return False
        kind = str(self.group_kind.currentData())
        try:
            ops = plan_group_wires(self.ctl.project, self._ids, kind)
        except EditError as exc:
            self._say(str(exc))
            return False
        ids = list(self._ids)
        if not self.ctl.run(strings.STEP_GROUP_WIRES, ops):
            return False
        self._say("")
        self.show_wires(ids)
        return True

    def ungroup_wires(self) -> bool:
        """Take apart the groups, that you made, of the selected wires."""
        if not self._ids or not self.ungroup_btn.isEnabled():
            return False
        try:
            groups = self._groups(self._selected())
            ops = plan_ungroup_all(self.ctl.project, [g.id for g in groups if g.manual])
        except EditError as exc:
            self._say(str(exc))
            return False
        ids = list(self._ids)
        if not ops or not self.ctl.run(strings.STEP_UNGROUP_WIRES, ops):
            return False
        self.show_wires(ids)
        return True

    def change_group(self) -> bool:
        """Change the kind, the wires and the shield ends of the group, that you made, of the
        selected wire (a window asks; one undo step)."""
        if not self._ids or not self.change_group_btn.isEnabled():
            return False
        groups = [g for g in self._groups(self._selected()) if g.manual]
        if len(groups) != 1:
            return False
        dlg = ChangeGroupDialog(self, self.theme, self.ctl.project, groups[0].id)
        if self.run_dialog(dlg) != QDialog.DialogCode.Accepted or not dlg.ops():
            return False
        ids = list(self._ids)
        if not self.ctl.run(strings.STEP_CHANGE_GROUP.format(groups[0].id), dlg.ops()):
            return False
        self._say("")
        self.show_wires(ids)
        return True

    def bulk_edit(self) -> bool:
        """Edit all wires of the harness, the selected ones or those of one signal (a window asks;
        one undo step; the wires become locked like an edited wire)."""
        if self._hid is None:
            self._say(strings.BULK_NO_HARNESS)
            return False
        if not self.bulk_btn.isEnabled():
            return False
        dlg = BulkWireDialog(self, self.theme, self.ctl.project, self._hid, self._ids)
        if self.run_dialog(dlg) != QDialog.DialogCode.Accepted or not dlg.ops():
            return False
        ids = list(self._ids)
        if not self.ctl.run(strings.STEP_BULK_WIRES.format(dlg.wire_count(), self._hid), dlg.ops()):
            return False
        self._say("")
        self.show_wires(ids)
        return True

    def reset_wires(self) -> bool:
        if not self._ids or not self.reset.isEnabled():
            return False
        try:
            ops = plan_wire_reset(self.ctl.project, self._ids)
        except EditError as exc:
            self._say(str(exc))
            return False
        ids = list(self._ids)
        if ops and not self.ctl.run(strings.STEP_RESET_WIRES, ops):
            return False
        self.show_wires(ids)
        return True


def _merge_strip(ops: list[Op], strip_op: Op, wire_ids: list[str]) -> list[Op]:
    """Add the strip lengths of `strip_op` (a `Put` of a harness) to the ops: onto the `Put` of the
    same harness if there is one, else as a new op. A `Put` replaces a whole harness, so two of them
    for one harness would lose the first."""
    if not (isinstance(strip_op, Put) and isinstance(strip_op.obj, Harness)):
        return [*ops, strip_op]
    done: Harness = strip_op.obj
    for k, op in enumerate(ops):
        if isinstance(op, Put) and isinstance(op.obj, Harness) and op.obj.id == done.id:
            lengths = {w.id: w for w in done.wires}
            wires = [
                evolve(w, **{key: getattr(lengths[w.id], key) for key in STRIP_FIELDS})
                if w.id in wire_ids
                else w
                for w in op.obj.wires
            ]
            merged = [*ops]
            merged[k] = Put("harnesses", evolve(op.obj, wires=wires))
            return merged
    return [*ops, strip_op]


def _text(value: object) -> str:
    return f"{value:g}" if isinstance(value, float) else str(value)
