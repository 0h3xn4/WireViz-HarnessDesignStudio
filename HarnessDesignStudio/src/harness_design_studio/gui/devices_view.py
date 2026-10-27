"""Devices view: one unit with its connectors and pins, edited in place, the pinout as it will be
exported, and the notes the pin checks give. Plugged into the window as the sixth main tab
(`install_view("devices", ...)`, Ctrl+6).

    DevicesView(ctl, theme, settings=None)

* Header: the device (a unit; the unit selected on the diagram or in the tree is the one shown),
  its name, subsystem and chain, its state (Draft, In use, Locked, Read-only), counts, Duplicate
  and Export pinout. A released device shows the lock banner with Start new revision.
* Connector list with an inline "add connector" row (a part picker that searches the library, its
  first entry is New part), connector card (part, gender, keying, what it carries, how its pins are
  allocated) and the pin table (pin, signal, mode, interface, direction, class, wire, state) whose
  cells are edited in place (`devices_pin_table`). Direction and class are worked out from the
  interface type of the pin's signal and are empty, with the reason as tooltip, when nothing can
  be said: nothing is guessed.
* Notes under the pin table (`core.devices.pinout_problems`) and "Pinout as exported": exactly
  the rows of `system/box_pinouts.csv` for this unit.
* Every number and sentence comes from headless code in `core.devices`, and every change goes
  through the controller as one named undo step; this file only asks. A question that needs an
  answer (a part change that resizes the pins, a delete) is asked on a line in the tab, never in a
  message box.
"""

from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from PySide6.QtCore import QItemSelectionModel, QModelIndex, QSettings, Qt, QTimer, Signal
from PySide6.QtGui import QAction, QGuiApplication, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QPushButton,
    QSpinBox,
    QSplitter,
    QStackedWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from harness_design_studio.core import copies, devices, edit
from harness_design_studio.core.edit import EditError
from harness_design_studio.core.links import effective_role
from harness_design_studio.core.model import Project
from harness_design_studio.core.outputs import exports
from harness_design_studio.core.outputs.stamp import Table, csv_bytes, stamp_of
from harness_design_studio.core.vcs.lockview import field_lock_reason
from harness_design_studio.gui import strings
from harness_design_studio.gui.controller import EditorController
from harness_design_studio.gui.devices_pin_table import (
    PinDelegate,
    PinModel,
    PinTable,
    plan_paste,
)
from harness_design_studio.gui.harness_view import REFRESH_DELAY_MS
from harness_design_studio.gui.icons import icon_button, tooltip_text
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
_SIDES = ("nominal", "redundant", "none")
_GENDERS = ("female", "male", "unspecified")
_NEW_PART = "\0new-part"  # the data of the first entry of the part picker


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


def role_cell(stored: str, effective: str) -> str:
    """The Role cell: the role a person gave, or the one taken from the signal name with "(auto)"."""
    if stored:
        return strings.LINK_ROLE_NAMES.get(stored, stored)
    if effective:
        return strings.DV_ROLE_AUTO.format(strings.LINK_ROLE_NAMES.get(effective, effective))
    return ""


def pin_rows_for_table(
    rows: list[devices.PinRow],
    problems: list[devices.PinProblem],
    frozen: str | None = None,
    roles: Mapping[str, tuple[str, str]] | None = None,
) -> list[dict[str, Any]]:
    """The pin table's rows (dicts) for `PIN_COLUMNS`. `roles` maps a pin to (the role a person
    gave, the role it has: given or taken from the signal name)."""
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
                "role": role_cell(*(roles or {}).get(r.pin, ("", ""))),
                "role_key": (roles or {}).get(r.pin, ("", ""))[0],
                "mode": strings.DV_MODE[r.mode],
                "mode_key": r.mode,
                "mode_tip": strings.DV_MODE_TIP[r.mode],
                "interface": r.interface_id,
                "direction": r.direction,
                "class": r.category,
                "meaning_tip": r.note,
                "wire": ";".join(r.wires),
                "function": r.function,
                "contact_size": r.contact_size,
                "termination": strings.DV_TERMINATION[r.termination],
                "termination_key": r.termination,
                "contact_part": r.contact_part,
                "state_key": key,
                "state": word,
                "state_tip": tip,
                "lock": r.lock or "",
                "pin_frozen": frozen or "",
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
    Column("role", strings.DV_COL_ROLE, tooltip=lambda _r: strings.DV_COL_ROLE_TIP, width=96),
    Column("mode", strings.DV_COL_MODE, tooltip=_tip("mode_tip"), width=64),
    Column("interface", strings.DV_COL_INTERFACE, mono=True, width=80),
    Column("direction", strings.DV_COL_DIRECTION, tooltip=_tip("meaning_tip"), width=76),
    Column("class", strings.DV_COL_CLASS, tooltip=_tip("meaning_tip"), width=76),
    Column("wire", strings.DV_COL_WIRE, mono=True, width=96),
    Column("contact_size", strings.DV_COL_CONTACT_SIZE, mono=True, width=96),
    Column("termination", strings.DV_COL_TERMINATION, width=96),
    Column(
        "contact_part", strings.DV_COL_CONTACT_PART, mono=True, width=120,
        tooltip=lambda _r: strings.DV_COL_CONTACT_PART_TIP,
    ),
    Column("function", strings.DV_COL_FUNCTION, width=140),
    Column(
        "state", strings.DV_COL_STATE, state=lambda r: _field(r, "state_key"), tooltip=_tip("state_tip"),
        width=130,
    ),
]  # fmt: skip
CONTACT_COLUMNS = ("contact_size", "termination", "contact_part")

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

    Signals (the window runs the flows): `addRequested()` (the empty state's button),
    `duplicateRequested(unit_id)`, `exportPinoutRequested(unit_id)` (the window asks for a file
    name and calls `export_to`), `whyRequested(kind, id)` for a pin ("pin", "connector.pin"),
    `reviseRequested(harness_id)`, `fillRequested(connector_id, pins)`, `contactRequested(connector_id, pins)`,
    `assignRequested(connector_id, pins)`, `newPartRequested()`, `newTypeRequested()`,
    `deviceChanged(unit_id)` and `connectorChanged(connector_id)`.
    """

    addRequested = Signal()
    duplicateRequested = Signal(str)
    exportPinoutRequested = Signal(str)
    saveToLibraryRequested = Signal(str)
    addFromLibraryRequested = Signal()
    whyRequested = Signal(str, str)
    reviseRequested = Signal(str)
    fillRequested = Signal(str, list)
    contactRequested = Signal(str, list)
    assignRequested = Signal(str, list)
    newPartRequested = Signal()
    newTypeRequested = Signal()
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
        self._want_pin: str | None = None  # the pin to select when the table next changes
        self._want_connector: str | None = None
        self._confirm: Callable[[list[bool]], None] | None = None
        self._frozen: str | None = None
        self._suggestion: list[str] = []
        self._banner_harness: str | None = None
        self._adding = False
        self._acting = False
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
        self._build_banner(theme)
        c.addWidget(self.banner)
        c.addWidget(self.confirm_bar)
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
        dup = QShortcut(QKeySequence("Ctrl+D"), self)
        dup.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        dup.activated.connect(self._duplicate)

        ctl.message.connect(self._on_message)
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
        icon_button(
            self.empty_add, "plus", theme, strings.DV_ADD_TIP, "Ctrl+Shift+N", text=strings.DV_ADD
        )
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
        self.name = QLineEdit()
        self.name.setObjectName("devices-name")
        self.name.setAccessibleName(strings.DV_NAME)
        self.name.setToolTip(strings.DV_NAME_TIP)
        self.name.setProperty("title", True)
        self.name.editingFinished.connect(self._name_edited)
        self.subsystem = QComboBox()
        self.subsystem.setObjectName("devices-subsystem")
        self.subsystem.setEditable(True)
        self.subsystem.setAccessibleName(strings.DV_SUBSYSTEM_LABEL)
        self.subsystem.setToolTip(strings.DV_SUBSYSTEM_TIP)
        self.subsystem.setMinimumWidth(theme.px(120))
        line = self.subsystem.lineEdit()
        if line is not None:
            line.editingFinished.connect(self._subsystem_edited)
        self.subsystem.activated.connect(lambda _i: self._subsystem_edited())
        self.chain = QComboBox()
        self.chain.setObjectName("devices-chain")
        self.chain.setAccessibleName(strings.DV_CHAIN_LABEL)
        self.chain.setToolTip(strings.DV_CHAIN_TIP)
        for side in _SIDES:
            self.chain.addItem(strings.DV_CHAIN[side], side)
        self.chain.activated.connect(self._chain_edited)
        row1.addWidget(self.selector)
        row1.addWidget(self.state_chip)
        row1.addWidget(self.name, 1)
        row1.addWidget(QLabel(strings.DV_SUBSYSTEM_LABEL))
        row1.addWidget(self.subsystem)
        row1.addWidget(self.chain)
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
        self.lib_save_btn = QPushButton()
        self.lib_save_btn.setObjectName("devices-library-save")
        icon_button(
            self.lib_save_btn, "export", theme, strings.DV_LIB_SAVE_TIP, text=strings.DV_LIB_SAVE
        )
        self.lib_save_btn.clicked.connect(self._save_to_library)
        self.lib_add_btn = QPushButton()
        self.lib_add_btn.setObjectName("devices-library-add")
        icon_button(
            self.lib_add_btn, "unit", theme, strings.DV_LIB_ADD_TIP, text=strings.DV_LIB_ADD
        )
        self.lib_add_btn.clicked.connect(self.addFromLibraryRequested.emit)
        self.number = QSpinBox()
        self.number.setObjectName("devices-number")
        self.number.setAccessibleName(strings.DV_NUMBER)
        self.number.setToolTip(strings.DV_NUMBER_TIP)
        self.number.setRange(1, copies.MAX_DEVICES)
        self.number.valueChanged.connect(self._number_changed)
        self.copies_btn = QPushButton()
        self.copies_btn.setObjectName("devices-copies")
        icon_button(self.copies_btn, "plus", theme, strings.DV_COPIES_TIP, text=strings.DV_COPIES)
        self.copies_btn.clicked.connect(self._make_copies)
        row2.addWidget(self.counts, 1)
        row2.addWidget(self.lib_add_btn)
        row2.addWidget(self.lib_save_btn)
        row2.addWidget(self.duplicate_btn)
        row2.addWidget(self.export_btn)
        box.addLayout(row2)
        row3 = QHBoxLayout()  # the number of these devices (a row of its own keeps the tab narrow)
        row3.addWidget(QLabel(strings.DV_NUMBER))
        row3.addWidget(self.number)
        row3.addWidget(self.copies_btn)
        row3.addStretch(1)
        box.addLayout(row3)
        return box

    def _build_banner(self, theme: ThemeManager) -> None:
        """The lock banner (a released device, a read-only project) and the question line."""
        self.banner = QFrame()
        self.banner.setObjectName("devices-banner")
        self.banner.setProperty("banner", True)
        bl = QHBoxLayout(self.banner)
        self.banner_text = QLabel()
        self.banner_text.setObjectName("devices-banner-text")
        self.banner_text.setWordWrap(True)
        self.banner_btn = QPushButton()
        self.banner_btn.setObjectName("devices-revise")
        icon_button(self.banner_btn, "revise", theme, strings.DV_REVISE_TIP, text=strings.DV_REVISE)
        self.banner_btn.clicked.connect(self._revise)
        bl.addWidget(self.banner_text, 1)
        bl.addWidget(self.banner_btn)
        self.banner.hide()

        self.confirm_bar = QFrame()
        self.confirm_bar.setObjectName("devices-confirm")
        self.confirm_bar.setProperty("banner", True)
        self.confirm_bar.setProperty("severity", "info")
        cl = QHBoxLayout(self.confirm_bar)
        self.confirm_text = QLabel()
        self.confirm_text.setObjectName("devices-confirm-text")
        self.confirm_text.setWordWrap(True)
        self.confirm_checks: list[QCheckBox] = []
        self.confirm_checks_box = QHBoxLayout()
        self.confirm_ok = QPushButton()
        self.confirm_ok.setObjectName("devices-confirm-ok")
        self.confirm_ok.setProperty("primary", True)
        self.confirm_ok.clicked.connect(self._confirmed)
        self.confirm_cancel = QPushButton(strings.CANCEL)
        self.confirm_cancel.setObjectName("devices-confirm-cancel")
        self.confirm_cancel.setAccessibleName(strings.CANCEL)
        self.confirm_cancel.setToolTip(f"{strings.CANCEL} (Esc)")
        self.confirm_cancel.clicked.connect(self.cancel_confirm)
        cl.addWidget(self.confirm_text, 1)
        cl.addLayout(self.confirm_checks_box)
        cl.addWidget(self.confirm_ok)
        cl.addWidget(self.confirm_cancel)
        self.confirm_bar.hide()
        esc = QShortcut(QKeySequence("Esc"), self.confirm_bar)
        esc.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        esc.activated.connect(self.cancel_confirm)

    @staticmethod
    def _caption(text: str) -> QLabel:
        label = QLabel(text)
        label.setProperty("heading", True)
        return label

    def _build_connectors(self, theme: ThemeManager) -> None:
        left = QWidget()
        left.setObjectName("devices-left")
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
        for sc in self.conn_table.findChildren(QShortcut):
            if sc.key() == QKeySequence("Ctrl+Shift+C"):
                sc.setEnabled(
                    False
                )  # here the key adds a connector; the pin table keeps "copy with header"
        sm = self.conn_table.selectionModel()
        if sm is not None:
            sm.currentChanged.connect(self._connector_current)
        ll.addWidget(self.conn_table, 1)
        self.no_connectors = QLabel(strings.DV_NO_CONNECTORS)
        self.no_connectors.setObjectName("devices-no-connectors")
        self.no_connectors.setProperty("muted", True)
        self.no_connectors.setWordWrap(True)
        ll.addWidget(self.no_connectors)
        self.part_picker = QComboBox()
        self.part_picker.setObjectName("devices-part-picker")
        self.part_picker.setEditable(True)
        self.part_picker.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.part_picker.setAccessibleName(strings.DV_PART_PICKER)
        self.part_picker.setToolTip(strings.DV_PART_PICKER_TIP)
        ll.addWidget(self.part_picker)
        self.add_connector_btn = QPushButton()
        self.add_connector_btn.setObjectName("devices-add-connector")
        icon_button(
            self.add_connector_btn, "plus", theme, strings.DV_ADD_CONNECTOR_TIP, "Ctrl+Shift+C",
            text=strings.DV_ADD_CONNECTOR,
        )  # fmt: skip
        self.add_connector_btn.clicked.connect(self._add_connector)
        self.delete_connector_btn = QPushButton()
        self.delete_connector_btn.setObjectName("devices-delete-connector")
        icon_button(
            self.delete_connector_btn, "close", theme, strings.DV_DELETE_CONNECTOR_TIP,
            text=strings.DV_DELETE_CONNECTOR,
        )  # fmt: skip
        self.delete_connector_btn.clicked.connect(self._delete_connector)
        row2 = QHBoxLayout()
        row2.addWidget(self.add_connector_btn)
        row2.addWidget(self.delete_connector_btn)
        ll.addLayout(row2)
        self.part_picker.activated.connect(self._part_picked)
        line = self.part_picker.lineEdit()
        if line is not None:
            line.returnPressed.connect(self._return_in_picker)
        sc = QShortcut(QKeySequence("Ctrl+Shift+C"), left)
        sc.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        sc.activated.connect(self._focus_part_picker)
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

        def caption(text: str) -> QLabel:
            label = QLabel(text)
            label.setProperty("muted", True)
            return label

        def value(key: str) -> QLabel:
            label = QLabel()
            label.setObjectName(f"devices-card-{key}")
            label.setWordWrap(True)
            label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            self.card_values[key] = label
            return label

        top = Qt.AlignmentFlag.AlignTop
        self.part_edit = QComboBox()
        self.part_edit.setObjectName("devices-card-part-edit")
        self.part_edit.setAccessibleName(strings.DV_CARD_PART)
        self.part_edit.setMinimumWidth(theme.px(200))
        self.part_edit.setToolTip(strings.DV_CARD_PART_TIP)
        self.part_edit.activated.connect(self._part_chosen)
        part_box = QHBoxLayout()
        part_box.addWidget(self.part_edit)
        part_box.addWidget(value("part"), 1)
        grid.addWidget(caption(strings.DV_CARD_PART), 0, 0, top)
        grid.addLayout(part_box, 0, 1)
        self.gender_edit = QComboBox()
        self.gender_edit.setObjectName("devices-card-gender-edit")
        self.gender_edit.setAccessibleName(strings.DV_CARD_GENDER)
        self.gender_edit.setToolTip(strings.DV_CARD_GENDER_TIP)
        for g in _GENDERS:
            self.gender_edit.addItem(strings.DV_GENDER[g], g)
        self.gender_edit.activated.connect(self._gender_chosen)
        self.keying_edit = QLineEdit()
        self.keying_edit.setObjectName("devices-card-keying-edit")
        self.keying_edit.setAccessibleName(strings.DV_CARD_KEYING)
        self.keying_edit.setToolTip(strings.DV_CARD_KEYING_TIP)
        self.keying_edit.setPlaceholderText(strings.DV_CARD_NONE)
        self.keying_edit.editingFinished.connect(self._keying_edited)
        gender_box = QHBoxLayout()
        gender_box.addWidget(self.gender_edit)
        gender_box.addWidget(caption(strings.DV_CARD_KEYING))
        gender_box.addWidget(self.keying_edit, 1)
        grid.addWidget(caption(strings.DV_CARD_GENDER), 1, 0, top)
        grid.addLayout(gender_box, 1, 1)
        self.carries_btn = QToolButton()
        self.carries_btn.setObjectName("devices-card-carries-edit")
        self.carries_btn.setText(strings.DV_CARRIES_EDIT)
        self.carries_btn.setAccessibleName(strings.DV_CARRIES_EDIT)
        self.carries_btn.setToolTip(strings.DV_CARRIES_TIP)
        self.carries_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.carries_menu = QMenu(self.carries_btn)
        self.carries_btn.setMenu(self.carries_menu)
        self.carries_suggest = QPushButton()
        self.carries_suggest.setObjectName("devices-card-carries-suggest")
        self.carries_suggest.clicked.connect(self._use_suggestion)
        carries_box = QHBoxLayout()
        carries_box.addWidget(value("carries"), 1)
        carries_box.addWidget(self.carries_suggest)
        carries_box.addWidget(self.carries_btn)
        grid.addWidget(caption(strings.DV_CARD_CARRIES), 2, 0, top)
        grid.addLayout(carries_box, 2, 1)
        grid.addWidget(caption(strings.DV_CARD_ALLOCATION), 3, 0, top)
        grid.addWidget(value("allocation"), 3, 1)
        self.label_edit = QLineEdit()
        self.label_edit.setObjectName("devices-card-label-edit")
        self.label_edit.setAccessibleName(strings.DV_CARD_LABEL)
        self.label_edit.setToolTip(strings.DV_CARD_LABEL_TIP)
        self.label_edit.setPlaceholderText(strings.DV_CARD_NONE)
        self.label_edit.editingFinished.connect(self._label_edited)
        grid.addWidget(caption(strings.DV_CARD_LABEL), 4, 0, top)
        grid.addWidget(self.label_edit, 4, 1)
        grid.setColumnStretch(1, 1)
        rl.addWidget(self.card)

        bar = QHBoxLayout()
        self.pins_caption = self._caption(strings.DV_PINS)
        bar.addWidget(self.pins_caption)
        bar.addStretch(1)
        self.pin_buttons: dict[str, QPushButton] = {}
        for key, icon_name, text, tip, shortcut, slot in (
            ("add", "plus", strings.DV_ADD_PIN, strings.DV_ADD_PIN_TIP, "Insert", self._insert_pin),
            ("delete", "close", strings.DV_DELETE_PINS, strings.DV_DELETE_PINS_TIP, "Shift+Delete", self._request_delete_pins),
            ("fill", "interface-type", strings.DV_FILL, strings.DV_FILL_TIP, "Ctrl+L", self._request_fill),
            ("assign", "interface", strings.DV_ASSIGN, strings.DV_ASSIGN_TIP, "Ctrl+Enter", self._request_assign),
            ("contact", "part", None, strings.DV_CONTACT_BULK_TIP, None, self._request_contact),  # (icon only)
        ):  # fmt: skip
            b = QPushButton()
            b.setObjectName(f"devices-pin-{key}")
            icon_button(b, icon_name, theme, tip, shortcut, text=text)
            b.clicked.connect(lambda _c=False, f=slot: f())
            self.pin_buttons[key] = b
            bar.addWidget(b)
        self.pin_filter = QLineEdit()
        self.pin_filter.setObjectName("devices-pin-filter")
        self.pin_filter.setPlaceholderText(strings.DV_PIN_FILTER)
        self.pin_filter.setAccessibleName(strings.DV_PIN_FILTER)
        self.pin_filter.setToolTip(f"{strings.DV_PIN_FILTER_TIP} (Ctrl+F)")
        self.pin_filter.setClearButtonEnabled(True)
        self.pin_filter.setMaximumWidth(theme.px(160))
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
        self.pin_model = PinModel(PIN_COLUMNS, (), self.theme)
        self.pin_table = PinTable(
            self.pin_model, self.theme, name=strings.DV_PINS, settings=self.settings,
            key="devices-pins",
        )  # fmt: skip
        self.pin_table.setObjectName("devices-pin-table")
        self.pin_table.setItemDelegate(
            PinDelegate(
                self.theme,
                self._signal_choices,
                self._validate_cell,
                self._show_error,
                self.pin_table,
                contacts=lambda: devices.contact_part_choices(self.ctl.project),
            )
        )
        self.pin_table.activated.connect(self._pin_activated)
        self.pin_model.cellEdited.connect(self._cell_edited)
        self.pin_table.insertRequested.connect(self._insert_pin)
        self.pin_table.deleteRequested.connect(self._request_delete_pins)
        self.pin_table.clearRequested.connect(self._clear_signals)
        self.pin_table.cycleModeRequested.connect(self._cycle_mode)
        self.pin_table.fillRequested.connect(self._request_fill)
        self.pin_table.assignRequested.connect(self._request_assign)
        self.pin_table.pasteRequested.connect(self._paste)
        self.pin_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.pin_table.customContextMenuRequested.connect(self._pin_menu)
        rl.addWidget(self.pin_table, 1)
        self.edit_error = QLabel()
        self.edit_error.setObjectName("devices-edit-error")
        self.edit_error.setProperty("error", True)
        self.edit_error.setWordWrap(True)
        self.edit_error.hide()
        rl.addWidget(self.edit_error)
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
        self.note_table.setMaximumHeight(theme.px(96))
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
        self._key = None
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

    def _reselect(self, current: str, pins: list[str]) -> None:
        """Select these pins again after the rows were replaced (the cursor on `current`)."""
        sm = self.pin_table.selectionModel()
        if sm is None:
            return
        flags = QItemSelectionModel.SelectionFlag.Select | QItemSelectionModel.SelectionFlag.Rows
        sm.clearSelection()
        for pid in pins:
            row = self._pin_index.get(pid)
            if row is not None:
                sm.select(self.pin_table.proxy.mapFromSource(self.pin_model.index(row, 0)), flags)
        row = self._pin_index[current]
        sm.setCurrentIndex(
            self.pin_table.proxy.mapFromSource(self.pin_model.index(row, 0)),
            QItemSelectionModel.SelectionFlag.NoUpdate,
        )

    def current_pin(self) -> str | None:
        index = self.pin_table.currentIndex()
        if not index.isValid():
            return None
        row = self.pin_table.row_at(index)
        return str(row["pin"]) if isinstance(row, dict) else None

    def selected_pins(self) -> list[str]:
        """The pins of the selected rows, in the order of the table; the current pin when no row
        is selected."""
        rows = self.pin_table.selected_rows()
        pins = [str(r["pin"]) for r in rows if isinstance(r, dict)]
        if not pins and (cur := self.current_pin()):
            pins = [cur]
        return pins

    def current_column(self) -> str | None:
        index = self.pin_table.currentIndex()
        if not index.isValid():
            return None
        return str(self.pin_model.columns[self.pin_table.proxy.mapToSource(index).column()].key)

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

    def focus_name(self) -> None:
        """Put the keyboard in the name of the device, selected (a new device is named first)."""
        self.name.setFocus()
        self.name.selectAll()

    def select_part(self, part_id: str) -> None:
        """Choose a part in the picker of the add-connector row (after New part)."""
        self._fill_parts()
        i = self.part_picker.findData(part_id)
        if i >= 0:
            self.part_picker.setCurrentIndex(i)
            self.part_picker.setFocus()

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

    # ---- internals: following the project ------------------------------------------------------
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

    def _focus_part_picker(self) -> None:
        self.part_picker.setFocus()
        line = self.part_picker.lineEdit()
        if line is not None:
            line.selectAll()

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
            self.cancel_confirm()
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
        ro = self.ctl.read_only
        self._syncing = True
        try:
            if not self.name.hasFocus():
                self.name.setText(unit.name)
            self._fill_subsystems(unit.subsystem)
            self.chain.setCurrentIndex(max(0, self.chain.findData(unit.side)))
        finally:
            self._syncing = False
        # the design fields of a released device stay as they are, with the reason
        design_lock = field_lock_reason(p, "unit", uid, "subsystem")
        self.subsystem.setEnabled(not ro and not design_lock)
        self.chain.setEnabled(not ro and not design_lock)
        self.name.setEnabled(not ro)
        self.subsystem.setToolTip(design_lock or strings.DV_SUBSYSTEM_TIP)
        self.chain.setToolTip(design_lock or strings.DV_CHAIN_TIP)
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
        self.duplicate_btn.setEnabled(not ro)
        self._show_number(p, uid, ro)
        self._banner_for(state)
        self._fill_parts()
        self.part_picker.setEnabled(not ro)
        self.add_connector_btn.setEnabled(not ro)
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
        if self._want_connector in ids:
            self._cid, self._want_connector = self._want_connector, None
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
        self.delete_connector_btn.setEnabled(bool(conns) and not ro)
        # the pinout as exported
        self._pinout = devices.pinout_table(p, uid)
        header, body = self._pinout[0], self._pinout[1:]
        self.preview_model.columns = table_columns("pinouts", header, body)
        self.preview_model.set_rows([tuple(r) for r in body])
        self.export_btn.setEnabled(bool(body))
        self._show_connector(problems.get(self._cid or "", []))

    def _show_number(self, p: Project, uid: str, ro: bool) -> None:
        """The number of these devices the project has; a copy has none of its own."""
        have = copies.device_count(p, uid)
        is_copy = copies.is_copy(p, uid)
        self.number.blockSignals(True)
        try:
            if not self.number.hasFocus() or is_copy:
                self.number.setValue(max(1, have))
        finally:
            self.number.blockSignals(False)
        self.number.setEnabled(not ro and not is_copy)
        self.number.setToolTip(strings.DV_NUMBER_COPY if is_copy else strings.DV_NUMBER_TIP)
        self._number_changed()

    def _number_changed(self, _value: int = 0) -> None:
        p = self.ctl.project
        uid = self._unit
        if uid is None or uid not in p.units:
            self.copies_btn.setEnabled(False)
            return
        more = self.number.value() > copies.device_count(p, uid)
        self.copies_btn.setEnabled(more and self.number.isEnabled() and not self.ctl.read_only)
        self.copies_btn.setToolTip(strings.DV_COPIES_TIP if more else strings.DV_COPIES_SAME)

    def _make_copies(self) -> None:
        uid = self._unit
        if uid is not None and self.ctl.make_copies(uid, self.number.value()):
            self._show_number(self.ctl.project, uid, self.ctl.read_only)

    def _fill_subsystems(self, current: str) -> None:
        names = sorted({u.subsystem for u in self.ctl.project.units.values()} | {current})
        have = [self.subsystem.itemText(i) for i in range(self.subsystem.count())]
        if have != names:
            self.subsystem.clear()
            self.subsystem.addItems(names)
        if not self.subsystem.hasFocus():
            self.subsystem.setCurrentText(current)

    def _fill_parts(self) -> None:
        """The part pickers: connector parts of the library; the first entry of the add row is
        New part."""
        parts = sorted(
            (p for p in self.ctl.project.parts.values() if p.category == "connector"),
            key=lambda p: natural_key(p.id),
        )
        labels = [
            (p.id, f"{p.id} · {plural(strings.DV_N_PINS, p.pin_count)}" if p.pin_count else p.id)
            for p in parts
        ]
        for box, new in ((self.part_picker, True), (self.part_edit, False)):
            want = ([(_NEW_PART, strings.DV_NEW_PART)] if new else []) + labels
            have = [(str(box.itemData(i)), box.itemText(i)) for i in range(box.count())]
            if have != want:
                keep = box.currentData()
                box.blockSignals(True)
                box.clear()
                for data, text in want:
                    box.addItem(text, data)
                idx = box.findData(keep) if keep is not None else -1
                box.setCurrentIndex(idx if idx >= 0 else (1 if new and len(want) > 1 else 0))
                box.blockSignals(False)
        comp = self.part_picker.completer()
        if comp is not None:
            comp.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
            comp.setFilterMode(Qt.MatchFlag.MatchContains)

    def _banner_for(self, state: devices.DeviceState) -> None:
        ro = self.ctl.read_only
        hid = state.released_by[0].harness_id if state.released_by else None
        self._banner_harness = hid
        if ro:
            self.banner.setProperty("severity", "warning")
            self.banner_text.setText(strings.DV_READ_ONLY_BANNER)
            self.banner_btn.hide()
            self.banner.show()
        elif state.state == "locked" and hid:
            self.banner.setProperty("severity", "info")
            self.banner_text.setText(state.sentence)
            self.banner_btn.show()
            self.banner_btn.setToolTip(strings.DV_REVISE_TIP_FOR.format(hid))
            self.banner.show()
        else:
            self.banner.hide()
        style = self.banner.style()
        style.unpolish(self.banner)
        style.polish(self.banner)

    def _show_connector(self, problems: list[devices.PinProblem]) -> None:
        p = self.ctl.project
        cid = self._cid
        keep_pin = self._want_pin or self.current_pin()
        kept = [] if self._want_pin else self.selected_pins()
        self._want_pin = None
        ro = self.ctl.read_only
        self.pin_model.read_only = ro
        for b in self.pin_buttons.values():
            b.setEnabled(cid is not None and not ro)
        if cid is None or cid not in p.connectors:
            for w in (
                self.part_edit,
                self.gender_edit,
                self.keying_edit,
                self.carries_btn,
                self.label_edit,
            ):
                w.setEnabled(False)
            self.carries_suggest.hide()
            self.pin_model.update_rows([])
            self.note_model.update_rows([])
            self._pin_index = {}
            self._notes = []
            self._frozen = None
            for label in self.card_values.values():
                label.setText("")
            self.keying_edit.setText("")
            self.label_edit.setText("")
            self.pin_count.setText("")
            self.note_label.setText("")
            return
        c = p.connectors[cid]
        part = p.parts.get(c.part_id)
        frozen = devices.pin_set_frozen(p, cid)
        self._frozen = frozen
        self._syncing = True
        try:
            self.part_edit.setCurrentIndex(max(0, self.part_edit.findData(c.part_id)))
            self.gender_edit.setCurrentIndex(max(0, self.gender_edit.findData(c.gender)))
            if not self.keying_edit.hasFocus():
                self.keying_edit.setText(c.keying or "")
            if not self.label_edit.hasFocus():
                self.label_edit.setText(c.label or "")
        finally:
            self._syncing = False
        for w in (self.part_edit, self.gender_edit, self.keying_edit):
            w.setEnabled(not ro and not frozen)
        self.carries_btn.setEnabled(not ro)
        self.label_edit.setEnabled(not ro)  # a label is not part of the design the release locks
        self.part_edit.setToolTip(frozen or strings.DV_CARD_PART_TIP)
        self.gender_edit.setToolTip(frozen or strings.DV_CARD_GENDER_TIP)
        self.keying_edit.setToolTip(frozen or strings.DV_CARD_KEYING_TIP)
        self.card_values["part"].setText(part.description if part and part.description else "")
        self.card_values["carries"].setText(
            ", ".join(p.interface_types[t].name if t in p.interface_types else t for t in c.carries)
            or strings.DV_CARD_ANY
        )
        self._fill_carries_menu(c.carries)
        self._suggestion = [t for t in devices.suggest_carries(p, cid) if t not in c.carries]
        self.carries_suggest.setVisible(bool(self._suggestion) and not ro)
        if self._suggestion:
            names = ", ".join(p.interface_types[t].name for t in self._suggestion)
            self.carries_suggest.setText(strings.DV_CARRIES_SUGGEST.format(names))
            self.carries_suggest.setAccessibleName(strings.DV_CARRIES_SUGGEST.format(names))
            self.carries_suggest.setToolTip(strings.DV_CARRIES_SUGGEST_TIP)
        fixed = any(x.fixed and x.signal for x in c.pins)
        self.card_values["allocation"].setText(
            strings.DV_ALLOC_FIXED if fixed else strings.DV_ALLOC_AUTO
        )
        self.card.setProperty("severity", "info" if frozen else "")
        self.card.style().unpolish(self.card)
        self.card.style().polish(self.card)
        self.card.setToolTip(frozen or "")
        rows = devices.pin_rows(p, cid, problems=problems)
        roles = {x.id: (x.role, effective_role(x, p, c)) for x in c.pins}
        data = pin_rows_for_table(rows, problems, frozen, roles)
        self._pin_index = {r.pin: k for k, r in enumerate(rows)}
        self.pins_caption.setText(strings.DV_PIN_TABLE.format(c.name))
        self.pin_table.setAccessibleName(strings.DV_PIN_TABLE.format(c.id))
        for key in ("add", "delete"):
            self.pin_buttons[key].setEnabled(not ro and not frozen)
            base, keys = (
                (strings.DV_ADD_PIN_TIP, "Insert")
                if key == "add"
                else (strings.DV_DELETE_PINS_TIP, "Shift+Delete")
            )
            self.pin_buttons[key].setToolTip(frozen or tooltip_text(base, keys))
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
        if keep_pin is not None and keep_pin in self._pin_index:
            if len(kept) > 1 and keep_pin in kept:
                self._reselect(keep_pin, kept)
            else:
                self.select_pin(keep_pin)

    def _fill_carries_menu(self, carried: list[str]) -> None:
        self.carries_menu.clear()
        types = sorted(
            self.ctl.project.interface_types.values(), key=lambda x: (x.name.casefold(), x.id)
        )
        for t in types:
            act = QAction(t.name, self.carries_menu)
            act.setCheckable(True)
            act.setChecked(t.id in carried)
            act.setData(t.id)
            act.setToolTip(t.id)
            act.toggled.connect(lambda _on: self._carries_toggled())
            self.carries_menu.addAction(act)
        self.carries_menu.addSeparator()
        new = QAction(strings.DV_NEW_TYPE_MENU, self.carries_menu)
        new.triggered.connect(self.newTypeRequested)
        self.carries_menu.addAction(new)

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
        self.pin_buttons["contact"].setVisible(on)  # (the bar has no room for it otherwise)

    def _connector_current(self, current: QModelIndex, _previous: QModelIndex) -> None:
        if self._syncing or not current.isValid():
            return
        row = self.conn_table.row_at(current)
        cid = row.get("id") if isinstance(row, dict) else None
        if isinstance(cid, str) and cid != self._cid:
            self._cid = cid
            self._key = None
            self.cancel_confirm()
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
        if self._unit is not None and not self.ctl.read_only:
            self.duplicateRequested.emit(self._unit)

    def _export(self) -> None:
        if self._unit is not None:
            self.exportPinoutRequested.emit(self._unit)

    def _save_to_library(self) -> None:
        if self._unit is not None:
            self.saveToLibraryRequested.emit(self._unit)

    def _revise(self) -> None:
        if self._banner_harness is not None:
            self.reviseRequested.emit(self._banner_harness)

    # ---- internals: asking a question on a line of the tab -------------------------------------
    def ask(
        self,
        text: str,
        ok: str,
        apply: Callable[[list[bool]], None],
        checks: tuple[tuple[str, bool], ...] = (),
    ) -> None:
        """Show a question with the options as check boxes and Apply/Cancel; `apply` gets the
        state of each check box. Esc or Cancel drops it. Nothing happens until Apply."""
        self.cancel_confirm()
        self.confirm_text.setText(text)
        self.confirm_ok.setText(ok)
        self.confirm_ok.setAccessibleName(ok)
        self.confirm_ok.setToolTip(ok)
        for label, on in checks:
            box = QCheckBox(label)
            box.setChecked(on)
            box.setAccessibleName(label)
            box.setToolTip(label)
            self.confirm_checks.append(box)
            self.confirm_checks_box.addWidget(box)
        self._confirm = apply
        self.confirm_bar.show()
        self.confirm_ok.setFocus()

    def cancel_confirm(self) -> None:
        for box in self.confirm_checks:
            self.confirm_checks_box.removeWidget(box)
            box.deleteLater()
        self.confirm_checks = []
        self._confirm = None
        self.confirm_bar.hide()

    def _confirmed(self) -> None:
        apply, states = self._confirm, [b.isChecked() for b in self.confirm_checks]
        self.cancel_confirm()
        if apply is not None:
            apply(states)

    def _do(self, method: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        """Run a controller action for this tab: when it is refused, the sentence is shown on the
        tab (under the table) as well as in the status line."""
        self._acting = True
        try:
            return method(*args, **kwargs)
        finally:
            self._acting = False

    def _on_message(self, text: str, offer_undo: bool) -> None:
        if self._acting and not offer_undo:
            self._show_error(text)

    def _show_error(self, message: str) -> None:
        self.edit_error.setText(message)
        self.edit_error.setVisible(bool(message))

    def _reload(self) -> None:
        """Show the project's values again (after a change that was refused)."""
        self._key = None
        self._invalidate()

    # ---- internals: editing the header ---------------------------------------------------------
    def _name_edited(self) -> None:
        if self._syncing or self._unit is None or self._unit not in self.ctl.project.units:
            return  # (the device is gone: for example the add was undone while the name had focus)
        text = self.name.text().strip()
        if text != self.ctl.project.units[self._unit].name:
            if self._do(self.ctl.update_device, self._unit, name=text):
                self._reload()
            else:
                self.name.setText(self.ctl.project.units[self._unit].name)

    def _subsystem_edited(self) -> None:
        if self._syncing or self._unit is None or self._unit not in self.ctl.project.units:
            return
        text = self.subsystem.currentText().strip()
        if text != self.ctl.project.units[self._unit].subsystem and not self._do(
            self.ctl.update_device, self._unit, subsystem=text
        ):
            self._reload()

    def _chain_edited(self, _i: int) -> None:
        if self._syncing or self._unit is None:
            return
        side = self.chain.currentData()
        if side != self.ctl.project.units[self._unit].side and not self._do(
            self.ctl.update_device, self._unit, side=side
        ):
            self._reload()

    # ---- internals: connectors -----------------------------------------------------------------
    def _part_picked(self, _i: int) -> None:
        if self.part_picker.currentData() == _NEW_PART:
            self.newPartRequested.emit()

    def _add_connector(self) -> None:
        if self._unit is None or self.ctl.read_only:
            return
        part = self.part_picker.currentData()
        if part == _NEW_PART:
            self.newPartRequested.emit()
            return
        text = self.part_picker.currentText().strip()
        if not part and text:  # typed: an ID, or the start of one
            hit = self.part_picker.findText(text, Qt.MatchFlag.MatchStartsWith)
            part = self.part_picker.itemData(hit) if hit >= 0 else text
        if not isinstance(part, str) or not part:
            self._show_error(strings.DV_PICK_PART)
            return
        cid = self._do(self.ctl.add_connector, self._unit, part)
        if cid:
            self._show_error("")
            self._want_connector = cid
            self._reload()
            self.refresh()
            self.connectorChanged.emit(cid)

    def _return_in_picker(self) -> None:
        """Enter in the part picker adds the connector (Qt reports Return in an editable combo
        box twice for one key press; the second is ignored)."""
        if self._adding:
            return
        self._adding = True
        QTimer.singleShot(0, lambda: setattr(self, "_adding", False))
        self._add_connector()

    def _delete_connector(self) -> None:
        cid = self._cid
        if cid is None:
            return
        impact = devices.connector_delete_impact(self.ctl.project, cid)
        if impact.frozen:
            self._show_error(impact.frozen)
            return
        if impact.blocked_by_harnesses:
            self._show_error(
                strings.DV_DELETE_BLOCKED.format(cid, ", ".join(impact.blocked_by_harnesses))
            )
            return
        parts = [strings.DV_DELETE_CONNECTOR_Q.format(cid)]
        if impact.interfaces:
            parts.append(strings.DV_DELETE_CONNECTOR_IFS.format(", ".join(impact.interfaces)))
        if impact.outdated_harnesses:
            parts.append(strings.DV_OUTDATED.format(", ".join(impact.outdated_harnesses)))
        self.ask(
            " ".join(parts),
            strings.DV_DELETE_CONNECTOR_OK,
            lambda _s: self._do_delete_connector(cid),
        )

    def _do_delete_connector(self, cid: str) -> None:
        if self._do(self.ctl.delete_connector, cid):
            self._cid = None
            self._show_error("")

    def _part_chosen(self, _i: int) -> None:
        cid = self._cid
        part_id = self.part_edit.currentData()
        if self._syncing or cid is None or not isinstance(part_id, str):
            return
        if part_id == self.ctl.project.connectors[cid].part_id:
            return
        try:
            plan = devices.plan_change_part(self.ctl.project, cid, part_id)
        except EditError as exc:
            self._show_error(str(exc))
            self._reload()
            return
        if plan.frozen:
            self._show_error(plan.frozen)
            self._reload()
            return
        if plan.blocked:
            self._show_error(
                strings.DV_PART_BLOCKED.format(
                    plan.new_pin_count, plan.old_pin_count, ", ".join(plan.blocked)
                )
            )
            self._reload()
            return
        checks: list[tuple[str, bool]] = []
        if plan.add or plan.remove:
            checks.append((strings.DV_PART_RESIZE.format(plan.new_pin_count), True))
        if plan.gender is not None:
            checks.append((strings.DV_PART_SET_GENDER.format(strings.DV_GENDER[plan.gender]), True))
        if not checks:
            self._do(self.ctl.change_connector_part, cid, part_id, resize=False, regender=False)
            return
        resizes = bool(plan.add or plan.remove)

        def apply(states: list[bool]) -> None:
            resize = states[0] if resizes else False
            regender = states[-1] if plan.gender is not None else False
            self._do(self.ctl.change_connector_part, cid, part_id, resize=resize, regender=regender)

        self.ask(strings.DV_PART_Q.format(cid, part_id), strings.DV_PART_OK, apply, tuple(checks))

    def _gender_chosen(self, _i: int) -> None:
        cid = self._cid
        if self._syncing or cid is None:
            return
        gender = self.gender_edit.currentData()
        if gender != self.ctl.project.connectors[cid].gender and not self._do(
            self.ctl.update_connector, cid, gender=gender
        ):
            self._reload()

    def _keying_edited(self) -> None:
        cid = self._cid
        if self._syncing or cid is None:
            return
        text = self.keying_edit.text().strip()
        if text != (self.ctl.project.connectors[cid].keying or "") and not self._do(
            self.ctl.update_connector, cid, keying=text
        ):
            self._reload()

    def _label_edited(self) -> None:
        cid = self._cid
        if self._syncing or cid is None:
            return
        text = self.label_edit.text().strip()
        if text != (self.ctl.project.connectors[cid].label or "") and not self._do(
            self.ctl.update_connector, cid, label=text
        ):
            self._reload()

    def _carries_toggled(self) -> None:
        cid = self._cid
        if self._syncing or cid is None:
            return
        chosen = [
            str(a.data()) for a in self.carries_menu.actions() if a.isCheckable() and a.isChecked()
        ]
        if chosen != self.ctl.project.connectors[cid].carries:
            self._do(self.ctl.update_connector, cid, carries=chosen)

    def _use_suggestion(self) -> None:
        cid = self._cid
        if cid is None or not self._suggestion:
            return
        carried = list(self.ctl.project.connectors[cid].carries)
        self._do(self.ctl.update_connector, cid, carries=[*carried, *self._suggestion])

    # ---- internals: pins -----------------------------------------------------------------------
    def _signal_choices(self) -> list[tuple[str, str]]:
        """(signal name, interface type name) for the signal editor, by interface type."""
        out: list[tuple[str, str]] = []
        types = sorted(
            self.ctl.project.interface_types.values(), key=lambda x: (x.name.casefold(), x.id)
        )
        for t in types:
            out.extend((s.name, t.name) for s in t.signals)
        return out

    def _validate_cell(self, key: str, row: dict[str, Any], text: str) -> str | None:
        """What is wrong with this text for this cell (None: nothing), as the planner says."""
        text = text.strip()
        if key == "pin":
            try:
                devices.check_pin(text)
            except EditError as exc:
                return str(exc)
            cid = self._cid
            if cid is not None and text.casefold() != str(row.get("pin", "")).casefold():
                pins = self.ctl.project.connectors[cid].pins
                if any(p.id.casefold() == text.casefold() for p in pins):
                    return strings.DV_PIN_EXISTS.format(text)
            return None
        if key in ("signal", "contact_size") and len(text) > 200:
            return strings.DV_TEXT_TOO_LONG
        if key == "contact_part":
            try:
                devices.check_contact_part(self.ctl.project, text)
            except EditError as exc:
                return str(exc)
        return None

    def _cell_edited(self, row_no: int, key: str, value: object) -> None:
        cid = self._cid
        row = self.pin_model.row(row_no)
        if cid is None or not isinstance(row, dict):
            return
        pin = str(row["pin"])
        if key == "pin":
            new = str(value)
            if new == pin:
                return
            ok = self._do(self.ctl.rename_pin, cid, pin, new)
            if ok:
                self._want_pin = new
            self._cell_done(ok)
            return
        old_key = {"mode": "mode_key", "termination": "termination_key", "role": "role_key"}.get(
            key, key
        )
        if str(value) == str(row.get(old_key) or ""):
            return
        self._cell_done(self._do(self.ctl.set_pin, cid, pin, **{key: value}))

    def _cell_done(self, ok: bool) -> None:
        if ok:
            self._show_error("")
        else:
            self._reload()

    def _insert_pin(self) -> None:
        cid = self._cid
        if cid is None or self.ctl.read_only:
            return
        after = self.current_pin()
        new = devices.next_pin_ids(self.ctl.project, cid, 1, after)
        if self._do(self.ctl.add_pins, cid, None, after=after):
            self._want_pin = new[0] if new else None
            self._show_error("")

    def _clear_signals(self) -> None:
        cid = self._cid
        pins = self.selected_pins()
        if cid is None or not pins or self.ctl.read_only:
            return
        have = {r.pin: r.signal for r in devices.pin_rows(self.ctl.project, cid)}
        rows = [{"pin": p, "signal": ""} for p in pins if have.get(p)]
        if not rows:
            return
        label = strings.STEP_CLEAR_SIGNALS.format(len(rows), self.ctl.project.connectors[cid].name)
        self._do(self.ctl.paste_pin_rows, cid, rows, label)

    def _cycle_mode(self) -> None:
        cid = self._cid
        pins = self.selected_pins()
        if cid is None or not pins or self.ctl.read_only:
            return
        modes = {r.pin: r.mode for r in devices.pin_rows(self.ctl.project, cid)}
        order = list(devices.PIN_MODES)
        nxt = order[(order.index(modes.get(pins[0], "free")) + 1) % len(order)]
        rows = [{"pin": p, "mode": nxt} for p in pins]
        label = strings.STEP_SET_MODE.format(len(rows), self.ctl.project.connectors[cid].name)
        self._do(self.ctl.paste_pin_rows, cid, rows, label)

    def _request_delete_pins(self) -> None:
        cid = self._cid
        pins = self.selected_pins()
        if cid is None or not pins or self.ctl.read_only:
            return
        impact = devices.pin_impact(self.ctl.project, cid, pins)
        if impact.frozen:
            self._show_error(impact.frozen)
            return
        if impact.locked:
            self._show_error(impact.locked[0][1])
            return
        if impact.blocked_by_harnesses:
            self._show_error(
                strings.DV_DELETE_BLOCKED.format(
                    ", ".join(pins), ", ".join(impact.blocked_by_harnesses)
                )
            )
            return
        text = strings.DV_DELETE_PINS_Q.format(", ".join(pins))
        if impact.sentence():
            text += " " + impact.sentence()[0].upper() + impact.sentence()[1:] + "."
        self.ask(text, strings.DV_DELETE_PINS_OK, lambda _s: self._do_delete_pins(cid, pins))

    def _do_delete_pins(self, cid: str, pins: list[str]) -> None:
        if self._do(self.ctl.delete_pins, cid, pins):
            self._show_error("")
            self.pin_table.setFocus()

    def _request_fill(self) -> None:
        cid, pins = self._cid, self.selected_pins()
        if cid is not None and pins and not self.ctl.read_only:
            self.fillRequested.emit(cid, pins)

    def _request_contact(self) -> None:
        cid, pins = self._cid, self.selected_pins()
        if cid is not None and pins and not self.ctl.read_only:
            self.contactRequested.emit(cid, pins)

    def _request_assign(self) -> None:
        cid, pins = self._cid, self.selected_pins()
        if cid is not None and pins and not self.ctl.read_only:
            self.assignRequested.emit(cid, pins)

    def _unassign(self) -> None:
        cid, pins = self._cid, self.selected_pins()
        if cid is None or not pins or self.ctl.read_only:
            return
        self._do(self.ctl.unassign_pins, cid, pins)

    def _paste(self) -> None:
        cid = self._cid
        if cid is None or self.ctl.read_only:
            return
        text = QGuiApplication.clipboard().text()
        try:
            rows, label = plan_paste(
                self.ctl.project, cid, (self.current_pin(), self.current_column()), text
            )
        except EditError as exc:
            self._show_error(str(exc))
            return
        if self._do(self.ctl.paste_pin_rows, cid, rows, label):
            self._show_error("")

    def paste_text(self, text: str) -> bool:
        """Paste this text as if it came from the clipboard (for tests and scripts); True when
        the project changed."""
        QGuiApplication.clipboard().setText(text)
        before = self.ctl.history.revision
        self._paste()
        return self.ctl.history.revision != before

    def _pin_menu(self, pos: Any) -> None:
        menu = QMenu(self.pin_table)
        for text, slot in (
            (strings.DV_ADD_PIN, self._insert_pin),
            (strings.DV_DELETE_PINS, self._request_delete_pins),
            (strings.DV_FILL, self._request_fill),
            (strings.DV_CONTACT_BULK, self._request_contact),
            (strings.DV_ASSIGN, self._request_assign),
            (strings.DV_UNASSIGN, self._unassign),
            (strings.DV_PASTE, self._paste),
        ):
            act = menu.addAction(text)
            act.setEnabled(not self.ctl.read_only)
            act.triggered.connect(lambda _c=False, f=slot: f())
        menu.exec(self.pin_table.viewport().mapToGlobal(pos))
