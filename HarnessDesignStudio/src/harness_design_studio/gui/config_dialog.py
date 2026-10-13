"""Engineering values as a form: supply the value a rule is waiting for.

    dialog = ConfigValueDialog(ctl, theme, file="derating", key="spare_pin_fraction")
    dialog.show()                                   # a window of its own, not modal

Lists `configcheck.engineering_values(project, include_optional=True)` grouped by config file, one
editor per value by kind (number with its unit, choice, pairs, table, yes/no). A value that is
still missing is marked with the pending chip; a value a release froze is disabled and says why.
Each file has a "placeholder" toggle (the values are not reviewed). Typing is checked at once with
`configcheck.plan_set_value`, so the reason appears under the field and never in a message box.
Apply runs every change through `ctl.run` as one step with a label (one Undo), and the controller
then re-runs the design rule check like after any other edit.
"""

from dataclasses import dataclass

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from harness_design_studio.core import configcheck, edit
from harness_design_studio.core.commands import Op
from harness_design_studio.core.configcheck import EngineeringValue
from harness_design_studio.core.errors import TransactionError
from harness_design_studio.core.vcs.locks import check_locks
from harness_design_studio.gui import strings
from harness_design_studio.gui.controller import EditorController
from harness_design_studio.gui.panels import muted
from harness_design_studio.gui.states import StateChip
from harness_design_studio.gui.theme import ThemeManager


def _repolish(widget: QWidget) -> None:
    widget.style().unpolish(widget)
    widget.style().polish(widget)


class FieldRow(QWidget):
    """One engineering value: editor, unit, state chip, caption and the error line."""

    edited = Signal()

    def __init__(self, ev: EngineeringValue, theme: ThemeManager, read_only: bool) -> None:
        super().__init__()
        self.ev, self.theme = ev, theme
        self.setObjectName(f"value-{ev.file}-{ev.key}")
        self.editor: QLineEdit | QComboBox
        name = (
            strings.CONFIG_FIELD_NAME.format(label=ev.label, unit=ev.unit) if ev.unit else ev.label
        )
        if ev.kind in ("choice", "flag"):
            box = QComboBox()
            box.addItem(strings.CONFIG_NOT_SET, "")
            options = (
                [(strings.CONFIG_YES, "yes"), (strings.CONFIG_NO, "no")]
                if ev.kind == "flag"
                else [(c, c) for c in ev.choices]
            )
            for text, data in options:
                box.addItem(text, data)
            self.initial = ev.display if ev.value is not None else ""
            box.setCurrentIndex(max(0, box.findData(self.initial)))
            box.currentIndexChanged.connect(lambda _i: self.edited.emit())
            self.editor = box
        else:
            edit_ = QLineEdit(ev.display)
            edit_.setPlaceholderText(strings.CONFIG_NOT_SET)
            edit_.textChanged.connect(lambda _t: self.edited.emit())
            if ev.kind in ("table", "pairs"):
                edit_.setToolTip(ev.hint)
            self.initial = ev.display
            self.editor = edit_
        self.editor.setObjectName(f"edit-{ev.file}-{ev.key}")
        self.editor.setAccessibleName(name)
        self.editor.setAccessibleDescription(f"{ev.what}. {ev.used_by}")
        tip = strings.CONFIG_NEEDED_FOR.format(what=ev.what, used_by=ev.used_by)
        self.editor.setToolTip(f"{tip}\n{ev.hint}" if ev.hint else tip)
        locked = ev.locked is not None
        self.editor.setEnabled(not locked and not read_only)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, theme.space(8))
        lay.setSpacing(theme.space(4))
        row = QHBoxLayout()
        row.setSpacing(theme.space(8))
        row.addWidget(self.editor, 1)
        if ev.unit:
            unit = QLabel(ev.unit)
            unit.setObjectName(f"unit-{ev.file}-{ev.key}")
            unit.setProperty("muted", True)
            unit.setAccessibleName("")
            row.addWidget(unit)
        self.chip = StateChip(theme, "pending")
        row.addWidget(self.chip)
        lay.addLayout(row)
        self.caption = muted("")
        self.caption.setObjectName(f"caption-{ev.file}-{ev.key}")
        lay.addWidget(self.caption)
        self.error = QLabel("")
        self.error.setObjectName(f"error-{ev.file}-{ev.key}")
        self.error.setProperty("error", True)
        self.error.setWordWrap(True)
        self.error.hide()
        lay.addWidget(self.error)
        self.set_baseline(ev)

    def set_baseline(self, ev: EngineeringValue) -> None:
        """Show the chip and caption for the value as it is stored now."""
        self.ev = ev
        if ev.locked is not None:
            self.chip.setVisible(True)
            self.chip.set_state("locked")
            self.caption.setText(strings.CONFIG_LOCKED.format(ev.locked))
        elif ev.missing:
            self.chip.setVisible(True)
            self.chip.set_state("pending")
            self.caption.setText(strings.CONFIG_NEEDED_FOR.format(what=ev.what, used_by=ev.used_by))
        else:
            self.chip.setVisible(False)
            source = strings.CONFIG_SOURCE.format(ev.source) if ev.source else ""
            if source and ev.placeholder:
                source = f"{source} {strings.CONFIG_PLACEHOLDER_SUFFIX}"
            self.caption.setText(source)
        self.caption.setVisible(bool(self.caption.text()))

    # ---- value -----------------------------------------------------------------------------------
    def raw(self) -> str:
        """What the person typed or chose ("" for not set)."""
        if isinstance(self.editor, QComboBox):
            return str(self.editor.currentData() or "")
        return self.editor.text().strip()

    def changed(self) -> bool:
        return self.editor.isEnabled() and self.raw() != self.initial.strip()

    def show_error(self, message: str) -> None:
        self.error.setText(message)
        self.error.setVisible(bool(message))
        self.editor.setProperty("invalid", bool(message))
        _repolish(self.editor)

    def has_error(self) -> bool:
        return bool(self.error.text())


@dataclass
class _Group:
    file: str
    box: QGroupBox
    form: QFormLayout
    toggle: QCheckBox
    rows: list[FieldRow]
    initial_placeholder: bool
    exists: bool


class ConfigValueDialog(QDialog):
    """The engineering values of the project as a form. See the module text."""

    applied = Signal(int)  # how many changes were applied

    def __init__(
        self,
        ctl: EditorController,
        theme: ThemeManager,
        file: str | None = None,
        key: str | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.ctl, self.theme = ctl, theme
        self.setObjectName("config-dialog")
        self.setWindowTitle(strings.CONFIG_TITLE)
        self.setModal(False)
        self.resize(theme.px(640), theme.px(640))
        self.groups: dict[str, _Group] = {}
        self.fields: dict[tuple[str, str], FieldRow] = {}
        self._tab: list[QWidget] = []
        lay = QVBoxLayout(self)
        lay.setSpacing(theme.space(8))
        intro = muted(strings.CONFIG_INTRO)
        intro.setObjectName("config-intro")
        lay.addWidget(intro)
        self.only_missing = QCheckBox(strings.CONFIG_ONLY_MISSING)
        self.only_missing.setObjectName("config-only-missing")
        self.only_missing.setAccessibleName(strings.CONFIG_ONLY_MISSING)
        lay.addWidget(self.only_missing)
        self.area = QScrollArea()
        self.area.setObjectName("config-scroll")
        self.area.setWidgetResizable(True)
        self.area.setFrameShape(QFrame.Shape.NoFrame)
        self.area.setAccessibleName(strings.CONFIG_TITLE)
        body = QWidget()
        self.body = QVBoxLayout(body)
        self.body.setContentsMargins(0, 0, theme.space(8), 0)
        self.area.setWidget(body)
        lay.addWidget(self.area, 1)
        self.message = muted("")
        self.message.setObjectName("config-message")
        lay.addWidget(self.message)
        buttons = QDialogButtonBox()
        self.apply_btn = QPushButton(strings.CONFIG_APPLY)
        self.cancel_btn = QPushButton(strings.CONFIG_CANCEL)
        buttons.addButton(self.apply_btn, QDialogButtonBox.ButtonRole.AcceptRole)
        buttons.addButton(self.cancel_btn, QDialogButtonBox.ButtonRole.RejectRole)
        self.apply_btn.setObjectName("config-apply")
        self.apply_btn.setProperty("primary", True)
        self.apply_btn.setAccessibleName(strings.CONFIG_APPLY)
        self.apply_btn.setToolTip(strings.CONFIG_APPLY_TIP)
        self.apply_btn.setDefault(True)
        self.cancel_btn.setObjectName("config-cancel")
        self.cancel_btn.setAccessibleName(strings.CONFIG_CANCEL)
        buttons.rejected.connect(self.reject)
        self.apply_btn.clicked.connect(self.apply)
        lay.addWidget(buttons)
        self.apply_key = QShortcut(QKeySequence("Ctrl+Return"), self)
        self.apply_key.activated.connect(self.apply)
        self._build()
        missing = any(f.ev.missing for f in self.fields.values())
        self.only_missing.setChecked(key is None and missing)
        self.only_missing.toggled.connect(self._filter)
        self._filter()
        self._status()
        if key is not None:
            self.focus_value(file, key)

    # ---- building ---------------------------------------------------------------------------------
    def _build(self) -> None:
        project = self.ctl.project
        read_only = self.ctl.read_only
        by_file: dict[str, list[EngineeringValue]] = {}
        for ev in configcheck.engineering_values(project, include_optional=True):
            by_file.setdefault(ev.file, []).append(ev)
        for file, values in by_file.items():
            cfg = project.config.get(file)
            box = QGroupBox(strings.CONFIG_FILE_GROUP.format(file))
            box.setObjectName(f"group-{file}")
            box.setAccessibleName(strings.CONFIG_FILE_GROUP.format(file))
            form = QFormLayout(box)
            form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
            form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
            placeholder = cfg.placeholder if cfg is not None else True
            toggle = QCheckBox(strings.CONFIG_PLACEHOLDER_TOGGLE)
            toggle.setObjectName(f"placeholder-{file}")
            toggle.setAccessibleName(
                f"{strings.CONFIG_FILE_GROUP.format(file)}: {strings.CONFIG_PLACEHOLDER_TOGGLE}"
            )
            toggle.setToolTip(strings.CONFIG_PLACEHOLDER_TIP)
            toggle.setChecked(placeholder)
            toggle.setEnabled(cfg is not None and not read_only)
            toggle.toggled.connect(lambda _c: self._status())
            form.addRow(toggle)
            rows: list[FieldRow] = []
            for ev in values:
                row = FieldRow(ev, self.theme, read_only)
                label = QLabel(ev.label)
                label.setBuddy(row.editor)
                label.setWordWrap(True)
                form.addRow(label, row)
                row.edited.connect(lambda r=row: self._edited(r))
                rows.append(row)
                self.fields[(ev.file, ev.key)] = row
                self._tab.append(row.editor)
            self._tab.append(toggle)
            self.groups[file] = _Group(file, box, form, toggle, rows, placeholder, cfg is not None)
            self.body.addWidget(box)
        self.body.addStretch(1)
        self._tab.insert(0, self.only_missing)
        self._tab += [self.apply_btn, self.cancel_btn]
        for a, b in zip(self._tab, self._tab[1:], strict=False):
            QWidget.setTabOrder(a, b)

    def _filter(self) -> None:
        only = self.only_missing.isChecked()
        for g in self.groups.values():
            shown = 0
            for i, row in enumerate(g.rows):
                visible = not only or row.ev.missing or row.changed()
                g.form.setRowVisible(i + 1, visible)  # row 0 is the placeholder toggle
                shown += visible
            g.box.setVisible(shown > 0)

    def focus_value(self, file: str | None, key: str | None) -> bool:
        """Scroll to a value and put the cursor in it; False when there is no such value."""
        row = self.fields.get((file or "", key or ""))
        if row is None:
            return False
        if self.only_missing.isChecked() and not row.ev.missing:
            self.only_missing.setChecked(False)
        self.area.ensureWidgetVisible(row)
        row.editor.setFocus(Qt.FocusReason.OtherFocusReason)
        return True

    # ---- editing ------------------------------------------------------------------------------------
    def _edited(self, row: FieldRow) -> None:
        if not row.changed():
            row.show_error("")
        else:
            plan = configcheck.plan_set_value(self.ctl.project, row.ev.file, row.ev.key, row.raw())
            row.show_error(plan.error or "")
        self._status()

    def changes(self) -> list[str]:
        """Names of what Apply would change (values by their label, files by their review flag)."""
        names = [r.ev.label for r in self.fields.values() if r.changed()]
        for g in self.groups.values():
            if g.exists and g.toggle.isEnabled() and g.toggle.isChecked() != g.initial_placeholder:
                names.append(strings.CONFIG_FILE_GROUP.format(g.file))
        return names

    def _status(self) -> None:
        names = self.changes()
        has_error = any(r.has_error() for r in self.fields.values())
        if self.ctl.read_only:
            text = strings.CONFIG_READ_ONLY
        elif has_error:
            text = strings.CONFIG_FIX_FIRST
        elif names:
            text = strings.CONFIG_CHANGES.format(len(names))
        else:
            text = strings.CONFIG_NO_CHANGES
        self.message.setText(text)
        self.message.setProperty("error", has_error)
        _repolish(self.message)
        self.apply_btn.setEnabled(bool(names) and not has_error and not self.ctl.read_only)

    # ---- applying ------------------------------------------------------------------------------------
    def plan(self) -> tuple[list[Op], list[str], dict[tuple[str, str], str]]:
        """The ops for every change (one config op per file), the names of the changes, and the
        reason for each value that cannot be set. Each value is planned on top of the earlier ones,
        so two values of one file end up in one op."""
        work = self.ctl.project
        per_file: dict[str, Op] = {}
        names: list[str] = []
        errors: dict[tuple[str, str], str] = {}
        for (file, key), row in self.fields.items():
            if not row.changed():
                continue
            plan = configcheck.plan_set_value(work, file, key, row.raw())
            if not plan.ok:
                errors[(file, key)] = plan.error or ""
                continue
            per_file[file] = plan.ops[0]
            work = edit.clone_with(work, plan.ops)
            names.append(row.ev.label)
        for g in self.groups.values():
            if g.exists and g.toggle.isEnabled() and g.toggle.isChecked() != g.initial_placeholder:
                flag = configcheck.plan_placeholder(work, g.file, g.toggle.isChecked())
                if not flag.ok:
                    errors[(g.file, "")] = flag.error or ""
                    continue
                per_file[g.file] = flag.ops[0]
                work = edit.clone_with(work, flag.ops)
                names.append(strings.CONFIG_FILE_GROUP.format(g.file))
        return list(per_file.values()), names, errors

    def apply(self) -> bool:
        """Set every changed value as one undo step. False (and the reason shown in the dialog)
        when something cannot be set; nothing is applied then."""
        if self.ctl.read_only:
            self.message.setText(strings.CONFIG_READ_ONLY)
            return False
        ops, names, errors = self.plan()
        for (file, key), why in errors.items():
            if (file, key) in self.fields:
                self.fields[(file, key)].show_error(why)
        problem = next((w for (f, k), w in errors.items() if (f, k) not in self.fields), "")
        if not problem and not errors:
            try:
                check_locks(self.ctl.project, ops)
            except TransactionError as exc:
                problem = exc.problems[0] if exc.problems else str(exc)
        if errors or problem:
            self.message.setText(problem or strings.CONFIG_FIX_FIRST)
            self.message.setProperty("error", True)
            _repolish(self.message)
            return False
        if not ops:
            return False
        label = (
            strings.CONFIG_LABEL_ONE.format(names[0])
            if len(names) == 1
            else strings.CONFIG_LABEL_MANY.format(len(names))
        )
        done = (
            strings.CONFIG_DONE_ONE.format(names[0])
            if len(names) == 1
            else strings.CONFIG_DONE_MANY.format(len(names))
        )
        if not self.ctl.run(label, ops, message=done):
            self.message.setText(strings.CONFIG_REFUSED)
            return False
        self.applied.emit(len(names))
        self.accept()
        return True
