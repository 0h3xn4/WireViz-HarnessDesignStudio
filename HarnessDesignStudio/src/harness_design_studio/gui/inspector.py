"""Inspector (SH-8, SC-8, CV-7, CV-9, CV-23): the right dock, with the tabs Inspector, Why and Problems.

    inspector = Inspector(ctl, theme, problems=problems_panel)
    inspector.reviseRequested.connect(...)   # harness ID: "Start new revision" was pressed
    inspector.showRequested.connect(...)     # (kind, id): a row of "Used in" was opened
    inspector.show_object("harness", "W001") # point it at something the canvas cannot select

The **Inspector** tab wraps the existing `PropertiesPanel` (unit and link forms are not rewritten)
and adds around it: a banner when the object is locked by a released harness or is itself a
harness (state chip, the sentence from `lockview.lock_reason`, a "Start new revision" button);
the fields a release forbids changed, disabled with the reason as their tooltip (the cosmetic ones
stay editable); a **Used in** table (`core.usedby`); and, for a part, interface type, harness or
configuration file, a table of its properties with a status chip per engineering value (not set,
unreviewed placeholder, locked). The **Why** tab is a `WhyPanel`. The **Problems** tab hosts the
`ProblemsPanel` that is handed in; this module does not touch it.
"""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from PySide6.QtCore import QModelIndex, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QResizeEvent, QShowEvent
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QStackedWidget,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from harness_design_studio.core import configcheck, describe
from harness_design_studio.core.build_data import plan_set_part_tool
from harness_design_studio.core.edit import EditError
from harness_design_studio.core.model import Project
from harness_design_studio.core.usedby import KINDS as USED_KINDS
from harness_design_studio.core.usedby import Use, used_by
from harness_design_studio.core.vcs.lockview import (
    cosmetic_fields,
    field_lock_reason,
    lock_reason,
    locked_objects,
)
from harness_design_studio.gui import strings
from harness_design_studio.gui.controller import LIST_DELAY_MS, EditorController
from harness_design_studio.gui.icons import icon_button
from harness_design_studio.gui.panels import PropertiesPanel, heading, muted
from harness_design_studio.gui.states import StateChip
from harness_design_studio.gui.tables import Column, DictTableModel, TableView
from harness_design_studio.gui.theme import ThemeManager
from harness_design_studio.gui.why_panel import WhyPanel

TABS = ("inspector", "why", "problems")
FACT_KINDS = ("harness", "part", "interface_type", "config")  # shown as a table, not a form
MAX_TABLE_ROWS = 4


# ---- the banner (no Qt) --------------------------------------------------------------------------


@dataclass(frozen=True)
class BannerInfo:
    state: str  # a key of gui.states
    chip: str  # the text on the chip
    sentence: str
    revise: str | None  # the released harness to start a new revision of, or None


def banner_for(project: Project, kind: str, object_id: str) -> BannerInfo | None:
    """What the banner above an object says, or None when there is nothing to say (the object is
    free to change)."""
    if kind == "harness":
        h = project.harnesses.get(object_id)
        if h is None:
            return None
        state = describe.harness_state(h)
        if state == "released":
            word = strings.STATE_LABELS["released"]
            sentence = lock_reason(project, "harness", object_id) or ""
            return BannerInfo(state, f"{word} {h.revision}", sentence, h.id)
        sentence = {
            "in-review": strings.INS_BANNER_IN_REVIEW,
            "revised": strings.INS_BANNER_REVISED,
            "draft": strings.INS_BANNER_DRAFT,
        }[state].format(h.id, h.revision)
        text = strings.STATE_LABELS[state]
        return BannerInfo(
            state, f"{text} {h.revision}" if state == "revised" else text, sentence, None
        )
    locked = locked_objects(project)
    refs = locked.get((kind, object_id))
    if not refs:
        return None
    sentence = lock_reason(project, kind, object_id, locked) or ""
    if cosmetic_fields(kind):
        sentence = f"{sentence} {strings.INS_BANNER_COSMETIC}"
    ref = refs[0]
    return BannerInfo(
        "released",
        strings.INS_BANNER_RELEASED.format(ref.harness_id, ref.revision),
        sentence,
        ref.harness_id,
    )


class Banner(QFrame):
    """The strip above the form: state chip, sentence, and the revise button when it applies."""

    reviseRequested = Signal(str)

    def __init__(self, theme: ThemeManager) -> None:
        super().__init__()
        self.theme = theme
        self.setProperty("card", True)  # the same card as the Problems and Why lists
        self.setProperty("severity", "info")
        self.setObjectName("inspector-banner")
        lay = QVBoxLayout(self)
        lay.setSpacing(theme.space(8))
        self.chip = StateChip(theme, "released")
        lay.addWidget(self.chip, 0, Qt.AlignmentFlag.AlignLeft)
        self.sentence = QLabel()
        self.sentence.setWordWrap(True)
        self.sentence.setObjectName("banner-sentence")
        self.sentence.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        lay.addWidget(self.sentence)
        self.button = QPushButton(strings.INS_REVISE)
        self.button.setObjectName("banner-revise")
        icon_button(self.button, "revise", theme, strings.INS_REVISE, text=strings.INS_REVISE)
        self.button.clicked.connect(self._pressed)
        lay.addWidget(self.button, 0, Qt.AlignmentFlag.AlignLeft)
        self._harness: str | None = None
        self.hide()

    def show_info(self, info: BannerInfo | None, read_only: bool = False) -> None:
        if info is None:
            self._harness = None
            self.hide()
            return
        self.chip.set_state(info.state, info.chip)
        self.sentence.setText(info.sentence)
        self.setAccessibleName(f"{info.chip}. {info.sentence}")
        self._harness = info.revise
        self.button.setVisible(info.revise is not None)
        self.button.setEnabled(not read_only)
        if info.revise is not None:
            self.button.setToolTip(strings.INS_REVISE_TIP.format(info.revise))
        self.show()

    def _pressed(self) -> None:
        if self._harness is not None:
            self.reviseRequested.emit(self._harness)


# ---- tables (no Qt in the row builders) ---------------------------------------------------------


def used_rows(uses: list[Use]) -> list[dict[str, Any]]:
    return [
        {
            "kind": strings.INS_USED_KINDS.get(u.kind, u.kind),
            "id": u.id,
            "via": u.via,
            "key": u.kind,
        }
        for u in uses
    ]


def _fact(
    name: str, value: str = "", status: str = "", state: str | None = None, tip: str = ""
) -> dict[str, Any]:
    return {"name": name, "value": value, "status": status, "state": state, "tip": tip}


def _harness_facts(p: Project, oid: str) -> list[dict[str, Any]]:
    h = p.harnesses[oid]
    L = strings.INS_FACT_LABELS
    state = describe.harness_state(h)
    rows = [
        _fact(L["name"], h.name),
        _fact(L["revision"], h.revision),
        _fact(L["state"], "", strings.STATE_LABELS[state], state),
        _fact(L["interfaces"], str(len(h.interfaces))),
        _fact(L["connectors"], str(len(h.connectors))),
        _fact(L["wires"], str(len(h.wires))),
    ]
    if h.released_on:
        rows.append(_fact(L["released_on"], h.released_on))
    if h.approver:
        rows.append(_fact(L["approver"], h.approver))
    return rows


def _part_facts(p: Project, oid: str) -> list[dict[str, Any]]:
    part = p.parts[oid]
    L = strings.INS_FACT_LABELS
    approval = {"approved": "pass", "pending": "pending", "not_approved": "fail"}[part.approval]
    rows = [
        _fact(L["description"], part.description or ""),
        _fact(L["category"], part.category),
        _fact(L["manufacturer"], part.manufacturer or ""),
        _fact(L["part_number"], part.part_number or ""),
        _fact(L["pins"], str(part.pin_count) if part.pin_count else ""),
        _fact(L["approval"], "", strings.APPROVAL[part.approval], approval),
    ]
    if part.category == "contact":
        rows.append(_fact(strings.INS_FACT_TOOL, part.tool or ""))
    if part.unverified:
        rows.insert(
            0,
            _fact(
                L["name"],
                part.id,
                strings.INS_STATUS_UNVERIFIED,
                "not-checked",
                strings.INS_STATUS_UNVERIFIED_TIP,
            ),
        )
    return rows


def _type_facts(p: Project, oid: str) -> list[dict[str, Any]]:
    t = p.interface_types[oid]
    L = strings.INS_FACT_LABELS
    rows = [
        _fact(L["name"], t.name),
        _fact(L["category"], t.category),
        _fact(L["construction"], t.construction.replace("_", " ")),
        _fact(L["signals"], ", ".join(s.name for s in t.signals)),
    ]
    if t.unverified:
        rows[0] = _fact(
            L["name"],
            t.name,
            strings.INS_STATUS_UNVERIFIED,
            "not-checked",
            strings.INS_STATUS_UNVERIFIED_TIP,
        )
    return rows


def _config_facts(p: Project, oid: str) -> list[dict[str, Any]]:
    cfg = p.config.get(oid)
    L = strings.INS_FACT_LABELS
    if cfg is None:
        return []
    review = (
        _fact(L["placeholder"], strings.INS_FACT_PLACEHOLDER, strings.WHY_PLACEHOLDER, "pending",
              strings.INS_STATUS_UNREVIEWED_TIP.format(oid))
        if cfg.placeholder
        else _fact(L["placeholder"], strings.INS_FACT_REVIEWED)
    )  # fmt: skip
    rows = [review]
    for ev in configcheck.engineering_values(p, include_optional=True):
        if ev.file != oid:
            continue
        value = f"{ev.display} {ev.unit}".strip() if ev.display else ""
        if ev.locked:
            rows.append(_fact(ev.label, value, strings.STATE_LABELS["locked"], "locked", ev.locked))
        elif ev.missing:
            rows.append(
                _fact(ev.label, "", strings.INS_STATUS_NOT_SET, "pending",
                      strings.INS_STATUS_NOT_SET_TIP.format(f"Needed for: {ev.used_by}."))
            )  # fmt: skip
        elif ev.placeholder:
            rows.append(
                _fact(ev.label, value, strings.INS_STATUS_UNREVIEWED, "pending",
                      f"{strings.INS_STATUS_UNREVIEWED_TIP.format(oid)} {ev.source}.")
            )  # fmt: skip
        else:
            rows.append(_fact(ev.label, value, tip=ev.source))
    return rows


_FACTS: dict[str, Callable[[Project, str], list[dict[str, Any]]]] = {
    "harness": _harness_facts,
    "part": _part_facts,
    "interface_type": _type_facts,
    "config": _config_facts,
}


def facts_for(project: Project, kind: str, object_id: str) -> list[dict[str, Any]]:
    """The rows of the properties table of a harness, part, interface type or configuration file."""
    exists: dict[str, Mapping[str, Any]] = {
        "harness": project.harnesses,
        "part": project.parts,
        "interface_type": project.interface_types,
        "config": project.config,
    }
    if kind not in exists or object_id not in exists[kind]:
        return []
    return _FACTS[kind](project, object_id)


FACT_COLUMNS = [
    Column("name", strings.INS_FACT_COLUMNS[0], tooltip="name"),
    Column("value", strings.INS_FACT_COLUMNS[1], tooltip="value"),
    Column("status", strings.INS_FACT_COLUMNS[2], state="state", tooltip="tip"),
]
USED_COLUMNS = [
    Column("kind", strings.INS_USED_COLUMNS[0]),
    Column("id", strings.INS_USED_COLUMNS[1], mono=True),
    Column("via", strings.INS_USED_COLUMNS[2]),
]


def fit_columns(table: TableView, shares: tuple[float, ...], last_min: int) -> None:
    """Size the columns to the width of the table (no sideways scrolling in a narrow dock): each
    column but the last gets its share of what is left after `last_min` px for the last one."""
    width = table.viewport().width()
    head = table.horizontalHeader()
    room = max(0, width - last_min)
    for k, share in enumerate(shares):
        head.resizeSection(k, max(40, int(room * share)))


def _fit_height(table: TableView, rows: int) -> None:
    """Make a table as tall as its rows (up to MAX_TABLE_ROWS), so it does not claim the dock."""
    rows = max(1, min(rows, MAX_TABLE_ROWS))
    height = (
        table.horizontalHeader().sizeHint().height()
        + rows * table.verticalHeader().defaultSectionSize()
    )
    table.setFixedHeight(height + 2 * table.frameWidth() + 2)


# ---- the inspector -------------------------------------------------------------------------------


class Inspector(QWidget):
    """Composite content for the right dock: tabs Inspector / Why / Problems.

    Public attributes: `tabs`, `props` (the wrapped `PropertiesPanel`), `why` (the `WhyPanel`),
    `banner`, `used_table`, `facts_table`. Signals: `reviseRequested(harness_id)`,
    `showRequested(kind, id)`.
    """

    reviseRequested = Signal(str)
    showRequested = Signal(str, str)

    def __init__(
        self,
        ctl: EditorController,
        theme: ThemeManager,
        *,
        props: PropertiesPanel | None = None,
        problems: QWidget | None = None,
    ) -> None:
        super().__init__()
        self.ctl, self.theme = ctl, theme
        self.setObjectName("inspector")
        self.setAccessibleName(strings.INS_NAME)
        self._target: tuple[str, str] | None = None  # None: follow the canvas selection
        self._locked_widgets: dict[QWidget, tuple[bool, str]] = {}
        self._lock_sig: object = None
        self._problems: QWidget | None = None
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self.tabs = QTabWidget()
        self.tabs.setObjectName("inspector-tabs")
        self.tabs.setAccessibleName(strings.INS_NAME)
        lay.addWidget(self.tabs)
        # ---- Inspector tab
        page = QWidget()
        page_lay = QVBoxLayout(page)
        page_lay.setContentsMargins(0, 0, 0, 0)
        page_lay.setSpacing(theme.space(8))
        self.banner = Banner(theme)
        self.banner.reviseRequested.connect(self.reviseRequested)
        page_lay.addWidget(self.banner)
        self.stack = QStackedWidget()
        self.props = props if props is not None else PropertiesPanel(ctl, theme)
        self.stack.addWidget(self.props)
        facts_page = QWidget()
        facts_lay = QVBoxLayout(facts_page)
        facts_lay.setContentsMargins(0, 0, 0, 0)
        self.facts_title = heading(strings.INS_NAME)
        facts_lay.addWidget(self.facts_title)
        self.facts_table = TableView(
            DictTableModel(FACT_COLUMNS, [], theme), theme, name=strings.INS_NAME
        )
        self.facts_table.setObjectName("inspector-facts")
        self.facts_table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.facts_table.setWordWrap(True)  # long labels wrap instead of being cut off
        self.facts_table.verticalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
        facts_lay.addWidget(self.facts_table, 1)
        # the crimp tool of a contact part (the one part field a person edits here)
        self.tool_box = QWidget()
        tool_lay = QVBoxLayout(self.tool_box)
        tool_lay.setContentsMargins(theme.space(8), 0, theme.space(8), 0)
        tool_lay.setSpacing(theme.space(4))
        self.tool_label = QLabel(strings.INS_PART_TOOL)
        self.tool_label.setProperty("heading", True)
        self.tool_edit = QLineEdit()
        self.tool_edit.setObjectName("part-tool")
        self.tool_edit.setAccessibleName(strings.INS_PART_TOOL)
        self.tool_edit.setToolTip(strings.INS_PART_TOOL_TIP)
        self.tool_set = QPushButton()
        self.tool_set.setObjectName("part-tool-set")
        icon_button(
            self.tool_set,
            "pass",
            theme,
            strings.INS_PART_TOOL_SET_TIP,
            text=strings.INS_PART_TOOL_SET,
        )
        self.tool_error = QLabel()
        self.tool_error.setObjectName("part-tool-error")
        self.tool_error.setWordWrap(True)
        self.tool_error.setProperty("error", True)
        self.tool_error.setVisible(False)
        tool_row = QHBoxLayout()
        tool_row.addWidget(self.tool_edit, 1)
        tool_row.addWidget(self.tool_set)
        tool_lay.addWidget(self.tool_label)
        tool_lay.addLayout(tool_row)
        tool_lay.addWidget(self.tool_error)
        self.tool_box.setVisible(False)
        self.tool_edit.returnPressed.connect(self.apply_tool)
        self.tool_set.clicked.connect(self.apply_tool)
        facts_lay.addWidget(self.tool_box)
        self.stack.addWidget(facts_page)
        page_lay.addWidget(self.stack, 1)
        self.used_box = QWidget()
        used_lay = QVBoxLayout(self.used_box)
        used_lay.setContentsMargins(theme.space(8), 0, theme.space(8), theme.space(8))
        self.used_title = heading(strings.INS_USED_IN)
        used_lay.addWidget(self.used_title)
        self.used_none = muted(strings.INS_USED_NONE)
        used_lay.addWidget(self.used_none)
        self.used_table = TableView(
            DictTableModel(USED_COLUMNS, [], theme), theme, name=strings.INS_USED_IN
        )
        self.used_table.setObjectName("inspector-used-in")
        self.used_table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.used_table.setToolTip(strings.INS_USED_TIP)
        self.used_table.activated.connect(self._used_activated)
        used_lay.addWidget(self.used_table)
        page_lay.addWidget(self.used_box)
        self.tabs.addTab(page, strings.INS_TAB_INSPECTOR)
        # ---- Why tab
        self.why = WhyPanel(ctl, theme)
        self.tabs.addTab(self.why, strings.INS_TAB_WHY)
        self.tabs.setTabToolTip(1, strings.WHY_TAB_TIP)
        # ---- Problems tab
        self._problems_host = QWidget()
        self._problems_lay = QVBoxLayout(self._problems_host)
        self._problems_lay.setContentsMargins(0, 0, 0, 0)
        self._problems_hint = muted(strings.INS_NO_PROBLEMS_HOST)
        self._problems_lay.addWidget(self._problems_hint)
        self.tabs.addTab(self._problems_host, strings.INS_TAB_PROBLEMS)
        if problems is not None:
            self.set_problems(problems)
        # ---- wiring
        self._later = QTimer(self)
        self._later.setSingleShot(True)
        self._later.setInterval(LIST_DELAY_MS)
        self._later.timeout.connect(self._refresh_lists)
        self.props.rebuilt.connect(self._apply_locks)
        ctl.selectionChanged.connect(self._selection_changed)
        ctl.changed.connect(lambda _d: self._changed())
        ctl.stateChanged.connect(self.refresh)
        ctl.drcChanged.connect(self.refresh_badges)
        theme.changed.connect(self.refresh)
        self.refresh()

    # ---- public ------------------------------------------------------------------------------

    def set_problems(self, panel: QWidget) -> None:
        """Host the problems list (the existing `ProblemsPanel`) on the Problems tab."""
        if self._problems is not None:
            self._problems_lay.removeWidget(self._problems)
        self._problems_hint.hide()
        self._problems = panel
        self._problems_lay.addWidget(panel)
        panel.show()
        self.refresh_badges()

    def problems_panel(self) -> QWidget | None:
        return self._problems

    def show_tab(self, name: str) -> None:
        """Bring a tab to the front: "inspector", "why" or "problems"."""
        self.tabs.setCurrentIndex(TABS.index(name))

    def current(self) -> tuple[str, str] | None:
        """(kind, id) the Inspector tab is about: the pointed-at object, else the selection."""
        if self._target is not None:
            return self._target
        s = self.ctl.selection
        return (s.kind, s.id) if s is not None else None

    def show_object(self, kind: str, object_id: str, *, tab: str | None = None) -> None:
        """Point the inspector at an object. A unit or link becomes the canvas selection; a
        harness, part, interface type or configuration file shows its properties table; anything
        the Why tab knows (wire, connector, pin ...) is also given to it. `tab` brings a tab up."""
        if kind in ("unit", "interface"):
            self._target = None
            self.ctl.select(kind, object_id)
            self.refresh()
        elif kind in FACT_KINDS:
            self._target = (kind, object_id)
            self.refresh()
        from harness_design_studio.core import why as why_core

        if kind in why_core.KINDS and kind not in ("unit", "interface"):
            self.why.show_object(kind, object_id)
        if tab is not None:
            self.show_tab(tab)

    def flush(self) -> None:
        """Bring the lists ("Used in", properties) up to date now instead of after a short wait."""
        self._later.stop()
        self._refresh_lists()

    def refresh_badges(self) -> None:
        """Put the number of errors and warnings on the Problems tab."""
        counts = getattr(self._problems, "counts", None)
        n = sum(counts()) if callable(counts) else 0
        self.tabs.setTabText(
            2, strings.INS_TAB_PROBLEMS_N.format(n) if n else strings.INS_TAB_PROBLEMS
        )

    def refresh(self) -> None:
        """Bring the banner, the stack, the lists and the locks in line with the project."""
        cur = self.current()
        project = self.ctl.project
        if cur is not None and not self._exists(project, *cur):
            self._target = None
            cur = self.current()
        if cur is not None and cur[0] in FACT_KINDS:
            self._show_facts(*cur)
        else:
            self.stack.setCurrentWidget(self.props)
        self.banner.show_info(
            banner_for(project, *cur) if cur is not None else None, self.ctl.read_only
        )
        self._refresh_lists()
        self._apply_locks()
        self.refresh_badges()

    # ---- internals ---------------------------------------------------------------------------

    @staticmethod
    def _exists(project: Project, kind: str, oid: str) -> bool:
        tables: dict[str, Mapping[str, Any]] = {
            "unit": project.units,
            "interface": project.interfaces,
            "harness": project.harnesses,
            "part": project.parts,
            "interface_type": project.interface_types,
            "config": project.config,
        }
        return kind in tables and oid in tables[kind]

    def _selection_changed(self) -> None:
        self._target = None
        self.refresh()

    def _changed(self) -> None:
        sig = self._signature()
        if sig != self._lock_sig:
            self._lock_sig = sig
            self.refresh()
        else:
            self._later.start()
            self.refresh_badges()

    def _signature(self) -> object:
        p = self.ctl.project
        return (
            id(p),
            tuple((h.id, h.revision, h.status) for h in p.harnesses.values()),
            tuple(id(c) for c in p.config.values()),
            self.current(),
        )

    def _fit_tables(self) -> None:
        fit_columns(self.facts_table, (0.55, 0.45), self.theme.px(116))
        fit_columns(self.used_table, (0.22, 0.30), self.theme.px(90))

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._fit_tables()

    def showEvent(self, event: QShowEvent) -> None:  # noqa: N802
        super().showEvent(event)
        self._fit_tables()

    def _show_facts(self, kind: str, oid: str) -> None:
        self.facts_title.setText(strings.INS_FACT_KIND[kind].upper() + " " + oid)
        self.facts_table.setAccessibleName(
            strings.INS_FACTS_NAME.format(strings.INS_FACT_KIND[kind], oid)
        )
        self.facts_table.set_rows(facts_for(self.ctl.project, kind, oid))
        self.stack.setCurrentIndex(1)
        self._show_tool(kind, oid, reload=True)
        self._fit_tables()

    def _show_tool(self, kind: str, oid: str, *, reload: bool) -> None:
        """The crimp tool field: only for a part of category contact; off for a read-only project."""
        part = self.ctl.project.parts.get(oid) if kind == "part" else None
        show = part is not None and part.category == "contact"
        self.tool_box.setVisible(show)
        if not show or part is None:
            return
        if reload and not self.tool_edit.hasFocus():
            self.tool_edit.setText(part.tool or "")
        self.tool_edit.setEnabled(not self.ctl.read_only)
        self.tool_set.setEnabled(not self.ctl.read_only)
        self.tool_edit.setToolTip(
            strings.WHY_READ_ONLY if self.ctl.read_only else strings.INS_PART_TOOL_TIP
        )

    def apply_tool(self) -> bool:
        """Save the crimp tool of the part shown; a refusal (a released harness uses the part) is
        said under the field."""
        cur = self.current()
        if cur is None or cur[0] != "part" or not self.tool_set.isEnabled():
            return False
        try:
            ops = plan_set_part_tool(self.ctl.project, cur[1], self.tool_edit.text())
        except EditError as exc:
            self.tool_error.setText(str(exc))
            self.tool_error.setVisible(True)
            return False
        self.tool_error.setVisible(False)
        return not ops or self.ctl.run(strings.STEP_SET_PART_TOOL.format(cur[1]), ops)

    def _refresh_lists(self) -> None:
        cur = self.current()
        project = self.ctl.project
        if cur is not None and cur[0] in FACT_KINDS and self._exists(project, *cur):
            self.facts_table.set_rows(facts_for(project, *cur))
            self._show_tool(*cur, reload=True)
        uses = used_by(project, *cur) if cur is not None and cur[0] in USED_KINDS else []
        applicable = cur is not None and cur[0] in USED_KINDS and self._exists(project, *cur)
        self.used_box.setVisible(applicable)
        self.used_title.setText(
            strings.INS_USED_IN_N.format(len(uses)).upper() if uses else strings.INS_USED_IN.upper()
        )
        self.used_none.setVisible(applicable and not uses)
        self.used_table.setVisible(bool(uses))
        self.used_table.set_rows(used_rows(uses))
        if uses:
            _fit_height(self.used_table, len(uses))
            self._fit_tables()

    def _used_activated(self, index: QModelIndex) -> None:
        row = self.used_table.row_at(index)
        if isinstance(row, dict):
            self.showRequested.emit(str(row["key"]), str(row["id"]))

    # ---- locked fields -----------------------------------------------------------------------

    def _field_widgets(self, kind: str, oid: str) -> list[tuple[QWidget, str, str, str]]:
        """The editable widgets of the form with (widget, lock kind, lock ID, field)."""
        out: list[tuple[QWidget, str, str, str]] = []
        p = self.ctl.project
        fields = self.props.fields
        if kind == "unit":
            for key, field in (("id", "id"), ("name", "name")):
                if key in fields:
                    out.append((fields[key], "unit", oid, field))
            side = self.props.findChild(QComboBox, "unit-side")
            if side is not None:
                out.append((side, "unit", oid, "side"))
            for combo in self.props.findChildren(QComboBox):
                name = combo.objectName()
                if name.startswith("part-") and not name.startswith("part-info"):
                    out.append((combo, "box_connector", name.removeprefix("part-"), "part_id"))
            for btn in self.props.findChildren(QPushButton):
                name = btn.objectName()
                if name.startswith("confirm-"):
                    cid = name.removeprefix("confirm-")
                    for i in p.interfaces.values():
                        if any(e.connector_id == cid and e.auto for e in i.endpoints):
                            out.append((btn, "interface", i.id, "endpoints"))
        elif kind == "interface":
            for key in ("name", "max_current_a", "voltage_v", "requirement_id"):
                if key in fields:
                    out.append((fields[key], "interface", oid, key))
            chain = self.props.findChild(QComboBox, "if-chain")
            if chain is not None:
                out.append((chain, "interface", oid, "redundancy"))
            for combo in self.props.findChildren(QComboBox):
                if combo.objectName().startswith("end-"):
                    out.append((combo, "interface", oid, "endpoints"))
            confirm = self.props.findChild(QPushButton, "if-confirm")
            if confirm is not None:
                out.append((confirm, "interface", oid, "endpoints"))
        return out

    def _apply_locks(self) -> None:
        """Disable the fields a release forbids changed, with the reason as the tooltip; enable
        them again when the lock is gone. Cosmetic fields are never touched."""
        project = self.ctl.project
        cur = self.current()
        # widgets of an earlier form are gone (the panel rebuilt itself)
        self._locked_widgets = {
            w: v for w, v in self._locked_widgets.items() if _alive(w, self.props)
        }
        wanted: dict[QWidget, str] = {}
        if cur is not None and cur[0] in ("unit", "interface") and self._exists(project, *cur):
            locked = locked_objects(project)
            if locked:
                for widget, kind, oid, field in self._field_widgets(*cur):
                    reason = field_lock_reason(project, kind, oid, field, locked)
                    if reason:
                        wanted[widget] = reason
        for widget, reason in wanted.items():
            if widget not in self._locked_widgets:
                self._locked_widgets[widget] = (widget.isEnabled(), widget.toolTip())
            widget.setEnabled(False)
            widget.setToolTip(reason)
            if isinstance(widget, QLineEdit):
                widget.setAccessibleDescription(reason)
        for widget in [w for w in self._locked_widgets if w not in wanted]:
            was_enabled, tip = self._locked_widgets.pop(widget)
            widget.setEnabled(was_enabled and not self.ctl.read_only)
            widget.setToolTip(tip)

    def sizeHint(self) -> QSize:  # noqa: N802
        return QSize(self.theme.px(320), self.theme.px(640))


def _alive(widget: QWidget, root: QWidget) -> bool:
    """True if the widget is still part of the form (not one the panel threw away)."""
    try:
        return widget.isHidden() is False and root.isAncestorOf(widget)
    except RuntimeError:  # the C++ object is gone
        return False
