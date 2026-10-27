"""Harness view: one harness with its connectors and pins, its wires, its drawing and the reasons
behind it, as four views of one selection.

    HarnessView(ctl, theme, settings=None)

* Header: harness selector, name, release state, interfaces, the hash Generate last read, the
  state of the design (up to date / out of date), of the outputs and of the independent check, and
  the actions Regenerate, Export, Open in review, Release and Revise.
* Connector / pin table, wire table, drawing preview (zoom, pan, sheets) and a Why pane in
  splitters. Hover and selection are linked all the ways round: pick a wire in the drawing and its
  rows light up in both tables, pick a pin row and the drawing marks the pin and its wire.
* Nothing in it changes the design. The independent check, the outputs state and the drawing sheets
  are worked out in a background thread and cached by the editor's state token, so `refresh()` stays
  fast on the UI thread; until they arrive the header says "Checking…".
"""

import html
from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from time import perf_counter
from typing import Any

from PySide6.QtCore import (
    QEvent,
    QItemSelection,
    QModelIndex,
    QObject,
    QSettings,
    QSize,
    Qt,
    QTimer,
    Signal,
)
from PySide6.QtGui import QAction, QBrush, QColor, QPainter, QPaintEvent, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QStackedWidget,
    QTabWidget,
    QTextBrowser,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from harness_design_studio.core import describe, edit
from harness_design_studio.core.generate.explain import (
    explain_connector,
    explain_harness,
    explain_pin,
    explain_wire,
)
from harness_design_studio.core.generate.lengths import wire_length
from harness_design_studio.core.model import Harness, Project
from harness_design_studio.core.outputs.build import outputs_status
from harness_design_studio.core.outputs.canvas import Sheet
from harness_design_studio.core.outputs.drawing import harness_sheets
from harness_design_studio.core.outputs.stamp import Stamp
from harness_design_studio.core.outputs.tables import shield_of
from harness_design_studio.core.vcs.lockview import Locked, lock_reason, locked_objects
from harness_design_studio.core.verify import verify_project
from harness_design_studio.core.wirecolours import name_of, resolve
from harness_design_studio.gui import strings
from harness_design_studio.gui.accessory_editor import AccessoryEditor
from harness_design_studio.gui.background import Job, JobRunner
from harness_design_studio.gui.connector_editor import ConnectorEditor
from harness_design_studio.gui.controller import EditorController
from harness_design_studio.gui.icons import icon_button
from harness_design_studio.gui.preview import DrawingPreview, Key
from harness_design_studio.gui.states import StateChip
from harness_design_studio.gui.tables import Column, DictTableModel, Row, TableView, natural_key
from harness_design_studio.gui.theme import ThemeManager
from harness_design_studio.gui.wire_editor import WireEditor

REFRESH_DELAY_MS = 60  # edits closer together than this share one refresh
SHEETS_KEPT = 8  # drawings kept for the harnesses looked at last

Selection = tuple[str, str]  # ("wire" | "pin" | "connector" | "harness", id); a pin is "J1/3"


# ---- rows (pure, no Qt) ------------------------------------------------------------------------


def colour_text(colour: str | None) -> str:
    """ "red (RD)" for a colour the table knows, the text as typed otherwise, "" if unset."""
    if not colour:
        return ""
    name = name_of(colour)
    return f"{name} ({resolve(colour)[0]})" if name else colour


def release_state(project: Project, h: Harness) -> tuple[str, str]:
    """(state key, text) of a harness for the header chip: draft, in review, released, or revised
    (a draft that has an earlier released revision)."""
    if h.status == "released":
        return "released", strings.HV_REL_RELEASED.format(h.revision)
    if h.status == "in_review":
        return "in-review", strings.HV_REL_REVIEW.format(h.revision)
    if any(b.harness_id == h.id for b in project.baselines.values()):
        return "revised", strings.HV_REL_REVISED.format(h.revision)
    return "draft", strings.HV_REL_DRAFT.format(h.revision)


def _wire_state(
    h: Harness, awg: int | None, length: float | None, hand_set: bool
) -> tuple[str, str, str]:
    """(state key, word, tooltip) of a wire row: pending values first, then auto-filled."""
    gauge, long = awg is None, length is None
    if gauge or long:
        word = (
            strings.HV_PENDING_BOTH
            if gauge and long
            else strings.HV_PENDING_GAUGE
            if gauge
            else strings.HV_PENDING_LENGTH
        )
        tip = " ".join(
            t
            for t, on in (
                (strings.HV_GAUGE_PENDING_TIP, gauge),
                (strings.HV_LENGTH_PENDING_TIP, long),
            )
            if on
        )
        return "pending", word, tip
    if h.generated and not hand_set:
        return "not-checked", strings.HV_STATE_AUTO, strings.HV_STATE_AUTO_TIP
    return "", "", ""


def _lock(
    project: Project, kind: str, object_id: str, locked: Locked, by_hand: str | None
) -> tuple[str, str]:
    """(word, tooltip) of the lock on an object: the release that locks it (named by
    `lockview.lock_reason`), else the hand-set lock, else nothing."""
    why = lock_reason(project, kind, object_id, locked)
    if why:
        return strings.HV_LOCKED_WORD, why
    if by_hand:
        return strings.HV_LOCKED_WORD, by_hand
    return "", ""


def pin_rows(project: Project, h: Harness, locked: Locked | None = None) -> list[dict[str, Any]]:
    """One row per pin of every cable connector of the harness, and one more for each further wire
    on the same pin. Built from the generated data as it is; nothing is changed or filled in."""
    locked = locked if locked is not None else locked_objects(project)
    shields = shield_of(h)
    attached: dict[tuple[str, str], list[Any]] = defaultdict(list)
    for w in h.wires:
        attached[(w.from_connector, w.from_pin)].append(w)
        attached[(w.to_connector, w.to_pin)].append(w)
    rows: list[dict[str, Any]] = []
    for c in sorted(h.connectors, key=lambda x: natural_key(x.id)):
        box = project.connectors.get(c.mates_with or "")
        box_signal = {p.id: p.signal for p in (box.pins if box else [])}
        for p in c.pins:
            ref = f"{c.id}/{p.id}"
            signal = p.signal or box_signal.get(p.id) or ""
            pin_word, pin_tip = _lock(
                project,
                "cable_pin",
                f"{c.id}.{p.id}",
                locked,
                strings.HV_LOCK_PIN if p.locked else None,
            )
            wires = sorted(attached.get((c.id, p.id), []), key=lambda w: w.id) or [None]
            for w in wires:
                row: dict[str, Any] = {
                    "connector": c.id, "pin": p.id, "signal": signal, "wire": "",
                    "gauge": None, "gauge_state": None, "colour": "", "colour_hex": "",
                    "shield": "", "locked": pin_word, "locked_state": "locked" if pin_word else None,
                    "locked_why": pin_tip, "state": "", "state_key": None, "state_why": "",
                    "ref": ref, "wire_id": "",
                }  # fmt: skip
                if w is not None:
                    length = wire_length(h, w)
                    key, word, tip = _wire_state(h, w.gauge_awg, length, w.locked or w.manual)
                    w_word, w_tip = _lock(
                        project, "wire", w.id, locked, strings.HV_LOCK_WIRE if w.locked else None
                    )
                    if not row["locked"]:
                        row["locked"], row["locked_why"] = w_word, w_tip
                        row["locked_state"] = "locked" if w_word else None
                    row.update(
                        wire=w.id, wire_id=w.id,
                        gauge=w.gauge_awg if w.gauge_awg is not None else strings.HV_PENDING,
                        gauge_state="pending" if w.gauge_awg is None else None,
                        colour=colour_text(w.colour), colour_hex=resolve(w.colour)[1] if w.colour else "",
                        shield=shields.get(w.id, ""),
                        state=word, state_key=key or None, state_why=tip,
                    )  # fmt: skip
                rows.append(row)
    return rows


def wire_rows(project: Project, h: Harness, locked: Locked | None = None) -> list[dict[str, Any]]:
    locked = locked if locked is not None else locked_objects(project)
    rows: list[dict[str, Any]] = []
    for w in sorted(h.wires, key=lambda x: natural_key(x.id)):
        length = wire_length(h, w)
        key, word, tip = _wire_state(h, w.gauge_awg, length, w.locked or w.manual)
        l_word, l_tip = _lock(
            project, "wire", w.id, locked, strings.HV_LOCK_WIRE if w.locked else None
        )
        rows.append({
            "id": w.id, "signal": w.signal or "",
            "from": f"{w.from_connector}.{w.from_pin}", "to": f"{w.to_connector}.{w.to_pin}",
            "gauge": w.gauge_awg if w.gauge_awg is not None else strings.HV_PENDING,
            "gauge_state": "pending" if w.gauge_awg is None else None,
            "length": length if length is not None else strings.HV_PENDING,
            "length_state": "pending" if length is None else None,
            "colour": colour_text(w.colour),
            "colour_hex": resolve(w.colour)[1] if w.colour else "",
            "locked": l_word, "locked_state": "locked" if l_word else None, "locked_why": l_tip,
            "state": word, "state_key": key or None, "state_why": tip,
            "from_connector": w.from_connector, "to_connector": w.to_connector,
            "from_ref": f"{w.from_connector}/{w.from_pin}", "to_ref": f"{w.to_connector}/{w.to_pin}",
        })  # fmt: skip
    return rows


def _gauge_text(v: Any) -> str:
    return "" if v is None else str(v)


def _length_text(v: Any) -> str:
    return "" if v is None else (v if isinstance(v, str) else f"{v:g}")


def _gauge_tip(row: Row) -> str | None:
    return (
        strings.HV_GAUGE_PENDING_TIP if isinstance(row, dict) and row.get("gauge_state") else None
    )


def _length_tip(row: Row) -> str | None:
    return (
        strings.HV_LENGTH_PENDING_TIP if isinstance(row, dict) and row.get("length_state") else None
    )


def _signal_tip(row: Row) -> str | None:
    """What a signal name such as RTN or GND stands for (nothing for other names)."""
    if not isinstance(row, dict):
        return None
    return describe.signal_meaning(str(row.get("signal") or "")) or None


PIN_COLUMNS = [
    Column("connector", strings.HV_COL_CONNECTOR, mono=True, width=92),
    Column("pin", strings.HV_COL_PIN, mono=True, width=44),
    Column("signal", strings.HV_COL_SIGNAL, tooltip=_signal_tip, width=72),
    Column("wire", strings.HV_COL_WIRE, mono=True, width=92),
    Column("gauge", strings.HV_COL_GAUGE, unit="AWG", numeric=True, state="gauge_state",
           fmt=_gauge_text, tooltip=_gauge_tip, width=110),
    Column("colour", strings.HV_COL_COLOUR, width=124),
    Column("shield", strings.HV_COL_SHIELD, mono=True, width=60),
    Column("locked", strings.HV_COL_LOCKED, state="locked_state", tooltip="locked_why", width=88),
    Column("state", strings.HV_COL_STATE, state="state_key", tooltip="state_why", width=184),
]  # fmt: skip
WIRE_COLUMNS = [
    Column("id", strings.HV_COL_WIRE, mono=True, width=92),
    Column("signal", strings.HV_COL_SIGNAL, tooltip=_signal_tip, width=72),
    Column("from", strings.HV_COL_FROM, mono=True, width=92),
    Column("to", strings.HV_COL_TO, mono=True, width=92),
    Column("gauge", strings.HV_COL_GAUGE, unit="AWG", numeric=True, state="gauge_state",
           fmt=_gauge_text, tooltip=_gauge_tip, width=110),
    Column("length", strings.HV_COL_LENGTH, unit="m", numeric=True, state="length_state",
           fmt=_length_text, tooltip=_length_tip, width=96),
    Column("colour", strings.HV_COL_COLOUR, width=124),
    Column("locked", strings.HV_COL_LOCKED, state="locked_state", tooltip="locked_why", width=88),
    Column("state", strings.HV_COL_STATE, state="state_key", tooltip="state_why", width=184),
]  # fmt: skip


class _FixedWidthTable(TableView):
    """A table whose columns start at the widths the `Column`s give, without measuring every cell
    (measuring chips in hundreds of rows is the slow part of showing a harness); widths the person
    changed and saved win."""

    def _fit_columns(self) -> None:
        if self._sized:
            return
        head = self.horizontalHeader()
        helper = self._widths
        if helper is not None:
            helper.busy = True
        try:
            for k, c in enumerate(self.source.columns):
                head.resizeSection(k, self.theme.px(c.width or 100))
        finally:
            if helper is not None:
                helper.busy = False
        self._sized = True


class _LinkedModel(DictTableModel):
    """A table model that can mark the rows under the pointer in the other views (a tint behind the
    row) and shows the wire colour as a small swatch beside its name."""

    def __init__(self, columns: list[Column], theme: ThemeManager) -> None:
        super().__init__(columns, (), theme)
        self.hover: frozenset[int] = frozenset()
        self._swatches: dict[tuple[str, str], QPixmap] = {}

    def set_hover(self, rows: Iterable[int]) -> None:
        new = frozenset(rows)
        if new == self.hover:
            return
        changed = self.hover ^ new
        self.hover = new
        for r in changed:
            if 0 <= r < self.rowCount():
                self.dataChanged.emit(
                    self.index(r, 0),
                    self.index(r, self.columnCount() - 1),
                    [int(Qt.ItemDataRole.BackgroundRole)],
                )

    def _swatch(self, hexcolour: str) -> QPixmap:
        theme = self.theme
        if theme is None:
            return QPixmap()
        key = (hexcolour, theme.name)
        pm = self._swatches.get(key)
        if pm is None:
            side = theme.px(12)
            pm = QPixmap(side, side)
            pm.fill(QColor(hexcolour))
            p = QPainter(pm)
            p.setPen(theme.color("border"))
            p.drawRect(0, 0, side - 1, side - 1)
            p.end()
            self._swatches[key] = pm
        return pm

    def data(  # type: ignore[override]
        self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole
    ) -> Any:
        if not index.isValid():
            return None
        if role == Qt.ItemDataRole.BackgroundRole and index.row() in self.hover and self.theme:
            return QBrush(self.theme.color("surface-2"))
        if role == Qt.ItemDataRole.DecorationRole and self.columns[index.column()].key == "colour":
            row = self.row(index.row())
            hexcolour = row.get("colour_hex") if isinstance(row, Mapping) else ""
            return self._swatch(str(hexcolour)) if hexcolour else None
        return super().data(index, role)


# ---- background work ---------------------------------------------------------------------------


@dataclass
class Status:
    """What is worked out off the UI thread: is the design generated, are the outputs current,
    does the independent check pass."""

    generation: str  # none | current | stale
    outputs: str  # none | current | stale | modified | unreadable | unsaved
    verify_ok: bool
    verify_summary: str
    errors: int
    ms: float = 0.0


def compute_status(project: Project, folder: Any) -> Status:
    """The slow parts of the header, on a private copy of the project (see `HarnessView`)."""
    from harness_design_studio.core.generation_status import generation_status

    gen = generation_status(project)
    out = "unsaved" if folder is None else outputs_status(project, folder).state
    rep = verify_project(project) if project.harnesses else None
    return Status(
        gen,
        out,
        rep.ok if rep else True,
        rep.summary() if rep else "",
        len(rep.errors) if rep else 0,
    )


# ---- small widgets -----------------------------------------------------------------------------


class _ElideLabel(QLabel):
    """A one-line label that shortens its text with "…" instead of clipping it; the full text is the
    tooltip."""

    def __init__(self, text: str = "", *, wants_room: bool = False) -> None:
        super().__init__()
        self._full = ""
        # a label that takes what is left over (Ignored), or one that asks for its whole text and
        # only gives it up when the window is too narrow (Preferred)
        self.setSizePolicy(
            QSizePolicy.Policy.Preferred if wants_room else QSizePolicy.Policy.Ignored,
            QSizePolicy.Policy.Preferred,
        )
        self.set_full(text)

    def set_full(self, text: str, tip: str | None = None) -> None:
        self._full = text
        self.setToolTip(tip if tip is not None else text)
        self.setAccessibleName(text)
        self.updateGeometry()
        self.update()

    def full(self) -> str:
        return self._full

    def is_elided(self) -> bool:
        return self.fontMetrics().horizontalAdvance(self._full) > self.width()

    def minimumSizeHint(self) -> QSize:  # noqa: N802
        return QSize(0, super().minimumSizeHint().height())

    def sizeHint(self) -> QSize:  # noqa: N802
        return QSize(
            self.fontMetrics().horizontalAdvance(self._full) + 12, super().sizeHint().height()
        )

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        p = QPainter(self)
        p.setPen(self.palette().color(self.foregroundRole()))
        shown = self.fontMetrics().elidedText(self._full, Qt.TextElideMode.ElideRight, self.width())
        p.drawText(self.rect(), int(self.alignment() | Qt.AlignmentFlag.AlignVCenter), shown)
        p.end()


class _WhyView(QWidget):
    """The reasons recorded for the selection, as a short list. A stand-in for the Why panel: the
    window can show the same lines in its own `WhyPanel` through `whyRequested`."""

    whyRequested = Signal(str, str)

    def __init__(self, theme: ThemeManager) -> None:
        super().__init__()
        self.setObjectName("harness-why")
        self.kind, self.ident = "harness", ""
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        top = QHBoxLayout()
        self.title = QLabel(strings.HV_WHY_HINT)
        self.title.setObjectName("why-title")
        self.title.setWordWrap(True)
        self.open_btn = QPushButton()
        self.open_btn.setObjectName("why-open")
        icon_button(self.open_btn, "info", theme, strings.HV_WHY_OPEN_TIP, text=strings.HV_WHY_OPEN)
        self.open_btn.clicked.connect(lambda: self.whyRequested.emit(self.kind, self.ident))
        top.addWidget(self.title, 1)
        top.addWidget(self.open_btn)
        lay.addLayout(top)
        self.body = QTextBrowser()
        self.body.setObjectName("why-body")
        self.body.setAccessibleName(strings.EXPLAIN)
        self.body.setOpenLinks(False)
        lay.addWidget(self.body, 1)
        self.lines: list[str] = []

    def show_lines(self, kind: str, ident: str, title: str, lines: list[str]) -> None:
        self.kind, self.ident, self.lines = kind, ident, list(lines)
        self.title.setText(title)
        if not lines:
            self.body.setHtml(f"<p>{html.escape(strings.HV_WHY_NONE)}</p>")
            return
        items = []
        for line in lines:
            head, sep, rest = line.partition(": ")
            items.append(
                f"<p><b>{html.escape(head)}</b>{html.escape(sep + rest)}</p>"
                if sep
                else f"<p>{html.escape(line)}</p>"
            )
        self.body.setHtml("".join(items))


def _caption(text: str) -> QLabel:
    label = QLabel(text)
    label.setProperty("heading", True)
    return label


# ---- the view ----------------------------------------------------------------------------------


class HarnessView(QWidget):
    """One harness, four linked views and its actions. See the module text.

    Signals: `generateRequested()`, `exportRequested()`, `reviewRequested(harness_id)`,
    `releaseRequested(harness_id)`, `reviseRequested(harness_id)`, `changesRequested(harness_id)`,
    `historyRequested(harness_id)`, `deleteRequested(harness_id)` (the window runs these flows;
    the last three are in the "More" menu),
    `whyRequested(kind, id)` with kind "harness", "wire", "connector" or "pin" (a pin is
    "connector/pin"), `selectionChanged(kind, id)` and `harnessChanged(harness_id)`.
    """

    generateRequested = Signal()
    exportRequested = Signal()
    reviewRequested = Signal(str)
    releaseRequested = Signal(str)
    reviseRequested = Signal(str)
    changesRequested = Signal(str)
    historyRequested = Signal(str)
    deleteRequested = Signal(str)
    newHarnessRequested = Signal()
    whyRequested = Signal(str, str)
    selectionChanged = Signal(str, str)
    harnessChanged = Signal(str)

    def __init__(
        self, ctl: EditorController, theme: ThemeManager, settings: QSettings | None = None
    ) -> None:
        super().__init__()
        self.ctl, self.theme, self.settings = ctl, theme, settings
        self.setObjectName("harness-view")
        self.last_refresh_ms = 0.0  # the last refresh, on the UI thread
        self.status_ms = 0.0  # the last independent check and outputs state, in the background
        self._dirty = True
        self._syncing = False
        self._hid: str | None = None
        self._sel: Selection | None = None
        self._rows_key: tuple[Any, ...] | None = None
        self._pin_data: list[dict[str, Any]] = []
        self._wire_data: list[dict[str, Any]] = []
        self._status: tuple[tuple[int, int], Status] | None = None
        self._sheets: dict[tuple[tuple[int, int], str], list[Sheet]] = {}
        self._shown_sheets_key: tuple[tuple[int, int], str] | None = None
        self.jobs = JobRunner(ctl)
        self.jobs.done.connect(self._job_done)
        self._combo_ids: list[str] = []
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(REFRESH_DELAY_MS)
        self._timer.timeout.connect(self.refresh)

        root = QVBoxLayout(self)
        gap = theme.space(8)
        root.setContentsMargins(gap, gap, gap, gap)
        root.setSpacing(gap)
        self.stack = QStackedWidget()
        root.addWidget(self.stack, 1)

        # empty state
        self.empty = QFrame()
        self.empty.setObjectName("harness-empty")
        e = QVBoxLayout(self.empty)
        e.addStretch(1)
        self.empty_title = QLabel(strings.HV_EMPTY_TITLE)
        self.empty_title.setObjectName("harness-empty-title")
        self.empty_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_title.setProperty("heading", True)
        self.empty_body = QLabel()
        self.empty_body.setObjectName("harness-empty-body")
        self.empty_body.setWordWrap(True)
        self.empty_body.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_generate = QPushButton()
        self.empty_generate.setObjectName("harness-empty-generate")
        self.empty_generate.setProperty("primary", True)
        icon_button(
            self.empty_generate,
            "generate",
            theme,
            strings.GENERATE_TIP,
            text=strings.HV_GENERATE_NOW,
        )
        self.empty_generate.clicked.connect(self.generateRequested)
        self.empty_new = QPushButton()
        self.empty_new.setObjectName("harness-empty-new")
        icon_button(
            self.empty_new, "plus", theme, strings.A_NEW_HARNESS_TIP, text=strings.HV_NEW_HARNESS
        )
        self.empty_new.clicked.connect(self.newHarnessRequested)
        e.addWidget(self.empty_title)
        e.addWidget(self.empty_body)
        e.addWidget(self.empty_generate, 0, Qt.AlignmentFlag.AlignHCenter)
        e.addWidget(self.empty_new, 0, Qt.AlignmentFlag.AlignHCenter)
        e.addStretch(2)
        self.stack.addWidget(self.empty)

        # content
        self.content = QWidget()
        c = QVBoxLayout(self.content)
        c.setContentsMargins(0, 0, 0, 0)
        c.setSpacing(gap)
        self.stack.addWidget(self.content)
        c.addLayout(self._build_header(theme))
        # the drawing has the width and most of the height; the tables and the reasons sit under it
        self.splitter = QSplitter(Qt.Orientation.Vertical)
        self.splitter.setObjectName("harness-splitter")
        self.splitter.setChildrenCollapsible(False)
        c.addWidget(self.splitter, 1)
        self._build_right(theme)  # the drawing (the top row)
        self._build_tables(theme)  # pins, wires and why (the bottom row)
        self.splitter.setStretchFactor(0, 3)
        self.splitter.setStretchFactor(1, 2)
        self.splitter.setSizes([420, 280])
        self._restore_splitters()

        ctl.changed.connect(lambda _d: self._invalidate())
        ctl.stateChanged.connect(self._read_only_changed)
        theme.changed.connect(self._retitle)
        self.refresh()

    # ---- building ----------------------------------------------------------------------------
    def _build_header(self, theme: ThemeManager) -> QVBoxLayout:
        box = QVBoxLayout()
        box.setSpacing(theme.space(4))
        row1 = QHBoxLayout()
        self.selector = QComboBox()
        self.selector.setObjectName("harness-selector")
        self.selector.setAccessibleName(strings.HV_HARNESS)
        self.selector.setToolTip(strings.HV_HARNESS_TIP)
        self.selector.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        self.selector.setMinimumWidth(theme.px(100))
        self.selector.currentIndexChanged.connect(self._selector_changed)
        self.release_chip = StateChip(theme, "draft")
        self.release_chip.setObjectName("harness-release")
        self.name = _ElideLabel()
        self.name.setObjectName("harness-name")
        self.name.setProperty("heading", False)
        self.hash_label = _ElideLabel(wants_room=True)
        self.hash_label.setObjectName("harness-hash")
        self.hash_label.setProperty("mono", True)
        self.hash_label.setProperty("muted", True)
        self.hash_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        row1.addWidget(self.selector)
        row1.addWidget(self.release_chip)
        row1.addWidget(self.name, 1)
        row1.addWidget(self.hash_label, 0)
        box.addLayout(row1)
        row2 = QHBoxLayout()
        self.interfaces = _ElideLabel()
        self.interfaces.setObjectName("harness-interfaces")
        self.interfaces.setProperty("muted", True)
        self.gen_chip = StateChip(theme, "not-checked")
        self.gen_chip.setObjectName("harness-gen-chip")
        self.outputs_chip = StateChip(theme, "not-checked")
        self.outputs_chip.setObjectName("harness-outputs-chip")
        self.verify_chip = StateChip(theme, "pending", strings.HV_CHECKING)
        self.verify_chip.setObjectName("harness-verify-chip")
        row2.addWidget(self.interfaces, 1)
        for chip in (self.gen_chip, self.outputs_chip, self.verify_chip):
            row2.addWidget(chip, 0)
        box.addLayout(row2)
        row3 = QHBoxLayout()
        self.new_button = QPushButton()
        self.new_button.setObjectName("harness-new")
        icon_button(
            self.new_button, "plus", theme, strings.A_NEW_HARNESS_TIP, text=strings.HV_NEW_HARNESS
        )
        self.new_button.clicked.connect(self.newHarnessRequested)
        row3.addWidget(self.new_button)
        self.action_buttons: dict[str, QPushButton] = {}
        specs = (
            ("regenerate", "generate", strings.HV_REGENERATE, strings.HV_REGENERATE_TIP),
            ("export", "export", strings.HV_EXPORT, strings.EXPORT_TIP),
            ("review", "review", strings.HV_REVIEW, strings.HV_REVIEW_TIP.format("")),
            ("release", "release", strings.RELEASE, strings.RELEASE_TIP),
            ("revise", "revise", strings.HV_REVISE, strings.NEW_REV_TIP),
        )
        for key, icon_name, text, tip in specs:
            b = QPushButton()
            b.setObjectName(f"harness-{key}")
            icon_button(b, icon_name, theme, tip, text=text)
            self.action_buttons[key] = b
            row3.addWidget(b)
        self.more_button = QToolButton()
        self.more_button.setObjectName("harness-more")
        icon_button(
            self.more_button, "chevron-down", theme, strings.HV_MORE_TIP, text=strings.HV_MORE
        )
        self.more_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.more_menu = QMenu(self.more_button)
        self.more_actions: dict[str, QAction] = {}
        for key, text, tip, signal in (
            ("changes", strings.CHANGES, strings.CHANGES_TIP, self.changesRequested),
            ("history", strings.HISTORY, strings.HISTORY_TIP, self.historyRequested),
            ("delete", strings.DELETE_HARNESS, strings.DELETE_HARNESS_TIP, self.deleteRequested),
        ):
            act = self.more_menu.addAction(text)
            act.setObjectName(f"harness-more-{key}")
            act.setToolTip(tip)
            act.triggered.connect(lambda _c=False, sig=signal: self._emit_for(sig))
            self.more_actions[key] = act
        self.more_button.setMenu(self.more_menu)
        row3.addWidget(self.more_button)
        row3.addStretch(1)
        self.export_reason = QLabel()
        self.export_reason.setObjectName("harness-export-reason")
        self.export_reason.setProperty("muted", True)
        self.export_reason.setAccessibleName(strings.HV_EXPORT_REASON_NAME)
        self.export_reason.setWordWrap(False)
        self.export_reason.hide()
        row3.insertWidget(row3.indexOf(self.action_buttons["export"]) + 1, self.export_reason)
        self.action_buttons["regenerate"].clicked.connect(self.generateRequested)
        self.action_buttons["export"].clicked.connect(self.exportRequested)
        self.action_buttons["review"].clicked.connect(lambda: self._emit_for(self.reviewRequested))
        self.action_buttons["release"].clicked.connect(
            lambda: self._emit_for(self.releaseRequested)
        )
        self.action_buttons["revise"].clicked.connect(lambda: self._emit_for(self.reviseRequested))
        self.action_bar = row3
        box.addLayout(row3)
        return box

    def _table(
        self, theme: ThemeManager, columns: list[Column], name: str, key: str
    ) -> tuple[_FixedWidthTable, _LinkedModel]:
        model = _LinkedModel(columns, theme)
        view = _FixedWidthTable(model, theme, name=name, settings=self.settings, key=key)
        view.setMouseTracking(True)
        view.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        view.viewport().installEventFilter(self)
        return view, model

    def _build_tables(self, theme: ThemeManager) -> None:
        left = QSplitter(Qt.Orientation.Horizontal)
        left.setObjectName("harness-left-splitter")
        left.setChildrenCollapsible(False)
        self.left_splitter = left
        pins = QWidget()
        pl = QVBoxLayout(pins)
        pl.setContentsMargins(0, 0, 0, 0)
        pl.setSpacing(theme.space(4))
        bar = QHBoxLayout()
        bar.addWidget(_caption(strings.HV_PINS_TITLE))
        bar.addStretch(1)
        self.pin_filter = QLineEdit()
        self.pin_filter.setObjectName("pin-filter")
        self.pin_filter.setPlaceholderText(strings.HV_FILTER_PINS)
        self.pin_filter.setAccessibleName(strings.HV_FILTER_PINS)
        self.pin_filter.setClearButtonEnabled(True)
        self.pin_filter.setMaximumWidth(theme.px(180))
        # a toggle button, not a check box: the theme styles a pressed button (fill, icon and word),
        # and a check box's tick box would disappear in the dark theme
        self.spare = QPushButton()
        self.spare.setObjectName("pin-spare")
        self.spare.setCheckable(True)
        icon_button(
            self.spare, "filter", theme, strings.HV_SHOW_SPARE_TIP,
            text=strings.HV_SHOW_SPARE, checked_role="on-primary",
        )  # fmt: skip
        bar.addWidget(self.pin_filter)
        bar.addWidget(self.spare)
        pl.addLayout(bar)
        self.pin_table, self.pin_model = self._table(
            theme, PIN_COLUMNS, strings.HV_PINS_TITLE, "harness-pins"
        )
        self.pin_table.setObjectName("harness-pin-table")
        pl.addWidget(self.pin_table, 1)
        self.pin_count = QLabel()
        self.pin_count.setObjectName("pin-count")
        self.pin_count.setProperty("muted", True)
        pl.addWidget(self.pin_count)
        left.addWidget(pins)
        wires = QWidget()
        wl = QVBoxLayout(wires)
        wl.setContentsMargins(0, 0, 0, 0)
        wl.setSpacing(theme.space(4))
        bar = QHBoxLayout()
        bar.addWidget(_caption(strings.HV_WIRES_TITLE))
        bar.addStretch(1)
        self.wire_filter = QLineEdit()
        self.wire_filter.setObjectName("wire-filter")
        self.wire_filter.setPlaceholderText(strings.HV_FILTER_WIRES)
        self.wire_filter.setAccessibleName(strings.HV_FILTER_WIRES)
        self.wire_filter.setClearButtonEnabled(True)
        self.wire_filter.setMaximumWidth(theme.px(180))
        bar.addWidget(self.wire_filter)
        wl.addLayout(bar)
        self.wire_table, self.wire_model = self._table(
            theme, WIRE_COLUMNS, strings.HV_WIRES_TITLE, "harness-wires"
        )
        self.wire_table.setObjectName("harness-wire-table")
        wl.addWidget(self.wire_table, 1)
        self.wire_count = QLabel()
        self.wire_count.setObjectName("wire-count")
        self.wire_count.setProperty("muted", True)
        wl.addWidget(self.wire_count)
        left.addWidget(wires)
        left.addWidget(self._why_box)
        left.setStretchFactor(0, 4)
        left.setStretchFactor(1, 4)
        left.setStretchFactor(2, 3)
        left.setSizes([340, 340, 240])
        self.splitter.addWidget(left)
        self.pin_filter.textChanged.connect(self.pin_table.proxy.set_text)
        self.pin_filter.textChanged.connect(lambda _t: self._update_counts())
        self.wire_filter.textChanged.connect(self.wire_table.proxy.set_text)
        self.wire_filter.textChanged.connect(lambda _t: self._update_counts())
        self.spare.toggled.connect(self._spare_toggled)
        self._spare_toggled(False)
        for table, handler in (
            (self.pin_table, self._pin_current),
            (self.wire_table, self._wire_current),
        ):
            sm = table.selectionModel()
            if sm is not None:
                sm.currentChanged.connect(handler)
            table.entered.connect(self._table_entered)
        self.pin_table.activated.connect(lambda _i: self._why_requested())
        self.wire_table.activated.connect(lambda _i: self._why_requested())
        wsm = self.wire_table.selectionModel()
        if wsm is not None:
            wsm.selectionChanged.connect(lambda *_a: self._update_wire_editor())

    def _build_right(self, theme: ThemeManager) -> None:
        draw = QWidget()
        dl = QVBoxLayout(draw)
        dl.setContentsMargins(0, 0, 0, 0)
        dl.setSpacing(theme.space(4))
        dl.addWidget(_caption(strings.HV_DRAWING_TITLE))
        self.preview = DrawingPreview(theme)
        dl.addWidget(self.preview, 1)
        self.splitter.addWidget(draw)
        self.why = _WhyView(theme)
        self.wire_editor = WireEditor(self.ctl, theme)
        side = QTabWidget()
        side.setObjectName("harness-side-tabs")
        side.setDocumentMode(True)
        side.addTab(self.why, strings.HV_WHY_TITLE)
        scroll = QScrollArea()  # the form scrolls, so it never forces the drawing to shrink
        scroll.setObjectName("wire-editor-scroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(self.wire_editor)
        side.addTab(scroll, strings.HV_EDIT_TAB)
        self.connector_editor = ConnectorEditor(self.ctl, theme)
        cscroll = QScrollArea()
        cscroll.setObjectName("connector-editor-scroll")
        cscroll.setWidgetResizable(True)
        cscroll.setFrameShape(QFrame.Shape.NoFrame)
        cscroll.setWidget(self.connector_editor)
        side.addTab(cscroll, strings.HV_CONNECTORS_TAB)
        self.connector_scroll = cscroll
        self.accessory_editor = AccessoryEditor(self.ctl, theme)
        ascroll = QScrollArea()
        ascroll.setObjectName("accessory-editor-scroll")
        ascroll.setWidgetResizable(True)
        ascroll.setFrameShape(QFrame.Shape.NoFrame)
        ascroll.setWidget(self.accessory_editor)
        side.addTab(ascroll, strings.HV_ACCESSORIES_TAB)
        self.connector_editor.connectorAdded.connect(lambda _cid: self.refresh())
        # four tabs in a narrow box: let them shrink and elide, never grow scroll arrows
        side.setUsesScrollButtons(False)
        side.setElideMode(Qt.TextElideMode.ElideRight)
        for i, tip in enumerate(
            (
                strings.HV_WHY_TITLE,
                strings.HV_EDIT_TAB,
                strings.HV_CONNECTORS_TAB,
                strings.HV_ACCESSORIES_TAB,
            )
        ):
            side.setTabToolTip(i, tip)
        self.side_tabs = side
        self._why_box = side  # placed beside the tables by `_build_tables`
        self.why.whyRequested.connect(self.whyRequested)
        self.wire_editor.wireAdded.connect(self._wire_added)
        self.preview.hovered.connect(self._drawing_hovered)
        self.preview.clicked.connect(self._drawing_clicked)

    def _restore_splitters(self) -> None:
        if self.settings is None:
            return
        for name, sp in (  # (new keys: the layout changed from columns to rows in M6)
            ("harness-view/rows", self.splitter),
            ("harness-view/tables", self.left_splitter),
        ):
            state = self.settings.value(name)
            if state is not None:
                sp.restoreState(state)
            sp.splitterMoved.connect(lambda _p, _i, n=name, s=sp: self._save_splitter(n, s))

    def _save_splitter(self, name: str, sp: QSplitter) -> None:
        if self.settings is not None:
            self.settings.setValue(name, sp.saveState())

    # ---- public API ------------------------------------------------------------------------
    def harness_id(self) -> str | None:
        return self._hid

    def selection(self) -> Selection | None:
        return self._sel

    def select_harness(self, harness_id: str) -> bool:
        """Show this harness. False if there is no such harness."""
        if harness_id not in self.ctl.project.harnesses:
            return False
        if self._dirty:
            self.refresh()
        i = self.selector.findData(harness_id)
        if i < 0:
            return False
        self.selector.setCurrentIndex(i)
        return True

    def show_connectors(self) -> None:
        """Open the Connectors tab beside the drawing."""
        self.side_tabs.setCurrentWidget(self.connector_scroll)

    def select(self, kind: str, ident: str) -> None:
        """Select a wire, a connector or a pin ("connector/pin") of the shown harness; the tables
        and the drawing follow. `("harness", id)` or an unknown object clears the selection."""
        self._set_selection((kind, ident) if self._exists(kind, ident) else None, origin="api")

    def refresh(self) -> None:
        """Bring the view up to date with the design. Quick: the slow parts are worked out in the
        background and cached (`wait_idle()` waits for them)."""
        t0 = perf_counter()
        self._timer.stop()
        self._dirty = False
        p = self.ctl.project
        ids = sorted(p.harnesses)
        self.stack.setCurrentWidget(self.content if ids else self.empty)
        if not ids:
            self._hid = None
            self._combo_ids = []
            self._show_empty()
            self.last_refresh_ms = (perf_counter() - t0) * 1000
            return
        self._fill_selector(ids)
        h = p.harnesses[self._hid or ids[0]]
        self._hid = h.id
        self._header(h)
        self._rows(h)
        self._status_now()
        self._ensure_sheets()
        self._buttons(h)
        self.last_refresh_ms = (perf_counter() - t0) * 1000
        self._update_verify_tip()

    def refresh_status(self) -> None:
        """Forget the cached check and outputs state and work them out again (call it after an
        export: the files changed, the design did not)."""
        self._status = None
        self.refresh()

    def wait_idle(self, timeout_ms: int = 10000) -> bool:
        """Wait (keeping the event loop going) until the background work has been delivered. For
        tests and screenshots; the window never needs it."""
        return self.jobs.wait_idle(timeout_ms)

    # ---- refresh pieces --------------------------------------------------------------------
    def _invalidate(self) -> None:
        self._dirty = True
        if self.isVisible():
            self._timer.start()

    def showEvent(self, event: object) -> None:  # noqa: N802
        super().showEvent(event)  # type: ignore[arg-type]
        if self._dirty:
            self.refresh()

    def _read_only_changed(self) -> None:
        if self._hid and self._hid in self.ctl.project.harnesses:
            self._buttons(self.ctl.project.harnesses[self._hid])

    def _retitle(self) -> None:
        self.pin_model.beginResetModel()
        self.pin_model.endResetModel()

    def _show_empty(self) -> None:
        p = self.ctl.project
        n = len(p.interfaces)
        if n:
            body = strings.HV_EMPTY_READY.format(n)
        elif p.links:  # connections first: a harness is made from a connection, not generated
            body = strings.HV_EMPTY_HAS_LINKS
        else:
            body = strings.HV_EMPTY_NO_INTERFACES
        self.empty_body.setText(body + strings.HV_EMPTY_BY_HAND)
        show = bool(n) and not self.ctl.read_only
        self.empty_generate.setVisible(show)  # no row of disabled buttons without a harness
        self.empty_new.setVisible(not self.ctl.read_only)

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

    def _wire_added(self, wire_id: str) -> None:
        """A wire was added in the form: show its row and its values."""
        self.refresh()
        self.select("wire", wire_id)
        self._update_wire_editor()

    def _header(self, h: Harness) -> None:
        self.wire_editor.set_harness(h.id)
        self.connector_editor.set_harness(h.id)
        self.accessory_editor.set_harness(h.id)
        p = self.ctl.project
        state, text = release_state(p, h)
        self.release_chip.set_state(state, text)
        self.release_chip.setToolTip(f"{text}. {strings.HV_REL_TIP[state]}")
        self.name.set_full(h.name)
        self.interfaces.set_full(
            strings.HV_INTERFACES.format(", ".join(h.interfaces))
            if h.interfaces
            else strings.HV_INTERFACES_NONE
        )
        gen = p.generation
        if gen is None:
            # a harness made from a connection or by hand is never generated: say so
            self.hash_label.set_full(
                strings.HV_NOT_GENERATED if h.generated else strings.HV_MADE_BY_HAND
            )
        else:
            self.hash_label.set_full(
                strings.HV_GENERATED_FROM.format(gen.input_hash[:12]),
                strings.HV_GENERATED_FROM_TIP.format(gen.input_hash),
            )

    def _rows(self, h: Harness) -> None:
        token = self.ctl.state_token
        key = (token, h.id)
        if key == self._rows_key:
            return
        p = self.ctl.project
        locked = locked_objects(p)
        pins = pin_rows(p, h, locked)
        wires = wire_rows(p, h, locked)
        same = self._rows_key is not None and self._rows_key[1] == h.id
        self._rows_key = key
        self._pin_data, self._wire_data = pins, wires
        keep = self._sel
        self._syncing = True
        try:
            for model, rows in ((self.pin_model, pins), (self.wire_model, wires)):
                if same:
                    model.update_rows(rows)
                else:
                    model.set_rows(rows)
        finally:
            self._syncing = False
        self._update_counts()
        if keep and self._exists(*keep):
            self._set_selection(keep, origin="api")
        else:
            self._set_selection(None, origin="api")
        self._update_wire_editor()

    def _update_wire_editor(self) -> None:
        """Show the selected wires of the wire table in the Edit wire form (untouched edits are
        dropped when the selection or the design changes)."""
        if self._syncing:
            return
        rows = self.wire_table.selected_rows()
        ids = [str(r["id"]) for r in rows if isinstance(r, dict) and "id" in r]
        if ids == self.wire_editor.wire_ids() and not self.wire_editor.dirty:
            self.wire_editor.show_wires(ids)  # same wires: refresh the values
        elif ids != self.wire_editor.wire_ids():
            self.wire_editor.show_wires(ids)

    def _update_counts(self) -> None:
        shown = self.pin_table.proxy.rowCount()
        hidden = (
            sum(1 for r in self._pin_data if self._is_spare(r)) if not self.spare.isChecked() else 0
        )
        self.pin_count.setText(
            strings.HV_PIN_COUNT_SPARE.format(shown, hidden)
            if hidden
            else strings.HV_PIN_COUNT.format(shown)
        )
        self.wire_count.setText(
            strings.HV_WIRE_COUNT.format(self.wire_table.proxy.rowCount())
            if self._wire_data
            else strings.HV_NO_WIRES
        )

    @staticmethod
    def _is_spare(row: Row) -> bool:
        return isinstance(row, dict) and not row.get("wire") and not row.get("signal")

    def _spare_toggled(self, on: bool) -> None:
        self.pin_table.proxy.set_predicate(None if on else (lambda r: not self._is_spare(r)))
        self._update_counts()

    def _buttons(self, h: Harness) -> None:
        ctl = self.ctl
        ro = ctl.read_only
        st = h.status
        specs: dict[str, tuple[bool, str, str]] = {
            "regenerate": (not ro, strings.WHY_READ_ONLY, strings.HV_REGENERATE_TIP),
            "export": (
                not ro,
                strings.HV_EXPORT_READ_ONLY,
                strings.EXPORT_TIP
                if ctl.root is not None
                else f"{strings.EXPORT_TIP}. {strings.HV_EXPORT_SAVES_FIRST_TIP}",
            ),
            "review": (True, "", strings.HV_REVIEW_TIP.format(h.id)),
            "release": (
                st in ("draft", "in_review") and not ro,
                strings.WHY_READ_ONLY if ro else strings.HV_WHY_RELEASE_NOT_DRAFT,
                strings.RELEASE_TIP,
            ),
            "revise": (
                st == "released" and not ro,
                strings.WHY_READ_ONLY if ro else strings.HV_WHY_NOT_RELEASED,
                strings.NEW_REV_TIP,
            ),
        }
        self.new_button.setEnabled(not ro)
        self.new_button.setToolTip(strings.WHY_READ_ONLY if ro else strings.A_NEW_HARNESS_TIP)
        has_base = any(b.harness_id == h.id for b in self.ctl.project.baselines.values())
        self.more_actions["changes"].setEnabled(has_base)
        self.more_actions["history"].setEnabled(True)
        self.more_actions["delete"].setEnabled(st in ("draft", "in_review") and not ro)
        for key, (on, why, tip) in specs.items():
            b = self.action_buttons[key]
            b.setEnabled(on)
            # a disabled button says why; an enabled one says what it does
            b.setToolTip(tip if on else f"{b.text()}: {why}")
            b.setAccessibleDescription(tip if on else why)
        # the reason sits beside the button (a tooltip alone is easy to miss)
        reason = (
            strings.HV_EXPORT_READ_ONLY
            if ro
            else strings.HV_EXPORT_SAVES_FIRST
            if ctl.root is None
            else ""
        )
        self.export_reason.setText(reason)
        self.export_reason.setVisible(bool(reason))

    def _emit_for(self, signal: Any) -> None:
        if self._hid:
            signal.emit(self._hid)

    def _selector_changed(self, _i: int) -> None:
        hid = self.selector.currentData()
        if isinstance(hid, str) and hid != self._hid:
            self._hid = hid
            self._sel = None
            self.harnessChanged.emit(hid)
            self.refresh()

    # ---- background work -------------------------------------------------------------------
    def _status_now(self) -> None:
        token = self.ctl.state_token
        if self._status is not None and self._status[0] == token:
            self._show_status(self._status[1])
            return
        if self._status is not None:  # keep showing the last answer, marked as being redone
            self._show_status(self._status[1], checking=True)
        else:
            self._show_checking()
        folder = self.ctl.outputs_folder()
        snapshot = edit.clone_with(self.ctl.project, [])
        self.jobs.start("status", None, lambda: compute_status(snapshot, folder))

    def _ensure_sheets(self) -> None:
        if not self._hid:
            self.preview.set_sheets([])
            return
        token = self.ctl.state_token
        key = (token, self._hid)
        if key in self._sheets:
            if self._shown_sheets_key != key:
                self._shown_sheets_key = key
                self.preview.set_sheets(self._sheets[key])
                self._reselect_drawing()
            return
        if not self.isVisible() and self._shown_sheets_key is not None:
            return  # a hidden view draws when it is shown again
        if self._shown_sheets_key is None or self._shown_sheets_key[1] != self._hid:
            self.preview.set_sheets([], strings.HV_DRAWING_BUSY)  # not the previous harness's
            self._shown_sheets_key = None
        snapshot = edit.clone_with(self.ctl.project, [])
        h = snapshot.harnesses[self._hid]
        self.jobs.start(
            "sheets",
            self._hid,
            lambda: harness_sheets(snapshot, h, Stamp("preview", "preview"), "A3"),
        )

    def _job_done(self, job: Job) -> None:
        current = self.jobs.is_current(job)
        if job.kind == "status":
            if job.error is not None:
                self._show_failed(job.error)
            elif current:
                st: Status = job.value
                st.ms = job.ms
                self._status = (job.token, st)
                self.status_ms = job.ms
                self._show_status(st)
        elif job.kind == "sheets" and job.error is None:
            sheets: list[Sheet] = job.value
            if current:
                self._sheets[(job.token, job.key)] = sheets
                while len(self._sheets) > SHEETS_KEPT:
                    self._sheets.pop(next(iter(self._sheets)))
            if current and job.key == self._hid:
                self._shown_sheets_key = (job.token, job.key)
                self.preview.set_sheets(sheets)
                self._reselect_drawing()
        if not current and self.isVisible() and not self.jobs.busy():
            self._invalidate()

    def _show_checking(self) -> None:
        self.gen_chip.set_state("pending", strings.HV_CHECKING)
        self.outputs_chip.set_state("pending", strings.HV_CHECKING)
        self.verify_chip.set_state("pending", strings.HV_CHECKING)
        for chip in (self.gen_chip, self.outputs_chip, self.verify_chip):
            chip.setToolTip(strings.HV_CHECKING_TIP)

    def _show_failed(self, reason: str) -> None:
        text = strings.HV_VERIFY_FAILED.format(reason)
        self.verify_chip.set_state("not-checked", strings.HV_VERIFY_FAILED.format("").rstrip(": "))
        self.verify_chip.setToolTip(text)

    def _show_status(self, st: Status, *, checking: bool = False) -> None:
        gen = {
            "current": ("pass", strings.HV_GEN_CURRENT),
            "stale": ("stale", strings.HV_GEN_STALE),
            "none": ("not-checked", strings.HV_GEN_NONE),
        }[st.generation]
        self.gen_chip.set_state(*gen)
        self.gen_chip.setToolTip(strings.GEN_STATUS[st.generation])
        out = {
            "current": ("pass", strings.HV_OUT_CURRENT),
            "stale": ("stale", strings.HV_OUT_STALE),
            "none": ("not-checked", strings.HV_OUT_NONE),
            "unsaved": ("not-checked", strings.HV_OUT_UNSAVED),
            "modified": ("warning", strings.HV_OUT_MODIFIED),
            "unreadable": ("fail", strings.HV_OUT_UNREADABLE),
        }[st.outputs]
        self.outputs_chip.set_state(*out)
        self.outputs_chip.setToolTip(strings.OUT_STATUS[st.outputs])
        if checking:
            self.verify_chip.set_state("pending", strings.HV_CHECKING)
            self.verify_chip.setToolTip(strings.HV_CHECKING_TIP)
        elif not self.ctl.project.harnesses:
            self.verify_chip.set_state("not-checked", strings.HV_CHECKING)
        elif st.verify_ok:
            self.verify_chip.set_state("pass", strings.HV_VERIFY_OK)
        else:
            self.verify_chip.set_state("fail", strings.HV_VERIFY_BAD.format(st.errors))
        self._update_verify_tip()

    def _update_verify_tip(self) -> None:
        if self._status is None or self.verify_chip.state() == "pending":
            return
        st = self._status[1]
        fmt = strings.PLANS_VERIFY_OK if st.verify_ok else strings.PLANS_VERIFY_BAD
        self.verify_chip.setToolTip(
            fmt.format(st.verify_summary)
            + " "
            + strings.HV_VERIFIED_IN.format(round(st.ms), round(self.last_refresh_ms))
        )

    # ---- selection and hover ---------------------------------------------------------------
    def _exists(self, kind: str, ident: str) -> bool:
        if kind == "wire":
            return any(r["id"] == ident for r in self._wire_data)
        if kind == "pin":
            return any(r["ref"] == ident for r in self._pin_data)
        if kind == "connector":
            return any(r["connector"] == ident for r in self._pin_data)
        return False

    def _rows_for(self, kind: str, ident: str) -> tuple[list[int], list[int]]:
        """(pin table rows, wire table rows), as source rows, that belong to an object."""
        pins: list[int] = []
        wires: list[int] = []
        if kind == "wire":
            pins = [i for i, r in enumerate(self._pin_data) if r["wire_id"] == ident]
            wires = [i for i, r in enumerate(self._wire_data) if r["id"] == ident]
        elif kind == "pin":
            pins = [i for i, r in enumerate(self._pin_data) if r["ref"] == ident]
            ids = {self._pin_data[i]["wire_id"] for i in pins if self._pin_data[i]["wire_id"]}
            wires = [i for i, r in enumerate(self._wire_data) if r["id"] in ids]
        elif kind == "connector":
            pins = [i for i, r in enumerate(self._pin_data) if r["connector"] == ident]
            wires = [
                i
                for i, r in enumerate(self._wire_data)
                if ident in (r["from_connector"], r["to_connector"])
            ]
        return pins, wires

    def _drawing_keys(self, kind: str, ident: str) -> list[Key]:
        if kind == "wire":
            keys: list[Key] = [("wire", ident)]
            for r in self._wire_data:
                if r["id"] == ident:
                    keys += [("pin", r["from_ref"]), ("pin", r["to_ref"])]
            return keys
        if kind == "pin":
            keys = [("pin", ident)]
            keys += [
                ("wire", r["wire_id"]) for r in self._pin_data if r["ref"] == ident and r["wire_id"]
            ]
            return keys
        if kind == "connector":
            return [("connector", ident)]
        return []

    def _select_in(self, table: TableView, rows: list[int]) -> None:
        model = table.source
        sel = QItemSelection()
        first: QModelIndex | None = None
        last_col = model.columnCount() - 1
        for r in rows:
            top = table.proxy.mapFromSource(model.index(r, 0))
            if not top.isValid():
                continue
            if first is None:
                first = top
            sel.select(top, table.proxy.index(top.row(), last_col))
        sm = table.selectionModel()
        if sm is None:
            return
        self._syncing = True
        try:
            sm.clearSelection()
            if first is not None:
                sm.select(sel, sm.SelectionFlag.ClearAndSelect)
                sm.setCurrentIndex(first, sm.SelectionFlag.NoUpdate)
                table.scrollTo(first)
        finally:
            self._syncing = False

    def _set_selection(self, sel: Selection | None, origin: str) -> None:
        self._sel = sel
        if sel is None:
            if origin != "pin":
                self._select_in(self.pin_table, [])
            if origin != "wire":
                self._select_in(self.wire_table, [])
            self.preview.set_selected([])
            self._show_why()
            self.selectionChanged.emit("harness", self._hid or "")
            return
        kind, ident = sel
        pins, wires = self._rows_for(kind, ident)
        if origin != "pin":
            self._select_in(self.pin_table, pins)
        if origin != "wire":
            self._select_in(self.wire_table, wires)
        self.preview.set_selected(self._drawing_keys(kind, ident))
        self._show_why()
        self.selectionChanged.emit(kind, ident)

    def _reselect_drawing(self) -> None:
        if self._sel:
            self.preview.set_selected(self._drawing_keys(*self._sel))

    def _pin_current(self, cur: QModelIndex, _prev: QModelIndex) -> None:
        if self._syncing or not cur.isValid():
            return
        row = self.pin_table.row_at(cur)
        if not isinstance(row, dict):
            return
        self._set_selection(("pin", row["ref"]), origin="pin")

    def _wire_current(self, cur: QModelIndex, _prev: QModelIndex) -> None:
        if self._syncing or not cur.isValid():
            return
        row = self.wire_table.row_at(cur)
        if not isinstance(row, dict):
            return
        self._set_selection(("wire", row["id"]), origin="wire")

    def _drawing_clicked(self, kind: str, ident: str) -> None:
        if kind and self._exists(kind, ident):
            self._set_selection((kind, ident), origin="draw")
        else:
            self._set_selection(None, origin="draw")

    def _drawing_hovered(self, kind: str, ident: str) -> None:
        self._hover(kind if self._exists(kind, ident) else "", ident, from_drawing=True)

    def _table_entered(self, index: QModelIndex) -> None:
        table = self.sender()
        if not isinstance(table, TableView) or not index.isValid():
            return
        row = table.row_at(index)
        if not isinstance(row, dict):
            return
        if table is self.pin_table:
            self._hover("pin", str(row["ref"]), from_drawing=False)
        else:
            self._hover("wire", str(row["id"]), from_drawing=False)

    def _hover(self, kind: str, ident: str, *, from_drawing: bool) -> None:
        pins, wires = self._rows_for(kind, ident) if kind else ([], [])
        self.pin_model.set_hover(pins)
        self.wire_model.set_hover(wires)
        if not from_drawing:
            self.preview.set_hover(self._drawing_keys(kind, ident) if kind else [])

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:  # noqa: N802
        if event.type() == QEvent.Type.Leave and obj in (
            self.pin_table.viewport(),
            self.wire_table.viewport(),
        ):
            self._hover("", "", from_drawing=False)
        return super().eventFilter(obj, event)

    # ---- why -------------------------------------------------------------------------------
    def why_for(self, kind: str, ident: str) -> tuple[str, list[str]]:
        """(title, reasons) recorded for a harness, wire, connector or pin."""
        p = self.ctl.project
        h = p.harnesses.get(self._hid or "")
        if h is None:
            return "", []
        if kind == "wire":
            w = next((w for w in h.wires if w.id == ident), None)
            return strings.HV_WHY_WIRE.format(ident), explain_wire(p, h, w) if w else []
        if kind == "connector":
            return strings.HV_WHY_CONNECTOR.format(ident), explain_connector(p, h, ident)
        if kind == "pin":
            cid, _, pin = ident.partition("/")
            lines = explain_pin(p, h, cid, pin)
            for r in self._pin_data:
                if r["ref"] == ident and r["wire_id"]:
                    w = next((w for w in h.wires if w.id == r["wire_id"]), None)
                    if w:
                        lines += [f"{w.id}: {line}" for line in explain_wire(p, h, w)]
            return strings.HV_WHY_PIN.format(f"{cid}.{pin}"), lines
        return strings.HV_WHY_HARNESS.format(h.id), explain_harness(p, h)

    def _show_why(self) -> None:
        kind, ident = self._sel if self._sel else ("harness", self._hid or "")
        title, lines = self.why_for(kind, ident)
        self.why.show_lines(kind, ident, title, lines)

    def _why_requested(self) -> None:
        kind, ident = self._sel if self._sel else ("harness", self._hid or "")
        self.whyRequested.emit(kind, ident)
