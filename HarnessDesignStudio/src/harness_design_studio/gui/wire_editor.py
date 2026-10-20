"""The Edit wire form of the Harness tab: gauge, type, colour, length, label and note of the
selected wires, and a button that gives them back to generation.

    editor = WireEditor(ctl, theme)
    editor.show_wires(["W001-0001", "W001-0002"])        # the selection of the wire table

A field that shows its common value (or "various" when the wires differ) changes nothing until the
person types in it; Apply then sets only the fields that were touched, on every selected wire, as
one undo step. Gauge, type, colour and length lock the wire, so Generate keeps them; label and note
are always kept. Mistakes are said in words under the form, never in a message box. Everything is
disabled for a released harness and for a read-only project, with the reason shown.
"""

from collections.abc import Sequence

from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from harness_design_studio.core.edit import EditError
from harness_design_studio.core.model import Wire
from harness_design_studio.core.wirecolours import COLOURS
from harness_design_studio.core.wires import (
    find_wire,
    plan_wire_edit,
    plan_wire_reset,
    wire_part_choices,
)
from harness_design_studio.gui import strings
from harness_design_studio.gui.controller import EditorController
from harness_design_studio.gui.icons import icon_button
from harness_design_studio.gui.theme import ThemeManager

FIELDS = ("gauge_awg", "part_id", "colour", "length_m", "label", "note")


def _common(values: Sequence[object]) -> object | None:
    """The value all wires share, or None when they differ."""
    first = values[0]
    return first if all(v == first for v in values) else None


class WireEditor(QWidget):
    def __init__(self, ctl: EditorController, theme: ThemeManager) -> None:
        super().__init__()
        self.ctl = ctl
        self.setObjectName("wire-editor")
        self._ids: list[str] = []
        self._touched: set[str] = set()
        self._filling = False

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
        self.label = QLineEdit()
        self.note = QPlainTextEdit()
        self.note.setFixedHeight(theme.px(56))
        for widget, name, text, tip in (
            (self.gauge, "wire-gauge", strings.WIRE_GAUGE, strings.WIRE_GAUGE_TIP),
            (self.part, "wire-type", strings.WIRE_TYPE, strings.WIRE_TYPE_TIP),
            (self.colour, "wire-colour", strings.WIRE_COLOUR, strings.WIRE_COLOUR_TIP),
            (self.length, "wire-length", strings.WIRE_LENGTH, strings.WIRE_LENGTH_TIP),
            (self.label, "wire-label", strings.WIRE_LABEL, strings.WIRE_LABEL_TIP),
            (self.note, "wire-note", strings.WIRE_NOTE, strings.WIRE_NOTE_TIP),
        ):
            widget.setObjectName(name)
            widget.setAccessibleName(text)
            widget.setToolTip(tip)
            form.addRow(text, widget)
        root.addLayout(form)

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
        root.addStretch(1)

        self.apply.clicked.connect(self.apply_changes)
        self.reset.clicked.connect(self.reset_wires)
        for w in (self.gauge, self.length, self.label):
            w.textEdited.connect(lambda _t, w=w: self._touch(w))
        self.part.activated.connect(lambda _i: self._touch(self.part))
        self.colour.activated.connect(lambda _i: self._touch(self.colour))
        colour_edit = self.colour.lineEdit()
        if colour_edit is not None:
            colour_edit.textEdited.connect(lambda _t: self._touch(self.colour))
        self.note.textChanged.connect(lambda: self._touch(self.note))
        for w in (self.gauge, self.length, self.label):
            w.returnPressed.connect(self.apply_changes)
        QShortcut(QKeySequence("Ctrl+Return"), self, self.apply_changes)
        self._names = {
            self.gauge: "gauge_awg",
            self.part: "part_id",
            self.colour: "colour",
            self.length: "length_m",
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
        self._enable()

    def _fill(self, wires: list[Wire]) -> None:
        choices = wire_part_choices(self.ctl.project)
        self.part.clear()
        self.part.addItems(["", *choices])
        self.colour.clear()
        self.colour.addItems(["", *[name for name, _code, _hex in COLOURS]])
        if not wires:
            self.title.setText(strings.WIRE_EDIT_NONE)
            for field in (self.gauge, self.length, self.label):
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
            strings.WIRE_STATE_MIXED
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
        for field in (self.gauge, self.part, self.colour, self.length, self.label, self.note):
            field.setEnabled(on)
        self.apply.setEnabled(on)
        self.reset.setEnabled(on)
        if reason:
            self.state.setText(reason)

    def _touch(self, widget: QWidget) -> None:
        if not self._filling:
            self._touched.add(self._names[widget])

    # ---- the buttons -----------------------------------------------------------------------
    def _changes(self) -> dict[str, object]:
        values: dict[str, object] = {
            "gauge_awg": self.gauge.text(),
            "part_id": self.part.currentText(),
            "colour": self.colour.currentText(),
            "length_m": self.length.text(),
            "label": self.label.text(),
            "note": self.note.toPlainText(),
        }
        return {k: v for k, v in values.items() if k in self._touched}

    def _say(self, text: str) -> None:
        self.error.setText(text)
        self.error.setVisible(bool(text))

    def apply_changes(self) -> bool:
        """Set the touched fields on the selected wires. False (and a reason on screen) when the
        edit was refused, True when it was done or there was nothing to do."""
        if not self._ids or not self.apply.isEnabled():
            return False
        changes = self._changes()
        if not changes:
            self._say(strings.WIRE_NOTHING_CHANGED)
            return True
        try:
            ops = plan_wire_edit(self.ctl.project, self._ids, changes)
        except EditError as exc:
            self._say(str(exc))
            return False
        ids = list(self._ids)
        if not self.ctl.run(strings.STEP_EDIT_WIRES, ops):
            return False
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


def _text(value: object) -> str:
    return f"{value:g}" if isinstance(value, float) else str(value)
