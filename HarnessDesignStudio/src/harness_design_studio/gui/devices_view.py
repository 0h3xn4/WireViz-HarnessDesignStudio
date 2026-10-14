"""Devices view: one unit with its connectors and pins, the pinout as it will be exported, and the
notes the pin checks give. Plugged into the window as the sixth main tab (`install_view("devices",
...)`, Ctrl+6).

    DevicesView(ctl, theme, settings=None)

* Header: the device (a unit; the unit selected on the diagram or in the project tree is the one
  shown), its state (Draft, In use, Locked, Read-only), counts, Duplicate and Export pinout.
* Connector list, connector card (part, gender, keying, what it carries, how its pins are
  allocated) and the pin table (pin, signal, mode, interface, direction, class, wire, state).
  Direction and class are worked out from the interface type of the pin's signal and are empty,
  with the reason as tooltip, when nothing can be said: nothing is guessed.
* Notes under the pin table (`core.devices.pinout_problems`) and "Pinout as exported": exactly
  the rows of `system/box_pinouts.csv` for this unit.
* Every number and sentence comes from headless code in `core.devices`; this file only shows it.
"""

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from PySide6.QtCore import QModelIndex, QSettings, Qt, QTimer, Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSplitter,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from harness_design_studio.core import devices, edit
from harness_design_studio.core.outputs import exports
from harness_design_studio.core.outputs.stamp import Table, csv_bytes, stamp_of
from harness_design_studio.gui import strings
from harness_design_studio.gui.controller import EditorController
from harness_design_studio.gui.harness_view import REFRESH_DELAY_MS
from harness_design_studio.gui.icons import icon_button
from harness_design_studio.gui.lists_panel import table_columns
from harness_design_studio.gui.states import StateChip
from harness_design_studio.gui.tables import Column, DictTableModel, Row, TableView, natural_key
from harness_design_studio.gui.theme import ThemeManager

_SEVERITY = {
    "error": ("fail", strings.DV_STATE_ERROR),
    "warning": ("warning", strings.DV_STATE_WARNING),
    "info": ("info", strings.DV_STATE_NOTE),
}
_DEVICE_STATE = {
    "draft": ("draft", strings.DV_STATE_DRAFT),
    "in_use": ("info", strings.DV_STATE_IN_USE),
    "locked": ("locked", strings.DV_STATE_LOCKED),
    "read_only": ("locked", strings.DV_STATE_READ_ONLY),
}


def plural(words: tuple[str, str], n: int) -> str:
    """ "1 connector", "3 connectors"."""
    return words[0 if n == 1 else 1].format(n)


def pin_state(row: devices.PinRow, notes: list[devices.PinProblem]) -> tuple[str | None, str, str]:
    """(state key, word, tooltip) of a pin's State cell. A lock by a release comes first, then the
    worst note, then an auto-filled pin; a spare pin shows its word without a chip."""
    if row.lock:
        return "locked", strings.DV_STATE_LOCKED_PIN, row.lock
    if notes:
        key, word = _SEVERITY[notes[0].severity]  # (sorted worst first)
        return key, word, "\n".join(n.message for n in notes)
    if row.auto:
        return "info", strings.DV_STATE_AUTO, strings.DV_STATE_AUTO_TIP
    if row.spare:
        return None, strings.DV_STATE_SPARE, ""
    return None, "", ""


def pin_rows_for_table(
    rows: list[devices.PinRow], problems: list[devices.PinProblem]
) -> list[dict[str, Any]]:
    """The pin table's rows (dicts) for `PIN_COLUMNS`."""
    by_pin: dict[str, list[devices.PinProblem]] = {}
    for pr in problems:
        if pr.pin_id is not None:
            by_pin.setdefault(pr.pin_id, []).append(pr)
    out = []
    for r in rows:
        key, word, tip = pin_state(r, by_pin.get(r.pin, []))
        out.append(
            {
                "pin": r.pin,
                "signal": r.signal,
                "mode": strings.DV_MODE[r.mode],
                "mode_tip": strings.DV_MODE_TIP[r.mode],
                "interface": r.interface_id,
                "direction": r.direction,
                "class": r.category,
                "meaning_tip": r.note,
                "wire": ";".join(r.wires),
                "contact_size": r.contact_size,
                "termination": strings.DV_TERMINATION[r.termination],
                "state_key": key,
                "state": word,
                "state_tip": tip,
            }
        )
    return out


def _tip(key: str) -> Any:
    return lambda row: _field(row, key) or None


def _field(row: Row, key: str) -> Any:
    """A field of a row of these tables (rows are dicts)."""
    return row.get(key) if isinstance(row, Mapping) else None


PIN_COLUMNS = [
    Column("pin", strings.DV_COL_PIN, mono=True, width=56),
    Column("signal", strings.DV_COL_SIGNAL, mono=True, width=104),
    Column("mode", strings.DV_COL_MODE, tooltip=_tip("mode_tip"), width=64),
    Column("interface", strings.DV_COL_INTERFACE, mono=True, width=80),
    Column("direction", strings.DV_COL_DIRECTION, tooltip=_tip("meaning_tip"), width=76),
    Column("class", strings.DV_COL_CLASS, tooltip=_tip("meaning_tip"), width=76),
    Column("wire", strings.DV_COL_WIRE, mono=True, width=96),
    Column("contact_size", strings.DV_COL_CONTACT_SIZE, mono=True, width=96),
    Column("termination", strings.DV_COL_TERMINATION, width=96),
    Column(
        "state", strings.DV_COL_STATE, state=lambda r: _field(r, "state_key"), tooltip=_tip("state_tip"),
        width=130,
    ),
]  # fmt: skip
CONTACT_COLUMNS = ("contact_size", "termination")

CONNECTOR_COLUMNS = [
    Column("name", strings.DV_COL_CONNECTOR, mono=True, width=80),
    Column("part", strings.DV_COL_PART, mono=True, width=130),
    Column("pins", strings.DV_COL_PINS, numeric=True, width=56),
        Column(
        "state", strings.DV_COL_STATE, state=lambda r: _field(r, "state_key"), tooltip=_tip("state_tip"),
        width=110,
    ),
]  # fmt: skip

NOTE_COLUMNS = [
    Column("severity", strings.DV_COL_SEVERITY, state=lambda r: _field(r, "state_key"), width=110),
    Column("where", strings.DV_COL_WHERE, mono=True, width=80),
    Column("check", strings.DV_COL_CHECK, mono=True, width=70),
    Column("message", strings.DV_COL_NOTE, width=480),
]


class DevicesView(QWidget):
    """One unit, its connectors, pins, notes and exported pinout. See the module text.

    Signals: `addRequested()` (the empty state's button), `duplicateRequested(unit_id)`,
    `exportPinoutRequested(unit_id)` (the window asks for a file name and calls `export_to`),
    `whyRequested(kind, id)` for a pin ("pin", "connector.pin"), `deviceChanged(unit_id)` and
    `connectorChanged(connector_id)`.
    """

    addRequested = Signal()
    duplicateRequested = Signal(str)
    exportPinoutRequested = Signal(str)
    whyRequested = Signal(str, str)
    deviceChanged = Signal(str)
    connectorChanged = Signal(str)

    def __init__(
        self, ctl: EditorController, theme: ThemeManager, settings: QSettings | None = None
    ) -> None:
        super().__init__()
        self.ctl, self.theme, self.settings = ctl, theme, settings
        self.setObjectName("devices-view")
        self.setAccessibleName(strings.DV_ACCESSIBLE)
        self._dirty = True
        self._syncing = False
        self._unit: str | None = None
        self._cid: str | None = None
        self._units: list[str] = []
        self._key: tuple[Any, ...] | None = None
        self._pinout: Table = []
        self._pin_index: dict[str, int] = {}
        self._notes: list[devices.PinProblem] = []
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(REFRESH_DELAY_MS)
        self._timer.timeout.connect(self.refresh)

        gap = theme.space(8)
        root = QVBoxLayout(self)
        root.setContentsMargins(gap, gap, gap, gap)
        root.setSpacing(gap)
        self.stack = QStackedWidget()
        root.addWidget(self.stack, 1)
        self._build_empty(theme)
        self.content = QWidget()
        c = QVBoxLayout(self.content)
        c.setContentsMargins(0, 0, 0, 0)
        c.setSpacing(gap)
        self.stack.addWidget(self.content)
        c.addLayout(self._build_header(theme))
        self.vsplit = QSplitter(Qt.Orientation.Vertical)
        self.vsplit.setObjectName("devices-splitter")
        self.vsplit.setChildrenCollapsible(False)
        c.addWidget(self.vsplit, 1)
        self.hsplit = QSplitter(Qt.Orientation.Horizontal)
        self.hsplit.setObjectName("devices-top-splitter")
        self.hsplit.setChildrenCollapsible(False)
        self.vsplit.addWidget(self.hsplit)
        self._build_connectors(theme)
        self._build_pins(theme)
        self._build_preview(theme)
        self.hsplit.setStretchFactor(0, 2)
        self.hsplit.setStretchFactor(1, 7)
        self.vsplit.setStretchFactor(0, 3)
        self.vsplit.setStretchFactor(1, 1)

        ctl.changed.connect(lambda _d: self._invalidate())
        ctl.selectionChanged.connect(self._follow_selection)
        ctl.stateChanged.connect(self._read_only_changed)
        self.refresh()

    # ---- building ----------------------------------------------------------------------------
    def _build_empty(self, theme: ThemeManager) -> None:
        self.empty = QFrame()
        self.empty.setObjectName("devices-empty")
        e = QVBoxLayout(self.empty)
        e.addStretch(1)
        title = QLabel(strings.DV_EMPTY_TITLE)
        title.setProperty("heading", True)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        body = QLabel(strings.DV_EMPTY_BODY)
        body.setObjectName("devices-empty-body")
        body.setWordWrap(True)
        body.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_add = QPushButton()
        self.empty_add.setObjectName("devices-empty-add")
        self.empty_add.setProperty("primary", True)
        icon_button(self.empty_add, "plus", theme, strings.DV_ADD_TIP, text=strings.DV_ADD)
        self.empty_add.clicked.connect(self.addRequested)
        e.addWidget(title)
        e.addWidget(body)
        e.addWidget(self.empty_add, 0, Qt.AlignmentFlag.AlignHCenter)
        e.addStretch(2)
        self.stack.addWidget(self.empty)

    def _build_header(self, theme: ThemeManager) -> QVBoxLayout:
        box = QVBoxLayout()
        box.setSpacing(theme.space(4))
        row1 = QHBoxLayout()
        self.selector = QComboBox()
        self.selector.setObjectName("devices-selector")
        self.selector.setAccessibleName(strings.DV_DEVICE)
        self.selector.setToolTip(strings.DV_DEVICE_TIP)
        self.selector.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        self.selector.setMinimumWidth(theme.px(100))
        self.selector.currentIndexChanged.connect(self._selector_changed)
        self.state_chip = StateChip(theme, "draft", strings.DV_STATE_DRAFT)
        self.state_chip.setObjectName("devices-state")
        self.name = QLabel()
        self.name.setObjectName("devices-name")
        self.name.setProperty("title", True)
        self.name.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.subsystem = QLabel()
        self.subsystem.setObjectName("devices-subsystem")
        self.subsystem.setProperty("muted", True)
        row1.addWidget(self.selector)
        row1.addWidget(self.state_chip)
        row1.addWidget(self.name, 1)
        row1.addWidget(self.subsystem)
        box.addLayout(row1)
        row2 = QHBoxLayout()
        self.counts = QLabel()
        self.counts.setObjectName("devices-counts")
        self.counts.setProperty("muted", True)
        self.duplicate_btn = QPushButton()
        self.duplicate_btn.setObjectName("devices-duplicate")
        icon_button(
            self.duplicate_btn, "unit", theme, strings.DV_DUPLICATE_TIP, "Ctrl+D",
            text=strings.DV_DUPLICATE,
        )  # fmt: skip
        self.duplicate_btn.clicked.connect(self._duplicate)
        self.export_btn = QPushButton()
        self.export_btn.setObjectName("devices-export")
        icon_button(self.export_btn, "export", theme, strings.DV_EXPORT_TIP, text=strings.DV_EXPORT)
        self.export_btn.clicked.connect(self._export)
        row2.addWidget(self.counts, 1)
        row2.addWidget(self.duplicate_btn)
        row2.addWidget(self.export_btn)
        box.addLayout(row2)
        return box

    @staticmethod
    def _caption(text: str) -> QLabel:
        label = QLabel(text)
        label.setProperty("heading", True)
        return label

    def _build_connectors(self, theme: ThemeManager) -> None:
        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 0, 0)
        ll.setSpacing(theme.space(4))
        ll.addWidget(self._caption(strings.DV_CONNECTORS))
        self.conn_model = DictTableModel(CONNECTOR_COLUMNS, (), theme)
        self.conn_table = TableView(
            self.conn_model, theme, name=strings.DV_CONNECTORS, settings=self.settings,
            key="devices-connectors",
        )  # fmt: skip
        self.conn_table.setObjectName("devices-connector-table")
        self.conn_table.setToolTip(strings.DV_CONNECTORS_TIP)
        self.conn_table.setSelectionBehavior(self.conn_table.SelectionBehavior.SelectRows)
        self.conn_table.setSelectionMode(self.conn_table.SelectionMode.SingleSelection)
        sm = self.conn_table.selectionModel()
        if sm is not None:
            sm.currentChanged.connect(self._connector_current)
        ll.addWidget(self.conn_table, 1)
        self.no_connectors = QLabel(strings.DV_NO_CONNECTORS)
        self.no_connectors.setObjectName("devices-no-connectors")
        self.no_connectors.setProperty("muted", True)
        self.no_connectors.setWordWrap(True)
        ll.addWidget(self.no_connectors)
        self.hsplit.addWidget(left)

    def _build_pins(self, theme: ThemeManager) -> None:
        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(theme.space(4))
        self.card = QFrame()
        self.card.setObjectName("devices-card")
        self.card.setProperty("card", True)
        grid = QGridLayout(self.card)
        grid.setContentsMargins(theme.space(8), theme.space(4), theme.space(8), theme.space(4))
        grid.setHorizontalSpacing(theme.space(12))
        self.card_values: dict[str, QLabel] = {}
        for k, (key, label) in enumerate(
            (
                ("part", strings.DV_CARD_PART),
                ("gender", strings.DV_CARD_GENDER),
                ("keying", strings.DV_CARD_KEYING),
                ("carries", strings.DV_CARD_CARRIES),
                ("allocation", strings.DV_CARD_ALLOCATION),
            )
        ):
            cap = QLabel(label)
            cap.setProperty("muted", True)
            value = QLabel()
            value.setObjectName(f"devices-card-{key}")
            value.setWordWrap(True)
            value.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            grid.addWidget(cap, k, 0, Qt.AlignmentFlag.AlignTop)
            grid.addWidget(value, k, 1)
            self.card_values[key] = value
        grid.setColumnStretch(1, 1)
        rl.addWidget(self.card)

        bar = QHBoxLayout()
        self.pins_caption = self._caption(strings.DV_PINS)
        bar.addWidget(self.pins_caption)
        bar.addStretch(1)
        self.pin_filter = QLineEdit()
        self.pin_filter.setObjectName("devices-pin-filter")
        self.pin_filter.setPlaceholderText(strings.DV_PIN_FILTER)
        self.pin_filter.setAccessibleName(strings.DV_PIN_FILTER)
        self.pin_filter.setToolTip(f"{strings.DV_PIN_FILTER_TIP} (Ctrl+F)")
        self.pin_filter.setClearButtonEnabled(True)
        self.pin_filter.setMaximumWidth(theme.px(180))
        self.contact_btn = QPushButton()
        self.contact_btn.setObjectName("devices-contact")
        self.contact_btn.setCheckable(True)
        icon_button(
            self.contact_btn, "filter", theme, strings.DV_CONTACT_TIP, text=strings.DV_CONTACT,
            checked_role="on-primary",
        )  # fmt: skip
        bar.addWidget(self.pin_filter)
        bar.addWidget(self.contact_btn)
        rl.addLayout(bar)
        self.pin_model = DictTableModel(PIN_COLUMNS, (), self.theme)
        self.pin_table = TableView(
            self.pin_model, self.theme, name=strings.DV_PINS, settings=self.settings,
            key="devices-pins",
        )  # fmt: skip
        self.pin_table.setObjectName("devices-pin-table")
        self.pin_table.sortByColumn(-1, Qt.SortOrder.AscendingOrder)
        self.pin_table.activated.connect(self._pin_activated)
        rl.addWidget(self.pin_table, 1)
        self.pin_count = QLabel()
        self.pin_count.setObjectName("devices-pin-count")
        self.pin_count.setProperty("muted", True)
        rl.addWidget(self.pin_count)

        rl.addWidget(self._caption(strings.DV_NOTES))
        self.note_model = DictTableModel(NOTE_COLUMNS, (), self.theme)
        self.note_table = TableView(
            self.note_model, self.theme, name=strings.DV_NOTES, settings=self.settings,
            key="devices-notes",
        )  # fmt: skip
        self.note_table.setObjectName("devices-note-table")
        self.note_table.setToolTip(strings.DV_NOTES_TIP)
        self.note_table.setMaximumHeight(theme.px(150))
        self.note_table.activated.connect(self._note_activated)
        rl.addWidget(self.note_table)
        self.note_label = QLabel()
        self.note_label.setObjectName("devices-note-label")
        self.note_label.setProperty("muted", True)
        rl.addWidget(self.note_label)
        self.hsplit.addWidget(right)

        self.pin_filter.textChanged.connect(self.pin_table.proxy.set_text)
        self.pin_filter.textChanged.connect(lambda _t: self._update_pin_count())
        self.contact_btn.toggled.connect(self._contact_toggled)
        self._contact_toggled(False)
        find = QShortcut(QKeySequence.StandardKey.Find, self)
        find.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        find.activated.connect(self._focus_filter)

    def _build_preview(self, theme: ThemeManager) -> None:
        box = QWidget()
        bl = QVBoxLayout(box)
        bl.setContentsMargins(0, 0, 0, 0)
        bl.setSpacing(theme.space(4))
        bar = QHBoxLayout()
        bar.addWidget(self._caption(strings.DV_PREVIEW))
        hint = QLabel(strings.DV_PREVIEW_HINT)
        hint.setProperty("muted", True)
        hint.setWordWrap(True)
        bar.addWidget(hint, 1)
        bl.addLayout(bar)
        self.preview_model = DictTableModel([], (), theme)
        self.preview_table = TableView(
            self.preview_model, theme, name=strings.DV_PREVIEW_TABLE, settings=self.settings,
            key="devices-preview",
        )  # fmt: skip
        self.preview_table.setObjectName("devices-preview-table")
        bl.addWidget(self.preview_table, 1)
        self.vsplit.addWidget(box)

    # ---- public API --------------------------------------------------------------------------
    def unit_id(self) -> str | None:
        """The device shown."""
        return self._unit

    def connector_id(self) -> str | None:
        """The connector whose pins are shown."""
        return self._cid

    def show_unit(self, unit_id: str, connector_id: str | None = None) -> bool:
        """Show a unit (and a connector of it). False when the unit does not exist."""
        if unit_id not in self.ctl.project.units:
            return False
        if self._dirty or unit_id not in self._units:
            self._refresh_units()
        self._unit = unit_id
        if connector_id is not None:
            self._cid = connector_id
        self.refresh()
        return True

    def select_connector(self, connector_id: str) -> bool:
        c = self.ctl.project.connectors.get(connector_id)
        if c is None or c.unit_id is None:
            return False
        return self.show_unit(c.unit_id, connector_id)

    def select_pin(self, pin_id: str) -> bool:
        """Make a pin of the connector shown the current row."""
        if self._dirty:
            self.refresh()
        row = self._pin_index.get(pin_id)
        if row is None:
            return False
        index = self.pin_table.proxy.mapFromSource(self.pin_model.index(row, 0))
        if not index.isValid():
            return False
        self.pin_table.setCurrentIndex(index)
        self.pin_table.scrollTo(index)
        return True

    def current_pin(self) -> str | None:
        index = self.pin_table.currentIndex()
        if not index.isValid():
            return None
        row = self.pin_table.row_at(index)
        return str(row["pin"]) if isinstance(row, dict) else None

    def notes(self) -> list[devices.PinProblem]:
        """The notes shown under the pin table."""
        return list(self._notes)

    def pinout(self) -> Table:
        """The pinout as exported: header row first, as `system/box_pinouts.csv` for this unit."""
        return [list(r) for r in self._pinout]

    def table_bytes(self, fmt: str) -> bytes:
        table = self.pinout()
        stamp = stamp_of(self.ctl.project)
        if fmt == "csv":
            return csv_bytes(table, stamp)
        return exports.xlsx_bytes({strings.DV_PREVIEW: table}, stamp)

    def export_to(self, path: Path) -> Path:
        """Write the pinout as CSV (`.csv`) or an Excel workbook (`.xlsx`)."""
        fmt = "xlsx" if path.suffix.lower() == ".xlsx" else "csv"
        data = self.table_bytes(fmt)
        path = path if path.suffix.lower() in (".csv", ".xlsx") else path.with_suffix("." + fmt)
        path.write_bytes(data)
        return path

    def refresh(self) -> None:
        """Bring everything in line with the project (the pin table keeps its selection)."""
        self._timer.stop()
        self._dirty = False
        self._refresh_units()
        if not self._units:
            self._unit = self._cid = None
            self.stack.setCurrentWidget(self.empty)
            self.empty_add.setEnabled(not self.ctl.read_only)
            self._key = None
            return
        self.stack.setCurrentWidget(self.content)
        if self._unit not in self._units:
            self._unit = self._units[0]
            self._cid = None
        key = (self.ctl.state_token, self._unit, self._cid, self.ctl.read_only)
        if key == self._key:
            return
        self._show_unit_now()
        self._key = (self.ctl.state_token, self._unit, self._cid, self.ctl.read_only)

    # ---- internals ---------------------------------------------------------------------------
    def _invalidate(self) -> None:
        self._dirty = True
        self._key = None
        if self.isVisible():
            self._timer.start()

    def showEvent(self, event: object) -> None:  # noqa: N802
        super().showEvent(event)  # type: ignore[arg-type]
        if self._dirty:
            self.refresh()

    def _read_only_changed(self) -> None:
        self._invalidate()

    def _focus_filter(self) -> None:
        self.pin_filter.setFocus()
        self.pin_filter.selectAll()

    def _refresh_units(self) -> None:
        ids = sorted(self.ctl.project.units, key=natural_key)
        if ids != self._units:
            self._units = ids
            self.selector.blockSignals(True)
            self.selector.clear()
            for uid in ids:
                self.selector.addItem(uid, uid)
            self.selector.blockSignals(False)
        i = self.selector.findData(self._unit)
        if i >= 0 and i != self.selector.currentIndex():
            self.selector.blockSignals(True)
            self.selector.setCurrentIndex(i)
            self.selector.blockSignals(False)

    def _follow_selection(self) -> None:
        """A unit picked on the diagram or in the tree is the device shown."""
        sel = self.ctl.selection
        if (
            sel is not None
            and sel.kind == "unit"
            and sel.id != self._unit
            and sel.id in self.ctl.project.units
        ):
            self._unit, self._cid = sel.id, None
            self._key = None
            self._dirty = True
            if self.isVisible():
                self.refresh()
            self.deviceChanged.emit(sel.id)

    def _selector_changed(self, _i: int) -> None:
        uid = self.selector.currentData()
        if isinstance(uid, str) and uid != self._unit and not self._syncing:
            self._unit, self._cid = uid, None
            self.refresh()
            self.ctl.select("unit", uid)  # (the diagram and the tree follow)
            self.deviceChanged.emit(uid)

    def _show_unit_now(self) -> None:
        p = self.ctl.project
        uid = self._unit or ""
        unit = p.units[uid]
        conns = edit.unit_connectors(p, uid)
        state = devices.device_state(p, uid)
        key, word = _DEVICE_STATE[state.state]
        self.state_chip.set_state(key, word)
        self.state_chip.setToolTip(state.sentence)
        self.name.setText(unit.name)
        self.subsystem.setText(
            f"{strings.DV_SUBSYSTEM.format(unit.subsystem)} · {strings.DV_CHAIN[unit.side]}"
        )
        pins = sum(len(c.pins) for c in conns)
        signals = sum(1 for c in conns for x in c.pins if x.signal)
        self.counts.setText(
            strings.DV_COUNTS.format(
                connectors=plural(strings.DV_N_CONNECTORS, len(conns)),
                pins=plural(strings.DV_N_PINS, pins),
                signals=plural(strings.DV_N_SIGNALS, signals),
                interfaces=plural(strings.DV_N_INTERFACES, len(state.interfaces)),
            )
        )
        self.duplicate_btn.setEnabled(not self.ctl.read_only)
        # connectors
        problems = {c.id: devices.pinout_problems(p, c.id) for c in conns}
        rows = []
        for c in conns:
            lock = devices.pin_set_frozen(p, c.id)
            notes = problems[c.id]
            if lock:
                skey, word, tip = "locked", strings.DV_STATE_LOCKED, lock
            elif notes:
                skey, word = _SEVERITY[notes[0].severity]
                tip = "\n".join(n.message for n in notes[:5])
            else:
                skey, word, tip = None, "", ""
            rows.append(
                {
                    "id": c.id, "name": c.name, "part": c.part_id, "pins": len(c.pins),
                    "state_key": skey, "state": word, "state_tip": tip,
                }
            )  # fmt: skip
        ids = [c.id for c in conns]
        if self._cid not in ids:
            self._cid = ids[0] if ids else None
        self._syncing = True
        try:
            self.conn_model.update_rows(rows)
            self.no_connectors.setVisible(not conns)
            if self._cid is not None:
                self.conn_table.selectRow(ids.index(self._cid))
        finally:
            self._syncing = False
        # the pinout as exported
        self._pinout = devices.pinout_table(p, uid)
        header, body = self._pinout[0], self._pinout[1:]
        self.preview_model.columns = table_columns("pinouts", header, body)
        self.preview_model.set_rows([tuple(r) for r in body])
        self.export_btn.setEnabled(bool(body))
        self._show_connector(problems.get(self._cid or "", []))

    def _show_connector(self, problems: list[devices.PinProblem]) -> None:
        p = self.ctl.project
        cid = self._cid
        if cid is None or cid not in p.connectors:
            self.pin_model.update_rows([])
            self.note_model.update_rows([])
            self._pin_index = {}
            self._notes = []
            for label in self.card_values.values():
                label.setText("")
            self.pin_count.setText("")
            self.note_label.setText("")
            return
        c = p.connectors[cid]
        part = p.parts.get(c.part_id)
        self.card_values["part"].setText(
            f"{c.part_id}" + (f" · {part.description}" if part and part.description else "")
        )
        self.card_values["gender"].setText(strings.DV_GENDER[c.gender])
        self.card_values["keying"].setText(c.keying or strings.DV_CARD_NONE)
        self.card_values["carries"].setText(
            ", ".join(p.interface_types[t].name if t in p.interface_types else t for t in c.carries)
            or strings.DV_CARD_ANY
        )
        fixed = any(x.fixed and x.signal for x in c.pins)
        self.card_values["allocation"].setText(
            strings.DV_ALLOC_FIXED if fixed else strings.DV_ALLOC_AUTO
        )
        frozen = devices.pin_set_frozen(p, cid)
        self.card.setProperty("severity", "info" if frozen else "")
        self.card.style().unpolish(self.card)
        self.card.style().polish(self.card)
        self.card.setToolTip(frozen or "")
        rows = devices.pin_rows(p, cid, problems=problems)
        data = pin_rows_for_table(rows, problems)
        self._pin_index = {r.pin: k for k, r in enumerate(rows)}
        self.pins_caption.setText(strings.DV_PIN_TABLE.format(c.name))
        self.pin_table.setAccessibleName(strings.DV_PIN_TABLE.format(c.id))
        self.pin_model.update_rows(data)
        self._notes = list(problems)
        self.note_model.update_rows(
            [
                {
                    "state_key": _SEVERITY[n.severity][0],
                    "severity": _SEVERITY[n.severity][1],
                    "where": n.pin_id or c.name,
                    "check": n.check,
                    "message": n.message,
                    "pin": n.pin_id,
                }
                for n in problems
            ]
        )
        self.note_label.setText(
            plural(strings.DV_NOTES_COUNT, len(problems)) if problems else strings.DV_NOTES_NONE
        )
        self.note_table.setVisible(bool(problems))
        self._update_pin_count()

    def _update_pin_count(self) -> None:
        shown, total = self.pin_table.proxy.rowCount(), self.pin_model.rowCount()
        self.pin_count.setText(
            strings.DV_PIN_COUNT.format(shown, total)
            if shown != total
            else strings.DV_PIN_COUNT_ALL.format(total)
        )

    def _contact_toggled(self, on: bool) -> None:
        for key in CONTACT_COLUMNS:
            self.pin_table.setColumnHidden(self.pin_model.column_index(key), not on)

    def _connector_current(self, current: QModelIndex, _previous: QModelIndex) -> None:
        if self._syncing or not current.isValid():
            return
        row = self.conn_table.row_at(current)
        cid = row.get("id") if isinstance(row, dict) else None
        if isinstance(cid, str) and cid != self._cid:
            self._cid = cid
            self._key = None
            self.refresh()
            self.connectorChanged.emit(cid)

    def _pin_activated(self, index: QModelIndex) -> None:
        if self._cid is None or not index.isValid():
            return
        row = self.pin_table.row_at(index)
        if isinstance(row, dict):
            self.whyRequested.emit("pin", f"{self._cid}.{row['pin']}")

    def _note_activated(self, index: QModelIndex) -> None:
        row = self.note_table.row_at(index) if index.isValid() else None
        if isinstance(row, dict) and row.get("pin"):
            self.select_pin(str(row["pin"]))
            self.pin_table.setFocus()

    def _duplicate(self) -> None:
        if self._unit is not None:
            self.duplicateRequested.emit(self._unit)

    def _export(self) -> None:
        if self._unit is not None:
            self.exportPinoutRequested.emit(self._unit)
