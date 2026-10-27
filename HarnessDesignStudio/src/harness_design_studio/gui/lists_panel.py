"""Lists: the wire list, pinouts, BOM, mass and length, test tables and labels of a harness, and the
system BOM, as sortable, filterable tables.

    ListsPanel(ctl, theme, settings=None)

The rows come read-only from the `core.outputs.tables` builders, so they are the rows of the
exported files (and the verifier's reference); nothing is computed again here. A cell that is still
`pending`, a placeholder (`TBD`), an unknown part or an unapproved one is drawn as a state chip
(icon, word, pattern), never as plain text and never as an empty cell. A banner says when the design
changed after the harnesses were generated. "Export table" saves the rows as filtered and sorted
through the existing CSV and XLSX writers of the outputs.
"""

from pathlib import Path
from typing import Any

from PySide6.QtCore import QSettings, Qt, QTimer, Signal
from PySide6.QtGui import QAction, QFontMetrics, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QPushButton,
    QSplitter,
    QStackedWidget,
    QTabWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from harness_design_studio.core import edit
from harness_design_studio.core.generation_status import generation_status
from harness_design_studio.core.model import Harness, Project
from harness_design_studio.core.outputs import exports, tables
from harness_design_studio.core.outputs.stamp import Table, csv_bytes, stamp_of
from harness_design_studio.gui import strings
from harness_design_studio.gui.background import Job, JobRunner
from harness_design_studio.gui.controller import EditorController
from harness_design_studio.gui.harness_view import REFRESH_DELAY_MS
from harness_design_studio.gui.icons import icon_button
from harness_design_studio.gui.outputs_files import OutputsFiles
from harness_design_studio.gui.states import StateChip, chip_size
from harness_design_studio.gui.tables import Column, DictTableModel, TableView
from harness_design_studio.gui.theme import ThemeManager, mono_item_font

# (name, tab title, needs a harness)
LISTS: tuple[tuple[str, str, bool], ...] = (
    ("wirelist", strings.LP_WIRELIST, True),
    ("pinouts", strings.LP_PINOUTS, True),
    ("bom", strings.LP_BOM, True),
    ("mass", strings.LP_MASS, True),
    ("tests", strings.LP_TESTS, True),
    ("labels", strings.LP_LABELS, True),
    ("system-bom", strings.LP_SYSTEM_BOM, False),
)
NUMERIC = frozenset(
    {
        "AWG",
        "Length (m)",
        "Quantity",
        "Wires",
        "Connectors",
        "Wire length known (m)",
        "Wires without length",
        "Mass of wires and cable connectors (g)",
        "Margin (g)",
        "Mass with margin (g)",
    }
)
MONO = frozenset(
    {
        "Wire",
        "Part",
        "Connector",
        "Pin",
        "From connector",
        "From pin",
        "To connector",
        "To pin",
        "Test",
        "Label",
        "Mates with",
        "Harness",
        "Wires",
        "Shield group",
        "Interface",
        "Part number",
        "Used in",
        "From",
        "To",
    }
)
BLANK_IS_PENDING = frozenset({"Length (m)", "Margin (g)", "Mass with margin (g)"})


def cell_state(header: str, text: str) -> str | None:
    """The state chip a cell of an output table gets, or None for a plain cell. Only what the
    tables themselves say: "pending", "TBD (placeholder)", an unknown part category, a part that
    is missing from the parts list, an approval, a hand-set lock; and a blank where a number could
    not be worked out (an unknown length) so that it cannot be taken for an empty cell."""
    t = text.strip()
    if t == tables.PENDING or t.startswith(tables.PENDING + " "):
        return "pending"
    if t.startswith("TBD"):
        return "pending"
    if header == "Approval":
        if t.startswith("approved"):
            return "pass"
        if t.startswith("not_approved"):
            return "fail"
        if t.startswith("missing"):
            return "warning"
    if header == "Locked" and t == "yes":
        return "locked"
    if header == "Category" and t == "unknown":
        return "not-checked"
    if header == "Complete" and t == "no":
        return "pending"
    if header in BLANK_IS_PENDING and t == "":
        return "pending"
    return None


def _number(text: str) -> bool:
    try:
        float(text)
    except ValueError:
        return False
    return True


def table_columns(name: str, header: list[str], body: list[list[str]]) -> list[Column]:
    """`Column`s for a table of the outputs: the builder's own headers (units included), numbers
    right-aligned, IDs in monospace, state chips from `cell_state`."""
    cols: list[Column] = []
    for i, h in enumerate(header):
        numeric = h in NUMERIC and all(
            r[i] == "" or _number(r[i]) or cell_state(h, r[i]) for r in body if i < len(r)
        )

        def state(row: Any, i: int = i, h: str = h) -> str | None:
            return cell_state(h, str(row[i])) if i < len(row) else None

        def tip(row: Any, i: int = i, h: str = h) -> str | None:
            return _tip(h, str(row[i])) if i < len(row) else None

        cols.append(
            Column(
                i,
                h,
                numeric=numeric,
                mono=h in MONO and not numeric,
                state=state,
                tooltip=tip,
            )
        )
    return cols


def _tip(header: str, text: str) -> str | None:
    if header == "Approval" and text.startswith("missing"):
        return strings.LP_APPROVAL_MISSING
    return None


def build_tables(project: Project, h: Harness | None) -> dict[str, Table]:
    """All the lists, as the outputs build them: the six of one harness and the system BOM."""
    tables.clear_cache()
    out: dict[str, Table] = {}
    if h is not None:
        out["wirelist"] = tables.wire_list(project, h)
        out["pinouts"] = tables.pinouts(project, h)
        out["bom"] = tables.bom(project, [h])
        out["mass"] = tables.mass_length(project, [h])
        out["tests"] = tables.tests(project, h)
        out["labels"] = tables.labels(project, h)
    out["system-bom"] = tables.bom(
        project, [project.harnesses[i] for i in sorted(project.harnesses)]
    )
    return out


class _MeasuredTable(TableView):
    """A table whose columns are as wide as their header, their longest cell and their chips need,
    worked out from the model (not from the rows Qt happens to have laid out, which misses a chip
    that is below the first screenful); widths the person changed and saved win."""

    MAX_ROWS = 2000  # a longer list is measured by its first rows

    def _fit_columns(self) -> None:
        model = self.source
        if self._sized or model.rowCount() == 0:
            return
        theme = self.theme
        head = self.horizontalHeader()
        text_fm, mono_fm = self.fontMetrics(), QFontMetrics(mono_item_font())
        head_fm = head.fontMetrics()
        helper = self._widths
        if helper is not None:
            helper.busy = True
        try:
            for k, c in enumerate(model.columns):
                wanted = head_fm.horizontalAdvance(c.title) + theme.space(16) + theme.px(16)
                fm = mono_fm if c.mono else text_fm
                for r in range(min(model.rowCount(), self.MAX_ROWS)):
                    text, state = model.text_at(r, k), model.state_at(r, k)
                    if state:
                        w = chip_size(
                            state, theme, text or None, self.font()
                        ).width() + theme.space(8)
                    else:
                        w = fm.horizontalAdvance(text) + theme.space(12)
                    wanted = max(wanted, w)
                head.resizeSection(k, min(wanted, theme.px(360)))
        finally:
            if helper is not None:
                helper.busy = False
        self._sized = True


class ListsPanel(QWidget):
    """Sub-tabs of read-only tables for the selected harness. See the module text.

    Signals: `generateRequested()` (the banner's and the empty state's Generate) and
    `exportTableRequested(name, fmt)` (name of the list, "csv" or "xlsx"): the window asks for a
    file name and calls `export_to(path, name)`; the panel never opens a file dialog itself.
    """

    generateRequested = Signal()
    exportTableRequested = Signal(str, str)

    def __init__(
        self, ctl: EditorController, theme: ThemeManager, settings: QSettings | None = None
    ) -> None:
        super().__init__()
        self.ctl, self.theme, self.settings = ctl, theme, settings
        self.setObjectName("lists-panel")
        self._dirty = True
        self._hid: str | None = None
        self._key: tuple[Any, ...] | None = None
        self._data: dict[str, Table] = {}
        self._stale = False
        self._gen: tuple[tuple[int, int], str] | None = None
        self.jobs = JobRunner(ctl)
        self.jobs.done.connect(self._job_done)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(REFRESH_DELAY_MS)
        self._timer.timeout.connect(self.refresh)
        self.views: dict[str, TableView] = {}
        self.models: dict[str, DictTableModel] = {}
        self._combo_ids: list[str] = []
        self._measured: dict[str, str | None] = {}  # the harness each list's widths fit

        root = QVBoxLayout(self)
        gap = theme.space(8)
        root.setContentsMargins(gap, gap, gap, gap)
        root.setSpacing(gap)
        self.stack = QStackedWidget()
        root.addWidget(self.stack, 1)

        self.empty = QFrame()
        self.empty.setObjectName("lists-empty")
        e = QVBoxLayout(self.empty)
        e.addStretch(1)
        title = QLabel(strings.LP_EMPTY_TITLE)
        title.setProperty("heading", True)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_body = QLabel()
        self.empty_body.setObjectName("lists-empty-body")
        self.empty_body.setWordWrap(True)
        self.empty_body.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_generate = QPushButton()
        self.empty_generate.setObjectName("lists-empty-generate")
        self.empty_generate.setProperty("primary", True)
        icon_button(
            self.empty_generate,
            "generate",
            theme,
            strings.GENERATE_TIP,
            text=strings.HV_GENERATE_NOW,
        )
        self.empty_generate.clicked.connect(self.generateRequested)
        e.addWidget(title)
        e.addWidget(self.empty_body)
        e.addWidget(self.empty_generate, 0, Qt.AlignmentFlag.AlignHCenter)
        e.addStretch(2)
        self.stack.addWidget(self.empty)

        self.content = QWidget()
        c = QVBoxLayout(self.content)
        c.setContentsMargins(0, 0, 0, 0)
        c.setSpacing(gap)
        self.stack.addWidget(self.content)

        bar = QHBoxLayout()
        self.selector = QComboBox()
        self.selector.setObjectName("lists-harness")
        self.selector.setAccessibleName(strings.LP_HARNESS)
        self.selector.setToolTip(strings.LP_HARNESS_TIP)
        self.selector.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        self.selector.currentIndexChanged.connect(self._selector_changed)
        self.filter = QLineEdit()
        self.filter.setObjectName("lists-filter")
        self.filter.setPlaceholderText(strings.LP_FILTER)
        self.filter.setAccessibleName(strings.LP_FILTER)
        self.filter.setToolTip(strings.LP_FILTER_TIP)
        self.filter.setClearButtonEnabled(True)
        self.only_open = QPushButton()  # a toggle button: it stays visible in the dark theme
        self.only_open.setObjectName("lists-only-open")
        self.only_open.setCheckable(True)
        icon_button(
            self.only_open, "filter", theme, strings.LP_ONLY_OPEN_TIP,
            text=strings.LP_ONLY_OPEN, checked_role="on-primary",
        )  # fmt: skip
        self.count = QLabel()
        self.count.setObjectName("lists-count")
        self.count.setProperty("muted", True)
        self.export_btn = QToolButton()
        self.export_btn.setObjectName("lists-export")
        icon_button(self.export_btn, "export", theme, strings.LP_EXPORT_TIP, text=strings.LP_EXPORT)
        self.export_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        menu = QMenu(self.export_btn)
        self.act_csv = QAction(strings.LP_EXPORT_CSV, menu)
        self.act_csv.triggered.connect(lambda: self._export_requested("csv"))
        self.act_xlsx = QAction(strings.LP_EXPORT_XLSX, menu)
        self.act_xlsx.triggered.connect(lambda: self._export_requested("xlsx"))
        menu.addAction(self.act_csv)
        menu.addAction(self.act_xlsx)
        self.export_btn.setMenu(menu)
        bar.addWidget(self.selector)
        bar.addWidget(self.filter, 1)
        bar.addWidget(self.only_open)
        bar.addWidget(self.count)
        bar.addWidget(self.export_btn)
        c.addLayout(bar)

        self.banner = QFrame()
        self.banner.setObjectName("lists-stale-banner")
        self.banner.setProperty("banner", True)
        bl = QHBoxLayout(self.banner)
        self.banner_chip = StateChip(theme, "stale", strings.LP_STALE_CHIP)
        self.banner_text = QLabel(strings.LP_STALE)
        self.banner_text.setWordWrap(True)
        self.banner_btn = QPushButton()
        self.banner_btn.setObjectName("lists-stale-regenerate")
        icon_button(
            self.banner_btn,
            "generate",
            theme,
            strings.LP_REGENERATE_TIP,
            text=strings.HV_REGENERATE,
        )
        self.banner_btn.clicked.connect(self.generateRequested)
        bl.addWidget(self.banner_chip)
        bl.addWidget(self.banner_text, 1)
        bl.addWidget(self.banner_btn)
        c.addWidget(self.banner)
        self.banner.hide()

        self.tabs = QTabWidget()
        self.tabs.setObjectName("lists-tabs")
        self.tabs.setAccessibleName(strings.LP_TABS)
        # the lists above, the files they were exported to under them (M8)
        self.split = QSplitter(Qt.Orientation.Vertical)
        self.split.setObjectName("lists-split")
        self.split.setChildrenCollapsible(False)
        self.files = OutputsFiles(ctl, theme, settings)
        self.split.addWidget(self.tabs)
        self.split.addWidget(self.files)
        self.split.setStretchFactor(0, 3)
        self.split.setStretchFactor(1, 2)
        c.addWidget(self.split, 1)
        ctl.changed.connect(
            lambda d: self.files.invalidate() if getattr(d, "full", False) else None
        )
        for name, tab_title, _needs in LISTS:
            model = DictTableModel([], (), theme)
            view = _MeasuredTable(
                model, theme, name=tab_title, settings=settings, key=f"lists-{name}"
            )
            view.setObjectName(f"list-{name}")
            self.views[name], self.models[name] = view, model
            self.tabs.addTab(view, tab_title)
        self.tabs.currentChanged.connect(lambda _i: self._update_count())
        self.filter.textChanged.connect(self._apply_filter)
        self.only_open.toggled.connect(self._apply_filter)
        sc = QShortcut(QKeySequence.StandardKey.Find, self)
        sc.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        sc.activated.connect(self._focus_filter)

        ctl.changed.connect(lambda _d: self._invalidate())
        self.refresh()

    # ---- public API ------------------------------------------------------------------------
    def current_name(self) -> str:
        """The name of the list that is showing ("wirelist", "pinouts", "bom", "mass", "tests",
        "labels" or "system-bom")."""
        return LISTS[self.tabs.currentIndex()][0]

    def set_table(self, name: str) -> None:
        for i, (n, _t, _h) in enumerate(LISTS):
            if n == name:
                self.tabs.setCurrentIndex(i)
                return
        raise KeyError(name)

    def harness_id(self) -> str | None:
        return self._hid

    def select_harness(self, harness_id: str) -> bool:
        if harness_id not in self.ctl.project.harnesses:
            return False
        if self._dirty:
            self.refresh()
        i = self.selector.findData(harness_id)
        if i < 0:
            return False
        self.selector.setCurrentIndex(i)
        return True

    def view(self, name: str) -> TableView:
        return self.views[name]

    def is_stale(self) -> bool:
        """Did the design change after the harnesses were generated? (the banner)"""
        return self._stale

    def refresh(self) -> None:
        """Rebuild the lists from the harnesses. The staleness check runs in the background."""
        self._timer.stop()
        self._dirty = False
        p = self.ctl.project
        ids = sorted(p.harnesses)
        self.stack.setCurrentWidget(self.content if ids else self.empty)
        if not ids:
            self._hid = None
            self._combo_ids = []
            n = len(p.interfaces)
            if n:
                body = strings.LP_EMPTY_READY
            elif p.links:  # connections first: harnesses are made from connections
                body = strings.LP_EMPTY_HAS_LINKS
            else:
                body = strings.LP_EMPTY_NO_INTERFACES
            self.empty_body.setText(body)
            self.empty_generate.setVisible(bool(n) and not self.ctl.read_only)
            self._set_stale(False)
            return
        self._fill_selector(ids)
        h = p.harnesses[self._hid or ids[0]]
        self._hid = h.id
        key = (self.ctl.state_token, h.id)
        if key != self._key:
            self._key = key
            self._data = build_tables(p, h)
            for name, table in self._data.items():
                self._show(name, table)
        self._start_stale_check()

    def visible_table(self, name: str | None = None) -> Table:
        """The list as it is shown: the builder's header row, then the rows that pass the filter,
        in the order of the sort."""
        name = name or self.current_name()
        view, model = self.views[name], self.models[name]
        header = [
            str(model.headerData(i, Qt.Orientation.Horizontal) or "")
            for i in range(model.columnCount())
        ]
        source = self._data.get(name, [])
        header = list(source[0]) if source else header
        rows: Table = []
        for r in range(view.proxy.rowCount()):
            src = view.proxy.mapToSource(view.proxy.index(r, 0)).row()
            rows.append([str(v) for v in model.row(src)])
        return [header, *rows]

    def table_bytes(self, fmt: str, name: str | None = None) -> bytes:
        """The visible rows as a CSV file or an Excel workbook, written by the same code that
        writes the outputs (same stamp line: the model hash)."""
        name = name or self.current_name()
        table = self.visible_table(name)
        stamp = stamp_of(self.ctl.project)
        if fmt == "csv":
            return csv_bytes(table, stamp)
        title = next(t for n, t, _h in LISTS if n == name)
        return exports.xlsx_bytes({title: table}, stamp)

    def export_to(self, path: Path, name: str | None = None) -> Path:
        """Write the visible rows to `path` as CSV (`.csv`) or an Excel workbook (`.xlsx`)."""
        fmt = "xlsx" if path.suffix.lower() == ".xlsx" else "csv"
        data = self.table_bytes(fmt, name)
        path = path if path.suffix.lower() in (".csv", ".xlsx") else path.with_suffix("." + fmt)
        path.write_bytes(data)
        return path

    def wait_idle(self, timeout_ms: int = 10000) -> bool:
        return self.jobs.wait_idle(timeout_ms)

    # ---- internals -------------------------------------------------------------------------
    def _invalidate(self) -> None:
        self._dirty = True
        if self.isVisible():
            self._timer.start()  # edits close together share one refresh, after the edit itself

    def showEvent(self, event: object) -> None:  # noqa: N802
        super().showEvent(event)  # type: ignore[arg-type]
        if self._dirty:
            self.refresh()

    def _focus_filter(self) -> None:
        self.filter.setFocus()
        self.filter.selectAll()

    def _fill_selector(self, ids: list[str]) -> None:
        if ids != self._combo_ids:
            keep = self._hid
            self.selector.blockSignals(True)
            self.selector.clear()
            for hid in ids:
                self.selector.addItem(hid, hid)
            self.selector.blockSignals(False)
            self._combo_ids = list(ids)
            self._hid = keep if keep in ids else ids[0]
        i = self.selector.findData(self._hid)
        if i >= 0 and i != self.selector.currentIndex():
            self.selector.blockSignals(True)
            self.selector.setCurrentIndex(i)
            self.selector.blockSignals(False)

    def _selector_changed(self, _i: int) -> None:
        hid = self.selector.currentData()
        if isinstance(hid, str) and hid != self._hid:
            self._hid = hid
            self.refresh()

    def _show(self, name: str, table: Table) -> None:
        header, body = (table[0], table[1:]) if table else ([], [])
        model, view = self.models[name], self.views[name]
        cols = table_columns(name, header, body)
        saved = view._widths is not None and view._widths.has_saved
        if not saved and (
            [c.header for c in model.columns] != header or self._measured.get(name) != self._hid
        ):
            view._sized = False  # other columns or another harness: measure again
        self._measured[name] = self._hid
        model.columns = cols  # replaced just before the reset that `set_rows` does
        model.set_rows([tuple(r) for r in body])
        self._apply_filter()

    def _apply_filter(self, *_: object) -> None:
        text = self.filter.text()
        states = {"pending", "not-checked"} if self.only_open.isChecked() else None
        for view in self.views.values():
            view.proxy.set_text(text)
            view.proxy.set_states(states)
        self._update_count()

    def _update_count(self) -> None:
        name = self.current_name()
        view, model = self.views[name], self.models[name]
        shown, total = view.proxy.rowCount(), model.rowCount()
        self.count.setText(
            strings.LP_COUNT.format(shown, total)
            if shown != total
            else strings.LP_COUNT_ALL.format(total)
        )

    def _export_requested(self, fmt: str) -> None:
        self.exportTableRequested.emit(self.current_name(), fmt)

    def _start_stale_check(self) -> None:
        token = self.ctl.state_token
        if self._gen is not None and self._gen[0] == token:
            self._set_stale(self._gen[1] == "stale")
            return
        snapshot = edit.clone_with(self.ctl.project, [])
        self.jobs.start("generation", None, lambda: generation_status(snapshot))

    def _job_done(self, job: Job) -> None:
        if job.error is None and self.jobs.is_current(job):
            self._gen = (job.token, job.value)
            self._set_stale(job.value == "stale")
        elif not self.jobs.is_current(job) and self.isVisible() and not self.jobs.busy():
            self._invalidate()

    def _set_stale(self, stale: bool) -> None:
        self._stale = stale and bool(self.ctl.project.harnesses)
        self.banner.setVisible(self._stale)
        self.banner_btn.setEnabled(not self.ctl.read_only)
