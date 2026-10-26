"""Two small windows of the Edit wire tab (workshop feedback M3, D-174): *Edit all wires…* and
*Change group…*.

    dlg = BulkWireDialog(parent, theme, project, "W001", selected=["W001-0001", "W001-0002"])
    if dlg.exec() and dlg.ops():
        ctl.run(strings.STEP_BULK_WIRES.format(dlg.wire_count(), "W001"), dlg.ops())

    dlg = ChangeGroupDialog(parent, theme, project, "W001-S3")

Both only plan: they read the project and offer `ops()` (planned by `core/wires.py`:
`plan_bulk_wire_edit`, `plan_regroup`), and the caller runs them as one undo step. A mistake is said
in a line under the fields, in words, and the button stays off until the plan is valid; nothing is
ever changed by the window itself.
"""

from collections.abc import Sequence

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
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from harness_design_studio.core.commands import Op
from harness_design_studio.core.edit import EditError
from harness_design_studio.core.model import Project
from harness_design_studio.core.wirecolours import COLOURS
from harness_design_studio.core.wires import (
    GROUP_KINDS,
    bulk_targets,
    plan_bulk_wire_edit,
    plan_regroup,
    signals_of,
    wire_part_choices,
    wires_changed,
)
from harness_design_studio.gui import strings
from harness_design_studio.gui.theme import ThemeManager


def _buttons(dialog: QDialog, ok_text: str, ok_tip: str) -> tuple[QPushButton, QHBoxLayout]:
    row = QHBoxLayout()
    row.addStretch(1)
    cancel = QPushButton(strings.CANCEL)
    cancel.setObjectName("dlg-cancel")
    cancel.setAccessibleName(strings.CANCEL)
    cancel.clicked.connect(dialog.reject)
    ok = QPushButton(ok_text)
    ok.setObjectName("dlg-ok")
    ok.setAccessibleName(ok_text)
    ok.setToolTip(ok_tip)
    ok.setProperty("primary", True)
    ok.setAutoDefault(True)
    ok.setDefault(True)
    ok.clicked.connect(dialog.accept)
    row.addWidget(cancel)
    row.addWidget(ok)
    return ok, row


def _field(widget: QWidget, name: str, text: str, tip: str) -> QWidget:
    widget.setObjectName(name)
    widget.setAccessibleName(text)
    widget.setToolTip(tip)
    return widget


def _line(name: str, muted: bool = False, error: bool = False) -> QLabel:
    label = QLabel()
    label.setObjectName(name)
    label.setWordWrap(True)
    if muted:
        label.setProperty("muted", True)
    if error:
        label.setProperty("error", True)
    return label


class BulkWireDialog(QDialog):
    """*Edit all wires…*: the same gauge, type, colour and length on all wires of a harness, the
    selected wires or the wires of one signal."""

    def __init__(
        self,
        parent: QWidget | None,
        theme: ThemeManager,
        project: Project,
        harness_id: str,
        selected: Sequence[str] = (),
    ) -> None:
        super().__init__(parent)
        self.project, self.harness_id = project, harness_id
        self._selected = [
            w for w in selected if w in {x.id for x in project.harnesses[harness_id].wires}
        ]
        self._ops: list[Op] = []
        self._count = 0
        title = strings.BULK_TITLE.format(harness_id)
        self.setObjectName("bulk-wire-dialog")
        self.setWindowTitle(title)
        self.setAccessibleName(title)
        self.setMinimumWidth(theme.px(460))
        h = project.harnesses[harness_id]
        lay = QVBoxLayout(self)
        intro = QLabel(strings.BULK_INTRO)
        intro.setWordWrap(True)
        intro.setProperty("muted", True)
        lay.addWidget(intro)
        form = QFormLayout()
        self.scope = QComboBox()
        if len(self._selected) > 1:
            self.scope.addItem(strings.BULK_SCOPE_SELECTED.format(len(self._selected)), "selected")
        self.scope.addItem(strings.BULK_SCOPE_ALL.format(len(h.wires), harness_id), "all")
        self.signals = signals_of(project, harness_id)
        if self.signals:
            self.scope.addItem(strings.BULK_SCOPE_SIGNAL, "signal")
        self.signal = QComboBox()
        self.signal.addItems(self.signals)
        self.gauge = QLineEdit()
        self.part = QComboBox()
        self.part.addItems(["", *wire_part_choices(project)])
        self.colour = QComboBox()
        self.colour.setEditable(True)
        self.colour.addItems(["", *[name for name, _code, _hex in COLOURS]])
        self.length = QLineEdit()
        self.only_empty = QCheckBox(strings.BULK_ONLY_EMPTY)
        for widget, name, text, tip in (
            (self.scope, "bulk-scope", strings.BULK_SCOPE, strings.BULK_SCOPE_TIP),
            (self.signal, "bulk-signal", strings.BULK_SIGNAL, strings.BULK_SIGNAL_TIP),
            (self.gauge, "bulk-gauge", strings.WIRE_GAUGE, strings.WIRE_GAUGE_TIP),
            (self.part, "bulk-type", strings.WIRE_TYPE, strings.WIRE_TYPE_TIP),
            (self.colour, "bulk-colour", strings.WIRE_COLOUR, strings.WIRE_COLOUR_TIP),
            (self.length, "bulk-length", strings.WIRE_LENGTH, strings.WIRE_LENGTH_TIP),
        ):
            form.addRow(text, _field(widget, name, text, tip))
        colour_edit = self.colour.lineEdit()
        if colour_edit is not None:
            colour_edit.setAccessibleName(strings.WIRE_COLOUR)
        lay.addLayout(form)
        _field(
            self.only_empty, "bulk-only-empty", strings.BULK_ONLY_EMPTY, strings.BULK_ONLY_EMPTY_TIP
        )
        lay.addWidget(self.only_empty)
        self.sentence = _line("bulk-sentence", muted=True)
        self.error = _line("bulk-error", error=True)
        lay.addWidget(self.sentence)
        lay.addWidget(self.error)
        self.ok, row = _buttons(self, strings.BULK_OK, strings.BULK_OK_TIP)
        lay.addLayout(row)

        self.scope.currentIndexChanged.connect(lambda _i: self._refresh())
        self.signal.currentIndexChanged.connect(lambda _i: self._refresh())
        self.part.currentIndexChanged.connect(lambda _i: self._refresh())
        self.colour.currentTextChanged.connect(lambda _t: self._refresh())
        self.gauge.textChanged.connect(lambda _t: self._refresh())
        self.length.textChanged.connect(lambda _t: self._refresh())
        self.only_empty.toggled.connect(lambda _on: self._refresh())
        self._refresh()

    # ---- what the window offers --------------------------------------------------------------
    def changes(self) -> dict[str, object]:
        """The fields that were filled in, as typed."""
        values: dict[str, object] = {
            "gauge_awg": self.gauge.text().strip(),
            "part_id": self.part.currentText().strip(),
            "colour": self.colour.currentText().strip(),
            "length_m": self.length.text().strip(),
        }
        return {k: v for k, v in values.items() if v}

    def target_ids(self) -> list[str]:
        """The wires the choice of *Wires* reaches."""
        scope = self.scope.currentData()
        if scope == "selected":
            return bulk_targets(self.project, self.harness_id, wire_ids=self._selected)
        if scope == "signal":
            return bulk_targets(self.project, self.harness_id, signal=self.signal.currentText())
        return bulk_targets(self.project, self.harness_id)

    def ops(self) -> list[Op]:
        return list(self._ops)

    def wire_count(self) -> int:
        """How many wires the plan changes."""
        return self._count

    # ---- the plan ----------------------------------------------------------------------------
    def _refresh(self) -> None:
        self.signal.setEnabled(self.scope.currentData() == "signal")
        self._ops, self._count = [], 0
        changes = self.changes()
        message, error = "", ""
        if not changes:
            error = strings.BULK_NOTHING
        else:
            try:
                ids = self.target_ids()
                self._ops = plan_bulk_wire_edit(
                    self.project,
                    self.harness_id,
                    changes,
                    wire_ids=ids,
                    only_empty=self.only_empty.isChecked(),
                )
                self._count = wires_changed(self.project, self._ops)
                if self._ops:
                    message = strings.BULK_READY.format(
                        ", ".join(_WORDS[k] for k in changes), self._count, len(ids)
                    )
                else:
                    error = strings.BULK_SAME
            except EditError as exc:
                error = str(exc)
        self.sentence.setText(message)
        self.sentence.setVisible(bool(message))
        self.error.setText(error)
        self.error.setVisible(bool(error))
        self.ok.setEnabled(bool(self._ops))


_WORDS = {
    "gauge_awg": "gauge",
    "part_id": "type",
    "colour": "colour",
    "length_m": "length",
}


class ChangeGroupDialog(QDialog):
    """*Change group…*: the kind, the wires and the shield ends of a group that you made."""

    def __init__(
        self, parent: QWidget | None, theme: ThemeManager, project: Project, group_id: str
    ) -> None:
        super().__init__(parent)
        self.project, self.group_id = project, group_id
        h, s = next(
            (h, s) for h in project.harnesses.values() for s in h.shields if s.id == group_id
        )
        self._ops: list[Op] = []
        title = strings.GD_TITLE.format(group_id)
        self.setObjectName("change-group-dialog")
        self.setWindowTitle(title)
        self.setAccessibleName(title)
        self.setMinimumWidth(theme.px(420))
        lay = QVBoxLayout(self)
        intro = QLabel(strings.GD_INTRO)
        intro.setWordWrap(True)
        intro.setProperty("muted", True)
        lay.addWidget(intro)
        form = QFormLayout()
        self.kind = QComboBox()
        for kind, label in strings.WIRE_GROUP_KINDS:
            if kind in GROUP_KINDS:
                self.kind.addItem(label, kind)
        self.kind.setCurrentIndex(max(0, self.kind.findData(s.kind)))
        self.end_a = QComboBox()
        self.end_b = QComboBox()
        for box, value in ((self.end_a, s.end_a), (self.end_b, s.end_b)):
            for key, label in strings.GD_ENDS:
                box.addItem(label, key)
            box.setCurrentIndex(max(0, box.findData(value)))
        self.wires = QListWidget()
        self.wires.setMaximumHeight(theme.px(150))
        taken = {wid for other in h.shields if other.id != group_id for wid in other.wire_ids}
        for w in sorted(h.wires, key=lambda x: x.id):
            if w.id in taken:
                continue
            item = QListWidgetItem(
                f"{w.id}  {w.signal or ''}  {w.from_connector}.{w.from_pin} - {w.to_connector}.{w.to_pin}"
            )
            item.setData(Qt.ItemDataRole.UserRole, w.id)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(
                Qt.CheckState.Checked if w.id in s.wire_ids else Qt.CheckState.Unchecked
            )
            self.wires.addItem(item)
        for widget, name, text, tip in (
            (self.kind, "group-kind", strings.GD_KIND, strings.GD_KIND_TIP),
            (self.end_a, "group-end-a", strings.GD_END_A, strings.GD_END_A_TIP),
            (self.end_b, "group-end-b", strings.GD_END_B, strings.GD_END_B_TIP),
        ):
            form.addRow(text, _field(widget, name, text, tip))
        lay.addLayout(form)
        lay.addWidget(QLabel(strings.GD_WIRES))
        _field(self.wires, "group-wires", strings.GD_WIRES, strings.GD_WIRES_TIP)
        lay.addWidget(self.wires)
        self.sentence = _line("group-sentence", muted=True)
        self.error = _line("group-error", error=True)
        lay.addWidget(self.sentence)
        lay.addWidget(self.error)
        self.ok, row = _buttons(self, strings.GD_OK, strings.GD_OK_TIP)
        lay.addLayout(row)
        self.kind.currentIndexChanged.connect(lambda _i: self._refresh())
        self.end_a.currentIndexChanged.connect(lambda _i: self._refresh())
        self.end_b.currentIndexChanged.connect(lambda _i: self._refresh())
        self.wires.itemChanged.connect(lambda _item: self._refresh())
        self._refresh()

    def wire_ids(self) -> list[str]:
        """The wires that are ticked."""
        return [
            str(self.wires.item(i).data(Qt.ItemDataRole.UserRole))
            for i in range(self.wires.count())
            if self.wires.item(i).checkState() == Qt.CheckState.Checked
        ]

    def ops(self) -> list[Op]:
        return list(self._ops)

    def _refresh(self) -> None:
        self._ops = []
        message, error = "", ""
        ids = self.wire_ids()
        try:
            self._ops = plan_regroup(
                self.project,
                self.group_id,
                kind=str(self.kind.currentData()),
                wire_ids=ids,
                end_a=str(self.end_a.currentData()),
                end_b=str(self.end_b.currentData()),
            )
            if self._ops:
                message = strings.GD_READY.format(
                    len(ids), self.wires.count(), self.kind.currentText()
                )
            else:
                error = strings.GD_SAME
        except EditError as exc:
            error = str(exc)
        self.sentence.setText(message)
        self.sentence.setVisible(bool(message))
        self.error.setText(error)
        self.error.setVisible(bool(error))
        self.ok.setEnabled(bool(self._ops))
