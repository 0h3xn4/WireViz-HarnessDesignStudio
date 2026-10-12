"""Dialogs. Each is a plain QDialog; the main window decides how to run them (so tests can drive them)."""

import csv
import io
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QIcon, QPixmap, QStandardItem, QStandardItemModel
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from harness_design_studio.core import checks, edit
from harness_design_studio.core.generate.engine import GenerationPlan
from harness_design_studio.core.imports import (
    FIELDS,
    ImportError_,
    ImportPlan,
    Table,
    guess_mapping,
    parse_csv,
    plan_interface_import,
    read_table,
)
from harness_design_studio.core.issues import Issue
from harness_design_studio.core.model import Project
from harness_design_studio.core.vcs.diff import KIND_NAMES, Diff
from harness_design_studio.core.wirecolours import COLOURS, name_of
from harness_design_studio.gui import strings
from harness_design_studio.gui.theme import ThemeManager


def _buttons(
    dialog: QDialog, ok_text: str, *, danger: bool = False, primary: bool = True
) -> tuple[QPushButton, QPushButton, QHBoxLayout]:
    row = QHBoxLayout()
    row.addStretch(1)
    cancel = QPushButton(strings.CANCEL)
    cancel.setObjectName("dlg-cancel")
    cancel.setAutoDefault(True)
    cancel.setDefault(True)  # the safe choice is the default
    ok = QPushButton(ok_text)
    ok.setObjectName("dlg-ok")
    ok.setAutoDefault(False)
    ok.setProperty("danger" if danger else "primary", primary or danger)
    cancel.clicked.connect(dialog.reject)
    ok.clicked.connect(dialog.accept)
    row.addWidget(cancel)
    row.addWidget(ok)
    return ok, cancel, row


class ConfirmDialog(QDialog):
    """Shows exactly what an action will affect. Cancel is the default button."""

    def __init__(
        self,
        parent: QWidget | None,
        title: str,
        body_html: str,
        ok_text: str,
        *,
        danger: bool = True,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setObjectName("confirm-dialog")
        lay = QVBoxLayout(self)
        head = QLabel(f"<h3>{title}</h3>")
        lay.addWidget(head)
        self.body = QLabel(body_html)
        self.body.setWordWrap(True)
        self.body.setTextFormat(Qt.TextFormat.RichText)
        lay.addWidget(self.body)
        self.ok, self.cancel, row = _buttons(self, ok_text, danger=danger, primary=not danger)
        lay.addLayout(row)
        self.cancel.setFocus()
        self.setMinimumWidth(420)


class WaiverDialog(QDialog):
    def __init__(self, parent: QWidget | None, finding: checks.Finding) -> None:
        super().__init__(parent)
        self.setWindowTitle(strings.WAIVE_TITLE)
        self.setObjectName("waiver-dialog")
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel(f"<h3>{strings.WAIVE_TITLE}</h3>"))
        lay.addWidget(QLabel(f"<b>{finding.title}</b>"))
        lay.addWidget(QLabel(strings.WAIVE_PROMPT))
        self.text = QPlainTextEdit()
        self.text.setObjectName("waiver-text")
        self.text.setAccessibleName(strings.WAIVE_PROMPT)
        lay.addWidget(self.text)
        self.error = QLabel("")
        self.error.setProperty("error", True)
        lay.addWidget(self.error)
        self.ok, self.cancel, row = _buttons(self, strings.WAIVE_OK)
        self.ok.clicked.disconnect()
        self.ok.clicked.connect(self._try_accept)
        lay.addLayout(row)
        self.text.setFocus()

    def _try_accept(self) -> None:
        if len(self.text.toPlainText().strip()) < 10:
            self.error.setText(strings.WAIVE_TOO_SHORT)
            return
        self.accept()

    def justification(self) -> str:
        return self.text.toPlainText().strip()


class NewInterfaceDialog(QDialog):
    """Table-first creation: pick a type and two units; unusable units are shown disabled with the reason."""

    def __init__(self, parent: QWidget | None, project: Project) -> None:
        super().__init__(parent)
        self.project = project
        self.setWindowTitle(strings.NEW_INTERFACE_TITLE)
        self.setObjectName("new-interface-dialog")
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel(f"<h3>{strings.NEW_INTERFACE_TITLE}</h3>"))
        self.type_box = QComboBox()
        self.type_box.setObjectName("ni-type")
        self.from_box = QComboBox()
        self.from_box.setObjectName("ni-from")
        self.to_box = QComboBox()
        self.to_box.setObjectName("ni-to")
        for label, box in (
            (strings.FIELD_TYPE, self.type_box),
            (strings.FROM, self.from_box),
            (strings.TO, self.to_box),
        ):
            lay.addWidget(QLabel(label))
            box.setAccessibleName(label)
            lay.addWidget(box)
        for tid, t in sorted(project.interface_types.items()):
            self.type_box.addItem(t.name, tid)
        self.note = QLabel(strings.NEW_INTERFACE_NOTE)
        self.note.setProperty("muted", True)
        self.note.setWordWrap(True)
        lay.addWidget(self.note)
        self.ok, self.cancel, row = _buttons(self, strings.ADD)
        self.cancel.setAutoDefault(False)
        self.cancel.setDefault(False)
        self.ok.setDefault(True)
        lay.addLayout(row)
        self.type_box.currentIndexChanged.connect(self._refill)
        self.from_box.currentIndexChanged.connect(self._refill_to)
        self._refill()

    def _fill(self, box: QComboBox, source: str | None) -> None:
        tid = self.type_box.currentData()
        model = QStandardItemModel(box)
        first_ok = -1
        for uid in sorted(self.project.units):
            compat = (
                edit.unit_compat(self.project, tid, uid, source)
                if tid
                else edit.Compat(False, "No type")
            )
            item = QStandardItem(uid if compat.ok else f"{uid}: {compat.short}")
            item.setData(uid, Qt.ItemDataRole.UserRole)
            if not compat.ok:
                item.setFlags(Qt.ItemFlag.NoItemFlags)
                item.setToolTip(compat.why)
            elif first_ok < 0:
                first_ok = model.rowCount()
            model.appendRow(item)
        box.setModel(model)
        box.setCurrentIndex(first_ok)

    def _refill(self) -> None:
        self.from_box.blockSignals(True)
        self._fill(self.from_box, None)
        self.from_box.blockSignals(False)
        self._refill_to()

    def _refill_to(self) -> None:
        self._fill(self.to_box, self.from_box.currentData(Qt.ItemDataRole.UserRole))
        self.ok.setEnabled(self.from_box.currentIndex() >= 0 and self.to_box.currentIndex() >= 0)

    def choice(self) -> tuple[str, str, str]:
        return (
            str(self.type_box.currentData()),
            str(self.from_box.currentData(Qt.ItemDataRole.UserRole)),
            str(self.to_box.currentData(Qt.ItemDataRole.UserRole)),
        )


def table_to_csv(table: Table) -> str:
    out = io.StringIO()
    csv.writer(out, lineterminator="\n").writerows(table)
    return out.getvalue()


class WireColoursDialog(QDialog):
    """One colour for each signal name (PWR, RTN, CANH ...): the wires of that signal are drawn
    in it. Nothing is preset: a signal with no choice stays without colour."""

    def __init__(self, parent: QWidget | None, project: Project) -> None:
        super().__init__(parent)
        self.setWindowTitle(strings.WIRE_COLOURS_TITLE)
        self.setObjectName("wire-colours-dialog")
        self.resize(460, 480)
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel(f"<h3>{strings.WIRE_COLOURS_TITLE}</h3>"))
        help_ = QLabel(strings.WIRE_COLOURS_HELP)
        help_.setProperty("muted", True)
        help_.setWordWrap(True)
        lay.addWidget(help_)
        self.signals = edit.signal_names(project)
        current = edit.wire_colour_map(project)
        self.table = QTableWidget(len(self.signals), 2)
        self.table.setObjectName("wire-colours-table")
        self.table.setAccessibleName(strings.WIRE_COLOURS_TABLE)
        self.table.setHorizontalHeaderLabels(
            [strings.WIRE_COLOURS_SIGNAL, strings.WIRE_COLOURS_COLUMN]
        )
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.boxes: dict[str, QComboBox] = {}
        for r, sig in enumerate(self.signals):
            item = QTableWidgetItem(sig)
            item.setFlags(Qt.ItemFlag.ItemIsEnabled)
            self.table.setItem(r, 0, item)
            box = QComboBox()
            box.setObjectName(f"wire-colour-{sig}")
            box.setAccessibleName(f"{strings.WIRE_COLOURS_TITLE}: {sig}")
            box.addItem(strings.WIRE_COLOUR_NONE, "")
            for name, code, hexcolour in COLOURS:
                pm = QPixmap(16, 16)
                pm.fill(QColor(hexcolour))
                box.addItem(QIcon(pm), f"{name} ({code})", name)
            known = name_of(current.get(sig))
            if current.get(sig) and not known:  # a colour typed by hand that the table lacks
                box.addItem(current[sig], current[sig])
                known = current[sig]
            box.setCurrentIndex(max(0, box.findData(known)))
            self.table.setCellWidget(r, 1, box)
            self.boxes[sig] = box
        lay.addWidget(self.table)
        if not self.signals:
            note = QLabel(strings.WIRE_COLOURS_NO_SIGNALS)
            note.setProperty("muted", True)
            lay.addWidget(note)
        self.ok, self.cancel, row = _buttons(self, strings.SAVE)
        lay.addLayout(row)

    def colours(self) -> dict[str, str]:
        """Signal name -> chosen colour name (empty: none)."""
        return {sig: str(box.currentData() or "") for sig, box in self.boxes.items()}


class ImportDialog(QDialog):
    """Import interfaces: read, map columns, preview every row, confirm. Nothing changes before OK."""

    def __init__(
        self,
        parent: QWidget | None,
        project: Project,
        theme: ThemeManager,
        pick_file: Callable[[], str | None] | None = None,
    ) -> None:
        super().__init__(parent)
        self.project, self.theme = project, theme
        self.pick_file = pick_file or self._default_pick
        self.table: Table = []
        self.plan = ImportPlan()
        self.setWindowTitle(strings.IMPORT_TITLE)
        self.setObjectName("import-dialog")
        self.resize(820, 640)
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel(f"<h3>{strings.IMPORT_TITLE}</h3>"))
        steps = QLabel(strings.IMPORT_STEPS)
        steps.setProperty("muted", True)
        steps.setWordWrap(True)
        lay.addWidget(steps)
        top = QHBoxLayout()
        self.open_btn = QPushButton(strings.OPEN_FILE)
        self.open_btn.setObjectName("import-open")
        self.open_btn.clicked.connect(self.open_file)
        self.file_label = QLabel(strings.NO_FILE)
        top.addWidget(self.open_btn)
        top.addWidget(self.file_label, 1)
        lay.addLayout(top)
        self.text = QPlainTextEdit()
        self.text.setObjectName("import-text")
        self.text.setAccessibleName(strings.CSV_CONTENT)
        self.text.setPlaceholderText(strings.CSV_PLACEHOLDER)
        self.text.setMaximumHeight(130)
        lay.addWidget(self.text)
        self.map_row = QHBoxLayout()
        self.map_boxes: dict[str, QComboBox] = {}
        for key, label in FIELDS:
            col = QVBoxLayout()
            col.addWidget(QLabel(label))
            box = QComboBox()
            box.setObjectName(f"map-{key}")
            box.setAccessibleName(label)
            col.addWidget(box)
            self.map_row.addLayout(col)
            self.map_boxes[key] = box
            box.activated.connect(self._replan)
        lay.addLayout(self.map_row)
        self.preview = QTableWidget(0, 6)
        self.preview.setObjectName("import-preview")
        self.preview.setAccessibleName(strings.IMPORT_PREVIEW)
        self.preview.setHorizontalHeaderLabels(["Row", "Interface", "Type", "From", "To", "Status"])
        self.preview.verticalHeader().hide()
        self.preview.horizontalHeader().setStretchLastSection(True)
        self.preview.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        lay.addWidget(self.preview, 1)
        self.summary = QLabel("")
        self.summary.setObjectName("import-summary")
        lay.addWidget(self.summary)
        self.ok, self.cancel, row = _buttons(self, strings.IMPORT_N.format(0, "s"))
        self.ok.setEnabled(False)
        self.ok.setObjectName("dlg-ok")
        lay.addLayout(row)
        self.text.textChanged.connect(self._reparse)

    @staticmethod
    def _default_pick() -> str | None:
        path, _ = QFileDialog.getOpenFileName(None, strings.OPEN_FILE, "", "Tables (*.csv *.xlsx)")
        return path or None

    def open_file(self) -> None:
        path = self.pick_file()
        if not path:
            return
        try:
            self.table = read_table(path)
        except ImportError_ as exc:
            self.summary.setText(f"✕ {exc}")
            return
        self.file_label.setText(Path(path).name)
        self.text.blockSignals(True)
        self.text.setPlainText(table_to_csv(self.table))
        self.text.blockSignals(False)
        self._setup_mapping()

    def _reparse(self) -> None:
        try:
            self.table = parse_csv(self.text.toPlainText())
        except ImportError_ as exc:
            self.table = []
            self.summary.setText(f"✕ {exc}")
            return
        self._setup_mapping()

    def _setup_mapping(self) -> None:
        header = self.table[0] if self.table else []
        guess = guess_mapping(header)
        for key, box in self.map_boxes.items():
            box.blockSignals(True)
            box.clear()
            box.addItem(strings.NOT_MAPPED, -1)
            for k, h in enumerate(header):
                box.addItem(h or f"(column {k + 1})", k)
            box.setCurrentIndex(guess.get(key, -1) + 1)
            box.blockSignals(False)
        self._replan()

    def mapping(self) -> dict[str, int]:
        return {
            k: int(b.currentData())
            for k, b in self.map_boxes.items()
            if b.currentData() is not None and int(b.currentData()) >= 0
        }

    def _replan(self) -> None:
        self.plan = plan_interface_import(self.project, self.table, self.mapping())
        err = self.theme.color("error")
        self.preview.setRowCount(len(self.plan.rows))
        for r, row in enumerate(self.plan.rows):
            cells = [str(row.row_number), *row.values[:4], "✓ OK" if row.ok else f"✕ {row.message}"]
            for c, text in enumerate(cells):
                item = QTableWidgetItem(text)
                if not row.ok and c == 5:
                    item.setForeground(QColor(err))
                self.preview.setItem(r, c, item)
        self.preview.resizeColumnsToContents()
        self.preview.setColumnWidth(5, max(self.preview.columnWidth(5), 300))
        n = self.plan.ok_count
        total = len(self.plan.rows)
        self.summary.setText(
            strings.IMPORT_SUMMARY.format(n, total, total - n) if total else strings.IMPORT_EMPTY
        )
        self.ok.setText(strings.IMPORT_N.format(n, "" if n == 1 else "s"))
        self.ok.setEnabled(n > 0)


class GlossaryDialog(QDialog):
    def __init__(self, parent: QWidget | None) -> None:
        super().__init__(parent)
        self.setWindowTitle(strings.GLOSSARY_TITLE)
        self.setObjectName("glossary-dialog")
        self.resize(560, 520)
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel(f"<h3>{strings.GLOSSARY_TITLE}</h3>"))
        area = QScrollArea()
        area.setWidgetResizable(True)
        body = QWidget()
        bl = QVBoxLayout(body)
        for term, text in strings.GLOSSARY:
            lab = QLabel(f"<b>{term}</b><br>{text}")
            lab.setWordWrap(True)
            bl.addWidget(lab)
        bl.addStretch(1)
        area.setWidget(body)
        lay.addWidget(area)
        close = QPushButton(strings.CLOSE)
        close.clicked.connect(self.accept)
        lay.addWidget(close, alignment=Qt.AlignmentFlag.AlignRight)


class IssuesDialog(QDialog):
    """Lists what is wrong with a project that opened in recovery mode."""

    saveCopyRequested = Signal()

    def __init__(self, parent: QWidget | None, issues: list[Issue], recovered: bool) -> None:
        super().__init__(parent)
        self.setWindowTitle(strings.ISSUES_TITLE)
        self.setObjectName("issues-dialog")
        self.resize(640, 420)
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel(f"<h3>{strings.ISSUES_TITLE}</h3>"))
        if recovered:
            lab = QLabel(strings.ISSUES_RECOVERED)
            lab.setWordWrap(True)
            lay.addWidget(lab)
        self.list = QListWidget()
        for i in issues:
            if i.severity == "info":
                continue
            where = f" [{i.location}]" if i.location else ""
            QListWidgetItem(
                f"{'✕' if i.severity == 'error' else '⚠'} {i.message}{where}", self.list
            )
        lay.addWidget(self.list, 1)
        row = QHBoxLayout()
        row.addStretch(1)
        if recovered:
            copy = QPushButton(strings.SAVE_SALVAGED)
            copy.setObjectName("save-salvaged")
            copy.clicked.connect(self.saveCopyRequested)
            row.addWidget(copy)
        close = QPushButton(strings.CLOSE)
        close.clicked.connect(self.accept)
        row.addWidget(close)
        lay.addLayout(row)


@dataclass
class PaletteEntry:
    label: str
    run: Callable[[], None]
    hint: str = ""


class CommandPalette(QDialog):
    """Ctrl+K: every action and every unit/interface ID in one searchable list."""

    def __init__(self, parent: QWidget | None, entries: list[PaletteEntry]) -> None:
        super().__init__(parent)
        self.entries = entries
        self.setWindowTitle(strings.COMMANDS_TITLE)
        self.setObjectName("command-palette")
        self.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
        self.resize(560, 380)
        lay = QVBoxLayout(self)
        self.input = QLineEdit()
        self.input.setObjectName("palette-input")
        self.input.setPlaceholderText(strings.COMMANDS_PLACEHOLDER)
        self.input.setAccessibleName(strings.COMMANDS_PLACEHOLDER)
        self.list = QListWidget()
        self.list.setObjectName("palette-list")
        self.list.setAccessibleName(strings.COMMANDS_LIST)
        lay.addWidget(self.input)
        lay.addWidget(self.list)
        self.input.textChanged.connect(self._filter)
        self.input.installEventFilter(self)
        self.list.itemActivated.connect(lambda _i: self._run_current())
        self.list.itemClicked.connect(lambda _i: self._run_current())
        self._filter("")
        self.input.setFocus()

    def _filter(self, text: str) -> None:
        words = text.lower().split()
        self.list.clear()
        shown = [e for e in self.entries if all(w in e.label.lower() for w in words)][:14]
        for e in shown:
            item = QListWidgetItem(f"{e.label}    {e.hint}".rstrip())
            item.setData(Qt.ItemDataRole.UserRole, e)
            self.list.addItem(item)
        if shown:
            self.list.setCurrentRow(0)

    def _run_current(self) -> None:
        item = self.list.currentItem()
        if item is None:
            return
        entry: PaletteEntry = item.data(Qt.ItemDataRole.UserRole)
        self.accept()
        entry.run()

    def eventFilter(self, obj: object, event: object) -> bool:
        from PySide6.QtCore import QEvent
        from PySide6.QtGui import QKeyEvent

        if (
            obj is self.input
            and isinstance(event, QEvent)
            and event.type() == QEvent.Type.KeyPress
            and isinstance(event, QKeyEvent)
        ):
            key = event.key()
            if key == Qt.Key.Key_Down:
                self.list.setCurrentRow(min(self.list.count() - 1, self.list.currentRow() + 1))
                return True
            if key == Qt.Key.Key_Up:
                self.list.setCurrentRow(max(0, self.list.currentRow() - 1))
                return True
            if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                self._run_current()
                return True
        return super().eventFilter(obj, event)  # type: ignore[arg-type]


class Banner(QFrame):
    """A one-line notice with an optional button (read-only, recovery, sample project)."""

    def __init__(self) -> None:
        super().__init__()
        self.setProperty("banner", True)
        self.setObjectName("banner")
        self._callback: Callable[[], None] | None = None
        lay = QHBoxLayout(self)
        self.label = QLabel("")
        self.label.setWordWrap(True)
        self.button = QPushButton("")
        self.button.clicked.connect(self._fire)
        lay.addWidget(self.label, 1)
        lay.addWidget(self.button)
        self.hide()

    def _fire(self) -> None:
        if self._callback is not None:
            self._callback()

    def show_message(
        self, text: str, button_text: str | None = None, callback: Callable[[], None] | None = None
    ) -> None:
        self.label.setText(text)
        self._callback = callback
        self.button.setVisible(button_text is not None)
        if button_text:
            self.button.setText(button_text)
        self.show()


class GeneratePreviewDialog(QDialog):
    """What generation will do, shown before anything changes. Apply is one undoable step."""

    def __init__(self, parent: QWidget | None, plan: GenerationPlan) -> None:
        super().__init__(parent)
        self.plan = plan
        self.setWindowTitle(strings.GEN_PREVIEW_TITLE)
        self.setObjectName("generate-preview")
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel(f"<h3>{strings.GEN_PREVIEW_TITLE}</h3>"))
        self.summary = QLabel(f"{plan.report.plain_summary()} {strings.GEN_PREVIEW_HEAD}")
        self.summary.setObjectName("generate-summary")
        self.summary.setWordWrap(True)
        lay.addWidget(self.summary)
        used = plan.record.placeholders_used
        self.placeholders = QLabel(strings.GEN_PLACEHOLDERS if used else "")
        self.placeholders.setWordWrap(True)
        self.placeholders.setVisible(bool(used))
        lay.addWidget(self.placeholders)
        self.findings = QListWidget()
        self.findings.setObjectName("generate-findings")
        order = {"error": 0, "warning": 1, "info": 2}
        for f in sorted(plan.report.findings, key=lambda x: (order.get(x.severity, 3), x.message)):
            self.findings.addItem(f"{f.severity.capitalize()}: {f.message}")
        self.findings.setVisible(self.findings.count() > 0)
        lay.addWidget(self.findings)
        self.ok, self.cancel, row = _buttons(self, strings.GEN_APPLY, danger=False, primary=True)
        lay.addLayout(row)
        self.setMinimumWidth(520)


class ChangeDialog(QDialog):
    """Review, release and new-revision steps: who, optional checker, mandatory comment, and
    anything that blocks the step (shown as plain sentences; OK stays disabled until clear)."""

    def __init__(
        self,
        parent: QWidget | None,
        title: str,
        *,
        by: str,
        blockers: list[str],
        ask_checker: bool = False,
        ask_comment: bool = True,
        ok_text: str = strings.OK,
        placeholders: list[str] | None = None,
        unapproved_parts: list[str] | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setObjectName("change-dialog")
        self._comment_needed = ask_comment
        self._placeholders = placeholders or []
        self._unapproved = unapproved_parts or []
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel(f"<h3>{title}</h3>"))
        self.blockers = blockers
        self.status = QLabel()
        self.status.setObjectName("change-status")
        self.status.setWordWrap(True)
        self.status.setTextFormat(Qt.TextFormat.RichText)
        if blockers:
            self.status.setText(
                strings.BLOCKED + "<ul>" + "".join(f"<li>{b}</li>" for b in blockers[:8]) + "</ul>"
            )
        else:
            self.status.setText(strings.READY_TO_RELEASE if ask_comment else "")
        lay.addWidget(self.status)
        lay.addWidget(QLabel(strings.YOUR_NAME))
        self.by = QLineEdit(by)
        self.by.setObjectName("change-by")
        lay.addWidget(self.by)
        self.by.setAccessibleName(strings.YOUR_NAME)
        self.checker = QLineEdit()
        self.checker.setObjectName("change-checker")
        self.checker.setAccessibleName(strings.CHECKED_BY)
        if ask_checker:
            lay.addWidget(QLabel(strings.CHECKED_BY))
            lay.addWidget(self.checker)
        self.comment = QPlainTextEdit()
        self.comment.setObjectName("change-comment")
        self.comment.setAccessibleName(strings.COMMENT)
        self.comment.setFixedHeight(80)
        if ask_comment:
            lay.addWidget(QLabel(strings.COMMENT))
            lay.addWidget(self.comment)
        self.placeholder_reason = QLineEdit()
        self.placeholder_reason.setObjectName("change-placeholder-reason")
        self.placeholder_reason.setAccessibleName(strings.PLACEHOLDER_REASON)
        if self._placeholders:
            warn = QLabel(strings.PLACEHOLDER_WARNING.format(", ".join(self._placeholders)))
            warn.setWordWrap(True)
            warn.setObjectName("change-placeholder-warning")
            lay.addWidget(warn)
            lay.addWidget(QLabel(strings.PLACEHOLDER_REASON))
            lay.addWidget(self.placeholder_reason)
        self.parts_reason = QLineEdit()
        self.parts_reason.setObjectName("change-parts-reason")
        self.parts_reason.setAccessibleName(strings.UNAPPROVED_PARTS_REASON)
        if self._unapproved:
            shown = ", ".join(self._unapproved[:5])
            more = f" and {len(self._unapproved) - 5} more" if len(self._unapproved) > 5 else ""
            pwarn = QLabel(strings.UNAPPROVED_PARTS_WARNING.format(shown + more))
            pwarn.setWordWrap(True)
            pwarn.setObjectName("change-parts-warning")
            lay.addWidget(pwarn)
            lay.addWidget(QLabel(strings.UNAPPROVED_PARTS_REASON))
            lay.addWidget(self.parts_reason)
        self.ok, self.cancel, row = _buttons(self, ok_text, danger=False, primary=True)
        lay.addLayout(row)
        self.by.textChanged.connect(self._validate)
        self.comment.textChanged.connect(self._validate)
        self.placeholder_reason.textChanged.connect(self._validate)
        self.parts_reason.textChanged.connect(self._validate)
        self.setMinimumWidth(480)
        self._validate()

    def _validate(self) -> None:
        good = not self.blockers and bool(self.by.text().strip())
        if self._comment_needed:
            good = good and len(self.comment.toPlainText().strip()) >= 10
        if self._placeholders:
            good = good and len(self.placeholder_reason.text().strip()) >= 10
        if self._unapproved:
            good = good and len(self.parts_reason.text().strip()) >= 10
        self.ok.setEnabled(good)

    def accepted_unapproved_parts(self) -> str | None:
        """The written reason for releasing with parts that are not approved (None if none)."""
        return self.parts_reason.text().strip() or None if self._unapproved else None

    def accepted_placeholders(self) -> str | None:
        """The written reason for releasing on placeholder values (None when there are none)."""
        return self.placeholder_reason.text().strip() or None if self._placeholders else None

    def values(self) -> tuple[str, str, str]:
        return (
            self.by.text().strip(),
            self.checker.text().strip(),
            self.comment.toPlainText().strip(),
        )


class DiffDialog(QDialog):
    """What changed: added, removed and changed objects with their field changes."""

    markRequested = Signal(object)  # dict[str, str]

    def __init__(
        self, parent: QWidget | None, title: str, diff: "Diff", baselines: list[str], current: str
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setObjectName("diff-dialog")
        self.diff = diff
        self.resize(720, 520)
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel(f"<h3>{title}</h3>"))
        self.baseline = QComboBox()
        self.baseline.setObjectName("diff-baseline")
        self.baseline.addItems(baselines)
        self.baseline.setCurrentText(current)
        row0 = QHBoxLayout()
        row0.addWidget(QLabel(strings.COMPARE_WITH))
        row0.addWidget(self.baseline)
        row0.addStretch(1)
        lay.addLayout(row0)
        self.summary = QLabel(diff.summary())
        self.summary.setObjectName("diff-summary")
        lay.addWidget(self.summary)
        self.list = QListWidget()
        self.list.setObjectName("diff-list")
        self.set_diff(diff)
        lay.addWidget(self.list, 1)
        row = QHBoxLayout()
        self.mark = QPushButton(strings.MARK_DIAGRAM)
        self.mark.setObjectName("diff-mark")
        self.mark.clicked.connect(lambda: self.markRequested.emit(self.diff.affected()))
        clear = QPushButton(strings.CLEAR_MARKS)
        clear.setObjectName("diff-clear")
        clear.clicked.connect(lambda: self.markRequested.emit({}))
        close = QPushButton(strings.CLOSE)
        close.clicked.connect(self.accept)
        row.addWidget(self.mark)
        row.addWidget(clear)
        row.addStretch(1)
        row.addWidget(close)
        lay.addLayout(row)

    def set_diff(self, diff: "Diff") -> None:
        self.diff = diff
        self.summary.setText(diff.summary() if not diff.empty else strings.NO_DIFF)
        self.list.clear()
        sym = {"added": "+", "removed": "−", "changed": "~"}
        for c in diff.changes:
            QListWidgetItem(f"{sym[c.change]} {KIND_NAMES.get(c.kind, c.kind)} {c.id}", self.list)
            for f in c.fields:
                QListWidgetItem(f"      {f.name}: {f.before} → {f.after}", self.list)


class HistoryDialog(QDialog):
    """The change log of one harness (or all)."""

    def __init__(self, parent: QWidget | None, title: str, rows: list[list[str]]) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setObjectName("history-dialog")
        self.resize(720, 400)
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel(f"<h3>{title}</h3>"))
        self.list = QListWidget()
        self.list.setObjectName("history-list")
        for r in rows[1:]:
            tail = f": {r[6]}" if r[6] else ""
            QListWidgetItem(f"{r[5]}  {r[1]} rev {r[2]}  {r[3]} by {r[4]}{tail}", self.list)
        if len(rows) == 1:
            QListWidgetItem(strings.NO_HISTORY, self.list)
        lay.addWidget(self.list, 1)
        close = QPushButton(strings.CLOSE)
        close.clicked.connect(self.accept)
        lay.addWidget(close)
