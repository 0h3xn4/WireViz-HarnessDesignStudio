"""The As-built area, a page of its own: what was built and measured, and what is still missing (S9).

    page = AsBuiltPage(theme, actions={"import": ..., "export": ...})
    page.show_report(asbuilt.asbuilt_report(project))

One line of intro, a summary, a table of the values that need attention (missing, out of the limit,
different from the design, stale), a box that adds every other value, and two buttons: import the
filled-in sheet, and save the sheet to fill in. It only shows and calls back; the window reads the
sheet and keeps the records (`core/asbuilt.py`). The page never says that anything passed: a value
is *within limit*, *out of limit*, *not compared* or *missing*.
"""

from collections.abc import Callable, Mapping

from PySide6.QtWidgets import QCheckBox, QFrame, QHBoxLayout, QLabel, QPushButton, QScrollArea

from harness_design_studio.core import asbuilt
from harness_design_studio.gui import strings
from harness_design_studio.gui.pages import _page
from harness_design_studio.gui.tables import Column, DictTableModel, TableView
from harness_design_studio.gui.theme import ThemeManager

ATTENTION = (asbuilt.OUT, asbuilt.MISSING, asbuilt.DIFFERS, asbuilt.STALE)
_ORDER = {
    s: n for n, s in enumerate((asbuilt.OUT, asbuilt.STALE, asbuilt.DIFFERS, asbuilt.MISSING))
}


def _cell(v: object) -> str:
    return "" if v is None else f"{v:g}" if isinstance(v, float) else str(v)


class AsBuiltPage(QScrollArea):
    def __init__(self, theme: ThemeManager, *, actions: Mapping[str, Callable[[], None]]) -> None:
        super().__init__()
        self.theme = theme
        self._actions = actions
        self._report: asbuilt.AsBuiltReport | None = None
        page, column = _page(theme, "asbuilt-page", strings.ASB_TITLE)
        self.setObjectName("asbuilt-page")
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setWidget(page.takeWidget())
        self.setAccessibleName(strings.ASB_TITLE)
        intro = QLabel(strings.ASB_INTRO)
        intro.setObjectName("asbuilt-intro")
        intro.setWordWrap(True)
        intro.setProperty("muted", True)
        self.summary = QLabel()
        self.summary.setObjectName("asbuilt-summary")
        self.summary.setWordWrap(True)
        row = QHBoxLayout()
        self.import_button = QPushButton(strings.ASB_IMPORT)
        self.import_button.setObjectName("asbuilt-import")
        self.import_button.setProperty("primary", True)
        self.import_button.setToolTip(strings.A_IMPORT_ASBUILT_TIP)
        self.import_button.clicked.connect(lambda _c=False: self._call("import"))
        self.export_button = QPushButton(strings.ASB_EXPORT)
        self.export_button.setObjectName("asbuilt-export")
        self.export_button.setToolTip(strings.A_EXPORT_ASBUILT_TIP)
        self.export_button.clicked.connect(lambda _c=False: self._call("export"))
        self.show_all = QCheckBox(strings.ASB_SHOW_ALL)
        self.show_all.setObjectName("asbuilt-show-all")
        self.show_all.setToolTip(strings.ASB_SHOW_ALL_TIP)
        self.show_all.toggled.connect(lambda _on=False: self._fill())
        row.addWidget(self.import_button)
        row.addWidget(self.export_button)
        row.addStretch(1)
        row.addWidget(self.show_all)
        columns = [
            Column("harness", strings.ASB_COLUMNS[0]),
            Column("item", strings.ASB_COLUMNS[1], mono=True),
            Column("value", strings.ASB_COLUMNS[2]),
            Column("status", strings.ASB_COLUMNS[3]),
            Column("actual", strings.ASB_COLUMNS[4], align="right"),
            Column("designed", strings.ASB_COLUMNS[5], align="right"),
            Column("note", strings.ASB_COLUMNS[6]),
        ]
        self.model = DictTableModel(columns, [], theme)
        self.table = TableView(self.model, theme, name=strings.ASB_TABLE_NAME)
        self.table.setObjectName("asbuilt-table")
        self.table.setMinimumHeight(theme.px(220))
        for w in (intro, self.summary):
            column.addWidget(w)
        column.addLayout(row)
        column.addWidget(self.table)
        column.addStretch(1)

    def _call(self, key: str) -> None:
        action = self._actions.get(key)
        if action is not None:
            action()

    def show_report(self, report: asbuilt.AsBuiltReport) -> None:
        """Show a report (the window calls this when the page is opened and when the records change)."""
        self._report = report
        self._fill()

    def _fill(self) -> None:
        report = self._report
        if report is None:
            return
        if not report.has_records:
            self.summary.setText(strings.ASB_NONE)
            self.model.set_rows([])
            return
        self.summary.setText(
            strings.ASB_SUMMARY.format(
                records=report.records,
                missing=report.missing,
                out=report.out_of_limit,
                differs=report.count(asbuilt.DIFFERS),
                stale=report.count(asbuilt.STALE),
            )
        )
        shown = [ln for ln in report.lines if self.show_all.isChecked() or ln.status in ATTENTION]
        shown.sort(key=lambda ln: (_ORDER.get(ln.status, 9), ln.harness_id, ln.kind, ln.subject))
        self.model.set_rows(
            [
                {
                    "harness": ln.harness_id,
                    "item": f"{ln.kind} {ln.subject}",
                    "value": ln.field,
                    "status": ln.status,
                    "actual": _cell(ln.actual),
                    "designed": _cell(ln.designed),
                    "note": ln.text,
                }
                for ln in shown
            ]
        )

    def rows(self) -> list[dict[str, str]]:
        """The rows on show (for the tests)."""
        return [dict(r) for r in self.model.rows()]
