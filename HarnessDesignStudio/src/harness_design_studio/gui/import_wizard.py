"""The import wizard: one pattern for every kind of import.

    wizard = ImportWizard(ctl, theme, parent)
    wizard.exec()                       # applies itself on Finish: one undo step, "Import 12 rows"
    wizard.imported.connect(...)        # rows imported (after the undo step exists)

Four pages: 1 what and which file, 2 matching the columns (or the unit, the meaning of the approval
words ...) with a live preview of the first rows, 3 the conflicts and placeholders with the exact
reason for every row, 4 apply. Nothing in the project changes before Finish.

Kinds: interfaces (CSV/XLSX), approved parts, segment lengths, engineering values (the ampacity
table, as `harness-design-studio config --ampacity-csv` reads it), a device pinout (one pin per row,
as `import-pinout` reads it) and a KiCad netlist. Each is planned by the
planner the command line uses (see `import_kinds`); the existing `ImportDialog` keeps working and
also lets you paste CSV text.
"""

import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt, QThread, QTimer, Signal
from PySide6.QtWidgets import (
    QAbstractButton,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
    QWizard,
    QWizardPage,
)

from harness_design_studio.core.errors import HarnessError
from harness_design_studio.core.model.library import PART_CATEGORIES
from harness_design_studio.gui import icons, import_kinds, strings
from harness_design_studio.gui.controller import EditorController
from harness_design_studio.gui.import_kinds import (
    KIND_BY_KEY,
    KINDS,
    ImportPlanView,
    Options,
    Source,
)
from harness_design_studio.gui.notice import InlineNotice
from harness_design_studio.gui.tables import Column, DictTableModel, TableView
from harness_design_studio.gui.theme import ThemeManager, mark_mono

PAGE_FILE, PAGE_MAP, PAGE_CHECK, PAGE_APPLY = range(4)
LARGE_ROWS = 1500  # a file with more rows is read in a helper thread (the window stays usable)
REPLAN_MS = 200  # typing in an option waits this long before the rows are read again
PickFile = Callable[[str, str], "str | None"]  # (kind key, file filter) -> path


def _pick_file(kind: str, filters: str) -> str | None:
    path, _ = QFileDialog.getOpenFileName(None, strings.IMP_FILE_BROWSE, "", filters)
    return path or None


_STATE_WORD = {"pass": strings.STATE_LABELS["pass"], "fail": strings.STATE_LABELS["fail"], "warning": strings.STATE_LABELS["warning"]}  # fmt: skip


def _row_dicts(plan: ImportPlanView) -> list[dict[str, Any]]:
    return [
        {"row": r.number, "item": r.item, "state": r.state, "result": r.result, "reason": r.reason}
        for r in plan.rows
    ]


def _table(model: DictTableModel, theme: ThemeManager, name: str, key: str, object_name: str, parent: QWidget) -> TableView:  # fmt: skip
    view = TableView(model, theme, name=name, key=key, parent=parent)
    view.setObjectName(object_name)
    return view


class FilePage(QWizardPage):
    """What to import and from which file."""

    def __init__(self, wizard: "ImportWizard") -> None:
        super().__init__(wizard)
        self.wiz = wizard
        self.setTitle(strings.IMP_STEP_FILE)
        lay = QVBoxLayout(self)
        prompt = QLabel(strings.IMP_KIND_PROMPT)
        prompt.setProperty("heading", True)
        lay.addWidget(prompt)
        self.group = QButtonGroup(self)
        self.radios: dict[str, QRadioButton] = {}
        for info in KINDS:
            radio = QRadioButton(info.title)
            radio.setObjectName(f"import-kind-{info.key}")
            radio.setAccessibleName(info.title)
            radio.setToolTip(info.summary)
            radio.setAccessibleDescription(info.summary)
            note = QLabel(info.summary)
            note.setProperty("muted", True)
            note.setWordWrap(True)
            note.setContentsMargins(wizard.theme.space(24), 0, 0, wizard.theme.space(8))
            self.group.addButton(radio)
            self.radios[info.key] = radio
            lay.addWidget(radio)
            lay.addWidget(note)
            radio.toggled.connect(lambda on, k=info.key: wizard.set_kind(k) if on else None)
        row = QHBoxLayout()
        label = QLabel(strings.IMP_FILE_LABEL)
        self.path = QLineEdit()
        self.path.setObjectName("import-file")
        self.path.setAccessibleName(strings.IMP_FILE_NAME)
        self.path.setPlaceholderText(strings.IMP_FILE_NONE)
        mark_mono(self.path)
        label.setBuddy(self.path)
        self.browse = QPushButton()
        self.browse.setObjectName("import-browse")
        icons.icon_button(self.browse, "folder-open", wizard.theme, strings.IMP_FILE_BROWSE_TIP, text=strings.IMP_FILE_BROWSE)  # fmt: skip
        self.browse.setToolTip(strings.IMP_FILE_BROWSE_TIP)
        row.addWidget(label)
        row.addWidget(self.path, 1)
        row.addWidget(self.browse)
        lay.addLayout(row)
        self.status = QLabel()
        self.status.setObjectName("import-file-status")
        self.status.setWordWrap(True)
        lay.addWidget(self.status)
        self.notice = InlineNotice(wizard.theme)
        self.notice.setObjectName("import-file-notice")
        lay.addWidget(self.notice)
        self.paste = QPushButton(strings.IMP_PASTE_TEXT)
        self.paste.setObjectName("import-paste")
        self.paste.setFlat(True)
        self.paste.setToolTip(strings.IMP_PASTE_TEXT_TIP)
        self.paste.clicked.connect(wizard.pasteRequested)
        lay.addWidget(self.paste, 0, Qt.AlignmentFlag.AlignLeft)
        lay.addStretch(1)
        self.browse.clicked.connect(wizard.browse)
        self.path.editingFinished.connect(lambda: wizard.load_file(self.path.text().strip()))

    def isComplete(self) -> bool:  # noqa: N802
        return self.wiz.source is not None and not self.wiz.ctl.read_only


class GridForm:
    """Label and field pairs laid out in `columns` columns, so a long list of choices (eleven
    columns to match) leaves room for the preview below it. `addRow(label, field)` takes the next
    cell; `addRow(widget)` takes a whole row."""

    def __init__(self, host: QWidget, columns: int = 3) -> None:
        self.grid = QGridLayout(host)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.columns = columns
        self._n = 0
        for c in range(columns):
            self.grid.setColumnStretch(c * 2 + 1, 1)

    def addRow(self, first: "str | QWidget", field: QWidget | None = None) -> None:  # noqa: N802
        if field is None:
            widget = first if isinstance(first, QWidget) else QLabel(first)
            self._n += (-self._n) % self.columns  # finish the row
            self.grid.addWidget(widget, self._n // self.columns, 0, 1, self.columns * 2)
            self._n += self.columns
            return
        row, col = divmod(self._n, self.columns)
        label = QLabel(first) if isinstance(first, str) else None
        if label is not None:
            label.setWordWrap(True)
            label.setBuddy(field)
            self.grid.addWidget(label, row, col * 2)
        elif isinstance(first, QWidget):
            self.grid.addWidget(first, row, col * 2)
        self.grid.addWidget(field, row, col * 2 + 1)
        self._n += 1


class MapPage(QWizardPage):
    """Match columns, choose units and words, and see the first rows as they will be read."""

    def __init__(self, wizard: "ImportWizard") -> None:
        super().__init__(wizard)
        self.wiz = wizard
        self.setTitle(strings.IMP_STEP_MAP)
        lay = QVBoxLayout(self)
        intro = QLabel(strings.IMP_MAP_INTRO)
        intro.setProperty("muted", True)
        intro.setWordWrap(True)
        lay.addWidget(intro)
        self.stack = QStackedWidget()
        self.stack.setObjectName("import-options")
        lay.addWidget(self.stack)
        self.map_boxes: dict[str, QComboBox] = {}
        self.word_edits: dict[str, QLineEdit] = {}
        self.category = QComboBox()
        self.unit_box = QComboBox()
        self.net_unit = QComboBox()
        self.prefix = QLineEdit("J")
        self.refs = QLineEdit()
        self.ids = QPlainTextEdit()
        self.parts = QPlainTextEdit()
        self.signals = QPlainTextEdit()
        self.pin_function = QCheckBox(strings.IMP_NET_PINFUNC)
        self.pin_widgets: dict[str, QWidget] = {}
        self._pages: dict[str, QWidget] = {}
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(REPLAN_MS)
        self._timer.timeout.connect(wizard.replan_soon)
        self.notice = InlineNotice(wizard.theme)
        self.notice.setObjectName("import-map-notice")
        lay.addWidget(self.notice)
        self.busy_row = QWidget()
        busy = QHBoxLayout(self.busy_row)
        busy.setContentsMargins(0, 0, 0, 0)
        self.busy_label = QLabel()
        self.busy_label.setObjectName("import-busy")
        self.busy_label.setAccessibleName(strings.IMP_READING_NAME)
        self.busy_bar = QProgressBar()
        self.busy_bar.setRange(0, 0)  # busy, no percentage: the reading is one step
        self.busy_bar.setTextVisible(False)
        self.busy_bar.setMaximumWidth(wizard.theme.px(160))
        self.busy_cancel = QPushButton(strings.CANCEL)
        self.busy_cancel.setObjectName("import-busy-cancel")
        self.busy_cancel.clicked.connect(wizard.cancel_plan)
        busy.addWidget(self.busy_label)
        busy.addWidget(self.busy_bar)
        busy.addWidget(self.busy_cancel)
        busy.addStretch(1)
        self.busy_row.setVisible(False)
        lay.addWidget(self.busy_row)
        self.summary = QLabel()
        self.summary.setObjectName("import-map-summary")
        self.summary.setProperty("muted", True)
        lay.addWidget(self.summary)
        self.model = DictTableModel([], [], wizard.theme)
        self.preview = _table(self.model, wizard.theme, strings.IMP_PREVIEW_NAME, "import-preview", "import-preview", self)  # fmt: skip
        lay.addWidget(self.preview, 1)

    # ---- option widgets (rebuilt for every file) ------------------------------------------

    def load(self, source: Source, options: Options) -> None:
        kind = source.kind
        while self.stack.count():
            w = self.stack.widget(0)
            if w is None:
                break
            self.stack.removeWidget(w)
            w.deleteLater()
        self.map_boxes.clear()
        self._build(kind, source, options)
        self._set_columns(kind)

    def _form(self) -> tuple[QWidget, "GridForm"]:
        w = QWidget()
        form = GridForm(w, columns=3)
        self.stack.addWidget(w)
        self.stack.setCurrentWidget(w)
        return w, form

    def _combo(self, form: GridForm, key: str, label: str, header: list[str], current: int | None) -> None:  # fmt: skip
        box = QComboBox()
        box.setObjectName(f"import-map-{key}")
        box.setAccessibleName(label)
        box.setToolTip(label)
        box.addItem(strings.IMP_NOT_MAPPED, -1)
        for k, h in enumerate(header):
            box.addItem(h or strings.IMP_COLUMN_N.format(k + 1), k)
        box.setCurrentIndex((current if current is not None else -1) + 1)
        box.currentIndexChanged.connect(self.wiz.options_changed)
        self.map_boxes[key] = box
        form.addRow(label, box)

    def _words(self, form: GridForm, key: str, label: str, words: list[str]) -> None:
        edit = QLineEdit(", ".join(words))
        edit.setObjectName(f"import-words-{key}")
        edit.setAccessibleName(label)
        edit.setToolTip(strings.IMP_PARTS_WORDS_TIP)
        edit.textChanged.connect(self._later)
        self.word_edits[key] = edit
        form.addRow(label, edit)

    def _build(self, kind: str, source: Source, options: Options) -> None:
        _, form = self._form()
        if kind in ("interfaces", "parts", "pinout"):
            header = source.table[0] if source.table else []
            for key, label in import_kinds.mapping_fields(kind):
                self._combo(form, key, label, header, options.mapping.get(key))
        if kind == "parts":
            self.word_edits.clear()
            self._words(form, "approved", strings.IMP_PARTS_APPROVED, options.approved)
            self._words(form, "pending", strings.IMP_PARTS_PENDING, options.pending)
            self._words(form, "rejected", strings.IMP_PARTS_REJECTED, options.rejected)
            self.category = QComboBox()
            self.category.setObjectName("import-category")
            self.category.setAccessibleName(strings.IMP_PARTS_CATEGORY)
            self.category.addItem(strings.IMP_NOT_MAPPED, "")
            for c in PART_CATEGORIES:
                self.category.addItem(c, c)
            self.category.currentIndexChanged.connect(self.wiz.options_changed)
            form.addRow(strings.IMP_PARTS_CATEGORY, self.category)
        elif kind == "lengths":
            self.unit_box = QComboBox()
            self.unit_box.setObjectName("import-length-unit")
            self.unit_box.setAccessibleName(strings.IMP_LENGTHS_UNIT)
            for u in import_kinds.LENGTH_UNITS:
                self.unit_box.addItem(u, u)
            self.unit_box.setCurrentIndex(self.unit_box.findData(options.length_unit))
            self.unit_box.currentIndexChanged.connect(self.wiz.options_changed)
            form.addRow(strings.IMP_LENGTHS_UNIT, self.unit_box)
            note = QLabel(strings.IMP_LENGTHS_NOTE)
            note.setProperty("muted", True)
            note.setWordWrap(True)
            form.addRow(note)
        elif kind == "values":
            note = QLabel(strings.IMP_VALUES_NOTE)
            note.setProperty("muted", True)
            note.setWordWrap(True)
            form.addRow(note)
        elif kind == "pinout":
            self._build_pinout(form, options)
        elif kind == "netlist":
            self._build_netlist(form, options)

    def _pin_field(self, form: GridForm, key: str, widget: QWidget, label: str, tip: str) -> None:
        widget.setObjectName(f"import-pinout-{key}")
        widget.setAccessibleName(label)
        widget.setToolTip(tip)
        self.pin_widgets[key] = widget
        form.addRow(label, widget)

    def _build_pinout(self, form: GridForm, options: Options) -> None:
        theme = self.wiz.theme
        project = self.wiz.ctl.project
        self.pin_widgets = {}
        device = QComboBox()
        device.addItem(strings.IMP_PIN_DEVICE_NEW, "")
        for uid, unit in sorted(project.units.items()):
            device.addItem(f"{uid}  {unit.name}", uid)
        device.setCurrentIndex(max(0, device.findData(options.device)))
        device.currentIndexChanged.connect(self.wiz.options_changed)
        self._pin_field(form, "device", device, strings.IMP_PIN_DEVICE, strings.IMP_PIN_DEVICE_TIP)
        for key, label, tip, text in (
            ("name", strings.IMP_PIN_NEW_NAME, strings.IMP_PIN_NEW_NAME_TIP, options.new_device_name),
            ("subsystem", strings.IMP_PIN_SUBSYSTEM, strings.IMP_PIN_SUBSYSTEM_TIP, options.subsystem),
            ("connector", strings.IMP_PIN_CONNECTOR, strings.IMP_PIN_CONNECTOR_TIP, options.connector),
        ):  # fmt: skip
            line = QLineEdit(text)
            line.textChanged.connect(self._later)
            self._pin_field(form, key, line, label, tip)
        part = QComboBox()
        part.addItem(strings.IMP_PIN_PART_NONE, "")
        for pid, p in sorted(project.parts.items()):
            if p.category == "connector":
                part.addItem(pid, pid)
        part.setCurrentIndex(max(0, part.findData(options.default_part)))
        part.currentIndexChanged.connect(self.wiz.options_changed)
        self._pin_field(form, "part", part, strings.IMP_PIN_PART, strings.IMP_PIN_PART_TIP)
        parts = QPlainTextEdit("\n".join(f"{k}={v}" for k, v in options.parts.items()))
        parts.setFixedHeight(theme.px(56))
        mark_mono(parts)
        parts.textChanged.connect(self._later)
        self._pin_field(form, "parts", parts, strings.IMP_PIN_PARTS, strings.IMP_PIN_PARTS_TIP)
        gender = QComboBox()
        gender.addItem(strings.IMP_PIN_GENDER_PART, "")
        for g in ("female", "male"):
            gender.addItem(strings.DV_GENDER[g], g)
        gender.setCurrentIndex(max(0, gender.findData(options.gender)))
        gender.currentIndexChanged.connect(self.wiz.options_changed)
        self._pin_field(form, "gender", gender, strings.IMP_PIN_GENDER, strings.IMP_PIN_GENDER_TIP)
        replace = QCheckBox(strings.IMP_PIN_REPLACE)
        replace.setChecked(options.replace)
        replace.toggled.connect(self.wiz.options_changed)
        replace.setObjectName("import-pinout-replace")
        replace.setAccessibleName(strings.IMP_PIN_REPLACE)
        replace.setToolTip(strings.IMP_PIN_REPLACE_TIP)
        self.pin_widgets["replace"] = replace
        form.addRow(replace)

    def _build_netlist(self, form: GridForm, options: Options) -> None:
        theme = self.wiz.theme
        self.net_unit = QComboBox()
        self.net_unit.setObjectName("import-net-unit")
        self.net_unit.setAccessibleName(strings.IMP_NET_UNIT)
        self.net_unit.addItem(strings.IMP_NET_UNIT_NONE, "")
        for uid, unit in sorted(self.wiz.ctl.project.units.items()):
            self.net_unit.addItem(f"{uid}  {unit.name}", uid)
        self.net_unit.setCurrentIndex(max(0, self.net_unit.findData(options.unit_id)))
        self.net_unit.currentIndexChanged.connect(self.wiz.options_changed)
        form.addRow(strings.IMP_NET_UNIT, self.net_unit)
        self.prefix = QLineEdit(options.prefix)
        self.prefix.setObjectName("import-net-prefix")
        self.prefix.setAccessibleName(strings.IMP_NET_PREFIX)
        mark_mono(self.prefix)
        self.prefix.textChanged.connect(self._later)
        form.addRow(strings.IMP_NET_PREFIX, self.prefix)
        self.refs = QLineEdit(", ".join(options.refs))
        self.refs.setObjectName("import-net-refs")
        self.refs.setAccessibleName(strings.IMP_NET_REFS)
        self.refs.setToolTip(strings.IMP_NET_REFS_TIP)
        mark_mono(self.refs)
        self.refs.textChanged.connect(self._later)
        form.addRow(strings.IMP_NET_REFS, self.refs)
        for attr, key, label, tip, pairs in (
            ("ids", "ids", strings.IMP_NET_IDS, strings.IMP_NET_IDS_TIP, options.connector_ids),
            ("parts", "parts", strings.IMP_NET_PARTS, strings.IMP_NET_PARTS_TIP, options.parts),
            (
                "signals",
                "signals",
                strings.IMP_NET_SIGNALS,
                strings.IMP_NET_SIGNALS_TIP,
                options.signal_map,
            ),  # fmt: skip
        ):
            edit = QPlainTextEdit("\n".join(f"{k}={v}" for k, v in pairs.items()))
            edit.setObjectName(f"import-net-{key}")
            edit.setAccessibleName(label)
            edit.setToolTip(tip)
            edit.setFixedHeight(theme.px(56))
            mark_mono(edit)
            edit.textChanged.connect(self._later)
            setattr(self, attr, edit)
            form.addRow(label, edit)
        self.pin_function = QCheckBox(strings.IMP_NET_PINFUNC)
        self.pin_function.setObjectName("import-net-pinfunc")
        self.pin_function.setAccessibleName(strings.IMP_NET_PINFUNC)
        self.pin_function.setChecked(options.pin_function)
        self.pin_function.toggled.connect(self.wiz.options_changed)
        form.addRow(self.pin_function)

    def _later(self) -> None:
        self._timer.start()

    # ---- reading the choices back --------------------------------------------------------------

    def collect(self, kind: str, base: Options) -> Options:
        """The choices as `Options`; a malformed entry raises `ImportError_` (shown inline)."""
        o = Options(
            mapping=dict(base.mapping), approved=list(base.approved), pending=list(base.pending),
            rejected=list(base.rejected), category=base.category, length_unit=base.length_unit,
            unit_id=base.unit_id, prefix=base.prefix, refs=list(base.refs),
            connector_ids=dict(base.connector_ids), parts=dict(base.parts),
            signal_map=dict(base.signal_map), pin_function=base.pin_function,
            device=base.device, new_device_name=base.new_device_name, subsystem=base.subsystem,
            default_part=base.default_part, gender=base.gender, connector=base.connector,
            replace=base.replace,
        )  # fmt: skip
        if kind in ("interfaces", "parts", "pinout"):
            o.mapping = {k: int(b.currentData()) for k, b in self.map_boxes.items() if int(b.currentData()) >= 0}  # fmt: skip
        if kind == "parts":
            o.approved = import_kinds.parse_words(self.word_edits["approved"].text())
            o.pending = import_kinds.parse_words(self.word_edits["pending"].text())
            o.rejected = import_kinds.parse_words(self.word_edits["rejected"].text())
            o.category = str(self.category.currentData() or "")
        elif kind == "pinout":
            w = self.pin_widgets
            o.device = str(w["device"].currentData() or "")  # type: ignore[attr-defined]
            o.new_device_name = w["name"].text()  # type: ignore[attr-defined]
            o.subsystem = w["subsystem"].text()  # type: ignore[attr-defined]
            o.connector = w["connector"].text()  # type: ignore[attr-defined]
            o.default_part = str(w["part"].currentData() or "")  # type: ignore[attr-defined]
            o.parts = import_kinds.parse_pairs(w["parts"].toPlainText(), "Part")  # type: ignore[attr-defined]
            o.gender = str(w["gender"].currentData() or "")  # type: ignore[attr-defined]
            o.replace = w["replace"].isChecked()  # type: ignore[attr-defined]
        elif kind == "lengths":
            o.length_unit = str(self.unit_box.currentData() or "mm")
        elif kind == "netlist":
            o.unit_id = str(self.net_unit.currentData() or "")
            o.prefix = self.prefix.text().strip() or "J"
            o.refs = import_kinds.parse_words(self.refs.text())
            o.connector_ids = import_kinds.parse_pairs(self.ids.toPlainText(), "Connector ID")
            o.parts = import_kinds.parse_pairs(self.parts.toPlainText(), "Part")
            o.signal_map = import_kinds.parse_pairs(self.signals.toPlainText(), "Signal")
            o.pin_function = self.pin_function.isChecked()
        return o

    # ---- the preview ----------------------------------------------------------------------------

    def set_busy(self, text: str) -> None:
        """Show (or, with "", hide) the line that says the rows are being read."""
        self.busy_label.setText(text)
        self.busy_row.setVisible(bool(text))
        if text:
            self.notice.clear()

    def _set_columns(self, kind: str) -> None:
        names = import_kinds.PREVIEW_COLUMNS[kind]
        cols = [Column(i, n, mono=i < 2, width=110) for i, n in enumerate(names)]
        cols.append(Column("result", strings.IMP_COLUMNS["result"], state="state", tooltip="reason", width=130))  # fmt: skip
        self.model.columns = cols
        self.model.set_rows([])  # a reset, so the view reads the new columns

    def show_plan(self, plan: ImportPlanView) -> None:
        shown = plan.rows[: import_kinds.PREVIEW_ROWS]
        rows: list[dict[Any, Any]] = []
        for cells, r in zip(plan.preview[: import_kinds.PREVIEW_ROWS], shown, strict=False):
            row: dict[Any, Any] = dict(enumerate(cells))
            row.update({"result": r.result, "state": r.state, "reason": r.reason})
            rows.append(row)
        self.model.set_rows(rows)
        self.preview.resizeColumnsToContents()
        more = len(plan.rows) > len(shown)
        self.summary.setText(strings.IMP_PREVIEW_MORE.format(len(shown), len(plan.rows)) if more else "")  # fmt: skip
        self.summary.setVisible(more)
        if plan.problem:
            self.notice.show_notice("warning", plan.problem)
        else:
            self.notice.clear()

    def isComplete(self) -> bool:  # noqa: N802
        plan = self.wiz.plan  # the reasons are read on the next page, so rows are enough
        return not self.wiz.planning and plan is not None and bool(plan.rows)


class CheckPage(QWizardPage):
    """Every row with its exact reason, and what stays pending."""

    def __init__(self, wizard: "ImportWizard") -> None:
        super().__init__(wizard)
        self.wiz = wizard
        self.setTitle(strings.IMP_STEP_CHECK)
        lay = QVBoxLayout(self)
        intro = QLabel(strings.IMP_CHECK_INTRO)
        intro.setProperty("muted", True)
        lay.addWidget(intro)
        self.summary = QLabel()
        self.summary.setObjectName("import-check-summary")
        self.summary.setWordWrap(True)
        lay.addWidget(self.summary)
        self.notice = InlineNotice(wizard.theme)
        self.notice.setObjectName("import-check-notice")
        lay.addWidget(self.notice)
        self.only = QCheckBox(strings.IMP_CHECK_ONLY)
        self.only.setObjectName("import-only-problems")
        self.only.setAccessibleName(strings.IMP_CHECK_ONLY)
        self.only.setToolTip(strings.IMP_CHECK_ONLY_TIP)
        lay.addWidget(self.only)
        cols = [
            Column("row", strings.IMP_COLUMNS["row"], mono=True, width=60),
            Column("item", strings.IMP_COLUMNS["item"], mono=True, width=170),
            Column(
                "result", strings.IMP_COLUMNS["result"], state="state", tooltip="reason", width=130
            ),  # fmt: skip
            Column("reason", strings.IMP_COLUMNS["reason"], tooltip="reason", width=420),
        ]
        self.rows_model = DictTableModel(cols, [], wizard.theme)
        self.rows = _table(self.rows_model, wizard.theme, strings.IMP_ROWS_NAME, "import-rows", "import-rows", self)  # fmt: skip
        self.rows.setWordWrap(True)
        lay.addWidget(self.rows, 3)
        head = QLabel(strings.IMP_PENDING_HEAD)
        head.setProperty("heading", True)
        lay.addWidget(head)
        pcols = [
            Column(
                "item",
                strings.IMP_PENDING_COLUMNS["item"],
                mono=True,
                state="pending_state",
                width=190,
            ),  # fmt: skip
            Column("what", strings.IMP_PENDING_COLUMNS["what"], tooltip="what", width=480),
        ]
        self.pending_model = DictTableModel(pcols, [], wizard.theme)
        self.pending = _table(self.pending_model, wizard.theme, strings.IMP_PENDING_NAME, "import-pending", "import-pending", self)  # fmt: skip
        self.pending.setWordWrap(True)
        lay.addWidget(self.pending, 2)
        self.none = QLabel(strings.IMP_PENDING_NONE)
        self.none.setObjectName("import-pending-none")
        self.none.setProperty("muted", True)
        lay.addWidget(self.none)
        self.notes = QLabel()
        self.notes.setObjectName("import-notes")
        self.notes.setWordWrap(True)
        self.notes.setProperty("muted", True)
        lay.addWidget(self.notes)
        self.only.toggled.connect(self._filter)

    def _filter(self) -> None:
        self.rows.proxy.set_predicate((lambda r: isinstance(r, dict) and r["state"] != "pass") if self.only.isChecked() else None)  # fmt: skip
        self._fit()

    def _fit(self) -> None:
        if self.rows.proxy.rowCount() <= 500:  # wrapped reasons need taller rows
            self.rows.resizeRowsToContents()
        if self.pending_model.rowCount() <= 500:
            self.pending.resizeRowsToContents()

    def show_plan(self, plan: ImportPlanView) -> None:
        total = len(plan.rows)
        bad = plan.bad_count
        if not total:
            self.summary.setText(strings.IMP_EMPTY)
        elif bad == 0:
            self.summary.setText(strings.IMP_CHECK_ALL_OK.format(plan.ok_count))
        else:
            tail = strings.IMP_CHECK_SKIPS if plan.partial else strings.IMP_CHECK_BLOCKS
            self.summary.setText(f"{strings.IMP_CHECK_SUMMARY.format(plan.ok_count, total, bad)} {tail}")  # fmt: skip
        if plan.problem:
            self.notice.show_notice("error", plan.problem)
        else:
            self.notice.clear()
        self.rows_model.set_rows(_row_dicts(plan))
        self.only.blockSignals(True)
        self.only.setChecked(bad > 0 or any(r.state == "warning" for r in plan.rows))
        self.only.blockSignals(False)
        self._filter()
        self.pending_model.set_rows(
            [
                {"item": item, "what": what, "pending_state": "pending"}
                for item, what in plan.pending
            ]
        )
        self.none.setVisible(not plan.pending)
        self.pending.setVisible(bool(plan.pending))
        self.notes.setText("\n".join(plan.notes))
        self.notes.setVisible(bool(plan.notes))
        self._fit()

    def isComplete(self) -> bool:  # noqa: N802
        plan = self.wiz.plan
        return plan is not None and plan.importable


class ApplyPage(QWizardPage):
    """The last look: what will be imported, as one undo step."""

    def __init__(self, wizard: "ImportWizard") -> None:
        super().__init__(wizard)
        self.wiz = wizard
        self.setTitle(strings.IMP_STEP_APPLY)
        self.setFinalPage(True)
        lay = QVBoxLayout(self)
        self.head = QLabel()
        self.head.setObjectName("import-apply-head")
        self.head.setWordWrap(True)
        self.detail = QLabel()
        self.detail.setObjectName("import-apply-detail")
        self.detail.setWordWrap(True)
        self.notice = InlineNotice(wizard.theme)
        self.notice.setObjectName("import-apply-notice")
        lay.addWidget(self.head)
        lay.addWidget(self.detail)
        lay.addWidget(self.notice)
        lay.addStretch(1)

    def show_plan(self, plan: ImportPlanView) -> None:
        self.head.setText(f"<h3>{strings.IMP_APPLY_HEAD.format(plan.label.removeprefix('Import '))}</h3>")  # fmt: skip
        lines = [strings.IMP_APPLY_ONE_STEP.format(plan.label)]
        if plan.bad_count and plan.partial:
            lines.append(strings.IMP_APPLY_SKIPPED.format(plan.bad_count))
        if plan.pending:
            lines.append(strings.IMP_APPLY_PENDING.format(len(plan.pending)))
        if plan.next_step:
            lines.append(plan.next_step)
        self.detail.setText("\n".join(lines))
        self.notice.clear()
        self.wiz.setButtonText(QWizard.WizardButton.FinishButton, plan.label)

    def validatePage(self) -> bool:  # noqa: N802
        return self.wiz.apply()


_SWITCH_BACKGROUND = 0.0001  # seconds: how often a busy Python thread hands the interpreter over


class _PlanThread(QThread):
    """Reads the rows of a large file with the current choices off the GUI thread. The project is
    only read (the wizard is modal, so nobody edits it meanwhile); a result of an older request
    is thrown away by the wizard."""

    def __init__(self, project: Any, source: Source, options: Options, generation: int) -> None:
        super().__init__()
        self.project, self.source, self.options, self.generation = (
            project,
            source,
            options,
            generation,
        )
        self.plan: ImportPlanView | None = None
        self.error: str | None = None

    def run(self) -> None:
        # A busy Python thread keeps the interpreter for up to 5 ms at a time, and every Python
        # callback of the window (a size hint, a paint) then waits for it: 100 of them were half a
        # second. Handing it over every 0.1 ms keeps the window responsive while the rows are read.
        previous = sys.getswitchinterval()
        sys.setswitchinterval(_SWITCH_BACKGROUND)
        try:
            self.plan = import_kinds.plan_import(self.project, self.source, self.options)
        except Exception as exc:  # never let it escape the thread
            self.error = str(exc) or type(exc).__name__
        finally:
            sys.setswitchinterval(previous)


class ImportWizard(QWizard):
    """Import interfaces, approved parts, segment lengths, engineering values, a device pinout or a
    KiCad netlist.

    `pick_file(kind, filters)` is the file chooser (tests replace it). `kind` and `path` start the
    wizard on that kind with that file already read."""

    imported = Signal(int)  # rows imported, after the undo step exists
    pasteRequested = Signal()  # "paste table text instead": the window opens the paste dialog
    planned = Signal()  # the rows of a large file were read in the background

    def __init__(
        self,
        ctl: EditorController,
        theme: ThemeManager,
        parent: QWidget | None = None,
        *,
        pick_file: PickFile | None = None,
        kind: str | None = None,
        path: str | Path | None = None,
    ) -> None:
        super().__init__(parent)
        self.ctl, self.theme = ctl, theme
        self.pick_file: PickFile = pick_file or _pick_file
        self.kind = kind or KINDS[0].key
        self.source: Source | None = None
        self.choices = Options()
        self.plan: ImportPlanView | None = None
        self._source_version = 0
        self._map_version = -1
        self._plan_generation = 0  # a newer request or a cancel makes an older result stale
        self._plan_thread: _PlanThread | None = None
        self._old_threads: list[_PlanThread] = []
        self.setObjectName("import-wizard")
        self.setWindowTitle(strings.IMP_TITLE)
        self.setAccessibleName(strings.IMP_ACCESSIBLE)
        self.setWizardStyle(QWizard.WizardStyle.ClassicStyle)
        self.setOption(QWizard.WizardOption.NoBackButtonOnStartPage, True)
        self.setOption(QWizard.WizardOption.IndependentPages, True)
        self.setOption(QWizard.WizardOption.HaveHelpButton, False)
        self.resize(theme.px(960), theme.px(660))
        self.setMinimumSize(theme.px(760), theme.px(520))
        self.file_page = FilePage(self)
        self.map_page = MapPage(self)
        self.check_page = CheckPage(self)
        self.apply_page = ApplyPage(self)
        for pid, page in (
            (PAGE_FILE, self.file_page), (PAGE_MAP, self.map_page),
            (PAGE_CHECK, self.check_page), (PAGE_APPLY, self.apply_page),
        ):  # fmt: skip
            self.setPage(pid, page)
        for which, text, tip in (
            (QWizard.WizardButton.BackButton, strings.IMP_BACK, "Back (Alt+B)"),
            (QWizard.WizardButton.NextButton, strings.IMP_NEXT, "Next (Alt+N)"),  # fmt: skip
            (QWizard.WizardButton.CancelButton, strings.CANCEL, "Cancel (Esc)"),
            (QWizard.WizardButton.FinishButton, strings.IMP_LABEL.format(0, "s"), "Import (Alt+I)"),
        ):
            self.setButtonText(which, text)
            button = self.button(which)
            button.setToolTip(tip)
            button.setAccessibleName(text)
        self.button(QWizard.WizardButton.NextButton).setProperty("primary", True)
        self.button(QWizard.WizardButton.FinishButton).setProperty("primary", True)
        self.currentIdChanged.connect(self._page_changed)
        theme.changed.connect(self._restyle)
        self.set_kind(self.kind, announce=False)
        self.file_page.radios[self.kind].setChecked(True)
        self._set_source(None)
        if ctl.read_only:
            self.file_page.notice.show_notice("warning", strings.IMP_READ_ONLY)
        if path is not None:
            self.load_file(str(path))

    def _restyle(self) -> None:
        for which in (QWizard.WizardButton.NextButton, QWizard.WizardButton.FinishButton):
            b: QAbstractButton | None = self.button(which)
            if b is not None:
                b.style().unpolish(b)
                b.style().polish(b)

    # ---- page 1: kind and file -----------------------------------------------------------------

    def set_kind(self, kind: str, announce: bool = True) -> None:
        if kind not in KIND_BY_KEY:
            raise KeyError(kind)
        changed = kind != self.kind
        self.kind = kind
        if announce and changed and self.file_page.path.text().strip():
            self.load_file(self.file_page.path.text().strip())  # the same file, read as this kind
        elif changed:
            self._set_source(None)
        self.file_page.radios[kind].blockSignals(True)
        self.file_page.radios[kind].setChecked(True)
        self.file_page.radios[kind].blockSignals(False)

    def browse(self) -> None:
        path = self.pick_file(self.kind, KIND_BY_KEY[self.kind].filters)
        if path:
            self.file_page.path.setText(path)
            self.load_file(path)

    def load_file(self, path: str) -> bool:
        """Read `path` as the chosen kind; the reason is shown inline when it cannot be read."""
        page = self.file_page
        page.notice.clear()
        if not path:
            self._set_source(None)
            return False
        if page.path.text() != path:
            page.path.setText(path)
        if self.ctl.read_only:
            page.notice.show_notice("warning", strings.IMP_READ_ONLY)  # fmt: skip
            return False
        try:
            source = import_kinds.read_source(self.kind, path)
            options = import_kinds.default_options(self.kind, source)
        except (HarnessError, OSError) as exc:
            self._set_source(None)
            page.notice.show_notice("error", str(exc))
            return False
        self._set_source(source, options)
        return True

    def _set_source(self, source: Source | None, options: Options | None = None) -> None:
        self.source = source
        self.choices = options or Options()
        self.plan = None
        self._source_version += 1
        page = self.file_page
        if source is None:
            page.status.setText(strings.IMP_FILE_NONE if not page.notice.isVisible() else "")
        else:
            what = (
                strings.IMP_FILE_COMPONENTS.format(source.rows)
                if source.netlist is not None
                else strings.IMP_FILE_ROWS.format(source.rows)
            )
            if source.sheet:
                what = f"{strings.IMP_FILE_SHEET.format(source.sheet)}, {what}"
            page.status.setText(strings.IMP_FILE_READ.format(source.name, what))
        page.completeChanged.emit()

    # ---- page 2: options and preview -----------------------------------------------------------

    def _page_changed(self, page_id: int) -> None:
        if page_id == PAGE_MAP:
            if self._map_version != self._source_version and self.source is not None:
                self.map_page.load(self.source, self.choices)
                self._map_version = self._source_version
            self.replan_soon()
        elif page_id == PAGE_CHECK and self.plan is not None:
            self.check_page.show_plan(self.plan)
            self.check_page.completeChanged.emit()
        elif page_id == PAGE_APPLY and self.plan is not None:
            self.apply_page.show_plan(self.plan)

    def options_changed(self) -> None:
        self.replan_soon()

    @property
    def planning(self) -> bool:
        """The rows of a large file are being read in the background."""
        return self._plan_thread is not None

    def replan_soon(self) -> ImportPlanView | None:
        """`replan`, but a large file is read in a helper thread, with a progress line and Cancel
        on the page, so the window never freezes."""
        if self.source is None or self.source.rows <= LARGE_ROWS:
            self._drop_background()
            return self.replan()
        page = self.map_page
        try:
            self.choices = page.collect(self.kind, self.choices)
        except HarnessError as exc:
            self._drop_background()
            self.plan = ImportPlanView(self.kind, problem=str(exc))
            page.show_plan(self.plan)
            page.completeChanged.emit()
            return self.plan
        self._drop_background()
        self.plan = None
        thread = _PlanThread(self.ctl.project, self.source, self.choices, self._plan_generation)
        thread.finished.connect(self._background_done)
        self._plan_thread = thread
        page.set_busy(strings.IMP_READING.format(self.source.rows))
        page.completeChanged.emit()
        thread.start()
        return None

    def cancel_plan(self) -> None:
        """Stop waiting for the background reading (its result is not used)."""
        if self._plan_thread is not None:
            self._drop_background()
            self.map_page.set_busy("")
            self.map_page.notice.show_notice("warning", strings.IMP_READING_CANCELLED)
            self.map_page.completeChanged.emit()

    def _drop_background(self) -> None:
        thread, self._plan_thread = self._plan_thread, None
        self._plan_generation += 1
        if thread is not None:
            self._old_threads.append(thread)  # kept until it ends (a running thread is not deleted)
        self._old_threads = [t for t in self._old_threads if t.isRunning()]

    def _background_done(self) -> None:
        thread = self._plan_thread
        if thread is None or not thread.isFinished() or thread.generation != self._plan_generation:
            return  # the signal of a request that was cancelled or replaced
        self._plan_thread = None
        page = self.map_page
        page.set_busy("")
        if thread.plan is None:
            self.plan = ImportPlanView(self.kind, problem=thread.error or "")
        else:
            self.plan = thread.plan
        page.show_plan(self.plan)
        page.completeChanged.emit()
        self.planned.emit()

    def done(self, result: int) -> None:
        self._drop_background()
        for t in self._old_threads:
            t.wait()  # at most the time one reading takes
        super().done(result)

    def replan(self) -> ImportPlanView | None:
        """Read the rows again with the current choices (the project is not changed)."""
        if self.source is None:
            return None
        page = self.map_page
        try:
            self.choices = page.collect(self.kind, self.choices)
        except HarnessError as exc:
            self.plan = ImportPlanView(self.kind, problem=str(exc))
            page.show_plan(self.plan)
            page.completeChanged.emit()
            return self.plan
        self.plan = import_kinds.plan_import(self.ctl.project, self.source, self.choices)
        page.show_plan(self.plan)
        page.completeChanged.emit()
        return self.plan

    # ---- page 4: apply -------------------------------------------------------------------------

    def apply(self) -> bool:
        """Import as one undo step. False (the wizard stays open) when the controller refused it."""
        plan = self.plan
        if plan is None or not plan.importable:
            return False
        n = plan.ok_count
        reasons: list[str] = []

        def heard(text: str, _undo: bool) -> None:
            reasons.append(text)

        message = strings.IMP_DONE.format(n, "" if n == 1 else "s", plan.next_step).strip()
        self.ctl.message.connect(heard)
        try:
            ok = self.ctl.run(plan.label, plan.ops, message=message)
        finally:
            self.ctl.message.disconnect(heard)
        if not ok:
            why = reasons[0] if reasons else ""
            self.apply_page.notice.show_notice("error", strings.IMP_FAILED.format(why))
            return False
        self.imported.emit(n)
        return True
