"""The History window (S4, D-191): the change journal of the open project, read-only.

    JournalDialog(parent, theme, project, start_journal=...).exec()

One row for each entry of `journal.json`: number, time (UTC), author, what kind of change, the
object and field, the value before and after, and the reason where the model holds one. The filter
box keeps the rows that contain the text you type in any column. A project that has no journal says
so and offers to start one. Opened from **Help > Change history**. Nothing here changes an entry;
the journal is append-only.
"""

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from harness_design_studio.core import journal
from harness_design_studio.core.model import Project
from harness_design_studio.gui import strings
from harness_design_studio.gui.theme import ThemeManager

COLUMNS = (
    strings.HISTORY_COL_NUMBER,
    strings.HISTORY_COL_WHEN,
    strings.HISTORY_COL_WHO,
    strings.HISTORY_COL_KIND,
    strings.HISTORY_COL_OBJECT,
    strings.HISTORY_COL_FIELD,
    strings.HISTORY_COL_OLD,
    strings.HISTORY_COL_NEW,
    strings.HISTORY_COL_REASON,
)


def _cell(value: object) -> str:
    return journal._show(value) if value is not None else ""


class JournalDialog(QDialog):
    def __init__(
        self,
        parent: QWidget | None,
        theme: ThemeManager,
        project: Project,
        start_journal: Callable[[], bool] | None = None,
    ) -> None:
        super().__init__(parent)
        self.project = project
        self._start = start_journal
        self.setObjectName("history-dialog")
        self.setWindowTitle(strings.JOURNAL_TITLE)
        self.resize(theme.px(980), theme.px(560))
        lay = QVBoxLayout(self)
        self.note = QLabel()
        self.note.setObjectName("history-note")
        self.note.setWordWrap(True)
        self.note.setProperty("muted", True)
        lay.addWidget(self.note)
        top = QHBoxLayout()
        self.filter = QLineEdit()
        self.filter.setObjectName("history-filter")
        self.filter.setPlaceholderText(strings.HISTORY_FILTER)
        self.filter.setAccessibleName(strings.HISTORY_FILTER)
        self.filter.setClearButtonEnabled(True)
        top.addWidget(self.filter, 1)
        self.start_button = QPushButton(strings.HISTORY_START)
        self.start_button.setObjectName("history-start")
        self.start_button.setToolTip(strings.HISTORY_START_TIP)
        top.addWidget(self.start_button)
        lay.addLayout(top)
        self.table = QTableWidget(0, len(COLUMNS))
        self.table.setObjectName("history-table")
        self.table.setAccessibleName(strings.JOURNAL_TITLE)
        self.table.setHorizontalHeaderLabels(list(COLUMNS))
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        lay.addWidget(self.table, 1)
        close = QPushButton(strings.CLOSE)
        close.setObjectName("history-close")
        close.clicked.connect(self.accept)
        close.setDefault(True)
        lay.addWidget(close, alignment=Qt.AlignmentFlag.AlignRight)
        self.filter.textChanged.connect(lambda _t: self._apply_filter())
        self.start_button.clicked.connect(self._start_clicked)
        self._fill()

    def _fill(self) -> None:
        j = self.project.journal
        self.start_button.setVisible(j is None and self._start is not None)
        self.filter.setEnabled(j is not None)
        entries = list(j) if j is not None else []
        self.note.setText(
            strings.HISTORY_NONE if j is None else strings.HISTORY_NOTE.format(len(entries))
        )
        self.table.setRowCount(len(entries))
        for r, e in enumerate(entries):
            for c, value in enumerate(
                (e.seq, e.when, e.author, e.kind, e.object, e.field, e.old, e.new, e.reason)
            ):
                item = QTableWidgetItem(_cell(value))
                item.setToolTip(_cell(value))
                self.table.setItem(r, c, item)
        self.table.resizeColumnsToContents()
        self.table.setColumnWidth(8, max(self.table.columnWidth(8), 260))
        self.table.scrollToBottom()
        self._apply_filter()

    def _apply_filter(self) -> None:
        """Keep the rows that contain the text in any column (case does not matter)."""
        wanted = self.filter.text().strip().casefold()
        for r in range(self.table.rowCount()):
            cells = (self.table.item(r, c) for c in range(self.table.columnCount()))
            text = " ".join(i.text() for i in cells if i is not None).casefold()
            self.table.setRowHidden(r, bool(wanted) and wanted not in text)

    def visible_rows(self) -> int:
        return sum(not self.table.isRowHidden(r) for r in range(self.table.rowCount()))

    def _start_clicked(self) -> None:
        if self._start is not None and self._start():
            self._fill()
