"""The Checks tab: one row per design rule with its result, and what to do about it.

    panel = ChecksPanel(ctl, theme)
    panel.showRequested.connect(window.show_object)     # an offending object: show it on the diagram

A summary strip says "34 rules: 20 passed · 2 failed · 12 not checked · 4 pending values" (text and
icons; each count filters the table). The rules table shows ID, rule, severity, result as a state chip
(pass, fail, not checked, pending), open and waived counts, and the standard's requirement IDs as a
tooltip. Selecting a rule opens its details below: the offending objects (Enter or double-click
shows one on the diagram), the exact value a not-checked or pending rule is waiting for (file, key,
unit) with a **Supply value...** button that opens `ConfigValueDialog`, and a note when a rule
passed on placeholder values.

The results come from `ctl.drc_rule_results()`, which groups the findings the controller already
holds (no rule runs twice). While the helper process runs the panel says "checking" and offers
Cancel; if the check itself failed a banner stays until the next success. `PendingValuesLink` is the
status-bar link ("4 values pending · 12 rules not checked"); its `filterRequested` filters this table.
"""

from collections.abc import Mapping, Sequence
from typing import Any, Final, cast

from PySide6.QtCore import QModelIndex, QSettings, Qt, Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSplitter,
    QStackedWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from harness_design_studio.core import configcheck
from harness_design_studio.core.checks import Finding
from harness_design_studio.core.drc import by_rule
from harness_design_studio.core.drc.by_rule import MissingValue, RuleResult
from harness_design_studio.gui import strings
from harness_design_studio.gui.config_dialog import ConfigValueDialog
from harness_design_studio.gui.controller import EditorController
from harness_design_studio.gui.icons import icon, icon_button
from harness_design_studio.gui.panels import clear_layout, heading, muted
from harness_design_studio.gui.states import STATES, StateChip
from harness_design_studio.gui.tables import Column, DictTableModel, TableView
from harness_design_studio.gui.theme import ThemeManager, mark_mono

# ---- what a result looks like ---------------------------------------------------------------------

STATE_OF: Final = {
    "pass": "pass",
    "fail": "fail",
    "not_checked": "not-checked",
    "pending": "pending",
}
RANK: Final = {"fail": 0, "pending": 1, "not-checked": 2, "info": 3, "pass": 4}  # worst first
UNCHECKED_STATES: Final = frozenset({"not-checked", "pending"})

# result filter keys -> the states a row must have; "unchecked" is not checked plus pending
FILTERS: Final[tuple[tuple[str, str, frozenset[str] | None], ...]] = (
    ("all", strings.CHECKS_FILTER_ALL, None),
    ("fail", strings.CHECKS_FILTER_FAIL, frozenset({"fail"})),
    ("unchecked", strings.CHECKS_FILTER_UNCHECKED, UNCHECKED_STATES),
    ("pending", strings.CHECKS_FILTER_PENDING, frozenset({"pending"})),
    ("not-checked", strings.CHECKS_FILTER_NOT_CHECKED, frozenset({"not-checked"})),
    ("pass", strings.CHECKS_FILTER_PASS, frozenset({"pass"})),
)


def _map(row: object) -> Mapping[str, Any]:
    """A table row of this module (always a dict) as a mapping."""
    return cast(Mapping[str, Any], row)


def rule_state(r: RuleResult) -> tuple[str, str]:
    """The state key and the words shown in the Result cell of a rule."""
    state = STATE_OF[r.status]
    if state == "pass" and r.placeholder_files:
        return state, strings.CHECKS_RESULT_PLACEHOLDER
    return state, STATES[state].label


def _where(m: MissingValue) -> str:
    return m.where or m.what


def result_tip(r: RuleResult) -> str:
    if r.rule_id == by_rule.UNCHECKED:  # the rule that lists what the others could not look at
        return strings.CHECKS_TIP_NOTES
    if r.status == "pass" and r.placeholder_files:
        return strings.CHECKS_TIP_PASS_PLACEHOLDER.format(", ".join(r.placeholder_files))
    waiting = [_where(m) for m in r.missing]
    return "\n".join(waiting[:6]) if waiting and r.status != "fail" else ""


def rule_row(r: RuleResult) -> dict[str, Any]:
    state, text = rule_state(r)
    tip = (
        strings.CHECKS_TIP_REQUIREMENTS.format(", ".join(r.sources))
        if r.sources
        else strings.CHECKS_TIP_NO_REQUIREMENTS
    )
    search = " ".join(
        (r.rule_id, r.topic, text, r.severity, *r.sources, *(m.key or "" for m in r.missing))
    ).lower()
    return {
        "id": r.rule_id,
        "topic": r.topic,
        "severity": r.severity,
        "result": (RANK[state], text),
        "state": state,
        "count": r.count,
        "waived": r.waived,
        "tip": tip,
        "result_tip": result_tip(r),
        "search": search,
        "rule": r,
    }


RULE_COLUMNS: Final = (
    Column("id", strings.CHECKS_COL_ID, mono=True, tooltip="tip", width=190),
    Column("topic", strings.CHECKS_COL_RULE, tooltip="tip", width=230),
    Column(
        "severity",
        strings.CHECKS_COL_SEVERITY,
        fmt=lambda v: strings.CHECKS_SEVERITY.get(str(v), str(v)),
        sort_key=lambda v: {"error": 0, "warning": 1, "info": 2}.get(str(v), 3),
        width=90,
    ),
    Column(
        "result",
        strings.CHECKS_COL_RESULT,
        state="state",
        fmt=lambda v: str(v[1]),
        sort_key=lambda v: v[0],
        tooltip="result_tip",
        width=210,
    ),
    Column("count", strings.CHECKS_COL_OPEN, numeric=True, width=70),
    Column("waived", strings.CHECKS_COL_WAIVED, numeric=True, width=80),
)


class RulesModel(DictTableModel):
    """The rules table: a row for each `RuleResult`."""

    def __init__(self, theme: ThemeManager) -> None:
        super().__init__(RULE_COLUMNS, (), theme)

    def set_results(self, results: Sequence[RuleResult]) -> bool:
        """Show these results. The same number of rows keeps the view's selection and scroll
        position; returns True when the rows were replaced instead."""
        return self.update_rows([rule_row(r) for r in results])

    def result_at(self, source_row: int) -> RuleResult:
        return cast(RuleResult, _map(self.row(source_row))["rule"])

    def row_of(self, rule_id: str) -> int | None:
        for i, row in enumerate(self.rows()):
            if _map(row)["id"] == rule_id:
                return i
        return None


OBJECT_COLUMNS: Final = (
    Column("object", strings.CHECKS_OBJ_OBJECT, mono=True, width=170),
    Column("message", strings.CHECKS_OBJ_MESSAGE, width=420),
    Column("severity", strings.CHECKS_OBJ_SEVERITY, width=90),
    Column("waiver", strings.CHECKS_OBJ_WAIVER, width=200),
)


def object_row(f: Finding) -> dict[str, Any]:
    return {
        "object": f.object_id or strings.CHECKS_WHOLE_DESIGN,
        "message": f.title,
        "severity": strings.CHECKS_SEVERITY.get(f.severity, f.severity),
        "waiver": f.waiver.justification if f.waiver is not None else "",
        "object_id": f.object_id,
        "finding": f,
    }


def pending_summary(ctl: EditorController) -> tuple[int, int]:
    """(rules not checked or pending, required values still missing) for the status-bar link.
    The first is 0 until a check has finished; the second is the length of the hand-over list
    `configcheck.missing`."""
    results = ctl.drc_rule_results()
    unchecked = 0
    if results:
        s = by_rule.summary(results)
        unchecked = s.not_checked + s.pending
    return unchecked, len(configcheck.missing(ctl.project))


class PendingValuesLink(QPushButton):
    """ "4 values pending · 12 rules not checked" for the status bar. Hidden when nothing is
    pending. Clicking it (or Enter) emits `filterRequested("unchecked")`; connect that to
    `ChecksPanel.set_result_filter` and show the Checks tab."""

    filterRequested = Signal(str)

    def __init__(self, ctl: EditorController, theme: ThemeManager) -> None:
        super().__init__()
        self.ctl, self.theme = ctl, theme
        self.setObjectName("pending-values-link")
        self.setFlat(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAccessibleName(strings.PENDING_LINK_NAME)
        self.setIcon(icon("pending", theme, "pending"))
        self.clicked.connect(lambda: self.filterRequested.emit("unchecked"))
        for signal in (ctl.drcChanged, ctl.drcStateChanged, ctl.stateChanged):
            signal.connect(self.update_text)
        ctl.changed.connect(lambda _d: self.update_text())
        self.update_text()

    def update_text(self) -> None:
        unchecked, values = pending_summary(self.ctl)
        if values and unchecked:
            text = strings.PENDING_LINK.format(values=values, rules=unchecked)
        elif values:
            text = strings.PENDING_LINK_VALUES.format(values)
        elif unchecked:
            text = strings.PENDING_LINK_RULES.format(unchecked)
        else:
            text = ""
        self.setText(text)
        self.setToolTip(strings.PENDING_LINK_TIP)
        self.setAccessibleName(
            f"{strings.PENDING_LINK_NAME}: {text}" if text else strings.PENDING_LINK_NAME
        )
        self.setVisible(bool(text))


# ---- the details of one rule ------------------------------------------------------------------------


class RuleDetails(QWidget):
    """What one rule found and what it needs."""

    showRequested = Signal(str)  # object id
    supplyRequested = Signal(str, str)  # config file, key

    def __init__(
        self, theme: ThemeManager, settings: QSettings | None = None, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.theme = theme
        self.setObjectName("checks-details")
        self.result: RuleResult | None = None
        lay = QVBoxLayout(self)
        lay.setContentsMargins(theme.space(8), theme.space(8), theme.space(8), theme.space(8))
        lay.setSpacing(theme.space(8))
        head = QHBoxLayout()
        self.id_label = QLabel()
        self.id_label.setObjectName("checks-detail-id")
        mark_mono(self.id_label)
        self.topic_label = QLabel()
        self.topic_label.setObjectName("checks-detail-topic")
        self.chip = StateChip(theme, "not-checked")
        self.chip.setObjectName("checks-detail-chip")
        head.addWidget(self.id_label)
        head.addWidget(self.topic_label, 1)
        head.addWidget(self.chip)
        lay.addLayout(head)
        self.requirements = QLabel()
        self.requirements.setObjectName("checks-detail-requirements")
        self.requirements.setWordWrap(True)
        self.requirements.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        mark_mono(self.requirements)
        lay.addWidget(self.requirements)
        self.note = muted("")
        self.note.setObjectName("checks-detail-note")
        lay.addWidget(self.note)
        self.missing_box = QWidget()
        self.missing_box.setObjectName("checks-missing")
        self.missing_lay = QVBoxLayout(self.missing_box)
        self.missing_lay.setContentsMargins(0, 0, 0, 0)
        self.missing_lay.setSpacing(theme.space(8))
        lay.addWidget(self.missing_box)
        self.objects_heading = heading("")
        lay.addWidget(self.objects_heading)
        self.objects = TableView(
            DictTableModel(OBJECT_COLUMNS, (), theme),
            theme,
            name=strings.CHECKS_OBJECTS_TABLE.format(""),
            settings=settings,
            key="checks-objects",
        )
        self.objects.setObjectName("checks-objects")
        self.objects.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.objects.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.objects.setTabKeyNavigation(False)  # Tab leaves the table; the arrows move in it
        self.objects.setMinimumHeight(theme.px(96))
        theme.changed.connect(self._select_rows)
        self.objects.activated.connect(self._activated)
        self.objects.selectionModel().currentRowChanged.connect(lambda *_: self._sync_show())
        lay.addWidget(self.objects, 1)
        row = QHBoxLayout()
        self.show_btn = QPushButton()
        self.show_btn.setObjectName("checks-show")
        icon_button(
            self.show_btn, "search", theme, strings.SHOW_ON_DIAGRAM, "Enter", text=strings.SHOW
        )
        self.show_btn.setToolTip(strings.CHECKS_SHOW_TIP)
        self.show_btn.clicked.connect(self.show_current)
        row.addWidget(self.show_btn)
        self.none_label = muted(strings.CHECKS_OBJECTS_NONE)
        self.none_label.setObjectName("checks-objects-none")
        row.addWidget(self.none_label, 1)
        lay.addLayout(row)
        self.notes_heading = heading(strings.CHECKS_NOTES_HEADING)
        lay.addWidget(self.notes_heading)
        self.notes_box = QWidget()
        self.notes_lay = QVBoxLayout(self.notes_box)
        self.notes_lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self.notes_box)
        self.supply_buttons: list[QPushButton] = []
        self.set_result(None)

    def _select_rows(self) -> None:
        self.objects.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.objects.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)

    # ---- content ---------------------------------------------------------------------------------
    def set_result(self, r: RuleResult | None) -> None:
        if r is not None and r == self.result:
            return  # nothing new: keep the selection and the keyboard focus where they are
        self.result = r
        clear_layout(self.missing_lay)
        clear_layout(self.notes_lay)
        self.supply_buttons = []
        shown = r is not None
        for w in (self.id_label, self.topic_label, self.chip, self.requirements, self.note):
            w.setVisible(shown)
        if r is None:
            self.objects_heading.setText(strings.CHECKS_PICK_A_RULE.upper())
            self.objects.source.set_rows([])
            self.objects.setVisible(False)
            self.show_btn.setVisible(False)
            self.none_label.setVisible(False)
            self.missing_box.setVisible(False)
            self.notes_heading.setVisible(False)
            self.notes_box.setVisible(False)
            return
        state, text = rule_state(r)
        self.id_label.setText(r.rule_id)
        self.topic_label.setText(f"<b>{r.topic}</b>")
        self.chip.set_state(state, text if text != STATES[state].label else None)
        self.requirements.setText(
            strings.CHECKS_DETAIL_REQUIREMENTS.format(", ".join(r.sources)) if r.sources else ""
        )
        self.requirements.setVisible(bool(r.sources))
        note = ""
        if r.rule_id == by_rule.UNCHECKED:
            note = strings.CHECKS_TIP_NOTES
        elif r.status == "pass" and r.placeholder_files:
            note = strings.CHECKS_PLACEHOLDER_NOTE.format(", ".join(r.placeholder_files))
        self.note.setText(note)
        self.note.setVisible(bool(note))
        self._fill_missing(r)
        self._fill_objects(r)
        self._fill_notes(r)

    def _fill_missing(self, r: RuleResult) -> None:
        self.missing_box.setVisible(bool(r.missing))
        if not r.missing:
            return
        self.missing_lay.addWidget(heading(strings.CHECKS_MISSING_HEADING))
        for m in r.missing:
            self.missing_lay.addWidget(self._missing_row(m))

    def _missing_row(self, m: MissingValue) -> QWidget:
        box = QFrame()
        box.setObjectName(f"checks-missing-{m.file or 'x'}-{m.key or 'x'}")
        lay = QHBoxLayout(box)
        lay.setContentsMargins(0, 0, 0, 0)
        text = QVBoxLayout()
        chip = StateChip(self.theme, "pending" if m.kind == "config" else "not-checked")
        lay.addWidget(chip, 0, Qt.AlignmentFlag.AlignTop)
        if m.kind == "config" and m.file and m.key:
            info = configcheck.FIELD_INFO.get((m.file, m.key))
            label = info.label if info else m.key
            unit = info.unit if info else ""
            title = QLabel(f"<b>{label}</b>")
            title.setObjectName("checks-missing-label")
            where = QLabel(m.where)
            where.setObjectName("checks-missing-where")
            where.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            mark_mono(where)
            what = muted(m.what + (f". {strings.CHECKS_MISSING_UNIT.format(unit)}" if unit else ""))
            what.setObjectName("checks-missing-what")
            for w in (title, where, what):
                text.addWidget(w)
            lay.addLayout(text, 1)
            button = QPushButton()
            button.setObjectName(f"supply-{m.file}-{m.key}")
            icon_button(
                button, "pending", self.theme, strings.CHECKS_SUPPLY_NAME.format(label),
                text=strings.CHECKS_SUPPLY,
            )  # fmt: skip
            button.setToolTip(strings.CHECKS_SUPPLY_TIP)
            file, key = m.file, m.key
            button.clicked.connect(lambda: self.supplyRequested.emit(file, key))
            lay.addWidget(button, 0, Qt.AlignmentFlag.AlignTop)
            self.supply_buttons.append(button)
        else:
            template = (
                strings.CHECKS_MISSING_ANALYSIS
                if m.kind == "analysis"
                else strings.CHECKS_MISSING_DATA
            )
            what = muted(template.format(m.what))
            what.setObjectName("checks-missing-what")
            text.addWidget(what)
            lay.addLayout(text, 1)
        return box

    def _fill_objects(self, r: RuleResult) -> None:
        rows = [object_row(f) for f in r.findings]
        self.objects.set_rows(rows)
        n = len(rows)
        silent = r.status == "pending" and n == 0  # the rule did not run: it found nothing to list
        self.objects_heading.setVisible(not silent)
        self.objects_heading.setText(strings.CHECKS_OBJECTS_HEADING.format(r.count).upper())
        self.objects.setAccessibleName(strings.CHECKS_OBJECTS_TABLE.format(r.topic))
        self.objects.setVisible(n > 0)
        self.show_btn.setVisible(n > 0)
        self.none_label.setText(
            strings.CHECKS_OBJECTS_NONE_PARTLY
            if r.status == "not_checked"
            else strings.CHECKS_OBJECTS_NONE
        )
        self.none_label.setVisible(n == 0 and not silent)
        if n:
            self.objects.selectRow(0)
        self._sync_show()

    def _fill_notes(self, r: RuleResult) -> None:
        said = {m.what for m in r.missing if m.kind != "config"}
        notes = [n for n in r.notes if n not in said]
        self.notes_heading.setVisible(bool(notes))
        self.notes_box.setVisible(bool(notes))
        for n in notes:
            label = muted(n)
            label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            self.notes_lay.addWidget(label)

    # ---- the objects --------------------------------------------------------------------------------
    def current_object(self) -> str:
        index = self.objects.currentIndex()
        if not index.isValid():
            return ""
        row = self.objects.row_at(index)
        return str(_map(row)["object_id"])

    def _sync_show(self) -> None:
        self.show_btn.setEnabled(bool(self.current_object()))

    def show_current(self) -> None:
        oid = self.current_object()
        if oid:
            self.showRequested.emit(oid)

    def _activated(self, index: QModelIndex) -> None:
        if index.isValid():
            self.show_current()

    def tab_chain(self) -> list[QWidget]:
        """The widgets Tab visits, in order."""
        chain: list[QWidget] = list(self.supply_buttons)
        if self.objects.isVisibleTo(self):
            chain += [self.objects, self.show_btn]
        return chain

    def focus_first(self) -> bool:
        chain = self.tab_chain()
        if chain:
            chain[0].setFocus(Qt.FocusReason.TabFocusReason)
        return bool(chain)


# ---- the tab ---------------------------------------------------------------------------------------


class ChecksPanel(QWidget):
    """The Checks tab. See the module text."""

    showRequested = Signal(str)  # object id of an offending object
    ruleSelected = Signal(str)  # rule id ("" when nothing is selected)
    resultFilterChanged = Signal(str)  # key of FILTERS

    def __init__(
        self,
        ctl: EditorController,
        theme: ThemeManager,
        parent: QWidget | None = None,
        *,
        settings: QSettings | None = None,
    ) -> None:
        super().__init__(parent)
        self.ctl, self.theme = ctl, theme
        self.setObjectName("checks")
        self.setAccessibleName(strings.CHECKS)
        self._dirty = True
        self._results: list[RuleResult] | None = None
        self._selected = ""
        self._split_set = False
        self._config_dialog: ConfigValueDialog | None = None
        self.details: RuleDetails
        lay = QVBoxLayout(self)
        lay.setContentsMargins(theme.space(8), theme.space(8), theme.space(8), theme.space(8))
        lay.setSpacing(theme.space(8))
        lay.addLayout(self._build_strip())
        self.banner = self._build_banner()
        lay.addWidget(self.banner)
        lay.addLayout(self._build_filters())
        self.model = RulesModel(theme)
        self.table = TableView(
            self.model, theme, name=strings.CHECKS_TABLE, settings=settings, key="checks-rules"
        )
        self.table.setObjectName("checks-rules")
        self.table.setTabKeyNavigation(False)  # Tab leaves the table; the arrows move in it
        self._select_rows()
        theme.changed.connect(self._select_rows)
        self.table.activated.connect(lambda _i: self.details.focus_first())
        self.table.selectionModel().currentRowChanged.connect(self._on_current)
        self.empty = QLabel()
        self.empty.setObjectName("checks-empty")
        self.empty.setWordWrap(True)
        self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty.setProperty("muted", True)
        self.stack = QStackedWidget()
        self.stack.addWidget(self.table)
        self.stack.addWidget(self.empty)
        self.details = RuleDetails(theme, settings)
        self.details.showRequested.connect(self.showRequested)
        self.details.supplyRequested.connect(lambda f, k: self.open_config(f, k))
        scroll = QScrollArea()
        scroll.setObjectName("checks-details-scroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(self.details)
        scroll.setAccessibleName(strings.CHECKS_DETAILS)
        self.split = split = QSplitter(Qt.Orientation.Vertical)
        split.setChildrenCollapsible(False)
        split.addWidget(self.stack)
        split.addWidget(scroll)
        split.setStretchFactor(0, 3)
        split.setStretchFactor(1, 2)
        lay.addWidget(split, 1)
        find = QShortcut(QKeySequence.StandardKey.Find, self)
        find.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        find.activated.connect(self.focus_filter)
        for signal in (ctl.drcChanged, ctl.drcStateChanged, ctl.stateChanged):
            signal.connect(self._invalidate)
        ctl.changed.connect(lambda _d: self._invalidate())
        self.refresh()

    # ---- building ----------------------------------------------------------------------------------
    def _build_strip(self) -> QHBoxLayout:
        theme = self.theme
        row = QHBoxLayout()
        row.setSpacing(theme.space(8))
        self.strip = QWidget()
        self.strip.setObjectName("checks-summary")
        strip = QHBoxLayout(self.strip)
        strip.setContentsMargins(0, 0, 0, 0)
        strip.setSpacing(theme.space(4))
        self.total_label = QLabel()
        self.total_label.setObjectName("checks-total")
        strip.addWidget(self.total_label)
        self.segments: dict[str, QToolButton] = {}
        for key, name, role, target in (
            ("pass", "pass", "success", "pass"),
            ("fail", "fail", "error", "fail"),
            ("unchecked", "not-checked", "not-checked", "unchecked"),
            ("values", "pending", "pending", "pending"),
        ):
            if key != "pass":
                strip.addWidget(self._dot())
            b = QToolButton()
            b.setObjectName(f"checks-count-{key}")
            b.setIcon(icon(name, theme, role))
            b.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
            b.setAutoRaise(True)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda _c=False, t=target: self.set_result_filter(t))
            strip.addWidget(b)
            self.segments[key] = b
        row.addWidget(self.strip)
        self.status = QLabel()
        self.status.setObjectName("checks-status")
        self.status.setWordWrap(True)
        row.addWidget(self.status, 1)
        self.cancel_btn = QPushButton(strings.CHECKS_CANCEL)
        self.cancel_btn.setObjectName("checks-cancel")
        self.cancel_btn.setFlat(True)
        icon_button(
            self.cancel_btn, "close", theme, strings.CHECKS_CANCEL_TIP, text=strings.CHECKS_CANCEL
        )
        self.cancel_btn.clicked.connect(self.ctl.cancel_check)
        self.again_btn = QPushButton(strings.CHECKS_AGAIN)
        self.again_btn.setObjectName("checks-again")
        icon_button(
            self.again_btn, "refresh", theme, strings.CHECKS_AGAIN_TIP, text=strings.CHECKS_AGAIN
        )
        self.again_btn.clicked.connect(self.ctl.check_now)
        self.fix_all_btn = QPushButton()  # one step for every problem that has a one-click fix
        self.fix_all_btn.setObjectName("checks-fix-all")
        icon_button(
            self.fix_all_btn,
            "check",
            theme,
            strings.CHECKS_FIX_ALL_TIP.format(0),
            text=strings.CHECKS_FIX_ALL.format(0),
        )
        self.fix_all_btn.clicked.connect(self.ctl.fix_all)
        row.addWidget(self.fix_all_btn)
        row.addWidget(self.cancel_btn)
        row.addWidget(self.again_btn)
        return row

    def _dot(self) -> QLabel:
        dot = QLabel("·")
        dot.setProperty("muted", True)
        dot.setAccessibleName("")
        return dot

    def _build_banner(self) -> QFrame:
        banner = QFrame()
        banner.setObjectName("checks-failure-banner")
        banner.setProperty("card", True)
        banner.setProperty("severity", "error")
        row = QHBoxLayout(banner)
        row.setContentsMargins(
            self.theme.space(8), self.theme.space(8), self.theme.space(8), self.theme.space(8)
        )
        row.addWidget(StateChip(self.theme, "fail", strings.CHECKS_FAILED_TITLE))
        self.banner_text = QLabel()
        self.banner_text.setObjectName("checks-failure-text")
        self.banner_text.setWordWrap(True)
        self.banner_text.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        row.addWidget(self.banner_text, 1)
        retry = QPushButton()
        retry.setObjectName("checks-failure-retry")
        icon_button(
            retry, "refresh", self.theme, strings.CHECKS_AGAIN_TIP, text=strings.CHECKS_AGAIN
        )
        retry.clicked.connect(self.ctl.check_now)
        row.addWidget(retry)
        banner.setVisible(False)
        return banner

    def _build_filters(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(self.theme.space(8))
        label = QLabel(strings.CHECKS_FILTER_LABEL)
        self.filter_box = QComboBox()
        self.filter_box.setObjectName("checks-filter")
        self.filter_box.setAccessibleName(strings.CHECKS_FILTER_LABEL)
        self.filter_box.setToolTip(strings.CHECKS_FILTER_LABEL)
        for key, text, _states in FILTERS:
            self.filter_box.addItem(text, key)
        label.setBuddy(self.filter_box)
        self.filter_text = QLineEdit()
        self.filter_text.setObjectName("checks-filter-text")
        self.filter_text.setAccessibleName(strings.CHECKS_FILTER_TEXT)
        self.filter_text.setPlaceholderText(strings.CHECKS_FILTER_TEXT_HINT)
        self.filter_text.setToolTip(f"{strings.CHECKS_FILTER_TEXT} (Ctrl+F)")
        self.filter_text.setClearButtonEnabled(True)
        self.count_label = muted("")
        self.count_label.setObjectName("checks-count")
        self.count_label.setWordWrap(False)
        row.addWidget(label)
        row.addWidget(self.filter_box)
        row.addWidget(self.filter_text, 1)
        row.addWidget(self.count_label)
        self.filter_box.currentIndexChanged.connect(self._filter_changed)
        self.filter_text.textChanged.connect(self._text_changed)
        return row

    def _select_rows(self) -> None:
        """Whole rows are selected (one rule at a time); the Rule column takes the spare width."""
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        head = self.table.horizontalHeader()
        head.setStretchLastSection(False)
        head.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)

    # ---- filters -----------------------------------------------------------------------------------
    def result_filter(self) -> str:
        return str(self.filter_box.currentData())

    def set_result_filter(self, key: str) -> None:
        """Show only rules with this result: "all", "pass", "fail", "not-checked", "pending" or
        "unchecked" (not checked plus pending)."""
        i = self.filter_box.findData(key)
        if i >= 0:
            self.filter_box.setCurrentIndex(i)

    def set_text_filter(self, text: str) -> None:
        self.filter_text.setText(text)

    def focus_filter(self) -> None:
        self.filter_text.setFocus(Qt.FocusReason.ShortcutFocusReason)
        self.filter_text.selectAll()

    def _filter_changed(self) -> None:
        key = self.result_filter()
        states = next((s for k, _t, s in FILTERS if k == key), None)
        self.table.proxy.set_states(states)
        self._after_filter()
        self.resultFilterChanged.emit(key)

    def _text_changed(self, text: str) -> None:
        words = tuple(text.lower().split())
        self.table.proxy.set_predicate(
            (lambda row: all(w in str(_map(row)["search"]) for w in words)) if words else None
        )
        self._after_filter()

    def _after_filter(self) -> None:
        shown = self.table.proxy.rowCount()
        self.count_label.setText(strings.CHECKS_SHOWING.format(shown, self.model.rowCount()))
        if self._selected and self.table.currentIndex().isValid() is False:
            self.select_rule(self._selected, announce=False)
        if shown == 0:
            self.details.set_result(None)

    # ---- state -----------------------------------------------------------------------------------------
    def _invalidate(self) -> None:
        self._dirty = True
        if self.isVisible():
            self.refresh()

    def showEvent(self, event: object) -> None:
        super().showEvent(event)  # type: ignore[arg-type]
        if self._dirty:
            self.refresh()
        if not self._split_set:  # the rules get a little over half, the details the rest
            self._split_set = True
            height = max(self.split.height(), self.height() - self.theme.px(120))
            self.split.setSizes([int(height * 0.55), int(height * 0.45)])

    def results(self) -> list[RuleResult]:
        return list(self._results or [])

    def summary_text(self) -> str:
        """ "34 rules: 20 passed · 2 failed · 12 not checked · 4 pending values", or "" before a
        check has finished."""
        results = self._results
        if not results:
            return ""
        s = by_rule.summary(results)
        return strings.CHECKS_SUMMARY.format(
            total=s.total,
            passed=s.passed,
            failed=s.failed,
            unchecked=s.not_checked + s.pending,
            values=len(configcheck.missing(self.ctl.project)),
        )

    def refresh(self) -> None:
        self._dirty = False
        ctl = self.ctl
        results = ctl.drc_rule_results()
        if results is not self._results:
            self._results = results
            self._show_results(results)
        self._update_strip(results)

    def _show_results(self, results: list[RuleResult]) -> None:
        replaced = self.model.set_results(results)
        self.stack.setCurrentWidget(self.table if results else self.empty)
        self._after_filter()
        if replaced or self._selected:
            self._reselect()
        self._retab()

    def _reselect(self) -> None:
        row = self.model.row_of(self._selected) if self._selected else None
        if row is not None:
            self.select_rule(self._selected, announce=False)
            self.details.set_result(self.model.result_at(row))  # the same rule, new result
        else:
            self._selected = ""
            self.details.set_result(None)

    def _update_strip(self, results: list[RuleResult]) -> None:
        ctl = self.ctl
        busy, current, error = ctl.drc_busy(), ctl.drc_current, ctl.drc_error
        self.banner.setVisible(error is not None)
        self.banner_text.setText(error or "")
        if error is not None:
            self.status.setText("")
        elif busy or not current:
            self.status.setText(strings.CHECKS_CHECKING if busy else strings.CHECKS_CANCELLED)
        else:
            self.status.setText("")
        if not results and not busy and error is None:
            self.empty.setText(strings.CHECKS_NO_RESULT)
        elif not results:
            self.empty.setText(
                strings.CHECKS_CHECKING if error is None else strings.CHECKS_FAILED_TITLE
            )
        self.cancel_btn.setVisible(busy)
        self.again_btn.setVisible(not busy and not current and error is None)
        self._update_fix_all()
        self.strip.setVisible(bool(results))
        if results:
            s = by_rule.summary(results)
            values = len(configcheck.missing(ctl.project))
            unchecked = s.not_checked + s.pending
            self.total_label.setText(strings.CHECKS_RULES_LABEL.format(s.total))
            for key, text in (
                ("pass", strings.CHECKS_SUMMARY_PASSED.format(s.passed)),
                ("fail", strings.CHECKS_SUMMARY_FAILED.format(s.failed)),
                ("unchecked", strings.CHECKS_SUMMARY_UNCHECKED.format(unchecked)),
                ("values", strings.CHECKS_SUMMARY_VALUES.format(values)),
            ):
                b = self.segments[key]
                b.setText(text)
                b.setAccessibleName(f"{text}: {strings.CHECKS_SEGMENT_TIP}")
                b.setToolTip(strings.CHECKS_SEGMENT_TIP)
            self.strip.setAccessibleName(self.summary_text())
            self.strip.setToolTip(self._placeholder_note(results))

    def _update_fix_all(self) -> None:
        """Fix all (n): n open problems have a one-click fix. Disabled, with the reason as its
        tooltip and description, when n is 0 or the project is read-only. (It does not wait for a
        running check: like the Fix button of a card it works from the findings shown, and a fix
        that no longer applies is left out and named.)"""
        ctl = self.ctl
        n = ctl.fixable_count()
        if ctl.read_only:
            reason = strings.WHY_READ_ONLY
        elif n == 0:
            reason = strings.CHECKS_FIX_ALL_NONE
        else:
            reason = ""
        text = strings.CHECKS_FIX_ALL.format(n)
        tip = strings.CHECKS_FIX_ALL_TIP.format(strings.problems_text(n))
        btn = self.fix_all_btn
        btn.setText(text)
        btn.setAccessibleName(text)
        btn.setEnabled(not reason)
        btn.setToolTip(f"{text}: {reason}" if reason else tip)
        btn.setAccessibleDescription(reason or tip)

    @staticmethod
    def _placeholder_note(results: Sequence[RuleResult]) -> str:
        n = sum(1 for r in results if r.status == "pass" and r.placeholder_files)
        return strings.CHECKS_PLACEHOLDER_PASSES.format(n) if n else ""

    # ---- selection ----------------------------------------------------------------------------------------
    def current_rule_id(self) -> str:
        return self._selected

    def visible_rule_ids(self) -> list[str]:
        proxy = self.table.proxy
        out: list[str] = []
        for r in range(proxy.rowCount()):
            row = self.table.row_at(proxy.index(r, 0))
            out.append(str(_map(row)["id"]))
        return out

    def select_rule(self, rule_id: str, *, announce: bool = True) -> bool:
        """Select a rule and show its details. False when no such rule is in the table or the
        filter hides it."""
        src = self.model.row_of(rule_id)
        if src is None:
            return False
        index = self.table.proxy.mapFromSource(self.model.index(src, 0))
        if not index.isValid():
            return False
        self.table.setCurrentIndex(index)
        self.table.selectRow(index.row())
        self.table.scrollTo(index)
        if announce:
            self._selected = rule_id
        return True

    def _on_current(self, current: QModelIndex, _previous: QModelIndex) -> None:
        if not current.isValid():
            return
        row = self.table.row_at(current)
        r = cast(RuleResult, _map(row)["rule"])
        self._selected = r.rule_id
        self.details.set_result(r)
        self._retab()
        self.ruleSelected.emit(r.rule_id)

    # ---- values -------------------------------------------------------------------------------------------
    def open_config(self, file: str | None = None, key: str | None = None) -> ConfigValueDialog:
        """Open the engineering values (a window of its own; the editor stays usable). A dialog
        that is already open is brought forward and moved to the value."""
        dlg = self._config_dialog
        if dlg is not None and dlg.isVisible():
            dlg.focus_value(file, key)
            dlg.raise_()
            dlg.activateWindow()
            return dlg
        dlg = ConfigValueDialog(self.ctl, self.theme, file, key, parent=self.window())
        dlg.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self._config_dialog = dlg
        dlg.show()
        return dlg

    def config_dialog(self) -> ConfigValueDialog | None:
        dlg = self._config_dialog
        return dlg if dlg is not None and dlg.isVisible() else None

    # ---- keyboard -----------------------------------------------------------------------------------------
    def _retab(self) -> None:
        chain: list[QWidget] = [
            *self.segments.values(),
            self.filter_box,
            self.filter_text,
            self.table,
            *self.details.tab_chain(),
        ]
        for a, b in zip(chain, chain[1:], strict=False):
            QWidget.setTabOrder(a, b)
