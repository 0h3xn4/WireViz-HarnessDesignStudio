"""The Problems list: every open finding of the project in one list, at the bottom of the window.

    panel = ProblemsList(ctl, theme)
    panel.showRequested.connect(window.show_object)

Columns: severity (icon and word), rule ID, object and message. Click a row to go to the object
(the diagram, the table or the drawing it is in). The filter keeps all, the errors or the warnings.
The list is a plain model/view table, so a project with thousands of findings stays fast; it is
filled when the panel is shown and refreshed (debounced) while it is open. It reads
`ctl.open_findings()`; the window decides where it sits.
"""

from collections.abc import Mapping
from typing import Any, Final

from PySide6.QtCore import QModelIndex, Qt, QTimer, Signal
from PySide6.QtGui import QShowEvent
from PySide6.QtWidgets import QButtonGroup, QHBoxLayout, QLabel, QToolButton, QVBoxLayout, QWidget

from harness_design_studio.core.checks import Finding
from harness_design_studio.gui import strings
from harness_design_studio.gui.controller import EditorController
from harness_design_studio.gui.tables import Column, DictTableModel, TableView
from harness_design_studio.gui.theme import ThemeManager

_SEVERITY_STATE: Final = {"error": "fail", "warning": "warning", "info": "info"}
_ORDER: Final = {"error": 0, "warning": 1, "info": 2}
FILTERS: Final = (("all", strings.PROBLEMS_FILTER_ALL), ("error", strings.CHECKS_SEVERITY["error"]),
                  ("warning", strings.CHECKS_SEVERITY["warning"]))  # fmt: skip

COLUMNS: Final = (
    Column(
        "severity",
        strings.PROBLEMS_COL_SEVERITY,
        state="state",
        fmt=lambda v: str(v[1]),
        sort_key=lambda v: v[0],
        width=110,
    ),
    Column("rule", strings.PROBLEMS_COL_RULE, mono=True, width=180),
    Column("object", strings.PROBLEMS_COL_OBJECT, mono=True, width=160),
    Column("message", strings.PROBLEMS_COL_MESSAGE, tooltip="why", width=520),
)


def problem_row(f: Finding) -> dict[str, Any]:
    word = strings.CHECKS_SEVERITY.get(f.severity, f.severity)
    order = _ORDER.get(f.severity, 3)
    return {
        "severity": (order, word),
        "state": _SEVERITY_STATE.get(f.severity, "info"),
        "rule": f.rule,
        "object": f.object_id or strings.CHECKS_WHOLE_DESIGN,
        "message": f.title,
        "why": f.why,
        "object_id": f.object_id,
        "level": f.severity,
    }


class ProblemsList(QWidget):
    showRequested = Signal(str)  # the ID of the object a row names

    def __init__(
        self, ctl: EditorController, theme: ThemeManager, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.ctl, self.theme = ctl, theme
        self.setObjectName("problems-panel")
        self.setAccessibleName(strings.PROBLEMS_PANEL_NAME)
        self._dirty = True
        self._level = "all"
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(250)  # typing and dragging cause many changes: read once
        self._timer.timeout.connect(self.refresh)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(theme.space(8), theme.space(4), theme.space(8), theme.space(8))
        bar = QHBoxLayout()
        self.filters: dict[str, QToolButton] = {}
        group = QButtonGroup(self)
        for key, label in FILTERS:
            b = QToolButton()
            b.setObjectName(f"problems-filter-{key}")
            b.setText(label)
            b.setCheckable(True)
            b.setProperty("toggle", True)
            b.setAccessibleName(label)
            group.addButton(b)
            bar.addWidget(b)
            self.filters[key] = b
            b.clicked.connect(lambda _c=False, k=key: self._filter(k))
        self.filters["all"].setChecked(True)
        self.count = QLabel()
        self.count.setObjectName("problems-count")
        self.count.setProperty("muted", True)
        bar.addWidget(self.count)
        bar.addStretch(1)
        outer.addLayout(bar)
        self.model = DictTableModel(COLUMNS, (), theme)
        self.table = TableView(self.model, theme, name=strings.PROBLEMS_PANEL_NAME)
        self.table.setObjectName("problems-table")
        outer.addWidget(self.table, 1)
        self.empty = QLabel(strings.PROBLEMS_EMPTY)
        self.empty.setObjectName("problems-empty")
        self.empty.setProperty("muted", True)
        self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        outer.addWidget(self.empty)
        self.table.clicked.connect(self._clicked)
        self.table.activated.connect(self._clicked)
        ctl.changed.connect(self._changed)
        ctl.drcStateChanged.connect(self._changed)

    # ---- data ---------------------------------------------------------------------------------
    def _changed(self, *_args: object) -> None:
        self._dirty = True
        if self.isVisible():
            self._timer.start()

    def showEvent(self, event: QShowEvent) -> None:  # noqa: N802
        super().showEvent(event)
        if self._dirty:
            self.refresh()

    def refresh(self) -> None:
        """Read the open findings now (errors first, then by rule and object)."""
        self._dirty = False
        found = sorted(
            self.ctl.open_findings(),
            key=lambda f: (_ORDER.get(f.severity, 3), f.rule, f.object_id),
        )
        self.model.update_rows([problem_row(f) for f in found])
        self.count.setText(strings.PROBLEMS_BUTTON.format(len(found)))
        self.empty.setVisible(not found)
        self.table.setVisible(bool(found))
        self._apply_filter()

    def total(self) -> int:
        return self.model.rowCount()

    def rows(self) -> list[dict[str, Any]]:
        return [dict(r) if isinstance(r, dict) else {} for r in self.model.rows()]

    # ---- filter and jump ----------------------------------------------------------------------
    def _filter(self, key: str) -> None:
        self._level = key
        self._apply_filter()

    def _apply_filter(self) -> None:
        level = self._level
        self.table.proxy.set_predicate(
            None
            if level == "all"
            else lambda row: isinstance(row, Mapping) and row.get("level") == level
        )

    def _clicked(self, index: QModelIndex) -> None:
        if not index.isValid():
            return
        source = self.table.proxy.mapToSource(index)
        row = self.model.row(source.row())  # (a dict: this table is built from dicts)
        target = row.get("object_id", "") if isinstance(row, Mapping) else ""
        if target:
            self.showRequested.emit(str(target))
